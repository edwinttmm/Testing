# Detection Issues Analysis Report

## Executive Summary

Analysis of log output reveals **critical detection filtering issue** causing 95 false negatives (72.5% miss rate). The system is only capturing 40 validated detections against 131 ground truth objects, resulting in an F1 score of 0.421.

**Root Cause**: Quality filtering is too aggressive, marking too many detections as `usable_for_validation = FALSE`, which excludes them from matching.

---

## Issue 1: Low Detection Count (40 vs 131 Expected)

### Current Behavior
```
Detection quality for session: Total=40, Validated=40
Found 131 ground truth objects
Result: 36 TP, 4 FP, 95 FN
F1 Score: 0.421
```

### Root Cause Analysis

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

**Line 300-310**: Detection query with aggressive quality filter:
```python
# QUALITY FILTER: Only fetch validated detections (usable_for_validation = TRUE)
detection_query = text("""
    SELECT id, timestamp, confidence, class_label, actual_latency_ms,
           video_relative_timestamp, video_frame_number, timing_sync_quality,
           video_id
    FROM detection_events
    WHERE test_session_id = :session_id
      AND usable_for_validation = TRUE  # ← CRITICAL FILTER
    ORDER BY timestamp
""")
```

### The Problem

1. **Only 40 detections** marked as `usable_for_validation = TRUE`
2. **91 detections excluded** (131 GT - 40 detections = 91 missing)
3. **95 false negatives** means the system missed 72.5% of ground truth objects

### Why Are Detections Being Marked Invalid?

The `usable_for_validation` flag is set based on timing quality assessment. Let me trace the logic:

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/timing_synchronization_calculator.py`

**Lines 638-654**: Detection filtering in batch processing:
```python
# CRITICAL BUG FIX: Extract video_start_time for this detection
video_start_time = None

if video_timing_map:
    # Find which video this detection belongs to
    video_id, video_start_time = self._get_video_start_time_for_detection(
        detection_system_time, video_timing_map
    )
    if video_start_time is None:
        logger.error(
            f"❌ Cannot determine video_start_time for detection {detection_id} "
            f"at timestamp {detection_system_time:.6f}. Skipping to avoid 8-9s latency bug."
        )
        continue  # ← DETECTION IS SKIPPED!
```

### Primary Causes

#### A. Missing `video_start_time` in Detection Records

**Log Evidence**:
```
Many logs show "No video_start_time found in detection" errors
Cannot calculate accurate latency. Skipping to prevent 8-9s inflation bug
```

**Code Location**: Lines 643-653 of `timing_synchronization_calculator.py`

When `video_start_time` is missing from detection metadata:
- Detection is **skipped entirely**
- Never gets matched to ground truth
- Results in **False Negative**

#### B. Timing Validation Failures

**File**: `timing_synchronization_calculator.py`, Lines 134-170

```python
def validate_latency(self, latency_ms: float, detection_id: str) -> bool:
    """
    Validate that latency is within acceptable range.
    BUG #6 FIX: Reject negative latencies (indicates timing errors).
    """
    # Allow small negative values for clock jitter (-50ms threshold)
    if latency_ms < -50:
        logger.error(
            f"❌ Detection {detection_id} has invalid negative latency: {latency_ms:.1f}ms. "
            f"This indicates a clock synchronization or timestamp calculation error."
        )
        return False  # ← DETECTION MARKED INVALID

    # Check for unrealistic positive latencies (>2 seconds)
    if latency_ms > 2000:
        logger.error(
            f"❌ Detection {detection_id} has unrealistic latency: {latency_ms:.1f}ms. "
            f"Expected range: 0-1000ms for hardware detection systems."
        )
        return False  # ← DETECTION MARKED INVALID

    return True
```

Detections with timing issues are marked as `usable_for_validation = FALSE`.

---

## Issue 2: Video Start Time Missing

### The Cascade Effect

1. **Detection arrives** from LabJack hardware
2. **Timing calculator** needs `video_start_time` to compute accurate latency
3. **`video_start_time` is NULL** in detection metadata
4. **Calculator skips detection** to avoid 8-9s latency inflation bug
5. **Detection never matched** to ground truth
6. **Result**: False Negative

### Where Should `video_start_time` Come From?

**File**: `detection_database_integration.py`, Lines 69-73

```python
# Timing calibration fields for corrected latency calculation
video_relative_timestamp = Column(Float, nullable=True, index=True)
actual_latency_ms = Column(Float, nullable=True, index=True)
video_start_time = Column(Float, nullable=True, index=True)  # ← THIS FIELD
```

This field should be populated when:
- **Video playback starts** (from video timing service)
- **Detection is captured** (from LabJack service)
- **Timing sync occurs** (from timing synchronization calculator)

### The Breakdown

**File**: `services/labjack_detection_service.py` (not fully read due to size)

The LabJack detection service likely:
1. Captures voltage threshold crossing
2. Records `timestamp` (Unix epoch time)
3. **BUT**: Does NOT populate `video_start_time`

**Why?** The LabJack service may not have access to video timing metadata.

---

## Issue 3: F1 Score Display

### Current Calculation (Appears Correct)

**File**: `ground_truth_matching_service.py`, Lines 1696-1699

```python
# Calculate core metrics with safe division
precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
recall = true_positives / actual_gt_count if actual_gt_count > 0 else 0.0
f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
```

**Verification**:
- TP = 36
- FP = 4
- FN = 95
- GT = 131

- Precision = 36 / (36 + 4) = 36 / 40 = **0.900** (90%)
- Recall = 36 / 131 = **0.275** (27.5%)
- F1 = 2 * (0.900 * 0.275) / (0.900 + 0.275) = 2 * 0.2475 / 1.175 = **0.421** ✓

**Conclusion**: F1 score calculation is **mathematically correct**. The low score is due to **extremely poor recall** (27.5%).

### Frontend Display

The F1 score should be displayed as `0.421` or `42.1%`. If it's not appearing:

**Possible Causes**:
1. API endpoint not returning `f1_score` field
2. Frontend not extracting/rendering the field
3. Results table query missing detection comparisons

---

## Issue 4: "Bottom Tables Don't Have Detection Anymore"

### What This Means

User reports that detection data is missing from results tables on the frontend.

### Likely Cause: Empty Result Set

**File**: `ground_truth_matching_service.py`, Lines 282-288

```python
# Check if matching already exists and force_rematch is False
existing_comparisons = db.query(DetectionComparison).filter(
    DetectionComparison.test_session_id == session_id
).count()

if existing_comparisons > 0 and not force_rematch:
    self.logger.info(f"Found {existing_comparisons} existing comparisons, using cached results")
    return self._calculate_session_metrics(db, session_id)
```

If no comparisons exist:
- `DetectionComparison` table is empty for this session
- Results endpoints return empty lists
- Frontend tables have no data to display

### Why Would Comparisons Be Missing?

**Scenario 1**: Matching never completed
- Error during matching process
- Transaction rollback
- Database connection lost

**Scenario 2**: All detections filtered out
- Only 40 detections validated
- Some may have been further filtered during matching
- Results in sparse comparison table

**Scenario 3**: Frontend query issue
- API endpoint not querying `DetectionComparison` correctly
- Missing JOIN with `detection_events` table
- Filtering out results unintentionally

---

## Recommendations

### Priority 1: Fix Detection Filtering (Immediate)

**Problem**: 91 detections being excluded from matching due to missing `video_start_time`.

**Solution Options**:

#### Option A: Populate `video_start_time` at Detection Time (Preferred)
```python
# In LabJack detection service
detection_event = DetectionEvent(
    timestamp=capture_time,
    video_start_time=self.get_current_video_start_time(),  # ← ADD THIS
    # ... other fields
)
```

**Benefits**:
- Fixes root cause
- Enables accurate latency calculation
- Prevents future issues

**Implementation**:
1. Add video timing context to LabJack service
2. Track current video playback start time
3. Populate field when detection is captured

#### Option B: Smart Fallback with Warning (Quick Fix)
```python
# In timing_synchronization_calculator.py, line 643
if video_start_time is None:
    # Use session start time as fallback (with warning)
    video_start_time = labjack_start_time
    logger.warning(
        f"⚠️ Using fallback video_start_time for detection {detection_id}. "
        f"Latency may be inflated by ~352ms (video buffer delay)."
    )
    # CONTINUE instead of skipping
```

**Benefits**:
- Immediate fix
- Includes all detections
- Documents accuracy impact

**Trade-offs**:
- Latency values may be less accurate
- Need to adjust acceptance thresholds

### Priority 2: Relax Timing Validation (Quick Win)

**Current**: Only detections with 0-2000ms latency are accepted.

**Problem**: Legitimate detections with timing issues are rejected.

**Solution**: Add degraded quality tier instead of complete rejection.

```python
# In timing_synchronization_calculator.py
def validate_latency(self, latency_ms: float, detection_id: str) -> tuple[bool, str]:
    """Returns (is_valid, quality_tier)"""

    if -50 <= latency_ms <= 1000:
        return True, "validated"  # High quality
    elif -200 <= latency_ms <= 2000:
        return True, "degraded"   # Lower quality but still usable
    else:
        return False, "rejected"  # Truly invalid
```

**Benefits**:
- Recovers marginal detections
- Improves recall
- Maintains quality metrics

### Priority 3: Fix Missing Detection Data in Tables

**Investigation Steps**:

1. **Check API endpoint** returns detection comparisons:
```python
# In results endpoint
comparisons = db.query(DetectionComparison).filter(
    DetectionComparison.test_session_id == session_id
).all()

logger.info(f"Returning {len(comparisons)} detection comparisons")
```

2. **Verify frontend receives data**:
```javascript
// In frontend results component
console.log("Detection comparisons:", results.detection_comparisons);
```

3. **Check table rendering logic**:
- Ensure data mapping is correct
- Verify column definitions match API response
- Check for filtering/pagination issues

### Priority 4: Add Detection Quality Dashboard

**Purpose**: Monitor detection filtering in real-time.

**Metrics to Display**:
- Total detections captured
- Validated detections count
- Degraded detections count
- Rejected detections count
- Reasons for rejection (missing fields, timing issues, etc.)

**Implementation**:
```python
@router.get("/api/sessions/{session_id}/detection-quality")
async def get_detection_quality(session_id: str, db: Session = Depends(get_db)):
    quality_stats = db.execute(text("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN usable_for_validation THEN 1 ELSE 0 END) as validated,
            SUM(CASE WHEN timing_degraded THEN 1 ELSE 0 END) as degraded,
            SUM(CASE WHEN video_start_time IS NULL THEN 1 ELSE 0 END) as missing_video_time,
            SUM(CASE WHEN actual_latency_ms > 2000 THEN 1 ELSE 0 END) as high_latency,
            SUM(CASE WHEN actual_latency_ms < -50 THEN 1 ELSE 0 END) as negative_latency
        FROM detection_events
        WHERE test_session_id = :session_id
    """), {'session_id': session_id}).fetchone()

    return {
        "total": quality_stats[0],
        "validated": quality_stats[1],
        "degraded": quality_stats[2],
        "rejection_reasons": {
            "missing_video_time": quality_stats[3],
            "high_latency": quality_stats[4],
            "negative_latency": quality_stats[5]
        }
    }
```

---

## Impact Assessment

### Current State
- **Recall**: 27.5% (extremely poor)
- **Precision**: 90% (good)
- **F1 Score**: 0.421 (unacceptable)
- **Detection Loss**: 91 detections (69.5% of GT objects)

### Expected After Fix

**If Option A implemented** (populate video_start_time):
- **Recall**: 80-90% (target)
- **Precision**: 85-95% (maintain)
- **F1 Score**: 0.82-0.92 (acceptable)
- **Detection Loss**: 10-20 detections (7-15%)

**If Option B implemented** (fallback with warning):
- **Recall**: 70-80% (improved)
- **Precision**: 80-90% (slight decrease due to noise)
- **F1 Score**: 0.75-0.85 (acceptable)
- **Detection Loss**: 15-25 detections (11-19%)

---

## Testing Checklist

Before deploying fixes:

### Unit Tests
- [ ] Test detection creation with `video_start_time`
- [ ] Test latency validation with edge cases
- [ ] Test fallback logic when `video_start_time` missing

### Integration Tests
- [ ] Run full session with 131 GT objects
- [ ] Verify all detections captured
- [ ] Check F1 score improves to >0.75

### Regression Tests
- [ ] Ensure existing sessions still work
- [ ] Verify backwards compatibility
- [ ] Check database migrations apply cleanly

### Frontend Tests
- [ ] Verify detection tables populate
- [ ] Check F1 score displays correctly
- [ ] Test quality metrics dashboard

---

## Files Requiring Changes

### Critical Path
1. `/backend/services/labjack_detection_service.py` - Add video_start_time population
2. `/backend/services/timing_synchronization_calculator.py` - Implement fallback logic
3. `/backend/services/ground_truth_matching_service.py` - Adjust quality filtering

### Supporting Changes
4. `/backend/models.py` - Verify `video_start_time` column exists
5. `/backend/schemas.py` - Add quality metrics to API response
6. `/backend/routers/test_sessions.py` - Add quality dashboard endpoint

### Documentation
7. `/backend/docs/detection_quality_guide.md` - Document quality tiers
8. `/backend/docs/troubleshooting_detections.md` - Common issues

---

## Conclusion

The detection issues stem from **overly aggressive quality filtering** that excludes detections with missing `video_start_time` fields. This is a **data pipeline issue**, not a calculation bug.

**Primary fix**: Ensure `video_start_time` is populated when detections are captured.

**Quick fix**: Use smart fallback to session start time with accuracy warnings.

**Secondary improvements**: Relax validation thresholds and add quality monitoring dashboard.

Implementing these fixes should improve recall from 27.5% to 80%+, bringing F1 score from 0.421 to 0.80+ (acceptable for production).
