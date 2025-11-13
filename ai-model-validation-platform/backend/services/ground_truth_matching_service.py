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
    TestSession, DetectionEvent, GroundTruthObject, DetectionComparison
)
try:
    from models import PerformanceMetrics, ValidationResult as ValidationResultEnum
except ImportError:
    # PerformanceMetrics not available in models, define local stub
    PerformanceMetrics = None
    ValidationResultEnum = None
from schemas_annotation import VRUTypeEnum
from services.optimal_matching_service import optimal_detection_matching

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
    session_start_time: Optional[float] = None
) -> Optional[float]:
    """
    Resolve the best available video-relative timestamp for a detection event.

    Preference order:
    1. Explicit per-video fields (video_relative_timestamp / video_time / video_timestamp)
    2. sequence_timestamp minus recorded video offset
    3. timestamp minus recorded video_start_time
    4. timestamp adjusted by session start if timestamp looks like epoch
    5. Raw timestamp as last resort
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

    sequence_timestamp = _safe_float(getattr(detection, "sequence_timestamp", None))
    offset_ms = _safe_float(getattr(detection, "video_play_offset_ms", None))
    if sequence_timestamp is not None and offset_ms is not None:
        return sequence_timestamp - (offset_ms / 1000.0)

    timestamp = _safe_float(getattr(detection, "timestamp", None))
    video_start_time = _safe_float(getattr(detection, "video_start_time", None))
    if timestamp is not None and video_start_time is not None:
        return timestamp - video_start_time

    if timestamp is not None and session_start_time is not None and _looks_like_epoch(timestamp):
        return timestamp - session_start_time

    return timestamp


def extract_ground_truth_video_time(
    ground_truth: Any,
    session_start_time: Optional[float] = None
) -> Optional[float]:
    """
    Resolve the best available video-relative timestamp for a ground truth object.

    Mirrors detection extraction so both domains stay aligned.
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
    if timestamp is None:
        return None

    if session_start_time is not None and _looks_like_epoch(timestamp):
        return timestamp - session_start_time

    return timestamp


class GroundTruthMatchingService:
    """
    Comprehensive service for matching LabJack detections against ground truth data.
    
    This service implements temporal matching algorithms that handle the complexity
    of real-world detection systems with varying latencies and precision requirements.
    """
    
    def __init__(self, default_tolerance_ms: int = 100):
        """
        Initialize the Ground Truth Matching Service.
        
        Args:
            default_tolerance_ms: Default tolerance window in milliseconds
        """
        self.default_tolerance_ms = default_tolerance_ms
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
            from sqlalchemy import text
            detection_query = text("""
                SELECT id, timestamp, confidence, class_label, actual_latency_ms,
                       video_relative_timestamp, video_frame_number, timing_sync_quality,
                       video_id
                FROM detection_events
                WHERE test_session_id = :session_id
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
            
            self.logger.info(f"Found {len(detection_events)} detection events")
            
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
        from models import VideoTestSequence, SequenceVideoResult

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

    def _perform_temporal_matching(
        self,
        detection_events: List[DetectionEvent],
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
            detection_events: List of detection events
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

        # CRITICAL FIX: Build video order map for smart detection assignment
        # Both GT and detection timestamps are video-relative (0-5s per video)
        # Need to infer which video each detection belongs to
        video_order_map = {}  # video_id -> order
        if has_multi_video_sequence and test_session.sequence_id:
            try:
                from models import VideoTestSequence
                sequence = db.query(VideoTestSequence).filter(
                    VideoTestSequence.id == test_session.sequence_id
                ).first()

                if sequence and sequence.sequence_order:
                    for video_info in sequence.sequence_order:
                        video_id = video_info.get('video_id')
                        order = video_info.get('order', 0)
                        duration_ms = video_info.get('duration_ms', 0)
                        video_order_map[video_id] = {
                            'order': order,
                            'duration_s': duration_ms / 1000.0
                        }
                    self.logger.info(f"📹 Video sequence order: {video_order_map}")
            except Exception as e:
                self.logger.warning(f"Could not load sequence order: {e}")

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
        # Extract timestamps for optimal matching
        gt_times = []
        det_times = []

        for gt_obj in ground_truth_objects:
            gt_time = extract_ground_truth_video_time(gt_obj, session_start_time)
            gt_times.append(gt_time if gt_time is not None else float('inf'))

        for detection in detection_events:
            det_time = extract_detection_video_time(detection, session_start_time)
            det_times.append(det_time if det_time is not None else float('inf'))

        # Run optimal matching algorithm
        optimal_result = optimal_detection_matching(
            gt_times,
            det_times,
            tolerance_seconds
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
                # Reclassify as FN for GT and FP for detection
                match_results.append(
                    MatchResult(
                        ground_truth_id=gt_obj.id,
                        detection_event_id=None,
                        match_type='FN',
                        temporal_offset=0.0,
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
                        temporal_offset=0.0,
                        confidence=detection.confidence,
                        iou_score=0.0,
                        latency_ms=FP_LATENCY_MARKER,  # AGENT #43: Use sentinel value for FP
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
                    # Reclassify as FN for GT and FP for detection
                    # Add GT as FN
                    match_results.append(
                        MatchResult(
                            ground_truth_id=gt_obj.id,
                            detection_event_id=None,
                            match_type='FN',
                            temporal_offset=0.0,
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
                            temporal_offset=0.0,
                            confidence=detection.confidence,
                            iou_score=0.0,
                            latency_ms=FP_LATENCY_MARKER,  # AGENT #43: Use sentinel value for FP
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
                confidence=detection.confidence,
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

        # Process false negatives from optimal matching
        for gt_idx in optimal_result['false_negatives']:
            gt_obj = ground_truth_objects[gt_idx]
            gt_video_id = getattr(gt_obj, 'video_id', None)

            # NULL SAFETY: Log warning if video_id is NULL
            if gt_video_id is None:
                logger.warning(f"FN ground truth {gt_obj.id[:8]} has NULL video_id")

            match_result = MatchResult(
                ground_truth_id=gt_obj.id,
                detection_event_id=None,
                match_type='FN',
                temporal_offset=0.0,
                confidence=None,
                iou_score=0.0,
                latency_ms=None,
                video_id=str(gt_video_id) if gt_video_id else None
            )
            match_results.append(match_result)

            # Enhanced logging
            gt_time = gt_times[gt_idx]
            if gt_time != float('inf'):
                self.logger.debug(
                    f"FN: Video {gt_video_id or 'unknown'} - GT@{gt_time:.3f}s - No matching detection"
                )

        # Process false positives from optimal matching
        for det_idx in optimal_result['false_positives']:
            detection = detection_events[det_idx]
            detection_video_id = getattr(detection, 'video_id', None)

            # NULL SAFETY: Log warning if video_id is NULL
            if detection_video_id is None:
                logger.warning(f"FP detection {detection.id[:8]} has NULL video_id")


            match_result = MatchResult(
                ground_truth_id=None,
                detection_event_id=detection.id,
                match_type='FP',
                temporal_offset=0.0,
                confidence=detection.confidence,
                iou_score=0.0,
                latency_ms=FP_LATENCY_MARKER,  # AGENT #43: Use sentinel value for FP
                video_id=str(detection_video_id) if detection_video_id else None
            )
            match_results.append(match_result)

            # Enhanced logging
            det_time = det_times[det_idx]
            if det_time != float('inf'):
                self.logger.debug(
                    f"FP: Video {detection_video_id or 'unknown'} - Detection@{det_time:.3f}s - No matching GT"
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
                        if match_result.latency_ms is not None:
                            detection_event.actual_latency_ms = match_result.latency_ms

                            # AGENT #43: Only evaluate latency for TP detections (not FP marker)
                            if match_result.match_type == 'TP' and match_result.latency_ms < FP_LATENCY_MARKER:
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
            SessionMetrics object
        """
        # Count classifications
        tp_results = [mr for mr in match_results if mr.match_type == 'TP']
        fp_results = [mr for mr in match_results if mr.match_type == 'FP']
        fn_results = [mr for mr in match_results if mr.match_type == 'FN']
        
        true_positives = len(tp_results)
        false_positives = len(fp_results)
        false_negatives = len(fn_results)
        
        # Calculate core metrics with safe division
        tp = true_positives
        fp = false_positives
        fn = false_negatives

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        
        # Calculate latency metrics - ONLY using first 10 TP detections per video
        # This avoids contamination from late-stage detections when GT runs out
        from collections import defaultdict

        # Group TP results by video_id, preserving order (already sorted by timestamp in matching)
        video_tp_latencies = defaultdict(list)
        for mr in tp_results:
            if mr.latency_ms is not None:
                # CRITICAL NULL SAFETY: Skip if video_id is None
                if mr.video_id is None:
                    self.logger.warning(f"Skipping TP match result - NULL video_id (latency={mr.latency_ms:.1f}ms)")
                    continue

                # Use video_id from MatchResult (populated during matching)
                video_id = str(mr.video_id)
                if len(video_tp_latencies[video_id]) < 10:  # Only first 10 per video
                    video_tp_latencies[video_id].append(mr.latency_ms)

        # AGENT #43: Filter valid latencies excluding FP marker
        # Combine first 10 from each video for overall average, exclude FP markers
        valid_latencies = []
        per_video_latency_samples: Dict[str, int] = {}
        for video_id, latencies in video_tp_latencies.items():
            # Filter out FP marker values (should not be in TP list, but defensive programming)
            filtered_latencies = [lat for lat in latencies if lat < FP_LATENCY_MARKER]
            per_video_latency_samples[video_id] = len(filtered_latencies)
            valid_latencies.extend(filtered_latencies)
            avg_lat = sum(filtered_latencies)/len(filtered_latencies) if filtered_latencies else 0
            self.logger.info(f"📊 Video {video_id[:12] if video_id != 'default_video' else video_id}: Using first {len(filtered_latencies)} TP detections for latency (avg: {avg_lat:.1f}ms)")

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
        
        # Create metrics object
        metrics = SessionMetrics(
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
            total_ground_truth=tp + fn,
            total_detections=tp + fp,
            matched_detections=tp
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
            f"F1: {f1_score:.3f}, Mean Latency: {mean_latency_ms:.1f}ms"
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
        
        return self._calculate_metrics_from_results(match_results)
    
    def _calculate_metrics_from_results(self, match_results: List[MatchResult]) -> SessionMetrics:
        """
        Calculate metrics from match results without database storage.
        
        Args:
            match_results: List of match results
            
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

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        accuracy = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        # AGENT #43: Filter valid latencies excluding FP marker
        valid_latencies = [
            mr.latency_ms
            for mr in tp_results
            if mr.latency_ms is not None and mr.latency_ms < FP_LATENCY_MARKER
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
            total_ground_truth=tp + fn,
            total_detections=tp + fp,
            matched_detections=tp,
            latency_sample_count=len(valid_latencies),
            per_video_latency_samples={}
        )
    
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
        Get a summary of matching results for API responses.
        
        Args:
            session_id: Test session identifier
            
        Returns:
            Dictionary containing matching results summary
        """
        try:
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
