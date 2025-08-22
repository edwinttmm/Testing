"""
Comprehensive Testing Framework Configuration
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestConfig:
    """Main test configuration class"""
    
    # Database Configuration
    test_database_url: str = "sqlite:///./test_comprehensive.db"
    test_database_pool_size: int = 5
    
    # API Configuration
    api_base_url: str = "http://localhost:8000"
    api_timeout: int = 30
    api_retry_attempts: int = 3
    
    # Video Testing Configuration
    test_video_path: str = "./tests/fixtures/test_videos"
    max_video_size_mb: int = 100
    supported_video_formats: list = field(default_factory=lambda: [".mp4", ".avi", ".mov"])
    test_video_duration_limits: Dict[str, int] = field(
        default_factory=lambda: {"min": 1, "max": 300}  # 1 second to 5 minutes
    )
    
    # Signal Detection Testing
    signal_detection_config: Dict[str, Any] = field(default_factory=lambda: {
        "timing_tolerance_ms": 100,
        "signal_types": ["GPIO", "Network Packet", "Serial"],
        "test_signal_patterns": [
            {"type": "regular", "interval_ms": 1000},
            {"type": "irregular", "intervals": [500, 1500, 2000]},
            {"type": "burst", "count": 5, "interval_ms": 100}
        ]
    })
    
    # Camera Testing Configuration
    camera_config: Dict[str, Any] = field(default_factory=lambda: {
        "connection_timeout_seconds": 10,
        "supported_resolutions": ["1920x1080", "1280x720", "640x480"],
        "supported_frame_rates": [30, 25, 24, 15],
        "camera_types": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]
    })
    
    # Performance Testing Configuration
    performance_config: Dict[str, Any] = field(default_factory=lambda: {
        "load_test_users": [1, 5, 10, 25, 50],
        "concurrent_video_uploads": 5,
        "max_response_time_ms": 5000,
        "memory_threshold_mb": 512,
        "cpu_threshold_percent": 80
    })
    
    # Real-time Validation Configuration
    real_time_config: Dict[str, Any] = field(default_factory=lambda: {
        "websocket_timeout_seconds": 30,
        "notification_delay_ms": 100,
        "max_concurrent_sessions": 10,
        "validation_scenarios": [
            "pass_all_criteria",
            "fail_timing_criteria", 
            "fail_accuracy_criteria",
            "mixed_results"
        ]
    })
    
    # Test Execution Configuration
    execution_config: Dict[str, Any] = field(default_factory=lambda: {
        "parallel_test_workers": 4,
        "test_timeout_seconds": 300,
        "cleanup_after_tests": True,
        "generate_coverage_report": True,
        "save_test_artifacts": True
    })
    
    # Logging Configuration
    logging_config: Dict[str, Any] = field(default_factory=lambda: {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file_handler": True,
        "console_handler": True,
        "log_file_path": "./tests/reports/test_execution.log"
    })

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Create configuration from environment variables"""
        config = cls()
        
        # Override with environment variables if present
        if db_url := os.getenv("TEST_DATABASE_URL"):
            config.test_database_url = db_url
            
        if api_url := os.getenv("TEST_API_BASE_URL"):
            config.api_base_url = api_url
            
        if video_path := os.getenv("TEST_VIDEO_PATH"):
            config.test_video_path = video_path
            
        return config
    
    def validate(self) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Validate paths
        if not Path(self.test_video_path).exists():
            errors.append(f"Test video path does not exist: {self.test_video_path}")
        
        # Validate database URL
        if not self.test_database_url:
            errors.append("Test database URL is required")
        
        # Validate API URL
        if not self.api_base_url:
            errors.append("API base URL is required")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
        
        return True


# Global test configuration instance
test_config = TestConfig.from_env()


# Test Categories and Priorities
TEST_CATEGORIES = {
    "critical": [
        "signal_detection",
        "video_annotation_accuracy", 
        "api_endpoints",
        "real_time_validation"
    ],
    "important": [
        "project_workflow",
        "camera_connection",
        "playback_testing"
    ],
    "optional": [
        "performance_load",
        "security_edge_cases",
        "ui_responsiveness"
    ]
}

# Test Data Patterns
TEST_DATA_PATTERNS = {
    "video_files": {
        "valid": [
            "test_video_30fps_1080p.mp4",
            "test_video_25fps_720p.mp4", 
            "test_video_24fps_480p.mp4"
        ],
        "invalid": [
            "corrupted_video.mp4",
            "unsupported_format.avi",
            "zero_byte_file.mp4"
        ],
        "edge_cases": [
            "very_short_video_1sec.mp4",
            "very_long_video_600sec.mp4",
            "high_resolution_4k.mp4"
        ]
    },
    "signal_patterns": {
        "regular": {"interval_ms": 1000, "count": 10},
        "irregular": {"intervals": [500, 1500, 2000, 800], "count": 4},
        "burst": {"interval_ms": 100, "burst_count": 5, "burst_interval": 2000}
    },
    "annotation_data": {
        "person": {"min_confidence": 0.7, "bbox_variance": 0.1},
        "vehicle": {"min_confidence": 0.8, "bbox_variance": 0.05},
        "bicycle": {"min_confidence": 0.6, "bbox_variance": 0.15}
    }
}

# Coverage Requirements
COVERAGE_REQUIREMENTS = {
    "unit_tests": {
        "statement_coverage": 85,
        "branch_coverage": 80,
        "function_coverage": 90
    },
    "integration_tests": {
        "api_endpoint_coverage": 100,
        "workflow_coverage": 95,
        "service_integration": 90
    },
    "e2e_tests": {
        "user_workflow_coverage": 100,
        "critical_path_coverage": 100
    }
}