#!/usr/bin/env python3
"""
CRITICAL DATABASE SCHEMA MISMATCH FIX
=====================================

5 WHAT IF ANALYSIS IMPLEMENTATION:

1. What if validation_status field doesn't exist? → CREATE IT
2. What if validation_type field doesn't exist? → CREATE IT
3. What if hil_testing_ready field doesn't exist? → CREATE IT
4. What if ground_truth_count field doesn't exist? → CREATE IT
5. What if validated_at field doesn't exist? → CREATE IT

FIXES ALL: sqlite3.OperationalError: no such column: videos.validation_status
"""

import sqlite3
import shutil
import os
from datetime import datetime

def backup_database(db_path):
    """Create backup before schema changes"""
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
        
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(db_path, backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return True

def get_existing_columns(cursor):
    """Get current column structure"""
    cursor.execute('PRAGMA table_info(videos)')
    existing_columns = [col[1] for col in cursor.fetchall()]
    print(f"📋 Existing columns: {existing_columns}")
    return existing_columns

def add_missing_columns(cursor, existing_columns):
    """Add all missing Video model fields to database"""
    
    # Define all missing fields from Video model
    missing_fields = [
        ("validation_status", "VARCHAR DEFAULT 'pending'"),
        ("validation_type", "VARCHAR"),
        ("validated_at", "DATETIME"),
        ("validated_by", "VARCHAR(36)"),
        ("ground_truth_count", "INTEGER DEFAULT 0"),
        ("ground_truth_quality_score", "FLOAT"),
        ("ground_truth_completed_at", "DATETIME"),
        ("hil_testing_ready", "BOOLEAN DEFAULT 0"),
        ("hil_testing_approved_by", "VARCHAR(36)"),
        ("hil_testing_approved_at", "DATETIME")
    ]
    
    added_count = 0
    
    for field_name, field_type in missing_fields:
        if field_name not in existing_columns:
            try:
                alter_sql = f"ALTER TABLE videos ADD COLUMN {field_name} {field_type}"
                cursor.execute(alter_sql)
                print(f"✅ Added column: {field_name} ({field_type})")
                added_count += 1
            except Exception as e:
                print(f"❌ Failed to add {field_name}: {e}")
        else:
            print(f"⚪ Column {field_name} already exists")
    
    return added_count

def create_indexes(cursor):
    """Create performance indexes for new fields"""
    indexes = [
        ("idx_videos_validation_status", "validation_status"),
        ("idx_videos_hil_testing_ready", "hil_testing_ready"),
        ("idx_videos_validated_at", "validated_at"),
        ("idx_videos_ground_truth_count", "ground_truth_count")
    ]
    
    for index_name, column in indexes:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON videos({column})")
            print(f"✅ Created index: {index_name}")
        except Exception as e:
            print(f"⚠️  Index creation warning for {index_name}: {e}")

def verify_schema_fix(cursor):
    """Verify all required fields now exist"""
    cursor.execute('PRAGMA table_info(videos)')
    columns = cursor.fetchall()
    
    print("\n=== FINAL SCHEMA VERIFICATION ===")
    required_fields = [
        'validation_status', 'validation_type', 'validated_at', 'validated_by',
        'hil_testing_ready', 'hil_testing_approved_by', 'hil_testing_approved_at',
        'ground_truth_count', 'ground_truth_quality_score', 'ground_truth_completed_at'
    ]
    
    existing_fields = [col[1] for col in columns]
    missing_fields = [field for field in required_fields if field not in existing_fields]
    
    if missing_fields:
        print(f"❌ Still missing fields: {missing_fields}")
        return False
    else:
        print("✅ All required fields present!")
        print(f"📊 Total fields: {len(existing_fields)}")
        return True

def test_critical_queries(cursor):
    """Test queries that were failing before"""
    critical_queries = [
        "SELECT validation_status FROM videos LIMIT 1",
        "SELECT hil_testing_ready FROM videos LIMIT 1", 
        "SELECT ground_truth_count FROM videos LIMIT 1",
        "SELECT validated_at FROM videos LIMIT 1"
    ]
    
    print("\n=== TESTING CRITICAL QUERIES ===")
    for query in critical_queries:
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            print(f"✅ Query works: {query.split('FROM')[0]}...")
        except Exception as e:
            print(f"❌ Query still fails: {query} - {e}")
            return False
    
    return True

def fix_database_schema(db_path):
    """Main schema fix function"""
    print(f"🚀 Starting schema fix for: {db_path}")
    
    # Backup database
    if not backup_database(db_path):
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current state
        existing_columns = get_existing_columns(cursor)
        original_count = len(existing_columns)
        
        # Add missing columns
        added_count = add_missing_columns(cursor, existing_columns)
        
        # Create performance indexes
        create_indexes(cursor)
        
        # Verify fix
        if verify_schema_fix(cursor):
            print(f"✅ Schema fix successful! Added {added_count} fields.")
        else:
            print("❌ Schema fix incomplete!")
            return False
        
        # Test critical queries
        if test_critical_queries(cursor):
            print("✅ All critical queries now working!")
        else:
            print("❌ Some queries still failing!")
            return False
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print(f"🎉 DATABASE SCHEMA FIX COMPLETE!")
        print(f"📊 Fields: {original_count} → {original_count + added_count}")
        return True
        
    except Exception as e:
        print(f"❌ Schema fix failed: {e}")
        return False

if __name__ == "__main__":
    # Fix both development and test databases
    databases = [
        "/home/rigade/Testing/ai-model-validation-platform/backend/test_database.db",
        "/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db"
    ]
    
    success_count = 0
    
    for db_path in databases:
        if os.path.exists(db_path):
            if fix_database_schema(db_path):
                success_count += 1
                print(f"✅ {db_path} - FIXED")
            else:
                print(f"❌ {db_path} - FAILED")
        else:
            print(f"⚪ {db_path} - NOT FOUND")
    
    print(f"\n🎯 SCHEMA FIX SUMMARY: {success_count}/{len([db for db in databases if os.path.exists(db)])} databases fixed")
    
    if success_count > 0:
        print("\n🚀 READY FOR DEPLOYMENT!")
        print("   - All Video model fields now exist in database")
        print("   - All 500 schema errors should be resolved")
        print("   - HIL workflow should work properly")
        print("   - Annotation creation should succeed")
    else:
        print("\n❌ MANUAL INTERVENTION REQUIRED")