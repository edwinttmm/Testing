#!/usr/bin/env python3
"""
Sequential Video Processing Service
Handles ONE-BUTTON START ALL VIDEOS functionality with proper results storage
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Import all necessary models and services
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, get_db
from models import (
    Project, Video, TestSession, DetectionEvent, TestResult, 
    DetectionComparison, GroundTruthObject
)

logger = logging.getLogger(__name__)

class SequentialVideoProcessor:
    """
    Complete Sequential Video Processing System
    - ONE button starts ALL videos
    - Sequential processing (video1 → video2 → video3)
    - Proper results storage
    - Project-based sessions (no random sessions)
    """
    
    def __init__(self):
        self.processing_sessions: Dict[str, Dict] = {}
        
    async def start_all_videos_sequential(
        self, 
        project_id: str, 
        video_ids: Optional[List[str]] = None,
        session_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ONE BUTTON: Start ALL videos in sequential processing
        
        Args:
            project_id: The test project ID (66f9c296-ee1e-4e81-b0ba-96d03fdc8c90)
            video_ids: Optional specific videos, otherwise processes all project videos
            session_name: Optional session name
        
        Returns:
            Dict with processing status and session info
        """
        db = SessionLocal()
        try:
            # Validate project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Get videos to process
            if video_ids:
                videos = db.query(Video).filter(
                    and_(Video.project_id == project_id, Video.id.in_(video_ids))
                ).all()
            else:
                videos = db.query(Video).filter(Video.project_id == project_id).all()
            
            if not videos:
                return {
                    "success": False,
                    "error": "No videos found for processing",
                    "project_id": project_id
                }
            
            # Create single project-based session (NO RANDOM SESSIONS)
            session_id = str(uuid.uuid4())
            
            # Get the first video for the test session requirement
            primary_video = videos[0]
            
            test_session = TestSession(
                id=session_id,
                name=session_name or f"Sequential Video Processing - {project.name}",
                project_id=project_id,
                video_id=primary_video.id,  # TestSession requires video_id
                tolerance_ms=100,  # Default tolerance
                status="running",
                session_type="sequential_processing",
                started_at=datetime.utcnow()
            )
            db.add(test_session)
            db.commit()
            
            # Track processing session
            self.processing_sessions[session_id] = {
                "project_id": project_id,
                "videos": [{"id": v.id, "filename": v.filename} for v in videos],
                "current_video_index": 0,
                "status": "running",
                "start_time": datetime.utcnow(),
                "results": [],
                "session_metadata": {
                    "auto_advance": True,
                    "sequential_processing": True,
                    "video_count": len(videos),
                    "processing_mode": "sequential"
                }
            }
            
            # Start sequential processing asynchronously
            asyncio.create_task(self._process_videos_sequentially(session_id, videos, db))
            
            return {
                "success": True,
                "message": f"Started sequential processing of {len(videos)} videos",
                "session_id": session_id,
                "project_id": project_id,
                "videos_to_process": len(videos),
                "processing_order": [v.filename for v in videos],
                "status": "started"
            }
            
        except Exception as e:
            logger.error(f"Error starting sequential processing: {e}")
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id
            }
        finally:
            db.close()
    
    async def _process_videos_sequentially(self, session_id: str, videos: List[Video], db: Session):
        """
        Process videos one by one in sequence
        """
        session_info = self.processing_sessions[session_id]
        
        try:
            for index, video in enumerate(videos):
                logger.info(f"Processing video {index + 1}/{len(videos)}: {video.filename}")
                
                # Update session progress
                session_info["current_video_index"] = index
                session_info["current_video"] = video.filename
                
                # Process single video
                video_result = await self._process_single_video(video, session_id, db)
                session_info["results"].append(video_result)
                
                # Update video status in database
                db_video = db.query(Video).filter(Video.id == video.id).first()
                if db_video:
                    db_video.status = "completed" if video_result["success"] else "failed"
                    db_video.processing_status = "completed"
                    db.commit()
                
                logger.info(f"Completed video {video.filename}: {video_result['success']}")
                
                # Small delay between videos for stability
                await asyncio.sleep(1)
            
            # Mark session as completed
            session_info["status"] = "completed"
            session_info["end_time"] = datetime.utcnow()
            
            # Update database session
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if test_session:
                test_session.status = "completed"
                test_session.completed_at = datetime.utcnow()
                # TestSession doesn't have results_summary field - store in processing metadata
                # The results will be stored in TestResult and DetectionComparison tables
                db.commit()
            
            logger.info(f"Sequential processing completed for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error in sequential processing: {e}")
            session_info["status"] = "failed"
            session_info["error"] = str(e)
            
            # Update database session as failed
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if test_session:
                test_session.status = "failed"
                test_session.error_message = str(e)
                db.commit()
    
    async def _process_single_video(self, video: Video, session_id: str, db: Session) -> Dict[str, Any]:
        """
        Process a single video with detection and result storage
        """
        try:
            logger.info(f"Starting detection for video: {video.filename}")
            
            # Simulate detection processing (replace with real detection service call)
            await asyncio.sleep(2)  # Simulate processing time
            
            # Create mock detections (replace with real detection results)
            detections = await self._generate_mock_detections(video, session_id, db)
            
            # Store results in database
            result_stored = await self._store_video_results(video, session_id, detections, db)
            
            return {
                "video_id": video.id,
                "filename": video.filename,
                "success": True,
                "detections_count": len(detections),
                "result_stored": result_stored,
                "processing_time": 2.0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing video {video.filename}: {e}")
            return {
                "video_id": video.id,
                "filename": video.filename,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _generate_mock_detections(self, video: Video, session_id: str, db: Session) -> List[Dict]:
        """
        Generate mock detections (replace with real detection service)
        """
        detections = []
        
        # Generate different detections based on video type
        if "child" in video.filename.lower():
            detection_types = ["pedestrian", "child", "person"]
        elif any(x in video.filename.lower() for x in ["vehicle", "car", "ae8e974b"]):
            detection_types = ["vehicle", "car", "cyclist"]
        else:
            detection_types = ["person", "vehicle"]
        
        # Create mock detection events
        for i, detection_type in enumerate(detection_types):
            detection_id = str(uuid.uuid4())
            
            # Create detection event (use the correct field names from models.py)
            detection_event = DetectionEvent(
                id=detection_id,
                test_session_id=session_id,
                detection_id=f"det_{i}_{video.id[:8]}",
                timestamp=i * 2.0,  # Float timestamp in seconds
                confidence=0.85 + (i * 0.05),
                class_label=detection_type,
                validation_result="Pass",
                frame_number=i * 30 + 10,
                vru_type=detection_type,
                # Bounding box coordinates (separate fields)
                bounding_box_x=100.0 + (i * 50),
                bounding_box_y=100.0 + (i * 30),
                bounding_box_width=80.0,
                bounding_box_height=120.0,
                processing_time_ms=45.2,
                model_version="yolov8_sequential"
            )
            
            db.add(detection_event)
            detections.append({
                "id": detection_id,
                "type": detection_type,
                "confidence": detection_event.confidence
            })
        
        db.commit()
        return detections
    
    async def _store_video_results(self, video: Video, session_id: str, detections: List[Dict], db: Session) -> bool:
        """
        Store comprehensive video results in database
        """
        try:
            # Create test result for this video
            result_id = str(uuid.uuid4())
            
            total_detections = len(detections)
            passed_detections = sum(1 for d in detections if d.get("confidence", 0) > 0.8)
            
            # Use the TestResult fields from models.py (enhanced test results)
            test_result = TestResult(
                id=result_id,
                test_session_id=session_id,
                accuracy=passed_detections / total_detections if total_detections > 0 else 0.0,
                precision=passed_detections / max(1, passed_detections),  # Avoid division by zero
                recall=passed_detections / max(1, total_detections),
                f1_score=2 * (passed_detections / max(1, total_detections)) * (passed_detections / max(1, passed_detections)) / 
                        (passed_detections / max(1, total_detections) + passed_detections / max(1, passed_detections)) 
                        if passed_detections > 0 else 0.0,
                true_positives=passed_detections,
                false_positives=max(0, total_detections - passed_detections),
                false_negatives=0,  # Would need ground truth for this
                statistical_analysis={
                    "video_filename": video.filename,
                    "video_id": video.id,
                    "total_detections": total_detections,
                    "passed_detections": passed_detections,
                    "failed_detections": total_detections - passed_detections,
                    "success_rate": (passed_detections / total_detections * 100) if total_detections > 0 else 0,
                    "detection_types": list(set(d["type"] for d in detections)),
                    "average_confidence": sum(d["confidence"] for d in detections) / len(detections) if detections else 0
                }
            )
            
            db.add(test_result)
            
            # Create detection comparisons for results page using correct field names
            for detection in detections:
                comparison_id = str(uuid.uuid4())
                detection_comparison = DetectionComparison(
                    id=comparison_id,
                    test_session_id=session_id,
                    detection_event_id=detection["id"],
                    match_type="TP" if detection["confidence"] > 0.8 else "FP",  # True/False Positive
                    iou_score=detection["confidence"],  # Using confidence as proxy for IoU
                    distance_error=0.0,
                    temporal_offset=0.0,
                    notes=f"Sequential processing detection: {detection['type']} with confidence {detection['confidence']:.3f}"
                )
                db.add(detection_comparison)
            
            db.commit()
            logger.info(f"Stored results for video {video.filename}: {total_detections} detections")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error storing results for video {video.filename}: {e}")
            return False
    
    def get_session_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current status of sequential processing session
        """
        if session_id not in self.processing_sessions:
            return {
                "success": False,
                "error": "Session not found",
                "session_id": session_id
            }
        
        session_info = self.processing_sessions[session_id]
        current_time = datetime.utcnow()
        
        if session_info["status"] == "running":
            elapsed_time = (current_time - session_info["start_time"]).total_seconds()
            progress = (session_info["current_video_index"] / len(session_info["videos"])) * 100
        else:
            elapsed_time = (session_info.get("end_time", current_time) - session_info["start_time"]).total_seconds()
            progress = 100 if session_info["status"] == "completed" else 0
        
        return {
            "success": True,
            "session_id": session_id,
            "status": session_info["status"],
            "progress": progress,
            "current_video_index": session_info["current_video_index"],
            "total_videos": len(session_info["videos"]),
            "current_video": session_info.get("current_video", ""),
            "elapsed_time_seconds": elapsed_time,
            "processed_videos": session_info["current_video_index"],
            "remaining_videos": len(session_info["videos"]) - session_info["current_video_index"],
            "results_count": len(session_info["results"]),
            "project_id": session_info["project_id"]
        }
    
    def get_session_results(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive results for completed session
        """
        db = SessionLocal()
        try:
            # Get session from database
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                return {
                    "success": False,
                    "error": "Session not found in database",
                    "session_id": session_id
                }
            
            # Get all test results for this session
            test_results = db.query(TestResult).filter(TestResult.test_session_id == session_id).all()
            
            # Get all detection events for this session
            detection_events = db.query(DetectionEvent).filter(DetectionEvent.test_session_id == session_id).all()
            
            # Get all detection comparisons for this session
            detection_comparisons = db.query(DetectionComparison).filter(DetectionComparison.test_session_id == session_id).all()
            
            # Get session metadata from memory
            session_metadata = {}
            if session_id in self.processing_sessions:
                session_metadata = self.processing_sessions[session_id].get("session_metadata", {})
            
            # Format results
            formatted_results = {
                "success": True,
                "session_id": session_id,
                "session_name": test_session.name,
                "project_id": test_session.project_id,
                "status": test_session.status,
                "started_at": test_session.started_at.isoformat() if test_session.started_at else None,
                "completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None,
                "session_metadata": session_metadata,
                "test_results": [
                    {
                        "id": result.id,
                        "test_session_id": result.test_session_id,
                        "accuracy": result.accuracy,
                        "precision": result.precision,
                        "recall": result.recall,
                        "f1_score": result.f1_score,
                        "true_positives": result.true_positives,
                        "false_positives": result.false_positives,
                        "false_negatives": result.false_negatives,
                        "statistical_analysis": result.statistical_analysis,
                        "created_at": result.created_at.isoformat() if result.created_at else None
                    }
                    for result in test_results
                ],
                "detection_events": [
                    {
                        "id": event.id,
                        "test_session_id": event.test_session_id,
                        "detection_id": event.detection_id,
                        "class_label": event.class_label,
                        "confidence": event.confidence,
                        "validation_result": event.validation_result,
                        "frame_number": event.frame_number,
                        "timestamp": event.timestamp,
                        "vru_type": event.vru_type,
                        "bounding_box": {
                            "x": event.bounding_box_x,
                            "y": event.bounding_box_y,
                            "width": event.bounding_box_width,
                            "height": event.bounding_box_height
                        } if event.bounding_box_x is not None else None
                    }
                    for event in detection_events
                ],
                "detection_comparisons": [
                    {
                        "id": comp.id,
                        "test_session_id": comp.test_session_id,
                        "detection_event_id": comp.detection_event_id,
                        "match_type": comp.match_type,
                        "iou_score": comp.iou_score,
                        "distance_error": comp.distance_error,
                        "temporal_offset": comp.temporal_offset,
                        "notes": comp.notes
                    }
                    for comp in detection_comparisons
                ],
                "statistics": {
                    "total_videos_processed": len(session_metadata.get("videos", [])),
                    "total_detections": len(detection_events),
                    "total_comparisons": len(detection_comparisons),
                    "passed_test_results": sum(1 for r in test_results if r.true_positives > 0),
                    "failed_test_results": sum(1 for r in test_results if r.true_positives == 0),
                    "average_confidence": sum(e.confidence for e in detection_events) / len(detection_events) if detection_events else 0,
                    "accuracy": sum(r.accuracy for r in test_results) / len(test_results) if test_results else 0,
                    "precision": sum(r.precision for r in test_results) / len(test_results) if test_results else 0,
                    "recall": sum(r.recall for r in test_results) / len(test_results) if test_results else 0
                }
            }
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error getting session results: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
        finally:
            db.close()

# Global instance
sequential_processor = SequentialVideoProcessor()