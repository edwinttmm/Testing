"""
Results Storage Pipeline Service - Complete solution for detection results storage and display
Handles the end-to-end flow: Video processing → Detection storage → Results calculation → Display
"""

import logging
import asyncio
import json
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from concurrent.futures import ThreadPoolExecutor
import threading

from models import (
    TestSession, DetectionEvent, DetectionComparison, TestResult,
    GroundTruthObject, Annotation, Project, Video
)
from database import get_db
from services.signal_validation_service import signal_validation_service
try:
    from services.websocket_service import websocket_service
except ImportError:
    # Use enhanced websocket service if available
    try:
        from services.websocket_enhanced import enhanced_websocket_service as websocket_service
    except ImportError:
        # Create a mock websocket service for testing
        class MockWebSocketService:
            async def broadcast_to_session(self, session_id: str, message: dict):
                logger.debug(f"Mock WebSocket: would broadcast to session {session_id}")
        websocket_service = MockWebSocketService()

logger = logging.getLogger(__name__)

class ResultsStoragePipelineService:
    """Complete pipeline for storing and displaying detection results"""
    
    def __init__(self):
        self.db = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.monitoring_sessions = {}  # Track active monitoring sessions
        self.detection_buffer = {}  # Buffer detections during processing
        
    def set_db(self, db: Session):
        """Set database session"""
        self.db = db
    
    async def start_test_session_monitoring(
        self,
        project_id: str,
        video_id: str,
        test_session_name: str = None,
        tolerance_ms: int = 100
    ) -> Dict[str, Any]:
        """Start a new test session with monitoring"""
        try:
            if not self.db:
                raise RuntimeError("Database session not initialized")
            
            # Create test session
            session_name = test_session_name or f"Test Session - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            test_session = TestSession(
                id=str(uuid.uuid4()),
                name=session_name,
                project_id=project_id,
                video_id=video_id,
                status="running",
                tolerance_ms=tolerance_ms,
                started_at=datetime.now(timezone.utc),
                session_type="user_created",
                metadata={"monitoring_enabled": True}
            )
            
            self.db.add(test_session)
            self.db.commit()
            
            # Initialize detection buffer for this session
            self.detection_buffer[test_session.id] = []
            
            # Start LabJack monitoring if available
            monitoring_started = False
            try:
                signal_validation_service.start_signal_monitoring(test_session.id)
                monitoring_started = True
                logger.info(f"LabJack monitoring started for session {test_session.id}")
            except Exception as e:
                logger.warning(f"LabJack monitoring failed to start: {e}. Continuing without signal monitoring.")
            
            # Track monitoring session
            self.monitoring_sessions[test_session.id] = {
                "project_id": project_id,
                "video_id": video_id,
                "started_at": datetime.now(timezone.utc),
                "monitoring_active": monitoring_started,
                "detection_count": 0
            }
            
            # Send WebSocket update
            await self._send_websocket_update(test_session.id, "session_started", {
                "test_session_id": test_session.id,
                "project_id": project_id,
                "video_id": video_id,
                "monitoring_active": monitoring_started
            })
            
            return {
                "success": True,
                "test_session_id": test_session.id,
                "monitoring_active": monitoring_started,
                "message": "Test session started successfully"
            }
            
        except Exception as e:
            logger.error(f"Error starting test session monitoring: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_detection_event(
        self,
        test_session_id: str,
        detection_data: Dict[str, Any],
        video_timestamp: float,
        frame_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process and store a detection event"""
        try:
            if not self.db:
                raise RuntimeError("Database session not initialized")
            
            # Get test session
            test_session = self.db.query(TestSession).filter(
                TestSession.id == test_session_id
            ).first()
            
            if not test_session:
                return {"success": False, "error": "Test session not found"}
            
            # Create detection event
            detection_event = DetectionEvent(
                id=str(uuid.uuid4()),
                test_session_id=test_session_id,
                detection_id=str(uuid.uuid4()),
                timestamp=video_timestamp,
                confidence=detection_data.get("confidence", 0.8),
                class_label=detection_data.get("class_label", "object"),
                validation_result="pending",  # Will be set during comparison
                vru_type=detection_data.get("vru_type", "unknown"),
                frame_number=frame_number,
                processing_time_ms=detection_data.get("processing_time_ms"),
                model_version=detection_data.get("model_version", "yolov8"),
                
                # Bounding box data
                bounding_box_x=detection_data.get("bbox", {}).get("x"),
                bounding_box_y=detection_data.get("bbox", {}).get("y"),
                bounding_box_width=detection_data.get("bbox", {}).get("width"),
                bounding_box_height=detection_data.get("bbox", {}).get("height"),
                
                # Visual evidence
                screenshot_path=detection_data.get("screenshot_path"),
                screenshot_zoom_path=detection_data.get("screenshot_zoom_path"),
                
                # Metadata
                metadata=json.dumps(detection_data.get("metadata", {}))
            )
            
            self.db.add(detection_event)
            
            # Update session detection count
            if test_session_id in self.monitoring_sessions:
                self.monitoring_sessions[test_session_id]["detection_count"] += 1
            
            # Store in buffer for batch processing
            if test_session_id not in self.detection_buffer:
                self.detection_buffer[test_session_id] = []
            
            self.detection_buffer[test_session_id].append({
                "detection_event": detection_event,
                "video_timestamp": video_timestamp,
                "processed_at": datetime.now(timezone.utc)
            })
            
            self.db.commit()
            
            # Send real-time WebSocket update
            await self._send_websocket_update(test_session_id, "detection_event", {
                "detection_id": detection_event.id,
                "timestamp": video_timestamp,
                "confidence": detection_event.confidence,
                "class_label": detection_event.class_label
            })
            
            # Trigger comparison processing asynchronously
            asyncio.create_task(self._process_detection_comparison(
                test_session_id, detection_event.id, video_timestamp
            ))
            
            return {
                "success": True,
                "detection_event_id": detection_event.id,
                "timestamp": video_timestamp
            }
            
        except Exception as e:
            logger.error(f"Error processing detection event: {e}")
            return {"success": False, "error": str(e)}
    
    async def _process_detection_comparison(
        self,
        test_session_id: str,
        detection_event_id: str,
        video_timestamp: float
    ):
        """Process detection comparison against ground truth"""
        try:
            if not self.db:
                return
            
            # Get test session and video
            test_session = self.db.query(TestSession).filter(
                TestSession.id == test_session_id
            ).first()
            
            if not test_session:
                return
            
            # Find matching ground truth objects within tolerance
            tolerance_seconds = (test_session.tolerance_ms or 100) / 1000.0
            
            # Query ground truth objects near the timestamp
            ground_truth_objects = self.db.query(GroundTruthObject).filter(
                and_(
                    GroundTruthObject.video_id == test_session.video_id,
                    GroundTruthObject.timestamp >= video_timestamp - tolerance_seconds,
                    GroundTruthObject.timestamp <= video_timestamp + tolerance_seconds
                )
            ).all()
            
            # Get the detection event
            detection_event = self.db.query(DetectionEvent).filter(
                DetectionEvent.id == detection_event_id
            ).first()
            
            if not detection_event:
                return
            
            # Find best match
            best_match = None
            best_score = 0.0
            best_temporal_offset = None

            for gt_obj in ground_truth_objects:
                # Calculate temporal offset
                # FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
                det_timestamp = detection_event.video_relative_timestamp if hasattr(detection_event, 'video_relative_timestamp') and detection_event.video_relative_timestamp is not None else video_timestamp
                temporal_offset = det_timestamp - gt_obj.timestamp

                # Calculate spatial matching (if applicable)
                iou_score = self._calculate_iou(detection_event, gt_obj)

                # Calculate combined score (temporal + spatial)
                temporal_score = max(0, 1 - abs(temporal_offset) / tolerance_seconds)
                combined_score = 0.7 * temporal_score + 0.3 * iou_score

                if combined_score > best_score:
                    best_match = gt_obj
                    best_score = combined_score
                    best_temporal_offset = temporal_offset
            
            # Determine match type
            match_type = "TP" if best_match else "FP"
            
            # Create detection comparison
            comparison = DetectionComparison(
                id=str(uuid.uuid4()),
                test_session_id=test_session_id,
                detection_event_id=detection_event_id,
                ground_truth_id=best_match.id if best_match else None,
                match_type=match_type,
                iou_score=self._calculate_iou(detection_event, best_match) if best_match else 0.0,
                distance_error=0.0,  # Calculate if needed
                temporal_offset=best_temporal_offset,
                notes=f"Auto-generated comparison - Score: {best_score:.3f}"
            )
            
            # Update detection event validation result
            detection_event.validation_result = match_type
            
            self.db.add(comparison)
            self.db.commit()
            
            # Send WebSocket update
            await self._send_websocket_update(test_session_id, "comparison_created", {
                "comparison_id": comparison.id,
                "match_type": match_type,
                "temporal_offset_ms": best_temporal_offset * 1000 if best_temporal_offset else None
            })
            
        except Exception as e:
            logger.error(f"Error processing detection comparison: {e}")
    
    def _calculate_iou(self, detection: DetectionEvent, ground_truth: GroundTruthObject) -> float:
        """Calculate Intersection over Union for spatial matching"""
        try:
            if not all([
                detection.bounding_box_x, detection.bounding_box_y,
                detection.bounding_box_width, detection.bounding_box_height,
                ground_truth.bounding_box_x, ground_truth.bounding_box_y,
                ground_truth.bounding_box_width, ground_truth.bounding_box_height
            ]):
                return 0.0
            
            # Calculate intersection
            x1 = max(detection.bounding_box_x, ground_truth.bounding_box_x)
            y1 = max(detection.bounding_box_y, ground_truth.bounding_box_y)
            x2 = min(
                detection.bounding_box_x + detection.bounding_box_width,
                ground_truth.bounding_box_x + ground_truth.bounding_box_width
            )
            y2 = min(
                detection.bounding_box_y + detection.bounding_box_height,
                ground_truth.bounding_box_y + ground_truth.bounding_box_height
            )
            
            if x2 <= x1 or y2 <= y1:
                return 0.0
            
            intersection = (x2 - x1) * (y2 - y1)
            
            # Calculate union
            area1 = detection.bounding_box_width * detection.bounding_box_height
            area2 = ground_truth.bounding_box_width * ground_truth.bounding_box_height
            union = area1 + area2 - intersection
            
            return intersection / union if union > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating IoU: {e}")
            return 0.0
    
    async def finalize_test_session(
        self,
        test_session_id: str,
        force_completion: bool = False
    ) -> Dict[str, Any]:
        """Finalize test session and generate results"""
        try:
            if not self.db:
                raise RuntimeError("Database session not initialized")
            
            # Get test session
            test_session = self.db.query(TestSession).filter(
                TestSession.id == test_session_id
            ).first()
            
            if not test_session:
                return {"success": False, "error": "Test session not found"}
            
            # Stop monitoring
            try:
                signal_validation_service.stop_signal_monitoring()
                logger.info(f"Monitoring stopped for session {test_session_id}")
            except Exception as e:
                logger.warning(f"Error stopping monitoring: {e}")
            
            # Clean up monitoring session
            if test_session_id in self.monitoring_sessions:
                del self.monitoring_sessions[test_session_id]
            
            # Process any remaining detections in buffer
            if test_session_id in self.detection_buffer:
                remaining_detections = len(self.detection_buffer[test_session_id])
                logger.info(f"Processing {remaining_detections} remaining detections")
                # Wait a bit for async comparison processing to complete
                await asyncio.sleep(2.0)
                del self.detection_buffer[test_session_id]
            
            # Generate test results
            test_results = await self._generate_test_results(test_session_id)
            
            # Update test session status
            test_session.status = "completed"
            test_session.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            
            # Send final WebSocket update
            await self._send_websocket_update(test_session_id, "session_completed", {
                "test_session_id": test_session_id,
                "test_results": test_results
            })
            
            return {
                "success": True,
                "test_session_id": test_session_id,
                "test_results": test_results,
                "message": "Test session finalized successfully"
            }
            
        except Exception as e:
            logger.error(f"Error finalizing test session: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_test_results(self, test_session_id: str) -> Dict[str, Any]:
        """Generate comprehensive test results"""
        try:
            # Get all detection events and comparisons
            detection_events = self.db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == test_session_id
            ).all()
            
            comparisons = self.db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == test_session_id
            ).all()
            
            # Calculate metrics
            total_detections = len(detection_events)
            true_positives = len([c for c in comparisons if c.match_type == "TP"])
            false_positives = len([c for c in comparisons if c.match_type == "FP"])
            false_negatives = len([c for c in comparisons if c.match_type == "FN"])
            
            # Calculate performance metrics
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            accuracy = true_positives / total_detections if total_detections > 0 else 0
            
            # Create test result record
            test_result = TestResult(
                id=str(uuid.uuid4()),
                test_session_id=test_session_id,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                true_positives=true_positives,
                false_positives=false_positives,
                false_negatives=false_negatives,
                statistical_analysis=json.dumps({
                    "total_detections": total_detections,
                    "total_comparisons": len(comparisons),
                    "timing_analysis": self._analyze_timing(comparisons)
                }),
                confidence_intervals=json.dumps({
                    "precision": [max(0, precision - 0.1), min(1, precision + 0.1)],
                    "recall": [max(0, recall - 0.1), min(1, recall + 0.1)],
                    "f1_score": [max(0, f1_score - 0.1), min(1, f1_score + 0.1)]
                })
            )
            
            self.db.add(test_result)
            self.db.commit()
            
            return {
                "test_result_id": test_result.id,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1_score": f1_score,
                "true_positives": true_positives,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "total_detections": total_detections,
                "pass_fail_status": "PASS" if accuracy >= 0.8 else "FAIL"
            }
            
        except Exception as e:
            logger.error(f"Error generating test results: {e}")
            return {"error": str(e)}
    
    def _analyze_timing(self, comparisons: List[DetectionComparison]) -> Dict[str, Any]:
        """Analyze timing performance from comparisons"""
        if not comparisons:
            return {"message": "No timing data available"}
        
        temporal_offsets = [c.temporal_offset for c in comparisons if c.temporal_offset is not None]
        
        if not temporal_offsets:
            return {"message": "No temporal offset data"}
        
        # Convert to milliseconds
        offsets_ms = [offset * 1000 for offset in temporal_offsets]
        
        return {
            "average_offset_ms": sum(offsets_ms) / len(offsets_ms),
            "max_offset_ms": max(offsets_ms),
            "min_offset_ms": min(offsets_ms),
            "within_100ms_tolerance": len([o for o in offsets_ms if abs(o) <= 100])
        }
    
    async def _send_websocket_update(self, test_session_id: str, event_type: str, data: Dict[str, Any]):
        """Send WebSocket update for real-time monitoring"""
        try:
            message = {
                "type": event_type,
                "test_session_id": test_session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data
            }
            
            # Use websocket service to broadcast
            if hasattr(websocket_service, 'broadcast_to_session'):
                await websocket_service.broadcast_to_session(test_session_id, message)
            
        except Exception as e:
            logger.error(f"Error sending WebSocket update: {e}")
    
    async def get_test_session_results(self, test_session_id: str) -> Dict[str, Any]:
        """Get comprehensive results for a test session"""
        try:
            if not self.db:
                raise RuntimeError("Database session not initialized")
            
            from services.detection_results_service import DetectionResultsService
            
            results_service = DetectionResultsService(self.db)
            return results_service.get_comprehensive_test_results(test_session_id)
            
        except Exception as e:
            logger.error(f"Error getting test session results: {e}")
            return {"error": str(e)}
    
    async def get_project_results_summary(self, project_id: str) -> Dict[str, Any]:
        """Get results summary for all sessions in a project"""
        try:
            if not self.db:
                raise RuntimeError("Database session not initialized")
            
            # Get all test sessions for project
            test_sessions = self.db.query(TestSession).filter(
                TestSession.project_id == project_id
            ).all()
            
            if not test_sessions:
                return {"message": "No test sessions found for project"}
            
            # Aggregate results
            total_sessions = len(test_sessions)
            completed_sessions = len([s for s in test_sessions if s.status == "completed"])
            
            # Get all test results for the project
            test_results = self.db.query(TestResult).join(TestSession).filter(
                TestSession.project_id == project_id
            ).all()
            
            if test_results:
                avg_accuracy = sum([r.accuracy for r in test_results]) / len(test_results)
                avg_precision = sum([r.precision for r in test_results]) / len(test_results)
                avg_recall = sum([r.recall for r in test_results]) / len(test_results)
            else:
                avg_accuracy = avg_precision = avg_recall = 0.0
            
            return {
                "project_id": project_id,
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "pending_sessions": total_sessions - completed_sessions,
                "average_accuracy": avg_accuracy,
                "average_precision": avg_precision,
                "average_recall": avg_recall,
                "overall_status": "PASS" if avg_accuracy >= 0.8 else "FAIL" if avg_accuracy > 0 else "PENDING"
            }
            
        except Exception as e:
            logger.error(f"Error getting project results summary: {e}")
            return {"error": str(e)}
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            # Stop all monitoring sessions
            for session_id in list(self.monitoring_sessions.keys()):
                try:
                    signal_validation_service.stop_signal_monitoring()
                except Exception as e:
                    logger.warning(f"Error stopping monitoring for session {session_id}: {e}")
            
            self.monitoring_sessions.clear()
            self.detection_buffer.clear()
            
            # Shutdown executor
            self.executor.shutdown(wait=False)
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Global service instance
results_storage_service = ResultsStoragePipelineService()