"""
Health check endpoints for container orchestration and monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis
import os
import logging
from datetime import datetime
from typing import Dict, Any

from database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
health_router = APIRouter(prefix="/health", tags=["health"])

def get_redis_client():
    """Get Redis client for health checks."""
    try:
        redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
        client = redis.from_url(redis_url, decode_responses=True)
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None

@health_router.get("/")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "vru-validation-backend",
        "version": "1.0.0"
    }

@health_router.get("/detailed")
async def detailed_health_check(db: Session = Depends(get_db)):
    """Detailed health check including all dependencies."""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "vru-validation-backend",
        "version": "1.0.0",
        "dependencies": {}
    }
    
    overall_healthy = True
    
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["dependencies"]["database"] = {
            "status": "healthy",
            "type": "postgresql",
            "message": "Connection successful"
        }
    except Exception as e:
        overall_healthy = False
        health_status["dependencies"]["database"] = {
            "status": "unhealthy",
            "type": "postgresql",
            "message": f"Connection failed: {str(e)}"
        }
    
    # Check Redis connectivity
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.ping()
            health_status["dependencies"]["redis"] = {
                "status": "healthy",
                "type": "redis",
                "message": "Connection successful"
            }
        except Exception as e:
            overall_healthy = False
            health_status["dependencies"]["redis"] = {
                "status": "unhealthy",
                "type": "redis",
                "message": f"Connection failed: {str(e)}"
            }
    else:
        overall_healthy = False
        health_status["dependencies"]["redis"] = {
            "status": "unhealthy",
            "type": "redis",
            "message": "Redis client initialization failed"
        }
    
    # Check environment variables
    required_env_vars = [
        "DATABASE_URL",
        "AIVALIDATION_SECRET_KEY",
        "REDIS_URL"
    ]
    
    missing_env_vars = []
    for var in required_env_vars:
        if not os.environ.get(var):
            missing_env_vars.append(var)
    
    if missing_env_vars:
        overall_healthy = False
        health_status["dependencies"]["environment"] = {
            "status": "unhealthy",
            "type": "environment",
            "message": f"Missing environment variables: {', '.join(missing_env_vars)}"
        }
    else:
        health_status["dependencies"]["environment"] = {
            "status": "healthy",
            "type": "environment",
            "message": "All required environment variables present"
        }
    
    # Update overall status
    if not overall_healthy:
        health_status["status"] = "unhealthy"
    
    return health_status

@health_router.get("/database")
async def database_health_check(db: Session = Depends(get_db)):
    """Database-specific health check."""
    try:
        # Test basic connectivity
        result = db.execute(text("SELECT 1 as test_value"))
        test_value = result.scalar()
        
        # Test database metadata
        db_info_result = db.execute(text("SELECT version() as db_version"))
        db_version = db_info_result.scalar()
        
        # Test current database and user
        current_db_result = db.execute(text("SELECT current_database() as current_db, current_user as current_user"))
        current_info = current_db_result.fetchone()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": {
                "connection": "successful",
                "version": db_version,
                "current_database": current_info.current_db if current_info else "unknown",
                "current_user": current_info.current_user if current_info else "unknown",
                "test_query_result": test_value
            }
        }
    
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "database": {
                    "connection": "failed",
                    "error": str(e)
                }
            }
        )

@health_router.get("/redis")
async def redis_health_check():
    """Redis-specific health check."""
    redis_client = get_redis_client()
    
    if not redis_client:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "redis": {
                    "connection": "failed",
                    "error": "Failed to initialize Redis client"
                }
            }
        )
    
    try:
        # Test ping
        ping_result = redis_client.ping()
        
        # Test set/get operations
        test_key = "health_check_test"
        test_value = f"test_{datetime.utcnow().timestamp()}"
        
        redis_client.set(test_key, test_value, ex=60)  # Expire in 60 seconds
        retrieved_value = redis_client.get(test_key)
        
        # Clean up test key
        redis_client.delete(test_key)
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "redis": {
                "connection": "successful",
                "ping": ping_result,
                "operations": "successful",
                "test_key_set": test_value,
                "test_key_retrieved": retrieved_value,
                "operations_match": test_value == retrieved_value
            }
        }
    
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "redis": {
                    "connection": "failed",
                    "error": str(e)
                }
            }
        )

@health_router.get("/readiness")
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes-style readiness probe.
    Returns 200 if service is ready to handle requests.
    """
    try:
        # Check database
        db.execute(text("SELECT 1"))
        
        # Check Redis
        redis_client = get_redis_client()
        if redis_client:
            redis_client.ping()
        else:
            raise Exception("Redis client not available")
        
        return {"status": "ready"}
    
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail={"status": "not ready", "error": str(e)})

@health_router.get("/liveness")
async def liveness_check():
    """
    Kubernetes-style liveness probe.
    Returns 200 if service is alive (doesn't check dependencies).
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": "service is running"
    }