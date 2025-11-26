"""Add quality tracking fields to detection_events

Revision ID: quality_tracking_001
Revises:
Create Date: 2025-01-25

This migration adds quality tracking fields to the detection_events table to
properly store quality assessment results and fix the usable_for_validation contradiction.

New Fields:
- quality_category: Overall quality classification
- quality_validation_suitability: Validation suitability assessment
- quality_confidence_score: Quality assessment confidence
- quality_notes: Human-readable quality notes
- timing_clamped: Flag for clamped timing
- original_video_relative: Original unclamped timestamp
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'quality_tracking_001'
down_revision = None  # Set to previous migration ID
branch_labels = None
depends_on = None


def upgrade():
    """Add quality tracking fields"""
    # Add quality tracking columns
    op.add_column('detection_events',
                  sa.Column('quality_category', sa.String(), nullable=True))
    op.add_column('detection_events',
                  sa.Column('quality_validation_suitability', sa.String(), nullable=True))
    op.add_column('detection_events',
                  sa.Column('quality_confidence_score', sa.Float(), nullable=True))
    op.add_column('detection_events',
                  sa.Column('quality_notes', sa.Text(), nullable=True))
    op.add_column('detection_events',
                  sa.Column('timing_clamped', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('detection_events',
                  sa.Column('original_video_relative', sa.Float(), nullable=True))

    # Create indexes for efficient querying
    op.create_index('idx_detection_quality_category', 'detection_events', ['quality_category'])
    op.create_index('idx_detection_quality_suitability', 'detection_events', ['quality_validation_suitability'])
    op.create_index('idx_detection_timing_clamped', 'detection_events', ['timing_clamped'])
    op.create_index('idx_detection_usable_quality', 'detection_events', ['usable_for_validation', 'quality_category'])

    print("✅ Added quality tracking fields to detection_events")


def downgrade():
    """Remove quality tracking fields"""
    # Drop indexes
    op.drop_index('idx_detection_usable_quality', table_name='detection_events')
    op.drop_index('idx_detection_timing_clamped', table_name='detection_events')
    op.drop_index('idx_detection_quality_suitability', table_name='detection_events')
    op.drop_index('idx_detection_quality_category', table_name='detection_events')

    # Drop columns
    op.drop_column('detection_events', 'original_video_relative')
    op.drop_column('detection_events', 'timing_clamped')
    op.drop_column('detection_events', 'quality_notes')
    op.drop_column('detection_events', 'quality_confidence_score')
    op.drop_column('detection_events', 'quality_validation_suitability')
    op.drop_column('detection_events', 'quality_category')

    print("✅ Removed quality tracking fields from detection_events")
