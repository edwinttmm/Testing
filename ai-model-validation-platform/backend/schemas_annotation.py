from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class VRUTypeEnum(str, Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"  
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
    ANIMAL = "animal"
    OTHER = "other"

class BoundingBox(BaseModel):
    """Bounding box coordinates with validation"""
    x: float = Field(..., ge=0, description="X coordinate (top-left)")
    y: float = Field(..., ge=0, description="Y coordinate (top-left)")
    width: float = Field(..., gt=0, description="Width of bounding box")
    height: float = Field(..., gt=0, description="Height of bounding box")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Detection confidence")
    label: Optional[str] = Field(None, description="Object label")

class AnnotationCreate(BaseModel):
    video_id: Optional[str] = Field(None, alias="videoId", description="Video ID - will be set from URL parameter")
    detection_id: Optional[str] = Field(None, alias="detectionId")
    frame_number: int = Field(..., ge=0, alias="frameNumber")
    timestamp: float = Field(..., ge=0)
    end_timestamp: Optional[float] = Field(None, ge=0, alias="endTimestamp")
    vru_type: VRUTypeEnum = Field(..., alias="vruType")
    bounding_box: BoundingBox = Field(..., alias="boundingBox")
    occluded: bool = False
    truncated: bool = False
    difficult: bool = False
    notes: Optional[str] = None
    annotator: Optional[str] = None
    validated: bool = False
    
    class Config:
        populate_by_name = True
        
    def dict(self, **kwargs):
        """Override dict method to ensure proper serialization"""
        data = super().dict(**kwargs)
        # Convert bounding_box to dict if it's a Pydantic model
        if 'bounding_box' in data and hasattr(data['bounding_box'], 'dict'):
            data['bounding_box'] = data['bounding_box'].dict()
        return data

class AnnotationUpdate(BaseModel):
    detection_id: Optional[str] = Field(None, alias="detectionId")
    frame_number: Optional[int] = Field(None, ge=0, alias="frameNumber")
    timestamp: Optional[float] = Field(None, ge=0)
    end_timestamp: Optional[float] = Field(None, ge=0, alias="endTimestamp")
    vru_type: Optional[VRUTypeEnum] = Field(None, alias="vruType")
    bounding_box: Optional[BoundingBox] = Field(None, alias="boundingBox")
    occluded: Optional[bool] = None
    truncated: Optional[bool] = None
    difficult: Optional[bool] = None
    notes: Optional[str] = None
    annotator: Optional[str] = None
    validated: Optional[bool] = None
    
    class Config:
        populate_by_name = True

class AnnotationResponse(BaseModel):
    id: str
    video_id: str = Field(alias="videoId")
    detection_id: Optional[str] = Field(None, alias="detectionId")
    frame_number: int = Field(alias="frameNumber")
    timestamp: float
    end_timestamp: Optional[float] = Field(None, alias="endTimestamp")
    vru_type: str = Field(alias="vruType")
    bounding_box: Dict[str, Any] = Field(alias="boundingBox")
    occluded: bool
    truncated: bool
    difficult: bool
    notes: Optional[str] = None
    annotator: Optional[str] = None
    validated: bool
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True

class AnnotationSessionCreate(BaseModel):
    video_id: str = Field(alias="videoId")
    project_id: str = Field(alias="projectId")
    annotator_id: Optional[str] = Field(None, alias="annotatorId")
    
    class Config:
        populate_by_name = True

class AnnotationSessionResponse(BaseModel):
    id: str
    video_id: str = Field(alias="videoId")
    project_id: str = Field(alias="projectId")
    annotator_id: Optional[str] = Field(None, alias="annotatorId")
    status: str
    total_detections: int = Field(alias="totalDetections")
    validated_detections: int = Field(alias="validatedDetections")
    current_frame: int = Field(alias="currentFrame")
    total_frames: Optional[int] = Field(None, alias="totalFrames")
    created_at: datetime = Field(alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True

class VideoProjectLinkCreate(BaseModel):
    video_id: str = Field(alias="videoId")
    project_id: str = Field(alias="projectId")
    assignment_reason: Optional[str] = Field(None, alias="assignmentReason")
    
    class Config:
        populate_by_name = True

class VideoProjectLinkResponse(BaseModel):
    id: str
    video_id: str = Field(alias="videoId")
    project_id: str = Field(alias="projectId")
    assignment_reason: Optional[str] = Field(None, alias="assignmentReason")
    intelligent_match: bool = Field(alias="intelligentMatch")
    confidence_score: Optional[float] = Field(None, alias="confidenceScore")
    created_at: datetime = Field(alias="createdAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True

class AnnotationExportRequest(BaseModel):
    format: str = Field(default="json", pattern="^(json|coco|yolo|pascal_voc)$")
    video_ids: Optional[List[str]] = Field(None, alias="videoIds")
    include_validated_only: bool = Field(default=False, alias="includeValidatedOnly")
    
    class Config:
        populate_by_name = True

class TestResultResponse(BaseModel):
    id: str
    test_session_id: str = Field(alias="testSessionId")
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = Field(None, alias="f1Score")
    true_positives: Optional[int] = Field(None, alias="truePositives")
    false_positives: Optional[int] = Field(None, alias="falsePositives")
    false_negatives: Optional[int] = Field(None, alias="falseNegatives")
    statistical_analysis: Optional[Dict[str, Any]] = Field(None, alias="statisticalAnalysis")
    confidence_intervals: Optional[Dict[str, Any]] = Field(None, alias="confidenceIntervals")
    created_at: datetime = Field(alias="createdAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True

class DetectionComparisonResponse(BaseModel):
    id: str
    test_session_id: str = Field(alias="testSessionId")
    ground_truth_id: Optional[str] = Field(None, alias="groundTruthId")
    detection_event_id: Optional[str] = Field(None, alias="detectionEventId")
    match_type: str = Field(alias="matchType")
    iou_score: Optional[float] = Field(None, alias="iouScore")
    distance_error: Optional[float] = Field(None, alias="distanceError")
    temporal_offset: Optional[float] = Field(None, alias="temporalOffset")
    notes: Optional[str] = None
    created_at: datetime = Field(alias="createdAt")
    
    class Config:
        from_attributes = True
        populate_by_name = True