# HIL Detection Pipeline Test Execution Instructions

**Quick Reference Guide for Running Tests**

---

## Prerequisites

### 1. Python Environment
```bash
# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Verify Python version (3.12+)
python --version
```

### 2. Install Test Dependencies
```bash
# Install pytest and plugins
pip install pytest pytest-cov pytest-asyncio pytest-mock psutil

# Verify installation
pytest --version
```

### 3. Environment Setup
```bash
# Set working directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Verify test files exist
ls -la tests/hil-detection-pipeline/
```

---

## Running Tests

### Option 1: Run All Tests (Recommended First)
```bash
# Run complete test suite with verbose output
pytest tests/hil-detection-pipeline/ -v

# Expected output:
# tests/hil-detection-pipeline/test_labjack_connection.py::TestLabJackConnection::test_connection_initialization PASSED
# tests/hil-detection-pipeline/test_websocket_events.py::TestWebSocketEmission::test_detection_event_emitted_via_websocket PASSED
# ...
# ==================== X passed in Y.YYs ====================
```

### Option 2: Run Specific Test File
```bash
# LabJack connection tests only
pytest tests/hil-detection-pipeline/test_labjack_connection.py -v

# WebSocket tests only
pytest tests/hil-detection-pipeline/test_websocket_events.py -v

# Detection queue tests only
pytest tests/hil-detection-pipeline/test_detection_queue.py -v

# Integration tests only
pytest tests/hil-detection-pipeline/test_integration.py -v
```

### Option 3: Run Specific Test Class or Method
```bash
# Run single test class
pytest tests/hil-detection-pipeline/test_labjack_connection.py::TestLabJackConnection -v

# Run single test method
pytest tests/hil-detection-pipeline/test_labjack_connection.py::TestLabJackConnection::test_connection_initialization -v
```

### Option 4: Run Tests by Marker
```bash
# Run only integration tests
pytest tests/hil-detection-pipeline/ -m integration -v

# Run only performance tests
pytest tests/hil-detection-pipeline/ -m performance -v -s

# Run all except slow tests
pytest tests/hil-detection-pipeline/ -m "not slow" -v
```

---

## Test Output Options

### Verbose Output (-v)
```bash
pytest tests/hil-detection-pipeline/ -v
# Shows each test name and result
```

### Extra Verbose (-vv)
```bash
pytest tests/hil-detection-pipeline/ -vv
# Shows test names, parameters, and assertion details
```

### Show Print Statements (-s)
```bash
pytest tests/hil-detection-pipeline/ -s
# Useful for performance benchmarks that print timing data
```

### Short Traceback (--tb=short)
```bash
pytest tests/hil-detection-pipeline/ --tb=short
# Shorter error messages for failed tests
```

### Stop on First Failure (-x)
```bash
pytest tests/hil-detection-pipeline/ -x
# Stops after first test failure for faster debugging
```

---

## Coverage Reports

### Generate Coverage Report
```bash
# Run tests with coverage tracking
pytest tests/hil-detection-pipeline/ --cov=services --cov-report=html

# Open coverage report
# Open: htmlcov/index.html in browser
```

### Coverage Options
```bash
# Terminal coverage report
pytest tests/hil-detection-pipeline/ --cov=services --cov-report=term

# Coverage with missing lines highlighted
pytest tests/hil-detection-pipeline/ --cov=services --cov-report=term-missing

# XML coverage (for CI/CD)
pytest tests/hil-detection-pipeline/ --cov=services --cov-report=xml
```

---

## Debugging Failed Tests

### Show Full Traceback
```bash
pytest tests/hil-detection-pipeline/ --tb=long
# Shows complete error traceback
```

### Drop into Debugger on Failure
```bash
pytest tests/hil-detection-pipeline/ --pdb
# Opens Python debugger (pdb) on test failure
```

### Print Test Output
```bash
pytest tests/hil-detection-pipeline/ -s -vv
# Shows all print statements and detailed output
```

### Run Single Failing Test
```bash
# Isolate and debug specific test
pytest tests/hil-detection-pipeline/test_labjack_connection.py::TestLabJackConnection::test_connection_initialization -vv -s
```

---

## Performance Benchmarking

### Run Performance Tests with Timing
```bash
# Run performance tests with output
pytest tests/hil-detection-pipeline/test_integration.py::TestPerformanceBenchmarks -v -s

# Expected output includes:
# Latency Benchmark:
#   Average: 45.23ms
#   Maximum: 67.89ms
#   Samples: 42
#
# Memory Usage:
#   Initial: 125.45 MB
#   Final: 138.23 MB
#   Increase: 12.78 MB
```

### Performance Test Targets
- **Latency**: Average < 100ms
- **Throughput**: 1000 detections/second
- **Memory Growth**: < 50MB over 3 seconds
- **Concurrent Sessions**: 5+ simultaneous

---

## Continuous Integration

### CI/CD Command
```bash
# Run all tests with coverage and XML output
pytest tests/hil-detection-pipeline/ \
  --cov=services \
  --cov-report=xml \
  --cov-report=term \
  --junitxml=test-results.xml \
  -v
```

### Expected Exit Codes
- `0`: All tests passed
- `1`: One or more tests failed
- `2`: Test execution interrupted
- `3`: Internal error
- `4`: pytest usage error

---

## Test Data & Fixtures

### Available Fixtures (see conftest.py)
- `mock_labjack_connection`: Mock hardware connection
- `mock_database_session`: Mock database
- `sample_detection_event`: Example detection
- `sample_video_timing_config`: Video configuration
- `mock_websocket_emit`: Mock WebSocket function
- `mock_ground_truth_data`: Ground truth data

### Using Fixtures in Tests
```python
def test_example(mock_labjack_connection, sample_detection_event):
    # Fixtures automatically provided by pytest
    assert mock_labjack_connection.is_connected() == True
    assert sample_detection_event.voltage == 3.5
```

---

## Troubleshooting

### Issue: ModuleNotFoundError
```bash
# Solution: Ensure PYTHONPATH includes backend directory
export PYTHONPATH="${PYTHONPATH}:/home/rigade/Testing/ai-model-validation-platform/backend"
```

### Issue: "Database not available" Skip
```bash
# Expected behavior - tests skip if database unavailable
# To enable: Ensure PostgreSQL is running and DATABASE_URL is set
```

### Issue: "No module named 'services'"
```bash
# Solution: Run tests from backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend
pytest tests/hil-detection-pipeline/ -v
```

### Issue: Async Test Warnings
```bash
# Solution: Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Then run tests normally
pytest tests/hil-detection-pipeline/ -v
```

---

## Test Execution Checklist

Before running tests:
- [ ] Virtual environment activated
- [ ] Test dependencies installed (`pytest`, `pytest-cov`, `pytest-asyncio`)
- [ ] Working directory is `/backend`
- [ ] PYTHONPATH includes backend directory (if needed)

After running tests:
- [ ] All tests passed or skipped appropriately
- [ ] Coverage report generated (if applicable)
- [ ] Performance benchmarks meet targets (if applicable)
- [ ] No unexpected failures or errors

---

## Quick Reference Commands

```bash
# Most common commands

# 1. Run all tests
pytest tests/hil-detection-pipeline/ -v

# 2. Run with coverage
pytest tests/hil-detection-pipeline/ --cov=services --cov-report=html -v

# 3. Run specific file
pytest tests/hil-detection-pipeline/test_labjack_connection.py -v

# 4. Run performance benchmarks
pytest tests/hil-detection-pipeline/ -m performance -s -v

# 5. Debug failing test
pytest tests/hil-detection-pipeline/test_<file>.py::TestClass::test_method -vv -s

# 6. Stop on first failure
pytest tests/hil-detection-pipeline/ -x -v

# 7. Run integration tests only
pytest tests/hil-detection-pipeline/ -m integration -v
```

---

## Next Steps After Running Tests

1. **Review Results**: Check for any unexpected failures
2. **Coverage Analysis**: Review coverage report for gaps
3. **Performance Review**: Verify benchmarks meet targets
4. **Document Issues**: Report any test failures or anomalies
5. **Share Results**: Provide summary to team

---

## Support & Documentation

- **Test Plan**: See `TEST_PLAN.md` for test coverage details
- **Investigation Reports**: `/backend/docs/HIL_TIMING_INVESTIGATION_REPORT.md`
- **Source Code**: Review services under test in `/backend/services/`
- **pytest Documentation**: https://docs.pytest.org/

---

**Created:** 2025-11-14
**Agent:** Test Engineering Specialist
**Last Updated:** 2025-11-14
