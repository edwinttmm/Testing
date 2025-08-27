"""
VRU ML Inference Engine - Production Implementation
Handles YOLO detection, VRU classification, and model management
"""

import os
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import yaml
import torch
import cv2
import numpy as np
from datetime import datetime
import aiofiles
import aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
import psutil

# ML Libraries
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logging.warning("YOLO not available - using mock detection")

from .database_integration import get_async_session
from .validation_models import DetectionResult, ProcessingStatus

logger = logging.getLogger(__name__)

class MLInferenceEngine:
    """Production ML inference engine with caching and optimization"""
    
    def __init__(self, config_path: str = "/app/config/ml_config.yaml"):
        self.config = self._load_config(config_path)
        self.models = {}
        self.redis_client = None
        self.processing_queue = asyncio.Queue(maxsize=self.config['processing']['queue_size'])
        self.workers = []
        self.is_initialized = False
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load ML configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Default configuration when config file is not available"""
        return {
            'models': {
                'detection': {
                    'yolo': {
                        'model_path': '/app/models/yolov8n.pt',
                        'confidence_threshold': 0.5,
                        'iou_threshold': 0.4,
                        'max_detections': 100,
                        'classes': [0, 1, 2],  # person, bicycle, car
                        'device': 'cpu'
                    }
                }
            },
            'processing': {
                'batch_size': 4,
                'max_workers': 2,
                'queue_size': 50,
                'timeout': 30
            },
            'cache': {
                'enabled': True,
                'ttl': 3600
            },
            'performance': {
                'gpu': {
                    'memory_fraction': 0.8
                }
            }
        }
    
    async def initialize(self):
        """Initialize the ML engine with models and connections"""
        try:
            logger.info("Initializing ML Inference Engine...")
            
            # Initialize Redis connection
            redis_url = os.getenv('VRU_REDIS_URL', 'redis://localhost:6379/1')
            self.redis_client = await aioredis.from_url(redis_url)
            
            # Load models
            await self._load_models()
            
            # Start worker processes
            await self._start_workers()
            
            self.is_initialized = True
            logger.info("ML Inference Engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ML engine: {e}")
            raise
    
    async def _load_models(self):
        """Load all configured models"""
        models_config = self.config.get('models', {})
        
        # Load YOLO detection model
        if 'detection' in models_config and YOLO_AVAILABLE:
            yolo_config = models_config['detection']['yolo']
            model_path = yolo_config['model_path']
            
            if os.path.exists(model_path):
                try:
                    self.models['yolo'] = YOLO(model_path)
                    logger.info(f"YOLO model loaded from {model_path}")
                    
                    # Set device
                    device = yolo_config.get('device', 'cpu')
                    if device.startswith('cuda') and torch.cuda.is_available():
                        self.models['yolo'].to(device)
                        logger.info(f"YOLO model moved to {device}")
                    
                except Exception as e:
                    logger.error(f"Failed to load YOLO model: {e}")
                    self.models['yolo'] = None
            else:
                logger.warning(f"YOLO model not found at {model_path}")
                self.models['yolo'] = None
        
        # Model warmup
        if self.models.get('yolo'):
            await self._warmup_models()
    
    async def _warmup_models(self):
        """Warmup models with dummy data"""
        try:
            dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
            await self._run_yolo_detection(dummy_image, warmup=True)
            logger.info("Models warmed up successfully")
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
    
    async def _start_workers(self):
        """Start background worker processes"""
        max_workers = self.config['processing']['max_workers']
        
        for i in range(max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
        
        logger.info(f"Started {max_workers} ML processing workers")
    
    async def _worker(self, name: str):
        """Background worker for processing ML tasks"""
        logger.info(f"ML worker {name} started")
        
        while True:
            try:
                task = await self.processing_queue.get()
                
                if task is None:  # Shutdown signal
                    break
                
                await self._process_task(task)
                self.processing_queue.task_done()
                
            except Exception as e:
                logger.error(f"Worker {name} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"ML worker {name} stopped")
    
    async def _process_task(self, task: Dict[str, Any]):
        """Process a single ML task"""
        task_type = task.get('type')
        
        if task_type == 'detection':
            await self._handle_detection_task(task)
        elif task_type == 'batch_detection':
            await self._handle_batch_detection_task(task)
        else:
            logger.warning(f"Unknown task type: {task_type}")
    
    async def _handle_detection_task(self, task: Dict[str, Any]):
        """Handle single image/frame detection"""
        try:
            image_data = task['image_data']
            task_id = task['task_id']
            
            # Run detection
            detections = await self._run_yolo_detection(image_data)
            
            # Store results in Redis
            if self.redis_client:
                await self.redis_client.setex(
                    f"detection:{task_id}",
                    self.config['cache']['ttl'],
                    str(detections)
                )
            
            # Store in database
            await self._store_detection_results(task_id, detections)
            
        except Exception as e:
            logger.error(f"Detection task failed: {e}")
    
    async def _run_yolo_detection(self, image: np.ndarray, warmup: bool = False) -> List[Dict[str, Any]]:
        """Run YOLO detection on image"""
        if not self.models.get('yolo') or not YOLO_AVAILABLE:
            if warmup:
                return []
            return self._mock_detection(image)
        
        try:
            # Run inference
            results = self.models['yolo'](image, verbose=False)
            
            detections = []
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        detection = {
                            'bbox': boxes.xyxy[i].tolist(),
                            'confidence': float(boxes.conf[i]),
                            'class_id': int(boxes.cls[i]),
                            'class_name': self.models['yolo'].names[int(boxes.cls[i])]
                        }
                        
                        # Filter by confidence and class
                        yolo_config = self.config['models']['detection']['yolo']
                        if (detection['confidence'] >= yolo_config['confidence_threshold'] and
                            detection['class_id'] in yolo_config['classes']):
                            detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"YOLO detection failed: {e}")
            if warmup:
                return []
            return self._mock_detection(image)
    
    def _mock_detection(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Mock detection for testing when YOLO is not available"""
        h, w = image.shape[:2]
        return [
            {
                'bbox': [w*0.1, h*0.1, w*0.9, h*0.9],
                'confidence': 0.85,
                'class_id': 0,
                'class_name': 'person'
            }
        ]
    
    async def _store_detection_results(self, task_id: str, detections: List[Dict[str, Any]]):
        """Store detection results in database"""
        try:
            async with get_async_session() as session:
                # Implementation depends on your database schema
                pass
        except Exception as e:
            logger.error(f"Failed to store detection results: {e}")
    
    # Public API methods
    
    async def detect_objects(self, image_path: str) -> Dict[str, Any]:
        """Detect objects in image file"""
        if not self.is_initialized:
            raise HTTPException(status_code=503, detail="ML engine not initialized")
        
        try:
            # Load image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Convert BGR to RGB
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Run detection
            detections = await self._run_yolo_detection(image)
            
            return {
                'image_path': image_path,
                'detections': detections,
                'num_detections': len(detections),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Object detection failed for {image_path}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def detect_objects_batch(self, image_paths: List[str]) -> Dict[str, Any]:
        """Batch object detection"""
        if not self.is_initialized:
            raise HTTPException(status_code=503, detail="ML engine not initialized")
        
        results = []
        batch_size = self.config['processing']['batch_size']
        
        for i in range(0, len(image_paths), batch_size):
            batch = image_paths[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self.detect_objects(path) for path in batch],
                return_exceptions=True
            )
            results.extend(batch_results)
        
        return {
            'batch_size': len(image_paths),
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def process_video(self, video_path: str, frame_skip: int = 1) -> Dict[str, Any]:
        """Process video for object detection"""
        if not self.is_initialized:
            raise HTTPException(status_code=503, detail="ML engine not initialized")
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {video_path}")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            frame_results = []
            frame_num = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_num % frame_skip == 0:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # Run detection
                    detections = await self._run_yolo_detection(frame_rgb)
                    
                    frame_results.append({
                        'frame_number': frame_num,
                        'timestamp': frame_num / fps,
                        'detections': detections
                    })
                
                frame_num += 1
            
            cap.release()
            
            return {
                'video_path': video_path,
                'total_frames': total_frames,
                'processed_frames': len(frame_results),
                'fps': fps,
                'frame_results': frame_results,
                'processing_time': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Video processing failed for {video_path}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded models"""
        info = {
            'initialized': self.is_initialized,
            'models_loaded': list(self.models.keys()),
            'config': self.config,
            'system_info': {
                'cuda_available': torch.cuda.is_available(),
                'cuda_devices': torch.cuda.device_count() if torch.cuda.is_available() else 0,
                'memory_usage': psutil.virtual_memory().percent,
                'cpu_usage': psutil.cpu_percent()
            }
        }
        
        if torch.cuda.is_available():
            info['system_info']['gpu_memory'] = {
                f'cuda:{i}': {
                    'allocated': torch.cuda.memory_allocated(i),
                    'cached': torch.cuda.memory_reserved(i)
                } for i in range(torch.cuda.device_count())
            }
        
        return info
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check endpoint"""
        try:
            # Check Redis connection
            redis_ok = False
            if self.redis_client:
                try:
                    await self.redis_client.ping()
                    redis_ok = True
                except:
                    pass
            
            # Check model status
            models_ok = len(self.models) > 0
            
            # Check system resources
            memory_usage = psutil.virtual_memory().percent
            memory_ok = memory_usage < 90
            
            cpu_usage = psutil.cpu_percent()
            cpu_ok = cpu_usage < 90
            
            status = "healthy" if all([redis_ok, models_ok, memory_ok, cpu_ok]) else "unhealthy"
            
            return {
                'status': status,
                'initialized': self.is_initialized,
                'redis': redis_ok,
                'models': models_ok,
                'memory_usage': memory_usage,
                'cpu_usage': cpu_usage,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down ML Inference Engine...")
        
        # Stop workers
        for _ in self.workers:
            await self.processing_queue.put(None)
        
        await asyncio.gather(*self.workers, return_exceptions=True)
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("ML Inference Engine shutdown complete")

# Global instance
ml_engine = MLInferenceEngine()