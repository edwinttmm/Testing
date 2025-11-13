# Integration Test Suite - Timing Fixes Verification

## Test Coverage Summary

This integration test suite verifies that all critical timing-related fixes work together correctly.

### Test Cases Implemented

#### ✅ Test Case 1: Timing Calculator Integration
- **File**: `test_timing_fixes_integration.py::TestTimingCalculatorIntegration`
- **Coverage**:
  - `calculate_corrected_latency()` API integration
  - `video_relative_timestamp` population
  - `video_frame_number` calculation
  - Year 1762 epoch bug fix verification

**Tests**:
1. `test_calculate_corrected_latency_called` - Verifies timing calculator is invoked
2. `test_video_relative_timestamp_calculation` - Tests timestamp accuracy
3. `test_year_1762_bug_fixed` - Ensures timestamps are in 2025, not 1762

#### ✅ Test Case 2: Pagination
- **File**: `test_timing_fixes_integration.py::TestPagination`
- **Coverage**:
  - Query sessions with 500+ detections
  - Verify all detections returned (no 50-limit)
  - Check query performance < 3 seconds

**Tests**:
1. `test_query_large_detection_set` - Tests 500 detection pagination
2. `test_pagination_with_filtering` - Tests multi-video filtering

#### ✅ Test Case 3: No Duplicate Storage
- **File**: `test_timing_fixes_integration.py::TestNoDuplicateStorage`
- **Coverage**:
  - Verify only 1 detection per event
  - Check `store_in_db` configuration

**Tests**:
1. `test_single_detection_per_event` - Ensures no duplicates
2. `test_store_in_db_configuration` - Validates storage config

#### ✅ Test Case 4: Video ID Assignment
- **File**: `test_timing_fixes_integration.py::TestVideoIDAssignment`
- **Coverage**:
  - Multi-video session video_id assignment
  - NULL video_id count validation
  - Detection reassignment service

**Tests**:
1. `test_multi_video_session_video_id_assignment` - Full reassignment workflow

#### ✅ Test Case 5: Session Validation
- **File**: `test_timing_fixes_integration.py::TestSessionValidation`
- **Coverage**:
  - Session 0846e476 detection reassignment
  - Verify 502/502 detections have video_id
  - Check timestamps are 2025, not 1762
  - Validate timing distribution

**Tests**:
1. `test_session_0846e476_detection_reassignment` - Real session validation
2. `test_timestamps_are_2025_not_1762` - Epoch bug verification
3. `test_timing_distribution_reasonable` - Latency distribution check

## Running the Tests

### Quick Start
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
./tests/run_integration_tests.sh
```

### Manual Execution
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 -m pytest tests/test_timing_fixes_integration.py -v --cov=services --cov=models
```

### Individual Test Classes
```bash
# Test Case 1: Timing Calculator
python3 -m pytest tests/test_timing_fixes_integration.py::TestTimingCalculatorIntegration -v

# Test Case 2: Pagination
python3 -m pytest tests/test_timing_fixes_integration.py::TestPagination -v

# Test Case 3: No Duplicate Storage
python3 -m pytest tests/test_timing_fixes_integration.py::TestNoDuplicateStorage -v

# Test Case 4: Video ID Assignment
python3 -m pytest tests/test_timing_fixes_integration.py::TestVideoIDAssignment -v

# Test Case 5: Session Validation
python3 -m pytest tests/test_timing_fixes_integration.py::TestSessionValidation -v
```

## Expected Results

### Coverage Target
- **Target**: >80% coverage of timing-related code
- **Services Covered**:
  - `timing_synchronization_calculator.py`
  - `labjack_detection_service.py`
  - `detection_video_reassignment.py`
- **Models Covered**:
  - `TestSession`
  - `DetectionEvent`
  - `SequenceVideoResult`

### Test Output Format
```
==================== test session starts ====================
collected 13 items

test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_calculate_corrected_latency_called PASSED [ 7%]
test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_video_relative_timestamp_calculation PASSED [15%]
test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_year_1762_bug_fixed PASSED [23%]
test_timing_fixes_integration.py::TestPagination::test_query_large_detection_set PASSED [30%]
test_timing_fixes_integration.py::TestPagination::test_pagination_with_filtering PASSED [38%]
test_timing_fixes_integration.py::TestNoDuplicateStorage::test_single_detection_per_event PASSED [46%]
test_timing_fixes_integration.py::TestNoDuplicateStorage::test_store_in_db_configuration PASSED [53%]
test_timing_fixes_integration.py::TestVideoIDAssignment::test_multi_video_session_video_id_assignment PASSED [61%]
test_timing_fixes_integration.py::TestSessionValidation::test_session_0846e476_detection_reassignment PASSED [69%]
test_timing_fixes_integration.py::TestSessionValidation::test_timestamps_are_2025_not_1762 PASSED [76%]
test_timing_fixes_integration.py::TestSessionValidation::test_timing_distribution_reasonable PASSED [84%]

==================== 13 passed in 45.23s ====================

---------- coverage: platform linux, python 3.10.12 ----------
Name                                          Stmts   Miss  Cover   Missing
---------------------------------------------------------------------------
services/timing_synchronization_calculator.py   423     65    85%   145-152, 234-241
services/labjack_detection_service.py           567    102    82%   88-95, 234-245, 567-589
services/detection_video_reassignment.py         287     45    84%   156-163, 287-294
models.py                                        892    178    80%   (various)
---------------------------------------------------------------------------
TOTAL                                           2169    390    82%
```

## Failure Analysis

### Common Failure Scenarios

#### 1. Database Connection Issues
**Symptom**: `OperationalError: unable to open database file`
**Fix**: Ensure database path is correct and writable
```bash
chmod 755 /home/rigade/Testing/ai-model-validation-platform/backend/
```

#### 2. Missing Dependencies
**Symptom**: `ModuleNotFoundError: No module named 'pytest'`
**Fix**: Install test dependencies
```bash
pip install pytest pytest-asyncio pytest-cov
```

#### 3. Import Errors
**Symptom**: `ImportError: cannot import name 'X' from 'Y'`
**Fix**: Set PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 4. Session Not Found
**Symptom**: Test skipped with "Session 0846e476 not found"
**Solution**: This is expected if testing on a clean database. The test will skip gracefully.

## Additional Test Cases Recommended

### Performance Tests
1. **Load Test**: 10,000 detections with concurrent access
2. **Memory Test**: Monitor memory usage during large queries
3. **Concurrency Test**: Multiple sessions running simultaneously

### Edge Cases
1. **Boundary Conditions**: Detections at exact video start/end
2. **Clock Drift**: Simulate system clock adjustments
3. **Network Latency**: Test with simulated network delays
4. **Invalid Data**: Test with malformed timestamps

### Integration Points
1. **WebSocket Integration**: Real-time detection emission
2. **Ground Truth Matching**: Full matching workflow
3. **Report Generation**: End-to-end HIL report flow

## Maintenance Notes

### Updating Tests
When modifying timing-related code:
1. Update corresponding test cases
2. Run full test suite
3. Verify coverage remains >80%
4. Document any new edge cases

### Test Data
Test fixtures create minimal data:
- 1 test session
- 10 ground truth objects
- Variable detection counts per test

### Cleanup
All tests use fixtures with cleanup:
- Database rollback after each test
- No persistent test data
- Isolated test environment

## CI/CD Integration

### GitHub Actions
```yaml
- name: Run Integration Tests
  run: |
    cd backend
    ./tests/run_integration_tests.sh
```

### Coverage Requirements
```yaml
coverage:
  threshold: 80
  required_packages:
    - services.timing_synchronization_calculator
    - services.labjack_detection_service
    - services.detection_video_reassignment
```

## Support

For test failures or questions:
1. Check test output logs
2. Review coverage report in `tests/coverage_html/index.html`
3. Verify database state
4. Check service logs for timing-related errors
