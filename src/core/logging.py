"""
Logging configuration for VRU Detection System
"""

import logging
import logging.config
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from src.core.config import settings


def setup_logging() -> None:
    """Setup application logging configuration"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"vru_detection_{timestamp}.log"
    
    # Logging configuration
    config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": settings.LOG_FORMAT,
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "()": JsonFormatter,
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.LOG_LEVEL,
                "formatter": "standard",
                "stream": sys.stdout
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "detailed",
                "filename": str(log_file),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": str(log_dir / f"vru_detection_errors_{timestamp}.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8"
            }
        },
        "loggers": {
            "src": {
                "level": settings.LOG_LEVEL,
                "handlers": ["console", "file", "error_file"],
                "propagate": False
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False
            },
            "sqlalchemy.engine": {
                "level": "WARNING" if not settings.DATABASE_ECHO else "INFO",
                "handlers": ["file"],
                "propagate": False
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "file"]
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")
    logger.info(f"Log level: {settings.LOG_LEVEL}")
    logger.info(f"Log file: {log_file}")


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        import json
        
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "getMessage", "exc_info",
                "exc_text", "stack_info"
            }:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class RequestLogger:
    """Request logging middleware helper"""
    
    @staticmethod
    def log_request(request, response, processing_time: float) -> None:
        """Log HTTP request details"""
        logger = logging.getLogger("src.api")
        
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "processing_time_ms": round(processing_time * 1000, 2),
            "user_agent": request.headers.get("user-agent"),
            "client_ip": request.client.host if request.client else None,
            "request_id": getattr(request.state, "request_id", None)
        }
        
        # Log level based on status code
        if response.status_code >= 500:
            logger.error("HTTP Request", extra=log_data)
        elif response.status_code >= 400:
            logger.warning("HTTP Request", extra=log_data)
        else:
            logger.info("HTTP Request", extra=log_data)


class PerformanceLogger:
    """Performance logging for detection and processing"""
    
    @staticmethod
    def log_detection_performance(
        video_id: str,
        frames_processed: int,
        detections_found: int,
        processing_time_ms: float,
        average_confidence: float
    ) -> None:
        """Log detection performance metrics"""
        logger = logging.getLogger("src.detection")
        
        fps = frames_processed / (processing_time_ms / 1000) if processing_time_ms > 0 else 0
        
        log_data = {
            "video_id": video_id,
            "frames_processed": frames_processed,
            "detections_found": detections_found,
            "processing_time_ms": processing_time_ms,
            "average_confidence": average_confidence,
            "fps": round(fps, 2),
            "detections_per_frame": round(detections_found / frames_processed, 3) if frames_processed > 0 else 0
        }
        
        logger.info("Detection Performance", extra=log_data)
    
    @staticmethod
    def log_validation_performance(
        test_session_id: str,
        precision: float,
        recall: float,
        f1_score: float,
        latency_ms: float
    ) -> None:
        """Log validation performance metrics"""
        logger = logging.getLogger("src.validation")
        
        log_data = {
            "test_session_id": test_session_id,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "latency_ms": latency_ms
        }
        
        logger.info("Validation Performance", extra=log_data)


class SecurityLogger:
    """Security event logging"""
    
    @staticmethod
    def log_authentication_attempt(
        username: str,
        success: bool,
        ip_address: str,
        user_agent: str
    ) -> None:
        """Log authentication attempts"""
        logger = logging.getLogger("src.security")
        
        log_data = {
            "event": "authentication_attempt",
            "username": username,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent
        }
        
        if success:
            logger.info("Authentication Success", extra=log_data)
        else:
            logger.warning("Authentication Failure", extra=log_data)
    
    @staticmethod
    def log_unauthorized_access(
        resource: str,
        user_id: str,
        ip_address: str
    ) -> None:
        """Log unauthorized access attempts"""
        logger = logging.getLogger("src.security")
        
        log_data = {
            "event": "unauthorized_access",
            "resource": resource,
            "user_id": user_id,
            "ip_address": ip_address
        }
        
        logger.warning("Unauthorized Access", extra=log_data)


class AuditLogger:
    """Audit trail logging"""
    
    @staticmethod
    def log_data_modification(
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        changes: dict
    ) -> None:
        """Log data modification events"""
        logger = logging.getLogger("src.audit")
        
        log_data = {
            "event": "data_modification",
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "changes": changes
        }
        
        logger.info("Data Modification", extra=log_data)
    
    @staticmethod
    def log_system_event(
        event_type: str,
        description: str,
        metadata: dict = None
    ) -> None:
        """Log system events"""
        logger = logging.getLogger("src.audit")
        
        log_data = {
            "event": "system_event",
            "event_type": event_type,
            "description": description,
            "metadata": metadata or {}
        }
        
        logger.info("System Event", extra=log_data)