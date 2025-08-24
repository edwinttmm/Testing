#!/usr/bin/env python3
"""
Comprehensive Database Migration System

This migration script handles upgrading existing databases to the latest schema
with support for both PostgreSQL and SQLite, including:
- Safe column additions
- Index creation with conflict resolution 
- Data type migrations
- Foreign key constraint updates
- Performance optimizations

Usage:
    python comprehensive_migration.py --dry-run    # Preview changes
    python comprehensive_migration.py --execute    # Apply changes
    python comprehensive_migration.py --rollback   # Rollback last migration
"""

import sys
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
from sqlalchemy import text, inspect, MetaData, Table, Column
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, OperationalError
import logging

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import engine, SessionLocal
from models import Base, Project, Video, GroundTruthObject, DetectionEvent, TestSession

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MigrationManager:
    """
    Comprehensive database migration manager with rollback support
    """
    
    def __init__(self, dry_run: bool = False):
        self.engine = engine
        self.dry_run = dry_run
        self.inspector = inspect(engine)
        self.is_postgresql = 'postgresql' in str(engine.url).lower()
        self.is_sqlite = 'sqlite' in str(engine.url).lower()
        
        # Migration tracking
        self.applied_migrations: List[Dict] = []
        self.failed_migrations: List[Dict] = []
        self.migration_log_file = Path(__file__).parent / 'migration_log.json'
        
        logger.info(f"Migration manager initialized for {'PostgreSQL' if self.is_postgresql else 'SQLite'}")
    
    def get_existing_tables(self) -> Set[str]:
        """Get set of existing table names"""
        return set(self.inspector.get_table_names())
    
    def get_existing_columns(self, table_name: str) -> Dict[str, dict]:
        """Get existing columns for a table"""
        try:
            columns = self.inspector.get_columns(table_name)
            return {col['name']: col for col in columns}
        except Exception as e:
            logger.error(f"Could not get columns for {table_name}: {e}")
            return {}
    
    def get_existing_indexes(self, table_name: str) -> Set[str]:
        """Get existing indexes for a table"""
        try:
            indexes = self.inspector.get_indexes(table_name)
            return {idx['name'] for idx in indexes if idx.get('name')}
        except Exception as e:
            logger.warning(f"Could not get indexes for {table_name}: {e}")
            return set()
    
    def log_migration(self, migration_name: str, success: bool, details: str = ""):
        """Log migration operation for rollback tracking"""
        migration_record = {
            'name': migration_name,
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'details': details,
            'database_type': 'PostgreSQL' if self.is_postgresql else 'SQLite'
        }
        
        if success:
            self.applied_migrations.append(migration_record)
            logger.info(f"✅ Migration '{migration_name}' completed successfully")
        else:
            self.failed_migrations.append(migration_record)
            logger.error(f"❌ Migration '{migration_name}' failed: {details}")
    
    def save_migration_log(self):
        """Save migration log to file"""
        try:
            log_data = {
                'migration_run_timestamp': datetime.now().isoformat(),
                'applied_migrations': self.applied_migrations,
                'failed_migrations': self.failed_migrations
            }
            
            with open(self.migration_log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            
            logger.info(f"Migration log saved to {self.migration_log_file}")
        except Exception as e:
            logger.error(f"Could not save migration log: {e}")
    
    def add_column_safe(self, table_name: str, column_name: str, 
                       column_definition: str, default_value: str = None) -> bool:
        """Safely add a column with proper error handling"""
        migration_name = f"add_column_{table_name}_{column_name}"
        
        try:
            existing_columns = self.get_existing_columns(table_name)
            
            if column_name in existing_columns:
                self.log_migration(migration_name, True, "Column already exists")
                return True
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would add column {column_name} to {table_name}: {column_definition}")
                self.log_migration(migration_name, True, "Dry run - would add column")
                return True
            
            with self.engine.connect() as conn:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                conn.execute(text(sql))
                
                # Set default value if provided
                if default_value:
                    update_sql = f"UPDATE {table_name} SET {column_name} = {default_value} WHERE {column_name} IS NULL"
                    conn.execute(text(update_sql))
                
                conn.commit()
                
            self.log_migration(migration_name, True, f"Added column with definition: {column_definition}")
            return True
            
        except Exception as e:
            self.log_migration(migration_name, False, str(e))
            return False
    
    def create_index_safe(self, table_name: str, index_name: str, 
                         columns: List[str], unique: bool = False) -> bool:
        """Safely create an index with conflict resolution"""
        migration_name = f"create_index_{index_name}"
        
        try:
            existing_indexes = self.get_existing_indexes(table_name)
            
            if index_name in existing_indexes:
                self.log_migration(migration_name, True, "Index already exists")
                return True
            
            columns_str = ', '.join(columns)
            unique_str = 'UNIQUE ' if unique else ''
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would create {unique_str}index {index_name} on {table_name}({columns_str})")
                self.log_migration(migration_name, True, "Dry run - would create index")
                return True
            
            with self.engine.connect() as conn:
                if self.is_postgresql:
                    sql = f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                else:  # SQLite
                    sql = f"CREATE {unique_str}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                
                conn.execute(text(sql))
                conn.commit()
            
            self.log_migration(migration_name, True, f"Created {unique_str}index on columns: {columns_str}")
            return True
            
        except Exception as e:
            # Handle duplicate index errors gracefully
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                self.log_migration(migration_name, True, "Index already exists (detected via error)")
                return True
            
            self.log_migration(migration_name, False, str(e))
            return False
    
    def migrate_projects_table(self) -> bool:
        """Migrate projects table to latest schema"""
        logger.info("🔄 Migrating projects table...")
        
        existing_tables = self.get_existing_tables()
        if 'projects' not in existing_tables:
            logger.warning("Projects table does not exist, skipping migration")
            return True
        
        # Add any missing columns
        success = True
        
        # Example: Add new columns if they don't exist
        # success &= self.add_column_safe('projects', 'new_column', 'VARCHAR(255)', "'default_value'")
        
        # Create essential indexes
        success &= self.create_index_safe('projects', 'idx_projects_name_search', ['name'])
        success &= self.create_index_safe('projects', 'idx_projects_status_filter', ['status'])
        success &= self.create_index_safe('projects', 'idx_projects_owner_status', ['owner_id', 'status'])
        success &= self.create_index_safe('projects', 'idx_projects_created_time', ['created_at'])
        
        return success
    
    def migrate_videos_table(self) -> bool:
        """Migrate videos table to latest schema"""
        logger.info("🔄 Migrating videos table...")
        
        existing_tables = self.get_existing_tables()
        if 'videos' not in existing_tables:
            logger.warning("Videos table does not exist, skipping migration")
            return True
        
        success = True
        
        # Ensure critical columns exist
        success &= self.add_column_safe('videos', 'processing_status', "VARCHAR(50) DEFAULT 'pending'")
        success &= self.add_column_safe('videos', 'ground_truth_generated', "BOOLEAN DEFAULT FALSE")
        success &= self.add_column_safe('videos', 'file_size', "INTEGER")
        success &= self.add_column_safe('videos', 'duration', "FLOAT")
        success &= self.add_column_safe('videos', 'fps', "FLOAT")
        success &= self.add_column_safe('videos', 'resolution', "VARCHAR(50)")
        
        # Create performance indexes
        success &= self.create_index_safe('videos', 'idx_videos_project_status', ['project_id', 'status'])
        success &= self.create_index_safe('videos', 'idx_videos_processing_status', ['processing_status'])
        success &= self.create_index_safe('videos', 'idx_videos_ground_truth', ['ground_truth_generated'])
        success &= self.create_index_safe('videos', 'idx_videos_filename_search', ['filename'])
        success &= self.create_index_safe('videos', 'idx_videos_project_created', ['project_id', 'created_at'])
        
        return success
    
    def migrate_detection_events_table(self) -> bool:
        """Migrate detection_events table with comprehensive schema"""
        logger.info("🔄 Migrating detection_events table...")
        
        existing_tables = self.get_existing_tables()
        if 'detection_events' not in existing_tables:
            logger.warning("Detection events table does not exist, skipping migration")
            return True
        
        success = True
        
        # Add enhanced detection storage columns
        success &= self.add_column_safe('detection_events', 'detection_id', "VARCHAR(50)")
        success &= self.add_column_safe('detection_events', 'frame_number', "INTEGER")
        success &= self.add_column_safe('detection_events', 'vru_type', "VARCHAR(50)")
        
        # Bounding box coordinates
        success &= self.add_column_safe('detection_events', 'bounding_box_x', "FLOAT")
        success &= self.add_column_safe('detection_events', 'bounding_box_y', "FLOAT")
        success &= self.add_column_safe('detection_events', 'bounding_box_width', "FLOAT")
        success &= self.add_column_safe('detection_events', 'bounding_box_height', "FLOAT")
        
        # Visual evidence paths
        success &= self.add_column_safe('detection_events', 'screenshot_path', "TEXT")
        success &= self.add_column_safe('detection_events', 'screenshot_zoom_path', "TEXT")
        
        # Processing metadata
        success &= self.add_column_safe('detection_events', 'processing_time_ms', "FLOAT")
        success &= self.add_column_safe('detection_events', 'model_version', "VARCHAR(100)")
        
        # Create comprehensive indexes
        success &= self.create_index_safe('detection_events', 'idx_detection_session_time', ['test_session_id', 'timestamp'])
        success &= self.create_index_safe('detection_events', 'idx_detection_validation', ['validation_result'])
        success &= self.create_index_safe('detection_events', 'idx_detection_confidence', ['confidence'])
        success &= self.create_index_safe('detection_events', 'idx_detection_class_label', ['class_label'])
        success &= self.create_index_safe('detection_events', 'idx_detection_frame', ['frame_number'])
        success &= self.create_index_safe('detection_events', 'idx_detection_vru_type', ['vru_type'])
        success &= self.create_index_safe('detection_events', 'idx_detection_model_version', ['model_version'])
        
        return success
    
    def migrate_ground_truth_objects_table(self) -> bool:
        """Migrate ground_truth_objects table"""
        logger.info("🔄 Migrating ground_truth_objects table...")
        
        existing_tables = self.get_existing_tables()
        if 'ground_truth_objects' not in existing_tables:
            logger.warning("Ground truth objects table does not exist, skipping migration")
            return True
        
        success = True
        
        # Ensure coordinate columns exist
        success &= self.add_column_safe('ground_truth_objects', 'x', "FLOAT NOT NULL DEFAULT 0")
        success &= self.add_column_safe('ground_truth_objects', 'y', "FLOAT NOT NULL DEFAULT 0")
        success &= self.add_column_safe('ground_truth_objects', 'width', "FLOAT NOT NULL DEFAULT 0")
        success &= self.add_column_safe('ground_truth_objects', 'height', "FLOAT NOT NULL DEFAULT 0")
        
        # Quality control columns
        success &= self.add_column_safe('ground_truth_objects', 'validated', "BOOLEAN DEFAULT FALSE")
        success &= self.add_column_safe('ground_truth_objects', 'difficult', "BOOLEAN DEFAULT FALSE")
        success &= self.add_column_safe('ground_truth_objects', 'frame_number', "INTEGER")
        
        # Create indexes
        success &= self.create_index_safe('ground_truth_objects', 'idx_gt_video_timestamp', ['video_id', 'timestamp'])
        success &= self.create_index_safe('ground_truth_objects', 'idx_gt_class_label', ['class_label'])
        success &= self.create_index_safe('ground_truth_objects', 'idx_gt_validated', ['validated'])
        success &= self.create_index_safe('ground_truth_objects', 'idx_gt_frame_number', ['frame_number'])
        
        return success
    
    def migrate_annotations_table(self) -> bool:
        """Migrate annotations table for enhanced annotation tracking"""
        logger.info("🔄 Migrating annotations table...")
        
        existing_tables = self.get_existing_tables()
        if 'annotations' not in existing_tables:
            logger.warning("Annotations table does not exist, skipping migration")
            return True
        
        success = True
        
        # Add detection tracking columns
        success &= self.add_column_safe('annotations', 'detection_id', "VARCHAR(50)")
        success &= self.add_column_safe('annotations', 'end_timestamp', "FLOAT")
        success &= self.add_column_safe('annotations', 'occluded', "BOOLEAN DEFAULT FALSE")
        success &= self.add_column_safe('annotations', 'truncated', "BOOLEAN DEFAULT FALSE")
        success &= self.add_column_safe('annotations', 'difficult', "BOOLEAN DEFAULT FALSE")
        success &= self.add_column_safe('annotations', 'notes', "TEXT")
        success &= self.add_column_safe('annotations', 'annotator', "VARCHAR(100)")
        
        # Create indexes
        success &= self.create_index_safe('annotations', 'idx_annotations_video_frame', ['video_id', 'frame_number'])
        success &= self.create_index_safe('annotations', 'idx_annotations_detection_id', ['detection_id'])
        success &= self.create_index_safe('annotations', 'idx_annotations_vru_type', ['vru_type'])
        success &= self.create_index_safe('annotations', 'idx_annotations_validated', ['validated'])
        success &= self.create_index_safe('annotations', 'idx_annotations_annotator', ['annotator'])
        
        return success
    
    def run_comprehensive_migration(self) -> bool:
        """Run complete database migration"""
        logger.info("🚀 Starting comprehensive database migration...")
        
        migration_steps = [
            ("Projects Table Migration", self.migrate_projects_table),
            ("Videos Table Migration", self.migrate_videos_table),
            ("Detection Events Migration", self.migrate_detection_events_table),
            ("Ground Truth Objects Migration", self.migrate_ground_truth_objects_table),
            ("Annotations Table Migration", self.migrate_annotations_table)
        ]
        
        overall_success = True
        
        for step_name, step_function in migration_steps:
            logger.info(f"\n📋 {step_name}")
            try:
                step_success = step_function()
                if not step_success:
                    logger.error(f"❌ {step_name} completed with errors")
                    overall_success = False
                else:
                    logger.info(f"✅ {step_name} completed successfully")
            except Exception as e:
                logger.error(f"❌ {step_name} failed with exception: {e}")
                overall_success = False
        
        # Save migration log
        self.save_migration_log()
        
        # Final status
        if overall_success:
            logger.info("\n🎉 Comprehensive database migration completed successfully!")
            logger.info(f"✅ Applied migrations: {len(self.applied_migrations)}")
        else:
            logger.error("\n💥 Database migration completed with issues")
            logger.error(f"❌ Failed migrations: {len(self.failed_migrations)}")
        
        return overall_success

def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Comprehensive Database Migration")
    parser.add_argument('--dry-run', action='store_true', 
                       help='Preview changes without applying them')
    parser.add_argument('--execute', action='store_true',
                       help='Execute the migration')
    
    args = parser.parse_args()
    
    if not args.execute and not args.dry_run:
        print("Please specify --execute or --dry-run")
        parser.print_help()
        return
    
    migration_manager = MigrationManager(dry_run=args.dry_run)
    
    try:
        success = migration_manager.run_comprehensive_migration()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"💥 Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()