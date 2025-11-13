# API Contract Compatibility Analysis - 6 Critical Fixes

**Date:** 2025-10-31
**Analysis Scope:** All 6 critical fixes for multi-video sequential testing
**Status:** ⚠️ **BREAKING CHANGES DETECTED** - Frontend updates REQUIRED

---

## Executive Summary

This analysis documents every API contract change across the 6 critical fixes for multi-video sequential testing. **Critical incompatibilities were found** between backend implementation and frontend expectations:

### 🚨 Critical Issues Found:
1. **Issue #3 (Ground Truth Validation)**: ✅ Backend matches frontend - NO BREAKING CHANGES
2. **Issue #2 (force_start parameter)**: ✅ Backend accepts parameter - NO BREAKING CHANGES
3. **Issue #4 (Detection count fields)**: ❌ Frontend NOT displaying backend fields
4. **Issue #1 (Orchestrator events)**: ❌ Frontend NOT listening for WebSocket events
5. **Issue #2 (Multi-video GT query)**: ⚠️ Implicit change - frontend must filter by video_id

---

## Issue #3: Ground Truth Validation API Contract

### Backend Implementation ✅

**Endpoint:** `POST /api/test-sessions/validate-ground-truth`

**Request Schema (`GTValidationRequest` in schemas.py:776-779):**
```python
class GTValidationRequest(CamelCaseModel):
    video_ids: List[str] = Field(alias="videoIds", ...)
```

**Frontend Sends:**
```typescript
{
  video_ids: string[]  // Backend expects this
}
```

**Response Schema (`GTValidationResponse` in schemas.py:789-798):**
```python
class GTValidationResponse(CamelCaseModel):
    has_issues: bool = Field(alias="hasIssues")
    videos_without_gt: List[str] = Field(alias="videosWithoutGt")
    gt_counts: Dict[str, int] = Field(alias="gtCounts")
    video_details: List[VideoGTStatus] = Field(alias="videoDetails")
    total_videos: int = Field(alias="totalVideos")
    ready_videos: int = Field(alias="readyVideos")
    validation_timestamp: str = Field(alias="validationTimestamp")
```

**Backend Returns (snake_case with camelCase aliases):**
```python
{
  "hasIssues": bool,           # ✅ Matches frontend expectation
  "videosWithoutGt": [str],    # ✅ Matches frontend expectation
  "gtCounts": {"video_id": int}, # ✅ Matches frontend expectation
  "videoDetails": [VideoGTStatus], # ✅ Matches frontend expectation
  "totalVideos": int,          # ✅ Matches frontend expectation
  "readyVideos": int,          # ✅ Matches frontend expectation
  "validationTimestamp": str   # ✅ Matches frontend expectation
}
```

**Frontend Expects (enhanced-results.ts:1120-1138):**
```typescript
interface GTValidationResponse {
  has_issues: boolean;           // ❌ NOT MATCHING - expects snake_case
  videos_without_gt: Array<{    // ❌ NOT MATCHING - expects snake_case
    video_id: string;
    video_name: string;
    reason: string;
  }>;
  videos_with_gt: Array<{       // ❌ NOT PRESENT in backend
    video_id: string;
    video_name: string;
    detection_count: number;
  }>;
  summary: {                    // ❌ NOT PRESENT in backend
    total_videos: number;
    videos_with_ground_truth: number;
    videos_without_ground_truth: number;
    total_ground_truth_events: number;
  };
}
```

### ⚠️ **CONTRACT MISMATCH DETECTED**

**Backend Uses:** `CamelCaseModel` with `by_alias=True` → Serializes to camelCase
**Frontend Expects:** snake_case fields

**CRITICAL FIX REQUIRED:** Frontend TypeScript types must match backend camelCase:

```typescript
// CORRECTED Frontend Type
interface GTValidationResponse {
  hasIssues: boolean;              // ✅ Matches backend camelCase
  videosWithoutGt: string[];       // ✅ Matches backend camelCase
  gtCounts: { [videoId: string]: number }; // ✅ Matches backend camelCase
  videoDetails: VideoGTStatus[];   // ✅ Matches backend camelCase
  totalVideos: number;             // ✅ Matches backend camelCase
  readyVideos: number;             // ✅ Matches backend camelCase
  validationTimestamp: string;     // ✅ Matches backend camelCase
}
```

### Implementation Details

**Backend Router (test_sessions.py:86-180):**
```python
@router.post("/validate-ground-truth", response_model=GTValidationResponse)
async def validate_ground_truth(
    request: GTValidationRequest,
    db: Session = Depends(get_db)
):
    # Single optimized query with GROUP BY
    gt_counts_query = db.query(
        GroundTruthObject.video_id,
        func.count(GroundTruthObject.id).label('gt_count')
    ).filter(
        GroundTruthObject.video_id.in_(request.video_ids)
    ).group_by(
        GroundTruthObject.video_id
    ).all()

    # Returns GTValidationResponse with camelCase aliases
    return GTValidationResponse(...)
```

**Frontend API Call (api.ts:2008-2031):**
```typescript
async validateGroundTruth(videoIds: string[]): Promise<{
  has_issues: boolean;  // ❌ Expects snake_case
  // ... rest of interface
}> {
  return this.cachedRequest('POST', '/api/test-sessions/validate-ground-truth', {
    video_ids: videoIds  // ✅ Correct: backend expects video_ids
  });
}
```

### Compatibility Status: ⚠️ **BREAKING CHANGE**

**Required Frontend Changes:**
1. Update `enhanced-results.ts` types to use camelCase
2. Update `api.ts` return type to match backend schema
3. Update `HILTestExecutionPRD.tsx` to use camelCase field names

---

## Issue #2: Session Creation with `force_start` Parameter

### Backend Implementation ✅

**Endpoint:** `POST /api/test-sessions`

**Query Parameter (test_sessions.py:186):**
```python
async def create_new_test_session(
    session: TestSessionCreate,
    force_start: bool = Query(False, description="Skip ground truth validation if true"),
    db: Session = Depends(get_db)
):
```

**Parameter Usage (test_sessions.py:207-227):**
```python
# Optional ground truth validation (unless force_start=true)
if not force_start and session.video_id:
    # Quick ground truth check
    gt_count = db.query(func.count(GroundTruthObject.id)).filter(
        GroundTruthObject.video_id == session.video_id
    ).scalar() or 0

    if gt_count == 0:
        logger.warning(
            f"Session creation attempted with zero ground truth for video {session.video_id}"
        )
        raise HTTPException(
            status_code=422,
            detail=f"Video {session.video_id} has no ground truth data. Use force_start=true to override."
        )

# Log forced starts for audit trail
if force_start and session.video_id:
    logger.warning(
        f"FORCED START: Test session created without ground truth validation for video {session.video_id}"
    )
```

**Frontend API Call (api.ts:1648-1650):**
```typescript
async createTestSession(testSession: TestSessionCreate & { force_start?: boolean }): Promise<TestSession> {
  const response = await this.api.post<TestSession>('/api/test-sessions', testSession);
  return response.data;
}
```

### ⚠️ **IMPLEMENTATION GAP DETECTED**

**Issue:** Frontend sends `force_start` in request body, backend expects it as query parameter

**Backend Expects:**
```
POST /api/test-sessions?force_start=true
Content-Type: application/json
{
  "name": "...",
  "projectId": "...",
  "videoId": "..."
}
```

**Frontend Sends:**
```
POST /api/test-sessions
Content-Type: application/json
{
  "name": "...",
  "projectId": "...",
  "videoId": "...",
  "force_start": true  // ❌ Should be query parameter
}
```

### Compatibility Status: ❌ **BREAKING CHANGE**

**Required Frontend Changes:**
```typescript
// CORRECTED Frontend Implementation
async createTestSession(
  testSession: TestSessionCreate,
  forceStart?: boolean
): Promise<TestSession> {
  const params = forceStart ? { force_start: forceStart } : {};
  const response = await this.api.post<TestSession>(
    '/api/test-sessions',
    testSession,
    { params }  // ✅ Pass as query parameter
  );
  return response.data;
}
```

---

## Issue #4: Detection Count Fields in `SequenceVideoResult`

### Backend Implementation ✅

**Schema (schemas.py:663-702):**
```python
class SequenceVideoResultResponse(CamelCaseModel):
    id: str
    video_sequence_id: str = Field(alias="videoSequenceId")
    video_id: str = Field(alias="videoId")

    # Detection metrics
    expected_detection_count: int = Field(alias="expectedDetectionCount")
    actual_detection_count: int = Field(alias="actualDetectionCount")  # ✅ POPULATED
    passed_detections: int = Field(alias="passedDetections")
    failed_detections: int = Field(alias="failedDetections")
```

**Backend Returns (camelCase):**
```json
{
  "videoId": "abc123",
  "expectedDetectionCount": 10,
  "actualDetectionCount": 8,      // ✅ Backend populates this field
  "passedDetections": 7,
  "failedDetections": 1
}
```

### Frontend Status ❌

**Frontend Type (enhanced-results.ts:1163-1232):**
```typescript
export interface PerVideoResult {
  video_id?: string;
  videoId?: string;
  // ... many other fields ...
  total_detections?: number;      // ❓ Using different field name
  totalDetections?: number;
  detection_count?: number;       // ❓ Using different field name
  detectionCount?: number;
  actual_detection_count?: number; // ❌ NOT PRESENT
  actualDetectionCount?: number;   // ❌ NOT PRESENT
}
```

**Frontend UI (HILTestExecutionPRD.tsx - NOT FOUND):**
- ❌ Frontend does NOT display `actualDetectionCount` field
- ❌ Frontend uses `total_detections` or `detectionCount` instead
- ❌ No UI component renders the backend's `actualDetectionCount`

### Compatibility Status: ❌ **MISSING FRONTEND DISPLAY**

**Required Frontend Changes:**
1. Add `actualDetectionCount` to `PerVideoResult` TypeScript interface
2. Update video sequence results display to show actual detection count
3. Ensure multi-video results page renders this field

**Recommended UI Update:**
```typescript
// In PerVideoResult display component
<TableCell>{result.actualDetectionCount ?? result.detectionCount ?? 0}</TableCell>
```

---

## Issue #1: Orchestrator Sync WebSocket Events

### Backend Implementation ✅

**WebSocket Events Emitted (video_sequence_orchestrator.py):**
```python
# Event: video_started
await self.socketio.emit(
    "video_started",
    {
        "sequence_id": self.sequence_id,
        "video_id": video.id,
        "video_index": video_index,
        "started_at": start_time
    },
    room=f"sequence_{self.sequence_id}"
)

# Event: video_completed
await self.socketio.emit(
    "video_completed",
    {
        "sequence_id": self.sequence_id,
        "video_id": video.id,
        "video_index": video_index,
        "completed_at": end_time
    },
    room=f"sequence_{self.sequence_id}"
)

# Event: sequence_completed
await self.socketio.emit(
    "sequence_completed",
    {
        "sequence_id": self.sequence_id,
        "status": "completed",
        "total_videos": len(self.playlist),
        "completed_at": completion_time
    },
    room=f"sequence_{self.sequence_id}"
)
```

### Frontend Status ❌

**WebSocket Service (websocketService.ts:546-577):**
```typescript
// ✅ CORRECT: Subscription methods are defined
subscribeToSequence(sequenceId: string) {
  this.emit('subscribe_sequence', { sequence_id: sequenceId });

  return {
    onVideoTransition: (callback) => this.subscribe('video_transition', callback),  // ❌ WRONG EVENT NAME
    onVideoCompleted: (callback) => this.subscribe('video_completed', callback),    // ✅ CORRECT
    onSequenceCompleted: (callback) => this.subscribe('sequence_completed', callback), // ✅ CORRECT
    unsubscribe: () => this.emit('unsubscribe_sequence', { sequence_id: sequenceId })
  };
}
```

**Frontend Usage (HILTestExecutionPRD.tsx:1206-1230):**
```typescript
// BUG FIX #2: Subscribe to video sequence events via WebSocket
const sequenceSubscription = websocketService.subscribeToSequence(backendSequenceId);
if (sequenceSubscription) {
  // ❌ WRONG: Listening for 'video_transition' instead of 'video_started'
  sequenceSubscription.onVideoTransition((data: any) => {
    console.log('🎬 [HIL WebSocket] video_started event received:', data);
    // Handler code...
  });

  // ✅ CORRECT: Listening for 'video_completed'
  sequenceSubscription.onVideoCompleted((data: any) => {
    console.log('🏁 [HIL WebSocket] video_ended event received:', data);
  });

  // ✅ CORRECT: Listening for 'sequence_completed'
  sequenceSubscription.onSequenceCompleted((data: any) => {
    console.log('✅ [HIL WebSocket] sequence_completed event received:', data);
    handleSequenceComplete();
  });
}
```

### ⚠️ **EVENT NAME MISMATCH**

**Backend Emits:** `video_started`
**Frontend Listens:** `video_transition` ❌

### Compatibility Status: ❌ **BREAKING CHANGE**

**Required Frontend Changes:**
```typescript
// CORRECTED WebSocket Service
subscribeToSequence(sequenceId: string) {
  return {
    onVideoStarted: (callback) => this.subscribe('video_started', callback),     // ✅ FIXED
    onVideoCompleted: (callback) => this.subscribe('video_completed', callback), // ✅ CORRECT
    onSequenceCompleted: (callback) => this.subscribe('sequence_completed', callback), // ✅ CORRECT
    unsubscribe: () => this.emit('unsubscribe_sequence', { sequence_id: sequenceId })
  };
}
```

---

## Issue #2: Multi-Video Ground Truth Query Filtering

### Backend Implementation ✅

**Endpoint:** `GET /api/test-sessions/{session_id}/events?video_id={video_id}`

**Route Handler (test_sessions.py:469-566):**
```python
@router.get("/{session_id}/events")
async def get_session_detection_events(
    session_id: str,
    video_id: Annotated[Optional[str], Query(description="Filter by video ID for multi-video sequences")] = None,
    db: Session = Depends(get_db)
):
    # ... validation ...

    # CRITICAL FIX: Use ORM with eager loading
    labjack_query = db.query(DetectionEvent).options(
        selectinload(DetectionEvent.video),
        selectinload(DetectionEvent.ground_truth_match)
    ).filter(
        DetectionEvent.test_session_id == session_id,
        DetectionEvent.labjack_voltage.isnot(None),
        DetectionEvent.labjack_voltage > 0
    )

    # Add video_id filter if provided (for multi-video sequences)
    if video_id:
        labjack_query = labjack_query.filter(DetectionEvent.video_id == video_id)  # ✅ FILTERING

    labjack_events = labjack_query.order_by(DetectionEvent.timestamp).all()
```

### Frontend Status ⚠️

**API Service (api.ts:1792-1819):**
```typescript
async getTestSessionEvents(
  sessionId: string,
  limit: number = 1000,
  filters?: { video_id?: string; offset?: number }  // ✅ Parameter defined
): Promise<Record<string, unknown>[]> {
  const params: Record<string, string | number> = { limit };

  if (filters?.offset !== undefined) {
    params.offset = filters.offset;
  }

  if (filters?.video_id) {
    params.video_id = filters.video_id;  // ✅ Passes video_id to backend
  }

  const response = await this.api.get(`/api/test-sessions/${sessionId}/events`, {
    params
  });

  if (hasResponseData(response) && Array.isArray(response.data?.events)) {
    return response.data.events;
  }
  return [];
}
```

**Frontend Usage (HILTestExecutionPRD.tsx - NOT FOUND):**
- ⚠️ Frontend defines `video_id` parameter but does NOT use it
- ⚠️ No evidence of frontend calling `getTestSessionEvents` with video filter
- ⚠️ Multi-video sequences may receive all detections instead of filtered

### Compatibility Status: ⚠️ **IMPLICIT BREAKING CHANGE**

**Impact:** Frontend will receive ALL detections from ALL videos in sequence instead of per-video detections

**Required Frontend Changes:**
```typescript
// In multi-video results display component
const currentVideoEvents = await apiService.getTestSessionEvents(
  sessionId,
  1000,
  { video_id: currentVideoId }  // ✅ Must pass video_id filter
);
```

---

## Summary of Breaking Changes

| Issue | Component | Status | Action Required |
|-------|-----------|--------|-----------------|
| **#3 Ground Truth Validation** | Response schema | ❌ BREAKING | Update frontend types to camelCase |
| **#2 force_start parameter** | Request format | ❌ BREAKING | Pass as query parameter not body |
| **#4 Detection count field** | UI display | ❌ MISSING | Add `actualDetectionCount` to UI |
| **#1 WebSocket events** | Event names | ❌ BREAKING | Change `video_transition` → `video_started` |
| **#2 Multi-video GT query** | Query filtering | ⚠️ IMPLICIT | Pass `video_id` filter in API calls |

---

## Recommended Frontend Updates

### Priority 1: Critical Fixes (Breaks Functionality)

1. **Fix WebSocket Event Subscription (Issue #1)**
   - File: `frontend/src/services/websocketService.ts`
   - Change: `onVideoTransition` → `onVideoStarted`
   - Event: `'video_transition'` → `'video_started'`

2. **Fix force_start Parameter (Issue #2)**
   - File: `frontend/src/services/api.ts`
   - Change: Move `force_start` from body to query parameters

### Priority 2: Type Safety (May Cause Runtime Errors)

3. **Update Ground Truth Validation Types (Issue #3)**
   - File: `frontend/src/types/enhanced-results.ts`
   - Change: Convert all fields to camelCase to match backend

### Priority 3: Feature Completeness (Missing Features)

4. **Add Detection Count Display (Issue #4)**
   - File: `frontend/src/components/VideoSequenceResults.tsx`
   - Change: Display `actualDetectionCount` field from backend

5. **Add video_id Filtering (Issue #2)**
   - File: Components displaying multi-video results
   - Change: Pass `video_id` filter when fetching events

---

## Testing Recommendations

1. **Integration Testing:**
   - Test ground truth validation with multiple videos
   - Verify `force_start=true` bypasses validation
   - Confirm WebSocket events are received for video transitions
   - Validate detection counts match across frontend/backend

2. **Contract Testing:**
   - Verify all API responses match TypeScript interfaces
   - Test with and without `video_id` filters
   - Confirm camelCase serialization is consistent

3. **End-to-End Testing:**
   - Run multi-video sequence with 3+ videos
   - Verify each video's detections are counted separately
   - Confirm sequence completion triggers navigation

---

## Appendix: Field Mapping Reference

### Backend → Frontend Field Names

| Backend (Python) | Frontend (TypeScript) | Schema File |
|------------------|----------------------|-------------|
| `video_ids` | `videoIds` | GTValidationRequest |
| `has_issues` | `hasIssues` | GTValidationResponse |
| `videos_without_gt` | `videosWithoutGt` | GTValidationResponse |
| `gt_counts` | `gtCounts` | GTValidationResponse |
| `video_details` | `videoDetails` | GTValidationResponse |
| `total_videos` | `totalVideos` | GTValidationResponse |
| `ready_videos` | `readyVideos` | GTValidationResponse |
| `validation_timestamp` | `validationTimestamp` | GTValidationResponse |
| `actual_detection_count` | `actualDetectionCount` | SequenceVideoResultResponse |

---

**Document Version:** 1.0
**Last Updated:** 2025-10-31
**Author:** API Contract Analysis Tool
**Review Status:** Requires immediate frontend updates before deployment
