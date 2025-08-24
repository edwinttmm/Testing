#!/usr/bin/env python3
"""
Quick database fix script to resolve table creation issues
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.exc import SQLAlchemyError

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database import engine, Base, SessionLocal
from config import settings
import models  # Import all models

def drop_all_objects():
    """Drop all existing database objects to start fresh"""
    print("🧹 Cleaning up existing database objects...")
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        try:
            # Drop all indexes first
            inspector = inspect(engine)
            
            # Get all table names
            table_names = inspector.get_table_names()
            print(f"Found {len(table_names)} existing tables: {table_names}")
            
            # Drop all indexes on all tables
            for table_name in table_names:
                indexes = inspector.get_indexes(table_name)
                for index in indexes:
                    try:
                        conn.execute(text(f"DROP INDEX IF EXISTS {index['name']} CASCADE"))
                        print(f"  ✅ Dropped index: {index['name']}")
                    except Exception as e:
                        print(f"  ⚠️ Could not drop index {index['name']}: {e}")
            
            # Drop all foreign key constraints
            for table_name in table_names:
                foreign_keys = inspector.get_foreign_keys(table_name)
                for fk in foreign_keys:
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {fk['name']} CASCADE"))
                        print(f"  ✅ Dropped foreign key: {fk['name']}")
                    except Exception as e:
                        print(f"  ⚠️ Could not drop foreign key {fk['name']}: {e}")
            
            # Drop all tables
            for table_name in table_names:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                    print(f"  ✅ Dropped table: {table_name}")
                except Exception as e:
                    print(f"  ⚠️ Could not drop table {table_name}: {e}")
            
            # Also drop any leftover indexes that might exist
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_video_project_created CASCADE"))
                print("  ✅ Dropped leftover index: idx_video_project_created")
            except:
                pass
            
            trans.commit()
            print("🧹 Database cleanup completed successfully")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Error during cleanup: {e}")
            raise

def create_fresh_tables():
    """Create all tables from scratch"""
    print("🏗️ Creating fresh database tables...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"✅ Created {len(tables)} tables: {tables}")
        
        if len(tables) >= 11:  # We expect at least 11 tables
            print("🎉 Database initialization successful!")
            return True
        else:
            print(f"⚠️ Warning: Only {len(tables)} tables created, expected at least 11")
            return False
            
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

def main():
    """Main function to fix database issues"""
    print("🔧 Starting database fix process...")
    print(f"Database URL: {settings.database_url}")
    
    try:
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Database connection successful")
        
        # Step 1: Clean up existing objects
        drop_all_objects()
        
        # Step 2: Create fresh tables
        success = create_fresh_tables()
        
        if success:
            print("\n🎉 Database fix completed successfully!")
            print("You can now restart your backend with: docker-compose restart backend")
        else:
            print("\n❌ Database fix failed!")
            return 1
            
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())