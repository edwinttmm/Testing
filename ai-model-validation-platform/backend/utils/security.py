"""Security utilities for session management"""
from sqlalchemy.orm import Session
from typing import Optional
from models import TestSession, VideoTestSequence
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

class SecurityError(Exception):
    """Raised when security check fails"""
    pass

def verify_session_ownership(
    session_id: str,
    project_id: str,
    db: Session,
    user_id: Optional[str] = None
) -> TestSession:
    """
    Verify that session belongs to the specified project.

    This function prevents unauthorized access by ensuring sessions
    can only be accessed by their owning project.

    Args:
        session_id: Session to verify
        project_id: Project ID from request
        db: Database session
        user_id: Current user ID (if authenticated)

    Returns:
        TestSession if authorized

    Raises:
        HTTPException(404): If session not found
        HTTPException(403): If unauthorized access attempt
    """
    # Use indexed lookup for performance
    session = db.query(TestSession).filter(
        TestSession.id == session_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )

    # Verify project ownership
    if session.project_id != project_id:
        logger.warning(
            f"Security: Unauthorized access attempt - session {session_id} "
            f"belongs to project {session.project_id}, not {project_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Session {session_id} belongs to a different project"
        )

    # TODO: Add user ownership check when auth is implemented
    # if user_id and session.created_by_user_id != user_id:
    #     logger.warning(
    #         f"Security: Unauthorized access attempt - user {user_id} "
    #         f"accessing session owned by {session.created_by_user_id}"
    #     )
    #     raise SecurityError("Unauthorized access to session")

    return session

def verify_sequence_ownership(
    sequence_id: str,
    project_id: str,
    db: Session,
    user_id: Optional[str] = None
) -> VideoTestSequence:
    """
    Verify that sequence belongs to the specified project.

    This function prevents unauthorized access by ensuring sequences
    can only be accessed by their owning project (via session).

    Args:
        sequence_id: Sequence to verify
        project_id: Project ID from request
        db: Database session
        user_id: Current user ID (if authenticated)

    Returns:
        VideoTestSequence if authorized

    Raises:
        HTTPException(404): If sequence not found
        HTTPException(403): If unauthorized access attempt
    """
    sequence = db.query(VideoTestSequence).filter(
        VideoTestSequence.id == sequence_id
    ).first()

    if not sequence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sequence {sequence_id} not found"
        )

    # Verify project ownership via associated session
    if sequence.session_id:
        session = db.query(TestSession).filter(
            TestSession.id == sequence.session_id
        ).first()

        if session and session.project_id != project_id:
            logger.warning(
                f"Security: Unauthorized access attempt - sequence {sequence_id} "
                f"belongs to project {session.project_id}, not {project_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sequence {sequence_id} belongs to a different project"
            )

    # TODO: Add user ownership check when auth is implemented
    # if user_id and sequence.created_by_user_id != user_id:
    #     logger.warning(
    #         f"Security: Unauthorized access attempt - user {user_id} "
    #         f"accessing sequence owned by {sequence.created_by_user_id}"
    #     )
    #     raise SecurityError("Unauthorized access to sequence")

    return sequence
