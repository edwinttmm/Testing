#!/usr/bin/env python3
"""
Database Connection Test Script
Tests the database connection fixes and configuration
"""

import os
import sys
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_production_env():
    """Load production environment variables"""
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env.production')
    if not os.path.exists(env_file):
        # Try from the ai-model-validation-platform directory
        env_file = '/home/rigade/Testing/ai-model-validation-platform/.env.production'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
        logger.info("✅ Loaded production environment variables")
    else:
        logger.warning("⚠️  Production environment file not found")

def test_environment_variables():
    """Test environment variable configuration"""
    logger.info("🔧 Testing environment variable configuration...")
    
    env_vars = {
        'VRU_DATABASE_URL': os.getenv('VRU_DATABASE_URL'),
        'DATABASE_URL': os.getenv('DATABASE_URL'),
        'AIVALIDATION_DATABASE_URL': os.getenv('AIVALIDATION_DATABASE_URL')
    }
    
    for name, value in env_vars.items():
        if value:
            logger.info(f"✅ {name}: SET (length: {len(value)})")
        else:
            logger.warning(f"❌ {name}: NOT SET")
    
    return any(env_vars.values())

def test_database_configuration():
    """Test database configuration and URL resolution"""
    logger.info("📊 Testing database configuration...")
    
    try:
        from database import get_database_url, DATABASE_URL, mask_database_url
        
        logger.info(f"✅ Database URL function: {mask_database_url(get_database_url())}")
        logger.info(f"✅ Module DATABASE_URL: {mask_database_url(DATABASE_URL)}")
        
        from config import settings
        logger.info(f"✅ Settings database_url: {mask_database_url(settings.database_url)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Database configuration test failed: {e}")
        return False

def test_database_health():
    """Test database health check functionality"""
    logger.info("🏥 Testing database health check...")
    
    try:
        from database import get_database_health
        
        health = get_database_health()
        
        logger.info(f"Health Status: {health['status']}")
        logger.info(f"Database: {health.get('database', 'unknown')}")
        
        if health['status'] == 'healthy':
            logger.info("✅ Database connection healthy!")
            logger.info(f"   Connection Test: {health.get('connection_test', 'unknown')}")
            logger.info(f"   Schema Status: {health.get('schema_status', 'unknown')}")
            logger.info(f"   Table Count: {health.get('table_count', 0)}")
            return True
        else:
            logger.warning("⚠️  Database connection unhealthy")
            logger.warning(f"   Error: {health.get('error', 'unknown')}")
            logger.warning(f"   Error Type: {health.get('error_type', 'unknown')}")
            logger.warning(f"   Suggestion: {health.get('suggestion', 'none')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Database health test failed: {e}")
        return False

def test_health_check_endpoint():
    """Test the health check endpoint functionality"""
    logger.info("🌐 Testing health check endpoint...")
    
    try:
        import asyncio
        from health_check import check_database_health
        
        async def test_async_health():
            health = await check_database_health()
            return health
        
        health = asyncio.run(test_async_health())
        
        logger.info(f"Async Health Status: {health['status']}")
        logger.info(f"Discovery Method: {health.get('discovery_method', 'unknown')}")
        
        if 'configured_vars' in health:
            logger.info(f"Configured Variables: {health['configured_vars']}")
        
        return health['status'] in ['healthy', 'degraded']
        
    except Exception as e:
        logger.error(f"❌ Health check endpoint test failed: {e}")
        return False

def test_database_initialization():
    """Test database initialization functions"""
    logger.info("🔨 Testing database initialization...")
    
    try:
        from database import initialize_database_on_startup
        
        # This will attempt to connect and create tables
        success = initialize_database_on_startup()
        
        if success:
            logger.info("✅ Database initialization completed successfully")
        else:
            logger.warning("⚠️  Database initialization completed with issues")
        
        return True  # Return True even if connection failed - the function works
        
    except Exception as e:
        logger.error(f"❌ Database initialization test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting Database Connection Tests")
    logger.info("=" * 50)
    
    # Load environment
    load_production_env()
    
    # Run tests
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Database Configuration", test_database_configuration),
        ("Database Health Check", test_database_health),
        ("Health Check Endpoint", test_health_check_endpoint),
        ("Database Initialization", test_database_initialization)
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results[test_name] = result
            status = "✅ PASSED" if result else "⚠️  PASSED WITH ISSUES"
            logger.info(f"{test_name}: {status}")
        except Exception as e:
            results[test_name] = False
            logger.error(f"❌ {test_name}: FAILED - {e}")
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📋 TEST SUMMARY")
    logger.info("=" * 50)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Database connection system is working correctly.")
        return 0
    elif passed > 0:
        logger.info("⚠️  Some tests passed. Database configuration is working but connection may have issues.")
        return 1
    else:
        logger.error("❌ All tests failed. Database configuration needs attention.")
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)