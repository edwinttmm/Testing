#!/usr/bin/env python3
"""
Comprehensive Database Migration Script for Video Processing Platform
Fixes all database schema issues identified in analysis
"""
import sys
import os
import logging
from pathlib import Path

# Add the backend directory to the Python path
backend_path = Path(__file__).parent.parent / "ai-model-validation-platform" / "backend"
sys.path.append(str(backend_path))

try:
    from sqlalchemy import text, inspect, MetaData, Table, Column, String, Boolean, Float, Integer, DateTime, JSON, ForeignKey, Index
    from sqlalchemy.sql import func
    from database import engine, SessionLocal
    from models import Base, Video, GroundTruthObject
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the correct directory")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    """Comprehensive database migration and schema validation"""
    
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
        
    def check_column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            columns = [col['name'] for col in self.inspector.get_columns(table_name)]
            return column_name in columns
        except Exception:
            return False
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        return table_name in self.inspector.get_table_names()
    
    def add_missing_columns(self):
        """Add missing columns to existing tables"""
        logger.info("🔍 Checking for missing columns...")
        
        migrations = []
        
        # Check videos table
        if self.check_table_exists('videos'):
            if not self.check_column_exists('videos', 'processing_status'):
                migrations.append({
                    'table': 'videos',
                    'column': 'processing_status',
                    'sql': "ALTER TABLE videos ADD COLUMN processing_status VARCHAR DEFAULT 'pending'"
                })
            
            if not self.check_column_exists('videos', 'ground_truth_generated'):
                migrations.append({
                    'table': 'videos',
                    'column': 'ground_truth_generated',
                    'sql': "ALTER TABLE videos ADD COLUMN ground_truth_generated BOOLEAN DEFAULT FALSE"
                })
        
        # Check ground_truth_objects table
        if self.check_table_exists('ground_truth_objects'):
            missing_columns = [
                ('frame_number', "ALTER TABLE ground_truth_objects ADD COLUMN frame_number INTEGER"),
                ('validated', "ALTER TABLE ground_truth_objects ADD COLUMN validated BOOLEAN DEFAULT FALSE"),
                ('difficult', "ALTER TABLE ground_truth_objects ADD COLUMN difficult BOOLEAN DEFAULT FALSE"),
                ('x', "ALTER TABLE ground_truth_objects ADD COLUMN x FLOAT"),
                ('y', "ALTER TABLE ground_truth_objects ADD COLUMN y FLOAT"),
                ('width', "ALTER TABLE ground_truth_objects ADD COLUMN width FLOAT"),
                ('height', "ALTER TABLE ground_truth_objects ADD COLUMN height FLOAT"),
            ]
            
            for col_name, sql in missing_columns:
                if not self.check_column_exists('ground_truth_objects', col_name):
                    migrations.append({
                        'table': 'ground_truth_objects',
                        'column': col_name,
                        'sql': sql
                    })
        
        # Execute migrations
        if migrations:
            logger.info(f"📝 Executing {len(migrations)} migrations...")
            with self.engine.connect() as connection:
                for migration in migrations:
                    try:
                        logger.info(f"Adding {migration['column']} to {migration['table']}")
                        connection.execute(text(migration['sql']))
                        connection.commit()
                        logger.info(f"✅ Added {migration['column']} to {migration['table']}")
                    except Exception as e:
                        logger.error(f"❌ Failed to add {migration['column']}: {e}")
                        # Continue with other migrations
                        continue
        else:
            logger.info("✅ All required columns already exist")
    
    def create_missing_tables(self):
        """Create any missing tables"""
        logger.info("🔍 Checking for missing tables...")
        
        # Use SQLAlchemy metadata to create missing tables
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ All tables created/verified")
        except Exception as e:
            logger.error(f"❌ Error creating tables: {e}")
    
    def create_indexes(self):
        """Create missing indexes for performance"""
        logger.info("🔍 Creating performance indexes...")
        
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_videos_processing_status ON videos(processing_status)",
            "CREATE INDEX IF NOT EXISTS idx_videos_project_status ON videos(project_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_videos_ground_truth ON videos(ground_truth_generated)",
            "CREATE INDEX IF NOT EXISTS idx_gt_video_timestamp ON ground_truth_objects(video_id, timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_gt_video_class ON ground_truth_objects(video_id, class_label)",
        ]
        
        with self.engine.connect() as connection:
            for index_sql in indexes:
                try:
                    connection.execute(text(index_sql))
                    connection.commit()
                    logger.info(f"✅ Created index: {index_sql.split('idx_')[1].split(' ')[0]}")
                except Exception as e:
                    logger.warning(f"⚠️ Index might already exist: {e}")
    
    def update_existing_data(self):
        """Update existing data to match new schema"""
        logger.info("🔄 Updating existing data...")
        
        updates = [
            """
            UPDATE videos 
            SET processing_status = CASE 
                WHEN ground_truth_generated = TRUE THEN 'completed'
                WHEN status = 'processing' THEN 'processing'
                ELSE 'pending'
            END
            WHERE processing_status IS NULL OR processing_status = ''
            """,
            """
            UPDATE videos 
            SET ground_truth_generated = FALSE 
            WHERE ground_truth_generated IS NULL
            """
        ]
        
        with self.engine.connect() as connection:
            for update_sql in updates:
                try:
                    result = connection.execute(text(update_sql))
                    connection.commit()
                    logger.info(f"✅ Updated {result.rowcount} rows")
                except Exception as e:
                    logger.error(f"❌ Update failed: {e}")
    
    def validate_schema(self):
        """Validate the final schema"""
        logger.info("🔍 Validating final schema...")
        
        required_tables = ['videos', 'projects', 'ground_truth_objects', 'test_sessions', 'detection_events']
        required_video_columns = ['id', 'filename', 'file_path', 'status', 'processing_status', 'ground_truth_generated', 'project_id']
        required_gt_columns = ['id', 'video_id', 'timestamp', 'class_label', 'x', 'y', 'width', 'height']
        
        # Check tables
        missing_tables = []
        for table in required_tables:
            if not self.check_table_exists(table):
                missing_tables.append(table)
        
        if missing_tables:
            logger.error(f"❌ Missing tables: {missing_tables}")
            return False
        
        # Check video columns
        missing_video_cols = []
        for col in required_video_columns:
            if not self.check_column_exists('videos', col):
                missing_video_cols.append(col)
        
        if missing_video_cols:
            logger.error(f"❌ Missing video columns: {missing_video_cols}")
            return False
        
        # Check ground truth columns
        missing_gt_cols = []
        for col in required_gt_columns:
            if not self.check_column_exists('ground_truth_objects', col):
                missing_gt_cols.append(col)
        
        if missing_gt_cols:
            logger.error(f"❌ Missing ground truth columns: {missing_gt_cols}")
            return False
        
        logger.info("✅ Schema validation passed!")
        return True
    
    def run_full_migration(self):
        """Run the complete migration process"""
        logger.info("🚀 Starting comprehensive database migration...")
        
        try:
            # Step 1: Create missing tables
            self.create_missing_tables()
            
            # Step 2: Add missing columns
            self.add_missing_columns()
            
            # Step 3: Create indexes
            self.create_indexes()
            
            # Step 4: Update existing data
            self.update_existing_data()
            
            # Step 5: Validate schema
            if self.validate_schema():
                logger.info("🎉 Migration completed successfully!")
                return True
            else:
                logger.error("❌ Migration validation failed!")
                return False
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False

def main():
    """Main migration runner"""
    print("🚀 Starting Database Migration for Video Processing Platform")
    print("=" * 60)
    
    migrator = DatabaseMigrator()
    
    if migrator.run_full_migration():
        print("\n✅ Migration completed successfully!")
        print("The video processing platform database is now ready.")
        return 0
    else:
        print("\n❌ Migration failed!")
        print("Please check the logs and fix any issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())