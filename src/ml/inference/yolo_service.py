"""
YOLOv8 Inference Service for VRU Detection

Optimized for <50ms inference latency with GPU acceleration
"""
import asyncio
import time
import logging
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import numpy as np
import cv2
import torch
from ultralytics import YOLO
from ultralytics.engine.results import Results

from ..config import ml_config
from ..utils.image_utils import preprocess_frame, postprocess_detections
from ..monitoring.performance_monitor import PerformanceMonitor

logger = logging.getLogger(__name__)

class Detection:
    """VRU Detection Result"""
    def __init__(self, bbox: List[float], confidence: float, class_id: int, class_name: str, track_id: Optional[int] = None):
        self.bbox = bbox  # [x1, y1, x2, y2]
        self.confidence = confidence
        self.class_id = class_id
        self.class_name = class_name
        self.track_id = track_id
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict:
        return {
            "bbox": self.bbox,
            "confidence": self.confidence,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "track_id": self.track_id,
            "timestamp": self.timestamp
        }

class YOLODetectionService:
    """High-performance YOLOv8 service optimized for VRU detection"""
    
    def __init__(self):
        self.model: Optional[YOLO] = None
        self.device = ml_config.get_device()
        self.is_initialized = False
        self.performance_monitor = PerformanceMonitor()
        self._inference_lock = asyncio.Semaphore(ml_config.max_concurrent_requests)
        
        # Performance tracking
        self.inference_times = []
        self.total_inferences = 0
        
    async def initialize(self) -> bool:
        """Initialize the YOLO model with optimizations"""
        try:
            start_time = time.time()
            
            # Load model
            model_path = Path(ml_config.model_path)
            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False
            
            logger.info(f"Loading YOLOv8 model from {model_path}")
            self.model = YOLO(str(model_path))
            
            # Configure device
            logger.info(f"Using device: {self.device}")
            if self.device == "cuda":
                # Enable CUDA optimizations
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
                
                # Set GPU memory fraction if specified
                if ml_config.gpu_memory_limit:
                    torch.cuda.set_per_process_memory_fraction(
                        ml_config.gpu_memory_limit / torch.cuda.get_device_properties(0).total_memory
                    )
            
            # Move model to device
            self.model.to(self.device)
            
            # Warm up model with dummy inference
            await self._warmup()
            
            initialization_time = time.time() - start_time
            logger.info(f"YOLOv8 model initialized in {initialization_time:.2f}s on {self.device}")
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize YOLO model: {str(e)}", exc_info=True)
            return False
    
    async def _warmup(self) -> None:
        """Warm up the model with dummy inference"""
        try:
            dummy_image = np.random.randint(0, 255, (*ml_config.input_size, 3), dtype=np.uint8)
            
            # Run a few dummy inferences to warm up GPU
            for _ in range(3):
                await self._run_inference(dummy_image)
            
            logger.info("Model warmup completed")
            
        except Exception as e:
            logger.warning(f"Model warmup failed: {str(e)}")
    
    async def detect_vru(self, frame: np.ndarray, return_annotated: bool = False) -> Tuple[List[Detection], Optional[np.ndarray]]:
        """
        Detect VRUs in a single frame
        
        Args:
            frame: Input frame as numpy array (BGR format)
            return_annotated: Whether to return annotated frame
            
        Returns:
            Tuple of (detections, annotated_frame)
        """
        if not self.is_initialized:
            raise RuntimeError("YOLODetectionService not initialized")
        
        async with self._inference_lock:
            start_time = time.time()
            
            try:
                # Preprocess frame
                processed_frame = preprocess_frame(frame, ml_config.input_size)
                
                # Run inference
                results = await self._run_inference(processed_frame)
                
                # Extract VRU detections
                detections = self._extract_vru_detections(results, frame.shape)
                
                # Generate annotated frame if requested
                annotated_frame = None
                if return_annotated and detections:
                    annotated_frame = self._annotate_frame(frame.copy(), detections)
                
                # Track performance
                inference_time = (time.time() - start_time) * 1000  # Convert to ms
                self.inference_times.append(inference_time)
                self.total_inferences += 1
                
                # Log performance warning if too slow
                if inference_time > ml_config.max_inference_time_ms:
                    logger.warning(f"Inference time {inference_time:.1f}ms exceeds target {ml_config.max_inference_time_ms}ms")
                
                # Update performance monitor
                if ml_config.enable_performance_monitoring:
                    await self.performance_monitor.record_inference(inference_time, len(detections))
                
                return detections, annotated_frame
                
            except Exception as e:
                logger.error(f"Detection failed: {str(e)}", exc_info=True)
                return [], None
    
    async def detect_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """
        Detect VRUs in a batch of frames for improved efficiency
        
        Args:
            frames: List of input frames
            
        Returns:
            List of detection lists for each frame
        """
        if not self.is_initialized:
            raise RuntimeError("YOLODetectionService not initialized")
        
        if len(frames) > ml_config.batch_size:
            # Process in chunks
            results = []
            for i in range(0, len(frames), ml_config.batch_size):
                batch = frames[i:i + ml_config.batch_size]
                batch_results = await self._process_batch(batch)
                results.extend(batch_results)
            return results
        else:
            return await self._process_batch(frames)
    
    async def _process_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """Process a batch of frames"""
        try:
            # Preprocess all frames
            processed_frames = [preprocess_frame(frame, ml_config.input_size) for frame in frames]
            
            # Stack for batch inference
            batch_tensor = np.stack(processed_frames)
            
            # Run batch inference
            results = await self._run_batch_inference(batch_tensor)
            
            # Extract detections for each frame
            all_detections = []
            for i, (result, original_frame) in enumerate(zip(results, frames)):
                detections = self._extract_vru_detections([result], original_frame.shape)
                all_detections.append(detections)
            
            return all_detections
            
        except Exception as e:
            logger.error(f"Batch detection failed: {str(e)}", exc_info=True)
            return [[] for _ in frames]
    
    async def _run_inference(self, frame: np.ndarray) -> List[Results]:
        """Run YOLO inference on a single frame"""
        loop = asyncio.get_event_loop()
        
        # Run in thread pool to avoid blocking
        result = await loop.run_in_executor(
            None,
            lambda: self.model(
                frame,
                conf=ml_config.confidence_threshold,
                iou=ml_config.iou_threshold,
                verbose=False,
                device=self.device
            )
        )
        
        return result
    
    async def _run_batch_inference(self, batch: np.ndarray) -> List[Results]:
        """Run YOLO inference on a batch of frames"""
        loop = asyncio.get_event_loop()
        
        result = await loop.run_in_executor(
            None,
            lambda: self.model(
                batch,
                conf=ml_config.confidence_threshold,
                iou=ml_config.iou_threshold,
                verbose=False,
                device=self.device
            )
        )
        
        return result
    
    def _extract_vru_detections(self, results: List[Results], original_shape: Tuple[int, int, int]) -> List[Detection]:
        """Extract VRU detections from YOLO results"""
        detections = []
        
        for result in results:
            if result.boxes is None:
                continue
                
            boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)
            
            for box, conf, class_id in zip(boxes, confidences, class_ids):
                # Only include VRU classes
                if ml_config.is_vru_class(class_id):
                    # Scale bounding box to original image dimensions
                    h, w = original_shape[:2]
                    input_h, input_w = ml_config.input_size
                    
                    x1, y1, x2, y2 = box
                    x1 = (x1 / input_w) * w
                    y1 = (y1 / input_h) * h
                    x2 = (x2 / input_w) * w
                    y2 = (y2 / input_h) * h
                    
                    detection = Detection(
                        bbox=[float(x1), float(y1), float(x2), float(y2)],
                        confidence=float(conf),
                        class_id=int(class_id),
                        class_name=ml_config.vru_classes[class_id]
                    )
                    detections.append(detection)
        
        return detections
    
    def _annotate_frame(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Annotate frame with detection bounding boxes"""
        for detection in detections:
            x1, y1, x2, y2 = map(int, detection.bbox)
            
            # Choose color based on class
            color_map = {
                "person": (0, 255, 0),      # Green for pedestrians
                "bicycle": (255, 0, 0),     # Blue for cyclists
                "motorcycle": (0, 0, 255)   # Red for motorcyclists
            }
            color = color_map.get(detection.class_name, (255, 255, 255))
            
            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, ml_config.annotation_thickness)
            
            # Draw label
            label = f"{detection.class_name}: {detection.confidence:.2f}"
            if detection.track_id is not None:
                label += f" ID:{detection.track_id}"
            
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
            cv2.rectangle(frame, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        if not self.inference_times:
            return {
                "total_inferences": 0,
                "average_inference_time_ms": 0,
                "min_inference_time_ms": 0,
                "max_inference_time_ms": 0,
                "target_latency_met": True
            }
        
        avg_time = np.mean(self.inference_times[-100:])  # Last 100 inferences
        min_time = np.min(self.inference_times[-100:])
        max_time = np.max(self.inference_times[-100:])
        
        return {
            "total_inferences": self.total_inferences,
            "average_inference_time_ms": round(avg_time, 2),
            "min_inference_time_ms": round(min_time, 2),
            "max_inference_time_ms": round(max_time, 2),
            "target_latency_met": avg_time <= ml_config.max_inference_time_ms,
            "device": self.device
        }
    
    async def shutdown(self) -> None:
        """Cleanup resources"""
        if self.model:
            del self.model
            if self.device == "cuda":
                torch.cuda.empty_cache()
        
        self.is_initialized = False
        logger.info("YOLODetectionService shut down")

# Global service instance
yolo_service = YOLODetectionService()