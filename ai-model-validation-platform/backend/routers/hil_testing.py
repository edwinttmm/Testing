"""
HIL Testing API Endpoints

This module provides API endpoints for Hardware-in-the-Loop (HIL) testing
with ground truth comparison and screenshot capture functionality.

Endpoints:
- GET /api/hil/{session_id}/ground-truth-comparison - Get ground truth comparison with screenshots
- GET /api/hil/{session_id}/detection-events - Get HIL detection events with visual evidence
- GET /api/hil/screenshots/{screenshot_id} - Serve screenshot files
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

# Local imports
from database import get_db
from models import TestSession, DetectionEvent, Video, GroundTruthObject
from services.ground_truth_matching_service import get_ground_truth_matching_service
from services.dedicated_labjack_monitor import get_hil_session_events
from services.hil_screenshot_service import get_hil_ground_truth_comparison
from services.detection_boundary_service import detection_boundary_analyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hil", tags=["HIL Testing"])


@router.get("/{session_id}/ground-truth-comparison")
async def get_ground_truth_comparison_with_screenshots(
    session_id: str,
    tolerance_ms: Optional[int] = 100,
    include_screenshots: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive ground truth comparison results with screenshot evidence for HIL testing.
    
    This endpoint provides:
    - Ground truth matching metrics (precision, recall, F1-score)
    - Detection events with screenshot URLs
    - Detailed analysis of timing accuracy
    - Visual evidence for each detection
    
    Args:
        session_id: HIL test session identifier
        tolerance_ms: Tolerance window for ground truth matching (default: 100ms)
        include_screenshots: Whether to include screenshot URLs (default: true)
        
    Returns:
        Comprehensive ground truth comparison results with visual evidence
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get ground truth matching service
        gt_service = get_ground_truth_matching_service()
        
        # Perform ground truth matching
        matching_metrics = gt_service.match_detections_to_ground_truth(
            session_id=session_id,
            tolerance_ms=tolerance_ms,
            force_rematch=False
        )
        
        # Get detailed analysis
        detailed_analysis = gt_service.get_detailed_analysis(session_id)
        
        # Get matching results summary
        matching_summary = gt_service.get_matching_results_summary(session_id)
        
        # Get HIL detection events with screenshot information
        hil_events = get_hil_session_events(session_id)
        
        # Get detection events from database with screenshot paths
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()
        
        # Enhance detection events with screenshot URLs
        enhanced_detections = []
        for event in detection_events:
            detection_data = {
                'id': event.id,
                'timestamp': event.timestamp,
                'video_relative_timestamp': event.video_relative_timestamp,
                'actual_latency_ms': event.actual_latency_ms,
                'video_frame_number': event.video_frame_number,
                'labjack_voltage': event.labjack_voltage,
                'detection_channel': event.detection_channel,
                'timing_sync_quality': event.timing_sync_quality,
                'validation_result': event.validation_result,
                'created_at': event.created_at.isoformat() if event.created_at else None
            }
            
            # Add screenshot URLs if available and requested
            if include_screenshots:
                if hasattr(event, 'screenshot_path') and event.screenshot_path:
                    # Convert file path to URL
                    screenshot_path = Path(event.screenshot_path)
                    if screenshot_path.exists():
                        detection_data['screenshot_url'] = f"/api/hil/screenshots/{screenshot_path.name}"
                    else:
                        detection_data['screenshot_url'] = None
                        
                if hasattr(event, 'screenshot_zoom_path') and event.screenshot_zoom_path:
                    zoom_path = Path(event.screenshot_zoom_path)
                    if zoom_path.exists():
                        detection_data['screenshot_zoom_url'] = f"/api/hil/screenshots/{zoom_path.name}"
                    else:
                        detection_data['screenshot_zoom_url'] = None
            
            enhanced_detections.append(detection_data)
        
        # Build comprehensive response
        response = {
            'session_id': session_id,
            'test_session_info': {
                'name': test_session.name,
                'status': test_session.status,
                'video_id': test_session.video_id,
                'created_at': test_session.created_at.isoformat() if test_session.created_at else None,
                'completed_at': test_session.completed_at.isoformat() if test_session.completed_at else None
            },
            'ground_truth_analysis': {
                'matching_metrics': matching_metrics.__dict__ if matching_metrics else None,
                'detailed_analysis': detailed_analysis,
                'matching_summary': matching_summary,
                'tolerance_ms': tolerance_ms
            },
            'detection_events': enhanced_detections,
            'hil_events': hil_events,
            'summary': {
                'total_detections': len(enhanced_detections),
                'detections_with_screenshots': len([d for d in enhanced_detections if d.get('screenshot_url')]),
                'precision': matching_metrics.precision if matching_metrics else 0.0,
                'recall': matching_metrics.recall if matching_metrics else 0.0,
                'f1_score': matching_metrics.f1_score if matching_metrics else 0.0,
                'mean_latency_ms': matching_metrics.mean_latency_ms if matching_metrics else 0.0,
                'within_tolerance_percentage': matching_metrics.within_tolerance_percentage if matching_metrics else 0.0
            },
            'visual_evidence': {
                'screenshots_available': include_screenshots,
                'screenshot_count': len([d for d in enhanced_detections if d.get('screenshot_url')]),
                'zoom_screenshot_count': len([d for d in enhanced_detections if d.get('screenshot_zoom_url')])
            }
        }
        
        logger.info(f"Ground truth comparison completed for HIL session {session_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ground truth comparison for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{session_id}/detection-events")
async def get_hil_detection_events(
    session_id: str,
    include_screenshots: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get HIL detection events with screenshot evidence and timing data.
    
    Args:
        session_id: HIL test session identifier
        include_screenshots: Whether to include screenshot URLs
        
    Returns:
        List of detection events with visual evidence and timing information
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get detection events from database
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()
        
        # Get HIL-specific events from monitoring service
        hil_events = get_hil_session_events(session_id)
        
        # Enhance with screenshot URLs
        enhanced_events = []
        for event in detection_events:
            event_data = {
                'id': event.id,
                'detection_id': getattr(event, 'detection_id', None),
                'timestamp': event.timestamp,
                'video_relative_timestamp': event.video_relative_timestamp,
                'actual_latency_ms': event.actual_latency_ms,
                'video_frame_number': event.video_frame_number,
                'labjack_voltage': event.labjack_voltage,
                'detection_channel': event.detection_channel,
                'timing_sync_quality': event.timing_sync_quality,
                'validation_result': event.validation_result,
                'source': getattr(event, 'source', 'unknown'),
                'detection_type': getattr(event, 'detection_type', 'unknown'),
                'created_at': event.created_at.isoformat() if event.created_at else None
            }
            
            # Add screenshot information
            if include_screenshots:
                screenshot_info = {}
                
                if hasattr(event, 'screenshot_path') and event.screenshot_path:
                    screenshot_path = Path(event.screenshot_path)
                    if screenshot_path.exists():
                        screenshot_info['screenshot_url'] = f"/api/hil/screenshots/{screenshot_path.name}"
                        screenshot_info['screenshot_filename'] = screenshot_path.name
                        screenshot_info['screenshot_exists'] = True
                    else:
                        screenshot_info['screenshot_exists'] = False
                        
                if hasattr(event, 'screenshot_zoom_path') and event.screenshot_zoom_path:
                    zoom_path = Path(event.screenshot_zoom_path)
                    if zoom_path.exists():
                        screenshot_info['screenshot_zoom_url'] = f"/api/hil/screenshots/{zoom_path.name}"
                        screenshot_info['screenshot_zoom_filename'] = zoom_path.name
                        screenshot_info['screenshot_zoom_exists'] = True
                    else:
                        screenshot_info['screenshot_zoom_exists'] = False
                
                event_data['screenshots'] = screenshot_info
            
            enhanced_events.append(event_data)
        
        response = {
            'session_id': session_id,
            'detection_events': enhanced_events,
            'hil_monitoring_events': hil_events,
            'summary': {
                'total_events': len(enhanced_events),
                'events_with_screenshots': len([e for e in enhanced_events if e.get('screenshots', {}).get('screenshot_exists')]),
                'latest_event_time': max([e['timestamp'] for e in enhanced_events]) if enhanced_events else None,
                'earliest_event_time': min([e['timestamp'] for e in enhanced_events]) if enhanced_events else None
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HIL detection events for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/screenshots/{screenshot_filename}")
async def serve_hil_screenshot(screenshot_filename: str):
    """
    Serve HIL screenshot files for display in the frontend.
    
    Args:
        screenshot_filename: Name of the screenshot file
        
    Returns:
        Image file response
    """
    try:
        # Define screenshot directories
        screenshot_dirs = [
            Path("screenshots/hil"),
            Path("screenshots"),
            Path("/app/screenshots/hil"),
            Path("/app/screenshots")
        ]
        
        # Find the screenshot file
        screenshot_path = None
        for screenshot_dir in screenshot_dirs:
            potential_path = screenshot_dir / screenshot_filename
            if potential_path.exists() and potential_path.is_file():
                screenshot_path = potential_path
                break
        
        if not screenshot_path:
            logger.warning(f"Screenshot not found: {screenshot_filename}")
            raise HTTPException(status_code=404, detail=f"Screenshot {screenshot_filename} not found")
        
        # Verify file is an image
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
        if screenshot_path.suffix.lower() not in allowed_extensions:
            raise HTTPException(status_code=400, detail="Invalid file type")
        
        # Return file response
        return FileResponse(
            path=str(screenshot_path),
            media_type="image/jpeg",
            filename=screenshot_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving screenshot {screenshot_filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving screenshot: {str(e)}")


@router.get("/{session_id}/analysis")
async def get_hil_analysis_summary(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive HIL analysis summary with performance metrics.
    
    Args:
        session_id: HIL test session identifier
        
    Returns:
        Analysis summary with performance metrics and recommendations
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get ground truth service
        gt_service = get_ground_truth_matching_service()
        
        # Get comprehensive analysis
        detailed_analysis = gt_service.get_detailed_analysis(session_id)
        matching_summary = gt_service.get_matching_results_summary(session_id)
        
        # Get detection events count
        detection_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).count()
        
        # Get screenshot availability
        events_with_screenshots = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.screenshot_path.isnot(None)
        ).count()
        
        response = {
            'session_id': session_id,
            'analysis_summary': detailed_analysis,
            'matching_summary': matching_summary,
            'visual_evidence_summary': {
                'total_detections': detection_count,
                'detections_with_screenshots': events_with_screenshots,
                'screenshot_coverage_percentage': (events_with_screenshots / detection_count * 100) if detection_count > 0 else 0
            },
            'performance_assessment': {
                'overall_status': 'PASS' if matching_summary.get('summary', {}).get('f1_score', 0) > 0.8 else 'NEEDS_IMPROVEMENT',
                'timing_accuracy': 'HIGH' if matching_summary.get('performance', {}).get('within_tolerance_percentage', 0) > 90 else 'MODERATE',
                'visual_evidence': 'COMPLETE' if events_with_screenshots == detection_count else 'PARTIAL'
            }
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HIL analysis for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{session_id}/detection-boundaries")
async def get_detection_boundaries_analysis(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detection boundary analysis for a HIL session to distinguish missing detections 
    from legitimate video end conditions.
    
    This endpoint analyzes:
    - When detection monitoring actually stopped vs when video ended
    - Categorizes ground truth events as during/after monitoring
    - Identifies true missing detections vs expected no-detections
    - Provides coverage and completeness metrics
    
    Args:
        session_id: HIL test session identifier
        
    Returns:
        Detection boundary analysis with categorized events and metrics
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")
        
        # Get detection events
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()
        
        # Convert to dict format for analysis
        detection_events_data = []
        for event in detection_events:
            detection_events_data.append({
                'id': event.id,
                'timestamp': event.timestamp,
                'video_timestamp': event.video_relative_timestamp,
                'detection_time': event.timestamp,
                'video_frame': event.video_frame_number,
                'latency_ms': event.actual_latency_ms
            })
        
        # Get ground truth events
        ground_truth_events = db.query(GroundTruthObject).filter(
            GroundTruthObject.test_session_id == session_id
        ).order_by(GroundTruthObject.frame_number).all()
        
        # Convert to dict format for analysis
        ground_truth_data = []
        for gt_event in ground_truth_events:
            ground_truth_data.append({
                'id': gt_event.id,
                'video_frame': gt_event.frame_number,
                'frame_number': gt_event.frame_number,
                'timestamp': getattr(gt_event, 'timestamp', None),
                'event_type': getattr(gt_event, 'event_type', 'detection'),
                'description': getattr(gt_event, 'description', '')
            })
        
        # Get video metadata
        video_metadata = {}
        if test_session.video_id:
            video = db.query(Video).filter(Video.id == test_session.video_id).first()
            if video:
                video_metadata = {
                    'duration': getattr(video, 'duration', 0),
                    'duration_s': getattr(video, 'duration_seconds', 0),
                    'fps': getattr(video, 'fps', 30),
                    'frame_rate': getattr(video, 'frame_rate', 30),
                    'total_frames': getattr(video, 'total_frames', 0),
                    'filename': getattr(video, 'filename', ''),
                    'width': getattr(video, 'width', 0),
                    'height': getattr(video, 'height', 0)
                }
        
        # Perform boundary analysis
        boundary_analysis = detection_boundary_analyzer.analyze_detection_boundaries(
            detection_events=detection_events_data,
            ground_truth_events=ground_truth_data,
            video_metadata=video_metadata
        )
        
        # Enhance response with session info
        response = {
            'session_id': session_id,
            'test_session_info': {
                'name': test_session.name,
                'status': test_session.status,
                'video_id': test_session.video_id,
                'created_at': test_session.created_at.isoformat() if test_session.created_at else None,
                'completed_at': test_session.completed_at.isoformat() if test_session.completed_at else None
            },
            'video_metadata': video_metadata,
            'boundary_analysis': boundary_analysis,
            'recommendations': {
                'status': boundary_analysis['boundary_analysis']['recommended_status'],
                'action_needed': _generate_recommendations(boundary_analysis),
                'coverage_assessment': _assess_coverage(boundary_analysis)
            }
        }
        
        logger.info(f"Detection boundary analysis completed for HIL session {session_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in detection boundary analysis for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _generate_recommendations(boundary_analysis: Dict[str, Any]) -> List[str]:
    """Generate actionable recommendations based on boundary analysis"""
    recommendations = []
    
    analysis = boundary_analysis['boundary_analysis']
    categorized = boundary_analysis['categorized_events']
    
    coverage = analysis.get('detection_coverage_percent', 0)
    missing_count = analysis.get('missing_detection_count', 0)
    post_video_count = analysis.get('post_video_gt_count', 0)
    
    if coverage < 50:
        recommendations.append("Detection coverage is insufficient - check equipment setup")
    elif coverage < 80:
        recommendations.append("Detection coverage is partial - verify monitoring duration")
    
    if missing_count > 5:
        recommendations.append(f"High number of missing detections ({missing_count}) - investigate detection system")
    elif missing_count > 2:
        recommendations.append(f"Some detections missing ({missing_count}) - review detection sensitivity")
    
    if post_video_count > 0:
        recommendations.append(f"{post_video_count} ground truth events after monitoring ended - this is expected behavior")
    
    if analysis.get('recommended_status') == 'complete_coverage':
        recommendations.append("Excellent detection coverage - no action needed")
    
    return recommendations


def _assess_coverage(boundary_analysis: Dict[str, Any]) -> str:
    """Assess overall coverage quality"""
    analysis = boundary_analysis['boundary_analysis']
    coverage = analysis.get('detection_coverage_percent', 0)
    missing_count = analysis.get('missing_detection_count', 0)
    
    if coverage >= 95 and missing_count == 0:
        return "EXCELLENT"
    elif coverage >= 80 and missing_count <= 2:
        return "GOOD"
    elif coverage >= 60 and missing_count <= 5:
        return "ACCEPTABLE"
    else:
        return "NEEDS_IMPROVEMENT"


# Export router
__all__ = ["router"]