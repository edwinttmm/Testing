"""
Session Completion Service

Automatically handles session completion triggers and ensures proper lifecycle management.
Resolves the issue where sessions never transition to "completed" status.

CRITICAL FIX: Implements validation failure handling with explicit state tracking.
Sessions that fail validation are marked as VALIDATION_FAILED instead of remaining
in limbo, with comprehensive error details and retry capability.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database import SessionLocal
from models import TestSession, DetectionEvent, TestResult, VideoTestSequence, SequenceVideoResult
from services.test_execution_service import test_execution_service
from services.ground_truth_matching_service import get_ground_truth_matching_service

logger = logging.getLogger(__name__)

class ValidationFailedException(Exception):
    """
    Raised when session validation fails.

    This is a controlled exception that indicates validation rules were not met,
    not an unexpected system error. The session should be marked as VALIDATION_FAILED.
    """
    pass


def validate_video_sequence_completion(db: Session, session_id: str) -> tuple[bool, str]:
    """
    Validate that video sequence has proper timing data before completion.

    This prevents sessions from completing when video lifecycle events (start/end)
    never fired, which would leave NULL timestamps in the database.

    Args:
        db: Database session
        session_id: Test session ID to validate

    Returns:
        (is_valid, error_message) tuple:
            - is_valid: True if validation passed, False if failed
            - error_message: Empty string if valid, descriptive error if invalid

    Validation Rules:
        1. Non-sequence sessions always pass (no validation needed)
        2. Sequence sessions must have sequence_metadata with video_timing
        3. Each video in sequence must have:
           - started_at timestamp (not NULL)
           - ended_at timestamp (not NULL)
        4. Videos with status "pending" are not allowed at completion time
    """
    try:
        # Get session from database
        session = db.query(TestSession).filter(TestSession.id == session_id).first()

        if not session:
            return (False, f"Session {session_id} not found in database")

        # Check if this is a video sequence session
        if not session.has_video_sequence:
            logger.info(f"Session {session_id} is not a video sequence - validation passed")
            return (True, "")  # Not a sequence, no validation needed

        logger.info(f"Validating video sequence completion for session {session_id}")

        # Check sequence_metadata exists
        if not session.sequence_metadata:
            error_msg = (
                f"Video sequence session {session_id} missing sequence_metadata. "
                "This indicates video lifecycle events never fired."
            )
            logger.error(error_msg)
            return (False, error_msg)

        # Parse sequence_metadata (handle both dict and JSON string)
        metadata = session.sequence_metadata
        if isinstance(metadata, str):
            try:
                import json
                metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid sequence_metadata JSON for session {session_id}: {e}"
                logger.error(error_msg)
                return (False, error_msg)

        # Check video_timing exists in metadata
        if 'video_timing' not in metadata:
            error_msg = (
                f"Video sequence session {session_id} missing video_timing in sequence_metadata. "
                "Frontend video lifecycle events (onPlay, onEnded) did not fire properly."
            )
            logger.error(error_msg)
            return (False, error_msg)

        video_timing = metadata['video_timing']

        # Validate video_timing is not empty
        if not video_timing:
            error_msg = (
                f"Video sequence session {session_id} has empty video_timing metadata. "
                "No videos were started during this session."
            )
            logger.error(error_msg)
            return (False, error_msg)

        # Validate each video has start and end times
        missing_start_times = []
        missing_end_times = []

        for video_id, timing in video_timing.items():
            # Check for started_at timestamp
            started_at = timing.get('started_at') or timing.get('start_time')
            if started_at is None:
                missing_start_times.append(video_id)
                logger.error(f"Video {video_id} missing start time in video_timing")

            # Check for ended_at timestamp
            ended_at = timing.get('ended_at') or timing.get('end_time')
            if ended_at is None:
                missing_end_times.append(video_id)
                logger.error(f"Video {video_id} missing end time in video_timing")

        # Report missing start times
        if missing_start_times:
            error_msg = (
                f"Video sequence validation failed for session {session_id}: "
                f"{len(missing_start_times)} video(s) missing start time: {', '.join(missing_start_times)}. "
                "Frontend video onPlay event did not fire or timing was not captured."
            )
            logger.error(error_msg)
            return (False, error_msg)

        # Report missing end times
        if missing_end_times:
            error_msg = (
                f"Video sequence validation failed for session {session_id}: "
                f"{len(missing_end_times)} video(s) missing end time: {', '.join(missing_end_times)}. "
                "Frontend video onEnded event did not fire or timing was not captured."
            )
            logger.error(error_msg)
            return (False, error_msg)

        # Additional validation: Check SequenceVideoResult records
        video_sequence = db.query(VideoTestSequence).filter(
            VideoTestSequence.test_session_id == str(session_id)
        ).first()

        if video_sequence:
            # Check for videos still in "pending" status
            pending_videos = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == video_sequence.id,
                SequenceVideoResult.video_status == "pending"
            ).all()

            if pending_videos:
                pending_ids = [v.video_id for v in pending_videos]
                error_msg = (
                    f"Video sequence validation failed for session {session_id}: "
                    f"{len(pending_ids)} video(s) still in 'pending' status: {', '.join(pending_ids)}. "
                    "Videos were never started or lifecycle events did not complete."
                )
                logger.error(error_msg)
                return (False, error_msg)

            logger.info(
                f"Session {session_id} video sequence validation passed: "
                f"{len(video_timing)} videos with complete timing data"
            )

        # All validations passed
        return (True, "")

    except Exception as e:
        error_msg = f"Unexpected error validating video sequence for session {session_id}: {e}"
        logger.error(error_msg, exc_info=True)
        return (False, error_msg)

class SessionCompletionService:
    """Handles automatic session completion and lifecycle management"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.completion_tasks: Dict[str, asyncio.Task] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def start_session_monitoring(self, session_id: str, estimated_duration_seconds: int = 60) -> bool:
        """
        Start monitoring a session for automatic completion.
        
        Args:
            session_id: The session to monitor
            estimated_duration_seconds: How long to wait before auto-completion
            
        Returns:
            bool: True if monitoring started successfully
        """
        try:
            # Store session monitoring info
            self.active_sessions[session_id] = {
                'start_time': datetime.now(timezone.utc),
                'estimated_duration': estimated_duration_seconds,
                'status': 'monitoring'
            }
            
            # Start auto-completion task
            completion_task = asyncio.create_task(
                self._monitor_session_completion(session_id, estimated_duration_seconds)
            )
            self.completion_tasks[session_id] = completion_task
            
            # Update session status to running
            await self._update_session_status(session_id, "running")
            
            self.logger.info(f"Started monitoring session {session_id} for {estimated_duration_seconds}s")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start session monitoring for {session_id}: {e}")
            return False
    
    async def complete_session(self, session_id: str, force: bool = False) -> bool:
        """
        Complete a session and generate results.

        Args:
            session_id: The session to complete
            force: Force completion even if already completed

        Returns:
            bool: True if session completed successfully
        """
        try:
            db = SessionLocal()
            try:
                # Get session
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if not session:
                    self.logger.error(f"Session {session_id} not found")
                    return False

                # Check if already completed
                if session.status == "completed" and not force:
                    self.logger.info(f"Session {session_id} already completed")
                    return True

                # CRITICAL VALIDATION: Check video sequence timing data before completion
                is_valid, error_message = validate_video_sequence_completion(db, session_id)

                if not is_valid:
                    self.logger.error(
                        f"Session completion validation failed for {session_id}: {error_message}"
                    )

                    # CRITICAL FIX: Mark session as failed with comprehensive details
                    session.status = "validation_failed"
                    session.failure_reason = error_message
                    session.failed_at = datetime.now(timezone.utc)

                    # Store structured failure details for debugging and recovery
                    session.failure_details = {
                        'validation_type': 'video_sequence_completion',
                        'error_message': error_message,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'session_type': 'multi_video' if session.has_video_sequence else 'single_video',
                        'recoverable': True  # Can be retried after fixing video lifecycle issues
                    }

                    session.updated_at = datetime.now(timezone.utc)
                    db.commit()

                    # Emit WebSocket event to notify frontend of failure
                    try:
                        # Import socketio only when needed to avoid circular imports
                        from socketio_server import sio
                        asyncio.create_task(
                            sio.emit('session_failed', {
                                'session_id': session_id,
                                'status': 'validation_failed',
                                'reason': error_message,
                                'details': session.failure_details,
                                'recoverable': True
                            })
                        )
                    except Exception as ws_error:
                        self.logger.warning(f"Could not emit session_failed WebSocket event: {ws_error}")

                    # Raise controlled exception (not generic ValueError)
                    raise ValidationFailedException(error_message)

                self.logger.info(f"Session {session_id} passed video sequence validation")
                
                # Before marking completed, ensure LabJack monitoring is stopped
                try:
                    # Lazy import to avoid circulars
                    from services.labjack_monitor_manager import stop_labjack_monitoring
                    await stop_labjack_monitoring()
                    self.logger.info(f"Stopped LabJack monitoring for session {session_id}")
                except Exception as e:
                    self.logger.warning(f"Could not stop LabJack monitoring: {e}")

                # CRITICAL FIX: Reassign NULL video_ids before marking session complete
                # This fixes race condition where detections arrive before video lifecycle events
                try:
                    from services.detection_video_reassignment import reassign_null_video_ids

                    self.logger.info(f"Running video_id reassignment for session {session_id}")
                    reassignment_result = await reassign_null_video_ids(session_id, dry_run=False)

                    if reassignment_result["success"]:
                        reassigned_count = reassignment_result.get("reassigned_count", 0)
                        corrected_count = reassignment_result.get("corrected_existing", 0)

                        if reassigned_count > 0 or corrected_count > 0:
                            self.logger.info(
                                f"✅ Video ID reassignment complete for session {session_id}: "
                                f"reassigned {reassigned_count} NULL detections, "
                                f"corrected {corrected_count} existing assignments"
                            )
                        else:
                            self.logger.info(f"Video ID reassignment: no changes needed for session {session_id}")
                    else:
                        error_msg = reassignment_result.get("error", "Unknown error")
                        self.logger.warning(f"Video ID reassignment failed for session {session_id}: {error_msg}")

                except Exception as e:
                    self.logger.error(f"Failed to run video_id reassignment for session {session_id}: {e}", exc_info=True)
                    # Don't fail session completion due to reassignment errors
                    # The reassignment can be run manually as a backfill operation

                # Update session to completed
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)
                
                # Check detection event count (but DO NOT create mock events)
                detection_count = db.query(DetectionEvent).filter(
                    DetectionEvent.test_session_id == session_id
                ).count()

                if detection_count == 0:
                    self.logger.warning(f"⚠️ No detection events found for session {session_id} - this is expected if hardware was not connected or no detections occurred")
                
                db.commit()
                
                # Generate results using test execution service
                self.logger.info(f"Generating results for completed session {session_id}")
                result_data = test_execution_service.get_session_results(session_id)

                if result_data:
                    self.logger.info(f"Results generated for session {session_id}: {result_data.get('total_detections', 0)} detections")
                else:
                    self.logger.warning(f"Failed to generate results for session {session_id}")

                # Trigger ground truth matching for validation
                try:
                    matching_service = get_ground_truth_matching_service()
                    self.logger.info(f"Starting ground truth matching for session {session_id}")
                    matching_results = matching_service.match_detections_to_ground_truth(session_id)

                    if matching_results:
                        matched_count = matching_results.get('matched_count', 0)
                        unmatched_count = matching_results.get('unmatched_count', 0)
                        self.logger.info(
                            f"Ground truth matching completed for session {session_id}: "
                            f"{matched_count} matched, {unmatched_count} unmatched"
                        )
                    else:
                        self.logger.warning(f"Ground truth matching returned no results for session {session_id}")
                except Exception as e:
                    # Don't fail session completion if matching fails
                    self.logger.error(
                        f"Ground truth matching failed for session {session_id}: {e}",
                        exc_info=True
                    )
                    # Continue with session completion even if matching fails

                # AGENT #32: Calculate per-video metrics for multi-video sessions
                try:
                    from services.sequence_video_metrics_aggregator import aggregate_video_metrics

                    # Check if this is a multi-video session
                    if session.has_video_sequence:
                        self.logger.info(
                            f"Session {session_id} is multi-video - calculating per-video metrics"
                        )

                        # Get all videos in this sequence
                        video_sequence = db.query(VideoTestSequence).filter(
                            VideoTestSequence.test_session_id == session_id
                        ).first()

                        if video_sequence and video_sequence.video_ids:
                            completed_video_ids = video_sequence.video_ids
                            self.logger.info(
                                f"Found {len(completed_video_ids)} videos to aggregate metrics for"
                            )

                            # Calculate metrics for each video
                            for video_id in completed_video_ids:
                                try:
                                    metrics = await aggregate_video_metrics(db, session_id, video_id)

                                    self.logger.info(
                                        f"✅ Aggregated metrics for video {video_id}: "
                                        f"TP={metrics['tp']}, FP={metrics['fp']}, FN={metrics['fn']}, "
                                        f"F1={metrics['f1']:.3f}, Avg Latency={metrics['avg_latency_ms']:.2f}ms"
                                    )
                                except Exception as video_error:
                                    self.logger.error(
                                        f"Failed to aggregate metrics for video {video_id}: {video_error}",
                                        exc_info=True
                                    )
                                    # Continue with other videos

                            self.logger.info(
                                f"✅ Completed per-video metrics aggregation for session {session_id}"
                            )
                        else:
                            self.logger.warning(
                                f"No video sequence or video_ids found for session {session_id}"
                            )
                    else:
                        self.logger.info(
                            f"Session {session_id} is single-video - skipping per-video aggregation"
                        )

                except Exception as e:
                    # Don't fail session completion if aggregation fails
                    self.logger.error(
                        f"Per-video metrics aggregation failed for session {session_id}: {e}",
                        exc_info=True
                    )
                    # Continue with session completion even if aggregation fails

                # Clean up monitoring
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]
                if session_id in self.completion_tasks:
                    task = self.completion_tasks[session_id]
                    if not task.done():
                        task.cancel()
                    del self.completion_tasks[session_id]
                
                self.logger.info(f"Successfully completed session {session_id}")

                # Optional: trigger TS compute-results if configured
                try:
                    import os, requests
                    ts_url = os.getenv('TS_INGEST_URL') or os.getenv('TS_INGEST_ENDPOINT')
                    service_token = os.getenv('SERVICE_TOKEN')
                    tol = int(os.getenv('TS_COMPUTE_TOLERANCE_MS', '100'))
                    thr = int(os.getenv('TS_COMPUTE_THRESHOLD_MS', '100'))
                    if ts_url and service_token:
                        endpoint = f"{ts_url.rstrip('/')}/labjack/compute-results/{session_id}"
                        headers = {"X-Service-Token": service_token, "Content-Type": "application/json"}
                        payload = {"toleranceMs": tol, "maxLatencyMs": thr}
                        try:
                            requests.post(endpoint, json=payload, headers=headers, timeout=2.0)
                            self.logger.info(f"Triggered TS compute-results for session {session_id} (tol={tol}ms, thr={thr}ms)")
                        except Exception as e:
                            self.logger.warning(f"Failed to trigger TS compute-results: {e}")
                except Exception:
                    pass
                return True

            finally:
                db.close()

        except ValidationFailedException as e:
            # Already handled - session marked as failed with details
            self.logger.warning(f"Session {session_id} validation failed: {e}")
            return False

        except Exception as e:
            # Unexpected error - mark as ERROR state
            self.logger.exception(f"Session {session_id} completion error: {e}")

            try:
                db = SessionLocal()
                try:
                    session = db.query(TestSession).filter(TestSession.id == session_id).first()
                    if session:
                        session.status = "error"
                        session.failure_reason = f"Completion error: {str(e)}"
                        session.failed_at = datetime.now(timezone.utc)
                        session.failure_details = {
                            'error_type': 'unexpected_error',
                            'error_message': str(e),
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'recoverable': False  # Unexpected errors may not be recoverable
                        }
                        db.commit()

                        # Emit WebSocket error event
                        try:
                            from socketio_server import sio
                            asyncio.create_task(
                                sio.emit('session_failed', {
                                    'session_id': session_id,
                                    'status': 'error',
                                    'reason': 'internal_error',
                                    'message': str(e),
                                    'recoverable': False
                                })
                            )
                        except Exception as ws_error:
                            self.logger.warning(f"Could not emit error WebSocket event: {ws_error}")
                finally:
                    db.close()
            except Exception as db_error:
                self.logger.error(f"Could not update session error state: {db_error}")

            return False
    
    async def _monitor_session_completion(self, session_id: str, duration_seconds: int):
        """
        Monitor a session and auto-complete it after the specified duration.
        """
        try:
            # Wait for the estimated duration
            await asyncio.sleep(duration_seconds)
            
            # Complete the session
            success = await self.complete_session(session_id)
            
            if success:
                self.logger.info(f"Auto-completed session {session_id} after {duration_seconds}s")
            else:
                self.logger.error(f"Failed to auto-complete session {session_id}")
                
        except asyncio.CancelledError:
            self.logger.info(f"Session monitoring cancelled for {session_id}")
        except Exception as e:
            self.logger.error(f"Error in session monitoring for {session_id}: {e}")
    
    async def _update_session_status(self, session_id: str, status: str):
        """Update session status in database"""
        try:
            db = SessionLocal()
            try:
                session = db.query(TestSession).filter(TestSession.id == session_id).first()
                if session:
                    session.status = status
                    if status == "running" and not session.started_at:
                        session.started_at = datetime.now(timezone.utc)
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"Failed to update session status: {e}")
    
    # REMOVED: Mock detection event generation
    # This method was creating fake hardware detection events which masked real issues
    # Real detection events should come from actual LabJack hardware monitoring
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get monitoring status for a session"""
        if session_id in self.active_sessions:
            session_info = self.active_sessions[session_id].copy()
            session_info['elapsed_seconds'] = (
                datetime.now(timezone.utc) - session_info['start_time']
            ).total_seconds()
            return session_info
        return None
    
    async def stop_session_monitoring(self, session_id: str):
        """Stop monitoring a session without completing it"""
        if session_id in self.completion_tasks:
            task = self.completion_tasks[session_id]
            if not task.done():
                task.cancel()
            del self.completion_tasks[session_id]
        
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        self.logger.info(f"Stopped monitoring session {session_id}")

# Global service instance
session_completion_service = SessionCompletionService()

# Convenience functions
async def start_session_monitoring(session_id: str, duration_seconds: int = 60) -> bool:
    """Start monitoring a session for auto-completion"""
    return await session_completion_service.start_session_monitoring(session_id, duration_seconds)

async def complete_session(session_id: str, force: bool = False) -> bool:
    """Complete a session and generate results"""
    return await session_completion_service.complete_session(session_id, force)

def get_session_monitoring_status(session_id: str) -> Optional[Dict[str, Any]]:
    """Get monitoring status for a session"""
    return session_completion_service.get_session_status(session_id)
