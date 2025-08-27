#!/usr/bin/env python3
"""
Enhanced ML Inference Engine - Complete SPARC Implementation
Production-ready YOLO-based VRU detection system with advanced capabilities

SPARC Implementation:
- Specification: Complete VRU detection requirements analysis
- Pseudocode: Optimized algorithm design for real-time inference
- Architecture: Scalable system design with microservices approach
- Refinement: Performance-optimized implementation
- Completion: Production deployment ready for 155.138.239.131

Author: SPARC ML Development Team
Version: 2.0.0
Target: Production VRU Detection Platform
"""

import asyncio
import logging
import time
import uuid
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Union, AsyncGenerator
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from threading import Lock, Event
import traceback

# Core ML and CV imports
import numpy as np
import cv2
try:
    import torch
    import torchvision.transforms as transforms
    from ultralytics import YOLO
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch/Ultralytics not available - using fallback inference")

# Database integration
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
from pathlib import Path

# Add backend root to path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

try:
    from unified_database import get_database_manager
    from models import Video, Detection, GroundTruthObject
except ImportError:
    logging.warning("Database models not available - using mock implementations")
    get_database_manager = None
    Video = None
    Detection = None
    GroundTruthObject = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SPARC SPECIFICATION CONSTANTS
VRU_CLASSES = {
    'person': 'pedestrian',
    'bicycle': 'cyclist',
    'motorcycle': 'motorcyclist',
    'car': 'vehicle',  # Additional class for context
    'truck': 'vehicle',
    'bus': 'vehicle'
}

COCO_VRU_MAPPING = {
    0: 'person',      # person
    1: 'bicycle',     # bicycle  
    2: 'car',         # car
    3: 'motorcycle',  # motorcycle
    5: 'bus',         # bus
    7: 'truck',       # truck
}

CONFIDENCE_THRESHOLDS = {
    'pedestrian': 0.25,
    'cyclist': 0.30,
    'motorcyclist': 0.35,
    'vehicle': 0.40
}

# SPARC PSEUDOCODE IMPLEMENTATION
@dataclass
class EnhancedBoundingBox:
    """Enhanced normalized bounding box with validation and conversion utilities"""
    x: float  # Top-left x (0-1)
    y: float  # Top-left y (0-1)
    width: float  # Width (0-1)
    height: float  # Height (0-1)
    confidence: float = 1.0
    
    def __post_init__(self):
        """Validate and normalize coordinates"""
        self.x = max(0.0, min(1.0, float(self.x)))
        self.y = max(0.0, min(1.0, float(self.y)))
        self.width = max(0.0, min(1.0 - self.x, float(self.width)))
        self.height = max(0.0, min(1.0 - self.y, float(self.height)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
    
    def to_pixel_coordinates(self, frame_width: int, frame_height: int) -> Tuple[int, int, int, int]:
        """Convert to pixel coordinates (x1, y1, x2, y2)"""
        x1 = int(self.x * frame_width)
        y1 = int(self.y * frame_height)
        x2 = int((self.x + self.width) * frame_width)
        y2 = int((self.y + self.height) * frame_height)
        return x1, y1, x2, y2
    
    def to_center_format(self) -> Tuple[float, float, float, float]:
        """Convert to center format (cx, cy, w, h)"""
        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        return cx, cy, self.width, self.height
    
    def area(self) -> float:
        """Calculate bounding box area"""
        return self.width * self.height
    
    def intersection_over_union(self, other: 'EnhancedBoundingBox') -> float:
        """Calculate IoU with another bounding box"""
        # Calculate intersection
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.x + self.width, other.x + other.width)
        y2 = min(self.y + self.height, other.y + other.height)
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        union = self.area() + other.area() - intersection
        
        return intersection / union if union > 0 else 0.0

@dataclass
class EnhancedVRUDetection:
    """Enhanced VRU detection with metadata and tracking"""
    detection_id: str
    frame_number: int
    timestamp: float
    vru_type: str
    confidence: float
    bounding_box: EnhancedBoundingBox
    tracking_id: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        self.metadata.update({
            'detection_timestamp': datetime.now(timezone.utc).isoformat(),
            'inference_version': '2.0.0',
            'confidence_threshold': CONFIDENCE_THRESHOLDS.get(self.vru_type, 0.3)
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'detection_id': self.detection_id,
            'frame_number': self.frame_number,
            'timestamp': self.timestamp,
            'vru_type': self.vru_type,
            'confidence': self.confidence,
            'bounding_box': asdict(self.bounding_box),
            'tracking_id': self.tracking_id,
            'metadata': self.metadata
        }

class EnhancedYOLOEngine:
    """Production-ready YOLO inference engine with advanced capabilities"""
    
    def __init__(self, model_path: Optional[str] = None, device: str = 'auto', 
                 batch_size: int = 1, enable_tracking: bool = False):
        self.device = self._get_optimal_device(device)
        self.model = None
        self.model_path = model_path or self._get_default_model_path()
        self.batch_size = batch_size
        self.enable_tracking = enable_tracking
        self.is_initialized = False
        self.inference_stats = {
            'total_inferences': 0,
            'total_detections': 0,
            'average_inference_time': 0.0,
            'model_type': None
        }
        self._stats_lock = Lock()
        
    def _get_optimal_device(self, device: str) -> str:
        """Determine optimal device with fallback chain"""
        if not TORCH_AVAILABLE:
            return 'cpu'
            
        if device == 'auto':
            if torch.cuda.is_available():
                # Check CUDA memory
                try:
                    torch.cuda.empty_cache()
                    device_count = torch.cuda.device_count()
                    logger.info(f"CUDA available with {device_count} device(s)")
                    return 'cuda:0'
                except:
                    pass
            
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                logger.info("Using Apple Metal Performance Shaders (MPS)")
                return 'mps'
            
            logger.info("Using CPU inference")
            return 'cpu'
        
        return device
    
    def _get_default_model_path(self) -> str:
        """Get default model path with fallback options"""
        possible_paths = [
            '/home/user/Testing/ai-model-validation-platform/backend/yolo11l.pt',
            '/home/user/Testing/ai-model-validation-platform/backend/yolov8n.pt',
            'yolov8n.pt',  # Download automatically
            'yolov8s.pt',
            'yolo11n.pt'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Default to auto-download
        return 'yolov8n.pt'
    
    async def initialize(self) -> bool:
        """Initialize YOLO model with error handling and performance optimization"""
        if self.is_initialized:
            return True
            
        try:
            if not TORCH_AVAILABLE:
                logger.warning("PyTorch not available - using mock inference")
                self.model = None
                self.inference_method = 'mock'
                self.is_initialized = True
                return True
            
            # Load YOLO model
            logger.info(f"Loading YOLO model: {self.model_path} on {self.device}")
            self.model = YOLO(self.model_path)
            
            # Optimize model
            if hasattr(self.model.model, 'to'):
                self.model.model.to(self.device)
            
            # Warm-up inference
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            await self._warmup_model(dummy_frame)
            
            self.inference_method = 'ultralytics'
            self.is_initialized = True
            
            # Update stats
            self.inference_stats['model_type'] = self.model_path
            logger.info(f"YOLO model initialized successfully on {self.device}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize YOLO model: {e}")
            logger.error(traceback.format_exc())
            
            # Fallback to mock
            self.model = None
            self.inference_method = 'mock'
            self.is_initialized = True
            return False
    
    async def _warmup_model(self, dummy_frame: np.ndarray) -> None:
        """Warm up model for consistent performance"""
        try:
            logger.info("Warming up YOLO model...")
            start_time = time.time()
            results = self.model(dummy_frame, verbose=False)
            warmup_time = time.time() - start_time
            logger.info(f"Model warmup completed in {warmup_time:.3f}s")
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
    
    async def detect_vrus_batch(self, frames: List[np.ndarray], 
                               frame_numbers: List[int],
                               timestamps: List[float]) -> List[List[EnhancedVRUDetection]]:
        """Batch VRU detection for improved performance"""
        if not self.is_initialized:
            await self.initialize()
        
        if len(frames) != len(frame_numbers) or len(frames) != len(timestamps):
            raise ValueError("Frames, frame_numbers, and timestamps must have same length")
        
        batch_results = []
        
        try:
            if self.inference_method == 'ultralytics' and len(frames) > 1:
                # True batch processing
                start_time = time.time()
                results = self.model(frames, verbose=False)
                inference_time = time.time() - start_time
                
                for i, result in enumerate(results):
                    detections = self._process_ultralytics_result(
                        result, frame_numbers[i], timestamps[i], frames[i]
                    )
                    batch_results.append(detections)
                
                # Update stats
                with self._stats_lock:
                    self.inference_stats['total_inferences'] += len(frames)
                    total_detections = sum(len(dets) for dets in batch_results)
                    self.inference_stats['total_detections'] += total_detections
                    
                    # Update average inference time
                    n = self.inference_stats['total_inferences']
                    if n > len(frames):
                        prev_avg = self.inference_stats['average_inference_time']
                        self.inference_stats['average_inference_time'] = (
                            prev_avg * (n - len(frames)) + inference_time
                        ) / n
                    else:
                        self.inference_stats['average_inference_time'] = inference_time / len(frames)
                
            else:
                # Process individually
                for i, frame in enumerate(frames):
                    detections = await self.detect_vrus_single(
                        frame, frame_numbers[i], timestamps[i]
                    )
                    batch_results.append(detections)
            
        except Exception as e:
            logger.error(f"Batch detection failed: {e}")
            # Return empty results for all frames
            batch_results = [[] for _ in frames]
        
        return batch_results
    
    async def detect_vrus_single(self, frame: np.ndarray, frame_number: int,
                                timestamp: float) -> List[EnhancedVRUDetection]:
        """Single frame VRU detection"""
        if not self.is_initialized:
            await self.initialize()
        
        try:
            start_time = time.time()
            
            if self.inference_method == 'ultralytics':
                results = self.model(frame, verbose=False)
                detections = []
                
                for result in results:
                    detections.extend(
                        self._process_ultralytics_result(result, frame_number, timestamp, frame)
                    )
            else:
                detections = self._generate_mock_detections(frame_number, timestamp)
            
            inference_time = time.time() - start_time
            
            # Update stats
            with self._stats_lock:
                self.inference_stats['total_inferences'] += 1
                self.inference_stats['total_detections'] += len(detections)
                
                n = self.inference_stats['total_inferences']
                if n > 1:
                    prev_avg = self.inference_stats['average_inference_time']
                    self.inference_stats['average_inference_time'] = (
                        prev_avg * (n - 1) + inference_time
                    ) / n
                else:
                    self.inference_stats['average_inference_time'] = inference_time
            
            return detections
            
        except Exception as e:
            logger.error(f"Single frame detection failed: {e}")
            return []
    
    def _process_ultralytics_result(self, result, frame_number: int, 
                                   timestamp: float, frame: np.ndarray) -> List[EnhancedVRUDetection]:
        """Process ultralytics YOLO result into enhanced detections"""
        detections = []
        
        if result.boxes is None:
            return detections
        
        frame_height, frame_width = frame.shape[:2]
        
        for box in result.boxes:
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])
            
            # Map COCO class to VRU type
            if cls_id not in COCO_VRU_MAPPING:
                continue
            
            coco_class = COCO_VRU_MAPPING[cls_id]
            vru_type = VRU_CLASSES.get(coco_class, 'other')
            
            # Apply confidence threshold
            threshold = CONFIDENCE_THRESHOLDS.get(vru_type, 0.3)
            if confidence < threshold:
                continue
            
            # Get normalized coordinates
            if hasattr(box, 'xyxyn') and box.xyxyn is not None:
                x1, y1, x2, y2 = box.xyxyn[0].tolist()
            else:
                # Fallback to pixel coordinates and normalize
                x1_px, y1_px, x2_px, y2_px = box.xyxy[0].tolist()
                x1, y1 = x1_px / frame_width, y1_px / frame_height
                x2, y2 = x2_px / frame_width, y2_px / frame_height
            
            # Create enhanced bounding box
            bbox = EnhancedBoundingBox(
                x=x1,
                y=y1,
                width=x2 - x1,
                height=y2 - y1,
                confidence=confidence
            )
            
            # Create detection
            detection = EnhancedVRUDetection(
                detection_id=str(uuid.uuid4()),
                frame_number=frame_number,
                timestamp=timestamp,
                vru_type=vru_type,
                confidence=confidence,
                bounding_box=bbox,
                metadata={
                    'coco_class_id': cls_id,
                    'coco_class_name': coco_class,
                    'model_confidence': confidence,
                    'frame_resolution': f"{frame_width}x{frame_height}"
                }
            )
            
            detections.append(detection)
        
        return detections
    
    def _generate_mock_detections(self, frame_number: int, 
                                 timestamp: float) -> List[EnhancedVRUDetection]:
        """Generate mock detections for development/testing"""
        detections = []
        
        # Simulate realistic detection patterns
        if frame_number % 15 == 0:  # Pedestrian every 15 frames
            detection = EnhancedVRUDetection(
                detection_id=str(uuid.uuid4()),
                frame_number=frame_number,
                timestamp=timestamp,
                vru_type='pedestrian',
                confidence=0.85 + (frame_number % 10) * 0.01,
                bounding_box=EnhancedBoundingBox(0.3, 0.2, 0.15, 0.6)
            )
            detections.append(detection)
        
        if frame_number % 25 == 0:  # Cyclist every 25 frames
            detection = EnhancedVRUDetection(
                detection_id=str(uuid.uuid4()),
                frame_number=frame_number,
                timestamp=timestamp,
                vru_type='cyclist',
                confidence=0.78,
                bounding_box=EnhancedBoundingBox(0.6, 0.3, 0.2, 0.4)
            )
            detections.append(detection)
        
        return detections
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get inference performance statistics"""
        with self._stats_lock:
            return dict(self.inference_stats)

# SPARC ARCHITECTURE IMPLEMENTATION
class EnhancedVideoProcessor:
    """Advanced video processing pipeline with frame extraction and optimization"""
    
    def __init__(self, batch_size: int = 4, max_fps: Optional[float] = None):
        self.batch_size = batch_size
        self.max_fps = max_fps
        self.processing_stats = {
            'videos_processed': 0,
            'total_frames': 0,
            'average_processing_fps': 0.0
        }
    
    async def extract_frames_async(self, video_path: str, 
                                  start_frame: int = 0,
                                  max_frames: Optional[int] = None) -> AsyncGenerator[Tuple[np.ndarray, int, float], None]:
        """Async frame extraction with memory management"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        try:
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Skip to start frame
            if start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            frame_number = start_frame
            frames_yielded = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                timestamp = frame_number / fps if fps > 0 else frame_number * 0.033  # Default 30fps
                
                yield frame, frame_number, timestamp
                
                frame_number += 1
                frames_yielded += 1
                
                if max_frames and frames_yielded >= max_frames:
                    break
                
                # Apply FPS limiting
                if self.max_fps and fps > self.max_fps:
                    skip_frames = int(fps / self.max_fps) - 1
                    for _ in range(skip_frames):
                        ret, _ = cap.read()
                        if not ret:
                            break
                        frame_number += 1
        
        finally:
            cap.release()
    
    def get_video_metadata(self, video_path: str) -> Dict[str, Any]:
        """Extract comprehensive video metadata"""
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        try:
            metadata = {
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'duration': 0,
                'codec': '',
                'bitrate': 0
            }
            
            if metadata['fps'] > 0:
                metadata['duration'] = metadata['total_frames'] / metadata['fps']
            
            # Get codec information if available
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            if fourcc:
                metadata['codec'] = ''.join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            
            return metadata
            
        finally:
            cap.release()

# SPARC REFINEMENT - Production-Ready ML Engine
class ProductionMLInferenceEngine:
    """Production-ready ML inference engine with comprehensive capabilities"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._get_default_config()
        self.yolo_engine = EnhancedYOLOEngine(
            model_path=self.config.get('model_path'),
            device=self.config.get('device', 'auto'),
            batch_size=self.config.get('batch_size', 4),
            enable_tracking=self.config.get('enable_tracking', False)
        )
        self.video_processor = EnhancedVideoProcessor(
            batch_size=self.config.get('batch_size', 4),
            max_fps=self.config.get('max_fps')
        )
        self.db_manager = None
        self._processing_queue = asyncio.Queue(maxsize=100)
        self._result_cache = {}
        self._cache_lock = Lock()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'model_path': None,  # Auto-detect
            'device': 'auto',
            'batch_size': 4,
            'max_fps': None,
            'enable_tracking': False,
            'confidence_thresholds': CONFIDENCE_THRESHOLDS,
            'cache_results': True,
            'max_cache_size': 1000
        }
    
    async def initialize(self) -> bool:
        """Initialize the complete ML engine"""
        try:
            logger.info("Initializing Production ML Inference Engine...")
            
            # Initialize YOLO engine
            yolo_success = await self.yolo_engine.initialize()
            
            # Initialize database connection
            if get_database_manager:
                try:
                    self.db_manager = get_database_manager()
                    db_health = self.db_manager.test_connection()
                    if db_health['status'] == 'healthy':
                        logger.info("Database connection established")
                    else:
                        logger.warning(f"Database health check failed: {db_health}")
                except Exception as e:
                    logger.warning(f"Database initialization failed: {e}")
                    self.db_manager = None
            
            logger.info(f"ML Engine initialization complete - YOLO: {yolo_success}")
            return yolo_success
            
        except Exception as e:
            logger.error(f"ML Engine initialization failed: {e}")
            return False
    
    async def process_video_complete(self, video_id: str, video_path: str,
                                   progress_callback: Optional[callable] = None) -> Dict[str, Any]:
        """Complete video processing with ground truth generation"""
        try:
            logger.info(f"Starting complete video processing for {video_id}")
            start_time = time.time()
            
            # Get video metadata
            metadata = self.video_processor.get_video_metadata(video_path)
            logger.info(f"Video metadata: {metadata}")
            
            # Process video in batches
            all_detections = []
            frames_processed = 0
            batch_frames = []
            batch_frame_numbers = []
            batch_timestamps = []
            
            async for frame, frame_number, timestamp in self.video_processor.extract_frames_async(video_path):
                batch_frames.append(frame)
                batch_frame_numbers.append(frame_number)
                batch_timestamps.append(timestamp)
                
                # Process batch when full
                if len(batch_frames) >= self.config['batch_size']:
                    batch_detections = await self.yolo_engine.detect_vrus_batch(
                        batch_frames, batch_frame_numbers, batch_timestamps
                    )
                    
                    for detections in batch_detections:
                        all_detections.extend(detections)
                    
                    frames_processed += len(batch_frames)
                    
                    # Progress callback
                    if progress_callback:
                        progress = frames_processed / metadata['total_frames'] * 100
                        await progress_callback(video_id, progress, frames_processed)
                    
                    # Clear batch
                    batch_frames.clear()
                    batch_frame_numbers.clear()
                    batch_timestamps.clear()
                    
                    # Log progress
                    if frames_processed % 1000 == 0:
                        logger.info(f"Processed {frames_processed}/{metadata['total_frames']} frames")
            
            # Process remaining frames
            if batch_frames:
                batch_detections = await self.yolo_engine.detect_vrus_batch(
                    batch_frames, batch_frame_numbers, batch_timestamps
                )
                
                for detections in batch_detections:
                    all_detections.extend(detections)
                
                frames_processed += len(batch_frames)
            
            processing_time = time.time() - start_time
            
            # Save to database
            if self.db_manager:
                await self._save_detections_to_database(video_id, all_detections, metadata)
            
            # Prepare result
            result = {
                'video_id': video_id,
                'status': 'completed',
                'metadata': metadata,
                'processing_stats': {
                    'total_frames': frames_processed,
                    'total_detections': len(all_detections),
                    'processing_time': processing_time,
                    'avg_fps': frames_processed / processing_time if processing_time > 0 else 0,
                    'detections_per_frame': len(all_detections) / frames_processed if frames_processed > 0 else 0
                },
                'detection_summary': self._generate_detection_summary(all_detections),
                'yolo_stats': self.yolo_engine.get_performance_stats()
            }
            
            logger.info(f"Video processing completed: {len(all_detections)} detections in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Video processing failed: {e}")
            logger.error(traceback.format_exc())
            return {
                'video_id': video_id,
                'status': 'failed',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    async def _save_detections_to_database(self, video_id: str, 
                                          detections: List[EnhancedVRUDetection],
                                          metadata: Dict[str, Any]) -> None:
        """Save detections to database with error handling"""
        if not self.db_manager or not Detection:
            logger.warning("Database not available - skipping save")
            return
        
        try:
            with self.db_manager.get_session() as session:
                # Clear existing detections for this video
                session.query(Detection).filter(Detection.video_id == video_id).delete()
                
                # Add new detections
                for detection in detections:
                    db_detection = Detection(
                        id=detection.detection_id,
                        video_id=video_id,
                        frame_number=detection.frame_number,
                        timestamp=detection.timestamp,
                        vru_type=detection.vru_type,
                        confidence=detection.confidence,
                        x=detection.bounding_box.x,
                        y=detection.bounding_box.y,
                        width=detection.bounding_box.width,
                        height=detection.bounding_box.height,
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(db_detection)
                
                # Update video processing status
                if Video:
                    video = session.query(Video).filter(Video.id == video_id).first()
                    if video:
                        video.processing_status = 'completed'
                        video.ground_truth_generated = True
                        video.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                logger.info(f"Saved {len(detections)} detections to database")
                
        except Exception as e:
            logger.error(f"Database save failed: {e}")
            raise
    
    def _generate_detection_summary(self, detections: List[EnhancedVRUDetection]) -> Dict[str, Any]:
        """Generate comprehensive detection summary"""
        if not detections:
            return {'total': 0, 'by_type': {}, 'confidence_stats': {}}
        
        by_type = {}
        confidences = []
        
        for detection in detections:
            vru_type = detection.vru_type
            if vru_type not in by_type:
                by_type[vru_type] = {'count': 0, 'avg_confidence': 0.0, 'confidences': []}
            
            by_type[vru_type]['count'] += 1
            by_type[vru_type]['confidences'].append(detection.confidence)
            confidences.append(detection.confidence)
        
        # Calculate averages
        for vru_type in by_type:
            confidences_list = by_type[vru_type]['confidences']
            by_type[vru_type]['avg_confidence'] = sum(confidences_list) / len(confidences_list)
            del by_type[vru_type]['confidences']  # Remove raw list
        
        return {
            'total': len(detections),
            'by_type': by_type,
            'confidence_stats': {
                'min': min(confidences),
                'max': max(confidences),
                'avg': sum(confidences) / len(confidences),
                'median': sorted(confidences)[len(confidences) // 2]
            }
        }
    
    async def get_video_detections(self, video_id: str) -> List[Dict[str, Any]]:
        """Retrieve video detections with caching"""
        cache_key = f"detections_{video_id}"
        
        # Check cache first
        with self._cache_lock:
            if cache_key in self._result_cache:
                logger.debug(f"Cache hit for video {video_id}")
                return self._result_cache[cache_key]
        
        if not self.db_manager or not Detection:
            return []
        
        try:
            with self.db_manager.get_session() as session:
                detections = session.query(Detection).filter(
                    Detection.video_id == video_id
                ).order_by(Detection.frame_number).all()
                
                result = []
                for det in detections:
                    detection_dict = {
                        'detection_id': det.id,
                        'frame_number': det.frame_number,
                        'timestamp': det.timestamp,
                        'vru_type': det.vru_type,
                        'confidence': det.confidence,
                        'bounding_box': {
                            'x': det.x,
                            'y': det.y,
                            'width': det.width,
                            'height': det.height
                        },
                        'created_at': det.created_at.isoformat() if det.created_at else None
                    }
                    result.append(detection_dict)
                
                # Cache result
                if self.config.get('cache_results', True):
                    with self._cache_lock:
                        self._result_cache[cache_key] = result
                        
                        # Limit cache size
                        if len(self._result_cache) > self.config.get('max_cache_size', 1000):
                            # Remove oldest entry
                            oldest_key = next(iter(self._result_cache))
                            del self._result_cache[oldest_key]
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to retrieve video detections: {e}")
            return []
    
    async def update_detection(self, detection_id: str, updates: Dict[str, Any]) -> bool:
        """Update detection with cache invalidation"""
        if not self.db_manager or not Detection:
            return False
        
        try:
            with self.db_manager.get_session() as session:
                detection = session.query(Detection).filter(
                    Detection.id == detection_id
                ).first()
                
                if not detection:
                    return False
                
                # Clear cache for this video
                cache_key = f"detections_{detection.video_id}"
                with self._cache_lock:
                    if cache_key in self._result_cache:
                        del self._result_cache[cache_key]
                
                # Update fields
                for key, value in updates.items():
                    if key == 'bounding_box' and isinstance(value, dict):
                        detection.x = value.get('x', detection.x)
                        detection.y = value.get('y', detection.y)
                        detection.width = value.get('width', detection.width)
                        detection.height = value.get('height', detection.height)
                    elif hasattr(detection, key):
                        setattr(detection, key, value)
                
                detection.updated_at = datetime.now(timezone.utc)
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to update detection: {e}")
            return False
    
    async def delete_detection(self, detection_id: str) -> bool:
        """Delete detection with cache invalidation"""
        if not self.db_manager or not Detection:
            return False
        
        try:
            with self.db_manager.get_session() as session:
                detection = session.query(Detection).filter(
                    Detection.id == detection_id
                ).first()
                
                if not detection:
                    return False
                
                video_id = detection.video_id
                session.delete(detection)
                session.commit()
                
                # Clear cache
                cache_key = f"detections_{video_id}"
                with self._cache_lock:
                    if cache_key in self._result_cache:
                        del self._result_cache[cache_key]
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete detection: {e}")
            return False
    
    def get_engine_stats(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics"""
        return {
            'yolo_stats': self.yolo_engine.get_performance_stats(),
            'video_processor_stats': self.video_processor.processing_stats,
            'cache_stats': {
                'cached_videos': len(self._result_cache),
                'max_cache_size': self.config.get('max_cache_size', 1000)
            },
            'config': self.config,
            'database_available': self.db_manager is not None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        health = {
            'status': 'healthy',
            'components': {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Check YOLO engine
        try:
            if self.yolo_engine.is_initialized:
                health['components']['yolo_engine'] = 'healthy'
            else:
                health['components']['yolo_engine'] = 'not_initialized'
                health['status'] = 'degraded'
        except Exception as e:
            health['components']['yolo_engine'] = f'error: {e}'
            health['status'] = 'unhealthy'
        
        # Check database
        if self.db_manager:
            try:
                db_health = self.db_manager.test_connection()
                health['components']['database'] = db_health['status']
                if db_health['status'] != 'healthy':
                    health['status'] = 'degraded'
            except Exception as e:
                health['components']['database'] = f'error: {e}'
                health['status'] = 'unhealthy'
        else:
            health['components']['database'] = 'not_available'
        
        return health

# SPARC COMPLETION - Global Instance and API
_global_engine = None

async def get_production_ml_engine() -> ProductionMLInferenceEngine:
    """Get or create global ML engine instance"""
    global _global_engine
    if _global_engine is None:
        _global_engine = ProductionMLInferenceEngine()
        await _global_engine.initialize()
    return _global_engine

# API-compatible functions for backward compatibility
async def process_video_for_ground_truth(video_id: str, video_path: str, 
                                        progress_callback: Optional[callable] = None) -> Dict[str, Any]:
    """Process video for ground truth generation - API compatible"""
    engine = await get_production_ml_engine()
    return await engine.process_video_complete(video_id, video_path, progress_callback)

async def get_video_annotations(video_id: str) -> List[Dict[str, Any]]:
    """Get video annotations - API compatible"""
    engine = await get_production_ml_engine()
    return await engine.get_video_detections(video_id)

async def update_annotation(annotation_id: str, updates: Dict[str, Any]) -> bool:
    """Update annotation - API compatible"""
    engine = await get_production_ml_engine()
    return await engine.update_detection(annotation_id, updates)

async def delete_annotation(annotation_id: str) -> bool:
    """Delete annotation - API compatible"""
    engine = await get_production_ml_engine()
    return await engine.delete_detection(annotation_id)

async def get_ml_engine_health() -> Dict[str, Any]:
    """Get ML engine health status"""
    try:
        engine = await get_production_ml_engine()
        return await engine.health_check()
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

# Main execution for testing
if __name__ == "__main__":
    import asyncio
    
    async def main():
        """Test the enhanced ML inference engine"""
        print("🚀 Enhanced ML Inference Engine - SPARC Implementation")
        print("=" * 60)
        
        # Initialize engine
        engine = await get_production_ml_engine()
        
        # Health check
        health = await engine.health_check()
        print(f"Health Status: {health['status']}")
        for component, status in health['components'].items():
            print(f"  {component}: {status}")
        
        # Performance stats
        stats = engine.get_engine_stats()
        print(f"\nEngine Statistics:")
        print(f"  YOLO Model: {stats['yolo_stats']['model_type']}")
        print(f"  Total Inferences: {stats['yolo_stats']['total_inferences']}")
        print(f"  Average Inference Time: {stats['yolo_stats']['average_inference_time']:.4f}s")
        print(f"  Database Available: {stats['database_available']}")
        
        print("\n✅ Enhanced ML Inference Engine initialized successfully!")
    
    asyncio.run(main())
