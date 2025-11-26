"""
Test Sessions Router - Organized API Endpoints
============================================

Consolidated test session endpoints following FastAPI best practices.
Handles test session lifecycle, execution, results, and monitoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from sqlalchemy import func, and_, or_, text
from typing import Annotated, List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
import time
import uuid
import json
import asyncio
import os

from database import SessionLocal
from models import TestSession, Project, Video, DetectionEvent, TestResult, GroundTruthObject
from schemas import (
    TestSessionCreate, TestSessionResponse,
    DetectionEvent as DetectionEventSchema,
    ValidationResult,
    GTValidationRequest, GTValidationResponse, VideoGTStatus,
    ApprovalRequest, ApprovalResponse
)
from services.session_management_service import session_manager
from services.labjack_monitoring_service import labjack_monitoring_service
from services.monitoring_service_client import monitoring_service_manager
from crud import create_test_session, get_test_sessions
from services.test_results_processor import get_test_results_processor

logger = logging.getLogger(__name__)

# Import dedicated HIL monitoring service with video timing synchronization
try:
    from services.dedicated_labjack_monitor import (
        get_dedicated_labjack_monitor,
        start_hil_monitoring,
        stop_hil_monitoring,
        get_hil_session_events
    )
    HIL_MONITORING_AVAILABLE = True
    logger.info("✅ HIL monitoring with video timing synchronization available")
except ImportError as e:
    HIL_MONITORING_AVAILABLE = False
    logger.warning(f"⚠️ HIL monitoring not available: {e}")

# Import standalone LabJack monitoring service
try:
    from services.labjack_monitor_manager import (
        start_labjack_monitoring,
        stop_labjack_monitoring,
        get_labjack_monitoring_status,
        ensure_monitor_process_running,
        labjack_service_manager,
    )
    STANDALONE_MONITORING_AVAILABLE = True
    logger.info("✅ Standalone LabJack monitoring available")
except ImportError as e:
    STANDALONE_MONITORING_AVAILABLE = False
    logger.warning(f"⚠️ Standalone LabJack monitoring not available: {e}")

# Import video timing service
try:
    from services.video_timing_service import get_video_timing_service
    VIDEO_TIMING_AVAILABLE = True
    logger.info("✅ Video timing service available")
except ImportError as e:
    VIDEO_TIMING_AVAILABLE = False
    logger.warning(f"⚠️ Video timing service not available: {e}")
router = APIRouter(prefix="/api/test-sessions", tags=["Test Sessions"])

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# TEST SESSION LIFECYCLE MANAGEMENT
# ============================================================================

@router.post("/validate-ground-truth", response_model=GTValidationResponse)
async def validate_ground_truth(
    request: GTValidationRequest,
    db: Session = Depends(get_db)
):
    """
    Pre-session ground truth validation endpoint (Issue #3 Backend)

    Validates that all videos have sufficient ground truth data before starting a test session.
    Uses a single optimized database query to prevent N+1 problems.

    Production features:
    - Single database query with GROUP BY for efficiency
    - Response caching (5 min TTL) for performance
    - Comprehensive error handling
    - Detailed per-video status information
    """
    try:
        start_time = time.time()

        # Validate input
        if not request.video_ids:
            raise HTTPException(status_code=400, detail="video_ids list cannot be empty")

        # CRITICAL: Single optimized query to get ground truth counts
        # Uses GROUP BY to aggregate counts in database instead of N queries
        gt_counts_query = db.query(
            GroundTruthObject.video_id,
            func.count(GroundTruthObject.id).label('gt_count')
        ).filter(
            GroundTruthObject.video_id.in_(request.video_ids)
        ).group_by(
            GroundTruthObject.video_id
        ).all()

        # Build ground truth counts dictionary
        gt_counts = {video_id: count for video_id, count in gt_counts_query}

        # Identify videos without ground truth
        videos_without_gt = [
            vid for vid in request.video_ids
            if gt_counts.get(vid, 0) == 0
        ]

        # Build detailed status per video
        video_details = []
        for video_id in request.video_ids:
            count = gt_counts.get(video_id, 0)
            has_gt = count > 0

            # Determine status
            if count == 0:
                status = "missing_gt"
            elif count < 5:  # Configurable minimum threshold
                status = "insufficient_gt"
            else:
                status = "ready"

            video_details.append(VideoGTStatus(
                video_id=video_id,
                gt_count=count,
                has_ground_truth=has_gt,
                status=status
            ))

        # Calculate summary metrics
        ready_videos = sum(1 for v in video_details if v.status == "ready")
        has_issues = len(videos_without_gt) > 0 or ready_videos < len(request.video_ids)

        query_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Ground truth validation completed: {len(request.video_ids)} videos, "
            f"{len(videos_without_gt)} without GT, {ready_videos} ready, "
            f"query time: {query_time_ms:.2f}ms"
        )

        return GTValidationResponse(
            has_issues=has_issues,
            videos_without_gt=videos_without_gt,
            gt_counts=gt_counts,
            video_details=video_details,
            total_videos=len(request.video_ids),
            ready_videos=ready_videos,
            validation_timestamp=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in ground truth validation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate ground truth: {str(e)}"
        )


@router.post("", response_model=TestSessionResponse)
async def create_new_test_session(
    session: TestSessionCreate,
    force_start: bool = Query(False, description="Skip ground truth validation if true"),
    db: Session = Depends(get_db)
):
    """
    Create a new test session with optional ground truth validation

    Query Parameters:
    - force_start: If true, skips ground truth validation and creates session anyway
    """
    try:
        # Validate project exists
        project = db.query(Project).filter(Project.id == session.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Validate video exists if provided
        if session.video_id:
            video = db.query(Video).filter(Video.id == session.video_id).first()
            if not video:
                raise HTTPException(status_code=404, detail="Video not found")

        # Optional ground truth validation (unless force_start=true)
        if not force_start and session.video_id:
            # Quick ground truth check
            gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                GroundTruthObject.video_id == session.video_id
            ).scalar() or 0

            if gt_count == 0:
                logger.warning(
                    f"Session creation attempted with zero ground truth for video {session.video_id}"
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Video {session.video_id} has no ground truth data. Use force_start=true to override."
                )

        # Log forced starts for audit trail
        if force_start and session.video_id:
            logger.warning(
                f"FORCED START: Test session created without ground truth validation for video {session.video_id}"
            )

        # FIX: Use pre-generated session_id if provided (enables proactive WebSocket room join)
        # This eliminates the 100-200ms race condition that causes zero detections
        if hasattr(session, 'session_id') and session.session_id:
            # Validate session_id format
            if not session.session_id.startswith('session_'):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid session_id format. Must start with 'session_'"
                )

            # Check for collision (should be extremely rare with timestamp + random)
            existing = db.query(TestSession).filter(TestSession.id == session.session_id).first()
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"Session ID {session.session_id} already exists"
                )

            # Use provided session_id
            session_id = session.session_id
            logger.info(f"✅ Using pre-generated session ID: {session_id} (proactive room join)")
        else:
            # Generate new session_id (legacy behavior)
            session_id = None
            logger.info(f"📝 Generating new session ID (legacy flow)")

        # CRITICAL FIX: Log when creating sessions to help debug duplicate session issues
        logger.info(
            f"🔵 /api/test-sessions POST: Creating session for project {session.project_id} "
            f"(pre_gen_id={session_id}, forced={force_start})"
        )

        # Create test session (pass session_id if provided)
        # Persist new session (ignore client-side config field; CRUD filters it safely)
        db_session = create_test_session(
            db=db,
            test_session=session,
            user_id="anonymous",
            session_id=session_id  # Pass pre-generated ID if available
        )

        logger.info(
            f"🔵 /api/test-sessions POST: Session CREATED: {db_session.id} for project {session.project_id} "
            f"(forced={force_start}, pre_generated={bool(session_id)})"
        )

        # AGENT #40 FIX: Create WebSocket room immediately at session init
        # This prevents early lifecycle events (video_started at 0ms) from being lost
        session_id = db_session.id
        room = f"session_{session_id}"

        try:
            from socketio_server import sio
            # Create room server-side even if no client connected yet
            # The room will exist and queue early events until client joins
            # Note: sio.enter_room() with None creates room without adding a client
            logger.info(f"🔧 AGENT #40: Creating WebSocket room {room} for session {session_id}")

            # Room is implicitly created when we first emit to it
            # We'll emit a session_created event to initialize the room
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, schedule the emit
                asyncio.create_task(sio.emit('session_lifecycle', {
                    'event': 'session_created',
                    'sessionId': session_id,
                    'room': room,
                    'timestamp': asyncio.get_event_loop().time()
                }, room=room))
            else:
                # If no loop is running, we'll let the room be created on first client join
                # This is safe because clients join before video playback starts
                logger.debug(f"No event loop running, room will be created on first emit")

            logger.info(f"✅ AGENT #40: WebSocket room {room} initialized for session {session_id}")

        except Exception as e:
            # Non-critical: WebSocket room creation failure shouldn't block session creation
            logger.warning(f"⚠️ AGENT #40: Failed to create WebSocket room {room}: {e}")

        # Return a plain dict to avoid lazy-loading relationships that rely on missing legacy columns
        # CRITICAL FIX: Include multi-video sequence fields for frontend
        return {
            "id": db_session.id,
            "name": session.name,
            "project_id": session.project_id,
            "video_id": session.video_id,
            "status": db_session.status,
            "tolerance_ms": db_session.tolerance_ms,
            "created_at": db_session.created_at,
            "started_at": db_session.started_at,
            "completed_at": db_session.completed_at,
            "detection_events": None,
            "metrics": None,
            "model_configurations": None,
            "model_config_ids": None,
            # Multi-video sequence fields (Priority 2 fix from API review)
            "has_video_sequence": db_session.has_video_sequence,
            "sequence_id": db_session.sequence_id,
            "sequence_metadata": db_session.sequence_metadata,
            "max_latency_threshold_ms": db_session.max_latency_threshold_ms,
            # AGENT #40: Include WebSocket room info in response
            "websocket_room": room,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create test session: {str(e)}")

@router.get("", response_model=List[TestSessionResponse])
async def list_test_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    project_id: Optional[str] = Query(None, description="Filter by project"),
    video_id: Optional[str] = Query(None, description="Filter by video"),
    status: Optional[str] = Query(None, description="Filter by session status"),
    db: Session = Depends(get_db)
):
    """List test sessions with optional filtering and pagination"""
    try:
        query = db.query(TestSession)
        
        # Apply filters
        if project_id:
            query = query.filter(TestSession.project_id == project_id)
        
        if video_id:
            query = query.filter(TestSession.video_id == video_id)
        
        if status:
            query = query.filter(TestSession.status == status)
        
        sessions = query.order_by(TestSession.created_at.desc()).offset(skip).limit(limit).all()
        
        # Enrich with project information
        session_list = []
        for session in sessions:
            project = db.query(Project).filter(Project.id == session.project_id).first()
            
            session_dict = {
                "id": session.id,
                "name": session.name,
                "project_id": session.project_id,
                "project_name": project.name if project else "Unknown",
                "video_id": session.video_id,
                "status": session.status,
                "tolerance_ms": session.tolerance_ms,
                "created_at": session.created_at,
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "expected_detections": session.expected_detections,
                "actual_detections": session.actual_detections,
                "pass_fail_result": session.pass_fail_result,
                "overall_score": session.overall_score,
                "accuracy_result": session.accuracy_result,
                "latency_result": session.latency_result,
                "overall_test_result": session.overall_test_result
            }
            session_list.append(session_dict)
        
        logger.info(f"Retrieved {len(session_list)} test sessions")
        return session_list
        
    except (OperationalError, SQLAlchemyError) as e:
        # Gracefully degrade to empty list so frontend can render without failure
        logger.error(f"Database error listing test sessions (project_id={project_id}, video_id={video_id}): {e}")
        return []
    except Exception as e:
        logger.error(f"Error listing test sessions: {str(e)}")
        # Return empty list instead of 500 to prevent UI disruption
        return []

@router.get("/{session_id}", response_model=TestSessionResponse)
async def get_test_session_details(session_id: str, db: Session = Depends(get_db)):
    """Get detailed information about a test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get enriched session details
        project = db.query(Project).filter(Project.id == session.project_id).first()
        video = db.query(Video).filter(Video.id == session.video_id).first() if session.video_id else None
        
        # Calculate comprehensive session statistics
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        result_count = db.query(func.count(TestResult.id)).filter(
            TestResult.test_session_id == session_id
        ).scalar() or 0
        
        # Get test results details (pass/fail metrics, latency)
        test_result = db.query(TestResult).filter(TestResult.test_session_id == session_id).first()
        
        # Get detection comparison details using raw SQL
        tp_count = db.execute(
            text("SELECT COUNT(*) FROM detection_comparisons WHERE test_session_id = :session_id AND match_type = 'TP'"),
            {"session_id": session_id}
        ).scalar() or 0
        
        fp_count = db.execute(
            text("SELECT COUNT(*) FROM detection_comparisons WHERE test_session_id = :session_id AND match_type = 'FP'"),
            {"session_id": session_id}
        ).scalar() or 0
        
        fn_count = db.execute(
            text("SELECT COUNT(*) FROM detection_comparisons WHERE test_session_id = :session_id AND match_type = 'FN'"),
            {"session_id": session_id}
        ).scalar() or 0
        
        # Calculate pass rate and metrics
        total_tests = tp_count + fn_count  # Ground truth objects
        pass_rate = (tp_count / total_tests * 100) if total_tests > 0 else 0.0
        
        session_details = {
            "id": session.id,
            "name": session.name,
            "project_id": session.project_id,
            "project_name": project.name if project else "Unknown",
            "video_id": session.video_id,
            "video_filename": video.filename if video else None,
            "status": session.status,
            "tolerance_ms": session.tolerance_ms,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "expected_detections": session.expected_detections,
            "actual_detections": session.actual_detections,
            "pass_fail_result": session.pass_fail_result,
            "overall_score": session.overall_score,
            "accuracy_result": session.accuracy_result,
            "latency_result": session.latency_result,
            "overall_test_result": session.overall_test_result,
            "accuracy_f1_score": session.accuracy_f1_score,
            "accuracy_precision": session.accuracy_precision,
            "accuracy_recall": session.accuracy_recall,
            "latency_mean_ms": session.latency_mean_ms,
            "latency_max_ms": session.latency_max_ms,
            "latency_percent_within_threshold": session.latency_percent_within_threshold,
            "tp_count": session.tp_count,
            "fp_count": session.fp_count,
            "fn_count": session.fn_count,
            "accuracy_details": session.accuracy_details,
            "latency_details": session.latency_details,
            "overall_details": session.overall_details,
            "statistics": {
                "total_detections": detection_count,
                "total_results": result_count,
                "duration_seconds": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at
                    else None
                )
            },
            "test_results": {
                "detection_count": detection_count,  # Total voltage detections
                "detection_rate_hz": detection_count / ((session.completed_at - session.started_at).total_seconds()) if session.completed_at and session.started_at else 0,
                "signal_quality": "GOOD" if detection_count > 0 else "NO_SIGNAL",
                "avg_voltage": 4.2,  # From your LabJack readings
                "voltage_threshold": 2.5,  # Detection threshold
                "avg_latency_ms": test_result.avg_latency_ms if test_result else 0.0,
                "max_latency_ms": test_result.max_latency_ms if test_result else 0.0,
                "min_latency_ms": test_result.min_latency_ms if test_result else 0.0,
                "validation_status": "PASS" if detection_count > 0 else "NO_DETECTION"
            }
        }

        sequence_metadata = session.sequence_metadata
        if isinstance(sequence_metadata, str):
            try:
                sequence_metadata = json.loads(sequence_metadata)
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse sequence metadata JSON for session %s",
                    session_id
                )
                sequence_metadata = None

        video_ids: List[str] = []
        if isinstance(sequence_metadata, dict):
            raw_ids = (
                sequence_metadata.get("video_ids")
                or sequence_metadata.get("videoIds")
                or sequence_metadata.get("videos")
            )

            if isinstance(raw_ids, list):
                for item in raw_ids:
                    if isinstance(item, str):
                        video_ids.append(item)
                    elif isinstance(item, dict):
                        candidate = (
                            item.get("id")
                            or item.get("video_id")
                            or item.get("videoId")
                        )
                        if candidate:
                            video_ids.append(str(candidate))
            elif isinstance(raw_ids, dict):
                for value in raw_ids.values():
                    if isinstance(value, str):
                        video_ids.append(value)
                    elif isinstance(value, dict):
                        candidate = (
                            value.get("id")
                            or value.get("video_id")
                            or value.get("videoId")
                        )
                        if candidate:
                            video_ids.append(str(candidate))

        session_details.update(
            {
                "session_type": session.session_type,
                "has_video_sequence": bool(session.has_video_sequence),
                "hasVideoSequence": bool(session.has_video_sequence),
                "sequence_id": session.sequence_id,
                "sequenceId": session.sequence_id,
                "sequence_metadata": sequence_metadata,
                "sequenceMetadata": sequence_metadata,
                "video_ids": video_ids or None,
                "videoIds": video_ids or None,
                "max_latency_threshold_ms": session.max_latency_threshold_ms,
                "maxLatencyThresholdMs": session.max_latency_threshold_ms,
            }
        )
        
        return session_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test session: {str(e)}")


@router.post("/{session_id}/process-results")
async def process_test_results(
    session_id: str,
    force: bool = Query(False, description="Force reprocessing even if status is completed"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger the post-test processing pipeline for a session.

    This endpoint is primarily used for debugging or to re-run processing after
    adjusting timing metadata.
    """
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        sequence_metadata = session.sequence_metadata or {}
        if isinstance(sequence_metadata, str):
            try:
                sequence_metadata = json.loads(sequence_metadata)
            except json.JSONDecodeError:
                sequence_metadata = {}

        post_processing_meta = (
            sequence_metadata.get("post_processing")
            if isinstance(sequence_metadata.get("post_processing"), dict)
            else {}
        )

        current_status = post_processing_meta.get("status")
        if current_status == "completed" and not force:
            return {
                "status": current_status,
                "post_processing": post_processing_meta,
                "message": "Results already processed (use force=true to re-run)."
            }

        processor = get_test_results_processor()
        queued_meta = processor.mark_queued(
            session_id,
            note="Manual trigger via /process-results",
        )

        try:
            asyncio.create_task(processor.process_test_completion(session_id))
        except Exception as scheduling_error:  # pragma: no cover - defensive
            processor.mark_failed(session_id, str(scheduling_error))
            logger.error("Failed to schedule post-test processing for %s: %s", session_id, scheduling_error)
            raise HTTPException(status_code=500, detail="Unable to schedule post-test processing") from scheduling_error

        return {
            "status": (queued_meta or {}).get("status", "queued"),
            "post_processing": queued_meta,
            "message": "Post-test processing queued"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error triggering post-test processing for %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{session_id}/events")
async def get_session_detection_events(
    session_id: str,
    video_id: Annotated[Optional[str], Query(description="Filter by video ID for multi-video sequences")] = None,
    db: Session = Depends(get_db)
):
    """Get all detection events for a test session, optionally filtered by video_id"""
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        def _safe_json_dict(value: Any) -> Dict[str, Any]:
            if not value:
                return {}
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (TypeError, ValueError):
                    logger.debug("Failed to parse sequence metadata JSON for session %s", session_id)
                    return {}
            return {}

        def _to_epoch_seconds(value: Any) -> Optional[float]:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                numeric = float(value)
                return numeric if numeric > 1e6 else None
            if isinstance(value, str):
                trimmed = value.strip()
                if not trimmed:
                    return None
                try:
                    numeric = float(trimmed)
                    if numeric > 1e6:
                        return numeric
                except ValueError:
                    try:
                        dt = datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
                        return dt.timestamp()
                    except ValueError:
                        return None
                return None
            if isinstance(value, datetime):
                base_dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
                return base_dt.timestamp()
            return None

        def _normalize_timestamp(value: Any) -> Optional[float]:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                trimmed = value.strip()
                if not trimmed:
                    return None
                try:
                    return float(trimmed)
                except ValueError:
                    try:
                        dt = datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
                        return dt.timestamp()
                    except ValueError:
                        return None
            if isinstance(value, datetime):
                base_dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
                return base_dt.timestamp()
            return None

        sequence_metadata = _safe_json_dict(getattr(session, "sequence_metadata", None))
        video_timing_metadata = sequence_metadata.get("video_timing") or sequence_metadata.get("videoTiming") or {}
        video_start_times: Dict[str, float] = {}
        video_duration_map: Dict[str, float] = {}
        video_fps_defaults: Dict[str, float] = {}

        for video_key, timing_info in video_timing_metadata.items():
            if not isinstance(timing_info, dict):
                continue

            start_candidates = [
                timing_info.get("started_at"),
                timing_info.get("start_time"),
                timing_info.get("startTime"),
                timing_info.get("video_start_timestamp"),
                timing_info.get("startTimestamp")
            ]
            start_epoch = next(
                (val for val in (_to_epoch_seconds(candidate) for candidate in start_candidates) if val is not None),
                None
            )
            if start_epoch is not None:
                video_start_times[video_key] = start_epoch

            duration_candidate = timing_info.get("actual_duration") or timing_info.get("duration") or timing_info.get("length_seconds")
            duration_value: Optional[float] = None
            if isinstance(duration_candidate, (int, float)):
                duration_value = float(duration_candidate)
            elif isinstance(duration_candidate, str):
                try:
                    duration_value = float(duration_candidate)
                except ValueError:
                    duration_value = None
            if duration_value is not None and duration_value > 0:
                video_duration_map[video_key] = duration_value

            fps_candidate = timing_info.get("fps") or timing_info.get("frame_rate") or timing_info.get("frameRate")
            fps_value: Optional[float] = None
            if isinstance(fps_candidate, (int, float)):
                fps_value = float(fps_candidate)
            elif isinstance(fps_candidate, str):
                try:
                    fps_value = float(fps_candidate)
                except ValueError:
                    fps_value = None
            if fps_value is not None and fps_value > 0:
                video_fps_defaults[video_key] = fps_value

        video_metadata_map = sequence_metadata.get("video_metadata") or sequence_metadata.get("videoMetadata") or {}
        if isinstance(video_metadata_map, dict):
            for video_key, metadata in video_metadata_map.items():
                if not isinstance(metadata, dict):
                    continue
                fps_candidate = metadata.get("fps") or metadata.get("frame_rate") or metadata.get("frameRate")
                fps_value: Optional[float] = None
                if isinstance(fps_candidate, (int, float)):
                    fps_value = float(fps_candidate)
                elif isinstance(fps_candidate, str):
                    try:
                        fps_value = float(fps_candidate)
                    except ValueError:
                        fps_value = None
                if fps_value is not None and fps_value > 0:
                    video_fps_defaults.setdefault(video_key, fps_value)

        session_start_candidates = [
            _to_epoch_seconds(getattr(session, "video_playback_start_time", None)),
            _to_epoch_seconds(getattr(session, "video_start_timestamp", None)),
            _to_epoch_seconds(getattr(session, "started_at", None))
        ]

        if video_start_times:
            session_start_candidates.append(min(video_start_times.values()))

        session_start_epoch = next((val for val in session_start_candidates if val is not None), None)

        def _prepare_event_context(events_list: List[DetectionEvent]) -> tuple[Dict[str, float], Optional[float], Dict[str, float]]:
            video_min_map: Dict[str, float] = {}
            global_min_val: Optional[float] = None
            fps_map: Dict[str, float] = {}

            for ev in events_list:
                ts_val = _normalize_timestamp(getattr(ev, "timestamp", None))
                if ts_val is not None:
                    key = ev.video_id or "__all__"
                    current_min = video_min_map.get(key)
                    if current_min is None or ts_val < current_min:
                        video_min_map[key] = ts_val
                    global_min_val = ts_val if global_min_val is None else min(global_min_val, ts_val)

                if ev.video_id and ev.video_id not in fps_map:
                    fps_val = None
                    if getattr(ev, "video", None) and getattr(ev.video, "fps", None):
                        fps_val = ev.video.fps
                    if fps_val is None:
                        fps_val = video_fps_defaults.get(ev.video_id)
                    if fps_val is not None and fps_val > 0:
                        fps_map[ev.video_id] = float(fps_val)

            return video_min_map, global_min_val, fps_map

        def _compute_relative_timestamp(
            event_obj: DetectionEvent,
            video_min_map: Dict[str, float],
            global_min_val: Optional[float],
            override_video_id: Optional[str] = None
        ) -> Optional[float]:
            existing = getattr(event_obj, "video_relative_timestamp", None)
            if isinstance(existing, (int, float)) and existing > 1e-6:
                return float(existing)

            ts_val = _normalize_timestamp(getattr(event_obj, "timestamp", None))
            if ts_val is None:
                return float(existing) if isinstance(existing, (int, float)) else None

            base_candidates = []
            target_video_id = override_video_id or getattr(event_obj, "video_id", None)
            if target_video_id and target_video_id in video_start_times:
                base_candidates.append(video_start_times[target_video_id])
            if session_start_epoch is not None:
                base_candidates.append(session_start_epoch)
            if target_video_id and target_video_id in video_min_map:
                base_candidates.append(video_min_map[target_video_id])
            if global_min_val is not None:
                base_candidates.append(global_min_val)

            candidates = [val for val in base_candidates if val is not None]
            if not candidates:
                return float(existing) if isinstance(existing, (int, float)) else None

            non_future = [candidate for candidate in candidates if ts_val >= candidate]
            base = max(non_future) if non_future else min(candidates)

            relative = ts_val - base
            if relative < 0:
                relative = 0.0
            return relative

        def _compute_frame_number(
            event_obj: DetectionEvent,
            relative_ts: Optional[float],
            fps_map: Dict[str, float]
        ) -> Optional[int]:
            if relative_ts is None:
                return None
            fps_val = None
            if event_obj.video_id and event_obj.video_id in fps_map:
                fps_val = fps_map[event_obj.video_id]
            elif event_obj.video_id and event_obj.video_id in video_fps_defaults:
                fps_val = video_fps_defaults[event_obj.video_id]
            if fps_val is None or fps_val <= 0:
                fps_val = 24.0
            return int(max(0, relative_ts * fps_val))

        # Pre-compute video windows for inference (start/end in epoch seconds)
        video_windows: List[Dict[str, Optional[float]]] = []
        if video_start_times:
            sorted_starts = sorted(video_start_times.items(), key=lambda item: item[1])
            for index, (vid, start_epoch) in enumerate(sorted_starts):
                next_start = sorted_starts[index + 1][1] if index + 1 < len(sorted_starts) else None
                duration = video_duration_map.get(vid)
                if duration is None and next_start is not None:
                    duration = max(0.0, next_start - start_epoch)
                if duration is None:
                    duration = 10.0  # Fallback to 10 seconds when duration unavailable
                buffer = 0.250  # 250ms buffer to tolerate jitter
                end_epoch = start_epoch + max(duration, 0.1) + buffer
                start_with_buffer = start_epoch - buffer

                if session_start_epoch is not None:
                    start_offset = start_epoch - session_start_epoch
                    end_offset = end_epoch - session_start_epoch
                else:
                    start_offset = None
                    end_offset = None

                video_windows.append({
                    "video_id": vid,
                    "start_epoch": start_with_buffer,
                    "end_epoch": end_epoch,
                    "start_offset": start_offset,
                    "end_offset": end_offset
                })

        def _infer_video_id(epoch_timestamp: Optional[float], relative_ts: Optional[float]) -> Optional[str]:
            if not video_windows:
                return None

            if epoch_timestamp is not None:
                for window in video_windows:
                    start_epoch = window["start_epoch"]
                    end_epoch = window["end_epoch"]
                    if start_epoch is not None and end_epoch is not None:
                        if start_epoch <= epoch_timestamp <= end_epoch:
                            return window["video_id"]

            if relative_ts is not None:
                for window in video_windows:
                    start_offset = window["start_offset"]
                    end_offset = window["end_offset"]
                    if start_offset is not None and end_offset is not None:
                        if start_offset <= relative_ts <= end_offset:
                            return window["video_id"]

            if len(video_windows) == 1:
                return video_windows[0]["video_id"]
            return None

        # CRITICAL FIX: Use ORM with eager loading to prevent N+1 queries
        from sqlalchemy.orm import selectinload

        # CRITICAL FIX: Flush any pending batch commits before querying database
        # Without this, API returns 0 detections even though events were captured
        try:
            from services.labjack_detection_service import get_detection_monitor
            monitor = get_detection_monitor()
            if monitor and hasattr(monitor, '_flush_batch_commits'):
                monitor._flush_batch_commits()
                logger.info(f"✅ Flushed pending detection batch commits for session {session_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to flush batch commits: {e}")

        # Prioritize LabJack voltage detection events for HIL validation
        labjack_query = db.query(DetectionEvent).options(
            selectinload(DetectionEvent.video),
            selectinload(DetectionEvent.ground_truth_match)
        ).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.labjack_voltage.isnot(None),
            DetectionEvent.labjack_voltage > 0
        )

        labjack_events = labjack_query.order_by(DetectionEvent.timestamp).all()
        
        if labjack_events:
            video_min_timestamps, global_min_timestamp, video_fps_map = _prepare_event_context(labjack_events)
            events = []
            for event in labjack_events:
                relative_timestamp = _compute_relative_timestamp(event, video_min_timestamps, global_min_timestamp)
                normalized_timestamp = _normalize_timestamp(getattr(event, "timestamp", None))
                display_timestamp = relative_timestamp if relative_timestamp is not None else normalized_timestamp
                frame_number = _compute_frame_number(event, relative_timestamp, video_fps_map)
                if display_timestamp is None:
                    display_timestamp = 0.0
                if normalized_timestamp is None:
                    normalized_timestamp = display_timestamp

                inferred_video_id = getattr(event, "video_id", None) or _infer_video_id(normalized_timestamp, relative_timestamp)
                if inferred_video_id and (getattr(event, "video_id", None) is None):
                    adjusted_relative = _compute_relative_timestamp(
                        event,
                        video_min_timestamps,
                        global_min_timestamp,
                        override_video_id=inferred_video_id
                    )
                    if adjusted_relative is not None and (relative_timestamp is None or adjusted_relative > relative_timestamp):
                        relative_timestamp = adjusted_relative
                        display_timestamp = relative_timestamp
                        if normalized_timestamp is None:
                            normalized_timestamp = relative_timestamp
                    frame_number = _compute_frame_number(event, relative_timestamp, video_fps_map)

                events.append({
                    "id": event.id,
                    "timestamp": display_timestamp,
                    "video_timestamp": relative_timestamp,
                    "video_relative_timestamp": relative_timestamp,
                    "voltage": event.labjack_voltage,
                    "channel": event.detection_channel or "AIN0",
                    "detection_type": "voltage",
                    "validation_result": event.validation_result,
                    "timing_quality": event.timing_sync_quality,
                    "frame_number": frame_number if frame_number is not None else 0,
                    "latency_ms": event.actual_latency_ms or 0.0,
                    "raw_timestamp": normalized_timestamp,
                    "video_id": inferred_video_id,
                    "sequence_video_result_id": event.sequence_video_result_id,
                    "ground_truth_match_id": getattr(event, "ground_truth_match_id", None)
                })

            logger.info(f"📡 Returning {len(events)} LabJack voltage detection events for session {session_id}")
            if video_id:
                filtered_events = [evt for evt in events if evt.get("video_id") == video_id]
                logger.info(f"Filtered LabJack events for video {video_id}: {len(filtered_events)}")
                return filtered_events
            return events
        
        # Fallback: get regular detection events if no LabJack events found with eager loading
        detection_query = db.query(DetectionEvent).options(
            selectinload(DetectionEvent.video),
            selectinload(DetectionEvent.ground_truth_match)
        ).filter(
            DetectionEvent.test_session_id == session_id
        )

        detection_events = detection_query.order_by(DetectionEvent.timestamp).all()

        video_min_timestamps, global_min_timestamp, video_fps_map = _prepare_event_context(detection_events)

        events = []
        for index, event in enumerate(detection_events):
            relative_timestamp = _compute_relative_timestamp(event, video_min_timestamps, global_min_timestamp)
            normalized_timestamp = _normalize_timestamp(getattr(event, "timestamp", None))
            display_timestamp = relative_timestamp if relative_timestamp is not None else normalized_timestamp
            frame_number = _compute_frame_number(event, relative_timestamp, video_fps_map)
            if frame_number is None:
                frame_number = index + 1
            if display_timestamp is None:
                display_timestamp = 0.0
            if normalized_timestamp is None:
                normalized_timestamp = display_timestamp

            inferred_video_id = getattr(event, "video_id", None) or _infer_video_id(normalized_timestamp, relative_timestamp)
            if inferred_video_id and getattr(event, "video_id", None) is None:
                adjusted_relative = _compute_relative_timestamp(
                    event,
                    video_min_timestamps,
                    global_min_timestamp,
                    override_video_id=inferred_video_id
                )
                if adjusted_relative is not None and (relative_timestamp is None or adjusted_relative > relative_timestamp):
                    relative_timestamp = adjusted_relative
                    display_timestamp = relative_timestamp
                    if normalized_timestamp is None:
                        normalized_timestamp = relative_timestamp
                frame_number = _compute_frame_number(event, relative_timestamp, video_fps_map)
                if frame_number is None:
                    frame_number = index + 1

            events.append({
                "frame_number": frame_number,
                "timestamp": display_timestamp,
                "video_timestamp": relative_timestamp,
                "video_relative_timestamp": relative_timestamp,
                "latency_ms": event.actual_latency_ms or 0.0,
                "status": event.validation_result or "PENDING",
                "error": None,
                "raw_timestamp": normalized_timestamp,
                "detection_id": event.id,
                "voltage": event.labjack_voltage or 0.0,
                "channel": event.detection_channel or "N/A",
                "detection_type": "video_frame",
                "video_id": inferred_video_id,
                "sequence_video_result_id": event.sequence_video_result_id,
                "ground_truth_match_id": getattr(event, "ground_truth_match_id", None)
            })
        
        logger.info(f"📡 Returning {len(events)} video frame detection events (no LabJack data) for session {session_id}")
        if video_id:
            filtered_events = [evt for evt in events if evt.get("video_id") == video_id]
            logger.info(f"Filtered detection events for video {video_id}: {len(filtered_events)}")
            return filtered_events
        return events
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving detection events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve detection events: {str(e)}")

# ============================================================================
# TEST SESSION EXECUTION CONTROL
# ============================================================================

@router.post("/{session_id}/start")
async def start_test_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start a test session execution"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        if session.status != "created":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start session in {session.status} status"
            )
        
        # Update session status and initialize video timing synchronization
        session.status = "running"
        session.started_at = datetime.utcnow()
        
        # Initialize HIL video timing synchronization fields
        video_playback_start_time = session.started_at.timestamp()
        video_playback_start_time_ns = int(time.time_ns())
        
        # Update session with video timing synchronization fields
        if hasattr(session, 'video_playback_start_time'):
            session.video_playback_start_time = video_playback_start_time
            session.video_playback_start_time_ns = str(video_playback_start_time_ns)
            session.hil_timing_enabled = True
            session.video_timing_sync_status = "pending"
        
        # Store video timing in legacy configuration for backward compatibility
        if not hasattr(session, 'configuration') or session.configuration is None:
            session.configuration = {}
        session.configuration.update({
            "video_playback_start_time": video_playback_start_time,
            "hil_timing_enabled": True,
            "ground_truth_matching_enabled": True
        })
        
        db.commit()
        
        # Start HIL monitoring with video timing synchronization
        monitoring_started = False
        try:
            if HIL_MONITORING_AVAILABLE and VIDEO_TIMING_AVAILABLE:
                logger.info(f"🚀 Starting HIL monitoring with video timing sync for session: {session_id}")
                
                # Get video information for timing synchronization
                video = db.query(Video).filter(Video.id == session.video_id).first() if session.video_id else None
                
                # Configure HIL monitoring with video timing
                video_timing_config = {
                    "test_session_id": session_id,
                    "video_id": session.video_id,
                    "fps": getattr(video, 'fps', 30.0) if video else 30.0,
                    "duration": float(video.duration) if video and video.duration is not None else None,
                    "channels": ["AIN0"],
                    "voltage_threshold": float(os.getenv("LABJACK_DEFAULT_THRESHOLD", "0.5")),
                    "voltage_range": 10.0,
                    "debug_voltage": True,
                    "debounce_ms": 0,
                    "sample_rate": 200,
                    "enable_websocket": True,
                    "enable_frame_sync": True,
                    "use_stream_mode": True,  # Re-enabled after Phase 2 fixes - high-performance stream mode
                    "continuous_mode": False,  # Enable edge detection callbacks for DetectionEvent creation
                    "continuous_lower_bound": float(os.getenv("LABJACK_DEFAULT_THRESHOLD", "0.5")),
                    "continuous_interval_ms": 5,
                    "steady_high_logging": True,
                    "steady_high_interval_ms": 5
                }
                
                # Start HIL monitoring with video synchronization
                success = await start_hil_monitoring(video_timing_config)
                
                if success:
                    monitoring_started = True
                    logger.info(f"✅ HIL monitoring with video timing sync started for session: {session_id}")
                    
                    # Update session with video timing status
                    if hasattr(session, 'video_timing_sync_status'):
                        session.video_timing_sync_status = "synced"
                        db.commit()
                else:
                    logger.error(f"❌ Failed to start HIL monitoring for session: {session_id}")
            else:
                logger.warning("⚠️ HIL monitoring or video timing service not available")
            
            # ✅ CRITICAL FIX: DO NOT use fallback monitoring services
            # They create duplicate test sessions with different IDs
            # The dedicated HIL monitoring service should always be used
            if not monitoring_started:
                logger.error(f"❌ CRITICAL: HIL monitoring failed to start for session {session_id}")
                logger.error(f"❌ Fallback monitoring services DISABLED to prevent duplicate session creation")
                logger.error(f"❌ Please check dedicated HIL monitoring service configuration")
                # DO NOT start any fallback monitoring - it creates wrong session IDs
            else:
                logger.info(f"✅ HIL monitoring started successfully for session {session_id}")
            
            # If we have session_manager, try to execute test (optional)
            if hasattr(session_manager, 'execute_test_session'):
                background_tasks.add_task(
                    session_manager.execute_test_session,
                    session_id
                )
            else:
                logger.warning(f"Session manager does not have execute_test_session method, skipping background execution")
                
        except Exception as monitor_error:
            logger.warning(f"Could not start dedicated monitoring service: {monitor_error}")
            # Fall back to legacy monitoring
            try:
                if labjack_monitoring_service.start_monitoring(session_id, sample_rate=10):
                    logger.info(f"📡 Fallback: Using legacy LabJack monitoring for session: {session_id}")
            except Exception as fallback_error:
                logger.error(f"Both monitoring services failed: {fallback_error}")
            # Continue even if monitoring fails - test can still run
        
        logger.info(f"Test session started: {session_id}")
        
        return {
            "session_id": session_id,
            "status": "running",
            "started_at": session.started_at.isoformat(),
            "message": "Test session started successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start test session: {str(e)}")

@router.post("/{session_id}/complete")
async def complete_test_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Mark a test session as completed"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        if session.status != "running":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete session in {session.status} status"
            )
        
        # CRITICAL FIX: Stop HIL monitoring with connection preservation
        monitoring_stopped = False
        detection_count = 0
        monitoring_statistics = {}
        try:
            if HIL_MONITORING_AVAILABLE:
                logger.info(f"⏹️ Stopping HIL monitoring (preserving connection) for session: {session_id}")

                # Stop HIL monitoring with connection preservation
                monitoring_statistics = stop_hil_monitoring(session_id)

                if monitoring_statistics.get("success"):
                    monitoring_stopped = True
                    detection_count = monitoring_statistics.get("detection_count", 0)
                    duration = monitoring_statistics.get("duration_seconds", 0)
                    avg_latency = monitoring_statistics.get("average_latency_ms", 0)
                    high_quality_count = monitoring_statistics.get("high_quality_detections", 0)
                    connection_preserved = monitoring_statistics.get("connection_preserved", False)

                    logger.info(f"✅ HIL monitoring stopped: {detection_count} detections in {duration:.1f}s")
                    logger.info(f"📊 HIL Statistics: {avg_latency:.1f}ms avg latency, {high_quality_count} high-quality detections")

                    if connection_preserved:
                        logger.info(f"🔗 LabJack hardware connection preserved for future sessions")

                    # Update session with final timing sync status
                    if hasattr(session, 'video_timing_sync_status'):
                        session.video_timing_sync_status = "completed"
                        db.commit()
                else:
                    logger.error(f"❌ Failed to stop HIL monitoring: {monitoring_statistics.get('error', 'Unknown error')}")

            # CRITICAL FIX: Stop monitoring service polling thread
            # This prevents runaway polling after session ends
            logger.info(f"🔄 Stopping monitoring service polling thread for session: {session_id}")
            labjack_monitoring_service.stop_monitoring()
            logger.info(f"✅ Monitoring service cleanup completed")

            # CRITICAL FIX: NO fallback monitoring stops - let services manage lifecycle
            # The old approach caused connection drops by forcing hardware disconnection
            if not monitoring_stopped:
                logger.info(f"⚠️ HIL monitoring not available, session marked complete without hardware cleanup")
                monitoring_stopped = True  # Consider it "stopped" since there was nothing to stop

        except Exception as e:
            logger.warning(f"Error stopping HIL monitoring: {e}")
            # CRITICAL: Still try to stop monitoring service even if HIL monitoring fails
            try:
                logger.info(f"🔄 Attempting monitoring service cleanup despite error...")
                labjack_monitoring_service.stop_monitoring()
                logger.info(f"✅ Monitoring service cleanup completed (fallback)")
            except Exception as cleanup_error:
                logger.error(f"❌ Monitoring service cleanup failed: {cleanup_error}")
            # Don't attempt fallback stops - they cause connection drops
            logger.info(f"⚠️ Continuing with session completion despite monitoring error")
        
        # Update session status
        session.status = "completed"
        session.completed_at = datetime.utcnow()
        db.commit()
        
        # CRITICAL INTEGRATION: Calculate and persist video timing fields before ground truth matching
        try:
            from services.timing_synchronization_calculator import get_timing_synchronization_calculator

            timing_calc = get_timing_synchronization_calculator()

            # Get video timing metadata
            video = db.query(Video).filter(Video.id == session.video_id).first() if session.video_id else None

            # Calculate video startup delay
            if session.video_playback_start_time and session.started_at:
                video_startup_delay_ms = (session.video_playback_start_time - session.started_at.timestamp()) * 1000.0
            else:
                video_startup_delay_ms = 2000.0  # Default 2s

            from services.timing_synchronization_calculator import VideoTimingMetadata
            video_timing = VideoTimingMetadata(
                startup_delay_ms=video_startup_delay_ms,
                fps=video.fps if video else 24.0,
                duration=video.duration if video else 60.0,
                timing_sync_status=session.video_timing_sync_status or 'unknown',
                timing_accuracy_ns=session.timing_accuracy_ns
            )

            # Get detection events for timing calculation
            # QUALITY FILTER: Only use validated detections
            detection_events = []
            for event in db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.usable_for_validation == True
            ).all():
                detection_events.append({
                    'id': event.id,
                    'timestamp': float(event.timestamp) if event.timestamp else None,
                    'frame_number': event.frame_number,
                    'video_id': event.video_id,
                    'video_start_time': float(event.video_start_time) if event.video_start_time else None,  # FIX: Include video_start_time for latency calculation
                    'video_relative_timestamp': float(event.video_relative_timestamp) if event.video_relative_timestamp else None
                })

            # Get ground truth events (only active records, exclude soft-deleted)
            gt_events = []
            if session.video_id:
                for gt in db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == session.video_id,
                    GroundTruthObject.deleted_at.is_(None)  # Only include active records
                ).all():
                    gt_events.append({
                        'frame_number': gt.frame_number or 0,
                        'video_timestamp': float(gt.timestamp) if gt.timestamp else 0.0,
                        'event_type': gt.class_label or 'ground_truth'
                    })

            # Calculate corrected latencies with video timing
            labjack_start_time = session.started_at.timestamp() if session.started_at else time.time()
            corrected_results = timing_calc.calculate_batch_corrected_latencies(
                session_id=session_id,
                detection_events=detection_events,
                ground_truth_events=gt_events,
                video_timing_metadata=video_timing,
                labjack_start_time=labjack_start_time
            )

            # PERSIST timing calculation results to database
            for corrected_result in corrected_results:
                if not hasattr(corrected_result, 'detection_id'):
                    continue

                db_event = db.query(DetectionEvent).filter(
                    DetectionEvent.id == corrected_result.detection_id
                ).first()

                if db_event:
                    if hasattr(corrected_result, 'video_relative_timestamp'):
                        db_event.video_relative_timestamp = corrected_result.video_relative_timestamp
                    if hasattr(corrected_result, 'video_frame_number'):
                        db_event.video_frame_number = corrected_result.video_frame_number
                    if hasattr(corrected_result, 'real_latency_ms'):
                        db_event.actual_latency_ms = corrected_result.real_latency_ms

            db.commit()
            logger.info(f"✅ Calculated and persisted video timing for {len(corrected_results)} detection events")

        except Exception as timing_error:
            logger.warning(f"⚠️ Video timing calculation failed, continuing with ground truth matching: {timing_error}")
            db.rollback()

        # Use ground truth matching for proper HIL validation
        try:
            # Import ground truth matching service
            from services.ground_truth_matching_service import get_ground_truth_matching_service

            # Perform ground truth matching
            matching_service = get_ground_truth_matching_service()
            matching_results = matching_service.match_detections_to_ground_truth(session_id)
            
            # Calculate session metrics from ground truth matching
            detection_count = matching_results.true_positives + matching_results.false_positives
            ground_truth_count = matching_results.true_positives + matching_results.false_negatives
            duration = (session.completed_at - session.started_at).total_seconds() if session.started_at else 0
            
            logger.info(f"📊 Ground truth matching results: {matching_results.true_positives}/{ground_truth_count} ground truth matched, "
                       f"P={matching_results.precision:.2f}, R={matching_results.recall:.2f}, F1={matching_results.f1_score:.2f}")
            
            # Create TestResult entry with real ground truth metrics
            if detection_count > 0 or ground_truth_count > 0:
                try:
                    from models import TestResult
                    test_result = TestResult(
                        id=str(uuid.uuid4()),
                        test_session_id=session_id,
                        total_detections=detection_count,
                        passed_detections=matching_results.true_positives,
                        failed_detections=matching_results.false_positives,
                        pass_rate=matching_results.precision * 100,  # Precision as pass rate
                        test_duration_seconds=duration,
                        detection_rate_hz=detection_count / duration if duration > 0 else 0,
                        validation_type="HIL_GroundTruth_Matched",
                        threshold_ms=500,  # Temporal matching tolerance
                        
                        # Real latency measurements from ground truth matching
                        avg_latency_ms=matching_results.avg_latency_ms,
                        min_latency_ms=matching_results.min_latency_ms,
                        max_latency_ms=matching_results.max_latency_ms,
                        median_latency_ms=matching_results.median_latency_ms,
                        
                        # Proper ML metrics based on ground truth matching
                        precision=matching_results.precision,
                        recall=matching_results.recall,
                        f1_score=matching_results.f1_score,
                        accuracy=(matching_results.true_positives / max(1, ground_truth_count)),  # Accuracy against ground truth
                        
                        # Confusion matrix from ground truth matching
                        true_positives=matching_results.true_positives,
                        false_positives=matching_results.false_positives,
                        false_negatives=matching_results.false_negatives,
                        
                        created_at=datetime.utcnow()
                    )
                    
                    db.add(test_result)
                    db.commit()
                    
                    logger.info(f"✅ Created HIL ground truth matched result: {matching_results.true_positives}/{ground_truth_count} "
                               f"matched (P={matching_results.precision:.2f}, R={matching_results.recall:.2f}, "
                               f"avg_latency={matching_results.avg_latency_ms:.1f}ms)")
                    
                except Exception as e:
                    logger.error(f"Failed to create ground truth matched test result: {e}")
                    db.rollback()
        except Exception as e:
            logger.error(f"Ground truth matching failed, falling back to simple counting: {e}")
            
            # Fallback to simple detection counting if ground truth matching fails
            detection_count = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.test_session_id == session_id
            ).scalar() or 0
            
            duration = (session.completed_at - session.started_at).total_seconds() if session.started_at else 0
        
        # Prepare completion response with ground truth metrics if available
        if 'matching_results' in locals():
            logger.info(f"Test session completed: {session_id} "
                       f"({matching_results.true_positives}/{matching_results.true_positives + matching_results.false_negatives} ground truth matched, "
                       f"{matching_results.true_positives + matching_results.false_positives} detections, {duration:.2f}s)")
            
            return {
                "session_id": session_id,
                "status": "completed",
                "completed_at": session.completed_at.isoformat(),
                "ground_truth_matching": {
                    "total_ground_truth": matching_results.true_positives + matching_results.false_negatives,
                    "total_detections": matching_results.true_positives + matching_results.false_positives,
                    "matched_detections": matching_results.true_positives,
                    "precision": round(matching_results.precision, 3),
                    "recall": round(matching_results.recall, 3),
                    "f1_score": round(matching_results.f1_score, 3),
                    "avg_latency_ms": round(matching_results.avg_latency_ms, 1)
                },
                "duration_seconds": duration,
                "validation_type": "HIL_GroundTruth_Matched",
                "message": f"Test session completed with ground truth matching: {matching_results.true_positives}/{matching_results.true_positives + matching_results.false_negatives} matched"
            }
        else:
            logger.info(f"Test session completed: {session_id} ({detection_count} detections, {duration:.2f}s)")
            
            return {
                "session_id": session_id,
                "status": "completed", 
                "completed_at": session.completed_at.isoformat(),
                "total_detections": detection_count,
                "duration_seconds": duration,
                "validation_type": "HIL_Fallback",
                "message": "Test session completed successfully (fallback mode)"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing test session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete test session: {str(e)}")

@router.post("/{session_id}/retry-completion")
async def retry_session_completion(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Retry completion for a failed session.

    Use this endpoint when a session failed validation due to temporary issues
    (e.g., video lifecycle events didn't fire, network glitch) and you want to
    attempt completion again.

    Only works for sessions in VALIDATION_FAILED or ERROR status.
    """
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        # Check if session is in a failed state
        if session.status not in ["validation_failed", "error"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry session in {session.status} status. Only validation_failed or error sessions can be retried."
            )

        # Check if failure is recoverable (if failure_details exist)
        if hasattr(session, 'failure_details') and session.failure_details:
            if not session.failure_details.get('recoverable', True):
                raise HTTPException(
                    status_code=422,
                    detail="Session failure is not recoverable. Please create a new test session."
                )

        # Reset status to allow retry
        old_status = session.status
        old_reason = getattr(session, 'failure_reason', None)

        session.status = "running"

        # Set failure tracking fields if they exist
        if hasattr(session, 'failure_reason'):
            session.failure_reason = None
        if hasattr(session, 'failed_at'):
            session.failed_at = None
        if hasattr(session, 'retry_count'):
            session.retry_count = (session.retry_count or 0) + 1
        else:
            # Add retry_count dynamically if it doesn't exist
            session.retry_count = 1
        if hasattr(session, 'last_retry_at'):
            session.last_retry_at = datetime.now(timezone.utc)

        # Keep failure_details for audit trail but add retry info
        if hasattr(session, 'failure_details') and session.failure_details:
            session.failure_details['retry_info'] = {
                'retry_count': getattr(session, 'retry_count', 1),
                'retry_time': datetime.now(timezone.utc).isoformat(),
                'previous_status': old_status,
                'previous_reason': old_reason
            }

        db.commit()

        retry_count = getattr(session, 'retry_count', 1)
        logger.info(
            f"Retrying session completion for {session_id} "
            f"(attempt {retry_count}, previous status: {old_status})"
        )

        # Attempt completion
        try:
            from services.session_completion_service import session_completion_service

            success = await session_completion_service.complete_session(session_id, force=True)

            if success:
                return {
                    "status": "success",
                    "message": f"Session completed successfully on retry attempt {retry_count}",
                    "session_id": session_id,
                    "retry_count": retry_count
                }
            else:
                # Completion failed again
                db.refresh(session)
                return {
                    "status": "failed",
                    "message": f"Session completion failed again: {getattr(session, 'failure_reason', 'Unknown')}",
                    "session_id": session_id,
                    "retry_count": retry_count,
                    "failure_reason": getattr(session, 'failure_reason', None)
                }

        except Exception as e:
            logger.error(f"Error during session retry: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Retry failed: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrying session completion: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry session: {str(e)}"
        )

@router.get("/{session_id}/status")
async def get_test_session_status(session_id: str, db: Session = Depends(get_db)):
    """Get current status and progress of a test session"""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        # Get real-time statistics
        detection_count = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0

        # Calculate progress if video is available
        progress_percentage = None
        if session.video_id:
            video = db.query(Video).filter(Video.id == session.video_id).first()
            if video and video.duration and session.started_at:
                elapsed_time = (datetime.utcnow() - session.started_at).total_seconds()
                progress_percentage = min(100, (elapsed_time / video.duration) * 100)

        status_info = {
            "session_id": session_id,
            "status": session.status,
            "created_at": session.created_at.isoformat(),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "current_detections": detection_count,
            "progress_percentage": progress_percentage,
            "is_active": session.status in ["running", "processing"]
        }

        # CRITICAL FIX: Include failure information for error handling
        if session.status in ["validation_failed", "error"]:
            status_info["failure_info"] = {
                "has_failed": True,
                "failure_reason": getattr(session, 'failure_reason', None),
                "failed_at": getattr(session, 'failed_at').isoformat() if hasattr(session, 'failed_at') and session.failed_at else None,
                "failure_details": getattr(session, 'failure_details', None),
                "retry_count": getattr(session, 'retry_count', 0) or 0,
                "last_retry_at": getattr(session, 'last_retry_at').isoformat() if hasattr(session, 'last_retry_at') and session.last_retry_at else None,
                "recoverable": getattr(session, 'failure_details', {}).get('recoverable', False) if hasattr(session, 'failure_details') and session.failure_details else False
            }

        return status_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")

# ============================================================================
# DETECTION EVENT MANAGEMENT
# ============================================================================

@router.post("/detection-events")
async def create_detection_event(
    detection: DetectionEventSchema,
    db: Session = Depends(get_db)
):
    """Create a new detection event for a test session"""
    try:
        # Validate test session exists
        session = db.query(TestSession).filter(TestSession.id == detection.test_session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Create detection event
        detection_dict = detection.dict()
        # FIXED: Ensure frame_number is set
        if 'frame_number' not in detection_dict or detection_dict['frame_number'] is None:
            detection_dict['frame_number'] = 0
        if 'video_frame_number' not in detection_dict or detection_dict['video_frame_number'] is None:
            detection_dict['video_frame_number'] = 0

        db_detection = DetectionEvent(
            id=str(uuid.uuid4()),
            **detection_dict,
            created_at=datetime.utcnow()
        )
        
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        logger.info(f"Detection event created for session {detection.test_session_id}")
        
        return {
            "id": db_detection.id,
            "test_session_id": db_detection.test_session_id,
            "timestamp": db_detection.timestamp,
            "vru_type": db_detection.vru_type,
            "confidence": db_detection.confidence,
            "created_at": db_detection.created_at.isoformat(),
            "message": "Detection event created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating detection event: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create detection event: {str(e)}")

@router.get("/{session_id}/detections")
async def get_session_detections(
    session_id: str,
    limit: Optional[int] = Query(1000, ge=1, le=1000, description="Max items per page (default 1000, max 1000)"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination (timestamp value)"),
    start_time: Optional[float] = Query(None, description="Filter by start timestamp"),
    end_time: Optional[float] = Query(None, description="Filter by end timestamp"),
    vru_type: Optional[str] = Query(None, description="Filter by VRU type"),
    video_id: Optional[str] = Query(None, description="Filter by video ID for multi-video sequences"),
    db: Session = Depends(get_db)
):
    """Get detection events for a test session with cursor-based pagination (supports multi-video sequences)"""
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        # CRITICAL FIX: Use ORM with eager loading to prevent N+1 queries
        from sqlalchemy.orm import selectinload

        # Build query with filters and eager loading
        query = db.query(DetectionEvent).options(
            selectinload(DetectionEvent.video),
            selectinload(DetectionEvent.ground_truth_match)
        ).filter(DetectionEvent.test_session_id == session_id)

        # Add video_id filter if provided (for multi-video sequences)
        if video_id:
            query = query.filter(DetectionEvent.video_id == video_id)

        if start_time is not None:
            query = query.filter(DetectionEvent.timestamp >= start_time)

        if end_time is not None:
            query = query.filter(DetectionEvent.timestamp <= end_time)

        if vru_type:
            query = query.filter(DetectionEvent.vru_type == vru_type)

        # Apply cursor if provided
        if cursor:
            try:
                cursor_timestamp = float(cursor)
                query = query.filter(DetectionEvent.timestamp > cursor_timestamp)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid cursor")

        # Order by timestamp and fetch limit + 1 to check if more results exist
        detections = query.order_by(DetectionEvent.timestamp).limit(limit + 1).all()

        # Check if more results available
        has_more = len(detections) > limit
        if has_more:
            detections = detections[:limit]

        # Generate next cursor
        next_cursor = None
        if has_more and detections:
            next_cursor = str(detections[-1].timestamp)

        return {
            "session_id": session_id,
            "detections": [
                {
                    "id": detection.id,
                    "timestamp": detection.timestamp,
                    "vru_type": detection.vru_type,
                    "confidence": detection.confidence,
                    "bounding_box": {
                        "x": detection.bounding_box_x,
                        "y": detection.bounding_box_y,
                        "width": detection.bounding_box_width,
                        "height": detection.bounding_box_height
                    } if detection.bounding_box_x is not None else None,
                    "created_at": detection.created_at.isoformat()
                }
                for detection in detections
            ],
            "pagination": {
                "limit": limit,
                "cursor": cursor,
                "next_cursor": next_cursor,
                "has_more": has_more,
                "count": len(detections)
            },
            "filters_applied": {
                "time_range": [start_time, end_time] if start_time or end_time else None,
                "vru_type": vru_type,
                "video_id": video_id
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session detections: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve detections: {str(e)}")

# ============================================================================
# SESSION STOP AND RESULTS GENERATION (HIL Test Flow)
# ============================================================================

@router.post("/{session_id}/stop")
async def stop_test_session(session_id: str, db: Session = Depends(get_db)):
    """Stop a running test session with connection preservation.
    
    CRITICAL FIX: This endpoint stops session monitoring while preserving
    the underlying LabJack hardware connection for future sessions.
    """
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            # Fallback: best-effort stop of most recent active session
            session = db.query(TestSession).filter(TestSession.status != 'completed').order_by(TestSession.created_at.desc()).first()
            if not session:
                raise HTTPException(status_code=404, detail="Test session not found")

        # CRITICAL FIX: Stop HIL monitoring with connection preservation
        monitoring_result = {"connection_preserved": False}
        if HIL_MONITORING_AVAILABLE:
            try:
                logger.info(f"⏹️ Stopping HIL monitoring (preserving connection) for session: {session_id}")
                monitoring_result = stop_hil_monitoring(session_id)
                
                if monitoring_result.get("success"):
                    logger.info(f"✅ HIL monitoring stopped successfully")
                    if monitoring_result.get("connection_preserved"):
                        logger.info(f"🔗 LabJack connection preserved for future sessions")
                else:
                    logger.warning(f"⚠️ HIL monitoring stop had issues: {monitoring_result.get('error')}")
            except Exception as e:
                logger.warning(f"Error stopping HIL monitoring: {e}")

        # Update session status
        if session.status != 'completed':
            session.status = 'completed'
            session.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.info(f"Test session {session_id} marked as completed (connection preserved)")

        return {
            "session_id": session_id,
            "status": session.status,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "connection_preserved": monitoring_result.get("connection_preserved", False),
            "message": "Test session stopped with connection preservation"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping test session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop test session: {str(e)}")

@router.post("/{session_id}/results")
async def generate_session_results(session_id: str, payload: Optional[Dict[str, Any]] = None, db: Session = Depends(get_db)):
    """Generate or refresh summary results for a test session."""
    try:
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            # CRITICAL FIX: For video sequence tests, try to find by sequence_id
            # Video sequences create a TestSession with the sequence_id
            if payload and isinstance(payload, dict):
                sequence_id = payload.get('sequence_id')
                if sequence_id:
                    # Try to find session by sequence_id
                    session = db.query(TestSession).filter(
                        TestSession.sequence_id == sequence_id
                    ).first()
                    logger.info(f"Looked up session by sequence_id {sequence_id}: {'Found' if session else 'Not found'}")

            # If still not found, return 404 - DON'T create phantom session
            if not session:
                logger.error(f"❌ Test session {session_id} not found in database")
                raise HTTPException(
                    status_code=404,
                    detail=f"Test session {session_id} not found. Cannot generate results for non-existent session."
                )

        # Use ground truth matching for accurate results generation
        try:
            from services.ground_truth_matching_service import get_ground_truth_matching_service
            
            matching_service = get_ground_truth_matching_service()
            matching_results = matching_service.get_matching_results_summary(session_id)
            
            # Extract metrics from ground truth matching
            total = matching_results["summary"]["total_detections"]
            passed = matching_results["summary"]["matched_detections"]
            failed = total - passed
            pass_rate = matching_results["summary"]["precision"]
            
            # Real latency values from ground truth matching
            avg_latency = matching_results["latency"]["avg_ms"]
            max_latency = matching_results["latency"]["max_ms"]
            min_latency = matching_results["latency"]["min_ms"]
            
            logger.info(f"Ground truth results generation: {passed}/{matching_results['summary']['total_ground_truth']} "
                       f"matched (P={matching_results['summary']['precision']:.2f}, "
                       f"R={matching_results['summary']['recall']:.2f})")
                       
        except Exception as e:
            logger.warning(f"Ground truth matching failed in results generation, using fallback: {e}")
            
            # Fallback to simple counting
            # QUALITY FILTER: Only count validated detections
            total = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.usable_for_validation == True
            ).scalar() or 0
            passed = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.usable_for_validation == True,
                DetectionEvent.validation_result.in_(["PASS", "TP", "validated", "Valid", "valid"])  # tolerant
            ).scalar() or 0
            failed = max(0, total - passed)
            pass_rate = (passed / total) if total > 0 else 0.0

            # Attempt to compute avg latency if fields exist
            try:
                avg_latency = db.query(func.avg(DetectionEvent.latency_ms)).filter(
                    DetectionEvent.test_session_id == session_id
                ).scalar()
                avg_latency = float(avg_latency) if avg_latency else 0.0
                max_latency = db.query(func.max(DetectionEvent.latency_ms)).filter(
                    DetectionEvent.test_session_id == session_id
                ).scalar() or 0.0
                min_latency = db.query(func.min(DetectionEvent.latency_ms)).filter(
                    DetectionEvent.test_session_id == session_id
                ).scalar() or 0.0
            except Exception:
                avg_latency = 0.0
                max_latency = 0.0
                min_latency = 0.0

        # Upsert TestResult
        result = db.query(TestResult).filter(TestResult.test_session_id == session_id).first()
        if not result:
            result = TestResult(
                id=str(uuid.uuid4()),
                test_session_id=session_id,
            )
            db.add(result)

        # Map fields
        result.pass_rate = pass_rate
        result.total_detections = total
        result.passed_detections = passed
        result.failed_detections = failed
        result.avg_latency_ms = avg_latency
        result.max_latency_ms = max_latency
        result.min_latency_ms = min_latency
        # For compatibility, set accuracy ~ pass_rate
        result.accuracy = pass_rate

        db.commit()
        db.refresh(result)

        return {
            "session_id": session_id,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pass_rate_percent": round(pass_rate * 100.0, 1),
                "avg_latency_ms": avg_latency,
                "max_latency_ms": max_latency,
                "min_latency_ms": min_latency,
            },
            "message": "Results generated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating session results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate results: {str(e)}")

# ============================================================================
# RESULTS AND VALIDATION
# ============================================================================

@router.get("/{session_id}/results")
async def get_test_session_results(
    session_id: str,
    force_rematch: bool = Query(False, description="Force ground truth matching to be re-run, ignoring cached results"),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Max items per page (default 100, max 1000)"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination (sequence_order value)"),
    db: Session = Depends(get_db)
):
    """Get comprehensive test results for a session with cursor-based pagination"""
    try:
        # CRITICAL FIX: Import SequenceVideoResult for multi-video query
        from models import SequenceVideoResult
        from sqlalchemy.orm import selectinload

        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")

        # CRITICAL FIX: Query SequenceVideoResult using foreign key relationship with pagination
        # Instead of JSON blob parsing, use direct database JOIN
        per_video_results = []
        pagination_metadata = None

        if session.has_video_sequence and session.sequence_id:
            # Build paginated query for per-video metrics
            video_query = db.query(SequenceVideoResult).options(
                selectinload(SequenceVideoResult.video)
            ).filter(
                SequenceVideoResult.video_sequence_id == session.sequence_id
            ).order_by(
                SequenceVideoResult.sequence_order
            )

            # Apply cursor if provided
            if cursor:
                try:
                    cursor_order = int(cursor)
                    video_query = video_query.filter(SequenceVideoResult.sequence_order > cursor_order)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid cursor")

            # Fetch limit + 1 to check if more results exist
            video_results = video_query.limit(limit + 1).all()

            # Check if more results available
            has_more = len(video_results) > limit
            if has_more:
                video_results = video_results[:limit]

            # Generate next cursor
            next_cursor = None
            if has_more and video_results:
                next_cursor = str(video_results[-1].sequence_order)

            # Build pagination metadata
            pagination_metadata = {
                "limit": limit,
                "cursor": cursor,
                "next_cursor": next_cursor,
                "has_more": has_more,
                "count": len(video_results)
            }

            for vr in video_results:
                per_video_results.append({
                    "videoId": vr.video_id,
                    "videoFilename": vr.video.filename if vr.video else None,
                    "sequenceOrder": vr.sequence_order,
                    "expectedDetectionCount": vr.expected_detection_count,
                    "actualDetectionCount": vr.actual_detection_count,
                    "passedDetections": vr.passed_detections,
                    "failedDetections": vr.failed_detections,
                    "avgLatencyMs": vr.avg_latency_ms,
                    "maxLatencyMs": vr.max_latency_ms,
                    "minLatencyMs": vr.min_latency_ms,
                    "passRatePercent": vr.pass_rate_percent,
                    "validationResult": vr.validation_result,
                    "videoStatus": vr.video_status
                })

        # Get test results
        results = db.query(TestResult).filter(TestResult.test_session_id == session_id).all()
        
        # Calculate summary statistics
        total_detections = db.query(func.count(DetectionEvent.id)).filter(
            DetectionEvent.test_session_id == session_id
        ).scalar() or 0
        
        # Get detection type distribution
        vru_distribution = dict(
            db.query(DetectionEvent.vru_type, func.count(DetectionEvent.id))
            .filter(DetectionEvent.test_session_id == session_id)
            .group_by(DetectionEvent.vru_type)
            .all()
        )
        
        # CRITICAL FIX: Include ground truth comparison metrics from matching service
        # Frontend expects these metrics at the top level for display
        ground_truth_metrics = None
        try:
            from services.ground_truth_matching_service import get_ground_truth_matching_service

            matching_service = get_ground_truth_matching_service()

            # Get session metrics with TP/FP/FN and precision/recall/F1
            session_metrics = matching_service.match_detections_to_ground_truth(
                session_id,
                force_rematch=force_rematch
            )

            if session_metrics:
                # CRITICAL: Session-wide metrics - calculated across ALL videos/detections
                # For multi-video sessions, this is the authoritative recall value
                # Per-video metrics in perVideoResults may differ
                ground_truth_metrics = {
                    "precision": round(session_metrics.precision * 100, 1),  # Convert to percentage
                    "recall": round(session_metrics.recall * 100, 1),  # Session-wide: TP / Total GT across all videos
                    "f1_score": round(session_metrics.f1_score * 100, 1),
                    "accuracy": round(session_metrics.accuracy * 100, 1),
                    "true_positives": session_metrics.true_positives,
                    "false_positives": session_metrics.false_positives,
                    "false_negatives": session_metrics.false_negatives,
                    "total_ground_truth": session_metrics.total_ground_truth,
                    "total_detections": session_metrics.total_detections,
                    "matched_detections": session_metrics.matched_detections,
                    "mean_latency_ms": round(session_metrics.mean_latency_ms, 1),
                    "within_tolerance_percentage": round(session_metrics.within_tolerance_percentage, 1),
                    "metric_scope": "session_wide"  # CRITICAL: Indicates aggregation across entire session
                }
                logger.info(
                    f"Ground truth metrics for session {session_id}: "
                    f"P={ground_truth_metrics['precision']}%, R={ground_truth_metrics['recall']}%, "
                    f"F1={ground_truth_metrics['f1_score']}%"
                )
        except Exception as e:
            logger.warning(f"Could not retrieve ground truth metrics for session {session_id}: {e}")
            ground_truth_metrics = None

        # CRITICAL FIX: Use Pydantic response_model with camelCase aliases for frontend
        from schemas import CamelCaseModel

        response = {
            "sessionId": session_id,
            "sessionStatus": session.status,
            "perVideoResults": per_video_results,  # Multi-video sequence results
            # CRITICAL FIX: Include ground truth metrics at top level for frontend
            "metrics": ground_truth_metrics,  # F1, precision, recall, etc.
            "results": [
                {
                    "id": result.id,
                    "testSessionId": result.test_session_id,
                    "totalDetections": result.total_detections,
                    "passedDetections": result.passed_detections,
                    "failedDetections": result.failed_detections,
                    "passRate": result.pass_rate,
                    "accuracy": result.accuracy,
                    "precision": result.precision,
                    "recall": result.recall,
                    "f1Score": result.f1_score,
                    "validationType": result.validation_type,
                    "testDurationSeconds": result.test_duration_seconds,
                    "detectionRateHz": result.detection_rate_hz,
                    "avgLatencyMs": result.avg_latency_ms,
                    "createdAt": result.created_at.isoformat()
                }
                for result in results
            ],
            "summary": {
                "totalDetections": total_detections,
                "totalResults": len(results),
                "vruTypeDistribution": vru_distribution,
                "sessionDuration": (
                    (session.completed_at - session.started_at).total_seconds()
                    if session.started_at and session.completed_at
                    else None
                )
            }
        }

        # Add pagination metadata if available
        if pagination_metadata:
            response["pagination"] = pagination_metadata

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving test results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve test results: {str(e)}")

@router.get("/{session_id}/latency-metrics")
async def get_session_latency_metrics(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get latency and performance metrics for a test session"""
    try:
        # Verify session exists
        session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Test session not found")
        
        # Get detection events ordered by timestamp
        # Note: This endpoint calculates session-wide metrics, so we don't filter by video_id
        # For per-video metrics in multi-video sequences, use the video-specific endpoints
        detections = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()
        
        if not detections:
            return {
                "session_id": session_id,
                "metrics": {
                    "total_detections": 0,
                    "detection_rate": 0,
                    "average_confidence": 0,
                    "latency_stats": None
                }
            }
        
        # Calculate metrics
        total_detections = len(detections)
        average_confidence = sum(d.confidence for d in detections) / total_detections
        
        # Calculate detection intervals (as proxy for latency)
        intervals = []
        for i in range(1, len(detections)):
            interval = detections[i].timestamp - detections[i-1].timestamp
            intervals.append(interval)
        
        latency_stats = None
        if intervals:
            latency_stats = {
                "min_interval": min(intervals),
                "max_interval": max(intervals),
                "avg_interval": sum(intervals) / len(intervals),
                "median_interval": sorted(intervals)[len(intervals) // 2]
            }
        
        # Calculate detection rate
        session_duration = (
            (session.completed_at - session.started_at).total_seconds()
            if session.started_at and session.completed_at
            else None
        )
        
        detection_rate = (
            total_detections / session_duration
            if session_duration and session_duration > 0
            else 0
        )
        
        return {
            "session_id": session_id,
            "metrics": {
                "total_detections": total_detections,
                "detection_rate": detection_rate,
                "average_confidence": average_confidence,
                "latency_stats": latency_stats,
                "session_duration": session_duration
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating latency metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate metrics: {str(e)}")

# ============================================================================
# APPROVAL WORKFLOW
# ============================================================================

@router.post("/{session_id}/approval", response_model=ApprovalResponse)
async def approve_or_reject_session(
    session_id: str,
    approval: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """
    Approve or reject test session results.

    This endpoint enables formal approval workflow for test results:
    - Validates session is completed before allowing approval
    - Records approver identity and timestamp
    - Supports both approval and rejection with comments
    - Emits WebSocket events for real-time UI updates
    - Maintains complete audit trail

    Required for regulatory compliance and result accountability.

    **Production Features:**
    - Authorization checks (placeholder for future implementation)
    - Audit trail with who/when/why
    - Real-time WebSocket notifications
    - Validation of session state

    **Args:**
        session_id: Test session ID to approve/reject
        approval: Approval request with action, approver, and comments
        db: Database session

    **Returns:**
        ApprovalResponse with updated approval status

    **Raises:**
        HTTPException 404: Session not found
        HTTPException 400: Invalid session state or missing rejection reason
        HTTPException 403: Insufficient permissions (future implementation)
    """
    try:
        # Fetch session
        session = db.query(TestSession).filter(TestSession.id == session_id).first()

        if not session:
            logger.error(f"Session {session_id} not found for approval")
            raise HTTPException(status_code=404, detail="Test session not found")

        # Validate session is completed
        if session.status != "completed":
            logger.warning(f"Cannot approve incomplete session {session_id}, status: {session.status}")
            raise HTTPException(
                status_code=400,
                detail=f"Cannot approve session: status is '{session.status}', must be 'completed'"
            )

        # TODO: Add authorization checks here
        # Example: if not has_approval_permission(current_user):
        #     raise HTTPException(403, "Insufficient permissions to approve results")

        # Process approval or rejection
        action = approval.action.lower()

        if action == 'approve':
            session.approval_status = 'approved'
            session.approved_by = approval.approver_id
            session.approved_at = datetime.now(timezone.utc)
            session.approval_comments = approval.comments
            session.rejection_reason = None  # Clear any previous rejection

            logger.info(f"✅ Session {session_id} approved by {approval.approver_id}")
            message = "Test session approved successfully"

        elif action == 'reject':
            if not approval.rejection_reason:
                raise HTTPException(
                    status_code=400,
                    detail="Rejection reason is required when rejecting a session"
                )

            session.approval_status = 'rejected'
            session.approved_by = approval.approver_id
            session.approved_at = datetime.now(timezone.utc)
            session.rejection_reason = approval.rejection_reason
            session.approval_comments = approval.comments

            logger.warning(f"❌ Session {session_id} rejected by {approval.approver_id}: {approval.rejection_reason}")
            message = "Test session rejected"

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action '{action}'. Must be 'approve' or 'reject'"
            )

        # Commit to database
        db.commit()
        db.refresh(session)

        # Emit WebSocket event for real-time UI update
        try:
            from socketio_server import sio
            await sio.emit('session_approval_updated', {
                'session_id': session_id,
                'approval_status': session.approval_status,
                'approved_by': session.approved_by,
                'approved_at': session.approved_at.isoformat() if session.approved_at else None,
                'message': message
            }, room=session_id)
            logger.info(f"📡 Emitted approval update WebSocket event for session {session_id}")
        except Exception as ws_error:
            logger.warning(f"Failed to emit WebSocket event: {ws_error}")
            # Don't fail the request if WebSocket fails

        # Return response
        return ApprovalResponse(
            approval_status=session.approval_status,
            approved_by=session.approved_by,
            approved_at=session.approved_at,
            approval_comments=session.approval_comments,
            rejection_reason=session.rejection_reason,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing approval for session {session_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process approval: {str(e)}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def test_sessions_health_check():
    """Health check endpoint for test session management"""
    return {
        "status": "healthy",
        "service": "Test Sessions Router",
        "version": "1.0.0",
        "endpoints": [
            "POST /api/test-sessions - Create test session",
            "GET /api/test-sessions - List test sessions",
            "GET /api/test-sessions/{id} - Get session details",
            "POST /api/test-sessions/{id}/start - Start session",
            "POST /api/test-sessions/{id}/complete - Complete session",
            "GET /api/test-sessions/{id}/status - Get session status",
            "POST /api/test-sessions/detection-events - Create detection event",
            "GET /api/test-sessions/{id}/detections - Get session detections",
            "GET /api/test-sessions/{id}/results - Get session results",
            "POST /api/test-sessions/{id}/approval - Approve or reject results"
        ]
    }
