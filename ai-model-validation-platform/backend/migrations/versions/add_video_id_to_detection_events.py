"""add video_id to detection_events

Revision ID: add_video_id_001
Revises:
Create Date: 2025-11-14

BUG #3 FIX: Add video_id column to detection_events table for accurate per-video detection counting.
This allows proper aggregation of detections by video_id during multi-video sequence testing.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_video_id_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add video_id column and foreign key to detection_events table."""
    # Check if column already exists (idempotent migration)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('detection_events')]

    if 'video_id' not in columns:
        # Add video_id column
        op.add_column('detection_events', sa.Column('video_id', sa.String(), nullable=True))

        # Add foreign key constraint
        op.create_foreign_key(
            'fk_detection_events_video_id',
            'detection_events',
            'videos',
            ['video_id'],
            ['id'],
            ondelete='CASCADE'
        )

        # Add index for query performance
        op.create_index('idx_detection_video_id', 'detection_events', ['video_id'])

        print("✅ Migration complete: video_id column added to detection_events")
    else:
        print("⚠️ Migration skipped: video_id column already exists")


def downgrade():
    """Remove video_id column and foreign key from detection_events table."""
    # Drop index first
    op.drop_index('idx_detection_video_id', table_name='detection_events')

    # Drop foreign key constraint
    op.drop_constraint('fk_detection_events_video_id', 'detection_events', type_='foreignkey')

    # Drop column
    op.drop_column('detection_events', 'video_id')

    print("✅ Downgrade complete: video_id column removed from detection_events")
