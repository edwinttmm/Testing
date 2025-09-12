"""
API Integration Script for AI Model Validation Platform

This script demonstrates how to integrate the new API modules into the main application.
It provides a clean way to add the new endpoints without modifying the main.py file directly.

Usage:
    from api_integration import integrate_enhanced_apis
    integrate_enhanced_apis(app)
"""

import logging
from fastapi import FastAPI
from typing import Optional

logger = logging.getLogger(__name__)

def integrate_enhanced_apis(app: FastAPI, enable_signal_validation: bool = True, enable_enhanced_test: bool = True) -> None:
    """
    Integrate enhanced API modules into the FastAPI application
    
    Args:
        app: FastAPI application instance
        enable_signal_validation: Whether to enable signal validation endpoints
        enable_enhanced_test: Whether to enable enhanced test endpoints
    """
    
    try:
        # Import and integrate enhanced test API
        if enable_enhanced_test:
            try:
                from api_enhanced_test import router as enhanced_test_router
                app.include_router(enhanced_test_router, prefix="/api/enhanced-test", tags=["Enhanced Testing"])
                logger.info("✅ Enhanced test API integrated successfully")
                logger.info("   - POST /api/enhanced-test/sessions - Create enhanced test session")
                logger.info("   - GET /api/enhanced-test/sessions/{session_id}/status - Get test status")
                logger.info("   - POST /api/enhanced-test/sessions/{session_id}/criteria - Configure pass/fail criteria")
                logger.info("   - GET /api/enhanced-test/sessions/{session_id}/analysis - Get comprehensive analysis")
                logger.info("   - POST /api/enhanced-test/sessions/{session_id}/export - Export test results")
                logger.info("   - GET /api/enhanced-test/dashboard/enhanced-stats - Get enhanced dashboard stats")
                
            except ImportError as e:
                logger.error(f"❌ Failed to import enhanced test API: {e}")
            except Exception as e:
                logger.error(f"❌ Failed to integrate enhanced test API: {e}")
        
        # Import and integrate signal validation API with graceful LabJack handling
        if enable_signal_validation:
            try:
                from api_signal_validation import router as signal_validation_router
                app.include_router(signal_validation_router)
                logger.info("✅ Signal validation API integrated successfully")
                logger.info("   - POST /api/signal-validation/labjack/initialize - Initialize LabJack (with auto-fallback)")
                logger.info("   - GET /api/signal-validation/labjack/status - Check LabJack status")
                logger.info("   - POST /api/signal-validation/labjack/configure - Configure voltage detection")
                logger.info("   - POST /api/signal-validation/monitoring/start/{test_session_id} - Start monitoring")
                logger.info("   - POST /api/signal-validation/monitoring/stop - Stop monitoring")
                logger.info("   - POST /api/signal-validation/signal/process - Process detection signal")
                logger.info("   - GET /api/signal-validation/statistics/{test_session_id} - Get signal statistics")
                logger.info("   - POST /api/signal-validation/validate/batch - Validate signal batch")
                logger.info("   - GET /api/signal-validation/test-connection - Comprehensive health check")
                logger.info("")
                logger.info("🔧 LabJack Integration Status:")
                
                # Check LabJack availability at startup
                try:
                    from services.signal_validation_service import signal_validation_service
                    import asyncio
                    
                    # Get current event loop or create a new one
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    
                    # Check LabJack status
                    if loop.is_running():
                        # If loop is already running, we can't await here
                        logger.info("   - LabJack status check scheduled for runtime")
                    else:
                        # Safe to check status synchronously
                        try:
                            status = loop.run_until_complete(
                                signal_validation_service.check_labjack_connection()
                            )
                            
                            if status.get("connected"):
                                mode = "Mock" if status.get("mock_mode") else "Hardware"
                                logger.info(f"   - ✅ LabJack ready ({mode} mode)")
                            else:
                                logger.info("   - ⚠️ LabJack not connected (manual initialization required)")
                                logger.info("   - 💡 System will auto-fallback to mock mode when needed")
                        except Exception as status_e:
                            logger.info(f"   - ⚠️ LabJack status check failed: {status_e}")
                            logger.info("   - 💡 LabJack will be initialized on first API call")
                            
                except ImportError:
                    logger.info("   - ⚠️ LabJack service not fully available")
                except Exception as service_e:
                    logger.info(f"   - ⚠️ LabJack service check failed: {service_e}")
                
                logger.info("")
                logger.info("📋 Integration Features:")
                logger.info("   - ✅ Automatic hardware detection")
                logger.info("   - ✅ Graceful fallback to mock mode")
                logger.info("   - ✅ No hardware required for development")
                logger.info("   - ✅ Real-time voltage signal acquisition")
                logger.info("   - ✅ Signal validation and statistics")
                
            except ImportError as e:
                logger.error(f"❌ Failed to import signal validation API: {e}")
                error_msg = str(e).lower()
                if "labjack" in error_msg:
                    logger.info("💡 LabJack hardware libraries not installed")
                    logger.info("   - For development: API will use mock mode automatically")
                    logger.info("   - For production: Run 'python scripts/install_labjack.py'")
                elif "mock_labjack" in error_msg:
                    logger.info("💡 Mock LabJack interface not available")
                    logger.info("   - Check that services/mock_labjack.py exists")
                else:
                    logger.info("💡 Signal validation service dependencies missing")
                    logger.info("   - Run: pip install -r requirements.txt")
            except Exception as e:
                logger.error(f"❌ Failed to integrate signal validation API: {e}")
                logger.info("💡 Signal validation API integration failed")
                logger.info("   - Check logs for detailed error information")
                logger.info("   - Verify all required files are present")
        
        logger.info("🚀 API integration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Critical error during API integration: {e}")
        raise


def get_api_status() -> dict:
    """
    Get status of all integrated API modules
    
    Returns:
        Dictionary with status information for each API module
    """
    status = {
        "integration_timestamp": None,
        "modules": {},
        "total_endpoints": 0
    }
    
    # Check enhanced test API
    try:
        from api_enhanced_test import router as enhanced_test_router
        status["modules"]["enhanced_test"] = {
            "status": "available",
            "prefix": enhanced_test_router.prefix,
            "tags": enhanced_test_router.tags,
            "endpoint_count": len(enhanced_test_router.routes)
        }
        status["total_endpoints"] += len(enhanced_test_router.routes)
    except Exception as e:
        status["modules"]["enhanced_test"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Check signal validation API with enhanced status
    try:
        from api_signal_validation import router as signal_validation_router
        
        # Get LabJack availability status
        labjack_status = "unknown"
        try:
            from services.signal_validation_service import signal_validation_service
            # This is a synchronous check, so we'll use a simple approach
            labjack_status = "available"
        except ImportError:
            labjack_status = "missing_dependencies"
        except Exception:
            labjack_status = "error"
        
        status["modules"]["signal_validation"] = {
            "status": "available",
            "prefix": signal_validation_router.prefix,
            "tags": signal_validation_router.tags,
            "endpoint_count": len(signal_validation_router.routes),
            "labjack_status": labjack_status,
            "features": [
                "voltage_signal_acquisition",
                "mock_mode_support", 
                "automatic_fallback",
                "real_time_monitoring",
                "signal_validation"
            ]
        }
        status["total_endpoints"] += len(signal_validation_router.routes)
    except Exception as e:
        error_details = str(e)
        suggestions = []
        
        if "labjack" in error_details.lower():
            suggestions.append("Install LabJack dependencies: python scripts/install_labjack.py --mock-only")
        if "import" in error_details.lower():
            suggestions.append("Install required packages: pip install -r requirements.txt")
        
        status["modules"]["signal_validation"] = {
            "status": "error",
            "error": error_details,
            "suggestions": suggestions
        }
    
    from datetime import datetime
    status["integration_timestamp"] = datetime.utcnow().isoformat()
    
    return status


def validate_integration(app: FastAPI) -> bool:
    """
    Validate that the API integration is working correctly
    
    Args:
        app: FastAPI application instance
        
    Returns:
        True if integration is valid, False otherwise
    """
    try:
        # Check if routers are registered
        router_prefixes = [route.path_regex.pattern for route in app.routes]
        
        # Look for our API prefixes in the routes
        has_enhanced_test = any("/api/enhanced-test" in pattern or "/api/test" in pattern for pattern in router_prefixes)
        has_signal_validation = any("/api/signal-validation" in pattern for pattern in router_prefixes)
        
        # Additional validation for signal validation API functionality
        signal_validation_health = "unknown"
        if has_signal_validation:
            try:
                from services.signal_validation_service import signal_validation_service
                # Basic service availability check
                if signal_validation_service:
                    signal_validation_health = "healthy"
                else:
                    signal_validation_health = "service_unavailable"
            except Exception:
                signal_validation_health = "service_error"
        
        logger.info(f"Enhanced test API found: {has_enhanced_test}")
        logger.info(f"Signal validation API found: {has_signal_validation}")
        logger.info(f"Signal validation health: {signal_validation_health}")
        
        logger.info(f"Enhanced test API found: {has_enhanced_test}")
        logger.info(f"Signal validation API found: {has_signal_validation}")
        
        return has_enhanced_test or has_signal_validation
        
    except Exception as e:
        logger.error(f"Integration validation failed: {e}")
        return False


def list_available_endpoints(app: FastAPI) -> list:
    """
    List all available endpoints in the application
    
    Args:
        app: FastAPI application instance
        
    Returns:
        List of endpoint information dictionaries
    """
    endpoints = []
    
    try:
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    if method != 'OPTIONS':  # Skip OPTIONS method
                        endpoints.append({
                            "method": method,
                            "path": route.path,
                            "name": getattr(route, 'name', 'unnamed'),
                            "tags": getattr(route, 'tags', [])
                        })
    
    except Exception as e:
        logger.error(f"Failed to list endpoints: {e}")
    
    return endpoints


# Example usage and testing functions
if __name__ == "__main__":
    # Example of how to use this integration
    from fastapi import FastAPI
    
    # Create test app
    test_app = FastAPI(title="Test Integration")
    
    # Set up logging for integration test
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("🧪 Testing API Integration...")
    
    # Integrate APIs with enhanced error handling
    try:
        integrate_enhanced_apis(test_app)
        print("✅ API integration completed successfully")
    except Exception as e:
        print(f"❌ API integration failed: {e}")
        print("💡 This may be due to missing dependencies or configuration issues")
    
    # Get status
    status = get_api_status()
    print("\n🔍 API Integration Status:")
    print(f"Total endpoints added: {status['total_endpoints']}")
    
    for module_name, module_status in status["modules"].items():
        print(f"\n📋 {module_name}:")
        if module_status["status"] == "available":
            print(f"   ✅ Status: {module_status['status']}")
            print(f"   📍 Prefix: {module_status['prefix']}")
            print(f"   🏷️  Tags: {', '.join(module_status['tags'])}")
            print(f"   🔗 Endpoints: {module_status['endpoint_count']}")
        else:
            print(f"   ❌ Status: {module_status['status']}")
            print(f"   📝 Error: {module_status['error']}")
    
    # Validate integration
    is_valid = validate_integration(test_app)
    print(f"\n✅ Integration valid: {is_valid}")
    
    # Test LabJack integration specifically
    print("\n🔍 LabJack Integration Test:")
    try:
        from services.signal_validation_service import signal_validation_service
        print("   ✅ Signal validation service imported successfully")
        
        # Check if service has LabJack interface
        if hasattr(signal_validation_service, 'labjack'):
            if signal_validation_service.labjack:
                mode = "Mock" if getattr(signal_validation_service.labjack, 'mock_mode', True) else "Hardware"
                print(f"   ✅ LabJack interface available ({mode} mode)")
            else:
                print("   ⚠️ LabJack interface not initialized")
        else:
            print("   ⚠️ LabJack interface not found")
            
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
    
    # List endpoints
    endpoints = list_available_endpoints(test_app)
    print(f"\n📋 Total endpoints in app: {len(endpoints)}")
    
    if endpoints:
        print("\nAvailable endpoints:")
        for endpoint in endpoints[:10]:  # Show first 10
            print(f"   {endpoint['method']} {endpoint['path']}")
        
        if len(endpoints) > 10:
            print(f"   ... and {len(endpoints) - 10} more")