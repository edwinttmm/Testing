"""
Comprehensive Validation Models for Annotation Data Integrity
============================================================

This module provides strict Pydantic models with comprehensive validation
to prevent annotation corruption at the source. All models enforce:

1. Required field validation
2. Data type constraints
3. Range validation
4. Cross-field validation
5. Custom business logic validation

These models MUST be used for all annotation operations to prevent 
undefined boundingBox properties from corrupting the database.
"""

from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)


class VRUTypeEnum(str, Enum):
    """Strict VRU type enumeration - no undefined values allowed"""
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR = "wheelchair"
    SCOOTER = "scooter"
    ANIMAL = "animal"
    OTHER = "other"


class AnnotationStatusEnum(str, Enum):
    """Annotation validation status"""
    DRAFT = "draft"
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class StrictBoundingBox(BaseModel):
    """
    Ultra-strict bounding box model with comprehensive validation.
    
    This model prevents ALL undefined/null/invalid bounding box properties
    that cause frontend crashes. Every field is REQUIRED and validated.
    """
    
    # Core coordinates - REQUIRED, no defaults, strict validation
    x: float = Field(
        ...,  # Required - no default
        ge=0.0,  # Must be >= 0
        description="X coordinate (top-left corner) - REQUIRED, must be >= 0"
    )
    
    y: float = Field(
        ...,  # Required - no default
        ge=0.0,  # Must be >= 0
        description="Y coordinate (top-left corner) - REQUIRED, must be >= 0"
    )
    
    width: float = Field(
        ...,  # Required - no default
        gt=0.0,  # Must be > 0 (positive width)
        description="Bounding box width - REQUIRED, must be > 0"
    )
    
    height: float = Field(
        ...,  # Required - no default
        gt=0.0,  # Must be > 0 (positive height)
        description="Bounding box height - REQUIRED, must be > 0"
    )
    
    # Optional but validated fields
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Detection confidence score [0-1]"
    )
    
    label: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Object label/class name"
    )

    @validator('x', 'y', 'width', 'height', pre=True, always=True)
    def validate_numeric_fields(cls, v, field):
        """Strict validation for all numeric fields"""
        if v is None:
            raise ValueError(f"{field.name} cannot be None/null - this causes frontend crashes")
        
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                raise ValueError(f"{field.name} must be a valid number, got: {v}")
        
        if not isinstance(v, (int, float)):
            raise ValueError(f"{field.name} must be a number, got type: {type(v)}")
        
        # Check for NaN/Infinity
        if str(v).lower() in ['nan', 'inf', '-inf']:
            raise ValueError(f"{field.name} cannot be NaN or Infinity")
        
        return float(v)
    
    @validator('confidence', pre=True, always=True)
    def validate_confidence(cls, v):
        """Validate confidence score"""
        if v is None:
            return None
        
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                raise ValueError(f"Confidence must be a valid number, got: {v}")
        
        if not isinstance(v, (int, float)):
            raise ValueError(f"Confidence must be a number, got type: {type(v)}")
        
        if str(v).lower() in ['nan', 'inf', '-inf']:
            raise ValueError("Confidence cannot be NaN or Infinity")
        
        return float(v)
    
    @root_validator
    def validate_bounding_box_logic(cls, values):
        """Cross-field validation for bounding box logic"""
        x, y, width, height = values.get('x'), values.get('y'), values.get('width'), values.get('height')
        
        if all(v is not None for v in [x, y, width, height]):
            # Ensure reasonable bounds (prevent extremely large boxes)
            if width > 10000 or height > 10000:
                raise ValueError("Bounding box dimensions are unreasonably large")
            
            # Ensure box is not zero-area (already handled by gt=0 but double-check)
            if width <= 0 or height <= 0:
                raise ValueError("Bounding box must have positive width and height")
            
            # Optional: Validate aspect ratio is reasonable
            aspect_ratio = width / height
            if aspect_ratio > 50 or aspect_ratio < 0.02:  # Very wide or very tall boxes
                logger.warning(f"Unusual aspect ratio detected: {aspect_ratio}")
        
        return values
    
    def dict(self, **kwargs):
        """Override dict to ensure all required fields are present"""
        data = super().dict(**kwargs)
        
        # Ensure no None values for critical fields
        required_fields = ['x', 'y', 'width', 'height']
        for field in required_fields:
            if data.get(field) is None:
                raise ValueError(f"Required field '{field}' cannot be None in serialized data")
        
        return data


class StrictAnnotationCreate(BaseModel):
    """
    Ultra-strict annotation creation model with comprehensive validation.
    
    This model prevents all forms of data corruption by validating:
    - All required fields are present
    - All data types are correct
    - All values are within valid ranges
    - Cross-field validation rules
    - Business logic constraints
    """
    
    # Video reference - REQUIRED
    video_id: str = Field(
        ...,  # Required
        min_length=1,
        description="Video ID - REQUIRED for annotation creation"
    )
    
    # Detection tracking
    detection_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Detection ID for tracking"
    )
    
    # Temporal information - REQUIRED
    frame_number: int = Field(
        ...,  # Required
        ge=0,
        description="Frame number - REQUIRED, must be >= 0"
    )
    
    timestamp: float = Field(
        ...,  # Required
        ge=0.0,
        description="Timestamp in seconds - REQUIRED, must be >= 0"
    )
    
    end_timestamp: Optional[float] = Field(
        None,
        ge=0.0,
        description="End timestamp for temporal annotations"
    )
    
    # Classification - REQUIRED
    vru_type: VRUTypeEnum = Field(
        ...,  # Required
        description="VRU type - REQUIRED, must be valid enum value"
    )
    
    # Spatial information - REQUIRED with strict validation
    bounding_box: StrictBoundingBox = Field(
        ...,  # Required
        description="Bounding box coordinates - REQUIRED with strict validation"
    )
    
    # Quality flags with defaults
    occluded: bool = Field(
        False,
        description="Whether object is occluded"
    )
    
    truncated: bool = Field(
        False,
        description="Whether object is truncated at image boundary"
    )
    
    difficult: bool = Field(
        False,
        description="Whether detection is difficult/ambiguous"
    )
    
    # Metadata
    notes: Optional[str] = Field(
        None,
        max_length=2000,
        description="Additional notes (max 2000 characters)"
    )
    
    annotator: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Annotator identifier"
    )
    
    validated: bool = Field(
        False,
        description="Whether annotation has been validated"
    )

    @validator('video_id', pre=True, always=True)
    def validate_video_id(cls, v):
        """Strict video ID validation"""
        if not v or (isinstance(v, str) and not v.strip()):
            raise ValueError("video_id cannot be empty or whitespace")
        
        # Validate UUID format if applicable
        str_v = str(v).strip()
        try:
            # Attempt to parse as UUID to ensure valid format
            uuid.UUID(str_v)
        except ValueError:
            # If not UUID, ensure it's a reasonable string
            if len(str_v) < 1 or len(str_v) > 100:
                raise ValueError("video_id must be between 1-100 characters")
        
        return str_v
    
    @validator('frame_number', pre=True, always=True)
    def validate_frame_number(cls, v):
        """Strict frame number validation"""
        if v is None:
            raise ValueError("frame_number cannot be None")
        
        if isinstance(v, str):
            try:
                v = int(v)
            except ValueError:
                raise ValueError(f"frame_number must be a valid integer, got: {v}")
        
        if not isinstance(v, int) or v < 0:
            raise ValueError("frame_number must be a non-negative integer")
        
        return v
    
    @validator('timestamp', pre=True, always=True)
    def validate_timestamp(cls, v):
        """Strict timestamp validation"""
        if v is None:
            raise ValueError("timestamp cannot be None")
        
        if isinstance(v, str):
            try:
                v = float(v)
            except ValueError:
                raise ValueError(f"timestamp must be a valid number, got: {v}")
        
        if not isinstance(v, (int, float)) or v < 0:
            raise ValueError("timestamp must be a non-negative number")
        
        # Check for reasonable bounds (not in the far future)
        if v > 86400 * 365 * 10:  # 10 years worth of seconds
            raise ValueError("timestamp appears to be unreasonably large")
        
        return float(v)
    
    @root_validator
    def validate_annotation_logic(cls, values):
        """Cross-field validation for annotation logic"""
        timestamp = values.get('timestamp')
        end_timestamp = values.get('end_timestamp')
        
        # Validate temporal consistency
        if end_timestamp is not None and timestamp is not None:
            if end_timestamp <= timestamp:
                raise ValueError("end_timestamp must be greater than timestamp")
            
            # Ensure reasonable duration (not longer than a typical video)
            duration = end_timestamp - timestamp
            if duration > 3600:  # 1 hour
                raise ValueError("Annotation duration cannot exceed 1 hour")
        
        # Validate bounding box exists and is valid
        bounding_box = values.get('bounding_box')
        if not bounding_box:
            raise ValueError("bounding_box is required and cannot be None")
        
        return values

    class Config:
        # Use enum values instead of enum objects
        use_enum_values = True
        # Validate assignment
        validate_assignment = True
        # Allow population by field name and alias
        populate_by_name = True
        # Extra fields are forbidden
        extra = 'forbid'


class StrictAnnotationUpdate(BaseModel):
    """Strict annotation update model - all fields optional but validated when present"""
    
    detection_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100
    )
    
    frame_number: Optional[int] = Field(
        None,
        ge=0
    )
    
    timestamp: Optional[float] = Field(
        None,
        ge=0.0
    )
    
    end_timestamp: Optional[float] = Field(
        None,
        ge=0.0
    )
    
    vru_type: Optional[VRUTypeEnum] = None
    
    bounding_box: Optional[StrictBoundingBox] = None
    
    occluded: Optional[bool] = None
    truncated: Optional[bool] = None
    difficult: Optional[bool] = None
    
    notes: Optional[str] = Field(
        None,
        max_length=2000
    )
    
    annotator: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100
    )
    
    validated: Optional[bool] = None

    @root_validator
    def validate_update_logic(cls, values):
        """Validate update logic for consistency"""
        timestamp = values.get('timestamp')
        end_timestamp = values.get('end_timestamp')
        
        if timestamp is not None and end_timestamp is not None:
            if end_timestamp <= timestamp:
                raise ValueError("end_timestamp must be greater than timestamp")
        
        return values

    class Config:
        use_enum_values = True
        validate_assignment = True
        populate_by_name = True
        extra = 'forbid'


class ValidationErrorResponse(BaseModel):
    """Structured error response for validation failures"""
    
    error_type: str = Field(..., description="Type of validation error")
    field: Optional[str] = Field(None, description="Field that failed validation")
    message: str = Field(..., description="Human-readable error message")
    provided_value: Optional[Any] = Field(None, description="The invalid value that was provided")
    expected_format: Optional[str] = Field(None, description="Expected format or constraints")
    
    class Config:
        extra = 'allow'


class BulkValidationResult(BaseModel):
    """Result of bulk annotation validation"""
    
    total_submitted: int
    valid_annotations: int
    invalid_annotations: int
    validation_errors: List[ValidationErrorResponse]
    successful_ids: List[str]
    
    class Config:
        extra = 'forbid'