# Test Execution Guide - Priority 3 Fixes

## Overview

This guide covers running the comprehensive test suites for:
1. **Recall Calculation Fix** - Session vs per-video metrics
2. **Constant Voltage Mode Fix** - Debounce bypass for 100% detection

## Test Files

```
tests/
├── test_recall_calculation_fix.py       # 12 test cases
├── test_constant_voltage_mode_fix.py    # 10 test cases
├── test_fixes_integration.py            # 10 integration tests
└── fixtures/
    └── test_data_fixtures.py            # Shared test data
```

## Prerequisites

```bash
# Install pytest if not already installed
pip install pytest pytest-cov pytest-mock

# Or use requirements-test.txt
pip install -r tests/requirements-test.txt
```

## Running Tests

### Run All Tests
```bash
# From backend directory
pytest tests/test_*fix*.py -v

# With detailed output
pytest tests/test_*fix*.py -vv
```

### Run Specific Test Suite
```bash
# Recall calculation tests only
pytest tests/test_recall_calculation_fix.py -v

# Constant voltage mode tests only
pytest tests/test_constant_voltage_mode_fix.py -v

# Integration tests only
pytest tests/test_fixes_integration.py -v
```

### Run Single Test
```bash
# Run specific test by name
pytest tests/test_recall_calculation_fix.py::TestRecallCalculationFix::test_session_fa204ef2_data_validation -v

# Run specific test class
pytest tests/test_constant_voltage_mode_fix.py::TestConstantVoltageModeBasics -v
```

### Run with Coverage
```bash
# Generate HTML coverage report
pytest tests/test_*fix*.py --cov=services --cov=routers --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Expected Output

### Successful Run
```
tests/test_recall_calculation_fix.py::TestRecallCalculationFix::test_single_video_recall_calculation PASSED
tests/test_recall_calculation_fix.py::TestRecallCalculationFix::test_multi_video_session_recall_not_equal_to_per_video PASSED
tests/test_recall_calculation_fix.py::TestRecallCalculationFix::test_session_fa204ef2_data_validation PASSED
...
============================= 32 passed in 2.45s ==============================
```

### With Coverage Report
```
---------- coverage: platform linux, python 3.12.0 -----------
Name                                           Stmts   Miss  Cover
------------------------------------------------------------------
services/ground_truth_matching_service.py       450     45    90%
services/labjack_detection_service.py           380     38    90%
routers/test_sessions.py                        520     52    90%
------------------------------------------------------------------
TOTAL                                          1350    135    90%
```

## Test Categories

### 1. Recall Calculation Tests
**File:** `test_recall_calculation_fix.py`

**What's Tested:**
- Single video recall calculation
- Multi-video session aggregation
- Session fa204ef2 data validation
- API response structure
- F1 score calculation
- Database storage
- Frontend data binding

**Key Assertions:**
```python
# Session recall must differ from per-video recall
assert session_recall != video_1_recall

# Correct formula: TP / (TP + FN)
assert recall == pytest.approx(0.3595, abs=0.001)

# API structure validation
assert "sessionMetrics" in response
assert response["sessionMetrics"]["recall"] != response["perVideoMetrics"][0]["recall"]
```

### 2. Constant Voltage Mode Tests
**File:** `test_constant_voltage_mode_fix.py`

**What's Tested:**
- Normal mode debounce behavior
- Constant voltage mode debounce bypass
- Frame-by-frame detection at 24 FPS
- 100% detection rate achievement
- Backward compatibility
- Frame gap pattern reproduction

**Key Assertions:**
```python
# Normal mode: debounce blocks detections
assert len(detections) == 2  # Only 2 of 5 frames

# Constant voltage mode: all frames detected
assert len(detections) == 5  # All 5 frames

# 100% detection rate
assert detections == total_frames
assert detection_rate == 100.0
```

### 3. Integration Tests
**File:** `test_fixes_integration.py`

**What's Tested:**
- Both fixes working together
- Complete workflow validation
- Performance improvements
- Database consistency
- Regression testing
- Stress testing (large sessions)

**Key Assertions:**
```python
# Both fixes applied
assert detection_rate == 1.0  # 100%
assert session_recall == pytest.approx(0.45)  # Improved from 0.36

# Performance improvement
assert improvement == pytest.approx(25.0)  # 25% improvement
```

## Debugging Failed Tests

### View Full Traceback
```bash
pytest tests/test_recall_calculation_fix.py -v --tb=long
```

### Run with Print Statements
```bash
pytest tests/test_recall_calculation_fix.py -v -s
```

### Stop on First Failure
```bash
pytest tests/test_recall_calculation_fix.py -v -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

## Continuous Integration

### GitHub Actions Example
```yaml
name: Test Priority 3 Fixes

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.12
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r tests/requirements-test.txt
      - name: Run tests
        run: |
          pytest tests/test_*fix*.py -v --cov=services --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Test Data

### Real Session Data
- **Session ID:** fa204ef2-9d8b-4480-9692-86e338c1218a
- **Issue:** Displayed 100% recall, actual 36%
- **Cause:** Per-video recall shown instead of session

### Mock Data Location
- **Fixtures:** `tests/fixtures/test_data_fixtures.py`
- **Constants:** Imported in each test file

### Example Fixture Usage
```python
from tests.fixtures.test_data_fixtures import (
    SESSION_FA204EF2_DATA,
    CONSTANT_VOLTAGE_SCENARIO,
    generate_constant_voltage_detections
)

def test_with_fixture():
    data = SESSION_FA204EF2_DATA
    assert data["actual_recall"] == 0.3595
    assert data["displayed_recall_bug"] == 1.0
```

## Performance Benchmarks

### Expected Test Times
- Recall calculation tests: < 1 second
- Constant voltage mode tests: < 1 second
- Integration tests: < 2 seconds
- **Total:** < 5 seconds

### Stress Test Thresholds
- Large session (2400 frames): < 0.5 seconds
- High frequency (10 kHz): < 0.1 seconds

## Validation Checklist

Before deployment, ensure:

- [ ] All 32 tests pass
- [ ] Code coverage > 90%
- [ ] No regressions in existing tests
- [ ] API response structure validated
- [ ] Database consistency verified
- [ ] Performance benchmarks met
- [ ] Documentation updated

## Troubleshooting

### Import Errors
```bash
# Add backend to Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/backend"
```

### Database Connection Errors
```bash
# Use test database
export DATABASE_URL="sqlite:///test.db"
```

### Mock Failures
```bash
# Install additional dependencies
pip install pytest-mock unittest-mock
```

## Additional Resources

- **Test Report:** `docs/TEST_SUITE_COMPREHENSIVE_REPORT.md`
- **Bug Analysis:** `docs/RECALL_METRIC_BUG_ANALYSIS.md`
- **Constant Voltage:** `CONSTANT_VOLTAGE_MODE.md`
- **Integration:** `INTEGRATION_SUMMARY.md`

## Contact

For questions or issues with tests:
- Review test documentation
- Check existing test output
- Consult comprehensive report

---

**Last Updated:** 2025-11-24
**Test Coverage:** 32 test cases
**Status:** ✅ Ready for Execution
