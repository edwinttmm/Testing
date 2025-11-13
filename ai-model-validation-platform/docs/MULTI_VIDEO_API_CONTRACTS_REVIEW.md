# Multi-Video API Contracts Review

**Status**: ⚠️ PARTIALLY IMPLEMENTED - Critical Gaps Identified
**Date**: 2025-10-30
**Reviewer**: Claude Code Architecture Analysis

---

## Executive Summary

The multi-video support has been **partially implemented** with significant gaps in API contracts between frontend and backend. While database schema is fully ready for multi-video sequences, several critical endpoints are missing or have incomplete parameter handling.

### Key Findings:
- ✅ Database schema fully supports multi-video (sequences, per-video results, timing)
- ✅ Backend enhanced HIL endpoint has `video_id` filter parameter
- ⚠️ Session creation lacks `has_video_sequence` response field
- ⚠️ Frontend API service missing `video_id` parameter in key methods
- ❌ Video start/end notification endpoints not implemented
- ❌ Frontend doesn't pass `video_id` to backend for filtering

---

## 1. Session Creation Endpoint

### Status: ⚠️ PARTIALLY COMPLIANT

**Endpoint**: `POST /api/test-sessions`

#### Request Schema (TestSessionCreate)
```python
# schemas.py - Lines 246-263
class TestSessionCreate(TestSessionBase):
    config: Optional[Dict[str, Any]] = None
```

**TestSessionBase includes:**
- ✅ `name: str`
- ✅ `project_id: str` (aliased as `projectId`)
- ✅ `video_id: Optional[str]` (single video)
- ✅ `video_ids: Optional[List[str]]` (multi-video)
- ✅ `tolerance_ms: Optional[int]`

**Database Model (TestSession):**
```python
# models.py - Lines 223-227
has_video_sequence = Column(Boolean, default=False, index=True)
sequence_id = Column(String(36), nullable=True, index=True)
sequence_metadata = Column(MutableDict.as_mutable(JSON), nullable=True)
max_latency_threshold_ms = Column(Float, nullable=True, index=True)
```

#### Response Schema
```python
# test_sessions.py - Lines 108-122
return {
    "id": db_session.id,
    "name": session.name,
    "project_id": session.project_id,
    "video_id": session.video_id,
    "status": db_session.status,
    "tolerance_ms": db_session.tolerance_ms,
    "created_at": db_session.created_at,
    # ...
}
```

#### ❌ MISSING FIELDS IN RESPONSE:
- `has_video_sequence` - Frontend needs this to determine if session is multi-video
- `sequence_id` - Required for tracking multi-video sequences
- `sequence_metadata` - Needed for video order and timing info

#### Frontend API Call:
```typescript
// api.ts - Lines 1638-1641
async createTestSession(testSession: TestSessionCreate): Promise<TestSession> {
  const response = await this.api.post<TestSession>('/api/test-sessions', testSession);
  return response.data;
}
```

**Frontend sends:**
- ✅ All required fields from TestSessionCreate schema

**Frontend expects to receive:**
- ❌ `has_video_sequence` field (not returned by backend)
- ❌ `sequence_id` field (not returned by backend)

---

## 2. Video Start Notification Endpoint

### Status: ❌ NOT IMPLEMENTED

**Expected Endpoint**: `POST /api/test-sessions/{session_id}/video/start`

#### Backend Implementation:
**NOT FOUND** - This endpoint does not exist in:
- `/backend/routers/test_sessions.py`
- `/backend/main.py` router registrations
- No matching route found

#### Frontend Implementation:
```typescript
// api.ts - Lines 1221-1237
async videoSequenceStarted(
  sequenceId: string,
  videoId: string,
  startedAt: number
): Promise<{ status: string; message: string }> {
  try {
    const response = await this.api.post(`/api/video-sequences/${sequenceId}/video-started`, {
      videoId: videoId,
      startedAt: startedAt,
      sequenceElapsedTime: 0
    });
    return response.data;
  } catch (error: unknown) {
    console.error('Failed to record video sequence start:', error);
    throw error;
  }
}
```

**Frontend calls:** `/api/video-sequences/{sequenceId}/video-started`
**Backend provides:** ❌ NOT FOUND

#### Required Backend Endpoint:
```python
# MISSING FROM: /backend/routers/test_sessions.py

@router.post("/api/video-sequences/{sequence_id}/video-started")
async def record_video_sequence_start(
    sequence_id: str,
    video_data: dict,  # {"videoId": str, "startedAt": float, "sequenceElapsedTime": float}
    db: Session = Depends(get_db)
):
    """Record when a video in a sequence starts playing"""
    # Implementation needed to update SequenceVideoResult
    pass
```

---

## 3. Video End Notification Endpoint

### Status: ❌ NOT IMPLEMENTED

**Expected Endpoint**: `POST /api/test-sessions/{session_id}/video/end`

#### Backend Implementation:
**NOT FOUND** - This endpoint does not exist

#### Frontend Implementation:
```typescript
// api.ts - Lines 1246-1264
async videoSequenceEnded(
  sequenceId: string,
  videoId: string,
  endedAt: number,
  duration: number
): Promise<{ status: string; message: string }> {
  try {
    const response = await this.api.post(`/api/video-sequences/${sequenceId}/video-ended`, {
      videoId: videoId,
      endedAt: endedAt,
      actualDuration: duration,
      sequenceElapsedTime: 0
    });
    return response.data;
  } catch (error: unknown) {
    console.error('Failed to record video sequence end:', error);
    throw error;
  }
}
```

**Frontend calls:** `/api/video-sequences/{sequenceId}/video-ended`
**Backend provides:** ❌ NOT FOUND

#### Required Backend Endpoint:
```python
# MISSING FROM: /backend/routers/test_sessions.py

@router.post("/api/video-sequences/{sequence_id}/video-ended")
async def record_video_sequence_end(
    sequence_id: str,
    video_data: dict,  # {"videoId": str, "endedAt": float, "actualDuration": float}
    db: Session = Depends(get_db)
):
    """Record when a video in a sequence ends playing"""
    # Implementation needed to update SequenceVideoResult with end time
    pass
```

---

## 4. Enhanced HIL Results Endpoint

### Status: ✅ CORRECTLY IMPLEMENTED

**Endpoint**: `GET /api/enhanced-hil/test-sessions/{session_id}/corrected-results`

#### Backend Implementation:
```python
# enhanced_hil_results_endpoints.py - Lines 228-233
@router.get("/test-sessions/{session_id}/corrected-results")
async def get_corrected_hil_results(
    session_id: str,
    video_id: Annotated[Optional[str], Query(description="Filter by video ID for multi-video sequences")] = None,
    db: Session = Depends(get_db)
):
```

**Backend accepts:**
- ✅ `session_id` (path parameter)
- ✅ `video_id` (optional query parameter) - **CRITICAL FOR MULTI-VIDEO**

#### Database Query with video_id Filter:
```python
# enhanced_hil_results_endpoints.py - Lines 261-270
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),
    selectinload(DetectionEvent.ground_truth_match),
    joinedload(DetectionEvent.test_session)
).filter(DetectionEvent.test_session_id == session_id)

# Add video_id filter if provided (for multi-video sequences)
if video_id is not None:
    detection_events_query = detection_events_query.filter(DetectionEvent.video_id == video_id)
```

**✅ Backend properly filters by video_id when provided**

#### Frontend Implementation:
```typescript
// api.ts - Lines 1149-1157
async getEnhancedHILResults(sessionId: string): Promise<any> {
  try {
    const response = await this.api.get(`/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`);
    return response.data;
  } catch (error: unknown) {
    console.warn(`Enhanced HIL results fetch failed for session ${sessionId}:`, error);
    throw error;
  }
}
```

**❌ Frontend does NOT pass `video_id` parameter**

#### Required Frontend Fix:
```typescript
// NEEDS UPDATE: api.ts
async getEnhancedHILResults(sessionId: string, videoId?: string): Promise<any> {
  try {
    const params = videoId ? { video_id: videoId } : {};
    const response = await this.api.get(
      `/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`,
      { params }
    );
    return response.data;
  } catch (error: unknown) {
    console.warn(`Enhanced HIL results fetch failed for session ${sessionId}:`, error);
    throw error;
  }
}
```

---

## 5. Detection Events Endpoint

### Status: ✅ CORRECTLY IMPLEMENTED (Backend) | ❌ MISSING (Frontend)

**Endpoint**: `GET /api/test-sessions/{session_id}/events`

#### Backend Implementation:
```python
# test_sessions.py - Lines 272-278
@router.get("/{session_id}/events")
async def get_session_detection_events(
    session_id: str,
    video_id: Annotated[Optional[str], Query(description="Filter by video ID for multi-video sequences")] = None,
    db: Session = Depends(get_db)
):
    """Get all detection events for a test session, optionally filtered by video_id"""
```

**Backend accepts:**
- ✅ `session_id` (path parameter)
- ✅ `video_id` (optional query parameter) - **CRITICAL FOR MULTI-VIDEO**

#### Database Query with video_id Filter:
```python
# test_sessions.py - Lines 298-300
# Add video_id filter if provided (for multi-video sequences)
if video_id:
    labjack_query = labjack_query.filter(DetectionEvent.video_id == video_id)
```

**✅ Backend properly filters by video_id when provided**

#### Frontend Implementation:
```typescript
// api.ts - Lines 1783-1809
async getTestSessionEvents(
  sessionId: string,
  limit: number = 1000,
  filters?: { video_id?: string; offset?: number }
): Promise<Record<string, unknown>[]> {
  try {
    const params: Record<string, string | number> = {
      limit
    };

    if (filters?.offset !== undefined) {
      params.offset = filters.offset;
    }

    if (filters?.video_id) {
      params.video_id = filters.video_id;
    }

    const response = await this.api.get(`/api/test-sessions/${sessionId}/events`, {
      params
    });
    // ...
  }
}
```

**✅ Frontend DOES accept and pass `video_id` parameter correctly**

#### Example Frontend Call:
```typescript
// CORRECT USAGE:
const events = await apiService.getTestSessionEvents(sessionId, 1000, {
  video_id: currentVideoId  // ✅ Filters by specific video
});
```

---

## 6. Detection Events API (Alternative Endpoint)

### Status: ✅ CORRECTLY IMPLEMENTED

**Endpoint**: `GET /api/test-sessions/{session_id}/detections`

#### Backend Implementation:
```python
# test_sessions.py - Lines 769-780
@router.get("/{session_id}/detections")
async def get_session_detections(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    start_time: Optional[float] = Query(None, description="Filter by start timestamp"),
    end_time: Optional[float] = Query(None, description="Filter by end timestamp"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    video_id: Optional[str] = Query(None, description="Filter by video ID for multi-video sequences"),
    db: Session = Depends(get_db)
):
```

**Backend accepts:**
- ✅ `session_id` (path parameter)
- ✅ `video_id` (optional query parameter)
- ✅ Additional filters: `start_time`, `end_time`, `vru_type`, `skip`, `limit`

#### Database Query with video_id Filter:
```python
# test_sessions.py - Lines 796-798
# Add video_id filter if provided (for multi-video sequences)
if video_id:
    query = query.filter(DetectionEvent.video_id == video_id)
```

**✅ Backend properly filters by video_id when provided**

#### Frontend Implementation:
```typescript
// api.ts - Lines 1766-1781
async getTestSessionDetections(
  sessionId: string,
  filters?: { video_id?: string }
): Promise<Record<string, unknown>[]> {
  try {
    const params = new URLSearchParams();
    if (filters?.video_id) {
      params.append('video_id', filters.video_id);
    }

    const url = `/api/test-sessions/${sessionId}/detections${params.toString() ? `?${params.toString()}` : ''}`;
    const response = await this.api.get(url);
    return response.data.detections || [];
  } catch (error: unknown) {
    // ...
  }
}
```

**✅ Frontend DOES accept and pass `video_id` parameter correctly**

---

## 7. Data Flow Analysis

### Frontend → Backend: Video Change Notifications

#### Current State: ❌ BROKEN

**Expected Flow:**
```
1. User selects Video 2 in multi-video sequence
2. Frontend calls: videoSequenceStarted(sequenceId, videoId, startTime)
3. Backend updates: SequenceVideoResult.video_start_time
4. Frontend displays: Video 2-specific results
```

**Actual Flow:**
```
1. User selects Video 2 in multi-video sequence
2. Frontend calls: /api/video-sequences/{sequenceId}/video-started ❌ 404 NOT FOUND
3. Backend: No update (endpoint doesn't exist)
4. Frontend: May show stale or mixed data
```

### Backend → Frontend: Multi-Video Results Structure

#### Current State: ⚠️ INCOMPLETE

**Backend Response Structure:**
```python
# enhanced_hil_results_endpoints.py returns:
{
    "session_id": "...",
    "detection_events": [...],  # Can be filtered by video_id
    "ground_truth_comparison": {
        "ground_truth_events_available": 10,
        "total_detections": 8,
        # Per-video breakdown NOT provided
    }
}
```

**Expected Multi-Video Response:**
```json
{
  "session_id": "abc123",
  "has_video_sequence": true,
  "sequence_results": {
    "total_videos": 3,
    "current_video_index": 1,
    "per_video_results": [
      {
        "video_id": "video1",
        "sequence_order": 0,
        "total_detections": 5,
        "passed_detections": 4,
        "avg_latency_ms": 75.2
      },
      {
        "video_id": "video2",
        "sequence_order": 1,
        "total_detections": 3,
        "passed_detections": 2,
        "avg_latency_ms": 82.1
      }
    ]
  },
  "detection_events": [...],  // Filtered by current video_id
  "ground_truth_comparison": {...}
}
```

**❌ Backend does NOT return `sequence_results` or `per_video_results`**

---

## 8. Critical Issues Summary

### ❌ Missing Backend Endpoints

1. **Video Start Notification**
   - Frontend calls: `/api/video-sequences/{sequenceId}/video-started`
   - Backend: Does not exist
   - Impact: Can't track when videos start in sequence

2. **Video End Notification**
   - Frontend calls: `/api/video-sequences/{sequenceId}/video-ended`
   - Backend: Does not exist
   - Impact: Can't track video completion or calculate actual duration

### ⚠️ Incomplete Response Schemas

3. **Session Creation Response**
   - Missing: `has_video_sequence`, `sequence_id`, `sequence_metadata`
   - Impact: Frontend can't determine if session is multi-video

4. **Enhanced HIL Results**
   - Missing: `sequence_results`, `per_video_results` array
   - Impact: No per-video breakdown for multi-video sessions

### ⚠️ Frontend Parameter Gaps

5. **Enhanced HIL Results Call**
   - Frontend method signature: `getEnhancedHILResults(sessionId: string)`
   - Backend accepts: `video_id` query parameter
   - Impact: Frontend can't filter by specific video in sequence

6. **Enhanced Ground Truth Comparison Call**
   - Same issue as above - no `video_id` parameter support

---

## 9. Recommended Fixes

### Priority 1: Critical Backend Endpoints

#### A. Video Start Notification
```python
# Add to: /backend/routers/test_sessions.py or /backend/routers/video_sequences.py

@router.post("/api/video-sequences/{sequence_id}/video-started")
async def record_video_sequence_start(
    sequence_id: str,
    video_data: dict,
    db: Session = Depends(get_db)
):
    """
    Record when a video in a sequence starts playing

    Request Body:
    {
        "videoId": "video-uuid",
        "startedAt": 1234567890.123,
        "sequenceElapsedTime": 0.0
    }
    """
    from models import SequenceVideoResult

    # Find the SequenceVideoResult for this video
    result = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id,
        SequenceVideoResult.video_id == video_data["videoId"]
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Video not found in sequence")

    # Update start time
    result.video_start_time = video_data["startedAt"]
    result.video_start_time_ns = str(int(video_data["startedAt"] * 1_000_000_000))
    result.video_status = "playing"

    db.commit()

    return {"status": "success", "message": f"Video {video_data['videoId']} start recorded"}
```

#### B. Video End Notification
```python
@router.post("/api/video-sequences/{sequence_id}/video-ended")
async def record_video_sequence_end(
    sequence_id: str,
    video_data: dict,
    db: Session = Depends(get_db)
):
    """
    Record when a video in a sequence ends playing

    Request Body:
    {
        "videoId": "video-uuid",
        "endedAt": 1234567890.123,
        "actualDuration": 30.5,
        "sequenceElapsedTime": 30.5
    }
    """
    from models import SequenceVideoResult

    result = db.query(SequenceVideoResult).filter(
        SequenceVideoResult.video_sequence_id == sequence_id,
        SequenceVideoResult.video_id == video_data["videoId"]
    ).first()

    if not result:
        raise HTTPException(status_code=404, detail="Video not found in sequence")

    # Update end time and duration
    result.video_end_time = video_data["endedAt"]
    result.video_end_time_ns = str(int(video_data["endedAt"] * 1_000_000_000))
    result.actual_duration_ms = video_data["actualDuration"] * 1000
    result.video_status = "completed"

    db.commit()

    return {"status": "success", "message": f"Video {video_data['videoId']} end recorded"}
```

### Priority 2: Response Schema Enhancements

#### C. Session Creation Response
```python
# Update: /backend/routers/test_sessions.py lines 108-122

return {
    "id": db_session.id,
    "name": session.name,
    "project_id": session.project_id,
    "video_id": session.video_id,
    "status": db_session.status,
    "tolerance_ms": db_session.tolerance_ms,
    "created_at": db_session.created_at,
    "started_at": db_session.started_at,
    "completed_at": db_session.completed_at,
    # ADD THESE FIELDS:
    "has_video_sequence": db_session.has_video_sequence,
    "sequence_id": db_session.sequence_id,
    "sequence_metadata": db_session.sequence_metadata,
    # ...
}
```

#### D. Enhanced HIL Results with Sequence Data
```python
# Update: /backend/src/api/enhanced_hil_results_endpoints.py

# Add after line 813 (session_stats calculation):
sequence_results = None
if session_result.has_video_sequence and session_result.sequence_id:
    from models import VideoTestSequence, SequenceVideoResult

    sequence = db.query(VideoTestSequence).filter(
        VideoTestSequence.id == session_result.sequence_id
    ).first()

    if sequence:
        video_results = db.query(SequenceVideoResult).filter(
            SequenceVideoResult.video_sequence_id == sequence.id
        ).order_by(SequenceVideoResult.sequence_order).all()

        sequence_results = {
            "total_videos": sequence.total_videos,
            "current_video_index": sequence.current_video_index,
            "completed_videos": sequence.completed_videos,
            "per_video_results": [
                {
                    "video_id": vr.video_id,
                    "sequence_order": vr.sequence_order,
                    "video_status": vr.video_status,
                    "total_detections": vr.actual_detection_count,
                    "passed_detections": vr.passed_detections,
                    "failed_detections": vr.failed_detections,
                    "avg_latency_ms": vr.avg_latency_ms,
                    "pass_rate_percent": vr.pass_rate_percent,
                    "validation_result": vr.validation_result
                }
                for vr in video_results
            ]
        }

# Then add to response dict (around line 893):
response = {
    "session_id": session_id,
    "validation_type": "enhanced_latency_with_timing_correction",
    # ADD THIS:
    "sequence_results": sequence_results,
    # ... rest of response
}
```

### Priority 3: Frontend Parameter Support

#### E. Enhanced HIL Results with video_id
```typescript
// Update: /frontend/src/services/api.ts lines 1149-1157

async getEnhancedHILResults(sessionId: string, videoId?: string): Promise<any> {
  try {
    const params = videoId ? { video_id: videoId } : {};
    const response = await this.api.get(
      `/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`,
      { params }
    );
    return response.data;
  } catch (error: unknown) {
    console.warn(`Enhanced HIL results fetch failed for session ${sessionId}:`, error);
    throw error;
  }
}
```

#### F. Enhanced Ground Truth Comparison with video_id
```typescript
// Update: /frontend/src/services/api.ts lines 1159-1167

async getEnhancedHILResultsWithGroundTruth(sessionId: string, videoId?: string): Promise<any> {
  try {
    const params = videoId ? { video_id: videoId } : {};
    const response = await this.api.get(
      `/api/enhanced-hil/test-sessions/${sessionId}/ground-truth-comparison`,
      { params }
    );
    return response.data;
  } catch (error: unknown) {
    console.warn(`Enhanced HIL ground truth comparison fetch failed for session ${sessionId}:`, error);
    throw error;
  }
}
```

---

## 10. Request/Response Examples

### ✅ Correct: Detection Events with video_id Filter

**Request:**
```bash
GET /api/test-sessions/abc123/events?video_id=video-uuid-2
```

**Response:**
```json
[
  {
    "event_id": "det1",
    "frame_number": 5,
    "timestamp": 0.208,
    "video_id": "video-uuid-2",
    "actual_latency_ms": 81.0,
    "validation_result": "pass"
  },
  {
    "event_id": "det2",
    "frame_number": 7,
    "timestamp": 0.289,
    "video_id": "video-uuid-2",
    "actual_latency_ms": 75.2,
    "validation_result": "pass"
  }
]
```

### ❌ Missing: Video Start Notification

**Expected Request:**
```bash
POST /api/video-sequences/seq123/video-started
Content-Type: application/json

{
  "videoId": "video-uuid-2",
  "startedAt": 1730307890.123,
  "sequenceElapsedTime": 30.5
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Video video-uuid-2 start recorded"
}
```

**Actual Result:**
```
404 Not Found
```

### ⚠️ Incomplete: Session Creation Response

**Request:**
```bash
POST /api/test-sessions
Content-Type: application/json

{
  "name": "Multi-Video Test",
  "projectId": "proj123",
  "videoIds": ["video1", "video2", "video3"],
  "toleranceMs": 100
}
```

**Current Response:**
```json
{
  "id": "session123",
  "name": "Multi-Video Test",
  "project_id": "proj123",
  "video_id": null,
  "status": "created",
  "tolerance_ms": 100
  // ❌ Missing: has_video_sequence, sequence_id, sequence_metadata
}
```

**Expected Response:**
```json
{
  "id": "session123",
  "name": "Multi-Video Test",
  "project_id": "proj123",
  "video_id": null,
  "status": "created",
  "tolerance_ms": 100,
  "has_video_sequence": true,
  "sequence_id": "seq456",
  "sequence_metadata": {
    "video_ids": ["video1", "video2", "video3"],
    "total_videos": 3,
    "sequence_order": [
      {"video_id": "video1", "order": 0, "duration_ms": 30000},
      {"video_id": "video2", "order": 1, "duration_ms": 25000},
      {"video_id": "video3", "order": 2, "duration_ms": 35000}
    ]
  }
}
```

---

## 11. Validation Checklist

### Backend API Endpoints
- [x] Session creation accepts `video_ids` array
- [ ] **MISSING** Session creation returns `has_video_sequence`
- [ ] **MISSING** Session creation returns `sequence_id`
- [ ] **MISSING** Session creation returns `sequence_metadata`
- [x] Detection events endpoint accepts `video_id` filter
- [x] Enhanced HIL results accepts `video_id` filter
- [ ] **MISSING** Video start notification endpoint
- [ ] **MISSING** Video end notification endpoint
- [ ] **MISSING** Enhanced HIL returns `sequence_results`
- [ ] **MISSING** Enhanced HIL returns `per_video_results`

### Frontend API Service
- [x] `createTestSession` sends `video_ids` array
- [ ] **MISSING** `getEnhancedHILResults` accepts `video_id` parameter
- [ ] **MISSING** `getEnhancedHILResultsWithGroundTruth` accepts `video_id` parameter
- [x] `getTestSessionEvents` accepts `video_id` filter
- [x] `getTestSessionDetections` accepts `video_id` filter
- [x] `videoSequenceStarted` implemented (but endpoint missing)
- [x] `videoSequenceEnded` implemented (but endpoint missing)

### Data Contracts
- [x] Database schema supports multi-video sequences
- [x] `VideoTestSequence` model exists
- [x] `SequenceVideoResult` model exists
- [x] `DetectionEvent.sequence_video_result_id` foreign key exists
- [x] `DetectionEvent.video_id` foreign key exists
- [ ] **INCOMPLETE** API responses match frontend TypeScript interfaces

---

## 12. Impact Assessment

### High Impact Issues (Critical)
1. **Missing Video Start/End Endpoints** - Prevents accurate per-video timing
2. **Missing `has_video_sequence` in Response** - Frontend can't detect multi-video mode
3. **Missing `sequence_results` Data** - No per-video breakdown in UI

### Medium Impact Issues (Important)
4. **Frontend Missing `video_id` Parameters** - Can't filter results by video
5. **Missing `sequence_id` in Response** - Can't link to sequence data

### Low Impact Issues (Nice to Have)
6. **Missing `sequence_metadata` in Response** - Less critical, can be fetched separately

---

## 13. Conclusion

The multi-video support is **60% implemented** with critical gaps:

**Working:**
- ✅ Database schema complete and indexed
- ✅ Backend filtering by `video_id` works
- ✅ Frontend has detection event filtering

**Broken:**
- ❌ Video start/end notification endpoints don't exist
- ❌ Session creation response missing multi-video fields
- ❌ Enhanced HIL results don't include per-video breakdown
- ❌ Frontend doesn't pass `video_id` to enhanced endpoints

**Risk Level**: 🔴 HIGH - Multi-video sequences won't work correctly without fixes

**Recommended Action**: Implement Priority 1 and Priority 2 fixes before deploying multi-video features to production.
