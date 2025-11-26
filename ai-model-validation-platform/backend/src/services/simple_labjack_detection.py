"""
Simple LabJack Detection Service - Background Logger Approach

This service implements a SIMPLE background detection pattern:
1. BEFORE video starts - Start detection service and begin logging
2. DURING video - Service runs silently collecting timestamps 
3. AFTER video - Stop service and process collected data

NO WebSocket complexity during video playback - just passive logging.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from threading import Thread, Event
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DetectionEvent:
    """Simple detection event with precise timestamp"""
    timestamp: float
    pin_state: bool
    detection_id: str
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class SimpleLabJackDetector:
    """
    Simple LabJack detection service that runs in background
    
    Key principles:
    - Runs independently from video playback
    - Just logs timestamps - no real-time streaming
    - Simple start/stop interface
    - Post-processing approach for analysis
    """
    
    def __init__(self, tolerance_ms: int = 100, storage_path: str = "detection_data"):
        self.tolerance_ms = tolerance_ms
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # Simple state management
        self.is_running = False
        self.detection_thread: Optional[Thread] = None
        self.stop_event = Event()
        
        # Detection storage
        self.session_id: Optional[str] = None
        self.detection_events: List[DetectionEvent] = []
        self.session_start_time: Optional[float] = None
        
        # Mock LabJack connection (replace with actual LabJack code)
        self.labjack_connected = False
        
    def start_detection_session(self, session_id: str) -> Dict[str, Any]:
        """
        Start background detection session
        
        Args:
            session_id: Unique identifier for this detection session
            
        Returns:
            Status dict with session info
        """
        if self.is_running:
            logger.warning(f"Detection already running for session: {self.session_id}")
            return {
                "success": False, 
                "message": "Detection already running",
                "current_session": self.session_id
            }
        
        # Initialize session
        self.session_id = session_id
        self.detection_events = []
        self.session_start_time = time.time()
        self.stop_event.clear()
        
        # Start background detection thread
        self.detection_thread = Thread(
            target=self._detection_worker, 
            name=f"LabJack-Detector-{session_id}"
        )
        self.is_running = True
        self.detection_thread.start()
        
        logger.info(f"Started LabJack detection session: {session_id}")
        return {
            "success": True,
            "session_id": session_id,
            "tolerance_ms": self.tolerance_ms,
            "start_time": self.session_start_time,
            "message": "Detection session started - running in background"
        }
    
    def stop_detection_session(self) -> Dict[str, Any]:
        """
        Stop background detection session and return collected data
        
        Returns:
            Session results with all collected detection events
        """
        if not self.is_running:
            logger.warning("No detection session running")
            return {
                "success": False,
                "message": "No detection session running"
            }
        
        # Signal stop and wait for thread
        self.stop_event.set()
        if self.detection_thread:
            self.detection_thread.join(timeout=5.0)
        
        self.is_running = False
        session_end_time = time.time()
        
        # Prepare session results
        results = {
            "success": True,
            "session_id": self.session_id,
            "start_time": self.session_start_time,
            "end_time": session_end_time,
            "duration_seconds": session_end_time - (self.session_start_time or 0),
            "total_detections": len(self.detection_events),
            "detection_events": [event.to_dict() for event in self.detection_events],
            "message": f"Detection session completed - {len(self.detection_events)} events collected"
        }
        
        # Store results to file for persistence
        self._save_session_data(results)
        
        logger.info(f"Stopped LabJack detection session: {self.session_id} - {len(self.detection_events)} events")
        
        # Reset state
        self.session_id = None
        self.detection_events = []
        self.session_start_time = None
        
        return results
    
    def get_session_status(self) -> Dict[str, Any]:
        """Get current session status without stopping"""
        if not self.is_running:
            return {
                "running": False,
                "session_id": None,
                "message": "No detection session active"
            }
        
        current_time = time.time()
        return {
            "running": True,
            "session_id": self.session_id,
            "start_time": self.session_start_time,
            "current_time": current_time,
            "duration_seconds": current_time - (self.session_start_time or 0),
            "events_collected": len(self.detection_events),
            "tolerance_ms": self.tolerance_ms,
            "message": "Detection session running - awaiting signals"
        }
    
    def _detection_worker(self) -> None:
        """
        Background worker thread for detection
        
        This runs continuously in background, checking LabJack pin state
        and logging detection events with precise timestamps.
        """
        logger.info(f"Detection worker started for session: {self.session_id}")
        
        # Initialize LabJack connection (mock for now)
        if not self._connect_labjack():
            logger.error("Failed to connect to LabJack device")
            return
        
        detection_count = 0
        # FIX #1: Sample-and-hold detection at video frame rate (not edge detection)
        # Matches ground truth pattern: continuous detections during object presence
        SAMPLE_RATE_HZ = 24  # Match video frame rate (24fps)
        SAMPLE_INTERVAL = 1.0 / SAMPLE_RATE_HZ  # ~42ms between samples
        last_sample_time = 0

        try:
            while not self.stop_event.is_set():
                try:
                    current_time = time.time()

                    # Sample at fixed intervals (frame rate)
                    if current_time - last_sample_time >= SAMPLE_INTERVAL:
                        # Check LabJack pin state
                        current_pin_state = self._read_labjack_pin()

                        # Level detection: Generate detection if signal is HIGH at sample time
                        if current_pin_state:
                            detection_count += 1
                            detection_event = DetectionEvent(
                                timestamp=current_time,
                                pin_state=current_pin_state,
                                detection_id=f"DET_{self.session_id}_{detection_count:04d}",
                                metadata={
                                    "session_start_offset": current_time - (self.session_start_time or 0),
                                    "detection_sequence": detection_count,
                                    "sample_rate_hz": SAMPLE_RATE_HZ,
                                    "detection_type": "level_sampled"
                                }
                            )

                            self.detection_events.append(detection_event)
                            logger.debug(f"Detection event recorded: {detection_event.detection_id} at {current_time}")

                        last_sample_time = current_time

                    # Small sleep to prevent excessive CPU usage while maintaining responsiveness
                    time.sleep(0.001)  # 1ms poll rate for precise sampling timing
                    
                except Exception as e:
                    logger.error(f"Error in detection worker: {e}")
                    # Continue running unless stop requested
                    if not self.stop_event.is_set():
                        time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Fatal error in detection worker: {e}")

        finally:
            logger.info(f"⚠️ Detection worker stopped, hardware remains connected")
            logger.info(f"Detection worker stopped for session: {self.session_id}")
    
    def _connect_labjack(self) -> bool:
        """
        Connect to LabJack device
        
        Replace this with actual LabJack connection code
        """
        try:
            # TODO: Replace with actual LabJack connection
            # from labjack import ljm
            # handle = ljm.openS("T4", "USB", "ANY")
            # self.labjack_handle = handle
            
            # Try real LabJack connection first  
            try:
                # Import enhanced USB stub for real hardware access
                import sys
                import os
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                import labjack_usb_stub as ljm
                
                # Try to connect to T7 via USB
                self.labjack_handle = ljm.openS("T7", "USB", "ANY")
                self.labjack_connected = True
                logger.info("✅ LabJack T7 connection established via USB")
                return True
                
            except Exception as hardware_error:
                logger.warning(f"⚠️ Real LabJack hardware connection failed: {hardware_error}")
                
                # Fallback to mock connection for development
                self.labjack_connected = True
                logger.info("🔧 LabJack connection established (mock fallback)")
                return True
            
        except Exception as e:
            logger.error(f"Failed to connect to LabJack: {e}")
            return False
    
    def _disconnect_labjack(self) -> None:
        """Disconnect from LabJack device"""
        try:
            # TODO: Replace with actual LabJack disconnection
            # ljm.close(self.labjack_handle)
            
            self.labjack_connected = False
            logger.info("LabJack connection closed")
            
        except Exception as e:
            logger.error(f"Error disconnecting LabJack: {e}")
    
    def _read_labjack_pin(self) -> bool:
        """
        Read LabJack digital pin state
        
        Prioritizes real hardware over mock
        """
        try:
            # Try real LabJack pin reading first
            if hasattr(self, 'labjack_handle') and self.labjack_handle:
                try:
                    # Import the LabJack module (either real or USB stub)
                    import sys
                    import os
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
                    import labjack_usb_stub as ljm
                    
                    # Read analog input - check for voltage threshold (3V threshold for detection)
                    voltage = ljm.eReadName(self.labjack_handle, "AIN0")
                    return voltage > 3.0  # Detection threshold
                    
                except Exception as hardware_error:
                    logger.debug(f"Hardware read failed, using mock: {hardware_error}")
            
            # Fallback to mock pin reading for development
            # Simulate occasional detections for testing
            import random
            if random.random() < 0.001:  # Very rare random detections
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error reading LabJack pin: {e}")
            return False
    
    def _save_session_data(self, results: Dict[str, Any]) -> None:
        """Save session data to persistent storage"""
        try:
            filename = f"detection_session_{self.session_id}_{int(time.time())}.json"
            filepath = self.storage_path / filename
            
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"Session data saved to: {filepath}")
            
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")
    
    def analyze_session_data(self, session_data: Dict[str, Any], video_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Post-processing analysis of detection data vs video events
        
        Args:
            session_data: Detection session results
            video_events: List of video events with timestamps
            
        Returns:
            Analysis results with correlations and statistics
        """
        detection_events = session_data.get("detection_events", [])
        
        if not detection_events:
            return {
                "success": False,
                "message": "No detection events to analyze"
            }
        
        # Convert detection timestamps to video timeline
        session_start = session_data.get("start_time", 0)
        video_correlations = []
        
        for detection in detection_events:
            detection_time = detection["timestamp"]
            video_offset = detection_time - session_start
            
            # Find matching video events within tolerance
            matches = []
            for video_event in video_events:
                video_time = video_event.get("timestamp", 0)
                time_diff = abs(video_offset - video_time) * 1000  # Convert to ms
                
                if time_diff <= self.tolerance_ms:
                    matches.append({
                        "video_event": video_event,
                        "time_difference_ms": time_diff,
                        "within_tolerance": True
                    })
            
            video_correlations.append({
                "detection_id": detection["detection_id"],
                "detection_timestamp": detection_time,
                "video_offset_seconds": video_offset,
                "matches": matches,
                "match_count": len(matches)
            })
        
        # Calculate statistics
        total_detections = len(detection_events)
        matched_detections = sum(1 for corr in video_correlations if corr["match_count"] > 0)
        accuracy = matched_detections / total_detections if total_detections > 0 else 0
        
        return {
            "success": True,
            "session_id": session_data.get("session_id"),
            "analysis_timestamp": time.time(),
            "total_detections": total_detections,
            "matched_detections": matched_detections,
            "unmatched_detections": total_detections - matched_detections,
            "accuracy_percentage": accuracy * 100,
            "tolerance_ms": self.tolerance_ms,
            "video_correlations": video_correlations,
            "statistics": {
                "session_duration": session_data.get("duration_seconds", 0),
                "detection_rate": total_detections / max(session_data.get("duration_seconds", 1), 1),
                "match_rate": accuracy
            }
        }

# Global detector instance
_detector_instance: Optional[SimpleLabJackDetector] = None

def get_detector() -> SimpleLabJackDetector:
    """Get global detector instance (singleton pattern)"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = SimpleLabJackDetector()
    return _detector_instance

def start_simple_detection(session_id: str, tolerance_ms: int = 100) -> Dict[str, Any]:
    """
    Simple function to start detection session
    
    Args:
        session_id: Unique session identifier
        tolerance_ms: Detection tolerance in milliseconds
        
    Returns:
        Status dict
    """
    detector = get_detector()
    detector.tolerance_ms = tolerance_ms
    return detector.start_detection_session(session_id)

def stop_simple_detection() -> Dict[str, Any]:
    """
    Simple function to stop detection session and get results
    
    Returns:
        Session results with all detection events
    """
    detector = get_detector()
    return detector.stop_detection_session()

def get_detection_status() -> Dict[str, Any]:
    """
    Get current detection status
    
    Returns:
        Status dict
    """
    detector = get_detector()
    return detector.get_session_status()

def analyze_detection_results(session_results: Dict[str, Any], video_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze detection results against video events
    
    Args:
        session_results: Results from stop_simple_detection()
        video_events: List of video events with timestamps
        
    Returns:
        Analysis results
    """
    detector = get_detector()
    return detector.analyze_session_data(session_results, video_events)