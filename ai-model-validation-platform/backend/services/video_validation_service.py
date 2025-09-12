"""
Video Validation Service

Comprehensive service for managing video validation workflows, status transitions,
and HIL testing readiness. Implements both automatic and manual validation logic.
"""

import asyncio
import uuid
import os
import tempfile
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from models import (
    Video, VideoValidationCriteria, VideoValidationResult, 
    VideoStatusTransition, GroundTruthObject
)
from schemas_video_validation import (
    VideoValidationStatus, ValidationStatus, ValidationType, ValidationResultType
)

class VideoValidationService:
    """Service for video validation operations"""
    
    # Supported video formats
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv'}
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    # Status transition rules
    AUTOMATIC_TRANSITIONS = {
        VideoValidationStatus.UPLOADED: [VideoValidationStatus.PROCESSING, VideoValidationStatus.ERROR],
        VideoValidationStatus.PROCESSING: [VideoValidationStatus.ANNOTATED, VideoValidationStatus.PROCESSING_FAILED],
        VideoValidationStatus.ANNOTATED: [VideoValidationStatus.VALIDATING, VideoValidationStatus.ERROR],
        VideoValidationStatus.VALIDATING: [VideoValidationStatus.VALIDATED, VideoValidationStatus.VALIDATION_FAILED],
        VideoValidationStatus.VALIDATED: [VideoValidationStatus.READY_FOR_TESTING],
        VideoValidationStatus.READY_FOR_TESTING: [VideoValidationStatus.IN_TESTING],
        VideoValidationStatus.IN_TESTING: [VideoValidationStatus.TESTED, VideoValidationStatus.READY_FOR_TESTING],
        VideoValidationStatus.TESTED: [VideoValidationStatus.ARCHIVED, VideoValidationStatus.READY_FOR_TESTING],
        VideoValidationStatus.PROCESSING_FAILED: [VideoValidationStatus.PROCESSING, VideoValidationStatus.ERROR],
        VideoValidationStatus.VALIDATION_FAILED: [VideoValidationStatus.VALIDATING, VideoValidationStatus.ERROR],
    }
    
    MANUAL_TRANSITIONS = {
        VideoValidationStatus.ANNOTATED: [VideoValidationStatus.VALIDATED],  # Skip automatic validation
        VideoValidationStatus.VALIDATION_FAILED: [VideoValidationStatus.VALIDATED],  # Manual override
        VideoValidationStatus.VALIDATED: [VideoValidationStatus.ANNOTATED],  # Revert for re-annotation
        VideoValidationStatus.READY_FOR_TESTING: [VideoValidationStatus.VALIDATED],  # Revert approval
        VideoValidationStatus.TESTED: [VideoValidationStatus.READY_FOR_TESTING],  # Re-use for testing
        # Admin actions
        "ANY": [VideoValidationStatus.ERROR, VideoValidationStatus.ARCHIVED],
    }
    
    def __init__(self):
        self.validation_queue = asyncio.Queue()
        
    async def transition_video_status(
        self, 
        video_id: str, 
        new_status: VideoValidationStatus,
        reason: str,
        triggered_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> Video:
        """
        Transition video to new status with validation rules
        
        Args:
            video_id: Video ID to transition
            new_status: Target status
            reason: Reason for transition
            triggered_by: User ID or 'system'
            metadata: Additional context data
            db: Database session
            
        Returns:
            Updated video object
            
        Raises:
            ValueError: If transition is not allowed
        """
        
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")
        
        current_status = VideoValidationStatus(video.status)
        
        # Check if transition is allowed
        if not self._is_transition_allowed(current_status, new_status):
            raise ValueError(
                f"Transition from {current_status} to {new_status} is not allowed"
            )
        
        # Record transition
        transition = VideoStatusTransition(
            id=str(uuid.uuid4()),
            video_id=video_id,
            from_status=current_status,
            to_status=new_status,
            transition_reason=reason,
            triggered_by=triggered_by or "system",
            metadata=metadata or {}
        )
        
        # Update video status
        old_status = video.status
        video.status = new_status
        
        # Update validation status based on new status
        video.validation_status = self._map_to_validation_status(new_status)
        
        # Handle status-specific logic
        await self._handle_status_transition_logic(video, current_status, new_status, triggered_by, db)
        
        # Save changes
        db.add(transition)
        db.commit()
        db.refresh(video)
        
        return video
    
    def _is_transition_allowed(
        self, 
        from_status: VideoValidationStatus, 
        to_status: VideoValidationStatus
    ) -> bool:
        """Check if status transition is allowed"""
        
        # Check automatic transitions
        if from_status in self.AUTOMATIC_TRANSITIONS:
            if to_status in self.AUTOMATIC_TRANSITIONS[from_status]:
                return True
        
        # Check manual transitions
        if from_status in self.MANUAL_TRANSITIONS:
            if to_status in self.MANUAL_TRANSITIONS[from_status]:
                return True
        
        # Check admin override transitions
        if to_status in self.MANUAL_TRANSITIONS.get("ANY", []):
            return True
        
        return False
    
    def _map_to_validation_status(self, video_status: VideoValidationStatus) -> str:
        """Map video status to validation status"""
        
        mapping = {
            VideoValidationStatus.UPLOADED: "pending",
            VideoValidationStatus.PROCESSING: "processing",
            VideoValidationStatus.PROCESSING_FAILED: "failed",
            VideoValidationStatus.ANNOTATED: "pending_validation",
            VideoValidationStatus.VALIDATING: "validating",
            VideoValidationStatus.VALIDATION_FAILED: "failed",
            VideoValidationStatus.VALIDATED: "validated",
            VideoValidationStatus.READY_FOR_TESTING: "validated",
            VideoValidationStatus.IN_TESTING: "validated",
            VideoValidationStatus.TESTED: "validated",
            VideoValidationStatus.ARCHIVED: "validated",
            VideoValidationStatus.ERROR: "failed"
        }
        
        return mapping.get(video_status, "pending")
    
    async def _handle_status_transition_logic(
        self,
        video: Video,
        from_status: VideoValidationStatus,
        to_status: VideoValidationStatus,
        triggered_by: Optional[str],
        db: Session
    ):
        """Handle business logic for specific status transitions"""
        
        now = datetime.utcnow()
        
        if to_status == VideoValidationStatus.PROCESSING:
            # Starting ground truth processing
            video.ground_truth_completed_at = None
            
        elif to_status == VideoValidationStatus.ANNOTATED:
            # Ground truth processing completed
            video.ground_truth_generated = True
            video.ground_truth_completed_at = now
            
            # Count ground truth objects
            gt_count = db.query(GroundTruthObject)\
                .filter(GroundTruthObject.video_id == video.id)\
                .count()
            video.ground_truth_count = gt_count
            
            # Calculate quality score based on ground truth
            video.ground_truth_quality_score = await self._calculate_ground_truth_quality(video.id, db)
            
        elif to_status == VideoValidationStatus.VALIDATED:
            # Validation completed successfully
            video.validated_at = now
            video.validated_by = triggered_by
            video.validation_type = "automatic"  # Can be overridden by manual validation
            
        elif to_status == VideoValidationStatus.READY_FOR_TESTING:
            # Approved for HIL testing
            if not video.hil_testing_ready:
                video.hil_testing_ready = True
                video.hil_testing_approved_at = now
                video.hil_testing_approved_by = triggered_by
                
        elif to_status in [VideoValidationStatus.PROCESSING_FAILED, VideoValidationStatus.VALIDATION_FAILED]:
            # Failed states - clear success timestamps
            video.validated_at = None
            video.validated_by = None
            video.hil_testing_ready = False
    
    async def _calculate_ground_truth_quality(self, video_id: str, db: Session) -> float:
        """Calculate ground truth quality score"""
        
        # Get ground truth objects for the video
        gt_objects = db.query(GroundTruthObject)\
            .filter(GroundTruthObject.video_id == video_id)\
            .all()
        
        if not gt_objects:
            return 0.0
        
        # Calculate quality metrics
        total_detections = len(gt_objects)
        avg_confidence = sum(obj.confidence or 0.5 for obj in gt_objects) / total_detections
        
        # VRU type diversity score
        unique_vru_types = len(set(obj.class_label for obj in gt_objects))
        diversity_score = min(unique_vru_types / 3.0, 1.0)  # Normalize to 3 types
        
        # Temporal coverage score (simplified)
        if gt_objects:
            timestamps = [obj.timestamp for obj in gt_objects]
            temporal_coverage = (max(timestamps) - min(timestamps)) / max(timestamps) if max(timestamps) > 0 else 0.5
        else:
            temporal_coverage = 0.0
        
        # Combine metrics (weighted average)
        quality_score = (
            avg_confidence * 0.4 +
            diversity_score * 0.3 +
            temporal_coverage * 0.3
        )
        
        return min(quality_score, 1.0)
    
    async def run_automatic_validation(
        self, 
        video_id: str, 
        criteria_id: Optional[str] = None,
        db: Session = None
    ) -> VideoValidationResult:
        """
        Run automatic validation for a video
        
        Args:
            video_id: Video to validate
            criteria_id: Validation criteria to use (None = default)
            db: Database session
            
        Returns:
            Validation result object
        """
        
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")
        
        # Get validation criteria
        if criteria_id:
            criteria = db.query(VideoValidationCriteria)\
                .filter(VideoValidationCriteria.id == criteria_id)\
                .first()
        else:
            # Use project-specific or global default criteria
            criteria = db.query(VideoValidationCriteria)\
                .filter(
                    or_(
                        VideoValidationCriteria.project_id == video.project_id,
                        VideoValidationCriteria.project_id.is_(None)
                    )
                )\
                .order_by(
                    VideoValidationCriteria.project_id.desc().nulls_last(),
                    VideoValidationCriteria.created_at.desc()
                )\
                .first()
        
        if not criteria:
            raise ValueError("No validation criteria found")
        
        try:
            # Run validation checks
            validation_results = await self._execute_automatic_validation_checks(video, criteria, db)
            
            # Create validation result record
            result = VideoValidationResult(
                id=str(uuid.uuid4()),
                video_id=video_id,
                validation_criteria_id=criteria.id,
                validation_type="automatic",
                overall_result=validation_results["overall_result"],
                ground_truth_score=validation_results["ground_truth_score"],
                technical_score=validation_results["technical_score"],
                content_score=validation_results["content_score"],
                overall_score=validation_results["overall_score"],
                criteria_met=validation_results["criteria_met"],
                validation_notes=validation_results["notes"],
                validated_by="system"
            )
            
            db.add(result)
            
            # Update video status based on validation result
            if validation_results["overall_result"] == "passed":
                await self.transition_video_status(
                    video_id=video_id,
                    new_status=VideoValidationStatus.VALIDATED,
                    reason="automatic_validation_passed",
                    triggered_by="system",
                    metadata={"validation_score": validation_results["overall_score"]},
                    db=db
                )
            else:
                await self.transition_video_status(
                    video_id=video_id,
                    new_status=VideoValidationStatus.VALIDATION_FAILED,
                    reason="automatic_validation_failed",
                    triggered_by="system",
                    metadata={"validation_score": validation_results["overall_score"]},
                    db=db
                )
            
            db.commit()
            db.refresh(result)
            return result
            
        except Exception as e:
            # Mark validation as failed
            await self.transition_video_status(
                video_id=video_id,
                new_status=VideoValidationStatus.VALIDATION_FAILED,
                reason="automatic_validation_error",
                triggered_by="system",
                metadata={"error": str(e)},
                db=db
            )
            raise
    
    async def _execute_automatic_validation_checks(
        self, 
        video: Video, 
        criteria: VideoValidationCriteria,
        db: Session
    ) -> Dict[str, Any]:
        """Execute automatic validation checks"""
        
        results = {
            "overall_result": "failed",
            "ground_truth_score": 0.0,
            "technical_score": 0.0,
            "content_score": 0.0,
            "overall_score": 0.0,
            "criteria_met": {},
            "notes": []
        }
        
        # Ground Truth Quality Checks
        gt_score, gt_criteria = await self._validate_ground_truth_quality(video, criteria, db)
        results["ground_truth_score"] = gt_score
        results["criteria_met"].update(gt_criteria)
        
        # Technical Quality Checks
        tech_score, tech_criteria = await self._validate_technical_quality(video, criteria)
        results["technical_score"] = tech_score
        results["criteria_met"].update(tech_criteria)
        
        # Content Quality Checks
        content_score, content_criteria = await self._validate_content_quality(video, criteria, db)
        results["content_score"] = content_score
        results["criteria_met"].update(content_criteria)
        
        # Calculate overall score (weighted average)
        overall_score = (gt_score * 0.4 + tech_score * 0.3 + content_score * 0.3)
        results["overall_score"] = overall_score
        
        # Determine pass/fail (all criteria must pass)
        all_criteria_passed = all(results["criteria_met"].values())
        results["overall_result"] = "passed" if all_criteria_passed and overall_score >= 0.7 else "failed"
        
        # Generate validation notes
        failed_criteria = [k for k, v in results["criteria_met"].items() if not v]
        if failed_criteria:
            results["notes"].append(f"Failed criteria: {', '.join(failed_criteria)}")
        
        results["notes"] = "; ".join(results["notes"])
        
        return results
    
    async def _validate_ground_truth_quality(
        self, 
        video: Video, 
        criteria: VideoValidationCriteria,
        db: Session
    ) -> Tuple[float, Dict[str, bool]]:
        """Validate ground truth quality"""
        
        score = 0.0
        criteria_met = {}
        
        # Check minimum detection count
        gt_count = video.ground_truth_count or 0
        min_detections_met = gt_count >= criteria.min_detection_count
        criteria_met["min_detection_count"] = min_detections_met
        if min_detections_met:
            score += 0.3
        
        # Check confidence threshold
        if gt_count > 0:
            gt_objects = db.query(GroundTruthObject)\
                .filter(GroundTruthObject.video_id == video.id)\
                .all()
            
            high_confidence_count = sum(
                1 for obj in gt_objects 
                if (obj.confidence or 0.0) >= criteria.min_confidence_threshold
            )
            confidence_ratio = high_confidence_count / gt_count
            confidence_met = confidence_ratio >= 0.8  # 80% must meet confidence threshold
            criteria_met["confidence_threshold"] = confidence_met
            if confidence_met:
                score += 0.3
        else:
            criteria_met["confidence_threshold"] = False
        
        # Check frame coverage (simplified - based on temporal spread)
        if gt_count > 0:
            # Assume good temporal distribution if we have enough detections
            frame_coverage_met = gt_count >= criteria.min_detection_count * 2
            criteria_met["frame_coverage"] = frame_coverage_met
            if frame_coverage_met:
                score += 0.4
        else:
            criteria_met["frame_coverage"] = False
        
        return score, criteria_met
    
    async def _validate_technical_quality(
        self, 
        video: Video, 
        criteria: VideoValidationCriteria
    ) -> Tuple[float, Dict[str, bool]]:
        """Validate technical video quality"""
        
        score = 0.0
        criteria_met = {}
        
        # Check duration
        duration_valid = (
            video.duration and 
            criteria.min_duration_seconds <= video.duration <= criteria.max_duration_seconds
        )
        criteria_met["duration_valid"] = duration_valid
        if duration_valid:
            score += 0.3
        
        # Check FPS
        fps_valid = video.fps and video.fps >= criteria.min_fps
        criteria_met["fps_valid"] = fps_valid
        if fps_valid:
            score += 0.3
        
        # Check resolution (simplified)
        resolution_valid = bool(video.resolution)  # More sophisticated check needed
        criteria_met["resolution_valid"] = resolution_valid
        if resolution_valid:
            score += 0.4
        
        return score, criteria_met
    
    async def _validate_content_quality(
        self, 
        video: Video, 
        criteria: VideoValidationCriteria,
        db: Session
    ) -> Tuple[float, Dict[str, bool]]:
        """Validate video content quality"""
        
        score = 0.5  # Base score for having content
        criteria_met = {}
        
        # Check VRU type requirements
        if criteria.required_vru_types:
            gt_objects = db.query(GroundTruthObject)\
                .filter(GroundTruthObject.video_id == video.id)\
                .all()
            
            detected_vru_types = set(obj.class_label for obj in gt_objects)
            required_types = set(criteria.required_vru_types)
            
            vru_types_met = required_types.issubset(detected_vru_types)
            criteria_met["required_vru_types"] = vru_types_met
            if vru_types_met:
                score += 0.3
        else:
            criteria_met["required_vru_types"] = True
            score += 0.3
        
        # Scene complexity (simplified)
        scene_complexity_met = (video.ground_truth_quality_score or 0.0) >= criteria.min_scene_complexity_score
        criteria_met["scene_complexity"] = scene_complexity_met
        if scene_complexity_met:
            score += 0.2
        
        return score, criteria_met
    
    async def initiate_manual_validation(
        self,
        video_id: str,
        validated_by: str,
        criteria_id: Optional[str] = None,
        notes: Optional[str] = None,
        db: Session = None
    ) -> VideoValidationResult:
        """Initiate manual validation workflow"""
        
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")
        
        # Transition to validating status
        await self.transition_video_status(
            video_id=video_id,
            new_status=VideoValidationStatus.VALIDATING,
            reason="manual_validation_started",
            triggered_by=validated_by,
            db=db
        )
        
        # Create pending validation result
        result = VideoValidationResult(
            id=str(uuid.uuid4()),
            video_id=video_id,
            validation_criteria_id=criteria_id,
            validation_type="manual",
            overall_result="processing",
            validation_notes=notes or "Manual validation initiated",
            validated_by=validated_by
        )
        
        db.add(result)
        db.commit()
        db.refresh(result)
        
        return result
    
    async def complete_manual_validation(
        self,
        video_id: str,
        validation_result: ValidationResultType,
        validated_by: str,
        criteria_id: Optional[str] = None,
        notes: Optional[str] = None,
        scores: Optional[Dict[str, float]] = None,
        db: Session = None
    ) -> VideoValidationResult:
        """Complete manual validation with user input"""
        
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found")
        
        # Create or update validation result
        result = db.query(VideoValidationResult)\
            .filter(VideoValidationResult.video_id == video_id)\
            .filter(VideoValidationResult.validation_type == "manual")\
            .order_by(VideoValidationResult.created_at.desc())\
            .first()
        
        if not result:
            result = VideoValidationResult(
                id=str(uuid.uuid4()),
                video_id=video_id,
                validation_criteria_id=criteria_id,
                validation_type="manual",
                validated_by=validated_by
            )
            db.add(result)
        
        # Update result
        result.overall_result = validation_result
        result.validation_notes = notes
        result.validated_by = validated_by
        
        if scores:
            result.ground_truth_score = scores.get("ground_truth_score")
            result.technical_score = scores.get("technical_score")
            result.content_score = scores.get("content_score")
            result.overall_score = scores.get("overall_score")
        
        # Update video status
        if validation_result == ValidationResultType.PASSED:
            video.validation_type = "manual"
            await self.transition_video_status(
                video_id=video_id,
                new_status=VideoValidationStatus.VALIDATED,
                reason="manual_validation_passed",
                triggered_by=validated_by,
                db=db
            )
        else:
            await self.transition_video_status(
                video_id=video_id,
                new_status=VideoValidationStatus.VALIDATION_FAILED,
                reason="manual_validation_failed",
                triggered_by=validated_by,
                db=db
            )
        
        db.commit()
        db.refresh(result)
        
        return result
    
    async def batch_automatic_validation(
        self,
        video_ids: List[str],
        criteria_id: Optional[str] = None,
        triggered_by: Optional[str] = None,
        db: Session = None
    ):
        """Run automatic validation for multiple videos"""
        
        for video_id in video_ids:
            try:
                await self.run_automatic_validation(video_id, criteria_id, db)
            except Exception as e:
                # Log error but continue with other videos
                print(f"Batch validation failed for video {video_id}: {str(e)}")
                continue
    
    def get_validation_statistics(self, db: Session) -> Dict[str, Any]:
        """Get validation statistics"""
        
        # Count videos by status
        status_counts = db.query(Video.status, func.count(Video.id))\
            .group_by(Video.status)\
            .all()
        
        # Count by validation type
        validation_type_counts = db.query(Video.validation_type, func.count(Video.id))\
            .filter(Video.validation_type.isnot(None))\
            .group_by(Video.validation_type)\
            .all()
        
        # Success rate
        total_validated = db.query(Video)\
            .filter(Video.status.in_(["validated", "ready_for_testing", "tested"]))\
            .count()
        total_attempted = db.query(Video)\
            .filter(Video.status.in_(["validated", "ready_for_testing", "tested", "validation_failed"]))\
            .count()
        
        success_rate = (total_validated / total_attempted * 100) if total_attempted > 0 else 0.0
        
        return {
            "total_videos": db.query(Video).count(),
            "by_status": dict(status_counts),
            "by_validation_type": dict(validation_type_counts),
            "success_rate_percent": success_rate,
            "hil_ready_count": db.query(Video).filter(Video.hil_testing_ready == True).count()
        }
    
    def validate_upload_file(self, file, filename: str) -> Dict[str, Any]:
        """Validate uploaded file before processing"""
        try:
            # Extract file extension
            file_extension = Path(filename).suffix.lower()
            
            # Validate file extension
            if file_extension not in self.SUPPORTED_FORMATS:
                return {
                    "valid": False,
                    "errors": [f"Unsupported file format: {file_extension}. Supported formats: {', '.join(self.SUPPORTED_FORMATS)}"],
                    "file_extension": file_extension,
                    "secure_filename": None
                }
            
            # Generate secure filename
            secure_filename = self._generate_secure_filename(filename)
            
            return {
                "valid": True,
                "errors": [],
                "file_extension": file_extension,
                "secure_filename": secure_filename
            }
            
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"File validation error: {str(e)}"],
                "file_extension": None,
                "secure_filename": None
            }
    
    def create_temp_file_safely(self, file_extension: str, upload_dir: str) -> Tuple[str, str]:
        """Create temporary file paths safely"""
        try:
            # Generate unique filename
            unique_id = str(uuid.uuid4())
            temp_filename = f"temp_{unique_id}{file_extension}"
            final_filename = f"video_{unique_id}{file_extension}"
            
            temp_file_path = os.path.join(upload_dir, temp_filename)
            final_file_path = os.path.join(upload_dir, final_filename)
            
            return temp_file_path, final_file_path
            
        except Exception as e:
            raise ValueError(f"Failed to create safe file paths: {str(e)}")
    
    def validate_video_file(self, file_path: str) -> Dict[str, Any]:
        """Validate video file structure and properties"""
        try:
            file_path_obj = Path(file_path)
            
            # Check if file exists
            if not file_path_obj.exists():
                return {
                    "valid": False,
                    "errors": ["File does not exist"]
                }
            
            # Check file extension
            if file_path_obj.suffix.lower() not in self.SUPPORTED_FORMATS:
                return {
                    "valid": False,
                    "errors": [f"Unsupported format: {file_path_obj.suffix}"]
                }
            
            # Check file size
            file_size = file_path_obj.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                return {
                    "valid": False,
                    "errors": [f"File size exceeds limit: {file_size} bytes > {self.MAX_FILE_SIZE} bytes"]
                }
            
            if file_size < 1024:  # Less than 1KB
                return {
                    "valid": False,
                    "errors": ["File too small to be a valid video"]
                }
            
            # Try to validate with OpenCV if available
            try:
                import cv2
                cap = cv2.VideoCapture(str(file_path))
                if not cap.isOpened():
                    return {
                        "valid": False,
                        "errors": ["Cannot open video file - corrupted or invalid format"]
                    }
                
                # Get basic properties
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                
                cap.release()
                
                errors = []
                
                # Check resolution (minimum 640x480)
                if width < 640 or height < 480:
                    errors.append(f"Resolution too low: {width}x{height} (minimum 640x480)")
                
                # Check frame rate (5-120 FPS)
                if fps < 5 or fps > 120:
                    errors.append(f"Invalid frame rate: {fps} FPS (must be 5-120)")
                
                # Check duration (maximum 60 minutes)
                duration = frame_count / fps if fps > 0 else 0
                if duration > 3600:  # 60 minutes
                    errors.append("Video too long (maximum 60 minutes)")
                
                return {
                    "valid": len(errors) == 0,
                    "errors": errors,
                    "metadata": {
                        "duration": duration,
                        "fps": fps,
                        "resolution": (width, height),
                        "frame_count": frame_count
                    }
                }
                
            except ImportError:
                # OpenCV not available - basic validation only
                return {
                    "valid": True,
                    "errors": [],
                    "metadata": {
                        "duration": None,
                        "fps": None,
                        "resolution": None,
                        "frame_count": None
                    }
                }
                
        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def _generate_secure_filename(self, filename: str) -> str:
        """Generate a secure filename"""
        # Remove path separators and dangerous characters
        safe_name = re.sub(r'[^\w\-_.]', '_', filename)
        
        # Remove multiple dots (except the extension)
        name_parts = safe_name.split('.')
        if len(name_parts) > 2:
            # Keep only the last extension
            safe_name = '_'.join(name_parts[:-1]) + '.' + name_parts[-1]
        
        # Add timestamp to ensure uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_without_ext = Path(safe_name).stem
        extension = Path(safe_name).suffix
        
        return f"{name_without_ext}_{timestamp}{extension}"
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """Clean up temporary files after upload processing"""
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"✅ Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            print(f"⚠️  Failed to cleanup temporary file {temp_file_path}: {e}")