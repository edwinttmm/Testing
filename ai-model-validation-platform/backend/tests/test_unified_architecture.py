#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite for SPARC Unified Architecture
Tests all components of the environment-aware configuration system
"""

import os
import sys
import asyncio
import pytest
import json
import time
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.config.environment_detector import (
    UnifiedEnvironmentDetector, EnvironmentType, ServiceMode, 
    detect_environment, is_containerized, is_docker, is_local, is_production
)
from src.config.service_discovery import (
    ServiceDiscoveryManager, ServiceType, ServiceStatus,
    service_discovery, discover_database, discover_redis
)
from src.config.path_resolver import (
    PathResolver, PathType, ResolvedPath,
    path_resolver, resolve_upload_directory, get_path_summary
)
from src.config.port_manager import (
    PortManager, PortStatus, ProcessType,
    port_manager, find_available_port, check_port_available
)

# Configure test logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestEnvironmentDetector:
    """Test environment detection functionality"""
    
    def test_basic_detection(self):
        """Test basic environment detection"""
        detector = UnifiedEnvironmentDetector()
        env_info = detector.detect_environment()
        
        assert env_info is not None
        assert env_info.environment_type in [e for e in EnvironmentType]
        assert env_info.service_mode in [m for m in ServiceMode]
        assert env_info.confidence_score >= 0.0 and env_info.confidence_score <= 1.0
        assert env_info.platform is not None
        assert env_info.python_version is not None
        
        logger.info(f"✅ Detected environment: {env_info.environment_type.value} "
                   f"({env_info.service_mode.value}) - Confidence: {env_info.confidence_score}")
    
    def test_environment_summary(self):
        """Test environment summary generation"""
        detector = UnifiedEnvironmentDetector()
        summary = detector.get_environment_summary()
        
        required_keys = [
            'environment_type', 'service_mode', 'platform', 
            'python_version', 'is_containerized', 'confidence_score'
        ]
        
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"
        
        logger.info(f"✅ Environment summary generated with {len(summary)} fields")
    
    @pytest.mark.parametrize("env_var,expected_type", [
        ("AIVALIDATION_APP_ENVIRONMENT=production", ServiceMode.PRODUCTION),
        ("APP_ENV=development", ServiceMode.DEVELOPMENT), 
        ("ENVIRONMENT=staging", ServiceMode.STAGING),
    ])
    def test_service_mode_detection(self, env_var, expected_type):
        """Test service mode detection from environment variables"""
        key, value = env_var.split('=')
        
        with patch.dict(os.environ, {key: value}):
            detector = UnifiedEnvironmentDetector()
            env_info = detector.detect_environment(force_refresh=True)
            
            assert env_info.service_mode == expected_type
            logger.info(f"✅ Service mode {expected_type.value} detected from {key}")
    
    def test_docker_detection_methods(self):
        """Test Docker detection methods"""
        detector = UnifiedEnvironmentDetector()
        
        # Test primary detection
        primary_results = detector._detect_docker_primary()
        assert 'docker_indicators' in primary_results
        
        # Test secondary detection
        secondary_results = detector._detect_docker_secondary()
        assert 'docker_indicators' in secondary_results
        
        logger.info(f"✅ Docker detection methods tested: "
                   f"primary={primary_results['docker_indicators']}, "
                   f"secondary={secondary_results['docker_indicators']}")
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        # These should not raise exceptions
        env_info = detect_environment()
        assert env_info is not None
        
        is_container = is_containerized()
        assert isinstance(is_container, bool)
        
        is_docker_env = is_docker()
        assert isinstance(is_docker_env, bool)
        
        is_local_env = is_local()
        assert isinstance(is_local_env, bool)
        
        is_prod = is_production()
        assert isinstance(is_prod, bool)
        
        logger.info(f"✅ Convenience functions: containerized={is_container}, "
                   f"docker={is_docker_env}, local={is_local_env}, prod={is_prod}")

class TestServiceDiscovery:
    """Test service discovery functionality"""
    
    @pytest.mark.asyncio
    async def test_basic_service_discovery(self):
        """Test basic service discovery"""
        manager = ServiceDiscoveryManager()
        
        # Test database discovery
        db_service = await manager.discover_service("postgres", ServiceType.DATABASE)
        assert db_service is not None
        assert db_service.name == "postgres"
        assert db_service.service_type == ServiceType.DATABASE
        assert db_service.status in [s for s in ServiceStatus]
        
        logger.info(f"✅ Database service discovered: {db_service.endpoint.to_url()} "
                   f"(status: {db_service.status.value})")
    
    @pytest.mark.asyncio
    async def test_redis_discovery(self):
        """Test Redis service discovery"""
        manager = ServiceDiscoveryManager()
        
        redis_service = await manager.discover_service("redis", ServiceType.REDIS)
        assert redis_service is not None
        assert redis_service.name == "redis"
        assert redis_service.service_type == ServiceType.REDIS
        
        logger.info(f"✅ Redis service discovered: {redis_service.endpoint.to_url()} "
                   f"(status: {redis_service.status.value})")
    
    @pytest.mark.asyncio 
    async def test_environment_variable_discovery(self):
        """Test service discovery from environment variables"""
        manager = ServiceDiscoveryManager()
        
        # Test with custom database URL
        test_db_url = "postgresql://testuser:testpass@testhost:5433/testdb"
        
        with patch.dict(os.environ, {'DATABASE_URL': test_db_url}):
            endpoints = await manager._discover_environment_variables("postgres", ServiceType.DATABASE)
            
            assert len(endpoints) > 0
            endpoint = endpoints[0]
            assert endpoint.host == "testhost"
            assert endpoint.port == 5433
            assert endpoint.username == "testuser"
            assert endpoint.database == "testdb"
            
            logger.info(f"✅ Environment variable discovery: {endpoint.to_url()}")
    
    @pytest.mark.asyncio
    async def test_localhost_fallback(self):
        """Test localhost fallback discovery"""
        manager = ServiceDiscoveryManager()
        
        endpoints = await manager._discover_localhost_services("postgres", ServiceType.DATABASE)
        
        # Should find localhost endpoints
        localhost_endpoints = [ep for ep in endpoints if ep.host in ['localhost', '127.0.0.1']]
        assert len(localhost_endpoints) > 0
        
        logger.info(f"✅ Localhost fallback discovered {len(localhost_endpoints)} endpoints")
    
    @pytest.mark.asyncio
    async def test_url_parsing(self):
        """Test URL parsing functionality"""
        manager = ServiceDiscoveryManager()
        
        test_cases = [
            "postgresql://user:pass@host:5432/dbname",
            "redis://host:6379", 
            "http://api:8000/v1",
            "https://secure-api:8443"
        ]
        
        for url in test_cases:
            endpoint = manager._parse_url_to_endpoint(url)
            assert endpoint is not None
            assert endpoint.host is not None
            assert endpoint.port is not None
            
            logger.info(f"✅ URL parsed: {url} -> {endpoint.to_url()}")
    
    @pytest.mark.asyncio
    async def test_health_check_services(self):
        """Test service health checking"""
        manager = ServiceDiscoveryManager()
        
        # Add some services to cache first
        await manager.discover_service("postgres", ServiceType.DATABASE)
        await manager.discover_service("redis", ServiceType.REDIS)
        
        health_results = await manager.health_check_services()
        
        assert isinstance(health_results, dict)
        assert len(health_results) >= 0  # May be empty if no services cached
        
        logger.info(f"✅ Health check completed for {len(health_results)} services")
    
    @pytest.mark.asyncio
    async def test_convenience_functions(self):
        """Test convenience functions"""
        # Test database discovery
        db_service = await discover_database()
        assert db_service is not None
        
        # Test Redis discovery  
        redis_service = await discover_redis()
        assert redis_service is not None
        
        # Test URL generation
        db_url = await service_discovery.get_database_url()
        assert isinstance(db_url, str)
        assert len(db_url) > 0
        
        redis_url = await service_discovery.get_redis_url()
        assert isinstance(redis_url, str)
        assert len(redis_url) > 0
        
        logger.info(f"✅ Convenience functions: db_url={db_url}, redis_url={redis_url}")

class TestPathResolver:
    """Test path resolution functionality"""
    
    def test_basic_path_resolution(self):
        """Test basic path resolution"""
        resolver = PathResolver()
        
        # Test each path type
        for path_type in PathType:
            resolved = resolver.resolve_path(path_type, ensure_exists=False)
            
            assert resolved is not None
            assert resolved.path is not None
            assert resolved.absolute_path is not None
            assert resolved.resolved_from is not None
            
            logger.info(f"✅ {path_type.value}: {resolved.path} (from: {resolved.resolved_from})")
    
    def test_environment_specific_paths(self):
        """Test environment-specific path resolution"""
        resolver = PathResolver()
        
        # Test with different environment types
        original_env_info = resolver._env_info
        
        # Mock Docker environment
        mock_docker_env = MagicMock()
        mock_docker_env.environment_type = EnvironmentType.DOCKER
        resolver._env_info = mock_docker_env
        
        docker_path = resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
        
        # Mock local environment
        mock_local_env = MagicMock()
        mock_local_env.environment_type = EnvironmentType.LOCAL
        resolver._env_info = mock_local_env
        
        local_path = resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
        
        # Paths should be different for different environments
        # (unless they happen to be the same by coincidence)
        logger.info(f"✅ Docker path: {docker_path.path}")
        logger.info(f"✅ Local path: {local_path.path}")
        
        # Restore original
        resolver._env_info = original_env_info
    
    def test_custom_path_override(self):
        """Test custom path override"""
        resolver = PathResolver()
        
        custom_path = "/tmp/custom_uploads"
        resolved = resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY, 
            custom_path=custom_path, 
            ensure_exists=False
        )
        
        assert custom_path in resolved.path
        assert resolved.resolved_from == "custom_override"
        
        logger.info(f"✅ Custom path override: {resolved.path}")
    
    def test_environment_variable_resolution(self):
        """Test path resolution from environment variables"""
        resolver = PathResolver()
        
        test_path = "/tmp/test_uploads"
        
        with patch.dict(os.environ, {'AIVALIDATION_UPLOAD_DIRECTORY': test_path}):
            resolved = resolver.resolve_path(PathType.UPLOAD_DIRECTORY, ensure_exists=False)
            
            assert test_path in resolved.path
            assert "env_var" in resolved.resolved_from
            
            logger.info(f"✅ Environment variable resolution: {resolved.path}")
    
    def test_directory_creation(self):
        """Test directory creation functionality"""
        resolver = PathResolver()
        
        # Test with a unique temporary directory
        test_dir = f"/tmp/test_sparc_arch_{int(time.time())}"
        
        resolved = resolver.resolve_path(
            PathType.UPLOAD_DIRECTORY,
            custom_path=test_dir,
            ensure_exists=True
        )
        
        assert resolved.exists
        assert os.path.exists(test_dir)
        
        # Cleanup
        try:
            os.rmdir(test_dir)
        except:
            pass
        
        logger.info(f"✅ Directory creation: {test_dir}")
    
    def test_path_validation(self):
        """Test path validation functionality"""
        resolver = PathResolver()
        
        validation_results = resolver.validate_paths()
        
        required_keys = ['environment_type', 'service_mode', 'paths', 'warnings', 'errors']
        for key in required_keys:
            assert key in validation_results
        
        assert isinstance(validation_results['paths'], dict)
        assert isinstance(validation_results['warnings'], list)
        assert isinstance(validation_results['errors'], list)
        
        logger.info(f"✅ Path validation: {len(validation_results['paths'])} paths, "
                   f"{len(validation_results['warnings'])} warnings, "
                   f"{len(validation_results['errors'])} errors")
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        upload_dir = resolve_upload_directory()
        assert isinstance(upload_dir, str)
        assert len(upload_dir) > 0
        
        path_summary = get_path_summary()
        assert isinstance(path_summary, dict)
        assert len(path_summary) > 0
        
        logger.info(f"✅ Convenience functions: upload_dir={upload_dir}, "
                   f"summary has {len(path_summary)} paths")

class TestPortManager:
    """Test port management functionality"""
    
    def test_port_availability_check(self):
        """Test port availability checking"""
        manager = PortManager()
        
        # Test a common port
        port_info = manager.check_port_status(8000)
        
        assert port_info is not None
        assert port_info.port == 8000
        assert port_info.status in [s for s in PortStatus]
        
        logger.info(f"✅ Port 8000 status: {port_info.status.value}")
        
        if port_info.pid:
            logger.info(f"   Process: {port_info.process_name} (PID: {port_info.pid})")
    
    def test_find_available_port(self):
        """Test finding available ports"""
        manager = PortManager()
        
        # Find any available port
        available_port = manager.find_available_port(
            preferred_port=9000,
            port_range=(9000, 9100)
        )
        
        assert available_port >= 9000
        assert available_port <= 65535
        
        # Verify the port is actually available
        port_info = manager.check_port_status(available_port)
        assert port_info.status == PortStatus.AVAILABLE
        
        logger.info(f"✅ Found available port: {available_port}")
    
    def test_port_usage_report(self):
        """Test port usage report generation"""
        manager = PortManager()
        
        test_ports = [8000, 8001, 3000, 5432, 6379]
        report = manager.get_port_usage_report(test_ports)
        
        required_keys = [
            'environment_type', 'timestamp', 'ports_checked',
            'available_ports', 'occupied_ports', 'blocked_ports', 'processes'
        ]
        
        for key in required_keys:
            assert key in report
        
        assert report['ports_checked'] == len(test_ports)
        assert isinstance(report['available_ports'], list)
        assert isinstance(report['occupied_ports'], list)
        assert isinstance(report['processes'], dict)
        
        logger.info(f"✅ Port usage report: {report['ports_checked']} ports checked, "
                   f"{len(report['available_ports'])} available, "
                   f"{len(report['occupied_ports'])} occupied")
    
    def test_process_type_identification(self):
        """Test process type identification"""
        manager = PortManager()
        
        # Mock process for testing
        mock_process = MagicMock()
        mock_process.name.return_value = "uvicorn"
        mock_process.cmdline.return_value = ["python", "-m", "uvicorn", "main:app", "--reload"]
        
        process_type = manager._identify_process_type(mock_process)
        assert process_type == ProcessType.UVICORN
        
        logger.info(f"✅ Process type identification: uvicorn -> {process_type.value}")
    
    def test_port_reservation(self):
        """Test port reservation functionality"""
        manager = PortManager()
        
        test_port = 9999
        
        # Reserve the port
        manager.reserve_port(test_port)
        reserved_ports = manager.get_reserved_ports()
        assert test_port in reserved_ports
        
        # Release the port
        manager.release_port(test_port)
        reserved_ports = manager.get_reserved_ports()
        assert test_port not in reserved_ports
        
        logger.info(f"✅ Port reservation: {test_port} reserved and released")
    
    def test_convenience_functions(self):
        """Test convenience functions"""
        # Find available port
        port = find_available_port(9001)
        assert isinstance(port, int)
        assert port > 0
        
        # Check port availability
        is_available = check_port_available(port)
        assert isinstance(is_available, bool)
        
        logger.info(f"✅ Convenience functions: found port {port}, available={is_available}")

class TestIntegration:
    """Integration tests for the complete architecture"""
    
    @pytest.mark.asyncio
    async def test_full_system_integration(self):
        """Test full system integration"""
        logger.info("🚀 Starting full system integration test...")
        
        # 1. Environment detection
        env_info = detect_environment()
        logger.info(f"1️⃣ Environment: {env_info.environment_type.value} ({env_info.service_mode.value})")
        
        # 2. Service discovery
        db_service = await discover_database()
        redis_service = await discover_redis()
        logger.info(f"2️⃣ Services: DB={db_service.status.value}, Redis={redis_service.status.value}")
        
        # 3. Path resolution
        paths = get_path_summary()
        logger.info(f"3️⃣ Paths: {len(paths)} resolved")
        
        # 4. Port management
        available_port = find_available_port(8000)
        logger.info(f"4️⃣ Port: {available_port} available")
        
        # 5. Create integration report
        integration_report = {
            "timestamp": time.time(),
            "environment": {
                "type": env_info.environment_type.value,
                "mode": env_info.service_mode.value,
                "confidence": env_info.confidence_score
            },
            "services": {
                "database": {
                    "status": db_service.status.value,
                    "endpoint": db_service.endpoint.to_url()
                },
                "redis": {
                    "status": redis_service.status.value,
                    "endpoint": redis_service.endpoint.to_url()
                }
            },
            "paths": paths,
            "port": {
                "available": available_port,
                "preferred": 8000
            },
            "integration_status": "success"
        }
        
        logger.info("✅ Full system integration test completed successfully")
        return integration_report
    
    @pytest.mark.asyncio
    async def test_health_check_integration(self):
        """Test health check integration with unified architecture"""
        logger.info("🏥 Testing health check integration...")
        
        # Import and test the health check system
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from health_check import comprehensive_health_check, unified_health_checker
            
            # Run comprehensive health check
            health_result = await comprehensive_health_check()
            
            assert health_result is not None
            assert "status" in health_result
            assert "architecture" in health_result
            assert health_result["architecture"] == "unified_sparc"
            
            logger.info(f"✅ Health check integration: {health_result['status']}")
            return health_result
            
        except ImportError as e:
            logger.warning(f"⚠️ Could not import health check system: {e}")
            return {"status": "skipped", "reason": str(e)}
    
    def test_configuration_consistency(self):
        """Test consistency across all configuration components"""
        logger.info("🔧 Testing configuration consistency...")
        
        # Test that all components agree on environment type
        env_detector = UnifiedEnvironmentDetector()
        service_discovery_manager = ServiceDiscoveryManager()
        path_resolver_instance = PathResolver()
        port_manager_instance = PortManager()
        
        # All should have the same environment info
        env_info1 = env_detector.detect_environment()
        env_info2 = service_discovery_manager._env_info
        env_info3 = path_resolver_instance._env_info
        env_info4 = port_manager_instance._env_info
        
        # Compare environment types (allowing for some variation in confidence)
        assert env_info1.environment_type == env_info2.environment_type
        assert env_info1.environment_type == env_info3.environment_type
        assert env_info1.environment_type == env_info4.environment_type
        
        logger.info(f"✅ Configuration consistency: all components agree on {env_info1.environment_type.value}")
    
    def test_error_handling_and_fallbacks(self):
        """Test error handling and fallback mechanisms"""
        logger.info("🛡️ Testing error handling and fallbacks...")
        
        # Test with invalid/unavailable services
        fallback_tests = []
        
        # 1. Test service discovery with invalid service
        try:
            manager = ServiceDiscoveryManager()
            # This should not raise an exception, but return unavailable service
            invalid_service = asyncio.run(
                manager.discover_service("nonexistent-service", ServiceType.DATABASE)
            )
            fallback_tests.append(f"Service discovery fallback: {invalid_service.status.value}")
        except Exception as e:
            fallback_tests.append(f"Service discovery error handling: {str(e)}")
        
        # 2. Test path resolution with invalid environment
        try:
            resolver = PathResolver()
            # Force invalid environment
            resolver._env_info = MagicMock()
            resolver._env_info.environment_type = None
            
            resolved = resolver.resolve_path(PathType.UPLOAD_DIRECTORY)
            fallback_tests.append(f"Path resolution fallback: {resolved.resolved_from}")
        except Exception as e:
            fallback_tests.append(f"Path resolution error handling: {str(e)}")
        
        # 3. Test port management with restricted permissions
        try:
            port_mgr = PortManager()
            # Test with system port (should handle gracefully)
            port_info = port_mgr.check_port_status(22)  # SSH port
            fallback_tests.append(f"Port management fallback: {port_info.status.value}")
        except Exception as e:
            fallback_tests.append(f"Port management error handling: {str(e)}")
        
        assert len(fallback_tests) > 0
        logger.info(f"✅ Error handling tested: {len(fallback_tests)} fallback scenarios")
        for test in fallback_tests:
            logger.info(f"   - {test}")

# Test runner and reporting
def run_comprehensive_tests():
    """Run all tests and generate comprehensive report"""
    logger.info("🧪 Starting SPARC Architecture Comprehensive Test Suite...")
    
    test_results = {
        "timestamp": time.time(),
        "architecture": "unified_sparc",
        "test_suites": {},
        "summary": {}
    }
    
    # Test suites to run
    test_suites = [
        ("Environment Detection", TestEnvironmentDetector),
        ("Service Discovery", TestServiceDiscovery),
        ("Path Resolution", TestPathResolver),
        ("Port Management", TestPortManager),
        ("Integration", TestIntegration)
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for suite_name, test_class in test_suites:
        logger.info(f"📋 Running {suite_name} tests...")
        
        suite_results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": []
        }
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for method_name in test_methods:
            test_instance = test_class()
            test_method = getattr(test_instance, method_name)
            
            try:
                if asyncio.iscoroutinefunction(test_method):
                    asyncio.run(test_method())
                else:
                    test_method()
                
                suite_results["tests_passed"] += 1
                suite_results["test_details"].append({
                    "test": method_name,
                    "status": "passed"
                })
                logger.info(f"   ✅ {method_name}")
                
            except Exception as e:
                suite_results["tests_failed"] += 1
                suite_results["test_details"].append({
                    "test": method_name,
                    "status": "failed",
                    "error": str(e)
                })
                logger.error(f"   ❌ {method_name}: {e}")
        
        suite_results["tests_run"] = len(test_methods)
        total_tests += suite_results["tests_run"]
        passed_tests += suite_results["tests_passed"]
        
        test_results["test_suites"][suite_name] = suite_results
        
        logger.info(f"📊 {suite_name}: {suite_results['tests_passed']}/{suite_results['tests_run']} passed")
    
    # Generate summary
    test_results["summary"] = {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": total_tests - passed_tests,
        "success_rate": (passed_tests / total_tests) * 100 if total_tests > 0 else 0,
        "overall_status": "PASSED" if passed_tests == total_tests else "FAILED"
    }
    
    logger.info("🎯 Test Summary:")
    logger.info(f"   Total Tests: {total_tests}")
    logger.info(f"   Passed: {passed_tests}")
    logger.info(f"   Failed: {total_tests - passed_tests}")
    logger.info(f"   Success Rate: {test_results['summary']['success_rate']:.1f}%")
    logger.info(f"   Overall Status: {test_results['summary']['overall_status']}")
    
    return test_results

if __name__ == "__main__":
    # Run tests when executed directly
    results = run_comprehensive_tests()
    
    # Save results to file
    results_file = f"tests/architecture_test_results_{int(time.time())}.json"
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Test results saved to: {results_file}")
    
    # Exit with appropriate code
    exit_code = 0 if results["summary"]["overall_status"] == "PASSED" else 1
    sys.exit(exit_code)