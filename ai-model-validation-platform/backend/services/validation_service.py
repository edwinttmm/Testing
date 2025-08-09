from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal
from crud import get_ground_truth_objects, get_detection_events, get_test_session
from schemas import ValidationResult, ValidationMetrics, DetectionEventResponse
import logging

logger = logging.getLogger(__name__)

class ValidationService:
    def __init__(self):
        pass
    
    def validate_detection(self, test_session_id: str, timestamp: float, confidence: float = None) -> str:
        """Validate a single detection against ground truth"""
        db = SessionLocal()
        try:
            # Get test session to find video and tolerance
            test_session = get_test_session(db, test_session_id)
            if not test_session:
                return "ERROR"
            
            # Get ground truth for the video
            ground_truth_objects = get_ground_truth_objects(db, str(test_session.video_id))
            
            # Find matching ground truth within tolerance
            tolerance_seconds = test_session.tolerance_ms / 1000.0
            
            for gt_obj in ground_truth_objects:
                time_diff = abs(gt_obj.timestamp - timestamp)
                if time_diff <= tolerance_seconds:
                    # Found a match - True Positive
                    return "TP"
            
            # No match found - False Positive
            return "FP"
            
        except Exception as e:
            logger.error(f"Error validating detection: {str(e)}", exc_info=True)
            return "ERROR"
        finally:
            db.close()
    
    def get_session_results(self, session_id: str) -> Optional[ValidationResult]:
        """Get comprehensive validation results for a test session"""
        db = SessionLocal()
        try:
            # Get test session
            test_session = get_test_session(db, session_id)
            if not test_session:
                return None
            
            # Get all detection events for this session
            detection_events = get_detection_events(db, session_id)
            
            # Get ground truth for the video
            ground_truth_objects = get_ground_truth_objects(db, str(test_session.video_id))
            
            # Calculate metrics
            metrics = self._calculate_metrics(detection_events, ground_truth_objects, test_session.tolerance_ms)
            
            # Convert detection events to response format
            detection_responses = [
                DetectionEventResponse(
                    id=event.id,
                    test_session_id=event.test_session_id,
                    timestamp=event.timestamp,
                    confidence=event.confidence,
                    class_label=event.class_label,
                    validation_result=event.validation_result,
                    ground_truth_match_id=event.ground_truth_match_id,
                    created_at=event.created_at
                )
                for event in detection_events
            ]
            
            return ValidationResult(
                test_session_id=session_id,
                metrics=metrics,
                detection_events=detection_responses,
                total_ground_truth=len(ground_truth_objects),
                total_detections=len(detection_events)
            )
            
        except Exception as e:
            logger.error(f"Error getting session results: {str(e)}", exc_info=True)
            return None
        finally:
            db.close()
    
    def _calculate_metrics(self, detection_events: List, ground_truth_objects: List, tolerance_ms: int) -> ValidationMetrics:
        """Calculate precision, recall, F1, and accuracy metrics"""
        tolerance_seconds = tolerance_ms / 1000.0
        
        # Count TP, FP, FN
        true_positives = 0
        false_positives = 0
        
        # Track which ground truth objects were detected
        detected_gt_objects = set()
        
        for detection in detection_events:
            is_match = False
            
            for i, gt_obj in enumerate(ground_truth_objects):
                if i in detected_gt_objects:
                    continue
                    
                time_diff = abs(gt_obj.timestamp - detection.timestamp)
                if time_diff <= tolerance_seconds:
                    true_positives += 1
                    detected_gt_objects.add(i)
                    is_match = True
                    break
            
            if not is_match:
                false_positives += 1
        
        # False negatives are ground truth objects that weren't detected
        false_negatives = len(ground_truth_objects) - len(detected_gt_objects)
        
        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = true_positives / len(ground_truth_objects) if len(ground_truth_objects) > 0 else 0
        
        return ValidationMetrics(
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy
        )
    
    def generate_report(self, session_id: str) -> Dict:
        """Generate a comprehensive PDF report for test results"""
        results = self.get_session_results(session_id)
        if not results:
            return None
        
        # This would generate a PDF report using ReportLab
        # For now, return a summary dict
        return {
            "session_id": session_id,
            "summary": {
                "total_detections": results.total_detections,
                "total_ground_truth": results.total_ground_truth,
                "accuracy": f"{results.metrics.accuracy * 100:.1f}%",
                "precision": f"{results.metrics.precision * 100:.1f}%",
                "recall": f"{results.metrics.recall * 100:.1f}%",
                "f1_score": f"{results.metrics.f1_score * 100:.1f}%"
            },
            "metrics": results.metrics,
            "report_generated": True
        }