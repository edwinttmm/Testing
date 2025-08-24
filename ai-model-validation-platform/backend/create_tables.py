#!/usr/bin/env python3
"""
Create database tables - Enhanced with comprehensive model imports
"""
import logging
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError
from sqlalchemy import inspect, text
from database import engine, Base, get_database_health
from models import (
    Project, Video, GroundTruthObject, TestSession, DetectionEvent, AuditLog,
    Annotation, AnnotationSession, VideoProjectLink, TestResult, DetectionComparison
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def create_tables():
    """Create all database tables with enhanced error handling"""
    try:
        logger.info("Checking database health...")
        health = get_database_health()
        if health['status'] != 'healthy':
            logger.error(f"Database health check failed: {health}")
            return False
        
        logger.info("Creating database tables...")
        
        # Get existing tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"Found {len(existing_tables)} existing tables: {existing_tables}")
        
        # Create all tables (will skip existing ones)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        
        # Verify critical tables exist
        new_tables = inspector.get_table_names()
        critical_tables = ['projects', 'videos', 'ground_truth_objects', 'detection_events', 
                          'test_sessions', 'annotations', 'annotation_sessions']
        
        missing_tables = [table for table in critical_tables if table not in new_tables]
        if missing_tables:
            logger.error(f"Critical tables missing: {missing_tables}")
            return False
        
        logger.info(f"✅ Database tables created successfully! Total tables: {len(new_tables)}")
        
        # Test with a simple query to ensure the projects table works
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM projects"))
            count = result.scalar()
            logger.info(f"✅ Projects table verified - contains {count} projects")
        
        return True
        
    except ProgrammingError as e:
        if "already exists" in str(e).lower():
            logger.info("Tables already exist (safe to ignore)")
            return True
        logger.error(f"Database programming error: {e}")
        return False
    except SQLAlchemyError as e:
        logger.error(f"Database error creating tables: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error creating tables: {e}")
        return False

def verify_database_schema():
    """Verify all required tables and indexes exist"""
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Required tables from our models
        required_tables = {
            'projects': 'Project configurations and metadata',
            'videos': 'Video files and processing status', 
            'ground_truth_objects': 'Manual annotations for validation',
            'detection_events': 'ML detection results and comparisons',
            'test_sessions': 'Test execution tracking',
            'annotations': 'Ground truth annotations with detection IDs',
            'annotation_sessions': 'Annotation workflow tracking',
            'video_project_links': 'Video-project association mapping',
            'test_results': 'Test metrics and statistical analysis',
            'detection_comparisons': 'Ground truth vs detection comparisons',
            'audit_logs': 'System audit trail'
        }
        
        logger.info("Verifying database schema...")
        for table, description in required_tables.items():
            if table in tables:
                logger.info(f"✅ Table '{table}' exists: {description}")
            else:
                logger.error(f"❌ Table '{table}' missing: {description}")
        
        # Verify critical indexes
        for table in ['projects', 'videos', 'detection_events']:
            if table in tables:
                indexes = inspector.get_indexes(table)
                logger.info(f"Table '{table}' has {len(indexes)} indexes")
        
        return len([t for t in required_tables.keys() if t in tables]) == len(required_tables)
        
    except Exception as e:
        logger.error(f"Schema verification error: {e}")
        return False

if __name__ == "__main__":
    success = create_tables()
    if success:
        logger.info("Verifying schema...")
        verify_database_schema()
    else:
        logger.error("Table creation failed")
        exit(1)