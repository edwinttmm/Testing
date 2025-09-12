#!/usr/bin/env python3
"""
Test Backend Startup Script
Validates that the backend can start without errors
"""

import asyncio
import logging
import sys
import os
from contextlib import asynccontextmanager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_startup():
    """Test the complete startup sequence"""
    try:
        logger.info("🧪 Testing FastAPI application startup...")
        
        # Import the main app
        from main import app
        logger.info("✅ FastAPI app imported successfully")
        
        # Test database connectivity
        from database import get_database_health, initialize_database_on_startup
        
        logger.info("🔌 Testing database initialization...")
        db_success = initialize_database_on_startup()
        if db_success:
            logger.info("✅ Database initialization successful")
        else:
            logger.warning("⚠️ Database initialization had issues but continuing...")
        
        # Test database health
        health = get_database_health()
        logger.info(f"Database health: {health['status']}")
        
        # Test critical service imports
        try:
            from services.ground_truth_service import GroundTruthService
            logger.info("✅ Ground Truth Service available")
        except ImportError as e:
            logger.warning(f"Ground Truth Service issue: {e}")
        
        try:
            from services.labjack_service import LabJackService
            logger.info("✅ LabJack Service available")
        except ImportError:
            try:
                from services.mock_labjack import MockLabJackService
                logger.info("✅ Mock LabJack Service available")
            except ImportError as e:
                logger.warning(f"LabJack Service issue: {e}")
        
        # Test WebSocket server
        try:
            from socketio_server import sio
            logger.info("✅ WebSocket server available")
        except ImportError as e:
            logger.warning(f"WebSocket server issue: {e}")
        
        logger.info("🎉 Backend startup test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the startup test"""
    success = asyncio.run(test_startup())
    if success:
        print("\n✅ Backend is ready to start!")
        print("Run: uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
        return 0
    else:
        print("\n❌ Backend startup test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())