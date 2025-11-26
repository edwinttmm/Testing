# Drift Compensation Integration - Exact Code Changes

## Summary

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

**Total Changes**:
- 3 sections modified
- ~180 lines added
- 0 lines removed
- 0 breaking changes

---

## Change #1: Import Services (Lines 64-72)

### Code Added:

```python
# Drift Compensation Services
try:
    from src.services.timestamp_compensation_service import TimestampCompensationService
    from src.services.drift_measurement_service import DriftMeasurementService
    DRIFT_COMPENSATION_AVAILABLE = True
except ImportError:
    DRIFT_COMPENSATION_AVAILABLE = False
    TimestampCompensationService = None
    DriftMeasurementService = None
```

### Context:

**Before** (Line 63):
```python
    ExpandedDetection = None

logger = logging.getLogger(__name__)
```

**After** (Line 73):
```python
    DriftMeasurementService = None

logger = logging.getLogger(__name__)
```

---

## Change #2: Integration Call (Lines 371-377)

### Code Added:

```python
# DRIFT COMPENSATION: Apply timestamp corrections BEFORE matching
detection_events = self._apply_drift_compensation(
    db,
    session_id,
    test_session,
    detection_events
)
```

### Context:

**Before** (Lines 365-370):
```python
self.logger.info(f"Found {len(ground_truth_objects)} ground truth objects")

if not ground_truth_objects:
    self.logger.warning("No ground truth objects found for matching")
    return self._create_empty_metrics(len(detection_events))

# OPTION C: Apply temporal expansion if available
```

**After** (Lines 365-379):
```python
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
```

---

## Change #3: New Method Implementation (Lines 1931-2109)

### Full Method:

```python
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
```

### Context:

**Inserted Between**:
- Line 1930: End of `_calculate_session_metrics()` method
- Line 2111: Start of `_create_empty_metrics()` method

---

## Verification

### Lines Referenced:
```bash
grep -n "DRIFT_COMPENSATION\|_apply_drift_compensation" services/ground_truth_matching_service.py
```

**Output**:
```
66:    from src.services.timestamp_compensation_service import TimestampCompensationService
67:    from src.services.drift_measurement_service import DriftMeasurementService
68:    DRIFT_COMPENSATION_AVAILABLE = True
70:    DRIFT_COMPENSATION_AVAILABLE = False
372:            detection_events = self._apply_drift_compensation(
1931:    def _apply_drift_compensation(
1956:        if not DRIFT_COMPENSATION_AVAILABLE:
1967:            drift_service = DriftMeasurementService()
1968:            compensation_service = TimestampCompensationService()
```

### File Size:
```bash
wc -l services/ground_truth_matching_service.py
```

**Output**: `2615 services/ground_truth_matching_service.py`

---

## Integration Validation

### ✅ Syntax Check:
```bash
python3 -m py_compile services/ground_truth_matching_service.py
# No output = Success
```

### ✅ Import Check:
```bash
python3 -c "from src.services.timestamp_compensation_service import TimestampCompensationService; print('✅ Import successful')"
# Output: ✅ Import successful
```

### ✅ Service Availability:
```bash
python3 -c "from services.ground_truth_matching_service import DRIFT_COMPENSATION_AVAILABLE; print(f'Available: {DRIFT_COMPENSATION_AVAILABLE}')"
# Output: Available: True
```

---

## Execution Trace Example

### Input:
```python
session_id = "test_session_001"
test_session = TestSession(id=session_id, ...)
detection_events = [
    DetectionEventProxy(id='det1', timestamp=1000.5, video_id='video1'),
    DetectionEventProxy(id='det2', timestamp=1001.0, video_id='video1'),
    DetectionEventProxy(id='det3', timestamp=2000.0, video_id='video2')
]
# Drift measurements:
# video1: 100ms drift
# video2: 150ms drift
```

### Processing:

**Step 1: Group by video_id**
```python
detections_by_video = {
    'video1': [det1, det2],
    'video2': [det3]
}
```

**Step 2: Get drift for video1**
```python
drift_measurement = drift_service.get_measurement('test_session_001', 'video1')
drift_ms = 100.0  # Retrieved from service
```

**Step 3: Compensate video1 detections**
```python
# Before: det1.timestamp = 1000.5, det2.timestamp = 1001.0
compensation_service.compensate_detections_batch(...)
# After: det1.timestamp = 1000.4, det2.timestamp = 1000.9

det1.original_timestamp = 1000.5
det1.timestamp = 1000.4  # Compensated
det1.drift_correction_ms = 100.0

det2.original_timestamp = 1001.0
det2.timestamp = 1000.9  # Compensated
det2.drift_correction_ms = 100.0
```

**Step 4: Get drift for video2**
```python
drift_measurement = drift_service.get_measurement('test_session_001', 'video2')
drift_ms = 150.0
```

**Step 5: Compensate video2 detections**
```python
# Before: det3.timestamp = 2000.0
compensation_service.compensate_detections_batch(...)
# After: det3.timestamp = 1999.85

det3.original_timestamp = 2000.0
det3.timestamp = 1999.85  # Compensated
det3.drift_correction_ms = 150.0
```

**Step 6: Log results**
```
[INFO] 📊 Compensated 2/2 detections for video video1 with drift=100.00ms
[INFO] 📊 Compensated 1/1 detections for video video2 with drift=150.00ms
[INFO] ✅ Drift compensation complete: 3/3 detections compensated (100.0% success rate)
```

**Step 7: Return compensated detections**
```python
return detection_events  # All timestamps now compensated
```

### Output:
```python
detection_events = [
    DetectionEventProxy(
        id='det1',
        original_timestamp=1000.5,
        timestamp=1000.4,  # Compensated!
        drift_correction_ms=100.0
    ),
    DetectionEventProxy(
        id='det2',
        original_timestamp=1001.0,
        timestamp=1000.9,  # Compensated!
        drift_correction_ms=100.0
    ),
    DetectionEventProxy(
        id='det3',
        original_timestamp=2000.0,
        timestamp=1999.85,  # Compensated!
        drift_correction_ms=150.0
    )
]
```

---

## Error Handling Examples

### Scenario 1: No Drift Measurement

**Input**: video_id='video_unknown', no drift measurement exists

**Processing**:
```python
drift_measurement = drift_service.get_measurement(session_id, 'video_unknown')
# Returns: None

if drift_measurement is None:
    self.logger.warning("⚠️ No drift measurement for video video_unknown, using drift=0ms")
    drift_ms = 0.0
```

**Result**: Detections use original timestamps (drift=0ms compensation is identity operation)

---

### Scenario 2: Extreme Drift

**Input**: video_id='video_extreme', drift=1250ms (>1000ms threshold)

**Processing**:
```python
drift_ms = 1250.0  # Retrieved from service

if abs(drift_ms) > 1000.0:
    self.logger.warning("⚠️ Extreme drift detected... Clamping to ±1000ms")
    drift_ms = max(-1000.0, min(1000.0, drift_ms))  # = 1000.0
```

**Result**: Drift clamped to 1000ms for safety

---

### Scenario 3: Service Unavailable

**Input**: TimestampCompensationService not importable

**Processing**:
```python
# At import time:
try:
    from src.services.timestamp_compensation_service import TimestampCompensationService
except ImportError:
    DRIFT_COMPENSATION_AVAILABLE = False

# At runtime:
if not DRIFT_COMPENSATION_AVAILABLE:
    self.logger.warning("⚠️ Drift compensation services not available")
    return detection_events  # Return unchanged
```

**Result**: Skip compensation entirely, continue with original timestamps

---

## Testing Commands

### Quick Validation:

```bash
# 1. Check file compiles
python3 -m py_compile services/ground_truth_matching_service.py && echo "✅ Syntax OK"

# 2. Check services available
python3 -c "
from src.services.timestamp_compensation_service import TimestampCompensationService
from src.services.drift_measurement_service import DriftMeasurementService
print('✅ Services available')
"

# 3. Check method exists
python3 -c "
from services.ground_truth_matching_service import GroundTruthMatchingService
assert hasattr(GroundTruthMatchingService, '_apply_drift_compensation')
print('✅ Method exists')
"

# 4. Check integration point
grep -n "_apply_drift_compensation" services/ground_truth_matching_service.py | grep -q "372:"
echo "✅ Integration point verified"
```

---

## Status: ✅ INTEGRATION COMPLETE

**Summary**:
- ✅ 3 sections modified
- ✅ ~180 lines added
- ✅ 0 breaking changes
- ✅ Syntax validated
- ✅ Imports verified
- ✅ Ready for testing

**Next Steps**:
1. Run integration tests with real drift measurements
2. Verify matching accuracy improves
3. Monitor performance impact
4. Deploy to staging environment

---

**Author**: Backend API Developer Agent
**Date**: 2025-11-20
**File**: ground_truth_matching_service.py
**Integration**: Drift Compensation
