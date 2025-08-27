"""
VRU Production Service Router
Routes requests to appropriate services based on deployment configuration
"""

import os
import asyncio
import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Import service implementations
from .ml_inference_engine import ml_engine
from .camera_integration_service import camera_service  
from .validation_engine import validation_engine

logger = logging.getLogger(__name__)

# Determine service type from environment
SERVICE_TYPE = os.getenv('VRU_SERVICE_TYPE', 'api_gateway')

def create_app() -> FastAPI:
    """Create FastAPI app based on service type"""
    
    if SERVICE_TYPE == 'ml_engine':
        return create_ml_engine_app()
    elif SERVICE_TYPE == 'camera_service':
        return create_camera_service_app()
    elif SERVICE_TYPE == 'validation_engine':
        return create_validation_engine_app()
    elif SERVICE_TYPE == 'api_gateway':
        return create_api_gateway_app()
    else:
        raise ValueError(f"Unknown service type: {SERVICE_TYPE}")

def create_ml_engine_app() -> FastAPI:
    """Create ML engine service"""
    app = FastAPI(
        title="VRU ML Engine",
        description="Machine Learning Inference Engine for VRU Detection",
        version="1.0.0"
    )
    
    @app.on_event("startup")
    async def startup_event():
        await ml_engine.initialize()
    
    @app.on_event("shutdown")
    async def shutdown_event():
        await ml_engine.shutdown()
    
    @app.get("/health")
    async def health_check():
        return await ml_engine.health_check()
    
    @app.get("/models/info")
    async def get_model_info():
        return await ml_engine.get_model_info()
    
    @app.post("/detect/image")
    async def detect_objects_in_image(image_path: str):
        return await ml_engine.detect_objects(image_path)
    
    @app.post("/detect/video")  
    async def process_video(video_path: str, frame_skip: int = 1):
        return await ml_engine.process_video(video_path, frame_skip)
    
    return app

def create_camera_service_app() -> FastAPI:
    """Create camera service"""
    app = FastAPI(
        title="VRU Camera Service",
        description="Camera Integration Service for VRU Platform",
        version="1.0.0"
    )
    
    @app.on_event("startup")
    async def startup_event():
        await camera_service.initialize()
    
    @app.on_event("shutdown")
    async def shutdown_event():
        await camera_service.shutdown()
    
    @app.get("/health")
    async def health_check():
        return await camera_service.health_check()
    
    @app.get("/cameras")
    async def get_camera_list():
        return await camera_service.get_camera_list()
    
    @app.get("/cameras/{camera_id}")
    async def get_camera_info(camera_id: str):
        return await camera_service.get_camera_info(camera_id)
    
    return app

def create_validation_engine_app() -> FastAPI:
    """Create validation engine service"""
    app = FastAPI(
        title="VRU Validation Engine",
        description="Validation Workflow Engine for VRU Platform",
        version="1.0.0"
    )
    
    @app.on_event("startup")
    async def startup_event():
        await validation_engine.initialize()
    
    @app.get("/health")
    async def health_check():
        return await validation_engine.health_check()
    
    return app

def create_api_gateway_app() -> FastAPI:
    """Create main API gateway"""
    app = FastAPI(
        title="VRU API Gateway",
        description="Main API Gateway for VRU Platform",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv('VRU_CORS_ORIGINS', '').split(','),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize all services for gateway
    @app.on_event("startup")
    async def startup_event():
        await ml_engine.initialize()
        await camera_service.initialize()
        await validation_engine.initialize()
    
    @app.get("/health")
    async def health_check():
        """Combined health check"""
        ml_health = await ml_engine.health_check()
        camera_health = await camera_service.health_check()
        validation_health = await validation_engine.health_check()
        
        overall_status = "healthy" if all([
            ml_health['status'] == 'healthy',
            camera_health['status'] == 'healthy', 
            validation_health['status'] == 'healthy'
        ]) else "unhealthy"
        
        return {
            'status': overall_status,
            'services': {
                'ml_engine': ml_health,
                'camera_service': camera_health,
                'validation_engine': validation_health
            }
        }
    
    # Proxy endpoints to services
    @app.get("/ml/models/info")
    async def get_ml_model_info():
        return await ml_engine.get_model_info()
    
    @app.get("/cameras")
    async def get_cameras():
        return await camera_service.get_camera_list()
    
    return app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv('VRU_API_PORT', 8000))
    host = os.getenv('VRU_API_HOST', '0.0.0.0')
    
    uvicorn.run(
        "main_service_router:app",
        host=host,
        port=port,
        reload=False,
        workers=1 if SERVICE_TYPE != 'api_gateway' else 4
    )