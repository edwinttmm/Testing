#!/usr/bin/env python3
"""
Database Verification Test Script
Tests the database storage functionality for the Enhanced Test Workflow system
"""

import sqlite3
import sys
import os

# Add the backend directory to the path
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

def verify_database_storage():
    """Verify that test data is properly stored in the database"""
    
    db_path = "/home/rigade/Testing/ai-model-validation-platform/backend/test_database.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    print(f"✅ Database file found: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📊 Database tables ({len(tables)} found):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check test sessions
        cursor.execute("SELECT COUNT(*) FROM test_sessions;")
        test_session_count = cursor.fetchone()[0]
        print(f"🧪 Test sessions in database: {test_session_count}")
        
        # Get latest test sessions
        cursor.execute("""
            SELECT id, name, status, project_id, started_at, completed_at 
            FROM test_sessions 
            ORDER BY created_at DESC 
            LIMIT 5;
        """)
        sessions = cursor.fetchall()
        
        print("\n📋 Latest test sessions:")
        for session in sessions:
            status = "🔴" if session[2] == "running" else "✅" if session[2] == "completed" else "⏸️"
            print(f"  {status} {session[1]} ({session[0][:8]}...)")
            print(f"     Project: {session[3]}")
            print(f"     Started: {session[4]}")
            print(f"     Completed: {session[5] or 'Still running'}")
            print()
        
        # Check detection events
        cursor.execute("SELECT COUNT(*) FROM detection_events;")
        detection_count = cursor.fetchone()[0]
        print(f"🎯 Detection events in database: {detection_count}")
        
        # Check test results
        cursor.execute("SELECT COUNT(*) FROM test_results;")
        result_count = cursor.fetchone()[0]
        print(f"📈 Test results in database: {result_count}")
        
        # Check detection comparisons
        cursor.execute("SELECT COUNT(*) FROM detection_comparisons;")
        comparison_count = cursor.fetchone()[0]
        print(f"⚖️ Detection comparisons in database: {comparison_count}")
        
        conn.close()
        
        print("\n✅ Database verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

if __name__ == "__main__":
    success = verify_database_storage()
    sys.exit(0 if success else 1)