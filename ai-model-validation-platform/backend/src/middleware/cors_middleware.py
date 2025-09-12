"""
CORS Middleware with Auto-Configuration
Automatically configures CORS based on detected environment
Part of the Unified Configuration Architecture
"""

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from typing import List, Dict, Any
from .unified_config import get_unified_config, get_cors_origins

logger = logging.getLogger(__name__)

async def setup_cors_middleware(app: FastAPI) -> None:
    """Setup CORS middleware with auto-detected configuration."""
    
    try:
        config = await get_unified_config()
        cors_origins = config.cors.origins
        
        # Log CORS configuration for debugging
        logger.info("🔒 Setting up CORS middleware:")
        logger.info(f"  Environment: {config.environment}")
        logger.info(f"  Platform: {config.platform}")
        logger.info(f"  Origins: {len(cors_origins)} configured")
        
        if config.features.debug_mode:
            logger.debug("🔍 CORS Origins:")
            for origin in cors_origins:
                logger.debug(f"    - {origin}")
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=config.cors.credentials,
            allow_methods=config.cors.methods,
            allow_headers=config.cors.headers,
            max_age=config.cors.max_age,
            expose_headers=["*"]
        )
        
        logger.info("✅ CORS middleware configured successfully")
        
        # Add CORS testing endpoint
        await _add_cors_test_endpoints(app, config)
        
    except Exception as e:
        logger.error(f"❌ Failed to setup CORS middleware: {e}")
        
        # Fallback CORS configuration
        logger.warning("🔄 Using fallback CORS configuration")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3001"
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"]
        )

async def _add_cors_test_endpoints(app: FastAPI, config):
    """Add CORS testing and debugging endpoints."""
    
    @app.get("/api/cors/test")
    async def test_cors(request: Request):
        """Test CORS configuration and return diagnostic information."""
        
        origin = request.headers.get('origin')
        referer = request.headers.get('referer')
        user_agent = request.headers.get('user-agent')
        
        # Check if origin is allowed
        origin_allowed = origin in config.cors.origins if origin else None
        
        return JSONResponse({
            "message": "CORS test endpoint",
            "status": "success",
            "request_info": {
                "origin": origin,
                "referer": referer,
                "user_agent": user_agent[:100] if user_agent else None,
                "origin_allowed": origin_allowed
            },
            "cors_config": {
                "origins": config.cors.origins,
                "credentials": config.cors.credentials,
                "methods": config.cors.methods,
                "headers": config.cors.headers
            },
            "network_info": {
                "internal_ip": config.network.internal_ip,
                "external_ip": config.network.external_ip,
                "hostname": config.network.hostname
            },
            "environment": {
                "type": config.environment,
                "platform": config.platform,
                "ssl_enabled": config.security.ssl_enabled,
                "debug_mode": config.features.debug_mode
            }
        })
    
    @app.options("/api/cors/test")
    async def test_cors_preflight(request: Request):
        """Handle CORS preflight requests for testing."""
        return Response(
            content="",
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": request.headers.get('origin', '*'),
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Max-Age": str(config.cors.max_age)
            }
        )
    
    if config.features.debug_mode:
        @app.get("/api/cors/debug")
        async def debug_cors_config():
            """Debug endpoint for CORS configuration (development only)."""
            return {
                "cors_configuration": {
                    "origins": config.cors.origins,
                    "credentials": config.cors.credentials, 
                    "methods": config.cors.methods,
                    "headers": config.cors.headers,
                    "max_age": config.cors.max_age,
                    "auto_detect": config.cors.auto_detect
                },
                "network_detection": {
                    "internal_ip": config.network.internal_ip,
                    "external_ip": config.network.external_ip,
                    "hostname": config.network.hostname,
                    "docker_network": config.network.docker_network,
                    "interfaces": config.network.interfaces
                },
                "environment_detection": {
                    "environment": config.environment,
                    "platform": config.platform,
                    "ssl_enabled": config.security.ssl_enabled,
                    "debug_mode": config.features.debug_mode
                },
                "validation_errors": config_manager.get_validation_errors() if hasattr(config, '_validation_errors') else []
            }

class CORSValidationMiddleware:
    """Custom CORS validation middleware for additional security."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        
    async def __call__(self, request: Request, call_next):
        """Validate CORS requests with additional security checks."""
        
        # Get current configuration
        try:
            config = await get_unified_config()
        except Exception as e:
            logger.error(f"Could not get configuration: {e}")
            # Continue without validation in case of config errors
            return await call_next(request)
        
        origin = request.headers.get('origin')
        
        # Skip validation for non-CORS requests
        if not origin:
            return await call_next(request)
        
        # Production security checks
        if config.environment == 'production':
            # Block suspicious origins
            suspicious_patterns = [
                'localhost',
                '127.0.0.1', 
                '192.168.',
                '10.',
                '172.16.',
                '172.17.',
                '172.18.',
                '172.19.',
                '172.20.'
            ]
            
            is_suspicious = any(pattern in origin.lower() for pattern in suspicious_patterns)
            is_allowed = origin in config.cors.origins
            
            if is_suspicious and not is_allowed:
                logger.warning(f"🚨 Blocked suspicious origin in production: {origin}")
                return JSONResponse(
                    status_code=403,
                    content={"error": "Origin not allowed"},
                    headers={"X-Blocked-Origin": origin}
                )
        
        # Continue with request
        response = await call_next(request)
        
        # Add security headers for CORS responses
        if origin in config.cors.origins:
            response.headers["X-CORS-Validated"] = "true"
            response.headers["X-Environment"] = config.environment
            
            if config.security.security_headers_enabled:
                response.headers["X-Content-Type-Options"] = "nosniff"
                response.headers["X-Frame-Options"] = "DENY"
                response.headers["X-XSS-Protection"] = "1; mode=block"
        
        return response

async def add_cors_validation_middleware(app: FastAPI):
    """Add CORS validation middleware to app."""
    app.middleware("http")(CORSValidationMiddleware(app))
    logger.info("✅ CORS validation middleware added")

# Utility functions for CORS management

async def is_origin_allowed(origin: str) -> bool:
    """Check if an origin is allowed by current CORS configuration."""
    try:
        cors_origins = await get_cors_origins()
        return origin in cors_origins
    except Exception:
        return False

async def get_allowed_origins() -> List[str]:
    """Get list of allowed origins."""
    try:
        return await get_cors_origins()
    except Exception:
        return []

async def add_cors_origin(origin: str) -> bool:
    """Dynamically add a CORS origin (development only)."""
    try:
        config = await get_unified_config()
        
        if config.environment != 'development':
            logger.warning("🚨 Cannot dynamically add CORS origin in non-development environment")
            return False
        
        if origin not in config.cors.origins:
            config.cors.origins.append(origin)
            logger.info(f"✅ Added CORS origin: {origin}")
            return True
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to add CORS origin: {e}")
        return False

async def remove_cors_origin(origin: str) -> bool:
    """Dynamically remove a CORS origin (development only)."""
    try:
        config = await get_unified_config()
        
        if config.environment != 'development':
            logger.warning("🚨 Cannot dynamically remove CORS origin in non-development environment")
            return False
        
        if origin in config.cors.origins:
            config.cors.origins.remove(origin)
            logger.info(f"✅ Removed CORS origin: {origin}")
            return True
        
        return True
    except Exception as e:
        logger.error(f"❌ Failed to remove CORS origin: {e}")
        return False

async def validate_cors_configuration() -> Dict[str, Any]:
    """Validate current CORS configuration and return detailed report."""
    try:
        config = await get_unified_config()
        
        validation_report = {
            "valid": True,
            "warnings": [],
            "errors": [],
            "configuration": {
                "origins_count": len(config.cors.origins),
                "origins": config.cors.origins,
                "credentials_enabled": config.cors.credentials,
                "environment": config.environment
            }
        }
        
        # Check for common issues
        if len(config.cors.origins) == 0:
            validation_report["errors"].append("No CORS origins configured")
            validation_report["valid"] = False
        
        if "*" in config.cors.origins and config.environment == 'production':
            validation_report["errors"].append("Wildcard CORS origin in production")
            validation_report["valid"] = False
        
        # Check for localhost in production
        if config.environment == 'production':
            localhost_origins = [o for o in config.cors.origins if 'localhost' in o or '127.0.0.1' in o]
            if localhost_origins:
                validation_report["warnings"].append(f"Localhost origins in production: {localhost_origins}")
        
        # Validate origin formats
        invalid_origins = []
        for origin in config.cors.origins:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(origin)
                if not parsed.scheme or not parsed.netloc:
                    invalid_origins.append(origin)
            except Exception:
                invalid_origins.append(origin)
        
        if invalid_origins:
            validation_report["errors"].append(f"Invalid origin formats: {invalid_origins}")
            validation_report["valid"] = False
        
        return validation_report
        
    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Failed to validate CORS configuration: {e}"],
            "warnings": [],
            "configuration": {}
        }