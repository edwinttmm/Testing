"""
Enhanced Test Workflow Orchestrator
Complete automated test execution system with real-time progress tracking
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from database import SessionLocal
from models import (
    Project, Video, TestSession, DetectionEvent, 
    GroundTruthObject, TestResult, DetectionComparison
)

# Import existing services
from services.video_processing_workflow import VideoProcessingWorkflow
from services.enhanced_detection_service import EnhancedDetection as EnhancedDetectionService
from services.websocket_service import realtime_service
from socketio_server import sio

logger = logging.getLogger(__name__)

class WorkflowStatus(Enum):
    """Test workflow execution status"""
    INITIALIZING = "initializing"
    LOADING_VIDEOS = "loading_videos"
    PROCESSING_VIDEO = "processing_video"
    RUNNING_DETECTION = "running_detection"
    COMPARING_RESULTS = "comparing_results"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class VideoStatus(Enum):
    """Individual video processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    DETECTION = "detection"
    COMPARISON = "comparison"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class VideoTestResult:
    """Individual video test results"""
    video_id: str
    video_filename: str
    status: VideoStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    processing_duration: Optional[float] = None
    
    # Detection Results
    total_detections: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    # Metrics
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    
    # Error information
    error_message: Optional[str] = None
    error_details: Optional[Dict] = None

@dataclass
class WorkflowProgress:
    """Overall workflow progress tracking"""
    total_videos: int
    completed_videos: int
    failed_videos: int
    current_video: Optional[str] = None
    current_video_progress: float = 0.0
    overall_progress: float = 0.0
    estimated_completion: Optional[datetime] = None

@dataclass
class WorkflowConfiguration:
    """Configuration for test workflow execution"""
    project_id: str
    test_session_name: str
    tolerance_ms: int = 100
    parallel_processing: bool = False
    max_parallel_videos: int = 3
    retry_failed_videos: bool = True
    max_retries: int = 2
    timeout_per_video: int = 300  # 5 minutes
    
    # Result generation options
    generate_individual_reports: bool = True
    generate_aggregate_report: bool = True
    include_visual_evidence: bool = True
    
    # Error handling
    continue_on_error: bool = True
    fail_fast: bool = False

class EnhancedTestWorkflowOrchestrator:
    """
    Complete automated test workflow orchestrator
    Handles sequential video processing with real-time updates
    """
    
    def __init__(self):
        self.active_workflows: Dict[str, Dict] = {}
        self.video_processing_service = None
        self.detection_service = None
        
    async def start_enhanced_test_workflow(
        self,
        config: WorkflowConfiguration,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Start the complete enhanced test workflow
        Returns workflow_id for tracking
        """
        workflow_id = str(uuid.uuid4())
        
        try:
            # Initialize workflow tracking
            workflow_data = {
                "id": workflow_id,
                "config": config,
                "status": WorkflowStatus.INITIALIZING,
                "start_time": datetime.utcnow(),
                "progress": WorkflowProgress(
                    total_videos=0,
                    completed_videos=0,
                    failed_videos=0
                ),
                "video_results": {},
                "error_log": [],
                "callbacks": [progress_callback] if progress_callback else []
            }
            
            self.active_workflows[workflow_id] = workflow_data
            
            # Start the workflow execution
            asyncio.create_task(self._execute_workflow(workflow_id))
            
            logger.info(f"Started enhanced test workflow: {workflow_id}")
            return workflow_id
            
        except Exception as e:
            logger.error(f"Failed to start workflow: {e}")
            raise
    
    async def _execute_workflow(self, workflow_id: str):
        """Execute the complete test workflow"""
        workflow_data = self.active_workflows[workflow_id]
        config = workflow_data["config"]
        
        try:
            # Phase 1: Initialize and load videos
            await self._update_workflow_status(
                workflow_id, 
                WorkflowStatus.LOADING_VIDEOS,
                "Loading project videos..."
            )
            
            videos = await self._load_project_videos(config.project_id)
            workflow_data["progress"].total_videos = len(videos)
            
            if not videos:
                raise Exception("No videos found in project")
            
            await self._emit_progress_update(workflow_id)
            
            # Phase 2: Process videos sequentially
            for video_index, video in enumerate(videos):
                if workflow_data["status"] == WorkflowStatus.CANCELLED:
                    break
                    
                await self._process_single_video(workflow_id, video, video_index)
                
                # Update overall progress
                workflow_data["progress"].completed_videos += 1
                workflow_data["progress"].overall_progress = (
                    workflow_data["progress"].completed_videos / 
                    workflow_data["progress"].total_videos * 100
                )
                
                await self._emit_progress_update(workflow_id)
            
            # Phase 3: Generate final report
            await self._update_workflow_status(
                workflow_id,
                WorkflowStatus.GENERATING_REPORT,
                "Generating comprehensive test results..."
            )
            
            final_results = await self._generate_final_report(workflow_id)
            workflow_data["final_results"] = final_results
            
            # Mark as completed
            await self._update_workflow_status(
                workflow_id,
                WorkflowStatus.COMPLETED,
                "Enhanced test workflow completed successfully!"
            )
            
            workflow_data["end_time"] = datetime.utcnow()
            workflow_data["duration"] = (
                workflow_data["end_time"] - workflow_data["start_time"]
            ).total_seconds()
            
        except Exception as e:
            logger.error(f"Workflow {workflow_id} failed: {e}")
            await self._handle_workflow_error(workflow_id, e)
    
    async def _process_single_video(
        self, 
        workflow_id: str, 
        video: Video,
        video_index: int
    ):
        """Process a single video through the complete test pipeline"""
        workflow_data = self.active_workflows[workflow_id]
        config = workflow_data["config"]
        
        # Initialize video result tracking
        video_result = VideoTestResult(
            video_id=video.id,
            video_filename=video.filename,
            status=VideoStatus.PENDING,
            start_time=datetime.utcnow()
        )
        
        workflow_data["video_results"][video.id] = video_result
        workflow_data["progress"].current_video = video.filename
        
        try:
            # Update status
            await self._update_workflow_status(
                workflow_id,
                WorkflowStatus.PROCESSING_VIDEO,
                f"Processing video {video_index + 1}/{workflow_data['progress'].total_videos}: {video.filename}"
            )
            
            # Step 1: Video preprocessing and ground truth generation
            video_result.status = VideoStatus.PROCESSING
            await self._emit_video_progress_update(workflow_id, video.id, 10.0, "Starting video processing...")
            
            await self._ensure_ground_truth_exists(video)
            
            # Step 2: Run LabJack detection
            video_result.status = VideoStatus.DETECTION
            await self._emit_video_progress_update(workflow_id, video.id, 40.0, "Running LabJack detection...")
            
            detection_results = await self._run_detection_pipeline(video, config)
            video_result.total_detections = len(detection_results.get("detections", []))
            
            # Step 3: Compare with ground truth
            video_result.status = VideoStatus.COMPARISON
            await self._emit_video_progress_update(workflow_id, video.id, 70.0, "Comparing with ground truth...")
            
            comparison_results = await self._compare_with_ground_truth(
                video, detection_results, config
            )
            
            # Update video metrics
            video_result.true_positives = comparison_results["true_positives"]
            video_result.false_positives = comparison_results["false_positives"]
            video_result.false_negatives = comparison_results["false_negatives"]
            
            # Calculate metrics
            if video_result.true_positives + video_result.false_positives > 0:
                video_result.precision = (
                    video_result.true_positives / 
                    (video_result.true_positives + video_result.false_positives)
                )
            
            if video_result.true_positives + video_result.false_negatives > 0:
                video_result.recall = (
                    video_result.true_positives / 
                    (video_result.true_positives + video_result.false_negatives)
                )
            
            if video_result.precision and video_result.recall:
                video_result.f1_score = (
                    2 * (video_result.precision * video_result.recall) / 
                    (video_result.precision + video_result.recall)
                )
            
            # Step 4: Generate individual video report
            await self._emit_video_progress_update(workflow_id, video.id, 90.0, "Generating video report...")
            
            if config.generate_individual_reports:
                await self._generate_individual_video_report(video, video_result)
            
            # Mark video as completed
            video_result.status = VideoStatus.COMPLETED
            video_result.end_time = datetime.utcnow()
            video_result.processing_duration = (
                video_result.end_time - video_result.start_time
            ).total_seconds()
            
            await self._emit_video_progress_update(workflow_id, video.id, 100.0, "Video processing completed!")
            
        except Exception as e:
            logger.error(f"Error processing video {video.id}: {e}")
            video_result.status = VideoStatus.FAILED
            video_result.error_message = str(e)
            video_result.error_details = {"exception_type": type(e).__name__}
            
            workflow_data["progress"].failed_videos += 1
            workflow_data["error_log"].append({
                "video_id": video.id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
            
            if not config.continue_on_error:
                raise
    
    async def _ensure_ground_truth_exists(self, video: Video):
        """Ensure ground truth data exists for the video"""
        if not video.ground_truth_generated:
            # Use existing ground truth service or generate
            db = SessionLocal()
            try:
                ground_truth_objects = db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == video.id
                ).all()
                
                if not ground_truth_objects:
                    logger.warning(f"No ground truth found for video {video.id}")
                    # Could integrate with ground truth generation service here
                    
            finally:
                db.close()
    
    async def _run_detection_pipeline(
        self, 
        video: Video, 
        config: WorkflowConfiguration
    ) -> Dict:
        """Run the LabJack detection pipeline on the video"""
        try:
            # Initialize detection service if needed
            if not self.detection_service:
                self.detection_service = EnhancedDetectionService()
            
            # Create test session
            db = SessionLocal()
            try:
                test_session = TestSession(
                    name=f"{config.test_session_name}_{video.filename}",
                    project_id=config.project_id,
                    video_id=video.id,
                    tolerance_ms=config.tolerance_ms
                )
                db.add(test_session)
                db.commit()
                db.refresh(test_session)
                
                # Run detection
                detection_results = await self.detection_service.run_enhanced_detection(
                    video_path=video.file_path,
                    test_session_id=test_session.id
                )
                
                return {
                    "test_session_id": test_session.id,
                    "detections": detection_results.get("detections", []),
                    "metadata": detection_results.get("metadata", {})
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Detection pipeline failed for video {video.id}: {e}")
            raise
    
    async def _compare_with_ground_truth(
        self, 
        video: Video, 
        detection_results: Dict,
        config: WorkflowConfiguration
    ) -> Dict:
        """Compare detection results with ground truth"""
        db = SessionLocal()
        try:
            # Load ground truth
            ground_truth = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).all()
            
            # Load detection events
            detection_events = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == detection_results["test_session_id"]
            ).all()
            
            # Perform comparison logic
            comparison_results = {
                "true_positives": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "comparisons": []
            }
            
            # Simple temporal matching (can be enhanced with spatial matching)
            tolerance_seconds = config.tolerance_ms / 1000.0
            
            for detection in detection_events:
                matched = False
                for gt_object in ground_truth:
                    time_diff = abs(detection.timestamp - gt_object.timestamp)
                    
                    if time_diff <= tolerance_seconds:
                        # Match found
                        comparison_results["true_positives"] += 1
                        matched = True
                        
                        # Store comparison
                        comparison = DetectionComparison(
                            test_session_id=detection_results["test_session_id"],
                            ground_truth_id=gt_object.id,
                            detection_event_id=detection.id,
                            match_type="TP",
                            temporal_offset=time_diff
                        )
                        db.add(comparison)
                        break
                
                if not matched:
                    comparison_results["false_positives"] += 1
                    comparison = DetectionComparison(
                        test_session_id=detection_results["test_session_id"],
                        detection_event_id=detection.id,
                        match_type="FP"
                    )
                    db.add(comparison)
            
            # Find unmatched ground truth (false negatives)
            for gt_object in ground_truth:
                matched = False
                for detection in detection_events:
                    time_diff = abs(detection.timestamp - gt_object.timestamp)
                    if time_diff <= tolerance_seconds:
                        matched = True
                        break
                
                if not matched:
                    comparison_results["false_negatives"] += 1
                    comparison = DetectionComparison(
                        test_session_id=detection_results["test_session_id"],
                        ground_truth_id=gt_object.id,
                        match_type="FN"
                    )
                    db.add(comparison)
            
            db.commit()
            return comparison_results
            
        finally:
            db.close()
    
    async def _generate_individual_video_report(
        self, 
        video: Video, 
        video_result: VideoTestResult
    ):
        """Generate individual video test report"""
        report_data = {
            "video_info": {
                "id": video.id,
                "filename": video.filename,
                "duration": video.duration,
                "fps": video.fps,
                "resolution": video.resolution
            },
            "test_results": {
                "total_detections": video_result.total_detections,
                "true_positives": video_result.true_positives,
                "false_positives": video_result.false_positives,
                "false_negatives": video_result.false_negatives,
                "precision": video_result.precision,
                "recall": video_result.recall,
                "f1_score": video_result.f1_score
            },
            "processing_info": {
                "start_time": video_result.start_time.isoformat() if video_result.start_time else None,
                "end_time": video_result.end_time.isoformat() if video_result.end_time else None,
                "duration_seconds": video_result.processing_duration,
                "status": video_result.status.value
            },
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Save report to file
        reports_dir = Path("reports/individual_videos")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = reports_dir / f"video_{video.id}_test_report.json"
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"Generated individual report for video {video.id}: {report_path}")
    
    async def _generate_final_report(self, workflow_id: str) -> Dict:
        """Generate comprehensive final test report"""
        workflow_data = self.active_workflows[workflow_id]
        video_results = workflow_data["video_results"]
        
        # Aggregate metrics
        total_videos = len(video_results)
        completed_videos = sum(1 for r in video_results.values() if r.status == VideoStatus.COMPLETED)
        failed_videos = sum(1 for r in video_results.values() if r.status == VideoStatus.FAILED)
        
        # Calculate overall metrics
        total_detections = sum(r.total_detections for r in video_results.values())
        total_tp = sum(r.true_positives for r in video_results.values())
        total_fp = sum(r.false_positives for r in video_results.values())
        total_fn = sum(r.false_negatives for r in video_results.values())
        
        overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
        overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
        overall_f1 = (
            2 * (overall_precision * overall_recall) / (overall_precision + overall_recall)
            if (overall_precision + overall_recall) > 0 else 0
        )
        
        final_report = {
            "workflow_summary": {
                "workflow_id": workflow_id,
                "project_id": workflow_data["config"].project_id,
                "test_session_name": workflow_data["config"].test_session_name,
                "start_time": workflow_data["start_time"].isoformat(),
                "end_time": workflow_data.get("end_time", datetime.utcnow()).isoformat(),
                "total_duration_seconds": workflow_data.get("duration", 0),
                "status": workflow_data["status"].value
            },
            "video_summary": {
                "total_videos": total_videos,
                "completed_videos": completed_videos,
                "failed_videos": failed_videos,
                "success_rate": completed_videos / total_videos if total_videos > 0 else 0
            },
            "detection_summary": {
                "total_detections": total_detections,
                "true_positives": total_tp,
                "false_positives": total_fp,
                "false_negatives": total_fn
            },
            "performance_metrics": {
                "overall_precision": overall_precision,
                "overall_recall": overall_recall,
                "overall_f1_score": overall_f1,
                "accuracy": total_tp / (total_tp + total_fp + total_fn) if (total_tp + total_fp + total_fn) > 0 else 0
            },
            "individual_video_results": {
                video_id: {
                    "filename": result.video_filename,
                    "status": result.status.value,
                    "metrics": {
                        "precision": result.precision,
                        "recall": result.recall,
                        "f1_score": result.f1_score,
                        "total_detections": result.total_detections
                    },
                    "processing_duration": result.processing_duration,
                    "error_message": result.error_message
                }
                for video_id, result in video_results.items()
            },
            "error_log": workflow_data["error_log"],
            "generated_at": datetime.utcnow().isoformat()
        }
        
        # Save final report
        reports_dir = Path("reports/final_reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_path = reports_dir / f"enhanced_test_workflow_{workflow_id}_final_report.json"
        with open(report_path, 'w') as f:
            json.dump(final_report, f, indent=2, default=str)
        
        logger.info(f"Generated final workflow report: {report_path}")
        return final_report
    
    async def _load_project_videos(self, project_id: str) -> List[Video]:
        """Load all videos for the project"""
        db = SessionLocal()
        try:
            videos = db.query(Video).filter(
                Video.project_id == project_id,
                Video.status != "deleted"
            ).all()
            return videos
        finally:
            db.close()
    
    async def _update_workflow_status(
        self, 
        workflow_id: str, 
        status: WorkflowStatus,
        message: str = None
    ):
        """Update workflow status and emit WebSocket event"""
        if workflow_id not in self.active_workflows:
            return
            
        workflow_data = self.active_workflows[workflow_id]
        workflow_data["status"] = status
        
        # Emit WebSocket update
        update_data = {
            "workflow_id": workflow_id,
            "status": status.value,
            "message": message,
            "progress": workflow_data["progress"].__dict__,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await realtime_service.ws_manager.send_json_to_room(
            update_data,
            f"workflow_{workflow_id}"
        )
        
        # Also emit to Socket.IO for broader compatibility
        await sio.emit(
            "workflow_status_update",
            update_data,
            room=f"workflow_{workflow_id}"
        )
    
    async def _emit_progress_update(self, workflow_id: str):
        """Emit progress update via WebSocket"""
        if workflow_id not in self.active_workflows:
            return
            
        workflow_data = self.active_workflows[workflow_id]
        
        progress_data = {
            "workflow_id": workflow_id,
            "type": "progress_update",
            "progress": workflow_data["progress"].__dict__,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await realtime_service.ws_manager.send_json_to_room(
            progress_data,
            f"workflow_{workflow_id}"
        )
        
        await sio.emit(
            "workflow_progress",
            progress_data,
            room=f"workflow_{workflow_id}"
        )
    
    async def _emit_video_progress_update(
        self, 
        workflow_id: str, 
        video_id: str,
        progress_percentage: float,
        message: str
    ):
        """Emit video-specific progress update"""
        if workflow_id not in self.active_workflows:
            return
            
        # Update workflow progress
        workflow_data = self.active_workflows[workflow_id]
        workflow_data["progress"].current_video_progress = progress_percentage
        
        video_progress_data = {
            "workflow_id": workflow_id,
            "video_id": video_id,
            "type": "video_progress",
            "progress_percentage": progress_percentage,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await realtime_service.ws_manager.send_json_to_room(
            video_progress_data,
            f"workflow_{workflow_id}"
        )
        
        await sio.emit(
            "video_progress",
            video_progress_data,
            room=f"workflow_{workflow_id}"
        )
    
    async def _handle_workflow_error(self, workflow_id: str, error: Exception):
        """Handle workflow errors"""
        if workflow_id not in self.active_workflows:
            return
            
        workflow_data = self.active_workflows[workflow_id]
        workflow_data["status"] = WorkflowStatus.FAILED
        workflow_data["end_time"] = datetime.utcnow()
        workflow_data["error"] = str(error)
        
        error_data = {
            "workflow_id": workflow_id,
            "type": "workflow_error",
            "error_message": str(error),
            "error_type": type(error).__name__,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await realtime_service.ws_manager.send_json_to_room(
            error_data,
            f"workflow_{workflow_id}"
        )
        
        await sio.emit(
            "workflow_error",
            error_data,
            room=f"workflow_{workflow_id}"
        )
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """Get current workflow status"""
        if workflow_id not in self.active_workflows:
            return None
            
        workflow_data = self.active_workflows[workflow_id]
        return {
            "workflow_id": workflow_id,
            "status": workflow_data["status"].value,
            "progress": workflow_data["progress"].__dict__,
            "start_time": workflow_data["start_time"].isoformat(),
            "video_count": len(workflow_data["video_results"]),
            "current_video": workflow_data["progress"].current_video,
            "error_count": len(workflow_data["error_log"])
        }
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel an active workflow"""
        if workflow_id not in self.active_workflows:
            return False
            
        self.active_workflows[workflow_id]["status"] = WorkflowStatus.CANCELLED
        logger.info(f"Cancelled workflow: {workflow_id}")
        return True
    
    def list_active_workflows(self) -> List[Dict]:
        """List all active workflows"""
        return [
            {
                "workflow_id": workflow_id,
                "status": data["status"].value,
                "start_time": data["start_time"].isoformat(),
                "project_id": data["config"].project_id
            }
            for workflow_id, data in self.active_workflows.items()
        ]

# Global orchestrator instance
enhanced_test_orchestrator = EnhancedTestWorkflowOrchestrator()