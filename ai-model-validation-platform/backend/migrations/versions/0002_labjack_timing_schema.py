"""Add LabJack timing validation schema

Revision ID: 0002
Revises: 0001
Create Date: 2025-09-09 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add LabJack timing validation fields to existing tables."""
    
    # Add LabJack timing fields to test_sessions table
    with op.batch_alter_table('test_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latency_threshold_ms', sa.Integer(), nullable=True, default=100))
        batch_op.add_column(sa.Column('video_start_timestamp', sa.Float(), nullable=True))
        batch_op.create_index('idx_testsession_latency_threshold', ['latency_threshold_ms'])
        batch_op.create_index('idx_testsession_video_start', ['video_start_timestamp'])
    
    # Add LabJack timing fields to detection_events table
    with op.batch_alter_table('detection_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('labjack_timestamp', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('video_start_time', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('labjack_voltage', sa.Float(), nullable=True))
        
        # Create LabJack-specific indexes
        batch_op.create_index('idx_detection_latency_validation', ['latency_ms', 'validation_result'])
        batch_op.create_index('idx_detection_labjack_timestamp', ['labjack_timestamp'])
        batch_op.create_index('idx_detection_session_latency', ['test_session_id', 'latency_ms'])
        batch_op.create_index('idx_detection_video_start_time', ['video_start_time'])
        batch_op.create_index('idx_detection_labjack_voltage', ['labjack_voltage'])
        batch_op.create_index('idx_detection_session_labjack_validation', ['test_session_id', 'validation_result', 'latency_ms'])
    
    # Update test_results table with LabJack timing metrics
    with op.batch_alter_table('test_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pass_rate', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('avg_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('max_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('min_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('total_detections', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('passed_detections', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('failed_detections', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('latency_distribution', sa.JSON(), nullable=True))
        
        # Create LabJack timing analysis indexes
        batch_op.create_index('idx_testresult_session_pass_rate', ['test_session_id', 'pass_rate'])
        batch_op.create_index('idx_testresult_avg_latency', ['avg_latency_ms'])
        batch_op.create_index('idx_testresult_max_latency', ['max_latency_ms'])
        batch_op.create_index('idx_testresult_total_detections', ['total_detections'])
        batch_op.create_index('idx_testresult_session_created', ['test_session_id', 'created_at'])
        batch_op.create_index('idx_testresult_latency_range', ['min_latency_ms', 'max_latency_ms'])
        batch_op.create_index('idx_testresult_pass_fail_counts', ['passed_detections', 'failed_detections'])


def downgrade() -> None:
    """Remove LabJack timing validation fields."""
    
    # Remove LabJack timing fields from test_results table
    with op.batch_alter_table('test_results', schema=None) as batch_op:
        batch_op.drop_index('idx_testresult_pass_fail_counts')
        batch_op.drop_index('idx_testresult_latency_range')
        batch_op.drop_index('idx_testresult_session_created')
        batch_op.drop_index('idx_testresult_total_detections')
        batch_op.drop_index('idx_testresult_max_latency')
        batch_op.drop_index('idx_testresult_avg_latency')
        batch_op.drop_index('idx_testresult_session_pass_rate')
        
        batch_op.drop_column('latency_distribution')
        batch_op.drop_column('failed_detections')
        batch_op.drop_column('passed_detections')
        batch_op.drop_column('total_detections')
        batch_op.drop_column('min_latency_ms')
        batch_op.drop_column('max_latency_ms')
        batch_op.drop_column('avg_latency_ms')
        batch_op.drop_column('pass_rate')
    
    # Remove LabJack timing fields from detection_events table
    with op.batch_alter_table('detection_events', schema=None) as batch_op:
        batch_op.drop_index('idx_detection_session_labjack_validation')
        batch_op.drop_index('idx_detection_labjack_voltage')
        batch_op.drop_index('idx_detection_video_start_time')
        batch_op.drop_index('idx_detection_session_latency')
        batch_op.drop_index('idx_detection_labjack_timestamp')
        batch_op.drop_index('idx_detection_latency_validation')
        
        batch_op.drop_column('labjack_voltage')
        batch_op.drop_column('video_start_time')
        batch_op.drop_column('labjack_timestamp')
        batch_op.drop_column('latency_ms')
    
    # Remove LabJack timing fields from test_sessions table
    with op.batch_alter_table('test_sessions', schema=None) as batch_op:
        batch_op.drop_index('idx_testsession_video_start')
        batch_op.drop_index('idx_testsession_latency_threshold')
        
        batch_op.drop_column('video_start_timestamp')
        batch_op.drop_column('latency_threshold_ms')