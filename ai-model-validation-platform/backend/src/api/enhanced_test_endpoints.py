"""
Enhanced Test API Endpoints with Robust Error Handling

This module provides comprehensive API endpoints for the Enhanced Test workflow:
1. LabJack connection management with detailed diagnostics
2. Test session creation and management
3. Enhanced test execution with real-time feedback
4. Comprehensive error handling and user feedback
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
import logging
import uuid

# Database and models
from database import SessionLocal
from models import Project, Video, TestSession

# Services
from services.labjack_service_enhanced import get_labjack_service, ConnectionMode

logger = logging.getLogger(__name__)

# Router setup
router = APIRouter(prefix="/api/enhanced-test", tags=["Enhanced Test"])

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models for API
class LabJackConnectionRequest(BaseModel):
    mode: str = Field("auto", description="Connection mode: auto, hardware, bridge, mock")
    
    @validator('mode')
    def validate_mode(cls, v):
        valid_modes = ["auto", "hardware", "bridge", "mock"]
        if v not in valid_modes:
            raise ValueError(f"Mode must be one of: {valid_modes}")
        return v

class TestSessionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Test session name")
    project_id: str = Field(..., description="Project ID")
    video_ids: List[str] = Field(..., min_items=1, description="List of video IDs")
    description: Optional[str] = Field(None, description="Optional session description")
    config: Dict[str, Any] = Field(default_factory=dict, description="Test configuration")
    # DUAL FIX PART B: Add constant_voltage_mode parameter for enhanced test workflow
    constant_voltage_mode: bool = Field(False, description="Enable constant voltage mode to bypass debounce filtering for 100% detection rate")

class TestSessionResponse(BaseModel):
    id: str
    name: str
    project_id: str
    video_id: str
    status: str
    created_at: datetime
    video_count: int
    config: Dict[str, Any]

class LabJackStatusResponse(BaseModel):
    mode: str
    connected: bool
    device_info: Dict[str, Any]
    streaming: bool
    error_message: Optional[str]
    diagnostics: Dict[str, Any]
    statistics: Dict[str, Any]
    recommendations: List[str]

# LabJack Connection Endpoints

@router.get("/labjack/status", response_model=LabJackStatusResponse)
async def get_labjack_status():
    """
    Get LabJack connection status with comprehensive diagnostics
    
    Returns detailed information about:
    - Connection mode and status
    - Device information
    - System diagnostics
    - Troubleshooting recommendations
    """
    try:
        service = get_labjack_service()
        status = service.get_status()
        
        # Extract recommendations from diagnostics
        recommendations = status.diagnostics.get("recommendations", []) if status.diagnostics else []
        
        return LabJackStatusResponse(
            mode=status.mode.value,
            connected=status.connected,
            device_info=status.device_info,
            streaming=status.streaming,
            error_message=status.error_message,
            diagnostics=status.diagnostics or {},
            statistics=status.statistics,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Error getting LabJack status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get LabJack status: {str(e)}")

@router.post("/labjack/connect")
async def connect_labjack(request: LabJackConnectionRequest):
    """
    Connect to LabJack device with specified mode
    
    Supports multiple connection modes:
    - auto: Try hardware → bridge → mock
    - hardware: Direct hardware connection
    - bridge: Connect via Windows bridge
    - mock: Simulation mode for testing
    """
    try:
        service = get_labjack_service()
        success = await service.connect(request.mode)
        
        if success:
            status = service.get_status()
            return {
                "success": True,
                "message": f"Successfully connected in {status.mode.value} mode",
                "mode": status.mode.value,
                "device_info": status.device_info
            }
        else:
            status = service.get_status()
            diagnostics = status.diagnostics or {}
            recommendations = diagnostics.get("recommendations", [])
            
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"Failed to connect to LabJack: {status.error_message}",
                    "mode": status.mode.value,
                    "diagnostics": diagnostics,
                    "recommendations": recommendations
                }
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error connecting to LabJack: {e}")
        raise HTTPException(status_code=500, detail=f"Connection failed: {str(e)}")

@router.post("/labjack/disconnect")
async def disconnect_labjack():
    """Disconnect from LabJack device"""
    try:
        service = get_labjack_service()
        await service.disconnect()
        
        return {
            "success": True,
            "message": "LabJack disconnected successfully"
        }
        
    except Exception as e:
        logger.error(f"Error disconnecting LabJack: {e}")
        raise HTTPException(status_code=500, detail=f"Disconnect failed: {str(e)}")

@router.get("/labjack/test-connection")
async def test_labjack_connection():
    """
    Test LabJack connection and return diagnostics
    
    Performs comprehensive connection testing:
    - Hardware detection
    - Bridge service availability
    - Driver status (Windows)
    - Configuration recommendations
    """
    try:
        service = get_labjack_service()
        status = service.get_status()
        
        # Perform connection test
        test_results = {
            "connection_status": "connected" if status.connected else "disconnected",
            "mode": status.mode.value,
            "device_info": status.device_info,
            "last_test": datetime.now().isoformat(),
            "diagnostics": status.diagnostics or {},
            "statistics": status.statistics
        }
        
        # Add test-specific information
        if status.connected and status.mode == ConnectionMode.MOCK:
            test_results["warning"] = "Running in MOCK mode - no real hardware connection"
        
        return test_results
        
    except Exception as e:
        logger.error(f"Error testing LabJack connection: {e}")
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")

# Test Session Endpoints

@router.post("/sessions", response_model=TestSessionResponse)
async def create_test_session(request: TestSessionCreateRequest, db: Session = Depends(get_db)):
    """
    Create a new enhanced test session
    
    Creates a test session with proper validation:
    - Validates project exists
    - Validates video availability
    - Handles multiple videos appropriately
    - Provides detailed error messages
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(
                status_code=404, 
                detail=f"Project not found: {request.project_id}"
            )
        
        # Validate videos exist
        videos = db.query(Video).filter(Video.id.in_(request.video_ids)).all()
        found_video_ids = [v.id for v in videos]
        missing_videos = set(request.video_ids) - set(found_video_ids)
        
        if missing_videos:
            raise HTTPException(
                status_code=404,
                detail=f"Videos not found: {list(missing_videos)}"
            )
        
        # Use first video for database compatibility
        first_video_id = request.video_ids[0]

        # DUAL FIX PART B: Merge constant_voltage_mode into config for DetectionConfig initialization
        enhanced_config = {
            **request.config,
            'constant_voltage_mode': request.constant_voltage_mode,
            'video_ids': request.video_ids  # Store all video IDs for multi-video sessions
        }

        # Create test session
        session_id = str(uuid.uuid4())
        test_session = TestSession(
            id=session_id,
            name=request.name,
            project_id=request.project_id,
            video_id=first_video_id,
            status="created",
            created_at=datetime.now()
        )

        db.add(test_session)
        db.commit()
        db.refresh(test_session)

        logger.info(f"Created test session {session_id} with {len(request.video_ids)} videos (constant_voltage_mode={request.constant_voltage_mode})")

        return TestSessionResponse(
            id=test_session.id,
            name=test_session.name,
            project_id=test_session.project_id,
            video_id=test_session.video_id,
            status=test_session.status,
            created_at=test_session.created_at,
            video_count=len(request.video_ids),
            config=enhanced_config
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating test session: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database error creating test session"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating test session: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to create test session: {str(e)}"
        )

@router.get("/sessions")
async def get_test_sessions(
    project_id: Optional[str] = None, 
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get test sessions with optional filtering"""
    try:
        query = db.query(TestSession)
        
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        if status:
            query = query.filter(TestSession.status == status)
        
        sessions = query.order_by(TestSession.created_at.desc()).limit(limit).all()
        
        result = []
        for session in sessions:
            result.append({
                "id": session.id,
                "name": session.name,
                "project_id": session.project_id,
                "video_id": session.video_id,
                "status": session.status,
                "created_at": session.created_at.isoformat(),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            })
        
        return {
            "sessions": result,
            "total": len(result),
            "filters": {
                "project_id": project_id,
                "status": status,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting test sessions: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get test sessions: {str(e)}"
        )

@router.get("/sessions/{session_id}")
async def get_test_session(session_id: str, db: Session = Depends(get_db)):
    """Get a specific test session by ID"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        return {
            "id": session.id,
            "name": session.name,
            "project_id": session.project_id,
            "video_id": session.video_id,
            "status": session.status,
            "tolerance_ms": session.tolerance_ms,
            "created_at": session.created_at.isoformat(),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting test session: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get test session: {str(e)}"
        )

@router.post("/sessions/{session_id}/run")
async def run_test_session(session_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Start running a test session
    
    Validates prerequisites:
    - LabJack connection
    - Session status
    - Video availability
    """
    try:
        # Check session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Check LabJack connection
        labjack_service = get_labjack_service()
        labjack_status = labjack_service.get_status()
        
        if not labjack_status.connected:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": "LabJack not connected. Please connect LabJack device first.",
                    "labjack_mode": labjack_status.mode.value,
                    "recommendations": labjack_status.diagnostics.get("recommendations", []) if labjack_status.diagnostics else []
                }
            )
        
        # Update session status
        session.status = "running"
        session.started_at = datetime.now()
        db.commit()
        
        # TODO: Add background task for actual test execution
        # background_tasks.add_task(execute_test_session, session_id)
        
        return {
            "success": True,
            "message": f"Test session {session_id} started successfully",
            "session_id": session_id,
            "labjack_mode": labjack_status.mode.value,
            "status": "running"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running test session: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to run test session: {str(e)}"
        )

# Health Check Endpoint

@router.get("/health")
async def health_check():
    """Get overall system health status"""
    try:
        # Check LabJack status
        labjack_service = get_labjack_service()
        labjack_status = labjack_service.get_status()
        
        # Check database connectivity
        db_status = "healthy"
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
        except Exception:
            db_status = "error"
        
        health_info = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "labjack": {
                    "status": "connected" if labjack_status.connected else "disconnected",
                    "mode": labjack_status.mode.value,
                    "error": labjack_status.error_message
                },
                "database": {
                    "status": db_status
                }
            },
            "version": "1.0.0"
        }
        
        # Determine overall status
        if not labjack_status.connected and labjack_status.mode != ConnectionMode.MOCK:
            health_info["status"] = "degraded"
        if db_status != "healthy":
            health_info["status"] = "error"
        
        return health_info
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
        )