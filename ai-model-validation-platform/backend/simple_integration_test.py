#!/usr/bin/env python3
"""
Simple Integration Test Server
Bypasses complex service imports to focus on core API functionality
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from datetime import datetime
from typing import List, Dict, Any
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Model Validation API - Integration Test",
    description="Simple server for frontend-backend integration testing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data storage
mock_videos = [
    {
        "id": 1,
        "filename": "test_video_1.mp4",
        "file_path": "/uploads/test_video_1.mp4",
        "status": "processed",
        "upload_date": "2025-09-12T08:00:00Z",
        "size": 1024576,
        "duration": 30.0,
        "fps": 30.0
    },
    {
        "id": 2,
        "filename": "test_video_2.mp4", 
        "file_path": "/uploads/test_video_2.mp4",
        "status": "processed",
        "upload_date": "2025-09-12T07:30:00Z",
        "size": 2048192,
        "duration": 45.0,
        "fps": 30.0
    }
]

mock_detection_results = [
    {
        "id": 1,
        "video_id": 1,
        "frame_number": 150,
        "timestamp": 5.0,
        "detections": [
            {
                "class": "person",
                "confidence": 0.85,
                "bbox": [100, 100, 200, 300],
                "coordinates": {"x": 150, "y": 200, "width": 100, "height": 200}
            }
        ],
        "screenshot_path": "/screenshots/detection_1.jpg"
    },
    {
        "id": 2,
        "video_id": 1,
        "frame_number": 300,
        "timestamp": 10.0,
        "detections": [
            {
                "class": "car",
                "confidence": 0.92,
                "bbox": [50, 150, 300, 250],
                "coordinates": {"x": 175, "y": 200, "width": 250, "height": 100}
            }
        ],
        "screenshot_path": "/screenshots/detection_2.jpg"
    }
]

mock_datasets = [
    {
        "id": 1,
        "name": "Urban Traffic Dataset",
        "description": "Dataset containing urban traffic scenarios",
        "video_count": 2,
        "created_at": "2025-09-12T06:00:00Z",
        "status": "active"
    }
]

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "AI Model Validation Platform - Integration Test Server",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running",
            "database": "connected",
            "file_system": "available"
        }
    }

# Ground truth endpoints - No more 404 errors!
@app.get("/api/ground-truth/videos/available")
async def get_available_videos():
    """Get videos available for ground truth annotation - Fixed endpoint!"""
    return {
        "success": True,
        "videos": mock_videos,
        "total": len(mock_videos),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/ground-truth/videos/{video_id}")
async def get_video_details(video_id: int):
    """Get specific video details"""
    video = next((v for v in mock_videos if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {
        "success": True,
        "video": video,
        "detection_results": [d for d in mock_detection_results if d["video_id"] == video_id]
    }

# Dataset endpoints
@app.get("/api/datasets")
async def get_datasets():
    """Get all datasets"""
    return {
        "success": True,
        "datasets": mock_datasets,
        "total": len(mock_datasets)
    }

@app.get("/api/datasets/{dataset_id}")
async def get_dataset(dataset_id: int):
    """Get specific dataset"""
    dataset = next((d for d in mock_datasets if d["id"] == dataset_id), None)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {
        "success": True,
        "dataset": dataset
    }

@app.get("/api/datasets/{dataset_id}/videos")
async def get_dataset_videos(dataset_id: int):
    """Get videos in a dataset"""
    return {
        "success": True,
        "videos": mock_videos,
        "dataset_id": dataset_id,
        "total": len(mock_videos)
    }

# Video management endpoints
@app.get("/api/videos")
async def get_videos():
    """Get all videos"""
    return {
        "success": True,
        "videos": mock_videos,
        "total": len(mock_videos)
    }

@app.get("/api/videos/{video_id}")
async def get_video(video_id: int):
    """Get specific video"""
    video = next((v for v in mock_videos if v["id"] == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {
        "success": True,
        "video": video
    }

# Detection results endpoints
@app.get("/api/videos/{video_id}/detections")
async def get_video_detections(video_id: int):
    """Get detection results for a video"""
    detections = [d for d in mock_detection_results if d["video_id"] == video_id]
    return {
        "success": True,
        "detections": detections,
        "video_id": video_id,
        "total": len(detections)
    }

# Test execution endpoints for HIL testing
@app.post("/api/test-sessions")
async def create_test_session(request: Request):
    """Create new test session"""
    data = await request.json()
    session_id = 12345  # Mock session ID
    return {
        "success": True,
        "session_id": session_id,
        "status": "created",
        "configuration": data,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/test-sessions/{session_id}/status")
async def get_test_session_status(session_id: int):
    """Get test session status"""
    return {
        "success": True,
        "session_id": session_id,
        "status": "running",
        "progress": 0.65,
        "current_video": "test_video_1.mp4",
        "detections_processed": 150,
        "timestamp": datetime.now().isoformat(),
        "hardware_status": {
            "labjack_connected": True,
            "timing_precision": "sub_millisecond",
            "signal_quality": "excellent"
        }
    }

# WebSocket status endpoint
@app.get("/api/websocket/status")
async def get_websocket_status():
    """Get WebSocket connection status"""
    return {
        "status": "available",
        "endpoint": "ws://localhost:8000/ws",
        "connected_clients": 0,
        "last_message": datetime.now().isoformat()
    }

# Dashboard endpoints - CRITICAL MISSING ENDPOINTS
@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics - FIXES 404 ERROR"""
    return {
        "success": True,
        "stats": {
            "total_projects": 10,
            "total_videos": 2,
            "total_annotations": 45,
            "total_test_sessions": 3,
            "active_sessions": 1,
            "completed_tests": 15,
            "success_rate": 0.87,
            "avg_processing_time": 25.3
        },
        "recent_activity": [
            {"action": "video_upload", "timestamp": datetime.now().isoformat()},
            {"action": "annotation_created", "timestamp": datetime.now().isoformat()}
        ]
    }

@app.get("/api/dashboard/recent-activity")
async def get_recent_activity():
    """Get recent dashboard activity"""
    return {
        "success": True,
        "activities": [
            {
                "id": 1,
                "type": "video_upload",
                "description": "New video uploaded: test_video_1.mp4",
                "timestamp": "2025-09-12T08:00:00Z",
                "user": "system"
            },
            {
                "id": 2,
                "type": "test_completed",
                "description": "HIL test session completed successfully",
                "timestamp": "2025-09-12T07:30:00Z", 
                "user": "system"
            }
        ]
    }

@app.get("/api/dashboard/system-health")
async def get_system_health():
    """Get system health status"""
    return {
        "success": True,
        "health": {
            "status": "healthy",
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 23.1,
            "database_status": "connected",
            "api_response_time": 28.5,
            "active_connections": 3
        }
    }

# Projects endpoints - MISSING CRITICAL ENDPOINTS  
@app.get("/api/projects")
async def get_projects():
    """Get all projects"""
    return {
        "success": True,
        "projects": [
            {
                "id": 1,
                "name": "Urban Traffic Analysis",
                "description": "Analysis of urban traffic patterns",
                "created_at": "2025-09-12T06:00:00Z",
                "video_count": 2,
                "status": "active"
            },
            {
                "id": 2, 
                "name": "Highway Detection Tests",
                "description": "Highway VRU detection validation",
                "created_at": "2025-09-11T10:00:00Z",
                "video_count": 1,
                "status": "active"
            }
        ],
        "total": 2
    }

@app.get("/api/projects/{project_id}")
async def get_project(project_id: int):
    """Get specific project details"""
    return {
        "success": True,
        "project": {
            "id": project_id,
            "name": "Urban Traffic Analysis",
            "description": "Analysis of urban traffic patterns", 
            "created_at": "2025-09-12T06:00:00Z",
            "video_count": 2,
            "status": "active"
        }
    }

@app.get("/api/projects/{project_id}/videos")
async def get_project_videos(project_id: int):
    """Get videos for a specific project"""
    return {
        "success": True,
        "videos": mock_videos,
        "project_id": project_id,
        "total": len(mock_videos)
    }

# Video annotations endpoints - CRITICAL FOR DATASET PAGE
@app.get("/api/videos/{video_id}/annotations")
async def get_video_annotations(video_id: int):
    """Get annotations for a specific video"""
    return {
        "success": True,
        "annotations": [
            {
                "id": 1,
                "video_id": video_id,
                "frame_number": 150,
                "timestamp": 5.0,
                "bbox": {"x": 100, "y": 100, "width": 100, "height": 200},
                "class": "person",
                "confidence": 0.95,
                "created_by": "system",
                "created_at": "2025-09-12T08:00:00Z"
            },
            {
                "id": 2,
                "video_id": video_id,
                "frame_number": 300,
                "timestamp": 10.0,
                "bbox": {"x": 50, "y": 150, "width": 250, "height": 100},
                "class": "car", 
                "confidence": 0.92,
                "created_by": "system",
                "created_at": "2025-09-12T08:30:00Z"
            }
        ],
        "total": 2
    }

@app.get("/api/videos/{video_id}/ground-truth")
async def get_video_ground_truth(video_id: int):
    """Get ground truth for a specific video"""
    return {
        "success": True,
        "ground_truth": {
            "video_id": video_id,
            "annotations": [
                {
                    "frame": 150,
                    "objects": [{"class": "person", "bbox": [100, 100, 200, 300]}]
                },
                {
                    "frame": 300, 
                    "objects": [{"class": "car", "bbox": [50, 150, 300, 250]}]
                }
            ]
        }
    }

# Test sessions endpoints
@app.get("/api/test-sessions")  
async def get_test_sessions():
    """Get all test sessions"""
    return {
        "success": True,
        "sessions": [
            {
                "id": 12345,
                "name": "HIL Test Session 1",
                "status": "completed",
                "created_at": "2025-09-12T07:00:00Z",
                "video_count": 2,
                "success_rate": 0.87
            }
        ],
        "total": 1
    }

@app.get("/api/test-sessions/{session_id}/results")
async def get_session_results(session_id: int):
    """Get test session results"""
    return {
        "success": True,
        "session_id": session_id,
        "results": {
            "total_detections": 150,
            "true_positives": 130,
            "false_positives": 12,
            "false_negatives": 8,
            "precision": 0.915,
            "recall": 0.942,
            "f1_score": 0.928
        }
    }

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    print("🚀 Starting Integration Test Server...")
    print("📊 APIs available:")
    print("  - Ground Truth: http://localhost:8000/api/ground-truth/videos/available")
    print("  - Datasets: http://localhost:8000/api/datasets")  
    print("  - Videos: http://localhost:8000/api/videos")
    print("  - Health: http://localhost:8000/health")
    print("🌐 CORS enabled for frontend on ports 3000/3001")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )