#!/usr/bin/env python3
"""
Backend Startup Fix Script
Ensures all dependencies and configurations are properly set up
"""

import os
import sys
import logging
from pathlib import Path

def setup_logging():
    """Setup basic logging for startup script"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def check_python_version():
    """Check if Python version is compatible"""
    logger = logging.getLogger(__name__)
    if sys.version_info < (3, 8):
        logger.error(f"Python 3.8+ required, found {sys.version}")
        return False
    logger.info(f"Python version: {sys.version}")
    return True

def check_virtual_environment():
    """Check if virtual environment is activated"""
    logger = logging.getLogger(__name__)
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        logger.info("Virtual environment is activated")
        return True
    else:
        logger.warning("Virtual environment not detected")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    logger = logging.getLogger(__name__)
    required_packages = [
        'fastapi', 'uvicorn', 'sqlalchemy', 'redis', 'pydantic'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✓ {package} available")
        except ImportError:
            missing_packages.append(package)
            logger.error(f"✗ {package} missing")
    
    return len(missing_packages) == 0, missing_packages

def check_database_config():
    """Check database configuration"""
    logger = logging.getLogger(__name__)
    try:
        from database import get_database_health
        health = get_database_health()
        if health['status'] == 'healthy':
            logger.info("✓ Database connection healthy")
            return True
        else:
            logger.warning(f"Database health check failed: {health.get('error', 'Unknown')}")
            return False
    except Exception as e:
        logger.error(f"Database configuration check failed: {e}")
        return False

def check_labjack_service():
    """Check LabJack service availability with fallback"""
    logger = logging.getLogger(__name__)
    try:
        from services.labjack_service import LabJackService
        logger.info("✓ LabJack service available")
        return True
    except ImportError:
        logger.warning("LabJack service not available, will use mock")
        try:
            from services.mock_labjack import MockLabJackService
            logger.info("✓ Mock LabJack service available")
            return True
        except ImportError:
            logger.error("Neither LabJack nor Mock service available")
            return False

def create_necessary_directories():
    """Create necessary directories for the application"""
    logger = logging.getLogger(__name__)
    directories = [
        'uploads',
        'logs',
        'temp',
        'screenshots',
        'detection_data'
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        else:
            logger.info(f"Directory exists: {directory}")

def fix_environment_variables():
    """Set up default environment variables if missing"""
    logger = logging.getLogger(__name__)
    default_env = {
        'AIVALIDATION_API_HOST': '0.0.0.0',
        'AIVALIDATION_API_PORT': '8000',
        'AIVALIDATION_LOG_LEVEL': 'INFO',
        'AIVALIDATION_APP_ENVIRONMENT': 'development',
        'DATABASE_URL': 'sqlite:///./dev_database.db'
    }
    
    for key, value in default_env.items():
        if not os.getenv(key):
            os.environ[key] = value
            logger.info(f"Set default environment variable: {key}={value}")

def run_startup_diagnostics():
    """Run complete startup diagnostics"""
    logger = setup_logging()
    logger.info("🚀 Starting backend startup diagnostics...")
    
    all_checks_passed = True
    
    # Check Python version
    if not check_python_version():
        all_checks_passed = False
    
    # Check virtual environment
    check_virtual_environment()  # Warning only
    
    # Fix environment variables
    fix_environment_variables()
    
    # Create directories
    create_necessary_directories()
    
    # Check dependencies
    deps_ok, missing = check_dependencies()
    if not deps_ok:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.info("Run: pip install -r requirements.txt")
        all_checks_passed = False
    
    # Check database
    if not check_database_config():
        logger.warning("Database check failed, but continuing...")
    
    # Check LabJack service
    if not check_labjack_service():
        logger.warning("LabJack service check failed, but continuing...")
    
    if all_checks_passed:
        logger.info("✅ All critical startup checks passed!")
        return True
    else:
        logger.error("❌ Some startup checks failed. Check logs above.")
        return False

if __name__ == "__main__":
    success = run_startup_diagnostics()
    sys.exit(0 if success else 1)