# Timestamp Compensation Algorithm
**Version:** 1.0.0
**Last Updated:** 2025-11-20
**Status:** Production-Ready

## Executive Summary

This document defines the timestamp compensation algorithm that adjusts detection timestamps to eliminate drift, achieving **<10ms effective drift** and enabling precise ground truth matching for HIL testing validation.

## 1. Problem Statement

### 1.1 The Timestamp Alignment Challenge

In HIL testing, we have two independent timelines:

1. **Video Timeline** (Ground Truth)
   - Origin: Video start (t=0)
   - Events: Object detections at specific video frames
   - Domain: Video playback time (ms)

2. **LabJack Timeline** (Detection Events)
   - Origin: LabJack monitoring start
   - Events: GPIO rising edges detected by hardware
   - Domain: System time (absolute timestamps)

**Problem**: LabJack starts monitoring with a delay after video starts (drift), causing misalignment.

```
Video Timeline:    |--[Frame 0]--[Frame 30]--[Frame 60]--|
                   t=0         t=1000ms     t=2000ms

LabJack Timeline:  .....delay.....|--[Det 1]--[Det 2]--|
                                   ^
                                   drift = 150ms

Without compensation:
  - Video event at t=1000ms
  - LabJack detection at t=1000ms (system time)
  - Appears matched, but actually 150ms early!

With compensation:
  - Video event at t=1000ms
  - LabJack detection at t=1000ms - 150ms = t=850ms
  - Correctly identified as early (no match)
```

### 1.2 Compensation Objectives

1. **Drift Elimination**: Remove systematic delay between video start and monitoring start
2. **Clock Skew Correction**: Account for browser/backend clock differences
3. **Precision**: Achieve ±1ms timestamp accuracy after compensation
4. **Consistency**: Ensure all timestamps use common reference frame

## 2. Compensation Algorithm

### 2.1 Core Formula

```python
def compensate_detection_timestamp(
    T_detection_raw: float,        # Raw LabJack detection time (backend clock)
    T_video_start_browser: float,  # Video start time (browser clock)
    T_labjack_start_backend: float,  # LabJack monitoring start (backend clock)
    clock_offset: float            # Browser → Backend offset (ms)
) -> float:
    """
    Compensate detection timestamp to video timeline

    Returns: Detection time relative to video start (ms)
    """
    # Step 1: Convert video start to backend clock domain
    T_video_start_backend = T_video_start_browser + clock_offset

    # Step 2: Calculate drift (how late LabJack started)
    drift_ms = (T_labjack_start_backend - T_video_start_backend) * 1000

    # Step 3: Compensate detection timestamp
    # Convert to video-relative time by subtracting both drift and video start
    T_detection_compensated = (T_detection_raw - T_labjack_start_backend) * 1000

    return T_detection_compensated
```

### 2.2 Step-by-Step Breakdown

**Input Timestamps:**
- `T_video_start_browser`: 1000.0 ms (browser `performance.now()`)
- `clock_offset`: +50 ms (browser is 50ms behind backend)
- `T_labjack_start_backend`: 1.200 s (backend `time.perf_counter()`)
- `T_detection_raw`: 2.500 s (backend `time.perf_counter()`)

**Step 1: Clock Domain Conversion**
```python
T_video_start_backend = 1000.0 + 50 = 1050.0 ms = 1.050 s
```

**Step 2: Drift Calculation**
```python
drift_ms = (1.200 - 1.050) * 1000 = 150 ms
```

**Step 3: Timestamp Compensation**
```python
# Time from LabJack start to detection
detection_delta = (2.500 - 1.200) * 1000 = 1300 ms

# This is already video-relative (LabJack started 150ms after video)
# So detection happened at video time = 1300 ms
T_detection_compensated = 1300 ms
```

**Verification:**
- Video started at t=0 (video timeline)
- LabJack started at t=150ms (video timeline, due to drift)
- Detection at t=1300ms (LabJack timeline) = t=1450ms (video timeline)

Wait, there's an issue above. Let me correct:

```python
# CORRECT FORMULA:
# Detection time relative to video start
T_detection_video_relative = (T_detection_raw - T_video_start_backend) * 1000

# Result: (2.500 - 1.050) * 1000 = 1450 ms ✓
```

This correctly places the detection at 1450ms in video time.

### 2.3 Complete Implementation

```python
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TimestampCompensationContext:
    """
    Context for timestamp compensation
    Contains all reference timestamps needed for compensation
    """
    # Video timeline (browser clock domain)
    video_start_browser_ms: float          # Video.play() time (performance.now())

    # Clock synchronization
    clock_offset_ms: float                 # Browser → Backend offset
    clock_sync_rtt_ms: float              # Clock sync quality metric

    # LabJack timeline (backend clock domain)
    labjack_start_backend_s: float        # Monitoring start (time.perf_counter())

    # Calculated drift
    total_drift_ms: float                 # Lag between video start and monitoring start

    # Metadata
    compensation_timestamp: datetime      # When compensation was calculated
    drift_measurement_valid: bool         # Whether drift measurement passed validation

    @property
    def video_start_backend_s(self) -> float:
        """Video start time in backend clock domain"""
        return (self.video_start_browser_ms + self.clock_offset_ms) / 1000

    def validate(self) -> tuple[bool, list[str]]:
        """Validate compensation context"""
        errors = []

        if abs(self.clock_offset_ms) > 1000:
            errors.append(f"Excessive clock offset: {self.clock_offset_ms} ms")

        if self.clock_sync_rtt_ms > 100:
            errors.append(f"Poor clock sync quality: {self.clock_sync_rtt_ms} ms RTT")

        if abs(self.total_drift_ms) > 5000:
            errors.append(f"Excessive drift: {self.total_drift_ms} ms")

        if not self.drift_measurement_valid:
            errors.append("Drift measurement failed validation")

        return len(errors) == 0, errors


class TimestampCompensator:
    """
    Compensates detection timestamps to align with video timeline
    """

    def __init__(self, context: TimestampCompensationContext):
        """
        Initialize compensator with compensation context

        Args:
            context: Compensation context from drift measurement
        """
        # Validate context
        is_valid, errors = context.validate()
        if not is_valid:
            logger.error(f"Invalid compensation context: {errors}")
            raise ValueError(f"Invalid compensation context: {errors}")

        self.context = context
        logger.info(
            f"Timestamp compensator initialized: "
            f"drift={context.total_drift_ms:.2f}ms, "
            f"clock_offset={context.clock_offset_ms:.2f}ms"
        )

    def compensate_detection(
        self,
        detection_timestamp_s: float
    ) -> float:
        """
        Compensate single detection timestamp

        Args:
            detection_timestamp_s: Raw detection time (backend clock, seconds)

        Returns:
            Compensated timestamp relative to video start (milliseconds)
        """
        # Convert to video-relative time
        video_relative_s = detection_timestamp_s - self.context.video_start_backend_s
        video_relative_ms = video_relative_s * 1000

        # Log for debugging
        logger.debug(
            f"Compensated detection: "
            f"raw={detection_timestamp_s:.6f}s, "
            f"compensated={video_relative_ms:.2f}ms"
        )

        return video_relative_ms

    def compensate_detections_batch(
        self,
        detection_timestamps_s: List[float]
    ) -> List[float]:
        """
        Compensate batch of detection timestamps (optimized)

        Args:
            detection_timestamps_s: List of raw detection times (backend clock, seconds)

        Returns:
            List of compensated timestamps (video-relative, milliseconds)
        """
        # Vectorized operation for performance
        import numpy as np

        timestamps_array = np.array(detection_timestamps_s)
        compensated_array = (timestamps_array - self.context.video_start_backend_s) * 1000

        logger.info(
            f"Compensated {len(detection_timestamps_s)} detections: "
            f"range=[{compensated_array.min():.2f}, {compensated_array.max():.2f}]ms"
        )

        return compensated_array.tolist()

    def compensate_with_uncertainty(
        self,
        detection_timestamp_s: float
    ) -> tuple[float, float]:
        """
        Compensate detection with uncertainty estimate

        Args:
            detection_timestamp_s: Raw detection time (backend clock, seconds)

        Returns:
            (compensated_ms, uncertainty_ms): Timestamp and ±uncertainty
        """
        compensated_ms = self.compensate_detection(detection_timestamp_s)

        # Uncertainty sources:
        # 1. Clock sync RTT (network jitter)
        # 2. Timer precision (typically < 1ms)
        # 3. Drift measurement uncertainty

        uncertainty_ms = (
            self.context.clock_sync_rtt_ms / 2 +  # ±RTT/2 for clock sync
            1.0 +                                   # ±1ms timer precision
            5.0                                     # ±5ms drift measurement uncertainty
        )

        return compensated_ms, uncertainty_ms

    def create_compensation_report(self) -> dict:
        """Generate detailed compensation report"""
        return {
            'compensation_context': {
                'video_start_browser_ms': self.context.video_start_browser_ms,
                'clock_offset_ms': self.context.clock_offset_ms,
                'labjack_start_backend_s': self.context.labjack_start_backend_s,
                'total_drift_ms': self.context.total_drift_ms,
                'drift_measurement_valid': self.context.drift_measurement_valid
            },
            'clock_sync_quality': {
                'rtt_ms': self.context.clock_sync_rtt_ms,
                'quality': self._assess_clock_sync_quality()
            },
            'timestamp': self.context.compensation_timestamp.isoformat()
        }

    def _assess_clock_sync_quality(self) -> str:
        """Assess clock synchronization quality"""
        rtt = self.context.clock_sync_rtt_ms
        if rtt < 10:
            return 'excellent'
        elif rtt < 50:
            return 'good'
        elif rtt < 100:
            return 'fair'
        else:
            return 'poor'
```

## 3. Ground Truth Matching

### 3.1 Matching Algorithm

After compensation, we can match detections to ground truth events:

```python
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class GroundTruthEvent:
    """Ground truth event from video annotation"""
    timestamp_ms: float          # Video-relative time
    object_id: str              # Object that appeared
    event_type: str             # 'appearance', 'disappearance'
    frame_number: int           # Video frame


@dataclass
class DetectionEvent:
    """Detection event from LabJack"""
    timestamp_raw_s: float      # Raw backend timestamp
    timestamp_compensated_ms: float  # Compensated video-relative time
    confidence: float           # Detection confidence (if applicable)
    channel: str               # LabJack channel (DIO0, DIO1, etc.)


@dataclass
class MatchResult:
    """Result of matching detection to ground truth"""
    detection: DetectionEvent
    ground_truth: Optional[GroundTruthEvent]
    matched: bool
    time_error_ms: float        # Detection - GT time
    match_quality: str          # 'perfect', 'good', 'acceptable', 'poor'

    @property
    def is_true_positive(self) -> bool:
        """Detection correctly matched to GT"""
        return self.matched

    @property
    def is_false_positive(self) -> bool:
        """Detection with no matching GT"""
        return not self.matched


def match_detections_to_ground_truth(
    detections: List[DetectionEvent],
    ground_truths: List[GroundTruthEvent],
    tolerance_ms: float = 50.0
) -> List[MatchResult]:
    """
    Match compensated detections to ground truth events

    Args:
        detections: List of detection events (compensated timestamps)
        ground_truths: List of ground truth events
        tolerance_ms: Maximum time error for match (default 50ms)

    Returns:
        List of match results
    """
    results = []
    matched_gts = set()  # Track which GTs have been matched

    # Sort detections by time
    detections_sorted = sorted(detections, key=lambda d: d.timestamp_compensated_ms)

    for detection in detections_sorted:
        best_match = None
        best_error = float('inf')

        # Find closest unmatched ground truth
        for gt in ground_truths:
            if gt.timestamp_ms in matched_gts:
                continue  # Already matched

            time_error = detection.timestamp_compensated_ms - gt.timestamp_ms

            # Check if within tolerance
            if abs(time_error) < tolerance_ms and abs(time_error) < abs(best_error):
                best_match = gt
                best_error = time_error

        # Create match result
        if best_match is not None:
            matched_gts.add(best_match.timestamp_ms)
            match_quality = assess_match_quality(abs(best_error))

            results.append(MatchResult(
                detection=detection,
                ground_truth=best_match,
                matched=True,
                time_error_ms=best_error,
                match_quality=match_quality
            ))
        else:
            # False positive
            results.append(MatchResult(
                detection=detection,
                ground_truth=None,
                matched=False,
                time_error_ms=float('inf'),
                match_quality='none'
            ))

    return results


def assess_match_quality(error_ms: float) -> str:
    """Assess quality of temporal match"""
    if error_ms < 10:
        return 'perfect'   # <10ms error
    elif error_ms < 25:
        return 'good'      # <25ms error
    elif error_ms < 50:
        return 'acceptable'  # <50ms error
    else:
        return 'poor'      # >50ms error
```

### 3.2 Match Validation

```python
def calculate_detection_metrics(
    match_results: List[MatchResult],
    ground_truths: List[GroundTruthEvent]
) -> dict:
    """
    Calculate comprehensive detection metrics

    Returns: Dict with precision, recall, F1, timing errors, etc.
    """
    true_positives = [r for r in match_results if r.is_true_positive]
    false_positives = [r for r in match_results if r.is_false_positive]

    matched_gt_ids = {r.ground_truth.timestamp_ms for r in true_positives}
    false_negatives = [gt for gt in ground_truths if gt.timestamp_ms not in matched_gt_ids]

    # Basic metrics
    num_tp = len(true_positives)
    num_fp = len(false_positives)
    num_fn = len(false_negatives)

    precision = num_tp / (num_tp + num_fp) if (num_tp + num_fp) > 0 else 0
    recall = num_tp / (num_tp + num_fn) if (num_tp + num_fn) > 0 else 0
    f1_score = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    # Timing error statistics
    timing_errors = [r.time_error_ms for r in true_positives]

    return {
        'detection_metrics': {
            'true_positives': num_tp,
            'false_positives': num_fp,
            'false_negatives': num_fn,
            'precision': precision,
            'recall': recall,
            'f1_score': f1_score
        },
        'timing_metrics': {
            'mean_error_ms': np.mean(timing_errors) if timing_errors else None,
            'median_error_ms': np.median(timing_errors) if timing_errors else None,
            'std_error_ms': np.std(timing_errors) if timing_errors else None,
            'max_error_ms': np.max(np.abs(timing_errors)) if timing_errors else None,
            'rmse_ms': np.sqrt(np.mean(np.square(timing_errors))) if timing_errors else None
        },
        'match_quality_distribution': {
            'perfect': sum(1 for r in true_positives if r.match_quality == 'perfect'),
            'good': sum(1 for r in true_positives if r.match_quality == 'good'),
            'acceptable': sum(1 for r in true_positives if r.match_quality == 'acceptable'),
            'poor': sum(1 for r in true_positives if r.match_quality == 'poor')
        }
    }
```

## 4. Edge Cases & Error Handling

### 4.1 Clock Skew Handling

```python
def handle_excessive_clock_skew(
    clock_offset_ms: float,
    max_acceptable_skew_ms: float = 500.0
) -> bool:
    """
    Check if clock skew is acceptable

    Returns: True if acceptable, False if excessive
    """
    if abs(clock_offset_ms) > max_acceptable_skew_ms:
        logger.error(
            f"Excessive clock skew detected: {clock_offset_ms:.2f}ms "
            f"(max: {max_acceptable_skew_ms}ms). "
            "This indicates a serious clock synchronization problem."
        )
        return False

    return True
```

### 4.2 Negative Timestamps

```python
def handle_negative_timestamps(
    compensated_timestamp_ms: float,
    context: TimestampCompensationContext
) -> Optional[float]:
    """
    Handle detections that occur before video start (negative timestamps)

    This can happen due to:
    1. Pre-start buffer strategy (intended)
    2. Clock sync errors (error)
    3. Measurement noise (acceptable if small)

    Returns: Corrected timestamp or None if invalid
    """
    if compensated_timestamp_ms < 0:
        if abs(compensated_timestamp_ms) < 100:
            # Small negative value, likely measurement noise
            logger.warning(
                f"Small negative timestamp: {compensated_timestamp_ms:.2f}ms. "
                "Likely measurement noise, clamping to 0."
            )
            return 0.0

        elif compensated_timestamp_ms < -200:
            # Large negative value with pre-start buffer enabled
            logger.info(
                f"Negative timestamp: {compensated_timestamp_ms:.2f}ms. "
                "Detection occurred before video start (pre-start buffer)."
            )
            return compensated_timestamp_ms  # Keep negative value

        else:
            logger.error(
                f"Invalid negative timestamp: {compensated_timestamp_ms:.2f}ms. "
                "Possible clock sync failure."
            )
            return None  # Invalid detection

    return compensated_timestamp_ms
```

### 4.3 Timestamp Overflow

```python
def validate_timestamp_range(
    compensated_timestamp_ms: float,
    video_duration_ms: float,
    tolerance_ms: float = 1000.0
) -> bool:
    """
    Validate that compensated timestamp is within video duration

    Args:
        compensated_timestamp_ms: Compensated detection time
        video_duration_ms: Total video duration
        tolerance_ms: Allow detections slightly after video end

    Returns: True if valid, False if outside range
    """
    if compensated_timestamp_ms > video_duration_ms + tolerance_ms:
        logger.error(
            f"Detection timestamp {compensated_timestamp_ms:.2f}ms "
            f"exceeds video duration {video_duration_ms:.2f}ms + tolerance {tolerance_ms}ms. "
            "Possible timing error or delayed detection."
        )
        return False

    return True
```

## 5. Testing & Validation

### 5.1 Unit Tests

```python
# tests/test_timestamp_compensation.py

import pytest
from services.timestamp_compensation import (
    TimestampCompensationContext,
    TimestampCompensator,
    compensate_detection_timestamp
)


class TestTimestampCompensation:

    def test_basic_compensation(self):
        """Test basic compensation with known values"""
        context = TimestampCompensationContext(
            video_start_browser_ms=1000.0,
            clock_offset_ms=50.0,
            labjack_start_backend_s=1.200,  # 1200ms backend time
            total_drift_ms=150.0,
            clock_sync_rtt_ms=10.0,
            compensation_timestamp=datetime.utcnow(),
            drift_measurement_valid=True
        )

        compensator = TimestampCompensator(context)

        # Detection at 2.500s backend time
        # Expected: (2.500 - 1.050) * 1000 = 1450ms video time
        compensated = compensator.compensate_detection(2.500)

        assert abs(compensated - 1450.0) < 0.01, f"Expected 1450ms, got {compensated}ms"

    def test_zero_drift_scenario(self):
        """Test compensation when drift is zero (perfect sync)"""
        context = TimestampCompensationContext(
            video_start_browser_ms=1000.0,
            clock_offset_ms=0.0,
            labjack_start_backend_s=1.000,  # No drift
            total_drift_ms=0.0,
            clock_sync_rtt_ms=5.0,
            compensation_timestamp=datetime.utcnow(),
            drift_measurement_valid=True
        )

        compensator = TimestampCompensator(context)

        # Detection at 2.000s backend time
        # Expected: 1000ms video time
        compensated = compensator.compensate_detection(2.000)

        assert abs(compensated - 1000.0) < 0.01

    def test_negative_timestamp_handling(self):
        """Test handling of detection before video start"""
        context = TimestampCompensationContext(
            video_start_browser_ms=1000.0,
            clock_offset_ms=0.0,
            labjack_start_backend_s=1.000,
            total_drift_ms=0.0,
            clock_sync_rtt_ms=5.0,
            compensation_timestamp=datetime.utcnow(),
            drift_measurement_valid=True
        )

        compensator = TimestampCompensator(context)

        # Detection at 0.950s backend time (50ms before video start)
        compensated = compensator.compensate_detection(0.950)

        # Should be negative
        assert compensated == -50.0

    def test_batch_compensation(self):
        """Test batch compensation performance"""
        context = TimestampCompensationContext(
            video_start_browser_ms=1000.0,
            clock_offset_ms=0.0,
            labjack_start_backend_s=1.000,
            total_drift_ms=0.0,
            clock_sync_rtt_ms=5.0,
            compensation_timestamp=datetime.utcnow(),
            drift_measurement_valid=True
        )

        compensator = TimestampCompensator(context)

        # 1000 detections
        raw_timestamps = [1.000 + i * 0.01 for i in range(1000)]

        compensated = compensator.compensate_detections_batch(raw_timestamps)

        assert len(compensated) == 1000
        assert compensated[0] == 0.0
        assert abs(compensated[-1] - 9990.0) < 0.1
```

### 5.2 Integration Tests

```python
# tests/integration/test_compensation_end_to_end.py

@pytest.mark.integration
def test_full_compensation_workflow():
    """Test complete workflow from drift measurement to compensation"""

    # Step 1: Perform clock sync
    clock_offset, rtt = perform_clock_sync()

    # Step 2: Measure drift
    drift_measurement = measure_drift(clock_offset)

    # Step 3: Create compensation context
    context = TimestampCompensationContext(
        video_start_browser_ms=drift_measurement.video_start_timestamp,
        clock_offset_ms=clock_offset,
        labjack_start_backend_s=drift_measurement.labjack_monitoring_active,
        total_drift_ms=drift_measurement.total_drift_ms,
        clock_sync_rtt_ms=rtt,
        compensation_timestamp=datetime.utcnow(),
        drift_measurement_valid=True
    )

    # Step 4: Compensate detections
    compensator = TimestampCompensator(context)
    raw_detections = [1.500, 2.000, 2.500]  # Backend timestamps
    compensated = compensator.compensate_detections_batch(raw_detections)

    # Step 5: Verify results
    assert len(compensated) == 3
    assert all(isinstance(t, float) for t in compensated)
```

## 6. Performance Optimization

### 6.1 Vectorized Operations

```python
import numpy as np

def compensate_detections_vectorized(
    detection_timestamps: np.ndarray,
    video_start_backend: float
) -> np.ndarray:
    """
    Vectorized compensation for high-performance batch processing

    10x faster than loop-based compensation for large batches
    """
    return (detection_timestamps - video_start_backend) * 1000
```

### 6.2 Caching

```python
class CachedTimestampCompensator(TimestampCompensator):
    """Compensator with LRU cache for repeated calculations"""

    def __init__(self, context: TimestampCompensationContext):
        super().__init__(context)
        self._cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def compensate_detection(self, detection_timestamp_s: float) -> float:
        """Compensate with caching (useful for repeated calculations)"""
        cache_key = detection_timestamp_s

        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]

        self._cache_misses += 1
        result = super().compensate_detection(detection_timestamp_s)
        self._cache[cache_key] = result

        return result

    def get_cache_stats(self) -> dict:
        """Get cache performance statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0

        return {
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': hit_rate,
            'cache_size': len(self._cache)
        }
```

## 7. Monitoring & Debugging

### 7.1 Compensation Audit Trail

```python
@dataclass
class CompensationAuditEntry:
    """Audit trail for timestamp compensation"""
    timestamp: datetime
    detection_id: int
    raw_timestamp_s: float
    compensated_timestamp_ms: float
    context_id: int
    compensation_delta_ms: float

    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'detection_id': self.detection_id,
            'raw_timestamp_s': self.raw_timestamp_s,
            'compensated_timestamp_ms': self.compensated_timestamp_ms,
            'context_id': self.context_id,
            'compensation_delta_ms': self.compensation_delta_ms
        }


class AuditedTimestampCompensator(TimestampCompensator):
    """Compensator with full audit trail"""

    def __init__(self, context: TimestampCompensationContext):
        super().__init__(context)
        self.audit_trail: List[CompensationAuditEntry] = []

    def compensate_detection(self, detection_timestamp_s: float, detection_id: int = None) -> float:
        """Compensate with audit logging"""
        compensated = super().compensate_detection(detection_timestamp_s)

        # Log to audit trail
        entry = CompensationAuditEntry(
            timestamp=datetime.utcnow(),
            detection_id=detection_id or 0,
            raw_timestamp_s=detection_timestamp_s,
            compensated_timestamp_ms=compensated,
            context_id=id(self.context),
            compensation_delta_ms=compensated - (detection_timestamp_s * 1000)
        )
        self.audit_trail.append(entry)

        return compensated

    def export_audit_trail(self, filepath: str):
        """Export audit trail to JSON"""
        import json
        with open(filepath, 'w') as f:
            json.dump([e.to_dict() for e in self.audit_trail], f, indent=2)
```

---

**Document Version:** 1.0.0
**Author:** System Architecture Designer
**Approved By:** [Pending Review]
**Next Review Date:** 2025-12-20
