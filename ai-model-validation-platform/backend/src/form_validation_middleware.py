"""
Comprehensive Form Validation Middleware
Root cause fixes for validation issues and security vulnerabilities
"""

from fastapi import HTTPException, status, Request
from pydantic import BaseModel, ValidationError, validator, Field
from typing import Any, Dict, List, Optional, Union, Callable
import re
import logging
import bleach
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    invalid_value: Any = None

class EnhancedProjectCreate(BaseModel):
    """
    Enhanced project creation schema with comprehensive validation
    Fixes: Empty project names, invalid inputs, security vulnerabilities
    """
    name: str = Field(..., min_length=1, max_length=255, description="Project name is required")
    description: Optional[str] = Field(None, max_length=2000, description="Project description")
    camera_model: str = Field(..., min_length=1, max_length=255, alias="cameraModel")
    camera_view: str = Field(..., alias="cameraView")
    lens_type: Optional[str] = Field(None, max_length=100, alias="lensType")
    resolution: Optional[str] = Field(None, max_length=50)
    frame_rate: Optional[int] = Field(None, ge=1, le=240, alias="frameRate")
    signal_type: str = Field(..., alias="signalType")
    
    class Config:
        populate_by_name = True
        str_strip_whitespace = True  # Automatically strip whitespace
    
    @validator('name')
    def validate_name(cls, v):
        """
        Root cause fix: Reject empty project names and sanitize input
        """
        if not v or not v.strip():
            raise ValueError("Project name cannot be empty or contain only whitespace")
        
        # Sanitize HTML and potentially dangerous characters
        sanitized = bleach.clean(v.strip(), tags=[], strip=True)
        if not sanitized:
            raise ValueError("Project name contains invalid characters")
        
        # Check for SQL injection patterns
        sql_patterns = ['--', ';', 'DROP', 'DELETE', 'INSERT', 'UPDATE', 'SELECT', 'UNION']
        for pattern in sql_patterns:
            if pattern.lower() in sanitized.lower():
                raise ValueError("Project name contains potentially dangerous content")
        
        # Validate character set (alphanumeric, spaces, hyphens, underscores only)
        if not re.match(r'^[a-zA-Z0-9\s\-_\.]+$', sanitized):
            raise ValueError("Project name can only contain letters, numbers, spaces, hyphens, underscores, and periods")
        
        return sanitized
    
    @validator('description')
    def validate_description(cls, v):
        """Sanitize and validate description"""
        if v:
            # Sanitize HTML but allow basic formatting
            allowed_tags = ['b', 'i', 'u', 'br', 'p']
            sanitized = bleach.clean(v.strip(), tags=allowed_tags, strip=True)
            return sanitized if sanitized else None
        return v
    
    @validator('camera_model')
    def validate_camera_model(cls, v):
        """Validate camera model"""
        if not v or not v.strip():
            raise ValueError("Camera model is required")
        
        sanitized = bleach.clean(v.strip(), tags=[], strip=True)
        if not sanitized:
            raise ValueError("Camera model contains invalid characters")
        
        # Basic validation - should contain alphanumeric characters and common symbols
        if not re.match(r'^[a-zA-Z0-9\s\-_\.\/]+$', sanitized):
            raise ValueError("Camera model contains invalid characters")
        
        return sanitized
    
    @validator('camera_view')
    def validate_camera_view(cls, v):
        """Validate camera view"""
        allowed_views = [
            "Front-facing VRU",
            "Rear-facing VRU", 
            "In-Cab Driver Behavior",
            "Multi-angle"
        ]
        
        if v not in allowed_views:
            raise ValueError(f"Camera view must be one of: {', '.join(allowed_views)}")
        
        return v
    
    @validator('signal_type')
    def validate_signal_type(cls, v):
        """Validate signal type"""
        allowed_signals = ["GPIO", "Network Packet", "Serial", "CAN Bus"]
        
        if v not in allowed_signals:
            raise ValueError(f"Signal type must be one of: {', '.join(allowed_signals)}")
        
        return v
    
    @validator('resolution')
    def validate_resolution(cls, v):
        """Validate resolution format"""
        if v:
            # Common resolution patterns: 1920x1080, 1280x720, etc.
            if not re.match(r'^\d+x\d+$', v.strip()):
                raise ValueError("Resolution must be in format 'WIDTHxHEIGHT' (e.g., 1920x1080)")
        return v
    
    @validator('frame_rate')
    def validate_frame_rate(cls, v):
        """Validate frame rate"""
        if v is not None:
            if not isinstance(v, int) or v <= 0 or v > 240:
                raise ValueError("Frame rate must be between 1 and 240 fps")
        return v

class ValidationMiddleware:
    """
    Comprehensive validation middleware for all form inputs
    Root cause fixes for validation, security, and input sanitization
    """
    
    @staticmethod
    def sanitize_string_input(value: str, max_length: int = None, allow_html: bool = False) -> str:
        """
        Sanitize string inputs to prevent XSS and injection attacks
        """
        if not isinstance(value, str):
            return str(value) if value is not None else ""
        
        # Strip whitespace
        value = value.strip()
        
        if not value:
            return value
        
        # HTML sanitization
        if allow_html:
            allowed_tags = ['b', 'i', 'u', 'br', 'p', 'strong', 'em']
            value = bleach.clean(value, tags=allowed_tags, strip=True)
        else:
            value = bleach.clean(value, tags=[], strip=True)
        
        # Length validation
        if max_length and len(value) > max_length:
            raise ValueError(f"Input exceeds maximum length of {max_length} characters")
        
        # Check for SQL injection patterns
        sql_patterns = [
            '--', ';', 'DROP ', 'DELETE ', 'INSERT ', 'UPDATE ', 'SELECT ', 'UNION ',
            'SCRIPT', 'EXEC', 'EXECUTE', 'sp_', 'xp_'
        ]
        
        value_upper = value.upper()
        for pattern in sql_patterns:
            if pattern.upper() in value_upper:
                raise ValueError("Input contains potentially dangerous content")
        
        return value
    
    @staticmethod
    def validate_file_upload(file_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate file upload data with proper security checks
        Fixes: Missing file upload validation
        """
        errors = []
        
        # Required fields
        required_fields = ['filename', 'size']
        for field in required_fields:
            if field not in file_data or not file_data[field]:
                errors.append(f"Field '{field}' is required")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        filename = file_data.get('filename', '')
        file_size = file_data.get('size', 0)
        
        # Validate filename
        if not filename or not filename.strip():
            errors.append("Filename cannot be empty")
        else:
            # Sanitize filename
            sanitized_filename = ValidationMiddleware.sanitize_string_input(filename, 255)
            
            # Validate file extension
            allowed_extensions = {
                '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm',
                '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'
            }
            
            file_ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
            if file_ext not in allowed_extensions:
                errors.append(f"File type '{file_ext}' not allowed. Allowed types: {', '.join(allowed_extensions)}")
            
            # Check for dangerous patterns in filename
            dangerous_patterns = ['..', '/', '\\', '<', '>', '|', ':', '*', '?', '"']
            for pattern in dangerous_patterns:
                if pattern in filename:
                    errors.append("Filename contains dangerous characters")
                    break
            
            file_data['filename'] = sanitized_filename
        
        # Validate file size
        if file_size <= 0:
            errors.append("File size must be greater than 0")
        elif file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
            errors.append("File size cannot exceed 2GB")
        
        # Validate duration if provided
        if 'duration' in file_data and file_data['duration'] is not None:
            try:
                duration = float(file_data['duration'])
                if duration <= 0:
                    errors.append("Video duration must be positive")
                elif duration > 7200:  # 2 hours max
                    errors.append("Video duration cannot exceed 2 hours")
                file_data['duration'] = duration
            except (ValueError, TypeError):
                errors.append("Invalid duration format")
        
        # Validate frame rate if provided
        if 'fps' in file_data and file_data['fps'] is not None:
            try:
                fps = float(file_data['fps'])
                if fps <= 0 or fps > 240:
                    errors.append("Frame rate must be between 0 and 240 fps")
                file_data['fps'] = fps
            except (ValueError, TypeError):
                errors.append("Invalid frame rate format")
        
        # Validate resolution if provided
        if 'resolution' in file_data and file_data['resolution']:
            resolution = file_data['resolution']
            if not re.match(r'^\d+x\d+$', str(resolution).strip()):
                errors.append("Resolution must be in format 'WIDTHxHEIGHT' (e.g., 1920x1080)")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "data": file_data}
    
    @staticmethod
    def validate_annotation_data(annotation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate annotation data with comprehensive checks
        """
        errors = []
        
        # Required fields
        required_fields = ['frame_number', 'timestamp', 'vru_type', 'bounding_box']
        for field in required_fields:
            if field not in annotation_data or annotation_data[field] is None:
                errors.append(f"Field '{field}' is required")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        # Validate frame number
        try:
            frame_number = int(annotation_data['frame_number'])
            if frame_number < 0:
                errors.append("Frame number must be non-negative")
            annotation_data['frame_number'] = frame_number
        except (ValueError, TypeError):
            errors.append("Frame number must be a valid integer")
        
        # Validate timestamp
        try:
            timestamp = float(annotation_data['timestamp'])
            if timestamp < 0:
                errors.append("Timestamp must be non-negative")
            annotation_data['timestamp'] = timestamp
        except (ValueError, TypeError):
            errors.append("Timestamp must be a valid number")
        
        # Validate end timestamp if provided
        if 'end_timestamp' in annotation_data and annotation_data['end_timestamp'] is not None:
            try:
                end_timestamp = float(annotation_data['end_timestamp'])
                if end_timestamp < annotation_data['timestamp']:
                    errors.append("End timestamp must be greater than start timestamp")
                annotation_data['end_timestamp'] = end_timestamp
            except (ValueError, TypeError):
                errors.append("End timestamp must be a valid number")
        
        # Validate VRU type
        allowed_vru_types = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'animal', 'other']
        vru_type = str(annotation_data['vru_type']).lower()
        if vru_type not in allowed_vru_types:
            errors.append(f"VRU type must be one of: {', '.join(allowed_vru_types)}")
        annotation_data['vru_type'] = vru_type
        
        # Validate bounding box
        bbox = annotation_data['bounding_box']
        if not isinstance(bbox, dict):
            errors.append("Bounding box must be an object")
        else:
            bbox_required = ['x', 'y', 'width', 'height']
            for bbox_field in bbox_required:
                if bbox_field not in bbox:
                    errors.append(f"Bounding box missing required field: {bbox_field}")
                else:
                    try:
                        value = float(bbox[bbox_field])
                        if bbox_field in ['x', 'y'] and value < 0:
                            errors.append(f"Bounding box {bbox_field} must be non-negative")
                        elif bbox_field in ['width', 'height'] and value <= 0:
                            errors.append(f"Bounding box {bbox_field} must be positive")
                        bbox[bbox_field] = value
                    except (ValueError, TypeError):
                        errors.append(f"Bounding box {bbox_field} must be a valid number")
            
            # Validate confidence if provided
            if 'confidence' in bbox and bbox['confidence'] is not None:
                try:
                    confidence = float(bbox['confidence'])
                    if confidence < 0 or confidence > 1:
                        errors.append("Bounding box confidence must be between 0 and 1")
                    bbox['confidence'] = confidence
                except (ValueError, TypeError):
                    errors.append("Bounding box confidence must be a valid number")
        
        # Sanitize text fields
        if 'notes' in annotation_data and annotation_data['notes']:
            try:
                annotation_data['notes'] = ValidationMiddleware.sanitize_string_input(
                    annotation_data['notes'], 1000, allow_html=False
                )
            except ValueError as e:
                errors.append(f"Notes validation error: {str(e)}")
        
        if 'annotator' in annotation_data and annotation_data['annotator']:
            try:
                annotation_data['annotator'] = ValidationMiddleware.sanitize_string_input(
                    annotation_data['annotator'], 255, allow_html=False
                )
            except ValueError as e:
                errors.append(f"Annotator validation error: {str(e)}")
        
        if errors:
            return {"valid": False, "errors": errors}
        
        return {"valid": True, "data": annotation_data}
    
    @staticmethod
    def validate_id_parameter(id_value: str, field_name: str = "ID") -> str:
        """
        Validate ID parameters to prevent injection attacks
        """
        if not id_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} cannot be empty"
            )
        
        # Remove any whitespace
        id_value = id_value.strip()
        
        # Validate UUID format if it looks like a UUID
        if len(id_value) == 36 and '-' in id_value:
            try:
                uuid.UUID(id_value)
                return id_value
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid {field_name} format"
                )
        
        # For other ID formats, ensure it only contains safe characters
        if not re.match(r'^[a-zA-Z0-9\-_]+$', id_value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} contains invalid characters"
            )
        
        if len(id_value) > 255:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} is too long"
            )
        
        return id_value
    
    @staticmethod
    def handle_validation_error(error: ValidationError) -> HTTPException:
        """
        Convert Pydantic validation errors to proper HTTP responses
        """
        error_details = []
        
        for err in error.errors():
            field_path = " -> ".join([str(loc) for loc in err['loc']])
            error_details.append(ValidationErrorDetail(
                field=field_path,
                message=err['msg'],
                invalid_value=err.get('input')
            ))
        
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Validation failed",
                "errors": [{"field": e.field, "message": e.message} for e in error_details]
            }
        )

def create_validation_dependency(validator_func: Callable) -> Callable:
    """
    Create a FastAPI dependency for validation
    """
    async def validate_request(request: Request):
        try:
            body = await request.json() if request.method in ['POST', 'PUT', 'PATCH'] else {}
            validation_result = validator_func(body)
            if not validation_result.get("valid", True):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": "Validation failed",
                        "errors": validation_result.get("errors", [])
                    }
                )
            return validation_result.get("data", body)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.error(f"Validation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Validation processing error"
            )
    
    return validate_request

# Pre-defined validation dependencies
validate_project_creation = create_validation_dependency(
    lambda data: {"valid": True, "data": EnhancedProjectCreate(**data).dict()}
)

validate_file_upload = create_validation_dependency(ValidationMiddleware.validate_file_upload)
validate_annotation = create_validation_dependency(ValidationMiddleware.validate_annotation_data)