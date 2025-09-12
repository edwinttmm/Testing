#!/usr/bin/env python3
"""
Minimal Backend Test Server
Creates a simplified FastAPI backend for testing API endpoints
"""

import asyncio
import os
import sqlite3
import json
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Simple data models
class Project(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = ""
    status: str = "active"

class Video(BaseModel):
    id: Optional[int] = None
    filename: str
    project_id: int
    file_path: Optional[str] = ""
    uploaded_at: Optional[str] = ""

class HealthResponse(BaseModel):
    status: str
    message: str
    database: str

# Create FastAPI app
app = FastAPI(
    title="AI Model Validation Platform - Test API",
    description="Minimal test version for deployment testing",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DB_PATH = "/tmp/test_backend.db"

def init_database():
    """Initialize SQLite database with test tables"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create videos table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                project_id INTEGER,
                file_path TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects (id)
            )
        """)
        
        # Insert test data
        cursor.execute("SELECT COUNT(*) FROM projects")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO projects (name, description, status) 
                VALUES ('Test Project 1', 'Automated test project', 'active')
            """)
            cursor.execute("""
                INSERT INTO projects (name, description, status) 
                VALUES ('Test Project 2', 'Second test project', 'active')
            """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_status = "connected" if os.path.exists(DB_PATH) else "disconnected"
    return HealthResponse(
        status="healthy",
        message="Test backend is running",
        database=db_status
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AI Model Validation Platform Test API", "status": "running"}

@app.get("/api/projects")
async def get_projects():
    """Get all projects"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, description, status FROM projects")
        rows = cursor.fetchall()
        conn.close()
        
        projects = [
            {"id": row[0], "name": row[1], "description": row[2], "status": row[3]}
            for row in rows
        ]
        return {"projects": projects, "count": len(projects)}
        
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects")
async def create_project(project: Project):
    """Create a new project"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (name, description, status)
            VALUES (?, ?, ?)
        """, (project.name, project.description or "", project.status))
        project_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {"id": project_id, "name": project.name, "status": "created"}
        
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/videos")
async def get_videos():
    """Get all videos"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT v.id, v.filename, v.project_id, v.file_path, v.uploaded_at, p.name as project_name
            FROM videos v 
            LEFT JOIN projects p ON v.project_id = p.id
        """)
        rows = cursor.fetchall()
        conn.close()
        
        videos = [
            {
                "id": row[0], "filename": row[1], "project_id": row[2], 
                "file_path": row[3], "uploaded_at": row[4], "project_name": row[5]
            }
            for row in rows
        ]
        return {"videos": videos, "count": len(videos)}
        
    except Exception as e:
        logger.error(f"Error fetching videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/videos/upload")
async def upload_video(file: UploadFile = File(...), project_id: int = 1):
    """Upload video file (mock implementation)"""
    try:
        # Validate file type
        if not file.filename.endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Mock file processing - in real implementation would save file
        file_content = await file.read()
        file_size = len(file_content)
        
        # Save to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO videos (filename, project_id, file_path)
            VALUES (?, ?, ?)
        """, (file.filename, project_id, f"/tmp/uploads/{file.filename}"))
        video_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "id": video_id,
            "filename": file.filename,
            "project_id": project_id,
            "size": file_size,
            "status": "uploaded"
        }
        
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get project count
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        
        # Get video count
        cursor.execute("SELECT COUNT(*) FROM videos")
        video_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_projects": project_count,
            "total_videos": video_count,
            "active_sessions": 0,
            "completed_tests": 0,
            "system_status": "operational"
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/validation/status")
async def get_validation_status():
    """Get validation system status"""
    return {
        "status": "operational",
        "models_loaded": True,
        "detection_pipeline": "active",
        "last_check": "2025-08-27T11:45:00Z"
    }

@app.get("/api/detection/models")
async def get_detection_models():
    """Get available detection models"""
    return {
        "models": [
            {"name": "YOLOv8n", "status": "available", "type": "object_detection"},
            {"name": "YOLOv8s", "status": "available", "type": "object_detection"}
        ]
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": f"Endpoint not found: {request.url.path}"}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

async def startup_event():
    """Application startup tasks"""
    logger.info("Starting minimal test backend...")
    if not init_database():
        logger.error("Failed to initialize database")
        sys.exit(1)

# Add startup event
@app.on_event("startup")
async def startup():
    await startup_event()

def main():
    """Main entry point"""
    logger.info("🚀 Starting Minimal Backend Test Server")
    
    # Initialize database
    init_database()
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )

if __name__ == "__main__":
    main()