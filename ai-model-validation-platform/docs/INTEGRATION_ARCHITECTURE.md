# Integration Architecture & Data Flow

## Overview

This document defines comprehensive integration patterns and data flow architecture for the AI Model Validation Platform, ensuring seamless integration between annotation, ground truth, validation, and existing project/video APIs.

## 1. INTEGRATION PATTERNS

### 1.1 Service Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INTEGRATION LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Event     │    │   Message   │    │   Service   │             │
│  │    Bus      │◄──►│    Queue    │◄──►│ Orchestrator│             │
│  │   (Redis)   │    │ (RabbitMQ)  │    │             │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│           ▲                 ▲                  ▲                    │
│           │                 │                  │                    │
├───────────┼─────────────────┼──────────────────┼────────────────────┤
│  SERVICE LAYER              │                  │                    │
│           │                 │                  │                    │
│  ┌────────▼───┐  ┌──────────▼─┐  ┌────────────▼─┐  ┌─────────────┐ │
│  │ Project    │  │ Video      │  │ Annotation   │  │ Ground      │ │
│  │ Service    │  │ Service    │  │ Service      │  │ Truth Svc   │ │
│  └────────────┘  └────────────┘  └──────────────┘  └─────────────┘ │
│           │              │                │                │       │
│           ▼              ▼                ▼                ▼       │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐│
│  │ ML         │  │ Validation   │  │ Notification │  │ Audit       ││
│  │ Inference  │  │ Service      │  │ Service      │  │ Service     ││
│  └────────────┘  └──────────────┘  └──────────────┘  └─────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Event-Driven Integration Pattern

```python
# services/integration_orchestrator.py - Central Integration Orchestrator

import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging
import redis
import aioredis

logger = logging.getLogger(__name__)

class EventType(Enum):
    # Project Events
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"
    
    # Video Events
    VIDEO_UPLOADED = "video.uploaded"
    VIDEO_PROCESSED = "video.processed"
    VIDEO_DELETED = "video.deleted"
    
    # Ground Truth Events
    GROUND_TRUTH_GENERATED = "ground_truth.generated"
    GROUND_TRUTH_VALIDATED = "ground_truth.validated"
    
    # Annotation Events
    ANNOTATION_CREATED = "annotation.created"
    ANNOTATION_UPDATED = "annotation.updated"
    ANNOTATION_SESSION_STARTED = "annotation_session.started"
    ANNOTATION_SESSION_COMPLETED = "annotation_session.completed"
    
    # Test & Validation Events
    TEST_SESSION_STARTED = "test_session.started"
    TEST_SESSION_COMPLETED = "test_session.completed"
    VALIDATION_COMPLETED = "validation.completed"
    
    # ML Events
    ML_INFERENCE_STARTED = "ml_inference.started"
    ML_INFERENCE_COMPLETED = "ml_inference.completed"
    
    # System Events
    SYSTEM_ERROR = "system.error"
    RESOURCE_THRESHOLD = "resource.threshold"

@dataclass
class IntegrationEvent:
    """Integration event data structure"""
    event_type: EventType
    event_id: str
    source_service: str
    timestamp: datetime
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

class IntegrationOrchestrator:
    """Central service orchestrator for managing integrations"""
    
    def __init__(self):
        self.redis_client = None
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.service_registry: Dict[str, Dict] = {}
        self.circuit_breaker_states: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize orchestrator"""
        try:
            self.redis_client = await aioredis.from_url("redis://localhost:6379")
            await self._register_core_handlers()
            await self._initialize_circuit_breakers()
            logger.info("Integration orchestrator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise
    
    async def publish_event(self, event: IntegrationEvent):
        """Publish integration event"""
        try:
            # Serialize event
            event_data = {
                "event_type": event.event_type.value,
                "event_id": event.event_id,
                "source_service": event.source_service,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
                "correlation_id": event.correlation_id,
                "retry_count": event.retry_count
            }
            
            # Publish to Redis
            await self.redis_client.publish(
                f"integration_events:{event.event_type.value}",
                json.dumps(event_data)
            )
            
            # Store in event log
            await self._store_event_log(event)
            
            # Process immediate handlers
            await self._process_event_handlers(event)
            
            logger.info(f"Published event: {event.event_type.value} from {event.source_service}")
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            await self._handle_event_error(event, str(e))
    
    def subscribe_to_event(self, event_type: EventType, handler: Callable):
        """Subscribe handler to event type"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.info(f"Handler subscribed to {event_type.value}")
    
    async def register_service(self, service_name: str, service_config: Dict):
        """Register service in integration layer"""
        self.service_registry[service_name] = {
            **service_config,
            "registered_at": datetime.utcnow().isoformat(),
            "health_status": "unknown"
        }
        
        # Initialize circuit breaker for service
        self.circuit_breaker_states[service_name] = {
            "state": "closed",  # closed, open, half_open
            "failure_count": 0,
            "last_failure": None,
            "next_attempt": None
        }
        
        logger.info(f"Service registered: {service_name}")
    
    async def orchestrate_workflow(self, workflow_name: str, initial_data: Dict) -> str:
        """Orchestrate complex workflow across services"""
        
        correlation_id = f"workflow_{workflow_name}_{datetime.utcnow().timestamp()}"
        
        try:
            if workflow_name == "video_upload_processing":
                return await self._orchestrate_video_upload(initial_data, correlation_id)
            elif workflow_name == "annotation_validation":
                return await self._orchestrate_annotation_validation(initial_data, correlation_id)
            elif workflow_name == "test_session_execution":
                return await self._orchestrate_test_session(initial_data, correlation_id)
            else:
                raise ValueError(f"Unknown workflow: {workflow_name}")
                
        except Exception as e:
            logger.error(f"Workflow orchestration failed: {workflow_name} - {e}")
            await self._handle_workflow_error(workflow_name, correlation_id, str(e))
            raise
    
    async def _orchestrate_video_upload(self, data: Dict, correlation_id: str) -> str:
        """Orchestrate video upload and processing workflow"""
        
        try:
            # Step 1: Upload video file
            upload_event = IntegrationEvent(
                event_type=EventType.VIDEO_UPLOADED,
                event_id=f"upload_{correlation_id}",
                source_service="orchestrator",
                timestamp=datetime.utcnow(),
                payload=data,
                correlation_id=correlation_id
            )
            await self.publish_event(upload_event)
            
            # Step 2: Wait for video processing
            video_id = data.get("video_id")
            await self._wait_for_event_completion(
                f"video_processed_{video_id}", 
                timeout=300  # 5 minutes
            )
            
            # Step 3: Generate ground truth
            ground_truth_event = IntegrationEvent(
                event_type=EventType.GROUND_TRUTH_GENERATED,
                event_id=f"ground_truth_{correlation_id}",
                source_service="orchestrator",
                timestamp=datetime.utcnow(),
                payload={"video_id": video_id, "auto_generate": True},
                correlation_id=correlation_id
            )
            await self.publish_event(ground_truth_event)
            
            # Step 4: Initialize annotation session
            annotation_event = IntegrationEvent(
                event_type=EventType.ANNOTATION_SESSION_STARTED,
                event_id=f"annotation_{correlation_id}",
                source_service="orchestrator",
                timestamp=datetime.utcnow(),
                payload={
                    "video_id": video_id,
                    "project_id": data.get("project_id"),
                    "auto_start": True
                },
                correlation_id=correlation_id
            )
            await self.publish_event(annotation_event)
            
            return correlation_id
            
        except Exception as e:
            logger.error(f"Video upload orchestration failed: {e}")
            raise
    
    async def _orchestrate_annotation_validation(self, data: Dict, correlation_id: str) -> str:
        """Orchestrate annotation validation workflow"""
        
        try:
            # Step 1: Validate annotations
            validation_event = IntegrationEvent(
                event_type=EventType.VALIDATION_COMPLETED,
                event_id=f"validation_{correlation_id}",
                source_service="orchestrator",
                timestamp=datetime.utcnow(),
                payload=data,
                correlation_id=correlation_id
            )
            await self.publish_event(validation_event)
            
            # Step 2: Generate validation report
            await self._generate_validation_report(data, correlation_id)
            
            # Step 3: Update annotation status
            await self._update_annotation_status(data, correlation_id)
            
            return correlation_id
            
        except Exception as e:
            logger.error(f"Annotation validation orchestration failed: {e}")
            raise
    
    async def _process_event_handlers(self, event: IntegrationEvent):
        """Process event handlers for the event"""
        
        handlers = self.event_handlers.get(event.event_type, [])
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler failed: {handler.__name__} - {e}")
                await self._retry_handler(handler, event, str(e))
    
    async def _register_core_handlers(self):
        """Register core event handlers"""
        
        # Video processing handlers
        self.subscribe_to_event(EventType.VIDEO_UPLOADED, self._handle_video_uploaded)
        self.subscribe_to_event(EventType.VIDEO_PROCESSED, self._handle_video_processed)
        
        # Ground truth handlers
        self.subscribe_to_event(EventType.GROUND_TRUTH_GENERATED, self._handle_ground_truth_generated)
        
        # Annotation handlers
        self.subscribe_to_event(EventType.ANNOTATION_CREATED, self._handle_annotation_created)
        self.subscribe_to_event(EventType.ANNOTATION_SESSION_COMPLETED, self._handle_annotation_completed)
        
        # Test session handlers
        self.subscribe_to_event(EventType.TEST_SESSION_STARTED, self._handle_test_session_started)
        self.subscribe_to_event(EventType.TEST_SESSION_COMPLETED, self._handle_test_session_completed)
    
    async def _handle_video_uploaded(self, event: IntegrationEvent):
        """Handle video uploaded event"""
        
        video_data = event.payload
        video_id = video_data.get("video_id")
        
        logger.info(f"Processing video upload: {video_id}")
        
        # Trigger video processing
        from services.video_service import VideoService
        video_service = VideoService()
        
        await video_service.start_processing(video_id)
        
        # Send notification
        await self._send_notification(
            "video_upload_started",
            f"Video {video_id} upload processing started",
            video_data.get("user_id")
        )
    
    async def _handle_video_processed(self, event: IntegrationEvent):
        """Handle video processed event"""
        
        video_data = event.payload
        video_id = video_data.get("video_id")
        
        logger.info(f"Video processed: {video_id}")
        
        # Update video status
        from services.video_service import VideoService
        video_service = VideoService()
        
        await video_service.update_processing_status(video_id, "completed")
        
        # Trigger ground truth generation
        ground_truth_event = IntegrationEvent(
            event_type=EventType.GROUND_TRUTH_GENERATED,
            event_id=f"ground_truth_auto_{video_id}",
            source_service="video_service",
            timestamp=datetime.utcnow(),
            payload={"video_id": video_id, "auto_generate": True},
            correlation_id=event.correlation_id
        )
        await self.publish_event(ground_truth_event)


# Service Integration Patterns
class ServiceIntegrationPattern:
    """Base class for service integration patterns"""
    
    def __init__(self, orchestrator: IntegrationOrchestrator):
        self.orchestrator = orchestrator
    
    async def execute(self, data: Dict) -> Dict:
        """Execute integration pattern"""
        raise NotImplementedError


class ProjectVideoIntegration(ServiceIntegrationPattern):
    """Integration pattern for project-video relationships"""
    
    async def execute(self, data: Dict) -> Dict:
        """Execute project-video integration"""
        
        project_id = data.get("project_id")
        video_id = data.get("video_id")
        
        # Create video-project link
        from services.project_service import ProjectService
        project_service = ProjectService()
        
        result = await project_service.link_video_to_project(project_id, video_id)
        
        # Publish integration event
        event = IntegrationEvent(
            event_type=EventType.PROJECT_UPDATED,
            event_id=f"project_video_link_{project_id}_{video_id}",
            source_service="project_service",
            timestamp=datetime.utcnow(),
            payload={
                "project_id": project_id,
                "video_id": video_id,
                "action": "video_linked"
            }
        )
        
        await self.orchestrator.publish_event(event)
        
        return result


class AnnotationGroundTruthIntegration(ServiceIntegrationPattern):
    """Integration pattern for annotation-ground truth synchronization"""
    
    async def execute(self, data: Dict) -> Dict:
        """Execute annotation-ground truth integration"""
        
        video_id = data.get("video_id")
        annotation_data = data.get("annotation_data")
        
        # Synchronize annotation with ground truth
        from services.ground_truth_service import GroundTruthService
        from services.annotation_service import AnnotationService
        
        ground_truth_service = GroundTruthService()
        annotation_service = AnnotationService()
        
        # Create ground truth from annotation
        ground_truth = await ground_truth_service.create_from_annotation(
            video_id, annotation_data
        )
        
        # Update annotation status
        await annotation_service.update_validation_status(
            annotation_data.get("annotation_id"),
            "ground_truth_synced"
        )
        
        # Publish sync event
        event = IntegrationEvent(
            event_type=EventType.GROUND_TRUTH_VALIDATED,
            event_id=f"gt_annotation_sync_{video_id}",
            source_service="annotation_service",
            timestamp=datetime.utcnow(),
            payload={
                "video_id": video_id,
                "ground_truth_id": ground_truth.get("id"),
                "annotation_id": annotation_data.get("annotation_id")
            }
        )
        
        await self.orchestrator.publish_event(event)
        
        return ground_truth


class ValidationResultIntegration(ServiceIntegrationPattern):
    """Integration pattern for validation result processing"""
    
    async def execute(self, data: Dict) -> Dict:
        """Execute validation result integration"""
        
        test_session_id = data.get("test_session_id")
        validation_results = data.get("validation_results")
        
        # Process validation results
        from services.validation_service import ValidationService
        from services.test_session_service import TestSessionService
        
        validation_service = ValidationService()
        test_session_service = TestSessionService()
        
        # Store validation results
        result = await validation_service.store_validation_results(
            test_session_id, validation_results
        )
        
        # Update test session status
        await test_session_service.update_status(test_session_id, "completed")
        
        # Generate validation report
        report = await validation_service.generate_validation_report(test_session_id)
        
        # Publish completion event
        event = IntegrationEvent(
            event_type=EventType.VALIDATION_COMPLETED,
            event_id=f"validation_complete_{test_session_id}",
            source_service="validation_service",
            timestamp=datetime.utcnow(),
            payload={
                "test_session_id": test_session_id,
                "validation_results": result,
                "report_id": report.get("id")
            }
        )
        
        await self.orchestrator.publish_event(event)
        
        return {
            "validation_results": result,
            "report": report
        }
```

### 1.3 Data Synchronization Pattern

```python
# services/data_synchronization.py - Data Synchronization Service

import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class SyncType(Enum):
    REAL_TIME = "real_time"
    BATCH = "batch"
    SCHEDULED = "scheduled"
    EVENT_DRIVEN = "event_driven"

@dataclass
class SyncTask:
    """Data synchronization task"""
    id: str
    source_service: str
    target_service: str
    sync_type: SyncType
    data_type: str
    last_sync: Optional[datetime] = None
    next_sync: Optional[datetime] = None
    sync_interval: Optional[int] = None  # seconds
    is_active: bool = True

class DataSynchronizationService:
    """Service for managing data synchronization between components"""
    
    def __init__(self):
        self.sync_tasks: Dict[str, SyncTask] = {}
        self.sync_locks: Dict[str, asyncio.Lock] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
    
    async def initialize(self):
        """Initialize synchronization service"""
        
        # Register core synchronization tasks
        await self._register_core_sync_tasks()
        
        # Start scheduled synchronizations
        await self._start_scheduled_syncs()
        
        logger.info("Data synchronization service initialized")
    
    async def register_sync_task(self, sync_task: SyncTask):
        """Register new synchronization task"""
        
        self.sync_tasks[sync_task.id] = sync_task
        self.sync_locks[sync_task.id] = asyncio.Lock()
        
        # Start task if it's scheduled
        if sync_task.sync_type == SyncType.SCHEDULED and sync_task.is_active:
            await self._start_scheduled_task(sync_task)
        
        logger.info(f"Sync task registered: {sync_task.id}")
    
    async def execute_sync(self, task_id: str, force: bool = False) -> Dict:
        """Execute synchronization task"""
        
        if task_id not in self.sync_tasks:
            raise ValueError(f"Sync task not found: {task_id}")
        
        task = self.sync_tasks[task_id]
        
        # Check if task is already running
        if not force and task_id in self.running_tasks:
            return {"status": "already_running", "task_id": task_id}
        
        async with self.sync_locks[task_id]:
            try:
                logger.info(f"Starting sync task: {task_id}")
                
                # Execute sync based on data type
                if task.data_type == "annotations":
                    result = await self._sync_annotations(task)
                elif task.data_type == "ground_truth":
                    result = await self._sync_ground_truth(task)
                elif task.data_type == "validation_results":
                    result = await self._sync_validation_results(task)
                elif task.data_type == "project_metadata":
                    result = await self._sync_project_metadata(task)
                else:
                    raise ValueError(f"Unknown data type: {task.data_type}")
                
                # Update sync timestamp
                task.last_sync = datetime.utcnow()
                if task.sync_interval:
                    task.next_sync = task.last_sync + timedelta(seconds=task.sync_interval)
                
                logger.info(f"Sync task completed: {task_id}")
                
                return {
                    "status": "completed",
                    "task_id": task_id,
                    "result": result,
                    "last_sync": task.last_sync.isoformat()
                }
                
            except Exception as e:
                logger.error(f"Sync task failed: {task_id} - {e}")
                return {
                    "status": "failed",
                    "task_id": task_id,
                    "error": str(e)
                }
    
    async def _sync_annotations(self, task: SyncTask) -> Dict:
        """Synchronize annotation data"""
        
        from services.annotation_service import AnnotationService
        from services.ground_truth_service import GroundTruthService
        
        annotation_service = AnnotationService()
        ground_truth_service = GroundTruthService()
        
        # Get recent annotations
        since = task.last_sync or datetime.utcnow() - timedelta(hours=1)
        annotations = await annotation_service.get_annotations_since(since)
        
        sync_count = 0
        for annotation in annotations:
            # Sync with ground truth if validated
            if annotation.validated:
                await ground_truth_service.sync_from_annotation(annotation)
                sync_count += 1
        
        return {
            "annotations_processed": len(annotations),
            "annotations_synced": sync_count
        }
    
    async def _sync_ground_truth(self, task: SyncTask) -> Dict:
        """Synchronize ground truth data"""
        
        from services.ground_truth_service import GroundTruthService
        from services.validation_service import ValidationService
        
        ground_truth_service = GroundTruthService()
        validation_service = ValidationService()
        
        # Get recent ground truth updates
        since = task.last_sync or datetime.utcnow() - timedelta(hours=1)
        ground_truth_updates = await ground_truth_service.get_updates_since(since)
        
        sync_count = 0
        for gt_update in ground_truth_updates:
            # Update validation baselines
            await validation_service.update_baseline_from_ground_truth(gt_update)
            sync_count += 1
        
        return {
            "ground_truth_updates": len(ground_truth_updates),
            "baselines_updated": sync_count
        }
    
    async def _sync_validation_results(self, task: SyncTask) -> Dict:
        """Synchronize validation results"""
        
        from services.validation_service import ValidationService
        from services.project_service import ProjectService
        
        validation_service = ValidationService()
        project_service = ProjectService()
        
        # Get recent validation results
        since = task.last_sync or datetime.utcnow() - timedelta(hours=1)
        validation_results = await validation_service.get_results_since(since)
        
        sync_count = 0
        for result in validation_results:
            # Update project statistics
            await project_service.update_validation_statistics(
                result.project_id, result
            )
            sync_count += 1
        
        return {
            "validation_results": len(validation_results),
            "project_stats_updated": sync_count
        }
    
    async def _register_core_sync_tasks(self):
        """Register core synchronization tasks"""
        
        # Annotation-Ground Truth sync (real-time)
        await self.register_sync_task(SyncTask(
            id="annotation_ground_truth_sync",
            source_service="annotation_service",
            target_service="ground_truth_service",
            sync_type=SyncType.EVENT_DRIVEN,
            data_type="annotations"
        ))
        
        # Ground Truth-Validation sync (scheduled every 5 minutes)
        await self.register_sync_task(SyncTask(
            id="ground_truth_validation_sync",
            source_service="ground_truth_service",
            target_service="validation_service",
            sync_type=SyncType.SCHEDULED,
            data_type="ground_truth",
            sync_interval=300  # 5 minutes
        ))
        
        # Validation-Project sync (scheduled every 10 minutes)
        await self.register_sync_task(SyncTask(
            id="validation_project_sync",
            source_service="validation_service",
            target_service="project_service",
            sync_type=SyncType.SCHEDULED,
            data_type="validation_results",
            sync_interval=600  # 10 minutes
        ))
    
    async def _start_scheduled_syncs(self):
        """Start all scheduled synchronization tasks"""
        
        for task in self.sync_tasks.values():
            if task.sync_type == SyncType.SCHEDULED and task.is_active:
                await self._start_scheduled_task(task)
    
    async def _start_scheduled_task(self, task: SyncTask):
        """Start individual scheduled task"""
        
        async def scheduled_sync():
            while task.is_active:
                try:
                    await self.execute_sync(task.id)
                    
                    # Wait for next sync
                    if task.sync_interval:
                        await asyncio.sleep(task.sync_interval)
                    else:
                        break
                        
                except Exception as e:
                    logger.error(f"Scheduled sync error: {task.id} - {e}")
                    await asyncio.sleep(60)  # Wait 1 minute before retry
        
        # Start background task
        self.running_tasks[task.id] = asyncio.create_task(scheduled_sync())
```

## 2. DATA FLOW ARCHITECTURE

### 2.1 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────┐  1. Upload   ┌─────────────┐  2. Process  ┌─────────────────┐     │
│  │ Client  │─────────────►│ Video       │─────────────►│ ML Inference    │     │
│  │ (React) │              │ Service     │              │ Service         │     │
│  └─────────┘              └─────────────┘              └─────────────────┘     │
│       ▲                           │                              │             │
│       │                           │ 3. Store                     │ 4. Generate │
│       │                           ▼                              ▼             │
│       │                  ┌─────────────┐                ┌─────────────────┐    │
│       │                  │ Database    │◄───────────────│ Ground Truth    │    │
│       │                  │ (Postgres)  │  5. Store GT   │ Service         │    │
│       │                  └─────────────┘                └─────────────────┘    │
│       │                           ▲                              │             │
│       │                           │ 6. Query                     │ 7. Event    │
│       │                           │                              ▼             │
│       │  12. Response    ┌─────────────┐  8. Load      ┌─────────────────┐     │
│       └──────────────────│ Annotation  │◄──────────────│ Event Bus       │     │
│                          │ Service     │               │ (Redis)         │     │
│                          └─────────────┘               └─────────────────┘     │
│                                   ▲                              │             │
│                                   │ 9. Create                    │ 11. Notify  │
│                                   │                              ▼             │
│                          ┌─────────────┐ 10. Validate   ┌─────────────────┐    │
│                          │ Validation  │◄───────────────│ Notification    │    │
│                          │ Service     │                │ Service         │    │
│                          └─────────────┘                └─────────────────┘    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

Data Flow Steps:
1. Client uploads video file to Video Service
2. Video Service processes video and extracts metadata  
3. Video metadata and file path stored in Database
4. ML Inference Service generates initial detections
5. Ground Truth Service stores generated ground truth
6. Annotation Service queries database for video data
7. Event Bus notifies of ground truth generation
8. Annotation Service loads ground truth for pre-annotation
9. User creates/updates annotations through Annotation Service
10. Validation Service validates annotations against ground truth
11. Notification Service sends updates to client
12. Client receives real-time updates and validation results
```

### 2.2 Data Flow Implementation

```python
# services/data_flow_manager.py - Data Flow Management

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class FlowStage(Enum):
    VIDEO_UPLOAD = "video_upload"
    VIDEO_PROCESSING = "video_processing"
    GROUND_TRUTH_GENERATION = "ground_truth_generation"
    ANNOTATION_PREPARATION = "annotation_preparation"
    ANNOTATION_SESSION = "annotation_session"
    VALIDATION = "validation"
    RESULT_AGGREGATION = "result_aggregation"
    NOTIFICATION = "notification"

@dataclass
class DataFlowContext:
    """Context for data flow execution"""
    flow_id: str
    project_id: str
    video_id: Optional[str] = None
    user_id: Optional[str] = None
    current_stage: FlowStage = FlowStage.VIDEO_UPLOAD
    stages_completed: List[FlowStage] = None
    stage_data: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.stages_completed is None:
            self.stages_completed = []
        if self.stage_data is None:
            self.stage_data = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

class DataFlowManager:
    """Manages end-to-end data flow across all services"""
    
    def __init__(self, orchestrator: IntegrationOrchestrator):
        self.orchestrator = orchestrator
        self.active_flows: Dict[str, DataFlowContext] = {}
        self.flow_handlers = {}
        self._register_flow_handlers()
    
    async def initialize_flow(self, project_id: str, user_id: str, initial_data: Dict) -> str:
        """Initialize new data flow"""
        
        flow_id = f"flow_{project_id}_{datetime.utcnow().timestamp()}"
        
        context = DataFlowContext(
            flow_id=flow_id,
            project_id=project_id,
            user_id=user_id
        )
        
        # Store initial data
        context.stage_data["initial"] = initial_data
        
        self.active_flows[flow_id] = context
        
        logger.info(f"Data flow initialized: {flow_id}")
        
        return flow_id
    
    async def advance_flow(self, flow_id: str, stage_result: Dict) -> Optional[FlowStage]:
        """Advance data flow to next stage"""
        
        if flow_id not in self.active_flows:
            logger.error(f"Flow not found: {flow_id}")
            return None
        
        context = self.active_flows[flow_id]
        current_stage = context.current_stage
        
        # Store stage result
        context.stage_data[current_stage.value] = stage_result
        context.stages_completed.append(current_stage)
        context.updated_at = datetime.utcnow()
        
        # Determine next stage
        next_stage = self._get_next_stage(current_stage, stage_result)
        
        if next_stage:
            context.current_stage = next_stage
            
            # Execute next stage
            await self._execute_stage(context, next_stage)
            
            logger.info(f"Flow advanced: {flow_id} -> {next_stage.value}")
        else:
            # Flow completed
            await self._complete_flow(context)
            logger.info(f"Flow completed: {flow_id}")
        
        return next_stage
    
    async def _execute_stage(self, context: DataFlowContext, stage: FlowStage):
        """Execute specific flow stage"""
        
        handler = self.flow_handlers.get(stage)
        if not handler:
            logger.error(f"No handler for stage: {stage.value}")
            return
        
        try:
            await handler(context)
        except Exception as e:
            logger.error(f"Stage execution failed: {stage.value} - {e}")
            await self._handle_stage_error(context, stage, str(e))
    
    def _register_flow_handlers(self):
        """Register handlers for each flow stage"""
        
        self.flow_handlers = {
            FlowStage.VIDEO_UPLOAD: self._handle_video_upload,
            FlowStage.VIDEO_PROCESSING: self._handle_video_processing,
            FlowStage.GROUND_TRUTH_GENERATION: self._handle_ground_truth_generation,
            FlowStage.ANNOTATION_PREPARATION: self._handle_annotation_preparation,
            FlowStage.ANNOTATION_SESSION: self._handle_annotation_session,
            FlowStage.VALIDATION: self._handle_validation,
            FlowStage.RESULT_AGGREGATION: self._handle_result_aggregation,
            FlowStage.NOTIFICATION: self._handle_notification
        }
    
    async def _handle_video_upload(self, context: DataFlowContext):
        """Handle video upload stage"""
        
        from services.video_service import VideoService
        
        video_service = VideoService()
        upload_data = context.stage_data.get("initial", {})
        
        # Process video upload
        result = await video_service.process_upload(
            context.project_id,
            upload_data.get("file_data"),
            upload_data.get("filename"),
            context.user_id
        )
        
        context.video_id = result.get("video_id")
        
        # Advance to next stage
        await self.advance_flow(context.flow_id, result)
    
    async def _handle_video_processing(self, context: DataFlowContext):
        """Handle video processing stage"""
        
        from services.video_service import VideoService
        
        video_service = VideoService()
        
        # Extract video metadata and frames
        result = await video_service.extract_metadata_and_frames(context.video_id)
        
        # Advance to ground truth generation
        await self.advance_flow(context.flow_id, result)
    
    async def _handle_ground_truth_generation(self, context: DataFlowContext):
        """Handle ground truth generation stage"""
        
        from services.ground_truth_service import GroundTruthService
        from services.ml_service import MLInferenceService
        
        ground_truth_service = GroundTruthService()
        ml_service = MLInferenceService()
        
        # Run ML inference for initial detections
        ml_result = await ml_service.run_inference(context.video_id)
        
        # Generate ground truth from ML results
        gt_result = await ground_truth_service.generate_from_ml_detections(
            context.video_id,
            ml_result.get("detections", [])
        )
        
        # Combine results
        result = {
            "ml_detections": ml_result,
            "ground_truth": gt_result
        }
        
        await self.advance_flow(context.flow_id, result)
    
    async def _handle_annotation_preparation(self, context: DataFlowContext):
        """Handle annotation preparation stage"""
        
        from services.annotation_service import AnnotationService
        
        annotation_service = AnnotationService()
        
        # Prepare annotation session with ground truth data
        ground_truth_data = context.stage_data.get(FlowStage.GROUND_TRUTH_GENERATION.value, {})
        
        result = await annotation_service.prepare_annotation_session(
            context.video_id,
            context.project_id,
            ground_truth_data.get("ground_truth", {})
        )
        
        await self.advance_flow(context.flow_id, result)
    
    async def _handle_annotation_session(self, context: DataFlowContext):
        """Handle annotation session stage"""
        
        # This stage is typically user-driven
        # We set up the session and wait for user completion
        
        from services.annotation_service import AnnotationService
        
        annotation_service = AnnotationService()
        
        result = await annotation_service.create_annotation_session(
            context.video_id,
            context.project_id,
            context.user_id
        )
        
        # Note: This stage completion is triggered by user actions
        # Not automatically advanced
        
        logger.info(f"Annotation session created for flow: {context.flow_id}")
    
    async def _handle_validation(self, context: DataFlowContext):
        """Handle validation stage"""
        
        from services.validation_service import ValidationService
        
        validation_service = ValidationService()
        
        # Get annotation data
        annotation_data = context.stage_data.get(FlowStage.ANNOTATION_SESSION.value, {})
        ground_truth_data = context.stage_data.get(FlowStage.GROUND_TRUTH_GENERATION.value, {})
        
        # Run validation
        result = await validation_service.validate_annotations(
            context.video_id,
            annotation_data.get("annotations", []),
            ground_truth_data.get("ground_truth", {})
        )
        
        await self.advance_flow(context.flow_id, result)
    
    async def _handle_result_aggregation(self, context: DataFlowContext):
        """Handle result aggregation stage"""
        
        from services.project_service import ProjectService
        
        project_service = ProjectService()
        
        # Aggregate all results
        validation_results = context.stage_data.get(FlowStage.VALIDATION.value, {})
        
        result = await project_service.aggregate_validation_results(
            context.project_id,
            context.video_id,
            validation_results
        )
        
        await self.advance_flow(context.flow_id, result)
    
    async def _handle_notification(self, context: DataFlowContext):
        """Handle notification stage"""
        
        from services.notification_service import NotificationService
        
        notification_service = NotificationService()
        
        # Send completion notification
        aggregated_results = context.stage_data.get(FlowStage.RESULT_AGGREGATION.value, {})
        
        await notification_service.send_flow_completion_notification(
            context.user_id,
            context.project_id,
            context.video_id,
            aggregated_results
        )
        
        # Flow completed
        await self._complete_flow(context)
    
    def _get_next_stage(self, current_stage: FlowStage, stage_result: Dict) -> Optional[FlowStage]:
        """Determine next stage based on current stage and results"""
        
        stage_transitions = {
            FlowStage.VIDEO_UPLOAD: FlowStage.VIDEO_PROCESSING,
            FlowStage.VIDEO_PROCESSING: FlowStage.GROUND_TRUTH_GENERATION,
            FlowStage.GROUND_TRUTH_GENERATION: FlowStage.ANNOTATION_PREPARATION,
            FlowStage.ANNOTATION_PREPARATION: FlowStage.ANNOTATION_SESSION,
            FlowStage.ANNOTATION_SESSION: FlowStage.VALIDATION,
            FlowStage.VALIDATION: FlowStage.RESULT_AGGREGATION,
            FlowStage.RESULT_AGGREGATION: FlowStage.NOTIFICATION,
            FlowStage.NOTIFICATION: None  # End of flow
        }
        
        # Check for conditional transitions
        next_stage = stage_transitions.get(current_stage)
        
        # Handle special cases
        if current_stage == FlowStage.ANNOTATION_SESSION:
            # Only advance if annotation session is completed
            if not stage_result.get("session_completed", False):
                return None
        
        return next_stage
    
    async def _complete_flow(self, context: DataFlowContext):
        """Mark flow as completed"""
        
        context.stages_completed.append(context.current_stage)
        context.updated_at = datetime.utcnow()
        
        # Archive flow data
        await self._archive_flow_data(context)
        
        # Remove from active flows
        if context.flow_id in self.active_flows:
            del self.active_flows[context.flow_id]
        
        logger.info(f"Flow completed and archived: {context.flow_id}")
    
    async def _archive_flow_data(self, context: DataFlowContext):
        """Archive completed flow data"""
        
        # Store in database for future reference
        from database import get_db
        from models.database import DataFlowLog
        
        db = next(get_db())
        
        flow_log = DataFlowLog(
            flow_id=context.flow_id,
            project_id=context.project_id,
            video_id=context.video_id,
            user_id=context.user_id,
            stages_completed=[stage.value for stage in context.stages_completed],
            stage_data=context.stage_data,
            created_at=context.created_at,
            completed_at=datetime.utcnow()
        )
        
        db.add(flow_log)
        db.commit()


# Example usage in FastAPI endpoint
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

data_flow_router = APIRouter()

@data_flow_router.post("/data-flow/start")
async def start_data_flow(
    project_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Start comprehensive data flow"""
    
    # Initialize orchestrator and flow manager
    orchestrator = IntegrationOrchestrator()
    await orchestrator.initialize()
    
    flow_manager = DataFlowManager(orchestrator)
    
    # Start data flow
    flow_id = await flow_manager.initialize_flow(
        project_id=project_id,
        user_id=current_user["user_id"],
        initial_data={
            "filename": file.filename,
            "file_data": await file.read(),
            "content_type": file.content_type
        }
    )
    
    # Begin flow execution
    await flow_manager._execute_stage(
        flow_manager.active_flows[flow_id],
        FlowStage.VIDEO_UPLOAD
    )
    
    return {
        "flow_id": flow_id,
        "status": "started",
        "project_id": project_id
    }

@data_flow_router.get("/data-flow/{flow_id}/status")
async def get_flow_status(
    flow_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get data flow status"""
    
    flow_manager = DataFlowManager(None)
    
    if flow_id not in flow_manager.active_flows:
        # Check archived flows
        from database import get_db
        from models.database import DataFlowLog
        
        db = next(get_db())
        flow_log = db.query(DataFlowLog).filter(
            DataFlowLog.flow_id == flow_id
        ).first()
        
        if flow_log:
            return {
                "flow_id": flow_id,
                "status": "completed",
                "stages_completed": flow_log.stages_completed,
                "completed_at": flow_log.completed_at.isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Flow not found")
    
    context = flow_manager.active_flows[flow_id]
    
    return {
        "flow_id": flow_id,
        "status": "active",
        "current_stage": context.current_stage.value,
        "stages_completed": [stage.value for stage in context.stages_completed],
        "updated_at": context.updated_at.isoformat()
    }
```

This comprehensive integration architecture provides:

1. **Event-Driven Integration**: Asynchronous event-based communication between services
2. **Data Synchronization**: Automated data consistency across all components
3. **Service Orchestration**: Centralized workflow management and coordination
4. **Integration Patterns**: Reusable patterns for common integration scenarios
5. **Data Flow Management**: End-to-end data flow tracking and control
6. **Error Handling**: Robust error handling and recovery mechanisms
7. **Monitoring**: Comprehensive logging and monitoring of integration processes
8. **Scalability**: Designed for horizontal scaling and high throughput