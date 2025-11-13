"""Add dual-evaluation fields for separate accuracy and latency assessment

Revision ID: a1b2c3d4e5f6
Revises: 950b4c965ca9
Create Date: 2025-11-11 15:05:00.000000

This migration adds dual-evaluation fields to test_sessions to enable separate
assessment of accuracy (detection correctness) and latency (timing performance).
This separation is critical for HIL validation where a system can have excellent
detection accuracy but fail latency requirements, or vice versa.

Key additions:
- accuracy_result: PASS/CONDITIONAL_PASS/FAIL based on F1 score
- latency_result: PASS/CONDITIONAL_PASS/FAIL/N_A based on timing
- evaluation_details: JSON field with detailed reasoning and metrics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '950b4c965ca9'
branch_labels = None
depends_on = None


def upgrade():
    """Add dual-evaluation fields to test_sessions."""
    # Note: Some fields may already exist from models.py schema
    # We use try/except to handle this gracefully

    # Check existing columns to avoid duplicates
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('test_sessions')]

    # Add evaluation_details JSON field (NEW - definitely doesn't exist)
    if 'evaluation_details' not in existing_columns:
        op.add_column(
            'test_sessions',
            sa.Column(
                'evaluation_details',
                sa.JSON(),
                nullable=True,
                comment='Detailed evaluation metrics, reasoning, and threshold data'
            )
        )

    # Note: accuracy_result, latency_result, accuracy_f1_score, latency_mean_ms
    # already exist in the TestSession model (lines 242-253 in models.py)
    # So we skip adding them to avoid migration conflicts

    # Backfill existing sessions with migrated evaluation data
    # For old sessions, derive separate evaluations from pass_fail_result
    # This provides backward compatibility while enabling new dual-evaluation logic
    op.execute("""
        UPDATE test_sessions
        SET evaluation_details = json_object(
            'migrated', 1,
            'original_result', pass_fail_result,
            'migration_date', datetime('now'),
            'accuracy_threshold', 0.80,
            'latency_threshold_ms', latency_threshold_ms,
            'notes', 'Migrated from legacy pass_fail_result system'
        )
        WHERE evaluation_details IS NULL
          AND created_at < '2025-11-11'
    """)

    # Create indexes for filtering/reporting by evaluation results
    if 'idx_test_sessions_evaluation_details' not in [idx['name'] for idx in inspector.get_indexes('test_sessions')]:
        # Note: Can't index JSON directly in SQLite, but we can add it for PostgreSQL
        # SQLite will simply ignore this for the JSON type
        try:
            op.create_index(
                'idx_test_sessions_evaluation_details',
                'test_sessions',
                ['evaluation_details'],
                unique=False,
                postgresql_using='gin'  # GIN index for PostgreSQL JSON queries
            )
        except Exception:
            # Skip if database doesn't support JSON indexing
            pass

    # Composite index for dual-evaluation filtering
    # This enables fast queries like "show all sessions with PASS accuracy but FAIL latency"
    if 'idx_test_sessions_dual_eval' not in [idx['name'] for idx in inspector.get_indexes('test_sessions')]:
        op.create_index(
            'idx_test_sessions_dual_eval',
            'test_sessions',
            ['accuracy_result', 'latency_result', 'overall_test_result'],
            unique=False
        )


def downgrade():
    """Remove dual-evaluation fields."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_indexes = [idx['name'] for idx in inspector.get_indexes('test_sessions')]

    # Drop indexes
    if 'idx_test_sessions_dual_eval' in existing_indexes:
        op.drop_index('idx_test_sessions_dual_eval', table_name='test_sessions')

    if 'idx_test_sessions_evaluation_details' in existing_indexes:
        try:
            op.drop_index('idx_test_sessions_evaluation_details', table_name='test_sessions')
        except Exception:
            pass

    # Drop evaluation_details column (the only new column we added)
    existing_columns = [col['name'] for col in inspector.get_columns('test_sessions')]
    if 'evaluation_details' in existing_columns:
        op.drop_column('test_sessions', 'evaluation_details')

    # Note: We DO NOT drop accuracy_result, latency_result, etc.
    # because they already existed in the model before this migration
