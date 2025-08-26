#!/usr/bin/env python3
"""
Docker-optimized PostgreSQL Enum Value Fix Script
Designed to run inside the backend Docker container with proper error handling.
"""

import os
import sys
import subprocess
import traceback
from datetime import datetime

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    print("psycopg2 not available. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2
    from psycopg2 import sql


def get_db_connection_docker():
    """Create connection to PostgreSQL database from Docker container."""
    # Docker container environment
    db_config = {
        'host': 'postgres',  # Docker service name
        'port': '5432',
        'database': os.getenv('POSTGRES_DB', 'vru_validation'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'secure_password_change_me')
    }
    
    # Try to extract from DATABASE_URL if available
    database_url = os.getenv('DATABASE_URL') or os.getenv('AIVALIDATION_DATABASE_URL')
    if database_url:
        print(f"Using DATABASE_URL: {database_url.split('@')[0]}@***")
        return psycopg2.connect(database_url)
    
    print(f"Connecting to PostgreSQL at {db_config['host']}:{db_config['port']}")
    print(f"Database: {db_config['database']}, User: {db_config['user']}")
    
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False  # Use manual transaction control
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None


def check_table_exists(cursor):
    """Check if the projects table exists."""
    try:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'projects'
            );
        """)
        return cursor.fetchone()[0]
    except Exception as e:
        print(f"Error checking table existence: {e}")
        return False


def check_invalid_values(cursor):
    """Check for invalid enum values before fixing."""
    print("\n=== CHECKING FOR INVALID ENUM VALUES ===")
    
    try:
        # Check for invalid camera_view values
        cursor.execute("""
            SELECT id, name, camera_view, created_at 
            FROM projects 
            WHERE camera_view = %s
            ORDER BY created_at DESC
            LIMIT 10;
        """, ('Mixed',))
        camera_view_issues = cursor.fetchall()
        
        # Check for invalid signal_type values
        cursor.execute("""
            SELECT id, name, signal_type, created_at 
            FROM projects 
            WHERE signal_type = %s
            ORDER BY created_at DESC
            LIMIT 10;
        """, ('Mixed',))
        signal_type_issues = cursor.fetchall()
        
        # Get total counts
        cursor.execute("SELECT COUNT(*) FROM projects WHERE camera_view = %s", ('Mixed',))
        camera_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM projects WHERE signal_type = %s", ('Mixed',))
        signal_count = cursor.fetchone()[0]
        
        print(f"Found {camera_count} projects with invalid camera_view='Mixed'")
        print(f"Found {signal_count} projects with invalid signal_type='Mixed'")
        
        if camera_view_issues:
            print("\nSample projects with invalid camera_view:")
            for row in camera_view_issues:
                print(f"  - ID: {row[0][:8]}..., Name: {row[1][:30]}, Created: {row[3]}")
        
        if signal_type_issues:
            print("\nSample projects with invalid signal_type:")
            for row in signal_type_issues:
                print(f"  - ID: {row[0][:8]}..., Name: {row[1][:30]}, Created: {row[3]}")
        
        return camera_count, signal_count
        
    except Exception as e:
        print(f"Error checking invalid values: {e}")
        return 0, 0


def fix_enum_values(cursor):
    """Fix the invalid enum values."""
    print("\n=== FIXING ENUM VALUES ===")
    
    try:
        # Fix camera_view values
        print("Fixing camera_view values...")
        cursor.execute("""
            UPDATE projects 
            SET camera_view = %s, updated_at = NOW()
            WHERE camera_view = %s;
        """, ('Multi-angle', 'Mixed'))
        camera_view_fixed = cursor.rowcount
        print(f"Updated {camera_view_fixed} camera_view records from 'Mixed' to 'Multi-angle'")
        
        # Fix signal_type values
        print("Fixing signal_type values...")
        cursor.execute("""
            UPDATE projects
            SET signal_type = %s, updated_at = NOW()
            WHERE signal_type = %s;
        """, ('Network Packet', 'Mixed'))
        signal_type_fixed = cursor.rowcount
        print(f"Updated {signal_type_fixed} signal_type records from 'Mixed' to 'Network Packet'")
        
        return camera_view_fixed, signal_type_fixed
        
    except Exception as e:
        print(f"Error fixing enum values: {e}")
        return 0, 0


def verify_fixes(cursor):
    """Verify the fixes were applied correctly."""
    print("\n=== VERIFYING FIXES ===")
    
    try:
        # Check for any remaining invalid values
        cursor.execute("SELECT COUNT(*) FROM projects WHERE camera_view = %s", ('Mixed',))
        remaining_camera_issues = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM projects WHERE signal_type = %s", ('Mixed',))
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
        
    except Exception as e:
        print(f"Error verifying fixes: {e}")
        return False


def main():
    """Main function to fix PostgreSQL enum values."""
    print("PostgreSQL Enum Value Fix Script (Docker Version)")
    print("=" * 55)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Running from: {os.getcwd()}")
    print(f"Python version: {sys.version}")
    
    # Connect to database
    print("\nConnecting to database...")
    conn = get_db_connection_docker()
    if not conn:
        print("Failed to connect to database. Exiting.")
        sys.exit(1)
    
    try:
        cursor = conn.cursor()
        
        # Check if table exists
        if not check_table_exists(cursor):
            print("Error: 'projects' table not found in database!")
            sys.exit(1)
        
        print("Successfully connected to database and found projects table.")
        
        # Check current state
        camera_issues, signal_issues = check_invalid_values(cursor)
        
        if camera_issues == 0 and signal_issues == 0:
            print("\n✅ No invalid enum values found. Nothing to fix!")
            return
        
        # Apply fixes automatically (no user input in Docker)
        total_issues = camera_issues + signal_issues
        print(f"\n🔧 Found {total_issues} invalid enum values. Applying fixes...")
        
        # Apply fixes
        camera_fixed, signal_fixed = fix_enum_values(cursor)
        
        # Commit changes
        conn.commit()
        print(f"\n✅ Committed changes to database.")
        
        # Verify fixes
        success = verify_fixes(cursor)
        
        if success:
            print("\n🎉 ALL ENUM VALUES SUCCESSFULLY FIXED!")
            print(f"Total records updated: {camera_fixed + signal_fixed}")
            print("  - camera_view fixes:", camera_fixed)
            print("  - signal_type fixes:", signal_fixed)
        else:
            print("\n❌ Some issues remain. Please check manually.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n💥 Error during execution: {e}")
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