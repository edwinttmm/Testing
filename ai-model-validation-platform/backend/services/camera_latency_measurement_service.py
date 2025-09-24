"""
Camera Latency Measurement Service

Provides comprehensive measurement and validation of camera system delays
in HIL environments, including component-wise analysis and accuracy assessment.
"""

import time
import logging
import statistics
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class LatencyComponent(Enum):
    """Camera system latency components"""
    VIDEO_CAPTURE = "video_capture"
    PROCESSING_PIPELINE = "processing_pipeline"
    DISPLAY_RENDERING = "display_rendering"
    CLOCK_SYNCHRONIZATION = "clock_sync"
    NETWORK_TRANSMISSION = "network_transmission"
    SYSTEM_OVERHEAD = "system_overhead"


@dataclass
class ComponentLatency:
    """Individual component latency measurement"""
    component: LatencyComponent
    measured_ms: float
    expected_range_ms: Tuple[float, float]
    confidence_level: str  # "high", "medium", "low"
    measurement_method: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_within_expected_range(self) -> bool:
        """Check if measurement is within expected range"""
        return self.expected_range_ms[0] <= self.measured_ms <= self.expected_range_ms[1]
    
    def percentage_of_total(self, total_latency: float) -> float:
        """Calculate component percentage of total latency"""
        return (self.measured_ms / total_latency * 100) if total_latency > 0 else 0


@dataclass
class CameraLatencyAnalysis:
    """Comprehensive camera latency analysis"""
    session_id: str
    total_latency_ms: float
    component_breakdown: List[ComponentLatency]
    measurement_quality: str  # "excellent", "good", "fair", "poor"
    accuracy_assessment: str
    industry_comparison: Dict[str, Any]
    validation_confidence: str  # "high", "medium", "low"
    recommendations: List[str]
    measurement_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_component_latency(self, component: LatencyComponent) -> Optional[ComponentLatency]:
        """Get latency for specific component"""
        for comp in self.component_breakdown:
            if comp.component == component:
                return comp
        return None
    
    def total_component_latency(self) -> float:
        """Sum of all component latencies"""
        return sum(comp.measured_ms for comp in self.component_breakdown)
    
    def unaccounted_latency(self) -> float:
        """Latency not accounted for by components"""
        return self.total_latency_ms - self.total_component_latency()


class CameraLatencyMeasurementService:
    """
    Service for measuring and validating camera system latency in HIL environments
    """
    
    # Industry standard latency ranges (ms)
    COMPONENT_RANGES = {
        LatencyComponent.VIDEO_CAPTURE: (50, 500),
        LatencyComponent.PROCESSING_PIPELINE: (200, 1200),
        LatencyComponent.DISPLAY_RENDERING: (100, 400),
        LatencyComponent.CLOCK_SYNCHRONIZATION: (50, 500),
        LatencyComponent.NETWORK_TRANSMISSION: (10, 200),
        LatencyComponent.SYSTEM_OVERHEAD: (50, 300)
    }
    
    # System type latency ranges
    SYSTEM_RANGES = {
        "industrial_cameras": (10, 100),
        "ip_surveillance": (500, 2000),
        "web_cameras": (1000, 3000),
        "video_conferencing": (150, 400),
        "hil_video_systems": (500, 2000),
        "complex_vision_processing": (1000, 5000)
    }
    
    def __init__(self):
        self.measurement_history: Dict[str, List[CameraLatencyAnalysis]] = {}
        self.component_calibrations: Dict[LatencyComponent, float] = {}
        logger.info("Camera Latency Measurement Service initialized")
    
    def analyze_camera_latency(self, session_id: str, total_latency_ms: float,
                              processing_time_ms: float = 50.0,
                              system_type: str = "hil_video_systems") -> CameraLatencyAnalysis:
        """
        Analyze camera latency components and validate against industry standards
        
        Args:
            session_id: Test session identifier
            total_latency_ms: Total measured latency (GT to detection)
            processing_time_ms: Known processing time
            system_type: Type of system for comparison
            
        Returns:
            Comprehensive latency analysis
        """
        try:
            # Calculate unaccounted camera system delay
            camera_system_delay = total_latency_ms - processing_time_ms
            
            # Estimate component breakdown
            components = self._estimate_component_breakdown(camera_system_delay)
            
            # Assess measurement quality
            quality = self._assess_measurement_quality(total_latency_ms, components)
            
            # Compare with industry standards
            industry_comparison = self._compare_with_industry_standards(
                total_latency_ms, system_type
            )
            
            # Determine validation confidence
            confidence = self._calculate_validation_confidence(
                total_latency_ms, components, quality
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                total_latency_ms, components, quality, system_type
            )
            
            # Create comprehensive analysis
            analysis = CameraLatencyAnalysis(
                session_id=session_id,
                total_latency_ms=total_latency_ms,
                component_breakdown=components,
                measurement_quality=quality,
                accuracy_assessment=self._assess_accuracy(total_latency_ms, system_type),
                industry_comparison=industry_comparison,
                validation_confidence=confidence,
                recommendations=recommendations
            )
            
            # Store in measurement history
            if session_id not in self.measurement_history:
                self.measurement_history[session_id] = []
            self.measurement_history[session_id].append(analysis)
            
            logger.info(f"Camera latency analysis completed for session {session_id}: "
                       f"{total_latency_ms:.1f}ms total, {confidence} confidence")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze camera latency: {e}")
            raise
    
    def _estimate_component_breakdown(self, camera_system_delay: float) -> List[ComponentLatency]:
        """Estimate latency breakdown by component"""
        components = []
        
        # Video capture latency (16-27% of total)
        capture_latency = camera_system_delay * 0.20  # 20% estimate
        components.append(ComponentLatency(
            component=LatencyComponent.VIDEO_CAPTURE,
            measured_ms=capture_latency,
            expected_range_ms=self.COMPONENT_RANGES[LatencyComponent.VIDEO_CAPTURE],
            confidence_level="medium",
            measurement_method="statistical_estimation"
        ))
        
        # Processing pipeline (40-50% of total)
        pipeline_latency = camera_system_delay * 0.45  # 45% estimate
        components.append(ComponentLatency(
            component=LatencyComponent.PROCESSING_PIPELINE,
            measured_ms=pipeline_latency,
            expected_range_ms=self.COMPONENT_RANGES[LatencyComponent.PROCESSING_PIPELINE],
            confidence_level="high",
            measurement_method="statistical_estimation"
        ))
        
        # Display rendering (15-20% of total)
        display_latency = camera_system_delay * 0.17  # 17% estimate
        components.append(ComponentLatency(
            component=LatencyComponent.DISPLAY_RENDERING,
            measured_ms=display_latency,
            expected_range_ms=self.COMPONENT_RANGES[LatencyComponent.DISPLAY_RENDERING],
            confidence_level="medium",
            measurement_method="statistical_estimation"
        ))
        
        # Clock synchronization and overhead (remaining ~18%)
        sync_latency = camera_system_delay * 0.18  # 18% estimate
        components.append(ComponentLatency(
            component=LatencyComponent.CLOCK_SYNCHRONIZATION,
            measured_ms=sync_latency,
            expected_range_ms=self.COMPONENT_RANGES[LatencyComponent.CLOCK_SYNCHRONIZATION],
            confidence_level="low",
            measurement_method="statistical_estimation"
        ))
        
        return components
    
    def _assess_measurement_quality(self, total_latency: float, 
                                  components: List[ComponentLatency]) -> str:
        """Assess overall measurement quality"""
        # Check if components are within expected ranges
        components_in_range = sum(1 for comp in components if comp.is_within_expected_range())
        range_score = components_in_range / len(components)
        
        # Check if total latency is reasonable
        reasonable_total = 500 <= total_latency <= 5000  # Reasonable range for HIL systems
        
        # Calculate quality score
        if range_score >= 0.8 and reasonable_total:
            return "excellent"
        elif range_score >= 0.6 and reasonable_total:
            return "good"
        elif range_score >= 0.4:
            return "fair"
        else:
            return "poor"
    
    def _compare_with_industry_standards(self, total_latency: float, 
                                       system_type: str) -> Dict[str, Any]:
        """Compare latency with industry standards"""
        comparison = {
            "system_type": system_type,
            "measured_latency_ms": total_latency,
            "industry_standards": {}
        }
        
        for system, (min_lat, max_lat) in self.SYSTEM_RANGES.items():
            within_range = min_lat <= total_latency <= max_lat
            comparison["industry_standards"][system] = {
                "range_ms": [min_lat, max_lat],
                "within_range": within_range,
                "deviation_percent": self._calculate_deviation(total_latency, min_lat, max_lat)
            }
        
        # Determine best match
        best_matches = [
            system for system, data in comparison["industry_standards"].items()
            if data["within_range"]
        ]
        comparison["best_matches"] = best_matches
        comparison["primary_classification"] = system_type if system_type in best_matches else best_matches[0] if best_matches else "unknown"
        
        return comparison
    
    def _calculate_deviation(self, measured: float, min_range: float, max_range: float) -> float:
        """Calculate deviation from expected range"""
        if min_range <= measured <= max_range:
            return 0.0  # Within range
        elif measured < min_range:
            return ((min_range - measured) / min_range) * 100
        else:
            return ((measured - max_range) / max_range) * 100
    
    def _calculate_validation_confidence(self, total_latency: float,
                                       components: List[ComponentLatency],
                                       quality: str) -> str:
        """Calculate confidence level in validation"""
        confidence_score = 0
        
        # Quality assessment contribution (40%)
        quality_scores = {"excellent": 40, "good": 30, "fair": 20, "poor": 10}
        confidence_score += quality_scores.get(quality, 0)
        
        # Component range compliance (30%)
        components_in_range = sum(1 for comp in components if comp.is_within_expected_range())
        range_score = (components_in_range / len(components)) * 30
        confidence_score += range_score
        
        # Industry standard compliance (30%)
        hil_range = self.SYSTEM_RANGES.get("hil_video_systems", (500, 2000))
        if hil_range[0] <= total_latency <= hil_range[1]:
            confidence_score += 30
        elif total_latency < hil_range[0] * 2 and total_latency > hil_range[1] / 2:
            confidence_score += 15  # Close to range
        
        # Determine confidence level
        if confidence_score >= 80:
            return "high"
        elif confidence_score >= 60:
            return "medium"
        else:
            return "low"
    
    def _assess_accuracy(self, total_latency: float, system_type: str) -> str:
        """Assess accuracy of latency measurement"""
        system_range = self.SYSTEM_RANGES.get(system_type, (0, float('inf')))
        
        if system_range[0] <= total_latency <= system_range[1]:
            return "ACCURATE - Within expected range for system type"
        elif total_latency < system_range[0]:
            return f"POTENTIALLY LOW - Below expected range ({system_range[0]}-{system_range[1]}ms)"
        else:
            deviation = (total_latency - system_range[1]) / system_range[1] * 100
            if deviation <= 50:  # Within 50% of upper bound
                return f"ACCEPTABLE - Slightly above range but within tolerance (+{deviation:.1f}%)"
            else:
                return f"HIGH - Significantly above expected range (+{deviation:.1f}%)"
    
    def _generate_recommendations(self, total_latency: float,
                                components: List[ComponentLatency],
                                quality: str, system_type: str) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        # Accept measurement if reasonable
        if 500 <= total_latency <= 2500 and quality in ["excellent", "good"]:
            recommendations.append("✅ Accept current measurements as accurate baseline")
            recommendations.append("📊 Document baseline for future comparison testing")
        
        # Component-specific recommendations
        pipeline_comp = next((c for c in components if c.component == LatencyComponent.PROCESSING_PIPELINE), None)
        if pipeline_comp and pipeline_comp.measured_ms > 1000:
            recommendations.append("🔧 Optimize video processing pipeline to reduce encoding/decoding delays")
            recommendations.append("⚡ Consider using raw frames or reduced buffering for HIL applications")
        
        capture_comp = next((c for c in components if c.component == LatencyComponent.VIDEO_CAPTURE), None)
        if capture_comp and capture_comp.measured_ms > 400:
            recommendations.append("📹 Optimize camera settings: reduce buffer size, disable auto-exposure")
            recommendations.append("🔌 Consider direct camera connection to minimize capture latency")
        
        # System-wide recommendations
        if total_latency > 2000:
            recommendations.append("⚙️ Implement component-specific measurement for optimization targets")
            recommendations.append("🚀 Consider hardware upgrade for time-critical applications")
        
        if quality in ["fair", "poor"]:
            recommendations.append("🧪 Perform component-wise validation using hardware triggers")
            recommendations.append("📏 Implement cross-validation using multiple measurement methods")
        
        # Monitoring recommendations
        recommendations.append("📈 Monitor trends to detect system degradation over time")
        recommendations.append("🔍 Set up alerts for latency exceeding baseline + 20%")
        
        return recommendations
    
    def validate_latency_measurement(self, session_id: str, ground_truth_time: float,
                                   detection_time: float, processing_time: float = 50.0) -> Dict[str, Any]:
        """
        Validate a specific latency measurement
        
        Args:
            session_id: Test session identifier
            ground_truth_time: Ground truth event timestamp
            detection_time: Detection event timestamp  
            processing_time: Known processing time (ms)
            
        Returns:
            Validation results with accuracy assessment
        """
        try:
            # Calculate total latency
            total_latency_ms = (detection_time - ground_truth_time) * 1000
            
            # Perform comprehensive analysis
            analysis = self.analyze_camera_latency(
                session_id, total_latency_ms, processing_time
            )
            
            # Create validation result
            result = {
                "session_id": session_id,
                "measurement_valid": analysis.validation_confidence in ["high", "medium"],
                "total_latency_ms": total_latency_ms,
                "camera_system_delay_ms": total_latency_ms - processing_time,
                "quality_assessment": analysis.measurement_quality,
                "accuracy_assessment": analysis.accuracy_assessment,
                "confidence_level": analysis.validation_confidence,
                "component_breakdown": {
                    comp.component.value: {
                        "measured_ms": comp.measured_ms,
                        "percentage": comp.percentage_of_total(total_latency_ms),
                        "within_range": comp.is_within_expected_range()
                    }
                    for comp in analysis.component_breakdown
                },
                "industry_comparison": analysis.industry_comparison,
                "recommendations": analysis.recommendations,
                "validation_timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Latency measurement validated: {total_latency_ms:.1f}ms "
                       f"({analysis.validation_confidence} confidence)")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate latency measurement: {e}")
            return {
                "session_id": session_id,
                "measurement_valid": False,
                "error": str(e),
                "validation_timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_measurement_history(self, session_id: str) -> List[CameraLatencyAnalysis]:
        """Get measurement history for a session"""
        return self.measurement_history.get(session_id, [])
    
    def export_latency_analysis(self, session_id: str) -> Dict[str, Any]:
        """Export comprehensive latency analysis for reporting"""
        analyses = self.get_measurement_history(session_id)
        
        if not analyses:
            return {"error": "No measurement history found", "session_id": session_id}
        
        latest_analysis = analyses[-1]
        
        return {
            "session_id": session_id,
            "measurement_count": len(analyses),
            "latest_analysis": {
                "total_latency_ms": latest_analysis.total_latency_ms,
                "measurement_quality": latest_analysis.measurement_quality,
                "accuracy_assessment": latest_analysis.accuracy_assessment,
                "validation_confidence": latest_analysis.validation_confidence,
                "component_breakdown": [
                    {
                        "component": comp.component.value,
                        "measured_ms": comp.measured_ms,
                        "expected_range_ms": comp.expected_range_ms,
                        "within_range": comp.is_within_expected_range(),
                        "percentage": comp.percentage_of_total(latest_analysis.total_latency_ms)
                    }
                    for comp in latest_analysis.component_breakdown
                ],
                "industry_comparison": latest_analysis.industry_comparison,
                "recommendations": latest_analysis.recommendations
            },
            "historical_trends": [
                {
                    "timestamp": analysis.measurement_timestamp.isoformat(),
                    "total_latency_ms": analysis.total_latency_ms,
                    "quality": analysis.measurement_quality,
                    "confidence": analysis.validation_confidence
                }
                for analysis in analyses
            ],
            "export_timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global service instance
_camera_latency_service: Optional[CameraLatencyMeasurementService] = None


def get_camera_latency_service() -> CameraLatencyMeasurementService:
    """Get global camera latency measurement service instance"""
    global _camera_latency_service
    if _camera_latency_service is None:
        _camera_latency_service = CameraLatencyMeasurementService()
    return _camera_latency_service


# Export key classes and functions
__all__ = [
    "CameraLatencyMeasurementService",
    "CameraLatencyAnalysis",
    "ComponentLatency",
    "LatencyComponent",
    "get_camera_latency_service"
]