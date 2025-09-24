"""Add video timing synchronization for HIL tests

Revision ID: add_video_timing_sync
Revises: 
Create Date: 2025-09-16

This migration adds video timing synchronization columns to support
proper ground truth matching in HIL (Hardware-in-the-Loop) tests.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging

# Configure logging
logger = logging.getLogger(__name__)

# revision identifiers
revision = 'add_video_timing_sync'
down_revision = None  # Set to None since this is a new migration
branch_labels = None
depends_on = None


def upgrade():
    """
    Add video timing synchronization columns to test_sessions and detection_events tables.
    
    This enables proper video playback start time capture and video-relative timestamp
    calculation for accurate ground truth matching in HIL validation tests.
    """
    try:
        logger.info("Starting video timing synchronization migration...")
        
        # Add video timing columns to test_sessions table
        logger.info("Adding video timing columns to test_sessions table...")
        
        # Check if columns already exist before adding them
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        
        # Get existing columns for test_sessions table
        existing_columns = {col['name'] for col in inspector.get_columns('test_sessions')}
        
        if 'video_playback_start_time' not in existing_columns:
            op.add_column('test_sessions', 
                sa.Column('video_playback_start_time', sa.DOUBLE_PRECISION, nullable=True,
                         comment='Unix timestamp when video playback started for HIL test'))
            logger.info("Added video_playback_start_time column to test_sessions")
        
        if 'video_playback_start_time_ns' not in existing_columns:
            op.add_column('test_sessions', 
                sa.Column('video_playback_start_time_ns', sa.String(), nullable=True,
                         comment='Nanosecond precision video start timestamp for HIL timing'))
            logger.info("Added video_playback_start_time_ns column to test_sessions")
        
        if 'hil_timing_enabled' not in existing_columns:
            op.add_column('test_sessions', 
                sa.Column('hil_timing_enabled', sa.Boolean(), nullable=True, default=True,
                         comment='Whether HIL timing synchronization is enabled'))
            logger.info("Added hil_timing_enabled column to test_sessions")
        
        if 'video_timing_sync_status' not in existing_columns:
            op.add_column('test_sessions', 
                sa.Column('video_timing_sync_status', sa.String(), nullable=True, default='pending',
                         comment='Status of video timing synchronization: pending, synced, failed'))
            logger.info("Added video_timing_sync_status column to test_sessions")
        
        # Add video timing columns to detection_events table
        logger.info("Adding video timing columns to detection_events table...")
        
        # Get existing columns for detection_events table
        existing_de_columns = {col['name'] for col in inspector.get_columns('detection_events')}
        
        if 'video_relative_timestamp' not in existing_de_columns:
            op.add_column('detection_events', 
                sa.Column('video_relative_timestamp', sa.DOUBLE_PRECISION, nullable=True,
                         comment='Timestamp relative to video start (seconds) for ground truth matching'))
            logger.info("Added video_relative_timestamp column to detection_events")
        
        if 'video_relative_timestamp_ns' not in existing_de_columns:
            op.add_column('detection_events', 
                sa.Column('video_relative_timestamp_ns', sa.String(), nullable=True,
                         comment='Nanosecond precision video-relative timestamp'))
            logger.info("Added video_relative_timestamp_ns column to detection_events")
        
        if 'actual_latency_ms' not in existing_de_columns:
            op.add_column('detection_events', 
                sa.Column('actual_latency_ms', sa.DOUBLE_PRECISION, nullable=True,
                         comment='Actual measured latency from video start to detection (milliseconds)'))
            logger.info("Added actual_latency_ms column to detection_events")
        
        if 'video_frame_number' not in existing_de_columns:
            op.add_column('detection_events', 
                sa.Column('video_frame_number', sa.Integer(), nullable=True,
                         comment='Video frame number corresponding to detection time'))
            logger.info("Added video_frame_number column to detection_events")
        
        if 'timing_sync_quality' not in existing_de_columns:
            op.add_column('detection_events', 
                sa.Column('timing_sync_quality', sa.String(), nullable=True, default='unknown',
                         comment='Quality of timing synchronization: high, medium, low, unknown'))
            logger.info("Added timing_sync_quality column to detection_events")
        
        # Create indexes for better query performance
        logger.info("Creating indexes for video timing queries...")
        
        try:
            op.create_index('idx_test_sessions_video_start_time', 'test_sessions', 
                          ['video_playback_start_time'], if_not_exists=True)
            logger.info("Created index on video_playback_start_time")
        except Exception as e:
            logger.warning(f"Index creation skipped (may already exist): {e}")
        
        try:
            op.create_index('idx_test_sessions_hil_timing', 'test_sessions', 
                          ['hil_timing_enabled', 'video_timing_sync_status'], if_not_exists=True)
            logger.info("Created composite index on HIL timing fields")
        except Exception as e:
            logger.warning(f"Index creation skipped (may already exist): {e}")
        
        try:
            op.create_index('idx_detection_events_video_relative', 'detection_events', 
                          ['video_relative_timestamp'], if_not_exists=True)
            logger.info("Created index on video_relative_timestamp")
        except Exception as e:
            logger.warning(f"Index creation skipped (may already exist): {e}")
        
        try:
            op.create_index('idx_detection_events_actual_latency', 'detection_events', 
                          ['actual_latency_ms'], if_not_exists=True)
            logger.info("Created index on actual_latency_ms")
        except Exception as e:
            logger.warning(f"Index creation skipped (may already exist): {e}")
        
        try:
            op.create_index('idx_detection_events_timing_quality', 'detection_events', 
                          ['timing_sync_quality'], if_not_exists=True)
            logger.info("Created index on timing_sync_quality")
        except Exception as e:
            logger.warning(f"Index creation skipped (may already exist): {e}")
        
        logger.info("Video timing synchronization migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during video timing migration: {e}")
        raise


def downgrade():
    """
    Remove video timing synchronization columns.
    
    WARNING: This will permanently delete video timing data!
    """
    try:
        logger.info("Starting video timing synchronization downgrade...")
        
        # Drop indexes first
        logger.info("Dropping video timing indexes...")
        
        indexes_to_drop = [
            'idx_detection_events_timing_quality',
            'idx_detection_events_actual_latency', 
            'idx_detection_events_video_relative',
            'idx_test_sessions_hil_timing',
            'idx_test_sessions_video_start_time'
        ]
        
        for index_name in indexes_to_drop:
            try:
                op.drop_index(index_name, if_exists=True)
                logger.info(f"Dropped index: {index_name}")
            except Exception as e:
                logger.warning(f"Failed to drop index {index_name}: {e}")
        
        # Drop columns from detection_events table
        logger.info("Removing video timing columns from detection_events table...")
        
        detection_columns_to_drop = [
            'timing_sync_quality',
            'video_frame_number', 
            'actual_latency_ms',
            'video_relative_timestamp_ns',
            'video_relative_timestamp'
        ]
        
        for column_name in detection_columns_to_drop:
            try:
                op.drop_column('detection_events', column_name)
                logger.info(f"Dropped column: detection_events.{column_name}")
            except Exception as e:
                logger.warning(f"Failed to drop column {column_name}: {e}")
        
        # Drop columns from test_sessions table
        logger.info("Removing video timing columns from test_sessions table...")
        
        session_columns_to_drop = [
            'video_timing_sync_status',
            'hil_timing_enabled',
            'video_playback_start_time_ns',
            'video_playback_start_time'
        ]
        
        for column_name in session_columns_to_drop:
            try:
                op.drop_column('test_sessions', column_name)
                logger.info(f"Dropped column: test_sessions.{column_name}")
            except Exception as e:
                logger.warning(f"Failed to drop column {column_name}: {e}")
        
        logger.info("Video timing synchronization downgrade completed!")
        
    except Exception as e:
        logger.error(f"Error during video timing downgrade: {e}")
        raise