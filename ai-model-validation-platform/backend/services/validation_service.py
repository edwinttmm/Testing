from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal
from crud import get_ground_truth_objects, get_detection_events, get_test_session
from schemas import ValidationResult, ValidationMetrics, DetectionEventResponse
from services.ground_truth_matching_service import GroundTruthMatchingService, SessionMetrics
import logging

logger = logging.getLogger(__name__)

class ValidationService:
    def __init__(self):
        self.ground_truth_matcher = GroundTruthMatchingService()
    
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

            # FIX: For validating single detection, we assume timestamp is already video-relative
            # since this is called during detection processing, not from ground truth matching
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
    
    def get_session_results(self, session_id: str, force_rematch: bool = False) -> Optional[ValidationResult]:
        """Get comprehensive validation results for a test session using advanced ground truth matching"""
        db = SessionLocal()
        try:
            # Get test session
            test_session = get_test_session(db, session_id)
            if not test_session:
                return None
            
            # Use the new ground truth matching service for comprehensive analysis
            session_metrics = self.ground_truth_matcher.match_detections_to_ground_truth(
                session_id, force_rematch=force_rematch
            )
            
            if not session_metrics:
                # Fallback to legacy method if advanced matching fails
                logger.warning(f"Advanced matching failed for session {session_id}, using legacy method")
                return self._get_legacy_session_results(db, session_id)
            
            # Get all detection events for response format
            detection_events = get_detection_events(db, session_id)
            
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
            
            # Convert SessionMetrics to ValidationMetrics format
            validation_metrics = ValidationMetrics(
                true_positives=session_metrics.true_positives,
                false_positives=session_metrics.false_positives,
                false_negatives=session_metrics.false_negatives,
                precision=session_metrics.precision,
                recall=session_metrics.recall,
                f1_score=session_metrics.f1_score,
                accuracy=session_metrics.accuracy
            )
            
            return ValidationResult(
                test_session_id=session_id,
                metrics=validation_metrics,
                detection_events=detection_responses,
                total_ground_truth=session_metrics.total_ground_truth,
                total_detections=session_metrics.total_detections
            )
            
        except Exception as e:
            logger.error(f"Error getting session results: {str(e)}", exc_info=True)
            return None
        finally:
            db.close()
    
    def _get_legacy_session_results(self, db: Session, session_id: str) -> Optional[ValidationResult]:
        """Legacy method for getting session results - kept for backward compatibility"""
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
            logger.error(f"Error in legacy session results: {str(e)}", exc_info=True)
            return None
    
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

                # FIX: Use video_relative_timestamp if available to avoid UNIX epoch vs video-relative mismatch
                det_timestamp = detection.video_relative_timestamp if hasattr(detection, 'video_relative_timestamp') and detection.video_relative_timestamp is not None else detection.timestamp
                time_diff = abs(gt_obj.timestamp - det_timestamp)
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
        
        # Get detailed analysis from ground truth matcher
        detailed_analysis = self.ground_truth_matcher.get_detailed_analysis(session_id)
        
        # This would generate a PDF report using ReportLab
        # For now, return a summary dict with enhanced analysis
        report = {
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
        
        # Add detailed analysis if available
        if detailed_analysis:
            report["detailed_analysis"] = detailed_analysis
        
        return report
    
    def get_comprehensive_session_metrics(self, session_id: str, force_rematch: bool = False) -> Optional[SessionMetrics]:
        """
        Get comprehensive session metrics using the advanced ground truth matching service.
        
        This method provides more detailed metrics than the standard ValidationMetrics,
        including latency statistics, temporal analysis, and quality scores.
        
        Args:
            session_id: Test session identifier
            force_rematch: Force re-matching even if results exist
            
        Returns:
            SessionMetrics object with comprehensive analysis or None
        """
        try:
            return self.ground_truth_matcher.match_detections_to_ground_truth(
                session_id, force_rematch=force_rematch
            )
        except Exception as e:
            logger.error(f"Error getting comprehensive metrics: {str(e)}", exc_info=True)
            return None
    
    def get_detailed_analysis(self, session_id: str) -> Optional[Dict]:
        """
        Get detailed analysis of ground truth matching results.
        
        This includes temporal offset analysis, quality metrics, and recommendations
        for improving detection performance.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            Detailed analysis dictionary or None
        """
        try:
            return self.ground_truth_matcher.get_detailed_analysis(session_id)
        except Exception as e:
            logger.error(f"Error getting detailed analysis: {str(e)}", exc_info=True)
            return None
    
    def validate_session_with_advanced_matching(
        self,
        session_id: str,
        tolerance_ms: Optional[int] = None,
        force_rematch: bool = False
    ) -> Optional[Dict]:
        """
        Perform comprehensive validation with advanced ground truth matching.
        
        This method combines the ground truth matching service with detailed analysis
        to provide a complete validation report including:
        - Standard metrics (precision, recall, F1)
        - Latency analysis (mean, std, distribution)
        - Temporal offset patterns
        - Quality scores and recommendations
        
        Args:
            session_id: Test session identifier
            tolerance_ms: Custom tolerance window (uses session default if None)
            force_rematch: Force re-matching even if results exist
            
        Returns:
            Comprehensive validation report or None
        """
        try:
            # Perform advanced matching
            session_metrics = self.ground_truth_matcher.match_detections_to_ground_truth(
                session_id, tolerance_ms, force_rematch
            )
            
            if not session_metrics:
                return None
            
            # Get detailed analysis
            detailed_analysis = self.ground_truth_matcher.get_detailed_analysis(session_id)
            
            # Combine into comprehensive report
            report = {
                'session_id': session_id,
                'validation_timestamp': datetime.now().isoformat(),
                'metrics': {
                    'classification': {
                        'true_positives': session_metrics.true_positives,
                        'false_positives': session_metrics.false_positives,
                        'false_negatives': session_metrics.false_negatives,
                        'total_ground_truth': session_metrics.total_ground_truth,
                        'total_detections': session_metrics.total_detections,
                        'matched_detections': session_metrics.matched_detections
                    },
                    'performance': {
                        'precision': session_metrics.precision,
                        'recall': session_metrics.recall,
                        'f1_score': session_metrics.f1_score,
                        'accuracy': session_metrics.accuracy
                    },
                    'latency': {
                        'mean_latency_ms': session_metrics.mean_latency_ms,
                        'std_latency_ms': session_metrics.std_latency_ms,
                        'min_latency_ms': session_metrics.min_latency_ms,
                        'max_latency_ms': session_metrics.max_latency_ms,
                        'within_tolerance_percentage': session_metrics.within_tolerance_percentage
                    }
                },
                'analysis': detailed_analysis or {},
                'summary': {
                    'overall_score': session_metrics.f1_score * 100,
                    'pass_fail_recommendation': 'PASS' if (
                        session_metrics.precision >= 0.8 and 
                        session_metrics.recall >= 0.75 and 
                        session_metrics.mean_latency_ms <= 100
                    ) else 'FAIL',
                    'key_findings': self._generate_key_findings(session_metrics, detailed_analysis)
                }
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Error in advanced validation: {str(e)}", exc_info=True)
            return None
    
    def _generate_key_findings(self, metrics: SessionMetrics, analysis: Optional[Dict]) -> List[str]:
        """Generate key findings from validation results"""
        findings = []
        
        # Performance findings
        if metrics.recall < 0.7:
            findings.append(f"Low recall ({metrics.recall:.1%}) indicates missed detections")
        if metrics.precision < 0.8:
            findings.append(f"Low precision ({metrics.precision:.1%}) indicates false alarms")
        if metrics.f1_score >= 0.85:
            findings.append("Excellent overall detection performance")
        
        # Latency findings
        if metrics.mean_latency_ms > 100:
            findings.append(f"High average latency ({metrics.mean_latency_ms:.1f}ms)")
        if metrics.std_latency_ms > 50:
            findings.append("High latency variability detected")
        
        # Analysis-based findings
        if analysis and 'temporal_analysis' in analysis:
            temp_analysis = analysis['temporal_analysis']
            if temp_analysis.get('mean_offset_ms', 0) > 50:
                findings.append("Consistent positive latency offset detected")
            
            dist = temp_analysis.get('offset_distribution', {})
            if dist.get('early_detections', 0) > dist.get('late_detections', 0) * 2:
                findings.append("System shows tendency for early detections")
        
        if not findings:
            findings.append("System performance within expected parameters")
        
        return findings