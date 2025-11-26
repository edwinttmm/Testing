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
        # Edge-detection state
        self.threshold_v = 2.5
        self._was_high = False
        
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
        """Stop monitoring LabJack signals and cleanup resources"""
        if not self.monitoring_active:
            logger.debug("Monitoring already stopped - nothing to cleanup")
            return

        session_id = self.current_session_id
        logger.info(f"⏹️ Stopping LabJack monitoring for session {session_id}")

        # CRITICAL FIX: Set flags FIRST to stop loop immediately
        self.monitoring_active = False
        self._stop_event.set()

        # Wait for monitoring thread to terminate
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.debug(f"Waiting for monitoring thread to terminate...")
            self.monitor_thread.join(timeout=3.0)

            if self.monitor_thread.is_alive():
                logger.warning(f"⚠️ Monitoring thread did not terminate cleanly")
            else:
                logger.debug(f"✅ Monitoring thread terminated successfully")

        # Cleanup resources
        self.current_session_id = None
        self.monitor_thread = None
        self._was_high = False  # Reset edge detection state

        logger.info(f"✅ Monitoring stopped and cleaned up for session {session_id}")
        
    def _monitor_loop(self, session_id: str):
        """Background loop to monitor and store LabJack signals"""
        detection_count = 0
        logger.info(f"📊 Starting monitoring loop for session {session_id}")

        try:
            # Import signal validation service
            from api_signal_validation import signal_validation_service
            logger.info(f"✅ Successfully imported signal validation service")

            sample_interval = 1.0 / self.sample_rate

            # CRITICAL FIX: Check BOTH flags on every iteration
            while self.monitoring_active and not self._stop_event.is_set():
                try:
                    # SAFETY: Double-check session is still active before reading
                    if not self.monitoring_active or self._stop_event.is_set():
                        logger.debug("Stop signal detected, breaking monitoring loop")
                        break

                    # Read voltage from LabJack
                    result = signal_validation_service.read_voltage_signal("AIN0")

                    if result.get("success") and result.get("voltage") is not None:
                        voltage = result["voltage"]
                        timestamp = time.time()
                        # Rising-edge detection at configurable threshold
                        if voltage > self.threshold_v and not self._was_high:
                            self._store_detection_event(
                                session_id=session_id,
                                voltage=voltage,
                                timestamp=timestamp,
                                channel="AIN0"
                            )
                            detection_count += 1
                            self._was_high = True
                            if detection_count <= 10 or detection_count % 10 == 0:
                                logger.info(f"📈 Captured {detection_count} detections, rising-edge @ {voltage:.3f}V")
                        elif voltage <= self.threshold_v:
                            # Reset for next edge
                            if self._was_high:
                                logger.debug("🔽 Falling edge detected; arming for next detection")
                            self._was_high = False
                        else:
                            # Still high; no new edge
                            pass
                    else:
                        # CRITICAL FIX: Check if error is due to monitoring being stopped
                        # If so, exit gracefully without logging as an error
                        error_msg = result.get("error", "")
                        if "Monitoring not active" in error_msg or "no sessions running" in error_msg:
                            logger.debug(f"Monitoring stopped signal received, exiting loop")
                            break
                        # Log other errors as warnings
                        logger.warning(f"❌ Failed to read voltage: {result}")

                    # CRITICAL FIX: Final check before sleeping to avoid unnecessary delay on shutdown
                    if not self.monitoring_active or self._stop_event.is_set():
                        logger.debug("Stop signal detected before sleep, breaking monitoring loop")
                        break

                    # Sleep for sample interval
                    time.sleep(sample_interval)

                except Exception as e:
                    # Check if this is a shutdown-related exception
                    if not self.monitoring_active or self._stop_event.is_set():
                        logger.debug(f"Exception during shutdown, exiting gracefully: {e}")
                        break
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
            
            # Insert detection event including LabJack-specific fields when available
            cursor.execute("""
                INSERT INTO detection_events (
                    id, test_session_id, timestamp,
                    labjack_timestamp, labjack_voltage, voltage_level, detection_channel,
                    validation_result, created_at, processing_time_ms,
                    class_label, confidence, vru_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                session_id,
                float(timestamp),
                float(timestamp),  # labjack_timestamp mirrors timestamp (epoch seconds)
                float(voltage),
                float(voltage),
                channel,
                "passed" if voltage > self.threshold_v else "failed",
                datetime.now().isoformat(),
                latency_ms,
                f"LabJack_{channel}",
                float(voltage),  # legacy confidence field stores voltage
                f"LabJack_{voltage:.3f}V"
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
