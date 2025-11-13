# 871ms Latency Display - Quick Fix Summary

## Problem
Enhanced HIL Results page shows **871ms average latency** instead of **~75ms**.

## Root Cause
**Frontend is reading the WRONG field from the API response.**

### What's Happening

1. **Backend correctly calculates**:
   - `apparent_latency_ms` = 871ms (includes video startup delay)
   - `real_latency_ms` = 75ms (corrected, true camera latency)

2. **API sends BOTH values**:
   - ✅ `detection_statistics.corrected_results.average_real_latency_ms` = 75ms
   - ❌ `detection_events[].latency_ms` = 871ms (apparent)

3. **Frontend uses the WRONG one**:
   ```typescript
   // Line 393-399 in EnhancedResults.tsx
   const latencyValues = detectionEvents
       .map((evt: any) => evt.latency_ms || evt.actual_latency_ms || 0)  // ❌ WRONG
   ```

   Should use:
   ```typescript
   const avg_latency = enhancedResults.detection_statistics?.corrected_results?.average_real_latency_ms || 0;  // ✅ CORRECT
   ```

## Quick Fix

**File**: `/frontend/src/pages/EnhancedResults.tsx`

**Location**: Around line 350-410

**Change**:
```typescript
// BEFORE (lines 393-399) - REMOVE THIS
const latencyValues = detectionEvents
    .map((evt: any) => evt.latency_ms || evt.actual_latency_ms || 0)
    .filter((lat: number) => lat > 0);

const avg_latency = latencyValues.length > 0
    ? latencyValues.reduce((sum: number, lat: number) => sum + lat, 0) / latencyValues.length
    : 0;

// AFTER - ADD THIS
const avg_latency = enhancedResults?.detection_statistics?.corrected_results?.average_real_latency_ms || 0;
```

## Expected Result

### Before Fix
- **Avg Latency**: 871ms ❌ (misleading - includes video startup delay)

### After Fix
- **Avg Latency**: 75ms ✅ (correct - true camera latency)
- **Frame Variance**: 0ms ✅ (perfect alignment)

## Verification

After applying the fix:

1. Navigate to Enhanced HIL Results page
2. Check "Avg Latency" metric
3. Should show ~75ms instead of 871ms
4. For perfect alignment (0ms variance), expect 50-100ms range

## Why This Matters

- **871ms** = Video startup delay + camera latency + processing time
- **75ms** = Camera latency + processing time only (what users care about)

The 871ms value is technically correct but misleading because it includes the ~796ms video startup delay, which has nothing to do with camera performance.

## Implementation Priority

**HIGH** - This is a critical UX bug that makes camera performance appear 10x worse than it actually is.

---

**Status**: Ready for implementation
**Estimated Time**: 5 minutes
**Risk**: Low (single line change, no backend changes needed)
