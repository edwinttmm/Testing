# Complete API Endpoints Inventory

## Authentication Endpoints

### `/api/auth` (Authentication Router)
- **POST** `/api/auth/login` - User login
- **POST** `/api/auth/register` - User registration
- **POST** `/api/auth/logout` - User logout
- **GET** `/api/auth/me` - Get current user
- **POST** `/api/auth/refresh` - Refresh JWT token
- **POST** `/api/auth/forgot-password` - Password reset request
- **POST** `/api/auth/reset-password` - Password reset confirmation

## Project Management Endpoints

### `/api/projects` (Projects Router)
- **GET** `/api/projects` - List all projects
  - Query parameters: `skip`, `limit`, `status`
- **POST** `/api/projects` - Create new project
  - Request body: `ProjectCreate` schema
- **GET** `/api/projects/{project_id}` - Get specific project
- **PUT** `/api/projects/{project_id}` - Update project
  - Request body: `ProjectUpdate` schema
- **DELETE** `/api/projects/{project_id}` - Delete project
- **GET** `/api/projects/{project_id}/videos` - Get project videos
- **POST** `/api/projects/{project_id}/videos` - Assign videos to project
- **GET** `/api/projects/{project_id}/stats` - Project statistics

## Video Management Endpoints

### `/api/videos` (Videos Router)
- **GET** `/api/videos` - List videos
  - Query parameters: `project_id`, `skip`, `limit`, `status`
- **POST** `/api/videos/upload` - Upload video file
  - Form data: Video file + metadata
- **GET** `/api/videos/{video_id}` - Get video details
- **PUT** `/api/videos/{video_id}` - Update video metadata
- **DELETE** `/api/videos/{video_id}` - Delete video
- **GET** `/api/videos/{video_id}/file` - Serve video file
- **POST** `/api/videos/{video_id}/process` - Trigger video processing
- **GET** `/api/videos/{video_id}/ground-truth` - Get ground truth data

### Video Ingestion Pipeline
- **POST** `/api/videos/batch-upload` - Bulk video upload
- **GET** `/api/videos/processing-status` - Get processing status
- **POST** `/api/videos/validate` - Validate video files

## Test Session Management

### `/api/test-sessions` (Test Sessions Router)
- **GET** `/api/test-sessions` - List test sessions
  - Query parameters: `project_id`, `video_id`, `status`
- **POST** `/api/test-sessions` - Create test session
  - Request body: `TestSessionCreate` schema
- **GET** `/api/test-sessions/{session_id}` - Get session details
- **PUT** `/api/test-sessions/{session_id}` - Update session
- **DELETE** `/api/test-sessions/{session_id}` - Delete session
- **POST** `/api/test-sessions/{session_id}/start` - Start test execution
- **POST** `/api/test-sessions/{session_id}/stop` - Stop test execution
- **GET** `/api/test-sessions/{session_id}/results` - Get test results

## LabJack Hardware Integration

### `/api/labjack` (LabJack Hardware Router)
- **GET** `/api/labjack/status` - Hardware connection status
- **POST** `/api/labjack/connect` - Connect to LabJack device
- **POST** `/api/labjack/disconnect` - Disconnect device
- **GET** `/api/labjack/channels` - List available channels
- **POST** `/api/labjack/configure` - Configure device settings
- **GET** `/api/labjack/stream` - Start data streaming
- **POST** `/api/labjack/calibrate` - Calibrate timing system

### LabJack Timing API
- **POST** `/api/labjack/timing/start` - Start timing measurement
- **POST** `/api/labjack/timing/stop` - Stop timing measurement
- **GET** `/api/labjack/timing/results` - Get timing results
- **POST** `/api/labjack/timing/validate` - Validate timing accuracy

### WebSocket Endpoints
- **WS** `/ws/labjack/stream` - Real-time LabJack data stream

## Detection & Analysis

### `/api/detection` (Simple Detection Router)
- **POST** `/api/detection/analyze` - Run detection on video
- **GET** `/api/detection/models` - List available models
- **POST** `/api/detection/configure` - Configure detection settings
- **GET** `/api/detection/{session_id}/events` - Get detection events

### Enhanced Detection Pipeline
- **POST** `/api/detection/pipeline/start` - Start detection pipeline
- **GET** `/api/detection/pipeline/status` - Pipeline status
- **GET** `/api/detection/pipeline/results` - Pipeline results

## Ground Truth Management

### `/api/ground-truth` (Ground Truth Router)
- **GET** `/api/ground-truth/videos/available` - Videos with ground truth
- **GET** `/api/ground-truth/{video_id}` - Get ground truth for video
- **POST** `/api/ground-truth/{video_id}` - Create ground truth annotations
- **PUT** `/api/ground-truth/{video_id}/{annotation_id}` - Update annotation
- **DELETE** `/api/ground-truth/{video_id}/{annotation_id}` - Delete annotation
- **POST** `/api/ground-truth/{video_id}/generate` - Auto-generate ground truth
- **POST** `/api/ground-truth/{video_id}/validate` - Validate annotations

## Dataset Management

### `/api/datasets` (Datasets Router)
- **GET** `/api/datasets` - List datasets
- **POST** `/api/datasets` - Create dataset
- **GET** `/api/datasets/{dataset_id}` - Get dataset details
- **PUT** `/api/datasets/{dataset_id}` - Update dataset
- **DELETE** `/api/datasets/{dataset_id}` - Delete dataset
- **POST** `/api/datasets/{dataset_id}/annotate` - Start annotation session
- **GET** `/api/datasets/{dataset_id}/annotations` - Get annotations
- **POST** `/api/datasets/{dataset_id}/export` - Export dataset

## Reports & Analytics

### `/api/reports` (Reports Router - PRD Module 4.2)
- **GET** `/api/reports` - List generated reports
- **POST** `/api/reports/generate` - Generate test report
  - Request body: `ReportGenerationRequest` schema
- **GET** `/api/reports/{report_id}` - Get report details
- **GET** `/api/reports/{report_id}/download` - Download report file
- **DELETE** `/api/reports/{report_id}` - Delete report
- **GET** `/api/reports/{report_id}/snapshots` - Get failure snapshots

### Report Formats
- **GET** `/api/reports/{report_id}/html` - HTML report
- **GET** `/api/reports/{report_id}/pdf` - PDF report  
- **GET** `/api/reports/{report_id}/json` - JSON report
- **GET** `/api/reports/{report_id}/csv` - CSV summary

## Dashboard & Statistics

### `/api/dashboard` (Dashboard Router)
- **GET** `/api/dashboard/stats` - Dashboard statistics
- **GET** `/api/dashboard/recent-activity` - Recent activity
- **GET** `/api/dashboard/project-summary` - Project summary
- **GET** `/api/dashboard/system-health` - System health metrics

## Enhanced Test Execution

### Enhanced Test Workflow
- **POST** `/api/enhanced-test/sessions` - Create enhanced test session
- **GET** `/api/enhanced-test/sessions/{session_id}` - Get session
- **POST** `/api/enhanced-test/sessions/{session_id}/execute` - Execute test
- **GET** `/api/enhanced-test/sessions/{session_id}/progress` - Execution progress

### Signal Validation
- **POST** `/api/signal/validate` - Validate signal processing
- **GET** `/api/signal/processors` - List signal processors
- **POST** `/api/signal/configure` - Configure signal processing

### Comprehensive Results
- **GET** `/api/results/comprehensive/{session_id}` - Comprehensive results
- **GET** `/api/results/analysis/{session_id}` - Results analysis
- **POST** `/api/results/compare` - Compare test results

## Video Processing

### Sequential Video Processing
- **POST** `/api/sequential-video/start` - Start sequential processing
- **GET** `/api/sequential-video/status/{job_id}` - Processing status
- **GET** `/api/sequential-video/results/{job_id}` - Processing results

### Enhanced Results
- **GET** `/api/results/enhanced/{session_id}` - Enhanced result format
- **GET** `/api/results/metrics/{session_id}` - Detailed metrics
- **POST** `/api/results/export` - Export results

## File Serving Endpoints

### Static Files
- **GET** `/uploads/{filename}` - Serve uploaded files
- **GET** `/screenshots/{filename}` - Serve screenshot files

### Dynamic File Serving
- **GET** `/api/videos/{video_id}/file` - Serve video file with fallbacks
- **GET** `/api/videos/{video_id}/thumbnail` - Video thumbnail
- **GET** `/api/videos/{video_id}/preview` - Video preview

## Validation & Quality

### Video Validation
- **POST** `/api/validation/video/{video_id}` - Validate video quality
- **GET** `/api/validation/criteria` - Get validation criteria
- **POST** `/api/validation/criteria` - Set validation criteria

### System Validation
- **GET** `/api/validation/system` - System validation status
- **POST** `/api/validation/calibrate` - Calibrate system
- **GET** `/api/validation/health` - System health check

## HTTP Status Codes Used

### Success Codes
- `200 OK` - Successful GET requests
- `201 Created` - Successful POST creation
- `204 No Content` - Successful DELETE

### Client Error Codes  
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Access denied
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Validation errors

### Server Error Codes
- `500 Internal Server Error` - Server errors
- `503 Service Unavailable` - Service temporarily unavailable

## Request/Response Formats

### Content Types
- **Request**: `application/json`, `multipart/form-data`
- **Response**: `application/json`, `video/mp4`, `image/png`

### Authentication
- **Method**: JWT Bearer tokens
- **Header**: `Authorization: Bearer <token>`

### Pagination
- **Parameters**: `skip` (offset), `limit` (page size)
- **Default Limit**: 100 items
- **Maximum Limit**: 1000 items

### Filtering
- Common query parameters: `status`, `project_id`, `video_id`
- Date ranges: `start_date`, `end_date`
- Search: `search` or `query` parameters

## WebSocket Endpoints

### Real-time Communication
- **WS** `/ws/labjack/stream` - LabJack data streaming
- **WS** `/ws/test-session/{session_id}` - Test execution updates
- **WS** `/ws/processing/{job_id}` - Processing status updates

### WebSocket Message Formats
```json
{
  "type": "data|status|error",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {...},
  "connection_id": "uuid"
}
```

## Rate Limiting
- Upload endpoints: 10 requests/minute
- Processing endpoints: 5 requests/minute
- General API: 100 requests/minute

## CORS Configuration
- **Allowed Origins**: localhost:3000, localhost:8001
- **Allowed Methods**: GET, POST, PUT, DELETE, OPTIONS
- **Allowed Headers**: All headers (*)
- **Credentials**: Enabled