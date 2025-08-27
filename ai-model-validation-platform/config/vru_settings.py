#!/usr/bin/env python3
"""
VRU AI Model Validation Platform - Unified Configuration System
Supports all environments with 155.138.239.131 external access
"""

import os
from typing import List, Dict, Any, Optional
from enum import Enum
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseType(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class VRUSettings(BaseSettings):
    """Unified settings for VRU AI Model Validation Platform"""
    
    # Environment Configuration
    environment: Environment = Field(default=Environment.DEVELOPMENT)
    debug: bool = Field(default=False)
    
    # Server Configuration with 155.138.239.131 support
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    frontend_port: int = Field(default=3000)
    external_ip: str = Field(default="155.138.239.131")
    
    # Database Configuration (Unified SQLite/PostgreSQL)
    database_type: DatabaseType = Field(default=DatabaseType.SQLITE)
    database_url: Optional[str] = Field(default=None)
    database_echo: bool = Field(default=False)
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379")
    redis_password: Optional[str] = Field(default=None)
    cache_ttl: int = Field(default=300)
    
    # Security Configuration
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expiration: int = Field(default=3600)
    
    # CORS Configuration with 155.138.239.131
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000,http://155.138.239.131:3000,https://155.138.239.131:3000")
    
    # ML Model Configuration
    yolo_model_path: str = Field(default="./models/yolov8n.pt")
    detection_confidence_threshold: float = Field(default=0.5)
    max_video_size_mb: int = Field(default=500)
    
    # Upload Configuration
    upload_directory: str = Field(default="./uploads")
    max_file_size_mb: int = Field(default=500)
    allowed_video_extensions: List[str] = Field(default_factory=lambda: [
        ".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm"
    ])
    
    # Feature Flags
    enable_cvat_integration: bool = Field(default=False)
    enable_real_time_detection: bool = Field(default=False)
    enable_batch_processing: bool = Field(default=True)
    enable_audit_logging: bool = Field(default=True)
    enable_performance_monitoring: bool = Field(default=True)
    
    # API Configuration
    api_v1_prefix: str = Field(default="/api/v1")
    docs_url: str = Field(default="/docs")
    redoc_url: str = Field(default="/redoc")
    openapi_url: str = Field(default="/openapi.json")
    
    # Uvicorn Configuration
    uvicorn_workers: int = Field(default=1)
    uvicorn_reload: bool = Field(default=True)
    uvicorn_access_log: bool = Field(default=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        env_prefix = "VRU_"
        extra = "allow"
    
    @field_validator('database_url', mode='before')
    @classmethod
    def set_database_url(cls, v):
        """Set database URL based on database type if not explicitly provided"""
        if v is not None:
            return v
        # Default to SQLite for development
        return "sqlite:///./dev_database.db"
    
    def get_cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(',')]
        return self.cors_origins
    
    @model_validator(mode='after')
    def set_debug_based_on_env(self):
        """Set debug based on environment"""
        if self.debug is None:
            self.debug = self.environment == Environment.DEVELOPMENT
        return self
    
    @model_validator(mode='after') 
    def set_workers_based_on_env_model(self):
        """Set workers based on environment"""
        if self.uvicorn_workers == 1:  # Default value
            if self.environment == Environment.DEVELOPMENT:
                self.uvicorn_workers = 1
            elif self.environment == Environment.STAGING:
                self.uvicorn_workers = 2
            elif self.environment == Environment.PRODUCTION:
                self.uvicorn_workers = 4
        return self
    
    def get_frontend_url(self) -> str:
        """Get complete frontend URL"""
        return f"http://{self.external_ip}:{self.frontend_port}"
    
    def get_backend_url(self) -> str:
        """Get complete backend URL"""
        return f"http://{self.external_ip}:{self.api_port}"
    
    def get_api_base_url(self) -> str:
        """Get complete API base URL"""
        return f"{self.get_backend_url()}{self.api_v1_prefix}"
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION
    
    def is_sqlite(self) -> bool:
        """Check if using SQLite database"""
        return self.database_type == DatabaseType.SQLITE
    
    def is_postgresql(self) -> bool:
        """Check if using PostgreSQL database"""
        return self.database_type == DatabaseType.POSTGRESQL


# Global settings instance
_settings = None

def get_settings(environment: Optional[Environment] = None) -> VRUSettings:
    """Get or create global settings instance"""
    global _settings
    
    if _settings is None or environment is not None:
        if environment:
            _settings = VRUSettings(environment=environment)
        else:
            _settings = VRUSettings()
    
    return _settings


# Convenience function for backward compatibility
def get_config() -> VRUSettings:
    """Backward compatible config getter"""
    return get_settings()


# Export settings for direct import
settings = get_settings()


if __name__ == "__main__":
    # Configuration validation and info
    config = get_settings()
    
    print("🔧 VRU Platform Configuration")
    print("=" * 50)
    print(f"Environment: {config.environment.value}")
    print(f"Debug Mode: {config.debug}")
    print(f"External IP: {config.external_ip}")
    print(f"Frontend URL: {config.get_frontend_url()}")
    print(f"Backend URL: {config.get_backend_url()}")
    print(f"API Base URL: {config.get_api_base_url()}")
    print(f"Database Type: {config.database_type.value}")
    print(f"Database URL: {config.database_url}")
    print(f"CORS Origins: {', '.join(config.get_cors_origins_list())}")
    print(f"Workers: {config.uvicorn_workers}")
    print("=" * 50)