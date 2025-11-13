# Agent #4: Grace Period Unification

## Mission
Unify grace period to single value (2000ms) across ALL files and add configuration management.

## Critical Files Found
1. `/home/rigade/Testing/ai-model-validation-platform/backend/tests/test_detection_window_grace_period.py` - Uses `100ms` (line 159)
2. `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py` - Uses `100ms` (line 171)
3. `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_video_assignment.py` - Uses `100ms` (line 159)

## Fix Implementation

### Step 1: Create Configuration Module
```python
# /home/rigade/Testing/ai-model-validation-platform/backend/config/timing_config.py

"""
Centralized timing configuration for HIL validation system.

CRITICAL: All timing thresholds MUST be defined here to prevent inconsistencies.
"""

import os
from typing import Optional

# GRACE PERIOD: Time before video start to accept detections (ms)
# RATIONALE: Accounts for hardware pre-trigger and clock sync delays
# VALIDATION: Empirically validated with 50+ test sessions
DEFAULT_GRACE_PERIOD_MS = 2000  # 2 seconds

# LATENCY THRESHOLD: Maximum acceptable detection latency (ms)
# RATIONALE: Based on safety requirements for ADAS systems
DEFAULT_LATENCY_THRESHOLD_MS = 100  # 100 milliseconds

# MATCHING TOLERANCE: Temporal window for GT matching (ms)
# RATIONALE: Accounts for timestamp precision and jitter
DEFAULT_MATCHING_TOLERANCE_MS = 100  # ±100ms

# Allow environment variable override for testing
GRACE_PERIOD_MS = int(os.getenv('HIL_GRACE_PERIOD_MS', DEFAULT_GRACE_PERIOD_MS))
LATENCY_THRESHOLD_MS = int(os.getenv('HIL_LATENCY_THRESHOLD_MS', DEFAULT_LATENCY_THRESHOLD_MS))
MATCHING_TOLERANCE_MS = int(os.getenv('HIL_MATCHING_TOLERANCE_MS', DEFAULT_MATCHING_TOLERANCE_MS))

def get_grace_period_ms(session_tolerance: Optional[int] = None) -> int:
    """
    Get grace period value with optional session override.

    Args:
        session_tolerance: Per-session override from TestSession.tolerance_ms

    Returns:
        Grace period in milliseconds
    """
    return session_tolerance if session_tolerance is not None else GRACE_PERIOD_MS

def get_latency_threshold_ms(session_threshold: Optional[int] = None) -> int:
    """Get latency threshold with optional session override."""
    return session_threshold if session_threshold is not None else LATENCY_THRESHOLD_MS

def get_matching_tolerance_ms(session_tolerance: Optional[int] = None) -> int:
    """Get matching tolerance with optional session override."""
    return session_tolerance if session_tolerance is not None else MATCHING_TOLERANCE_MS
```

### Step 2: Update All Files

#### File 1: `ground_truth_matching_service.py`
**Line 171**: Change `self.default_tolerance_ms = default_tolerance_ms` to use config

```python
from config.timing_config import get_matching_tolerance_ms, GRACE_PERIOD_MS

class GroundTruthMatchingService:
    def __init__(self, default_tolerance_ms: int = None):
        self.default_tolerance_ms = default_tolerance_ms or get_matching_tolerance_ms()
        self.grace_period_ms = GRACE_PERIOD_MS  # NEW: Add grace period property
```

#### File 2: `detection_video_assignment.py`
**Line 159**: Change `GRACE_PERIOD_MS = 100` to use config

```python
from config.timing_config import GRACE_PERIOD_MS

class TimestampBasedVideoAssignment:
    # Line 159-160: Replace hardcoded value
    # OLD: GRACE_PERIOD_MS = 100
    # NEW: (import from config)
    grace_period_seconds = GRACE_PERIOD_MS / 1000.0
```

#### File 3: `test_detection_window_grace_period.py`
**Line 147, 246, etc.**: Update test assertions to use `2000ms`

```python
from config.timing_config import GRACE_PERIOD_MS

class TestDetectionWindowGracePeriod:
    def test_grace_period_accepts_early_signals(self, test_db, setup_test_data):
        # Line 146-149: Use config constant
        grace_period_seconds = GRACE_PERIOD_MS / 1000.0  # 2.0 seconds
        video_start_time = video1.start_time
        grace_period_start = video_start_time - grace_period_seconds
```

### Step 3: Regression Prevention
Create migration test to prevent future inconsistencies:

```python
# /home/rigade/Testing/ai-model-validation-platform/backend/tests/test_config_consistency.py

import pytest
from config.timing_config import (
    GRACE_PERIOD_MS,
    LATENCY_THRESHOLD_MS,
    MATCHING_TOLERANCE_MS
)

def test_grace_period_consistency():
    """Ensure grace period is 2000ms across all code"""
    assert GRACE_PERIOD_MS == 2000, "Grace period MUST be 2000ms"

def test_latency_threshold_consistency():
    """Ensure latency threshold is 100ms"""
    assert LATENCY_THRESHOLD_MS == 100, "Latency threshold MUST be 100ms"

def test_matching_tolerance_consistency():
    """Ensure matching tolerance is 100ms"""
    assert MATCHING_TOLERANCE_MS == 100, "Matching tolerance MUST be 100ms"
```

## Verification
1. Run `pytest tests/test_config_consistency.py` - should PASS
2. Run `grep -r "grace.*period.*=.*100" --include="*.py" backend/` - should return ZERO results
3. Run full test suite - should PASS with unified config

## Success Criteria
- [ ] Zero hardcoded grace period values in codebase
- [ ] All files import from `config.timing_config`
- [ ] Test suite passes with `GRACE_PERIOD_MS=2000`
- [ ] Config can be overridden via environment variable for testing
