# Backend Architecture Blueprint: AI Model Validation Platform

## Executive Summary

This architectural blueprint provides a comprehensive design for enhancing the AI Model Validation Platform's backend with five critical subsystems: Annotation Management, Enhanced WebSocket Architecture, Real-time Detection Pipeline, Project-Video Relationship Management, and Export/Import Service Layer.

## Current Architecture Analysis

### Strengths
1. **Well-structured FastAPI application** with proper separation of concerns
2. **Comprehensive SQLAlchemy models** with appropriate indexes and relationships
3. **Service layer architecture** with specialized services for different domains
4. **Real-time capabilities** via Socket.IO integration
5. **Robust error handling** and logging throughout the application

### Gaps Identified
1. **Missing annotation management** for temporal video annotations
2. **Limited WebSocket scalability** for multi-user real-time scenarios
3. **Lack of advanced detection pipeline** orchestration
4. **Basic project-video relationships** without intelligent matching
5. **No export/import capabilities** for data portability

## Proposed Architecture

### 1. Annotation Management System

#### 1.1 Database Schema Extensions

```sql
-- Temporal annotation tables
CREATE TABLE annotation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    annotator_id VARCHAR(36) DEFAULT 'anonymous',
    session_name VARCHAR(255) NOT NULL,
    annotation_type VARCHAR(50) NOT NULL, -- 'temporal', 'spatial', 'behavioral'
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'completed', 'paused'
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP NULL,
    metadata JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE video_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    annotation_session_id UUID NOT NULL REFERENCES annotation_sessions(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    start_timestamp DOUBLE PRECISION NOT NULL,
    end_timestamp DOUBLE PRECISION NOT NULL,
    annotation_type VARCHAR(50) NOT NULL,
    class_label VARCHAR(100) NOT NULL,
    bounding_box JSON NULL, -- For spatial annotations
    confidence DOUBLE PRECISION DEFAULT 1.0,
    annotator_notes TEXT,
    keyframe_data JSON DEFAULT '{}',
    validation_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'validated', 'rejected'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE annotation_keyframes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    annotation_id UUID NOT NULL REFERENCES video_annotations(id) ON DELETE CASCADE,
    frame_number INTEGER NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    frame_data JSON NOT NULL, -- Stores detection/annotation data for this frame
    screenshot_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_annotation_sessions_project_video ON annotation_sessions(project_id, video_id);
CREATE INDEX idx_video_annotations_session_time ON video_annotations(annotation_session_id, start_timestamp);
CREATE INDEX idx_annotation_keyframes_annotation_frame ON annotation_keyframes(annotation_id, frame_number);
```

#### 1.2 Pydantic Schemas

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class AnnotationType(str, Enum):
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    BEHAVIORAL = "behavioral"

class AnnotationStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"

class ValidationStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"

class AnnotationSessionCreate(BaseModel):
    project_id: str
    video_id: str
    session_name: str
    annotation_type: AnnotationType
    metadata: Optional[Dict[str, Any]] = {}

class AnnotationSessionResponse(BaseModel):
    id: str
    project_id: str
    video_id: str
    session_name: str
    annotation_type: AnnotationType
    status: AnnotationStatus
    start_time: datetime
    end_time: Optional[datetime]
    metadata: Dict[str, Any]
    annotation_count: int = 0

class VideoAnnotationCreate(BaseModel):
    annotation_session_id: str
    video_id: str
    start_timestamp: float
    end_timestamp: float
    annotation_type: str
    class_label: str
    bounding_box: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    annotator_notes: Optional[str] = None
    keyframe_data: Optional[Dict[str, Any]] = {}

class KeyframeCreate(BaseModel):
    annotation_id: str
    frame_number: int
    timestamp: float
    frame_data: Dict[str, Any]
    screenshot_path: Optional[str] = None
```

#### 1.3 Service Layer

```python
class AnnotationManagementService:
    """Comprehensive annotation management with temporal awareness"""
    
    def __init__(self):
        self.temporal_processor = TemporalAnnotationProcessor()
        self.validation_engine = AnnotationValidationEngine()
        self.export_manager = AnnotationExportManager()
    
    async def create_annotation_session(self, session_data: AnnotationSessionCreate) -> str:
        """Create new annotation session with validation"""
        pass
    
    async def add_temporal_annotation(self, annotation: VideoAnnotationCreate) -> str:
        """Add temporal annotation with keyframe extraction"""
        pass
    
    async def validate_annotation(self, annotation_id: str, validator_id: str) -> bool:
        """Validate annotation quality and consistency"""
        pass
    
    async def export_annotations(self, session_id: str, format: str = "coco") -> bytes:
        """Export annotations in various formats (COCO, YOLO, etc.)"""
        pass
```

### 2. Enhanced WebSocket Architecture

#### 2.1 Scalable WebSocket Infrastructure

```python
import socketio
from typing import Dict, Set
import redis.asyncio as redis
from contextlib import asynccontextmanager

class ScalableSocketIOManager:
    """Enhanced WebSocket manager with Redis pub/sub for horizontal scaling"""
    
    def __init__(self):
        # Redis for cross-instance communication
        self.redis_client = None
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins=['*'],  # Configure appropriately for production
            logger=True,
            client_manager=socketio.AsyncRedisManager('redis://redis:6379')
        )
        
        # Room management
        self.user_rooms: Dict[str, Set[str]] = {}
        self.project_subscribers: Dict[str, Set[str]] = {}
        self.annotation_collaborators: Dict[str, Set[str]] = {}
    
    async def initialize(self):
        """Initialize Redis connections and setup handlers"""
        self.redis_client = redis.from_url('redis://redis:6379')
        await self.setup_event_handlers()
    
    async def setup_event_handlers(self):
        """Setup comprehensive WebSocket event handlers"""
        
        @self.sio.event
        async def connect(sid, environ, auth):
            """Enhanced connection handler with authentication"""
            user_id = auth.get('user_id', 'anonymous') if auth else 'anonymous'
            project_id = auth.get('project_id') if auth else None
            
            # Store user context
            await self.sio.save_session(sid, {
                'user_id': user_id,
                'project_id': project_id,
                'connected_at': datetime.utcnow().isoformat()
            })
            
            # Join relevant rooms
            if project_id:
                await self.join_project_room(sid, project_id)
            
            await self.emit_connection_status(sid, 'connected')
        
        @self.sio.event
        async def join_annotation_session(sid, data):
            """Join collaborative annotation session"""
            session_id = data.get('session_id')
            if session_id:
                await self.sio.enter_room(sid, f"annotation_{session_id}")
                await self.broadcast_user_joined_annotation(session_id, sid)
        
        @self.sio.event
        async def real_time_annotation(sid, data):
            """Handle real-time annotation updates"""
            session_id = data.get('session_id')
            annotation_data = data.get('annotation')
            
            # Broadcast to other collaborators
            await self.sio.emit('annotation_update', {
                'session_id': session_id,
                'annotation': annotation_data,
                'from_user': (await self.sio.get_session(sid)).get('user_id')
            }, room=f"annotation_{session_id}", skip_sid=sid)
        
        @self.sio.event
        async def detection_stream_subscribe(sid, data):
            """Subscribe to real-time detection stream"""
            test_session_id = data.get('test_session_id')
            if test_session_id:
                await self.sio.enter_room(sid, f"detection_stream_{test_session_id}")
```

#### 2.2 Real-time Event Broadcasting

```python
class EventBroadcastService:
    """Centralized event broadcasting for real-time updates"""
    
    def __init__(self, socketio_manager: ScalableSocketIOManager):
        self.sio = socketio_manager
    
    async def broadcast_detection_event(self, test_session_id: str, detection_data: Dict):
        """Broadcast real-time detection events"""
        await self.sio.sio.emit('detection_event', {
            'test_session_id': test_session_id,
            'detection': detection_data,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f"detection_stream_{test_session_id}")
    
    async def broadcast_annotation_validation(self, annotation_id: str, validation_result: Dict):
        """Broadcast annotation validation results"""
        await self.sio.sio.emit('annotation_validated', {
            'annotation_id': annotation_id,
            'validation': validation_result
        }, room=f"annotation_{annotation_id}")
    
    async def broadcast_project_progress(self, project_id: str, progress_data: Dict):
        """Broadcast project progress updates"""
        await self.sio.sio.emit('project_progress_update', {
            'project_id': project_id,
            'progress': progress_data
        }, room=f"project_{project_id}")
```

### 3. Real-time Detection Pipeline

#### 3.1 Pipeline Architecture

```python
from dataclasses import dataclass
from typing import AsyncGenerator
import asyncio
from concurrent.futures import ThreadPoolExecutor

@dataclass
class PipelineConfig:
    model_name: str = "yolov8n"
    confidence_threshold: float = 0.7
    nms_threshold: float = 0.45
    batch_size: int = 8
    max_queue_size: int = 50
    enable_tracking: bool = True
    enable_analytics: bool = True

class RealTimeDetectionPipeline:
    """Enhanced real-time detection pipeline with streaming capabilities"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.detection_queue = asyncio.Queue(maxsize=config.max_queue_size)
        self.result_queue = asyncio.Queue()
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Pipeline components
        self.frame_preprocessor = FramePreprocessor()
        self.model_inference = ModelInferenceEngine(config.model_name)
        self.post_processor = DetectionPostProcessor()
        self.tracker = ObjectTracker() if config.enable_tracking else None
        self.analytics = DetectionAnalytics() if config.enable_analytics else None
    
    async def start_pipeline(self, video_path: str, test_session_id: str) -> AsyncGenerator[Dict, None]:
        """Start real-time detection pipeline"""
        self.is_running = True
        
        # Start pipeline workers
        workers = [
            asyncio.create_task(self._frame_reader_worker(video_path)),
            asyncio.create_task(self._detection_worker()),
            asyncio.create_task(self._result_processor_worker(test_session_id))
        ]
        
        try:
            # Yield results as they become available
            async for result in self._result_generator():
                yield result
        finally:
            self.is_running = False
            for worker in workers:
                worker.cancel()
    
    async def _frame_reader_worker(self, video_path: str):
        """Worker to read and preprocess video frames"""
        import cv2
        
        cap = cv2.VideoCapture(video_path)
        frame_number = 0
        
        while self.is_running and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_number += 1
            
            # Preprocess frame
            processed_frame = await self.frame_preprocessor.process(frame)
            
            # Add to detection queue
            try:
                await asyncio.wait_for(
                    self.detection_queue.put({
                        'frame': processed_frame,
                        'frame_number': frame_number,
                        'timestamp': frame_number / cap.get(cv2.CAP_PROP_FPS)
                    }),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                # Drop frame if queue is full
                continue
        
        cap.release()
    
    async def _detection_worker(self):
        """Worker to perform ML inference"""
        batch = []
        
        while self.is_running:
            try:
                # Collect frames for batch processing
                frame_data = await asyncio.wait_for(
                    self.detection_queue.get(), 
                    timeout=0.1
                )
                batch.append(frame_data)
                
                if len(batch) >= self.config.batch_size:
                    # Process batch
                    results = await self._process_batch(batch)
                    
                    # Add results to output queue
                    for result in results:
                        await self.result_queue.put(result)
                    
                    batch = []
                    
            except asyncio.TimeoutError:
                if batch:  # Process partial batch
                    results = await self._process_batch(batch)
                    for result in results:
                        await self.result_queue.put(result)
                    batch = []
    
    async def _process_batch(self, batch: List[Dict]) -> List[Dict]:
        """Process batch of frames through ML pipeline"""
        # Run inference in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        
        detection_results = await loop.run_in_executor(
            self.executor,
            self._run_inference_sync,
            [item['frame'] for item in batch]
        )
        
        # Post-process results
        processed_results = []
        for i, detections in enumerate(detection_results):
            frame_info = batch[i]
            
            # Apply confidence filtering and NMS
            filtered_detections = self.post_processor.filter_detections(
                detections, 
                self.config.confidence_threshold,
                self.config.nms_threshold
            )
            
            # Apply tracking if enabled
            if self.tracker:
                tracked_detections = self.tracker.update_tracks(
                    filtered_detections,
                    frame_info['frame_number']
                )
            else:
                tracked_detections = filtered_detections
            
            processed_results.append({
                'frame_number': frame_info['frame_number'],
                'timestamp': frame_info['timestamp'],
                'detections': tracked_detections,
                'processing_metadata': {
                    'detection_count': len(tracked_detections),
                    'confidence_avg': np.mean([d.confidence for d in tracked_detections]) if tracked_detections else 0
                }
            })
        
        return processed_results
```

### 4. Project-Video Relationship Management

#### 4.1 Enhanced Database Schema

```sql
-- Enhanced project-video relationships
CREATE TABLE project_video_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    assignment_type VARCHAR(20) DEFAULT 'automatic', -- 'automatic', 'manual', 'intelligent'
    compatibility_score DOUBLE PRECISION DEFAULT 0.0,
    assignment_reason TEXT,
    assigned_by VARCHAR(36) DEFAULT 'system',
    assigned_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'inactive', 'archived'
    metadata JSON DEFAULT '{}',
    
    UNIQUE(project_id, video_id)
);

CREATE TABLE video_compatibility_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    compatibility_vector JSON NOT NULL, -- Cached compatibility features
    last_updated TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(video_id)
);

CREATE TABLE project_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirement_type VARCHAR(50) NOT NULL, -- 'resolution', 'duration', 'scene_type', etc.
    requirement_value JSON NOT NULL,
    weight DOUBLE PRECISION DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_project_video_assignments_project ON project_video_assignments(project_id);
CREATE INDEX idx_project_video_assignments_compatibility ON project_video_assignments(compatibility_score DESC);
CREATE INDEX idx_video_compatibility_cache_updated ON video_compatibility_cache(last_updated);
```

#### 4.2 Intelligent Assignment Service

```python
class IntelligentProjectVideoManager:
    """AI-powered project-video relationship management"""
    
    def __init__(self):
        self.compatibility_engine = VideoCompatibilityEngine()
        self.assignment_optimizer = AssignmentOptimizer()
        self.analytics_engine = AssignmentAnalyticsEngine()
    
    async def analyze_video_compatibility(self, video_id: str) -> Dict:
        """Analyze video characteristics for intelligent assignment"""
        db = SessionLocal()
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            # Extract video features
            features = await self._extract_video_features(video)
            
            # Cache compatibility vector
            await self._cache_compatibility_vector(video_id, features)
            
            return features
            
        finally:
            db.close()
    
    async def find_optimal_assignments(self, project_id: str, candidate_videos: List[str] = None) -> List[Dict]:
        """Find optimal video assignments for project using ML"""
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Get candidate videos
            if candidate_videos is None:
                candidate_videos = [v.id for v in db.query(Video).filter(Video.project_id.is_(None)).all()]
            
            # Calculate compatibility scores
            assignments = []
            for video_id in candidate_videos:
                score = await self.compatibility_engine.calculate_compatibility(project_id, video_id)
                
                if score > 0.6:  # Minimum compatibility threshold
                    assignment = {
                        'video_id': video_id,
                        'project_id': project_id,
                        'compatibility_score': score,
                        'assignment_reason': await self._generate_assignment_reason(project_id, video_id, score),
                        'confidence': self._calculate_assignment_confidence(score)
                    }
                    assignments.append(assignment)
            
            # Optimize assignments using constraint solver
            optimized_assignments = await self.assignment_optimizer.optimize(assignments, project)
            
            return optimized_assignments
            
        finally:
            db.close()
    
    async def execute_intelligent_assignment(self, assignment_data: Dict) -> bool:
        """Execute intelligent video assignment with tracking"""
        db = SessionLocal()
        try:
            assignment = ProjectVideoAssignment(
                project_id=assignment_data['project_id'],
                video_id=assignment_data['video_id'],
                assignment_type='intelligent',
                compatibility_score=assignment_data['compatibility_score'],
                assignment_reason=assignment_data['assignment_reason'],
                assigned_by='ai_system',
                metadata={
                    'confidence': assignment_data.get('confidence', 0.5),
                    'algorithm_version': '1.0',
                    'features_used': assignment_data.get('features', [])
                }
            )
            
            db.add(assignment)
            
            # Update video project relationship
            video = db.query(Video).filter(Video.id == assignment_data['video_id']).first()
            if video:
                video.project_id = assignment_data['project_id']
            
            db.commit()
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to execute assignment: {str(e)}")
            return False
        finally:
            db.close()
```

### 5. Export/Import Service Layer

#### 5.1 Database Schema for Data Portability

```sql
-- Export/Import tracking
CREATE TABLE export_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(255) NOT NULL,
    export_type VARCHAR(50) NOT NULL, -- 'project', 'annotations', 'results', 'full'
    format VARCHAR(20) NOT NULL, -- 'json', 'csv', 'coco', 'yolo'
    scope_filter JSON DEFAULT '{}', -- What to export
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    progress_percent INTEGER DEFAULT 0,
    file_path VARCHAR(500),
    file_size BIGINT,
    download_count INTEGER DEFAULT 0,
    created_by VARCHAR(36) DEFAULT 'anonymous',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    expires_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE import_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(255) NOT NULL,
    import_type VARCHAR(50) NOT NULL, -- 'project', 'annotations', 'results'
    source_format VARCHAR(20) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    validation_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'valid', 'invalid'
    import_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    progress_percent INTEGER DEFAULT 0,
    records_processed INTEGER DEFAULT 0,
    records_total INTEGER DEFAULT 0,
    validation_errors JSON DEFAULT '[]',
    import_errors JSON DEFAULT '[]',
    created_by VARCHAR(36) DEFAULT 'anonymous',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Indexes
CREATE INDEX idx_export_jobs_status_created ON export_jobs(status, created_at);
CREATE INDEX idx_import_jobs_status_created ON import_jobs(status, created_at);
```

#### 5.2 Export/Import Service Implementation

```python
class DataPortabilityService:
    """Comprehensive data export/import service with multiple formats"""
    
    def __init__(self):
        self.export_engines = {
            'json': JSONExportEngine(),
            'csv': CSVExportEngine(),
            'coco': COCOExportEngine(),
            'yolo': YOLOExportEngine()
        }
        self.import_engines = {
            'json': JSONImportEngine(),
            'csv': CSVImportEngine(),
            'coco': COCOImportEngine(),
            'yolo': YOLOImportEngine()
        }
        self.validation_service = DataValidationService()
    
    async def create_export_job(self, job_config: Dict) -> str:
        """Create new export job with background processing"""
        db = SessionLocal()
        try:
            export_job = ExportJob(
                job_name=job_config['job_name'],
                export_type=job_config['export_type'],
                format=job_config['format'],
                scope_filter=job_config.get('scope_filter', {}),
                created_by=job_config.get('user_id', 'anonymous'),
                expires_at=datetime.utcnow() + timedelta(days=7)  # 7-day expiration
            )
            
            db.add(export_job)
            db.commit()
            db.refresh(export_job)
            
            # Start background export task
            asyncio.create_task(self._process_export_job(export_job.id))
            
            return export_job.id
            
        finally:
            db.close()
    
    async def _process_export_job(self, job_id: str):
        """Background task to process export job"""
        db = SessionLocal()
        try:
            job = db.query(ExportJob).filter(ExportJob.id == job_id).first()
            if not job:
                return
            
            # Update status to processing
            job.status = 'processing'
            db.commit()
            
            # Get export engine
            engine = self.export_engines.get(job.format)
            if not engine:
                raise ValueError(f"Unsupported export format: {job.format}")
            
            # Process export based on type
            if job.export_type == 'project':
                data = await self._export_project_data(job.scope_filter)
            elif job.export_type == 'annotations':
                data = await self._export_annotation_data(job.scope_filter)
            elif job.export_type == 'results':
                data = await self._export_results_data(job.scope_filter)
            else:
                raise ValueError(f"Unsupported export type: {job.export_type}")
            
            # Generate export file
            export_file_path = await engine.generate_export_file(data, job_id)
            
            # Update job with completion info
            job.status = 'completed'
            job.file_path = export_file_path
            job.file_size = Path(export_file_path).stat().st_size
            job.completed_at = datetime.utcnow()
            job.progress_percent = 100
            
            db.commit()
            
        except Exception as e:
            # Update job with error status
            job.status = 'failed'
            job.error_message = str(e)
            db.commit()
            logger.error(f"Export job {job_id} failed: {str(e)}")
            
        finally:
            db.close()
    
    async def validate_import_file(self, file_path: str, format: str, import_type: str) -> Dict:
        """Validate import file before processing"""
        validator = self.validation_service.get_validator(format, import_type)
        return await validator.validate_file(file_path)
    
    async def create_import_job(self, job_config: Dict) -> str:
        """Create new import job with validation"""
        # First validate the file
        validation_result = await self.validate_import_file(
            job_config['file_path'],
            job_config['source_format'],
            job_config['import_type']
        )
        
        db = SessionLocal()
        try:
            import_job = ImportJob(
                job_name=job_config['job_name'],
                import_type=job_config['import_type'],
                source_format=job_config['source_format'],
                file_path=job_config['file_path'],
                validation_status='valid' if validation_result['is_valid'] else 'invalid',
                validation_errors=validation_result.get('errors', []),
                records_total=validation_result.get('total_records', 0),
                created_by=job_config.get('user_id', 'anonymous')
            )
            
            db.add(import_job)
            db.commit()
            db.refresh(import_job)
            
            # Start background import if validation passed
            if validation_result['is_valid']:
                asyncio.create_task(self._process_import_job(import_job.id))
            
            return import_job.id
            
        finally:
            db.close()
```

## API Endpoint Specifications

### Annotation Management Endpoints

```python
# FastAPI endpoint definitions
@app.post("/api/annotations/sessions", response_model=AnnotationSessionResponse)
async def create_annotation_session(session: AnnotationSessionCreate, db: Session = Depends(get_db)):
    """Create new annotation session"""
    pass

@app.post("/api/annotations/temporal", response_model=VideoAnnotationResponse)
async def add_temporal_annotation(annotation: VideoAnnotationCreate, db: Session = Depends(get_db)):
    """Add temporal video annotation"""
    pass

@app.get("/api/annotations/sessions/{session_id}/export/{format}")
async def export_annotations(session_id: str, format: str = "coco"):
    """Export annotations in specified format"""
    pass

@app.websocket("/ws/annotations/{session_id}")
async def annotation_collaboration_websocket(websocket: WebSocket, session_id: str):
    """WebSocket for real-time annotation collaboration"""
    pass
```

### Project-Video Management Endpoints

```python
@app.post("/api/projects/{project_id}/assignments/intelligent")
async def create_intelligent_assignments(project_id: str, db: Session = Depends(get_db)):
    """Generate intelligent video assignments for project"""
    pass

@app.get("/api/projects/{project_id}/assignments/analysis")
async def analyze_assignment_quality(project_id: str, db: Session = Depends(get_db)):
    """Analyze quality of current video assignments"""
    pass

@app.post("/api/videos/{video_id}/compatibility/analyze")
async def analyze_video_compatibility(video_id: str):
    """Analyze video compatibility characteristics"""
    pass
```

### Export/Import Endpoints

```python
@app.post("/api/export/jobs", response_model=ExportJobResponse)
async def create_export_job(job_config: ExportJobCreate, db: Session = Depends(get_db)):
    """Create new export job"""
    pass

@app.get("/api/export/jobs/{job_id}/download")
async def download_export_file(job_id: str):
    """Download completed export file"""
    pass

@app.post("/api/import/jobs", response_model=ImportJobResponse)  
async def create_import_job(job_config: ImportJobCreate, db: Session = Depends(get_db)):
    """Create new import job"""
    pass

@app.get("/api/import/jobs/{job_id}/status")
async def get_import_job_status(job_id: str):
    """Get import job status and progress"""
    pass
```

## Performance and Scalability Considerations

### Database Optimizations
1. **Composite indexes** on frequently queried column combinations
2. **Partitioning** for large tables (annotations, detection_events)
3. **Connection pooling** with appropriate pool sizes
4. **Read replicas** for analytics and reporting queries

### Caching Strategy
1. **Redis caching** for frequently accessed data
2. **Application-level caching** for compatibility calculations
3. **CDN integration** for static assets and export files
4. **Query result caching** for expensive operations

### Horizontal Scaling
1. **Microservices decomposition** for independent scaling
2. **Message queue integration** (Redis/RabbitMQ) for async processing
3. **Load balancer configuration** for WebSocket scaling
4. **Container orchestration** with Kubernetes

## Security and Compliance

### Data Protection
1. **Encryption at rest** for sensitive video data
2. **Encrypted file transfers** for import/export operations
3. **Access control** with role-based permissions
4. **Audit logging** for all data operations

### API Security
1. **JWT authentication** for API endpoints
2. **Rate limiting** to prevent abuse
3. **Input validation** for all user inputs
4. **CORS configuration** for browser security

## Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- Database schema extensions
- Basic annotation management service
- Enhanced WebSocket infrastructure

### Phase 2: Core Features (Weeks 3-4)
- Real-time detection pipeline
- Intelligent assignment system
- Basic export functionality

### Phase 3: Advanced Features (Weeks 5-6)
- Collaborative annotation tools
- Advanced analytics and reporting
- Import functionality and validation

### Phase 4: Optimization (Weeks 7-8)
- Performance tuning
- Scalability improvements
- Security hardening

## Conclusion

This architectural blueprint provides a comprehensive foundation for enhancing the AI Model Validation Platform with advanced annotation management, real-time capabilities, intelligent project-video relationships, and robust data portability. The design emphasizes scalability, performance, and maintainability while building upon the existing solid foundation.

The modular architecture allows for incremental implementation and provides clear separation of concerns, making the system easier to maintain and extend in the future.