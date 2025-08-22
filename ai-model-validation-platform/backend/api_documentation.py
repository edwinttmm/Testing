from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from pathlib import Path

from database import get_db
from models import Project, Video, Annotation, TestSession, DetectionEvent

router = APIRouter(prefix="/api/docs", tags=["API Documentation"])

class APIDocumentationService:
    """Service for generating comprehensive API documentation"""
    
    def __init__(self):
        self.doc_cache = {}  # Cache for generated documentation
        self.examples_cache = {}  # Cache for code examples
    
    def get_comprehensive_api_docs(self) -> Dict[str, Any]:
        """Generate comprehensive API documentation"""
        return {
            "info": {
                "title": "AI Model Validation Platform API",
                "version": "2.0.0",
                "description": "Comprehensive backend API for AI model validation with video processing, real-time signal detection, and annotation management",
                "contact": {
                    "name": "AI Validation Team",
                    "email": "support@aivalidation.com"
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
                    "url": "https://api.aivalidation.com",
                    "description": "Production server"
                }
            ],
            "endpoints": self._get_endpoint_documentation(),
            "schemas": self._get_schema_documentation(),
            "authentication": self._get_authentication_docs(),
            "rate_limiting": self._get_rate_limiting_docs(),
            "error_handling": self._get_error_handling_docs(),
            "examples": self._get_code_examples(),
            "websocket": self._get_websocket_docs(),
            "deployment": self._get_deployment_docs()
        }
    
    def _get_endpoint_documentation(self) -> Dict[str, Any]:
        """Get comprehensive endpoint documentation"""
        return {
            "video_management": {
                "description": "Video upload, storage, and management endpoints",
                "endpoints": {
                    "POST /api/videos": {
                        "summary": "Upload video to central store",
                        "description": "Upload video files with chunked upload support and automatic metadata extraction",
                        "parameters": {
                            "file": {
                                "type": "file",
                                "required": True,
                                "description": "Video file (MP4, AVI, MOV, MKV)",
                                "max_size": "100MB"
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Video uploaded successfully",
                                "schema": "VideoUploadResponse"
                            },
                            "400": "Invalid file format or size",
                            "413": "File too large",
                            "500": "Upload failed"
                        },
                        "example_request": {
                            "curl": "curl -X POST -F 'file=@video.mp4' http://localhost:8000/api/videos"
                        }
                    },
                    "POST /api/projects/{project_id}/videos": {
                        "summary": "Upload video to specific project",
                        "description": "Upload video directly to a project with automatic ground truth processing",
                        "parameters": {
                            "project_id": {
                                "type": "string",
                                "required": True,
                                "description": "Project identifier"
                            },
                            "file": {
                                "type": "file",
                                "required": True,
                                "description": "Video file"
                            }
                        }
                    },
                    "GET /api/videos": {
                        "summary": "List all videos from central store",
                        "description": "Retrieve videos with filtering and pagination",
                        "parameters": {
                            "skip": {"type": "integer", "default": 0},
                            "limit": {"type": "integer", "default": 100, "max": 1000},
                            "unassigned": {"type": "boolean", "default": False}
                        }
                    },
                    "DELETE /api/videos/{video_id}": {
                        "summary": "Delete video and associated data",
                        "description": "Permanently delete video file and all related annotations, detections, and ground truth data",
                        "parameters": {
                            "video_id": {
                                "type": "string",
                                "required": True,
                                "description": "Video identifier"
                            }
                        }
                    }
                }
            },
            "annotation_system": {
                "description": "Comprehensive annotation management with AI pre-annotation",
                "endpoints": {
                    "POST /api/annotations/videos/{video_id}/annotations": {
                        "summary": "Create annotation for video",
                        "description": "Create new annotation with bounding box, VRU type, and validation status",
                        "parameters": {
                            "video_id": {"type": "string", "required": True}
                        },
                        "request_body": "AnnotationCreate",
                        "responses": {
                            "200": {"schema": "AnnotationResponse"},
                            "404": "Video not found",
                            "422": "Validation error"
                        }
                    },
                    "POST /api/annotations/videos/{video_id}/annotations/bulk": {
                        "summary": "Create multiple annotations in batch",
                        "description": "Efficiently create multiple annotations for a video in a single transaction",
                        "request_body": "AnnotationBulkCreate",
                        "performance": "Optimized for batch operations with transaction safety"
                    },
                    "POST /api/annotations/videos/{video_id}/pre-annotate": {
                        "summary": "Trigger AI pre-annotation",
                        "description": "Start background AI pre-annotation using ML models (YOLOv8, etc.)",
                        "parameters": {
                            "model_name": {"type": "string", "default": "yolov8n"},
                            "confidence_threshold": {"type": "float", "default": 0.5}
                        },
                        "async": True,
                        "websocket_updates": True
                    },
                    "GET /api/annotations/videos/{video_id}/annotations": {
                        "summary": "Get video annotations with filtering",
                        "description": "Retrieve annotations with advanced filtering by VRU type, validation status, frame range",
                        "parameters": {
                            "validated_only": {"type": "boolean", "default": False},
                            "vru_type": {"type": "string", "enum": ["pedestrian", "cyclist", "motorcyclist"]},
                            "frame_start": {"type": "integer"},
                            "frame_end": {"type": "integer"}
                        }
                    },
                    "POST /api/annotations/videos/{video_id}/export": {
                        "summary": "Export annotations in multiple formats",
                        "description": "Export annotations as JSON, CSV, XML, COCO, YOLO, or PASCAL VOC",
                        "request_body": "AnnotationExportRequest",
                        "supported_formats": ["json", "csv", "xml", "coco", "yolo", "pascal_voc"]
                    }
                }
            },
            "project_management": {
                "description": "Project management with intelligent video assignment",
                "endpoints": {
                    "POST /api/projects": {
                        "summary": "Create new project",
                        "description": "Create project with camera configuration and signal type specification",
                        "request_body": "ProjectCreate",
                        "required_fields": ["name", "camera_model", "camera_view", "signal_type"]
                    },
                    "GET /api/projects": {
                        "summary": "List projects with pagination",
                        "parameters": {
                            "skip": {"type": "integer", "default": 0},
                            "limit": {"type": "integer", "default": 100}
                        }
                    },
                    "POST /api/projects/{project_id}/videos/link": {
                        "summary": "Link videos to project",
                        "description": "Assign videos from central store to project",
                        "request_body": {"video_ids": ["string"]}
                    },
                    "GET /api/projects/{project_id}/assignments/intelligent": {
                        "summary": "Get intelligent video assignments",
                        "description": "AI-powered video assignment recommendations based on project requirements"
                    }
                }
            },
            "signal_detection": {
                "description": "Real-time camera signal detection and validation",
                "endpoints": {
                    "POST /api/annotations/camera/signals/detect": {
                        "summary": "Detect camera signals in video",
                        "description": "Analyze video for GPIO, Network, Serial, or CAN bus signals",
                        "parameters": {
                            "video_id": {"type": "string", "required": True},
                            "signal_type": {
                                "type": "string", 
                                "required": True,
                                "enum": ["GPIO", "Network Packet", "Serial", "CAN Bus"]
                            }
                        },
                        "async": True,
                        "processing_types": {
                            "GPIO": "Computer vision analysis of LED indicators and status lights",
                            "Network Packet": "Network traffic monitoring and packet analysis",
                            "Serial": "Serial communication protocol detection",
                            "CAN Bus": "CAN bus message frame analysis"
                        }
                    },
                    "GET /api/annotations/camera/signals/{video_id}/results": {
                        "summary": "Get signal detection results",
                        "description": "Retrieve detected signals with confidence scores and temporal analysis"
                    },
                    "POST /api/annotations/timing/compare": {
                        "summary": "Compare signal timing",
                        "description": "Compare reference and detected signal timestamps with tolerance analysis",
                        "request_body": "TimingComparisonRequest",
                        "metrics": ["accuracy", "precision", "recall", "average_delay"]
                    }
                }
            },
            "real_time_validation": {
                "description": "Real-time detection validation with pass/fail criteria",
                "endpoints": {
                    "POST /api/annotations/validation/real-time": {
                        "summary": "Validate detection in real-time",
                        "description": "Compare detection against ground truth with spatial and temporal validation",
                        "request_body": "AnnotationValidationRequest",
                        "validation_types": ["spatial", "temporal", "combined"]
                    },
                    "GET /api/annotations/validation/pass-fail/{test_session_id}": {
                        "summary": "Get pass/fail validation results",
                        "description": "Comprehensive pass/fail analysis with detailed metrics and recommendations"
                    },
                    "POST /api/projects/{project_id}/criteria/configure": {
                        "summary": "Configure pass/fail criteria",
                        "description": "Set validation thresholds for detection rate, latency, spatial accuracy",
                        "request_body": "PassFailCriteriaSchema"
                    }
                }
            },
            "test_execution": {
                "description": "Automated test execution and results analysis",
                "endpoints": {
                    "POST /api/projects/{project_id}/execute-test": {
                        "summary": "Execute test session for project",
                        "description": "Run automated validation test against all project videos with ground truth"
                    },
                    "GET /api/test-sessions/{session_id}/status": {
                        "summary": "Get test session status",
                        "description": "Real-time test execution status with progress tracking"
                    },
                    "GET /api/test-sessions/{session_id}/results": {
                        "summary": "Get comprehensive test results",
                        "description": "Detailed test results with statistical analysis and confidence intervals"
                    }
                }
            }
        }
    
    def _get_schema_documentation(self) -> Dict[str, Any]:
        """Get schema documentation"""
        return {
            "AnnotationCreate": {
                "description": "Schema for creating new annotations",
                "properties": {
                    "frame_number": {"type": "integer", "minimum": 0},
                    "timestamp": {"type": "number", "minimum": 0},
                    "vru_type": {"enum": ["pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"]},
                    "bounding_box": {"$ref": "#/schemas/BoundingBox"},
                    "validated": {"type": "boolean", "default": False}
                },
                "required": ["frame_number", "timestamp", "vru_type", "bounding_box"]
            },
            "BoundingBox": {
                "description": "Bounding box coordinates with confidence",
                "properties": {
                    "x": {"type": "number", "minimum": 0},
                    "y": {"type": "number", "minimum": 0},
                    "width": {"type": "number", "minimum": 0},
                    "height": {"type": "number", "minimum": 0},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["x", "y", "width", "height"]
            },
            "ProjectCreate": {
                "description": "Schema for creating new projects",
                "properties": {
                    "name": {"type": "string", "maxLength": 255},
                    "description": {"type": "string"},
                    "camera_model": {"type": "string"},
                    "camera_view": {"enum": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]},
                    "signal_type": {"enum": ["GPIO", "Network Packet", "Serial", "CAN Bus"]}
                },
                "required": ["name", "camera_model", "camera_view", "signal_type"]
            },
            "ValidationResult": {
                "description": "Real-time validation result",
                "properties": {
                    "validation_status": {"enum": ["PASS", "FAIL", "UNCERTAIN"]},
                    "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
                    "timing_offset": {"type": "number", "description": "Offset in milliseconds"},
                    "spatial_error": {"type": "number", "description": "IoU score for spatial accuracy"}
                }
            }
        }
    
    def _get_authentication_docs(self) -> Dict[str, Any]:
        """Get authentication documentation"""
        return {
            "overview": "Currently using anonymous authentication for development. Production will implement JWT tokens.",
            "development": {
                "type": "anonymous",
                "description": "No authentication required for development environment"
            },
            "production": {
                "type": "JWT",
                "header": "Authorization: Bearer <token>",
                "token_endpoint": "/api/auth/token",
                "refresh_endpoint": "/api/auth/refresh",
                "expiry": "24 hours"
            },
            "scopes": {
                "read": "Read access to projects and videos",
                "write": "Create and modify annotations",
                "admin": "Full administrative access"
            }
        }
    
    def _get_rate_limiting_docs(self) -> Dict[str, Any]:
        """Get rate limiting documentation"""
        return {
            "overview": "API implements rate limiting to ensure fair usage and system stability",
            "limits": {
                "general": "1000 requests per hour per IP",
                "upload": "10 video uploads per hour per user",
                "export": "50 exports per hour per user",
                "websocket": "100 connections per IP"
            },
            "headers": {
                "X-RateLimit-Limit": "Request limit per window",
                "X-RateLimit-Remaining": "Remaining requests in current window",
                "X-RateLimit-Reset": "Time when limit resets (Unix timestamp)"
            },
            "retry_after": "When rate limited, wait time specified in Retry-After header"
        }
    
    def _get_error_handling_docs(self) -> Dict[str, Any]:
        """Get error handling documentation"""
        return {
            "overview": "Comprehensive error handling with detailed error codes and messages",
            "error_format": {
                "structure": {
                    "detail": "Human-readable error message",
                    "error_code": "Machine-readable error code",
                    "field_errors": "Field-specific validation errors (if applicable)",
                    "timestamp": "Error occurrence timestamp",
                    "request_id": "Unique request identifier for debugging"
                }
            },
            "http_status_codes": {
                "400": "Bad Request - Invalid request format or parameters",
                "401": "Unauthorized - Authentication required",
                "403": "Forbidden - Insufficient permissions",
                "404": "Not Found - Resource does not exist",
                "409": "Conflict - Resource already exists or constraint violation",
                "413": "Payload Too Large - File size exceeds limit",
                "422": "Unprocessable Entity - Validation errors",
                "429": "Too Many Requests - Rate limit exceeded",
                "500": "Internal Server Error - Unexpected server error",
                "503": "Service Unavailable - Server temporarily unavailable"
            },
            "custom_error_codes": {
                "VIDEO_NOT_FOUND": "Specified video does not exist",
                "INVALID_FILE_FORMAT": "Unsupported video file format",
                "PROCESSING_IN_PROGRESS": "Video is currently being processed",
                "GROUND_TRUTH_MISSING": "Ground truth data not available",
                "ANNOTATION_CONFLICT": "Annotation conflicts with existing data",
                "SIGNAL_DETECTION_FAILED": "Signal detection processing failed",
                "VALIDATION_TIMEOUT": "Real-time validation timed out"
            }
        }
    
    def _get_code_examples(self) -> Dict[str, Any]:
        """Get comprehensive code examples"""
        return {
            "python": {
                "upload_video": {
                    "description": "Upload video with error handling",
                    "code": '''
import requests
import json

def upload_video(file_path, api_base_url="http://localhost:8000"):
    """Upload video to AI validation platform"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path, f, 'video/mp4')}
            response = requests.post(
                f"{api_base_url}/api/videos",
                files=files,
                timeout=300  # 5 minute timeout for large files
            )
            
        response.raise_for_status()
        result = response.json()
        
        print(f"Video uploaded successfully: {result['id']}")
        print(f"Processing status: {result['processingStatus']}")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"Upload failed: {e}")
        return None

# Example usage
result = upload_video("test_video.mp4")
if result:
    video_id = result['id']
    print(f"Video ID: {video_id}")
'''
                },
                "create_annotation": {
                    "description": "Create annotation with validation",
                    "code": '''
import requests
import json

def create_annotation(video_id, frame_number, timestamp, bbox, vru_type="pedestrian"):
    """Create annotation for video"""
    annotation_data = {
        "frame_number": frame_number,
        "timestamp": timestamp,
        "vru_type": vru_type,
        "bounding_box": {
            "x": bbox[0],
            "y": bbox[1],
            "width": bbox[2],
            "height": bbox[3],
            "confidence": 0.95
        },
        "validated": False,
        "annotator": "human_annotator"
    }
    
    response = requests.post(
        f"http://localhost:8000/api/annotations/videos/{video_id}/annotations",
        json=annotation_data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Annotation created: {result['id']}")
        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Example usage
bbox = [100, 100, 80, 120]  # x, y, width, height
annotation = create_annotation("video_id", 150, 5.0, bbox, "pedestrian")
'''
                },
                "websocket_client": {
                    "description": "WebSocket client for real-time updates",
                    "code": '''
import asyncio
import websockets
import json

async def websocket_client():
    """Connect to WebSocket for real-time updates"""
    uri = "ws://localhost:8000/ws/progress/general"
    
    async with websockets.connect(uri) as websocket:
        # Send subscription message
        subscribe_msg = {
            "type": "subscribe_video",
            "video_id": "your_video_id"
        }
        await websocket.send(json.dumps(subscribe_msg))
        
        # Listen for updates
        async for message in websocket:
            data = json.loads(message)
            
            if data["type"] == "pre_annotation_status":
                progress = data["data"]["progress_percentage"]
                print(f"Pre-annotation progress: {progress:.1f}%")
            
            elif data["type"] == "validation_result":
                result = data["data"]["validation_result"]
                confidence = data["data"]["confidence_score"]
                print(f"Validation result: {result} (confidence: {confidence:.2f})")

# Run WebSocket client
asyncio.run(websocket_client())
'''
                }
            },
            "javascript": {
                "upload_with_progress": {
                    "description": "Upload video with progress tracking",
                    "code": '''
const uploadVideo = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    const response = await fetch('/api/videos', {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header, let browser set it with boundary
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }
    
    const result = await response.json();
    console.log('Upload successful:', result);
    
    // Start monitoring progress via WebSocket
    monitorVideoProcessing(result.id);
    
    return result;
  } catch (error) {
    console.error('Upload error:', error);
    throw error;
  }
};

const monitorVideoProcessing = (videoId) => {
  const ws = new WebSocket(`ws://localhost:8000/ws/progress/general`);
  
  ws.onopen = () => {
    ws.send(JSON.stringify({
      type: 'subscribe_video',
      video_id: videoId
    }));
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'pre_annotation_status') {
      const progress = data.data.progress_percentage;
      console.log(`Processing progress: ${progress}%`);
      
      // Update UI progress bar
      updateProgressBar(progress);
    }
  };
};
'''
                }
            },
            "curl": {
                "basic_operations": {
                    "description": "Common curl commands for API testing",
                    "code": '''
# Upload video
curl -X POST \
  -F "file=@test_video.mp4" \
  http://localhost:8000/api/videos

# Create project
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "description": "Test project for validation",
    "camera_model": "Test Camera",
    "camera_view": "Front-facing VRU",
    "signal_type": "GPIO"
  }' \
  http://localhost:8000/api/projects

# Create annotation
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "frame_number": 100,
    "timestamp": 3.33,
    "vru_type": "pedestrian",
    "bounding_box": {
      "x": 100,
      "y": 100,
      "width": 80,
      "height": 120
    },
    "validated": false
  }' \
  http://localhost:8000/api/annotations/videos/VIDEO_ID/annotations

# Trigger pre-annotation
curl -X POST \
  "http://localhost:8000/api/annotations/videos/VIDEO_ID/pre-annotate?model_name=yolov8s&confidence_threshold=0.6"

# Export annotations
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "format": "json",
    "include_metadata": true,
    "validated_only": false
  }' \
  http://localhost:8000/api/annotations/videos/VIDEO_ID/export
'''
                }
            }
        }
    
    def _get_websocket_docs(self) -> Dict[str, Any]:
        """Get WebSocket documentation"""
        return {
            "overview": "Real-time communication for progress updates, validation results, and system notifications",
            "endpoints": {
                "ws://localhost:8000/ws/progress/general": "General purpose WebSocket connection",
                "ws://localhost:8000/ws/progress/{task_id}": "Task-specific progress updates"
            },
            "message_types": {
                "connection_established": "Sent when connection is established",
                "pre_annotation_status": "Pre-annotation progress updates",
                "validation_result": "Real-time validation results",
                "signal_detection": "Signal detection progress and results",
                "test_session_update": "Test execution status updates",
                "system_alert": "System-wide notifications",
                "ping/pong": "Keep-alive messages"
            },
            "client_commands": {
                "join_room": "Join a specific room for targeted updates",
                "leave_room": "Leave a room",
                "subscribe_video": "Subscribe to video processing updates",
                "subscribe_test_session": "Subscribe to test session updates"
            },
            "rooms": {
                "video_{video_id}": "Video-specific updates",
                "test_session_{session_id}": "Test session updates",
                "annotation_session_{session_id}": "Annotation session updates",
                "project_{project_id}": "Project-level updates"
            }
        }
    
    def _get_deployment_docs(self) -> Dict[str, Any]:
        """Get deployment documentation"""
        return {
            "docker": {
                "description": "Containerized deployment with Docker",
                "dockerfile": {
                    "base_image": "python:3.11-slim",
                    "dependencies": ["FastAPI", "SQLAlchemy", "OpenCV", "PyTorch", "Ultralytics"],
                    "ports": ["8000:8000"],
                    "volumes": ["/app/uploads", "/app/exports"]
                },
                "docker_compose": {
                    "services": ["api", "database", "redis", "nginx"],
                    "networks": "ai_validation_network",
                    "environment_variables": ["DATABASE_URL", "REDIS_URL", "ML_MODEL_PATH"]
                }
            },
            "kubernetes": {
                "description": "Scalable deployment with Kubernetes",
                "manifests": ["deployment.yaml", "service.yaml", "ingress.yaml", "configmap.yaml"],
                "scaling": "Horizontal Pod Autoscaler based on CPU and memory",
                "storage": "Persistent volumes for video uploads and model files"
            },
            "environment_variables": {
                "DATABASE_URL": "PostgreSQL connection string",
                "REDIS_URL": "Redis connection for caching",
                "ML_MODEL_PATH": "Path to ML model files",
                "UPLOAD_DIRECTORY": "Directory for video uploads",
                "API_PORT": "Port for API server (default: 8000)",
                "LOG_LEVEL": "Logging level (DEBUG, INFO, WARNING, ERROR)",
                "CORS_ORIGINS": "Allowed CORS origins",
                "MAX_FILE_SIZE": "Maximum upload file size in bytes"
            },
            "monitoring": {
                "health_checks": "/health endpoint for liveness and readiness probes",
                "metrics": "Prometheus metrics for monitoring",
                "logging": "Structured JSON logging with correlation IDs",
                "alerting": "Integration with monitoring systems"
            }
        }

# Global documentation service instance
api_docs_service = APIDocumentationService()

@router.get("/")
async def get_api_documentation():
    """Get comprehensive API documentation"""
    return api_docs_service.get_comprehensive_api_docs()

@router.get("/endpoints")
async def get_endpoint_docs():
    """Get detailed endpoint documentation"""
    return api_docs_service._get_endpoint_documentation()

@router.get("/schemas")
async def get_schema_docs():
    """Get schema documentation"""
    return api_docs_service._get_schema_documentation()

@router.get("/examples")
async def get_code_examples():
    """Get code examples in multiple languages"""
    return api_docs_service._get_code_examples()

@router.get("/websocket")
async def get_websocket_docs():
    """Get WebSocket documentation"""
    return api_docs_service._get_websocket_docs()

@router.get("/deployment")
async def get_deployment_docs():
    """Get deployment documentation"""
    return api_docs_service._get_deployment_docs()

@router.get("/health")
async def api_health_check():
    """API health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "components": {
            "database": "healthy",
            "ml_models": "available",
            "file_storage": "accessible",
            "websocket": "active"
        }
    }

@router.get("/stats", response_model=Dict[str, Any])
async def get_api_statistics(db: Session = Depends(get_db)):
    """Get API usage statistics"""
    try:
        # Calculate basic statistics
        total_projects = db.query(Project).count()
        total_videos = db.query(Video).count()
        total_annotations = db.query(Annotation).count()
        total_test_sessions = db.query(TestSession).count()
        total_detections = db.query(DetectionEvent).count()
        
        # Calculate processing statistics
        videos_with_ground_truth = db.query(Video).filter(
            Video.ground_truth_generated == True
        ).count()
        
        validated_annotations = db.query(Annotation).filter(
            Annotation.validated == True
        ).count()
        
        return {
            "database_statistics": {
                "total_projects": total_projects,
                "total_videos": total_videos,
                "total_annotations": total_annotations,
                "total_test_sessions": total_test_sessions,
                "total_detections": total_detections
            },
            "processing_statistics": {
                "videos_with_ground_truth": videos_with_ground_truth,
                "ground_truth_coverage": (
                    (videos_with_ground_truth / total_videos * 100) 
                    if total_videos > 0 else 0
                ),
                "validated_annotations": validated_annotations,
                "validation_rate": (
                    (validated_annotations / total_annotations * 100) 
                    if total_annotations > 0 else 0
                )
            },
            "api_information": {
                "version": "2.0.0",
                "uptime": "Real-time uptime tracking would be implemented here",
                "last_updated": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting API statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get API statistics")
