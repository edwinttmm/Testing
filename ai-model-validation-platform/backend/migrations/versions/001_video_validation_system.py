"""Video Validation System Migration

Revision ID: 001_video_validation_system
Revises: 
Create Date: 2025-01-11 12:00:00.000000

This migration implements the unified video validation status system
to resolve frontend/backend contract mismatches and provide clear
video workflow states for HIL testing.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001_video_validation_system'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Upgrade to video validation system"""
    
    # Add new columns to videos table
    op.add_column('videos', sa.Column('validation_status', sa.String(50), nullable=False, server_default='pending'))
    op.add_column('videos', sa.Column('validation_type', sa.String(20), nullable=True))
    op.add_column('videos', sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('validated_by', sa.String(36), nullable=True))
    op.add_column('videos', sa.Column('ground_truth_count', sa.Integer, nullable=False, server_default='0'))
    op.add_column('videos', sa.Column('ground_truth_quality_score', sa.Float, nullable=True))
    op.add_column('videos', sa.Column('ground_truth_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('videos', sa.Column('hil_testing_ready', sa.Boolean, nullable=False, server_default='false'))
    op.add_column('videos', sa.Column('hil_testing_approved_by', sa.String(36), nullable=True))
    op.add_column('videos', sa.Column('hil_testing_approved_at', sa.DateTime(timezone=True), nullable=True))
    
    # Create indexes for new columns
    op.create_index('idx_video_validation_status', 'videos', ['validation_status'])
    op.create_index('idx_video_status_validation', 'videos', ['status', 'validation_status'])
    op.create_index('idx_video_hil_ready', 'videos', ['hil_testing_ready', 'status'])
    op.create_index('idx_video_validation_completed', 'videos', ['validated_at', 'validation_type'])
    op.create_index('idx_video_ground_truth_quality', 'videos', ['ground_truth_quality_score', 'ground_truth_count'])
    op.create_index('idx_video_testing_workflow', 'videos', ['status', 'hil_testing_ready', 'validated_at'])
    
    # Create video_validation_criteria table
    op.create_table(
        'video_validation_criteria',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        
        # Ground truth quality requirements
        sa.Column('min_detection_count', sa.Integer, nullable=False, server_default='5'),
        sa.Column('min_confidence_threshold', sa.Float, nullable=False, server_default='0.7'),
        sa.Column('min_frame_coverage_percent', sa.Float, nullable=False, server_default='80.0'),
        
        # Technical requirements
        sa.Column('min_duration_seconds', sa.Float, nullable=False, server_default='10.0'),
        sa.Column('max_duration_seconds', sa.Float, nullable=False, server_default='300.0'),
        sa.Column('required_resolution_min', sa.String, nullable=False, server_default='640x480'),
        sa.Column('min_fps', sa.Float, nullable=False, server_default='24.0'),
        
        # Content requirements
        sa.Column('required_vru_types', sa.JSON, nullable=True),
        sa.Column('min_scene_complexity_score', sa.Float, nullable=False, server_default='0.5'),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now(), nullable=True),
    )
    
    # Create indexes for validation criteria
    op.create_index('idx_validation_criteria_project', 'video_validation_criteria', ['project_id'])
    op.create_index('idx_validation_criteria_created', 'video_validation_criteria', ['created_at'])
    
    # Create video_validation_results table
    op.create_table(
        'video_validation_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('video_id', sa.String(36), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('validation_criteria_id', sa.String(36), sa.ForeignKey('video_validation_criteria.id'), nullable=False),
        
        # Validation results
        sa.Column('validation_type', sa.String, nullable=False),
        sa.Column('overall_result', sa.String, nullable=False),
        
        # Detailed results
        sa.Column('ground_truth_score', sa.Float, nullable=True),
        sa.Column('technical_score', sa.Float, nullable=True),
        sa.Column('content_score', sa.Float, nullable=True),
        sa.Column('overall_score', sa.Float, nullable=True),
        
        # Validation details
        sa.Column('criteria_met', sa.JSON, nullable=True),
        sa.Column('validation_notes', sa.Text, nullable=True),
        sa.Column('validated_by', sa.String(36), nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for validation results
    op.create_index('idx_validation_result_video', 'video_validation_results', ['video_id'])
    op.create_index('idx_validation_result_type', 'video_validation_results', ['validation_type'])
    op.create_index('idx_validation_result_overall', 'video_validation_results', ['overall_result'])
    op.create_index('idx_validation_result_score', 'video_validation_results', ['overall_score'])
    op.create_index('idx_validation_result_created', 'video_validation_results', ['created_at'])
    
    # Create video_status_transitions table
    op.create_table(
        'video_status_transitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('video_id', sa.String(36), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        
        sa.Column('from_status', sa.String, nullable=False),
        sa.Column('to_status', sa.String, nullable=False),
        sa.Column('transition_reason', sa.String, nullable=False),
        
        # Context
        sa.Column('triggered_by', sa.String(36), nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create indexes for status transitions
    op.create_index('idx_status_transition_video', 'video_status_transitions', ['video_id'])
    op.create_index('idx_status_transition_video_time', 'video_status_transitions', ['video_id', 'created_at'])
    op.create_index('idx_status_transition_from_to', 'video_status_transitions', ['from_status', 'to_status'])
    op.create_index('idx_status_transition_created', 'video_status_transitions', ['created_at'])

def downgrade() -> None:
    """Downgrade from video validation system"""
    
    # Drop status transitions table
    op.drop_table('video_status_transitions')
    
    # Drop validation results table  
    op.drop_table('video_validation_results')
    
    # Drop validation criteria table
    op.drop_table('video_validation_criteria')
    
    # Drop new indexes from videos table
    op.drop_index('idx_video_testing_workflow', 'videos')
    op.drop_index('idx_video_ground_truth_quality', 'videos')
    op.drop_index('idx_video_validation_completed', 'videos')
    op.drop_index('idx_video_hil_ready', 'videos')
    op.drop_index('idx_video_status_validation', 'videos')
    op.drop_index('idx_video_validation_status', 'videos')
    
    # Remove new columns from videos table
    op.drop_column('videos', 'hil_testing_approved_at')
    op.drop_column('videos', 'hil_testing_approved_by')
    op.drop_column('videos', 'hil_testing_ready')
    op.drop_column('videos', 'ground_truth_completed_at')
    op.drop_column('videos', 'ground_truth_quality_score')
    op.drop_column('videos', 'ground_truth_count')
    op.drop_column('videos', 'validated_by')
    op.drop_column('videos', 'validated_at')
    op.drop_column('videos', 'validation_type')
    op.drop_column('videos', 'validation_status')