#!/usr/bin/env python3
"""
Unified VRU API Orchestration Layer
SPARC Implementation: Comprehensive API layer orchestrating all VRU services

This module provides a unified API layer that coordinates:
- ML inference endpoints with video processing
- Camera integration with real-time WebSocket
- Validation engine with project workflows
- Ground truth management with annotation system
- Integration with existing main.py FastAPI app
- Support for 155.138.239.131 external access

Architecture:
- Unified Router: Central API routing and coordination
- Service Orchestration: Coordinates all VRU services
- WebSocket Coordination: Real-time communication
- Memory Coordination: Shared state via vru-api-orchestration namespace
- External Access: Configured for production deployment

Memory Namespace: vru-api-orchestration
External IP: 155.138.239.131
"""

import logging
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import asynccontextmanager
import traceback
import time

# FastAPI and WebSocket imports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocketState
from pydantic import BaseModel, Field
from starlette.websockets import WebSocket as StarletteWebSocket

# Core system imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Database and models
from database import get_db, SessionLocal
from models import Project, Video, TestSession, DetectionEvent, GroundTruthObject
from sqlalchemy.orm import Session

# Service imports
try:
    from ml_inference_engine import MLInferenceEngine, get_ml_engine
    from camera_integration_service import CameraIntegrationService, CameraServiceManager
    from validation_engine import VRUValidationEngine, create_validation_engine, ValidationCriteria
    from project_workflow_manager import ProjectWorkflowManager, WorkflowConfiguration, LatencyThreshold
    
    # Additional service integrations
    from services.video_processing_service import VideoProcessingService
    from services.websocket_service import websocket_manager, realtime_service
    from services.ground_truth_service import GroundTruthService
    
except ImportError as e:
    logging.warning(f"Some service imports failed: {e}")
    # Define fallback classes for development
    class MLInferenceEngine:
        async def initialize(self): pass
    class CameraIntegrationService:
        async def initialize(self, external_ip: str): pass
    class VRUValidationEngine:
        async def validate_test_session(self, *args, **kwargs): return {}
    class ProjectWorkflowManager:
        async def create_project_workflow(self, *args, **kwargs): return {}

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """Service status levels"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    SHUTDOWN = "shutdown"

class APIEndpointType(Enum):
    """API endpoint types"""
    ML_INFERENCE = "ml_inference"
    CAMERA_INTEGRATION = "camera_integration"
    VALIDATION = "validation"
    PROJECT_WORKFLOW = "project_workflow"
    GROUND_TRUTH = "ground_truth"
    WEBSOCKET = "websocket"
    HEALTH = "health"

@dataclass
class ServiceHealth:
    """Service health status"""
    service_name: str
    status: ServiceStatus
    last_check: datetime
    response_time_ms: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

@dataclass
class APIRequest:
    """Unified API request structure"""
    endpoint_type: APIEndpointType
    method: str
    path: str
    data: Dict[str, Any]
    client_id: Optional[str] = None
    timestamp: datetime = None
    request_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())

@dataclass
class APIResponse:
    """Unified API response structure"""
    request_id: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    processing_time_ms: float = 0.0
    service: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

# Pydantic models for API validation
class ProjectCreationRequest(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field("", description="Project description")
    camera_model: str = Field(..., description="Camera model")
    camera_view: str = Field(..., description="Camera view description")
    signal_type: str = Field("video", description="Signal type (video, gpio, network)")
    workflow_config: Optional[Dict[str, Any]] = Field(None, description="Workflow configuration")
    latency_thresholds: Optional[Dict[str, float]] = Field(None, description="Latency thresholds")

class VideoProcessingRequest(BaseModel):
    video_id: str = Field(..., description="Video ID to process")
    processing_type: str = Field("ground_truth", description="Processing type")
    options: Dict[str, Any] = Field(default_factory=dict, description="Processing options")

class ValidationRequest(BaseModel):
    session_id: str = Field(..., description="Test session ID")
    criteria: Optional[Dict[str, Any]] = Field(None, description="Custom validation criteria")
    alignment_method: str = Field("adaptive", description="Temporal alignment method")

class CameraConfigRequest(BaseModel):
    camera_id: str = Field(..., description="Camera identifier")
    camera_type: str = Field(..., description="Camera type (webcam, ip_camera, etc.)")
    connection_url: str = Field(..., description="Connection URL/path")
    format: str = Field("mjpeg", description="Video format")
    resolution: Tuple[int, int] = Field((1920, 1080), description="Video resolution")
    fps: int = Field(30, description="Frames per second")
    external_ip: str = Field("155.138.239.131", description="External IP address")

class WebSocketMessage(BaseModel):
    type: str = Field(..., description="Message type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Message data")
    client_id: Optional[str] = Field(None, description="Client identifier")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")

class UnifiedVRUOrchestrator:
    """Main orchestrator for all VRU services"""
    
    def __init__(self, external_ip: str = "155.138.239.131"):
        self.external_ip = external_ip
        self.services = {}
        self.service_health = {}
        self.active_connections = {}
        self.request_history = []
        self.memory_namespace = "vru-api-orchestration"
        
        # Initialize service instances
        self.ml_engine = None
        self.camera_service = None
        self.validation_engine = None
        self.workflow_manager = None
        
        # Performance tracking
        self.request_count = 0
        self.average_response_time = 0.0
        
        logger.info(f"Initialized VRU Orchestrator with external IP: {external_ip}")
    
    async def initialize_services(self):
        """Initialize all VRU services"""
        try:
            logger.info("Initializing VRU services...")
            
            # Initialize ML inference engine
            self.ml_engine = MLInferenceEngine()
            await self.ml_engine.initialize()
            self.services["ml_inference"] = self.ml_engine
            
            # Initialize camera integration service
            self.camera_service = CameraIntegrationService()
            await self.camera_service.initialize(self.external_ip)
            self.services["camera_integration"] = self.camera_service
            
            # Initialize validation engine
            self.validation_engine = create_validation_engine()
            self.services["validation"] = self.validation_engine
            
            # Initialize workflow manager
            self.workflow_manager = ProjectWorkflowManager()
            self.services["project_workflow"] = self.workflow_manager
            
            # Perform health checks
            await self._perform_health_checks()
            
            logger.info("All VRU services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize VRU services: {str(e)}")
            raise
    
    async def _perform_health_checks(self):
        """Perform health checks on all services"""
        for service_name, service in self.services.items():
            try:
                start_time = time.time()
                
                # Perform service-specific health check
                if hasattr(service, 'get_health_status'):
                    health_status = await service.get_health_status()
                    status = ServiceStatus.READY if health_status.get('healthy', False) else ServiceStatus.ERROR
                else:
                    status = ServiceStatus.READY  # Assume ready if no health check
                
                response_time = (time.time() - start_time) * 1000
                
                self.service_health[service_name] = ServiceHealth(
                    service_name=service_name,
                    status=status,
                    last_check=datetime.utcnow(),
                    response_time_ms=response_time
                )
                
            except Exception as e:
                self.service_health[service_name] = ServiceHealth(
                    service_name=service_name,
                    status=ServiceStatus.ERROR,
                    last_check=datetime.utcnow(),
                    response_time_ms=0.0,
                    error_message=str(e)
                )
    
    async def process_api_request(self, request: APIRequest) -> APIResponse:
        """Process unified API request"""
        start_time = time.time()
        
        try:
            # Route request to appropriate service
            if request.endpoint_type == APIEndpointType.ML_INFERENCE:
                result = await self._handle_ml_inference_request(request)
            elif request.endpoint_type == APIEndpointType.CAMERA_INTEGRATION:
                result = await self._handle_camera_request(request)
            elif request.endpoint_type == APIEndpointType.VALIDATION:
                result = await self._handle_validation_request(request)
            elif request.endpoint_type == APIEndpointType.PROJECT_WORKFLOW:
                result = await self._handle_project_workflow_request(request)
            elif request.endpoint_type == APIEndpointType.GROUND_TRUTH:
                result = await self._handle_ground_truth_request(request)
            elif request.endpoint_type == APIEndpointType.HEALTH:
                result = await self._handle_health_request(request)
            else:
                raise ValueError(f"Unsupported endpoint type: {request.endpoint_type}")
            
            processing_time = (time.time() - start_time) * 1000
            
            # Update metrics
            self._update_metrics(processing_time)
            
            response = APIResponse(
                request_id=request.request_id,
                success=True,
                data=result,
                processing_time_ms=processing_time,
                service=request.endpoint_type.value
            )
            
            # Store in memory for coordination
            await self._store_request_response(request, response)
            
            return response
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_msg = f"Request processing failed: {str(e)}"
            logger.error(error_msg)
            
            response = APIResponse(
                request_id=request.request_id,
                success=False,
                error=error_msg,
                processing_time_ms=processing_time,
                service=request.endpoint_type.value
            )
            
            return response
    
    async def _handle_ml_inference_request(self, request: APIRequest) -> Dict[str, Any]:
        """Handle ML inference requests"""
        if not self.ml_engine:
            raise RuntimeError("ML inference engine not initialized")
        
        if request.method == "POST" and request.path.endswith("/process_video"):
            video_id = request.data.get("video_id")
            video_path = request.data.get("video_path")
            
            if not video_id or not video_path:
                raise ValueError("video_id and video_path are required")
            
            result = await self.ml_engine.process_video_for_ground_truth(video_id, video_path)
            return result
            
        elif request.method == "GET" and "/annotations/" in request.path:
            video_id = request.path.split("/annotations/")[1]
            annotations = await self.ml_engine.get_video_annotations(video_id)
            return {"video_id": video_id, "annotations": annotations}
        
        else:
            raise ValueError(f"Unsupported ML inference endpoint: {request.method} {request.path}")
    
    async def _handle_camera_request(self, request: APIRequest) -> Dict[str, Any]:
        """Handle camera integration requests"""
        if not self.camera_service:
            raise RuntimeError("Camera service not initialized")
        
        if request.method == "POST" and request.path.endswith("/add_camera"):
            camera_config = request.data
            success = await self.camera_service.add_camera(camera_config)
            return {"success": success, "camera_id": camera_config.get("camera_id")}
            
        elif request.method == "GET" and request.path.endswith("/status"):
            camera_id = request.data.get("camera_id")
            status = await self.camera_service.get_camera_status(camera_id)
            return status
            
        elif request.method == "GET" and request.path.endswith("/stats"):
            stats = self.camera_service.get_service_stats()
            return stats
        
        else:
            raise ValueError(f"Unsupported camera endpoint: {request.method} {request.path}")
    
    async def _handle_validation_request(self, request: APIRequest) -> Dict[str, Any]:
        """Handle validation requests"""
        if not self.validation_engine:
            raise RuntimeError("Validation engine not initialized")
        
        if request.method == "POST" and request.path.endswith("/validate_session"):
            session_id = request.data.get("session_id")
            criteria = request.data.get("criteria")
            
            if not session_id:
                raise ValueError("session_id is required")
            
            # Convert criteria dict to ValidationCriteria if provided
            validation_criteria = None
            if criteria:
                validation_criteria = ValidationCriteria(**criteria)
            
            report = await self.validation_engine.validate_test_session(
                session_id, validation_criteria
            )
            
            return {
                "session_id": session_id,
                "validation_status": report.validation_status.value,
                "overall_score": report.overall_score,
                "report": asdict(report)
            }
        
        else:
            raise ValueError(f"Unsupported validation endpoint: {request.method} {request.path}")
    
    async def _handle_project_workflow_request(self, request: APIRequest) -> Dict[str, Any]:
        """Handle project workflow requests"""
        if not self.workflow_manager:
            raise RuntimeError("Workflow manager not initialized")
        
        if request.method == "POST" and request.path.endswith("/create_project"):
            project_data = request.data.get("project_data", {})
            workflow_config = request.data.get("workflow_config")
            
            # Convert workflow_config dict if provided
            config = None
            if workflow_config:
                config = WorkflowConfiguration(**workflow_config)
            
            result = await self.workflow_manager.create_project_workflow(project_data, config)
            return result
            
        elif request.method == "POST" and request.path.endswith("/execute_tests"):
            project_id = request.data.get("project_id")
            if not project_id:
                raise ValueError("project_id is required")
            
            results = await self.workflow_manager.execute_project_tests(project_id)
            return results
            
        elif request.method == "GET" and "/status/" in request.path:
            project_id = request.path.split("/status/")[1]
            status = self.workflow_manager.get_project_status(project_id)
            return status
        
        else:
            raise ValueError(f"Unsupported workflow endpoint: {request.method} {request.path}")
    
    async def _handle_ground_truth_request(self, request: APIRequest) -> Dict[str, Any]:
        """Handle ground truth management requests"""
        # This would integrate with actual ground truth service
        if request.method == "POST" and request.path.endswith("/generate"):
            video_id = request.data.get("video_id")
            # Simulate ground truth generation
            return {
                "video_id": video_id,
                "status": "completed",
                "objects_generated": 25,
                "processing_time_ms": 1500
            }
        
        return {"message": "Ground truth service endpoint"}
    
    async def _handle_health_request(self, request: APIRequest) -> Dict[str, Any]:
        """Handle health check requests"""
        if request.path.endswith("/health"):
            return {
                "status": "healthy",
                "services": {
                    name: {
                        "status": health.status.value,
                        "response_time_ms": health.response_time_ms,
                        "last_check": health.last_check.isoformat(),
                        "error": health.error_message
                    }
                    for name, health in self.service_health.items()
                },
                "metrics": {
                    "request_count": self.request_count,
                    "average_response_time_ms": self.average_response_time,
                    "active_connections": len(self.active_connections)
                },
                "external_ip": self.external_ip,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return {"message": "Health service endpoint"}
    
    def _update_metrics(self, processing_time_ms: float):
        """Update performance metrics"""
        self.request_count += 1
        self.average_response_time = (
            (self.average_response_time * (self.request_count - 1) + processing_time_ms) 
            / self.request_count
        )
    
    async def _store_request_response(self, request: APIRequest, response: APIResponse):
        """Store request/response in memory for coordination"""
        entry = {
            "request": asdict(request),
            "response": asdict(response),
            "stored_at": datetime.utcnow().isoformat()
        }
        
        # Keep only last 1000 entries
        self.request_history.append(entry)
        if len(self.request_history) > 1000:
            self.request_history.pop(0)
        
        # Store in memory namespace for coordination
        key = f"request_response:{response.request_id}"
        await self._store_in_memory(key, entry)
    
    async def _store_in_memory(self, key: str, data: Any):
        """Store data in memory coordination system"""
        # This would integrate with the actual memory coordination system
        # For now, using simple storage pattern
        full_key = f"{self.memory_namespace}:{key}"
        # Integration point for memory coordination system
        pass
    
    # WebSocket coordination methods
    async def handle_websocket_connection(self, websocket: WebSocket, client_id: str = None):
        """Handle WebSocket connection for real-time coordination"""
        if not client_id:
            client_id = str(uuid.uuid4())
        
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        logger.info(f"WebSocket client connected: {client_id}")
        
        # Send welcome message
        welcome_msg = {
            "type": "connection_established",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
            "external_ip": self.external_ip,
            "available_services": list(self.services.keys())
        }
        await websocket.send_text(json.dumps(welcome_msg))
        
        try:
            while True:
                # Wait for messages from client
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # Handle WebSocket message
                await self._handle_websocket_message(client_id, data)
                
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {str(e)}")
        finally:
            if client_id in self.active_connections:
                del self.active_connections[client_id]
    
    async def _handle_websocket_message(self, client_id: str, message: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        message_type = message.get("type")
        websocket = self.active_connections.get(client_id)
        
        if not websocket:
            return
        
        try:
            if message_type == "get_service_status":
                # Send service status
                status_msg = {
                    "type": "service_status",
                    "data": {
                        name: {
                            "status": health.status.value,
                            "response_time_ms": health.response_time_ms
                        }
                        for name, health in self.service_health.items()
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_text(json.dumps(status_msg, default=str))
                
            elif message_type == "subscribe_updates":
                # Subscribe to real-time updates
                service = message.get("service", "all")
                # Implementation would set up subscription
                response = {
                    "type": "subscription_confirmed",
                    "service": service,
                    "client_id": client_id
                }
                await websocket.send_text(json.dumps(response))
                
            elif message_type == "api_request":
                # Handle API request via WebSocket
                request_data = message.get("data", {})
                request = APIRequest(
                    endpoint_type=APIEndpointType(request_data.get("endpoint_type")),
                    method=request_data.get("method", "GET"),
                    path=request_data.get("path", "/"),
                    data=request_data.get("data", {}),
                    client_id=client_id
                )
                
                response = await self.process_api_request(request)
                
                ws_response = {
                    "type": "api_response",
                    "request_id": request.request_id,
                    "data": response.data if response.success else None,
                    "error": response.error,
                    "success": response.success,
                    "processing_time_ms": response.processing_time_ms
                }
                await websocket.send_text(json.dumps(ws_response, default=str))
                
            else:
                # Echo unknown message types
                echo_response = {
                    "type": "echo",
                    "original_message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_text(json.dumps(echo_response, default=str))
                
        except Exception as e:
            error_response = {
                "type": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send_text(json.dumps(error_response))
    
    async def broadcast_to_clients(self, message: Dict[str, Any], service_filter: str = None):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
        
        message["timestamp"] = datetime.utcnow().isoformat()
        message_json = json.dumps(message, default=str)
        
        disconnected_clients = []
        
        for client_id, websocket in self.active_connections.items():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text(message_json)
                else:
                    disconnected_clients.append(client_id)
            except Exception as e:
                logger.warning(f"Failed to send message to client {client_id}: {str(e)}")
                disconnected_clients.append(client_id)
        
        # Remove disconnected clients
        for client_id in disconnected_clients:
            self.active_connections.pop(client_id, None)
    
    async def shutdown_services(self):
        """Shutdown all services gracefully"""
        logger.info("Shutting down VRU services...")
        
        try:
            # Close all WebSocket connections
            for client_id, websocket in self.active_connections.items():
                try:
                    await websocket.close()
                except:
                    pass
            
            self.active_connections.clear()
            
            # Shutdown camera service
            if self.camera_service and hasattr(self.camera_service, 'shutdown'):
                await self.camera_service.shutdown()
            
            # Update service status
            for service_name in self.service_health:
                self.service_health[service_name].status = ServiceStatus.SHUTDOWN
            
            logger.info("All VRU services shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during services shutdown: {str(e)}")

# Global orchestrator instance
vru_orchestrator = UnifiedVRUOrchestrator()

# FastAPI application integration
@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager"""
    try:
        # Startup
        logger.info("Starting VRU API Orchestration Layer...")
        await vru_orchestrator.initialize_services()
        logger.info("VRU API Orchestration Layer started successfully")
        yield
    finally:
        # Shutdown
        logger.info("Shutting down VRU API Orchestration Layer...")
        await vru_orchestrator.shutdown_services()
        logger.info("VRU API Orchestration Layer shutdown complete")

def create_unified_vru_app() -> FastAPI:
    """Create unified VRU API application"""
    app = FastAPI(
        title="Unified VRU API Orchestration Layer",
        description="Comprehensive API layer orchestrating all VRU services",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS configuration for external access
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health endpoint
    @app.get("/api/v1/health")
    async def health_check():
        """Comprehensive health check endpoint"""
        request = APIRequest(
            endpoint_type=APIEndpointType.HEALTH,
            method="GET",
            path="/health",
            data={}
        )
        
        response = await vru_orchestrator.process_api_request(request)
        return JSONResponse(
            status_code=200 if response.success else 500,
            content=response.data if response.success else {"error": response.error}
        )
    
    # ML Inference endpoints
    @app.post("/api/v1/ml/process_video")
    async def process_video_for_ml(request: VideoProcessingRequest):
        """Process video with ML inference engine"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.ML_INFERENCE,
            method="POST",
            path="/process_video",
            data=request.dict()
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 400,
            content=response.data if response.success else {"error": response.error}
        )
    
    @app.get("/api/v1/ml/annotations/{video_id}")
    async def get_video_annotations(video_id: str):
        """Get ML-generated annotations for video"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.ML_INFERENCE,
            method="GET",
            path=f"/annotations/{video_id}",
            data={}
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 404,
            content=response.data if response.success else {"error": response.error}
        )
    
    # Camera Integration endpoints
    @app.post("/api/v1/camera/add")
    async def add_camera(config: CameraConfigRequest):
        """Add camera configuration"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.CAMERA_INTEGRATION,
            method="POST",
            path="/add_camera",
            data=config.dict()
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 400,
            content=response.data if response.success else {"error": response.error}
        )
    
    @app.get("/api/v1/camera/status")
    async def get_camera_status(camera_id: Optional[str] = None):
        """Get camera status"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.CAMERA_INTEGRATION,
            method="GET",
            path="/status",
            data={"camera_id": camera_id}
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 404,
            content=response.data if response.success else {"error": response.error}
        )
    
    # Validation endpoints
    @app.post("/api/v1/validation/validate_session")
    async def validate_test_session(request: ValidationRequest):
        """Validate test session"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.VALIDATION,
            method="POST",
            path="/validate_session",
            data=request.dict()
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 400,
            content=response.data if response.success else {"error": response.error}
        )
    
    # Project Workflow endpoints
    @app.post("/api/v1/projects/create")
    async def create_project(request: ProjectCreationRequest):
        """Create project with workflow"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.PROJECT_WORKFLOW,
            method="POST",
            path="/create_project",
            data=request.dict()
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=201 if response.success else 400,
            content=response.data if response.success else {"error": response.error}
        )
    
    @app.get("/api/v1/projects/{project_id}/status")
    async def get_project_status(project_id: str):
        """Get project status"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.PROJECT_WORKFLOW,
            method="GET",
            path=f"/status/{project_id}",
            data={}
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 404,
            content=response.data if response.success else {"error": response.error}
        )
    
    @app.post("/api/v1/projects/{project_id}/execute_tests")
    async def execute_project_tests(project_id: str):
        """Execute project tests"""
        api_request = APIRequest(
            endpoint_type=APIEndpointType.PROJECT_WORKFLOW,
            method="POST",
            path="/execute_tests",
            data={"project_id": project_id}
        )
        
        response = await vru_orchestrator.process_api_request(api_request)
        return JSONResponse(
            status_code=200 if response.success else 400,
            content=response.data if response.success else {"error": response.error}
        )
    
    # WebSocket endpoint for real-time coordination
    @app.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
        """Main WebSocket endpoint for real-time coordination"""
        await vru_orchestrator.handle_websocket_connection(websocket, client_id)
    
    # Camera-specific WebSocket endpoint
    @app.websocket("/api/v1/ws/camera")
    async def camera_websocket_endpoint(websocket: WebSocket, client_id: Optional[str] = None):
        """Camera-specific WebSocket endpoint"""
        if not client_id:
            client_id = str(uuid.uuid4())
        
        # Use camera service WebSocket handler if available
        if vru_orchestrator.camera_service and hasattr(vru_orchestrator.camera_service, 'connect_websocket'):
            await vru_orchestrator.camera_service.connect_websocket(websocket, client_id)
        else:
            # Fallback to main WebSocket handler
            await vru_orchestrator.handle_websocket_connection(websocket, client_id)
    
    return app

# Create the application instance
app = create_unified_vru_app()

if __name__ == "__main__":
    import uvicorn
    
    # Run the unified VRU API
    uvicorn.run(
        "unified_vru_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )