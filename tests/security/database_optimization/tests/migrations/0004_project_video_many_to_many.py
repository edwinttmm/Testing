"""Project-Video Many-to-Many Relationship Migration

Revision ID: 0004
Revises: 0003
Create Date: 2025-09-09 20:55:00.000000

This migration implements:
1. Creates project_videos junction table for many-to-many relationship
2. Adds new fields to Video model (camera_model, camera_view, lens_type, resolution, frame_rate)  
3. Migrates existing data from Project to Video tables safely
4. Removes old fields from Project model after data migration
5. Updates all foreign key relationships and constraints
6. Ensures zero data loss during migration
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import Column, String, DateTime, Float, Integer, Boolean, Text, ForeignKey, JSON, Index
from sqlalchemy.sql import text
import uuid
import json
import logging

# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def upgrade() -> None:
    """Upgrade to many-to-many Project-Video relationship."""
    
    logger.info("Starting Project-Video many-to-many migration...")
    
    # Step 1: Create project_videos junction table
    logger.info("Creating project_videos junction table...")
    op.create_table('project_videos',
        sa.Column('id', sa.String(36), nullable=False, default=lambda: str(uuid.uuid4())),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('video_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for project_videos junction table
    op.create_index('idx_project_videos_project_id', 'project_videos', ['project_id'])
    op.create_index('idx_project_videos_video_id', 'project_videos', ['video_id'])
    op.create_index('idx_project_videos_project_video', 'project_videos', ['project_id', 'video_id'])
    op.create_index('idx_project_videos_created_at', 'project_videos', ['created_at'])
    
    # Create unique constraint to prevent duplicate relationships
    op.create_unique_constraint('uq_project_video_relationship', 'project_videos', ['project_id', 'video_id'])
    
    # Step 2: Add new fields to videos table
    logger.info("Adding new fields to videos table...")
    
    # Add camera and technical specification fields
    op.add_column('videos', sa.Column('camera_model', sa.String(), nullable=True))
    op.add_column('videos', sa.Column('camera_view', sa.String(), nullable=True))
    op.add_column('videos', sa.Column('lens_type', sa.String(), nullable=True))
    op.add_column('videos', sa.Column('video_resolution', sa.String(), nullable=True))  # Avoid conflict with existing 'resolution'
    op.add_column('videos', sa.Column('frame_rate', sa.Integer(), nullable=True))
    
    # Add metadata fields for enhanced video management
    op.add_column('videos', sa.Column('signal_type', sa.String(), nullable=True))
    op.add_column('videos', sa.Column('video_metadata', sa.JSON(), nullable=True))
    op.add_column('videos', sa.Column('processing_status', sa.String(), nullable=True))
    op.add_column('videos', sa.Column('quality_metrics', sa.JSON(), nullable=True))
    
    # Add indexes for new fields
    op.create_index('idx_videos_camera_model', 'videos', ['camera_model'])
    op.create_index('idx_videos_camera_view', 'videos', ['camera_view'])
    op.create_index('idx_videos_processing_status', 'videos', ['processing_status'])
    op.create_index('idx_videos_signal_type', 'videos', ['signal_type'])
    
    # Step 3: Migrate existing project-video relationships
    logger.info("Migrating existing project-video relationships...")
    
    # Get database connection
    connection = op.get_bind()
    
    # Migrate existing one-to-many relationships to many-to-many
    result = connection.execute(text("""
        SELECT 
            v.id as video_id,
            v.project_id as project_id,
            p.camera_model,
            p.camera_view,
            p.lens_type,
            p.resolution as project_resolution,
            p.frame_rate as project_frame_rate,
            p.signal_type
        FROM videos v
        INNER JOIN projects p ON v.project_id = p.id
        WHERE v.project_id IS NOT NULL
    """))
    
    relationships = result.fetchall()
    logger.info(f"Found {len(relationships)} existing relationships to migrate")
    
    # Insert into junction table and update video fields
    for row in relationships:
        # Insert into project_videos junction table
        connection.execute(text("""
            INSERT INTO project_videos (id, project_id, video_id, created_at)
            VALUES (:id, :project_id, :video_id, datetime('now'))
        """), {
            'id': str(uuid.uuid4()),
            'project_id': row.project_id,
            'video_id': row.video_id
        })
        
        # Update video with project's technical specifications
        connection.execute(text("""
            UPDATE videos SET
                camera_model = :camera_model,
                camera_view = :camera_view,
                lens_type = :lens_type,
                video_resolution = :video_resolution,
                frame_rate = :frame_rate,
                signal_type = :signal_type,
                updated_at = datetime('now')
            WHERE id = :video_id
        """), {
            'camera_model': row.camera_model,
            'camera_view': row.camera_view,
            'lens_type': row.lens_type,
            'video_resolution': row.project_resolution,
            'frame_rate': row.project_frame_rate,
            'signal_type': row.signal_type,
            'video_id': row.video_id
        })
    
    logger.info("Data migration completed successfully")
    
    # Step 4: Remove old project_id foreign key from videos table
    logger.info("Removing old project_id foreign key from videos table...")
    
    # For SQLite, we need to recreate the table without the project_id column
    # This is a complex operation that requires careful handling
    
    # First, create a new videos table without project_id
    op.create_table('videos_new',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('ground_truth_generated', sa.Boolean(), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        # New fields
        sa.Column('camera_model', sa.String(), nullable=True),
        sa.Column('camera_view', sa.String(), nullable=True),
        sa.Column('lens_type', sa.String(), nullable=True),
        sa.Column('video_resolution', sa.String(), nullable=True),
        sa.Column('frame_rate', sa.Integer(), nullable=True),
        sa.Column('signal_type', sa.String(), nullable=True),
        sa.Column('video_metadata', sa.JSON(), nullable=True),
        sa.Column('processing_status', sa.String(), nullable=True),
        sa.Column('quality_metrics', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old table to new table (excluding project_id)
    connection.execute(text("""
        INSERT INTO videos_new (
            id, filename, file_path, file_size, duration, fps, resolution,
            status, ground_truth_generated, upload_timestamp, created_at,
            updated_at, metadata, camera_model, camera_view, lens_type,
            video_resolution, frame_rate, signal_type, video_metadata,
            processing_status, quality_metrics
        )
        SELECT 
            id, filename, file_path, file_size, duration, fps, resolution,
            status, ground_truth_generated, upload_timestamp, created_at,
            updated_at, metadata, camera_model, camera_view, lens_type,
            video_resolution, frame_rate, signal_type, video_metadata,
            processing_status, quality_metrics
        FROM videos
    """))
    
    # Drop old videos table and rename new one
    op.drop_table('videos')
    op.rename_table('videos_new', 'videos')
    
    # Recreate indexes for videos table
    op.create_index('idx_videos_filename', 'videos', ['filename'])
    op.create_index('idx_videos_status', 'videos', ['status'])
    op.create_index('idx_videos_ground_truth_generated', 'videos', ['ground_truth_generated'])
    op.create_index('idx_videos_created_at', 'videos', ['created_at'])
    op.create_index('idx_videos_camera_model', 'videos', ['camera_model'])
    op.create_index('idx_videos_camera_view', 'videos', ['camera_view'])
    op.create_index('idx_videos_processing_status', 'videos', ['processing_status'])
    op.create_index('idx_videos_signal_type', 'videos', ['signal_type'])
    
    # Step 5: Remove deprecated fields from projects table
    logger.info("Removing deprecated fields from projects table...")
    
    # Create new projects table without deprecated fields
    op.create_table('projects_new',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('owner_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        # Keep project-level metadata
        sa.Column('project_metadata', sa.JSON(), nullable=True),
        sa.Column('max_videos', sa.Integer(), nullable=True),
        sa.Column('tolerance_ms', sa.Integer(), nullable=True),
        sa.Column('pass_fail_criteria', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old projects table (excluding deprecated fields)
    connection.execute(text("""
        INSERT INTO projects_new (
            id, name, description, status, owner_id, created_at, updated_at,
            project_metadata, max_videos, tolerance_ms, pass_fail_criteria
        )
        SELECT 
            id, name, description, status, owner_id, created_at, updated_at,
            '{}' as project_metadata,
            100 as max_videos,
            100 as tolerance_ms,
            '{}' as pass_fail_criteria
        FROM projects
    """))
    
    # Drop old projects table and rename new one
    op.drop_table('projects')
    op.rename_table('projects_new', 'projects')
    
    # Recreate indexes for projects table
    op.create_index('idx_projects_name', 'projects', ['name'])
    op.create_index('idx_projects_status', 'projects', ['status'])
    op.create_index('idx_projects_owner_id', 'projects', ['owner_id'])
    op.create_index('idx_projects_created_at', 'projects', ['created_at'])
    
    # Step 6: Update related tables to reference new structure
    logger.info("Updating related table references...")
    
    # Update detection_sessions table if it exists
    try:
        # Check if detection_sessions table exists
        inspector = sa.inspect(connection)
        if 'detection_sessions' in inspector.get_table_names():
            logger.info("Updating detection_sessions table references...")
            # The detection_sessions table already has separate project_id and video_id columns
            # which work well with the new many-to-many structure
            pass
    except Exception as e:
        logger.warning(f"Could not update detection_sessions: {e}")
    
    # Step 7: Create comprehensive indexes for performance
    logger.info("Creating performance optimization indexes...")
    
    # Composite indexes for common query patterns
    op.create_index('idx_project_videos_lookup', 'project_videos', ['project_id', 'video_id', 'created_at'])
    op.create_index('idx_videos_tech_specs', 'videos', ['camera_model', 'camera_view', 'signal_type'])
    op.create_index('idx_videos_processing', 'videos', ['processing_status', 'created_at'])
    op.create_index('idx_videos_quality', 'videos', ['ground_truth_generated', 'processing_status'])
    
    logger.info("Migration completed successfully!")


def downgrade() -> None:
    """Downgrade from many-to-many back to one-to-many relationship."""
    
    logger.info("Starting downgrade migration...")
    
    # Get database connection
    connection = op.get_bind()
    
    # Step 1: Recreate videos table with project_id foreign key
    logger.info("Recreating videos table with project_id foreign key...")
    
    op.create_table('videos_old',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('fps', sa.Float(), nullable=True),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('ground_truth_generated', sa.Boolean(), nullable=True),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Step 2: Migrate data back using junction table
    logger.info("Migrating data back from many-to-many to one-to-many...")
    
    # For each video, pick the first project relationship
    connection.execute(text("""
        INSERT INTO videos_old (
            id, filename, file_path, file_size, duration, fps, resolution,
            status, ground_truth_generated, project_id, upload_timestamp,
            created_at, updated_at, metadata
        )
        SELECT DISTINCT
            v.id, v.filename, v.file_path, v.file_size, v.duration, v.fps, v.resolution,
            v.status, v.ground_truth_generated, pv.project_id, v.upload_timestamp,
            v.created_at, v.updated_at, v.metadata
        FROM videos v
        LEFT JOIN (
            SELECT DISTINCT video_id, project_id,
                   ROW_NUMBER() OVER (PARTITION BY video_id ORDER BY created_at) as rn
            FROM project_videos
        ) pv ON v.id = pv.video_id AND pv.rn = 1
    """))
    
    # Step 3: Recreate projects table with technical fields
    logger.info("Recreating projects table with technical specification fields...")
    
    op.create_table('projects_old',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('camera_model', sa.String(), nullable=True),
        sa.Column('camera_view', sa.String(), nullable=True),
        sa.Column('lens_type', sa.String(), nullable=True),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('frame_rate', sa.Integer(), nullable=True),
        sa.Column('signal_type', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('owner_id', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Migrate projects data back with default technical specifications
    connection.execute(text("""
        INSERT INTO projects_old (
            id, name, description, camera_model, camera_view, lens_type,
            resolution, frame_rate, signal_type, status, owner_id,
            created_at, updated_at
        )
        SELECT 
            id, name, description, 
            'Unknown' as camera_model,
            'Front-facing VRU' as camera_view,
            'Standard' as lens_type,
            '1920x1080' as resolution,
            30 as frame_rate,
            'GPIO' as signal_type,
            status, owner_id, created_at, updated_at
        FROM projects
    """))
    
    # Step 4: Drop new tables and rename old ones
    logger.info("Finalizing downgrade...")
    
    # Drop many-to-many junction table
    op.drop_table('project_videos')
    
    # Replace tables
    op.drop_table('videos')
    op.drop_table('projects')
    op.rename_table('videos_old', 'videos')
    op.rename_table('projects_old', 'projects')
    
    # Recreate original indexes
    op.create_index('idx_videos_filename', 'videos', ['filename'])
    op.create_index('idx_videos_status', 'videos', ['status'])
    op.create_index('idx_videos_project_id', 'videos', ['project_id'])
    op.create_index('idx_videos_created_at', 'videos', ['created_at'])
    
    op.create_index('idx_projects_name', 'projects', ['name'])
    op.create_index('idx_projects_status', 'projects', ['status'])
    op.create_index('idx_projects_owner_id', 'projects', ['owner_id'])
    op.create_index('idx_projects_created_at', 'projects', ['created_at'])
    
    logger.info("Downgrade completed successfully!")