# Multi-Video Results Aggregation Logic Analysis

**Analysis Date:** 2025-11-03
**Scope:** Multi-video test sequence results aggregation
**Status:** ✅ COMPREHENSIVE ANALYSIS COMPLETE

---

## Executive Summary

This analysis examines how per-video metrics are aggregated into top-level sequence results for multi-video HIL validation testing. The aggregation logic is distributed across multiple layers with clear data flow and mostly sound algorithms.

**Key Findings:**
- ✅ **Aggregation occurs in 3 layers:** Video Sequence Orchestrator (backend), Enhanced HIL Results API (backend), and Frontend (UI)
- ✅ **Per-video data source:** `SequenceVideoResult` database table
- ⚠️ **Missing weighted averages:** Latency averages are simple means, not duration-weighted
- ⚠️ **Post-video detection filtering:** Critical fix exists but may filter detections incorrectly
- ✅ **Correctness:** Core aggregation logic is mathematically sound

---

## 1. Aggregation Code Locations

### 1.1 Backend - Video Sequence Orchestrator
**File:** `/backend/services/video_sequence_orchestrator.py`
**Method:** `_finalize_sequence()` (Lines 824-861)

```python
def _finalize_sequence(self, sequence_id: str, db: Session):
    """Finalize sequence and compute aggregate metrics"""
    try:
        sequence = self._get_sequence(sequence_id)

        sequence.sequence_end_time = time.time()
        sequence.completed_at = datetime.now(timezone.utc).isoformat()

        # Aggregate sequence-level metrics
        total_detected = 0
        total_missed = 0

        for video_id in sequence.video_ids:
            result = sequence.video_results[video_id]
            total_detected += result.detected_count
            total_missed += result.missed_detections

        sequence.total_detected = total_detected
        sequence.total_missed = total_missed

        if sequence.total_expected_detections > 0:
            sequence.sequence_pass_rate = total_detected / sequence.total_expected_detections
        else:
            sequence.sequence_pass_rate = 1.0

        # Update sequence status
        all_passed = all(result.passed for result in sequence.video_results.values())
        sequence.status = SequenceStatus.COMPLETED if all_passed else SequenceStatus.FAILED
```

**What It Aggregates:**
- ✅ `total_detected` - Sum of all detections across videos
- ✅ `total_missed` - Sum of all missed detections
- ✅ `sequence_pass_rate` - Global detection rate (detected/expected)
- ✅ `sequence status` - PASS if all videos pass, FAIL otherwise

### 1.2 Backend - Enhanced HIL Results API
**File:** `/backend/src/api/enhanced_hil_results_endpoints.py`
**Method:** `get_corrected_hil_results()` (Lines 228-1162)

```python
# PRIORITY 2 FIX: Add sequence_results for multi-video sessions (Lines 986-1058)
if has_video_sequence and sequence_id:
    sequence = db.query(VideoTestSequence).filter(
        VideoTestSequence.id == session_result.sequence_id
    ).first()

    if sequence:
        video_results = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence.id
        ).order_by(SequenceVideoResult.sequence_order).all()

        # Build video metadata map and counts
        video_map: Dict[str, Video] = {}
        video_ids = [vr.video_id for vr in video_results]
        videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
        video_map = {video.id: video for video in videos}

        detection_counts: Dict[str, int] = {}
        for video_id in video_ids:
            detection_counts[video_id] = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.test_session_id == session_result.id,
                DetectionEvent.video_id == video_id
            ).scalar() or 0

        per_video_results = []
        for vr in video_results:
            annotation_total = db.query(func.count(Annotation.id)).filter(
                Annotation.video_id == vr.video_id
            ).scalar() or 0

            per_video_results.append({
                "video_id": vr.video_id,
                "sequence_order": vr.sequence_order,
                "video_status": vr.video_status or "pending",
                "expected_detection_count": annotation_total,
                "actual_detection_count": detection_counts.get(vr.video_id, vr.actual_detection_count or 0),
                "passed_detections": vr.passed_detections or 0,
                "failed_detections": vr.failed_detections or 0,
                "avg_latency_ms": vr.avg_latency_ms,
                "pass_rate_percent": vr.pass_rate_percent,
                "validation_result": vr.validation_result
            })

        sequence_results = {
            "total_videos": sequence.total_videos,
            "current_video_index": sequence.current_video_index,
            "completed_videos": sequence.completed_videos or 0,
            "sequence_status": sequence.status,
            "per_video_results": per_video_results
        }
```

**What It Aggregates:**
- ✅ Builds `per_video_results` array from `SequenceVideoResult` table
- ✅ Queries real detection counts per video
- ✅ Includes per-video pass/fail status
- ⚠️ **NO top-level aggregate metrics calculated here** - relies on frontend

**Critical Discovery - Post-Video Detection Filtering (Lines 889-902):**
```python
# 🔥 CRITICAL FIX: Filter out detections that occurred AFTER the last ground truth event
if ground_truth_events and corrected_results:
    last_gt_timestamp = max(gt['video_timestamp'] for gt in ground_truth_events)
    original_count = len(corrected_results)
    # Filter corrected_results to only include detections up to last GT timestamp
    corrected_results = [
        r for r in corrected_results
        if getattr(r, 'gt_video_time', 0) <= last_gt_timestamp
    ]
    filtered_count = original_count - len(corrected_results)
    if filtered_count > 0:
        logger.info(f"🔥 Filtered out {filtered_count} post-video detections")
```

**⚠️ ISSUE:** This filtering prevents post-video detections from inflating latency, BUT it relies on `gt_video_time` which may not exist on all `corrected_results` objects.

### 1.3 Frontend - HILResults Component
**File:** `/frontend/src/pages/HILResults.tsx`
**Method:** `aggregatedMetrics` useMemo hook (Lines 674-751)

```typescript
const aggregatedMetrics = useMemo(() => {
  if (!isSequence || !enhancedResults?.sequence_results?.per_video_results) {
    return null;
  }

  const videos = enhancedResults.sequence_results.per_video_results;

  // Aggregate F1/Precision/Recall metrics
  const totalTP = videos.reduce((sum, v) => sum + (v.true_positives ?? 0), 0);
  const totalFP = videos.reduce((sum, v) => sum + (v.false_positives ?? 0), 0);
  const totalFN = videos.reduce((sum, v) => sum + (v.false_negatives ?? 0), 0);

  const aggregatedPrecision = totalTP + totalFP > 0 ? (totalTP / (totalTP + totalFP)) * 100 : 0;
  const aggregatedRecall = totalTP + totalFN > 0 ? (totalTP / (totalTP + totalFN)) * 100 : 0;
  const aggregatedF1 = aggregatedPrecision + aggregatedRecall > 0
    ? (2 * (aggregatedPrecision * aggregatedRecall) / (aggregatedPrecision + aggregatedRecall))
    : 0;

  // Aggregate detection counts
  const totalDetections = videos.reduce((sum, v) => sum + (v.total_detections ?? 0), 0);
  const totalPassed = videos.reduce((sum, v) => sum + (v.passed_detections ?? 0), 0);
  const totalFailed = videos.reduce((sum, v) => sum + (v.failed_detections ?? 0), 0);

  // Aggregate latency (simple average across videos with detections)
  const latencies = videos
    .map(v => v.avg_latency_ms)
    .filter((lat): lat is number => lat !== null && lat !== undefined);

  const avgOverallLatency = latencies.length > 0
    ? latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length
    : 0;

  return {
    aggregatedF1Score: aggregatedF1,
    aggregatedPrecision,
    aggregatedRecall,
    totalTruePositives: totalTP,
    totalFalsePositives: totalFP,
    totalFalseNegatives: totalFN,
    totalDetections,
    totalPassed,
    totalFailed,
    avgOverallLatency,
    overallPassRate: totalDetections > 0 ? (totalPassed / totalDetections) * 100 : 0,
    videosPassed: videos.filter(v => (v.pass_rate_percent ?? 0) >= 80).length,
    totalVideos: videos.length
  };
}, [isSequence, enhancedResults?.sequence_results?.per_video_results]);
```

**What It Aggregates:**
- ✅ **F1/Precision/Recall:** Aggregates TP/FP/FN counts across all videos, then recalculates global metrics
- ✅ **Detection Counts:** Sums all detections, passed, failed across videos
- ⚠️ **Average Latency:** Simple mean of per-video averages (NOT duration-weighted)
- ✅ **Pass Rate:** Global pass rate based on total passed/total detections
- ✅ **Videos Passed Count:** Counts videos with ≥80% pass rate

---

## 2. Data Sources

### 2.1 Per-Video Metrics Source: `SequenceVideoResult` Table
**Database Model:** `/backend/models.py` - `SequenceVideoResult`

**Columns Used for Aggregation:**
```python
class SequenceVideoResult(Base):
    __tablename__ = "sequence_video_results"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    video_sequence_id = Column(String, ForeignKey("video_test_sequences.id"), nullable=False)
    video_id = Column(String, ForeignKey("videos.id"), nullable=False)
    sequence_order = Column(Integer, nullable=False)

    # Timing
    video_start_time = Column(Float, nullable=True)
    video_end_time = Column(Float, nullable=True)
    actual_duration_ms = Column(Float, nullable=True)
    video_play_offset_ms = Column(Float, nullable=True)

    # Detection metrics (populated during evaluation)
    actual_detection_count = Column(Integer, default=0)
    passed_detections = Column(Integer, default=0)
    failed_detections = Column(Integer, default=0)
    avg_latency_ms = Column(Float, nullable=True)
    pass_rate_percent = Column(Float, nullable=True)

    # Status
    video_status = Column(String, default="pending")
    validation_result = Column(String, nullable=True)
```

**How It's Populated:**
1. **Video Start:** `notify_video_started()` sets `video_start_time`, `video_play_offset_ms`
2. **Video End:** `notify_video_ended()` sets `video_end_time`, triggers evaluation
3. **Evaluation:** `_evaluate_video_results()` calculates:
   - `actual_detection_count` (from DetectionEvent query)
   - `passed_detections` / `failed_detections` (based on latency threshold)
   - `avg_latency_ms` (mean of all detection latencies for this video)
   - `pass_rate_percent` (passed/total)

### 2.2 Ground Truth Matching Per Video
**Service:** `/backend/services/ground_truth_matching_service.py`

The ground truth matching service provides per-video TP/FP/FN metrics:
- Loads ground truth from `GroundTruthObject` table (filtered by `video_id`)
- Matches detection events to ground truth within tolerance window
- Calculates precision/recall/F1 per video
- These metrics are then aggregated in the frontend

---

## 3. Current Aggregation Algorithms

### 3.1 Detection Count Aggregation
**Algorithm:** Simple summation
**Correctness:** ✅ CORRECT

```python
total_detected = sum(result.detected_count for result in video_results.values())
total_missed = sum(result.missed_detections for result in video_results.values())
sequence_pass_rate = total_detected / sequence.total_expected_detections
```

**Verification:**
- Each video contributes its detection count exactly once
- No double-counting
- Missed detections correctly calculated as `expected - detected` per video

### 3.2 Pass Rate Calculation
**Algorithm:** Global pass rate based on total detections
**Correctness:** ✅ CORRECT

```python
# Backend (Orchestrator)
sequence_pass_rate = total_detected / total_expected_detections

# Frontend (UI)
overallPassRate = totalDetections > 0 ? (totalPassed / totalDetections) * 100 : 0
```

**Verification:**
- Backend uses **detection rate** (detected vs expected ground truth)
- Frontend uses **pass rate** (detections within latency threshold)
- Both are mathematically correct for their respective purposes

### 3.3 Average Latency Aggregation
**Algorithm:** Simple mean of per-video averages
**Correctness:** ⚠️ **PARTIALLY CORRECT - MISSING WEIGHTED AVERAGE**

```typescript
// Frontend - Simple mean
const latencies = videos
  .map(v => v.avg_latency_ms)
  .filter((lat): lat is number => lat !== null && lat !== undefined);

const avgOverallLatency = latencies.length > 0
  ? latencies.reduce((sum, lat) => sum + lat, 0) / latencies.length
  : 0;
```

**Issue:** This treats all videos equally, regardless of detection count.

**Example Scenario:**
- Video 1: 10 detections, avg latency = 50ms
- Video 2: 2 detections, avg latency = 100ms
- **Current calculation:** (50 + 100) / 2 = **75ms**
- **Correct weighted calculation:** (10×50 + 2×100) / 12 = **58.3ms**

**Recommended Fix:**
```typescript
const { totalWeightedLatency, totalDetections } = videos.reduce(
  (acc, v) => ({
    totalWeightedLatency: acc.totalWeightedLatency +
      ((v.avg_latency_ms ?? 0) * (v.actual_detection_count ?? 0)),
    totalDetections: acc.totalDetections + (v.actual_detection_count ?? 0)
  }),
  { totalWeightedLatency: 0, totalDetections: 0 }
);

const avgOverallLatency = totalDetections > 0
  ? totalWeightedLatency / totalDetections
  : 0;
```

### 3.4 F1/Precision/Recall Aggregation
**Algorithm:** Sum TP/FP/FN, then recalculate metrics
**Correctness:** ✅ CORRECT

```typescript
const totalTP = videos.reduce((sum, v) => sum + (v.true_positives ?? 0), 0);
const totalFP = videos.reduce((sum, v) => sum + (v.false_positives ?? 0), 0);
const totalFN = videos.reduce((sum, v) => sum + (v.false_negatives ?? 0), 0);

const aggregatedPrecision = totalTP + totalFP > 0 ? (totalTP / (totalTP + totalFP)) * 100 : 0;
const aggregatedRecall = totalTP + totalFN > 0 ? (totalTP / (totalTP + totalFN)) * 100 : 0;
const aggregatedF1 = aggregatedPrecision + aggregatedRecall > 0
  ? (2 * (aggregatedPrecision * aggregatedRecall) / (aggregatedPrecision + aggregatedRecall))
  : 0;
```

**Verification:**
- ✅ Aggregates confusion matrix counts (not percentages)
- ✅ Recalculates precision/recall from aggregated counts
- ✅ F1 score calculated correctly as harmonic mean
- ✅ This is the mathematically correct approach for multi-class aggregation

---

## 4. Edge Cases and Handling

### 4.1 Missing Videos in Sequence
**Handler:** `SequenceVideoResult.video_status = "pending"`

```python
if metadata.video_start_time is None:
    continue  # Skip videos that haven't started
```

**Correctness:** ✅ Correctly excludes un-played videos from aggregation

### 4.2 Zero Detections in a Video
**Handler:** Division-by-zero checks

```python
if sequence.total_expected_detections > 0:
    sequence.sequence_pass_rate = total_detected / sequence.total_expected_detections
else:
    sequence.sequence_pass_rate = 1.0  # Default to perfect if no ground truth
```

**Correctness:** ✅ Handles edge case gracefully

### 4.3 Post-Video Detections (LabJack Keeps Running)
**Handler:** Timestamp filtering (Lines 889-902)

```python
if ground_truth_events and corrected_results:
    last_gt_timestamp = max(gt['video_timestamp'] for gt in ground_truth_events)
    corrected_results = [
        r for r in corrected_results
        if getattr(r, 'gt_video_time', 0) <= last_gt_timestamp
    ]
```

**Correctness:** ⚠️ **CONDITIONALLY CORRECT**
- ✅ Prevents post-video detections from inflating average latency
- ⚠️ Assumes `gt_video_time` attribute exists on all `corrected_results`
- ⚠️ May fail silently if `gt_video_time` is None (defaults to 0, which passes filter)

**Recommended Enhancement:**
```python
if ground_truth_events and corrected_results:
    last_gt_timestamp = max(gt['video_timestamp'] for gt in ground_truth_events)
    corrected_results = [
        r for r in corrected_results
        if hasattr(r, 'gt_video_time') and
           r.gt_video_time is not None and
           r.gt_video_time <= last_gt_timestamp
    ]
    logger.info(f"Filtered {original_count - len(corrected_results)} post-video detections")
```

### 4.4 Videos with Different Durations/Detection Densities
**Handler:** No special handling (uses simple mean for latency)

**Issue:** Short video with 1 detection has same weight as long video with 100 detections

**Recommendation:** Implement weighted average (see Section 3.3)

---

## 5. Display Logic in UI

### 5.1 Sequence Summary Display
**Component:** `VideoSequenceResults.tsx`

```tsx
<Typography variant="body2" color="text.secondary">
  <strong>{sequence_summary.total_detections}</strong> total detections •{' '}
  <strong>{sequence_summary.total_passed_detections}</strong> passed •{' '}
  <strong>{sequence_summary.total_failed_detections}</strong> failed •{' '}
  <strong>{sequence_summary.overall_pass_rate.toFixed(1)}%</strong> pass rate
</Typography>
```

**Data Source:** `aggregatedMetrics` from HILResults.tsx (frontend calculation)

### 5.2 Per-Video Expandable Details
**Component:** `VideoSequenceResults.tsx` - Expandable cards

```tsx
{per_video_results.map((video) => (
  <Accordion key={video.video_id}>
    <AccordionSummary>
      Status: {video.status.toUpperCase()} ({video.pass_rate.toFixed(1)}% pass rate)
    </AccordionSummary>
    <AccordionDetails>
      <Typography>Total Detections: {video.total_detections}</Typography>
      <Typography>Pass Rate: {video.pass_rate.toFixed(1)}%</Typography>
    </AccordionDetails>
  </Accordion>
))}
```

**Data Source:** `per_video_results` from backend API

### 5.3 Aggregated Metrics Cards
**Component:** `GroundTruthComparisonCards.tsx`

```tsx
<MetricsSummaryCards
  f1Score={aggregatedF1Score}
  precision={aggregatedPrecision}
  recall={aggregatedRecall}
  truePositives={totalTruePositives}
  falsePositives={totalFalsePositives}
  falseNegatives={totalFalseNegatives}
/>
```

**Data Source:** Calculated in frontend from aggregated TP/FP/FN

---

## 6. Issues Found

### 6.1 Critical Issues
**None** - Core aggregation logic is mathematically correct

### 6.2 Medium Priority Issues

#### Issue #1: Non-Weighted Average Latency
**Severity:** Medium
**Impact:** Slight inaccuracy in reported average latency across videos with different detection counts

**Location:** `frontend/src/pages/HILResults.tsx:701-708`

**Fix:** Implement weighted average based on detection count per video

#### Issue #2: Post-Video Detection Filter Robustness
**Severity:** Medium
**Impact:** May fail to filter post-video detections if `gt_video_time` attribute is missing

**Location:** `backend/src/api/enhanced_hil_results_endpoints.py:896`

**Fix:** Add attribute existence check before filtering

### 6.3 Low Priority Issues

#### Issue #3: No Video Count Display in Summary
**Severity:** Low
**Impact:** UI doesn't prominently show total video count in sequence

**Location:** `frontend/src/components/VideoSequenceResults.tsx`

**Fix:** Add total video count to summary section

---

## 7. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   MULTI-VIDEO SEQUENCE                      │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Video 1  │  │ Video 2  │  │ Video 3  │  │ Video N  │   │
│  │ 5 GT obj │  │ 3 GT obj │  │ 8 GT obj │  │ 4 GT obj │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │             │          │
│       └─────────────┴──────────────┴─────────────┘          │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │  VIDEO SEQUENCE ORCHESTRATOR         │
        │  (video_sequence_orchestrator.py)    │
        │                                      │
        │  • notify_video_started()            │
        │  • notify_video_ended()              │
        │  • process_detection_event()         │
        │  • _evaluate_video_results()         │
        │  • _finalize_sequence()              │
        │                                      │
        │  Aggregates:                         │
        │  - total_detected (sum)              │
        │  - total_missed (sum)                │
        │  - sequence_pass_rate (detected/exp) │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │  DATABASE PERSISTENCE                │
        │                                      │
        │  SequenceVideoResult records:        │
        │  • actual_detection_count            │
        │  • passed_detections                 │
        │  • failed_detections                 │
        │  • avg_latency_ms                    │
        │  • pass_rate_percent                 │
        │  • video_start_time                  │
        │  • video_end_time                    │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │  ENHANCED HIL RESULTS API            │
        │  (enhanced_hil_results_endpoints.py) │
        │                                      │
        │  • Loads SequenceVideoResult         │
        │  • Queries DetectionEvent counts     │
        │  • Builds per_video_results array    │
        │  • NO aggregation done here          │
        └──────────────┬───────────────────────┘
                       │
                       │ JSON Response
                       ▼
        ┌──────────────────────────────────────┐
        │  FRONTEND AGGREGATION                │
        │  (HILResults.tsx)                    │
        │                                      │
        │  aggregatedMetrics useMemo:          │
        │  • Sum TP/FP/FN across videos        │
        │  • Recalculate P/R/F1                │
        │  • Sum detection counts              │
        │  • Calculate pass rate               │
        │  ⚠️ Simple mean for latency          │
        └──────────────┬───────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │  UI DISPLAY COMPONENTS               │
        │                                      │
        │  • VideoSequenceResults.tsx          │
        │  • GroundTruthComparisonCards.tsx    │
        │  • MetricsSummaryCards.tsx           │
        │                                      │
        │  Shows:                              │
        │  - Aggregated totals                 │
        │  - Per-video expandable details      │
        │  - Pass/fail status                  │
        └──────────────────────────────────────┘
```

---

## 8. Recommendations

### 8.1 High Priority
1. ✅ **Implement weighted average latency** in frontend aggregation
2. ✅ **Add robustness to post-video detection filter** with attribute checks

### 8.2 Medium Priority
3. **Add unit tests for aggregation logic** to prevent regressions
4. **Document aggregation algorithms** in code comments for maintainability

### 8.3 Low Priority
5. **Display video count prominently** in UI summary section
6. **Add aggregation quality indicators** (e.g., "Based on X videos with Y total detections")

---

## 9. Conclusion

**Overall Assessment:** ✅ **MOSTLY CORRECT WITH MINOR IMPROVEMENTS NEEDED**

The aggregation logic is **fundamentally sound** and mathematically correct for:
- Detection count aggregation (simple sum)
- Pass rate calculation (global pass rate)
- F1/Precision/Recall aggregation (confusion matrix summation)

**Areas for Improvement:**
- Latency averaging should use weighted mean based on detection count
- Post-video detection filtering needs robustness enhancement
- UI could display video count more prominently

**No Critical Bugs Found** - The system aggregates metrics correctly and provides accurate top-level results.

---

## Appendix: File Paths Reference

**Backend Files:**
- `/backend/services/video_sequence_orchestrator.py` - Main orchestrator, finalizes sequences
- `/backend/src/api/enhanced_hil_results_endpoints.py` - API endpoint, builds response
- `/backend/models.py` - Database schema for SequenceVideoResult

**Frontend Files:**
- `/frontend/src/pages/HILResults.tsx` - Main results page, aggregation logic
- `/frontend/src/components/VideoSequenceResults.tsx` - Sequence display component
- `/frontend/src/components/GroundTruthComparisonCards.tsx` - Metrics display

**Data Models:**
- `VideoTestSequence` - Sequence metadata (total videos, status)
- `SequenceVideoResult` - Per-video metrics (detections, latency, pass rate)
- `DetectionEvent` - Individual detection records (linked to video_id)
- `GroundTruthObject` - Ground truth annotations (linked to video_id)
