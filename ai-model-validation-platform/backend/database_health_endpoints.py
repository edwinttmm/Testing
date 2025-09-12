"""
Database health check and management endpoints for AI Model Validation Platform.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from typing import Dict, Any, List
import logging

from database import get_db
from database_initialization import get_database_health, DatabaseInitializer
from models import AuthUser, Project, Video, DetectionEvent, GroundTruthObject

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/database", tags=["Database Management"])

@router.get("/health", response_model=Dict[str, Any])
async def get_database_health_status():
    """Get comprehensive database health status."""
    try:
        health_status = get_database_health()
        
        # Add more detailed metrics
        if health_status.get("database_connected"):
            try:
                initializer = DatabaseInitializer()
                initializer.create_engine_with_retry()
                
                # Get table counts
                with initializer.session_local() as session:
                    table_counts = {
                        "users": session.query(func.count(AuthUser.id)).scalar() or 0,
                        "projects": session.query(func.count(Project.id)).scalar() or 0,
                        "videos": session.query(func.count(Video.id)).scalar() or 0,
                        "detection_events": session.query(func.count(DetectionEvent.id)).scalar() or 0,
                        "ground_truth_objects": session.query(func.count(GroundTruthObject.id)).scalar() or 0,
                    }
                    health_status["table_counts"] = table_counts
                    
            except Exception as e:
                health_status["table_counts_error"] = str(e)
        
        return health_status
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database health check failed: {str(e)}"
        )

@router.get("/migration-status")
async def get_migration_status():
    """Get current database migration status."""
    try:
        initializer = DatabaseInitializer()
        initializer.create_engine_with_retry()
        initializer.setup_alembic()
        
        migration_status = initializer.check_migration_status()
        return migration_status
        
    except Exception as e:
        logger.error(f"Migration status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration status check failed: {str(e)}"
        )

@router.post("/initialize")
async def initialize_database_endpoint():
    """Initialize or re-initialize the database."""
    try:
        from database_initialization import initialize_database
        
        success = initialize_database()
        
        if success:
            return {"message": "Database initialized successfully", "success": True}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database initialization failed"
            )
            
    except Exception as e:
        logger.error(f"Database initialization endpoint failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database initialization failed: {str(e)}"
        )

@router.get("/schema-info")
async def get_schema_info(db: Session = Depends(get_db)):
    """Get database schema information."""
    try:
        from sqlalchemy import inspect
        from database import engine
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        schema_info = {}
        for table_name in tables:
            columns = inspector.get_columns(table_name)
            indexes = inspector.get_indexes(table_name)
            foreign_keys = inspector.get_foreign_keys(table_name)
            
            schema_info[table_name] = {
                "columns": [{"name": col["name"], "type": str(col["type"])} for col in columns],
                "indexes": [idx["name"] for idx in indexes],
                "foreign_keys": [fk["name"] for fk in foreign_keys if fk.get("name")]
            }
        
        return {
            "total_tables": len(tables),
            "tables": schema_info
        }
        
    except Exception as e:
        logger.error(f"Schema info retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema info retrieval failed: {str(e)}"
        )

@router.get("/connection-test")
async def test_database_connection():
    """Test database connection with detailed diagnostics."""
    try:
        from database import engine
        
        connection_info = {}
        
        # Test basic connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test_value"))
            connection_info["basic_test"] = result.fetchone()[0] == 1
        
        # Test transaction
        with engine.begin() as conn:
            result = conn.execute(text("SELECT 'transaction_test' as test"))
            connection_info["transaction_test"] = result.fetchone()[0] == "transaction_test"
        
        # Get database version
        with engine.connect() as conn:
            if "postgresql" in str(engine.url).lower():
                result = conn.execute(text("SELECT version()"))
                connection_info["database_version"] = result.fetchone()[0]
            elif "sqlite" in str(engine.url).lower():
                result = conn.execute(text("SELECT sqlite_version()"))
                connection_info["database_version"] = f"SQLite {result.fetchone()[0]}"
        
        # Pool information
        if hasattr(engine, 'pool'):
            try:
                connection_info["pool_info"] = {
                    "size": engine.pool.size(),
                    "checked_out": engine.pool.checkedout(),
                    "overflow": engine.pool.overflow(),
                }
            except:
                connection_info["pool_info"] = "Not available for SQLite"
        
        return {
            "status": "connected",
            "details": connection_info,
            "database_url_masked": str(engine.url).replace(
                engine.url.password or "", "***"
            ) if engine.url.password else str(engine.url)
        }
        
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "database_url_masked": "Connection failed"
        }

@router.get("/performance-metrics")
async def get_database_performance_metrics(db: Session = Depends(get_db)):
    """Get database performance metrics."""
    try:
        metrics = {}
        
        # Query execution time test
        import time
        start_time = time.time()
        
        # Simple queries to test performance
        user_count = db.query(func.count(AuthUser.id)).scalar() or 0
        project_count = db.query(func.count(Project.id)).scalar() or 0
        
        query_time = time.time() - start_time
        
        metrics["query_performance"] = {
            "simple_count_queries_ms": round(query_time * 1000, 2),
            "user_count": user_count,
            "project_count": project_count
        }
        
        # Check for long-running transactions (PostgreSQL only)
        if "postgresql" in str(db.get_bind().url).lower():
            try:
                long_queries = db.execute(text("""
                    SELECT count(*) as count
                    FROM pg_stat_activity 
                    WHERE state = 'active' 
                    AND query_start < NOW() - INTERVAL '1 minute'
                """)).fetchone()[0]
                
                metrics["postgresql_specific"] = {
                    "long_running_queries": long_queries
                }
            except:
                metrics["postgresql_specific"] = {"error": "Could not retrieve PostgreSQL metrics"}
        
        return metrics
        
    except Exception as e:
        logger.error(f"Performance metrics retrieval failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Performance metrics retrieval failed: {str(e)}"
        )