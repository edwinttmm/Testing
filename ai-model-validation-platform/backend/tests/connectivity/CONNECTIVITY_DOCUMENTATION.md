# AI Model Validation Platform - Connectivity Documentation

## Overview

This document provides comprehensive information about all accessible URLs, endpoints, and connectivity requirements for the AI Model Validation Platform deployed on both localhost and the external Vultr server IP.

**Generated:** 2025-08-24  
**Last Updated:** 2025-08-24

## Server Configurations

### Localhost Environment
- **Frontend URL:** http://127.0.0.1:3000
- **Backend API URL:** http://127.0.0.1:8000
- **WebSocket URL:** ws://127.0.0.1:8000
- **Socket.IO URL:** http://127.0.0.1:8000

### External/Production Environment  
- **Frontend URL:** http://155.138.239.131:3000
- **Backend API URL:** http://155.138.239.131:8000
- **WebSocket URL:** ws://155.138.239.131:8000
- **Socket.IO URL:** http://155.138.239.131:8000

## Accessible URLs and Endpoints

### Frontend Application Routes

#### Public Routes
- **Homepage:** `/`
  - URL: http://127.0.0.1:3000/ | http://155.138.239.131:3000/
  - Description: Main landing page of the application
  - Authentication: Not required

- **Dashboard:** `/dashboard`
  - URL: http://127.0.0.1:3000/dashboard | http://155.138.239.131:3000/dashboard
  - Description: Main dashboard with system statistics
  - Authentication: Required

- **Projects:** `/projects`
  - URL: http://127.0.0.1:3000/projects | http://155.138.239.131:3000/projects
  - Description: Project management interface
  - Authentication: Required

- **Videos:** `/videos`
  - URL: http://127.0.0.1:3000/videos | http://155.138.239.131:3000/videos
  - Description: Video library and management
  - Authentication: Required

- **Annotations:** `/annotations`
  - URL: http://127.0.0.1:3000/annotations | http://155.138.239.131:3000/annotations
  - Description: Video annotation interface
  - Authentication: Required

- **Results:** `/results`
  - URL: http://127.0.0.1:3000/results | http://155.138.239.131:3000/results
  - Description: Test results and analysis
  - Authentication: Required

#### Static Assets
- **Favicon:** `/favicon.ico`
- **App Manifest:** `/manifest.json`  
- **Service Worker:** `/service-worker.js` (if enabled)
- **Static Files:** `/static/` (CSS, JS, images)

### Backend API Endpoints

#### Health Check Endpoints
- **Basic Health Check:** 
  - URL: `/health`
  - Methods: GET
  - Description: Basic service health status
  - Response: `{"status": "healthy", "timestamp": "..."}`

- **API Health Check:**
  - URL: `/api/health`
  - Methods: GET
  - Description: Detailed API health information
  - Response: Detailed health metrics

- **Database Health Check:**
  - URL: `/api/health/database`
  - Methods: GET
  - Description: Database connectivity status
  - Authentication: May be required

#### Project Management
- **List Projects:**
  - URL: `/api/projects`
  - Methods: GET
  - Description: Retrieve all projects
  - Authentication: Required

- **Create Project:**
  - URL: `/api/projects`
  - Methods: POST
  - Description: Create new project
  - Authentication: Required

- **Get Project Details:**
  - URL: `/api/projects/{project_id}`
  - Methods: GET
  - Description: Retrieve specific project
  - Authentication: Required

- **Update Project:**
  - URL: `/api/projects/{project_id}`
  - Methods: PUT, PATCH
  - Description: Update project information
  - Authentication: Required

- **Delete Project:**
  - URL: `/api/projects/{project_id}`
  - Methods: DELETE
  - Description: Delete project
  - Authentication: Required

#### Video Management
- **List Videos:**
  - URL: `/api/videos`
  - Methods: GET
  - Description: Retrieve all videos
  - Authentication: Required

- **Upload Video:**
  - URL: `/api/videos/upload`
  - Methods: POST
  - Description: Upload new video file
  - Authentication: Required
  - Content-Type: multipart/form-data

- **Get Video Details:**
  - URL: `/api/videos/{video_id}`
  - Methods: GET
  - Description: Retrieve specific video information
  - Authentication: Required

- **Stream Video:**
  - URL: `/api/videos/{video_id}/stream`
  - Methods: GET
  - Description: Stream video content
  - Authentication: Required

- **Delete Video:**
  - URL: `/api/videos/{video_id}`
  - Methods: DELETE
  - Description: Delete video
  - Authentication: Required

#### Dashboard and Statistics
- **Dashboard Statistics:**
  - URL: `/api/dashboard/stats`
  - Methods: GET
  - Description: System statistics and metrics
  - Authentication: Required

- **Enhanced Dashboard Stats:**
  - URL: `/api/dashboard/enhanced-stats`
  - Methods: GET
  - Description: Detailed dashboard statistics
  - Authentication: Required

#### Detection and ML
- **Detection Events:**
  - URL: `/api/detection-events`
  - Methods: GET, POST
  - Description: Manage detection events
  - Authentication: Required

- **Run Detection:**
  - URL: `/api/detection/run`
  - Methods: POST
  - Description: Execute detection on video
  - Authentication: Required

- **Detection Results:**
  - URL: `/api/detection/results/{detection_id}`
  - Methods: GET
  - Description: Retrieve detection results
  - Authentication: Required

#### Test Sessions
- **List Test Sessions:**
  - URL: `/api/test-sessions`
  - Methods: GET
  - Description: Retrieve test sessions
  - Authentication: Required

- **Create Test Session:**
  - URL: `/api/test-sessions`
  - Methods: POST
  - Description: Create new test session
  - Authentication: Required

- **Get Test Session:**
  - URL: `/api/test-sessions/{session_id}`
  - Methods: GET
  - Description: Retrieve specific test session
  - Authentication: Required

#### Annotation Management
- **List Annotations:**
  - URL: `/api/annotations`
  - Methods: GET
  - Description: Retrieve annotations
  - Authentication: Required

- **Create Annotation:**
  - URL: `/api/annotations`
  - Methods: POST
  - Description: Create new annotation
  - Authentication: Required

- **Update Annotation:**
  - URL: `/api/annotations/{annotation_id}`
  - Methods: PUT, PATCH
  - Description: Update annotation
  - Authentication: Required

- **Export Annotations:**
  - URL: `/api/annotations/export`
  - Methods: GET, POST
  - Description: Export annotations in various formats
  - Authentication: Required

#### File Management
- **File Upload:**
  - URL: `/api/upload`
  - Methods: POST
  - Description: Generic file upload
  - Authentication: Required

- **File Download:**
  - URL: `/api/files/{file_id}`
  - Methods: GET
  - Description: Download files
  - Authentication: May be required

#### Signal Processing and Validation
- **Signal Processing:**
  - URL: `/api/signal-processing`
  - Methods: POST
  - Description: Process signals for validation
  - Authentication: Required

- **Validation Results:**
  - URL: `/api/validation/results`
  - Methods: GET
  - Description: Retrieve validation results
  - Authentication: Required

### WebSocket Endpoints

#### Real-time Communication
- **Base WebSocket:**
  - URL: `ws://127.0.0.1:8000/ws` | `ws://155.138.239.131:8000/ws`
  - Description: General WebSocket connection for real-time updates
  - Authentication: May be required via query parameters or headers

- **Detection Updates:**
  - URL: `ws://127.0.0.1:8000/ws/detection` | `ws://155.138.239.131:8000/ws/detection`
  - Description: Real-time detection event updates
  - Authentication: Required

- **Progress Updates:**
  - URL: `ws://127.0.0.1:8000/ws/progress` | `ws://155.138.239.131:8000/ws/progress`
  - Description: Task progress notifications
  - Authentication: Required

### Socket.IO Endpoints

#### Namespaces
- **Default Namespace:** `/`
  - Description: General Socket.IO communication
  - Events: connect, disconnect, error

- **Detection Namespace:** `/detection`
  - Description: Detection-specific events
  - Events: detection_started, detection_progress, detection_complete

- **Progress Namespace:** `/progress`
  - Description: Task progress events
  - Events: task_started, task_progress, task_complete

## Network Requirements and Configurations

### Port Requirements
- **Frontend (React):** Port 3000
- **Backend (FastAPI):** Port 8000
- **Database (PostgreSQL):** Port 5432 (Internal only)
- **Redis:** Port 6379 (Internal only)
- **CVAT (Optional):** Port 8080

### Firewall Configuration

#### Required Open Ports (External Access)
```bash
# HTTP traffic for frontend
3000/tcp

# HTTP traffic for backend API  
8000/tcp

# CVAT (if used)
8080/tcp
```

#### Blocked Ports (Security)
```bash
# Database ports should NOT be accessible externally
5432/tcp  # PostgreSQL
6379/tcp  # Redis
```

### CORS Configuration

#### Allowed Origins
- `http://127.0.0.1:3000` (localhost frontend)
- `http://localhost:3000` (localhost alternative)
- `http://155.138.239.131:3000` (external frontend)

#### Allowed Methods
- GET, POST, PUT, PATCH, DELETE, OPTIONS

#### Allowed Headers
- Content-Type, Authorization, X-Requested-With, Accept, Origin

### SSL/TLS Configuration
Currently configured for HTTP. For production deployment, consider:
- SSL certificate installation
- HTTPS redirection
- Secure WebSocket (WSS) connections

## Authentication and Security

### Authentication Methods
- Session-based authentication
- JWT tokens (if implemented)
- API key authentication (for API access)

### Security Headers
The backend should include appropriate security headers:
- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Methods`
- `Access-Control-Allow-Headers`
- `X-Content-Type-Options`
- `X-Frame-Options`
- `X-XSS-Protection`

### Rate Limiting
Consider implementing rate limiting for:
- API endpoints: 100 requests/minute per IP
- File uploads: 10 uploads/hour per user
- WebSocket connections: 5 concurrent per user

## Testing and Monitoring

### Health Check URLs for Monitoring
- **Frontend Availability:** http://127.0.0.1:3000/ | http://155.138.239.131:3000/
- **Backend Health:** http://127.0.0.1:8000/health | http://155.138.239.131:8000/health
- **API Health:** http://127.0.0.1:8000/api/health | http://155.138.239.131:8000/api/health

### Performance Monitoring Endpoints
- **System Metrics:** `/api/metrics` (if available)
- **Database Status:** `/api/health/database`
- **Resource Usage:** `/api/health/resources`

### Log Files Locations
- **Frontend Logs:** Browser console, nginx access logs
- **Backend Logs:** Application logs, uvicorn logs
- **Database Logs:** PostgreSQL logs
- **System Logs:** /var/log/syslog, /var/log/nginx/

## Deployment Considerations

### Environment Variables
Critical environment variables that affect connectivity:
```bash
# Frontend
REACT_APP_API_URL=http://155.138.239.131:8000
REACT_APP_WS_URL=ws://155.138.239.131:8000

# Backend
AIVALIDATION_API_HOST=0.0.0.0
AIVALIDATION_API_PORT=8000
```

### Docker Configuration
Ensure proper port mapping in docker-compose.yml:
```yaml
frontend:
  ports:
    - "0.0.0.0:3000:3000"
    
backend:
  ports:
    - "0.0.0.0:8000:8000"
```

### Reverse Proxy Configuration (if used)
If using nginx or similar:
```nginx
# Frontend proxy
location / {
    proxy_pass http://127.0.0.1:3000;
}

# Backend API proxy
location /api/ {
    proxy_pass http://127.0.0.1:8000;
}

# WebSocket proxy
location /ws {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## Troubleshooting Common Issues

### Connection Refused Errors
1. Check if services are running: `docker ps`
2. Verify port bindings: `netstat -tlnp`
3. Check firewall rules: `ufw status`

### CORS Errors
1. Verify CORS configuration in backend
2. Check Origin headers in requests
3. Ensure preflight requests are handled

### WebSocket Connection Issues
1. Check WebSocket URL format
2. Verify proxy configuration for WebSocket upgrade
3. Check authentication requirements

### Performance Issues
1. Monitor network latency: `ping 155.138.239.131`
2. Check bandwidth utilization
3. Monitor server resources: `htop`, `free -h`

## Contact and Support

For connectivity issues or questions about this documentation:
- Check application logs first
- Verify network connectivity
- Review firewall and security group settings
- Test with provided connectivity test scripts

---

**Note:** This documentation should be updated whenever new endpoints are added or network configurations change.