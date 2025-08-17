from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal
from models import DetectionEvent, TestSession, GroundTruthObject, Video
from services.project_management_service import TestResults, PassFailCriteria, TestVerdict
import statistics
import json

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetrics:
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float

@dataclass
class TemporalMetrics:
    mean_timing_error_ms: float
    std_timing_error_ms: float
    max_timing_error_ms: float
    min_timing_error_ms: float
    within_tolerance_percentage: float
    median_timing_error_ms: float

@dataclass
class StatisticalResults:
    confidence_intervals: Dict
    distribution_stats: Dict
    outlier_analysis: Dict
    trend_analysis: Dict

@dataclass
class ValidationResult:
    test_session_id: str
    performance_metrics: PerformanceMetrics
    temporal_metrics: TemporalMetrics
    statistical_results: StatisticalResults
    test_verdict: TestVerdict
    overall_score: float
    detailed_analysis: Dict

class ToleranceCalculator:
    """Calculate and manage timing tolerance for detection validation"""
    
    def __init__(self, base_tolerance_ms: int = 100):
        self.base_tolerance_ms = base_tolerance_ms
    
    def calculate_adaptive_tolerance(self, historical_latencies: List[float]) -> float:
        """Calculate adaptive tolerance based on historical performance"""
        if not historical_latencies:
            return self.base_tolerance_ms
        
        # Calculate statistical measures
        mean_latency = np.mean(historical_latencies)
        std_latency = np.std(historical_latencies)
        
        # Adaptive tolerance: mean + 2 * standard deviation
        adaptive_tolerance = mean_latency + (2 * std_latency)
        
        # Ensure it's within reasonable bounds
        min_tolerance = 50  # 50ms minimum
        max_tolerance = 500  # 500ms maximum
        
        return max(min_tolerance, min(adaptive_tolerance, max_tolerance))
    
    def get_tolerance_for_session(self, test_session_id: str) -> float:
        """Get appropriate tolerance for a specific test session"""
        db = SessionLocal()
        try:
            # Get historical latencies for similar test scenarios
            test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
            if not test_session:
                return self.base_tolerance_ms
            
            # Find similar test sessions (same project)
            similar_sessions = db.query(TestSession).filter(
                TestSession.project_id == test_session.project_id,
                TestSession.id != test_session_id,
                TestSession.status == "completed"
            ).all()
            
            historical_latencies = []
            for session in similar_sessions:
                # Calculate average latency for this session
                avg_latency = self._calculate_session_average_latency(session.id, db)
                if avg_latency is not None:
                    historical_latencies.append(avg_latency)
            
            return self.calculate_adaptive_tolerance(historical_latencies)
            
        except Exception as e:
            logger.error(f"Error calculating tolerance: {str(e)}")
            return self.base_tolerance_ms
        finally:
            db.close()
    
    def _calculate_session_average_latency(self, session_id: str, db: Session) -> Optional[float]:
        """Calculate average latency for a completed session"""
        try:
            # This would require actual timing data from detection events
            # For now, return a mock value
            return 75.0  # Mock average latency
        except Exception as e:
            logger.error(f"Error calculating session latency: {str(e)}")
            return None

class MetricsEngine:
    """Advanced metrics calculation engine"""
    
    def __init__(self):
        self.tolerance_calculator = ToleranceCalculator()
    
    def calculate_comprehensive_metrics(self, test_session_id: str) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics for a test session"""
        db = SessionLocal()
        try:
            # Get test session and related data
            test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
            if not test_session:
                raise ValueError(f"Test session {test_session_id} not found")
            
            # Get detection events
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == test_session_id
            ).all()
            
            # Get ground truth objects for the video
            ground_truth_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == test_session.video_id
            ).all()
            
            # Calculate metrics using tolerance
            tolerance_ms = test_session.tolerance_ms or self.tolerance_calculator.get_tolerance_for_session(test_session_id)
            
            return self._calculate_detection_metrics(detection_events, ground_truth_objects, tolerance_ms)
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {str(e)}")
            raise
        finally:
            db.close()
    
    def _calculate_detection_metrics(self, detection_events: List[DetectionEvent], 
                                   ground_truth_objects: List[GroundTruthObject], 
                                   tolerance_ms: float) -> PerformanceMetrics:
        """Calculate detection performance metrics"""
        tolerance_seconds = tolerance_ms / 1000.0
        
        # Track matches
        true_positives = 0
        false_positives = 0
        matched_gt_objects = set()
        
        # Find true positives and false positives
        for detection in detection_events:
            is_match = False
            
            for i, gt_obj in enumerate(ground_truth_objects):
                if i in matched_gt_objects:
                    continue
                
                # Check temporal match
                time_diff = abs(detection.timestamp - gt_obj.timestamp)
                
                # Check class match
                class_match = detection.class_label == gt_obj.class_label
                
                if time_diff <= tolerance_seconds and class_match:
                    true_positives += 1
                    matched_gt_objects.add(i)
                    is_match = True
                    break
            
            if not is_match:
                false_positives += 1
        
        # False negatives are unmatched ground truth objects
        false_negatives = len(ground_truth_objects) - len(matched_gt_objects)
        
        # Calculate standard metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = true_positives / len(ground_truth_objects) if len(ground_truth_objects) > 0 else 0.0
        
        return PerformanceMetrics(
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy
        )
    
    def calculate_temporal_metrics(self, detection_events: List[DetectionEvent], 
                                 ground_truth_objects: List[GroundTruthObject],
                                 tolerance_ms: float) -> TemporalMetrics:
        """Calculate temporal accuracy metrics"""
        tolerance_seconds = tolerance_ms / 1000.0
        timing_errors = []
        within_tolerance = 0
        
        for detection in detection_events:
            closest_gt = self._find_closest_ground_truth(detection, ground_truth_objects)
            if closest_gt:
                time_diff_ms = abs(detection.timestamp - closest_gt.timestamp) * 1000
                timing_errors.append(time_diff_ms)
                
                if time_diff_ms <= tolerance_ms:
                    within_tolerance += 1
        
        if not timing_errors:
            return TemporalMetrics(
                mean_timing_error_ms=0.0,
                std_timing_error_ms=0.0,
                max_timing_error_ms=0.0,
                min_timing_error_ms=0.0,
                within_tolerance_percentage=0.0,
                median_timing_error_ms=0.0
            )
        
        return TemporalMetrics(
            mean_timing_error_ms=np.mean(timing_errors),
            std_timing_error_ms=np.std(timing_errors),
            max_timing_error_ms=np.max(timing_errors),
            min_timing_error_ms=np.min(timing_errors),
            within_tolerance_percentage=(within_tolerance / len(detection_events) * 100) if detection_events else 0,
            median_timing_error_ms=np.median(timing_errors)
        )
    
    def _find_closest_ground_truth(self, detection: DetectionEvent, 
                                 ground_truth_objects: List[GroundTruthObject]) -> Optional[GroundTruthObject]:
        """Find the closest ground truth object to a detection"""
        closest_gt = None
        min_time_diff = float('inf')
        
        for gt_obj in ground_truth_objects:
            if detection.class_label == gt_obj.class_label:
                time_diff = abs(detection.timestamp - gt_obj.timestamp)
                if time_diff < min_time_diff:
                    min_time_diff = time_diff
                    closest_gt = gt_obj
        
        return closest_gt

class StatisticalAnalyzer:
    """Advanced statistical analysis for detection performance"""
    
    def __init__(self):
        pass
    
    def analyze_performance_distribution(self, detection_events: List[DetectionEvent]) -> StatisticalResults:
        """Analyze statistical distribution of detection performance"""
        if not detection_events:
            return self._empty_statistical_results()
        
        # Extract confidence values
        confidences = [event.confidence for event in detection_events if event.confidence is not None]
        timestamps = [event.timestamp for event in detection_events]
        
        # Confidence distribution analysis
        confidence_stats = self._analyze_distribution(confidences) if confidences else {}
        
        # Temporal distribution analysis
        temporal_stats = self._analyze_temporal_distribution(timestamps)
        
        # Outlier analysis
        outlier_analysis = self._detect_outliers(confidences) if confidences else {}
        
        # Trend analysis
        trend_analysis = self._analyze_trends(timestamps, confidences) if confidences else {}
        
        # Confidence intervals
        confidence_intervals = self._calculate_confidence_intervals(confidences) if confidences else {}
        
        return StatisticalResults(
            confidence_intervals=confidence_intervals,
            distribution_stats={
                "confidence": confidence_stats,
                "temporal": temporal_stats
            },
            outlier_analysis=outlier_analysis,
            trend_analysis=trend_analysis
        )
    
    def _analyze_distribution(self, values: List[float]) -> Dict:
        """Analyze statistical distribution of values"""
        if not values:
            return {}
        
        return {
            "mean": np.mean(values),
            "median": np.median(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "quartiles": {
                "q1": np.percentile(values, 25),
                "q2": np.percentile(values, 50),
                "q3": np.percentile(values, 75)
            },
            "skewness": self._calculate_skewness(values),
            "kurtosis": self._calculate_kurtosis(values)
        }
    
    def _analyze_temporal_distribution(self, timestamps: List[float]) -> Dict:
        """Analyze temporal distribution of detections"""
        if len(timestamps) < 2:
            return {}
        
        # Calculate intervals between detections
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        
        return {
            "detection_rate": len(timestamps) / (max(timestamps) - min(timestamps)) if timestamps else 0,
            "interval_stats": self._analyze_distribution(intervals),
            "temporal_clustering": self._detect_temporal_clusters(timestamps)
        }
    
    def _detect_outliers(self, values: List[float]) -> Dict:
        """Detect statistical outliers using IQR method"""
        if len(values) < 4:
            return {"outliers": [], "outlier_count": 0}
        
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outliers = [v for v in values if v < lower_bound or v > upper_bound]
        
        return {
            "outliers": outliers,
            "outlier_count": len(outliers),
            "outlier_percentage": len(outliers) / len(values) * 100,
            "bounds": {"lower": lower_bound, "upper": upper_bound}
        }
    
    def _analyze_trends(self, timestamps: List[float], values: List[float]) -> Dict:
        """Analyze trends in detection performance over time"""
        if len(timestamps) != len(values) or len(timestamps) < 3:
            return {}
        
        # Simple linear regression to detect trends
        x = np.array(timestamps)
        y = np.array(values)
        
        # Normalize timestamps to start from 0
        x_norm = x - x.min()
        
        # Calculate correlation
        correlation = np.corrcoef(x_norm, y)[0, 1] if len(x_norm) > 1 else 0
        
        # Calculate slope (trend direction)
        if len(x_norm) > 1:
            slope = np.polyfit(x_norm, y, 1)[0]
        else:
            slope = 0
        
        return {
            "correlation": correlation,
            "trend_direction": "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable",
            "slope": slope,
            "strength": abs(correlation)
        }
    
    def _calculate_confidence_intervals(self, values: List[float], confidence_level: float = 0.95) -> Dict:
        """Calculate confidence intervals for metrics"""
        if len(values) < 2:
            return {}
        
        mean = np.mean(values)
        std_error = np.std(values) / np.sqrt(len(values))
        
        # Using t-distribution for small samples
        from scipy import stats
        t_value = stats.t.ppf((1 + confidence_level) / 2, len(values) - 1)
        
        margin_error = t_value * std_error
        
        return {
            "mean": mean,
            "lower_bound": mean - margin_error,
            "upper_bound": mean + margin_error,
            "confidence_level": confidence_level,
            "margin_of_error": margin_error
        }
    
    def _calculate_skewness(self, values: List[float]) -> float:
        """Calculate skewness of distribution"""
        if len(values) < 3:
            return 0.0
        
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return 0.0
        
        return np.mean([(x - mean) ** 3 for x in values]) / (std ** 3)
    
    def _calculate_kurtosis(self, values: List[float]) -> float:
        """Calculate kurtosis of distribution"""
        if len(values) < 4:
            return 0.0
        
        mean = np.mean(values)
        std = np.std(values)
        
        if std == 0:
            return 0.0
        
        return np.mean([(x - mean) ** 4 for x in values]) / (std ** 4) - 3
    
    def _detect_temporal_clusters(self, timestamps: List[float]) -> Dict:
        """Detect temporal clustering of detections"""
        if len(timestamps) < 3:
            return {"clusters": 0, "cluster_density": 0}
        
        # Simple clustering based on detection density
        sorted_timestamps = sorted(timestamps)
        intervals = [sorted_timestamps[i+1] - sorted_timestamps[i] for i in range(len(sorted_timestamps)-1)]
        
        # Threshold for cluster separation (mean + std)
        threshold = np.mean(intervals) + np.std(intervals)
        
        clusters = 1
        for interval in intervals:
            if interval > threshold:
                clusters += 1
        
        return {
            "clusters": clusters,
            "cluster_density": len(timestamps) / clusters,
            "separation_threshold": threshold
        }
    
    def _empty_statistical_results(self) -> StatisticalResults:
        """Return empty statistical results"""
        return StatisticalResults(
            confidence_intervals={},
            distribution_stats={},
            outlier_analysis={},
            trend_analysis={}
        )

class ValidationWorkflow:
    """Complete validation workflow orchestrator"""
    
    def __init__(self):
        self.tolerance_calculator = ToleranceCalculator()
        self.metrics_engine = MetricsEngine()
        self.statistical_analyzer = StatisticalAnalyzer()
    
    async def validate_test_session(self, test_session_id: str, 
                                  custom_criteria: Optional[PassFailCriteria] = None) -> ValidationResult:
        """Complete validation workflow for a test session"""
        db = SessionLocal()
        try:
            # Stage 1: Data Collection
            test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
            if not test_session:
                raise ValueError(f"Test session {test_session_id} not found")
            
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == test_session_id
            ).all()
            
            ground_truth = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == test_session.video_id
            ).all()
            
            # Stage 2: Performance Metrics Calculation
            performance_metrics = self.metrics_engine.calculate_comprehensive_metrics(test_session_id)
            
            # Stage 3: Temporal Analysis
            tolerance_ms = test_session.tolerance_ms or self.tolerance_calculator.get_tolerance_for_session(test_session_id)
            temporal_metrics = self.metrics_engine.calculate_temporal_metrics(
                detection_events, ground_truth, tolerance_ms
            )
            
            # Stage 4: Statistical Analysis
            statistical_results = self.statistical_analyzer.analyze_performance_distribution(detection_events)
            
            # Stage 5: Create test results for evaluation
            test_results = TestResults(
                precision=performance_metrics.precision,
                recall=performance_metrics.recall,
                f1_score=performance_metrics.f1_score,
                accuracy=performance_metrics.accuracy,
                average_latency_ms=temporal_metrics.mean_timing_error_ms,
                false_positive_rate=performance_metrics.false_positives / len(detection_events) if detection_events else 0,
                average_confidence=np.mean([e.confidence for e in detection_events if e.confidence]) if detection_events else 0,
                total_detections=len(detection_events),
                true_positives=performance_metrics.true_positives,
                false_positives=performance_metrics.false_positives,
                false_negatives=performance_metrics.false_negatives
            )
            
            # Stage 6: Pass/Fail Determination
            from services.project_management_service import PassFailCriteriaEngine
            criteria_engine = PassFailCriteriaEngine()
            
            test_verdict = criteria_engine.evaluate(test_results, custom_criteria)
            overall_score = criteria_engine._calculate_overall_score(test_results, custom_criteria or criteria_engine.default_criteria)
            
            # Stage 7: Detailed Analysis
            detailed_analysis = self._generate_detailed_analysis(
                performance_metrics, temporal_metrics, statistical_results, test_results
            )
            
            return ValidationResult(
                test_session_id=test_session_id,
                performance_metrics=performance_metrics,
                temporal_metrics=temporal_metrics,
                statistical_results=statistical_results,
                test_verdict=test_verdict,
                overall_score=overall_score,
                detailed_analysis=detailed_analysis
            )
            
        except Exception as e:
            logger.error(f"Error in validation workflow: {str(e)}")
            raise
        finally:
            db.close()
    
    def _generate_detailed_analysis(self, performance_metrics: PerformanceMetrics,
                                  temporal_metrics: TemporalMetrics,
                                  statistical_results: StatisticalResults,
                                  test_results: TestResults) -> Dict:
        """Generate detailed analysis report"""
        
        # Performance analysis
        performance_analysis = {
            "detection_accuracy": {
                "score": performance_metrics.accuracy,
                "rating": self._rate_performance(performance_metrics.accuracy),
                "insights": self._generate_accuracy_insights(performance_metrics)
            },
            "precision_recall": {
                "precision": performance_metrics.precision,
                "recall": performance_metrics.recall,
                "f1_score": performance_metrics.f1_score,
                "balance": "balanced" if abs(performance_metrics.precision - performance_metrics.recall) < 0.1 else "imbalanced",
                "insights": self._generate_precision_recall_insights(performance_metrics)
            }
        }
        
        # Temporal analysis
        temporal_analysis = {
            "timing_performance": {
                "mean_latency": temporal_metrics.mean_timing_error_ms,
                "consistency": "high" if temporal_metrics.std_timing_error_ms < 20 else "medium" if temporal_metrics.std_timing_error_ms < 50 else "low",
                "reliability": temporal_metrics.within_tolerance_percentage,
                "insights": self._generate_temporal_insights(temporal_metrics)
            }
        }
        
        # Quality assessment
        quality_assessment = {
            "overall_quality": self._assess_overall_quality(test_results),
            "strengths": self._identify_strengths(performance_metrics, temporal_metrics),
            "weaknesses": self._identify_weaknesses(performance_metrics, temporal_metrics),
            "recommendations": self._generate_recommendations(performance_metrics, temporal_metrics, statistical_results)
        }
        
        return {
            "performance_analysis": performance_analysis,
            "temporal_analysis": temporal_analysis,
            "quality_assessment": quality_assessment,
            "statistical_insights": self._extract_statistical_insights(statistical_results),
            "generated_at": datetime.utcnow().isoformat()
        }
    
    def _rate_performance(self, score: float) -> str:
        """Rate performance based on score"""
        if score >= 0.95:
            return "excellent"
        elif score >= 0.90:
            return "very_good"
        elif score >= 0.80:
            return "good"
        elif score >= 0.70:
            return "fair"
        else:
            return "poor"
    
    def _generate_accuracy_insights(self, metrics: PerformanceMetrics) -> List[str]:
        """Generate insights about detection accuracy"""
        insights = []
        
        if metrics.accuracy >= 0.95:
            insights.append("Excellent detection accuracy achieved")
        elif metrics.accuracy < 0.80:
            insights.append("Detection accuracy below target - consider model tuning")
        
        if metrics.false_positives > metrics.true_positives:
            insights.append("High false positive rate - review detection thresholds")
        
        if metrics.false_negatives > metrics.true_positives * 0.2:
            insights.append("Significant missed detections - check model sensitivity")
        
        return insights
    
    def _generate_precision_recall_insights(self, metrics: PerformanceMetrics) -> List[str]:
        """Generate insights about precision and recall balance"""
        insights = []
        
        if metrics.precision > 0.95 and metrics.recall < 0.80:
            insights.append("High precision but low recall - model is conservative")
        elif metrics.recall > 0.95 and metrics.precision < 0.80:
            insights.append("High recall but low precision - model is aggressive")
        elif metrics.precision > 0.90 and metrics.recall > 0.90:
            insights.append("Excellent precision-recall balance")
        
        return insights
    
    def _generate_temporal_insights(self, metrics: TemporalMetrics) -> List[str]:
        """Generate insights about temporal performance"""
        insights = []
        
        if metrics.mean_timing_error_ms < 50:
            insights.append("Excellent timing performance")
        elif metrics.mean_timing_error_ms > 100:
            insights.append("Timing performance needs improvement")
        
        if metrics.std_timing_error_ms > 50:
            insights.append("High timing variability - investigate consistency issues")
        
        if metrics.within_tolerance_percentage < 80:
            insights.append("Many detections outside tolerance - review timing requirements")
        
        return insights
    
    def _assess_overall_quality(self, results: TestResults) -> str:
        """Assess overall test quality"""
        score = (results.precision + results.recall + results.f1_score + results.accuracy) / 4
        
        if score >= 0.90:
            return "high"
        elif score >= 0.80:
            return "medium"
        else:
            return "low"
    
    def _identify_strengths(self, perf_metrics: PerformanceMetrics, temp_metrics: TemporalMetrics) -> List[str]:
        """Identify test performance strengths"""
        strengths = []
        
        if perf_metrics.precision >= 0.90:
            strengths.append("High detection precision")
        
        if perf_metrics.recall >= 0.90:
            strengths.append("High detection recall")
        
        if temp_metrics.mean_timing_error_ms < 50:
            strengths.append("Fast detection response")
        
        if temp_metrics.std_timing_error_ms < 20:
            strengths.append("Consistent timing performance")
        
        return strengths
    
    def _identify_weaknesses(self, perf_metrics: PerformanceMetrics, temp_metrics: TemporalMetrics) -> List[str]:
        """Identify test performance weaknesses"""
        weaknesses = []
        
        if perf_metrics.precision < 0.80:
            weaknesses.append("Low detection precision")
        
        if perf_metrics.recall < 0.80:
            weaknesses.append("Low detection recall")
        
        if temp_metrics.mean_timing_error_ms > 100:
            weaknesses.append("Slow detection response")
        
        if temp_metrics.std_timing_error_ms > 50:
            weaknesses.append("Inconsistent timing")
        
        return weaknesses
    
    def _generate_recommendations(self, perf_metrics: PerformanceMetrics, 
                                temp_metrics: TemporalMetrics, 
                                stat_results: StatisticalResults) -> List[str]:
        """Generate improvement recommendations"""
        recommendations = []
        
        if perf_metrics.false_positives > perf_metrics.true_positives:
            recommendations.append("Increase detection confidence threshold to reduce false positives")
        
        if perf_metrics.false_negatives > perf_metrics.true_positives * 0.3:
            recommendations.append("Lower detection threshold or retrain model for better sensitivity")
        
        if temp_metrics.mean_timing_error_ms > 100:
            recommendations.append("Optimize detection pipeline for faster processing")
        
        if temp_metrics.std_timing_error_ms > 50:
            recommendations.append("Investigate timing inconsistencies in processing pipeline")
        
        return recommendations
    
    def _extract_statistical_insights(self, stat_results: StatisticalResults) -> Dict:
        """Extract key insights from statistical analysis"""
        insights = {}
        
        if stat_results.outlier_analysis:
            outlier_percentage = stat_results.outlier_analysis.get("outlier_percentage", 0)
            if outlier_percentage > 10:
                insights["outliers"] = f"High outlier rate ({outlier_percentage:.1f}%) detected"
        
        if stat_results.trend_analysis:
            trend = stat_results.trend_analysis.get("trend_direction", "stable")
            if trend != "stable":
                insights["trend"] = f"Performance shows {trend} trend over time"
        
        return insights