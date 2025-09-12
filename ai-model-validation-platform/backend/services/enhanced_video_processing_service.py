"""
Enhanced Video Processing Service - Fixes monitoring failures and integrates results storage
Addresses the "failed to do monitoring" issue and ensures detection results are properly stored
"""

import asyncio
import logging
import json
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone
import threading
from pathlib import Path
import traceback

# Avoid circular import - will import dynamically when needed
from services.signal_validation_service import signal_validation_service
try:
    from services.websocket_service import websocket_service
except ImportError:
    # Create a mock websocket service for testing
    class MockWebSocketService:
        async def broadcast_message(self, message: str):
            logger.debug(f"Mock WebSocket: would broadcast message")
    websocket_service = MockWebSocketService()
from database import get_db

logger = logging.getLogger(__name__)

class EnhancedVideoProcessingService:
    """Enhanced video processing with integrated monitoring and results storage"""
    
    def __init__(self):
        self.active_processing = {}  # Track active processing sessions
        self.monitoring_lock = threading.RLock()
        
    async def process_video_with_monitoring(
        self,
        project_id: str,
        video_id: str,
        video_path: str,
        detection_callback: Optional[Callable] = None,
        monitoring_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process video with integrated monitoring and results storage"""
        
        session_id = None
        test_session_id = None
        
        try:
            session_id = str(uuid.uuid4())
            logger.info(f"Starting enhanced video processing session {session_id}")
            
            # Initialize database session for results service
            db = next(get_db())
            try:
                # Import dynamically to avoid circular imports
                from services.results_storage_pipeline_service import results_storage_service
                results_storage_service.set_db(db)
                
                # Start test session with monitoring
                session_result = await results_storage_service.start_test_session_monitoring(
                    project_id=project_id,
                    video_id=video_id,
                    test_session_name=f"Video Processing - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    tolerance_ms=monitoring_config.get("tolerance_ms", 100) if monitoring_config else 100
                )
                
                if not session_result.get("success"):
                    logger.error(f"Failed to start test session: {session_result.get('error')}")
                    return {
                        "success": False,
                        "error": f"Failed to start monitoring: {session_result.get('error')}"
                    }
                
                test_session_id = session_result["test_session_id"]
                logger.info(f"Test session started: {test_session_id}, monitoring active: {session_result['monitoring_active']}")
                
                # Track active processing
                self.active_processing[session_id] = {
                    "project_id": project_id,
                    "video_id": video_id,
                    "test_session_id": test_session_id,
                    "started_at": datetime.now(timezone.utc),
                    "monitoring_active": session_result["monitoring_active"]
                }
                
                # Process video with robust error handling
                processing_result = await self._process_video_robust(
                    session_id=session_id,
                    test_session_id=test_session_id,
                    video_path=video_path,
                    detection_callback=detection_callback,
                    monitoring_config=monitoring_config or {}
                )
                
                # Finalize test session
                if test_session_id:
                    logger.info(f"Finalizing test session {test_session_id}")
                    from services.results_storage_pipeline_service import results_storage_service
                    finalization_result = await results_storage_service.finalize_test_session(test_session_id)
                    
                    if finalization_result.get("success"):
                        processing_result["test_results"] = finalization_result.get("test_results", {})
                        logger.info(f"Test session finalized successfully with results")
                    else:
                        logger.warning(f"Test session finalization failed: {finalization_result.get('error')}")
                
                return processing_result
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Critical error in video processing: {e}")
            logger.error(traceback.format_exc())
            
            # Attempt to clean up test session
            if test_session_id:
                try:
                    db = next(get_db())
                    results_storage_service.set_db(db)
                    await results_storage_service.finalize_test_session(test_session_id, force_completion=True)
                    db.close()
                except Exception as cleanup_error:
                    logger.error(f"Error during cleanup: {cleanup_error}")
            
            return {
                "success": False,
                "error": f"Video processing failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
        
        finally:
            # Clean up active processing tracking
            if session_id in self.active_processing:
                del self.active_processing[session_id]
    
    async def _process_video_robust(
        self,
        session_id: str,
        test_session_id: str,
        video_path: str,
        detection_callback: Optional[Callable],
        monitoring_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Robust video processing with comprehensive error handling"""
        
        detections_processed = 0
        errors_encountered = []
        
        try:
            logger.info(f"Starting robust video processing for session {session_id}")
            
            # Verify video file exists and is accessible
            if not Path(video_path).exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Import video processing modules
            try:
                import cv2
                from services.ground_truth_service import ground_truth_service
            except ImportError as e:
                raise ImportError(f"Required video processing modules not available: {e}")
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError(f"Failed to open video: {video_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            logger.info(f"Video properties - FPS: {fps}, Frames: {frame_count}, Duration: {duration}s")
            
            frame_number = 0
            detection_id_counter = 0
            
            # Send initial progress update
            await self._send_progress_update(test_session_id, "processing_started", {
                "total_frames": frame_count,
                "fps": fps,
                "duration": duration
            })
            
            # Process frames
            while True:
                try:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    frame_number += 1
                    current_time = frame_number / fps if fps > 0 else 0
                    
                    # Process frame for detections (with error isolation)
                    try:
                        frame_detections = await self._process_frame_for_detections(
                            frame, frame_number, current_time, session_id
                        )
                        
                        # Store each detection
                        for detection in frame_detections:
                            detection_id_counter += 1
                            
                            # Enhance detection data
                            enhanced_detection = {
                                **detection,
                                "session_id": session_id,
                                "frame_number": frame_number,
                                "timestamp": current_time,
                                "processing_time_ms": detection.get("processing_time_ms", 50),
                                "model_version": "yolov8_enhanced",
                                "detection_id": f"{session_id}_{detection_id_counter}"
                            }
                            
                            # Store detection in results service
                            from services.results_storage_pipeline_service import results_storage_service
                            storage_result = await results_storage_service.process_detection_event(
                                test_session_id=test_session_id,
                                detection_data=enhanced_detection,
                                video_timestamp=current_time,
                                frame_number=frame_number
                            )
                            
                            if storage_result.get("success"):
                                detections_processed += 1
                                logger.debug(f"Detection stored successfully: {storage_result['detection_event_id']}")
                            else:
                                error_msg = f"Detection storage failed: {storage_result.get('error')}"
                                logger.error(error_msg)
                                errors_encountered.append(error_msg)
                            
                            # Call custom detection callback if provided
                            if detection_callback:
                                try:
                                    await detection_callback(enhanced_detection)
                                except Exception as callback_error:
                                    logger.error(f"Detection callback error: {callback_error}")
                    
                    except Exception as frame_error:
                        error_msg = f"Frame processing error at frame {frame_number}: {frame_error}"
                        logger.error(error_msg)
                        errors_encountered.append(error_msg)
                    
                    # Send progress updates every 10 frames or at key intervals
                    if frame_number % 10 == 0 or frame_number in [1, frame_count]:
                        progress = (frame_number / frame_count) * 100 if frame_count > 0 else 0
                        await self._send_progress_update(test_session_id, "processing_progress", {
                            "frame_number": frame_number,
                            "total_frames": frame_count,
                            "progress_percentage": progress,
                            "detections_processed": detections_processed,
                            "current_timestamp": current_time
                        })
                
                except Exception as loop_error:
                    error_msg = f"Processing loop error: {loop_error}"
                    logger.error(error_msg)
                    errors_encountered.append(error_msg)
                    break
            
            # Clean up
            cap.release()
            
            # Send completion update
            await self._send_progress_update(test_session_id, "processing_completed", {
                "total_frames_processed": frame_number,
                "total_detections": detections_processed,
                "processing_errors": len(errors_encountered)
            })
            
            logger.info(f"Video processing completed - Frames: {frame_number}, Detections: {detections_processed}, Errors: {len(errors_encountered)}")
            
            return {
                "success": True,
                "session_id": session_id,
                "test_session_id": test_session_id,
                "frames_processed": frame_number,
                "detections_processed": detections_processed,
                "errors_encountered": errors_encountered,
                "video_duration": duration,
                "processing_completed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            error_msg = f"Critical video processing error: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": error_msg,
                "detections_processed": detections_processed,
                "errors_encountered": errors_encountered
            }
    
    async def _process_frame_for_detections(
        self,
        frame,
        frame_number: int,
        timestamp: float,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Process a single frame for object detection"""
        
        detections = []
        
        try:
            # Import detection service
            from services.ground_truth_service import ground_truth_service
            
            # Run YOLOv8 detection on frame
            detection_results = ground_truth_service.detect_objects_in_frame(frame)
            
            # Convert to our detection format
            for detection in detection_results:
                bbox = detection.get("bbox", {})
                
                detection_data = {
                    "confidence": detection.get("confidence", 0.8),
                    "class_label": detection.get("class_name", "object"),
                    "vru_type": self._classify_vru_type(detection.get("class_name", "object")),
                    "bbox": {
                        "x": bbox.get("x", 0),
                        "y": bbox.get("y", 0),
                        "width": bbox.get("width", 0),
                        "height": bbox.get("height", 0)
                    },
                    "processing_time_ms": 25,  # Estimated processing time
                    "metadata": {
                        "detection_method": "yolov8_frame_processing",
                        "frame_dimensions": {
                            "width": frame.shape[1],
                            "height": frame.shape[0]
                        }
                    }
                }
                
                detections.append(detection_data)
            
            # Also check for LabJack signals during this frame (if monitoring is active)
            try:
                signal_detections = await self._check_signal_detections(timestamp, session_id)
                detections.extend(signal_detections)
            except Exception as signal_error:
                logger.warning(f"Signal detection check failed: {signal_error}")
            
        except Exception as e:
            logger.error(f"Frame detection processing error: {e}")
            # Return empty list rather than failing completely
        
        return detections
    
    async def _check_signal_detections(self, timestamp: float, session_id: str) -> List[Dict[str, Any]]:
        """Check for LabJack signal detections at current timestamp"""
        
        signal_detections = []
        
        try:
            # Check if signal validation service has detected any signals
            if hasattr(signal_validation_service, 'signal_buffer'):
                # Look for recent signals within a small time window
                recent_signals = [
                    signal for signal in signal_validation_service.signal_buffer
                    if abs(signal.timestamp - timestamp) <= 0.1  # 100ms tolerance
                ]
                
                for signal in recent_signals:
                    signal_detection = {
                        "confidence": signal.confidence,
                        "class_label": "labjack_signal_enhanced",
                        "vru_type": "signal_detection",
                        "bbox": {
                            "x": signal.voltage_value if signal.voltage_value else 0,  # Store voltage in bbox
                            "y": 0,  # Channel info could go here
                            "width": getattr(signal_validation_service.labjack, 'voltage_threshold', 2.5) if signal_validation_service.labjack else 2.5,
                            "height": getattr(signal_validation_service.labjack, 'sample_rate', 1000) if signal_validation_service.labjack else 1000
                        },
                        "processing_time_ms": 5,
                        "metadata": {
                            "signal_type": signal.signal_type.value,
                            "voltage_value": signal.voltage_value,
                            "detection_method": "labjack_signal_monitoring",
                            "mock_mode": getattr(signal_validation_service.labjack, 'mock_mode', True) if signal_validation_service.labjack else True
                        }
                    }
                    
                    signal_detections.append(signal_detection)
        
        except Exception as e:
            logger.error(f"Error checking signal detections: {e}")
        
        return signal_detections
    
    def _classify_vru_type(self, class_name: str) -> str:
        """Classify detection into VRU type"""
        class_name_lower = class_name.lower()
        
        if any(word in class_name_lower for word in ["person", "pedestrian", "human"]):
            return "pedestrian"
        elif any(word in class_name_lower for word in ["bicycle", "bike", "cyclist"]):
            return "cyclist"
        elif any(word in class_name_lower for word in ["motorcycle", "motorbike", "scooter"]):
            return "motorcyclist"
        elif "signal" in class_name_lower:
            return "signal_detection"
        else:
            return "other_vru"
    
    async def _send_progress_update(self, test_session_id: str, event_type: str, data: Dict[str, Any]):
        """Send progress update via WebSocket"""
        try:
            message = {
                "type": event_type,
                "test_session_id": test_session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data
            }
            
            # Send via websocket service
            if hasattr(websocket_service, 'broadcast_message'):
                await websocket_service.broadcast_message(json.dumps(message))
            
        except Exception as e:
            logger.error(f"Error sending progress update: {e}")
    
    def get_active_processing_sessions(self) -> Dict[str, Any]:
        """Get information about currently active processing sessions"""
        return {
            "active_count": len(self.active_processing),
            "sessions": [
                {
                    "session_id": session_id,
                    **session_info,
                    "started_at": session_info["started_at"].isoformat()
                }
                for session_id, session_info in self.active_processing.items()
            ]
        }
    
    async def stop_processing_session(self, session_id: str) -> Dict[str, Any]:
        """Stop a processing session (if possible)"""
        try:
            if session_id in self.active_processing:
                session_info = self.active_processing[session_id]
                test_session_id = session_info.get("test_session_id")
                
                if test_session_id:
                    # Try to finalize the test session
                    db = next(get_db())
                    try:
                        results_storage_service.set_db(db)
                        result = await results_storage_service.finalize_test_session(
                            test_session_id, force_completion=True
                        )
                        return result
                    finally:
                        db.close()
                
                del self.active_processing[session_id]
                
            return {"success": True, "message": "Processing session stopped"}
            
        except Exception as e:
            logger.error(f"Error stopping processing session: {e}")
            return {"success": False, "error": str(e)}

# Global service instance
enhanced_video_processing_service = EnhancedVideoProcessingService()