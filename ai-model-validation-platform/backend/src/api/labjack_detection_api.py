"""
LabJack Detection API Endpoints

This module provides REST API endpoints for independent LabJack hardware detection
storage, retrieval, and temporal synchronization with video playback systems.

Features:
- Independent LabJack detection storage
- Video detection storage and correlation
- Temporal synchronization analysis
- Configurable detection windows
- Real-time vs recorded time comparison
- Performance monitoring and analytics
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text, desc, asc
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, validator
import uuid
import logging
from decimal import Decimal

from database import SessionLocal
from src.models.labjack_models import (
    LabJackDetection, VideoDetection, DetectionSynchronization,
    DetectionConfiguration, TemporalAnalysisResult,
    DetectionSourceEnum, DetectionStatusEnum, SynchronizationStatusEnum
)

logger = logging.getLogger(__name__)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create router
router = APIRouter(prefix="/api/labjack-detections", tags=["LabJack Detections"])


# Pydantic schemas for API requests/responses

class LabJackDetectionCreate(BaseModel):
    """Schema for creating LabJack detection"""
    session_id: str = Field(..., description="Test session ID")
    device_id: str = Field(..., description="LabJack device identifier")
    hardware_timestamp: Optional[datetime] = Field(None, description="Hardware-generated timestamp")
    system_timestamp: Optional[datetime] = Field(None, description="System receive timestamp")
    monotonic_time: float = Field(..., description="Monotonic time for precise intervals")
    signal_value: float = Field(..., description="Raw signal value")
    threshold_value: float = Field(..., description="Detection threshold")
    channel: int = Field(..., ge=0, le=32, description="LabJack channel (0-32)")
    detection_confidence: float = Field(1.0, ge=0.0, le=1.0, description="Detection confidence")
    device_config: Optional[Dict[str, Any]] = Field(None, description="Device configuration")
    sampling_rate: Optional[float] = Field(None, description="Sampling rate in Hz")
    signal_to_noise_ratio: Optional[float] = Field(None, description="Signal quality metric")
    correlation_window_ms: int = Field(100, ge=1, le=10000, description="Detection window in ms")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator('hardware_timestamp', 'system_timestamp', pre=True, always=True)
    def set_default_timestamp(cls, v):
        if v is None:
            return datetime.now(timezone.utc)
        return v


class LabJackDetectionResponse(BaseModel):
    """Schema for LabJack detection response"""
    id: str
    session_id: str
    device_id: str
    hardware_timestamp: datetime
    system_timestamp: datetime
    monotonic_time: float
    signal_value: float
    threshold_value: float
    channel: int
    detection_confidence: float
    status: str
    source: str
    correlation_window_ms: int
    matched_detection_id: Optional[str]
    created_at: datetime
    is_valid: bool
    metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class VideoDetectionCreate(BaseModel):
    """Schema for creating video detection"""
    session_id: str = Field(..., description="Test session ID")
    video_id: str = Field(..., description="Video ID")
    video_timestamp: float = Field(..., description="Video time in seconds")
    playback_timestamp: Optional[datetime] = Field(None, description="Real playback time")
    frame_number: Optional[int] = Field(None, description="Video frame number")
    detection_type: str = Field(..., description="Type of video detection")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="Detection confidence")
    bounding_box: Optional[Dict[str, Any]] = Field(None, description="Bounding box coordinates")
    playback_speed: float = Field(1.0, description="Video playback speed")
    processing_delay_ms: float = Field(0.0, description="Processing delay in ms")
    correlation_window_ms: int = Field(100, ge=1, le=10000, description="Detection window in ms")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @validator('playback_timestamp', pre=True, always=True)
    def set_default_timestamp(cls, v):
        if v is None:
            return datetime.now(timezone.utc)
        return v


class VideoDetectionResponse(BaseModel):
    """Schema for video detection response"""
    id: str
    session_id: str
    video_id: str
    video_timestamp: float
    playback_timestamp: datetime
    frame_number: Optional[int]
    detection_type: str
    confidence_score: float
    bounding_box: Optional[Dict[str, Any]]
    playback_speed: float
    processing_delay_ms: float
    status: str
    source: str
    correlation_window_ms: int
    matched_labjack_id: Optional[str]
    created_at: datetime
    is_valid: bool
    metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class DetectionConfigurationCreate(BaseModel):
    """Schema for creating detection configuration"""
    name: str = Field(..., description="Configuration name")
    session_id: Optional[str] = Field(None, description="Session ID (null for global)")
    labjack_window_ms: int = Field(100, ge=1, le=10000, description="LabJack window in ms")
    video_window_ms: int = Field(100, ge=1, le=10000, description="Video window in ms")
    synchronization_tolerance_ms: int = Field(50, ge=1, le=1000, description="Sync tolerance in ms")
    signal_threshold: float = Field(3.0, description="Signal detection threshold")
    confidence_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Confidence threshold")
    quality_threshold: float = Field(0.8, ge=0.0, le=1.0, description="Quality threshold")
    correlation_method: str = Field("pearson", description="Correlation algorithm")
    is_default: bool = Field(False, description="Is default configuration")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DetectionConfigurationResponse(BaseModel):
    """Schema for detection configuration response"""
    id: str
    name: str
    session_id: Optional[str]
    labjack_window_ms: int
    video_window_ms: int
    synchronization_tolerance_ms: int
    signal_threshold: float
    confidence_threshold: float
    quality_threshold: float
    correlation_method: str
    is_active: bool
    is_default: bool
    created_at: datetime
    metadata: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class SynchronizationRequest(BaseModel):
    """Schema for requesting synchronization analysis"""
    session_id: str = Field(..., description="Session ID to analyze")
    configuration_id: Optional[str] = Field(None, description="Configuration to use")
    time_range_start: Optional[datetime] = Field(None, description="Analysis start time")
    time_range_end: Optional[datetime] = Field(None, description="Analysis end time")
    force_reanalysis: bool = Field(False, description="Force reanalysis of existing matches")
    analysis_parameters: Optional[Dict[str, Any]] = Field(None, description="Custom parameters")


class SynchronizationResponse(BaseModel):
    """Schema for synchronization analysis response"""
    analysis_id: str
    session_id: str
    total_labjack_detections: int
    total_video_detections: int
    matched_detections: int
    unmatched_labjack: int
    unmatched_video: int
    mean_time_difference_ms: float
    synchronization_accuracy: float
    processing_time_seconds: float
    analysis_status: str
    warnings: List[str]
    metadata: Dict[str, Any]


# API Endpoints

@router.post("/labjack", response_model=LabJackDetectionResponse)
async def create_labjack_detection(
    detection: LabJackDetectionCreate,
    db: Session = Depends(get_db)
):
    """
    Store a LabJack hardware detection with high-precision timestamp
    
    This endpoint stores hardware detections independently of video playback,
    enabling later temporal synchronization analysis.
    """
    try:
        # Create detection record
        db_detection = LabJackDetection(
            id=str(uuid.uuid4()),
            session_id=detection.session_id,
            device_id=detection.device_id,
            hardware_timestamp=detection.hardware_timestamp,
            system_timestamp=detection.system_timestamp,
            monotonic_time=detection.monotonic_time,
            signal_value=detection.signal_value,
            threshold_value=detection.threshold_value,
            channel=detection.channel,
            detection_confidence=detection.detection_confidence,
            device_config=detection.device_config,
            sampling_rate=detection.sampling_rate,
            signal_to_noise_ratio=detection.signal_to_noise_ratio,
            correlation_window_ms=detection.correlation_window_ms,
            metadata=detection.metadata,
            status=DetectionStatusEnum.PENDING,
            source=DetectionSourceEnum.LABJACK_HARDWARE,
            is_valid=True
        )
        
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        logger.info(f"Created LabJack detection {db_detection.id} for session {detection.session_id}")
        return db_detection
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating LabJack detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating detection: {str(e)}")


@router.post("/video", response_model=VideoDetectionResponse)
async def create_video_detection(
    detection: VideoDetectionCreate,
    db: Session = Depends(get_db)
):
    """
    Store a video playback detection event for temporal comparison
    
    This endpoint stores detection events from video playback timeline
    for comparison with hardware detections.
    """
    try:
        # Create detection record
        db_detection = VideoDetection(
            id=str(uuid.uuid4()),
            session_id=detection.session_id,
            video_id=detection.video_id,
            video_timestamp=detection.video_timestamp,
            playback_timestamp=detection.playback_timestamp,
            frame_number=detection.frame_number,
            detection_type=detection.detection_type,
            confidence_score=detection.confidence_score,
            bounding_box=detection.bounding_box,
            playback_speed=detection.playback_speed,
            processing_delay_ms=detection.processing_delay_ms,
            correlation_window_ms=detection.correlation_window_ms,
            metadata=detection.metadata,
            status=DetectionStatusEnum.PENDING,
            source=DetectionSourceEnum.VIDEO_PLAYBACK,
            is_valid=True
        )
        
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        logger.info(f"Created video detection {db_detection.id} for session {detection.session_id}")
        return db_detection
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating video detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating detection: {str(e)}")


@router.get("/labjack/session/{session_id}", response_model=List[LabJackDetectionResponse])
async def get_labjack_detections(
    session_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retrieve LabJack detections for a session with filtering options
    """
    try:
        query = db.query(LabJackDetection).filter(LabJackDetection.session_id == session_id)
        
        # Apply filters
        if status:
            query = query.filter(LabJackDetection.status == status)
        if device_id:
            query = query.filter(LabJackDetection.device_id == device_id)
        if start_time:
            query = query.filter(LabJackDetection.hardware_timestamp >= start_time)
        if end_time:
            query = query.filter(LabJackDetection.hardware_timestamp <= end_time)
        
        # Order by timestamp and apply pagination
        detections = query.order_by(LabJackDetection.hardware_timestamp)\
                         .offset(offset)\
                         .limit(limit)\
                         .all()
        
        return detections
        
    except Exception as e:
        logger.error(f"Error retrieving LabJack detections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving detections: {str(e)}")


@router.get("/video/session/{session_id}", response_model=List[VideoDetectionResponse])
async def get_video_detections(
    session_id: str,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    video_id: Optional[str] = Query(None),
    start_time: Optional[float] = Query(None),
    end_time: Optional[float] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Retrieve video detections for a session with filtering options
    """
    try:
        query = db.query(VideoDetection).filter(VideoDetection.session_id == session_id)
        
        # Apply filters
        if status:
            query = query.filter(VideoDetection.status == status)
        if video_id:
            query = query.filter(VideoDetection.video_id == video_id)
        if start_time is not None:
            query = query.filter(VideoDetection.video_timestamp >= start_time)
        if end_time is not None:
            query = query.filter(VideoDetection.video_timestamp <= end_time)
        
        # Order by video timestamp and apply pagination
        detections = query.order_by(VideoDetection.video_timestamp)\
                         .offset(offset)\
                         .limit(limit)\
                         .all()
        
        return detections
        
    except Exception as e:
        logger.error(f"Error retrieving video detections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving detections: {str(e)}")


@router.post("/configurations", response_model=DetectionConfigurationResponse)
async def create_detection_configuration(
    config: DetectionConfigurationCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new detection configuration for temporal analysis
    """
    try:
        # Check if setting as default and unset existing defaults
        if config.is_default:
            db.query(DetectionConfiguration)\
              .filter(DetectionConfiguration.session_id == config.session_id)\
              .update({"is_default": False})
        
        # Create configuration
        db_config = DetectionConfiguration(
            id=str(uuid.uuid4()),
            name=config.name,
            session_id=config.session_id,
            labjack_window_ms=config.labjack_window_ms,
            video_window_ms=config.video_window_ms,
            synchronization_tolerance_ms=config.synchronization_tolerance_ms,
            signal_threshold=config.signal_threshold,
            confidence_threshold=config.confidence_threshold,
            quality_threshold=config.quality_threshold,
            correlation_method=config.correlation_method,
            is_default=config.is_default,
            metadata=config.metadata,
            is_active=True
        )
        
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        
        logger.info(f"Created detection configuration {db_config.id}")
        return db_config
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating detection configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating configuration: {str(e)}")


@router.get("/configurations", response_model=List[DetectionConfigurationResponse])
async def get_detection_configurations(
    session_id: Optional[str] = Query(None),
    include_global: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Retrieve detection configurations for a session or globally
    """
    try:
        query = db.query(DetectionConfiguration).filter(DetectionConfiguration.is_active == True)
        
        if session_id and include_global:
            query = query.filter(or_(
                DetectionConfiguration.session_id == session_id,
                DetectionConfiguration.session_id.is_(None)
            ))
        elif session_id:
            query = query.filter(DetectionConfiguration.session_id == session_id)
        elif include_global:
            query = query.filter(DetectionConfiguration.session_id.is_(None))
        
        configurations = query.order_by(DetectionConfiguration.is_default.desc(),
                                      DetectionConfiguration.created_at.desc()).all()
        
        return configurations
        
    except Exception as e:
        logger.error(f"Error retrieving configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving configurations: {str(e)}")


@router.post("/synchronize", response_model=SynchronizationResponse)
async def analyze_detection_synchronization(
    request: SynchronizationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Analyze temporal synchronization between LabJack and video detections
    
    This endpoint performs comprehensive temporal analysis, matching detections
    within configurable time windows and calculating synchronization metrics.
    """
    try:
        # Get or create analysis configuration
        config = None
        if request.configuration_id:
            config = db.query(DetectionConfiguration)\
                       .filter(DetectionConfiguration.id == request.configuration_id)\
                       .first()
        
        if not config:
            # Get default configuration for session or global
            config = db.query(DetectionConfiguration)\
                       .filter(and_(
                           or_(DetectionConfiguration.session_id == request.session_id,
                               DetectionConfiguration.session_id.is_(None)),
                           DetectionConfiguration.is_default == True,
                           DetectionConfiguration.is_active == True
                       ))\
                       .first()
        
        if not config:
            # Create default configuration
            config = DetectionConfiguration(
                id=str(uuid.uuid4()),
                name="Default Analysis Config",
                session_id=request.session_id,
                is_default=True,
                is_active=True
            )
            db.add(config)
            db.commit()
            db.refresh(config)
        
        # Schedule background analysis task
        analysis_id = str(uuid.uuid4())
        background_tasks.add_task(
            perform_synchronization_analysis,
            analysis_id,
            request.session_id,
            config.id,
            request.time_range_start,
            request.time_range_end,
            request.force_reanalysis,
            request.analysis_parameters or {}
        )
        
        # Return immediate response
        return SynchronizationResponse(
            analysis_id=analysis_id,
            session_id=request.session_id,
            total_labjack_detections=0,
            total_video_detections=0,
            matched_detections=0,
            unmatched_labjack=0,
            unmatched_video=0,
            mean_time_difference_ms=0.0,
            synchronization_accuracy=0.0,
            processing_time_seconds=0.0,
            analysis_status="processing",
            warnings=[],
            metadata={"config_id": config.id, "started_at": datetime.now(timezone.utc).isoformat()}
        )
        
    except Exception as e:
        logger.error(f"Error starting synchronization analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting analysis: {str(e)}")


@router.get("/synchronization/{analysis_id}")
async def get_synchronization_result(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """
    Get synchronization analysis results by analysis ID
    """
    try:
        result = db.query(TemporalAnalysisResult)\
                   .filter(TemporalAnalysisResult.id == analysis_id)\
                   .first()
        
        if not result:
            raise HTTPException(status_code=404, detail="Analysis result not found")
        
        return result.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving analysis result: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving result: {str(e)}")


@router.get("/session/{session_id}/synchronization-summary")
async def get_session_synchronization_summary(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get synchronization summary for a session
    """
    try:
        # Get latest analysis results for the session
        latest_analysis = db.query(TemporalAnalysisResult)\
                           .filter(TemporalAnalysisResult.session_id == session_id)\
                           .order_by(TemporalAnalysisResult.analyzed_at.desc())\
                           .first()
        
        # Get detection counts
        labjack_count = db.query(func.count(LabJackDetection.id))\
                         .filter(LabJackDetection.session_id == session_id)\
                         .scalar()
        
        video_count = db.query(func.count(VideoDetection.id))\
                       .filter(VideoDetection.session_id == session_id)\
                       .scalar()
        
        matched_count = db.query(func.count(DetectionSynchronization.id))\
                         .filter(DetectionSynchronization.session_id == session_id)\
                         .scalar()
        
        # Calculate synchronization statistics
        sync_stats = db.query(
            func.avg(DetectionSynchronization.time_difference_ms).label('mean_diff'),
            func.stddev(DetectionSynchronization.time_difference_ms).label('std_diff'),
            func.min(DetectionSynchronization.time_difference_ms).label('min_diff'),
            func.max(DetectionSynchronization.time_difference_ms).label('max_diff')
        ).filter(DetectionSynchronization.session_id == session_id).first()
        
        return {
            "session_id": session_id,
            "total_labjack_detections": labjack_count or 0,
            "total_video_detections": video_count or 0,
            "matched_detections": matched_count or 0,
            "unmatched_labjack": (labjack_count or 0) - (matched_count or 0),
            "unmatched_video": (video_count or 0) - (matched_count or 0),
            "synchronization_accuracy": (matched_count / max(labjack_count, 1)) * 100 if labjack_count else 0,
            "timing_statistics": {
                "mean_difference_ms": float(sync_stats.mean_diff or 0),
                "std_difference_ms": float(sync_stats.std_diff or 0),
                "min_difference_ms": float(sync_stats.min_diff or 0),
                "max_difference_ms": float(sync_stats.max_diff or 0)
            } if sync_stats.mean_diff is not None else None,
            "latest_analysis": latest_analysis.to_dict() if latest_analysis else None
        }
        
    except Exception as e:
        logger.error(f"Error getting synchronization summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting summary: {str(e)}")


# Background task functions

async def perform_synchronization_analysis(
    analysis_id: str,
    session_id: str,
    config_id: str,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    force_reanalysis: bool,
    analysis_parameters: Dict[str, Any]
):
    """
    Background task to perform temporal synchronization analysis
    """
    from src.services.temporal_sync_service import TemporalSynchronizationService
    
    db = SessionLocal()
    try:
        logger.info(f"Starting synchronization analysis {analysis_id} for session {session_id}")
        
        # Initialize synchronization service
        sync_service = TemporalSynchronizationService(db)
        
        # Perform analysis
        result = await sync_service.analyze_session_synchronization(
            analysis_id=analysis_id,
            session_id=session_id,
            config_id=config_id,
            start_time=start_time,
            end_time=end_time,
            force_reanalysis=force_reanalysis,
            analysis_parameters=analysis_parameters
        )
        
        logger.info(f"Completed synchronization analysis {analysis_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in synchronization analysis {analysis_id}: {str(e)}")
        # Update analysis result with error status
        try:
            error_result = TemporalAnalysisResult(
                id=analysis_id,
                session_id=session_id,
                analysis_name=f"Error Analysis {analysis_id[:8]}",
                start_time=start_time or datetime.now(timezone.utc),
                end_time=end_time or datetime.now(timezone.utc),
                duration_seconds=0,
                analysis_status="error",
                is_valid=False,
                metadata={"error": str(e)}
            )
            db.add(error_result)
            db.commit()
        except Exception as save_error:
            logger.error(f"Error saving error result: {str(save_error)}")
        
        raise
        
    finally:
        db.close()