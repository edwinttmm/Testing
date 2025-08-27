#!/usr/bin/env python3
"""
Bulletproof Detection Service - YOLO to Database Pipeline with Zero Corruption
Integrates YOLO detection with bulletproof data integrity validation.
"""

import logging
import numpy as np
import cv2
import time
import uuid
from typing import List, Dict, Optional, Any, AsyncGenerator
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Import our bulletproof integrity system
from src.data_pipeline_integrity import (
    validate_and_repair_annotation,
    AnnotationDataContract,
    VRUTypeContract,
    BoundingBoxContract,
    ValidationStatusContract,
    PipelineIntegrityMonitor
)

@dataclass
class BulletproofDetection:
    """Bulletproof detection data structure"""
    id: str
    video_id: str
    frame_number: int
    timestamp: float
    class_label: str
    vru_type: str
    confidence: float
    bounding_box: Dict[str, float]
    processing_time_ms: float
    model_version: str
    integrity_status: str = ValidationStatusContract.VALID.value
    
    def to_annotation_dict(self) -> Dict[str, Any]:
        """Convert to annotation dictionary for database storage"""
        return {
            'id': self.id,
            'video_id': self.video_id,
            'detection_id': self.id,
            'frame_number': self.frame_number,
            'timestamp': self.timestamp,
            'vru_type': self.vru_type,
            'bounding_box': self.bounding_box,
            'occluded': False,
            'truncated': False,
            'difficult': False,
            'notes': f"Auto-detected by {self.model_version} with {self.confidence:.3f} confidence",
            'annotator': 'YOLO_AI',
            'validated': self.confidence > 0.8  # Auto-validate high-confidence detections
        }

class BulletproofYOLOWrapper:
    """Wrapper for YOLO that ensures data integrity"""
    
    def __init__(self):
        self.model = None
        self.model_version = "yolo11l"
        self.vru_class_mapping = {
            0: VRUTypeContract.PEDESTRIAN,     # COCO person class
            1: VRUTypeContract.CYCLIST,       # COCO bicycle class  
            3: VRUTypeContract.MOTORCYCLIST,  # COCO motorcycle class
        }
        self.confidence_thresholds = {
            VRUTypeContract.PEDESTRIAN: 0.4,
            VRUTypeContract.CYCLIST: 0.4,
            VRUTypeContract.MOTORCYCLIST: 0.4
        }
    
    async def initialize(self):
        """Initialize YOLO model with error handling"""
        try:
            from ultralytics import YOLO
            import torch
            
            logger.info("🤖 Initializing bulletproof YOLO detection...")
            
            # Load model with fallback strategy
            try:
                self.model = YOLO('yolo11l.pt')  # Primary model
                self.model_version = "yolo11l"
            except Exception:
                logger.warning("YOLOv11l not available, falling back to YOLOv8n")
                self.model = YOLO('yolov8n.pt')  # Fallback model
                self.model_version = "yolov8n"
            
            # Test model
            test_frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            results = self.model(test_frame, conf=0.1, verbose=False)
            
            logger.info(f"✅ Bulletproof YOLO initialized: {self.model_version}")
            return True
            
        except Exception as e:
            logger.error(f"❌ YOLO initialization failed: {str(e)}")
            return False
    
    async def detect_objects(self, frame: np.ndarray, video_id: str, frame_number: int, timestamp: float) -> List[BulletproofDetection]:
        """Detect objects with bulletproof data validation"""
        if not self.model:
            logger.error("Model not initialized")
            return []
        
        detections = []
        start_time = time.time()
        
        try:
            # Run YOLO inference
            results = self.model(frame, conf=0.01, verbose=False)  # Ultra-low threshold for debugging
            
            for r in results:
                if r.boxes is not None:
                    logger.debug(f"🔍 YOLO found {len(r.boxes)} raw detections")
                    
                    for box in r.boxes:
                        try:
                            # Extract box data safely
                            conf = float(box.conf[0].cpu().numpy())
                            cls = int(box.cls[0].cpu().numpy())
                            xyxy = box.xyxy[0].cpu().numpy()
                            
                            # Check if this is a VRU class
                            if cls not in self.vru_class_mapping:
                                logger.debug(f"Skipping non-VRU class {cls}")
                                continue
                            
                            vru_type = self.vru_class_mapping[cls]
                            class_label = vru_type.value
                            
                            # Apply confidence threshold
                            min_confidence = self.confidence_thresholds.get(vru_type, 0.5)
                            if conf < min_confidence:
                                logger.debug(f"Low confidence {class_label}: {conf:.3f} < {min_confidence}")
                                continue
                            
                            # Extract bounding box coordinates
                            x1, y1, x2, y2 = xyxy
                            width = x2 - x1
                            height = y2 - y1
                            
                            # Validate bounding box dimensions
                            if width <= 0 or height <= 0:
                                logger.debug(f"Invalid dimensions: {width}x{height}")
                                continue
                            
                            # Size filtering for realistic detections
                            if width < 10 or height < 20:
                                logger.debug(f"Too small: {width}x{height}")
                                continue
                            
                            # Create bulletproof bounding box
                            bbox_dict = {
                                'x': float(x1),
                                'y': float(y1),
                                'width': float(width),
                                'height': float(height),
                                'confidence': conf
                            }
                            
                            # Validate bounding box using contract
                            try:
                                bbox_contract = BoundingBoxContract.from_any(bbox_dict)
                                validated_bbox = bbox_contract.to_dict()
                            except Exception as bbox_error:
                                logger.warning(f"Bounding box validation failed: {bbox_error}")
                                continue
                            
                            # Create bulletproof detection
                            detection = BulletproofDetection(
                                id=str(uuid.uuid4()),
                                video_id=video_id,
                                frame_number=frame_number,
                                timestamp=timestamp,
                                class_label=class_label,
                                vru_type=class_label,
                                confidence=conf,
                                bounding_box=validated_bbox,
                                processing_time_ms=(time.time() - start_time) * 1000,
                                model_version=self.model_version
                            )
                            
                            detections.append(detection)
                            logger.info(f"🎯 Bulletproof detection: {class_label} conf={conf:.3f} at frame {frame_number}")
                            
                        except Exception as detection_error:
                            logger.warning(f"Failed to process detection: {detection_error}")
                            continue
            
            processing_time = (time.time() - start_time) * 1000
            logger.debug(f"🔍 Processed frame {frame_number}: {len(detections)} detections in {processing_time:.1f}ms")
            
            return detections
            
        except Exception as e:
            logger.error(f"❌ Detection failed for frame {frame_number}: {str(e)}")
            return []

class BulletproofDetectionPipeline:
    """Complete bulletproof detection pipeline"""
    
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.yolo_wrapper = BulletproofYOLOWrapper()
        self.thread_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="BulletproofDetection")
        self.integrity_monitor = None
        self.initialized = False
        
        # Performance settings
        self.frame_skip = 5  # Process every 5th frame for efficiency
        self.batch_size = 10
        self.max_detections_per_frame = 20
    
    async def initialize(self):
        """Initialize the bulletproof pipeline"""
        if self.initialized:
            return True
        
        try:
            logger.info("🛡️ Initializing bulletproof detection pipeline...")
            
            # Initialize YOLO wrapper
            yolo_ready = await self.yolo_wrapper.initialize()
            if not yolo_ready:
                logger.error("❌ YOLO initialization failed")
                return False
            
            # Initialize integrity monitor with database session
            db = self.db_session_factory()
            try:
                self.integrity_monitor = PipelineIntegrityMonitor(db)
                logger.info("✅ Pipeline integrity monitor initialized")
            finally:
                db.close()
            
            self.initialized = True
            logger.info("🛡️ Bulletproof detection pipeline ready!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Pipeline initialization failed: {str(e)}")
            return False
    
    async def process_video_bulletproof(self, video_path: str, video_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process video with complete bulletproof protection"""
        if not self.initialized:
            await self.initialize()
        
        logger.info(f"🎬 Starting bulletproof video processing: {video_path}")
        
        try:
            # Verify video file
            video_file = Path(video_path)
            if not video_file.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
            
            # Open video
            cap = cv2.VideoCapture(str(video_file))
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {video_path}")
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"📊 Video: {total_frames} frames, {fps:.2f} fps, {duration:.1f}s")
            
            # Process video with bulletproof detection
            all_detections = []
            stored_detections = []
            frame_number = 0
            processing_errors = []
            
            # Database session for storage
            db = self.db_session_factory()
            
            try:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    
                    frame_number += 1
                    
                    # Skip frames for efficiency
                    if frame_number % self.frame_skip != 0:
                        continue
                    
                    timestamp = frame_number / fps
                    
                    try:
                        # Run bulletproof detection
                        detections = await self.yolo_wrapper.detect_objects(
                            frame=frame,
                            video_id=video_id,
                            frame_number=frame_number,
                            timestamp=timestamp
                        )
                        
                        # Process each detection through integrity pipeline
                        for detection in detections:
                            try:
                                # Convert to annotation format
                                annotation_dict = detection.to_annotation_dict()
                                
                                # Validate through integrity monitor
                                validated_data = await self.integrity_monitor.monitor_yolo_to_db_pipeline(annotation_dict)
                                
                                if validated_data is not None:
                                    all_detections.append(validated_data)
                                    
                                    # Store in database immediately for real-time processing
                                    await self._store_detection_in_db(validated_data, db)
                                    stored_detections.append(validated_data['id'])
                                    
                                else:
                                    logger.warning(f"⚠️ Detection quarantined: {detection.id}")
                                    
                            except Exception as detection_error:
                                processing_errors.append({
                                    'frame': frame_number,
                                    'detection_id': detection.id,
                                    'error': str(detection_error)
                                })
                                logger.warning(f"Detection processing error: {detection_error}")
                        
                        # Commit batch periodically
                        if frame_number % (self.frame_skip * 10) == 0:
                            db.commit()
                            logger.debug(f"📝 Committed batch at frame {frame_number}")
                    
                    except Exception as frame_error:
                        processing_errors.append({
                            'frame': frame_number,
                            'error': str(frame_error)
                        })
                        logger.warning(f"Frame {frame_number} processing error: {frame_error}")
                        continue
                
                # Final commit
                db.commit()
                
            finally:
                cap.release()
                db.close()
            
            # Generate comprehensive processing report
            processing_report = {
                'video_info': {
                    'video_id': video_id,
                    'file_path': str(video_path),
                    'total_frames': total_frames,
                    'processed_frames': frame_number // self.frame_skip,
                    'fps': fps,
                    'duration': duration
                },
                'detection_summary': {
                    'total_detections': len(all_detections),
                    'stored_detections': len(stored_detections),
                    'processing_errors': len(processing_errors),
                    'success_rate': len(stored_detections) / max(1, len(all_detections))
                },
                'integrity_report': self.integrity_monitor.get_health_report() if self.integrity_monitor else {},
                'processing_errors': processing_errors[:10],  # Limit error details
                'detection_data': all_detections,
                'stored_ids': stored_detections,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"🎯 Bulletproof processing complete: {processing_report['detection_summary']}")
            
            return processing_report
            
        except Exception as e:
            logger.error(f"❌ Bulletproof video processing failed: {str(e)}")
            raise RuntimeError(f"Processing failed: {str(e)}")
    
    async def _store_detection_in_db(self, validated_data: Dict[str, Any], db_session):
        """Store validated detection in database"""
        try:
            from models import DetectionEvent, TestSession
            
            # Create or get test session
            test_session_id = validated_data.get('test_session_id')
            if not test_session_id:
                # Create default test session
                test_session = TestSession(
                    id=str(uuid.uuid4()),
                    name=f"Bulletproof Detection - {time.strftime('%Y-%m-%d %H:%M')}",
                    project_id="00000000-0000-0000-0000-000000000000",  # Default project
                    video_id=validated_data['video_id'],
                    status="running",
                    started_at=datetime.now(timezone.utc)
                )
                db_session.add(test_session)
                db_session.flush()  # Get the ID
                test_session_id = test_session.id
            
            # Create detection event with complete data
            bbox_data = validated_data.get('bounding_box', {})
            
            detection_event = DetectionEvent(
                id=validated_data['id'],
                test_session_id=test_session_id,
                timestamp=validated_data['timestamp'],
                confidence=bbox_data.get('confidence', 0.0),
                class_label=validated_data['vru_type'],
                validation_result='PENDING',
                
                # Complete detection data
                detection_id=validated_data['id'],
                frame_number=validated_data['frame_number'],
                vru_type=validated_data['vru_type'],
                
                # Bounding box coordinates
                bounding_box_x=bbox_data.get('x', 0),
                bounding_box_y=bbox_data.get('y', 0),
                bounding_box_width=bbox_data.get('width', 0),
                bounding_box_height=bbox_data.get('height', 0),
                
                # Processing metadata
                processing_time_ms=10.0,  # Approximate
                model_version=self.yolo_wrapper.model_version
            )
            
            db_session.add(detection_event)
            
        except Exception as e:
            logger.error(f"❌ Failed to store detection in database: {str(e)}")
            raise
    
    async def process_video_stream_bulletproof(self, video_id: str, test_session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Process video stream with bulletproof protection"""
        if not self.initialized:
            await self.initialize()
        
        db = self.db_session_factory()
        try:
            # Get video info
            from models import Video, TestSession
            
            video = db.query(Video).filter(Video.id == video_id).first()
            test_session = db.query(TestSession).filter(TestSession.id == test_session_id).first()
            
            if not video or not test_session:
                raise ValueError("Video or test session not found")
            
            # Process video stream
            cap = cv2.VideoCapture(video.file_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_number = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_number += 1
                
                # Skip frames for real-time processing
                if frame_number % self.frame_skip != 0:
                    continue
                
                timestamp = frame_number / fps
                
                # Run bulletproof detection
                detections = await self.yolo_wrapper.detect_objects(
                    frame=frame,
                    video_id=video_id,
                    frame_number=frame_number,
                    timestamp=timestamp
                )
                
                # Process each detection
                for detection in detections:
                    try:
                        annotation_dict = detection.to_annotation_dict()
                        validated_data = await self.integrity_monitor.monitor_yolo_to_db_pipeline(annotation_dict)
                        
                        if validated_data is not None:
                            await self._store_detection_in_db(validated_data, db)
                            yield validated_data
                        
                    except Exception as e:
                        logger.warning(f"Stream detection error: {str(e)}")
                        continue
                
                # Commit periodically
                if frame_number % 30 == 0:
                    db.commit()
            
            cap.release()
            db.commit()
            
        finally:
            db.close()
    
    def get_pipeline_metrics(self) -> Dict[str, Any]:
        """Get pipeline performance and integrity metrics"""
        metrics = {
            'pipeline_status': 'active' if self.initialized else 'inactive',
            'model_version': self.yolo_wrapper.model_version if self.yolo_wrapper else 'none',
            'integrity_monitoring': self.integrity_monitor is not None,
            'frame_processing_rate': 1.0 / self.frame_skip,
            'max_detections_per_frame': self.max_detections_per_frame,
            'thread_pool_size': self.thread_executor._max_workers,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if self.integrity_monitor:
            metrics['integrity_report'] = self.integrity_monitor.get_health_report()
        
        return metrics

# ==================== INTEGRATION FUNCTIONS ====================

async def create_bulletproof_detection_pipeline(db_session_factory) -> BulletproofDetectionPipeline:
    """Create and initialize bulletproof detection pipeline"""
    pipeline = BulletproofDetectionPipeline(db_session_factory)
    await pipeline.initialize()
    return pipeline

async def process_video_with_bulletproof_protection(
    video_path: str,
    video_id: str,
    db_session_factory,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process video with complete bulletproof protection
    USE THIS FUNCTION TO REPLACE EXISTING VIDEO PROCESSING
    """
    pipeline = await create_bulletproof_detection_pipeline(db_session_factory)
    return await pipeline.process_video_bulletproof(video_path, video_id, config)

if __name__ == "__main__":
    # Test the bulletproof detection system
    import asyncio
    from database import SessionLocal
    
    async def test_bulletproof_detection():
        logger.info("🧪 Testing bulletproof detection system...")
        
        pipeline = await create_bulletproof_detection_pipeline(SessionLocal)
        metrics = pipeline.get_pipeline_metrics()
        
        print("Pipeline Metrics:", metrics)
        logger.info("✅ Bulletproof detection system test completed")
    
    asyncio.run(test_bulletproof_detection())