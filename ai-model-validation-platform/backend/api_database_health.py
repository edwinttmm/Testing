#!/usr/bin/env python3
"""
Database Health Check API Endpoints

Provides comprehensive database health monitoring and diagnostics
for the AI Model Validation Platform.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from typing import Dict, List, Optional
from datetime import datetime
import logging

from database import get_db, engine, get_database_health
from database_startup import get_database_startup_status
from models import Project, Video, TestSession, DetectionEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/database", tags=["Database Health"])

@router.get("/health", response_model=Dict)
async def get_database_health_status():
    """
    Get comprehensive database health status
    """
    try:
        # Get basic health
        basic_health = get_database_health()
        
        # Get startup status
        startup_status = get_database_startup_status()
        
        # Get table counts
        table_stats = {}
        try:
            with engine.connect() as conn:
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                for table in tables:
                    try:
                        result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                        count = result.scalar()
                        table_stats[table] = count
                    except Exception as e:
                        table_stats[table] = f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Could not get table statistics: {e}")
        
        return {
            "status": "healthy" if basic_health.get('status') == 'healthy' else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "basic_health": basic_health,
            "startup_status": startup_status,
            "table_statistics": table_stats,
            "total_tables": len(table_stats)
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@router.get("/schema", response_model=Dict)
async def get_database_schema():
    """
    Get detailed database schema information
    """
    try:
        inspector = inspect(engine)
        
        schema_info = {
            "database_type": "PostgreSQL" if 'postgresql' in str(engine.url) else "SQLite",
            "tables": {},
            "total_tables": 0,
            "total_indexes": 0
        }
        
        tables = inspector.get_table_names()
        schema_info["total_tables"] = len(tables)
        
        for table_name in tables:
            try:
                columns = inspector.get_columns(table_name)
                indexes = inspector.get_indexes(table_name)
                foreign_keys = inspector.get_foreign_keys(table_name)
                
                schema_info["tables"][table_name] = {
                    "columns": [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "nullable": col.get("nullable", True),
                            "primary_key": col.get("primary_key", False)
                        } for col in columns
                    ],
                    "indexes": [
                        {
                            "name": idx.get("name"),
                            "columns": idx.get("column_names", []),
                            "unique": idx.get("unique", False)
                        } for idx in indexes
                    ],
                    "foreign_keys": [
                        {
                            "name": fk.get("name"),
                            "constrained_columns": fk.get("constrained_columns", []),
                            "referred_table": fk.get("referred_table"),
                            "referred_columns": fk.get("referred_columns", [])
                        } for fk in foreign_keys
                    ],
                    "column_count": len(columns),
                    "index_count": len(indexes),
                    "foreign_key_count": len(foreign_keys)
                }
                
                schema_info["total_indexes"] += len(indexes)
                
            except Exception as e:
                logger.error(f"Error getting schema for table {table_name}: {e}")
                schema_info["tables"][table_name] = {"error": str(e)}
        
        return schema_info
    
    except Exception as e:
        logger.error(f"Schema retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Schema retrieval failed: {str(e)}")

@router.get("/statistics", response_model=Dict)
async def get_database_statistics(db: Session = Depends(get_db)):
    """
    Get detailed database usage statistics
    """
    try:
        stats = {
            "timestamp": datetime.now().isoformat(),
            "record_counts": {},
            "recent_activity": {},
            "data_quality": {}
        }
        
        # Get record counts
        try:
            stats["record_counts"] = {
                "projects": db.query(Project).count(),
                "videos": db.query(Video).count(),
                "test_sessions": db.query(TestSession).count(),
                "detection_events": db.query(DetectionEvent).count()
            }
        except Exception as e:
            stats["record_counts"] = {"error": str(e)}
        
        # Get recent activity (last 24 hours)
        try:
            from sqlalchemy import func
            from datetime import timedelta
            
            yesterday = datetime.now() - timedelta(days=1)
            
            recent_projects = db.query(Project).filter(
                Project.created_at >= yesterday
            ).count()
            
            recent_videos = db.query(Video).filter(
                Video.created_at >= yesterday
            ).count()
            
            recent_sessions = db.query(TestSession).filter(
                TestSession.created_at >= yesterday
            ).count()
            
            stats["recent_activity"] = {
                "projects_last_24h": recent_projects,
                "videos_last_24h": recent_videos,
                "test_sessions_last_24h": recent_sessions
            }
        except Exception as e:
            stats["recent_activity"] = {"error": str(e)}
        
        # Data quality checks
        try:
            videos_with_ground_truth = db.query(Video).filter(
                Video.ground_truth_generated == True
            ).count()
            
            videos_processing = db.query(Video).filter(
                Video.processing_status == 'processing'
            ).count()
            
            stats["data_quality"] = {
                "videos_with_ground_truth": videos_with_ground_truth,
                "videos_currently_processing": videos_processing,
                "ground_truth_percentage": (
                    (videos_with_ground_truth / stats["record_counts"]["videos"] * 100) 
                    if stats["record_counts"]["videos"] > 0 else 0
                )
            }
        except Exception as e:
            stats["data_quality"] = {"error": str(e)}
        
        return stats
    
    except Exception as e:
        logger.error(f"Statistics retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Statistics retrieval failed: {str(e)}")

@router.post("/migrate")
async def trigger_database_migration():
    """
    Trigger database migration (admin endpoint)
    """
    try:
        from database_init import DatabaseManager
        
        db_manager = DatabaseManager()
        success = db_manager.run_migration()
        
        return {
            "success": success,
            "message": "Migration completed successfully" if success else "Migration completed with issues",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Migration trigger failed: {e}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

@router.post("/verify")
async def verify_database_schema():
    """
    Verify database schema integrity
    """
    try:
        from database_init import DatabaseManager
        
        db_manager = DatabaseManager()
        schema_report = db_manager.verify_schema()
        
        return {
            "verification_result": schema_report,
            "status": "passed" if schema_report['status'] == 'healthy' else "issues_found",
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Schema verification failed: {str(e)}")

@router.get("/connection-test")
async def test_database_connection():
    """
    Test basic database connectivity
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test, NOW() as timestamp" 
                                    if 'postgresql' in str(engine.url) 
                                    else "SELECT 1 as test, datetime('now') as timestamp"))
            row = result.fetchone()
            
            return {
                "status": "connected",
                "test_value": row[0],
                "server_timestamp": str(row[1]),
                "database_type": "PostgreSQL" if 'postgresql' in str(engine.url) else "SQLite",
                "connection_successful": True
            }
    
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return {
            "status": "failed",
            "connection_successful": False,
            "error": str(e),
            "database_type": "Unknown"
        }