"""
Integration script to add annotation system routes to main FastAPI application
"""

from fastapi import FastAPI
import sys
import os

# Add current directory to Python path
sys.path.append(os.path.dirname(__file__))

# Import the annotation routes
from annotation_routes import router as annotation_router

def integrate_annotation_system(app: FastAPI):
    """
    Integrate the annotation system into the main FastAPI application
    """
    
    # Include annotation routes
    app.include_router(annotation_router)
    
    # Import and register enhanced WebSocket events
    from websocket_enhanced import register_enhanced_websocket_events
    from socketio_server import sio
    
    # Register enhanced WebSocket events
    register_enhanced_websocket_events(sio)
    
    print("✅ Annotation system integrated successfully!")
    print("✅ Enhanced WebSocket events registered!")
    print("✅ New endpoints available:")
    print("   - POST /api/videos/{video_id}/annotations")
    print("   - GET /api/videos/{video_id}/annotations") 
    print("   - PUT /api/annotations/{annotation_id}")
    print("   - DELETE /api/annotations/{annotation_id}")
    print("   - PATCH /api/annotations/{annotation_id}/validate")
    print("   - POST /api/annotation-sessions")
    print("   - POST /api/projects/{project_id}/videos/link")
    print("   - GET /api/ground-truth/videos/available")
    print("   - GET /api/videos/{video_id}/annotations/export")

# Usage: Add this to main.py after app creation
# from integration_main import integrate_annotation_system
# integrate_annotation_system(app)