#!/usr/bin/env python3
"""
CRITICAL SCHEMA MISMATCH FIX
=============================

Fixes the critical database schema mismatch where Video model expects 23 fields
but database only has 13 fields. This causes cascading 500 errors across HIL workflow.

MISSING FIELDS (10):
- validation_status, validation_type, validated_at, validated_by
- ground_truth_count, ground_truth_quality_score, ground_truth_completed_at  
- hil_testing_ready, hil_testing_approved_by, hil_testing_approved_at

IMPACT: 41 files affected across API endpoints, services, and tests.
"""

import sqlite3
import sys
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_database_schema(db_path: str) -> dict:
    """Check current database schema and identify missing fields"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get current schema
        cursor.execute("PRAGMA table_info(videos)")
        current_columns = {row[1] for row in cursor.fetchall()}
        
        # Expected fields from model
        expected_fields = {
            'id', 'filename', 'file_path', 'file_size', 'duration', 'fps', 'resolution',
            'status', 'validation_status', 'validation_type', 'validated_at', 'validated_by',
            'ground_truth_generated', 'ground_truth_count', 'ground_truth_quality_score',
            'ground_truth_completed_at', 'hil_testing_ready', 'hil_testing_approved_by',
            'hil_testing_approved_at', 'processing_status', 'project_id', 'created_at', 'updated_at'
        }
        
        missing_fields = expected_fields - current_columns
        extra_fields = current_columns - expected_fields
        
        conn.close()
        
        return {
            'current_fields': current_columns,
            'expected_fields': expected_fields,
            'missing_fields': missing_fields,
            'extra_fields': extra_fields,
            'total_current': len(current_columns),
            'total_expected': len(expected_fields),
            'total_missing': len(missing_fields)
        }
    except Exception as e:
        logger.error(f"Failed to check database schema: {e}")
        return None

def add_missing_fields(db_path: str, missing_fields: set) -> bool:
    """Add missing fields to videos table"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Define field specifications
        field_specs = {
            'validation_status': "VARCHAR(50) DEFAULT 'pending'",
            'validation_type': "VARCHAR(20)",
            'validated_at': "TIMESTAMP",
            'validated_by': "VARCHAR(36)",
            'ground_truth_count': "INTEGER DEFAULT 0",
            'ground_truth_quality_score': "FLOAT",
            'ground_truth_completed_at': "TIMESTAMP",
            'hil_testing_ready': "BOOLEAN DEFAULT 0",
            'hil_testing_approved_by': "VARCHAR(36)",
            'hil_testing_approved_at': "TIMESTAMP"
        }
        
        logger.info(f"Adding {len(missing_fields)} missing fields to videos table...")
        
        for field in missing_fields:
            if field in field_specs:
                sql = f"ALTER TABLE videos ADD COLUMN {field} {field_specs[field]}"
                logger.info(f"Adding field: {field}")
                cursor.execute(sql)
        
        # Create critical indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_video_validation_status ON videos(validation_status)",
            "CREATE INDEX IF NOT EXISTS idx_video_status_validation ON videos(status, validation_status)",
            "CREATE INDEX IF NOT EXISTS idx_video_hil_ready ON videos(hil_testing_ready, status)",
            "CREATE INDEX IF NOT EXISTS idx_video_validation_completed ON videos(validated_at, validation_type)",
            "CREATE INDEX IF NOT EXISTS idx_video_ground_truth_quality ON videos(ground_truth_quality_score, ground_truth_count)",
            "CREATE INDEX IF NOT EXISTS idx_video_testing_workflow ON videos(status, hil_testing_ready, validated_at)"
        ]
        
        logger.info("Creating critical indexes...")
        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
                logger.info(f"✅ Index created: {index_sql.split('ON')[0].split('EXISTS')[1].strip()}")
            except sqlite3.Error as e:
                logger.warning(f"⚠️ Index creation failed (may already exist): {e}")
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Successfully added missing fields and indexes")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add missing fields: {e}")
        return False

def migrate_existing_data(db_path: str) -> bool:
    """Migrate existing video data to new schema"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("Migrating existing video data to new schema...")
        
        # Update existing videos with default validation status based on current state
        migration_sql = """
        UPDATE videos 
        SET validation_status = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN 'validated'
                WHEN status = 'processing' THEN 'processing' 
                WHEN ground_truth_generated = 1 THEN 'annotated'
                ELSE 'pending'
            END,
            validation_type = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN 'automatic'
                ELSE NULL
            END,
            validated_at = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN updated_at
                ELSE NULL
            END,
            validated_by = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN 'system'
                ELSE NULL
            END,
            ground_truth_count = CASE 
                WHEN ground_truth_generated = 1 THEN 1
                ELSE 0
            END,
            hil_testing_ready = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN 1
                ELSE 0
            END,
            hil_testing_approved_at = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN updated_at
                ELSE NULL
            END,
            hil_testing_approved_by = CASE 
                WHEN status = 'completed' AND ground_truth_generated = 1 THEN 'system'
                ELSE NULL
            END
        WHERE validation_status IS NULL OR validation_status = ''
        """
        
        cursor.execute(migration_sql)
        affected_rows = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Successfully migrated {affected_rows} video records")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate existing data: {e}")
        return False

def verify_fix(db_path: str) -> bool:
    """Verify that the schema fix was successful"""
    logger.info("Verifying schema fix...")
    
    schema_info = check_database_schema(db_path)
    if not schema_info:
        return False
    
    if schema_info['total_missing'] == 0:
        logger.info("✅ All expected fields are now present in database")
        logger.info(f"📊 Total fields: {schema_info['total_current']}/{schema_info['total_expected']}")
        return True
    else:
        logger.error(f"❌ Still missing {schema_info['total_missing']} fields: {schema_info['missing_fields']}")
        return False

def test_critical_queries(db_path: str) -> bool:
    """Test critical queries that were failing"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        logger.info("Testing critical queries...")
        
        # Test queries that were failing
        test_queries = [
            ("Validation Status Query", "SELECT id, validation_status FROM videos LIMIT 1"),
            ("HIL Ready Query", "SELECT id, hil_testing_ready FROM videos LIMIT 1"),
            ("Ground Truth Count Query", "SELECT id, ground_truth_count FROM videos LIMIT 1"),
            ("Validated At Query", "SELECT id, validated_at FROM videos LIMIT 1"),
            ("Full Video Query", "SELECT id, filename, validation_status, hil_testing_ready, ground_truth_count FROM videos LIMIT 1")
        ]
        
        for query_name, sql in test_queries:
            try:
                cursor.execute(sql)
                result = cursor.fetchone()
                logger.info(f"✅ {query_name}: SUCCESS")
            except Exception as e:
                logger.error(f"❌ {query_name}: FAILED - {e}")
                return False
        
        conn.close()
        logger.info("✅ All critical queries working correctly")
        return True
        
    except Exception as e:
        logger.error(f"❌ Query testing failed: {e}")
        return False

def main():
    """Main fix execution"""
    logger.info("🚨 STARTING CRITICAL SCHEMA MISMATCH FIX")
    logger.info("=" * 60)
    
    # Find database file
    db_candidates = ['test_database.db', 'test_database.db', 'database.db']
    db_path = None
    
    for candidate in db_candidates:
        if Path(candidate).exists():
            db_path = candidate
            break
    
    if not db_path:
        logger.error("❌ No database file found. Candidates checked: " + ", ".join(db_candidates))
        sys.exit(1)
    
    logger.info(f"📁 Using database: {db_path}")
    
    # 1. Check current schema
    logger.info("\n1️⃣ ANALYZING CURRENT SCHEMA")
    schema_info = check_database_schema(db_path)
    if not schema_info:
        logger.error("❌ Failed to analyze database schema")
        sys.exit(1)
    
    logger.info(f"📊 Current fields: {schema_info['total_current']}")
    logger.info(f"📊 Expected fields: {schema_info['total_expected']}")
    logger.info(f"❌ Missing fields: {schema_info['total_missing']}")
    
    if schema_info['total_missing'] == 0:
        logger.info("✅ Database schema is already correct!")
        return
    
    logger.info(f"🔍 Missing fields: {', '.join(sorted(schema_info['missing_fields']))}")
    
    # 2. Backup database
    logger.info(f"\n2️⃣ BACKING UP DATABASE")
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        logger.info(f"✅ Database backed up to: {backup_path}")
    except Exception as e:
        logger.error(f"❌ Failed to backup database: {e}")
        logger.info("⚠️ Continuing without backup (RISKY)")
    
    # 3. Add missing fields
    logger.info(f"\n3️⃣ ADDING MISSING FIELDS")
    if not add_missing_fields(db_path, schema_info['missing_fields']):
        logger.error("❌ Failed to add missing fields")
        sys.exit(1)
    
    # 4. Migrate existing data
    logger.info(f"\n4️⃣ MIGRATING EXISTING DATA")
    if not migrate_existing_data(db_path):
        logger.error("❌ Failed to migrate existing data")
        sys.exit(1)
    
    # 5. Verify fix
    logger.info(f"\n5️⃣ VERIFYING FIX")
    if not verify_fix(db_path):
        logger.error("❌ Schema fix verification failed")
        sys.exit(1)
    
    # 6. Test critical queries
    logger.info(f"\n6️⃣ TESTING CRITICAL QUERIES")
    if not test_critical_queries(db_path):
        logger.error("❌ Critical query testing failed")
        sys.exit(1)
    
    # Success!
    logger.info("\n" + "=" * 60)
    logger.info("🎉 CRITICAL SCHEMA MISMATCH FIX COMPLETED SUCCESSFULLY!")
    logger.info("=" * 60)
    logger.info("✅ Database schema updated")
    logger.info("✅ Missing fields added")
    logger.info("✅ Existing data migrated") 
    logger.info("✅ Critical indexes created")
    logger.info("✅ All queries tested")
    logger.info("\n🚀 API services can now be safely restarted!")
    logger.info(f"💾 Backup available at: {backup_path}")

if __name__ == "__main__":
    main()