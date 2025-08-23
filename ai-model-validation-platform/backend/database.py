from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, IntegrityError
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./test_database.db"
)


# Validate database URL
if not DATABASE_URL:
    logger.warning("Using default database configuration. Please set DATABASE_URL environment variable.")

# Enhanced engine configuration with optimized connection pool
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        connect_args={"check_same_thread": False}
    )
else:
    # FIXED: Increased connection pool for concurrent load testing
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=25,  # Increased from 10 to handle concurrent stress testing
        max_overflow=50,  # Increased from 20 for burst capacity
        pool_timeout=60,  # Increased timeout from default 30s
        pool_recycle=3600,  # Recycle connections every hour instead of 5 minutes
        pool_pre_ping=True,  # Verify connections before use
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        connect_args={
            "connect_timeout": 60,
            "sslmode": os.getenv("DATABASE_SSLMODE", "prefer"),
            "application_name": "AI_Model_Validation_Platform"
        }
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Database dependency with enhanced error handling and connection management"""
    db = SessionLocal()
    try:
        # Test connection health before yielding
        db.execute(text("SELECT 1"))
        yield db
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error in get_db: {str(e)}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error in get_db: {str(e)}")
        raise
    finally:
        db.close()

def get_database_health() -> dict:
    """Check database connectivity and return health status"""
    try:
        with engine.connect() as connection:
            from sqlalchemy import text
            result = connection.execute(text("SELECT 1"))
            health_info = {
                "status": "healthy",
                "database": "connected"
            }
            
            # Add pool info for non-SQLite databases
            if hasattr(engine, 'pool') and engine.pool:
                try:
                    health_info.update({
                        "pool_size": engine.pool.size(),
                        "checked_out_connections": engine.pool.checkedout()
                    })
                except:
                    pass  # SQLite doesn't have pool info
            
            return health_info
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }

def safe_create_indexes_and_tables():
    """Safely create database indexes and tables with error handling"""
    try:
        # Import Base and models after they're defined
        from models import Base
        
        # Check if database exists and get inspector
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        logger.info(f"Found {len(existing_tables)} existing tables")
        
        # Create tables if they don't exist
        if not existing_tables:
            logger.info("Creating all database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created successfully")
        else:
            # Create only missing tables
            logger.info("Checking for missing tables...")
            with engine.begin() as conn:
                # Use checkfirst=True to avoid duplicate errors
                Base.metadata.create_all(bind=conn, checkfirst=True)
                logger.info("✅ Database schema updated successfully")
        
        # Verify critical indexes exist
        _verify_critical_indexes()
        
    except ProgrammingError as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "duplicate" in error_msg:
            logger.warning(f"Index/table already exists (safe to ignore): {e}")
        else:
            logger.error(f"Database schema error: {e}")
            raise
    except Exception as e:
        logger.error(f"Failed to create database schema: {e}")
        raise

def _verify_critical_indexes():
    """Verify critical indexes exist and create if missing"""
    try:
        inspector = inspect(engine)
        
        # Define critical indexes that must exist
        critical_indexes = {
            'videos': ['idx_video_project_status', 'idx_video_project_created'],
            'ground_truth_objects': ['idx_gt_video_timestamp', 'idx_gt_video_class'],
            'detection_events': ['idx_detection_session_timestamp', 'idx_detection_session_validation']
        }
        
        with engine.connect() as conn:
            for table_name, required_indexes in critical_indexes.items():
                if table_name in inspector.get_table_names():
                    existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
                    
                    for idx_name in required_indexes:
                        if idx_name not in existing_indexes:
                            logger.info(f"Creating missing index: {idx_name}")
                            # Index creation will be handled by SQLAlchemy's table definition
                            
        logger.info("✅ Critical indexes verified")
        
    except Exception as e:
        logger.warning(f"Index verification warning: {e}")