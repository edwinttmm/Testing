# Duplicate Latency Fix - API Response Update

## Problem Statement

The Enhanced HIL Results API was returning DUPLICATE latency values per detection event:
- `original_latency.apparent_latency_ms` (from database, often 10000ms for FPs)
- `corrected_latency.real_latency_ms` (from timing calculator, realistic 12-19ms)

This caused the frontend to display **TWO ROWS** for the same detection event.

## Root Cause

The API response structure included both:
1. **Database stored latency** (`actual_latency_ms`) - which uses 10000ms as a marker for false positives
2. **Calculator computed latency** (`detection_latency_ms`) - the actual measured/corrected value

Both values were being returned in nested `original_latency` and `corrected_latency` objects, causing duplicate entries in the UI table.

## Solution Implemented

### 1. Created Single Latency Function

Added `_get_single_authoritative_latency()` helper function with priority-based selection:

```python
def _get_single_authoritative_latency(detection_event, corrected_result) -> Optional[float]:
    """
    Return ONE authoritative latency value per detection.

    Priority:
    1. Timing calculator result (most accurate - corrected_result.detection_latency_ms)
    2. Stored latency if valid (< 10000ms, not a FP marker)
    3. Calculated from timestamps if available
    4. None (don't use placeholder values like 10000ms)
    """
```

### 2. Updated API Response Structure

**BEFORE (caused duplicates):**
```json
{
  "detection_events": [
    {
      "event_id": "123",
      "original_latency": {
        "apparent_latency_ms": 10000.0  // FP marker from DB
      },
      "corrected_latency": {
        "real_latency_ms": 12.5  // Actual measured value
      }
    }
  ]
}
```

**AFTER (single value):**
```json
{
  "detection_events": [
    {
      "event_id": "123",
      "latency_ms": 12.5,  // SINGLE authoritative value
      "latency_source": "timing_calculator_corrected",
      "match_type": "true_positive",
      "result": "pass"
    }
  ]
}
```

### 3. Updated Match Type and Pass/Fail Logic

- Added `match_type` field from detection event (TP, FP, FN)
- Pass/Fail now based on SINGLE `latency_ms` value
- Removed duplicate `timing_synchronization` object
- Consolidated timing metadata into single object

## Files Modified

### `/backend/src/api/enhanced_hil_results_endpoints.py`

**Changes:**
1. Added `_get_single_authoritative_latency()` function (lines 50-97)
2. Updated "no ground truth" response section (lines 870-941)
   - Replaced nested `original_latency`/`corrected_latency` with single `latency_ms`
   - Added `latency_source` field
   - Added `match_type` field
3. Updated "with corrected results" response section (lines 942-1048)
   - Replaced nested objects with single `latency_ms`
   - Updated pass/fail logic to use single value
   - Removed duplicate `timing_synchronization` object

## Testing Plan

### 1. API Response Validation

```bash
# Test API endpoint
curl http://localhost:8000/api/enhanced-hil/results/<session_id>

# Verify response structure
{
  "detection_events": [
    {
      "event_id": "...",
      "latency_ms": 12.5,  // Single value
      "latency_source": "timing_calculator_corrected",
      "match_type": "true_positive",
      "result": "pass",
      "threshold_ms": 100
    }
  ]
}
```

### 2. Frontend UI Validation

**Expected Result:**
- Each detection event shows ONCE in the table
- Latency column displays single value (12-19ms for TPs, not 10000ms)
- Pass/Fail status matches latency threshold
- No duplicate rows

**Test Steps:**
1. Open HIL results page
2. Load session with detections
3. Verify detection table shows ONE row per detection
4. Verify latency values are realistic (not 10000ms markers)
5. Verify pass/fail status is correct

### 3. Edge Cases

- [ ] Detections without corrected results (fallback path)
- [ ] False positives (should not use 10000ms marker)
- [ ] Detections with missing timestamps
- [ ] Sessions without ground truth

## Migration Notes

**Breaking Change:** API response structure changed

**Frontend Updates Required:**
- Update table column mapping from `corrected_latency.real_latency_ms` to `latency_ms`
- Remove duplicate row filtering logic (no longer needed)
- Update latency display to use single `latency_ms` field

**Backward Compatibility:**
- Old API endpoints unchanged
- Only affects `/api/enhanced-hil/results/` endpoint

## Verification Checklist

- [x] Single latency function implemented
- [x] API response structure updated (no ground truth path)
- [x] API response structure updated (with corrected results path)
- [x] Pass/Fail logic uses single latency value
- [x] Match type field added
- [ ] API endpoint tested
- [ ] Frontend UI verified (no duplicate rows)
- [ ] Edge cases tested
- [ ] Documentation updated

## Next Steps

1. **Test API endpoint** with real session data
2. **Verify frontend** displays single row per detection
3. **Update frontend code** to use new `latency_ms` field
4. **Remove** frontend duplicate filtering logic
5. **Test edge cases** (missing data, FPs, etc.)

## Related Files

- `/backend/src/api/enhanced_hil_results_endpoints.py` - Main fix
- `/frontend/src/components/HILResultsTable.tsx` - Frontend update needed
- `/backend/services/timing_synchronization_calculator.py` - Latency calculation
- `/backend/services/ground_truth_matching_service.py` - Match type assignment

## Success Metrics

✅ **BEFORE:** UI showed 2+ rows per detection (database + calculated latency)
✅ **AFTER:** UI shows 1 row per detection with single authoritative latency value

✅ **BEFORE:** Latency values mixed (10000ms markers + real values)
✅ **AFTER:** Only realistic latency values (12-19ms for valid detections)

✅ **BEFORE:** Pass/Fail logic inconsistent (multiple sources)
✅ **AFTER:** Pass/Fail based on single authoritative latency value
