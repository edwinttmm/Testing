# Error Propagation Across System Layers Analysis

## Overview
This document provides comprehensive analysis of error handling, propagation patterns, recovery mechanisms, and error boundary strategies across all layers of the AI Model Validation Platform.

## Error Propagation Architecture

```
┌─────────────────┐    Errors    ┌──────────────────┐    Errors    ┌─────────────────┐
│  Frontend UI    │ ◄─────────── │   API Layer      │ ◄─────────── │  Backend Logic  │
│   Components    │    HTTP      │   Transport      │    Python    │   Services      │
└─────────────────┘   Responses  └──────────────────┘  Exceptions  └─────────────────┘
         │                                │                                │
    ┌────▼────┐                      ┌────▼────┐                      ┌────▼────┐
    │Error    │                      │HTTP     │                      │Database │
    │Boundary │                      │Error    │                      │ Errors  │
    │Recovery │                      │Handler  │                      │Hardware │
    └─────────┘                      └─────────┘                      │Failures │
                                                                      └─────────┘
```

## Backend Error Handling and Propagation

### 1. Exception Hierarchy and Transformation

#### Custom Exception Classes
```python
# exceptions.py - Centralized exception handling
from typing import Optional, Dict, Any
from enum import Enum

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class BaseValidationError(Exception):
    """Base exception for all application errors"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None,
        details: Dict[str, Any] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        user_message: str = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.severity = severity
        self.recoverable = recoverable
        self.user_message = user_message or self._generate_user_message()
        self.timestamp = datetime.utcnow()
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly error message"""
        return "An error occurred while processing your request."
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception for API responses"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "details": self.details,
            "severity": self.severity.value,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat()
        }

class DatabaseConnectionError(BaseValidationError):
    """Database connection and operation errors"""
    
    def __init__(self, operation: str, original_error: Exception = None):
        super().__init__(
            message=f"Database operation failed: {operation}",
            error_code="DATABASE_CONNECTION_ERROR",
            details={
                "operation": operation,
                "original_error": str(original_error) if original_error else None
            },
            severity=ErrorSeverity.HIGH,
            recoverable=True
        )
    
    def _generate_user_message(self) -> str:
        return "Database is temporarily unavailable. Please try again in a moment."

class VideoProcessingError(BaseValidationError):
    """Video upload and processing errors"""
    
    def __init__(self, filename: str, stage: str, reason: str):
        super().__init__(
            message=f"Video processing failed at {stage}: {reason}",
            error_code="VIDEO_PROCESSING_ERROR",
            details={
                "filename": filename,
                "processing_stage": stage,
                "failure_reason": reason
            },
            severity=ErrorSeverity.MEDIUM,
            recoverable=True
        )
    
    def _generate_user_message(self) -> str:
        return f"Unable to process video '{self.details['filename']}'. Please check the file format and try again."

class LabJackHardwareError(BaseValidationError):
    """LabJack hardware communication errors"""
    
    def __init__(self, operation: str, device_info: Dict[str, Any] = None, original_error: Exception = None):
        super().__init__(
            message=f"LabJack hardware error during {operation}",
            error_code="LABJACK_HARDWARE_ERROR",
            details={
                "operation": operation,
                "device_info": device_info or {},
                "original_error": str(original_error) if original_error else None,
                "mock_mode_available": True
            },
            severity=ErrorSeverity.HIGH,
            recoverable=True
        )
    
    def _generate_user_message(self) -> str:
        return "Hardware connection lost. Switching to simulation mode for continued testing."

class AuthenticationError(BaseValidationError):
    """Authentication and authorization errors"""
    
    def __init__(self, reason: str, action_attempted: str = None):
        super().__init__(
            message=f"Authentication failed: {reason}",
            error_code="AUTHENTICATION_ERROR",
            details={
                "reason": reason,
                "action_attempted": action_attempted
            },
            severity=ErrorSeverity.MEDIUM,
            recoverable=False
        )
    
    def _generate_user_message(self) -> str:
        return "Please log in to continue."
```

### 2. Global Error Handler

#### FastAPI Exception Handlers
```python
# main.py - Global error handling middleware
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import ValidationError, RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
import logging

logger = logging.getLogger(__name__)

class ErrorPropagationService:
    """Service for consistent error handling and propagation"""
    
    @staticmethod
    def create_error_response(error: Exception, request: Request) -> JSONResponse:
        """Create standardized error response"""
        
        # Log error with context
        ErrorPropagationService._log_error(error, request)
        
        if isinstance(error, BaseValidationError):
            return JSONResponse(
                status_code=ErrorPropagationService._get_http_status_code(error),
                content=error.to_dict()
            )
        elif isinstance(error, HTTPException):
            return JSONResponse(
                status_code=error.status_code,
                content={
                    "error_code": "HTTP_ERROR",
                    "message": error.detail,
                    "user_message": error.detail,
                    "severity": "medium",
                    "recoverable": True
                }
            )
        elif isinstance(error, RequestValidationError):
            return ErrorPropagationService._handle_validation_error(error)
        elif isinstance(error, SQLAlchemyError):
            return ErrorPropagationService._handle_database_error(error)
        else:
            return ErrorPropagationService._handle_unexpected_error(error)
    
    @staticmethod
    def _log_error(error: Exception, request: Request):
        """Log error with appropriate level and context"""
        
        context = {
            "url": str(request.url),
            "method": request.method,
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "error_type": type(error).__name__
        }
        
        if isinstance(error, BaseValidationError):
            if error.severity == ErrorSeverity.CRITICAL:
                logger.critical(f"Critical error: {error.message}", extra=context)
            elif error.severity == ErrorSeverity.HIGH:
                logger.error(f"High severity error: {error.message}", extra=context)
            else:
                logger.warning(f"Error: {error.message}", extra=context)
        else:
            logger.error(f"Unhandled error: {str(error)}", extra=context)
    
    @staticmethod
    def _get_http_status_code(error: BaseValidationError) -> int:
        """Map application errors to HTTP status codes"""
        
        error_status_map = {
            "AUTHENTICATION_ERROR": 401,
            "AUTHORIZATION_ERROR": 403,
            "VALIDATION_ERROR": 400,
            "NOT_FOUND_ERROR": 404,
            "DATABASE_CONNECTION_ERROR": 503,
            "LABJACK_HARDWARE_ERROR": 503,
            "VIDEO_PROCESSING_ERROR": 422,
            "RATE_LIMIT_ERROR": 429
        }
        
        return error_status_map.get(error.error_code, 500)
    
    @staticmethod
    def _handle_validation_error(error: RequestValidationError) -> JSONResponse:
        """Handle Pydantic validation errors"""
        
        validation_details = []
        for err in error.errors():
            validation_details.append({
                "field": ".".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "invalid_value": err.get("input"),
                "error_type": err["type"]
            })
        
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "user_message": "Please check your input and try again.",
                "details": {"validation_errors": validation_details},
                "severity": "medium",
                "recoverable": True
            }
        )
    
    @staticmethod 
    def _handle_database_error(error: SQLAlchemyError) -> JSONResponse:
        """Handle database errors with appropriate responses"""
        
        if isinstance(error, IntegrityError):
            return JSONResponse(
                status_code=400,
                content={
                    "error_code": "DATA_INTEGRITY_ERROR",
                    "message": "Data integrity constraint violated",
                    "user_message": "The data you're trying to save conflicts with existing records.",
                    "details": {"constraint_info": str(error.orig) if error.orig else "Unknown constraint"},
                    "severity": "medium",
                    "recoverable": True
                }
            )
        elif isinstance(error, OperationalError):
            return JSONResponse(
                status_code=503,
                content={
                    "error_code": "DATABASE_OPERATIONAL_ERROR",
                    "message": "Database temporarily unavailable",
                    "user_message": "Service temporarily unavailable. Please try again in a moment.",
                    "severity": "high",
                    "recoverable": True
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "error_code": "DATABASE_ERROR",
                    "message": "Database error occurred",
                    "user_message": "An unexpected error occurred. Please try again.",
                    "severity": "high",
                    "recoverable": True
                }
            )
    
    @staticmethod
    def _handle_unexpected_error(error: Exception) -> JSONResponse:
        """Handle unexpected errors safely"""
        
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "user_message": "Something went wrong. Our team has been notified.",
                "severity": "high",
                "recoverable": True
            }
        )

# Register global error handlers
@app.exception_handler(BaseValidationError)
async def validation_error_handler(request: Request, exc: BaseValidationError):
    return ErrorPropagationService.create_error_response(exc, request)

@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    return ErrorPropagationService.create_error_response(exc, request)

@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    return ErrorPropagationService.create_error_response(exc, request)

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return ErrorPropagationService.create_error_response(exc, request)
```

### 3. Service-Level Error Propagation

#### Service Error Handling Pattern
```python
# Service layer error handling with propagation
from contextlib import asynccontextmanager
from typing import TypeVar, Generic, Optional, Callable

T = TypeVar('T')

class ServiceResult(Generic[T]):
    """Result wrapper for service operations"""
    
    def __init__(self, success: bool, data: Optional[T] = None, error: Optional[Exception] = None):
        self.success = success
        self.data = data
        self.error = error
    
    @classmethod
    def success(cls, data: T) -> 'ServiceResult[T]':
        return cls(success=True, data=data)
    
    @classmethod
    def failure(cls, error: Exception) -> 'ServiceResult[T]':
        return cls(success=False, error=error)

class VideoProcessingService:
    """Video service with comprehensive error handling"""
    
    async def process_video_upload(self, file: UploadFile, project_id: str) -> ServiceResult[Video]:
        """Process video upload with error propagation"""
        
        try:
            # Validate file
            validation_result = await self._validate_video_file(file)
            if not validation_result.success:
                return validation_result
            
            # Store file
            storage_result = await self._store_video_file(file, project_id)
            if not storage_result.success:
                return storage_result
            
            # Extract metadata
            metadata_result = await self._extract_video_metadata(storage_result.data)
            if not metadata_result.success:
                # Cleanup stored file on metadata failure
                await self._cleanup_file(storage_result.data.file_path)
                return metadata_result
            
            # Create database record
            db_result = await self._create_video_record(
                storage_result.data, 
                metadata_result.data, 
                project_id
            )
            if not db_result.success:
                # Cleanup on database failure
                await self._cleanup_file(storage_result.data.file_path)
                return db_result
            
            return ServiceResult.success(db_result.data)
            
        except Exception as e:
            logger.error(f"Unexpected error in video processing: {e}")
            return ServiceResult.failure(
                VideoProcessingError(
                    filename=file.filename or "unknown",
                    stage="processing",
                    reason=str(e)
                )
            )
    
    async def _validate_video_file(self, file: UploadFile) -> ServiceResult[bool]:
        """Validate uploaded video file"""
        try:
            # Check file size
            if file.size and file.size > settings.max_file_size:
                return ServiceResult.failure(
                    VideoProcessingError(
                        filename=file.filename or "unknown",
                        stage="validation",
                        reason=f"File size {file.size} exceeds limit {settings.max_file_size}"
                    )
                )
            
            # Check MIME type
            file_content = await file.read(1024)
            await file.seek(0)  # Reset file pointer
            
            mime_type = magic.from_buffer(file_content, mime=True)
            if mime_type not in settings.allowed_video_types:
                return ServiceResult.failure(
                    VideoProcessingError(
                        filename=file.filename or "unknown",
                        stage="validation",
                        reason=f"Invalid MIME type: {mime_type}"
                    )
                )
            
            return ServiceResult.success(True)
            
        except Exception as e:
            return ServiceResult.failure(
                VideoProcessingError(
                    filename=file.filename or "unknown",
                    stage="validation",
                    reason=str(e)
                )
            )
```

## Frontend Error Handling and Propagation

### 1. Error Boundary Components

#### Cascading Error Boundaries
```typescript
// ErrorBoundary.tsx - React error boundary with recovery
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
  retryCount: number;
}

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ComponentType<ErrorFallbackProps>;
  onError?: (error: Error, errorInfo: ErrorInfo, errorId: string) => void;
  maxRetries?: number;
  retryDelay?: number;
  level?: 'page' | 'section' | 'component';
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private retryTimeoutId: NodeJS.Timeout | null = null;
  private static errorReportingService = new ErrorReportingService();
  
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      retryCount: 0
    };
  }
  
  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    const errorId = `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    return {
      hasError: true,
      error,
      errorId,
      retryCount: 0
    };
  }
  
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const { onError, level = 'component' } = this.props;
    const errorId = this.state.errorId!;
    
    // Enhanced error context
    const errorContext = {
      ...errorInfo,
      level,
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      stack: error.stack,
      props: this.props,
      retryCount: this.state.retryCount
    };
    
    this.setState({ errorInfo });
    
    // Report error
    ErrorBoundary.errorReportingService.reportError(error, errorContext, errorId);
    
    // Propagate to parent error handler
    onError?.(error, errorInfo, errorId);
    
    // Emit global error event
    window.dispatchEvent(new CustomEvent('component-error', {
      detail: { error, errorInfo: errorContext, errorId, level }
    }));
  }
  
  handleRetry = async () => {
    const { maxRetries = 3, retryDelay = 1000 } = this.props;
    
    if (this.state.retryCount >= maxRetries) {
      return; // Max retries exceeded
    }
    
    // Clear any existing timeout
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
    
    // Calculate exponential backoff delay
    const delay = retryDelay * Math.pow(2, this.state.retryCount);
    
    this.retryTimeoutId = setTimeout(() => {
      this.setState(prevState => ({
        hasError: false,
        error: null,
        errorInfo: null,
        errorId: null,
        retryCount: prevState.retryCount + 1
      }));
    }, delay);
  };
  
  render() {
    if (this.state.hasError) {
      const FallbackComponent = this.props.fallback || DefaultErrorFallback;
      
      return (
        <FallbackComponent
          error={this.state.error}
          errorInfo={this.state.errorInfo}
          errorId={this.state.errorId}
          retryCount={this.state.retryCount}
          maxRetries={this.props.maxRetries || 3}
          onRetry={this.handleRetry}
          level={this.props.level || 'component'}
        />
      );
    }
    
    return this.props.children;
  }
  
  componentWillUnmount() {
    if (this.retryTimeoutId) {
      clearTimeout(this.retryTimeoutId);
    }
  }
}

// Specialized error fallback components
interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
  retryCount: number;
  maxRetries: number;
  onRetry: () => void;
  level: string;
}

const DefaultErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  errorId,
  retryCount,
  maxRetries,
  onRetry,
  level
}) => {
  const canRetry = retryCount < maxRetries;
  const isComponentLevel = level === 'component';
  
  return (
    <div className={`error-fallback error-fallback--${level}`}>
      <div className="error-content">
        <h3>
          {isComponentLevel ? 'Component Error' : 'Something went wrong'}
        </h3>
        <p className="error-message">
          {error?.message || 'An unexpected error occurred'}
        </p>
        
        {errorId && (
          <p className="error-id">
            Error ID: <code>{errorId}</code>
          </p>
        )}
        
        <div className="error-actions">
          {canRetry && (
            <button 
              onClick={onRetry}
              className="retry-button"
              disabled={retryCount > 0}
            >
              {retryCount > 0 ? `Retrying... (${retryCount}/${maxRetries})` : 'Try Again'}
            </button>
          )}
          
          <button 
            onClick={() => window.location.reload()}
            className="reload-button"
          >
            Reload Page
          </button>
          
          {process.env.NODE_ENV === 'development' && (
            <details className="error-details">
              <summary>Error Details</summary>
              <pre>{error?.stack}</pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
};
```

### 2. API Error Handling and Propagation

#### Enhanced API Error Processing
```typescript
// services/errorService.ts - Centralized error handling
export interface ApiError {
  errorCode: string;
  message: string;
  userMessage: string;
  details?: any;
  severity: 'low' | 'medium' | 'high' | 'critical';
  recoverable: boolean;
  timestamp: string;
}

export interface ErrorContext {
  url: string;
  method: string;
  requestData?: any;
  responseStatus?: number;
  userAgent: string;
  timestamp: string;
}

export class ErrorHandlingService {
  private static instance: ErrorHandlingService;
  private errorQueue: Array<{ error: ApiError; context: ErrorContext }> = [];
  private errorHandlers = new Map<string, (error: ApiError) => void>();
  
  static getInstance(): ErrorHandlingService {
    if (!ErrorHandlingService.instance) {
      ErrorHandlingService.instance = new ErrorHandlingService();
    }
    return ErrorHandlingService.instance;
  }
  
  /**
   * Process API error and determine appropriate handling
   */
  handleApiError(error: AxiosError, requestContext?: any): ApiError {
    const apiError = this.transformAxiosError(error);
    const context = this.buildErrorContext(error, requestContext);
    
    // Queue error for batch processing
    this.errorQueue.push({ error: apiError, context });
    
    // Process error based on severity
    this.processErrorBySeverity(apiError, context);
    
    // Emit error event for component consumption
    this.emitErrorEvent(apiError, context);
    
    return apiError;
  }
  
  private transformAxiosError(error: AxiosError): ApiError {
    // Handle structured API errors
    if (error.response?.data && typeof error.response.data === 'object') {
      const responseData = error.response.data as any;
      
      if (responseData.error_code || responseData.errorCode) {
        return {
          errorCode: responseData.error_code || responseData.errorCode,
          message: responseData.message || 'Unknown error',
          userMessage: responseData.user_message || responseData.userMessage || 'An error occurred',
          details: responseData.details,
          severity: responseData.severity || 'medium',
          recoverable: responseData.recoverable !== false,
          timestamp: responseData.timestamp || new Date().toISOString()
        };
      }
    }
    
    // Handle HTTP status code errors
    if (error.response) {
      return this.createErrorFromStatus(error.response.status, error.response.statusText);
    }
    
    // Handle network errors
    if (error.request) {
      return {
        errorCode: 'NETWORK_ERROR',
        message: 'Network request failed',
        userMessage: 'Unable to connect to the server. Please check your internet connection.',
        severity: 'high',
        recoverable: true,
        timestamp: new Date().toISOString()
      };
    }
    
    // Handle request setup errors
    return {
      errorCode: 'REQUEST_ERROR',
      message: error.message,
      userMessage: 'Failed to process request',
      severity: 'medium',
      recoverable: true,
      timestamp: new Date().toISOString()
    };
  }
  
  private createErrorFromStatus(status: number, statusText: string): ApiError {
    const statusErrorMap: Record<number, Partial<ApiError>> = {
      400: {
        errorCode: 'BAD_REQUEST',
        userMessage: 'Invalid request. Please check your input and try again.'
      },
      401: {
        errorCode: 'UNAUTHORIZED',
        userMessage: 'Please log in to continue.',
        severity: 'medium'
      },
      403: {
        errorCode: 'FORBIDDEN',
        userMessage: 'You do not have permission to perform this action.',
        severity: 'medium'
      },
      404: {
        errorCode: 'NOT_FOUND',
        userMessage: 'The requested resource was not found.'
      },
      422: {
        errorCode: 'VALIDATION_ERROR',
        userMessage: 'Please check your input and try again.'
      },
      429: {
        errorCode: 'RATE_LIMITED',
        userMessage: 'Too many requests. Please try again later.',
        severity: 'medium'
      },
      500: {
        errorCode: 'INTERNAL_SERVER_ERROR',
        userMessage: 'Server error. Please try again later.',
        severity: 'high'
      },
      502: {
        errorCode: 'BAD_GATEWAY',
        userMessage: 'Service temporarily unavailable.',
        severity: 'high'
      },
      503: {
        errorCode: 'SERVICE_UNAVAILABLE',
        userMessage: 'Service temporarily unavailable. Please try again later.',
        severity: 'high'
      }
    };
    
    const errorConfig = statusErrorMap[status] || {};
    
    return {
      errorCode: errorConfig.errorCode || 'HTTP_ERROR',
      message: `HTTP ${status}: ${statusText}`,
      userMessage: errorConfig.userMessage || 'An error occurred',
      severity: errorConfig.severity || 'medium',
      recoverable: true,
      timestamp: new Date().toISOString()
    };
  }
  
  private buildErrorContext(error: AxiosError, requestContext?: any): ErrorContext {
    return {
      url: error.config?.url || 'unknown',
      method: (error.config?.method || 'unknown').toUpperCase(),
      requestData: error.config?.data,
      responseStatus: error.response?.status,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString(),
      ...requestContext
    };
  }
  
  private processErrorBySeverity(error: ApiError, context: ErrorContext) {
    switch (error.severity) {
      case 'critical':
        this.handleCriticalError(error, context);
        break;
      case 'high':
        this.handleHighSeverityError(error, context);
        break;
      case 'medium':
        this.handleMediumSeverityError(error, context);
        break;
      case 'low':
        this.handleLowSeverityError(error, context);
        break;
    }
  }
  
  private handleCriticalError(error: ApiError, context: ErrorContext) {
    // Log critical errors immediately
    console.error('Critical error occurred:', error, context);
    
    // Send to error reporting service immediately
    this.reportErrorImmediately(error, context);
    
    // Show user notification
    this.showErrorNotification(error, { 
      type: 'error',
      persistent: true,
      actions: ['reload', 'contact-support']
    });
  }
  
  private handleHighSeverityError(error: ApiError, context: ErrorContext) {
    console.error('High severity error:', error, context);
    
    // Show prominent error notification
    this.showErrorNotification(error, { 
      type: 'error',
      timeout: 10000,
      actions: error.recoverable ? ['retry', 'dismiss'] : ['dismiss']
    });
  }
  
  private handleMediumSeverityError(error: ApiError, context: ErrorContext) {
    console.warn('Medium severity error:', error, context);
    
    // Show standard error notification
    this.showErrorNotification(error, { 
      type: 'warning',
      timeout: 5000,
      actions: error.recoverable ? ['retry'] : []
    });
  }
  
  private handleLowSeverityError(error: ApiError, context: ErrorContext) {
    console.info('Low severity error:', error, context);
    
    // Show subtle notification or just log
    if (error.userMessage) {
      this.showErrorNotification(error, { 
        type: 'info',
        timeout: 3000
      });
    }
  }
  
  private emitErrorEvent(error: ApiError, context: ErrorContext) {
    // Emit custom event for component consumption
    window.dispatchEvent(new CustomEvent('api-error', {
      detail: { error, context }
    }));
    
    // Call registered error handlers
    const handler = this.errorHandlers.get(error.errorCode);
    if (handler) {
      try {
        handler(error);
      } catch (handlerError) {
        console.error('Error in custom error handler:', handlerError);
      }
    }
  }
  
  /**
   * Register custom error handler for specific error codes
   */
  registerErrorHandler(errorCode: string, handler: (error: ApiError) => void) {
    this.errorHandlers.set(errorCode, handler);
  }
  
  /**
   * Show user notification for errors
   */
  private showErrorNotification(error: ApiError, options: {
    type: 'error' | 'warning' | 'info';
    timeout?: number;
    persistent?: boolean;
    actions?: string[];
  }) {
    // Integration with notification system
    const notificationService = NotificationService.getInstance();
    notificationService.show({
      id: `error_${Date.now()}`,
      type: options.type,
      title: options.type === 'error' ? 'Error' : 'Warning',
      message: error.userMessage,
      timeout: options.persistent ? 0 : (options.timeout || 5000),
      actions: options.actions?.map(action => ({
        label: this.getActionLabel(action),
        handler: () => this.handleNotificationAction(action, error)
      }))
    });
  }
  
  private getActionLabel(action: string): string {
    const actionLabels: Record<string, string> = {
      'retry': 'Try Again',
      'dismiss': 'Dismiss',
      'reload': 'Reload Page',
      'contact-support': 'Contact Support'
    };
    return actionLabels[action] || action;
  }
  
  private handleNotificationAction(action: string, error: ApiError) {
    switch (action) {
      case 'retry':
        // Emit retry event for component to handle
        window.dispatchEvent(new CustomEvent('error-retry', {
          detail: { error }
        }));
        break;
      case 'reload':
        window.location.reload();
        break;
      case 'contact-support':
        // Open support contact with error details
        this.openSupportContact(error);
        break;
    }
  }
  
  private async reportErrorImmediately(error: ApiError, context: ErrorContext) {
    try {
      // Send to error reporting service
      await fetch('/api/errors/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ error, context })
      });
    } catch (reportingError) {
      console.error('Failed to report error:', reportingError);
    }
  }
  
  private openSupportContact(error: ApiError) {
    const supportUrl = `mailto:support@company.com?subject=Error Report&body=Error ID: ${error.timestamp}%0AError: ${error.errorCode}%0AMessage: ${error.message}`;
    window.open(supportUrl, '_blank');
  }
}

// Global error handler setup
const errorHandlingService = ErrorHandlingService.getInstance();

// Register specific error handlers
errorHandlingService.registerErrorHandler('AUTHENTICATION_ERROR', (error) => {
  // Redirect to login
  window.location.href = '/login';
});

errorHandlingService.registerErrorHandler('LABJACK_HARDWARE_ERROR', (error) => {
  // Show hardware error dialog with mock mode option
  const event = new CustomEvent('show-hardware-error-dialog', {
    detail: { error }
  });
  window.dispatchEvent(event);
});
```

### 3. Component-Level Error Recovery

#### Resilient Component Pattern
```typescript
// hooks/useErrorRecovery.ts - Error recovery hook
interface ErrorRecoveryOptions {
  maxRetries?: number;
  retryDelay?: number;
  fallbackData?: any;
  onError?: (error: Error) => void;
  onRecovery?: () => void;
}

export const useErrorRecovery = <T>(
  operation: () => Promise<T>,
  dependencies: any[],
  options: ErrorRecoveryOptions = {}
) => {
  const {
    maxRetries = 3,
    retryDelay = 1000,
    fallbackData = null,
    onError,
    onRecovery
  } = options;
  
  const [state, setState] = useState<{
    data: T | null;
    loading: boolean;
    error: Error | null;
    retryCount: number;
  }>({
    data: null,
    loading: false,
    error: null,
    retryCount: 0
  });
  
  const executeOperation = useCallback(async (isRetry = false) => {
    setState(prev => ({ 
      ...prev, 
      loading: true, 
      error: null 
    }));
    
    try {
      const result = await operation();
      setState(prev => ({ 
        ...prev, 
        data: result, 
        loading: false, 
        error: null,
        retryCount: isRetry ? prev.retryCount + 1 : 0
      }));
      
      if (isRetry && onRecovery) {
        onRecovery();
      }
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Unknown error');
      
      setState(prev => ({ 
        ...prev, 
        loading: false, 
        error: err,
        retryCount: isRetry ? prev.retryCount + 1 : 0
      }));
      
      onError?.(err);
      
      // Auto-retry for certain types of errors
      if (state.retryCount < maxRetries && isRecoverableError(err)) {
        setTimeout(() => {
          executeOperation(true);
        }, retryDelay * Math.pow(2, state.retryCount));
      }
    }
  }, [operation, state.retryCount, maxRetries, retryDelay, onError, onRecovery]);
  
  // Execute operation when dependencies change
  useEffect(() => {
    executeOperation();
  }, dependencies);
  
  const retry = useCallback(() => {
    if (state.retryCount < maxRetries) {
      executeOperation(true);
    }
  }, [executeOperation, state.retryCount, maxRetries]);
  
  return {
    data: state.data || fallbackData,
    loading: state.loading,
    error: state.error,
    retryCount: state.retryCount,
    canRetry: state.retryCount < maxRetries,
    retry
  };
};

function isRecoverableError(error: Error): boolean {
  const recoverableErrors = [
    'NetworkError',
    'TimeoutError',
    'ServiceUnavailableError',
    'InternalServerError'
  ];
  
  return recoverableErrors.some(errorType => 
    error.name.includes(errorType) || error.message.includes(errorType)
  );
}

// Usage in component
export const ResilientVideoPlayer: React.FC<{ videoId: string }> = ({ videoId }) => {
  const { data: video, loading, error, retry, canRetry } = useErrorRecovery(
    () => apiService.getVideo(videoId),
    [videoId],
    {
      maxRetries: 3,
      fallbackData: null,
      onError: (error) => {
        console.error('Failed to load video:', error);
      },
      onRecovery: () => {
        console.log('Video loading recovered');
      }
    }
  );
  
  if (loading) {
    return <LoadingSpinner />;
  }
  
  if (error) {
    return (
      <ErrorFallback
        error={error}
        canRetry={canRetry}
        onRetry={retry}
        fallbackContent={<div>Unable to load video</div>}
      />
    );
  }
  
  return video ? <VideoPlayer video={video} /> : <div>No video found</div>;
};
```

## WebSocket Error Handling

### Real-Time Error Propagation
```typescript
// WebSocket error handling with recovery
export class WebSocketErrorHandler {
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseReconnectDelay = 1000;
  
  handleConnectionError(error: Error, socket: Socket | null): void {
    console.error('WebSocket connection error:', error);
    
    const errorEvent: WebSocketErrorEvent = {
      type: 'connection_error',
      error: error.message,
      timestamp: Date.now(),
      reconnectAttempt: this.reconnectAttempts,
      canReconnect: this.reconnectAttempts < this.maxReconnectAttempts
    };
    
    // Emit error event for UI handling
    this.emitErrorEvent(errorEvent);
    
    // Attempt reconnection with exponential backoff
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
      this.scheduleReconnect(delay);
    } else {
      // Max attempts reached - switch to fallback mode
      this.enterFallbackMode();
    }
  }
  
  handleMessageError(error: Error, message: any): void {
    console.error('WebSocket message error:', error, message);
    
    const errorEvent: WebSocketErrorEvent = {
      type: 'message_error',
      error: error.message,
      message,
      timestamp: Date.now(),
      severity: this.determineSeverity(error, message)
    };
    
    this.emitErrorEvent(errorEvent);
    
    // Request message resend if possible
    if (message?.messageId) {
      this.requestMessageResend(message.messageId);
    }
  }
  
  private scheduleReconnect(delay: number): void {
    setTimeout(() => {
      this.reconnectAttempts++;
      // Trigger reconnection (handled by WebSocket hook)
      window.dispatchEvent(new CustomEvent('websocket-reconnect'));
    }, delay);
  }
  
  private enterFallbackMode(): void {
    // Switch to HTTP polling as fallback
    window.dispatchEvent(new CustomEvent('websocket-fallback-mode'));
    
    this.emitErrorEvent({
      type: 'fallback_mode',
      error: 'WebSocket reconnection failed',
      timestamp: Date.now(),
      severity: 'high'
    });
  }
  
  private emitErrorEvent(event: WebSocketErrorEvent): void {
    window.dispatchEvent(new CustomEvent('websocket-error', {
      detail: event
    }));
  }
}
```

## Future Error Handling Enhancements

### Planned Improvements

1. **Advanced Error Analytics**
   - Error pattern detection
   - Automated error classification
   - Predictive error prevention

2. **Enhanced Recovery Mechanisms**
   - Circuit breaker patterns
   - Graceful degradation modes
   - Self-healing capabilities

3. **User Experience Improvements**
   - Context-aware error messages
   - Progressive error disclosure
   - Guided error recovery flows

4. **Monitoring and Alerting**
   - Real-time error dashboards
   - Automated error reporting
   - Performance impact analysis

5. **Testing and Validation**
   - Error simulation frameworks
   - Chaos engineering integration
   - Recovery testing automation