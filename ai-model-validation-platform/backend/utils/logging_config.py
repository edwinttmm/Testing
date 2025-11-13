"""
Production-Grade Structured Logging Configuration

Provides JSON-formatted logging for production observability with:
- Structured log messages for easy parsing
- Request correlation IDs
- Performance metrics
- Error context enrichment
- ELK/CloudWatch compatibility
"""

import logging
import json
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variable for request correlation
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class StructuredLogger:
    """JSON structured logging for production with correlation IDs"""

    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Prevent duplicate handlers
        if not self.logger.handlers:
            # JSON formatter for production
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)

    def _build_extra(self, **kwargs) -> Dict[str, Any]:
        """Build extra data dict with correlation ID"""
        extra = kwargs.copy()
        correlation_id = correlation_id_var.get()
        if correlation_id:
            extra['correlation_id'] = correlation_id
        return extra

    def info(self, message: str, **kwargs):
        """Log info level with structured data"""
        self.logger.info(message, extra=self._build_extra(**kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning level with structured data"""
        self.logger.warning(message, extra=self._build_extra(**kwargs))

    def error(self, message: str, exc_info: bool = False, **kwargs):
        """Log error level with structured data and optional exception"""
        self.logger.error(message, exc_info=exc_info, extra=self._build_extra(**kwargs))

    def critical(self, message: str, exc_info: bool = False, **kwargs):
        """Log critical level with structured data"""
        self.logger.critical(message, exc_info=exc_info, extra=self._build_extra(**kwargs))

    def debug(self, message: str, **kwargs):
        """Log debug level with structured data"""
        self.logger.debug(message, extra=self._build_extra(**kwargs))


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add correlation ID if present
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_data['correlation_id'] = correlation_id

        # Add any extra fields from log call
        if hasattr(record, 'session_id'):
            log_data['session_id'] = record.session_id
        if hasattr(record, 'video_id'):
            log_data['video_id'] = record.video_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'metrics'):
            log_data['metrics'] = record.metrics
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'endpoint'):
            log_data['endpoint'] = record.endpoint
        if hasattr(record, 'status_code'):
            log_data['status_code'] = record.status_code

        # Add exception information if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': ''.join(traceback.format_exception(*record.exc_info))
            }

        # Add stack trace for errors
        if record.levelno >= logging.ERROR and record.stack_info:
            log_data['stack_trace'] = record.stack_info

        return json.dumps(log_data)


def set_correlation_id(correlation_id: str):
    """Set correlation ID for current request context"""
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current request context"""
    return correlation_id_var.get()


def clear_correlation_id():
    """Clear correlation ID from current request context"""
    correlation_id_var.set(None)


# Pre-configured loggers for common modules
session_logger = StructuredLogger('session')
detection_logger = StructuredLogger('detection')
matching_logger = StructuredLogger('matching')
api_logger = StructuredLogger('api')
database_logger = StructuredLogger('database')
websocket_logger = StructuredLogger('websocket')


# Example usage patterns
"""
# Basic usage
from utils.logging_config import session_logger

session_logger.info(
    "Session completed successfully",
    session_id=session_id,
    metrics={
        'precision': 0.85,
        'recall': 0.78,
        'f1_score': 0.81
    },
    duration_ms=1523.4
)

# Error logging with exception
try:
    process_session(session_id)
except Exception as e:
    session_logger.error(
        "Session processing failed",
        exc_info=True,
        session_id=session_id,
        error_type=type(e).__name__
    )

# With correlation ID
from utils.logging_config import set_correlation_id, api_logger

set_correlation_id(request_id)
api_logger.info(
    "API request received",
    endpoint="/api/sessions",
    method="POST"
)
"""
