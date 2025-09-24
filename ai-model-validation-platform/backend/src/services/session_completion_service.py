"""
Session Completion Service

Comprehensive service to handle test session completion workflow:
- Update session status to "completed"
- Generate test results and metrics
- Update session metadata (video count, timestamps)
- Integrate with LabJack timing completion
- Ensure proper API response formatting
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, and_

from models import (
    TestSession, DetectionEvent, TestResult, Video, Project,
    DetectionComparison, GroundTruthObject
)
from services.labjack_timing_service import LabJackTimingService

logger = logging.getLogger(__name__)


class SessionCompletionService:
    """Service for comprehensive test session completion"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.timing_service = LabJackTimingService(db_session)
    
    def complete_test_session(
        self, 
        session_id: str, 
        force_completion: bool = False,
        final_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete a test session with comprehensive result generation
        
        Args:
            session_id: Test session ID to complete
            force_completion: Force completion even if errors exist
            final_results: Optional final results to include
            
        Returns:
            Completion status and results
        """
        try:
            # Get test session
            test_session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            if not test_session:
                raise ValueError(f"Test session {session_id} not found")
            
            logger.info(f"Starting completion of test session {session_id}")
            
            # Check if already completed
            if test_session.status == "completed" and not force_completion:
                return {
                    "success": True,
                    "message": "Test session already completed",
                    "session_id": session_id,
                    "status": "completed"
                }
            
            # Step 1: Update session timing
            completion_time = datetime.utcnow()
            test_session.completed_at = completion_time
            if not test_session.started_at:
                # Fallback: use created_at if started_at is missing
                test_session.started_at = test_session.created_at
            
            # Step 2: Calculate session metrics
            session_metrics = self._calculate_session_metrics(session_id)
            
            # Step 3: Generate/update test results
            test_result = self._generate_test_results(session_id, session_metrics)
            
            # Step 4: Update session metadata
            self._update_session_metadata(test_session, session_metrics)
            
            # Step 5: Update session status to completed
            test_session.status = "completed"
            
            # Step 6: Store additional results if provided
            if final_results:
                test_session.results_summary = final_results
            
            # Commit all changes
            self.db_session.commit()
            
            logger.info(f"Successfully completed test session {session_id}")
            
            # Return completion summary
            return {
                "success": True,
                "message": "Test session completed successfully",
                "session_id": session_id,
                "status": "completed",
                "completed_at": completion_time.isoformat(),
                "metrics": session_metrics,
                "test_result_id": test_result.id if test_result else None,
                "session_summary": self._generate_session_summary(test_session, session_metrics)
            }
            
        except Exception as e:
            self.db_session.rollback()
            logger.error(f"Error completing test session {session_id}: {e}")
            
            if force_completion:
                # Force completion with error state
                return self._force_complete_with_error(session_id, str(e))
            else:
                raise Exception(f"Failed to complete test session: {str(e)}")
    
    def _calculate_session_metrics(self, session_id: str) -> Dict[str, Any]:
        """Calculate comprehensive session metrics using ground truth matching"""
        try:
            # Use ground truth matching for accurate HIL metrics
            from services.ground_truth_matching_service import get_ground_truth_matching_service
            
            matching_service = get_ground_truth_matching_service(self.db_session)
            matching_results = matching_service.match_detections_to_ground_truth(session_id)
            
            # Get session duration
            test_session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            duration_seconds = 0
            if test_session and test_session.started_at and test_session.completed_at:
                duration_seconds = (test_session.completed_at - test_session.started_at).total_seconds()
            
            # Build comprehensive metrics from ground truth matching
            total_detections = matching_results.true_positives + matching_results.false_positives
            total_ground_truth = matching_results.true_positives + matching_results.false_negatives
            
            # Calculate success rate based on ground truth matching
            success_rate = matching_results.precision * 100  # Precision represents detection accuracy
            
            # Real latency statistics from ground truth matching
            latency_stats = {}
            if matching_results.temporal_offsets:
                latencies = matching_results.temporal_offsets
                latencies.sort()
                n = len(latencies)
                latency_stats = {
                    "average_ms": matching_results.avg_latency_ms,
                    "min_ms": matching_results.min_latency_ms,
                    "max_ms": matching_results.max_latency_ms,
                    "median_ms": matching_results.median_latency_ms,
                    "std_dev": self._calculate_std_dev(latencies) if n > 1 else 0,
                    "percentiles": {
                        "25th": latencies[int(0.25 * n)] if n > 0 else 0,
                        "75th": latencies[int(0.75 * n)] if n > 0 else 0,
                        "95th": latencies[int(0.95 * n)] if n > 0 else 0
                    }
                }
            
            # Get video count for this session
            video_count = self._get_session_video_count(session_id)
            
            return {
                "total_detections": total_detections,
                "total_ground_truth": total_ground_truth,
                "passed_detections": matching_results.true_positives,
                "failed_detections": matching_results.false_positives,
                "missed_detections": matching_results.false_negatives,
                "success_rate": success_rate,
                "precision": matching_results.precision,
                "recall": matching_results.recall,
                "f1_score": matching_results.f1_score,
                "video_count": video_count,
                "duration_seconds": duration_seconds,
                "latency_stats": latency_stats,
                "detection_rate_hz": total_detections / duration_seconds if duration_seconds > 0 else 0,
                "ground_truth_matched": True,
                "validation_type": "HIL_GroundTruth_Matched"
            }
            
        except Exception as e:
            logger.error(f"Ground truth matching failed, falling back to simple metrics: {e}")
            
            # Fallback to simple counting if ground truth matching fails
            detection_events = self.db_session.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).all()
            
            total_detections = len(detection_events)
            passed_detections = len([d for d in detection_events if d.validation_result == "passed"])
            failed_detections = total_detections - passed_detections
            success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0.0
            
            # Get session duration
            test_session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            duration_seconds = 0
            if test_session and test_session.started_at and test_session.completed_at:
                duration_seconds = (test_session.completed_at - test_session.started_at).total_seconds()
            
            return {
                "total_detections": total_detections,
                "passed_detections": passed_detections,
                "failed_detections": failed_detections,
                "success_rate": success_rate,
                "video_count": self._get_session_video_count(session_id),
                "duration_seconds": duration_seconds,
                "latency_stats": {},
                "detection_rate_hz": total_detections / duration_seconds if duration_seconds > 0 else 0,
                "ground_truth_matched": False,
                "validation_type": "HIL_Fallback"
            }
    
    def _generate_test_results(self, session_id: str, metrics: Dict[str, Any]) -> Optional[TestResult]:
        """Generate or update test results record"""
        try:
            # Check if test result already exists
            existing_result = self.db_session.query(TestResult).filter(
                TestResult.test_session_id == session_id
            ).first()
            
            if existing_result:
                # Update existing result
                self._update_test_result(existing_result, metrics)
                return existing_result
            else:
                # Create new test result with ground truth metrics if available
                is_ground_truth_matched = metrics.get("ground_truth_matched", False)
                validation_type = metrics.get("validation_type", "HIL_Fallback")
                
                test_result = TestResult(
                    test_session_id=session_id,
                    pass_rate=metrics.get("success_rate", 0.0),
                    total_detections=metrics.get("total_detections", 0),
                    passed_detections=metrics.get("passed_detections", 0),
                    failed_detections=metrics.get("failed_detections", 0),
                    test_duration_seconds=metrics.get("duration_seconds", 0.0),
                    detection_rate_hz=metrics.get("detection_rate_hz", 0.0),
                    
                    # Real latency metrics from ground truth matching
                    avg_latency_ms=metrics.get("latency_stats", {}).get("average_ms"),
                    max_latency_ms=metrics.get("latency_stats", {}).get("max_ms"),
                    min_latency_ms=metrics.get("latency_stats", {}).get("min_ms"),
                    median_latency_ms=metrics.get("latency_stats", {}).get("median_ms"),
                    std_dev_latency_ms=metrics.get("latency_stats", {}).get("std_dev"),
                    latency_distribution=metrics.get("latency_stats", {}),
                    
                    # Proper ML metrics from ground truth matching (if available)
                    accuracy=metrics.get("recall", metrics.get("success_rate", 0.0) / 100.0),  # Accuracy = recall for HIL
                    precision=metrics.get("precision", metrics.get("success_rate", 0.0) / 100.0),
                    recall=metrics.get("recall", metrics.get("success_rate", 0.0) / 100.0),
                    f1_score=metrics.get("f1_score", metrics.get("success_rate", 0.0) / 100.0),
                    
                    # Confusion matrix from ground truth matching
                    true_positives=metrics.get("passed_detections", 0),
                    false_positives=metrics.get("failed_detections", 0),
                    false_negatives=metrics.get("missed_detections", 0),
                    
                    validation_type=validation_type,
                    statistical_analysis=metrics.get("latency_stats", {}),
                    confidence_intervals={"confidence_level": 0.95, "ground_truth_matched": is_ground_truth_matched}
                )
                
                self.db_session.add(test_result)
                return test_result
                
        except Exception as e:
            logger.error(f"Error generating test results: {e}")
            return None
    
    def _update_test_result(self, test_result: TestResult, metrics: Dict[str, Any]) -> None:
        """Update existing test result with new metrics"""
        test_result.pass_rate = metrics.get("success_rate", 0.0)
        test_result.total_detections = metrics.get("total_detections", 0)
        test_result.passed_detections = metrics.get("passed_detections", 0)
        test_result.failed_detections = metrics.get("failed_detections", 0)
        test_result.test_duration_seconds = metrics.get("duration_seconds", 0.0)
        test_result.detection_rate_hz = metrics.get("detection_rate_hz", 0.0)
        
        # Update LabJack timing metrics
        latency_stats = metrics.get("latency_stats", {})
        test_result.avg_latency_ms = latency_stats.get("average_ms")
        test_result.max_latency_ms = latency_stats.get("max_ms")
        test_result.min_latency_ms = latency_stats.get("min_ms")
        test_result.median_latency_ms = latency_stats.get("median_ms")
        test_result.std_dev_latency_ms = latency_stats.get("std_dev")
        test_result.latency_distribution = latency_stats
        
        # Update legacy compatibility fields
        success_rate = metrics.get("success_rate", 0.0)
        test_result.accuracy = success_rate / 100.0
        test_result.precision = success_rate / 100.0
        test_result.recall = success_rate / 100.0
        test_result.f1_score = success_rate / 100.0
        test_result.true_positives = metrics.get("passed_detections", 0)
        test_result.false_positives = metrics.get("failed_detections", 0)
    
    def _update_session_metadata(self, test_session: TestSession, metrics: Dict[str, Any]) -> None:
        """Update session metadata with calculated metrics"""
        # Update configuration with results summary
        if not test_session.configuration:
            test_session.configuration = {}
            
        test_session.configuration.update({
            "completion_metadata": {
                "total_detections": metrics.get("total_detections", 0),
                "success_rate": metrics.get("success_rate", 0.0),
                "video_count": metrics.get("video_count", 0),
                "duration_seconds": metrics.get("duration_seconds", 0.0),
                "completed_at": datetime.utcnow().isoformat()
            }
        })
        
        # Update results summary
        if not test_session.results_summary:
            test_session.results_summary = {}
            
        test_session.results_summary.update({
            "status": "completed",
            "metrics": metrics,
            "completion_time": datetime.utcnow().isoformat()
        })
    
    def _get_session_video_count(self, session_id: str) -> int:
        """Get accurate video count for session"""
        try:
            # Get test session to find project
            test_session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            if not test_session:
                return 0
            
            # Method 1: Count videos in the same project
            project_video_count = self.db_session.query(Video).filter(
                Video.project_id == test_session.project_id,
                Video.status != "deleted"
            ).count()
            
            # Method 2: Count unique videos that have detection events in this session
            session_video_count = self.db_session.query(DetectionEvent.video_id).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.video_id.isnot(None)
            ).distinct().count()
            
            # Use the higher count (more inclusive)
            return max(project_video_count, session_video_count, 1)
            
        except Exception as e:
            logger.error(f"Error getting session video count: {e}")
            return 1  # Default to 1 to avoid showing 0
    
    def _generate_session_summary(self, test_session: TestSession, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive session summary"""
        return {
            "session_id": test_session.id,
            "session_name": test_session.name,
            "project_id": test_session.project_id,
            "status": test_session.status,
            "created_at": test_session.created_at.isoformat() if test_session.created_at else None,
            "started_at": test_session.started_at.isoformat() if test_session.started_at else None,
            "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None,
            "video_count": metrics.get("video_count", 1),
            "total_detections": metrics.get("total_detections", 0),
            "success_rate": metrics.get("success_rate", 0.0),
            "duration_seconds": metrics.get("duration_seconds", 0.0),
            "average_latency_ms": metrics.get("latency_stats", {}).get("average_ms"),
            "detection_rate_hz": metrics.get("detection_rate_hz", 0.0)
        }
    
    def _force_complete_with_error(self, session_id: str, error_message: str) -> Dict[str, Any]:
        """Force completion of session with error state"""
        try:
            test_session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            if test_session:
                test_session.status = "completed_with_errors"
                test_session.completed_at = datetime.utcnow()
                
                if not test_session.results_summary:
                    test_session.results_summary = {}
                    
                test_session.results_summary.update({
                    "status": "completed_with_errors",
                    "error_message": error_message,
                    "force_completed": True,
                    "completion_time": datetime.utcnow().isoformat()
                })
                
                self.db_session.commit()
                
                return {
                    "success": True,
                    "message": f"Test session force completed with errors: {error_message}",
                    "session_id": session_id,
                    "status": "completed_with_errors",
                    "error_message": error_message
                }
            
        except Exception as e:
            logger.error(f"Error force completing session: {e}")
            
        return {
            "success": False,
            "message": f"Failed to force complete session: {error_message}",
            "session_id": session_id,
            "status": "error"
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
            
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            "total_detections": 0,
            "passed_detections": 0,
            "failed_detections": 0,
            "success_rate": 0.0,
            "video_count": 0,
            "duration_seconds": 0.0,
            "latency_stats": {},
            "detection_rate_hz": 0.0
        }
    
    def get_session_completion_status(self, session_id: str) -> Dict[str, Any]:
        """Get current completion status of a session"""
        try:
            test_session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            if not test_session:
                return {"error": "Session not found"}
            
            # Get basic session info
            session_info = {
                "session_id": session_id,
                "name": test_session.name,
                "status": test_session.status,
                "created_at": test_session.created_at.isoformat() if test_session.created_at else "Unknown",
                "started_at": test_session.started_at.isoformat() if test_session.started_at else None,
                "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None,
            }
            
            # Get detection events count
            detection_count = self.db_session.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).count()
            
            # Get video count
            video_count = self._get_session_video_count(session_id)
            
            session_info.update({
                "detection_events": detection_count,
                "video_count": video_count,
                "has_results": detection_count > 0,
                "completion_ready": test_session.status in ["running", "active"] and detection_count > 0
            })
            
            return session_info
            
        except Exception as e:
            logger.error(f"Error getting session completion status: {e}")
            return {"error": str(e)}


# Global service instance helper
def get_session_completion_service(db_session: Session) -> SessionCompletionService:
    """Get session completion service instance"""
    return SessionCompletionService(db_session)


def complete_test_session_simple(db_session: Session, session_id: str) -> Dict[str, Any]:
    """Simple wrapper for completing a test session"""
    service = SessionCompletionService(db_session)
    return service.complete_test_session(session_id)