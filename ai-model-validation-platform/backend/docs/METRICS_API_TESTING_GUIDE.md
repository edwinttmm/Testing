# Metrics API Testing Guide

## Quick Start

### 1. Start Backend Server

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Run Quick Test Script

```bash
./scripts/test_metrics_api.sh
```

### 3. Run Comprehensive Integration Tests

```bash
pytest tests/test_frontend_metrics_integration.py -v
```

## Manual API Testing

### Test with curl

```bash
# Basic test
curl http://localhost:8000/api/test-sessions/49e5d00f-eea7-44cb-a647-480268ef43ee/results | jq '.metrics'

# Full response
curl http://localhost:8000/api/test-sessions/49e5d00f-eea7-44cb-a647-480268ef43ee/results | jq '.'

# Check specific metric
curl http://localhost:8000/api/test-sessions/49e5d00f-eea7-44cb-a647-480268ef43ee/results | jq '.metrics.f1_score'
```

### Test with Python

```python
import requests
import json

session_id = "49e5d00f-eea7-44cb-a647-480268ef43ee"
response = requests.get(f"http://localhost:8000/api/test-sessions/{session_id}/results")

if response.status_code == 200:
    data = response.json()
    metrics = data.get("metrics")

    print("Metrics:")
    print(json.dumps(metrics, indent=2))

    print(f"\nPrecision: {metrics['precision']}%")
    print(f"Recall: {metrics['recall']}%")
    print(f"F1 Score: {metrics['f1_score']}%")
    print(f"Accuracy: {metrics['accuracy']}%")
else:
    print(f"Error: {response.status_code}")
```

## Frontend Integration Testing

### 1. Open Browser DevTools

Navigate to: `http://localhost:3000/results/49e5d00f-eea7-44cb-a647-480268ef43ee`

### 2. Check Network Tab

Look for the API call to `/api/test-sessions/{id}/results`

Verify response contains:
```json
{
  "metrics": {
    "precision": 85.5,
    "recall": 92.3,
    "f1_score": 88.8,
    "accuracy": 89.1,
    "true_positives": 42,
    "false_positives": 7,
    "false_negatives": 3
  }
}
```

### 3. Check Console for Errors

Look for any TypeScript type errors or data parsing issues.

### 4. Verify Visual Display

ComparisonMetricsCard should show:
- ✅ Precision: 85.5% (with color coding)
- ✅ Recall: 92.3% (with color coding)
- ✅ F1 Score: 88.8% (with color coding)
- ✅ Accuracy: 89.1% (with color coding)
- ✅ True Positives: 42
- ✅ False Positives: 7
- ✅ False Negatives: 3

## Expected Results

### API Response Structure

```json
{
  "sessionId": "49e5d00f-eea7-44cb-a647-480268ef43ee",
  "sessionStatus": "completed",
  "perVideoResults": [
    {
      "video_id": "video-123",
      "videoName": "test_video.mp4",
      "detection_count": 10,
      "pass_rate": 95.0
    }
  ],
  "metrics": {
    "precision": 85.5,
    "recall": 92.3,
    "f1_score": 88.8,
    "accuracy": 89.1,
    "true_positives": 42,
    "false_positives": 7,
    "false_negatives": 3,
    "total_ground_truth": 45,
    "total_detections": 49,
    "matched_detections": 42,
    "mean_latency_ms": 45.2,
    "within_tolerance_percentage": 95.8
  },
  "results": [...]
}
```

### Metrics Field Specification

| Field | Type | Range | Precision | Description |
|-------|------|-------|-----------|-------------|
| `precision` | float | 0-100 | 1 decimal | Percentage of correct positive predictions |
| `recall` | float | 0-100 | 1 decimal | Percentage of actual positives found |
| `f1_score` | float | 0-100 | 1 decimal | Harmonic mean of precision and recall |
| `accuracy` | float | 0-100 | 1 decimal | Overall correctness percentage |
| `true_positives` | int | ≥0 | 0 decimal | Correctly identified detections |
| `false_positives` | int | ≥0 | 0 decimal | Incorrectly identified detections |
| `false_negatives` | int | ≥0 | 0 decimal | Missed actual detections |
| `total_ground_truth` | int | ≥0 | 0 decimal | Total ground truth events |
| `total_detections` | int | ≥0 | 0 decimal | Total detections made |
| `matched_detections` | int | ≥0 | 0 decimal | Successfully matched detections |
| `mean_latency_ms` | float | ≥0 | 1 decimal | Average detection latency |
| `within_tolerance_percentage` | float | 0-100 | 1 decimal | Detections within timing tolerance |

## Troubleshooting

### Server Not Starting

```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill existing process
kill -9 $(lsof -t -i:8000)

# Start with different port
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Metrics Field Missing

Check backend logs:
```bash
tail -f backend.log | grep metrics
```

Look for error messages from `ground_truth_matching_service`

### Frontend Not Displaying Metrics

1. Check browser console for errors
2. Verify API response in Network tab
3. Check if ComparisonMetricsCard receives metrics prop
4. Verify TypeScript interface matches API response

### Type Errors in Frontend

If you see TypeScript errors about metrics types:

```typescript
// Check if metrics exists before accessing
if (data.metrics) {
  const metrics = data.metrics;
  console.log(`F1 Score: ${metrics.f1_score}%`);
}

// Use optional chaining
const f1Score = data.metrics?.f1_score ?? 0;
```

## Validation Checklist

Before deploying to production:

- [ ] Backend server starts successfully
- [ ] API endpoint returns 200 status
- [ ] Response contains `metrics` field at top level
- [ ] All required metric fields are present
- [ ] Percentage values are 0-100 with 1 decimal place
- [ ] Count values are non-negative integers
- [ ] Mathematical formulas are consistent (P, R, F1)
- [ ] Integration tests pass
- [ ] Frontend displays metrics correctly
- [ ] No TypeScript type errors
- [ ] Color coding works correctly
- [ ] Progress bars render properly
- [ ] No console errors

## Performance Benchmarks

Expected API response times:
- **Fast**: < 1 second (database cached)
- **Normal**: 1-3 seconds (database query)
- **Slow**: 3-5 seconds (complex calculation)
- **Timeout**: > 5 seconds (investigate)

## Support

For issues or questions:
1. Check this guide first
2. Review integration test failures
3. Check backend logs
4. Verify database contains session data
5. Test with different session IDs

## Related Documentation

- **Integration Tests**: `/backend/tests/test_frontend_metrics_integration.py`
- **Verification Report**: `/backend/docs/FRONTEND_METRICS_INTEGRATION_VERIFICATION.md`
- **Backend Implementation**: `/backend/routers/test_sessions.py` (lines 2073-2116)
- **Frontend Component**: `/frontend/src/components/results/ComparisonMetricsCard.tsx`
- **TypeScript Interface**: `/frontend/src/types/enhanced-results.ts`
