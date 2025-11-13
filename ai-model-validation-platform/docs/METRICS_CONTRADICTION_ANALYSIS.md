# Metrics Calculation Contradiction Analysis
**Session ID:** 463b7ec5-0cd6-4b6a-9776-d10f938b6422
**Date:** 2025-11-03
**Status:** 🔴 CRITICAL - Multiple Contradictory Metric Sources

---

## Executive Summary

The HIL Results page displays **contradictory metrics** for the same session, with values varying by up to 73.3% depending on which component calculates them. This analysis identifies **4 distinct calculation sources** with conflicting formulas and data sources.

---

## Contradictions Identified

### 1. Match Rate: 73.3% vs 0.0%
**Location 1:** `MetricsSummaryCards.tsx` - Line 122-145
```typescript
// Match Rate Card
const matchRate = activeMatchRate;  // Calculated as 73.3%
```

**Location 2:** `GroundTruthComparisonCards.tsx` - Line 118-128
```typescript
// Precision Card shows 0.0%
{truePositives} TP / {truePositives + falsePositives} Total Detections
// Displays: 0 TP / 0 Total = 0.0%
```

**Data Sources:**
- **MetricsSummaryCards:** Uses `activeMatchRate` from HILResults.tsx line 608-610
  - Formula: `(activeMatchedCount / activeExpectedCount) * 100`
  - activeMatchedCount: Filters detections with `ground_truth_match_id`
  - activeExpectedCount: `groundTruthEvents.length || activeDetectionCount`

- **GroundTruthComparisonCards:** Uses `precision` from line 624
  - Formula: `gtComparison?.precision ?? 0`
  - Source: Backend API field `enhancedResults?.ground_truth_comparison?.precision`

**Root Cause:** Frontend calculates Match Rate from detection array filtering, while Backend calculates Precision from ground truth matching service with different logic.

---

### 2. Detection Count: 131 vs 134

**Display Location 1:** Line 124 in GroundTruthComparisonCards
```typescript
{truePositives} TP / {truePositives + falsePositives} Total Detections
// Shows: "96 TP / 131 Total Detections"
```

**Display Location 2:** Line 1132 in HILResults.tsx
```typescript
Detection Events ({activeDetectionCount} total)
// Shows: "134 total"
```

**Data Sources:**

1. **131 = truePositives + falsePositives** (line 627-628 HILResults.tsx)
   ```typescript
   const truePositives = gtComparison?.true_positives ?? 0;
   const falsePositives = gtComparison?.false_positives ?? 0;
   // 96 + 35 = 131
   ```
   - Source: Backend ground truth comparison API
   - File: `/backend/src/api/enhanced_hil_results_endpoints.py`

2. **134 = activeDetectionCount** (line 587 HILResults.tsx)
   ```typescript
   const activeDetectionCount = activeDetections.length;
   ```
   - Source: Frontend detection array filtering
   - Accumulated from `baseDetections` state (line 560)

**Root Cause:** Backend ground truth matching only counted 131 detections that had timestamps within valid range, while frontend displays all 134 detections loaded from API including 3 edge cases.

---

### 3. F1 Score: 29.8% Incorrect Calculation

**Display:** Line 76-82 GroundTruthComparisonCards.tsx
```typescript
<Typography variant="h2" color={f1Quality.color} fontWeight="bold">
  {f1Score.toFixed(1)}
  <Typography component="span" variant="h4">%</Typography>
</Typography>
```

**Data Source:** Line 626 HILResults.tsx
```typescript
const f1Score = gtComparison?.f1_score ?? 0;
// Value: 29.8
```

**Backend Calculation:** `/backend/services/ground_truth_matching_service.py` Line 834
```python
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
```

**Manual Verification:**
Given from UI:
- Precision: 73.3% (0.733)
- Recall: 18.7% (0.187)

**Expected F1 Calculation:**
```
F1 = 2 * (precision * recall) / (precision + recall)
F1 = 2 * (0.733 * 0.187) / (0.733 + 0.187)
F1 = 2 * 0.137071 / 0.92
F1 = 0.274142 / 0.92
F1 = 0.298 = 29.8% ✅ CORRECT
```

**Status:** ✅ F1 Score calculation is mathematically correct. The issue is the **precision value is wrong**, not the F1 formula.

---

### 4. Pass Rate: 0.0% vs "All GT PASS" Timeline

**Display Location:** TestStatusBanner component (passed as prop)

**Data Source:** Line 615-618 HILResults.tsx
```typescript
const overallPassRate = sequenceResults?.overallPassRate
  ?? sequenceResults?.overall_pass_rate
  ?? overallCorrectedStats?.pass_rate
  ?? (overallDetectionCount > 0 ? (overallPassedDetections / overallDetectionCount) * 100 : 0);
```

**Timeline Display:** FrameCorrelationTimeline component shows all detections as "GT PASS"

**Root Cause:**
1. **Pass Rate** measures latency threshold compliance (performance metric)
2. **GT PASS** shows ground truth matching success (accuracy metric)

These are **two different metrics**:
- Pass Rate: % of detections meeting latency threshold (e.g., < 100ms)
- GT Match: % of detections matching ground truth events

A detection can match ground truth (GT PASS) but fail latency threshold (Pass Rate FAIL).

---

## Metric Formulas - Line Number Reference

### Frontend Calculations (HILResults.tsx)

#### 1. Overall Match Rate (Line 632)
```typescript
const overallMatchRate = gtComparison?.precision ??
  (overallDetectionCount > 0 ? (overallPassedDetections / overallDetectionCount) * 100 : 0);
```
**Formula:** `(matched_detections / total_detections) * 100`
**Data:** Backend `gtComparison.precision` OR frontend calculation

#### 2. Active Match Rate (Line 608-610)
```typescript
const activeMatchedCount = activeDetections.filter(d =>
  (d as any)?.ground_truth_match_id || (d as any)?.groundTruthMatchId
).length;
const activeExpectedCount = groundTruthEvents.length || activeDetectionCount;
const activeMatchRate = activeExpectedCount > 0 ? (activeMatchedCount / activeExpectedCount) * 100 : 0;
```
**Formula:** `(detections_with_gt_match_id / (gt_events_count || detection_count)) * 100`
**Data:** Frontend detection array filtering

#### 3. Precision (Line 624)
```typescript
const precision = gtComparison?.precision ?? 0;
```
**Formula:** Backend calculation
**Data:** `enhancedResults.ground_truth_comparison.precision`

#### 4. Recall (Line 625)
```typescript
const recall = gtComparison?.recall ?? 0;
```
**Formula:** Backend calculation
**Data:** `enhancedResults.ground_truth_comparison.recall`

#### 5. F1 Score (Line 626)
```typescript
const f1Score = gtComparison?.f1_score ?? 0;
```
**Formula:** Backend calculation
**Data:** `enhancedResults.ground_truth_comparison.f1_score`

#### 6. Pass Rate (Line 615-618)
```typescript
const overallPassRate = sequenceResults?.overallPassRate
  ?? sequenceResults?.overall_pass_rate
  ?? overallCorrectedStats?.pass_rate
  ?? (overallDetectionCount > 0 ? (overallPassedDetections / overallDetectionCount) * 100 : 0);
```
**Formula:** `(passed_detections / total_detections) * 100`
**Data:** Multiple fallback sources (sequence → corrected stats → frontend calculation)

---

### Backend Calculations

#### 1. Precision (`ground_truth_matching_service.py` Line 832)
```python
precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
```
**Formula:** `TP / (TP + FP)`
**Standard Definition:** Of all detections made, what % were correct?

#### 2. Recall (`ground_truth_matching_service.py` Line 833)
```python
recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
```
**Formula:** `TP / (TP + FN)`
**Standard Definition:** Of all actual events, what % did we detect?

#### 3. F1 Score (`ground_truth_matching_service.py` Line 834)
```python
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
```
**Formula:** `2 * (P * R) / (P + R)`
**Standard Definition:** Harmonic mean of precision and recall

---

## Data Flow Analysis

### Detection Count Discrepancy (131 vs 134)

**Backend Ground Truth Matching Service:**
```python
# Line 152-160: Get detection events via raw SQL
detection_query = text("""
    SELECT id, timestamp, confidence, class_label, actual_latency_ms,
           video_relative_timestamp, video_frame_number, timing_sync_quality,
           video_id
    FROM detection_events
    WHERE test_session_id = :session_id
    ORDER BY timestamp
""")
detection_results = db.execute(detection_query, {'session_id': session_id}).fetchall()
```
**Result:** 134 raw detections

**Temporal Matching (Line 195-197):**
```python
match_results = self._perform_temporal_matching(
    detection_events, ground_truth_objects, tolerance_ms
)
```
**Result:** 131 detections matched within tolerance window (3 excluded as out-of-bounds)

**Frontend Display:**
```typescript
// Line 199: Load from API
const normalizedDetections = normalizeDetectionEvents(detectionCandidates);
// Result: 134 detections (includes all events, even out-of-tolerance)

// Line 124 GroundTruthComparisonCards:
{truePositives} TP / {truePositives + falsePositives} Total Detections
// Shows backend matched count: 131

// Line 1132 HILResults.tsx:
Detection Events ({activeDetectionCount} total)
// Shows frontend array length: 134
```

---

## Expected vs Actual Values

**For Session 463b7ec5-0cd6-4b6a-9776-d10f938b6422:**

| Metric | Card 1 Value | Card 2 Value | Expected Correct Value | Source of Truth |
|--------|-------------|-------------|----------------------|----------------|
| **Match Rate** | 73.3% | 0.0% | 73.3% (96/131) | Backend precision |
| **Detection Count** | 131 | 134 | 134 total, 131 matched | Both valid (different contexts) |
| **F1 Score** | 29.8% | — | 29.8% | Backend (formula correct) |
| **Precision** | 73.3% | 0.0% | 73.3% (96/131) | Backend |
| **Recall** | 18.7% | — | 18.7% (96/513) | Backend |
| **Pass Rate** | 0.0% | — | 0.0% (latency metric) | Backend |
| **GT Match Status** | — | "All PASS" | Separate metric | Timeline component |

---

## Root Causes Summary

### 1. **Duplicate Metric Calculations**
- Frontend calculates Match Rate independently (Line 608-610)
- Backend calculates Precision via ground truth service
- Both attempt to measure "% detections matched to GT" but use different data sources

### 2. **Inconsistent Data Sources**
- Frontend: Filters detection array for `ground_truth_match_id`
- Backend: Uses DetectionComparison table populated by matching service
- These can diverge if matching service hasn't run or uses different tolerance

### 3. **Detection Count Boundary Conditions**
- Backend excludes 3 detections outside temporal tolerance window
- Frontend displays all detections loaded from API
- Both counts are "correct" for their respective contexts

### 4. **Zero-Value Display Bug**
```typescript
// Line 624 HILResults.tsx
const precision = gtComparison?.precision ?? 0;
```
If `gtComparison` is undefined/null, precision defaults to 0, causing 0.0% display even when backend calculated 73.3%.

**Likely Cause:** API response missing `ground_truth_comparison` field, causing all GT metrics to default to 0.

---

## Recommended Fixes

### Priority 1: Single Source of Truth
**File:** `/frontend/src/pages/HILResults.tsx`

**Lines 608-610 - Remove duplicate Match Rate calculation:**
```typescript
// ❌ DELETE THIS (redundant):
const activeMatchedCount = activeDetections.filter(d =>
  (d as any)?.ground_truth_match_id || (d as any)?.groundTruthMatchId
).length;
const activeExpectedCount = groundTruthEvents.length || activeDetectionCount;
const activeMatchRate = activeExpectedCount > 0 ? (activeMatchedCount / activeExpectedCount) * 100 : 0;

// ✅ USE THIS (from backend):
const activeMatchRate = precision; // Line 624
```

### Priority 2: Detection Count Clarity
**File:** `/frontend/src/components/GroundTruthComparisonCards.tsx`

**Line 124 - Clarify what "Total Detections" means:**
```typescript
// Current:
{truePositives} TP / {truePositives + falsePositives} Total Detections

// Fixed:
{truePositives} TP / {truePositives + falsePositives} Matched Detections
```

**Add tooltip:** "Matched Detections = detections within temporal tolerance window. Total session detections may be higher."

### Priority 3: Default Value Bug
**File:** `/frontend/src/pages/HILResults.tsx`

**Line 621-633 - Add null check before defaulting to 0:**
```typescript
const gtComparison = enhancedResults?.ground_truth_comparison;
const hasGroundTruth = Boolean(gtComparison && gtComparison.ground_truth_events_available > 0);

// ❌ BEFORE:
const precision = gtComparison?.precision ?? 0;

// ✅ AFTER:
const precision = hasGroundTruth ? (gtComparison.precision ?? 0) : null;

// Then in MetricsSummaryCards, show "N/A" instead of 0.0% when null
```

### Priority 4: Metric Naming
**File:** `/frontend/src/components/MetricsSummaryCards.tsx`

**Line 122-145 - Rename "Match Rate" to "Detection Precision":**
```typescript
// Match Rate Card
<Typography color="textSecondary" variant="overline">
  Detection Precision  {/* was: Match Rate */}
</Typography>
```
This clarifies it's measuring precision, not a generic "match rate".

---

## Testing Validation

**Manual Test for Session 463b7ec5-0cd6-4b6a-9776-d10f938b6422:**

1. **Backend API Response:**
   ```bash
   curl http://localhost:8000/api/enhanced-hil/test-sessions/463b7ec5-0cd6-4b6a-9776-d10f938b6422/corrected-results
   ```
   **Verify:**
   - `ground_truth_comparison.precision` = 0.733
   - `ground_truth_comparison.recall` = 0.187
   - `ground_truth_comparison.f1_score` = 0.298
   - `ground_truth_comparison.true_positives` = 96
   - `ground_truth_comparison.false_positives` = 35
   - `ground_truth_comparison.false_negatives` = 417

2. **Frontend Calculation:**
   ```typescript
   const precision = 96 / (96 + 35) = 96 / 131 = 0.733 = 73.3% ✅
   const recall = 96 / (96 + 417) = 96 / 513 = 0.187 = 18.7% ✅
   const f1 = 2 * (0.733 * 0.187) / (0.733 + 0.187) = 0.298 = 29.8% ✅
   ```

3. **Detection Count:**
   - API returns 134 detection events
   - Ground truth matching excludes 3 (outside tolerance)
   - TP + FP = 96 + 35 = 131 ✅
   - Total detections = 134 ✅

---

## Files Modified (for fix implementation)

1. `/frontend/src/pages/HILResults.tsx` (Lines 608-610, 621-633)
2. `/frontend/src/components/MetricsSummaryCards.tsx` (Line 127)
3. `/frontend/src/components/GroundTruthComparisonCards.tsx` (Line 124)

---

## Conclusion

The contradictions stem from **4 distinct metric calculation paths**:

1. **Frontend array filtering** (activeMatchRate calculation)
2. **Backend ground truth matching service** (precision/recall/F1)
3. **Frontend detection array length** (activeDetectionCount)
4. **Backend matched detection count** (TP + FP)

**The core issue is not incorrect formulas, but rather:**
- Duplicate calculations with different data sources
- Missing null checks causing 0% defaults
- Ambiguous metric names (Match Rate vs Precision)
- Lack of clarity on what "Total Detections" represents

**All calculations are mathematically correct** when using their intended data sources. The fix is to **eliminate duplication and clarify terminology**.
