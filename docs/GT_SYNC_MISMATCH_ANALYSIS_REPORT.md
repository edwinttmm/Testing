# Ground Truth Data Synchronization Mismatch Analysis Report

**Investigation Date:** 2025-11-14
**Agent:** Data Synchronization Specialist
**Session:** GT Sync Analysis

---

## Executive Summary

Critical data synchronization issues identified between frontend and backend ground truth (GT) counting systems. The evidence shows three different GT counts for the same session:

- **Frontend Display:** 242 total GT events
- **Backend API (session metrics):** 0 total_ground_truth
- **Backend API (video comparison):** 514 ground_truth_events_available

### Root Cause
The mismatch stems from **multiple independent GT counting systems** that are NOT synchronized, leading to inconsistent data across different API endpoints and frontend calculations.

---

## Evidence Analysis

### 1. Frontend Ground Truth Calculation

**File:** `/frontend/src/pages/HILResults.tsx`

**Lines 1243-1258:** Frontend calculates GT count from `videoGroundTruthMap`
```typescript
const totalGroundTruthFromMap = useMemo(() => {
  if (isSequence) {
    return Object.values(videoGroundTruthMap).reduce(
      (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
      0
    );
  }

  if (selectedVideoId && videoGroundTruthMap[selectedVideoId]) {
    return videoGroundTruthMap[selectedVideoId]?.length ?? 0;
  }

  return groundTruthEvents.length;
}, [isSequence, videoGroundTruthMap, groundTruthEvents, selectedVideoId]);

const totalGroundTruth = totalGroundTruthFromMap || gtComparison?.ground_truth_events_available || 0;
```

**Problem:** Frontend loads GT data asynchronously per video via `loadGroundTruthData()` function, which populates `videoGroundTruthMap`. If this map is incomplete or not loaded, the count will be incorrect.

**Lines 425-435:** GT data is loaded per video on demand
```typescript
perVideoSummaries.forEach(video => {
  const currentId = video.videoId ?? video.video_id ?? video.id;
  if (!currentId) {
    return;
  }

  if (videoGroundTruthMap[currentId] === undefined) {
    loadGroundTruthData(currentId);  // Async call - may not complete before aggregation
  }
});
```

### 2. Backend Ground Truth Loading

**File:** `/backend/src/api/enhanced_hil_results_endpoints.py`

**Lines 531-611:** Backend loads GT from database for ALL videos
```python
# Multi-video sequence: Load GT for ALL videos in sequence
if has_video_sequence and sequence_id:
    video_results = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence.id
    ).all()

    video_ids = [vr.video_id for vr in video_results]

    # Load GT for ALL videos in sequence
    gt_q = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id.in_(video_ids)
    ).order_by(GroundTruthObject.video_id, GroundTruthObject.timestamp).all()

    logger.info(f"🎯 BUG #8 FIX: Loaded GT for {len(video_ids)} videos in sequence: {len(gt_q)} total GT objects")
```

**Lines 600-608:** Backend transforms GT objects into events array
```python
ground_truth_events.append({
    'frame_number': frame_number or 0,
    'video_timestamp': gt_video_time or 0.0,
    'event_type': getattr(gt, 'class_label', 'ground_truth'),
    'video_id': getattr(gt, 'video_id', None),
    'confidence': getattr(gt, 'confidence', None)
})
```

### 3. Backend Per-Video Metrics Calculation

**File:** `/backend/src/api/enhanced_hil_results_endpoints.py`

**Lines 1209-1254:** Backend calculates per-video GT metrics
```python
# Get ground truth objects for this specific video (excluding soft-deleted)
video_ground_truth = db.query(GroundTruthObject).filter(
    GroundTruthObject.video_id == vr.video_id,
    GroundTruthObject.deleted_at.is_(None)
).all()
total_ground_truth = len(video_ground_truth)

# Calculate TP, FP, FN for this video
video_true_positives = sum(1 for d in video_detections if d.ground_truth_match_id is not None)
video_false_positives = sum(1 for d in video_detections if d.ground_truth_match_id is None)
video_false_negatives = total_ground_truth - video_true_positives

per_video_results.append({
    "ground_truth_metrics": {
        "total_ground_truth": total_ground_truth,
        "true_positives": video_true_positives,
        "false_positives": video_false_positives,
        "false_negatives": video_false_negatives,
        "precision": round(video_precision * 100, 2),
        "recall": round(video_recall * 100, 2),
        "f1_score": round(video_f1_score * 100, 2)
    }
})
```

### 4. Session-Level Aggregation

**File:** `/backend/routers/video_sequence_testing.py`

**Lines 1411-1442:** Aggregates GT metrics across all videos
```python
match_counts_for_video = per_video_match_counts.get(video_id, {"TP": 0, "FP": 0})
tp_count = match_counts_for_video.get("TP", 0)
fp_count = match_counts_for_video.get("FP", 0)
fn_count = per_video_fn_counts.get(video_id, 0)
total_ground_truth_events = tp_count + fn_count

ground_truth_metrics = {
    "true_positives": tp_count,
    "false_positives": fp_count,
    "false_negatives": fn_count,
    "total_ground_truth": total_ground_truth_events,
    "precision": round(precision_ratio * 100, 1),
    "recall": round(recall_ratio * 100, 1),
    "f1_score": round(f1_ratio * 100, 1),
    "ground_truth_events_available": total_ground_truth_events
}
```

**Lines 1550-1589:** Creates session-level ground_truth_comparison
```python
total_ground_truth_events = sequence_true_positives + sequence_false_negatives

if session_metrics:
    ground_truth_comparison = {
        "ground_truth_events_available": session_metrics.total_ground_truth,
        "total_detections": session_metrics.total_detections,
        "true_positives": session_metrics.true_positives,
        # ... more metrics
    }
elif total_ground_truth_events > 0 or sequence_false_positives > 0:
    ground_truth_comparison = {
        "ground_truth_events_available": total_ground_truth_events,
        # ... calculated from aggregated per-video data
    }
```

---

## Data Flow Diagram

```
DATABASE (ground_truth_objects table)
         │
         ├─────────────────────────────────────────────────┐
         │                                                  │
         ▼                                                  ▼
   enhanced_hil_results_endpoints.py              video_sequence_testing.py
   (Lines 531-611)                                (Lines 1209-1254, 1411-1442)
         │                                                  │
         │ Query: GroundTruthObject.filter(                │ Query per video:
         │   video_id.in_(all_video_ids)                   │   GroundTruthObject.filter(
         │ )                                                │     video_id == specific_video
         │                                                  │   )
         │ Returns: gt_q list                              │
         │ Transforms into:                                │ Aggregates into:
         │   ground_truth_events[] array                   │   per_video_results[]
         │                                                  │
         ▼                                                  ▼
   API Response Field:                            API Response Fields:
   - ground_truth_comparison.                     - perVideoResults[].ground_truth_metrics
     ground_truth_events                          - ground_truth_comparison.
   - Array of GT event objects                      ground_truth_events_available
   - Count: 514 (in evidence)                     - Calculated from session_metrics or
                                                     aggregated per-video TP+FN
         │                                                  │
         └──────────────────┬───────────────────────────────┘
                            │
                            ▼
                     FRONTEND HILResults.tsx
                            │
                ┌───────────┴────────────┐
                │                        │
                ▼                        ▼
         loadGroundTruthData()    totalGroundTruthFromMap
         (Lines 425-435)          (Lines 1243-1258)
                │                        │
                │ Async per-video        │ Calculates from:
                │ API calls to:          │ 1. videoGroundTruthMap (async loaded)
                │ getGroundTruthEvents() │ 2. gtComparison.ground_truth_events_available
                │                        │ 3. groundTruthEvents.length (fallback)
                │                        │
                ▼                        ▼
         videoGroundTruthMap{}    totalGroundTruth = 242 (evidence)
         (State updated async)    (Display value - INCONSISTENT)
```

---

## Root Cause Analysis

### Issue 1: Multiple Independent Counting Systems

**Problem:** Three separate systems count ground truth events:

1. **`enhanced_hil_results_endpoints.py`** (Lines 531-611)
   - Directly queries `GroundTruthObject` table
   - Transforms into `ground_truth_events[]` array
   - Returns count in API response

2. **`video_sequence_testing.py`** (Lines 1209-1254)
   - Queries `GroundTruthObject` per video
   - Aggregates into `per_video_results[].ground_truth_metrics`
   - Uses `session_metrics.total_ground_truth` OR calculates from TP+FN

3. **Frontend `HILResults.tsx`** (Lines 1243-1258)
   - Loads GT data asynchronously via `loadGroundTruthData()`
   - Aggregates from `videoGroundTruthMap`
   - Fallback to `gtComparison.ground_truth_events_available`

**Result:** Each system may produce different counts due to:
- Timing of queries (data changes between calls)
- Different filtering logic (soft-deleted records)
- Async loading race conditions on frontend
- Calculation vs direct query differences

### Issue 2: Session Metrics vs Video Aggregation Mismatch

**File:** `/backend/routers/video_sequence_testing.py` (Lines 1560-1572)

```python
if session_metrics:
    ground_truth_comparison = {
        "ground_truth_events_available": session_metrics.total_ground_truth,  # ← Returns 0
        # ...
    }
elif total_ground_truth_events > 0 or sequence_false_positives > 0:
    ground_truth_comparison = {
        "ground_truth_events_available": total_ground_truth_events,  # ← Returns 514
        # ...
    }
```

**Problem:** Two different code paths:
- **Path 1 (session_metrics exists):** Uses pre-calculated `session_metrics.total_ground_truth` → **Returns 0**
- **Path 2 (no session_metrics):** Calculates from aggregated per-video data → **Returns 514**

**Why session_metrics.total_ground_truth = 0:**
- Session metrics are calculated by `ground_truth_matching_service.py` (Lines 76, 1289, 1691, 1721)
- If matching hasn't run or failed, `total_ground_truth = 0` is returned
- This stale/missing data takes precedence over actual database counts

### Issue 3: Frontend Async Loading Race Condition

**File:** `/frontend/src/pages/HILResults.tsx` (Lines 425-435)

```typescript
perVideoSummaries.forEach(video => {
  const currentId = video.videoId ?? video.video_id ?? video.id;
  if (videoGroundTruthMap[currentId] === undefined) {
    loadGroundTruthData(currentId);  // ← Async - doesn't block
  }
});
```

**Problem:** Frontend triggers async GT loading for each video, but aggregation happens BEFORE these loads complete:

**Lines 1243-1258:** Aggregation runs immediately
```typescript
const totalGroundTruthFromMap = useMemo(() => {
  if (isSequence) {
    return Object.values(videoGroundTruthMap).reduce(  // ← May be incomplete!
      (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
      0
    );
  }
  // ...
}, [isSequence, videoGroundTruthMap, groundTruthEvents, selectedVideoId]);
```

**Result:** `videoGroundTruthMap` may be empty or partially populated when aggregation runs, leading to incorrect count (242 instead of 514).

### Issue 4: Session-to-Video GT Association

**File:** `/backend/src/api/enhanced_hil_results_endpoints.py` (Lines 534-577)

```python
# Check if this is a multi-video sequence session
has_video_sequence = getattr(session_result, 'has_video_sequence', False)
sequence_id = getattr(session_result, 'sequence_id', None)

if has_video_sequence and sequence_id:
    # Multi-video sequence: Load GT for ALL videos in sequence
    # ...
else:
    # Single video session - use existing logic
    video_id = getattr(session_result, 'video_id', None)
    if video_id is not None:
        gt_q = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == video_id
        ).order_by(GroundTruthObject.timestamp).all()
```

**Problem:** Two different loading paths:
- Multi-video: Loads GT for ALL videos in sequence
- Single-video: Loads GT for ONE video only

**If session metadata is incorrect:**
- Session marked as single-video but has multiple videos → Missing GT data
- Session marked as multi-video but sequence not found → Falls back to single video

---

## Why Frontend Shows 242 (Not 514 or 0)

### Hypothesis: Partial Load + Stale Cache

**Evidence from code analysis:**

1. **Backend returns 514 in one field:**
   - `ground_truth_comparison.ground_truth_events_available = 514`
   - This comes from aggregated per-video TP+FN calculation

2. **Backend returns 0 in another field:**
   - `session_metrics.total_ground_truth = 0`
   - This comes from stale or missing matching service data

3. **Frontend shows 242:**
   - Frontend's `videoGroundTruthMap` is partially populated
   - Some videos loaded GT data (242 events), others still pending
   - Aggregation ran before all async loads completed

**Timeline of Events:**
```
T0: Page loads, fetches session data
T1: Backend returns:
    - ground_truth_comparison.ground_truth_events_available = 514
    - session_metrics.total_ground_truth = 0
T2: Frontend parses response, sets perVideoSummaries[]
T3: Frontend triggers loadGroundTruthData() for each video (async)
T4: Frontend aggregation runs (useMemo dependency changed)
T5: videoGroundTruthMap = { video1: [50 events], video2: [192 events] }
T6: totalGroundTruthFromMap = 242 (partial data)
T7: Remaining loadGroundTruthData() calls complete (too late)
T8: User sees 242 on screen (incorrect)
```

---

## Recommended Fixes

### Fix 1: Single Source of Truth for GT Count (CRITICAL)

**Priority:** P0 - Critical
**Impact:** Eliminates root cause of all count mismatches

**Implementation:**

**Backend Changes:**
1. Create a single function to get GT count for session:
   ```python
   # backend/services/ground_truth_service.py
   def get_session_ground_truth_count(
       db: Session,
       session_id: str,
       include_soft_deleted: bool = False
   ) -> int:
       """
       Single source of truth for session GT count.
       Uses actual database query, not cached metrics.
       """
       session = db.query(TestSession).filter(TestSession.id == session_id).first()
       if not session:
           return 0

       video_ids = []
       if session.has_video_sequence and session.sequence_id:
           # Multi-video: Get all video IDs from sequence
           sequence = db.query(VideoTestSequence).filter(
               VideoTestSequence.id == session.sequence_id
           ).first()
           if sequence:
               video_results = db.query(SequenceVideoResult).filter(
                   SequenceVideoResult.video_sequence_id == sequence.id
               ).all()
               video_ids = [vr.video_id for vr in video_results]
       elif session.video_id:
           # Single video
           video_ids = [session.video_id]

       if not video_ids:
           return 0

       # Query ground truth objects
       query = db.query(GroundTruthObject).filter(
           GroundTruthObject.video_id.in_(video_ids)
       )

       # Exclude soft-deleted by default
       if not include_soft_deleted:
           query = query.filter(GroundTruthObject.deleted_at.is_(None))

       return query.count()
   ```

2. Update ALL backend endpoints to use this function:
   ```python
   # In enhanced_hil_results_endpoints.py
   from services.ground_truth_service import get_session_ground_truth_count

   # Replace existing GT loading logic with:
   total_ground_truth_count = get_session_ground_truth_count(db, session_id)

   ground_truth_comparison = {
       "ground_truth_events_available": total_ground_truth_count,
       # ... other fields
   }
   ```

3. Update session_metrics to always refresh from database:
   ```python
   # In ground_truth_matching_service.py
   def calculate_session_metrics(db: Session, session_id: str) -> SessionMetrics:
       # ALWAYS get fresh count from database
       total_ground_truth = get_session_ground_truth_count(db, session_id)

       # Calculate TP/FP/FN from matches
       # ...

       return SessionMetrics(
           total_ground_truth=total_ground_truth,  # ← Fresh data
           # ...
       )
   ```

### Fix 2: Frontend GT Data Pre-Loading (HIGH)

**Priority:** P1 - High
**Impact:** Eliminates async race condition

**Implementation:**

**Frontend Changes:**
1. Load all GT data BEFORE rendering:
   ```typescript
   // In HILResults.tsx
   const loadHILResults = useCallback(async () => {
     if (!sessionId) return;

     try {
       setLoading(true);

       // Step 1: Fetch session data
       const sessionData = await apiService.getEnhancedHILResults(sessionId);

       // Step 2: Extract all video IDs
       const videoIds = extractVideoIds(sessionData);

       // Step 3: Pre-load ALL ground truth data in parallel
       const gtLoadPromises = videoIds.map(videoId =>
         apiService.getGroundTruthEvents(videoId)
           .then(response => ({
             videoId,
             events: response?.data?.ground_truth_events || []
           }))
           .catch(err => {
             console.error(`Failed to load GT for ${videoId}:`, err);
             return { videoId, events: [] };
           })
       );

       const gtResults = await Promise.all(gtLoadPromises);

       // Step 4: Build complete videoGroundTruthMap
       const completeGTMap = gtResults.reduce((map, result) => {
         map[result.videoId] = result.events;
         return map;
       }, {} as Record<string, any[]>);

       // Step 5: Set all state together (atomic update)
       setVideoGroundTruthMap(completeGTMap);
       setEnhancedResults(sessionData);
       setPerVideoSummaries(sessionData.perVideoResults || []);

       setLoading(false);
     } catch (err) {
       console.error('Error loading HIL results:', err);
       setError(err?.message || 'Failed to load HIL results');
       setLoading(false);
     }
   }, [sessionId]);
   ```

2. Update aggregation to wait for complete data:
   ```typescript
   const totalGroundTruthFromMap = useMemo(() => {
     // Check if all GT data is loaded
     const allVideosHaveGT = perVideoSummaries.every(video => {
       const videoId = video.videoId ?? video.video_id ?? video.id;
       return videoId && videoGroundTruthMap[videoId] !== undefined;
     });

     if (!allVideosHaveGT) {
       console.warn('GT data still loading, showing backend count');
       return gtComparison?.ground_truth_events_available || 0;
     }

     // All data loaded - calculate from map
     if (isSequence) {
       return Object.values(videoGroundTruthMap).reduce(
         (sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0),
         0
       );
     }

     if (selectedVideoId && videoGroundTruthMap[selectedVideoId]) {
       return videoGroundTruthMap[selectedVideoId]?.length ?? 0;
     }

     return groundTruthEvents.length;
   }, [
     isSequence,
     videoGroundTruthMap,
     groundTruthEvents,
     selectedVideoId,
     perVideoSummaries,
     gtComparison
   ]);
   ```

### Fix 3: Add GT Count Validation (MEDIUM)

**Priority:** P2 - Medium
**Impact:** Catches mismatches early, aids debugging

**Implementation:**

**Backend Changes:**
1. Add validation endpoint:
   ```python
   @router.get("/api/sessions/{session_id}/validate-gt-counts")
   async def validate_ground_truth_counts(
       session_id: str,
       db: Session = Depends(get_db)
   ):
       """
       Validates GT count consistency across all data sources.
       Returns diagnostic information about any mismatches.
       """
       from services.ground_truth_service import get_session_ground_truth_count

       # Source 1: Direct database query
       db_count = get_session_ground_truth_count(db, session_id)

       # Source 2: Session metrics
       session_metrics = get_session_metrics(db, session_id)
       metrics_count = session_metrics.total_ground_truth if session_metrics else None

       # Source 3: Aggregated per-video
       per_video_results = get_per_video_results(db, session_id)
       aggregated_count = sum(
           vr.get('ground_truth_metrics', {}).get('total_ground_truth', 0)
           for vr in per_video_results
       )

       # Check for mismatches
       counts_match = (
           db_count == metrics_count == aggregated_count
       )

       return {
           "counts_match": counts_match,
           "database_query": db_count,
           "session_metrics": metrics_count,
           "aggregated_per_video": aggregated_count,
           "mismatch_detected": not counts_match,
           "diagnostic_info": {
               "session_id": session_id,
               "timestamp": datetime.utcnow().isoformat(),
               "video_count": len(per_video_results)
           }
       }
   ```

2. Add backend logging:
   ```python
   # In video_sequence_testing.py
   logger.warning(
       f"[GT_COUNT_CHECK] Session {session_id}: "
       f"DB={db_count}, "
       f"SessionMetrics={session_metrics.total_ground_truth if session_metrics else None}, "
       f"Aggregated={aggregated_count}"
   )

   if db_count != (session_metrics.total_ground_truth if session_metrics else 0):
       logger.error(
           f"[GT_COUNT_MISMATCH] Session {session_id} has inconsistent GT counts! "
           f"This indicates a synchronization issue."
       )
   ```

**Frontend Changes:**
1. Add validation check on load:
   ```typescript
   // In HILResults.tsx
   useEffect(() => {
     if (!sessionId || !enhancedResults) return;

     const validateCounts = async () => {
       try {
         const validation = await apiService.validateGroundTruthCounts(sessionId);

         if (!validation.counts_match) {
           console.error('GT count mismatch detected:', validation);

           // Show warning to user
           setError(
             `Ground truth count mismatch detected: ` +
             `Database=${validation.database_query}, ` +
             `Metrics=${validation.session_metrics}, ` +
             `Aggregated=${validation.aggregated_per_video}`
           );
         }
       } catch (err) {
         console.warn('GT validation failed:', err);
       }
     };

     validateCounts();
   }, [sessionId, enhancedResults]);
   ```

### Fix 4: Improve Session-to-Video Association (MEDIUM)

**Priority:** P2 - Medium
**Impact:** Ensures correct video IDs are used for GT queries

**Implementation:**

**Backend Changes:**
1. Add association verification:
   ```python
   # In enhanced_hil_results_endpoints.py
   def verify_session_video_association(
       db: Session,
       session_id: str
   ) -> Tuple[bool, List[str], str]:
       """
       Verifies session is correctly associated with videos.
       Returns: (is_multi_video, video_ids_list, error_message)
       """
       session = db.query(TestSession).filter(TestSession.id == session_id).first()
       if not session:
           return (False, [], "Session not found")

       # Check for sequence
       if session.has_video_sequence and session.sequence_id:
           sequence = db.query(VideoTestSequence).filter(
               VideoTestSequence.id == session.sequence_id
           ).first()

           if not sequence:
               logger.error(
                   f"Session {session_id} has sequence_id {session.sequence_id} "
                   f"but sequence not found in database!"
               )
               # Fall back to single video
               if session.video_id:
                   return (False, [session.video_id], "Sequence not found, using single video")
               return (False, [], "Sequence not found and no fallback video")

           video_results = db.query(SequenceVideoResult).filter(
               SequenceVideoResult.video_sequence_id == sequence.id
           ).all()

           video_ids = [vr.video_id for vr in video_results]

           if not video_ids:
               logger.error(
                   f"Sequence {sequence.id} has no associated videos!"
               )
               return (False, [], "Sequence has no videos")

           return (True, video_ids, "")

       # Single video
       if session.video_id:
           return (False, [session.video_id], "")

       return (False, [], "No video associated with session")
   ```

2. Use verification before loading GT:
   ```python
   # In enhanced_hil_results_endpoints.py (replace existing logic)
   is_multi_video, video_ids, error_msg = verify_session_video_association(db, session_id)

   if error_msg and not video_ids:
       logger.error(f"Cannot load GT for session {session_id}: {error_msg}")
       ground_truth_events = []
   else:
       if error_msg:
           logger.warning(f"Session {session_id}: {error_msg}")

       # Load GT for verified video IDs
       gt_q = db.query(GroundTruthObject).filter(
           GroundTruthObject.video_id.in_(video_ids),
           GroundTruthObject.deleted_at.is_(None)
       ).order_by(
           GroundTruthObject.video_id,
           GroundTruthObject.timestamp
       ).all()

       logger.info(
           f"Loaded {len(gt_q)} GT objects for session {session_id} "
           f"({'multi-video' if is_multi_video else 'single-video'}, "
           f"{len(video_ids)} videos)"
       )
   ```

---

## Testing Strategy

### Test 1: Verify Single Source of Truth

**Objective:** Confirm all endpoints return same GT count

**Steps:**
1. Select test session with known GT count (e.g., 24 events)
2. Call `/api/sessions/{session_id}/enhanced-results` - check `ground_truth_comparison.ground_truth_events_available`
3. Call `/api/sessions/{session_id}/sequence-results` - check `ground_truth_comparison.ground_truth_events_available`
4. Call `/api/sessions/{session_id}/metrics` - check `total_ground_truth`
5. Query database directly: `SELECT COUNT(*) FROM ground_truth_objects WHERE video_id IN (session_videos)`
6. **PASS:** All 5 counts match exactly
7. **FAIL:** Any count differs - investigate which system is incorrect

### Test 2: Frontend Pre-Loading Race Condition

**Objective:** Confirm GT data fully loaded before aggregation

**Steps:**
1. Open HILResults page for multi-video session
2. Add console logging to track load sequence:
   ```typescript
   console.log('T1: Starting loadHILResults');
   // ... after fetching session data
   console.log('T2: Session data fetched, videoIds:', videoIds);
   // ... after Promise.all GT loads
   console.log('T3: All GT data loaded, map:', videoGroundTruthMap);
   // ... in useMemo aggregation
   console.log('T4: Aggregating GT count, map keys:', Object.keys(videoGroundTruthMap));
   console.log('T5: Aggregated count:', totalGroundTruthFromMap);
   ```
3. Verify log order: T1 → T2 → T3 → T4 → T5
4. Verify T4 shows ALL video IDs from T2 present in map
5. **PASS:** All videos loaded before aggregation runs
6. **FAIL:** T4 runs before T3, or missing video IDs in map

### Test 3: Validation Endpoint

**Objective:** Confirm validation detects mismatches

**Steps:**
1. Call `/api/sessions/{session_id}/validate-gt-counts`
2. Check response structure:
   ```json
   {
     "counts_match": true/false,
     "database_query": 514,
     "session_metrics": 0,
     "aggregated_per_video": 514,
     "mismatch_detected": true,
     "diagnostic_info": {...}
   }
   ```
3. If mismatch detected, use diagnostic_info to investigate root cause
4. **PASS:** Validation returns `counts_match: true`
5. **FAIL:** Validation returns `mismatch_detected: true` - apply fixes and re-test

### Test 4: Session-Video Association

**Objective:** Confirm correct video IDs used for GT queries

**Steps:**
1. Test multi-video session:
   - Call `verify_session_video_association(db, session_id)`
   - Verify returns `(True, [vid1, vid2, vid3], "")`
   - Verify GT query uses ALL video IDs
2. Test single-video session:
   - Call `verify_session_video_association(db, session_id)`
   - Verify returns `(False, [vid1], "")`
   - Verify GT query uses single video ID
3. Test broken sequence (sequence_id exists but sequence not found):
   - Verify falls back to single video
   - Verify error message logged
4. **PASS:** All session types correctly identify video IDs
5. **FAIL:** Wrong video IDs returned or errors not handled

---

## Deployment Plan

### Phase 1: Backend Single Source of Truth (Week 1)

**Tasks:**
1. Implement `ground_truth_service.py` with `get_session_ground_truth_count()`
2. Update `enhanced_hil_results_endpoints.py` to use service
3. Update `video_sequence_testing.py` to use service
4. Update `ground_truth_matching_service.py` to refresh from database
5. Add logging for GT count at each endpoint
6. Deploy to staging environment
7. Run Test 1 (Verify Single Source of Truth)
8. Monitor logs for 24 hours

**Success Criteria:**
- All endpoints return same GT count
- No "GT_COUNT_MISMATCH" errors in logs
- Test 1 passes for 10 different sessions

### Phase 2: Frontend Pre-Loading (Week 2)

**Tasks:**
1. Refactor `loadHILResults()` to pre-load all GT data
2. Update `totalGroundTruthFromMap` to check for complete data
3. Add loading state indicators for GT data
4. Deploy to staging environment
5. Run Test 2 (Frontend Pre-Loading Race Condition)
6. Performance testing (check for slowdowns with large GT datasets)

**Success Criteria:**
- Frontend always shows correct GT count
- No race condition warnings in console
- Test 2 passes for multi-video sessions
- Page load time < 3 seconds for 10-video sequences

### Phase 3: Validation & Monitoring (Week 3)

**Tasks:**
1. Implement validation endpoint `/validate-gt-counts`
2. Add frontend validation check on load
3. Create monitoring dashboard for GT count mismatches
4. Set up alerts for validation failures
5. Deploy to production
6. Run Tests 3 & 4

**Success Criteria:**
- Validation endpoint returns `counts_match: true` for all sessions
- No mismatch alerts triggered in first week
- Tests 3 & 4 pass for all test cases

---

## Monitoring & Alerting

### Metrics to Track

1. **GT Count Consistency Rate:**
   ```
   (Sessions with matching GT counts / Total sessions) * 100%
   Target: 100%
   ```

2. **Frontend-Backend GT Difference:**
   ```
   |Frontend GT count - Backend GT count|
   Target: 0 (exact match)
   ```

3. **Async Load Completion Rate:**
   ```
   (GT loads completed before aggregation / Total GT loads) * 100%
   Target: 100%
   ```

4. **Session-Video Association Failures:**
   ```
   Count of sessions with video association errors
   Target: 0
   ```

### Alert Thresholds

**Critical (P0):**
- GT count mismatch > 10% difference
- Session-video association failure rate > 1%
- Frontend async load failures > 5%

**Warning (P1):**
- GT count mismatch > 5% difference
- Validation endpoint failures > 2%
- Slow GT load times (> 5 seconds)

### Logging Strategy

**Add structured logs:**
```python
logger.info(
    "GT_COUNT_SYNC",
    extra={
        "session_id": session_id,
        "source": "database_query",
        "count": db_count,
        "video_count": len(video_ids),
        "is_multi_video": is_multi_video,
        "timestamp": datetime.utcnow().isoformat()
    }
)
```

**Log locations:**
- Backend: `/backend/logs/gt_sync.log`
- Frontend: Browser console + Sentry
- Alerts: Slack #gt-sync-alerts channel

---

## Conclusion

The ground truth data mismatch (242 vs 514 vs 0) stems from **multiple independent counting systems** that are not synchronized:

1. **Backend session_metrics** (returns 0) - stale/missing matching data
2. **Backend aggregated per-video** (returns 514) - calculated from TP+FN
3. **Frontend async loading** (shows 242) - race condition, partial data

**Recommended fixes prioritize:**
1. **Single source of truth** (P0) - Eliminate root cause
2. **Frontend pre-loading** (P1) - Fix race condition
3. **Validation endpoint** (P2) - Catch future issues
4. **Session-video verification** (P2) - Prevent association errors

**Implementation timeline:** 3 weeks with phased rollout and comprehensive testing.

---

## Appendices

### Appendix A: File References

**Backend Files:**
- `/backend/src/api/enhanced_hil_results_endpoints.py` (Lines 531-611, 1209-1254)
- `/backend/routers/video_sequence_testing.py` (Lines 1411-1442, 1550-1589)
- `/backend/services/ground_truth_matching_service.py` (Lines 76, 1289, 1691, 1721)

**Frontend Files:**
- `/frontend/src/pages/HILResults.tsx` (Lines 207, 425-435, 1243-1258)

### Appendix B: API Response Structure

**Enhanced Results API:**
```json
{
  "ground_truth_comparison": {
    "ground_truth_events_available": 514,
    "total_detections": 131,
    "true_positives": 0,
    "false_positives": 131,
    "false_negatives": 514
  },
  "perVideoResults": [
    {
      "video_id": "vid1",
      "ground_truth_metrics": {
        "total_ground_truth": 242,
        "true_positives": 0,
        "false_positives": 50,
        "false_negatives": 242
      }
    }
  ]
}
```

**Session Metrics API:**
```json
{
  "session_metrics": {
    "total_ground_truth": 0,
    "total_detections": 131,
    "matched_detections": 0
  }
}
```

### Appendix C: Database Schema

**ground_truth_objects table:**
```sql
CREATE TABLE ground_truth_objects (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR REFERENCES videos(id),
    frame_number INTEGER,
    timestamp FLOAT,
    class_label VARCHAR,
    confidence FLOAT,
    deleted_at TIMESTAMP,  -- Soft delete
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_gt_video_id ON ground_truth_objects(video_id);
CREATE INDEX idx_gt_deleted_at ON ground_truth_objects(deleted_at);
```

**Query for session GT count:**
```sql
-- Multi-video session
SELECT COUNT(*)
FROM ground_truth_objects
WHERE video_id IN (
    SELECT video_id
    FROM sequence_video_results
    WHERE video_sequence_id = :sequence_id
)
AND deleted_at IS NULL;

-- Single-video session
SELECT COUNT(*)
FROM ground_truth_objects
WHERE video_id = :video_id
AND deleted_at IS NULL;
```

---

**Report End**
**Generated:** 2025-11-14
**Agent:** Data Synchronization Specialist
