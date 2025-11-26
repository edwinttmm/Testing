# Duplicate Detection Fix - Implementation Summary

## Problem
Duplicate detections appearing in the frontend HIL Results page:
- Frame 1: Two entries with "real 9ms" and "real 7ms"
- Frame 5: Two entries with "real 16ms" and "real 1ms"

## Root Causes Identified

### 1. Missing Deduplication in `allDetections` useMemo (HILResults.tsx:1182-1191)
**Issue**: When combining detections from multiple videos in `videoDetectionMap`, the code used `.flatMap()` without checking for duplicate IDs.

```typescript
// OLD CODE (Line 1182-1187)
const combined = Object.entries(videoDetectionMap)
  .filter(([key]) => key !== '__all__')
  .flatMap(([, value]) => (Array.isArray(value) ? value : []));
if (combined.length > baseCount) {
  return combined;  // ❌ No deduplication!
}
```

**Root Cause**: When the same detection exists in multiple video entries in `videoDetectionMap`, it would be included multiple times in the combined array.

### 2. Collision-Prone ID Generation (hilResultsNormalization.ts:203-210)
**Issue**: The ID generation fallback used only the index: `detection-${index}`

```typescript
// OLD CODE (Line 203-210)
const id =
  source.id ??
  source.event_id ??
  source.detection_id ??
  source.detectionId ??
  source.uuid ??
  source.identifier ??
  `detection-${index}`;  // ❌ Collision-prone!
```

**Root Cause**: When detections from different videos were normalized separately, the index would reset to 0 for each video, creating duplicate IDs like `detection-0`, `detection-1`, etc. across multiple videos.

### 3. Missing Deduplication in __all__ Aggregate (HILResults.tsx:467-476)
**Issue**: When building the `__all__` aggregate view, detections were combined without deduplication.

```typescript
// OLD CODE (Line 467-476)
const combined = Object.entries(next)
  .filter(([key]) => key !== '__all__')
  .flatMap(([, value]) => Array.isArray(value) ? value : []);
if (combined.length > prevAll.length) {
  next['__all__'] = combined;  // ❌ No deduplication!
}
```

### 4. Potential Duplicates in Sequence Events (HILResults.tsx:712-719)
**Issue**: Multiple arrays were spread together without checking for duplicates.

```typescript
// OLD CODE (Line 712-719)
const sequenceCombinedEvents = normalizeDetectionEvents(
  [
    ...(effectiveSeqResults?.combined_detection_events ?? []),
    ...(effectiveSeqResults?.combinedDetectionEvents ?? []),
    ...(effectiveSeqResults?.detection_events ?? []),
    ...collectDetectionCandidates(effectiveSeqResults)
  ]  // ❌ Potential duplicates from multiple sources!
);
```

## Fixes Implemented

### Fix 1: Deduplication in `allDetections` useMemo
**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
**Lines**: 1186-1202

```typescript
// NEW CODE with deduplication
if (combined.length > baseCount) {
  const seen = new Set<string>();
  const deduplicated = combined.filter((detection) => {
    const id = detection?.id ?? detection?.event_id ?? detection?.detection_id;
    if (!id || seen.has(id)) {
      return false;
    }
    seen.add(id);
    return true;
  });
  console.log(`🔍 [allDetections] Deduplication: ${combined.length} → ${deduplicated.length} (removed ${combined.length - deduplicated.length} duplicates)`);
  return deduplicated;
}
```

**Impact**: Removes duplicate detections when combining from multiple video entries.

### Fix 2: Improved ID Generation with Composite Keys
**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/utils/hilResultsNormalization.ts`
**Lines**: 203-226

```typescript
// NEW CODE with collision-resistant IDs
const baseId =
  source.id ??
  source.event_id ??
  source.detection_id ??
  source.detectionId ??
  source.uuid ??
  source.identifier;

let id: string;
if (baseId) {
  id = String(baseId);
} else {
  // Generate collision-resistant ID using multiple fields
  const videoIdPart = source.video_id ?? source.videoId ?? 'unknown';
  const timestampPart = source.timestamp ?? source.time ?? source.unix_timestamp ?? index;
  const framePart = source.frame_number ?? source.frameNumber ?? '';
  const latencyPart = source.actual_latency_ms ?? source.latency_ms ?? source.real_latency_ms ?? '';

  // Create composite ID that's unique across videos and frames
  id = `detection-${videoIdPart}-${timestampPart}-${framePart}-${latencyPart}-${index}`;
}
```

**Impact**: Generates unique IDs even when index resets across different videos, preventing ID collisions.

### Fix 3: Deduplication in __all__ Aggregate
**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
**Lines**: 471-489

```typescript
// NEW CODE with deduplication for __all__ aggregate
const combined = Object.entries(next)
  .filter(([key]) => key !== '__all__')
  .flatMap(([, value]) => Array.isArray(value) ? value : []);

// DEDUPLICATION FIX: Remove duplicates when building __all__ aggregate
const seen = new Set<string>();
const deduplicated = combined.filter((detection) => {
  const id = detection?.id ?? detection?.event_id ?? detection?.detection_id;
  if (!id || seen.has(id)) {
    return false;
  }
  seen.add(id);
  return true;
});

const prevAll = Array.isArray(prev['__all__']) ? prev['__all__'] : [];
if (deduplicated.length > prevAll.length) {
  console.log(`🔍 [videoDetectionMap __all__] Deduplication: ${combined.length} → ${deduplicated.length} (removed ${combined.length - deduplicated.length} duplicates)`);
  next['__all__'] = deduplicated;
}
```

**Impact**: Ensures the aggregate `__all__` view doesn't contain duplicate detections.

### Fix 4: Deduplication in Sequence Events
**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
**Lines**: 712-736

```typescript
// NEW CODE with raw event deduplication
const rawCombinedEvents = [
  ...(((effectiveSeqResults as any)?.combined_detection_events) ?? []),
  ...(((effectiveSeqResults as any)?.combinedDetectionEvents) ?? []),
  ...(((effectiveSeqResults as any)?.detection_events) ?? []),
  ...collectDetectionCandidates(effectiveSeqResults)
];

// DEDUPLICATION FIX: Remove duplicates from raw events before normalization
const seenRawIds = new Set<string>();
const dedupedRawEvents = rawCombinedEvents.filter((event) => {
  const rawId = event?.id ?? event?.event_id ?? event?.detection_id ?? event?.uuid;
  if (!rawId) {
    return true; // Keep events without IDs (will get generated IDs during normalization)
  }
  if (seenRawIds.has(String(rawId))) {
    return false;
  }
  seenRawIds.add(String(rawId));
  return true;
});

console.log(`🔍 [sequenceCombinedEvents] Raw deduplication: ${rawCombinedEvents.length} → ${dedupedRawEvents.length} (removed ${rawCombinedEvents.length - dedupedRawEvents.length} duplicates)`);

const sequenceCombinedEvents = normalizeDetectionEvents(dedupedRawEvents);
```

**Impact**: Prevents duplicates from multiple sequence data sources.

## Files Modified

1. **HILResults.tsx** (3 locations)
   - Line 1186-1202: Added deduplication in `allDetections` useMemo
   - Line 471-489: Added deduplication when building `__all__` aggregate in videoDetectionMap
   - Line 712-736: Added deduplication for raw sequence events before normalization

2. **hilResultsNormalization.ts** (1 location)
   - Line 203-226: Improved ID generation with composite keys to prevent collisions

## Testing Recommendations

1. **Test Case 1**: Load a video sequence with multiple videos
   - Verify no duplicate detections in "All Videos" view
   - Check Frame 1 and Frame 5 specifically (previously problematic)

2. **Test Case 2**: Switch between individual video views and "All Videos"
   - Verify detection counts are consistent
   - Check console logs for deduplication messages

3. **Test Case 3**: Load videos with missing backend IDs
   - Verify generated IDs are unique across videos
   - Check format: `detection-{videoId}-{timestamp}-{frame}-{latency}-{index}`

4. **Console Monitoring**:
   - Look for deduplication logs: `🔍 [allDetections] Deduplication: X → Y`
   - Look for deduplication logs: `🔍 [videoDetectionMap __all__] Deduplication: X → Y`
   - Look for deduplication logs: `🔍 [sequenceCombinedEvents] Raw deduplication: X → Y`

## Expected Behavior After Fix

- **No duplicate detections** in any view (All Videos or individual videos)
- **Consistent detection counts** across views
- **Unique IDs** for all detections, even when backend doesn't provide them
- **Console logs** showing deduplication statistics when applicable

## Performance Considerations

- Set-based deduplication is O(n) time complexity
- Memory overhead is minimal (Set of strings)
- Logging can be removed in production if needed
- Deduplication only runs when:
  - Combining detections from multiple videos
  - Building aggregate views
  - Processing sequence events

## Related Issues

This fix addresses the frontend data flow issues identified in the previous research:
- Issue #1: `allDetections` useMemo lacked deduplication
- Issue #2: ID generation created collision-prone identifiers
- Issue #3: Multiple array spreads without duplicate checking
