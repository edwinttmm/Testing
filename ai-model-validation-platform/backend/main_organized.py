"""
AI Model Validation Platform - Organized Main Application
========================================================

Reorganized FastAPI application with structured router architecture.
This version consolidates scattered endpoints into organized routers following
FastAPI best practices for maintainability and scalability.
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError, TimeoutError
from sqlalchemy import func, select, delete, text
from typing import List, Optional, AsyncIterator
from pydantic import ValidationError
from datetime import datetime, timezone
import threading
import time
import uvicorn
import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager

# Configuration and core imports
from config import settings, setup_logging, create_directories, validate_environment
from database import SessionLocal, engine
from models import Base

# Import organized routers
from routers.projects import router as projects_router
from routers.videos import router as videos_router
from routers.test_sessions import router as test_sessions_router
from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router

# Import specialized routers (keep existing functionality)
from api_enhanced_test import router as enhanced_test_router
from api_enhanced_test_workflow import router as enhanced_test_workflow_router
from api_enhanced_test_workflow_integrated import router as enhanced_test_workflow_integrated_router
from api_signal_validation import router as signal_validation_router
from api_comprehensive_results import router as comprehensive_results_router
from api_enhanced_test_execution import enhanced_test_execution_router
from api_project_session_management import project_session_router

# Import Socket.IO integration
from socketio_server import sio, create_socketio_app

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)

# ============================================================================
# APPLICATION LIFECYCLE MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("🚀 Starting AI Model Validation Platform (Organized Architecture)")
    
    try:
        # Validate environment
        validate_environment()
        
        # Create necessary directories
        create_directories()
        
        # Initialize database tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables initialized")
        
        # Additional startup tasks
        logger.info("✅ Application startup complete")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    finally:
        # Cleanup tasks
        logger.info("🛑 Shutting down application")

# ============================================================================
# FASTAPI APPLICATION SETUP
# ============================================================================

app = FastAPI(
    title="AI Model Validation Platform (Organized)",
    description="Organized API architecture for AI model validation with structured routers",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"🌐 {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response time
    process_time = time.time() - start_time
    logger.info(f"⏱️  {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
    
    return response

# Error handling middleware
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """Global error handling middleware"""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.error(f"❌ Unhandled error in {request.method} {request.url.path}: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(e)}
        )

# Performance monitoring middleware
@app.middleware("http")
async def performance_monitoring(request: Request, call_next):
    """Monitor request performance and log slow requests"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log slow requests (>2 seconds)
    if process_time > 2.0:
        logger.warning(f"🐌 Slow request: {request.method} {request.url.path} took {process_time:.3f}s")
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    return response

# ============================================================================
# ORGANIZED ROUTER REGISTRATION
# ============================================================================

# Core business logic routers (organized)
app.include_router(projects_router, tags=["Projects"])
app.include_router(videos_router, tags=["Videos"]) 
app.include_router(test_sessions_router, tags=["Test Sessions"])
app.include_router(auth_router, tags=["Authentication"])
app.include_router(dashboard_router, tags=["Dashboard"])

# Specialized/enhanced routers (keep existing functionality)
app.include_router(enhanced_test_router, tags=["Enhanced Testing"])
app.include_router(enhanced_test_workflow_router, tags=["Test Workflows"])
app.include_router(enhanced_test_workflow_integrated_router, tags=["Integrated Workflows"])
app.include_router(signal_validation_router, tags=["Signal Validation"])
app.include_router(comprehensive_results_router, tags=["Results"])
app.include_router(enhanced_test_execution_router, tags=["Test Execution"])
app.include_router(project_session_router, tags=["Project Sessions"])

# Conditional imports for optional features
try:
    from src.api.enhanced_test_endpoints import router as enhanced_test_endpoints_router
    app.include_router(enhanced_test_endpoints_router, tags=["Enhanced Test Endpoints"])
    logger.info("✅ Enhanced test endpoints loaded")
except ImportError:
    logger.info("ℹ️  Enhanced test endpoints not available")

try:
    from src.api.simple_detection_endpoints import router as simple_detection_router
    app.include_router(simple_detection_router, tags=["Simple Detection"])
    logger.info("✅ Simple detection endpoints loaded")
except ImportError:
    logger.info("ℹ️  Simple detection endpoints not available")

try:
    from src.api.results_endpoints import router as basic_results_router
    app.include_router(basic_results_router, tags=["Basic Results"])
    logger.info("✅ Basic results endpoints loaded")
except ImportError:
    logger.info("ℹ️  Basic results endpoints not available")

# Optional specialized routers
try:
    from routes.labjack_timing import router as labjack_router
    from routes.labjack_timing_api import router as labjack_timing_router
    app.include_router(labjack_router, tags=["LabJack"])
    app.include_router(labjack_timing_router, tags=["LabJack Timing"])
    logger.info("✅ LabJack integration loaded")
except ImportError:
    logger.info("ℹ️  LabJack integration not available")

# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors"""
    logger.error(f"Validation error in {request.url.path}: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation error", "errors": exc.errors()}
    )

@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle SQLAlchemy database errors"""
    logger.error(f"Database error in {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error occurred", "error": str(exc)}
    )

@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError):
    """Handle database integrity constraint violations"""
    logger.error(f"Database integrity error in {request.url.path}: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": "Data integrity constraint violation", "error": str(exc.orig)}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with enhanced logging"""
    logger.warning(f"HTTP {exc.status_code} in {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other unhandled exceptions"""
    logger.error(f"Unhandled exception in {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

# Serve static files (screenshots, uploads, etc.)
static_dirs = [
    ("screenshots", "screenshots"),
    ("uploads", "uploads"), 
    ("exports", "exports")
]

for mount_path, directory in static_dirs:
    if os.path.exists(directory):
        app.mount(f"/{mount_path}", StaticFiles(directory=directory), name=mount_path)
        logger.info(f"✅ Static files mounted: /{mount_path} -> {directory}")

# ============================================================================
# WEBSOCKET INTEGRATION
# ============================================================================

# WebSocket endpoints for real-time communication
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    """General WebSocket endpoint"""
    await sio.websocket_handler(websocket)

@app.websocket("/ws/progress/{connection_type}")
async def progress_websocket(websocket, connection_type: str):
    """Progress monitoring WebSocket"""
    await sio.websocket_handler(websocket, connection_type)

@app.websocket("/ws/test-session/{session_id}")
async def test_session_websocket(websocket, session_id: str):
    """Test session specific WebSocket"""
    await sio.websocket_handler(websocket, f"session_{session_id}")

# ============================================================================
# ROOT AND HEALTH ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "AI Model Validation Platform",
        "version": "2.0.0",
        "architecture": "Organized Router Structure",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "organized_routers": True,
            "authentication": True,
            "real_time_monitoring": True,
            "websocket_support": True,
            "static_file_serving": True
        },
        "endpoints": {
            "api_docs": "/docs",
            "health_check": "/health",
            "dashboard": "/api/dashboard/stats",
            "projects": "/api/projects",
            "videos": "/api/videos",
            "test_sessions": "/api/test-sessions",
            "authentication": "/auth"
        }
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        # Database connectivity check
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
        finally:
            db.close()
        
        # Check static directories
        static_status = {}
        for mount_path, directory in static_dirs:
            static_status[mount_path] = {
                "exists": os.path.exists(directory),
                "readable": os.access(directory, os.R_OK) if os.path.exists(directory) else False
            }
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "architecture": "Organized Router Structure",
            "components": {
                "database": db_status,
                "static_files": static_status,
                "routers": {
                    "projects": "loaded",
                    "videos": "loaded", 
                    "test_sessions": "loaded",
                    "auth": "loaded",
                    "dashboard": "loaded"
                }
            },
            "uptime": time.time()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )

@app.get("/health/simple")
async def simple_health_check():
    """Simple health check for load balancers"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# ============================================================================
# API INFORMATION ENDPOINTS
# ============================================================================

@app.get("/api/info")
async def get_api_info():
    """Get comprehensive API information"""
    return {
        "name": "AI Model Validation Platform API",
        "version": "2.0.0",
        "architecture": "Organized Router Structure",
        "documentation": "/docs",
        "router_organization": {
            "projects": {
                "prefix": "/api/projects",
                "description": "Project management endpoints",
                "endpoints_count": 10
            },
            "videos": {
                "prefix": "/api/videos", 
                "description": "Video upload and management endpoints",
                "endpoints_count": 12
            },
            "test_sessions": {
                "prefix": "/api/test-sessions",
                "description": "Test session lifecycle endpoints", 
                "endpoints_count": 10
            },
            "auth": {
                "prefix": "/auth",
                "description": "Authentication and user management endpoints",
                "endpoints_count": 12
            },
            "dashboard": {
                "prefix": "/api/dashboard",
                "description": "Dashboard statistics and monitoring endpoints",
                "endpoints_count": 8
            }
        },
        "features": [
            "Organized router architecture",
            "Comprehensive error handling",
            "Performance monitoring",
            "Real-time WebSocket support", 
            "JWT authentication",
            "Database health monitoring",
            "Static file serving",
            "Request logging"
        ]
    }

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == "__main__":
    logger.info("🚀 Starting AI Model Validation Platform with Organized Architecture")
    
    uvicorn.run(
        "main_organized:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )