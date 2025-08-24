#!/usr/bin/env python3
"""
Emergency Database Fix - Complete PostgreSQL Reset
This script will completely reset the PostgreSQL database state.
"""

import sys
from pathlib import Path
from sqlalchemy import create_engine, text
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from config import settings

def reset_postgresql_database():
    """Completely reset PostgreSQL database"""
    print("🚨 EMERGENCY DATABASE RESET - PostgreSQL")
    
    # Database connection details
    db_parts = settings.database_url.replace('postgresql://', '').split('@')[1].split('/')
    host_port = db_parts[0]
    db_name = db_parts[1]
    
    # Get connection details from URL
    user_pass = settings.database_url.replace('postgresql://', '').split('@')[0]
    user = user_pass.split(':')[0]
    password = user_pass.split(':')[1]
    host = host_port.split(':')[0] if ':' in host_port else host_port
    port = host_port.split(':')[1] if ':' in host_port else '5432'
    
    print(f"Database: {db_name} on {host}:{port}")
    
    try:
        # Connect to postgres database (not our app database)
        conn_string = f"host={host} port={port} user={user} password={password} dbname=postgres"
        conn = psycopg2.connect(conn_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        print("✅ Connected to PostgreSQL server")
        
        # Terminate all connections to our database
        cur.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{db_name}'
              AND pid <> pg_backend_pid()
        """)
        
        print(f"🔌 Terminated all connections to {db_name}")
        
        # Drop and recreate the database
        cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
        print(f"🗑️ Dropped database {db_name}")
        
        cur.execute(f"CREATE DATABASE {db_name}")
        print(f"🆕 Created fresh database {db_name}")
        
        cur.close()
        conn.close()
        
        print("✅ Database reset completed successfully!")
        print("Now restart your backend container to initialize the fresh database.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        return False

def main():
    """Main function"""
    print("=" * 60)
    print("🚨 EMERGENCY DATABASE RESET TOOL")
    print("=" * 60)
    
    print("\n⚠️  WARNING: This will completely destroy and recreate your database!")
    print("All data will be permanently lost!")
    
    response = input("\nType 'YES' to proceed with database reset: ")
    if response != 'YES':
        print("❌ Operation cancelled")
        return 1
    
    if reset_postgresql_database():
        print("\n🎉 SUCCESS: Database has been completely reset")
        print("\nNext steps:")
        print("1. Restart your backend container:")
        print("   docker-compose restart backend")
        print("2. Check logs to verify clean database initialization")
        return 0
    else:
        print("\n❌ FAILED: Database reset failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())