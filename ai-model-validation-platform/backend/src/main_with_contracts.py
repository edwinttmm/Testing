from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import logging
from datetime import datetime

from .api_contracts import api_contract
from .contract_definitions import define_all_contracts, validate_critical_endpoints
from .contract_middleware import setup_contract_validation, ValidationLevel
from .contract_testing import run_contract_tests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with contract initialization"""
    logger.info("🚀 Starting AI Model Validation Platform with Contract Validation")
    
    # Initialize all contracts
    define_all_contracts()
    validate_critical_endpoints()
    
    # Export OpenAPI specification
    export_path = os.getenv("OPENAPI_EXPORT_PATH", "docs/openapi_spec.yaml")
    api_contract.export_to_file(app, export_path, "yaml")
    logger.info(f"📋 Exported OpenAPI specification to {export_path}")
    
    # Run contract tests in development/testing environments
    if os.getenv("ENVIRONMENT") in ["development", "testing"]:
        logger.info("🧪 Running contract validation tests...")
        try:
            test_results = run_contract_tests(app)
            if test_results["failed"] > 0 or test_results["critical_failures"]:
                logger.error(f"❌ Contract tests failed: {test_results['failed']} failures, {len(test_results['critical_failures'])} critical")
                if os.getenv("STRICT_CONTRACT_VALIDATION", "false").lower() == "true":
                    raise Exception("Contract validation failed - preventing startup")
            else:
                logger.info(f"✅ All contract tests passed ({test_results['passed']} tests)")
        except Exception as e:
            logger.error(f"Contract testing error: {e}")
            if os.getenv("STRICT_CONTRACT_VALIDATION", "false").lower() == "true":
                raise
    
    logger.info("🛡️ Contract validation system initialized")
    yield
    
    logger.info("🛑 Shutting down contract validation system")

def create_app_with_contracts() -> FastAPI:
    """Create FastAPI app with comprehensive contract validation"""
    
    # Create FastAPI app
    app = FastAPI(
        title="AI Model Validation Platform",
        version="1.0.0",
        description="AI model validation platform with bulletproof API contracts",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Determine validation level based on environment
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        validation_level = ValidationLevel.COMPATIBLE
    elif environment == "testing":
        validation_level = ValidationLevel.STRICT
    else:
        validation_level = ValidationLevel.STRICT
    
    logger.info(f"Setting up contract validation with {validation_level.value} level")
    
    # Setup contract validation middleware
    contract_middleware = setup_contract_validation(
        app=app,
        validation_level=validation_level,
        enable_monitoring=True
    )
    
    # Add contract management endpoints
    @app.get("/api/contracts/openapi.json")
    async def get_openapi_json():
        """Get OpenAPI specification as JSON"""
        return api_contract.generate_openapi_spec(app)
    
    @app.get("/api/contracts/openapi.yaml")
    async def get_openapi_yaml():
        """Get OpenAPI specification as YAML"""
        import yaml
        spec = api_contract.generate_openapi_spec(app)
        yaml_content = yaml.dump(spec, default_flow_style=False)
        return Response(content=yaml_content, media_type="text/yaml")
    
    @app.get("/api/contracts/version")
    async def get_contract_version():
        """Get current contract version and hash"""
        return {
            "version": api_contract.version,
            "hash": api_contract.get_contract_hash(),
            "total_contracts": len(api_contract.contracts),
            "environment": environment,
            "validation_level": validation_level.value,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.post("/api/contracts/validate")
    async def validate_contracts():
        """Manually trigger contract validation"""
        try:
            results = run_contract_tests(app)
            return {
                "status": "completed",
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Manual contract validation failed: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
    
    @app.get("/api/contracts/compatibility/{other_version}")
    async def check_compatibility(other_version: str):
        """Check compatibility between contract versions"""
        # In a real implementation, this would load and compare contract versions
        return {
            "current_version": api_contract.version,
            "other_version": other_version,
            "compatible": True,  # Placeholder
            "breaking_changes": [],
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Health check with contract status
    @app.get("/health/contracts")
    async def contract_health():
        """Get contract validation health status"""
        health_status = contract_middleware.get_health_status()
        return {
            **health_status,
            "contract_coverage": {
                "total_endpoints": len(api_contract.contracts),
                "critical_endpoints": len(get_critical_endpoints()),
                "validation_level": validation_level.value
            }
        }
    
    # Add error handlers for contract violations
    @app.exception_handler(422)
    async def contract_validation_handler(request: Request, exc: HTTPException):
        """Handle contract validation errors"""
        return JSONResponse(
            status_code=422,
            content={
                "error": "Contract Validation Failed",
                "message": "Request failed API contract validation",
                "details": getattr(exc, 'detail', 'Unknown validation error'),
                "endpoint": f"{request.method} {request.url.path}",
                "timestamp": datetime.utcnow().isoformat(),
                "contract_version": api_contract.version,
                "help": "Check the OpenAPI specification at /api/contracts/openapi.json"
            }
        )
    
    logger.info("✅ FastAPI app with contract validation created successfully")
    return app

# Import and setup existing endpoints from main application
def setup_existing_endpoints(app: FastAPI):
    """Setup existing endpoints from the main application"""
    # This would import and register all existing endpoints
    # from the main application while maintaining contract validation
    
    # Example of how to register existing endpoints:
    # from main import router as main_router
    # app.include_router(main_router)
    
    pass

if __name__ == "__main__":
    import uvicorn
    
    # Create app with contracts
    app = create_app_with_contracts()
    
    # Setup existing endpoints
    setup_existing_endpoints(app)
    
    # Run the application
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"🚀 Starting server on {host}:{port}")
    logger.info(f"📋 OpenAPI docs available at http://{host}:{port}/docs")
    logger.info(f"🛡️ Contract validation enabled")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )