"""
Enhanced Test Diagnostics API
Provides comprehensive diagnostics for Enhanced Test page troubleshooting
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from database import SessionLocal
from models import Project, Video, TestSession, DetectionEvent
from services.labjack_service import get_labjack_service
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enhanced-test-diagnostics", tags=["Enhanced Test Diagnostics"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/health-check")
async def enhanced_test_health_check(db: Session = Depends(get_db)):
    """Comprehensive health check for Enhanced Test functionality"""
    
    diagnostics = {
        "timestamp": datetime.utcnow().isoformat(),
        "overall_status": "checking",
        "components": {}
    }
    
    try:
        # 1. Database connectivity check
        try:
            project_count = db.query(func.count(Project.id)).scalar()
            video_count = db.query(func.count(Video.id)).scalar()
            session_count = db.query(func.count(TestSession.id)).scalar()
            
            diagnostics["components"]["database"] = {
                "status": "healthy",
                "project_count": project_count,
                "video_count": video_count,
                "session_count": session_count,
                "message": "Database connectivity confirmed"
            }
        except Exception as e:
            diagnostics["components"]["database"] = {
                "status": "error",
                "error": str(e),
                "message": "Database connectivity failed"
            }
        
        # 2. LabJack service check
        try:
            labjack_service = get_labjack_service()
            labjack_status = labjack_service.get_status()
            
            diagnostics["components"]["labjack"] = {
                "status": "connected" if labjack_status.connected else "disconnected",
                "mode": labjack_status.mode.value,
                "connection_status": labjack_status.status.value,
                "device_info": labjack_status.device_info,
                "streaming": labjack_status.streaming,
                "message": f"LabJack in {labjack_status.mode.value} mode"
            }
        except Exception as e:
            diagnostics["components"]["labjack"] = {
                "status": "error",
                "error": str(e),
                "message": "LabJack service check failed"
            }
        
        # 3. Model relationship check
        try:
            # Test DetectionEvent.video relationship
            test_query = db.query(DetectionEvent).join(DetectionEvent.video).limit(1).all()
            
            diagnostics["components"]["relationships"] = {
                "status": "healthy",
                "detection_video_relationship": "working",
                "message": "Database relationships verified"
            }
        except Exception as e:
            diagnostics["components"]["relationships"] = {
                "status": "warning",
                "detection_video_relationship": "issue_detected",
                "error": str(e),
                "message": "Some database relationships may have issues"
            }
        
        # 4. Session creation capability check
        try:
            # Check if we can create a test session (dry run)
            projects_with_videos = db.query(Project).join(Project.videos).limit(1).all()
            
            if projects_with_videos:
                diagnostics["components"]["session_creation"] = {
                    "status": "ready",
                    "projects_available": len(projects_with_videos),
                    "message": "Session creation should work - projects and videos available"
                }
            else:
                diagnostics["components"]["session_creation"] = {
                    "status": "warning",
                    "projects_available": 0,
                    "message": "No projects with videos found - session creation may fail"
                }
                
        except Exception as e:
            diagnostics["components"]["session_creation"] = {
                "status": "error",
                "error": str(e),
                "message": "Session creation capability check failed"
            }
        
        # 5. Overall status determination
        component_statuses = [comp["status"] for comp in diagnostics["components"].values()]
        
        if all(status == "healthy" for status in component_statuses):
            diagnostics["overall_status"] = "healthy"
            diagnostics["message"] = "All Enhanced Test components are working correctly"
        elif any(status == "error" for status in component_statuses):
            diagnostics["overall_status"] = "error"
            diagnostics["message"] = "Critical errors detected - Enhanced Test may not work properly"
        else:
            diagnostics["overall_status"] = "warning"
            diagnostics["message"] = "Some issues detected but Enhanced Test should work with limitations"
        
        return diagnostics
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        diagnostics["overall_status"] = "error"
        diagnostics["error"] = str(e)
        diagnostics["message"] = "Health check failed"
        return diagnostics

@router.get("/connection-test")
async def test_labjack_connection():
    """Test LabJack connection and provide detailed status"""
    
    try:
        labjack_service = get_labjack_service()
        
        # Get current status
        status = labjack_service.get_status()
        
        # Try to reconnect if not connected
        if not status.connected:
            logger.info("Attempting LabJack reconnection...")
            connection_result = await labjack_service.connect()
            status = labjack_service.get_status()  # Get updated status
            
            return {
                "reconnection_attempted": True,
                "connection_successful": connection_result,
                "current_status": {
                    "mode": status.mode.value,
                    "connected": status.connected,
                    "device_info": status.device_info,
                    "streaming": status.streaming
                },
                "message": f"Reconnection {'successful' if connection_result else 'failed'} - now in {status.mode.value} mode"
            }
        else:
            return {
                "reconnection_attempted": False,
                "connection_successful": True,
                "current_status": {
                    "mode": status.mode.value,
                    "connected": status.connected,
                    "device_info": status.device_info,
                    "streaming": status.streaming
                },
                "message": f"Already connected in {status.mode.value} mode"
            }
            
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return {
            "reconnection_attempted": True,
            "connection_successful": False,
            "error": str(e),
            "message": "Connection test failed"
        }

@router.get("/project-video-analysis")
async def analyze_project_video_relationships(db: Session = Depends(get_db)):
    """Analyze project-video relationships for session creation"""
    
    try:
        # Get projects with video counts
        projects_query = db.query(
            Project.id,
            Project.name,
            func.count(Video.id).label('video_count')
        ).outerjoin(Video).group_by(Project.id, Project.name).all()
        
        projects_analysis = []
        for project_id, project_name, video_count in projects_query:
            projects_analysis.append({
                "project_id": project_id,
                "project_name": project_name,
                "video_count": video_count,
                "session_ready": video_count > 0
            })
        
        # Count test sessions
        total_sessions = db.query(func.count(TestSession.id)).scalar()
        
        return {
            "total_projects": len(projects_analysis),
            "projects_with_videos": len([p for p in projects_analysis if p["video_count"] > 0]),
            "total_sessions": total_sessions,
            "projects": projects_analysis,
            "ready_for_enhanced_test": len([p for p in projects_analysis if p["video_count"] > 0]) > 0
        }
        
    except Exception as e:
        logger.error(f"Project-video analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

# Export the router
enhanced_test_diagnostics_router = router
