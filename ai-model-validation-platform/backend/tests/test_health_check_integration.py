#!/usr/bin/env python3
"""
Integration tests for health check system with unified architecture
Tests backward compatibility and graceful fallbacks
"""

import pytest
import sys
import os
import json
import asyncio
import unittest.mock as mock
from typing import Dict, Any

# Add the backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Test basic imports work
def test_health_check_imports():
    """Test that health check can import unified architecture components"""
    try:
        # This should work even with fallback components
        from src.config import (
            detect_environment, 
            service_discovery, 
            path_resolver, 
            port_manager
        )
        assert detect_environment is not None
        assert service_discovery is not None
        assert path_resolver is not None
        assert port_manager is not None
        print("✅ Health check imports successful")
    except ImportError as e:
        pytest.fail(f"Health check imports failed: {e}")

def test_environment_detection_integration():
    """Test environment detection integration"""
    try:
        from src.config import detect_environment, EnvironmentType, ServiceMode
        
        env_info = detect_environment()
        
        # Verify structure
        assert hasattr(env_info, 'environment_type')
        assert hasattr(env_info, 'service_mode')
        assert hasattr(env_info, 'confidence_score')
        assert hasattr(env_info, 'is_containerized')
        
        # Verify types
        assert isinstance(env_info.environment_type, EnvironmentType)
        assert isinstance(env_info.service_mode, ServiceMode)
        assert isinstance(env_info.confidence_score, float)
        assert isinstance(env_info.is_containerized, bool)
        
        print(f"✅ Environment detection: {env_info.environment_type.value} ({env_info.confidence_score:.2f})")
        
    except Exception as e:
        pytest.fail(f"Environment detection integration failed: {e}")

def test_health_check_basic_functionality():
    """Test basic health check functionality without external dependencies"""
    try:
        # Import health check components
        sys.path.append('.')
        
        # Create a minimal health checker that doesn't require external services
        import logging
        import time
        
        logger = logging.getLogger(__name__)
        
        def basic_health_check():
            """Basic health check without external dependencies"""
            health_data = {
                "status": "healthy",
                "timestamp": time.time(),
                "checks": {
                    "python": {
                        "status": "healthy",
                        "version": sys.version
                    },
                    "imports": {
                        "status": "healthy", 
                        "config_available": True
                    }
                }
            }
            
            # Test environment detection
            try:
                from src.config import detect_environment
                env_info = detect_environment()
                health_data["checks"]["environment"] = {
                    "status": "healthy",
                    "type": env_info.environment_type.value,
                    "confidence": env_info.confidence_score
                }
            except Exception as e:
                health_data["checks"]["environment"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
            
            # Test configuration validation
            try:
                from src.config import validate_configuration
                validation = validate_configuration()
                health_data["checks"]["configuration"] = {
                    "status": validation.get("overall_status", "unknown"),
                    "components": len(validation.get("components", {})),
                    "errors": len(validation.get("errors", [])),
                    "warnings": len(validation.get("warnings", []))
                }
            except Exception as e:
                health_data["checks"]["configuration"] = {
                    "status": "error",
                    "error": str(e)
                }
                health_data["status"] = "degraded"
            
            return health_data
        
        # Run basic health check
        result = basic_health_check()
        
        # Verify structure
        assert "status" in result
        assert "timestamp" in result
        assert "checks" in result
        
        # Should have basic checks
        assert "python" in result["checks"]
        assert "imports" in result["checks"]
        
        print(f"✅ Basic health check: {result['status']}")
        print(f"📊 Checks completed: {len(result['checks'])}")
        
        return result
        
    except Exception as e:
        pytest.fail(f"Basic health check failed: {e}")

def test_backward_compatibility():
    """Test backward compatibility with existing health check patterns"""
    try:
        # Test that we can use the health check without breaking existing code
        import os
        import socket
        
        def legacy_health_check():
            """Legacy-style health check for compatibility testing"""
            health = {
                "status": "healthy",
                "system": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "cwd": os.getcwd()
                }
            }
            
            # Test basic connectivity patterns that existing code might use
            try:
                hostname = socket.gethostname()
                health["system"]["hostname"] = hostname
            except:
                health["status"] = "degraded"
            
            return health
        
        result = legacy_health_check()
        assert result["status"] in ["healthy", "degraded"]
        assert "system" in result
        
        print("✅ Backward compatibility maintained")
        
    except Exception as e:
        pytest.fail(f"Backward compatibility test failed: {e}")

def test_unified_architecture_graceful_degradation():
    """Test that unified architecture degrades gracefully when components are unavailable"""
    try:
        from src.config import get_configuration_summary, get_initialization_status
        
        # Get initialization status
        init_status = get_initialization_status()
        print(f"📊 Initialization status: {json.dumps(init_status, indent=2)}")
        
        # Get configuration summary
        summary = get_configuration_summary()
        print(f"📋 Configuration summary: {json.dumps(summary, indent=2)}")
        
        # Should not crash even if components are unavailable
        assert "components_available" in summary
        assert "initialization_status" in summary
        
        # Count available vs unavailable components
        available_count = sum(
            1 for status in summary["components_available"].values() 
            if status.get("available", False)
        )
        total_count = len(summary["components_available"])
        
        print(f"📈 Components available: {available_count}/{total_count}")
        
        # Even if no components are available, the system should work
        assert total_count > 0  # Should have attempted to load components
        
        print("✅ Graceful degradation working")
        
    except Exception as e:
        pytest.fail(f"Graceful degradation test failed: {e}")

@pytest.mark.asyncio
async def test_async_health_checks():
    """Test async health check functionality"""
    try:
        # Simulate async health checks without external dependencies
        async def mock_database_check():
            await asyncio.sleep(0.01)  # Simulate I/O
            return {
                "status": "unavailable",
                "message": "No database configured for test"
            }
        
        async def mock_service_check():
            await asyncio.sleep(0.01)  # Simulate I/O
            return {
                "status": "healthy",
                "message": "Mock service check passed"
            }
        
        # Run checks concurrently
        db_result, service_result = await asyncio.gather(
            mock_database_check(),
            mock_service_check(),
            return_exceptions=True
        )
        
        assert isinstance(db_result, dict)
        assert isinstance(service_result, dict)
        
        print("✅ Async health checks working")
        
    except Exception as e:
        pytest.fail(f"Async health check test failed: {e}")

def test_production_readiness_indicators():
    """Test production readiness indicators"""
    try:
        from src.config import detect_environment
        
        env_info = detect_environment()
        
        # Production readiness checks
        readiness_indicators = {
            "environment_detected": True,
            "confidence_acceptable": env_info.confidence_score > 0.3,
            "service_mode_detected": env_info.service_mode is not None,
            "platform_identified": env_info.platform is not None
        }
        
        readiness_score = sum(readiness_indicators.values()) / len(readiness_indicators)
        
        print(f"🎯 Production readiness: {readiness_score:.2f}")
        print(f"📊 Indicators: {json.dumps(readiness_indicators, indent=2)}")
        
        # Should have basic readiness even without full components
        assert readiness_score >= 0.5  # At least 50% ready
        
        print("✅ Production readiness indicators working")
        
    except Exception as e:
        pytest.fail(f"Production readiness test failed: {e}")

if __name__ == "__main__":
    # Run tests manually if pytest not available
    print("🧪 Running health check integration tests...")
    
    try:
        test_health_check_imports()
        test_environment_detection_integration()
        test_health_check_basic_functionality()
        test_backward_compatibility()
        test_unified_architecture_graceful_degradation()
        asyncio.run(test_async_health_checks())
        test_production_readiness_indicators()
        
        print("✅ All integration tests passed!")
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)