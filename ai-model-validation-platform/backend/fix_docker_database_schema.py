#!/usr/bin/env python3
"""
Fix the database schema in the Docker container by adding the missing detection_id column
"""

import os
import sys
import asyncio
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables"""
    # Try common environment variable names
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        db_url = os.getenv('DB_URL')
    if not db_url:
        # Construct from components
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'ai_validation')
        db_user = os.getenv('DB_USER', 'postgres')
        db_pass = os.getenv('DB_PASSWORD', 'password')
        
        db_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    logger.info(f"Using database URL: {db_url.replace(db_pass, '***') if db_pass else db_url}")
    return db_url

def fix_detection_events_schema():
    """Add missing detection_id column to detection_events table"""
    
    try:
        db_url = get_database_url()
        engine = create_engine(db_url)
        
        # Test connection
        with engine.connect() as conn:
            logger.info("✅ Database connection successful")
            
            # Check if table exists
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if 'detection_events' not in tables:
                logger.error("❌ detection_events table does not exist!")
                return False
            
            # Get current columns
            columns = [col['name'] for col in inspector.get_columns('detection_events')]
            logger.info(f"Current columns: {columns}")
            
            # Check if detection_id column is missing
            if 'detection_id' not in columns:
                logger.info("⚠️ detection_id column is missing. Adding it now...")
                
                # Add the missing column
                conn.execute(text("""
                    ALTER TABLE detection_events 
                    ADD COLUMN detection_id VARCHAR(36);
                """))
                conn.commit()
                
                logger.info("✅ Successfully added detection_id column!")
                
                # Optionally add index for performance
                try:
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_detection_events_detection_id 
                        ON detection_events(detection_id);
                    """))
                    conn.commit()
                    logger.info("✅ Added index on detection_id column")
                except Exception as e:
                    logger.warning(f"⚠️ Could not add index: {e}")
                
            else:
                logger.info("✅ detection_id column already exists")
            
            # Verify the fix
            columns_after = [col['name'] for col in inspector.get_columns('detection_events')]
            logger.info(f"Columns after fix: {columns_after}")
            
            if 'detection_id' in columns_after:
                logger.info("🎉 SCHEMA FIX SUCCESSFUL!")
                return True
            else:
                logger.error("❌ Failed to add detection_id column")
                return False
                
    except OperationalError as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.info("🔧 Trying with different connection parameters...")
        
        # Try alternative connection for Docker environment
        docker_db_url = "postgresql://postgres:password@db:5432/ai_validation"
        try:
            engine = create_engine(docker_db_url)
            with engine.connect() as conn:
                logger.info("✅ Connected using Docker database URL")
                # Repeat the schema fix with Docker connection
                return fix_schema_with_engine(engine)
        except Exception as docker_e:
            logger.error(f"❌ Docker database connection also failed: {docker_e}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return False

def fix_schema_with_engine(engine):
    """Helper function to fix schema with given engine"""
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('detection_events')]
            
            if 'detection_id' not in columns:
                conn.execute(text("""
                    ALTER TABLE detection_events 
                    ADD COLUMN detection_id VARCHAR(36);
                """))
                conn.commit()
                logger.info("✅ Added detection_id column with Docker connection")
                return True
            else:
                logger.info("✅ detection_id column already exists")
                return True
                
    except Exception as e:
        logger.error(f"❌ Failed to fix schema: {e}")
        return False

def create_migration_sql():
    """Create SQL migration file for manual execution"""
    
    migration_sql = """
-- Migration: Add detection_id column to detection_events table
-- Date: 2025-08-22
-- Issue: Column "detection_id" of relation "detection_events" does not exist

-- Add detection_id column
ALTER TABLE detection_events 
ADD COLUMN IF NOT EXISTS detection_id VARCHAR(36);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_detection_events_detection_id 
ON detection_events(detection_id);

-- Verify the change
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'detection_events' 
ORDER BY ordinal_position;
"""
    
    with open('add_detection_id_migration.sql', 'w') as f:
        f.write(migration_sql)
    
    logger.info("✅ Created add_detection_id_migration.sql")
    logger.info("📝 You can run this manually in your database if the automatic fix fails")

def main():
    logger.info("🔧 FIXING DETECTION_EVENTS TABLE SCHEMA")
    logger.info("="*50)
    
    # Create migration SQL file
    create_migration_sql()
    
    # Try to fix automatically
    success = fix_detection_events_schema()
    
    if success:
        logger.info("🎉 DATABASE SCHEMA FIXED SUCCESSFULLY!")
        logger.info("✅ detection_id column is now available")
        logger.info("✅ Detection pipeline should work correctly")
    else:
        logger.error("❌ AUTOMATIC FIX FAILED")
        logger.info("📝 Please run the SQL migration manually:")
        logger.info("   1. Connect to your PostgreSQL database")
        logger.info("   2. Run the SQL from add_detection_id_migration.sql")
        logger.info("   3. Restart the detection pipeline")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)