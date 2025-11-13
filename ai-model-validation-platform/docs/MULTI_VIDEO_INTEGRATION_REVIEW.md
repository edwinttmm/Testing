# Multi-Video Sequence HIL Testing Implementation Review

**Review Date:** 2025-09-30
**Reviewer:** Code Review Agent
**Implementation Branch:** v8
**Review Status:** COMPREHENSIVE ANALYSIS COMPLETE

---

## Executive Summary

The multi-video sequence HIL testing implementation represents a **substantial and well-architected** addition to the platform. The implementation demonstrates **strong technical foundations** with dynamic timing management, per-video result tracking, and comprehensive database schema design. However, **critical integration gaps** remain that prevent the system from functioning as a complete end-to-end solution for unattended sequential testing.

### Overall Assessment

| Category | Status | Grade |
|----------|--------|-------|
| **Architecture** | ✅ Excellent | A+ |
| **Database Schema** | ✅ Complete | A |
| **Backend API** | ⚠️ Functional but incomplete | B+ |
| **Frontend Integration** | ⚠️ Partial | C+ |
| **Timing Synchronization** | ⚠️ Needs work | C |
| **Testing Coverage** | ⚠️ Limited | C |
| **Documentation** | ✅ Excellent | A |
| **Production Readiness** | ❌ Not ready | D |

**Overall Grade: B- (Solid foundation, incomplete execution)**

---

## 1. What Works Correctly ✅

### 1.1 Database Schema (Grade: A)

**Strengths:**
- ✅ Comprehensive three-tier timing system (sequence → video → detection)
- ✅ Proper foreign key relationships with CASCADE deletes
- ✅ Well-indexed for query performance (13+ indexes)
- ✅ Backward compatible with single-video sessions
- ✅ Rich metadata storage with JSON fields
- ✅ Nanosecond precision timing fields for HIL validation

**Evidence:**
```python
# models.py - VideoTestSequence
- sequence_start_time: Float  # Unix timestamp
- sequence_start_time_ns: String  # Nanosecond precision
- Per-video tracking with video_play_offset_ms

# models.py - SequenceVideoResult
- video_start_time, video_end_time (dynamic tracking)
- Detection metrics: passed/failed/expected counts
- Latency statistics: avg/max/min/pass_rate

# models.py - DetectionEvent enhancements
- video_relative_timestamp: Float  # Time since video start
- sequence_timestamp: Float  # Time since sequence start
- correlation_method: String  # 'timestamp' or 'frame_number'
```

**Database Migration:**
- ✅ Migration file exists: `add_video_sequence_schema.py`
- ✅ Includes rollback capability
- ✅ Automatic verification of schema changes
- ✅ Safe for production deployment

### 1.2 Backend API Structure (Grade: B+)

**Strengths:**
- ✅ RESTful API design with clear endpoints
- ✅ Comprehensive request/response schemas with camelCase aliases
- ✅ Proper error handling and validation
- ✅ Detection correlation logic based on timing windows
- ✅ LabjJack monitoring integration hooks

**API Endpoints Implemented:**
```
POST   /api/video-sequences/start           ✅ Working
POST   /api/video-sequences/{id}/video-started   ✅ Working
POST   /api/video-sequences/{id}/video-ended     ✅ Working
GET    /api/video-sequences/{id}/status          ✅ Working
GET    /api/video-sequences/{id}/results         ✅ Working
POST   /api/video-sequences/{id}/detection       ✅ Working
POST   /api/video-sequences/{id}/stop            ✅ Working
GET    /api/video-sequences/health               ✅ Working
```

**Detection Correlation (Lines 863-880 in video_sequence_testing.py):**
```python
# Correctly identifies active video based on timing windows
for video_id, timing_info in video_timing.items():
    started_at = timing_info.get("started_at")
    ended_at = timing_info.get("ended_at")

    if started_at:
        if ended_at:
            if started_at <= request.unix_timestamp <= ended_at:
                active_video_id = video_id
                video_relative_timestamp = request.unix_timestamp - started_at
```

### 1.3 Documentation (Grade: A)

**Strengths:**
- ✅ Comprehensive schema documentation (MULTI_VIDEO_SEQUENCE_SCHEMA_DOCUMENTATION.md)
- ✅ Implementation summary with usage examples
- ✅ Quick reference guides
- ✅ API documentation with request/response examples
- ✅ Clear timing architecture explanations

---

## 2. Critical Issues Requiring Fixes 🔴

### 2.1 Frontend-Backend Integration Gap (CRITICAL)

**Issue:** The frontend SequentialVideoPlayer and HILTestExecutionPRD page are **NOT integrated** with the backend video sequence API.

**Evidence:**

**Frontend (SequentialVideoPlayer.tsx):**
```typescript
// Lines 88-102: Local state management only
const handleVideoStart = useCallback((videoIndex: number) => {
  const timestamp = performance.now();

  if (videoIndex === 0 && !sequenceStartTime) {
    setSequenceStartTime(timestamp);
  }

  setVideoStartTime(timestamp);

  // ❌ NO API call to backend's /video-started endpoint
  onVideoStart?.({
    videoIndex,
    timestamp,
    sequenceElapsedTime: sequenceStartTime ? timestamp - sequenceStartTime : 0
  });
}, [sequenceId, sequenceStartTime]);
```

**Backend Expects (video_sequence_testing.py, lines 374-466):**
```python
@router.post("/{sequence_id}/video-started", status_code=200)
async def record_video_started(
    sequence_id: str,
    request: VideoStartedRequest,  # ❌ Never called from frontend
    db: Session = Depends(get_db)
):
    # Records video_start_time in database for detection correlation
```

**Impact:**
- ❌ Video start times are NOT recorded in database
- ❌ Detection correlation cannot work correctly (backend has no video timing data)
- ❌ Per-video results cannot be calculated accurately
- ❌ Sequence timing analysis is impossible

**Recommendation:**
```typescript
// SequentialVideoPlayer.tsx - Add API integration
const handleVideoStart = useCallback(async (videoIndex: number) => {
  const timestamp = performance.now();
  const unixTime = Date.now() / 1000;

  // Record in backend
  try {
    await apiService.recordVideoStarted(sequenceId, {
      videoId: currentVideo.id,
      startedAt: unixTime,
      clientTimestamp: new Date().toISOString()
    });
  } catch (error) {
    console.error('Failed to record video start:', error);
  }

  // Update local state
  setVideoStartTime(timestamp);
  onVideoStart?.({ videoIndex, timestamp });
}, [sequenceId, currentVideo]);
```

### 2.2 Timing Synchronization Issues (HIGH PRIORITY)

**Issue:** Multiple timing reference points causing confusion and potential drift.

**Evidence:**

**Frontend uses `performance.now()`:**
```typescript
// SequentialVideoPlayer.tsx:57-58
const [sequenceStartTime, setSequenceStartTime] = useState<number | null>(null);
const [videoStartTime, setVideoStartTime] = useState<number | null>(null);

// performance.now() returns milliseconds since page load
```

**Backend expects Unix timestamps:**
```python
# video_sequence_testing.py:124
started_at: float = Field(..., description="Unix timestamp when video started (seconds)")

# Detection correlation uses Unix timestamps:
if started_at <= request.unix_timestamp <= ended_at:
    active_video_id = video_id
```

**Impact:**
- ❌ Timing mismatch between frontend and backend
- ❌ Detection correlation will fail (comparing performance.now() values to Unix timestamps)
- ❌ Video-relative timestamps will be incorrect

**Recommendation:**
1. **Frontend:** Use `Date.now() / 1000` for Unix timestamps
2. **Keep performance.now()** for UI display only (elapsed time)
3. **Send Unix timestamps** to backend for correlation

```typescript
const handleVideoStart = useCallback(async (videoIndex: number) => {
  const perfTimestamp = performance.now();  // For UI
  const unixTimestamp = Date.now() / 1000;  // For backend

  await apiService.recordVideoStarted(sequenceId, {
    videoId: currentVideo.id,
    startedAt: unixTimestamp,  // ✅ Unix timestamp
    clientTimestamp: new Date().toISOString()
  });

  setVideoStartTime(unixTimestamp);  // Store Unix time
}, []);
```

### 2.3 Missing Video Transition Logic (HIGH PRIORITY)

**Issue:** No automatic video advancement logic in HILTestExecutionPRD.

**Evidence:**

**HILTestExecutionPRD.tsx (Line 1338):**
```typescript
const handleVideoEnded = async () => {
  console.log('🎬 Video ended');

  // ❌ No logic to:
  // 1. Record video end time in backend
  // 2. Request next video from backend
  // 3. Advance to next video in sequence
  // 4. Handle sequence completion
};
```

**Backend Provides Next Video Info (video_sequence_testing.py:469-596):**
```python
@router.post("/{sequence_id}/video-ended", response_model=VideoEndedResponse)
async def record_video_ended(...):
    return VideoEndedResponse(
        next_video=next_video_info,  # Contains next video ID and metadata
        sequence_complete=sequence_complete  # Boolean flag
    )
```

**Impact:**
- ❌ Manual video advancement required (not unattended)
- ❌ Per-video results not calculated
- ❌ Sequence never completes automatically

**Recommendation:**
```typescript
const handleVideoEnded = async () => {
  console.log('🎬 Video ended');

  try {
    // Record video end in backend
    const result = await apiService.recordVideoEnded(sequenceId, {
      videoId: currentVideoId,
      endedAt: Date.now() / 1000,
      actualDuration: videoElement.duration
    });

    if (result.sequenceComplete) {
      // Sequence finished - navigate to results
      setTestRunning(false);
      navigate(`/hil-results/${currentSession.id}`);
    } else if (result.nextVideo) {
      // Advance to next video
      setCurrentVideoIdx(result.nextVideo.sequenceIndex);
      setCurrentVideoId(result.nextVideo.videoId);
      // Video player will auto-play next video
    }
  } catch (error) {
    console.error('Failed to record video end:', error);
  }
};
```

### 2.4 LabJack Detection Recording Gap (HIGH PRIORITY)

**Issue:** No integration between LabJack monitoring and video sequence API.

**Evidence:**

**Current LabJack monitoring (dedicated_labjack_monitor.py):**
```python
# Records detections to DetectionEvent table directly
detection = DetectionEvent(
    test_session_id=session_id,
    video_id=video_id,  # ❌ Static video_id, doesn't track current video
    timestamp=time.time()
)
```

**Video Sequence API Expects (video_sequence_testing.py:815-934):**
```python
@router.post("/{sequence_id}/detection", response_model=DetectionEventResponse)
async def record_detection_event(
    sequence_id: str,
    request: DetectionEventRequest,
    db: Session
):
    # Correlates detection to currently active video
    # Calculates video_relative_timestamp
    # Stores sequence context
```

**Impact:**
- ❌ Detections not correlated to correct video in sequence
- ❌ Video-relative timestamps not calculated
- ❌ Per-video detection counts incorrect

**Recommendation:**
1. Modify LabJack monitor to call `/video-sequences/{id}/detection` instead of direct DB write
2. Pass sequence_id to monitoring service
3. Let backend handle video correlation

```python
# Modified LabJack monitor integration
async def on_labjack_detection(timestamp: float, signal_value: float):
    if sequence_id:
        # Use video sequence API
        await http_client.post(
            f"/api/video-sequences/{sequence_id}/detection",
            json={
                "unixTimestamp": timestamp,
                "signalType": "GPIO",
                "channel": 0,
                "signalValue": signal_value
            }
        )
    else:
        # Fallback to single-video logic
        detection = DetectionEvent(...)
```

### 2.5 Results Page Integration Missing (MEDIUM PRIORITY)

**Issue:** HILResults.tsx cannot display multi-video sequence results.

**Evidence:**

**Frontend types (enhanced-results.ts):**
```typescript
export interface VideoSequenceResults {
  session_id: string;
  has_video_sequence: true;
  sequence_summary: { ... };
  per_video_results: PerVideoResult[];
}
```

**API service (api.ts):**
```typescript
// ✅ Function exists but not called from HILResults
export const getVideoSequenceResults = async (sequenceId: string) => {
  const response = await axios.get(`/api/video-sequences/${sequenceId}/results`);
  return response.data;
};
```

**HILResults.tsx:**
```typescript
// ❌ No check for sequence results
// ❌ No conditional rendering for VideoSequenceResults component
// ❌ Always loads single-video results
```

**Impact:**
- ❌ Cannot view sequence-level summary
- ❌ Cannot view per-video breakdown
- ❌ Users see incomplete results

**Recommendation:**
```typescript
// HILResults.tsx
useEffect(() => {
  const loadResults = async () => {
    try {
      // Check if session is a sequence
      const session = await apiService.getTestSession(sessionId);

      if (session.sequence_id) {
        // Load sequence results
        const seqResults = await apiService.getVideoSequenceResults(session.sequence_id);
        setSequenceResults(seqResults);
        setIsSequence(true);
      } else {
        // Load single-video results
        const results = await apiService.getEnhancedDetectionResults(sessionId);
        setResults(results);
      }
    } catch (error) {
      console.error('Failed to load results:', error);
    }
  };

  loadResults();
}, [sessionId]);

// Conditional rendering
{isSequence && sequenceResults ? (
  <VideoSequenceResults results={sequenceResults} />
) : (
  <SingleVideoResults results={results} />
)}
```

---

## 3. Additional Issues and Edge Cases ⚠️

### 3.1 Error Handling Gaps

**Missing Error Scenarios:**
1. ❌ Video fails to load during sequence
2. ❌ Network disconnection during test
3. ❌ LabJack disconnection mid-sequence
4. ❌ Browser crash/refresh during test
5. ❌ Backend crash during sequence

**Recommendation:**
- Implement sequence state persistence
- Add resume capability from last completed video
- Add health check polling during test execution
- Store checkpoints in localStorage

### 3.2 Race Conditions

**Potential Issues:**
1. ⚠️ Video transitions before detection correlation completes
2. ⚠️ Multiple videos start before backend records timing
3. ⚠️ Detection arrives during video transition window

**Recommendation:**
- Add sequence locks/semaphores
- Buffer detections during transitions
- Use message queue for detection processing

### 3.3 Performance Concerns

**Large Sequences:**
- ⚠️ No pagination for per-video results
- ⚠️ Loading 100+ videos could cause UI lag
- ⚠️ Detection event queries not optimized for large datasets

**Recommendation:**
- Implement virtual scrolling for video results table
- Add pagination to results endpoint
- Use database query optimization (already has indexes)

### 3.4 Testing Coverage

**Current Test Status:**
```bash
# Test files exist:
./backend/tests/test_video_sequence_api.py         ✅ Basic
./backend/tests/test_video_sequence_orchestrator.py ✅ Basic
./frontend/src/tests/sequential-video-*.test.tsx   ✅ Basic

# Missing tests:
❌ End-to-end integration tests
❌ Timing accuracy tests
❌ Detection correlation tests
❌ Error recovery tests
❌ Large sequence tests (100+ videos)
```

**Recommendation:**
- Add integration tests with real video playback
- Add timing drift measurement tests
- Add stress tests for large sequences
- Add error injection tests

---

## 4. Architecture Assessment 🏗️

### 4.1 Strengths

1. **Separation of Concerns:**
   - ✅ SequentialVideoPlayer: Pure UI component
   - ✅ HILTestExecutionPRD: Test orchestration
   - ✅ VideoSequenceOrchestrator: Backend business logic
   - ✅ API Router: Clean REST interface

2. **Dynamic Timing Management:**
   - ✅ No hardcoded offsets
   - ✅ Event-driven timing tracking
   - ✅ Accounts for loading delays
   - ✅ Three-tier timing system

3. **Database Design:**
   - ✅ Normalized schema
   - ✅ Proper relationships
   - ✅ Performance-optimized indexes
   - ✅ Backward compatible

4. **Extensibility:**
   - ✅ Easy to add new sequence types
   - ✅ JSON metadata fields for flexibility
   - ✅ Pluggable monitoring services

### 4.2 Weaknesses

1. **Integration Gaps:**
   - ❌ Frontend and backend not connected
   - ❌ LabJack monitoring not sequence-aware
   - ❌ Results page not sequence-aware

2. **State Management:**
   - ⚠️ No global state management (Redux/Zustand)
   - ⚠️ Heavy prop drilling in components
   - ⚠️ State synchronization issues between components

3. **Error Recovery:**
   - ❌ No checkpoint/resume capability
   - ❌ No state persistence
   - ❌ No rollback mechanisms

4. **Observability:**
   - ⚠️ Limited logging/tracing
   - ⚠️ No metrics collection
   - ⚠️ No real-time monitoring dashboard

---

## 5. Recommendations for Completion 📋

### 5.1 Immediate Actions (P0 - Required for Functionality)

1. **Connect Frontend to Backend API** (4-6 hours)
   - Add API calls in SequentialVideoPlayer
   - Integrate video-started endpoint
   - Integrate video-ended endpoint
   - Handle sequence completion

2. **Fix Timing Synchronization** (2-3 hours)
   - Convert frontend to Unix timestamps
   - Ensure consistent time reference
   - Add time sync validation

3. **Implement Video Transition Logic** (3-4 hours)
   - Add automatic advancement
   - Handle sequence completion
   - Navigate to results on finish

4. **Integrate LabJack with Sequence API** (3-4 hours)
   - Route detections through sequence endpoint
   - Pass sequence_id to monitoring
   - Let backend handle video correlation

5. **Connect Results Page** (2-3 hours)
   - Detect sequence sessions
   - Load sequence results
   - Render VideoSequenceResults component

**Total Estimate: 14-20 hours of development**

### 5.2 High Priority (P1 - Required for Production)

1. **Error Handling** (4-6 hours)
   - Add comprehensive error boundaries
   - Implement retry logic
   - Add graceful degradation

2. **End-to-End Testing** (6-8 hours)
   - Integration tests with real video playback
   - Timing accuracy validation
   - Detection correlation verification

3. **State Persistence** (3-4 hours)
   - Implement checkpoint system
   - Add resume capability
   - Store in localStorage + backend

4. **Performance Optimization** (3-4 hours)
   - Add virtual scrolling to results
   - Optimize database queries
   - Add result caching

**Total Estimate: 16-22 hours of development**

### 5.3 Nice to Have (P2 - Future Enhancements)

1. **Real-time Progress Dashboard** (6-8 hours)
2. **Sequence Templates** (4-6 hours)
3. **Parallel Sequence Support** (8-10 hours)
4. **Advanced Analytics** (6-8 hours)
5. **PDF Report Generation** (4-6 hours)

---

## 6. Testing Plan 🧪

### 6.1 Unit Tests (Per Component)

**Frontend:**
```typescript
describe('SequentialVideoPlayer', () => {
  it('should record video start time via API');
  it('should record video end time via API');
  it('should advance to next video automatically');
  it('should complete sequence and navigate to results');
  it('should handle API errors gracefully');
});

describe('HILTestExecutionPRD', () => {
  it('should initialize video sequence via API');
  it('should track current video index');
  it('should handle video transitions');
  it('should complete test when sequence finishes');
});
```

**Backend:**
```python
def test_sequence_video_correlation():
    """Test that detections are correlated to correct video"""

def test_video_timing_accuracy():
    """Test that video start/end times are recorded accurately"""

def test_sequence_completion():
    """Test that sequence completes after last video"""

def test_detection_latency_calculation():
    """Test that per-video latencies are calculated correctly"""
```

### 6.2 Integration Tests

```typescript
describe('End-to-End Multi-Video Sequence', () => {
  it('should play 3 videos sequentially without user interaction', async () => {
    // 1. Start sequence
    const sequence = await startSequence(projectId, [video1, video2, video3]);

    // 2. Wait for video 1 to complete
    await waitForVideoEnd(video1);
    expect(currentVideoIndex).toBe(1);

    // 3. Wait for video 2 to complete
    await waitForVideoEnd(video2);
    expect(currentVideoIndex).toBe(2);

    // 4. Wait for video 3 to complete
    await waitForVideoEnd(video3);
    expect(sequenceComplete).toBe(true);

    // 5. Verify results page
    expect(window.location.pathname).toBe('/hil-results/...');
  });

  it('should correlate detections to correct video', async () => {
    // Send detection during video 2
    await simulateLabJackDetection(timestamp);

    // Verify detection assigned to video 2
    const results = await getSequenceResults(sequenceId);
    const video2Results = results.per_video_results.find(r => r.video_id === video2.id);
    expect(video2Results.detection_count).toBe(1);
  });
});
```

### 6.3 Performance Tests

```python
def test_large_sequence_performance():
    """Test 100-video sequence completes successfully"""
    videos = [create_video(f"video_{i}") for i in range(100)]
    sequence = start_sequence(videos)

    # Measure performance
    assert sequence.total_duration < 300  # Max 5 minutes for 100 videos
    assert all_videos_completed(sequence)

def test_high_detection_rate():
    """Test 1000 detections across 10 videos"""
    sequence = start_sequence(10_videos)

    for i in range(1000):
        record_detection(sequence_id, timestamp=i * 0.1)

    results = get_sequence_results(sequence_id)
    assert results.total_detections == 1000
    assert all([r.avg_latency_ms > 0 for r in results.per_video_results])
```

---

## 7. Production Readiness Checklist ✅

### Critical Requirements

- [ ] **Frontend-Backend Integration**
  - [ ] Video start times recorded via API
  - [ ] Video end times recorded via API
  - [ ] Automatic video advancement working
  - [ ] Sequence completion handling

- [ ] **Timing Synchronization**
  - [ ] Consistent Unix timestamp usage
  - [ ] Accurate video-relative timestamps
  - [ ] Drift compensation implemented

- [ ] **Detection Correlation**
  - [ ] LabJack integrated with sequence API
  - [ ] Detections assigned to correct video
  - [ ] Per-video latencies calculated accurately

- [ ] **Results Display**
  - [ ] Sequence results page working
  - [ ] Per-video breakdown displaying
  - [ ] Export functionality working

- [ ] **Error Handling**
  - [ ] Network errors handled gracefully
  - [ ] Video load failures handled
  - [ ] Hardware disconnection handled
  - [ ] Resume capability implemented

### Testing Requirements

- [ ] Unit tests passing (90%+ coverage)
- [ ] Integration tests passing
- [ ] End-to-end tests passing
- [ ] Performance tests passing
- [ ] Load tests passing

### Documentation Requirements

- [ ] API documentation complete
- [ ] User guide created
- [ ] Deployment guide created
- [ ] Troubleshooting guide created

### Monitoring Requirements

- [ ] Logging implemented
- [ ] Metrics collection enabled
- [ ] Alerting configured
- [ ] Dashboard created

---

## 8. Conclusion

### Summary

The multi-video sequence HIL testing implementation demonstrates **excellent architectural design and strong foundational work**. The database schema is comprehensive, the API design is clean, and the documentation is thorough. However, **critical integration gaps prevent the system from functioning as an end-to-end solution**.

### Key Gaps Identified

1. ❌ **Frontend and backend are not connected** - No API calls from video player
2. ❌ **Timing synchronization issues** - Mixing performance.now() with Unix timestamps
3. ❌ **No automatic video transitions** - Manual intervention required
4. ❌ **LabJack not sequence-aware** - Detections not correlated to videos
5. ❌ **Results page not integrated** - Cannot display sequence results

### Path Forward

With **14-20 hours of focused development** to address the P0 issues, this implementation can become a fully functional unattended multi-video testing system. The foundation is solid, and the remaining work is primarily **integration and wiring**.

### Recommended Next Steps

1. **Prioritize P0 fixes** - Focus on frontend-backend integration
2. **Add integration tests** - Verify end-to-end functionality
3. **Perform load testing** - Test with 10+ video sequences
4. **Document deployment** - Create production deployment guide
5. **Plan monitoring** - Add observability before production release

### Final Assessment

**Current State:** Solid architecture, incomplete execution
**Production Ready:** No (missing critical integrations)
**Time to Production:** 2-3 weeks with focused effort
**Risk Level:** Medium (foundation is good, integration is straightforward)

---

**Reviewer Signature:** Code Review Agent
**Review Completion Date:** 2025-09-30
**Next Review Date:** After P0 fixes are implemented

---

## Appendix A: File Locations

### Backend Files
- `/backend/models.py` - Database models (VideoTestSequence, SequenceVideoResult)
- `/backend/schemas.py` - API schemas with camelCase aliases
- `/backend/routers/video_sequence_testing.py` - API endpoints (1047 lines)
- `/backend/services/video_sequence_orchestrator.py` - Business logic (200+ lines)
- `/backend/migrations/add_video_sequence_schema.py` - Database migration

### Frontend Files
- `/frontend/src/components/SequentialVideoPlayer.tsx` - Video player (764 lines)
- `/frontend/src/pages/HILTestExecutionPRD.tsx` - Test execution page (2197 lines)
- `/frontend/src/components/VideoSequenceResults.tsx` - Results display (467 lines)
- `/frontend/src/types/enhanced-results.ts` - TypeScript types
- `/frontend/src/services/api.ts` - API client functions

### Documentation Files
- `/backend/migrations/MULTI_VIDEO_SEQUENCE_SCHEMA_DOCUMENTATION.md`
- `/frontend/src/docs/MULTI_VIDEO_SEQUENCE_IMPLEMENTATION_SUMMARY.md`
- `/frontend/src/docs/FINAL_INTEGRATION_STEPS.md`
- `/backend/migrations/QUICK_REFERENCE_MULTI_VIDEO_SEQUENCE.md`

### Test Files
- `/backend/tests/test_video_sequence_api.py`
- `/backend/tests/test_video_sequence_orchestrator.py`
- `/frontend/src/tests/sequential-video-*.test.tsx`

---

## Appendix B: Code Snippets for Quick Fixes

### Fix 1: Connect Video Start to Backend

```typescript
// In SequentialVideoPlayer.tsx
const handleVideoStart = useCallback(async (videoIndex: number) => {
  const perfTimestamp = performance.now();
  const unixTimestamp = Date.now() / 1000;

  try {
    // Record in backend
    await fetch(`/api/video-sequences/${sequenceId}/video-started`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        videoId: videos[videoIndex].id,
        startedAt: unixTimestamp,
        clientTimestamp: new Date().toISOString()
      })
    });

    // Update local state
    if (videoIndex === 0 && !sequenceStartTime) {
      setSequenceStartTime(unixTimestamp);
    }
    setVideoStartTime(unixTimestamp);

    onVideoStart?.({ videoIndex, timestamp: perfTimestamp });
  } catch (error) {
    console.error('Failed to record video start:', error);
    // Continue anyway - don't block playback
  }
}, [sequenceId, videos, sequenceStartTime]);
```

### Fix 2: Implement Video Transitions

```typescript
// In SequentialVideoPlayer.tsx
const handleVideoEnd = useCallback(async () => {
  if (!currentVideo) return;

  const unixTimestamp = Date.now() / 1000;
  const actualDuration = videoRef.current?.duration || 0;

  try {
    // Record video end in backend
    const response = await fetch(`/api/video-sequences/${sequenceId}/video-ended`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        videoId: currentVideo.id,
        endedAt: unixTimestamp,
        actualDuration: actualDuration
      })
    });

    const result = await response.json();

    if (result.sequenceComplete) {
      // Sequence finished
      onSequenceComplete?.();
    } else if (result.nextVideo) {
      // Advance to next video
      setCurrentVideoIndex(result.nextVideo.sequenceIndex);
      // Video will auto-play due to useEffect
    }
  } catch (error) {
    console.error('Failed to record video end:', error);
  }
}, [sequenceId, currentVideo, currentVideoIndex]);
```

### Fix 3: LabJack Integration

```python
# In dedicated_labjack_monitor.py
async def record_detection(
    session_id: str,
    sequence_id: Optional[str],
    timestamp: float,
    signal_value: float,
    db: Session
):
    if sequence_id:
        # Use video sequence API for correlation
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8000/api/video-sequences/{sequence_id}/detection",
                json={
                    "unixTimestamp": timestamp,
                    "signalType": "GPIO",
                    "channel": 0,
                    "signalValue": signal_value,
                    "metadata": {"source": "labjack_monitor"}
                }
            )
            return response.json()
    else:
        # Single-video logic (existing code)
        detection = DetectionEvent(...)
        db.add(detection)
        db.commit()
```

---

**End of Review Report**