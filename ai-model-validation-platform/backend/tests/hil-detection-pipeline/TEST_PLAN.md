# HIL Detection Pipeline Test Plan

**Created:** 2025-11-14
**Agent:** Test Engineering Specialist
**Coverage:** LabJack Connection, WebSocket Events, Detection Queue, Integration, Performance

---

## Test Structure

```
tests/hil-detection-pipeline/
├── conftest.py                    # Shared fixtures and configuration
├── test_labjack_connection.py    # LabJack hardware tests
├── test_websocket_events.py      # WebSocket emission tests
├── test_detection_queue.py       # Detection queue tests
├── test_integration.py           # End-to-end integration tests
├── TEST_PLAN.md                  # This file
└── EXECUTION_INSTRUCTIONS.md     # How to run tests
```

---

## Test Coverage Areas

### 1. LabJack Connection Tests (`test_labjack_connection.py`)

#### Test Classes:
- **TestLabJackConnection**: Hardware connection stability
- **TestSignalCapture**: Voltage detection and signal processing
- **TestDetectionWindowValidation**: Timing window validation

#### Key Test Cases:
- `test_connection_initialization`: Verifies connection manager setup
- `test_connection_stability_during_monitoring`: Connection remains stable
- `test_reconnection_on_disconnect`: Automatic reconnection
- `test_multiple_sessions_share_connection`: Connection pooling
- `test_voltage_threshold_detection`: Detection triggers correctly
- `test_debounce_logic`: Prevents duplicate detections
- `test_channel_isolation`: Channels are independent
- `test_continuous_mode`: Continuous sampling mode
- `test_early_detection_rejection`: Rejects detections before video start
- `test_grace_period_allows_pre_trigger`: Grace period (2000ms) works
- `test_auto_stop_after_video_end`: Auto-stops after video duration

#### Known Issues Tested:
- **Issue #1**: Detection monitoring starts 3-4 seconds late (PRIMARY SUSPECT: Windows LabJack Bridge)
- **Issue #2**: Connection drops during long sessions
- **Issue #3**: Early detections (0-200ms) being rejected

---

### 2. WebSocket Event Tests (`test_websocket_events.py`)

#### Test Classes:
- **TestWebSocketEmission**: Real-time event emission
- **TestRoomBasedNotification**: Session-scoped notification
- **TestFallbackPolling**: HTTP polling fallback

#### Key Test Cases:
- `test_detection_event_emitted_via_websocket`: Events emitted in real-time
- `test_websocket_emission_includes_timing_data`: Timing data included
- `test_websocket_emission_disabled_when_configured`: Can disable WebSocket
- `test_websocket_emission_handles_errors_gracefully`: Error handling
- `test_detection_emitted_to_session_room`: Room-based emission
- `test_detection_events_available_via_http_endpoint`: Fallback polling
- `test_database_persistence_enables_polling`: DB-backed polling

#### Known Issues Tested:
- **Issue #4**: WebSocket events not reaching frontend
- **Issue #5**: Missing fallback when WebSocket fails
- **Issue #6**: No session-scoped rooms (all clients get all events)

---

### 3. Detection Queue Tests (`test_detection_queue.py`)

#### Test Classes:
- **TestDetectionQueue**: Queue basic operations
- **TestRaceConditionHandling**: Race condition scenarios
- **TestQueueHealthMonitoring**: Queue health monitoring

#### Key Test Cases:
- `test_enqueue_detection`: Detection queuing works
- `test_multiple_detections_queued`: Multiple detections handled
- `test_flush_assigns_video_id`: Queue flush assigns video_id
- `test_flush_handles_database_errors`: Graceful error handling
- `test_queue_metrics_tracking`: Metrics are accurate
- `test_detection_queued_when_video_id_unavailable`: Race condition handling
- `test_flush_after_video_lifecycle_completes`: Flush timing
- `test_queue_prevents_null_video_id_rate`: Eliminates NULL rate
- `test_queue_health_normal`: Health monitoring
- `test_queue_health_high_pending_warning`: Warning system

#### Known Issues Tested:
- **Issue #7**: 15% of detections have NULL video_id (1,426 out of 18,611)
- **Issue #8**: Detections arrive before `/video-started` completes
- **Issue #9**: SequenceVideoResult doesn't exist yet when detection captured

---

### 4. Integration Tests (`test_integration.py`)

#### Test Classes:
- **TestEndToEndDetectionFlow**: Complete pipeline
- **TestGroundTruthIntegration**: Ground truth matching
- **TestPerformanceBenchmarks**: Performance validation

#### Key Test Cases:
- `test_complete_detection_flow`: Hardware → Database flow
- `test_session_id_propagation`: Session ID maintained
- `test_video_timing_integration`: Video timing sync
- `test_detection_queue_integration`: Queue integration
- `test_ground_truth_matching_pipeline`: Ground truth matching
- `test_high_frequency_detection_handling`: Handles 1kHz sampling
- `test_multiple_concurrent_sessions`: 5 concurrent sessions
- `test_detection_latency_benchmark`: Latency < 100ms
- `test_memory_usage_stability`: Memory < 50MB increase

#### Performance Targets:
- **Latency**: Average < 100ms, Maximum < 150ms
- **Throughput**: Handle 1000 detections/second
- **Memory**: < 50MB growth over 3 seconds
- **Concurrent Sessions**: Support 5+ simultaneous sessions

---

## Test Data & Fixtures

### Mock Data (`conftest.py`):
- `mock_labjack_connection`: Standard hardware mock
- `mock_database_session`: Database mock
- `sample_detection_event`: Detection event fixture
- `sample_video_timing_config`: Video config
- `sample_test_session`: Test session data
- `mock_ground_truth_data`: Ground truth for matching

### Test Markers:
- `@pytest.mark.integration`: Integration tests (may be slow)
- `@pytest.mark.performance`: Performance benchmarks
- `@pytest.mark.slow`: Tests taking > 1 second

---

## Expected Test Results

### Coverage Targets:
- **Unit Tests**: > 80% line coverage
- **Integration Tests**: Critical paths covered
- **Edge Cases**: Boundary conditions validated

### Success Criteria:
1. All unit tests pass (connection, WebSocket, queue)
2. Integration tests demonstrate end-to-end flow
3. Performance benchmarks meet requirements
4. No race conditions or NULL video_id issues
5. Memory and connection stability verified

### Known Failures (Expected):
- Tests requiring actual LabJack hardware will be skipped
- Database tests skip if database unavailable
- WebSocket tests may skip in CI environment

---

## Test Execution Order

### Recommended Order:
1. **Unit Tests First**: Fast feedback on individual components
2. **Integration Tests**: Verify component interactions
3. **Performance Tests**: Validate under load

### Command Examples:
```bash
# Run all tests
pytest tests/hil-detection-pipeline/ -v

# Run specific test file
pytest tests/hil-detection-pipeline/test_labjack_connection.py -v

# Run with coverage
pytest tests/hil-detection-pipeline/ --cov=services --cov-report=html

# Run only integration tests
pytest tests/hil-detection-pipeline/ -m integration

# Run performance benchmarks
pytest tests/hil-detection-pipeline/ -m performance -s
```

---

## Test Maintenance

### Adding New Tests:
1. Identify functionality to test
2. Create test class in appropriate file
3. Add fixtures to `conftest.py` if reusable
4. Document in this test plan
5. Run locally before committing

### Updating Tests:
- Update tests when detection logic changes
- Verify all tests still pass after changes
- Update test plan documentation
- Review coverage reports

---

## References

- **Investigation Report**: `/home/rigade/Testing/ai-model-validation-platform/backend/docs/HIL_TIMING_INVESTIGATION_REPORT.md`
- **Queen's Fix Reports**: `/home/rigade/Testing/ai-model-validation-platform/backend/docs/QUEEN_*.md`
- **Detection Service**: `services/labjack_detection_service.py`
- **HIL Monitor**: `services/dedicated_labjack_monitor.py`
- **Detection Queue**: `services/detection_queue_service.py`

---

## Next Steps

1. Run test suite and verify all tests pass
2. Review coverage reports and add tests for gaps
3. Add tests for any new features or bug fixes
4. Document any test failures or issues
5. Share results with team for review
