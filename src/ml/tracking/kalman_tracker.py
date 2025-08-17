"""
Kalman Filter-based tracking for VRU detection across frames
"""
import numpy as np
from typing import List, Dict, Optional, Tuple
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
import logging
import time

from ..inference.yolo_service import Detection
from ..config import ml_config

logger = logging.getLogger(__name__)

class KalmanTracker:
    """
    Kalman filter tracker for a single VRU
    """
    
    count = 0  # Global track ID counter
    
    def __init__(self, detection: Detection):
        """Initialize tracker with first detection"""
        self.track_id = KalmanTracker.count
        KalmanTracker.count += 1
        
        self.kalman = KalmanFilter(dim_x=8, dim_z=4)
        self.setup_kalman_filter()
        
        # Initialize state with detection
        bbox = detection.bbox
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        # State: [cx, cy, w, h, vx, vy, vw, vh]
        self.kalman.x = np.array([cx, cy, w, h, 0, 0, 0, 0]).reshape(8, 1)
        
        # Track management
        self.age = 0
        self.hits = 1
        self.hit_streak = 1
        self.time_since_update = 0
        self.last_detection = detection
        self.class_id = detection.class_id
        self.class_name = detection.class_name
        
        # Confidence tracking
        self.confidence_history = [detection.confidence]
        self.avg_confidence = detection.confidence
    
    def setup_kalman_filter(self):
        """Setup Kalman filter matrices"""
        dt = 1.0  # Time step
        
        # State transition matrix (constant velocity model)
        self.kalman.F = np.array([
            [1, 0, 0, 0, dt, 0, 0, 0],   # cx
            [0, 1, 0, 0, 0, dt, 0, 0],   # cy
            [0, 0, 1, 0, 0, 0, dt, 0],   # w
            [0, 0, 0, 1, 0, 0, 0, dt],   # h
            [0, 0, 0, 0, 1, 0, 0, 0],    # vx
            [0, 0, 0, 0, 0, 1, 0, 0],    # vy
            [0, 0, 0, 0, 0, 0, 1, 0],    # vw
            [0, 0, 0, 0, 0, 0, 0, 1]     # vh
        ])
        
        # Measurement matrix (we observe position and size)
        self.kalman.H = np.array([
            [1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0]
        ])
        
        # Measurement noise covariance
        self.kalman.R *= 10.0
        
        # Process noise covariance
        self.kalman.Q = Q_discrete_white_noise(dim=4, dt=dt, var=0.01, block_size=2, order_by_dim=False)
        
        # Initial covariance
        self.kalman.P *= 100.0
    
    def predict(self) -> np.ndarray:
        """Predict next state"""
        self.kalman.predict()
        self.age += 1
        self.time_since_update += 1
        return self.get_bbox()
    
    def update(self, detection: Detection):
        """Update tracker with new detection"""
        bbox = detection.bbox
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        # Update Kalman filter
        measurement = np.array([cx, cy, w, h]).reshape(4, 1)
        self.kalman.update(measurement)
        
        # Update track management
        self.hits += 1
        self.hit_streak += 1
        self.time_since_update = 0
        self.last_detection = detection
        
        # Update confidence
        self.confidence_history.append(detection.confidence)
        if len(self.confidence_history) > 10:  # Keep last 10 confidences
            self.confidence_history.pop(0)
        self.avg_confidence = np.mean(self.confidence_history)
    
    def get_bbox(self) -> List[float]:
        """Get current bounding box prediction"""
        state = self.kalman.x
        cx, cy, w, h = state[0], state[1], state[2], state[3]
        
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        
        return [float(x1[0]), float(y1[0]), float(x2[0]), float(y2[0])]
    
    def get_detection(self) -> Detection:
        """Get current detection with track ID"""
        bbox = self.get_bbox()
        detection = Detection(
            bbox=bbox,
            confidence=self.avg_confidence,
            class_id=self.class_id,
            class_name=self.class_name,
            track_id=self.track_id
        )
        return detection
    
    def is_confirmed(self) -> bool:
        """Check if track is confirmed"""
        return self.hits >= ml_config.tracking_min_hits
    
    def should_delete(self) -> bool:
        """Check if track should be deleted"""
        return self.time_since_update >= ml_config.tracking_max_age

class VRUTracker:
    """
    Multi-object tracker for VRUs using Kalman filters
    """
    
    def __init__(self):
        self.trackers: List[KalmanTracker] = []
        self.frame_count = 0
        
    def update(self, detections: List[Detection]) -> List[Detection]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of new detections
            
        Returns:
            List of tracked detections with track IDs
        """
        self.frame_count += 1
        
        # Predict new locations for existing trackers
        predicted_bboxes = []
        for tracker in self.trackers:
            predicted_bbox = tracker.predict()
            predicted_bboxes.append(predicted_bbox)
        
        # Associate detections with trackers
        matched_indices, unmatched_detections, unmatched_trackers = self._associate_detections(
            detections, predicted_bboxes
        )
        
        # Update matched trackers
        for detection_idx, tracker_idx in matched_indices:
            self.trackers[tracker_idx].update(detections[detection_idx])
        
        # Create new trackers for unmatched detections
        for detection_idx in unmatched_detections:
            new_tracker = KalmanTracker(detections[detection_idx])
            self.trackers.append(new_tracker)
        
        # Remove old trackers
        self.trackers = [t for t in self.trackers if not t.should_delete()]
        
        # Get tracked detections
        tracked_detections = []
        for tracker in self.trackers:
            if tracker.is_confirmed():
                detection = tracker.get_detection()
                tracked_detections.append(detection)
        
        return tracked_detections
    
    def _associate_detections(self, detections: List[Detection], predicted_bboxes: List[List[float]]) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Associate detections with existing trackers using Hungarian algorithm
        """
        if not detections or not predicted_bboxes:
            return [], list(range(len(detections))), list(range(len(predicted_bboxes)))
        
        # Calculate IoU matrix
        iou_matrix = np.zeros((len(detections), len(predicted_bboxes)))
        
        for d_idx, detection in enumerate(detections):
            for t_idx, predicted_bbox in enumerate(predicted_bboxes):
                # Only match same class detections
                if detection.class_id == self.trackers[t_idx].class_id:
                    iou = self._calculate_iou(detection.bbox, predicted_bbox)
                    iou_matrix[d_idx, t_idx] = iou
                else:
                    iou_matrix[d_idx, t_idx] = 0.0
        
        # Simple greedy assignment (could be replaced with Hungarian algorithm)
        matched_indices = []
        unmatched_detections = list(range(len(detections)))
        unmatched_trackers = list(range(len(predicted_bboxes)))
        
        # Find best matches above threshold
        while True:
            max_iou = 0.0
            best_detection_idx = -1
            best_tracker_idx = -1
            
            for d_idx in unmatched_detections:
                for t_idx in unmatched_trackers:
                    if iou_matrix[d_idx, t_idx] > max_iou:
                        max_iou = iou_matrix[d_idx, t_idx]
                        best_detection_idx = d_idx
                        best_tracker_idx = t_idx
            
            if max_iou >= ml_config.tracking_iou_threshold:
                matched_indices.append((best_detection_idx, best_tracker_idx))
                unmatched_detections.remove(best_detection_idx)
                unmatched_trackers.remove(best_tracker_idx)
            else:
                break
        
        return matched_indices, unmatched_detections, unmatched_trackers
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate IoU between two bounding boxes"""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        x1_int = max(x1_1, x1_2)
        y1_int = max(y1_1, y1_2)
        x2_int = min(x2_1, x2_2)
        y2_int = min(y2_1, y2_2)
        
        if x2_int <= x1_int or y2_int <= y1_int:
            return 0.0
        
        intersection = (x2_int - x1_int) * (y2_int - y1_int)
        
        # Calculate areas
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        # Calculate union
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def get_active_tracks(self) -> List[Dict]:
        """Get information about active tracks"""
        tracks = []
        for tracker in self.trackers:
            if tracker.is_confirmed():
                tracks.append({
                    'track_id': tracker.track_id,
                    'class_name': tracker.class_name,
                    'age': tracker.age,
                    'hits': tracker.hits,
                    'avg_confidence': tracker.avg_confidence,
                    'bbox': tracker.get_bbox()
                })
        return tracks
    
    def reset(self):
        """Reset tracker"""
        self.trackers.clear()
        self.frame_count = 0
        KalmanTracker.count = 0

# Global tracker instance
vru_tracker = VRUTracker()