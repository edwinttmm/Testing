"""
Enhanced Error Handling Middleware
Provides comprehensive error handling, logging, and user-friendly error responses
"""
import logging
import time
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError
import traceback

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware:
    """Advanced error handling middleware with comprehensive logging and monitoring"""
    
    def __init__(self, app, enable_debug: bool = False):
        self.app = app
        self.enable_debug = enable_debug
        self.error_stats = {
            "total_errors": 0,
            "error_types": {},
            "error_endpoints": {}
        }
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                # Add request ID header
                headers = dict(message.get("headers", []))
                headers[b"x-request-id"] = request_id.encode()
                message["headers"] = list(headers.items())
            await send(message)
        
        try:
            await self.app(scope, receive, wrapped_send)
        except Exception as e:
            # Handle the exception and send appropriate response
            response = await self._handle_exception(e, scope, request_id, start_time)
            await response(scope, receive, send)
    
    async def _handle_exception(
        self, 
        exc: Exception, 
        scope: Dict[str, Any], 
        request_id: str,
        start_time: float
    ) -> Response:
        """Handle different types of exceptions with appropriate responses"""
        
        # Extract request information
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/unknown")
        processing_time = time.time() - start_time
        
        # Update error statistics
        self._update_error_stats(exc.__class__.__name__, path)
        
        # Log error details
        error_context = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "processing_time_ms": round(processing_time * 1000, 2),
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Handle specific exception types
        if isinstance(exc, HTTPException):
            return await self._handle_http_exception(exc, error_context)
        elif isinstance(exc, ValidationError):
            return await self._handle_validation_error(exc, error_context)
        elif isinstance(exc, SQLAlchemyError):
            return await self._handle_database_error(exc, error_context)
        elif isinstance(exc, (ConnectionError, TimeoutError)):
            return await self._handle_network_error(exc, error_context)
        else:
            return await self._handle_generic_error(exc, error_context)
    
    async def _handle_http_exception(
        self, 
        exc: HTTPException, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""
        logger.warning(f"HTTP Exception [{context['request_id']}]: {exc.status_code} - {exc.detail}")
        
        error_response = {
            "error": {
                "type": "http_error",
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": context["request_id"],
                "timestamp": context["timestamp"],
                "path": context["path"]
            }
        }
        
        # Add debug info if enabled
        if self.enable_debug:
            error_response["debug"] = {
                "processing_time_ms": context["processing_time_ms"],
                "method": context["method"]
            }
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response,
            headers={"x-request-id": context["request_id"]}
        )
    
    async def _handle_validation_error(
        self, 
        exc: ValidationError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle Pydantic validation errors"""
        logger.warning(f"Validation Error [{context['request_id']}]: {exc}")
        
        # Extract detailed validation errors
        validation_errors = []
        for error in exc.errors():
            validation_errors.append({
                "field": ".".join(str(x) for x in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })
        
        error_response = {
            "error": {
                "type": "validation_error",
                "code": 422,
                "message": "Input validation failed",
                "request_id": context["request_id"],
                "timestamp": context["timestamp"],
                "validation_errors": validation_errors
            }
        }
        
        if self.enable_debug:
            error_response["debug"] = {
                "processing_time_ms": context["processing_time_ms"],
                "path": context["path"],
                "method": context["method"]
            }
        
        return JSONResponse(
            status_code=422,
            content=error_response,
            headers={"x-request-id": context["request_id"]}
        )
    
    async def _handle_database_error(
        self, 
        exc: SQLAlchemyError, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle database-related errors"""
        
        # Different handling based on error type
        if isinstance(exc, IntegrityError):
            status_code = 409
            error_type = "integrity_error"
            user_message = "Data integrity constraint violation. The requested operation conflicts with existing data."
            logger.error(f"Database Integrity Error [{context['request_id']}]: {exc}")
            
        elif isinstance(exc, OperationalError):
            status_code = 503
            error_type = "database_unavailable"
            user_message = "Database is temporarily unavailable. Please try again later."
            logger.critical(f"Database Operational Error [{context['request_id']}]: {exc}")
            
        else:
            status_code = 500
            error_type = "database_error"
            user_message = "A database error occurred. Please try again or contact support."
            logger.error(f"Database Error [{context['request_id']}]: {exc}")
        
        error_response = {
            "error": {
                "type": error_type,
                "code": status_code,
                "message": user_message,
                "request_id": context["request_id"],
                "timestamp": context["timestamp"],
                "retry_after": 30 if status_code == 503 else None
            }
        }
        
        if self.enable_debug:
            error_response["debug"] = {
                "processing_time_ms": context["processing_time_ms"],
                "path": context["path"],
                "method": context["method"],
                "database_error": str(exc)
            }
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={"x-request-id": context["request_id"]}
        )
    
    async def _handle_network_error(
        self, 
        exc: Exception, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle network-related errors"""
        logger.error(f"Network Error [{context['request_id']}]: {exc}")
        
        if isinstance(exc, TimeoutError):
            status_code = 504
            error_type = "timeout_error"
            user_message = "Request timed out. Please try again with a smaller request or check your connection."
        else:
            status_code = 502
            error_type = "network_error"
            user_message = "Network connectivity issue. Please check your connection and try again."
        
        error_response = {
            "error": {
                "type": error_type,
                "code": status_code,
                "message": user_message,
                "request_id": context["request_id"],
                "timestamp": context["timestamp"],
                "retry_after": 10
            }
        }
        
        if self.enable_debug:
            error_response["debug"] = {
                "processing_time_ms": context["processing_time_ms"],
                "path": context["path"],
                "method": context["method"],
                "network_error": str(exc)
            }
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={"x-request-id": context["request_id"]}
        )
    
    async def _handle_generic_error(
        self, 
        exc: Exception, 
        context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle unexpected errors"""
        logger.critical(
            f"Unhandled Exception [{context['request_id']}]: {exc}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        error_response = {
            "error": {
                "type": "internal_server_error",
                "code": 500,
                "message": "An unexpected error occurred. Our team has been notified.",
                "request_id": context["request_id"],
                "timestamp": context["timestamp"]
            }
        }
        
        if self.enable_debug:
            error_response["debug"] = {
                "processing_time_ms": context["processing_time_ms"],
                "path": context["path"],
                "method": context["method"],
                "exception_type": exc.__class__.__name__,
                "exception_message": str(exc),
                "traceback": traceback.format_exc().split("\n")
            }
        
        return JSONResponse(
            status_code=500,
            content=error_response,
            headers={"x-request-id": context["request_id"]}
        )
    
    def _update_error_stats(self, error_type: str, endpoint: str):
        """Update error statistics for monitoring"""
        self.error_stats["total_errors"] += 1
        
        # Track error types
        if error_type not in self.error_stats["error_types"]:
            self.error_stats["error_types"][error_type] = 0
        self.error_stats["error_types"][error_type] += 1
        
        # Track error endpoints
        if endpoint not in self.error_stats["error_endpoints"]:
            self.error_stats["error_endpoints"][endpoint] = 0
        self.error_stats["error_endpoints"][endpoint] += 1
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get current error statistics for monitoring"""
        return {
            **self.error_stats,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
    
    def reset_error_statistics(self):
        """Reset error statistics"""
        self.error_stats = {
            "total_errors": 0,
            "error_types": {},
            "error_endpoints": {}
        }
        logger.info("Error statistics reset")

def create_error_handling_middleware(app, debug: bool = False):
    """Factory function to create error handling middleware"""
    return ErrorHandlingMiddleware(app, enable_debug=debug)

# Enhanced HTTP exception handlers for FastAPI
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation exceptions"""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    validation_errors = []
    for error in exc.errors():
        validation_errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Validation error [{request_id}]: {exc}")
    
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "type": "validation_error",
                "code": 422,
                "message": "Input validation failed",
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "validation_errors": validation_errors
            }
        },
        headers={"x-request-id": request_id}
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with enhanced formatting"""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    logger.warning(f"HTTP exception [{request_id}]: {exc.status_code} - {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_error",
                "code": exc.status_code,
                "message": exc.detail,
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        },
        headers={"x-request-id": request_id}
    )

async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database exceptions"""
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    if isinstance(exc, IntegrityError):
        status_code = 409
        message = "Data integrity constraint violation"
        logger.error(f"Database integrity error [{request_id}]: {exc}")
    elif isinstance(exc, OperationalError):
        status_code = 503
        message = "Database temporarily unavailable"
        logger.critical(f"Database operational error [{request_id}]: {exc}")
    else:
        status_code = 500
        message = "Database operation failed"
        logger.error(f"Database error [{request_id}]: {exc}")
    
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "type": "database_error",
                "code": status_code,
                "message": message,
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        },
        headers={"x-request-id": request_id}
    )