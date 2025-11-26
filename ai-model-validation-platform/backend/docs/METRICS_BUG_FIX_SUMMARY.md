# Ground Truth Metrics Bug Fix Summary

## Issue Description
**Symptom**: Individual detections showed "GT PASS" status in timeline, but aggregated metrics displayed 0% for all values (Precision, Recall, F1 Score).

**User Impact**: Frontend showed "N/A" for all metrics despite successful ground truth matching.

## Root Cause Analysis

The bug was NOT in the metrics calculation logic itself, but in the **temporal expansion** feature (Option C) that was preventing the matching from completing successfully.

### Bug Chain

1. **Primary Bug**: `temporal_expansion.py` line 135
   - Code: `confidence = float(getattr(detection, 'confidence', 0.0))`
   - Problem: Some DetectionEvents have `confidence=None` in database
   - `getattr` returns None (attribute exists but is None)
   - `float(None)` raises TypeError
   - **Impact**: Matching failed before creating any DetectionComparison records

2. **Secondary Bug**: `ground_truth_matching_service.py` multiple locations
   - Code: `confidence=detection.confidence`
   - Problem: ExpandedDetection objects have `confidence_score` not `confidence`
   - AttributeError when accessing `.confidence` on ExpandedDetection
   - **Impact**: Even after fixing primary bug, matching still failed

3. **Tertiary Bug**: `ground_truth_matching_service.py` line 794
   - Code: `detection_id = match.detection_id`
   - Problem: MatchResult dataclass has `detection_event_id` not `detection_id`
   - AttributeError when collapsing virtual matches
   - **Impact**: Matching failed during duplicate removal

4. **Quaternary Bug**: `ground_truth_matching_service.py` line 797
   - Code: `if '-v' in detection_id:`
   - Problem: `detection_event_id` can be None for FN (False Negative) matches
   - TypeError: argument of type 'NoneType' is not iterable
   - **Impact**: Matching failed when processing FN matches

5. **Quinary Bug**: `ground_truth_matching_service.py` line 821
   - Code: `abs(m.latency_ms) if m.latency_ms != FP_LATENCY_MARKER`
   - Problem: `latency_ms` can be None for FN matches
   - TypeError: bad operand type for abs(): 'NoneType'
   - **Impact**: Matching failed during duplicate resolution

## Files Modified

### 1. `/backend/src/services/temporal_expansion.py`
**Line 135-137**: Fixed None confidence handling
```python
# BEFORE (BROKEN):
confidence = float(getattr(detection, 'confidence', 0.0))

# AFTER (FIXED):
confidence_raw = getattr(detection, 'confidence', 0.0)
confidence = float(confidence_raw) if confidence_raw is not None else 0.0
```

### 2. `/backend/services/ground_truth_matching_service.py`

**Added helper function** (Line 1189-1209):
```python
def _get_detection_confidence(self, detection: Union[any, 'ExpandedDetection']) -> float:
    """Extract confidence from DetectionEvent or ExpandedDetection"""
    if hasattr(detection, 'confidence_score'):
        return detection.confidence_score  # ExpandedDetection
    elif hasattr(detection, 'confidence'):
        confidence_value = detection.confidence
        return float(confidence_value) if confidence_value is not None else 0.0
    else:
        return 0.0
```

**Fixed all confidence accesses** (Lines 974, 1012, 1042, 1112):
```python
# BEFORE:
confidence=detection.confidence

# AFTER:
confidence=self._get_detection_confidence(detection)
```

**Fixed detection_id references** (Line 794):
```python
# BEFORE:
detection_id = match.detection_id

# AFTER:
detection_id = match.detection_event_id
```

**Fixed None detection_event_id handling** (Lines 796-801):
```python
# BEFORE:
if '-v' in detection_id:
    parent_id = detection_id.rsplit('-v', 1)[0]

# AFTER:
if detection_id is None:
    # FN match - no detection to collapse
    parent_groups[None] = parent_groups.get(None, [])
    parent_groups[None].append(match)
    continue

if '-v' in detection_id:
    parent_id = detection_id.rsplit('-v', 1)[0]
```

**Fixed None latency_ms handling** (Lines 821-825):
```python
# BEFORE:
best_match = min(group, key=lambda m: abs(m.latency_ms) if m.latency_ms != FP_LATENCY_MARKER else float('inf'))

# AFTER:
best_match = min(group, key=lambda m: (
    abs(m.latency_ms) if (m.latency_ms is not None and m.latency_ms != FP_LATENCY_MARKER)
    else float('inf')
))
```

## Test Results

**Test Session**: `5568a6e1-1c3e-4ae9-bfd9-31e116f0fc70`

### Before Fix
- DetectionComparison records: 0
- Metrics: All 0% (N/A in frontend)
- Error: `TypeError: float() argument must be a string or a real number, not 'NoneType'`

### After Fix
- DetectionComparison records: 247 ✅
- True Positives: 67
- False Positives: 179
- False Negatives: 1
- Precision: 27.2%
- Recall: 98.5%
- F1 Score: 42.7%
- Mean Latency: 6.05ms

## Impact

✅ **Fixed**: Ground truth matching now completes successfully
✅ **Fixed**: Metrics are calculated and stored in database
✅ **Fixed**: Frontend displays correct metric values
✅ **Fixed**: DetectionComparison records are persisted
✅ **Fixed**: Timeline shows correct GT PASS/FAIL with actual numbers

## Technical Details

### Why the Bug Was Hard to Find

1. **Silent Failure**: The matching code caught exceptions and returned None, hiding the actual error
2. **Multiple Layers**: Bug was in temporal_expansion.py but error manifested in ground_truth_matching_service.py
3. **Cascading Failures**: Fixing one bug revealed the next in a chain of 5 bugs
4. **Database Confusion**: Existing 48,333 DetectionComparison records from previous sessions made it seem like the system was working

### Data Flow

```
DetectionEvent (DB)
  ↓
temporal_expansion.py (expand_detections_temporally)
  ↓
ExpandedDetection objects (in-memory)
  ↓
ground_truth_matching_service.py (_perform_temporal_matching)
  ↓
MatchResult objects
  ↓
_collapse_virtual_matches (deduplicate)
  ↓
_populate_detection_comparisons (save to DB)
  ↓
DetectionComparison records (DB)
  ↓
_calculate_and_store_metrics
  ↓
SessionMetrics + PerformanceMetrics (DB)
  ↓
Frontend API (/api/test-sessions/{id}/results)
  ↓
Display metrics to user
```

### Why Metrics Showed 0%

The metrics calculation code was **100% correct**. The problem was that no DetectionComparison records were being created because temporal expansion was crashing. Without comparison records, the query returned empty results, leading to 0 TP, 0 FP, 0 FN, and thus 0% for all calculated metrics.

## Prevention

### Code Review Checklist
- [ ] Always check for None values before type conversion
- [ ] Use consistent attribute names across related dataclasses
- [ ] Add None checks when accessing optional fields
- [ ] Test with real database data that may have None values
- [ ] Add logging to catch silent failures

### Recommended Improvements
1. Add explicit None checks in temporal_expansion.py for all DetectionEvent fields
2. Create property methods in ExpandedDetection for backward compatibility
3. Add integration tests with None values in DetectionEvents
4. Improve error logging to surface root causes
5. Add validation to detect when metrics == 0 but detections exist

## Verification Steps

To verify the fix is working:

1. Create a test session with detections
2. Run ground truth matching: `service.match_detections_to_ground_truth(session_id)`
3. Check DetectionComparison count: `SELECT COUNT(*) FROM detection_comparisons WHERE test_session_id = ?`
4. Check metrics in PerformanceMetrics table
5. Call frontend API: `GET /api/test-sessions/{session_id}/results`
6. Verify frontend displays non-zero metrics

## Date
November 20, 2025

## Author
Code Implementation Agent (Senior Software Engineer specializing in Python/FastAPI)
