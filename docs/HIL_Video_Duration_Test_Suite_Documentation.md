# HIL Video Duration Auto-Stop Test Suite Documentation

## Overview

This comprehensive test suite validates the critical HIL (Hardware-in-the-Loop) video duration auto-stop system that ensures LabJack monitoring continues for the full video duration plus grace period, preventing early termination and missed detections.

## Problem Statement

The HIL validation system was experiencing missed detections due to early LabJack monitoring termination. The issue occurred when:

1. Video duration was not properly resolved from multiple sources
2. LabJack auto-stop timer was set incorrectly
3. Grace period calculations were inconsistent
4. Database fallback scenarios failed silently

## Solution

The test suite validates a robust video duration handling system with:

- **Multi-source duration resolution**: `video_data["duration_s"]` → `video_data["duration"]` → database fallback
- **Grace period calculation**: `max(0.25, min(2.0, duration * 0.05))`
- **Auto-stop timing**: `auto_stop_time = video_duration + grace_period`
- **Comprehensive error handling**: Invalid duration rejection and logging

## Test Suite Architecture

### Core Files

```
tests/
├── test_hil_video_duration.py              # Main test module
├── test_hil_video_duration_fixtures.py     # Test fixtures and utilities  
├── run_hil_video_duration_tests.py         # Test runner with reporting
├── validate_hil_duration_tests.py          # Validation script
└── docs/HIL_Video_Duration_Test_Suite_Documentation.md
```

### Test Categories

#### 1. Duration Resolution Tests (`TestGetVideoDuration`)

Tests the `get_video_duration()` function with all source patterns:

```python
def test_duration_from_video_data_duration_s_primary(self):
    """Test duration extraction from video_data['duration_s'] (primary source)"""
    
def test_duration_from_video_data_duration_fallback(self):
    """Test duration extraction from video_data['duration'] (fallback source)"""
    
def test_duration_from_database_fallback(self):
    """Test duration extraction from database when video_data has no duration"""
```

**Key Assertions:**
- Primary source (`duration_s`) takes precedence
- Fallback to `duration` when `duration_s` unavailable  
- Database query only when payload sources fail
- Invalid durations (< 0.1s or > 7200s) rejected
- Type conversion from string to float handled

#### 2. Auto-Stop Timer Tests (`TestLabJackAutoStopTiming`)

Tests LabJack auto-stop timer calculations with grace periods:

```python
def test_grace_period_calculation(self):
    """Test grace period calculation for various video durations"""
    test_cases = [
        (0.5, 0.25),   # Very short: min grace (0.25s)
        (10.0, 0.5),   # Medium: 5% = 0.5s  
        (40.0, 2.0),   # Long: max grace (2.0s)
    ]

def test_auto_stop_timing_accuracy(self):
    """Test LabJack auto-stop timing for various video durations"""
```

**Grace Period Formula:**
```python
grace_period = max(0.25, min(2.0, duration * 0.05))
auto_stop_time = video_duration + grace_period
```

#### 3. Database Fallback Tests (`TestDatabaseFallbackScenarios`) 

Tests database query scenarios:

```python
def test_database_query_success(self):
    """Test successful database query for video duration"""
    
def test_database_video_not_found(self):
    """Test database query when video not found"""
    
def test_database_query_exception(self):
    """Test handling of database query exceptions"""
```

#### 4. Integration Tests (`TestHILVideoTimingIntegration`)

Tests integration with HIL components:

```python
def test_video_start_with_duration_resolution(self):
    """Test video start endpoint resolves duration correctly"""
    
def test_session_metadata_includes_duration(self):
    """Test that session metadata properly includes resolved duration"""
```

#### 5. Edge Cases & Error Handling

- Invalid duration values (negative, zero, NaN)
- Very short videos (0.1 seconds) 
- Very long videos (2 hours)
- Database connection failures
- Malformed video metadata

#### 6. End-to-End Workflow Tests

Tests complete auto-stop workflow:

```python
def test_complete_auto_stop_workflow(self):
    """Test complete LabJack auto-stop workflow from duration to timer"""
    
def test_auto_stop_prevents_early_termination(self):
    """Test that auto-stop timer prevents early LabJack termination"""
```

## Test Fixtures and Data

### Video Test Fixtures

The `VideoFixtureFactory` provides comprehensive test data:

```python
# Short duration videos (< 5 seconds)
short_videos = VideoFixtureFactory.create_short_videos()

# Medium duration videos (5-60 seconds)  
medium_videos = VideoFixtureFactory.create_medium_videos()

# Long duration videos (> 60 seconds)
long_videos = VideoFixtureFactory.create_long_videos()

# Edge cases (boundary conditions)
edge_cases = VideoFixtureFactory.create_edge_case_videos()

# Invalid durations (negative, zero, too long)
invalid_videos = VideoFixtureFactory.create_invalid_videos()
```

### Mock Objects

- **Database Mocks**: Success, failure, exception scenarios
- **LabJack Service Mocks**: Connected/disconnected states
- **Timing Service Mocks**: Precision timing simulation
- **HIL Session Mocks**: Active/completed session states

## Usage Instructions

### Quick Validation

```bash
# Validate test suite functionality
python3 validate_hil_duration_tests.py
```

### Run All Tests

```bash
# Run complete test suite
python3 run_hil_video_duration_tests.py

# Verbose output
python3 run_hil_video_duration_tests.py --verbose

# Save detailed report
python3 run_hil_video_duration_tests.py --output=test_report.json
```

### Run Specific Categories

```bash
# Test only duration resolution
python3 run_hil_video_duration_tests.py --category=duration_resolution

# Test only auto-stop timing  
python3 run_hil_video_duration_tests.py --category=auto_stop_timing

# Test only database fallback
python3 run_hil_video_duration_tests.py --category=database_fallback
```

### List Available Categories

```bash
python3 run_hil_video_duration_tests.py --list-categories
```

## Expected Results

### Successful Test Run Output

```
HIL VIDEO DURATION AUTO-STOP TEST RESULTS
===============================================
Total Tests: 45
Passed: 45
Failed: 0
Errors: 0
Skipped: 0
Success Rate: 100.0%

Execution Time: 2.34 seconds

Test Categories:
TestGetVideoDuration              12/12 (100.0%)
TestLabJackAutoStopTiming         8/8 (100.0%)
TestHILVideoTimingIntegration     6/6 (100.0%)
TestDatabaseFallbackScenarios     7/7 (100.0%)
TestVideoTimingServiceDurationHandling  5/5 (100.0%)
TestErrorHandlingAndValidation    4/4 (100.0%)
TestLabJackAutoStopEndToEnd      3/3 (100.0%)

Test Fixtures: 24/24 valid

✅ ALL TESTS PASSED - HIL auto-stop system validated
```

## Key Test Scenarios

### Scenario 1: Primary Duration Source
```python
video_data = {"duration_s": 10.0, "filename": "test.mp4"}
result = get_video_duration(video_id, db, video_data)
assert result == 10.0  # Uses duration_s directly
```

### Scenario 2: Fallback Duration Source
```python
video_data = {"duration": 15.0, "filename": "test.mp4"}  # No duration_s
result = get_video_duration(video_id, db, video_data)
assert result == 15.0  # Falls back to duration
```

### Scenario 3: Database Fallback
```python
video_data = {"filename": "test.mp4"}  # No duration fields
# Mock database returns video with duration=20.0
result = get_video_duration(video_id, mock_db, video_data)
assert result == 20.0  # Uses database value
```

### Scenario 4: Grace Period Calculation
```python
duration = 30.0
grace = max(0.25, min(2.0, duration * 0.05))  # = 1.5s
auto_stop = duration + grace  # = 31.5s
```

### Scenario 5: Auto-Stop Prevents Early Termination
```python
video_ends_at = 10.0    # Video finishes
labjack_stops_at = 10.5  # Grace period allows extra monitoring
# Detections between 10.0-10.5s are still captured
```

## Validation Criteria

The test suite validates these critical requirements:

1. **Duration Resolution Accuracy**: All three source levels work correctly
2. **Grace Period Compliance**: 5% of duration, min 0.25s, max 2.0s
3. **Auto-Stop Timing**: Prevents early LabJack termination
4. **Error Handling**: Invalid durations rejected gracefully
5. **Database Fallback**: Handles connection failures and missing data
6. **Integration Compatibility**: Works with existing HIL components

## Debugging Test Failures

### Common Failure Scenarios

1. **Import Errors**: Ensure all dependencies available
2. **Mock Setup Issues**: Verify mock objects configured correctly  
3. **Assertion Failures**: Check expected vs actual values
4. **Database Mock Problems**: Ensure proper query chain setup

### Debug Tips

```python
# Enable verbose logging
logging.basicConfig(level=logging.DEBUG)

# Run single test for focused debugging
python3 -m unittest test_hil_video_duration.TestGetVideoDuration.test_duration_from_video_data_duration_s_primary

# Use breakpoints for step-through debugging
import pdb; pdb.set_trace()
```

## Contributing

When adding new tests:

1. Follow existing naming conventions
2. Use appropriate fixtures from `VideoFixtureFactory`
3. Include both positive and negative test cases
4. Add docstrings explaining test purpose
5. Update this documentation for new test categories

## Technical Implementation Notes

### Duration Validation Range
- **Minimum**: 0.1 seconds (prevents instantaneous videos)
- **Maximum**: 7200 seconds (2 hours maximum test duration)

### Grace Period Constraints
- **Minimum**: 0.25 seconds (prevents immediate cutoff)
- **Maximum**: 2.0 seconds (prevents excessive delays)
- **Calculation**: 5% of video duration, clamped to min/max

### Database Query Pattern
```python
video = db.query(Video).filter(Video.id == video_id).first()
if video and video.duration:
    return float(video.duration)
```

### Error Handling Strategy
- Log all duration resolution attempts
- Graceful degradation for missing data
- Clear error messages for debugging
- No exceptions raised (returns None for failures)

## Performance Considerations

- Test suite runs in ~2-3 seconds
- Mock objects minimize database overhead
- Fixtures pre-generated for efficiency
- Parallel test execution supported

## Future Enhancements

Potential test suite improvements:

1. **Performance Testing**: Large-scale duration processing
2. **Concurrency Testing**: Multiple simultaneous sessions
3. **Real Hardware Testing**: Actual LabJack integration
4. **Load Testing**: High-frequency duration requests
5. **Regression Testing**: Automated CI/CD integration

---

This test suite provides comprehensive validation of the HIL video duration auto-stop system, ensuring robust and reliable operation that prevents missed detections due to early monitoring termination.