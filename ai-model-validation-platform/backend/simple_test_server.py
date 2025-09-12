#!/usr/bin/env python3
"""
Simple Test Server for AI Model Validation Platform
Minimal FastAPI server to test basic startup functionality
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging
import os

# Simple logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create minimal FastAPI app
app = FastAPI(
    title="AI Model Validation Platform - Test Server",
    description="Minimal test server for startup validation",
    version="1.0.0"
)

# Basic CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Model Validation Platform - Test Server",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ai-model-validation-backend",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "api": "ok",
            "server": "ok"
        }
    }

@app.get("/api/test")
async def test_endpoint():
    """Test API endpoint"""
    return {
        "message": "Test endpoint working",
        "api_status": "operational",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting simple test server...")
    uvicorn.run(
        "simple_test_server:app",
        host="0.0.0.0",
        port=8001,
        reload=False
    )