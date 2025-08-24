#!/usr/bin/env python3
"""
Database Startup Integration for FastAPI Application

This module provides seamless integration between the database initialization
system and FastAPI application startup, with proper error handling and
environment-specific behavior.
"""

import logging
import os
from typing import Optional
from sqlalchemy.exc import SQLAlchemyError
from contextlib import asynccontextmanager

# Import application components
from database_init import DatabaseManager
from database import get_database_health
from config import settings

logger = logging.getLogger(__name__)

class DatabaseStartupManager:
    """
    Manages database initialization during application startup
    with environment-aware behavior and comprehensive error handling.
    """
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        self.is_development = settings.api_debug
        self.is_production = not settings.api_debug
        self.startup_success = False
        
    def should_auto_initialize(self) -> bool:
        """
        Determine if database should be auto-initialized based on environment
        """
        # Check environment variable
        auto_init = os.getenv('AUTO_INIT_DATABASE', 'false').lower() == 'true'
        
        # Development mode: auto-initialize by default
        if self.is_development:
            return auto_init or True
        
        # Production mode: require explicit flag
        return auto_init
    
    def perform_startup_checks(self) -> dict:
        """
        Perform comprehensive startup database checks
        """
        logger.info("🔍 Performing database startup checks...")
        
        checks = {
            'connection': False,
            'health': False,
            'schema': False,
            'tables_exist': False,
            'critical_data': False
        }
        
        try:
            # 1. Test database connection
            if self.db_manager.test_connection():
                checks['connection'] = True
                logger.info("✅ Database connection verified")
            else:
                logger.error("❌ Database connection failed")
                return checks
            
            # 2. Check database health
            health = get_database_health()
            if health['status'] == 'healthy':
                checks['health'] = True
                logger.info("✅ Database health check passed")
            else:
                logger.warning(f"⚠️  Database health concerns: {health}")
            
            # 3. Check if tables exist
            existing_tables = self.db_manager.get_existing_tables()
            if len(existing_tables) >= 5:  # Expect at least 5 core tables
                checks['tables_exist'] = True
                logger.info(f"✅ Found {len(existing_tables)} database tables")
            else:
                logger.info(f"⚠️  Only {len(existing_tables)} tables found, may need initialization")
            
            # 4. Verify schema integrity
            schema_report = self.db_manager.verify_schema()
            if schema_report['status'] == 'healthy':
                checks['schema'] = True
                logger.info("✅ Database schema verification passed")
            else:
                logger.warning(f"⚠️  Schema issues detected: {len(schema_report.get('missing_tables', []))} missing tables")
            
            # 5. Check for critical initial data
            if checks['tables_exist']:
                try:
                    from database import SessionLocal
                    from models import Project
                    
                    db = SessionLocal()
                    try:
                        project_count = db.query(Project).count()
                        if project_count > 0:
                            checks['critical_data'] = True
                            logger.info(f"✅ Found {project_count} projects in database")
                        else:
                            logger.info("⚠️  No projects found, may need initial data creation")
                    finally:
                        db.close()
                except Exception as e:
                    logger.warning(f"⚠️  Could not check initial data: {e}")
        
        except Exception as e:
            logger.error(f"❌ Database startup checks failed: {e}")
        
        return checks
    
    def handle_initialization_needed(self, checks: dict) -> bool:
        """
        Handle cases where database initialization is needed
        """
        if not self.should_auto_initialize():
            logger.warning("⚠️  Database needs initialization but auto-init is disabled")
            logger.warning("    Set AUTO_INIT_DATABASE=true or run: python database_init.py --init")
            return False
        
        logger.info("🚀 Auto-initializing database...")
        
        try:
            # Run appropriate initialization based on what's needed
            if not checks['tables_exist']:
                # Full initialization needed
                logger.info("Running full database initialization...")
                # Use clean_slate=True to handle any existing conflicting objects
                success = self.db_manager.run_full_initialization(clean_slate=True)
            else:
                # Migration/update needed
                logger.info("Running database migration/update...")
                success = self.db_manager.run_migration()
            
            if success:
                logger.info("✅ Database initialization completed successfully")
                return True
            else:
                logger.error("❌ Database initialization failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Database initialization failed with error: {e}")
            return False
    
    def startup_database(self) -> bool:
        """
        Main database startup routine
        """
        logger.info("🚀 Starting database initialization for FastAPI application...")
        
        try:
            # Perform startup checks
            checks = self.perform_startup_checks()
            
            # Determine if database is ready
            database_ready = (
                checks['connection'] and
                checks['health'] and 
                checks['tables_exist'] and
                checks['schema']
            )
            
            if database_ready:
                logger.info("✅ Database is ready for application startup")
                
                # Create initial data if missing (non-critical)
                if not checks['critical_data']:
                    logger.info("Creating initial data...")
                    try:
                        self.db_manager.create_initial_data()
                    except Exception as e:
                        logger.warning(f"⚠️  Could not create initial data: {e}")
                
                self.startup_success = True
                return True
            
            else:
                # Database needs initialization
                logger.info("📊 Database initialization required")
                success = self.handle_initialization_needed(checks)
                self.startup_success = success
                return success
        
        except Exception as e:
            logger.error(f"💥 Critical database startup failure: {e}")
            self.startup_success = False
            
            if self.is_production:
                # In production, fail fast
                raise RuntimeError(f"Database startup failed in production: {e}")
            else:
                # In development, warn but continue
                logger.warning("⚠️  Continuing with degraded database functionality")
                return False
    
    def get_startup_status(self) -> dict:
        """
        Get detailed startup status for health checks
        """
        return {
            'database_startup_success': self.startup_success,
            'environment': 'development' if self.is_development else 'production',
            'auto_initialization_enabled': self.should_auto_initialize(),
            'database_health': get_database_health()
        }

# Global instance for application use
_startup_manager: Optional[DatabaseStartupManager] = None

def get_startup_manager() -> DatabaseStartupManager:
    """Get or create the global startup manager instance"""
    global _startup_manager
    if _startup_manager is None:
        _startup_manager = DatabaseStartupManager()
    return _startup_manager

@asynccontextmanager
async def lifespan_database_manager(app):
    """
    FastAPI lifespan context manager for database initialization
    
    Usage in FastAPI app:
    
    from database_startup import lifespan_database_manager
    
    app = FastAPI(lifespan=lifespan_database_manager)
    """
    startup_manager = get_startup_manager()
    
    # Startup
    logger.info("🚀 FastAPI Application Starting - Database Initialization")
    try:
        database_ready = startup_manager.startup_database()
        if not database_ready:
            logger.warning("⚠️  Application starting with database issues")
        
        logger.info("✅ FastAPI application startup completed")
        yield
    
    except Exception as e:
        logger.error(f"💥 FastAPI startup failed: {e}")
        raise
    
    # Shutdown
    finally:
        logger.info("🔄 FastAPI Application Shutting Down")
        # Add any cleanup here if needed
        logger.info("✅ FastAPI application shutdown completed")

def safe_startup_database() -> bool:
    """
    Safe database startup function for use in existing startup events
    
    This function can be called from FastAPI startup events or other
    initialization routines with comprehensive error handling.
    """
    try:
        startup_manager = get_startup_manager()
        return startup_manager.startup_database()
    except Exception as e:
        logger.error(f"Database startup failed: {e}")
        return False

def get_database_startup_status() -> dict:
    """
    Get current database startup status for health check endpoints
    """
    try:
        startup_manager = get_startup_manager()
        return startup_manager.get_startup_status()
    except Exception as e:
        return {
            'database_startup_success': False,
            'error': str(e),
            'environment': 'unknown',
            'auto_initialization_enabled': False
        }