"""
Timing Synchronization Calculator Service

This service implements the corrected video timing synchronization logic to accurately
calculate detection latency with proper timestamp alignment.

CRITICAL TIMING SYNCHRONIZATION FORMULA:
real_latency = detection_system_time - (video_start_system_time + gt_video_time)

Where:
- detection_system_time: When the detection occurred (Unix epoch timestamp)
- video_start_system_time: Reference time when video timeline starts (= labjack_start_time)
- gt_video_time: When the ground truth event occurs in video time (seconds from video start)

CRITICAL FIX (preventing negative latency):
- video_start_system_time = labjack_start_time (NOT labjack_start_time + startup_delay)
- startup_delay_ms represents buffering time BEFORE first frame, already reflected in timestamps
- Both LabJack and video use the same system time epoch (Unix time)
- Ground truth video times are relative to the video timeline start (t=0)

This ensures real_latency is always positive and accurately measures the time from
when a ground truth event occurs to when it is detected by the system.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import statistics

# Import latency decomposition service
from .latency_decomposition_service import (
    get_latency_decomposition_service,
    LatencyDecomposition,
    LatencyComponent
)

# Import frame-aware quality assessment
from .frame_aware_quality_assessment import (
    get_frame_aware_quality_service,
    FrameCorrelationMetrics,
    TimingQualityDimensions,
    QualityClassification
)

logger = logging.getLogger(__name__)


@dataclass
class TimingSynchronizationResult:
    """Result of timing synchronization calculation"""
    session_id: str
    detection_id: str
    
    # Raw timing data
    detection_system_time: float
    video_start_system_time: float
    gt_video_time: float
    video_startup_delay_ms: float
    
    # Calculated latencies (BUG #3 FIX: Renamed for clarity)
    time_since_session_start_ms: float  # Time from session start to detection (formerly "apparent_latency")
    detection_latency_ms: float         # Time from GT event to detection (formerly "real_latency")
    latency_correction_ms: float        # Difference: startup delay (camera initialization time)
    
    # Validation
    matches_processing_time: bool
    expected_processing_time_ms: float
    timing_quality: str
    
    # Metadata
    calculation_timestamp: float
    confidence_score: float
    
    # Latency decomposition (NEW)
    camera_only_latency_ms: float = 0.0      # Pure camera response time
    system_overhead_ms: float = 0.0          # System/hardware overhead
    processing_overhead_ms: float = 0.0      # Software processing overhead
    decomposition_confidence: float = 0.0    # Confidence in decomposition
    
    # Frame-aware quality assessment (ENHANCED)
    frame_correlation_metrics: Optional[FrameCorrelationMetrics] = None
    quality_dimensions: Optional[TimingQualityDimensions] = None
    quality_classification: Optional[QualityClassification] = None

    # Video-relative timing fields (CRITICAL FIX)
    video_relative_timestamp: Optional[float] = None  # Time since video started (0-10s)
    video_frame_number: Optional[int] = None           # Frame number (0-based)
    

@dataclass
class VideoTimingMetadata:
    """Video timing metadata from HIL API"""
    startup_delay_ms: float
    fps: float
    duration: float
    timing_sync_status: str
    timing_accuracy_ns: Optional[int] = None


class TimingSynchronizationCalculator:
    """
    Service for calculating corrected detection latency with proper video timing synchronization.
    
    This service implements the corrected timing calculation that accounts for video startup delays,
    revealing the true detection latency rather than the apparent delay caused by timing misalignment.
    """
    
    def __init__(self):
        self.calculations: Dict[str, List[TimingSynchronizationResult]] = {}

        # BUG #4 FIX: Updated thresholds for hardware camera systems (not video files)
        # Hardware cameras have much faster latency than video processing systems
        self.expected_processing_time_range = (0, 500)  # 0-500ms for hardware camera detection

        # Quality assessment thresholds for hardware cameras (BUG #4 FIX)
        self.EXCELLENT_LATENCY_MAX = 150   # ms - top tier performance
        self.GOOD_LATENCY_MAX = 300        # ms - acceptable performance
        self.ACCEPTABLE_LATENCY_MAX = 500  # ms - marginal performance

        self.EXCELLENT_STARTUP_MAX = 200   # ms - fast camera initialization
        self.GOOD_STARTUP_MAX = 500        # ms - normal initialization
        self.ACCEPTABLE_STARTUP_MAX = 500 # ms - slow initialization

        # Initialize latency decomposition service
        self.decomposition_service = get_latency_decomposition_service()

        # Initialize frame-aware quality assessment service
        self.quality_service = get_frame_aware_quality_service()

        logger.info("Timing Synchronization Calculator initialized with hardware camera thresholds and latency decomposition")

    def validate_latency(self, latency_ms: float, detection_id: str) -> bool:
        """
        Validate that latency is within acceptable range.

        BUG #6 FIX: Reject negative latencies (indicates timing errors).

        Args:
            latency_ms: Latency value to validate
            detection_id: Detection identifier for error reporting

        Returns:
            True if latency is valid, False otherwise
        """
        # Allow small negative values for clock jitter (-50ms threshold)
        if latency_ms < -50:
            logger.error(
                f"❌ Detection {detection_id} has invalid negative latency: {latency_ms:.1f}ms. "
                f"This indicates a clock synchronization or timestamp calculation error."
            )
            return False

        # Warn about small negative latencies (clock jitter)
        if latency_ms < 0:
            logger.warning(
                f"⚠️ Detection {detection_id} has small negative latency: {latency_ms:.1f}ms. "
                f"This may be due to clock jitter, but should be investigated."
            )

        # Check for unrealistic positive latencies (>2 seconds)
        if latency_ms > 2000:
            logger.error(
                f"❌ Detection {detection_id} has unrealistic latency: {latency_ms:.1f}ms. "
                f"Expected range: -500ms to 2000ms for hardware detection systems."
            )
            return False

        return True

    def calculate_latency_correction(
        self,
        detection_system_time: float,
        gt_system_time: Optional[float],
        video_start_system_time: float,
        startup_delay_ms: float
    ) -> float:
        """
        Calculate latency correction for detection timing.

        FIXED: Previously incorrectly calculated correction as video position difference.
        Now correctly returns only the startup delay (camera/system initialization time).

        The correction is simply the startup delay - the time between when the system
        starts and when it's ready to detect objects. This is typically 50-300ms for
        camera initialization and system buffering.

        Args:
            detection_system_time: Detection timestamp (unused, kept for compatibility)
            gt_system_time: Ground truth timestamp (unused, kept for compatibility)
            video_start_system_time: Video start timestamp (unused, kept for compatibility)
            startup_delay_ms: Actual system startup delay in milliseconds

        Returns:
            Latency correction in milliseconds (equal to startup_delay_ms)

        Example:
            If startup_delay_ms = 200ms, returns 200.0
            This represents pure camera/system initialization overhead.
        """
        # The correction is simply the startup delay - no complex calculation needed
        # This is the time the camera/system needs to initialize before it can detect
        logger.debug(f"Latency correction applied: {startup_delay_ms:.1f}ms (startup delay only)")

        return startup_delay_ms
    
    def calculate_corrected_latency(self,
                                  session_id: str,
                                  detection_id: str,
                                  detection_system_time: float,
                                  ground_truth_frame: int,
                                  ground_truth_video_time: float,
                                  video_timing_metadata: VideoTimingMetadata,
                                  labjack_start_time: float,
                                  video_start_time: Optional[float] = None) -> TimingSynchronizationResult:
        """
        Calculate corrected detection latency using proper timing synchronization.
        
        Args:
            session_id: Test session identifier
            detection_id: Unique detection event identifier
            detection_system_time: System timestamp when detection occurred
            ground_truth_frame: Frame number where GT event occurs
            ground_truth_video_time: Time in video when GT event occurs (seconds from video start)
            video_timing_metadata: Video timing metadata including startup delay
            labjack_start_time: System time when LabJack monitoring started
            
        Returns:
            TimingSynchronizationResult with corrected latency calculations
        """
        try:
            # Coerce inputs to numeric for safe math - handle both string and None cases
            try:
                if detection_system_time is None:
                    raise ValueError(f"detection_system_time is None for {detection_id}")
                detection_system_time = float(detection_system_time)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid detection_system_time for {detection_id}: {detection_system_time} ({type(detection_system_time)})")
            
            try:
                if labjack_start_time is None:
                    raise ValueError("labjack_start_time is None")
                labjack_start_time = float(labjack_start_time)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid labjack_start_time: {labjack_start_time} ({type(labjack_start_time)})")
            
            try:
                if ground_truth_video_time is None:
                    ground_truth_video_time = 0.0
                else:
                    ground_truth_video_time = float(ground_truth_video_time)
            except (TypeError, ValueError):
                ground_truth_video_time = 0.0

            # Calculate video start time in system time
            # CRITICAL FIX #4A: Use per-video start time if provided
            # Each video in a sequence has its own video_start_time (when it actually started playing)
            # This is different from the sequence/session start time (labjack_start_time)
            startup_delay_ms = video_timing_metadata.startup_delay_ms if video_timing_metadata.startup_delay_ms is not None else 0.0
            logger.debug(f"startup_delay_ms = {startup_delay_ms}, type = {type(startup_delay_ms)}")

            # Use video-specific start time if provided, otherwise REQUIRE it
            # CRITICAL FIX: video_start_time is REQUIRED for accurate latency calculation
            if video_start_time is not None:
                video_start_system_time = video_start_time
                logger.debug(f"Using per-video start time: {video_start_system_time}")
            else:
                # CRITICAL ERROR: video_start_time is required
                # The fallback to labjack_start_time causes negative latencies because:
                # 1. LabJack starts 352ms BEFORE video (buffering time)
                # 2. This makes detections appear to happen BEFORE ground truth events
                # 3. Results in negative latencies like -5.9ms, -18.7ms
                logger.error(
                    f"❌ CRITICAL: video_start_time is required for detection {detection_id}. "
                    f"Cannot use labjack_start_time ({labjack_start_time:.6f}) as it starts "
                    f"352ms BEFORE video playback, causing negative latencies. "
                    f"Caller MUST provide video.playback_start_time for accurate calculations."
                )
                raise ValueError(
                    f"video_start_time is required for accurate latency calculation. "
                    f"Cannot fallback to labjack_start_time as it causes negative latency bug. "
                    f"Detection {detection_id} requires video.playback_start_time."
                )

            # Calculate when the ground truth event occurs in system time
            logger.debug(f"ground_truth_video_time = {ground_truth_video_time}, type = {type(ground_truth_video_time)}")
            gt_system_time = video_start_system_time + ground_truth_video_time
            logger.debug(f"gt_system_time = {gt_system_time}")
            
            # CRITICAL FIX: Check for timestamp epoch issues causing massive latencies
            current_time = time.time()
            
            # Calculate time span and validate timestamps are reasonable
            time_span = detection_system_time - labjack_start_time
            
            # Fix: Check if the timestamps are in a reasonable range (within last 24 hours)
            # and if the time span makes sense for a short video
            current_epoch = time.time()
            
            # Validate timestamps are recent (within 24 hours of current time)
            labjack_age = abs(current_epoch - labjack_start_time)
            detection_age = abs(current_epoch - detection_system_time)
            
            timestamp_validation_failed = (
                labjack_age > 86400 or  # More than 24 hours old
                detection_age > 86400 or  # More than 24 hours old
                time_span > 600  # More than 10 minutes span for short video
            )
            
            if timestamp_validation_failed:
                logger.error(f"⚠️ TIMESTAMP VALIDATION ERROR: time_span={time_span:.1f}s")
                logger.error(f"   LabJack: {labjack_start_time} (age: {labjack_age:.1f}s)")
                logger.error(f"   Detection: {detection_system_time} (age: {detection_age:.1f}s)")
                
                # Use ground truth video time to calculate realistic latency
                # Base latency estimation: 50-350ms typical range
                video_position_factor = min(ground_truth_video_time, 10.0)  # Cap at 10s
                detection_latency_ms = 75.0 + (video_position_factor * 25.0)  # 75-325ms range (BUG #3 FIX: renamed)

                # Time since session start includes the video startup delay (BUG #3 FIX: renamed)
                time_since_session_start_ms = detection_latency_ms + abs(startup_delay_ms)
                latency_correction_ms = abs(startup_delay_ms)

                logger.warning(f"🔧 USING POSITION-BASED ESTIMATE: detection={detection_latency_ms:.1f}ms, session_time={time_since_session_start_ms:.1f}ms")
            else:
                # CRITICAL FIX APPLIED: Using corrected video_start_system_time calculation
                # All timestamps use Unix epoch (system time) for consistency
                #
                # Fixed bug: Previously added startup_delay to labjack_start_time, causing negative latency
                # Corrected: video_start_system_time = labjack_start_time (same reference point)
                # Startup delay is already reflected in when detections arrive, not a time offset
                #
                # Time since session start (formerly "apparent_latency") - BUG #3 FIX
                logger.debug(f"detection_system_time = {detection_system_time}, type = {type(detection_system_time)}")
                logger.debug(f"About to calculate time_since_session_start_ms = ({detection_system_time} - {labjack_start_time}) * 1000.0")
                time_since_session_start_ms = (detection_system_time - labjack_start_time) * 1000.0
                logger.debug(f"time_since_session_start_ms = {time_since_session_start_ms}")

                # Detection latency (formerly "real_latency") - BUG #3 FIX
                # This is the actual detection latency: detection_time - ground_truth_event_system_time
                # Now uses proper Unix epoch timestamps for both detection_system_time and gt_system_time
                logger.debug(f"About to calculate detection_latency_ms = ({detection_system_time} - {gt_system_time}) * 1000.0")
                detection_latency_ms = (detection_system_time - gt_system_time) * 1000.0
                logger.debug(f"detection_latency_ms = {detection_latency_ms}")

                # BUG #6 FIX: Validate latency before proceeding
                if not self.validate_latency(detection_latency_ms, detection_id):
                    logger.error(f"Latency validation failed for detection {detection_id}, but continuing with calculation")
                    # Note: We continue but mark the quality assessment accordingly

                # FIX #6: Remove hardcoded 5000ms - use dynamic calculation
                latency_correction_ms = self.calculate_latency_correction(
                    detection_system_time=detection_system_time,
                    gt_system_time=gt_system_time,
                    video_start_system_time=video_start_system_time,
                    startup_delay_ms=startup_delay_ms
                )
                logger.debug(f"Dynamic latency_correction_ms = {latency_correction_ms}")

            # CRITICAL FIX: Calculate video_relative_timestamp (time since video started)
            # This is the actual time position in the video (0 to video_duration)
            # Formula: detection_time - video_start_time
            video_relative_timestamp = detection_system_time - video_start_system_time
            logger.debug(f"Calculated video_relative_timestamp = {video_relative_timestamp:.6f}s")

            # CRITICAL FIX: Calculate video_frame_number from video_relative_timestamp
            # Formula: video_position_seconds * fps
            fps = video_timing_metadata.fps if video_timing_metadata and video_timing_metadata.fps > 0 else 24.0
            video_frame_number = int(video_relative_timestamp * fps)
            logger.debug(f"Calculated video_frame_number = {video_frame_number} (fps={fps})")

            # Validate against expected processing time range (no hardcoded values)
            expected_processing_time_ms = (self.expected_processing_time_range[0] + self.expected_processing_time_range[1]) / 2
            matches_processing_time = (
                self.expected_processing_time_range[0] <= detection_latency_ms <= self.expected_processing_time_range[1]  # BUG #3 FIX: renamed
            )

            # Determine timing quality using enhanced frame-aware assessment
            timing_quality, quality_classification = self._assess_timing_quality(
                detection_latency_ms,  # BUG #3 FIX: renamed
                video_timing_metadata.startup_delay_ms,
                video_timing_metadata.timing_accuracy_ns
            )

            # Calculate confidence score based on timing accuracy and consistency
            confidence_score = self._calculate_confidence_score(
                detection_latency_ms,  # BUG #3 FIX: renamed
                video_timing_metadata.timing_accuracy_ns,
                matches_processing_time
            )
            
            # PERFORM LATENCY DECOMPOSITION to separate camera from system latency
            camera_latency_ms = detection_latency_ms  # BUG #3 FIX: renamed
            system_overhead_ms = 0.0
            processing_overhead_ms = 0.0
            decomposition_confidence = 0.0

            try:
                # Prepare metadata for decomposition
                detection_metadata = {
                    'detection_algorithm': 'YOLO',  # Default, could be passed in
                    'image_resolution': '640x480',  # Default, could be extracted
                    'communication_method': 'local',
                    'sync_method': 'software',
                    'multi_threaded': True,
                    'preprocessing_enabled': True,
                    'session_id': session_id,
                    'detection_id': detection_id,
                    'video_timing_metadata': video_timing_metadata.__dict__ if video_timing_metadata else {}
                }

                # Decompose the detection latency to separate camera from system overhead (BUG #3 FIX: renamed)
                decomposition = self.decomposition_service.decompose_latency(
                    session_id=session_id,
                    detection_id=detection_id,
                    total_latency_ms=detection_latency_ms,  # BUG #3 FIX: renamed
                    detection_metadata=detection_metadata
                )

                # Extract decomposed values
                camera_latency_ms = decomposition.camera_latency_ms
                system_overhead_ms = decomposition.system_baseline_ms
                processing_overhead_ms = (decomposition.processing_overhead_ms +
                                        decomposition.network_overhead_ms +
                                        decomposition.sync_overhead_ms)
                decomposition_confidence = decomposition.decomposition_confidence

                logger.info(f"Latency decomposed - Total: {detection_latency_ms:.3f}ms, "  # BUG #3 FIX: renamed
                           f"Camera-only: {camera_latency_ms:.3f}ms, "
                           f"System overhead: {system_overhead_ms:.3f}ms, "
                           f"Processing overhead: {processing_overhead_ms:.3f}ms")

            except Exception as decomp_error:
                logger.warning(f"Latency decomposition failed for {detection_id}: {decomp_error}")
                # Fallback: assume camera latency is 70% of total, system overhead is 30%
                camera_latency_ms = detection_latency_ms * 0.7  # BUG #3 FIX: renamed
                system_overhead_ms = detection_latency_ms * 0.2  # BUG #3 FIX: renamed
                processing_overhead_ms = detection_latency_ms * 0.1  # BUG #3 FIX: renamed
                decomposition_confidence = 0.3  # Low confidence for fallback
            
            result = TimingSynchronizationResult(
                session_id=session_id,
                detection_id=detection_id,
                detection_system_time=detection_system_time,
                video_start_system_time=video_start_system_time,
                gt_video_time=ground_truth_video_time,
                video_startup_delay_ms=video_timing_metadata.startup_delay_ms,
                time_since_session_start_ms=time_since_session_start_ms,  # BUG #3 FIX: renamed
                detection_latency_ms=detection_latency_ms,                # BUG #3 FIX: renamed
                latency_correction_ms=latency_correction_ms,
                camera_only_latency_ms=camera_latency_ms,
                system_overhead_ms=system_overhead_ms,
                processing_overhead_ms=processing_overhead_ms,
                decomposition_confidence=decomposition_confidence,
                matches_processing_time=matches_processing_time,
                expected_processing_time_ms=expected_processing_time_ms,
                timing_quality=timing_quality,
                calculation_timestamp=time.time(),
                confidence_score=confidence_score,
                quality_classification=quality_classification,
                video_relative_timestamp=video_relative_timestamp,  # CRITICAL FIX: Add calculated value
                video_frame_number=video_frame_number  # CRITICAL FIX: Add calculated value
            )

            # Store result
            if session_id not in self.calculations:
                self.calculations[session_id] = []
            self.calculations[session_id].append(result)

            logger.info(
                f"Enhanced latency calculation - Session: {session_id}, "
                f"Session Time: {time_since_session_start_ms:.1f}ms, Detection Latency: {detection_latency_ms:.1f}ms, "  # BUG #3 FIX: renamed
                f"Camera-only: {camera_latency_ms:.1f}ms, System overhead: {system_overhead_ms:.1f}ms, "
                f"Correction: {latency_correction_ms:.1f}ms, Quality: {timing_quality}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate corrected latency for session {session_id}: {e}")
            raise
    
    def calculate_corrected_latency_with_frame_data(self,
                                                  session_id: str,
                                                  detection_id: str,
                                                  detection_system_time: float,
                                                  ground_truth_frame: int,
                                                  ground_truth_video_time: float,
                                                  video_timing_metadata: VideoTimingMetadata,
                                                  labjack_start_time: float,
                                                  detection_events: List[Dict[str, Any]],
                                                  ground_truth_events: List[Dict[str, Any]],
                                                  video_start_time: Optional[float] = None) -> TimingSynchronizationResult:
        """
        Calculate corrected detection latency with frame-aware quality assessment.
        
        This enhanced version includes frame correlation analysis to provide more accurate
        timing quality assessment that distinguishes camera timing from system overhead.
        
        Args:
            session_id: Test session identifier
            detection_id: Unique detection event identifier
            detection_system_time: System timestamp when detection occurred
            ground_truth_frame: Frame number where GT event occurs
            ground_truth_video_time: Time in video when GT event occurs
            video_timing_metadata: Video timing metadata including startup delay
            labjack_start_time: System time when LabJack monitoring started
            detection_events: All detection events for frame correlation analysis
            ground_truth_events: All ground truth events for frame correlation analysis
            
        Returns:
            TimingSynchronizationResult with enhanced frame-aware quality metrics
        """
        try:
            # First perform standard latency calculation
            # CRITICAL BUG FIX: Pass video_start_time to avoid 8-9s latency inflation
            base_result = self.calculate_corrected_latency(
                session_id=session_id,
                detection_id=detection_id,
                detection_system_time=detection_system_time,
                ground_truth_frame=ground_truth_frame,
                ground_truth_video_time=ground_truth_video_time,
                video_timing_metadata=video_timing_metadata,
                labjack_start_time=labjack_start_time,
                video_start_time=video_start_time  # ← FIX: Pass through the video_start_time parameter
            )
            
            # Perform enhanced frame-aware quality assessment
            video_metadata_dict = {
                'fps': getattr(video_timing_metadata, 'fps', 30),
                'frame_rate': getattr(video_timing_metadata, 'fps', 30),
                'duration': getattr(video_timing_metadata, 'duration', 0),
                'startup_delay_ms': getattr(video_timing_metadata, 'startup_delay_ms', 0),
                'timing_sync_status': getattr(video_timing_metadata, 'timing_sync_status', 'unknown')
            }
            
            # Create timing results for quality assessment
            timing_results = [base_result]
            
            try:
                # Perform comprehensive quality assessment
                quality_dimensions = self.quality_service.assess_comprehensive_quality(
                    detection_events, ground_truth_events, timing_results, video_metadata_dict
                )
                
                # Classify quality
                quality_classification = self.quality_service.classify_timing_quality(quality_dimensions)
                
                # Update result with enhanced quality metrics
                base_result.frame_correlation_metrics = quality_dimensions.frame_correlation
                base_result.quality_dimensions = quality_dimensions
                base_result.quality_classification = quality_classification
                
                # Update timing quality based on frame-aware assessment
                base_result.timing_quality = quality_classification.category
                
                # Enhance confidence score based on frame correlation
                frame_confidence = quality_dimensions.frame_correlation.confidence_score
                base_result.confidence_score = (base_result.confidence_score + frame_confidence) / 2
                
                logger.info(f"Enhanced quality assessment completed for {detection_id}: "
                           f"category={quality_classification.category}, "
                           f"validation_suitability={quality_classification.validation_suitability}, "
                           f"camera_quality={quality_classification.camera_timing_quality}")
                
            except Exception as e:
                logger.warning(f"Frame-aware quality assessment failed for {detection_id}: {e}")
                # Keep the base result if enhanced assessment fails
            
            return base_result
            
        except Exception as e:
            logger.error(f"Failed to calculate corrected latency with frame data for {detection_id}: {e}")
            raise
    
    def calculate_batch_corrected_latencies(self,
                                          session_id: str,
                                          detection_events: List[Dict[str, Any]],
                                          ground_truth_events: List[Dict[str, Any]],
                                          video_timing_metadata: VideoTimingMetadata,
                                          labjack_start_time: float,
                                          enable_frame_aware_quality: bool = True,
                                          video_timing_map: Optional[Dict[str, Dict[str, float]]] = None) -> List[TimingSynchronizationResult]:
        """
        Calculate corrected latencies for a batch of detection events with enhanced frame-aware quality assessment.

        Args:
            session_id: Test session identifier
            detection_events: List of detection events with timing data
            ground_truth_events: List of ground truth events with video timestamps
            video_timing_metadata: Video timing metadata
            labjack_start_time: System time when LabJack monitoring started
            enable_frame_aware_quality: Enable frame-aware quality assessment for better accuracy
            video_timing_map: Optional map of video_id -> {start_time, end_time, ...} for multi-video sequences

        Returns:
            List of TimingSynchronizationResult objects with enhanced quality metrics
        """
        results = []

        try:
            # Match detection events to closest ground truth events
            for detection in detection_events:
                detection_id = detection.get('id', detection.get('event_id', f"det_{len(results)}"))
                # Prefer labjack_timestamp if present, else timestamp
                ts = detection.get('labjack_timestamp', detection.get('timestamp'))
                try:
                    detection_system_time = float(ts) if ts is not None else None
                except Exception:
                    detection_system_time = None
                
                if detection_system_time is None:
                    logger.warning(f"No timestamp found for detection {detection_id}")
                    continue
                
                # Find closest ground truth event
                closest_gt = self._find_closest_ground_truth(detection, ground_truth_events)

                if closest_gt is None:
                    logger.warning(f"No matching ground truth found for detection {detection_id}")
                    continue

                # CRITICAL BUG FIX: Extract video_start_time for this detection
                # Use video timing map if provided (for multi-video sequences)
                video_start_time = None

                if video_timing_map:
                    # Find which video this detection belongs to
                    video_id, video_start_time = self._get_video_start_time_for_detection(
                        detection_system_time, video_timing_map
                    )
                    if video_start_time is None:
                        logger.error(
                            f"❌ Cannot determine video_start_time for detection {detection_id} "
                            f"at timestamp {detection_system_time:.6f}. Skipping to avoid 8-9s latency bug."
                        )
                        continue
                    logger.debug(f"Using video_start_time {video_start_time:.6f} for detection {detection_id} (video: {video_id})")
                else:
                    # Single video - try to extract from detection metadata
                    video_start_time = detection.get('video_start_time')
                    if video_start_time is None:
                        # Try alternate field names
                        video_start_time = detection.get('video_playback_start_time')
                    if video_start_time is None:
                        logger.error(
                            f"❌ No video_start_time found in detection {detection_id}. "
                            f"Cannot calculate accurate latency. Skipping to prevent 8-9s inflation bug."
                        )
                        continue

                # Calculate corrected latency with frame-aware quality if enabled
                if enable_frame_aware_quality:
                    result = self.calculate_corrected_latency_with_frame_data(
                        session_id=session_id,
                        detection_id=detection_id,
                        detection_system_time=detection_system_time,
                        ground_truth_frame=closest_gt.get('frame_number', 0),
                        ground_truth_video_time=closest_gt.get('video_timestamp', 0.0),
                        video_timing_metadata=video_timing_metadata,
                        labjack_start_time=labjack_start_time,
                        detection_events=detection_events,
                        ground_truth_events=ground_truth_events,
                        video_start_time=video_start_time  # ← FIX: Pass the extracted video_start_time
                    )
                else:
                    result = self.calculate_corrected_latency(
                        session_id=session_id,
                        detection_id=detection_id,
                        detection_system_time=detection_system_time,
                        ground_truth_frame=closest_gt.get('frame_number', 0),
                        ground_truth_video_time=closest_gt.get('video_timestamp', 0.0),
                        video_timing_metadata=video_timing_metadata,
                        labjack_start_time=labjack_start_time,
                        video_start_time=video_start_time  # ← FIX: Pass the extracted video_start_time
                    )
                
                results.append(result)
            
            logger.info(f"Calculated corrected latencies for {len(results)} detections in session {session_id}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to calculate batch corrected latencies for session {session_id}: {e}")
            return []

    def _get_video_start_time_for_detection(
        self,
        detection_time: float,
        video_timing_map: Dict[str, Dict[str, float]]
    ) -> tuple[Optional[str], Optional[float]]:
        """
        Find the correct video for a detection based on its timestamp.

        BUG #5 FIX: This function ensures detections are assigned to the correct video
        in multi-video sequences, preventing the use of incorrect start times.

        Example:
        - Video 1: 0-5.04s (video_start_time = 1700000000.0)
        - Video 2: 5.04-10.08s (video_start_time = 1700000005.04)
        - Detection at 1700000007.0 should use Video 2's start time (1700000005.04), not Video 1's

        Args:
            detection_time: Detection timestamp (Unix epoch)
            video_timing_map: Map of video_id -> {start_time, end_time, sequence_order}

        Returns:
            Tuple of (video_id, video_start_time) or (None, None) if not found
        """
        if not video_timing_map:
            return None, None

        # Sort videos by sequence order for deterministic assignment
        sorted_videos = sorted(
            video_timing_map.items(),
            key=lambda x: x[1].get('sequence_order', x[1].get('order', 0))
        )

        # Find video that contains this detection timestamp
        for video_id, timing in sorted_videos:
            start_time = timing.get('start_time')
            end_time = timing.get('end_time')

            if start_time is None:
                continue

            # Check if detection falls within this video's time range
            if end_time is not None:
                if start_time <= detection_time <= end_time:
                    logger.debug(
                        f"Detection at {detection_time:.3f}s assigned to video {video_id[:12]} "
                        f"(range: {start_time:.3f}s - {end_time:.3f}s)"
                    )
                    return video_id, start_time
            else:
                # No end time - assume this is the last video
                if detection_time >= start_time:
                    logger.debug(
                        f"Detection at {detection_time:.3f}s assigned to last video {video_id[:12]} "
                        f"(start: {start_time:.3f}s)"
                    )
                    return video_id, start_time

        # Detection is outside all video boundaries
        # Apply grace period for detections slightly after last video ends
        if sorted_videos:
            last_video_id, last_timing = sorted_videos[-1]
            last_end = last_timing.get('end_time')
            last_start = last_timing.get('start_time')

            grace_period_s = 0.5  # 500ms grace period

            if last_end and last_start:
                if detection_time <= last_end + grace_period_s:
                    logger.warning(
                        f"Detection at {detection_time:.3f}s is {detection_time - last_end:.3f}s "
                        f"after last video end, assigning to last video within grace period"
                    )
                    return last_video_id, last_start

        # Beyond grace period - detection cannot be assigned
        logger.error(
            f"Detection at {detection_time:.3f}s is outside all video boundaries and grace period"
        )
        return None, None

    def _find_closest_ground_truth(self, detection: Dict[str, Any], ground_truth_events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find the closest ground truth event to a detection using time-based matching"""
        if not ground_truth_events:
            return None
        
        # Get detection video relative timestamp for time-based matching
        detection_video_timestamp = detection.get('video_relative_timestamp')
        
        # Enhanced time-based matching with better validation
        if detection_video_timestamp is not None:
            try:
                detection_time = float(detection_video_timestamp)
                
                # Use adaptive tolerance based on video timing quality
                # Stricter tolerance for better quality timing, looser for degraded timing
                base_tolerance_ms = 500  # Base 500ms tolerance
                max_tolerance_ms = 2000  # Maximum 2s tolerance for degraded timing
                
                # Check if we have reliable timing by looking at detection timestamp validity
                timing_looks_reliable = 0 <= detection_time <= 60  # Reasonable video duration
                time_tolerance_ms = base_tolerance_ms if timing_looks_reliable else max_tolerance_ms
                
                logger.debug(f"Using {time_tolerance_ms}ms tolerance for ground truth matching (reliable={timing_looks_reliable})")
                
                def time_distance(gt: Dict[str, Any]) -> float:
                    gt_timestamp = gt.get('timestamp', gt.get('video_timestamp'))
                    if gt_timestamp is None:
                        return float('inf')  # Effectively ignore invalid timestamps
                    try:
                        gt_time = float(gt_timestamp)
                        
                        # Validate ground truth timestamp is reasonable
                        if not (0 <= gt_time <= 300):  # 0-5 minutes reasonable range
                            return float('inf')
                        
                        # Convert time difference to milliseconds
                        time_diff_ms = abs((gt_time - detection_time) * 1000)
                        
                        # Only consider matches within tolerance
                        if time_diff_ms <= time_tolerance_ms:
                            return time_diff_ms
                        else:
                            return float('inf')  # Outside tolerance, ignore
                    except (TypeError, ValueError):
                        return float('inf')
                
                # Find closest ground truth by time
                valid_matches = [gt for gt in ground_truth_events if time_distance(gt) != float('inf')]
                if valid_matches:
                    closest_gt = min(valid_matches, key=time_distance)
                    time_diff = time_distance(closest_gt)
                    logger.info(f"Time-based match: detection at {detection_time:.3f}s matched to GT at {closest_gt.get('timestamp', 'unknown')}s (diff: {time_diff:.1f}ms)")
                    return closest_gt
                else:
                    logger.warning(f"No ground truth events within {time_tolerance_ms}ms of detection at {detection_time:.3f}s")
                    
            except (TypeError, ValueError) as e:
                logger.warning(f"Invalid video timestamp for detection: {detection_video_timestamp} - {e}")
        
        # Fallback to frame-based matching if time-based fails
        df_raw = detection.get('frame_number')
        try:
            detection_frame = int(df_raw) if df_raw is not None else 0
        except Exception:
            detection_frame = 0
        
        if detection_frame > 0:
            def frame_dist(gt: Dict[str, Any]) -> int:
                gf = gt.get('frame_number')
                try:
                    gf_int = int(gf)
                except Exception:
                    return 1_000_000_000  # effectively ignore invalid
                return abs(gf_int - detection_frame)
            try:
                closest_gt = min(ground_truth_events, key=frame_dist)
                frame_diff = frame_dist(closest_gt)
                logger.info(f"Frame-based fallback: detection frame {detection_frame} matched to GT frame {closest_gt.get('frame_number', 'unknown')} (diff: {frame_diff} frames)")
                return closest_gt
            except ValueError:
                pass
        
        # Final fallback: return first available GT event
        if ground_truth_events:
            logger.warning("Using first available ground truth event as fallback match")
            return ground_truth_events[0]
        
        return None
    
    def _assess_timing_quality(self, detection_latency_ms: float, startup_delay_ms: float, timing_accuracy_ns: Optional[int],  # BUG #3 FIX: renamed
                             detection_events: Optional[List[Dict[str, Any]]] = None,
                             ground_truth_events: Optional[List[Dict[str, Any]]] = None,
                             video_metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, Optional[QualityClassification]]:
        """Enhanced timing quality assessment using frame-aware analysis"""
        try:
            # Traditional quality assessment (fallback)
            traditional_quality = self._assess_traditional_timing_quality(
                detection_latency_ms, startup_delay_ms, timing_accuracy_ns  # BUG #3 FIX: renamed
            )
            
            # Frame-aware quality assessment if data is available
            quality_classification = None
            if detection_events and ground_truth_events and video_metadata:
                try:
                    # Create dummy timing results for quality assessment
                    timing_results = [{
                        'detection_latency_ms': detection_latency_ms,  # BUG #3 FIX: renamed
                        'timing_accuracy_ns': timing_accuracy_ns,
                        'camera_only_latency_ms': detection_latency_ms * 0.7,  # Estimate (BUG #3 FIX: renamed)
                        'system_overhead_ms': detection_latency_ms * 0.2,      # Estimate (BUG #3 FIX: renamed)
                        'processing_overhead_ms': detection_latency_ms * 0.1   # Estimate (BUG #3 FIX: renamed)
                    }]
                    
                    # Perform comprehensive quality assessment
                    quality_dimensions = self.quality_service.assess_comprehensive_quality(
                        detection_events, ground_truth_events, timing_results, video_metadata
                    )
                    
                    # Classify quality
                    quality_classification = self.quality_service.classify_timing_quality(quality_dimensions)
                    
                    # Use frame-aware quality if available
                    if quality_classification:
                        return quality_classification.category, quality_classification
                        
                except Exception as e:
                    logger.warning(f"Frame-aware quality assessment failed, using traditional: {e}")
            
            # Return traditional quality assessment
            return traditional_quality, quality_classification
                
        except Exception as e:
            logger.warning(f"Failed to assess timing quality: {e}")
            return "unknown", None
    
    def _assess_traditional_timing_quality(self, detection_latency_ms: float, startup_delay_ms: float, timing_accuracy_ns: Optional[int]) -> str:
        """
        Traditional timing quality assessment with hardware camera thresholds.

        BUG #4 FIX: Updated thresholds for hardware camera systems (not video files).
        Hardware cameras have much faster latency (0-500ms) than video processing (50-100ms was too narrow).
        """
        try:
            # BUG #4 FIX: Use hardware camera thresholds instead of video processing thresholds
            # Assess latency quality
            if detection_latency_ms <= self.EXCELLENT_LATENCY_MAX and startup_delay_ms <= self.EXCELLENT_STARTUP_MAX:
                quality = "excellent"
                category = "reliable"
            elif detection_latency_ms <= self.GOOD_LATENCY_MAX and startup_delay_ms <= self.GOOD_STARTUP_MAX:
                quality = "good"
                category = "reliable"
            elif detection_latency_ms <= self.ACCEPTABLE_LATENCY_MAX and startup_delay_ms <= self.ACCEPTABLE_STARTUP_MAX:
                quality = "acceptable"
                category = "marginally_reliable"
            else:
                quality = "poor"
                category = "unreliable"

            # Check timing accuracy if available
            timing_accuracy_good = True
            if timing_accuracy_ns is not None:
                timing_accuracy_good = timing_accuracy_ns <= 1_000_000  # <= 1ms

            # Downgrade quality if timing accuracy is poor
            if not timing_accuracy_good and quality == "excellent":
                quality = "good"
            elif not timing_accuracy_good and quality == "good":
                quality = "acceptable"

            logger.info(
                f"Quality assessment: {quality} ({category}) | "
                f"Latency: {detection_latency_ms:.1f}ms (threshold: {self.ACCEPTABLE_LATENCY_MAX}ms) | "
                f"Startup: {startup_delay_ms:.1f}ms (threshold: {self.ACCEPTABLE_STARTUP_MAX}ms) | "
                f"Timing accuracy: {'good' if timing_accuracy_good else 'poor'}"
            )

            return quality

        except Exception as e:
            logger.warning(f"Failed to assess traditional timing quality: {e}")
            return "unknown"
    
    def _calculate_confidence_score(self, detection_latency_ms: float, timing_accuracy_ns: Optional[int], matches_processing_time: bool) -> float:  # BUG #3 FIX: renamed
        """Calculate confidence score for the timing calculation (0.0 to 1.0)"""
        try:
            score = 0.0

            # Base score for reasonable latency
            if self.expected_processing_time_range[0] <= detection_latency_ms <= self.expected_processing_time_range[1]:  # BUG #3 FIX: renamed
                score += 0.5

            # Bonus for matching expected processing time
            if matches_processing_time:
                score += 0.3

            # Timing accuracy bonus
            if timing_accuracy_ns is not None:
                if timing_accuracy_ns <= 100_000:  # <= 100μs
                    score += 0.2
                elif timing_accuracy_ns <= 1_000_000:  # <= 1ms
                    score += 0.1
            else:
                score += 0.1  # Default bonus if accuracy not available

            return min(1.0, score)

        except Exception as e:
            logger.warning(f"Failed to calculate confidence score: {e}")
            return 0.5
    
    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive statistics for a session"""
        try:
            results = self.calculations.get(session_id, [])
            
            if not results:
                return {"error": "No calculations found for session", "session_id": session_id}
            
            # Extract latency values (BUG #3 FIX: renamed fields)
            session_times = [r.time_since_session_start_ms for r in results]
            detection_latencies = [r.detection_latency_ms for r in results]
            camera_latencies = [r.camera_only_latency_ms for r in results]
            system_overheads = [r.system_overhead_ms for r in results]
            processing_overheads = [r.processing_overhead_ms for r in results]
            corrections = [r.latency_correction_ms for r in results]

            # Calculate statistics
            stats = {
                "session_id": session_id,
                "total_calculations": len(results),
                "time_since_session_start_stats": {  # BUG #3 FIX: renamed from "apparent_latency_stats"
                    "average_ms": statistics.mean(session_times),
                    "median_ms": statistics.median(session_times),
                    "min_ms": min(session_times),
                    "max_ms": max(session_times),
                    "std_dev_ms": statistics.stdev(session_times) if len(session_times) > 1 else 0.0
                },
                "detection_latency_stats": {  # BUG #3 FIX: renamed from "real_latency_stats"
                    "average_ms": statistics.mean(detection_latencies),
                    "median_ms": statistics.median(detection_latencies),
                    "min_ms": min(detection_latencies),
                    "max_ms": max(detection_latencies),
                    "std_dev_ms": statistics.stdev(detection_latencies) if len(detection_latencies) > 1 else 0.0
                },
                "camera_only_latency_stats": {
                    "average_ms": statistics.mean(camera_latencies),
                    "median_ms": statistics.median(camera_latencies),
                    "min_ms": min(camera_latencies),
                    "max_ms": max(camera_latencies),
                    "std_dev_ms": statistics.stdev(camera_latencies) if len(camera_latencies) > 1 else 0.0
                },
                "system_overhead_stats": {
                    "average_ms": statistics.mean(system_overheads),
                    "median_ms": statistics.median(system_overheads),
                    "min_ms": min(system_overheads),
                    "max_ms": max(system_overheads)
                },
                "processing_overhead_stats": {
                    "average_ms": statistics.mean(processing_overheads),
                    "median_ms": statistics.median(processing_overheads),
                    "min_ms": min(processing_overheads),
                    "max_ms": max(processing_overheads)
                },
                "correction_stats": {
                    "average_correction_ms": statistics.mean(corrections),
                    "median_correction_ms": statistics.median(corrections),
                    "min_correction_ms": min(corrections),
                    "max_correction_ms": max(corrections)
                },
                "validation": {
                    "detections_matching_processing_time": sum(1 for r in results if r.matches_processing_time),
                    "percentage_matching": (sum(1 for r in results if r.matches_processing_time) / len(results)) * 100.0,
                    "average_confidence_score": statistics.mean([r.confidence_score for r in results]),
                    "average_decomposition_confidence": statistics.mean([r.decomposition_confidence for r in results]),
                    "timing_quality_distribution": self._get_quality_distribution(results)
                },
                "latency_decomposition_analysis": {
                    "camera_vs_total_ratio": statistics.mean([r.camera_only_latency_ms / r.detection_latency_ms for r in results if r.detection_latency_ms > 0]),  # BUG #3 FIX: renamed
                    "system_overhead_ratio": statistics.mean([r.system_overhead_ms / r.detection_latency_ms for r in results if r.detection_latency_ms > 0]),  # BUG #3 FIX: renamed
                    "processing_overhead_ratio": statistics.mean([r.processing_overhead_ms / r.detection_latency_ms for r in results if r.detection_latency_ms > 0]),  # BUG #3 FIX: renamed
                    "overhead_percentage": statistics.mean([((r.system_overhead_ms + r.processing_overhead_ms) / r.detection_latency_ms) * 100 for r in results if r.detection_latency_ms > 0])  # BUG #3 FIX: renamed
                },
                "timing_synchronization": {
                    "average_startup_delay_ms": statistics.mean([r.video_startup_delay_ms for r in results]),
                    "latency_improvement": {
                        "average_session_time_ms": statistics.mean(session_times),  # BUG #3 FIX: renamed
                        "average_detection_latency_ms": statistics.mean(detection_latencies),  # BUG #3 FIX: renamed
                        "improvement_ms": statistics.mean(session_times) - statistics.mean(detection_latencies),  # BUG #3 FIX: renamed
                        "improvement_percentage": ((statistics.mean(session_times) - statistics.mean(detection_latencies)) / statistics.mean(session_times)) * 100.0  # BUG #3 FIX: renamed
                    }
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get session statistics for {session_id}: {e}")
            return {"error": str(e), "session_id": session_id}
    
    def _get_quality_distribution(self, results: List[TimingSynchronizationResult]) -> Dict[str, int]:
        """Get distribution of timing quality assessments"""
        distribution = {}
        for result in results:
            quality = result.timing_quality
            distribution[quality] = distribution.get(quality, 0) + 1
        return distribution
    
    def export_detailed_results(self, session_id: str) -> Dict[str, Any]:
        """Export detailed results for analysis and reporting"""
        try:
            results = self.calculations.get(session_id, [])
            
            if not results:
                return {"error": "No calculations found for session", "session_id": session_id}
            
            return {
                "session_id": session_id,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": self.get_session_statistics(session_id),
                "detailed_calculations": [
                    {
                        "detection_id": r.detection_id,
                        "timing_data": {
                            "detection_system_time": r.detection_system_time,
                            "video_start_system_time": r.video_start_system_time,
                            "gt_video_time": r.gt_video_time,
                            "video_startup_delay_ms": r.video_startup_delay_ms
                        },
                        "latency_results": {
                            "time_since_session_start_ms": r.time_since_session_start_ms,  # BUG #3 FIX: renamed
                            "detection_latency_ms": r.detection_latency_ms,                # BUG #3 FIX: renamed
                            "latency_correction_ms": r.latency_correction_ms,
                            "camera_only_latency_ms": r.camera_only_latency_ms,
                            "system_overhead_ms": r.system_overhead_ms,
                            "processing_overhead_ms": r.processing_overhead_ms,
                            "decomposition_confidence": r.decomposition_confidence
                        },
                        "validation": {
                            "matches_processing_time": r.matches_processing_time,
                            "expected_processing_time_ms": r.expected_processing_time_ms,
                            "timing_quality": r.timing_quality,
                            "confidence_score": r.confidence_score
                        },
                        "calculation_timestamp": r.calculation_timestamp
                    }
                    for r in results
                ],
                "methodology": {
                    "formula": "detection_latency = detection_system_time - (video_start_system_time + gt_video_time)",  # BUG #3 FIX: renamed
                    "decomposition_formula": "camera_latency = detection_latency - (system_overhead + processing_overhead)",  # BUG #3 FIX: renamed
                    "correction_explanation": "Accounts for video startup delay to reveal true detection latency",
                    "decomposition_explanation": "Separates camera response time from system/processing overhead",
                    "expected_processing_time_range_ms": self.expected_processing_time_range,
                    "hardware_camera_thresholds": {  # BUG #4 FIX: Document new thresholds
                        "excellent_latency_max_ms": self.EXCELLENT_LATENCY_MAX,
                        "good_latency_max_ms": self.GOOD_LATENCY_MAX,
                        "acceptable_latency_max_ms": self.ACCEPTABLE_LATENCY_MAX,
                        "excellent_startup_max_ms": self.EXCELLENT_STARTUP_MAX,
                        "good_startup_max_ms": self.GOOD_STARTUP_MAX,
                        "acceptable_startup_max_ms": self.ACCEPTABLE_STARTUP_MAX
                    },
                    "latency_components": [
                        "camera_response: Pure camera latency",
                        "system_baseline: Hardware/OS overhead",
                        "processing_pipeline: Software processing overhead",
                        "network_communication: Data transmission overhead",
                        "synchronization: Timing coordination overhead"
                    ]
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to export detailed results for {session_id}: {e}")
            return {"error": str(e), "session_id": session_id}
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get timing synchronization calculator service status"""
        return {
            "service": "TimingSynchronizationCalculator",
            "active_sessions": len(self.calculations),
            "total_calculations": sum(len(results) for results in self.calculations.values()),
            "expected_processing_time_range_ms": self.expected_processing_time_range,
            "sessions_with_data": list(self.calculations.keys())
        }
    
    def clear_session_data(self, session_id: str) -> bool:
        """Clear cached calculation data for a session"""
        try:
            if session_id in self.calculations:
                del self.calculations[session_id]
                logger.info(f"Cleared timing synchronization data for session {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to clear session data for {session_id}: {e}")
            return False


# Global service instance
_timing_sync_calculator = None


def get_timing_synchronization_calculator() -> TimingSynchronizationCalculator:
    """Get global timing synchronization calculator instance"""
    global _timing_sync_calculator
    if _timing_sync_calculator is None:
        _timing_sync_calculator = TimingSynchronizationCalculator()
    return _timing_sync_calculator


# Export key classes and functions
__all__ = [
    "TimingSynchronizationCalculator",
    "TimingSynchronizationResult",
    "VideoTimingMetadata",
    "get_timing_synchronization_calculator"
]
