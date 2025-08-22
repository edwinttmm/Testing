# SPARC ARCHITECTURE PHASE
## System Design for Video Playback and Detection Integration Fixes

### High-Level Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React/TypeScript)                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Video Player    │  │ Detection UI    │  │ Dataset Mgmt    │  │
│  │ Component       │  │ Controls        │  │ Interface       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│           │                    │                    │           │
│           ▼                    ▼                    ▼           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Video Hook      │  │ Detection Hook  │  │ Dataset Hook    │  │
│  │ useVideoPlayer  │  │ useDetection    │  │ useDataset      │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│           │                    │                    │           │
│           ▼                    ▼                    ▼           │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              API Client & WebSocket Manager                │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI/Python)                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Video API       │  │ Detection API   │  │ Dataset API     │  │
│  │ Endpoints       │  │ Endpoints       │  │ Endpoints       │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│           │                    │                    │           │
│           ▼                    ▼                    ▼           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Video Service   │  │ Detection       │  │ Dataset Service │  │
│  │ Layer           │  │ Pipeline        │  │ Layer           │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
│           │                    │                    │           │
│           ▼                    ▼                    ▼           │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │            Data Access Layer (SQLAlchemy ORM)              │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                               │                                 │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                   Database Schema                           │  │
│  │  Projects ←→ Videos ←→ TestSessions ←→ DetectionEvents     │  │
│  │      ↕           ↕           ↕              ↕              │  │
│  │  VideoLinks  Annotations  SessionStats  GroundTruth       │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Architecture Details

#### 1. Frontend Component Architecture

##### VideoAnnotationPlayer Enhancement
```typescript
interface VideoPlayerArchitecture {
  // Core video handling
  videoElement: HTMLVideoElement;
  metadataManager: VideoMetadataManager;
  frameRateDetector: FrameRateDetector;
  errorRecoveryHandler: VideoErrorHandler;
  
  // State management
  playbackState: PlaybackStateManager;
  frameTracker: FrameTrackingManager;
  annotationRenderer: AnnotationRenderer;
  
  // Integration points
  detectionWebSocket: DetectionWebSocketClient;
  annotationService: AnnotationServiceClient;
  sessionStatsTracker: SessionStatsTracker;
}

class VideoMetadataManager {
  async extractMetadata(videoUrl: string): Promise<VideoMetadata> {
    // Priority order for metadata extraction
    const sources = [
      () => this.extractFromVideoElement(videoUrl),
      () => this.extractFromFileHeaders(videoUrl),
      () => this.extractFromAPI(videoUrl),
      () => this.useDefaultMetadata()
    ];
    
    for (const source of sources) {
      try {
        const metadata = await source();
        if (this.validateMetadata(metadata)) {
          return metadata;
        }
      } catch (error) {
        console.warn('Metadata extraction failed:', error);
      }
    }
    
    throw new Error('Unable to extract valid video metadata');
  }
}

class FrameRateDetector {
  async detectFrameRate(video: HTMLVideoElement): Promise<number> {
    // Multi-method frame rate detection
    const methods = [
      () => this.getFromVideoMetadata(video),
      () => this.calculateFromDuration(video),
      () => this.analyzeFrameTimestamps(video),
      () => this.useDefaultFrameRate(24) // Fallback to common rate
    ];
    
    for (const method of methods) {
      const frameRate = await method();
      if (frameRate > 0 && frameRate <= 120) { // Reasonable range
        return frameRate;
      }
    }
    
    return 24; // Default fallback
  }
}
```

##### Detection Control Interface
```typescript
interface DetectionControlArchitecture {
  // State management
  detectionState: DetectionStateManager;
  progressTracker: ProgressTracker;
  resultAggregator: DetectionResultAggregator;
  
  // Communication
  webSocketManager: DetectionWebSocketManager;
  apiClient: DetectionAPIClient;
  
  // UI components
  controlPanel: DetectionControlPanel;
  progressDisplay: ProgressDisplay;
  resultsViewer: ResultsViewer;
}

class DetectionStateManager {
  private state: DetectionState = {
    status: 'idle', // 'idle' | 'starting' | 'running' | 'paused' | 'stopping' | 'completed' | 'error'
    sessionId: null,
    progress: { current: 0, total: 0 },
    results: [],
    errors: []
  };
  
  async startDetection(videoId: string, config: DetectionConfig): Promise<void> {
    this.setState({ status: 'starting' });
    
    try {
      const response = await this.apiClient.startDetection(videoId, config);
      this.setState({ 
        status: 'running', 
        sessionId: response.sessionId 
      });
      
      await this.webSocketManager.connect(response.sessionId);
    } catch (error) {
      this.setState({ status: 'error', errors: [error] });
      throw error;
    }
  }
  
  async pauseDetection(): Promise<void> {
    if (this.state.status !== 'running') return;
    
    await this.apiClient.pauseDetection(this.state.sessionId);
    this.setState({ status: 'paused' });
  }
  
  async resumeDetection(): Promise<void> {
    if (this.state.status !== 'paused') return;
    
    await this.apiClient.resumeDetection(this.state.sessionId);
    this.setState({ status: 'running' });
  }
  
  async stopDetection(): Promise<void> {
    if (!['running', 'paused'].includes(this.state.status)) return;
    
    this.setState({ status: 'stopping' });
    await this.apiClient.stopDetection(this.state.sessionId);
    this.webSocketManager.disconnect();
    this.setState({ status: 'completed' });
  }
}
```

##### Dataset Management Interface
```typescript
interface DatasetManagementArchitecture {
  // Data management
  dataProvider: ProcessedVideoDataProvider;
  filterManager: DatasetFilterManager;
  sortManager: DatasetSortManager;
  
  // UI components
  videoGrid: ProcessedVideoGrid;
  filterPanel: DatasetFilterPanel;
  statisticsPanel: DatasetStatisticsPanel;
  
  // Export/Import
  exportManager: DatasetExportManager;
  importManager: DatasetImportManager;
}

class ProcessedVideoDataProvider {
  async getProcessedVideos(filters?: DatasetFilters): Promise<ProcessedVideo[]> {
    const params = this.buildQueryParams(filters);
    const response = await this.apiClient.get('/api/dataset/videos', { params });
    
    return response.data.map(video => ({
      ...video,
      detectionSummary: this.aggregateDetections(video.detections),
      datasetReadiness: this.calculateReadinessScore(video),
      projectInfo: video.project || { name: 'Unknown Project', id: null }
    }));
  }
  
  private calculateReadinessScore(video: any): DatasetReadinessScore {
    const criteria = {
      hasDetections: video.detection_count > 0,
      hasValidatedAnnotations: video.validated_annotations > 0,
      hasGroundTruth: video.ground_truth_count > 0,
      hasProject: !!video.project_id,
      fileHealthy: video.file_status === 'healthy'
    };
    
    const score = Object.values(criteria).filter(Boolean).length;
    return {
      score: score * 20, // 0-100 scale
      criteria,
      readiness: score >= 4 ? 'ready' : score >= 2 ? 'partial' : 'not_ready'
    };
  }
}
```

#### 2. Backend Service Architecture

##### Video Processing Service
```python
class VideoServiceArchitecture:
    def __init__(self):
        self.metadata_extractor = VideoMetadataExtractor()
        self.file_validator = VideoFileValidator()
        self.project_manager = ProjectAssociationManager()
        self.storage_manager = VideoStorageManager()
        
    async def process_video_upload(self, video_file, user_context):
        # 1. Validate and store file
        validated_file = await self.file_validator.validate(video_file)
        stored_path = await self.storage_manager.store(validated_file)
        
        # 2. Extract metadata
        metadata = await self.metadata_extractor.extract(stored_path)
        
        # 3. Associate with project
        project_id = await self.project_manager.determine_project(
            video_file, user_context, metadata
        )
        
        # 4. Create database record
        video = await self.create_video_record(
            file_path=stored_path,
            metadata=metadata,
            project_id=project_id
        )
        
        return video

class ProjectAssociationManager:
    async def determine_project(self, video_file, user_context, metadata):
        # Strategy pattern for project determination
        strategies = [
            ExplicitProjectStrategy(),
            UserActiveProjectStrategy(),
            UserDefaultProjectStrategy(),
            FilenameInferenceStrategy(),
            SystemDefaultStrategy()
        ]
        
        for strategy in strategies:
            project_id = await strategy.determine_project(
                video_file, user_context, metadata
            )
            if project_id and await self.validate_project_access(project_id, user_context):
                return project_id
        
        # Create default project if none found
        return await self.create_default_project()
```

##### Detection Pipeline Service Enhancement
```python
class DetectionPipelineArchitecture:
    def __init__(self):
        self.session_manager = DetectionSessionManager()
        self.video_processor = VideoFrameProcessor()
        self.model_manager = MLModelManager()
        self.result_processor = DetectionResultProcessor()
        self.websocket_manager = DetectionWebSocketManager()
        
    async def start_detection_session(self, video_id: str, config: dict, user_id: str):
        # 1. Create detection session
        session = await self.session_manager.create_session(
            video_id=video_id,
            config=config,
            user_id=user_id
        )
        
        # 2. Initialize WebSocket connection
        websocket = await self.websocket_manager.create_connection(session.id)
        
        # 3. Start background processing task
        task = asyncio.create_task(
            self.process_video_async(session, websocket)
        )
        
        # 4. Track session and task
        self.session_manager.track_session(session.id, task)
        
        return session
    
    async def process_video_async(self, session: DetectionSession, websocket):
        try:
            # Initialize processing components
            video_stream = await self.video_processor.open_stream(session.video_path)
            model = await self.model_manager.get_model(session.config.model_type)
            
            frame_count = 0
            total_frames = video_stream.frame_count
            
            async for frame in video_stream:
                # Check session status
                if session.status == 'paused':
                    await self.wait_for_resume(session)
                
                if session.status == 'stopped':
                    break
                
                # Process frame
                detections = await model.detect(frame)
                processed_detections = await self.result_processor.process(
                    detections, frame_count, session
                )
                
                # Store results
                await self.store_detections(processed_detections, session)
                
                # Send real-time updates
                await websocket.send_progress(frame_count, total_frames)
                await websocket.send_detections(processed_detections)
                
                frame_count += 1
            
            # Complete session
            await self.session_manager.complete_session(session.id)
            await websocket.send_completion(session.summary)
            
        except Exception as e:
            await self.session_manager.error_session(session.id, str(e))
            await websocket.send_error(str(e))
        finally:
            await video_stream.close()
            await websocket.close()

class DetectionSessionManager:
    def __init__(self):
        self.active_sessions = {}
        self.session_store = SessionStore()
    
    async def create_session(self, video_id: str, config: dict, user_id: str):
        session = DetectionSession(
            id=str(uuid.uuid4()),
            video_id=video_id,
            user_id=user_id,
            config=config,
            status='created',
            created_at=datetime.utcnow()
        )
        
        await self.session_store.save(session)
        self.active_sessions[session.id] = session
        
        return session
    
    async def pause_session(self, session_id: str):
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = 'paused'
            await self.session_store.update_status(session_id, 'paused')
    
    async def resume_session(self, session_id: str):
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = 'running'
            await self.session_store.update_status(session_id, 'running')
    
    async def stop_session(self, session_id: str):
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = 'stopped'
            await self.session_store.update_status(session_id, 'stopped')
            
            # Cancel background task
            task = self.active_sessions[session_id].task
            if task and not task.done():
                task.cancel()
            
            del self.active_sessions[session_id]
```

##### API Validation Architecture
```python
class APIValidationArchitecture:
    def __init__(self):
        self.field_normalizer = FieldNormalizer()
        self.validation_middleware = ValidationMiddleware()
        self.error_handler = ValidationErrorHandler()
    
    def create_flexible_models(self):
        # Enhanced Pydantic models with field aliases
        
        class FlexibleVideoIdentifier(BaseModel):
            video_id: str = Field(
                validation_alias=AliasChoices('videoId', 'video_id', 'id'),
                serialization_alias='videoId',
                description="Video identifier (flexible field naming)"
            )
            
            @field_validator('video_id', mode='before')
            @classmethod
            def normalize_video_id(cls, value):
                if isinstance(value, dict):
                    return (value.get('videoId') or 
                           value.get('video_id') or 
                           value.get('id'))
                return value
            
            @field_serializer('video_id')
            def serialize_video_id(self, value):
                return value
        
        class DetectionRequest(FlexibleVideoIdentifier):
            config: Optional[DetectionConfig] = None
            timestamp: Optional[float] = None
            
            # Backward compatibility fields
            videoId: Optional[str] = Field(None, exclude=True)
            id: Optional[str] = Field(None, exclude=True)
            
            @model_validator(mode='before')
            @classmethod
            def extract_video_id(cls, values):
                if isinstance(values, dict):
                    # Normalize video identifier fields
                    video_id = (values.get('videoId') or 
                              values.get('video_id') or 
                              values.get('id'))
                    if video_id:
                        values['video_id'] = video_id
                return values
        
        return {
            'DetectionRequest': DetectionRequest,
            'FlexibleVideoIdentifier': FlexibleVideoIdentifier
        }

class ValidationMiddleware:
    async def __call__(self, request: Request, call_next):
        try:
            # Pre-process request data for field normalization
            if hasattr(request, 'json'):
                body = await request.json()
                normalized_body = self.normalize_fields(body)
                # Replace request body with normalized version
                request._body = json.dumps(normalized_body).encode()
        except Exception:
            pass  # Continue with original request if normalization fails
        
        response = await call_next(request)
        return response
    
    def normalize_fields(self, data: dict) -> dict:
        """Normalize common field name variations"""
        normalized = data.copy()
        
        # Video ID normalization
        if 'videoId' in normalized and 'video_id' not in normalized:
            normalized['video_id'] = normalized['videoId']
        elif 'video_id' in normalized and 'videoId' not in normalized:
            normalized['videoId'] = normalized['video_id']
        
        # Recursively normalize nested objects
        for key, value in normalized.items():
            if isinstance(value, dict):
                normalized[key] = self.normalize_fields(value)
            elif isinstance(value, list):
                normalized[key] = [
                    self.normalize_fields(item) if isinstance(item, dict) else item
                    for item in value
                ]
        
        return normalized
```

### Database Schema Architecture

#### Enhanced Entity Relationships
```sql
-- Enhanced schema with proper foreign key relationships

-- Projects table (enhanced)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    description TEXT,
    camera_model VARCHAR NOT NULL,
    camera_view VARCHAR NOT NULL,
    lens_type VARCHAR,
    resolution VARCHAR,
    frame_rate INTEGER,
    signal_type VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'Active',
    owner_id UUID,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Videos table (enhanced with better project relationship)
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    file_size BIGINT,
    duration REAL,
    fps REAL,
    frame_count INTEGER,
    resolution VARCHAR,
    status VARCHAR DEFAULT 'uploaded',
    processing_status VARCHAR DEFAULT 'pending',
    ground_truth_generated BOOLEAN DEFAULT FALSE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE SET NULL,
    uploader_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Session statistics table (new)
CREATE TABLE session_statistics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    total_annotations INTEGER DEFAULT 0,
    total_detections INTEGER DEFAULT 0,
    annotations_by_type JSONB DEFAULT '{}',
    detection_accuracy REAL,
    processing_time_seconds REAL,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(test_session_id)
);

-- Detection sessions table (new)
CREATE TABLE detection_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    user_id UUID,
    config JSONB,
    status VARCHAR DEFAULT 'created',
    progress JSONB DEFAULT '{"current": 0, "total": 0}',
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Annotations table (enhanced to link with detection events)
CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    detection_event_id UUID REFERENCES detection_events(id) ON DELETE SET NULL,
    frame_number INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    vru_type VARCHAR NOT NULL,
    bounding_box JSONB NOT NULL,
    confidence REAL,
    validated BOOLEAN DEFAULT FALSE,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_videos_project_status ON videos(project_id, status);
CREATE INDEX idx_videos_processing_status ON videos(processing_status);
CREATE INDEX idx_detection_events_session_frame ON detection_events(test_session_id, frame_number);
CREATE INDEX idx_annotations_video_timestamp ON annotations(video_id, timestamp);
CREATE INDEX idx_annotations_detection_event ON annotations(detection_event_id);
CREATE INDEX idx_session_stats_session ON session_statistics(test_session_id);
CREATE INDEX idx_detection_sessions_video_status ON detection_sessions(video_id, status);
```

#### Data Migration Architecture
```python
class DataMigrationArchitecture:
    def __init__(self):
        self.migration_executor = MigrationExecutor()
        self.data_validator = DataValidator()
        self.rollback_manager = RollbackManager()
    
    async def migrate_project_associations(self):
        """Migrate videos without proper project associations"""
        migration = ProjectAssociationMigration()
        
        # 1. Create default project if needed
        default_project = await self.ensure_default_project()
        
        # 2. Find orphaned videos
        orphaned_videos = await self.find_orphaned_videos()
        
        # 3. Apply migration strategy
        for video in orphaned_videos:
            try:
                project_id = await self.infer_project(video) or default_project.id
                await self.update_video_project(video.id, project_id)
                await self.update_related_test_sessions(video.id, project_id)
            except Exception as e:
                await self.log_migration_error(video.id, str(e))
        
        # 4. Validate migration results
        await self.validate_project_associations()
    
    async def migrate_detection_annotations_link(self):
        """Create links between detection events and annotations"""
        migration = DetectionAnnotationLinkMigration()
        
        # 1. Find unlinked detection events
        unlinked_detections = await self.find_unlinked_detections()
        
        # 2. Find matching annotations or create new ones
        for detection in unlinked_detections:
            matching_annotation = await self.find_matching_annotation(detection)
            
            if matching_annotation:
                # Link existing annotation
                await self.link_annotation_to_detection(
                    matching_annotation.id, detection.id
                )
            else:
                # Create annotation from detection event
                annotation = await self.create_annotation_from_detection(detection)
                await self.link_annotation_to_detection(
                    annotation.id, detection.id
                )
        
        # 3. Update session statistics
        await self.recalculate_all_session_statistics()

class MigrationExecutor:
    async def execute_with_rollback(self, migration_func, *args, **kwargs):
        """Execute migration with automatic rollback on failure"""
        checkpoint = await self.create_checkpoint()
        
        try:
            result = await migration_func(*args, **kwargs)
            await self.commit_checkpoint(checkpoint)
            return result
        except Exception as e:
            await self.rollback_to_checkpoint(checkpoint)
            raise MigrationError(f"Migration failed: {e}") from e
```

### WebSocket Architecture

#### Real-time Communication Design
```python
class WebSocketArchitecture:
    def __init__(self):
        self.connection_manager = WebSocketConnectionManager()
        self.message_router = MessageRouter()
        self.session_tracker = SessionTracker()
    
    async def handle_detection_websocket(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        
        try:
            # Register connection
            await self.connection_manager.register(websocket, session_id)
            
            # Handle incoming messages
            async for message in websocket.iter_text():
                await self.message_router.route_message(
                    websocket, session_id, json.loads(message)
                )
        
        except WebSocketDisconnect:
            await self.connection_manager.unregister(websocket, session_id)
        except Exception as e:
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': str(e)
            }))
            await websocket.close()

class WebSocketConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_connections: Dict[str, Set[WebSocket]] = {}
    
    async def register(self, websocket: WebSocket, session_id: str):
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        
        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()
        self.session_connections[session_id].add(websocket)
    
    async def broadcast_to_session(self, session_id: str, message: dict):
        if session_id in self.session_connections:
            for websocket in self.session_connections[session_id]:
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    # Remove broken connections
                    self.session_connections[session_id].discard(websocket)

class MessageRouter:
    async def route_message(self, websocket: WebSocket, session_id: str, message: dict):
        message_type = message.get('type')
        
        handlers = {
            'ping': self.handle_ping,
            'pause_detection': self.handle_pause,
            'resume_detection': self.handle_resume,
            'stop_detection': self.handle_stop,
            'get_progress': self.handle_get_progress
        }
        
        handler = handlers.get(message_type)
        if handler:
            await handler(websocket, session_id, message)
        else:
            await websocket.send_text(json.dumps({
                'type': 'error',
                'message': f'Unknown message type: {message_type}'
            }))
```

### Performance and Scalability Architecture

#### Caching Strategy
```python
class CachingArchitecture:
    def __init__(self):
        self.redis_client = redis.Redis()
        self.memory_cache = TTLCache(maxsize=1000, ttl=300)
        self.cache_strategies = {
            'session_stats': SessionStatsCacheStrategy(),
            'video_metadata': VideoMetadataCacheStrategy(),
            'detection_results': DetectionResultsCacheStrategy()
        }
    
    async def get_or_compute(self, cache_key: str, compute_func, ttl: int = 300):
        # Try memory cache first
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]
        
        # Try Redis cache
        cached_value = await self.redis_client.get(cache_key)
        if cached_value:
            value = json.loads(cached_value)
            self.memory_cache[cache_key] = value
            return value
        
        # Compute and cache
        value = await compute_func()
        await self.cache_value(cache_key, value, ttl)
        return value
    
    async def cache_value(self, key: str, value: any, ttl: int):
        # Cache in memory
        self.memory_cache[key] = value
        
        # Cache in Redis
        await self.redis_client.setex(
            key, ttl, json.dumps(value, default=str)
        )

class SessionStatsCacheStrategy:
    async def get_cache_key(self, session_id: str) -> str:
        return f"session_stats:{session_id}"
    
    async def compute_stats(self, session_id: str) -> dict:
        # Expensive computation to aggregate session statistics
        detections = await query_detection_events(session_id)
        annotations = await query_annotations(session_id)
        
        return {
            'total_detections': len(detections),
            'total_annotations': len(annotations),
            'by_type': self.aggregate_by_type(detections + annotations),
            'accuracy_metrics': await self.calculate_accuracy(session_id)
        }
```

#### Load Balancing and Scaling
```python
class ScalingArchitecture:
    def __init__(self):
        self.task_queue = AsyncTaskQueue()
        self.worker_pool = WorkerPool(max_workers=4)
        self.load_balancer = DetectionLoadBalancer()
    
    async def distribute_detection_task(self, video_id: str, config: dict):
        # Determine optimal worker based on current load
        worker = await self.load_balancer.select_worker()
        
        # Create detection task
        task = DetectionTask(
            video_id=video_id,
            config=config,
            worker_id=worker.id
        )
        
        # Queue task for processing
        await self.task_queue.enqueue(task)
        
        return task.id
    
    async def scale_workers_based_on_load(self):
        current_load = await self.get_current_load()
        
        if current_load > 0.8:  # Scale up
            await self.worker_pool.add_worker()
        elif current_load < 0.3:  # Scale down
            await self.worker_pool.remove_worker()

class DetectionLoadBalancer:
    def __init__(self):
        self.workers = {}
        self.load_metrics = {}
    
    async def select_worker(self) -> WorkerInfo:
        # Round-robin with load consideration
        available_workers = [
            worker for worker in self.workers.values()
            if worker.status == 'available'
        ]
        
        if not available_workers:
            # Create new worker if possible
            return await self.create_worker()
        
        # Select worker with lowest load
        return min(available_workers, key=lambda w: w.current_load)
```

### Error Handling and Resilience Architecture

#### Circuit Breaker Pattern
```python
class CircuitBreakerArchitecture:
    def __init__(self):
        self.circuit_breakers = {
            'video_processing': CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=30,
                expected_exception=VideoProcessingError
            ),
            'detection_api': CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=60,
                expected_exception=DetectionAPIError
            )
        }
    
    async def call_with_circuit_breaker(self, service: str, func, *args, **kwargs):
        circuit_breaker = self.circuit_breakers.get(service)
        if not circuit_breaker:
            return await func(*args, **kwargs)
        
        return await circuit_breaker.call(func, *args, **kwargs)

class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_timeout: int, expected_exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if self.should_attempt_reset():
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            await self.on_success()
            return result
        except self.expected_exception as e:
            await self.on_failure()
            raise e
    
    async def on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    async def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

### Security Architecture

#### Authentication and Authorization
```python
class SecurityArchitecture:
    def __init__(self):
        self.auth_manager = AuthenticationManager()
        self.authz_manager = AuthorizationManager()
        self.session_manager = SecureSessionManager()
    
    async def authenticate_websocket(self, websocket: WebSocket, token: str):
        try:
            user = await self.auth_manager.verify_token(token)
            await self.session_manager.create_websocket_session(websocket, user)
            return user
        except AuthenticationError:
            await websocket.close(code=1008, reason="Authentication failed")
            return None
    
    async def authorize_detection_access(self, user_id: str, video_id: str):
        # Check if user has access to the video and its project
        video = await get_video(video_id)
        if not video:
            raise NotFoundError("Video not found")
        
        project_access = await self.authz_manager.check_project_access(
            user_id, video.project_id
        )
        
        if not project_access:
            raise AuthorizationError("Access denied to video")
        
        return True

class AuthorizationManager:
    async def check_project_access(self, user_id: str, project_id: str) -> bool:
        # Implementation for project-based authorization
        user_permissions = await self.get_user_permissions(user_id)
        project_permissions = await self.get_project_permissions(project_id)
        
        return self.evaluate_permissions(user_permissions, project_permissions)
```

### Monitoring and Observability Architecture

#### Metrics and Logging
```python
class ObservabilityArchitecture:
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.logger = StructuredLogger()
        self.tracer = DistributedTracer()
    
    async def track_detection_performance(self, session_id: str, metrics: dict):
        await self.metrics_collector.record({
            'detection.session.duration': metrics['duration'],
            'detection.session.frames_processed': metrics['frames_processed'],
            'detection.session.detections_found': metrics['detections_found'],
            'detection.session.accuracy': metrics['accuracy']
        }, tags={'session_id': session_id})
    
    async def log_system_event(self, event_type: str, data: dict):
        await self.logger.info(event_type, {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'data': data,
            'trace_id': self.tracer.get_current_trace_id()
        })

class MetricsCollector:
    def __init__(self):
        self.metrics_backend = PrometheusMetrics()
    
    async def record(self, metrics: dict, tags: dict = None):
        for metric_name, value in metrics.items():
            await self.metrics_backend.record_gauge(
                metric_name, value, tags or {}
            )
```

This architecture provides a comprehensive foundation for implementing all the fixes identified in the SPARC specification and pseudocode phases, with proper separation of concerns, scalability considerations, and robust error handling.