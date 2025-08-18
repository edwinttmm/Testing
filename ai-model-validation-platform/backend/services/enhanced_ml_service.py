"""
Enhanced ML service that integrates with the existing backend

This service replaces the basic ground truth service with a full ML pipeline
"""
import sys
import os
sys.path.append('/home/user/Testing/src')

import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
import tempfile
import shutil

# Import ML pipeline components
from ml.integration.backend_integration import ml_validation_service
from ml.inference.yolo_service import yolo_service
from ml.models.model_manager import model_manager
from ml.preprocessing.video_processor import video_processor
from ml.monitoring.performance_monitor import performance_monitor
from ml.utils.screenshot_generator import screenshot_generator

# Import existing backend components
from database import SessionLocal
from models import Video, GroundTruthObject, DetectionEvent, TestSession
from schemas import GroundTruthResponse

logger = logging.getLogger(__name__)

class EnhancedMLService:
    """
    Enhanced ML service that provides comprehensive VRU detection capabilities
    Integrates with existing backend database and validation workflows
    """
    
    def __init__(self):
        self.is_initialized = False
        self.ml_service = ml_validation_service
        
    async def initialize(self) -> bool:
        """Initialize the enhanced ML service"""
        try:
            logger.info("Initializing enhanced ML service...")
            
            # Initialize ML validation service
            success = await self.ml_service.initialize()
            
            if success:
                self.is_initialized = True
                logger.info("Enhanced ML service initialized successfully")
                return True
            else:
                logger.error("Failed to initialize ML validation service")
                return False
                
        except Exception as e:
            logger.error(f"Enhanced ML service initialization failed: {str(e)}")
            return False
    
    async def process_video_async(self, video_id: str, video_path: str) -> Dict[str, Any]:
        """
        Process video asynchronously for ground truth generation
        
        Args:
            video_id: Database video ID
            video_path: Path to video file
            
        Returns:
            Dictionary with processing results
        """
        try:
            if not self.is_initialized:
                await self.initialize()
            
            logger.info(f"Starting ML processing for video {video_id}: {video_path}")
            
            # Create output directory for this video
            output_dir = tempfile.mkdtemp(prefix=f"ml_video_{video_id}_")
            
            # Generate ground truth using ML pipeline
            ground_truth_result = await self.ml_service.generate_ground_truth(
                video_path, output_dir
            )
            
            if ground_truth_result.get("status") == "completed":
                # Store ground truth in database
                await self._store_ground_truth_in_db(video_id, ground_truth_result)
                
                # Update video status
                await self._update_video_status(video_id, "processed", ground_truth_result)
                
                logger.info(f"ML processing completed for video {video_id}: {ground_truth_result['total_detections']} detections")
                
                return {
                    "status": "success",
                    "video_id": video_id,
                    "total_detections": ground_truth_result["total_detections"],
                    "processing_time": ground_truth_result["processing_time_seconds"],
                    "output_dir": output_dir,
                    "screenshot_paths": ground_truth_result["metadata"]["screenshot_paths"]
                }
            else:
                logger.error(f"ML processing failed for video {video_id}")
                await self._update_video_status(video_id, "failed", ground_truth_result)
                
                return {
                    "status": "error",
                    "video_id": video_id,
                    "error": ground_truth_result.get("error", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Video processing failed for {video_id}: {str(e)}", exc_info=True)
            await self._update_video_status(video_id, "failed", {"error": str(e)})
            
            return {
                "status": "error",
                "video_id": video_id,
                "error": str(e)
            }
    
    async def _store_ground_truth_in_db(self, video_id: str, ground_truth_result: Dict[str, Any]):
        """Store ground truth objects in database"""
        try:
            db = SessionLocal()
            
            # Clear existing ground truth for this video
            db.query(GroundTruthObject).filter(GroundTruthObject.video_id == video_id).delete()
            
            # Store new ground truth objects
            ground_truth_objects = ground_truth_result.get("objects", [])
            
            for gt_obj in ground_truth_objects:
                db_gt_obj = GroundTruthObject(
                    video_id=video_id,
                    timestamp=gt_obj["timestamp"],
                    class_label=gt_obj["class_label"],
                    confidence=gt_obj["confidence"],
                    bounding_box={
                        "x": gt_obj["bbox"]["x1"],
                        "y": gt_obj["bbox"]["y1"],
                        "width": gt_obj["bbox"]["x2"] - gt_obj["bbox"]["x1"],
                        "height": gt_obj["bbox"]["y2"] - gt_obj["bbox"]["y1"]
                    }
                )
                db.add(db_gt_obj)
            
            db.commit()
            logger.info(f"Stored {len(ground_truth_objects)} ground truth objects for video {video_id}")
            
        except Exception as e:
            logger.error(f"Failed to store ground truth in database: {str(e)}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    async def _update_video_status(self, video_id: str, status: str, result_data: Dict[str, Any]):
        """Update video processing status in database"""
        try:
            db = SessionLocal()
            
            video = db.query(Video).filter(Video.id == video_id).first()
            if video:
                video.status = status
                if status == "processed":
                    video.ground_truth_generated = True
                
                db.commit()
                
        except Exception as e:
            logger.error(f"Failed to update video status: {str(e)}")
            if db:
                db.rollback()
        finally:
            if db:
                db.close()
    
    async def get_ground_truth_response(self, video_id: str) -> GroundTruthResponse:
        """
        Get ground truth response in the format expected by existing API
        
        Args:
            video_id: Database video ID
            
        Returns:
            GroundTruthResponse object
        """
        try:
            db = SessionLocal()
            
            # Get ground truth objects from database
            ground_truth_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video_id
            ).all()
            
            # Convert to response format
            objects = []
            for gt_obj in ground_truth_objects:
                obj_dict = {
                    "id": gt_obj.id,
                    "timestamp": gt_obj.timestamp,
                    "class_label": gt_obj.class_label,
                    "confidence": gt_obj.confidence,
                    "bbox": {
                        "x1": gt_obj.bbox_x1,
                        "y1": gt_obj.bbox_y1,
                        "x2": gt_obj.bbox_x2,
                        "y2": gt_obj.bbox_y2
                    },
                    "track_id": gt_obj.track_id,
                    "frame_number": gt_obj.frame_number
                }
                objects.append(obj_dict)
            
            response = GroundTruthResponse(
                video_id=video_id,
                objects=objects,
                total_detections=len(objects),
                status="completed" if objects else "no_detections",
                message=f"Found {len(objects)} VRU detections using ML pipeline"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to get ground truth response: {str(e)}")
            return GroundTruthResponse(
                video_id=video_id,
                objects=[],
                total_detections=0,
                status="error",
                message=f"Error retrieving ground truth: {str(e)}"
            )
        finally:
            if db:
                db.close()
    
    async def validate_detection_event(self, 
                                     test_session_id: str,
                                     timestamp: float,
                                     class_label: str,
                                     confidence: Optional[float] = None) -> str:
        """
        Validate detection event using ML-generated ground truth
        
        Args:
            test_session_id: Test session ID
            timestamp: Detection timestamp
            class_label: Detected class
            confidence: Detection confidence
            
        Returns:
            Validation result: "TP", "FP", "FN", or "ERROR"
        """
        try:
            db = SessionLocal()
            
            # Get test session to find video and tolerance
            test_session = db.query(TestSession).filter(
                TestSession.id == test_session_id
            ).first()
            
            if not test_session:
                return "ERROR"
            
            # Get ground truth objects for the video
            ground_truth_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == test_session.video_id
            ).all()
            
            # Convert to format expected by ML service
            gt_objects_list = []
            for gt_obj in ground_truth_objects:
                gt_dict = {
                    "timestamp": gt_obj.timestamp,
                    "class_label": gt_obj.class_label,
                    "confidence": gt_obj.confidence
                }
                gt_objects_list.append(gt_dict)
            
            # Create detection event dict
            detection_event = {
                "timestamp": timestamp,
                "class_label": class_label,
                "confidence": confidence or 0.5
            }
            
            # Use ML service for validation
            result = await self.ml_service.validate_detection_event(
                detection_event, gt_objects_list, test_session.tolerance_ms
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Detection validation failed: {str(e)}")
            return "ERROR"
        finally:
            if db:
                db.close()
    
    async def get_session_validation_results(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive validation results for a test session using ML metrics
        
        Args:
            session_id: Test session ID
            
        Returns:
            Dictionary with validation metrics
        """
        try:
            db = SessionLocal()
            
            # Get test session
            test_session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()
            
            if not test_session:
                return {"error": "Test session not found"}
            
            # Get detection events
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).all()
            
            # Get ground truth objects
            ground_truth_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == test_session.video_id
            ).all()
            
            # Convert to format expected by ML service
            events_list = []
            for event in detection_events:
                event_dict = {
                    "timestamp": event.timestamp,
                    "class_label": event.class_label,
                    "confidence": event.confidence or 0.5
                }
                events_list.append(event_dict)
            
            gt_list = []
            for gt_obj in ground_truth_objects:
                gt_dict = {
                    "timestamp": gt_obj.timestamp,
                    "class_label": gt_obj.class_label,
                    "confidence": gt_obj.confidence
                }
                gt_list.append(gt_dict)
            
            # Calculate metrics using ML service
            metrics = await self.ml_service.calculate_session_metrics(
                events_list, gt_list, test_session.tolerance_ms
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Session validation results failed: {str(e)}")
            return {"error": str(e)}
        finally:
            if db:
                db.close()
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get enhanced ML service status"""
        try:
            ml_status = await self.ml_service.get_service_status()
            performance_stats = performance_monitor.get_current_stats()
            
            return {
                "enhanced_ml_service": {
                    "initialized": self.is_initialized,
                    "ml_pipeline_status": ml_status,
                    "performance_stats": performance_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Service status retrieval failed: {str(e)}")
            return {
                "enhanced_ml_service": {
                    "initialized": False,
                    "error": str(e)
                }
            }
    
    async def shutdown(self):
        """Shutdown enhanced ML service"""
        try:
            await self.ml_service.shutdown()
            self.is_initialized = False
            logger.info("Enhanced ML service shut down")
            
        except Exception as e:
            logger.error(f"Enhanced ML service shutdown failed: {str(e)}")

# Global enhanced ML service instance
enhanced_ml_service = EnhancedMLService()