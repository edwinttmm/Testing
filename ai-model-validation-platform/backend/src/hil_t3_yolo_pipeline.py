#!/usr/bin/env python3
"""
T3 YOLO Detection Event Pipeline for HIL Testing
Phase 2: Real-time YOLO detection integration with HIL workflow

This module provides:
- Real-time YOLO inference during HIL video playback
- T3 timestamp capture with nanosecond precision
- Integration with existing T0-T1 and T4 LabJack timing systems
- Database storage of detection events with complete timing pipeline

T3 = YOLO Detection Timestamp (when YOLO model detects VRU)
T4 = LabJack Signal Timestamp (hardware signal response)
Latency T4-T3 = Detection to hardware signal delay

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
from concurrent.futures import ThreadPoolExecutor
import threading
from queue import Queue, Empty

# Core ML and CV imports
import numpy as np
import cv2

# Database integration
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
from pathlib import Path

# Add backend root to path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from database import get_db
    from models import TestSession, DetectionEvent, Video
    from src.enhanced_ml_inference_engine import get_production_ml_engine, EnhancedVRUDetection
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
class T3DetectionEvent:
    """T3 YOLO Detection Event with precise timing and metadata"""
    detection_id: str
    test_session_id: str
    video_id: str
    
    # T3 YOLO Detection Timing (nanosecond precision)
    t3_detection_timestamp: float  # Unix timestamp when YOLO detected VRU
    t3_detection_timestamp_ns: str  # Nanosecond precision timestamp (string for precision)
    t3_monotonic_timestamp_ns: str  # Monotonic clock for drift compensation
    
    # YOLO Detection Data
    frame_number: int
    video_relative_timestamp: float  # Timestamp relative to video start
    yolo_confidence: float
    vru_type: str  # pedestrian, cyclist, motorcyclist
    bounding_box: Dict[str, float]  # {x, y, width, height}
    
    # Video Synchronization
    video_start_time: float  # Video playback start reference
    video_start_time_ns: str  # Nanosecond precision video start
    frame_accurate_timestamp: Optional[float] = None  # Frame-accurate timing if available
    
    # Timing Quality Metadata
    timing_sync_quality: str = "high"  # high, medium, low
    drift_compensated: bool = False
    timing_interpolated: bool = False
    
    # Processing Metadata
    processing_time_ms: float = 0.0
    model_version: str = "enhanced_yolo_v2.0.0"
    detection_source: str = "t3_yolo_realtime"
    
    def to_detection_event_dict(self) -> Dict[str, Any]:
        """Convert to DetectionEvent database model format"""
        return {
            'id': self.detection_id,
            'test_session_id': self.test_session_id,
            'video_id': self.video_id,
            
            # Main Detection Timing (T3 as primary timestamp)
            'timestamp': self.t3_detection_timestamp,
            'video_relative_timestamp': self.video_relative_timestamp,
            'frame_number': self.frame_number,
            
            # Video Synchronization Fields
            'video_start_time': self.video_start_time,
            'video_start_time_ns': self.video_start_time_ns,
            'monotonic_timestamp_ns': self.t3_monotonic_timestamp_ns,
            'frame_accurate_timestamp': self.frame_accurate_timestamp,
            'timing_sync_quality': self.timing_sync_quality,
            'drift_compensated': self.drift_compensated,
            'timing_interpolated': self.timing_interpolated,
            
            # T3 YOLO Detection Specific Fields - Phase 2 Implementation
            't3_detection_timestamp': self.t3_detection_timestamp,
            't3_detection_timestamp_ns': self.t3_detection_timestamp_ns,
            't3_monotonic_timestamp_ns': self.t3_monotonic_timestamp_ns,
            't3_processing_time_ms': self.processing_time_ms,
            't3_yolo_confidence': self.yolo_confidence,
            't3_model_version': self.model_version,
            't3_detection_quality': self.timing_sync_quality,  # Use timing quality as detection quality
            
            # Legacy/Compatible Detection Data
            'confidence': self.yolo_confidence,  # Legacy compatibility
            'vru_type': self.vru_type,
            'class_label': self.vru_type,  # Legacy compatibility
            'bounding_box_x': self.bounding_box.get('x', 0.0),
            'bounding_box_y': self.bounding_box.get('y', 0.0),
            'bounding_box_width': self.bounding_box.get('width', 0.0),
            'bounding_box_height': self.bounding_box.get('height', 0.0),
            
            # Processing Metadata
            'processing_time_ms': self.processing_time_ms,
            'model_version': self.model_version,
            'source': self.detection_source,
            'detection_type': 'automatic',
            
            # T4 Integration Placeholders (will be filled by LabJack monitoring)
            'labjack_timestamp': None,  # T4 - filled by LabJack monitor
            'labjack_timestamp_ns': None,  # T4 nanosecond precision
            'actual_latency_ms': None,  # T4-T3 latency - calculated when T4 available
            'validation_result': None,  # Pass/Fail based on T4-T3 < threshold
            'detection_channel': None,  # LabJack channel (T4)
            'labjack_voltage': None,  # LabJack voltage reading (T4)
            
            'created_at': datetime.now(timezone.utc)
        }

class T3YOLODetectionPipeline:
    """Real-time YOLO detection pipeline for HIL testing with T3 timing capture"""
    
    def __init__(self, ml_engine=None):
        self.ml_engine = ml_engine
        self.is_running = False
        self.detection_queue = Queue(maxsize=1000)
        self.event_callbacks = []
        self._processing_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # T3 Detection Statistics
        self.stats = {
            'total_detections': 0,
            'detections_per_second': 0.0,
            'average_processing_time_ms': 0.0,
            'last_detection_time': None,
            'session_start_time': None,
            # Software delay instrumentation
            'queue_size': 0,
            'software_delays': {
                'slow_inference': False,
                'queue_backlog': False,
                'stale_detections': False
            },
            'alerts': []
        }
        
        # HIL Session State
        self.current_session_id = None
        self.current_video_id = None
        self.video_start_time = None
        self.video_start_time_ns = None
        
    async def initialize(self) -> bool:
        """Initialize the T3 YOLO pipeline"""
        try:
            logger.info("Initializing T3 YOLO Detection Pipeline...")
            
            # Initialize ML engine if not provided
            if self.ml_engine is None:
                self.ml_engine = await get_production_ml_engine()
            
            # Verify ML engine is ready
            if not self.ml_engine:
                logger.error("Failed to initialize ML engine")
                return False
            
            # Test YOLO engine health
            health = await self.ml_engine.health_check()
            if health['status'] != 'healthy':
                logger.warning(f"ML engine health check: {health['status']}")
            
            logger.info("T3 YOLO Detection Pipeline initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"T3 YOLO Pipeline initialization failed: {e}")
            return False
    
    async def start_hil_session(self, session_id: str, video_id: str, video_start_time: float = None) -> bool:
        """Start T3 detection monitoring for HIL test session"""
        try:
            logger.info(f"Starting T3 detection for HIL session {session_id}")
            
            self.current_session_id = session_id
            self.current_video_id = video_id
            self.video_start_time = video_start_time or time.time()
            self.video_start_time_ns = str(time_ns())
            self.is_running = True
            
            # Reset statistics
            self.stats['total_detections'] = 0
            self.stats['session_start_time'] = time.time()
            
            logger.info(f"T3 HIL session started - Video start time: {self.video_start_time}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start T3 HIL session: {e}")
            return False
    
    async def stop_hil_session(self) -> Dict[str, Any]:
        """Stop T3 detection monitoring and return session statistics"""
        try:
            logger.info(f"Stopping T3 detection for HIL session {self.current_session_id}")
            
            self.is_running = False
            
            # Calculate session statistics
            session_duration = time.time() - self.stats['session_start_time'] if self.stats['session_start_time'] else 0
            detection_rate = self.stats['total_detections'] / session_duration if session_duration > 0 else 0
            
            session_stats = {
                'session_id': self.current_session_id,
                'video_id': self.current_video_id,
                'total_detections': self.stats['total_detections'],
                'session_duration_seconds': session_duration,
                'detection_rate_hz': detection_rate,
                'average_processing_time_ms': self.stats['average_processing_time_ms'],
                'last_detection_time': self.stats['last_detection_time']
            }
            
            # Reset session state
            self.current_session_id = None
            self.current_video_id = None
            self.video_start_time = None
            self.video_start_time_ns = None
            
            logger.info(f"T3 HIL session stopped: {session_stats}")
            return session_stats
            
        except Exception as e:
            logger.error(f"Error stopping T3 HIL session: {e}")
            return {}
    
    async def process_video_frame_for_t3(self, frame: np.ndarray, frame_number: int, 
                                        video_timestamp: float) -> List[T3DetectionEvent]:
        """Process single video frame for T3 YOLO detection with precise timing"""
        if not self.is_running or not self.current_session_id:
            return []
        
        try:
            # Capture T3 detection start time with nanosecond precision
            t3_start_time = time.time()
            t3_start_time_ns = str(time_ns())
            t3_monotonic_ns = str(time.monotonic_ns())
            
            # Run YOLO inference
            processing_start = time.time()
            yolo_detections = await self.ml_engine.yolo_engine.detect_vrus_single(
                frame, frame_number, video_timestamp
            )
            processing_time_ms = (time.time() - processing_start) * 1000
            
            # Convert YOLO detections to T3 detection events
            t3_events = []
            for yolo_detection in yolo_detections:
                # Calculate video-relative timestamp
                video_relative_timestamp = video_timestamp
                if self.video_start_time:
                    video_relative_timestamp = video_timestamp - (t3_start_time - self.video_start_time)
                
                t3_event = T3DetectionEvent(
                    detection_id=str(uuid.uuid4()),
                    test_session_id=self.current_session_id,
                    video_id=self.current_video_id,
                    
                    # T3 Precise Timing
                    t3_detection_timestamp=t3_start_time,
                    t3_detection_timestamp_ns=t3_start_time_ns,
                    t3_monotonic_timestamp_ns=t3_monotonic_ns,
                    
                    # YOLO Detection Data
                    frame_number=frame_number,
                    video_relative_timestamp=video_relative_timestamp,
                    yolo_confidence=yolo_detection.confidence,
                    vru_type=yolo_detection.vru_type,
                    bounding_box={
                        'x': yolo_detection.bounding_box.x,
                        'y': yolo_detection.bounding_box.y,
                        'width': yolo_detection.bounding_box.width,
                        'height': yolo_detection.bounding_box.height
                    },
                    
                    # Video Synchronization
                    video_start_time=self.video_start_time,
                    video_start_time_ns=self.video_start_time_ns,
                    frame_accurate_timestamp=video_timestamp,
                    
                    # Processing Metadata
                    processing_time_ms=processing_time_ms,
                    timing_sync_quality="high",  # High quality for real-time processing
                    drift_compensated=False  # TODO: Implement drift compensation
                )
                
                t3_events.append(t3_event)
            
            # Update statistics
            with self._processing_lock:
                self.stats['total_detections'] += len(t3_events)
                self.stats['last_detection_time'] = t3_start_time
                
                # Update average processing time
                n = self.stats['total_detections']
                if n > len(t3_events):
                    prev_avg = self.stats['average_processing_time_ms']
                    self.stats['average_processing_time_ms'] = (
                        prev_avg * (n - len(t3_events)) + processing_time_ms
                    ) / n
                else:
                    self.stats['average_processing_time_ms'] = processing_time_ms

                # Software delay checks (simple thresholds)
                alerts = []
                inference_threshold_ms = 120.0  # per-frame inference budget
                backlog_threshold = int(self.detection_queue.maxsize * 0.7)
                stale_threshold_s = 5.0

                slow = processing_time_ms > inference_threshold_ms
                backlog = self.detection_queue.qsize() > backlog_threshold
                stale = False
                if self.stats.get('last_detection_time'):
                    stale = (time.time() - self.stats['last_detection_time']) > stale_threshold_s and self.is_running

                self.stats['software_delays'] = {
                    'slow_inference': bool(slow),
                    'queue_backlog': bool(backlog),
                    'stale_detections': bool(stale)
                }
                if slow:
                    alerts.append({
                        'type': 'slow_inference',
                        'severity': 'warning',
                        'message': f'YOLO inference {processing_time_ms:.1f}ms exceeds {inference_threshold_ms}ms'
                    })
                if backlog:
                    alerts.append({
                        'type': 'queue_backlog',
                        'severity': 'warning',
                        'message': f'Detection queue backlog at {self.detection_queue.qsize()}/{self.detection_queue.maxsize}'
                    })
                if stale:
                    alerts.append({
                        'type': 'stale_detections',
                        'severity': 'error',
                        'message': f'No detections for > {stale_threshold_s:.0f}s while running'
                    })
                if alerts:
                    existing = self.stats.get('alerts', [])
                    self.stats['alerts'] = (existing + alerts)[-25:]
            
            # Queue events for database storage
            for event in t3_events:
                try:
                    self.detection_queue.put_nowait(event)
                except:
                    logger.warning("T3 detection queue full, dropping event")
            
            # Notify event callbacks
            for callback in self.event_callbacks:
                try:
                    await callback(t3_events)
                except Exception as e:
                    logger.error(f"T3 event callback error: {e}")
            
            if t3_events:
                logger.debug(f"T3 detected {len(t3_events)} VRUs in frame {frame_number}")
            
            return t3_events
            
        except Exception as e:
            logger.error(f"T3 frame processing error: {e}")
            return []
    
    def add_event_callback(self, callback: Callable[[List[T3DetectionEvent]], Any]):
        """Add callback for real-time T3 detection events"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable):
        """Remove T3 detection event callback"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    async def get_pending_t3_events(self) -> List[T3DetectionEvent]:
        """Get pending T3 detection events from queue"""
        events = []
        try:
            while True:
                event = self.detection_queue.get_nowait()
                events.append(event)
        except Empty:
            pass
        
        return events
    
    def get_t3_statistics(self) -> Dict[str, Any]:
        """Get T3 detection pipeline statistics"""
        with self._processing_lock:
            stats = dict(self.stats)
        
        # Calculate detection rate
        if stats['session_start_time']:
            session_duration = time.time() - stats['session_start_time']
            stats['detections_per_second'] = stats['total_detections'] / session_duration if session_duration > 0 else 0
        
        stats['is_running'] = self.is_running
        stats['current_session_id'] = self.current_session_id
        stats['current_video_id'] = self.current_video_id
        stats['queue_size'] = self.detection_queue.qsize()
        
        return stats

class T3DatabaseService:
    """Database service for storing T3 detection events"""
    
    def __init__(self):
        self.db_available = get_db is not None
        self.stats = {
            'last_write_ms': None,
            'avg_write_ms': 0.0,
            'writes': 0,
            'errors': 0,
            'alerts': []
        }
        
    async def store_t3_detection_events(self, t3_events: List[T3DetectionEvent]) -> bool:
        """Store T3 detection events in database"""
        if not self.db_available or not DetectionEvent:
            logger.warning("Database not available for T3 event storage")
            return False
        
        try:
            # Get database session
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                stored_count = 0
                write_start = time.time()
                for t3_event in t3_events:
                    # Convert T3 event to database format
                    event_data = t3_event.to_detection_event_dict()
                    
                    # Create DetectionEvent record
                    detection_event = DetectionEvent(**event_data)
                    db.add(detection_event)
                    stored_count += 1
                
                # Commit all T3 events
                db.commit()
                write_ms = (time.time() - write_start) * 1000.0
                self.stats['last_write_ms'] = write_ms
                self.stats['writes'] += 1
                n = self.stats['writes']
                prev = self.stats['avg_write_ms']
                self.stats['avg_write_ms'] = (prev * (n - 1) + write_ms) / n
                if write_ms > 100.0:
                    self.stats['alerts'] = (self.stats.get('alerts', []) + [{
                        'type': 'slow_db_write',
                        'severity': 'warning',
                        'message': f'DB commit took {write_ms:.1f}ms'
                    }])[-25:]
                
                logger.info(f"Stored {stored_count} T3 detection events to database")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Database error storing T3 events: {e}")
                self.stats['errors'] += 1
                return False
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to store T3 events: {e}")
            return False
    
    async def get_t3_events_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve T3 detection events for HIL session"""
        if not self.db_available or not DetectionEvent:
            return []
        
        try:
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                # Query T3 detection events
                t3_events = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session_id,
                    DetectionEvent.source == 't3_yolo_realtime'
                ).order_by(DetectionEvent.timestamp).all()
                
                # Convert to dictionaries
                events_data = []
                for event in t3_events:
                    event_dict = {
                        'detection_id': event.id,
                        'timestamp': event.timestamp,
                        't3_detection_timestamp_ns': event.video_start_time_ns,  # T3 nanosecond timestamp
                        'video_relative_timestamp': event.video_relative_timestamp,
                        'frame_number': event.frame_number,
                        'vru_type': event.vru_type,
                        'confidence': event.confidence,
                        'bounding_box': {
                            'x': event.bounding_box_x,
                            'y': event.bounding_box_y,
                            'width': event.bounding_box_width,
                            'height': event.bounding_box_height
                        },
                        'timing_sync_quality': event.timing_sync_quality,
                        'processing_time_ms': event.processing_time_ms,
                        'model_version': event.model_version,
                        
                        # T4 Integration Data (if available)
                        't4_labjack_timestamp': event.labjack_timestamp,
                        't4_labjack_timestamp_ns': event.labjack_timestamp_ns,
                        't4_t3_latency_ms': event.actual_latency_ms,
                        'validation_result': event.validation_result,
                        
                        'created_at': event.created_at.isoformat() if event.created_at else None
                    }
                    events_data.append(event_dict)
                
                return events_data
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to retrieve T3 events: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)

# Global T3 pipeline instance
_t3_pipeline_instance = None

async def get_t3_yolo_pipeline() -> T3YOLODetectionPipeline:
    """Get or create global T3 YOLO detection pipeline instance"""
    global _t3_pipeline_instance
    if _t3_pipeline_instance is None:
        _t3_pipeline_instance = T3YOLODetectionPipeline()
        await _t3_pipeline_instance.initialize()
    return _t3_pipeline_instance

def get_t3_database_service() -> T3DatabaseService:
    """Get T3 database service instance"""
    return T3DatabaseService()

# API-compatible functions for integration
async def start_t3_detection_for_hil_session(session_id: str, video_id: str, 
                                            video_start_time: float = None) -> bool:
    """Start T3 YOLO detection monitoring for HIL test session"""
    pipeline = await get_t3_yolo_pipeline()
    return await pipeline.start_hil_session(session_id, video_id, video_start_time)

async def stop_t3_detection_for_hil_session() -> Dict[str, Any]:
    """Stop T3 YOLO detection monitoring and get session statistics"""
    pipeline = await get_t3_yolo_pipeline()
    return await pipeline.stop_hil_session()

async def process_frame_for_t3_detection(frame: np.ndarray, frame_number: int, 
                                        video_timestamp: float) -> List[T3DetectionEvent]:
    """Process video frame for T3 YOLO detection with precise timing"""
    pipeline = await get_t3_yolo_pipeline()
    return await pipeline.process_video_frame_for_t3(frame, frame_number, video_timestamp)

async def get_t3_detection_statistics() -> Dict[str, Any]:
    """Get T3 detection pipeline performance statistics"""
    pipeline = await get_t3_yolo_pipeline()
    return pipeline.get_t3_statistics()

# Main execution for testing
if __name__ == "__main__":
    import asyncio
    
    async def test_t3_pipeline():
        """Test the T3 YOLO detection pipeline"""
        print("🚀 Testing T3 YOLO Detection Pipeline for HIL")
        print("=" * 60)
        
        # Initialize pipeline
        pipeline = await get_t3_yolo_pipeline()
        
        # Get statistics
        stats = pipeline.get_t3_statistics()
        print(f"Pipeline Statistics: {stats}")
        
        # Test database service
        db_service = get_t3_database_service()
        print(f"Database Available: {db_service.db_available}")
        
        print("\n✅ T3 YOLO Detection Pipeline test completed!")
    
    asyncio.run(test_t3_pipeline())
