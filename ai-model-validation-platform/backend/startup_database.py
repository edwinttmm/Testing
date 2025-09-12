#!/usr/bin/env python3
"""
Database startup and health check script for AI Model Validation Platform.
This script ensures the database is properly initialized before starting the application.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Dict, Any

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def wait_for_database(max_retries: int = 30, retry_delay: float = 2.0) -> bool:
    """Wait for database to be available."""
    logger.info("🔍 Waiting for database to be available...")
    
    retries = 0
    while retries < max_retries:
        try:
            from database_initialization import DatabaseInitializer
            
            initializer = DatabaseInitializer()
            initializer.create_engine_with_retry(max_retries=1)
            
            logger.info("✅ Database is available")
            return True
            
        except Exception as e:
            retries += 1
            if retries < max_retries:
                logger.info(f"⏳ Database not ready (attempt {retries}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                logger.error(f"❌ Database not available after {max_retries} attempts")
                return False
    
    return False

def run_database_startup() -> bool:
    """Run complete database startup sequence."""
    logger.info("🚀 Starting database initialization sequence...")
    
    try:
        # Step 1: Wait for database to be available
        if not wait_for_database():
            return False
        
        # Step 2: Initialize database
        from database_initialization import initialize_database
        
        if not initialize_database():
            logger.error("❌ Database initialization failed")
            return False
        
        # Step 3: Final health check
        from database_initialization import get_database_health
        
        health = get_database_health()
        if not health.get("overall_healthy"):
            logger.error(f"❌ Database health check failed: {health}")
            return False
        
        logger.info("🎉 Database startup completed successfully!")
        logger.info(f"📊 Health status: {health}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Database startup failed: {e}")
        return False

def print_database_info() -> None:
    """Print database configuration information."""
    db_url = os.getenv('AIVALIDATION_DATABASE_URL') or os.getenv('DATABASE_URL', 'sqlite:///./dev_database.db')
    
    # Mask password for logging
    import re
    masked_url = re.sub(r'://([^:]+):([^@]+)@', r'://\1:***@', db_url)
    
    logger.info(f"📊 Database URL: {masked_url}")
    logger.info(f"🐳 Docker mode: {os.getenv('AIVALIDATION_DOCKER_MODE', 'false')}")
    logger.info(f"🌍 Environment: {os.getenv('AIVALIDATION_APP_ENVIRONMENT', 'development')}")

if __name__ == "__main__":
    """Main startup sequence."""
    try:
        print_database_info()
        
        success = run_database_startup()
        
        if success:
            logger.info("✅ Database startup completed - ready to start application")
            sys.exit(0)
        else:
            logger.error("❌ Database startup failed - application cannot start")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("🛑 Database startup interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error during startup: {e}")
        sys.exit(1)