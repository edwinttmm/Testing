# FastAPI Router & Middleware Architecture

## Overview

This document defines the comprehensive FastAPI router organization and middleware architecture for the AI Model Validation Platform, ensuring scalable, maintainable, and secure API design.

## 1. APPLICATION STRUCTURE

### 1.1 Project Organization

```
backend/
├── main.py                     # Application entry point
├── config/
│   ├── __init__.py
│   ├── settings.py             # Application settings
│   ├── database.py             # Database configuration
│   └── middleware.py           # Middleware configuration
├── routers/
│   ├── __init__.py
│   ├── v1/                     # API version 1
│   │   ├── __init__.py
│   │   ├── projects.py         # Project management endpoints
│   │   ├── videos.py           # Video management endpoints
│   │   ├── annotations.py      # Annotation endpoints
│   │   ├── ground_truth.py     # Ground truth endpoints
│   │   ├── test_sessions.py    # Test session endpoints
│   │   ├── detection_events.py # Detection event endpoints
│   │   ├── validation.py       # Validation endpoints
│   │   ├── ml_inference.py     # ML inference endpoints
│   │   ├── dashboard.py        # Dashboard endpoints
│   │   └── health.py           # Health check endpoints
│   └── v2/                     # Future API version
├── middleware/
│   ├── __init__.py
│   ├── security.py             # Security middleware
│   ├── cors.py                 # CORS configuration
│   ├── rate_limiting.py        # Rate limiting middleware
│   ├── error_handling.py       # Error handling middleware
│   ├── request_logging.py      # Request logging middleware
│   ├── auth.py                 # Authentication middleware
│   └── validation.py           # Input validation middleware
├── services/
│   ├── __init__.py
│   ├── auth_service.py         # Authentication service
│   ├── project_service.py      # Project business logic
│   ├── video_service.py        # Video processing service
│   ├── annotation_service.py   # Annotation management service
│   ├── ground_truth_service.py # Ground truth generation service
│   ├── ml_service.py           # ML inference service
│   ├── validation_service.py   # Validation logic service
│   └── notification_service.py # Notification service
├── models/
│   ├── __init__.py
│   ├── database.py             # SQLAlchemy models
│   ├── schemas.py              # Pydantic schemas
│   └── enums.py                # Enum definitions
└── utils/
    ├── __init__.py
    ├── security.py             # Security utilities
    ├── file_handling.py        # File handling utilities
    ├── validation.py           # Validation utilities
    └── exceptions.py           # Custom exceptions
```

### 1.2 Main Application Configuration

```python
# main.py - Application Entry Point

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.sessions import SessionMiddleware

from config.settings import settings
from config.middleware import configure_middleware
from routers.v1 import (
    projects, videos, annotations, ground_truth, 
    test_sessions, detection_events, validation, 
    ml_inference, dashboard, health
)
from middleware.error_handling import ErrorHandlingMiddleware
from middleware.security import SecurityMiddleware
from middleware.rate_limiting import RateLimitingMiddleware
from middleware.request_logging import RequestLoggingMiddleware
from middleware.auth import AuthenticationMiddleware

# Application factory pattern
def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="AI Model Validation Platform API",
        description="Comprehensive API for AI model validation, annotation management, and ground truth validation",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json"
    )
    
    # Configure middleware stack
    configure_middleware(app)
    
    # Include API routers
    configure_routes(app)
    
    # Configure event handlers
    configure_events(app)
    
    return app

def configure_middleware(app: FastAPI):
    """Configure application middleware in correct order"""
    
    # Outermost: Error handling (catches all exceptions)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Security middleware (input validation, sanitization)
    app.add_middleware(SecurityMiddleware)
    
    # Request logging (audit trail)
    app.add_middleware(RequestLoggingMiddleware)
    
    # Rate limiting (DDoS protection)
    app.add_middleware(
        RateLimitingMiddleware,
        requests_per_minute=1000,
        burst_size=100,
        per_ip_limit=100
    )
    
    # Authentication middleware
    app.add_middleware(AuthenticationMiddleware)
    
    # Trusted host protection
    app.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=settings.allowed_hosts
    )
    
    # Session middleware (before CORS)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        max_age=3600,  # 1 hour
        same_site="lax",
        https_only=settings.environment == "production"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page-Count", "X-Request-ID"]
    )
    
    # Response compression (innermost)
    app.add_middleware(
        GZipMiddleware, 
        minimum_size=1000,
        compresslevel=6
    )

def configure_routes(app: FastAPI):
    """Configure API routes"""
    
    # Health check (no auth required)
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    
    # Core API routes
    app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
    app.include_router(videos.router, prefix="/api/v1", tags=["videos"])
    app.include_router(annotations.router, prefix="/api/v1", tags=["annotations"])
    app.include_router(ground_truth.router, prefix="/api/v1", tags=["ground-truth"])
    app.include_router(test_sessions.router, prefix="/api/v1", tags=["test-sessions"])
    app.include_router(detection_events.router, prefix="/api/v1", tags=["detection-events"])
    app.include_router(validation.router, prefix="/api/v1", tags=["validation"])
    app.include_router(ml_inference.router, prefix="/api/v1", tags=["ml-inference"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])

def configure_events(app: FastAPI):
    """Configure application event handlers"""
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize application on startup"""
        from services.notification_service import NotificationService
        from database import safe_create_indexes_and_tables
        
        # Initialize database
        await safe_create_indexes_and_tables()
        
        # Initialize notification service
        await NotificationService.initialize()
        
        # Log startup
        logger.info("AI Model Validation Platform API started")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on application shutdown"""
        from services.notification_service import NotificationService
        
        # Cleanup notification service
        await NotificationService.shutdown()
        
        logger.info("AI Model Validation Platform API shutdown")

# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        access_log=True
    )
```

## 2. ROUTER ARCHITECTURE

### 2.1 Project Management Router

```python
# routers/v1/projects.py

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from database import get_db
from models.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, 
    DashboardStats, PassFailCriteriaSchema
)
from services.project_service import ProjectService
from services.auth_service import get_current_user, require_permission
from middleware.validation import validate_uuid
from utils.pagination import PaginationParams, paginate_response

router = APIRouter()

@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=201,
    summary="Create new project",
    description="Create a new AI model validation project with specified parameters"
)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new validation project"""
    
    # Check permissions
    await require_permission(current_user, "projects", "create")
    
    # Create project via service
    project_service = ProjectService(db)
    project = await project_service.create_project(project_data, current_user["id"])
    
    return project

@router.get(
    "/projects",
    response_model=List[ProjectResponse],
    summary="List projects",
    description="Retrieve paginated list of projects with optional filtering"
)
async def list_projects(
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by project status"),
    camera_view: Optional[str] = Query(None, description="Filter by camera view type"),
    search: Optional[str] = Query(None, description="Search in project name and description")
):
    """List projects with filtering and pagination"""
    
    # Check permissions
    await require_permission(current_user, "projects", "read")
    
    # Get projects via service
    project_service = ProjectService(db)
    projects, total = await project_service.list_projects(
        user_id=current_user["id"],
        status=status,
        camera_view=camera_view,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit
    )
    
    return paginate_response(projects, total, pagination)

@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
    description="Retrieve detailed information about a specific project"
)
async def get_project(
    project_id: UUID = Path(..., description="Project ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get project by ID"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "projects", "read")
    
    # Get project via service
    project_service = ProjectService(db)
    project = await project_service.get_project(project_id, current_user["id"])
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project

@router.put(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    summary="Update project",
    description="Update project information and configuration"
)
async def update_project(
    project_id: UUID = Path(..., description="Project ID"),
    project_data: ProjectUpdate = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update project"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "projects", "update")
    
    # Update project via service
    project_service = ProjectService(db)
    project = await project_service.update_project(
        project_id, project_data, current_user["id"]
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return project

@router.delete(
    "/projects/{project_id}",
    status_code=204,
    summary="Delete project",
    description="Delete project and all associated data"
)
async def delete_project(
    project_id: UUID = Path(..., description="Project ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete project"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "projects", "delete")
    
    # Delete project via service
    project_service = ProjectService(db)
    success = await project_service.delete_project(project_id, current_user["id"])
    
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")

@router.post(
    "/projects/{project_id}/validation-criteria",
    response_model=PassFailCriteriaResponse,
    summary="Set validation criteria",
    description="Configure pass/fail criteria for project validation"
)
async def set_validation_criteria(
    project_id: UUID = Path(..., description="Project ID"),
    criteria: PassFailCriteriaSchema = Body(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Set project validation criteria"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "projects", "update")
    
    # Set criteria via service
    project_service = ProjectService(db)
    result = await project_service.set_validation_criteria(
        project_id, criteria, current_user["id"]
    )
    
    return result

@router.get(
    "/projects/{project_id}/statistics",
    response_model=DashboardStats,
    summary="Get project statistics",
    description="Retrieve comprehensive statistics for a project"
)
async def get_project_statistics(
    project_id: UUID = Path(..., description="Project ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get project statistics"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "projects", "read")
    
    # Get statistics via service
    project_service = ProjectService(db)
    stats = await project_service.get_project_statistics(
        project_id, current_user["id"]
    )
    
    return stats
```

### 2.2 Video Management Router

```python
# routers/v1/videos.py

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import mimetypes
import os

from database import get_db
from models.schemas import VideoResponse, VideoUploadResponse
from services.video_service import VideoService
from services.auth_service import get_current_user, require_permission
from middleware.validation import validate_uuid, validate_file_upload
from utils.pagination import PaginationParams, paginate_response

router = APIRouter()

@router.post(
    "/projects/{project_id}/videos/upload",
    response_model=VideoUploadResponse,
    status_code=201,
    summary="Upload video file",
    description="Upload video file to project for processing and validation"
)
async def upload_video(
    project_id: UUID,
    file: UploadFile = File(..., description="Video file to upload"),
    original_filename: Optional[str] = Form(None, description="Original filename"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Upload video to project"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "videos", "create")
    
    # Validate file upload
    await validate_file_upload(file, allowed_types=["video/mp4", "video/avi", "video/mov"])
    
    # Upload video via service
    video_service = VideoService(db)
    result = await video_service.upload_video(
        project_id=project_id,
        file=file,
        original_filename=original_filename or file.filename,
        user_id=current_user["id"]
    )
    
    return result

@router.get(
    "/projects/{project_id}/videos",
    response_model=List[VideoResponse],
    summary="List project videos",
    description="Get paginated list of videos for a specific project"
)
async def list_project_videos(
    project_id: UUID,
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    status: Optional[str] = Query(None, description="Filter by video status"),
    processing_status: Optional[str] = Query(None, description="Filter by processing status")
):
    """List videos in project"""
    
    # Validate UUID
    project_id = validate_uuid(project_id)
    
    # Check permissions
    await require_permission(current_user, "videos", "read")
    
    # Get videos via service
    video_service = VideoService(db)
    videos, total = await video_service.list_project_videos(
        project_id=project_id,
        status=status,
        processing_status=processing_status,
        offset=pagination.offset,
        limit=pagination.limit,
        user_id=current_user["id"]
    )
    
    return paginate_response(videos, total, pagination)

@router.get(
    "/videos/{video_id}",
    response_model=VideoResponse,
    summary="Get video details",
    description="Retrieve detailed information about a specific video"
)
async def get_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get video by ID"""
    
    # Validate UUID
    video_id = validate_uuid(video_id)
    
    # Check permissions
    await require_permission(current_user, "videos", "read")
    
    # Get video via service
    video_service = VideoService(db)
    video = await video_service.get_video(video_id, current_user["id"])
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return video

@router.get(
    "/videos/{video_id}/stream",
    summary="Stream video file",
    description="Stream video file content with range support"
)
async def stream_video(
    video_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Stream video file"""
    
    # Validate UUID
    video_id = validate_uuid(video_id)
    
    # Check permissions
    await require_permission(current_user, "videos", "read")
    
    # Get video file path via service
    video_service = VideoService(db)
    video = await video_service.get_video(video_id, current_user["id"])
    
    if not video or not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Handle range requests for video streaming
    return await video_service.stream_video_file(video.file_path, request)

@router.delete(
    "/videos/{video_id}",
    status_code=204,
    summary="Delete video",
    description="Delete video file and all associated data"
)
async def delete_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete video"""
    
    # Validate UUID
    video_id = validate_uuid(video_id)
    
    # Check permissions
    await require_permission(current_user, "videos", "delete")
    
    # Delete video via service
    video_service = VideoService(db)
    success = await video_service.delete_video(video_id, current_user["id"])
    
    if not success:
        raise HTTPException(status_code=404, detail="Video not found")

@router.post(
    "/videos/{video_id}/reprocess",
    response_model=VideoResponse,
    summary="Reprocess video",
    description="Trigger video reprocessing for ground truth generation"
)
async def reprocess_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Reprocess video for ground truth generation"""
    
    # Validate UUID
    video_id = validate_uuid(video_id)
    
    # Check permissions
    await require_permission(current_user, "videos", "update")
    
    # Reprocess video via service
    video_service = VideoService(db)
    result = await video_service.reprocess_video(video_id, current_user["id"])
    
    if not result:
        raise HTTPException(status_code=404, detail="Video not found")
    
    return result
```

## 3. MIDDLEWARE ARCHITECTURE

### 3.1 Security Middleware

```python
# middleware/security.py

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import re
import html
import json
from typing import Optional
import time

from utils.security import SecurityValidator
from utils.exceptions import SecurityViolationError

class SecurityMiddleware(BaseHTTPMiddleware):
    """Comprehensive security middleware for input validation and sanitization"""
    
    def __init__(self, app, max_request_size: int = 50 * 1024 * 1024):  # 50MB
        super().__init__(app)
        self.max_request_size = max_request_size
        self.security_validator = SecurityValidator()
        
        # Dangerous patterns to block
        self.blocked_patterns = [
            r"<script[^>]*>.*?</script>",  # Script tags
            r"javascript:",                # JavaScript protocol
            r"vbscript:",                 # VBScript protocol
            r"onload\s*=",                # Event handlers
            r"onerror\s*=",
            r"onclick\s*=",
            r"eval\s*\(",                 # Eval function
            r"expression\s*\(",           # CSS expression
            r"import\s+os",               # Python imports
            r"import\s+subprocess",
            r"__import__",                # Dynamic imports
            r"\bexec\b",                  # Exec function
        ]
        
        # Compile regex patterns for performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.blocked_patterns]
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security checks"""
        
        start_time = time.time()
        
        try:
            # Check request size
            await self._check_request_size(request)
            
            # Validate headers
            await self._validate_headers(request)
            
            # Validate URL and query parameters
            await self._validate_url_and_params(request)
            
            # Validate request body
            if request.method in ["POST", "PUT", "PATCH"]:
                await self._validate_request_body(request)
            
            # Check for suspicious patterns
            await self._check_malicious_patterns(request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers to response
            response = await self._add_security_headers(response)
            
            # Log security metrics
            processing_time = time.time() - start_time
            await self._log_security_metrics(request, response, processing_time)
            
            return response
            
        except SecurityViolationError as e:
            # Log security violation
            await self._log_security_violation(request, str(e))
            raise HTTPException(status_code=400, detail=f"Security violation: {str(e)}")
        
        except Exception as e:
            # Log unexpected error
            await self._log_security_error(request, str(e))
            raise HTTPException(status_code=500, detail="Security validation failed")
    
    async def _check_request_size(self, request: Request):
        """Check if request size exceeds limit"""
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_request_size:
            raise SecurityViolationError(f"Request size {content_length} exceeds limit {self.max_request_size}")
    
    async def _validate_headers(self, request: Request):
        """Validate request headers for security"""
        
        # Check for suspicious headers
        suspicious_headers = ["x-forwarded-host", "x-real-ip", "x-forwarded-for"]
        for header in suspicious_headers:
            if header in request.headers:
                value = request.headers[header]
                if not self._is_valid_ip_or_host(value):
                    raise SecurityViolationError(f"Invalid {header} header: {value}")
        
        # Validate user agent
        user_agent = request.headers.get("user-agent", "")
        if self._contains_malicious_patterns(user_agent):
            raise SecurityViolationError("Malicious user agent detected")
    
    async def _validate_url_and_params(self, request: Request):
        """Validate URL path and query parameters"""
        
        # Check URL path
        path = str(request.url.path)
        if self._contains_malicious_patterns(path):
            raise SecurityViolationError("Malicious URL path detected")
        
        # Check query parameters
        for key, value in request.query_params.items():
            if self._contains_malicious_patterns(f"{key}={value}"):
                raise SecurityViolationError(f"Malicious query parameter: {key}")
    
    async def _validate_request_body(self, request: Request):
        """Validate request body content"""
        
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            try:
                # Read body without consuming the stream
                body = await request.body()
                if body:
                    # Parse JSON to validate structure
                    json_data = json.loads(body.decode())
                    
                    # Check JSON for malicious patterns
                    json_str = json.dumps(json_data)
                    if self._contains_malicious_patterns(json_str):
                        raise SecurityViolationError("Malicious content in JSON body")
                    
                    # Validate JSON depth (prevent deeply nested attacks)
                    if self._get_json_depth(json_data) > 10:
                        raise SecurityViolationError("JSON nesting too deep")
                        
            except json.JSONDecodeError:
                raise SecurityViolationError("Invalid JSON format")
        
        elif "multipart/form-data" in content_type:
            # File upload validation will be handled by specific endpoints
            pass
        
        elif "application/x-www-form-urlencoded" in content_type:
            body = await request.body()
            if body and self._contains_malicious_patterns(body.decode()):
                raise SecurityViolationError("Malicious content in form data")
    
    def _contains_malicious_patterns(self, text: str) -> bool:
        """Check if text contains malicious patterns"""
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True
        return False
    
    def _is_valid_ip_or_host(self, value: str) -> bool:
        """Validate IP address or hostname"""
        # Basic validation for IP addresses and hostnames
        ip_pattern = re.compile(r'^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$')
        host_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$')
        
        return bool(ip_pattern.match(value) or host_pattern.match(value))
    
    def _get_json_depth(self, obj, depth=0):
        """Get maximum depth of JSON object"""
        if isinstance(obj, dict):
            return max([self._get_json_depth(value, depth + 1) for value in obj.values()] + [depth])
        elif isinstance(obj, list):
            return max([self._get_json_depth(item, depth + 1) for item in obj] + [depth])
        else:
            return depth
    
    async def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response
    
    async def _log_security_metrics(self, request: Request, response: Response, processing_time: float):
        """Log security processing metrics"""
        from services.audit_service import AuditService
        
        audit_service = AuditService()
        await audit_service.log_security_event(
            event_type="security_validation",
            request_path=str(request.url.path),
            processing_time=processing_time,
            status_code=response.status_code
        )
    
    async def _log_security_violation(self, request: Request, violation: str):
        """Log security violation"""
        from services.audit_service import AuditService
        
        audit_service = AuditService()
        await audit_service.log_security_event(
            event_type="security_violation",
            request_path=str(request.url.path),
            violation=violation,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", "")
        )
    
    async def _log_security_error(self, request: Request, error: str):
        """Log security processing error"""
        from services.audit_service import AuditService
        
        audit_service = AuditService()
        await audit_service.log_security_event(
            event_type="security_error",
            request_path=str(request.url.path),
            error=error,
            ip_address=request.client.host
        )
```

### 3.2 Rate Limiting Middleware

```python
# middleware/rate_limiting.py

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
import asyncio
from collections import defaultdict, deque
from typing import Dict, Optional
import redis
import json

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Advanced rate limiting middleware with multiple strategies"""
    
    def __init__(
        self, 
        app,
        requests_per_minute: int = 1000,
        burst_size: int = 100,
        per_ip_limit: int = 100,
        use_redis: bool = True
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.per_ip_limit = per_ip_limit
        self.use_redis = use_redis
        
        # In-memory storage for development
        self.ip_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.per_ip_limit))
        self.global_requests = deque(maxlen=requests_per_minute)
        
        # Redis client for production
        if use_redis:
            try:
                self.redis_client = redis.Redis(
                    host='localhost', 
                    port=6379, 
                    db=0, 
                    decode_responses=True
                )
            except:
                self.redis_client = None
                self.use_redis = False
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting checks"""
        
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        try:
            # Check global rate limit
            if not await self._check_global_limit(current_time):
                raise HTTPException(
                    status_code=429,
                    detail="Global rate limit exceeded",
                    headers={"Retry-After": "60"}
                )
            
            # Check per-IP rate limit
            if not await self._check_ip_limit(client_ip, current_time):
                raise HTTPException(
                    status_code=429,
                    detail="IP rate limit exceeded",
                    headers={"Retry-After": "60"}
                )
            
            # Check burst limit
            if not await self._check_burst_limit(client_ip, current_time):
                raise HTTPException(
                    status_code=429,
                    detail="Burst limit exceeded",
                    headers={"Retry-After": "10"}
                )
            
            # Record request
            await self._record_request(client_ip, current_time)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response = await self._add_rate_limit_headers(response, client_ip)
            
            return response
            
        except HTTPException:
            # Log rate limit violation
            await self._log_rate_limit_violation(client_ip, request)
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for forwarded IP headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host
    
    async def _check_global_limit(self, current_time: float) -> bool:
        """Check global request rate limit"""
        
        if self.use_redis and self.redis_client:
            # Redis-based global limit
            key = "rate_limit:global"
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, current_time - 60)
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            # Count requests in last minute
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, 60)
            
            results = pipe.execute()
            request_count = results[2]
            
            return request_count <= self.requests_per_minute
        else:
            # In-memory global limit
            cutoff_time = current_time - 60
            
            # Remove old requests
            while self.global_requests and self.global_requests[0] < cutoff_time:
                self.global_requests.popleft()
            
            return len(self.global_requests) < self.requests_per_minute
    
    async def _check_ip_limit(self, client_ip: str, current_time: float) -> bool:
        """Check per-IP request rate limit"""
        
        if self.use_redis and self.redis_client:
            # Redis-based IP limit
            key = f"rate_limit:ip:{client_ip}"
            pipe = self.redis_client.pipeline()
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, current_time - 60)
            # Count requests in last minute
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, 60)
            
            results = pipe.execute()
            request_count = results[1]
            
            return request_count < self.per_ip_limit
        else:
            # In-memory IP limit
            ip_requests = self.ip_requests[client_ip]
            cutoff_time = current_time - 60
            
            # Remove old requests
            while ip_requests and ip_requests[0] < cutoff_time:
                ip_requests.popleft()
            
            return len(ip_requests) < self.per_ip_limit
    
    async def _check_burst_limit(self, client_ip: str, current_time: float) -> bool:
        """Check burst request limit (requests in last 10 seconds)"""
        
        if self.use_redis and self.redis_client:
            # Redis-based burst limit
            key = f"rate_limit:burst:{client_ip}"
            pipe = self.redis_client.pipeline()
            
            # Remove old entries (last 10 seconds)
            pipe.zremrangebyscore(key, 0, current_time - 10)
            # Count requests in last 10 seconds
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, 10)
            
            results = pipe.execute()
            request_count = results[1]
            
            return request_count < self.burst_size
        else:
            # In-memory burst limit
            ip_requests = self.ip_requests[client_ip]
            burst_cutoff_time = current_time - 10
            
            burst_count = sum(1 for req_time in ip_requests if req_time >= burst_cutoff_time)
            return burst_count < self.burst_size
    
    async def _record_request(self, client_ip: str, current_time: float):
        """Record request for rate limiting"""
        
        if self.use_redis and self.redis_client:
            # Record in Redis
            global_key = "rate_limit:global"
            ip_key = f"rate_limit:ip:{client_ip}"
            burst_key = f"rate_limit:burst:{client_ip}"
            
            pipe = self.redis_client.pipeline()
            pipe.zadd(global_key, {str(current_time): current_time})
            pipe.zadd(ip_key, {str(current_time): current_time})
            pipe.zadd(burst_key, {str(current_time): current_time})
            pipe.execute()
        else:
            # Record in memory
            self.global_requests.append(current_time)
            self.ip_requests[client_ip].append(current_time)
    
    async def _add_rate_limit_headers(self, response, client_ip: str):
        """Add rate limiting headers to response"""
        
        current_time = time.time()
        
        # Calculate remaining requests
        if self.use_redis and self.redis_client:
            key = f"rate_limit:ip:{client_ip}"
            request_count = self.redis_client.zcard(key)
        else:
            ip_requests = self.ip_requests[client_ip]
            cutoff_time = current_time - 60
            request_count = sum(1 for req_time in ip_requests if req_time >= cutoff_time)
        
        remaining = max(0, self.per_ip_limit - request_count)
        reset_time = int(current_time) + 60
        
        response.headers["X-RateLimit-Limit"] = str(self.per_ip_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    async def _log_rate_limit_violation(self, client_ip: str, request: Request):
        """Log rate limit violation"""
        from services.audit_service import AuditService
        
        audit_service = AuditService()
        await audit_service.log_security_event(
            event_type="rate_limit_violation",
            ip_address=client_ip,
            request_path=str(request.url.path),
            user_agent=request.headers.get("user-agent", "")
        )
```

This comprehensive FastAPI router and middleware architecture provides:

1. **Scalable Router Organization**: Clean separation of concerns with version-specific routing
2. **Comprehensive Security**: Multi-layer security middleware with input validation and sanitization
3. **Advanced Rate Limiting**: Multiple rate limiting strategies with Redis support
4. **Authentication & Authorization**: Role-based access control with JWT tokens
5. **Request/Response Processing**: Proper validation, pagination, and error handling
6. **Performance Optimization**: Middleware ordering and caching strategies
7. **Audit Logging**: Comprehensive logging for security and compliance
8. **Extensibility**: Easy to extend with new endpoints and middleware