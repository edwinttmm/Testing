#!/usr/bin/env python3
"""
PostgreSQL Enum Value Fix Script
Connects to the PostgreSQL database running in Docker and fixes invalid enum values.
"""

import os
import sys
import psycopg2
import traceback
from datetime import datetime


def get_db_connection():
    """Create connection to PostgreSQL database."""
    # Get connection details from environment or use defaults
    db_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'vru_validation'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_change_me')
    }
    
    print(f"Connecting to PostgreSQL at {db_config['host']}:{db_config['port']}")
    print(f"Database: {db_config['database']}, User: {db_config['user']}")
    
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def check_invalid_values(cursor):
    """Check for invalid enum values before fixing."""
    print("\n=== CHECKING FOR INVALID ENUM VALUES ===")
    
    # Check for invalid camera_view values
    cursor.execute("""
        SELECT id, name, camera_view, created_at 
        FROM projects 
        WHERE camera_view = 'Mixed'
        ORDER BY created_at DESC;
    """)
    camera_view_issues = cursor.fetchall()
    
    # Check for invalid signal_type values
    cursor.execute("""
        SELECT id, name, signal_type, created_at 
        FROM projects 
        WHERE signal_type = 'Mixed'
        ORDER BY created_at DESC;
    """)
    signal_type_issues = cursor.fetchall()
    
    print(f"Found {len(camera_view_issues)} projects with invalid camera_view='Mixed'")
    print(f"Found {len(signal_type_issues)} projects with invalid signal_type='Mixed'")
    
    if camera_view_issues:
        print("\nProjects with invalid camera_view:")
        for row in camera_view_issues:
            print(f"  - ID: {row[0]}, Name: {row[1]}, Created: {row[3]}")
    
    if signal_type_issues:
        print("\nProjects with invalid signal_type:")
        for row in signal_type_issues:
            print(f"  - ID: {row[0]}, Name: {row[1]}, Created: {row[3]}")
    
    return len(camera_view_issues), len(signal_type_issues)


def fix_enum_values(cursor):
    """Fix the invalid enum values."""
    print("\n=== FIXING ENUM VALUES ===")
    
    # Fix camera_view values
    print("Fixing camera_view values...")
    cursor.execute("""
        UPDATE projects 
        SET camera_view = 'Multi-angle'
        WHERE camera_view = 'Mixed';
    """)
    camera_view_fixed = cursor.rowcount
    print(f"Updated {camera_view_fixed} camera_view records from 'Mixed' to 'Multi-angle'")
    
    # Fix signal_type values
    print("Fixing signal_type values...")
    cursor.execute("""
        UPDATE projects
        SET signal_type = 'Network Packet'
        WHERE signal_type = 'Mixed';
    """)
    signal_type_fixed = cursor.rowcount
    print(f"Updated {signal_type_fixed} signal_type records from 'Mixed' to 'Network Packet'")
    
    return camera_view_fixed, signal_type_fixed


def verify_fixes(cursor):
    """Verify the fixes were applied correctly."""
    print("\n=== VERIFYING FIXES ===")
    
    # Check for any remaining invalid values
    cursor.execute("""
        SELECT COUNT(*) FROM projects WHERE camera_view = 'Mixed';
    """)
    remaining_camera_issues = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM projects WHERE signal_type = 'Mixed';
    """)
    remaining_signal_issues = cursor.fetchone()[0]
    
    print(f"Remaining invalid camera_view values: {remaining_camera_issues}")
    print(f"Remaining invalid signal_type values: {remaining_signal_issues}")
    
    # Show current distribution of enum values
    cursor.execute("""
        SELECT camera_view, COUNT(*) as count
        FROM projects 
        GROUP BY camera_view
        ORDER BY count DESC;
    """)
    camera_view_dist = cursor.fetchall()
    
    cursor.execute("""
        SELECT signal_type, COUNT(*) as count
        FROM projects 
        GROUP BY signal_type
        ORDER BY count DESC;
    """)
    signal_type_dist = cursor.fetchall()
    
    print("\nCurrent camera_view distribution:")
    for view, count in camera_view_dist:
        print(f"  - {view}: {count}")
    
    print("\nCurrent signal_type distribution:")
    for signal, count in signal_type_dist:
        print(f"  - {signal}: {count}")
    
    return remaining_camera_issues == 0 and remaining_signal_issues == 0


def main():
    """Main function to fix PostgreSQL enum values."""
    print("PostgreSQL Enum Value Fix Script")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to database
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    try:
        cursor = conn.cursor()
        
        # Check current state
        camera_issues, signal_issues = check_invalid_values(cursor)
        
        if camera_issues == 0 and signal_issues == 0:
            print("\nNo invalid enum values found. Nothing to fix!")
            return
        
        # Confirm before making changes
        total_issues = camera_issues + signal_issues
        response = input(f"\nFound {total_issues} invalid enum values. Fix them? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled.")
            return
        
        # Apply fixes
        camera_fixed, signal_fixed = fix_enum_values(cursor)
        
        # Commit changes
        conn.commit()
        print(f"\nCommitted changes to database.")
        
        # Verify fixes
        success = verify_fixes(cursor)
        
        if success:
            print("\n✅ ALL ENUM VALUES SUCCESSFULLY FIXED!")
            print(f"Total records updated: {camera_fixed + signal_fixed}")
        else:
            print("\n❌ Some issues remain. Please check manually.")
            
    except Exception as e:
        print(f"\nError during execution: {e}")
        print("Rolling back changes...")
        conn.rollback()
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        cursor.close()
        conn.close()
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()