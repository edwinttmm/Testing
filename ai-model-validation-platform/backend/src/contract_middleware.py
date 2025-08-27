from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, ValidationError
from typing import Dict, Any, List, Optional, Callable
import json
import time
import logging
from datetime import datetime
import asyncio
from contextlib import asynccontextmanager

from .api_contracts import api_contract, ContractViolation, ValidationLevel
from .contract_definitions import define_all_contracts, get_critical_endpoints

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContractValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for real-time API contract validation"""
    
    def __init__(self, 
                 app: FastAPI, 
                 validation_level: ValidationLevel = ValidationLevel.STRICT,
                 enable_monitoring: bool = True,
                 enable_metrics: bool = True):
        super().__init__(app)
        self.validation_level = validation_level
        self.enable_monitoring = enable_monitoring
        self.enable_metrics = enable_metrics
        self.metrics = {
            "total_requests": 0,
            "validation_errors": 0,
            "contract_violations": 0,
            "response_time_ms": [],
            "error_rates": {},
            "endpoint_stats": {}
        }
        self.violation_history: List[ContractViolation] = []
        
        # Initialize contracts
        define_all_contracts()
        logger.info(f"Contract validation middleware initialized with {validation_level} validation")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Main middleware dispatch method"""
        start_time = time.time()
        
        # Extract request information
        method = request.method
        path = request.url.path
        endpoint_key = f"{method} {path}"
        
        # Update metrics
        self.metrics["total_requests"] += 1
        if endpoint_key not in self.metrics["endpoint_stats"]:
            self.metrics["endpoint_stats"][endpoint_key] = {
                "requests": 0,
                "errors": 0,
                "avg_response_time": 0
            }
        
        self.metrics["endpoint_stats"][endpoint_key]["requests"] += 1
        
        try:
            # Validate request
            request_violations = await self._validate_request(request, method, path)
            
            # Handle strict validation failures
            if request_violations and self.validation_level == ValidationLevel.STRICT:
                return await self._handle_validation_error(request_violations, endpoint_key)
            
            # Process request
            response = await call_next(request)
            
            # Validate response
            response_violations = await self._validate_response(response, method, path)
            
            # Log violations but don't block response in compatible/lenient modes
            if response_violations:
                self._log_violations(response_violations, endpoint_key)
                if self.validation_level == ValidationLevel.COMPATIBLE:
                    # Add warning headers
                    response.headers["X-Contract-Warnings"] = str(len(response_violations))
            
            # Add contract metadata to response
            await self._add_contract_headers(response, endpoint_key, start_time)
            
            return response
            
        except Exception as e:
            # Handle middleware errors
            logger.error(f"Contract validation middleware error: {e}")
            self.metrics["endpoint_stats"][endpoint_key]["errors"] += 1
            
            # In production, continue processing even if validation fails
            if self.validation_level == ValidationLevel.LENIENT:
                response = await call_next(request)
                return response
            else:
                raise HTTPException(status_code=500, detail="Contract validation error")
    
    async def _validate_request(self, request: Request, method: str, path: str) -> List[ContractViolation]:
        """Validate incoming request against contract"""
        violations = []
        
        try:
            # Get request body for validation
            request_data = None
            if method in ["POST", "PUT", "PATCH"]:
                content_type = request.headers.get("content-type", "")
                
                if "application/json" in content_type:
                    try:
                        body = await request.body()
                        if body:
                            request_data = json.loads(body)
                    except json.JSONDecodeError as e:
                        violations.append(ContractViolation(
                            endpoint=f"{method} {path}",
                            violation_type="invalid_json",
                            message=f"Invalid JSON in request body: {str(e)}",
                            severity="error"
                        ))
                elif "multipart/form-data" in content_type:
                    # Handle file uploads - basic validation
                    request_data = {"file_upload": True}
            
            # Validate against contract
            contract_violations = api_contract.validate_request(method, path, request_data)
            violations.extend(contract_violations)
            
        except Exception as e:
            violations.append(ContractViolation(
                endpoint=f"{method} {path}",
                violation_type="validation_error",
                message=f"Request validation error: {str(e)}",
                severity="error"
            ))
        
        return violations
    
    async def _validate_response(self, response: Response, method: str, path: str) -> List[ContractViolation]:
        """Validate outgoing response against contract"""
        violations = []
        
        try:
            # Basic response validation
            contract_violations = api_contract.validate_response(
                method, path, response.status_code, None
            )
            violations.extend(contract_violations)
            
            # For critical endpoints, perform additional validation
            endpoint_key = f"{method} {path}"
            critical_endpoints = get_critical_endpoints()
            
            if endpoint_key in critical_endpoints:
                # Enhanced validation for critical endpoints
                if response.status_code >= 500:
                    violations.append(ContractViolation(
                        endpoint=endpoint_key,
                        violation_type="critical_endpoint_error",
                        message=f"Critical endpoint returned server error: {response.status_code}",
                        severity="error"
                    ))
                
                # Check response time for performance SLA
                response_time = getattr(response, '_processing_time', 0)
                if response_time > 5.0:  # 5 second SLA
                    violations.append(ContractViolation(
                        endpoint=endpoint_key,
                        violation_type="performance_violation",
                        message=f"Critical endpoint exceeded performance SLA: {response_time:.2f}s",
                        severity="warning"
                    ))
        
        except Exception as e:
            violations.append(ContractViolation(
                endpoint=f"{method} {path}",
                violation_type="response_validation_error",
                message=f"Response validation error: {str(e)}",
                severity="warning"
            ))
        
        return violations
    
    async def _handle_validation_error(self, violations: List[ContractViolation], endpoint: str) -> JSONResponse:
        """Handle validation errors in strict mode"""
        self.metrics["validation_errors"] += 1
        self.metrics["contract_violations"] += len(violations)
        
        # Store violations for monitoring
        self.violation_history.extend(violations)
        
        # Keep only recent violations (last 1000)
        if len(self.violation_history) > 1000:
            self.violation_history = self.violation_history[-1000:]
        
        error_response = {
            "error": "Contract Validation Failed",
            "message": "Request failed API contract validation",
            "violations": [
                {
                    "type": v.violation_type,
                    "message": v.message,
                    "severity": v.severity,
                    "field": v.field_path
                } for v in violations
            ],
            "endpoint": endpoint,
            "timestamp": datetime.utcnow().isoformat(),
            "contract_version": api_contract.version
        }
        
        return JSONResponse(
            status_code=422,
            content=error_response,
            headers={
                "X-Contract-Validation": "failed",
                "X-Violation-Count": str(len(violations)),
                "X-Contract-Version": api_contract.version
            }
        )
    
    def _log_violations(self, violations: List[ContractViolation], endpoint: str):
        """Log contract violations for monitoring"""
        for violation in violations:
            if violation.severity == "error":
                logger.error(f"Contract violation [{endpoint}]: {violation.message}")
            elif violation.severity == "warning":
                logger.warning(f"Contract warning [{endpoint}]: {violation.message}")
            else:
                logger.info(f"Contract info [{endpoint}]: {violation.message}")
        
        # Store violations for monitoring
        self.violation_history.extend(violations)
        self.metrics["contract_violations"] += len(violations)
    
    async def _add_contract_headers(self, response: Response, endpoint: str, start_time: float):
        """Add contract metadata headers to response"""
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Store processing time for response validation
        setattr(response, '_processing_time', processing_time / 1000)
        
        # Update metrics
        self.metrics["response_time_ms"].append(processing_time)
        if len(self.metrics["response_time_ms"]) > 1000:  # Keep last 1000 response times
            self.metrics["response_time_ms"] = self.metrics["response_time_ms"][-1000:]
        
        # Update endpoint stats
        stats = self.metrics["endpoint_stats"][endpoint]
        stats["avg_response_time"] = (
            (stats["avg_response_time"] * (stats["requests"] - 1) + processing_time) / stats["requests"]
        )
        
        # Add headers
        response.headers["X-Contract-Version"] = api_contract.version
        response.headers["X-Contract-Hash"] = api_contract.get_contract_hash()[:8]
        response.headers["X-Processing-Time"] = f"{processing_time:.2f}ms"
        response.headers["X-Validation-Level"] = self.validation_level.value
        response.headers["X-Contract-Endpoint"] = endpoint
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get validation metrics for monitoring"""
        avg_response_time = (
            sum(self.metrics["response_time_ms"]) / len(self.metrics["response_time_ms"])
            if self.metrics["response_time_ms"] else 0
        )
        
        return {
            "total_requests": self.metrics["total_requests"],
            "validation_errors": self.metrics["validation_errors"],
            "contract_violations": self.metrics["contract_violations"],
            "average_response_time_ms": avg_response_time,
            "error_rate": (
                self.metrics["validation_errors"] / self.metrics["total_requests"]
                if self.metrics["total_requests"] > 0 else 0
            ),
            "endpoints": dict(self.metrics["endpoint_stats"]),
            "recent_violations": [
                {
                    "endpoint": v.endpoint,
                    "type": v.violation_type,
                    "message": v.message,
                    "severity": v.severity
                } for v in self.violation_history[-10:]  # Last 10 violations
            ]
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get contract validation health status"""
        total_requests = self.metrics["total_requests"]
        error_rate = (
            self.metrics["validation_errors"] / total_requests
            if total_requests > 0 else 0
        )
        
        # Determine health status based on error rate
        if error_rate > 0.1:  # More than 10% error rate
            status = "unhealthy"
        elif error_rate > 0.05:  # More than 5% error rate
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "contract_version": api_contract.version,
            "validation_level": self.validation_level.value,
            "total_contracts": len(api_contract.contracts),
            "error_rate": error_rate,
            "recent_violations": len([v for v in self.violation_history if v.severity == "error"]),
            "last_check": datetime.utcnow().isoformat()
        }

class ContractMonitoringService:
    """Service for monitoring contract violations and API health"""
    
    def __init__(self, middleware: ContractValidationMiddleware):
        self.middleware = middleware
        self.alerts_sent = set()
        self.monitoring_active = False
    
    async def start_monitoring(self, check_interval: int = 60):
        """Start continuous contract monitoring"""
        self.monitoring_active = True
        logger.info(f"Started contract monitoring with {check_interval}s interval")
        
        while self.monitoring_active:
            await asyncio.sleep(check_interval)
            await self._check_contract_health()
    
    async def stop_monitoring(self):
        """Stop contract monitoring"""
        self.monitoring_active = False
        logger.info("Stopped contract monitoring")
    
    async def _check_contract_health(self):
        """Check contract health and send alerts if needed"""
        try:
            health = self.middleware.get_health_status()
            
            # Check for critical issues
            if health["status"] == "unhealthy":
                await self._send_alert("CRITICAL", "API contract validation is unhealthy", health)
            elif health["status"] == "degraded":
                await self._send_alert("WARNING", "API contract validation is degraded", health)
            
            # Check for specific endpoint issues
            metrics = self.middleware.get_metrics()
            for endpoint, stats in metrics["endpoints"].items():
                error_rate = stats["errors"] / stats["requests"] if stats["requests"] > 0 else 0
                
                if error_rate > 0.2:  # More than 20% error rate for an endpoint
                    alert_key = f"endpoint_error_{endpoint}"
                    if alert_key not in self.alerts_sent:
                        await self._send_alert(
                            "WARNING", 
                            f"High error rate for endpoint {endpoint}: {error_rate:.1%}",
                            {"endpoint": endpoint, "error_rate": error_rate, "stats": stats}
                        )
                        self.alerts_sent.add(alert_key)
        
        except Exception as e:
            logger.error(f"Error in contract health check: {e}")
    
    async def _send_alert(self, level: str, message: str, details: Dict[str, Any]):
        """Send contract violation alert"""
        alert = {
            "level": level,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "contract_validation"
        }
        
        # In a real implementation, this would send to monitoring systems
        # (e.g., Slack, PagerDuty, email, etc.)
        logger.error(f"CONTRACT ALERT [{level}]: {message}")
        logger.error(f"Alert details: {json.dumps(details, indent=2)}")

def setup_contract_validation(
    app: FastAPI,
    validation_level: ValidationLevel = ValidationLevel.STRICT,
    enable_monitoring: bool = True
) -> ContractValidationMiddleware:
    """Setup complete contract validation system"""
    
    # Add middleware
    middleware = ContractValidationMiddleware(
        app=app,
        validation_level=validation_level,
        enable_monitoring=enable_monitoring
    )
    
    app.add_middleware(
        ContractValidationMiddleware,
        validation_level=validation_level,
        enable_monitoring=enable_monitoring
    )
    
    # Add contract endpoints
    @app.get("/api/contracts/spec")
    async def get_openapi_spec():
        """Get OpenAPI specification"""
        return api_contract.generate_openapi_spec(app)
    
    @app.get("/api/contracts/health")
    async def get_contract_health():
        """Get contract validation health status"""
        return middleware.get_health_status()
    
    @app.get("/api/contracts/metrics")
    async def get_contract_metrics():
        """Get contract validation metrics"""
        return middleware.get_metrics()
    
    @app.get("/api/contracts/violations")
    async def get_recent_violations():
        """Get recent contract violations"""
        return {
            "violations": [
                {
                    "endpoint": v.endpoint,
                    "type": v.violation_type,
                    "message": v.message,
                    "severity": v.severity,
                    "field": v.field_path
                } for v in middleware.violation_history[-50:]  # Last 50 violations
            ],
            "total_count": len(middleware.violation_history)
        }
    
    # Start monitoring service
    if enable_monitoring:
        monitoring_service = ContractMonitoringService(middleware)
        
        @app.on_event("startup")
        async def start_contract_monitoring():
            asyncio.create_task(monitoring_service.start_monitoring())
        
        @app.on_event("shutdown")
        async def stop_contract_monitoring():
            await monitoring_service.stop_monitoring()
    
    logger.info(f"✅ Contract validation system setup complete")
    logger.info(f"📊 Monitoring {len(api_contract.contracts)} API endpoints")
    logger.info(f"🔒 Validation level: {validation_level.value}")
    
    return middleware