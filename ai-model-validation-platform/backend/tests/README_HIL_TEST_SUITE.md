# HIL Ground Truth Matching Test Suite

A comprehensive test suite to validate the Hardware-in-the-Loop (HIL) ground truth matching implementation for accurate latency calculation and detection validation.

## Overview

This test suite validates that the complete HIL test workflow properly matches LabJack detections against ground truth timing with accurate latency calculation, ensuring the system meets performance and accuracy requirements.

## Test Architecture

### Test Categories

1. **Ground Truth Matching Tests** (`test_ground_truth_matching.py`)
   - Core algorithm validation
   - Tolerance window testing
   - Latency calculation accuracy
   - Edge cases and error handling

2. **Video Timing Service Tests** (`test_video_timing_service.py`)
   - Video start time capture precision (±1ms)
   - Unix to video-relative time conversion
   - Frame synchronization accuracy
   - Timing performance benchmarks

3. **End-to-End HIL Workflow Tests** (`test_hil_workflow_end_to_end.py`)
   - Complete session lifecycle validation
   - Realistic 24-object test scenarios
   - Multiple performance scenarios
   - Integration testing

4. **Session Completion Logic Tests** (`test_session_completion_logic.py`)
   - Metrics calculation accuracy
   - TestResult generation validation
   - Database updates and integrity
   - Error handling and recovery

5. **Performance Benchmark Tests** (`test_performance_benchmarks.py`)
   - Large dataset processing (1000+ objects)
   - Memory usage validation (<500MB)
   - Processing time requirements (<5s)
   - Concurrent operation handling

6. **Database Integration Tests** (`test_database_integration.py`)
   - Model relationships and foreign keys
   - Transaction handling and rollback
   - Data integrity constraints
   - Index performance validation

## Key Test Scenarios

### Video Timing Synchronization
```python
def test_video_timing_capture():
    # Test video start time capture during session start
    # Verify Unix to video-relative timestamp conversion
    # Test timing accuracy within ±1ms
```

### Ground Truth Matching with Tolerance
```python
def test_ground_truth_matching_perfect_match():
    # LabJack detection at exactly ground truth time → 0ms latency

def test_ground_truth_matching_with_tolerance():
    # LabJack detection 50ms after ground truth → 50ms latency, within tolerance

def test_ground_truth_matching_outside_tolerance():
    # LabJack detection 150ms after ground truth → False Negative
```

### End-to-End HIL Workflow
```python
def test_complete_hil_workflow():
    # 1. Create test session with known ground truth (24 objects)
    # 2. Start session → capture video start time
    # 3. Simulate LabJack detections at specific video times
    # 4. Complete session → trigger ground truth matching
    # 5. Verify TestResult shows correct precision/recall/latency
```

### Expected Test Results Validation
- Ground truth at 1.0s + LabJack at 1.02s = +20ms latency (TP)
- Ground truth at 5.0s + no LabJack = False Negative
- Final metrics: 80% recall, 100% precision, 25ms avg latency

## Performance Requirements

### Timing Accuracy
- Video timing conversion: <10ms for 1000 detections
- Timestamp accuracy: ±1ms precision
- Ground truth matching: <100ms for 24 objects

### Processing Performance
- Session completion: <500ms total processing time
- Large dataset: <5s for 1000+ detections
- Memory usage: <500MB increase during processing

### Accuracy Requirements
- Ground truth matching tolerance: 100ms default
- Latency calculation accuracy: ±1ms
- Detection validation: >80% precision, >75% recall

## Running the Tests

### Quick Start
```bash
# Run all HIL tests
python tests/run_hil_test_suite.py

# Run with verbose output
python tests/run_hil_test_suite.py --verbose

# Run only critical tests
python tests/run_hil_test_suite.py --critical-only
```

### Specific Test Categories
```bash
# Run only ground truth matching tests
python tests/run_hil_test_suite.py --category ground_truth_matching

# Run performance benchmarks
python tests/run_hil_test_suite.py --benchmark

# Run end-to-end workflow tests
python tests/run_hil_test_suite.py --category hil_workflow
```

### Individual Test Files
```bash
# Run specific test file with pytest
python -m pytest tests/test_ground_truth_matching.py -v

# Run with performance profiling
python -m pytest tests/test_performance_benchmarks.py -v --durations=10

# Run with coverage reporting
python -m pytest tests/ --cov=src --cov-report=html
```

## Test Data and Mock Objects

### Ground Truth Test Scenarios
The test suite creates realistic scenarios with:
- **24 Ground Truth Objects**: Simulating typical HIL test session
- **Multiple VRU Types**: Pedestrians, cyclists, motorcyclists, wheelchairs
- **Varying Complexity**: Simple, moderate, and difficult detections
- **Realistic Timing**: Distributed across 12-second test videos

### LabJack Detection Patterns
Different performance scenarios:
- **Perfect System**: 100% detection rate, 0-20ms latency
- **Good System**: 92% detection rate, 10-60ms latency  
- **Realistic System**: 85% detection rate, 5-100ms latency
- **Challenging System**: 75% detection rate, 20-150ms latency

### Mock Data Factory Functions
```python
def create_realistic_ground_truth_scenario(db_session, video):
    # Creates 24 ground truth objects with realistic distribution
    
def create_realistic_labjack_detections(db_session, session, scenario_type):
    # Creates LabJack detections based on performance scenario
    
def create_large_dataset_for_performance(db_session, count):
    # Creates large datasets for performance testing
```

## Test Validation Criteria

### Functional Requirements
- ✅ Video timing capture within ±1ms accuracy
- ✅ Ground truth matching with configurable tolerance
- ✅ Accurate latency calculation in milliseconds
- ✅ Proper handling of edge cases and missing data
- ✅ Complete session lifecycle validation

### Performance Requirements
- ✅ Processing time <5s for large datasets (1000+ objects)
- ✅ Memory usage <500MB during processing
- ✅ Concurrent operation support
- ✅ Database query performance optimization

### Integration Requirements
- ✅ End-to-end workflow validation
- ✅ Database integrity and transactions
- ✅ Service layer integration
- ✅ Error handling and recovery

## Test Output and Reporting

### Test Suite Runner Output
```
🚀 Starting HIL Test Suite
Timestamp: 2024-01-15T10:30:00
Categories: ground_truth_matching, video_timing, hil_workflow, session_completion, performance, database

============================================================
Running GROUND_TRUTH_MATCHING Tests
Description: Ground truth matching algorithm validation
File: tests/test_ground_truth_matching.py
Critical: Yes
============================================================

✅ GROUND_TRUTH_MATCHING TESTS PASSED
   Duration: 2.45s
   Tests: 12/12 passed

[... other categories ...]

================================================================================
HIL TEST SUITE FINAL REPORT
================================================================================
🎉 OVERALL RESULT: SUCCESS

📊 SUMMARY STATISTICS:
   Total Duration: 25.67s
   Test Categories: 6/6 passed
   Individual Tests: 58/58 passed
   Success Rate: 100.0%
   Critical Failures: 0

📋 CATEGORY BREAKDOWN:
   ground_truth_matching ✅ PASS   🔥 CRITICAL  (2.45s)
   video_timing         ✅ PASS   🔥 CRITICAL  (1.89s)
   hil_workflow         ✅ PASS   🔥 CRITICAL  (8.23s)
   session_completion   ✅ PASS   🔥 CRITICAL  (3.12s)
   performance          ✅ PASS   📝 OPTIONAL (7.34s)
   database            ✅ PASS   🔥 CRITICAL  (2.64s)

🎯 TEST COVERAGE VALIDATION:
   Video Timing Synchronization    ✅
   Ground Truth Matching           ✅
   End-to-End HIL Workflow         ✅
   Session Completion Logic        ✅
   Database Integration            ✅
   Performance Benchmarks          ✅

✨ All critical tests passed! HIL system ready for deployment.
```

### Individual Test Output Examples
```python
# Ground Truth Matching Test Results
test_ground_truth_matching_perfect_match PASSED
test_ground_truth_matching_with_tolerance PASSED  
test_ground_truth_matching_outside_tolerance PASSED
test_complete_hil_workflow PASSED
Expected: 4 TP, 0 FP, 1 FN → 100% precision, 80% recall ✅

# Performance Benchmark Results
Large Dataset Performance:
  Ground Truth Objects: 1000
  Detection Events: 5000
  Processing Time: 3.24s
  Memory Increase: 245.3MB
  Success Rate: 87.2%
  Average Latency: 45.7ms
```

## Troubleshooting

### Common Issues

**Test Failures in Ground Truth Matching**
- Check video timing configuration is properly set
- Verify ground truth objects have correct timestamps
- Ensure tolerance window is appropriate for test scenario

**Performance Test Failures**
- Verify system has sufficient memory (>2GB available)
- Check database performance and indexing
- Ensure no other heavy processes running during tests

**Database Integration Failures**
- Verify database schema matches model definitions
- Check foreign key constraints are properly configured
- Ensure transaction handling works correctly

### Debug Mode
```bash
# Run with detailed debug output
python -m pytest tests/test_ground_truth_matching.py -v -s --tb=long

# Run with profiling
python -m pytest tests/test_performance_benchmarks.py --profile

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: HIL Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    - name: Run HIL Test Suite
      run: |
        cd backend
        python tests/run_hil_test_suite.py --critical-only
    - name: Run Performance Benchmarks
      run: |
        cd backend  
        python tests/run_hil_test_suite.py --benchmark
```

## Contributing

### Adding New Tests
1. Follow existing test structure and naming conventions
2. Include both positive and negative test cases
3. Add performance benchmarks for new features
4. Update test documentation and expected results

### Test Categories
- **Critical Tests**: Must pass for deployment
- **Performance Tests**: Validate system performance
- **Integration Tests**: End-to-end validation
- **Unit Tests**: Individual component validation

---

## Summary

This comprehensive test suite ensures the HIL ground truth matching system works correctly end-to-end, validating timing accuracy, detection matching, performance requirements, and data integrity. The test suite provides confidence that the system will perform accurately in production environments with real LabJack hardware and video timing synchronization.

**Key Validations:**
- ✅ 24-object ground truth scenarios with <100ms matching tolerance
- ✅ Video timing synchronization with ±1ms accuracy  
- ✅ Processing performance <5s for large datasets
- ✅ Memory usage <500MB during processing
- ✅ Database integrity and transaction handling
- ✅ End-to-end workflow validation with realistic scenarios

The test suite serves as both validation and documentation of the HIL system's capabilities and requirements.