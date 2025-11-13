# Validation Logic and Threshold Documentation

## Executive Summary

This document details all thresholds, validation rules, and pass/fail criteria used throughout the AI Model Validation Platform. All threshold values and logic have been extracted from production code and tests.

**Last Updated**: 2025-11-11
**System Version**: v8
**Coverage**: Backend validation services, schemas, models, and test suites

---

## Table of Contents

1. [Ground Truth Matching Thresholds](#ground-truth-matching-thresholds)
2. [Latency Validation Thresholds](#latency-validation-thresholds)
3. [Performance Metrics Criteria](#performance-metrics-criteria)
4. [Video Validation Rules](#video-validation-rules)
5. [Detection Event Validation](#detection-event-validation)
6. [Temporal Matching Logic](#temporal-matching-logic)
7. [Multi-Video Sequence Validation](#multi-video-sequence-validation)
8. [Test Assertions and Expectations](#test-assertions-and-expectations)
9. [Edge Case Handling](#edge-case-handling)

---

## 1. Ground Truth Matching Thresholds

### 1.1 Default Tolerance Windows

**File**: `services/ground_truth_matching_service.py`

```python
# Default temporal tolerance for matching
default_tolerance_ms = 100  # milliseconds

# Configurable per session
session.tolerance_ms = 100  # Can be customized per test session
```

**Usage**:
- Ground truth objects and detections are matched if their timestamps differ by ≤ tolerance
- Tolerance converts to seconds: `tolerance_seconds = tolerance_ms / 1000.0`

### 1.2 Temporal IoU Calculation

**File**: `test_ground_truth_matching_service.py` lines 245-263

```python
# Perfect match: 0ms difference
iou_score = 1.0  # when timestamps exactly match

# Half tolerance: 50ms difference (50% of 100ms)
iou_score ≈ 0.75

# At tolerance boundary: 99ms difference
iou_score ≈ 0.5

# Outside tolerance: >100ms difference
iou_score = 0.0  # No match
```

**Formula**:
```
temporal_diff = abs(detection_time - ground_truth_time)
if temporal_diff <= tolerance:
    iou_score = 1.0 - (temporal_diff / tolerance) * 0.5
else:
    iou_score = 0.0
```

### 1.3 Expected Test Results

**File**: `test_ground_truth_matching_service.py` lines 59-84

Sample data expectations:
- **Total Ground Truth**: 24 objects
- **Total Detections**: 22 events
- **True Positives**: 18 (matched detections)
- **False Positives**: 4 (unmatched detections)
- **False Negatives**: 6 (unmatched ground truth)

**Latency Distribution**:
```python
# Example detection latencies (23ms average)
latencies = [23.0, 25.0, 23.0, 23.0, 23.0, ...]  # milliseconds
mean_latency = 23.0 ms
```

---

## 2. Latency Validation Thresholds

### 2.1 Core Latency Thresholds

**File**: `services/latency_validation_service.py`

```python
# Default latency threshold for Pass/Fail
default_threshold_ms = 50.0  # milliseconds

# Timeout threshold (detection too late)
timeout_threshold_ms = 5000.0  # 5 seconds

# Histogram binning for distribution analysis
histogram_bin_size_ms = 5.0  # 5ms bins
```

### 2.2 Latency Result Classification

**File**: `services/latency_validation_service.py` lines 149-162

```python
if latency_ms < 0:
    # Detection BEFORE video start - ERROR
    result = LatencyResult.ERROR

elif latency_ms > timeout_threshold_ms:  # > 5000ms
    # Detection too late - TIMEOUT
    result = LatencyResult.TIMEOUT

elif latency_ms <= threshold:  # ≤ 50ms (default)
    # Within threshold - PASS
    result = LatencyResult.PASS

else:  # > 50ms (default)
    # Exceeds threshold - FAIL
    result = LatencyResult.FAIL
```

### 2.3 Latency Pass Rate Calculation

**File**: `latency_validation_service.py` lines 276

```python
pass_rate_percent = (pass_count / total_measurements) * 100.0

# Example:
# 18 passed / 22 total = 81.8% pass rate
```

### 2.4 Statistical Percentiles

**File**: `latency_validation_service.py` lines 315-317

```python
# 95th percentile latency
percentile_95_ms = calculate_percentile(sorted_latencies, 95)

# 99th percentile latency
percentile_99_ms = calculate_percentile(sorted_latencies, 99)

# Standard deviation
std_deviation_ms = statistics.stdev(valid_latencies)  # if > 1 sample
```

---

## 3. Performance Metrics Criteria

### 3.1 Precision, Recall, F1 Score

**File**: `validation_service.py` lines 185-189

```python
# Precision: What % of detections are correct?
precision = TP / (TP + FP) if (TP + FP) > 0 else 0

# Recall: What % of ground truth was detected?
recall = TP / (TP + FN) if (TP + FN) > 0 else 0

# F1 Score: Harmonic mean of precision and recall
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

# Accuracy: Overall correctness
accuracy = TP / total_ground_truth if total_ground_truth > 0 else 0
```

### 3.2 Expected Metric Values (From Tests)

**File**: `test_ground_truth_matching_service.py` lines 284-290

```python
# Example with 3 TP, 1 FP, 1 FN
expected_precision = 3 / (3 + 1) = 0.75  # 75%
expected_recall = 3 / (3 + 1) = 0.75     # 75%
expected_f1 = 2 * (0.75 * 0.75) / (0.75 + 0.75) = 0.75  # 75%
```

### 3.3 Coverage Thresholds (From Tests)

**File**: `tests/test_phase4_solves_all_issues.py`

```python
# Test coverage requirements (not validation thresholds)
statements_coverage = 80%  # Minimum 80%
branches_coverage = 75%    # Minimum 75%
functions_coverage = 80%   # Minimum 80%
lines_coverage = 80%       # Minimum 80%
```

---

## 4. Video Validation Rules

### 4.1 Video Duration Limits

**File**: `migrations/data_validation_utils.py`

```python
if video_duration <= 0:
    # CRITICAL: Invalid duration
    validation_status = "FAILED"

elif video_duration > 7200:  # 2 hours
    # WARNING: Very long video
    validation_status = "WARNING"
```

### 4.2 Frame Rate (FPS) Validation

**File**: `migrations/data_validation_utils.py` lines 74-90

```python
if fps <= 0:
    # CRITICAL: Invalid FPS
    validation_status = "FAILED"

elif fps < 15:
    # WARNING: Low FPS (below standard)
    validation_status = "WARNING"

elif fps > 120:
    # WARNING: Very high FPS
    validation_status = "WARNING"
```

**Standard FPS**: 24-30 fps (expected range)

### 4.3 Playback Timing Validation

**File**: `data_validation_utils.py` lines 101-128

```python
if playback_start_time < 946684800:  # Year 2000 timestamp
    # CRITICAL: Invalid timestamp (before year 2000)
    validation_status = "FAILED"

# Playback duration tolerance
playback_duration_diff = abs(playback_duration - video_duration)
if playback_duration_diff > 5.0:  # 5 second tolerance
    # WARNING: Playback duration mismatch
    validation_status = "WARNING"
```

### 4.4 Video Resolution Validation

**File**: `data_validation_utils.py` lines 257

```python
if width <= 0 or height <= 0:
    # CRITICAL: Invalid resolution
    validation_status = "FAILED"

# Minimum resolution (from requirements)
required_resolution_min = "640x480"

# Maximum for sanity checks
if width > 10000 or height > 10000:
    # WARNING: Unreasonably large resolution
    validation_status = "WARNING"
```

---

## 5. Detection Event Validation

### 5.1 Timestamp Validation

**File**: `data_validation_utils.py` lines 181-207

```python
# Video-relative timestamp must be non-negative
if video_relative_timestamp < 0:
    # CRITICAL: Detection before video start
    validation_status = "FAILED"

# Timestamp consistency check
timestamp_diff = abs(detection_timestamp - expected_timestamp)
if timestamp_diff > 1.0:  # 1 second tolerance
    # CRITICAL: Large timestamp inconsistency
    validation_status = "FAILED"

elif timestamp_diff > 0.1:  # 100ms tolerance
    # WARNING: Minor timestamp inconsistency
    validation_status = "WARNING"

# Latency validation
if latency_ms > 10000:  # More than 10 seconds late
    # WARNING: Very high latency
    validation_status = "WARNING"
```

### 5.2 Confidence Score Validation

**File**: `data_validation_utils.py` lines 299-306

```python
if not 0.0 <= confidence <= 1.0:
    # CRITICAL: Invalid confidence range
    validation_status = "FAILED"

elif confidence < 0.1:
    # WARNING: Very low confidence
    validation_status = "WARNING"
```

### 5.3 Bounding Box Validation

**File**: `data_validation_utils.py` lines 266

```python
# Coordinates must be non-negative
if x < 0 or y < 0:
    # CRITICAL: Negative coordinates
    validation_status = "FAILED"

# Dimensions must be positive
if width <= 0 or height <= 0:
    # CRITICAL: Invalid dimensions
    validation_status = "FAILED"

# Sanity check for extremely large boxes
if width > 10000 or height > 10000:
    # WARNING: Unreasonably large bounding box
    validation_status = "WARNING"

# Aspect ratio check
aspect_ratio = width / height
if aspect_ratio > 50 or aspect_ratio < 0.02:
    # WARNING: Extreme aspect ratio
    validation_status = "WARNING"
```

---

## 6. Temporal Matching Logic

### 6.1 Tolerance Window Variations

**File**: `test_ground_truth_matching_service.py` lines 296-316

```python
# Strict tolerance: 50ms
tolerance_strict = 50  # milliseconds
# Expected: High precision, lower recall

# Standard tolerance: 100ms (default)
tolerance_standard = 100  # milliseconds
# Expected: Balanced precision/recall

# Relaxed tolerance: 200ms
tolerance_relaxed = 200  # milliseconds
# Expected: Higher recall, lower precision

# Rule: Relaxed tolerance >= Standard tolerance >= Strict tolerance
# In matches: tp_relaxed >= tp_standard >= tp_strict
```

### 6.2 Matching Algorithm Logic

**File**: `ground_truth_matching_service.py`

```python
# Step 1: For each detection
for detection in detections:
    best_match = None
    min_time_diff = float('inf')

    # Step 2: Find nearest ground truth within tolerance
    for ground_truth in ground_truths:
        time_diff = abs(detection.timestamp - ground_truth.timestamp)

        if time_diff <= tolerance_seconds and time_diff < min_time_diff:
            best_match = ground_truth
            min_time_diff = time_diff

    # Step 3: Classify match
    if best_match:
        match_type = "TP"  # True Positive
        latency_ms = (detection.timestamp - best_match.timestamp) * 1000
    else:
        match_type = "FP"  # False Positive
        latency_ms = None

# Step 4: Unmatched ground truth = False Negatives
for ground_truth in ground_truths:
    if not ground_truth.matched:
        match_type = "FN"  # False Negative
```

### 6.3 Empty Data Handling

**File**: `test_ground_truth_matching_service.py` lines 318-352

```python
# Empty ground truth → All detections are FP
if len(ground_truth) == 0:
    fp_count = len(detections)
    tp_count = 0
    fn_count = 0

# Empty detections → All ground truth are FN
if len(detections) == 0:
    fn_count = len(ground_truth)
    tp_count = 0
    fp_count = 0

# Both empty → Zero metrics
if len(ground_truth) == 0 and len(detections) == 0:
    precision = 0.0
    recall = 0.0
    f1_score = 0.0
```

---

## 7. Multi-Video Sequence Validation

### 7.1 Sequence Timing Validation

**File**: `data_validation_utils.py` lines 366

```python
# Duration consistency across videos
duration_diff = abs(actual_duration - expected_duration)
if duration_diff > 5.0:  # 5 second tolerance
    # WARNING: Duration mismatch in sequence
    validation_status = "WARNING"
```

### 7.2 Per-Video Metrics

**File**: `schemas.py` lines 685-694

```python
class GroundTruthMetrics:
    """Per-video ground truth validation metrics"""
    total_ground_truth: int  # Total GT objects for this video
    true_positives: int      # Correctly matched detections
    false_positives: int     # Detections without GT match
    false_negatives: int     # GT objects without detection
    precision: float         # TP / (TP + FP)
    recall: float           # TP / (TP + FN)
    f1_score: float         # Harmonic mean of precision/recall
```

### 7.3 Latency Aggregation Rules

**File**: `schemas.py` lines 675-683

```python
# Per-video latency statistics
avg_latency_ms: float        # Average latency for this video
max_latency_ms: float        # Maximum latency for this video
min_latency_ms: float        # Minimum latency for this video
pass_rate_percent: float     # Pass rate for this video
latency_threshold_ms: int    # Threshold used for this video

# Pass/Fail determination
passed_detections: int       # Count of detections ≤ threshold
failed_detections: int       # Count of detections > threshold
```

---

## 8. Test Assertions and Expectations

### 8.1 Phase 4 Validation Tests

**File**: `test_phase4_solves_all_issues.py`

```python
# Concurrent operations (Issue #1)
concurrent_threads = 100
expected_success_rate = 100%  # All operations must succeed

# Race condition tolerance
acceptable_conflicts = 0  # Zero race conditions allowed

# Clock skew immunity (Issue #3)
ntp_adjustment_seconds = 5.0  # Simulated clock jump
expected_correct_assignment = 100%  # Must still assign correctly

# Late detection handling (Issue #6)
late_detection_delay_ms = 500  # Detection 500ms after video end
expected_assignment_success = True  # Must still assign to correct video

# N+1 query prevention (Issue #7)
max_queries_per_video = 5
videos_tested = 3
max_total_queries = 15  # 5 queries × 3 videos
```

### 8.2 Timing Validation Test Expectations

**File**: `test_timing_validation_api.py`

```python
# Video duration validation
VIDEO_DURATION_SECONDS = 10.0
MAX_FRAME_NUMBER = 240  # 24 fps × 10 seconds

# Detection count expectations
EXPECTED_TOTAL_DETECTIONS = 502
EXPECTED_VIDEO1_DETECTIONS = 251
EXPECTED_VIDEO2_DETECTIONS = 251

# Timestamp range validation
valid_timestamp_range = (0.0, VIDEO_DURATION_SECONDS)

# Frame number validation
valid_frame_range = (0, MAX_FRAME_NUMBER)

# Latency validation
negative_latencies_allowed = 0  # Zero negative latencies
```

### 8.3 Ground Truth Matching Test Expectations

**File**: `test_ground_truth_matching_service.py`

```python
# Sample test data (24 GT objects, 22 detections)
total_ground_truth = 24
total_detections = 22
expected_true_positives = 18
expected_false_positives = 4
expected_false_negatives = 6

# Expected metrics
expected_precision = 18 / (18 + 4) = 0.818  # 81.8%
expected_recall = 18 / (18 + 6) = 0.750     # 75.0%
expected_f1_score = 0.783                    # 78.3%

# Latency expectations
expected_mean_latency = 23.5 ms
expected_std_latency = 2.1 ms
expected_max_latency = 28.0 ms
expected_min_latency = 20.0 ms
within_tolerance_percentage = 100.0%  # All within 100ms
```

---

## 9. Edge Case Handling

### 9.1 Boundary Conditions

**File**: Multiple validation files

```python
# Timestamp boundaries
year_2000_epoch = 946684800  # Minimum valid timestamp
video_timestamp_min = 0.0
video_timestamp_max = video_duration

# Confidence boundaries
confidence_min = 0.0
confidence_max = 1.0

# Latency boundaries
latency_min = -∞  # Can be negative (error condition)
latency_error_threshold = 0.0  # Negative latencies are errors
latency_pass_threshold = 50.0  # Default
latency_timeout_threshold = 5000.0  # 5 seconds

# Frame number boundaries
frame_min = 0
frame_max = total_frames - 1
```

### 9.2 Error Handling Thresholds

**File**: `data_validation_utils.py` lines 561-567

```python
# System health determination
if critical_count > 0:
    system_health = "CRITICAL"
elif error_count > 0:
    system_health = "ERROR"
elif warning_count > 5:
    system_health = "WARNING"
elif warning_count > 0:
    system_health = "WARNING_LOW"
else:
    system_health = "HEALTHY"
```

### 9.3 Performance Degradation Thresholds

**File**: `validation_middleware.py`

```python
# Memory cleanup triggers
max_validation_errors_stored = 1000
max_performance_metrics_stored = 1000

# Response time monitoring
slow_operation_threshold_ms = 5000  # 5 seconds

# Success rate monitoring
if total_requests > 0:
    success_rate = successful_requests / total_requests
    if success_rate < 0.8:  # Below 80%
        # WARNING: System degradation
        send_alert()
```

### 9.4 Data Quality Checks

**File**: `comprehensive_validation_service.py`

```python
# Spatial validation
if bbox.x > 3840 or bbox.y > 2160:  # 4K resolution limits
    # WARNING: Box outside 4K frame
    validation_status = "WARNING"

# Temporal validation
if timestamp > 86400 * 365:  # More than 1 year
    # WARNING: Unreasonably large timestamp
    validation_status = "WARNING"

# Frame rate sanity check
if fps > 240 or fps < 1:  # Unreasonable FPS
    # WARNING: Unusual frame rate
    validation_status = "WARNING"

# Detection quality
if quality_score < 0.7:
    # WARNING: Low quality detection
    validation_status = "WARNING"

# Processing delay
if processing_delay_ms > 100:
    # WARNING: High processing delay
    validation_status = "WARNING"
```

---

## 10. Summary of All Thresholds

### Critical Thresholds (PASS/FAIL)

| Metric | Threshold | Unit | File Reference |
|--------|-----------|------|----------------|
| Latency Pass/Fail | ≤ 50.0 | ms | `latency_validation_service.py:114` |
| Latency Timeout | > 5000.0 | ms | `latency_validation_service.py:123` |
| Temporal Tolerance (Default) | 100 | ms | `ground_truth_matching_service.py:169` |
| Negative Latency | < 0 | ms | Always ERROR |
| Video Timestamp Min | 0.0 | seconds | Multiple files |
| Confidence Range | 0.0 - 1.0 | ratio | `data_validation_utils.py:299` |

### Performance Metrics

| Metric | Calculation | Expected Range |
|--------|-------------|----------------|
| Precision | TP / (TP + FP) | 0.0 - 1.0 |
| Recall | TP / (TP + FN) | 0.0 - 1.0 |
| F1 Score | 2 × (P × R) / (P + R) | 0.0 - 1.0 |
| Accuracy | TP / Total GT | 0.0 - 1.0 |
| Pass Rate | Passed / Total × 100 | 0.0 - 100.0% |

### Warning Thresholds

| Metric | Threshold | Severity | File Reference |
|--------|-----------|----------|----------------|
| Low Confidence | < 0.1 | WARNING | `data_validation_utils.py:306` |
| High Latency | > 10000 ms | WARNING | `data_validation_utils.py:207` |
| Duration Mismatch | > 5.0 s | WARNING | `data_validation_utils.py:128` |
| Timestamp Drift | > 100 ms | WARNING | `data_validation_utils.py:168` |
| Low FPS | < 15 fps | WARNING | `data_validation_utils.py:82` |
| High FPS | > 120 fps | WARNING | `data_validation_utils.py:90` |

---

## 11. Validation Decision Tree

```
START: Detection Event
│
├─> video_relative_timestamp < 0?
│   └─> YES → FAIL (ERROR: Before video start)
│   └─> NO → Continue
│
├─> actual_latency_ms < 0?
│   └─> YES → FAIL (ERROR: Negative latency)
│   └─> NO → Continue
│
├─> actual_latency_ms > 5000?
│   └─> YES → FAIL (TIMEOUT: Too late)
│   └─> NO → Continue
│
├─> actual_latency_ms ≤ threshold (50ms)?
│   └─> YES → PASS
│   └─> NO → FAIL (Above threshold)
│
├─> Has ground truth match?
│   ├─> YES → TRUE POSITIVE
│   └─> NO → FALSE POSITIVE
│
END
```

---

## 12. Test Coverage Map

### Test Files and Their Thresholds

1. **test_ground_truth_matching_service.py**
   - Tolerance: 100ms (standard), 50ms (strict), 200ms (relaxed)
   - Expected TP/FP/FN: 18/4/6

2. **test_timing_validation_api.py**
   - Total detections: 502
   - Valid timestamp range: 0-10 seconds
   - Valid frame range: 0-240

3. **test_phase4_solves_all_issues.py**
   - Concurrent operations: 100 threads, 0 conflicts
   - Late detection: 500ms tolerance
   - Max queries: 15 for 3 videos

4. **test_latency_validation_service.py** (inferred)
   - Default threshold: 50ms
   - Timeout threshold: 5000ms
   - Percentiles: 95th, 99th

---

## Appendix A: Calculation Formulas

### Precision
```
Precision = True Positives / (True Positives + False Positives)
```

### Recall
```
Recall = True Positives / (True Positives + False Negatives)
```

### F1 Score
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

### Accuracy
```
Accuracy = True Positives / Total Ground Truth Objects
```

### Pass Rate
```
Pass Rate = (Detections with latency ≤ threshold / Total Detections) × 100%
```

### Temporal IoU
```
time_diff = |detection_time - ground_truth_time|
if time_diff ≤ tolerance:
    IoU = 1.0 - (time_diff / tolerance) × 0.5
else:
    IoU = 0.0
```

---

## Appendix B: File References

Key files analyzed for this documentation:

1. `backend/services/ground_truth_matching_service.py` (Lines 1-300)
2. `backend/services/latency_validation_service.py` (Full file)
3. `backend/services/validation_service.py` (Lines 1-200)
4. `backend/schemas.py` (Lines 1-831)
5. `backend/models.py` (Lines 1-935)
6. `backend/tests/test_ground_truth_matching_service.py` (Lines 1-594)
7. `backend/tests/test_timing_validation_api.py` (Lines 1-361)
8. `backend/tests/test_phase4_solves_all_issues.py` (Lines 1-1165)
9. `backend/migrations/data_validation_utils.py` (Lines 1-650)

---

**Document Control**:
- Created: 2025-11-11
- Version: 1.0
- Maintained by: QA/Test Engineering Team
- Review Cycle: Quarterly or on major threshold changes

