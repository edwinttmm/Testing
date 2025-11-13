"""Add performance indexes for video_id_resolver

Revision ID: add_video_timing_indexes
Revises: previous_migration
Create Date: 2025-11-07

This migration adds composite indexes to support <5ms query performance
for the video_id_resolver service.

Critical indexes:
1. idx_sequence_video_timing - Composite index on (video_sequence_id, video_start_time, video_end_time)
2. idx_sequence_video_session_timing - Join optimization for session-based queries

Expected performance improvement:
- Without indexes: 50-200ms query time
- With indexes: <5ms query time
- 10-40x speedup for timestamp-based video lookup
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_video_timing_indexes'
down_revision = None  # Update with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for video_id resolution"""

    # Critical composite index for timestamp-based video lookup
    # Used by: get_video_id_for_detection()
    # Query pattern: WHERE video_sequence_id = X AND video_start_time <= Y AND video_end_time > Y
    op.create_index(
        'idx_sequence_video_timing',
        'sequence_video_results',
        ['video_sequence_id', 'video_start_time', 'video_end_time'],
        unique=False
    )

    # Composite index for sequence-session joins
    # Used by: Join queries from TestSession to SequenceVideoResult
    op.create_index(
        'idx_video_sequence_session_timing',
        'video_test_sequences',
        ['test_session_id', 'status'],
        unique=False
    )

    # Index for video_id lookups in sequence results
    # Used by: get_sequence_video_result_id()
    op.create_index(
        'idx_sequence_video_result_video_lookup',
        'sequence_video_results',
        ['video_sequence_id', 'video_id'],
        unique=False
    )

    print("✅ Added video_id_resolver performance indexes")
    print("   Expected query performance: <5ms")
    print("   Coverage: Multi-video timestamp resolution queries")


def downgrade():
    """Remove performance indexes"""

    op.drop_index('idx_sequence_video_timing', table_name='sequence_video_results')
    op.drop_index('idx_video_sequence_session_timing', table_name='video_test_sequences')
    op.drop_index('idx_sequence_video_result_video_lookup', table_name='sequence_video_results')

    print("✅ Removed video_id_resolver performance indexes")
