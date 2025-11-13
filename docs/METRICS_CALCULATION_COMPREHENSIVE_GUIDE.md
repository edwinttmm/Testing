# Comprehensive Metrics Calculation Guide

**Document Version:** 1.0
**Last Updated:** 2025-11-11
**Status:** PRODUCTION REFERENCE

---

## Table of Contents

1. [Overview](#overview)
2. [Core Classification Metrics](#core-classification-metrics)
3. [Performance Metrics Formulas](#performance-metrics-formulas)
4. [Latency Calculation Methods](#latency-calculation-methods)
5. [Per-Video vs Aggregated Metrics](#per-video-vs-aggregated-metrics)
6. [Multi-Video Sequence Handling](#multi-video-sequence-handling)
7. [Code References](#code-references)
8. [Examples with Real Data](#examples-with-real-data)

---

## 1. Overview

This system implements **temporal matching** for Hardware-in-the-Loop (HIL) validation testing. Detection events are matched to ground truth objects within a configurable tolerance window, and classified as:

- **TP (True Positive)**: Detection matched to ground truth within tolerance
- **FP (False Positive)**: Detection with no matching ground truth
- **FN (False Negative)**: Ground truth with no matching detection
- **TN (True Negative)**: Not applicable for temporal detection matching

---

## 2. Core Classification Metrics

### 2.1 How Counts Are Calculated

**Location:** `/backend/services/ground_truth_matching_service.py` (Lines 644-918)

#### Algorithm Overview

**Phase 1: Match Ground Truth to Detections (TP and FN)**

```python
# For each ground truth object
for gt_obj in ground_truth_objects:
    best_match = None
    best_time_diff = float('inf')

    # Find nearest detection within tolerance window
    for detection in detection_events:
        if detection not in used_detections:
            time_diff = abs(detection_time - gt_time)

            if time_diff <= tolerance_seconds and time_diff < best_time_diff:
                best_match = detection
                best_time_diff = time_diff

    if best_match:
        # TRUE POSITIVE: Ground truth matched to detection
        match_results.append(MatchResult(
            ground_truth_id=gt_obj.id,
            detection_event_id=best_match.id,
            match_type='TP',
            latency_ms=time_diff * 1000
        ))
        used_detections.add(best_match)
    else:
        # FALSE NEGATIVE: Ground truth with no matching detection
        match_results.append(MatchResult(
            ground_truth_id=gt_obj.id,
            detection_event_id=None,
            match_type='FN'
        ))
```

**Phase 2: Mark Remaining Detections as False Positives**

```python
# All unmatched detections are false positives
for detection in detection_events:
    if detection not in used_detections:
        # FALSE POSITIVE: Detection with no matching ground truth
        match_results.append(MatchResult(
            ground_truth_id=None,
            detection_event_id=detection.id,
            match_type='FP'
        ))
```

#### Multi-Video Video Boundary Validation

**CRITICAL FIX (Lines 757-790):** Detections are NOT matched across video boundaries in multi-video sequences:

```python
# Video boundary validation prevents incorrect cross-video matches
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)

if detection_video_id is not None and gt_video_id is not None:
    if detection_video_id != gt_video_id:
        # REJECT: Detection and ground truth from different videos
        video_boundary_rejections += 1
        continue  # Skip this detection for this ground truth
```

#### Latency-Limited Sample (Lines 1107-1125)

**CRITICAL:** Only the **first 10 TP detections per video** are used for latency averaging to avoid contamination from late-stage detections when ground truth runs out:

```python
# Group TP results by video_id
video_tp_latencies = defaultdict(list)
for mr in tp_results:
    if mr.latency_ms is not None:
        video_id = str(mr.video_id) if mr.video_id else 'default_video'
        if len(video_tp_latencies[video_id]) < 10:  # ONLY FIRST 10 PER VIDEO
            video_tp_latencies[video_id].append(mr.latency_ms)

# Combine first 10 from each video for overall average
valid_latencies = []
for video_id, latencies in video_tp_latencies.items():
    valid_latencies.extend(latencies)
```

---

## 3. Performance Metrics Formulas

### 3.1 Precision

**Definition:** Percentage of detections that are correct (matched to ground truth)

**Formula:**
```
Precision = TP / (TP + FP)
```

**Code Reference:** `ground_truth_matching_service.py` Line 1102
```python
precision = true_positives / (true_positives + false_positives) \
    if (true_positives + false_positives) > 0 else 0.0
```

**Example:**
- TP = 18, FP = 4
- Precision = 18 / (18 + 4) = 18 / 22 = **0.818 (81.8%)**

---

### 3.2 Recall

**Definition:** Percentage of ground truth objects that were detected

**Formula:**
```
Recall = TP / (TP + FN)
```

**Code Reference:** `ground_truth_matching_service.py` Line 1103
```python
recall = true_positives / (true_positives + false_negatives) \
    if (true_positives + false_negatives) > 0 else 0.0
```

**Example:**
- TP = 18, FN = 6
- Recall = 18 / (18 + 6) = 18 / 24 = **0.750 (75.0%)**

---

### 3.3 F1 Score

**Definition:** Harmonic mean of precision and recall (balanced metric)

**Formula:**
```
F1 Score = 2 * (Precision * Recall) / (Precision + Recall)
```

**Code Reference:** `ground_truth_matching_service.py` Line 1104
```python
f1_score = 2 * (precision * recall) / (precision + recall) \
    if (precision + recall) > 0 else 0.0
```

**Example:**
- Precision = 0.818, Recall = 0.750
- F1 = 2 * (0.818 * 0.750) / (0.818 + 0.750)
- F1 = 2 * 0.6135 / 1.568 = **0.782 (78.2%)**

---

### 3.4 Accuracy

**Definition:** Percentage of ground truth objects successfully detected

**Formula:**
```
Accuracy = TP / (TP + FN)
```

**Code Reference:** `ground_truth_matching_service.py` Line 1105
```python
accuracy = true_positives / (true_positives + false_negatives) \
    if (true_positives + false_negatives) > 0 else 0.0
```

**Note:** Accuracy is equivalent to Recall in this temporal detection system.

---

## 4. Latency Calculation Methods

### 4.1 Single Detection Latency

**Formula:**
```
Latency (ms) = abs(detection_timestamp - ground_truth_timestamp) * 1000
```

**Code Reference:** `ground_truth_matching_service.py` Line 810
```python
temporal_offset_ms = (detection_time - gt_time) * 1000
latency_ms = abs(temporal_offset_ms)
```

**Example:**
- Ground Truth at **1.042s**
- Detection at **1.065s**
- Latency = abs(1.065 - 1.042) * 1000 = **23.0ms**

---

### 4.2 Mean Latency

**Formula:**
```
Mean Latency = sum(all_latencies) / count(latencies)
```

**Code Reference:** `ground_truth_matching_service.py` Line 1128
```python
mean_latency_ms = statistics.mean(valid_latencies)
```

**CRITICAL:** Only first 10 TP detections per video are used (see Section 2.1)

**Example:**
- Latencies: [23.0, 25.0, 23.0, 23.0, 23.0, 23.0, 23.0, 23.0]
- Mean = (23+25+23+23+23+23+23+23) / 8 = **23.25ms**

---

### 4.3 Standard Deviation

**Formula:**
```
Std Dev = sqrt(sum((x - mean)^2) / (n - 1))
```

**Code Reference:** `ground_truth_matching_service.py` Line 1129
```python
std_latency_ms = statistics.stdev(valid_latencies) \
    if len(valid_latencies) > 1 else 0.0
```

---

### 4.4 Within Tolerance Percentage

**Formula:**
```
Within Tolerance % = (count(latencies <= tolerance) / total_latencies) * 100
```

**Code Reference:** `ground_truth_matching_service.py` Lines 1135-1137
```python
within_tolerance_count = sum(1 for lat in valid_latencies if lat <= tolerance_ms)
within_tolerance_percentage = (within_tolerance_count / len(valid_latencies)) * 100
```

**Example:**
- Tolerance = 100ms
- 8 latencies, all ≤ 100ms
- Within Tolerance = (8 / 8) * 100 = **100.0%**

---

## 5. Per-Video vs Aggregated Metrics

### 5.1 Per-Video Metrics Calculation

**Location:** Frontend `hilResultsNormalization.ts` Lines 340-602

Each video in a sequence has independent metrics:

```typescript
const normalizePerVideoResult = (video: any) => {
  // Detection counts
  const detectionCount = video?.detection_count ?? 0;
  const passedDetections = video?.passed_detections ?? 0;
  const failedDetections = video?.failed_detections ?? 0;

  // Pass rate calculation
  const passRatePercent = (passedDetections / detectionCount) * 100;

  // Latency statistics
  const avgLatency = video?.avg_latency_ms;
  const maxLatency = video?.max_latency_ms;
  const minLatency = video?.min_latency_ms;

  // Ground truth metrics (per video)
  const groundTruthMetrics = {
    total_ground_truth: video?.ground_truth_metrics?.total_ground_truth ?? 0,
    true_positives: video?.ground_truth_metrics?.true_positives ?? 0,
    false_positives: video?.ground_truth_metrics?.false_positives ?? 0,
    false_negatives: video?.ground_truth_metrics?.false_negatives ?? 0,
    precision: video?.ground_truth_metrics?.precision ?? 0,
    recall: video?.ground_truth_metrics?.recall ?? 0,
    f1_score: video?.ground_truth_metrics?.f1_score ?? 0
  };

  return {
    video_id,
    detection_count,
    passed_detections,
    failed_detections,
    pass_rate_percent: passRatePercent,
    avg_latency_ms: avgLatency,
    max_latency_ms: maxLatency,
    min_latency_ms: minLatency,
    ground_truth_metrics: groundTruthMetrics
  };
};
```

---

### 5.2 Aggregated Sequence Metrics

**Location:** Frontend `hilResultsNormalization.ts` Lines 604-854

Aggregation combines all videos in a sequence:

```typescript
const normalizeSequenceResults = (raw: any) => {
  const normalizedVideos = perVideoRaw.map(normalizePerVideoResult);

  // CRITICAL: Calculate from per-video results (not stale top-level values)
  const totalDetections = normalizedVideos.reduce(
    (sum, video) => sum + (video.total_detections ?? 0), 0
  );

  const totalPassedDetections = normalizedVideos.reduce(
    (sum, video) => sum + (video.passed_detections ?? 0), 0
  );

  const totalFailedDetections = normalizedVideos.reduce(
    (sum, video) => sum + (video.failed_detections ?? 0), 0
  );

  // Weighted average latency
  const totalLatencyWeighted = normalizedVideos.reduce((sum, video) => {
    const avg = video.average_latency_ms;
    const count = video.total_detections ?? 0;
    if (avg && count > 0) {
      return sum + (avg * count);
    }
    return sum;
  }, 0);

  const averageLatency = totalDetections > 0
    ? totalLatencyWeighted / totalDetections
    : 0;

  // Overall pass rate
  const overallPassRate = totalDetections > 0
    ? (totalPassedDetections / totalDetections) * 100
    : 0;

  // Aggregate ground truth metrics
  const aggregateGT = {
    true_positives: sum(videos.map(v => v.gt_metrics.true_positives)),
    false_positives: sum(videos.map(v => v.gt_metrics.false_positives)),
    false_negatives: sum(videos.map(v => v.gt_metrics.false_negatives)),
    total_ground_truth: sum(videos.map(v => v.gt_metrics.total_ground_truth))
  };

  // Recalculate precision/recall/F1 from aggregated counts
  const precision = aggregateGT.true_positives /
    (aggregateGT.true_positives + aggregateGT.false_positives);
  const recall = aggregateGT.true_positives /
    (aggregateGT.true_positives + aggregateGT.false_negatives);
  const f1_score = 2 * (precision * recall) / (precision + recall);

  return {
    total_detections: totalDetections,
    total_passed_detections: totalPassedDetections,
    total_failed_detections: totalFailedDetections,
    overall_pass_rate: overallPassRate,
    average_latency_ms: averageLatency,
    per_video_results: normalizedVideos,
    ground_truth_comparison: {
      ...aggregateGT,
      precision,
      recall,
      f1_score
    }
  };
};
```

---

## 6. Multi-Video Sequence Handling

### 6.1 Video Boundary Protection

**Location:** `ground_truth_matching_service.py` Lines 681-722

Multi-video sequences are detected and video boundaries are enforced:

```python
# Detect multi-video sequence
gt_video_ids = set()
for gt_obj in ground_truth_objects:
    gt_video_id = getattr(gt_obj, 'video_id', None)
    if gt_video_id is not None:
        gt_video_ids.add(gt_video_id)

has_multi_video_sequence = len(gt_video_ids) > 1

if has_multi_video_sequence:
    logger.info(f"Detected multi-video sequence with {len(gt_video_ids)} videos - "
                f"Enforcing strict video boundary validation")
```

---

### 6.2 Per-Video Latency Grouping

**Location:** `ground_truth_matching_service.py` Lines 1107-1125

Latencies are grouped by video to ensure balanced sampling:

```python
# Group TP results by video_id
video_tp_latencies = defaultdict(list)
for mr in tp_results:
    if mr.latency_ms is not None:
        video_id = str(mr.video_id) if mr.video_id else 'default_video'
        if len(video_tp_latencies[video_id]) < 10:  # First 10 per video
            video_tp_latencies[video_id].append(mr.latency_ms)

# Log per-video sampling
for video_id, latencies in video_tp_latencies.items():
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    logger.info(f"Video {video_id[:12]}: Using first {len(latencies)} TP detections "
                f"for latency (avg: {avg_lat:.1f}ms)")
```

---

### 6.3 Capture Rate Calculation

**Definition:** Percentage of ground truth objects successfully detected

**Formula:**
```
Capture Rate = (TP / Total Ground Truth) * 100
```

**Code Reference:** `ground_truth_matching_service.py` Lines 1540-1542
```python
if metrics.total_ground_truth > 0:
    detection_rate = (metrics.matched_detections / metrics.total_ground_truth) * 100
    summary['summary']['detection_rate_percentage'] = round(detection_rate, 1)
```

**Example:**
- Total Ground Truth: 24
- Matched Detections (TP): 18
- Capture Rate = (18 / 24) * 100 = **75.0%**

---

## 7. Code References

### 7.1 Backend Services

| File | Lines | Description |
|------|-------|-------------|
| `ground_truth_matching_service.py` | 644-918 | Temporal matching algorithm |
| `ground_truth_matching_service.py` | 1075-1205 | Metrics calculation and storage |
| `ground_truth_matching_service.py` | 1465-1583 | API response formatting |
| `session_completion_service.py` | 214-455 | Session completion and validation |

### 7.2 Frontend Normalization

| File | Lines | Description |
|------|-------|-------------|
| `hilResultsNormalization.ts` | 340-602 | Per-video result normalization |
| `hilResultsNormalization.ts` | 604-854 | Sequence aggregation logic |
| `hilResultsNormalization.ts` | 106-269 | Detection event normalization |

### 7.3 Database Models

| File | Lines | Description |
|------|-------|-------------|
| `models.py` | 276-440 | DetectionEvent model with latency fields |
| `models.py` | 442-548 | VideoTestSequence and SequenceVideoResult |
| `schemas.py` | 685-694 | GroundTruthMetrics schema |

### 7.4 Test Files

| File | Lines | Description |
|------|-------|-------------|
| `test_ground_truth_matching_service.py` | 65-150 | Test data generation (24 GT, 22 detections) |
| `test_ground_truth_matching_service.py` | 216-244 | Temporal matching algorithm validation |
| `test_ground_truth_matching_service.py` | 264-294 | Metrics calculation validation |

---

## 8. Examples with Real Data

### 8.1 Single Video Example

**Scenario:** Single 5-second video with 24 ground truth pedestrians

**Input Data:**
- Ground Truth Objects: 24 (timestamps: 0.208s, 0.417s, ..., 5.000s)
- Detection Events: 22 (18 matched + 4 false positives)
- Tolerance Window: ±100ms

**Matching Results:**
```
TRUE POSITIVES (TP):  18  (matched detections)
FALSE POSITIVES (FP): 4   (late detections with no nearby GT)
FALSE NEGATIVES (FN): 6   (unmatched GT at end of video)
TOTAL COMPARISONS:    28  (18 TP + 4 FP + 6 FN)
```

**Calculated Metrics:**
```
Precision = 18 / (18 + 4) = 0.818 (81.8%)
Recall    = 18 / (18 + 6) = 0.750 (75.0%)
F1 Score  = 2 * (0.818 * 0.750) / (0.818 + 0.750) = 0.783 (78.3%)
Accuracy  = 18 / 24 = 0.750 (75.0%)

Total Ground Truth:  24
Total Detections:    22
Matched Detections:  18
Capture Rate:        75.0%
```

**Latency Metrics:**
```
Mean Latency:    23.5ms
Std Dev:         2.1ms
Max Latency:     28.0ms
Min Latency:     20.0ms
Within Tolerance: 100.0%
```

---

### 8.2 Multi-Video Sequence Example

**Scenario:** 3-video sequence with 72 total ground truth objects

**Input Data:**
- Video 1: 24 GT, 20 detections (18 TP, 2 FP, 6 FN)
- Video 2: 24 GT, 22 detections (22 TP, 0 FP, 2 FN)
- Video 3: 24 GT, 18 detections (16 TP, 2 FP, 8 FN)

**Per-Video Metrics:**

**Video 1:**
```
TP: 18, FP: 2, FN: 6
Precision: 18 / (18 + 2) = 0.900 (90.0%)
Recall:    18 / (18 + 6) = 0.750 (75.0%)
F1 Score:  0.818 (81.8%)
Avg Latency: 23.2ms
```

**Video 2:**
```
TP: 22, FP: 0, FN: 2
Precision: 22 / (22 + 0) = 1.000 (100.0%)
Recall:    22 / (22 + 2) = 0.917 (91.7%)
F1 Score:  0.957 (95.7%)
Avg Latency: 25.8ms
```

**Video 3:**
```
TP: 16, FP: 2, FN: 8
Precision: 16 / (16 + 2) = 0.889 (88.9%)
Recall:    16 / (16 + 8) = 0.667 (66.7%)
F1 Score:  0.762 (76.2%)
Avg Latency: 28.5ms
```

**Aggregated Sequence Metrics:**
```
Total TP:  56 (18 + 22 + 16)
Total FP:  4  (2 + 0 + 2)
Total FN:  16 (6 + 2 + 8)

Precision = 56 / (56 + 4)  = 0.933 (93.3%)
Recall    = 56 / (56 + 16) = 0.778 (77.8%)
F1 Score  = 2 * (0.933 * 0.778) / (0.933 + 0.778) = 0.847 (84.7%)

Total Ground Truth:  72
Total Detections:    60
Matched Detections:  56
Capture Rate:        77.8%

Weighted Avg Latency: (23.2*20 + 25.8*22 + 28.5*18) / 60 = 25.7ms
```

---

### 8.3 Latency Distribution Example

**Sample Latencies (ms):** [20, 21, 23, 23, 23, 25, 25, 28, 30, 35]

**Calculations:**
```
Mean:   (20+21+23+23+23+25+25+28+30+35) / 10 = 25.3ms
Min:    20ms
Max:    35ms

Variance = sum((x - mean)^2) / (n - 1)
         = ((20-25.3)^2 + (21-25.3)^2 + ... + (35-25.3)^2) / 9
         = 24.9

Std Dev  = sqrt(24.9) = 4.99ms

Within 100ms Tolerance: 10 / 10 = 100.0%
Within 30ms Tolerance:  9 / 10 = 90.0%
```

---

## Summary

This guide documents the complete metrics calculation pipeline:

1. **Classification Counts:** TP/FP/FN via temporal matching algorithm
2. **Performance Metrics:** Precision, Recall, F1, Accuracy formulas
3. **Latency Analysis:** Mean, std dev, tolerance percentage
4. **Video Boundary Protection:** Prevents cross-video matches in sequences
5. **Latency Sampling:** First 10 TP detections per video to avoid contamination
6. **Aggregation Logic:** Weighted averaging across videos
7. **Frontend Normalization:** Per-video and sequence-level calculations

**Key Takeaways:**
- Metrics are calculated at **both per-video and aggregated levels**
- **Video boundaries are strictly enforced** in multi-video sequences
- **Latency uses first 10 TP detections per video** to avoid late-stage bias
- **Frontend recalculates from per-video results** to avoid stale top-level data
- **All formulas use standard classification metrics** (precision, recall, F1)

---

**File Location:** `/home/rigade/Testing/docs/METRICS_CALCULATION_COMPREHENSIVE_GUIDE.md`
