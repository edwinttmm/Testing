"""
WebSocket Progress Tracking Service
Provides real-time progress updates for long-running ML operations
"""
import asyncio
import json
import time
import logging
from typing import Dict, Optional, Any, Callable
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Track and broadcast progress for long-running operations"""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict] = {}
        self.websocket_connections: Dict[str, Any] = {}  # WebSocket connections by task_id
        
    def create_task(self, task_id: str, task_name: str, total_steps: int = 100) -> str:
        """Create a new tracked task"""
        self.active_tasks[task_id] = {
            "id": task_id,
            "name": task_name,
            "status": "started",
            "progress": 0,
            "total_steps": total_steps,
            "current_step": 0,
            "message": "Initializing...",
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "error": None,
            "result": None
        }
        
        logger.info(f"📊 Created progress tracker for task: {task_name} ({task_id})")
        return task_id
    
    def update_progress(self, task_id: str, current_step: int, message: str = None):
        """Update task progress"""
        if task_id not in self.active_tasks:
            logger.warning(f"Task {task_id} not found")
            return
        
        task = self.active_tasks[task_id]
        task["current_step"] = current_step
        task["progress"] = min(100, (current_step / task["total_steps"]) * 100)
        task["updated_at"] = datetime.utcnow().isoformat()
        
        if message:
            task["message"] = message
        
        # Broadcast update via WebSocket
        asyncio.create_task(self._broadcast_update(task_id, task))
        
        logger.debug(f"📈 Task {task_id} progress: {task['progress']:.1f}% - {message}")
    
    def complete_task(self, task_id: str, result: Any = None):
        """Mark task as completed"""
        if task_id not in self.active_tasks:
            return
        
        task = self.active_tasks[task_id]
        task["status"] = "completed"
        task["progress"] = 100
        task["current_step"] = task["total_steps"]
        task["message"] = "Completed successfully"
        task["updated_at"] = datetime.utcnow().isoformat()
        task["result"] = result
        
        # Broadcast completion
        asyncio.create_task(self._broadcast_update(task_id, task))
        
        logger.info(f"✅ Task {task_id} completed successfully")
        
        # Clean up after 5 minutes
        asyncio.create_task(self._cleanup_task(task_id, delay=300))
    
    def fail_task(self, task_id: str, error: str):
        """Mark task as failed"""
        if task_id not in self.active_tasks:
            return
        
        task = self.active_tasks[task_id]
        task["status"] = "failed"
        task["message"] = f"Failed: {error}"
        task["updated_at"] = datetime.utcnow().isoformat()
        task["error"] = error
        
        # Broadcast failure
        asyncio.create_task(self._broadcast_update(task_id, task))
        
        logger.error(f"❌ Task {task_id} failed: {error}")
        
        # Clean up after 1 minute
        asyncio.create_task(self._cleanup_task(task_id, delay=60))
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get current status of a task"""
        return self.active_tasks.get(task_id)
    
    def list_active_tasks(self) -> Dict[str, Dict]:
        """List all active tasks"""
        return {
            task_id: task for task_id, task in self.active_tasks.items()
            if task["status"] not in ["completed", "failed"]
        }
    
    async def register_websocket(self, task_id: str, websocket):
        """Register WebSocket connection for progress updates"""
        self.websocket_connections[task_id] = websocket
        logger.info(f"🔗 Registered WebSocket for task {task_id}")
        
        # Send current status immediately
        if task_id in self.active_tasks:
            await self._send_update(websocket, self.active_tasks[task_id])
    
    def unregister_websocket(self, task_id: str):
        """Unregister WebSocket connection"""
        if task_id in self.websocket_connections:
            del self.websocket_connections[task_id]
            logger.info(f"🔗 Unregistered WebSocket for task {task_id}")
    
    async def _broadcast_update(self, task_id: str, task: Dict):
        """Broadcast task update to connected WebSockets"""
        if task_id in self.websocket_connections:
            websocket = self.websocket_connections[task_id]
            try:
                await self._send_update(websocket, task)
            except Exception as e:
                logger.warning(f"Failed to send WebSocket update for {task_id}: {e}")
                # Remove failed connection
                self.unregister_websocket(task_id)
    
    async def _send_update(self, websocket, task: Dict):
        """Send update to specific WebSocket"""
        try:
            message = {
                "type": "progress_update",
                "data": task
            }
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.warning(f"WebSocket send failed: {e}")
            raise
    
    async def _cleanup_task(self, task_id: str, delay: int = 300):
        """Clean up completed/failed task after delay"""
        await asyncio.sleep(delay)
        
        if task_id in self.active_tasks:
            del self.active_tasks[task_id]
            logger.debug(f"🗑️  Cleaned up task {task_id}")
        
        if task_id in self.websocket_connections:
            self.unregister_websocket(task_id)

class ProgressContext:
    """Context manager for progress tracking"""
    
    def __init__(self, tracker: ProgressTracker, task_name: str, total_steps: int = 100):
        self.tracker = tracker
        self.task_name = task_name
        self.total_steps = total_steps
        self.task_id = str(uuid.uuid4())
        self.current_step = 0
    
    async def __aenter__(self):
        self.tracker.create_task(self.task_id, self.task_name, self.total_steps)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.tracker.fail_task(self.task_id, str(exc_val))
        else:
            self.tracker.complete_task(self.task_id)
    
    def update(self, step_increment: int = 1, message: str = None):
        """Update progress by incrementing steps"""
        self.current_step += step_increment
        self.tracker.update_progress(self.task_id, self.current_step, message)
    
    def set_progress(self, current_step: int, message: str = None):
        """Set absolute progress"""
        self.current_step = current_step
        self.tracker.update_progress(self.task_id, current_step, message)

# Global progress tracker instance
progress_tracker = ProgressTracker()

# Decorator for automatic progress tracking
def track_progress(task_name: str, total_steps: int = 100):
    """Decorator to automatically track function progress"""
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            async with ProgressContext(progress_tracker, task_name, total_steps) as context:
                # Pass context to function if it accepts it
                import inspect
                sig = inspect.signature(func)
                if 'progress_context' in sig.parameters:
                    kwargs['progress_context'] = context
                
                result = await func(*args, **kwargs)
                return result
        
        return wrapper
    return decorator