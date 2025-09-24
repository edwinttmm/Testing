#!/usr/bin/env python3
"""
Monitoring Service Startup Script
================================

Standalone script to start the dedicated monitoring service.
Can be run directly or integrated into application startup.
"""

import asyncio
import sys
import logging
import argparse
import signal
from pathlib import Path

# Add parent directory to path to import services
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.monitoring_process_manager import monitoring_process_manager
from services.dedicated_monitoring_service import DedicatedMonitoringService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitoring_service_startup.log')
    ]
)
logger = logging.getLogger(__name__)

class MonitoringServiceStarter:
    """Helper class for starting monitoring service with options"""
    
    def __init__(self):
        self.shutdown_requested = False
        
    async def start_as_subprocess(self, auto_restart: bool = True) -> bool:
        """Start monitoring service as a managed subprocess"""
        try:
            logger.info("🚀 Starting monitoring service as subprocess...")
            
            result = await monitoring_process_manager.start_service(auto_restart=auto_restart)
            
            if result.get("success"):
                logger.info(f"✅ Monitoring service started successfully (PID: {result.get('pid')})")
                return True
            else:
                logger.error(f"❌ Failed to start monitoring service: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting monitoring service: {e}")
            return False
    
    async def start_inline(self) -> bool:
        """Start monitoring service inline (current process becomes the service)"""
        try:
            logger.info("🚀 Starting monitoring service inline...")
            
            # Create and run the monitoring service directly
            service = DedicatedMonitoringService()
            await service.run()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("🔄 Service interrupted by user")
            return True
        except Exception as e:
            logger.error(f"❌ Error running monitoring service: {e}")
            return False
    
    async def wait_for_service(self, max_wait: float = 30.0) -> bool:
        """Wait for monitoring service to become available"""
        try:
            logger.info(f"⏳ Waiting up to {max_wait}s for monitoring service...")
            
            from services.monitoring_service_client import MonitoringServiceClient
            client = MonitoringServiceClient()
            
            available = await client.wait_for_service(max_wait_time=max_wait)
            
            if available:
                logger.info("✅ Monitoring service is available and responsive")
                return True
            else:
                logger.error("❌ Monitoring service did not become available in time")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error waiting for service: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Perform health check on monitoring service"""
        try:
            from services.monitoring_service_client import MonitoringServiceClient
            client = MonitoringServiceClient()
            
            health = await client.health_check()
            status = health.get("service_status", "unknown")
            
            logger.info(f"🔍 Health check result: {status}")
            
            if status in ["healthy", "degraded"]:
                logger.info("✅ Monitoring service is healthy")
                return True
            else:
                logger.warning(f"⚠️ Monitoring service status: {status}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False
    
    async def stop_service(self) -> bool:
        """Stop monitoring service"""
        try:
            logger.info("⏹️ Stopping monitoring service...")
            
            result = await monitoring_process_manager.stop_service()
            
            if result.get("success"):
                logger.info("✅ Monitoring service stopped successfully")
                return True
            else:
                logger.error(f"❌ Failed to stop monitoring service: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error stopping monitoring service: {e}")
            return False
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"📡 Received signal {signum}, initiating shutdown...")
            self.shutdown_requested = True
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

async def main():
    """Main entry point for monitoring service startup"""
    parser = argparse.ArgumentParser(description="Start HIL Monitoring Service")
    parser.add_argument(
        "--mode",
        choices=["subprocess", "inline", "wait", "health", "stop"],
        default="subprocess",
        help="Startup mode (default: subprocess)"
    )
    parser.add_argument(
        "--auto-restart",
        action="store_true",
        default=True,
        help="Enable automatic restart on failure (subprocess mode only)"
    )
    parser.add_argument(
        "--max-wait",
        type=float,
        default=30.0,
        help="Maximum wait time for service availability (wait mode only)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (subprocess mode only)"
    )
    
    args = parser.parse_args()
    
    starter = MonitoringServiceStarter()
    starter.setup_signal_handlers()
    
    success = False
    
    try:
        if args.mode == "subprocess":
            success = await starter.start_as_subprocess(auto_restart=args.auto_restart)
            
            if success and args.daemon:
                logger.info("🔄 Running in daemon mode, press Ctrl+C to stop...")
                try:
                    while not starter.shutdown_requested:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    pass
                
                # Clean shutdown
                await starter.stop_service()
            
        elif args.mode == "inline":
            success = await starter.start_inline()
            
        elif args.mode == "wait":
            success = await starter.wait_for_service(max_wait=args.max_wait)
            
        elif args.mode == "health":
            success = await starter.health_check()
            
        elif args.mode == "stop":
            success = await starter.stop_service()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("🔄 Startup interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())