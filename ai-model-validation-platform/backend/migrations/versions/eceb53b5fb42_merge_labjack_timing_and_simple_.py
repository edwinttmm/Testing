"""Merge LabJack timing and simple detection schemas

Revision ID: eceb53b5fb42
Revises: 0002, simple_detection_001
Create Date: 2025-09-09 10:48:20.527599

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eceb53b5fb42'
down_revision = ('0002', 'simple_detection_001')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass