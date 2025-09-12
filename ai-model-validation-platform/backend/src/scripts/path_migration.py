"""
Path Migration Script
Comprehensive script to migrate existing relative paths to absolute paths in the database.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import time
from datetime import datetime

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.path_manager import PathManager, PathType
from src.config.path_config import get_path_config_manager
from config import get_settings

logger = logging.getLogger(__name__)


class PathMigrationManager:
    """Manages migration of relative paths to absolute paths in the database"""
    
    def __init__(self, database_url: Optional[str] = None, dry_run: bool = False):
        self.dry_run = dry_run
        self.path_manager = PathManager()
        self.config_manager = get_path_config_manager()
        
        # Setup database connection
        if database_url:
            self.database_url = database_url
        else:
            settings = get_settings()
            self.database_url = settings.database_url
        
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Migration tracking
        self.migration_stats = {
            "total_records": 0,
            "successful_migrations": 0,
            "failed_migrations": 0,
            "skipped_records": 0,
            "tables_processed": 0
        }
        self.failed_migrations = []
        
        logger.info(f"PathMigrationManager initialized {'(DRY RUN)' if dry_run else ''}")
    
    def run_full_migration(self) -> Dict[str, Any]:
        """Run complete path migration for all tables"""
        logger.info("🚀 Starting full path migration...")
        
        start_time = time.time()
        
        try:
            # Check if migration tables exist, create if not
            self._ensure_migration_tables()
            
            # Migrate each table
            migration_functions = [
                ("videos", self._migrate_video_paths),
                ("ground_truth_objects", self._migrate_ground_truth_paths),
                ("detection_events", self._migrate_detection_event_paths),
                ("test_reports", self._migrate_test_report_paths),
                ("report_snapshots", self._migrate_report_snapshot_paths)
            ]
            
            for table_name, migration_func in migration_functions:
                try:
                    logger.info(f"📊 Migrating {table_name}...")
                    table_stats = migration_func()
                    self._update_stats(table_stats)
                    logger.info(f"✅ Completed {table_name}: {table_stats['successful']} successful, {table_stats['failed']} failed")
                except Exception as e:
                    logger.error(f"❌ Failed to migrate {table_name}: {str(e)}")
                    self.migration_stats["failed_migrations"] += 1
            
            # Generate migration report
            end_time = time.time()
            duration = end_time - start_time
            
            migration_report = {
                "status": "completed" if self.migration_stats["failed_migrations"] == 0 else "completed_with_errors",
                "duration_seconds": duration,
                "dry_run": self.dry_run,
                "statistics": self.migration_stats,
                "failed_migrations": self.failed_migrations[:10],  # First 10 failures
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"🎉 Migration completed in {duration:.2f} seconds")
            logger.info(f"📊 Statistics: {self.migration_stats}")
            
            return migration_report
            
        except Exception as e:
            logger.error(f"💥 Migration failed: {str(e)}")
            raise
    
    def _ensure_migration_tables(self):
        """Ensure migration tracking tables exist"""
        with self.engine.connect() as conn:
            # Check if path_migrations table exists
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='path_migrations'
            """)).fetchone()
            
            if not result:
                logger.info("Creating path_migrations table...")
                conn.execute(text("""
                    CREATE TABLE path_migrations (
                        id TEXT PRIMARY KEY,
                        table_name TEXT NOT NULL,
                        column_name TEXT NOT NULL,
                        old_relative_path TEXT,
                        new_absolute_path TEXT,
                        migration_status TEXT NOT NULL,
                        error_message TEXT,
                        migrated_at TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
    
    def _migrate_video_paths(self) -> Dict[str, int]:
        """Migrate video file paths"""
        stats = {"successful": 0, "failed": 0, "skipped": 0}
        
        with self.SessionLocal() as db:
            try:
                # Get videos with file_path but no absolute_file_path
                videos = db.execute(text("""
                    SELECT id, file_path, absolute_file_path 
                    FROM videos 
                    WHERE file_path IS NOT NULL 
                    AND (absolute_file_path IS NULL OR absolute_file_path = '')
                """)).fetchall()
                
                logger.info(f"Found {len(videos)} videos to migrate")
                
                for video in videos:
                    try:
                        # Resolve path using path manager
                        result = self.path_manager.resolve_path(video.file_path, PathType.VIDEO)
                        
                        if not self.dry_run:
                            # Update video record
                            db.execute(text("""
                                UPDATE videos 
                                SET absolute_file_path = :abs_path 
                                WHERE id = :video_id
                            """), {
                                'abs_path': result.absolute_path,
                                'video_id': video.id
                            })
                            
                            # Record migration
                            self._record_migration(
                                db, "videos", "file_path", 
                                video.file_path, result.absolute_path, "completed"
                            )
                        
                        stats["successful"] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate video {video.id}: {str(e)}")
                        stats["failed"] += 1
                        self.failed_migrations.append({
                            "table": "videos",
                            "record_id": video.id,
                            "path": video.file_path,
                            "error": str(e)
                        })
                        
                        if not self.dry_run:
                            self._record_migration(
                                db, "videos", "file_path", 
                                video.file_path, None, "failed", str(e)
                            )
                
                if not self.dry_run:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Video path migration failed: {str(e)}")
                db.rollback()
                raise
        
        return stats
    
    def _migrate_ground_truth_paths(self) -> Dict[str, int]:
        """Migrate ground truth screenshot paths"""
        stats = {"successful": 0, "failed": 0, "skipped": 0}
        
        with self.SessionLocal() as db:
            try:
                # Get ground truth objects with screenshot paths
                gt_objects = db.execute(text("""
                    SELECT id, screenshot_path, screenshot_zoom_path,
                           screenshot_absolute_path, screenshot_zoom_absolute_path
                    FROM ground_truth_objects 
                    WHERE (screenshot_path IS NOT NULL OR screenshot_zoom_path IS NOT NULL)
                    AND (screenshot_absolute_path IS NULL OR screenshot_zoom_absolute_path IS NULL)
                """)).fetchall()
                
                logger.info(f"Found {len(gt_objects)} ground truth objects to migrate")
                
                for gt_obj in gt_objects:
                    try:
                        updates = {}
                        
                        # Migrate main screenshot path
                        if gt_obj.screenshot_path and not gt_obj.screenshot_absolute_path:
                            result = self.path_manager.resolve_path(gt_obj.screenshot_path, PathType.SCREENSHOT)
                            updates['screenshot_absolute_path'] = result.absolute_path
                        
                        # Migrate zoom screenshot path
                        if gt_obj.screenshot_zoom_path and not gt_obj.screenshot_zoom_absolute_path:
                            result = self.path_manager.resolve_path(gt_obj.screenshot_zoom_path, PathType.SCREENSHOT)
                            updates['screenshot_zoom_absolute_path'] = result.absolute_path
                        
                        if updates and not self.dry_run:
                            # Build dynamic update query
                            set_clauses = [f"{key} = :{key}" for key in updates.keys()]
                            query = f"UPDATE ground_truth_objects SET {', '.join(set_clauses)} WHERE id = :obj_id"
                            
                            updates['obj_id'] = gt_obj.id
                            db.execute(text(query), updates)
                        
                        stats["successful"] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate ground truth object {gt_obj.id}: {str(e)}")
                        stats["failed"] += 1
                        self.failed_migrations.append({
                            "table": "ground_truth_objects",
                            "record_id": gt_obj.id,
                            "error": str(e)
                        })
                
                if not self.dry_run:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Ground truth path migration failed: {str(e)}")
                db.rollback()
                raise
        
        return stats
    
    def _migrate_detection_event_paths(self) -> Dict[str, int]:
        """Migrate detection event screenshot paths"""
        stats = {"successful": 0, "failed": 0, "skipped": 0}
        
        with self.SessionLocal() as db:
            try:
                # Get detection events with screenshot paths
                events = db.execute(text("""
                    SELECT id, screenshot_path, screenshot_zoom_path,
                           screenshot_absolute_path, screenshot_zoom_absolute_path
                    FROM detection_events 
                    WHERE (screenshot_path IS NOT NULL OR screenshot_zoom_path IS NOT NULL)
                    AND (screenshot_absolute_path IS NULL OR screenshot_zoom_absolute_path IS NULL)
                """)).fetchall()
                
                logger.info(f"Found {len(events)} detection events to migrate")
                
                for event in events:
                    try:
                        updates = {}
                        
                        # Migrate screenshot paths similar to ground truth
                        if event.screenshot_path and not event.screenshot_absolute_path:
                            result = self.path_manager.resolve_path(event.screenshot_path, PathType.SCREENSHOT)
                            updates['screenshot_absolute_path'] = result.absolute_path
                        
                        if event.screenshot_zoom_path and not event.screenshot_zoom_absolute_path:
                            result = self.path_manager.resolve_path(event.screenshot_zoom_path, PathType.SCREENSHOT)
                            updates['screenshot_zoom_absolute_path'] = result.absolute_path
                        
                        if updates and not self.dry_run:
                            set_clauses = [f"{key} = :{key}" for key in updates.keys()]
                            query = f"UPDATE detection_events SET {', '.join(set_clauses)} WHERE id = :event_id"
                            
                            updates['event_id'] = event.id
                            db.execute(text(query), updates)
                        
                        stats["successful"] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate detection event {event.id}: {str(e)}")
                        stats["failed"] += 1
                
                if not self.dry_run:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Detection event path migration failed: {str(e)}")
                db.rollback()
                raise
        
        return stats
    
    def _migrate_test_report_paths(self) -> Dict[str, int]:
        """Migrate test report file paths"""
        stats = {"successful": 0, "failed": 0, "skipped": 0}
        
        with self.SessionLocal() as db:
            try:
                # Get test reports with file paths but missing absolute paths
                reports = db.execute(text("""
                    SELECT id, html_report_path, pdf_report_path, json_report_path, 
                           csv_summary_path, snapshots_storage_path,
                           html_report_absolute_path, pdf_report_absolute_path,
                           json_report_absolute_path, csv_summary_absolute_path,
                           snapshots_storage_absolute_path
                    FROM test_reports 
                    WHERE (html_report_path IS NOT NULL OR pdf_report_path IS NOT NULL OR
                           json_report_path IS NOT NULL OR csv_summary_path IS NOT NULL OR
                           snapshots_storage_path IS NOT NULL)
                """)).fetchall()
                
                logger.info(f"Found {len(reports)} test reports to migrate")
                
                for report in reports:
                    try:
                        updates = {}
                        
                        # Migrate each report path type
                        path_mappings = [
                            ('html_report_path', 'html_report_absolute_path'),
                            ('pdf_report_path', 'pdf_report_absolute_path'),
                            ('json_report_path', 'json_report_absolute_path'),
                            ('csv_summary_path', 'csv_summary_absolute_path'),
                            ('snapshots_storage_path', 'snapshots_storage_absolute_path')
                        ]
                        
                        for rel_field, abs_field in path_mappings:
                            rel_path = getattr(report, rel_field)
                            abs_path = getattr(report, abs_field)
                            
                            if rel_path and not abs_path:
                                result = self.path_manager.resolve_path(rel_path, PathType.REPORT)
                                updates[abs_field] = result.absolute_path
                        
                        if updates and not self.dry_run:
                            set_clauses = [f"{key} = :{key}" for key in updates.keys()]
                            query = f"UPDATE test_reports SET {', '.join(set_clauses)} WHERE id = :report_id"
                            
                            updates['report_id'] = report.id
                            db.execute(text(query), updates)
                        
                        stats["successful"] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate test report {report.id}: {str(e)}")
                        stats["failed"] += 1
                
                if not self.dry_run:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Test report path migration failed: {str(e)}")
                db.rollback()
                raise
        
        return stats
    
    def _migrate_report_snapshot_paths(self) -> Dict[str, int]:
        """Migrate report snapshot file paths"""
        stats = {"successful": 0, "failed": 0, "skipped": 0}
        
        with self.SessionLocal() as db:
            try:
                # Get report snapshots with paths but missing absolute paths
                snapshots = db.execute(text("""
                    SELECT id, snapshot_path, snapshot_absolute_path
                    FROM report_snapshots 
                    WHERE snapshot_path IS NOT NULL 
                    AND (snapshot_absolute_path IS NULL OR snapshot_absolute_path = '')
                """)).fetchall()
                
                logger.info(f"Found {len(snapshots)} report snapshots to migrate")
                
                for snapshot in snapshots:
                    try:
                        result = self.path_manager.resolve_path(snapshot.snapshot_path, PathType.SCREENSHOT)
                        
                        if not self.dry_run:
                            db.execute(text("""
                                UPDATE report_snapshots 
                                SET snapshot_absolute_path = :abs_path 
                                WHERE id = :snapshot_id
                            """), {
                                'abs_path': result.absolute_path,
                                'snapshot_id': snapshot.id
                            })
                        
                        stats["successful"] += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate report snapshot {snapshot.id}: {str(e)}")
                        stats["failed"] += 1
                
                if not self.dry_run:
                    db.commit()
                
            except Exception as e:
                logger.error(f"Report snapshot path migration failed: {str(e)}")
                db.rollback()
                raise
        
        return stats
    
    def _record_migration(self, db, table_name: str, column_name: str, 
                         old_path: str, new_path: Optional[str], 
                         status: str, error_msg: Optional[str] = None):
        """Record migration in tracking table"""
        try:
            migration_id = str(uuid.uuid4())
            migrated_at = datetime.now().isoformat() if status == "completed" else None
            
            db.execute(text("""
                INSERT INTO path_migrations 
                (id, table_name, column_name, old_relative_path, new_absolute_path, 
                 migration_status, error_message, migrated_at)
                VALUES (:id, :table, :column, :old_path, :new_path, :status, :error, :migrated)
            """), {
                'id': migration_id,
                'table': table_name,
                'column': column_name,
                'old_path': old_path,
                'new_path': new_path,
                'status': status,
                'error': error_msg,
                'migrated': migrated_at
            })
            
        except Exception as e:
            logger.warning(f"Failed to record migration: {str(e)}")
    
    def _update_stats(self, table_stats: Dict[str, int]):
        """Update overall migration statistics"""
        self.migration_stats["successful_migrations"] += table_stats["successful"]
        self.migration_stats["failed_migrations"] += table_stats["failed"]
        self.migration_stats["skipped_records"] += table_stats["skipped"]
        self.migration_stats["total_records"] += sum(table_stats.values())
        self.migration_stats["tables_processed"] += 1
    
    def validate_migration(self) -> Dict[str, Any]:
        """Validate migration results"""
        validation_results = {"status": "valid", "issues": []}
        
        with self.SessionLocal() as db:
            try:
                # Check for remaining unmigrated records
                tables_to_check = [
                    ("videos", "file_path", "absolute_file_path"),
                    ("ground_truth_objects", "screenshot_path", "screenshot_absolute_path"),
                    ("detection_events", "screenshot_path", "screenshot_absolute_path"),
                    ("test_reports", "html_report_path", "html_report_absolute_path"),
                    ("report_snapshots", "snapshot_path", "snapshot_absolute_path")
                ]
                
                for table_name, rel_col, abs_col in tables_to_check:
                    unmigrated = db.execute(text(f"""
                        SELECT COUNT(*) as count FROM {table_name}
                        WHERE {rel_col} IS NOT NULL 
                        AND ({abs_col} IS NULL OR {abs_col} = '')
                    """)).fetchone()
                    
                    if unmigrated and unmigrated.count > 0:
                        validation_results["issues"].append(
                            f"{table_name}: {unmigrated.count} unmigrated records"
                        )
                
                # Check migration statistics
                migration_stats = db.execute(text("""
                    SELECT migration_status, COUNT(*) as count
                    FROM path_migrations
                    GROUP BY migration_status
                """)).fetchall()
                
                stats_dict = {stat.migration_status: stat.count for stat in migration_stats}
                validation_results["migration_stats"] = stats_dict
                
                # Overall validation status
                if validation_results["issues"]:
                    validation_results["status"] = "issues_found"
                
            except Exception as e:
                validation_results["status"] = "validation_failed"
                validation_results["error"] = str(e)
        
        return validation_results
    
    def rollback_migration(self) -> Dict[str, Any]:
        """Rollback migration by clearing absolute path fields"""
        if self.dry_run:
            return {"error": "Cannot rollback in dry-run mode"}
        
        rollback_stats = {"cleared_records": 0, "errors": 0}
        
        with self.SessionLocal() as db:
            try:
                # Clear absolute path fields
                rollback_queries = [
                    "UPDATE videos SET absolute_file_path = NULL",
                    "UPDATE ground_truth_objects SET screenshot_absolute_path = NULL, screenshot_zoom_absolute_path = NULL",
                    "UPDATE detection_events SET screenshot_absolute_path = NULL, screenshot_zoom_absolute_path = NULL",
                    "UPDATE test_reports SET html_report_absolute_path = NULL, pdf_report_absolute_path = NULL, json_report_absolute_path = NULL, csv_summary_absolute_path = NULL, snapshots_storage_absolute_path = NULL",
                    "UPDATE report_snapshots SET snapshot_absolute_path = NULL"
                ]
                
                for query in rollback_queries:
                    result = db.execute(text(query))
                    rollback_stats["cleared_records"] += result.rowcount
                
                # Clear migration tracking
                db.execute(text("DELETE FROM path_migrations"))
                
                db.commit()
                logger.info(f"Rollback completed: {rollback_stats['cleared_records']} records cleared")
                
            except Exception as e:
                logger.error(f"Rollback failed: {str(e)}")
                db.rollback()
                rollback_stats["errors"] = 1
                rollback_stats["error_message"] = str(e)
        
        return rollback_stats


def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate relative paths to absolute paths in database")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode without making changes")
    parser.add_argument("--database-url", help="Database URL to use")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing migration")
    parser.add_argument("--rollback", action="store_true", help="Rollback previous migration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Create migration manager
        migration_manager = PathMigrationManager(
            database_url=args.database_url,
            dry_run=args.dry_run
        )
        
        if args.validate_only:
            # Validate existing migration
            logger.info("🔍 Validating migration...")
            validation_results = migration_manager.validate_migration()
            
            print("\n📊 Validation Results:")
            print(f"Status: {validation_results['status']}")
            
            if validation_results.get('issues'):
                print("Issues found:")
                for issue in validation_results['issues']:
                    print(f"  - {issue}")
            
            if validation_results.get('migration_stats'):
                print("Migration Statistics:")
                for status, count in validation_results['migration_stats'].items():
                    print(f"  {status}: {count}")
        
        elif args.rollback:
            # Rollback migration
            logger.info("🔄 Rolling back migration...")
            rollback_results = migration_manager.rollback_migration()
            
            print("\n📊 Rollback Results:")
            print(f"Cleared records: {rollback_results.get('cleared_records', 0)}")
            if rollback_results.get('errors', 0) > 0:
                print(f"Errors: {rollback_results['errors']}")
                if rollback_results.get('error_message'):
                    print(f"Error message: {rollback_results['error_message']}")
        
        else:
            # Run migration
            migration_results = migration_manager.run_full_migration()
            
            print("\n📊 Migration Results:")
            print(f"Status: {migration_results['status']}")
            print(f"Duration: {migration_results['duration_seconds']:.2f} seconds")
            print(f"Dry Run: {migration_results['dry_run']}")
            
            stats = migration_results['statistics']
            print(f"\nStatistics:")
            print(f"  Total records: {stats['total_records']}")
            print(f"  Successful migrations: {stats['successful_migrations']}")
            print(f"  Failed migrations: {stats['failed_migrations']}")
            print(f"  Skipped records: {stats['skipped_records']}")
            print(f"  Tables processed: {stats['tables_processed']}")
            
            if migration_results['failed_migrations']:
                print(f"\nFirst 10 failed migrations:")
                for failure in migration_results['failed_migrations'][:10]:
                    print(f"  - {failure['table']}/{failure['record_id']}: {failure['error']}")
        
    except Exception as e:
        logger.error(f"💥 Migration script failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()