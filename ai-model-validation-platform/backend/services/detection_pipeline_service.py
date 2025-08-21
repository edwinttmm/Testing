from typing import List, Dict, Optional, AsyncGenerator, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import numpy as np
import cv2
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
import time
import logging
from pathlib import Path
import uuid
from sqlalchemy.orm import Session
from database import SessionLocal
from models import DetectionEvent, TestSession, Video
import json

logger = logging.getLogger(__name__)

class VRUClass(Enum):
    PEDESTRIAN = "pedestrian"
    CYCLIST = "cyclist"
    MOTORCYCLIST = "motorcyclist"
    WHEELCHAIR_USER = "wheelchair_user"
    SCOOTER_RIDER = "scooter_rider"
    CHILD_WITH_STROLLER = "child_with_stroller"

@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float
    
    def to_dict(self) -> Dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }

@dataclass
class Detection:
    class_label: str
    confidence: float
    bounding_box: BoundingBox
    timestamp: float
    frame_number: int
    detection_id: Optional[str] = None

@dataclass
class DetectionResult:
    detections: List[Detection]
    frame_number: int
    timestamp: float
    processing_time_ms: float

# VRU Detection Configuration
VRU_DETECTION_CONFIG = {
    "pedestrian": {
        "min_confidence": 0.35,  # Lowered from 0.70 to detect more pedestrians including children
        "nms_threshold": 0.45,
        "class_id": 0
    },
    "cyclist": {
        "min_confidence": 0.75,
        "nms_threshold": 0.40,
        "class_id": 1
    },
    "motorcyclist": {
        "min_confidence": 0.80,
        "nms_threshold": 0.35,
        "class_id": 2
    },
    "wheelchair_user": {
        "min_confidence": 0.65,
        "nms_threshold": 0.50,
        "class_id": 3
    },
    "scooter_rider": {
        "min_confidence": 0.70,
        "nms_threshold": 0.45,
        "class_id": 4
    }
}

class ModelRegistry:
    """Registry for managing multiple ML models"""
    
    def __init__(self):
        self.models = {}
        self.active_model_id = None
        self.model_cache = {}
    
    def register_model(self, model_id: str, model_path: str, model_type: str = "yolov8"):
        """Register a new model"""
        self.models[model_id] = {
            "path": model_path,
            "type": model_type,
            "loaded": False,
            "metadata": {}
        }
        logger.info(f"Registered model {model_id}: {model_path}")
    
    async def load_model(self, model_id: str):
        """Load model into memory"""
        if model_id not in self.models:
            raise ValueError(f"Model {model_id} not registered")
        
        if model_id in self.model_cache:
            return self.model_cache[model_id]
        
        model_info = self.models[model_id]
        
        # Load based on model type
        if model_info["type"] == "yolov8":
            try:
                # Try to load real YOLOv8 first
                try:
                    from ultralytics import YOLO
                    import torch
                    
                    # Check if model file exists
                    from pathlib import Path
                    model_path = Path(model_info["path"])
                    
                    if not model_path.exists():
                        logger.info(f"Model file not found at {model_path}, downloading default model...")
                        # Download default YOLOv8 model
                        model = YOLO('yolov8n.pt')  # This will auto-download if needed
                        # Save to expected location
                        model_path.parent.mkdir(parents=True, exist_ok=True)
                        # Note: YOLO handles model downloading automatically
                    else:
                        model = YOLO(str(model_path))
                    
                    # Validate model works
                    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                    model.to(device)
                    
                    # Test with dummy input
                    test_input = torch.randn(1, 3, 640, 640).to(device)
                    with torch.no_grad():
                        _ = model.model(test_input)
                    
                    logger.info(f"✅ Loaded real YOLOv8 model: {model_id} on {device}")
                    self.model_cache[model_id] = RealYOLOv8Wrapper(model)
                    self.models[model_id]["loaded"] = True
                    return self.model_cache[model_id]
                    
                except ImportError as e:
                    logger.error(f"❌ ML dependencies not available: {e}")
                    raise RuntimeError(f"ML dependencies required: {e}. Please install: pip install torch ultralytics")
                except Exception as e:
                    logger.error(f"❌ Failed to load real YOLOv8 model: {str(e)}")
                    raise RuntimeError(f"Model loading failed: {e}")
                    
            except RuntimeError:
                # Re-raise runtime errors (dependency issues)
                raise
            except Exception as e:
                logger.error(f"Unexpected error loading model {model_id}: {str(e)}")
                raise ValueError(f"Model loading failed: {e}")
        else:
            raise ValueError(f"Unsupported model type: {model_info['type']}")
    
    async def get_active_model(self):
        """Get the currently active model"""
        if not self.active_model_id:
            # Use default model if available
            if "yolov8n" in self.models:
                self.active_model_id = "yolov8n"
            else:
                raise ValueError("No active model set")
        
        return await self.load_model(self.active_model_id)
    
    def set_active_model(self, model_id: str):
        """Set the active model for detection"""
        if model_id not in self.models:
            raise ValueError(f"Model {model_id} not registered")
        self.active_model_id = model_id
        logger.info(f"Set active model to: {model_id}")

class RealYOLOv8Wrapper:
    """Wrapper for real YOLOv8 model to match interface"""
    
    def __init__(self, yolo_model):
        self.model = yolo_model
        self.class_names = list(VRU_DETECTION_CONFIG.keys())
        # Map YOLO class IDs to VRU classes (COCO dataset class IDs)
        self.yolo_to_vru_mapping = {
            0: 'pedestrian',    # person - COCO class 0 is critical for pedestrian detection
            1: 'cyclist',       # bicycle  
            3: 'motorcyclist',  # motorcycle (COCO class 3, not 2!)
            # Note: COCO class 2 is 'car' which we skip for VRU detection
            # Could add vehicle classes if needed for context
        }
        logger.info(f"YOLOv8 initialized with VRU mapping: {self.yolo_to_vru_mapping}")
    
    async def predict(self, frame: np.ndarray) -> List[Detection]:
        """Real prediction using YOLOv8"""
        try:
            # Run inference with enhanced settings for better pedestrian detection
            results = self.model(frame, verbose=False, conf=0.1)  # Lower inference confidence to catch more detections
            
            detections = []
            
            for r in results:
                boxes = r.boxes
                if boxes is not None:
                    for box in boxes:
                        # Extract box data
                        xyxy = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        cls = int(box.cls[0].cpu().numpy())
                        
                        # Convert to our bounding box format
                        x1, y1, x2, y2 = xyxy
                        width = x2 - x1
                        height = y2 - y1
                        
                        # Map YOLO class to VRU class
                        if cls in self.yolo_to_vru_mapping:
                            class_label = self.yolo_to_vru_mapping[cls]
                            logger.debug(f"Found {class_label} (COCO class {cls}) with confidence {conf:.3f}")
                        else:
                            logger.debug(f"Skipping non-VRU object: COCO class {cls} with confidence {conf:.3f}")
                            continue  # Skip non-VRU objects
                        
                        # Filter by confidence threshold with debugging
                        min_confidence = VRU_DETECTION_CONFIG.get(class_label, {}).get("min_confidence", 0.5)
                        if conf < min_confidence:
                            logger.debug(f"Filtered detection: {class_label} confidence {conf:.3f} < threshold {min_confidence}")
                            continue
                        else:
                            logger.debug(f"Valid detection: {class_label} confidence {conf:.3f} >= threshold {min_confidence}")
                        
                        detection = Detection(
                            class_label=class_label,
                            confidence=float(conf),
                            bounding_box=BoundingBox(x=float(x1), y=float(y1), width=float(width), height=float(height)),
                            timestamp=time.time(),
                            frame_number=0,  # Will be set by caller
                            detection_id=str(uuid.uuid4())
                        )
                        
                        detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Real YOLOv8 prediction failed: {str(e)}")
            raise
    
    async def predict_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """Batch prediction for multiple frames"""
        results = []
        for frame in frames:
            detections = await self.predict(frame)
            results.append(detections)
        return results

class MockYOLOv8Model:
    """Mock YOLOv8 model for testing without ML dependencies"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.class_names = list(VRU_DETECTION_CONFIG.keys())
    
    async def predict(self, frame: np.ndarray) -> List[Detection]:
        """Mock prediction that returns random detections"""
        # Simulate processing time
        await asyncio.sleep(0.01)  # 10ms processing time
        
        detections = []
        
        # Generate 0-3 random detections per frame
        num_detections = np.random.randint(0, 4)
        
        for i in range(num_detections):
            class_label = np.random.choice(self.class_names)
            confidence = np.random.uniform(0.5, 0.95)
            
            # Random bounding box within frame
            height, width = frame.shape[:2]
            x = np.random.uniform(0, width * 0.8)
            y = np.random.uniform(0, height * 0.8)
            w = np.random.uniform(width * 0.1, width * 0.3)
            h = np.random.uniform(height * 0.1, height * 0.3)
            
            detection = Detection(
                class_label=class_label,
                confidence=confidence,
                bounding_box=BoundingBox(x=x, y=y, width=w, height=h),
                timestamp=time.time(),
                frame_number=0,  # Will be set by caller
                detection_id=str(uuid.uuid4())
            )
            
            detections.append(detection)
        
        return detections
    
    async def predict_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        """Batch prediction for multiple frames"""
        results = []
        for frame in frames:
            detections = await self.predict(frame)
            results.append(detections)
        return results

class FrameProcessor:
    """Video frame preprocessing for ML inference"""
    
    def __init__(self, target_size: Tuple[int, int] = (640, 640)):
        self.target_size = target_size
    
    async def preprocess(self, frame: np.ndarray) -> np.ndarray:
        """Preprocess frame for model inference"""
        try:
            # Resize frame to target size
            resized = cv2.resize(frame, self.target_size)
            
            # Normalize pixel values
            normalized = resized.astype(np.float32) / 255.0
            
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(normalized, cv2.COLOR_BGR2RGB)
            
            return rgb_frame
            
        except Exception as e:
            logger.error(f"Error preprocessing frame: {str(e)}")
            raise
    
    async def preprocess_batch(self, frames: List[np.ndarray]) -> np.ndarray:
        """Batch preprocessing for multiple frames"""
        processed_frames = []
        
        for frame in frames:
            processed = await self.preprocess(frame)
            processed_frames.append(processed)
        
        # Stack into batch tensor
        return np.stack(processed_frames, axis=0)

class TimestampSynchronizer:
    """Precise timestamp synchronization for detection events"""
    
    def __init__(self):
        self.reference_clock = time.time()
        self.video_start_time = None
        self.frame_timestamps = {}
    
    def initialize_video_timeline(self, video_id: str, fps: float):
        """Initialize timeline for a video"""
        self.video_start_time = time.time()
        self.frame_timestamps[video_id] = {
            "start_time": self.video_start_time,
            "fps": fps,
            "frame_duration": 1.0 / fps
        }
    
    async def sync_frame_timestamp(self, video_id: str, frame_number: int, system_time: float) -> float:
        """Synchronize frame timestamp with system clock"""
        if video_id not in self.frame_timestamps:
            raise ValueError(f"Video timeline not initialized for {video_id}")
        
        timeline = self.frame_timestamps[video_id]
        
        # Calculate video timestamp
        video_timestamp = timeline["start_time"] + (frame_number * timeline["frame_duration"])
        
        # Apply drift correction
        drift = system_time - video_timestamp
        corrected_timestamp = video_timestamp + (drift * 0.1)  # 10% drift correction
        
        return corrected_timestamp
    
    def apply_drift_correction(self, video_timestamp: float, system_time: float) -> float:
        """Apply drift correction between video and system time"""
        drift = system_time - video_timestamp
        
        # Apply exponential smoothing for drift correction
        alpha = 0.1  # Smoothing factor
        corrected_timestamp = video_timestamp + (alpha * drift)
        
        return corrected_timestamp

class ScreenshotCapture:
    """Detection moment capture and annotation"""
    
    def __init__(self, screenshot_dir: str = "/app/screenshots"):
        self.screenshot_dir = Path(screenshot_dir)
        # Create parent directories if they don't exist
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
    
    async def capture_detection(self, frame: np.ndarray, bounding_box: BoundingBox, 
                              detection_id: str) -> str:
        """Capture and annotate detection screenshot"""
        try:
            # Create annotated frame
            annotated_frame = self._annotate_frame(frame, bounding_box)
            
            # Save screenshot
            screenshot_path = self.screenshot_dir / f"detection_{detection_id}.jpg"
            cv2.imwrite(str(screenshot_path), annotated_frame)
            
            logger.debug(f"Captured detection screenshot: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            logger.error(f"Error capturing screenshot: {str(e)}")
            return None
    
    def _annotate_frame(self, frame: np.ndarray, bounding_box: BoundingBox) -> np.ndarray:
        """Annotate frame with bounding box"""
        annotated = frame.copy()
        
        # Draw bounding box
        x, y, w, h = int(bounding_box.x), int(bounding_box.y), int(bounding_box.width), int(bounding_box.height)
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        return annotated
    
    async def capture_zoomed_region(self, frame: np.ndarray, bounding_box: BoundingBox, 
                                   detection_id: str) -> str:
        """Capture zoomed region of detection"""
        try:
            # Extract region of interest
            x, y, w, h = int(bounding_box.x), int(bounding_box.y), int(bounding_box.width), int(bounding_box.height)
            
            # Add padding
            padding = 20
            x_start = max(0, x - padding)
            y_start = max(0, y - padding)
            x_end = min(frame.shape[1], x + w + padding)
            y_end = min(frame.shape[0], y + h + padding)
            
            roi = frame[y_start:y_end, x_start:x_end]
            
            # Resize for better visibility
            zoomed = cv2.resize(roi, (200, 200))
            
            # Save zoomed region
            zoom_path = self.screenshot_dir / f"detection_{detection_id}_zoom.jpg"
            cv2.imwrite(str(zoom_path), zoomed)
            
            return str(zoom_path)
            
        except Exception as e:
            logger.error(f"Error capturing zoomed region: {str(e)}")
            return None

class DetectionPipeline:
    """Complete detection pipeline orchestrating all components"""
    
    def __init__(self):
        self.model_registry = ModelRegistry()
        self.frame_processor = FrameProcessor()
        self.timestamp_sync = TimestampSynchronizer()
        self.screenshot_capture = ScreenshotCapture()
        self.initialized = False
        
        # Performance settings
        self.batch_size = 8
        self.max_queue_size = 30
        self.processing_queue = asyncio.Queue(maxsize=self.max_queue_size)
    
    async def initialize(self):
        """Initialize pipeline with default models"""
        if self.initialized:
            return
        
        try:
            # Register default YOLOv8 model
            self.model_registry.register_model(
                "yolov8n",
                "/app/models/yolov8n.pt",
                "yolov8"
            )
            self.model_registry.set_active_model("yolov8n")
            
            self.initialized = True
            logger.info("Detection pipeline initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize detection pipeline: {str(e)}")
            raise
    
    async def process_video_stream(self, video_id: str, test_session_id: str) -> AsyncGenerator[DetectionEvent, None]:
        """Process video stream and yield detection events"""
        if not self.initialized:
            await self.initialize()
        
        db = SessionLocal()
        try:
            # Get video and test session info
            video = db.query(Video).filter(Video.id == video_id).first()
            test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
            
            if not video or not test_session:
                raise ValueError("Video or test session not found")
            
            # Initialize video timeline
            cap = cv2.VideoCapture(video.file_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            self.timestamp_sync.initialize_video_timeline(video_id, fps)
            
            frame_number = 0
            model = await self.model_registry.get_active_model()
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_number += 1
                start_time = time.time()
                
                # Preprocess frame
                processed_frame = await self.frame_processor.preprocess(frame)
                
                # Run detection
                detections = await model.predict(processed_frame)
                
                # Process each detection
                for detection in detections:
                    detection.frame_number = frame_number
                    
                    # Synchronize timestamp
                    synchronized_timestamp = await self.timestamp_sync.sync_frame_timestamp(
                        video_id, frame_number, detection.timestamp
                    )
                    
                    # Capture screenshot if confidence is high enough
                    screenshot_path = None
                    if detection.confidence > 0.8:
                        screenshot_path = await self.screenshot_capture.capture_detection(
                            frame, detection.bounding_box, detection.detection_id
                        )
                    
                    # Create detection event
                    detection_event = DetectionEvent(
                        id=detection.detection_id,
                        test_session_id=test_session_id,
                        timestamp=synchronized_timestamp,
                        confidence=detection.confidence,
                        class_label=detection.class_label,
                        validation_result="PENDING"  # Will be set by validation service
                    )
                    
                    # Store in database
                    db.add(detection_event)
                    
                    yield detection_event
                
                # Commit batch of detections
                if frame_number % 30 == 0:  # Commit every 30 frames
                    db.commit()
            
            cap.release()
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing video stream: {str(e)}")
            raise
        finally:
            db.close()
    
    async def process_frame_batch(self, frames: List[np.ndarray]) -> List[DetectionResult]:
        """Process multiple frames in batch for better performance"""
        if not self.initialized:
            await self.initialize()
        
        try:
            start_time = time.time()
            
            # Batch preprocessing
            processed_batch = await self.frame_processor.preprocess_batch(frames)
            
            # Batch inference
            model = await self.model_registry.get_active_model()
            batch_detections = await model.predict_batch(processed_batch)
            
            # Build results
            results = []
            for i, detections in enumerate(batch_detections):
                processing_time = (time.time() - start_time) * 1000 / len(frames)
                
                result = DetectionResult(
                    detections=detections,
                    frame_number=i,
                    timestamp=time.time(),
                    processing_time_ms=processing_time
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing frame batch: {str(e)}")
            raise
    
    def validate_detections(self, detections: List[Detection]) -> List[Detection]:
        """Post-process and validate detections"""
        validated = []
        
        for detection in detections:
            config = VRU_DETECTION_CONFIG.get(detection.class_label, {})
            min_confidence = config.get("min_confidence", 0.5)
            
            # Filter by confidence threshold
            if detection.confidence >= min_confidence:
                validated.append(detection)
        
        # Apply Non-Maximum Suppression if multiple detections overlap
        validated = self._apply_nms(validated)
        
        return validated
    
    def _apply_nms(self, detections: List[Detection]) -> List[Detection]:
        """Apply Non-Maximum Suppression to remove overlapping detections"""
        if not detections:
            return detections
        
        # Group by class
        class_groups = {}
        for detection in detections:
            if detection.class_label not in class_groups:
                class_groups[detection.class_label] = []
            class_groups[detection.class_label].append(detection)
        
        # Apply NMS per class
        final_detections = []
        for class_label, class_detections in class_groups.items():
            config = VRU_DETECTION_CONFIG.get(class_label, {})
            nms_threshold = config.get("nms_threshold", 0.5)
            
            # Simple NMS implementation
            nms_detections = self._simple_nms(class_detections, nms_threshold)
            final_detections.extend(nms_detections)
        
        return final_detections
    
    def _simple_nms(self, detections: List[Detection], threshold: float) -> List[Detection]:
        """Simple Non-Maximum Suppression implementation"""
        if not detections:
            return detections
        
        # Sort by confidence
        detections.sort(key=lambda x: x.confidence, reverse=True)
        
        keep = []
        for i, detection in enumerate(detections):
            should_keep = True
            
            for kept_detection in keep:
                # Calculate IoU
                iou = self._calculate_iou(detection.bounding_box, kept_detection.bounding_box)
                if iou > threshold:
                    should_keep = False
                    break
            
            if should_keep:
                keep.append(detection)
        
        return keep
    
    def _calculate_iou(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """Calculate Intersection over Union of two bounding boxes"""
        # Calculate intersection
        x1 = max(box1.x, box2.x)
        y1 = max(box1.y, box2.y)
        x2 = min(box1.x + box1.width, box2.x + box2.width)
        y2 = min(box1.y + box1.height, box2.y + box2.height)
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        
        # Calculate union
        area1 = box1.width * box1.height
        area2 = box2.width * box2.height
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def _enhance_pedestrian_detection(self, detections: List[Detection]) -> List[Detection]:
        """Apply pedestrian-specific detection enhancements"""
        enhanced_detections = []
        
        for detection in detections:
            if detection.class_label == 'pedestrian':
                # Apply pedestrian-specific confidence boosting for certain size ranges
                bbox = detection.bounding_box
                aspect_ratio = bbox.height / bbox.width if bbox.width > 0 else 0
                
                # Children tend to have different aspect ratios and sizes
                # Boost confidence for smaller pedestrians (children)
                area = bbox.width * bbox.height
                if area < 50000:  # Smaller bounding boxes (likely children)
                    confidence_boost = 0.05
                    detection.confidence = min(0.99, detection.confidence + confidence_boost)
                    logger.debug(f"Applied child pedestrian confidence boost: {detection.confidence:.3f}")
                
                # Boost confidence for typical pedestrian aspect ratios
                if 1.5 <= aspect_ratio <= 4.0:  # Typical human aspect ratio
                    confidence_boost = 0.03
                    detection.confidence = min(0.99, detection.confidence + confidence_boost)
                    logger.debug(f"Applied aspect ratio confidence boost: {detection.confidence:.3f}")
            
            enhanced_detections.append(detection)
        
        return enhanced_detections

    async def process_video(self, video_path: str, config: dict = None) -> List[Dict]:
        """Process video file and return detections for API endpoint"""
        if not self.initialized:
            await self.initialize()
        
        try:
            logger.info(f"🎬 Starting video processing: {video_path}")
            
            # Apply configuration if provided
            if config and 'confidence_threshold' in config:
                # Update pedestrian confidence threshold from config
                original_threshold = VRU_DETECTION_CONFIG["pedestrian"]["min_confidence"]
                VRU_DETECTION_CONFIG["pedestrian"]["min_confidence"] = config['confidence_threshold']
                logger.info(f"Updated pedestrian confidence threshold: {original_threshold} → {config['confidence_threshold']}")
            
            # Verify video file exists
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Open video with OpenCV
            cap = cv2.VideoCapture(str(video_file))
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {video_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"📊 Video properties: {total_frames} frames, {fps:.2f} fps, {duration:.2f}s")
            
            # Initialize timeline
            video_id = str(uuid.uuid4())
            self.timestamp_sync.initialize_video_timeline(video_id, fps)
            
            # Get active model
            model = await self.model_registry.get_active_model()
            
            all_detections = []
            frame_number = 0
            
            # Process video frame by frame
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.info(f"✅ Completed processing {frame_number} frames")
                    break
                
                frame_number += 1
                
                # Process every frame for better detection accuracy (especially for pedestrians)
                # Comment out frame skipping to catch all pedestrians
                # if frame_number % 5 != 0:
                #     continue
                
                try:
                    # Preprocess frame
                    processed_frame = await self.frame_processor.preprocess(frame)
                    
                    # Run detection
                    detections = await model.predict(processed_frame)
                    
                    # Apply pedestrian-specific enhancements
                    detections = self._enhance_pedestrian_detection(detections)
                    
                    # Process each detection
                    for detection in detections:
                        detection.frame_number = frame_number
                        detection.timestamp = frame_number / fps
                        
                        # Convert to API response format
                        detection_dict = {
                            "id": detection.detection_id or str(uuid.uuid4()),
                            "frame_number": detection.frame_number,
                            "timestamp": detection.timestamp,
                            "class_label": detection.class_label,
                            "confidence": detection.confidence,
                            "bounding_box": detection.bounding_box.to_dict(),
                            "vru_type": detection.class_label,  # Map class_label to vru_type
                        }
                        
                        all_detections.append(detection_dict)
                        
                        if len(all_detections) % 50 == 0:
                            logger.info(f"🔍 Processed {len(all_detections)} detections so far...")
                
                except Exception as e:
                    logger.warning(f"⚠️ Error processing frame {frame_number}: {str(e)}")
                    continue
            
            cap.release()
            
            # Apply validation and filtering
            validated_detections = self._validate_api_detections(all_detections)
            
            logger.info(f"🎯 Completed processing: {len(validated_detections)} valid detections from {frame_number} frames")
            
            # Log detection summary by class
            detection_summary = {}
            for detection in validated_detections:
                class_label = detection.get("class_label", "unknown")
                detection_summary[class_label] = detection_summary.get(class_label, 0) + 1
            
            logger.info(f"📊 Detection summary: {detection_summary}")
            if not validated_detections:
                logger.warning("⚠️ NO VALID DETECTIONS FOUND! Check video content and detection thresholds.")
            
            return validated_detections
            
        except Exception as e:
            logger.error(f"❌ Error processing video {video_path}: {str(e)}")
            raise RuntimeError(f"Video processing failed: {str(e)}")
    
    def _validate_api_detections(self, detections: List[Dict]) -> List[Dict]:
        """Validate detections for API response"""
        validated = []
        filtered_count = {"low_confidence": 0, "invalid_format": 0}
        
        for detection in detections:
            try:
                # Check confidence threshold
                class_label = detection.get("class_label", "")
                confidence = detection.get("confidence", 0.0)
                
                config = VRU_DETECTION_CONFIG.get(class_label, {})
                min_confidence = config.get("min_confidence", 0.5)
                
                if confidence >= min_confidence:
                    # Ensure all required fields are present
                    validated_detection = {
                        "id": detection.get("id", str(uuid.uuid4())),
                        "frame_number": detection.get("frame_number", 0),
                        "timestamp": detection.get("timestamp", 0.0),
                        "class_label": detection.get("class_label", "pedestrian"),
                        "confidence": float(confidence),
                        "bounding_box": detection.get("bounding_box", {}),
                        "vru_type": detection.get("vru_type", detection.get("class_label", "pedestrian")),
                    }
                    validated.append(validated_detection)
                else:
                    filtered_count["low_confidence"] += 1
                    logger.debug(f"Filtered {class_label}: confidence {confidence:.3f} < {min_confidence}")
                    
            except Exception as e:
                filtered_count["invalid_format"] += 1
                logger.warning(f"⚠️ Skipping invalid detection: {str(e)}")
                continue
        
        # Log filtering summary
        if filtered_count["low_confidence"] > 0:
            logger.info(f"🔍 Filtered {filtered_count['low_confidence']} detections due to low confidence")
        if filtered_count["invalid_format"] > 0:
            logger.warning(f"⚠️ Filtered {filtered_count['invalid_format']} detections due to invalid format")
        
        return validated

# Performance optimization classes
class BatchProcessor:
    """Optimized batch processing for multiple frames"""
    
    def __init__(self, batch_size: int = 8):
        self.batch_size = batch_size
    
    async def process_in_batches(self, items: List[Any], processor_func) -> List[Any]:
        """Process items in batches"""
        results = []
        
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            batch_results = await processor_func(batch)
            results.extend(batch_results)
        
        return results

class MemoryPool:
    """Memory pool for efficient frame processing"""
    
    def __init__(self, initial_size: int, max_size: int):
        self.initial_size = initial_size
        self.max_size = max_size
        self.available_buffers = []
        self.current_size = 0
    
    def allocate(self, size: int) -> np.ndarray:
        """Allocate buffer from pool"""
        if self.available_buffers:
            return self.available_buffers.pop()
        
        if self.current_size + size <= self.max_size:
            buffer = np.zeros((size,), dtype=np.uint8)
            self.current_size += size
            return buffer
        
        raise MemoryError("Memory pool exhausted")
    
    def deallocate(self, buffer: np.ndarray):
        """Return buffer to pool"""
        self.available_buffers.append(buffer)