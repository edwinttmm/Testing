"""
LabJack Monitoring Service for HIL Tests
Monitors LabJack voltage signals during test sessions and stores them as detection events
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional, Dict, Any
import sqlite3
import uuid

logger = logging.getLogger(__name__)

class LabJackMonitoringService:
    """Service to monitor LabJack signals during HIL test sessions"""
    
    def __init__(self):
        self.monitoring_active = False
        self.current_session_id = None
        self.monitor_thread = None
        self.sample_rate = 10  # Hz (10 samples per second)
        self._stop_event = threading.Event()
        
    def start_monitoring(self, session_id: str, sample_rate: int = 10):
        """Start monitoring LabJack signals for a test session"""
        if self.monitoring_active:
            logger.warning(f"Monitoring already active for session {self.current_session_id}")
            return False
            
        self.current_session_id = session_id
        self.sample_rate = sample_rate
        self.monitoring_active = True
        self._stop_event.clear()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(session_id,),
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"📊 Started LabJack monitoring for session {session_id} at {sample_rate}Hz")
        return True
        
    def stop_monitoring(self):
        """Stop monitoring LabJack signals"""
        if not self.monitoring_active:
            return
            
        logger.info(f"⏹️ Stopping LabJack monitoring for session {self.current_session_id}")
        self.monitoring_active = False
        self._stop_event.set()
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            
        self.current_session_id = None
        
    def _monitor_loop(self, session_id: str):
        """Background loop to monitor and store LabJack signals"""
        detection_count = 0
        logger.info(f"📊 Starting monitoring loop for session {session_id}")
        
        try:
            # Import signal validation service
            from api_signal_validation import signal_validation_service
            logger.info(f"✅ Successfully imported signal validation service")
            
            sample_interval = 1.0 / self.sample_rate
            
            while self.monitoring_active and not self._stop_event.is_set():
                try:
                    # Read voltage from LabJack
                    result = signal_validation_service.read_voltage_signal("AIN0")
                    
                    if result.get("success") and result.get("voltage") is not None:
                        voltage = result["voltage"]
                        timestamp = time.time()
                        
                        # Store as detection event if voltage exceeds threshold (e.g., 3.0V)
                        if voltage > 3.0:  # TTL high threshold
                            self._store_detection_event(
                                session_id=session_id,
                                voltage=voltage,
                                timestamp=timestamp,
                                channel="AIN0"
                            )
                            detection_count += 1
                            
                            # Log every detection during first 10, then every 10th
                            if detection_count <= 10 or detection_count % 10 == 0:
                                logger.info(f"📈 Captured {detection_count} detections, latest: {voltage:.3f}V")
                        else:
                            # Log low voltage readings occasionally for debugging
                            if detection_count == 0:  # Log first few readings
                                logger.debug(f"🔽 Low voltage reading: {voltage:.3f}V (below 3.0V threshold)")
                    else:
                        logger.warning(f"❌ Failed to read voltage: {result}")
                    
                    # Sleep for sample interval
                    time.sleep(sample_interval)
                    
                except Exception as e:
                    logger.error(f"❌ Error in monitoring loop: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    time.sleep(1)  # Back off on error
                    
        except Exception as e:
            logger.error(f"💥 Fatal error in monitoring thread: {e}")
            import traceback
            logger.error(f"Fatal traceback: {traceback.format_exc()}")
        finally:
            # Mark monitoring as inactive when thread ends
            self.monitoring_active = False
            self.current_session_id = None
            logger.info(f"🏁 Monitoring thread ended for session {session_id}, captured {detection_count} detections")
            
    def _store_detection_event(self, session_id: str, voltage: float, timestamp: float, channel: str):
        """Store a detection event in the database"""
        try:
            # Connect to database
            conn = sqlite3.connect('dev_database.db')
            cursor = conn.cursor()
            
            # Generate unique ID
            event_id = str(uuid.uuid4())
            
            # Calculate latency (assuming minimal hardware latency)
            latency_ms = 5.0  # Typical LabJack response time
            
            # Insert detection event using existing schema
            cursor.execute("""
                INSERT INTO detection_events (
                    id, test_session_id, timestamp, 
                    confidence, class_label, validation_result,
                    created_at, vru_type, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                session_id,
                timestamp,
                voltage,  # Use confidence field to store voltage
                f"LabJack_{channel}",  # Use class_label to store channel info
                "passed" if voltage > 3.0 else "failed",
                datetime.now().isoformat(),
                f"LabJack_{voltage:.3f}V",  # Store voltage info in vru_type
                latency_ms  # Processing time
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Stored detection event: {voltage:.3f}V at {timestamp:.3f}")
            
        except Exception as e:
            logger.error(f"Failed to store detection event: {e}")
            
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            "active": self.monitoring_active,
            "session_id": self.current_session_id,
            "sample_rate": self.sample_rate,
            "timestamp": datetime.now().isoformat()
        }

# Global service instance
labjack_monitoring_service = LabJackMonitoringService()