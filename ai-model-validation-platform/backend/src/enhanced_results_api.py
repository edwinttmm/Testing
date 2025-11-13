#!/usr/bin/env python3
"""
Enhanced Results API
Populates the results page with stored detection data from project-based sessions
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, desc, func
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db
from models import (
    Project, Video, TestSession, DetectionEvent, TestResult, 
    DetectionComparison, GroundTruthObject, SequenceVideoResult
)
from services.ground_truth_matching_service import (
    get_session_matching_results, get_detection_event_details, calculate_project_metrics
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/results", tags=["Enhanced Results"])

def _generate_session_summary(total_gt: int, matched_gt: int, precision: float, avg_latency: float) -> str:
    """Generate human-readable session summary"""
    if total_gt == 0:
        return "No ground truth data available for analysis"
    
    coverage = (matched_gt / total_gt) * 100 if total_gt > 0 else 0
    
    if coverage >= 90 and precision >= 85 and avg_latency <= 50:
        return f"Excellent: {matched_gt}/{total_gt} ground truth found ({coverage:.0f}%), {precision:.0f}% precision, {avg_latency:.1f}ms latency"
    elif coverage >= 75 and precision >= 70 and avg_latency <= 100:
        return f"Good: {matched_gt}/{total_gt} ground truth found ({coverage:.0f}%), {precision:.0f}% precision, {avg_latency:.1f}ms latency"
    elif coverage >= 50:
        return f"Fair: {matched_gt}/{total_gt} ground truth found ({coverage:.0f}%), {precision:.0f}% precision, {avg_latency:.1f}ms latency"
    else:
        return f"Poor: {matched_gt}/{total_gt} ground truth found ({coverage:.0f}%), {precision:.0f}% precision, {avg_latency:.1f}ms latency"

# Response Models
class VideoDetectionResult(BaseModel):
    """Individual video detection result"""
    video_id: str
    video_filename: str
    total_detections: int
    passed_detections: int
    failed_detections: int
    success_rate: float
    detection_types: List[str]
    average_confidence: float
    processing_time: Optional[str]

class GroundTruthMetrics(BaseModel):
    """Ground truth matching metrics"""
    ground_truth_total: int
    ground_truth_matched: int
    ground_truth_missed: int
    extra_detections: int
    precision: float
    recall: float
    f1_score: float
    avg_latency_ms: float
    median_latency_ms: float
    latency_std_ms: float

class DetectionEventDetail(BaseModel):
    """Detection event with ground truth correlation"""
    ground_truth_time: Optional[float]
    detected_time: Optional[float]
    video_relative_time: Optional[float]
    latency_ms: Optional[float]
    temporal_offset_ms: Optional[float]
    status: str  # 'matched', 'missed', 'false_positive'
    match_type: str  # 'true_positive', 'false_negative', 'false_positive'
    confidence: Optional[float]
    ground_truth_id: Optional[str]
    detection_event_id: Optional[str]

class SessionResults(BaseModel):
    """Complete session results with ground truth metrics"""
    session_id: str
    session_name: str
    project_id: str
    project_name: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_videos: int
    successful_videos: int
    failed_videos: int
    video_results: List[VideoDetectionResult]
    statistics: Dict[str, Any]
    ground_truth_metrics: Optional[GroundTruthMetrics]
    detection_details: List[DetectionEventDetail]

class ProjectResultsSummary(BaseModel):
    """Project-level results summary"""
    project_id: str
    project_name: str
    total_sessions: int
    total_videos_processed: int
    total_detections: int
    overall_success_rate: float
    recent_sessions: List[Dict[str, Any]]
    detection_type_breakdown: Dict[str, int]

@router.get("/projects/{project_id}/sessions", response_model=List[Dict[str, Any]])
async def get_project_results_sessions(
    project_id: str,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all test sessions for a project with results summary
    This is what populates the results page
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get sessions with results
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).order_by(desc(TestSession.started_at)).limit(limit).all()
        
        session_results = []
        for session in sessions:
            # Get test results for this session
            test_results = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).all()
            
            # Get detection events count
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            # Get comparison results
            comparison_count = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session.id
            ).count()
            
            session_data = {
                "session_id": session.id,
                "session_name": session.name,
                "status": session.status,
                "session_type": getattr(session, 'session_type', 'standard'),
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "results_count": len(test_results),
                "detection_events": detection_count,
                "detection_comparisons": comparison_count,
                "has_results": len(test_results) > 0 or detection_count > 0,
                "results_summary": session.results_summary or {},
                "configuration": session.configuration or {}
            }
            
            session_results.append(session_data)
        
        return session_results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project sessions: {str(e)}"
        )

@router.get("/{session_id}/results", response_model=Dict[str, Any])
async def get_session_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get ground truth matching results for a session
    Returns enhanced metrics with precision, recall, and real latency data
    """
    try:
        # Get ground truth matching results
        matching_results = get_session_matching_results(session_id, db)
        
        # Get detailed detection events
        detection_details = get_detection_event_details(session_id, db)
        
        # Get session info
        session = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(TestSession.id == session_id).first()
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        if not matching_results:
            logger.warning(f"No matching results found for session {session_id}, returning empty metrics")
            ground_truth_total = 0
            true_positives = false_negatives = false_positives = 0
            precision_pct = recall_pct = f1_pct = 0.0
            avg_latency = median_latency = latency_std = 0.0
        else:
            ground_truth_total = getattr(
                matching_results,
                "total_ground_truth",
                matching_results.true_positives + matching_results.false_negatives
            )
            true_positives = matching_results.true_positives
            false_negatives = matching_results.false_negatives
            false_positives = matching_results.false_positives
            precision_pct = round((matching_results.precision or 0.0) * 100, 1)
            recall_pct = round((matching_results.recall or 0.0) * 100, 1)
            f1_pct = round((matching_results.f1_score or 0.0) * 100, 1)
            avg_latency = round(getattr(matching_results, "mean_latency_ms", 0.0), 1)
            latency_std = round(getattr(matching_results, "std_latency_ms", 0.0), 1)
            # SessionMetrics does not expose median latency; approximate with mean for now
            median_latency = avg_latency

        return {
            "session_id": session_id,
            "session_name": session.name,
            "project_name": session.project.name if session.project else "Unknown Project",
            "status": session.status,
            "ground_truth_total": ground_truth_total,
            "ground_truth_matched": true_positives,
            "ground_truth_missed": false_negatives,
            "extra_detections": false_positives,
            "precision": precision_pct,
            "recall": recall_pct,
            "f1_score": f1_pct,
            "avg_latency_ms": avg_latency,
            "median_latency_ms": median_latency,
            "latency_std_ms": latency_std,
            "detection_details": detection_details,
            "summary": {
                "coverage_percentage": recall_pct,
                "detection_accuracy": precision_pct,
                "overall_performance": f1_pct,
                "timing_performance": f"{avg_latency:.1f}ms ± {latency_std:.1f}ms"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving session results: {str(e)}"
        )

@router.get("/{session_id}/detection-events", response_model=List[Dict[str, Any]])
async def get_session_detection_events(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detection events with ground truth correlation for display in detection table
    Shows video-relative timestamps and match status (TP/FP/FN)
    """
    try:
        # Get detection event details with ground truth correlation
        detection_details = get_detection_event_details(session_id, db)
        
        if not detection_details:
            return []
        
        # Format for frontend display
        formatted_events = []
        for detail in detection_details:
            event = {
                "id": detail.get("detection_event_id") or detail.get("ground_truth_id", ""),
                "video_time": detail.get("video_relative_time", 0.0),
                "ground_truth_time": detail.get("ground_truth_time"),
                "detected_time": detail.get("detected_time"),
                "latency_ms": detail.get("latency_ms"),
                "temporal_offset_ms": detail.get("temporal_offset_ms"),
                "status": detail.get("status", "unknown"),
                "match_type": detail.get("match_type", "unknown"),
                "confidence": detail.get("confidence"),
                "status_color": {
                    "matched": "green",
                    "missed": "red", 
                    "false_positive": "orange"
                }.get(detail.get("status", "unknown"), "gray"),
                "display_text": {
                    "matched": "✓ Matched",
                    "missed": "✗ Missed GT",
                    "false_positive": "⚠ False Positive"
                }.get(detail.get("status", "unknown"), "Unknown")
            }
            
            formatted_events.append(event)
        
        # Sort by video time for timeline display
        formatted_events.sort(key=lambda x: x["video_time"] if x["video_time"] is not None else float('inf'))
        
        return formatted_events
        
    except Exception as e:
        logger.error(f"Error getting detection events for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving detection events: {str(e)}"
        )

@router.get("/sessions/{session_id}/detailed", response_model=SessionResults)
async def get_detailed_session_results(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive detailed results for a specific session
    This provides all the data needed for the detailed results view
    """
    try:
        # Get session with project info
        session = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(TestSession.id == session_id).first()
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Get all test results for this session with test_session relationship loaded
        test_results = db.query(TestResult).options(
            joinedload(TestResult.test_session)
        ).filter(TestResult.test_session_id == session_id).all()
        
        # Get all detection events for this session with proper error handling
        detection_events = db.query(DetectionEvent).options(
            joinedload(DetectionEvent.video)  # ✅ Load video relationship properly
        ).filter(
            DetectionEvent.test_session_id == session_id
        ).all()
        
        # Get all detection comparisons for this session with relationships loaded
        detection_comparisons = db.query(DetectionComparison).options(
            joinedload(DetectionComparison.detection_event)
        ).filter(
            DetectionComparison.test_session_id == session_id
        ).all()
        
        # Group results by video
        video_results = {}
        
        # Process test results
        for result in test_results:
            # FIXED: Get video_id from the test_session relationship since TestResult doesn't have video_id directly
            video_id = result.test_session.video_id if result.test_session else None
            if not video_id:
                continue  # Skip if no video_id available
            if video_id not in video_results:
                # Get video info
                video = db.query(Video).filter(Video.id == video_id).first()
                video_results[video_id] = {
                    "video_id": video_id,
                    "video_filename": video.filename if video else "Unknown",
                    "test_results": [],
                    "detection_events": [],
                    "detection_comparisons": []
                }
            
            # Map TestResult fields to expected format
            test_result_data = {
                "id": result.id,
                "accuracy": result.accuracy,
                "precision": result.precision,
                "recall": result.recall,
                "f1_score": result.f1_score,
                "true_positives": result.true_positives,
                "false_positives": result.false_positives,
                "false_negatives": result.false_negatives,
                "statistical_analysis": result.statistical_analysis,
                "confidence_intervals": result.confidence_intervals,
                "created_at": result.created_at.isoformat()
            }
            
            video_results[video_id]["test_results"].append(test_result_data)
        
        # Process detection events with comprehensive error handling
        for event in detection_events:
            try:
                # Use loaded video relationship or fallback to video_id lookup
                video_id = getattr(event, 'video_id', None)
                video_obj = getattr(event, 'video', None) if hasattr(event, 'video') else None
                
                if video_id and video_id not in video_results:
                    # Try to get video filename from loaded relationship first
                    try:
                        if video_obj:
                            video_filename = video_obj.filename
                        else:
                            # Fallback: Get video info directly from database
                            video = db.query(Video).filter(Video.id == video_id).first() if video_id else None
                            video_filename = video.filename if video else "Unknown"
                    except Exception as video_error:
                        logger.warning(f"Could not load video {video_id}: {video_error}")
                        video_filename = "Unknown"
                    
                    video_results[video_id] = {
                        "video_id": video_id,
                        "video_filename": video_filename,
                        "test_results": [],
                        "detection_events": [],
                        "detection_comparisons": []
                    }
                
                if video_id:  # Only process if we have a valid video_id
                    video_results[video_id]["detection_events"].append({
                        "id": getattr(event, 'id', ''),
                        "detection_id": getattr(event, 'detection_id', ''),
                        "object_type": getattr(event, 'class_label', ''),  # FIXED: Use class_label from DetectionEvent model
                        "confidence_score": getattr(event, 'confidence', 0.0),  # FIXED: Use confidence from DetectionEvent model
                        "validation_result": getattr(event, 'validation_result', ''),
                        "bounding_box": {
                            "x": getattr(event, 'bounding_box_x', 0),
                            "y": getattr(event, 'bounding_box_y', 0),
                            "width": getattr(event, 'bounding_box_width', 0),
                            "height": getattr(event, 'bounding_box_height', 0)
                        } if getattr(event, 'bounding_box_x', None) is not None else None,
                        "frame_number": getattr(event, 'frame_number', 0),
                        "timestamp": str(getattr(event, 'timestamp', 0.0))
                    })
            except Exception as event_error:
                logger.warning(f"Error processing detection event {getattr(event, 'id', 'unknown')}: {event_error}")
                continue
        
        # Ensure sequence videos are represented even if no detections/tests were recorded
        try:
            if getattr(session, "has_video_sequence", False) and getattr(session, "sequence_id", None):
                sequence_videos = db.query(SequenceVideoResult).filter(
                    SequenceVideoResult.video_sequence_id == session.sequence_id
                ).all()
                for seq_video in sequence_videos:
                    vid = getattr(seq_video, "video_id", None)
                    if not vid or vid in video_results:
                        continue
                    video = db.query(Video).filter(Video.id == vid).first()
                    video_results[vid] = {
                        "video_id": vid,
                        "video_filename": video.filename if video else "Unknown",
                        "test_results": [],
                        "detection_events": [],
                        "detection_comparisons": []
                    }
        except Exception as seq_error:
            logger.warning(f"Could not load sequence videos for session {session_id}: {seq_error}")
        
        # Process detection comparisons with error handling
        for comparison in detection_comparisons:
            try:
                # Get video_id through detection_event relationship with error handling
                detection_event = getattr(comparison, 'detection_event', None)
                if detection_event:
                    video_id = getattr(detection_event, 'video_id', None)
                    if video_id and video_id in video_results:
                        video_results[video_id]["detection_comparisons"].append({
                            "id": getattr(comparison, 'id', ''),
                            "detection_event_id": getattr(comparison, 'detection_event_id', ''),
                            "ground_truth_id": getattr(comparison, 'ground_truth_id', ''),
                            "match_type": getattr(comparison, 'match_type', ''),  # FIXED: Use correct field name
                            "iou_score": getattr(comparison, 'iou_score', 0.0),  # FIXED: Use correct field name
                            "distance_error": getattr(comparison, 'distance_error', 0.0),
                            "temporal_offset": getattr(comparison, 'temporal_offset', 0.0),
                            "notes": getattr(comparison, 'notes', '')  # FIXED: Use correct field name
                        })
            except Exception as comp_error:
                logger.warning(f"Error processing detection comparison {getattr(comparison, 'id', 'unknown')}: {comp_error}")
                continue
        
        # Create video result summaries with ENHANCED TEST METRICS
        formatted_video_results = []
        for video_id, data in video_results.items():
            detection_events = data["detection_events"]
            
            total_detections = len(detection_events)
            passed_detections = sum(1 for d in detection_events if d["validation_result"] == "Pass")
            failed_detections = total_detections - passed_detections
            success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
            
            detection_types = sorted({
                str(d["object_type"])
                for d in detection_events
                if d.get("object_type")
            })
            if not detection_types:
                detection_types = ["unknown"]
            
            # ENHANCED: Calculate average latency for passed tests (timestamp represents latency in enhanced tests)
            passed_latencies = [
                float(d["timestamp"]) * 1000  # Convert to ms for latency display
                for d in detection_events 
                if d["validation_result"] == "Pass" and d["timestamp"]
            ]
            average_latency_ms = sum(passed_latencies) / len(passed_latencies) if passed_latencies else 0
            
            # Use latency as the confidence metric for enhanced tests (more meaningful)
            average_confidence = average_latency_ms
            
            # ENHANCED: Calculate processing time from detection event timestamps
            processing_times = [
                float(d["timestamp"]) for d in detection_events if d["timestamp"]
            ]
            total_processing_time = f"{max(processing_times):.3f}s" if processing_times else None
            
            video_result = VideoDetectionResult(
                video_id=video_id,
                video_filename=data["video_filename"],
                total_detections=total_detections,
                passed_detections=passed_detections,
                failed_detections=failed_detections,
                success_rate=success_rate,
                detection_types=detection_types,
                average_confidence=average_latency_ms,  # Now represents average latency
                processing_time=total_processing_time
            )
            
            formatted_video_results.append(video_result)
        
        # Get ground truth matching results
        try:
            matching_results = get_session_matching_results(session_id, db)
            detection_details = get_detection_event_details(session_id, db)
            
            ground_truth_metrics = GroundTruthMetrics(
                ground_truth_total=matching_results.ground_truth_total,
                ground_truth_matched=matching_results.true_positives,
                ground_truth_missed=matching_results.false_negatives,
                extra_detections=matching_results.false_positives,
                precision=matching_results.precision,
                recall=matching_results.recall,
                f1_score=matching_results.f1_score,
                avg_latency_ms=matching_results.avg_latency_ms,
                median_latency_ms=matching_results.median_latency_ms,
                latency_std_ms=matching_results.latency_std_ms
            )
            
            # Convert detection details to the required format
            converted_detection_details = [
                DetectionEventDetail(
                    ground_truth_time=detail.get("ground_truth_time"),
                    detected_time=detail.get("detected_time"),
                    video_relative_time=detail.get("video_relative_time"),
                    latency_ms=detail.get("latency_ms"),
                    temporal_offset_ms=detail.get("temporal_offset_ms"),
                    status=detail.get("status", "unknown"),
                    match_type=detail.get("match_type", "unknown"),
                    confidence=detail.get("confidence"),
                    ground_truth_id=detail.get("ground_truth_id"),
                    detection_event_id=detail.get("detection_event_id")
                )
                for detail in detection_details
            ]
        except Exception as e:
            logger.warning(f"Could not get ground truth metrics for session {session_id}: {str(e)}")
            ground_truth_metrics = None
            converted_detection_details = []
        
        # Calculate overall statistics
        total_videos = len(formatted_video_results)
        successful_videos = sum(1 for v in formatted_video_results if v.success_rate > 50)
        failed_videos = total_videos - successful_videos
        
        session_result = SessionResults(
            session_id=session_id,
            session_name=session.name,
            project_id=session.project_id,
            project_name=session.project.name if session.project else "Unknown Project",
            status=session.status,
            started_at=session.started_at.isoformat() if session.started_at else None,
            completed_at=session.completed_at.isoformat() if session.completed_at else None,
            total_videos=total_videos,
            successful_videos=successful_videos,
            failed_videos=failed_videos,
            video_results=formatted_video_results,
            statistics={
                "total_detections": sum(v.total_detections for v in formatted_video_results),
                "total_passed": sum(v.passed_detections for v in formatted_video_results),
                "total_failed": sum(v.failed_detections for v in formatted_video_results),
                "overall_success_rate": (
                    sum(v.success_rate for v in formatted_video_results) / len(formatted_video_results)
                    if formatted_video_results else 0
                ),
                "unique_detection_types": list(set(
                    dt for v in formatted_video_results for dt in v.detection_types
                )),
                "average_confidence_all_videos": (
                    sum(v.average_confidence for v in formatted_video_results) / len(formatted_video_results)
                    if formatted_video_results else 0
                )
            },
            ground_truth_metrics=ground_truth_metrics,
            detection_details=converted_detection_details
        )
        
        return session_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed session results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving detailed results: {str(e)}"
        )

@router.get("/projects/{project_id}/summary", response_model=ProjectResultsSummary)
async def get_project_results_summary(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive project-level results summary
    Shows overall project performance across all sessions
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get all sessions for project
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).all()
        
        # Get all detection events for project
        all_detection_events = db.query(DetectionEvent).join(
            TestSession, DetectionEvent.test_session_id == TestSession.id
        ).filter(TestSession.project_id == project_id).all()
        
        # Get unique videos processed
        unique_videos = db.query(Video).filter(Video.project_id == project_id).count()
        
        # Calculate statistics
        total_detections = len(all_detection_events)
        passed_detections = sum(1 for d in all_detection_events if d.validation_result == "Pass")
        overall_success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
        
        # Detection type breakdown
        detection_type_counts = {}
        for event in all_detection_events:
            obj_type = event.class_label  # FIXED: Use class_label from DetectionEvent model
            detection_type_counts[obj_type] = detection_type_counts.get(obj_type, 0) + 1
        
        # Recent sessions (last 5)
        recent_sessions = []
        for session in sorted(sessions, key=lambda s: s.started_at or datetime.min, reverse=True)[:5]:
            session_detection_count = sum(
                1 for d in all_detection_events if d.test_session_id == session.id
            )
            
            recent_sessions.append({
                "session_id": session.id,
                "session_name": session.name,
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "detection_count": session_detection_count
            })
        
        summary = ProjectResultsSummary(
            project_id=project_id,
            project_name=project.name,
            total_sessions=len(sessions),
            total_videos_processed=unique_videos,
            total_detections=total_detections,
            overall_success_rate=overall_success_rate,
            recent_sessions=recent_sessions,
            detection_type_breakdown=detection_type_counts
        )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving project summary: {str(e)}"
        )

@router.get("/sessions/{session_id}/export", response_model=Dict[str, Any])
async def export_session_results(
    session_id: str,
    format: str = Query("json", pattern="^(json|csv|excel)$"),
    db: Session = Depends(get_db)
):
    """
    Export session results in various formats
    Useful for downloading and sharing results
    """
    try:
        # Get detailed results
        detailed_results = await get_detailed_session_results(session_id, db)
        
        if format == "json":
            return {
                "success": True,
                "format": "json",
                "data": detailed_results.dict(),
                "export_timestamp": datetime.utcnow().isoformat()
            }
        elif format == "csv":
            # Convert to CSV-friendly format
            csv_data = []
            for video_result in detailed_results.video_results:
                csv_data.append({
                    "session_id": session_id,
                    "session_name": detailed_results.session_name,
                    "video_filename": video_result.video_filename,
                    "total_detections": video_result.total_detections,
                    "passed_detections": video_result.passed_detections,
                    "failed_detections": video_result.failed_detections,
                    "success_rate": video_result.success_rate,
                    "detection_types": ",".join(video_result.detection_types),
                    "average_confidence": video_result.average_confidence
                })
            
            return {
                "success": True,
                "format": "csv",
                "headers": list(csv_data[0].keys()) if csv_data else [],
                "data": csv_data,
                "export_timestamp": datetime.utcnow().isoformat()
            }
        else:
            # Excel format would require additional processing
            return {
                "success": False,
                "error": "Excel export not yet implemented",
                "available_formats": ["json", "csv"]
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting session results: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error exporting results: {str(e)}"
        )

@router.get("/dashboard/project/{project_id}", response_model=Dict[str, Any])
async def get_project_dashboard_data(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Get dashboard data for a specific project
    Provides charts and metrics for the frontend dashboard
    """
    try:
        # Get project summary
        summary = await get_project_results_summary(project_id, db)
        
        # Get session trend data (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        recent_sessions = db.query(TestSession).filter(
            and_(
                TestSession.project_id == project_id,
                TestSession.started_at >= thirty_days_ago
            )
        ).order_by(TestSession.started_at).all()
        
        # Create trend data
        session_trend = []
        for session in recent_sessions:
            detection_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            session_trend.append({
                "date": session.started_at.date().isoformat() if session.started_at else None,
                "session_name": session.name,
                "detection_count": detection_count,
                "status": session.status
            })
        
        dashboard_data = {
            "project_summary": summary.dict(),
            "session_trend": session_trend,
            "quick_stats": {
                "active_sessions": sum(1 for s in recent_sessions if s.status == "running"),
                "completed_today": sum(
                    1 for s in recent_sessions 
                    if s.completed_at and s.completed_at.date() == datetime.utcnow().date()
                ),
                "average_detections_per_session": (
                    summary.total_detections / summary.total_sessions
                    if summary.total_sessions > 0 else 0
                )
            },
            "charts_data": {
                "detection_types_pie": [
                    {"name": dtype, "value": count}
                    for dtype, count in summary.detection_type_breakdown.items()
                ],
                "success_rate_gauge": summary.overall_success_rate,
                "sessions_timeline": [
                    {
                        "date": s["started_at"][:10] if s["started_at"] else "Unknown",
                        "count": 1
                    }
                    for s in summary.recent_sessions
                ]
            }
        }
        
        return dashboard_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving dashboard data: {str(e)}"
        )

# Simple endpoint that returns all completed sessions regardless of project
@router.get("/completed", response_model=List[Dict[str, Any]])
async def get_completed_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all completed test sessions for the Results page
    This is a simpler endpoint that doesn't require project filtering
    """
    try:
        # Get all completed sessions with project info
        sessions = db.query(TestSession).options(
            joinedload(TestSession.project)
        ).filter(
            TestSession.status == "completed"
        ).order_by(desc(TestSession.completed_at)).limit(limit).all()
        
        session_results = []
        for session in sessions:
            # Get test results count
            test_results_count = db.query(TestResult).filter(
                TestResult.test_session_id == session.id
            ).count()
            
            # Get detection events count  
            detection_events_count = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session.id
            ).count()
            
            # Get ground truth matching metrics
            try:
                matching_results = get_session_matching_results(session.id, db)
                
                # Use ground truth metrics if available
                if matching_results.ground_truth_total > 0:
                    success_rate = matching_results.recall * 100  # Ground truth coverage
                    precision_rate = matching_results.precision * 100
                    f1_rate = matching_results.f1_score * 100
                    avg_latency = matching_results.avg_latency_ms
                    total_ground_truth = matching_results.ground_truth_total
                    matched_ground_truth = matching_results.true_positives
                    extra_detections = matching_results.false_positives
                    
                    # Enhanced metrics based on ground truth
                    avg_accuracy = matching_results.f1_score  # Use F1 as overall accuracy
                    avg_precision = matching_results.precision
                    avg_recall = matching_results.recall
                    avg_f1 = matching_results.f1_score
                else:
                    # Fallback to legacy detection metrics
                    detection_events = db.query(DetectionEvent).filter(
                        DetectionEvent.test_session_id == session.id
                    ).all()
                    
                    passed_detections = sum(1 for d in detection_events if d.validation_result == "Pass")
                    total_detections = len(detection_events)
                    success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
                    precision_rate = success_rate
                    f1_rate = success_rate
                    avg_latency = 0.0
                    total_ground_truth = 0
                    matched_ground_truth = 0
                    extra_detections = total_detections
                    
                    # Get legacy test result metrics
                    test_results = db.query(TestResult).filter(
                        TestResult.test_session_id == session.id
                    ).all()
                    
                    avg_accuracy = sum(r.accuracy for r in test_results if r.accuracy) / len(test_results) if test_results else None
                    avg_precision = sum(r.precision for r in test_results if r.precision) / len(test_results) if test_results else None
                    avg_recall = sum(r.recall for r in test_results if r.recall) / len(test_results) if test_results else None
                    avg_f1 = sum(r.f1_score for r in test_results if r.f1_score) / len(test_results) if test_results else None
            
            except Exception as e:
                logger.warning(f"Could not get ground truth metrics for session {session.id}: {str(e)}")
                # Fallback to legacy metrics
                detection_events = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session.id
                ).all()
                
                passed_detections = sum(1 for d in detection_events if d.validation_result == "Pass")
                total_detections = len(detection_events)
                success_rate = (passed_detections / total_detections * 100) if total_detections > 0 else 0
                precision_rate = success_rate
                f1_rate = success_rate
                avg_latency = 0.0
                total_ground_truth = 0
                matched_ground_truth = 0
                extra_detections = total_detections
                
                avg_accuracy = None
                avg_precision = None
                avg_recall = None
                avg_f1 = None
            
            session_data = {
                "session_id": session.id,
                "session_name": session.name,
                "project_id": session.project_id,
                "project_name": session.project.name if session.project else "Unknown Project",
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "test_results_count": test_results_count,
                "detection_events_count": detection_events_count,
                "has_results": test_results_count > 0 or detection_events_count > 0,
                "metrics": {
                    # Ground truth enhanced metrics
                    "ground_truth_coverage": round(success_rate, 1),  # Replaces simple pass rate
                    "detection_precision": round(precision_rate, 1),   # Detection accuracy
                    "overall_performance": round(f1_rate, 1),          # F1 score as overall metric
                    "avg_latency_ms": round(avg_latency, 1),           # Real latency measurements
                    
                    # Ground truth breakdown
                    "total_ground_truth": total_ground_truth,
                    "matched_ground_truth": matched_ground_truth,
                    "missed_ground_truth": total_ground_truth - matched_ground_truth,
                    "extra_detections": extra_detections,
                    
                    # Legacy metrics (for backward compatibility)
                    "success_rate": round(success_rate, 2),
                    "total_detections": detection_events_count,
                    "passed_detections": matched_ground_truth,
                    "failed_detections": extra_detections,
                    "accuracy": round(avg_accuracy * 100, 2) if avg_accuracy else None,
                    "precision": round(avg_precision * 100, 2) if avg_precision else None,
                    "recall": round(avg_recall * 100, 2) if avg_recall else None,
                    "f1_score": round(avg_f1 * 100, 2) if avg_f1 else None
                },
                "summary_text": _generate_session_summary(
                    total_ground_truth, matched_ground_truth, precision_rate, avg_latency
                ),
                "processing_time": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at else None
                )
            }
            
            session_results.append(session_data)
        
        logger.info(f"Retrieved {len(session_results)} completed test sessions")
        return session_results
        
    except Exception as e:
        logger.error(f"Error retrieving completed sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving completed sessions: {str(e)}"
        )

# Health check for results API
@router.get("/health", response_model=Dict[str, Any])
async def results_api_health():
    """Health check for enhanced results API"""
    return {
        "status": "healthy",
        "service": "Enhanced Results API",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Results API is operational and ready to serve detection data"
    }

# Export router
enhanced_results_router = router
__all__ = ["router", "enhanced_results_router"]
