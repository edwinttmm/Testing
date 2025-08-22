"""
Real Test Execution Service
Performs actual AI model validation against ground truth data
"""
import asyncio
import logging
import time
import uuid
from typing import List, Dict, Optional, AsyncGenerator, Tuple, Any
from dataclasses import dataclass
from sqlalchemy.orm import Session
from pathlib import Path

from database import SessionLocal
from models import TestSession, Video, DetectionEvent, GroundTruthObject
from services.detection_pipeline_service import DetectionPipeline, Detection, DetectionResult
from schemas import ValidationResult, ValidationMetrics

logger = logging.getLogger(__name__)

@dataclass
class TestExecutionConfig:
    """Configuration for test execution"""
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.5
    max_videos_per_test: int = 100
    batch_size: int = 8
    enable_detailed_logging: bool = True

@dataclass
class ValidationMetricsCalculator:
    """Calculate validation metrics from detection results"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset all counters"""
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0
        self.true_negatives = 0
        self.total_detections = 0
        self.total_ground_truth = 0
        
        # Per-class metrics
        self.class_metrics = {}
    
    def calculate_iou(self, detection_box, ground_truth_box) -> float:
        """Calculate Intersection over Union (IoU) between two bounding boxes"""
        # Convert to x1, y1, x2, y2 format
        d_x1, d_y1 = detection_box.x, detection_box.y
        d_x2, d_y2 = d_x1 + detection_box.width, d_y1 + detection_box.height
        
        gt_x1, gt_y1 = ground_truth_box['x'], ground_truth_box['y']
        gt_x2, gt_y2 = gt_x1 + ground_truth_box['width'], gt_y1 + ground_truth_box['height']
        
        # Calculate intersection
        inter_x1 = max(d_x1, gt_x1)
        inter_y1 = max(d_y1, gt_y1)
        inter_x2 = min(d_x2, gt_x2)
        inter_y2 = min(d_y2, gt_y2)
        
        if inter_x1 >= inter_x2 or inter_y1 >= inter_y2:
            return 0.0
        
        intersection = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        
        # Calculate union
        d_area = detection_box.width * detection_box.height
        gt_area = ground_truth_box['width'] * ground_truth_box['height']
        union = d_area + gt_area - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def add_frame_results(self, detections: List[Detection], ground_truths: List[Dict], 
                         iou_threshold: float = 0.5):
        """Add results from a single frame"""
        self.total_detections += len(detections)
        self.total_ground_truth += len(ground_truths)
        
        # Track which ground truth objects have been matched
        matched_gt = set()
        
        for detection in detections:
            best_iou = 0.0
            best_gt_idx = -1
            
            # Find best matching ground truth object
            for gt_idx, gt in enumerate(ground_truths):
                if gt_idx in matched_gt:
                    continue
                
                # Check class match
                if detection.class_label != gt['class_label']:
                    continue
                
                # Calculate IoU
                iou = self.calculate_iou(detection.bounding_box, gt)
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = gt_idx
            
            # Classify detection
            if best_iou >= iou_threshold and best_gt_idx >= 0:
                self.true_positives += 1
                matched_gt.add(best_gt_idx)
            else:
                self.false_positives += 1
        
        # Count false negatives (unmatched ground truth)
        self.false_negatives += len(ground_truths) - len(matched_gt)
    
    def get_metrics(self) -> Dict[str, float]:
        """Calculate final metrics"""
        precision = self.true_positives / (self.true_positives + self.false_positives) if (self.true_positives + self.false_positives) > 0 else 0.0
        recall = self.true_positives / (self.true_positives + self.false_negatives) if (self.true_positives + self.false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = (self.true_positives + self.true_negatives) / (self.true_positives + self.false_positives + self.false_negatives + self.true_negatives) if (self.true_positives + self.false_positives + self.false_negatives + self.true_negatives) > 0 else 0.0
        
        return {
            "precision": precision * 100,
            "recall": recall * 100,
            "f1_score": f1_score * 100,
            "accuracy": accuracy * 100,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "total_detections": self.total_detections,
            "total_ground_truth": self.total_ground_truth
        }

class TestExecutionService:
    """Service for executing real AI model validation tests"""
    
    def __init__(self):
        self.detection_pipeline = DetectionPipeline()
        self.config = TestExecutionConfig()
        self.active_sessions = {}  # Track active test sessions
    
    async def initialize(self):
        """Initialize the service"""
        await self.detection_pipeline.initialize()
        logger.info("Test execution service initialized")
    
    async def execute_test_session(self, project_id: str, test_config: Dict = None) -> str:
        """Execute a complete test session for a project"""
        try:
            # Create test session
            db = SessionLocal()
            test_session = TestSession(
                id=str(uuid.uuid4()),
                project_id=project_id,
                status="running",
                name=f"Test Session {time.strftime('%Y-%m-%d %H:%M:%S')}",
                description="AI model validation test"
            )
            db.add(test_session)
            db.commit()
            db.refresh(test_session)
            
            session_id = test_session.id
            self.active_sessions[session_id] = {
                "status": "running",
                "progress": 0,
                "videos_processed": 0,
                "total_videos": 0
            }
            
            # Run test in background
            asyncio.create_task(self._execute_test_background(session_id, project_id, test_config or {}))
            
            logger.info(f"Started test session {session_id} for project {project_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start test session: {str(e)}")
            raise
        finally:
            db.close()
    
    async def _execute_test_background(self, session_id: str, project_id: str, test_config: Dict):
        """Execute test session in background"""
        db = SessionLocal()
        try:
            # Get linked videos for the project
            videos = db.query(Video).filter(
                Video.project_id == project_id,
                Video.ground_truth_generated == True,
                Video.status == 'completed'
            ).limit(self.config.max_videos_per_test).all()
            
            if not videos:
                raise ValueError("No videos with ground truth found for testing")
            
            self.active_sessions[session_id]["total_videos"] = len(videos)
            
            # Initialize metrics calculator
            metrics_calc = ValidationMetricsCalculator()
            
            # Process each video
            for i, video in enumerate(videos):
                try:
                    await self._process_video_for_test(session_id, video, metrics_calc)
                    self.active_sessions[session_id]["videos_processed"] = i + 1
                    self.active_sessions[session_id]["progress"] = ((i + 1) / len(videos)) * 100
                    
                except Exception as e:
                    logger.error(f"Error processing video {video.id}: {str(e)}")
                    continue
            
            # Calculate final metrics
            final_metrics = metrics_calc.get_metrics()
            
            # Save results to database
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if test_session:
                test_session.status = "completed"
                test_session.completed_at = time.time()
                test_session.metrics = final_metrics
                db.commit()
            
            # Update session status
            self.active_sessions[session_id]["status"] = "completed"
            self.active_sessions[session_id]["metrics"] = final_metrics
            
            logger.info(f"Test session {session_id} completed successfully")
            logger.info(f"Final metrics: {final_metrics}")
            
        except Exception as e:
            logger.error(f"Test session {session_id} failed: {str(e)}")
            
            # Mark session as failed
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if test_session:
                test_session.status = "failed"
                test_session.error_message = str(e)
                db.commit()
            
            self.active_sessions[session_id]["status"] = "failed"
            self.active_sessions[session_id]["error"] = str(e)
            
        finally:
            db.close()
    
    async def _process_video_for_test(self, session_id: str, video: Video, metrics_calc: ValidationMetricsCalculator):
        """Process a single video for testing"""
        import cv2
        
        try:
            # Open video file
            cap = cv2.VideoCapture(video.file_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open video file: {video.file_path}")
            
            frame_count = 0
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Get ground truth data
            db = SessionLocal()
            try:
                ground_truth_objects = db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == video.id
                ).all()
                
                # Group by frame number
                gt_by_frame = {}
                for gt in ground_truth_objects:
                    if gt.frame_number not in gt_by_frame:
                        gt_by_frame[gt.frame_number] = []
                    gt_by_frame[gt.frame_number].append({
                        'class_label': gt.class_label,
                        'x': gt.x,
                        'y': gt.y,
                        'width': gt.width,
                        'height': gt.height,
                        'confidence': gt.confidence or 1.0
                    })
                
            finally:
                db.close()
            
            # Process video frames
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                frame_count += 1
                
                # Run AI detection
                try:
                    model = await self.detection_pipeline.model_registry.get_active_model()
                    processed_frame = await self.detection_pipeline.frame_processor.preprocess(frame)
                    detections = await model.predict(processed_frame)
                    
                    # Apply validation and filtering
                    validated_detections = self.detection_pipeline.validate_detections(detections)
                    
                    # Get ground truth for this frame
                    frame_gt = gt_by_frame.get(frame_count, [])
                    
                    # Calculate metrics for this frame
                    metrics_calc.add_frame_results(validated_detections, frame_gt, self.config.iou_threshold)
                    
                    # Store detection events
                    db = SessionLocal()
                    try:
                        for detection in validated_detections:
                            detection_event = DetectionEvent(
                                id=detection.detection_id,
                                test_session_id=session_id,
                                # REMOVED: video_id=video.id,  # ❌ This field does not exist in DetectionEvent model
                                frame_number=frame_count,
                                timestamp=frame_count / fps,
                                confidence=detection.confidence,
                                class_label=detection.class_label,
                                # FIXED: Use correct column names from the model
                                bounding_box_x=detection.bounding_box.x,
                                bounding_box_y=detection.bounding_box.y,
                                bounding_box_width=detection.bounding_box.width,
                                bounding_box_height=detection.bounding_box.height,
                                validation_result="VALIDATED",
                                # Additional fields for better tracking
                                detection_id=detection.detection_id,
                                vru_type=detection.class_label  # Map class_label to vru_type
                            )
                            db.add(detection_event)
                        
                        db.commit()
                    finally:
                        db.close()
                    
                except Exception as e:
                    logger.error(f"Error processing frame {frame_count}: {str(e)}")
                    continue
                
                # Limit processing for performance (every 30th frame)
                if frame_count % 30 != 0:
                    continue
            
            cap.release()
            logger.info(f"Processed {frame_count} frames for video {video.id}")
            
        except Exception as e:
            logger.error(f"Error processing video {video.id}: {str(e)}")
            raise
    
    def get_session_status(self, session_id: str) -> Dict:
        """Get current status of a test session"""
        if session_id not in self.active_sessions:
            # Try to get from database
            db = SessionLocal()
            try:
                test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if test_session:
                    return {
                        "session_id": session_id,
                        "status": test_session.status,
                        "progress": 100 if test_session.status == "completed" else 0,
                        "metrics": test_session.metrics or {},
                        "error": test_session.error_message
                    }
                else:
                    return {"error": "Session not found"}
            finally:
                db.close()
        
        session = self.active_sessions[session_id]
        return {
            "session_id": session_id,
            "status": session["status"],
            "progress": session["progress"],
            "videos_processed": session["videos_processed"],
            "total_videos": session["total_videos"],
            "metrics": session.get("metrics", {}),
            "error": session.get("error")
        }
    
    def get_session_results(self, session_id: str) -> Optional[ValidationResult]:
        """Get final results for a completed test session"""
        db = SessionLocal()
        try:
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                return None
            
            if test_session.status != "completed":
                return None
            
            metrics = test_session.metrics or {}
            
            return ValidationResult(
                session_id=session_id,
                status=test_session.status,
                metrics=ValidationMetrics(
                    accuracy=metrics.get("accuracy", 0.0),
                    precision=metrics.get("precision", 0.0),
                    recall=metrics.get("recall", 0.0),
                    f1Score=metrics.get("f1_score", 0.0),
                    truePositives=metrics.get("true_positives", 0),
                    falsePositives=metrics.get("false_positives", 0),
                    falseNegatives=metrics.get("false_negatives", 0),
                    totalDetections=metrics.get("total_detections", 0),
                    totalGroundTruth=metrics.get("total_ground_truth", 0)
                ),
                completedAt=test_session.completed_at,
                processingTime=0,  # Calculate if needed
                videoCount=metrics.get("total_videos", 0),
                message="Test completed successfully"
            )
            
        finally:
            db.close()

# Global service instance
test_execution_service = TestExecutionService()