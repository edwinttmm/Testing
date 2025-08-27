import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application configuration settings with environment variable support"""
    
    # Database settings
    database_url: str = os.getenv('AIVALIDATION_DATABASE_URL', os.getenv('DATABASE_URL', 'sqlite:///./dev_database.db'))
    test_database_url: str = os.getenv('AIVALIDATION_TEST_DATABASE_URL', 'sqlite:///./test.db')
    database_pool_size: int = int(os.getenv('AIVALIDATION_DATABASE_POOL_SIZE', '10'))
    database_max_overflow: int = int(os.getenv('AIVALIDATION_DATABASE_MAX_OVERFLOW', '20'))
    database_sslmode: str = os.getenv('DATABASE_SSLMODE', 'prefer')
    database_echo: bool = os.getenv('DATABASE_ECHO', 'false').lower() == 'true'
    
    # API settings
    api_host: str = os.getenv('AIVALIDATION_API_HOST', os.getenv('API_HOST', '0.0.0.0'))
    api_port: int = int(os.getenv('AIVALIDATION_API_PORT', os.getenv('API_PORT', '8000')))
    api_debug: bool = os.getenv('AIVALIDATION_API_DEBUG', 'false').lower() == 'true'
    api_reload: bool = os.getenv('AIVALIDATION_API_RELOAD', 'false').lower() == 'true'
    api_base_url: str = os.getenv('AIVALIDATION_API_BASE_URL', f'http://localhost:{api_port}')
    
    # Environment
    app_environment: str = os.getenv('AIVALIDATION_APP_ENVIRONMENT', os.getenv('APP_ENV', 'development'))
    
    # CORS settings - Environment-based configuration (includes production IP)
    cors_origins: List[str] = os.getenv('AIVALIDATION_CORS_ORIGINS', os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000')).split(',')
    cors_credentials: bool = True
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # File upload settings
    max_file_size: int = int(os.getenv('AIVALIDATION_MAX_FILE_SIZE', os.getenv('MAX_UPLOAD_SIZE', str(100 * 1024 * 1024))))
    allowed_video_extensions: List[str] = os.getenv('AIVALIDATION_ALLOWED_VIDEO_EXTENSIONS', '.mp4,.avi,.mov,.mkv,.webm').split(',')
    upload_directory: str = os.getenv('AIVALIDATION_UPLOAD_DIRECTORY', os.getenv('UPLOAD_DIRECTORY', 'uploads'))
    
    # Logging settings
    log_level: str = os.getenv('AIVALIDATION_LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO'))
    log_format: str = os.getenv('AIVALIDATION_LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    log_file: Optional[str] = os.getenv('AIVALIDATION_LOG_FILE')
    log_max_bytes: int = int(os.getenv('AIVALIDATION_LOG_MAX_BYTES', '10485760'))
    log_backup_count: int = int(os.getenv('AIVALIDATION_LOG_BACKUP_COUNT', '5'))
    
    # Security settings - CRITICAL FOR PRODUCTION
    secret_key: str = os.getenv('AIVALIDATION_SECRET_KEY', os.getenv('SECRET_KEY', 'INSECURE-DEFAULT-CHANGE-ME'))
    
    # JWT Configuration
    jwt_secret_key: str = os.getenv('AIVALIDATION_JWT_SECRET_KEY', secret_key)
    jwt_algorithm: str = os.getenv('AIVALIDATION_JWT_ALGORITHM', 'HS256')
    jwt_expire_minutes: int = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
    
    # Security Headers
    security_headers_enabled: bool = os.getenv('AIVALIDATION_SECURITY_HEADERS_ENABLED', 'true').lower() == 'true'
    hsts_enabled: bool = os.getenv('AIVALIDATION_HSTS_ENABLED', 'false').lower() == 'true'
    csp_enabled: bool = os.getenv('AIVALIDATION_CSP_ENABLED', 'true').lower() == 'true'
    
    # SSL/TLS Configuration
    ssl_enabled: bool = os.getenv('AIVALIDATION_SSL_ENABLED', 'false').lower() == 'true'
    ssl_cert_file: Optional[str] = os.getenv('AIVALIDATION_SSL_CERT_FILE')
    ssl_key_file: Optional[str] = os.getenv('AIVALIDATION_SSL_KEY_FILE')
    
    # Application settings
    app_name: str = os.getenv('AIVALIDATION_APP_NAME', 'AI Model Validation Platform')
    app_version: str = os.getenv('AIVALIDATION_APP_VERSION', '1.0.0')
    app_description: str = os.getenv('AIVALIDATION_APP_DESCRIPTION', 'API for validating vehicle-mounted camera VRU detection')
    
    # Redis Configuration
    redis_url: Optional[str] = os.getenv('AIVALIDATION_REDIS_URL')
    redis_password: Optional[str] = os.getenv('AIVALIDATION_REDIS_PASSWORD')
    redis_decode_responses: bool = os.getenv('AIVALIDATION_REDIS_DECODE_RESPONSES', 'true').lower() == 'true'
    
    # Feature flags
    enable_ground_truth_service: bool = os.getenv('AIVALIDATION_ENABLE_GROUND_TRUTH_SERVICE', 'false').lower() == 'true'
    enable_validation_service: bool = os.getenv('AIVALIDATION_ENABLE_VALIDATION_SERVICE', 'false').lower() == 'true'
    enable_async_processing: bool = os.getenv('AIVALIDATION_ENABLE_ASYNC_PROCESSING', 'false').lower() == 'true'
    enable_caching: bool = os.getenv('AIVALIDATION_ENABLE_CACHING', 'false').lower() == 'true'
    
    # Health Check Configuration
    health_check_enabled: bool = os.getenv('AIVALIDATION_HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
    metrics_enabled: bool = os.getenv('AIVALIDATION_METRICS_ENABLED', 'false').lower() == 'true'
    monitoring_token: Optional[str] = os.getenv('AIVALIDATION_MONITORING_TOKEN')
    
    # Docker Configuration
    docker_mode: bool = os.getenv('AIVALIDATION_DOCKER_MODE', 'false').lower() == 'true'
    container_name: str = os.getenv('AIVALIDATION_CONTAINER_NAME', 'ai-validation-backend')
    
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
    """Validate environment configuration with enhanced security checks"""
    warnings = []
    errors = []
    
    # CRITICAL: Check for insecure secret key
    insecure_keys = [
        "your-secret-key-change-in-production",
        "INSECURE-DEFAULT-CHANGE-ME",
        "your-secret-key-here-development-only",
        "REPLACE-WITH-SECURE-32-CHAR-RANDOM-STRING"
    ]
    
    if settings.secret_key in insecure_keys:
        if settings.app_environment.lower() == 'production':
            errors.append("CRITICAL: Using insecure default secret key in production!")
        else:
            warnings.append("Using default secret key - change for production!")
    
    if len(settings.secret_key) < 32:
        warnings.append("Secret key should be at least 32 characters long")
    
    # Database configuration validation
    if "sqlite" in settings.database_url.lower():
        if settings.app_environment.lower() == 'production':
            warnings.append("Using SQLite in production - consider PostgreSQL for better performance and reliability")
        else:
            logger.info("Using SQLite database for development")
    
    # CORS validation
    if not settings.cors_origins or len(settings.cors_origins) == 0:
        warnings.append("No CORS origins configured - this may block frontend requests")
    
    # SSL/TLS validation for production
    if settings.app_environment.lower() == 'production':
        if not settings.ssl_enabled:
            warnings.append("SSL/TLS not enabled in production - consider enabling HTTPS")
        
        if 'http://' in settings.api_base_url:
            warnings.append("Using HTTP in production - consider HTTPS for security")
    
    # File upload size validation
    if settings.max_file_size > 1000 * 1024 * 1024:  # 1GB
        warnings.append(f"Very large max file size ({settings.max_file_size / 1024 / 1024:.1f}MB) may cause memory issues")
    
    # Log errors (these are critical)
    for error in errors:
        logger.error(f"Configuration ERROR: {error}")
        
    # Log warnings
    for warning in warnings:
        logger.warning(f"Configuration warning: {warning}")
    
    # Raise exception for critical errors in production
    if errors and settings.app_environment.lower() == 'production':
        raise ValueError(f"Critical configuration errors found: {'; '.join(errors)}")
    
    # Log configuration summary
    logger.info(f"Application: {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_environment}")
    logger.info(f"Database: {_mask_database_url(settings.database_url)}")
    logger.info(f"Upload directory: {settings.upload_directory}")
    logger.info(f"Max file size: {settings.max_file_size / 1024 / 1024:.1f}MB")
    logger.info(f"CORS origins: {len(settings.cors_origins)} configured")
    logger.info(f"SSL enabled: {settings.ssl_enabled}")
    logger.info(f"Security headers: {settings.security_headers_enabled}")

def _mask_database_url(db_url: str) -> str:
    """Mask sensitive information in database URL for logging"""
    import re
    # Replace password with asterisks
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', db_url)

def generate_secure_secret_key() -> str:
    """Generate a secure secret key for development purposes"""
    import secrets
    return secrets.token_urlsafe(32)

def is_production() -> bool:
    """Check if running in production environment"""
    env = os.getenv('AIVALIDATION_APP_ENVIRONMENT', os.getenv('APP_ENV', 'development'))
    return env.lower() in ['production', 'prod']

# Global settings instance
settings = get_settings()

# Security validation on import
if __name__ != "__main__":
    try:
        validate_environment(settings)
        setup_logging(settings)
        create_directories(settings)
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        if is_production():
            raise