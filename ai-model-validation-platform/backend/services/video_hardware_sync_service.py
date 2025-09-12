"""
Video-Hardware Synchronization Service
PRD Module 3.3 Implementation

This service provides precise synchronization between video playback and LabJack
hardware signal detection for Hardware-in-the-Loop testing.

Features:
- Video-hardware timestamp synchronization
- Frame-accurate detection timing
- Latency calculation and validation
- Test result correlation
- Real-time sync monitoring
"""

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import queue
import uuid

# Import hardware service
from services.labjack_hardware_service import (
    get_labjack_hardware_service, 
    LabJackHardwareService,
    HardwareEvent
)

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Synchronization status"""
    IDLE = "idle"
    SYNCING = "syncing"
    SYNCHRONIZED = "synchronized"
    DRIFT_DETECTED = "drift_detected"
    ERROR = "error"


@dataclass
class VideoFrame:
    """Video frame information"""
    frame_number: int
    timestamp: datetime
    video_time_seconds: float
    frame_data: Optional[Dict[str, Any]] = None


@dataclass
class SyncEvent:
    """Synchronized event between video and hardware"""
    event_id: str
    session_id: str
    video_frame: VideoFrame
    hardware_event: Optional[HardwareEvent]
    expected_detection_time: datetime
    actual_detection_time: Optional[datetime]
    latency_ms: float
    sync_accuracy_ms: float
    detection_result: str  # "detected", "missed", "false_positive"
    created_at: datetime


@dataclass
class SyncConfiguration:
    """Synchronization configuration"""
    session_id: str
    video_source: str
    hardware_channels: List[str]
    sync_tolerance_ms: float = 50.0  # Maximum allowed sync drift
    detection_window_ms: float = 100.0  # Detection window around expected time
    frame_rate: float = 30.0  # Expected video frame rate
    enable_drift_correction: bool = True
    sync_markers: bool = False  # Use sync markers for timing reference


class VideoHardwareSyncService:
    """
    Video-Hardware Synchronization Service
    
    Provides precise synchronization between video playback and LabJack hardware
    signal detection for accurate HIL testing latency measurements.
    """
    
    def __init__(self, hardware_service: Optional[LabJackHardwareService] = None):
        self.hardware_service = hardware_service or get_labjack_hardware_service()
        
        # Synchronization state
        self.active_sessions: Dict[str, SyncConfiguration] = {}
        self.sync_status: Dict[str, SyncStatus] = {}
        self.sync_threads: Dict[str, threading.Thread] = {}
        self.stop_events: Dict[str, threading.Event] = {}
        
        # Timing data
        self.video_frames: Dict[str, List[VideoFrame]] = {}
        self.sync_events: Dict[str, List[SyncEvent]] = {}
        self.timing_reference: Dict[str, datetime] = {}  # Session start time reference
        
        # Callbacks
        self.sync_callbacks: List[Callable[[SyncEvent], None]] = []
        
        # Statistics
        self.statistics = {
            "active_sync_sessions": 0,
            "total_sync_events": 0,
            "average_latency_ms": 0.0,
            "sync_accuracy_ms": 0.0,
            "missed_detections": 0,
            "false_positives": 0
        }
        
        # Thread safety
        self.lock = threading.RLock()
        
        logger.info("🎬 Video-Hardware Synchronization Service initialized")
    
    def start_synchronization(self, config: SyncConfiguration) -> bool:
        """
        Start video-hardware synchronization for a session
        
        Args:
            config: Synchronization configuration
        
        Returns:
            True if synchronization started successfully
        """
        with self.lock:
            session_id = config.session_id
            
            if session_id in self.active_sessions:
                logger.warning(f"Synchronization already active for session {session_id}")
                return True
            
            try:
                # Initialize session state
                self.active_sessions[session_id] = config
                self.sync_status[session_id] = SyncStatus.SYNCING
                self.video_frames[session_id] = []
                self.sync_events[session_id] = []
                self.timing_reference[session_id] = datetime.now()
                self.stop_events[session_id] = threading.Event()
                
                # Setup hardware event monitoring
                self.hardware_service.add_event_callback(
                    lambda event: self._on_hardware_event(session_id, event)
                )
                
                # Start synchronization thread
                sync_thread = threading.Thread(
                    target=self._synchronization_loop,
                    args=(session_id,),
                    daemon=True,
                    name=f"VideoHardwareSync-{session_id}"
                )
                self.sync_threads[session_id] = sync_thread
                sync_thread.start()
                
                self.statistics["active_sync_sessions"] += 1
                
                logger.info(f"✅ Started video-hardware synchronization for session {session_id}")
                logger.info(f"📹 Video: {config.video_source}, Channels: {config.hardware_channels}")
                logger.info(f"⚡ Tolerance: {config.sync_tolerance_ms}ms, Window: {config.detection_window_ms}ms")
                
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to start synchronization: {e}")
                self.sync_status[session_id] = SyncStatus.ERROR
                return False
    
    def stop_synchronization(self, session_id: str) -> bool:
        """
        Stop video-hardware synchronization for a session
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if stopped successfully
        """
        with self.lock:
            if session_id not in self.active_sessions:
                logger.warning(f"No active synchronization for session {session_id}")
                return True
            
            try:
                # Signal stop to synchronization thread
                if session_id in self.stop_events:
                    self.stop_events[session_id].set()
                
                # Wait for thread to finish
                if session_id in self.sync_threads:
                    thread = self.sync_threads[session_id]
                    thread.join(timeout=5)
                    if thread.is_alive():
                        logger.warning(f"Sync thread for session {session_id} did not stop gracefully")
                
                # Clean up session state
                self._cleanup_session(session_id)
                
                if self.statistics["active_sync_sessions"] > 0:
                    self.statistics["active_sync_sessions"] -= 1
                
                logger.info(f"⏹️ Stopped video-hardware synchronization for session {session_id}")
                return True
                
            except Exception as e:
                logger.error(f"❌ Failed to stop synchronization: {e}")
                return False
    
    def register_video_frame(self, session_id: str, frame_number: int, 
                           video_time_seconds: float, frame_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a video frame for synchronization
        
        Args:
            session_id: Session identifier
            frame_number: Frame number
            video_time_seconds: Video timestamp in seconds
            frame_data: Optional frame metadata
        
        Returns:
            True if frame registered successfully
        """
        if session_id not in self.active_sessions:
            logger.warning(f"No active synchronization for session {session_id}")
            return False
        
        try:
            timestamp = datetime.now()
            
            frame = VideoFrame(
                frame_number=frame_number,
                timestamp=timestamp,
                video_time_seconds=video_time_seconds,
                frame_data=frame_data
            )
            
            with self.lock:
                if session_id not in self.video_frames:
                    self.video_frames[session_id] = []
                
                self.video_frames[session_id].append(frame)
                
                # Keep only recent frames to prevent memory issues
                if len(self.video_frames[session_id]) > 1000:
                    self.video_frames[session_id] = self.video_frames[session_id][-500:]
            
            logger.debug(f"📹 Frame registered: {frame_number} @ {video_time_seconds:.3f}s")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to register video frame: {e}")
            return False
    
    def register_expected_detection(self, session_id: str, expected_time: datetime, 
                                  detection_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Register an expected detection event
        
        Args:
            session_id: Session identifier
            expected_time: Expected detection timestamp
            detection_metadata: Optional metadata about the expected detection
        
        Returns:
            Event ID for tracking
        """
        if session_id not in self.active_sessions:
            logger.warning(f"No active synchronization for session {session_id}")
            return ""
        
        try:
            event_id = str(uuid.uuid4())
            
            # Find the closest video frame
            closest_frame = self._find_closest_video_frame(session_id, expected_time)
            
            if closest_frame:
                # Create sync event (waiting for hardware detection)
                sync_event = SyncEvent(
                    event_id=event_id,
                    session_id=session_id,
                    video_frame=closest_frame,
                    hardware_event=None,  # Will be filled when hardware event arrives
                    expected_detection_time=expected_time,
                    actual_detection_time=None,
                    latency_ms=0.0,
                    sync_accuracy_ms=0.0,
                    detection_result="pending",
                    created_at=datetime.now()
                )
                
                with self.lock:
                    if session_id not in self.sync_events:
                        self.sync_events[session_id] = []
                    self.sync_events[session_id].append(sync_event)
                
                logger.info(f"⏰ Expected detection registered: {event_id} @ {expected_time.isoformat()}")
                return event_id
            
            else:
                logger.warning(f"No video frame found near expected detection time: {expected_time}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Failed to register expected detection: {e}")
            return ""
    
    def _on_hardware_event(self, session_id: str, hardware_event: HardwareEvent):
        """Handle hardware detection event"""
        if session_id not in self.active_sessions:
            return
        
        try:
            config = self.active_sessions[session_id]
            
            # Find matching expected detection within time window
            detection_window = timedelta(milliseconds=config.detection_window_ms)
            matched_event = None
            
            with self.lock:
                session_events = self.sync_events.get(session_id, [])
                
                for sync_event in session_events:
                    if sync_event.detection_result == "pending":
                        time_diff = abs(hardware_event.signal_received_time - sync_event.expected_detection_time)
                        
                        if time_diff <= detection_window:
                            # Match found
                            sync_event.hardware_event = hardware_event
                            sync_event.actual_detection_time = hardware_event.signal_received_time
                            sync_event.latency_ms = (
                                hardware_event.signal_received_time - sync_event.expected_detection_time
                            ).total_seconds() * 1000
                            sync_event.sync_accuracy_ms = time_diff.total_seconds() * 1000
                            sync_event.detection_result = "detected"
                            
                            matched_event = sync_event
                            break
            
            if matched_event:
                # Update statistics
                self.statistics["total_sync_events"] += 1
                self._update_statistics(matched_event)
                
                # Notify callbacks
                self._notify_sync_callbacks(matched_event)
                
                logger.info(f"🎯 Detection synchronized: {matched_event.event_id} "
                           f"(latency: {matched_event.latency_ms:.1f}ms, "
                           f"accuracy: {matched_event.sync_accuracy_ms:.1f}ms)")
            else:
                # Potential false positive
                self.statistics["false_positives"] += 1
                logger.warning(f"🚨 Unmatched hardware event: {hardware_event.event_id}")
        
        except Exception as e:
            logger.error(f"❌ Error processing hardware event: {e}")
    
    def _find_closest_video_frame(self, session_id: str, target_time: datetime) -> Optional[VideoFrame]:
        """Find the video frame closest to the target time"""
        session_frames = self.video_frames.get(session_id, [])
        
        if not session_frames:
            return None
        
        # Find frame with minimum time difference
        closest_frame = None
        min_diff = float('inf')
        
        for frame in session_frames:
            time_diff = abs((target_time - frame.timestamp).total_seconds())
            if time_diff < min_diff:
                min_diff = time_diff
                closest_frame = frame
        
        return closest_frame
    
    def _synchronization_loop(self, session_id: str):
        """Main synchronization monitoring loop"""
        try:
            config = self.active_sessions[session_id]
            stop_event = self.stop_events[session_id]
            
            self.sync_status[session_id] = SyncStatus.SYNCHRONIZED
            
            logger.info(f"🔄 Synchronization loop started for session {session_id}")
            
            while not stop_event.is_set():
                try:
                    # Check for missed detections
                    self._check_missed_detections(session_id, config)
                    
                    # Monitor sync drift
                    if config.enable_drift_correction:
                        self._monitor_sync_drift(session_id, config)
                    
                    # Sleep before next check
                    time.sleep(1.0)
                
                except Exception as e:
                    logger.error(f"❌ Error in synchronization loop: {e}")
                    time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"❌ Fatal error in synchronization loop: {e}")
            self.sync_status[session_id] = SyncStatus.ERROR
        
        finally:
            if session_id in self.sync_status:
                self.sync_status[session_id] = SyncStatus.IDLE
            logger.info(f"🏁 Synchronization loop ended for session {session_id}")
    
    def _check_missed_detections(self, session_id: str, config: SyncConfiguration):
        """Check for missed detections and mark them"""
        current_time = datetime.now()
        timeout_threshold = timedelta(milliseconds=config.detection_window_ms * 2)
        
        with self.lock:
            session_events = self.sync_events.get(session_id, [])
            
            for sync_event in session_events:
                if (sync_event.detection_result == "pending" and 
                    current_time - sync_event.expected_detection_time > timeout_threshold):
                    
                    sync_event.detection_result = "missed"
                    sync_event.latency_ms = float('inf')  # Missed detection
                    
                    self.statistics["missed_detections"] += 1
                    
                    logger.warning(f"⚠️ Missed detection: {sync_event.event_id}")
                    
                    # Notify callbacks
                    self._notify_sync_callbacks(sync_event)
    
    def _monitor_sync_drift(self, session_id: str, config: SyncConfiguration):
        """Monitor synchronization drift and apply corrections"""
        try:
            session_events = self.sync_events.get(session_id, [])
            recent_events = [e for e in session_events 
                           if e.detection_result == "detected" 
                           and e.created_at > datetime.now() - timedelta(minutes=1)]
            
            if len(recent_events) >= 3:
                # Calculate average sync accuracy
                avg_accuracy = sum(e.sync_accuracy_ms for e in recent_events) / len(recent_events)
                
                if avg_accuracy > config.sync_tolerance_ms:
                    self.sync_status[session_id] = SyncStatus.DRIFT_DETECTED
                    logger.warning(f"⚠️ Sync drift detected: {avg_accuracy:.1f}ms > {config.sync_tolerance_ms:.1f}ms")
                else:
                    self.sync_status[session_id] = SyncStatus.SYNCHRONIZED
            
        except Exception as e:
            logger.error(f"❌ Error monitoring sync drift: {e}")
    
    def _update_statistics(self, sync_event: SyncEvent):
        """Update synchronization statistics"""
        try:
            # Update average latency
            total_events = self.statistics["total_sync_events"]
            current_avg = self.statistics["average_latency_ms"]
            
            if sync_event.latency_ms != float('inf'):  # Don't include missed detections
                new_avg = ((current_avg * (total_events - 1)) + sync_event.latency_ms) / total_events
                self.statistics["average_latency_ms"] = new_avg
            
            # Update sync accuracy
            current_accuracy = self.statistics["sync_accuracy_ms"]
            new_accuracy = ((current_accuracy * (total_events - 1)) + sync_event.sync_accuracy_ms) / total_events
            self.statistics["sync_accuracy_ms"] = new_accuracy
            
        except Exception as e:
            logger.error(f"❌ Error updating statistics: {e}")
    
    def _notify_sync_callbacks(self, sync_event: SyncEvent):
        """Notify synchronization callbacks"""
        for callback in self.sync_callbacks:
            try:
                callback(sync_event)
            except Exception as e:
                logger.error(f"❌ Error in sync callback: {e}")
    
    def add_sync_callback(self, callback: Callable[[SyncEvent], None]):
        """Add callback for synchronization events"""
        self.sync_callbacks.append(callback)
    
    def remove_sync_callback(self, callback: Callable[[SyncEvent], None]):
        """Remove synchronization callback"""
        if callback in self.sync_callbacks:
            self.sync_callbacks.remove(callback)
    
    def get_session_sync_events(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all synchronization events for a session"""
        with self.lock:
            session_events = self.sync_events.get(session_id, [])
            return [asdict(event) for event in session_events]
    
    def get_sync_status(self, session_id: str) -> Dict[str, Any]:
        """Get synchronization status for a session"""
        if session_id not in self.active_sessions:
            return {
                "session_id": session_id,
                "status": "not_found",
                "error": "Session not found"
            }
        
        config = self.active_sessions[session_id]
        status = self.sync_status.get(session_id, SyncStatus.IDLE)
        
        with self.lock:
            session_events = self.sync_events.get(session_id, [])
            session_frames = self.video_frames.get(session_id, [])
            
            detected_events = [e for e in session_events if e.detection_result == "detected"]
            missed_events = [e for e in session_events if e.detection_result == "missed"]
            pending_events = [e for e in session_events if e.detection_result == "pending"]
        
        return {
            "session_id": session_id,
            "status": status.value,
            "config": asdict(config),
            "statistics": {
                "total_events": len(session_events),
                "detected_events": len(detected_events),
                "missed_events": len(missed_events),
                "pending_events": len(pending_events),
                "video_frames": len(session_frames),
                "average_latency_ms": sum(e.latency_ms for e in detected_events) / len(detected_events) if detected_events else 0.0,
                "detection_rate": len(detected_events) / len(session_events) if session_events else 0.0
            },
            "timing_reference": self.timing_reference.get(session_id, datetime.now()).isoformat()
        }
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get status for all active sessions"""
        return [self.get_sync_status(sid) for sid in self.active_sessions.keys()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall synchronization statistics"""
        return {
            **self.statistics,
            "sessions_active": len(self.active_sessions),
            "detection_rate": (
                (self.statistics["total_sync_events"] - self.statistics["missed_detections"]) / 
                max(1, self.statistics["total_sync_events"])
            ) * 100.0,
            "false_positive_rate": (
                self.statistics["false_positives"] / 
                max(1, self.statistics["total_sync_events"])
            ) * 100.0
        }
    
    def _cleanup_session(self, session_id: str):
        """Clean up session resources"""
        with self.lock:
            self.active_sessions.pop(session_id, None)
            self.sync_status.pop(session_id, None)
            self.sync_threads.pop(session_id, None)
            self.stop_events.pop(session_id, None)
            self.timing_reference.pop(session_id, None)
            
            # Keep sync events and video frames for analysis
            # These can be cleaned up separately if needed
    
    def cleanup_session_data(self, session_id: str):
        """Clean up all data for a session"""
        with self.lock:
            self.video_frames.pop(session_id, None)
            self.sync_events.pop(session_id, None)


# Global service instance
_sync_service: Optional[VideoHardwareSyncService] = None


def get_video_hardware_sync_service() -> VideoHardwareSyncService:
    """Get global video-hardware synchronization service instance"""
    global _sync_service
    if _sync_service is None:
        _sync_service = VideoHardwareSyncService()
    return _sync_service


# Export key classes and functions
__all__ = [
    "VideoHardwareSyncService",
    "SyncStatus",
    "VideoFrame", 
    "SyncEvent",
    "SyncConfiguration",
    "get_video_hardware_sync_service"
]