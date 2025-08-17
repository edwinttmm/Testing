"""
Configuration settings for VRU Detection System
"""

import os
from typing import List, Optional, Any, Dict
from pydantic import BaseSettings, validator, Field
from pathlib import Path


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Application settings
    APP_NAME: str = "VRU Detection System"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Security settings
    SECRET_KEY: str = Field(..., min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Database settings
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False
    
    # File storage settings
    UPLOAD_DIR: Path = Path("uploads")
    VIDEO_STORAGE_DIR: Path = Path("storage/videos")
    SCREENSHOT_STORAGE_DIR: Path = Path("storage/screenshots")
    MAX_FILE_SIZE_MB: int = 10240  # 10GB
    ALLOWED_VIDEO_FORMATS: List[str] = ["mp4", "avi", "mov", "mkv"]
    
    # ML Model settings
    MODEL_DIR: Path = Path("models")
    DEFAULT_MODEL_NAME: str = "yolov8n.pt"
    MODEL_CACHE_SIZE: int = 3
    BATCH_SIZE: int = 8
    MAX_GPU_MEMORY_GB: float = 8.0
    
    # Detection settings
    VRU_CLASSES: Dict[str, int] = {
        "pedestrian": 0,
        "cyclist": 1,
        "motorcyclist": 2,
        "wheelchair_user": 3,
        "scooter_rider": 4,
        "child_with_stroller": 5
    }
    
    MIN_CONFIDENCE_THRESHOLD: float = 0.5
    NMS_THRESHOLD: float = 0.45
    MAX_DETECTION_LATENCY_MS: int = 50
    
    # Video processing settings
    FRAME_EXTRACTION_FPS: int = 30
    MAX_VIDEO_DURATION_MINUTES: int = 60
    VIDEO_RESOLUTION_MIN: tuple = (640, 480)
    VIDEO_RESOLUTION_MAX: tuple = (3840, 2160)  # 4K
    
    # Signal processing settings
    SIGNAL_SAMPLING_RATE_HZ: float = 1000.0
    SIGNAL_BUFFER_SIZE: int = 1000
    HIGH_PRECISION_TIMING: bool = True
    DEFAULT_TOLERANCE_MS: int = 100
    
    # Background task settings
    CLEANUP_INTERVAL_HOURS: int = 24
    SCREENSHOT_RETENTION_DAYS: int = 30
    ARCHIVE_DATA_AFTER_DAYS: int = 90
    
    # Monitoring and logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # Performance settings
    MAX_CONCURRENT_DETECTIONS: int = 4
    WORKER_THREADS: int = 4
    ASYNC_POOL_SIZE: int = 10
    
    # Development settings
    MOCK_DETECTION_ENGINE: bool = False
    MOCK_SIGNAL_PROCESSOR: bool = False
    ENABLE_PROFILING: bool = False
    
    @validator("UPLOAD_DIR", "VIDEO_STORAGE_DIR", "SCREENSHOT_STORAGE_DIR", "MODEL_DIR")
    def create_directories(cls, v):
        """Ensure directories exist"""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL")
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        """Ensure secret key is secure"""
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v
    
    @validator("ALLOWED_ORIGINS")
    def validate_origins(cls, v):
        """Validate CORS origins"""
        if not v:
            return ["*"]  # Allow all origins if none specified
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Detection-specific configurations
class DetectionConfig:
    """Detection engine configuration"""
    
    # Model confidence thresholds per class
    CONFIDENCE_THRESHOLDS = {
        "pedestrian": 0.70,
        "cyclist": 0.75,
        "motorcyclist": 0.80,
        "wheelchair_user": 0.65,
        "scooter_rider": 0.70,
        "child_with_stroller": 0.75
    }
    
    # NMS thresholds per class
    NMS_THRESHOLDS = {
        "pedestrian": 0.45,
        "cyclist": 0.40,
        "motorcyclist": 0.35,
        "wheelchair_user": 0.50,
        "scooter_rider": 0.45,
        "child_with_stroller": 0.45
    }
    
    # Detection validation rules
    MIN_BOUNDING_BOX_AREA = 100  # pixels
    MAX_BOUNDING_BOX_AREA = 500000  # pixels
    MIN_ASPECT_RATIO = 0.2
    MAX_ASPECT_RATIO = 5.0
    
    # Performance targets
    TARGET_FPS = 30
    MAX_PROCESSING_LATENCY_MS = 50
    MEMORY_LIMIT_MB = 4096


class SignalConfig:
    """Signal processing configuration"""
    
    # Signal types and their configurations
    SIGNAL_TYPES = {
        "GPIO": {
            "sampling_rate": 1000.0,
            "buffer_size": 1000,
            "debounce_ms": 10,
            "noise_threshold": 0.1
        },
        "Network": {
            "sampling_rate": 100.0,
            "buffer_size": 100,
            "timeout_ms": 1000,
            "retry_count": 3
        },
        "Serial": {
            "sampling_rate": 1000.0,
            "buffer_size": 1000,
            "baud_rate": 115200,
            "timeout_ms": 100
        },
        "CAN_Bus": {
            "sampling_rate": 1000.0,
            "buffer_size": 1000,
            "can_id_filter": None,
            "extended_frame": False
        }
    }
    
    # Timing precision settings
    HIGH_PRECISION_MODE = True
    TIMESTAMP_RESOLUTION_US = 1  # microsecond precision
    MAX_TIMING_DRIFT_MS = 1
    
    # Validation settings
    MAX_SIGNAL_AGE_MS = 5000
    SIGNAL_VALIDATION_TIMEOUT_MS = 1000


class ValidationConfig:
    """Validation and metrics configuration"""
    
    # Performance metrics thresholds
    MIN_PRECISION = 0.90
    MIN_RECALL = 0.95
    MIN_F1_SCORE = 0.92
    MAX_FALSE_POSITIVE_RATE = 0.05
    
    # Temporal accuracy requirements
    TIMING_TOLERANCE_MS = 100
    MAX_TIMING_ERROR_MS = 50
    MIN_TEMPORAL_ACCURACY = 0.95
    
    # Test session criteria
    MIN_TEST_DURATION_SECONDS = 10
    MAX_TEST_DURATION_MINUTES = 60
    MIN_DETECTION_EVENTS = 5
    
    # Pass/fail criteria
    PASS_CRITERIA = {
        "precision": 0.90,
        "recall": 0.95,
        "f1_score": 0.92,
        "temporal_accuracy": 0.95,
        "avg_latency_ms": 50
    }


# Create global settings instance
settings = Settings()

# Environment-specific configurations
if settings.DEBUG:
    # Development settings
    settings.LOG_LEVEL = "DEBUG"
    settings.DATABASE_ECHO = True
    settings.ENABLE_PROFILING = True

# Export configurations
__all__ = [
    "settings",
    "DetectionConfig",
    "SignalConfig", 
    "ValidationConfig"
]