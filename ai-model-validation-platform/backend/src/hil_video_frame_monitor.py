#!/usr/bin/env python3
"""
HIL Video Frame Monitoring Service with T3 YOLO Detection
Phase 2: Real-time video frame monitoring during HIL test playback

This module provides:
- Real-time video frame extraction during HIL playback
- T3 YOLO detection on video frames with precise timing
- Integration with HIL test workflow and T4 LabJack monitoring
- Synchronized video playback with detection event capture

Features:
- Frame-accurate video playback synchronization
- Real-time YOLO inference with T3 timestamp capture
- Database storage of detection events with timing pipeline
- WebSocket streaming for real-time HIL monitoring

Author: AI Model Validation Platform Team
Version: 1.0.0 - Phase 2 Implementation
"""

import asyncio
import logging
import time
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
from queue import Queue, Empty
import weakref

# Core ML and CV imports
import numpy as np
import cv2

# Database integration
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add backend root to path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from database import get_db
    from models import TestSession, DetectionEvent, Video
    from src.hil_t3_yolo_pipeline import get_t3_yolo_pipeline, T3DetectionEvent, get_t3_database_service
except ImportError as e:
    logging.warning(f"Import error: {e}")
    get_db = None
    TestSession = None
    DetectionEvent = None
    Video = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Precision timing imports
try:
    import time_ns  # Python 3.7+ nanosecond timing
except ImportError:
    # Fallback for older Python versions
    def time_ns():
        return int(time.time() * 1_000_000_000)

@dataclass
class FrameProcessingResult:
    """Result of frame processing with T3 detection events"""
    frame_number: int
    video_timestamp: float
    processing_time_ms: float
    t3_detection_events: List[T3DetectionEvent]
    frame_width: int
    frame_height: int
    processing_success: bool
    error_message: Optional[str] = None

class HILVideoFrameMonitor:
    """Real-time video frame monitoring service for HIL testing with T3 YOLO detection"""
    
    def __init__(self, max_fps: float = 30.0, max_concurrent_frames: int = 4):
        self.max_fps = max_fps
        self.max_concurrent_frames = max_concurrent_frames
        self.is_monitoring = False
        self.monitoring_lock = threading.Lock()
        
        # Video playback state
        self.current_video_path = None
        self.video_cap = None
        self.video_fps = 30.0
        self.total_frames = 0
        self.current_frame_number = 0
        self.video_start_time = None
        
        # HIL session state
        self.current_session_id = None
        self.current_video_id = None
        self.hil_start_time = None
        
        # T3 pipeline integration
        self.t3_pipeline = None
        self.t3_db_service = None
        
        # Frame processing queue
        self.frame_processing_queue = asyncio.Queue(maxsize=50)
        self.processing_results_queue = Queue(maxsize=200)
        
        # Event callbacks for real-time monitoring
        self.frame_callbacks = []
        self.detection_callbacks = []
        
        # Statistics
        self.stats = {
            'total_frames_processed': 0,
            'total_detections': 0,
            'average_processing_fps': 0.0,
            'average_detection_time_ms': 0.0,
            'monitoring_duration_seconds': 0.0,
            'last_frame_time': None,
            'errors': [],
            # Software delay instrumentation
            'software_delays': {
                'slow_frame_processing': False,
                'processing_rate_drift': False
            },
            'alerts': []
        }
    
    async def initialize(self) -> bool:
        """Initialize the HIL video frame monitor"""
        try:
            logger.info("Initializing HIL Video Frame Monitor...")
            
            # Initialize T3 YOLO pipeline
            self.t3_pipeline = await get_t3_yolo_pipeline()
            if not self.t3_pipeline:
                logger.error("Failed to initialize T3 YOLO pipeline")
                return False
            
            # Initialize T3 database service
            self.t3_db_service = get_t3_database_service()
            
            logger.info("HIL Video Frame Monitor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"HIL Video Frame Monitor initialization failed: {e}")
            return False
    
    async def start_hil_monitoring(self, session_id: str, video_path: str, 
                                   video_id: str = None, start_frame: int = 0) -> bool:
        """Start HIL video monitoring with T3 detection"""
        try:
            logger.info(f"Starting HIL video monitoring for session {session_id}")
            
            with self.monitoring_lock:
                if self.is_monitoring:
                    logger.warning("HIL monitoring already in progress")
                    return False
                
                # Initialize video capture
                if not await self._initialize_video_capture(video_path, start_frame):
                    return False
                
                # Set HIL session state
                self.current_session_id = session_id
                self.current_video_id = video_id or str(uuid.uuid4())
                self.hil_start_time = time.time()
                self.video_start_time = time.time()
                
                # Start T3 pipeline for this HIL session
                await self.t3_pipeline.start_hil_session(
                    session_id, self.current_video_id, self.video_start_time
                )
                
                # Reset statistics
                self.stats = {
                    'total_frames_processed': 0,
                    'total_detections': 0,
                    'average_processing_fps': 0.0,
                    'average_detection_time_ms': 0.0,
                    'monitoring_duration_seconds': 0.0,
                    'last_frame_time': None,
                    'errors': []
                }
                
                self.is_monitoring = True
            
            logger.info(f"HIL monitoring started - Video: {Path(video_path).name}, FPS: {self.video_fps}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start HIL monitoring: {e}")
            return False
    
    async def stop_hil_monitoring(self) -> Dict[str, Any]:
        """Stop HIL video monitoring and return session statistics"""
        try:
            logger.info(f"Stopping HIL video monitoring for session {self.current_session_id}")
            
            with self.monitoring_lock:
                self.is_monitoring = False
                
                # Stop T3 pipeline
                t3_stats = await self.t3_pipeline.stop_hil_session() if self.t3_pipeline else {}
                
                # Release video capture
                if self.video_cap:
                    self.video_cap.release()
                    self.video_cap = None
                
                # Calculate final statistics
                monitoring_duration = time.time() - self.hil_start_time if self.hil_start_time else 0
                processing_fps = self.stats['total_frames_processed'] / monitoring_duration if monitoring_duration > 0 else 0
                
                final_stats = {
                    'session_id': self.current_session_id,
                    'video_id': self.current_video_id,
                    'monitoring_duration_seconds': monitoring_duration,
                    'total_frames_processed': self.stats['total_frames_processed'],
                    'total_detections': self.stats['total_detections'],
                    'processing_fps': processing_fps,
                    'average_detection_time_ms': self.stats['average_detection_time_ms'],
                    'errors_count': len(self.stats['errors']),
                    't3_pipeline_stats': t3_stats
                }
                
                # Reset session state
                self.current_session_id = None
                self.current_video_id = None
                self.hil_start_time = None
                self.video_start_time = None
                
                logger.info(f"HIL monitoring stopped: {final_stats}")
                return final_stats
            
        except Exception as e:
            logger.error(f"Error stopping HIL monitoring: {e}")
            return {}
    
    async def _initialize_video_capture(self, video_path: str, start_frame: int = 0) -> bool:
        """Initialize video capture with proper configuration"""
        try:
            self.current_video_path = video_path
            
            # Open video capture
            self.video_cap = cv2.VideoCapture(video_path)
            if not self.video_cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return False
            
            # Get video properties
            self.video_fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Validate video properties
            if self.video_fps <= 0:
                self.video_fps = 30.0  # Default fallback
            
            if self.total_frames <= 0:
                logger.warning("Could not determine total frame count")
                self.total_frames = 999999
            
            # Seek to start frame if specified
            if start_frame > 0:
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
                self.current_frame_number = start_frame
            else:
                self.current_frame_number = 0
            
            logger.info(f"Video initialized: {video_width}x{video_height} @ {self.video_fps}fps, "
                       f"{self.total_frames} frames, starting at frame {start_frame}")
            return True
            
        except Exception as e:
            logger.error(f"Video capture initialization failed: {e}")
            return False
    
    async def process_next_frame(self) -> Optional[FrameProcessingResult]:
        """Process next video frame with T3 YOLO detection"""
        if not self.is_monitoring or not self.video_cap:
            return None
        
        try:
            # Read next frame
            ret, frame = self.video_cap.read()
            if not ret:
                logger.info("Reached end of video or failed to read frame")
                return None
            
            # Calculate frame timing
            frame_start_time = time.time()
            video_timestamp = self.current_frame_number / self.video_fps
            
            # Process frame for T3 detection
            processing_start = time.time()
            t3_events = await self.t3_pipeline.process_video_frame_for_t3(
                frame, self.current_frame_number, video_timestamp
            )
            processing_time_ms = (time.time() - processing_start) * 1000
            
            # Create processing result
            result = FrameProcessingResult(
                frame_number=self.current_frame_number,
                video_timestamp=video_timestamp,
                processing_time_ms=processing_time_ms,
                t3_detection_events=t3_events,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
                processing_success=True
            )
            
            # Update statistics
            with self.monitoring_lock:
                self.stats['total_frames_processed'] += 1
                self.stats['total_detections'] += len(t3_events)
                self.stats['last_frame_time'] = frame_start_time
                
                # Update average detection time
                n = self.stats['total_frames_processed']
                if n > 1:
                    prev_avg = self.stats['average_detection_time_ms']
                    self.stats['average_detection_time_ms'] = (
                        prev_avg * (n - 1) + processing_time_ms
                    ) / n
                else:
                    self.stats['average_detection_time_ms'] = processing_time_ms

                # Software delay checks
                alerts = []
                slow_frame_threshold_ms = 120.0
                rate_drift_threshold = 0.8  # processing fps should be >= 80% of video fps

                # update monitoring duration & fps for checks
                if self.hil_start_time:
                    monitoring_duration = time.time() - self.hil_start_time
                else:
                    monitoring_duration = 0
                processing_fps = (self.stats['total_frames_processed'] / monitoring_duration) if monitoring_duration > 0 else 0

                slow = processing_time_ms > slow_frame_threshold_ms
                drift = False
                if self.video_fps > 0 and processing_fps > 0:
                    drift = (processing_fps / self.video_fps) < rate_drift_threshold

                self.stats['software_delays'] = {
                    'slow_frame_processing': bool(slow),
                    'processing_rate_drift': bool(drift)
                }
                if slow:
                    alerts.append({
                        'type': 'slow_frame_processing',
                        'severity': 'warning',
                        'message': f'Frame processing {processing_time_ms:.1f}ms exceeds {slow_frame_threshold_ms}ms'
                    })
                if drift:
                    alerts.append({
                        'type': 'processing_rate_drift',
                        'severity': 'warning',
                        'message': f'Processing rate {processing_fps:.1f}fps < 80% of video fps {self.video_fps:.1f}'
                    })
                if alerts:
                    existing = self.stats.get('alerts', [])
                    self.stats['alerts'] = (existing + alerts)[-25:]
            
            # Notify callbacks
            await self._notify_frame_callbacks(frame, result)
            await self._notify_detection_callbacks(t3_events)
            
            # Increment frame counter
            self.current_frame_number += 1
            
            if t3_events:
                logger.debug(f"Frame {self.current_frame_number}: {len(t3_events)} T3 detections "
                            f"in {processing_time_ms:.2f}ms")
            
            return result
            
        except Exception as e:
            error_msg = f"Frame processing error: {e}"
            logger.error(error_msg)
            
            # Add error to statistics
            with self.monitoring_lock:
                self.stats['errors'].append({
                    'timestamp': time.time(),
                    'frame_number': self.current_frame_number,
                    'error': error_msg
                })
            
            return FrameProcessingResult(
                frame_number=self.current_frame_number,
                video_timestamp=0.0,
                processing_time_ms=0.0,
                t3_detection_events=[],
                frame_width=0,
                frame_height=0,
                processing_success=False,
                error_message=error_msg
            )
    
    async def run_continuous_monitoring(self, frame_limit: Optional[int] = None) -> Dict[str, Any]:
        """Run continuous video monitoring with T3 detection until completion"""
        if not self.is_monitoring:
            logger.error("HIL monitoring not started")
            return {}
        
        try:
            logger.info(f"Starting continuous HIL monitoring (limit: {frame_limit})")
            
            frames_processed = 0
            start_time = time.time()
            
            # Process frames continuously
            while self.is_monitoring and (frame_limit is None or frames_processed < frame_limit):
                result = await self.process_next_frame()
                
                if result is None:
                    # End of video or error
                    break
                
                frames_processed += 1
                
                # Store T3 detection events in database
                if result.t3_detection_events and self.t3_db_service:
                    await self.t3_db_service.store_t3_detection_events(result.t3_detection_events)
                
                # Rate limiting to maintain target FPS
                if self.max_fps > 0:
                    frame_duration = 1.0 / self.max_fps
                    processing_time = time.time() - start_time - (frames_processed - 1) * frame_duration
                    if processing_time < frame_duration:
                        await asyncio.sleep(frame_duration - processing_time)
                
                # Periodic logging
                if frames_processed % 100 == 0:
                    logger.info(f"Processed {frames_processed} frames, "
                               f"{self.stats['total_detections']} total detections")
            
            monitoring_duration = time.time() - start_time
            
            # Final statistics
            final_stats = {
                'frames_processed': frames_processed,
                'monitoring_duration': monitoring_duration,
                'processing_fps': frames_processed / monitoring_duration if monitoring_duration > 0 else 0,
                'total_detections': self.stats['total_detections'],
                'average_detection_time_ms': self.stats['average_detection_time_ms'],
                'completion_reason': 'video_end' if result is None else 'frame_limit_reached'
            }
            
            logger.info(f"Continuous monitoring completed: {final_stats}")
            return final_stats
            
        except Exception as e:
            logger.error(f"Continuous monitoring error: {e}")
            return {'error': str(e)}
    
    def add_frame_callback(self, callback: Callable[[np.ndarray, FrameProcessingResult], Any]):
        """Add callback for processed frames"""
        self.frame_callbacks.append(callback)
    
    def add_detection_callback(self, callback: Callable[[List[T3DetectionEvent]], Any]):
        """Add callback for T3 detection events"""
        self.detection_callbacks.append(callback)
    
    def remove_frame_callback(self, callback: Callable):
        """Remove frame callback"""
        if callback in self.frame_callbacks:
            self.frame_callbacks.remove(callback)
    
    def remove_detection_callback(self, callback: Callable):
        """Remove detection callback"""
        if callback in self.detection_callbacks:
            self.detection_callbacks.remove(callback)
    
    async def _notify_frame_callbacks(self, frame: np.ndarray, result: FrameProcessingResult):
        """Notify frame processing callbacks"""
        for callback in self.frame_callbacks:
            try:
                await callback(frame, result)
            except Exception as e:
                logger.error(f"Frame callback error: {e}")
    
    async def _notify_detection_callbacks(self, t3_events: List[T3DetectionEvent]):
        """Notify T3 detection event callbacks"""
        if not t3_events:
            return
        
        for callback in self.detection_callbacks:
            try:
                await callback(t3_events)
            except Exception as e:
                logger.error(f"Detection callback error: {e}")
    
    def get_monitoring_statistics(self) -> Dict[str, Any]:
        """Get current monitoring statistics"""
        with self.monitoring_lock:
            stats = dict(self.stats)
        
        # Calculate real-time metrics
        if stats['last_frame_time'] and self.hil_start_time:
            monitoring_duration = time.time() - self.hil_start_time
            stats['monitoring_duration_seconds'] = monitoring_duration
            stats['average_processing_fps'] = stats['total_frames_processed'] / monitoring_duration if monitoring_duration > 0 else 0
        
        stats.update({
            'is_monitoring': self.is_monitoring,
            'current_session_id': self.current_session_id,
            'current_video_id': self.current_video_id,
            'current_frame_number': self.current_frame_number,
            'total_video_frames': self.total_frames,
            'video_fps': self.video_fps,
            'progress_percentage': (self.current_frame_number / self.total_frames * 100) if self.total_frames > 0 else 0
        })
        
        return stats
    
    async def seek_to_frame(self, frame_number: int) -> bool:
        """Seek to specific frame in video"""
        if not self.video_cap or not self.is_monitoring:
            return False
        
        try:
            if 0 <= frame_number < self.total_frames:
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                self.current_frame_number = frame_number
                logger.info(f"Seeked to frame {frame_number}")
                return True
            else:
                logger.warning(f"Frame number {frame_number} out of range (0-{self.total_frames-1})")
                return False
                
        except Exception as e:
            logger.error(f"Failed to seek to frame {frame_number}: {e}")
            return False
    
    def is_monitoring_active(self) -> bool:
        """Check if HIL monitoring is currently active"""
        return self.is_monitoring
    
    def get_current_frame_info(self) -> Dict[str, Any]:
        """Get current frame information"""
        return {
            'current_frame': self.current_frame_number,
            'total_frames': self.total_frames,
            'video_fps': self.video_fps,
            'video_timestamp': self.current_frame_number / self.video_fps if self.video_fps > 0 else 0,
            'progress_percentage': (self.current_frame_number / self.total_frames * 100) if self.total_frames > 0 else 0
        }

# Global monitor instance
_hil_monitor_instance = None

async def get_hil_video_monitor() -> HILVideoFrameMonitor:
    """Get or create global HIL video frame monitor instance"""
    global _hil_monitor_instance
    if _hil_monitor_instance is None:
        _hil_monitor_instance = HILVideoFrameMonitor()
        await _hil_monitor_instance.initialize()
    return _hil_monitor_instance

# API-compatible functions for integration
async def start_hil_video_monitoring(session_id: str, video_path: str, 
                                     video_id: str = None, start_frame: int = 0) -> bool:
    """Start HIL video monitoring with T3 detection"""
    monitor = await get_hil_video_monitor()
    return await monitor.start_hil_monitoring(session_id, video_path, video_id, start_frame)

async def stop_hil_video_monitoring() -> Dict[str, Any]:
    """Stop HIL video monitoring and get statistics"""
    monitor = await get_hil_video_monitor()
    return await monitor.stop_hil_monitoring()

async def process_hil_video_frame() -> Optional[FrameProcessingResult]:
    """Process next HIL video frame with T3 detection"""
    monitor = await get_hil_video_monitor()
    return await monitor.process_next_frame()

async def get_hil_monitoring_stats() -> Dict[str, Any]:
    """Get HIL video monitoring statistics"""
    monitor = await get_hil_video_monitor()
    return monitor.get_monitoring_statistics()

# Main execution for testing
if __name__ == "__main__":
    import asyncio
    
    async def test_hil_monitor():
        """Test the HIL video frame monitor"""
        print("🚀 Testing HIL Video Frame Monitor with T3 Detection")
        print("=" * 60)
        
        # Initialize monitor
        monitor = await get_hil_video_monitor()
        
        # Get statistics
        stats = monitor.get_monitoring_statistics()
        print(f"Monitor Statistics: {stats}")
        
        # Test frame info
        frame_info = monitor.get_current_frame_info()
        print(f"Frame Info: {frame_info}")
        
        print("\n✅ HIL Video Frame Monitor test completed!")
    
    asyncio.run(test_hil_monitor())
