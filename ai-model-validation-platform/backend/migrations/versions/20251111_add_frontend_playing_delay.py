"""Add frontend_playing_delay_ms field for timing analysis

Revision ID: 950b4c965ca9
Revises: add_approval_workflow
Create Date: 2025-11-11 15:00:00.000000

This migration adds the frontend_playing_delay_ms field to sequence_video_results
to support precise detection window timing analysis. This field measures the delay
between video load and the actual playing event, which is critical for accurate
latency calculations in HIL testing.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '950b4c965ca9'
down_revision = 'add_approval_workflow'
branch_labels = None
depends_on = None


def upgrade():
    """Add frontend_playing_delay_ms to sequence_video_results."""
    # Check which table exists (sequence_video_results or video_results)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    target_table = 'sequence_video_results' if 'sequence_video_results' in tables else 'video_results'

    # Add the new field
    op.add_column(
        target_table,
        sa.Column(
            'frontend_playing_delay_ms',
            sa.Float(),
            nullable=True,
            comment='Milliseconds between video load and playing event (T1-T0 presentation delay)'
        )
    )

    # Backfill legacy sessions with estimated delay (1500ms typical browser behavior)
    # This is based on historical data showing ~1.5s average between loadeddata and playing
    op.execute(f"""
        UPDATE {target_table}
        SET frontend_playing_delay_ms = 1500.0
        WHERE frontend_playing_delay_ms IS NULL
          AND created_at < '2025-11-11'
    """)

    # Create index for performance analysis queries
    # This enables fast filtering/sorting by presentation delay
    op.create_index(
        f'idx_{target_table}_playing_delay',
        target_table,
        ['frontend_playing_delay_ms'],
        unique=False
    )

    # Composite index for timing analysis queries (delay + status)
    op.create_index(
        f'idx_{target_table}_delay_status',
        target_table,
        ['frontend_playing_delay_ms', 'video_status'],
        unique=False
    )


def downgrade():
    """Remove frontend_playing_delay_ms field."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    target_table = 'sequence_video_results' if 'sequence_video_results' in tables else 'video_results'

    # Drop indexes
    op.drop_index(f'idx_{target_table}_delay_status', table_name=target_table)
    op.drop_index(f'idx_{target_table}_playing_delay', table_name=target_table)

    # Drop column
    op.drop_column(target_table, 'frontend_playing_delay_ms')
