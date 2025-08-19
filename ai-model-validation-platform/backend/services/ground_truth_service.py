import os
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "0"  # Disable OpenEXR support
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
                # Load YOLOv8 model with proper configuration
                logger.info("🚀 Loading YOLOv8 model for ground truth generation...")
                self.model = YOLO('yolov8n.pt')  # Using nano version for speed
                
                # Test the model with a dummy input to ensure it works
                import torch
                device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                logger.info(f"✅ YOLOv8 model loaded successfully on {device}")
                
                # Test inference
                dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
                _ = self.model(dummy_img, verbose=False)
                logger.info("✅ YOLOv8 model inference test successful")
                
            except Exception as e:
                logger.error(f"❌ Failed to load YOLOv8 model: {e}")
                logger.warning("🔧 Falling back to disabled mode - install ML dependencies to enable ground truth generation")
                self.ml_available = False
        else:
            logger.warning("❌ ML dependencies not available - ground truth generation disabled")
            logger.info("💡 To enable: pip install torch ultralytics")
        
        # Class mapping for VRU detection (YOLO COCO classes to VRU types)
        self.vru_classes = {
            0: 'pedestrian',      # person -> pedestrian
            1: 'cyclist',         # bicycle -> cyclist  
            3: 'motorcyclist',    # motorcycle -> motorcyclist
            # Note: wheelchair_user and scooter_rider would need custom training
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
            logger.info(f"🚀 Starting ground truth processing for video {video_id} at {video_file_path}")
            
            # Check if video file exists
            import os
            if not os.path.exists(video_file_path):
                logger.error(f"❌ Video file not found: {video_file_path}")
                update_video_status(db, video_id, "failed")
                return
            
            # Update video status to processing
            video = get_video(db, video_id)
            if video:
                video.status = "processing"
                video.processing_status = "processing"
                db.commit()
                logger.info(f"📝 Updated video {video_id} status to processing")
            
            if not self.ml_available:
                logger.error(f"❌ ML not available. Cannot process ground truth for video {video_id}")
                video = get_video(db, video_id)
                if video:
                    video.status = "failed"
                    video.processing_status = "failed"
                    db.commit()
                return
            
            # Process video with YOLO  
            logger.info(f"🔍 Extracting detections using YOLOv8...")
            detections = self._extract_detections(video_file_path)
            
            logger.info(f"✅ Extracted {len(detections)} detections from video {video_id}")
            
            if len(detections) == 0:
                logger.warning(f"⚠️  No VRU detections found in video {video_id}")
            
            # Store ground truth objects in database
            detection_count = 0
            for detection in detections:
                try:
                    create_ground_truth_object(
                        db=db,
                        video_id=video_id,
                        frame_number=detection.get("frame_number"),
                        timestamp=detection["timestamp"],
                        class_label=detection["class_label"],
                        x=detection["x"],
                        y=detection["y"],
                        width=detection["width"],
                        height=detection["height"],
                        confidence=detection["confidence"],
                        validated=detection.get("validated", True),
                        difficult=detection.get("difficult", False)
                    )
                    detection_count += 1
                except Exception as e:
                    logger.error(f"❌ Failed to store detection: {str(e)}")
                    continue
            
            logger.info(f"💾 Stored {detection_count} detections in database")
            
            # Update video status and mark ground truth as generated
            video = get_video(db, video_id)
            if video:
                video.status = "completed"
                video.processing_status = "completed"
                video.ground_truth_generated = True
                db.commit()
                logger.info(f"✅ Ground truth processing completed for video {video_id} with {detection_count} detections")
            
        except Exception as e:
            logger.error(f"💥 Error processing video {video_id}: {str(e)}")
            logger.exception("Full error details:")
            
            # Update video status to failed
            try:
                video = get_video(db, video_id)
                if video:
                    video.status = "failed"
                    video.processing_status = "failed"
                    db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update video status: {str(db_error)}")
                
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
                                "frame_number": frame_count,
                                "timestamp": timestamp,
                                "class_label": self.vru_classes[class_id],
                                "x": float(x1),
                                "y": float(y1),
                                "width": float(x2 - x1),
                                "height": float(y2 - y1),
                                "confidence": confidence,
                                "validated": True,  # Mark AI detections as validated ground truth
                                "difficult": False  # YOLO confident detections are not difficult
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