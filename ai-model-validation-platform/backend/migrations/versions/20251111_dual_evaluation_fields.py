"""Add dual evaluation fields to test_sessions.

Revision ID: 20251111_dual_eval
Revises: 20251111_merge_all
Create Date: 2025-11-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251111_dual_eval'
down_revision = '20251111_merge_all'
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col['name'] for col in inspector.get_columns(table_name)}


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {idx['name'] for idx in inspector.get_indexes(table_name)}


def upgrade():
    """Add dual evaluation + supporting fields to test_sessions."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Helper to add a column only when it is missing (supports partially upgraded DBs)
    def add_column(name: str, column: sa.Column):
        if not _column_exists(inspector, 'test_sessions', name):
            op.add_column('test_sessions', column)

    add_column('pass_fail_result', sa.Column('pass_fail_result', sa.String(), nullable=True, server_default='pending'))
    add_column('overall_score', sa.Column('overall_score', sa.Float(), nullable=True))

    # Accuracy metrics
    add_column('accuracy_result', sa.Column('accuracy_result', sa.String(), nullable=True, server_default='pending'))
    add_column('accuracy_f1_score', sa.Column('accuracy_f1_score', sa.Float(), nullable=True))
    add_column('accuracy_precision', sa.Column('accuracy_precision', sa.Float(), nullable=True))
    add_column('accuracy_recall', sa.Column('accuracy_recall', sa.Float(), nullable=True))
    add_column('accuracy_details', sa.Column('accuracy_details', sa.JSON(), nullable=True))

    # Latency metrics
    add_column('latency_result', sa.Column('latency_result', sa.String(), nullable=True, server_default='pending'))
    add_column('latency_mean_ms', sa.Column('latency_mean_ms', sa.Float(), nullable=True))
    add_column('latency_max_ms', sa.Column('latency_max_ms', sa.Float(), nullable=True))
    add_column(
        'latency_percent_within_threshold',
        sa.Column('latency_percent_within_threshold', sa.Float(), nullable=True)
    )
    add_column('latency_details', sa.Column('latency_details', sa.JSON(), nullable=True))

    # Overall aggregation
    add_column(
        'overall_test_result',
        sa.Column('overall_test_result', sa.String(), nullable=True, server_default='pending')
    )
    add_column('overall_details', sa.Column('overall_details', sa.JSON(), nullable=True))

    # Counts for transparency
    add_column('tp_count', sa.Column('tp_count', sa.Integer(), nullable=True))
    add_column('fp_count', sa.Column('fp_count', sa.Integer(), nullable=True))
    add_column('fn_count', sa.Column('fn_count', sa.Integer(), nullable=True))

    # Create indexes when missing
    def add_index(name: str, columns: list[str]):
        if not _index_exists(inspector, 'test_sessions', name):
            op.create_index(name, 'test_sessions', columns)

    add_index('idx_testsession_pass_fail_result', ['pass_fail_result'])
    add_index('idx_testsession_accuracy_result', ['accuracy_result'])
    add_index('idx_testsession_latency_result', ['latency_result'])
    add_index('idx_testsession_overall_result', ['overall_test_result'])
    add_index('idx_testsession_accuracy_f1', ['accuracy_f1_score'])
    add_index('idx_testsession_latency_mean', ['latency_mean_ms'])
    add_index('idx_testsession_tp_count', ['tp_count'])


def downgrade():
    """Remove dual evaluation fields from test_sessions."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    def drop_index(name: str):
        if _index_exists(inspector, 'test_sessions', name):
            op.drop_index(name, table_name='test_sessions')

    drop_index('idx_testsession_tp_count')
    drop_index('idx_testsession_latency_mean')
    drop_index('idx_testsession_accuracy_f1')
    drop_index('idx_testsession_overall_result')
    drop_index('idx_testsession_latency_result')
    drop_index('idx_testsession_accuracy_result')
    drop_index('idx_testsession_pass_fail_result')

    def drop_column(name: str):
        if _column_exists(inspector, 'test_sessions', name):
            op.drop_column('test_sessions', name)

    for column_name in [
        'fn_count',
        'fp_count',
        'tp_count',
        'overall_details',
        'overall_test_result',
        'latency_details',
        'latency_percent_within_threshold',
        'latency_max_ms',
        'latency_mean_ms',
        'latency_result',
        'accuracy_details',
        'accuracy_recall',
        'accuracy_precision',
        'accuracy_f1_score',
        'accuracy_result',
        'overall_score',
        'pass_fail_result',
    ]:
        drop_column(column_name)
