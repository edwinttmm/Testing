"""
Latency Validation Schema Migration

This migration adds latency-based validation fields to support LabJack timing validation.
Adds latency_ms, validation_result, threshold_ms, and video_start_time to stored_detection_events.
Updates test_results table with comprehensive latency metrics fields.

Revision ID: 0003_latency_validation_schema
Revises: 0002
Create Date: 2025-09-09 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0003_latency_validation_schema'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    """Add latency validation fields to stored_detection_events and update test_results"""
    
    # Add latency validation fields to stored_detection_events
    with op.batch_alter_table('stored_detection_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('validation_result', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('threshold_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('video_start_time', sa.Float(), nullable=True))
        
        # Add indexes for performance
        batch_op.create_index('idx_stored_detection_latency_ms', ['latency_ms'])
        batch_op.create_index('idx_stored_detection_validation_result', ['validation_result'])
    
    # Add comprehensive latency validation fields to test_results
    with op.batch_alter_table('test_results', schema=None) as batch_op:
        # Primary latency metrics
        batch_op.add_column(sa.Column('pass_rate', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('avg_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('max_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('min_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('median_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('std_dev_latency_ms', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('total_detections', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('passed_detections', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('failed_detections', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('threshold_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('latency_distribution', sa.JSON(), nullable=True))
        
        # Validation metadata
        batch_op.add_column(sa.Column('validation_type', sa.String(length=50), nullable=True, default='latency_based'))
        batch_op.add_column(sa.Column('test_duration_seconds', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('detection_rate_hz', sa.Float(), nullable=True))
        
        # Add indexes for latency-based queries
        batch_op.create_index('idx_test_results_pass_rate', ['pass_rate'])
        batch_op.create_index('idx_test_results_avg_latency', ['avg_latency_ms'])
        batch_op.create_index('idx_test_results_max_latency', ['max_latency_ms'])
        batch_op.create_index('idx_test_results_min_latency', ['min_latency_ms'])
        batch_op.create_index('idx_test_results_median_latency', ['median_latency_ms'])
        batch_op.create_index('idx_test_results_std_dev_latency', ['std_dev_latency_ms'])
        batch_op.create_index('idx_test_results_total_detections', ['total_detections'])
        batch_op.create_index('idx_test_results_passed_detections', ['passed_detections'])
        batch_op.create_index('idx_test_results_failed_detections', ['failed_detections'])
        batch_op.create_index('idx_test_results_threshold_ms', ['threshold_ms'])
        batch_op.create_index('idx_test_results_validation_type', ['validation_type'])


def downgrade():
    """Remove latency validation fields"""
    
    # Remove latency fields from stored_detection_events
    with op.batch_alter_table('stored_detection_events', schema=None) as batch_op:
        batch_op.drop_index('idx_stored_detection_validation_result', table_name='stored_detection_events')
        batch_op.drop_index('idx_stored_detection_latency_ms', table_name='stored_detection_events')
        batch_op.drop_column('video_start_time')
        batch_op.drop_column('threshold_ms')
        batch_op.drop_column('validation_result')
        batch_op.drop_column('latency_ms')
    
    # Remove latency fields from test_results
    with op.batch_alter_table('test_results', schema=None) as batch_op:
        # Drop indexes first
        batch_op.drop_index('idx_test_results_validation_type', table_name='test_results')
        batch_op.drop_index('idx_test_results_threshold_ms', table_name='test_results')
        batch_op.drop_index('idx_test_results_failed_detections', table_name='test_results')
        batch_op.drop_index('idx_test_results_passed_detections', table_name='test_results')
        batch_op.drop_index('idx_test_results_total_detections', table_name='test_results')
        batch_op.drop_index('idx_test_results_std_dev_latency', table_name='test_results')
        batch_op.drop_index('idx_test_results_median_latency', table_name='test_results')
        batch_op.drop_index('idx_test_results_min_latency', table_name='test_results')
        batch_op.drop_index('idx_test_results_max_latency', table_name='test_results')
        batch_op.drop_index('idx_test_results_avg_latency', table_name='test_results')
        batch_op.drop_index('idx_test_results_pass_rate', table_name='test_results')
        
        # Drop columns
        batch_op.drop_column('detection_rate_hz')
        batch_op.drop_column('test_duration_seconds')
        batch_op.drop_column('validation_type')
        batch_op.drop_column('latency_distribution')
        batch_op.drop_column('threshold_ms')
        batch_op.drop_column('failed_detections')
        batch_op.drop_column('passed_detections')
        batch_op.drop_column('total_detections')
        batch_op.drop_column('std_dev_latency_ms')
        batch_op.drop_column('median_latency_ms')
        batch_op.drop_column('min_latency_ms')
        batch_op.drop_column('max_latency_ms')
        batch_op.drop_column('avg_latency_ms')
        batch_op.drop_column('pass_rate')