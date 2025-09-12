"""
Integration module for Enhanced Test Workflow system
Integrates with existing main.py and provides setup utilities
"""

from fastapi import FastAPI
import logging
from pathlib import Path

# Import the enhanced test workflow components
from src.enhanced_test_api_endpoints import router as enhanced_test_router
from src.enhanced_test_workflow_orchestrator import enhanced_test_orchestrator

logger = logging.getLogger(__name__)

def setup_enhanced_test_workflow(app: FastAPI):
    """
    Setup the Enhanced Test Workflow system
    Call this from main.py to integrate the system
    """
    try:
        # Create necessary directories
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        individual_reports_dir = reports_dir / "individual_videos"
        individual_reports_dir.mkdir(exist_ok=True)
        
        final_reports_dir = reports_dir / "final_reports"
        final_reports_dir.mkdir(exist_ok=True)
        
        # Include the enhanced test router
        app.include_router(enhanced_test_router)
        
        logger.info("Enhanced Test Workflow system initialized successfully")
        
        return {
            "status": "initialized",
            "components": [
                "Enhanced Test Workflow Orchestrator",
                "Real-time WebSocket Communication",
                "Sequential Video Processing",
                "Automated Report Generation",
                "Error Handling & Recovery"
            ],
            "endpoints": [
                "/api/enhanced-test/start-workflow",
                "/api/enhanced-test/workflow/{workflow_id}/status",
                "/api/enhanced-test/workflow/{workflow_id}/results",
                "/api/enhanced-test/workflow/{workflow_id}/ws"
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to setup Enhanced Test Workflow: {e}")
        raise

def get_system_status():
    """Get current system status"""
    try:
        active_workflows = enhanced_test_orchestrator.list_active_workflows()
        
        return {
            "system_status": "operational",
            "active_workflows": len(active_workflows),
            "workflows": active_workflows,
            "orchestrator_ready": True,
            "reports_directory": "reports/",
            "capabilities": [
                "Sequential video processing",
                "Real-time progress tracking",
                "Automated LabJack detection",
                "Ground truth comparison",
                "Individual video reports",
                "Comprehensive final reports",
                "WebSocket live updates",
                "Error handling & recovery"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "system_status": "error",
            "error": str(e)
        }

# Integration instructions for main.py
INTEGRATION_INSTRUCTIONS = """
To integrate the Enhanced Test Workflow system into main.py, add these lines:

1. Import the integration module:
   from src.enhanced_test_integration import setup_enhanced_test_workflow

2. In your FastAPI app initialization (after creating the app):
   # Setup Enhanced Test Workflow
   enhanced_test_info = setup_enhanced_test_workflow(app)
   logger.info(f"Enhanced Test Workflow: {enhanced_test_info}")

3. The system will automatically be available at:
   - REST API endpoints under /api/enhanced-test/
   - WebSocket endpoints for real-time updates
   - Report generation in reports/ directory

4. Frontend integration:
   - Connect to WebSocket: ws://localhost:8000/api/enhanced-test/workflow/{workflow_id}/ws
   - Use POST /api/enhanced-test/start-workflow to begin automated testing
   - Monitor progress through WebSocket events
   - Download results via GET /api/enhanced-test/workflow/{workflow_id}/results
"""