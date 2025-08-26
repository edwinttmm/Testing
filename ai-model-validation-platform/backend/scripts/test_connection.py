#!/usr/bin/env python3
"""
Test PostgreSQL connection for enum fix
This script tests the connection without making any changes.
"""

import os
import sys

def test_connection():
    """Test connection to PostgreSQL database."""
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed. Install with: pip install psycopg2-binary")
        return False
    
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
    
    print("PostgreSQL Connection Test")
    print("=" * 30)
    
    if database_url:
        print(f"Using DATABASE_URL: {database_url.split('@')[0]}@***")
    else:
        print(f"Using connection details:")
        print(f"  Host: {db_config['host']}")
        print(f"  Port: {db_config['port']}")
        print(f"  Database: {db_config['database']}")
        print(f"  User: {db_config['user']}")
    
    try:
        if database_url:
            conn = psycopg2.connect(database_url)
        else:
            conn = psycopg2.connect(**db_config)
        
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"\n✅ Connection successful!")
        print(f"PostgreSQL version: {version}")
        
        # Check if projects table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'projects'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if table_exists:
            print("✅ Projects table exists")
            
            # Check for invalid values
            cursor.execute("SELECT COUNT(*) FROM projects WHERE camera_view = 'Mixed'")
            camera_mixed = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM projects WHERE signal_type = 'Mixed'")
            signal_mixed = cursor.fetchone()[0]
            
            print(f"📊 Invalid enum values found:")
            print(f"   camera_view='Mixed': {camera_mixed}")
            print(f"   signal_type='Mixed': {signal_mixed}")
            
            if camera_mixed > 0 or signal_mixed > 0:
                print("🔧 Ready to run enum fix!")
            else:
                print("✅ No enum fixes needed!")
        else:
            print("❌ Projects table not found")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)