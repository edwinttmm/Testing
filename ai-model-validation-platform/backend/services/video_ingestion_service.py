"""
PRD Module 1.1 & 1.2: Video Ingestion Pipeline with Real YOLO-based VRU Detection
Implements complete video ingestion workflow with automated annotation using Ultralytics YOLO
"""

import os
import cv2
import json
import asyncio
import logging
import uuid
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import tempfile
import subprocess
from sqlalchemy.orm import Session
from sqlalchemy import func

# Real AI model imports - NO MOCKS
try:
    from ultralytics import YOLO
    import torch
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("WARNING: YOLO not available. Install with: pip install ultralytics torch")

from models import Video, GroundTruthObject, Project, VideoProjectLink
from schemas import VideoStatus, VRUType
from services.vru_tracking_service import VRUTrackingService

logger = logging.getLogger(__name__)

class VideoIngestionService:
    """PRD-compliant video ingestion with real YOLO VRU detection"""
    
    # PRD Module 1.1: Supported file formats
    SUPPORTED_FORMATS = {'.mp4', '.mov', '.avi'}
    MAX_FILE_SIZE = 2048 * 1024 * 1024  # 2GB limit
    
    # PRD Module 1.2: VRU classes for YOLO detection
    VRU_CLASS_MAPPING = {
        0: VRUType.PEDESTRIAN,      # person
        1: VRUType.CYCLIST,         # bicycle  
        3: VRUType.MOTORCYCLIST,    # motorcycle
        # Additional mappings based on COCO classes
        17: VRUType.CYCLIST,        # bicycle (alternative)
        18: VRUType.MOTORCYCLIST,   # motorcycle (alternative)
    }
    
    def __init__(self):
        self.upload_dir = Path("uploads")
        self.upload_dir.mkdir(exist_ok=True)
        
        # Initialize real YOLO model - NO MOCKS
        if YOLO_AVAILABLE:
            try:
                # Use YOLOv8 nano for fast inference
                self.yolo_model = YOLO('yolov8n.pt')
                logger.info("YOLO model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load YOLO model: {e}")
                self.yolo_model = None
        else:
            self.yolo_model = None
            logger.error("YOLO not available - real VRU detection disabled")
        
        # Initialize VRU tracking service for persistent IDs
        self.vru_tracker = VRUTrackingService()
    
    async def process_video_upload(
        self, 
        db: Session, 
        file_content: bytes, 
        filename: str, 
        project_id: str = None
    ) -> Dict[str, Any]:
        """
        PRD Module 1.1: Process uploaded video file
        - Validate file format (MP4, MOV, AVI)
        - Store with "Pending Annotation" status
        - Add to central library
        """
        try:
            # Validate file format
            file_ext = Path(filename).suffix.lower()
            if file_ext not in self.SUPPORTED_FORMATS:
                raise ValueError(f"Unsupported format {file_ext}. Supported: {', '.join(self.SUPPORTED_FORMATS)}")
            
            # Validate file size
            if len(file_content) > self.MAX_FILE_SIZE:
                raise ValueError(f"File too large. Max size: {self.MAX_FILE_SIZE / (1024*1024):.0f}MB")
            
            # Generate unique file ID and path
            video_id = str(uuid.uuid4())
            safe_filename = f"{video_id}_{filename}"
            file_path = self.upload_dir / safe_filename
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Extract video metadata
            metadata = await self._extract_video_metadata(file_path)
            
            # Handle project_id - provide default if none given
            if not project_id:
                # Use default project or first available project
                default_project = db.query(Project).filter(Project.id == "default-test-project").first()
                if not default_project:
                    default_project = db.query(Project).first()
                if default_project:
                    project_id = default_project.id
                else:
                    raise ValueError("No projects available. Please create a project first.")
            
            # Create video record with PRD-compliant status
            db_video = Video(
                id=video_id,
                filename=safe_filename,
                file_path=str(file_path),
                file_size=len(file_content),
                duration=metadata.get('duration'),
                fps=metadata.get('fps'),
                resolution=f"{metadata.get('width', 0)}x{metadata.get('height', 0)}",
                status="pending_annotation",  # PRD Module 1.1 status
                processing_status="pending",
                ground_truth_generated=False,
                project_id=project_id  # FIX: Add project_id to avoid NOT NULL constraint
            )
            
            db.add(db_video)
            db.commit()
            db.refresh(db_video)
            
            # Assign to project if provided, otherwise add to central store
            if project_id:
                await self._assign_to_project(db, video_id, project_id)
            else:
                await self._assign_to_central_store(db, video_id)
            
            # Trigger automated annotation processing (Module 1.2)
            await self._trigger_automated_annotation(db, video_id)
            
            logger.info(f"Video {filename} uploaded successfully with ID {video_id}")
            
            return {
                "video_id": video_id,
                "filename": filename,
                "status": "pending_annotation",
                "file_size": len(file_content),
                "duration": metadata.get('duration'),
                "message": "Video uploaded and queued for automated annotation"
            }
            
        except Exception as e:
            logger.error(f"Error processing video upload: {e}")
            # Cleanup file if created
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink()
            raise
    
    async def process_automated_annotation(
        self, 
        db: Session, 
        video_id: str
    ) -> Dict[str, Any]:
        """
        PRD Module 1.2: Automated Annotation with Real YOLO
        - Use AI model to identify VRUs
        - Draw bounding boxes
        - Assign persistent VRU IDs
        - Move to "Pending Validation" status
        """
        try:
            # Get video record
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            if not self.yolo_model:
                raise RuntimeError("YOLO model not available - cannot perform real VRU detection")
            
            logger.info(f"Starting automated annotation for video {video_id}")
            
            # Update status to processing
            video.processing_status = "processing"
            db.commit()
            
            # Process video with YOLO
            detections = await self._detect_vrus_with_yolo(video.file_path)
            
            # Generate persistent VRU IDs and create ground truth objects
            annotations_created = await self._create_ground_truth_annotations(
                db, video_id, detections
            )
            
            # Update video status to pending validation (PRD workflow)
            video.status = "pending_validation"  # PRD Module 1.2 status
            video.processing_status = "completed"
            video.ground_truth_generated = True
            video.detection_count = len(annotations_created)
            
            db.commit()
            
            logger.info(f"Automated annotation completed for video {video_id}. Created {len(annotations_created)} annotations")
            
            return {
                "video_id": video_id,
                "status": "pending_validation",
                "annotations_created": len(annotations_created),
                "processing_time": "completed",
                "message": "Automated annotation completed. Video ready for validation."
            }
            
        except Exception as e:
            logger.error(f"Error in automated annotation for video {video_id}: {e}")
            # Update video status to error
            if 'video' in locals():
                video.processing_status = "error"
                video.status = "error"
                db.commit()
            raise
    
    async def _detect_vrus_with_yolo(self, video_path: str) -> List[Dict[str, Any]]:
        """
        Real YOLO-based VRU detection - NO MOCKS
        Returns list of detections with bounding boxes and confidence
        """
        if not self.yolo_model:
            raise RuntimeError("YOLO model not available")
        
        detections = []
        cap = cv2.VideoCapture(video_path)
        
        try:
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            frame_idx = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Run YOLO inference on frame
                results = self.yolo_model(frame, verbose=False)
                
                # Process detections
                for result in results:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            # Get detection data
                            class_id = int(box.cls)
                            confidence = float(box.conf)
                            coords = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                            
                            # Filter for VRU classes only
                            if class_id in self.VRU_CLASS_MAPPING and confidence > 0.5:
                                vru_type = self.VRU_CLASS_MAPPING[class_id]
                                
                                # Convert coordinates to x, y, width, height
                                x1, y1, x2, y2 = coords
                                width = x2 - x1
                                height = y2 - y1
                                
                                detection = {
                                    "frame_number": frame_idx,
                                    "timestamp": frame_idx / fps,
                                    "vru_type": vru_type.value,
                                    "bbox": {
                                        "x": x1,
                                        "y": y1,
                                        "width": width,
                                        "height": height
                                    },
                                    "confidence": confidence,
                                    "class_id": class_id
                                }
                                
                                detections.append(detection)
                
                frame_idx += 1
                
                # Progress logging every 100 frames
                if frame_idx % 100 == 0:
                    logger.info(f"Processed {frame_idx}/{frame_count} frames")
        
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            logger.exception("YOLO detection error details:")
            return []
        finally:
            cap.release()
        
        logger.info(f"YOLO detection completed. Found {len(detections)} VRU detections")
        return detections
    
    async def _create_ground_truth_annotations(
        self, 
        db: Session, 
        video_id: str, 
        detections: List[Dict[str, Any]]
    ) -> List[GroundTruthObject]:
        """
        Create ground truth objects with persistent VRU ID tracking
        """
        if not detections:
            return []
        
        # Initialize tracking for this video
        self.vru_tracker.initialize_video_tracking(video_id)
        
        annotations = []
        
        for detection in detections:
            # Get or assign persistent VRU ID
            vru_id = self.vru_tracker.track_vru(
                video_id=video_id,
                frame_number=detection["frame_number"],
                bbox=detection["bbox"],
                vru_type=detection["vru_type"],
                confidence=detection["confidence"]
            )
            
            # Create ground truth object
            gt_object = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video_id,
                tracking_id=vru_id,  # Persistent VRU ID
                frame_number=detection["frame_number"],
                timestamp=detection["timestamp"],
                class_label=detection["vru_type"],
                x=detection["bbox"]["x"],
                y=detection["bbox"]["y"],
                width=detection["bbox"]["width"],
                height=detection["bbox"]["height"],
                bounding_box=detection["bbox"],  # For backward compatibility
                confidence=detection["confidence"],
                validated=False,  # Requires manual validation
                difficult=False
            )
            
            annotations.append(gt_object)
        
        # Batch insert all annotations
        db.add_all(annotations)
        db.commit()
        
        # Refresh all objects
        for annotation in annotations:
            db.refresh(annotation)
        
        return annotations
    
    async def _extract_video_metadata(self, video_path: Path) -> Dict[str, Any]:
        """Extract video metadata using OpenCV"""
        try:
            cap = cv2.VideoCapture(str(video_path))
            
            metadata = {
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "fps": cap.get(cv2.CAP_PROP_FPS),
                "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            }
            
            # Calculate duration
            if metadata["fps"] > 0:
                metadata["duration"] = metadata["frame_count"] / metadata["fps"]
            else:
                metadata["duration"] = 0
            
            cap.release()
            return metadata
            
        except Exception as e:
            logger.error(f"Error extracting video metadata: {e}")
            return {"width": 0, "height": 0, "fps": 0, "duration": 0, "frame_count": 0}
    
    async def _assign_to_project(self, db: Session, video_id: str, project_id: str):
        """Assign video to specific project"""
        try:
            # Check if project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Create video-project link
            link = VideoProjectLink(
                id=str(uuid.uuid4()),
                video_id=video_id,
                project_id=project_id,
                assignment_reason="user_upload",
                intelligent_match=False
            )
            
            db.add(link)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error assigning video to project: {e}")
            raise
    
    async def _assign_to_central_store(self, db: Session, video_id: str):
        """Assign video to central store project"""
        try:
            # Get or create central store project
            central_project = db.query(Project).filter(
                Project.name == "Central Video Library"
            ).first()
            
            if not central_project:
                # Create central store project
                central_project = Project(
                    id=str(uuid.uuid4()),
                    name="Central Video Library",
                    description="Centralized storage for uploaded videos",
                    camera_model="Various",
                    camera_view="Front-facing VRU",
                    signal_type="GPIO",
                    status="Active",
                    owner_id="system"
                )
                db.add(central_project)
                db.commit()
                db.refresh(central_project)
            
            await self._assign_to_project(db, video_id, central_project.id)
            
        except Exception as e:
            logger.error(f"Error assigning video to central store: {e}")
            raise
    
    async def _trigger_automated_annotation(self, db: Session, video_id: str):
        """Trigger automated annotation processing in background"""
        try:
            # In production, this would trigger a background task/queue
            # For now, process immediately
            asyncio.create_task(self.process_automated_annotation(db, video_id))
            
        except Exception as e:
            logger.error(f"Error triggering automated annotation: {e}")
    
    async def get_video_library(
        self, 
        db: Session, 
        status_filter: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        PRD Module 1.4: Video Library
        Get videos with status filtering and search capability
        """
        try:
            query = db.query(Video)
            
            # Apply status filter
            if status_filter:
                query = query.filter(Video.status == status_filter)
            
            # Apply project filter
            if project_id:
                query = query.join(VideoProjectLink).filter(
                    VideoProjectLink.project_id == project_id
                )
            
            videos = query.order_by(Video.created_at.desc()).all()
            
            # Format response
            video_list = []
            for video in videos:
                video_data = {
                    "id": video.id,
                    "filename": video.filename,
                    "status": video.status,
                    "processing_status": video.processing_status,
                    "ground_truth_generated": video.ground_truth_generated,
                    "detection_count": video.detection_count or 0,
                    "duration": video.duration,
                    "file_size": video.file_size,
                    "created_at": video.created_at.isoformat() if video.created_at else None,
                    "resolution": video.resolution
                }
                video_list.append(video_data)
            
            return video_list
            
        except Exception as e:
            logger.error(f"Error getting video library: {e}")
            raise
    
    async def get_video_annotations(
        self, 
        db: Session, 
        video_id: str
    ) -> Dict[str, Any]:
        """Get annotations for a specific video with overlay data"""
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            # Get ground truth objects
            annotations = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video_id
            ).order_by(GroundTruthObject.timestamp).all()
            
            # Format annotations
            annotation_data = []
            for ann in annotations:
                annotation_data.append({
                    "id": ann.id,
                    "tracking_id": ann.tracking_id,
                    "frame_number": ann.frame_number,
                    "timestamp": ann.timestamp,
                    "vru_type": ann.class_label,
                    "bbox": {
                        "x": ann.x,
                        "y": ann.y,
                        "width": ann.width,
                        "height": ann.height
                    },
                    "confidence": ann.confidence,
                    "validated": ann.validated
                })
            
            return {
                "video_id": video_id,
                "video_filename": video.filename,
                "status": video.status,
                "annotations": annotation_data,
                "total_annotations": len(annotation_data),
                "validation_required": video.status == "pending_validation"
            }
            
        except Exception as e:
            logger.error(f"Error getting video annotations: {e}")
            raise
    
    async def validate_video_annotations(
        self, 
        db: Session, 
        video_id: str
    ) -> Dict[str, Any]:
        """
        PRD Module 1.3: Mark video annotations as validated
        Move from "Pending Validation" to "Validated" status
        """
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                raise ValueError(f"Video {video_id} not found")
            
            if video.status != "pending_validation":
                raise ValueError(f"Video status is {video.status}, expected 'pending_validation'")
            
            # Mark all annotations as validated
            db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video_id
            ).update({"validated": True})
            
            # Update video status to validated
            video.status = "validated"
            
            db.commit()
            
            logger.info(f"Video {video_id} annotations validated successfully")
            
            return {
                "video_id": video_id,
                "status": "validated",
                "message": "Video annotations validated and locked. Video is now available for testing projects."
            }
            
        except Exception as e:
            logger.error(f"Error validating video annotations: {e}")
            db.rollback()
            raise