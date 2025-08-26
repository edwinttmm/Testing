"""
Validation Architecture Integration Layer
========================================

This module provides the integration layer that replaces existing annotation
endpoints with the new comprehensive validation architecture. It demonstrates
how to integrate the validation system without breaking existing functionality.

Key Features:
1. Drop-in replacement for existing annotation endpoints
2. Backward compatibility with existing API contracts
3. Comprehensive error handling and reporting
4. Performance monitoring and metrics
5. Easy rollback capability
"""

from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

from database import get_db
from src.validation_middleware import (
    validate_video_exists,
    validate_annotation_exists,
    ValidationException,
    validation_metrics
)
from src.comprehensive_validation_service import validation_service
from src.validation_models import (
    StrictAnnotationCreate,
    StrictAnnotationUpdate,
    ValidationErrorResponse
)
from models import Annotation, Video

logger = logging.getLogger(__name__)


class ValidatedAnnotationEndpoints:
    """
    Drop-in replacement for existing annotation endpoints with comprehensive validation.
    
    This class provides the same API interface as the original endpoints but with
    the full validation architecture applied.
    """
    
    def __init__(self):
        self.validation_enabled = True
        self.fallback_to_original = False
    
    async def create_annotation_validated(
        self,
        video_id: str,
        annotation_data: Dict[str, Any],
        db: Session = Depends(get_db),
        video: Video = Depends(validate_video_exists)
    ):
        """
        Create annotation with comprehensive validation pipeline.
        
        This replaces the original create_annotation endpoint.
        """
        
        logger.info(f"Creating annotation for video {video_id} with validation")
        
        try:
            if not self.validation_enabled:
                # Fallback to original logic if validation is disabled
                return await self._fallback_create_annotation(video_id, annotation_data, db)
            
            # Ensure video_id is in annotation data
            annotation_data['video_id'] = video_id
            
            # Run comprehensive validation pipeline
            success, validated_model, errors = await validation_service.validate_annotation_creation(
                annotation_data=annotation_data,
                video_id=video_id,
                db=db
            )
            
            if not success:
                logger.warning(f"Annotation validation failed for video {video_id}: {len(errors)} errors")
                raise ValidationException(
                    status_code=422,
                    detail="Annotation validation failed",
                    validation_errors=errors
                )
            
            # Create annotation using validated model
            success, db_annotation, creation_errors = await validation_service.create_validated_annotation(
                validated_model=validated_model,
                db=db,
                commit=True
            )
            
            if not success:
                logger.error(f"Failed to create annotation for video {video_id}")
                raise ValidationException(
                    status_code=500,
                    detail="Failed to create annotation",
                    validation_errors=creation_errors
                )
            
            # Return annotation in API-compatible format
            return self._format_annotation_response(db_annotation)
            
        except ValidationException:
            raise
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating annotation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create annotation: {str(e)}"
            )
    
    async def update_annotation_validated(
        self,
        annotation_id: str,
        update_data: Dict[str, Any],
        db: Session = Depends(get_db),
        annotation: Annotation = Depends(validate_annotation_exists)
    ):
        """
        Update annotation with comprehensive validation pipeline.
        
        This replaces the original update_annotation endpoint.
        """
        
        logger.info(f"Updating annotation {annotation_id} with validation")
        
        try:
            if not self.validation_enabled:
                return await self._fallback_update_annotation(annotation_id, update_data, db)
            
            # Run comprehensive validation pipeline for updates
            success, validated_model, errors = await validation_service.validate_annotation_update(
                annotation_id=annotation_id,
                update_data=update_data,
                db=db
            )
            
            if not success:
                logger.warning(f"Annotation update validation failed for {annotation_id}: {len(errors)} errors")
                raise ValidationException(
                    status_code=422,
                    detail="Annotation update validation failed",
                    validation_errors=errors
                )
            
            # Apply validated updates to existing annotation
            await self._apply_validated_updates(annotation, validated_model, db)
            
            return self._format_annotation_response(annotation)
            
        except ValidationException:
            raise
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating annotation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update annotation: {str(e)}"
            )
    
    async def bulk_create_annotations_validated(
        self,
        video_id: str,
        annotations_data: List[Dict[str, Any]],
        db: Session = Depends(get_db),
        video: Video = Depends(validate_video_exists)
    ):
        """
        Create multiple annotations with comprehensive validation.
        """
        
        logger.info(f"Creating {len(annotations_data)} annotations for video {video_id} with validation")
        
        try:
            if not self.validation_enabled:
                return await self._fallback_bulk_create(video_id, annotations_data, db)
            
            # Validate all annotations in bulk
            validation_result = await validation_service.validate_bulk_annotations(
                annotations_data=annotations_data,
                video_id=video_id,
                db=db,
                fail_fast=False  # Continue validation for all annotations
            )
            
            if validation_result.invalid_annotations > 0:
                logger.warning(f"Bulk validation found {validation_result.invalid_annotations} invalid annotations")
                
                # Return partial success response with errors
                return {
                    "status": "partial_success",
                    "total_submitted": validation_result.total_submitted,
                    "valid_annotations": validation_result.valid_annotations,
                    "invalid_annotations": validation_result.invalid_annotations,
                    "validation_errors": [error.dict() for error in validation_result.validation_errors],
                    "message": f"Processed {validation_result.valid_annotations} valid annotations, {validation_result.invalid_annotations} failed validation"
                }
            
            # All annotations are valid - create them
            created_annotations = []
            failed_creations = []
            
            for i, annotation_data in enumerate(annotations_data):
                try:
                    # Re-validate and create each annotation
                    success, validated_model, errors = await validation_service.validate_annotation_creation(
                        annotation_data=annotation_data,
                        video_id=video_id,
                        db=db
                    )
                    
                    if success:
                        success, db_annotation, creation_errors = await validation_service.create_validated_annotation(
                            validated_model=validated_model,
                            db=db,
                            commit=True
                        )
                        
                        if success:
                            created_annotations.append(self._format_annotation_response(db_annotation))
                        else:
                            failed_creations.append({
                                "index": i,
                                "errors": [error.dict() for error in creation_errors]
                            })
                    
                except Exception as e:
                    logger.error(f"Error creating annotation {i}: {e}")
                    failed_creations.append({
                        "index": i,
                        "error": str(e)
                    })
            
            return {
                "status": "success" if not failed_creations else "partial_success",
                "created_annotations": created_annotations,
                "failed_creations": failed_creations,
                "total_created": len(created_annotations),
                "total_failed": len(failed_creations)
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in bulk annotation creation: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Bulk annotation creation failed: {str(e)}"
            )
    
    async def get_validation_stats(self):
        """Get current validation statistics"""
        
        service_stats = validation_service.get_validation_stats()
        
        return {
            "validation_architecture": {
                "enabled": self.validation_enabled,
                "fallback_mode": self.fallback_to_original,
                "layers": validation_service.layers
            },
            "performance": service_stats,
            "middleware_stats": validation_metrics.get_validation_stats(None),  # This would need middleware instance
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _format_annotation_response(self, annotation: Annotation) -> Dict[str, Any]:
        """Format annotation for API response compatibility"""
        
        return {
            "id": annotation.id,
            "videoId": annotation.video_id,
            "detectionId": annotation.detection_id,
            "frameNumber": annotation.frame_number,
            "timestamp": annotation.timestamp,
            "endTimestamp": annotation.end_timestamp,
            "vruType": annotation.vru_type,
            "boundingBox": annotation.bounding_box,
            "occluded": annotation.occluded,
            "truncated": annotation.truncated,
            "difficult": annotation.difficult,
            "notes": annotation.notes,
            "annotator": annotation.annotator,
            "validated": annotation.validated,
            "createdAt": annotation.created_at.isoformat() if annotation.created_at else None,
            "updatedAt": annotation.updated_at.isoformat() if annotation.updated_at else None
        }
    
    async def _apply_validated_updates(
        self,
        annotation: Annotation,
        validated_updates: StrictAnnotationUpdate,
        db: Session
    ):
        """Apply validated updates to existing annotation"""
        
        update_data = validated_updates.dict(exclude_unset=True)
        
        for field, value in update_data.items():
            if field == 'bounding_box' and value is not None:
                # Convert Pydantic model to dict
                setattr(annotation, field, value.dict())
            elif field == 'vru_type' and value is not None:
                # Handle enum values
                setattr(annotation, field, value.value if hasattr(value, 'value') else value)
            elif value is not None:
                setattr(annotation, field, value)
        
        annotation.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(annotation)
    
    async def _fallback_create_annotation(
        self,
        video_id: str,
        annotation_data: Dict[str, Any],
        db: Session
    ):
        """Fallback to original annotation creation logic"""
        
        logger.info(f"Using fallback annotation creation for video {video_id}")
        
        # This would call the original create_annotation logic
        # For now, just return a basic creation
        from models import Annotation
        import uuid
        
        db_annotation = Annotation(
            id=str(uuid.uuid4()),
            video_id=video_id,
            **annotation_data
        )
        
        db.add(db_annotation)
        db.commit()
        db.refresh(db_annotation)
        
        return self._format_annotation_response(db_annotation)
    
    async def _fallback_update_annotation(
        self,
        annotation_id: str,
        update_data: Dict[str, Any],
        db: Session
    ):
        """Fallback to original annotation update logic"""
        
        logger.info(f"Using fallback annotation update for {annotation_id}")
        
        # This would call the original update logic
        annotation = db.query(Annotation).filter(Annotation.id == annotation_id).first()
        
        for field, value in update_data.items():
            setattr(annotation, field, value)
        
        db.commit()
        db.refresh(annotation)
        
        return self._format_annotation_response(annotation)
    
    async def _fallback_bulk_create(
        self,
        video_id: str,
        annotations_data: List[Dict[str, Any]],
        db: Session
    ):
        """Fallback to original bulk creation logic"""
        
        logger.info(f"Using fallback bulk creation for video {video_id}")
        
        created_annotations = []
        
        for annotation_data in annotations_data:
            try:
                db_annotation = await self._fallback_create_annotation(video_id, annotation_data, db)
                created_annotations.append(db_annotation)
            except Exception as e:
                logger.error(f"Fallback bulk creation error: {e}")
        
        return {
            "status": "success",
            "created_annotations": created_annotations,
            "total_created": len(created_annotations)
        }
    
    def enable_validation(self, enabled: bool = True):
        """Enable or disable validation architecture"""
        self.validation_enabled = enabled
        logger.info(f"Validation architecture {'enabled' if enabled else 'disabled'}")
    
    def enable_fallback(self, enabled: bool = True):
        """Enable or disable fallback to original logic"""
        self.fallback_to_original = enabled
        logger.info(f"Fallback mode {'enabled' if enabled else 'disabled'}")


# Global instance for use in FastAPI routes
validated_endpoints = ValidatedAnnotationEndpoints()


# FastAPI route integration functions
async def create_annotation_with_validation(
    video_id: str,
    annotation_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """FastAPI route function for validated annotation creation"""
    return await validated_endpoints.create_annotation_validated(video_id, annotation_data, db)


async def update_annotation_with_validation(
    annotation_id: str,
    update_data: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """FastAPI route function for validated annotation updates"""
    return await validated_endpoints.update_annotation_validated(annotation_id, update_data, db)


async def bulk_create_annotations_with_validation(
    video_id: str,
    annotations_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """FastAPI route function for validated bulk annotation creation"""
    return await validated_endpoints.bulk_create_annotations_validated(video_id, annotations_data, db)


async def get_validation_architecture_stats():
    """FastAPI route function for validation statistics"""
    return await validated_endpoints.get_validation_stats()


# Configuration and management functions
def configure_validation_architecture(
    enable_validation: bool = True,
    enable_fallback: bool = False,
    apply_database_constraints: bool = True
):
    """Configure the validation architecture"""
    
    validated_endpoints.enable_validation(enable_validation)
    validated_endpoints.enable_fallback(enable_fallback)
    
    if apply_database_constraints:
        from src.database_constraints import apply_annotation_constraints
        from database import engine
        
        try:
            apply_annotation_constraints(engine)
            logger.info("Database constraints applied successfully")
        except Exception as e:
            logger.error(f"Failed to apply database constraints: {e}")
    
    logger.info("Validation architecture configuration complete")


def rollback_validation_architecture():
    """Rollback to original annotation logic"""
    
    validated_endpoints.enable_validation(False)
    validated_endpoints.enable_fallback(True)
    
    logger.info("Validation architecture rolled back - using original logic")


def validate_existing_annotations():
    """Validate all existing annotations against new validation rules"""
    
    from database import SessionLocal
    
    db = SessionLocal()
    
    try:
        all_annotations = db.query(Annotation).all()
        validation_issues = []
        
        for annotation in all_annotations:
            # Check bounding box integrity
            if not annotation.bounding_box:
                validation_issues.append(f"Annotation {annotation.id}: missing bounding_box")
                continue
            
            required_fields = ['x', 'y', 'width', 'height']
            for field in required_fields:
                if field not in annotation.bounding_box or annotation.bounding_box[field] is None:
                    validation_issues.append(f"Annotation {annotation.id}: bounding_box missing {field}")
        
        return {
            "total_annotations": len(all_annotations),
            "validation_issues": len(validation_issues),
            "issues": validation_issues[:10],  # Show first 10 issues
            "status": "clean" if not validation_issues else "issues_found"
        }
        
    finally:
        db.close()