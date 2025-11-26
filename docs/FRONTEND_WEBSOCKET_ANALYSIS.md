# Frontend WebSocket Detection Reception Failure Analysis

**Investigation Date**: 2025-11-14
**File Analyzed**: `/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx`
**Status**: 🔴 CRITICAL ISSUES IDENTIFIED

---

## Executive Summary

The frontend WebSocket implementation has **MULTIPLE CRITICAL ISSUES** preventing detection events from being received and displayed. The code shows evidence of being triggered (console logs appear), but events are **NOT reaching the UI state**.

### Key Findings:

1. ✅ **WebSocket initialization is correct** (line 1269-1270)
2. ✅ **Message handler is properly bound** (line 1274-1335)
3. ❌ **CRITICAL: Polling fallback doesn't wait for WebSocket failure** (line 1342-1347)
4. ❌ **CRITICAL: Race condition in testRunning state** (line 1499)
5. ❌ **WARNING: No cleanup/unmount handling** (missing useEffect cleanup)
6. ⚠️ **SUSPICIOUS: Early polling exit conditions may skip events** (line 1499)

---

## Detailed Analysis

### 1. WebSocket Connection Setup (Lines 1267-1270)

**Code:**
```typescript
const base = (process.env.REACT_APP_API_URL || 'http://localhost:8000').replace(/^http/, 'ws');
const wsUrl = `${base}/ws/test-sessions/${session.id}/detections`;
console.log('🔌 [HIL] Attempting WebSocket connection:', wsUrl);
wsRef.current = new WebSocket(wsUrl);
```

**Assessment:** ✅ **CORRECT**
- Properly constructs WebSocket URL
- Uses session ID correctly
- Stores reference in useRef

---

### 2. WebSocket Message Handler (Lines 1274-1335)

**Code:**
```typescript
wsRef.current.onmessage = (evt) => {
  try {
    const payload = JSON.parse(evt.data);
    const items = Array.isArray(payload) ? payload : (payload?.detections ? payload.detections : [payload]);
    items.forEach((d: any, idx: number) => {
      // Processing logic...
      setDetectionEvents(prev => [...prev, event]);
    });
  } catch (e) {
    console.warn('⚠️ [HIL] WS parse error:', (e as Error)?.message);
  }
};
```

**Assessment:** ✅ **PROPERLY BOUND**
- Handler is correctly attached to WebSocket instance
- Uses functional state update (`prev => [...prev, event]`)
- Error handling is present

**Potential Issues:**
- ⚠️ **Multiple early returns** may skip valid events:
  - Missing `timestamp_ms` (line 1281-1284)
  - Missing `sequenceStartTimeRef` (line 1287-1291)
  - No ground truth (line 1300-1302)

---

### 3. **CRITICAL ISSUE #1**: Dual Execution (WebSocket + Polling)

**Code (Lines 1342-1347):**
```typescript
// If WS doesn't open quickly, fallback to polling
setTimeout(() => {
  if (!wsRef.current || wsRef.current.readyState !== 1) {
    console.log('ℹ️ [HIL] WS not open yet; starting polling');
    startSignalPolling(session);
  }
}, 1500);
```

**Problem:** 🔴 **RACE CONDITION**

This creates a **1.5 second race window** where:
1. WebSocket may be connecting but not yet open
2. Polling starts SIMULTANEOUSLY with WebSocket
3. **BOTH systems receive the SAME events**
4. Events may be processed TWICE or skipped due to deduplication

**Evidence from logs:**
```
✅ WebSocket initialized
ℹ️ WS not open yet; starting polling
📊 Final Results: Detected: 0
```

This shows:
- WebSocket was created
- Polling started before WebSocket opened
- **NO events were counted**

**Root Cause:**
The `setTimeout` fires regardless of whether WebSocket will eventually connect. If WebSocket is slow (but valid), polling starts anyway and may interfere with WebSocket reception.

---

### 4. **CRITICAL ISSUE #2**: Polling Guard Condition

**Code (Line 1498-1499):**
```typescript
pollingIntervalRef.current = setInterval(async () => {
  if (!testRunning || !session) return;  // ⚠️ EARLY EXIT
  pollCount++;
  try {
    const detections = await apiService.getTestSessionDetections(session.id);
    // Process detections...
```

**Problem:** 🔴 **STATE STALENESS**

The `testRunning` check uses **captured state** from when `startSignalPolling` was called. React state closures mean:

1. `testRunning` is captured as `true` when interval is created
2. If component re-renders and `testRunning` changes, **interval still sees old value**
3. Interval may exit early even though test is running

**Fix Required:**
Use a `useRef` for `testRunning` instead of state, or restructure the interval to check current state.

---

### 5. **CRITICAL ISSUE #3**: Missing Cleanup on Unmount

**Code Analysis:**
```typescript
// ❌ NO useEffect cleanup found in codebase
// WebSocket and polling interval are NOT cleaned up on unmount
```

**Problem:** 🔴 **MEMORY LEAK + STALE UPDATES**

When component unmounts or test stops:
1. WebSocket stays open and continues receiving messages
2. Polling interval continues running
3. `setDetectionEvents` calls on unmounted component → **React warning**
4. Memory leaks accumulate

**Evidence:**
The logs show "WS not open yet; starting polling" but no corresponding cleanup logs. This suggests:
- WebSocket may be open in background
- Events are being received but NOT processed
- State updates fail silently

---

### 6. Polling Implementation (Lines 1485-1578)

**Code:**
```typescript
const startSignalPolling = (session: HILTestSession) => {
  console.log('🚀 [HIL] Starting backend signal monitoring...');

  if (pollingIntervalRef.current) {
    clearInterval(pollingIntervalRef.current);
  }

  const processedIds = new Set<string>();
  let pollCount = 0;

  pollingIntervalRef.current = setInterval(async () => {
    if (!testRunning || !session) return;  // ⚠️ STALE CLOSURE
    pollCount++;
    try {
      const detections = await apiService.getTestSessionDetections(session.id);
      // Process detections...
```

**Assessment:** ⚠️ **PARTIAL IMPLEMENTATION**

Good parts:
- Clears existing interval before starting new one
- Uses deduplication (`processedIds` Set)
- Has error handling

Problems:
- **Stale closure on `testRunning`**
- No cleanup when test stops
- May run indefinitely if test crashes

---

### 7. Detection State Management (Lines 1786-1812)

**Code:**
```typescript
const actualDetections = detectionEvents.length;
const passedDetections = detectionEvents.filter(e => e.outcome === 'pass').length;
const failedDetections = detectionEvents.filter(e => e.outcome === 'fail_high_latency').length;

console.log('📊 [HIL] Final Test Results:');
console.log(`  Total Expected: ${totalExpectedDetections}`);
console.log(`  Detected: ${actualDetections}`);
```

**Assessment:** ✅ **CORRECT CALCULATION**

The results calculation is correct. The issue is that `detectionEvents` array is **EMPTY** because events never reach `setDetectionEvents`.

---

## Root Cause Summary

### Why Events Aren't Being Received:

1. **Dual Execution Conflict**: WebSocket and polling start simultaneously, causing:
   - Race conditions in event processing
   - Potential deduplication conflicts
   - Unclear which system is "active"

2. **Stale State in Polling**: The `testRunning` check in polling interval uses captured state, causing:
   - Early exits even when test is running
   - Intervals that don't actually poll

3. **No Cleanup Logic**: Missing useEffect cleanup means:
   - WebSocket stays open after unmount
   - Polling continues after test stops
   - State updates fail on unmounted component

4. **Silent Failures**: The combination of early returns in message handlers means:
   - Events may be received but silently discarded
   - No error logs for skipped events
   - "0 detections" appears even if backend is sending data

---

## Recommended Fixes

### Fix #1: Add Proper useEffect Cleanup

```typescript
useEffect(() => {
  return () => {
    // Cleanup WebSocket
    if (wsRef.current) {
      console.log('🧹 [HIL] Cleaning up WebSocket on unmount');
      wsRef.current.close();
      wsRef.current = null;
    }

    // Cleanup polling
    if (pollingIntervalRef.current) {
      console.log('🧹 [HIL] Cleaning up polling on unmount');
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };
}, []);
```

### Fix #2: Use Ref for testRunning in Polling

```typescript
const testRunningRef = useRef(false);

// Update ref whenever state changes
useEffect(() => {
  testRunningRef.current = testRunning;
}, [testRunning]);

// Use ref in polling
pollingIntervalRef.current = setInterval(async () => {
  if (!testRunningRef.current || !session) return;  // ✅ Uses current value
  // ...
```

### Fix #3: Sequential Fallback Instead of Parallel

```typescript
// Try WebSocket first
try {
  wsRef.current = new WebSocket(wsUrl);

  wsRef.current.onopen = () => {
    console.log('✅ [HIL] WebSocket connected - polling NOT needed');
    // Don't start polling if WebSocket succeeds
  };

  wsRef.current.onerror = () => {
    console.warn('⚠️ [HIL] WebSocket error; falling back to polling');
    wsRef.current?.close();
    startSignalPolling(session);
  };

  // Only start polling if WebSocket doesn't open in time
  setTimeout(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.log('⏱️ [HIL] WebSocket timeout; starting polling');
      wsRef.current?.close();
      wsRef.current = null;
      startSignalPolling(session);
    }
  }, 3000);  // Increased from 1500ms
} catch (e) {
  console.warn('⚠️ [HIL] WebSocket setup failed; starting polling:', e);
  startSignalPolling(session);
}
```

### Fix #4: Add Logging for Skipped Events

```typescript
wsRef.current.onmessage = (evt) => {
  try {
    const payload = JSON.parse(evt.data);
    const items = Array.isArray(payload) ? payload : [payload];

    console.log(`📨 [HIL WebSocket] Received ${items.length} events`);

    items.forEach((d: any, idx: number) => {
      // Check 1: Timestamp
      const tsMs = d.timestamp_ms ?? (typeof d.timestamp === 'number' ? d.timestamp * 1000 : null);
      if (tsMs === null) {
        console.warn('⚠️ [HIL WebSocket] Skipped event: missing timestamp', d);
        return;
      }

      // Check 2: Sequence start time
      const sequenceStart = sequenceStartTimeRef.current || currentSession?.testStartTime?.getTime();
      if (!sequenceStart) {
        console.warn('⚠️ [HIL WebSocket] Skipped event: no sequence start time');
        return;
      }

      // Check 3: Ground truth
      const activeVideoId = currentVideoId || validatedVideos[0]?.id || '';
      const videoGroundTruth = allVideoExpectedDetections.get(activeVideoId) || [];
      if (videoGroundTruth.length === 0) {
        console.warn(`⚠️ [HIL WebSocket] Skipped event: no ground truth for video ${activeVideoId}`);
        return;
      }

      console.log(`✅ [HIL WebSocket] Processing valid event ${idx + 1}/${items.length}`);

      // Process event...
      setDetectionEvents(prev => {
        const newEvents = [...prev, event];
        console.log(`📊 [HIL WebSocket] Total detections now: ${newEvents.length}`);
        return newEvents;
      });
    });
  } catch (e) {
    console.error('❌ [HIL] WS parse error:', e);
  }
};
```

### Fix #5: Polling Interval Cleanup on Test Stop

```typescript
const stopTest = async () => {
  console.log('⏹️ [HIL] Stopping test...');

  setTestRunning(false);
  testRunningRef.current = false;  // Update ref immediately

  // Stop WebSocket
  if (wsRef.current) {
    wsRef.current.close();
    wsRef.current = null;
  }

  // Stop polling
  if (pollingIntervalRef.current) {
    clearInterval(pollingIntervalRef.current);
    pollingIntervalRef.current = null;
    console.log('✅ [HIL] Polling stopped');
  }

  // Rest of stop logic...
};
```

---

## Testing Recommendations

### Test Case 1: WebSocket Success
1. Start test with working WebSocket
2. Verify "✅ WebSocket connected" appears
3. Verify "ℹ️ WS not open yet" does NOT appear
4. Verify detections are received via WebSocket
5. Verify polling is NOT started

### Test Case 2: WebSocket Failure
1. Block WebSocket port or simulate network error
2. Verify "⚠️ WebSocket error" appears
3. Verify polling starts as fallback
4. Verify detections are received via polling

### Test Case 3: Slow WebSocket
1. Add artificial delay to WebSocket connection
2. Verify timeout triggers (after 3 seconds)
3. Verify polling starts after timeout
4. Verify no duplicate events

### Test Case 4: Component Unmount During Test
1. Start test
2. Navigate away or unmount component
3. Verify cleanup logs appear
4. Verify no console errors about setState on unmounted component

### Test Case 5: Event Validation
1. Send events with missing timestamps
2. Verify events are logged as skipped
3. Verify error messages are clear
4. Verify valid events are still processed

---

## Priority Actions

1. **IMMEDIATE**: Add useEffect cleanup to prevent memory leaks
2. **IMMEDIATE**: Fix stale testRunning closure in polling
3. **HIGH**: Implement sequential fallback (WebSocket → Polling)
4. **HIGH**: Add comprehensive logging for skipped events
5. **MEDIUM**: Increase WebSocket timeout from 1.5s to 3s
6. **MEDIUM**: Add test status ref for real-time checks

---

## Files Affected

- `/ai-model-validation-platform/frontend/src/pages/HILTestExecutionPRD.tsx`

---

## Conclusion

The frontend WebSocket implementation is **partially functional** but has **critical race conditions and cleanup issues** that prevent events from being reliably received and displayed. The "0 detections" result is likely caused by:

1. **Both WebSocket and polling starting simultaneously** → confusion about which is active
2. **Stale state closures** → polling exits early
3. **No cleanup logic** → events processed on unmounted component
4. **Silent event filtering** → valid events discarded without logging

**All recommended fixes should be implemented together** to ensure reliable detection event reception.
