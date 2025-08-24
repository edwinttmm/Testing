#!/usr/bin/env python3
"""
Comprehensive Database Initialization and Schema Management System

This module provides robust database initialization that handles:
- PostgreSQL and SQLite configuration
- Table creation with proper error handling
- Index creation with conflict resolution
- Schema validation and verification
- Migration capabilities for existing databases
- Environment-specific setup (development vs production)

Usage:
    python database_init.py --init        # Initialize fresh database
    python database_init.py --migrate     # Migrate existing database
    python database_init.py --verify      # Verify schema only
    python database_init.py --health      # Check database health
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from sqlalchemy import (
    create_engine, text, inspect, Index, MetaData, Table, Column
)
from sqlalchemy.exc import (
    SQLAlchemyError, OperationalError, ProgrammingError, 
    IntegrityError, DatabaseError
)
from sqlalchemy.engine import Engine
from datetime import datetime
import uuid

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Import application components
from database import engine, Base, SessionLocal, get_database_health
from config import settings

# Import all models to ensure they're registered
from models import (
    Project, Video, GroundTruthObject, TestSession, DetectionEvent,
    Annotation, AnnotationSession, VideoProjectLink, TestResult,
    DetectionComparison, AuditLog
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseInitializationError(Exception):
    """Custom exception for database initialization errors"""
    pass

class DatabaseManager:
    """
    Comprehensive Database Management System
    
    Handles initialization, migration, and schema management for both
    development and production environments.
    """
    
    def __init__(self, engine: Optional[Engine] = None, dry_run: bool = False):
        self.engine = engine or globals()['engine']
        self.dry_run = dry_run
        self.inspector = None
        self.metadata = Base.metadata
        self.is_postgresql = self._is_postgresql()
        self.is_sqlite = self._is_sqlite()
        
        # Track operations for rollback
        self.operations_log: List[Dict] = []
        self.successful_operations: Set[str] = set()
        self.failed_operations: Set[str] = set()
        
        logger.info(f"DatabaseManager initialized for {'PostgreSQL' if self.is_postgresql else 'SQLite'}")
    
    def _is_postgresql(self) -> bool:
        """Check if using PostgreSQL"""
        return 'postgresql' in str(self.engine.url).lower()
    
    def _is_sqlite(self) -> bool:
        """Check if using SQLite"""
        return 'sqlite' in str(self.engine.url).lower()
    
    def get_inspector(self):
        """Get database inspector with error handling"""
        if not self.inspector:
            try:
                self.inspector = inspect(self.engine)
            except Exception as e:
                logger.error(f"Failed to create database inspector: {e}")
                raise DatabaseInitializationError(f"Inspector creation failed: {e}")
        return self.inspector
    
    def test_connection(self) -> bool:
        """Test database connectivity"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1 as test"))
                test_value = result.scalar()
                if test_value == 1:
                    logger.info("✅ Database connection successful")
                    return True
                else:
                    logger.error("❌ Database connection test failed")
                    return False
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def get_existing_tables(self) -> Set[str]:
        """Get list of existing table names"""
        try:
            inspector = self.get_inspector()
            return set(inspector.get_table_names())
        except Exception as e:
            logger.error(f"Failed to get existing tables: {e}")
            return set()
    
    def get_existing_indexes(self, table_name: str) -> Set[str]:
        """Get existing indexes for a table"""
        try:
            inspector = self.get_inspector()
            indexes = inspector.get_indexes(table_name)
            return {idx['name'] for idx in indexes if idx.get('name')}
        except Exception as e:
            logger.warning(f"Could not get indexes for {table_name}: {e}")
            return set()
    
    def create_database_extensions(self) -> bool:
        """Create required database extensions (PostgreSQL only)"""
        if not self.is_postgresql:
            logger.info("Skipping extensions (SQLite database)")
            return True
        
        try:
            with self.engine.connect() as conn:
                # Enable UUID extension for PostgreSQL
                conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                conn.commit()
                logger.info("✅ PostgreSQL extensions created")
                self.successful_operations.add("extensions")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to create database extensions: {e}")
            self.failed_operations.add("extensions")
            return False
    
    def create_all_tables(self, force: bool = False) -> bool:
        """Create all tables from models"""
        try:
            existing_tables = self.get_existing_tables()
            logger.info(f"Found {len(existing_tables)} existing tables: {list(existing_tables)}")
            
            if not force and existing_tables:
                logger.info("Tables already exist, using checkfirst=True")
            
            # Create all tables
            if self.dry_run:
                logger.info("[DRY RUN] Would create all tables from metadata")
            else:
                logger.info("Creating tables from SQLAlchemy metadata...")
                self.metadata.create_all(bind=self.engine, checkfirst=True)
            
            # Verify table creation
            new_tables = self.get_existing_tables()
            created_tables = new_tables - existing_tables
            
            if created_tables:
                logger.info(f"✅ Created {len(created_tables)} new tables: {list(created_tables)}")
            
            logger.info(f"✅ Total tables in database: {len(new_tables)}")
            self.successful_operations.add("create_tables")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            self.failed_operations.add("create_tables")
            return False
    
    def create_critical_indexes(self) -> bool:
        """Create critical performance indexes"""
        
        # Define critical indexes that must exist
        critical_indexes = {
            'projects': [
                ('idx_projects_name', ['name']),
                ('idx_projects_status', ['status']),
                ('idx_projects_owner_status', ['owner_id', 'status']),
                ('idx_projects_created_at', ['created_at'])
            ],
            'videos': [
                ('idx_videos_project_id', ['project_id']),
                ('idx_videos_status', ['status']),
                ('idx_videos_processing_status', ['processing_status']),
                ('idx_videos_project_status', ['project_id', 'status']),
                ('idx_videos_filename', ['filename'])
            ],
            'test_sessions': [
                ('idx_test_sessions_project_id', ['project_id']),
                ('idx_test_sessions_video_id', ['video_id']),
                ('idx_test_sessions_status', ['status']),
                ('idx_test_sessions_created_at', ['created_at'])
            ],
            'detection_events': [
                ('idx_detection_events_test_session_id', ['test_session_id']),
                ('idx_detection_events_timestamp', ['timestamp']),
                ('idx_detection_events_confidence', ['confidence']),
                ('idx_detection_events_validation_result', ['validation_result']),
                ('idx_detection_events_session_timestamp', ['test_session_id', 'timestamp'])
            ],
            'ground_truth_objects': [
                ('idx_ground_truth_video_id', ['video_id']),
                ('idx_ground_truth_timestamp', ['timestamp']),
                ('idx_ground_truth_class_label', ['class_label']),
                ('idx_ground_truth_validated', ['validated']),
                ('idx_ground_truth_video_timestamp', ['video_id', 'timestamp'])
            ],
            'annotations': [
                ('idx_annotations_video_id', ['video_id']),
                ('idx_annotations_detection_id', ['detection_id']),
                ('idx_annotations_frame_number', ['frame_number']),
                ('idx_annotations_timestamp', ['timestamp']),
                ('idx_annotations_vru_type', ['vru_type']),
                ('idx_annotations_validated', ['validated'])
            ]
        }
        
        success_count = 0
        total_indexes = sum(len(indexes) for indexes in critical_indexes.values())
        
        for table_name, indexes in critical_indexes.items():
            existing_tables = self.get_existing_tables()
            if table_name not in existing_tables:
                logger.warning(f"Table {table_name} does not exist, skipping indexes")
                continue
            
            existing_indexes = self.get_existing_indexes(table_name)
            
            for index_name, columns in indexes:
                if index_name in existing_indexes:
                    logger.info(f"Index {index_name} already exists on {table_name}")
                    success_count += 1
                    continue
                
                try:
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would create index {index_name} on {table_name}({', '.join(columns)})")
                    else:
                        self._create_index_safe(table_name, index_name, columns)
                    success_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to create index {index_name}: {e}")
                    self.failed_operations.add(f"index_{index_name}")
        
        if success_count == total_indexes:
            logger.info(f"✅ All {total_indexes} critical indexes verified/created")
            self.successful_operations.add("create_indexes")
            return True
        else:
            logger.warning(f"⚠️  Created/verified {success_count}/{total_indexes} indexes")
            return False
    
    def _create_index_safe(self, table_name: str, index_name: str, columns: List[str]):
        """Safely create an index with database-specific syntax"""
        columns_str = ', '.join(columns)
        
        try:
            with self.engine.connect() as conn:
                if self.is_postgresql:
                    # PostgreSQL syntax with IF NOT EXISTS (PostgreSQL 9.5+)
                    sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                else:
                    # SQLite syntax
                    sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
                
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"✅ Created index {index_name} on {table_name}")
                
        except Exception as e:
            # Handle the case where index already exists but wasn't detected
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                logger.info(f"Index {index_name} already exists (safe to ignore)")
            else:
                raise
    
    def verify_schema(self) -> Dict[str, any]:
        """Comprehensive schema verification"""
        logger.info("🔍 Performing comprehensive schema verification...")
        
        # Expected tables from models
        expected_tables = {
            'projects': 'Project configurations and metadata',
            'videos': 'Video files and processing status',
            'ground_truth_objects': 'Manual annotations for validation',
            'detection_events': 'ML detection results and analysis',
            'test_sessions': 'Test execution and workflow tracking',
            'annotations': 'Ground truth annotations with detection IDs',
            'annotation_sessions': 'Collaborative annotation sessions',
            'video_project_links': 'Intelligent video-project associations',
            'test_results': 'Statistical test results and metrics',
            'detection_comparisons': 'Ground truth vs detection analysis',
            'audit_logs': 'System audit trail and user actions'
        }
        
        existing_tables = self.get_existing_tables()
        
        # Check table existence
        missing_tables = []
        present_tables = []
        
        for table, description in expected_tables.items():
            if table in existing_tables:
                present_tables.append(table)
                logger.info(f"✅ Table '{table}': {description}")
            else:
                missing_tables.append(table)
                logger.error(f"❌ Table '{table}' MISSING: {description}")
        
        # Verify critical columns for key tables
        column_issues = []
        if 'projects' in existing_tables:
            column_issues.extend(self._verify_table_columns('projects', [
                'id', 'name', 'description', 'camera_model', 'camera_view', 
                'signal_type', 'status', 'created_at'
            ]))
        
        if 'videos' in existing_tables:
            column_issues.extend(self._verify_table_columns('videos', [
                'id', 'filename', 'file_path', 'project_id', 'status',
                'processing_status', 'ground_truth_generated', 'created_at'
            ]))
        
        if 'detection_events' in existing_tables:
            column_issues.extend(self._verify_table_columns('detection_events', [
                'id', 'test_session_id', 'timestamp', 'confidence', 'class_label',
                'validation_result', 'detection_id', 'frame_number'
            ]))
        
        # Generate report
        schema_report = {
            'status': 'healthy' if not missing_tables and not column_issues else 'issues_detected',
            'total_expected_tables': len(expected_tables),
            'present_tables': len(present_tables),
            'missing_tables': missing_tables,
            'column_issues': column_issues,
            'database_type': 'PostgreSQL' if self.is_postgresql else 'SQLite',
            'verification_timestamp': datetime.now().isoformat()
        }
        
        return schema_report
    
    def _verify_table_columns(self, table_name: str, required_columns: List[str]) -> List[str]:
        """Verify that a table has all required columns"""
        issues = []
        try:
            inspector = self.get_inspector()
            columns = inspector.get_columns(table_name)
            existing_columns = {col['name'] for col in columns}
            
            for column in required_columns:
                if column not in existing_columns:
                    issue = f"Column '{column}' missing from table '{table_name}'"
                    issues.append(issue)
                    logger.error(f"❌ {issue}")
                    
        except Exception as e:
            issue = f"Could not verify columns for table '{table_name}': {e}"
            issues.append(issue)
            logger.error(f"❌ {issue}")
            
        return issues
    
    def create_initial_data(self) -> bool:
        """Create essential initial data"""
        try:
            if self.dry_run:
                logger.info("[DRY RUN] Would create initial data")
                return True
            
            db = SessionLocal()
            try:
                # Check if we already have projects
                existing_projects = db.query(Project).count()
                if existing_projects > 0:
                    logger.info(f"Database already has {existing_projects} projects, skipping initial data creation")
                    return True
                
                # Create Central Store project
                central_project = Project(
                    id="central-store-project",
                    name="Central Store",
                    description="Central repository for uploaded videos awaiting project assignment",
                    camera_model="Various",
                    camera_view="Mixed",
                    signal_type="Mixed",
                    status="Active"
                )
                db.add(central_project)
                
                # Create default test project
                default_project = Project(
                    id="default-test-project",
                    name="Default Test Project", 
                    description="Default project for testing and validation workflows",
                    camera_model="TestCam-HD",
                    camera_view="Front-facing VRU",
                    signal_type="GPIO",
                    status="Active"
                )
                db.add(default_project)
                
                db.commit()
                logger.info("✅ Initial projects created successfully")
                self.successful_operations.add("initial_data")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to create initial data: {e}")
                raise
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ Failed to create initial data: {e}")
            self.failed_operations.add("initial_data")
            return False
    
    def run_full_initialization(self, force: bool = False) -> bool:
        """Run complete database initialization process"""
        logger.info("🚀 Starting comprehensive database initialization...")
        
        initialization_steps = [
            ("Database Connection Test", self.test_connection),
            ("Database Extensions", self.create_database_extensions),
            ("Table Creation", lambda: self.create_all_tables(force=force)),
            ("Index Creation", self.create_critical_indexes),
            ("Initial Data", self.create_initial_data)
        ]
        
        failed_steps = []
        
        for step_name, step_function in initialization_steps:
            logger.info(f"\n📋 Step: {step_name}")
            try:
                if not step_function():
                    failed_steps.append(step_name)
                    logger.error(f"❌ Step '{step_name}' failed")
                else:
                    logger.info(f"✅ Step '{step_name}' completed successfully")
            except Exception as e:
                failed_steps.append(step_name)
                logger.error(f"❌ Step '{step_name}' failed with exception: {e}")
        
        # Final verification
        logger.info("\n🔍 Final Schema Verification")
        schema_report = self.verify_schema()
        
        # Generate final report
        success = len(failed_steps) == 0 and schema_report['status'] == 'healthy'
        
        logger.info("\n" + "="*80)
        if success:
            logger.info("🎉 DATABASE INITIALIZATION COMPLETED SUCCESSFULLY!")
            logger.info(f"✅ Database Type: {schema_report['database_type']}")
            logger.info(f"✅ Tables Created: {schema_report['present_tables']}/{schema_report['total_expected_tables']}")
            logger.info(f"✅ Successful Operations: {len(self.successful_operations)}")
        else:
            logger.error("💥 DATABASE INITIALIZATION COMPLETED WITH ISSUES")
            if failed_steps:
                logger.error(f"❌ Failed Steps: {', '.join(failed_steps)}")
            if schema_report.get('missing_tables'):
                logger.error(f"❌ Missing Tables: {', '.join(schema_report['missing_tables'])}")
            if schema_report.get('column_issues'):
                logger.error(f"❌ Column Issues: {len(schema_report['column_issues'])}")
        
        logger.info("="*80)
        
        return success
    
    def run_migration(self) -> bool:
        """Run database migration for existing installations"""
        logger.info("🔄 Starting database migration...")
        
        try:
            # Check if database exists and has tables
            existing_tables = self.get_existing_tables()
            if not existing_tables:
                logger.info("No existing tables found, running full initialization instead")
                return self.run_full_initialization()
            
            logger.info(f"Found existing database with {len(existing_tables)} tables")
            
            # Run migration steps
            migration_steps = [
                ("Database Health Check", self.test_connection),
                ("Schema Update", lambda: self.create_all_tables(force=False)),
                ("Index Migration", self.create_critical_indexes),
                ("Data Verification", lambda: self.verify_schema()['status'] == 'healthy')
            ]
            
            failed_steps = []
            for step_name, step_function in migration_steps:
                logger.info(f"\n📋 Migration Step: {step_name}")
                try:
                    if not step_function():
                        failed_steps.append(step_name)
                except Exception as e:
                    failed_steps.append(step_name)
                    logger.error(f"❌ Migration step '{step_name}' failed: {e}")
            
            success = len(failed_steps) == 0
            if success:
                logger.info("\n✅ Database migration completed successfully")
            else:
                logger.error(f"\n❌ Database migration completed with {len(failed_steps)} failed steps")
            
            return success
            
        except Exception as e:
            logger.error(f"💥 Database migration failed: {e}")
            return False

def main():
    """Main CLI interface for database management"""
    parser = argparse.ArgumentParser(
        description="AI Model Validation Platform - Database Management",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--init', action='store_true', 
                       help='Initialize fresh database with all tables and data')
    parser.add_argument('--migrate', action='store_true',
                       help='Migrate existing database to latest schema')
    parser.add_argument('--verify', action='store_true',
                       help='Verify database schema without making changes')
    parser.add_argument('--health', action='store_true',
                       help='Check database connectivity and health')
    parser.add_argument('--force', action='store_true',
                       help='Force operations even if tables exist')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    if not any([args.init, args.migrate, args.verify, args.health]):
        parser.print_help()
        return
    
    # Initialize database manager
    db_manager = DatabaseManager(dry_run=args.dry_run)
    
    try:
        if args.health:
            logger.info("🔍 Checking database health...")
            health = get_database_health()
            if health['status'] == 'healthy':
                logger.info("✅ Database is healthy and responsive")
                print(f"Database Status: {health}")
            else:
                logger.error("❌ Database health check failed")
                print(f"Database Issues: {health}")
                sys.exit(1)
        
        elif args.verify:
            logger.info("🔍 Verifying database schema...")
            schema_report = db_manager.verify_schema()
            print(f"\nSchema Verification Report:")
            print(f"Status: {schema_report['status']}")
            print(f"Tables: {schema_report['present_tables']}/{schema_report['total_expected_tables']}")
            if schema_report['missing_tables']:
                print(f"Missing Tables: {schema_report['missing_tables']}")
            if schema_report['column_issues']:
                print(f"Column Issues: {len(schema_report['column_issues'])}")
        
        elif args.init:
            logger.info("🚀 Initializing database...")
            success = db_manager.run_full_initialization(force=args.force)
            sys.exit(0 if success else 1)
        
        elif args.migrate:
            logger.info("🔄 Migrating database...")
            success = db_manager.run_migration()
            sys.exit(0 if success else 1)
    
    except KeyboardInterrupt:
        logger.info("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()