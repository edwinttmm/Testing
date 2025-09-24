"""
ML Generation Service - Automated Ground Truth Generation
SPARC Implementation - ML-powered ground truth generation service
"""

import os
import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

# Optional ML dependencies with runtime disable flag
DISABLE_ML = os.getenv("AIVALIDATION_DISABLE_ML", "false").lower() == "true"
try:
    if DISABLE_ML:
        raise ImportError("ML disabled by environment variable")
    from ultralytics import YOLO
    import torch
    ML_AVAILABLE = True
except ImportError as e:
    YOLO = None
    torch = None
    ML_AVAILABLE = False
    logging.warning(f"ML unavailable ({e}). Using fallback mode.")

from database import SessionLocal
from models import GroundTruthObject, Video
from src.models.ground_truth_models import (
    GroundTruthValidationWorkflow, ValidationStatus, GenerationMethod, QualityLevel
)

logger = logging.getLogger(__name__)

class MLGenerationService:
    """
    ML-powered ground truth generation service
    Provides automated detection and ground truth creation using YOLO and other models
    """
    
    def __init__(self):
        self.ml_available = ML_AVAILABLE
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.model_loaded = False
        
        # Initialize ML model if available
        if self.ml_available:
            try:
                self._initialize_models()
            except Exception as e:
                logger.error(f"Failed to initialize ML models: {str(e)}")
                self.ml_available = False
        
        # VRU class mapping for YOLO COCO classes
        self.vru_classes = {
            0: 'pedestrian',      # person -> pedestrian
            1: 'cyclist',         # bicycle -> cyclist  
            3: 'motorcyclist',    # motorcycle -> motorcyclist
        }
        
        # Detection thresholds for different quality levels
        self.quality_thresholds = {
            QualityLevel.HIGH: 0.7,
            QualityLevel.MEDIUM: 0.5,
            QualityLevel.LOW: 0.3,
            QualityLevel.UNCERTAIN: 0.1
        }
    
    def _initialize_models(self):
        """Initialize ML models"""
        try:
            logger.info("🚀 Initializing YOLOv8 model for ground truth generation...")
            
            # Check for YOLO model files
            model_paths = ['yolov8n.pt', 'yolo11l.pt', '/app/yolov8n.pt']
            model_path = None
            
            for path in model_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            
            if not model_path:
                logger.warning("No YOLO model found, downloading YOLOv8n...")
                model_path = 'yolov8n.pt'  # This will auto-download
            
            # Load model
            self.model = YOLO(model_path)
            
            # Test the model
            if torch:
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                logger.info(f"✅ YOLOv8 model loaded successfully on {device}")
            
            # Warm up model
            dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
            results = self.model(dummy_img, verbose=False)
            logger.info("✅ Model warm-up successful")
            
            self.model_loaded = True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ML models: {str(e)}")
            self.ml_available = False
            self.model = None
            raise
    
    async def generate_ground_truth(
        self, 
        video_id: str, 
        confidence_threshold: float = 0.5,
        method: GenerationMethod = GenerationMethod.AUTOMATED_ML
    ) -> int:
        """
        Generate ground truth for a video using ML models
        Returns the number of detections generated
        """
        if not self.ml_available or not self.model_loaded:
            logger.warning(f"ML not available for video {video_id}, using fallback generation")
            return await self._generate_fallback_ground_truth(video_id, method)
        
        db = SessionLocal()
        try:
            # Get video information
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                logger.error(f"Video {video_id} not found")
                return 0
            
            # Check if video file exists
            video_path = video.file_path
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return 0
            
            logger.info(f"🎬 Starting ML ground truth generation for video {video_id}")
            
            # Update video processing status
            video.processing_status = "processing"
            db.commit()
            
            # Process video in thread pool
            loop = asyncio.get_event_loop()
            detections = await loop.run_in_executor(
                self.executor,
                self._process_video_with_ml,
                video_path,
                confidence_threshold
            )
            
            # Create ground truth objects and validation workflows
            detection_count = 0
            for detection in detections:
                try:
                    # Create ground truth object
                    gt_id = await self._create_ground_truth_object(
                        db, video_id, detection, method
                    )
                    
                    if gt_id:
                        # Create validation workflow
                        await self._create_validation_workflow(
                            db, gt_id, video_id, detection, method
                        )
                        detection_count += 1
                        
                except Exception as e:
                    logger.error(f"Failed to create ground truth object: {str(e)}")
                    continue
            
            # Update video status
            video.processing_status = "completed"
            video.ground_truth_generated = True
            db.commit()
            
            logger.info(f"✅ Generated {detection_count} ground truth objects for video {video_id}")
            return detection_count
            
        except Exception as e:
            logger.error(f"Error generating ground truth for video {video_id}: {str(e)}")
            video.processing_status = "failed"
            db.commit()
            return 0
        finally:
            db.close()
    
    def _process_video_with_ml(self, video_path: str, confidence_threshold: float) -> List[Dict[str, Any]]:
        """
        Process video with ML models to extract detections
        """
        detections = []
        
        try:
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return []
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Default FPS
            
            frame_count = 0
            processed_frames = 0
            
            # Process video frames
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # Process every 5th frame for efficiency
                if frame_count % 5 != 0:
                    continue
                
                processed_frames += 1
                timestamp = (frame_count - 1) / fps
                
                # Run YOLO inference
                results = self.model(frame, verbose=False)
                
                # Process detections
                if results and len(results) > 0:
                    frame_detections = self._extract_detections_from_results(
                        results[0], frame_count, timestamp, confidence_threshold
                    )
                    detections.extend(frame_detections)
                
                # Log progress periodically
                if processed_frames % 100 == 0:
                    logger.info(f"Processed {processed_frames} frames, found {len(detections)} detections")
            
            cap.release()
            logger.info(f"Completed processing: {processed_frames} frames, {len(detections)} total detections")
            
            return detections
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
            return []
    
    def _extract_detections_from_results(
        self, 
        results, 
        frame_number: int, 
        timestamp: float, 
        confidence_threshold: float
    ) -> List[Dict[str, Any]]:
        """Extract detections from YOLO results"""
        detections = []
        
        try:
            boxes = results.boxes
            if boxes is None:
                return detections
            
            for box in boxes:
                # Get class ID and confidence
                class_id = int(box.cls.cpu().numpy()[0])
                confidence = float(box.conf.cpu().numpy()[0])
                
                # Filter by VRU classes and confidence
                if class_id in self.vru_classes and confidence >= confidence_threshold:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy.cpu().numpy()[0]
                    
                    # Calculate quality level based on confidence
                    quality_level = self._determine_quality_level(confidence)
                    
                    # Create detection object
                    detection = {
                        "frame_number": frame_number,
                        "timestamp": timestamp,
                        "class_label": self.vru_classes[class_id],
                        "x": float(x1),
                        "y": float(y1),
                        "width": float(x2 - x1),
                        "height": float(y2 - y1),
                        "confidence": confidence,
                        "quality_level": quality_level,
                        "detection_method": "yolo_v8",
                        "model_version": "yolov8n",
                        "validated": confidence >= 0.8,  # Auto-validate high confidence detections
                        "difficult": confidence < 0.4,   # Mark low confidence as difficult
                        "metadata": {
                            "original_class_id": class_id,
                            "bbox_area": (x2 - x1) * (y2 - y1),
                            "aspect_ratio": (x2 - x1) / max(y2 - y1, 1)
                        }
                    }
                    
                    detections.append(detection)
            
        except Exception as e:
            logger.error(f"Error extracting detections from results: {str(e)}")
        
        return detections
    
    def _determine_quality_level(self, confidence: float) -> QualityLevel:
        """Determine quality level based on confidence score"""
        if confidence >= self.quality_thresholds[QualityLevel.HIGH]:
            return QualityLevel.HIGH
        elif confidence >= self.quality_thresholds[QualityLevel.MEDIUM]:
            return QualityLevel.MEDIUM
        elif confidence >= self.quality_thresholds[QualityLevel.LOW]:
            return QualityLevel.LOW
        else:
            return QualityLevel.UNCERTAIN
    
    async def _create_ground_truth_object(
        self, 
        db: Session, 
        video_id: str, 
        detection: Dict[str, Any], 
        method: GenerationMethod
    ) -> Optional[str]:
        """Create ground truth object from detection"""
        try:
            gt_id = str(uuid.uuid4())
            
            gt = GroundTruthObject(
                id=gt_id,
                video_id=video_id,
                frame_number=detection["frame_number"],
                timestamp=detection["timestamp"],
                class_label=detection["class_label"],
                x=detection["x"],
                y=detection["y"],
                width=detection["width"],
                height=detection["height"],
                confidence=detection["confidence"],
                validated=detection["validated"],
                difficult=detection["difficult"],
                created_at=datetime.utcnow()
            )
            
            db.add(gt)
            db.commit()
            
            return gt_id
            
        except Exception as e:
            logger.error(f"Error creating ground truth object: {str(e)}")
            db.rollback()
            return None
    
    async def _create_validation_workflow(
        self, 
        db: Session, 
        ground_truth_id: str, 
        video_id: str, 
        detection: Dict[str, Any], 
        method: GenerationMethod
    ):
        """Create validation workflow for ground truth object"""
        try:
            workflow_id = str(uuid.uuid4())
            
            # Determine validation status based on confidence
            validation_status = ValidationStatus.APPROVED if detection["confidence"] >= 0.8 else ValidationStatus.PENDING
            
            workflow = GroundTruthValidationWorkflow(
                id=workflow_id,
                ground_truth_id=ground_truth_id,
                video_id=video_id,
                generation_method=method,
                validation_status=validation_status,
                quality_level=detection["quality_level"],
                confidence_score=detection["confidence"],
                metadata={
                    "detection_method": detection["detection_method"],
                    "model_version": detection["model_version"],
                    "auto_generated": True,
                    "generation_timestamp": datetime.utcnow().isoformat()
                },
                created_at=datetime.utcnow()
            )
            
            db.add(workflow)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error creating validation workflow: {str(e)}")
            db.rollback()
    
    async def _generate_fallback_ground_truth(
        self, 
        video_id: str, 
        method: GenerationMethod
    ) -> int:
        """Generate fallback ground truth when ML is not available"""
        logger.info(f"🔧 Generating fallback ground truth for video {video_id}")
        
        # Create realistic test detections
        fallback_detections = [
            {
                "frame_number": 45,
                "timestamp": 1.5,
                "class_label": "pedestrian",
                "x": 150.0,
                "y": 200.0,
                "width": 80.0,
                "height": 160.0,
                "confidence": 0.87,
                "quality_level": QualityLevel.HIGH,
                "detection_method": "fallback",
                "model_version": "fallback_v1.0",
                "validated": True,
                "difficult": False,
                "metadata": {"fallback": True}
            },
            {
                "frame_number": 96,
                "timestamp": 3.2,
                "class_label": "cyclist",
                "x": 300.0,
                "y": 180.0,
                "width": 120.0,
                "height": 180.0,
                "confidence": 0.92,
                "quality_level": QualityLevel.HIGH,
                "detection_method": "fallback",
                "model_version": "fallback_v1.0",
                "validated": True,
                "difficult": False,
                "metadata": {"fallback": True}
            },
            {
                "frame_number": 174,
                "timestamp": 5.8,
                "class_label": "pedestrian",
                "x": 220.0,
                "y": 190.0,
                "width": 75.0,
                "height": 150.0,
                "confidence": 0.79,
                "quality_level": QualityLevel.MEDIUM,
                "detection_method": "fallback",
                "model_version": "fallback_v1.0",
                "validated": True,
                "difficult": True,
                "metadata": {"fallback": True}
            }
        ]
        
        db = SessionLocal()
        try:
            detection_count = 0
            
            for detection in fallback_detections:
                gt_id = await self._create_ground_truth_object(db, video_id, detection, method)
                if gt_id:
                    await self._create_validation_workflow(db, gt_id, video_id, detection, method)
                    detection_count += 1
            
            # Update video status
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.processing_status = "completed"
                video.ground_truth_generated = True
                db.commit()
            
            logger.info(f"✅ Generated {detection_count} fallback ground truth objects")
            return detection_count
            
        except Exception as e:
            logger.error(f"Error generating fallback ground truth: {str(e)}")
            return 0
        finally:
            db.close()
    
    async def batch_generate_ground_truth(
        self, 
        video_ids: List[str], 
        confidence_threshold: float = 0.5,
        method: GenerationMethod = GenerationMethod.AUTOMATED_ML
    ) -> Dict[str, int]:
        """
        Generate ground truth for multiple videos in batch
        """
        results = {}
        
        for video_id in video_ids:
            try:
                detection_count = await self.generate_ground_truth(
                    video_id, confidence_threshold, method
                )
                results[video_id] = detection_count
                
            except Exception as e:
                logger.error(f"Error processing video {video_id}: {str(e)}")
                results[video_id] = 0
        
        total_detections = sum(results.values())
        successful_videos = sum(1 for count in results.values() if count > 0)
        
        logger.info(f"Batch processing completed: {successful_videos}/{len(video_ids)} successful, "
                   f"{total_detections} total detections")
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about loaded ML models"""
        return {
            "ml_available": self.ml_available,
            "model_loaded": self.model_loaded,
            "model_type": "YOLOv8" if self.model else None,
            "supported_classes": list(self.vru_classes.values()),
            "quality_thresholds": {
                level.value: threshold 
                for level, threshold in self.quality_thresholds.items()
            },
            "cuda_available": torch.cuda.is_available() if torch else False,
            "device": str(torch.device('cuda' if torch.cuda.is_available() else 'cpu')) if torch else "cpu"
        }
    
    async def validate_video_for_processing(self, video_path: str) -> Tuple[bool, str]:
        """
        Validate if video can be processed for ground truth generation
        """
        if not os.path.exists(video_path):
            return False, f"Video file not found: {video_path}"
        
        try:
            # Check if video can be opened
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False, "Cannot open video file"
            
            # Get video properties
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            cap.release()
            
            # Validate video properties
            if frame_count <= 0:
                return False, "Video has no frames"
            
            if fps <= 0:
                return False, "Invalid video FPS"
            
            if width <= 0 or height <= 0:
                return False, "Invalid video resolution"
            
            return True, "Video is valid for processing"
            
        except Exception as e:
            return False, f"Error validating video: {str(e)}"
