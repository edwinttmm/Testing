from typing import Dict, Any
from .api_contracts import api_contract, register_endpoint_contract

def define_all_contracts():
    """Define all API endpoint contracts for the AI Model Validation Platform"""
    
    # PROJECT ENDPOINTS
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/projects",
        contract={
            "summary": "List all projects",
            "description": "Retrieve a paginated list of all projects",
            "tags": ["Projects"],
            "parameters": {
                "skip": {"type": "integer", "minimum": 0, "default": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100}
            },
            "response_schema": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Project"}
            },
            "error_schemas": {
                "500": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="POST",
        path="/api/projects",
        contract={
            "summary": "Create new project",
            "description": "Create a new AI model validation project",
            "tags": ["Projects"],
            "request_schema": {
                "type": "object",
                "required": ["name", "cameraModel", "cameraView", "signalType"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 255},
                    "description": {"type": "string", "nullable": True},
                    "cameraModel": {"type": "string"},
                    "cameraView": {
                        "type": "string",
                        "enum": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]
                    },
                    "lensType": {"type": "string", "nullable": True},
                    "resolution": {"type": "string", "nullable": True},
                    "frameRate": {"type": "integer", "minimum": 1, "nullable": True},
                    "signalType": {
                        "type": "string",
                        "enum": ["GPIO", "Network Packet", "Serial", "CAN Bus"]
                    }
                }
            },
            "response_schema": {"$ref": "#/components/schemas/Project"},
            "error_schemas": {
                "400": {"$ref": "#/components/schemas/ValidationError"},
                "422": {"$ref": "#/components/schemas/ValidationError"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/projects/{project_id}",
        contract={
            "summary": "Get project by ID",
            "description": "Retrieve a specific project by its ID",
            "tags": ["Projects"],
            "parameters": {
                "project_id": {"$ref": "#/components/parameters/ProjectId"}
            },
            "response_schema": {"$ref": "#/components/schemas/Project"},
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="PUT",
        path="/api/projects/{project_id}",
        contract={
            "summary": "Update project",
            "description": "Update an existing project",
            "tags": ["Projects"],
            "parameters": {
                "project_id": {"$ref": "#/components/parameters/ProjectId"}
            },
            "request_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 255},
                    "description": {"type": "string", "nullable": True},
                    "cameraModel": {"type": "string"},
                    "cameraView": {
                        "type": "string",
                        "enum": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]
                    },
                    "status": {
                        "type": "string",
                        "enum": ["draft", "active", "testing", "completed", "archived"]
                    }
                }
            },
            "response_schema": {"$ref": "#/components/schemas/Project"},
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"},
                "400": {"$ref": "#/components/schemas/ValidationError"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="DELETE",
        path="/api/projects/{project_id}",
        contract={
            "summary": "Delete project",
            "description": "Delete a project and all associated data",
            "tags": ["Projects"],
            "parameters": {
                "project_id": {"$ref": "#/components/parameters/ProjectId"}
            },
            "response_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "deleted_id": {"type": "string"}
                }
            },
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    # VIDEO ENDPOINTS
    api_contract.add_endpoint_contract(
        method="POST",
        path="/api/projects/{project_id}/videos",
        contract={
            "summary": "Upload video to project",
            "description": "Upload a video file to a specific project for validation",
            "tags": ["Videos"],
            "parameters": {
                "project_id": {"$ref": "#/components/parameters/ProjectId"}
            },
            "request_schema": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "description": "Video file to upload"
                    }
                }
            },
            "response_schema": {"$ref": "#/components/schemas/VideoFile"},
            "error_schemas": {
                "400": {"$ref": "#/components/schemas/ValidationError"},
                "404": {"$ref": "#/components/schemas/Error"},
                "413": {
                    "description": "File too large",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                }
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/projects/{project_id}/videos",
        contract={
            "summary": "List project videos",
            "description": "Get all videos associated with a project",
            "tags": ["Videos"],
            "parameters": {
                "project_id": {"$ref": "#/components/parameters/ProjectId"}
            },
            "response_schema": {
                "type": "object",
                "properties": {
                    "videos": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/VideoFile"}
                    },
                    "total": {"type": "integer", "minimum": 0}
                }
            },
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/videos",
        contract={
            "summary": "List all videos",
            "description": "Get all videos in the system with optional filtering",
            "tags": ["Videos"],
            "parameters": {
                "unassigned": {"type": "boolean", "default": False},
                "skip": {"$ref": "#/components/parameters/Skip"},
                "limit": {"$ref": "#/components/parameters/Limit"}
            },
            "response_schema": {
                "type": "object",
                "properties": {
                    "videos": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/VideoFile"}
                    },
                    "total": {"type": "integer", "minimum": 0}
                }
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="DELETE",
        path="/api/videos/{video_id}",
        contract={
            "summary": "Delete video",
            "description": "Delete a video and all associated annotations",
            "tags": ["Videos"],
            "parameters": {
                "video_id": {"$ref": "#/components/parameters/VideoId"}
            },
            "response_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "deleted_id": {"type": "string"}
                }
            },
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    # ANNOTATION ENDPOINTS (The critical GroundTruth issue source)
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/videos/{video_id}/annotations",
        contract={
            "summary": "Get video annotations",
            "description": "Retrieve all ground truth annotations for a video",
            "tags": ["Annotations"],
            "parameters": {
                "video_id": {"$ref": "#/components/parameters/VideoId"}
            },
            "response_schema": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Annotation"}
            },
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="POST",
        path="/api/videos/{video_id}/annotations",
        contract={
            "summary": "Create annotation",
            "description": "Create a new ground truth annotation for a video",
            "tags": ["Annotations"],
            "parameters": {
                "video_id": {"$ref": "#/components/parameters/VideoId"}
            },
            "request_schema": {
                "type": "object",
                "required": ["frameNumber", "timestamp", "vruType", "boundingBox"],
                "properties": {
                    "detectionId": {"type": "string", "nullable": True},
                    "frameNumber": {"type": "integer", "minimum": 0},
                    "timestamp": {"type": "number", "minimum": 0},
                    "endTimestamp": {"type": "number", "minimum": 0, "nullable": True},
                    "vruType": {
                        "type": "string",
                        "enum": ["pedestrian", "cyclist", "motorcyclist", "wheelchair_user", "scooter_rider"]
                    },
                    "boundingBox": {"$ref": "#/components/schemas/BoundingBox"},
                    "occluded": {"type": "boolean", "default": False},
                    "truncated": {"type": "boolean", "default": False},
                    "difficult": {"type": "boolean", "default": False},
                    "notes": {"type": "string", "nullable": True},
                    "annotator": {"type": "string", "nullable": True},
                    "validated": {"type": "boolean", "default": False}
                }
            },
            "response_schema": {"$ref": "#/components/schemas/Annotation"},
            "error_schemas": {
                "400": {"$ref": "#/components/schemas/ValidationError"},
                "404": {"$ref": "#/components/schemas/Error"},
                "422": {"$ref": "#/components/schemas/ValidationError"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/videos/{video_id}/ground-truth",
        contract={
            "summary": "Get ground truth data",
            "description": "Retrieve processed ground truth objects for a video",
            "tags": ["Annotations"],
            "parameters": {
                "video_id": {"$ref": "#/components/parameters/VideoId"}
            },
            "response_schema": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "format": "uuid"},
                    "objects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "format": "uuid"},
                                "timestamp": {"type": "number", "minimum": 0},
                                "frame_number": {"type": "integer", "minimum": 0},
                                "class_label": {"type": "string"},
                                "x": {"type": "number", "minimum": 0},
                                "y": {"type": "number", "minimum": 0},
                                "width": {"type": "number", "minimum": 0},
                                "height": {"type": "number", "minimum": 0},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                "validated": {"type": "boolean"}
                            }
                        }
                    },
                    "total_detections": {"type": "integer", "minimum": 0},
                    "status": {"type": "string", "enum": ["pending", "processing", "completed", "error"]}
                }
            },
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    # TEST SESSION ENDPOINTS
    api_contract.add_endpoint_contract(
        method="POST",
        path="/api/test-sessions",
        contract={
            "summary": "Create test session",
            "description": "Create a new model validation test session",
            "tags": ["Testing"],
            "request_schema": {
                "type": "object",
                "required": ["name", "project_id", "video_id"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "project_id": {"type": "string", "format": "uuid"},
                    "video_id": {"type": "string", "format": "uuid"},
                    "tolerance_ms": {"type": "integer", "minimum": 0, "default": 100}
                }
            },
            "response_schema": {"$ref": "#/components/schemas/TestSession"},
            "error_schemas": {
                "400": {"$ref": "#/components/schemas/ValidationError"},
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/test-sessions",
        contract={
            "summary": "List test sessions",
            "description": "Get all test sessions with optional project filtering",
            "tags": ["Testing"],
            "parameters": {
                "project_id": {"type": "string", "format": "uuid", "nullable": True}
            },
            "response_schema": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/TestSession"}
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/test-sessions/{session_id}/results",
        contract={
            "summary": "Get test results",
            "description": "Retrieve validation results for a test session",
            "tags": ["Testing"],
            "parameters": {
                "session_id": {"$ref": "#/components/parameters/SessionId"}
            },
            "response_schema": {"$ref": "#/components/schemas/ValidationMetrics"},
            "error_schemas": {
                "404": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    # DETECTION PIPELINE ENDPOINTS
    api_contract.add_endpoint_contract(
        method="POST",
        path="/api/detection/pipeline/run",
        contract={
            "summary": "Run detection pipeline",
            "description": "Execute object detection on a video",
            "tags": ["Detection"],
            "request_schema": {
                "type": "object",
                "required": ["video_id"],
                "properties": {
                    "video_id": {"type": "string", "format": "uuid"},
                    "confidence_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.7},
                    "nms_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.45},
                    "model_name": {"type": "string", "default": "yolov8n"},
                    "target_classes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["pedestrian", "cyclist", "motorcyclist"]
                    }
                }
            },
            "response_schema": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "format": "uuid"},
                    "detections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "timestamp": {"type": "number"},
                                "frame_number": {"type": "integer"},
                                "confidence": {"type": "number"},
                                "class_label": {"type": "string"},
                                "bounding_box": {"$ref": "#/components/schemas/BoundingBox"}
                            }
                        }
                    },
                    "processing_time": {"type": "number"},
                    "model_used": {"type": "string"},
                    "total_detections": {"type": "integer"},
                    "confidence_distribution": {
                        "type": "object",
                        "additionalProperties": {"type": "integer"}
                    }
                }
            },
            "error_schemas": {
                "400": {"$ref": "#/components/schemas/ValidationError"},
                "404": {"$ref": "#/components/schemas/Error"},
                "500": {"$ref": "#/components/schemas/Error"}
            }
        }
    )
    
    # DASHBOARD ENDPOINTS
    api_contract.add_endpoint_contract(
        method="GET",
        path="/api/dashboard/stats",
        contract={
            "summary": "Get dashboard statistics",
            "description": "Retrieve comprehensive dashboard analytics",
            "tags": ["Dashboard"],
            "response_schema": {
                "type": "object",
                "properties": {
                    "projectCount": {"type": "integer", "minimum": 0},
                    "videoCount": {"type": "integer", "minimum": 0},
                    "testCount": {"type": "integer", "minimum": 0},
                    "totalDetections": {"type": "integer", "minimum": 0},
                    "averageAccuracy": {"type": "number", "minimum": 0, "maximum": 1},
                    "activeTests": {"type": "integer", "minimum": 0},
                    "confidenceIntervals": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "array",
                            "items": {"type": "number"}
                        }
                    },
                    "trendAnalysis": {
                        "type": "object",
                        "additionalProperties": {"type": "string"}
                    },
                    "signalProcessingMetrics": {
                        "type": "object",
                        "additionalProperties": True
                    }
                }
            }
        }
    )
    
    # HEALTH CHECK ENDPOINTS
    api_contract.add_endpoint_contract(
        method="GET",
        path="/health",
        contract={
            "summary": "Health check",
            "description": "Check API health and connectivity",
            "tags": ["Health"],
            "response_schema": {
                "type": "object",
                "required": ["status"],
                "properties": {
                    "status": {"type": "string", "enum": ["healthy", "unhealthy"]},
                    "timestamp": {"type": "string", "format": "date-time"},
                    "environment": {"type": "string", "nullable": True},
                    "database_status": {"type": "string", "nullable": True},
                    "version": {"type": "string", "nullable": True}
                }
            }
        }
    )
    
    api_contract.add_endpoint_contract(
        method="GET",
        path="/health/database",
        contract={
            "summary": "Database health check",
            "description": "Check database connectivity and health",
            "tags": ["Health"],
            "response_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["healthy", "unhealthy"]},
                    "connection_time_ms": {"type": "number"},
                    "active_connections": {"type": "integer"},
                    "database_size": {"type": "string", "nullable": True},
                    "last_backup": {"type": "string", "format": "date-time", "nullable": True}
                }
            }
        }
    )
    
    print(f"✅ Defined {len(api_contract.contracts)} API endpoint contracts")

def get_critical_endpoints() -> Dict[str, str]:
    """Return list of critical endpoints that must never break"""
    return {
        "GET /api/videos/{video_id}/annotations": "Annotation retrieval - GroundTruth issue source",
        "POST /api/videos/{video_id}/annotations": "Annotation creation - Critical for data integrity",
        "GET /api/videos/{video_id}/ground-truth": "Ground truth data - Core functionality",
        "POST /api/projects/{project_id}/videos": "Video upload - Core workflow",
        "GET /api/projects/{project_id}/videos": "Video listing - Dashboard dependency",
        "POST /api/detection/pipeline/run": "Detection pipeline - Main feature",
        "GET /api/dashboard/stats": "Dashboard data - UI dependency",
        "POST /api/test-sessions": "Test creation - Validation workflow",
        "GET /api/test-sessions/{session_id}/results": "Results retrieval - Validation output"
    }

def validate_critical_endpoints():
    """Validate that all critical endpoints have proper contracts"""
    critical = get_critical_endpoints()
    missing = []
    
    for endpoint in critical:
        if endpoint not in api_contract.contracts:
            missing.append(endpoint)
    
    if missing:
        raise Exception(f"Missing contracts for critical endpoints: {missing}")
    
    print(f"✅ All {len(critical)} critical endpoints have valid contracts")

if __name__ == "__main__":
    define_all_contracts()
    validate_critical_endpoints()