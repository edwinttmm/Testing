"""
Video State Machine for Independent State Management

This service manages video states independently of frontend,
providing robust state transitions with validation and recovery.

Key Features:
- State machine for video lifecycle
- Backend-driven state transitions
- Validation of state changes
- Error recovery mechanisms
- Comprehensive state history

Production Standards:
- No frontend dependency
- Thread-safe operations
- Transaction safety
- Complete audit trail
"""

import logging
import time
import threading
from typing import Dict, Optional, List, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class VideoState(str, Enum):
    """Video lifecycle states"""
    PENDING = "pending"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class StateTransition:
    """Records a state transition"""
    from_state: VideoState
    to_state: VideoState
    timestamp: float
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoStateInfo:
    """Complete state information for a video"""
    session_id: str
    video_id: str
    current_state: VideoState
    created_at: float
    updated_at: float

    # State history
    state_history: List[StateTransition] = field(default_factory=list)

    # Timing information
    loading_started_at: Optional[float] = None
    playback_started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_occurred_at: Optional[float] = None

    # Error information
    error_message: Optional[str] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class VideoStateMachine:
    """
    Manages video states independently of frontend.
    Transitions: PENDING → LOADING → PLAYING → COMPLETED → ERROR

    Provides autonomous state management with validation,
    error recovery, and comprehensive audit trail.
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        VideoState.PENDING: [VideoState.LOADING, VideoState.ERROR],
        VideoState.LOADING: [VideoState.PLAYING, VideoState.ERROR, VideoState.TIMEOUT],
        VideoState.PLAYING: [VideoState.PAUSED, VideoState.COMPLETED, VideoState.ERROR, VideoState.TIMEOUT],
        VideoState.PAUSED: [VideoState.PLAYING, VideoState.COMPLETED, VideoState.ERROR],
        VideoState.COMPLETED: [],  # Terminal state
        VideoState.ERROR: [],      # Terminal state
        VideoState.TIMEOUT: []     # Terminal state
    }

    def __init__(self):
        """Initialize video state machine"""
        self._video_states: Dict[Tuple[str, str], VideoStateInfo] = {}
        self._lock = threading.RLock()

        # Statistics
        self._total_transitions = 0
        self._invalid_transitions_blocked = 0

        logger.info("VideoStateMachine initialized")

    def initialize_video(
        self,
        session_id: str,
        video_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Initialize video state tracking.

        Args:
            session_id: Test session identifier
            video_id: Video identifier
            metadata: Optional metadata about video

        Returns:
            True if initialized successfully
        """
        try:
            with self._lock:
                state_key = (session_id, video_id)

                if state_key in self._video_states:
                    logger.warning(
                        f"Video already initialized - "
                        f"Session: {session_id}, Video: {video_id}"
                    )
                    return False

                current_time = time.time()

                state_info = VideoStateInfo(
                    session_id=session_id,
                    video_id=video_id,
                    current_state=VideoState.PENDING,
                    created_at=current_time,
                    updated_at=current_time,
                    metadata=metadata or {}
                )

                self._video_states[state_key] = state_info

                logger.info(
                    f"Initialized video state - "
                    f"Session: {session_id}, Video: {video_id}, "
                    f"State: PENDING"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to initialize video state: {e}")
            return False

    def transition_state(
        self,
        session_id: str,
        video_id: str,
        new_state: VideoState,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db_session: Optional[Session] = None
    ) -> bool:
        """
        Transition video to new state with validation.

        Args:
            session_id: Test session identifier
            video_id: Video identifier
            new_state: Target state
            reason: Reason for transition
            metadata: Optional metadata about transition
            db_session: Optional database session for persistence

        Returns:
            True if transition successful
        """
        try:
            with self._lock:
                state_key = (session_id, video_id)

                # Get current state
                if state_key not in self._video_states:
                    logger.error(
                        f"Cannot transition - video not initialized: {state_key}"
                    )
                    return False

                state_info = self._video_states[state_key]
                current_state = state_info.current_state

                # Validate transition
                if not self._is_valid_transition(current_state, new_state):
                    self._invalid_transitions_blocked += 1
                    logger.error(
                        f"Invalid state transition blocked - "
                        f"Session: {session_id}, Video: {video_id}, "
                        f"From: {current_state.value}, To: {new_state.value}"
                    )
                    return False

                # Record transition
                current_time = time.time()

                transition = StateTransition(
                    from_state=current_state,
                    to_state=new_state,
                    timestamp=current_time,
                    reason=reason,
                    metadata=metadata or {}
                )

                state_info.state_history.append(transition)
                state_info.current_state = new_state
                state_info.updated_at = current_time

                # Update timing fields
                if new_state == VideoState.LOADING:
                    state_info.loading_started_at = current_time
                elif new_state == VideoState.PLAYING:
                    state_info.playback_started_at = current_time
                elif new_state == VideoState.COMPLETED:
                    state_info.completed_at = current_time
                elif new_state == VideoState.ERROR or new_state == VideoState.TIMEOUT:
                    state_info.error_occurred_at = current_time
                    if reason:
                        state_info.error_message = reason

                self._total_transitions += 1

                logger.info(
                    f"State transition - "
                    f"Session: {session_id}, Video: {video_id}, "
                    f"{current_state.value} → {new_state.value}, "
                    f"Reason: {reason or 'None'}"
                )

                # Persist to database if provided
                if db_session:
                    self._persist_state(session_id, video_id, state_info, db_session)

                return True

        except Exception as e:
            logger.error(f"Failed to transition state: {e}")
            return False

    def get_state(self, session_id: str, video_id: str) -> Optional[VideoState]:
        """
        Get current state for a video.

        Args:
            session_id: Test session identifier
            video_id: Video identifier

        Returns:
            Current video state, or None if not tracked
        """
        with self._lock:
            state_key = (session_id, video_id)
            state_info = self._video_states.get(state_key)
            return state_info.current_state if state_info else None

    def get_state_info(
        self,
        session_id: str,
        video_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get complete state information for a video.

        Args:
            session_id: Test session identifier
            video_id: Video identifier

        Returns:
            Dictionary with complete state information
        """
        with self._lock:
            state_key = (session_id, video_id)
            state_info = self._video_states.get(state_key)

            if not state_info:
                return None

            return {
                'session_id': session_id,
                'video_id': video_id,
                'current_state': state_info.current_state.value,
                'created_at': state_info.created_at,
                'updated_at': state_info.updated_at,
                'loading_started_at': state_info.loading_started_at,
                'playback_started_at': state_info.playback_started_at,
                'completed_at': state_info.completed_at,
                'error_occurred_at': state_info.error_occurred_at,
                'error_message': state_info.error_message,
                'transition_count': len(state_info.state_history),
                'state_history': [
                    {
                        'from': t.from_state.value,
                        'to': t.to_state.value,
                        'timestamp': t.timestamp,
                        'reason': t.reason,
                        'metadata': t.metadata
                    }
                    for t in state_info.state_history
                ],
                'metadata': state_info.metadata
            }

    def is_terminal_state(self, session_id: str, video_id: str) -> bool:
        """Check if video is in a terminal state"""
        state = self.get_state(session_id, video_id)
        return state in [VideoState.COMPLETED, VideoState.ERROR, VideoState.TIMEOUT]

    def cleanup_video(self, session_id: str, video_id: str) -> bool:
        """Remove state tracking for a video"""
        try:
            with self._lock:
                state_key = (session_id, video_id)

                if state_key in self._video_states:
                    del self._video_states[state_key]
                    logger.info(f"Cleaned up video state: {state_key}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to cleanup video state: {e}")
            return False

    def _is_valid_transition(
        self,
        from_state: VideoState,
        to_state: VideoState
    ) -> bool:
        """Validate if state transition is allowed"""
        if from_state == to_state:
            # Allow same-state transitions (idempotent)
            return True

        valid_targets = self.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_targets

    def _persist_state(
        self,
        session_id: str,
        video_id: str,
        state_info: VideoStateInfo,
        db_session: Session
    ):
        """Persist state to database"""
        try:
            from models import SequenceVideoResult

            # Find the video result record
            video_result = db_session.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_id == video_id
            ).first()

            if video_result:
                # Update status field
                video_result.status = state_info.current_state.value

                # Update timing fields
                if state_info.playback_started_at:
                    video_result.started_at = datetime.fromtimestamp(
                        state_info.playback_started_at,
                        tz=timezone.utc
                    )

                if state_info.completed_at:
                    video_result.ended_at = datetime.fromtimestamp(
                        state_info.completed_at,
                        tz=timezone.utc
                    )

                db_session.commit()

                logger.debug(f"Persisted state to database for video {video_id}")
            else:
                logger.warning(f"SequenceVideoResult not found for video {video_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error persisting state: {e}")
            db_session.rollback()
        except Exception as e:
            logger.error(f"Error persisting state: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get state machine statistics"""
        with self._lock:
            state_counts = {}
            for state_info in self._video_states.values():
                state = state_info.current_state.value
                state_counts[state] = state_counts.get(state, 0) + 1

            return {
                'total_videos_tracked': len(self._video_states),
                'total_transitions': self._total_transitions,
                'invalid_transitions_blocked': self._invalid_transitions_blocked,
                'state_distribution': state_counts
            }


# Global singleton instance
_video_state_machine = None
_state_machine_lock = threading.Lock()


def get_video_state_machine() -> VideoStateMachine:
    """Get global video state machine instance (thread-safe singleton)"""
    global _video_state_machine

    if _video_state_machine is None:
        with _state_machine_lock:
            if _video_state_machine is None:
                _video_state_machine = VideoStateMachine()

    return _video_state_machine
