"""
Detection Results Service - Centralized service for processing and displaying detection results
Provides comprehensive analysis and formatting of detection events, comparisons, and test results
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from models import (
    TestSession, DetectionEvent, DetectionComparison, TestResult, 
    GroundTruthObject, Annotation, Project, Video
)
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DetectionResultsService:
    """Service for comprehensive detection results processing and analysis"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_comprehensive_test_results(self, test_session_id: str) -> Dict[str, Any]:
        """Get comprehensive results for a test session with enhanced analytics"""
        try:
            # Get test session with project/video context
            test_session = self.db.query(TestSession).filter(
                TestSession.id == test_session_id
            ).first()
            
            if not test_session:
                return {"error": "Test session not found"}
            
            # Get related project and video information
            project = self.db.query(Project).filter(Project.id == test_session.project_id).first()
            video = self.db.query(Video).filter(Video.id == test_session.video_id).first()
            
            # Get all detection events for this session
            detection_events = self.db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == test_session_id
            ).all()
            
            # Get all detection comparisons
            comparisons = self.db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == test_session_id
            ).all()
            
            # Get all test results
            test_results = self.db.query(TestResult).filter(
                TestResult.test_session_id == test_session_id
            ).all()
            
            # Build comprehensive result structure
            result = {
                "test_session": self._format_test_session(test_session, project, video),
                "detection_events": self._format_detection_events(detection_events),
                "detection_comparisons": self._format_detection_comparisons(comparisons),
                "test_results": self._format_test_results(test_results),
                "analytics": self._calculate_comprehensive_analytics(
                    detection_events, comparisons, test_results
                ),
                "summary": self._generate_executive_summary(
                    detection_events, comparisons, test_results
                )
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting comprehensive test results: {e}")
            return {"error": f"Failed to retrieve results: {str(e)}"}
    
    def _format_test_session(self, session: TestSession, project: Optional[Project], video: Optional[Video]) -> Dict[str, Any]:
        """Format test session data with context"""
        duration = None
        if session.started_at and session.completed_at:
            duration = (session.completed_at - session.started_at).total_seconds()
        
        return {
            "id": session.id,
            "name": session.name,
            "project_id": session.project_id,
            "project_name": project.name if project else "Unknown Project",
            "video_id": session.video_id,
            "video_name": video.filename if video else "Unknown Video",
            "status": session.status,
            "tolerance_ms": session.tolerance_ms,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "duration_seconds": duration,
            "created_at": session.created_at.isoformat() if session.created_at else None
        }
    
    def _format_detection_events(self, events: List[DetectionEvent]) -> List[Dict[str, Any]]:
        """Format detection events with enhanced signal data"""
        formatted_events = []
        
        for event in events:
            formatted_event = {
                "id": event.id,
                "detection_id": event.detection_id,
                "timestamp": event.timestamp,
                "confidence": event.confidence,
                "class_label": event.class_label,
                "validation_result": event.validation_result,
                "vru_type": event.vru_type,
                "frame_number": event.frame_number,
                "processing_time_ms": event.processing_time_ms,
                "model_version": event.model_version,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                
                # LabJack signal data (stored in bounding box fields for signal validation)
                "signal_data": {
                    "voltage": event.bounding_box_x,  # Voltage stored in x coordinate
                    "channel": f"AIN{int(event.bounding_box_y)}" if event.bounding_box_y is not None else None,
                    "voltage_threshold": event.bounding_box_width,
                    "sample_rate": event.bounding_box_height
                } if event.bounding_box_x is not None else None,
                
                # Bounding box data (for actual object detection)
                "bounding_box": {
                    "x": event.bounding_box_x,
                    "y": event.bounding_box_y,
                    "width": event.bounding_box_width,
                    "height": event.bounding_box_height
                } if event.class_label != "labjack_signal" and event.class_label != "labjack_signal_enhanced" else None,
                
                # Visual evidence paths
                "visual_evidence": {
                    "screenshot_path": event.screenshot_path,
                    "screenshot_zoom_path": event.screenshot_zoom_path
                } if event.screenshot_path else None
            }
            
            formatted_events.append(formatted_event)
        
        return formatted_events
    
    def _format_detection_comparisons(self, comparisons: List[DetectionComparison]) -> List[Dict[str, Any]]:
        """Format detection comparisons with enhanced timing analysis"""
        formatted_comparisons = []
        
        for comp in comparisons:
            formatted_comp = {
                "id": comp.id,
                "detection_event_id": comp.detection_event_id,
                "ground_truth_id": comp.ground_truth_id,
                "match_type": comp.match_type,
                "iou_score": comp.iou_score,
                "distance_error": comp.distance_error,
                "temporal_offset": comp.temporal_offset,
                "temporal_offset_ms": comp.temporal_offset * 1000 if comp.temporal_offset else None,
                "notes": comp.notes,
                "created_at": comp.created_at.isoformat() if comp.created_at else None,
                
                # Performance classification
                "performance_category": self._classify_performance(comp.match_type, comp.temporal_offset),
                
                # Timing analysis
                "timing_analysis": {
                    "is_within_tolerance": abs(comp.temporal_offset * 1000) <= 100 if comp.temporal_offset else False,
                    "delay_classification": self._classify_timing_delay(comp.temporal_offset),
                    "quality_score": self._calculate_quality_score(comp)
                }
            }
            
            formatted_comparisons.append(formatted_comp)
        
        return formatted_comparisons
    
    def _format_test_results(self, results: List[TestResult]) -> List[Dict[str, Any]]:
        """Format test results with enhanced statistical analysis"""
        formatted_results = []
        
        for result in results:
            formatted_result = {
                "id": result.id,
                "accuracy": result.accuracy,
                "precision": result.precision,
                "recall": result.recall,
                "f1_score": result.f1_score,
                "true_positives": result.true_positives,
                "false_positives": result.false_positives,
                "false_negatives": result.false_negatives,
                "statistical_analysis": result.statistical_analysis,
                "confidence_intervals": result.confidence_intervals,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                
                # Performance metrics
                "performance_grade": self._calculate_performance_grade(result),
                "quality_indicators": self._extract_quality_indicators(result)
            }
            
            formatted_results.append(formatted_result)
        
        return formatted_results
    
    def _calculate_comprehensive_analytics(
        self, events: List[DetectionEvent], comparisons: List[DetectionComparison], 
        results: List[TestResult]
    ) -> Dict[str, Any]:
        """Calculate comprehensive analytics across all data"""
        
        analytics = {
            "detection_performance": self._analyze_detection_performance(events),
            "timing_analysis": self._analyze_timing_performance(comparisons),
            "signal_quality": self._analyze_signal_quality(events),
            "test_efficiency": self._analyze_test_efficiency(events, results),
            "recommendations": self._generate_recommendations(events, comparisons)
        }
        
        return analytics
    
    def _analyze_detection_performance(self, events: List[DetectionEvent]) -> Dict[str, Any]:
        """Analyze detection performance metrics"""
        if not events:
            return {"message": "No detection events to analyze"}
        
        total_detections = len(events)
        successful_detections = len([e for e in events if e.validation_result == "TP"])
        failed_detections = len([e for e in events if e.validation_result in ["FN", "FP"]])
        
        # Confidence analysis
        confidences = [e.confidence for e in events if e.confidence is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        # Processing time analysis
        processing_times = [e.processing_time_ms for e in events if e.processing_time_ms is not None]
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
        
        return {
            "total_detections": total_detections,
            "successful_detections": successful_detections,
            "failed_detections": failed_detections,
            "success_rate": (successful_detections / total_detections) * 100 if total_detections > 0 else 0,
            "average_confidence": avg_confidence,
            "average_processing_time_ms": avg_processing_time,
            "confidence_distribution": {
                "high_confidence": len([c for c in confidences if c > 0.8]),
                "medium_confidence": len([c for c in confidences if 0.5 <= c <= 0.8]),
                "low_confidence": len([c for c in confidences if c < 0.5])
            }
        }
    
    def _analyze_timing_performance(self, comparisons: List[DetectionComparison]) -> Dict[str, Any]:
        """Analyze timing performance from comparisons"""
        if not comparisons:
            return {"message": "No timing comparisons to analyze"}
        
        temporal_offsets = [c.temporal_offset for c in comparisons if c.temporal_offset is not None]
        
        if not temporal_offsets:
            return {"message": "No temporal offset data available"}
        
        # Convert to milliseconds for analysis
        offsets_ms = [offset * 1000 for offset in temporal_offsets]
        
        return {
            "total_comparisons": len(comparisons),
            "timing_samples": len(temporal_offsets),
            "average_offset_ms": sum(offsets_ms) / len(offsets_ms),
            "max_offset_ms": max(offsets_ms),
            "min_offset_ms": min(offsets_ms),
            "within_tolerance_100ms": len([offset for offset in offsets_ms if abs(offset) <= 100]),
            "timing_precision": {
                "excellent": len([offset for offset in offsets_ms if abs(offset) <= 50]),
                "good": len([offset for offset in offsets_ms if 50 < abs(offset) <= 100]),
                "fair": len([offset for offset in offsets_ms if 100 < abs(offset) <= 200]),
                "poor": len([offset for offset in offsets_ms if abs(offset) > 200])
            }
        }
    
    def _analyze_signal_quality(self, events: List[DetectionEvent]) -> Dict[str, Any]:
        """Analyze LabJack signal quality"""
        signal_events = [e for e in events if e.class_label in ["labjack_signal", "labjack_signal_enhanced"]]
        
        if not signal_events:
            return {"message": "No LabJack signal events to analyze"}
        
        # Extract voltage data (stored in bounding_box_x)
        voltages = [e.bounding_box_x for e in signal_events if e.bounding_box_x is not None]
        thresholds = [e.bounding_box_width for e in signal_events if e.bounding_box_width is not None]
        
        return {
            "total_signal_events": len(signal_events),
            "voltage_samples": len(voltages),
            "average_voltage": sum(voltages) / len(voltages) if voltages else 0,
            "max_voltage": max(voltages) if voltages else 0,
            "min_voltage": min(voltages) if voltages else 0,
            "average_threshold": sum(thresholds) / len(thresholds) if thresholds else 0,
            "signal_strength": {
                "strong": len([v for v in voltages if v > 4.0]),
                "medium": len([v for v in voltages if 2.0 <= v <= 4.0]),
                "weak": len([v for v in voltages if v < 2.0])
            } if voltages else {}
        }
    
    def _analyze_test_efficiency(self, events: List[DetectionEvent], results: List[TestResult]) -> Dict[str, Any]:
        """Analyze overall test efficiency"""
        return {
            "total_test_results": len(results),
            "total_events": len(events),
            "events_per_result": len(events) / len(results) if results else 0,
            "overall_accuracy": sum([r.accuracy for r in results]) / len(results) if results else 0,
            "overall_precision": sum([r.precision for r in results]) / len(results) if results else 0,
            "overall_recall": sum([r.recall for r in results]) / len(results) if results else 0
        }
    
    def _generate_recommendations(self, events: List[DetectionEvent], comparisons: List[DetectionComparison]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        if events:
            success_rate = len([e for e in events if e.validation_result == "TP"]) / len(events)
            if success_rate < 0.8:
                recommendations.append("Consider adjusting detection thresholds to improve success rate")
        
        if comparisons:
            temporal_offsets = [c.temporal_offset * 1000 for c in comparisons if c.temporal_offset is not None]
            if temporal_offsets:
                avg_offset = sum(temporal_offsets) / len(temporal_offsets)
                if abs(avg_offset) > 100:
                    recommendations.append("Detection timing may need calibration - average offset exceeds 100ms")
        
        # Add more recommendations based on data patterns
        if not recommendations:
            recommendations.append("Detection performance appears to be within acceptable parameters")
        
        return recommendations
    
    def _generate_executive_summary(
        self, events: List[DetectionEvent], comparisons: List[DetectionComparison], 
        results: List[TestResult]
    ) -> Dict[str, Any]:
        """Generate executive summary of test performance"""
        
        total_events = len(events)
        successful_events = len([e for e in events if e.validation_result == "TP"])
        
        return {
            "overall_status": ("PASS" if (successful_events / total_events) >= 0.8 else "FAIL") if total_events > 0 else "INCOMPLETE",
            "total_detections": total_events,
            "successful_detections": successful_events,
            "success_rate_percentage": (successful_events / total_events) * 100 if total_events > 0 else 0,
            "key_metrics": {
                "detection_accuracy": successful_events / total_events if total_events > 0 else 0,
                "timing_precision": "Good" if comparisons and all(abs(c.temporal_offset or 0) <= 0.1 for c in comparisons) else "Needs Improvement",
                "signal_quality": "Good" if events and all(e.confidence and e.confidence > 0.7 for e in events if e.confidence) else "Fair"
            },
            "test_duration_analysis": {
                "total_events": total_events,
                "events_with_timing": len([c for c in comparisons if c.temporal_offset is not None])
            }
        }
    
    # Helper methods for classification
    def _classify_performance(self, match_type: str, temporal_offset: Optional[float]) -> str:
        """Classify performance based on match type and timing"""
        if match_type == "TP":
            if temporal_offset and abs(temporal_offset) <= 0.05:  # 50ms
                return "Excellent"
            elif temporal_offset and abs(temporal_offset) <= 0.1:  # 100ms
                return "Good"
            else:
                return "Acceptable"
        elif match_type == "FN":
            return "Miss"
        elif match_type == "FP":
            return "False Alarm"
        else:
            return "Unknown"
    
    def _classify_timing_delay(self, temporal_offset: Optional[float]) -> str:
        """Classify timing delay"""
        if temporal_offset is None:
            return "No Data"
        
        abs_offset_ms = abs(temporal_offset) * 1000
        
        if abs_offset_ms <= 50:
            return "Excellent"
        elif abs_offset_ms <= 100:
            return "Good"
        elif abs_offset_ms <= 200:
            return "Fair"
        else:
            return "Poor"
    
    def _calculate_quality_score(self, comparison: DetectionComparison) -> float:
        """Calculate quality score for a comparison"""
        score = 1.0
        
        # Reduce score based on timing offset
        if comparison.temporal_offset:
            abs_offset_ms = abs(comparison.temporal_offset) * 1000
            if abs_offset_ms > 50:
                score -= min(0.5, abs_offset_ms / 1000)
        
        # Adjust based on match type
        if comparison.match_type == "FN":
            score = 0.0
        elif comparison.match_type == "FP":
            score *= 0.3
        
        return max(0.0, score)
    
    def _calculate_performance_grade(self, result: TestResult) -> str:
        """Calculate performance grade"""
        if result.accuracy >= 0.9:
            return "A"
        elif result.accuracy >= 0.8:
            return "B"
        elif result.accuracy >= 0.7:
            return "C"
        elif result.accuracy >= 0.6:
            return "D"
        else:
            return "F"
    
    def _extract_quality_indicators(self, result: TestResult) -> Dict[str, Any]:
        """Extract quality indicators from test result"""
        return {
            "high_accuracy": result.accuracy >= 0.9,
            "balanced_precision_recall": abs((result.precision or 0) - (result.recall or 0)) <= 0.1,
            "low_false_positives": (result.false_positives or 0) <= 1,
            "no_false_negatives": (result.false_negatives or 0) == 0
        }