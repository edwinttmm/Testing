"""Add simple detection models

Revision ID: simple_detection_001
Revises: 
Create Date: 2024-09-07 15:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = 'simple_detection_001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    """Add tables for simple detection system"""
    
    # Create detection_sessions table
    op.create_table('detection_sessions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('video_id', sa.String(36), nullable=True),
        sa.Column('start_time', sa.Float(), nullable=False),
        sa.Column('end_time', sa.Float(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('tolerance_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('total_detections', sa.Integer(), nullable=True),
        sa.Column('matched_detections', sa.Integer(), nullable=True),
        sa.Column('accuracy_percentage', sa.Float(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('storage_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id')
    )
    
    # Create indexes for detection_sessions
    op.create_index(op.f('ix_detection_sessions_session_id'), 'detection_sessions', ['session_id'], unique=False)
    op.create_index(op.f('ix_detection_sessions_project_id'), 'detection_sessions', ['project_id'], unique=False)
    op.create_index(op.f('ix_detection_sessions_video_id'), 'detection_sessions', ['video_id'], unique=False)
    op.create_index(op.f('ix_detection_sessions_start_time'), 'detection_sessions', ['start_time'], unique=False)
    op.create_index(op.f('ix_detection_sessions_end_time'), 'detection_sessions', ['end_time'], unique=False)
    op.create_index(op.f('ix_detection_sessions_status'), 'detection_sessions', ['status'], unique=False)
    op.create_index(op.f('ix_detection_sessions_created_at'), 'detection_sessions', ['created_at'], unique=False)

    # Create stored_detection_events table
    op.create_table('stored_detection_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('detection_id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('pin_state', sa.Boolean(), nullable=False),
        sa.Column('session_start_offset', sa.Float(), nullable=True),
        sa.Column('detection_sequence', sa.Integer(), nullable=True),
        sa.Column('video_offset_seconds', sa.Float(), nullable=True),
        sa.Column('matched_video_events', sa.JSON(), nullable=True),
        sa.Column('match_count', sa.Integer(), nullable=True),
        sa.Column('within_tolerance', sa.Boolean(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['detection_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for stored_detection_events  
    op.create_index(op.f('ix_stored_detection_events_session_id'), 'stored_detection_events', ['session_id'], unique=False)
    op.create_index(op.f('ix_stored_detection_events_detection_id'), 'stored_detection_events', ['detection_id'], unique=False)
    op.create_index(op.f('ix_stored_detection_events_timestamp'), 'stored_detection_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_stored_detection_events_created_at'), 'stored_detection_events', ['created_at'], unique=False)

    # Create video_events table
    op.create_table('video_events',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('video_id', sa.String(36), nullable=False),
        sa.Column('timestamp', sa.Float(), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('class_label', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('bbox_x', sa.Float(), nullable=True),
        sa.Column('bbox_y', sa.Float(), nullable=True),
        sa.Column('bbox_width', sa.Float(), nullable=True),
        sa.Column('bbox_height', sa.Float(), nullable=True),
        sa.Column('matched_detection_events', sa.JSON(), nullable=True),
        sa.Column('correlation_analysis', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for video_events
    op.create_index(op.f('ix_video_events_video_id'), 'video_events', ['video_id'], unique=False)
    op.create_index(op.f('ix_video_events_timestamp'), 'video_events', ['timestamp'], unique=False)
    op.create_index(op.f('ix_video_events_frame_number'), 'video_events', ['frame_number'], unique=False)
    op.create_index(op.f('ix_video_events_event_type'), 'video_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_video_events_class_label'), 'video_events', ['class_label'], unique=False)
    op.create_index(op.f('ix_video_events_created_at'), 'video_events', ['created_at'], unique=False)

def downgrade():
    """Remove simple detection tables"""
    
    # Drop indexes and tables in reverse order
    op.drop_index(op.f('ix_video_events_created_at'), table_name='video_events')
    op.drop_index(op.f('ix_video_events_class_label'), table_name='video_events')
    op.drop_index(op.f('ix_video_events_event_type'), table_name='video_events')
    op.drop_index(op.f('ix_video_events_frame_number'), table_name='video_events')
    op.drop_index(op.f('ix_video_events_timestamp'), table_name='video_events')
    op.drop_index(op.f('ix_video_events_video_id'), table_name='video_events')
    op.drop_table('video_events')
    
    op.drop_index(op.f('ix_stored_detection_events_created_at'), table_name='stored_detection_events')
    op.drop_index(op.f('ix_stored_detection_events_timestamp'), table_name='stored_detection_events')
    op.drop_index(op.f('ix_stored_detection_events_detection_id'), table_name='stored_detection_events')
    op.drop_index(op.f('ix_stored_detection_events_session_id'), table_name='stored_detection_events')
    op.drop_table('stored_detection_events')
    
    op.drop_index(op.f('ix_detection_sessions_created_at'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_status'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_end_time'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_start_time'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_video_id'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_project_id'), table_name='detection_sessions')
    op.drop_index(op.f('ix_detection_sessions_session_id'), table_name='detection_sessions')
    op.drop_table('detection_sessions')