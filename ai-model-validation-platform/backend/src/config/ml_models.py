"""
ML Model Configuration Management
Centralized configuration for YOLO models, confidence thresholds, and processing parameters
"""

import os
import yaml
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field
import torch

logger = logging.getLogger(__name__)

@dataclass
class YOLOModelConfig:
    """YOLO model configuration"""
    primary_model: str = "yolov8n.pt"
    fallback_model: str = "yolov8n.pt"
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.4
    max_detections: int = 100
    device: str = "cpu"
    batch_size: int = 1
    timeout_seconds: int = 30
    classes: List[int] = field(default_factory=lambda: [0, 1, 2])  # person, bicycle, car
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(f"Invalid confidence threshold: {self.confidence_threshold}")
        if not 0.0 <= self.iou_threshold <= 1.0:
            raise ValueError(f"Invalid IoU threshold: {self.iou_threshold}")
        if self.timeout_seconds <= 0:
            raise ValueError(f"Invalid timeout: {self.timeout_seconds}")

@dataclass  
class DetectionConfig:
    """Detection pipeline configuration"""
    enable_validation: bool = True
    auto_validate_threshold: float = 0.8
    manual_review_threshold: float = 0.65
    quality_threshold: float = 0.7
    enable_screenshots: bool = True
    screenshot_padding: int = 20
    frame_skip_ratio: int = 1  # Process every N frames (1 = every frame)
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        thresholds = [self.auto_validate_threshold, self.manual_review_threshold, self.quality_threshold]
        for threshold in thresholds:
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(f"Invalid threshold value: {threshold}")

@dataclass
class ProcessingConfig:
    """Processing pipeline configuration"""
    max_workers: int = 2
    queue_size: int = 50
    batch_size: int = 4
    memory_limit_mb: int = 1024
    enable_gpu: bool = False
    gpu_memory_fraction: float = 0.8
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.max_workers <= 0:
            raise ValueError(f"Invalid max_workers: {self.max_workers}")
        if not 0.1 <= self.gpu_memory_fraction <= 1.0:
            raise ValueError(f"Invalid GPU memory fraction: {self.gpu_memory_fraction}")

class MLModelConfigManager:
    """Centralized ML model configuration management"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.environment = self._detect_environment()
        self.config_dir = config_dir or Path(os.getcwd()) / "config"
        self.config_file = self.config_dir / "ml_models.yaml"
        
        # Load configuration
        self._raw_config = self._load_config()
        self.yolo = self._create_yolo_config()
        self.detection = self._create_detection_config() 
        self.processing = self._create_processing_config()
        
        logger.info(f"ML configuration loaded for environment: {self.environment}")
    
    def _detect_environment(self) -> str:
        """Detect current environment"""
        env_indicators = [
            os.getenv('AIVALIDATION_APP_ENVIRONMENT'),
            os.getenv('APP_ENV'),
            os.getenv('ENVIRONMENT'),
        ]
        
        for env in env_indicators:
            if env:
                env_lower = env.lower()
                if env_lower in ['production', 'prod']:
                    return 'production'
                elif env_lower in ['staging', 'stage']:
                    return 'staging'
                elif env_lower in ['test', 'testing']:
                    return 'test'
                elif env_lower in ['development', 'dev', 'local']:
                    return 'development'
        
        return 'development'
    
    def _load_config(self) -> Dict[str, Any]:
        """Load ML configuration from multiple sources"""
        # 1. Start with environment-specific defaults
        config = self._get_environment_defaults()
        
        # 2. Load from YAML file if exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    config = self._deep_merge(config, file_config)
                    logger.info(f"Loaded ML config from {self.config_file}")
            except Exception as e:
                logger.warning(f"Failed to load ML config file: {e}")
        
        # 3. Apply environment variable overrides
        env_overrides = self._get_environment_overrides()
        config = self._deep_merge(config, env_overrides)
        
        return config
    
    def _get_environment_defaults(self) -> Dict[str, Any]:
        """Get environment-specific default configuration"""
        
        if self.environment == 'production':
            return {
                'yolo': {
                    'primary_model': 'yolo11l.pt',  # Best accuracy for production
                    'fallback_model': 'yolov8n.pt',
                    'confidence_threshold': 0.7,   # Higher threshold for production
                    'iou_threshold': 0.4,
                    'max_detections': 100,
                    'device': 'cuda' if self._is_cuda_available() else 'cpu',
                    'batch_size': 8,
                    'timeout_seconds': 60,
                    'classes': [0, 1, 2, 3, 5, 7, 14, 15, 16]  # Expanded VRU classes
                },
                'detection': {
                    'enable_validation': True,
                    'auto_validate_threshold': 0.85,
                    'manual_review_threshold': 0.7,
                    'quality_threshold': 0.8,
                    'enable_screenshots': True,
                    'screenshot_padding': 20,
                    'frame_skip_ratio': 1
                },
                'processing': {
                    'max_workers': 4,
                    'queue_size': 100,
                    'batch_size': 8,
                    'memory_limit_mb': 2048,
                    'enable_gpu': True,
                    'gpu_memory_fraction': 0.8
                }
            }
        
        elif self.environment == 'staging':
            return {
                'yolo': {
                    'primary_model': 'yolov8l.pt',  # Good balance for staging
                    'fallback_model': 'yolov8n.pt',
                    'confidence_threshold': 0.6,
                    'iou_threshold': 0.4,
                    'max_detections': 50,
                    'device': 'cuda' if self._is_cuda_available() else 'cpu',
                    'batch_size': 4,
                    'timeout_seconds': 45,
                    'classes': [0, 1, 2]
                },
                'detection': {
                    'enable_validation': True,
                    'auto_validate_threshold': 0.8,
                    'manual_review_threshold': 0.65,
                    'quality_threshold': 0.7,
                    'enable_screenshots': True,
                    'screenshot_padding': 20,
                    'frame_skip_ratio': 1
                },
                'processing': {
                    'max_workers': 2,
                    'queue_size': 50,
                    'batch_size': 4,
                    'memory_limit_mb': 1024,
                    'enable_gpu': True,
                    'gpu_memory_fraction': 0.6
                }
            }
        
        elif self.environment == 'test':
            return {
                'yolo': {
                    'primary_model': 'mock',  # Use mock for testing
                    'fallback_model': 'mock',
                    'confidence_threshold': 0.5,
                    'iou_threshold': 0.4,
                    'max_detections': 10,
                    'device': 'cpu',
                    'batch_size': 1,
                    'timeout_seconds': 5,
                    'classes': [0, 1, 2]
                },
                'detection': {
                    'enable_validation': False,
                    'auto_validate_threshold': 0.8,
                    'manual_review_threshold': 0.5,
                    'quality_threshold': 0.5,
                    'enable_screenshots': False,
                    'screenshot_padding': 10,
                    'frame_skip_ratio': 5  # Skip frames for faster testing
                },
                'processing': {
                    'max_workers': 1,
                    'queue_size': 5,
                    'batch_size': 1,
                    'memory_limit_mb': 256,
                    'enable_gpu': False,
                    'gpu_memory_fraction': 0.5
                }
            }
        
        else:  # development
            return {
                'yolo': {
                    'primary_model': 'yolov8n.pt',  # Fast for development
                    'fallback_model': 'yolov8n.pt',
                    'confidence_threshold': 0.01,  # Very low for debugging
                    'iou_threshold': 0.4,
                    'max_detections': 50,
                    'device': 'cpu',  # Stable for development
                    'batch_size': 2,
                    'timeout_seconds': 30,
                    'classes': [0, 1, 2]  # Basic VRU classes
                },
                'detection': {
                    'enable_validation': False,  # Skip validation in dev
                    'auto_validate_threshold': 0.8,
                    'manual_review_threshold': 0.5,
                    'quality_threshold': 0.5,
                    'enable_screenshots': True,
                    'screenshot_padding': 20,
                    'frame_skip_ratio': 1
                },
                'processing': {
                    'max_workers': 1,
                    'queue_size': 20,
                    'batch_size': 2,
                    'memory_limit_mb': 512,
                    'enable_gpu': False,  # CPU only for dev stability
                    'gpu_memory_fraction': 0.5
                }
            }
    
    def _get_environment_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables"""
        overrides = {}
        
        # YOLO model overrides
        if os.getenv('ML_PRIMARY_MODEL'):
            overrides.setdefault('yolo', {})['primary_model'] = os.getenv('ML_PRIMARY_MODEL')
        
        if os.getenv('ML_CONFIDENCE_THRESHOLD'):
            try:
                threshold = float(os.getenv('ML_CONFIDENCE_THRESHOLD'))
                overrides.setdefault('yolo', {})['confidence_threshold'] = threshold
            except ValueError:
                logger.warning(f"Invalid ML_CONFIDENCE_THRESHOLD value: {os.getenv('ML_CONFIDENCE_THRESHOLD')}")
        
        if os.getenv('ML_DEVICE'):
            device = os.getenv('ML_DEVICE').lower()
            if device in ['cpu', 'cuda', 'auto']:
                if device == 'auto':
                    device = 'cuda' if self._is_cuda_available() else 'cpu'
                overrides.setdefault('yolo', {})['device'] = device
        
        if os.getenv('ML_BATCH_SIZE'):
            try:
                batch_size = int(os.getenv('ML_BATCH_SIZE'))
                overrides.setdefault('yolo', {})['batch_size'] = batch_size
                overrides.setdefault('processing', {})['batch_size'] = batch_size
            except ValueError:
                logger.warning(f"Invalid ML_BATCH_SIZE value: {os.getenv('ML_BATCH_SIZE')}")
        
        # Detection overrides
        if os.getenv('ML_AUTO_VALIDATE_THRESHOLD'):
            try:
                threshold = float(os.getenv('ML_AUTO_VALIDATE_THRESHOLD'))
                overrides.setdefault('detection', {})['auto_validate_threshold'] = threshold
            except ValueError:
                logger.warning(f"Invalid ML_AUTO_VALIDATE_THRESHOLD value: {os.getenv('ML_AUTO_VALIDATE_THRESHOLD')}")
        
        # Processing overrides
        if os.getenv('ML_MAX_WORKERS'):
            try:
                workers = int(os.getenv('ML_MAX_WORKERS'))
                overrides.setdefault('processing', {})['max_workers'] = workers
            except ValueError:
                logger.warning(f"Invalid ML_MAX_WORKERS value: {os.getenv('ML_MAX_WORKERS')}")
        
        return overrides
    
    def _create_yolo_config(self) -> YOLOModelConfig:
        """Create YOLO configuration from raw config"""
        yolo_dict = self._raw_config.get('yolo', {})
        return YOLOModelConfig(**yolo_dict)
    
    def _create_detection_config(self) -> DetectionConfig:
        """Create detection configuration from raw config"""
        detection_dict = self._raw_config.get('detection', {})
        return DetectionConfig(**detection_dict)
    
    def _create_processing_config(self) -> ProcessingConfig:
        """Create processing configuration from raw config"""
        processing_dict = self._raw_config.get('processing', {})
        return ProcessingConfig(**processing_dict)
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _is_cuda_available(self) -> bool:
        """Check if CUDA is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False
    
    def get_model_paths(self) -> List[Path]:
        """Get prioritized list of model paths to try"""
        from .paths import path_manager, PathType
        
        model_dirs = [
            path_manager.get_path(PathType.MODELS),  # Configured models directory
            Path.cwd(),  # Current working directory
            Path.cwd() / "models",  # Local models subdirectory
            Path("/app/models"),  # Docker container models
            Path.home() / ".cache" / "torch" / "hub",  # PyTorch cache
        ]
        
        return [d for d in model_dirs if d.exists()]
    
    def get_model_path(self, model_name: str) -> Optional[Path]:
        """Get full path to model file"""
        if model_name == 'mock':
            return None  # Use mock model for testing
        
        # Try each model directory
        for model_dir in self.get_model_paths():
            model_path = model_dir / model_name
            if model_path.exists():
                logger.debug(f"Found model {model_name} at {model_path}")
                return model_path
        
        # Model not found locally - return expected path for download
        from .paths import path_manager, PathType
        expected_path = path_manager.get_path(PathType.MODELS) / model_name
        logger.info(f"Model {model_name} not found locally, expected at {expected_path}")
        return expected_path
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'model_availability': {}
        }
        
        # Validate YOLO configuration
        try:
            # Check model availability
            primary_path = self.get_model_path(self.yolo.primary_model)
            fallback_path = self.get_model_path(self.yolo.fallback_model)
            
            validation_results['model_availability'] = {
                'primary_model': {
                    'name': self.yolo.primary_model,
                    'path': str(primary_path) if primary_path else None,
                    'exists': primary_path and primary_path.exists() if primary_path else False
                },
                'fallback_model': {
                    'name': self.yolo.fallback_model,
                    'path': str(fallback_path) if fallback_path else None,
                    'exists': fallback_path and fallback_path.exists() if fallback_path else False
                }
            }
            
            # Check if at least one model is available
            if (not validation_results['model_availability']['primary_model']['exists'] and 
                not validation_results['model_availability']['fallback_model']['exists'] and
                self.yolo.primary_model != 'mock'):
                validation_results['warnings'].append("No YOLO models found locally - will attempt download")
            
            # Validate device availability
            if self.yolo.device.startswith('cuda') and not self._is_cuda_available():
                validation_results['warnings'].append("CUDA requested but not available - will fall back to CPU")
            
        except Exception as e:
            validation_results['errors'].append(f"YOLO configuration validation failed: {e}")
            validation_results['valid'] = False
        
        # Validate thresholds
        if self.detection.auto_validate_threshold <= self.detection.manual_review_threshold:
            validation_results['warnings'].append("Auto-validate threshold should be higher than manual review threshold")
        
        return validation_results
    
    def save_config(self, config_path: Optional[Path] = None) -> Path:
        """Save current configuration to YAML file"""
        if config_path is None:
            config_path = self.config_file
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = {
            'yolo': {
                'primary_model': self.yolo.primary_model,
                'fallback_model': self.yolo.fallback_model,
                'confidence_threshold': self.yolo.confidence_threshold,
                'iou_threshold': self.yolo.iou_threshold,
                'max_detections': self.yolo.max_detections,
                'device': self.yolo.device,
                'batch_size': self.yolo.batch_size,
                'timeout_seconds': self.yolo.timeout_seconds,
                'classes': self.yolo.classes
            },
            'detection': {
                'enable_validation': self.detection.enable_validation,
                'auto_validate_threshold': self.detection.auto_validate_threshold,
                'manual_review_threshold': self.detection.manual_review_threshold,
                'quality_threshold': self.detection.quality_threshold,
                'enable_screenshots': self.detection.enable_screenshots,
                'screenshot_padding': self.detection.screenshot_padding,
                'frame_skip_ratio': self.detection.frame_skip_ratio
            },
            'processing': {
                'max_workers': self.processing.max_workers,
                'queue_size': self.processing.queue_size,
                'batch_size': self.processing.batch_size,
                'memory_limit_mb': self.processing.memory_limit_mb,
                'enable_gpu': self.processing.enable_gpu,
                'gpu_memory_fraction': self.processing.gpu_memory_fraction
            }
        }
        
        with open(config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
        
        logger.info(f"ML configuration saved to {config_path}")
        return config_path
    
    def reload(self):
        """Reload configuration from sources"""
        self.__init__(self.config_dir)

# Global instance
ml_config = MLModelConfigManager()

# Convenience functions
def get_yolo_config() -> YOLOModelConfig:
    """Get YOLO configuration"""
    return ml_config.yolo

def get_detection_config() -> DetectionConfig:
    """Get detection configuration"""
    return ml_config.detection

def get_processing_config() -> ProcessingConfig:
    """Get processing configuration"""  
    return ml_config.processing

def get_model_path(model_name: str) -> Optional[Path]:
    """Get path to model file"""
    return ml_config.get_model_path(model_name)

def validate_ml_config() -> Dict[str, Any]:
    """Validate ML configuration"""
    return ml_config.validate_configuration()