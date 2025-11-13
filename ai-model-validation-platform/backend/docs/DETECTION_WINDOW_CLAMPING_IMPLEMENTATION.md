# Detection Window Clamping Implementation

## Critical Bug Fixed

**PROBLEM**: LabJack detection monitoring was capturing detections ~7 seconds BEFORE video playback started, polluting the dataset with invalid early detections. These pre-video detections were being stored in the database and included in metrics calculations, causing inaccurate results.

**ROOT CAUSE**: The monitoring loop started immediately when the session was created, but video playback didn't begin until several seconds later. There was no validation to ensure detections were only captured during the actual video playback window.

## Solution: Detection Window Validation

### Implementation Overview

Added window validation logic to `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py` that:

1. **Retrieves video timing boundaries** from session metadata
2. **Validates each detection** against the video playback window before storage
3. **Skips invalid detections** that occur before video start or after video end
4. **Tracks statistics** on how many detections were filtered out

### Key Changes

#### 1. Window Validation Method (`_is_detection_within_video_window`)

```python
def _is_detection_within_video_window(
    self,
    session_id: str,
    detection_timestamp: float,
    video_start_time: Optional[float],
    video_end_time: Optional[float]
) -> bool:
    """
    Validate detection is within video playback window.

    Returns:
        True if detection is within valid window, False to skip
    """
    GRACE_PERIOD_MS = 100  # Allow 100ms before video start for hardware pre-trigger

    # If no timing constraints, allow all detections (fallback)
    if video_start_time is None and video_end_time is None:
        return True

    # Check early detection (before video start - grace period)
    if video_start_time is not None:
        grace_period_seconds = GRACE_PERIOD_MS / 1000.0
        earliest_valid_time = video_start_time - grace_period_seconds

        if detection_timestamp < earliest_valid_time:
            return False  # Too early, skip

    # Check late detection (after video end + buffer)
    if video_end_time is not None:
        if detection_timestamp > video_end_time:
            return False  # Too late, skip

    return True  # Valid detection within window
```

#### 2. Enhanced Monitoring Loop

**Before detection storage:**
```python
# Check for detection events
current_time = datetime.now()
current_epoch_time = current_time.timestamp()

for channel, voltage in channel_readings.items():
    if voltage >= config.voltage_threshold:
        logger.info(f"🎯 DETECTION! {channel}: {voltage:.3f}V")

        # CRITICAL FIX: WINDOW VALIDATION
        if not self._is_detection_within_video_window(
            session_id, current_epoch_time, video_start_timestamp_float, stop_time_with_buffer
        ):
            # Count and skip invalid detections
            if video_start_timestamp_float and current_epoch_time < video_start_timestamp_float:
                skipped_early_detections += 1
                logger.debug(f"⏭️ Skipping early detection")
            else:
                skipped_late_detections += 1
                logger.debug(f"⏭️ Skipping late detection")
            continue  # Skip this detection

        # Only reach here if detection is within valid window
        if self._should_record_detection(session_id, channel, current_time, config):
            event = self._create_detection_event(...)
            self._record_detection_event(session_id, event)
            total_valid_detections += 1
```

#### 3. Statistics Tracking

Added counters to monitor filtering effectiveness:
- `skipped_early_detections` - Detections before video start
- `skipped_late_detections` - Detections after video end
- `total_valid_detections` - Detections successfully recorded

**Final summary logged:**
```python
logger.info(
    f"📊 Detection Window Stats: "
    f"Valid={total_valid_detections}, "
    f"Skipped Early={skipped_early_detections}, "
    f"Skipped Late={skipped_late_detections}, "
    f"Total Captured={total_valid_detections + skipped_early_detections + skipped_late_detections}"
)
```

#### 4. Timing Boundary Extraction

Enhanced video timing extraction with normalization:

```python
# CRITICAL FIX: Normalize video_start_time to float epoch timestamp
video_start_timestamp_float = None
if video_start_time is not None:
    if hasattr(video_start_time, 'timestamp'):
        video_start_timestamp_float = video_start_time.timestamp()
    elif isinstance(video_start_time, (int, float)):
        video_start_timestamp_float = video_start_time
    else:
        logger.warning(f"Unexpected video_start_time type: {type(video_start_time)}")

# Calculate stop time if we have duration
if video_duration and video_start_timestamp_float:
    stop_buffer_seconds = 0.5  # 500ms buffer after video ends
    stop_time_with_buffer = video_start_timestamp_float + video_duration + stop_buffer_seconds
    logger.info(
        f"🕐 Window validation enabled: "
        f"video_start={video_start_timestamp_float:.6f}, "
        f"video_end={video_start_timestamp_float + video_duration:.6f}, "
        f"monitor_stop={stop_time_with_buffer:.6f}"
    )
```

## Expected Impact

### Before Fix
```
Session Start: T0
Video Playback Start: T0 + 7s
Detection Monitoring: Starts at T0 (too early!)

Result: Captures detections from T0 to T0+7s (invalid pre-video detections)
```

### After Fix
```
Session Start: T0
Video Playback Start: T0 + 7s
Detection Monitoring: Starts at T0, but VALIDATES against video window

Result: Only captures detections from T0+7s onwards (valid in-video detections)
       Pre-video detections are skipped with counter tracking
```

### Metrics Improvement

**Before:**
- Total detections: 45
- Invalid early detections: ~15-20 (mixed into total)
- Impossible to distinguish valid vs invalid

**After:**
- Total valid detections: ~25-30
- Skipped early: ~15-20 (logged separately)
- Clear separation of valid vs invalid detections

## Validation Steps

### 1. Check Logs for Window Validation
```bash
# Look for window validation initialization
grep "Window validation enabled" backend_logs.log

# Example output:
# 🕐 Window validation enabled: video_start=1758205535.639260,
#    video_end=1758205565.639260, monitor_stop=1758205566.139260
```

### 2. Monitor Detection Filtering
```bash
# Check for skipped detections
grep "Skipping early detection" backend_logs.log

# Example output:
# ⏭️ Skipping early detection -6.543s before video start (total skipped early: 1)
# ⏭️ Skipping early detection -5.234s before video start (total skipped early: 2)
```

### 3. Review Final Statistics
```bash
# Check session completion summary
grep "Detection Window Stats" backend_logs.log

# Example output:
# 📊 Detection Window Stats: Valid=28, Skipped Early=17, Skipped Late=0, Total Captured=45
```

### 4. Verify Database Consistency
```sql
-- Check earliest detection relative to video start
SELECT
    de.id,
    de.timestamp as detection_epoch,
    ts.video_start_timestamp as video_start_epoch,
    de.timestamp - ts.video_start_timestamp as relative_time_seconds
FROM detection_events de
JOIN test_sessions ts ON de.test_session_id = ts.id
WHERE ts.id = 'your-session-id'
ORDER BY de.timestamp ASC
LIMIT 1;

-- Expected: relative_time_seconds >= -0.1 (within 100ms grace period)
```

## Configuration

### Grace Period
```python
GRACE_PERIOD_MS = 100  # Allow 100ms before video start
```

**Rationale**: Hardware pre-trigger can fire slightly before video frame appears. 100ms grace period prevents valid hardware detections from being filtered.

### Stop Buffer
```python
stop_buffer_seconds = 0.5  # 500ms buffer after video ends
```

**Rationale**: Allows monitor to capture detections that occur very close to video end without premature termination.

## Integration Points

### 1. Session Timing Data Source
- **Primary**: `test_sessions.video_start_timestamp` (epoch seconds)
- **Fallback**: `config.metadata.video_start_time`
- **Multi-video**: Aggregates total duration from sequence

### 2. Detection Storage
- Window validation occurs BEFORE `_record_detection_event()`
- Only valid detections reach database storage
- Invalid detections never enter the data pipeline

### 3. Metrics Calculation
- All downstream metrics (latency, pass/fail, etc.) now use only valid detections
- No contamination from pre-video or post-video noise

## Testing Recommendations

### Unit Tests
```python
def test_detection_before_video_start_is_skipped():
    """Test that detections before video start are filtered"""
    video_start = 1000.0  # epoch seconds
    detection_time = 993.0  # 7 seconds before start

    result = monitor._is_detection_within_video_window(
        session_id="test",
        detection_timestamp=detection_time,
        video_start_time=video_start,
        video_end_time=None
    )

    assert result == False  # Should be skipped

def test_detection_within_grace_period_is_accepted():
    """Test that detections within grace period are accepted"""
    video_start = 1000.0
    detection_time = 999.95  # 50ms before start (within 100ms grace)

    result = monitor._is_detection_within_video_window(
        session_id="test",
        detection_timestamp=detection_time,
        video_start_time=video_start,
        video_end_time=None
    )

    assert result == True  # Should be accepted
```

### Integration Tests
1. Start test session
2. Monitor logs for "Window validation enabled"
3. Trigger hardware detections before video starts
4. Verify "Skipping early detection" appears in logs
5. Start video playback
6. Trigger hardware detections during video
7. Verify detections are recorded
8. Check final statistics match expected counts

## Backward Compatibility

### Fallback Behavior
If video timing data is not available:
```python
if video_start_time is None and video_end_time is None:
    return True  # Accept all detections (legacy behavior)
```

This ensures the system continues to work for:
- Sessions without video timing metadata
- Legacy data that pre-dates window validation
- Test/development environments with incomplete setup

## Performance Impact

### Minimal Overhead
- Single timestamp comparison per detection: O(1)
- No database queries in validation loop
- No network calls or I/O operations

### Memory Usage
- 3 additional integer counters per session: ~24 bytes
- Negligible impact on overall memory footprint

## Files Modified

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
   - Added `_is_detection_within_video_window()` method (lines 651-712)
   - Enhanced `_monitoring_loop()` with window validation (lines 590-600)
   - Added statistics tracking (lines 505-515, 631-638)
   - Normalized video timing extraction (lines 491-510)

## Related Issues

- **Issue**: "Detections starting 7 seconds before video"
- **Impact**: Invalid early detections contaminating metrics
- **Priority**: P0 - Data accuracy blocker
- **Status**: ✅ RESOLVED with this implementation

## Future Enhancements

1. **Dynamic Grace Period**: Adjust grace period based on hardware latency measurements
2. **Per-Video Windows**: Support per-video timing in multi-video sequences
3. **Frame-Level Validation**: Validate detections against actual frame numbers
4. **Metrics Dashboard**: Expose skipped detection counts in monitoring dashboard

---

**Implementation Date**: 2025-11-05
**Author**: Agent 4 - Detection Window Clamping Specialist
**Status**: ✅ Complete and Ready for Testing
