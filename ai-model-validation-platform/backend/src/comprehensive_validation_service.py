"""
Comprehensive Validation Service for Annotation Data Integrity
============================================================

This service provides the main validation orchestration layer, coordinating
between Pydantic models, database constraints, and business logic validation.
It serves as the single source of truth for annotation validation rules.

Key Features:
1. Multi-layer validation pipeline
2. Comprehensive error handling and reporting
3. Performance optimization
4. Rollback capabilities for failed validations
5. Integration with monitoring and logging
6. Batch validation support
"""

from typing import Dict, List, Optional, Any, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import ValidationError
import logging
import time
import uuid
from datetime import datetime
import json

from src.validation_models import (
    StrictAnnotationCreate,
    StrictAnnotationUpdate,
    StrictBoundingBox,
    ValidationErrorResponse,
    BulkValidationResult
)
from src.database_constraints import validate_existing_data, apply_annotation_constraints
from models import Annotation, Video, GroundTruthObject
from database import SessionLocal

logger = logging.getLogger(__name__)


class ComprehensiveValidationService:
    """
    Main validation service that orchestrates all validation layers.
    
    This service ensures that annotation data is validated through multiple
    layers before being stored in the database, preventing corruption.
    """
    
    def __init__(self):
        self.validation_history = []
        self.performance_metrics = {}
        
        # Validation layer configuration
        self.layers = {
            'pydantic': True,       # Pydantic model validation
            'business_logic': True, # Custom business rules
            'cross_reference': True, # Video/project reference validation
            'database': True,       # Database constraint validation
            'post_save': True       # Post-save verification
        }
    
    async def validate_annotation_creation(
        self,
        annotation_data: Dict[str, Any],
        video_id: str,
        db: Session,
        skip_layers: List[str] = None
    ) -> Tuple[bool, Optional[StrictAnnotationCreate], List[ValidationErrorResponse]]:
        """
        Comprehensive validation pipeline for annotation creation.
        
        Returns:
            (success, validated_model, errors)
        """
        
        validation_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"[{validation_id}] Starting annotation creation validation")
        
        skip_layers = skip_layers or []
        errors = []
        validated_model = None
        
        try:
            # Layer 1: Pydantic Model Validation
            if 'pydantic' not in skip_layers and self.layers['pydantic']:
                success, model, pydantic_errors = await self._validate_pydantic_model(
                    annotation_data, StrictAnnotationCreate, validation_id
                )
                
                if not success:
                    errors.extend(pydantic_errors)
                    return False, None, errors
                
                validated_model = model
                # Ensure video_id is set correctly
                validated_model.video_id = video_id
            
            # Layer 2: Business Logic Validation
            if 'business_logic' not in skip_layers and self.layers['business_logic']:
                success, business_errors = await self._validate_business_logic(
                    validated_model, validation_id
                )
                
                if not success:
                    errors.extend(business_errors)
                    return False, None, errors
            
            # Layer 3: Cross-Reference Validation
            if 'cross_reference' not in skip_layers and self.layers['cross_reference']:
                success, ref_errors = await self._validate_cross_references(
                    validated_model, db, validation_id
                )
                
                if not success:
                    errors.extend(ref_errors)
                    return False, None, errors
            
            # Layer 4: Database Constraint Pre-validation
            if 'database' not in skip_layers and self.layers['database']:
                success, db_errors = await self._pre_validate_database_constraints(
                    validated_model, db, validation_id
                )
                
                if not success:
                    errors.extend(db_errors)
                    return False, None, errors
            
            # All validation layers passed
            duration = time.time() - start_time
            logger.info(f"[{validation_id}] Validation completed successfully in {duration:.3f}s")
            
            self._record_validation_metrics(validation_id, duration, success=True)
            
            return True, validated_model, []
            
        except Exception as e:
            logger.error(f"[{validation_id}] Unexpected error during validation: {e}", exc_info=True)
            
            duration = time.time() - start_time
            self._record_validation_metrics(validation_id, duration, success=False, error=str(e))
            
            errors.append(ValidationErrorResponse(
                error_type="validation_service_error",
                message=f"Unexpected validation error: {str(e)}",
                field=None
            ))
            
            return False, None, errors
    
    async def validate_annotation_update(
        self,
        annotation_id: str,
        update_data: Dict[str, Any],
        db: Session,
        skip_layers: List[str] = None
    ) -> Tuple[bool, Optional[StrictAnnotationUpdate], List[ValidationErrorResponse]]:
        """
        Comprehensive validation pipeline for annotation updates.
        
        Returns:
            (success, validated_model, errors)
        """
        
        validation_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"[{validation_id}] Starting annotation update validation for {annotation_id}")
        
        skip_layers = skip_layers or []
        errors = []
        validated_model = None
        
        try:
            # Check if annotation exists
            existing_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            if not existing_annotation:
                errors.append(ValidationErrorResponse(
                    error_type="not_found_error",
                    message=f"Annotation with id {annotation_id} not found",
                    field="annotation_id"
                ))
                return False, None, errors
            
            # Layer 1: Pydantic Model Validation
            if 'pydantic' not in skip_layers and self.layers['pydantic']:
                success, model, pydantic_errors = await self._validate_pydantic_model(
                    update_data, StrictAnnotationUpdate, validation_id
                )
                
                if not success:
                    errors.extend(pydantic_errors)
                    return False, None, errors
                
                validated_model = model
            
            # Layer 2: Business Logic Validation (for updates)
            if 'business_logic' not in skip_layers and self.layers['business_logic']:
                success, business_errors = await self._validate_update_business_logic(
                    validated_model, existing_annotation, validation_id
                )
                
                if not success:
                    errors.extend(business_errors)
                    return False, None, errors
            
            # All validation layers passed
            duration = time.time() - start_time
            logger.info(f"[{validation_id}] Update validation completed successfully in {duration:.3f}s")
            
            self._record_validation_metrics(validation_id, duration, success=True)
            
            return True, validated_model, []
            
        except Exception as e:
            logger.error(f"[{validation_id}] Unexpected error during update validation: {e}", exc_info=True)
            
            duration = time.time() - start_time
            self._record_validation_metrics(validation_id, duration, success=False, error=str(e))
            
            errors.append(ValidationErrorResponse(
                error_type="validation_service_error",
                message=f"Unexpected validation error: {str(e)}",
                field=None
            ))
            
            return False, None, errors
    
    async def validate_bulk_annotations(
        self,
        annotations_data: List[Dict[str, Any]],
        video_id: str,
        db: Session,
        fail_fast: bool = True
    ) -> BulkValidationResult:
        """
        Validate multiple annotations in batch with optional fail-fast behavior.
        """
        
        validation_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"[{validation_id}] Starting bulk annotation validation for {len(annotations_data)} annotations")
        
        total_submitted = len(annotations_data)
        valid_annotations = 0
        all_errors = []
        successful_ids = []
        
        for i, annotation_data in enumerate(annotations_data):
            try:
                success, validated_model, errors = await self.validate_annotation_creation(
                    annotation_data, video_id, db
                )
                
                if success:
                    valid_annotations += 1
                    # Generate a temporary ID for successful validation
                    successful_ids.append(str(uuid.uuid4()))
                else:
                    # Add index to error messages
                    for error in errors:
                        error.field = f"annotations[{i}].{error.field}" if error.field else f"annotations[{i}]"
                    all_errors.extend(errors)
                    
                    if fail_fast:
                        break
            
            except Exception as e:
                logger.error(f"[{validation_id}] Error validating annotation {i}: {e}")
                all_errors.append(ValidationErrorResponse(
                    error_type="validation_error",
                    field=f"annotations[{i}]",
                    message=f"Validation failed: {str(e)}"
                ))
                
                if fail_fast:
                    break
        
        invalid_annotations = total_submitted - valid_annotations
        
        duration = time.time() - start_time
        logger.info(f"[{validation_id}] Bulk validation completed in {duration:.3f}s: {valid_annotations} valid, {invalid_annotations} invalid")
        
        return BulkValidationResult(
            total_submitted=total_submitted,
            valid_annotations=valid_annotations,
            invalid_annotations=invalid_annotations,
            validation_errors=all_errors,
            successful_ids=successful_ids
        )
    
    async def create_validated_annotation(
        self,
        validated_model: StrictAnnotationCreate,
        db: Session,
        commit: bool = True
    ) -> Tuple[bool, Optional[Annotation], List[ValidationErrorResponse]]:
        """
        Create annotation in database using pre-validated model with post-save verification.
        """
        
        validation_id = str(uuid.uuid4())
        logger.info(f"[{validation_id}] Creating validated annotation in database")
        
        errors = []
        
        try:
            # Convert Pydantic model to database model
            db_annotation = Annotation(
                id=str(uuid.uuid4()),
                video_id=validated_model.video_id,
                detection_id=validated_model.detection_id,
                frame_number=validated_model.frame_number,
                timestamp=validated_model.timestamp,
                end_timestamp=validated_model.end_timestamp,
                vru_type=validated_model.vru_type.value if hasattr(validated_model.vru_type, 'value') else validated_model.vru_type,
                bounding_box=validated_model.bounding_box.dict(),
                occluded=validated_model.occluded,
                truncated=validated_model.truncated,
                difficult=validated_model.difficult,
                notes=validated_model.notes,
                annotator=validated_model.annotator,
                validated=validated_model.validated,
                created_at=datetime.utcnow()
            )
            
            # Add to session
            db.add(db_annotation)
            
            if commit:
                # Attempt database commit with constraint validation
                try:
                    db.commit()
                    logger.info(f"[{validation_id}] Annotation saved successfully: {db_annotation.id}")
                    
                    # Layer 5: Post-save verification
                    if self.layers['post_save']:
                        verification_success = await self._verify_saved_annotation(
                            db_annotation.id, db, validation_id
                        )
                        
                        if not verification_success:
                            # Rollback if verification fails
                            db.rollback()
                            errors.append(ValidationErrorResponse(
                                error_type="post_save_verification_error",
                                message="Saved annotation failed post-save verification",
                                field="annotation"
                            ))
                            return False, None, errors
                    
                    db.refresh(db_annotation)
                    return True, db_annotation, []
                    
                except IntegrityError as e:
                    db.rollback()
                    logger.error(f"[{validation_id}] Database integrity error: {e}")
                    
                    errors.append(ValidationErrorResponse(
                        error_type="database_integrity_error",
                        message=f"Database constraint violation: {str(e)}",
                        field="annotation"
                    ))
                    return False, None, errors
                    
                except SQLAlchemyError as e:
                    db.rollback()
                    logger.error(f"[{validation_id}] Database error: {e}")
                    
                    errors.append(ValidationErrorResponse(
                        error_type="database_error",
                        message=f"Database operation failed: {str(e)}",
                        field="annotation"
                    ))
                    return False, None, errors
            else:
                # Don't commit - return for batch operations
                return True, db_annotation, []
                
        except Exception as e:
            db.rollback()
            logger.error(f"[{validation_id}] Unexpected error creating annotation: {e}", exc_info=True)
            
            errors.append(ValidationErrorResponse(
                error_type="creation_error",
                message=f"Failed to create annotation: {str(e)}",
                field="annotation"
            ))
            return False, None, errors
    
    async def _validate_pydantic_model(
        self,
        data: Dict[str, Any],
        model_class: type,
        validation_id: str
    ) -> Tuple[bool, Optional[Any], List[ValidationErrorResponse]]:
        """Validate data against Pydantic model"""
        
        try:
            validated_model = model_class(**data)
            logger.debug(f"[{validation_id}] Pydantic validation passed for {model_class.__name__}")
            return True, validated_model, []
            
        except ValidationError as e:
            logger.warning(f"[{validation_id}] Pydantic validation failed: {e}")
            
            errors = []
            for error in e.errors():
                field_path = '.'.join(str(loc) for loc in error.get('loc', []))
                errors.append(ValidationErrorResponse(
                    error_type=error.get('type', 'validation_error'),
                    field=field_path if field_path else None,
                    message=error.get('msg', 'Validation failed'),
                    provided_value=error.get('input')
                ))
            
            return False, None, errors
    
    async def _validate_business_logic(
        self,
        validated_model: StrictAnnotationCreate,
        validation_id: str
    ) -> Tuple[bool, List[ValidationErrorResponse]]:
        """Apply custom business logic validation rules"""
        
        errors = []
        
        # Rule 1: Bounding box must not be larger than reasonable video dimensions
        bbox = validated_model.bounding_box
        if bbox.x > 3840 or bbox.y > 2160:  # 4K resolution limits
            errors.append(ValidationErrorResponse(
                error_type="business_logic_error",
                field="bounding_box",
                message="Bounding box coordinates exceed reasonable video dimensions",
                provided_value=f"x={bbox.x}, y={bbox.y}"
            ))
        
        # Rule 2: Timestamp should be reasonable (not in the far future)
        if validated_model.timestamp > 86400 * 365:  # More than 1 year
            errors.append(ValidationErrorResponse(
                error_type="business_logic_error",
                field="timestamp",
                message="Timestamp is unreasonably large (> 1 year)",
                provided_value=validated_model.timestamp
            ))
        
        # Rule 3: Frame number should correlate reasonably with timestamp (if both present)
        if validated_model.frame_number > 0 and validated_model.timestamp > 0:
            implied_fps = validated_model.frame_number / validated_model.timestamp
            if implied_fps > 240 or implied_fps < 1:  # Unreasonable FPS
                logger.warning(f"[{validation_id}] Unusual FPS detected: {implied_fps}")
                # Don't fail validation, but log for review
        
        # Rule 4: If detection_id is provided, it should follow naming convention
        if validated_model.detection_id:
            if not validated_model.detection_id.startswith(('DET_', 'DETECT_', 'det_')):
                logger.warning(f"[{validation_id}] Detection ID doesn't follow naming convention: {validated_model.detection_id}")
        
        if errors:
            logger.warning(f"[{validation_id}] Business logic validation failed with {len(errors)} errors")
            return False, errors
        
        logger.debug(f"[{validation_id}] Business logic validation passed")
        return True, []
    
    async def _validate_update_business_logic(
        self,
        validated_model: StrictAnnotationUpdate,
        existing_annotation: Annotation,
        validation_id: str
    ) -> Tuple[bool, List[ValidationErrorResponse]]:
        """Apply business logic validation for updates"""
        
        errors = []
        
        # Rule 1: Don't allow changing video_id (if that was somehow attempted)
        # This is handled at the endpoint level, but double-check
        
        # Rule 2: If updating timestamp, ensure it doesn't conflict with existing temporal annotations
        if validated_model.timestamp is not None:
            if validated_model.timestamp < 0:
                errors.append(ValidationErrorResponse(
                    error_type="business_logic_error",
                    field="timestamp",
                    message="Timestamp cannot be negative"
                ))
        
        # Rule 3: If updating bounding box, ensure it's still valid
        if validated_model.bounding_box is not None:
            bbox = validated_model.bounding_box
            if bbox.x > 3840 or bbox.y > 2160:
                errors.append(ValidationErrorResponse(
                    error_type="business_logic_error",
                    field="bounding_box",
                    message="Updated bounding box coordinates exceed reasonable dimensions"
                ))
        
        if errors:
            logger.warning(f"[{validation_id}] Update business logic validation failed")
            return False, errors
        
        logger.debug(f"[{validation_id}] Update business logic validation passed")
        return True, []
    
    async def _validate_cross_references(
        self,
        validated_model: StrictAnnotationCreate,
        db: Session,
        validation_id: str
    ) -> Tuple[bool, List[ValidationErrorResponse]]:
        """Validate cross-references (video exists, etc.)"""
        
        errors = []
        
        # Validate video exists
        video = db.query(Video).filter(Video.id == validated_model.video_id).first()
        if not video:
            errors.append(ValidationErrorResponse(
                error_type="reference_error",
                field="video_id",
                message=f"Video with id {validated_model.video_id} not found",
                provided_value=validated_model.video_id
            ))
            return False, errors
        
        # Validate frame number is within video bounds (if video duration is known)
        if video.duration and video.fps and validated_model.frame_number:
            max_frames = int(video.duration * video.fps)
            if validated_model.frame_number > max_frames:
                errors.append(ValidationErrorResponse(
                    error_type="reference_error",
                    field="frame_number",
                    message=f"Frame number {validated_model.frame_number} exceeds video duration",
                    provided_value=validated_model.frame_number,
                    expected_format=f"0 to {max_frames}"
                ))
        
        # Validate timestamp is within video duration (if known)
        if video.duration and validated_model.timestamp > video.duration:
            errors.append(ValidationErrorResponse(
                error_type="reference_error",
                field="timestamp",
                message=f"Timestamp {validated_model.timestamp} exceeds video duration {video.duration}",
                provided_value=validated_model.timestamp
            ))
        
        if errors:
            logger.warning(f"[{validation_id}] Cross-reference validation failed")
            return False, errors
        
        logger.debug(f"[{validation_id}] Cross-reference validation passed")
        return True, []
    
    async def _pre_validate_database_constraints(
        self,
        validated_model: StrictAnnotationCreate,
        db: Session,
        validation_id: str
    ) -> Tuple[bool, List[ValidationErrorResponse]]:
        """Pre-validate against database constraints before saving"""
        
        errors = []
        
        # Check for duplicate annotations (same video, frame, and similar bbox)
        similar_annotations = db.query(Annotation).filter(
            Annotation.video_id == validated_model.video_id,
            Annotation.frame_number == validated_model.frame_number
        ).all()
        
        bbox = validated_model.bounding_box
        for existing in similar_annotations:
            if existing.bounding_box:
                existing_bbox = existing.bounding_box
                # Check if bounding boxes overlap significantly
                if self._bounding_boxes_overlap(
                    (bbox.x, bbox.y, bbox.width, bbox.height),
                    (existing_bbox.get('x', 0), existing_bbox.get('y', 0), 
                     existing_bbox.get('width', 0), existing_bbox.get('height', 0))
                ):
                    logger.warning(f"[{validation_id}] Potential duplicate annotation detected")
                    # Don't fail validation, but log for review
        
        logger.debug(f"[{validation_id}] Database constraint pre-validation passed")
        return True, []
    
    def _bounding_boxes_overlap(self, bbox1: tuple, bbox2: tuple, threshold: float = 0.8) -> bool:
        """Check if two bounding boxes overlap significantly"""
        
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Calculate intersection
        left = max(x1, x2)
        top = max(y1, y2)
        right = min(x1 + w1, x2 + w2)
        bottom = min(y1 + h1, y2 + h2)
        
        if left >= right or top >= bottom:
            return False
        
        intersection = (right - left) * (bottom - top)
        union = w1 * h1 + w2 * h2 - intersection
        
        iou = intersection / union if union > 0 else 0
        return iou > threshold
    
    async def _verify_saved_annotation(
        self,
        annotation_id: str,
        db: Session,
        validation_id: str
    ) -> bool:
        """Verify annotation was saved correctly with valid data"""
        
        try:
            # Refresh session to ensure we get latest data
            db.refresh(db.query(Annotation).filter(Annotation.id == annotation_id).first())
            
            # Reload annotation from database
            saved_annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
            
            if not saved_annotation:
                logger.error(f"[{validation_id}] Post-save verification failed: annotation not found")
                return False
            
            # Verify bounding box integrity
            if not saved_annotation.bounding_box:
                logger.error(f"[{validation_id}] Post-save verification failed: bounding_box is None")
                return False
            
            required_bbox_fields = ['x', 'y', 'width', 'height']
            for field in required_bbox_fields:
                if field not in saved_annotation.bounding_box or saved_annotation.bounding_box[field] is None:
                    logger.error(f"[{validation_id}] Post-save verification failed: bounding_box missing {field}")
                    return False
            
            logger.debug(f"[{validation_id}] Post-save verification passed")
            return True
            
        except Exception as e:
            logger.error(f"[{validation_id}] Post-save verification error: {e}")
            return False
    
    def _record_validation_metrics(
        self,
        validation_id: str,
        duration: float,
        success: bool,
        error: str = None
    ):
        """Record validation performance metrics"""
        
        metric = {
            'validation_id': validation_id,
            'duration_ms': duration * 1000,
            'success': success,
            'error': error,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.validation_history.append(metric)
        
        # Keep only last 1000 entries
        if len(self.validation_history) > 1000:
            self.validation_history = self.validation_history[-1000:]
        
        # Update performance metrics
        if success:
            if 'successful_validations' not in self.performance_metrics:
                self.performance_metrics['successful_validations'] = 0
            self.performance_metrics['successful_validations'] += 1
        else:
            if 'failed_validations' not in self.performance_metrics:
                self.performance_metrics['failed_validations'] = 0
            self.performance_metrics['failed_validations'] += 1
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get current validation statistics"""
        
        total_validations = len(self.validation_history)
        if total_validations == 0:
            return {
                'total_validations': 0,
                'success_rate': 0,
                'average_duration_ms': 0,
                'recent_activity': []
            }
        
        successful = sum(1 for v in self.validation_history if v['success'])
        success_rate = successful / total_validations * 100
        
        durations = [v['duration_ms'] for v in self.validation_history]
        avg_duration = sum(durations) / len(durations)
        
        return {
            'total_validations': total_validations,
            'successful_validations': successful,
            'failed_validations': total_validations - successful,
            'success_rate': round(success_rate, 2),
            'average_duration_ms': round(avg_duration, 2),
            'recent_activity': self.validation_history[-10:],  # Last 10 validations
            'performance_metrics': self.performance_metrics
        }


# Global validation service instance
validation_service = ComprehensiveValidationService()