#!/usr/bin/env python3
"""
Main Integration Module for Unified VRU API
SPARC Implementation: Integration layer with existing main.py FastAPI application

This module provides integration between the unified VRU API orchestration layer 
and the existing FastAPI application, ensuring seamless coordination and 
backward compatibility.

Key Features:
- Unified API orchestration integration
- Service coordination middleware setup
- WebSocket orchestration integration
- Error handling and monitoring setup
- External IP configuration (155.138.239.131)
- Memory coordination via vru-api-orchestration namespace

Architecture:
- MainAppIntegration: Integrates unified VRU API with existing FastAPI
- ServiceMountManager: Manages service mounting and routing
- MiddlewareManager: Handles middleware setup and coordination
- LifecycleManager: Manages application lifecycle
"""

import logging
import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

# FastAPI imports
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Add the src directory to Python path for imports
backend_dir = Path(__file__).parent.parent
src_dir = backend_dir / "src"
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(backend_dir))

# Import unified VRU API components
from unified_vru_api import create_unified_vru_app, vru_orchestrator
from service_coordination_middleware import ServiceCoordinationMiddleware, create_coordination_middleware
from websocket_orchestration import websocket_orchestrator, websocket_orchestrator_lifespan
from error_handling_monitoring import comprehensive_monitor, MonitoringMiddleware, monitoring_lifespan

logger = logging.getLogger(__name__)

class MainAppIntegration:
    """Integration manager for unified VRU API with existing main.py"""
    
    def __init__(self, external_ip: str = "155.138.239.131"):
        self.external_ip = external_ip
        self.existing_app = None
        self.unified_app = None
        self.integrated_app = None
        self.middleware_configured = False
        
    def create_integrated_app(self, existing_app: Optional[FastAPI] = None) -> FastAPI:
        """Create integrated application combining existing and unified VRU API"""
        
        # Create unified VRU app
        self.unified_app = create_unified_vru_app()
        
        if existing_app:
            # Integration mode: mount unified API on existing app
            self.existing_app = existing_app
            self.integrated_app = self._integrate_with_existing_app()
        else:
            # Standalone mode: use unified app directly
            self.integrated_app = self.unified_app
        
        # Setup middleware and configuration
        self._setup_middleware()
        self._setup_cors()
        self._add_integration_endpoints()
        
        return self.integrated_app
    
    def _integrate_with_existing_app(self) -> FastAPI:
        """Integrate unified VRU API with existing FastAPI app"""
        
        # Mount unified VRU API on existing app
        self.existing_app.mount("/vru", self.unified_app)
        
        # Add unified endpoints to existing app
        self._add_unified_endpoints_to_existing()
        
        # Setup lifecycle events
        self._setup_integrated_lifecycle()
        
        return self.existing_app
    
    def _add_unified_endpoints_to_existing(self):
        """Add unified VRU endpoints to existing app"""
        
        # Add unified health endpoint
        @self.existing_app.get("/api/unified/health")
        async def unified_health_check():
            """Unified health check endpoint"""
            return await vru_orchestrator.process_api_request({
                "endpoint_type": "health",
                "method": "GET",
                "path": "/health",
                "data": {}
            })
        
        # Add unified status endpoint
        @self.existing_app.get("/api/unified/status")
        async def unified_status():
            """Get unified system status"""
            try:
                status = {
                    "vru_orchestrator": vru_orchestrator.service_health if hasattr(vru_orchestrator, 'service_health') else {},
                    "websocket_orchestrator": websocket_orchestrator.get_orchestrator_status(),
                    "monitoring": comprehensive_monitor.get_comprehensive_status(),
                    "external_ip": self.external_ip,
                    "integration_status": "active"
                }
                return JSONResponse(status_code=200, content=status)
            except Exception as e:
                logger.error(f"Failed to get unified status: {str(e)}")
                return JSONResponse(
                    status_code=500, 
                    content={"error": "Failed to get status", "message": str(e)}
                )
        
        # Add service coordination endpoint
        @self.existing_app.get("/api/coordination/status")
        async def coordination_status():
            """Get service coordination status"""
            try:
                # Get coordination status from middleware if available
                coordination_middleware = None
                for middleware in self.existing_app.user_middleware:
                    if isinstance(middleware.cls, type) and issubclass(middleware.cls, ServiceCoordinationMiddleware):
                        coordination_middleware = middleware.cls
                        break
                
                if coordination_middleware and hasattr(coordination_middleware, 'get_coordination_status'):
                    status = coordination_middleware.get_coordination_status()
                else:
                    status = {"message": "Service coordination middleware not found"}
                
                return JSONResponse(status_code=200, content=status)
                
            except Exception as e:
                logger.error(f"Failed to get coordination status: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"error": "Failed to get coordination status", "message": str(e)}
                )
    
    def _setup_integrated_lifecycle(self):
        """Setup integrated lifecycle management"""
        
        @asynccontextmanager
        async def integrated_lifespan(app: FastAPI):
            """Integrated application lifespan"""
            try:
                logger.info("Starting integrated VRU API application...")
                
                # Start monitoring
                await comprehensive_monitor.start_monitoring()
                
                # Start WebSocket orchestration
                await websocket_orchestrator.initialize()
                
                # Start VRU orchestration
                await vru_orchestrator.initialize_services()
                
                logger.info("Integrated VRU API application started successfully")
                yield
                
            finally:
                logger.info("Shutting down integrated VRU API application...")
                
                # Shutdown in reverse order
                await vru_orchestrator.shutdown_services()
                await websocket_orchestrator.shutdown()
                await comprehensive_monitor.stop_monitoring()
                
                logger.info("Integrated VRU API application shutdown complete")
        
        # Apply lifespan to existing app
        if hasattr(self.existing_app, 'router'):
            self.existing_app.router.lifespan_context = integrated_lifespan
    
    def _setup_middleware(self):
        """Setup middleware for integrated application"""
        if self.middleware_configured:
            return
        
        app = self.integrated_app
        
        # Add monitoring middleware
        app.add_middleware(MonitoringMiddleware, monitor=comprehensive_monitor)
        
        # Add service coordination middleware
        coordination_config = {
            "load_balancing_strategy": "health_based",
            "circuit_breaker_failure_threshold": 5,
            "circuit_breaker_recovery_timeout": 60,
            "external_ip": self.external_ip
        }
        
        coordination_middleware = create_coordination_middleware(coordination_config)
        app.add_middleware(type(coordination_middleware), config=coordination_config)
        
        # Add request ID middleware
        @app.middleware("http")
        async def add_request_id(request: Request, call_next):
            request.state.request_id = f"req_{uuid.uuid4()}"
            response = await call_next(request)
            response.headers["X-Request-ID"] = request.state.request_id
            return response
        
        # Add external IP headers
        @app.middleware("http")
        async def add_external_ip_headers(request: Request, call_next):
            response = await call_next(request)
            response.headers["X-External-IP"] = self.external_ip
            response.headers["X-VRU-API-Version"] = "1.0.0"
            return response
        
        self.middleware_configured = True
    
    def _setup_cors(self):
        """Setup CORS configuration"""
        app = self.integrated_app
        
        # CORS configuration for external IP access
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "X-External-IP", "X-VRU-API-Version"]
        )
    
    def _add_integration_endpoints(self):
        """Add integration-specific endpoints"""
        app = self.integrated_app
        
        @app.get("/api/integration/health")
        async def integration_health():
            """Integration health check"""
            try:
                health_status = {
                    "integration": "healthy",
                    "external_ip": self.external_ip,
                    "services": {
                        "vru_orchestrator": "healthy" if vru_orchestrator else "unavailable",
                        "websocket_orchestrator": "healthy" if websocket_orchestrator else "unavailable",
                        "monitoring": "healthy" if comprehensive_monitor else "unavailable"
                    },
                    "middleware": {
                        "configured": self.middleware_configured,
                        "cors_enabled": True,
                        "monitoring_enabled": True
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                return JSONResponse(status_code=200, content=health_status)
                
            except Exception as e:
                logger.error(f"Integration health check failed: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "integration": "unhealthy",
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
        
        @app.get("/api/integration/config")
        async def integration_config():
            """Get integration configuration"""
            return {
                "external_ip": self.external_ip,
                "unified_api_mounted": self.existing_app is not None,
                "standalone_mode": self.existing_app is None,
                "middleware_configured": self.middleware_configured,
                "endpoints": {
                    "unified_api": "/vru" if self.existing_app else "/",
                    "websocket": "/api/v1/ws",
                    "camera_websocket": "/api/v1/ws/camera",
                    "health": "/api/v1/health",
                    "integration_health": "/api/integration/health"
                }
            }

class LegacyCompatibilityLayer:
    """Compatibility layer for existing API endpoints"""
    
    def __init__(self, app: FastAPI, orchestrator):
        self.app = app
        self.orchestrator = orchestrator
        self._setup_legacy_routes()
    
    def _setup_legacy_routes(self):
        """Setup routes for backward compatibility"""
        
        # Legacy ML inference endpoints
        @self.app.post("/api/ml/inference")
        async def legacy_ml_inference(request: dict):
            """Legacy ML inference endpoint"""
            try:
                api_request = {
                    "endpoint_type": "ml_inference",
                    "method": "POST",
                    "path": "/process_video",
                    "data": request
                }
                response = await self.orchestrator.process_api_request(api_request)
                return response.data if response.success else {"error": response.error}
            except Exception as e:
                return {"error": str(e)}
        
        # Legacy validation endpoints
        @self.app.post("/api/validation/run")
        async def legacy_validation(request: dict):
            """Legacy validation endpoint"""
            try:
                api_request = {
                    "endpoint_type": "validation",
                    "method": "POST",
                    "path": "/validate_session",
                    "data": request
                }
                response = await self.orchestrator.process_api_request(api_request)
                return response.data if response.success else {"error": response.error}
            except Exception as e:
                return {"error": str(e)}

def integrate_with_existing_main(existing_app: FastAPI, external_ip: str = "155.138.239.131") -> FastAPI:
    """
    Main integration function to be called from existing main.py
    
    Usage in main.py:
    ```python
    from src.main_integration import integrate_with_existing_main
    
    app = FastAPI(...)  # Your existing app
    
    # Integrate unified VRU API
    app = integrate_with_existing_main(app, "155.138.239.131")
    ```
    """
    
    try:
        logger.info(f"Integrating unified VRU API with existing FastAPI app (External IP: {external_ip})")
        
        # Create integration manager
        integration = MainAppIntegration(external_ip)
        
        # Create integrated app
        integrated_app = integration.create_integrated_app(existing_app)
        
        # Add legacy compatibility layer
        legacy_layer = LegacyCompatibilityLayer(integrated_app, vru_orchestrator)
        
        logger.info("Unified VRU API integration completed successfully")
        
        return integrated_app
        
    except Exception as e:
        logger.error(f"Failed to integrate unified VRU API: {str(e)}")
        raise

def create_standalone_vru_app(external_ip: str = "155.138.239.131") -> FastAPI:
    """
    Create standalone unified VRU API application
    
    Usage for standalone deployment:
    ```python
    from src.main_integration import create_standalone_vru_app
    
    app = create_standalone_vru_app("155.138.239.131")
    
    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8000)
    ```
    """
    
    try:
        logger.info(f"Creating standalone unified VRU API application (External IP: {external_ip})")
        
        # Create integration manager
        integration = MainAppIntegration(external_ip)
        
        # Create standalone app
        standalone_app = integration.create_integrated_app(existing_app=None)
        
        logger.info("Standalone unified VRU API application created successfully")
        
        return standalone_app
        
    except Exception as e:
        logger.error(f"Failed to create standalone VRU API: {str(e)}")
        raise

# Configuration and utilities
def configure_logging():
    """Configure logging for integrated application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/tmp/vru_api_integration.log')
        ]
    )
    
    # Set specific log levels
    logging.getLogger('uvicorn').setLevel(logging.INFO)
    logging.getLogger('fastapi').setLevel(logging.INFO)
    logging.getLogger('websockets').setLevel(logging.WARNING)

def validate_integration_environment():
    """Validate environment for integration"""
    required_vars = ['DATABASE_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
    
    # Validate external IP accessibility
    import socket
    try:
        external_ip = "155.138.239.131"
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((external_ip, 80))
        sock.close()
        
        if result == 0:
            logger.info(f"External IP {external_ip} is accessible")
        else:
            logger.warning(f"External IP {external_ip} may not be accessible")
            
    except Exception as e:
        logger.warning(f"Could not validate external IP accessibility: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Configure logging
    configure_logging()
    
    # Validate environment
    validate_integration_environment()
    
    # Create standalone VRU API
    app = create_standalone_vru_app()
    
    # Run application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )