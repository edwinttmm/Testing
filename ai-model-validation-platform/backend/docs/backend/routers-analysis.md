# Routers Analysis - API Organization Architecture

## Overview

The FastAPI application uses a modular router architecture to organize API endpoints by functional domain. Each router handles a specific aspect of the system, from authentication to video processing to report generation.

## Router Architecture

### Router Registration Order
Routers are registered in a specific order to ensure proper endpoint precedence:

1. **Authentication Router** - Must be first for security
2. **LabJack Hardware Router** - Hardware integration
3. **Reports Router** - PRD Module 4.2 compliance
4. **Dashboard Router** - System statistics
5. **Video Ingestion Router** - Core video processing
6. **Videos Router** - Video management
7. **Test Sessions Router** - Test execution
8. **Datasets Router** - Dataset management
9. **Enhanced Test Routers** - Multiple enhanced test workflows
10. **Ground Truth Router** - Annotation management

## Detailed Router Analysis

### 1. Authentication Router (`/api/auth`)

**Location**: `auth_endpoints.py`
**Purpose**: User authentication and session management

**Endpoints**:
- `POST /api/auth/login` - User login with JWT token generation
- `POST /api/auth/register` - New user registration
- `POST /api/auth/logout` - Session termination
- `GET /api/auth/me` - Current user profile
- `POST /api/auth/refresh` - JWT token refresh
- `POST /api/auth/forgot-password` - Password reset initiation
- `POST /api/auth/reset-password` - Password reset completion

**Security Features**:
- JWT token generation and validation
- Password hashing with bcrypt
- Session management
- Rate limiting on sensitive endpoints

### 2. Projects Router (`/api/projects`)

**Location**: `routers/projects.py`  
**Purpose**: Project lifecycle management

```python
router = APIRouter(prefix="/api/projects", tags=["Project Management"])
```

**Key Features**:
- User-scoped project access
- Project-video relationship management
- Statistics and analytics
- Bulk operations support

**Sample Endpoints**:
```python
@router.post("", response_model=ProjectResponse)
async def create_new_project(project: ProjectCreate, db: Session = Depends(get_db))

@router.get("", response_model=List[ProjectResponse])
async def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db))
```

### 3. Videos Router (`/api/videos`)

**Location**: `routers/videos.py`
**Purpose**: Video file management and processing

**Key Features**:
- Video upload with validation
- File serving with dynamic path resolution
- Processing status tracking
- Ground truth integration

**Upload Handling**:
```python
@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    db: Session = Depends(get_db)
)
```

### 4. Test Sessions Router (`/api/test-sessions`)

**Location**: `routers/test_sessions.py`
**Purpose**: Test execution workflow management

**Key Features**:
- Test session lifecycle
- Execution monitoring
- Result aggregation
- Session-based security

### 5. Reports Router (`/api/reports`)

**Location**: `routers/reports.py`
**Purpose**: PRD Module 4.2 - Test report generation

**Key Features**:
- Multiple format support (HTML, PDF, JSON)
- Failure snapshot integration
- Comprehensive metrics calculation
- Report template management

**Core Endpoints**:
```python
@router.post("/generate", response_model=TestReportFileResponse)
async def generate_test_report(
    request: ReportGenerationRequest,
    db: Session = Depends(get_db)
)

@router.get("/{report_id}/download")
async def download_report(report_id: str, format: str = "html")
```

### 6. Dashboard Router (`/api/dashboard`)

**Location**: `routers/dashboard.py`
**Purpose**: System statistics and monitoring

**Key Features**:
- Real-time system metrics
- User-scoped statistics
- Performance monitoring
- Health checks

### 7. Datasets Router (`/api/datasets`)

**Location**: `routers/datasets.py`
**Purpose**: Dataset management and annotation

**Key Features**:
- Dataset creation and management
- Annotation workflow orchestration
- Export functionality
- Version control

### 8. LabJack Hardware Router (`/api/labjack`)

**Location**: `api/labjack_hardware_api.py`
**Purpose**: Hardware integration for timing validation

**Key Features**:
- Device connection management
- Real-time data streaming
- Timing calibration
- WebSocket support

## Enhanced Test Routers

### Enhanced Test Router
**Location**: `api_enhanced_test.py`
**Purpose**: Core enhanced test functionality

### Enhanced Test Workflow Router
**Location**: `api_enhanced_test_workflow.py`
**Purpose**: Workflow orchestration

### Enhanced Test Workflow Integrated Router
**Location**: `api_enhanced_test_workflow_integrated.py`
**Purpose**: Integrated workflow management

### Signal Validation Router
**Location**: `api_signal_validation.py`
**Purpose**: Signal processing validation

### Comprehensive Results Router
**Location**: `api_comprehensive_results.py`
**Purpose**: Advanced result analysis

### Enhanced Test Execution Router
**Location**: `api_enhanced_test_execution.py`
**Purpose**: Test execution engine

### Project Session Router
**Location**: `api_project_session_management.py`
**Purpose**: Project-level session management

## Router Dependencies

### Database Dependencies
```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Authentication Dependencies
```python
def get_current_user(token: str = Depends(oauth2_scheme)):
    # JWT token validation
    return user
```

### Service Dependencies
```python
# Service injection pattern
video_library_manager = VideoLibraryManager()
ground_truth_service = GroundTruthService()
```

## Error Handling Patterns

### Consistent Error Responses
```python
@router.get("/{item_id}")
async def get_item(item_id: str, db: Session = Depends(get_db)):
    try:
        item = get_item_from_db(db, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        return item
    except Exception as e:
        logger.error(f"Error getting item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

### Validation Error Handling
```python
@router.post("/")
async def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    try:
        return create_item_crud(db, item)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except IntegrityError as e:
        raise HTTPException(status_code=409, detail="Resource already exists")
```

## Response Model Patterns

### Consistent Response Schemas
```python
# List responses with metadata
@router.get("", response_model=List[ItemResponse])
async def list_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    items = get_items(db, skip=skip, limit=limit)
    return items
```

### Pagination Support
```python
class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    skip: int
    limit: int
    has_more: bool
```

## Security Implementation

### Route-Level Security
```python
@router.get("/protected", dependencies=[Depends(get_current_user)])
async def protected_endpoint():
    return {"message": "Access granted"}
```

### Role-Based Access Control
```python
@router.delete("/{item_id}", dependencies=[Depends(require_admin)])
async def delete_item(item_id: str):
    # Only admins can delete
    pass
```

## File Upload Handling

### Secure File Upload
```python
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # File validation
    if not file.content_type.startswith('video/'):
        raise HTTPException(400, "Invalid file type")
    
    # Size validation
    if file.size > settings.max_file_size:
        raise HTTPException(413, "File too large")
    
    # Process upload
    return await process_upload(file, db)
```

## WebSocket Integration

### WebSocket Endpoints
```python
@app.websocket("/ws/labjack/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await get_labjack_data()
            await websocket.send_json(data)
            await asyncio.sleep(0.030)  # 30ms timing
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

## Background Task Integration

### Task Orchestration
```python
@router.post("/process")
async def start_processing(
    request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    background_tasks.add_task(process_video, request.video_id)
    return {"status": "processing_started"}
```

## Monitoring and Logging

### Request Logging
```python
@router.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    logger.info(
        f"Request: {request.method} {request.url} "
        f"Status: {response.status_code} "
        f"Duration: {process_time:.3f}s"
    )
    return response
```

### Health Check Endpoints
```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": settings.app_version
    }
```

## OpenAPI Documentation

### Tags and Metadata
```python
router = APIRouter(
    prefix="/api/videos",
    tags=["Video Management"],
    responses={404: {"description": "Not found"}}
)
```

### Response Documentation
```python
@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get video details",
    description="Retrieve detailed information about a specific video",
    responses={
        200: {"description": "Video details retrieved successfully"},
        404: {"description": "Video not found"},
        403: {"description": "Access denied"}
    }
)
```

## Performance Optimization

### Query Optimization
```python
# Use select_related equivalent (joinedload) for N+1 prevention
@router.get("/projects-with-videos")
async def get_projects_with_videos(db: Session = Depends(get_db)):
    return db.query(Project).options(
        joinedload(Project.videos)
    ).all()
```

### Caching Integration
```python
@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    cache_key = f"stats:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    stats = calculate_stats(db)
    await redis.setex(cache_key, 300, json.dumps(stats))
    return stats
```

## Testing Patterns

### Router Testing
```python
def test_create_project(client, db_session):
    project_data = {
        "name": "Test Project",
        "description": "Test Description"
    }
    response = client.post("/api/projects", json=project_data)
    assert response.status_code == 201
    assert response.json()["name"] == "Test Project"
```

### Dependency Override
```python
def override_get_db():
    return test_db_session

app.dependency_overrides[get_db] = override_get_db
```