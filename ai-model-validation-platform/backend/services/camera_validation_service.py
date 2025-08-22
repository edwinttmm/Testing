"""
Camera Validation Service
Handles camera signal detection and validation for vehicle-mounted VRU detection systems
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import json

from sqlalchemy.orm import Session
from schemas_video_annotation import SignalDetectionResult, CameraSignalType

logger = logging.getLogger(__name__)

class CameraValidationService:
    """Service for validating camera signals and detection accuracy"""
    
    def __init__(self):
        self.signal_processors = {
            "GPIO": self._process_gpio_signal,
            "Network": self._process_network_signal, 
            "Serial": self._process_serial_signal,
            "CAN": self._process_can_signal
        }
    
    async def detect_signals(
        self,
        video_id: str,
        signal_type: CameraSignalType,
        video_path: str,
        db: Session
    ) -> SignalDetectionResult:
        """Detect and analyze camera signals in video"""
        try:
            logger.info(f"Starting signal detection for video {video_id}, type: {signal_type}")
            
            # Get appropriate signal processor
            processor = self.signal_processors.get(signal_type.value)
            if not processor:
                raise ValueError(f"Unsupported signal type: {signal_type.value}")
            
            # Process the signal
            detection_data = await processor(video_path, video_id)
            
            # Create result
            result = SignalDetectionResult(
                video_id=video_id,
                signal_type=signal_type,
                detection_count=detection_data.get("count", 0),
                detection_timestamps=detection_data.get("timestamps", []),
                confidence_scores=detection_data.get("confidence_scores", []),
                signal_quality=detection_data.get("quality", "good"),
                processing_time_ms=detection_data.get("processing_time", 0),
                validation_results=detection_data.get("validation", {}),
                created_at=datetime.utcnow()
            )
            
            logger.info(f"Signal detection completed: {result.detection_count} signals found")
            return result
            
        except Exception as e:
            logger.error(f"Signal detection failed for video {video_id}: {str(e)}")
            raise
    
    async def _process_gpio_signal(self, video_path: str, video_id: str) -> Dict[str, Any]:
        """Process GPIO signal detection"""
        # Simulate GPIO signal processing
        await asyncio.sleep(0.5)  # Simulate processing time
        
        return {
            "count": 3,
            "timestamps": [1.2, 3.4, 5.6],
            "confidence_scores": [0.95, 0.87, 0.92],
            "quality": "excellent",
            "processing_time": 500,
            "validation": {
                "signal_strength": "strong",
                "noise_level": "low",
                "stability": "stable"
            }
        }
    
    async def _process_network_signal(self, video_path: str, video_id: str) -> Dict[str, Any]:
        """Process network packet signal detection"""
        await asyncio.sleep(0.3)
        
        return {
            "count": 5,
            "timestamps": [0.8, 2.1, 3.9, 4.7, 6.2],
            "confidence_scores": [0.88, 0.91, 0.85, 0.89, 0.93],
            "quality": "good",
            "processing_time": 300,
            "validation": {
                "packet_integrity": "valid",
                "latency": "low",
                "throughput": "high"
            }
        }
    
    async def _process_serial_signal(self, video_path: str, video_id: str) -> Dict[str, Any]:
        """Process serial communication signal detection"""
        await asyncio.sleep(0.4)
        
        return {
            "count": 2,
            "timestamps": [2.3, 4.8],
            "confidence_scores": [0.94, 0.87],
            "quality": "good",
            "processing_time": 400,
            "validation": {
                "baud_rate": "correct",
                "parity": "none",
                "data_integrity": "valid"
            }
        }
    
    async def _process_can_signal(self, video_path: str, video_id: str) -> Dict[str, Any]:
        """Process CAN bus signal detection"""
        await asyncio.sleep(0.6)
        
        return {
            "count": 4,
            "timestamps": [1.5, 2.8, 4.2, 5.9],
            "confidence_scores": [0.91, 0.88, 0.95, 0.89],
            "quality": "excellent", 
            "processing_time": 600,
            "validation": {
                "bus_load": "normal",
                "error_frames": 0,
                "message_rate": "optimal"
            }
        }
    
    async def validate_detection_timing(
        self,
        ground_truth_timestamps: List[float],
        detected_timestamps: List[float],
        tolerance_ms: float = 100.0
    ) -> Dict[str, Any]:
        """Validate detection timing against ground truth"""
        try:
            tolerance_sec = tolerance_ms / 1000.0
            matches = 0
            false_positives = 0
            false_negatives = 0
            timing_errors = []
            
            # Simple matching algorithm
            matched_detections = set()
            
            for gt_time in ground_truth_timestamps:
                best_match = None
                best_error = float('inf')
                
                for i, det_time in enumerate(detected_timestamps):
                    if i in matched_detections:
                        continue
                    
                    error = abs(gt_time - det_time)
                    if error <= tolerance_sec and error < best_error:
                        best_match = i
                        best_error = error
                
                if best_match is not None:
                    matches += 1
                    matched_detections.add(best_match)
                    timing_errors.append(best_error * 1000)  # Convert to ms
                else:
                    false_negatives += 1
            
            false_positives = len(detected_timestamps) - len(matched_detections)
            
            # Calculate metrics
            precision = matches / len(detected_timestamps) if detected_timestamps else 0
            recall = matches / len(ground_truth_timestamps) if ground_truth_timestamps else 0
            f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            avg_timing_error = sum(timing_errors) / len(timing_errors) if timing_errors else 0
            
            return {
                "matches": matches,
                "false_positives": false_positives,
                "false_negatives": false_negatives,
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1_score": round(f1_score, 3),
                "average_timing_error_ms": round(avg_timing_error, 2),
                "tolerance_ms": tolerance_ms,
                "timing_errors_ms": [round(e, 2) for e in timing_errors]
            }
            
        except Exception as e:
            logger.error(f"Timing validation failed: {str(e)}")
            raise
    
    def get_signal_quality_assessment(
        self, 
        signal_data: Dict[str, Any],
        signal_type: CameraSignalType
    ) -> Dict[str, Any]:
        """Assess signal quality based on detection results"""
        try:
            confidence_scores = signal_data.get("confidence_scores", [])
            detection_count = signal_data.get("count", 0)
            
            if not confidence_scores:
                return {"quality": "unknown", "score": 0.0, "issues": ["No confidence data"]}
            
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            min_confidence = min(confidence_scores)
            max_confidence = max(confidence_scores)
            confidence_variance = sum((x - avg_confidence) ** 2 for x in confidence_scores) / len(confidence_scores)
            
            # Quality assessment logic
            quality_score = avg_confidence
            quality_level = "excellent" if quality_score >= 0.9 else \
                           "good" if quality_score >= 0.8 else \
                           "fair" if quality_score >= 0.7 else \
                           "poor"
            
            issues = []
            if min_confidence < 0.6:
                issues.append("Low confidence detections found")
            if confidence_variance > 0.1:
                issues.append("High confidence variance")
            if detection_count == 0:
                issues.append("No signals detected")
            
            return {
                "quality": quality_level,
                "score": round(quality_score, 3),
                "average_confidence": round(avg_confidence, 3),
                "min_confidence": round(min_confidence, 3),
                "max_confidence": round(max_confidence, 3),
                "confidence_variance": round(confidence_variance, 4),
                "detection_count": detection_count,
                "signal_type": signal_type.value,
                "issues": issues,
                "assessment_time": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Signal quality assessment failed: {str(e)}")
            return {"quality": "error", "score": 0.0, "issues": [str(e)]}
    
    async def perform_comprehensive_validation(
        self,
        video_id: str,
        signal_type: CameraSignalType,
        ground_truth_data: Dict[str, Any],
        detection_results: SignalDetectionResult
    ) -> Dict[str, Any]:
        """Perform comprehensive validation of camera signal detection"""
        try:
            logger.info(f"Starting comprehensive validation for video {video_id}")
            
            # Timing validation
            timing_validation = await self.validate_detection_timing(
                ground_truth_data.get("timestamps", []),
                detection_results.detection_timestamps,
                ground_truth_data.get("tolerance_ms", 100.0)
            )
            
            # Quality assessment
            signal_quality = self.get_signal_quality_assessment(
                {
                    "confidence_scores": detection_results.confidence_scores,
                    "count": detection_results.detection_count
                },
                signal_type
            )
            
            # Performance metrics
            processing_efficiency = {
                "processing_time_ms": detection_results.processing_time_ms,
                "detections_per_second": detection_results.detection_count / (detection_results.processing_time_ms / 1000) if detection_results.processing_time_ms > 0 else 0,
                "efficiency_score": min(1000 / detection_results.processing_time_ms, 1.0) if detection_results.processing_time_ms > 0 else 0
            }
            
            # Overall validation result
            overall_score = (
                timing_validation["f1_score"] * 0.4 +
                signal_quality["score"] * 0.4 +
                performance_efficiency["efficiency_score"] * 0.2
            )
            
            validation_result = {
                "video_id": video_id,
                "signal_type": signal_type.value,
                "overall_score": round(overall_score, 3),
                "overall_grade": "excellent" if overall_score >= 0.9 else \
                               "good" if overall_score >= 0.8 else \
                               "fair" if overall_score >= 0.7 else \
                               "poor",
                "timing_validation": timing_validation,
                "signal_quality": signal_quality,
                "performance_metrics": processing_efficiency,
                "validation_timestamp": datetime.utcnow().isoformat(),
                "recommendations": self._generate_recommendations(timing_validation, signal_quality, performance_efficiency)
            }
            
            logger.info(f"Comprehensive validation completed with score: {overall_score}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Comprehensive validation failed: {str(e)}")
            raise
    
    def _generate_recommendations(
        self,
        timing_validation: Dict[str, Any],
        signal_quality: Dict[str, Any],
        performance_metrics: Dict[str, Any]
    ) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        # Timing recommendations
        if timing_validation["precision"] < 0.8:
            recommendations.append("Consider reducing false positive rate through improved filtering")
        if timing_validation["recall"] < 0.8:
            recommendations.append("Improve sensitivity to reduce missed detections")
        if timing_validation["average_timing_error_ms"] > 50:
            recommendations.append("Consider tightening timing accuracy requirements")
        
        # Quality recommendations
        if signal_quality["score"] < 0.8:
            recommendations.append("Review signal processing algorithms for better confidence")
        if "Low confidence detections found" in signal_quality.get("issues", []):
            recommendations.append("Implement confidence threshold filtering")
        if "High confidence variance" in signal_quality.get("issues", []):
            recommendations.append("Stabilize detection confidence through better preprocessing")
        
        # Performance recommendations  
        if performance_metrics["processing_time_ms"] > 1000:
            recommendations.append("Optimize signal processing for better real-time performance")
        if performance_metrics["efficiency_score"] < 0.5:
            recommendations.append("Consider hardware acceleration for signal processing")
        
        return recommendations if recommendations else ["System performance is acceptable"]