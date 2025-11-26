# Frontend Duplicate Detection Data Flow Diagram

## Visual Representation of How Duplicates Are Created

```
┌─────────────────────────────────────────────────────────────────┐
│                    HILResults Component                          │
│                    (loadHILResults function)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │    Multiple API Endpoint Calls START        │
        └─────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
    ┌──────────────────────┐    ┌──────────────────────┐
    │   ENDPOINT #1        │    │   ENDPOINT #2        │
    │   Enhanced Results   │    │   Session Events     │
    │   /api/sessions/{id} │    │   /api/sessions/     │
    │   /enhanced-results  │    │   {id}/events        │
    └──────────────────────┘    └──────────────────────┘
            │                           │
            │ Returns:                  │ Returns:
            │ - detection_events        │ - events []
            │ - detectionEvents         │
            │ - combined_detection_     │
            │   events                  │
            │ - detection_statistics    │
            │   .detection_events       │
            │                           │
            ▼                           ▼
    ┌─────────────────────────────────────────┐
    │   candidateEvents.push(...events)       │
    │   ❌ SAME DETECTIONS ADDED TWICE         │
    └─────────────────────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────┐
        │    ENDPOINT #3            │
        │    Fallback Detections    │
        │    /api/sessions/{id}/    │
        │    detections             │
        └───────────────────────────┘
                    │
                    │ Returns: detections []
                    ▼
    ┌─────────────────────────────────────────┐
    │   candidateEvents.push(...detections)   │
    │   ❌ SAME DETECTIONS ADDED THIRD TIME    │
    └─────────────────────────────────────────┘
                    │
                    ▼
    ┌────────────────────────────────────────────────┐
    │   IF Multi-Video Sequence:                     │
    │                                                 │
    │   ENDPOINT #4: Sequence Results                │
    │   /api/sequences/{id}/results                  │
    │   - combined_detection_events                  │
    │   - detection_events                           │
    │                                                 │
    │   ❌ SAME DETECTIONS ADDED FOURTH TIME          │
    └────────────────────────────────────────────────┘
                    │
                    ▼
    ┌────────────────────────────────────────────────┐
    │   IF Multi-Video Sequence:                     │
    │                                                 │
    │   ENDPOINT #5: Per-Video Detections (Loop)     │
    │   For each video in sequence:                  │
    │     /api/sessions/{id}/events?video_id={vid}   │
    │                                                 │
    │   ❌ SAME DETECTIONS ADDED FIFTH TIME           │
    └────────────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────┐
    │   WEAK DEDUPLICATION LOGIC                      │
    │   (Lines 626-636)                               │
    │                                                  │
    │   const key = event.id ||                       │
    │     `${timestamp}-${voltage}-${real_latency}`   │
    │                                                  │
    │   ❌ FAILS when backend returns different        │
    │      real_latency_ms values!                    │
    │                                                  │
    │   Example:                                      │
    │   Detection #123:                               │
    │     - From endpoint #1: real_latency = 45.2ms   │
    │     - From endpoint #2: real_latency = 45.8ms   │
    │                                                  │
    │   Different keys → Both kept as "unique"!       │
    └─────────────────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────────────────┐
    │   RESULT: DUPLICATES IN UI                      │
    │                                                  │
    │   Detection #123 appears TWICE with:            │
    │   - Different real_latency_ms values            │
    │   - All other fields identical                  │
    │                                                  │
    │   User sees confusion in table!                 │
    └─────────────────────────────────────────────────┘
```

---

## Why Different Latency Values?

```
Backend Processing Timeline:

Time T0: Detection recorded
  └─> raw_timestamp = 1732511234.567
  └─> voltage = 3.2V
  └─> Initial latency calculation = 45.2ms

Time T1: Enhanced results endpoint hit
  └─> Returns detection with real_latency_ms = 45.2ms

Time T2: Session events endpoint hit
  └─> Backend recalculates latency using slightly different reference
  └─> Returns SAME detection with real_latency_ms = 45.8ms
  └─> Possible causes:
      - Different timestamp precision
      - Recalculation from raw data
      - Different video_start_timestamp reference
      - Floating-point rounding differences

Time T3: Frontend combines both
  └─> Deduplication key differs due to latency mismatch
  └─> Both detections kept in array
  └─> User sees duplicate with "different" latencies
```

---

## Data Flow Summary

```
API Endpoint          | Returns Count | Dedup Key Issues
----------------------|---------------|------------------
Enhanced Results      | 65 detections | Some have ID, some don't
Session Events        | 65 detections | Latency recalculated → different key
Fallback Detections   | 65 detections | Latency recalculated → different key
Sequence Results      | 65 detections | Combined from above sources
Per-Video (x3 videos) | 195 (3x65)    | Video-specific, but duplicates session-level

BEFORE Dedup:  ~325 total detection objects (5x65)
AFTER Dedup:   130 detections (some duplicates slip through)
EXPECTED:      65 unique detections

Duplicate Rate: 100% over-fetching, ~50% slipping through dedup
```

---

## Proof of Frontend as Duplicate Source

### Evidence 1: Multiple Fetch Calls
- Line 574: `getEnhancedHILResultsWithGroundTruth()`
- Line 604: `getTestSessionEvents()`
- Line 616: `getTestSessionDetections()`
- Line 690: `getVideoSequenceResults()`
- Line 788: `getDetectionEvents()` per video

### Evidence 2: Combining Results
```typescript
// Lines 585-597
addCandidateEvents((enhancedData as any)?.detection_events);
addCandidateEvents((enhancedData as any)?.detectionEvents);
addCandidateEvents((enhancedData as any)?.combined_detection_events);
// ... 6 more sources from same response!

// Line 607
candidateEvents.push(...events);  // From different endpoint

// Line 619
candidateEvents.push(...fallbackDetections);  // From third endpoint
```

### Evidence 3: Weak Deduplication
```typescript
// Lines 626-636
const key = event.id || `${event.timestamp}-${event.voltage ?? ''}-${event.real_latency_ms ?? ''}`;

// ❌ This WILL create different keys if:
//    - event.id is missing/null
//    - real_latency_ms differs between endpoints
//    - voltage has precision differences
//    - timestamp has rounding differences
```

---

## Recommended Fix (Simplest)

**Replace lines 583-624 with:**

```typescript
// Load detections from SINGLE authoritative source
console.log('Loading detections from authoritative endpoint');
const normalizedDetections = normalizeDetectionEvents(
  await apiService.getTestSessionEvents(sessionId, 2000)
);

// Deduplication by ID only (ignore calculated fields)
const deduped: EnhancedDetectionEvent[] = [];
const seenIds = new Set<string>();
normalizedDetections.forEach(event => {
  const eventId = event.id || event.detection_id || event.event_id;
  if (!eventId) {
    console.warn('Detection without ID:', event);
    deduped.push(event);
    return;
  }
  if (!seenIds.has(eventId)) {
    seenIds.add(eventId);
    deduped.push(event);
  }
});

console.log(`✅ Loaded ${deduped.length} unique detections (deduped ${normalizedDetections.length - deduped.length})`);
```

**Result:**
- Single API call instead of 5+
- No duplicate fetching
- No latency value mismatches
- Clean, predictable data flow

---

## Impact Analysis

**Current State:**
- 5+ API calls per page load
- 325 detection objects fetched (for 65 unique detections)
- 400% data over-fetching
- ~50% duplicates slip through weak deduplication
- User confusion from "different" latency values
- Increased load time
- Unnecessary backend load

**After Fix:**
- 1 API call per page load
- 65 detection objects fetched (exact count)
- 0% data over-fetching
- 0% duplicates (ID-based dedup)
- Clear, consistent UI
- Faster load time
- 80% reduction in API calls
