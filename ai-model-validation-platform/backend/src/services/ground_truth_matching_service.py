"""
Ground Truth Matching Service
============================

Service for matching HIL detection events to ground truth objects with video timing synchronization.
This service replaces simple detection counting with proper validation against known ground truth.

Key Features:
- Temporal matching between detections and ground truth
- Video timing synchronization for accurate latency calculation
- Precision/recall calculation based on matched detections
- Real latency measurement using ground truth timestamps
- Support for multiple matching strategies
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, NamedTuple
from dataclasses import dataclass, asdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models import DetectionEvent, GroundTruthObject, Video, TestSession
from database import SessionLocal

logger = logging.getLogger(__name__)


@dataclass
class MatchingResult:
    """Result of matching a detection to ground truth"""
    detection_id: str
    ground_truth_id: Optional[str]
    is_match: bool
    temporal_offset_ms: float  # Positive if detection is after ground truth
    spatial_overlap: float     # IoU or similar spatial metric
    confidence_score: float
    match_type: str           # "true_positive", "false_positive", "false_negative"


@dataclass 
class GroundTruthMatchingResults:
    """Complete results of ground truth matching for a session"""
    session_id: str
    video_id: Optional[str]
    video_playback_start_time: Optional[float]
    
    # Match results
    matches: List[MatchingResult]
    
    # Summary metrics
    true_positives: int
    false_positives: int
    false_negatives: int
    
    # Temporal metrics
    temporal_offsets: List[float]  # All temporal offsets for matched detections
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    median_latency_ms: float
    
    # Quality metrics  
    precision: float
    recall: float
    f1_score: float
    
    # Matching configuration
    temporal_tolerance_ms: float
    spatial_tolerance: float
    
    created_at: datetime


class GroundTruthMatchingService:
    """Service for matching detections to ground truth with video timing"""
    
    def __init__(self, db_session: Optional[Session] = None):
        self.db_session = db_session or SessionLocal()
        self._should_close_session = db_session is None
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._should_close_session and self.db_session:
            self.db_session.close()
    
    def match_detections_to_ground_truth(
        self,
        session_id: str,
        temporal_tolerance_ms: float = 500.0,  # 500ms tolerance window
        spatial_tolerance: float = 0.3,        # 30% IoU threshold
        matching_strategy: str = "nearest_temporal"
    ) -> GroundTruthMatchingResults:
        """
        Match detection events to ground truth objects for a test session
        
        Args:
            session_id: Test session ID
            temporal_tolerance_ms: Maximum time difference for temporal matching (ms)
            spatial_tolerance: Minimum spatial overlap for spatial matching
            matching_strategy: Strategy for matching ("nearest_temporal", "best_spatial", "combined")
            
        Returns:
            Comprehensive matching results with metrics
        """
        try:
            logger.info(f"Starting ground truth matching for session {session_id}")
            
            # Get session and video information
            session = self.db_session.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            if not session:
                raise ValueError(f"Test session {session_id} not found")
            
            # Get video timing information
            video_timing = self._get_video_timing_context(session)
            
            # Get detection events for this session
            detections = self.db_session.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).order_by(DetectionEvent.timestamp).all()
            
            # Get ground truth objects for the session's video
            ground_truth_objects = self._get_ground_truth_for_session(session)
            
            logger.info(f"Found {len(detections)} detections and {len(ground_truth_objects)} ground truth objects")
            
            if not ground_truth_objects:
                logger.warning(f"No ground truth objects found for session {session_id}")
                return self._create_empty_results(session_id, session.video_id, video_timing)
            
            # Perform matching based on strategy
            matches = self._perform_matching(
                detections,
                ground_truth_objects,
                video_timing,
                temporal_tolerance_ms,
                spatial_tolerance,
                matching_strategy
            )
            
            # Calculate metrics from matches
            results = self._calculate_matching_metrics(
                session_id,
                session.video_id,
                video_timing,
                matches,
                len(detections),
                len(ground_truth_objects),
                temporal_tolerance_ms,
                spatial_tolerance
            )
            
            logger.info(f"Ground truth matching completed: {results.true_positives}/{len(ground_truth_objects)} matched, "
                       f"P={results.precision:.2f}, R={results.recall:.2f}, F1={results.f1_score:.2f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in ground truth matching: {str(e)}")
            raise
    
    def _get_video_timing_context(self, session: TestSession) -> Dict[str, Any]:
        """Get video timing context for the session"""
        video_timing = {
            "video_playback_start_time": None,
            "video_duration": None,
            "fps": None,
            "session_start_time": session.started_at.timestamp() if session.started_at else None
        }
        
        if session.video_id:
            video = self.db_session.query(Video).filter(Video.id == session.video_id).first()
            if video:
                video_timing["video_duration"] = video.duration
                video_timing["fps"] = getattr(video, 'fps', None)
                
                # Check if video playback start time is stored in session configuration
                if hasattr(session, 'configuration') and session.configuration:
                    video_timing["video_playback_start_time"] = session.configuration.get("video_playback_start_time")
                # Prefer persisted session field when available
                if getattr(session, 'video_playback_start_time', None):
                    try:
                        vps = float(session.video_playback_start_time)
                        # If value seems like ms epoch, convert to seconds
                        if vps >= 1e11:
                            vps = vps / 1000.0
                        video_timing["video_playback_start_time"] = vps
                    except Exception:
                        pass
        
        return video_timing
    
    def _get_ground_truth_for_session(self, session: TestSession) -> List[GroundTruthObject]:
        """Get ground truth objects for the session's video"""
        if not session.video_id:
            return []
            
        return self.db_session.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == session.video_id,
            GroundTruthObject.validated == True  # Only use validated ground truth
        ).order_by(GroundTruthObject.timestamp).all()
    
    def _perform_matching(
        self,
        detections: List[DetectionEvent],
        ground_truth_objects: List[GroundTruthObject],
        video_timing: Dict[str, Any],
        temporal_tolerance_ms: float,
        spatial_tolerance: float,
        strategy: str
    ) -> List[MatchingResult]:
        """Perform the actual matching between detections and ground truth"""
        matches = []
        used_ground_truth_ids = set()
        
        for detection in detections:
            best_match = self._find_best_match(
                detection,
                ground_truth_objects,
                video_timing,
                temporal_tolerance_ms,
                spatial_tolerance,
                strategy,
                used_ground_truth_ids
            )
            
            if best_match:
                matches.append(best_match)
                if best_match.ground_truth_id:
                    used_ground_truth_ids.add(best_match.ground_truth_id)
            else:
                # False positive - detection with no matching ground truth
                matches.append(MatchingResult(
                    detection_id=detection.id,
                    ground_truth_id=None,
                    is_match=False,
                    temporal_offset_ms=0.0,
                    spatial_overlap=0.0,
                    confidence_score=detection.confidence or 0.0,
                    match_type="false_positive"
                ))
        
        # Add false negatives - ground truth objects not matched to any detection
        for gt_obj in ground_truth_objects:
            if gt_obj.id not in used_ground_truth_ids:
                matches.append(MatchingResult(
                    detection_id="",  # No detection for this ground truth
                    ground_truth_id=gt_obj.id,
                    is_match=False,
                    temporal_offset_ms=0.0,
                    spatial_overlap=0.0,
                    confidence_score=0.0,
                    match_type="false_negative"
                ))
        
        return matches
    
    def _find_best_match(
        self,
        detection: DetectionEvent,
        ground_truth_objects: List[GroundTruthObject],
        video_timing: Dict[str, Any],
        temporal_tolerance_ms: float,
        spatial_tolerance: float,
        strategy: str,
        used_ground_truth_ids: set
    ) -> Optional[MatchingResult]:
        """Find the best matching ground truth object for a detection"""
        
        # Convert detection timing to video-relative time
        detection_video_time = self._to_video_relative_time(detection, video_timing)
        
        if detection_video_time is None:
            logger.warning(f"Could not convert detection timestamp to video time for detection {detection.id}")
            return None
        
        best_match = None
        best_score = -1.0
        
        for gt_obj in ground_truth_objects:
            if gt_obj.id in used_ground_truth_ids:
                continue  # Already matched
            
            # Calculate temporal offset
            temporal_offset_ms = abs(detection_video_time * 1000 - gt_obj.timestamp * 1000)
            
            # Skip if outside temporal tolerance
            if temporal_offset_ms > temporal_tolerance_ms:
                continue
            
            # Calculate spatial overlap if bounding boxes are available
            spatial_overlap = self._calculate_spatial_overlap(detection, gt_obj)
            
            # Skip if below spatial tolerance (when spatial data is available)
            if spatial_overlap is not None and spatial_overlap < spatial_tolerance:
                continue
            
            # Calculate match score based on strategy
            match_score = self._calculate_match_score(
                temporal_offset_ms, spatial_overlap, strategy, temporal_tolerance_ms, spatial_tolerance
            )
            
            if match_score > best_score:
                best_score = match_score
                best_match = MatchingResult(
                    detection_id=detection.id,
                    ground_truth_id=gt_obj.id,
                    is_match=True,
                    temporal_offset_ms=detection_video_time * 1000 - gt_obj.timestamp * 1000,  # Signed offset
                    spatial_overlap=spatial_overlap or 0.0,
                    confidence_score=detection.confidence or 0.0,
                    match_type="true_positive"
                )
        
        return best_match
    
    def _to_video_relative_time(self, detection: DetectionEvent, video_timing: Dict[str, Any]) -> Optional[float]:
        """Derive detection time relative to video start using best available data.
        Priority:
        1) detection.video_relative_timestamp (already relative)
        2) detection.video_frame_number / fps (if fps known)
        3) detection.timestamp - video_playback_start_time (if both exist)
        4) detection.timestamp - session_start_time (fallback)
        5) detection.timestamp (last resort)
        """
        # 1) Direct video-relative timestamp
        if getattr(detection, 'video_relative_timestamp', None) is not None:
            try:
                return float(detection.video_relative_timestamp)
            except Exception:
                pass
        # 2) Compute from frame number
        fps = video_timing.get('fps')
        if fps and getattr(detection, 'video_frame_number', None) is not None:
            try:
                return float(detection.video_frame_number) / float(fps)
            except Exception:
                pass
        # 3) Unix timestamp minus video start
        vps = video_timing.get('video_playback_start_time')
        if vps is not None and getattr(detection, 'timestamp', None) is not None:
            try:
                return float(detection.timestamp) - float(vps)
            except Exception:
                pass
        # 4) Use session start time
        session_start = video_timing.get('session_start_time')
        if session_start is not None and getattr(detection, 'timestamp', None) is not None:
            try:
                return float(detection.timestamp) - float(session_start)
            except Exception:
                pass
        # 5) Last resort
        try:
            return float(getattr(detection, 'timestamp', 0.0))
        except Exception:
            return None
    
    def _calculate_spatial_overlap(self, detection: DetectionEvent, gt_obj: GroundTruthObject) -> Optional[float]:
        """Calculate spatial overlap (IoU) between detection and ground truth bounding boxes"""
        
        # Check if both have bounding box data
        if not all([
            detection.bounding_box_x is not None,
            detection.bounding_box_y is not None, 
            detection.bounding_box_width is not None,
            detection.bounding_box_height is not None
        ]):
            return None  # No spatial data for detection
        
        if not hasattr(gt_obj, 'bounding_box') or not gt_obj.bounding_box:
            return None  # No spatial data for ground truth
        
        # Extract coordinates
        det_x1 = detection.bounding_box_x
        det_y1 = detection.bounding_box_y
        det_x2 = det_x1 + detection.bounding_box_width
        det_y2 = det_y1 + detection.bounding_box_height
        
        # Parse ground truth bounding box (assuming it's stored as dict or similar)
        try:
            if isinstance(gt_obj.bounding_box, dict):
                gt_x1 = gt_obj.bounding_box.get('x', 0)
                gt_y1 = gt_obj.bounding_box.get('y', 0) 
                gt_x2 = gt_x1 + gt_obj.bounding_box.get('width', 0)
                gt_y2 = gt_y1 + gt_obj.bounding_box.get('height', 0)
            else:
                # If stored differently, parse as needed
                return None
        except:
            return None
        
        # Calculate IoU
        intersection_x1 = max(det_x1, gt_x1)
        intersection_y1 = max(det_y1, gt_y1)
        intersection_x2 = min(det_x2, gt_x2)
        intersection_y2 = min(det_y2, gt_y2)
        
        if intersection_x2 <= intersection_x1 or intersection_y2 <= intersection_y1:
            return 0.0  # No intersection
        
        intersection_area = (intersection_x2 - intersection_x1) * (intersection_y2 - intersection_y1)
        
        det_area = (det_x2 - det_x1) * (det_y2 - det_y1)
        gt_area = (gt_x2 - gt_x1) * (gt_y2 - gt_y1)
        union_area = det_area + gt_area - intersection_area
        
        if union_area <= 0:
            return 0.0
        
        return intersection_area / union_area
    
    def _calculate_match_score(
        self, 
        temporal_offset_ms: float, 
        spatial_overlap: Optional[float], 
        strategy: str,
        temporal_tolerance_ms: float,
        spatial_tolerance: float
    ) -> float:
        """Calculate match score based on temporal and spatial factors"""
        
        # Temporal score (0-1, higher is better)
        temporal_score = max(0, 1.0 - (temporal_offset_ms / temporal_tolerance_ms))
        
        # Spatial score (0-1, higher is better)
        if spatial_overlap is not None:
            spatial_score = spatial_overlap
        else:
            spatial_score = 1.0  # Assume perfect spatial match when no spatial data
        
        # Combine scores based on strategy
        if strategy == "nearest_temporal":
            return temporal_score
        elif strategy == "best_spatial":
            return spatial_score
        elif strategy == "combined":
            return (temporal_score + spatial_score) / 2.0
        else:
            return temporal_score  # Default to temporal
    
    def _calculate_matching_metrics(
        self,
        session_id: str,
        video_id: Optional[str],
        video_timing: Dict[str, Any],
        matches: List[MatchingResult],
        total_detections: int,
        total_ground_truth: int,
        temporal_tolerance_ms: float,
        spatial_tolerance: float
    ) -> GroundTruthMatchingResults:
        """Calculate comprehensive metrics from matching results"""
        
        # Count match types
        true_positives = len([m for m in matches if m.match_type == "true_positive"])
        false_positives = len([m for m in matches if m.match_type == "false_positive"])
        false_negatives = len([m for m in matches if m.match_type == "false_negative"])
        
        # Calculate precision, recall, F1
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Extract temporal offsets for latency analysis
        temporal_offsets = [m.temporal_offset_ms for m in matches if m.match_type == "true_positive"]
        
        # Calculate latency statistics
        if temporal_offsets:
            temporal_offsets.sort()
            avg_latency_ms = sum(temporal_offsets) / len(temporal_offsets)
            min_latency_ms = min(temporal_offsets)
            max_latency_ms = max(temporal_offsets)
            median_latency_ms = temporal_offsets[len(temporal_offsets) // 2]
        else:
            avg_latency_ms = min_latency_ms = max_latency_ms = median_latency_ms = 0.0
        
        return GroundTruthMatchingResults(
            session_id=session_id,
            video_id=video_id,
            video_playback_start_time=video_timing.get("video_playback_start_time"),
            matches=matches,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            temporal_offsets=temporal_offsets,
            avg_latency_ms=avg_latency_ms,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            median_latency_ms=median_latency_ms,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            temporal_tolerance_ms=temporal_tolerance_ms,
            spatial_tolerance=spatial_tolerance,
            created_at=datetime.now(timezone.utc)
        )
    
    def _create_empty_results(
        self, 
        session_id: str, 
        video_id: Optional[str], 
        video_timing: Dict[str, Any]
    ) -> GroundTruthMatchingResults:
        """Create empty results when no ground truth is available"""
        return GroundTruthMatchingResults(
            session_id=session_id,
            video_id=video_id,
            video_playback_start_time=video_timing.get("video_playback_start_time"),
            matches=[],
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            temporal_offsets=[],
            avg_latency_ms=0.0,
            min_latency_ms=0.0,
            max_latency_ms=0.0,
            median_latency_ms=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            temporal_tolerance_ms=500.0,
            spatial_tolerance=0.3,
            created_at=datetime.now(timezone.utc)
        )
    
    def get_matching_results_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of matching results for API responses"""
        results = self.match_detections_to_ground_truth(session_id)
        
        return {
            "session_id": session_id,
            "video_id": results.video_id,
            "summary": {
                "total_ground_truth": results.true_positives + results.false_negatives,
                "total_detections": results.true_positives + results.false_positives,
                "matched_detections": results.true_positives,
                "precision": round(results.precision, 3),
                "recall": round(results.recall, 3),
                "f1_score": round(results.f1_score, 3)
            },
            "latency": {
                "avg_ms": round(results.avg_latency_ms, 1),
                "min_ms": round(results.min_latency_ms, 1),
                "max_ms": round(results.max_latency_ms, 1),
                "median_ms": round(results.median_latency_ms, 1)
            },
            "validation_type": "HIL_GroundTruth_Matched",
            "timestamp": results.created_at.isoformat()
        }


# Global service instance
ground_truth_matching_service = GroundTruthMatchingService()


def get_ground_truth_matching_service(db_session: Optional[Session] = None) -> GroundTruthMatchingService:
    """Get ground truth matching service instance"""
    if db_session:
        return GroundTruthMatchingService(db_session)
    return ground_truth_matching_service
