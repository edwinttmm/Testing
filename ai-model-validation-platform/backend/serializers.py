"""
Comprehensive API Serialization System
=====================================

This module provides a complete solution for the snake_case/camelCase inconsistency
between backend (Python snake_case) and frontend (JavaScript camelCase).

Features:
- Automatic field name conversion using Pydantic's alias_generator
- Response models for all major entities (Project, Video, Annotation, etc.)
- Backward compatibility with snake_case clients
- Type-safe serialization with comprehensive validation
- Collection wrappers for lists and paginated responses
- Utility functions for consistent serialization

Usage:
    from serializers import ProjectResponse, VideoResponse, serialize_for_frontend
    
    # Automatic camelCase conversion
    project_data = ProjectResponse.model_validate(db_project)
    
    # Manual serialization with options
    response = serialize_for_frontend(data, include_snake_case=True)
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field
from pydantic.alias_generators import to_camel
from typing import List, Optional, Dict, Any, Union, Generic, TypeVar
from datetime import datetime
from enum import Enum
import json
from decimal import Decimal

# =============================================================================
# BASE SERIALIZER CONFIGURATION
# =============================================================================

class SerializerConfig:
    """Base configuration for all API serializers"""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Allow both camelCase and snake_case field names
        from_attributes=True,   # Allow creation from SQLAlchemy models
        use_enum_values=True,   # Serialize enums as their values
        validate_assignment=True,
        extra='forbid',         # Prevent extra fields
        str_strip_whitespace=True,
        json_encoders={
            datetime: lambda dt: dt.isoformat() if dt else None,
            Decimal: lambda d: float(d) if d else None,
        }
    )

class BaseAPISerializer(BaseModel):
    """Base class for all API response serializers"""
    model_config = SerializerConfig.model_config

# =============================================================================
# ENUMS FOR TYPE SAFETY
# =============================================================================

class ProjectStatusEnum(str, Enum):
    """Project status enumeration"""
    DRAFT = "draft"
    ACTIVE = "active" 
    TESTING = "testing"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    ARCHIVED = "archived"

class VideoStatusEnum(str, Enum):
    """Video status enumeration"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingStatusEnum(str, Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    QUEUED = "queued"

class CameraTypeEnum(str, Enum):
    """Camera type enumeration"""
    FRONT_FACING_VRU = "Front-facing VRU"
    REAR_FACING_VRU = "Rear-facing VRU"
    IN_CAB_DRIVER_BEHAVIOR = "In-Cab Driver Behavior"
    MULTI_ANGLE_SCENARIOS = "Multi-angle"

class SignalTypeEnum(str, Enum):
    """Signal type enumeration"""
    GPIO = "GPIO"
    NETWORK_PACKET = "Network Packet"
    SERIAL = "Serial"
    CAN_BUS = "CAN Bus"

class VRUTypeEnum(str, Enum):
    """VRU type enumeration"""
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
    ANIMAL = "animal"
    OTHER = "other"

class ValidationStatusEnum(str, Enum):
    """Validation status enumeration"""
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"

# =============================================================================
# CORE ENTITY SERIALIZERS
# =============================================================================

class BoundingBoxSerializer(BaseAPISerializer):
    """Bounding box coordinates serializer with camelCase conversion"""
    x: float = Field(..., description="X coordinate (left edge)", ge=0)
    y: float = Field(..., description="Y coordinate (top edge)", ge=0)
    width: float = Field(..., description="Bounding box width", gt=0)
    height: float = Field(..., description="Bounding box height", gt=0)
    confidence: Optional[float] = Field(None, description="Detection confidence", ge=0, le=1)
    
    @computed_field
    @property
    def area(self) -> float:
        """Computed area of the bounding box"""
        return self.width * self.height
    
    @computed_field
    @property 
    def center_x(self) -> float:
        """Computed center X coordinate"""
        return self.x + (self.width / 2)
    
    @computed_field
    @property
    def center_y(self) -> float:
        """Computed center Y coordinate"""
        return self.y + (self.height / 2)

class ProjectSerializer(BaseAPISerializer):
    """Project entity serializer with automatic camelCase field conversion"""
    id: str = Field(..., description="Project unique identifier")
    name: str = Field(..., description="Project name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Project description", max_length=2000)
    
    # Camera configuration - these will be converted to camelCase
    camera_model: str = Field(..., description="Camera model name")
    camera_view: CameraTypeEnum = Field(..., description="Camera view type")
    lens_type: Optional[str] = Field(None, description="Lens type")
    resolution: Optional[str] = Field(None, description="Video resolution")
    frame_rate: Optional[int] = Field(None, description="Frame rate (FPS)", gt=0)
    signal_type: SignalTypeEnum = Field(..., description="Signal type")
    
    # Metadata
    status: ProjectStatusEnum = Field(..., description="Project status")
    owner_id: str = Field(..., description="Project owner ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    # Computed fields
    video_count: Optional[int] = Field(None, description="Total number of videos")
    total_annotations: Optional[int] = Field(None, description="Total annotations count")
    average_accuracy: Optional[float] = Field(None, description="Average accuracy score")

class VideoSerializer(BaseAPISerializer):
    """Video entity serializer with comprehensive metadata"""
    id: str = Field(..., description="Video unique identifier")
    project_id: str = Field(..., description="Associated project ID")
    filename: str = Field(..., description="Video filename")
    original_name: Optional[str] = Field(None, description="Original uploaded filename")
    
    # File properties
    file_size: Optional[int] = Field(None, description="File size in bytes", ge=0)
    file_path: Optional[str] = Field(None, description="Server file path")
    url: Optional[str] = Field(None, description="Public access URL")
    
    # Video properties  
    duration: Optional[float] = Field(None, description="Duration in seconds", ge=0)
    fps: Optional[float] = Field(None, description="Frames per second", gt=0)
    resolution: Optional[str] = Field(None, description="Video resolution")
    frame_count: Optional[int] = Field(None, description="Total frame count", ge=0)
    
    # Processing status
    status: VideoStatusEnum = Field(..., description="Video processing status")
    processing_status: ProcessingStatusEnum = Field(..., description="Detailed processing status")
    ground_truth_generated: bool = Field(False, description="Ground truth generation status")
    
    # Analytics
    detection_count: Optional[int] = Field(0, description="Total detection count", ge=0)
    annotation_count: Optional[int] = Field(0, description="Total annotation count", ge=0)
    validation_score: Optional[float] = Field(None, description="Validation score", ge=0, le=1)
    
    # Timestamps (uploaded_at provided manually in responses)
    uploaded_at: Optional[datetime] = Field(None, description="Upload timestamp (mapped from created_at)") 
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")

class AnnotationSerializer(BaseAPISerializer):
    """Annotation entity serializer with validation"""
    id: str = Field(..., description="Annotation unique identifier")
    video_id: str = Field(..., description="Associated video ID")
    detection_id: Optional[str] = Field(None, description="Detection identifier")
    
    # Temporal information
    frame_number: int = Field(..., description="Frame number", ge=0)
    timestamp: float = Field(..., description="Timestamp in seconds", ge=0)
    end_timestamp: Optional[float] = Field(None, description="End timestamp", ge=0)
    
    # Classification
    vru_type: VRUTypeEnum = Field(..., description="VRU classification type")
    class_label: Optional[str] = Field(None, description="Object class label")
    
    # Spatial information
    bounding_box: BoundingBoxSerializer = Field(..., description="Bounding box coordinates")
    
    # Quality attributes
    occluded: bool = Field(False, description="Object is occluded")
    truncated: bool = Field(False, description="Object is truncated")
    difficult: bool = Field(False, description="Detection is difficult")
    
    # Validation
    validation_status: ValidationStatusEnum = Field(ValidationStatusEnum.PENDING, description="Validation status")
    validated: bool = Field(False, description="Has been validated")
    confidence: Optional[float] = Field(None, description="Annotation confidence", ge=0, le=1)
    
    # Metadata
    notes: Optional[str] = Field(None, description="Additional notes", max_length=2000)
    annotator: Optional[str] = Field(None, description="Annotator identifier")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class DetectionSerializer(BaseAPISerializer):
    """Detection entity serializer for ML inference results"""
    id: str = Field(..., description="Detection unique identifier")
    video_id: str = Field(..., description="Associated video ID")
    inference_session_id: Optional[str] = Field(None, description="ML inference session ID")
    
    # Temporal information
    frame_number: int = Field(..., description="Frame number", ge=0)
    timestamp: float = Field(..., description="Timestamp in seconds", ge=0)
    
    # Detection results
    class_id: int = Field(..., description="COCO class ID", ge=0)
    class_name: str = Field(..., description="Object class name")
    vru_type: VRUTypeEnum = Field(..., description="VRU classification")
    confidence: float = Field(..., description="Detection confidence", ge=0, le=1)
    
    # Spatial information
    bounding_box: BoundingBoxSerializer = Field(..., description="Bounding box coordinates")
    
    # Quality metrics
    detection_score: Optional[float] = Field(None, description="Raw detection score", ge=0, le=1)
    nms_score: Optional[float] = Field(None, description="NMS score", ge=0, le=1)
    tracking_id: Optional[str] = Field(None, description="Multi-object tracking ID")
    
    # Validation
    validation_status: ValidationStatusEnum = Field(ValidationStatusEnum.PENDING, description="Validation status")
    ground_truth_match_id: Optional[str] = Field(None, description="Matched ground truth annotation ID")
    iou_with_ground_truth: Optional[float] = Field(None, description="IoU with ground truth", ge=0, le=1)
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")

class GroundTruthSerializer(BaseAPISerializer):
    """Ground truth object serializer"""
    id: str = Field(..., description="Ground truth unique identifier")
    video_id: str = Field(..., description="Associated video ID")
    timestamp: float = Field(..., description="Timestamp in seconds", ge=0)
    class_label: str = Field(..., description="Object class label")
    bounding_box: Dict[str, Any] = Field(..., description="Bounding box data")
    confidence: float = Field(..., description="Confidence score", ge=0, le=1)
    
    created_at: datetime = Field(..., description="Creation timestamp")

class TestSessionSerializer(BaseAPISerializer):
    """Test session serializer"""
    id: str = Field(..., description="Test session unique identifier")
    name: str = Field(..., description="Test session name", min_length=1)
    project_id: str = Field(..., description="Associated project ID")
    video_id: str = Field(..., description="Associated video ID")
    tolerance_ms: Optional[int] = Field(100, description="Tolerance in milliseconds", ge=0)
    status: str = Field(..., description="Session status")
    
    started_at: Optional[datetime] = Field(None, description="Session start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Session completion timestamp") 
    created_at: datetime = Field(..., description="Creation timestamp")

class ValidationResultSerializer(BaseAPISerializer):
    """Validation result metrics serializer"""
    session_id: str = Field(..., description="Test session ID")
    accuracy: float = Field(..., description="Accuracy score", ge=0, le=1)
    precision: float = Field(..., description="Precision score", ge=0, le=1)
    recall: float = Field(..., description="Recall score", ge=0, le=1)
    f1_score: float = Field(..., description="F1 score", ge=0, le=1)
    
    total_detections: int = Field(..., description="Total detections", ge=0)
    true_positives: int = Field(..., description="True positives count", ge=0)
    false_positives: int = Field(..., description="False positives count", ge=0)
    false_negatives: int = Field(..., description="False negatives count", ge=0)
    
    status: str = Field(..., description="Validation status")

# =============================================================================
# COLLECTION AND PAGINATION SERIALIZERS
# =============================================================================

T = TypeVar('T')

class PaginationMetaSerializer(BaseAPISerializer):
    """Pagination metadata serializer"""
    page: int = Field(..., description="Current page number", ge=1)
    per_page: int = Field(..., description="Items per page", ge=1)
    total: int = Field(..., description="Total items count", ge=0)
    pages: int = Field(..., description="Total pages count", ge=1)
    has_next: bool = Field(..., description="Has next page")
    has_prev: bool = Field(..., description="Has previous page")

class PaginatedResponseSerializer(BaseAPISerializer, Generic[T]):
    """Generic paginated response serializer"""
    data: List[T] = Field(..., description="Response data items")
    meta: PaginationMetaSerializer = Field(..., description="Pagination metadata")
    success: bool = Field(True, description="Request success status")
    message: Optional[str] = Field(None, description="Response message")

class ListResponseSerializer(BaseAPISerializer, Generic[T]):
    """Generic list response serializer"""
    data: List[T] = Field(..., description="Response data items")
    count: int = Field(..., description="Total items count", ge=0)
    success: bool = Field(True, description="Request success status")
    message: Optional[str] = Field(None, description="Response message")

class SingleResponseSerializer(BaseAPISerializer, Generic[T]):
    """Generic single item response serializer"""
    data: T = Field(..., description="Response data")
    success: bool = Field(True, description="Request success status")
    message: Optional[str] = Field(None, description="Response message")

# =============================================================================
# SPECIALIZED RESPONSE SERIALIZERS
# =============================================================================

class VideoUploadResponseSerializer(BaseAPISerializer):
    """Video upload response with processing status"""
    id: str = Field(..., description="Video unique identifier")
    project_id: str = Field(..., description="Associated project ID")
    filename: str = Field(..., description="Video filename")
    original_name: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    file_size: int = Field(..., description="File size (alias for size)")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    
    uploaded_at: str = Field(..., description="Upload timestamp (ISO string)") 
    created_at: str = Field(..., description="Creation timestamp (ISO string)")
    
    status: VideoStatusEnum = Field(..., description="Video status")
    ground_truth_generated: bool = Field(False, description="Ground truth status")
    processing_status: ProcessingStatusEnum = Field(..., description="Processing status")
    detection_count: int = Field(0, description="Detection count", ge=0)
    
    message: str = Field(..., description="Upload result message")

class DashboardStatsSerializer(BaseAPISerializer):
    """Dashboard statistics serializer with camelCase conversion"""
    project_count: int = Field(..., description="Total projects count", ge=0)
    video_count: int = Field(..., description="Total videos count", ge=0)
    test_session_count: int = Field(..., description="Total test sessions", ge=0)
    detection_event_count: int = Field(..., description="Total detection events", ge=0)
    average_accuracy: float = Field(..., description="Average accuracy score", ge=0, le=1)
    active_tests: int = Field(..., description="Active tests count", ge=0)

class ErrorResponseSerializer(BaseAPISerializer):
    """Error response serializer"""
    success: bool = Field(False, description="Request success status")
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def serialize_for_frontend(
    data: Any,
    model_class: Optional[type] = None,
    include_snake_case: bool = False,
    wrap_response: bool = False
) -> Dict[str, Any]:
    """
    Utility function to serialize data for frontend consumption
    
    Args:
        data: Data to serialize (can be model instance, dict, or list)
        model_class: Pydantic model class to use for validation
        include_snake_case: Whether to include snake_case field names for compatibility
        wrap_response: Whether to wrap in success response format
        
    Returns:
        Serialized data with camelCase field names
    """
    if model_class and hasattr(model_class, 'model_validate'):
        # Use Pydantic model for validation and serialization
        if isinstance(data, list):
            serialized = [model_class.model_validate(item).model_dump(by_alias=True) for item in data]
        else:
            serialized = model_class.model_validate(data).model_dump(by_alias=True)
    else:
        # Convert dict keys to camelCase
        if isinstance(data, dict):
            serialized = _convert_keys_to_camel_case(data)
        elif isinstance(data, list):
            serialized = [_convert_keys_to_camel_case(item) if isinstance(item, dict) else item for item in data]
        else:
            serialized = data
    
    # Add snake_case fields for backward compatibility
    if include_snake_case and isinstance(serialized, dict):
        snake_case_fields = _add_snake_case_fields(serialized)
        serialized.update(snake_case_fields)
    
    # Wrap in response format
    if wrap_response:
        serialized = {
            "success": True,
            "data": serialized,
            "message": "Request successful"
        }
    
    return serialized

def _convert_keys_to_camel_case(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert dictionary keys from snake_case to camelCase"""
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        # Convert key to camelCase
        camel_key = to_camel(key)
        
        # Recursively convert nested dictionaries
        if isinstance(value, dict):
            result[camel_key] = _convert_keys_to_camel_case(value)
        elif isinstance(value, list):
            result[camel_key] = [
                _convert_keys_to_camel_case(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[camel_key] = value
    
    return result

def _add_snake_case_fields(camel_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add snake_case versions of camelCase fields for backward compatibility"""
    snake_fields = {}
    
    # Common field mappings
    field_mappings = {
        'projectId': 'project_id',
        'videoId': 'video_id',
        'ownerId': 'owner_id',
        'createdAt': 'created_at',
        'updatedAt': 'updated_at',
        'fileName': 'filename',  # Note: filename is already snake_case compatible
        'fileSize': 'file_size',
        'frameRate': 'frame_rate',
        'cameraModel': 'camera_model',
        'cameraView': 'camera_view',
        'lensType': 'lens_type',
        'signalType': 'signal_type',
        'boundingBox': 'bounding_box',
        'frameNumber': 'frame_number',
        'vruType': 'vru_type',
        'detectionId': 'detection_id',
        'classLabel': 'class_label',
        'validationStatus': 'validation_status',
        'processingStatus': 'processing_status',
        'groundTruthGenerated': 'ground_truth_generated',
        'detectionCount': 'detection_count'
    }
    
    for camel_key, snake_key in field_mappings.items():
        if camel_key in camel_data:
            snake_fields[snake_key] = camel_data[camel_key]
    
    return snake_fields

def create_paginated_response(
    items: List[Any],
    model_class: type,
    page: int = 1,
    per_page: int = 10,
    total: int = 0
) -> Dict[str, Any]:
    """Create a paginated response with proper serialization"""
    
    # Serialize items
    serialized_items = [
        model_class.model_validate(item).model_dump(by_alias=True)
        for item in items
    ]
    
    # Calculate pagination metadata
    pages = (total + per_page - 1) // per_page
    has_next = page < pages
    has_prev = page > 1
    
    return PaginatedResponseSerializer(
        data=serialized_items,
        meta=PaginationMetaSerializer(
            page=page,
            per_page=per_page,
            total=total,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
    ).model_dump(by_alias=True)

def create_list_response(
    items: List[Any],
    model_class: type,
    message: str = "Success"
) -> Dict[str, Any]:
    """Create a list response with proper serialization"""
    
    # Serialize items
    serialized_items = [
        model_class.model_validate(item).model_dump(by_alias=True)
        for item in items
    ]
    
    return ListResponseSerializer(
        data=serialized_items,
        count=len(serialized_items),
        message=message
    ).model_dump(by_alias=True)

def create_single_response(
    item: Any,
    model_class: type,
    message: str = "Success"
) -> Dict[str, Any]:
    """Create a single item response with proper serialization"""
    
    # Serialize item
    serialized_item = model_class.model_validate(item).model_dump(by_alias=True)
    
    return SingleResponseSerializer(
        data=serialized_item,
        message=message
    ).model_dump(by_alias=True)

def create_error_response(
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400
) -> Dict[str, Any]:
    """Create a standardized error response"""
    
    return ErrorResponseSerializer(
        error=error_type,
        message=message,
        details=details
    ).model_dump(by_alias=True)

# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

# Backward compatibility aliases
ProjectResponse = ProjectSerializer
VideoResponse = VideoSerializer
AnnotationResponse = AnnotationSerializer
DetectionResponse = DetectionSerializer
GroundTruthResponse = GroundTruthSerializer
TestSessionResponse = TestSessionSerializer
ValidationResponse = ValidationResultSerializer

if __name__ == "__main__":
    print("🔄 API Serialization System")
    print("=" * 40)
    print("✅ Automatic snake_case to camelCase conversion")
    print("✅ Comprehensive entity serializers")
    print("✅ Type-safe validation with Pydantic")
    print("✅ Backward compatibility support")
    print("✅ Collection and pagination wrappers")
    print("✅ Utility functions for consistent serialization")
    print("=" * 40)
    print("🚀 Ready to fix field name inconsistencies!")