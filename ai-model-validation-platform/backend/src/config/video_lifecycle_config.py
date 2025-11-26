"""
Video Lifecycle Configuration - Production Settings
====================================================

Centralized configuration for video lifecycle API with environment
variable support and validation.

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

import os
import logging
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Deployment environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass
class RateLimitConfig:
    """Rate limiting configuration"""

    # Per-endpoint rate limits (requests per window)
    video_started_limit: int = 30
    video_ended_limit: int = 30
    video_error_limit: int = 30
    status_limit: int = 60
    drift_stats_limit: int = 60
    health_check_limit: int = 120
    default_limit: int = 100

    # Time window in seconds
    window_seconds: int = 60

    # Enable/disable rate limiting
    enabled: bool = True

    # Redis connection (for distributed rate limiting)
    redis_url: Optional[str] = None
    use_redis: bool = False

    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        """Load configuration from environment variables"""
        return cls(
            video_started_limit=int(os.getenv("RATE_LIMIT_VIDEO_STARTED", "30")),
            video_ended_limit=int(os.getenv("RATE_LIMIT_VIDEO_ENDED", "30")),
            video_error_limit=int(os.getenv("RATE_LIMIT_VIDEO_ERROR", "30")),
            status_limit=int(os.getenv("RATE_LIMIT_STATUS", "60")),
            drift_stats_limit=int(os.getenv("RATE_LIMIT_DRIFT_STATS", "60")),
            health_check_limit=int(os.getenv("RATE_LIMIT_HEALTH", "120")),
            default_limit=int(os.getenv("RATE_LIMIT_DEFAULT", "100")),
            window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
            enabled=os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "true",
            redis_url=os.getenv("REDIS_URL"),
            use_redis=os.getenv("USE_REDIS_RATE_LIMITING", "false").lower() == "true"
        )


@dataclass
class DriftConfig:
    """Drift measurement and compensation configuration"""

    # Drift thresholds (milliseconds)
    acceptable_drift_ms: float = 50.0
    warning_drift_ms: float = 100.0
    critical_drift_ms: float = 500.0

    # Measurement settings
    enable_drift_compensation: bool = True
    store_all_measurements: bool = True

    # Clock sync settings
    clock_sync_interval_seconds: int = 60  # Re-sync every 60 seconds
    clock_sync_timeout_seconds: float = 5.0

    # Quality assessment
    min_measurements_for_stats: int = 3
    std_dev_threshold_ms: float = 20.0  # High variance threshold

    @classmethod
    def from_env(cls) -> "DriftConfig":
        """Load configuration from environment variables"""
        return cls(
            acceptable_drift_ms=float(os.getenv("ACCEPTABLE_DRIFT_MS", "50.0")),
            warning_drift_ms=float(os.getenv("WARNING_DRIFT_MS", "100.0")),
            critical_drift_ms=float(os.getenv("CRITICAL_DRIFT_MS", "500.0")),
            enable_drift_compensation=os.getenv("ENABLE_DRIFT_COMPENSATION", "true").lower() == "true",
            store_all_measurements=os.getenv("STORE_ALL_DRIFT_MEASUREMENTS", "true").lower() == "true",
            clock_sync_interval_seconds=int(os.getenv("CLOCK_SYNC_INTERVAL_SECONDS", "60")),
            clock_sync_timeout_seconds=float(os.getenv("CLOCK_SYNC_TIMEOUT_SECONDS", "5.0")),
            min_measurements_for_stats=int(os.getenv("MIN_DRIFT_MEASUREMENTS", "3")),
            std_dev_threshold_ms=float(os.getenv("DRIFT_STD_DEV_THRESHOLD_MS", "20.0"))
        )


@dataclass
class LabJackConfig:
    """LabJack device configuration"""

    # Device settings
    device_id: str = "T7_001"
    connection_type: str = "USB"  # USB, ETHERNET, WIFI
    ip_address: Optional[str] = None

    # Monitoring settings
    sample_rate_hz: int = 1000
    buffer_size: int = 10000
    dio_channel: int = 0  # Digital input channel

    # Timeout settings
    command_timeout_seconds: float = 2.0
    connection_timeout_seconds: float = 5.0
    startup_timeout_seconds: float = 10.0

    # Retry settings
    max_connection_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Fallback mode (software timing if LabJack unavailable)
    enable_fallback_mode: bool = True
    warn_on_fallback: bool = True

    @classmethod
    def from_env(cls) -> "LabJackConfig":
        """Load configuration from environment variables"""
        return cls(
            device_id=os.getenv("LABJACK_DEVICE_ID", "T7_001"),
            connection_type=os.getenv("LABJACK_CONNECTION_TYPE", "USB"),
            ip_address=os.getenv("LABJACK_IP_ADDRESS"),
            sample_rate_hz=int(os.getenv("LABJACK_SAMPLE_RATE_HZ", "1000")),
            buffer_size=int(os.getenv("LABJACK_BUFFER_SIZE", "10000")),
            dio_channel=int(os.getenv("LABJACK_DIO_CHANNEL", "0")),
            command_timeout_seconds=float(os.getenv("LABJACK_COMMAND_TIMEOUT", "2.0")),
            connection_timeout_seconds=float(os.getenv("LABJACK_CONNECTION_TIMEOUT", "5.0")),
            startup_timeout_seconds=float(os.getenv("LABJACK_STARTUP_TIMEOUT", "10.0")),
            max_connection_retries=int(os.getenv("LABJACK_MAX_RETRIES", "3")),
            retry_delay_seconds=float(os.getenv("LABJACK_RETRY_DELAY", "1.0")),
            enable_fallback_mode=os.getenv("LABJACK_ENABLE_FALLBACK", "true").lower() == "true",
            warn_on_fallback=os.getenv("LABJACK_WARN_ON_FALLBACK", "true").lower() == "true"
        )


@dataclass
class LoggingConfig:
    """Logging configuration"""

    # Log level
    log_level: str = "INFO"

    # Structured logging
    use_json_logs: bool = True

    # Log file settings
    log_to_file: bool = True
    log_file_path: str = "/var/log/video_lifecycle/api.log"
    log_rotation_max_bytes: int = 10 * 1024 * 1024  # 10 MB
    log_backup_count: int = 5

    # Request logging
    log_all_requests: bool = True
    log_request_body: bool = False  # Security: disable in production
    log_response_body: bool = False  # Security: disable in production

    # Performance logging
    log_slow_requests_threshold_ms: float = 1000.0

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Load configuration from environment variables"""
        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            use_json_logs=os.getenv("USE_JSON_LOGS", "true").lower() == "true",
            log_to_file=os.getenv("LOG_TO_FILE", "true").lower() == "true",
            log_file_path=os.getenv("LOG_FILE_PATH", "/var/log/video_lifecycle/api.log"),
            log_rotation_max_bytes=int(os.getenv("LOG_ROTATION_MAX_BYTES", str(10 * 1024 * 1024))),
            log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            log_all_requests=os.getenv("LOG_ALL_REQUESTS", "true").lower() == "true",
            log_request_body=os.getenv("LOG_REQUEST_BODY", "false").lower() == "true",
            log_response_body=os.getenv("LOG_RESPONSE_BODY", "false").lower() == "true",
            log_slow_requests_threshold_ms=float(os.getenv("LOG_SLOW_REQUESTS_MS", "1000.0"))
        )


@dataclass
class DatabaseConfig:
    """Database configuration"""

    # Connection
    database_url: str = "postgresql://user:pass@localhost:5432/hildb"

    # Connection pool
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout_seconds: float = 30.0
    pool_recycle_seconds: int = 3600

    # Transaction settings
    autocommit: bool = False
    autoflush: bool = False

    # Retry settings
    enable_retry_on_deadlock: bool = True
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Load configuration from environment variables"""
        return cls(
            database_url=os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/hildb"),
            pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
            pool_timeout_seconds=float(os.getenv("DB_POOL_TIMEOUT", "30.0")),
            pool_recycle_seconds=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            autocommit=os.getenv("DB_AUTOCOMMIT", "false").lower() == "true",
            autoflush=os.getenv("DB_AUTOFLUSH", "false").lower() == "true",
            enable_retry_on_deadlock=os.getenv("DB_RETRY_ON_DEADLOCK", "true").lower() == "true",
            max_retries=int(os.getenv("DB_MAX_RETRIES", "3"))
        )


@dataclass
class VideoLifecycleConfig:
    """Main video lifecycle configuration"""

    # Environment
    environment: Environment = Environment.DEVELOPMENT

    # Component configs
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    drift: DriftConfig = field(default_factory=DriftConfig)
    labjack: LabJackConfig = field(default_factory=LabJackConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # API settings
    api_version: str = "1.0.0"
    enable_cors: bool = True
    cors_origins: list = field(default_factory=lambda: ["*"])

    # Feature flags
    enable_health_checks: bool = True
    enable_metrics: bool = True
    enable_debug_endpoints: bool = False  # Only in development

    # Performance
    max_concurrent_sessions: int = 100
    session_timeout_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "VideoLifecycleConfig":
        """Load complete configuration from environment variables"""

        # Get environment
        env_name = os.getenv("ENVIRONMENT", "development").lower()
        try:
            environment = Environment(env_name)
        except ValueError:
            logger.warning(f"Invalid environment '{env_name}', defaulting to development")
            environment = Environment.DEVELOPMENT

        # Load component configs
        config = cls(
            environment=environment,
            rate_limit=RateLimitConfig.from_env(),
            drift=DriftConfig.from_env(),
            labjack=LabJackConfig.from_env(),
            logging=LoggingConfig.from_env(),
            database=DatabaseConfig.from_env(),
            api_version=os.getenv("API_VERSION", "1.0.0"),
            enable_cors=os.getenv("ENABLE_CORS", "true").lower() == "true",
            cors_origins=os.getenv("CORS_ORIGINS", "*").split(","),
            enable_health_checks=os.getenv("ENABLE_HEALTH_CHECKS", "true").lower() == "true",
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            enable_debug_endpoints=os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true",
            max_concurrent_sessions=int(os.getenv("MAX_CONCURRENT_SESSIONS", "100")),
            session_timeout_seconds=int(os.getenv("SESSION_TIMEOUT_SECONDS", "3600"))
        )

        # Apply environment-specific overrides
        if environment == Environment.PRODUCTION:
            config._apply_production_overrides()
        elif environment == Environment.DEVELOPMENT:
            config._apply_development_overrides()

        return config

    def _apply_production_overrides(self):
        """Apply production-specific security and performance settings"""
        # Disable debug features
        self.enable_debug_endpoints = False
        self.logging.log_request_body = False
        self.logging.log_response_body = False

        # Stricter rate limits if not explicitly set
        if os.getenv("RATE_LIMIT_VIDEO_STARTED") is None:
            self.rate_limit.video_started_limit = 20  # More conservative in prod

        logger.info("Applied production configuration overrides")

    def _apply_development_overrides(self):
        """Apply development-specific settings for easier debugging"""
        # Enable debug features
        self.enable_debug_endpoints = True

        # More lenient rate limits
        if os.getenv("RATE_LIMIT_VIDEO_STARTED") is None:
            self.rate_limit.video_started_limit = 100

        # Verbose logging
        if os.getenv("LOG_LEVEL") is None:
            self.logging.log_level = "DEBUG"

        logger.info("Applied development configuration overrides")

    def validate(self) -> list[str]:
        """
        Validate configuration for common issues.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Database URL validation
        if not self.database.database_url or self.database.database_url == "postgresql://user:pass@localhost:5432/hildb":
            if self.environment == Environment.PRODUCTION:
                errors.append("DATABASE_URL must be set in production")

        # LabJack validation
        if self.labjack.connection_type == "ETHERNET" and not self.labjack.ip_address:
            errors.append("LABJACK_IP_ADDRESS must be set when using ETHERNET connection")

        # Rate limit validation
        if self.rate_limit.enabled and self.rate_limit.use_redis and not self.rate_limit.redis_url:
            errors.append("REDIS_URL must be set when USE_REDIS_RATE_LIMITING is enabled")

        # Drift threshold validation
        if self.drift.acceptable_drift_ms >= self.drift.warning_drift_ms:
            errors.append("ACCEPTABLE_DRIFT_MS must be less than WARNING_DRIFT_MS")

        if self.drift.warning_drift_ms >= self.drift.critical_drift_ms:
            errors.append("WARNING_DRIFT_MS must be less than CRITICAL_DRIFT_MS")

        return errors

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary (for logging/debugging)"""
        from dataclasses import asdict
        config_dict = asdict(self)

        # Redact sensitive information
        if 'database' in config_dict and 'database_url' in config_dict['database']:
            # Redact password from database URL
            db_url = config_dict['database']['database_url']
            if '@' in db_url:
                parts = db_url.split('@')
                user_part = parts[0].split('://')
                if len(user_part) > 1:
                    config_dict['database']['database_url'] = f"{user_part[0]}://***:***@{parts[1]}"

        return config_dict


# ==================== GLOBAL CONFIGURATION ====================

# Global configuration instance (initialized at startup)
_config: Optional[VideoLifecycleConfig] = None


def get_config() -> VideoLifecycleConfig:
    """
    Get global configuration instance.

    Returns:
        VideoLifecycleConfig instance

    Raises:
        RuntimeError: If configuration not initialized
    """
    if _config is None:
        raise RuntimeError("Configuration not initialized. Call initialize_config() first.")
    return _config


def initialize_config() -> VideoLifecycleConfig:
    """
    Initialize global configuration from environment variables.

    Returns:
        Initialized configuration

    Raises:
        ValueError: If configuration validation fails
    """
    global _config

    # Load configuration
    _config = VideoLifecycleConfig.from_env()

    # Validate
    validation_errors = _config.validate()
    if validation_errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in validation_errors)
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Log configuration (redacted)
    logger.info(
        f"Configuration initialized for {_config.environment.value} environment",
        extra={"config": _config.to_dict()}
    )

    return _config


# ==================== CONVENIENCE FUNCTIONS ====================

def is_production() -> bool:
    """Check if running in production environment"""
    return get_config().environment == Environment.PRODUCTION


def is_development() -> bool:
    """Check if running in development environment"""
    return get_config().environment == Environment.DEVELOPMENT


def get_drift_thresholds() -> tuple[float, float, float]:
    """
    Get drift thresholds in order: acceptable, warning, critical

    Returns:
        Tuple of (acceptable_ms, warning_ms, critical_ms)
    """
    config = get_config()
    return (
        config.drift.acceptable_drift_ms,
        config.drift.warning_drift_ms,
        config.drift.critical_drift_ms
    )
