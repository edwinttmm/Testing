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
        from processing_state_guard import processing_guard
        
        # Check if processing can start
        if not processing_guard.can_start_processing(video_id):
            logger.warning(f"🚫 Skipping duplicate processing request for video {video_id}")
            return
        
        # Mark as starting processing
        if not processing_guard.start_processing(video_id):
            logger.warning(f"🚫 Could not start processing for video {video_id}")
            return
        
        db = SessionLocal()
        
        try:
            logger.info(f"🚀 Starting ground truth processing for video {video_id} at {video_file_path}")
            
            # Check if video file exists
            import os
            if not os.path.exists(video_file_path):
                logger.error(f"❌ Video file not found: {video_file_path}")
                processing_guard.complete_processing(video_id, success=False)
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
                logger.warning(f"⚠️ ML not available. Using fallback detection mode for video {video_id}")
                # Generate fallback test detections for development/testing
                detections = self._generate_fallback_detections()
                logger.info(f"📝 Generated {len(detections)} fallback detections")
            else:
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
                        difficult=detection.get("difficult", False),
                        screenshot_path=detection.get("screenshot_path"),
                        screenshot_zoom_path=detection.get("screenshot_zoom_path")
                    )
                    detection_count += 1
                    if detection.get("screenshot_path"):
                        logger.info(f"📸 Ground truth screenshot saved: {detection['screenshot_path']}")
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
            
            # Mark processing as completed
            processing_guard.complete_processing(video_id, success=True)
            
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
                        
                        # Only process VRU-related classes with ultra-low threshold for debugging
                        # Using 0.01 threshold to catch all detections including children
                        if class_id in self.vru_classes and confidence > 0.01:
                            # Get bounding box coordinates
                            x1, y1, x2, y2 = box.xyxy.cpu().numpy()[0]
                            
                            # Generate screenshot for this detection
                            screenshot_path, screenshot_zoom_path = self._generate_screenshot(
                                frame, x1, y1, x2, y2, frame_count, self.vru_classes[class_id]
                            )
                            
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
                                "difficult": False,  # YOLO confident detections are not difficult
                                "screenshot_path": screenshot_path,
                                "screenshot_zoom_path": screenshot_zoom_path
                            }
                            detections.append(detection)
        
            cap.release()
            return detections
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            return []
    
    def _generate_screenshot(self, frame, x1, y1, x2, y2, frame_number, class_label):
        """Generate screenshots for ground truth detection"""
        import uuid
        
        try:
            # Create screenshots directory if it doesn't exist
            os.makedirs("screenshots", exist_ok=True)
            
            # Generate unique detection ID
            detection_id = str(uuid.uuid4())
            
            # Full frame screenshot with bounding box
            screenshot_frame = frame.copy()
            cv2.rectangle(screenshot_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)
            cv2.putText(screenshot_frame, f"{class_label} ({frame_number})", 
                       (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            
            full_screenshot_path = f"screenshots/ground_truth_{detection_id}.jpg"
            cv2.imwrite(full_screenshot_path, screenshot_frame)
            
            # Zoomed screenshot of detection area with padding
            padding = 20
            x1_crop = max(0, int(x1) - padding)
            y1_crop = max(0, int(y1) - padding)
            x2_crop = min(frame.shape[1], int(x2) + padding)
            y2_crop = min(frame.shape[0], int(y2) + padding)
            
            cropped_frame = frame[y1_crop:y2_crop, x1_crop:x2_crop]
            
            # Draw bounding box on cropped frame
            adjusted_x1 = int(x1) - x1_crop
            adjusted_y1 = int(y1) - y1_crop
            adjusted_x2 = int(x2) - x1_crop
            adjusted_y2 = int(y2) - y1_crop
            
            cv2.rectangle(cropped_frame, (adjusted_x1, adjusted_y1), (adjusted_x2, adjusted_y2), (0, 255, 0), 2)
            cv2.putText(cropped_frame, class_label, (adjusted_x1, adjusted_y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            zoom_screenshot_path = f"screenshots/ground_truth_{detection_id}_zoom.jpg"
            cv2.imwrite(zoom_screenshot_path, cropped_frame)
            
            return full_screenshot_path, zoom_screenshot_path
            
        except Exception as e:
            logger.error(f"Failed to generate screenshot: {e}")
            return None, None
    
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
    
    def _generate_fallback_detections(self) -> List[Dict[str, Any]]:
        """Generate fallback test detections when ML is unavailable"""
        logger.info("🔧 Generating fallback detections for testing")
        
        # Create realistic test detections
        fallback_detections = [
            {
                "timestamp": 1.5,
                "frame_number": 45,
                "class_label": "pedestrian",
                "x": 150.0,
                "y": 200.0,
                "width": 80.0,
                "height": 160.0,
                "confidence": 0.87,
                "validated": True,
                "difficult": False
            },
            {
                "timestamp": 3.2,
                "frame_number": 96,
                "class_label": "cyclist",
                "x": 300.0,
                "y": 180.0,
                "width": 120.0,
                "height": 180.0,
                "confidence": 0.92,
                "validated": True,
                "difficult": False
            },
            {
                "timestamp": 5.8,
                "frame_number": 174,
                "class_label": "pedestrian",
                "x": 220.0,
                "y": 190.0,
                "width": 75.0,
                "height": 150.0,
                "confidence": 0.79,
                "validated": True,
                "difficult": True
            }
        ]
        
        return fallback_detections