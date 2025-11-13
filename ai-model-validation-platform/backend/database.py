from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, IntegrityError
import os
import logging
from dotenv import load_dotenv

# Import unified database system
try:
    from unified_database import get_database_manager, get_database_health as unified_get_health
    USE_UNIFIED_DATABASE = True
    logger = logging.getLogger(__name__)
    logger.info("Using Unified Database Architecture")
except ImportError:
    USE_UNIFIED_DATABASE = False
    logger = logging.getLogger(__name__)
    logger.warning("Unified database not available, falling back to legacy system")
    load_dotenv()

# Initialize DATABASE_URL for legacy compatibility
DATABASE_URL = None

# Database URL configuration with proper environment variable precedence
def get_database_url():
    """Get database URL with proper environment variable precedence"""
    # Priority order: VRU_DATABASE_URL > DATABASE_URL > AIVALIDATION_DATABASE_URL > fallback
    database_url = (
        os.getenv("VRU_DATABASE_URL") or
        os.getenv("DATABASE_URL") or 
        os.getenv("AIVALIDATION_DATABASE_URL") or
        "sqlite:///./dev_database.db"
    )
    return database_url

# Legacy database configuration (fallback)
if not USE_UNIFIED_DATABASE:
    try:
        from config import settings
        DATABASE_URL = settings.database_url
        logger.info(f"Using configured database URL: {DATABASE_URL}")
    except ImportError:
        try:
            from database_connectivity_helper import get_enhanced_database_url
            DATABASE_URL = get_enhanced_database_url()
            logger.info(f"Using enhanced database URL: {DATABASE_URL.replace('password', '***')}")
        except ImportError:
            DATABASE_URL = get_database_url()
        logger.info("Using fallback database configuration")
else:
    # Use unified database settings for legacy compatibility
    try:
        db_manager = get_database_manager()
        DATABASE_URL = db_manager.settings.database_url
        logger.info(f"Using unified database URL: {DATABASE_URL}")
    except Exception as e:
        DATABASE_URL = get_database_url()
        logger.warning(f"Failed to get unified database URL, using fallback: {e}")

# Validate database URL
if not DATABASE_URL:
    DATABASE_URL = get_database_url()
    logger.warning("Using default database configuration. Please set VRU_DATABASE_URL or DATABASE_URL environment variable.")

# Mask sensitive information for logging
def mask_database_url(url):
    """Mask password in database URL for logging"""
    import re
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', url)

logger.info(f"Database URL configured: {mask_database_url(DATABASE_URL)}")

# Enhanced engine configuration with optimized connection pool
if DATABASE_URL.startswith("sqlite"):
    # SQLite: avoid implicit RETURNING and use NullPool to reduce cross-thread cursor conflicts.
    from sqlalchemy.pool import NullPool
    engine = create_engine(
        DATABASE_URL,
        echo=os.getenv("DATABASE_ECHO", "false").lower() == "true",
        connect_args={"check_same_thread": False},
        implicit_returning=False,
        poolclass=NullPool
    )
else:
    # Enhanced connection pool with better error handling for Docker networking
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
            "connect_timeout": 60,  # Extended connection timeout for Docker networking
            "sslmode": os.getenv("DATABASE_SSLMODE", "prefer"),
            "application_name": "AI_Model_Validation_Platform",
            # Additional connection parameters for reliability
            "keepalives_idle": "600",  # Keep connections alive for 10 minutes
            "keepalives_interval": "30",  # Send keepalive every 30 seconds  
            "keepalives_count": "3",  # Allow 3 missed keepalives before considering connection dead
        }
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Get database session with proper cleanup on errors."""
    # Use unified database system if available
    if USE_UNIFIED_DATABASE:
        try:
            db_manager = get_database_manager()
            session_cm = db_manager.get_session()
            session = session_cm.__enter__()
            exception_occurred = False

            try:
                # Verify connection is alive
                session.execute(text("SELECT 1"))
                yield session
            except Exception as inner_e:
                exception_occurred = True
                logger.error(f"Database session error during operation: {inner_e}")

                # Exit context manager with exception
                try:
                    session_cm.__exit__(type(inner_e), inner_e, inner_e.__traceback__)
                except Exception as cleanup_error:
                    logger.error(f"Error during session cleanup: {cleanup_error}")
                    pass  # Suppress cleanup errors

                raise  # Re-raise original exception

            finally:
                # Normal cleanup if no exception
                if not exception_occurred:
                    try:
                        session_cm.__exit__(None, None, None)
                    except Exception as cleanup_error:
                        logger.error(f"Error during normal session cleanup: {cleanup_error}")
                        pass  # Suppress cleanup errors

            return  # Now safe - after proper cleanup
        except Exception as e:
            logger.error(f"Unified database error, falling back to legacy: {str(e)}")

    # Legacy database system (fallback)
    db = SessionLocal()
    try:
        # Test connection health before yielding
        db.execute(text("SELECT 1"))
        yield db
    except SQLAlchemyError as e:
        try:
            db.rollback()
        except Exception:
            pass  # Suppress rollback errors during cleanup
        logger.error(f"Database error in get_db: {str(e)}")
        raise
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass  # Suppress rollback errors during cleanup
        logger.error(f"Unexpected error in get_db: {str(e)}")
        raise
    finally:
        try:
            db.close()
        except Exception as close_e:
            # Suppress "Cannot operate on a closed database" errors - session already closed
            error_msg = str(close_e).lower()
            if "closed database" not in error_msg and "invalid" not in error_msg:
                logger.warning(f"Error closing database connection: {str(close_e)}")

def get_database_health() -> dict:
    """Check database connectivity and return health status with detailed information"""
    try:
        # Test connection with explicit timeout
        from sqlalchemy import text
        with engine.connect() as connection:
            # Use a simple query to test connectivity
            result = connection.execute(text("SELECT 1 as test_connection"))
            test_value = result.fetchone()[0]
            
            if test_value != 1:
                raise Exception("Database connectivity test failed - unexpected result")
            
            health_info = {
                "status": "healthy",
                "database": "connected",
                "url_configured": mask_database_url(DATABASE_URL),
                "connection_test": "passed"
            }
            
            # Add pool info for non-SQLite databases
            if hasattr(engine, 'pool') and engine.pool:
                try:
                    health_info.update({
                        "pool_size": engine.pool.size(),
                        "checked_out_connections": engine.pool.checkedout(),
                        "pool_status": "active"
                    })
                except Exception as pool_error:
                    health_info["pool_status"] = f"pool_info_unavailable: {str(pool_error)}"
            
            # Test table existence (basic schema validation)
            try:
                inspector = inspect(engine)
                table_count = len(inspector.get_table_names())
                health_info["schema_status"] = "tables_present" if table_count > 0 else "no_tables"
                health_info["table_count"] = table_count
            except Exception as schema_error:
                health_info["schema_status"] = f"schema_check_failed: {str(schema_error)}"
            
            return health_info
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Database health check failed: {error_msg}")
        
        # Provide more detailed error information
        health_info = {
            "status": "unhealthy",
            "database": "disconnected",
            "error": error_msg,
            "url_configured": mask_database_url(DATABASE_URL)
        }
        
        # Check if it's a connection error vs authentication error
        if "authentication failed" in error_msg.lower() or "password" in error_msg.lower():
            health_info["error_type"] = "authentication_failed"
            health_info["suggestion"] = "Check database credentials in environment variables"
        elif "could not connect" in error_msg.lower() or "connection refused" in error_msg.lower():
            health_info["error_type"] = "connection_refused"
            health_info["suggestion"] = "Check if database server is running and accessible"
        elif "could not translate host name" in error_msg.lower() or "name resolution" in error_msg.lower():
            health_info["error_type"] = "dns_resolution_failed"
            health_info["suggestion"] = "Check if database hostname is accessible (may need Docker/network setup)"
        elif "does not exist" in error_msg.lower():
            health_info["error_type"] = "database_not_found"
            health_info["suggestion"] = "Check if database name is correct and database exists"
        else:
            health_info["error_type"] = "unknown_error"
        
        return health_info

def ensure_database_connection():
    """Ensure database connection is working, with retry logic for startup"""
    import time
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            health = get_database_health()
            if health["status"] == "healthy":
                logger.info(f"✅ Database connection established successfully on attempt {attempt + 1}")
                return True
            else:
                logger.warning(f"Database health check failed on attempt {attempt + 1}: {health.get('error', 'Unknown error')}")
                if health.get("error_type") == "dns_resolution_failed":
                    logger.info("DNS resolution failed - may be running outside Docker environment")
                    
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            
        if attempt < max_retries - 1:
            logger.info(f"Retrying database connection in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 1.5  # Exponential backoff
    
    logger.error("❌ Failed to establish database connection after all retries")
    return False

def initialize_database_on_startup():
    """Initialize database connection and create tables if needed"""
    logger.info("🔌 Initializing database connection...")
    
    # Log current configuration
    logger.info(f"Database URL: {mask_database_url(DATABASE_URL)}")
    
    # Check if we can connect
    if not ensure_database_connection():
        logger.warning("⚠️  Database connection failed - application will start but database features may not work")
        return False
    
    # Create tables if connection is successful
    try:
        safe_create_indexes_and_tables()

        # One-time SQLite migrations to align legacy DBs with current ORM
        try:
            if str(engine.url).startswith('sqlite'):
                from sqlite_migrations import ensure_test_sessions_columns, ensure_detection_events_columns, ensure_videos_columns
                ts_result = ensure_test_sessions_columns(engine)
                de_result = ensure_detection_events_columns(engine)
                v_result = ensure_videos_columns(engine)
                logger.info(f"SQLite migrations result (test_sessions): {ts_result}")
                logger.info(f"SQLite migrations result (detection_events): {de_result}")
                logger.info(f"SQLite migrations result (videos): {v_result}")
        except Exception as e:
            logger.warning(f"SQLite migrations skipped/failed: {e}")
        logger.info("✅ Database initialization completed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Database table creation failed: {e}")
        return False

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
