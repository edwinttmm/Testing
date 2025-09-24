# HIL Testing API with Ground Truth Comparison and Screenshots

This document describes the Hardware-in-the-Loop (HIL) testing API endpoints that provide ground truth comparison with visual evidence through screenshot capture.

## Overview

The HIL testing system captures video frames at the exact moment when LabJack voltage detections occur (4.2V signals), providing visual evidence for ground truth comparison in validation tests. This enables users to see "screenshot shown in their of that time to see if that got detected" as requested.

## Key Features

- **Real-time Screenshot Capture**: Captures video frames during 4.2V LabJack detection events
- **Ground Truth Matching**: Compares HIL voltage detections against expected ground truth timing
- **Visual Evidence**: Provides both full frame and zoomed region screenshots
- **Performance Metrics**: Calculates precision, recall, F1-score, and timing accuracy
- **API Integration**: RESTful endpoints for frontend integration

## API Endpoints

### 1. Ground Truth Comparison with Screenshots

**Endpoint**: `GET /api/hil/{session_id}/ground-truth-comparison`

**Description**: Get comprehensive ground truth comparison results with screenshot evidence for HIL testing.

**Parameters**:
- `session_id` (path): HIL test session identifier
- `tolerance_ms` (query, optional): Tolerance window for ground truth matching (default: 100ms)
- `include_screenshots` (query, optional): Whether to include screenshot URLs (default: true)

**Response**:
```json
{
  "session_id": "session-uuid",
  "test_session_info": {
    "name": "HIL Test Session",
    "status": "completed",
    "video_id": "video-uuid",
    "created_at": "2024-01-01T10:00:00Z",
    "completed_at": "2024-01-01T10:05:00Z"
  },
  "ground_truth_analysis": {
    "matching_metrics": {
      "true_positives": 8,
      "false_positives": 1,
      "false_negatives": 0,
      "precision": 0.889,
      "recall": 1.0,
      "f1_score": 0.941,
      "mean_latency_ms": 45.7,
      "within_tolerance_percentage": 95.0
    },
    "detailed_analysis": {
      "temporal_analysis": {
        "mean_offset_ms": 45.7,
        "early_detections": 1,
        "on_time_detections": 7,
        "late_detections": 1
      }
    },
    "tolerance_ms": 100
  },
  "detection_events": [
    {
      "id": "detection-001",
      "timestamp": 1640995215.456,
      "video_relative_timestamp": 15.456,
      "actual_latency_ms": 45.7,
      "video_frame_number": 463,
      "labjack_voltage": 4.2,
      "detection_channel": "AIN0",
      "timing_sync_quality": "high",
      "validation_result": "Pass",
      "screenshot_url": "/api/hil/screenshots/hil_detection_001.jpg",
      "screenshot_zoom_url": "/api/hil/screenshots/hil_detection_001_zoom.jpg",
      "created_at": "2024-01-01T10:00:15Z"
    }
  ],
  "summary": {
    "total_detections": 9,
    "detections_with_screenshots": 9,
    "precision": 0.889,
    "recall": 1.0,
    "f1_score": 0.941,
    "mean_latency_ms": 45.7,
    "within_tolerance_percentage": 95.0
  },
  "visual_evidence": {
    "screenshots_available": true,
    "screenshot_count": 9,
    "zoom_screenshot_count": 9
  }
}
```

### 2. HIL Detection Events

**Endpoint**: `GET /api/hil/{session_id}/detection-events`

**Description**: Get HIL detection events with screenshot evidence and timing data.

**Parameters**:
- `session_id` (path): HIL test session identifier
- `include_screenshots` (query, optional): Whether to include screenshot URLs (default: true)

**Response**:
```json
{
  "session_id": "session-uuid",
  "detection_events": [
    {
      "id": "detection-001",
      "detection_id": "det-uuid",
      "timestamp": 1640995215.456,
      "video_relative_timestamp": 15.456,
      "actual_latency_ms": 45.7,
      "video_frame_number": 463,
      "labjack_voltage": 4.2,
      "detection_channel": "AIN0",
      "timing_sync_quality": "high",
      "validation_result": "Pass",
      "source": "dedicated_labjack_monitor",
      "detection_type": "labjack_voltage",
      "screenshots": {
        "screenshot_url": "/api/hil/screenshots/hil_detection_001.jpg",
        "screenshot_filename": "hil_detection_001.jpg",
        "screenshot_exists": true,
        "screenshot_zoom_url": "/api/hil/screenshots/hil_detection_001_zoom.jpg",
        "screenshot_zoom_filename": "hil_detection_001_zoom.jpg",
        "screenshot_zoom_exists": true
      },
      "created_at": "2024-01-01T10:00:15Z"
    }
  ],
  "summary": {
    "total_events": 9,
    "events_with_screenshots": 9,
    "latest_event_time": 1640995275.123,
    "earliest_event_time": 1640995215.456
  }
}
```

### 3. Screenshot Serving

**Endpoint**: `GET /api/hil/screenshots/{screenshot_filename}`

**Description**: Serve HIL screenshot files for display in the frontend.

**Parameters**:
- `screenshot_filename` (path): Name of the screenshot file

**Response**: Image file (JPEG)

**Example URLs**:
- `/api/hil/screenshots/hil_detection_001.jpg` - Full frame screenshot
- `/api/hil/screenshots/hil_detection_001_zoom.jpg` - Zoomed region screenshot

### 4. HIL Analysis Summary

**Endpoint**: `GET /api/hil/{session_id}/analysis`

**Description**: Get comprehensive HIL analysis summary with performance metrics.

**Parameters**:
- `session_id` (path): HIL test session identifier

**Response**:
```json
{
  "session_id": "session-uuid",
  "analysis_summary": {
    "temporal_analysis": {
      "mean_offset_ms": 45.7,
      "early_detections": 1,
      "on_time_detections": 7,
      "late_detections": 1
    },
    "recommendations": [
      "System performance is within acceptable parameters"
    ]
  },
  "visual_evidence_summary": {
    "total_detections": 9,
    "detections_with_screenshots": 9,
    "screenshot_coverage_percentage": 100.0
  },
  "performance_assessment": {
    "overall_status": "PASS",
    "timing_accuracy": "HIGH",
    "visual_evidence": "COMPLETE"
  }
}
```

## Screenshot Types

### Full Frame Screenshots
- **Filename**: `hil_detection_{detection_id}.jpg`
- **Content**: Complete video frame with HIL detection overlay
- **Annotations**:
  - Yellow detection region rectangle
  - HIL 4.2V detection label
  - Video timestamp overlay
  - Red circle marking detection center

### Zoomed Region Screenshots
- **Filename**: `hil_detection_{detection_id}_zoom.jpg`
- **Content**: Center region of frame (400x400 pixels)
- **Annotations**:
  - HIL detection timestamp
  - Enhanced visibility for detailed analysis

## Integration Workflow

### 1. HIL Test Execution
```python
# Start HIL monitoring with video synchronization
from services.dedicated_labjack_monitor import start_hil_monitoring

config = {
    'video_id': 'video-uuid',
    'fps': 30.0,
    'duration': 60.0,
    'channels': ['AIN0'],
    'voltage_threshold': 4.0,
    'video_path': '/path/to/video.mp4'  # Required for screenshot capture
}

success = start_hil_monitoring(session_id, config)
```

### 2. Real-time Detection Processing
When a 4.2V signal is detected:
1. **Voltage Detection**: LabJack detects 4.2V signal
2. **Timestamp Synchronization**: Converts to video-relative timing
3. **Frame Capture**: Extracts exact video frame at detection moment
4. **Screenshot Generation**: Creates annotated full frame and zoom images
5. **Ground Truth Matching**: Compares against expected timing
6. **Database Storage**: Stores detection with screenshot paths

### 3. Frontend Integration
```javascript
// Get ground truth comparison with screenshots
const response = await fetch(`/api/hil/${sessionId}/ground-truth-comparison?include_screenshots=true`);
const data = await response.json();

// Display screenshots in UI
data.detection_events.forEach(event => {
    if (event.screenshot_url) {
        const img = document.createElement('img');
        img.src = event.screenshot_url;
        img.alt = `HIL Detection at ${event.video_relative_timestamp}s`;
        container.appendChild(img);
    }
});
```

## File Storage Structure

```
backend/
├── screenshots/
│   └── hil/
│       ├── hil_detection_001.jpg          # Full frame screenshots
│       ├── hil_detection_001_zoom.jpg     # Zoomed region screenshots
│       ├── hil_detection_002.jpg
│       ├── hil_detection_002_zoom.jpg
│       └── ...
└── static file serving at /screenshots/*
```

## Error Handling

### Common Error Responses

**404 - Session Not Found**:
```json
{
  "detail": "Test session session-uuid not found"
}
```

**404 - Screenshot Not Found**:
```json
{
  "detail": "Screenshot filename.jpg not found"
}
```

**500 - Internal Server Error**:
```json
{
  "detail": "Internal server error: specific error message"
}
```

## Performance Considerations

- **Concurrent Processing**: Screenshot capture runs in background threads
- **Memory Management**: Video captures are cleaned up after sessions
- **File Optimization**: JPEG compression for reasonable file sizes
- **Caching**: Static file serving with appropriate headers

## Testing

Run the HIL screenshot capture tests:
```bash
cd backend
python -m pytest tests/test_hil_screenshot_capture.py -v
```

## Configuration Requirements

### Environment Variables
- Ensure `screenshots` directory is writable
- Video files must be accessible to the backend service

### Dependencies
- `opencv-python` for video frame capture
- `numpy` for image processing
- `pathlib` for file management

## Security Considerations

- Screenshot filenames are validated for security
- Only image files are served through screenshot endpoints
- File paths are sanitized to prevent directory traversal

## Summary

The HIL Testing API provides comprehensive ground truth comparison with visual evidence, addressing the user's request for "screenshot shown in their of that time to see if that got detected." The system captures video frames at the exact moment of LabJack voltage detections, enabling precise validation of HIL test performance with visual confirmation.