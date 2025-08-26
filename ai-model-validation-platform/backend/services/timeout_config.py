#!/usr/bin/env python3
"""
Timeout Configuration Management
Centralized timeout settings for all detection services
"""

import os
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class TimeoutConfig:
    """Centralized timeout configuration"""
    
    # API timeouts
    api_request_timeout: float = 30.0
    api_response_timeout: float = 60.0
    
    # Detection pipeline timeouts
    max_video_processing_timeout: float = 300.0  # 5 minutes
    frame_inference_timeout: float = 15.0        # 15 seconds per frame
    model_loading_timeout: float = 60.0          # 1 minute to load model
    
    # Database timeouts
    database_connection_timeout: float = 30.0
    database_query_timeout: float = 60.0
    
    # Video processing timeouts
    video_open_timeout: float = 10.0
    frame_processing_timeout: float = 5.0
    
    # Background task timeouts
    background_task_timeout: float = 600.0       # 10 minutes
    
    # Performance settings
    frame_skip_ratio: int = 5                    # Process every 5th frame
    batch_size: int = 8
    max_concurrent_videos: int = 3
    
    # Graceful degradation settings
    enable_mock_fallback: bool = True
    mock_detection_count: int = 3
    
    @classmethod
    def from_environment(cls) -> 'TimeoutConfig':
        """Create config from environment variables"""
        return cls(
            api_request_timeout=float(os.getenv('DETECTION_API_TIMEOUT', '30.0')),
            api_response_timeout=float(os.getenv('DETECTION_API_RESPONSE_TIMEOUT', '60.0')),
            
            max_video_processing_timeout=float(os.getenv('DETECTION_MAX_PROCESSING_TIMEOUT', '300.0')),
            frame_inference_timeout=float(os.getenv('DETECTION_FRAME_TIMEOUT', '15.0')),
            model_loading_timeout=float(os.getenv('DETECTION_MODEL_LOADING_TIMEOUT', '60.0')),
            
            database_connection_timeout=float(os.getenv('DB_CONNECTION_TIMEOUT', '30.0')),
            database_query_timeout=float(os.getenv('DB_QUERY_TIMEOUT', '60.0')),
            
            video_open_timeout=float(os.getenv('VIDEO_OPEN_TIMEOUT', '10.0')),
            frame_processing_timeout=float(os.getenv('FRAME_PROCESSING_TIMEOUT', '5.0')),
            
            background_task_timeout=float(os.getenv('BACKGROUND_TASK_TIMEOUT', '600.0')),
            
            frame_skip_ratio=int(os.getenv('DETECTION_FRAME_SKIP', '5')),
            batch_size=int(os.getenv('DETECTION_BATCH_SIZE', '8')),
            max_concurrent_videos=int(os.getenv('MAX_CONCURRENT_VIDEOS', '3')),
            
            enable_mock_fallback=os.getenv('ENABLE_MOCK_FALLBACK', 'true').lower() == 'true',
            mock_detection_count=int(os.getenv('MOCK_DETECTION_COUNT', '3'))
        )
    
    def get_video_timeout(self, video_duration_seconds: float) -> float:
        """Calculate dynamic timeout based on video duration"""
        # Base timeout + processing time per second of video
        processing_time_per_second = 2.0  # 2 seconds processing per 1 second of video
        dynamic_timeout = 60.0 + (video_duration_seconds * processing_time_per_second)
        
        # Cap at maximum timeout
        return min(dynamic_timeout, self.max_video_processing_timeout)
    
    def get_performance_config(self) -> Dict[str, Any]:
        """Get performance optimization settings"""
        return {
            'frame_skip_ratio': self.frame_skip_ratio,
            'batch_size': self.batch_size,
            'max_concurrent_videos': self.max_concurrent_videos,
            'enable_model_caching': True,
            'enable_frame_caching': False,  # Memory intensive
            'use_gpu_if_available': True
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/debugging"""
        return {
            'timeouts': {
                'api_request': self.api_request_timeout,
                'api_response': self.api_response_timeout,
                'video_processing_max': self.max_video_processing_timeout,
                'frame_inference': self.frame_inference_timeout,
                'model_loading': self.model_loading_timeout,
                'database_connection': self.database_connection_timeout,
                'database_query': self.database_query_timeout,
                'video_open': self.video_open_timeout,
                'frame_processing': self.frame_processing_timeout,
                'background_task': self.background_task_timeout
            },
            'performance': {
                'frame_skip_ratio': self.frame_skip_ratio,
                'batch_size': self.batch_size,
                'max_concurrent_videos': self.max_concurrent_videos
            },
            'fallback': {
                'enable_mock_fallback': self.enable_mock_fallback,
                'mock_detection_count': self.mock_detection_count
            }
        }

# Global configuration instance
timeout_config = TimeoutConfig.from_environment()

# Timeout decorators for common use cases
import asyncio
import functools
import logging
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')

def with_timeout(timeout_seconds: float, fallback_value: Any = None):
    """Decorator to add timeout to async functions"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.warning(f"Function {func.__name__} timed out after {timeout_seconds}s")
                if fallback_value is not None:
                    return fallback_value
                raise
        return wrapper
    return decorator

def with_api_timeout(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for API endpoint timeouts"""
    return with_timeout(timeout_config.api_response_timeout)(func)

def with_detection_timeout(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for detection processing timeouts"""
    return with_timeout(timeout_config.max_video_processing_timeout)(func)

def with_model_timeout(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator for model loading timeouts"""
    return with_timeout(timeout_config.model_loading_timeout)(func)

# Context manager for timeout handling
@asynccontextmanager
async def timeout_context(timeout_seconds: float, operation_name: str = "operation"):
    """Context manager for timeout handling with logging"""
    start_time = asyncio.get_event_loop().time()
    try:
        async with asyncio.timeout(timeout_seconds):
            yield
    except asyncio.TimeoutError:
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.error(f"⏰ {operation_name} timed out after {elapsed:.2f}s (limit: {timeout_seconds}s)")
        raise
    except Exception as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.error(f"❌ {operation_name} failed after {elapsed:.2f}s: {e}")
        raise
    else:
        elapsed = asyncio.get_event_loop().time() - start_time
        logger.info(f"✅ {operation_name} completed in {elapsed:.2f}s")

# Utility functions
async def safe_video_processing(video_path: str, processing_func: Callable, *args, **kwargs):
    """Safely process video with timeout and error handling"""
    import cv2
    
    # Get video duration for dynamic timeout
    try:
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 60.0  # Default to 60s
            cap.release()
        else:
            duration = 60.0  # Default duration
    except Exception:
        duration = 60.0
    
    # Calculate timeout
    processing_timeout = timeout_config.get_video_timeout(duration)
    
    logger.info(f"🎬 Processing video: {Path(video_path).name} ({duration:.1f}s) with {processing_timeout:.0f}s timeout")
    
    async with timeout_context(processing_timeout, f"video processing: {Path(video_path).name}"):
        return await processing_func(*args, **kwargs)

if __name__ == "__main__":
    # Print configuration for debugging
    print("🔧 Timeout Configuration:")
    import json
    print(json.dumps(timeout_config.to_dict(), indent=2))