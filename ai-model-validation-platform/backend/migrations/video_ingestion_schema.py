"""
Alembic migration for PRD Module 1.1 & 1.2: Video Ingestion Pipeline
Adds enhanced video status workflow and VRU tracking fields
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'video_ingestion_001'
down_revision = None
depends_on = None

def upgrade() -> None:
    """Add PRD-compliant video ingestion schema enhancements"""
    
    # Add video status enum if not exists
    video_status_enum = postgresql.ENUM(
        'pending_annotation', 'pending_validation', 'validated', 
        'processing', 'error', name='videostatus'
    )
    video_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Add VRU type enum if not exists
    vru_type_enum = postgresql.ENUM(
        'pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter',
        name='vrutype'
    )
    vru_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Enhance videos table for PRD compliance
    op.execute("""
        ALTER TABLE videos 
        ALTER COLUMN status TYPE videostatus USING status::videostatus;
    """)
    
    # Add detection_count if not exists
    try:
        op.add_column('videos', sa.Column('detection_count', sa.Integer, default=0))
    except Exception:
        pass  # Column may already exist
    
    # Add annotation_count if not exists  
    try:
        op.add_column('videos', sa.Column('annotation_count', sa.Integer, default=0))
    except Exception:
        pass
    
    # Enhance ground_truth_objects table for VRU tracking
    try:
        op.add_column('ground_truth_objects', sa.Column('tracking_id', sa.String(50), index=True))
    except Exception:
        pass
    
    # Update class_label to use VRU types
    op.execute("""
        UPDATE ground_truth_objects 
        SET class_label = CASE 
            WHEN class_label IN ('person', 'people') THEN 'pedestrian'
            WHEN class_label IN ('bike', 'bicycle') THEN 'cyclist' 
            WHEN class_label IN ('motorbike', 'motorcycle') THEN 'motorcyclist'
            ELSE class_label
        END
        WHERE class_label IS NOT NULL;
    """)
    
    # Create indexes for performance
    try:
        op.create_index('idx_videos_status_processing', 'videos', ['status', 'processing_status'])
        op.create_index('idx_videos_ground_truth_status', 'videos', ['ground_truth_generated', 'status'])
        op.create_index('idx_ground_truth_tracking_video', 'ground_truth_objects', ['video_id', 'tracking_id'])
        op.create_index('idx_ground_truth_tracking_timestamp', 'ground_truth_objects', ['tracking_id', 'timestamp'])
    except Exception:
        pass  # Indexes may already exist

def downgrade() -> None:
    """Revert video ingestion schema changes"""
    
    # Remove added columns
    try:
        op.drop_column('videos', 'detection_count')
        op.drop_column('videos', 'annotation_count')
        op.drop_column('ground_truth_objects', 'tracking_id')
    except Exception:
        pass
    
    # Remove indexes
    try:
        op.drop_index('idx_videos_status_processing', 'videos')
        op.drop_index('idx_videos_ground_truth_status', 'videos')
        op.drop_index('idx_ground_truth_tracking_video', 'ground_truth_objects')
        op.drop_index('idx_ground_truth_tracking_timestamp', 'ground_truth_objects')
    except Exception:
        pass
    
    # Remove enums (be careful about existing data)
    try:
        op.execute("DROP TYPE IF EXISTS videostatus CASCADE;")
        op.execute("DROP TYPE IF EXISTS vrutype CASCADE;")
    except Exception:
        pass