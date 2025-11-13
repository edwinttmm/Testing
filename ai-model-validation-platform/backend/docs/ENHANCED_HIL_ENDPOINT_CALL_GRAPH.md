# Complete Code Flow Map: Enhanced HIL Results Endpoint

## Executive Summary

**PRIMARY ENDPOINT**: `/api/enhanced-hil/test-sessions/{session_id}/corrected-results`

**CRITICAL FINDING**: The `video_id` query parameter is **DEFINED but NEVER PASSED** from the frontend!

---

## 1. Frontend API Call Chain

### Entry Point: Frontend Pages

**Location**: `frontend/src/pages/HILResults.tsx` (Line 304-308)
```typescript
// Primary call - tries ground truth endpoint first
enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);

// Fallback - uses corrected-results endpoint
enhancedData = await apiService.getEnhancedHILResults(sessionId);
```

**Location**: `frontend/src/pages/EnhancedResults.tsx`
```typescript
// Also uses the same API service methods
```

### API Service Layer

**Location**: `frontend/src/services/api.ts` (Lines 1149-1164)

#### Method 1: `getEnhancedHILResults(sessionId: string)`
```typescript
async getEnhancedHILResults(sessionId: string): Promise<any> {
  const response = await this.api.get(
    `/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`
  );
  return response.data;
}
```
**⚠️ ISSUE**: No `video_id` parameter passed!

#### Method 2: `getEnhancedHILResultsWithGroundTruth(sessionId: string)`
```typescript
async getEnhancedHILResultsWithGroundTruth(sessionId: string): Promise<any> {
  const response = await this.api.get(
    `/api/enhanced-hil/test-sessions/${sessionId}/ground-truth-comparison`
  );
  return response.data;
}
```
**⚠️ ISSUE**: No `video_id` parameter passed!

---

## 2. Backend Endpoint Registration

### Main Application Router

**Location**: `backend/main.py` (Lines 883-887)
```python
from src.api.enhanced_hil_results_endpoints import router as enhanced_hil_router
app.include_router(enhanced_hil_router)
print("✅ Enhanced HIL Test Results with Timing Correction API endpoints registered at /api/enhanced-hil")
```

**Router Prefix**: `/api/enhanced-hil` (defined in router configuration)

---

## 3. Backend Endpoint Implementation

### Primary Endpoint: `corrected-results`

**Location**: `backend/src/api/enhanced_hil_results_endpoints.py` (Lines 224-373)

#### Endpoint Declaration
```python
@router.get("/test-sessions/{session_id}/corrected-results")
async def get_corrected_hil_results(
    session_id: str,
    video_id: Optional[str] = Query(None, description="Filter by video ID for multi-video sequences"),
    db: Session = Depends(get_db)
):
```

#### Parameter Handling Flow
```python
# Line 264-265: video_id filter is applied IF provided
if video_id:
    detection_events_query = detection_events_query.filter(
        DetectionEvent.video_id == video_id
    )
```

**🔴 ROOT CAUSE**: The endpoint ACCEPTS `video_id` as optional query parameter but:
1. Frontend NEVER passes it
2. When `video_id=None`, ALL detection events are returned
3. This causes multi-video sessions to return data from ALL videos instead of current video

---

## 4. Alternative/Mirror Endpoint

### Ground Truth Comparison Endpoint

**Location**: `backend/src/api/enhanced_hil_results_endpoints.py` (Lines 902-928)

```python
@router.get("/test-sessions/{session_id}/ground-truth-comparison")
async def get_ground_truth_comparison(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Compatibility endpoint that returns enhanced HIL results payload
    including embedded `ground_truth_comparison` block.

    This mirrors GET /api/enhanced-hil/test-sessions/{session_id}/corrected-results
    """
    # Line 918: Internally calls corrected-results
    base_response = await get_corrected_hil_results(session_id=session_id, db=db)

    # Line 922: Adds metadata marker
    base_response["_meta"]["served_by"] = "ground-truth-comparison (mirrors corrected-results)"
    return base_response
```

**⚠️ ISSUE**: This endpoint ALSO doesn't accept `video_id` parameter!

---

## 5. Database Query Path

### Detection Events Retrieval

**Location**: Lines 256-267 in `enhanced_hil_results_endpoints.py`

```python
# Build query with eager loading (N+1 query optimization)
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    joinedload(DetectionEvent.test_session)
).filter(DetectionEvent.test_session_id == session_id)

# CRITICAL: This filter is ONLY applied if video_id is provided
if video_id:
    detection_events_query = detection_events_query.filter(
        DetectionEvent.video_id == video_id
    )

detection_events_result = detection_events_query.order_by(DetectionEvent.timestamp).all()
```

**🔴 BUG MANIFESTATION**:
- Multi-video session has `video_1.mp4` and `video_2.mp4`
- Frontend loads `video_1.mp4` at timestamp 0:05
- API call: `/api/enhanced-hil/test-sessions/{session_id}/corrected-results` (no video_id)
- Backend returns detection events from BOTH videos
- Frontend shows detection at 0:05 from `video_2.mp4` instead of `video_1.mp4`

---

## 6. Test and Debug Scripts

### Scripts calling the endpoint:
1. `backend/test_enhanced_hil_fix.py` (Line 17)
2. `backend/debug_ground_truth_events_structure.py` (Line 16)
3. `backend/test_time_based_matching.py` (Line 17)
4. `backend/debug_video_timing_final.py` (Line 16)
5. `backend/debug_api_response_structure.py` (Line 16)
6. `backend/test_frontend_integration.py` (Line 16)
7. `backend/debug_detection_events.py` (Line 16)

**⚠️ All test scripts**: Use hardcoded session_id, no video_id parameter

---

## 7. Related Endpoints (for reference)

### Other endpoints with video_id support:
- `/api/test-sessions/{session_id}/events` - **HAS** video_id parameter
- `/api/test-sessions/{session_id}/detection-events` - **HAS** video_id parameter
- `/api/labjack-detection/{session_id}/detections` - **HAS** video_id parameter

**These endpoints correctly implement video_id filtering!**

---

## 8. Complete Call Graph Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND LAYER                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  HILResults.tsx / EnhancedResults.tsx                      │
│         │                                                   │
│         ├─► apiService.getEnhancedHILResultsWithGroundTruth()│
│         │        │                                          │
│         │        └─► GET /api/enhanced-hil/.../ground-truth-comparison
│         │                                                   │
│         └─► apiService.getEnhancedHILResults()             │
│                  │                                          │
│                  └─► GET /api/enhanced-hil/.../corrected-results
│                                                             │
│         ⚠️ NO video_id passed in either call               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND ROUTING                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  main.py                                                    │
│    │                                                        │
│    └─► app.include_router(enhanced_hil_router)            │
│            │                                                │
│            └─► Prefix: /api/enhanced-hil                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 ENDPOINT HANDLERS                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  enhanced_hil_results_endpoints.py                         │
│                                                             │
│  Endpoint 1: /test-sessions/{session_id}/corrected-results │
│    ├─► Accepts: session_id (path), video_id (query)       │
│    ├─► video_id defaults to None                          │
│    └─► Line 264: if video_id: filter DetectionEvent       │
│                                                             │
│  Endpoint 2: /test-sessions/{session_id}/ground-truth-comparison
│    ├─► Accepts: session_id (path) ONLY                    │
│    └─► Line 918: Calls corrected-results internally       │
│                     (without video_id!)                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   DATABASE QUERY                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Query Builder:                                            │
│    db.query(DetectionEvent)                                │
│      .filter(test_session_id == session_id)               │
│      .filter(video_id == video_id)  ◄── ONLY IF PROVIDED  │
│      .all()                                                │
│                                                             │
│  🔴 When video_id=None:                                    │
│      Returns ALL detection events from ALL videos!         │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. The Bug in Detail

### Scenario: Multi-Video Test Session

**Setup**:
- Test session: `b7481a7d-b4d2-4425-afe1-235c7b29a8b5`
- Video 1: `pedestrian_crossing.mp4` (ID: `vid-001`)
- Video 2: `cyclist_approach.mp4` (ID: `vid-002`)
- User currently viewing Video 1

**What Happens**:

1. **Frontend Request**:
   ```
   GET /api/enhanced-hil/test-sessions/b7481a7d.../corrected-results
   ```
   ❌ Missing: `?video_id=vid-001`

2. **Backend Processing**:
   ```python
   # video_id = None (not provided)
   detection_events_query = db.query(DetectionEvent)
       .filter(test_session_id == 'b7481a7d...')

   # This condition is FALSE, so NO video filter applied
   if video_id:  # video_id is None
       detection_events_query = detection_events_query.filter(...)

   # Returns ALL detections from BOTH videos
   results = detection_events_query.all()
   ```

3. **Result**:
   - API returns 50 detections (25 from each video)
   - Frontend shows detections from BOTH videos
   - Timeline shows overlapping/incorrect events

### Expected Behavior:

1. **Frontend Request**:
   ```
   GET /api/enhanced-hil/test-sessions/b7481a7d.../corrected-results?video_id=vid-001
   ```

2. **Backend Processing**:
   ```python
   # video_id = 'vid-001' (provided)
   detection_events_query = db.query(DetectionEvent)
       .filter(test_session_id == 'b7481a7d...')
       .filter(video_id == 'vid-001')  # THIS FILTER NOW APPLIED

   # Returns ONLY detections from video_id='vid-001'
   results = detection_events_query.all()
   ```

3. **Result**:
   - API returns 25 detections (only from video 1)
   - Frontend shows correct detections for current video
   - Timeline is accurate

---

## 10. Fix Requirements

### Frontend Changes Needed:

**File**: `frontend/src/services/api.ts`

```typescript
// BEFORE (Lines 1149-1152)
async getEnhancedHILResults(sessionId: string): Promise<any> {
  const response = await this.api.get(
    `/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`
  );
  return response.data;
}

// AFTER
async getEnhancedHILResults(
  sessionId: string,
  videoId?: string
): Promise<any> {
  const params = videoId ? { video_id: videoId } : {};
  const response = await this.api.get(
    `/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`,
    { params }
  );
  return response.data;
}
```

**File**: `frontend/src/pages/HILResults.tsx`

```typescript
// BEFORE (Line 304)
enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);

// AFTER
const currentVideoId = getCurrentVideoId(); // Get from state/props
enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(
  sessionId,
  currentVideoId
);
```

### Backend Changes Needed:

**File**: `backend/src/api/enhanced_hil_results_endpoints.py`

```python
# Line 902: Add video_id parameter
@router.get("/test-sessions/{session_id}/ground-truth-comparison")
async def get_ground_truth_comparison(
    session_id: str,
    video_id: Optional[str] = Query(None, description="Filter by video ID"),  # ADD THIS
    db: Session = Depends(get_db)
):
    # Line 918: Pass video_id through
    base_response = await get_corrected_hil_results(
        session_id=session_id,
        video_id=video_id,  # ADD THIS
        db=db
    )
    return base_response
```

---

## 11. Verification Tests

### Test Cases to Add:

1. **Single Video Session** (regression test):
   ```python
   # Should work with or without video_id
   response1 = get("/api/enhanced-hil/test-sessions/{id}/corrected-results")
   response2 = get("/api/enhanced-hil/test-sessions/{id}/corrected-results?video_id={vid}")
   assert response1 == response2
   ```

2. **Multi-Video Session**:
   ```python
   # Without video_id: returns all detections
   all_detections = get("/api/enhanced-hil/test-sessions/{id}/corrected-results")

   # With video_id: returns filtered detections
   video1_detections = get("/api/enhanced-hil/test-sessions/{id}/corrected-results?video_id=vid1")
   video2_detections = get("/api/enhanced-hil/test-sessions/{id}/corrected-results?video_id=vid2")

   # Verify filtering
   assert len(all_detections) == len(video1_detections) + len(video2_detections)
   assert all(d.video_id == 'vid1' for d in video1_detections)
   assert all(d.video_id == 'vid2' for d in video2_detections)
   ```

---

## 12. Related Files to Check

### Files that might need updates:
- `frontend/src/types/enhanced-results.ts` - Type definitions
- `frontend/src/components/VideoSequenceResults.tsx` - Video sequence UI
- `backend/schemas.py` - Response schemas
- All test files in `backend/tests/` that call this endpoint

### Files with similar patterns (working correctly):
- `backend/routers/test_sessions.py` - Has proper video_id handling
- `backend/src/api/labjack_detection_api.py` - Has proper video_id handling

---

## Summary

**The Issue**: Missing `video_id` query parameter in frontend API calls causes multi-video sessions to return detection events from ALL videos instead of filtering by the currently active video.

**The Solution**:
1. Add `video_id` parameter to frontend API service methods
2. Pass current video ID from page components
3. Ensure `ground-truth-comparison` endpoint forwards `video_id` parameter

**Impact**: Critical for multi-video test sessions, no impact on single-video sessions.
