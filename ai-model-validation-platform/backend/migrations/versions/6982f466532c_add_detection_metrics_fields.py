"""add_detection_metrics_fields

Revision ID: 6982f466532c
Revises: 20251111_dual_eval
Create Date: 2025-11-11 13:18:02.619970

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6982f466532c'
down_revision = '20251111_dual_eval'
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col['name'] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    """Add missing detection summary fields to test_sessions."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    def add_column(name: str, column: sa.Column):
        if not _column_exists(inspector, 'test_sessions', name):
            op.add_column('test_sessions', column)

    add_column('test_configuration', sa.Column('test_configuration', sa.JSON(), nullable=True))
    add_column('expected_detections', sa.Column('expected_detections', sa.Integer(), nullable=True))
    add_column('actual_detections', sa.Column('actual_detections', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Remove detection summary fields if present."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    def drop_column(name: str):
        if _column_exists(inspector, 'test_sessions', name):
            op.drop_column('test_sessions', name)

    for column_name in ('actual_detections', 'expected_detections', 'test_configuration'):
        drop_column(column_name)
