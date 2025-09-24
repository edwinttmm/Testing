"""
Frame-Detection Correlation Fixes
=================================

This module provides concrete fixes for the timing synchronization issues identified
in the frame-detection correlation analysis. These fixes address the core problem
that detection timestamps don't properly correlate to their source video frames.

Key Issues Fixed:
1. Processing delay compensation
2. Consistent frame numbering
3. Improved timing quality assessment
4. Enhanced ground truth matching
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FrameDetectionCorrelation:
    """Represents the correlation between a detection and its source frame"""
    detection_id: str
    source_frame_number: int
    detection_frame_number: int
    processing_delay_ms: float
    correlation_confidence: float
    timing_quality: str
    frame_offset: int  # How many frames off the detection is


class FrameTimingAuthority:
    """
    Centralized authority for all frame-time conversions and validations.
    
    This class ensures consistent frame numbering and timing calculations
    across the entire detection-to-ground-truth correlation pipeline.
    """
    
    def __init__(self, default_fps: float = 24.0):
        self.default_fps = default_fps
        self._frame_cache = {}
        
    def frame_to_timestamp(self, frame_number: int, fps: float, video_start_time: float) -> float:
        """Convert frame number to absolute timestamp"""
        frame_time_offset = frame_number / fps
        return video_start_time + frame_time_offset
    
    def timestamp_to_frame(self, timestamp: float, fps: float, video_start_time: float) -> int:
        """Convert absolute timestamp to frame number"""
        video_relative_time = timestamp - video_start_time
        return max(0, int(video_relative_time * fps))
    
    def frame_to_video_relative_time(self, frame_number: int, fps: float) -> float:
        """Convert frame number to video-relative time in seconds"""
        return frame_number / fps
    
    def video_relative_time_to_frame(self, video_time: float, fps: float) -> int:
        """Convert video-relative time to frame number"""
        return max(0, int(video_time * fps))
    
    def validate_frame_detection_correlation(self, 
                                           detection_frame: int, 
                                           source_frame: int, 
                                           fps: float) -> Tuple[bool, float]:
        """
        Validate if detection frame properly correlates to source frame.
        
        Returns:
            (is_valid, confidence_score)
        """
        frame_diff = abs(detection_frame - source_frame)
        max_reasonable_diff = max(2, int(fps * 0.2))  # 20% of 1 second or 2 frames minimum
        
        is_valid = frame_diff <= max_reasonable_diff
        
        # Confidence decreases with frame difference
        if frame_diff == 0:
            confidence = 1.0
        elif frame_diff <= 2:
            confidence = 0.8
        elif frame_diff <= max_reasonable_diff:
            confidence = 0.6 - (frame_diff / max_reasonable_diff) * 0.3
        else:
            confidence = 0.1
            
        return is_valid, confidence


class ProcessingDelayCompensator:
    """
    Compensates for detection processing pipeline delays to improve frame correlation.
    
    The core insight is that a detection recorded at time T actually corresponds
    to a frame that was captured at time T - processing_delay.
    """
    
    def __init__(self):
        self.default_processing_delay_ms = 75.0  # Typical YOLO processing time
        self.delay_history = []
        
    def estimate_processing_delay(self, detection_metadata: Dict[str, Any]) -> float:
        """
        Estimate processing delay for a detection based on available metadata.
        
        Priority:
        1. Measured processing_time_ms from detection
        2. Historical average for this session
        3. Default estimate based on detection type
        """
        # Use measured processing time if available
        if 'processing_time_ms' in detection_metadata and detection_metadata['processing_time_ms']:
            measured_delay = float(detection_metadata['processing_time_ms'])
            self.delay_history.append(measured_delay)
            return measured_delay
        
        # Use historical average if available
        if self.delay_history:
            avg_delay = sum(self.delay_history[-10:]) / len(self.delay_history[-10:])  # Last 10 samples
            return avg_delay
        
        # Fall back to default estimate
        return self.default_processing_delay_ms
    
    def compensate_detection_timestamp(self, 
                                     detection_timestamp: float, 
                                     processing_delay_ms: float) -> Tuple[float, float]:
        """
        Compensate detection timestamp for processing delay.
        
        Returns:
            (source_frame_timestamp, processing_delay_seconds)
        """
        processing_delay_seconds = processing_delay_ms / 1000.0
        source_frame_timestamp = detection_timestamp - processing_delay_seconds
        
        logger.debug(f"Compensated detection timestamp: {detection_timestamp:.6f} -> {source_frame_timestamp:.6f} "
                    f"(delay: {processing_delay_ms:.1f}ms)")
        
        return source_frame_timestamp, processing_delay_seconds
    
    def calculate_frame_correlation(self, 
                                  detection_timestamp: float,
                                  processing_delay_ms: float,
                                  video_start_time: float,
                                  fps: float,
                                  frame_authority: FrameTimingAuthority) -> FrameDetectionCorrelation:
        """
        Calculate the correlation between detection and source frame.
        """
        # Compensate for processing delay
        source_timestamp, delay_seconds = self.compensate_detection_timestamp(
            detection_timestamp, processing_delay_ms
        )
        
        # Calculate frame numbers
        detection_frame = frame_authority.timestamp_to_frame(detection_timestamp, fps, video_start_time)
        source_frame = frame_authority.timestamp_to_frame(source_timestamp, fps, video_start_time)
        
        # Validate correlation
        is_valid, confidence = frame_authority.validate_frame_detection_correlation(
            detection_frame, source_frame, fps
        )
        
        # Assess timing quality
        frame_offset = detection_frame - source_frame
        if abs(frame_offset) == 0:
            timing_quality = "excellent"
        elif abs(frame_offset) <= 1:
            timing_quality = "good"
        elif abs(frame_offset) <= 2:
            timing_quality = "fair"
        else:
            timing_quality = "poor"
        
        return FrameDetectionCorrelation(
            detection_id="",  # To be filled by caller
            source_frame_number=source_frame,
            detection_frame_number=detection_frame,
            processing_delay_ms=processing_delay_ms,
            correlation_confidence=confidence,
            timing_quality=timing_quality,
            frame_offset=frame_offset
        )


class EnhancedGroundTruthMatcher:
    """
    Enhanced ground truth matching that accounts for processing delays and frame accuracy.
    """
    
    def __init__(self, frame_authority: FrameTimingAuthority, delay_compensator: ProcessingDelayCompensator):
        self.frame_authority = frame_authority
        self.delay_compensator = delay_compensator
        
    def find_closest_ground_truth_with_frame_correlation(self,
                                                       detection_event: Dict[str, Any],
                                                       ground_truth_events: List[Dict[str, Any]],
                                                       video_metadata: Dict[str, Any]) -> Tuple[Optional[Dict], float, FrameDetectionCorrelation]:
        """
        Find closest ground truth event using frame-accurate correlation.
        
        Returns:
            (best_match, confidence, correlation_info)
        """
        if not ground_truth_events:
            return None, 0.0, None
            
        fps = video_metadata.get('fps', 24.0)
        video_start_time = video_metadata.get('video_start_time', 0.0)
        
        # Extract detection timing information
        detection_timestamp = detection_event.get('timestamp') or detection_event.get('labjack_timestamp')
        if detection_timestamp is None:
            logger.error("No timestamp found in detection event")
            return None, 0.0, None
            
        detection_timestamp = float(detection_timestamp)
        
        # Estimate processing delay
        processing_delay_ms = self.delay_compensator.estimate_processing_delay(detection_event)
        
        # Calculate frame correlation
        correlation = self.delay_compensator.calculate_frame_correlation(
            detection_timestamp, processing_delay_ms, video_start_time, fps, self.frame_authority
        )
        correlation.detection_id = detection_event.get('id', '')
        
        # Find best ground truth match based on source frame
        best_match = None
        best_frame_diff = float('inf')
        best_confidence = 0.0
        
        for gt_event in ground_truth_events:
            # Get ground truth frame number
            gt_frame = self._get_ground_truth_frame_number(gt_event, fps)
            
            # Calculate frame difference using source frame (compensated for processing delay)
            frame_diff = abs(correlation.source_frame_number - gt_frame)
            
            # Frame-based tolerance (more accurate than time-based for video)
            frame_tolerance = max(2, int(fps * 0.1))  # 10% of 1 second or 2 frames minimum
            
            if frame_diff <= frame_tolerance and frame_diff < best_frame_diff:
                best_match = gt_event
                best_frame_diff = frame_diff
                
                # Calculate confidence based on frame accuracy
                if frame_diff == 0:
                    match_confidence = 1.0
                elif frame_diff == 1:
                    match_confidence = 0.9
                elif frame_diff <= frame_tolerance:
                    match_confidence = 0.8 - (frame_diff / frame_tolerance) * 0.3
                else:
                    match_confidence = 0.1
                    
                best_confidence = match_confidence * correlation.correlation_confidence
        
        if best_match:
            logger.info(f"Frame-based GT match: detection frame {correlation.source_frame_number} "
                       f"-> GT frame {self._get_ground_truth_frame_number(best_match, fps)} "
                       f"(diff: {best_frame_diff}, confidence: {best_confidence:.3f})")
        
        return best_match, best_confidence, correlation
    
    def _get_ground_truth_frame_number(self, gt_event: Dict[str, Any], fps: float) -> int:
        """Extract or calculate ground truth frame number"""
        # Priority: explicit frame_number > calculated from timestamp
        if 'frame_number' in gt_event and gt_event['frame_number'] is not None:
            return int(gt_event['frame_number'])
        
        # Calculate from video timestamp
        if 'timestamp' in gt_event or 'video_timestamp' in gt_event:
            timestamp = gt_event.get('timestamp') or gt_event.get('video_timestamp', 0.0)
            return self.frame_authority.video_relative_time_to_frame(float(timestamp), fps)
        
        return 0


class ImprovedTimingSynchronizationCalculator:
    """
    Improved timing synchronization calculator that addresses frame correlation issues.
    """
    
    def __init__(self):
        self.frame_authority = FrameTimingAuthority()
        self.delay_compensator = ProcessingDelayCompensator()
        self.gt_matcher = EnhancedGroundTruthMatcher(self.frame_authority, self.delay_compensator)
        
    def calculate_corrected_latency_with_frame_correlation(self,
                                                         session_id: str,
                                                         detection_id: str,
                                                         detection_event: Dict[str, Any],
                                                         ground_truth_events: List[Dict[str, Any]],
                                                         video_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate corrected latency accounting for frame correlation and processing delays.
        """
        try:
            # Find best ground truth match with frame correlation
            gt_match, match_confidence, correlation = self.gt_matcher.find_closest_ground_truth_with_frame_correlation(
                detection_event, ground_truth_events, video_metadata
            )
            
            if not gt_match or not correlation:
                logger.warning(f"No valid ground truth match found for detection {detection_id}")
                return self._create_fallback_result(detection_event, video_metadata)
            
            # Calculate timing information
            fps = video_metadata.get('fps', 24.0)
            video_start_time = video_metadata.get('video_start_time', 0.0)
            
            # Get timestamps
            detection_timestamp = float(detection_event.get('timestamp') or detection_event.get('labjack_timestamp'))
            gt_video_time = float(gt_match.get('timestamp') or gt_match.get('video_timestamp', 0.0))
            
            # Calculate corrected timing
            source_timestamp, processing_delay_seconds = self.delay_compensator.compensate_detection_timestamp(
                detection_timestamp, correlation.processing_delay_ms
            )
            
            # Ground truth system time
            gt_system_time = video_start_time + gt_video_time
            
            # Corrected latency calculation
            corrected_latency_ms = (source_timestamp - gt_system_time) * 1000.0
            apparent_latency_ms = (detection_timestamp - gt_system_time) * 1000.0
            
            # Enhanced timing quality assessment
            timing_quality = self._assess_enhanced_timing_quality(
                correlation, match_confidence, corrected_latency_ms, fps
            )
            
            result = {
                'session_id': session_id,
                'detection_id': detection_id,
                'corrected_latency_ms': corrected_latency_ms,
                'apparent_latency_ms': apparent_latency_ms,
                'processing_delay_compensation_ms': correlation.processing_delay_ms,
                'source_frame_number': correlation.source_frame_number,
                'detection_frame_number': correlation.detection_frame_number,
                'ground_truth_frame_number': self.gt_matcher._get_ground_truth_frame_number(gt_match, fps),
                'frame_offset': correlation.frame_offset,
                'timing_quality': timing_quality,
                'correlation_confidence': correlation.correlation_confidence,
                'match_confidence': match_confidence,
                'overall_confidence': (correlation.correlation_confidence + match_confidence) / 2,
                'frame_correlation_info': {
                    'source_frame_matches_gt': abs(correlation.frame_offset) <= 1,
                    'frame_accuracy_assessment': correlation.timing_quality,
                    'processing_delay_compensated': True,
                    'frame_based_matching_used': True
                }
            }
            
            logger.info(f"Enhanced latency calculation completed for {detection_id}: "
                       f"corrected={corrected_latency_ms:.3f}ms, "
                       f"frame_correlation={correlation.timing_quality}, "
                       f"overall_confidence={result['overall_confidence']:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced latency calculation: {e}", exc_info=True)
            return self._create_error_result(detection_id, str(e))
    
    def _assess_enhanced_timing_quality(self, 
                                      correlation: FrameDetectionCorrelation,
                                      match_confidence: float,
                                      latency_ms: float,
                                      fps: float) -> str:
        """Enhanced timing quality assessment considering frame correlation"""
        
        # Frame correlation quality (most important)
        frame_quality_weight = 0.5
        if correlation.timing_quality == "excellent":
            frame_score = 1.0
        elif correlation.timing_quality == "good":
            frame_score = 0.8
        elif correlation.timing_quality == "fair":
            frame_score = 0.6
        else:
            frame_score = 0.3
        
        # Match confidence (second most important)
        match_quality_weight = 0.3
        match_score = match_confidence
        
        # Latency reasonableness (least important for timing quality)
        latency_quality_weight = 0.2
        if 10 <= latency_ms <= 200:  # Reasonable detection latency range
            latency_score = 1.0
        elif 0 <= latency_ms <= 500:
            latency_score = 0.7
        else:
            latency_score = 0.3
        
        # Weighted overall score
        overall_score = (frame_score * frame_quality_weight + 
                        match_score * match_quality_weight + 
                        latency_score * latency_quality_weight)
        
        # Convert to quality label
        if overall_score >= 0.85:
            return "excellent"
        elif overall_score >= 0.7:
            return "good"
        elif overall_score >= 0.5:
            return "fair"
        else:
            return "poor"
    
    def _create_fallback_result(self, detection_event: Dict[str, Any], video_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback result when no ground truth match is found"""
        return {
            'error': 'no_ground_truth_match',
            'timing_quality': 'limited_no_ground_truth',
            'corrected_latency_ms': 0.0,
            'frame_correlation_info': {
                'source_frame_matches_gt': False,
                'frame_accuracy_assessment': 'unknown',
                'processing_delay_compensated': False,
                'frame_based_matching_used': False
            }
        }
    
    def _create_error_result(self, detection_id: str, error_msg: str) -> Dict[str, Any]:
        """Create error result for failed calculations"""
        return {
            'detection_id': detection_id,
            'error': error_msg,
            'timing_quality': 'calculation_failed',
            'corrected_latency_ms': 0.0,
            'correlation_confidence': 0.0
        }


# Usage example and integration points
def integrate_frame_correlation_fixes():
    """
    Example of how to integrate these fixes into the existing codebase.
    """
    # 1. Replace timing synchronization calculator
    improved_calculator = ImprovedTimingSynchronizationCalculator()
    
    # 2. Use in enhanced HIL endpoints
    def enhanced_calculate_corrected_latency(session_id, detection_events, ground_truth_events, video_metadata):
        results = []
        for detection in detection_events:
            result = improved_calculator.calculate_corrected_latency_with_frame_correlation(
                session_id, detection.get('id'), detection, ground_truth_events, video_metadata
            )
            results.append(result)
        return results
    
    return improved_calculator


if __name__ == "__main__":
    # Example usage
    calculator = integrate_frame_correlation_fixes()
    print("Frame-detection correlation fixes integrated successfully!")