# AI Model Validation Platform - System Architecture

## Executive Summary

This document presents the comprehensive system architecture for the AI Model Validation Platform, following SPARC methodology principles. The architecture integrates annotation management, ground truth validation, and ML inference systems into a scalable, maintainable platform.

## 1. HIGH-LEVEL SYSTEM ARCHITECTURE

### 1.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI MODEL VALIDATION PLATFORM                │
├─────────────────────────────────────────────────────────────────┤
│  Client Layer                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Web App   │  │ Mobile App  │  │ API Clients │             │
│  │  (React)    │  │   (Future)  │  │  (External) │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│  API Gateway & Security Layer                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ FastAPI Application Server                                  │ │
│  │ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │ │
│  │ │    CORS     │ │   Security  │ │ Rate Limit  │           │ │
│  │ │ Middleware  │ │ Middleware  │ │ Middleware  │           │ │
│  │ └─────────────┘ └─────────────┘ └─────────────┘           │ │
│  └─────────────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  Application Services Layer                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ Project     │ │ Video       │ │ Annotation  │              │
│  │ Service     │ │ Service     │ │ Service     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ Ground      │ │ ML          │ │ Validation  │              │
│  │ Truth Svc   │ │ Inference   │ │ Service     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer                                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │ PostgreSQL  │ │    Redis    │ │ File System │              │
│  │  (Primary)  │ │   (Cache)   │ │ (Videos)    │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Architecture Layers

**Client Layer**
- React-based web application
- Responsive design for multiple screen sizes
- Future mobile application support
- External API client integration

**API Gateway & Security**
- FastAPI application server
- CORS middleware for cross-origin requests
- Security middleware for input validation
- Rate limiting and authentication

**Application Services**
- Project management services
- Video processing and validation
- Annotation and ground truth management
- ML inference and detection services

**Data Layer**
- PostgreSQL for structured data
- Redis for caching and sessions
- File system for video storage
- Comprehensive indexing strategy

## 2. DATABASE ARCHITECTURE

### 2.1 Enhanced Entity Relationship Design

```sql
-- Core Entities with Relationships

┌─────────────────┐     1:N     ┌─────────────────┐
│    Projects     │────────────→│     Videos      │
│                 │             │                 │
│ - id (PK)       │             │ - id (PK)       │
│ - name          │             │ - project_id    │
│ - camera_model  │             │ - filename      │
│ - camera_view   │             │ - file_path     │
│ - signal_type   │             │ - duration      │
│ - status        │             │ - fps           │
└─────────────────┘             └─────────────────┘
                                         │
                                         │ 1:N
                                         ▼
┌─────────────────┐     1:N     ┌─────────────────┐
│ TestSessions    │────────────→│ DetectionEvents │
│                 │             │                 │
│ - id (PK)       │             │ - id (PK)       │
│ - project_id    │             │ - test_session_id│
│ - video_id      │             │ - timestamp     │
│ - tolerance_ms  │             │ - confidence    │
│ - status        │             │ - class_label   │
│ - started_at    │             │ - bounding_box  │
└─────────────────┘             └─────────────────┘

┌─────────────────┐     1:N     ┌─────────────────┐
│     Videos      │────────────→│   Annotations   │
│                 │             │                 │
│ - id (PK)       │             │ - id (PK)       │
│ - filename      │             │ - video_id      │
│ - project_id    │             │ - detection_id  │
│ - status        │             │ - frame_number  │
│ - ground_truth  │             │ - timestamp     │
│   _generated    │             │ - vru_type      │
└─────────────────┘             │ - bounding_box  │
                                │ - validated     │
                                └─────────────────┘

┌─────────────────┐     1:N     ┌─────────────────┐
│     Videos      │────────────→│GroundTruthObj   │
│                 │             │                 │
│ - id (PK)       │             │ - id (PK)       │
│ - project_id    │             │ - video_id      │
│ - status        │             │ - timestamp     │
│ - processing    │             │ - class_label   │
│   _status       │             │ - confidence    │
└─────────────────┘             │ - bounding_box  │
                                │ - validated     │
                                └─────────────────┘
```

### 2.2 Performance Index Strategy

```sql
-- Critical Performance Indexes

-- Video-centric queries
CREATE INDEX idx_video_project_status ON videos (project_id, status);
CREATE INDEX idx_video_project_created ON videos (project_id, created_at);
CREATE INDEX idx_video_ground_truth_status ON videos (ground_truth_generated, processing_status);

-- Annotation queries  
CREATE INDEX idx_annotation_video_frame ON annotations (video_id, frame_number);
CREATE INDEX idx_annotation_video_timestamp ON annotations (video_id, timestamp);
CREATE INDEX idx_annotation_vru_validated ON annotations (vru_type, validated);

-- Detection event queries
CREATE INDEX idx_detection_session_timestamp ON detection_events (test_session_id, timestamp);
CREATE INDEX idx_detection_session_validation ON detection_events (test_session_id, validation_result);
CREATE INDEX idx_detection_confidence_validation ON detection_events (confidence, validation_result, timestamp);

-- Ground truth queries
CREATE INDEX idx_gt_video_timestamp ON ground_truth_objects (video_id, timestamp);
CREATE INDEX idx_gt_video_class ON ground_truth_objects (video_id, class_label);
CREATE INDEX idx_gt_validated_class ON ground_truth_objects (validated, class_label);
```

### 2.3 Data Integrity Constraints

```sql
-- Cascading Deletes for Data Consistency
ALTER TABLE videos 
ADD CONSTRAINT fk_videos_projects 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

ALTER TABLE annotations 
ADD CONSTRAINT fk_annotations_videos 
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE;

ALTER TABLE ground_truth_objects 
ADD CONSTRAINT fk_ground_truth_videos 
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE;

-- Check Constraints for Data Quality
ALTER TABLE detection_events 
ADD CONSTRAINT chk_confidence_range 
CHECK (confidence >= 0.0 AND confidence <= 1.0);

ALTER TABLE annotations 
ADD CONSTRAINT chk_frame_number_positive 
CHECK (frame_number >= 0);

ALTER TABLE videos 
ADD CONSTRAINT chk_duration_positive 
CHECK (duration IS NULL OR duration > 0);
```

## 3. API ARCHITECTURE

### 3.1 Router Organization

```python
# FastAPI Application Structure
app/
├── main.py                 # Application entry point
├── routers/
│   ├── __init__.py
│   ├── projects.py         # Project CRUD operations
│   ├── videos.py           # Video upload and management
│   ├── annotations.py      # Annotation management
│   ├── ground_truth.py     # Ground truth operations
│   ├── test_sessions.py    # Test session management
│   ├── detection_events.py # Detection event handling
│   ├── validation.py       # Validation and metrics
│   └── dashboard.py        # Dashboard endpoints
├── middleware/
│   ├── __init__.py
│   ├── security.py         # Security middleware
│   ├── cors.py            # CORS configuration
│   ├── rate_limiting.py   # Rate limiting
│   └── error_handling.py  # Error handling
├── services/
│   ├── __init__.py
│   ├── project_service.py
│   ├── video_service.py
│   ├── annotation_service.py
│   ├── ground_truth_service.py
│   ├── ml_inference_service.py
│   └── validation_service.py
└── models/
    ├── __init__.py
    ├── database.py         # SQLAlchemy models
    └── schemas.py          # Pydantic schemas
```

### 3.2 API Endpoint Design

```python
# Core API Endpoints

# Project Management
POST   /api/v1/projects                    # Create project
GET    /api/v1/projects                    # List projects
GET    /api/v1/projects/{id}               # Get project
PUT    /api/v1/projects/{id}               # Update project
DELETE /api/v1/projects/{id}               # Delete project

# Video Management
POST   /api/v1/projects/{id}/videos/upload # Upload video
GET    /api/v1/projects/{id}/videos        # List project videos
GET    /api/v1/videos/{id}                 # Get video details
DELETE /api/v1/videos/{id}                 # Delete video
GET    /api/v1/videos/{id}/stream          # Stream video

# Annotation System
POST   /api/v1/videos/{id}/annotations     # Create annotation
GET    /api/v1/videos/{id}/annotations     # List annotations
PUT    /api/v1/annotations/{id}            # Update annotation
DELETE /api/v1/annotations/{id}            # Delete annotation
POST   /api/v1/annotations/{id}/validate   # Validate annotation

# Ground Truth System
POST   /api/v1/videos/{id}/ground-truth/generate  # Generate ground truth
GET    /api/v1/videos/{id}/ground-truth           # Get ground truth
PUT    /api/v1/ground-truth/{id}/validate         # Validate ground truth

# Test Sessions & Detection
POST   /api/v1/test-sessions               # Create test session
GET    /api/v1/test-sessions               # List test sessions
POST   /api/v1/test-sessions/{id}/start    # Start test session
POST   /api/v1/test-sessions/{id}/stop     # Stop test session
GET    /api/v1/test-sessions/{id}/results  # Get test results

# ML Inference
POST   /api/v1/ml/detect                   # Run ML detection
GET    /api/v1/ml/models                   # List available models
POST   /api/v1/ml/models/{name}/load       # Load specific model

# Validation & Metrics
GET    /api/v1/validation/metrics/{session_id}    # Get validation metrics
POST   /api/v1/validation/compare                 # Compare detections
GET    /api/v1/validation/statistics              # Get validation statistics

# Dashboard
GET    /api/v1/dashboard/stats             # Dashboard statistics
GET    /api/v1/dashboard/recent-activity   # Recent activity
```

### 3.3 Middleware Stack

```python
# Application Middleware Configuration

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.security import SecurityMiddleware
from middleware.rate_limiting import RateLimitingMiddleware
from middleware.error_handling import ErrorHandlingMiddleware

def configure_middleware(app: FastAPI):
    """Configure application middleware stack"""
    
    # Error handling (outermost layer)
    app.add_middleware(ErrorHandlingMiddleware)
    
    # Security middleware
    app.add_middleware(SecurityMiddleware)
    
    # Rate limiting
    app.add_middleware(
        RateLimitingMiddleware,
        requests_per_minute=1000,
        burst_size=100
    )
    
    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",      # Development
            "https://yourapp.com",        # Production
            "https://api.yourapp.com"     # API domain
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page-Count"]
    )
```

## 4. SECURITY ARCHITECTURE

### 4.1 Multi-Layer Security Model

```python
# Security Architecture Implementation

class SecurityArchitecture:
    """Comprehensive security architecture"""
    
    def __init__(self):
        self.layers = {
            "input_validation": InputValidationLayer(),
            "authentication": AuthenticationLayer(),
            "authorization": AuthorizationLayer(),
            "data_sanitization": DataSanitizationLayer(),
            "audit_logging": AuditLoggingLayer()
        }
    
    async def process_request(self, request):
        """Process request through security layers"""
        
        # Layer 1: Input Validation
        await self.layers["input_validation"].validate(request)
        
        # Layer 2: Authentication
        user = await self.layers["authentication"].authenticate(request)
        
        # Layer 3: Authorization
        await self.layers["authorization"].authorize(user, request)
        
        # Layer 4: Data Sanitization
        sanitized_data = await self.layers["data_sanitization"].sanitize(
            request.data
        )
        
        # Layer 5: Audit Logging
        await self.layers["audit_logging"].log(user, request)
        
        return sanitized_data
```

### 4.2 Input Validation Architecture

```python
# Comprehensive Input Validation

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import bleach
import re

class InputValidationService:
    """Centralized input validation service"""
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not value:
            return ""
        
        # Remove HTML/JS injection attempts
        value = bleach.clean(value, strip=True)
        
        # Limit length
        value = value[:max_length]
        
        # Remove control characters
        value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)
        
        return value.strip()
    
    @staticmethod
    def validate_file_upload(file_data: bytes, allowed_types: List[str]) -> bool:
        """Validate file upload security"""
        
        # Check file size (max 500MB)
        if len(file_data) > 500 * 1024 * 1024:
            raise ValueError("File size exceeds maximum allowed")
        
        # Check file type by magic bytes
        if not FileTypeValidator.is_valid_video(file_data):
            raise ValueError("Invalid file type")
        
        # Scan for malicious content
        if MalwareScanner.scan(file_data):
            raise ValueError("File contains malicious content")
        
        return True
    
    @staticmethod
    def validate_json_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate JSON payload structure"""
        
        # Limit JSON depth
        if JSONUtils.get_depth(payload) > 10:
            raise ValueError("JSON payload too deeply nested")
        
        # Limit total size
        if len(str(payload)) > 1024 * 1024:  # 1MB
            raise ValueError("JSON payload too large")
        
        # Sanitize all string values
        return JSONUtils.sanitize_strings(payload)
```

### 4.3 Authentication & Authorization

```python
# Authentication and Authorization System

class AuthenticationService:
    """JWT-based authentication service"""
    
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = "HS256"
        self.token_expiry = 3600  # 1 hour
    
    async def authenticate_user(self, token: str) -> Optional[User]:
        """Authenticate user from JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub")
            
            if not user_id:
                return None
            
            # Validate token expiry
            exp = payload.get("exp", 0)
            if datetime.utcnow().timestamp() > exp:
                return None
            
            # Load user from database
            user = await self.get_user(user_id)
            return user
            
        except JWTError:
            return None
    
    async def generate_token(self, user: User) -> str:
        """Generate JWT token for user"""
        payload = {
            "sub": user.id,
            "username": user.username,
            "roles": user.roles,
            "exp": datetime.utcnow() + timedelta(seconds=self.token_expiry),
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

class AuthorizationService:
    """Role-based authorization service"""
    
    PERMISSIONS = {
        "admin": ["*"],
        "annotator": [
            "projects:read",
            "videos:read",
            "annotations:create",
            "annotations:update",
            "annotations:read"
        ],
        "viewer": [
            "projects:read",
            "videos:read",
            "annotations:read",
            "results:read"
        ]
    }
    
    async def check_permission(self, user: User, action: str, resource: str) -> bool:
        """Check if user has permission for action on resource"""
        
        required_permission = f"{resource}:{action}"
        user_permissions = []
        
        for role in user.roles:
            user_permissions.extend(self.PERMISSIONS.get(role, []))
        
        # Check for wildcard permission
        if "*" in user_permissions:
            return True
        
        # Check specific permission
        return required_permission in user_permissions
```

## 5. INTEGRATION ARCHITECTURE

### 5.1 Service Integration Patterns

```python
# Service Integration Architecture

class ServiceOrchestrator:
    """Central service orchestration"""
    
    def __init__(self):
        self.services = {
            "project_service": ProjectService(),
            "video_service": VideoService(),
            "annotation_service": AnnotationService(),
            "ground_truth_service": GroundTruthService(),
            "ml_inference_service": MLInferenceService(),
            "validation_service": ValidationService()
        }
        
        self.event_bus = EventBus()
        self.cache = RedisCache()
    
    async def create_project_with_video(self, project_data: dict, video_file: bytes):
        """Orchestrated project creation with video upload"""
        
        async with DatabaseTransaction() as transaction:
            try:
                # Step 1: Create project
                project = await self.services["project_service"].create(
                    project_data, transaction
                )
                
                # Step 2: Upload and process video
                video = await self.services["video_service"].upload(
                    project.id, video_file, transaction
                )
                
                # Step 3: Generate ground truth (async)
                await self.event_bus.publish("video.uploaded", {
                    "video_id": video.id,
                    "project_id": project.id
                })
                
                # Step 4: Cache results
                await self.cache.set(f"project:{project.id}", project.dict())
                
                await transaction.commit()
                return project, video
                
            except Exception as e:
                await transaction.rollback()
                raise ServiceOrchestrationError(f"Failed to create project: {e}")
```

### 5.2 Event-Driven Architecture

```python
# Event-Driven Integration System

class EventBus:
    """Asynchronous event bus for service communication"""
    
    def __init__(self):
        self.subscribers = defaultdict(list)
        self.redis_client = redis.Redis()
    
    async def publish(self, event_type: str, payload: dict):
        """Publish event to all subscribers"""
        
        event = {
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        # Notify local subscribers
        for handler in self.subscribers[event_type]:
            asyncio.create_task(handler(event))
        
        # Publish to Redis for distributed subscribers
        await self.redis_client.publish(
            f"events:{event_type}", 
            json.dumps(event)
        )
    
    def subscribe(self, event_type: str, handler: callable):
        """Subscribe to event type"""
        self.subscribers[event_type].append(handler)

# Event Handlers
class VideoEventHandlers:
    """Event handlers for video-related events"""
    
    @staticmethod
    async def on_video_uploaded(event: dict):
        """Handle video uploaded event"""
        video_id = event["payload"]["video_id"]
        
        # Start ground truth generation
        await GroundTruthService().generate_async(video_id)
    
    @staticmethod
    async def on_ground_truth_generated(event: dict):
        """Handle ground truth generated event"""
        video_id = event["payload"]["video_id"]
        
        # Update video status
        await VideoService().update_status(video_id, "ground_truth_ready")
        
        # Notify frontend via WebSocket
        await WebSocketManager().broadcast_to_room(
            f"video:{video_id}", 
            {"type": "ground_truth_ready", "video_id": video_id}
        )
```

## 6. ERROR HANDLING & LOGGING ARCHITECTURE

### 6.1 Comprehensive Error Handling

```python
# Error Handling Architecture

class ErrorHandler:
    """Centralized error handling system"""
    
    ERROR_TYPES = {
        "ValidationError": {"status": 400, "level": "WARNING"},
        "AuthenticationError": {"status": 401, "level": "WARNING"},
        "AuthorizationError": {"status": 403, "level": "WARNING"},
        "NotFoundError": {"status": 404, "level": "INFO"},
        "ConflictError": {"status": 409, "level": "WARNING"},
        "ServiceUnavailableError": {"status": 503, "level": "ERROR"},
        "InternalServerError": {"status": 500, "level": "ERROR"}
    }
    
    async def handle_exception(self, request: Request, exc: Exception):
        """Handle application exceptions"""
        
        error_type = type(exc).__name__
        error_info = self.ERROR_TYPES.get(error_type, {
            "status": 500, 
            "level": "ERROR"
        })
        
        # Log error with appropriate level
        logger.log(
            getattr(logging, error_info["level"]),
            f"Error handling request {request.url}: {str(exc)}",
            extra={
                "error_type": error_type,
                "request_id": request.state.request_id,
                "user_id": getattr(request.state, "user_id", None),
                "traceback": traceback.format_exc() if error_info["level"] == "ERROR" else None
            }
        )
        
        # Return appropriate error response
        return JSONResponse(
            status_code=error_info["status"],
            content={
                "error": error_type,
                "message": str(exc),
                "request_id": request.state.request_id
            }
        )
```

### 6.2 Structured Logging Architecture

```python
# Structured Logging System

import structlog
from pythonjsonlogger import jsonlogger

class LoggingConfiguration:
    """Configure structured logging"""
    
    @staticmethod
    def configure():
        """Configure application logging"""
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configure Python logging
        handler = logging.StreamHandler()
        handler.setFormatter(jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        ))
        
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

class AuditLogger:
    """Audit logging for security and compliance"""
    
    def __init__(self):
        self.logger = structlog.get_logger("audit")
    
    async def log_user_action(self, user_id: str, action: str, resource: str, 
                             details: dict = None):
        """Log user action for audit trail"""
        
        await self.logger.info(
            "User action",
            user_id=user_id,
            action=action,
            resource=resource,
            details=details or {},
            timestamp=datetime.utcnow().isoformat(),
            ip_address=request.client.host if request else None
        )
    
    async def log_system_event(self, event_type: str, details: dict):
        """Log system event"""
        
        await self.logger.info(
            "System event",
            event_type=event_type,
            details=details,
            timestamp=datetime.utcnow().isoformat()
        )
```

## 7. DATA FLOW ARCHITECTURE

### 7.1 Data Flow Diagram

```
┌─────────────┐    1. Upload     ┌─────────────┐
│   Client    │─────────────────→│  API Gateway │
│ (React App) │                  │ (FastAPI)   │
└─────────────┘                  └─────────────┘
       ▲                                │ 2. Validate
       │                                ▼
       │ 8. Response           ┌─────────────┐
       │                       │ Video       │
       │                       │ Service     │
       │                       └─────────────┘
       │                                │ 3. Store
       │                                ▼
       │                       ┌─────────────┐
       │                       │ Database    │
       │                       │ (PostgreSQL)│
       │                       └─────────────┘
       │                                │ 4. Event
       │                                ▼
       │                       ┌─────────────┐
       │                       │ Event Bus   │
       │                       │ (Redis)     │
       │                       └─────────────┘
       │                                │ 5. Trigger
       │                                ▼
       │                       ┌─────────────┐
       │                       │ ML          │
       │                       │ Inference   │
       │                       └─────────────┘
       │                                │ 6. Generate
       │                                ▼
       │                       ┌─────────────┐
       │                       │ Ground      │
       │                       │ Truth       │
       │                       └─────────────┘
       │                                │ 7. Update
       │                                ▼
       └───────────────────────────────────┘
```

### 7.2 Data Processing Pipeline

```python
# Data Processing Pipeline Architecture

class DataProcessingPipeline:
    """Orchestrated data processing pipeline"""
    
    def __init__(self):
        self.stages = [
            ValidationStage(),
            StorageStage(), 
            MetadataExtractionStage(),
            MLInferenceStage(),
            GroundTruthGenerationStage(),
            AnnotationStage(),
            ValidationStage()
        ]
    
    async def process_video(self, video_data: bytes, metadata: dict):
        """Process video through all pipeline stages"""
        
        context = ProcessingContext({
            "video_data": video_data,
            "metadata": metadata,
            "results": {}
        })
        
        for stage in self.stages:
            try:
                context = await stage.process(context)
                
                # Log stage completion
                logger.info(f"Completed stage: {stage.__class__.__name__}")
                
            except Exception as e:
                # Handle stage failure
                logger.error(f"Stage {stage.__class__.__name__} failed: {e}")
                await self.handle_stage_failure(stage, context, e)
                break
        
        return context.results

class ValidationStage:
    """Video validation stage"""
    
    async def process(self, context: ProcessingContext):
        """Validate video file and metadata"""
        
        # Validate file format
        if not self.is_valid_video_format(context.video_data):
            raise ValidationError("Invalid video format")
        
        # Validate metadata
        if not self.validate_metadata(context.metadata):
            raise ValidationError("Invalid metadata")
        
        # Extract basic properties
        properties = await self.extract_basic_properties(context.video_data)
        context.results["properties"] = properties
        
        return context

class MLInferenceStage:
    """ML inference stage for object detection"""
    
    async def process(self, context: ProcessingContext):
        """Run ML inference on video"""
        
        video_path = context.results["file_path"]
        
        # Load ML model
        model = await self.load_model("yolov8n")
        
        # Process video frames
        detections = await self.process_video_frames(model, video_path)
        
        # Store detection results
        context.results["detections"] = detections
        context.results["detection_count"] = len(detections)
        
        return context
```

## 8. DEPLOYMENT ARCHITECTURE

### 8.1 Container Architecture

```yaml
# Docker Compose Production Configuration

version: '3.8'

services:
  # Application Services
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile.production
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/validation_platform
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - video_storage:/app/uploads
      - model_storage:/app/models
    networks:
      - validation_network
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
  
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.production
    environment:
      - REACT_APP_API_URL=http://api:8000
    depends_on:
      - api
    networks:
      - validation_network
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
  
  # Data Services
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=validation_platform
      - POSTGRES_USER=${DB_USER}
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - validation_network
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
  
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - validation_network
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.25'
  
  # Infrastructure Services
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
    depends_on:
      - frontend
      - api
    networks:
      - validation_network

volumes:
  postgres_data:
  redis_data:
  video_storage:
  model_storage:

networks:
  validation_network:
    driver: bridge
```

### 8.2 Scalability Architecture

```python
# Horizontal Scaling Configuration

class ScalingConfiguration:
    """Auto-scaling configuration"""
    
    SCALING_METRICS = {
        "api": {
            "min_replicas": 2,
            "max_replicas": 10,
            "cpu_threshold": 70,
            "memory_threshold": 80,
            "request_rate_threshold": 1000  # requests/sec
        },
        "ml_inference": {
            "min_replicas": 1,
            "max_replicas": 5,
            "cpu_threshold": 80,
            "memory_threshold": 90,
            "queue_length_threshold": 10
        },
        "database": {
            "read_replicas": 3,
            "connection_pool_size": 50,
            "max_connections": 200
        }
    }
    
    @staticmethod
    def get_scaling_rules():
        """Get auto-scaling rules"""
        return {
            "scale_up_triggers": [
                "cpu_utilization > 70%",
                "memory_utilization > 80%",
                "request_rate > 1000/sec",
                "response_time_p95 > 500ms"
            ],
            "scale_down_triggers": [
                "cpu_utilization < 30%",
                "memory_utilization < 40%", 
                "request_rate < 200/sec"
            ],
            "cooldown_period": 300,  # 5 minutes
            "evaluation_period": 60   # 1 minute
        }
```

## 9. PERFORMANCE & MONITORING

### 9.1 Performance Optimization

```python
# Performance Optimization Architecture

class PerformanceOptimizer:
    """System performance optimization"""
    
    def __init__(self):
        self.cache = RedisCache()
        self.metrics = MetricsCollector()
    
    async def optimize_database_queries(self):
        """Optimize database query performance"""
        
        # Implement connection pooling
        pool_config = {
            "pool_size": 25,
            "max_overflow": 50,
            "pool_timeout": 30,
            "pool_recycle": 3600
        }
        
        # Enable query caching
        cache_config = {
            "query_cache_size": "256MB",
            "cache_timeout": 300  # 5 minutes
        }
        
        return pool_config, cache_config
    
    async def optimize_api_responses(self):
        """Optimize API response performance"""
        
        # Enable response compression
        compression_config = {
            "algorithms": ["gzip", "brotli"],
            "min_size": 1024,  # Only compress responses > 1KB
            "level": 6  # Compression level
        }
        
        # Implement response caching
        cache_config = {
            "cache_headers": {
                "Cache-Control": "public, max-age=300",
                "ETag": True,
                "Last-Modified": True
            }
        }
        
        return compression_config, cache_config
```

### 9.2 Monitoring Architecture

```python
# Comprehensive Monitoring System

class MonitoringSystem:
    """Application monitoring and alerting"""
    
    def __init__(self):
        self.metrics_collector = PrometheusMetrics()
        self.logger = structlog.get_logger("monitoring")
        self.alerting = AlertingSystem()
    
    async def collect_application_metrics(self):
        """Collect application performance metrics"""
        
        metrics = {
            "http_requests_total": self.metrics_collector.counter(
                "http_requests_total",
                "Total HTTP requests",
                ["method", "endpoint", "status"]
            ),
            "http_request_duration": self.metrics_collector.histogram(
                "http_request_duration_seconds",
                "HTTP request duration",
                ["method", "endpoint"]
            ),
            "database_connections_active": self.metrics_collector.gauge(
                "database_connections_active",
                "Active database connections"
            ),
            "ml_inference_duration": self.metrics_collector.histogram(
                "ml_inference_duration_seconds",
                "ML inference duration"
            ),
            "video_processing_queue_size": self.metrics_collector.gauge(
                "video_processing_queue_size",
                "Video processing queue size"
            )
        }
        
        return metrics
    
    async def setup_health_checks(self):
        """Setup comprehensive health checks"""
        
        health_checks = [
            DatabaseHealthCheck(),
            RedisHealthCheck(),
            FileSystemHealthCheck(),
            MLModelHealthCheck(),
            ExternalAPIHealthCheck()
        ]
        
        for check in health_checks:
            await check.register()
        
        return health_checks
```

## 10. CONCLUSION

This comprehensive system architecture provides:

1. **Scalable Foundation**: Multi-layer architecture supporting horizontal scaling
2. **Data Integrity**: Robust database design with comprehensive indexing
3. **Security**: Multi-layer security with input validation and audit logging  
4. **Performance**: Optimized for high-throughput video processing
5. **Maintainability**: Clean service separation with event-driven integration
6. **Monitoring**: Comprehensive observability and alerting
7. **Deployment**: Container-based deployment with auto-scaling

The architecture supports the core requirements for annotation management, ground truth validation, and ML inference while providing extensibility for future enhancements.