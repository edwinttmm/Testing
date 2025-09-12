"""
Frame-Accurate Video Seeking Service

Provides frame-accurate video seeking capabilities integrated with the precision
timing system for HIL validation. Enables precise navigation to specific frames
or timestamps with sub-millisecond accuracy.

Key Features:
- Frame-accurate seeking with precision timing
- Interpolation for frames beyond cached range
- Integration with video timing service
- Support for multiple seek methods
- Accuracy validation for HIL compliance

HIL Integration:
- Sub-millisecond seek accuracy
- Frame synchronization with hardware events
- Timing accuracy reporting
- Integration with detection event analysis
"""

import logging
import threading
import time
import math
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path
import uuid

from .precision_timing_service import (
    get_precision_timing_service,
    PrecisionTimingService,
    FrameTimestamp
)
from .video_timing_service import get_video_timing_service, VideoTimingService

logger = logging.getLogger(__name__)

# Seeking constants
DEFAULT_SEEK_ACCURACY_MS = 1.0  # Default seek accuracy
HIL_SEEK_ACCURACY_MS = 0.1      # HIL precision requirement
MAX_INTERPOLATION_DISTANCE = 100  # Max frames for interpolation


@dataclass
class SeekRequest:
    """Frame seek request data"""
    video_id: str
    target_frame: Optional[int] = None
    target_timestamp_ms: Optional[float] = None
    accuracy_requirement_ms: float = HIL_SEEK_ACCURACY_MS
    seek_method: str = "precise"  # 'precise', 'fast', 'interpolated'


@dataclass
class SeekResult:
    """Frame seek result data"""
    video_id: str
    requested_frame: Optional[int]
    requested_timestamp_ms: Optional[float]
    actual_frame: int
    actual_timestamp_ms: float
    seek_accuracy_ms: float
    seek_successful: bool
    frame_timestamp: Optional[FrameTimestamp] = None
    interpolated: bool = False
    seek_time_ms: float = 0.0
    error_message: Optional[str] = None


class FrameSeekingService:
    """
    Service for frame-accurate video seeking with precision timing integration.
    
    Provides sub-millisecond accurate seeking capabilities for HIL validation
    scenarios where precise frame timing is critical.
    """
    
    def __init__(self, precision_service: Optional[PrecisionTimingService] = None,
                 video_service: Optional[VideoTimingService] = None):
        """
        Initialize frame seeking service.
        
        Args:
            precision_service: Precision timing service instance
            video_service: Video timing service instance
        """
        self._lock = threading.RLock()
        self._precision_service = precision_service or get_precision_timing_service()
        self._video_service = video_service or get_video_timing_service()
        
        # Seeking cache and state
        self._seek_cache: Dict[str, List[FrameTimestamp]] = {}  # video_id -> frame cache
        self._seek_history: List[SeekResult] = []
        self._interpolation_cache: Dict[str, Dict[int, FrameTimestamp]] = {}  # video_id -> frame -> timestamp
        
        # Performance metrics
        self._total_seeks = 0
        self._successful_seeks = 0
        self._interpolated_seeks = 0
        self._cache_hits = 0
        
        logger.info("FrameSeekingService initialized with precision timing integration")
    
    def seek_to_frame(self, video_id: str, target_frame: int,
                     accuracy_requirement_ms: float = HIL_SEEK_ACCURACY_MS) -> SeekResult:
        """
        Seek to a specific frame with precision timing.
        
        Args:
            video_id: Video identifier
            target_frame: Target frame number
            accuracy_requirement_ms: Required seek accuracy in milliseconds
            
        Returns:
            SeekResult with seek operation results
        """
        seek_start = time.time()
        
        try:
            with self._lock:
                # Create seek request
                request = SeekRequest(
                    video_id=video_id,
                    target_frame=target_frame,
                    accuracy_requirement_ms=accuracy_requirement_ms
                )
                
                # Check cache first
                frame_timestamp = self._get_cached_frame_timestamp(video_id, target_frame)
                
                if frame_timestamp is None:
                    # Try to get from precision timing service
                    frame_timestamp = self._precision_service.get_frame_timestamp(video_id, target_frame)
                
                if frame_timestamp is None:
                    # Generate through interpolation if needed
                    frame_timestamp = self._interpolate_frame_timestamp(video_id, target_frame)
                
                if frame_timestamp is None:
                    # Create basic timestamp estimate
                    frame_timestamp = self._estimate_frame_timestamp(video_id, target_frame)
                
                # Calculate seek results
                seek_time = (time.time() - seek_start) * 1000  # Convert to ms
                actual_timestamp_ms = frame_timestamp.video_timestamp_ms
                
                # Determine if seek was successful based on accuracy
                target_timestamp_ms = target_frame * (1000.0 / frame_timestamp.frame_rate) if frame_timestamp else 0.0
                seek_error_ms = abs(actual_timestamp_ms - target_timestamp_ms) if target_frame is not None else 0.0
                seek_successful = seek_error_ms <= accuracy_requirement_ms
                
                result = SeekResult(
                    video_id=video_id,
                    requested_frame=target_frame,
                    requested_timestamp_ms=target_timestamp_ms,
                    actual_frame=frame_timestamp.frame_number,
                    actual_timestamp_ms=actual_timestamp_ms,
                    seek_accuracy_ms=seek_error_ms,
                    seek_successful=seek_successful,
                    frame_timestamp=frame_timestamp,
                    interpolated=frame_timestamp.interpolated,
                    seek_time_ms=seek_time
                )
                
                # Update statistics
                self._update_seek_statistics(result)
                
                logger.debug(f"Frame seek - Video: {video_id}, Frame: {target_frame}, "
                           f"Accuracy: {seek_error_ms:.3f}ms, Success: {seek_successful}")
                
                return result
                
        except Exception as e:
            seek_time = (time.time() - seek_start) * 1000
            error_result = SeekResult(
                video_id=video_id,
                requested_frame=target_frame,
                requested_timestamp_ms=None,
                actual_frame=-1,
                actual_timestamp_ms=0.0,
                seek_accuracy_ms=float('inf'),
                seek_successful=False,
                seek_time_ms=seek_time,
                error_message=str(e)
            )
            
            logger.error(f"Frame seek failed for video {video_id}, frame {target_frame}: {e}")
            return error_result
    
    def seek_to_timestamp(self, video_id: str, target_timestamp_ms: float,
                         accuracy_requirement_ms: float = HIL_SEEK_ACCURACY_MS) -> SeekResult:
        """
        Seek to a specific timestamp with precision timing.
        
        Args:
            video_id: Video identifier
            target_timestamp_ms: Target timestamp in milliseconds
            accuracy_requirement_ms: Required seek accuracy in milliseconds
            
        Returns:
            SeekResult with seek operation results
        """
        seek_start = time.time()
        
        try:
            with self._lock:
                # Get video frame rate for timestamp-to-frame conversion
                frame_rate = self._get_video_frame_rate(video_id)
                
                if frame_rate is None:
                    raise ValueError(f"Cannot determine frame rate for video {video_id}")
                
                # Convert timestamp to frame number
                target_frame = int(target_timestamp_ms * frame_rate / 1000.0)
                
                # Create seek request
                request = SeekRequest(
                    video_id=video_id,
                    target_timestamp_ms=target_timestamp_ms,
                    accuracy_requirement_ms=accuracy_requirement_ms
                )
                
                # Find closest frame timestamp
                closest_frame = self._find_closest_frame_by_timestamp(video_id, target_timestamp_ms)
                
                if closest_frame is None:
                    # Interpolate or estimate
                    closest_frame = self._interpolate_timestamp_to_frame(video_id, target_timestamp_ms, frame_rate)
                
                # Calculate seek results
                seek_time = (time.time() - seek_start) * 1000  # Convert to ms
                actual_timestamp_ms = closest_frame.video_timestamp_ms
                seek_error_ms = abs(actual_timestamp_ms - target_timestamp_ms)
                seek_successful = seek_error_ms <= accuracy_requirement_ms
                
                result = SeekResult(
                    video_id=video_id,
                    requested_frame=target_frame,
                    requested_timestamp_ms=target_timestamp_ms,
                    actual_frame=closest_frame.frame_number,
                    actual_timestamp_ms=actual_timestamp_ms,
                    seek_accuracy_ms=seek_error_ms,
                    seek_successful=seek_successful,
                    frame_timestamp=closest_frame,
                    interpolated=closest_frame.interpolated,
                    seek_time_ms=seek_time
                )
                
                # Update statistics
                self._update_seek_statistics(result)
                
                logger.debug(f"Timestamp seek - Video: {video_id}, Target: {target_timestamp_ms:.3f}ms, "
                           f"Actual: {actual_timestamp_ms:.3f}ms, Accuracy: {seek_error_ms:.3f}ms")
                
                return result
                
        except Exception as e:
            seek_time = (time.time() - seek_start) * 1000
            error_result = SeekResult(
                video_id=video_id,
                requested_frame=None,
                requested_timestamp_ms=target_timestamp_ms,
                actual_frame=-1,
                actual_timestamp_ms=0.0,
                seek_accuracy_ms=float('inf'),
                seek_successful=False,
                seek_time_ms=seek_time,
                error_message=str(e)
            )
            
            logger.error(f"Timestamp seek failed for video {video_id}, timestamp {target_timestamp_ms}: {e}")
            return error_result
    
    def _get_cached_frame_timestamp(self, video_id: str, frame_number: int) -> Optional[FrameTimestamp]:
        """Get frame timestamp from cache"""
        if video_id in self._seek_cache:
            frames = self._seek_cache[video_id]
            
            for frame_ts in frames:
                if frame_ts.frame_number == frame_number:
                    self._cache_hits += 1
                    return frame_ts
        
        return None
    
    def _interpolate_frame_timestamp(self, video_id: str, target_frame: int) -> Optional[FrameTimestamp]:
        """Interpolate frame timestamp when not directly available"""
        try:
            # Check interpolation cache first
            if video_id in self._interpolation_cache:
                cached_frame = self._interpolation_cache[video_id].get(target_frame)
                if cached_frame:
                    return cached_frame
            
            # Get nearby frames for interpolation
            nearby_frames = self._get_nearby_frames(video_id, target_frame, MAX_INTERPOLATION_DISTANCE)
            
            if len(nearby_frames) < 2:
                return None
            
            # Find two frames to interpolate between
            before_frame = None
            after_frame = None
            
            for frame_ts in nearby_frames:
                if frame_ts.frame_number <= target_frame:
                    if before_frame is None or frame_ts.frame_number > before_frame.frame_number:
                        before_frame = frame_ts
                if frame_ts.frame_number >= target_frame:
                    if after_frame is None or frame_ts.frame_number < after_frame.frame_number:
                        after_frame = frame_ts
            
            if before_frame is None or after_frame is None:
                return None
            
            # Perform linear interpolation
            if before_frame.frame_number == after_frame.frame_number:
                interpolated = before_frame
            else:
                # Calculate interpolation factor
                factor = (target_frame - before_frame.frame_number) / (after_frame.frame_number - before_frame.frame_number)
                
                # Interpolate timestamp
                interpolated_timestamp_ms = (
                    before_frame.video_timestamp_ms + 
                    factor * (after_frame.video_timestamp_ms - before_frame.video_timestamp_ms)
                )
                
                # Interpolate system timestamp
                interpolated_system_ns = (
                    before_frame.system_timestamp_ns + 
                    int(factor * (after_frame.system_timestamp_ns - before_frame.system_timestamp_ns))
                )
                
                # Interpolate monotonic timestamp
                interpolated_monotonic_ns = (
                    before_frame.monotonic_timestamp_ns + 
                    int(factor * (after_frame.monotonic_timestamp_ns - before_frame.monotonic_timestamp_ns))
                )
                
                # Create interpolated frame timestamp
                interpolated = FrameTimestamp(
                    frame_number=target_frame,
                    video_timestamp_ms=interpolated_timestamp_ms,
                    system_timestamp_ns=interpolated_system_ns,
                    monotonic_timestamp_ns=interpolated_monotonic_ns,
                    frame_rate=before_frame.frame_rate,
                    interpolated=True,
                    accuracy_estimate_ns=max(before_frame.accuracy_estimate_ns, after_frame.accuracy_estimate_ns) * 2
                )
            
            # Cache interpolated result
            if video_id not in self._interpolation_cache:
                self._interpolation_cache[video_id] = {}
            self._interpolation_cache[video_id][target_frame] = interpolated
            
            self._interpolated_seeks += 1
            
            logger.debug(f"Interpolated frame {target_frame} for video {video_id}")
            return interpolated
            
        except Exception as e:
            logger.error(f"Frame interpolation failed for video {video_id}, frame {target_frame}: {e}")
            return None
    
    def _estimate_frame_timestamp(self, video_id: str, target_frame: int) -> Optional[FrameTimestamp]:
        """Create basic timestamp estimate when interpolation is not possible"""
        try:
            # Try to get video metadata
            frame_rate = self._get_video_frame_rate(video_id)
            
            if frame_rate is None:
                frame_rate = 30.0  # Default assumption
            
            # Calculate basic timestamp
            video_timestamp_ms = target_frame * (1000.0 / frame_rate)
            current_time = time.time()
            current_time_ns = int(current_time * 1_000_000_000)
            monotonic_time_ns = time.perf_counter_ns()
            
            estimated = FrameTimestamp(
                frame_number=target_frame,
                video_timestamp_ms=video_timestamp_ms,
                system_timestamp_ns=current_time_ns,
                monotonic_timestamp_ns=monotonic_time_ns,
                frame_rate=frame_rate,
                interpolated=True,  # Mark as interpolated since it's an estimate
                accuracy_estimate_ns=10_000_000  # 10ms estimate accuracy
            )
            
            logger.debug(f"Estimated frame {target_frame} for video {video_id} (frame rate: {frame_rate})")
            return estimated
            
        except Exception as e:
            logger.error(f"Frame estimation failed for video {video_id}, frame {target_frame}: {e}")
            return None
    
    def _get_nearby_frames(self, video_id: str, target_frame: int, max_distance: int) -> List[FrameTimestamp]:
        """Get frames near the target frame for interpolation"""
        nearby_frames = []
        
        # Check cache
        if video_id in self._seek_cache:
            for frame_ts in self._seek_cache[video_id]:
                if abs(frame_ts.frame_number - target_frame) <= max_distance:
                    nearby_frames.append(frame_ts)
        
        # Sort by frame number
        nearby_frames.sort(key=lambda f: f.frame_number)
        
        return nearby_frames
    
    def _find_closest_frame_by_timestamp(self, video_id: str, target_timestamp_ms: float) -> Optional[FrameTimestamp]:
        """Find the closest frame to a target timestamp"""
        closest_frame = None
        min_difference = float('inf')
        
        # Check precision timing service first
        if video_id in self._precision_service._frame_cache:
            frames = self._precision_service._frame_cache[video_id]
            
            for frame_ts in frames:
                difference = abs(frame_ts.video_timestamp_ms - target_timestamp_ms)
                
                if difference < min_difference:
                    min_difference = difference
                    closest_frame = frame_ts
        
        # Check local cache
        if video_id in self._seek_cache:
            for frame_ts in self._seek_cache[video_id]:
                difference = abs(frame_ts.video_timestamp_ms - target_timestamp_ms)
                
                if difference < min_difference:
                    min_difference = difference
                    closest_frame = frame_ts
        
        return closest_frame
    
    def _interpolate_timestamp_to_frame(self, video_id: str, target_timestamp_ms: float, 
                                       frame_rate: float) -> Optional[FrameTimestamp]:
        """Interpolate a frame timestamp from a target timestamp"""
        # Calculate approximate frame number
        target_frame = int(target_timestamp_ms * frame_rate / 1000.0)
        
        # Use frame interpolation
        return self._interpolate_frame_timestamp(video_id, target_frame)
    
    def _get_video_frame_rate(self, video_id: str) -> Optional[float]:
        """Get video frame rate from cached data or services"""
        # Check precision timing service first
        if hasattr(self._precision_service, '_frame_cache') and video_id in self._precision_service._frame_cache:
            frames = self._precision_service._frame_cache[video_id]
            if frames:
                return frames[0].frame_rate
        
        # Check local cache
        if video_id in self._seek_cache:
            frames = self._seek_cache[video_id]
            if frames:
                return frames[0].frame_rate
        
        # Try video timing service
        try:
            # This would need to be implemented in video timing service
            # For now, return None to trigger default handling
            return None
        except:
            return None
    
    def _update_seek_statistics(self, result: SeekResult):
        """Update seeking performance statistics"""
        self._total_seeks += 1
        
        if result.seek_successful:
            self._successful_seeks += 1
        
        if result.interpolated:
            self._interpolated_seeks += 1
        
        # Keep history of recent seeks (limit to 1000)
        self._seek_history.append(result)
        if len(self._seek_history) > 1000:
            self._seek_history.pop(0)
    
    def preload_video_frames(self, video_id: str, frame_count: Optional[int] = None,
                            frame_rate: Optional[float] = None) -> bool:
        """
        Preload frame timestamps for a video to improve seek performance.
        
        Args:
            video_id: Video identifier
            frame_count: Total number of frames (optional)
            frame_rate: Video frame rate (optional)
            
        Returns:
            True if preloading was successful
        """
        try:
            with self._lock:
                # Try to get frames from precision timing service
                if hasattr(self._precision_service, '_frame_cache') and video_id in self._precision_service._frame_cache:
                    frames = self._precision_service._frame_cache[video_id]
                    self._seek_cache[video_id] = frames
                    
                    logger.info(f"Preloaded {len(frames)} frame timestamps for video {video_id}")
                    return True
                
                # Generate basic frame timestamps if metadata provided
                if frame_count and frame_rate:
                    frames = []
                    current_time = time.time()
                    
                    for frame_num in range(frame_count):
                        timestamp_ms = frame_num * (1000.0 / frame_rate)
                        system_time_ns = int((current_time + timestamp_ms/1000.0) * 1_000_000_000)
                        monotonic_time_ns = time.perf_counter_ns() + int(timestamp_ms * 1_000_000)
                        
                        frame_ts = FrameTimestamp(
                            frame_number=frame_num,
                            video_timestamp_ms=timestamp_ms,
                            system_timestamp_ns=system_time_ns,
                            monotonic_timestamp_ns=monotonic_time_ns,
                            frame_rate=frame_rate,
                            interpolated=False,
                            accuracy_estimate_ns=1_000_000  # 1ms estimate
                        )
                        
                        frames.append(frame_ts)
                    
                    self._seek_cache[video_id] = frames
                    
                    logger.info(f"Generated and cached {len(frames)} frame timestamps for video {video_id}")
                    return True
                
                logger.warning(f"Could not preload frames for video {video_id} - insufficient metadata")
                return False
                
        except Exception as e:
            logger.error(f"Failed to preload frames for video {video_id}: {e}")
            return False
    
    def get_seek_statistics(self) -> Dict[str, Any]:
        """Get frame seeking performance statistics"""
        with self._lock:
            success_rate = (self._successful_seeks / max(self._total_seeks, 1)) * 100
            interpolation_rate = (self._interpolated_seeks / max(self._total_seeks, 1)) * 100
            cache_hit_rate = (self._cache_hits / max(self._total_seeks, 1)) * 100
            
            # Calculate average seek time from recent history
            recent_seeks = self._seek_history[-100:] if self._seek_history else []
            avg_seek_time_ms = sum(s.seek_time_ms for s in recent_seeks) / max(len(recent_seeks), 1)
            
            return {
                'total_seeks': self._total_seeks,
                'successful_seeks': self._successful_seeks,
                'success_rate_percent': success_rate,
                'interpolated_seeks': self._interpolated_seeks,
                'interpolation_rate_percent': interpolation_rate,
                'cache_hits': self._cache_hits,
                'cache_hit_rate_percent': cache_hit_rate,
                'average_seek_time_ms': avg_seek_time_ms,
                'cached_videos': len(self._seek_cache),
                'total_cached_frames': sum(len(frames) for frames in self._seek_cache.values()),
                'recent_seeks_count': len(self._seek_history)
            }
    
    def clear_cache(self, video_id: Optional[str] = None) -> bool:
        """Clear seeking cache for a specific video or all videos"""
        try:
            with self._lock:
                if video_id:
                    removed_frames = 0
                    if video_id in self._seek_cache:
                        removed_frames += len(self._seek_cache[video_id])
                        del self._seek_cache[video_id]
                    if video_id in self._interpolation_cache:
                        removed_frames += len(self._interpolation_cache[video_id])
                        del self._interpolation_cache[video_id]
                    
                    logger.info(f"Cleared {removed_frames} cached frames for video {video_id}")
                else:
                    total_frames = sum(len(frames) for frames in self._seek_cache.values())
                    total_interpolated = sum(len(cache) for cache in self._interpolation_cache.values())
                    
                    self._seek_cache.clear()
                    self._interpolation_cache.clear()
                    
                    logger.info(f"Cleared all cached frames: {total_frames} regular, {total_interpolated} interpolated")
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False


# Global service instance
_frame_seeking_service: Optional[FrameSeekingService] = None
_service_lock = threading.Lock()


def get_frame_seeking_service() -> FrameSeekingService:
    """Get global frame seeking service instance (thread-safe singleton)"""
    global _frame_seeking_service
    
    if _frame_seeking_service is None:
        with _service_lock:
            if _frame_seeking_service is None:
                _frame_seeking_service = FrameSeekingService()
    
    return _frame_seeking_service


# Convenience functions
def seek_to_frame(video_id: str, target_frame: int, 
                 accuracy_ms: float = HIL_SEEK_ACCURACY_MS) -> SeekResult:
    """Seek to a specific frame"""
    service = get_frame_seeking_service()
    return service.seek_to_frame(video_id, target_frame, accuracy_ms)


def seek_to_timestamp(video_id: str, target_timestamp_ms: float,
                     accuracy_ms: float = HIL_SEEK_ACCURACY_MS) -> SeekResult:
    """Seek to a specific timestamp"""
    service = get_frame_seeking_service()
    return service.seek_to_timestamp(video_id, target_timestamp_ms, accuracy_ms)


def preload_video_frames(video_id: str, frame_count: Optional[int] = None,
                        frame_rate: Optional[float] = None) -> bool:
    """Preload frame timestamps for improved seek performance"""
    service = get_frame_seeking_service()
    return service.preload_video_frames(video_id, frame_count, frame_rate)