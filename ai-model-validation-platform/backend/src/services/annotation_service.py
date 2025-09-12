"""
Annotation Service Layer
SPARC Implementation - Business logic for annotation management
"""

from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from datetime import datetime, timedelta
import uuid
import json
import logging

# Import models and utilities
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from models import (
    Annotation, Video, Project, AnnotationSession, 
    DetectionEvent, GroundTruthObject
)
from src.utils.annotation_validators import (
    AnnotationValidator, GeometricValidator, TemporalValidator,
    BoundingBox, ValidationResult
)

logger = logging.getLogger(__name__)


class AnnotationService:
    """Core annotation service with business logic"""
    
    def __init__(self):
        self.validator = AnnotationValidator()
        self.geometric_validator = GeometricValidator()
        self.temporal_validator = TemporalValidator()
    
    def create_annotation(self, db: Session, annotation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create new annotation with comprehensive validation
        
        Args:
            db: Database session
            annotation_data: Annotation data dictionary
            
        Returns:
            Dictionary with creation result and annotation data
        """
        try:
            # Get video metadata for validation
            video = db.query(Video).filter(Video.id == annotation_data.get("video_id")).first()
            if not video:
                return {
                    "success": False,
                    "error": "Video not found",
                    "code": "VIDEO_NOT_FOUND"
                }
            
            video_metadata = {
                "duration": video.duration,
                "fps": video.fps,
                "resolution": video.resolution
            }
            
            # Validate annotation data
            validation_result = self.validator.validate_annotation(annotation_data, video_metadata)
            
            if not validation_result.is_valid:
                return {
                    "success": False,
                    "error": "Validation failed",
                    "validation_errors": validation_result.errors,
                    "validation_warnings": validation_result.warnings,
                    "code": "VALIDATION_FAILED"
                }
            
            # Generate detection ID if not provided
            if not annotation_data.get("detection_id"):
                annotation_data["detection_id"] = self._generate_detection_id(
                    annotation_data.get("vru_type", "UNKNOWN")
                )
            
            # Create annotation object
            annotation = Annotation(
                id=str(uuid.uuid4()),
                video_id=annotation_data["video_id"],
                detection_id=annotation_data.get("detection_id"),
                frame_number=annotation_data["frame_number"],
                timestamp=annotation_data["timestamp"],
                end_timestamp=annotation_data.get("end_timestamp"),
                vru_type=annotation_data["vru_type"],
                bounding_box=annotation_data["bounding_box"],
                occluded=annotation_data.get("occluded", False),
                truncated=annotation_data.get("truncated", False),
                difficult=annotation_data.get("difficult", False),
                notes=annotation_data.get("notes", ""),
                annotator=annotation_data.get("annotator"),
                validated=annotation_data.get("validated", False)
            )
            
            db.add(annotation)
            db.commit()
            db.refresh(annotation)
            
            logger.info(f"Created annotation {annotation.id} for video {video.id}")
            
            return {
                "success": True,
                "annotation": self._annotation_to_dict(annotation),
                "validation_warnings": validation_result.warnings,
                "validation_metadata": validation_result.metadata
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating annotation: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def get_annotation(self, db: Session, annotation_id: str) -> Optional[Dict[str, Any]]:
        """Get annotation by ID"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return None
            
            return self._annotation_to_dict(annotation)
            
        except Exception as e:
            logger.error(f"Error getting annotation {annotation_id}: {str(e)}")
            return None
    
    def update_annotation(self, db: Session, annotation_id: str, 
                         update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing annotation with validation"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return {
                    "success": False,
                    "error": "Annotation not found",
                    "code": "ANNOTATION_NOT_FOUND"
                }
            
            # Get video metadata for validation
            video = db.query(Video).filter(Video.id == annotation.video_id).first()
            video_metadata = {
                "duration": video.duration,
                "fps": video.fps,
                "resolution": video.resolution
            } if video else {}
            
            # Merge current data with updates
            current_data = self._annotation_to_dict(annotation)
            current_data.update(update_data)
            
            # Validate updated data
            validation_result = self.validator.validate_annotation(current_data, video_metadata)
            
            if not validation_result.is_valid:
                return {
                    "success": False,
                    "error": "Validation failed",
                    "validation_errors": validation_result.errors,
                    "validation_warnings": validation_result.warnings,
                    "code": "VALIDATION_FAILED"
                }
            
            # Update annotation fields
            updatable_fields = [
                "detection_id", "frame_number", "timestamp", "end_timestamp",
                "vru_type", "bounding_box", "occluded", "truncated", "difficult",
                "notes", "annotator", "validated"
            ]
            
            for field in updatable_fields:
                if field in update_data:
                    setattr(annotation, field, update_data[field])
            
            annotation.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(annotation)
            
            logger.info(f"Updated annotation {annotation_id}")
            
            return {
                "success": True,
                "annotation": self._annotation_to_dict(annotation),
                "validation_warnings": validation_result.warnings
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating annotation {annotation_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def delete_annotation(self, db: Session, annotation_id: str) -> Dict[str, Any]:
        """Delete annotation"""
        try:
            annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not annotation:
                return {
                    "success": False,
                    "error": "Annotation not found",
                    "code": "ANNOTATION_NOT_FOUND"
                }
            
            db.delete(annotation)
            db.commit()
            
            logger.info(f"Deleted annotation {annotation_id}")
            
            return {
                "success": True,
                "message": f"Annotation {annotation_id} deleted successfully"
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting annotation {annotation_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def get_video_annotations(self, db: Session, video_id: str, 
                            filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get annotations for a video with optional filtering"""
        try:
            query = db.query(Annotation).filter(Annotation.video_id == video_id)
            
            # Apply filters
            if filters:
                if "vru_type" in filters:
                    query = query.filter(Annotation.vru_type == filters["vru_type"])
                
                if "validated" in filters:
                    query = query.filter(Annotation.validated == filters["validated"])
                
                if "annotator" in filters:
                    query = query.filter(Annotation.annotator == filters["annotator"])
                
                if "frame_range" in filters:
                    start_frame, end_frame = filters["frame_range"]
                    query = query.filter(
                        Annotation.frame_number.between(start_frame, end_frame)
                    )
                
                if "timestamp_range" in filters:
                    start_time, end_time = filters["timestamp_range"]
                    query = query.filter(
                        Annotation.timestamp.between(start_time, end_time)
                    )
                
                if "difficult_only" in filters and filters["difficult_only"]:
                    query = query.filter(Annotation.difficult == True)
                
                if "exclude_validated" in filters and filters["exclude_validated"]:
                    query = query.filter(Annotation.validated == False)
            
            # Order by timestamp
            annotations = query.order_by(Annotation.timestamp).all()
            
            return {
                "success": True,
                "annotations": [self._annotation_to_dict(ann) for ann in annotations],
                "count": len(annotations),
                "filters_applied": filters or {}
            }
            
        except Exception as e:
            logger.error(f"Error getting video annotations {video_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def get_annotation_statistics(self, db: Session, video_id: str) -> Dict[str, Any]:
        """Get comprehensive annotation statistics for a video"""
        try:
            annotations = db.query(Annotation).filter(Annotation.video_id == video_id).all()
            
            if not annotations:
                return {
                    "success": True,
                    "statistics": {
                        "total_annotations": 0,
                        "by_vru_type": {},
                        "validation_status": {"validated": 0, "pending": 0},
                        "quality_metrics": {},
                        "temporal_coverage": {}
                    }
                }
            
            # Basic counts
            total_count = len(annotations)
            vru_type_counts = {}
            validated_count = 0
            difficult_count = 0
            occluded_count = 0
            truncated_count = 0
            
            annotator_stats = {}
            timestamps = []
            
            for ann in annotations:
                # VRU type distribution
                vru_type = ann.vru_type
                vru_type_counts[vru_type] = vru_type_counts.get(vru_type, 0) + 1
                
                # Validation status
                if ann.validated:
                    validated_count += 1
                
                # Quality flags
                if ann.difficult:
                    difficult_count += 1
                if ann.occluded:
                    occluded_count += 1
                if ann.truncated:
                    truncated_count += 1
                
                # Annotator performance
                annotator = ann.annotator or "unknown"
                if annotator not in annotator_stats:
                    annotator_stats[annotator] = {"total": 0, "validated": 0}
                annotator_stats[annotator]["total"] += 1
                if ann.validated:
                    annotator_stats[annotator]["validated"] += 1
                
                timestamps.append(ann.timestamp)
            
            # Temporal coverage
            if timestamps:
                temporal_coverage = {
                    "start_time": min(timestamps),
                    "end_time": max(timestamps),
                    "duration_covered": max(timestamps) - min(timestamps),
                    "annotation_density": total_count / (max(timestamps) - min(timestamps)) if max(timestamps) > min(timestamps) else 0
                }
            else:
                temporal_coverage = {}
            
            # Geometric analysis (if video metadata available)
            video = db.query(Video).filter(Video.id == video_id).first()
            geometric_stats = {}
            
            if video and video.resolution:
                try:
                    width, height = map(int, video.resolution.split("x"))
                    annotation_dicts = [self._annotation_to_dict(ann) for ann in annotations]
                    geometric_stats = self.geometric_validator.validate_annotation_density(
                        annotation_dicts, width, height
                    )
                except Exception as e:
                    logger.warning(f"Could not calculate geometric statistics: {e}")
            
            return {
                "success": True,
                "statistics": {
                    "total_annotations": total_count,
                    "by_vru_type": vru_type_counts,
                    "validation_status": {
                        "validated": validated_count,
                        "pending": total_count - validated_count,
                        "validation_rate": validated_count / total_count if total_count > 0 else 0
                    },
                    "quality_metrics": {
                        "difficult": difficult_count,
                        "occluded": occluded_count,
                        "truncated": truncated_count,
                        "quality_rate": (total_count - difficult_count) / total_count if total_count > 0 else 0
                    },
                    "annotator_performance": annotator_stats,
                    "temporal_coverage": temporal_coverage,
                    "geometric_analysis": geometric_stats
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting annotation statistics {video_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def validate_annotation_sequence(self, db: Session, video_id: str) -> Dict[str, Any]:
        """Validate temporal and geometric consistency of annotation sequence"""
        try:
            annotations = db.query(Annotation).filter(
                Annotation.video_id == video_id
            ).order_by(Annotation.timestamp).all()
            
            if not annotations:
                return {
                    "success": True,
                    "validation": {"status": "no_annotations"}
                }
            
            # Convert to dictionaries for validation
            annotation_dicts = [self._annotation_to_dict(ann) for ann in annotations]
            
            # Temporal validation
            temporal_result = self.temporal_validator.validate_temporal_consistency(annotation_dicts)
            
            # Geometric validation (overlaps)
            overlaps = self.geometric_validator.find_overlapping_annotations(annotation_dicts, threshold=0.3)
            
            # Quality assessment
            quality_issues = []
            for ann_dict in annotation_dicts:
                validation_result = self.validator.validate_annotation(ann_dict)
                if validation_result.warnings:
                    quality_issues.extend(validation_result.warnings)
            
            return {
                "success": True,
                "validation": {
                    "temporal_consistency": temporal_result,
                    "geometric_overlaps": [
                        {
                            "annotation_1": overlaps[i][0],
                            "annotation_2": overlaps[i][1],
                            "iou": overlaps[i][2]
                        } for i in range(len(overlaps))
                    ],
                    "quality_issues": quality_issues,
                    "overall_score": self._calculate_overall_quality_score(temporal_result, overlaps, quality_issues)
                }
            }
            
        except Exception as e:
            logger.error(f"Error validating annotation sequence {video_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Validation error: {str(e)}",
                "code": "VALIDATION_ERROR"
            }
    
    def bulk_update_annotations(self, db: Session, annotation_ids: List[str], 
                               update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk update multiple annotations"""
        try:
            annotations = db.query(Annotation).filter(
                Annotation.id.in_(annotation_ids)
            ).all()
            
            if not annotations:
                return {
                    "success": False,
                    "error": "No annotations found",
                    "code": "ANNOTATIONS_NOT_FOUND"
                }
            
            updated_count = 0
            errors = []
            
            # Updatable fields for bulk operations
            bulk_updatable_fields = ["validated", "annotator", "difficult", "occluded", "truncated"]
            
            for annotation in annotations:
                try:
                    for field in bulk_updatable_fields:
                        if field in update_data:
                            setattr(annotation, field, update_data[field])
                    
                    annotation.updated_at = datetime.utcnow()
                    updated_count += 1
                    
                except Exception as e:
                    errors.append(f"Error updating annotation {annotation.id}: {str(e)}")
            
            if updated_count > 0:
                db.commit()
                logger.info(f"Bulk updated {updated_count} annotations")
            
            return {
                "success": True,
                "updated_count": updated_count,
                "total_requested": len(annotation_ids),
                "errors": errors
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error bulk updating annotations: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def _annotation_to_dict(self, annotation: Annotation) -> Dict[str, Any]:
        """Convert annotation model to dictionary"""
        return {
            "id": annotation.id,
            "video_id": annotation.video_id,
            "detection_id": annotation.detection_id,
            "frame_number": annotation.frame_number,
            "timestamp": annotation.timestamp,
            "end_timestamp": annotation.end_timestamp,
            "vru_type": annotation.vru_type,
            "bounding_box": annotation.bounding_box,
            "occluded": annotation.occluded,
            "truncated": annotation.truncated,
            "difficult": annotation.difficult,
            "notes": annotation.notes,
            "annotator": annotation.annotator,
            "validated": annotation.validated,
            "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
            "updated_at": annotation.updated_at.isoformat() if annotation.updated_at else None
        }
    
    def _generate_detection_id(self, vru_type: str) -> str:
        """Generate unique detection ID"""
        vru_code = vru_type.upper().replace(" ", "_")
        timestamp = int(datetime.utcnow().timestamp())
        random_part = str(uuid.uuid4())[:8]
        return f"DET_{vru_code}_{timestamp}_{random_part}"
    
    def _calculate_overall_quality_score(self, temporal_result: Dict[str, Any], 
                                       overlaps: List[Tuple], 
                                       quality_issues: List[str]) -> float:
        """Calculate overall annotation sequence quality score"""
        base_score = 1.0
        
        # Temporal consistency score
        temporal_score = temporal_result.get("consistency", 1.0)
        base_score *= temporal_score
        
        # Geometric overlap penalty
        if overlaps:
            overlap_penalty = min(0.5, len(overlaps) * 0.1)  # Max 50% penalty
            base_score *= (1.0 - overlap_penalty)
        
        # Quality issues penalty
        if quality_issues:
            quality_penalty = min(0.3, len(quality_issues) * 0.05)  # Max 30% penalty
            base_score *= (1.0 - quality_penalty)
        
        return max(0.0, base_score)


class AnnotationSessionService:
    """Service for managing annotation sessions"""
    
    def create_session(self, db: Session, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new annotation session"""
        try:
            session = AnnotationSession(
                id=str(uuid.uuid4()),
                video_id=session_data["video_id"],
                project_id=session_data["project_id"],
                annotator_id=session_data.get("annotator_id"),
                status="active",
                total_detections=0,
                validated_detections=0,
                current_frame=0,
                total_frames=session_data.get("total_frames", 0)
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            logger.info(f"Created annotation session {session.id}")
            
            return {
                "success": True,
                "session": self._session_to_dict(session)
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating annotation session: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def update_session_progress(self, db: Session, session_id: str, 
                               progress_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update annotation session progress"""
        try:
            session = db.query(AnnotationSession).filter(
                AnnotationSession.id == session_id
            ).first()
            
            if not session:
                return {
                    "success": False,
                    "error": "Session not found",
                    "code": "SESSION_NOT_FOUND"
                }
            
            # Update progress fields
            if "current_frame" in progress_data:
                session.current_frame = progress_data["current_frame"]
            
            if "total_detections" in progress_data:
                session.total_detections = progress_data["total_detections"]
            
            if "validated_detections" in progress_data:
                session.validated_detections = progress_data["validated_detections"]
            
            if "status" in progress_data:
                session.status = progress_data["status"]
            
            session.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(session)
            
            return {
                "success": True,
                "session": self._session_to_dict(session)
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating session progress {session_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "code": "DATABASE_ERROR"
            }
    
    def _session_to_dict(self, session: AnnotationSession) -> Dict[str, Any]:
        """Convert session model to dictionary"""
        return {
            "id": session.id,
            "video_id": session.video_id,
            "project_id": session.project_id,
            "annotator_id": session.annotator_id,
            "status": session.status,
            "total_detections": session.total_detections,
            "validated_detections": session.validated_detections,
            "current_frame": session.current_frame,
            "total_frames": session.total_frames,
            "progress_percentage": (session.current_frame / session.total_frames * 100) if session.total_frames > 0 else 0,
            "validation_percentage": (session.validated_detections / session.total_detections * 100) if session.total_detections > 0 else 0,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None
        }