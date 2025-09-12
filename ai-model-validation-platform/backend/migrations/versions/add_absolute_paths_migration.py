"""Add absolute path storage and migration support

Revision ID: add_absolute_paths_001
Revises: previous_migration
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import logging

# revision identifiers, used by Alembic
revision = 'add_absolute_paths_001'
down_revision = None  # Update with actual previous revision
branch_labels = None
depends_on = None

logger = logging.getLogger(__name__)


def upgrade():
    """Add absolute path columns and migrate existing data"""
    
    # Add new columns for absolute path storage
    logger.info("Adding absolute path columns...")
    
    # Videos table - add absolute_file_path column
    op.add_column('videos', sa.Column('absolute_file_path', sa.String(), nullable=True))
    op.create_index('idx_video_absolute_file_path', 'videos', ['absolute_file_path'])
    
    # Ground Truth Objects table - add screenshot absolute paths
    op.add_column('ground_truth_objects', sa.Column('screenshot_absolute_path', sa.String(), nullable=True))
    op.add_column('ground_truth_objects', sa.Column('screenshot_zoom_absolute_path', sa.String(), nullable=True))
    op.create_index('idx_gt_screenshot_absolute_path', 'ground_truth_objects', ['screenshot_absolute_path'])
    
    # Detection Events table - add screenshot absolute paths
    op.add_column('detection_events', sa.Column('screenshot_absolute_path', sa.String(), nullable=True))
    op.add_column('detection_events', sa.Column('screenshot_zoom_absolute_path', sa.String(), nullable=True))
    
    # Test Reports table - add absolute paths for reports
    op.add_column('test_reports', sa.Column('html_report_absolute_path', sa.String(), nullable=True))
    op.add_column('test_reports', sa.Column('pdf_report_absolute_path', sa.String(), nullable=True))
    op.add_column('test_reports', sa.Column('json_report_absolute_path', sa.String(), nullable=True))
    op.add_column('test_reports', sa.Column('csv_summary_absolute_path', sa.String(), nullable=True))
    op.add_column('test_reports', sa.Column('snapshots_storage_absolute_path', sa.String(), nullable=True))
    
    # Report Snapshots table - add absolute path
    op.add_column('report_snapshots', sa.Column('snapshot_absolute_path', sa.String(), nullable=True))
    
    # Add configuration table for path management
    op.create_table('path_configurations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('deployment_context', sa.String(50), nullable=False, index=True),
        sa.Column('path_type', sa.String(50), nullable=False, index=True),
        sa.Column('base_directory', sa.String(), nullable=False),
        sa.Column('absolute_base_path', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.Column('metadata', sa.JSON()),
    )
    
    # Add indexes for path configurations
    op.create_index('idx_path_config_context_type', 'path_configurations', ['deployment_context', 'path_type'])
    op.create_index('idx_path_config_active', 'path_configurations', ['is_active'])
    
    # Add path migration tracking table
    op.create_table('path_migrations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('table_name', sa.String(100), nullable=False, index=True),
        sa.Column('column_name', sa.String(100), nullable=False),
        sa.Column('old_relative_path', sa.String(), nullable=True),
        sa.Column('new_absolute_path', sa.String(), nullable=True),
        sa.Column('migration_status', sa.String(50), nullable=False, index=True),  # 'pending', 'completed', 'failed'
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('migrated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    
    # Add indexes for migration tracking
    op.create_index('idx_path_migration_table', 'path_migrations', ['table_name'])
    op.create_index('idx_path_migration_status', 'path_migrations', ['migration_status'])
    
    logger.info("Absolute path columns and tables created successfully")


def downgrade():
    """Remove absolute path columns and tables"""
    
    logger.info("Removing absolute path migration...")
    
    # Drop migration tracking table
    op.drop_table('path_migrations')
    op.drop_table('path_configurations')
    
    # Remove columns from existing tables
    op.drop_column('videos', 'absolute_file_path')
    op.drop_column('ground_truth_objects', 'screenshot_absolute_path')
    op.drop_column('ground_truth_objects', 'screenshot_zoom_absolute_path')
    op.drop_column('detection_events', 'screenshot_absolute_path')
    op.drop_column('detection_events', 'screenshot_zoom_absolute_path')
    op.drop_column('test_reports', 'html_report_absolute_path')
    op.drop_column('test_reports', 'pdf_report_absolute_path')
    op.drop_column('test_reports', 'json_report_absolute_path')
    op.drop_column('test_reports', 'csv_summary_absolute_path')
    op.drop_column('test_reports', 'snapshots_storage_absolute_path')
    op.drop_column('report_snapshots', 'snapshot_absolute_path')
    
    logger.info("Absolute path migration rolled back successfully")


def migrate_existing_paths():
    """Data migration function to convert relative paths to absolute paths"""
    from src.utils.path_manager import PathManager, PathType
    import uuid
    
    logger.info("Starting data migration for existing paths...")
    
    # Get database connection
    connection = op.get_bind()
    path_manager = PathManager()
    
    try:
        # Migrate video file paths
        logger.info("Migrating video file paths...")
        videos = connection.execute(text("SELECT id, file_path FROM videos WHERE file_path IS NOT NULL")).fetchall()
        
        for video in videos:
            try:
                result = path_manager.resolve_path(video.file_path, PathType.VIDEO)
                connection.execute(
                    text("UPDATE videos SET absolute_file_path = :abs_path WHERE id = :video_id"),
                    {'abs_path': result.absolute_path, 'video_id': video.id}
                )
                
                # Record migration
                connection.execute(
                    text("""
                        INSERT INTO path_migrations (id, table_name, column_name, old_relative_path, 
                                                   new_absolute_path, migration_status, migrated_at)
                        VALUES (:id, 'videos', 'file_path', :old_path, :new_path, 'completed', NOW())
                    """),
                    {
                        'id': str(uuid.uuid4()),
                        'old_path': video.file_path,
                        'new_path': result.absolute_path
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to migrate video path {video.file_path}: {str(e)}")
                connection.execute(
                    text("""
                        INSERT INTO path_migrations (id, table_name, column_name, old_relative_path,
                                                   migration_status, error_message, created_at)
                        VALUES (:id, 'videos', 'file_path', :old_path, 'failed', :error, NOW())
                    """),
                    {
                        'id': str(uuid.uuid4()),
                        'old_path': video.file_path,
                        'error': str(e)
                    }
                )
        
        # Migrate ground truth screenshot paths
        logger.info("Migrating ground truth screenshot paths...")
        gt_objects = connection.execute(text("""
            SELECT id, screenshot_path, screenshot_zoom_path 
            FROM ground_truth_objects 
            WHERE screenshot_path IS NOT NULL OR screenshot_zoom_path IS NOT NULL
        """)).fetchall()
        
        for gt_obj in gt_objects:
            try:
                if gt_obj.screenshot_path:
                    result = path_manager.resolve_path(gt_obj.screenshot_path, PathType.SCREENSHOT)
                    connection.execute(
                        text("UPDATE ground_truth_objects SET screenshot_absolute_path = :abs_path WHERE id = :obj_id"),
                        {'abs_path': result.absolute_path, 'obj_id': gt_obj.id}
                    )
                
                if gt_obj.screenshot_zoom_path:
                    result = path_manager.resolve_path(gt_obj.screenshot_zoom_path, PathType.SCREENSHOT)
                    connection.execute(
                        text("UPDATE ground_truth_objects SET screenshot_zoom_absolute_path = :abs_path WHERE id = :obj_id"),
                        {'abs_path': result.absolute_path, 'obj_id': gt_obj.id}
                    )
                
            except Exception as e:
                logger.error(f"Failed to migrate ground truth paths for object {gt_obj.id}: {str(e)}")
        
        # Migrate detection event screenshot paths
        logger.info("Migrating detection event screenshot paths...")
        detection_events = connection.execute(text("""
            SELECT id, screenshot_path, screenshot_zoom_path
            FROM detection_events
            WHERE screenshot_path IS NOT NULL OR screenshot_zoom_path IS NOT NULL
        """)).fetchall()
        
        for event in detection_events:
            try:
                if event.screenshot_path:
                    result = path_manager.resolve_path(event.screenshot_path, PathType.SCREENSHOT)
                    connection.execute(
                        text("UPDATE detection_events SET screenshot_absolute_path = :abs_path WHERE id = :event_id"),
                        {'abs_path': result.absolute_path, 'event_id': event.id}
                    )
                
                if event.screenshot_zoom_path:
                    result = path_manager.resolve_path(event.screenshot_zoom_path, PathType.SCREENSHOT)
                    connection.execute(
                        text("UPDATE detection_events SET screenshot_zoom_absolute_path = :abs_path WHERE id = :event_id"),
                        {'abs_path': result.absolute_path, 'event_id': event.id}
                    )
                    
            except Exception as e:
                logger.error(f"Failed to migrate detection event paths for event {event.id}: {str(e)}")
        
        # Migrate report paths
        logger.info("Migrating report file paths...")
        reports = connection.execute(text("""
            SELECT id, html_report_path, pdf_report_path, json_report_path, 
                   csv_summary_path, snapshots_storage_path
            FROM test_reports
            WHERE html_report_path IS NOT NULL OR pdf_report_path IS NOT NULL OR
                  json_report_path IS NOT NULL OR csv_summary_path IS NOT NULL OR
                  snapshots_storage_path IS NOT NULL
        """)).fetchall()
        
        for report in reports:
            try:
                if report.html_report_path:
                    result = path_manager.resolve_path(report.html_report_path, PathType.REPORT)
                    connection.execute(
                        text("UPDATE test_reports SET html_report_absolute_path = :abs_path WHERE id = :report_id"),
                        {'abs_path': result.absolute_path, 'report_id': report.id}
                    )
                
                if report.pdf_report_path:
                    result = path_manager.resolve_path(report.pdf_report_path, PathType.REPORT)
                    connection.execute(
                        text("UPDATE test_reports SET pdf_report_absolute_path = :abs_path WHERE id = :report_id"),
                        {'abs_path': result.absolute_path, 'report_id': report.id}
                    )
                
                if report.json_report_path:
                    result = path_manager.resolve_path(report.json_report_path, PathType.REPORT)
                    connection.execute(
                        text("UPDATE test_reports SET json_report_absolute_path = :abs_path WHERE id = :report_id"),
                        {'abs_path': result.absolute_path, 'report_id': report.id}
                    )
                
                if report.csv_summary_path:
                    result = path_manager.resolve_path(report.csv_summary_path, PathType.REPORT)
                    connection.execute(
                        text("UPDATE test_reports SET csv_summary_absolute_path = :abs_path WHERE id = :report_id"),
                        {'abs_path': result.absolute_path, 'report_id': report.id}
                    )
                
                if report.snapshots_storage_path:
                    result = path_manager.resolve_path(report.snapshots_storage_path, PathType.REPORT)
                    connection.execute(
                        text("UPDATE test_reports SET snapshots_storage_absolute_path = :abs_path WHERE id = :report_id"),
                        {'abs_path': result.absolute_path, 'report_id': report.id}
                    )
                    
            except Exception as e:
                logger.error(f"Failed to migrate report paths for report {report.id}: {str(e)}")
        
        # Commit the migration
        connection.commit()
        logger.info("Data migration completed successfully")
        
    except Exception as e:
        logger.error(f"Data migration failed: {str(e)}")
        connection.rollback()
        raise


# Additional utility functions for migration
def validate_migration():
    """Validate that migration was successful"""
    connection = op.get_bind()
    
    # Check migration status
    migration_stats = connection.execute(text("""
        SELECT migration_status, COUNT(*) as count
        FROM path_migrations
        GROUP BY migration_status
    """)).fetchall()
    
    logger.info("Migration statistics:")
    for stat in migration_stats:
        logger.info(f"  {stat.migration_status}: {stat.count}")
    
    # Check for failed migrations
    failed_migrations = connection.execute(text("""
        SELECT table_name, column_name, old_relative_path, error_message
        FROM path_migrations
        WHERE migration_status = 'failed'
        LIMIT 10
    """)).fetchall()
    
    if failed_migrations:
        logger.warning("Failed migrations found:")
        for failure in failed_migrations:
            logger.warning(f"  {failure.table_name}.{failure.column_name}: {failure.old_relative_path} - {failure.error_message}")
    
    return len(failed_migrations) == 0


def cleanup_migration():
    """Clean up temporary migration data"""
    connection = op.get_bind()
    
    # Archive completed migrations older than 30 days
    connection.execute(text("""
        DELETE FROM path_migrations
        WHERE migration_status = 'completed'
        AND migrated_at < NOW() - INTERVAL '30 days'
    """))
    
    logger.info("Migration cleanup completed")