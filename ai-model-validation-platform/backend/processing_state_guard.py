"""
Processing State Guard - Prevents duplicate processing operations
"""
import time
from typing import Dict, Set
from dataclasses import dataclass
from threading import Lock
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProcessingStatus:
    video_id: str
    started_at: float
    status: str  # 'processing', 'completed', 'failed'
    
class ProcessingStateGuard:
    """Thread-safe guard to prevent duplicate video processing"""
    
    def __init__(self):
        self._processing_videos: Dict[str, ProcessingStatus] = {}
        self._lock = Lock()
        self._timeout_seconds = 3600  # 1 hour timeout for processing
    
    def can_start_processing(self, video_id: str) -> bool:
        """Check if video processing can be started"""
        with self._lock:
            # Clean up expired processing entries
            self._cleanup_expired()
            
            if video_id in self._processing_videos:
                status = self._processing_videos[video_id]
                
                if status.status == 'processing':
                    logger.warning(f"🚫 Video {video_id} is already being processed")
                    return False
                elif status.status == 'completed':
                    logger.info(f"✅ Video {video_id} processing already completed")
                    return False
            
            return True
    
    def start_processing(self, video_id: str) -> bool:
        """Mark video as being processed"""
        with self._lock:
            if not self.can_start_processing(video_id):
                return False
            
            self._processing_videos[video_id] = ProcessingStatus(
                video_id=video_id,
                started_at=time.time(),
                status='processing'
            )
            
            logger.info(f"🟡 Started processing for video {video_id}")
            return True
    
    def complete_processing(self, video_id: str, success: bool = True):
        """Mark video processing as completed"""
        with self._lock:
            if video_id in self._processing_videos:
                self._processing_videos[video_id].status = 'completed' if success else 'failed'
                logger.info(f"✅ Completed processing for video {video_id}: {'success' if success else 'failed'}")
    
    def _cleanup_expired(self):
        """Clean up expired processing entries"""
        current_time = time.time()
        expired_keys = []
        
        for video_id, status in self._processing_videos.items():
            if current_time - status.started_at > self._timeout_seconds:
                expired_keys.append(video_id)
        
        for key in expired_keys:
            del self._processing_videos[key]
            logger.warning(f"⏰ Cleaned up expired processing entry for video {key}")
    
    def get_processing_status(self, video_id: str) -> str:
        """Get current processing status for a video"""
        with self._lock:
            self._cleanup_expired()
            
            if video_id in self._processing_videos:
                return self._processing_videos[video_id].status
            
            return 'not_started'
    
    def get_all_processing(self) -> Dict[str, str]:
        """Get all current processing statuses"""
        with self._lock:
            self._cleanup_expired()
            
            return {
                video_id: status.status 
                for video_id, status in self._processing_videos.items()
            }

# Global instance
processing_guard = ProcessingStateGuard()