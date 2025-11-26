# FIX-3 Test Plan: Session Verification in start_video_timing()

## Overview

This test plan covers validation of FIX-3 implementation which adds:
1. Explicit session verification before timing operations
2. Database-first cache consistency (write-through pattern)
3. Transaction isolation handling with db.flush()
4. Comprehensive error handling and propagation

## Test Categories

### 1. Unit Tests (services/test_video_timing_service.py)

#### Test 1.1: Session Not Found Raises Error
**Objective**: Verify fail-fast behavior when session doesn't exist

```python
def test_start_video_timing_session_not_found(mock_db_session):
    """Test that VideoTimingError is raised when session doesn't exist"""
    # Setup
    timing_service = VideoTimingService()
    mock_db_session.query().filter().first.return_value = None  # No session

    # Execute & Assert
    with pytest.raises(VideoTimingError) as exc_info:
        timing_service.start_video_timing(
            session_id="nonexistent_session",
            video_id="test_video",
            db=mock_db_session
        )

    assert "not found in database" in str(exc_info.value)

    # Verify db.flush() was called for visibility
    mock_db_session.flush.assert_called_once()

    # Verify cache was NOT updated (consistency check)
    assert "nonexistent_session" not in timing_service._timing_cache
```

**Expected**: VideoTimingError raised with clear message, cache not updated

#### Test 1.2: Database Write Failure Doesn't Update Cache
**Objective**: Verify cache consistency on DB failure

```python
def test_start_video_timing_db_failure_no_cache_update(mock_db_session):
    """Test that cache is not updated when database write fails"""
    # Setup
    timing_service = VideoTimingService()
    session_id = "test_session"

    # Mock session exists
    mock_session = Mock(id=session_id)
    mock_db_session.query().filter().first.return_value = mock_session

    # Make db.flush() fail after _store_enhanced_video_timing
    mock_db_session.flush.side_effect = [None, SQLAlchemyError("Connection lost")]

    # Execute & Assert
    with pytest.raises(VideoTimingError) as exc_info:
        timing_service.start_video_timing(
            session_id=session_id,
            video_id="test_video",
            db=mock_db_session
        )

    assert "Failed to persist timing data" in str(exc_info.value)

    # CRITICAL: Verify cache was NOT updated
    assert session_id not in timing_service._timing_cache
```

**Expected**: VideoTimingError raised, cache remains empty

#### Test 1.3: Successful Path Updates Cache After DB
**Objective**: Verify write-through pattern works correctly

```python
def test_start_video_timing_success_cache_after_db(mock_db_session):
    """Test that cache is updated ONLY after successful DB write"""
    # Setup
    timing_service = VideoTimingService()
    session_id = "test_session"
    video_id = "test_video"

    mock_session = Mock(id=session_id)
    mock_db_session.query().filter().first.return_value = mock_session

    # Track operation order
    operations = []

    def track_flush():
        operations.append("db_flush")

    mock_db_session.flush.side_effect = track_flush

    # Execute
    result = timing_service.start_video_timing(
        session_id=session_id,
        video_id=video_id,
        db=mock_db_session,
        video_metadata={'fps': 30, 'duration': 10.0}
    )

    # Verify order: DB flush happened before cache update
    assert "db_flush" in operations
    assert session_id in timing_service._timing_cache

    # Verify timing data is correct
    timing_data = timing_service._timing_cache[session_id]
    assert timing_data.session_id == session_id
    assert timing_data.video_id == video_id
    assert timing_data.start_timestamp == result
```

**Expected**: DB flushed, then cache updated, correct timing data

#### Test 1.4: Concurrent Calls Are Serialized
**Objective**: Verify thread safety with lock

```python
def test_start_video_timing_concurrent_serialization(mock_db_session):
    """Test that concurrent calls to same session are serialized by lock"""
    import threading
    import time

    timing_service = VideoTimingService()
    session_id = "concurrent_session"

    mock_session = Mock(id=session_id)
    mock_db_session.query().filter().first.return_value = mock_session

    call_order = []

    def slow_timing_start(video_id):
        result = timing_service.start_video_timing(
            session_id=session_id,
            video_id=video_id,
            db=mock_db_session
        )
        call_order.append(video_id)
        return result

    # Start two threads
    thread1 = threading.Thread(target=slow_timing_start, args=("video1",))
    thread2 = threading.Thread(target=slow_timing_start, args=("video2",))

    thread1.start()
    time.sleep(0.01)  # Ensure thread1 starts first
    thread2.start()

    thread1.join()
    thread2.join()

    # Verify calls were serialized (not interleaved)
    assert len(call_order) == 2
```

**Expected**: Both calls complete, no race conditions

#### Test 1.5: Transaction Visibility with db.flush()
**Objective**: Verify flush makes pending writes visible

```python
def test_start_video_timing_flush_for_visibility(mock_db_session):
    """Test that db.flush() is called to ensure transaction visibility"""
    timing_service = VideoTimingService()
    session_id = "visibility_test"

    mock_session = Mock(id=session_id)
    mock_db_session.query().filter().first.return_value = mock_session

    # Execute
    timing_service.start_video_timing(
        session_id=session_id,
        video_id="test_video",
        db=mock_db_session
    )

    # Verify flush was called twice:
    # 1. Before session verification (for visibility)
    # 2. After _store_enhanced_video_timing (to catch errors)
    assert mock_db_session.flush.call_count >= 2
```

**Expected**: db.flush() called at correct points

### 2. Integration Tests (tests/test_video_timing_integration.py)

#### Test 2.1: Race Condition with Delayed Session Creation
**Objective**: Test transaction isolation with concurrent operations

```python
@pytest.mark.integration
def test_race_condition_delayed_session_creation(test_db):
    """Test handling of race condition where session creation is delayed"""
    import threading
    import time

    timing_service = VideoTimingService()
    session_id = "race_test_session"
    video_id = "race_test_video"

    session_created = threading.Event()
    timing_started = threading.Event()

    def create_session_delayed():
        time.sleep(0.1)  # Simulate slow session creation
        session = TestSession(
            id=session_id,
            name="Race Test",
            project_id="test_project",
            video_id=video_id,
            status="created"
        )
        test_db.add(session)
        test_db.commit()
        session_created.set()

    def start_timing_early():
        try:
            timing_service.start_video_timing(
                session_id=session_id,
                video_id=video_id,
                db=test_db
            )
            timing_started.set()
        except VideoTimingError as e:
            assert "not found" in str(e)

    # Start timing before session is created
    timing_thread = threading.Thread(target=start_timing_early)
    session_thread = threading.Thread(target=create_session_delayed)

    timing_thread.start()
    session_thread.start()

    timing_thread.join()
    session_thread.join()

    # Verify session was created
    assert session_created.is_set()

    # Timing should have failed because session didn't exist yet
    assert not timing_started.is_set()
```

**Expected**: Timing fails with clear error when session doesn't exist

#### Test 2.2: Connection Failure Handling
**Objective**: Test behavior on database connection loss

```python
@pytest.mark.integration
def test_connection_failure_during_timing(test_db):
    """Test graceful handling of connection failures"""
    timing_service = VideoTimingService()
    session_id = "connection_test"

    # Create session
    session = TestSession(
        id=session_id,
        name="Connection Test",
        project_id="test_project",
        video_id="test_video",
        status="created"
    )
    test_db.add(session)
    test_db.commit()

    # Close connection to simulate failure
    test_db.close()

    # Should raise clear error
    with pytest.raises(VideoTimingError) as exc_info:
        timing_service.start_video_timing(
            session_id=session_id,
            video_id="test_video",
            db=test_db
        )

    assert "database error" in str(exc_info.value).lower()
```

**Expected**: Clear error message on connection failure

#### Test 2.3: Transaction Rollback Behavior
**Objective**: Verify cache consistency after rollback

```python
@pytest.mark.integration
def test_transaction_rollback_cache_consistency(test_db):
    """Test that cache doesn't contain data for rolled-back sessions"""
    timing_service = VideoTimingService()
    session_id = "rollback_test"

    # Create session in transaction
    session = TestSession(
        id=session_id,
        name="Rollback Test",
        project_id="test_project",
        video_id="test_video",
        status="created"
    )
    test_db.add(session)
    test_db.flush()  # Make visible but don't commit

    # Start timing (should work because flushed)
    timing_service.start_video_timing(
        session_id=session_id,
        video_id="test_video",
        db=test_db
    )

    # Rollback transaction
    test_db.rollback()

    # Cache should still have data (it was written after successful DB ops)
    # But querying DB should fail because session was rolled back
    assert session_id in timing_service._timing_cache

    # New db session shouldn't find the rolled-back session
    new_db = SessionLocal()
    found_session = new_db.query(TestSession).filter(TestSession.id == session_id).first()
    assert found_session is None
    new_db.close()
```

**Expected**: Cache-DB mismatch detected, documented as caller responsibility

#### Test 2.4: Concurrent Timing Starts for Same Session
**Objective**: Test idempotency and last-write-wins behavior

```python
@pytest.mark.integration
def test_concurrent_timing_starts_same_session(test_db):
    """Test that concurrent timing starts for same session are handled correctly"""
    import threading

    timing_service = VideoTimingService()
    session_id = "concurrent_timing_test"

    # Create session
    session = TestSession(
        id=session_id,
        name="Concurrent Timing Test",
        project_id="test_project",
        video_id="video1",
        status="created"
    )
    test_db.add(session)
    test_db.commit()

    results = []

    def start_timing(video_id):
        timestamp = timing_service.start_video_timing(
            session_id=session_id,
            video_id=video_id,
            db=test_db
        )
        results.append((video_id, timestamp))

    # Start 3 concurrent timing operations
    threads = [
        threading.Thread(target=start_timing, args=(f"video{i}",))
        for i in range(3)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # All should succeed
    assert len(results) == 3

    # Last write wins - final cache state should have last video_id
    timing_data = timing_service.get_timing_data(session_id)
    assert timing_data is not None
    assert timing_data.video_id in ["video0", "video1", "video2"]
```

**Expected**: All calls succeed, last write wins, no corruption

### 3. System Tests (tests/test_video_timing_system.py)

#### Test 3.1: End-to-End LabJack Monitoring Flow
**Objective**: Test complete flow with LabJack integration

```python
@pytest.mark.system
def test_e2e_labjack_monitoring_with_timing(test_db, mock_labjack):
    """Test complete LabJack monitoring flow with video timing"""
    # This test verifies FIX-3 integrates correctly with existing systems
    # Full test implementation would follow the dedicated_labjack_monitor pattern
    pass  # Detailed implementation omitted for brevity
```

#### Test 3.2: Multi-Video Sequence Orchestration
**Objective**: Test timing in multi-video sequences

```python
@pytest.mark.system
def test_multi_video_sequence_timing(test_db):
    """Test video timing in multi-video sequences"""
    # Verifies FIX-3 works with video_sequence_orchestrator
    pass  # Detailed implementation omitted for brevity
```

## Test Execution Plan

### Phase 1: Unit Tests (Est. 2 hours)
1. Implement all 5 unit tests
2. Run with `pytest tests/test_video_timing_service.py -v`
3. Achieve 100% code coverage for modified methods

### Phase 2: Integration Tests (Est. 3 hours)
1. Implement all 4 integration tests
2. Run with `pytest tests/test_video_timing_integration.py -v --integration`
3. Verify database isolation and transaction handling

### Phase 3: System Tests (Est. 2 hours)
1. Implement system-level tests
2. Run with existing test suite
3. Verify no regressions in LabJack monitoring and orchestration

### Phase 4: Manual Testing (Est. 1 hour)
1. Test via API endpoints
2. Monitor logs for proper debug messages
3. Verify WebSocket notifications work correctly

## Success Criteria

- ✅ All unit tests pass with 100% coverage of modified code
- ✅ All integration tests pass without database corruption
- ✅ System tests show no regressions
- ✅ Manual testing confirms proper error messages in logs
- ✅ Cache-DB consistency maintained in all scenarios
- ✅ No silent failures (all errors properly raised)

## Rollback Plan

If tests fail or regressions detected:
1. Revert `services/video_timing_service.py` to previous version
2. Document specific failure modes
3. Re-analyze transaction requirements
4. Implement alternative approach (Option B from analysis doc)

## Monitoring in Production

After deployment, monitor:
1. VideoTimingError frequency in logs
2. Cache-DB consistency metrics
3. Session creation timing patterns
4. Database connection pool exhaustion
5. Transaction rollback rates

## Documentation Updates Required

- ✅ Update API documentation with new error responses
- ✅ Update service docstrings with transaction requirements
- ✅ Create troubleshooting guide for VideoTimingError
- ✅ Document caller responsibilities for transaction management
