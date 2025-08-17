"""
VRU Detection System - Main FastAPI Application
Vulnerable Road User Detection and Validation Platform
"""

import asyncio
import logging
import sys
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.api import (
    detection_router,
    project_router,
    video_router,
    signal_router,
    validation_router,
    health_router
)
from src.core.config import settings
from src.core.database import init_database, close_database
from src.core.logging import setup_logging
from src.core.exceptions import VRUDetectionException
from src.services.detection_engine import DetectionEngine
from src.services.signal_processor import SignalProcessor

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management"""
    logger.info("Starting VRU Detection System...")
    
    try:
        # Initialize database
        await init_database()
        logger.info("Database initialized successfully")
        
        # Initialize detection engine
        detection_engine = DetectionEngine()
        await detection_engine.initialize()
        app.state.detection_engine = detection_engine
        logger.info("Detection engine initialized successfully")
        
        # Initialize signal processor
        signal_processor = SignalProcessor()
        await signal_processor.initialize()
        app.state.signal_processor = signal_processor
        logger.info("Signal processor initialized successfully")
        
        # Start background tasks
        background_tasks = asyncio.create_task(start_background_services(app))
        app.state.background_tasks = background_tasks
        
        logger.info("VRU Detection System startup completed")
        yield
        
    except Exception as e:
        logger.error(f"Failed to start VRU Detection System: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        # Cleanup
        logger.info("Shutting down VRU Detection System...")
        
        # Cancel background tasks
        if hasattr(app.state, 'background_tasks'):
            app.state.background_tasks.cancel()
            try:
                await app.state.background_tasks
            except asyncio.CancelledError:
                pass
        
        # Cleanup detection engine
        if hasattr(app.state, 'detection_engine'):
            await app.state.detection_engine.cleanup()
        
        # Cleanup signal processor
        if hasattr(app.state, 'signal_processor'):
            await app.state.signal_processor.cleanup()
        
        # Close database connections
        await close_database()
        
        logger.info("VRU Detection System shutdown completed")


async def start_background_services(app: FastAPI) -> None:
    """Start background monitoring and maintenance services"""
    try:
        # Start monitoring services
        monitoring_task = asyncio.create_task(monitor_system_health())
        cleanup_task = asyncio.create_task(periodic_cleanup())
        
        await asyncio.gather(monitoring_task, cleanup_task)
    except asyncio.CancelledError:
        logger.info("Background services cancelled")
    except Exception as e:
        logger.error(f"Background services error: {e}")


async def monitor_system_health() -> None:
    """Monitor system health and performance"""
    while True:
        try:
            # Monitor GPU usage
            if hasattr(torch, 'cuda') and torch.cuda.is_available():
                gpu_memory = torch.cuda.memory_allocated() / 1024**3  # GB
                if gpu_memory > settings.MAX_GPU_MEMORY_GB:
                    logger.warning(f"High GPU memory usage: {gpu_memory:.2f}GB")
            
            # Monitor processing queues
            # Implementation depends on queue system
            
            await asyncio.sleep(30)  # Check every 30 seconds
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Health monitoring error: {e}")
            await asyncio.sleep(60)  # Wait longer on error


async def periodic_cleanup() -> None:
    """Periodic cleanup of temporary files and old data"""
    while True:
        try:
            # Cleanup old screenshots
            await cleanup_old_screenshots()
            
            # Cleanup processing cache
            await cleanup_processing_cache()
            
            await asyncio.sleep(3600)  # Run every hour
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")
            await asyncio.sleep(3600)


async def cleanup_old_screenshots() -> None:
    """Remove screenshots older than retention period"""
    # Implementation for cleaning up old screenshot files
    pass


async def cleanup_processing_cache() -> None:
    """Clear processing cache and temporary files"""
    # Implementation for cache cleanup
    pass


# Create FastAPI application
app = FastAPI(
    title="VRU Detection System",
    description="Vulnerable Road User Detection and Validation Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add metrics instrumentation
if settings.ENABLE_METRICS:
    instrumentator = Instrumentator()
    instrumentator.instrument(app).expose(app)


@app.exception_handler(VRUDetectionException)
async def vru_exception_handler(request: Request, exc: VRUDetectionException) -> JSONResponse:
    """Handle VRU Detection specific exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An internal server error occurred",
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID for tracing"""
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests for monitoring"""
    import time
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Duration: {process_time:.3f}s - "
        f"Request ID: {getattr(request.state, 'request_id', 'unknown')}"
    )
    
    return response


# Include API routers
app.include_router(health_router, prefix="/api/health", tags=["Health"])
app.include_router(project_router, prefix="/api/projects", tags=["Projects"])
app.include_router(video_router, prefix="/api/videos", tags=["Videos"])
app.include_router(detection_router, prefix="/api/detection", tags=["Detection"])
app.include_router(signal_router, prefix="/api/signals", tags=["Signals"])
app.include_router(validation_router, prefix="/api/validation", tags=["Validation"])


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint"""
    return {
        "message": "VRU Detection System API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/api/docs"
    }


if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )