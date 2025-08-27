from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional, Union, Literal
from datetime import datetime
from pathlib import Path
import json
import yaml
import logging
from enum import Enum
import hashlib
from dataclasses import dataclass
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Contract version for API evolution tracking
API_CONTRACT_VERSION = "1.0.0"
CONTRACT_HASH_ALGORITHM = "sha256"

class ContractValidationError(Exception):
    """Raised when API contract validation fails"""
    def __init__(self, message: str, violations: List[str] = None):
        super().__init__(message)
        self.violations = violations or []

class ValidationLevel(str, Enum):
    """Contract validation strictness levels"""
    STRICT = "strict"         # All contracts must match exactly
    COMPATIBLE = "compatible" # Allow backward compatible changes
    LENIENT = "lenient"      # Allow most changes with warnings

@dataclass
class ContractViolation:
    """Represents a contract validation violation"""
    endpoint: str
    violation_type: str
    message: str
    severity: str  # 'error', 'warning', 'info'
    field_path: Optional[str] = None

class APIContract:
    """Unified API contract management system"""
    
    def __init__(self):
        self.contracts: Dict[str, Dict] = {}
        self.schemas: Dict[str, Any] = {}
        self.validation_rules: Dict[str, List[str]] = {}
        self.version = API_CONTRACT_VERSION
        self.validation_level = ValidationLevel.STRICT
        self.violations: List[ContractViolation] = []
    
    def add_endpoint_contract(self, method: str, path: str, contract: Dict[str, Any]):
        """Add contract specification for an endpoint"""
        key = f"{method.upper()} {path}"
        self.contracts[key] = {
            "method": method.upper(),
            "path": path,
            "request_schema": contract.get("request_schema"),
            "response_schema": contract.get("response_schema"),
            "error_schemas": contract.get("error_schemas", {}),
            "headers": contract.get("headers", {}),
            "parameters": contract.get("parameters", {}),
            "description": contract.get("description", ""),
            "tags": contract.get("tags", []),
            "security": contract.get("security", []),
            "deprecated": contract.get("deprecated", False)
        }
        logger.info(f"Added contract for {key}")
    
    def get_contract_hash(self) -> str:
        """Generate hash of all contracts for change detection"""
        contract_str = json.dumps(self.contracts, sort_keys=True)
        return hashlib.new(CONTRACT_HASH_ALGORITHM, contract_str.encode()).hexdigest()
    
    def validate_request(self, method: str, path: str, request_data: Any) -> List[ContractViolation]:
        """Validate incoming request against contract"""
        violations = []
        key = f"{method.upper()} {path}"
        
        if key not in self.contracts:
            violations.append(ContractViolation(
                endpoint=key,
                violation_type="unknown_endpoint",
                message=f"No contract found for {key}",
                severity="error"
            ))
            return violations
        
        contract = self.contracts[key]
        request_schema = contract.get("request_schema")
        
        if request_schema and request_data is not None:
            violations.extend(self._validate_against_schema(
                data=request_data,
                schema=request_schema,
                endpoint=key,
                schema_type="request"
            ))
        
        return violations
    
    def validate_response(self, method: str, path: str, status_code: int, response_data: Any) -> List[ContractViolation]:
        """Validate outgoing response against contract"""
        violations = []
        key = f"{method.upper()} {path}"
        
        if key not in self.contracts:
            return violations  # Skip validation for unknown endpoints in lenient mode
        
        contract = self.contracts[key]
        
        # Check if status code is expected
        expected_responses = contract.get("response_schema", {})
        if str(status_code) not in expected_responses and status_code != 200:
            if str(status_code) not in contract.get("error_schemas", {}):
                violations.append(ContractViolation(
                    endpoint=key,
                    violation_type="unexpected_status_code",
                    message=f"Unexpected status code {status_code}",
                    severity="warning"
                ))
        
        # Validate response body
        if status_code == 200 and "200" in expected_responses:
            response_schema = expected_responses["200"]
            violations.extend(self._validate_against_schema(
                data=response_data,
                schema=response_schema,
                endpoint=key,
                schema_type="response"
            ))
        
        return violations
    
    def _validate_against_schema(self, data: Any, schema: Dict, endpoint: str, schema_type: str) -> List[ContractViolation]:
        """Validate data against JSON schema"""
        violations = []
        
        try:
            # Basic type validation
            if "type" in schema:
                expected_type = schema["type"]
                actual_type = type(data).__name__
                
                type_mapping = {
                    "object": "dict",
                    "array": "list",
                    "string": "str",
                    "integer": "int",
                    "number": ["int", "float"],
                    "boolean": "bool",
                    "null": "NoneType"
                }
                
                expected_python_types = type_mapping.get(expected_type, expected_type)
                if isinstance(expected_python_types, list):
                    type_match = actual_type in expected_python_types
                else:
                    type_match = actual_type == expected_python_types
                
                if not type_match:
                    violations.append(ContractViolation(
                        endpoint=endpoint,
                        violation_type="type_mismatch",
                        message=f"{schema_type} type mismatch: expected {expected_type}, got {actual_type}",
                        severity="error"
                    ))
            
            # Required fields validation for objects
            if isinstance(data, dict) and "required" in schema:
                for required_field in schema["required"]:
                    if required_field not in data:
                        violations.append(ContractViolation(
                            endpoint=endpoint,
                            violation_type="missing_required_field",
                            message=f"Missing required field: {required_field}",
                            severity="error",
                            field_path=required_field
                        ))
            
            # Properties validation for objects
            if isinstance(data, dict) and "properties" in schema:
                for field_name, field_value in data.items():
                    if field_name in schema["properties"]:
                        field_schema = schema["properties"][field_name]
                        field_violations = self._validate_against_schema(
                            data=field_value,
                            schema=field_schema,
                            endpoint=endpoint,
                            schema_type=f"{schema_type}.{field_name}"
                        )
                        violations.extend(field_violations)
        
        except Exception as e:
            violations.append(ContractViolation(
                endpoint=endpoint,
                violation_type="validation_error",
                message=f"Schema validation error: {str(e)}",
                severity="error"
            ))
        
        return violations
    
    def generate_openapi_spec(self, app: FastAPI) -> Dict[str, Any]:
        """Generate comprehensive OpenAPI 3.0 specification"""
        
        # Base OpenAPI specification
        openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "AI Model Validation Platform API",
                "version": self.version,
                "description": "Comprehensive API for AI model validation with bulletproof contracts",
                "contact": {
                    "name": "API Contract Validation Agent",
                    "email": "api-contracts@ai-validation.com"
                },
                "license": {
                    "name": "MIT",
                    "url": "https://opensource.org/licenses/MIT"
                }
            },
            "servers": [
                {
                    "url": "http://localhost:8000",
                    "description": "Development server"
                },
                {
                    "url": "http://155.138.239.131:8000",
                    "description": "Production server"
                }
            ],
            "paths": {},
            "components": {
                "schemas": self._generate_component_schemas(),
                "responses": self._generate_standard_responses(),
                "parameters": self._generate_standard_parameters(),
                "securitySchemes": {
                    "ApiKeyAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key"
                    }
                }
            },
            "tags": [
                {"name": "Projects", "description": "Project management operations"},
                {"name": "Videos", "description": "Video upload and management"},
                {"name": "Annotations", "description": "Ground truth annotation operations"},
                {"name": "Testing", "description": "Model validation and testing"},
                {"name": "Detection", "description": "Object detection pipeline"},
                {"name": "Dashboard", "description": "Analytics and monitoring"},
                {"name": "Health", "description": "System health and diagnostics"}
            ]
        }
        
        # Add paths from contracts
        for contract_key, contract in self.contracts.items():
            method, path = contract_key.split(" ", 1)
            
            if path not in openapi_spec["paths"]:
                openapi_spec["paths"][path] = {}
            
            openapi_spec["paths"][path][method.lower()] = self._contract_to_openapi_operation(contract)
        
        return openapi_spec
    
    def _generate_component_schemas(self) -> Dict[str, Any]:
        """Generate reusable component schemas"""
        return {
            "Project": {
                "type": "object",
                "required": ["id", "name", "cameraModel", "cameraView", "signalType", "status"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 255},
                    "description": {"type": "string", "nullable": True},
                    "cameraModel": {"type": "string"},
                    "cameraView": {
                        "type": "string",
                        "enum": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]
                    },
                    "lensType": {"type": "string", "nullable": True},
                    "resolution": {"type": "string", "nullable": True},
                    "frameRate": {"type": "integer", "nullable": True, "minimum": 1},
                    "signalType": {
                        "type": "string",
                        "enum": ["GPIO", "Network Packet", "Serial", "CAN Bus"]
                    },
                    "status": {"type": "string", "enum": ["draft", "active", "testing", "completed"]},
                    "ownerId": {"type": "string"},
                    "createdAt": {"type": "string", "format": "date-time"},
                    "updatedAt": {"type": "string", "format": "date-time", "nullable": True}
                },
                "example": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Urban Pedestrian Detection",
                    "description": "Testing pedestrian detection in urban environments",
                    "cameraModel": "Sony IMX274",
                    "cameraView": "Front-facing VRU",
                    "signalType": "GPIO",
                    "status": "active"
                }
            },
            "VideoFile": {
                "type": "object",
                "required": ["id", "filename", "projectId", "status"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "filename": {"type": "string"},
                    "originalName": {"type": "string", "nullable": True},
                    "projectId": {"type": "string", "format": "uuid"},
                    "fileSize": {"type": "integer", "minimum": 0},
                    "duration": {"type": "number", "minimum": 0},
                    "fps": {"type": "number", "minimum": 0},
                    "resolution": {"type": "string", "nullable": True},
                    "status": {"type": "string", "enum": ["uploaded", "processing", "processed", "error"]},
                    "url": {"type": "string", "format": "uri"},
                    "groundTruthGenerated": {"type": "boolean"},
                    "processingStatus": {"type": "string"},
                    "detectionCount": {"type": "integer", "minimum": 0},
                    "createdAt": {"type": "string", "format": "date-time"},
                    "updatedAt": {"type": "string", "format": "date-time", "nullable": True}
                }
            },
            "Annotation": {
                "type": "object",
                "required": ["id", "videoId", "frameNumber", "timestamp", "vruType", "boundingBox"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "videoId": {"type": "string", "format": "uuid"},
                    "detectionId": {"type": "string", "nullable": True},
                    "frameNumber": {"type": "integer", "minimum": 0},
                    "timestamp": {"type": "number", "minimum": 0},
                    "endTimestamp": {"type": "number", "minimum": 0, "nullable": True},
                    "vruType": {
                        "type": "string",
                        "enum": ["pedestrian", "cyclist", "motorcyclist", "wheelchair_user", "scooter_rider"]
                    },
                    "boundingBox": {
                        "$ref": "#/components/schemas/BoundingBox"
                    },
                    "occluded": {"type": "boolean"},
                    "truncated": {"type": "boolean"},
                    "difficult": {"type": "boolean"},
                    "notes": {"type": "string", "nullable": True},
                    "annotator": {"type": "string", "nullable": True},
                    "validated": {"type": "boolean"},
                    "createdAt": {"type": "string", "format": "date-time"},
                    "updatedAt": {"type": "string", "format": "date-time", "nullable": True}
                }
            },
            "BoundingBox": {
                "type": "object",
                "required": ["x", "y", "width", "height"],
                "properties": {
                    "x": {"type": "number", "minimum": 0},
                    "y": {"type": "number", "minimum": 0},
                    "width": {"type": "number", "minimum": 0},
                    "height": {"type": "number", "minimum": 0},
                    "label": {"type": "string", "nullable": True},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "example": {
                    "x": 100,
                    "y": 200,
                    "width": 80,
                    "height": 160,
                    "label": "pedestrian",
                    "confidence": 0.95
                }
            },
            "TestSession": {
                "type": "object",
                "required": ["id", "name", "projectId", "videoId", "status"],
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "projectId": {"type": "string", "format": "uuid"},
                    "videoId": {"type": "string", "format": "uuid"},
                    "toleranceMs": {"type": "integer", "minimum": 0},
                    "status": {"type": "string", "enum": ["created", "running", "completed", "error"]},
                    "startedAt": {"type": "string", "format": "date-time", "nullable": True},
                    "completedAt": {"type": "string", "format": "date-time", "nullable": True},
                    "createdAt": {"type": "string", "format": "date-time"}
                }
            },
            "ValidationMetrics": {
                "type": "object",
                "required": ["accuracy", "precision", "recall", "f1Score"],
                "properties": {
                    "accuracy": {"type": "number", "minimum": 0, "maximum": 1},
                    "precision": {"type": "number", "minimum": 0, "maximum": 1},
                    "recall": {"type": "number", "minimum": 0, "maximum": 1},
                    "f1Score": {"type": "number", "minimum": 0, "maximum": 1},
                    "truePositives": {"type": "integer", "minimum": 0},
                    "falsePositives": {"type": "integer", "minimum": 0},
                    "falseNegatives": {"type": "integer", "minimum": 0},
                    "totalDetections": {"type": "integer", "minimum": 0}
                }
            },
            "Error": {
                "type": "object",
                "required": ["message"],
                "properties": {
                    "message": {"type": "string"},
                    "code": {"type": "string", "nullable": True},
                    "details": {"type": "object", "nullable": True},
                    "timestamp": {"type": "string", "format": "date-time"}
                }
            }
        }
    
    def _generate_standard_responses(self) -> Dict[str, Any]:
        """Generate standard response definitions"""
        return {
            "Success": {
                "description": "Successful operation",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                                "timestamp": {"type": "string", "format": "date-time"}
                            }
                        }
                    }
                }
            },
            "BadRequest": {
                "description": "Invalid request parameters",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "NotFound": {
                "description": "Resource not found",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "InternalServerError": {
                "description": "Internal server error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/Error"}
                    }
                }
            },
            "ValidationError": {
                "description": "Request validation failed",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "message": {"type": "string"},
                                "violations": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "field": {"type": "string"},
                                            "message": {"type": "string"},
                                            "value": {}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def _generate_standard_parameters(self) -> Dict[str, Any]:
        """Generate standard parameter definitions"""
        return {
            "ProjectId": {
                "name": "project_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Project identifier"
            },
            "VideoId": {
                "name": "video_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Video identifier"
            },
            "SessionId": {
                "name": "session_id",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Session identifier"
            },
            "Skip": {
                "name": "skip",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "minimum": 0, "default": 0},
                "description": "Number of items to skip"
            },
            "Limit": {
                "name": "limit",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100},
                "description": "Maximum number of items to return"
            }
        }
    
    def _contract_to_openapi_operation(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """Convert internal contract to OpenAPI operation"""
        operation = {
            "summary": contract.get("summary", f"{contract['method']} {contract['path']}"),
            "description": contract.get("description", ""),
            "tags": contract.get("tags", []),
            "operationId": contract.get("operationId", f"{contract['method'].lower()}_{contract['path'].replace('/', '_').replace('{', '').replace('}', '')}"),
            "parameters": [],
            "responses": {
                "400": {"$ref": "#/components/responses/BadRequest"},
                "500": {"$ref": "#/components/responses/InternalServerError"}
            }
        }
        
        # Add request body if present
        if contract.get("request_schema"):
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": contract["request_schema"]
                    }
                }
            }
        
        # Add response schemas
        if contract.get("response_schema"):
            operation["responses"]["200"] = {
                "description": "Successful response",
                "content": {
                    "application/json": {
                        "schema": contract["response_schema"]
                    }
                }
            }
        
        # Add error response schemas
        for status_code, error_schema in contract.get("error_schemas", {}).items():
            operation["responses"][status_code] = {
                "description": f"Error response {status_code}",
                "content": {
                    "application/json": {
                        "schema": error_schema
                    }
                }
            }
        
        if contract.get("deprecated"):
            operation["deprecated"] = True
        
        return operation
    
    def export_to_file(self, app: FastAPI, file_path: str, format: str = "yaml"):
        """Export OpenAPI specification to file"""
        spec = self.generate_openapi_spec(app)
        
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format.lower() == "yaml":
            with open(path, 'w') as f:
                yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
        else:
            with open(path, 'w') as f:
                json.dump(spec, f, indent=2)
        
        logger.info(f"Exported OpenAPI spec to {file_path}")
    
    def validate_compatibility(self, other_contract: 'APIContract') -> List[ContractViolation]:
        """Validate compatibility between two contract versions"""
        violations = []
        
        # Check for removed endpoints
        for endpoint in self.contracts:
            if endpoint not in other_contract.contracts:
                violations.append(ContractViolation(
                    endpoint=endpoint,
                    violation_type="removed_endpoint",
                    message=f"Endpoint {endpoint} was removed",
                    severity="error"
                ))
        
        # Check for breaking changes in existing endpoints
        for endpoint, contract in self.contracts.items():
            if endpoint in other_contract.contracts:
                other = other_contract.contracts[endpoint]
                
                # Check for removed required fields
                old_required = contract.get("request_schema", {}).get("required", [])
                new_required = other.get("request_schema", {}).get("required", [])
                
                for field in old_required:
                    if field not in new_required:
                        violations.append(ContractViolation(
                            endpoint=endpoint,
                            violation_type="removed_required_field",
                            message=f"Required field '{field}' was removed",
                            severity="error"
                        ))
        
        return violations

# Global contract instance
api_contract = APIContract()

def setup_contract_validation(app: FastAPI, validation_level: ValidationLevel = ValidationLevel.STRICT):
    """Setup contract validation middleware for FastAPI app"""
    api_contract.validation_level = validation_level
    
    @app.middleware("http")
    async def contract_validation_middleware(request: Request, call_next):
        """Middleware to validate requests and responses against contracts"""
        start_time = datetime.now()
        
        # Extract request data for validation
        method = request.method
        path = str(request.url.path)
        
        # Get request body for POST/PUT requests
        request_data = None
        if method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    request_data = json.loads(body) if body else None
            except Exception as e:
                logger.warning(f"Failed to parse request body: {e}")
        
        # Validate request
        request_violations = api_contract.validate_request(method, path, request_data)
        
        if request_violations and validation_level == ValidationLevel.STRICT:
            error_response = {
                "message": "Request validation failed",
                "violations": [
                    {
                        "field": v.field_path,
                        "message": v.message,
                        "type": v.violation_type
                    } for v in request_violations
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            return JSONResponse(
                status_code=422,
                content=error_response
            )
        
        # Process request
        response = await call_next(request)
        
        # Validate response (in development/testing mode)
        if validation_level != ValidationLevel.LENIENT:
            try:
                # This is a simplified check - in production you might want more sophisticated response validation
                response_violations = api_contract.validate_response(method, path, response.status_code, None)
                
                if response_violations:
                    for violation in response_violations:
                        logger.warning(f"Response validation warning: {violation.message}")
            
            except Exception as e:
                logger.warning(f"Response validation error: {e}")
        
        # Add contract validation headers
        response.headers["X-Contract-Version"] = api_contract.version
        response.headers["X-Contract-Hash"] = api_contract.get_contract_hash()[:8]  # Short hash
        response.headers["X-Validation-Time"] = str((datetime.now() - start_time).total_seconds())
        
        return response
    
    logger.info(f"Contract validation middleware setup with {validation_level} validation level")

@contextmanager
def contract_transaction():
    """Context manager for batch contract updates"""
    original_contracts = api_contract.contracts.copy()
    try:
        yield api_contract
    except Exception as e:
        # Rollback on error
        api_contract.contracts = original_contracts
        logger.error(f"Contract transaction failed, rolled back: {e}")
        raise
    else:
        logger.info(f"Contract transaction completed successfully")

def register_endpoint_contract(method: str, path: str, **kwargs):
    """Decorator to register endpoint contracts"""
    def decorator(func):
        api_contract.add_endpoint_contract(method, path, kwargs)
        return func
    return decorator