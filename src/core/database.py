"""
Database connection and session management for VRU Detection System
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession, 
    create_async_engine, 
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, event
from sqlalchemy.exc import SQLAlchemyError

from src.core.config import settings
from src.models.database import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
engine: Optional[AsyncEngine] = None
async_session_factory: Optional[async_sessionmaker] = None


class DatabaseError(Exception):
    """Database-related errors"""
    pass


def create_database_engine() -> AsyncEngine:
    """Create and configure the database engine"""
    
    # Connection arguments for PostgreSQL
    connect_args = {
        "connect_timeout": 10,
        "command_timeout": 30,
        "server_settings": {
            "application_name": "VRU_Detection_System",
            "jit": "off"  # Disable JIT for consistent performance
        }
    }
    
    # Create engine with connection pooling
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_recycle=settings.DATABASE_POOL_RECYCLE,
        pool_pre_ping=True,  # Verify connections before use
        pool_timeout=30,
        poolclass=QueuePool,
        connect_args=connect_args,
        # Enable autocommit=False for explicit transaction control
        future=True
    )
    
    # Add connection event listeners
    @event.listens_for(engine.sync_engine, "connect")
    def set_postgresql_search_path(dbapi_connection, connection_record):
        """Set search path and other PostgreSQL-specific settings"""
        with dbapi_connection.cursor() as cursor:
            # Set search path
            cursor.execute("SET search_path TO public")
            
            # Set timezone
            cursor.execute("SET timezone TO 'UTC'")
            
            # Enable statement timeout (30 seconds)
            cursor.execute("SET statement_timeout TO 30000")
            
            # Set work memory for complex queries
            cursor.execute("SET work_mem TO '64MB'")
    
    @event.listens_for(engine.sync_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Log connection checkout"""
        logger.debug("Database connection checked out")
    
    @event.listens_for(engine.sync_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Log connection checkin"""
        logger.debug("Database connection checked in")
    
    return engine


async def init_database() -> None:
    """Initialize database connection and create tables"""
    global engine, async_session_factory
    
    try:
        logger.info("Initializing database connection...")
        
        # Create engine
        engine = create_database_engine()
        
        # Create session factory
        async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=True,
            autocommit=False
        )
        
        # Test connection
        async with engine.begin() as conn:
            # Test basic connectivity
            result = await conn.execute(text("SELECT 1"))
            if result.scalar() != 1:
                raise DatabaseError("Database connectivity test failed")
            
            # Check PostgreSQL version
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            logger.info(f"Connected to PostgreSQL: {version}")
            
            # Create all tables
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
            
            # Create indexes if they don't exist
            await create_custom_indexes(conn)
            
            # Set up partitioning for large tables
            await setup_table_partitioning(conn)
            
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if engine:
            await engine.dispose()
        raise DatabaseError(f"Database initialization failed: {e}")


async def create_custom_indexes(conn) -> None:
    """Create custom indexes for performance optimization"""
    
    custom_indexes = [
        # GIN indexes for JSONB columns
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gt_bounding_box_gin 
        ON ground_truth_objects USING gin (bounding_box)
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detection_bounding_box_gin 
        ON detection_events USING gin (bounding_box)
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signal_data_gin 
        ON signal_events USING gin (signal_data)
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_validation_detailed_gin 
        ON validation_results USING gin (detailed_metrics)
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_event_data_gin 
        ON audit_logs USING gin (event_data)
        """,
        
        # Composite indexes for common query patterns
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_detection_session_class_timestamp 
        ON detection_events (test_session_id, class_label, timestamp)
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_gt_video_class_timestamp 
        ON ground_truth_objects (video_id, class_label, timestamp)
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_signal_session_type_timestamp 
        ON signal_events (test_session_id, signal_type, timestamp)
        """,
        
        # Partial indexes for active records
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_projects_active_status 
        ON projects (name, created_at) WHERE status = 'Active'
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_processing 
        ON videos (project_id, created_at) WHERE status IN ('uploaded', 'processing')
        """,
        """
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_running 
        ON test_sessions (project_id, started_at) WHERE status = 'running'
        """
    ]
    
    for index_sql in custom_indexes:
        try:
            await conn.execute(text(index_sql))
            logger.debug(f"Created index: {index_sql.split()[5]}")
        except Exception as e:
            logger.warning(f"Failed to create index: {e}")


async def setup_table_partitioning(conn) -> None:
    """Set up table partitioning for large tables"""
    
    partitioning_sql = [
        # Enable pg_partman extension if available
        """
        CREATE EXTENSION IF NOT EXISTS pg_partman
        """,
        
        # Partition detection_events by test_session_id hash
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'detection_events_partitioned'
            ) THEN
                CREATE TABLE detection_events_partitioned (
                    LIKE detection_events INCLUDING ALL
                ) PARTITION BY HASH (test_session_id);
                
                -- Create 4 partitions
                CREATE TABLE detection_events_p0 PARTITION OF detection_events_partitioned 
                FOR VALUES WITH (modulus 4, remainder 0);
                CREATE TABLE detection_events_p1 PARTITION OF detection_events_partitioned 
                FOR VALUES WITH (modulus 4, remainder 1);
                CREATE TABLE detection_events_p2 PARTITION OF detection_events_partitioned 
                FOR VALUES WITH (modulus 4, remainder 2);
                CREATE TABLE detection_events_p3 PARTITION OF detection_events_partitioned 
                FOR VALUES WITH (modulus 4, remainder 3);
            END IF;
        END
        $$
        """,
        
        # Partition audit_logs by created_at (monthly)
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'audit_logs_partitioned'
            ) THEN
                CREATE TABLE audit_logs_partitioned (
                    LIKE audit_logs INCLUDING ALL
                ) PARTITION BY RANGE (created_at);
                
                -- Create initial partition for current month
                CREATE TABLE audit_logs_y2024m08 PARTITION OF audit_logs_partitioned
                FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
            END IF;
        END
        $$
        """
    ]
    
    for sql in partitioning_sql:
        try:
            await conn.execute(text(sql))
            logger.debug("Partitioning setup completed")
        except Exception as e:
            logger.warning(f"Partitioning setup failed: {e}")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session with automatic cleanup"""
    if not async_session_factory:
        raise DatabaseError("Database not initialized")
    
    async with async_session_factory() as session:
        try:
            yield session
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in database session: {e}")
            raise
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session"""
    async with get_db_session() as session:
        yield session


class DatabaseTransaction:
    """Context manager for database transactions"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.transaction = None
    
    async def __aenter__(self):
        self.transaction = await self.session.begin()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.transaction.rollback()
            logger.error(f"Transaction rolled back due to: {exc_val}")
        else:
            await self.transaction.commit()
            logger.debug("Transaction committed successfully")


async def execute_raw_sql(sql: str, params: dict = None) -> any:
    """Execute raw SQL with parameters"""
    async with get_db_session() as session:
        result = await session.execute(text(sql), params or {})
        await session.commit()
        return result


async def check_database_health() -> dict:
    """Check database health and return status"""
    try:
        async with get_db_session() as session:
            # Check basic connectivity
            await session.execute(text("SELECT 1"))
            
            # Check table accessibility
            result = await session.execute(
                text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
            )
            table_count = result.scalar()
            
            # Check connection pool status
            pool = engine.pool
            pool_status = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "invalid": pool.invalid()
            }
            
            return {
                "status": "healthy",
                "tables": table_count,
                "pool": pool_status,
                "engine": str(engine.url).replace(engine.url.password or "", "***")
            }
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def close_database() -> None:
    """Close database connections"""
    global engine, async_session_factory
    
    if engine:
        logger.info("Closing database connections...")
        await engine.dispose()
        engine = None
        async_session_factory = None
        logger.info("Database connections closed")


# Utility functions for common database operations
async def create_materialized_views() -> None:
    """Create materialized views for analytics"""
    
    materialized_views = [
        # Project statistics view
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS project_statistics AS
        SELECT 
            p.id as project_id,
            p.name,
            COUNT(DISTINCT v.id) as total_videos,
            COUNT(DISTINCT ts.id) as total_test_sessions,
            AVG(vr.precision) as avg_precision,
            AVG(vr.recall) as avg_recall,
            AVG(vr.f1_score) as avg_f1_score,
            AVG(vr.avg_latency_ms) as avg_latency
        FROM projects p
        LEFT JOIN videos v ON p.id = v.project_id
        LEFT JOIN test_sessions ts ON p.id = ts.project_id
        LEFT JOIN validation_results vr ON ts.id = vr.test_session_id
        GROUP BY p.id, p.name
        """,
        
        # Daily performance summary
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS daily_performance_summary AS
        SELECT 
            DATE(ts.created_at) as date,
            COUNT(ts.id) as sessions_run,
            AVG(vr.precision) as avg_precision,
            AVG(vr.recall) as avg_recall,
            AVG(vr.f1_score) as avg_f1_score,
            AVG(de.confidence) as avg_confidence
        FROM test_sessions ts
        JOIN validation_results vr ON ts.id = vr.test_session_id
        JOIN detection_events de ON ts.id = de.test_session_id
        WHERE ts.status = 'completed'
        GROUP BY DATE(ts.created_at)
        ORDER BY date DESC
        """
    ]
    
    async with get_db_session() as session:
        for view_sql in materialized_views:
            try:
                await session.execute(text(view_sql))
                await session.commit()
                logger.info("Created materialized view")
            except Exception as e:
                logger.warning(f"Failed to create materialized view: {e}")
                await session.rollback()


async def refresh_materialized_views() -> None:
    """Refresh materialized views"""
    views_to_refresh = [
        "project_statistics",
        "daily_performance_summary"
    ]
    
    async with get_db_session() as session:
        for view_name in views_to_refresh:
            try:
                await session.execute(text(f"REFRESH MATERIALIZED VIEW {view_name}"))
                await session.commit()
                logger.debug(f"Refreshed materialized view: {view_name}")
            except Exception as e:
                logger.warning(f"Failed to refresh view {view_name}: {e}")
                await session.rollback()


# Export main functions
__all__ = [
    "init_database",
    "close_database", 
    "get_db",
    "get_db_session",
    "DatabaseTransaction",
    "check_database_health",
    "execute_raw_sql",
    "create_materialized_views",
    "refresh_materialized_views"
]