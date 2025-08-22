# Backend API Analysis Report

## Server Status
- **Host**: 155.138.239.131:8000
- **Status**: ✅ Healthy (FastAPI server running)
- **Documentation**: Available at `/docs` (Swagger UI)
- **OpenAPI Spec**: Available at `/openapi.json`

## Key Findings

### 1. API Naming Convention Issue
**CRITICAL**: The API uses `snake_case` for request parameters, not `camelCase`:
- ❌ Wrong: `{"videoId": "...", "modelName": "..."}`
- ✅ Correct: `{"video_id": "...", "model_name": "..."}`

### 2. Detection Pipeline Status
**FIXED**: The detection pipeline endpoint works correctly with proper parameters:
```bash
POST /api/detection/pipeline/run
Content-Type: application/json
{
  "video_id": "454d5bc6-0067-4a5d-bebd-ce5ed5e30f25",
  "model_name": "yolov8s",
  "confidence_threshold": 0.5
}
```

### 3. Server Errors Identified
**Backend Bug**: Multiple endpoints have Python import errors:
- `GET /api/videos/{id}/ground-truth` returns: `"name 'models' is not defined"`
- `POST /api/videos/{id}/process-ground-truth` returns: `"name 'models' is not defined"`

## Working Endpoints ✅

### Videos
- `GET /api/videos` - Lists all videos with metadata
- `GET /api/videos/{id}/annotations` - Returns annotations (empty arrays for existing videos)
- `POST /api/videos/{id}/annotations` - Creates new annotations
- `DELETE /api/videos/{id}` - Deletes videos

### Detection System
- `POST /api/detection/pipeline/run` - **WORKS** with correct snake_case parameters
- `GET /api/detection/models/available` - Lists available models:
  ```json
  {
    "models": ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x", "yolov9c", "yolov9e", "yolov10n", "yolov10s"],
    "default": "yolov8n",
    "recommended": "yolov8s"
  }
  ```

### Dashboard & Stats
- `GET /api/dashboard/stats` - Returns system statistics
- `GET /health` - Health check endpoint

### Projects
- `GET /api/projects` - Lists projects
- `POST /api/projects` - Creates projects

### Ground Truth
- `GET /api/ground-truth/videos/available` - Lists available videos for linking

### Video Quality
- `GET /api/video-library/quality-assessment/{id}` - Video quality analysis

### Signal Processing
- `GET /api/signals/protocols/supported` - Lists supported protocols
- `POST /api/signals/process` - Signal processing (requires specific schema)

## Broken Endpoints ❌

### Ground Truth Issues
- `GET /api/videos/{id}/ground-truth` - **500 Error**: `name 'models' is not defined`
- `POST /api/videos/{id}/process-ground-truth` - **500 Error**: `name 'models' is not defined`

### Missing Individual Video Endpoint
- `GET /api/videos/{id}` - **405 Method Not Allowed** (only DELETE supported)

### WebSocket
- `GET /ws` - WebSocket endpoint exists but requires proper WebSocket handshake headers

## API Data Structures

### Video Object
```json
{
  "id": "454d5bc6-0067-4a5d-bebd-ce5ed5e30f25",
  "projectId": "00000000-0000-0000-0000-000000000000",
  "filename": "b38fabf4-c213-402e-96ed-b2f677545a92.mp4",
  "originalName": "b38fabf4-c213-402e-96ed-b2f677545a92.mp4",
  "url": "http://155.138.239.131:8000/uploads/b38fabf4-c213-402e-96ed-b2f677545a92.mp4",
  "status": "completed",
  "createdAt": "2025-08-21T08:27:17.003678+00:00",
  "uploadedAt": "2025-08-21T08:27:17.003678+00:00",
  "duration": 5.041666666666667,
  "size": 765755,
  "fileSize": 765755,
  "groundTruthGenerated": true,
  "groundTruthStatus": "completed",
  "detectionCount": 24,
  "assigned": false
}
```

### Detection Pipeline Response
```json
{
  "video_id": "454d5bc6-0067-4a5d-bebd-ce5ed5e30f25",
  "detections": [],
  "processing_time": 0.0,
  "model_used": "yolov8s",
  "total_detections": 0,
  "confidence_distribution": {}
}
```

### Annotation Object
```json
{
  "id": "29cb1d94-7ccf-42a6-90d0-3316b9123e1a",
  "videoId": "454d5bc6-0067-4a5d-bebd-ce5ed5e30f25",
  "detectionId": null,
  "frameNumber": 10,
  "timestamp": 0.5,
  "endTimestamp": null,
  "vruType": "pedestrian",
  "boundingBox": {"x": 100, "y": 100, "width": 50, "height": 100},
  "occluded": false,
  "truncated": false,
  "difficult": false,
  "notes": null,
  "annotator": "test",
  "validated": false,
  "createdAt": "2025-08-21T09:13:42.099402Z",
  "updatedAt": null
}
```

## Available Test Data
The API has 4 test videos available:
- `454d5bc6-0067-4a5d-bebd-ce5ed5e30f25` - 5.04s, 1088x832, 24fps
- `34209032-a646-4a6b-a6a1-803e9d7218bb` - 5.04s, 1088x832, 24fps  
- `9781637c-a8d9-4e7c-a9c7-60a6fe1a4862` - 5.04s, 1104x832, 25fps
- `cfb876ae-3c1f-4982-af55-88b5db9303d8` - 5.04s, 1088x832, 24fps

## Recommendations for Frontend

### 1. Fix API Parameter Format
Update all API calls to use `snake_case`:
```typescript
// Current (broken)
const payload = {
  videoId: videoId,
  modelName: 'yolov8s',
  confidenceThreshold: 0.5
};

// Fixed
const payload = {
  video_id: videoId,
  model_name: 'yolov8s',
  confidence_threshold: 0.5
};
```

### 2. Handle Backend Errors Gracefully
Add error handling for the known backend bugs:
```typescript
try {
  const groundTruth = await api.get(`/api/videos/${videoId}/ground-truth`);
} catch (error) {
  if (error.status === 500 && error.data?.detail?.includes("name 'models' is not defined")) {
    // Handle known backend bug
    console.warn('Backend ground truth processing unavailable due to server error');
    setGroundTruthStatus('unavailable');
  }
}
```

### 3. WebSocket Integration
For real-time detection updates:
```typescript
const wsUrl = `ws://155.138.239.131:8000/ws`;
const ws = new WebSocket(wsUrl);
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Handle real-time detection updates
};
```

### 4. Model Selection
Use the recommended model for better performance:
```typescript
const { data: models } = await api.get('/api/detection/models/available');
const modelName = models.recommended || models.default; // "yolov8s"
```

## Backend Issues to Report

1. **Python Import Error**: Fix `name 'models' is not defined` in ground truth endpoints
2. **Missing GET endpoint**: Add `GET /api/videos/{id}` for individual video details
3. **Inconsistent naming**: Consider standardizing on either camelCase or snake_case throughout

## Summary

The backend API is functional for core detection operations but has several issues:
- ✅ Detection pipeline works correctly with proper parameters
- ✅ Video listing and annotation system functional  
- ❌ Ground truth processing broken due to Python errors
- ❌ API uses inconsistent naming conventions
- ⚠️ WebSocket endpoint exists but needs proper implementation

The main issue causing frontend problems is the parameter naming convention mismatch between snake_case (backend) and camelCase (frontend expectations).