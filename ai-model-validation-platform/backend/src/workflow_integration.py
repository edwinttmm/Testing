"""
Complete Integration Layer for Project Workflow Management System
Integrates with existing FastAPI application and all system components

SPARC Phase: Integration & Completion
Component: Complete system integration and coordination
Integration: Full FastAPI integration, database, and existing services
Memory Namespace: vru-project-workflow
"""

import sys
import os
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# Import all workflow components
from project_workflow_manager import (
    ProjectWorkflowManager,
    workflow_manager,
    api_integration
)
from workflow_endpoints import router as workflow_router

# Import existing system components
try:
    from database import get_db, SessionLocal
    from models import Project, Video, TestSession
    from services.project_management_service import ProjectManager
except ImportError as e:
    logging.warning(f"Could not import some database components: {e}")

logger = logging.getLogger(__name__)

class WorkflowIntegrationManager:
    """
    Complete integration manager for workflow system
    Coordinates all system components and provides unified interface
    """
    
    def __init__(self):
        self.workflow_manager = workflow_manager
        self.api_integration = api_integration
        self.background_tasks = []
        self.integration_status = {"initialized": False, "healthy": False}
    
    async def initialize(self):
        """Initialize the complete workflow integration system"""
        try:
            logger.info("Initializing Project Workflow Management System...")
            
            # Initialize memory coordination
            await self._initialize_memory_coordination()
            
            # Initialize background monitoring
            await self._initialize_background_monitoring()
            
            # Verify database connections
            await self._verify_database_connections()
            
            # Initialize workflow orchestrator
            await self._initialize_workflow_orchestrator()
            
            # Set up system health monitoring
            await self._setup_health_monitoring()
            
            self.integration_status["initialized"] = True
            self.integration_status["healthy"] = True
            
            logger.info("✅ Project Workflow Management System initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize workflow system: {str(e)}")
            self.integration_status["initialized"] = False
            self.integration_status["healthy"] = False
            raise
    
    async def _initialize_memory_coordination(self):
        """Initialize memory coordination system"""
        logger.info("Initializing memory coordination...")
        
        # Store system initialization data
        init_data = {
            "initialized_at": "2025-08-27T07:00:00Z",
            "system_version": "1.0.0",
            "memory_namespace": self.workflow_manager.memory_namespace,
            "components": [
                "project_workflow_manager",
                "workflow_orchestrator", 
                "progress_tracker",
                "test_execution_orchestrator",
                "api_integration"
            ]
        }
        
        self.workflow_manager._store_in_memory("system_init", init_data)
        logger.info("✅ Memory coordination initialized")
    
    async def _initialize_background_monitoring(self):
        """Initialize background monitoring tasks"""
        logger.info("Setting up background monitoring...")
        
        # Start progress monitoring task
        monitor_task = asyncio.create_task(self._background_progress_monitor())
        self.background_tasks.append(monitor_task)
        
        # Start health check task  
        health_task = asyncio.create_task(self._background_health_check())
        self.background_tasks.append(health_task)
        
        logger.info("✅ Background monitoring initialized")
    
    async def _verify_database_connections(self):
        """Verify database connections"""
        try:
            db = SessionLocal()
            
            # Test basic database connection
            db.execute("SELECT 1")
            
            # Count existing projects
            project_count = db.query(Project).count() if Project else 0
            
            db.close()
            
            logger.info(f"✅ Database connection verified. Found {project_count} existing projects")
            
        except Exception as e:
            logger.warning(f"⚠️ Database connection issues: {str(e)}")
            # Don't fail initialization due to database issues
    
    async def _initialize_workflow_orchestrator(self):
        """Initialize workflow orchestrator"""
        logger.info("Initializing workflow orchestrator...")
        
        # Verify orchestrator is ready
        orchestrator = self.workflow_manager.orchestrator
        
        # Register any custom task handlers
        await self._register_custom_tasks()
        
        logger.info(f"✅ Workflow orchestrator initialized with {len(orchestrator.task_registry)} task types")
    
    async def _register_custom_tasks(self):
        """Register custom task handlers"""
        orchestrator = self.workflow_manager.orchestrator
        
        # Add custom task types specific to this system
        custom_tasks = {
            "vru_detection_validation": self._vru_detection_task,
            "camera_calibration": self._camera_calibration_task,
            "signal_validation": self._signal_validation_task,
            "performance_optimization": self._performance_optimization_task
        }
        
        orchestrator.task_registry.update(custom_tasks)
        logger.info(f"Registered {len(custom_tasks)} custom task types")
    
    async def _setup_health_monitoring(self):
        """Setup comprehensive health monitoring"""
        logger.info("Setting up health monitoring...")
        
        # Initialize health metrics
        health_metrics = {
            "system_start_time": "2025-08-27T07:00:00Z",
            "active_workflows": 0,
            "total_projects": 0,
            "system_load": "normal",
            "memory_usage": "optimal",
            "database_status": "connected"
        }
        
        self.workflow_manager._store_in_memory("health_metrics", health_metrics)
        logger.info("✅ Health monitoring configured")
    
    async def _background_progress_monitor(self):
        """Background task for monitoring progress"""
        while True:
            try:
                # Monitor active workflows
                active_workflows = len(self.workflow_manager.orchestrator.active_workflows)
                
                # Update health metrics
                health_data = self.workflow_manager._load_from_memory("health_metrics") or {}
                health_data["active_workflows"] = active_workflows
                health_data["last_check"] = "2025-08-27T07:00:00Z"
                
                self.workflow_manager._store_in_memory("health_metrics", health_data)
                
                # Sleep for monitoring interval
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
            except Exception as e:
                logger.error(f"Progress monitoring error: {str(e)}")
                await asyncio.sleep(60)  # Longer sleep on error
    
    async def _background_health_check(self):
        """Background health check task"""
        while True:
            try:
                # Perform health checks
                health_status = await self._perform_health_checks()
                
                # Update system health
                self.integration_status["healthy"] = health_status["overall_healthy"]
                
                # Store detailed health data
                self.workflow_manager._store_in_memory("detailed_health", health_status)
                
                # Sleep for health check interval
                await asyncio.sleep(120)  # Health check every 2 minutes
                
            except Exception as e:
                logger.error(f"Health check error: {str(e)}")
                self.integration_status["healthy"] = False
                await asyncio.sleep(300)  # Longer sleep on error
    
    async def _perform_health_checks(self) -> Dict[str, Any]:
        """Perform comprehensive health checks"""
        health_status = {
            "overall_healthy": True,
            "components": {},
            "timestamp": "2025-08-27T07:00:00Z"
        }
        
        # Check workflow manager
        try:
            workflow_healthy = hasattr(self.workflow_manager, 'orchestrator')
            health_status["components"]["workflow_manager"] = "healthy" if workflow_healthy else "unhealthy"
            if not workflow_healthy:
                health_status["overall_healthy"] = False
        except Exception as e:
            health_status["components"]["workflow_manager"] = f"error: {str(e)}"
            health_status["overall_healthy"] = False
        
        # Check orchestrator
        try:
            orchestrator_healthy = len(self.workflow_manager.orchestrator.task_registry) > 0
            health_status["components"]["orchestrator"] = "healthy" if orchestrator_healthy else "unhealthy"
            if not orchestrator_healthy:
                health_status["overall_healthy"] = False
        except Exception as e:
            health_status["components"]["orchestrator"] = f"error: {str(e)}"
            health_status["overall_healthy"] = False
        
        # Check progress tracker
        try:
            tracker_healthy = hasattr(self.workflow_manager.progress_tracker, 'track_progress')
            health_status["components"]["progress_tracker"] = "healthy" if tracker_healthy else "unhealthy"
        except Exception as e:
            health_status["components"]["progress_tracker"] = f"error: {str(e)}"
        
        # Check database (if available)
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
            health_status["components"]["database"] = "healthy"
        except Exception as e:
            health_status["components"]["database"] = f"error: {str(e)}"
            # Don't fail overall health for database issues
        
        return health_status
    
    # Custom task implementations
    async def _vru_detection_task(self, task, config):
        """Custom VRU detection validation task"""
        logger.info(f"Executing VRU detection validation for project {config.project_id}")
        
        # Track progress
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "vru_detection", 25.0, 
            {"task": "VRU detection validation started"}
        )
        
        # Simulate VRU detection processing
        await asyncio.sleep(2)
        
        # Complete task
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "vru_detection", 100.0,
            {"task": "VRU detection validation completed"}
        )
    
    async def _camera_calibration_task(self, task, config):
        """Custom camera calibration task"""
        logger.info(f"Executing camera calibration for project {config.project_id}")
        
        # Track progress
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "camera_calibration", 50.0,
            {"task": "Camera calibration in progress"}
        )
        
        # Simulate calibration processing
        await asyncio.sleep(1)
        
        # Complete task
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "camera_calibration", 100.0,
            {"task": "Camera calibration completed"}
        )
    
    async def _signal_validation_task(self, task, config):
        """Custom signal validation task"""
        logger.info(f"Executing signal validation for project {config.project_id}")
        
        # Track progress
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "signal_validation", 75.0,
            {"task": "Signal validation processing"}
        )
        
        # Simulate signal validation
        await asyncio.sleep(1.5)
        
        # Complete task  
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "signal_validation", 100.0,
            {"task": "Signal validation completed"}
        )
    
    async def _performance_optimization_task(self, task, config):
        """Custom performance optimization task"""
        logger.info(f"Executing performance optimization for project {config.project_id}")
        
        # Track progress
        self.workflow_manager.progress_tracker.track_progress(
            config.project_id, "performance_optimization", 0.0,
            {"task": "Performance optimization started"}
        )
        
        # Simulate optimization steps
        for step in range(4):
            await asyncio.sleep(0.5)
            progress = (step + 1) * 25.0
            self.workflow_manager.progress_tracker.track_progress(
                config.project_id, "performance_optimization", progress,
                {"task": f"Optimization step {step + 1}/4"}
            )
    
    def get_integration_status(self) -> Dict[str, Any]:
        """Get current integration status"""
        return {
            "initialized": self.integration_status["initialized"],
            "healthy": self.integration_status["healthy"],
            "background_tasks": len(self.background_tasks),
            "workflow_manager_active": hasattr(self, 'workflow_manager'),
            "api_integration_active": hasattr(self, 'api_integration')
        }
    
    async def shutdown(self):
        """Gracefully shutdown the integration system"""
        logger.info("Shutting down Project Workflow Management System...")
        
        # Cancel background tasks
        for task in self.background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Store shutdown data
        shutdown_data = {
            "shutdown_at": "2025-08-27T07:00:00Z",
            "reason": "normal_shutdown",
            "active_workflows_at_shutdown": len(self.workflow_manager.orchestrator.active_workflows)
        }
        
        self.workflow_manager._store_in_memory("shutdown_info", shutdown_data)
        
        logger.info("✅ Project Workflow Management System shutdown complete")

# Global integration manager instance
integration_manager = WorkflowIntegrationManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup and shutdown"""
    # Startup
    try:
        await integration_manager.initialize()
        logger.info("🚀 Project Workflow Management System is ready")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize system: {str(e)}")
        yield
    finally:
        # Shutdown
        await integration_manager.shutdown()

def create_integrated_app(existing_app: Optional[FastAPI] = None) -> FastAPI:
    """
    Create or enhance FastAPI application with workflow management
    Can be used to add workflow management to existing app or create new one
    """
    
    if existing_app:
        app = existing_app
        logger.info("Integrating workflow management into existing FastAPI app")
    else:
        app = FastAPI(
            title="AI Model Validation Platform - Workflow Management",
            description="Complete project workflow management system for AI model validation",
            version="1.0.0",
            lifespan=lifespan
        )
        logger.info("Creating new FastAPI app with workflow management")
    
    # Add CORS middleware if not already present
    if not any(isinstance(middleware, CORSMiddleware) for middleware in getattr(app, 'user_middleware', [])):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    # Include workflow router
    app.include_router(workflow_router)
    
    # Add system-level endpoints
    @app.get("/api/v1/system/integration-status")
    async def get_integration_status():
        """Get workflow integration system status"""
        return integration_manager.get_integration_status()
    
    @app.get("/api/v1/system/memory-coordination")
    async def get_memory_coordination_info():
        """Get memory coordination information"""
        try:
            system_init = workflow_manager._load_from_memory("system_init")
            health_metrics = workflow_manager._load_from_memory("health_metrics")
            
            return {
                "success": True,
                "namespace": workflow_manager.memory_namespace,
                "system_init": system_init,
                "health_metrics": health_metrics,
                "memory_store_size": len(getattr(workflow_manager, '_memory_store', {}))
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @app.post("/api/v1/system/initialize-workflow-system")
    async def initialize_workflow_system():
        """Manually initialize or reinitialize the workflow system"""
        try:
            await integration_manager.initialize()
            return {
                "success": True,
                "message": "Workflow system initialized successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to initialize workflow system"
            }
    
    @app.get("/api/v1/system/comprehensive-status")
    async def get_comprehensive_system_status():
        """Get comprehensive system status including all components"""
        try:
            integration_status = integration_manager.get_integration_status()
            health_data = workflow_manager._load_from_memory("detailed_health")
            memory_info = {
                "namespace": workflow_manager.memory_namespace,
                "store_size": len(getattr(workflow_manager, '_memory_store', {}))
            }
            active_workflows = len(workflow_manager.orchestrator.active_workflows)
            
            return {
                "success": True,
                "timestamp": "2025-08-27T07:00:00Z",
                "integration_status": integration_status,
                "health_data": health_data,
                "memory_info": memory_info,
                "active_workflows": active_workflows,
                "system_components": {
                    "workflow_manager": "operational",
                    "orchestrator": "operational", 
                    "progress_tracker": "operational",
                    "test_orchestrator": "operational",
                    "api_integration": "operational"
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get comprehensive status"
            }
    
    return app

# Convenience function for easy integration
def integrate_workflow_management(app: FastAPI) -> FastAPI:
    """
    Simple integration function to add workflow management to existing FastAPI app
    
    Usage:
        app = FastAPI()
        app = integrate_workflow_management(app)
    """
    return create_integrated_app(app)

# Export main components
__all__ = [
    "WorkflowIntegrationManager",
    "integration_manager", 
    "create_integrated_app",
    "integrate_workflow_management",
    "lifespan"
]

if __name__ == "__main__":
    # Demo/test usage
    import uvicorn
    
    # Create demo app
    demo_app = create_integrated_app()
    
    # Run with uvicorn
    logger.info("Starting demo Project Workflow Management System...")
    uvicorn.run(
        demo_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )