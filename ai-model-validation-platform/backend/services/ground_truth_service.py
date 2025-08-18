import cv2
import numpy as np
from typing import List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import logging
from sqlalchemy.orm import Session

# Optional ML dependencies - make them optional for Docker environments without ML packages
try:
    from ultralytics import YOLO
    import torch
    ML_AVAILABLE = True
except ImportError as e:
    YOLO = None
    torch = None
    ML_AVAILABLE = False
    logging.warning(f"ML dependencies not available: {e}. Using fallback mode.")

logger = logging.getLogger(__name__)

from database import SessionLocal
from crud import create_ground_truth_object, update_video_status, get_video
from schemas import GroundTruthResponse, GroundTruthObject as GroundTruthObjectSchema

class GroundTruthService:
    def __init__(self):
        self.ml_available = ML_AVAILABLE
        self.model = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        if self.ml_available:
            try:
                # Configure torch to allow unsafe loading for YOLO models
                torch.serialization.add_safe_globals(['ultralytics.nn.tasks.DetectionModel'])
                
                # Load YOLOv8 model
                self.model = YOLO('yolov8n.pt')  # Using nano version for speed
                logger.info("YOLO model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load YOLO model: {e}. Using fallback mode.")
                self.ml_available = False
        else:
            logger.warning("ML dependencies not available. Using fallback mode.")
        
        # Class mapping for VRU detection
        self.vru_classes = {
            0: 'person',  # pedestrian
            1: 'bicycle',  # cyclist
            2: 'car',
            3: 'motorcycle',
            5: 'bus',
            7: 'truck'
        }
        
        # Driver behavior classes (would need custom trained model)
        self.driver_behavior_classes = {
            0: 'normal_driving',
            1: 'distracted_phone',
            2: 'distracted_other',
            3: 'drowsy',
            4: 'aggressive'
        }
    
    async def process_video_async(self, video_id: str, video_file_path: str):
        """Process video asynchronously to generate ground truth"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, self._process_video, video_id, video_file_path)
    
    def _process_video(self, video_id: str, video_file_path: str):
        """Process video synchronously using YOLO for ground truth generation"""
        db = SessionLocal()
        
        try:
            # Update video status to processing
            update_video_status(db, video_id, "processing")
            
            if not self.ml_available:
                logger.warning(f"ML not available. Skipping ground truth generation for video {video_id}")
                # Update video status to indicate ML is not available
                update_video_status(db, video_id, "ml_unavailable")
                return
            
            # Process video with YOLO  
            detections = self._extract_detections(video_file_path)
            
            # Store ground truth objects in database
            for detection in detections:
                create_ground_truth_object(
                    db=db,
                    video_id=video_id,
                    timestamp=detection["timestamp"],
                    class_label=detection["class_label"],
                    bounding_box=detection["bounding_box"],
                    confidence=detection["confidence"]
                )
            
            # Update video status and mark ground truth as generated
            video = get_video(db, video_id)
            if video:
                video.status = "completed"
                video.ground_truth_generated = True
                db.commit()
            
        except Exception as e:
            print(f"Error processing video {video_id}: {str(e)}")
            update_video_status(db, video_id, "failed")
        finally:
            db.close()
    
    def _extract_detections(self, video_path: str) -> List[Dict[str, Any]]:
        """Extract detections from video using YOLO"""
        if not self.ml_available or not self.model:
            logger.warning("ML not available. Returning empty detections.")
            return []
        
        detections = []
        
        try:
            # Open video
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
            
                frame_count += 1

                # Process every 5th frame for efficiency
                if frame_count % 5 != 0:
                    continue

                # Calculate timestamp in seconds
                timestamp = (frame_count - 1) / fps
                
                # Run YOLO inference
                results = self.model(frame, verbose=False)
                
                # Extract boxes from results
                boxes = results[0].boxes if results and len(results) > 0 else None

                # Process detections
                if boxes is not None:
                    for box in boxes:
                        # Get class ID and confidence
                        class_id = int(box.cls.cpu().numpy()[0])
                        confidence = float(box.conf.cpu().numpy()[0])
                        
                        # Only process VRU-related classes with high confidence
                        if class_id in self.vru_classes and confidence > 0.5:
                            # Get bounding box coordinates
                            x1, y1, x2, y2 = box.xyxy.cpu().numpy()[0]
                            
                            detection = {
                                "timestamp": timestamp,
                                "class_label": self.vru_classes[class_id],
                                "bounding_box": {
                                    "x": float(x1),
                                    "y": float(y1),
                                    "width": float(x2 - x1),
                                    "height": float(y2 - y1)
                                },
                                "confidence": confidence
                            }
                            detections.append(detection)
        
            cap.release()
            return detections
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            return []
    
    def get_ground_truth(self, video_id: str) -> GroundTruthResponse:
        """Get ground truth data for a video"""
        db = SessionLocal()
        try:
            from crud import get_ground_truth_objects
            
            objects = get_ground_truth_objects(db, video_id)
            
            ground_truth_objects = [
                GroundTruthObjectSchema(
                    id=obj.id,
                    timestamp=obj.timestamp,
                    class_label=obj.class_label,
                    bounding_box=obj.bounding_box,
                    confidence=obj.confidence
                )
                for obj in objects
            ]
            
            return GroundTruthResponse(
                video_id=video_id,
                objects=ground_truth_objects,
                total_detections=len(ground_truth_objects),
                status="completed"
            )
            
        finally:
            db.close()