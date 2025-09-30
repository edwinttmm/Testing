"""
Dataset Management Router - API Endpoints for Dataset Views
==========================================================

Provides endpoints specifically for dataset management and annotation viewing.
Handles annotation retrieval, AI detection data, and screenshot serving for the Datasets page.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os

from database import SessionLocal
from models import Video, Annotation, TestSession, DetectionEvent, Project
from schemas_annotation import AnnotationResponse
from services.ground_truth_service import GroundTruthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/datasets", tags=["Datasets"])

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/videos/{video_id}/annotations")
async def get_video_annotations_for_dataset(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get annotations (ground truth data) for a specific video in Dataset format.
    Returns data compatible with frontend GroundTruthAnnotation interface.
    """
    try:
        logger.info(f"Fetching dataset annotations for video {video_id}")
        
        # Query existing annotations for this video with proper joins
        annotations = db.query(Annotation).filter(
            Annotation.video_id == video_id
        ).order_by(Annotation.timestamp).all()
        
        # Load detection events with screenshots for reuse
        try:
            from pathlib import Path
            dets = db.query(DetectionEvent).filter(
                DetectionEvent.video_id == video_id,
                DetectionEvent.screenshot_path.isnot(None)
            ).all()
            det_list = [
                {
                    'timestamp': float(getattr(d, 'timestamp') or 0.0),
                    'frame_number': getattr(d, 'frame_number', None),
                    'screenshot_path': getattr(d, 'screenshot_path', None),
                    'screenshot_zoom_path': getattr(d, 'screenshot_zoom_path', None)
                }
                for d in dets
            ]
            det_by_frame = {d['frame_number']: d for d in det_list if d.get('frame_number') is not None}
        except Exception:
            det_list = []
            det_by_frame = {}

        # Convert to frontend-compatible format
        result = []
        for annotation in annotations:
            # Handle bounding box data - could be JSON or individual fields
            bounding_box = {}
            if annotation.bounding_box:
                if isinstance(annotation.bounding_box, dict):
                    bounding_box = annotation.bounding_box
                else:
                    # Try to parse if it's a string
                    try:
                        import json
                        bounding_box = json.loads(annotation.bounding_box) if isinstance(annotation.bounding_box, str) else annotation.bounding_box
                    except:
                        bounding_box = {
                            "x": getattr(annotation, 'bounding_box_x', 0),
                            "y": getattr(annotation, 'bounding_box_y', 0), 
                            "width": getattr(annotation, 'bounding_box_width', 100),
                            "height": getattr(annotation, 'bounding_box_height', 100),
                            "confidence": getattr(annotation, 'confidence', 1.0)
                        }
            
            # Attempt to match screenshots by frame number first, else nearest timestamp
            screenshot_path = None
            screenshot_zoom_path = None
            if det_list:
                try:
                    matched = None
                    if annotation.frame_number is not None:
                        fn = annotation.frame_number
                        if fn in det_by_frame:
                            matched = det_by_frame[fn]
                        elif (fn - 1) in det_by_frame:
                            matched = det_by_frame[fn - 1]
                        elif (fn + 1) in det_by_frame:
                            matched = det_by_frame[fn + 1]
                    else:
                        t = float(annotation.timestamp or 0.0)
                        best = None
                        best_dt = 10**9
                        for d in det_list:
                            dt = abs(d['timestamp'] - t)
                            if dt < best_dt:
                                best = d
                                best_dt = dt
                        if best is not None and best_dt <= 1.0:
                            matched = best
                    if matched is not None:
                        if matched.get('screenshot_zoom_path'):
                            screenshot_zoom_path = f"/screenshots/{Path(matched['screenshot_zoom_path']).name}"
                        if matched.get('screenshot_path'):
                            screenshot_path = f"/screenshots/{Path(matched['screenshot_path']).name}"
                except Exception:
                    pass

            annotation_data = {
                "id": annotation.id,
                "videoId": annotation.video_id,
                "detectionId": annotation.detection_id,
                "frameNumber": annotation.frame_number,
                "timestamp": annotation.timestamp,
                "endTimestamp": annotation.end_timestamp,
                "vruType": annotation.vru_type,
                "classLabel": bounding_box.get("label", annotation.vru_type),
                "boundingBox": {
                    "x": bounding_box.get("x", 0),
                    "y": bounding_box.get("y", 0), 
                    "width": bounding_box.get("width", 100),
                    "height": bounding_box.get("height", 100),
                    "confidence": getattr(bounding_box, 'confidence', bounding_box.get("confidence", 1.0) if hasattr(bounding_box, 'get') else 1.0),
                    "label": bounding_box.get("label", annotation.vru_type)
                },
                "occluded": annotation.occluded or False,
                "truncated": annotation.truncated or False,
                "difficult": annotation.difficult or False,
                "validationStatus": "validated" if annotation.validated else "pending",
                "validated": annotation.validated or False,
                "confidence": getattr(bounding_box, 'confidence', bounding_box.get("confidence", 1.0) if hasattr(bounding_box, 'get') else 1.0),
                "notes": annotation.notes,
                "annotator": annotation.annotator,
                "createdAt": annotation.created_at.isoformat() if annotation.created_at else None,
                "updatedAt": annotation.updated_at.isoformat() if annotation.updated_at else None
            }
            # Attach screenshot info if available
            if screenshot_path or screenshot_zoom_path:
                annotation_data["screenshotPath"] = screenshot_zoom_path or screenshot_path
                annotation_data["rawScreenshotPath"] = screenshot_path
                annotation_data["hasVisualEvidence"] = True
            else:
                annotation_data["hasVisualEvidence"] = False
            result.append(annotation_data)
        
        logger.info(f"Found {len(result)} annotations for video {video_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error fetching annotations for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch annotations: {str(e)}")

@router.get("/videos/{video_id}/ai-detections")
async def get_video_ai_detections(
    video_id: str,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get AI detection results for a video from test sessions.
    Returns data in format expected by frontend AIDetection interface.
    """
    try:
        logger.info(f"Fetching AI detections for video {video_id}")
        
        # Get test sessions that used this video
        test_sessions = db.query(TestSession).filter(TestSession.video_id == video_id).all()
        
        if not test_sessions:
            logger.info(f"No test sessions found for video {video_id}")
            return []
        
        # Get detection events from these sessions
        session_ids = [session.id for session in test_sessions]
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id.in_(session_ids)
        ).order_by(DetectionEvent.timestamp).limit(limit).all()
        
        # Convert to frontend format
        ai_detections = []
        # Build frame->screenshot map for reuse
        try:
            from pathlib import Path
            det_with_shots = [
                {
                    'frame_number': getattr(d, 'frame_number', None),
                    'timestamp': float(getattr(d, 'timestamp') or 0.0),
                    'screenshot_path': getattr(d, 'screenshot_path', None),
                    'screenshot_zoom_path': getattr(d, 'screenshot_zoom_path', None)
                }
                for d in detection_events if getattr(d, 'screenshot_path', None)
            ]
            det_by_frame = {d['frame_number']: d for d in det_with_shots if d.get('frame_number') is not None}
        except Exception:
            det_with_shots = []
            det_by_frame = {}
        for detection in detection_events:
            detection_data = {
                "id": detection.id,
                "detectionId": detection.id,  # Use same ID for compatibility
                "timestamp": detection.timestamp,
                "frameNumber": detection.frame_number or 0,
                "confidence": detection.confidence or 0.0,
                "classLabel": detection.vru_type,
                "vruType": detection.vru_type,
                "boundingBox": {
                    "x": detection.bounding_box_x or 0,
                    "y": detection.bounding_box_y or 0,
                    "width": detection.bounding_box_width or 100,
                    "height": detection.bounding_box_height or 100,
                    "confidence": detection.confidence or 0.0
                },
                "screenshotPath": None,  # Will be populated if screenshots exist
                "screenshotZoomPath": None
            }
            
            # Set screenshot if this detection has one
            if detection.screenshot_path:
                screenshot_path = detection.screenshot_path
                if not screenshot_path.startswith('/screenshots/'):
                    screenshot_path = f"/screenshots/{os.path.basename(screenshot_path)}"
                detection_data["screenshotPath"] = screenshot_path
            else:
                # Reuse by frame number ±1, else leave None
                fn = detection.frame_number or 0
                matched = None
                if fn in det_by_frame:
                    matched = det_by_frame[fn]
                elif (fn - 1) in det_by_frame:
                    matched = det_by_frame[fn - 1]
                elif (fn + 1) in det_by_frame:
                    matched = det_by_frame[fn + 1]
                if matched:
                    sp = matched.get('screenshot_zoom_path') or matched.get('screenshot_path')
                    if sp:
                        if not str(sp).startswith('/screenshots/'):
                            sp = f"/screenshots/{os.path.basename(str(sp))}"
                        detection_data["screenshotPath"] = sp
            
            ai_detections.append(detection_data)
        
        logger.info(f"Found {len(ai_detections)} AI detections for video {video_id}")
        return ai_detections
        
    except Exception as e:
        logger.error(f"Error fetching AI detections for video {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch AI detections: {str(e)}")

@router.get("/videos/{video_id}/summary")
async def get_video_dataset_summary(
    video_id: str,
    db: Session = Depends(get_db)
):
    """
    Get summary information for a video including annotation count, detection types, etc.
    """
    try:
        # Get video info
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Count annotations
        annotation_count = db.query(func.count(Annotation.id)).filter(
            Annotation.video_id == video_id
        ).scalar() or 0
        
        # Get unique detection types from annotations
        annotation_types = db.query(Annotation.vru_type).filter(
            Annotation.video_id == video_id
        ).distinct().all()
        
        # Get AI detection count from test sessions
        test_sessions = db.query(TestSession).filter(TestSession.video_id == video_id).all()
        session_ids = [session.id for session in test_sessions] if test_sessions else []
        
        ai_detection_count = 0
        ai_detection_types = []
        if session_ids:
            ai_detection_count = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.test_session_id.in_(session_ids)
            ).scalar() or 0
            
            ai_types = db.query(DetectionEvent.vru_type).filter(
                DetectionEvent.test_session_id.in_(session_ids)
            ).distinct().all()
            ai_detection_types = [t[0] for t in ai_types if t[0]]
        
        # Videos are now project-independent - get project name from VideoProjectLink if needed
        project_name = "Shared Video"
        # Could get first linked project name via VideoProjectLink if needed
        
        summary = {
            "videoId": video.id,
            "filename": video.filename,
            "annotationCount": annotation_count,
            "aiDetectionCount": ai_detection_count,
            "detectionTypes": list(set([t[0] for t in annotation_types if t[0]] + ai_detection_types)),
            "projectName": project_name,
            "duration": video.duration,
            "fileSize": video.file_size,
            "quality": "high" if annotation_count > 10 else "medium" if annotation_count > 0 else "low"
        }
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video summary for {video_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get video summary: {str(e)}")

@router.get("/health")
async def datasets_health_check():
    """Health check for dataset endpoints"""
    return {
        "status": "healthy",
        "service": "Datasets API",
        "version": "1.0.0",
        "endpoints": [
            "GET /api/datasets/videos/{video_id}/annotations - Get video annotations",
            "GET /api/datasets/videos/{video_id}/ai-detections - Get AI detection results",
            "GET /api/datasets/videos/{video_id}/summary - Get video dataset summary"
        ]
    }
