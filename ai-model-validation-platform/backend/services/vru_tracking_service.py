"""
VRU Tracking Service for Persistent ID Assignment
Implements tracking algorithm to maintain consistent VRU IDs across video frames
"""

import logging
import uuid
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)

@dataclass
class VRUTrack:
    """Represents a tracked VRU with persistent ID"""
    vru_id: str
    vru_type: str
    last_frame: int
    last_bbox: Dict[str, float]
    last_confidence: float
    track_history: List[Tuple[int, Dict[str, float]]]  # (frame, bbox) history
    frames_since_detection: int = 0
    max_gap_frames: int = 30  # Maximum frames without detection before track dies

class VRUTrackingService:
    """
    PRD Module 1.2: Persistent VRU ID tracking across video frames
    Implements simple IoU-based tracking with temporal consistency
    """
    
    def __init__(self):
        self.video_tracks: Dict[str, Dict[str, VRUTrack]] = {}  # video_id -> {track_id -> VRUTrack}
        self.track_counter: Dict[str, int] = {}  # video_id -> counter
        
        # Tracking parameters
        self.iou_threshold = 0.3  # Minimum IoU for track association
        self.max_distance_threshold = 100  # Maximum pixel distance for track association
        self.confidence_weight = 0.3  # Weight for confidence in track scoring
    
    def initialize_video_tracking(self, video_id: str):
        """Initialize tracking for a new video"""
        self.video_tracks[video_id] = {}
        self.track_counter[video_id] = 0
        logger.info(f"Initialized VRU tracking for video {video_id}")
    
    def track_vru(
        self, 
        video_id: str, 
        frame_number: int, 
        bbox: Dict[str, float], 
        vru_type: str, 
        confidence: float
    ) -> str:
        """
        Track VRU and return persistent ID
        
        Args:
            video_id: Video identifier
            frame_number: Current frame number
            bbox: Bounding box {"x": x, "y": y, "width": w, "height": h}
            vru_type: VRU type (pedestrian, cyclist, etc.)
            confidence: Detection confidence
            
        Returns:
            Persistent VRU ID string
        """
        if video_id not in self.video_tracks:
            self.initialize_video_tracking(video_id)
        
        tracks = self.video_tracks[video_id]
        
        # Update existing tracks (increment frames since detection)
        for track in tracks.values():
            track.frames_since_detection += 1
        
        # Find best matching track
        best_track_id = self._find_best_matching_track(
            tracks, bbox, vru_type, confidence, frame_number
        )
        
        if best_track_id:
            # Update existing track
            track = tracks[best_track_id]
            track.last_frame = frame_number
            track.last_bbox = bbox.copy()
            track.last_confidence = confidence
            track.frames_since_detection = 0
            track.track_history.append((frame_number, bbox.copy()))
            
            # Limit history size
            if len(track.track_history) > 50:
                track.track_history = track.track_history[-50:]
            
            logger.debug(f"Updated track {best_track_id} for frame {frame_number}")
            return best_track_id
        
        else:
            # Create new track
            new_track_id = self._generate_vru_id(video_id, vru_type)
            new_track = VRUTrack(
                vru_id=new_track_id,
                vru_type=vru_type,
                last_frame=frame_number,
                last_bbox=bbox.copy(),
                last_confidence=confidence,
                track_history=[(frame_number, bbox.copy())],
                frames_since_detection=0
            )
            
            tracks[new_track_id] = new_track
            
            logger.debug(f"Created new track {new_track_id} for frame {frame_number}")
            return new_track_id
    
    def _find_best_matching_track(
        self, 
        tracks: Dict[str, VRUTrack], 
        bbox: Dict[str, float], 
        vru_type: str, 
        confidence: float,
        frame_number: int
    ) -> Optional[str]:
        """Find the best matching existing track for current detection"""
        
        best_track_id = None
        best_score = 0.0
        
        for track_id, track in tracks.items():
            # Skip tracks that have been missing too long
            if track.frames_since_detection > track.max_gap_frames:
                continue
            
            # Only match same VRU type
            if track.vru_type != vru_type:
                continue
            
            # Skip tracks too far in the past
            if frame_number - track.last_frame > track.max_gap_frames:
                continue
            
            # Calculate IoU
            iou = self._calculate_iou(bbox, track.last_bbox)
            
            # Calculate center distance
            distance = self._calculate_center_distance(bbox, track.last_bbox)
            
            # Calculate temporal consistency score
            temporal_score = self._calculate_temporal_score(track, frame_number)
            
            # Combined score
            score = (
                iou * 0.5 +  # IoU weight
                (1.0 / (1.0 + distance / 100.0)) * 0.3 +  # Distance weight (normalized)
                temporal_score * 0.1 +  # Temporal consistency
                confidence * self.confidence_weight * 0.1  # Confidence weight
            )
            
            # Must meet minimum IoU threshold
            if iou >= self.iou_threshold and score > best_score:
                best_score = score
                best_track_id = track_id
        
        return best_track_id
    
    def _calculate_iou(self, bbox1: Dict[str, float], bbox2: Dict[str, float]) -> float:
        """Calculate Intersection over Union (IoU) between two bounding boxes"""
        try:
            # Convert to (x1, y1, x2, y2) format
            x1_1, y1_1 = bbox1["x"], bbox1["y"]
            x2_1, y2_1 = x1_1 + bbox1["width"], y1_1 + bbox1["height"]
            
            x1_2, y1_2 = bbox2["x"], bbox2["y"]
            x2_2, y2_2 = x1_2 + bbox2["width"], y1_2 + bbox2["height"]
            
            # Calculate intersection
            x1_i = max(x1_1, x1_2)
            y1_i = max(y1_1, y1_2)
            x2_i = min(x2_1, x2_2)
            y2_i = min(y2_1, y2_2)
            
            if x2_i <= x1_i or y2_i <= y1_i:
                return 0.0
            
            intersection = (x2_i - x1_i) * (y2_i - y1_i)
            
            # Calculate union
            area1 = bbox1["width"] * bbox1["height"]
            area2 = bbox2["width"] * bbox2["height"]
            union = area1 + area2 - intersection
            
            return intersection / union if union > 0 else 0.0
            
        except (KeyError, ZeroDivisionError):
            return 0.0
    
    def _calculate_center_distance(self, bbox1: Dict[str, float], bbox2: Dict[str, float]) -> float:
        """Calculate Euclidean distance between bounding box centers"""
        try:
            center1_x = bbox1["x"] + bbox1["width"] / 2
            center1_y = bbox1["y"] + bbox1["height"] / 2
            
            center2_x = bbox2["x"] + bbox2["width"] / 2
            center2_y = bbox2["y"] + bbox2["height"] / 2
            
            return math.sqrt((center1_x - center2_x)**2 + (center1_y - center2_y)**2)
            
        except KeyError:
            return float('inf')
    
    def _calculate_temporal_score(self, track: VRUTrack, current_frame: int) -> float:
        """Calculate temporal consistency score based on track history"""
        if len(track.track_history) < 2:
            return 0.5  # Neutral score for new tracks
        
        # Frame gap penalty
        frame_gap = current_frame - track.last_frame
        gap_penalty = max(0.0, 1.0 - (frame_gap / track.max_gap_frames))
        
        # Track stability bonus (longer tracks are more stable)
        stability_bonus = min(1.0, len(track.track_history) / 10.0)
        
        return (gap_penalty + stability_bonus) / 2.0
    
    def _generate_vru_id(self, video_id: str, vru_type: str) -> str:
        """Generate unique VRU ID with meaningful prefix"""
        self.track_counter[video_id] += 1
        counter = self.track_counter[video_id]
        
        # Type prefix mapping
        type_prefix = {
            "pedestrian": "PED",
            "cyclist": "CYC",
            "motorcyclist": "MOT",
            "wheelchair": "WHE",
            "scooter": "SCO"
        }.get(vru_type, "VRU")
        
        return f"{type_prefix}_{counter:04d}"
    
    def cleanup_dead_tracks(self, video_id: str):
        """Remove tracks that haven't been detected for too long"""
        if video_id not in self.video_tracks:
            return
        
        tracks = self.video_tracks[video_id]
        dead_tracks = []
        
        for track_id, track in tracks.items():
            if track.frames_since_detection > track.max_gap_frames:
                dead_tracks.append(track_id)
        
        for track_id in dead_tracks:
            del tracks[track_id]
            logger.debug(f"Removed dead track {track_id}")
    
    def get_track_statistics(self, video_id: str) -> Dict[str, any]:
        """Get tracking statistics for a video"""
        if video_id not in self.video_tracks:
            return {"error": "Video not found"}
        
        tracks = self.video_tracks[video_id]
        
        # Count by VRU type
        type_counts = {}
        total_detections = 0
        
        for track in tracks.values():
            vru_type = track.vru_type
            type_counts[vru_type] = type_counts.get(vru_type, 0) + 1
            total_detections += len(track.track_history)
        
        return {
            "total_tracks": len(tracks),
            "total_detections": total_detections,
            "tracks_by_type": type_counts,
            "active_tracks": len([t for t in tracks.values() 
                                if t.frames_since_detection <= t.max_gap_frames])
        }