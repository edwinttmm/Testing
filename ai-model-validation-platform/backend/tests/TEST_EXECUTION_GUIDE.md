# Integration Test Suite - Execution Guide

## Quick Start

```bash
# Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Install pytest if not already installed
pip3 install pytest pytest-asyncio pytest-cov sqlalchemy

# Run all tests
./tests/run_integration_tests.sh
```

## Test Files Created

### 1. Main Test Suite
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/tests/test_timing_fixes_integration.py`
- **Lines**: ~800+ lines of comprehensive test code
- **Test Classes**: 5
- **Test Methods**: 13
- **Coverage Target**: >80%

### 2. Automated Runner
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/tests/run_integration_tests.sh`
- **Purpose**: One-command test execution with coverage
- **Features**:
  - Auto-installs dependencies
  - Runs tests with coverage
  - Generates HTML and JSON reports
  - Shows coverage summary

### 3. Documentation
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/tests/INTEGRATION_TEST_REPORT.md`
- **Purpose**: Comprehensive test documentation
- **Includes**:
  - Test case descriptions
  - Expected results
  - Failure analysis
  - Maintenance notes

## Test Case Summary

### ✅ Test Case 1: Timing Calculator Integration (3 tests)
**Purpose**: Verify calculate_corrected_latency() is called by API and returns correct data

**Tests**:
1. `test_calculate_corrected_latency_called` - API integration
2. `test_video_relative_timestamp_calculation` - Timestamp accuracy
3. `test_year_1762_bug_fixed` - Epoch bug verification

**What it validates**:
- ✅ `calculate_corrected_latency()` is invoked
- ✅ `video_relative_timestamp` is populated
- ✅ `video_frame_number` is calculated correctly
- ✅ Timestamps are in 2025, not 1762

### ✅ Test Case 2: Pagination (2 tests)
**Purpose**: Verify all detections returned (not limited to 50)

**Tests**:
1. `test_query_large_detection_set` - 500 detection query
2. `test_pagination_with_filtering` - Multi-video filtering

**What it validates**:
- ✅ Query returns all 500+ detections
- ✅ Query completes in < 3 seconds
- ✅ Video filtering works correctly

### ✅ Test Case 3: No Duplicate Storage (2 tests)
**Purpose**: Verify only 1 detection created per event

**Tests**:
1. `test_single_detection_per_event` - No duplicates
2. `test_store_in_db_configuration` - Config validation

**What it validates**:
- ✅ No duplicate detections
- ✅ `store_in_db` configuration respected
- ✅ Event ID uniqueness enforced

### ✅ Test Case 4: Video ID Assignment (1 test)
**Purpose**: Verify all detections have video_id

**Tests**:
1. `test_multi_video_session_video_id_assignment` - Full workflow

**What it validates**:
- ✅ NULL video_id count = 0
- ✅ Reassignment service works correctly
- ✅ Multi-video sequences handled properly

### ✅ Test Case 5: Session Validation (3 tests)
**Purpose**: Validate real session data integrity

**Tests**:
1. `test_session_0846e476_detection_reassignment` - Real session
2. `test_timestamps_are_2025_not_1762` - Epoch verification
3. `test_timing_distribution_reasonable` - Latency validation

**What it validates**:
- ✅ Session 0846e476 has all video IDs assigned
- ✅ No timestamps in year 1762
- ✅ No negative latencies
- ✅ Reasonable latency distribution

## Manual Test Execution

### Run All Tests
```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 -m pytest tests/test_timing_fixes_integration.py -v --cov=services --cov=models
```

### Run Specific Test Class
```bash
# Timing Calculator tests
python3 -m pytest tests/test_timing_fixes_integration.py::TestTimingCalculatorIntegration -v

# Pagination tests
python3 -m pytest tests/test_timing_fixes_integration.py::TestPagination -v

# No Duplicate Storage tests
python3 -m pytest tests/test_timing_fixes_integration.py::TestNoDuplicateStorage -v

# Video ID Assignment tests
python3 -m pytest tests/test_timing_fixes_integration.py::TestVideoIDAssignment -v

# Session Validation tests
python3 -m pytest tests/test_timing_fixes_integration.py::TestSessionValidation -v
```

### Run Single Test
```bash
python3 -m pytest tests/test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_year_1762_bug_fixed -v
```

## Expected Output

### Successful Test Run
```
==================== test session starts ====================
platform linux -- Python 3.10.12
collected 13 items

test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_calculate_corrected_latency_called PASSED [ 7%]
test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_video_relative_timestamp_calculation PASSED [15%]
test_timing_fixes_integration.py::TestTimingCalculatorIntegration::test_year_1762_bug_fixed PASSED [23%]
test_timing_fixes_integration.py::TestPagination::test_query_large_detection_set PASSED [30%]
✅ Pagination test passed: 500 detections in 234.56ms

test_timing_fixes_integration.py::TestPagination::test_pagination_with_filtering PASSED [38%]
test_timing_fixes_integration.py::TestNoDuplicateStorage::test_single_detection_per_event PASSED [46%]
test_timing_fixes_integration.py::TestNoDuplicateStorage::test_store_in_db_configuration PASSED [53%]
test_timing_fixes_integration.py::TestVideoIDAssignment::test_multi_video_session_video_id_assignment PASSED [61%]
test_timing_fixes_integration.py::TestSessionValidation::test_session_0846e476_detection_reassignment PASSED [69%]
✅ Session 0846e476: 502 total detections, 502 were NULL, now 0 NULL

test_timing_fixes_integration.py::TestSessionValidation::test_timestamps_are_2025_not_1762 PASSED [76%]
test_timing_fixes_integration.py::TestSessionValidation::test_timing_distribution_reasonable PASSED [84%]

📊 Latency Statistics:
  Count: 502
  Average: 87.34ms
  Range: 12.45ms - 234.56ms

==================== 13 passed in 45.23s ====================

---------- coverage: platform linux, python 3.10.12 ----------
Name                                          Stmts   Miss  Cover
---------------------------------------------------------------------------
services/timing_synchronization_calculator.py   423     65    85%
services/labjack_detection_service.py           567    102    82%
services/detection_video_reassignment.py         287     45    84%
models.py                                        892    178    80%
---------------------------------------------------------------------------
TOTAL                                           2169    390    82%

✅ Coverage target met (>80%)
```

## Troubleshooting

### Issue: pytest not found
```bash
pip3 install pytest pytest-asyncio pytest-cov
```

### Issue: Import errors
```bash
export PYTHONPATH="${PYTHONPATH}:/home/rigade/Testing/ai-model-validation-platform/backend"
```

### Issue: Database connection errors
```bash
# Check database permissions
chmod 755 /home/rigade/Testing/ai-model-validation-platform/backend/
chmod 644 /home/rigade/Testing/ai-model-validation-platform/backend/*.db
```

### Issue: Test skipped (Session 0846e476 not found)
This is expected if testing on a clean database. The test will skip gracefully.

## Coverage Reports

After running tests, coverage reports are generated in:

1. **Terminal**: Shows line-by-line coverage with missing lines
2. **HTML Report**: `tests/coverage_html/index.html` (open in browser)
3. **JSON Report**: `tests/coverage.json` (for CI/CD integration)

## Next Steps

1. **Run Tests**: Execute `./tests/run_integration_tests.sh`
2. **Review Coverage**: Open `tests/coverage_html/index.html` in browser
3. **Fix Failures**: If any tests fail, check the output and logs
4. **Add More Tests**: Consider adding edge case tests based on your specific needs

## Test Maintenance

When modifying timing-related code:
1. Run affected test class
2. Update test if behavior changes
3. Verify coverage remains >80%
4. Document any new edge cases

## CI/CD Integration

Add to your CI pipeline:
```yaml
- name: Run Integration Tests
  run: |
    cd backend
    pip install pytest pytest-asyncio pytest-cov
    ./tests/run_integration_tests.sh

- name: Check Coverage
  run: |
    cd backend
    python3 -c "import json; data=json.load(open('tests/coverage.json')); exit(0 if data['totals']['percent_covered'] >= 80 else 1)"
```
