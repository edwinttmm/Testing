# Frontend-Backend Integration Flow Analysis

## Overview
This document provides a comprehensive analysis of all frontend-backend API interactions, data flows, and communication patterns in the AI Model Validation Platform.

## Architecture Overview
```
┌─────────────────┐    HTTP/WebSocket    ┌──────────────────┐
│   React Frontend│ ◄─────────────────── │  FastAPI Backend │
│   (Port 3000)   │                      │   (Port 8000)    │
└─────────────────┘                      └──────────────────┘
         │                                         │
         │                                         │
    ┌────▼────┐                              ┌────▼────┐
    │ API     │                              │Database │
    │ Service │                              │SQLAlchemy│
    │ Layer   │                              │ ORM     │
    └─────────┘                              └─────────┘
```

## Primary Integration Points

### 1. HTTP API Communication

#### Core API Service (`frontend/src/services/api.ts`)
- **Base URL**: `http://localhost:8000` (development)
- **Transport**: Axios HTTP client
- **Authentication**: None (removed for current implementation)
- **Timeout**: 30 seconds with retry logic
- **Error Handling**: Comprehensive error transformation

#### Request/Response Flow
```
Frontend Component
    ↓ (API Call)
ApiService.cachedRequest()
    ↓ (HTTP Request)
Axios Interceptors (Request/Response)
    ↓ (Network)
FastAPI Backend
    ↓ (Route Handler)
CRUD Operations
    ↓ (Database)
SQLAlchemy ORM
```

### 2. Data Transformation Layers

#### Frontend → Backend (Camelcase to Snake_case)
```javascript
// Frontend (camelCase)
const projectData = {
  cameraView: "Front-facing VRU",
  signalType: "GPIO",
  frameRate: 30
}

// Automatically converted to snake_case for backend
const backendData = {
  camera_view: "Front-facing VRU",
  signal_type: "GPIO", 
  frame_rate: 30
}
```

#### Backend → Frontend (Pydantic Serialization)
```python
# Backend uses Pydantic with camelCase aliases
class ProjectResponse(CamelCaseModel):
    camera_view: CameraTypeEnum  # Serialized as "cameraView"
    signal_type: SignalTypeEnum  # Serialized as "signalType"
    frame_rate: Optional[int]    # Serialized as "frameRate"
```

## API Endpoints Analysis

### Project Management
| Method | Endpoint | Frontend Function | Backend Handler | Purpose |
|--------|----------|-------------------|-----------------|---------|
| GET | `/api/projects` | `getProjects()` | `get_projects()` | List user projects |
| POST | `/api/projects` | `createProject()` | `create_project()` | Create new project |
| GET | `/api/projects/{id}` | `getProject()` | `get_project()` | Get project details |
| PUT | `/api/projects/{id}` | `updateProject()` | `update_project()` | Update project |
| DELETE | `/api/projects/{id}` | `deleteProject()` | `delete_project()` | Delete project |

### Video Management
| Method | Endpoint | Frontend Function | Backend Handler | Purpose |
|--------|----------|-------------------|-----------------|---------|
| GET | `/api/projects/{id}/videos` | `getVideos()` | `get_project_videos()` | Get project videos |
| POST | `/api/projects/{id}/videos` | `uploadVideo()` | `upload_video()` | Upload video to project |
| POST | `/api/videos` | `uploadVideoCentral()` | `upload_video_central()` | Central video upload |
| GET | `/api/videos` | `getAllVideos()` | `get_all_videos()` | List all videos |
| DELETE | `/api/videos/{id}` | `deleteVideo()` | `delete_video()` | Delete video |

### Ground Truth Management
| Method | Endpoint | Frontend Function | Backend Handler | Purpose |
|--------|----------|-------------------|-----------------|---------|
| GET | `/api/videos/{id}/ground-truth` | `getGroundTruth()` | `get_video_ground_truth()` | Get ground truth data |
| GET | `/api/videos/{id}/annotations` | `getAnnotations()` | `get_video_annotations()` | Get annotations |
| POST | `/api/videos/{id}/annotations` | `createAnnotation()` | `create_annotation()` | Create annotation |
| PUT | `/api/annotations/{id}` | `updateAnnotation()` | `update_annotation()` | Update annotation |

### Test Execution
| Method | Endpoint | Frontend Function | Backend Handler | Purpose |
|--------|----------|-------------------|-----------------|---------|
| GET | `/api/test-sessions` | `getTestSessions()` | `get_test_sessions()` | List test sessions |
| POST | `/api/test-sessions` | `createTestSession()` | `create_test_session()` | Create test session |
| GET | `/api/test-sessions/{id}/results` | `getTestResults()` | `get_test_results()` | Get test results |

## Data Flow Patterns

### 1. Video Upload Flow
```
1. Frontend: File selection → FormData creation
2. API: POST /api/videos with multipart/form-data
3. Backend: File validation → Disk storage → Database record
4. Response: Enhanced video object with URL
5. Frontend: Cache invalidation → UI update
```

### 2. Ground Truth Processing Flow  
```
1. Frontend: Request ground truth data
2. API: GET /api/videos/{id}/ground-truth
3. Backend: Database query → Data transformation
4. Response: Objects array with bounding boxes
5. Frontend: Video enhancement → URL fixing → Display
```

### 3. Real-time Test Execution Flow
```
1. Frontend: Start test session
2. API: POST /api/test-sessions
3. WebSocket: Connect to real-time updates
4. Backend: LabJack integration → Detection events
5. WebSocket: Stream results to frontend
6. Frontend: Live UI updates
```

## Error Handling Integration

### Frontend Error Processing
```javascript
handleError(error: AxiosError) {
  // Status-based error mapping
  switch (error.response?.status) {
    case 404: return "Resource not found"
    case 500: return "Server error occurred"
    case 503: return "Service temporarily unavailable"
  }
  
  // User-friendly message generation
  // Error reporting to monitoring service
  // Fallback error boundaries
}
```

### Backend Error Responses
```python
# Consistent error structure
{
  "detail": "Human readable message",
  "error": "Technical error details", 
  "status": 400,
  "code": "VALIDATION_ERROR"
}
```

## Performance Optimization

### Caching Strategy
- **Frontend**: ApiCache with request deduplication
- **GET Requests**: Cached with TTL and pattern invalidation
- **Cache Keys**: Method + URL + Parameters
- **Invalidation**: Pattern-based cache clearing

### Request Optimization
- **Retry Logic**: Exponential backoff for failed requests
- **Timeout Handling**: Progressive timeout increases
- **Connection Pooling**: HTTP keep-alive enabled
- **Request Batching**: Multiple operations combined

## Security Considerations

### Data Validation
- **Frontend**: TypeScript type checking + runtime validation
- **Backend**: Pydantic schema validation + SQL injection prevention
- **File Uploads**: MIME type validation + size limits

### CORS Configuration
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

## Integration Failure Points

### Common Issues
1. **CORS Errors**: Mismatched origins between frontend/backend
2. **Timeout Issues**: Long-running operations exceeding limits
3. **Data Format Mismatch**: Inconsistent camelCase/snake_case handling
4. **File Upload Limits**: Size restrictions causing failures
5. **Database Connection**: Pool exhaustion under load

### Recovery Strategies
1. **Automatic Retry**: Built-in retry logic for transient failures
2. **Fallback Data**: Default responses when APIs fail
3. **Cache Fallback**: Serving cached data during outages
4. **User Notification**: Clear error messages with actionable steps

## Performance Bottlenecks

### Identified Issues
1. **Video Enhancement**: Multiple URL transformations per video
2. **Database Queries**: N+1 queries in project/video relationships
3. **File Serving**: Direct file system access without CDN
4. **WebSocket Connections**: Multiple connections per session

### Optimization Recommendations
1. **Batch Processing**: Group multiple API calls
2. **Database Optimization**: Use JOIN queries with eager loading
3. **CDN Integration**: Serve static files through CDN
4. **Connection Pooling**: Reuse WebSocket connections

## Monitoring and Observability

### Logging Integration
- **Frontend**: Structured logging with context
- **Backend**: Request/response logging with timing
- **Error Tracking**: Centralized error collection
- **Performance Metrics**: API response times and success rates

### Health Checks
```javascript
// Frontend health monitoring
await apiService.healthCheck()

// Backend health endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}
```

## Future Integration Enhancements

### Planned Improvements
1. **GraphQL Integration**: More efficient data fetching
2. **Server-Sent Events**: Alternative to WebSocket for one-way updates
3. **API Versioning**: Backward compatibility support
4. **Request/Response Compression**: Reduce bandwidth usage
5. **Authentication Integration**: JWT token-based auth
6. **Rate Limiting**: API usage controls and quotas