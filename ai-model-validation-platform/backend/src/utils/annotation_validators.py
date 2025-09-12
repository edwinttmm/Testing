"""
Annotation Validation Utilities
SPARC Implementation - Comprehensive validation logic for annotations
"""

import re
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import math


class VRUType(Enum):
    """Valid VRU (Vulnerable Road User) types"""
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    WHEELCHAIR_USER = "wheelchair_user"
    SCOOTER_USER = "scooter_user"
    CHILD = "child"
    ELDERLY = "elderly"
    MOBILITY_AID_USER = "mobility_aid_user"


class AnnotationStatus(Enum):
    """Annotation validation status"""
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"


@dataclass
class BoundingBox:
    """Bounding box data structure with validation"""
    x: float
    y: float
    width: float
    height: float
    
    def __post_init__(self):
        """Validate bounding box after initialization"""
        if self.width <= 0:
            raise ValueError(f"Width must be positive, got {self.width}")
        if self.height <= 0:
            raise ValueError(f"Height must be positive, got {self.height}")
        if self.x < 0:
            raise ValueError(f"X coordinate cannot be negative, got {self.x}")
        if self.y < 0:
            raise ValueError(f"Y coordinate cannot be negative, got {self.y}")
    
    @property
    def area(self) -> float:
        """Calculate bounding box area"""
        return self.width * self.height
    
    @property
    def center(self) -> Tuple[float, float]:
        """Calculate bounding box center point"""
        return (self.x + self.width / 2, self.y + self.height / 2)
    
    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio (width/height)"""
        return self.width / self.height
    
    def contains_point(self, x: float, y: float) -> bool:
        """Check if point is within bounding box"""
        return (self.x <= x <= self.x + self.width and 
                self.y <= y <= self.y + self.height)
    
    def intersects(self, other: 'BoundingBox') -> bool:
        """Check if this bounding box intersects with another"""
        return not (self.x + self.width < other.x or 
                   other.x + other.width < self.x or
                   self.y + self.height < other.y or
                   other.y + other.height < self.y)
    
    def intersection_area(self, other: 'BoundingBox') -> float:
        """Calculate intersection area with another bounding box"""
        if not self.intersects(other):
            return 0.0
            
        x_left = max(self.x, other.x)
        y_top = max(self.y, other.y)
        x_right = min(self.x + self.width, other.x + other.width)
        y_bottom = min(self.y + self.height, other.y + other.height)
        
        return (x_right - x_left) * (y_bottom - y_top)
    
    def iou(self, other: 'BoundingBox') -> float:
        """Calculate Intersection over Union (IoU) with another bounding box"""
        intersection = self.intersection_area(other)
        union = self.area + other.area - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary format"""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BoundingBox':
        """Create BoundingBox from dictionary"""
        return cls(
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data["height"])
        )


@dataclass
class ValidationResult:
    """Result of annotation validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    
    def add_error(self, error: str):
        """Add validation error"""
        self.is_valid = False
        self.errors.append(error)
    
    def add_warning(self, warning: str):
        """Add validation warning"""
        self.warnings.append(warning)
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata"""
        self.metadata[key] = value


class AnnotationValidator:
    """Comprehensive annotation validation system"""
    
    def __init__(self):
        self.valid_vru_types = {vru.value for vru in VRUType}
        self.detection_id_pattern = re.compile(r'^DET_[A-Z_]+_\d{4,}$')
        
        # Validation thresholds
        self.min_bbox_area = 100  # Minimum bounding box area in pixels
        self.max_bbox_area_ratio = 0.8  # Maximum ratio of image area
        self.min_aspect_ratio = 0.1  # Minimum width/height ratio
        self.max_aspect_ratio = 10.0  # Maximum width/height ratio
    
    def validate_annotation(self, annotation_data: Dict[str, Any], 
                          video_metadata: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Comprehensive annotation validation
        
        Args:
            annotation_data: Dictionary containing annotation data
            video_metadata: Optional video metadata for context validation
            
        Returns:
            ValidationResult with validation status and details
        """
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            metadata={}
        )
        
        # Validate required fields
        self._validate_required_fields(annotation_data, result)
        
        # Validate VRU type
        self._validate_vru_type(annotation_data, result)
        
        # Validate detection ID format
        self._validate_detection_id(annotation_data, result)
        
        # Validate temporal data
        self._validate_temporal_data(annotation_data, video_metadata, result)
        
        # Validate bounding box
        self._validate_bounding_box(annotation_data, video_metadata, result)
        
        # Validate frame number consistency
        self._validate_frame_consistency(annotation_data, video_metadata, result)
        
        # Quality checks
        self._quality_checks(annotation_data, result)
        
        return result
    
    def _validate_required_fields(self, data: Dict[str, Any], result: ValidationResult):
        """Validate required annotation fields"""
        required_fields = [
            "video_id", "frame_number", "timestamp", "vru_type", "bounding_box"
        ]
        
        for field in required_fields:
            if field not in data or data[field] is None:
                result.add_error(f"Missing required field: {field}")
                continue
            
            if field in ["video_id"] and not isinstance(data[field], str):
                result.add_error(f"Field {field} must be a string")
            
            if field in ["frame_number"] and not isinstance(data[field], int):
                result.add_error(f"Field {field} must be an integer")
            
            if field in ["timestamp"] and not isinstance(data[field], (int, float)):
                result.add_error(f"Field {field} must be a number")
    
    def _validate_vru_type(self, data: Dict[str, Any], result: ValidationResult):
        """Validate VRU type"""
        vru_type = data.get("vru_type")
        if vru_type and vru_type not in self.valid_vru_types:
            result.add_error(f"Invalid VRU type: {vru_type}. Valid types: {list(self.valid_vru_types)}")
        
        result.add_metadata("vru_type_valid", vru_type in self.valid_vru_types)
    
    def _validate_detection_id(self, data: Dict[str, Any], result: ValidationResult):
        """Validate detection ID format"""
        detection_id = data.get("detection_id")
        if detection_id:
            if not self.detection_id_pattern.match(detection_id):
                result.add_error(f"Invalid detection ID format: {detection_id}. Expected format: DET_TYPE_NNNN")
            else:
                result.add_metadata("detection_id_format_valid", True)
    
    def _validate_temporal_data(self, data: Dict[str, Any], 
                              video_metadata: Optional[Dict[str, Any]], 
                              result: ValidationResult):
        """Validate temporal consistency"""
        timestamp = data.get("timestamp")
        end_timestamp = data.get("end_timestamp")
        
        if video_metadata and timestamp is not None:
            video_duration = video_metadata.get("duration")
            if video_duration and timestamp > video_duration:
                result.add_error(f"Timestamp {timestamp}s exceeds video duration {video_duration}s")
            
            if timestamp < 0:
                result.add_error(f"Timestamp cannot be negative: {timestamp}")
        
        if end_timestamp is not None and timestamp is not None:
            if end_timestamp <= timestamp:
                result.add_error(f"End timestamp {end_timestamp} must be greater than start timestamp {timestamp}")
        
        result.add_metadata("temporal_validation_performed", True)
    
    def _validate_bounding_box(self, data: Dict[str, Any], 
                             video_metadata: Optional[Dict[str, Any]], 
                             result: ValidationResult):
        """Validate bounding box geometry and constraints"""
        bbox_data = data.get("bounding_box")
        if not bbox_data:
            result.add_error("Missing bounding box data")
            return
        
        try:
            bbox = BoundingBox.from_dict(bbox_data)
        except (ValueError, KeyError, TypeError) as e:
            result.add_error(f"Invalid bounding box format: {str(e)}")
            return
        
        # Area validation
        if bbox.area < self.min_bbox_area:
            result.add_warning(f"Bounding box area {bbox.area:.1f} is very small (minimum recommended: {self.min_bbox_area})")
        
        # Aspect ratio validation
        aspect_ratio = bbox.aspect_ratio
        if aspect_ratio < self.min_aspect_ratio or aspect_ratio > self.max_aspect_ratio:
            result.add_warning(f"Unusual aspect ratio {aspect_ratio:.2f} (expected range: {self.min_aspect_ratio}-{self.max_aspect_ratio})")
        
        # Image bounds validation
        if video_metadata:
            resolution = video_metadata.get("resolution")
            if resolution:
                try:
                    width, height = map(int, resolution.split("x"))
                    
                    if bbox.x + bbox.width > width:
                        result.add_error(f"Bounding box extends beyond image width ({width}px)")
                    
                    if bbox.y + bbox.height > height:
                        result.add_error(f"Bounding box extends beyond image height ({height}px)")
                    
                    # Area ratio validation
                    image_area = width * height
                    bbox_ratio = bbox.area / image_area
                    if bbox_ratio > self.max_bbox_area_ratio:
                        result.add_warning(f"Bounding box covers {bbox_ratio:.1%} of image (unusually large)")
                    
                    result.add_metadata("image_bounds_checked", True)
                    result.add_metadata("bbox_area_ratio", bbox_ratio)
                    
                except ValueError:
                    result.add_warning(f"Could not parse video resolution: {resolution}")
        
        result.add_metadata("bbox_area", bbox.area)
        result.add_metadata("bbox_aspect_ratio", aspect_ratio)
        result.add_metadata("bbox_center", bbox.center)
    
    def _validate_frame_consistency(self, data: Dict[str, Any], 
                                  video_metadata: Optional[Dict[str, Any]], 
                                  result: ValidationResult):
        """Validate frame number consistency with timestamp"""
        frame_number = data.get("frame_number")
        timestamp = data.get("timestamp")
        
        if frame_number is not None and timestamp is not None and video_metadata:
            fps = video_metadata.get("fps")
            if fps:
                expected_timestamp = frame_number / fps
                timestamp_diff = abs(timestamp - expected_timestamp)
                
                # Allow for small rounding errors (within 1 frame)
                tolerance = 1.0 / fps
                
                if timestamp_diff > tolerance:
                    result.add_warning(
                        f"Frame {frame_number} timestamp {timestamp}s doesn't match expected "
                        f"{expected_timestamp:.3f}s (diff: {timestamp_diff:.3f}s)"
                    )
                
                result.add_metadata("frame_timestamp_consistency", timestamp_diff <= tolerance)
                result.add_metadata("timestamp_difference", timestamp_diff)
    
    def _quality_checks(self, data: Dict[str, Any], result: ValidationResult):
        """Additional quality validation checks"""
        
        # Check for annotator information
        if not data.get("annotator"):
            result.add_warning("No annotator specified - tracking recommended for quality control")
        
        # Check for annotation notes on difficult cases
        is_difficult = data.get("difficult", False)
        is_occluded = data.get("occluded", False)
        is_truncated = data.get("truncated", False)
        has_notes = bool(data.get("notes", "").strip())
        
        if (is_difficult or is_occluded or is_truncated) and not has_notes:
            result.add_warning("Difficult/occluded/truncated annotations should include explanatory notes")
        
        # Metadata for quality tracking
        quality_flags = {
            "has_annotator": bool(data.get("annotator")),
            "has_notes": has_notes,
            "is_difficult": is_difficult,
            "is_occluded": is_occluded,
            "is_truncated": is_truncated,
            "quality_score": self._calculate_quality_score(data)
        }
        
        result.metadata.update(quality_flags)
    
    def _calculate_quality_score(self, data: Dict[str, Any]) -> float:
        """Calculate annotation quality score (0-1)"""
        score = 1.0
        
        # Deduct for missing optional but recommended fields
        if not data.get("annotator"):
            score -= 0.1
        
        if not data.get("notes") and (data.get("difficult") or data.get("occluded")):
            score -= 0.1
        
        # Deduct for quality issues
        if data.get("difficult", False):
            score -= 0.05
        if data.get("occluded", False):
            score -= 0.05
        if data.get("truncated", False):
            score -= 0.05
        
        return max(0.0, score)


class GeometricValidator:
    """Geometric validation utilities for annotations"""
    
    @staticmethod
    def calculate_overlap_matrix(annotations: List[Dict[str, Any]]) -> List[List[float]]:
        """Calculate IoU matrix for all annotation pairs"""
        n = len(annotations)
        matrix = [[0.0] * n for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                try:
                    bbox_i = BoundingBox.from_dict(annotations[i]["bounding_box"])
                    bbox_j = BoundingBox.from_dict(annotations[j]["bounding_box"])
                    iou = bbox_i.iou(bbox_j)
                    matrix[i][j] = iou
                    matrix[j][i] = iou
                except (ValueError, KeyError):
                    continue
        
        return matrix
    
    @staticmethod
    def find_overlapping_annotations(annotations: List[Dict[str, Any]], 
                                   threshold: float = 0.3) -> List[Tuple[int, int, float]]:
        """Find pairs of annotations with high overlap"""
        overlap_matrix = GeometricValidator.calculate_overlap_matrix(annotations)
        overlaps = []
        
        for i in range(len(overlap_matrix)):
            for j in range(i + 1, len(overlap_matrix[i])):
                if overlap_matrix[i][j] > threshold:
                    overlaps.append((i, j, overlap_matrix[i][j]))
        
        return overlaps
    
    @staticmethod
    def validate_annotation_density(annotations: List[Dict[str, Any]], 
                                  image_width: int, 
                                  image_height: int) -> Dict[str, Any]:
        """Validate annotation density and distribution"""
        if not annotations:
            return {"density": 0.0, "distribution": "empty"}
        
        # Calculate total annotated area
        total_area = 0
        centers = []
        
        for ann in annotations:
            try:
                bbox = BoundingBox.from_dict(ann["bounding_box"])
                total_area += bbox.area
                centers.append(bbox.center)
            except (ValueError, KeyError):
                continue
        
        image_area = image_width * image_height
        density = total_area / image_area
        
        # Analyze distribution
        if len(centers) > 1:
            # Calculate center of mass and spread
            center_x = sum(c[0] for c in centers) / len(centers)
            center_y = sum(c[1] for c in centers) / len(centers)
            
            spread = sum(math.sqrt((c[0] - center_x)**2 + (c[1] - center_y)**2) 
                        for c in centers) / len(centers)
            
            # Normalize spread by image diagonal
            image_diagonal = math.sqrt(image_width**2 + image_height**2)
            normalized_spread = spread / image_diagonal
            
            if normalized_spread < 0.1:
                distribution = "clustered"
            elif normalized_spread > 0.4:
                distribution = "dispersed"
            else:
                distribution = "balanced"
        else:
            distribution = "single"
        
        return {
            "density": density,
            "distribution": distribution,
            "total_annotations": len(annotations),
            "total_area_ratio": density,
            "annotation_centers": centers
        }


class TemporalValidator:
    """Temporal validation utilities for annotation sequences"""
    
    @staticmethod
    def validate_temporal_consistency(annotations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate temporal consistency across annotation sequence"""
        if len(annotations) < 2:
            return {"status": "insufficient_data", "consistency": 1.0}
        
        # Sort by timestamp
        sorted_annotations = sorted(annotations, key=lambda x: x.get("timestamp", 0))
        
        issues = []
        frame_gaps = []
        timestamp_gaps = []
        
        for i in range(1, len(sorted_annotations)):
            prev_ann = sorted_annotations[i-1]
            curr_ann = sorted_annotations[i]
            
            prev_frame = prev_ann.get("frame_number", 0)
            curr_frame = curr_ann.get("frame_number", 0)
            prev_time = prev_ann.get("timestamp", 0.0)
            curr_time = curr_ann.get("timestamp", 0.0)
            
            frame_gap = curr_frame - prev_frame
            time_gap = curr_time - prev_time
            
            frame_gaps.append(frame_gap)
            timestamp_gaps.append(time_gap)
            
            # Check for temporal anomalies
            if frame_gap < 0:
                issues.append(f"Frame order inconsistency at position {i}")
            
            if time_gap < 0:
                issues.append(f"Timestamp order inconsistency at position {i}")
            
            if frame_gap > 100:  # Large frame gap
                issues.append(f"Large frame gap ({frame_gap}) at position {i}")
        
        # Calculate consistency metrics
        if frame_gaps:
            avg_frame_gap = sum(frame_gaps) / len(frame_gaps)
            frame_gap_variance = sum((gap - avg_frame_gap)**2 for gap in frame_gaps) / len(frame_gaps)
        else:
            avg_frame_gap = 0
            frame_gap_variance = 0
        
        consistency_score = max(0.0, 1.0 - len(issues) / len(annotations))
        
        return {
            "status": "analyzed",
            "consistency": consistency_score,
            "issues": issues,
            "average_frame_gap": avg_frame_gap,
            "frame_gap_variance": frame_gap_variance,
            "temporal_span": sorted_annotations[-1].get("timestamp", 0) - sorted_annotations[0].get("timestamp", 0),
            "annotation_count": len(annotations)
        }