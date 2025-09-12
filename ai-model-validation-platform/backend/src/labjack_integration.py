"""
LabJack Integration Module

This module integrates the LabJack API endpoints with the existing FastAPI application.
It provides a simple way to add LabJack functionality to the backend.
"""

import logging
from fastapi import FastAPI

# Import the LabJack API endpoints
from labjack_api_endpoints import router as labjack_router

logger = logging.getLogger(__name__)

def integrate_labjack_api(app: FastAPI) -> None:
    """
    Integrate LabJack API endpoints with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    try:
        # Include the LabJack API router
        app.include_router(labjack_router)
        
        logger.info("✅ LabJack API endpoints integrated successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to integrate LabJack API: {e}")
        # Don't raise exception - allow app to continue without LabJack if needed
        
def setup_labjack_integration(app: FastAPI) -> None:
    """
    Setup LabJack integration with error handling and logging.
    
    Args:
        app: FastAPI application instance
    """
    logger.info("Setting up LabJack integration...")
    
    try:
        # Initialize LabJack service on startup
        @app.on_event("startup")
        async def startup_labjack():
            try:
                from services.labjack_service import initialize_labjack_service
                success = await initialize_labjack_service()
                if success:
                    logger.info("✅ LabJack service initialized successfully")
                else:
                    logger.warning("⚠️ LabJack service initialization failed, running in fallback mode")
            except Exception as e:
                logger.error(f"❌ LabJack service initialization error: {e}")
        
        # Integrate API endpoints
        integrate_labjack_api(app)
        
        logger.info("✅ LabJack integration setup complete")
        
    except Exception as e:
        logger.error(f"❌ LabJack integration setup failed: {e}")

# Export functions
__all__ = ["integrate_labjack_api", "setup_labjack_integration"]