from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

# Import CamelCaseModel from schemas for consistency
def snake_to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    
    # Split by underscores and join, capitalizing all but the first word
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

class CamelCaseModel(BaseModel):
    """Base model that automatically converts snake_case fields to camelCase aliases for API serialization"""
    
    model_config = ConfigDict(
        # Generate camelCase aliases for all fields
        alias_generator=snake_to_camel,
        # Allow both snake_case and camelCase field names when parsing
        populate_by_name=True,
        # Enable serialization by alias (camelCase for frontend)
        by_alias=True,
        # Enable SQLAlchemy integration
        from_attributes=True
    )

class VRUTypeEnum(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"  
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
    ANIMAL = "animal"
    OTHER = "other"

class BoundingBox(CamelCaseModel):
    """Bounding box coordinates with validation"""
    x: float = Field(..., ge=0, description="X coordinate (top-left)")
    y: float = Field(..., ge=0, description="Y coordinate (top-left)")
    width: float = Field(..., gt=0, description="Width of bounding box")
    height: float = Field(..., gt=0, description="Height of bounding box")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Detection confidence")
    label: Optional[str] = Field(None, description="Object label")
    # Computed fields for frontend compatibility
    area: Optional[float] = Field(None, description="Computed area")
    center_x: Optional[float] = Field(None, description="Center X coordinate")
    center_y: Optional[float] = Field(None, description="Center Y coordinate")

class AnnotationCreate(CamelCaseModel):
    video_id: Optional[str] = Field(None, description="Video ID - will be set from URL parameter")
    detection_id: Optional[str] = None
    frame_number: int = Field(..., ge=0)
    timestamp: float = Field(..., ge=0)
    end_timestamp: Optional[float] = Field(None, ge=0)
    vru_type: VRUTypeEnum
    class_label: Optional[str] = None
    bounding_box: BoundingBox
    occluded: bool = False
    truncated: bool = False
    difficult: bool = False
    validation_status: str = Field(default="pending")
    validated: bool = False
    confidence: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = None
    annotator: Optional[str] = None

class AnnotationUpdate(CamelCaseModel):
    detection_id: Optional[str] = None
    frame_number: Optional[int] = Field(None, ge=0)
    timestamp: Optional[float] = Field(None, ge=0)
    end_timestamp: Optional[float] = Field(None, ge=0)
    vru_type: Optional[VRUTypeEnum] = None
    class_label: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    occluded: Optional[bool] = None
    truncated: Optional[bool] = None
    difficult: Optional[bool] = None
    validation_status: Optional[str] = None
    validated: Optional[bool] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = None
    annotator: Optional[str] = None

class AnnotationResponse(CamelCaseModel):
    id: str
    video_id: str
    detection_id: Optional[str] = None
    frame_number: int
    timestamp: float
    end_timestamp: Optional[float] = None
    vru_type: VRUTypeEnum
    class_label: Optional[str] = None
    bounding_box: BoundingBox
    occluded: bool
    truncated: bool
    difficult: bool
    validation_status: str = Field(default="pending")
    validated: bool
    confidence: Optional[float] = None
    notes: Optional[str] = None
    annotator: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class AnnotationSessionCreate(CamelCaseModel):
    video_id: str
    project_id: str
    annotator_id: Optional[str] = None

class AnnotationSessionResponse(CamelCaseModel):
    id: str
    video_id: str
    project_id: str
    annotator_id: Optional[str] = None
    status: str  # 'active' | 'paused' | 'completed' | 'cancelled'
    total_detections: int
    validated_detections: int
    current_frame: int
    total_frames: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

class VideoProjectLinkCreate(CamelCaseModel):
    video_id: str
    project_id: str
    assignment_reason: Optional[str] = None
    intelligent_match: bool = True

class VideoProjectLinkResponse(CamelCaseModel):
    id: str
    video_id: str
    project_id: str
    assignment_reason: Optional[str] = None
    intelligent_match: bool
    confidence_score: Optional[float] = None
    created_at: datetime

class AnnotationExportRequest(CamelCaseModel):
    format: str = Field(default="json", pattern="^(json|coco|yolo|pascal_voc)$")
    video_ids: Optional[List[str]] = None
    include_validated_only: bool = Field(default=False)

class TestResultResponse(CamelCaseModel):
    id: str
    test_session_id: str
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    true_positives: Optional[int] = None
    false_positives: Optional[int] = None
    false_negatives: Optional[int] = None
    statistical_analysis: Optional[Dict[str, Any]] = None
    confidence_intervals: Optional[Dict[str, Any]] = None
    created_at: datetime

class DetectionComparisonResponse(CamelCaseModel):
    id: str
    test_session_id: str
    ground_truth_id: Optional[str] = None
    detection_event_id: Optional[str] = None
    match_type: str  # 'true_positive' | 'false_positive' | 'false_negative' | 'true_negative'
    iou_score: Optional[float] = None
    distance_error: Optional[float] = None
    temporal_offset: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime

class VideoAnnotationStats(CamelCaseModel):
    """Statistics about video annotations"""
    video_id: str
    total_annotations: int
    validated_annotations: int
    validation_percentage: float
    vru_type_distribution: Dict[str, int]
    annotation_density: float