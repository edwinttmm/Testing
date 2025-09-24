# Ground Truth Matching API Integration

## Overview

This document describes the enhanced ground truth matching API that transforms the frontend display from meaningless detection counts to actual ground truth matching results with real latency metrics.

## Problem Solved

**Before**: Frontend showed "0 of 24 tests, 0.0% Pass Rate, No events available" with fixed "5.0ms" latency values

**After**: Frontend displays "18 of 24 ground truth found, 82% precision, 75% recall, 23.4ms avg latency"

## Key Components

### 1. Ground Truth Matching Service

**File**: `/src/services/ground_truth_matching_service.py`

Core service that provides:
- Temporal matching between detection events and ground truth objects
- Precision, recall, and F1-score calculations
- Real latency measurements from detection timing
- Classification of detections as True Positive, False Positive, False Negative

**Key Classes:**

```python
@dataclass
class SessionMatchingResults:
    session_id: str
    ground_truth_total: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    avg_latency_ms: float
    median_latency_ms: float
    latency_std_ms: float
    matched_pairs: List[MatchingResult]
    unmatched_detections: List[MatchingResult]
    missed_ground_truths: List[MatchingResult]
```

**Key Methods:**
- `get_session_matching_results(session_id)`: Returns comprehensive matching metrics
- `get_detection_event_details(session_id)`: Returns event-by-event correlation data
- `calculate_project_metrics(project_id)`: Project-level aggregated metrics

### 2. Enhanced Results API Endpoints

**File**: `/src/enhanced_results_api.py`

#### New Enhanced Endpoints

**GET `/api/results/{session_id}/results`**
```json
{
  "session_id": "abc123",
  "session_name": "Test Session",
  "ground_truth_total": 24,
  "ground_truth_matched": 18,
  "ground_truth_missed": 6,
  "extra_detections": 4,
  "precision": 81.8,
  "recall": 75.0,
  "f1_score": 78.3,
  "avg_latency_ms": 31.2,
  "median_latency_ms": 29.5,
  "latency_std_ms": 8.7,
  "detection_details": [...],
  "summary": {
    "coverage_percentage": 75.0,
    "detection_accuracy": 81.8,
    "overall_performance": 78.3,
    "timing_performance": "31.2ms ± 8.7ms"
  }
}
```

**GET `/api/results/{session_id}/detection-events`**
```json
[
  {
    "id": "det_001",
    "video_time": 1.2,
    "ground_truth_time": 1.2,
    "detected_time": 1.223,
    "latency_ms": 23.0,
    "temporal_offset_ms": 23.0,
    "status": "matched",
    "match_type": "true_positive",
    "confidence": 0.87,
    "status_color": "green",
    "display_text": "✓ Matched"
  },
  {
    "id": "gt_002",
    "video_time": 2.4,
    "ground_truth_time": 2.4,
    "detected_time": null,
    "latency_ms": null,
    "status": "missed",
    "match_type": "false_negative",
    "status_color": "red",
    "display_text": "✗ Missed GT"
  },
  {
    "id": "det_003",
    "video_time": 3.8,
    "detected_time": 3.8,
    "ground_truth_time": null,
    "latency_ms": 25.0,
    "status": "false_positive",
    "match_type": "false_positive",
    "status_color": "orange",
    "display_text": "⚠ False Positive"
  }
]
```

#### Enhanced Existing Endpoints

**GET `/api/results/completed`** - Now includes ground truth metrics:
```json
[
  {
    "session_id": "abc123",
    "session_name": "Test Session",
    "metrics": {
      "ground_truth_coverage": 75.0,
      "detection_precision": 81.8,
      "overall_performance": 78.3,
      "avg_latency_ms": 31.2,
      "total_ground_truth": 24,
      "matched_ground_truth": 18,
      "missed_ground_truth": 6,
      "extra_detections": 4
    },
    "summary_text": "Good: 18/24 ground truth found (75%), 82% precision, 31.2ms latency"
  }
]
```

**GET `/api/results/sessions/{session_id}/detailed`** - Enhanced with ground truth metrics:
```json
{
  "session_id": "abc123",
  "ground_truth_metrics": {
    "ground_truth_total": 24,
    "ground_truth_matched": 18,
    "precision": 0.818,
    "recall": 0.75,
    "f1_score": 0.783,
    "avg_latency_ms": 31.2
  },
  "detection_details": [...]
}
```

## Frontend Integration Changes Required

### 1. Results Display Transformation

**Before:**
```javascript
// Legacy display
"0 of 24 tests, 0.0% Pass Rate"
"24 Failed Tests, 100.0% failure rate"
"Fixed 5.0ms latency"
```

**After:**
```javascript
// Enhanced display using new API
`${data.ground_truth_matched} of ${data.ground_truth_total} ground truth found`
`${data.precision}% precision, ${data.recall}% recall`
`${data.avg_latency_ms}ms avg latency (±${data.latency_std_ms}ms)`
```

### 2. Detection Events Table

**Before:**
```javascript
// Raw LabJack signals with Unix timestamps
{
  timestamp: 1694876543.123,
  value: "Pass/Fail",
  latency: 5.0
}
```

**After:**
```javascript
// Ground truth correlated events with video-relative time
{
  video_time: 1.2,           // Video-relative seconds
  status: "matched",         // matched/missed/false_positive
  match_type: "true_positive", // TP/FP/FN classification
  latency_ms: 23.4,         // Real measured latency
  status_color: "green",    // Color coding for UI
  display_text: "✓ Matched" // Human-readable status
}
```

### 3. Session Overview Metrics

**Before:**
```javascript
const metrics = {
  passRate: 0.0,
  totalTests: 24,
  passedTests: 0,
  avgLatency: 5.0
};
```

**After:**
```javascript
const metrics = {
  groundTruthCoverage: 75.0,      // Recall percentage
  detectionAccuracy: 81.8,       // Precision percentage
  overallPerformance: 78.3,      // F1-score percentage
  avgLatencyMs: 31.2,            // Real measured latency
  latencyStdMs: 8.7,             // Latency variance
  totalGroundTruth: 24,          // Ground truth count
  matchedGroundTruth: 18,        // Successfully detected
  missedGroundTruth: 6,          // False negatives
  extraDetections: 4             // False positives
};
```

## Algorithm Details

### Ground Truth Matching Algorithm

1. **Temporal Matching**: Detections matched to ground truth within configurable time tolerance (default: 100ms)
2. **Closest Match Selection**: For multiple candidates, selects detection with smallest temporal offset
3. **One-to-One Mapping**: Each ground truth can match at most one detection
4. **Classification**:
   - **True Positive (TP)**: Ground truth with matching detection
   - **False Negative (FN)**: Ground truth with no matching detection  
   - **False Positive (FP)**: Detection with no matching ground truth

### Metrics Calculation

```python
precision = TP / (TP + FP)           # Detection accuracy
recall = TP / (TP + FN)              # Ground truth coverage  
f1_score = 2 * (precision * recall) / (precision + recall)
avg_latency = mean([match.latency_ms for match in true_positives])
```

## Error Handling

The API includes comprehensive error handling:

1. **Graceful Degradation**: Falls back to legacy metrics if ground truth unavailable
2. **Session Validation**: Validates session existence before processing
3. **Database Error Recovery**: Handles missing relationships and corrupted data
4. **Temporal Edge Cases**: Handles videos without proper timing synchronization

## Backward Compatibility

All changes maintain backward compatibility:

1. **Legacy Endpoints**: Existing endpoints continue to work with enhanced data
2. **Legacy Fields**: Original metric fields preserved alongside new ones
3. **Fallback Modes**: API falls back to original behavior when ground truth unavailable
4. **Schema Compatibility**: New fields are optional and don't break existing clients

## Performance Considerations

1. **Optimized Queries**: Uses database indexes for temporal and relationship queries
2. **Lazy Loading**: Ground truth matching calculated only when requested
3. **Caching Opportunities**: Results can be cached since ground truth is stable
4. **Batch Processing**: Multiple sessions can be processed efficiently

## Testing

Test data generator creates realistic scenarios:
- 24 ground truth objects at regular intervals
- 18 true positive detections with varying latency (15-49ms)
- 4 false positive detections
- 6 false negative cases (missed ground truth)

Expected metrics: 81.8% precision, 75.0% recall, 78.3% F1-score

## Integration Checklist

### Backend (Completed)
- ✅ Ground truth matching service with temporal correlation
- ✅ Enhanced API endpoints with precision/recall metrics
- ✅ Video-relative timestamp calculation
- ✅ Detection event classification (TP/FP/FN)
- ✅ Real latency measurements from detection timing
- ✅ Backward compatible response format

### Frontend (Required)
- 🔲 Update results parsing to use ground_truth_matched vs ground_truth_total
- 🔲 Replace "Pass Rate" with "Ground Truth Coverage" and "Precision"
- 🔲 Display real latency distribution instead of fixed values
- 🔲 Color-code detection events by match status (Green/Red/Orange)
- 🔲 Sort detection table by video-relative timeline order
- 🔲 Show "18 of 24 ground truth found" instead of "0 of 24 tests"
- 🔲 Display "Precision: 82%, Recall: 75%" instead of "0.0% Pass Rate"
- 🔲 Show "Avg Latency: 23.4ms" instead of fixed "5.0ms"

## Expected Transformation

**Current Frontend Display:**
```
Session: Test Session
Status: 0 of 24 tests, 0.0% Pass Rate
Details: 24 Failed Tests, 100.0% failure rate
Latency: Fixed 5.0ms values
Events: No events available
```

**Enhanced Frontend Display:**
```
Session: Test Session  
Status: 18 of 24 ground truth found (75% coverage)
Details: 82% precision, 6 missed, 4 false positives
Latency: 31.2ms avg (±8.7ms), range 15-49ms
Events: 28 events (18 ✓ matched, 6 ✗ missed, 4 ⚠ false positive)
```

This transformation provides users with meaningful, actionable metrics that directly relate to the ground truth validation performance rather than generic test counts.