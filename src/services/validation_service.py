"""
Validation Service for VRU Detection System
Handles test session validation, latency analysis, and pass/fail determination
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from src.core.config import settings, ValidationConfig
from src.core.exceptions import VRUDetectionException
from src.models.database import (
    TestSession, DetectionEvent, SignalEvent, GroundTruthObject,
    ValidationResults, TestSessionStatus, ValidationResult as DBValidationResult
)
from src.services.detection_engine import Detection, BoundingBox

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics container"""
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    
    @property
    def specificity(self) -> float:
        """Calculate specificity (true negative rate)"""
        if self.true_negatives + self.false_positives == 0:
            return 0.0
        return self.true_negatives / (self.true_negatives + self.false_positives)
    
    @property
    def false_positive_rate(self) -> float:
        """Calculate false positive rate"""
        return 1.0 - self.specificity


@dataclass
class LatencyMetrics:
    """Latency analysis metrics"""
    mean_latency_ms: float
    median_latency_ms: float
    std_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    within_tolerance_percentage: float
    latency_violations: int


@dataclass
class TemporalAlignment:
    """Temporal alignment between detection and signal events"""
    detection_event: DetectionEvent
    signal_event: Optional[SignalEvent]
    time_difference_ms: float
    within_tolerance: bool


@dataclass
class ValidationSummary:
    """Complete validation summary"""
    test_session_id: uuid.UUID
    performance_metrics: PerformanceMetrics
    latency_metrics: LatencyMetrics
    temporal_alignments: List[TemporalAlignment]
    test_verdict: str  # "PASS", "FAIL", "INCONCLUSIVE"
    verdict_reasons: List[str]
    detailed_analysis: Dict[str, Any]


class ValidationService:
    """Main validation service for test sessions"""
    
    def __init__(self):
        self.tolerance_calculator = ToleranceCalculator()
        self.metrics_calculator = MetricsCalculator()
        self.latency_analyzer = LatencyAnalyzer()
        self.pass_fail_determiner = PassFailDeterminer()
    
    async def validate_test_session(
        self,
        test_session_id: uuid.UUID,
        session: AsyncSession
    ) -> ValidationSummary:
        """
        Perform complete validation of a test session
        
        Args:
            test_session_id: Test session to validate
            session: Database session
            
        Returns:
            Complete validation summary
        """
        try:
            logger.info(f"Starting validation for test session: {test_session_id}")
            
            # Load test session data
            test_session = await self._load_test_session(test_session_id, session)
            if not test_session:
                raise VRUDetectionException(
                    "TEST_SESSION_NOT_FOUND",
                    f"Test session {test_session_id} not found"
                )
            
            # Load all related data
            detection_events = await self._load_detection_events(test_session_id, session)
            signal_events = await self._load_signal_events(test_session_id, session)
            ground_truth = await self._load_ground_truth(test_session.video_id, session)
            
            logger.info(f"Loaded {len(detection_events)} detections, {len(signal_events)} signals, {len(ground_truth)} ground truth objects")
            
            # Perform temporal alignment
            temporal_alignments = await self._align_temporal_events(
                detection_events, signal_events, test_session.tolerance_ms
            )
            
            # Match detections with ground truth
            ground_truth_matches = await self._match_ground_truth(
                detection_events, ground_truth, test_session.tolerance_ms
            )
            
            # Calculate performance metrics
            performance_metrics = await self.metrics_calculator.calculate_performance_metrics(
                ground_truth_matches, len(ground_truth)
            )
            
            # Analyze latency
            latency_metrics = await self.latency_analyzer.analyze_latency(
                temporal_alignments, test_session.tolerance_ms
            )
            
            # Determine test verdict
            test_verdict, verdict_reasons = await self.pass_fail_determiner.determine_verdict(
                performance_metrics, latency_metrics, test_session
            )
            
            # Generate detailed analysis
            detailed_analysis = await self._generate_detailed_analysis(
                detection_events, ground_truth_matches, temporal_alignments
            )
            
            # Create validation summary
            validation_summary = ValidationSummary(
                test_session_id=test_session_id,
                performance_metrics=performance_metrics,
                latency_metrics=latency_metrics,
                temporal_alignments=temporal_alignments,
                test_verdict=test_verdict,
                verdict_reasons=verdict_reasons,
                detailed_analysis=detailed_analysis
            )
            
            # Save validation results to database
            await self._save_validation_results(validation_summary, session)
            
            logger.info(f"Validation completed for test session: {test_session_id}, verdict: {test_verdict}")
            
            return validation_summary
            
        except Exception as e:
            logger.error(f"Validation failed for test session {test_session_id}: {e}")
            raise VRUDetectionException(
                "VALIDATION_FAILED",
                f"Failed to validate test session: {test_session_id}",
                details={"error": str(e)}
            )
    
    async def _load_test_session(self, test_session_id: uuid.UUID, session: AsyncSession) -> Optional[TestSession]:
        """Load test session with related data"""
        query = (
            select(TestSession)
            .options(
                selectinload(TestSession.project),
                selectinload(TestSession.video)
            )
            .where(TestSession.id == test_session_id)
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def _load_detection_events(self, test_session_id: uuid.UUID, session: AsyncSession) -> List[DetectionEvent]:
        """Load detection events for test session"""
        query = (
            select(DetectionEvent)
            .where(DetectionEvent.test_session_id == test_session_id)
            .order_by(DetectionEvent.timestamp)
        )
        result = await session.execute(query)
        return result.scalars().all()
    
    async def _load_signal_events(self, test_session_id: uuid.UUID, session: AsyncSession) -> List[SignalEvent]:
        """Load signal events for test session"""
        query = (
            select(SignalEvent)
            .where(SignalEvent.test_session_id == test_session_id)
            .order_by(SignalEvent.timestamp)
        )
        result = await session.execute(query)
        return result.scalars().all()
    
    async def _load_ground_truth(self, video_id: uuid.UUID, session: AsyncSession) -> List[GroundTruthObject]:
        """Load ground truth objects for video"""
        query = (
            select(GroundTruthObject)
            .where(GroundTruthObject.video_id == video_id)
            .order_by(GroundTruthObject.timestamp)
        )
        result = await session.execute(query)
        return result.scalars().all()
    
    async def _align_temporal_events(
        self,
        detection_events: List[DetectionEvent],
        signal_events: List[SignalEvent],
        tolerance_ms: int
    ) -> List[TemporalAlignment]:
        """Align detection events with signal events based on timing"""
        alignments = []
        tolerance_seconds = tolerance_ms / 1000.0
        
        for detection in detection_events:
            best_signal = None
            min_time_diff = float('inf')
            
            # Find closest signal event
            for signal in signal_events:
                time_diff = abs(detection.timestamp - signal.timestamp)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    best_signal = signal
            
            time_diff_ms = min_time_diff * 1000
            within_tolerance = time_diff_ms <= tolerance_ms
            
            alignment = TemporalAlignment(
                detection_event=detection,
                signal_event=best_signal,
                time_difference_ms=time_diff_ms,
                within_tolerance=within_tolerance
            )
            
            alignments.append(alignment)
        
        return alignments
    
    async def _match_ground_truth(
        self,
        detection_events: List[DetectionEvent],
        ground_truth: List[GroundTruthObject],
        tolerance_ms: int
    ) -> List[Tuple[DetectionEvent, Optional[GroundTruthObject], str]]:
        """Match detection events with ground truth objects"""
        matches = []
        tolerance_seconds = tolerance_ms / 1000.0
        matched_gt_ids = set()
        
        for detection in detection_events:
            best_match = None
            best_score = 0.0
            match_type = "FP"  # Default to False Positive
            
            for gt in ground_truth:
                if gt.id in matched_gt_ids:
                    continue
                
                # Check temporal overlap
                time_diff = abs(detection.timestamp - gt.timestamp)
                if time_diff > tolerance_seconds:
                    continue
                
                # Check class match
                if detection.class_label != gt.class_label:
                    continue
                
                # Check spatial overlap (IoU)
                if detection.bounding_box and gt.bounding_box:
                    iou = self._calculate_iou(detection.bounding_box, gt.bounding_box)
                    
                    # Consider it a match if IoU > 0.5
                    if iou > 0.5:
                        # Calculate overall match score
                        temporal_score = max(0, 1.0 - (time_diff / tolerance_seconds))
                        spatial_score = iou
                        overall_score = (temporal_score + spatial_score) / 2
                        
                        if overall_score > best_score:
                            best_score = overall_score
                            best_match = gt
                            match_type = "TP"  # True Positive
            
            if best_match:
                matched_gt_ids.add(best_match.id)
            
            matches.append((detection, best_match, match_type))
        
        # Add False Negatives (unmatched ground truth)
        for gt in ground_truth:
            if gt.id not in matched_gt_ids:
                matches.append((None, gt, "FN"))  # False Negative
        
        return matches
    
    def _calculate_iou(self, bbox1: Dict, bbox2: Dict) -> float:
        """Calculate Intersection over Union of two bounding boxes"""
        try:
            # Extract coordinates
            x1_1, y1_1 = bbox1['x'], bbox1['y']
            x2_1, y2_1 = x1_1 + bbox1['width'], y1_1 + bbox1['height']
            
            x1_2, y1_2 = bbox2['x'], bbox2['y'] 
            x2_2, y2_2 = x1_2 + bbox2['width'], y1_2 + bbox2['height']
            
            # Calculate intersection
            x1_i = max(x1_1, x1_2)
            y1_i = max(y1_1, y1_2)
            x2_i = min(x2_1, x2_2)
            y2_i = min(y2_1, y2_2)
            
            if x2_i <= x1_i or y2_i <= y1_i:
                return 0.0
            
            intersection = (x2_i - x1_i) * (y2_i - y1_i)
            
            # Calculate areas
            area1 = bbox1['width'] * bbox1['height']
            area2 = bbox2['width'] * bbox2['height']
            
            # Calculate union
            union = area1 + area2 - intersection
            
            return intersection / union if union > 0 else 0.0
            
        except (KeyError, TypeError, ZeroDivisionError):
            return 0.0
    
    async def _generate_detailed_analysis(
        self,
        detection_events: List[DetectionEvent],
        ground_truth_matches: List[Tuple],
        temporal_alignments: List[TemporalAlignment]
    ) -> Dict[str, Any]:
        """Generate detailed analysis of validation results"""
        
        # Analyze detection distribution by class
        class_distribution = {}
        confidence_stats = {}
        
        for detection in detection_events:
            class_label = detection.class_label
            
            if class_label not in class_distribution:
                class_distribution[class_label] = 0
                confidence_stats[class_label] = []
            
            class_distribution[class_label] += 1
            if detection.confidence:
                confidence_stats[class_label].append(detection.confidence)
        
        # Calculate confidence statistics
        for class_label in confidence_stats:
            confidences = confidence_stats[class_label]
            if confidences:
                confidence_stats[class_label] = {
                    "mean": sum(confidences) / len(confidences),
                    "min": min(confidences),
                    "max": max(confidences),
                    "count": len(confidences)
                }
            else:
                confidence_stats[class_label] = {
                    "mean": 0, "min": 0, "max": 0, "count": 0
                }
        
        # Analyze temporal patterns
        timing_violations = [
            alignment.time_difference_ms
            for alignment in temporal_alignments
            if not alignment.within_tolerance
        ]
        
        return {
            "class_distribution": class_distribution,
            "confidence_statistics": confidence_stats,
            "timing_violations": {
                "count": len(timing_violations),
                "violations_ms": timing_violations
            },
            "detection_density": len(detection_events) / max(1, len(temporal_alignments)),
            "alignment_success_rate": sum(1 for a in temporal_alignments if a.within_tolerance) / max(1, len(temporal_alignments))
        }
    
    async def _save_validation_results(self, summary: ValidationSummary, session: AsyncSession) -> None:
        """Save validation results to database"""
        try:
            validation_result = ValidationResults(
                test_session_id=summary.test_session_id,
                true_positives=summary.performance_metrics.true_positives,
                false_positives=summary.performance_metrics.false_positives,
                false_negatives=summary.performance_metrics.false_negatives,
                precision=summary.performance_metrics.precision,
                recall=summary.performance_metrics.recall,
                f1_score=summary.performance_metrics.f1_score,
                accuracy=summary.performance_metrics.accuracy,
                avg_latency_ms=summary.latency_metrics.mean_latency_ms,
                detailed_metrics={
                    "latency_metrics": {
                        "median_ms": summary.latency_metrics.median_latency_ms,
                        "std_ms": summary.latency_metrics.std_latency_ms,
                        "p95_ms": summary.latency_metrics.p95_latency_ms,
                        "p99_ms": summary.latency_metrics.p99_latency_ms,
                        "within_tolerance_percentage": summary.latency_metrics.within_tolerance_percentage
                    },
                    "test_verdict": summary.test_verdict,
                    "verdict_reasons": summary.verdict_reasons,
                    "detailed_analysis": summary.detailed_analysis
                }
            )
            
            session.add(validation_result)
            await session.commit()
            
        except Exception as e:
            logger.error(f"Failed to save validation results: {e}")
            raise


class ToleranceCalculator:
    """Calculate timing tolerances and thresholds"""
    
    def calculate_adaptive_tolerance(self, signal_events: List[SignalEvent]) -> int:
        """Calculate adaptive tolerance based on signal timing variance"""
        if not signal_events:
            return ValidationConfig.TIMING_TOLERANCE_MS
        
        # Calculate inter-signal timing variance
        intervals = []
        for i in range(1, len(signal_events)):
            interval = signal_events[i].timestamp - signal_events[i-1].timestamp
            intervals.append(interval * 1000)  # Convert to ms
        
        if not intervals:
            return ValidationConfig.TIMING_TOLERANCE_MS
        
        # Use standard deviation as basis for adaptive tolerance
        import statistics
        mean_interval = statistics.mean(intervals)
        std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
        
        # Adaptive tolerance: base + 2 * std deviation
        adaptive_tolerance = ValidationConfig.TIMING_TOLERANCE_MS + (2 * std_interval)
        
        # Clamp to reasonable range
        return min(max(adaptive_tolerance, 50), 500)


class MetricsCalculator:
    """Calculate performance metrics"""
    
    async def calculate_performance_metrics(
        self,
        ground_truth_matches: List[Tuple],
        total_ground_truth: int
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics"""
        
        tp = fp = fn = tn = 0
        
        for detection, ground_truth, match_type in ground_truth_matches:
            if match_type == "TP":
                tp += 1
            elif match_type == "FP":
                fp += 1
            elif match_type == "FN":
                fn += 1
        
        # True negatives are harder to calculate in object detection
        # For now, we'll estimate based on negative space
        tn = max(0, (total_ground_truth * 2) - (tp + fp + fn))
        
        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0.0
        
        return PerformanceMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy
        )


class LatencyAnalyzer:
    """Analyze timing and latency metrics"""
    
    async def analyze_latency(
        self,
        temporal_alignments: List[TemporalAlignment],
        tolerance_ms: int
    ) -> LatencyMetrics:
        """Analyze latency patterns and statistics"""
        
        if not temporal_alignments:
            return LatencyMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        latencies = [alignment.time_difference_ms for alignment in temporal_alignments]
        within_tolerance_count = sum(1 for alignment in temporal_alignments if alignment.within_tolerance)
        
        # Calculate statistics
        import statistics
        
        mean_latency = statistics.mean(latencies)
        median_latency = statistics.median(latencies)
        std_latency = statistics.stdev(latencies) if len(latencies) > 1 else 0
        min_latency = min(latencies)
        max_latency = max(latencies)
        
        # Calculate percentiles
        sorted_latencies = sorted(latencies)
        p95_index = int(0.95 * len(sorted_latencies))
        p99_index = int(0.99 * len(sorted_latencies))
        
        p95_latency = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]
        p99_latency = sorted_latencies[min(p99_index, len(sorted_latencies) - 1)]
        
        within_tolerance_percentage = (within_tolerance_count / len(temporal_alignments)) * 100
        latency_violations = len(temporal_alignments) - within_tolerance_count
        
        return LatencyMetrics(
            mean_latency_ms=mean_latency,
            median_latency_ms=median_latency,
            std_latency_ms=std_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            within_tolerance_percentage=within_tolerance_percentage,
            latency_violations=latency_violations
        )


class PassFailDeterminer:
    """Determine test pass/fail status based on criteria"""
    
    async def determine_verdict(
        self,
        performance_metrics: PerformanceMetrics,
        latency_metrics: LatencyMetrics,
        test_session: TestSession
    ) -> Tuple[str, List[str]]:
        """Determine test verdict and reasons"""
        
        verdict_reasons = []
        criteria_met = 0
        total_criteria = 0
        
        # Check precision criterion
        total_criteria += 1
        if performance_metrics.precision >= ValidationConfig.PASS_CRITERIA["precision"]:
            criteria_met += 1
        else:
            verdict_reasons.append(
                f"Precision {performance_metrics.precision:.3f} below threshold {ValidationConfig.PASS_CRITERIA['precision']}"
            )
        
        # Check recall criterion
        total_criteria += 1
        if performance_metrics.recall >= ValidationConfig.PASS_CRITERIA["recall"]:
            criteria_met += 1
        else:
            verdict_reasons.append(
                f"Recall {performance_metrics.recall:.3f} below threshold {ValidationConfig.PASS_CRITERIA['recall']}"
            )
        
        # Check F1 score criterion
        total_criteria += 1
        if performance_metrics.f1_score >= ValidationConfig.PASS_CRITERIA["f1_score"]:
            criteria_met += 1
        else:
            verdict_reasons.append(
                f"F1 score {performance_metrics.f1_score:.3f} below threshold {ValidationConfig.PASS_CRITERIA['f1_score']}"
            )
        
        # Check temporal accuracy criterion
        total_criteria += 1
        temporal_accuracy = latency_metrics.within_tolerance_percentage / 100
        if temporal_accuracy >= ValidationConfig.PASS_CRITERIA["temporal_accuracy"]:
            criteria_met += 1
        else:
            verdict_reasons.append(
                f"Temporal accuracy {temporal_accuracy:.3f} below threshold {ValidationConfig.PASS_CRITERIA['temporal_accuracy']}"
            )
        
        # Check average latency criterion
        total_criteria += 1
        if latency_metrics.mean_latency_ms <= ValidationConfig.PASS_CRITERIA["avg_latency_ms"]:
            criteria_met += 1
        else:
            verdict_reasons.append(
                f"Average latency {latency_metrics.mean_latency_ms:.1f}ms above threshold {ValidationConfig.PASS_CRITERIA['avg_latency_ms']}ms"
            )
        
        # Determine verdict
        if criteria_met == total_criteria:
            verdict = "PASS"
            verdict_reasons = ["All validation criteria met"]
        elif criteria_met >= total_criteria * 0.8:  # 80% of criteria met
            verdict = "PASS"
            verdict_reasons.insert(0, "Majority of validation criteria met")
        elif criteria_met >= total_criteria * 0.5:  # 50% of criteria met
            verdict = "INCONCLUSIVE"
            verdict_reasons.insert(0, "Mixed validation results")
        else:
            verdict = "FAIL"
            verdict_reasons.insert(0, "Insufficient validation criteria met")
        
        return verdict, verdict_reasons