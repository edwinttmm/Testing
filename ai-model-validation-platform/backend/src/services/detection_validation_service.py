"""
Detection Validation Service

This service provides comprehensive validation and quality assurance
for LabJack and video detections, ensuring data integrity and reliability.

Features:
- Real-time detection validation
- Signal quality assessment
- Anomaly detection
- Data integrity checks
- Performance validation
- Quality metrics and reporting
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import statistics
from scipy import stats
from scipy.signal import find_peaks, butter, filtfilt
import uuid

from src.models.labjack_models import (
    LabJackDetection, VideoDetection, DetectionConfiguration,
    DetectionStatusEnum, DetectionSourceEnum
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Validation result data structure"""
    is_valid: bool
    confidence_score: float
    quality_score: float
    warnings: List[str]
    errors: List[str]
    metrics: Dict[str, float]
    recommendations: List[str]


@dataclass 
class QualityMetrics:
    """Quality assessment metrics"""
    signal_to_noise_ratio: float
    temporal_consistency: float
    amplitude_stability: float
    detection_accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    overall_quality: float


class SignalQualityAnalyzer:
    """Analyzer for signal quality assessment"""
    
    def __init__(self):
        self.logger = logger
    
    def analyze_signal_quality(
        self, 
        signal_values: List[float],
        timestamps: List[datetime],
        threshold: float,
        sampling_rate: Optional[float] = None
    ) -> QualityMetrics:
        """Analyze signal quality and return comprehensive metrics"""
        
        if not signal_values or len(signal_values) < 2:
            return QualityMetrics(0, 0, 0, 0, 1, 1, 0)
        
        try:
            signal_array = np.array(signal_values)
            
            # Signal-to-noise ratio
            snr = self._calculate_snr(signal_array, threshold)
            
            # Temporal consistency
            temporal_consistency = self._calculate_temporal_consistency(
                signal_array, timestamps
            )
            
            # Amplitude stability
            amplitude_stability = self._calculate_amplitude_stability(signal_array)
            
            # Detection accuracy metrics
            detection_accuracy = self._calculate_detection_accuracy(
                signal_array, threshold
            )
            
            # False positive/negative rates
            fp_rate, fn_rate = self._estimate_error_rates(
                signal_array, threshold
            )
            
            # Overall quality score
            overall_quality = self._calculate_overall_quality(
                snr, temporal_consistency, amplitude_stability, 
                detection_accuracy, fp_rate, fn_rate
            )
            
            return QualityMetrics(
                signal_to_noise_ratio=snr,
                temporal_consistency=temporal_consistency,
                amplitude_stability=amplitude_stability,
                detection_accuracy=detection_accuracy,
                false_positive_rate=fp_rate,
                false_negative_rate=fn_rate,
                overall_quality=overall_quality
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing signal quality: {str(e)}")
            return QualityMetrics(0, 0, 0, 0, 1, 1, 0)
    
    def _calculate_snr(self, signal: np.ndarray, threshold: float) -> float:
        """Calculate signal-to-noise ratio"""
        
        # Separate signal and noise regions
        signal_regions = signal[signal > threshold]
        noise_regions = signal[signal <= threshold * 0.8]  # Conservative noise threshold
        
        if len(signal_regions) == 0 or len(noise_regions) == 0:
            return 0.0
        
        signal_power = np.mean(signal_regions ** 2)
        noise_power = np.mean(noise_regions ** 2)
        
        if noise_power == 0:
            return float('inf')
        
        snr_db = 10 * np.log10(signal_power / noise_power)
        return max(0, snr_db)  # Clamp to positive values
    
    def _calculate_temporal_consistency(
        self, signal: np.ndarray, timestamps: List[datetime]
    ) -> float:
        """Calculate temporal consistency score"""
        
        if len(timestamps) < 2:
            return 1.0
        
        # Calculate time intervals
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return 1.0
        
        # Consistency based on coefficient of variation
        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return 1.0
        
        std_interval = statistics.stdev(intervals) if len(intervals) > 1 else 0
        cv = std_interval / mean_interval
        
        # Convert CV to consistency score (lower CV = higher consistency)
        consistency = max(0, 1 - min(cv, 1.0))
        return consistency
    
    def _calculate_amplitude_stability(self, signal: np.ndarray) -> float:
        """Calculate amplitude stability score"""
        
        if len(signal) < 2:
            return 1.0
        
        # Calculate relative variation of signal amplitude
        signal_std = np.std(signal)
        signal_mean = np.mean(np.abs(signal))
        
        if signal_mean == 0:
            return 0.0
        
        # Coefficient of variation for amplitude
        cv = signal_std / signal_mean
        
        # Convert to stability score
        stability = max(0, 1 - min(cv, 2.0) / 2.0)
        return stability
    
    def _calculate_detection_accuracy(
        self, signal: np.ndarray, threshold: float
    ) -> float:
        """Estimate detection accuracy based on signal characteristics"""
        
        # Find peaks in signal that should be detections
        peaks, properties = find_peaks(
            signal, 
            height=threshold,
            distance=int(len(signal) * 0.01)  # Minimum distance between peaks
        )
        
        # Calculate accuracy based on peak characteristics
        if len(peaks) == 0:
            return 0.0
        
        peak_heights = signal[peaks]
        peak_qualities = []
        
        for height in peak_heights:
            # Quality based on how much above threshold
            quality = min(1.0, (height - threshold) / threshold)
            peak_qualities.append(quality)
        
        return statistics.mean(peak_qualities)
    
    def _estimate_error_rates(
        self, signal: np.ndarray, threshold: float
    ) -> Tuple[float, float]:
        """Estimate false positive and false negative rates"""
        
        # This is a simplified estimation - in practice, you'd need ground truth
        # For now, we estimate based on signal characteristics
        
        # Find potential false positives (brief spikes)
        brief_peaks, _ = find_peaks(
            signal,
            height=threshold,
            width=(1, 3)  # Very brief peaks might be false positives
        )
        
        # Find potential false negatives (signal above threshold but no peak detected)
        above_threshold = np.sum(signal > threshold)
        detected_peaks = len(find_peaks(signal, height=threshold)[0])
        
        total_samples = len(signal)
        
        # Rough estimation
        fp_rate = len(brief_peaks) / max(total_samples, 1)
        fn_rate = max(0, (above_threshold - detected_peaks)) / max(above_threshold, 1)
        
        return min(1.0, fp_rate), min(1.0, fn_rate)
    
    def _calculate_overall_quality(
        self, snr: float, consistency: float, stability: float,
        accuracy: float, fp_rate: float, fn_rate: float
    ) -> float:
        """Calculate overall quality score"""
        
        # Weighted combination of quality metrics
        weights = {
            'snr': 0.3,
            'consistency': 0.2,
            'stability': 0.2,
            'accuracy': 0.2,
            'error_rates': 0.1
        }
        
        # Normalize SNR to 0-1 scale (assuming max useful SNR is 40 dB)
        snr_normalized = min(1.0, snr / 40.0)
        
        # Error rate score (lower rates = higher score)
        error_score = 1.0 - (fp_rate + fn_rate) / 2
        
        overall = (
            weights['snr'] * snr_normalized +
            weights['consistency'] * consistency +
            weights['stability'] * stability +
            weights['accuracy'] * accuracy +
            weights['error_rates'] * error_score
        )
        
        return max(0.0, min(1.0, overall))


class DetectionValidationService:
    """
    Comprehensive detection validation and quality assurance service
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.signal_analyzer = SignalQualityAnalyzer()
        self.logger = logger
        
        # Validation thresholds
        self.thresholds = {
            'min_snr_db': 6.0,
            'min_confidence': 0.5,
            'max_fp_rate': 0.1,
            'max_fn_rate': 0.2,
            'min_consistency': 0.7,
            'min_stability': 0.6
        }
    
    async def validate_labjack_detection(
        self, detection: LabJackDetection, context_window_seconds: int = 60
    ) -> ValidationResult:
        """Validate a single LabJack detection with context analysis"""
        
        warnings = []
        errors = []
        metrics = {}
        recommendations = []
        
        try:
            # Basic validation
            basic_valid = self._validate_basic_detection_data(detection, errors)
            
            # Signal quality validation
            quality_metrics = await self._validate_signal_quality(
                detection, context_window_seconds
            )
            
            # Temporal validation
            temporal_valid = await self._validate_temporal_consistency(
                detection, warnings
            )
            
            # Threshold validation
            threshold_valid = self._validate_threshold_logic(detection, warnings)
            
            # Device configuration validation
            config_valid = self._validate_device_configuration(
                detection, warnings
            )
            
            # Calculate overall confidence and quality scores
            confidence_score = self._calculate_confidence_score(
                basic_valid, quality_metrics, temporal_valid, 
                threshold_valid, config_valid
            )
            
            overall_quality = quality_metrics.overall_quality if quality_metrics else 0.0
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                quality_metrics, warnings, errors
            )
            
            # Compile metrics
            if quality_metrics:
                metrics = {
                    'signal_to_noise_ratio': quality_metrics.signal_to_noise_ratio,
                    'temporal_consistency': quality_metrics.temporal_consistency,
                    'amplitude_stability': quality_metrics.amplitude_stability,
                    'detection_accuracy': quality_metrics.detection_accuracy,
                    'false_positive_rate': quality_metrics.false_positive_rate,
                    'false_negative_rate': quality_metrics.false_negative_rate,
                    'confidence_score': confidence_score,
                    'overall_quality': overall_quality
                }
            
            is_valid = (
                basic_valid and 
                len(errors) == 0 and 
                confidence_score >= self.thresholds['min_confidence']
            )
            
            return ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                quality_score=overall_quality,
                warnings=warnings,
                errors=errors,
                metrics=metrics,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error validating detection: {str(e)}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                quality_score=0.0,
                warnings=[],
                errors=[f"Validation error: {str(e)}"],
                metrics={},
                recommendations=["Review detection data and retry validation"]
            )
    
    async def validate_video_detection(
        self, detection: VideoDetection
    ) -> ValidationResult:
        """Validate a video detection"""
        
        warnings = []
        errors = []
        metrics = {}
        recommendations = []
        
        try:
            # Basic validation
            if not detection.video_id:
                errors.append("Missing video ID")
            
            if detection.video_timestamp < 0:
                errors.append("Invalid video timestamp")
            
            if not detection.detection_type:
                errors.append("Missing detection type")
            
            # Confidence validation
            if detection.confidence_score < 0 or detection.confidence_score > 1:
                warnings.append("Confidence score outside valid range [0,1]")
            
            # Bounding box validation
            if detection.bounding_box:
                bbox_valid = self._validate_bounding_box(detection.bounding_box)
                if not bbox_valid:
                    warnings.append("Invalid bounding box coordinates")
            
            # Playback speed validation
            if detection.playback_speed <= 0:
                errors.append("Invalid playback speed")
            elif detection.playback_speed != 1.0:
                warnings.append(f"Non-standard playback speed: {detection.playback_speed}")
            
            # Temporal consistency with video
            video_duration_valid = await self._validate_video_duration_consistency(
                detection
            )
            if not video_duration_valid:
                warnings.append("Detection timestamp may exceed video duration")
            
            confidence_score = self._calculate_video_confidence_score(
                detection, len(errors), len(warnings)
            )
            
            quality_score = detection.confidence_score * 0.8 + confidence_score * 0.2
            
            metrics = {
                'detection_confidence': detection.confidence_score,
                'validation_confidence': confidence_score,
                'quality_score': quality_score,
                'playback_speed': detection.playback_speed,
                'processing_delay_ms': detection.processing_delay_ms
            }
            
            if quality_score < 0.7:
                recommendations.append("Consider manual review of detection")
            
            if detection.processing_delay_ms > 100:
                recommendations.append("High processing delay may affect synchronization")
            
            is_valid = len(errors) == 0 and confidence_score >= 0.5
            
            return ValidationResult(
                is_valid=is_valid,
                confidence_score=confidence_score,
                quality_score=quality_score,
                warnings=warnings,
                errors=errors,
                metrics=metrics,
                recommendations=recommendations
            )
            
        except Exception as e:
            self.logger.error(f"Error validating video detection: {str(e)}")
            return ValidationResult(
                is_valid=False,
                confidence_score=0.0,
                quality_score=0.0,
                warnings=[],
                errors=[f"Validation error: {str(e)}"],
                metrics={},
                recommendations=["Review detection data and retry validation"]
            )
    
    async def validate_session_detections(
        self, session_id: str, sample_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """Validate detections for an entire session"""
        
        try:
            # Get sample of detections for analysis
            labjack_detections = self._get_sample_detections(
                session_id, 'labjack', sample_size or 100
            )
            video_detections = self._get_sample_detections(
                session_id, 'video', sample_size or 100
            )
            
            # Validate samples
            labjack_results = []
            for detection in labjack_detections:
                result = await self.validate_labjack_detection(detection)
                labjack_results.append(result)
            
            video_results = []
            for detection in video_detections:
                result = await self.validate_video_detection(detection)
                video_results.append(result)
            
            # Compile session-level metrics
            session_metrics = self._compile_session_metrics(
                labjack_results, video_results
            )
            
            return {
                'session_id': session_id,
                'validation_timestamp': datetime.now(timezone.utc).isoformat(),
                'sample_sizes': {
                    'labjack_detections': len(labjack_results),
                    'video_detections': len(video_results)
                },
                'labjack_validation': self._summarize_results(labjack_results),
                'video_validation': self._summarize_results(video_results),
                'session_metrics': session_metrics,
                'overall_quality': session_metrics.get('overall_session_quality', 0.0),
                'recommendations': self._generate_session_recommendations(session_metrics)
            }
            
        except Exception as e:
            self.logger.error(f"Error validating session detections: {str(e)}")
            raise
    
    # Private methods
    
    def _validate_basic_detection_data(
        self, detection: LabJackDetection, errors: List[str]
    ) -> bool:
        """Validate basic detection data integrity"""
        
        valid = True
        
        if not detection.device_id:
            errors.append("Missing device ID")
            valid = False
        
        if detection.channel < 0 or detection.channel > 32:
            errors.append("Invalid channel number")
            valid = False
        
        if detection.signal_value is None:
            errors.append("Missing signal value")
            valid = False
        
        if detection.threshold_value is None:
            errors.append("Missing threshold value")
            valid = False
        elif detection.threshold_value <= 0:
            errors.append("Invalid threshold value")
            valid = False
        
        if detection.detection_confidence < 0 or detection.detection_confidence > 1:
            errors.append("Invalid detection confidence")
            valid = False
        
        return valid
    
    async def _validate_signal_quality(
        self, detection: LabJackDetection, context_window_seconds: int
    ) -> Optional[QualityMetrics]:
        """Validate signal quality using context window"""
        
        try:
            # Get context detections around this detection
            start_time = detection.hardware_timestamp - timedelta(seconds=context_window_seconds//2)
            end_time = detection.hardware_timestamp + timedelta(seconds=context_window_seconds//2)
            
            context_detections = self.db.query(LabJackDetection)\
                                        .filter(and_(
                                            LabJackDetection.session_id == detection.session_id,
                                            LabJackDetection.device_id == detection.device_id,
                                            LabJackDetection.channel == detection.channel,
                                            LabJackDetection.hardware_timestamp >= start_time,
                                            LabJackDetection.hardware_timestamp <= end_time
                                        ))\
                                        .order_by(LabJackDetection.hardware_timestamp)\
                                        .all()
            
            if len(context_detections) < 2:
                return None
            
            # Extract signal values and timestamps
            signal_values = [det.signal_value for det in context_detections]
            timestamps = [det.hardware_timestamp for det in context_detections]
            threshold = detection.threshold_value
            
            # Analyze signal quality
            quality_metrics = self.signal_analyzer.analyze_signal_quality(
                signal_values, timestamps, threshold
            )
            
            return quality_metrics
            
        except Exception as e:
            self.logger.error(f"Error validating signal quality: {str(e)}")
            return None
    
    async def _validate_temporal_consistency(
        self, detection: LabJackDetection, warnings: List[str]
    ) -> bool:
        """Validate temporal consistency of detection"""
        
        try:
            # Check for temporal anomalies
            time_diff = (detection.system_timestamp - detection.hardware_timestamp).total_seconds()
            
            if abs(time_diff) > 1.0:  # More than 1 second difference
                warnings.append(f"Large timestamp difference: {time_diff:.3f}s")
            
            # Check monotonic time consistency
            if hasattr(detection, 'monotonic_time') and detection.monotonic_time:
                expected_mono_time = time.monotonic()
                if abs(detection.monotonic_time - expected_mono_time) > 60:  # More than 1 minute old
                    warnings.append("Detection appears to be from old monotonic time")
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error validating temporal consistency: {str(e)}")
            return True
    
    def _validate_threshold_logic(
        self, detection: LabJackDetection, warnings: List[str]
    ) -> bool:
        """Validate threshold logic"""
        
        if detection.signal_value <= detection.threshold_value:
            warnings.append(
                f"Signal value ({detection.signal_value}) not above threshold ({detection.threshold_value})"
            )
            return False
        
        # Check if signal is significantly above threshold
        ratio = detection.signal_value / detection.threshold_value
        if ratio < 1.1:  # Less than 10% above threshold
            warnings.append("Signal barely above threshold - may be noise")
        
        return True
    
    def _validate_device_configuration(
        self, detection: LabJackDetection, warnings: List[str]
    ) -> bool:
        """Validate device configuration"""
        
        if not detection.device_config:
            warnings.append("Missing device configuration")
            return True  # Not critical
        
        # Check sampling rate
        if detection.sampling_rate:
            if detection.sampling_rate < 100:
                warnings.append("Low sampling rate may affect detection quality")
            elif detection.sampling_rate > 100000:
                warnings.append("Very high sampling rate may be unnecessary")
        
        return True
    
    def _validate_bounding_box(self, bbox: Dict[str, Any]) -> bool:
        """Validate bounding box coordinates"""
        
        required_keys = ['x', 'y', 'width', 'height']
        
        for key in required_keys:
            if key not in bbox:
                return False
            if not isinstance(bbox[key], (int, float)):
                return False
            if bbox[key] < 0:
                return False
        
        # Check if width and height are positive
        if bbox['width'] <= 0 or bbox['height'] <= 0:
            return False
        
        return True
    
    async def _validate_video_duration_consistency(
        self, detection: VideoDetection
    ) -> bool:
        """Validate that detection timestamp is within video duration"""
        
        try:
            # In a real implementation, you'd query the video metadata
            # For now, we assume reasonable video durations
            max_reasonable_duration = 7200  # 2 hours in seconds
            
            return detection.video_timestamp <= max_reasonable_duration
            
        except Exception:
            return True  # Don't fail validation on this
    
    def _calculate_confidence_score(
        self, basic_valid: bool, quality_metrics: Optional[QualityMetrics],
        temporal_valid: bool, threshold_valid: bool, config_valid: bool
    ) -> float:
        """Calculate overall confidence score for detection"""
        
        score = 0.0
        
        # Base score from basic validation
        if basic_valid:
            score += 0.3
        
        # Score from quality metrics
        if quality_metrics:
            score += 0.4 * quality_metrics.overall_quality
        else:
            score += 0.2  # Partial credit if no quality analysis available
        
        # Score from temporal validation
        if temporal_valid:
            score += 0.15
        
        # Score from threshold validation
        if threshold_valid:
            score += 0.1
        
        # Score from configuration validation
        if config_valid:
            score += 0.05
        
        return min(1.0, max(0.0, score))
    
    def _calculate_video_confidence_score(
        self, detection: VideoDetection, error_count: int, warning_count: int
    ) -> float:
        """Calculate confidence score for video detection"""
        
        base_score = 1.0
        
        # Reduce score for errors and warnings
        base_score -= error_count * 0.2
        base_score -= warning_count * 0.1
        
        # Factor in detection confidence
        base_score *= detection.confidence_score
        
        return max(0.0, min(1.0, base_score))
    
    def _generate_recommendations(
        self, quality_metrics: Optional[QualityMetrics], 
        warnings: List[str], errors: List[str]
    ) -> List[str]:
        """Generate recommendations based on validation results"""
        
        recommendations = []
        
        if errors:
            recommendations.append("Fix critical errors before using detection data")
        
        if quality_metrics:
            if quality_metrics.signal_to_noise_ratio < self.thresholds['min_snr_db']:
                recommendations.append("Consider increasing signal amplification or reducing noise")
            
            if quality_metrics.false_positive_rate > self.thresholds['max_fp_rate']:
                recommendations.append("Consider increasing detection threshold to reduce false positives")
            
            if quality_metrics.temporal_consistency < self.thresholds['min_consistency']:
                recommendations.append("Check for timing synchronization issues")
        
        if "Large timestamp difference" in ' '.join(warnings):
            recommendations.append("Synchronize system clocks between hardware and software")
        
        return recommendations
    
    def _get_sample_detections(
        self, session_id: str, detection_type: str, sample_size: int
    ) -> List[Union[LabJackDetection, VideoDetection]]:
        """Get sample detections for validation"""
        
        if detection_type == 'labjack':
            return self.db.query(LabJackDetection)\
                          .filter(LabJackDetection.session_id == session_id)\
                          .order_by(func.random())\
                          .limit(sample_size)\
                          .all()
        else:
            return self.db.query(VideoDetection)\
                          .filter(VideoDetection.session_id == session_id)\
                          .order_by(func.random())\
                          .limit(sample_size)\
                          .all()
    
    def _compile_session_metrics(
        self, labjack_results: List[ValidationResult], 
        video_results: List[ValidationResult]
    ) -> Dict[str, Any]:
        """Compile session-level validation metrics"""
        
        all_results = labjack_results + video_results
        
        if not all_results:
            return {'overall_session_quality': 0.0}
        
        # Calculate averages
        avg_confidence = statistics.mean([r.confidence_score for r in all_results])
        avg_quality = statistics.mean([r.quality_score for r in all_results])
        valid_ratio = sum(1 for r in all_results if r.is_valid) / len(all_results)
        
        # Error and warning statistics
        total_errors = sum(len(r.errors) for r in all_results)
        total_warnings = sum(len(r.warnings) for r in all_results)
        
        return {
            'overall_session_quality': (avg_confidence + avg_quality + valid_ratio) / 3,
            'average_confidence': avg_confidence,
            'average_quality': avg_quality,
            'validation_success_rate': valid_ratio,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'error_rate': total_errors / len(all_results),
            'warning_rate': total_warnings / len(all_results)
        }
    
    def _summarize_results(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """Summarize validation results"""
        
        if not results:
            return {}
        
        return {
            'total_validated': len(results),
            'valid_count': sum(1 for r in results if r.is_valid),
            'invalid_count': sum(1 for r in results if not r.is_valid),
            'average_confidence': statistics.mean([r.confidence_score for r in results]),
            'average_quality': statistics.mean([r.quality_score for r in results]),
            'total_errors': sum(len(r.errors) for r in results),
            'total_warnings': sum(len(r.warnings) for r in results),
            'common_warnings': self._get_common_issues([w for r in results for w in r.warnings]),
            'common_errors': self._get_common_issues([e for r in results for e in r.errors])
        }
    
    def _get_common_issues(self, issues: List[str]) -> List[Dict[str, Any]]:
        """Get most common issues from validation results"""
        
        if not issues:
            return []
        
        issue_counts = {}
        for issue in issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        # Sort by frequency and return top 5
        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {'issue': issue, 'count': count, 'frequency': count / len(issues)}
            for issue, count in sorted_issues[:5]
        ]
    
    def _generate_session_recommendations(
        self, session_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate session-level recommendations"""
        
        recommendations = []
        
        if session_metrics.get('overall_session_quality', 0) < 0.7:
            recommendations.append("Session quality is below acceptable threshold - review detection parameters")
        
        if session_metrics.get('error_rate', 0) > 0.1:
            recommendations.append("High error rate detected - check hardware configuration")
        
        if session_metrics.get('validation_success_rate', 0) < 0.8:
            recommendations.append("Low validation success rate - review detection criteria")
        
        return recommendations