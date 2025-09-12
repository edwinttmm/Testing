"""
Database initialization and migration system for AI Model Validation Platform.

This module handles:
1. Database connection establishment with retry logic
2. Schema creation and migration
3. Initial data seeding
4. Health checks and validation
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError, TimeoutError
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

# Import application components
from database import DATABASE_URL, Base, engine as app_engine, SessionLocal
from models import AuthUser, UserSession, Project  # Import all models
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseInitializer:
    """Database initialization and migration manager."""
    
    def __init__(self):
        self.database_url = self._get_database_url()
        self.engine = None
        self.session_local = None
        self.alembic_cfg = None
        
    def _get_database_url(self) -> str:
        """Get database URL with fallback logic."""
        # Try environment variables first
        db_url = os.getenv('AIVALIDATION_DATABASE_URL') or os.getenv('DATABASE_URL')
        
        if not db_url:
            # Use configured URL
            db_url = DATABASE_URL
        
        if not db_url or db_url == "sqlite:///./test_database.db":
            # Use development database
            db_url = "sqlite:///./dev_database.db"
        
        logger.info(f"Database URL: {self._mask_database_url(db_url)}")
        return db_url
    
    def _mask_database_url(self, db_url: str) -> str:
        """Mask sensitive information in database URL."""
        import re
        return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', db_url)
    
    def create_engine_with_retry(self, max_retries: int = 5, retry_delay: float = 2.0):
        """Create database engine with connection retry logic."""
        retries = 0
        last_error = None
        
        while retries < max_retries:
            try:
                if self.database_url.startswith("sqlite"):
                    self.engine = create_engine(
                        self.database_url,
                        echo=settings.database_echo,
                        connect_args={"check_same_thread": False}
                    )
                else:
                    # PostgreSQL configuration with enhanced retry logic
                    self.engine = create_engine(
                        self.database_url,
                        pool_size=10,
                        max_overflow=20,
                        pool_timeout=60,
                        pool_recycle=3600,
                        pool_pre_ping=True,
                        echo=settings.database_echo,
                        connect_args={
                            "connect_timeout": 60,
                            "sslmode": os.getenv("DATABASE_SSLMODE", "prefer"),
                            "application_name": "AI_Model_Validation_Platform_Init",
                            "keepalives_idle": "600",
                            "keepalives_interval": "30",
                            "keepalives_count": "3",
                        }
                    )
                
                # Test connection
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    logger.info("✅ Database connection established successfully")
                
                self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
                return self.engine
                
            except Exception as e:
                last_error = e
                retries += 1
                if retries < max_retries:
                    logger.warning(f"Database connection attempt {retries} failed: {e}")
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    logger.error(f"Failed to connect to database after {max_retries} attempts")
                    raise last_error
    
    def setup_alembic(self) -> Config:
        """Setup Alembic configuration for migrations."""
        alembic_ini_path = Path(__file__).parent / "alembic.ini"
        
        if not alembic_ini_path.exists():
            logger.error(f"Alembic configuration not found at {alembic_ini_path}")
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini_path}")
        
        self.alembic_cfg = Config(str(alembic_ini_path))
        self.alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)
        
        # Set script location relative to this file
        script_location = str(Path(__file__).parent / "migrations")
        self.alembic_cfg.set_main_option("script_location", script_location)
        
        logger.info(f"Alembic configured with script location: {script_location}")
        return self.alembic_cfg
    
    def check_migration_status(self) -> Dict[str, Any]:
        """Check current migration status."""
        try:
            script = ScriptDirectory.from_config(self.alembic_cfg)
            
            with self.engine.connect() as conn:
                context = MigrationContext.configure(conn)
                current_rev = context.get_current_revision()
                head_rev = script.get_current_head()
                
                pending_revisions = []
                if current_rev != head_rev:
                    for revision in script.walk_revisions():
                        if revision.revision == current_rev:
                            break
                        pending_revisions.append(revision.revision)
                
                return {
                    "current_revision": current_rev,
                    "head_revision": head_rev,
                    "pending_revisions": pending_revisions,
                    "up_to_date": current_rev == head_rev
                }
        except Exception as e:
            logger.error(f"Failed to check migration status: {e}")
            return {
                "current_revision": None,
                "head_revision": None,
                "pending_revisions": [],
                "up_to_date": False,
                "error": str(e)
            }
    
    def run_migrations(self) -> bool:
        """Run database migrations."""
        try:
            logger.info("🔄 Running database migrations...")
            
            # Check if alembic_version table exists
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            if "alembic_version" not in tables:
                logger.info("📝 Initializing Alembic version tracking...")
                # Stamp with initial revision instead of creating all tables
                command.stamp(self.alembic_cfg, "head")
            
            # Run migrations
            command.upgrade(self.alembic_cfg, "head")
            
            # Verify migration status
            status = self.check_migration_status()
            if status.get("up_to_date"):
                logger.info("✅ Database migrations completed successfully")
                return True
            else:
                logger.warning(f"⚠️ Migrations may not be complete: {status}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False
    
    def create_tables_fallback(self) -> bool:
        """Fallback table creation if migrations fail."""
        try:
            logger.info("🔄 Creating tables using SQLAlchemy metadata...")
            
            # Import all models to ensure they're registered
            import models
            from models import (
                AuthUser, UserSession, Project, Video, GroundTruthObject,
                TestSession, DetectionEvent, Annotation, AnnotationSession,
                VideoProjectLink, TestResult, DetectionComparison, AuditLog
            )
            
            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            
            logger.info("✅ Tables created successfully via fallback method")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fallback table creation failed: {e}")
            return False
    
    def seed_initial_data(self) -> bool:
        """Seed initial data if needed."""
        try:
            with self.session_local() as session:
                # Check if admin user exists
                admin_user = session.query(AuthUser).filter_by(username="admin").first()
                
                if not admin_user:
                    logger.info("👤 Creating default admin user...")
                    admin_user = AuthUser(
                        email="admin@aivalidation.local",
                        username="admin",
                        full_name="System Administrator",
                        is_active=True,
                        is_superuser=True,
                        is_verified=True
                    )
                    admin_user.set_password("admin123")  # Change in production
                    session.add(admin_user)
                    session.commit()
                    logger.info("✅ Default admin user created")
                else:
                    logger.info("👤 Admin user already exists")
                
                # Check if default project exists
                default_project = session.query(Project).filter_by(
                    name="Default VRU Validation Project"
                ).first()
                
                if not default_project:
                    logger.info("📁 Creating default project...")
                    default_project = Project(
                        name="Default VRU Validation Project",
                        description="Default project for VRU detection validation",
                        camera_model="Generic Camera",
                        camera_view="Front-facing VRU",
                        signal_type="GPIO",
                        status="Active",
                        owner_id=admin_user.id
                    )
                    session.add(default_project)
                    session.commit()
                    logger.info("✅ Default project created")
                else:
                    logger.info("📁 Default project already exists")
                
                return True
                
        except Exception as e:
            logger.error(f"❌ Initial data seeding failed: {e}")
            return False
    
    def verify_schema(self) -> bool:
        """Verify that all required tables exist."""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            required_tables = [
                "auth_users", "user_sessions", "projects", "videos",
                "ground_truth_objects", "test_sessions", "detection_events",
                "annotations", "annotation_sessions"
            ]
            
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"❌ Missing required tables: {missing_tables}")
                return False
            
            logger.info(f"✅ All required tables exist: {len(tables)} total tables")
            return True
            
        except Exception as e:
            logger.error(f"❌ Schema verification failed: {e}")
            return False
    
    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive database health check."""
        health_status = {
            "database_connected": False,
            "tables_exist": False,
            "migrations_current": False,
            "initial_data_seeded": False,
            "overall_healthy": False
        }
        
        try:
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                health_status["database_connected"] = True
            
            # Check tables
            health_status["tables_exist"] = self.verify_schema()
            
            # Check migrations
            migration_status = self.check_migration_status()
            health_status["migrations_current"] = migration_status.get("up_to_date", False)
            
            # Check initial data
            with self.session_local() as session:
                admin_exists = session.query(AuthUser).filter_by(username="admin").first() is not None
                health_status["initial_data_seeded"] = admin_exists
            
            # Overall health
            health_status["overall_healthy"] = all([
                health_status["database_connected"],
                health_status["tables_exist"],
                health_status["migrations_current"]
            ])
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_status["error"] = str(e)
        
        return health_status
    
    def initialize_database(self) -> bool:
        """Complete database initialization process."""
        logger.info("🚀 Starting database initialization...")
        
        try:
            # Step 1: Create engine with retry logic
            self.create_engine_with_retry()
            
            # Step 2: Setup Alembic
            self.setup_alembic()
            
            # Step 3: Run migrations
            migration_success = self.run_migrations()
            
            # Step 4: Fallback table creation if needed
            if not migration_success:
                logger.warning("Migration failed, attempting fallback table creation...")
                self.create_tables_fallback()
            
            # Step 5: Verify schema
            schema_valid = self.verify_schema()
            if not schema_valid:
                logger.error("Schema validation failed")
                return False
            
            # Step 6: Seed initial data
            self.seed_initial_data()
            
            # Step 7: Final health check
            health = self.run_health_check()
            
            if health["overall_healthy"]:
                logger.info("🎉 Database initialization completed successfully!")
                return True
            else:
                logger.error(f"❌ Database initialization incomplete: {health}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            return False


def initialize_database() -> bool:
    """Main function to initialize the database."""
    initializer = DatabaseInitializer()
    return initializer.initialize_database()


def get_database_health() -> Dict[str, Any]:
    """Get current database health status."""
    initializer = DatabaseInitializer()
    try:
        initializer.create_engine_with_retry()
        initializer.setup_alembic()
        return initializer.run_health_check()
    except Exception as e:
        return {
            "database_connected": False,
            "overall_healthy": False,
            "error": str(e)
        }


if __name__ == "__main__":
    """Run database initialization when script is executed directly."""
    success = initialize_database()
    sys.exit(0 if success else 1)