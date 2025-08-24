"""
Enhanced logging configuration for the AI Model Validation Platform.

Provides structured logging with security-aware features including:
- Sanitized log messages (no sensitive data)
- Configurable log levels
- File rotation
- JSON structured logs for production
- Security event logging
"""

import os
import sys
import logging
import logging.config
import logging.handlers
import json
from datetime import datetime
from typing import Dict, Any, Optional
import traceback

from config import Settings

class SecurityAwareFormatter(logging.Formatter):
    """
    Custom log formatter that sanitizes sensitive information from log messages.
    """
    
    SENSITIVE_PATTERNS = [
        'password', 'passwd', 'secret', 'key', 'token', 'auth',
        'credential', 'api_key', 'private', 'confidential'
    ]
    
    def format(self, record: logging.LogRecord) -> str:
        # Create a copy of the record to avoid modifying the original
        record_copy = logging.makeLogRecord(record.__dict__)
        
        # Sanitize the message
        record_copy.msg = self._sanitize_message(str(record_copy.msg))
        
        # Sanitize any args
        if record_copy.args:
            record_copy.args = tuple(
                self._sanitize_message(str(arg)) if isinstance(arg, str) else arg 
                for arg in record_copy.args
            )
        
        return super().format(record_copy)
    
    def _sanitize_message(self, message: str) -> str:
        """Remove or mask sensitive information from log messages"""
        message_lower = message.lower()
        
        for pattern in self.SENSITIVE_PATTERNS:
            if pattern in message_lower:
                # Mask sensitive values after common patterns
                import re
                
                # Pattern: key=value or key: value
                pattern_regex = rf'({pattern}[=:]\s*)([^\s,\]}}]+)'
                message = re.sub(
                    pattern_regex, 
                    r'\1***MASKED***', 
                    message, 
                    flags=re.IGNORECASE
                )
                
                # Pattern: "password": "value"
                pattern_regex = rf'("{pattern}":\s*")([^"]+)(")'
                message = re.sub(
                    pattern_regex, 
                    r'\1***MASKED***\3', 
                    message, 
                    flags=re.IGNORECASE
                )
                
        return message

class JSONFormatter(SecurityAwareFormatter):
    """
    JSON formatter for structured logging in production environments.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Get the basic formatted message
        message = super().format(record)
        
        # Create JSON log structure
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': message,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add process and thread info
        log_entry['process_id'] = os.getpid()
        log_entry['thread_id'] = record.thread
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        return json.dumps(log_entry, ensure_ascii=False)

class SecurityEventLogger:
    """
    Specialized logger for security events.
    """
    
    def __init__(self, logger_name: str = 'security'):
        self.logger = logging.getLogger(logger_name)
    
    def log_authentication_attempt(self, user_id: str, success: bool, ip_address: str):
        """Log authentication attempts"""
        event = {
            'event_type': 'authentication_attempt',
            'user_id': user_id,
            'success': success,
            'ip_address': ip_address,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if success:
            self.logger.info(f"Authentication successful for user {user_id}", extra={'extra_data': event})
        else:
            self.logger.warning(f"Authentication failed for user {user_id}", extra={'extra_data': event})
    
    def log_authorization_failure(self, user_id: str, resource: str, action: str, ip_address: str):
        """Log authorization failures"""
        event = {
            'event_type': 'authorization_failure',
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'ip_address': ip_address,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.warning(f"Authorization failed: user {user_id} attempted {action} on {resource}", 
                          extra={'extra_data': event})
    
    def log_rate_limit_exceeded(self, client_id: str, endpoint: str, attempts: int):
        """Log rate limit violations"""
        event = {
            'event_type': 'rate_limit_exceeded',
            'client_id': client_id,
            'endpoint': endpoint,
            'attempts': attempts,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.warning(f"Rate limit exceeded by {client_id} on {endpoint} ({attempts} attempts)", 
                          extra={'extra_data': event})
    
    def log_suspicious_activity(self, description: str, details: Dict[str, Any]):
        """Log suspicious activities"""
        event = {
            'event_type': 'suspicious_activity',
            'description': description,
            'details': details,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.error(f"Suspicious activity detected: {description}", 
                         extra={'extra_data': event})

def setup_logging(settings: Settings) -> None:
    """
    Setup comprehensive logging configuration based on settings.
    """
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(settings.log_file) if settings.log_file else 'logs'
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Determine if we should use JSON logging (production)
    use_json_logging = settings.app_environment.lower() == 'production'
    
    # Configure formatters
    if use_json_logging:
        formatter_class = JSONFormatter
        format_string = None  # Not used for JSON formatter
    else:
        formatter_class = SecurityAwareFormatter
        format_string = settings.log_format
    
    # Base logging configuration
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'default': {
                '()': formatter_class,
                'format': format_string,
            },
            'security': {
                '()': JSONFormatter,  # Always use JSON for security events
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': settings.log_level,
                'formatter': 'default',
                'stream': sys.stdout,
            },
        },
        'loggers': {
            '': {  # Root logger
                'level': settings.log_level,
                'handlers': ['console'],
                'propagate': False,
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'uvicorn.access': {
                'level': 'WARNING',  # Reduce noise from access logs
                'handlers': ['console'],
                'propagate': False,
            },
            'sqlalchemy.engine': {
                'level': 'WARNING',  # Reduce database query noise
                'handlers': ['console'],
                'propagate': False,
            },
            'security': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            }
        }
    }
    
    # Add file handler if log file is specified
    if settings.log_file:
        # Main application log file
        logging_config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': settings.log_level,
            'formatter': 'default',
            'filename': settings.log_file,
            'maxBytes': settings.log_max_bytes,
            'backupCount': settings.log_backup_count,
            'encoding': 'utf-8',
        }
        
        # Security events log file
        security_log_file = settings.log_file.replace('.log', '_security.log')
        logging_config['handlers']['security_file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'security',
            'filename': security_log_file,
            'maxBytes': settings.log_max_bytes,
            'backupCount': settings.log_backup_count,
            'encoding': 'utf-8',
        }
        
        # Add file handlers to loggers
        for logger_name in ['', 'uvicorn', 'uvicorn.access', 'sqlalchemy.engine']:
            logging_config['loggers'][logger_name]['handlers'].append('file')
        
        logging_config['loggers']['security']['handlers'].append('security_file')
    
    # Apply logging configuration
    logging.config.dictConfig(logging_config)
    
    # Log configuration summary
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {settings.log_level}")
    logger.info(f"Environment: {settings.app_environment}")
    
    if settings.log_file:
        logger.info(f"Logging to file: {settings.log_file}")
        logger.info(f"Log rotation: {settings.log_max_bytes / 1024 / 1024:.1f}MB x {settings.log_backup_count} files")
    
    if use_json_logging:
        logger.info("JSON structured logging enabled for production")
    
    # Test security logger
    security_logger = SecurityEventLogger()
    security_logger.logger.info("Security logging system initialized")

class LoggingContextManager:
    """
    Context manager for adding contextual information to logs.
    """
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_factory = None
    
    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)

# Utility functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger with security-aware formatting"""
    return logging.getLogger(name)

def log_with_context(logger: logging.Logger, **context):
    """Context manager for adding context to log messages"""
    return LoggingContextManager(logger, **context)

# Global security event logger instance
security_logger = SecurityEventLogger()

# Example usage:
# from logging_config import security_logger
# security_logger.log_authentication_attempt("user123", True, "192.168.1.1")