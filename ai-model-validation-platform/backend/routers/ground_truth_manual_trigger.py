"""
Ground Truth Manual Trigger Router
Provides manual backfill endpoint for triggering ground truth matching on existing sessions
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from database import get_db
from services.ground_truth_matching_service import get_ground_truth_matching_service
from models import TestSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test-sessions", tags=["ground-truth-backfill"])


@router.post("/{session_id}/match-ground-truth")
async def trigger_ground_truth_matching(
    session_id: str,
    db: Session = Depends(get_db),
    force_rematch: bool = False
) -> Dict[str, Any]:
    """
    Manually trigger ground truth matching for a session (backfill endpoint)

    This endpoint allows retroactive ground truth matching for test sessions that completed
    before automatic matching was implemented. It's useful for:
    - Backfilling historical sessions with ground truth analysis
    - Re-running matching with updated algorithms
    - Debugging and validating matching logic

    Args:
        session_id: The test session ID to process
        force_rematch: If True, clear existing matches and recompute (default: False)

    Returns:
        Dictionary containing:
        - success: Boolean indicating operation success
        - session_id: The session ID that was processed
        - results: Matching results with TP/FP/FN counts and metrics
        - message: Human-readable status message

    Raises:
        HTTPException 404: Session not found
        HTTPException 500: Matching failed

    Example Response:
        {
            "success": true,
            "session_id": "abc123",
            "results": {
                "true_positives": 45,
                "false_positives": 2,
                "false_negatives": 3,
                "precision": 0.957,
                "recall": 0.938,
                "f1_score": 0.947,
                "mean_latency_ms": 23.4,
                "total_ground_truth": 48,
                "total_detections": 47,
                "matched_detections": 45
            },
            "message": "Ground truth matching completed successfully"
        }
    """
    try:
        logger.info(f"🎯 Manual ground truth matching triggered for session {session_id} (force_rematch={force_rematch})")

        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            logger.warning(f"❌ Session not found: {session_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Test session {session_id} not found"
            )

        # Get ground truth matching service
        matching_service = get_ground_truth_matching_service()

        # Perform matching
        logger.info(f"🔄 Running ground truth matching for session {session_id}...")
        metrics = matching_service.match_detections_to_ground_truth(
            session_id=session_id,
            force_rematch=force_rematch
        )

        if metrics is None:
            logger.error(f"❌ Ground truth matching failed for session {session_id}")
            raise HTTPException(
                status_code=500,
                detail="Ground truth matching failed - check logs for details"
            )

        # Build response with detailed results
        results = {
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,
            "precision": round(metrics.precision, 3),
            "recall": round(metrics.recall, 3),
            "f1_score": round(metrics.f1_score, 3),
            "accuracy": round(metrics.accuracy, 3),
            "mean_latency_ms": round(metrics.mean_latency_ms, 2),
            "std_latency_ms": round(metrics.std_latency_ms, 2),
            "max_latency_ms": round(metrics.max_latency_ms, 2),
            "min_latency_ms": round(metrics.min_latency_ms, 2),
            "within_tolerance_percentage": round(metrics.within_tolerance_percentage, 1),
            "total_ground_truth": metrics.total_ground_truth,
            "total_detections": metrics.total_detections,
            "matched_detections": metrics.matched_detections
        }

        # Generate status message
        message = (
            f"Ground truth matching completed: "
            f"{metrics.matched_detections}/{metrics.total_ground_truth} matched "
            f"(Precision: {metrics.precision:.1%}, Recall: {metrics.recall:.1%})"
        )

        logger.info(f"✅ {message}")

        return {
            "success": True,
            "session_id": session_id,
            "results": results,
            "message": message,
            "rematch_performed": force_rematch
        }

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"❌ Manual GT matching failed for {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Ground truth matching error: {str(e)}"
        )


@router.get("/{session_id}/ground-truth-status")
async def get_ground_truth_status(
    session_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Check if ground truth matching has been performed for a session

    This endpoint allows checking whether a session has ground truth matching results
    without triggering a new matching operation.

    Args:
        session_id: The test session ID to check

    Returns:
        Dictionary containing:
        - session_id: The session ID
        - has_ground_truth_matching: Boolean indicating if matching exists
        - comparison_count: Number of detection comparisons stored
        - session_status: Current session status

    Example Response:
        {
            "session_id": "abc123",
            "has_ground_truth_matching": true,
            "comparison_count": 50,
            "session_status": "completed"
        }
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if not test_session:
            raise HTTPException(
                status_code=404,
                detail=f"Test session {session_id} not found"
            )

        # Check for existing comparisons
        from models import DetectionComparison
        from sqlalchemy import func

        comparison_count = db.query(func.count(DetectionComparison.id)).filter(
            DetectionComparison.test_session_id == session_id
        ).scalar() or 0

        has_matching = comparison_count > 0

        return {
            "session_id": session_id,
            "has_ground_truth_matching": has_matching,
            "comparison_count": comparison_count,
            "session_status": test_session.status,
            "session_created_at": test_session.created_at.isoformat() if test_session.created_at else None,
            "session_completed_at": test_session.completed_at.isoformat() if test_session.completed_at else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking GT status for {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error checking ground truth status: {str(e)}"
        )
