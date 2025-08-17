"""
Model Management System for ML Pipeline

Handles model loading, versioning, hot-swapping, and optimization
"""
import os
import asyncio
import logging
import hashlib
import json
import shutil
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import torch
from ultralytics import YOLO

from ..config import ml_config

logger = logging.getLogger(__name__)

@dataclass
class ModelInfo:
    """Model information and metadata"""
    name: str
    version: str
    path: str
    size_mb: float
    hash_md5: str
    created_at: datetime
    last_used: Optional[datetime] = None
    performance_metrics: Optional[Dict[str, float]] = None
    is_active: bool = False
    device: str = "cpu"

class ModelVersionManager:
    """Manages model versions and metadata"""
    
    def __init__(self, models_dir: str = "/home/user/Testing/src/ml/models/checkpoints"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_file = self.models_dir / "models_metadata.json"
        self.models_cache: Dict[str, ModelInfo] = {}
        
        # Load existing metadata
        self._load_metadata()
    
    def _load_metadata(self):
        """Load models metadata from file"""
        try:
            if self.metadata_file.exists():
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    
                for model_data in data.get('models', []):
                    # Convert datetime strings back to datetime objects
                    model_data['created_at'] = datetime.fromisoformat(model_data['created_at'])
                    if model_data.get('last_used'):
                        model_data['last_used'] = datetime.fromisoformat(model_data['last_used'])
                    
                    model_info = ModelInfo(**model_data)
                    self.models_cache[model_info.name] = model_info
                    
            logger.info(f"Loaded metadata for {len(self.models_cache)} models")
            
        except Exception as e:
            logger.error(f"Failed to load models metadata: {str(e)}")
            self.models_cache = {}
    
    def _save_metadata(self):
        """Save models metadata to file"""
        try:
            data = {
                'models': [asdict(model_info) for model_info in self.models_cache.values()],
                'updated_at': datetime.now().isoformat()
            }
            
            # Convert datetime objects to strings for JSON serialization
            for model_data in data['models']:
                model_data['created_at'] = model_data['created_at'].isoformat()
                if model_data['last_used']:
                    model_data['last_used'] = model_data['last_used'].isoformat()
            
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Failed to save models metadata: {str(e)}")
    
    def _calculate_file_hash(self, filepath: str) -> str:
        """Calculate MD5 hash of file"""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate hash for {filepath}: {str(e)}")
            return ""
    
    def register_model(self, model_path: str, name: str, version: str) -> Optional[ModelInfo]:
        """Register a new model"""
        try:
            source_path = Path(model_path)
            if not source_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return None
            
            # Create destination path
            model_filename = f"{name}_v{version}.pt"
            dest_path = self.models_dir / model_filename
            
            # Copy model file
            if source_path != dest_path:
                shutil.copy2(source_path, dest_path)
            
            # Calculate metadata
            file_size_mb = dest_path.stat().st_size / (1024 * 1024)
            file_hash = self._calculate_file_hash(str(dest_path))
            
            # Create model info
            model_info = ModelInfo(
                name=name,
                version=version,
                path=str(dest_path),
                size_mb=round(file_size_mb, 2),
                hash_md5=file_hash,
                created_at=datetime.now(),
                device=ml_config.get_device()
            )
            
            # Store in cache
            model_key = f"{name}_v{version}"
            self.models_cache[model_key] = model_info
            
            # Save metadata
            self._save_metadata()
            
            logger.info(f"Registered model: {name} v{version} ({file_size_mb:.1f}MB)")
            return model_info
            
        except Exception as e:
            logger.error(f"Failed to register model {name} v{version}: {str(e)}")
            return None
    
    def get_model_info(self, name: str, version: str = None) -> Optional[ModelInfo]:
        """Get model information"""
        if version:
            model_key = f"{name}_v{version}"
            return self.models_cache.get(model_key)
        else:
            # Get latest version
            matching_models = [
                model for key, model in self.models_cache.items()
                if model.name == name
            ]
            if matching_models:
                return max(matching_models, key=lambda m: m.created_at)
            return None
    
    def list_models(self) -> List[ModelInfo]:
        """List all registered models"""
        return list(self.models_cache.values())
    
    def delete_model(self, name: str, version: str) -> bool:
        """Delete a model"""
        try:
            model_key = f"{name}_v{version}"
            model_info = self.models_cache.get(model_key)
            
            if not model_info:
                logger.warning(f"Model not found: {name} v{version}")
                return False
            
            # Delete file
            model_path = Path(model_info.path)
            if model_path.exists():
                model_path.unlink()
            
            # Remove from cache
            del self.models_cache[model_key]
            
            # Save metadata
            self._save_metadata()
            
            logger.info(f"Deleted model: {name} v{version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete model {name} v{version}: {str(e)}")
            return False

class ModelManager:
    """
    Comprehensive model management system
    Handles loading, optimization, hot-swapping, and performance tracking
    """
    
    def __init__(self):
        self.version_manager = ModelVersionManager()
        self.loaded_models: Dict[str, YOLO] = {}
        self.active_model: Optional[YOLO] = None
        self.active_model_info: Optional[ModelInfo] = None
        self._model_lock = asyncio.Lock()
        
    async def initialize_default_model(self) -> bool:
        """Initialize with the default YOLOv8 model"""
        try:
            # Register default model if not already registered
            default_model_path = ml_config.model_path
            
            if not Path(default_model_path).exists():
                logger.error(f"Default model not found: {default_model_path}")
                return False
            
            # Check if already registered
            model_info = self.version_manager.get_model_info("yolov8n", "default")
            
            if not model_info:
                model_info = self.version_manager.register_model(
                    default_model_path, "yolov8n", "default"
                )
            
            if model_info:
                success = await self.load_model("yolov8n", "default")
                if success:
                    await self.set_active_model("yolov8n", "default")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to initialize default model: {str(e)}")
            return False
    
    async def load_model(self, name: str, version: str = None) -> bool:
        """Load a model into memory"""
        async with self._model_lock:
            try:
                model_info = self.version_manager.get_model_info(name, version)
                if not model_info:
                    logger.error(f"Model not found: {name} v{version}")
                    return False
                
                model_key = f"{name}_v{model_info.version}"
                
                # Check if already loaded
                if model_key in self.loaded_models:
                    logger.info(f"Model already loaded: {model_key}")
                    return True
                
                # Load model
                logger.info(f"Loading model: {model_key} from {model_info.path}")
                model = YOLO(model_info.path)
                
                # Move to device
                device = ml_config.get_device()
                model.to(device)
                
                # Apply optimizations
                await self._optimize_model(model, device)
                
                # Store loaded model
                self.loaded_models[model_key] = model
                
                # Update model info
                model_info.last_used = datetime.now()
                model_info.device = device
                self.version_manager._save_metadata()
                
                logger.info(f"Successfully loaded model: {model_key} on {device}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to load model {name} v{version}: {str(e)}")
                return False
    
    async def _optimize_model(self, model: YOLO, device: str):
        """Apply model optimizations"""
        try:
            if device == "cuda":
                # Enable CUDA optimizations
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
                
                # Try to compile model for better performance (PyTorch 2.0+)
                try:
                    if hasattr(torch, 'compile'):
                        model.model = torch.compile(model.model, mode="reduce-overhead")
                        logger.info("Applied torch.compile optimization")
                except Exception as e:
                    logger.debug(f"torch.compile not available: {str(e)}")
                
                # Set to half precision if supported
                try:
                    model.half()
                    logger.info("Applied half precision optimization")
                except Exception as e:
                    logger.debug(f"Half precision not supported: {str(e)}")
            
        except Exception as e:
            logger.warning(f"Model optimization failed: {str(e)}")
    
    async def set_active_model(self, name: str, version: str = None) -> bool:
        """Set the active model for inference"""
        async with self._model_lock:
            try:
                model_info = self.version_manager.get_model_info(name, version)
                if not model_info:
                    logger.error(f"Model not found: {name} v{version}")
                    return False
                
                model_key = f"{name}_v{model_info.version}"
                
                # Ensure model is loaded
                if model_key not in self.loaded_models:
                    success = await self.load_model(name, model_info.version)
                    if not success:
                        return False
                
                # Set as active
                self.active_model = self.loaded_models[model_key]
                self.active_model_info = model_info
                
                # Update metadata
                for model in self.version_manager.models_cache.values():
                    model.is_active = False
                model_info.is_active = True
                model_info.last_used = datetime.now()
                self.version_manager._save_metadata()
                
                logger.info(f"Set active model: {model_key}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to set active model {name} v{version}: {str(e)}")
                return False
    
    def get_active_model(self) -> Optional[YOLO]:
        """Get the currently active model"""
        return self.active_model
    
    def get_active_model_info(self) -> Optional[ModelInfo]:
        """Get active model information"""
        return self.active_model_info
    
    async def hot_swap_model(self, name: str, version: str = None) -> bool:
        """Hot swap to a different model without service interruption"""
        try:
            # Load new model
            success = await self.load_model(name, version)
            if not success:
                return False
            
            # Set as active
            success = await self.set_active_model(name, version)
            if success:
                logger.info(f"Hot swapped to model: {name} v{version}")
                
                # Clean up old models (keep last 3 loaded)
                await self._cleanup_old_models()
                
            return success
            
        except Exception as e:
            logger.error(f"Hot swap failed: {str(e)}")
            return False
    
    async def _cleanup_old_models(self, keep_count: int = 3):
        """Clean up old loaded models to free memory"""
        try:
            if len(self.loaded_models) <= keep_count:
                return
            
            # Sort by last used time
            models_by_usage = []
            for model_key, model in self.loaded_models.items():
                name, version = model_key.split('_v')
                model_info = self.version_manager.get_model_info(name, version)
                if model_info and not model_info.is_active:
                    models_by_usage.append((model_key, model_info.last_used or datetime.min))
            
            # Sort by last used (oldest first)
            models_by_usage.sort(key=lambda x: x[1])
            
            # Remove oldest models
            models_to_remove = models_by_usage[:-keep_count]
            
            for model_key, _ in models_to_remove:
                del self.loaded_models[model_key]
                logger.info(f"Cleaned up model from memory: {model_key}")
            
            # Force garbage collection
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
        except Exception as e:
            logger.error(f"Model cleanup failed: {str(e)}")
    
    def get_model_performance(self, name: str, version: str = None) -> Optional[Dict[str, float]]:
        """Get model performance metrics"""
        model_info = self.version_manager.get_model_info(name, version)
        if model_info:
            return model_info.performance_metrics
        return None
    
    def update_model_performance(self, name: str, version: str, metrics: Dict[str, float]):
        """Update model performance metrics"""
        try:
            model_info = self.version_manager.get_model_info(name, version)
            if model_info:
                model_info.performance_metrics = metrics
                self.version_manager._save_metadata()
                logger.info(f"Updated performance metrics for {name} v{version}")
        except Exception as e:
            logger.error(f"Failed to update performance metrics: {str(e)}")
    
    async def benchmark_model(self, name: str, version: str = None, num_iterations: int = 100) -> Dict[str, float]:
        """Benchmark model performance"""
        try:
            import numpy as np
            import time
            
            model_info = self.version_manager.get_model_info(name, version)
            if not model_info:
                return {}
            
            model_key = f"{name}_v{model_info.version}"
            if model_key not in self.loaded_models:
                await self.load_model(name, model_info.version)
            
            model = self.loaded_models[model_key]
            
            # Create dummy input
            dummy_input = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            # Warmup
            for _ in range(10):
                _ = model(dummy_input, verbose=False)
            
            # Benchmark
            inference_times = []
            
            for _ in range(num_iterations):
                start_time = time.time()
                _ = model(dummy_input, verbose=False)
                inference_time = (time.time() - start_time) * 1000  # Convert to ms
                inference_times.append(inference_time)
            
            # Calculate metrics
            metrics = {
                "avg_inference_time_ms": np.mean(inference_times),
                "min_inference_time_ms": np.min(inference_times),
                "max_inference_time_ms": np.max(inference_times),
                "std_inference_time_ms": np.std(inference_times),
                "fps": 1000 / np.mean(inference_times)
            }
            
            # Update model performance
            self.update_model_performance(name, model_info.version, metrics)
            
            logger.info(f"Benchmarked model {name} v{model_info.version}: {metrics['avg_inference_time_ms']:.1f}ms avg")
            return metrics
            
        except Exception as e:
            logger.error(f"Model benchmarking failed: {str(e)}")
            return {}
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for model management"""
        try:
            import psutil
            
            info = {
                "loaded_models": len(self.loaded_models),
                "active_model": f"{self.active_model_info.name}_v{self.active_model_info.version}" if self.active_model_info else None,
                "available_models": len(self.version_manager.models_cache),
                "device": ml_config.get_device(),
                "cuda_available": torch.cuda.is_available(),
                "memory_usage_mb": psutil.virtual_memory().used / (1024 * 1024)
            }
            
            if torch.cuda.is_available():
                info["gpu_memory_allocated_mb"] = torch.cuda.memory_allocated() / (1024 * 1024)
                info["gpu_memory_cached_mb"] = torch.cuda.memory_reserved() / (1024 * 1024)
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get system info: {str(e)}")
            return {}
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        async with self._model_lock:
            self.loaded_models.clear()
            self.active_model = None
            self.active_model_info = None
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Model manager shut down")

# Global model manager instance
model_manager = ModelManager()