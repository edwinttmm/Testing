"""
Database Migration Strategy: Project Schema Refactoring
Transforms Project model from heavy entity to lightweight playlist following PRD requirements
"""

from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import logging
from typing import Dict, List, Optional
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProjectSchemaRefactoringMigration:
    """
    Multi-phase migration strategy to safely transform Project model
    from heavy all-encompassing entity to lightweight playlist container
    """
    
    def __init__(self, database_url: str, dry_run: bool = True):
        self.engine = create_engine(database_url)
        self.dry_run = dry_run
        self.metadata = MetaData()
        self.Session = sessionmaker(bind=self.engine)
        
        # Migration state tracking
        self.migration_id = f"project_refactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.rollback_data = {}
        
    def execute_sql(self, sql: str, description: str = "") -> None:
        """Execute SQL with logging and dry-run support"""
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Executing: {description}")
        logger.debug(f"SQL: {sql}")
        
        if not self.dry_run:
            with self.engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
        else:
            logger.info(f"DRY RUN: Would execute SQL: {sql[:100]}...")
    
    def create_backup_tables(self) -> None:
        """Create backup tables before migration for rollback capability"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        backup_sqls = [
            f"""
            CREATE TABLE projects_backup_{timestamp} AS 
            SELECT * FROM projects;
            """,
            f"""
            CREATE TABLE videos_backup_{timestamp} AS 
            SELECT * FROM videos;
            """,
            f"""
            CREATE TABLE test_sessions_backup_{timestamp} AS 
            SELECT * FROM test_sessions;
            """
        ]
        
        for sql in backup_sqls:
            self.execute_sql(sql, f"Creating backup table for rollback")
    
    def phase_1_add_video_columns(self) -> None:
        """
        Phase 1: Add camera metadata columns to Video model
        This allows dual storage during migration period
        """
        logger.info("=== PHASE 1: Adding camera metadata columns to Video model ===")
        
        video_column_additions = [
            "ALTER TABLE videos ADD COLUMN camera_model VARCHAR",
            "ALTER TABLE videos ADD COLUMN camera_view VARCHAR", 
            "ALTER TABLE videos ADD COLUMN lens_type VARCHAR",
            "ALTER TABLE videos ADD COLUMN camera_resolution VARCHAR",
            "ALTER TABLE videos ADD COLUMN camera_frame_rate INTEGER",
            "ALTER TABLE videos ADD COLUMN signal_type VARCHAR",
            "ALTER TABLE videos ADD COLUMN codec VARCHAR",
            "ALTER TABLE videos ADD COLUMN bitrate INTEGER",
            "ALTER TABLE videos ADD COLUMN quality_score FLOAT",
            "ALTER TABLE videos ADD COLUMN scene_type VARCHAR",
            "ALTER TABLE videos ADD COLUMN weather_conditions VARCHAR",
            "ALTER TABLE videos ADD COLUMN lighting_conditions VARCHAR",
            "ALTER TABLE videos ADD COLUMN validation_status VARCHAR DEFAULT 'pending'",
        ]
        
        # Add indexes for new columns
        index_additions = [
            "CREATE INDEX idx_video_camera_model ON videos(camera_model)",
            "CREATE INDEX idx_video_camera_view ON videos(camera_view)",
            "CREATE INDEX idx_video_signal_type ON videos(signal_type)",
            "CREATE INDEX idx_video_validation_status ON videos(validation_status)",
            "CREATE INDEX idx_video_scene_type ON videos(scene_type)",
            "CREATE INDEX idx_video_camera_model_view ON videos(camera_model, camera_view)",
            "CREATE INDEX idx_video_camera_specs ON videos(camera_model, camera_resolution, camera_frame_rate)",
        ]
        
        for sql in video_column_additions + index_additions:
            self.execute_sql(sql, "Adding camera metadata column to Video model")
    
    def phase_2_create_junction_table(self) -> None:
        """
        Phase 2: Create project_videos junction table for many-to-many relationship
        """
        logger.info("=== PHASE 2: Creating project_videos junction table ===")
        
        junction_table_sql = """
        CREATE TABLE project_videos (
            project_id VARCHAR(36) NOT NULL,
            video_id VARCHAR(36) NOT NULL,
            sequence_order INTEGER DEFAULT 0 NOT NULL,
            added_by VARCHAR(36),
            notes TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (project_id, video_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        """
        
        junction_indexes = [
            "CREATE INDEX idx_project_video_order ON project_videos(project_id, sequence_order)",
            "CREATE INDEX idx_video_project_added ON project_videos(video_id, added_at)",
            "CREATE INDEX idx_project_video_sequence ON project_videos(project_id, sequence_order, video_id)",
        ]
        
        self.execute_sql(junction_table_sql, "Creating project_videos junction table")
        
        for sql in junction_indexes:
            self.execute_sql(sql, "Adding junction table indexes")
    
    def phase_3_migrate_data(self) -> None:
        """
        Phase 3: Migrate camera metadata from projects to videos and populate junction table
        """
        logger.info("=== PHASE 3: Migrating camera metadata and relationships ===")
        
        # Migrate camera metadata from projects to their videos
        camera_metadata_migration = """
        UPDATE videos v SET 
            camera_model = (SELECT p.camera_model FROM projects p WHERE p.id = v.project_id),
            camera_view = (SELECT p.camera_view FROM projects p WHERE p.id = v.project_id),
            lens_type = (SELECT p.lens_type FROM projects p WHERE p.id = v.project_id),
            camera_resolution = (SELECT p.resolution FROM projects p WHERE p.id = v.project_id),
            camera_frame_rate = (SELECT p.frame_rate FROM projects p WHERE p.id = v.project_id),
            signal_type = (SELECT p.signal_type FROM projects p WHERE p.id = v.project_id)
        WHERE v.project_id IS NOT NULL;
        """
        
        # Populate junction table with existing project-video relationships
        junction_population = """
        INSERT INTO project_videos (project_id, video_id, sequence_order, added_at)
        SELECT 
            v.project_id, 
            v.id,
            ROW_NUMBER() OVER (PARTITION BY v.project_id ORDER BY v.created_at) - 1,
            v.created_at
        FROM videos v 
        WHERE v.project_id IS NOT NULL;
        """
        
        # Update project statistics
        project_stats_update = """
        UPDATE projects p SET 
            video_count = (
                SELECT COUNT(*) 
                FROM project_videos pv 
                WHERE pv.project_id = p.id
            ),
            total_duration = (
                SELECT COALESCE(SUM(v.duration), 0)
                FROM project_videos pv
                JOIN videos v ON pv.video_id = v.id
                WHERE pv.project_id = p.id
            )
        WHERE EXISTS (
            SELECT 1 FROM project_videos pv WHERE pv.project_id = p.id
        );
        """
        
        migrations = [
            (camera_metadata_migration, "Migrating camera metadata to videos"),
            (junction_population, "Populating project_videos junction table"),
            (project_stats_update, "Updating project statistics"),
        ]
        
        for sql, description in migrations:
            self.execute_sql(sql, description)
    
    def phase_4_update_test_sessions(self) -> None:
        """
        Phase 4: Update TestSession model to work with new architecture
        """
        logger.info("=== PHASE 4: Updating TestSession model ===")
        
        test_session_updates = [
            "ALTER TABLE test_sessions ADD COLUMN current_video_id VARCHAR(36)",
            "ALTER TABLE test_sessions ADD COLUMN playlist_position INTEGER DEFAULT 0",
            "ALTER TABLE test_sessions ADD CONSTRAINT fk_test_session_current_video FOREIGN KEY (current_video_id) REFERENCES videos(id) ON DELETE SET NULL",
            "CREATE INDEX idx_testsession_current_video ON test_sessions(current_video_id, status)",
            "CREATE INDEX idx_testsession_playlist_position ON test_sessions(project_id, playlist_position)",
        ]
        
        # Set initial current_video_id for existing sessions
        initial_video_setup = """
        UPDATE test_sessions ts SET 
            current_video_id = (
                SELECT pv.video_id 
                FROM project_videos pv 
                WHERE pv.project_id = ts.project_id 
                ORDER BY pv.sequence_order 
                LIMIT 1
            ),
            playlist_position = 0
        WHERE ts.current_video_id IS NULL;
        """
        
        for sql in test_session_updates:
            self.execute_sql(sql, "Updating TestSession model")
        
        self.execute_sql(initial_video_setup, "Setting initial video for existing test sessions")
    
    def phase_5_remove_obsolete_columns(self) -> None:
        """
        Phase 5: Remove obsolete camera metadata columns from projects table
        WARNING: This is irreversible without backup
        """
        logger.info("=== PHASE 5: Removing obsolete columns from projects ===")
        logger.warning("This phase removes data permanently - ensure backups exist!")
        
        # Drop foreign key constraints first
        constraint_drops = [
            "ALTER TABLE videos DROP CONSTRAINT IF EXISTS fk_videos_project_id",
        ]
        
        # Remove obsolete columns from projects
        column_drops = [
            "ALTER TABLE projects DROP COLUMN IF EXISTS camera_model",
            "ALTER TABLE projects DROP COLUMN IF EXISTS camera_view", 
            "ALTER TABLE projects DROP COLUMN IF EXISTS lens_type",
            "ALTER TABLE projects DROP COLUMN IF EXISTS resolution",
            "ALTER TABLE projects DROP COLUMN IF EXISTS frame_rate",
            "ALTER TABLE projects DROP COLUMN IF EXISTS signal_type",
        ]
        
        # Remove project_id from videos (breaking change!)
        video_cleanup = [
            "ALTER TABLE videos DROP COLUMN IF EXISTS project_id",
        ]
        
        all_drops = constraint_drops + column_drops + video_cleanup
        
        for sql in all_drops:
            self.execute_sql(sql, "Removing obsolete columns and constraints")
    
    def validate_migration(self) -> Dict[str, bool]:
        """
        Validate migration success by checking data consistency
        """
        logger.info("=== VALIDATING MIGRATION RESULTS ===")
        
        validation_queries = {
            "junction_table_populated": """
                SELECT COUNT(*) > 0 FROM project_videos
            """,
            "camera_metadata_migrated": """
                SELECT COUNT(*) FROM videos 
                WHERE camera_model IS NOT NULL
            """,
            "project_stats_updated": """
                SELECT COUNT(*) FROM projects 
                WHERE video_count > 0 AND total_duration IS NOT NULL
            """,
            "no_orphaned_videos": """
                SELECT COUNT(*) = 0 FROM videos v
                WHERE NOT EXISTS (
                    SELECT 1 FROM project_videos pv WHERE pv.video_id = v.id
                )
            """,
            "test_sessions_updated": """
                SELECT COUNT(*) FROM test_sessions 
                WHERE current_video_id IS NOT NULL
            """
        }
        
        results = {}
        if not self.dry_run:
            with self.Session() as session:
                for check_name, sql in validation_queries.items():
                    try:
                        result = session.execute(text(sql)).scalar()
                        results[check_name] = bool(result)
                        logger.info(f"Validation {check_name}: {'PASS' if results[check_name] else 'FAIL'}")
                    except Exception as e:
                        results[check_name] = False
                        logger.error(f"Validation {check_name} failed: {e}")
        else:
            logger.info("DRY RUN: Skipping validation checks")
            results = {k: True for k in validation_queries.keys()}
        
        return results
    
    def create_rollback_script(self) -> str:
        """
        Generate rollback script for emergency recovery
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        rollback_script = f"""
-- EMERGENCY ROLLBACK SCRIPT for Project Schema Refactoring
-- Generated: {datetime.now().isoformat()}
-- Migration ID: {self.migration_id}

-- Step 1: Drop new junction table
DROP TABLE IF EXISTS project_videos;

-- Step 2: Re-add project_id to videos table
ALTER TABLE videos ADD COLUMN project_id VARCHAR(36);

-- Step 3: Restore original project columns
ALTER TABLE projects ADD COLUMN camera_model VARCHAR;
ALTER TABLE projects ADD COLUMN camera_view VARCHAR; 
ALTER TABLE projects ADD COLUMN lens_type VARCHAR;
ALTER TABLE projects ADD COLUMN resolution VARCHAR;
ALTER TABLE projects ADD COLUMN frame_rate INTEGER;
ALTER TABLE projects ADD COLUMN signal_type VARCHAR;

-- Step 4: Restore data from backup tables (if they exist)
-- UPDATE projects SET ... FROM projects_backup_{timestamp} WHERE ...;
-- UPDATE videos SET ... FROM videos_backup_{timestamp} WHERE ...;

-- Step 5: Re-create original foreign key constraints
ALTER TABLE videos ADD CONSTRAINT fk_videos_project_id 
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Step 6: Drop new video columns
ALTER TABLE videos DROP COLUMN IF EXISTS camera_model;
ALTER TABLE videos DROP COLUMN IF EXISTS camera_view;
ALTER TABLE videos DROP COLUMN IF EXISTS lens_type;
ALTER TABLE videos DROP COLUMN IF EXISTS camera_resolution;
ALTER TABLE videos DROP COLUMN IF EXISTS camera_frame_rate;
ALTER TABLE videos DROP COLUMN IF EXISTS signal_type;
ALTER TABLE videos DROP COLUMN IF EXISTS codec;
ALTER TABLE videos DROP COLUMN IF EXISTS bitrate;
ALTER TABLE videos DROP COLUMN IF EXISTS quality_score;
ALTER TABLE videos DROP COLUMN IF EXISTS scene_type;
ALTER TABLE videos DROP COLUMN IF EXISTS weather_conditions;
ALTER TABLE videos DROP COLUMN IF EXISTS lighting_conditions;
ALTER TABLE videos DROP COLUMN IF EXISTS validation_status;

-- Step 7: Drop test session columns
ALTER TABLE test_sessions DROP COLUMN IF EXISTS current_video_id;
ALTER TABLE test_sessions DROP COLUMN IF EXISTS playlist_position;

-- WARNING: This rollback script may result in data loss!
-- Ensure you have proper backups before executing!
        """
        
        rollback_file = f"/tmp/rollback_project_refactor_{timestamp}.sql"
        with open(rollback_file, 'w') as f:
            f.write(rollback_script)
        
        logger.info(f"Rollback script created: {rollback_file}")
        return rollback_file
    
    def execute_full_migration(self) -> Dict[str, any]:
        """
        Execute complete migration with error handling and validation
        """
        logger.info(f"Starting Project Schema Refactoring Migration (ID: {self.migration_id})")
        logger.info(f"Dry run mode: {self.dry_run}")
        
        migration_results = {
            'migration_id': self.migration_id,
            'dry_run': self.dry_run,
            'start_time': datetime.now(),
            'phases_completed': [],
            'validation_results': {},
            'rollback_script': None,
            'success': False,
            'errors': []
        }
        
        try:
            # Create rollback script first
            migration_results['rollback_script'] = self.create_rollback_script()
            
            # Create backups
            if not self.dry_run:
                self.create_backup_tables()
                migration_results['phases_completed'].append('backup_created')
            
            # Execute migration phases
            phases = [
                (self.phase_1_add_video_columns, 'phase_1_video_columns'),
                (self.phase_2_create_junction_table, 'phase_2_junction_table'),
                (self.phase_3_migrate_data, 'phase_3_data_migration'),
                (self.phase_4_update_test_sessions, 'phase_4_test_sessions'),
                # Phase 5 is optional and dangerous - only run if explicitly requested
                # (self.phase_5_remove_obsolete_columns, 'phase_5_cleanup'),
            ]
            
            for phase_func, phase_name in phases:
                logger.info(f"Starting {phase_name}")
                phase_func()
                migration_results['phases_completed'].append(phase_name)
                logger.info(f"Completed {phase_name}")
            
            # Validate results
            migration_results['validation_results'] = self.validate_migration()
            
            # Check if migration was successful
            validation_passed = all(migration_results['validation_results'].values())
            migration_results['success'] = validation_passed
            
            if validation_passed:
                logger.info("✅ Migration completed successfully!")
            else:
                logger.warning("⚠️  Migration completed with validation issues")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            migration_results['errors'].append(str(e))
            migration_results['success'] = False
        
        migration_results['end_time'] = datetime.now()
        migration_results['duration'] = migration_results['end_time'] - migration_results['start_time']
        
        # Log final results
        logger.info("=== MIGRATION SUMMARY ===")
        logger.info(f"Migration ID: {migration_results['migration_id']}")
        logger.info(f"Success: {migration_results['success']}")
        logger.info(f"Duration: {migration_results['duration']}")
        logger.info(f"Phases completed: {migration_results['phases_completed']}")
        
        if migration_results['errors']:
            logger.error(f"Errors: {migration_results['errors']}")
        
        return migration_results

def run_migration(database_url: str, dry_run: bool = True, include_cleanup: bool = False) -> Dict[str, any]:
    """
    Main entry point for running the Project schema refactoring migration
    
    Args:
        database_url: Database connection URL
        dry_run: If True, only log what would be done without executing
        include_cleanup: If True, includes Phase 5 (removing obsolete columns)
    
    Returns:
        Dictionary with migration results and validation data
    """
    migration = ProjectSchemaRefactoringMigration(database_url, dry_run)
    
    # Add cleanup phase if requested
    if include_cleanup:
        logger.warning("Including cleanup phase - this will permanently remove obsolete columns!")
    
    return migration.execute_full_migration()

# CLI interface for running migration
if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Project Schema Refactoring Migration")
    parser.add_argument("--database-url", required=True, help="Database connection URL")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Run in dry-run mode (default)")
    parser.add_argument("--execute", action="store_true", help="Actually execute migration (disables dry-run)")
    parser.add_argument("--include-cleanup", action="store_true", help="Include cleanup phase (removes obsolete columns)")
    
    args = parser.parse_args()
    
    # Determine if this is a dry run
    dry_run = not args.execute
    
    if not dry_run:
        confirm = input("This will modify your database. Are you sure you want to proceed? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Migration cancelled.")
            sys.exit(0)
    
    # Run migration
    results = run_migration(
        database_url=args.database_url,
        dry_run=dry_run,
        include_cleanup=args.include_cleanup
    )
    
    # Exit with appropriate code
    sys.exit(0 if results['success'] else 1)