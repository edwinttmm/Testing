"""
Database Migration: Add Detection Quality Fields

Adds timing_degraded and usable_for_validation fields to DetectionEvent model
for filtering out non-validated detections in ground truth matching.

Run with: python migrations/add_detection_quality_fields.py
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def upgrade():
    """Add timing quality fields to detection_events table"""

    logger.info("Adding detection quality fields to detection_events table...")

    try:
        # Add timing_degraded column
        op.add_column('detection_events',
            sa.Column('timing_degraded', sa.Boolean(), nullable=False, server_default='false')
        )
        logger.info("✅ Added timing_degraded column")

        # Add usable_for_validation column
        op.add_column('detection_events',
            sa.Column('usable_for_validation', sa.Boolean(), nullable=False, server_default='true')
        )
        logger.info("✅ Added usable_for_validation column")

        # Create indexes for performance
        op.create_index('idx_detection_timing_degraded', 'detection_events', ['timing_degraded'])
        logger.info("✅ Created index on timing_degraded")

        op.create_index('idx_detection_usable', 'detection_events', ['usable_for_validation'])
        logger.info("✅ Created index on usable_for_validation")

        # Composite index for filtering
        op.create_index('idx_detection_quality_session', 'detection_events',
                       ['test_session_id', 'usable_for_validation', 'timing_degraded'])
        logger.info("✅ Created composite quality index")

        logger.info("Migration completed successfully")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


def downgrade():
    """Remove timing quality fields from detection_events table"""

    logger.info("Removing detection quality fields from detection_events table...")

    try:
        # Drop indexes first
        op.drop_index('idx_detection_quality_session', 'detection_events')
        op.drop_index('idx_detection_usable', 'detection_events')
        op.drop_index('idx_detection_timing_degraded', 'detection_events')
        logger.info("✅ Dropped indexes")

        # Drop columns
        op.drop_column('detection_events', 'usable_for_validation')
        op.drop_column('detection_events', 'timing_degraded')
        logger.info("✅ Dropped columns")

        logger.info("Downgrade completed successfully")

    except Exception as e:
        logger.error(f"Downgrade failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    """Run migration directly"""
    from database import engine

    logging.basicConfig(level=logging.INFO)

    logger.info("Running detection quality fields migration...")

    with engine.begin() as connection:
        op.execute = connection.execute
        op.add_column = lambda table, column: connection.execute(
            text(f"ALTER TABLE {table} ADD COLUMN {column.compile(connection)}")
        )
        op.create_index = lambda name, table, cols: connection.execute(
            text(f"CREATE INDEX {name} ON {table} ({', '.join(cols)})")
        )

        upgrade()

    logger.info("Migration completed - detection quality fields added successfully")
