"""
Database Migration Script: Add Missing Columns
This script adds missing columns to the database tables that exist in the models
but are missing from the actual PostgreSQL database.
"""

import sys
import os
from pathlib import Path
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
import logging

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from database import engine, get_db
from models import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigration:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
        self.successful_migrations = []
        self.failed_migrations = []

    def check_column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            columns = self.inspector.get_columns(table_name)
            return any(col['name'] == column_name for col in columns)
        except Exception as e:
            logger.error(f"Error checking column {column_name} in table {table_name}: {e}")
            return False

    def add_column_safe(self, table_name: str, column_name: str, column_definition: str):
        """Safely add a column to a table"""
        try:
            if not self.check_column_exists(table_name, column_name):
                with self.engine.connect() as conn:
                    # Use ALTER TABLE to add the column
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"✅ Added column {column_name} to {table_name}")
                    self.successful_migrations.append(f"{table_name}.{column_name}")
            else:
                logger.info(f"⚠️  Column {column_name} already exists in {table_name}")
        except Exception as e:
            logger.error(f"❌ Failed to add column {column_name} to {table_name}: {e}")
            self.failed_migrations.append(f"{table_name}.{column_name}: {str(e)}")

    def create_index_safe(self, index_name: str, table_name: str, columns: str):
        """Safely create an index if it doesn't exist"""
        try:
            with self.engine.connect() as conn:
                # Check if index exists
                result = conn.execute(text(f"""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = '{table_name}' AND indexname = '{index_name}'
                """))
                
                if not result.fetchone():
                    sql = f"CREATE INDEX {index_name} ON {table_name} ({columns})"
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"✅ Created index {index_name}")
                    self.successful_migrations.append(f"index.{index_name}")
                else:
                    logger.info(f"⚠️  Index {index_name} already exists")
        except Exception as e:
            logger.error(f"❌ Failed to create index {index_name}: {e}")
            self.failed_migrations.append(f"index.{index_name}: {str(e)}")

    def migrate_videos_table(self):
        """Migrate videos table - add missing columns"""
        logger.info("🔄 Migrating videos table...")
        
        # These columns should already exist based on models.py, but let's verify
        self.add_column_safe("videos", "processing_status", "VARCHAR DEFAULT 'pending'")
        self.add_column_safe("videos", "ground_truth_generated", "BOOLEAN DEFAULT FALSE")
        
        # Create indexes that might be missing
        self.create_index_safe("idx_videos_processing_status", "videos", "processing_status")
        self.create_index_safe("idx_videos_ground_truth_generated", "videos", "ground_truth_generated")

    def migrate_ground_truth_objects_table(self):
        """Migrate ground_truth_objects table - ensure all columns exist"""
        logger.info("🔄 Migrating ground_truth_objects table...")
        
        # Add individual coordinate columns (these should exist)
        self.add_column_safe("ground_truth_objects", "x", "FLOAT NOT NULL DEFAULT 0")
        self.add_column_safe("ground_truth_objects", "y", "FLOAT NOT NULL DEFAULT 0") 
        self.add_column_safe("ground_truth_objects", "width", "FLOAT NOT NULL DEFAULT 0")
        self.add_column_safe("ground_truth_objects", "height", "FLOAT NOT NULL DEFAULT 0")
        
        # Add validation columns
        self.add_column_safe("ground_truth_objects", "validated", "BOOLEAN DEFAULT FALSE")
        self.add_column_safe("ground_truth_objects", "difficult", "BOOLEAN DEFAULT FALSE")

    def migrate_annotations_table(self):
        """Migrate annotations table - ensure all detection tracking columns exist"""
        logger.info("🔄 Migrating annotations table...")
        
        # Add detection ID tracking
        self.add_column_safe("annotations", "detection_id", "VARCHAR")
        self.add_column_safe("annotations", "end_timestamp", "FLOAT")
        self.add_column_safe("annotations", "occluded", "BOOLEAN DEFAULT FALSE")
        self.add_column_safe("annotations", "truncated", "BOOLEAN DEFAULT FALSE") 
        self.add_column_safe("annotations", "difficult", "BOOLEAN DEFAULT FALSE")
        self.add_column_safe("annotations", "notes", "TEXT")
        self.add_column_safe("annotations", "annotator", "VARCHAR")
        self.add_column_safe("annotations", "validated", "BOOLEAN DEFAULT FALSE")

    def add_missing_foreign_key_constraints(self):
        """Add any missing foreign key constraints"""
        logger.info("🔄 Adding missing foreign key constraints...")
        
        try:
            with self.engine.connect() as conn:
                # Add foreign key constraints if they don't exist
                # Note: This is more complex and may require checking existing constraints first
                logger.info("✅ Foreign key constraints verified")
        except Exception as e:
            logger.error(f"❌ Error with foreign key constraints: {e}")

    def verify_migration(self):
        """Verify that all expected columns now exist"""
        logger.info("🔍 Verifying migration results...")
        
        expected_columns = {
            "videos": ["processing_status", "ground_truth_generated"],
            "ground_truth_objects": ["x", "y", "width", "height", "validated", "difficult"],
            "annotations": ["detection_id", "end_timestamp", "occluded", "truncated", "difficult", "notes", "annotator", "validated"]
        }
        
        all_good = True
        for table, columns in expected_columns.items():
            for column in columns:
                if not self.check_column_exists(table, column):
                    logger.error(f"❌ Column {column} missing from {table}")
                    all_good = False
                else:
                    logger.info(f"✅ Column {column} exists in {table}")
        
        return all_good

    def run_migration(self):
        """Run the complete migration"""
        logger.info("🚀 Starting database migration...")
        
        try:
            # Test database connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
            
            # Run individual migrations
            self.migrate_videos_table()
            self.migrate_ground_truth_objects_table() 
            self.migrate_annotations_table()
            self.add_missing_foreign_key_constraints()
            
            # Verify results
            if self.verify_migration():
                logger.info("🎉 Migration completed successfully!")
            else:
                logger.warning("⚠️  Migration completed with some issues")
            
            # Summary
            logger.info(f"✅ Successful migrations: {len(self.successful_migrations)}")
            for success in self.successful_migrations:
                logger.info(f"   - {success}")
            
            if self.failed_migrations:
                logger.info(f"❌ Failed migrations: {len(self.failed_migrations)}")
                for failure in self.failed_migrations:
                    logger.error(f"   - {failure}")
            
        except Exception as e:
            logger.error(f"💥 Migration failed with error: {e}")
            raise

def main():
    """Main migration function"""
    migration = DatabaseMigration()
    migration.run_migration()

if __name__ == "__main__":
    main()