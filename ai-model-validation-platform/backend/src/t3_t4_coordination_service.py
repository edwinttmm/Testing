#!/usr/bin/env python3
"""
T3-T4 Coordination Service for HIL Testing
Phase 2: Complete timing pipeline coordination between YOLO detection and LabJack monitoring

This module provides:
- Coordination between T3 YOLO detection events and T4 LabJack signal events
- Complete timing pipeline calculation (T0->T1->T3->T4)
- Latency analysis and validation against HIL requirements
- Real-time correlation of detection events with hardware signals

Timing Pipeline:
- T0: Command Start Timestamp (presentation command initiated)
- T1: Video Display Timestamp (video frame displayed on screen)  
- T3: YOLO Detection Timestamp (AI model detects VRU)
- T4: LabJack Signal Timestamp (hardware signal triggered)

Latencies:
- T1-T0: Presentation Delay (display latency)
- T3-T1: Detection Delay (AI processing time from display to detection)
- T4-T3: Signal Delay (detection to hardware response)
- T4-T0: Total System Latency (end-to-end system response)

Author: AI Model Validation Platform Team
Version: 1.0.0 - Phase 2 Implementation
"""

import asyncio
import logging
import time
import uuid
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass
import threading
from queue import Queue, Empty
import statistics

# Database integration
from sqlalchemy.orm import Session
import sys
from pathlib import Path

# Add backend root to path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from database import get_db
    from models import TestSession, DetectionEvent
    from src.hil_t3_yolo_pipeline import T3DetectionEvent, get_t3_database_service
    # TODO: Import LabJack monitoring service when available
    # from services.dedicated_labjack_monitor import LabJackEvent
except ImportError as e:
    logging.warning(f"Import error: {e}")
    get_db = None
    TestSession = None
    DetectionEvent = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Precision timing imports
try:
    import time_ns
except ImportError:
    def time_ns():
        return int(time.time() * 1_000_000_000)

@dataclass
class T4LabJackEvent:
    """T4 LabJack hardware signal event (mock for development)"""
    event_id: str
    test_session_id: str
    t4_labjack_timestamp: float
    t4_labjack_timestamp_ns: str
    voltage_level: float
    detection_channel: str
    signal_quality: str = "high"
    
    # Raw LabJack data
    raw_voltage_reading: float = 0.0
    channel_config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.channel_config is None:
            self.channel_config = {}

@dataclass
class TimingPipelineEvent:
    """Complete timing pipeline event with T0-T1-T3-T4 correlation"""
    correlation_id: str
    test_session_id: str
    
    # T0: Command Start (if available)
    t0_command_timestamp: Optional[float] = None
    t0_command_timestamp_ns: Optional[str] = None
    
    # T1: Video Display (if available)  
    t1_display_timestamp: Optional[float] = None
    t1_display_timestamp_ns: Optional[str] = None
    
    # T3: YOLO Detection
    t3_detection_event: T3DetectionEvent = None
    t3_detection_timestamp: float = 0.0
    t3_detection_timestamp_ns: str = "0"
    
    # T4: LabJack Signal
    t4_labjack_event: T4LabJackEvent = None
    t4_labjack_timestamp: float = 0.0
    t4_labjack_timestamp_ns: str = "0"
    
    # Calculated Latencies (milliseconds)
    t1_t0_presentation_delay_ms: Optional[float] = None  # Display latency
    t3_t1_detection_delay_ms: Optional[float] = None    # AI processing delay
    t4_t3_signal_delay_ms: Optional[float] = None       # Detection to signal delay
    t4_t0_total_latency_ms: Optional[float] = None      # Total system latency
    
    # Validation Results
    validation_result: str = "pending"  # "pass", "fail", "error", "timeout"
    latency_threshold_ms: float = 100.0
    validation_notes: List[str] = None
    
    # Correlation Quality
    correlation_confidence: float = 0.0  # 0-1 confidence in T3-T4 correlation
    timing_accuracy_estimate_ns: float = 1000000.0  # Estimated accuracy in nanoseconds
    
    # Metadata
    correlation_timestamp: float = 0.0
    correlation_method: str = "temporal_proximity"
    
    def __post_init__(self):
        if self.validation_notes is None:
            self.validation_notes = []
        if self.correlation_timestamp == 0.0:
            self.correlation_timestamp = time.time()
        
        # Calculate latencies if both T3 and T4 events exist
        self._calculate_latencies()
    
    def _calculate_latencies(self):
        """Calculate all timing pipeline latencies"""
        try:
            # T4-T3 Signal Delay (most important for HIL validation)
            if self.t3_detection_timestamp > 0 and self.t4_labjack_timestamp > 0:
                self.t4_t3_signal_delay_ms = (self.t4_labjack_timestamp - self.t3_detection_timestamp) * 1000
            
            # T3-T1 Detection Delay (AI processing time)
            if self.t1_display_timestamp and self.t3_detection_timestamp > 0:
                self.t3_t1_detection_delay_ms = (self.t3_detection_timestamp - self.t1_display_timestamp) * 1000
            
            # T1-T0 Presentation Delay (display latency)
            if self.t0_command_timestamp and self.t1_display_timestamp:
                self.t1_t0_presentation_delay_ms = (self.t1_display_timestamp - self.t0_command_timestamp) * 1000
            
            # T4-T0 Total System Latency (end-to-end)
            if self.t0_command_timestamp and self.t4_labjack_timestamp > 0:
                self.t4_t0_total_latency_ms = (self.t4_labjack_timestamp - self.t0_command_timestamp) * 1000
            
            # Validate against threshold
            self._validate_latencies()
            
        except Exception as e:
            logger.error(f"Latency calculation error: {e}")
            self.validation_notes.append(f"Latency calculation failed: {e}")
    
    def _validate_latencies(self):
        """Validate latencies against HIL requirements"""
        try:
            # Primary validation: T4-T3 signal delay
            if self.t4_t3_signal_delay_ms is not None:
                if self.t4_t3_signal_delay_ms <= self.latency_threshold_ms:
                    self.validation_result = "pass"
                    self.validation_notes.append(f"Signal delay {self.t4_t3_signal_delay_ms:.2f}ms within threshold")
                else:
                    self.validation_result = "fail"
                    self.validation_notes.append(f"Signal delay {self.t4_t3_signal_delay_ms:.2f}ms exceeds threshold {self.latency_threshold_ms}ms")
            
            # Additional validation checks
            if self.t4_t0_total_latency_ms is not None and self.t4_t0_total_latency_ms > 500:
                self.validation_notes.append(f"Total system latency {self.t4_t0_total_latency_ms:.2f}ms is high")
            
            if self.t3_t1_detection_delay_ms is not None and self.t3_t1_detection_delay_ms > 200:
                self.validation_notes.append(f"AI detection delay {self.t3_t1_detection_delay_ms:.2f}ms is high")
                
        except Exception as e:
            self.validation_result = "error"
            self.validation_notes.append(f"Validation error: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses and database storage"""
        return {
            'correlation_id': self.correlation_id,
            'test_session_id': self.test_session_id,
            
            # Timestamps
            't0_command_timestamp': self.t0_command_timestamp,
            't1_display_timestamp': self.t1_display_timestamp,
            't3_detection_timestamp': self.t3_detection_timestamp,
            't4_labjack_timestamp': self.t4_labjack_timestamp,
            
            # Nanosecond precision timestamps
            't0_command_timestamp_ns': self.t0_command_timestamp_ns,
            't1_display_timestamp_ns': self.t1_display_timestamp_ns,
            't3_detection_timestamp_ns': self.t3_detection_timestamp_ns,
            't4_labjack_timestamp_ns': self.t4_labjack_timestamp_ns,
            
            # Calculated latencies
            't1_t0_presentation_delay_ms': self.t1_t0_presentation_delay_ms,
            't3_t1_detection_delay_ms': self.t3_t1_detection_delay_ms,
            't4_t3_signal_delay_ms': self.t4_t3_signal_delay_ms,
            't4_t0_total_latency_ms': self.t4_t0_total_latency_ms,
            
            # Validation
            'validation_result': self.validation_result,
            'latency_threshold_ms': self.latency_threshold_ms,
            'validation_notes': self.validation_notes,
            
            # Correlation metadata
            'correlation_confidence': self.correlation_confidence,
            'timing_accuracy_estimate_ns': self.timing_accuracy_estimate_ns,
            'correlation_timestamp': self.correlation_timestamp,
            'correlation_method': self.correlation_method,
            
            # Event data
            't3_detection_data': self.t3_detection_event.to_dict() if self.t3_detection_event else None,
            't4_labjack_data': {
                'voltage_level': self.t4_labjack_event.voltage_level,
                'detection_channel': self.t4_labjack_event.detection_channel,
                'signal_quality': self.t4_labjack_event.signal_quality
            } if self.t4_labjack_event else None
        }

class T3T4CoordinationService:
    """Service for coordinating T3 YOLO detection events with T4 LabJack signal events"""
    
    def __init__(self, correlation_window_ms: float = 500.0, max_pending_events: int = 1000):
        self.correlation_window_ms = correlation_window_ms  # Time window for T3-T4 correlation
        self.max_pending_events = max_pending_events
        
        # Event storage
        self.pending_t3_events = Queue(maxsize=max_pending_events)
        self.pending_t4_events = Queue(maxsize=max_pending_events)
        self.correlated_events = Queue(maxsize=max_pending_events * 2)
        
        # Session state
        self.current_session_id = None
        self.is_coordinating = False
        self.coordination_lock = threading.Lock()
        
        # Event callbacks
        self.correlation_callbacks = []
        
        # Statistics
        self.stats = {
            'total_t3_events': 0,
            'total_t4_events': 0,
            'successful_correlations': 0,
            'failed_correlations': 0,
            'average_t4_t3_latency_ms': 0.0,
            'correlation_success_rate': 0.0,
            'session_start_time': None
        }
        
        # Database service
        self.db_service = None
    
    async def initialize(self) -> bool:
        """Initialize the T3-T4 coordination service"""
        try:
            logger.info("Initializing T3-T4 Coordination Service...")
            
            # Initialize database service
            self.db_service = get_t3_database_service()
            
            logger.info("T3-T4 Coordination Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"T3-T4 Coordination Service initialization failed: {e}")
            return False
    
    async def start_coordination_for_session(self, session_id: str, 
                                           latency_threshold_ms: float = 100.0) -> bool:
        """Start T3-T4 coordination for HIL test session"""
        try:
            logger.info(f"Starting T3-T4 coordination for session {session_id}")
            
            with self.coordination_lock:
                if self.is_coordinating:
                    logger.warning("T3-T4 coordination already in progress")
                    return False
                
                self.current_session_id = session_id
                self.latency_threshold_ms = latency_threshold_ms
                self.is_coordinating = True
                
                # Reset statistics
                self.stats = {
                    'total_t3_events': 0,
                    'total_t4_events': 0,
                    'successful_correlations': 0,
                    'failed_correlations': 0,
                    'average_t4_t3_latency_ms': 0.0,
                    'correlation_success_rate': 0.0,
                    'session_start_time': time.time()
                }
                
                # Clear event queues
                self._clear_event_queues()
            
            logger.info(f"T3-T4 coordination started for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start T3-T4 coordination: {e}")
            return False
    
    async def stop_coordination(self) -> Dict[str, Any]:
        """Stop T3-T4 coordination and return session statistics"""
        try:
            logger.info(f"Stopping T3-T4 coordination for session {self.current_session_id}")
            
            with self.coordination_lock:
                self.is_coordinating = False
                
                # Process any remaining pending events
                await self._process_pending_correlations(force_timeout=True)
                
                # Calculate final statistics
                session_duration = time.time() - self.stats['session_start_time'] if self.stats['session_start_time'] else 0
                total_attempts = self.stats['successful_correlations'] + self.stats['failed_correlations']
                success_rate = self.stats['successful_correlations'] / total_attempts * 100 if total_attempts > 0 else 0
                
                final_stats = {
                    'session_id': self.current_session_id,
                    'coordination_duration_seconds': session_duration,
                    'total_t3_events': self.stats['total_t3_events'],
                    'total_t4_events': self.stats['total_t4_events'],
                    'successful_correlations': self.stats['successful_correlations'],
                    'failed_correlations': self.stats['failed_correlations'],
                    'correlation_success_rate_percent': success_rate,
                    'average_t4_t3_latency_ms': self.stats['average_t4_t3_latency_ms']
                }
                
                # Reset session state
                self.current_session_id = None
                
                logger.info(f"T3-T4 coordination stopped: {final_stats}")
                return final_stats
            
        except Exception as e:
            logger.error(f"Error stopping T3-T4 coordination: {e}")
            return {}
    
    async def process_t3_detection_event(self, t3_event: T3DetectionEvent) -> bool:
        """Process T3 YOLO detection event for correlation"""
        if not self.is_coordinating:
            return False
        
        try:
            # Add T3 event to pending queue
            self.pending_t3_events.put_nowait(t3_event)
            
            # Update statistics
            with self.coordination_lock:
                self.stats['total_t3_events'] += 1
            
            # Attempt correlation with existing T4 events
            await self._attempt_t3_correlation(t3_event)
            
            logger.debug(f"Processed T3 detection event: {t3_event.detection_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing T3 event: {e}")
            return False
    
    async def process_t4_labjack_event(self, t4_event: T4LabJackEvent) -> bool:
        """Process T4 LabJack signal event for correlation"""
        if not self.is_coordinating:
            return False
        
        try:
            # Add T4 event to pending queue
            self.pending_t4_events.put_nowait(t4_event)
            
            # Update statistics
            with self.coordination_lock:
                self.stats['total_t4_events'] += 1
            
            # Attempt correlation with existing T3 events
            await self._attempt_t4_correlation(t4_event)
            
            logger.debug(f"Processed T4 LabJack event: {t4_event.event_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing T4 event: {e}")
            return False
    
    async def _attempt_t3_correlation(self, t3_event: T3DetectionEvent) -> Optional[TimingPipelineEvent]:
        """Attempt to correlate T3 event with existing T4 events"""
        try:
            best_t4_match = None
            best_correlation_score = 0.0
            correlation_window_seconds = self.correlation_window_ms / 1000.0
            
            # Search through pending T4 events for correlation
            pending_t4_events = []
            while not self.pending_t4_events.empty():
                try:
                    t4_event = self.pending_t4_events.get_nowait()
                    pending_t4_events.append(t4_event)
                    
                    # Calculate temporal proximity
                    time_diff = abs(t4_event.t4_labjack_timestamp - t3_event.t3_detection_timestamp)
                    
                    if time_diff <= correlation_window_seconds:
                        # Calculate correlation score (inverse of time difference)
                        correlation_score = 1.0 - (time_diff / correlation_window_seconds)
                        
                        if correlation_score > best_correlation_score:
                            best_correlation_score = correlation_score
                            best_t4_match = t4_event
                
                except Empty:
                    break
            
            # Put non-matched T4 events back (except the best match)
            for t4_event in pending_t4_events:
                if t4_event != best_t4_match:
                    try:
                        self.pending_t4_events.put_nowait(t4_event)
                    except:
                        pass  # Queue full, drop old events
            
            # Create correlation if match found
            if best_t4_match and best_correlation_score > 0.5:  # Minimum confidence threshold
                correlation = await self._create_timing_pipeline_event(t3_event, best_t4_match, best_correlation_score)
                await self._process_correlation(correlation)
                return correlation
            
            return None
            
        except Exception as e:
            logger.error(f"T3 correlation error: {e}")
            return None
    
    async def _attempt_t4_correlation(self, t4_event: T4LabJackEvent) -> Optional[TimingPipelineEvent]:
        """Attempt to correlate T4 event with existing T3 events"""
        try:
            best_t3_match = None
            best_correlation_score = 0.0
            correlation_window_seconds = self.correlation_window_ms / 1000.0
            
            # Search through pending T3 events for correlation
            pending_t3_events = []
            while not self.pending_t3_events.empty():
                try:
                    t3_event = self.pending_t3_events.get_nowait()
                    pending_t3_events.append(t3_event)
                    
                    # Calculate temporal proximity
                    time_diff = abs(t4_event.t4_labjack_timestamp - t3_event.t3_detection_timestamp)
                    
                    if time_diff <= correlation_window_seconds:
                        # Calculate correlation score (inverse of time difference)
                        correlation_score = 1.0 - (time_diff / correlation_window_seconds)
                        
                        if correlation_score > best_correlation_score:
                            best_correlation_score = correlation_score
                            best_t3_match = t3_event
                
                except Empty:
                    break
            
            # Put non-matched T3 events back (except the best match)
            for t3_event in pending_t3_events:
                if t3_event != best_t3_match:
                    try:
                        self.pending_t3_events.put_nowait(t3_event)
                    except:
                        pass  # Queue full, drop old events
            
            # Create correlation if match found
            if best_t3_match and best_correlation_score > 0.5:  # Minimum confidence threshold
                correlation = await self._create_timing_pipeline_event(best_t3_match, t4_event, best_correlation_score)
                await self._process_correlation(correlation)
                return correlation
            
            return None
            
        except Exception as e:
            logger.error(f"T4 correlation error: {e}")
            return None
    
    async def _create_timing_pipeline_event(self, t3_event: T3DetectionEvent, t4_event: T4LabJackEvent,
                                          correlation_confidence: float) -> TimingPipelineEvent:
        """Create complete timing pipeline event from T3 and T4 events"""
        correlation_id = str(uuid.uuid4())
        
        # Create timing pipeline event
        pipeline_event = TimingPipelineEvent(
            correlation_id=correlation_id,
            test_session_id=self.current_session_id,
            
            # T3 Data
            t3_detection_event=t3_event,
            t3_detection_timestamp=t3_event.t3_detection_timestamp,
            t3_detection_timestamp_ns=t3_event.t3_detection_timestamp_ns,
            
            # T4 Data
            t4_labjack_event=t4_event,
            t4_labjack_timestamp=t4_event.t4_labjack_timestamp,
            t4_labjack_timestamp_ns=t4_event.t4_labjack_timestamp_ns,
            
            # Correlation metadata
            correlation_confidence=correlation_confidence,
            latency_threshold_ms=getattr(self, 'latency_threshold_ms', 100.0)
        )
        
        return pipeline_event
    
    async def _process_correlation(self, correlation: TimingPipelineEvent) -> bool:
        """Process completed timing pipeline correlation"""
        try:
            # Add to correlated events queue
            self.correlated_events.put_nowait(correlation)
            
            # Update statistics
            with self.coordination_lock:
                if correlation.validation_result == "pass":
                    self.stats['successful_correlations'] += 1
                else:
                    self.stats['failed_correlations'] += 1
                
                # Update average latency
                if correlation.t4_t3_signal_delay_ms is not None:
                    current_avg = self.stats['average_t4_t3_latency_ms']
                    total_correlations = self.stats['successful_correlations'] + self.stats['failed_correlations']
                    self.stats['average_t4_t3_latency_ms'] = (
                        current_avg * (total_correlations - 1) + correlation.t4_t3_signal_delay_ms
                    ) / total_correlations
            
            # Store correlation in database
            await self._store_correlation_in_database(correlation)
            
            # Notify callbacks
            await self._notify_correlation_callbacks(correlation)
            
            logger.info(f"Processed T3-T4 correlation: {correlation.validation_result}, "
                       f"T4-T3 latency: {correlation.t4_t3_signal_delay_ms:.2f}ms")
            return True
            
        except Exception as e:
            logger.error(f"Error processing correlation: {e}")
            return False
    
    async def _store_correlation_in_database(self, correlation: TimingPipelineEvent) -> bool:
        """Store timing pipeline correlation in database"""
        if not self.db_service or not get_db:
            return False
        
        try:
            # Get database session
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                # Update the T3 detection event record with T4 correlation data
                detection_event = db.query(DetectionEvent).filter(
                    DetectionEvent.id == correlation.t3_detection_event.detection_id
                ).first()
                
                if detection_event:
                    # Update with T4 LabJack data
                    detection_event.labjack_timestamp = correlation.t4_labjack_timestamp
                    detection_event.labjack_timestamp_ns = correlation.t4_labjack_timestamp_ns
                    detection_event.actual_latency_ms = correlation.t4_t3_signal_delay_ms
                    detection_event.validation_result = correlation.validation_result
                    detection_event.labjack_voltage = correlation.t4_labjack_event.voltage_level
                    detection_event.detection_channel = correlation.t4_labjack_event.detection_channel
                    
                    # Update timing quality based on correlation confidence
                    if correlation.correlation_confidence > 0.8:
                        detection_event.timing_sync_quality = "high"
                    elif correlation.correlation_confidence > 0.6:
                        detection_event.timing_sync_quality = "medium"
                    else:
                        detection_event.timing_sync_quality = "low"
                    
                    db.commit()
                    logger.debug(f"Updated detection event {detection_event.id} with T4 correlation data")
                    return True
                else:
                    logger.warning(f"Detection event {correlation.t3_detection_event.detection_id} not found in database")
                    return False
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Database correlation storage error: {e}")
            return False
    
    def add_correlation_callback(self, callback: Callable[[TimingPipelineEvent], Any]):
        """Add callback for timing pipeline correlations"""
        self.correlation_callbacks.append(callback)
    
    def remove_correlation_callback(self, callback: Callable):
        """Remove timing pipeline correlation callback"""
        if callback in self.correlation_callbacks:
            self.correlation_callbacks.remove(callback)
    
    async def _notify_correlation_callbacks(self, correlation: TimingPipelineEvent):
        """Notify correlation callbacks"""
        for callback in self.correlation_callbacks:
            try:
                await callback(correlation)
            except Exception as e:
                logger.error(f"Correlation callback error: {e}")
    
    async def get_correlated_events(self, limit: int = 100) -> List[TimingPipelineEvent]:
        """Get completed timing pipeline correlations"""
        events = []
        count = 0
        
        try:
            while count < limit and not self.correlated_events.empty():
                event = self.correlated_events.get_nowait()
                events.append(event)
                count += 1
        except Empty:
            pass
        
        return events
    
    async def _process_pending_correlations(self, force_timeout: bool = False):
        """Process any remaining pending correlations"""
        # TODO: Implement timeout-based correlation cleanup
        pass
    
    def _clear_event_queues(self):
        """Clear all event queues"""
        while not self.pending_t3_events.empty():
            try:
                self.pending_t3_events.get_nowait()
            except Empty:
                break
        
        while not self.pending_t4_events.empty():
            try:
                self.pending_t4_events.get_nowait()
            except Empty:
                break
        
        while not self.correlated_events.empty():
            try:
                self.correlated_events.get_nowait()
            except Empty:
                break
    
    def get_coordination_statistics(self) -> Dict[str, Any]:
        """Get T3-T4 coordination statistics"""
        with self.coordination_lock:
            stats = dict(self.stats)
        
        # Calculate real-time metrics
        if stats['session_start_time']:
            coordination_duration = time.time() - stats['session_start_time']
            stats['coordination_duration_seconds'] = coordination_duration
            
            total_attempts = stats['successful_correlations'] + stats['failed_correlations']
            stats['correlation_success_rate_percent'] = (stats['successful_correlations'] / total_attempts * 100) if total_attempts > 0 else 0
        
        stats.update({
            'is_coordinating': self.is_coordinating,
            'current_session_id': self.current_session_id,
            'pending_t3_events': self.pending_t3_events.qsize(),
            'pending_t4_events': self.pending_t4_events.qsize(),
            'completed_correlations': self.correlated_events.qsize(),
            'correlation_window_ms': self.correlation_window_ms
        })
        
        return stats

# Global coordination service instance
_coordination_service_instance = None

async def get_t3_t4_coordination_service() -> T3T4CoordinationService:
    """Get or create global T3-T4 coordination service instance"""
    global _coordination_service_instance
    if _coordination_service_instance is None:
        _coordination_service_instance = T3T4CoordinationService()
        await _coordination_service_instance.initialize()
    return _coordination_service_instance

# API-compatible functions for integration
async def start_t3_t4_coordination(session_id: str, latency_threshold_ms: float = 100.0) -> bool:
    """Start T3-T4 coordination for HIL test session"""
    service = await get_t3_t4_coordination_service()
    return await service.start_coordination_for_session(session_id, latency_threshold_ms)

async def stop_t3_t4_coordination() -> Dict[str, Any]:
    """Stop T3-T4 coordination and get statistics"""
    service = await get_t3_t4_coordination_service()
    return await service.stop_coordination()

async def correlate_t3_detection_event(t3_event: T3DetectionEvent) -> bool:
    """Process T3 detection event for T4 correlation"""
    service = await get_t3_t4_coordination_service()
    return await service.process_t3_detection_event(t3_event)

# Mock T4 event creation for development/testing
def create_mock_t4_event(session_id: str, timestamp: float = None, voltage: float = 3.3) -> T4LabJackEvent:
    """Create mock T4 LabJack event for testing"""
    if timestamp is None:
        timestamp = time.time()
    
    return T4LabJackEvent(
        event_id=str(uuid.uuid4()),
        test_session_id=session_id,
        t4_labjack_timestamp=timestamp,
        t4_labjack_timestamp_ns=str(int(timestamp * 1_000_000_000)),
        voltage_level=voltage,
        detection_channel="AIN0",
        signal_quality="high"
    )

# Main execution for testing
if __name__ == "__main__":
    import asyncio
    
    async def test_coordination_service():
        """Test the T3-T4 coordination service"""
        print("🚀 Testing T3-T4 Coordination Service")
        print("=" * 60)
        
        # Initialize service
        service = await get_t3_t4_coordination_service()
        
        # Get statistics
        stats = service.get_coordination_statistics()
        print(f"Coordination Statistics: {stats}")
        
        print("\n✅ T3-T4 Coordination Service test completed!")
    
    asyncio.run(test_coordination_service())