#!/usr/bin/env python3
"""
Minimal server to test basic functionality
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Model Validation Platform - Minimal",
    description="Minimal version for testing",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "AI Model Validation Platform API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Server is running"}

@app.get("/test-imports")
async def test_imports():
    """Test that all key imports work"""
    try:
        import jwt
        import passlib
        from sqlalchemy import create_engine
        return {
            "jwt": "✅ Working",
            "passlib": "✅ Working", 
            "sqlalchemy": "✅ Working",
            "status": "All imports successful"
        }
    except Exception as e:
        return {"error": str(e), "status": "Import failed"}

if __name__ == "__main__":
    logger.info("Starting minimal server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,  # Use different port to avoid conflicts
        log_level="info"
    )