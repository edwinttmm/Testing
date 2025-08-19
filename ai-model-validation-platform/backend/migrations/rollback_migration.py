"""
Database Rollback Script: Remove Added Columns
This script provides rollback functionality for the migration script.
Use this if you need to undo the migration changes.
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

from database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseRollback:
    def __init__(self):
        self.engine = engine
        self.inspector = inspect(engine)
        self.successful_rollbacks = []
        self.failed_rollbacks = []

    def check_column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            columns = self.inspector.get_columns(table_name)
            return any(col['name'] == column_name for col in columns)
        except Exception as e:
            logger.error(f"Error checking column {column_name} in table {table_name}: {e}")
            return False

    def drop_column_safe(self, table_name: str, column_name: str):
        """Safely drop a column from a table"""
        try:
            if self.check_column_exists(table_name, column_name):
                with self.engine.connect() as conn:
                    # Use ALTER TABLE to drop the column
                    sql = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"✅ Dropped column {column_name} from {table_name}")
                    self.successful_rollbacks.append(f"{table_name}.{column_name}")
            else:
                logger.info(f"⚠️  Column {column_name} doesn't exist in {table_name}")
        except Exception as e:
            logger.error(f"❌ Failed to drop column {column_name} from {table_name}: {e}")
            self.failed_rollbacks.append(f"{table_name}.{column_name}: {str(e)}")

    def drop_index_safe(self, index_name: str):
        """Safely drop an index if it exists"""
        try:
            with self.engine.connect() as conn:
                # Check if index exists
                result = conn.execute(text(f"""
                    SELECT indexname FROM pg_indexes 
                    WHERE indexname = '{index_name}'
                """))
                
                if result.fetchone():
                    sql = f"DROP INDEX IF EXISTS {index_name}"
                    conn.execute(text(sql))
                    conn.commit()
                    logger.info(f"✅ Dropped index {index_name}")
                    self.successful_rollbacks.append(f"index.{index_name}")
                else:
                    logger.info(f"⚠️  Index {index_name} doesn't exist")
        except Exception as e:
            logger.error(f"❌ Failed to drop index {index_name}: {e}")
            self.failed_rollbacks.append(f"index.{index_name}: {str(e)}")

    def rollback_videos_table(self):
        """Rollback videos table changes"""
        logger.info("🔄 Rolling back videos table...")
        
        # Drop indexes first
        self.drop_index_safe("idx_videos_processing_status")
        self.drop_index_safe("idx_videos_ground_truth_generated")
        
        # Note: Don't drop processing_status and ground_truth_generated as they are core model fields

    def rollback_ground_truth_objects_table(self):
        """Rollback ground_truth_objects table changes"""
        logger.info("🔄 Rolling back ground_truth_objects table...")
        
        # Only drop columns that were added in migration (not core model fields)
        # The x, y, width, height, validated, difficult should remain as they're in the model

    def rollback_annotations_table(self):
        """Rollback annotations table changes"""
        logger.info("🔄 Rolling back annotations table...")
        
        # Only drop columns that were incorrectly added
        # Most of these should remain as they're in the actual model

    def run_rollback(self):
        """Run the complete rollback"""
        logger.info("🚀 Starting database rollback...")
        
        try:
            # Test database connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("✅ Database connection successful")
            
            # Run rollbacks
            self.rollback_videos_table()
            self.rollback_ground_truth_objects_table()
            self.rollback_annotations_table()
            
            # Summary
            logger.info(f"✅ Successful rollbacks: {len(self.successful_rollbacks)}")
            for success in self.successful_rollbacks:
                logger.info(f"   - {success}")
            
            if self.failed_rollbacks:
                logger.info(f"❌ Failed rollbacks: {len(self.failed_rollbacks)}")
                for failure in self.failed_rollbacks:
                    logger.error(f"   - {failure}")
                    
            logger.info("🎉 Rollback completed!")
            
        except Exception as e:
            logger.error(f"💥 Rollback failed with error: {e}")
            raise

def main():
    """Main rollback function"""
    rollback = DatabaseRollback()
    
    # Confirm with user
    response = input("⚠️  Are you sure you want to rollback the database migration? (yes/no): ")
    if response.lower() in ['yes', 'y']:
        rollback.run_rollback()
    else:
        logger.info("Rollback cancelled by user")

if __name__ == "__main__":
    main()