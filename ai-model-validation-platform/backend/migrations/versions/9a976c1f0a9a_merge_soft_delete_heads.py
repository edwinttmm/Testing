"""merge_soft_delete_heads

Revision ID: 9a976c1f0a9a
Revises: 002_migrate_existing_video_data, 20251031_soft_delete, add_absolute_paths_001, add_detection_indexes, eceb53b5fb42
Create Date: 2025-10-31 13:21:50.505921

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a976c1f0a9a'
down_revision = ('002_migrate_existing_video_data', '20251031_soft_delete', 'add_absolute_paths_001', 'add_detection_indexes', 'eceb53b5fb42')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass