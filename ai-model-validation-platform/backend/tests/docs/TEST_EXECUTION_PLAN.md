# Stream Mode Integration Test Execution Plan

## Overview

This document provides a structured test execution plan for validating the LabJack stream mode implementation. Tests are designed to expose critical issues and validate fixes.

---

## Test Suite Structure

### File Location
```
tests/hil-detection-pipeline/test_stream_mode_integration.py
```

### Test Classes (6 classes, 15+ tests)

1. **TestStreamModeHighSpeed** - High-speed data capture validation
2. **TestStreamBufferManagement** - Buffer overflow and memory tests
3. **TestStreamFallbackBehavior** - Fallback and error recovery
4. **TestStreamThreadSafety** - Concurrency and race conditions
5. **TestStreamPerformance** - Latency and throughput validation
6. **TestStreamConfiguration** - Configuration flexibility

---

## Prerequisites

### Environment Setup

```bash
# 1. Navigate to backend directory
cd /home/rigade/Testing/ai-model-validation-platform/backend

# 2. Activate virtual environment (if using venv)
source venv/bin/activate

# 3. Install test dependencies
pip install pytest pytest-asyncio

# 4. Verify pytest installation
pytest --version
```

### Hardware Requirements

- **Optional**: LabJack T7 device (tests work with mock fallback)
- **Required**: 4GB+ RAM (for buffer overflow tests)
- **Required**: Multi-core CPU (for thread safety tests)

---

## Test Execution Commands

### 1. Run All Tests (Comprehensive)

```bash
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v
```

**Expected Duration**: ~90 seconds
**Expected Results**:
- Some tests PASS (confirming current behavior)
- Some tests FAIL (exposing critical issues)
- All tests output diagnostic information

### 2. Run Specific Test Class

```bash
# High-speed streaming tests
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamModeHighSpeed -v

# Buffer management tests
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamBufferManagement -v

# Fallback behavior tests
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamFallbackBehavior -v

# Thread safety tests
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamThreadSafety -v

# Performance tests
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamPerformance -v

# Configuration tests
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamConfiguration -v
```

### 3. Run Specific Test

```bash
# Test 1000 Hz capture accuracy
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamModeHighSpeed::test_stream_1000hz_capture_accuracy -v -s

# Test buffer overflow handling
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamBufferManagement::test_buffer_overflow_handling -v -s
```

### 4. Run with Detailed Output

```bash
# Show all print statements and debug output
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v -s
```

### 5. Run Performance Benchmarks Only

```bash
# Run tests marked with @pytest.mark.performance
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v -m performance
```

### 6. Generate Test Report

```bash
# Create HTML test report
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v --html=tests/docs/test_report.html --self-contained-html

# Create JUnit XML report
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v --junitxml=tests/docs/test_results.xml
```

---

## Expected Test Results

### Phase 1: Current Implementation (Before Fixes)

#### Tests that PASS ✅ (Confirming Issues):

1. **test_stream_1000hz_capture_accuracy**
   - Status: ✅ PASS (with assertion change)
   - Confirms: System runs at 24 Hz, not 1000 Hz
   - Output: "ISSUE #1 CONFIRMED: Capture rate is 24 Hz (expected 1000 Hz)"

2. **test_buffer_overflow_handling**
   - Status: ✅ PASS
   - Confirms: Unbounded buffer stores all events
   - Output: "ISSUE #3 CONFIRMED: Unbounded buffer stored X events"

3. **test_stream_failure_fallback_to_polling**
   - Status: ✅ PASS
   - Confirms: No stream mode exists, only polling
   - Output: "ISSUE #5 CONFIRMED: No stream mode - always polling"

4. **test_concurrent_access_to_detection_buffer**
   - Status: ✅ PASS (may not always fail due to GIL)
   - Confirms: No explicit thread synchronization
   - Output: "ISSUE #7 WARNING: No thread synchronization"

#### Tests that FAIL ❌ (Exposing Critical Gaps):

1. **test_stream_data_consistency**
   - Status: ❌ FAIL
   - Expected: 1ms intervals (1000 Hz)
   - Actual: 42ms intervals (24 Hz)
   - Output: "ISSUE #2 CONFIRMED: Intervals don't match streaming"

2. **test_buffer_circular_behavior**
   - Status: ❌ FAIL
   - Expected: Circular buffer limits to 1000 events
   - Actual: Unbounded growth to 1200+ events
   - Output: "ISSUE #4 CONFIRMED: No circular buffer"

3. **test_sustained_1000hz_performance**
   - Status: ❌ FAIL
   - Expected: 1000 Hz sustained for 10 seconds
   - Actual: 24 Hz maximum
   - Output: "ISSUE #10 CONFIRMED: System runs at 24 Hz"

### Phase 2: After Stream Mode Implementation

#### Expected Changes:

1. **test_stream_1000hz_capture_accuracy** → ✅ PASS
   - Sample rate: 990-1010 Hz (within 1%)
   - Evidence of true streaming mode

2. **test_stream_data_consistency** → ✅ PASS
   - Inter-sample intervals: ~1ms
   - Hardware timestamps used

3. **test_buffer_circular_behavior** → ✅ PASS
   - Buffer limited to configured max size
   - Old events dropped when full

4. **test_stream_failure_fallback_to_polling** → ✅ PASS
   - Falls back to polling on stream error
   - Mode indicator shows "polling" or "streaming"

5. **test_sustained_1000hz_performance** → ✅ PASS
   - Sustained 1000 Hz for 10+ seconds
   - No data loss or degradation

---

## Test Execution Schedule

### Day 1: Baseline Testing (Before Fixes)

**Objective**: Document current behavior and confirm issues

**Tasks**:
1. Run complete test suite
2. Capture all output and diagnostic messages
3. Document which tests pass/fail
4. Generate baseline performance metrics

**Commands**:
```bash
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v -s > baseline_results.txt 2>&1
```

**Expected Outcome**:
- 60-70% tests pass (confirming issues)
- 30-40% tests fail (exposing gaps)
- All 12 issues confirmed via test output

### Day 2-7: Implementation Phase

**Tasks**:
1. Implement stream mode (Issue #1)
2. Add circular buffer (Issue #3)
3. Add thread synchronization (Issue #7)
4. Add fallback logic (Issue #5)
5. Add error recovery (Issue #6)

**Validation**:
Run affected test classes after each fix:
```bash
# After implementing stream mode
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamModeHighSpeed -v

# After implementing circular buffer
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamBufferManagement -v
```

### Day 8: Final Validation

**Objective**: Verify all issues are resolved

**Tasks**:
1. Run complete test suite
2. Verify 100% pass rate
3. Run performance benchmarks
4. Generate final test report

**Commands**:
```bash
# Full test suite
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v --html=final_report.html

# Performance benchmarks
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v -m performance
```

**Success Criteria**:
- ✅ 100% test pass rate
- ✅ 1000 Hz sustained capture confirmed
- ✅ <5ms latency achieved
- ✅ No memory leaks in 1-hour test
- ✅ All 12 issues resolved

---

## Performance Benchmarks

### Benchmark 1: Throughput Test

**Command**:
```bash
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamModeBenchmarks::test_throughput_1000hz_10_seconds -v -s
```

**Metrics Captured**:
- Total samples collected
- Duration (seconds)
- Throughput (samples/sec)
- Gap from target (1000 Hz)

**Current Baseline** (Before Fixes):
```
Duration: 10.00s
Total Samples: 240
Throughput: 24.00 samples/sec
Expected: 1000 samples/sec
Gap: 976 samples/sec
```

**Target** (After Fixes):
```
Duration: 10.00s
Total Samples: 10,000
Throughput: 1000.00 samples/sec
Expected: 1000 samples/sec
Gap: 0 samples/sec
```

### Benchmark 2: Latency Test

**Command**:
```bash
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamPerformance::test_stream_latency_sub_100ms -v -s
```

**Metrics Captured**:
- Detection-to-record latency (ms)
- Best case latency
- Worst case latency
- Average latency

**Current Baseline**:
```
Best Case: 0ms
Worst Case: 42ms
Average: 21ms
HIL Requirement (<100ms): ✅ PASS
Optimal (<5ms): ❌ FAIL
```

**Target**:
```
Best Case: <1ms
Worst Case: <5ms
Average: <3ms
HIL Requirement (<100ms): ✅ PASS
Optimal (<5ms): ✅ PASS
```

### Benchmark 3: Memory Usage Test

**Command**:
```bash
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamBufferManagement::test_buffer_overflow_handling -v -s
```

**Metrics Captured**:
- Memory usage over time
- Buffer size growth
- Max memory reached

**Current Baseline**:
```
Duration: 5 seconds at 24 Hz
Events Stored: 120
Memory Used: ~24 KB (unbounded)
```

**Target** (With Circular Buffer):
```
Duration: 3600 seconds (1 hour) at 1000 Hz
Events Stored: 10,000 (max buffer size)
Memory Used: ~2 MB (bounded)
```

---

## Debugging Failed Tests

### If Tests Fail Unexpectedly:

#### 1. Check Import Errors
```bash
python -c "from services.simple_labjack_detection import SimpleLabJackDetector"
```

#### 2. Check LabJack Hardware Connection
```bash
python -c "import sys; sys.path.insert(0, 'src'); from services.simple_labjack_detection import SimpleLabJackDetector; d = SimpleLabJackDetector(); d._connect_labjack()"
```

#### 3. Run Single Test with Full Debug Output
```bash
pytest tests/hil-detection-pipeline/test_stream_mode_integration.py::TestStreamModeHighSpeed::test_stream_1000hz_capture_accuracy -v -s --tb=long
```

#### 4. Check Python Version
```bash
python --version  # Should be 3.8+
```

#### 5. Check Dependencies
```bash
pip list | grep -E "pytest|mock"
```

---

## Continuous Integration Setup

### GitHub Actions Workflow

Create `.github/workflows/stream_mode_tests.yml`:

```yaml
name: Stream Mode Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python 3.10
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-asyncio pytest-html
        pip install -r backend/requirements.txt

    - name: Run stream mode integration tests
      run: |
        cd backend
        pytest tests/hil-detection-pipeline/test_stream_mode_integration.py -v --html=test_report.html --self-contained-html

    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: backend/test_report.html
```

---

## Acceptance Criteria

### Definition of Done

Stream mode implementation is considered **complete** when:

✅ **Functional Requirements**:
- [ ] Stream mode captures at 1000 Hz ±1%
- [ ] Hardware timestamps used for all samples
- [ ] Circular buffer limits memory to <100 MB
- [ ] Automatic fallback to polling on stream failure
- [ ] Mode indicator shows "streaming" or "polling"

✅ **Quality Requirements**:
- [ ] 100% test pass rate
- [ ] No race conditions detected
- [ ] No memory leaks in 1-hour test
- [ ] Thread-safe concurrent access

✅ **Performance Requirements**:
- [ ] Sustained 1000 Hz for 10+ seconds
- [ ] <5ms average latency
- [ ] <10% CPU usage at 1000 Hz
- [ ] <100 MB memory usage (with circular buffer)

✅ **Documentation Requirements**:
- [ ] API documentation updated
- [ ] Configuration guide created
- [ ] Migration guide from polling to streaming
- [ ] Performance tuning guide

---

## Support and Escalation

### If Tests Fail During Implementation:

**Level 1 - Self-Service**:
1. Check test output for diagnostic messages
2. Review code review report for issue details
3. Run individual tests to isolate problem
4. Check logs for error details

**Level 2 - Team Support**:
1. Share test output with team
2. Review implementation with senior developer
3. Pair programming session
4. Code review before merge

**Level 3 - Architecture Review**:
1. Review approach with architect
2. Consider alternative implementations
3. Update design documents
4. Revise timeline if needed

---

## Additional Resources

### Documentation:
- [LabJack LJM User's Guide](https://labjack.com/support/software/api/ljm)
- [LabJack Stream Mode Documentation](https://labjack.com/support/software/api/ljm/stream-mode)
- [Python Threading Documentation](https://docs.python.org/3/library/threading.html)

### Code Examples:
- `/home/rigade/Testing/ai-model-validation-platform/backend/tests/docs/STREAM_MODE_CODE_REVIEW_REPORT.md` - Appendix A

### Test Files:
- `/home/rigade/Testing/ai-model-validation-platform/backend/tests/hil-detection-pipeline/test_stream_mode_integration.py`

---

**Document Version**: 1.0
**Last Updated**: 2025-11-14
**Owner**: QA Team
**Reviewers**: Development Team, Architecture Team
