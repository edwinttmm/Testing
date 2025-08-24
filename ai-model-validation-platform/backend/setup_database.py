#!/usr/bin/env python3
"""
Database Setup and Testing Script

Quick script to setup, test, and verify the database for the 
AI Model Validation Platform.

Usage:
    python setup_database.py                    # Interactive setup
    python setup_database.py --quick-setup     # Automated setup
    python setup_database.py --test-only       # Test existing database
    python setup_database.py --full-reset      # Complete reset (dangerous!)
"""

import sys
import os
import argparse
from pathlib import Path
import logging

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from database_init import DatabaseManager
from database import get_database_health
from config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_banner():
    """Print application banner"""
    print("\n" + "="*80)
    print(" " * 15 + "AI MODEL VALIDATION PLATFORM")
    print(" " * 18 + "Database Setup & Testing")
    print("="*80)

def print_database_info():
    """Print current database configuration"""
    print(f"\n📄 Database Configuration:")
    print(f"   Database URL: {settings.database_url}")
    print(f"   Environment: {'Development' if settings.api_debug else 'Production'}")
    print(f"   Auto-init: {os.getenv('AUTO_INIT_DATABASE', 'false')}")

def test_database() -> bool:
    """Test database connectivity and basic functionality"""
    print("\n🔍 Testing Database Connection...")
    
    try:
        # Test basic connectivity
        health = get_database_health()
        
        if health['status'] == 'healthy':
            print("✅ Database connection successful")
            print(f"   Status: {health['status']}")
            if 'pool_size' in health:
                print(f"   Pool size: {health['pool_size']}")
                print(f"   Active connections: {health['checked_out_connections']}")
        else:
            print("❌ Database connection issues detected")
            print(f"   Error: {health.get('error', 'Unknown error')}")
            return False
        
        # Test database manager
        db_manager = DatabaseManager()
        if db_manager.test_connection():
            print("✅ Database manager connection test passed")
        else:
            print("❌ Database manager connection test failed")
            return False
        
        # Check existing tables
        existing_tables = db_manager.get_existing_tables()
        print(f"✅ Found {len(existing_tables)} existing tables")
        
        if existing_tables:
            core_tables = ['projects', 'videos', 'detection_events', 'test_sessions']
            missing_core = [table for table in core_tables if table not in existing_tables]
            
            if missing_core:
                print(f"⚠️  Missing core tables: {missing_core}")
            else:
                print("✅ All core tables present")
        
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def setup_database(force: bool = False) -> bool:
    """Setup database with full initialization"""
    print("\n🚀 Setting up database...")
    
    try:
        db_manager = DatabaseManager()
        
        # Run full initialization
        success = db_manager.run_full_initialization(force=force)
        
        if success:
            print("✅ Database setup completed successfully!")
            
            # Verify setup
            schema_report = db_manager.verify_schema()
            print(f"\n📊 Setup Summary:")
            print(f"   Status: {schema_report['status']}")
            print(f"   Tables: {schema_report['present_tables']}/{schema_report['total_expected_tables']}")
            print(f"   Database Type: {schema_report['database_type']}")
            
            if schema_report.get('missing_tables'):
                print(f"   Missing Tables: {', '.join(schema_report['missing_tables'])}")
            
        else:
            print("❌ Database setup completed with issues")
        
        return success
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False

def migrate_database() -> bool:
    """Run database migration"""
    print("\n🔄 Running database migration...")
    
    try:
        db_manager = DatabaseManager()
        success = db_manager.run_migration()
        
        if success:
            print("✅ Database migration completed successfully!")
        else:
            print("❌ Database migration completed with issues")
        
        return success
        
    except Exception as e:
        print(f"❌ Database migration failed: {e}")
        return False

def interactive_setup():
    """Interactive setup process"""
    print_banner()
    print_database_info()
    
    # Test current state
    database_works = test_database()
    
    if database_works:
        print("\n🎉 Database is already working!")
        
        choice = input("\nDo you want to run migration/updates anyway? (y/N): ").lower()
        if choice in ['y', 'yes']:
            migrate_database()
        
        choice = input("\nDo you want to see database schema details? (y/N): ").lower()
        if choice in ['y', 'yes']:
            db_manager = DatabaseManager()
            schema_report = db_manager.verify_schema()
            print(f"\n📄 Database Schema Report:")
            print(f"   Status: {schema_report['status']}")
            print(f"   Tables: {schema_report['present_tables']}/{schema_report['total_expected_tables']}")
            print(f"   Database Type: {schema_report['database_type']}")
    
    else:
        print("\n⚠️  Database needs setup or repair")
        
        choice = input("\nDo you want to initialize the database? (Y/n): ").lower()
        if choice not in ['n', 'no']:
            force = False
            if input("Force recreate existing tables? (y/N): ").lower() in ['y', 'yes']:
                force = True
            
            setup_success = setup_database(force=force)
            
            if setup_success:
                print("\n🎉 Database setup completed successfully!")
                print("You can now start the FastAPI application.")
            else:
                print("\n❌ Database setup failed. Please check the logs above.")
                return False
    
    print("\n✅ Database setup process completed.")
    return True

def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="AI Model Validation Platform - Database Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--quick-setup', action='store_true',
                       help='Quick automated setup without prompts')
    parser.add_argument('--test-only', action='store_true',
                       help='Only test database connectivity')
    parser.add_argument('--migrate', action='store_true',
                       help='Run database migration')
    parser.add_argument('--full-reset', action='store_true',
                       help='Complete database reset (DANGEROUS!)')
    parser.add_argument('--force', action='store_true',
                       help='Force operations without prompts')
    
    args = parser.parse_args()
    
    try:
        if args.test_only:
            print_banner()
            print_database_info()
            success = test_database()
            print(f"\n{'✅ Database test PASSED' if success else '❌ Database test FAILED'}")
            sys.exit(0 if success else 1)
        
        elif args.migrate:
            print_banner()
            success = migrate_database()
            sys.exit(0 if success else 1)
        
        elif args.full_reset:
            print_banner()
            if not args.force:
                confirm = input("⚠️  This will completely reset the database. Are you sure? (yes/NO): ")
                if confirm.lower() != 'yes':
                    print("Reset cancelled.")
                    sys.exit(0)
            
            success = setup_database(force=True)
            sys.exit(0 if success else 1)
        
        elif args.quick_setup:
            print_banner()
            print_database_info()
            
            # Test first
            if test_database():
                print("✅ Database already working, running migration...")
                success = migrate_database()
            else:
                print("⚠️  Setting up database...")
                success = setup_database()
            
            sys.exit(0 if success else 1)
        
        else:
            # Interactive mode
            success = interactive_setup()
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        print("\n⏹️  Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()