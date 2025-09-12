"""
Response formatting middleware to ensure consistent API responses between frontend and backend.
This middleware standardizes all API responses to match frontend TypeScript interface expectations.
"""

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
import json
import logging

from schemas import ErrorResponse, ApiResponse

logger = logging.getLogger(__name__)

class ResponseFormattingMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure consistent API response formatting"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Process the request
            response = await call_next(request)
            
            # Only process JSON API responses
            if not self._should_format_response(request, response):
                return response
            
            # Get response content
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            
            if not response_body:
                return response
                
            try:
                response_data = json.loads(response_body.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return response
            
            # Format successful responses
            if 200 <= response.status_code < 300:
                formatted_data = self._format_success_response(response_data, response.status_code)
            else:
                formatted_data = self._format_error_response(response_data, response.status_code)
            
            # Create new response with formatted data
            return JSONResponse(
                content=formatted_data,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
        except Exception as e:
            logger.error(f"Response formatting middleware error: {e}")
            # Return error response in consistent format
            return self._create_error_response(
                message="An internal server error occurred",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="INTERNAL_ERROR",
                details={"middleware_error": str(e)}
            )
    
    def _should_format_response(self, request: Request, response: Response) -> bool:
        """Determine if response should be formatted"""
        # Only format API endpoints
        if not request.url.path.startswith("/api/"):
            return False
        
        # Only format JSON responses
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return False
            
        # Don't format file downloads, websockets, etc.
        if any(path in request.url.path for path in ["/download", "/export", "/ws", "/static"]):
            return False
            
        return True
    
    def _format_success_response(self, data: Any, status_code: int) -> Dict[str, Any]:
        """Format successful response data"""
        # If data is already in the expected format, return as is
        if isinstance(data, dict) and ("data" in data or "message" in data or "success" in data):
            # Ensure timestamp is present
            if "timestamp" not in data:
                data["timestamp"] = datetime.now(timezone.utc).isoformat()
            return data
        
        # Wrap raw data in standard format
        return {
            "data": data,
            "success": True,
            "status": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _format_error_response(self, data: Any, status_code: int) -> Dict[str, Any]:
        """Format error response data"""
        # Extract error information
        if isinstance(data, dict):
            message = data.get("message") or data.get("detail") or data.get("error") or "An error occurred"
            error_code = data.get("code")
            details = data.get("details")
        elif isinstance(data, str):
            message = data
            error_code = None
            details = None
        else:
            message = "An error occurred"
            error_code = None
            details = {"original_data": data}
        
        return {
            "message": message,
            "status": status_code,
            "code": error_code,
            "details": details,
            "success": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def _create_error_response(
        self, 
        message: str, 
        status_code: int, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Create a standardized error response"""
        error_data = {
            "message": message,
            "status": status_code,
            "code": error_code,
            "details": details,
            "success": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return JSONResponse(
            content=error_data,
            status_code=status_code
        )

def setup_error_handlers(app):
    """Setup consistent error handlers for the FastAPI app"""
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "message": exc.detail,
                "status": exc.status_code,
                "code": "HTTP_ERROR",
                "success": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "message": "Validation error",
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "code": "VALIDATION_ERROR", 
                "details": {"validation_errors": exc.errors()},
                "success": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": "Database error occurred",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "code": "DATABASE_ERROR",
                "success": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "message": "Data integrity constraint violation",
                "status": status.HTTP_409_CONFLICT,
                "code": "INTEGRITY_ERROR",
                "success": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "message": "An unexpected error occurred",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "code": "INTERNAL_ERROR",
                "success": False,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

# Helper functions for manual response formatting
def success_response(data: Any, message: Optional[str] = None, status_code: int = 200) -> Dict[str, Any]:
    """Create a successful response in standard format"""
    return {
        "data": data,
        "message": message,
        "success": True,
        "status": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def error_response(
    message: str, 
    status_code: int = 400, 
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create an error response in standard format"""
    return {
        "message": message,
        "status": status_code,
        "code": error_code,
        "details": details,
        "success": False,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Field transformation utilities for camelCase conversion
def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    if not snake_str or snake_str.startswith('_'):
        return snake_str
    
    components = snake_str.split('_')
    return components[0] + ''.join(word.capitalize() for word in components[1:])

def transform_keys_to_camel_case(data: Union[Dict, list, Any]) -> Any:
    """Recursively transform dictionary keys from snake_case to camelCase"""
    if isinstance(data, dict):
        return {to_camel_case(key): transform_keys_to_camel_case(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [transform_keys_to_camel_case(item) for item in data]
    else:
        return data