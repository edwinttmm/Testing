"""Security validation utilities"""
import re
from typing import Optional
from fastapi import HTTPException, status

# RFC 4122 UUID validation pattern
UUID_PATTERN = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    re.IGNORECASE
)

class ValidationError(Exception):
    """Raised when validation fails"""
    pass

def validate_uuid(value: str, field_name: str = "ID") -> str:
    """
    Validate UUID format to prevent SQL injection.

    This function validates UUIDs according to RFC 4122 and prevents
    SQL injection by ensuring only valid UUID formats are accepted.

    Args:
        value: String to validate
        field_name: Name of field for error messages

    Returns:
        Validated UUID string (lowercase)

    Raises:
        HTTPException(400): If UUID is invalid
    """
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} cannot be empty"
        )

    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be a string, got {type(value).__name__}"
        )

    if len(value) != 36:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be 36 characters, got {len(value)}"
        )

    if not UUID_PATTERN.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format. Expected RFC 4122 UUID format (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
        )

    return value.lower()

def validate_session_id(session_id: str) -> str:
    """Validate session ID format"""
    return validate_uuid(session_id, "Session ID")

def validate_project_id(project_id: str) -> str:
    """Validate project ID format"""
    return validate_uuid(project_id, "Project ID")

def validate_video_id(video_id: str) -> str:
    """Validate video ID format"""
    return validate_uuid(video_id, "Video ID")

def validate_sequence_id(sequence_id: str) -> str:
    """Validate sequence ID format"""
    return validate_uuid(sequence_id, "Sequence ID")
