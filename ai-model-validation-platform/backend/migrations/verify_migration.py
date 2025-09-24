#!/usr/bin/env python3
"""
Simple Migration Verification Script
====================================

Quick verification that the HIL ground truth timing migration was applied successfully.

Usage:
    python3 migrations/verify_migration.py
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_database_url():
    """Get database URL"""
    return (
        os.getenv("VRU_DATABASE_URL") or
        os.getenv("DATABASE_URL") or 
        os.getenv("AIVALIDATION_DATABASE_URL") or
        "sqlite:///./dev_database.db"
    )

def verify_migration():
    """Verify that the migration was applied successfully"""
    database_url = get_database_url()
    print(f"🔍 Verifying HIL migration on database: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    
    engine = create_engine(database_url)
    inspector = inspect(engine)
    
    results = {
        'test_sessions_fields': [],
        'detection_events_fields': [],
        'detection_comparisons_table': False,
        'indexes': [],
        'status': 'success'
    }
    
    try:
        # Check test_sessions table enhancements
        if 'test_sessions' in inspector.get_table_names():
            ts_columns = {col['name'] for col in inspector.get_columns('test_sessions')}
            
            required_ts_fields = [
                'video_playback_start_time',
                'video_playback_duration', 
                'ground_truth_count'
            ]
            
            for field in required_ts_fields:
                if field in ts_columns:
                    results['test_sessions_fields'].append(f"✅ {field}")
                else:
                    results['test_sessions_fields'].append(f"❌ {field}")
                    results['status'] = 'incomplete'
        else:
            print("❌ test_sessions table not found")
            results['status'] = 'failed'
            return results
        
        # Check detection_events table enhancements
        if 'detection_events' in inspector.get_table_names():
            de_columns = {col['name'] for col in inspector.get_columns('detection_events')}
            
            required_de_fields = [
                'video_relative_timestamp',
                'actual_latency_ms'
            ]
            
            for field in required_de_fields:
                if field in de_columns:
                    results['detection_events_fields'].append(f"✅ {field}")
                else:
                    results['detection_events_fields'].append(f"❌ {field}")
                    results['status'] = 'incomplete'
        else:
            print("❌ detection_events table not found")
            results['status'] = 'failed'
            return results
        
        # Check detection_comparisons table
        if 'detection_comparisons' in inspector.get_table_names():
            results['detection_comparisons_table'] = True
            dc_columns = {col['name'] for col in inspector.get_columns('detection_comparisons')}
            
            required_dc_fields = [
                'is_matched',
                'matching_confidence',
                'match_quality',
                'latency_ms'
            ]
            
            for field in required_dc_fields:
                if field in dc_columns:
                    results['detection_events_fields'].append(f"✅ detection_comparisons.{field}")
                else:
                    results['detection_events_fields'].append(f"❌ detection_comparisons.{field}")
                    results['status'] = 'incomplete'
        else:
            results['status'] = 'incomplete'
        
        # Check for key indexes
        timing_indexes = [
            'idx_detection_events_video_relative_time',
            'idx_detection_events_session_time',
            'idx_ground_truth_video_time'
        ]
        
        for table_name in ['detection_events', 'ground_truth_objects', 'detection_comparisons']:
            if table_name in inspector.get_table_names():
                table_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
                for index_name in timing_indexes:
                    if index_name in table_indexes:
                        results['indexes'].append(f"✅ {index_name}")
                    else:
                        # Only warn about missing indexes, don't fail
                        results['indexes'].append(f"⚠️  {index_name}")
        
        # Test a sample query to ensure fields work
        with engine.connect() as conn:
            # Test that we can query the new fields without errors
            test_query = text("""
                SELECT 
                    ts.id,
                    ts.video_playback_start_time,
                    ts.video_playback_duration,
                    ts.ground_truth_count,
                    COUNT(de.id) as detection_count
                FROM test_sessions ts
                LEFT JOIN detection_events de ON ts.id = de.test_session_id
                GROUP BY ts.id
                LIMIT 5
            """)
            
            result = conn.execute(test_query)
            rows = result.fetchall()
            
            print(f"📊 Sample data query returned {len(rows)} rows")
            for row in rows[:3]:  # Show first 3 rows
                print(f"   Session: {row[0][:8]}... | Start: {row[1]} | Duration: {row[2]} | GT Count: {row[3]} | Detections: {row[4]}")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        results['status'] = 'failed'
        results['error'] = str(e)
    
    return results

def main():
    """Main verification function"""
    print("🚀 Starting HIL Ground Truth Timing Migration Verification")
    print("=" * 60)
    
    results = verify_migration()
    
    print("\n📋 Verification Results:")
    print("-" * 30)
    
    print("\n🏗️  Test Sessions Fields:")
    for field in results['test_sessions_fields']:
        print(f"   {field}")
    
    print("\n🎯 Detection Events Fields:")
    for field in results['detection_events_fields']:
        print(f"   {field}")
    
    print(f"\n📊 Detection Comparisons Table: {'✅ Present' if results['detection_comparisons_table'] else '❌ Missing'}")
    
    print("\n📈 Performance Indexes:")
    for index in results['indexes']:
        print(f"   {index}")
    
    print("\n" + "=" * 60)
    
    if results['status'] == 'success':
        print("✅ MIGRATION VERIFICATION SUCCESSFUL!")
        print("   All HIL ground truth timing fields are properly configured.")
        print("   The system is ready for video timing synchronization and ground truth matching.")
    elif results['status'] == 'incomplete':
        print("⚠️  MIGRATION PARTIALLY APPLIED")
        print("   Some fields or tables may be missing. Check the details above.")
        print("   Consider re-running the migration script.")
    else:
        print("❌ MIGRATION VERIFICATION FAILED")
        print("   Critical issues detected. Please check the error details.")
        if 'error' in results:
            print(f"   Error: {results['error']}")
    
    return 0 if results['status'] == 'success' else 1

if __name__ == "__main__":
    sys.exit(main())