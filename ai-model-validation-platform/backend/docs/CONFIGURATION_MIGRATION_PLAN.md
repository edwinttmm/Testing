# Configuration Management Migration Plan

**Project**: AI Model Validation Platform - Ground Truth System
**Phase**: Eliminate Hardcoded Values & Implement Centralized Configuration
**Timeline**: 6 weeks
**Priority**: CRITICAL

## Migration Strategy Overview

This plan systematically removes 187 identified hardcoded values and implements a robust, hierarchical configuration management system following industry best practices.

### Core Principles
1. **Security First**: No secrets in code or version control
2. **Environment Parity**: Identical deployment process across environments
3. **Configuration as Code**: Versioned, validated, and documented
4. **Fail-Safe Defaults**: Sensible defaults with clear override mechanisms
5. **Runtime Flexibility**: Change behavior without code deployment

## Phase 1: Critical Security & Infrastructure (Week 1)

### 🔐 Priority 1A: Secret Management (Days 1-2)

#### Current State Problems
```python
# CRITICAL SECURITY ISSUE - Remove immediately
secret_key = 'INSECURE-DEFAULT-CHANGE-ME'
SERVICE_TOKEN = 'st_v1_0t7C9mQ2wX5pL8rS1uV4yB7dE0gH3kN6qT9zA2fJ5mR8xC1vD4pF7sG0jK3n'
```

#### Implementation Steps

**Step 1.1: Create Secret Management Module**
```python
# src/config/secrets.py
import os
import secrets
from typing import Optional
from cryptography.fernet import Fernet

class SecretManager:
    """Centralized secret management with multiple backend support"""
    
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key) if self.encryption_key else None
    
    def _get_encryption_key(self) -> Optional[bytes]:
        """Get encryption key from environment or generate new one"""
        key_env = os.getenv('ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        return None
    
    def get_secret(self, key: str, default: Optional[str] = None) -> str:
        """Get secret with fallback hierarchy"""
        # 1. Environment variable
        value = os.getenv(key)
        if value:
            return value
            
        # 2. Encrypted secrets file (future)
        # value = self._get_from_secrets_file(key)
        
        # 3. Default (only for non-production)
        if default and not self._is_production():
            return default
            
        raise ValueError(f"Secret '{key}' not found and no default provided")
    
    def generate_secret_key(self, length: int = 32) -> str:
        """Generate cryptographically secure secret"""
        return secrets.token_urlsafe(length)
    
    def _is_production(self) -> bool:
        """Check if running in production"""
        return os.getenv('ENVIRONMENT', '').lower() in ['production', 'prod']

secret_manager = SecretManager()
```

**Step 1.2: Update Configuration Class**
```python
# config.py - Update Settings class
from src.config.secrets import secret_manager

class Settings(BaseSettings):
    # Security - NO DEFAULTS for production secrets
    secret_key: str = secret_manager.get_secret('SECRET_KEY')
    jwt_secret_key: str = secret_manager.get_secret('JWT_SECRET_KEY') 
    service_token: str = secret_manager.get_secret('SERVICE_TOKEN')
    
    # Database credentials
    database_password: str = secret_manager.get_secret('DATABASE_PASSWORD')
    redis_password: Optional[str] = secret_manager.get_secret('REDIS_PASSWORD', None)
```

**Step 1.3: Environment Template Creation**
```bash
# .env.template - Safe to commit
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
SERVICE_TOKEN=your-service-token-here
DATABASE_PASSWORD=your-db-password-here
REDIS_PASSWORD=your-redis-password-here

# .env.development.template
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-change-in-production
# ... development-safe defaults

# .env.production.template  
SECRET_KEY=REQUIRED-GENERATE-SECURE-KEY
JWT_SECRET_KEY=REQUIRED-GENERATE-SECURE-KEY
# ... no defaults for production
```

### 🗃️ Priority 1B: Database Configuration (Days 3-4)

#### Create Database Configuration Module
```python
# src/config/database.py
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import os

class DatabaseConfig:
    """Centralized database configuration management"""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self._config = self._load_database_config()
    
    def _load_database_config(self) -> Dict[str, Any]:
        """Load database configuration with environment-specific defaults"""
        
        base_config = {
            'pool_size': int(os.getenv('DATABASE_POOL_SIZE', '10')),
            'max_overflow': int(os.getenv('DATABASE_MAX_OVERFLOW', '20')),
            'pool_timeout': int(os.getenv('DATABASE_POOL_TIMEOUT', '30')),
            'pool_recycle': int(os.getenv('DATABASE_POOL_RECYCLE', '3600')),
            'echo': os.getenv('DATABASE_ECHO', 'false').lower() == 'true',
        }
        
        # Environment-specific defaults
        if self.environment == 'production':
            base_config.update({
                'pool_size': 20,
                'max_overflow': 40,
                'pool_timeout': 60,
                'echo': False
            })
        elif self.environment == 'test':
            base_config.update({
                'pool_size': 1,
                'max_overflow': 0,
                'echo': False
            })
        
        return base_config
    
    def get_database_url(self) -> str:
        """Get database URL with environment-specific fallbacks"""
        # Priority order for database URL
        url_candidates = [
            os.getenv('VRU_DATABASE_URL'),
            os.getenv('DATABASE_URL'),
            os.getenv('AIVALIDATION_DATABASE_URL'),
            self._get_default_database_url()
        ]
        
        for url in url_candidates:
            if url:
                return self._validate_database_url(url)
        
        raise ValueError("No valid database URL configured")
    
    def _get_default_database_url(self) -> str:
        """Get environment-appropriate default database URL"""
        if self.environment == 'test':
            return 'sqlite:///./test_database.db'
        elif self.environment == 'development':
            return 'sqlite:///./dev_database.db'
        else:
            # Production requires explicit configuration
            return None
    
    def _validate_database_url(self, url: str) -> str:
        """Validate and potentially modify database URL"""
        parsed = urlparse(url)
        
        if not parsed.scheme:
            raise ValueError(f"Invalid database URL scheme: {url}")
        
        # Security check for production
        if self.environment == 'production':
            if parsed.scheme == 'sqlite':
                raise ValueError("SQLite not allowed in production")
            if 'localhost' in parsed.netloc:
                raise ValueError("Localhost database not allowed in production")
        
        return url

database_config = DatabaseConfig()
```

### 📁 Priority 1C: Path Management System (Days 5-7)

#### Centralized Path Configuration
```python
# src/config/paths.py
from pathlib import Path
import os
from typing import Dict, Union
from enum import Enum

class PathType(Enum):
    UPLOAD = "upload"
    SCREENSHOTS = "screenshots"
    MODELS = "models"
    EXPORTS = "exports"
    LOGS = "logs"
    TEMP = "temp"
    CONFIG = "config"

class PathManager:
    """Centralized path management with environment awareness"""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.base_dir = Path(os.getenv('APP_BASE_DIR', os.getcwd()))
        self._paths = self._initialize_paths()
    
    def _initialize_paths(self) -> Dict[PathType, Path]:
        """Initialize all path configurations"""
        
        # Base paths from environment or defaults
        paths = {
            PathType.UPLOAD: self._resolve_path('UPLOAD_DIRECTORY', 'uploads'),
            PathType.SCREENSHOTS: self._resolve_path('SCREENSHOTS_DIRECTORY', 'screenshots'),
            PathType.MODELS: self._resolve_path('MODELS_DIRECTORY', 'models'),
            PathType.EXPORTS: self._resolve_path('EXPORTS_DIRECTORY', 'exports'),
            PathType.LOGS: self._resolve_path('LOGS_DIRECTORY', 'logs'),
            PathType.TEMP: self._resolve_path('TEMP_DIRECTORY', 'temp'),
            PathType.CONFIG: self._resolve_path('CONFIG_DIRECTORY', 'config'),
        }
        
        # Environment-specific overrides
        if self.environment == 'production':
            paths.update({
                PathType.UPLOAD: Path('/app/data/uploads'),
                PathType.MODELS: Path('/app/models'),
                PathType.LOGS: Path('/app/logs'),
                PathType.TEMP: Path('/tmp/aivalidation'),
            })
        elif self.environment == 'test':
            # Use temp directories for testing
            import tempfile
            temp_base = Path(tempfile.mkdtemp(prefix='aivalidation_test_'))
            for path_type in PathType:
                paths[path_type] = temp_base / path_type.value
        
        return paths
    
    def _resolve_path(self, env_var: str, default: str) -> Path:
        """Resolve path from environment variable or default"""
        path_str = os.getenv(env_var, default)
        path = Path(path_str)
        
        # Convert relative paths to absolute
        if not path.is_absolute():
            path = self.base_dir / path
        
        return path
    
    def get_path(self, path_type: PathType) -> Path:
        """Get path for specific type"""
        return self._paths[path_type]
    
    def ensure_path_exists(self, path_type: PathType) -> Path:
        """Ensure path exists and return it"""
        path = self.get_path(path_type)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_model_path(self, model_name: str) -> Path:
        """Get full path for a model file"""
        return self.get_path(PathType.MODELS) / model_name
    
    def get_export_path(self, export_name: str) -> Path:
        """Get full path for an export file"""
        return self.ensure_path_exists(PathType.EXPORTS) / export_name

path_manager = PathManager()
```

## Phase 2: ML Model Configuration (Week 2-3)

### 🤖 ML Model Configuration System

#### Create ML Configuration Module
```python
# src/config/ml_models.py
from typing import Dict, List, Any, Optional
from pathlib import Path
import yaml
import os
from src.config.paths import path_manager, PathType

class MLModelConfig:
    """Centralized ML model configuration management"""
    
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
        self.config = self._load_ml_config()
    
    def _load_ml_config(self) -> Dict[str, Any]:
        """Load ML configuration from hierarchy"""
        # 1. Load base configuration
        base_config = self._get_base_ml_config()
        
        # 2. Load from config file if exists
        config_file = path_manager.get_path(PathType.CONFIG) / 'ml_models.yaml'
        if config_file.exists():
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f)
                base_config.update(file_config)
        
        # 3. Environment variable overrides
        env_overrides = self._get_env_overrides()
        base_config.update(env_overrides)
        
        return base_config
    
    def _get_base_ml_config(self) -> Dict[str, Any]:
        """Get base ML configuration with environment-specific defaults"""
        
        if self.environment == 'production':
            return {
                'yolo': {
                    'primary_model': 'yolo11l.pt',  # Best accuracy for production
                    'fallback_model': 'yolov8n.pt',
                    'confidence_threshold': 0.7,  # Higher threshold for production
                    'iou_threshold': 0.4,
                    'max_detections': 100,
                    'device': 'cuda' if self._cuda_available() else 'cpu',
                    'batch_size': 8,
                    'timeout_seconds': 30
                },
                'detection': {
                    'enable_validation': True,
                    'auto_validate_threshold': 0.85,
                    'manual_review_threshold': 0.65,
                    'quality_threshold': 0.8
                }
            }
        elif self.environment == 'development':
            return {
                'yolo': {
                    'primary_model': 'yolov8n.pt',  # Faster for development
                    'fallback_model': 'yolov8n.pt',
                    'confidence_threshold': 0.01,  # Lower for debugging
                    'iou_threshold': 0.4,
                    'max_detections': 50,
                    'device': 'cpu',  # Stable for development
                    'batch_size': 2,
                    'timeout_seconds': 15
                },
                'detection': {
                    'enable_validation': False,  # Skip validation in dev
                    'auto_validate_threshold': 0.8,
                    'manual_review_threshold': 0.5,
                    'quality_threshold': 0.5
                }
            }
        else:  # test environment
            return {
                'yolo': {
                    'primary_model': 'mock',  # Use mock for testing
                    'fallback_model': 'mock',
                    'confidence_threshold': 0.5,
                    'device': 'cpu',
                    'batch_size': 1,
                    'timeout_seconds': 5
                }
            }
    
    def _get_env_overrides(self) -> Dict[str, Any]:
        """Get configuration overrides from environment variables"""
        overrides = {}
        
        # YOLO model overrides
        if os.getenv('ML_PRIMARY_MODEL'):
            overrides.setdefault('yolo', {})['primary_model'] = os.getenv('ML_PRIMARY_MODEL')
        
        if os.getenv('ML_CONFIDENCE_THRESHOLD'):
            overrides.setdefault('yolo', {})['confidence_threshold'] = float(os.getenv('ML_CONFIDENCE_THRESHOLD'))
        
        if os.getenv('ML_DEVICE'):
            overrides.setdefault('yolo', {})['device'] = os.getenv('ML_DEVICE')
        
        return overrides
    
    def get_model_path(self, model_name: str) -> Path:
        """Get full path to model file"""
        if model_name == 'mock':
            return None  # Use mock model
        
        # Try configured model paths in order
        search_paths = [
            path_manager.get_path(PathType.MODELS) / model_name,
            Path.cwd() / model_name,  # Current directory
            Path.cwd() / 'models' / model_name,  # Local models directory
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        # Model not found locally - will need to download
        return path_manager.get_path(PathType.MODELS) / model_name
    
    def get_yolo_config(self) -> Dict[str, Any]:
        """Get YOLO-specific configuration"""
        return self.config.get('yolo', {})
    
    def get_detection_config(self) -> Dict[str, Any]:
        """Get detection pipeline configuration"""
        return self.config.get('detection', {})
    
    def _cuda_available(self) -> bool:
        """Check if CUDA is available"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

ml_config = MLModelConfig()
```

#### Update Ground Truth Service
```python
# services/ground_truth_service.py - Remove hardcoded values
from src.config.ml_models import ml_config
from src.config.paths import path_manager, PathType

class GroundTruthService:
    def __init__(self):
        self.ml_available = ML_AVAILABLE
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Get configuration instead of hardcoded values
        self.yolo_config = ml_config.get_yolo_config()
        self.detection_config = ml_config.get_detection_config()
        
        if self.ml_available:
            self._initialize_model()
    
    def _initialize_model(self):
        """Initialize YOLO model with configured parameters"""
        try:
            primary_model = self.yolo_config.get('primary_model', 'yolov8n.pt')
            fallback_model = self.yolo_config.get('fallback_model', 'yolov8n.pt')
            
            # Try primary model first
            model_path = ml_config.get_model_path(primary_model)
            if model_path and model_path.exists():
                self.model = YOLO(str(model_path))
                self.model_version = primary_model
                logger.info(f"✅ Loaded primary model: {primary_model}")
            else:
                # Try fallback model
                fallback_path = ml_config.get_model_path(fallback_model)
                self.model = YOLO(str(fallback_path))
                self.model_version = fallback_model
                logger.info(f"✅ Loaded fallback model: {fallback_model}")
                
        except Exception as e:
            logger.error(f"❌ Failed to load YOLO model: {e}")
            self.ml_available = False
    
    def _extract_detections(self, video_path: str) -> List[Dict[str, Any]]:
        """Extract detections using configured parameters"""
        if not self.ml_available or not self.model:
            return []
        
        detections = []
        confidence_threshold = self.yolo_config.get('confidence_threshold', 0.5)
        
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                timestamp = (frame_count - 1) / fps
                
                # Run YOLO inference with configured timeout
                results = self.model(frame, verbose=False)
                
                # Process detections with configured threshold
                boxes = results[0].boxes if results and len(results) > 0 else None
                if boxes is not None:
                    for box in boxes:
                        class_id = int(box.cls.cpu().numpy()[0])
                        confidence = float(box.conf.cpu().numpy()[0])
                        
                        # Use configured confidence threshold
                        if class_id in self.vru_classes and confidence > confidence_threshold:
                            x1, y1, x2, y2 = box.xyxy.cpu().numpy()[0]
                            
                            # Generate screenshot using configured paths
                            screenshot_path, screenshot_zoom_path = self._generate_screenshot(
                                frame, x1, y1, x2, y2, frame_count, self.vru_classes[class_id]
                            )
                            
                            detection = {
                                "frame_number": frame_count,
                                "timestamp": timestamp,
                                "class_label": self.vru_classes[class_id],
                                "x": float(x1),
                                "y": float(y1),
                                "width": float(x2 - x1),
                                "height": float(y2 - y1),
                                "confidence": confidence,
                                "validated": confidence >= self.detection_config.get('auto_validate_threshold', 0.8),
                                "difficult": False,
                                "screenshot_path": screenshot_path,
                                "screenshot_zoom_path": screenshot_zoom_path
                            }
                            detections.append(detection)
            
            cap.release()
            return detections
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            return []
    
    def _generate_screenshot(self, frame, x1, y1, x2, y2, frame_number, class_label):
        """Generate screenshots using configured paths"""
        try:
            # Use configured screenshots directory
            screenshots_dir = path_manager.ensure_path_exists(PathType.SCREENSHOTS)
            
            detection_id = str(uuid.uuid4())
            
            # Full frame screenshot with bounding box
            screenshot_frame = frame.copy()
            cv2.rectangle(screenshot_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
            cv2.putText(screenshot_frame, f"{class_label} ({frame_number})", 
                       (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            full_screenshot_path = screenshots_dir / f"ground_truth_{detection_id}.jpg"
            cv2.imwrite(str(full_screenshot_path), screenshot_frame)
            
            # Zoomed screenshot
            padding = 20
            x1_crop = max(0, int(x1) - padding)
            y1_crop = max(0, int(y1) - padding)
            x2_crop = min(frame.shape[1], int(x2) + padding)
            y2_crop = min(frame.shape[0], int(y2) + padding)
            
            cropped_frame = frame[y1_crop:y2_crop, x1_crop:x2_crop]
            
            adjusted_x1 = int(x1) - x1_crop
            adjusted_y1 = int(y1) - y1_crop
            adjusted_x2 = int(x2) - x1_crop
            adjusted_y2 = int(y2) - y1_crop
            
            cv2.rectangle(cropped_frame, (adjusted_x1, adjusted_y1), (adjusted_x2, adjusted_y2), (0, 255, 0), 2)
            cv2.putText(cropped_frame, class_label, (adjusted_x1, adjusted_y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            zoom_screenshot_path = screenshots_dir / f"ground_truth_{detection_id}_zoom.jpg"
            cv2.imwrite(str(zoom_screenshot_path), cropped_frame)
            
            return str(full_screenshot_path), str(zoom_screenshot_path)
            
        except Exception as e:
            logger.error(f"Failed to generate screenshot: {e}")
            return None, None
```

## Phase 3: API & Network Configuration (Week 4)

### 🌐 Network Configuration Module

```python
# src/config/network.py
from typing import List, Dict, Any
import os
from src.config.environment import environment_detector

class NetworkConfig:
    """Centralized network and API configuration"""
    
    def __init__(self):
        self.environment = environment_detector.get_environment()
        self.config = self._load_network_config()
    
    def _load_network_config(self) -> Dict[str, Any]:
        """Load network configuration with environment-specific defaults"""
        
        base_config = {
            'api': {
                'host': os.getenv('API_HOST', '0.0.0.0'),
                'port': int(os.getenv('API_PORT', '8000')),
                'workers': int(os.getenv('API_WORKERS', self._get_default_workers())),
                'timeout': int(os.getenv('API_TIMEOUT', self._get_default_timeout())),
                'max_request_size': int(os.getenv('MAX_REQUEST_SIZE', self._get_default_max_size())),
            },
            'cors': {
                'origins': self._get_cors_origins(),
                'credentials': os.getenv('CORS_CREDENTIALS', 'true').lower() == 'true',
                'methods': self._get_cors_methods(),
                'headers': self._get_cors_headers(),
                'max_age': int(os.getenv('CORS_MAX_AGE', '3600'))
            },
            'timeouts': {
                'request': int(os.getenv('REQUEST_TIMEOUT', '30')),
                'database': int(os.getenv('DATABASE_TIMEOUT', '30')),
                'ml_inference': int(os.getenv('ML_INFERENCE_TIMEOUT', '60')),
                'websocket': int(os.getenv('WEBSOCKET_TIMEOUT', '300')),
                'file_upload': int(os.getenv('FILE_UPLOAD_TIMEOUT', '600')),
            }
        }
        
        return base_config
    
    def _get_default_workers(self) -> str:
        """Get default worker count based on environment"""
        if self.environment.is_production():
            return '4'
        elif self.environment.is_staging():
            return '2'
        else:
            return '1'
    
    def _get_default_timeout(self) -> str:
        """Get default timeout based on environment"""
        if self.environment.is_production():
            return '60'
        else:
            return '30'
    
    def _get_default_max_size(self) -> str:
        """Get default max request size"""
        if self.environment.is_production():
            return str(500 * 1024 * 1024)  # 500MB
        else:
            return str(100 * 1024 * 1024)  # 100MB
    
    def _get_cors_origins(self) -> List[str]:
        """Get CORS origins with environment-specific defaults"""
        # Environment variable override
        cors_env = os.getenv('CORS_ORIGINS')
        if cors_env:
            return [origin.strip() for origin in cors_env.split(',')]
        
        # Environment-specific defaults
        if self.environment.is_production():
            return [
                "https://vru-validation.company.com",
                "https://api.company.com"
            ]
        elif self.environment.is_staging():
            return [
                "https://staging-vru.company.com",
                "http://localhost:3000"  # For testing
            ]
        else:  # development
            return [
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3001"
            ]
    
    def _get_cors_methods(self) -> List[str]:
        """Get allowed CORS methods"""
        methods_env = os.getenv('CORS_METHODS')
        if methods_env:
            return [method.strip() for method in methods_env.split(',')]
        
        return ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    
    def _get_cors_headers(self) -> List[str]:
        """Get allowed CORS headers"""
        headers_env = os.getenv('CORS_HEADERS')
        if headers_env:
            return [header.strip() for header in headers_env.split(',')]
        
        return ["*"]
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self.config['api']
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration"""
        return self.config['cors']
    
    def get_timeout_config(self) -> Dict[str, Any]:
        """Get timeout configuration"""
        return self.config['timeouts']

network_config = NetworkConfig()
```

## Phase 4: Configuration Validation & Testing (Week 5)

### ✅ Configuration Validation System

```python
# src/config/validation.py
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class ConfigurationValidator:
    """Validates configuration integrity and security"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self, config: Dict[str, Any]) -> bool:
        """Validate entire configuration"""
        self.errors.clear()
        self.warnings.clear()
        
        # Validate different configuration sections
        self._validate_security(config.get('security', {}))
        self._validate_database(config.get('database', {}))
        self._validate_paths(config.get('paths', {}))
        self._validate_ml_models(config.get('ml_models', {}))
        self._validate_network(config.get('network', {}))
        
        # Log results
        if self.errors:
            logger.error(f"Configuration validation failed with {len(self.errors)} errors:")
            for error in self.errors:
                logger.error(f"  - {error}")
        
        if self.warnings:
            logger.warning(f"Configuration validation has {len(self.warnings)} warnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        return len(self.errors) == 0
    
    def _validate_security(self, security_config: Dict[str, Any]):
        """Validate security configuration"""
        required_secrets = ['secret_key', 'jwt_secret_key']
        
        for secret in required_secrets:
            value = security_config.get(secret)
            if not value:
                self.errors.append(f"Missing required secret: {secret}")
            elif len(value) < 32:
                self.warnings.append(f"Secret '{secret}' should be at least 32 characters")
            elif value in ['INSECURE-DEFAULT-CHANGE-ME', 'your-secret-key-here']:
                self.errors.append(f"Using insecure default for {secret}")
    
    def _validate_database(self, db_config: Dict[str, Any]):
        """Validate database configuration"""
        db_url = db_config.get('url')
        if not db_url:
            self.errors.append("Missing database URL")
            return
        
        # Validate URL format
        if not re.match(r'^(sqlite|postgresql|mysql)://', db_url):
            self.errors.append(f"Invalid database URL format: {db_url}")
        
        # Production-specific validations
        environment = db_config.get('environment', 'development')
        if environment == 'production':
            if 'sqlite://' in db_url:
                self.warnings.append("SQLite not recommended for production")
            if 'localhost' in db_url:
                self.warnings.append("Localhost database not recommended for production")
    
    def _validate_paths(self, paths_config: Dict[str, Any]):
        """Validate path configuration"""
        required_paths = ['upload', 'screenshots', 'models', 'logs']
        
        for path_name in required_paths:
            path_value = paths_config.get(path_name)
            if not path_value:
                self.errors.append(f"Missing required path: {path_name}")
                continue
            
            path = Path(path_value)
            if not path.parent.exists():
                self.warnings.append(f"Parent directory does not exist for {path_name}: {path}")
    
    def _validate_ml_models(self, ml_config: Dict[str, Any]):
        """Validate ML model configuration"""
        yolo_config = ml_config.get('yolo', {})
        
        # Validate confidence thresholds
        confidence_threshold = yolo_config.get('confidence_threshold')
        if confidence_threshold is not None:
            if not 0.0 <= confidence_threshold <= 1.0:
                self.errors.append(f"Invalid confidence threshold: {confidence_threshold}")
        
        # Validate model paths
        primary_model = yolo_config.get('primary_model')
        if primary_model and primary_model != 'mock':
            # Check if model exists or can be downloaded
            pass  # Implementation depends on model management strategy
    
    def _validate_network(self, network_config: Dict[str, Any]):
        """Validate network configuration"""
        api_config = network_config.get('api', {})
        
        # Validate port
        port = api_config.get('port')
        if port and not 1 <= port <= 65535:
            self.errors.append(f"Invalid API port: {port}")
        
        # Validate CORS origins
        cors_config = network_config.get('cors', {})
        origins = cors_config.get('origins', [])
        
        for origin in origins:
            if not re.match(r'^https?://', origin) and origin != '*':
                self.warnings.append(f"Invalid CORS origin format: {origin}")

validator = ConfigurationValidator()
```

## Phase 5: Implementation & Rollout (Week 6)

### 🚀 Implementation Strategy

#### Step 5.1: Configuration Loading Order
```python
# src/config/__init__.py
"""
Configuration loading with proper hierarchy:
1. Default values (in code)
2. Configuration files (config/*.yaml)
3. Environment variables
4. Runtime overrides (future: admin interface)
"""

from .secrets import secret_manager
from .database import database_config  
from .paths import path_manager
from .ml_models import ml_config
from .network import network_config
from .validation import validator

class UnifiedConfig:
    """Single source of truth for all configuration"""
    
    def __init__(self):
        self.secrets = secret_manager
        self.database = database_config
        self.paths = path_manager
        self.ml_models = ml_config
        self.network = network_config
        
        # Validate configuration on load
        config_dict = self._to_dict()
        if not validator.validate_all(config_dict):
            raise ValueError("Configuration validation failed")
    
    def _to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for validation"""
        return {
            'security': {
                'secret_key': getattr(self.secrets, 'secret_key', None),
                'jwt_secret_key': getattr(self.secrets, 'jwt_secret_key', None),
            },
            'database': {
                'url': self.database.get_database_url(),
                'environment': self.database.environment,
            },
            'paths': {
                path_type.value: str(self.paths.get_path(path_type))
                for path_type in PathType
            },
            'ml_models': self.ml_models.config,
            'network': {
                'api': self.network.get_api_config(),
                'cors': self.network.get_cors_config(),
                'timeouts': self.network.get_timeout_config(),
            }
        }
    
    def reload(self):
        """Reload configuration (for runtime updates)"""
        self.__init__()

# Global configuration instance
config = UnifiedConfig()
```

#### Step 5.2: Migration Script
```python
# scripts/migrate_hardcoded_values.py
"""
Automated migration script to replace hardcoded values
"""

import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

class HardcodedValueMigrator:
    """Migrates hardcoded values to configuration system"""
    
    def __init__(self, backend_dir: Path):
        self.backend_dir = backend_dir
        self.backup_dir = backend_dir / 'migration_backups'
        self.migration_log = []
    
    def migrate_all(self):
        """Run complete migration"""
        print("🔄 Starting hardcoded values migration...")
        
        # Create backup
        self._create_backup()
        
        # Migrate each category
        self._migrate_model_paths()
        self._migrate_confidence_thresholds()
        self._migrate_file_paths()
        self._migrate_network_configs()
        
        # Generate report
        self._generate_migration_report()
        
        print("✅ Migration completed successfully!")
    
    def _create_backup(self):
        """Create backup of original files"""
        print("📦 Creating backup...")
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        # Backup key files
        important_files = [
            'config.py',
            'services/ground_truth_service.py',
            'src/ml_inference_engine.py',
            'main.py'
        ]
        
        for file_path in important_files:
            source = self.backend_dir / file_path
            if source.exists():
                dest = self.backup_dir / file_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                print(f"  ✅ Backed up {file_path}")
    
    def _migrate_model_paths(self):
        """Migrate hardcoded model paths"""
        print("🤖 Migrating ML model paths...")
        
        # Find all Python files with model paths
        pattern = re.compile(r"'([^']*yolo[^']*\.pt)'|\"([^\"]*yolo[^\"]*\.pt)\"")
        
        for py_file in self.backend_dir.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
                
            content = py_file.read_text()
            original_content = content
            
            # Replace hardcoded model paths
            def replace_model_path(match):
                model_path = match.group(1) or match.group(2)
                model_name = Path(model_path).name
                
                # Generate replacement
                replacement = f"ml_config.get_model_path('{model_name}')"
                
                self.migration_log.append({
                    'file': str(py_file.relative_to(self.backend_dir)),
                    'old': match.group(0),
                    'new': replacement,
                    'type': 'model_path'
                })
                
                return f"str({replacement})"
            
            content = pattern.sub(replace_model_path, content)
            
            if content != original_content:
                # Add import if needed
                if 'from src.config.ml_models import ml_config' not in content:
                    content = self._add_import(content, 'from src.config.ml_models import ml_config')
                
                py_file.write_text(content)
                print(f"  ✅ Updated {py_file.relative_to(self.backend_dir)}")
    
    def _migrate_confidence_thresholds(self):
        """Migrate hardcoded confidence thresholds"""
        print("📊 Migrating confidence thresholds...")
        
        # Pattern for confidence comparisons
        pattern = re.compile(r'confidence\s*[><=]+\s*0\.\d+')
        
        # This is more complex and requires semantic analysis
        # For now, just log occurrences for manual review
        threshold_files = []
        
        for py_file in self.backend_dir.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
                
            content = py_file.read_text()
            matches = pattern.findall(content)
            
            if matches:
                threshold_files.append({
                    'file': str(py_file.relative_to(self.backend_dir)),
                    'matches': matches
                })
        
        print(f"  📋 Found confidence thresholds in {len(threshold_files)} files")
        print("  ⚠️  Manual review required for confidence threshold migration")
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped during migration"""
        skip_patterns = [
            'venv/', 'test_env/', '.venv/', '__pycache__/',
            'migration_backups/', '.git/', 'docs/',
            'tests/', 'scripts/'
        ]
        
        str_path = str(file_path)
        return any(pattern in str_path for pattern in skip_patterns)

# Usage
if __name__ == "__main__":
    backend_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend")
    migrator = HardcodedValueMigrator(backend_dir)
    migrator.migrate_all()
```

## Implementation Checklist

### Week 1: Critical Security
- [ ] Implement SecretManager class
- [ ] Create environment templates (.env.template, etc.)
- [ ] Remove hardcoded secrets from all files  
- [ ] Update Settings class to use SecretManager
- [ ] Test secret loading in all environments
- [ ] Add security validation checks
- [ ] Update deployment documentation

### Week 2-3: Core Infrastructure
- [ ] Implement DatabaseConfig class
- [ ] Create PathManager system
- [ ] Implement MLModelConfig class
- [ ] Update GroundTruthService to use configs
- [ ] Create configuration validation system
- [ ] Test configuration loading hierarchy
- [ ] Add environment-specific defaults

### Week 4: Network & API
- [ ] Implement NetworkConfig class
- [ ] Update CORS configuration
- [ ] Centralize timeout management
- [ ] Update API configuration
- [ ] Test multi-environment deployments
- [ ] Add configuration health checks

### Week 5-6: Testing & Rollout
- [ ] Create comprehensive test suite
- [ ] Run migration scripts
- [ ] Validate all environments
- [ ] Update documentation
- [ ] Deploy to staging
- [ ] Deploy to production
- [ ] Monitor and adjust

## Post-Migration Monitoring

### Key Metrics to Track
1. **Configuration Load Time**: < 1 second
2. **Environment Deployment Success**: 100%
3. **Configuration Validation Pass Rate**: 100%
4. **Secret Security Score**: No hardcoded secrets
5. **Documentation Coverage**: All parameters documented

### Success Criteria
- ✅ Zero hardcoded secrets in codebase
- ✅ Single-command deployment to any environment  
- ✅ Configuration changes without code changes
- ✅ Environment parity maintained
- ✅ Clear audit trail for all configuration changes

---

**Implementation Priority**: CRITICAL - Begin Phase 1 immediately
**Risk Level**: HIGH if not implemented within 6 weeks
**Dependencies**: DevOps team for environment setup, Security team for secret management
