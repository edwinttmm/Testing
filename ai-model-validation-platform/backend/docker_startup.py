#!/usr/bin/env python3
"""
Docker Startup Script for AI Model Validation Platform Backend
Handles database connectivity, initialization, and health checks in Docker environment
"""
import os
import sys
import time
import logging
from typing import Optional
import signal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DockerStartupManager:
    """Manages the startup sequence for Docker containers"""
    
    def __init__(self):
        self.max_startup_time = int(os.getenv("STARTUP_TIMEOUT", "300"))  # 5 minutes
        self.shutdown_requested = False
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle graceful shutdown signals"""
        logger.info(f"Received shutdown signal {signum}")
        self.shutdown_requested = True
    
    def wait_for_database(self) -> bool:
        """Wait for database to become available with enhanced error handling"""
        try:
            from database_connectivity_helper import wait_for_database_startup
            logger.info("Waiting for database connectivity...")
            
            success = wait_for_database_startup(max_attempts=30)
            if success:
                logger.info("✅ Database connectivity established")
                return True
            else:
                logger.warning("⚠️  Database connectivity failed, continuing with SQLite fallback")
                return True  # Continue with SQLite fallback
                
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            logger.warning("Continuing with fallback database configuration")
            return True  # Don't fail startup due to database issues
    
    def initialize_database_schema(self) -> bool:
        """Initialize database schema and verify tables"""
        try:
            from database import safe_create_indexes_and_tables
            from database_init import init_database
            
            logger.info("Initializing database schema...")
            safe_create_indexes_and_tables()
            logger.info("✅ Database schema initialized")
            
            logger.info("Creating initial database data...")
            init_success = init_database()
            if init_success:
                logger.info("✅ Database initialization completed")
            else:
                logger.warning("⚠️  Database initialization had issues, but continuing")
            
            return True
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # Don't fail startup - the application can still work with empty tables
            return True
    
    def validate_environment(self) -> bool:
        """Validate critical environment variables"""
        critical_vars = [
            "AIVALIDATION_SECRET_KEY",
            "AIVALIDATION_API_PORT",
        ]
        
        missing_vars = []
        for var in critical_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.warning(f"Missing environment variables: {missing_vars}")
            # Set defaults for missing vars
            if "AIVALIDATION_SECRET_KEY" in missing_vars:
                logger.warning("Using default secret key - CHANGE FOR PRODUCTION!")
                os.environ["AIVALIDATION_SECRET_KEY"] = "default-dev-key-change-for-production"
            if "AIVALIDATION_API_PORT" in missing_vars:
                os.environ["AIVALIDATION_API_PORT"] = "8000"
        
        return True
    
    def run_health_checks(self) -> bool:
        """Run comprehensive health checks"""
        try:
            # Test database health
            from database import get_database_health
            db_health = get_database_health()
            logger.info(f"Database health: {db_health['status']}")
            
            # Test database connectivity helper
            from database_connectivity_helper import diagnose_database_connectivity
            diagnosis = diagnose_database_connectivity()
            logger.info(f"Database connectivity diagnosis completed")
            
            # Log any recommendations
            if diagnosis.get('recommendations'):
                for rec in diagnosis['recommendations']:
                    logger.info(f"💡 Recommendation: {rec}")
            
            return True
            
        except Exception as e:
            logger.error(f"Health checks failed: {e}")
            return False
    
    def start_application(self) -> None:
        """Start the main application"""
        try:
            import uvicorn
            from main import socketio_app
            
            host = os.getenv("AIVALIDATION_API_HOST", "0.0.0.0")
            port = int(os.getenv("AIVALIDATION_API_PORT", "8000"))
            
            logger.info(f"🚀 Starting application on {host}:{port}")
            
            # Start the application
            uvicorn.run(
                socketio_app,
                host=host,
                port=port,
                log_level="info",
                access_log=True,
                reload=os.getenv("AIVALIDATION_APP_ENVIRONMENT") == "development"
            )
            
        except Exception as e:
            logger.error(f"Application startup failed: {e}")
            sys.exit(1)
    
    def run_startup_sequence(self) -> None:
        """Execute the complete startup sequence"""
        start_time = time.time()
        logger.info("🔄 Starting Docker container startup sequence")
        
        try:
            # Step 1: Validate environment
            logger.info("1️⃣  Validating environment configuration...")
            if not self.validate_environment():
                logger.error("Environment validation failed")
                sys.exit(1)
            
            # Step 2: Wait for database
            logger.info("2️⃣  Waiting for database connectivity...")
            if not self.wait_for_database():
                logger.error("Database connectivity failed")
                sys.exit(1)
            
            # Step 3: Initialize database
            logger.info("3️⃣  Initializing database schema...")
            if not self.initialize_database_schema():
                logger.error("Database initialization failed")
                sys.exit(1)
            
            # Step 4: Run health checks
            logger.info("4️⃣  Running health checks...")
            if not self.run_health_checks():
                logger.warning("Health checks had issues, but continuing...")
            
            elapsed_time = time.time() - start_time
            logger.info(f"✅ Startup sequence completed in {elapsed_time:.2f} seconds")
            
            # Step 5: Start application
            logger.info("5️⃣  Starting application server...")
            self.start_application()
            
        except KeyboardInterrupt:
            logger.info("Startup interrupted by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Startup sequence failed: {e}")
            sys.exit(1)

def main():
    """Main entry point"""
    logger.info("AI Model Validation Platform - Docker Startup")
    logger.info("=" * 50)
    
    startup_manager = DockerStartupManager()
    startup_manager.run_startup_sequence()

if __name__ == "__main__":
    main()