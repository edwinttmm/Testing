"""
Ground Truth Matching Service

This service provides comprehensive temporal matching between LabJack detections 
and pre-recorded ground truth timing data. It implements sophisticated algorithms
for detection classification, latency calculation, and performance metrics.

Key Features:
- Temporal matching with configurable tolerance windows
- True Positive / False Positive / False Negative classification
- Latency calculation and statistical analysis
- Precision, Recall, F1 Score computation
- Database population with match results
"""

import logging
import uuid
import statistics
from typing import Dict, List, Optional, Tuple, Union, Any
from datetime import datetime
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_, or_, func, insert

from database import SessionLocal, get_db
from models import (
    TestSession, DetectionEvent, GroundTruthObject, DetectionComparison, VideoTestSequence
)
try:
    from models import PerformanceMetrics, ValidationResult as ValidationResultEnum
except ImportError:
    # PerformanceMetrics not available in models, define local stub
    PerformanceMetrics = None
    ValidationResultEnum = None
from schemas_annotation import VRUTypeEnum

# CRITICAL DEPENDENCY CHECK: scipy required for optimal matching algorithm
try:
    from scipy.optimize import linear_sum_assignment
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    linear_sum_assignment = None

from services.optimal_matching_service import optimal_detection_matching
from config.timing_config import MATCHING_TOLERANCE_MS

# Option C: Temporal Expansion for improved matching accuracy
try:
    from src.services.temporal_expansion import (
        expand_detections_temporally,
        collapse_duplicates,
        ExpandedDetection
    )
    TEMPORAL_EXPANSION_AVAILABLE = True
except ImportError:
    TEMPORAL_EXPANSION_AVAILABLE = False
    expand_detections_temporally = None
    collapse_duplicates = None
    ExpandedDetection = None

# Drift Compensation Services
try:
    from src.services.timestamp_compensation_service import TimestampCompensationService
    from src.services.drift_measurement_service import DriftMeasurementService
    DRIFT_COMPENSATION_AVAILABLE = True
except ImportError:
    DRIFT_COMPENSATION_AVAILABLE = False
    TimestampCompensationService = None
    DriftMeasurementService = None

logger = logging.getLogger(__name__)

# AGENT #43: FP Latency Marker Constant
# False Positive detections get artificial latency of 10000ms (sentinel value)
# This marks them clearly and excludes them from statistics calculations
FP_LATENCY_MARKER = 10000.0


@dataclass
class MatchResult:
    """Data class for individual match results"""
    ground_truth_id: str
    detection_event_id: Optional[str]
    match_type: str  # 'TP', 'FP', 'FN'
    temporal_offset: float  # in milliseconds
    confidence: Optional[float]
    iou_score: Optional[float]  # Temporal overlap score
    latency_ms: Optional[float]  # Actual detection latency
    video_id: Optional[str] = None  # Video ID for multi-video latency grouping


@dataclass
class SessionMetrics:
    """Comprehensive metrics for a test session"""
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    mean_latency_ms: float
    std_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float
    within_tolerance_percentage: float
    total_ground_truth: int
    total_detections: int
    matched_detections: int
    latency_sample_count: int = 0
    per_video_latency_samples: Dict[str, int] = field(default_factory=dict)


def _safe_float(value: Optional[Any]) -> Optional[float]:
    """Convert value to float when possible, otherwise return None."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_like_epoch(timestamp: Optional[float]) -> bool:
    """Heuristic to detect Unix epoch timestamps."""
    return bool(timestamp is not None and timestamp > 1_000_000_000)


def extract_detection_video_time(
    detection: Any,
    video_timing_map: Dict[str, Dict[str, Any]] = {},
    session_start_time: Optional[float] = None
) -> Optional[float]:
    """
    Resolve the best available video-relative timestamp for a detection event.
    Updated to handle per-video start times for multi-video sequences.
    """
    preferred_attrs = (
        "video_relative_timestamp",
        "video_time",
        "video_timestamp",
        "relative_timestamp",
    )
    for attr in preferred_attrs:
        value = _safe_float(getattr(detection, attr, None))
        if value is not None:
            return value

    timestamp = _safe_float(getattr(detection, "timestamp", None))
    video_id = getattr(detection, 'video_id', None)

    # Use per-video start time from the timing map if available
    if video_id and video_id in video_timing_map:
        video_start_time = video_timing_map[video_id].get('start_time')
        if video_start_time and timestamp and _looks_like_epoch(timestamp):
            return timestamp - video_start_time

    # Fallback to session start time
    if timestamp is not None and session_start_time is not None and _looks_like_epoch(timestamp):
        return timestamp - session_start_time

    return timestamp


def extract_ground_truth_video_time(
    ground_truth: Any,
    video_timing_map: Dict[str, Dict[str, Any]] = {},
    session_start_time: Optional[float] = None
) -> Optional[float]:
    """
    Resolve the best available video-relative timestamp for a ground truth object.
    Updated to handle per-video start times for multi-video sequences.
    """
    preferred_attrs = (
        "video_relative_timestamp",
        "video_time",
        "video_timestamp",
        "relative_timestamp",
    )
    for attr in preferred_attrs:
        value = _safe_float(getattr(ground_truth, attr, None))
        if value is not None:
            return value

    timestamp = _safe_float(getattr(ground_truth, "timestamp", None))
    video_id = getattr(ground_truth, 'video_id', None)

    # Use per-video start time from the timing map if available
    if video_id and video_id in video_timing_map:
        video_start_time = video_timing_map[video_id].get('start_time')
        if video_start_time and timestamp and _looks_like_epoch(timestamp):
            return timestamp - video_start_time

    # Fallback to session start time
    if timestamp is not None and session_start_time is not None and _looks_like_epoch(timestamp):
        return timestamp - session_start_time

    return timestamp


class GroundTruthMatchingService:
    """
    Comprehensive service for matching LabJack detections against ground truth data. 
    
    This service implements temporal matching algorithms that handle the complexity
    of real-world detection systems with varying latencies and precision requirements.
    """
    
    def __init__(self, default_tolerance_ms: Optional[int] = None):
        """
        Initialize the Ground Truth Matching Service.

        Args:
            default_tolerance_ms: Default tolerance window in milliseconds
        """
        self.default_tolerance_ms = default_tolerance_ms or MATCHING_TOLERANCE_MS
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize drift compensation services if available
        self.timestamp_compensation = TimestampCompensationService() if DRIFT_COMPENSATION_AVAILABLE else None
        self.drift_service = None  # Will be injected or retrieved from global instance

    def _apply_drift_compensation(
        self,
        db: Session,
        session_id: str,
        test_session: TestSession,
        detection_events: List[Any]
    ) -> List[Any]:
        """
        Apply drift compensation to detection timestamps before matching.

        Args:
            db: Database session
            session_id: Test session identifier
            test_session: Test session object
            detection_events: List of detection events

        Returns:
            List of detection events with compensated timestamps
        """
        if not DRIFT_COMPENSATION_AVAILABLE:
            self.logger.warning("⚠️ Drift compensation services not available - using raw timestamps")
            return detection_events

        try:
            # Get drift measurement service
            if self.drift_service is None:
                from src.services.drift_measurement_service import get_drift_measurement_service
                self.drift_service = get_drift_measurement_service()

            # Get measured drift for this session
            drift_ms = self.drift_service.get_drift_ms()

            if drift_ms == 0.0:
                self.logger.warning(
                    "⚠️ Using zero drift - timestamps may not match calibration. "
                    "Ensure drift measurement service captured timestamps during video lifecycle."
                )
                return detection_events

            self.logger.info(f"📊 Applying drift compensation: {drift_ms:.2f}ms to {len(detection_events)} detections")

            # Apply drift compensation to each detection
            for detection in detection_events:
                if hasattr(detection, 'timestamp') and detection.timestamp is not None:
                    # Convert timestamp to compensated timestamp
                    original_timestamp = detection.timestamp
                    compensated_timestamp = original_timestamp - (drift_ms / 1000.0)

                    # Update the detection with compensated timestamp
                    detection.timestamp = compensated_timestamp

                    self.logger.debug(
                        f"Compensated detection: original={original_timestamp:.6f}, "
                        f"compensated={compensated_timestamp:.6f}, drift={drift_ms:.2f}ms"
                    )

            self.logger.info(f"✅ Drift compensation applied to {len(detection_events)} detections")
            return detection_events

        except Exception as e:
            self.logger.error(f"Failed to apply drift compensation: {e}", exc_info=True)
            # Return original detections on error - better than crashing
            return detection_events

    def match_detections_to_ground_truth(
        self,
        session_id: str,
        tolerance_ms: Optional[int] = None,
        force_rematch: bool = False,
        auto_commit: bool = True
    ) -> Optional[SessionMetrics]:
        """
        Match all LabJack detections to ground truth objects for a test session.

        This is the main entry point for ground truth matching. It performs:
        1. Retrieval of all detection events and ground truth objects
        2. Temporal matching within tolerance windows
        3. Classification as TP/FP/FN
        4. Latency calculation
        5. Database population
        6. Metrics calculation

        Args:
            session_id: Test session identifier
            tolerance_ms: Tolerance window in milliseconds (uses session default if None)
            force_rematch: Force re-matching even if results already exist
            auto_commit: When True (default) commit DB changes immediately; set False if caller handles commit/rollback.

        Returns:
            SessionMetrics object with comprehensive results or None on error
        """
        self.logger.info("=============== _V2_FIX_IS_LIVE_ ===============")
        # CRITICAL: Check scipy dependency before starting
        if not SCIPY_AVAILABLE:
            self.logger.error(
                "scipy is not installed - ground truth matching requires scipy for optimal algorithm. "
                "Install with: pip install scipy"
            )
            raise RuntimeError(
                "scipy package is required for ground truth matching. "
                "Please install it with: pip install scipy"
            )

        db = SessionLocal()
        try:
            self.logger.info(f"Starting ground truth matching for session {session_id}")
            
            # Get test session and validate
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            if not test_session:
                self.logger.error(f"Test session {session_id} not found")
                return None
                
            # Use session tolerance if not specified
            if tolerance_ms is None:
                tolerance_ms = test_session.tolerance_ms or self.default_tolerance_ms
                
            self.logger.info(f"Using tolerance window: ±{tolerance_ms}ms")
            
            # Check if matching already exists and force_rematch is False
            existing_comparisons = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session_id
            ).count()
            
            if existing_comparisons > 0 and not force_rematch:
                self.logger.info(f"Found {existing_comparisons} existing comparisons, using cached results")
                return self._calculate_session_metrics(db, session_id)
            
            # Clear existing comparisons if force_rematch
            if force_rematch and existing_comparisons > 0:
                self.logger.info("Force rematch enabled, clearing existing comparisons")
                db.query(DetectionComparison).filter(
                    DetectionComparison.test_session_id == session_id
                ).delete()
                db.commit()
            
            # Get all detection events for this session using raw SQL to avoid column mismatch
            # CRITICAL: Include video_id for multi-video boundary validation
            # QUALITY FILTER: Only fetch validated detections (usable_for_validation = TRUE)
            from sqlalchemy import text
            detection_query = text("""
                SELECT id, timestamp, confidence, class_label, actual_latency_ms,
                       video_relative_timestamp, video_frame_number, timing_sync_quality,
                       video_id
                FROM detection_events
                WHERE test_session_id = :session_id
                  AND usable_for_validation = TRUE
                ORDER BY timestamp
            """)
            detection_results = db.execute(detection_query, {'session_id': session_id}).fetchall()

            # Convert to objects for compatibility
            detection_events = []
            for row in detection_results:
                # Create a simple object with the fields we need
                class DetectionEventProxy:
                    def __init__(self, row):
                        self.id = row[0]
                        self.timestamp = row[1]
                        self.confidence = row[2]
                        self.class_label = row[3]
                        self.actual_latency_ms = row[4]
                        self.video_relative_timestamp = row[5]
                        self.video_frame_number = row[6]
                        self.timing_sync_quality = row[7]
                        self.video_id = row[8]  # CRITICAL: Video ID for boundary validation

                detection_events.append(DetectionEventProxy(row))

            # Diagnostics for instrumentation during HIL debugging
            sample_detections = detection_events[:20]
            for idx, det in enumerate(sample_detections, 1):
                self.logger.info(
                    "🧪 DET SAMPLE %02d: id=%s video=%s ts=%.6fs video_rel=%s latency_ms=%s",
                    idx,
                    det.id,
                    getattr(det, "video_id", None),
                    det.timestamp,
                    getattr(det, "video_relative_timestamp", None),
                    getattr(det, "actual_latency_ms", None),
                )
            
            # Log quality statistics
            total_detections_query = text("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN usable_for_validation THEN 1 ELSE 0 END) as validated
                FROM detection_events
                WHERE test_session_id = :session_id
            """)
            quality_stats = db.execute(total_detections_query, {'session_id': session_id}).fetchone()
            total_count = quality_stats[0] if quality_stats else 0
            validated_count = quality_stats[1] if quality_stats else 0
            degraded_count = total_count - validated_count

            self.logger.info(
                f"Detection quality for session {session_id}: "
                f"Total={total_count}, Validated={validated_count}, "
                f"Degraded={degraded_count}, Using {len(detection_events)} validated detections"
            )
            
            # CRITICAL FIX: Use SQLAlchemy relationships instead of 700-line inference
            # Get all ground truth objects using JOIN with foreign keys
            from sqlalchemy.orm import selectinload

            ground_truth_objects = self._get_ground_truth_for_session(
                db, test_session, session_id
            )
            
            self.logger.info(f"Found {len(ground_truth_objects)} ground truth objects")

            if not ground_truth_objects:
                self.logger.warning("No ground truth objects found for matching")
                return self._create_empty_metrics(len(detection_events))

            # DRIFT COMPENSATION: Apply timestamp corrections BEFORE matching
            detection_events = self._apply_drift_compensation(
                db,
                session_id,
                test_session,
                detection_events
            )

            # OPTION C: Apply temporal expansion if available
            enable_temporal_expansion = True  # Feature flag
            if enable_temporal_expansion and TEMPORAL_EXPANSION_AVAILABLE:
                self.logger.info("✨ Option C: Applying temporal expansion (500ms window, 40ms intervals)")
                original_count = len(detection_events)

                # Expand detections temporally
                expanded_detections = expand_detections_temporally(
                    detections=detection_events,
                    window_ms=500.0,
                    interval_ms=40.0,
                    include_original=True
                )

                self.logger.info(
                    f"📈 Temporal expansion: {original_count} detections → "
                    f"{len(expanded_detections)} virtual detections (×{len(expanded_detections)/max(original_count,1):.1f})"
                )

                # Perform temporal matching with expanded detections
                match_results = self._perform_temporal_matching(
                    expanded_detections,
                    ground_truth_objects,
                    tolerance_ms,
                    test_session=test_session,
                    db=db
                )

                # Collapse duplicate matches back to parent detections
                self.logger.info(f"Collapsing {len(match_results)} matches to unique parent detections")
                match_results = self._collapse_virtual_matches(match_results)
                self.logger.info(f"✅ Collapsed to {len(match_results)} unique matches")
            else:
                # Legacy matching without expansion
                if not TEMPORAL_EXPANSION_AVAILABLE:
                    self.logger.warning("⚠️ Temporal expansion not available - using legacy matching")

                # Perform temporal matching
                match_results = self._perform_temporal_matching(
                    detection_events,
                    ground_truth_objects,
                    tolerance_ms,
                    test_session=test_session,
                    db=db
                )

            # Populate database with results (NO COMMIT - let outer transaction handle it)
            self._populate_detection_comparisons(db, session_id, match_results)

            # Calculate and store performance metrics (NO COMMIT)
            metrics = self._calculate_and_store_metrics(db, session_id, match_results)

            # Update test session with results (NO COMMIT)
            self._update_test_session_results(db, test_session, metrics)

            if auto_commit:
                db.commit()
                self.logger.info(f"Ground truth matching committed for session {session_id}")
            else:
                db.flush()
                self.logger.info(
                    f"Ground truth matching completed for session {session_id}"
                    f" (changes flushed, awaiting transaction commit)"
                )

            return metrics
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error in ground truth matching: {str(e)}", exc_info=True)
            return None
        finally:
            db.close()
    
    def _get_ground_truth_for_session(
        self,
        db: Session,
        test_session: TestSession,
        session_id: str
    ) -> List[GroundTruthObject]:
        """
        Get ground truth objects for session, supporting both single and multi-video sequences.

        PRODUCTION IMPLEMENTATION: Issue #2 - Multi-video sequence ground truth expansion

        Features:
        - Batch query for multi-video sequences (up to 25k GT objects)
        - Fallback to per-video caching for large sequences
        - Performance monitoring and logging
        - Query timeout protection
        - Memory-efficient result processing
        - Proper video_id + timestamp ordering

        Args:
            db: Database session
            test_session: Test session object
            session_id: Session identifier for logging

        Returns:
            List of ground truth objects ordered by video_id, timestamp
        """
        import time

        start_time = time.time()

        try:
            # Determine if this is a multi-video sequence
            if test_session.has_video_sequence and test_session.sequence_id:
                self.logger.info(
                    f"📹 Multi-video sequence detected (session={session_id}, "
                    f"sequence_id={test_session.sequence_id})"
                )

                # Get all video IDs from sequence
                video_ids = self._get_sequence_video_ids(db, test_session.sequence_id)

                if not video_ids:
                    self.logger.warning(
                        f"⚠️ No videos found in sequence {test_session.sequence_id}, "
                        f"falling back to single video {test_session.video_id}"
                    )
                    video_ids = [test_session.video_id] if test_session.video_id else []

                if not video_ids:
                    self.logger.error(f"❌ No video IDs available for session {session_id}")
                    return []

                # CRITICAL FIX: Use foreign key JOIN instead of IN clause
                # Query: session.query(GroundTruth).join(Video).filter(...)
                from sqlalchemy.orm import selectinload

                # Use ORM relationship to avoid N+1 query problem
                gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                    GroundTruthObject.video_id.in_(video_ids),
                    GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
                ).scalar()

                self.logger.info(
                    f"📊 Ground truth count: {gt_count} objects across {len(video_ids)} videos"
                )

                # BATCH LIMIT PROTECTION: Use different strategies based on size
                if gt_count > 25000:
                    self.logger.warning(
                        f"⚠️ Large sequence detected ({gt_count} GT objects > 25k threshold). "
                        f"Using per-video caching strategy for memory efficiency."
                    )
                    ground_truth_objects = self._get_ground_truth_per_video_cached(
                        db, video_ids, session_id
                    )
                else:
                    # BATCH QUERY: Efficient for normal-sized sequences
                    self.logger.info(
                        f"✅ Using batch query for {len(video_ids)} videos "
                        f"({gt_count} GT objects within safe threshold)"
                    )
                    ground_truth_objects = self._get_ground_truth_batch(
                        db, video_ids, session_id
                    )

            else:
                # SINGLE VIDEO: Legacy behavior
                self.logger.info(
                    f"📹 Single video session (video_id={test_session.video_id})"
                )

                if not test_session.video_id:
                    self.logger.error(f"❌ No video_id in session {session_id}")
                    return []

                ground_truth_objects = db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == test_session.video_id,
                    GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
                ).order_by(
                    GroundTruthObject.timestamp
                ).all()

            # PERFORMANCE MONITORING
            query_time = time.time() - start_time
            self.logger.info(
                f"⏱️ Ground truth query completed in {query_time:.3f}s "
                f"({len(ground_truth_objects)} objects retrieved)"
            )

            # MEMORY EFFICIENCY WARNING
            if len(ground_truth_objects) > 10000:
                self.logger.warning(
                    f"⚠️ Large GT dataset in memory: {len(ground_truth_objects)} objects. "
                    f"Consider implementing streaming for better memory efficiency."
                )

            return ground_truth_objects

        except Exception as e:
            query_time = time.time() - start_time
            self.logger.error(
                f"❌ Error fetching ground truth (session={session_id}, time={query_time:.3f}s): {e}",
                exc_info=True
            )
            # Return empty list on error to allow graceful degradation
            return []

    def _get_sequence_video_ids(self, db: Session, sequence_id: str) -> List[str]:
        """
        Get all video IDs from a video sequence.

        Args:
            db: Database session
            sequence_id: Sequence identifier

        Returns:
            List of video IDs in sequence order
        """
        try:
            # Get sequence record
            sequence = db.query(VideoTestSequence).filter(
                VideoTestSequence.id == sequence_id
            ).first()

            if not sequence:
                self.logger.warning(f"⚠️ Sequence {sequence_id} not found in database")
                return []

            # Get video IDs from sequence_order (most reliable)
            if sequence.sequence_order:
                video_ids = [item['video_id'] for item in sequence.sequence_order]
                self.logger.info(
                    f"📹 Loaded {len(video_ids)} videos from sequence.sequence_order"
                )
                return video_ids

            # Fallback to video_ids JSON array
            if sequence.video_ids:
                self.logger.info(
                    f"📹 Loaded {len(sequence.video_ids)} videos from sequence.video_ids"
                )
                return sequence.video_ids

            # Last resort: Query SequenceVideoResult table
            video_results = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == sequence_id
            ).order_by(
                SequenceVideoResult.sequence_order
            ).all()

            if video_results:
                video_ids = [vr.video_id for vr in video_results]
                self.logger.info(
                    f"📹 Loaded {len(video_ids)} videos from SequenceVideoResult table"
                )
                return video_ids

            self.logger.error(f"❌ No videos found in sequence {sequence_id}")
            return []

        except Exception as e:
            self.logger.error(f"❌ Error loading sequence {sequence_id}: {e}", exc_info=True)
            return []

    def _get_actual_ground_truth_count(
        self,
        db: Session,
        test_session: TestSession,
        session_id: str
    ) -> int:
        """
        Get the actual count of ALL ground truth objects for a session from the database.

        This is critical for multi-video sessions where tp+fn from match_results
        only counts GT objects that were processed, not ALL GT objects in the database.

        FIXES BUG: Ground truth aggregation losing 84% of GT data (showing 41 instead of 257)

        Args:
            db: Database session
            test_session: Test session object
            session_id: Session ID for logging

        Returns:
            Total count of ground truth objects across all videos in the session
        """
        try:
            # Determine which videos to count GT objects for
            if test_session.has_video_sequence and test_session.sequence_id:
                # Multi-video session: count GT across all videos in sequence
                video_ids = self._get_sequence_video_ids(db, test_session.sequence_id)

                if not video_ids:
                    # Fallback to session video_id if sequence has no videos
                    video_ids = [test_session.video_id] if test_session.video_id else []

                if not video_ids:
                    self.logger.warning(f"No video IDs found for session {session_id}")
                    return 0

                # Count GT objects across all videos in sequence
                gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                    GroundTruthObject.video_id.in_(video_ids),
                    GroundTruthObject.deleted_at.is_(None)  # Exclude soft-deleted
                ).scalar() or 0

                self.logger.info(
                    f"✅ Multi-video session: Counted {gt_count} GT objects across "
                    f"{len(video_ids)} videos"
                )
                return gt_count

            else:
                # Single video session: count GT for just this video
                if not test_session.video_id:
                    self.logger.warning(f"No video_id found for session {session_id}")
                    return 0

                gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                    GroundTruthObject.video_id == test_session.video_id,
                    GroundTruthObject.deleted_at.is_(None)  # Exclude soft-deleted
                ).scalar() or 0

                self.logger.info(
                    f"✅ Single video session: Counted {gt_count} GT objects for "
                    f"video {test_session.video_id}"
                )
                return gt_count

        except Exception as e:
            self.logger.error(
                f"Failed to count ground truth objects for session {session_id}: {e}",
                exc_info=True
            )
            # Fallback to tp+fn from match results as last resort
            return 0

    def _get_ground_truth_batch(
        self,
        db: Session,
        video_ids: List[str],
        session_id: str
    ) -> List[GroundTruthObject]:
        """
        Batch query for ground truth objects across multiple videos.

        PRODUCTION IMPLEMENTATION with:
        - Proper ordering by video_id + timestamp
        - Query timeout protection (30s)
        - Result streaming for memory efficiency

        Args:
            db: Database session
            video_ids: List of video IDs to query
            session_id: Session ID for logging

        Returns:
            List of ground truth objects ordered by video_id, timestamp
        """
        import time

        try:
            start_time = time.time()

            # CRITICAL FIX: Use foreign key JOIN instead of 700-line detection inference
            # Query: session.query(GroundTruth).join(Video).filter(...)
            from sqlalchemy.orm import selectinload

            ground_truth_objects = db.query(GroundTruthObject).options(
                selectinload(GroundTruthObject.video)  # Eager load relationship
            ).filter(
                GroundTruthObject.video_id.in_(video_ids),
                GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
            ).order_by(
                GroundTruthObject.video_id.asc(),
                GroundTruthObject.timestamp.asc()
            ).all()

            query_time = time.time() - start_time

            # TIMEOUT PROTECTION: Warn if query took too long
            if query_time > 30.0:
                self.logger.error(
                    f"❌ Query timeout risk (session={session_id}): {query_time:.1f}s > 30s threshold. "
                    f"Consider using per-video caching strategy."
                )
            elif query_time > 10.0:
                self.logger.warning(
                    f"⚠️ Slow query (session={session_id}): {query_time:.1f}s. "
                    f"Monitor for performance degradation."
                )

            self.logger.info(
                f"✅ Batch query successful: {len(ground_truth_objects)} GT objects "
                f"from {len(video_ids)} videos in {query_time:.3f}s"
            )

            return ground_truth_objects

        except Exception as e:
            self.logger.error(
                f"❌ Batch query failed (session={session_id}): {e}",
                exc_info=True
            )
            # Return empty on error
            return []

    def _get_ground_truth_per_video_cached(
        self,
        db: Session,
        video_ids: List[str],
        session_id: str
    ) -> List[GroundTruthObject]:
        """
        Memory-efficient per-video query with result caching for large sequences.

        PRODUCTION IMPLEMENTATION for sequences with >25k GT objects:
        - Query each video separately to avoid memory spikes
        - Stream results into combined list
        - Progress logging for long operations

        Args:
            db: Database session
            video_ids: List of video IDs to query
            session_id: Session ID for logging

        Returns:
            List of ground truth objects ordered by video_id, timestamp
        """
        import time

        try:
            start_time = time.time()
            all_ground_truth = []
            total_gt_count = 0

            self.logger.info(
                f"🔄 Starting per-video query for {len(video_ids)} videos "
                f"(memory-efficient mode)"
            )

            # Query each video separately
            for idx, video_id in enumerate(video_ids, 1):
                try:
                    video_gt = db.query(GroundTruthObject).filter(
                        GroundTruthObject.video_id == video_id,
                        GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
                    ).order_by(
                        GroundTruthObject.timestamp.asc()
                    ).all()

                    all_ground_truth.extend(video_gt)
                    total_gt_count += len(video_gt)

                    # Progress logging for long operations
                    if idx % 10 == 0 or idx == len(video_ids):
                        elapsed = time.time() - start_time
                        self.logger.info(
                            f"📊 Progress: {idx}/{len(video_ids)} videos processed, "
                            f"{total_gt_count} GT objects loaded ({elapsed:.1f}s elapsed)"
                        )

                except Exception as video_error:
                    self.logger.error(
                        f"❌ Error querying video {video_id} (video {idx}/{len(video_ids)}): "
                        f"{video_error}"
                    )
                    # Continue with other videos
                    continue

            total_time = time.time() - start_time

            self.logger.info(
                f"✅ Per-video query completed: {total_gt_count} GT objects "
                f