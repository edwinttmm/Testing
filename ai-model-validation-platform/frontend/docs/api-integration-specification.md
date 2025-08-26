# AI Model Validation Platform - API Integration Specification

## Overview

This document provides comprehensive integration documentation for the AI Model Validation Platform, covering all REST API endpoints, WebSocket protocols, MCP agent coordination, data formats, and external service integrations.

## Table of Contents

1. [REST API Endpoints](#rest-api-endpoints)
2. [WebSocket & Real-time Communication](#websocket--real-time-communication)
3. [MCP Agent Coordination](#mcp-agent-coordination)
4. [Data Formats & Schemas](#data-formats--schemas)
5. [External Integrations](#external-integrations)
6. [Authentication & Security](#authentication--security)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)

---

## REST API Endpoints

### Base Configuration
- **Base URL**: `http://155.138.239.131:8000` (Production) / `http://localhost:8000` (Development)
- **Content-Type**: `application/json`
- **Timeout**: 30 seconds
- **Rate Limiting**: Not explicitly configured (consider implementing)

### Project Management APIs

#### Create Project
```http
POST /api/projects
Content-Type: application/json

{
  "name": "string",
  "description": "string (optional)",
  "cameraModel": "string",
  "cameraView": "Front-facing VRU" | "Rear-facing VRU" | "In-Cab Driver Behavior" | "Multi-angle",
  "lensType": "string (optional)",
  "resolution": "string (optional)",
  "frameRate": number,
  "signalType": "GPIO" | "Network Packet" | "Serial" | "CAN Bus"
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "string",
  "status": "draft" | "active" | "testing" | "analysis" | "completed" | "archived",
  "ownerId": "uuid",
  "createdAt": "ISO 8601 datetime",
  "updatedAt": "ISO 8601 datetime",
  ...
}
```

#### Get Projects
```http
GET /api/projects?skip=0&limit=100
```

#### Get Project
```http
GET /api/projects/{project_id}
```

#### Update Project
```http
PUT /api/projects/{project_id}
Content-Type: application/json

{
  // Partial project fields for update
}
```

#### Delete Project
```http
DELETE /api/projects/{project_id}
```

### Video Management APIs

#### Upload Video to Project
```http
POST /api/projects/{project_id}/videos
Content-Type: multipart/form-data

file: <video file>
```

**Response:**
```json
{
  "id": "uuid",
  "projectId": "uuid",
  "filename": "string",
  "originalName": "string",
  "size": number,
  "fileSize": number,
  "duration": number,
  "uploadedAt": "ISO 8601 datetime",
  "createdAt": "ISO 8601 datetime",
  "status": "uploaded" | "processing" | "processed" | "error",
  "groundTruthGenerated": boolean,
  "processingStatus": "pending" | "processing" | "completed" | "failed",
  "detectionCount": number,
  "message": "string"
}
```

#### Central Video Upload (No Project Required)
```http
POST /api/videos
Content-Type: multipart/form-data

file: <video file>
```

#### Get Project Videos
```http
GET /api/projects/{project_id}/videos
```

#### Get All Videos
```http
GET /api/videos?unassigned=false&skip=0&limit=100
```

#### Get Video
```http
GET /api/videos/{video_id}
```

#### Delete Video
```http
DELETE /api/videos/{video_id}
```

#### Link Videos to Project
```http
POST /api/projects/{project_id}/videos/link
Content-Type: application/json

{
  "video_ids": ["uuid1", "uuid2", ...]
}
```

#### Get Linked Videos
```http
GET /api/projects/{project_id}/videos/linked
```

#### Unlink Video from Project
```http
DELETE /api/projects/{project_id}/videos/{video_id}/unlink
```

### Ground Truth & Annotation APIs

#### Get Ground Truth Data
```http
GET /api/videos/{video_id}/ground-truth
```

**Response:**
```json
{
  "video_id": "uuid",
  "objects": [
    {
      "id": "uuid",
      "timestamp": number,
      "frame_number": number,
      "class_label": "pedestrian" | "cyclist" | "motorcyclist",
      "x": number,
      "y": number,
      "width": number,
      "height": number,
      "bounding_box": {
        "x": number,
        "y": number,
        "width": number,
        "height": number,
        "confidence": number,
        "label": "string"
      },
      "confidence": number,
      "validated": boolean,
      "difficult": boolean
    }
  ],
  "total_detections": number,
  "status": "pending" | "processing" | "completed" | "error"
}
```

#### Process Ground Truth
```http
POST /api/videos/{video_id}/process-ground-truth
```

#### Create Annotation
```http
POST /api/videos/{video_id}/annotations
Content-Type: application/json

{
  "detection_id": "string",
  "frame_number": number,
  "timestamp": number,
  "vru_type": "pedestrian" | "cyclist" | "motorcyclist",
  "bounding_box": {
    "x": number,
    "y": number,
    "width": number,
    "height": number,
    "confidence": number,
    "label": "string"
  },
  "occluded": boolean,
  "truncated": boolean,
  "difficult": boolean,
  "notes": "string",
  "annotator": "string",
  "validated": boolean
}
```

#### Get Annotations
```http
GET /api/videos/{video_id}/annotations?validated_only=false
```

#### Update Annotation
```http
PUT /api/annotations/{annotation_id}
Content-Type: application/json

{
  // Partial annotation fields for update
}
```

#### Delete Annotation
```http
DELETE /api/annotations/{annotation_id}
```

#### Validate Annotation
```http
PATCH /api/annotations/{annotation_id}/validate?validated=true
```

#### Get Annotations by Detection ID
```http
GET /api/annotations/detection/{detection_id}
```

#### Export Annotations
```http
GET /api/videos/{video_id}/annotations/export?format=json|coco|yolo|pascal_voc
```

#### Import Annotations
```http
POST /api/videos/{video_id}/annotations/import?format=json|coco|yolo|pascal_voc
Content-Type: multipart/form-data

file: <annotation file>
```

### Test Session Management APIs

#### Create Test Session
```http
POST /api/test-sessions
Content-Type: application/json

{
  "name": "string",
  "project_id": "uuid",
  "video_id": "uuid",
  "tolerance_ms": 100
}
```

#### Get Test Sessions
```http
GET /api/test-sessions?project_id={project_id}
```

#### Get Test Session
```http
GET /api/test-sessions/{session_id}
```

#### Execute Test
```http
POST /api/projects/{project_id}/execute-test
Content-Type: application/json

{
  "session_id": "uuid",
  "configuration": {
    // Test configuration parameters
  }
}
```

#### Get Test Status
```http
GET /api/test-sessions/{session_id}/status
```

#### Get Test Results
```http
GET /api/test-sessions/{session_id}/results
```

### Detection Pipeline APIs

#### Run Detection Pipeline
```http
POST /api/detection/pipeline/run
Content-Type: application/json

{
  "video_id": "uuid",
  "confidence_threshold": 0.7,
  "nms_threshold": 0.45,
  "model_name": "yolov8n",
  "target_classes": ["pedestrian", "cyclist", "motorcyclist"]
}
```

**Response:**
```json
{
  "video_id": "uuid",
  "detections": [
    {
      "detection_id": "string",
      "timestamp": number,
      "frame_number": number,
      "class_label": "string",
      "confidence": number,
      "bounding_box_x": number,
      "bounding_box_y": number,
      "bounding_box_width": number,
      "bounding_box_height": number,
      "vru_type": "string",
      "screenshot_path": "string",
      "screenshot_zoom_path": "string",
      "processing_time_ms": number,
      "model_version": "string"
    }
  ],
  "processing_time": number,
  "model_used": "string",
  "total_detections": number,
  "confidence_distribution": {
    "0.5-0.6": number,
    "0.6-0.7": number,
    "0.7-0.8": number,
    "0.8-0.9": number,
    "0.9-1.0": number
  }
}
```

#### Get Available Models
```http
GET /api/detection/models/available
```

**Response:**
```json
{
  "models": ["yolov8n", "yolov8s", "yolov8m", "yolov8l", "yolov8x"],
  "default": "yolov8n",
  "recommended": "yolov8m"
}
```

#### Get Video Detections
```http
GET /api/videos/{video_id}/detections
```

#### Get Test Session Detections
```http
GET /api/test-sessions/{session_id}/detections
```

### Signal Processing APIs

#### Process Signal
```http
POST /api/signals/process
Content-Type: application/json

{
  "signal_type": "GPIO" | "Network Packet" | "Serial" | "CAN Bus",
  "signal_data": {
    // Signal-specific data structure
  },
  "processing_config": {
    // Optional processing configuration
  }
}
```

#### Get Supported Protocols
```http
GET /api/signals/protocols/supported
```

### Statistical Validation APIs

#### Run Statistical Validation
```http
POST /api/validation/statistical/run
Content-Type: application/json

{
  "test_session_id": "uuid",
  "confidence_level": 0.95
}
```

#### Get Confidence Intervals
```http
GET /api/validation/confidence-intervals/{session_id}
```

### Dashboard & Analytics APIs

#### Get Dashboard Stats
```http
GET /api/dashboard/stats
```

**Response:**
```json
{
  "projectCount": number,
  "videoCount": number,
  "testCount": number,
  "totalDetections": number,
  "averageAccuracy": number,
  "activeTests": number,
  "confidence_intervals": {
    "precision": [number, number],
    "recall": [number, number],
    "f1_score": [number, number]
  },
  "trend_analysis": {
    "accuracy_trend": "string",
    "detection_trend": "string"
  },
  "signal_processing_metrics": {
    // Signal processing statistics
  }
}
```

### Health Check APIs

#### Basic Health Check
```http
GET /health
```

#### Detailed Health Check
```http
GET /health/detailed
```

#### Database Health
```http
GET /health/database
```

#### Simple Health
```http
GET /health/simple
```

---

## WebSocket & Real-time Communication

### Connection Configuration
- **URL**: `http://155.138.239.131:8001` (Production) / `http://localhost:8001` (Development)
- **Transport**: WebSocket with Socket.IO fallback to polling
- **Timeout**: 20 seconds
- **Reconnection**: Enabled with exponential backoff
- **Heartbeat**: 30-second intervals

### Event Types

#### Connection Events
```typescript
// Connection established
socket.on('connect', () => {
  console.log('Connected to WebSocket server');
});

// Connection error
socket.on('connect_error', (error) => {
  console.error('Connection failed:', error);
});

// Disconnection
socket.on('disconnect', (reason) => {
  console.log('Disconnected:', reason);
});
```

#### Detection Update Events
```typescript
// Real-time detection updates
socket.on('detection_update', (data) => {
  // data structure:
  {
    video_id: "uuid",
    detection_id: "string",
    timestamp: number,
    frame_number: number,
    class_label: "string",
    confidence: number,
    bounding_box: {
      x: number,
      y: number,
      width: number,
      height: number
    },
    status: "new" | "updated" | "validated"
  }
});

// Detection processing progress
socket.on('detection_progress', (data) => {
  // data structure:
  {
    video_id: "uuid",
    progress: number, // 0-100
    current_frame: number,
    total_frames: number,
    eta_seconds: number
  }
});
```

#### Test Session Events
```typescript
// Test session status updates
socket.on('test_session_update', (data) => {
  // data structure:
  {
    session_id: "uuid",
    status: "created" | "running" | "completed" | "failed",
    progress: number,
    results: {
      precision: number,
      recall: number,
      f1_score: number,
      accuracy: number
    }
  }
});
```

#### Video Processing Events
```typescript
// Video upload progress
socket.on('video_upload_progress', (data) => {
  // data structure:
  {
    video_id: "uuid",
    progress: number, // 0-100
    status: "uploading" | "processing" | "completed" | "error"
  }
});

// Ground truth generation progress
socket.on('ground_truth_progress', (data) => {
  // data structure:
  {
    video_id: "uuid",
    progress: number,
    status: "processing" | "completed" | "error",
    detections_found: number
  }
});
```

#### Annotation Collaboration Events
```typescript
// Real-time annotation updates
socket.on('annotation_update', (data) => {
  // data structure:
  {
    video_id: "uuid",
    annotation_id: "uuid",
    action: "created" | "updated" | "deleted" | "validated",
    annotator: "string",
    timestamp: number,
    annotation: {
      // Full annotation object
    }
  }
});

// Collaborative cursor/selection
socket.on('annotation_cursor', (data) => {
  // data structure:
  {
    video_id: "uuid",
    annotator: "string",
    frame_number: number,
    cursor_x: number,
    cursor_y: number,
    selected_annotation: "uuid" | null
  }
});
```

#### System Status Events
```typescript
// System health updates
socket.on('system_status', (data) => {
  // data structure:
  {
    component: "api" | "database" | "ml_pipeline" | "storage",
    status: "healthy" | "degraded" | "error",
    message: "string",
    timestamp: number
  }
});
```

### Client-side WebSocket Integration

```typescript
import { useWebSocket } from '../services/websocketService';

const MyComponent = () => {
  const {
    isConnected,
    connectionState,
    lastMessage,
    error,
    emit,
    subscribe,
    metrics,
    healthStatus
  } = useWebSocket('detection_update');

  useEffect(() => {
    // Subscribe to specific events
    const unsubscribe = subscribe('test_session_update', (data) => {
      console.log('Test session update:', data);
    });

    return unsubscribe;
  }, [subscribe]);

  const handleStartTest = () => {
    emit('start_test', { session_id: 'uuid' });
  };

  return (
    <div>
      <p>Connection Status: {connectionState}</p>
      <p>Is Connected: {isConnected ? 'Yes' : 'No'}</p>
      {error && <p>Error: {error}</p>}
      <button onClick={handleStartTest} disabled={!isConnected}>
        Start Test
      </button>
    </div>
  );
};
```

---

## MCP Agent Coordination

### Agent Spawning Protocol

#### Initialize Coordination Swarm
```bash
npx claude-flow@alpha swarm init --topology mesh --max-agents 6
```

#### Pre-task Coordination Hook
```bash
npx claude-flow@alpha hooks pre-task --description "Task description"
```

#### Session Restoration Hook
```bash
npx claude-flow@alpha hooks session-restore --session-id "swarm-session-id"
```

#### Post-edit Coordination Hook
```bash
npx claude-flow@alpha hooks post-edit --file "file-path" --memory-key "swarm/component/step"
```

#### Post-task Completion Hook
```bash
npx claude-flow@alpha hooks post-task --task-id "task-id"
```

### Agent Types and Capabilities

#### Core Development Agents
- **coder**: Implementation and code generation
- **reviewer**: Code quality and security review
- **tester**: Test creation and validation
- **architect**: System design and architecture

#### Specialized Agents
- **ml-developer**: Machine learning pipeline development
- **api-docs**: API documentation generation
- **performance-analyzer**: Performance optimization
- **security-manager**: Security validation and hardening

#### Data Processing Agents
- **code-analyzer**: Code analysis and metrics
- **detection-pipeline**: Video detection processing
- **annotation-processor**: Annotation management

### Memory Coordination Protocol

#### Store Operation State
```javascript
// Via hooks
npx claude-flow@alpha hooks post-edit --memory-key "swarm/video-processing/frame-analysis"

// Direct memory operations
mcp__claude-flow__memory_usage {
  action: "store",
  key: "detection-results",
  value: JSON.stringify(detectionData),
  namespace: "video-processing",
  ttl: 3600
}
```

#### Retrieve Coordination Data
```javascript
mcp__claude-flow__memory_usage {
  action: "retrieve",
  key: "detection-results",
  namespace: "video-processing"
}
```

#### Search Memory Patterns
```javascript
mcp__claude-flow__memory_search {
  pattern: "detection-*",
  namespace: "video-processing",
  limit: 10
}
```

---

## Data Formats & Schemas

### Project Schema
```typescript
interface Project {
  id: string;
  name: string;
  description?: string;
  cameraModel: string;
  cameraView: 'Front-facing VRU' | 'Rear-facing VRU' | 'In-Cab Driver Behavior' | 'Multi-angle';
  lensType?: string;
  resolution?: string;
  frameRate?: number;
  signalType: 'GPIO' | 'Network Packet' | 'Serial' | 'CAN Bus';
  status: 'draft' | 'active' | 'testing' | 'analysis' | 'completed' | 'archived';
  ownerId: string;
  createdAt: string;
  updatedAt?: string;
}
```

### Video Schema
```typescript
interface VideoFile {
  id: string;
  projectId: string;
  filename: string;
  originalName: string;
  filePath: string;
  fileSize: number;
  size: number;
  duration?: number;
  fps?: number;
  resolution?: string;
  status: 'uploaded' | 'processing' | 'processed' | 'error';
  processingStatus: 'pending' | 'processing' | 'completed' | 'failed';
  groundTruthGenerated: boolean;
  detectionCount: number;
  url: string;
  createdAt: string;
  updatedAt?: string;
}
```

### Detection Event Schema
```typescript
interface DetectionEvent {
  id: string;
  testSessionId: string;
  detectionId?: string;
  timestamp: number;
  frameNumber?: number;
  confidence?: number;
  classLabel?: string;
  vruType?: string;
  boundingBoxX?: number;
  boundingBoxY?: number;
  boundingBoxWidth?: number;
  boundingBoxHeight?: number;
  validationResult?: 'TP' | 'FP' | 'FN';
  groundTruthMatchId?: string;
  screenshotPath?: string;
  screenshotZoomPath?: string;
  processingTimeMs?: number;
  modelVersion?: string;
  createdAt: string;
}
```

### Ground Truth Annotation Schema
```typescript
interface GroundTruthAnnotation {
  id: string;
  videoId: string;
  detectionId?: string;
  frameNumber: number;
  timestamp: number;
  endTimestamp?: number;
  vruType: 'pedestrian' | 'cyclist' | 'motorcyclist' | 'wheelchair_user' | 'scooter_rider';
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
    confidence: number;
    label: string;
  };
  occluded: boolean;
  truncated: boolean;
  difficult: boolean;
  notes?: string;
  annotator?: string;
  validated: boolean;
  createdAt: string;
  updatedAt?: string;
}
```

### Test Session Schema
```typescript
interface TestSession {
  id: string;
  name: string;
  projectId: string;
  videoId: string;
  toleranceMs: number;
  status: 'created' | 'running' | 'completed' | 'failed';
  startedAt?: string;
  completedAt?: string;
  createdAt: string;
  updatedAt?: string;
}
```

### Validation Result Schema
```typescript
interface ValidationResult {
  sessionId: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  totalDetections: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  status: string;
  confidenceIntervals?: {
    precision: [number, number];
    recall: [number, number];
    f1Score: [number, number];
    accuracy: [number, number];
  };
  statisticalAnalysis?: {
    pValue: number;
    confidenceLevel: number;
    sampleSize: number;
    statisticallySignificant: boolean;
  };
}
```

### Export/Import Formats

#### COCO Format
```json
{
  "images": [
    {
      "id": 1,
      "width": 1920,
      "height": 1080,
      "file_name": "frame_0001.jpg"
    }
  ],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 1,
      "bbox": [x, y, width, height],
      "area": number,
      "iscrowd": 0
    }
  ],
  "categories": [
    {
      "id": 1,
      "name": "pedestrian",
      "supercategory": "person"
    }
  ]
}
```

#### YOLO Format
```
# class_id x_center y_center width height confidence
0 0.5 0.5 0.2 0.3 0.95
1 0.3 0.7 0.15 0.25 0.87
```

---

## External Integrations

### YOLO Model Integration

#### Model Loading
```python
# Backend: services/detection_pipeline_service.py
from ultralytics import YOLO

class DetectionPipeline:
    def __init__(self, model_name="yolov8n"):
        self.model = YOLO(f"{model_name}.pt")
        
    def process_video(self, video_path, config):
        results = self.model(
            video_path,
            conf=config.confidence_threshold,
            iou=config.nms_threshold,
            classes=config.target_class_ids
        )
        return self.format_detections(results)
```

#### Model Configuration
```json
{
  "model_name": "yolov8n",
  "confidence_threshold": 0.7,
  "nms_threshold": 0.45,
  "target_classes": ["person", "bicycle", "motorcycle"],
  "input_size": [640, 640],
  "max_det": 300,
  "device": "cuda" | "cpu"
}
```

### File Storage System

#### Video Storage Structure
```
uploads/
├── {video_id}.mp4              # Original video file
├── frames/
│   └── {video_id}/
│       ├── frame_0001.jpg      # Extracted frames
│       ├── frame_0002.jpg
│       └── ...
├── screenshots/
│   └── {video_id}/
│       ├── detection_001.jpg   # Detection screenshots
│       ├── detection_001_zoom.jpg
│       └── ...
└── exports/
    └── annotations/
        ├── {video_id}_coco.json
        ├── {video_id}_yolo.txt
        └── ...
```

#### File Access URLs
```
GET /uploads/{video_id}.mp4
GET /screenshots/{video_id}/{detection_id}.jpg
GET /exports/annotations/{video_id}_{format}.{ext}
```

### Database Connectivity

#### SQLAlchemy Configuration
```python
# Backend: database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./ai_validation.db"
# Production: "postgresql://user:pass@host:port/db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

#### Connection Health Check
```python
def check_database_health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            return {"status": "healthy", "latency_ms": latency}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Logging and Monitoring

#### Structured Logging
```python
# Backend: logging_config.py
import logging
import structlog

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

logger = structlog.get_logger()

# Usage
logger.info("Detection completed", 
           video_id=video_id,
           detections_count=count,
           processing_time_ms=time_ms)
```

#### Health Monitoring Endpoints
```python
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.get("/health/detailed")
def detailed_health():
    return {
        "api": check_api_health(),
        "database": check_database_health(),
        "ml_pipeline": check_ml_health(),
        "storage": check_storage_health(),
        "websocket": check_websocket_health()
    }
```

---

## Authentication & Security

### Current Implementation
- **Authentication**: None (Anonymous access)
- **CORS**: Configured for cross-origin requests
- **Rate Limiting**: Not implemented (recommended for production)
- **Input Validation**: Pydantic schemas for request validation
- **File Upload**: Size and type validation

### Recommended Security Enhancements

#### API Key Authentication
```python
# Recommended implementation
from fastapi import Header, HTTPException

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@app.get("/api/projects", dependencies=[Depends(verify_api_key)])
def get_projects():
    # Protected endpoint
    pass
```

#### Rate Limiting
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/projects")
@limiter.limit("10/minute")
def get_projects(request: Request):
    # Rate limited endpoint
    pass
```

### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Error Handling

### Standard Error Response Format
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {
      // Additional error context
    },
    "timestamp": "ISO 8601 datetime",
    "request_id": "uuid"
  }
}
```

### HTTP Status Codes

| Status Code | Description | Usage |
|-------------|-------------|-------|
| 200 | OK | Successful request |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 502 | Bad Gateway | Upstream service error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Error Handling Examples

#### Validation Error
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input parameters",
    "details": {
      "field": "cameraView",
      "value": "InvalidView",
      "allowed_values": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior", "Multi-angle"]
    },
    "timestamp": "2025-01-26T12:00:00Z",
    "request_id": "req-123456"
  }
}
```

#### Not Found Error
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Project not found",
    "details": {
      "resource_type": "project",
      "resource_id": "123e4567-e89b-12d3-a456-426614174000"
    },
    "timestamp": "2025-01-26T12:00:00Z",
    "request_id": "req-123457"
  }
}
```

### Client-side Error Handling
```typescript
// Frontend: services/api.ts
class ApiService {
  private handleError(error: AxiosError): AppError {
    if (error.response) {
      // Server responded with error status
      return {
        name: 'ApiError',
        message: error.response.data?.error?.message || 'Server error',
        status: error.response.status,
        code: error.response.data?.error?.code,
        details: error.response.data?.error?.details
      };
    } else if (error.request) {
      // Network error
      return {
        name: 'NetworkError',
        message: 'Network error - please check your connection',
        status: 0,
        code: 'NETWORK_ERROR'
      };
    } else {
      // Request setup error
      return {
        name: 'RequestError',
        message: error.message,
        status: 0,
        code: 'REQUEST_ERROR'
      };
    }
  }
}
```

---

## Performance Considerations

### API Response Optimization

#### Pagination
```http
GET /api/projects?skip=0&limit=20
GET /api/videos?skip=0&limit=50
```

#### Field Selection
```http
GET /api/projects?fields=id,name,status,createdAt
```

#### Caching Strategy
```typescript
// Frontend: services/api.ts
class ApiService {
  private async cachedRequest<T>(
    method: string,
    url: string,
    data?: unknown
  ): Promise<T> {
    // Check cache for GET requests
    if (method === 'GET') {
      const cached = apiCache.get<T>(method, url);
      if (cached) return cached;
    }
    
    const response = await this.api.request({ method, url, data });
    
    // Cache successful GET responses
    if (method === 'GET') {
      apiCache.set(method, url, response.data);
    }
    
    return response.data;
  }
}
```

### Database Optimization

#### Indexing Strategy
```sql
-- Core indexes for performance-critical queries
CREATE INDEX idx_video_project_status ON videos(project_id, status);
CREATE INDEX idx_video_project_created ON videos(project_id, created_at);
CREATE INDEX idx_gt_video_timestamp ON ground_truth_objects(video_id, timestamp);
CREATE INDEX idx_detection_session_timestamp ON detection_events(test_session_id, timestamp);
```

#### Connection Pooling
```python
# Backend: database.py
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=300
)
```

### File Upload Optimization

#### Chunked Upload Support
```typescript
// Frontend: Recommended implementation
async uploadVideoChunked(file: File, chunkSize: number = 5 * 1024 * 1024) {
  const totalChunks = Math.ceil(file.size / chunkSize);
  
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex++) {
    const start = chunkIndex * chunkSize;
    const end = Math.min(start + chunkSize, file.size);
    const chunk = file.slice(start, end);
    
    await this.uploadChunk(chunk, chunkIndex, totalChunks, file.name);
  }
}
```

#### Background Processing
```python
# Backend: Background task processing
from fastapi import BackgroundTasks

@app.post("/api/videos/{video_id}/process-ground-truth")
async def process_ground_truth(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    background_tasks.add_task(
        ground_truth_service.process_video,
        video_id,
        db
    )
    return {"message": "Processing started", "video_id": video_id}
```

### WebSocket Performance

#### Connection Pooling
```typescript
// Frontend: WebSocket connection management
class WebSocketService {
  private connectionPool: Map<string, Socket> = new Map();
  
  getConnection(namespace: string = '/'): Socket {
    if (!this.connectionPool.has(namespace)) {
      const socket = io(`${this.url}${namespace}`);
      this.connectionPool.set(namespace, socket);
    }
    return this.connectionPool.get(namespace)!;
  }
}
```

#### Message Batching
```typescript
// Frontend: Batch WebSocket messages
class WebSocketService {
  private messageQueue: any[] = [];
  private batchTimer?: NodeJS.Timeout;
  
  queueMessage(message: any) {
    this.messageQueue.push(message);
    
    if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => {
        this.flushMessageQueue();
      }, 100);
    }
  }
  
  private flushMessageQueue() {
    if (this.messageQueue.length > 0) {
      this.emit('batch_messages', this.messageQueue);
      this.messageQueue = [];
    }
    this.batchTimer = undefined;
  }
}
```

---

## Integration Examples

### Complete Video Processing Workflow
```typescript
async function processVideoWorkflow(projectId: string, videoFile: File) {
  try {
    // 1. Upload video
    const uploadedVideo = await apiService.uploadVideo(
      projectId, 
      videoFile, 
      (progress) => console.log(`Upload: ${progress}%`)
    );
    
    // 2. Subscribe to processing updates
    const unsubscribe = websocketService.subscribe('ground_truth_progress', (data) => {
      if (data.video_id === uploadedVideo.id) {
        console.log(`Ground truth: ${data.progress}%`);
      }
    });
    
    // 3. Start ground truth processing
    await apiService.get(`/api/videos/${uploadedVideo.id}/process-ground-truth`);
    
    // 4. Wait for completion and get results
    const groundTruth = await apiService.getGroundTruth(uploadedVideo.id);
    
    // 5. Create test session
    const testSession = await apiService.createTestSession({
      name: `Test ${videoFile.name}`,
      project_id: projectId,
      video_id: uploadedVideo.id,
      tolerance_ms: 100
    });
    
    // 6. Run detection pipeline
    const detectionResults = await apiService.runDetectionPipeline(uploadedVideo.id, {
      confidenceThreshold: 0.7,
      nmsThreshold: 0.45,
      modelName: 'yolov8n',
      targetClasses: ['pedestrian', 'cyclist', 'motorcyclist']
    });
    
    // 7. Get validation results
    const validationResults = await apiService.getTestResults(testSession.id);
    
    console.log('Workflow completed:', {
      video: uploadedVideo,
      groundTruth,
      detections: detectionResults,
      validation: validationResults
    });
    
    unsubscribe();
    
  } catch (error) {
    console.error('Workflow failed:', error);
    throw error;
  }
}
```

### Real-time Annotation Collaboration
```typescript
function setupAnnotationCollaboration(videoId: string) {
  const websocket = useWebSocket();
  
  // Subscribe to annotation updates
  useEffect(() => {
    const unsubscribe = websocket.subscribe('annotation_update', (data) => {
      if (data.video_id === videoId) {
        // Update local annotation state
        updateAnnotationInStore(data.annotation);
        
        // Show notification
        showNotification(`${data.annotator} ${data.action} an annotation`);
      }
    });
    
    return unsubscribe;
  }, [videoId]);
  
  // Send annotation updates
  const handleAnnotationUpdate = useCallback((annotation) => {
    // Update local state
    updateAnnotationInStore(annotation);
    
    // Broadcast to other users
    websocket.emit('annotation_update', {
      video_id: videoId,
      annotation_id: annotation.id,
      action: 'updated',
      annotator: 'current_user',
      timestamp: Date.now(),
      annotation
    });
  }, [videoId, websocket]);
  
  return { handleAnnotationUpdate };
}
```

This comprehensive integration specification provides complete documentation for all API endpoints, WebSocket protocols, MCP agent coordination, data formats, and external service integrations in the AI Model Validation Platform.