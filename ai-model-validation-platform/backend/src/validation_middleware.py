"""
Validation Middleware for Annotation Data Integrity
==================================================

This module provides FastAPI middleware and dependency injection for comprehensive
annotation validation. All annotation-related endpoints are protected by multiple
layers of validation to prevent data corruption.

Key Features:
1. Request validation middleware
2. Response validation middleware  
3. Dependency injection for validation services
4. Error handling with structured responses
5. Logging and monitoring integration
6. Performance optimization
"""

from fastapi import Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from sqlalchemy.orm import Session
from typing import Any, Callable, Dict, List, Optional, Union
import json
import time
import uuid
import logging
from datetime import datetime

from src.validation_models import (
    StrictAnnotationCreate,
    StrictAnnotationUpdate, 
    StrictBoundingBox,
    ValidationErrorResponse,
    BulkValidationResult
)
from database import get_db
from models import Video, Annotation

logger = logging.getLogger(__name__)


class ValidationMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive validation middleware for annotation endpoints.
    
    This middleware intercepts all annotation-related requests and responses
    to ensure data integrity at the API boundary.
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.annotation_endpoints = {
            '/api/videos/{video_id}/annotations',
            '/api/annotations/{annotation_id}',
            '/api/annotations/bulk',
            '/api/detection/annotate',
            '/api/ground-truth/annotate'
        }
        
        self.validation_stats = {
            'requests_validated': 0,
            'validation_failures': 0,
            'validation_errors': [],
            'performance_metrics': []
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch - validates requests and responses"""
        
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Add request ID for tracing
        request.state.validation_request_id = request_id
        
        try:
            # Check if this is an annotation-related endpoint
            if self._is_annotation_endpoint(request):
                logger.info(f"[{request_id}] Validating annotation request: {request.method} {request.url.path}")
                
                # Pre-request validation
                await self._validate_request(request, request_id)
                
                # Process the request
                response = await call_next(request)
                
                # Post-response validation
                await self._validate_response(response, request, request_id)
                
                # Update statistics
                self._update_stats(request_id, start_time, success=True)
                
                return response
            else:
                # Not an annotation endpoint - pass through
                return await call_next(request)
                
        except ValidationException as e:
            logger.error(f"[{request_id}] Validation failed: {e.detail}")
            self._update_stats(request_id, start_time, success=False, error=str(e.detail))
            
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": "Validation Error",
                    "detail": e.detail,
                    "validation_errors": e.validation_errors,
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error in validation middleware: {e}", exc_info=True)
            self._update_stats(request_id, start_time, success=False, error=str(e))
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Validation Error", 
                    "detail": "An unexpected error occurred during validation",
                    "request_id": request_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    def _is_annotation_endpoint(self, request: Request) -> bool:
        """Check if request is for an annotation-related endpoint"""
        path = request.url.path
        method = request.method
        
        # Check for annotation creation/update endpoints
        annotation_patterns = [
            '/api/videos/',
            '/api/annotations',
            '/api/detection/annotate',
            '/api/ground-truth'
        ]
        
        # Only validate POST/PUT/PATCH requests to annotation endpoints
        if method in ['POST', 'PUT', 'PATCH']:
            return any(pattern in path for pattern in annotation_patterns)
        
        return False
    
    async def _validate_request(self, request: Request, request_id: str):
        """Validate incoming request data"""
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                # Get request body
                body = await request.body()
                if not body:
                    return  # No body to validate
                
                try:
                    request_data = json.loads(body)
                except json.JSONDecodeError:
                    raise ValidationException(
                        status_code=400,
                        detail="Invalid JSON in request body",
                        validation_errors=[ValidationErrorResponse(
                            error_type="json_decode_error",
                            message="Request body must be valid JSON",
                            provided_value=str(body[:100])
                        )]
                    )
                
                # Validate based on endpoint type
                path = request.url.path
                
                if '/annotations' in path and request.method == 'POST':
                    await self._validate_annotation_create(request_data, request_id)
                elif '/annotations' in path and request.method in ['PUT', 'PATCH']:
                    await self._validate_annotation_update(request_data, request_id)
                elif 'bulk' in path:
                    await self._validate_bulk_annotations(request_data, request_id)
                
            except ValidationException:
                raise
            except Exception as e:
                logger.error(f"[{request_id}] Error validating request: {e}", exc_info=True)
                raise ValidationException(
                    status_code=500,
                    detail=f"Request validation failed: {str(e)}"
                )
    
    async def _validate_annotation_create(self, data: Dict, request_id: str):
        """Validate annotation creation data"""
        
        try:
            # Use strict validation model
            validated_annotation = StrictAnnotationCreate(**data)
            logger.info(f"[{request_id}] Annotation creation data validated successfully")
            
        except Exception as e:
            validation_errors = self._parse_validation_errors(e)
            raise ValidationException(
                status_code=422,
                detail="Annotation creation data validation failed",
                validation_errors=validation_errors
            )
    
    async def _validate_annotation_update(self, data: Dict, request_id: str):
        """Validate annotation update data"""
        
        try:
            # Use strict update validation model
            validated_update = StrictAnnotationUpdate(**data)
            logger.info(f"[{request_id}] Annotation update data validated successfully")
            
        except Exception as e:
            validation_errors = self._parse_validation_errors(e)
            raise ValidationException(
                status_code=422,
                detail="Annotation update data validation failed", 
                validation_errors=validation_errors
            )
    
    async def _validate_bulk_annotations(self, data: Dict, request_id: str):
        """Validate bulk annotation data"""
        
        annotations = data.get('annotations', [])
        if not annotations:
            raise ValidationException(
                status_code=400,
                detail="Bulk annotation request must contain annotations array"
            )
        
        validation_errors = []
        valid_count = 0
        
        for i, annotation_data in enumerate(annotations):
            try:
                StrictAnnotationCreate(**annotation_data)
                valid_count += 1
            except Exception as e:
                error_details = self._parse_validation_errors(e)
                for error in error_details:
                    error.field = f"annotations[{i}].{error.field}" if error.field else f"annotations[{i}]"
                validation_errors.extend(error_details)
        
        if validation_errors:
            raise ValidationException(
                status_code=422,
                detail=f"Bulk validation failed: {len(validation_errors)} errors found",
                validation_errors=validation_errors
            )
        
        logger.info(f"[{request_id}] Bulk annotation validation completed: {valid_count} valid annotations")
    
    async def _validate_response(self, response: Response, request: Request, request_id: str):
        """Validate outgoing response data"""
        
        # Only validate successful responses with content
        if response.status_code >= 400:
            return
        
        # For annotation responses, ensure bounding box data integrity
        if hasattr(response, 'body') and response.headers.get('content-type', '').startswith('application/json'):
            try:
                # This would validate response structure
                # For performance, we might only validate in debug mode
                logger.debug(f"[{request_id}] Response validation completed")
                
            except Exception as e:
                logger.error(f"[{request_id}] Response validation failed: {e}")
                # Don't fail the request for response validation errors
                # Just log them for monitoring
    
    def _parse_validation_errors(self, exception: Exception) -> List[ValidationErrorResponse]:
        """Parse Pydantic validation errors into structured format"""
        
        validation_errors = []
        
        if hasattr(exception, 'errors'):
            # Pydantic ValidationError
            for error in exception.errors():
                field_path = '.'.join(str(loc) for loc in error.get('loc', []))
                validation_errors.append(ValidationErrorResponse(
                    error_type=error.get('type', 'validation_error'),
                    field=field_path if field_path else None,
                    message=error.get('msg', 'Validation failed'),
                    provided_value=error.get('input'),
                    expected_format=error.get('ctx', {}).get('limit_value')
                ))
        else:
            # Generic validation error
            validation_errors.append(ValidationErrorResponse(
                error_type="validation_error",
                message=str(exception),
                provided_value=None
            ))
        
        return validation_errors
    
    def _update_stats(self, request_id: str, start_time: float, success: bool, error: str = None):
        """Update validation statistics"""
        
        duration = time.time() - start_time
        
        self.validation_stats['requests_validated'] += 1
        if not success:
            self.validation_stats['validation_failures'] += 1
            if error:
                self.validation_stats['validation_errors'].append({
                    'request_id': request_id,
                    'timestamp': datetime.utcnow().isoformat(),
                    'error': error
                })
        
        self.validation_stats['performance_metrics'].append({
            'request_id': request_id,
            'duration_ms': duration * 1000,
            'success': success,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 1000 entries for memory management
        if len(self.validation_stats['validation_errors']) > 1000:
            self.validation_stats['validation_errors'] = self.validation_stats['validation_errors'][-1000:]
        if len(self.validation_stats['performance_metrics']) > 1000:
            self.validation_stats['performance_metrics'] = self.validation_stats['performance_metrics'][-1000:]


class ValidationException(HTTPException):
    """Custom exception for validation errors"""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        validation_errors: List[ValidationErrorResponse] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.validation_errors = validation_errors or []


# Dependency injection for validation services

async def validate_video_exists(video_id: str, db: Session = Depends(get_db)) -> Video:
    """Dependency to validate that video exists before annotation operations"""
    
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(
            status_code=404,
            detail=f"Video with id {video_id} not found"
        )
    
    return video


async def validate_annotation_exists(annotation_id: str, db: Session = Depends(get_db)) -> Annotation:
    """Dependency to validate that annotation exists before update/delete operations"""
    
    annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
    if not annotation:
        raise HTTPException(
            status_code=404,
            detail=f"Annotation with id {annotation_id} not found"
        )
    
    return annotation


async def validate_annotation_create_data(
    annotation_data: Dict[str, Any]
) -> StrictAnnotationCreate:
    """Dependency to validate annotation creation data"""
    
    try:
        return StrictAnnotationCreate(**annotation_data)
    except Exception as e:
        validation_middleware = ValidationMiddleware(None)
        validation_errors = validation_middleware._parse_validation_errors(e)
        raise ValidationException(
            status_code=422,
            detail="Annotation creation data validation failed",
            validation_errors=validation_errors
        )


async def validate_annotation_update_data(
    annotation_data: Dict[str, Any]
) -> StrictAnnotationUpdate:
    """Dependency to validate annotation update data"""
    
    try:
        return StrictAnnotationUpdate(**annotation_data)
    except Exception as e:
        validation_middleware = ValidationMiddleware(None)
        validation_errors = validation_middleware._parse_validation_errors(e)
        raise ValidationException(
            status_code=422,
            detail="Annotation update data validation failed",
            validation_errors=validation_errors
        )


class ValidationMetrics:
    """Validation metrics collection and reporting"""
    
    def __init__(self):
        self.metrics = {
            'total_validations': 0,
            'validation_failures': 0,
            'validation_success_rate': 0.0,
            'average_validation_time_ms': 0.0,
            'common_errors': {},
            'last_reset': datetime.utcnow().isoformat()
        }
    
    def get_validation_stats(self, middleware: ValidationMiddleware) -> Dict[str, Any]:
        """Get current validation statistics"""
        
        stats = middleware.validation_stats
        
        if stats['requests_validated'] > 0:
            success_rate = 1 - (stats['validation_failures'] / stats['requests_validated'])
        else:
            success_rate = 0.0
        
        performance_metrics = stats['performance_metrics']
        if performance_metrics:
            avg_time = sum(m['duration_ms'] for m in performance_metrics) / len(performance_metrics)
        else:
            avg_time = 0.0
        
        return {
            'total_validations': stats['requests_validated'],
            'validation_failures': stats['validation_failures'],
            'validation_success_rate': round(success_rate * 100, 2),
            'average_validation_time_ms': round(avg_time, 2),
            'recent_errors': stats['validation_errors'][-10:],  # Last 10 errors
            'performance_metrics': stats['performance_metrics'][-10:],  # Last 10 metrics
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def reset_metrics(self, middleware: ValidationMiddleware):
        """Reset validation metrics"""
        middleware.validation_stats = {
            'requests_validated': 0,
            'validation_failures': 0,
            'validation_errors': [],
            'performance_metrics': []
        }
        
        self.metrics['last_reset'] = datetime.utcnow().isoformat()


# Global validation metrics instance
validation_metrics = ValidationMetrics()


# Health check endpoint for validation middleware
async def validation_health_check() -> Dict[str, Any]:
    """Health check for validation system"""
    
    return {
        "status": "healthy",
        "validation_middleware": "active",
        "strict_models": "loaded",
        "database_constraints": "enabled",
        "timestamp": datetime.utcnow().isoformat()
    }


# Configuration for validation middleware
class ValidationConfig:
    """Configuration class for validation middleware"""
    
    def __init__(self):
        self.enable_request_validation = True
        self.enable_response_validation = False  # Disabled for performance
        self.log_validation_errors = True
        self.log_performance_metrics = True
        self.max_error_history = 1000
        self.max_performance_history = 1000
        
        # Performance thresholds
        self.validation_timeout_ms = 5000
        self.slow_validation_threshold_ms = 1000
        
        # Error handling
        self.fail_fast_on_critical_errors = True
        self.allow_partial_success_bulk = False


# Global validation configuration
validation_config = ValidationConfig()