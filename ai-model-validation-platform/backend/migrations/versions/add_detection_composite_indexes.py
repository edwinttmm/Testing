"""Add composite indexes for detection events to optimize N+1 query patterns

Revision ID: add_detection_indexes
Revises: 0003_latency_validation_schema
Create Date: 2025-10-31
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = 'add_detection_indexes'
down_revision = '0003_latency_validation_schema'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite indexes for common query patterns"""

    with op.batch_alter_table('detection_events', schema=None) as batch_op:
        # Session + Video + Timestamp - Used in HIL results queries
        batch_op.create_index(
            'idx_detection_session_video_timestamp',
            ['test_session_id', 'video_id', 'timestamp'],
            unique=False
        )

        # Session + Validation + Latency - Used in results filtering
        batch_op.create_index(
            'idx_detection_session_validation_latency',
            ['test_session_id', 'validation_result', 'actual_latency_ms'],
            unique=False
        )

        # Video + Ground Truth Match - Used in matching queries
        batch_op.create_index(
            'idx_detection_video_gt_match',
            ['video_id', 'ground_truth_match_id'],
            unique=False
        )

        # Sequence + Video + Timestamp - Used in multi-video sequences
        batch_op.create_index(
            'idx_detection_sequence_video_timestamp',
            ['sequence_id', 'video_id', 'timestamp'],
            unique=False
        )

        # Session + LabJack filters - Used in LabJack event queries
        batch_op.create_index(
            'idx_detection_session_labjack',
            ['test_session_id', 'labjack_voltage', 'labjack_timestamp'],
            unique=False
        )


def downgrade():
    """Remove composite indexes"""

    with op.batch_alter_table('detection_events', schema=None) as batch_op:
        batch_op.drop_index('idx_detection_session_video_timestamp')
        batch_op.drop_index('idx_detection_session_validation_latency')
        batch_op.drop_index('idx_detection_video_gt_match')
        batch_op.drop_index('idx_detection_sequence_video_timestamp')
        batch_op.drop_index('idx_detection_session_labjack')
