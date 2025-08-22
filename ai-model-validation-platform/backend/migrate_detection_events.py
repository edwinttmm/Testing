#!/usr/bin/env python3
"""
Database Migration Script for DetectionEvent Model
Adds missing fields for complete detection storage with visual evidence
"""
import sys
import os
from pathlib import Path
import logging
from sqlalchemy import text, inspect, MetaData

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import engine, get_db
from models import Base, DetectionEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectionEventMigration:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
    
    def check_table_exists(self, table_name: str) -> bool:
        """Check if table exists"""
        return table_name in self.inspector.get_table_names()
    
    def get_existing_columns(self, table_name: str) -> list:
        """Get list of existing column names"""
        if not self.check_table_exists(table_name):
            return []
        return [col['name'] for col in self.inspector.get_columns(table_name)]
    
    def add_column_if_not_exists(self, table_name: str, column_name: str, column_definition: str):
        """Add column if it doesn't exist"""
        existing_columns = self.get_existing_columns(table_name)
        
        if column_name not in existing_columns:
            try:
                sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                with self.engine.connect() as conn:
                    conn.execute(text(sql))
                    conn.commit()
                logger.info(f"✅ Added column: {table_name}.{column_name}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to add column {column_name}: {e}")
                return False
        else:
            logger.info(f"⏭️  Column {table_name}.{column_name} already exists")
            return True
    
    def create_index_if_not_exists(self, index_name: str, table_name: str, columns: list):
        """Create index if it doesn't exist"""
        try:
            # Check if index exists
            existing_indexes = [idx['name'] for idx in self.inspector.get_indexes(table_name)]
            if index_name in existing_indexes:
                logger.info(f"⏭️  Index {index_name} already exists")
                return True
            
            # Create index
            columns_str = ', '.join(columns)
            sql = f"CREATE INDEX {index_name} ON {table_name} ({columns_str})"
            with self.engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            logger.info(f"✅ Created index: {index_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create index {index_name}: {e}")
            return False
    
    def migrate_detection_events(self):
        """Add missing fields to detection_events table"""
        logger.info("🚀 Starting DetectionEvent table migration...")
        
        table_name = "detection_events"
        
        # Check if table exists
        if not self.check_table_exists(table_name):
            logger.error(f"❌ Table {table_name} does not exist!")
            return False
        
        logger.info(f"📋 Current columns: {self.get_existing_columns(table_name)}")
        
        # Define new columns to add
        new_columns = [
            ("detection_id", "VARCHAR(36)"),
            ("frame_number", "INTEGER"),
            ("vru_type", "VARCHAR(50)"),
            ("bounding_box_x", "FLOAT"),
            ("bounding_box_y", "FLOAT"),
            ("bounding_box_width", "FLOAT"),
            ("bounding_box_height", "FLOAT"),
            ("screenshot_path", "VARCHAR(500)"),
            ("screenshot_zoom_path", "VARCHAR(500)"),
            ("processing_time_ms", "FLOAT"),
            ("model_version", "VARCHAR(50)")
        ]
        
        # Add each new column
        success_count = 0
        for column_name, column_type in new_columns:
            if self.add_column_if_not_exists(table_name, column_name, column_type):
                success_count += 1
        
        # Create new indexes
        new_indexes = [
            ("idx_detection_frame_class", ["frame_number", "class_label"]),
            ("idx_detection_bbox_area", ["bounding_box_width", "bounding_box_height"]),
            ("idx_detection_id", ["detection_id"]),
            ("idx_detection_vru_type", ["vru_type"])
        ]
        
        index_success_count = 0
        for index_name, columns in new_indexes:
            if self.create_index_if_not_exists(index_name, table_name, columns):
                index_success_count += 1
        
        logger.info(f"📊 Migration Summary:")
        logger.info(f"   - New columns added: {success_count}/{len(new_columns)}")
        logger.info(f"   - New indexes created: {index_success_count}/{len(new_indexes)}")
        
        if success_count == len(new_columns) and index_success_count == len(new_indexes):
            logger.info("🎉 DetectionEvent migration completed successfully!")
            return True
        else:
            logger.warning("⚠️  Migration completed with some issues")
            return False
    
    def verify_migration(self):
        """Verify migration was successful"""
        logger.info("🔍 Verifying migration...")
        
        table_name = "detection_events"
        existing_columns = self.get_existing_columns(table_name)
        
        required_columns = [
            "detection_id", "frame_number", "vru_type",
            "bounding_box_x", "bounding_box_y", "bounding_box_width", "bounding_box_height",
            "screenshot_path", "screenshot_zoom_path", "processing_time_ms", "model_version"
        ]
        
        missing_columns = [col for col in required_columns if col not in existing_columns]
        
        if not missing_columns:
            logger.info("✅ All required columns present!")
            logger.info(f"📋 Total columns: {len(existing_columns)}")
            return True
        else:
            logger.error(f"❌ Missing columns: {missing_columns}")
            return False
    
    def create_screenshots_directory(self):
        """Ensure screenshots directory exists"""
        screenshots_dir = Path("/app/screenshots")
        try:
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Screenshots directory ready: {screenshots_dir}")
            
            # Create subdirectories for organization
            (screenshots_dir / "detections").mkdir(exist_ok=True)
            (screenshots_dir / "zoomed").mkdir(exist_ok=True)
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create screenshots directory: {e}")
            return False

def main():
    """Run the migration"""
    print("🗃️  DetectionEvent Database Migration")
    print("=" * 50)
    
    migrator = DetectionEventMigration()
    
    try:
        # Create screenshots directory
        migrator.create_screenshots_directory()
        
        # Run migration
        success = migrator.migrate_detection_events()
        
        if success:
            # Verify migration
            if migrator.verify_migration():
                print("\n🎉 Migration completed successfully!")
                print("\nNext steps:")
                print("1. Restart the backend server")
                print("2. Run detection pipeline to test database storage")
                print("3. Check /app/screenshots for visual evidence")
                return 0
            else:
                print("\n❌ Migration verification failed!")
                return 1
        else:
            print("\n❌ Migration failed!")
            return 1
            
    except Exception as e:
        logger.error(f"💥 Migration error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())