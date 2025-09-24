"""
Frame-Aware Timing Quality Assessment Service

This service enhances timing quality assessment by considering frame-level correlation
accuracy rather than just timestamp proximity. It provides reliable indicators for
camera validation vs system timing overhead.

Key Features:
- Frame correlation accuracy scoring
- Camera vs system timing distinction
- Confidence metrics based on frame alignment
- Quality indicators that reflect validation reliability
- Multi-dimensional timing quality assessment
"""

import logging
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
try:
    import numpy as np
except ImportError:
    # Fallback for systems without numpy
    np = None

logger = logging.getLogger(__name__)


@dataclass
class FrameCorrelationMetrics:
    """Metrics for frame-level correlation quality"""
    frame_alignment_accuracy: float  # How well frames align with timestamps
    temporal_consistency: float      # Consistency of frame timing
    correlation_coefficient: float   # Statistical correlation strength
    frame_drift_ms: float           # Frame timing drift over session
    sync_stability: float           # Synchronization stability
    confidence_score: float         # Overall confidence in frame correlation


@dataclass
class TimingQualityDimensions:
    """Multi-dimensional timing quality assessment"""
    frame_correlation: FrameCorrelationMetrics
    timestamp_precision: float      # Precision of timestamps
    latency_consistency: float      # Consistency of latency measurements
    system_overhead_ratio: float    # Ratio of system vs camera latency
    camera_response_quality: float  # Quality of pure camera response
    validation_reliability: float   # Reliability for validation purposes
    overall_quality_score: float    # Composite quality score


@dataclass
class QualityClassification:
    """Classification of timing quality with actionable insights"""
    category: str                   # 'excellent', 'good', 'fair', 'poor', 'unreliable'
    confidence_level: str          # 'high', 'medium', 'low'
    validation_suitability: str    # 'suitable', 'conditional', 'unsuitable'
    camera_timing_quality: str     # 'precise', 'acceptable', 'imprecise'
    system_timing_quality: str     # 'precise', 'acceptable', 'imprecise'
    recommendations: List[str]      # Actionable recommendations
    warning_flags: List[str]        # Warning indicators


class FrameAwareQualityAssessment:
    """
    Enhanced timing quality assessment that considers frame-level correlation
    accuracy to distinguish between camera timing accuracy and system overhead.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Quality thresholds for frame correlation
        self.frame_correlation_thresholds = {
            'excellent': 0.95,
            'good': 0.85,
            'fair': 0.70,
            'poor': 0.50
        }
        
        # Quality thresholds for timing consistency
        self.timing_consistency_thresholds = {
            'excellent': 0.90,
            'good': 0.75,
            'fair': 0.60,
            'poor': 0.40
        }
        
        # Expected camera response ranges (in ms)
        self.camera_response_ranges = {
            'excellent': (30, 100),    # Typical camera response
            'good': (100, 200),        # Acceptable range
            'fair': (200, 500),        # Higher latency but usable
            'poor': (500, 1000)        # Poor performance
        }
        
    def assess_frame_correlation(self, 
                               detection_events: List[Dict[str, Any]], 
                               ground_truth_events: List[Dict[str, Any]],
                               video_metadata: Dict[str, Any]) -> FrameCorrelationMetrics:
        """
        Assess the quality of frame-level correlation between detections and ground truth.
        
        Args:
            detection_events: List of detection events with frame data
            ground_truth_events: List of ground truth events with frame data  
            video_metadata: Video metadata including FPS, frame count, etc.
            
        Returns:
            FrameCorrelationMetrics with detailed frame correlation assessment
        """
        try:
            # Extract frame data
            detection_frames = self._extract_frame_data(detection_events)
            gt_frames = self._extract_frame_data(ground_truth_events)
            
            if not detection_frames or not gt_frames:
                return self._create_empty_frame_metrics()
            
            # Calculate frame alignment accuracy
            frame_alignment = self._calculate_frame_alignment_accuracy(
                detection_frames, gt_frames, video_metadata
            )
            
            # Calculate temporal consistency
            temporal_consistency = self._calculate_temporal_consistency(
                detection_frames, video_metadata
            )
            
            # Calculate correlation coefficient
            correlation_coeff = self._calculate_frame_correlation_coefficient(
                detection_frames, gt_frames
            )
            
            # Calculate frame drift
            frame_drift_ms = self._calculate_frame_drift(
                detection_frames, video_metadata
            )
            
            # Calculate sync stability
            sync_stability = self._calculate_sync_stability(
                detection_frames, gt_frames
            )
            
            # Calculate overall confidence
            confidence_score = self._calculate_frame_confidence_score(
                frame_alignment, temporal_consistency, correlation_coeff, 
                frame_drift_ms, sync_stability
            )
            
            return FrameCorrelationMetrics(
                frame_alignment_accuracy=frame_alignment,
                temporal_consistency=temporal_consistency,
                correlation_coefficient=correlation_coeff,
                frame_drift_ms=frame_drift_ms,
                sync_stability=sync_stability,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            self.logger.error(f"Error assessing frame correlation: {e}")
            return self._create_empty_frame_metrics()
    
    def assess_comprehensive_quality(self,
                                   detection_events: List[Dict[str, Any]],
                                   ground_truth_events: List[Dict[str, Any]],
                                   timing_results: List[Any],
                                   video_metadata: Dict[str, Any]) -> TimingQualityDimensions:
        """
        Perform comprehensive multi-dimensional timing quality assessment.
        
        Args:
            detection_events: Detection events with timing data
            ground_truth_events: Ground truth events for correlation
            timing_results: Timing synchronization results
            video_metadata: Video timing metadata
            
        Returns:
            TimingQualityDimensions with comprehensive assessment
        """
        try:
            # Assess frame correlation
            frame_correlation = self.assess_frame_correlation(
                detection_events, ground_truth_events, video_metadata
            )
            
            # Assess timestamp precision
            timestamp_precision = self._assess_timestamp_precision(
                detection_events, timing_results
            )
            
            # Assess latency consistency
            latency_consistency = self._assess_latency_consistency(timing_results)
            
            # Calculate system overhead ratio
            system_overhead_ratio = self._calculate_system_overhead_ratio(timing_results)
            
            # Assess camera response quality
            camera_response_quality = self._assess_camera_response_quality(timing_results)
            
            # Calculate validation reliability
            validation_reliability = self._calculate_validation_reliability(
                frame_correlation, timestamp_precision, latency_consistency
            )
            
            # Calculate overall quality score
            overall_quality = self._calculate_overall_quality_score(
                frame_correlation, timestamp_precision, latency_consistency,
                system_overhead_ratio, camera_response_quality, validation_reliability
            )
            
            return TimingQualityDimensions(
                frame_correlation=frame_correlation,
                timestamp_precision=timestamp_precision,
                latency_consistency=latency_consistency,
                system_overhead_ratio=system_overhead_ratio,
                camera_response_quality=camera_response_quality,
                validation_reliability=validation_reliability,
                overall_quality_score=overall_quality
            )
            
        except Exception as e:
            self.logger.error(f"Error in comprehensive quality assessment: {e}")
            return self._create_default_quality_dimensions()
    
    def classify_timing_quality(self, quality_dimensions: TimingQualityDimensions) -> QualityClassification:
        """
        Classify timing quality with actionable insights and recommendations.
        
        Args:
            quality_dimensions: Multi-dimensional quality assessment
            
        Returns:
            QualityClassification with category, recommendations, and warnings
        """
        try:
            # Determine overall category
            category = self._determine_quality_category(quality_dimensions)
            
            # Determine confidence level
            confidence_level = self._determine_confidence_level(quality_dimensions)
            
            # Assess validation suitability
            validation_suitability = self._assess_validation_suitability(quality_dimensions)
            
            # Assess camera timing quality
            camera_timing_quality = self._assess_camera_timing_quality(quality_dimensions)
            
            # Assess system timing quality
            system_timing_quality = self._assess_system_timing_quality(quality_dimensions)
            
            # Generate recommendations
            recommendations = self._generate_quality_recommendations(quality_dimensions)
            
            # Generate warning flags
            warning_flags = self._generate_warning_flags(quality_dimensions)
            
            return QualityClassification(
                category=category,
                confidence_level=confidence_level,
                validation_suitability=validation_suitability,
                camera_timing_quality=camera_timing_quality,
                system_timing_quality=system_timing_quality,
                recommendations=recommendations,
                warning_flags=warning_flags
            )
            
        except Exception as e:
            self.logger.error(f"Error classifying timing quality: {e}")
            return self._create_default_classification()
    
    def _extract_frame_data(self, events: List[Dict[str, Any]]) -> List[Tuple[float, int]]:
        """Extract frame timing data from events"""
        frame_data = []
        for event in events:
            timestamp = event.get('video_relative_timestamp') or event.get('timestamp')
            frame_number = event.get('video_frame_number') or event.get('frame_number')
            
            if timestamp is not None and frame_number is not None:
                try:
                    frame_data.append((float(timestamp), int(frame_number)))
                except (ValueError, TypeError):
                    continue
        
        # Debug logging
        self.logger.debug(f"Extracted {len(frame_data)} frame data points from {len(events)} events")
        if frame_data:
            self.logger.debug(f"Sample frame data: {frame_data[:3]}")
                    
        return sorted(frame_data, key=lambda x: x[0])  # Sort by timestamp
    
    def _calculate_frame_alignment_accuracy(self, 
                                          detection_frames: List[Tuple[float, int]], 
                                          gt_frames: List[Tuple[float, int]],
                                          video_metadata: Dict[str, Any]) -> float:
        """Calculate how accurately frames align with timestamps"""
        if not detection_frames or not gt_frames:
            return 0.0
            
        fps = video_metadata.get('fps', video_metadata.get('frame_rate', 30))
        expected_frame_interval = 1.0 / fps
        
        # Calculate frame timing accuracy
        timing_accuracies = []
        
        for timestamp, frame_num in detection_frames:
            # For video-relative timestamps, frame alignment should be linear
            # Expected timestamp = frame_number / fps
            expected_timestamp = frame_num / fps
            
            # Calculate accuracy based on how close the actual timestamp is to expected
            time_error = abs(timestamp - expected_timestamp)
            
            # Normalize error - errors within one frame interval get high scores
            if time_error <= expected_frame_interval:
                # Error within one frame = 80-100% accuracy
                accuracy = 1.0 - (time_error / expected_frame_interval) * 0.2
            elif time_error <= expected_frame_interval * 2:
                # Error within two frames = 60-80% accuracy
                accuracy = 0.8 - ((time_error - expected_frame_interval) / expected_frame_interval) * 0.2
            else:
                # Larger errors get lower scores
                normalized_error = min(time_error / (expected_frame_interval * 5), 1.0)
                accuracy = max(0.0, 0.6 - normalized_error * 0.6)
            
            timing_accuracies.append(accuracy)
        
        return statistics.mean(timing_accuracies) if timing_accuracies else 0.0
    
    def _calculate_temporal_consistency(self, 
                                      detection_frames: List[Tuple[float, int]], 
                                      video_metadata: Dict[str, Any]) -> float:
        """Calculate temporal consistency of frame timing"""
        if len(detection_frames) < 2:
            return 0.0
            
        fps = video_metadata.get('fps', video_metadata.get('frame_rate', 30))
        expected_interval = 1.0 / fps
        
        # Calculate frame intervals
        intervals = []
        for i in range(1, len(detection_frames)):
            prev_time, prev_frame = detection_frames[i-1]
            curr_time, curr_frame = detection_frames[i]
            
            frame_diff = curr_frame - prev_frame
            time_diff = curr_time - prev_time
            
            if frame_diff > 0:
                actual_interval = time_diff / frame_diff
                intervals.append(actual_interval)
        
        if not intervals:
            return 0.0
        
        # Calculate consistency (1.0 - coefficient of variation)
        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return 0.0
            
        std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
        coefficient_of_variation = std_interval / mean_interval
        
        # Convert to consistency score (higher is better)
        consistency = max(0.0, 1.0 - coefficient_of_variation)
        return min(1.0, consistency)
    
    def _calculate_frame_correlation_coefficient(self, 
                                               detection_frames: List[Tuple[float, int]], 
                                               gt_frames: List[Tuple[float, int]]) -> float:
        """Calculate statistical correlation between frame numbers and timestamps"""
        if len(detection_frames) < 2 or len(gt_frames) < 2:
            return 0.0
            
        try:
            # Extract timestamps and frame numbers
            det_times = [x[0] for x in detection_frames]
            det_frames = [x[1] for x in detection_frames]
            
            if np is not None:
                # Use numpy if available
                correlation = np.corrcoef(det_times, det_frames)[0, 1]
                
                # Handle NaN (perfect correlation when all values are identical)
                if np.isnan(correlation):
                    return 1.0 if len(set(det_times)) == 1 or len(set(det_frames)) == 1 else 0.0
                    
                return abs(correlation)  # Use absolute value
            else:
                # Fallback calculation without numpy
                return self._calculate_correlation_fallback(det_times, det_frames)
            
        except Exception:
            return 0.0
    
    def _calculate_correlation_fallback(self, x_values: List[float], y_values: List[int]) -> float:
        """Fallback correlation calculation without numpy"""
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0
        
        try:
            n = len(x_values)
            x_mean = statistics.mean(x_values)
            y_mean = statistics.mean(y_values)
            
            numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
            
            x_variance = sum((x - x_mean) ** 2 for x in x_values)
            y_variance = sum((y - y_mean) ** 2 for y in y_values)
            
            denominator = (x_variance * y_variance) ** 0.5
            
            if denominator == 0:
                return 1.0 if x_variance == 0 and y_variance == 0 else 0.0
            
            correlation = numerator / denominator
            return abs(correlation)
            
        except Exception:
            return 0.0
    
    def _calculate_frame_drift(self, 
                             detection_frames: List[Tuple[float, int]], 
                             video_metadata: Dict[str, Any]) -> float:
        """Calculate frame timing drift in milliseconds"""
        if len(detection_frames) < 2:
            return 0.0
            
        fps = video_metadata.get('fps', video_metadata.get('frame_rate', 30))
        expected_interval = 1.0 / fps
        
        # Calculate drift between first and last frames
        first_time, first_frame = detection_frames[0]
        last_time, last_frame = detection_frames[-1]
        
        expected_duration = (last_frame - first_frame) * expected_interval
        actual_duration = last_time - first_time
        
        drift_seconds = abs(actual_duration - expected_duration)
        return drift_seconds * 1000  # Convert to milliseconds
    
    def _calculate_sync_stability(self, 
                                detection_frames: List[Tuple[float, int]], 
                                gt_frames: List[Tuple[float, int]]) -> float:
        """Calculate synchronization stability between detection and ground truth"""
        if not detection_frames or not gt_frames:
            return 0.0
        
        # Calculate time offsets between matched frames
        offsets = []
        for det_time, det_frame in detection_frames:
            # Find closest ground truth frame
            closest_gt = min(gt_frames, key=lambda x: abs(x[1] - det_frame))
            offset = det_time - closest_gt[0]
            offsets.append(offset)
        
        if not offsets:
            return 0.0
        
        # Calculate stability (1.0 - normalized standard deviation)
        mean_offset = statistics.mean(offsets)
        std_offset = statistics.stdev(offsets) if len(offsets) > 1 else 0
        
        # Normalize by mean or use absolute if mean is close to zero
        if abs(mean_offset) > 0.001:  # 1ms threshold
            normalized_std = std_offset / abs(mean_offset)
        else:
            normalized_std = std_offset / 0.001  # Use 1ms as reference
        
        stability = max(0.0, 1.0 - normalized_std)
        return min(1.0, stability)
    
    def _calculate_frame_confidence_score(self, 
                                        frame_alignment: float, 
                                        temporal_consistency: float,
                                        correlation_coeff: float,
                                        frame_drift_ms: float,
                                        sync_stability: float) -> float:
        """Calculate overall confidence score for frame correlation"""
        # Weight different factors
        weights = {
            'alignment': 0.3,
            'consistency': 0.25,
            'correlation': 0.2,
            'drift': 0.1,
            'stability': 0.15
        }
        
        # Normalize drift (lower drift = higher score)
        drift_score = max(0.0, 1.0 - (frame_drift_ms / 1000.0))  # Normalize to 1 second
        
        # Calculate weighted score
        confidence = (
            frame_alignment * weights['alignment'] +
            temporal_consistency * weights['consistency'] +
            correlation_coeff * weights['correlation'] +
            drift_score * weights['drift'] +
            sync_stability * weights['stability']
        )
        
        return min(1.0, max(0.0, confidence))
    
    def _assess_timestamp_precision(self, 
                                  detection_events: List[Dict[str, Any]], 
                                  timing_results: List[Any]) -> float:
        """Assess the precision of timestamps"""
        if not timing_results:
            return 0.5  # Default medium precision
        
        # Analyze timing accuracy from results
        accuracies = []
        for result in timing_results:
            timing_accuracy_ns = getattr(result, 'timing_accuracy_ns', None)
            if timing_accuracy_ns is not None:
                # Convert nanoseconds to precision score (0.0 to 1.0)
                # Perfect timing (0ns) = 1.0, 1ms = 0.5, 10ms+ = 0.0
                precision = max(0.0, 1.0 - (timing_accuracy_ns / 10_000_000))  # 10ms reference
                accuracies.append(precision)
        
        return statistics.mean(accuracies) if accuracies else 0.5
    
    def _assess_latency_consistency(self, timing_results: List[Any]) -> float:
        """Assess consistency of latency measurements"""
        if not timing_results:
            return 0.0
        
        latencies = []
        for result in timing_results:
            real_latency = getattr(result, 'real_latency_ms', None)
            if real_latency is not None and real_latency > 0:
                latencies.append(real_latency)
        
        if len(latencies) < 2:
            return 0.0
        
        # Calculate coefficient of variation
        mean_latency = statistics.mean(latencies)
        std_latency = statistics.stdev(latencies)
        
        if mean_latency == 0:
            return 0.0
        
        cv = std_latency / mean_latency
        consistency = max(0.0, 1.0 - cv)  # Lower CV = higher consistency
        return min(1.0, consistency)
    
    def _calculate_system_overhead_ratio(self, timing_results: List[Any]) -> float:
        """Calculate ratio of system overhead to total latency"""
        if not timing_results:
            return 0.5  # Default medium overhead
        
        overhead_ratios = []
        for result in timing_results:
            real_latency = getattr(result, 'real_latency_ms', None)
            system_overhead = getattr(result, 'system_overhead_ms', None)
            processing_overhead = getattr(result, 'processing_overhead_ms', None)
            
            if real_latency and real_latency > 0:
                total_overhead = (system_overhead or 0) + (processing_overhead or 0)
                ratio = total_overhead / real_latency
                overhead_ratios.append(min(1.0, ratio))
        
        return statistics.mean(overhead_ratios) if overhead_ratios else 0.5
    
    def _assess_camera_response_quality(self, timing_results: List[Any]) -> float:
        """Assess quality of camera response timing"""
        if not timing_results:
            return 0.0
        
        camera_latencies = []
        for result in timing_results:
            camera_latency = getattr(result, 'camera_only_latency_ms', None)
            if camera_latency is not None and camera_latency > 0:
                camera_latencies.append(camera_latency)
        
        if not camera_latencies:
            return 0.0
        
        # Assess based on expected camera response ranges
        quality_scores = []
        for latency in camera_latencies:
            if self.camera_response_ranges['excellent'][0] <= latency <= self.camera_response_ranges['excellent'][1]:
                quality_scores.append(1.0)
            elif self.camera_response_ranges['good'][0] <= latency <= self.camera_response_ranges['good'][1]:
                quality_scores.append(0.8)
            elif self.camera_response_ranges['fair'][0] <= latency <= self.camera_response_ranges['fair'][1]:
                quality_scores.append(0.6)
            elif self.camera_response_ranges['poor'][0] <= latency <= self.camera_response_ranges['poor'][1]:
                quality_scores.append(0.4)
            else:
                quality_scores.append(0.2)  # Outside all ranges
        
        return statistics.mean(quality_scores)
    
    def _calculate_validation_reliability(self, 
                                        frame_correlation: FrameCorrelationMetrics,
                                        timestamp_precision: float,
                                        latency_consistency: float) -> float:
        """Calculate overall validation reliability"""
        # Weight different reliability factors
        reliability = (
            frame_correlation.confidence_score * 0.4 +
            timestamp_precision * 0.3 +
            latency_consistency * 0.3
        )
        
        return min(1.0, max(0.0, reliability))
    
    def _calculate_overall_quality_score(self, 
                                       frame_correlation: FrameCorrelationMetrics,
                                       timestamp_precision: float,
                                       latency_consistency: float,
                                       system_overhead_ratio: float,
                                       camera_response_quality: float,
                                       validation_reliability: float) -> float:
        """Calculate composite overall quality score"""
        # Lower system overhead is better
        overhead_score = 1.0 - system_overhead_ratio
        
        # Weight all factors
        overall = (
            frame_correlation.confidence_score * 0.25 +
            timestamp_precision * 0.15 +
            latency_consistency * 0.15 +
            overhead_score * 0.15 +
            camera_response_quality * 0.15 +
            validation_reliability * 0.15
        )
        
        return min(1.0, max(0.0, overall))
    
    def _determine_quality_category(self, quality: TimingQualityDimensions) -> str:
        """Determine overall quality category"""
        score = quality.overall_quality_score
        
        if score >= 0.9:
            return "excellent"
        elif score >= 0.75:
            return "good"
        elif score >= 0.6:
            return "fair"
        elif score >= 0.4:
            return "poor"
        else:
            return "unreliable"
    
    def _determine_confidence_level(self, quality: TimingQualityDimensions) -> str:
        """Determine confidence level"""
        confidence = quality.frame_correlation.confidence_score
        
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _assess_validation_suitability(self, quality: TimingQualityDimensions) -> str:
        """Assess suitability for validation purposes"""
        reliability = quality.validation_reliability
        
        if reliability >= 0.8:
            return "suitable"
        elif reliability >= 0.6:
            return "conditional"
        else:
            return "unsuitable"
    
    def _assess_camera_timing_quality(self, quality: TimingQualityDimensions) -> str:
        """Assess camera timing quality"""
        camera_quality = quality.camera_response_quality
        
        if camera_quality >= 0.8:
            return "precise"
        elif camera_quality >= 0.6:
            return "acceptable"
        else:
            return "imprecise"
    
    def _assess_system_timing_quality(self, quality: TimingQualityDimensions) -> str:
        """Assess system timing quality"""
        precision = quality.timestamp_precision
        consistency = quality.latency_consistency
        
        combined = (precision + consistency) / 2
        
        if combined >= 0.8:
            return "precise"
        elif combined >= 0.6:
            return "acceptable"
        else:
            return "imprecise"
    
    def _generate_quality_recommendations(self, quality: TimingQualityDimensions) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Frame correlation recommendations
        if quality.frame_correlation.confidence_score < 0.7:
            recommendations.append("Improve frame-to-timestamp synchronization")
        
        if quality.frame_correlation.frame_drift_ms > 100:
            recommendations.append("Address frame timing drift - check video encoding quality")
        
        # Timestamp precision recommendations
        if quality.timestamp_precision < 0.7:
            recommendations.append("Improve timestamp precision - consider hardware timing")
        
        # Latency consistency recommendations
        if quality.latency_consistency < 0.7:
            recommendations.append("Improve system stability to reduce latency variation")
        
        # System overhead recommendations
        if quality.system_overhead_ratio > 0.6:
            recommendations.append("Optimize system to reduce processing overhead")
        
        # Camera response recommendations
        if quality.camera_response_quality < 0.6:
            recommendations.append("Check camera settings and performance optimization")
        
        if not recommendations:
            recommendations.append("Timing quality is within acceptable parameters")
        
        return recommendations
    
    def _generate_warning_flags(self, quality: TimingQualityDimensions) -> List[str]:
        """Generate warning flags for potential issues"""
        warnings = []
        
        if quality.frame_correlation.confidence_score < 0.5:
            warnings.append("LOW_FRAME_CORRELATION")
        
        if quality.frame_correlation.frame_drift_ms > 200:
            warnings.append("HIGH_FRAME_DRIFT")
        
        if quality.system_overhead_ratio > 0.8:
            warnings.append("HIGH_SYSTEM_OVERHEAD")
        
        if quality.validation_reliability < 0.5:
            warnings.append("UNRELIABLE_FOR_VALIDATION")
        
        if quality.timestamp_precision < 0.4:
            warnings.append("LOW_TIMESTAMP_PRECISION")
        
        return warnings
    
    def _create_empty_frame_metrics(self) -> FrameCorrelationMetrics:
        """Create default empty frame metrics"""
        return FrameCorrelationMetrics(
            frame_alignment_accuracy=0.0,
            temporal_consistency=0.0,
            correlation_coefficient=0.0,
            frame_drift_ms=0.0,
            sync_stability=0.0,
            confidence_score=0.0
        )
    
    def _create_default_quality_dimensions(self) -> TimingQualityDimensions:
        """Create default quality dimensions"""
        return TimingQualityDimensions(
            frame_correlation=self._create_empty_frame_metrics(),
            timestamp_precision=0.0,
            latency_consistency=0.0,
            system_overhead_ratio=0.5,
            camera_response_quality=0.0,
            validation_reliability=0.0,
            overall_quality_score=0.0
        )
    
    def _create_default_classification(self) -> QualityClassification:
        """Create default quality classification"""
        return QualityClassification(
            category="unknown",
            confidence_level="low",
            validation_suitability="unsuitable",
            camera_timing_quality="unknown",
            system_timing_quality="unknown",
            recommendations=["Unable to assess timing quality - insufficient data"],
            warning_flags=["INSUFFICIENT_DATA"]
        )


# Global service instance
_frame_aware_quality_service = None


def get_frame_aware_quality_service() -> FrameAwareQualityAssessment:
    """Get global frame-aware quality assessment service instance"""
    global _frame_aware_quality_service
    if _frame_aware_quality_service is None:
        _frame_aware_quality_service = FrameAwareQualityAssessment()
    return _frame_aware_quality_service


# Export key classes and functions
__all__ = [
    "FrameAwareQualityAssessment",
    "FrameCorrelationMetrics", 
    "TimingQualityDimensions",
    "QualityClassification",
    "get_frame_aware_quality_service"
]