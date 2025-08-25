#!/usr/bin/env python3

"""
Database Connection Test Script
This script tests the database connection from within a Docker container
and provides detailed diagnostics for networking issues.
"""

import os
import sys
import time
import socket
import logging
from typing import Dict, Any, Optional
import traceback

# Add the backend directory to Python path
sys.path.insert(0, '/app')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_dns_resolution(hostname: str, port: int = None) -> bool:
    """Test DNS resolution for a hostname"""
    try:
        logger.info(f"Testing DNS resolution for {hostname}...")
        result = socket.gethostbyname(hostname)
        logger.info(f"✓ DNS resolved {hostname} to {result}")
        return True
    except socket.gaierror as e:
        logger.error(f"✗ DNS resolution failed for {hostname}: {e}")
        return False

def test_tcp_connection(hostname: str, port: int, timeout: int = 10) -> bool:
    """Test TCP connection to hostname:port"""
    try:
        logger.info(f"Testing TCP connection to {hostname}:{port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((hostname, port))
        sock.close()
        
        if result == 0:
            logger.info(f"✓ TCP connection to {hostname}:{port} successful")
            return True
        else:
            logger.error(f"✗ TCP connection to {hostname}:{port} failed (code: {result})")
            return False
    except Exception as e:
        logger.error(f"✗ TCP connection test failed: {e}")
        return False

def test_database_connection() -> Dict[str, Any]:
    """Test database connection using SQLAlchemy"""
    results = {
        'success': False,
        'error': None,
        'connection_info': {},
        'health_info': {}
    }
    
    try:
        # Import database modules
        from database import engine, get_database_health
        from sqlalchemy import text
        
        logger.info("Testing database connection...")
        
        # Get database URL info
        db_url = str(engine.url)
        logger.info(f"Database URL: {db_url.replace(engine.url.password or '', '***')}")
        
        # Test basic connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            logger.info(f"✓ Database query test passed (result: {test_value})")
            
            # Get database version
            if 'postgresql' in db_url.lower():
                version_result = connection.execute(text("SELECT version()"))
                version = version_result.fetchone()[0]
                logger.info(f"PostgreSQL version: {version.split(',')[0]}")
            
        # Get health information
        health_info = get_database_health()
        results['health_info'] = health_info
        logger.info(f"Database health status: {health_info.get('status', 'unknown')}")
        
        results['success'] = True
        logger.info("✓ Database connection test passed")
        
    except Exception as e:
        error_msg = f"Database connection failed: {str(e)}"
        logger.error(f"✗ {error_msg}")
        results['error'] = error_msg
        results['traceback'] = traceback.format_exc()
        
    return results

def test_redis_connection() -> Dict[str, Any]:
    """Test Redis connection"""
    results = {
        'success': False,
        'error': None,
        'connection_info': {}
    }
    
    try:
        import redis
        
        # Get Redis URL from environment
        redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        logger.info(f"Testing Redis connection to: {redis_url}")
        
        # Create Redis client
        r = redis.from_url(redis_url, decode_responses=True)
        
        # Test basic operations
        r.ping()
        logger.info("✓ Redis ping successful")
        
        # Test set/get
        test_key = 'connection_test'
        test_value = 'test_value_' + str(int(time.time()))
        r.set(test_key, test_value, ex=30)  # Expire in 30 seconds
        retrieved_value = r.get(test_key)
        
        if retrieved_value == test_value:
            logger.info("✓ Redis set/get test passed")
            results['success'] = True
        else:
            raise Exception(f"Set/get test failed: expected {test_value}, got {retrieved_value}")
            
        # Clean up
        r.delete(test_key)
        
    except Exception as e:
        error_msg = f"Redis connection failed: {str(e)}"
        logger.error(f"✗ {error_msg}")
        results['error'] = error_msg
        results['traceback'] = traceback.format_exc()
        
    return results

def check_environment_variables() -> Dict[str, str]:
    """Check important environment variables"""
    important_vars = [
        'DATABASE_URL',
        'AIVALIDATION_DATABASE_URL',
        'REDIS_URL',
        'AIVALIDATION_REDIS_URL',
        'POSTGRES_USER',
        'POSTGRES_PASSWORD',
        'POSTGRES_DB',
        'AIVALIDATION_DOCKER_MODE'
    ]
    
    logger.info("Checking environment variables...")
    env_vars = {}
    
    for var in important_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive information
            if 'password' in var.lower() or 'secret' in var.lower():
                masked_value = '***' if value else None
            elif 'url' in var.lower() and '://' in str(value):
                # Mask password in URLs
                masked_value = str(value).split('@')[0].split('://')[0] + '://***@' + str(value).split('@')[1] if '@' in str(value) else str(value)
            else:
                masked_value = value
            env_vars[var] = masked_value
            logger.info(f"  {var}: {masked_value}")
        else:
            logger.warning(f"  {var}: NOT SET")
            env_vars[var] = None
    
    return env_vars

def run_network_diagnostics() -> Dict[str, Any]:
    """Run comprehensive network diagnostics"""
    results = {
        'dns_tests': {},
        'tcp_tests': {},
        'environment': {},
        'database_test': {},
        'redis_test': {}
    }
    
    logger.info("=== Starting Network Diagnostics ===")
    
    # Check environment variables
    results['environment'] = check_environment_variables()
    
    # DNS tests
    hostnames = ['postgres', 'redis', 'backend', 'frontend']
    for hostname in hostnames:
        results['dns_tests'][hostname] = test_dns_resolution(hostname)
    
    # TCP connection tests
    tcp_tests = [
        ('postgres', 5432),
        ('redis', 6379),
        ('backend', 8000),
        ('frontend', 3000)
    ]
    
    for hostname, port in tcp_tests:
        results['tcp_tests'][f'{hostname}:{port}'] = test_tcp_connection(hostname, port)
    
    # Database connection test
    results['database_test'] = test_database_connection()
    
    # Redis connection test
    results['redis_test'] = test_redis_connection()
    
    return results

def print_summary(results: Dict[str, Any]):
    """Print a summary of test results"""
    print("\n" + "="*60)
    print("NETWORK DIAGNOSTICS SUMMARY")
    print("="*60)
    
    # DNS Summary
    dns_results = results.get('dns_tests', {})
    dns_passed = sum(1 for r in dns_results.values() if r)
    print(f"DNS Resolution Tests: {dns_passed}/{len(dns_results)} passed")
    
    # TCP Summary
    tcp_results = results.get('tcp_tests', {})
    tcp_passed = sum(1 for r in tcp_results.values() if r)
    print(f"TCP Connection Tests: {tcp_passed}/{len(tcp_results)} passed")
    
    # Database Summary
    db_test = results.get('database_test', {})
    db_status = "✓ PASSED" if db_test.get('success') else "✗ FAILED"
    print(f"Database Connection: {db_status}")
    if db_test.get('error'):
        print(f"  Error: {db_test['error']}")
    
    # Redis Summary
    redis_test = results.get('redis_test', {})
    redis_status = "✓ PASSED" if redis_test.get('success') else "✗ FAILED"
    print(f"Redis Connection: {redis_status}")
    if redis_test.get('error'):
        print(f"  Error: {redis_test['error']}")
    
    # Overall Status
    all_critical_tests = [
        dns_results.get('postgres', False),
        dns_results.get('redis', False),
        tcp_results.get('postgres:5432', False),
        tcp_results.get('redis:6379', False),
        db_test.get('success', False),
        redis_test.get('success', False)
    ]
    
    overall_success = all(all_critical_tests)
    overall_status = "✓ ALL TESTS PASSED" if overall_success else "✗ SOME TESTS FAILED"
    
    print("-"*60)
    print(f"OVERALL STATUS: {overall_status}")
    print("="*60)
    
    return overall_success

def main():
    """Main function"""
    try:
        # Run diagnostics
        results = run_network_diagnostics()
        
        # Print summary
        success = print_summary(results)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Diagnostic script failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()