"""
Main Integration Module for Camera Integration System
Integrates camera system with the existing AI model validation platform
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Import existing main application components
try:
    from main import app as main_app, get_db
    from database import SessionLocal, engine
    from models import Base
except ImportError:
    # Fallback for standalone testing
    from fastapi import FastAPI
    main_app = FastAPI()
    def get_db():
        return None

# Import our camera integration components
from camera_integration_service import camera_service, CameraServiceManager
from camera_config_manager import camera_config_manager
from camera_integration_api import camera_api_router
from camera_websocket_handlers import camera_websocket_router

logger = logging.getLogger(__name__)

# Application lifespan management
@asynccontextmanager
async def camera_lifespan(app: FastAPI):
    """Manage camera service lifecycle"""
    try:
        logger.info("Starting camera integration service...")
        
        # Initialize camera service
        external_ip = "155.138.239.131"  # Production external IP
        await camera_service.initialize(external_ip)
        
        logger.info(f"Camera integration service started with external IP: {external_ip}")
        
        # Store startup time
        app.state.camera_startup_time = datetime.utcnow()
        app.state.camera_service_running = True
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start camera integration service: {str(e)}")
        app.state.camera_service_running = False
        raise
    finally:
        logger.info("Shutting down camera integration service...")
        try:
            await camera_service.shutdown()
            app.state.camera_service_running = False
            logger.info("Camera integration service shutdown complete")
        except Exception as e:
            logger.error(f"Error during camera service shutdown: {str(e)}")

# Create camera integration app
camera_app = FastAPI(
    title="AI Model Validation Platform - Camera Integration",
    description="Real-time camera integration and validation system for VRU detection",
    version="1.0.0",
    docs_url="/camera/docs",
    redoc_url="/camera/redoc",
    openapi_url="/camera/openapi.json",
    lifespan=camera_lifespan
)

# Add CORS middleware
camera_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include camera API router
camera_app.include_router(camera_api_router)

# Root endpoint for camera service
@camera_app.get("/camera/", response_model=Dict[str, Any])
async def camera_root():
    """Root endpoint for camera integration service"""
    try:
        service_stats = camera_service.get_service_stats()
        config_summary = camera_config_manager.get_config_summary()
        
        return {
            "service": "AI Model Validation Platform - Camera Integration",
            "version": "1.0.0",
            "status": "running" if camera_service.running else "stopped",
            "external_ip": camera_service.external_ip,
            "startup_time": getattr(camera_app.state, 'camera_startup_time', None),
            "service_stats": service_stats,
            "config_summary": config_summary,
            "endpoints": {
                "api": "/camera/api/v1/camera/",
                "websocket": "/camera/ws/camera",
                "documentation": "/camera/docs",
                "health": "/camera/api/v1/camera/health"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in camera root endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Camera service error: {str(e)}")

# Health check endpoint
@camera_app.get("/camera/health", response_model=Dict[str, Any])
async def camera_health_check():
    """Enhanced health check for camera integration"""
    try:
        # Service health
        service_running = getattr(camera_app.state, 'camera_service_running', False)
        
        # Camera stats
        service_stats = camera_service.get_service_stats() if service_running else {}
        
        # Configuration health
        config_summary = camera_config_manager.get_config_summary()
        
        # System health
        uptime = datetime.utcnow() - getattr(camera_app.state, 'camera_startup_time', datetime.utcnow())
        
        health_status = {
            "status": "healthy" if service_running and camera_service.running else "unhealthy",
            "service_running": service_running,
            "camera_service_active": camera_service.running,
            "uptime_seconds": uptime.total_seconds(),
            "external_ip": camera_service.external_ip if service_running else None,
            "active_cameras": service_stats.get("active_cameras", 0),
            "total_frames_processed": service_stats.get("total_frames_processed", 0),
            "websocket_connections": service_stats.get("websocket_connections", 0),
            "config_health": {
                "total_cameras": config_summary.get("total_cameras", 0),
                "enabled_cameras": config_summary.get("enabled_cameras", 0)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Integration endpoints for existing application
@camera_app.get("/camera/integration/status", response_model=Dict[str, Any])
async def integration_status():
    """Get integration status with main application"""
    try:
        integration_info = {
            "camera_service_integrated": True,
            "main_app_available": main_app is not None,
            "database_integration": get_db is not None,
            "websocket_integration": True,
            "api_integration": True,
            "external_ip_configured": camera_service.external_ip == "155.138.239.131",
            "validation_engine_active": camera_service.running,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return integration_info
        
    except Exception as e:
        logger.error(f"Integration status check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Camera data endpoint for main application integration
@camera_app.get("/camera/data/latest", response_model=Dict[str, Any])
async def get_latest_camera_data(camera_id: Optional[str] = None):
    """Get latest camera data for integration with main application"""
    try:
        if camera_id:
            # Get data for specific camera
            if camera_id not in camera_service.cameras:
                raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
            
            camera_status = await camera_service.get_camera_status(camera_id)
            return {
                "camera_id": camera_id,
                "data": camera_status,
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Get data for all cameras
            all_camera_data = {}
            for cam_id in camera_service.cameras.keys():
                try:
                    camera_status = await camera_service.get_camera_status(cam_id)
                    all_camera_data[cam_id] = camera_status
                except Exception as e:
                    logger.warning(f"Failed to get data for camera {cam_id}: {str(e)}")
                    all_camera_data[cam_id] = {"error": str(e)}
            
            return {
                "cameras": all_camera_data,
                "total_cameras": len(all_camera_data),
                "timestamp": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get camera data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Validation results endpoint
@camera_app.get("/camera/validation/recent", response_model=Dict[str, Any])
async def get_recent_validation_results(limit: int = 50):
    """Get recent validation results for dashboard integration"""
    try:
        # This would typically query a database or cache
        # For now, return service statistics as validation summary
        service_stats = camera_service.get_service_stats()
        
        validation_summary = {
            "total_validations": service_stats.get("total_validations", 0),
            "total_frames_processed": service_stats.get("total_frames_processed", 0),
            "active_cameras": service_stats.get("active_cameras", 0),
            "avg_processing_time": service_stats.get("avg_processing_time", 0.0),
            "buffer_utilization": {
                camera_id: buffer_stats["utilization"]
                for camera_id, buffer_stats in service_stats.get("buffer_stats", {}).items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return validation_summary
        
    except Exception as e:
        logger.error(f"Failed to get validation results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Integration with main application
def integrate_camera_with_main_app(main_application: FastAPI):
    """Integrate camera system with main FastAPI application"""
    try:
        # Mount camera app as sub-application
        main_application.mount("/camera", camera_app)
        
        logger.info("Camera integration mounted on main application at /camera")
        
        # Add camera-specific middleware to main app if needed
        # This could include camera-specific authentication, logging, etc.
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to integrate camera with main app: {str(e)}")
        return False

# Standalone server for camera integration
async def run_camera_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    external_ip: str = "155.138.239.131"
):
    """Run camera integration as standalone server"""
    try:
        logger.info(f"Starting camera integration server on {host}:{port}")
        logger.info(f"External IP configured as: {external_ip}")
        
        config = uvicorn.Config(
            camera_app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
            reload=False  # Set to True for development
        )
        
        server = uvicorn.Server(config)
        await server.serve()
        
    except Exception as e:
        logger.error(f"Failed to start camera server: {str(e)}")
        raise

# Context manager for easy integration testing
class CameraIntegrationManager:
    """Context manager for camera integration lifecycle"""
    
    def __init__(self, external_ip: str = "155.138.239.131"):
        self.external_ip = external_ip
        
    async def __aenter__(self):
        """Start camera integration"""
        await camera_service.initialize(self.external_ip)
        return camera_service
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop camera integration"""
        await camera_service.shutdown()

# Example usage and testing
async def test_camera_integration():
    """Test the complete camera integration"""
    logger.info("Testing camera integration...")
    
    async with CameraIntegrationManager() as service:
        # Test service functionality
        stats = service.get_service_stats()
        logger.info(f"Service stats: {stats}")
        
        # Test configuration management
        config_summary = camera_config_manager.get_config_summary()
        logger.info(f"Config summary: {config_summary}")
        
        # Wait for processing
        await asyncio.sleep(5)
        
        # Final stats
        final_stats = service.get_service_stats()
        logger.info(f"Final stats: {final_stats}")
        
    logger.info("Camera integration test completed")

# Main execution
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run based on command line arguments or environment
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            asyncio.run(test_camera_integration())
        elif sys.argv[1] == "server":
            host = sys.argv[2] if len(sys.argv) > 2 else "0.0.0.0"
            port = int(sys.argv[3]) if len(sys.argv) > 3 else 8080
            external_ip = sys.argv[4] if len(sys.argv) > 4 else "155.138.239.131"
            asyncio.run(run_camera_server(host, port, external_ip))
        else:
            print("Usage: python main_camera_integration.py [test|server] [host] [port] [external_ip]")
    else:
        # Default: integrate with main app if available
        if main_app:
            success = integrate_camera_with_main_app(main_app)
            if success:
                logger.info("Camera integration added to main application")
            else:
                logger.error("Failed to integrate camera with main application")
        else:
            logger.warning("Main application not available, run as standalone server")
            asyncio.run(run_camera_server())