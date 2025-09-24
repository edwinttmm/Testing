"""
Ground Truth Matching Service

This service provides comprehensive temporal matching between LabJack detections 
and pre-recorded ground truth timing data. It implements sophisticated algorithms
for detection classification, latency calculation, and performance metrics.

Key Features:
- Temporal matching with configurable tolerance windows
- True Positive / False Positive / False Negative classification
- Latency calculation and statistical analysis
- Precision, Recall, F1 Score computation
- Database population with match results
"""

import logging
import statistics
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, func

from database import SessionLocal, get_db
from models import (
    TestSession, DetectionEvent, GroundTruthObject, DetectionComparison
)
try:
    from models import PerformanceMetrics, ValidationResult as ValidationResultEnum
except ImportError:
    # PerformanceMetrics not available in models, define local stub
    PerformanceMetrics = None
    ValidationResultEnum = None
from schemas_annotation import VRUTypeEnum

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Data class for individual match results"""
    ground_truth_id: str
    detection_event_id: Optional[str]
    match_type: str  # 'TP', 'FP', 'FN'
    temporal_offset: float  # in milliseconds
    confidence: Optional[float]
    iou_score: Optional[float]  # Temporal overlap score
    latency_ms: Optional[float]  # Actual detection latency


@dataclass
class SessionMetrics:
    """Comprehensive metrics for a test session"""
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    mean_latency_ms: float
    std_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float
    within_tolerance_percentage: float
    total_ground_truth: int
    total_detections: int
    matched_detections: int


class GroundTruthMatchingService:
    """
    Comprehensive service for matching LabJack detections against ground truth data.
    
    This service implements temporal matching algorithms that handle the complexity
    of real-world detection systems with varying latencies and precision requirements.
    """
    
    def __init__(self, default_tolerance_ms: int = 100):
        """
        Initialize the Ground Truth Matching Service.
        
        Args:
            default_tolerance_ms: Default tolerance window in milliseconds
        """
        self.default_tolerance_ms = default_tolerance_ms
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
    def match_detections_to_ground_truth(
        self,
        session_id: str,
        tolerance_ms: Optional[int] = None,
        force_rematch: bool = False
    ) -> Optional[SessionMetrics]:
        """
        Match all LabJack detections to ground truth objects for a test session.
        
        This is the main entry point for ground truth matching. It performs:
        1. Retrieval of all detection events and ground truth objects
        2. Temporal matching within tolerance windows
        3. Classification as TP/FP/FN
        4. Latency calculation
        5. Database population
        6. Metrics calculation
        
        Args:
            session_id: Test session identifier
            tolerance_ms: Tolerance window in milliseconds (uses session default if None)
            force_rematch: Force re-matching even if results already exist
            
        Returns:
            SessionMetrics object with comprehensive results or None on error
        """
        db = SessionLocal()
        try:
            self.logger.info(f"Starting ground truth matching for session {session_id}")
            
            # Get test session and validate
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                self.logger.error(f"Test session {session_id} not found")
                return None
                
            # Use session tolerance if not specified
            if tolerance_ms is None:
                tolerance_ms = test_session.tolerance_ms or self.default_tolerance_ms
                
            self.logger.info(f"Using tolerance window: ±{tolerance_ms}ms")
            
            # Check if matching already exists and force_rematch is False
            existing_comparisons = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session_id
            ).count()
            
            if existing_comparisons > 0 and not force_rematch:
                self.logger.info(f"Found {existing_comparisons} existing comparisons, using cached results")
                return self._calculate_session_metrics(db, session_id)
            
            # Clear existing comparisons if force_rematch
            if force_rematch and existing_comparisons > 0:
                self.logger.info("Force rematch enabled, clearing existing comparisons")
                db.query(DetectionComparison).filter(
                    DetectionComparison.test_session_id == session_id
                ).delete()
                db.commit()
            
            # Get all detection events for this session using raw SQL to avoid column mismatch
            from sqlalchemy import text
            detection_query = text("""
                SELECT id, timestamp, confidence, class_label, actual_latency_ms, 
                       video_relative_timestamp, video_frame_number, timing_sync_quality
                FROM detection_events 
                WHERE test_session_id = :session_id 
                ORDER BY timestamp
            """)
            detection_results = db.execute(detection_query, {'session_id': session_id}).fetchall()
            
            # Convert to objects for compatibility
            detection_events = []
            for row in detection_results:
                # Create a simple object with the fields we need
                class DetectionEventProxy:
                    def __init__(self, row):
                        self.id = row[0]
                        self.timestamp = row[1]
                        self.confidence = row[2]
                        self.class_label = row[3]
                        self.actual_latency_ms = row[4]
                        self.video_relative_timestamp = row[5]
                        self.video_frame_number = row[6]
                        self.timing_sync_quality = row[7]
                
                detection_events.append(DetectionEventProxy(row))
            
            self.logger.info(f"Found {len(detection_events)} detection events")
            
            # Get all ground truth objects for the video
            ground_truth_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == test_session.video_id
            ).order_by(GroundTruthObject.timestamp).all()
            
            self.logger.info(f"Found {len(ground_truth_objects)} ground truth objects")
            
            if not ground_truth_objects:
                self.logger.warning("No ground truth objects found for matching")
                return self._create_empty_metrics(len(detection_events))
            
            # Perform temporal matching
            match_results = self._perform_temporal_matching(
                detection_events, ground_truth_objects, tolerance_ms
            )
            
            # Populate database with results
            self._populate_detection_comparisons(db, session_id, match_results)
            
            # Calculate and store performance metrics
            metrics = self._calculate_and_store_metrics(db, session_id, match_results)
            
            # Update test session with results
            self._update_test_session_results(db, test_session, metrics)
            
            db.commit()
            self.logger.info(f"Ground truth matching completed for session {session_id}")
            
            return metrics
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error in ground truth matching: {str(e)}", exc_info=True)
            return None
        finally:
            db.close()
    
    def _perform_temporal_matching(
        self,
        detection_events: List[DetectionEvent],
        ground_truth_objects: List[GroundTruthObject],
        tolerance_ms: int
    ) -> List[MatchResult]:
        """
        Perform temporal matching between detections and ground truth.
        
        Algorithm:
        1. For each ground truth object, find the closest detection within tolerance
        2. Handle multiple detections near the same ground truth (first-match wins)
        3. Classify remaining detections as false positives
        4. Classify unmatched ground truth as false negatives
        
        Args:
            detection_events: List of detection events
            ground_truth_objects: List of ground truth objects
            tolerance_ms: Tolerance window in milliseconds
            
        Returns:
            List of MatchResult objects
        """
        tolerance_seconds = tolerance_ms / 1000.0
        match_results = []
        used_detections = set()
        
        self.logger.info(f"Performing temporal matching with {tolerance_ms}ms tolerance")
        
        # Phase 1: Match ground truth objects to nearest detections (True Positives)
        for gt_obj in ground_truth_objects:
            best_match = None
            best_time_diff = float('inf')
            
            for i, detection in enumerate(detection_events):
                if i in used_detections:
                    continue
                    
                # Calculate temporal difference
                time_diff = abs(detection.timestamp - gt_obj.timestamp)
                
                # Check if within tolerance and better than current best
                if time_diff <= tolerance_seconds and time_diff < best_time_diff:
                    best_match = (i, detection)
                    best_time_diff = time_diff
            
            if best_match:
                # True Positive match found
                detection_idx, detection = best_match
                used_detections.add(detection_idx)
                
                # Calculate metrics
                temporal_offset_ms = (detection.timestamp - gt_obj.timestamp) * 1000
                latency_ms = temporal_offset_ms if temporal_offset_ms >= 0 else None
                iou_score = self._calculate_temporal_iou(
                    gt_obj.timestamp, detection.timestamp, tolerance_seconds
                )
                
                match_result = MatchResult(
                    ground_truth_id=gt_obj.id,
                    detection_event_id=detection.id,
                    match_type='TP',
                    temporal_offset=temporal_offset_ms,
                    confidence=detection.confidence,
                    iou_score=iou_score,
                    latency_ms=latency_ms
                )
                match_results.append(match_result)
                
                self.logger.debug(
                    f"TP Match: GT@{gt_obj.timestamp:.3f}s → Detection@{detection.timestamp:.3f}s "
                    f"(offset: {temporal_offset_ms:+.1f}ms)"
                )
            else:
                # False Negative - ground truth with no matching detection
                match_result = MatchResult(
                    ground_truth_id=gt_obj.id,
                    detection_event_id=None,
                    match_type='FN',
                    temporal_offset=0.0,
                    confidence=None,
                    iou_score=0.0,
                    latency_ms=None
                )
                match_results.append(match_result)
                
                self.logger.debug(f"FN: GT@{gt_obj.timestamp:.3f}s - No matching detection")
        
        # Phase 2: Mark remaining detections as False Positives
        for i, detection in enumerate(detection_events):
            if i not in used_detections:
                match_result = MatchResult(
                    ground_truth_id=None,  # No matching ground truth
                    detection_event_id=detection.id,
                    match_type='FP',
                    temporal_offset=0.0,
                    confidence=detection.confidence,
                    iou_score=0.0,
                    latency_ms=None
                )
                match_results.append(match_result)
                
                self.logger.debug(f"FP: Detection@{detection.timestamp:.3f}s - No matching GT")
        
        # Log matching summary
        tp_count = sum(1 for mr in match_results if mr.match_type == 'TP')
        fp_count = sum(1 for mr in match_results if mr.match_type == 'FP')
        fn_count = sum(1 for mr in match_results if mr.match_type == 'FN')
        
        self.logger.info(
            f"Matching completed: {tp_count} TP, {fp_count} FP, {fn_count} FN "
            f"(Total: {len(match_results)} comparisons)"
        )
        
        return match_results
    
    def _calculate_temporal_iou(
        self,
        gt_timestamp: float,
        detection_timestamp: float,
        tolerance_seconds: float
    ) -> float:
        """
        Calculate temporal Intersection over Union (IoU) score.
        
        This provides a normalized score based on how close the detection
        is to the ground truth within the tolerance window.
        
        Args:
            gt_timestamp: Ground truth timestamp
            detection_timestamp: Detection timestamp
            tolerance_seconds: Tolerance window in seconds
            
        Returns:
            IoU score between 0.0 and 1.0
        """
        time_diff = abs(gt_timestamp - detection_timestamp)
        if time_diff > tolerance_seconds:
            return 0.0
        
        # Calculate IoU based on temporal overlap
        # Perfect match (0 diff) = 1.0, at tolerance boundary = ~0.5
        iou_score = 1.0 - (time_diff / tolerance_seconds) * 0.5
        return max(0.0, min(1.0, iou_score))
    
    def _populate_detection_comparisons(
        self,
        db: Session,
        session_id: str,
        match_results: List[MatchResult]
    ) -> None:
        """
        Populate the detection_comparisons table with match results.
        
        Args:
            db: Database session
            session_id: Test session ID
            match_results: List of match results to store
        """
        self.logger.info(f"Populating detection_comparisons table with {len(match_results)} results")
        
        for match_result in match_results:
            comparison = DetectionComparison(
                test_session_id=session_id,
                ground_truth_id=match_result.ground_truth_id,
                detection_event_id=match_result.detection_event_id,
                match_type=match_result.match_type,
                iou_score=match_result.iou_score,
                temporal_offset=match_result.temporal_offset,
                distance_error=None,  # Not applicable for temporal matching
                notes=f"Temporal matching with offset {match_result.temporal_offset:.1f}ms"
            )
            db.add(comparison)
        
        self.logger.info("Detection comparisons populated successfully")
    
    def _calculate_and_store_metrics(
        self,
        db: Session,
        session_id: str,
        match_results: List[MatchResult]
    ) -> SessionMetrics:
        """
        Calculate comprehensive performance metrics and store in database.
        
        Args:
            db: Database session
            session_id: Test session ID
            match_results: List of match results
            
        Returns:
            SessionMetrics object
        """
        # Count classifications
        tp_results = [mr for mr in match_results if mr.match_type == 'TP']
        fp_results = [mr for mr in match_results if mr.match_type == 'FP']
        fn_results = [mr for mr in match_results if mr.match_type == 'FN']
        
        true_positives = len(tp_results)
        false_positives = len(fp_results)
        false_negatives = len(fn_results)
        
        # Calculate core metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        
        # Calculate latency metrics
        valid_latencies = [mr.latency_ms for mr in tp_results if mr.latency_ms is not None and mr.latency_ms >= 0]
        
        if valid_latencies:
            mean_latency_ms = statistics.mean(valid_latencies)
            std_latency_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
            max_latency_ms = max(valid_latencies)
            min_latency_ms = min(valid_latencies)
            
            # Calculate percentage within tolerance (assuming tolerance is the acceptance criteria)
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            tolerance_ms = test_session.tolerance_ms if test_session else self.default_tolerance_ms
            within_tolerance_count = sum(1 for lat in valid_latencies if lat <= tolerance_ms)
            within_tolerance_percentage = (within_tolerance_count / len(valid_latencies)) * 100
        else:
            mean_latency_ms = 0.0
            std_latency_ms = 0.0
            max_latency_ms = 0.0
            min_latency_ms = 0.0
            within_tolerance_percentage = 0.0
        
        # Create metrics object
        metrics = SessionMetrics(
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            mean_latency_ms=mean_latency_ms,
            std_latency_ms=std_latency_ms,
            max_latency_ms=max_latency_ms,
            min_latency_ms=min_latency_ms,
            within_tolerance_percentage=within_tolerance_percentage,
            total_ground_truth=true_positives + false_negatives,
            total_detections=true_positives + false_positives,
            matched_detections=true_positives
        )
        
        # Store in PerformanceMetrics table if available
        if PerformanceMetrics is not None:
            performance_metrics = PerformanceMetrics(
                test_session_id=session_id,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                accuracy=accuracy,
                mean_latency_ms=mean_latency_ms,
                std_latency_ms=std_latency_ms,
                max_latency_ms=max_latency_ms,
                within_tolerance_percentage=within_tolerance_percentage,
                true_positives=true_positives,
                false_positives=false_positives,
                false_negatives=false_negatives,
                overall_score=f1_score * 100,  # Overall score as percentage
                statistical_data={
                    'latency_distribution': valid_latencies[:100],  # Sample for analysis
                    'temporal_offsets': [mr.temporal_offset for mr in tp_results],
                    'confidence_scores': [mr.confidence for mr in tp_results if mr.confidence is not None],
                    'matching_summary': {
                        'total_comparisons': len(match_results),
                        'tp_count': true_positives,
                        'fp_count': false_positives,
                        'fn_count': false_negatives
                    }
                }
            )
            
            # Remove existing metrics for this session
            db.query(PerformanceMetrics).filter(
                PerformanceMetrics.test_session_id == session_id
            ).delete()
            
            db.add(performance_metrics)
        
        self.logger.info(
            f"Metrics calculated - Precision: {precision:.3f}, Recall: {recall:.3f}, "
            f"F1: {f1_score:.3f}, Mean Latency: {mean_latency_ms:.1f}ms"
        )
        
        return metrics
    
    def _update_test_session_results(
        self,
        db: Session,
        test_session: TestSession,
        metrics: SessionMetrics
    ) -> None:
        """
        Update test session with summary results.
        
        Args:
            db: Database session
            test_session: TestSession object
            metrics: Calculated metrics
        """
        test_session.actual_detections = metrics.total_detections
        test_session.overall_score = metrics.f1_score * 100
        
        # Determine pass/fail result based on criteria
        if metrics.precision >= 0.8 and metrics.recall >= 0.75 and metrics.mean_latency_ms <= 100:
            test_session.pass_fail_result = "PASS"
        elif metrics.precision >= 0.6 and metrics.recall >= 0.6:
            test_session.pass_fail_result = "CONDITIONAL_PASS"
        else:
            test_session.pass_fail_result = "FAIL"
        
        # Update completion time if not set
        if not test_session.completed_at:
            test_session.completed_at = datetime.utcnow()
        
        self.logger.info(f"Test session updated with result: {test_session.pass_fail_result}")
    
    def _calculate_session_metrics(self, db: Session, session_id: str) -> Optional[SessionMetrics]:
        """
        Calculate session metrics from existing detection comparisons.
        
        Args:
            db: Database session
            session_id: Test session ID
            
        Returns:
            SessionMetrics object or None if no data
        """
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id
        ).all()
        
        if not comparisons:
            return None
        
        # Convert to match results format
        match_results = []
        for comp in comparisons:
            match_result = MatchResult(
                ground_truth_id=comp.ground_truth_id,
                detection_event_id=comp.detection_event_id,
                match_type=comp.match_type,
                temporal_offset=comp.temporal_offset or 0.0,
                confidence=None,  # Would need to join with detection_events
                iou_score=comp.iou_score,
                latency_ms=comp.temporal_offset if comp.temporal_offset and comp.temporal_offset >= 0 else None
            )
            match_results.append(match_result)
        
        return self._calculate_metrics_from_results(match_results)
    
    def _calculate_metrics_from_results(self, match_results: List[MatchResult]) -> SessionMetrics:
        """
        Calculate metrics from match results without database storage.
        
        Args:
            match_results: List of match results
            
        Returns:
            SessionMetrics object
        """
        tp_results = [mr for mr in match_results if mr.match_type == 'TP']
        fp_results = [mr for mr in match_results if mr.match_type == 'FP']
        fn_results = [mr for mr in match_results if mr.match_type == 'FN']
        
        true_positives = len(tp_results)
        false_positives = len(fp_results)
        false_negatives = len(fn_results)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        
        valid_latencies = [mr.latency_ms for mr in tp_results if mr.latency_ms is not None and mr.latency_ms >= 0]
        
        if valid_latencies:
            mean_latency_ms = statistics.mean(valid_latencies)
            std_latency_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
            max_latency_ms = max(valid_latencies)
            min_latency_ms = min(valid_latencies)
            within_tolerance_count = sum(1 for lat in valid_latencies if lat <= self.default_tolerance_ms)
            within_tolerance_percentage = (within_tolerance_count / len(valid_latencies)) * 100
        else:
            mean_latency_ms = 0.0
            std_latency_ms = 0.0
            max_latency_ms = 0.0
            min_latency_ms = 0.0
            within_tolerance_percentage = 0.0
        
        return SessionMetrics(
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            mean_latency_ms=mean_latency_ms,
            std_latency_ms=std_latency_ms,
            max_latency_ms=max_latency_ms,
            min_latency_ms=min_latency_ms,
            within_tolerance_percentage=within_tolerance_percentage,
            total_ground_truth=true_positives + false_negatives,
            total_detections=true_positives + false_positives,
            matched_detections=true_positives
        )
    
    def _create_empty_metrics(self, total_detections: int) -> SessionMetrics:
        """
        Create empty metrics for sessions with no ground truth.
        
        Args:
            total_detections: Number of detections (all become false positives)
            
        Returns:
            SessionMetrics with all detections as false positives
        """
        return SessionMetrics(
            true_positives=0,
            false_positives=total_detections,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            accuracy=0.0,
            mean_latency_ms=0.0,
            std_latency_ms=0.0,
            max_latency_ms=0.0,
            min_latency_ms=0.0,
            within_tolerance_percentage=0.0,
            total_ground_truth=0,
            total_detections=total_detections,
            matched_detections=0
        )
    
    def get_detailed_analysis(self, session_id: str) -> Optional[Dict]:
        """
        Get detailed analysis of matching results for a session.
        
        Args:
            session_id: Test session ID
            
        Returns:
            Detailed analysis dictionary or None
        """
        db = SessionLocal()
        try:
            # Get all comparisons with related data
            comparisons = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session_id
            ).all()
            
            if not comparisons:
                return None
            
            # Analyze patterns
            tp_comparisons = [c for c in comparisons if c.match_type == 'TP']
            fp_comparisons = [c for c in comparisons if c.match_type == 'FP']
            fn_comparisons = [c for c in comparisons if c.match_type == 'FN']
            
            # Calculate detailed statistics
            temporal_offsets = [c.temporal_offset for c in tp_comparisons if c.temporal_offset is not None]
            iou_scores = [c.iou_score for c in tp_comparisons if c.iou_score is not None]
            
            analysis = {
                'session_id': session_id,
                'summary': {
                    'total_comparisons': len(comparisons),
                    'true_positives': len(tp_comparisons),
                    'false_positives': len(fp_comparisons),
                    'false_negatives': len(fn_comparisons)
                },
                'temporal_analysis': {
                    'mean_offset_ms': statistics.mean(temporal_offsets) if temporal_offsets else 0,
                    'std_offset_ms': statistics.stdev(temporal_offsets) if len(temporal_offsets) > 1 else 0,
                    'min_offset_ms': min(temporal_offsets) if temporal_offsets else 0,
                    'max_offset_ms': max(temporal_offsets) if temporal_offsets else 0,
                    'offset_distribution': {
                        'early_detections': len([o for o in temporal_offsets if o < -10]),
                        'on_time_detections': len([o for o in temporal_offsets if -10 <= o <= 10]),
                        'late_detections': len([o for o in temporal_offsets if o > 10])
                    }
                },
                'quality_analysis': {
                    'mean_iou_score': statistics.mean(iou_scores) if iou_scores else 0,
                    'high_quality_matches': len([s for s in iou_scores if s > 0.8]),
                    'medium_quality_matches': len([s for s in iou_scores if 0.5 <= s <= 0.8]),
                    'low_quality_matches': len([s for s in iou_scores if s < 0.5])
                },
                'recommendations': self._generate_recommendations(comparisons)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error in detailed analysis: {str(e)}", exc_info=True)
            return None
        finally:
            db.close()
    
    def _generate_recommendations(self, comparisons: List[DetectionComparison]) -> List[str]:
        """
        Generate recommendations based on analysis results.
        
        Args:
            comparisons: List of detection comparisons
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        tp_count = len([c for c in comparisons if c.match_type == 'TP'])
        fp_count = len([c for c in comparisons if c.match_type == 'FP'])
        fn_count = len([c for c in comparisons if c.match_type == 'FN'])
        
        total_gt = tp_count + fn_count
        total_detections = tp_count + fp_count
        
        if total_gt > 0:
            recall = tp_count / total_gt
            if recall < 0.7:
                recommendations.append("Consider improving detection sensitivity to reduce missed detections")
        
        if total_detections > 0:
            precision = tp_count / total_detections
            if precision < 0.8:
                recommendations.append("Consider improving detection specificity to reduce false alarms")
        
        # Analyze temporal offsets for timing recommendations
        tp_comparisons = [c for c in comparisons if c.match_type == 'TP' and c.temporal_offset is not None]
        if tp_comparisons:
            mean_offset = statistics.mean([c.temporal_offset for c in tp_comparisons])
            if mean_offset > 50:
                recommendations.append("System shows consistent positive latency - consider optimizing processing pipeline")
            elif mean_offset < -20:
                recommendations.append("System shows early detection pattern - verify timing calibration")
        
        if not recommendations:
            recommendations.append("System performance is within acceptable parameters")
        
        return recommendations

    def get_matching_results_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of matching results for API responses.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            Dictionary containing matching results summary
        """
        try:
            # Get the detailed matching results
            metrics = self.match_detections_to_ground_truth(session_id)
            
            if metrics is None:
                # Return empty summary if no results
                return {
                    'session_id': session_id,
                    'summary': {
                        'total_detections': 0,
                        'matched_detections': 0,
                        'precision': 0.0,
                        'recall': 0.0,
                        'f1_score': 0.0,
                        'mean_latency_ms': 0.0
                    },
                    'details': {
                        'true_positives': 0,
                        'false_positives': 0,
                        'false_negatives': 0,
                        'ground_truth_count': 0
                    },
                    'status': 'no_data'
                }
            
            # Format the results for API consumption
            summary = {
                'session_id': session_id,
                'summary': {
                    'total_detections': metrics.total_detections,
                    'matched_detections': metrics.matched_detections,
                    'precision': round(metrics.precision, 3),
                    'recall': round(metrics.recall, 3),
                    'f1_score': round(metrics.f1_score, 3),
                    'mean_latency_ms': round(metrics.mean_latency_ms, 2)
                },
                'details': {
                    'true_positives': metrics.true_positives,
                    'false_positives': metrics.false_positives,
                    'false_negatives': metrics.false_negatives,
                    'ground_truth_count': metrics.total_ground_truth
                },
                'performance': {
                    'accuracy': round(metrics.accuracy, 3),
                    'within_tolerance_percentage': round(metrics.within_tolerance_percentage, 1),
                    'std_latency_ms': round(metrics.std_latency_ms, 2),
                    'max_latency_ms': round(metrics.max_latency_ms, 2),
                    'min_latency_ms': round(metrics.min_latency_ms, 2)
                },
                'status': 'success'
            }
            
            # Add result interpretation
            if metrics.total_ground_truth > 0:
                detection_rate = (metrics.matched_detections / metrics.total_ground_truth) * 100
                summary['summary']['detection_rate_percentage'] = round(detection_rate, 1)
                
                # Add status message based on performance
                if metrics.precision >= 0.8 and metrics.recall >= 0.75:
                    summary['status_message'] = f"{metrics.matched_detections}/{metrics.total_ground_truth} ground truth found - HIGH PERFORMANCE"
                elif metrics.precision >= 0.6 and metrics.recall >= 0.6:
                    summary['status_message'] = f"{metrics.matched_detections}/{metrics.total_ground_truth} ground truth found - MODERATE PERFORMANCE"
                else:
                    summary['status_message'] = f"{metrics.matched_detections}/{metrics.total_ground_truth} ground truth found - NEEDS IMPROVEMENT"
            else:
                summary['status_message'] = "No ground truth data available for comparison"
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting matching results summary: {str(e)}", exc_info=True)
            return {
                'session_id': session_id,
                'summary': {
                    'total_detections': 0,
                    'matched_detections': 0,
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1_score': 0.0,
                    'mean_latency_ms': 0.0
                },
                'details': {
                    'true_positives': 0,
                    'false_positives': 0,
                    'false_negatives': 0,
                    'ground_truth_count': 0
                },
                'status': 'error',
                'error_message': str(e)
            }


# Module-level convenience functions for API compatibility
_service_instance = None

def get_ground_truth_matching_service() -> GroundTruthMatchingService:
    """Get singleton instance of ground truth matching service"""
    global _service_instance
    if _service_instance is None:
        _service_instance = GroundTruthMatchingService()
    return _service_instance


def get_session_matching_results(session_id: str, db: Session = None) -> Optional[SessionMetrics]:
    """
    Get comprehensive matching results for a test session.
    
    Args:
        session_id: Test session identifier
        db: Optional database session (will create if not provided)
    
    Returns:
        SessionMetrics object with precision, recall, latency metrics, etc.
    """
    service = get_ground_truth_matching_service()
    
    if db is None:
        db = SessionLocal()
        try:
            return service._calculate_session_metrics(db, session_id)
        finally:
            db.close()
    else:
        return service._calculate_session_metrics(db, session_id)


def get_detection_event_details(session_id: str, db: Session = None) -> List[Dict]:
    """
    Get detailed detection event information for a session.
    
    Args:
        session_id: Test session identifier  
        db: Optional database session
        
    Returns:
        List of detection event details with ground truth correlation
    """
    if db is None:
        db = SessionLocal()
        try:
            return _get_detection_event_details_impl(session_id, db)
        finally:
            db.close()
    else:
        return _get_detection_event_details_impl(session_id, db)


def _get_detection_event_details_impl(session_id: str, db: Session) -> List[Dict]:
    """Implementation of detection event details retrieval"""
    try:
        # Get detection events with comparisons
        events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).all()
        
        # Get detection comparisons 
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id
        ).all()
        
        # Create lookup for comparisons by detection event ID
        comparison_lookup = {comp.detection_event_id: comp for comp in comparisons if comp.detection_event_id}
        
        event_details = []
        for event in events:
            comp = comparison_lookup.get(event.id)
            
            detail = {
                'id': event.id,
                'video_time': getattr(event, 'video_relative_timestamp', event.timestamp),
                'detected_time': event.timestamp,
                'latency_ms': getattr(event, 'actual_latency_ms', None),
                'confidence': getattr(event, 'confidence', None),
                'status': 'matched' if comp and comp.match_type == 'TP' else 'unmatched',
                'match_type': comp.match_type if comp else 'unmatched',
                'temporal_offset_ms': comp.temporal_offset if comp else None,
                'status_color': 'green' if comp and comp.match_type == 'TP' else 'orange' if comp and comp.match_type == 'FP' else 'gray',
                'display_text': '✓ Matched' if comp and comp.match_type == 'TP' else '⚠ False Positive' if comp and comp.match_type == 'FP' else '○ Unmatched'
            }
            event_details.append(detail)
        
        # Add missed ground truth (false negatives)
        missed_gt = db.query(DetectionComparison).filter(
            and_(
                DetectionComparison.test_session_id == session_id,
                DetectionComparison.match_type == 'FN'
            )
        ).all()
        
        for comp in missed_gt:
            if comp.ground_truth_id:
                # Get ground truth object details
                gt_obj = db.query(GroundTruthObject).filter(
                    GroundTruthObject.id == comp.ground_truth_id
                ).first()
                
                detail = {
                    'id': f"gt_{comp.ground_truth_id}",
                    'video_time': gt_obj.timestamp if gt_obj else None,
                    'ground_truth_time': gt_obj.timestamp if gt_obj else None,
                    'detected_time': None,
                    'latency_ms': None,
                    'status': 'missed',
                    'match_type': 'false_negative',
                    'status_color': 'red',
                    'display_text': '✗ Missed GT'
                }
                event_details.append(detail)
        
        # Sort by video time
        event_details.sort(key=lambda x: x.get('video_time', 0) or 0)
        
        return event_details
        
    except Exception as e:
        logger.error(f"Error getting detection event details: {e}")
        return []


def calculate_project_metrics(project_id: str, db: Session = None) -> Dict:
    """
    Calculate aggregated metrics across all sessions in a project.
    
    Args:
        project_id: Project identifier
        db: Optional database session
        
    Returns:
        Aggregated project metrics
    """
    if db is None:
        db = SessionLocal()
        try:
            return _calculate_project_metrics_impl(project_id, db)
        finally:
            db.close()
    else:
        return _calculate_project_metrics_impl(project_id, db)


def _calculate_project_metrics_impl(project_id: str, db: Session) -> Dict:
    """Implementation of project metrics calculation"""
    try:
        # Get all test sessions for the project
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).all()
        
        if not sessions:
            return {
                'project_id': project_id,
                'total_sessions': 0,
                'aggregated_metrics': None
            }
        
        # Aggregate metrics across all sessions
        all_metrics = []
        for session in sessions:
            metrics = get_session_matching_results(session.id, db)
            if metrics:
                all_metrics.append(metrics)
        
        if not all_metrics:
            return {
                'project_id': project_id,
                'total_sessions': len(sessions),
                'aggregated_metrics': None
            }
        
        # Calculate aggregated statistics
        total_tp = sum(m.true_positives for m in all_metrics)
        total_fp = sum(m.false_positives for m in all_metrics)
        total_fn = sum(m.false_negatives for m in all_metrics)
        
        agg_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        agg_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        agg_f1 = 2 * (agg_precision * agg_recall) / (agg_precision + agg_recall) if (agg_precision + agg_recall) > 0 else 0.0
        
        # Average latency across all valid measurements
        all_latencies = []
        for m in all_metrics:
            if m.mean_latency_ms > 0:
                all_latencies.append(m.mean_latency_ms)
        
        avg_latency = statistics.mean(all_latencies) if all_latencies else 0.0
        
        return {
            'project_id': project_id,
            'total_sessions': len(sessions),
            'successful_sessions': len(all_metrics),
            'aggregated_metrics': {
                'precision': agg_precision,
                'recall': agg_recall,
                'f1_score': agg_f1,
                'total_true_positives': total_tp,
                'total_false_positives': total_fp,
                'total_false_negatives': total_fn,
                'average_latency_ms': avg_latency,
                'session_count': len(all_metrics)
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating project metrics: {e}")
        return {
            'project_id': project_id,
            'error': str(e)
        }