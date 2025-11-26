# Frontend Duplicate Detection Analysis Report

## Investigation Summary

**Date**: 2025-11-25
**Component**: Frontend Detection Event Fetching
**Issue**: Duplicate detection entries appearing in UI with different "real" latency values

---

## Key Findings

### 1. **CONFIRMED: Frontend IS Creating Duplicates**

The HILResults.tsx component is fetching detection events from **multiple sources** and combining them WITHOUT proper deduplication:

#### Multiple API Endpoints Called:

**In `loadHILResults()` function (lines 583-624):**

```typescript
// SOURCE 1: From enhanced results response
addCandidateEvents((enhancedData as any)?.detection_events);
addCandidateEvents((enhancedData as any)?.detectionEvents);
addCandidateEvents((enhancedData as any)?.combined_detection_events);
addCandidateEvents((enhancedData as any)?.combinedDetectionEvents);
addCandidateEvents((enhancedData as any)?.detection_statistics?.detection_events);
addCandidateEvents((enhancedData as any)?.detection_statistics?.combined_detection_events);

// SOURCE 2: From session events endpoint
const events = await apiService.getTestSessionEvents(sessionId, 2000);
candidateEvents.push(...events);

// SOURCE 3: From session detections endpoint
const fallbackDetections = await apiService.getTestSessionDetections(sessionId);
candidateEvents.push(...fallbackDetections);

// SOURCE 4: From sequence results (if multi-video)
const sequenceCombinedEvents = normalizeDetectionEvents([
  ...(((effectiveSeqResults as any)?.combined_detection_events) ?? []),
  ...(((effectiveSeqResults as any)?.combinedDetectionEvents) ?? []),
  ...(((effectiveSeqResults as any)?.detection_events) ?? []),
  ...collectDetectionCandidates(effectiveSeqResults)
]);
```

**In parallel loading (lines 782-824):**

```typescript
// SOURCE 5: Per-video detection loading
const detResponse = await apiService.getDetectionEvents(sessionId, videoId);
```

### 2. **Weak Deduplication Logic**

The deduplication is based on a simple key that can fail:

```typescript
// Lines 626-636
const deduped: EnhancedDetectionEvent[] = [];
const seenKeys = new Set<string>();
normalizedDetections.forEach(event => {
  const key = event.id || `${event.timestamp}-${event.voltage ?? ''}-${event.real_latency_ms ?? ''}`;
  if (!seenKeys.has(key)) {
    seenKeys.add(key);
    deduped.push(event);
  }
});
```

**Problem**: If backend returns DIFFERENT `real_latency_ms` values for the same detection (due to processing at different times), the composite key will differ, allowing duplicates through!

### 3. **Why Different Latency Values?**

The different `real_latency_ms` values suggest:

1. **Backend is recalculating latency** when returning detections from different endpoints
2. **Different timestamp references** being used (raw vs video-relative)
3. **Race conditions** in backend processing creating slightly different values
4. **Precision differences** in floating-point calculations

### 4. **Root Cause: Over-Fetching**

The frontend is trying to be "defensive" by fetching from multiple sources:
- Enhanced results endpoint
- Session events endpoint
- Session detections endpoint
- Sequence results endpoint
- Per-video detection endpoint

This creates a scenario where the **same detection can be returned by multiple endpoints** with slightly different calculated fields.

---

## Evidence from Code

### File: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`

**Multiple fetch locations:**

1. **Line 574**: `apiService.getEnhancedHILResultsWithGroundTruth(sessionId)`
2. **Line 604**: `apiService.getTestSessionEvents(sessionId, 2000)`
3. **Line 616**: `apiService.getTestSessionDetections(sessionId)`
4. **Line 690**: `apiService.getVideoSequenceResults(detectedSequenceId)`
5. **Line 788**: `apiService.getDetectionEvents(sessionId, videoId)` (per-video)
6. **Line 452**: `apiService.getTestSessionEvents(sessionId, 2000, filters)` (video-specific)

### File: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/FrameCorrelationTimeline.tsx`

This component receives the already-duplicated `detectionEvents` array and displays them, showing different latency values for what appears to be the same detection.

---

## Recommended Fixes

### Fix #1: Use Single Source of Truth (BEST SOLUTION)

**Pick ONE authoritative endpoint** for detection events and remove all others:

```typescript
// Replace lines 583-624 with:
const normalizedDetections = await apiService.getTestSessionEvents(sessionId, 2000, filters);
```

**Remove**:
- ❌ Enhanced results detection arrays
- ❌ Fallback to getTestSessionDetections
- ❌ Sequence combined_detection_events
- ❌ Multiple candidate sources

### Fix #2: Strengthen Deduplication (IF Fix #1 Not Possible)

Use detection ID ONLY for deduplication:

```typescript
// Replace lines 626-636 with:
const deduped: EnhancedDetectionEvent[] = [];
const seenIds = new Set<string>();
normalizedDetections.forEach(event => {
  // CRITICAL: Only use ID for deduplication
  // Ignore timestamp/voltage/latency as they can vary between endpoints
  const eventId = event.id || event.detection_id || event.event_id;

  if (!eventId) {
    console.warn('Detection without ID, keeping it:', event);
    deduped.push(event);
    return;
  }

  if (!seenIds.has(eventId)) {
    seenIds.add(eventId);
    deduped.push(event);
  } else {
    console.log(`Skipping duplicate detection ID: ${eventId}`);
  }
});
```

### Fix #3: Backend Consistency Check

Ensure backend returns **consistent calculated fields** across all endpoints:
- Same `real_latency_ms` calculation
- Same timestamp normalization
- Same rounding/precision

### Fix #4: Add Detection Count Validation

```typescript
// After deduplication, validate against expected count
console.log(`✅ Deduplicated ${normalizedDetections.length - deduped.length} duplicates`);
console.log(`Final detection count: ${deduped.length}`);

// Optional: Alert if massive deduplication suggests a problem
if (normalizedDetections.length > deduped.length * 1.5) {
  console.error(`⚠️ High duplication rate: ${normalizedDetections.length} → ${deduped.length}`);
}
```

---

## Conclusion

**YES, the frontend IS the source of duplicates.**

The component is:
1. ✅ Fetching from 5+ different API endpoints
2. ✅ Combining results without proper deduplication
3. ✅ Using a composite key that fails when latency differs
4. ✅ Showing duplicates in UI with different `real_latency_ms` values

**The fix is to either:**
- Use a single authoritative endpoint (recommended)
- OR strengthen deduplication to use ID-only matching

The backend deduplication is bypassed because the frontend is **combining results from different endpoints** that each return the same detections with slight variations in calculated fields.
