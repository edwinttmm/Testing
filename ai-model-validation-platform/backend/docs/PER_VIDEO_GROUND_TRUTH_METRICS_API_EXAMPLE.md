# Per-Video Ground Truth Metrics - API Response Example

## Overview
This document shows the new `ground_truth_metrics` field added to the Enhanced HIL Results API response for multi-video test sessions.

## Endpoint
```
GET /api/enhanced-hil/results/{session_id}
```

## API Response Structure (New Fields)

### Complete Response with Per-Video Ground Truth Metrics

```json
{
  "session_id": "abc-123-def-456",
  "validation_type": "enhanced_latency_with_timing_correction",
  "has_video_sequence": true,
  "sequence_id": "seq-789-xyz-012",

  "sequence_results": {
    "total_videos": 3,
    "current_video_index": 2,
    "completed_videos": 3,
    "sequence_status": "completed",

    "per_video_results": [
      {
        "video_id": "video-001",
        "sequence_order": 0,
        "video_status": "completed",
        "video_filename": "test_video_1.mp4",
        "video_url": "/uploads/test_video_1.mp4",
        "video_duration": 30.5,

        "expected_detection_count": 10,
        "actual_detection_count": 8,
        "passed_detections": 7,
        "failed_detections": 1,
        "avg_latency_ms": 45.2,
        "pass_rate_percent": 87.5,
        "validation_result": "pass",

        "ground_truth_metrics": {
          "total_ground_truth": 10,
          "true_positives": 8,
          "false_positives": 0,
          "false_negatives": 2,
          "precision": 100.0,
          "recall": 80.0,
          "f1_score": 88.89
        }
      },
      {
        "video_id": "video-002",
        "sequence_order": 1,
        "video_status": "completed",
        "video_filename": "test_video_2.mp4",
        "video_url": "/uploads/test_video_2.mp4",
        "video_duration": 25.0,

        "expected_detection_count": 5,
        "actual_detection_count": 6,
        "passed_detections": 5,
        "failed_detections": 1,
        "avg_latency_ms": 52.1,
        "pass_rate_percent": 83.33,
        "validation_result": "pass",

        "ground_truth_metrics": {
          "total_ground_truth": 5,
          "true_positives": 5,
          "false_positives": 1,
          "false_negatives": 0,
          "precision": 83.33,
          "recall": 100.0,
          "f1_score": 90.91
        }
      },
      {
        "video_id": "video-003",
        "sequence_order": 2,
        "video_status": "completed",
        "video_filename": "test_video_3.mp4",
        "video_url": "/uploads/test_video_3.mp4",
        "video_duration": 40.2,

        "expected_detection_count": 15,
        "actual_detection_count": 14,
        "passed_detections": 13,
        "failed_detections": 1,
        "avg_latency_ms": 48.7,
        "pass_rate_percent": 92.86,
        "validation_result": "pass",

        "ground_truth_metrics": {
          "total_ground_truth": 15,
          "true_positives": 14,
          "false_positives": 0,
          "false_negatives": 1,
          "precision": 100.0,
          "recall": 93.33,
          "f1_score": 96.55
        }
      }
    ]
  },

  "ground_truth_performance": {
    "overall_true_positives": 27,
    "overall_false_positives": 1,
    "overall_false_negatives": 3,
    "overall_precision": 96.43,
    "overall_recall": 90.0,
    "overall_f1_score": 93.1
  },

  "detection_statistics": {
    "total_detections": 28,
    "corrected_results": {
      "passed_detections": 25,
      "failed_detections": 3,
      "pass_rate": 89.29,
      "average_real_latency_ms": 48.67
    }
  }
}
```

## Field Descriptions

### ground_truth_metrics (per video)

| Field | Type | Description |
|-------|------|-------------|
| `total_ground_truth` | int | Total number of ground truth objects for this video |
| `true_positives` | int | Number of detections correctly matched to ground truth |
| `false_positives` | int | Number of detections without a ground truth match |
| `false_negatives` | int | Number of ground truth objects without a detection match |
| `precision` | float | Precision percentage: TP / (TP + FP) × 100 |
| `recall` | float | Recall percentage: TP / (TP + FN) × 100 |
| `f1_score` | float | F1 score percentage: 2 × (Precision × Recall) / (Precision + Recall) |

## Calculation Logic

### True Positives (TP)
```python
tp = count(detections with ground_truth_match_id != NULL)
```

### False Positives (FP)
```python
fp = count(detections with ground_truth_match_id == NULL)
```

### False Negatives (FN)
```python
fn = total_ground_truth - tp
```

### Metrics Formulas
```python
precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
```

## Frontend Usage

```typescript
interface GroundTruthMetrics {
  totalGroundTruth: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  precision: number;
  recall: number;
  f1Score: number;
}

interface PerVideoResult {
  videoId: string;
  sequenceOrder: number;
  // ... other fields ...
  groundTruthMetrics: GroundTruthMetrics;
}

// Display per-video metrics
function displayVideoMetrics(video: PerVideoResult) {
  const { groundTruthMetrics } = video;

  console.log(`Video ${video.videoFilename}:`);
  console.log(`  Precision: ${groundTruthMetrics.precision.toFixed(2)}%`);
  console.log(`  Recall: ${groundTruthMetrics.recall.toFixed(2)}%`);
  console.log(`  F1 Score: ${groundTruthMetrics.f1Score.toFixed(2)}%`);
  console.log(`  TP: ${groundTruthMetrics.truePositives}`);
  console.log(`  FP: ${groundTruthMetrics.falsePositives}`);
  console.log(`  FN: ${groundTruthMetrics.falseNegatives}`);
}
```

## Implementation Details

### Backend Changes

1. **File**: `/backend/src/api/enhanced_hil_results_endpoints.py`
   - Lines 1033-1083: Added per-video ground truth calculation
   - Queries ground truth objects per video (excluding soft-deleted)
   - Queries detections per video
   - Calculates TP/FP/FN/Precision/Recall/F1 for each video

2. **File**: `/backend/schemas.py`
   - Lines 664-672: Added `GroundTruthMetrics` schema
   - Uses CamelCase aliases for frontend compatibility

### Database Queries

```python
# Per video ground truth objects (active only)
video_ground_truth = db.query(GroundTruthObject).filter(
    GroundTruthObject.video_id == video_id,
    GroundTruthObject.deleted_at.is_(None)
).all()

# Per video detections
video_detections = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.video_id == video_id
).all()
```

## Testing

### Manual Test
```bash
# Start backend server
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 main.py

# Test endpoint
curl http://localhost:8000/api/enhanced-hil/results/{session_id} | jq '.sequence_results.per_video_results[0].ground_truth_metrics'
```

### Expected Output
```json
{
  "totalGroundTruth": 10,
  "truePositives": 8,
  "falsePositives": 0,
  "falseNegatives": 2,
  "precision": 100.0,
  "recall": 80.0,
  "f1Score": 88.89
}
```

## Benefits

1. **Per-Video Analysis**: Frontend can now show ground truth metrics for each video in a sequence
2. **Data-Driven Insights**: Identify which videos have poor precision/recall
3. **Quality Assurance**: Validate ground truth matching quality per video
4. **Performance Tracking**: Compare detection performance across different videos
5. **Debugging**: Identify videos with high FP or FN rates

## Backward Compatibility

- This is a new optional field in the response
- Existing API consumers will not break
- Only present when `has_video_sequence` is true
- Falls back gracefully if ground truth matching service fails
