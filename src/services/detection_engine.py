"""
VRU Detection Engine - YOLOv8 Integration
Real-time vulnerable road user detection with <50ms latency target
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import cv2

try:
    import torch
    import torchvision.transforms as transforms
    from ultralytics import YOLO
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch/Ultralytics not available - using mock detection engine")

from src.core.config import settings, DetectionConfig
from src.core.exceptions import VRUDetectionException
from src.models.database import VRUClass

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    """Bounding box coordinates"""
    x: float
    y: float
    width: float
    height: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "x": self.x,
            "y": self.y, 
            "width": self.width,
            "height": self.height
        }
    
    def area(self) -> float:
        return self.width * self.height
    
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


@dataclass
class Detection:
    """Single VRU detection result"""
    id: str
    class_label: str
    confidence: float
    bounding_box: BoundingBox
    timestamp: float
    frame_number: int
    
    def is_valid(self) -> bool:
        """Check if detection meets validation criteria"""
        # Check confidence threshold
        min_confidence = DetectionConfig.CONFIDENCE_THRESHOLDS.get(self.class_label, 0.5)
        if self.confidence < min_confidence:
            return False
        
        # Check bounding box area
        area = self.bounding_box.area()
        if area < DetectionConfig.MIN_BOUNDING_BOX_AREA or area > DetectionConfig.MAX_BOUNDING_BOX_AREA:
            return False
        
        # Check aspect ratio
        aspect_ratio = self.bounding_box.width / self.bounding_box.height
        if aspect_ratio < DetectionConfig.MIN_ASPECT_RATIO or aspect_ratio > DetectionConfig.MAX_ASPECT_RATIO:
            return False
        
        return True


@dataclass
class DetectionBatch:
    """Batch of detections for a frame"""
    frame_number: int
    timestamp: float
    detections: List[Detection]
    processing_time_ms: float
    
    def get_valid_detections(self) -> List[Detection]:
        """Get only valid detections from the batch"""
        return [d for d in self.detections if d.is_valid()]


class ModelManager:
    """Manage ML model loading and caching"""
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.model_cache_size = settings.MODEL_CACHE_SIZE
        self.model_dir = settings.MODEL_DIR
        self.device = self._get_device()
        
    def _get_device(self) -> str:
        """Determine the best device for inference"""
        if not TORCH_AVAILABLE:
            return "cpu"
        
        if torch.cuda.is_available():
            # Check GPU memory
            if torch.cuda.get_device_properties(0).total_memory > 2 * 1024**3:  # 2GB
                return "cuda:0"
        
        # Check for MPS (Apple Silicon)
        if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"
        
        return "cpu"
    
    async def load_model(self, model_name: str = None) -> Any:
        """Load YOLOv8 model"""
        if not TORCH_AVAILABLE:
            return MockDetectionModel()
        
        model_name = model_name or settings.DEFAULT_MODEL_NAME
        
        if model_name in self.models:
            return self.models[model_name]
        
        try:
            model_path = self.model_dir / model_name
            
            if not model_path.exists():
                # Download default model if not found
                logger.info(f"Model {model_name} not found, downloading...")
                model = YOLO(model_name)  # This will download the model
            else:
                model = YOLO(str(model_path))
            
            # Move model to appropriate device
            model.to(self.device)
            
            # Cache the model
            if len(self.models) >= self.model_cache_size:
                # Remove oldest model
                oldest_model = next(iter(self.models))
                del self.models[oldest_model]
                
            self.models[model_name] = model
            
            logger.info(f"Model {model_name} loaded successfully on {self.device}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise VRUDetectionException(
                "MODEL_LOAD_FAILED",
                f"Failed to load detection model: {model_name}",
                details={"error": str(e)}
            )
    
    def unload_model(self, model_name: str) -> None:
        """Unload model from memory"""
        if model_name in self.models:
            del self.models[model_name]
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info(f"Model {model_name} unloaded")


class MockDetectionModel:
    """Mock detection model for testing when PyTorch is not available"""
    
    def __init__(self):
        self.device = "cpu"
        
    def predict(self, frame: np.ndarray, **kwargs) -> List[Dict]:
        """Mock prediction that returns random detections"""
        import random
        
        height, width = frame.shape[:2]
        
        # Generate 0-3 random detections
        num_detections = random.randint(0, 3)
        results = []
        
        for _ in range(num_detections):
            # Random class
            class_id = random.randint(0, 5)
            class_names = list(VRUClass)
            class_label = class_names[class_id].value
            
            # Random bounding box
            x = random.randint(0, width - 100)
            y = random.randint(0, height - 100)
            w = random.randint(50, min(200, width - x))
            h = random.randint(80, min(300, height - y))
            
            # Random confidence
            confidence = random.uniform(0.3, 0.95)
            
            results.append({
                "class": class_id,
                "class_name": class_label,
                "confidence": confidence,
                "bbox": [x, y, w, h]
            })
        
        return results
    
    def to(self, device: str):
        """Mock device assignment"""
        self.device = device
        return self


class FrameProcessor:
    """Process video frames for detection"""
    
    def __init__(self):
        self.preprocessing_enabled = True
        
    async def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for detection"""
        if not self.preprocessing_enabled:
            return frame
        
        try:
            # Resize if needed (maintain aspect ratio)
            height, width = frame.shape[:2]
            max_size = 640  # YOLOv8 default input size
            
            if max(height, width) > max_size:
                scale = max_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
            
            # Normalize pixel values
            frame = frame.astype(np.float32) / 255.0
            
            return frame
            
        except Exception as e:
            logger.error(f"Frame preprocessing failed: {e}")
            return frame
    
    def postprocess_detections(
        self, 
        raw_detections: List[Dict], 
        frame_shape: Tuple[int, int],
        frame_number: int,
        timestamp: float
    ) -> List[Detection]:
        """Convert raw model output to Detection objects"""
        detections = []
        
        for i, det in enumerate(raw_detections):
            try:
                # Extract detection data
                if TORCH_AVAILABLE and hasattr(det, 'boxes'):
                    # Ultralytics YOLO format
                    boxes = det.boxes
                    for j, box in enumerate(boxes):
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        
                        # Map class ID to VRU class
                        class_names = list(VRUClass)
                        if class_id < len(class_names):
                            class_label = class_names[class_id].value
                        else:
                            continue  # Skip unknown classes
                        
                        # Create bounding box
                        bbox = BoundingBox(
                            x=float(x1),
                            y=float(y1),
                            width=float(x2 - x1),
                            height=float(y2 - y1)
                        )
                        
                        detection = Detection(
                            id=f"{frame_number}_{j}_{uuid.uuid4().hex[:8]}",
                            class_label=class_label,
                            confidence=float(confidence),
                            bounding_box=bbox,
                            timestamp=timestamp,
                            frame_number=frame_number
                        )
                        
                        detections.append(detection)
                        
                else:
                    # Mock format
                    bbox = BoundingBox(
                        x=det["bbox"][0],
                        y=det["bbox"][1],
                        width=det["bbox"][2],
                        height=det["bbox"][3]
                    )
                    
                    detection = Detection(
                        id=f"{frame_number}_{i}_{uuid.uuid4().hex[:8]}",
                        class_label=det["class_name"],
                        confidence=det["confidence"],
                        bounding_box=bbox,
                        timestamp=timestamp,
                        frame_number=frame_number
                    )
                    
                    detections.append(detection)
                    
            except Exception as e:
                logger.error(f"Failed to process detection {i}: {e}")
                continue
        
        return detections


class NonMaximumSuppression:
    """Non-Maximum Suppression for overlapping detections"""
    
    @staticmethod
    def calculate_iou(box1: BoundingBox, box2: BoundingBox) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes"""
        x1 = max(box1.x, box2.x)
        y1 = max(box1.y, box2.y)
        x2 = min(box1.x + box1.width, box2.x + box2.width)
        y2 = min(box1.y + box1.height, box2.y + box2.height)
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = box1.area()
        area2 = box2.area()
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    @classmethod
    def apply(cls, detections: List[Detection], threshold: float = 0.45) -> List[Detection]:
        """Apply Non-Maximum Suppression to reduce overlapping detections"""
        if not detections:
            return []
        
        # Group detections by class
        class_groups = {}
        for detection in detections:
            if detection.class_label not in class_groups:
                class_groups[detection.class_label] = []
            class_groups[detection.class_label].append(detection)
        
        # Apply NMS per class
        final_detections = []
        for class_label, class_detections in class_groups.items():
            # Sort by confidence (highest first)
            class_detections.sort(key=lambda d: d.confidence, reverse=True)
            
            # Get class-specific threshold
            class_threshold = DetectionConfig.NMS_THRESHOLDS.get(class_label, threshold)
            
            selected = []
            for detection in class_detections:
                # Check if this detection overlaps significantly with already selected ones
                should_keep = True
                for selected_detection in selected:
                    iou = cls.calculate_iou(detection.bounding_box, selected_detection.bounding_box)
                    if iou > class_threshold:
                        should_keep = False
                        break
                
                if should_keep:
                    selected.append(detection)
            
            final_detections.extend(selected)
        
        return final_detections


class DetectionEngine:
    """Main VRU Detection Engine"""
    
    def __init__(self):
        self.model_manager = ModelManager()
        self.frame_processor = FrameProcessor()
        self.nms = NonMaximumSuppression()
        self.model = None
        self.processing_stats = {
            "total_frames": 0,
            "total_detections": 0,
            "total_processing_time": 0.0,
            "average_fps": 0.0
        }
        
    async def initialize(self) -> None:
        """Initialize the detection engine"""
        try:
            logger.info("Initializing VRU Detection Engine...")
            
            # Load default model
            self.model = await self.model_manager.load_model()
            
            # Warm up the model
            await self._warmup_model()
            
            logger.info("VRU Detection Engine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize detection engine: {e}")
            raise VRUDetectionException(
                "DETECTION_ENGINE_INIT_FAILED",
                "Failed to initialize detection engine",
                details={"error": str(e)}
            )
    
    async def detect_frame(
        self, 
        frame: np.ndarray, 
        frame_number: int, 
        timestamp: float
    ) -> DetectionBatch:
        """
        Detect VRUs in a single frame
        
        Args:
            frame: Video frame as numpy array
            frame_number: Frame sequence number
            timestamp: Frame timestamp in seconds
            
        Returns:
            DetectionBatch with all detections for the frame
        """
        start_time = time.time()
        
        try:
            # Preprocess frame
            processed_frame = await self.frame_processor.preprocess_frame(frame)
            
            # Run inference
            raw_detections = await self._run_inference(processed_frame)
            
            # Postprocess detections
            detections = self.frame_processor.postprocess_detections(
                raw_detections, frame.shape[:2], frame_number, timestamp
            )
            
            # Apply Non-Maximum Suppression
            filtered_detections = self.nms.apply(detections)
            
            # Calculate processing time
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Update statistics
            self._update_stats(1, len(filtered_detections), processing_time)
            
            # Check latency target
            if processing_time > DetectionConfig.MAX_PROCESSING_LATENCY_MS:
                logger.warning(f"Detection latency exceeded target: {processing_time:.1f}ms")
            
            return DetectionBatch(
                frame_number=frame_number,
                timestamp=timestamp,
                detections=filtered_detections,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            logger.error(f"Frame detection failed: {e}")
            return DetectionBatch(
                frame_number=frame_number,
                timestamp=timestamp,
                detections=[],
                processing_time_ms=(time.time() - start_time) * 1000
            )
    
    async def detect_video_stream(
        self, 
        frame_generator: AsyncGenerator[np.ndarray, None]
    ) -> AsyncGenerator[DetectionBatch, None]:
        """
        Process video stream and yield detection batches
        
        Args:
            frame_generator: Async generator yielding video frames
            
        Yields:
            DetectionBatch for each processed frame
        """
        frame_number = 0
        start_time = time.time()
        
        async for frame in frame_generator:
            frame_number += 1
            
            # Calculate timestamp
            timestamp = (frame_number - 1) / settings.FRAME_EXTRACTION_FPS
            
            # Detect VRUs in frame
            detection_batch = await self.detect_frame(frame, frame_number, timestamp)
            
            yield detection_batch
            
            # Adaptive processing rate control
            if frame_number % 30 == 0:  # Every second
                elapsed_time = time.time() - start_time
                current_fps = frame_number / elapsed_time
                
                # If processing is too slow, skip some frames
                if current_fps < DetectionConfig.TARGET_FPS * 0.8:
                    await asyncio.sleep(0.001)  # Small delay to prevent overwhelming
    
    async def _run_inference(self, frame: np.ndarray) -> List[Dict]:
        """Run model inference on preprocessed frame"""
        try:
            if self.model is None:
                raise VRUDetectionException("DETECTION_MODEL_NOT_LOADED", "Detection model not loaded")
            
            # Run inference
            if hasattr(self.model, 'predict'):
                # Ultralytics YOLO
                results = self.model.predict(
                    frame,
                    conf=settings.MIN_CONFIDENCE_THRESHOLD,
                    iou=settings.NMS_THRESHOLD,
                    verbose=False
                )
                return results
            else:
                # Mock model
                return self.model.predict(frame)
                
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return []
    
    async def _warmup_model(self) -> None:
        """Warm up the model with a dummy frame"""
        try:
            # Create dummy frame
            dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            # Run inference
            await self._run_inference(dummy_frame)
            
            logger.info("Model warmup completed")
            
        except Exception as e:
            logger.warning(f"Model warmup failed: {e}")
    
    def _update_stats(self, frames: int, detections: int, processing_time: float) -> None:
        """Update processing statistics"""
        self.processing_stats["total_frames"] += frames
        self.processing_stats["total_detections"] += detections
        self.processing_stats["total_processing_time"] += processing_time
        
        if self.processing_stats["total_processing_time"] > 0:
            self.processing_stats["average_fps"] = (
                self.processing_stats["total_frames"] * 1000 / 
                self.processing_stats["total_processing_time"]
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return self.processing_stats.copy()
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            # Clear model cache
            if self.model_manager:
                for model_name in list(self.model_manager.models.keys()):
                    self.model_manager.unload_model(model_name)
            
            # Clear GPU cache if available
            if TORCH_AVAILABLE and torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Detection engine cleanup completed")
            
        except Exception as e:
            logger.error(f"Detection engine cleanup failed: {e}")


# Utility functions
def validate_detection_confidence(detection: Detection) -> bool:
    """Validate detection meets confidence requirements"""
    min_confidence = DetectionConfig.CONFIDENCE_THRESHOLDS.get(
        detection.class_label,
        settings.MIN_CONFIDENCE_THRESHOLD
    )
    return detection.confidence >= min_confidence


def filter_detections_by_roi(detections: List[Detection], roi: BoundingBox) -> List[Detection]:
    """Filter detections to those within a region of interest"""
    filtered = []
    
    for detection in detections:
        # Check if detection center is within ROI
        center_x, center_y = detection.bounding_box.center()
        
        if (roi.x <= center_x <= roi.x + roi.width and 
            roi.y <= center_y <= roi.y + roi.height):
            filtered.append(detection)
    
    return filtered


def calculate_detection_density(detections: List[Detection], frame_area: float) -> float:
    """Calculate detection density (detections per unit area)"""
    if frame_area <= 0:
        return 0.0
    
    return len(detections) / frame_area