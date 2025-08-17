"""
Custom exception classes for VRU Detection System
"""

from typing import Optional, Dict, Any
from fastapi import status


class VRUDetectionException(Exception):
    """Base exception for VRU Detection System"""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class DatabaseException(VRUDetectionException):
    """Database-related exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="DATABASE_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class VideoProcessingException(VRUDetectionException):
    """Video processing exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="VIDEO_PROCESSING_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class DetectionException(VRUDetectionException):
    """Detection engine exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="DETECTION_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ValidationException(VRUDetectionException):
    """Validation-related exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_400_BAD_REQUEST
        )


class SignalProcessingException(VRUDetectionException):
    """Signal processing exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="SIGNAL_PROCESSING_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ResourceNotFoundException(VRUDetectionException):
    """Resource not found exceptions"""
    
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            error_code="RESOURCE_NOT_FOUND",
            message=f"{resource_type} with ID {resource_id} not found",
            details={"resource_type": resource_type, "resource_id": resource_id},
            status_code=status.HTTP_404_NOT_FOUND
        )


class AuthenticationException(VRUDetectionException):
    """Authentication-related exceptions"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            error_code="AUTHENTICATION_ERROR",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class AuthorizationException(VRUDetectionException):
    """Authorization-related exceptions"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            error_code="AUTHORIZATION_ERROR",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN
        )


class RateLimitException(VRUDetectionException):
    """Rate limiting exceptions"""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            error_code="RATE_LIMIT_EXCEEDED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class ConfigurationException(VRUDetectionException):
    """Configuration-related exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="CONFIGURATION_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class ModelException(VRUDetectionException):
    """ML model-related exceptions"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code="MODEL_ERROR",
            message=message,
            details=details,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )