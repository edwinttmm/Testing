#!/usr/bin/env python3
"""Check database schema and available data for timing analysis"""

import sqlite3
import os
from typing import List, Dict, Any

def check_database(db_path: str) -> Dict[str, Any]:
    """Check database schema and data availability"""
    if not os.path.exists(db_path):
        return {"error": f"Database {db_path} does not exist"}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        schema_info = {"tables": tables, "table_details": {}}
        
        # For each table, get schema and row count
        for table in tables:
            try:
                # Get schema
                cursor.execute(f"PRAGMA table_info({table})")
                columns = []
                for col_info in cursor.fetchall():
                    columns.append({
                        "name": col_info[1],
                        "type": col_info[2],
                        "nullable": not col_info[3],
                        "default": col_info[4]
                    })
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                
                schema_info["table_details"][table] = {
                    "columns": columns,
                    "row_count": row_count
                }
                
            except Exception as e:
                schema_info["table_details"][table] = {"error": str(e)}
        
        conn.close()
        return schema_info
        
    except Exception as e:
        return {"error": f"Failed to analyze database {db_path}: {e}"}

def check_timing_data_availability(db_path: str) -> Dict[str, Any]:
    """Check for timing-related data specifically"""
    if not os.path.exists(db_path):
        return {"error": f"Database {db_path} does not exist"}
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        timing_info = {}
        
        # Check for test_sessions table
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_sessions'")
            if cursor.fetchone():
                # Check for timing columns
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(video_start_timestamp) as with_video_start,
                        COUNT(video_playback_start_time) as with_playback_start,
                        COUNT(video_timing_sync_status) as with_sync_status,
                        COUNT(timing_accuracy_ns) as with_timing_accuracy
                    FROM test_sessions
                """)
                timing_info["test_sessions"] = dict(cursor.fetchone())
        except Exception as e:
            timing_info["test_sessions"] = {"error": str(e)}
        
        # Check for detection_events table
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='detection_events'")
            if cursor.fetchone():
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_detections,
                        COUNT(labjack_timestamp) as with_labjack_timestamp,
                        COUNT(processing_time_ms) as with_processing_time
                    FROM detection_events
                """)
                timing_info["detection_events"] = dict(cursor.fetchone())
        except Exception as e:
            timing_info["detection_events"] = {"error": str(e)}
        
        # Check for ground_truth_objects table
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ground_truth_objects'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) as total_ground_truth FROM ground_truth_objects")
                timing_info["ground_truth_objects"] = dict(cursor.fetchone())
        except Exception as e:
            timing_info["ground_truth_objects"] = {"error": str(e)}
        
        conn.close()
        return timing_info
        
    except Exception as e:
        return {"error": f"Failed to check timing data in {db_path}: {e}"}

def main():
    """Check all available databases"""
    databases = [
        "validation_platform.db",
        "ai_model_validation.db", 
        "test_database.db",
        "dev_database.db",
        "app.db",
        "test.db"
    ]
    
    print("Database Schema Analysis")
    print("="*50)
    
    for db_path in databases:
        print(f"\nChecking: {db_path}")
        print("-" * 40)
        
        # Check basic schema
        schema_info = check_database(db_path)
        if "error" in schema_info:
            print(f"ERROR: {schema_info['error']}")
            continue
        
        print(f"Tables found: {len(schema_info['tables'])}")
        for table in schema_info['tables']:
            details = schema_info['table_details'][table]
            if "error" in details:
                print(f"  {table}: ERROR - {details['error']}")
            else:
                print(f"  {table}: {details['row_count']} rows, {len(details['columns'])} columns")
        
        # Check timing data availability
        timing_info = check_timing_data_availability(db_path)
        if "error" not in timing_info:
            print(f"\nTiming Data Availability:")
            for table, info in timing_info.items():
                if "error" in info:
                    print(f"  {table}: ERROR - {info['error']}")
                else:
                    print(f"  {table}: {info}")
        
        # Check for video startup delay capability
        if "test_sessions" in timing_info and "error" not in timing_info["test_sessions"]:
            ts_info = timing_info["test_sessions"]
            if ts_info.get("with_playback_start", 0) > 0:
                print(f"\n✅ GOOD: Database has video playback timing data!")
                print(f"   Sessions with playback start time: {ts_info['with_playback_start']}")
                print(f"   Can analyze video startup delay hypothesis: YES")
                
                # This database is suitable for our analysis
                return db_path
        
    print(f"\n❌ No suitable database found for video startup delay analysis")
    return None

if __name__ == "__main__":
    suitable_db = main()
    if suitable_db:
        print(f"\nRecommended database for analysis: {suitable_db}")
    else:
        print(f"\nNeed to create test data or use a different approach")