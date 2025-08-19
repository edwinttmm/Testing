"""
Database Initialization Script
This script initializes the database with all tables and proper schema.
Use this for fresh database setups or after major schema changes.
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

from database import engine, Base
from models import *

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)

    def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        try:
            return table_name in self.inspector.get_table_names()
        except Exception as e:
            logger.error(f"Error checking table {table_name}: {e}")
            return False

    def create_all_tables(self):
        """Create all tables from models"""
        try:
            logger.info("🚀 Creating all database tables...")
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ All tables created successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            return False

    def verify_schema(self):
        """Verify that all expected tables and columns exist"""
        logger.info("🔍 Verifying database schema...")
        
        expected_tables = [
            "projects", "videos", "ground_truth_objects", "test_sessions",
            "detection_events", "annotations", "annotation_sessions",
            "video_project_links", "test_results", "detection_comparisons",
            "audit_logs"
        ]
        
        all_good = True
        for table in expected_tables:
            if self.check_table_exists(table):
                logger.info(f"✅ Table {table} exists")
                
                # Check key columns for critical tables
                if table == "videos":
                    self._verify_video_columns()
                elif table == "ground_truth_objects":
                    self._verify_ground_truth_columns()
                elif table == "annotations":
                    self._verify_annotation_columns()
            else:
                logger.error(f"❌ Table {table} missing")
                all_good = False
        
        return all_good

    def _verify_video_columns(self):
        """Verify videos table has all required columns"""
        required_columns = [
            "id", "filename", "file_path", "project_id", "status",
            "processing_status", "ground_truth_generated"
        ]
        self._check_table_columns("videos", required_columns)

    def _verify_ground_truth_columns(self):
        """Verify ground_truth_objects table has all required columns"""
        required_columns = [
            "id", "video_id", "timestamp", "class_label",
            "x", "y", "width", "height", "confidence", "validated"
        ]
        self._check_table_columns("ground_truth_objects", required_columns)

    def _verify_annotation_columns(self):
        """Verify annotations table has all required columns"""
        required_columns = [
            "id", "video_id", "frame_number", "timestamp", "vru_type",
            "bounding_box", "validated", "detection_id"
        ]
        self._check_table_columns("annotations", required_columns)

    def _check_table_columns(self, table_name: str, required_columns: list):
        """Check if table has all required columns"""
        try:
            columns = self.inspector.get_columns(table_name)
            existing_columns = {col['name'] for col in columns}
            
            for column in required_columns:
                if column in existing_columns:
                    logger.info(f"  ✅ {table_name}.{column}")
                else:
                    logger.error(f"  ❌ {table_name}.{column} missing")
        except Exception as e:
            logger.error(f"Error checking columns for {table_name}: {e}")

    def create_initial_data(self):
        """Create some initial test data"""
        logger.info("🔄 Creating initial test data...")
        
        try:
            with self.engine.connect() as conn:
                # Create a default project
                conn.execute(text("""
                    INSERT INTO projects (id, name, description, camera_model, camera_view, signal_type, status)
                    VALUES ('default-project-001', 'Default Test Project', 'Initial test project for validation', 
                            'TestCam-HD', 'Front-facing VRU', 'GPIO', 'Active')
                    ON CONFLICT (id) DO NOTHING
                """))
                
                conn.commit()
                logger.info("✅ Initial test data created")
        except Exception as e:
            logger.error(f"❌ Failed to create initial data: {e}")

    def run_initialization(self):
        """Run complete database initialization"""
        logger.info("🚀 Starting database initialization...")
        
        try:
            # Test database connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
            
            # Create all tables
            if self.create_all_tables():
                logger.info("✅ Table creation successful")
            else:
                logger.error("❌ Table creation failed")
                return False
            
            # Verify schema
            if self.verify_schema():
                logger.info("✅ Schema verification successful")
            else:
                logger.warning("⚠️  Schema verification found issues")
            
            # Create initial data
            self.create_initial_data()
            
            logger.info("🎉 Database initialization completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"💥 Initialization failed with error: {e}")
            raise

def main():
    """Main initialization function"""
    initializer = DatabaseInitializer()
    
    # Confirm with user for fresh initialization
    response = input("🔄 Initialize database? This will create all tables. Continue? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        initializer.run_initialization()
    else:
        logger.info("Initialization cancelled by user")

if __name__ == "__main__":
    main()