# Router Architecture Migration Guide

## Overview

This document outlines the reorganization of the AI Model Validation Platform API from scattered endpoints in `main.py` to an organized router structure following FastAPI best practices.

## Architecture Before and After

### Before: Scattered Endpoints
- **main.py**: 3,300+ lines with mixed endpoints
- **api_project_session_management.py**: Project session endpoints
- **api_video_annotation.py**: Video annotation endpoints
- **auth_endpoints.py**: Authentication endpoints
- No clear organization by resource type
- Inconsistent patterns between files

### After: Organized Router Structure
```
/routers/
├── __init__.py              # Router package initialization
├── projects.py              # All project-related endpoints
├── videos.py                # All video-related endpoints  
├── test_sessions.py         # All test session endpoints
├── auth.py                  # Authentication endpoints
└── dashboard.py             # Dashboard and monitoring endpoints
```

## Router Responsibilities

### 1. Projects Router (`/api/projects`)
**File**: `routers/projects.py`

**Endpoints**:
- `POST /api/projects` - Create new project
- `GET /api/projects` - List projects with filtering
- `GET /api/projects/{id}` - Get project details
- `PUT /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project
- `POST /api/projects/{id}/videos/link` - Link video to project
- `GET /api/projects/{id}/videos/linked` - Get linked videos
- `DELETE /api/projects/{id}/videos/{video_id}/unlink` - Unlink video
- `GET /api/projects/{id}/statistics` - Get project statistics
- `POST /api/projects/{id}/criteria/configure` - Configure pass/fail criteria

**Features**:
- Project CRUD operations
- Video-project relationship management
- Project statistics and analytics
- Intelligent video assignments
- Pass/fail criteria configuration

### 2. Videos Router (`/api/videos`)
**File**: `routers/videos.py`

**Endpoints**:
- `POST /api/videos` - Upload video file
- `GET /api/videos` - List videos with filtering
- `POST /api/videos/{project_id}/videos` - Upload to specific project
- `GET /api/videos/{project_id}/videos` - Get project videos
- `DELETE /api/videos/{id}` - Delete video
- `POST /api/videos/{id}/annotations` - Create annotation
- `GET /api/videos/{id}/annotations` - Get annotations
- `GET /api/videos/{id}/stats` - Get annotation statistics
- `GET /api/videos/{id}/ground-truth` - Get ground truth data
- `POST /api/videos/{id}/process-ground-truth` - Process ground truth
- `GET /api/videos/{id}/detections` - Get detection events

**Features**:
- Video upload and storage
- Annotation management
- Ground truth processing
- Detection event tracking
- Video statistics and analysis

### 3. Test Sessions Router (`/api/test-sessions`)
**File**: `routers/test_sessions.py`

**Endpoints**:
- `POST /api/test-sessions` - Create test session
- `GET /api/test-sessions` - List sessions with filtering
- `GET /api/test-sessions/{id}` - Get session details
- `POST /api/test-sessions/{id}/start` - Start session
- `POST /api/test-sessions/{id}/complete` - Complete session
- `GET /api/test-sessions/{id}/status` - Get session status
- `POST /api/test-sessions/detection-events` - Create detection event
- `GET /api/test-sessions/{id}/detections` - Get session detections
- `GET /api/test-sessions/{id}/results` - Get session results
- `GET /api/test-sessions/{id}/latency-metrics` - Get performance metrics

**Features**:
- Test session lifecycle management
- Real-time status monitoring
- Detection event handling
- Results and validation
- Performance metrics

### 4. Authentication Router (`/auth`)
**File**: `routers/auth.py`

**Endpoints**:
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `POST /auth/refresh` - Refresh access token
- `POST /auth/verify-token` - Verify token validity
- `GET /auth/profile` - Get user profile
- `PUT /auth/profile` - Update user profile
- `POST /auth/change-password` - Change password
- `GET /auth/sessions` - Get user sessions
- `DELETE /auth/sessions/{id}` - Revoke session

**Features**:
- JWT-based authentication
- User registration and login
- Session management
- Profile management
- Token refresh and validation

### 5. Dashboard Router (`/api/dashboard`)
**File**: `routers/dashboard.py`

**Endpoints**:
- `GET /api/dashboard/stats` - Basic dashboard statistics
- `GET /api/dashboard/stats/enhanced` - Enhanced statistics
- `GET /api/dashboard/health/system` - System health check
- `GET /api/dashboard/health/database` - Database health check
- `GET /api/dashboard/metrics/performance` - Performance metrics
- `GET /api/dashboard/monitoring/live` - Real-time monitoring

**Features**:
- System health monitoring
- Performance metrics
- Real-time dashboard data
- Database health checks
- Activity trends and analytics

## Migration Benefits

### 1. **Better Organization**
- Clear separation of concerns
- Resource-based routing
- Consistent patterns across routers
- Easy to locate and maintain endpoints

### 2. **Improved Maintainability**
- Smaller, focused files
- Consistent error handling
- Standard dependency injection
- Clear documentation

### 3. **Enhanced Security**
- Centralized authentication patterns
- Consistent input validation
- Standardized error responses
- Security best practices

### 4. **Better Performance**
- Optimized database queries
- Proper connection management
- Request logging and monitoring
- Performance middleware

### 5. **Developer Experience**
- Clear API documentation
- Consistent response formats
- Comprehensive error handling
- Easy testing and debugging

## Implementation Details

### Dependency Injection
All routers use consistent dependency injection patterns:

```python
from database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/endpoint")
async def endpoint_function(db: Session = Depends(get_db)):
    # Endpoint logic
```

### Error Handling
Consistent error handling across all routers:

```python
try:
    # Business logic
    return result
except HTTPException:
    raise
except Exception as e:
    logger.error(f"Error description: {str(e)}")
    raise HTTPException(status_code=500, detail=f"Error message: {str(e)}")
```

### Logging
Structured logging throughout:

```python
import logging
logger = logging.getLogger(__name__)

# Log important operations
logger.info(f"Operation completed: {details}")
logger.error(f"Operation failed: {error}")
```

### Response Models
Consistent Pydantic models for responses:

```python
from pydantic import BaseModel

class ResourceResponse(BaseModel):
    id: str
    name: str
    created_at: datetime
    # Additional fields
```

## Migration Process

### 1. **Backward Compatibility**
- All existing endpoints remain functional
- No breaking changes to API contracts
- Same URL paths maintained
- Consistent response formats

### 2. **Gradual Transition**
- New `main_organized.py` with router structure
- Original `main.py` remains functional
- Easy rollback if needed
- Can run both versions during transition

### 3. **Testing Strategy**
- Comprehensive endpoint testing
- Database integration testing
- Authentication flow testing
- Performance benchmarking

## Usage Instructions

### Running the Organized Version
```bash
# Use the new organized main file
python main_organized.py

# Or with uvicorn
uvicorn main_organized:app --reload --host 0.0.0.0 --port 8000
```

### API Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`
- **API Info**: `http://localhost:8000/api/info`

### Router Health Checks
Each router provides its own health check endpoint:
- Projects: `GET /api/projects/health`
- Videos: `GET /api/videos/health`
- Test Sessions: `GET /api/test-sessions/health`
- Auth: `GET /auth/health`
- Dashboard: `GET /api/dashboard/health`

## Best Practices Followed

### 1. **FastAPI Best Practices**
- Resource-based routing
- Proper dependency injection
- Comprehensive error handling
- Pydantic model validation
- OpenAPI documentation

### 2. **Database Best Practices**
- Connection pooling
- Query optimization
- Transaction management
- Error handling
- Connection cleanup

### 3. **Security Best Practices**
- JWT token validation
- Input sanitization
- Error message sanitization
- Rate limiting considerations
- CORS configuration

### 4. **Performance Best Practices**
- Efficient queries
- Response caching considerations
- Request logging
- Performance monitoring
- Database connection management

## Future Enhancements

### 1. **Additional Routers**
- **Notifications Router**: Real-time notifications
- **Reports Router**: Report generation and management  
- **Admin Router**: Administrative functions
- **Integration Router**: Third-party integrations

### 2. **Advanced Features**
- Request rate limiting
- Response caching
- API versioning
- Advanced monitoring
- Automated testing

### 3. **Microservices Preparation**
- Service boundaries defined
- Independent deployability
- Database per service
- Service communication patterns

## Conclusion

The organized router architecture provides a solid foundation for the AI Model Validation Platform, improving maintainability, scalability, and developer experience while maintaining full backward compatibility with existing API contracts.