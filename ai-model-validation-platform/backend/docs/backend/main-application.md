# Main Application Analysis - FastAPI Backend

## Overview

The main application (`main.py`) is a sophisticated FastAPI application designed for AI model validation, specifically focusing on VRU (Vulnerable Road User) detection systems with LabJack hardware timing integration.

## Application Structure

### Core Configuration
- **Framework**: FastAPI with async support
- **Title**: "AI Model Validation Platform" 
- **Version**: Configurable via settings (default 1.0.0)
- **Environment**: Development/Production support
- **Lifespan Management**: Full application lifecycle with startup/shutdown hooks

### Application Initialization

```python
app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.api_debug,
    lifespan=lifespan
)
```

### Startup Process (Lifespan Manager)

1. **Logging Configuration**
   - Basic logging setup from config.py
   - Environment-specific log levels
   - Structured logging with extra metadata

2. **Security Validation** (Currently Disabled)
   - Planned security middleware integration
   - Environment validation
   - Security header configuration

3. **Directory Creation**
   - Upload directories (`uploads/`)
   - Screenshot directories (`screenshots/`)
   - Log directories

4. **Database Initialization**
   - Safe startup database system
   - Comprehensive migration handling
   - Error tolerance for development

5. **Service Initialization**
   - Ground truth service
   - Video validation service
   - Detection pipeline services

## Middleware Configuration

### CORS (Cross-Origin Resource Sharing)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Default: localhost:3000, 8001
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600
)
```

### Static File Serving
- `/uploads` → `uploads/` directory (video files)
- `/screenshots` → `screenshots/` directory (detection snapshots)

## Router Registration Order

The application includes routers in a specific order for endpoint precedence:

1. **Authentication Router** (`auth_router`)
2. **LabJack Hardware API** (`labjack_hardware_router`)
3. **Reports Router** (`reports_router`) - PRD Module 4.2
4. **Dashboard Router** (`dashboard_router`)
5. **Video Ingestion Router** (`video_ingestion_router`)
6. **Videos Router** (`videos_router`)
7. **Test Sessions Router** (`test_sessions_router`)
8. **Datasets Router** (`datasets_router`)
9. **Enhanced Test Routers** (Multiple)
10. **Ground Truth Router** (`ground_truth_router`)

## Custom Endpoints

### Video File Serving
```python
@app.get("/api/videos/{video_id}/file")
async def get_video_file(video_id: str, db: Session = Depends(get_db)):
```
**Features:**
- Dynamic video file resolution
- Fallback path handling
- Proper HTTP headers (Accept-Ranges, Cache-Control)
- Error handling for missing files

### Screenshot Serving
```python
@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
```
**Features:**
- Direct file serving
- 404 error handling

### Ground Truth Video Endpoint
```python
@app.get("/api/ground-truth/videos/available")
async def get_videos_with_ground_truth(db: Session = Depends(get_db)):
```
**Features:**
- Frontend-compatible response format
- Ground truth count calculation
- Comprehensive video metadata
- Error tolerance (returns empty list vs. errors)

### WebSocket LabJack Streaming
```python
@app.websocket("/ws/labjack/stream")
async def labjack_websocket_stream(websocket: WebSocket):
```
**Features:**
- Real-time LabJack data streaming
- 30ms timing optimization
- Connection state management
- Safe message sending with error handling

## Import Architecture

### Service Imports
- **Ground Truth Service**: `services.ground_truth_service`
- **Video Library Manager**: `services.video_library_service`
- **Detection Pipeline**: `services.detection_pipeline_service`
- **Signal Processing**: `services.signal_processing_service`
- **Validation Services**: Multiple validation services

### API Router Imports
- Modular router architecture
- Fallback handling for missing modules
- Development-friendly error tolerance

### ML Dependencies
```python
try:
    import torch
    import ultralytics
except ImportError:
    # Auto-installer for ML dependencies
    subprocess.run([sys.executable, "auto_install_ml.py"])
```

## Database Integration

### Session Management
- SQLAlchemy ORM with dependency injection
- Proper session lifecycle management
- Error handling and rollback support

### Database Startup
```python
from database_startup import safe_startup_database
database_ready = safe_startup_database()
```

## Security Features (Planned)

### Currently Disabled
- Security middleware
- Enhanced logging
- Security validation

### Configuration Ready
- JWT token support
- CORS configuration
- Security headers
- SSL/TLS support

## Environment Support

### Development Mode
- Debug logging enabled
- Hot reloading support
- Relaxed security validation
- SQLite database support

### Production Mode
- Enhanced security validation
- PostgreSQL database support
- SSL/TLS enforcement
- Comprehensive audit logging

## Error Handling

### Startup Resilience
- Graceful degradation for missing components
- Warning logs instead of crashes
- Development-friendly fallbacks

### Runtime Error Handling
- Structured exception handling
- HTTP status code mapping
- User-friendly error messages

## Background Tasks

### Auto-Installation
- ML dependency auto-installer
- Development environment setup
- Fallback mode configuration

### Service Integration
- Progress tracking system
- Background video processing
- Real-time WebSocket connections

## Configuration Management

### Settings Integration
- Centralized configuration via `config.py`
- Environment variable support
- Default value fallbacks
- Validation and error checking

### Directory Management
- Automatic directory creation
- Path validation
- Upload directory management

## API Documentation

### FastAPI Integration
- Automatic OpenAPI schema generation
- Interactive documentation at `/docs`
- Redoc documentation at `/redoc`
- Type-safe request/response models

### Response Models
- Pydantic model integration
- CamelCase API compatibility
- Comprehensive type validation
- Error response schemas

## Performance Considerations

### Static File Optimization
- Direct file serving for videos
- Caching headers
- Range request support

### Database Optimization
- Connection pooling
- Query optimization
- Lazy loading strategies

### WebSocket Optimization
- 30ms timing for LabJack streams
- Connection state validation
- Efficient message serialization

## Monitoring and Logging

### Structured Logging
- Event type categorization
- Extra metadata support
- Environment-specific levels

### Application Events
- Startup/shutdown tracking
- Router registration logging
- Error event logging

## Development Features

### Hot Reloading
- Module import fallbacks
- Development-friendly error handling
- Debug mode support

### Testing Support
- Test database configuration
- Mock service integration
- Development data fixtures