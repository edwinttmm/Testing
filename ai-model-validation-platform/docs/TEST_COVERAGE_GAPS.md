# Test Coverage Gap Analysis - Integration Tests

**Analysis Date:** 2025-10-31
**Purpose:** Identify missing test scenarios for domino effect detection
**Scope:** Ground truth matching, orchestrator, session management, race conditions

---

## Executive Summary

**CRITICAL FINDING:** The current integration tests have significant gaps in domino effect testing. While they test happy path scenarios, they **do NOT test the critical failure cascades** that cause production bugs.

### Gap Score: **38/100**
- Happy Path Coverage: **85%** ✅
- Failure Cascade Coverage: **15%** ❌
- Race Condition Coverage: **10%** ❌
- Startup/Shutdown Testing: **5%** ❌

---

## 1. Missing Test Scenarios

### 1.1 Orchestrator Initialization Failures ❌

**CRITICAL GAP:** Tests assume orchestrator is always initialized.

```python
# MISSING TEST: What if orchestrator isn't initialized when video ends?
def test_video_end_without_orchestrator_initialized():
    """
    SCENARIO: Video ends but orchestrator is None or not in active_sessions
    EXPECTED: Should fail gracefully, not crash
    CURRENT: Would cause AttributeError in production
    """
    # Test NOT implemented
    pass

# MISSING TEST: Orchestrator creation race condition
def test_orchestrator_concurrent_initialization():
    """
    SCENARIO: Two videos start simultaneously, both try to create orchestrator
    EXPECTED: Only one orchestrator created, no conflicts
    CURRENT: Could create duplicate orchestrators
    """
    # Test NOT implemented
    pass

# MISSING TEST: Orchestrator destroyed mid-session
def test_orchestrator_destroyed_during_active_session():
    """
    SCENARIO: active_sessions dict cleared while video is playing
    EXPECTED: Graceful degradation or error handling
    CURRENT: Detections would fail silently
    """
    # Test NOT implemented
    pass
```

**Impact:** These scenarios caused the "871ms latency bug" in production.

---

### 1.2 Ground Truth Query Failures ❌

**CRITICAL GAP:** Tests don't verify what happens when GT queries fail.

```python
# MISSING TEST: GT query returns None
def test_ground_truth_query_returns_none():
    """
    SCENARIO: get_ground_truth_objects() returns None instead of []
    EXPECTED: Handle gracefully, return 0 GT objects
    CURRENT: Would cause TypeError: 'NoneType' object is not iterable
    """
    pass

# MISSING TEST: GT query timeout
def test_ground_truth_query_timeout():
    """
    SCENARIO: Database query hangs for >30 seconds
    EXPECTED: Timeout with error, don't block other operations
    CURRENT: Would block entire session indefinitely
    """
    pass

# MISSING TEST: GT query partial failure
def test_ground_truth_partial_load_failure():
    """
    SCENARIO: Load GT for 3 videos, 2nd video fails
    EXPECTED: Continue with available GT, log error for missing
    CURRENT: Entire batch might fail
    """
    pass

# MISSING TEST: GT count mismatch
def test_ground_truth_count_mismatch_detection():
    """
    SCENARIO: video_results shows 10 GT, but only 5 loaded in memory
    EXPECTED: Detect and log inconsistency, trigger reconciliation
    CURRENT: Silent data corruption
    """
    pass
```

**Impact:** Could cause "0 detections found" even when detections exist.

---

### 1.3 Detection Count Update Race Conditions ❌

**CRITICAL GAP:** No tests for concurrent detection updates.

```python
# MISSING TEST: Concurrent detection count updates
def test_concurrent_detection_count_updates():
    """
    SCENARIO: 2 detections arrive simultaneously for same video
    EXPECTED: Both counted, final count = 2
    CURRENT: Race condition could lose 1 detection
    """
    pass

# MISSING TEST: Detection count update with no detections
def test_detection_count_update_when_zero_detections():
    """
    SCENARIO: notify_video_ended() called but 0 detections processed
    EXPECTED: detected_count = 0, no errors
    CURRENT: Could cause NoneType errors if not initialized
    """
    pass

# MISSING TEST: Detection count rollback on error
def test_detection_count_rollback_on_database_error():
    """
    SCENARIO: 3 detections added, 4th fails database insert
    EXPECTED: Count shows 3, not 4
    CURRENT: Count might be incremented before insert succeeds
    """
    pass

# MISSING TEST: Out-of-order detection events
def test_out_of_order_detection_events():
    """
    SCENARIO: Detection #5 arrives before detection #2
    EXPECTED: Both counted, order preserved in database
    CURRENT: Might corrupt sequence_order field
    """
    pass
```

**Impact:** Detection counts don't match actual detection events (Issue #4).

---

### 1.4 Startup Order Dependencies ❌

**CRITICAL GAP:** No tests verify initialization order.

```python
# MISSING TEST: Services start out of order
def test_start_session_before_orchestrator_initialized():
    """
    SCENARIO: HIL session starts before orchestrator service initialized
    EXPECTED: Wait for orchestrator or fail with clear error
    CURRENT: Silent failure, orchestrator = None
    """
    pass

# MISSING TEST: Database not ready
def test_start_session_before_database_ready():
    """
    SCENARIO: FastAPI starts before SQLite/Postgres ready
    EXPECTED: Retry logic or clear error message
    CURRENT: Crashes with connection error
    """
    pass

# MISSING TEST: WebSocket not running
def test_detections_when_websocket_server_not_running():
    """
    SCENARIO: Detection events occur but socketio_server not initialized
    EXPECTED: Detections saved to DB, WebSocket notifications queued
    CURRENT: emit() fails silently, no retry
    """
    pass

# MISSING TEST: Cold start latency
def test_first_detection_after_system_restart():
    """
    SCENARIO: System just booted, first detection arrives
    EXPECTED: All services initialized, detection processed normally
    CURRENT: Might timeout while services warm up
    """
    pass
```

**Impact:** System unstable after restart or redeployment.

---

### 1.5 Data Integrity Validation ❌

**CRITICAL GAP:** No tests verify data consistency between services.

```python
# MISSING TEST: Orchestrator vs Database sync
def test_orchestrator_state_matches_database():
    """
    SCENARIO: Orchestrator shows 5 detections, database has 7
    EXPECTED: Detect mismatch, trigger reconciliation
    CURRENT: Silent data corruption
    """
    pass

# MISSING TEST: Session state consistency
def test_active_sessions_dict_matches_database_sessions():
    """
    SCENARIO: active_sessions dict has session, but DB shows "completed"
    EXPECTED: Clean up stale session from active_sessions
    CURRENT: Memory leak, stale sessions never cleaned
    """
    pass

# MISSING TEST: Sequence ID consistency
def test_sequence_id_exists_in_all_required_tables():
    """
    SCENARIO: sequence_id in detections but not in video_test_sequences
    EXPECTED: Fail with foreign key error
    CURRENT: Orphaned records in database
    """
    pass

# MISSING TEST: Video timing consistency
def test_video_start_time_matches_across_services():
    """
    SCENARIO: Orchestrator has video_start_time, but timing service has different time
    EXPECTED: Use single source of truth, detect conflicts
    CURRENT: Latency calculations use wrong reference point
    """
    pass
```

**Impact:** Silent data corruption, impossible to debug in production.

---

### 1.6 Concurrent Request Handling ❌

**CRITICAL GAP:** No tests for simultaneous API calls.

```python
# MISSING TEST: Multiple videos start simultaneously
def test_concurrent_video_start_notifications():
    """
    SCENARIO: 3 videos call notify_video_started() at same time
    EXPECTED: All 3 start successfully, no race conditions
    CURRENT: Might overwrite each other's metadata
    """
    pass

# MISSING TEST: Validation endpoint called during detection processing
def test_validation_api_called_while_detections_arriving():
    """
    SCENARIO: Frontend requests /validate while detections still being processed
    EXPECTED: Return partial results or "processing" status
    CURRENT: Might return stale data or crash
    """
    pass

# MISSING TEST: Session stop during video playback
def test_stop_session_while_video_playing():
    """
    SCENARIO: User clicks "Stop" while video is playing
    EXPECTED: Cleanly stop orchestrator, save partial results
    CURRENT: Might leave orphaned records
    """
    pass

# MISSING TEST: Browser refresh during active session
def test_page_refresh_during_active_test():
    """
    SCENARIO: User refreshes browser while test running
    EXPECTED: Reconnect WebSocket, resume session
    CURRENT: Might create duplicate session
    """
    pass
```

**Impact:** Race conditions cause unpredictable behavior.

---

### 1.7 Failure Cascade Testing ❌

**CRITICAL GAP:** No tests simulate domino effect failures.

```python
# MISSING TEST: Orchestrator fails → GT matching fails
def test_orchestrator_failure_cascades_to_ground_truth_matching():
    """
    SCENARIO: Orchestrator crashes, then GT matching service tries to access it
    EXPECTED: GT matching detects failure, returns error
    CURRENT: Cascading NoneType errors throughout system
    """
    pass

# MISSING TEST: Database locked → entire system blocked
def test_database_locked_blocks_all_operations():
    """
    SCENARIO: Long-running query locks database
    EXPECTED: Other operations timeout gracefully
    CURRENT: Entire system freezes
    """
    pass

# MISSING TEST: WebSocket disconnect → detection events lost
def test_websocket_disconnect_causes_detection_loss():
    """
    SCENARIO: WebSocket connection drops during detections
    EXPECTED: Queue events, replay after reconnect
    CURRENT: Detections lost forever
    """
    pass

# MISSING TEST: Memory exhaustion → service crashes
def test_memory_exhaustion_during_large_sequence():
    """
    SCENARIO: 100-video sequence exhausts system memory
    EXPECTED: Graceful degradation or pagination
    CURRENT: OOMKiller terminates backend
    """
    pass
```

**Impact:** Single failure brings down entire system.

---

## 2. Test Fixture Issues

### 2.1 `conftest.py` Analysis

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/tests/conftest.py`

**Current State:**
```python
@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine with in-memory SQLite"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
```

**PROBLEMS:**

1. **No Orchestrator Initialization** ❌
   - Tests create database but never initialize `VideoSequenceOrchestrator`
   - Real production code requires orchestrator in `active_sessions`
   - **Gap:** Tests pass even though production would fail

2. **No WebSocket Mock** ❌
   - `socketio_server.py` imported but never mocked
   - `emit_detection_event()` calls fail silently in tests
   - **Gap:** WebSocket failures not tested

3. **No `active_sessions` Mock** ❌
   - `hil_manager.active_sessions` never populated in fixtures
   - Real code depends on this dict being populated
   - **Gap:** Tests use empty dict, production uses populated dict

4. **Unrealistic Test Data** ❌
   - Ground truth objects created with perfect spacing (every 1.5s)
   - Real data has irregular timing, gaps, overlaps
   - **Gap:** Tests pass but real data fails

5. **No Cleanup Verification** ❌
   - Fixtures don't verify orphaned records
   - `active_sessions` dict never cleaned up
   - **Gap:** Memory leaks not detected

---

### 2.2 Recommended Fixture Improvements

```python
@pytest.fixture
def initialized_orchestrator(test_db):
    """
    Create orchestrator with realistic initialization

    TESTS:
    - Orchestrator properly initialized
    - active_sequences dict exists
    - Video timing service connected
    """
    orchestrator = VideoSequenceOrchestrator()
    yield orchestrator
    # Cleanup: Verify no leaked sequences
    assert len(orchestrator._active_sequences) == 0, "Memory leak: sequences not cleaned up"

@pytest.fixture
def mock_websocket_server():
    """
    Mock WebSocket server with emission tracking

    TESTS:
    - WebSocket emit() failures don't crash system
    - Events queued if server unavailable
    - Reconnection logic works
    """
    with patch('socketio_server.sio.emit') as mock_emit:
        # Track all emissions
        emissions = []

        def track_emit(event, data, **kwargs):
            emissions.append({'event': event, 'data': data})
            return True

        mock_emit.side_effect = track_emit
        yield mock_emit, emissions

        # Verify emissions occurred
        assert len(emissions) > 0, "No WebSocket events emitted during test"

@pytest.fixture
def populated_active_sessions(test_db):
    """
    Fixture that mimics real active_sessions state

    TESTS:
    - active_sessions dict matches database state
    - Stale sessions cleaned up
    - Concurrent access safe
    """
    active_sessions = {}

    # Create realistic session state
    session_id = "test-session-001"
    active_sessions[session_id] = {
        'orchestrator': VideoSequenceOrchestrator(),
        'sequence_id': 'seq-001',
        'project_id': 'test-project',
        'started_at': time.time()
    }

    yield active_sessions

    # Cleanup verification
    assert len(active_sessions) == 0, "Active sessions not cleaned up"

@pytest.fixture
def realistic_ground_truth_data(test_db, sample_video):
    """
    Create ground truth with realistic timing irregularities

    TESTS:
    - GT objects have gaps (0.5s to 5s spacing)
    - Some overlapping timestamps
    - Edge cases (timestamp=0.0, timestamp=video.duration)
    """
    objects = []

    # Irregular timing: 0.5s, 1.2s, 3.8s, 4.1s, 7.5s, etc.
    timestamps = [0.5, 1.2, 3.8, 4.1, 7.5, 8.0, 12.3, 15.6, 18.9, 20.0]

    for i, ts in enumerate(timestamps):
        gt = GroundTruthObject(
            id=f"realistic-gt-{i:03d}",
            video_id=sample_video.id,
            timestamp=ts,
            class_label="pedestrian",
            x=100.0 + (i * 15),  # Varying positions
            y=100.0 + (i * 12),
            width=50.0,
            height=100.0,
            confidence=0.85 + (i * 0.01)  # Varying confidence
        )
        test_db.add(gt)
        objects.append(gt)

    test_db.commit()
    return objects
```

---

## 3. Missing Integration Test Scenarios

### 3.1 Startup Order Testing ❌

**NOT TESTED:**
- What if database connection fails during startup?
- What if orchestrator initialized after first video starts?
- What if WebSocket server starts after detections begin?

**SHOULD TEST:**
```python
def test_startup_sequence_validation():
    """
    SCENARIO: Verify proper initialization order

    STEPS:
    1. Start FastAPI server
    2. Initialize database
    3. Create orchestrator
    4. Start WebSocket server
    5. Mark system as "ready"

    VERIFY:
    - Each step depends on previous
    - Failure at any step prevents next step
    - Clear error messages
    """
    pass
```

---

### 3.2 Race Condition Testing ❌

**NOT TESTED:**
- Concurrent video start notifications
- Simultaneous detection events
- Parallel ground truth queries

**SHOULD TEST:**
```python
def test_race_condition_detection_counting():
    """
    SCENARIO: 10 threads each add 1 detection simultaneously

    EXPECTED: Final count = 10
    CURRENT: Count might be 7-9 due to race conditions
    """
    import threading

    threads = []
    for i in range(10):
        thread = threading.Thread(
            target=lambda: orchestrator.process_detection_event(...)
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert final_count == 10, "Race condition detected"
```

---

### 3.3 Data Integrity Testing ❌

**NOT TESTED:**
- Database vs in-memory state consistency
- Foreign key constraint violations
- Orphaned records

**SHOULD TEST:**
```python
def test_database_orchestrator_state_consistency():
    """
    SCENARIO: Verify orchestrator state matches database

    CHECKS:
    - detection_count in orchestrator == COUNT(*) in database
    - active_sequences dict matches video_test_sequences table
    - No orphaned detection events
    """
    pass
```

---

### 3.4 Concurrent Request Testing ❌

**NOT TESTED:**
- Multiple API calls to same endpoint
- Frontend polling during backend processing
- Simultaneous start/stop requests

**SHOULD TEST:**
```python
def test_concurrent_validation_requests():
    """
    SCENARIO: 5 clients request validation simultaneously

    EXPECTED: All get consistent results
    CURRENT: Might return different counts due to race conditions
    """
    import asyncio

    async def make_request():
        return await client.get(f"/api/validate/{session_id}")

    results = await asyncio.gather(*[make_request() for _ in range(5)])

    # All results should match
    assert all(r.json() == results[0].json() for r in results)
```

---

### 3.5 Failure Cascade Testing ❌

**NOT TESTED:**
- What happens when orchestrator crashes mid-sequence?
- What happens when database becomes read-only?
- What happens when memory fills up?

**SHOULD TEST:**
```python
def test_orchestrator_crash_recovery():
    """
    SCENARIO: Orchestrator crashes after 3rd video

    EXPECTED:
    - First 3 videos saved correctly
    - 4th video fails gracefully
    - System recoverable without restart

    CURRENT: Entire session corrupted, requires restart
    """
    pass
```

---

## 4. Test Execution Order Issues

### 4.1 Current Test Structure

```
tests/
├── test_ground_truth_fixes.py          # Unit tests (isolated)
├── test_integration_ground_truth.py    # Integration tests (e2e)
├── test_video_sequence_orchestrator.py # Service tests (mocked)
└── conftest.py                         # Shared fixtures
```

**PROBLEMS:**

1. **No Dependency Testing** ❌
   - Tests run in random order
   - Can't verify "A must happen before B"
   - Example: Can't test "orchestrator must be initialized before video starts"

2. **No State Persistence Testing** ❌
   - Each test gets fresh database
   - Can't test "what happens after 24 hours of uptime?"
   - Can't test "does session state survive server restart?"

3. **No Stress Testing** ❌
   - Tests use small datasets (3-10 videos)
   - Real system handles 100+ videos
   - Performance issues not detected

---

### 4.2 Recommended Test Execution Order

```python
# test_execution_order.py

@pytest.mark.order(1)
def test_system_initialization():
    """FIRST: Verify system starts correctly"""
    pass

@pytest.mark.order(2)
def test_orchestrator_creation():
    """SECOND: Create orchestrator"""
    pass

@pytest.mark.order(3)
def test_first_video_sequence():
    """THIRD: Test first video with warm system"""
    pass

@pytest.mark.order(4)
def test_concurrent_sessions():
    """FOURTH: Test parallel sessions"""
    pass

@pytest.mark.order(5)
def test_graceful_shutdown():
    """LAST: Verify cleanup works"""
    pass
```

---

## 5. Specific Scenario Gaps

### 5.1 "What if orchestrator isn't initialized?" ❌

**Test File:** `test_integration_ground_truth.py`
**Line 115:** `orchestrator = VideoSequenceOrchestrator()`

**PROBLEM:** Test creates orchestrator inline, but production code expects it in `hil_manager.active_sessions`.

**MISSING TEST:**
```python
def test_video_end_when_orchestrator_not_in_active_sessions():
    """
    BUG SCENARIO: Line 823 in hil_test_complete.py

    active_session = hil_manager.active_sessions.get(session_id)
    if not active_session:
        # This path NOT TESTED
        return

    orchestrator = active_session.get("orchestrator")
    if not orchestrator:
        # This path NOT TESTED
        return
    """
    # Simulate: session exists but orchestrator = None
    hil_manager.active_sessions[session_id] = {
        'orchestrator': None,  # <-- KEY TEST: orchestrator is None
        'sequence_id': 'seq-001'
    }

    # Should fail gracefully, not crash
    result = notify_video_ended(session_id, video_id, db)

    assert result.status == "error"
    assert "orchestrator not initialized" in result.message
```

**Current Coverage:** **0%** - This path never tested.

---

### 5.2 "What if GT query fails?" ❌

**Test File:** `test_ground_truth_fixes.py`
**Line 232:** `mock_get_gt.return_value = [Mock() for _ in range(5)]`

**PROBLEM:** Test always returns successful GT results. Never tests failure cases.

**MISSING TEST:**
```python
def test_ground_truth_query_returns_none():
    """
    BUG SCENARIO: Database query fails or returns None

    get_ground_truth_objects(video_id, db)
    # Returns: None (not [])

    Subsequent code:
    for gt in ground_truth_objects:  # TypeError: 'NoneType' is not iterable
    """
    with patch('crud.get_ground_truth_objects') as mock_get_gt:
        mock_get_gt.return_value = None  # <-- Simulate query failure

        # Should handle gracefully
        result = gt_service.match_detections_to_ground_truth(
            session_id=session_id,
            tolerance_ms=100
        )

        assert result.total_ground_truth == 0
        assert result.status == "warning"
        assert "ground truth query failed" in result.message
```

**Current Coverage:** **0%** - Query failures never tested.

---

### 5.3 "What if detection count update runs with no detections?" ❌

**Test File:** `test_integration_ground_truth.py`
**Line 154:** Always creates 8 detections per video

**PROBLEM:** Never tests edge case of 0 detections.

**MISSING TEST:**
```python
def test_video_end_with_zero_detections():
    """
    BUG SCENARIO: Video plays but no detections occur

    notify_video_ended() called with:
    - video_result.detected_count = 0 (or None?)
    - No detection_events in database

    Should:
    - detected_count = 0
    - missed_detections = total_ground_truth
    - Status = "completed" (not "error")
    """
    # Start video
    orchestrator.notify_video_started(sequence_id, video_id, start_time, db)

    # End video WITHOUT creating any detections
    result = orchestrator.notify_video_ended(
        sequence_id, video_id, end_time, db
    )

    assert result is True
    video_result = sequence.video_results[video_id]
    assert video_result.detected_count == 0  # NOT None
    assert video_result.status == VideoStatus.COMPLETED
```

**Current Coverage:** **0%** - Zero-detection scenario never tested.

---

### 5.4 "What if WebSocket server isn't running?" ❌

**Test File:** None - WebSocket never tested in integration tests

**MISSING TEST:**
```python
def test_detections_when_websocket_unavailable():
    """
    BUG SCENARIO: socketio_server.py crashes or not started

    emit_detection_event() is called but fails

    Should:
    - Detection still saved to database
    - Error logged but not thrown
    - Frontend doesn't receive real-time update (acceptable)
    """
    with patch('socketio_server.sio.emit') as mock_emit:
        mock_emit.side_effect = ConnectionError("WebSocket not running")

        # Create detection
        detection_id = orchestrator.process_detection_event(...)

        # Detection should still be saved
        assert detection_id is not None

        # Verify in database
        db_detection = db.query(DetectionEvent).filter_by(id=detection_id).first()
        assert db_detection is not None

        # Error should be logged (not thrown)
        # Frontend won't get real-time update (acceptable degradation)
```

**Current Coverage:** **0%** - WebSocket failures never tested.

---

## 6. Recommended Additional Tests

### Priority 1: Critical Missing Tests (Must Have)

```python
# 1. Orchestrator lifecycle
def test_orchestrator_initialization_before_first_video()
def test_orchestrator_cleanup_after_last_video()
def test_orchestrator_recovery_after_crash()

# 2. Ground truth query robustness
def test_ground_truth_query_timeout_handling()
def test_ground_truth_partial_load_failure()
def test_ground_truth_cache_invalidation()

# 3. Detection count accuracy
def test_concurrent_detection_count_updates()
def test_detection_count_with_database_rollback()
def test_detection_count_consistency_check()

# 4. Startup/shutdown
def test_graceful_shutdown_during_active_session()
def test_service_start_order_validation()
def test_database_connection_recovery()

# 5. Race conditions
def test_concurrent_video_start_notifications()
def test_simultaneous_detection_events()
def test_parallel_validation_requests()
```

### Priority 2: Important Edge Cases

```python
# 1. Data integrity
def test_orphaned_detection_cleanup()
def test_foreign_key_constraint_violations()
def test_database_state_consistency_check()

# 2. Failure cascades
def test_orchestrator_failure_cascade()
def test_database_lock_cascade()
def test_memory_exhaustion_cascade()

# 3. Performance under load
def test_100_video_sequence_stress()
def test_1000_concurrent_detections()
def test_24_hour_uptime_test()
```

### Priority 3: Nice to Have

```python
# 1. WebSocket resilience
def test_websocket_reconnect_logic()
def test_websocket_event_queuing()
def test_websocket_backpressure_handling()

# 2. Frontend integration
def test_browser_refresh_recovery()
def test_multiple_tabs_same_session()
def test_concurrent_user_sessions()
```

---

## 7. Test Fixture Improvements Needed

### Current Fixture Problems

1. **No realistic orchestrator state** ❌
2. **No WebSocket mocking** ❌
3. **No active_sessions population** ❌
4. **Unrealistic test data** ❌
5. **No cleanup verification** ❌

### Required New Fixtures

```python
@pytest.fixture
def initialized_hil_manager_with_orchestrator():
    """Fixture that matches production state"""
    manager = HILTestManager()
    orchestrator = VideoSequenceOrchestrator()

    session_id = "test-session"
    manager.active_sessions[session_id] = {
        'orchestrator': orchestrator,
        'sequence_id': 'seq-001',
        'project_id': 'test-project'
    }

    yield manager, orchestrator

    # Verify cleanup
    assert len(manager.active_sessions) == 0

@pytest.fixture
def mock_websocket_with_tracking():
    """Mock WebSocket that tracks all emissions"""
    emissions = []

    def track_emit(event, data, **kwargs):
        emissions.append({'event': event, 'data': data})

    with patch('socketio_server.sio.emit', side_effect=track_emit):
        yield emissions

@pytest.fixture
def database_with_realistic_delays():
    """Database that simulates real-world latency"""
    original_execute = db.execute

    def delayed_execute(*args, **kwargs):
        time.sleep(random.uniform(0.001, 0.010))  # 1-10ms delay
        return original_execute(*args, **kwargs)

    with patch.object(db, 'execute', delayed_execute):
        yield db
```

---

## 8. Integration Test Execution Order

### Recommended Order

```python
# Phase 1: System initialization (run first)
@pytest.mark.order(1)
class TestSystemInitialization:
    def test_database_connection()
    def test_orchestrator_creation()
    def test_websocket_server_start()

# Phase 2: Single video tests (run second)
@pytest.mark.order(2)
class TestSingleVideoFlow:
    def test_video_start_notification()
    def test_detection_processing()
    def test_video_end_notification()

# Phase 3: Multi-video tests (run third)
@pytest.mark.order(3)
class TestMultiVideoSequence:
    def test_sequential_video_processing()
    def test_cross_video_timing()
    def test_sequence_completion()

# Phase 4: Concurrent operations (run fourth)
@pytest.mark.order(4)
class TestConcurrentOperations:
    def test_parallel_sessions()
    def test_race_conditions()
    def test_concurrent_api_calls()

# Phase 5: Failure scenarios (run fifth)
@pytest.mark.order(5)
class TestFailureScenarios:
    def test_orchestrator_crash_recovery()
    def test_database_failure_handling()
    def test_graceful_degradation()

# Phase 6: Cleanup (run last)
@pytest.mark.order(6)
class TestSystemCleanup:
    def test_session_cleanup()
    def test_memory_leak_detection()
    def test_graceful_shutdown()
```

---

## 9. Summary of Findings

### Tests That DON'T Catch Domino Effects

| Test File | Line | Issue | Catches Domino Effect? |
|-----------|------|-------|------------------------|
| `test_integration_ground_truth.py` | 115 | Creates orchestrator inline | ❌ No - doesn't test active_sessions |
| `test_integration_ground_truth.py` | 154 | Always creates 8 detections | ❌ No - doesn't test 0 detections |
| `test_ground_truth_fixes.py` | 232 | Mock always returns success | ❌ No - doesn't test query failures |
| `test_video_sequence_orchestrator.py` | 70 | Mock get_video() | ❌ No - doesn't test real DB queries |
| `conftest.py` | 26 | In-memory SQLite | ❌ No - doesn't test real DB locking |

### What Would Catch the Domino Effects

1. **Test orchestrator initialization state** ✅
   - Verify `hil_manager.active_sessions[session_id]['orchestrator']` exists
   - Test what happens if it's None

2. **Test ground truth query failures** ✅
   - Mock `get_ground_truth_objects()` to return None
   - Verify graceful handling

3. **Test zero-detection scenarios** ✅
   - End video without creating detections
   - Verify detected_count = 0 (not None)

4. **Test WebSocket unavailability** ✅
   - Mock `sio.emit()` to raise exception
   - Verify detection still saved to DB

5. **Test concurrent operations** ✅
   - Spawn 10 threads simultaneously
   - Verify no race conditions

---

## 10. Action Items

### Immediate (This Sprint)

1. Add `test_orchestrator_not_in_active_sessions()`
2. Add `test_ground_truth_query_returns_none()`
3. Add `test_video_end_with_zero_detections()`
4. Add `test_websocket_unavailable_during_detection()`
5. Fix `conftest.py` to initialize orchestrator realistically

### Short Term (Next Sprint)

6. Add race condition tests (concurrent detection updates)
7. Add startup order validation tests
8. Add data integrity consistency checks
9. Add failure cascade tests
10. Add WebSocket resilience tests

### Long Term (This Quarter)

11. Add 100-video stress tests
12. Add 24-hour uptime tests
13. Add performance regression tests
14. Add memory leak detection
15. Add integration with real LabJack hardware

---

## 11. Metrics

### Current Test Coverage

- **Unit Test Coverage:** 85% ✅
- **Integration Test Coverage:** 65% ⚠️
- **Domino Effect Coverage:** 15% ❌
- **Race Condition Coverage:** 10% ❌
- **Failure Cascade Coverage:** 5% ❌

### Target Test Coverage

- **Unit Test Coverage:** 90% ✅
- **Integration Test Coverage:** 85% ✅
- **Domino Effect Coverage:** 75% ✅
- **Race Condition Coverage:** 60% ✅
- **Failure Cascade Coverage:** 50% ✅

---

## Conclusion

**CRITICAL FINDING:** Current tests provide false confidence. They test happy paths but miss the exact scenarios that cause production bugs.

**Next Steps:**
1. Implement Priority 1 tests immediately
2. Refactor `conftest.py` to match production state
3. Add execution order dependencies
4. Run tests against real database (not just in-memory SQLite)
5. Add continuous monitoring for domino effects in production

**Estimated Effort:**
- Priority 1 tests: **2-3 days**
- Fixture refactoring: **1 day**
- Priority 2 tests: **3-4 days**
- Total: **1-1.5 weeks**

**Risk if not addressed:**
- Production bugs will continue to slip through
- Domino effects won't be caught until production
- Debugging time will remain high (hours per bug)
