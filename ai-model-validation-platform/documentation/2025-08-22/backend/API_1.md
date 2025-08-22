# API Documentation

## Overview

The AI Model Validation Platform API provides endpoints for managing VRU detection validation projects, uploading videos, running tests, and analyzing results.

**Base URL**: `http://localhost:8000` (development)

## Authentication

**Note**: Authentication has been removed for simplified deployment. All endpoints are now publicly accessible.

## API Endpoints

### Health and Status

#### GET /health
Returns the health status of the API.

**Response:**
```json
{
  "status": "healthy"
}
```

#### GET /
Returns basic API information.

**Response:**
```json
{
  "message": "AI Model Validation Platform API"
}
```

### Projects

#### GET /api/projects
List all projects.

**Query Parameters:**
- `skip` (integer, optional): Number of projects to skip (default: 0)
- `limit` (integer, optional): Maximum number of projects to return (default: 100)

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Project Name",
    "description": "Project description",
    "camera_model": "Camera Model",
    "camera_view": "Front-facing VRU",
    "signal_type": "GPIO",
    "status": "Active",
    "owner_id": "anonymous",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z"
  }
]
```

#### POST /api/projects
Create a new project.

**Request Body:**
```json
{
  "name": "Project Name",
  "description": "Project description",
  "cameraModel": "Camera Model",
  "cameraView": "Front-facing VRU",
  "signalType": "GPIO"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Project Name",
  "description": "Project description",
  "camera_model": "Camera Model",
  "camera_view": "Front-facing VRU",
  "signal_type": "GPIO",
  "status": "Active",
  "owner_id": "anonymous",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Validation Errors:**
- `400`: Project name is required
- `422`: Invalid input data

#### GET /api/projects/{project_id}
Get a specific project by ID.

**Response:**
```json
{
  "id": "uuid",
  "name": "Project Name",
  "description": "Project description",
  "camera_model": "Camera Model",
  "camera_view": "Front-facing VRU",
  "signal_type": "GPIO",
  "status": "Active",
  "owner_id": "anonymous",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z"
}
```

**Errors:**
- `404`: Project not found

### Videos

#### POST /api/projects/{project_id}/videos
Upload a video file to a project.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `file` (video file)

**Supported Formats:**
- MP4 (.mp4)
- AVI (.avi)  
- MOV (.mov)
- MKV (.mkv)
- WebM (.webm)

**File Size Limit:** 100MB (configurable)

**Response:**
```json
{
  "video_id": "uuid",
  "filename": "video.mp4",
  "status": "uploaded",
  "message": "Video uploaded successfully."
}
```

**Validation Errors:**
- `400`: Invalid file format or file too large
- `404`: Project not found
- `413`: File size exceeds limit

#### GET /api/videos/{video_id}/ground-truth
Get ground truth data for a video.

**Response:**
```json
{
  "video_id": "uuid",
  "annotations": [],
  "status": "pending",
  "message": "Ground truth processing not yet implemented"
}
```

### Test Sessions

#### POST /api/test-sessions
Create a new test session.

**Request Body:**
```json
{
  "name": "Test Session Name",
  "project_id": "uuid",
  "video_id": "uuid",
  "tolerance_ms": 100
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Test Session Name",
  "project_id": "uuid",
  "video_id": "uuid",
  "tolerance_ms": 100,
  "status": "created",
  "started_at": null,
  "completed_at": null,
  "created_at": "2023-01-01T00:00:00Z"
}
```

**Validation Errors:**
- `400`: Test session name is required
- `404`: Project not found

#### GET /api/test-sessions
List test sessions.

**Query Parameters:**
- `project_id` (string, optional): Filter by project ID
- `skip` (integer, optional): Number of sessions to skip (default: 0)
- `limit` (integer, optional): Maximum number of sessions to return (default: 100)

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Test Session Name",
    "project_id": "uuid",
    "video_id": "uuid",
    "tolerance_ms": 100,
    "status": "created",
    "started_at": null,
    "completed_at": null,
    "created_at": "2023-01-01T00:00:00Z"
  }
]
```

#### GET /api/test-sessions/{session_id}/results
Get test results for a session.

**Response:**
```json
{
  "session_id": "uuid",
  "accuracy": 94.2,
  "precision": 92.5,
  "recall": 95.8,
  "f1_score": 94.1,
  "total_detections": 150,
  "true_positives": 142,
  "false_positives": 8,
  "false_negatives": 6,
  "status": "completed"
}
```

### Detection Events

#### POST /api/detection-events
Submit a detection event from Raspberry Pi.

**Request Body:**
```json
{
  "test_session_id": "uuid",
  "timestamp": 1.5,
  "confidence": 0.95,
  "class_label": "pedestrian"
}
```

**Response:**
```json
{
  "detection_id": "uuid",
  "validation_result": null,
  "status": "processed"
}
```

**Validation Errors:**
- `400`: Invalid confidence value (must be 0-1) or negative timestamp

### Dashboard

#### GET /api/dashboard/stats
Get dashboard statistics.

**Response:**
```json
{
  "projectCount": 5,
  "videoCount": 10,
  "testCount": 15,
  "averageAccuracy": 94.2,
  "activeTests": 0,
  "totalDetections": 100
}
```

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message",
  "status_code": 400,
  "error": "Additional error information"
}
```

### HTTP Status Codes

- `200`: Success
- `201`: Created
- `400`: Bad Request (validation error)
- `404`: Not Found
- `409`: Conflict (integrity error)
- `413`: Request Entity Too Large
- `422`: Unprocessable Entity
- `500`: Internal Server Error

### Validation Errors

For validation errors (422), the response includes detailed error information:

```json
{
  "detail": "Input validation failed",
  "errors": [
    {
      "loc": ["field_name"],
      "msg": "Error message",
      "type": "value_error"
    }
  ]
}
```

## Rate Limiting

Currently, no rate limiting is implemented. Consider implementing rate limiting for production deployments.

## CORS

CORS is configured to allow requests from:
- `http://localhost:3000` (development frontend)
- `http://127.0.0.1:3000`
- `http://localhost:8080`
- `http://127.0.0.1:8080`
- Additional origins can be configured via environment variables

## Configuration

API behavior can be customized using environment variables:

- `AIVALIDATION_API_HOST`: API host (default: 0.0.0.0)
- `AIVALIDATION_API_PORT`: API port (default: 8000)
- `AIVALIDATION_MAX_FILE_SIZE`: Maximum upload file size in bytes
- `AIVALIDATION_CORS_ORIGINS`: Comma-separated list of allowed origins

## Examples

### Create Project and Upload Video

```bash
# Create project
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Highway VRU Detection",
    "description": "Testing pedestrian detection on highway footage",
    "cameraModel": "Sony IMX219",
    "cameraView": "Front-facing VRU",
    "signalType": "GPIO"
  }'

# Upload video (replace {project_id} with actual ID)
curl -X POST http://localhost:8000/api/projects/{project_id}/videos \
  -F "file=@test_video.mp4"
```

### Submit Detection Event

```bash
curl -X POST http://localhost:8000/api/detection-events \
  -H "Content-Type: application/json" \
  -d '{
    "test_session_id": "session-uuid",
    "timestamp": 5.25,
    "confidence": 0.87,
    "class_label": "pedestrian"
  }'
```

### Get Dashboard Stats

```bash
curl http://localhost:8000/api/dashboard/stats
```

## SDKs and Libraries

### Python Client Example

```python
import requests

class AIValidationClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def create_project(self, name, description, camera_model, camera_view, signal_type):
        data = {
            "name": name,
            "description": description,
            "cameraModel": camera_model,
            "cameraView": camera_view,
            "signalType": signal_type
        }
        response = requests.post(f"{self.base_url}/api/projects", json=data)
        return response.json()
    
    def upload_video(self, project_id, file_path):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(
                f"{self.base_url}/api/projects/{project_id}/videos",
                files=files
            )
        return response.json()
```

### JavaScript/Node.js Client Example

```javascript
class AIValidationClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }
    
    async createProject(projectData) {
        const response = await fetch(`${this.baseUrl}/api/projects`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(projectData),
        });
        return response.json();
    }
    
    async getProjects() {
        const response = await fetch(`${this.baseUrl}/api/projects`);
        return response.json();
    }
}
```

## WebSocket Support

Currently, the API does not include WebSocket support. Real-time features for test execution monitoring could be implemented using WebSockets or Server-Sent Events in future versions.

## Future Enhancements

Planned API enhancements:
- Real-time test execution monitoring
- Batch operations for projects and videos
- Advanced filtering and search
- Export functionality for results
- Webhook support for notifications
- API versioning support