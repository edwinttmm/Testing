#!/usr/bin/env python3
"""
Debug Ground Truth Query
This script tests the exact query used in the enhanced HIL endpoint.
"""

import sqlite3
import sys

def debug_ground_truth_query():
    """Debug the exact ground truth query used in enhanced HIL endpoint"""
    print("🔍 Testing Enhanced HIL Ground Truth Query...")
    
    try:
        # Connect to database
        conn = sqlite3.connect('dev_database.db')
        cursor = conn.cursor()
        
        video_id = "5f7c8aa3-a73e-4be0-85db-a40215a1f3c1"
        
        # Test the exact query from enhanced HIL endpoint
        cursor.execute("""
            SELECT * FROM ground_truth_objects 
            WHERE video_id = ? AND validated = ?
            ORDER BY timestamp
        """, (video_id, True))
        validated_gt = cursor.fetchall()
        
        print(f"📊 Query with validated=True: {len(validated_gt)} objects")
        
        # Test without validated filter
        cursor.execute("""
            SELECT * FROM ground_truth_objects 
            WHERE video_id = ?
            ORDER BY timestamp
        """, (video_id,))
        all_gt = cursor.fetchall()
        
        print(f"📊 Query without validated filter: {len(all_gt)} objects")
        
        # Check the validated field values
        cursor.execute("""
            SELECT validated, COUNT(*) FROM ground_truth_objects 
            WHERE video_id = ?
            GROUP BY validated
        """, (video_id,))
        validated_counts = cursor.fetchall()
        
        print(f"🔍 Validated field breakdown:")
        for validated_val, count in validated_counts:
            print(f"   validated = {validated_val}: {count} objects")
            
        # Show sample ground truth data
        if all_gt:
            print(f"📋 Sample ground truth objects:")
            for i, gt in enumerate(all_gt[:3]):
                print(f"   Object {i+1}: frame_number={gt[4]}, timestamp={gt[5]}, validated={gt[7]}, class_label={gt[6]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"💥 Error: {e}")
        return False

def main():
    print("🚀 Ground Truth Query Debug")
    print("=" * 50)
    
    debug_ground_truth_query()

if __name__ == "__main__":
    main()