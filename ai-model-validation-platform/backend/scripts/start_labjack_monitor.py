#!/usr/bin/env python3
"""
Start LabJack Monitoring Service
===============================

Script to start the dedicated LabJack monitoring service process.
This service provides exclusive LabJack access to prevent device conflicts.
"""

import asyncio
import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Add backend path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_monitoring_service():
    """Check if monitoring service is already running"""
    try:
        from services.labjack_monitor_client import labjack_monitor_client
        return await labjack_monitor_client.is_monitoring_service_available()
    except Exception:
        return False

def start_monitoring_service():
    """Start the monitoring service as a background process"""
    try:
        service_script = backend_path / "services" / "dedicated_labjack_monitor.py"
        
        # Start the service process
        process = subprocess.Popen([
            sys.executable, str(service_script)
        ], 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True  # Detach from parent
        )
        
        logger.info(f"🚀 Started LabJack monitoring service (PID: {process.pid})")
        return process
        
    except Exception as e:
        logger.error(f"❌ Failed to start monitoring service: {e}")
        return None

async def main():
    """Main entry point"""
    logger.info("🔍 Checking if LabJack monitoring service is running...")
    
    # Check if service is already running
    if await check_monitoring_service():
        logger.info("✅ LabJack monitoring service is already running")
        return
    
    logger.info("🚀 Starting LabJack monitoring service...")
    
    # Start the service
    process = start_monitoring_service()
    if not process:
        logger.error("❌ Failed to start monitoring service")
        sys.exit(1)
    
    # Wait a moment for service to start
    time.sleep(2)
    
    # Check if service is now available
    if await check_monitoring_service():
        logger.info("✅ LabJack monitoring service started successfully")
        
        # Save PID for later management
        pid_file = backend_path / "labjack_monitor.pid"
        with open(pid_file, "w") as f:
            f.write(str(process.pid))
        logger.info(f"📝 PID saved to {pid_file}")
        
    else:
        logger.error("❌ Monitoring service failed to start properly")
        process.terminate()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())