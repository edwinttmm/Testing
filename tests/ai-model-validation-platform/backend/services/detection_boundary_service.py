from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DetectionBoundaryAnalyzer:
    """Analyzes detection vs ground truth boundaries to distinguish missing vs video ended"""
    
    def analyze_detection_boundaries(
        self, 
        detection_events: List[Dict[str, Any]], 
        ground_truth_events: List[Dict[str, Any]],
        video_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze detection boundaries and categorize ground truth events
        
        Args:
            detection_events: List of detection events with timestamps
            ground_truth_events: List of ground truth events with frame numbers
            video_metadata: Video information including fps, duration, etc.
        
        Returns:
            Dict containing:
            {
                "last_detection_time": float,
                "video_duration": float,  
                "monitoring_end_time": float,
                "categorized_events": {
                    "during_monitoring": [...],  # GT events during active detection
                    "after_monitoring": [...],   # GT events after detection stopped
                    "unmatched_during": [...],   # Missing detections (true failures)
                    "expected_after": [...]      # Expected no detections (video ended)
                },
                "boundary_analysis": {
                    "detection_coverage_percent": float,
                    "missing_detection_count": int,
                    "post_video_gt_count": int,
                    "recommended_status": str
                }
            }
        """
        logger.info(f"Analyzing detection boundaries for {len(detection_events)} detections and {len(ground_truth_events)} GT events")
        
        # Extract timestamps and find boundaries
        last_detection_time = self._find_last_detection_time(detection_events)
        video_duration = video_metadata.get('duration', 0) or video_metadata.get('duration_s', 0)
        
        # Calculate monitoring end with grace period
        grace_period = max(0.25, min(2.0, last_detection_time * 0.05)) if last_detection_time else 0.5
        monitoring_end_time = last_detection_time + grace_period
        
        logger.info(f"Last detection time: {last_detection_time}s, Monitoring end: {monitoring_end_time}s, Video duration: {video_duration}s")
        
        # Categorize ground truth events
        categorized = self._categorize_ground_truth_events(
            ground_truth_events, 
            last_detection_time,
            monitoring_end_time,
            video_metadata
        )
        
        # Match detections to ground truth during monitoring period
        categorized = self._match_detections_to_ground_truth(
            detection_events, 
            categorized,
            video_metadata
        )
        
        # Generate boundary analysis
        analysis = self._generate_boundary_analysis(
            detection_events, 
            categorized, 
            last_detection_time,
            video_duration
        )
        
        return {
            "last_detection_time": last_detection_time,
            "video_duration": video_duration,
            "monitoring_end_time": monitoring_end_time,
            "categorized_events": categorized,
            "boundary_analysis": analysis
        }
    
    def _find_last_detection_time(self, detection_events: List[Dict[str, Any]]) -> float:
        """Find the timestamp of the last detection event"""
        if not detection_events:
            logger.warning("No detection events found")
            return 0.0
            
        timestamps = []
        for event in detection_events:
            # Try multiple timestamp field names
            ts = (event.get('timestamp') or 
                  event.get('detection_time') or 
                  event.get('video_timestamp') or
                  event.get('time') or 0)
            
            if isinstance(ts, datetime):
                ts = ts.timestamp()
            elif isinstance(ts, str):
                try:
                    # Try parsing ISO format datetime
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    ts = dt.timestamp()
                except:
                    logger.warning(f"Could not parse timestamp: {ts}")
                    ts = 0
            
            timestamps.append(float(ts))
        
        last_time = max(timestamps) if timestamps else 0.0
        logger.info(f"Found {len(timestamps)} detection timestamps, last: {last_time}")
        return last_time
    
    def _categorize_ground_truth_events(
        self, 
        ground_truth_events: List[Dict[str, Any]],
        last_detection_time: float,
        monitoring_end_time: float, 
        video_metadata: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize ground truth events based on timing boundaries"""
        
        fps = video_metadata.get('fps', 30) or video_metadata.get('frame_rate', 30)
        
        during_monitoring = []
        after_monitoring = []
        
        logger.info(f"Categorizing GT events with FPS: {fps}, monitoring end: {monitoring_end_time}s")
        
        for gt_event in ground_truth_events:
            # Calculate GT event time from frame number
            frame_num = (gt_event.get('video_frame') or 
                        gt_event.get('frame_number') or 
                        gt_event.get('frame') or 0)
            
            gt_time = frame_num / fps if frame_num and fps > 0 else 0
            
            # Add calculated time to event
            enriched_event = {**gt_event, 'calculated_time': gt_time}
            
            if gt_time <= monitoring_end_time:
                during_monitoring.append(enriched_event)
            else:
                after_monitoring.append(enriched_event)
        
        logger.info(f"Categorized: {len(during_monitoring)} during monitoring, {len(after_monitoring)} after monitoring")
        
        return {
            "during_monitoring": during_monitoring,
            "after_monitoring": after_monitoring,
            "unmatched_during": [],  # Will be populated by detection matching
            "expected_after": after_monitoring  # These are expected to have no detections
        }
    
    def _match_detections_to_ground_truth(
        self,
        detection_events: List[Dict[str, Any]], 
        categorized: Dict[str, List[Dict[str, Any]]],
        video_metadata: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Match detections to ground truth events during monitoring period"""
        
        fps = video_metadata.get('fps', 30) or video_metadata.get('frame_rate', 30)
        match_tolerance = 1.0  # 1 second tolerance for matching
        
        during_monitoring = categorized["during_monitoring"].copy()
        matched_gt = []
        unmatched_during = []
        
        logger.info(f"Matching {len(detection_events)} detections to {len(during_monitoring)} GT events")
        
        # Convert detection timestamps for easier matching
        detection_times = []
        for detection in detection_events:
            ts = (detection.get('timestamp') or 
                  detection.get('detection_time') or 
                  detection.get('video_timestamp') or
                  detection.get('time') or 0)
            
            if isinstance(ts, datetime):
                ts = ts.timestamp()
            elif isinstance(ts, str):
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    ts = dt.timestamp()
                except:
                    ts = 0
                    
            detection_times.append(float(ts))
        
        # Find unmatched ground truth events (missing detections)
        for gt_event in during_monitoring:
            gt_time = gt_event['calculated_time']
            
            # Check if any detection is within tolerance
            matched = False
            for det_time in detection_times:
                if abs(det_time - gt_time) <= match_tolerance:
                    matched = True
                    break
            
            if matched:
                matched_gt.append(gt_event)
            else:
                unmatched_during.append(gt_event)
        
        logger.info(f"Matching results: {len(matched_gt)} matched, {len(unmatched_during)} unmatched during monitoring")
        
        # Update categorization
        categorized["unmatched_during"] = unmatched_during
        return categorized
    
    def _generate_boundary_analysis(
        self, 
        detection_events: List[Dict[str, Any]], 
        categorized: Dict[str, List],
        last_detection_time: float,
        video_duration: float
    ) -> Dict[str, Any]:
        """Generate summary analysis of detection boundaries"""
        
        detection_count = len(detection_events)
        gt_during_monitoring = len(categorized["during_monitoring"])
        gt_after_monitoring = len(categorized["after_monitoring"])
        missing_detections = len(categorized["unmatched_during"])
        
        # Calculate detection coverage percentage
        detection_coverage = 0.0
        if video_duration > 0:
            detection_coverage = (last_detection_time / video_duration) * 100
            detection_coverage = min(100.0, detection_coverage)  # Cap at 100%
        
        # Determine recommended status based on coverage and missing detections
        if detection_coverage >= 95 and missing_detections == 0:
            recommended_status = "complete_coverage"
        elif detection_coverage >= 80 and missing_detections <= 2:
            recommended_status = "good_coverage"
        elif detection_coverage >= 50 and missing_detections <= 5:
            recommended_status = "partial_coverage"
        else:
            recommended_status = "insufficient_coverage"
        
        # Calculate monitoring completeness
        monitoring_completeness = 0.0
        if video_duration > 0:
            monitoring_completeness = last_detection_time / video_duration
            monitoring_completeness = min(1.0, monitoring_completeness)
        
        logger.info(f"Boundary analysis: {detection_coverage:.1f}% coverage, {missing_detections} missing, status: {recommended_status}")
        
        return {
            "detection_coverage_percent": round(detection_coverage, 2),
            "missing_detection_count": missing_detections,
            "post_video_gt_count": gt_after_monitoring,
            "recommended_status": recommended_status,
            "total_detection_events": detection_count,
            "total_gt_events": gt_during_monitoring + gt_after_monitoring,
            "monitoring_completeness": round(monitoring_completeness, 3),
            "gt_during_monitoring": gt_during_monitoring,
            "matched_detections": gt_during_monitoring - missing_detections,
            "detection_accuracy": round((gt_during_monitoring - missing_detections) / max(1, gt_during_monitoring) * 100, 2)
        }

# Global instance for use across the application
detection_boundary_analyzer = DetectionBoundaryAnalyzer()