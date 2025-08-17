"""
Image processing utilities for ML pipeline
"""
import cv2
import numpy as np
from typing import Tuple, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

def preprocess_frame(frame: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
    """
    Preprocess frame for YOLO inference
    
    Args:
        frame: Input frame (BGR format)
        target_size: Target size (height, width)
        
    Returns:
        Preprocessed frame
    """
    try:
        # Resize with aspect ratio preservation
        h, w = frame.shape[:2]
        target_h, target_w = target_size
        
        # Calculate scaling factor to fit within target size
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize frame
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Create padded frame
        padded = np.zeros((target_h, target_w, 3), dtype=np.uint8)
        
        # Calculate padding offsets
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        
        # Place resized frame in center
        padded[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized
        
        # Convert BGR to RGB for YOLO
        rgb_frame = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        
        return rgb_frame
        
    except Exception as e:
        logger.error(f"Frame preprocessing failed: {str(e)}")
        # Return original frame if preprocessing fails
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

def postprocess_detections(detections: List[Dict], frame_shape: Tuple[int, int, int], 
                         confidence_threshold: float = 0.25) -> List[Dict]:
    """
    Post-process detection results
    
    Args:
        detections: Raw detection results
        frame_shape: Original frame shape (h, w, c)
        confidence_threshold: Minimum confidence threshold
        
    Returns:
        Filtered and processed detections
    """
    try:
        processed_detections = []
        
        for detection in detections:
            # Filter by confidence
            if detection.get('confidence', 0) < confidence_threshold:
                continue
            
            # Validate bounding box
            bbox = detection.get('bbox', [])
            if len(bbox) != 4:
                continue
            
            x1, y1, x2, y2 = bbox
            
            # Ensure valid bounding box
            if x2 <= x1 or y2 <= y1:
                continue
            
            # Clamp to frame boundaries
            h, w = frame_shape[:2]
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(x1 + 1, min(x2, w))
            y2 = max(y1 + 1, min(y2, h))
            
            # Update detection with clamped bbox
            detection['bbox'] = [x1, y1, x2, y2]
            
            # Calculate additional metrics
            detection['area'] = (x2 - x1) * (y2 - y1)
            detection['center'] = [(x1 + x2) / 2, (y1 + y2) / 2]
            
            processed_detections.append(detection)
        
        return processed_detections
        
    except Exception as e:
        logger.error(f"Detection post-processing failed: {str(e)}")
        return []

def extract_roi(frame: np.ndarray, bbox: List[float], padding: float = 0.1) -> np.ndarray:
    """
    Extract region of interest from frame
    
    Args:
        frame: Input frame
        bbox: Bounding box [x1, y1, x2, y2]
        padding: Padding factor around bbox
        
    Returns:
        Extracted ROI
    """
    try:
        x1, y1, x2, y2 = map(int, bbox)
        h, w = frame.shape[:2]
        
        # Add padding
        pad_w = int((x2 - x1) * padding)
        pad_h = int((y2 - y1) * padding)
        
        # Expand bounding box with padding
        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(w, x2 + pad_w)
        y2 = min(h, y2 + pad_h)
        
        # Extract ROI
        roi = frame[y1:y2, x1:x2]
        
        return roi
        
    except Exception as e:
        logger.error(f"ROI extraction failed: {str(e)}")
        return frame

def apply_nms(detections: List[Dict], iou_threshold: float = 0.45) -> List[Dict]:
    """
    Apply Non-Maximum Suppression to remove overlapping detections
    
    Args:
        detections: List of detection dictionaries
        iou_threshold: IoU threshold for NMS
        
    Returns:
        Filtered detections after NMS
    """
    try:
        if not detections:
            return []
        
        # Convert to format for cv2.dnn.NMSBoxes
        boxes = []
        confidences = []
        
        for detection in detections:
            bbox = detection['bbox']
            x1, y1, x2, y2 = bbox
            # Convert to [x, y, width, height] format
            boxes.append([x1, y1, x2 - x1, y2 - y1])
            confidences.append(detection['confidence'])
        
        # Apply NMS
        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.0, iou_threshold)
        
        if len(indices) > 0:
            indices = indices.flatten()
            return [detections[i] for i in indices]
        else:
            return []
            
    except Exception as e:
        logger.error(f"NMS failed: {str(e)}")
        return detections

def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """
    Calculate Intersection over Union (IoU) between two bounding boxes
    
    Args:
        box1: First bounding box [x1, y1, x2, y2]
        box2: Second bounding box [x1, y1, x2, y2]
        
    Returns:
        IoU value
    """
    try:
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
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
        
    except Exception as e:
        logger.error(f"IoU calculation failed: {str(e)}")
        return 0.0

def enhance_frame_quality(frame: np.ndarray) -> np.ndarray:
    """
    Enhance frame quality for better detection
    
    Args:
        frame: Input frame
        
    Returns:
        Enhanced frame
    """
    try:
        # Convert to LAB color space for better processing
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        
        # Convert back to BGR
        enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Apply slight gaussian blur to reduce noise
        enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0.5)
        
        return enhanced
        
    except Exception as e:
        logger.error(f"Frame enhancement failed: {str(e)}")
        return frame

def resize_maintain_aspect(frame: np.ndarray, target_size: Tuple[int, int]) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Resize frame while maintaining aspect ratio
    
    Args:
        frame: Input frame
        target_size: Target size (width, height)
        
    Returns:
        Tuple of (resized_frame, scale_info)
    """
    try:
        h, w = frame.shape[:2]
        target_w, target_h = target_size
        
        # Calculate scale factor
        scale = min(target_w / w, target_h / h)
        
        # Calculate new dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize frame
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Calculate padding
        pad_w = target_w - new_w
        pad_h = target_h - new_h
        
        # Add padding to center the image
        top = pad_h // 2
        bottom = pad_h - top
        left = pad_w // 2
        right = pad_w - left
        
        padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        
        scale_info = {
            'scale': scale,
            'pad_left': left,
            'pad_top': top,
            'original_size': (w, h),
            'target_size': target_size
        }
        
        return padded, scale_info
        
    except Exception as e:
        logger.error(f"Resize with aspect ratio failed: {str(e)}")
        return frame, {'scale': 1.0, 'pad_left': 0, 'pad_top': 0, 'original_size': frame.shape[:2][::-1], 'target_size': target_size}