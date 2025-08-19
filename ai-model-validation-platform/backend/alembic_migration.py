"""Add annotation system tables and relationships

Revision ID: 001_annotation_system
Create Date: 2025-08-19 08:15:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '001_annotation_system'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Create annotation system tables"""
    
    # Create annotations table
    op.create_table('annotations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('video_id', sa.String(36), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('detection_id', sa.String(36), nullable=True),
        sa.Column('frame_number', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('end_timestamp', sa.Float(), nullable=True),
        sa.Column('vru_type', sa.String(), nullable=False),
        sa.Column('bounding_box', sa.JSON(), nullable=False),
        sa.Column('occluded', sa.Boolean(), default=False),
        sa.Column('truncated', sa.Boolean(), default=False),
        sa.Column('difficult', sa.Boolean(), default=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('annotator', sa.String(36), nullable=True),
        sa.Column('validated', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )
    
    # Create indexes for annotations
    op.create_index('idx_annotation_video_frame', 'annotations', ['video_id', 'frame_number'])
    op.create_index('idx_annotation_video_timestamp', 'annotations', ['video_id', 'timestamp'])
    op.create_index('idx_annotation_video_validated', 'annotations', ['video_id', 'validated'])
    op.create_index('idx_annotation_detection_id', 'annotations', ['detection_id'])
    op.create_index('idx_annotation_vru_validated', 'annotations', ['vru_type', 'validated'])
    op.create_index('idx_annotation_frame_number', 'annotations', ['frame_number'])
    op.create_index('idx_annotation_timestamp', 'annotations', ['timestamp'])
    op.create_index('idx_annotation_validated', 'annotations', ['validated'])
    
    # Create annotation_sessions table
    op.create_table('annotation_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('video_id', sa.String(36), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('annotator_id', sa.String(36), nullable=True),
        sa.Column('status', sa.String(), default='active'),
        sa.Column('total_detections', sa.Integer(), default=0),
        sa.Column('validated_detections', sa.Integer(), default=0),
        sa.Column('current_frame', sa.Integer(), default=0),
        sa.Column('total_frames', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )
    
    # Create video_project_links table
    op.create_table('video_project_links',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('video_id', sa.String(36), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assignment_reason', sa.Text(), nullable=True),
        sa.Column('intelligent_match', sa.Boolean(), default=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Create unique index for video_project_links
    op.create_index('idx_video_project_unique', 'video_project_links', ['video_id', 'project_id'], unique=True)
    
    # Create test_results table
    op.create_table('test_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_session_id', sa.String(36), sa.ForeignKey('test_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('recall', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.Column('true_positives', sa.Integer(), nullable=True),
        sa.Column('false_positives', sa.Integer(), nullable=True),
        sa.Column('false_negatives', sa.Integer(), nullable=True),
        sa.Column('statistical_analysis', sa.JSON(), nullable=True),
        sa.Column('confidence_intervals', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Create detection_comparisons table
    op.create_table('detection_comparisons',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('test_session_id', sa.String(36), sa.ForeignKey('test_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ground_truth_id', sa.String(36), sa.ForeignKey('annotations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('detection_event_id', sa.String(36), sa.ForeignKey('detection_events.id', ondelete='SET NULL'), nullable=True),
        sa.Column('match_type', sa.String(), nullable=False),
        sa.Column('iou_score', sa.Float(), nullable=True),
        sa.Column('distance_error', sa.Float(), nullable=True),
        sa.Column('temporal_offset', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes for performance
    op.create_index('idx_comparison_session_match', 'detection_comparisons', ['test_session_id', 'match_type'])
    op.create_index('idx_annotation_session_video', 'annotation_sessions', ['video_id'])
    op.create_index('idx_annotation_session_project', 'annotation_sessions', ['project_id'])
    op.create_index('idx_test_result_session', 'test_results', ['test_session_id'])

def downgrade():
    """Drop annotation system tables"""
    op.drop_table('detection_comparisons')
    op.drop_table('test_results')
    op.drop_table('video_project_links')
    op.drop_table('annotation_sessions')
    op.drop_table('annotations')