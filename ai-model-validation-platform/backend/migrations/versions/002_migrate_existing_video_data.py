"""Migrate existing video data to validation system

Revision ID: 002_migrate_existing_video_data
Revises: 001_video_validation_system
Create Date: 2025-01-11 12:01:00.000000

This migration migrates existing video data to the new unified validation
status system, mapping legacy statuses and creating audit trails.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid
from datetime import datetime

# revision identifiers
revision = '002_migrate_existing_video_data'
down_revision = '001_video_validation_system'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Migrate existing video data to validation system"""
    
    # Get database connection
    conn = op.get_bind()
    
    # Create default validation criteria for projects without specific criteria
    default_criteria_id = str(uuid.uuid4())
    
    conn.execute(text("""
        INSERT INTO video_validation_criteria (
            id, project_id, 
            min_detection_count, min_confidence_threshold, min_frame_coverage_percent,
            min_duration_seconds, max_duration_seconds, required_resolution_min, min_fps,
            required_vru_types, min_scene_complexity_score,
            created_at
        ) VALUES (
            :criteria_id, NULL,
            5, 0.7, 80.0,
            10.0, 300.0, '640x480', 24.0,
            '["pedestrian", "cyclist", "motorcyclist"]'::json, 0.5,
            NOW()
        )
    """), {"criteria_id": default_criteria_id})
    
    # Query all existing videos for migration
    result = conn.execute(text("""
        SELECT id, status, processing_status, ground_truth_generated, 
               created_at, updated_at, project_id
        FROM videos 
        ORDER BY created_at
    """))
    
    videos = result.fetchall()
    
    # Process each video for status migration
    for video in videos:
        video_id = video.id
        legacy_status = video.status
        processing_status = video.processing_status
        ground_truth_generated = video.ground_truth_generated
        
        # Determine new status based on legacy fields
        new_status, validation_status, validation_type = map_legacy_status(
            legacy_status, processing_status, ground_truth_generated
        )
        
        # Set HIL readiness and validation timestamps
        hil_ready = False
        validated_at = None
        validated_by = 'system'
        
        if new_status in ['validated', 'ready_for_testing', 'tested']:
            hil_ready = True
            validated_at = video.updated_at or video.created_at
            
        # Update video with new status fields
        conn.execute(text("""
            UPDATE videos 
            SET 
                status = :new_status,
                validation_status = :validation_status,
                validation_type = :validation_type,
                validated_at = :validated_at,
                validated_by = :validated_by,
                hil_testing_ready = :hil_ready,
                ground_truth_count = CASE 
                    WHEN ground_truth_generated THEN 1
                    ELSE 0
                END,
                ground_truth_quality_score = CASE
                    WHEN ground_truth_generated THEN 0.8
                    ELSE NULL
                END,
                ground_truth_completed_at = CASE
                    WHEN ground_truth_generated THEN updated_at
                    ELSE NULL
                END
            WHERE id = :video_id
        """), {
            "video_id": video_id,
            "new_status": new_status,
            "validation_status": validation_status,
            "validation_type": validation_type,
            "validated_at": validated_at,
            "validated_by": validated_by,
            "hil_ready": hil_ready
        })
        
        # Create status transition audit record
        transition_id = str(uuid.uuid4())
        conn.execute(text("""
            INSERT INTO video_status_transitions (
                id, video_id, from_status, to_status, transition_reason,
                triggered_by, metadata, created_at
            ) VALUES (
                :transition_id, :video_id, :from_status, :to_status, 
                'legacy_data_migration', 'system', :metadata, NOW()
            )
        """), {
            "transition_id": transition_id,
            "video_id": video_id,
            "from_status": legacy_status,
            "to_status": new_status,
            "metadata": f'{{"legacy_status": "{legacy_status}", "processing_status": "{processing_status}", "ground_truth_generated": {str(ground_truth_generated).lower()}, "migration_version": "1.0"}}'
        })
        
        # Create validation result record for validated videos
        if new_status in ['validated', 'ready_for_testing', 'tested']:
            result_id = str(uuid.uuid4())
            overall_score = calculate_legacy_validation_score(ground_truth_generated)
            
            conn.execute(text("""
                INSERT INTO video_validation_results (
                    id, video_id, validation_criteria_id, validation_type, 
                    overall_result, ground_truth_score, technical_score, 
                    content_score, overall_score, criteria_met,
                    validation_notes, validated_by, created_at
                ) VALUES (
                    :result_id, :video_id, :criteria_id, :validation_type,
                    'passed', :gt_score, :tech_score, :content_score, :overall_score,
                    :criteria_met, :notes, 'system', NOW()
                )
            """), {
                "result_id": result_id,
                "video_id": video_id,
                "criteria_id": default_criteria_id,
                "validation_type": validation_type or 'automatic',
                "gt_score": 0.8 if ground_truth_generated else 0.0,
                "tech_score": 0.9,  # Assume technical validation passed
                "content_score": 0.7,  # Conservative content score
                "overall_score": overall_score,
                "criteria_met": '{"ground_truth_generated": true, "technical_valid": true, "migrated_from_legacy": true}',
                "notes": f"Migrated from legacy status: {legacy_status}, processing: {processing_status}"
            })

def map_legacy_status(status: str, processing_status: str, ground_truth_generated: bool) -> tuple[str, str, str]:
    """Map legacy status fields to new unified status system"""
    
    # Priority: processing_status indicates current state
    if processing_status == "failed":
        return "processing_failed", "failed", "automatic"
    elif processing_status == "pending":
        return "processing", "pending", "automatic"
    elif processing_status == "processing":
        return "processing", "processing", "automatic"
    elif processing_status == "completed" and ground_truth_generated:
        # Completed processing with ground truth = validated and ready
        return "validated", "validated", "automatic"
    
    # Fallback to main status field
    if status == "uploaded" and not ground_truth_generated:
        return "uploaded", "pending", "automatic"
    elif status == "uploaded" and ground_truth_generated:
        return "annotated", "pending_validation", "automatic"
    elif status == "completed":
        return "validated", "validated", "automatic"
    else:
        # Unknown or error states
        return "error", "failed", "manual"

def calculate_legacy_validation_score(ground_truth_generated: bool) -> float:
    """Calculate validation score for legacy videos"""
    base_score = 0.7  # Conservative base score for migrated videos
    if ground_truth_generated:
        base_score += 0.2  # Bonus for having ground truth
    return min(base_score, 1.0)

def downgrade() -> None:
    """Downgrade migration - restore legacy status values"""
    
    conn = op.get_bind()
    
    # Restore original status values based on transition history
    conn.execute(text("""
        UPDATE videos 
        SET status = CASE 
            WHEN status IN ('validated', 'ready_for_testing', 'tested') THEN 'completed'
            WHEN status IN ('processing_failed', 'validation_failed', 'error') THEN 'uploaded'
            WHEN status IN ('processing', 'annotated', 'validating') THEN 'uploaded'
            ELSE 'uploaded'
        END,
        processing_status = CASE 
            WHEN status IN ('validated', 'ready_for_testing', 'tested') THEN 'completed'
            WHEN status IN ('processing_failed', 'validation_failed') THEN 'failed'
            WHEN status IN ('processing', 'validating') THEN 'processing'
            WHEN status IN ('annotated') THEN 'completed'
            ELSE 'pending'
        END
    """))
    
    # Clear new validation fields
    conn.execute(text("""
        UPDATE videos 
        SET validation_status = 'pending',
            validation_type = NULL,
            validated_at = NULL,
            validated_by = NULL,
            ground_truth_count = 0,
            ground_truth_quality_score = NULL,
            ground_truth_completed_at = NULL,
            hil_testing_ready = false,
            hil_testing_approved_by = NULL,
            hil_testing_approved_at = NULL
    """))
    
    # Remove migration audit records
    conn.execute(text("""
        DELETE FROM video_status_transitions 
        WHERE transition_reason = 'legacy_data_migration'
    """))
    
    # Remove migration validation results
    conn.execute(text("""
        DELETE FROM video_validation_results 
        WHERE validation_notes LIKE 'Migrated from legacy status%'
    """))
    
    # Remove default validation criteria
    conn.execute(text("""
        DELETE FROM video_validation_criteria 
        WHERE project_id IS NULL
    """))