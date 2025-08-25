import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import cv2
import json

try:
    from ultralytics import YOLO
    import torch
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logging.warning("ML dependencies not available. Pre-annotation will use mock data.")

from models import Annotation, Video
from schemas_video_annotation import AnnotationCreate, BoundingBox, VRUTypeEnum
from services.video_annotation_service import VideoAnnotationService

logger = logging.getLogger(__name__)

class PreAnnotationService:
    """Service for AI-powered pre-annotation of videos using ML models"""
    
    def __init__(self):
        self.annotation_service = VideoAnnotationService()
        self.processing_status = {}  # In-memory status tracking
        self.models_cache = {}  # Cache loaded models
        
        # Class mapping for YOLO models
        self.yolo_class_map = {
            0: 'pedestrian',  # person
            1: 'cyclist',     # bicycle
            2: 'cyclist',     # car -> cyclist for VRU focus
            3: 'motorcyclist', # motorcycle
            # Add more mappings as needed
        }
        
        # VRU type mapping
        self.vru_type_map = {
            'person': VRUTypeEnum.PEDESTRIAN,
            'pedestrian': VRUTypeEnum.PEDESTRIAN,
            'cyclist': VRUTypeEnum.CYCLIST,
            'bicycle': VRUTypeEnum.CYCLIST,
            'motorcyclist': VRUTypeEnum.MOTORCYCLIST,
            'motorcycle': VRUTypeEnum.MOTORCYCLIST,
            'scooter': VRUTypeEnum.SCOOTER,
            'wheelchair': VRUTypeEnum.WHEELCHAIR,
            'animal': VRUTypeEnum.ANIMAL,
            'other': VRUTypeEnum.OTHER
        }
    
    async def process_video(
        self, 
        video_id: str, 
        video_path: str, 
        model_name: str = "yolov8n",
        confidence_threshold: float = 0.5,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process video for pre-annotation using ML model"""
        if not task_id:
            task_id = str(uuid.uuid4())
        
        # Initialize processing status
        self.processing_status[task_id] = {
            "video_id": video_id,
            "task_id": task_id,
            "status": "processing",
            "progress_percentage": 0,
            "processed_frames": 0,
            "total_frames": 0,
            "detections_found": 0,
            "processing_time": None,
            "error_message": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            logger.info(f"Starting pre-annotation for video {video_id} with model {model_name}")
            
            if ML_AVAILABLE:
                result = await self._process_video_with_ml(
                    video_id, video_path, model_name, confidence_threshold, task_id
                )
            else:
                result = await self._process_video_mock(
                    video_id, video_path, model_name, confidence_threshold, task_id
                )
            
            # Update final status
            self.processing_status[task_id].update({
                "status": "completed",
                "progress_percentage": 100,
                "processing_time": result.get("processing_time"),
                "updated_at": datetime.utcnow()
            })
            
            logger.info(f"Completed pre-annotation for video {video_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error in pre-annotation for video {video_id}: {str(e)}")
            
            # Update error status
            self.processing_status[task_id].update({
                "status": "failed",
                "error_message": str(e),
                "updated_at": datetime.utcnow()
            })
            
            raise
    
    async def _process_video_with_ml(
        self, 
        video_id: str, 
        video_path: str, 
        model_name: str,
        confidence_threshold: float,
        task_id: str
    ) -> Dict[str, Any]:
        """Process video using actual ML models"""
        start_time = datetime.utcnow()
        
        # Load model
        model = await self._load_model(model_name)
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        
        self.processing_status[task_id]["total_frames"] = total_frames
        
        annotations_created = []
        frame_number = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            timestamp = frame_number / fps if fps > 0 else frame_number
            
            # Run inference
            results = model(frame, conf=confidence_threshold)
            
            # Process detections
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Extract detection data
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = float(box.conf[0].cpu().numpy())
                        class_id = int(box.cls[0].cpu().numpy())
                        
                        # Map to VRU type
                        class_name = self.yolo_class_map.get(class_id, 'other')
                        vru_type = self.vru_type_map.get(class_name, VRUTypeEnum.OTHER)
                        
                        # Create bounding box
                        bbox = BoundingBox(
                            x=float(x1),
                            y=float(y1),
                            width=float(x2 - x1),
                            height=float(y2 - y1),
                            confidence=confidence
                        )
                        
                        # Create annotation
                        annotation_data = AnnotationCreate(
                            video_id=video_id,  # CRITICAL: Include video_id field
                            frame_number=frame_number,
                            timestamp=timestamp,
                            vru_type=vru_type,
                            bounding_box=bbox,
                            annotator=f"ai_model_{model_name}",
                            validated=False  # AI annotations need human validation
                        )
                        
                        annotations_created.append(annotation_data)
                        
                        self.processing_status[task_id]["detections_found"] += 1
            
            frame_number += 1
            
            # Update progress
            progress = (frame_number / total_frames) * 100
            self.processing_status[task_id].update({
                "progress_percentage": progress,
                "processed_frames": frame_number,
                "updated_at": datetime.utcnow()
            })
            
            # Yield control periodically
            if frame_number % 30 == 0:
                await asyncio.sleep(0.01)
        
        cap.release()
        
        # Save annotations to database if any were found
        if annotations_created:
            from database import SessionLocal
            db = SessionLocal()
            try:
                saved_annotations = await self.annotation_service.create_bulk_annotations(
                    db, video_id, annotations_created
                )
                db.close()
                logger.info(f"Saved {len(saved_annotations)} pre-annotations for video {video_id}")
            except Exception as e:
                db.close()
                logger.error(f"Error saving pre-annotations: {str(e)}")
                raise
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "video_id": video_id,
            "task_id": task_id,
            "total_detections": len(annotations_created),
            "processing_time": processing_time,
            "model_used": model_name,
            "confidence_distribution": self._calculate_confidence_distribution(annotations_created),
            "class_distribution": self._calculate_class_distribution(annotations_created),
            "frame_coverage": (len(set(ann.frame_number for ann in annotations_created)) / total_frames * 100) if total_frames > 0 else 0,
            "annotations_created": len(annotations_created),
            "created_at": datetime.utcnow()
        }
    
    async def _process_video_mock(
        self, 
        video_id: str, 
        video_path: str, 
        model_name: str,
        confidence_threshold: float,
        task_id: str
    ) -> Dict[str, Any]:
        """Process video using mock data when ML is not available"""
        start_time = datetime.utcnow()
        
        # Get video info
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        
        self.processing_status[task_id]["total_frames"] = total_frames
        
        # Generate mock annotations
        annotations_created = []
        
        # Simulate processing frames
        for frame_number in range(0, total_frames, 30):  # Every 30th frame
            timestamp = frame_number / fps if fps > 0 else frame_number
            
            # Create mock detection
            bbox = BoundingBox(
                x=100.0 + (frame_number % 500),
                y=100.0 + (frame_number % 300),
                width=80.0,
                height=120.0,
                confidence=0.7 + (frame_number % 30) / 100
            )
            
            annotation_data = AnnotationCreate(
                video_id=video_id,  # CRITICAL: Include video_id field
                frame_number=frame_number,
                timestamp=timestamp,
                vru_type=VRUTypeEnum.PEDESTRIAN,
                bounding_box=bbox,
                annotator=f"mock_model_{model_name}",
                validated=False
            )
            
            annotations_created.append(annotation_data)
            
            # Update progress
            progress = (frame_number / total_frames) * 100
            self.processing_status[task_id].update({
                "progress_percentage": progress,
                "processed_frames": frame_number,
                "detections_found": len(annotations_created),
                "updated_at": datetime.utcnow()
            })
            
            await asyncio.sleep(0.01)  # Simulate processing time
        
        # Save mock annotations
        if annotations_created:
            from database import SessionLocal
            db = SessionLocal()
            try:
                saved_annotations = await self.annotation_service.create_bulk_annotations(
                    db, video_id, annotations_created
                )
                db.close()
                logger.info(f"Saved {len(saved_annotations)} mock pre-annotations for video {video_id}")
            except Exception as e:
                db.close()
                logger.error(f"Error saving mock pre-annotations: {str(e)}")
                raise
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        return {
            "video_id": video_id,
            "task_id": task_id,
            "total_detections": len(annotations_created),
            "processing_time": processing_time,
            "model_used": f"mock_{model_name}",
            "confidence_distribution": self._calculate_confidence_distribution(annotations_created),
            "class_distribution": self._calculate_class_distribution(annotations_created),
            "frame_coverage": 100.0,  # Mock full coverage
            "annotations_created": len(annotations_created),
            "created_at": datetime.utcnow()
        }
    
    async def _load_model(self, model_name: str):
        """Load and cache ML model"""
        if model_name in self.models_cache:
            return self.models_cache[model_name]
        
        try:
            # Load YOLO model
            model = YOLO(f"{model_name}.pt")
            self.models_cache[model_name] = model
            logger.info(f"Loaded model {model_name}")
            return model
        except Exception as e:
            logger.error(f"Error loading model {model_name}: {str(e)}")
            raise
    
    def _calculate_confidence_distribution(self, annotations: List[AnnotationCreate]) -> Dict[str, int]:
        """Calculate confidence distribution for annotations"""
        distribution = {"high": 0, "medium": 0, "low": 0}
        
        for ann in annotations:
            confidence = ann.bounding_box.confidence or 0.5
            if confidence >= 0.8:
                distribution["high"] += 1
            elif confidence >= 0.5:
                distribution["medium"] += 1
            else:
                distribution["low"] += 1
        
        return distribution
    
    def _calculate_class_distribution(self, annotations: List[AnnotationCreate]) -> Dict[str, int]:
        """Calculate class distribution for annotations"""
        distribution = {}
        
        for ann in annotations:
            vru_type = ann.vru_type.value
            distribution[vru_type] = distribution.get(vru_type, 0) + 1
        
        return distribution
    
    async def get_processing_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get processing status for a video"""
        # Find status by video_id
        for task_id, status in self.processing_status.items():
            if status["video_id"] == video_id:
                return status
        
        return None
    
    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get processing status for a specific task"""
        return self.processing_status.get(task_id)
    
    def clear_completed_tasks(self, max_age_hours: int = 24):
        """Clear old completed tasks from memory"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        tasks_to_remove = []
        for task_id, status in self.processing_status.items():
            if (status["status"] in ["completed", "failed"] and 
                status["updated_at"] < cutoff_time):
                tasks_to_remove.append(task_id)
        
        for task_id in tasks_to_remove:
            del self.processing_status[task_id]
        
        logger.info(f"Cleared {len(tasks_to_remove)} old task statuses")
    
    async def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available pre-annotation models"""
        models = [
            {
                "name": "yolov8n",
                "description": "YOLOv8 Nano - Fast inference",
                "type": "object_detection",
                "supported_classes": list(self.vru_type_map.keys()),
                "recommended_confidence": 0.5
            },
            {
                "name": "yolov8s",
                "description": "YOLOv8 Small - Balanced speed/accuracy",
                "type": "object_detection",
                "supported_classes": list(self.vru_type_map.keys()),
                "recommended_confidence": 0.5
            },
            {
                "name": "yolov8m",
                "description": "YOLOv8 Medium - High accuracy",
                "type": "object_detection",
                "supported_classes": list(self.vru_type_map.keys()),
                "recommended_confidence": 0.6
            }
        ]
        
        return models
