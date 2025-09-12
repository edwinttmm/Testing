#!/usr/bin/env python3
"""
Enhanced Snapshot API endpoints for comprehensive failure evidence capture.
PRD Module 3.3 - Visual Evidence Generation System
"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends, Query
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session
import asyncio

from database import get_db
from services.failure_snapshot_service import FailureSnapshotService
from models import ReportSnapshot, DetectionEvent, Video

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])

# Initialize enhanced snapshot service
snapshot_service = FailureSnapshotService("screenshots")

# Ensure snapshot directory exists
SNAPSHOT_DIR = Path("uploads/snapshots")
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/capture-failure")
async def capture_failure_snapshot(
    video_path: str = Form(...),
    timestamp_ms: float = Form(...),
    failure_type: str = Form(...),
    event_id: str = Form(...),
    detection_data: Optional[str] = Form(None),  # JSON string
    ground_truth_data: Optional[str] = Form(None),  # JSON string
    expected_data: Optional[str] = Form(None),  # JSON string
    db: Session = Depends(get_db)
):
    """
    Capture comprehensive failure snapshot with visual evidence
    PRD Module 3.3 requirement
    """
    try:
        import json
        
        # Parse JSON data if provided
        parsed_detection = json.loads(detection_data) if detection_data else None
        parsed_ground_truth = json.loads(ground_truth_data) if ground_truth_data else None
        parsed_expected = json.loads(expected_data) if expected_data else None
        
        # Capture comprehensive snapshot
        snapshot_result = await snapshot_service.capture_failure_snapshot(
            video_path=video_path,
            timestamp_ms=timestamp_ms,
            failure_type=failure_type,
            event_id=event_id,
            detection_data=parsed_detection,
            ground_truth_data=parsed_ground_truth,
            expected_data=parsed_expected
        )
        
        if not snapshot_result:
            raise HTTPException(
                status_code=500,
                detail="Failed to capture failure snapshot"
            )
        
        # Store snapshot metadata in database
        db_snapshot = ReportSnapshot(
            id=str(uuid.uuid4()),
            detection_event_id=event_id,
            failure_type=failure_type,
            timestamp_ms=timestamp_ms,
            frame_number=snapshot_result["frame_number"],
            snapshot_filename=snapshot_result["snapshots"].get("full", {}).get("filename", ""),
            snapshot_path=snapshot_result["snapshots"].get("full", {}).get("path", ""),
            file_size_bytes=snapshot_result["snapshots"].get("full", {}).get("size", 0),
            video_fps=snapshot_result["video_fps"],
            video_total_frames=snapshot_result["video_total_frames"],
            capture_success=True
        )
        
        db.add(db_snapshot)
        db.commit()
        db.refresh(db_snapshot)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Failure snapshot captured successfully",
                "data": {
                    "snapshot_id": db_snapshot.id,
                    "snapshots": snapshot_result["snapshots"],
                    "snapshot_types": snapshot_result["snapshot_types"],
                    "total_snapshots": snapshot_result["total_snapshots"],
                    "metadata": {
                        "frame_number": snapshot_result["frame_number"],
                        "timestamp_ms": timestamp_ms,
                        "failure_type": failure_type,
                        "captured_at": snapshot_result["captured_at"]
                    }
                }
            }
        )
        
    except Exception as e:
        print(f"Error capturing failure snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to capture failure snapshot: {str(e)}"
        )

@router.post("/save")
async def save_snapshot(
    file: UploadFile = File(...),
    video_id: str = Form(...),
    frame_number: int = Form(...),
    timestamp: float = Form(...),
    annotation_count: int = Form(0)
):
    """
    Save annotated video snapshot to dataset.
    
    This endpoint saves video snapshots with annotations directly to the dataset
    for later analysis and validation purposes.
    """
    try:
        # Generate unique filename
        file_extension = os.path.splitext(file.filename or "snapshot.png")[1]
        snapshot_id = str(uuid.uuid4())
        filename = f"snapshot_{video_id}_{frame_number}_{snapshot_id}{file_extension}"
        
        # Save file to snapshot directory
        file_path = SNAPSHOT_DIR / filename
        
        # Read and save file content
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Create snapshot record (you can extend this with database storage)
        snapshot_data = {
            "id": snapshot_id,
            "filename": filename,
            "video_id": video_id,
            "frame_number": frame_number,
            "timestamp": timestamp,
            "annotation_count": annotation_count,
            "file_path": str(file_path),
            "file_size": len(content),
            "created_at": datetime.now().isoformat(),
            "url": f"/uploads/snapshots/{filename}"
        }
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Snapshot saved successfully to dataset",
                "data": snapshot_data
            }
        )
        
    except Exception as e:
        print(f"Error saving snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save snapshot: {str(e)}"
        )

@router.get("/list/{video_id}")
async def list_snapshots(video_id: str):
    """
    List all snapshots for a specific video.
    """
    try:
        # Find all snapshot files for this video
        snapshots = []
        pattern = f"snapshot_{video_id}_*"
        
        for file_path in SNAPSHOT_DIR.glob(pattern):
            if file_path.is_file():
                stat = file_path.stat()
                snapshots.append({
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "file_size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "url": f"/uploads/snapshots/{file_path.name}"
                })
        
        # Sort by creation time (newest first)
        snapshots.sort(key=lambda x: x["created_at"], reverse=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": snapshots,
                "count": len(snapshots)
            }
        )
        
    except Exception as e:
        print(f"Error listing snapshots: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list snapshots: {str(e)}"
        )

@router.delete("/{snapshot_filename}")
async def delete_snapshot(snapshot_filename: str):
    """
    Delete a specific snapshot file.
    """
    try:
        file_path = SNAPSHOT_DIR / snapshot_filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Snapshot not found"
            )
        
        # Delete the file
        file_path.unlink()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Snapshot deleted successfully"
            }
        )
        
    except Exception as e:
        print(f"Error deleting snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete snapshot: {str(e)}"
        )

@router.get("/failure/{event_id}")
async def get_failure_snapshots(
    event_id: str,
    snapshot_type: str = Query("all", description="Type: full, zoom, comparison, all"),
    db: Session = Depends(get_db)
):
    """
    Get all snapshots for a specific failure event
    """
    try:
        # Get snapshot record from database
        db_snapshot = db.query(ReportSnapshot).filter(
            ReportSnapshot.detection_event_id == event_id
        ).first()
        
        if not db_snapshot:
            raise HTTPException(
                status_code=404,
                detail="No snapshots found for this event"
            )
        
        # Find all related snapshot files
        snapshots = {}
        base_pattern = f"*{event_id}*"
        
        if snapshot_type in ["full", "all"]:
            full_files = list(snapshot_service.full_frame_dir.glob(base_pattern))
            if full_files:
                snapshots["full"] = [str(f) for f in full_files]
        
        if snapshot_type in ["zoom", "all"]:
            zoom_files = list(snapshot_service.zoomed_dir.glob(base_pattern))
            if zoom_files:
                snapshots["zoom"] = [str(f) for f in zoom_files]
                
        if snapshot_type in ["comparison", "all"]:
            comp_files = list(snapshot_service.comparison_dir.glob(base_pattern))
            if comp_files:
                snapshots["comparison"] = [str(f) for f in comp_files]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "event_id": event_id,
                    "failure_type": db_snapshot.failure_type,
                    "timestamp_ms": db_snapshot.timestamp_ms,
                    "frame_number": db_snapshot.frame_number,
                    "snapshots": snapshots,
                    "metadata": {
                        "captured_at": db_snapshot.captured_at.isoformat() if db_snapshot.captured_at else None,
                        "video_fps": db_snapshot.video_fps,
                        "total_frames": db_snapshot.video_total_frames
                    }
                }
            }
        )
        
    except Exception as e:
        print(f"Error getting failure snapshots: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get failure snapshots: {str(e)}"
        )

@router.get("/stats")
async def get_snapshot_statistics():
    """
    Get comprehensive snapshot storage statistics
    """
    try:
        stats = snapshot_service.get_snapshot_stats()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": stats
            }
        )
        
    except Exception as e:
        print(f"Error getting snapshot statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get snapshot statistics: {str(e)}"
        )

@router.post("/cleanup")
async def cleanup_old_snapshots(
    days_old: int = Query(30, description="Delete snapshots older than N days")
):
    """
    Cleanup old snapshot files to manage storage
    """
    try:
        snapshot_service.cleanup_old_snapshots(days_old)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Cleaned up snapshots older than {days_old} days"
            }
        )
        
    except Exception as e:
        print(f"Error cleaning up snapshots: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cleanup snapshots: {str(e)}"
        )

# Enhanced static file serving for snapshots
@router.get("/view/{snapshot_type}/{snapshot_filename}")
async def view_snapshot(snapshot_type: str, snapshot_filename: str):
    """
    Serve snapshot file for viewing with type-specific routing
    """
    try:
        # Determine correct directory based on snapshot type
        if snapshot_type == "full":
            file_path = snapshot_service.full_frame_dir / snapshot_filename
        elif snapshot_type == "zoom":
            file_path = snapshot_service.zoomed_dir / snapshot_filename
        elif snapshot_type == "comparison":
            file_path = snapshot_service.comparison_dir / snapshot_filename
        else:
            # Fallback to legacy behavior
            file_path = SNAPSHOT_DIR / snapshot_filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Snapshot not found: {snapshot_filename}"
            )
        
        return FileResponse(
            path=str(file_path),
            media_type="image/jpeg",
            filename=snapshot_filename
        )
        
    except Exception as e:
        print(f"Error serving snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to serve snapshot: {str(e)}"
        )

@router.get("/view/{snapshot_filename}")
async def view_legacy_snapshot(snapshot_filename: str):
    """
    Legacy snapshot serving endpoint for backward compatibility
    """
    try:
        file_path = SNAPSHOT_DIR / snapshot_filename
        
        if not file_path.exists():
            raise HTTPException(
                status_code=404,
                detail="Snapshot not found"
            )
        
        return FileResponse(
            path=str(file_path),
            media_type="image/png",
            filename=snapshot_filename
        )
        
    except Exception as e:
        print(f"Error serving snapshot: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to serve snapshot: {str(e)}"
        )