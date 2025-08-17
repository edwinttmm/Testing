"""
Health Check API Router
System health monitoring and status endpoints
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db, check_database_health
from src.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    
    Returns:
        System health status
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "VRU Detection System",
        "version": "1.0.0"
    }


@router.get("/detailed", status_code=status.HTTP_200_OK)
async def detailed_health_check(
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Detailed health check with component status
    
    Args:
        session: Database session
        
    Returns:
        Detailed system health information
    """
    start_time = time.time()
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "VRU Detection System",
        "version": "1.0.0",
        "components": {},
        "response_time_ms": 0
    }
    
    try:
        # Check database health
        db_health = await check_database_health()
        health_status["components"]["database"] = db_health
        
        # Check GPU availability
        gpu_status = await check_gpu_health()
        health_status["components"]["gpu"] = gpu_status
        
        # Check storage
        storage_status = check_storage_health()
        health_status["components"]["storage"] = storage_status
        
        # Check model availability
        model_status = check_model_health()
        health_status["components"]["models"] = model_status
        
        # Determine overall status
        component_statuses = [
            comp.get("status", "unhealthy") 
            for comp in health_status["components"].values()
        ]
        
        if all(status == "healthy" for status in component_statuses):
            health_status["status"] = "healthy"
        elif any(status == "healthy" for status in component_statuses):
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
    
    finally:
        health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
    
    return health_status


@router.get("/database", status_code=status.HTTP_200_OK)
async def database_health_check() -> Dict[str, Any]:
    """
    Database-specific health check
    
    Returns:
        Database health status and metrics
    """
    try:
        db_health = await check_database_health()
        return {
            "component": "database",
            **db_health,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "component": "database",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/gpu", status_code=status.HTTP_200_OK)
async def gpu_health_check() -> Dict[str, Any]:
    """
    GPU-specific health check
    
    Returns:
        GPU health status and metrics
    """
    try:
        gpu_status = await check_gpu_health()
        return {
            "component": "gpu",
            **gpu_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"GPU health check failed: {e}")
        return {
            "component": "gpu",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/storage", status_code=status.HTTP_200_OK)
async def storage_health_check() -> Dict[str, Any]:
    """
    Storage-specific health check
    
    Returns:
        Storage health status and metrics
    """
    try:
        storage_status = check_storage_health()
        return {
            "component": "storage",
            **storage_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return {
            "component": "storage",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Helper functions for component health checks

async def check_gpu_health() -> Dict[str, Any]:
    """Check GPU availability and memory"""
    try:
        # Try to import torch and check CUDA
        try:
            import torch
            
            if torch.cuda.is_available():
                device_count = torch.cuda.device_count()
                current_device = torch.cuda.current_device()
                device_name = torch.cuda.get_device_name(current_device)
                
                # Get memory info
                memory_allocated = torch.cuda.memory_allocated(current_device)
                memory_cached = torch.cuda.memory_reserved(current_device)
                memory_total = torch.cuda.get_device_properties(current_device).total_memory
                
                memory_used_gb = memory_allocated / (1024**3)
                memory_total_gb = memory_total / (1024**3)
                memory_usage_percent = (memory_allocated / memory_total) * 100
                
                return {
                    "status": "healthy",
                    "available": True,
                    "device_count": device_count,
                    "current_device": current_device,
                    "device_name": device_name,
                    "memory_used_gb": round(memory_used_gb, 2),
                    "memory_total_gb": round(memory_total_gb, 2),
                    "memory_usage_percent": round(memory_usage_percent, 2)
                }
            else:
                return {
                    "status": "healthy",
                    "available": False,
                    "reason": "CUDA not available",
                    "fallback": "CPU processing"
                }
                
        except ImportError:
            return {
                "status": "degraded",
                "available": False,
                "reason": "PyTorch not installed",
                "fallback": "Mock detection engine"
            }
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "available": False,
            "error": str(e)
        }


def check_storage_health() -> Dict[str, Any]:
    """Check storage availability and usage"""
    try:
        import shutil
        from pathlib import Path
        
        # Check main storage directories
        directories = [
            settings.UPLOAD_DIR,
            settings.VIDEO_STORAGE_DIR,
            settings.SCREENSHOT_STORAGE_DIR,
            settings.MODEL_DIR
        ]
        
        storage_info = {}
        total_used = 0
        
        for directory in directories:
            if isinstance(directory, str):
                directory = Path(directory)
            
            if directory.exists():
                # Calculate directory size
                dir_size = sum(f.stat().st_size for f in directory.rglob('*') if f.is_file())
                storage_info[directory.name] = {
                    "exists": True,
                    "size_bytes": dir_size,
                    "size_mb": round(dir_size / (1024**2), 2)
                }
                total_used += dir_size
            else:
                storage_info[directory.name] = {
                    "exists": False,
                    "size_bytes": 0,
                    "size_mb": 0
                }
        
        # Get disk usage for the storage root
        disk_usage = shutil.disk_usage(settings.VIDEO_STORAGE_DIR.parent)
        
        return {
            "status": "healthy",
            "directories": storage_info,
            "total_used_gb": round(total_used / (1024**3), 2),
            "disk_total_gb": round(disk_usage.total / (1024**3), 2),
            "disk_free_gb": round(disk_usage.free / (1024**3), 2),
            "disk_usage_percent": round((disk_usage.used / disk_usage.total) * 100, 2)
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


def check_model_health() -> Dict[str, Any]:
    """Check model availability and status"""
    try:
        from pathlib import Path
        
        model_dir = settings.MODEL_DIR
        default_model = settings.DEFAULT_MODEL_NAME
        
        models_info = {}
        
        if model_dir.exists():
            # List available models
            model_files = list(model_dir.glob("*.pt"))
            
            for model_file in model_files:
                models_info[model_file.name] = {
                    "exists": True,
                    "size_mb": round(model_file.stat().st_size / (1024**2), 2),
                    "is_default": model_file.name == default_model
                }
            
            # Check if default model exists
            default_model_path = model_dir / default_model
            default_available = default_model_path.exists()
            
            status = "healthy" if default_available else "degraded"
            
        else:
            status = "degraded"
            default_available = False
        
        return {
            "status": status,
            "model_directory_exists": model_dir.exists(),
            "default_model": default_model,
            "default_model_available": default_available,
            "available_models": models_info
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }