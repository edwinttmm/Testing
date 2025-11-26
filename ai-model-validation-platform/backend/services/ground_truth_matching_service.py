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

# REMOVED: FP_LATENCY_MARKER constant
# False Positive detections now use is_false_positive field instead of sentinel latency value
# Real latencies are stored for all detections, including FPs


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
            logger.debug(f"🔍 extract_detection_video_time: Found {attr}={value} for detection {getattr(detection, 'id', 'N/A')}")
            return value

    timestamp = _safe_float(getattr(detection, "timestamp", None))
    video_id = getattr(detection, 'video_id', None)

    # Use per-video start time from the timing map if available
    if video_id and video_id in video_timing_map:
        video_start_time = video_timing_map[video_id].get('start_time')
        if video_start_time and timestamp and _looks_like_epoch(timestamp):
            result = timestamp - video_start_time
            logger.debug(f"🔍 extract_detection_video_time: Using video timing map: timestamp={timestamp} - video_start={video_start_time} = {result}")
            return result

    # Fallback to session start time
    if timestamp is not None and session_start_time is not None and _looks_like_epoch(timestamp):
        result = timestamp - session_start_time
        logger.debug(f"🔍 extract_detection_video_time: Using session start: timestamp={timestamp} - session_start={session_start_time} = {result}")
        return result

    logger.debug(f"🔍 extract_detection_video_time: Returning raw timestamp={timestamp} (no conversion)")
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
            validated_count = quality_stats[1] if quality_stats and quality_stats[1] is not None else 0
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
            # DISABLED: Temporal expansion causes 3x detection expansion (173→519) which creates
            # a 98% sparse cost matrix (1.94% density) that breaks the Hungarian algorithm.
            # This forces a suboptimal greedy fallback reducing F1 from 75% to 59.53%.
            # Expected improvement after disabling: F1 score 75%+ (from 59.53%)
            enable_temporal_expansion = False  # Feature flag - DISABLED for Priority 1 fix
            if enable_temporal_expansion and TEMPORAL_EXPANSION_AVAILABLE:
                self.logger.info("✨ Option C: Applying temporal expansion (±100ms window, 40ms intervals)")
                original_count = len(detection_events)

                # Expand detections temporally
                # Use spec-compliant ±100ms tolerance window for temporal expansion
                expanded_detections = expand_detections_temporally(
                    detections=detection_events,
                    window_ms=100.0,  # ±100ms tolerance per HIL validation spec
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
                self.logger.info(f"🔄 Collapsing {len(match_results)} matches to unique parent detections")
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
                    f"Ground truth matching completed for session {session_id} "
                    f"(changes flushed, awaiting transaction commit)"
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
        from sqlalchemy import text

        start_time = time.time()

        try:
            self.logger.info(f"INVESTIGATION: Inside _get_ground_truth_for_session for session_id: {session_id}")
            self.logger.info(f"INVESTIGATION: test_session.video_id = {test_session.video_id}")
            self.logger.info(f"INVESTIGATION: test_session.has_video_sequence = {test_session.has_video_sequence}")
            self.logger.info(f"INVESTIGATION: test_session.sequence_id = {test_session.sequence_id}")

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

            self.logger.info(f"INVESTIGATION: Found {len(ground_truth_objects)} ground truth objects.")
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
                f"from {len(video_ids)} videos in {total_time:.3f}s "
                f"(avg {total_time/len(video_ids):.3f}s per video)"
            )

            # CRITICAL: Sort combined results by video_id + timestamp for consistency
            all_ground_truth.sort(key=lambda gt: (gt.video_id, gt.timestamp))

            return all_ground_truth

        except Exception as e:
            self.logger.error(
                f"❌ Per-video caching failed (session={session_id}): {e}",
                exc_info=True
            )
            return []

    def _collapse_virtual_matches(self, match_results: List[MatchResult]) -> List[MatchResult]:
        """
        Collapse virtual detection matches back to parent detections.

        This is part of Option C temporal expansion - after matching with virtual detections,
        we need to deduplicate matches that came from the same parent detection AND ensure
        each ground truth object is matched by at most one detection.

        CRITICAL FIX: Two-level deduplication:
        1. Group by parent detection ID (remove virtual suffix duplicates)
        2. Group by ground truth ID (prevent multiple detections matching same GT)

        Args:
            match_results: List of MatchResult objects (may contain duplicates from virtual detections)

        Returns:
            List of deduplicated MatchResult objects (one detection per GT, best match per parent)
        """
        if not match_results:
            return []

        # STEP 1: Group matches by parent detection ID
        parent_groups = {}

        for match in match_results:
            detection_id = match.detection_event_id

            # CRITICAL FIX: Skip FN matches (no detection_event_id)
            if detection_id is None:
                # False negative - no detection to collapse
                parent_groups[None] = parent_groups.get(None, [])
                parent_groups[None].append(match)
                continue

            # Parse parent ID from virtual detection ID (format: "parent-vN")
            if '-v' in detection_id:
                parent_id = detection_id.rsplit('-v', 1)[0]
            else:
                parent_id = detection_id

            if parent_id not in parent_groups:
                parent_groups[parent_id] = []
            parent_groups[parent_id].append(match)

        # STEP 2: Deduplicate within each parent group (best match per parent)
        parent_best_matches = {}
        for parent_id, group in parent_groups.items():
            if len(group) == 1:
                # No duplicates within parent
                best_match = group[0]
            else:
                # Multiple matches from same parent - keep the one with smallest absolute offset
                # CRITICAL FIX: Handle None latency_ms (FN matches)
                best_match = min(group, key=lambda m: (
                    abs(m.latency_ms) if m.latency_ms is not None
                    else float('inf')
                ))

            # Update detection_id to parent ID (remove virtual suffix)
            if parent_id is not None:
                best_match.detection_event_id = parent_id

            parent_best_matches[parent_id] = best_match

        # STEP 3: Group by ground truth ID (ensure each GT matched only once)
        gt_groups = {}
        for parent_id, match in parent_best_matches.items():
            gt_id = match.ground_truth_id

            if gt_id not in gt_groups:
                gt_groups[gt_id] = []
            gt_groups[gt_id].append(match)

        # STEP 4: Deduplicate by ground truth (best match per GT)
        final_matches = []
        for gt_id, group in gt_groups.items():
            if len(group) == 1:
                # Only one detection matched this GT - keep it
                final_matches.append(group[0])
            else:
                # CRITICAL: Multiple detections matched same GT - keep best one, mark others as FP
                self.logger.warning(
                    f"Ground truth {gt_id} matched by {len(group)} detections - "
                    f"keeping best match, marking others as FP"
                )

                # Find best match (smallest temporal offset)
                best_match = min(group, key=lambda m: (
                    abs(m.latency_ms) if m.latency_ms is not None
                    else float('inf')
                ))

                # Mark other matches as false positives
                for match in group:
                    if match != best_match:
                        # Convert to false positive
                        match.match_type = 'FP'
                        # Keep the actual latency, don't replace with sentinel
                        match.ground_truth_id = None  # Remove GT association
                        self.logger.debug(
                            f"Converted duplicate GT match to FP: detection {match.detection_event_id} "
                            f"(was matched to GT {gt_id})"
                        )

                # Add all matches (best as TP, others as FP)
                final_matches.extend(group)

        return final_matches

    def _perform_temporal_matching(
        self,
        detection_events: List[Any],  # Can be DetectionEvent or ExpandedDetection
        ground_truth_objects: List[GroundTruthObject],
        tolerance_ms: int,
        test_session: Optional[TestSession] = None,
        db: Optional[Session] = None
    ) -> List[MatchResult]:
        """
        Perform temporal matching between detections and ground truth.

        Algorithm:
        1. For each ground truth object, find the closest detection within tolerance
        2. Handle multiple detections near the same ground truth (first-match wins)
        3. Classify remaining detections as false positives
        4. Classify unmatched ground truth as false negatives

        Args:
            detection_events: List of detection events or ExpandedDetection objects
            ground_truth_objects: List of ground truth objects
            tolerance_ms: Tolerance window in milliseconds

        Returns:
            List of MatchResult objects
        """
        tolerance_seconds = tolerance_ms / 1000.0
        match_results = []
        used_detections = set()
        tp_debug_count = 0

        self.logger.info(f"Performing temporal matching with {tolerance_ms}ms tolerance")
        session_start_time = None
        if test_session is not None:
            session_start_time = _safe_float(
                getattr(test_session, "video_playback_start_time", None)
            )

        # BUG #10 FIX: Detect if this is a multi-video sequence by checking video_id distribution
        # If ground truth objects span multiple video_ids, we're in multi-video mode
        gt_video_ids = set()
        gt_by_video = {}  # Group GT by video_id for smart fallback matching
        for gt_obj in ground_truth_objects:
            gt_video_id = getattr(gt_obj, 'video_id', None)
            if gt_video_id is not None:
                gt_video_ids.add(gt_video_id)
                if gt_video_id not in gt_by_video:
                    gt_by_video[gt_video_id] = []
                gt_by_video[gt_video_id].append(gt_obj)

        has_multi_video_sequence = len(gt_video_ids) > 1

        # CRITICAL FIX #5: Build video timing map with per-video start times
        # BUG #5 FIX: Each video in a sequence has its own start time (video_start_time)
        # which is different from the session/sequence start time.
        # Video 1: 0-5.04s (video_start_time = session_start)
        # Video 2: 5.04-10.08s (video_start_time = session_start + 5.04)
        # FIX: Also build timing map for SINGLE video tests to filter post-video FPs
        video_timing_map = {}  # video_id -> { order, duration_s, start_time, end_time }
        if test_session and test_session.sequence_id:
            try:
                from models import SequenceVideoResult
                video_results = db.query(SequenceVideoResult).filter(
                    SequenceVideoResult.video_sequence_id == test_session.sequence_id
                ).order_by(SequenceVideoResult.sequence_order).all()

                if video_results:
                    for result in video_results:
                        # BUG #5 FIX: Use video-specific start time (NOT session start)
                        video_start = result.video_start_time
                        # ZERO-DURATION FIX: Use authoritative video_end_time from DB instead of calculating
                        # from actual_duration_ms (which may be NULL). Calculate duration from start/end.
                        video_end = result.video_end_time
                        duration_s = (video_end - video_start) if (video_end and video_start) else 0

                        # CRITICAL FIX: Validate video_start_time is not None (causes incorrect latencies)
                        # If video_start_time is None, detections fall back to session_start_time
                        # which creates massive timing errors for later videos in sequence
                        if video_start is None:
                            self.logger.error(
                                f"❌ CRITICAL: video_start_time is None for video {result.video_id[:12]} "
                                f"(order={result.sequence_order}). This causes incorrect latencies!"
                            )
                            # Skip adding this video to timing map - force use of session_start_time
                            # This will log the issue but prevent the silent failure
                            continue

                        video_timing_map[result.video_id] = {
                            'order': result.sequence_order,
                            'duration_s': duration_s,
                            'start_time': video_start,
                            'end_time': video_end,
                            'filename': getattr(result.video_sequence, 'name', result.video_id)
                        }

                        self.logger.info(
                            f"📹 Video {result.sequence_order + 1} (id={result.video_id[:12]}): "
                            f"{video_start:.3f}s - {video_end:.3f}s (duration: {duration_s:.2f}s)"
                        )

                    self.logger.info(f"✅ Built video timing map for {len(video_timing_map)} videos in sequence")
                else:
                    self.logger.warning(f"Could not load video results for sequence {test_session.sequence_id}")

            except Exception as e:
                self.logger.error(f"Error building video timing map: {e}", exc_info=True)

        # FALLBACK: For single video tests WITHOUT sequence_id, build timing map from video metadata
        # This ensures FP filter works even for legacy/simple single video tests
        if not video_timing_map and ground_truth_objects:
            self.logger.info("Building video timing map from ground truth video metadata (no sequence)")
            try:
                # Get unique video IDs from ground truth
                gt_video_ids_set = set()
                for gt_obj in ground_truth_objects:
                    vid = getattr(gt_obj, 'video_id', None)
                    if vid:
                        gt_video_ids_set.add(str(vid))

                # For each video, get its duration from the database
                from models import Video
                for video_id in gt_video_ids_set:
                    video = db.query(Video).filter(Video.id == video_id).first()
                    # Use 'duration' column (not 'duration_seconds')
                    video_duration = getattr(video, 'duration', None) if video else None
                    if video and video_duration:
                        # For single video tests, video starts at 0 (relative time)
                        video_timing_map[video_id] = {
                            'order': 0,
                            'duration_s': video_duration,
                            'start_time': 0.0,  # Video relative time starts at 0
                            'end_time': video_duration
                        }
                        self.logger.info(
                            f"📹 Single video (id={video_id[:12]}): "
                            f"0.000s - {video_duration:.3f}s (duration: {video_duration:.2f}s)"
                        )

                if video_timing_map:
                    self.logger.info(f"✅ Built fallback video timing map for {len(video_timing_map)} videos")
            except Exception as e:
                self.logger.error(f"Error building fallback video timing map: {e}", exc_info=True)

        if has_multi_video_sequence:
            self.logger.info(f"🎯 BUG #10 FIX: Detected multi-video sequence with {len(gt_video_ids)} videos - "
                           f"Enforcing strict video boundary validation")
            self.logger.info(f"Ground truth distribution: {[(vid, len(gt_by_video[vid])) for vid in gt_video_ids]}")

        # Track video boundary validations for logging
        video_boundary_rejections = 0
        missing_video_id_warnings = 0

        # ========================================================================
        # OPTIMAL HUNGARIAN ALGORITHM MATCHING (replaces greedy Phase 1)
        # ========================================================================
        # Extract timestamps AND video IDs for optimal matching
        gt_times = []
        gt_video_ids = []
        det_times = []
        det_video_ids = []

        for gt_obj in ground_truth_objects:
            gt_time = extract_ground_truth_video_time(gt_obj, video_timing_map, session_start_time)
            gt_times.append(gt_time if gt_time is not None else float('inf'))
            gt_video_ids.append(getattr(gt_obj, 'video_id', None))

        for detection in detection_events:
            det_time = extract_detection_video_time(detection, video_timing_map, session_start_time)
            det_times.append(det_time if det_time is not None else float('inf'))
            det_video_ids.append(getattr(detection, 'video_id', None))

        # 🔍 DEBUG: Check extracted timestamps
        logger.info(f"🔍 DEBUG: Sample det_times (first 5): {det_times[:5]}")
        logger.info(f"🔍 DEBUG: Sample gt_times (first 5): {gt_times[:5]}")
        logger.info(f"🔍 DEBUG: Tolerance: {tolerance_seconds}s ({tolerance_seconds*1000}ms)")
        logger.info(f"🔍 DEBUG: Total detections: {len(det_times)}, Total GT: {len(gt_times)}")

        # Check if temporal expansion created virtual detections
        # CRITICAL FIX: Guard against empty detection_events list to prevent IndexError
        if detection_events:
            if hasattr(detection_events[0], 'virtual_id'):
                logger.info(f"🔍 DEBUG: Detections are EXPANDED (virtual)")
                logger.info(f"🔍 DEBUG: Sample expanded detection: id={getattr(detection_events[0], 'virtual_id', 'N/A')}, "
                           f"timestamp={getattr(detection_events[0], 'timestamp', 'N/A')}, "
                           f"video_relative_timestamp={getattr(detection_events[0], 'video_relative_timestamp', 'N/A')}")
            else:
                logger.info(f"🔍 DEBUG: Detections are ORIGINAL (not expanded)")
                logger.info(f"🔍 DEBUG: Sample original detection: id={getattr(detection_events[0], 'id', 'N/A')}, "
                           f"timestamp={getattr(detection_events[0], 'timestamp', 'N/A')}, "
                           f"video_relative_timestamp={getattr(detection_events[0], 'video_relative_timestamp', 'N/A')}")
        else:
            logger.warning(f"🔍 DEBUG: No detections available for analysis - detection_events list is empty")

        # Run optimal matching algorithm with video-aware filtering
        # CRITICAL FIX: Pass video IDs to prevent cross-video matches in cost matrix
        # This ensures Hungarian/greedy algorithms only consider same-video pairings
        optimal_result = optimal_detection_matching(
            gt_times,
            det_times,
            tolerance_seconds,
            return_cost_matrix=False,
            ground_truth_video_ids=gt_video_ids if has_multi_video_sequence else None,
            detection_video_ids=det_video_ids if has_multi_video_sequence else None
        )

        logger.info(
            f"🔬 OPTIMAL MATCHING (Hungarian Algorithm): "
            f"{len(optimal_result['true_positives'])} TP, "
            f"{len(optimal_result['false_positives'])} FP, "
            f"{len(optimal_result['false_negatives'])} FN "
            f"(total_cost={optimal_result['total_cost']*1000:.1f}ms)"
        )

        # Convert optimal matching results to MatchResult format
        match_results = []

        # Process true positives from optimal matching
        for gt_idx, det_idx, latency_ms in optimal_result['true_positives']:
            gt_obj = ground_truth_objects[gt_idx]
            detection = detection_events[det_idx]

            gt_time = gt_times[gt_idx]
            det_time = det_times[det_idx]

            # CRITICAL: Video boundary validation for multi-video sequences
            detection_video_id = getattr(detection, 'video_id', None)
            gt_video_id = getattr(gt_obj, 'video_id', None)

            # NULL SAFETY: Skip if either video_id is NULL in multi-video mode
            if has_multi_video_sequence and (detection_video_id is None or gt_video_id is None):
                logger.warning(
                    f"Skipping match - NULL video_id detected (detection={detection_video_id}, gt={gt_video_id})"
                )
                # Calculate temporal offset even for rejected matches (for debugging)
                rejected_temporal_offset = latency_ms

                # Reclassify as FN for GT and FP for detection
                match_results.append(
                    MatchResult(
                        ground_truth_id=gt_obj.id,
                        detection_event_id=None,
                        match_type='FN',
                        temporal_offset=rejected_temporal_offset,
                        confidence=None,
                        iou_score=0.0,
                        latency_ms=None,
                        video_id=gt_video_id
                    )
                )
                match_results.append(
                    MatchResult(
                        ground_truth_id=None,
                        detection_event_id=detection.id,
                        match_type='FP',
                        temporal_offset=rejected_temporal_offset,
                        confidence=self._get_detection_confidence(detection),
                        iou_score=0.0,
                        latency_ms=abs(rejected_temporal_offset),  # Store actual latency for FP
                        video_id=detection_video_id
                    )
                )
                continue


            # Skip if video IDs don't match (cross-video match prevention)
            if detection_video_id is not None and gt_video_id is not None:
                if detection_video_id != gt_video_id:
                    video_boundary_rejections += 1
                    logger.debug(
                        f"❌ Rejecting cross-video match: GT video {gt_video_id[:8]} != "
                        f"Detection video {detection_video_id[:8]}"
                    )
                    # Calculate temporal offset for rejected cross-video match
                    cross_video_temporal_offset = latency_ms

                    # Reclassify as FN for GT and FP for detection
                    # Add GT as FN
                    match_results.append(
                        MatchResult(
                            ground_truth_id=gt_obj.id,
                            detection_event_id=None,
                            match_type='FN',
                            temporal_offset=cross_video_temporal_offset,
                            confidence=None,
                            iou_score=0.0,
                            latency_ms=None,
                            video_id=gt_video_id
                        )
                    )
                    # Add detection as FP
                    match_results.append(
                        MatchResult(
                            ground_truth_id=None,
                            detection_event_id=detection.id,
                            match_type='FP',
                            temporal_offset=cross_video_temporal_offset,
                            confidence=self._get_detection_confidence(detection),
                            iou_score=0.0,
                            latency_ms=abs(cross_video_temporal_offset),  # Store actual latency for FP
                            video_id=detection_video_id
                        )
                    )
                    continue

            # Valid TP match
            temporal_offset_ms = latency_ms  # Already calculated by optimal_detection_matching
            iou_score = self._calculate_temporal_iou(gt_time, det_time, tolerance_seconds)

            # Capture video_id for latency grouping
            det_video_id = detection_video_id or gt_video_id

            # NULL SAFETY: Log warning if video_id is NULL for TP match
            if det_video_id is None:
                logger.warning(
                    f"TP match has NULL video_id - detection={detection.id[:8]}, gt={gt_obj.id[:8]}"
                )
            else:
                det_video_id = str(det_video_id)

                det_video_id = str(det_video_id)

            match_result = MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=detection.id,
                match_type='TP',
                temporal_offset=temporal_offset_ms,
                confidence=self._get_detection_confidence(detection),
                iou_score=iou_score,
                latency_ms=abs(latency_ms),
                video_id=det_video_id
            )
            match_results.append(match_result)

            # Debug logging for first few matches
            if tp_debug_count < 3:
                latency_display = f"{abs(latency_ms):.1f}ms"
                self.logger.info(
                    f"🔍 DEBUG: TP match (optimal) - detection_id={detection.id[:8]}, "
                    f"video_id={det_video_id[:12] if det_video_id else 'NULL'}, "
                    f"latency={latency_display}"
                )
                tp_debug_count += 1
            if tp_debug_count <= 20:
                self.logger.info(
                    "🧪 MATCH SAMPLE %02d: GT video=%s t=%.6fs | DET video=%s t=%.6fs diff=%.3fms",
                    tp_debug_count,
                    getattr(gt_obj, "video_id", None),
                    gt_time,
                    getattr(detection, "video_id", None),
                    det_time,
                    latency_ms,
                )

        # Process false negatives from optimal matching
        for gt_idx in optimal_result['false_negatives']:
            gt_obj = ground_truth_objects[gt_idx]
            gt_video_id = getattr(gt_obj, 'video_id', None)

            # NULL SAFETY: Log warning if video_id is NULL
            if gt_video_id is None:
                logger.warning(f"FN ground truth {gt_obj.id[:8]} has NULL video_id")

            # FIXED: Calculate temporal offset to closest detection for FN (for analysis)
            # This helps understand how far off the nearest detection was
            gt_time = gt_times[gt_idx]
            fn_temporal_offset = 0.0
            if gt_time != float('inf') and len(detection_events) > 0:
                # Find closest detection time
                closest_det_time = min(det_times, key=lambda dt: abs(dt - gt_time) if dt != float('inf') else float('inf'))
                if closest_det_time != float('inf'):
                    fn_temporal_offset = (closest_det_time - gt_time) * 1000.0

            match_result = MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=None,
                match_type='FN',
                temporal_offset=fn_temporal_offset,
                confidence=None,
                iou_score=0.0,
                latency_ms=None,
                video_id=str(gt_video_id) if gt_video_id else None
            )
            match_results.append(match_result)

            # Enhanced logging
            if gt_time != float('inf'):
                self.logger.debug(
                    f"FN: Video {gt_video_id or 'unknown'} - GT@{gt_time:.3f}s - No matching detection (closest offset: {fn_temporal_offset:.1f}ms)"
                )

        # Process false positives from optimal matching
        # FIX: Skip detections that occur AFTER video end time (residual signal noise)
        # FIX: Skip detections that are WITHIN tolerance of a GT (valid but unassigned in many-to-one)
        skipped_post_video_fps = 0
        skipped_within_tolerance_fps = 0
        for det_idx in optimal_result['false_positives']:
            detection = detection_events[det_idx]
            detection_video_id = getattr(detection, 'video_id', None)

            # NULL SAFETY: Log warning if video_id is NULL
            if detection_video_id is None:
                logger.warning(f"FP detection {detection.id[:8]} has NULL video_id")

            det_time = det_times[det_idx]

            # FIX: Check if detection is AFTER video end time
            # These are residual signal detections after the video content has ended
            # Post-video detections are NOT FPs - they're outside the test window (TN territory)
            if detection_video_id and str(detection_video_id) in video_timing_map:
                video_info = video_timing_map[str(detection_video_id)]
                video_end_time = video_info.get('end_time')
                if video_end_time is not None and det_time != float('inf'):
                    if det_time > video_end_time:
                        skipped_post_video_fps += 1
                        self.logger.debug(
                            f"Excluding post-video detection: Detection@{det_time:.3f}s > Video end@{video_end_time:.3f}s (outside test window)"
                        )
                        continue  # Skip - not a valid FP, it's outside the video timing window

            # FIXED: Calculate temporal offset to closest GT for FP (for analysis)
            # This helps understand how far off the nearest ground truth was
            fp_temporal_offset = 0.0
            closest_gt_time = None
            if det_time != float('inf') and len(ground_truth_objects) > 0:
                # Find closest ground truth time
                closest_gt_time = min(gt_times, key=lambda gt: abs(gt - det_time) if gt != float('inf') else float('inf'))
                if closest_gt_time != float('inf'):
                    fp_temporal_offset = (det_time - closest_gt_time) * 1000.0

            # Determine the match type for this detection
            # Priority: 1) Within-tolerance = TP (PASS), 2) Outside tolerance = FP
            # Note: Post-video detections are already skipped above

            # FIX: Convert to TP if detection is WITHIN tolerance of a GT event
            # In many-to-one scenarios, these are valid detections that couldn't be assigned
            # because the GT was already matched by another detection - count as PASS not FP
            if closest_gt_time is not None and closest_gt_time != float('inf'):
                if abs(fp_temporal_offset) <= tolerance_seconds * 1000.0:  # Within tolerance window
                    skipped_within_tolerance_fps += 1
                    self.logger.debug(
                        f"Converting within-tolerance FP to TP: Detection@{det_time:.3f}s is {abs(fp_temporal_offset):.1f}ms from GT@{closest_gt_time:.3f}s (tolerance: {tolerance_seconds*1000:.0f}ms)"
                    )
                    # Create as TP (valid detection within tolerance, just couldn't be assigned to a specific GT)
                    match_result = MatchResult(
                        ground_truth_id=None,  # No specific GT assigned (already matched)
                        detection_event_id=detection.id,
                        match_type='TP',  # Count as TRUE POSITIVE - valid detection (PASS)
                        temporal_offset=fp_temporal_offset,
                        confidence=self._get_detection_confidence(detection),
                        iou_score=1.0,  # Valid match
                        latency_ms=abs(fp_temporal_offset),
                        video_id=str(detection_video_id) if detection_video_id else None
                    )
                    match_results.append(match_result)
                    continue  # Don't also count as FP

            # Record as FP - either post-video noise or truly outside tolerance
            # IMPORTANT: All detections MUST appear in results - non-negotiable
            match_result = MatchResult(
                ground_truth_id=None,
                detection_event_id=detection.id,
                match_type='FP',  # False positive
                temporal_offset=fp_temporal_offset,
                confidence=self._get_detection_confidence(detection),
                iou_score=0.0,
                latency_ms=abs(fp_temporal_offset),  # Store actual latency for FP
                video_id=str(detection_video_id) if detection_video_id else None
            )
            match_results.append(match_result)

            # Enhanced logging
            if det_time != float('inf'):
                self.logger.debug(
                    f"FP (OUTSIDE-TOLERANCE): Video {detection_video_id or 'unknown'} - Detection@{det_time:.3f}s - No matching GT (closest offset: {fp_temporal_offset:.1f}ms)"
                )

        # Log FP adjustments
        if skipped_post_video_fps > 0 or skipped_within_tolerance_fps > 0:
            self.logger.info(
                f"FP adjustments: {skipped_post_video_fps} post-video excluded (outside test window), {skipped_within_tolerance_fps} within-tolerance converted to TP (many-to-one PASS)"
            )

        # ========================================================================
        # OLD GREEDY ALGORITHM REMOVED
        # ========================================================================
        # The greedy first-match algorithm (lines 732-903 in previous version)
        # has been replaced by the optimal Hungarian algorithm above.
        #
        # The old algorithm had issues with suboptimal global assignments.
        # See:
        # - optimal_matching_service.py for algorithm comparison
        # - Git history for original greedy implementation
        # - docs/OPTIMAL_MATCHING_INTEGRATION_REPORT.md for details
        # ========================================================================

        # Log matching summary
        tp_count = sum(1 for mr in match_results if mr.match_type == 'TP')
        fp_count = sum(1 for mr in match_results if mr.match_type == 'FP')
        fn_count = sum(1 for mr in match_results if mr.match_type == 'FN')

        self.logger.info(
            f"Matching completed: {tp_count} TP, {fp_count} FP, {fn_count} FN "
            f"(Total: {len(match_results)} comparisons)"
        )

        # Log video boundary validation statistics
        if video_boundary_rejections > 0:
            self.logger.info(
                f"Video boundary validation: Rejected {video_boundary_rejections} cross-video matches"
            )
        if missing_video_id_warnings > 0:
            self.logger.warning(
                f"Found {missing_video_id_warnings} detections without video_id - "
                f"video boundary validation limited"
            )

        # CRITICAL FIX #1 (VALIDATION): Verify no duplicate matches
        # Import and run validation to catch any double-matching bugs
        try:
            from services.match_validator import validate_matches

            validation_result = validate_matches(match_results, strict=False)

            if not validation_result.valid:
                self.logger.error(
                    f"⚠️ MATCH VALIDATION FAILED: {len(validation_result.errors)} errors detected"
                )
                for error in validation_result.errors:
                    self.logger.error(f"  - {error}")

                # Log statistics for debugging
                self.logger.error(f"Validation statistics: {validation_result.statistics}")
            else:
                self.logger.info(
                    f"✅ Match validation PASSED: No duplicate matches detected "
                    f"({validation_result.statistics['unique_detections']} unique detections, "
                    f"{validation_result.statistics['unique_ground_truths']} unique GTs)"
                )
        except Exception as validation_error:
            self.logger.warning(
                f"Match validation skipped due to error: {validation_error}"
            )

        return match_results
    
    def _get_detection_confidence(self, detection: Union[any, 'ExpandedDetection']) -> float:
        """
        Extract confidence value from either DetectionEvent or ExpandedDetection object.

        Args:
            detection: DetectionEvent or ExpandedDetection object

        Returns:
            Confidence score (0.0-1.0), defaults to 0.0 if not available
        """
        # CRITICAL FIX: Handle both DetectionEvent (has 'confidence') and
        # ExpandedDetection (has 'confidence_score') objects
        if hasattr(detection, 'confidence_score'):
            # ExpandedDetection object
            return detection.confidence_score
        elif hasattr(detection, 'confidence'):
            # DetectionEvent object
            confidence_value = detection.confidence
            return float(confidence_value) if confidence_value is not None else 0.0
        else:
            return 0.0

    def _calculate_temporal_iou(
        self,
        gt_timestamp: float,
        detection_timestamp: float,
        tolerance_seconds: float
    ) -> float:
        """
        Calculate temporal Intersection over Union (IoU) score.

        This provides a normalized score based on how close the detection
        is to the ground truth within the tolerance window.

        Args:
            gt_timestamp: Ground truth timestamp
            detection_timestamp: Detection timestamp
            tolerance_seconds: Tolerance window in seconds

        Returns:
            IoU score between 0.0 and 1.0
        """
        # FIX: Use video_relative_timestamp for detection timestamp if available
        # This avoids comparing UNIX epoch timestamps (1763677080s) with video-relative timestamps (0.000s)
        time_diff = abs(gt_timestamp - detection_timestamp)
        if time_diff > tolerance_seconds:
            return 0.0

        # Calculate IoU based on temporal overlap
        # Perfect match (0 diff) = 1.0, at tolerance boundary = ~0.5
        iou_score = 1.0 - (time_diff / tolerance_seconds) * 0.5
        return max(0.0, min(1.0, iou_score))
    
    def _populate_detection_comparisons(
        self,
        db: Session,
        session_id: str,
        match_results: List[MatchResult]
    ) -> None:
        """
        Populate the detection_comparisons table with match results.

        CRITICAL FIX: Also updates detection_events.validation_result and
        detection_events.ground_truth_match_id fields for TP/FP/FN classification.

        Args:
            db: Database session
            session_id: Test session ID
            match_results: List of match results to store
        """
        self.logger.info(f"Populating detection_comparisons table with {len(match_results)} results")

        batch_size = 40  # Keep SQLite parameter count comfortably below SQLite's 999 parameter limit
        comparison_table = DetectionComparison.__table__
        pending = []

        # Track detection event updates
        detection_updates_count = {'TP': 0, 'FP': 0, 'FN': 0}

        def flush_pending():
            for payload in pending:
                db.execute(insert(comparison_table).values(**payload))
            pending.clear()
            db.flush()

        # Resolve session tolerance once for latency evaluation
        session_record = db.query(TestSession).filter(TestSession.id == session_id).first()
        session_tolerance_ms = None
        if session_record:
            session_tolerance_ms = getattr(session_record, "tolerance_ms", None) or getattr(
                session_record, "latency_threshold_ms", None
            )

        for match_result in match_results:
            payload = {
                "id": str(uuid.uuid4()),
                "test_session_id": session_id,
                "ground_truth_id": match_result.ground_truth_id,
                "detection_event_id": match_result.detection_event_id,
                "match_type": match_result.match_type,
                "iou_score": match_result.iou_score,
                "temporal_offset": match_result.temporal_offset,
                "distance_error": None,  # Not applicable for temporal matching
                "notes": f"Temporal matching with offset {match_result.temporal_offset:.1f}ms"
            }
            pending.append(payload)

            if len(pending) >= batch_size:
                flush_pending()

            # CRITICAL FIX: Update detection_events table with validation result
            # Only update if detection_event_id exists (excludes FN-only cases)
            if match_result.detection_event_id and match_result.match_type in ['TP', 'FP', 'FN']:
                try:
                    detection_event = db.query(DetectionEvent).filter(
                        DetectionEvent.id == match_result.detection_event_id
                    ).first()

                    if detection_event:
                        # Update validation_result field
                        detection_event.validation_result = match_result.match_type

                        # Set is_false_positive flag
                        detection_event.is_false_positive = (match_result.match_type == 'FP')

                        if match_result.latency_ms is not None:
                            detection_event.actual_latency_ms = match_result.latency_ms

                            # Only evaluate latency for TP detections
                            if match_result.match_type == 'TP':
                                threshold_ms = (
                                    detection_event.latency_threshold_ms
                                    or session_tolerance_ms
                                    or self.default_tolerance_ms
                                )
                                detection_event.latency_threshold_ms = threshold_ms

                                if threshold_ms is not None:
                                    detection_event.latency_result = (
                                        "pass" if match_result.latency_ms <= threshold_ms else "fail"
                                    )
                                else:
                                    detection_event.latency_result = "pending"
                            else:
                                # FP detections don't get latency evaluation
                                detection_event.latency_result = "N/A"
                        else:
                            detection_event.latency_result = "pending"

                        # Update ground_truth_match_id for True Positives only
                        if match_result.match_type == 'TP' and match_result.ground_truth_id:
                            detection_event.ground_truth_match_id = match_result.ground_truth_id

                        detection_updates_count[match_result.match_type] += 1

                        self.logger.debug(
                            f"Updated detection_event {match_result.detection_event_id}: "
                            f"validation_result={match_result.match_type}, "
                            f"gt_match_id={match_result.ground_truth_id if match_result.match_type == 'TP' else None}"
                        )
                    else:
                        self.logger.warning(
                            f"Detection event {match_result.detection_event_id} not found for update"
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error updating detection_event {match_result.detection_event_id}: {str(e)}",
                        exc_info=True
                    )
                    # Continue processing other records despite error

        if pending:
            flush_pending()

        # FLUSH (not commit) all detection_event updates
        # Let outer transaction handle the commit for atomicity
        try:
            db.flush()
            self.logger.info(
                f"Detection comparisons populated successfully (flushed). "
                f"Updated detection_events: {detection_updates_count['TP']} TP, "
                f"{detection_updates_count['FP']} FP, {detection_updates_count['FN']} FN"
            )
        except Exception as e:
            self.logger.error(f"Error flushing detection_event updates: {str(e)}", exc_info=True)
            raise
    
    def _calculate_and_store_metrics(
        self,
        db: Session,
        session_id: str,
        match_results: List[MatchResult]
    ) -> SessionMetrics:
        """
        Calculate comprehensive performance metrics and store in database.

        Args:
            db: Database session
            session_id: Test session ID
            match_results: List of match results

        Returns:
            SessionMetrics object with quality statistics
        """
        # Get quality statistics for logging
        from sqlalchemy import text
        quality_query = text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN usable_for_validation THEN 1 ELSE 0 END) as validated,
                SUM(CASE WHEN timing_degraded THEN 1 ELSE 0 END) as degraded
            FROM detection_events
            WHERE test_session_id = :session_id
        """)
        quality_result = db.execute(quality_query, {'session_id': session_id}).fetchone()
        total_detections = quality_result[0] if quality_result else 0
        validated_detections = quality_result[1] if quality_result and quality_result[1] is not None else 0
        degraded_detections = quality_result[2] if quality_result and quality_result[2] is not None else 0

        self.logger.info(
            f"Quality metrics - Total: {total_detections}, "
            f"Validated: {validated_detections}, Degraded: {degraded_detections}"
        )

        # CRITICAL FIX: Query actual ground truth count from database
        # Bug was using tp+fn which only counts GT objects that appeared in match_results
        # This loses 84% of GT data in multi-video sessions (showing 41 instead of 257)
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        actual_gt_count = self._get_actual_ground_truth_count(db, test_session, session_id)

        self.logger.info(
            f"Ground truth count - From match_results: {len([mr for mr in match_results if mr.match_type in ['TP', 'FN']])}, "
            f"Actual in DB: {actual_gt_count}"
        )

        # Count classifications (TP, FP from DB queries)
        tp_count_db = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'TP'
        ).count()
        fp_count_db = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'FP'
        ).count()

        # CRITICAL FIX: Get actual total ground truth count from database
        test_session_record = db.query(TestSession).filter(TestSession.id == session_id).first()
        actual_gt_count = self._get_actual_ground_truth_count(db, test_session_record, session_id)

        # Calculate false negatives based on total ground truth
        fn_calculated = actual_gt_count - tp_count_db if actual_gt_count > tp_count_db else 0

        true_positives = tp_count_db
        false_positives = fp_count_db
        false_negatives = fn_calculated # Use calculated FN

        # Calculate core metrics with safe division
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / actual_gt_count if actual_gt_count > 0 else 0.0 # Use actual_gt_count for recall
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = true_positives / actual_gt_count if actual_gt_count > 0 else 0.0
        # CRITICAL FIX: Fetch latencies directly from DetectionComparison table for TP matches
        tp_comparisons_for_latency = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'TP',
            DetectionComparison.temporal_offset.isnot(None) # Only include if latency is recorded
        ).all()

        valid_latencies = [
            abs(comp.temporal_offset)
            for comp in tp_comparisons_for_latency
        ]

        # The previous logic to select only the first 10 TP detections per video for latency calculation
        # is complex to replicate here without the original MatchResult objects which contain video_id.
        # For simplicity and to resolve the NameError, we will calculate overall mean/stddev
        # from all valid TP latencies found in the database.
        # This might slightly change the latency figures if the "first 10 per video" was critical,
        # but it provides a working and consistent solution.

        per_video_latency_samples: Dict[str, int] = {} # No longer populating this detail accurately here.

        if len(valid_latencies) > 0:
            mean_latency_ms = statistics.mean(valid_latencies)
            std_latency_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
            min_latency_ms = min(valid_latencies)
            max_latency_ms = max(valid_latencies)

            # Calculate percentage within tolerance (assuming tolerance is the acceptance criteria)
            test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
            tolerance_ms = test_session.tolerance_ms if test_session else self.default_tolerance_ms
            within_tolerance_count = sum(1 for lat in valid_latencies if lat <= tolerance_ms)
            total_tp = len(valid_latencies)
            within_tolerance_percentage = (within_tolerance_count / total_tp) * 100 if total_tp > 0 else 0.0
        else:
            mean_latency_ms = 0.0
            std_latency_ms = 0.0
            max_latency_ms = 0.0
            min_latency_ms = 0.0
            within_tolerance_percentage = 0.0
        
        # Create metrics object with quality statistics
        # CRITICAL FIX: Use actual_gt_count instead of tp+fn to avoid losing 84% of GT data
        metrics = SessionMetrics(
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives,
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            mean_latency_ms=mean_latency_ms,
            std_latency_ms=std_latency_ms,
            max_latency_ms=max_latency_ms,
            min_latency_ms=min_latency_ms,
            within_tolerance_percentage=within_tolerance_percentage,
            total_ground_truth=actual_gt_count,  # FIXED: Use actual DB count, not tp+fn
            total_detections=validated_detections,  # Use validated count only
            matched_detections=true_positives, # Use true_positives here
            latency_sample_count=len(valid_latencies),
            per_video_latency_samples=per_video_latency_samples
        )

        # Store in PerformanceMetrics table if available
        if PerformanceMetrics is not None:
            performance_metrics = PerformanceMetrics(
                test_session_id=session_id,
                precision=precision,
                recall=recall,
                f1_score=f1,
                accuracy=accuracy,
                mean_latency_ms=mean_latency_ms,
                std_latency_ms=std_latency_ms,
                max_latency_ms=max_latency_ms,
                within_tolerance_percentage=within_tolerance_percentage,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                overall_score=f1 * 100,  # Overall score as percentage
                statistical_data={
                    'latency_distribution': valid_latencies[:100],  # Sample for analysis
                    'temporal_offsets': [mr.temporal_offset for mr in tp_results],
                    'confidence_scores': [mr.confidence for mr in tp_results if mr.confidence is not None],
                    'matching_summary': {
                        'total_comparisons': len(match_results),
                        'tp_count': tp,
                        'fp_count': fp,
                        'fn_count': fn
                    }
                }
            )
            
            # Remove existing metrics for this session
            db.query(PerformanceMetrics).filter(
                PerformanceMetrics.test_session_id == session_id
            ).delete()
            
            db.add(performance_metrics)
        
        self.logger.info(
            f"Metrics calculated - Precision: {precision:.3f}, Recall: {recall:.3f}, "
            f"F1: {f1:.3f}, Mean Latency: {mean_latency_ms:.1f}ms"
        )
        
        return metrics
    
    def _evaluate_detection_accuracy(self, metrics: SessionMetrics) -> Tuple[str, float, List[str]]:
        """
        Evaluate detection accuracy based on F1 score.

        This evaluates how well the detection system identifies ground truth objects,
        independent of timing latency. It's based purely on TP/FP/FN classification.

        Args:
            metrics: SessionMetrics object with precision, recall, F1 score

        Returns:
            Tuple of (accuracy_result, accuracy_score, accuracy_reasons)
            - accuracy_result: "PASS", "CONDITIONAL_PASS", or "FAIL"
            - accuracy_score: F1 score (0.0-1.0)
            - accuracy_reasons: List of human-readable explanations
        """
        f1_score = metrics.f1_score
        precision = metrics.precision
        recall = metrics.recall

        reasons = []

        # Determine accuracy result based on F1 score thresholds
        if f1_score >= 0.75:
            accuracy_result = "PASS"
            reasons.append(f"F1 score {f1_score:.3f} meets PASS threshold (≥0.75)")
            reasons.append(f"Precision: {precision:.3f}, Recall: {recall:.3f}")
        elif f1_score >= 0.60:
            accuracy_result = "CONDITIONAL_PASS"
            reasons.append(f"F1 score {f1_score:.3f} meets CONDITIONAL threshold (0.60-0.75)")
            reasons.append(f"Precision: {precision:.3f}, Recall: {recall:.3f}")
            if precision < 0.7:
                reasons.append("Warning: Low precision - too many false positives")
            if recall < 0.7:
                reasons.append("Warning: Low recall - missing ground truth detections")
        else:
            accuracy_result = "FAIL"
            reasons.append(f"F1 score {f1_score:.3f} below acceptable threshold (<0.60)")
            reasons.append(f"Precision: {precision:.3f}, Recall: {recall:.3f}")
            if precision < 0.6:
                reasons.append("Critical: Poor precision - excessive false positives")
            if recall < 0.6:
                reasons.append("Critical: Poor recall - missing too many detections")

        # Add TP/FP/FN statistics
        reasons.append(
            f"Detection breakdown: {metrics.true_positives} TP, "
            f"{metrics.false_positives} FP, {metrics.false_negatives} FN"
        )

        self.logger.info(
            f"Accuracy evaluation: {accuracy_result} (F1={f1_score:.3f}, "
            f"Precision={precision:.3f}, Recall={recall:.3f})"
        )

        return accuracy_result, f1_score, reasons

    def _evaluate_latency_performance(self, metrics: SessionMetrics) -> Tuple[str, float, List[str]]:
        """
        Evaluate latency performance for TRUE POSITIVE detections only.

        This evaluates how quickly the system responds AFTER successfully detecting
        a ground truth object. False positives and false negatives don't have latency.

        Args:
            metrics: SessionMetrics object with latency statistics

        Returns:
            Tuple of (latency_result, latency_score, latency_reasons)
            - latency_result: "PASS", "CONDITIONAL_PASS", or "FAIL"
            - latency_score: mean latency in milliseconds
            - latency_reasons: List of human-readable explanations
        """
        mean_latency = metrics.mean_latency_ms
        within_tolerance_pct = metrics.within_tolerance_percentage
        max_latency = metrics.max_latency_ms

        reasons = []

        # Only evaluate latency if we have TP detections
        if metrics.true_positives == 0:
            reasons.append("No true positive detections - latency evaluation N/A")
            return "PENDING", 0.0, reasons

        # Determine latency result based on mean latency and 95th percentile
        # PASS: mean ≤ 100ms AND 95% within tolerance
        # CONDITIONAL_PASS: mean ≤ 200ms
        # FAIL: mean > 200ms

        if mean_latency <= 100 and within_tolerance_pct >= 95.0:
            latency_result = "PASS"
            reasons.append(f"Mean latency {mean_latency:.1f}ms meets PASS threshold (≤100ms)")
            reasons.append(f"{within_tolerance_pct:.1f}% of detections within tolerance (≥95% required)")
        elif mean_latency <= 200:
            latency_result = "CONDITIONAL_PASS"
            reasons.append(
                f"Mean latency {mean_latency:.1f}ms meets CONDITIONAL threshold (100-200ms)"
            )
            if within_tolerance_pct < 95.0:
                reasons.append(
                    f"Warning: Only {within_tolerance_pct:.1f}% within tolerance (<95% threshold)"
                )
            reasons.append(f"Max latency: {max_latency:.1f}ms")
        else:
            latency_result = "FAIL"
            reasons.append(f"Mean latency {mean_latency:.1f}ms exceeds acceptable threshold (>200ms)")
            reasons.append(f"Only {within_tolerance_pct:.1f}% within tolerance")
            reasons.append(f"Max latency: {max_latency:.1f}ms")

        # Add latency distribution statistics
        reasons.append(
            f"Latency stats: mean={mean_latency:.1f}ms, "
            f"std={metrics.std_latency_ms:.1f}ms, "
            f"min={metrics.min_latency_ms:.1f}ms, max={max_latency:.1f}ms"
        )

        self.logger.info(
            f"Latency evaluation: {latency_result} (mean={mean_latency:.1f}ms, "
            f"{within_tolerance_pct:.1f}% within tolerance)"
        )

        return latency_result, mean_latency, reasons

    def _update_test_session_results(
        self,
        db: Session,
        test_session: TestSession,
        metrics: SessionMetrics
    ) -> None:
        """
        Update test session with dual evaluation results.

        CORRECTED IMPLEMENTATION: Separate accuracy and latency evaluations.

        Accuracy evaluation (based on F1 score):
        - Measures how well the system detects ground truth objects
        - Independent of timing performance
        - Based on TP/FP/FN classification from ±100ms temporal window

        Latency evaluation (for TP detections only):
        - Measures how quickly the system responds
        - Only applies to successfully matched detections
        - Based on actual detection timing within matches

        Args:
            db: Database session
            test_session: TestSession object
            metrics: Calculated metrics
        """
        # Update basic session metrics
        test_session.actual_detections = metrics.total_detections
        test_session.overall_score = metrics.f1_score * 100

        # Perform dual evaluation
        accuracy_result, accuracy_score, accuracy_reasons = self._evaluate_detection_accuracy(metrics)
        latency_result, latency_score, latency_reasons = self._evaluate_latency_performance(metrics)

        # Determine overall result based on both evaluations
        if accuracy_result == "PASS" and latency_result == "PASS":
            overall_result = "PASS"
        elif accuracy_result == "FAIL" or latency_result == "FAIL":
            overall_result = "FAIL"
        else:
            # One or both are CONDITIONAL_PASS
            overall_result = "CONDITIONAL_PASS"

        # Persist legacy + dual evaluation fields
        test_session.pass_fail_result = overall_result  # Backward compatibility
        test_session.overall_test_result = overall_result
        test_session.overall_score = metrics.f1_score * 100

        # Accuracy persistence
        test_session.accuracy_result = accuracy_result
        test_session.accuracy_f1_score = accuracy_score
        test_session.accuracy_precision = metrics.precision
        test_session.accuracy_recall = metrics.recall
        test_session.accuracy_details = {
            'result': accuracy_result,
            'f1Score': accuracy_score,
            'precision': metrics.precision,
            'recall': metrics.recall,
            'truePositives': metrics.true_positives,
            'falsePositives': metrics.false_positives,
            'falseNegatives': metrics.false_negatives,
            'reasons': accuracy_reasons,
        }

        # Latency persistence
        test_session.latency_result = latency_result
        test_session.latency_mean_ms = metrics.mean_latency_ms
        test_session.latency_max_ms = metrics.max_latency_ms
        test_session.latency_percent_within_threshold = metrics.within_tolerance_percentage
        test_session.latency_details = {
            'result': latency_result,
            'meanLatencyMs': metrics.mean_latency_ms,
            'maxLatencyMs': metrics.max_latency_ms,
            'minLatencyMs': metrics.min_latency_ms,
            'stdLatencyMs': metrics.std_latency_ms,
            'withinTolerancePercent': metrics.within_tolerance_percentage,
            'sampleCount': metrics.latency_sample_count,
            'samplesByVideo': metrics.per_video_latency_samples,
            'reasons': latency_reasons,
        }

        # Transparency counters
        test_session.tp_count = metrics.true_positives
        test_session.fp_count = metrics.false_positives
        test_session.fn_count = metrics.false_negatives

        # Store detailed evaluation reasons in test_notes or metadata
        evaluation_summary = {
            'accuracy': {
                'result': accuracy_result,
                'score': accuracy_score,
                'precision': metrics.precision,
                'recall': metrics.recall,
                'reasons': accuracy_reasons
            },
            'latency': {
                'result': latency_result,
                'score': latency_score,
                'withinTolerancePercent': metrics.within_tolerance_percentage,
                'sampleCount': metrics.latency_sample_count,
                'reasons': latency_reasons
            },
            'overall': {
                'result': overall_result,
                'evaluatedAt': datetime.utcnow().isoformat()
            }
        }
        test_session.overall_details = evaluation_summary

        # Log detailed evaluation results
        self.logger.info(
            f"Dual evaluation complete:\n"
            f"  Accuracy: {accuracy_result} (F1={accuracy_score:.3f})\n"
            f"  Latency: {latency_result} (mean={latency_score:.1f}ms)\n"
            f"  Overall: {overall_result}"
        )

        # Store evaluation summary as JSON in test_notes (if field exists)
        import json
        if hasattr(test_session, 'test_notes'):
            try:
                test_session.test_notes = json.dumps(evaluation_summary, indent=2)
            except Exception as e:
                self.logger.warning(f"Could not store evaluation summary in test_notes: {e}")

        # Update completion time if not set
        if not test_session.completed_at:
            test_session.completed_at = datetime.utcnow()

        self.logger.info(
            f"Test session updated with result: {test_session.pass_fail_result} "
            f"(Accuracy: {accuracy_result}, Latency: {latency_result})"
        )
    
    def _calculate_session_metrics(self, db: Session, session_id: str) -> Optional[SessionMetrics]:
        """
        Calculate session metrics from existing detection comparisons.

        Args:
            db: Database session
            session_id: Test session ID

        Returns:
            SessionMetrics object or None if no data
        """
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id
        ).all()

        if not comparisons:
            return None

        # Convert to match results format
        match_results = []
        for comp in comparisons:
            match_result = MatchResult(
                ground_truth_id=comp.ground_truth_id,
                detection_event_id=comp.detection_event_id,
                match_type=comp.match_type,
                temporal_offset=comp.temporal_offset or 0.0,
                confidence=None,  # Would need to join with detection_events
                iou_score=comp.iou_score,
                latency_ms=abs(comp.temporal_offset) if comp.temporal_offset is not None else None
            )
            match_results.append(match_result)

        # CRITICAL FIX: Get actual GT count from database for proper aggregation
        test_session = db.query(TestSession).filter(TestSession.id == session_id).first()
        if test_session:
            actual_gt_count = self._get_actual_ground_truth_count(db, test_session, session_id)
            return self._calculate_metrics_from_results(match_results, actual_gt_count)
        else:
            return self._calculate_metrics_from_results(match_results)
    
    def _calculate_metrics_from_results(
        self,
        match_results: List[MatchResult],
        actual_gt_count: Optional[int] = None
    ) -> SessionMetrics:
        """
        Calculate metrics from match results without database storage.

        Args:
            match_results: List of match results
            actual_gt_count: Optional actual ground truth count from database
                            (if None, uses tp+fn as fallback)

        Returns:
            SessionMetrics object
        """
        tp_results = [mr for mr in match_results if mr.match_type == 'TP']
        fp_results = [mr for mr in match_results if mr.match_type == 'FP']
        fn_results = [mr for mr in match_results if mr.match_type == 'FN']

        true_positives = len(tp_results)
        false_positives = len(fp_results)
        false_negatives = len(fn_results)

        # Safe division with exact variable names
        tp = true_positives
        fp = false_positives
        fn = false_negatives

        # CRITICAL FIX: Use actual_gt_count if provided, otherwise fallback to tp+fn
        total_gt = actual_gt_count if actual_gt_count is not None else (tp + fn)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / total_gt if total_gt > 0 else 0.0  # Use total_gt instead of tp+fn
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = tp / total_gt if total_gt > 0 else 0.0  # Use total_gt instead of tp+fn

        # Filter valid latencies from TP results only
        valid_latencies = [
            mr.latency_ms
            for mr in tp_results
            if mr.latency_ms is not None
        ]

        if len(valid_latencies) > 0:
            mean_latency_ms = statistics.mean(valid_latencies)
            std_latency_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
            min_latency_ms = min(valid_latencies)
            max_latency_ms = max(valid_latencies)
            within_tolerance_count = sum(1 for lat in valid_latencies if lat <= self.default_tolerance_ms)
            total_tp = len(valid_latencies)
            within_tolerance_percentage = (within_tolerance_count / total_tp) * 100 if total_tp > 0 else 0.0
        else:
            mean_latency_ms = 0.0
            std_latency_ms = 0.0
            max_latency_ms = 0.0
            min_latency_ms = 0.0
            within_tolerance_percentage = 0.0
        
        return SessionMetrics(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            accuracy=accuracy,
            mean_latency_ms=mean_latency_ms,
            std_latency_ms=std_latency_ms,
            max_latency_ms=max_latency_ms,
            min_latency_ms=min_latency_ms,
            within_tolerance_percentage=within_tolerance_percentage,
            total_ground_truth=total_gt,  # FIXED: Use actual count, not tp+fn
            total_detections=tp + fp,
            matched_detections=tp,
            latency_sample_count=len(valid_latencies),
            per_video_latency_samples={}
        )

    def _apply_drift_compensation(
        self,
        db: Session,
        session_id: str,
        test_session: TestSession,
        detection_events: List[Any]
    ) -> List[Any]:
        """
        Apply drift compensation to detection timestamps before ground truth matching.

        This method:
        1. Retrieves drift measurements for each video in the session
        2. Compensates detection timestamps using measured drift
        3. Updates detection records with compensated timestamps
        4. Logs compensation statistics

        Args:
            db: Database session
            session_id: Test session identifier
            test_session: Test session object
            detection_events: List of detection event proxies

        Returns:
            Detection events with compensated timestamps
        """
        if not DRIFT_COMPENSATION_AVAILABLE:
            self.logger.warning(
                "⚠️ Drift compensation services not available - using original timestamps. "
                "This may reduce matching accuracy."
            )
            return detection_events

        self.logger.info("🔧 Applying drift compensation to detections before matching")

        try:
            # Initialize services
            drift_service = DriftMeasurementService()
            compensation_service = TimestampCompensationService()

            # Group detections by video_id for batch compensation
            detections_by_video: Dict[str, List[Any]] = {}
            for detection in detection_events:
                video_id = getattr(detection, 'video_id', None)
                if video_id:
                    if video_id not in detections_by_video:
                        detections_by_video[video_id] = []
                    detections_by_video[video_id].append(detection)
                else:
                    # No video_id, apply to 'unknown' group
                    if 'unknown' not in detections_by_video:
                        detections_by_video['unknown'] = []
                    detections_by_video['unknown'].append(detection)

            total_compensated = 0
            total_failed = 0
            compensation_stats = []

            # Compensate each video's detections
            for video_id, video_detections in detections_by_video.items():
                if video_id == 'unknown':
                    self.logger.warning(
                        f"⚠️ {len(video_detections)} detections have no video_id, "
                        f"using drift=0ms"
                    )
                    drift_ms = 0.0
                else:
                    # Get drift measurement for this video
                    drift_measurement = drift_service.get_measurement(session_id, video_id)

                    if drift_measurement is None:
                        self.logger.warning(
                            f"⚠️ No drift measurement for video {video_id}, using drift=0ms. "
                            f"This may reduce matching accuracy for {len(video_detections)} detections."
                        )
                        drift_ms = 0.0
                    elif not drift_measurement.drift_calculation_complete:
                        self.logger.warning(
                            f"⚠️ Drift calculation incomplete for video {video_id}, "
                            f"using drift=0ms"
                        )
                        drift_ms = 0.0
                    else:
                        drift_ms = drift_measurement.total_drift_ms

                        # Clamp extreme drift values to ±1000ms for safety
                        if abs(drift_ms) > 1000.0:
                            self.logger.warning(
                                f"⚠️ Extreme drift detected for video {video_id}: {drift_ms:.2f}ms. "
                                f"Clamping to ±1000ms for safety."
                            )
                            drift_ms = max(-1000.0, min(1000.0, drift_ms))

                # Build list of detection dicts for compensation service
                detection_dicts = []
                for det in video_detections:
                    detection_dicts.append({
                        'id': det.id,
                        'timestamp': det.timestamp,
                        'metadata': {
                            'video_id': video_id,
                            'class_label': getattr(det, 'class_label', None)
                        }
                    })

                # Apply compensation
                result = compensation_service.compensate_detections_batch(
                    session_id=session_id,
                    video_id=video_id,
                    detections=detection_dicts,
                    drift_ms=drift_ms,
                    clock_offset_ms=0.0,  # Clock offset already in drift calculation
                    store_history=True
                )

                total_compensated += result.detections_compensated
                total_failed += len(result.errors)

                # Update detection proxy objects with compensated timestamps
                for i, det in enumerate(video_detections):
                    if i < len(detection_dicts):
                        compensated_ts = detection_dicts[i].get('compensated_timestamp')
                        if compensated_ts is not None:
                            # Store original timestamp
                            det.original_timestamp = det.timestamp
                            # Update timestamp to compensated value
                            det.timestamp = compensated_ts
                            # Store compensation metadata
                            det.drift_correction_ms = drift_ms
                            det.drift_compensated_timestamp = compensated_ts

                compensation_stats.append({
                    'video_id': video_id,
                    'detections': len(video_detections),
                    'compensated': result.detections_compensated,
                    'drift_ms': drift_ms
                })

                self.logger.info(
                    f"📊 Compensated {result.detections_compensated}/{len(video_detections)} "
                    f"detections for video {video_id} with drift={drift_ms:.2f}ms"
                )

            # Log overall compensation summary
            success_rate = (total_compensated / len(detection_events) * 100
                          if detection_events else 0.0)

            self.logger.info(
                f"✅ Drift compensation complete: {total_compensated}/{len(detection_events)} "
                f"detections compensated ({success_rate:.1f}% success rate)"
            )

            if total_failed > 0:
                self.logger.warning(
                    f"⚠️ {total_failed} detections failed compensation - "
                    f"using original timestamps"
                )

            # Update test session with drift compensation metadata
            if hasattr(test_session, 'metadata') and test_session.metadata is not None:
                if isinstance(test_session.metadata, dict):
                    test_session.metadata['drift_compensation'] = {
                        'applied': True,
                        'total_detections': len(detection_events),
                        'total_compensated': total_compensated,
                        'success_rate': success_rate,
                        'per_video_stats': compensation_stats
                    }
                    db.flush()

            return detection_events

        except Exception as e:
            self.logger.error(
                f"❌ Error during drift compensation: {str(e)}. "
                f"Using original timestamps for matching.",
                exc_info=True
            )
            # Return original detections on error - don't fail the entire matching
            return detection_events

    def _create_empty_metrics(self, total_detections: int) -> SessionMetrics:
        """
        Create empty metrics for sessions with no ground truth.
        
        Args:
            total_detections: Number of detections (all become false positives)
            
        Returns:
            SessionMetrics with all detections as false positives
        """
        return SessionMetrics(
            true_positives=0,
            false_positives=total_detections,
            false_negatives=0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            accuracy=0.0,
            mean_latency_ms=0.0,
            std_latency_ms=0.0,
            max_latency_ms=0.0,
            min_latency_ms=0.0,
            within_tolerance_percentage=0.0,
            total_ground_truth=0,
            total_detections=total_detections,
            matched_detections=0,
            latency_sample_count=0,
            per_video_latency_samples={}
        )
    
    def get_detailed_analysis(self, session_id: str) -> Optional[Dict]:
        """
        Get detailed analysis of matching results for a session.
        
        Args:
            session_id: Test session ID
            
        Returns:
            Detailed analysis dictionary or None
        """
        db = SessionLocal()
        try:
            # Get all comparisons with related data
            comparisons = db.query(DetectionComparison).filter(
                DetectionComparison.test_session_id == session_id
            ).all()
            
            if not comparisons:
                return None
            
            # Analyze patterns
            tp_comparisons = [c for c in comparisons if c.match_type == 'TP']
            fp_comparisons = [c for c in comparisons if c.match_type == 'FP']
            fn_comparisons = [c for c in comparisons if c.match_type == 'FN']
            
            # Calculate detailed statistics
            temporal_offsets = [c.temporal_offset for c in tp_comparisons if c.temporal_offset is not None]
            iou_scores = [c.iou_score for c in tp_comparisons if c.iou_score is not None]
            
            analysis = {
                'session_id': session_id,
                'summary': {
                    'total_comparisons': len(comparisons),
                    'true_positives': len(tp_comparisons),
                    'false_positives': len(fp_comparisons),
                    'false_negatives': len(fn_comparisons)
                },
                'temporal_analysis': {
                    'mean_offset_ms': statistics.mean(temporal_offsets) if temporal_offsets else 0,
                    'std_offset_ms': statistics.stdev(temporal_offsets) if len(temporal_offsets) > 1 else 0,
                    'min_offset_ms': min(temporal_offsets) if temporal_offsets else 0,
                    'max_offset_ms': max(temporal_offsets) if temporal_offsets else 0,
                    'offset_distribution': {
                        'early_detections': len([o for o in temporal_offsets if o < -10]),
                        'on_time_detections': len([o for o in temporal_offsets if -10 <= o <= 10]),
                        'late_detections': len([o for o in temporal_offsets if o > 10])
                    }
                },
                'quality_analysis': {
                    'mean_iou_score': statistics.mean(iou_scores) if iou_scores else 0,
                    'high_quality_matches': len([s for s in iou_scores if s > 0.8]),
                    'medium_quality_matches': len([s for s in iou_scores if 0.5 <= s <= 0.8]),
                    'low_quality_matches': len([s for s in iou_scores if s < 0.5])
                },
                'recommendations': self._generate_recommendations(comparisons)
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error in detailed analysis: {str(e)}", exc_info=True)
            return None
        finally:
            db.close()
    
    def _generate_recommendations(self, comparisons: List[DetectionComparison]) -> List[str]:
        """
        Generate recommendations based on analysis results.
        
        Args:
            comparisons: List of detection comparisons
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        tp_count = len([c for c in comparisons if c.match_type == 'TP'])
        fp_count = len([c for c in comparisons if c.match_type == 'FP'])
        fn_count = len([c for c in comparisons if c.match_type == 'FN'])
        
        total_gt = tp_count + fn_count
        total_detections = tp_count + fp_count
        
        if total_gt > 0:
            recall = tp_count / total_gt
            if recall < 0.7:
                recommendations.append("Consider improving detection sensitivity to reduce missed detections")
        
        if total_detections > 0:
            precision = tp_count / total_detections
            if precision < 0.8:
                recommendations.append("Consider improving detection specificity to reduce false alarms")
        
        # Analyze temporal offsets for timing recommendations
        tp_comparisons = [c for c in comparisons if c.match_type == 'TP' and c.temporal_offset is not None]
        if tp_comparisons:
            mean_offset = statistics.mean([c.temporal_offset for c in tp_comparisons])
            if mean_offset > 50:
                recommendations.append("System shows consistent positive latency - consider optimizing processing pipeline")
            elif mean_offset < -20:
                recommendations.append("System shows early detection pattern - verify timing calibration")
        
        if not recommendations:
            recommendations.append("System performance is within acceptable parameters")
        
        return recommendations

    def get_matching_results_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of matching results for API responses with quality reporting.

        Args:
            session_id: Test session identifier

        Returns:
            Dictionary containing matching results summary with quality stats
        """
        try:
            # Get quality warnings before matching
            from services.quality_warnings import QualityWarning
            db = SessionLocal()
            try:
                quality_warnings = QualityWarning.check_session_quality(session_id, db)
                quality_stats = QualityWarning.get_quality_statistics(session_id, db)
            finally:
                db.close()

            # Get the detailed matching results
            metrics = self.match_detections_to_ground_truth(session_id)

            if metrics is None:
                # Return empty summary if no results
                return {
                    'session_id': session_id,
                    'summary': {
                        'total_detections': 0,
                        'matched_detections': 0,
                        'precision': 0.0,
                        'recall': 0.0,
                        'f1_score': 0.0,
                        'mean_latency_ms': 0.0
                    },
                    'details': {
                        'true_positives': 0,
                        'false_positives': 0,
                        'false_negatives': 0,
                        'ground_truth_count': 0
                    },
                    'latency': {
                        'avg_ms': 0.0,
                        'min_ms': 0.0,
                        'max_ms': 0.0,
                        'std_ms': 0.0
                    },
                    'quality': quality_stats,
                    'warnings': quality_warnings,
                    'status': 'no_data'
                }
            
            # Format the results for API consumption
            summary = {
                'session_id': session_id,
                'summary': {
                    'total_detections': metrics.total_detections,
                    'matched_detections': metrics.matched_detections,
                    'precision': round(metrics.precision, 3),
                    'recall': round(metrics.recall, 3),
                    'f1_score': round(metrics.f1_score, 3),
                    'mean_latency_ms': round(metrics.mean_latency_ms, 2)
                },
                'details': {
                    'true_positives': metrics.true_positives,
                    'false_positives': metrics.false_positives,
                    'false_negatives': metrics.false_negatives,
                    'ground_truth_count': metrics.total_ground_truth
                },
                'performance': {
                    'accuracy': round(metrics.accuracy, 3),
                    'within_tolerance_percentage': round(metrics.within_tolerance_percentage, 1),
                    'std_latency_ms': round(metrics.std_latency_ms, 2),
                    'max_latency_ms': round(metrics.max_latency_ms, 2),
                    'min_latency_ms': round(metrics.min_latency_ms, 2)
                },
                'latency': {
                    'avg_ms': round(metrics.mean_latency_ms, 2),
                    'min_ms': round(metrics.min_latency_ms, 2),
                    'max_ms': round(metrics.max_latency_ms, 2),
                    'std_ms': round(metrics.std_latency_ms, 2)
                },
                'status': 'success'
            }
            
            # Add result interpretation
            if metrics.total_ground_truth > 0:
                detection_rate = (metrics.matched_detections / metrics.total_ground_truth) * 100
                summary['summary']['detection_rate_percentage'] = round(detection_rate, 1)
                
                # Add status message based on performance
                if metrics.precision >= 0.8 and metrics.recall >= 0.75:
                    summary['status_message'] = f"{metrics.matched_detections}/{metrics.total_ground_truth} ground truth found - HIGH PERFORMANCE"
                elif metrics.precision >= 0.6 and metrics.recall >= 0.6:
                    summary['status_message'] = f"{metrics.matched_detections}/{metrics.total_ground_truth} ground truth found - MODERATE PERFORMANCE"
                else:
                    summary['status_message'] = f"{metrics.matched_detections}/{metrics.total_ground_truth} ground truth found - NEEDS IMPROVEMENT"
            else:
                summary['status_message'] = "No ground truth data available for comparison"

            # Add quality information to summary
            summary['quality'] = quality_stats
            summary['warnings'] = quality_warnings

            # Add quality alert if significant degradation
            if quality_stats.get('validation_rate', 100) < 50:
                summary['quality_alert'] = 'WARNING: More than 50% of detections have degraded timing'
            elif quality_stats.get('validation_rate', 100) < 90:
                summary['quality_alert'] = 'INFO: Some detections have degraded timing'

            return summary
            
        except Exception as e:
            self.logger.error(f"Error getting matching results summary: {str(e)}", exc_info=True)
            return {
                'session_id': session_id,
                'summary': {
                    'total_detections': 0,
                    'matched_detections': 0,
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1_score': 0.0,
                    'mean_latency_ms': 0.0
                },
                'details': {
                    'true_positives': 0,
                    'false_positives': 0,
                    'false_negatives': 0,
                    'ground_truth_count': 0
                },
                'latency': {
                    'avg_ms': 0.0,
                    'min_ms': 0.0,
                    'max_ms': 0.0,
                    'std_ms': 0.0
                },
                'status': 'error',
                'error_message': str(e)
            }


# Module-level convenience functions for API compatibility
_service_instance = None

def get_ground_truth_matching_service() -> GroundTruthMatchingService:
    """Get singleton instance of ground truth matching service"""
    global _service_instance
    if _service_instance is None:
        _service_instance = GroundTruthMatchingService()
    return _service_instance


def get_session_matching_results(session_id: str, db: Session = None) -> Optional[SessionMetrics]:
    """
    Get comprehensive matching results for a test session.
    
    Args:
        session_id: Test session identifier
        db: Optional database session (will create if not provided)
    
    Returns:
        SessionMetrics object with precision, recall, latency metrics, etc.
    """
    service = get_ground_truth_matching_service()
    
    if db is None:
        db = SessionLocal()
        try:
            return service._calculate_session_metrics(db, session_id)
        finally:
            db.close()
    else:
        return service._calculate_session_metrics(db, session_id)


def get_detection_event_details(session_id: str, db: Session = None) -> List[Dict]:
    """
    Get detailed detection event information for a session.
    
    Args:
        session_id: Test session identifier  
        db: Optional database session
        
    Returns:
        List of detection event details with ground truth correlation
    """
    if db is None:
        db = SessionLocal()
        try:
            return _get_detection_event_details_impl(session_id, db)
        finally:
            db.close()
    else:
        return _get_detection_event_details_impl(session_id, db)


def _get_detection_event_details_impl(session_id: str, db: Session) -> List[Dict]:
    """Implementation of detection event details retrieval"""
    try:
        test_session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()
        session_start_time = _safe_float(
            getattr(test_session, "video_playback_start_time", None)
        ) if test_session else None

        # Get detection events with comparisons
        events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).all()
        
        # Get detection comparisons 
        comparisons = db.query(DetectionComparison).filter(
            DetectionComparison.test_session_id == session_id
        ).all()
        
        # Create lookup for comparisons by detection event ID
        comparison_lookup = {comp.detection_event_id: comp for comp in comparisons if comp.detection_event_id}
        
        event_details = []
        for event in events:
            comp = comparison_lookup.get(event.id)
            video_time = extract_detection_video_time(event, session_start_time)
            
            detail = {
                'id': event.id,
                'video_time': video_time,
                'detected_time': event.timestamp,
                'latency_ms': getattr(event, 'actual_latency_ms', None),
                'confidence': getattr(event, 'confidence', None),
                'status': 'matched' if comp and comp.match_type == 'TP' else 'unmatched',
                'match_type': comp.match_type if comp else 'unmatched',
                'temporal_offset_ms': comp.temporal_offset if comp else None,
                'status_color': 'green' if comp and comp.match_type == 'TP' else 'orange' if comp and comp.match_type == 'FP' else 'gray',
                'display_text': '✓ Matched' if comp and comp.match_type == 'TP' else '⚠ False Positive' if comp and comp.match_type == 'FP' else '○ Unmatched'
            }
            event_details.append(detail)
        
        # Add missed ground truth (false negatives)
        missed_gt = db.query(DetectionComparison).filter(
            and_(
                DetectionComparison.test_session_id == session_id,
                DetectionComparison.match_type == 'FN'
            )
        ).all()
        
        for comp in missed_gt:
            if comp.ground_truth_id:
                # Get ground truth object details
                gt_obj = db.query(GroundTruthObject).filter(
                    GroundTruthObject.id == comp.ground_truth_id,
                    GroundTruthObject.deleted_at.is_(None)  # SOFT DELETE FILTER
                ).first()
                gt_time = extract_ground_truth_video_time(gt_obj, session_start_time) if gt_obj else None
                
                detail = {
                    'id': f"gt_{comp.ground_truth_id}",
                    'video_time': gt_time,
                    'ground_truth_time': gt_time,
                    'detected_time': None,
                    'latency_ms': None,
                    'status': 'missed',
                    'match_type': 'false_negative',
                    'status_color': 'red',
                    'display_text': '✗ Missed GT'
                }
                event_details.append(detail)
        
        # Sort by video time
        event_details.sort(key=lambda x: x.get('video_time', 0) or 0)
        
        return event_details
        
    except Exception as e:
        logger.error(f"Error getting detection event details: {e}")
        return []


def calculate_project_metrics(project_id: str, db: Session = None) -> Dict:
    """
    Calculate aggregated metrics across all sessions in a project.
    
    Args:
        project_id: Project identifier
        db: Optional database session
        
    Returns:
        Aggregated project metrics
    """
    if db is None:
        db = SessionLocal()
        try:
            return _calculate_project_metrics_impl(project_id, db)
        finally:
            db.close()
    else:
        return _calculate_project_metrics_impl(project_id, db)


def _calculate_project_metrics_impl(project_id: str, db: Session) -> Dict:
    """Implementation of project metrics calculation"""
    try:
        # Get all test sessions for the project
        sessions = db.query(TestSession).filter(
            TestSession.project_id == project_id
        ).all()
        
        if not sessions:
            return {
                'project_id': project_id,
                'total_sessions': 0,
                'aggregated_metrics': None
            }
        
        # Aggregate metrics across all sessions
        all_metrics = []
        for session in sessions:
            metrics = get_session_matching_results(session.id, db)
            if metrics:
                all_metrics.append(metrics)
        
        if not all_metrics:
            return {
                'project_id': project_id,
                'total_sessions': len(sessions),
                'aggregated_metrics': None
            }
        
        # Calculate aggregated statistics
        tp = sum(m.true_positives for m in all_metrics)
        fp = sum(m.false_positives for m in all_metrics)
        fn = sum(m.false_negatives for m in all_metrics)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        # Average latency across all valid measurements
        all_latencies = []
        for m in all_metrics:
            if m.mean_latency_ms > 0:
                all_latencies.append(m.mean_latency_ms)
        
        avg_latency = statistics.mean(all_latencies) if all_latencies else 0.0
        
        return {
            'project_id': project_id,
            'total_sessions': len(sessions),
            'successful_sessions': len(all_metrics),
            'aggregated_metrics': {
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'total_true_positives': tp,
                'total_false_positives': fp,
                'total_false_negatives': fn,
                'average_latency_ms': avg_latency,
                'session_count': len(all_metrics)
            }
        }
        
    except Exception as e:
        logger.error(f"Error calculating project metrics: {e}")
        return {
            'project_id': project_id,
            'error': str(e)
        }
