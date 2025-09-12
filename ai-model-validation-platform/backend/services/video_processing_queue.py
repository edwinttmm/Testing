"""
Video Processing Queue Service
Manages background processing of video ingestion and annotation tasks
"""

import asyncio
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class TaskType(str, Enum):
    VIDEO_UPLOAD = "video_upload"
    AUTOMATED_ANNOTATION = "automated_annotation"
    VIDEO_VALIDATION = "video_validation"

@dataclass
class ProcessingTask:
    """Represents a video processing task"""
    task_id: str
    task_type: TaskType
    video_id: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class VideoProcessingQueue:
    """
    Simple in-memory queue for video processing tasks
    In production, this would use Redis or a proper message queue
    """
    
    def __init__(self):
        self.tasks: Dict[str, ProcessingTask] = {}
        self.pending_queue = asyncio.Queue()
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self.worker_count = 2  # Number of concurrent workers
        self.workers_started = False
        
    async def start_workers(self):
        """Start background workers to process tasks"""
        if self.workers_started:
            return
            
        self.workers_started = True
        
        # Start worker tasks
        for i in range(self.worker_count):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.processing_tasks[f"worker-{i}"] = worker_task
        
        logger.info(f"Started {self.worker_count} video processing workers")
    
    async def stop_workers(self):
        """Stop all background workers"""
        if not self.workers_started:
            return
            
        # Cancel all worker tasks
        for worker_name, task in self.processing_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.processing_tasks.clear()
        self.workers_started = False
        logger.info("Stopped all video processing workers")
    
    async def add_task(
        self, 
        task_type: TaskType, 
        video_id: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a new task to the processing queue"""
        
        task_id = str(uuid.uuid4())
        
        task = ProcessingTask(
            task_id=task_id,
            task_type=task_type,
            video_id=video_id,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.tasks[task_id] = task
        await self.pending_queue.put(task_id)
        
        logger.info(f"Added task {task_id} ({task_type}) for video {video_id}")
        return task_id
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific task"""
        if task_id not in self.tasks:
            return None
            
        task = self.tasks[task_id]
        return {
            "task_id": task.task_id,
            "task_type": task.task_type.value,
            "video_id": task.video_id,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "retry_count": task.retry_count,
            "error_message": task.error_message,
            "metadata": task.metadata
        }
    
    async def get_video_tasks(self, video_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific video"""
        video_tasks = []
        
        for task in self.tasks.values():
            if task.video_id == video_id:
                task_data = await self.get_task_status(task.task_id)
                if task_data:
                    video_tasks.append(task_data)
        
        # Sort by creation time
        video_tasks.sort(key=lambda x: x["created_at"])
        return video_tasks
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        pending_count = 0
        processing_count = 0
        completed_count = 0
        failed_count = 0
        
        for task in self.tasks.values():
            if task.status == TaskStatus.PENDING:
                pending_count += 1
            elif task.status == TaskStatus.PROCESSING:
                processing_count += 1
            elif task.status == TaskStatus.COMPLETED:
                completed_count += 1
            elif task.status == TaskStatus.FAILED:
                failed_count += 1
        
        return {
            "total_tasks": len(self.tasks),
            "pending": pending_count,
            "processing": processing_count,
            "completed": completed_count,
            "failed": failed_count,
            "workers_active": len([t for t in self.processing_tasks.values() if not t.done()]),
            "queue_size": self.pending_queue.qsize()
        }
    
    async def _worker(self, worker_name: str):
        """Background worker to process tasks"""
        logger.info(f"Video processing worker {worker_name} started")
        
        try:
            while True:
                # Get next task from queue
                task_id = await self.pending_queue.get()
                
                if task_id not in self.tasks:
                    continue
                
                task = self.tasks[task_id]
                
                # Mark task as processing
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.utcnow()
                
                logger.info(f"Worker {worker_name} processing task {task_id} ({task.task_type})")
                
                try:
                    # Process the task based on type
                    await self._process_task(task)
                    
                    # Mark as completed
                    task.status = TaskStatus.COMPLETED
                    task.completed_at = datetime.utcnow()
                    
                    logger.info(f"Worker {worker_name} completed task {task_id}")
                    
                except Exception as e:
                    logger.error(f"Worker {worker_name} failed to process task {task_id}: {e}")
                    
                    # Handle retry logic
                    task.retry_count += 1
                    task.error_message = str(e)
                    
                    if task.retry_count <= task.max_retries:
                        # Retry the task
                        task.status = TaskStatus.RETRYING
                        await asyncio.sleep(min(2 ** task.retry_count, 60))  # Exponential backoff
                        await self.pending_queue.put(task_id)
                        logger.info(f"Retrying task {task_id} (attempt {task.retry_count})")
                    else:
                        # Mark as failed
                        task.status = TaskStatus.FAILED
                        task.completed_at = datetime.utcnow()
                        logger.error(f"Task {task_id} failed after {task.max_retries} retries")
                
                finally:
                    self.pending_queue.task_done()
                    
        except asyncio.CancelledError:
            logger.info(f"Video processing worker {worker_name} cancelled")
        except Exception as e:
            logger.error(f"Video processing worker {worker_name} crashed: {e}")
    
    async def _process_task(self, task: ProcessingTask):
        """Process a specific task based on its type"""
        from database import SessionLocal
        from services.video_ingestion_service import VideoIngestionService
        
        # Create database session
        db = SessionLocal()
        video_service = VideoIngestionService()
        
        try:
            if task.task_type == TaskType.AUTOMATED_ANNOTATION:
                # Process automated annotation
                result = await video_service.process_automated_annotation(db, task.video_id)
                task.metadata["processing_result"] = result
                
            elif task.task_type == TaskType.VIDEO_VALIDATION:
                # Process video validation
                result = await video_service.validate_video_annotations(db, task.video_id)
                task.metadata["validation_result"] = result
                
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
                
        finally:
            db.close()
    
    async def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Clean up old completed/failed tasks"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        tasks_to_remove = []
        
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED] and 
                task.completed_at and task.completed_at < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.tasks[task_id]
        
        if tasks_to_remove:
            logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")

# Global queue instance
video_processing_queue = VideoProcessingQueue()