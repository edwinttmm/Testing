import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application configuration settings with environment variable support"""
    
    # Database settings
    database_url: str = "sqlite:///./test_database.db"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    api_reload: bool = False
    
    # CORS settings - Comprehensive production configuration
    cors_origins: List[str] = [
        # Development origins
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        
        # Production HTTP origins
        "http://155.138.239.131:3000",
        "http://155.138.239.131:8000",
        "http://155.138.239.131:8080",
        
        # Production HTTPS origins (recommended for production)
        "https://155.138.239.131:3000",
        "https://155.138.239.131:8000",
        "https://155.138.239.131:8080",
        "https://155.138.239.131:8443",
        
        # Cloud Workstations
        "https://3000-firebase-testinggit-1755382041749.cluster-lu4mup47g5gm4rtyvhzpwbfadi.cloudworkstations.dev"
    ]
    cors_credentials: bool = True
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # File upload settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_video_extensions: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    upload_directory: str = "uploads"
    
    # Logging settings
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None
    
    # Security settings
    secret_key: str = "your-secret-key-change-in-production"
    
    # Application settings
    app_name: str = "AI Model Validation Platform"
    app_version: str = "1.0.0"
    app_description: str = "API for validating vehicle-mounted camera VRU detection"
    
    # Feature flags
    enable_ground_truth_service: bool = False
    enable_validation_service: bool = False
    enable_async_processing: bool = False
    enable_caching: bool = False
    
    # Performance settings
    default_page_size: int = 100
    max_page_size: int = 1000
    request_timeout: int = 30
    
    @field_validator('cors_origins', mode='before')
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @field_validator('allowed_video_extensions', mode='before')
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",") if ext.strip()]
        return v
    
    @field_validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Log level must be one of: {", ".join(valid_levels)}')
        return v.upper()
    
    @field_validator('max_file_size')
    def validate_file_size(cls, v):
        if v <= 0:
            raise ValueError('Maximum file size must be positive')
        return v
    
    @field_validator('database_pool_size', 'database_max_overflow')
    def validate_positive_integers(cls, v):
        if v < 0:
            raise ValueError('Value must be non-negative')
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields to be ignored
        
        # Environment variable prefix
        env_prefix = "AIVALIDATION_"
        
        # Example: AIVALIDATION_DATABASE_URL=postgresql://user:pass@localhost/db

def get_settings() -> Settings:
    """Get application settings with caching"""
    return Settings()

def setup_logging(settings: Settings) -> None:
    """Configure application logging"""
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format=settings.log_format,
        filename=settings.log_file
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logger.info(f"Logging configured with level: {settings.log_level}")

def create_directories(settings: Settings) -> None:
    """Create necessary directories"""
    directories = [
        settings.upload_directory,
        "logs",
        "data"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")

def validate_environment(settings: Settings) -> None:
    """Validate environment configuration"""
    warnings = []
    
    # Check for default secret key
    if settings.secret_key == "your-secret-key-change-in-production":
        warnings.append("Using default secret key - change in production!")
    
    # Check database configuration
    if "sqlite" in settings.database_url.lower() and settings.api_debug is False:
        warnings.append("Using SQLite in production mode - consider PostgreSQL")
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"Configuration warning: {warning}")
    
    # Log configuration summary
    logger.info(f"Application: {settings.app_name} v{settings.app_version}")
    logger.info(f"Database: {settings.database_url}")
    logger.info(f"Upload directory: {settings.upload_directory}")
    logger.info(f"Max file size: {settings.max_file_size / 1024 / 1024:.1f}MB")
    logger.info(f"CORS origins: {len(settings.cors_origins)} configured")

# Global settings instance
settings = get_settings()