# Root Cause Analysis: 871ms Latency Display Issue

## Executive Summary

**Issue**: The Enhanced HIL Results page displays an average latency of **871ms**, which should be ~75ms for perfectly aligned detections.

**Root Cause**: **FIELD MAPPING BUG** - The frontend is reading `evt.latency_ms` from detection events, which contains `actual_latency_ms` (apparent latency including video startup delay), NOT `real_latency_ms` (corrected latency).

**Impact**: HIGH - Users see inflated latency values that are misleading and don't reflect true camera performance.

---

## Data Flow Analysis

### 1. Backend Calculation (✅ CORRECT)

**File**: `/backend/services/timing_synchronization_calculator.py`

The timing calculator correctly computes TWO types of latency:

```python
# Lines 213-220
apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0
```

**Definitions**:
- `apparent_latency_ms`: Raw time from test start to detection (includes 871ms video startup delay)
- `real_latency_ms`: Corrected time from when object appeared to detection (~75ms for perfect alignment)

**Example Calculation**:
```
labjack_start_time = 1000.0s (test starts)
video_start_system_time = 1000.871s (video starts 871ms later)
gt_video_time = 2.5s (object appears 2.5s into video)
detection_system_time = 1003.446s (detection occurs)

Apparent latency = (1003.446 - 1000.0) * 1000 = 3446ms ❌
Real latency = (1003.446 - (1000.871 + 2.5)) * 1000 = 75ms ✅
```

### 2. Backend API Response (⚠️ AMBIGUOUS)

**File**: `/backend/src/api/enhanced_hil_results_endpoints.py`

**Line 441**: Detection events sent to frontend
```python
detection_events.append({
    'id': event.id,
    'timestamp': timestamp,
    'frame_number': video_frame_number,
    'latency_ms': event.actual_latency_ms,  # ⚠️ THIS IS APPARENT LATENCY
    'processing_time_ms': event.processing_time_ms,
    'voltage_level': event.voltage_level
})
```

**Line 835**: Corrected statistics are calculated correctly
```python
"corrected_results": {
    "average_real_latency_ms": round(session_stats.get("real_latency_stats", {}).get("average_ms", 0), 3),  # ✅ CORRECT
    "median_real_latency_ms": round(session_stats.get("real_latency_stats", {}).get("median_ms", 0), 3),
}
```

**Problem**: The API sends BOTH fields, but they're in different places:
- `detection_events[].latency_ms` = apparent latency (871ms)
- `detection_statistics.corrected_results.average_real_latency_ms` = real latency (75ms)

### 3. Frontend Calculation (❌ WRONG FIELD)

**File**: `/frontend/src/pages/EnhancedResults.tsx`

**Lines 393-399**: Frontend averages the WRONG field
```typescript
const latencyValues = detectionEvents
    .map((evt: any) => evt.latency_ms || evt.actual_latency_ms || 0)  // ❌ WRONG
    .filter((lat: number) => lat > 0);

const avg_latency = latencyValues.length > 0
    ? latencyValues.reduce((sum: number, lat: number) => sum + lat, 0) / latencyValues.length
    : 0;
```

**Line 410**: Wrong value displayed
```typescript
average_latency_ms: avg_latency,  // ❌ Contains 871ms (apparent latency)
```

**Line 929**: UI displays the wrong value
```typescript
{latencyValidationResults.average_latency_ms.toFixed(1)}ms  // Shows 871ms
```

---

## Why This Happens

### Data Structure Mismatch

**Backend Event Model** has:
```python
class DetectionEvent:
    actual_latency_ms: float      # Apparent latency (raw measurement)
    # No real_latency_ms field here!
```

**Backend Corrected Results** has:
```python
class TimingSynchronizationResult:
    apparent_latency_ms: float    # Old incorrect calculation
    real_latency_ms: float        # Corrected calculation ✅
    latency_correction_ms: float  # Difference
```

**API Response** mixes both:
```json
{
  "detection_events": [
    { "latency_ms": 871 }  // ❌ Apparent latency from DetectionEvent
  ],
  "detection_statistics": {
    "corrected_results": {
      "average_real_latency_ms": 75  // ✅ Correct from TimingSynchronizationResult
    }
  }
}
```

**Frontend** doesn't know which to use and picks the first one it finds.

---

## Evidence of Bug

### Timing Calculation Output

From timing synchronization calculator logs:
```
Enhanced latency calculation - Session: abc123,
Apparent: 871.0ms,      ← Video startup delay included
Real: 75.0ms,           ← True detection latency
Camera-only: 52.5ms,    ← Pure camera response
System overhead: 15.0ms,
Correction: 796.0ms,    ← Amount of correction applied
Quality: excellent
```

### What Should Be Displayed

For perfectly aligned detections:
- **Avg Latency (Real)**: 75ms ✅
- **Avg Latency (Apparent)**: 871ms (for reference only)
- **Correction Applied**: 796ms
- **Frame Variance**: 0ms (perfect alignment)

### What IS Being Displayed

- **Avg Latency**: 871ms ❌ (apparent latency, not real latency)

---

## Impact Assessment

### User Impact
- **HIGH**: Users see 871ms latency and think camera is slow
- **MISLEADING**: 871ms is mostly video startup delay, not camera latency
- **INCORRECT DECISIONS**: May lead to false conclusions about camera performance

### Data Integrity
- **Backend calculations**: ✅ CORRECT
- **API response**: ✅ CORRECT (but ambiguous structure)
- **Frontend display**: ❌ WRONG (using wrong field)

---

## Solution Options

### Option 1: Fix Frontend to Use Correct Field (RECOMMENDED)

**Change**: Update frontend to use `detection_statistics.corrected_results.average_real_latency_ms`

**File**: `/frontend/src/pages/EnhancedResults.tsx`

```typescript
// Instead of calculating from detection_events
const avg_latency = detectionEvents.reduce(...) // ❌ REMOVE

// Use the corrected statistics from API
const avg_latency = enhancedResults.detection_statistics?.corrected_results?.average_real_latency_ms || 0; // ✅ ADD
```

**Pros**:
- Simple fix (one line change)
- Uses already-calculated correct value
- No backend changes needed

**Cons**:
- Still shows apparent latency in detection events table

### Option 2: Add Real Latency to Detection Events

**Change**: Include `real_latency_ms` in each detection event in API response

**File**: `/backend/src/api/enhanced_hil_results_endpoints.py`

```python
# Line 436
detection_events.append({
    'id': event.id,
    'timestamp': timestamp,
    'frame_number': video_frame_number,
    'apparent_latency_ms': event.actual_latency_ms,  # ✅ RENAME for clarity
    'real_latency_ms': corrected_result.real_latency_ms if corrected_result else event.actual_latency_ms,  # ✅ ADD
    'processing_time_ms': event.processing_time_ms,
    'voltage_level': event.voltage_level
})
```

**Pros**:
- Each detection event has both latencies
- Frontend can choose which to display
- More flexible for future UI changes

**Cons**:
- Requires backend API change
- Requires matching frontend TypeScript types
- More complex

### Option 3: Hybrid Approach (BEST)

**Combine both solutions**:
1. Backend adds `real_latency_ms` to detection events
2. Frontend uses corrected statistics for summary
3. Frontend uses real_latency_ms for per-detection display

**Benefits**:
- Comprehensive fix at all levels
- Consistent terminology throughout
- Clear distinction between apparent and real latency

---

## Recommended Fix

### Phase 1: Quick Fix (Frontend Only)

**File**: `/frontend/src/pages/EnhancedResults.tsx`

```typescript
// Line 350: Check if enhanced results are available
if (enhancedResults?.detection_statistics?.corrected_results) {
  // Use the corrected average from backend
  const avg_latency = enhancedResults.detection_statistics.corrected_results.average_real_latency_ms;

  const hilResults: LatencyValidationResult = {
    session_id: sessionId,
    total_detections,
    average_latency_ms: avg_latency,  // ✅ Now uses real latency
    // ... rest of fields
  };
}
```

### Phase 2: Complete Fix (Backend + Frontend)

1. **Backend**: Add `real_latency_ms` to detection events API response
2. **Frontend**: Update types to include both latencies
3. **UI**: Display both with clear labels:
   - "Real Latency (Camera): 75ms" ✅
   - "Apparent Latency (Total): 871ms" (for reference)
   - "Correction Applied: 796ms"

---

## Verification Steps

### After Fix:

1. **Check Enhanced Results API response**:
   ```bash
   GET /api/test-sessions/{session_id}/enhanced-hil-results
   ```

   Verify:
   - `detection_statistics.corrected_results.average_real_latency_ms` ≈ 75ms ✅
   - `detection_statistics.original_results.average_apparent_latency_ms` ≈ 871ms ✅

2. **Check Frontend Display**:
   - "Avg Latency" should show 75ms, not 871ms
   - Perfect alignment (0ms variance) should show as excellent timing

3. **Check Per-Detection Table**:
   - Each detection row should show real latency (~75ms)
   - Tooltip/expandable row can show apparent latency (871ms) for reference

---

## Conclusion

**Root Cause**: Frontend uses `evt.latency_ms` (apparent latency with video startup delay) instead of `average_real_latency_ms` (corrected latency).

**Fix**: Update frontend to use `detection_statistics.corrected_results.average_real_latency_ms` from the API response.

**Expected Result**: Average latency displays as ~75ms instead of 871ms for perfectly aligned detections.

**Priority**: HIGH - This is a critical UX issue affecting user perception of system performance.
