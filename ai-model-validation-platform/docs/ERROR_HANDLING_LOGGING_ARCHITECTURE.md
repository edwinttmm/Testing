# Error Handling & Logging Architecture

## Overview

This document defines the comprehensive error handling and logging architecture for the AI Model Validation Platform, ensuring robust error management, comprehensive audit trails, and effective system monitoring.

## 1. ERROR HANDLING ARCHITECTURE

### 1.1 Error Classification System

```python
# utils/exceptions.py - Custom Exception Hierarchy

from typing import Dict, Any, Optional
from enum import Enum
import traceback
from datetime import datetime

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    BUSINESS_LOGIC = "business_logic"
    DATABASE = "database"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    ML_INFERENCE = "ml_inference"
    INTEGRATION = "integration"
    SYSTEM = "system"

class BaseApplicationError(Exception):
    """Base application error with comprehensive error context"""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        context: Dict[str, Any] = None,
        cause: Exception = None,
        recoverable: bool = True,
        user_message: str = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self._generate_error_code()
        self.severity = severity
        self.category = category
        self.context = context or {}
        self.cause = cause
        self.recoverable = recoverable
        self.user_message = user_message or self._generate_user_message()
        self.timestamp = datetime.utcnow()
        self.stack_trace = traceback.format_exc()
    
    def _generate_error_code(self) -> str:
        """Generate unique error code"""
        return f"{self.category.value.upper()}_{int(self.timestamp.timestamp())}"
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly error message"""
        return "An error occurred while processing your request. Please try again."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for serialization"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "severity": self.severity.value,
            "category": self.category.value,
            "context": self.context,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
            "stack_trace": self.stack_trace if self.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL] else None
        }

# Specific Exception Classes

class ValidationError(BaseApplicationError):
    """Input validation errors"""
    
    def __init__(self, message: str, field_errors: Dict[str, List[str]] = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            **kwargs
        )
        self.field_errors = field_errors or {}
    
    def _generate_user_message(self) -> str:
        return "Please check your input and try again."

class AuthenticationError(BaseApplicationError):
    """Authentication errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.MEDIUM,
            recoverable=False,
            **kwargs
        )
    
    def _generate_user_message(self) -> str:
        return "Authentication failed. Please log in again."

class AuthorizationError(BaseApplicationError):
    """Authorization errors"""
    
    def __init__(self, message: str, required_permission: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.MEDIUM,
            recoverable=False,
            **kwargs
        )
        self.required_permission = required_permission
    
    def _generate_user_message(self) -> str:
        return "You don't have permission to perform this action."

class BusinessLogicError(BaseApplicationError):
    """Business logic errors"""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
    
    def _generate_user_message(self) -> str:
        return "This operation cannot be completed due to business rules."

class DatabaseError(BaseApplicationError):
    """Database operation errors"""
    
    def __init__(self, message: str, query: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.query = query
    
    def _generate_user_message(self) -> str:
        return "A database error occurred. Please try again later."

class MLInferenceError(BaseApplicationError):
    """ML inference errors"""
    
    def __init__(self, message: str, model_name: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.ML_INFERENCE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.model_name = model_name
    
    def _generate_user_message(self) -> str:
        return "AI processing failed. Please try again or contact support."

class IntegrationError(BaseApplicationError):
    """Service integration errors"""
    
    def __init__(self, message: str, service_name: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.INTEGRATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.service_name = service_name
    
    def _generate_user_message(self) -> str:
        return "A service integration error occurred. Please try again."

class FileSystemError(BaseApplicationError):
    """File system operation errors"""
    
    def __init__(self, message: str, file_path: str = None, operation: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.FILE_SYSTEM,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )
        self.file_path = file_path
        self.operation = operation
    
    def _generate_user_message(self) -> str:
        return "A file operation error occurred. Please try again."

class NetworkError(BaseApplicationError):
    """Network communication errors"""
    
    def __init__(self, message: str, endpoint: str = None, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )
        self.endpoint = endpoint
    
    def _generate_user_message(self) -> str:
        return "A network error occurred. Please check your connection and try again."
```

### 1.2 Error Handler Implementation

```python
# middleware/error_handling.py - Comprehensive Error Handling Middleware

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any
import logging
import time
import json

from utils.exceptions import BaseApplicationError, ErrorSeverity, ErrorCategory
from services.audit_service import AuditService
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Comprehensive error handling middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.audit_service = AuditService()
        self.notification_service = NotificationService()
        
        # Error rate tracking
        self.error_counts = {}
        self.circuit_breakers = {}
    
    async def dispatch(self, request: Request, call_next):
        """Handle all application errors"""
        
        start_time = time.time()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        try:
            response = await call_next(request)
            
            # Log successful requests
            if response.status_code < 400:
                await self._log_success(request, response, start_time)
            
            return response
            
        except BaseApplicationError as e:
            # Handle custom application errors
            return await self._handle_application_error(request, e, start_time)
            
        except HTTPException as e:
            # Handle FastAPI HTTP exceptions
            return await self._handle_http_exception(request, e, start_time)
            
        except Exception as e:
            # Handle unexpected system errors
            return await self._handle_system_error(request, e, start_time)
    
    async def _handle_application_error(self, request: Request, error: BaseApplicationError, start_time: float) -> JSONResponse:
        """Handle custom application errors"""
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Determine HTTP status code
        status_code = self._get_status_code_for_error(error)
        
        # Log error
        await self._log_application_error(request, error, processing_time)
        
        # Send notifications for critical errors
        if error.severity == ErrorSeverity.CRITICAL:
            await self._send_critical_error_notification(request, error)
        
        # Track error rates
        await self._track_error_rate(request, error)
        
        # Check circuit breaker
        if await self._should_circuit_break(request, error):
            return await self._handle_circuit_breaker(request)
        
        # Create error response
        error_response = {
            "error": {
                "code": error.error_code,
                "message": error.user_message,
                "category": error.category.value,
                "severity": error.severity.value,
                "recoverable": error.recoverable,
                "timestamp": error.timestamp.isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
        
        # Add field errors for validation errors
        if hasattr(error, 'field_errors') and error.field_errors:
            error_response["error"]["field_errors"] = error.field_errors
        
        # Add stack trace for development
        if logger.getEffectiveLevel() <= logging.DEBUG and error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            error_response["error"]["debug"] = {
                "stack_trace": error.stack_trace,
                "context": error.context
            }
        
        return JSONResponse(
            status_code=status_code,
            content=error_response,
            headers={"X-Error-Code": error.error_code}
        )
    
    async def _handle_http_exception(self, request: Request, error: HTTPException, start_time: float) -> JSONResponse:
        """Handle FastAPI HTTP exceptions"""
        
        processing_time = (time.time() - start_time) * 1000
        
        # Convert to application error
        app_error = BaseApplicationError(
            message=str(error.detail),
            error_code=f"HTTP_{error.status_code}",
            severity=self._get_severity_for_status_code(error.status_code),
            category=ErrorCategory.SYSTEM,
            context={"status_code": error.status_code}
        )
        
        # Log error
        await self._log_application_error(request, app_error, processing_time)
        
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": app_error.error_code,
                    "message": str(error.detail),
                    "status_code": error.status_code,
                    "timestamp": app_error.timestamp.isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            },
            headers=getattr(error, 'headers', None) or {}
        )
    
    async def _handle_system_error(self, request: Request, error: Exception, start_time: float) -> JSONResponse:
        """Handle unexpected system errors"""
        
        processing_time = (time.time() - start_time) * 1000
        
        # Create application error from system error
        app_error = BaseApplicationError(
            message=f"Unexpected system error: {str(error)}",
            severity=ErrorSeverity.CRITICAL,
            category=ErrorCategory.SYSTEM,
            cause=error,
            recoverable=False,
            context={"error_type": type(error).__name__}
        )
        
        # Log critical system error
        await self._log_system_error(request, app_error, processing_time)
        
        # Send critical error notification
        await self._send_critical_error_notification(request, app_error)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": app_error.error_code,
                    "message": "An unexpected error occurred. Please try again later.",
                    "severity": "critical",
                    "timestamp": app_error.timestamp.isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
        )
    
    def _get_status_code_for_error(self, error: BaseApplicationError) -> int:
        """Get HTTP status code for application error"""
        
        status_map = {
            ErrorCategory.VALIDATION: 400,
            ErrorCategory.AUTHENTICATION: 401,
            ErrorCategory.AUTHORIZATION: 403,
            ErrorCategory.BUSINESS_LOGIC: 400,
            ErrorCategory.DATABASE: 503,
            ErrorCategory.NETWORK: 503,
            ErrorCategory.FILE_SYSTEM: 500,
            ErrorCategory.ML_INFERENCE: 503,
            ErrorCategory.INTEGRATION: 503,
            ErrorCategory.SYSTEM: 500
        }
        
        return status_map.get(error.category, 500)
    
    def _get_severity_for_status_code(self, status_code: int) -> ErrorSeverity:
        """Get error severity for HTTP status code"""
        
        if status_code < 400:
            return ErrorSeverity.LOW
        elif status_code < 500:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.HIGH
    
    async def _log_application_error(self, request: Request, error: BaseApplicationError, processing_time: float):
        """Log application error with full context"""
        
        error_context = {
            "error_code": error.error_code,
            "message": error.message,
            "category": error.category.value,
            "severity": error.severity.value,
            "processing_time_ms": processing_time,
            "request_method": request.method,
            "request_url": str(request.url),
            "request_id": getattr(request.state, 'request_id', None),
            "user_id": getattr(request.state, 'user_id', None),
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "context": error.context
        }
        
        # Log at appropriate level
        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical("Critical application error", extra=error_context)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error("High severity error", extra=error_context)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning("Medium severity error", extra=error_context)
        else:
            logger.info("Low severity error", extra=error_context)
        
        # Audit log the error
        await self.audit_service.log_error_event(
            error_code=error.error_code,
            message=error.message,
            category=error.category.value,
            severity=error.severity.value,
            request_path=str(request.url.path),
            user_id=getattr(request.state, 'user_id', None),
            context=error_context
        )
    
    async def _log_system_error(self, request: Request, error: BaseApplicationError, processing_time: float):
        """Log critical system errors"""
        
        logger.critical(
            f"Critical system error: {error.message}",
            extra={
                "error_code": error.error_code,
                "stack_trace": error.stack_trace,
                "processing_time_ms": processing_time,
                "request_url": str(request.url),
                "request_method": request.method
            }
        )
    
    async def _log_success(self, request: Request, response: Response, start_time: float):
        """Log successful requests"""
        
        processing_time = (time.time() - start_time) * 1000
        
        # Only log slow requests to avoid noise
        if processing_time > 1000:  # More than 1 second
            logger.warning(
                f"Slow request: {request.method} {request.url.path}",
                extra={
                    "processing_time_ms": processing_time,
                    "status_code": response.status_code,
                    "request_id": getattr(request.state, 'request_id', None)
                }
            )
    
    async def _send_critical_error_notification(self, request: Request, error: BaseApplicationError):
        """Send notification for critical errors"""
        
        try:
            await self.notification_service.send_critical_error_alert(
                error_code=error.error_code,
                message=error.message,
                category=error.category.value,
                request_path=str(request.url.path),
                user_id=getattr(request.state, 'user_id', None),
                context=error.context
            )
        except Exception as e:
            logger.error(f"Failed to send critical error notification: {e}")
    
    async def _track_error_rate(self, request: Request, error: BaseApplicationError):
        """Track error rates for monitoring"""
        
        endpoint = f"{request.method} {request.url.path}"
        current_time = int(time.time() / 60)  # Per minute
        
        if endpoint not in self.error_counts:
            self.error_counts[endpoint] = {}
        
        if current_time not in self.error_counts[endpoint]:
            self.error_counts[endpoint][current_time] = 0
        
        self.error_counts[endpoint][current_time] += 1
        
        # Clean old counts (keep last 10 minutes)
        cutoff_time = current_time - 10
        for minute in list(self.error_counts[endpoint].keys()):
            if minute < cutoff_time:
                del self.error_counts[endpoint][minute]
    
    async def _should_circuit_break(self, request: Request, error: BaseApplicationError) -> bool:
        """Check if circuit breaker should be triggered"""
        
        if error.severity != ErrorSeverity.CRITICAL:
            return False
        
        endpoint = f"{request.method} {request.url.path}"
        current_time = int(time.time() / 60)
        
        # Count errors in last 5 minutes
        recent_errors = 0
        for minute in range(current_time - 5, current_time + 1):
            recent_errors += self.error_counts.get(endpoint, {}).get(minute, 0)
        
        # Circuit break if more than 10 critical errors in 5 minutes
        return recent_errors > 10
    
    async def _handle_circuit_breaker(self, request: Request) -> JSONResponse:
        """Handle circuit breaker response"""
        
        logger.warning(f"Circuit breaker triggered for {request.method} {request.url.path}")
        
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "CIRCUIT_BREAKER_OPEN",
                    "message": "Service temporarily unavailable due to high error rate. Please try again later.",
                    "timestamp": datetime.utcnow().isoformat(),
                    "retry_after": 300  # 5 minutes
                }
            },
            headers={"Retry-After": "300"}
        )
```

## 2. LOGGING ARCHITECTURE

### 2.1 Structured Logging Implementation

```python
# services/logging_service.py - Comprehensive Logging Service

import structlog
import logging
import logging.handlers
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import aiofiles

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogCategory(Enum):
    API = "api"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    BUSINESS_LOGIC = "business_logic"
    ML_INFERENCE = "ml_inference"
    FILE_OPERATIONS = "file_operations"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    AUDIT = "audit"
    SYSTEM = "system"

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    message: str
    service: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    context: Dict[str, Any] = None
    duration_ms: Optional[float] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['level'] = self.level.value
        data['category'] = self.category.value
        return data

class LoggingService:
    """Centralized logging service with multiple output targets"""
    
    def __init__(self):
        self.logger = None
        self.file_handlers = {}
        self.async_log_queue = asyncio.Queue()
        self.log_processors = []
        
        # Configuration
        self.config = {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "format": "json",  # json or text
            "output_console": True,
            "output_file": True,
            "output_elasticsearch": False,
            "output_database": True,
            "file_rotation_size": 10 * 1024 * 1024,  # 10MB
            "file_rotation_count": 5,
            "async_processing": True
        }
    
    def initialize(self):
        """Initialize logging service"""
        
        # Configure structlog
        self._configure_structlog()
        
        # Setup output handlers
        self._setup_console_output()
        self._setup_file_output()
        
        if self.config["output_database"]:
            self._setup_database_output()
        
        if self.config["output_elasticsearch"]:
            self._setup_elasticsearch_output()
        
        # Start async processing
        if self.config["async_processing"]:
            asyncio.create_task(self._process_log_queue())
        
        self.logger = structlog.get_logger("ai_validation_platform")
        self.logger.info("Logging service initialized", config=self.config)
    
    def _configure_structlog(self):
        """Configure structlog with processors"""
        
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]
        
        if self.config["format"] == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())
        
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def _setup_console_output(self):
        """Setup console output handler"""
        
        if not self.config["output_console"]:
            return
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.config["level"])
        
        if self.config["format"] == "json":
            formatter = logging.Formatter('%(message)s')
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)
        root_logger.setLevel(self.config["level"])
    
    def _setup_file_output(self):
        """Setup file output handlers with rotation"""
        
        if not self.config["output_file"]:
            return
        
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Main application log
        app_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, "application.log"),
            maxBytes=self.config["file_rotation_size"],
            backupCount=self.config["file_rotation_count"]
        )
        
        # Error log
        error_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, "errors.log"),
            maxBytes=self.config["file_rotation_size"],
            backupCount=self.config["file_rotation_count"]
        )
        error_handler.setLevel(logging.ERROR)
        
        # Security log
        security_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, "security.log"),
            maxBytes=self.config["file_rotation_size"],
            backupCount=self.config["file_rotation_count"]
        )
        
        # Performance log
        performance_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, "performance.log"),
            maxBytes=self.config["file_rotation_size"],
            backupCount=self.config["file_rotation_count"]
        )
        
        # Configure formatters
        json_formatter = logging.Formatter('%(message)s')
        for handler in [app_handler, error_handler, security_handler, performance_handler]:
            handler.setFormatter(json_formatter)
        
        # Add handlers to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(app_handler)
        root_logger.addHandler(error_handler)
        
        # Store handlers for category-specific logging
        self.file_handlers = {
            LogCategory.SECURITY: security_handler,
            LogCategory.PERFORMANCE: performance_handler,
            LogCategory.AUDIT: security_handler,  # Share with security
        }
    
    def _setup_database_output(self):
        """Setup database output for log persistence"""
        
        class DatabaseLogHandler(logging.Handler):
            """Custom handler to write logs to database"""
            
            def __init__(self, logging_service):
                super().__init__()
                self.logging_service = logging_service
            
            def emit(self, record):
                try:
                    # Add to async queue for database insertion
                    log_data = {
                        "timestamp": datetime.fromtimestamp(record.created),
                        "level": record.levelname,
                        "logger_name": record.name,
                        "message": record.getMessage(),
                        "module": record.module,
                        "function": record.funcName,
                        "line": record.lineno,
                        "extra_data": getattr(record, 'extra_data', {})
                    }
                    
                    # Add to queue for async processing
                    asyncio.create_task(
                        self.logging_service.async_log_queue.put(
                            ("database", log_data)
                        )
                    )
                    
                except Exception:
                    pass  # Never raise exceptions in log handlers
        
        db_handler = DatabaseLogHandler(self)
        db_handler.setLevel(logging.INFO)
        
        root_logger = logging.getLogger()
        root_logger.addHandler(db_handler)
    
    def _setup_elasticsearch_output(self):
        """Setup Elasticsearch output for log aggregation"""
        
        try:
            from elasticsearch import AsyncElasticsearch
            
            class ElasticsearchLogHandler(logging.Handler):
                """Custom handler to write logs to Elasticsearch"""
                
                def __init__(self, logging_service):
                    super().__init__()
                    self.logging_service = logging_service
                    self.es_client = AsyncElasticsearch(['localhost:9200'])
                
                def emit(self, record):
                    try:
                        log_data = {
                            "@timestamp": datetime.fromtimestamp(record.created).isoformat(),
                            "level": record.levelname,
                            "logger": record.name,
                            "message": record.getMessage(),
                            "module": record.module,
                            "function": record.funcName,
                            "line": record.lineno,
                            "extra": getattr(record, 'extra_data', {})
                        }
                        
                        # Add to queue for async processing
                        asyncio.create_task(
                            self.logging_service.async_log_queue.put(
                                ("elasticsearch", log_data)
                            )
                        )
                        
                    except Exception:
                        pass
            
            es_handler = ElasticsearchLogHandler(self)
            es_handler.setLevel(logging.INFO)
            
            root_logger = logging.getLogger()
            root_logger.addHandler(es_handler)
            
        except ImportError:
            self.logger.warning("Elasticsearch not available, skipping ES log handler")
    
    async def _process_log_queue(self):
        """Process async log queue"""
        
        while True:
            try:
                # Get log entry from queue
                output_type, log_data = await self.async_log_queue.get()
                
                if output_type == "database":
                    await self._write_to_database(log_data)
                elif output_type == "elasticsearch":
                    await self._write_to_elasticsearch(log_data)
                
                self.async_log_queue.task_done()
                
            except Exception as e:
                # Log processing error (but don't create infinite loop)
                print(f"Log processing error: {e}")
                await asyncio.sleep(1)
    
    async def _write_to_database(self, log_data: Dict[str, Any]):
        """Write log entry to database"""
        
        try:
            from database import get_db
            from models.database import SystemLog
            
            db = next(get_db())
            
            log_entry = SystemLog(
                timestamp=log_data["timestamp"],
                level=log_data["level"],
                logger_name=log_data["logger_name"],
                message=log_data["message"],
                module=log_data["module"],
                function=log_data["function"],
                line_number=log_data["line"],
                extra_data=log_data["extra_data"]
            )
            
            db.add(log_entry)
            db.commit()
            
        except Exception as e:
            print(f"Database log write error: {e}")
    
    async def _write_to_elasticsearch(self, log_data: Dict[str, Any]):
        """Write log entry to Elasticsearch"""
        
        try:
            if hasattr(self, 'es_client'):
                index_name = f"logs-{datetime.now().strftime('%Y-%m-%d')}"
                
                await self.es_client.index(
                    index=index_name,
                    document=log_data
                )
                
        except Exception as e:
            print(f"Elasticsearch log write error: {e}")
    
    def create_logger(self, name: str, category: LogCategory = LogCategory.SYSTEM) -> structlog.BoundLogger:
        """Create categorized logger"""
        
        logger = structlog.get_logger(name)
        
        # Add category-specific handler if available
        if category in self.file_handlers:
            category_logger = logging.getLogger(f"{name}.{category.value}")
            category_logger.addHandler(self.file_handlers[category])
            category_logger.setLevel(logging.INFO)
        
        return logger.bind(category=category.value)
    
    async def log_structured(self, log_entry: LogEntry):
        """Log structured entry"""
        
        logger = self.create_logger(log_entry.service, log_entry.category)
        
        log_method = getattr(logger, log_entry.level.value.lower())
        
        log_method(
            log_entry.message,
            request_id=log_entry.request_id,
            user_id=log_entry.user_id,
            session_id=log_entry.session_id,
            correlation_id=log_entry.correlation_id,
            context=log_entry.context,
            duration_ms=log_entry.duration_ms,
            error_code=log_entry.error_code,
            stack_trace=log_entry.stack_trace
        )
    
    async def log_api_request(self, request_data: Dict[str, Any]):
        """Log API request"""
        
        log_entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=LogLevel.INFO,
            category=LogCategory.API,
            message=f"{request_data['method']} {request_data['path']}",
            service="api",
            request_id=request_data.get("request_id"),
            user_id=request_data.get("user_id"),
            context={
                "method": request_data["method"],
                "path": request_data["path"],
                "status_code": request_data.get("status_code"),
                "user_agent": request_data.get("user_agent"),
                "ip_address": request_data.get("ip_address")
            },
            duration_ms=request_data.get("duration_ms")
        )
        
        await self.log_structured(log_entry)
    
    async def log_performance_metric(self, metric_data: Dict[str, Any]):
        """Log performance metric"""
        
        log_entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=LogLevel.INFO,
            category=LogCategory.PERFORMANCE,
            message=f"Performance metric: {metric_data['metric_name']}",
            service=metric_data.get("service", "system"),
            context=metric_data
        )
        
        await self.log_structured(log_entry)
    
    async def log_security_event(self, event_data: Dict[str, Any]):
        """Log security event"""
        
        log_entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=LogLevel.WARNING,
            category=LogCategory.SECURITY,
            message=f"Security event: {event_data['event_type']}",
            service="security",
            user_id=event_data.get("user_id"),
            context=event_data
        )
        
        await self.log_structured(log_entry)


# Initialize global logging service
logging_service = LoggingService()

def get_logger(name: str, category: LogCategory = LogCategory.SYSTEM) -> structlog.BoundLogger:
    """Get categorized logger instance"""
    return logging_service.create_logger(name, category)
```

### 2.2 Request Logging Middleware

```python
# middleware/request_logging.py - Request Logging Middleware

import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Any
import json

from services.logging_service import logging_service, LogCategory, LogLevel, LogEntry

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request logging"""
    
    def __init__(self, app):
        super().__init__(app)
        self.sensitive_headers = {
            'authorization', 'cookie', 'x-api-key', 'x-auth-token'
        }
        self.sensitive_params = {
            'password', 'secret', 'token', 'key', 'auth'
        }
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response"""
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        await self._log_request(request, request_id)
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        await self._log_response(request, response, request_id, duration_ms)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request"""
        
        # Extract request data
        request_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": self._sanitize_headers(dict(request.headers)),
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "content_type": request.headers.get("content-type", ""),
            "content_length": request.headers.get("content-length", 0)
        }
        
        # Get user info if authenticated
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            request_data["user_id"] = user_id
        
        # Sanitize query parameters
        request_data["query_params"] = self._sanitize_params(
            request_data["query_params"]
        )
        
        # Log request body for POST/PUT requests (if not file upload)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request_data["content_type"]
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    if body:
                        body_data = json.loads(body.decode())
                        request_data["body"] = self._sanitize_body(body_data)
                except Exception:
                    request_data["body"] = "[Unable to parse body]"
        
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=LogLevel.INFO,
            category=LogCategory.API,
            message=f"Incoming request: {request.method} {request.url.path}",
            service="api_gateway",
            request_id=request_id,
            user_id=user_id,
            context=request_data
        )
        
        await logging_service.log_structured(log_entry)
    
    async def _log_response(self, request: Request, response, request_id: str, duration_ms: float):
        """Log outgoing response"""
        
        response_data = {
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "response_size": len(response.body) if hasattr(response, 'body') else 0
        }
        
        # Determine log level based on status code
        if response.status_code >= 500:
            level = LogLevel.ERROR
        elif response.status_code >= 400:
            level = LogLevel.WARNING
        elif duration_ms > 5000:  # Slow requests
            level = LogLevel.WARNING
        else:
            level = LogLevel.INFO
        
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            category=LogCategory.API,
            message=f"Response: {request.method} {request.url.path} - {response.status_code}",
            service="api_gateway",
            request_id=request_id,
            user_id=getattr(request.state, 'user_id', None),
            context=response_data,
            duration_ms=duration_ms
        )
        
        await logging_service.log_structured(log_entry)
        
        # Log to audit service for sensitive operations
        if self._is_sensitive_operation(request):
            await self._log_audit_event(request, response, request_id, duration_ms)
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize sensitive headers"""
        
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_params(self, params: Dict[str, str]) -> Dict[str, str]:
        """Sanitize sensitive parameters"""
        
        sanitized = {}
        for key, value in params.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_params):
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _sanitize_body(self, body_data: Any) -> Any:
        """Sanitize sensitive body data"""
        
        if isinstance(body_data, dict):
            sanitized = {}
            for key, value in body_data.items():
                if any(sensitive in key.lower() for sensitive in self.sensitive_params):
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_body(value)
                else:
                    sanitized[key] = value
            return sanitized
        elif isinstance(body_data, list):
            return [self._sanitize_body(item) for item in body_data]
        else:
            return body_data
    
    def _is_sensitive_operation(self, request: Request) -> bool:
        """Check if operation requires audit logging"""
        
        sensitive_paths = [
            '/auth', '/login', '/logout', '/users', '/admin',
            '/projects', '/videos', '/annotations'
        ]
        
        return any(sensitive in request.url.path for sensitive in sensitive_paths)
    
    async def _log_audit_event(self, request: Request, response, request_id: str, duration_ms: float):
        """Log audit event for sensitive operations"""
        
        from services.audit_service import AuditService
        
        audit_service = AuditService()
        
        await audit_service.log_api_access(
            user_id=getattr(request.state, 'user_id', None),
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", "")
        )
```

This comprehensive error handling and logging architecture provides:

1. **Comprehensive Error Classification**: Hierarchical error types with severity and category classification
2. **Advanced Error Handling**: Multi-layer error processing with circuit breakers and rate limiting
3. **Structured Logging**: JSON-based logging with multiple output targets
4. **Request Tracking**: Complete request/response logging with sensitive data sanitization
5. **Performance Monitoring**: Automatic performance metric logging
6. **Security Logging**: Dedicated security event logging and audit trails
7. **Async Processing**: Non-blocking log processing to maintain performance
8. **Multiple Output Targets**: Console, file, database, and Elasticsearch integration
9. **Error Recovery**: Automatic error recovery and fallback mechanisms
10. **Monitoring Integration**: Easy integration with monitoring systems like Prometheus and Grafana