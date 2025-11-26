"""add is_false_positive field to detection_events

Revision ID: 20251125_is_false_positive
Revises: 20251121_drift_compensation
Create Date: 2025-11-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251125_is_false_positive'
down_revision = '20251121_drift_compensation'
branch_labels = None
depends_on = None


def upgrade():
    """Add is_false_positive Boolean field to replace 10000ms sentinel value approach"""

    # Add is_false_positive column with default False
    op.add_column('detection_events',
        sa.Column('is_false_positive', sa.Boolean(),
                  nullable=False, server_default='0',
                  comment='TRUE if detection is a False Positive. Replaces 10000ms sentinel value in actual_latency_ms.')
    )

    # Create index for filtering False Positives
    op.create_index(
        'ix_detection_events_is_false_positive',
        'detection_events',
        ['is_false_positive']
    )

    # Data Migration Step 1: Mark detections with actual_latency_ms >= 10000 as False Positives
    op.execute('''
        UPDATE detection_events
        SET is_false_positive = 1
        WHERE actual_latency_ms >= 10000
    ''')

    # Data Migration Step 2: Update actual_latency_ms for False Positives to NULL
    # This allows the calculator to compute the REAL latency value
    op.execute('''
        UPDATE detection_events
        SET actual_latency_ms = NULL
        WHERE is_false_positive = 1
    ''')

    # Add composite index for common query patterns
    op.create_index(
        'ix_detection_events_session_is_fp',
        'detection_events',
        ['test_session_id', 'is_false_positive']
    )

    op.create_index(
        'ix_detection_events_validation_is_fp',
        'detection_events',
        ['validation_result', 'is_false_positive']
    )


def downgrade():
    """Remove is_false_positive field and restore 10000ms sentinel values"""

    # Restore 10000ms marker for False Positives before dropping the column
    op.execute('''
        UPDATE detection_events
        SET actual_latency_ms = 10000
        WHERE is_false_positive = 1
    ''')

    # Drop indexes
    op.drop_index('ix_detection_events_validation_is_fp', 'detection_events')
    op.drop_index('ix_detection_events_session_is_fp', 'detection_events')
    op.drop_index('ix_detection_events_is_false_positive', 'detection_events')

    # Drop column
    op.drop_column('detection_events', 'is_false_positive')
