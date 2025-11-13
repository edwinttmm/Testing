# Agent #5: Clock Synchronization Validation

## Mission
Add clock skew detection and handling to prevent negative latency and cross-video timestamp errors.

## Problem Statement
**3 different clock sources** exist in the system:
1. **LabJack hardware clock** - Generates detection timestamps
2. **Video playback clock** - Generates frame timestamps
3. **System clock (Python `time.time()`)** - Generates session timestamps

**Current Risk:** If clocks drift >100ms, detections can be assigned to wrong video or show negative latency.

## Implementation

### Step 1: Add Clock Synchronization Service

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/services/clock_sync_service.py

"""
Clock Synchronization Validation Service

Detects and alerts on clock skew between hardware, video, and system clocks.

CRITICAL: Clock skew >100ms can cause:
- Negative latency values
- Cross-video detection assignment errors
- Incorrect timing calculations
"""

import logging
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class ClockSkewReport:
    """Clock skew analysis results"""
    has_skew: bool
    skew_ms: float
    clock_source_1: str
    clock_source_2: str
    timestamp_1: float
    timestamp_2: float
    severity: str  # 'acceptable', 'warning', 'critical'
    recommendation: str

class ClockSynchronizationService:
    """Validate clock synchronization across system components"""

    # Skew thresholds (milliseconds)
    ACCEPTABLE_SKEW_MS = 50    # <50ms: No action needed
    WARNING_SKEW_MS = 100      # 50-100ms: Log warning
    CRITICAL_SKEW_MS = 500     # >100ms: Reject session

    def __init__(self):
        self._reference_time: Optional[float] = None
        self._reference_source: Optional[str] = None

    def set_reference_time(self, timestamp: float, source: str = "system"):
        """
        Set reference time for session (call at session start).

        Args:
            timestamp: Unix epoch timestamp (seconds)
            source: Clock source identifier
        """
        self._reference_time = timestamp
        self._reference_source = source
        logger.info(f"Clock reference set: {timestamp:.6f} from {source}")

    def check_clock_skew(
        self,
        timestamp: float,
        source: str,
        expected_time: Optional[float] = None
    ) -> ClockSkewReport:
        """
        Check if timestamp shows acceptable clock skew.

        Args:
            timestamp: Timestamp to validate (seconds)
            source: Source of this timestamp
            expected_time: Expected timestamp for comparison (optional)

        Returns:
            ClockSkewReport with analysis results
        """
        if expected_time is None and self._reference_time is not None:
            expected_time = self._reference_time

        if expected_time is None:
            # No reference - accept first timestamp
            return ClockSkewReport(
                has_skew=False,
                skew_ms=0.0,
                clock_source_1=source,
                clock_source_2="none",
                timestamp_1=timestamp,
                timestamp_2=0.0,
                severity="acceptable",
                recommendation="First timestamp - set as reference"
            )

        # Calculate skew
        skew_seconds = timestamp - expected_time
        skew_ms = abs(skew_seconds * 1000.0)

        # Determine severity
        if skew_ms <= self.ACCEPTABLE_SKEW_MS:
            severity = "acceptable"
            has_skew = False
            recommendation = "Clock skew within acceptable range"
        elif skew_ms <= self.WARNING_SKEW_MS:
            severity = "warning"
            has_skew = True
            recommendation = f"Clock skew detected ({skew_ms:.1f}ms). Monitor for drift."
        elif skew_ms <= self.CRITICAL_SKEW_MS:
            severity = "critical"
            has_skew = True
            recommendation = f"CRITICAL clock skew ({skew_ms:.1f}ms). Verify hardware clock sync."
        else:
            severity = "critical"
            has_skew = True
            recommendation = f"SEVERE clock skew ({skew_ms:.1f}ms). REJECT session - clock sync failed."

        report = ClockSkewReport(
            has_skew=has_skew,
            skew_ms=skew_ms,
            clock_source_1=source,
            clock_source_2=self._reference_source or "unknown",
            timestamp_1=timestamp,
            timestamp_2=expected_time,
            severity=severity,
            recommendation=recommendation
        )

        # Log based on severity
        if severity == "critical":
            logger.error(
                f"❌ CRITICAL CLOCK SKEW: {skew_ms:.1f}ms between {source} and {self._reference_source}. "
                f"{recommendation}"
            )
        elif severity == "warning":
            logger.warning(
                f"⚠️  Clock skew warning: {skew_ms:.1f}ms between {source} and {self._reference_source}"
            )
        else:
            logger.debug(f"✅ Clock sync OK: skew={skew_ms:.1f}ms")

        return report

    def validate_detection_timestamp(
        self,
        detection_timestamp: float,
        video_start_time: Optional[float] = None,
        video_duration: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate detection timestamp is reasonable.

        Args:
            detection_timestamp: Detection epoch timestamp (seconds)
            video_start_time: Video start epoch timestamp (seconds)
            video_duration: Video duration (seconds)

        Returns:
            (is_valid, error_message)
        """
        # Check for negative latency (detection before video start)
        if video_start_time is not None:
            latency_ms = (detection_timestamp - video_start_time) * 1000.0

            # Allow small negative values due to grace period
            if latency_ms < -2000:  # More than 2s before video start
                return False, f"Detection timestamp {latency_ms:.1f}ms before video start (clock skew?)"

            # Detect unreasonably high latency (clock drift)
            if latency_ms > 10000:  # More than 10s after video start
                if video_duration and latency_ms > (video_duration * 1000 + 2000):
                    return False, f"Detection timestamp {latency_ms:.1f}ms after video start (exceeds duration)"

        # Check for timestamps in the far future or past
        current_time = time.time()
        time_diff_hours = abs(detection_timestamp - current_time) / 3600.0

        if time_diff_hours > 24:
            return False, f"Detection timestamp {time_diff_hours:.1f} hours from current time (wrong epoch?)"

        return True, None

# Global singleton
_clock_sync_service: Optional[ClockSynchronizationService] = None

def get_clock_sync_service() -> ClockSynchronizationService:
    """Get global clock sync service instance"""
    global _clock_sync_service
    if _clock_sync_service is None:
        _clock_sync_service = ClockSynchronizationService()
    return _clock_sync_service
```

### Step 2: Integration with Detection Pipeline

```python
# In detection_video_assignment.py or labjack_detection_service.py

from services.clock_sync_service import get_clock_sync_service

def process_detection_event(detection_timestamp: float, video_start_time: float, ...):
    # Validate clock sync BEFORE assigning video
    clock_sync = get_clock_sync_service()

    is_valid, error_msg = clock_sync.validate_detection_timestamp(
        detection_timestamp=detection_timestamp,
        video_start_time=video_start_time,
        video_duration=video.duration
    )

    if not is_valid:
        logger.error(f"❌ Rejecting detection due to clock sync issue: {error_msg}")
        # Store detection with error flag
        detection.validation_result = "REJECTED_CLOCK_SKEW"
        detection.validation_error = error_msg
        return None

    # Check skew against expected time
    skew_report = clock_sync.check_clock_skew(
        timestamp=detection_timestamp,
        source="labjack",
        expected_time=video_start_time
    )

    if skew_report.severity == "critical":
        logger.error(f"❌ CRITICAL clock skew detected: {skew_report.recommendation}")
        # Flag for manual review
        detection.clock_skew_warning = True
        detection.clock_skew_ms = skew_report.skew_ms
```

### Step 3: Session Initialization Check

```python
# In video_sequence_orchestrator.py or session startup

def start_sequence(...):
    clock_sync = get_clock_sync_service()

    # Set reference time at session start
    session_start_time = time.time()
    clock_sync.set_reference_time(session_start_time, source="system")

    logger.info(f"Session started with reference time: {session_start_time:.6f}")
```

## Testing Strategy

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/tests/test_clock_sync_validation.py

import pytest
import time
from services.clock_sync_service import ClockSynchronizationService

class TestClockSyncValidation:

    def test_acceptable_skew(self):
        """Skew <50ms should be acceptable"""
        service = ClockSynchronizationService()
        service.set_reference_time(1000.0, "system")

        report = service.check_clock_skew(1000.040, "labjack")  # 40ms skew
        assert report.severity == "acceptable"
        assert not report.has_skew

    def test_warning_skew(self):
        """Skew 50-100ms should trigger warning"""
        service = ClockSynchronizationService()
        service.set_reference_time(1000.0, "system")

        report = service.check_clock_skew(1000.075, "labjack")  # 75ms skew
        assert report.severity == "warning"
        assert report.has_skew

    def test_critical_skew(self):
        """Skew >100ms should be critical"""
        service = ClockSynchronizationService()
        service.set_reference_time(1000.0, "system")

        report = service.check_clock_skew(1000.150, "labjack")  # 150ms skew
        assert report.severity == "critical"
        assert report.has_skew

    def test_negative_latency_detection(self):
        """Detection >2s before video start should be rejected"""
        service = ClockSynchronizationService()

        video_start = 1000.0
        detection_ts = 997.5  # 2.5s before video start

        is_valid, error = service.validate_detection_timestamp(
            detection_timestamp=detection_ts,
            video_start_time=video_start
        )

        assert not is_valid
        assert "before video start" in error
```

## Deployment Checklist
- [ ] Add `clock_sync_service.py` to services/
- [ ] Integrate validation in detection pipeline
- [ ] Add clock skew fields to DetectionEvent model
- [ ] Run test suite to verify skew detection
- [ ] Monitor first 10 production sessions for clock sync warnings

## Success Criteria
- [ ] Zero "negative latency" errors in logs
- [ ] Clock skew >100ms triggers alerts
- [ ] Detections with critical skew are flagged for review
- [ ] System automatically rejects sessions with >500ms skew
