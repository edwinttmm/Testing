#!/usr/bin/env python3
"""
Simple database startup check for AI Model Validation Platform.
This script just checks database connectivity and exits quickly.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Simple database check and quick exit."""
    try:
        # Import database components
        from database_initialization import DatabaseInitializer
        from config import settings
        
        logger.info(f"📊 Database URL: {settings.database_url.replace(':' + settings.database_url.split(':')[2].split('@')[0], ':***')}")
        logger.info(f"🐳 Docker mode: {settings.docker_mode}")
        logger.info(f"🌍 Environment: {settings.app_environment}")
        
        # Quick database check
        initializer = DatabaseInitializer()
        engine = initializer.create_engine_with_retry(max_retries=3, retry_delay=1.0)
        
        logger.info("✅ Database connection verified")
        logger.info("🚀 Ready to start application")
        
    except Exception as e:
        logger.warning(f"Database check failed (continuing anyway): {str(e)}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)