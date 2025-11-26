# Timing Synchronization Fixes - Negative Latency Bug Resolution

**Date**: 2025-11-25
**Status**: ✅ FIXED

## Problem Summary

Negative latencies (-5.9ms, -18.7ms) were occurring because:
1. Timing calculator fell back to `labjack_start_time` when `video_start_time` was missing
2. LabJack starts 352ms BEFORE video playback (buffering time)
3. Clamping happened BEFORE drift compensation, masking timing errors

## Root Causes

### Cause 1: Incorrect Fallback Logic
**Location**: `timing_synchronization_calculator.py` lines 264-286

**Problem**:
```python
# BROKEN - Causes negative latencies
if video_start_time is None:
    video_start_time = labjack_start_time  # WRONG - different start times!
```

**Why it breaks**:
- LabJack monitoring starts at `t=0`
- Video playback starts at `t=352ms` (after buffering)
- Using labjack_start_time makes detections appear 352ms earlier than they actually are
- Results: Detection at 1.0s looks like it happened at 0.648s → negative latency

**Fix Applied**:
```python
# FIXED - Requires video_start_time
if video_start_time is None:
    logger.error(f"❌ video_start_time is required for accurate latency calculation")
    raise ValueError(
        "video_start_time is required. Cannot fallback to labjack_start_time "
        "as it causes negative latency bug (352ms offset)."
    )
```

### Cause 2: Wrong Order of Operations
**Location**: `video_timing_service.py` lines 456-517

**Problem**:
```python
# BROKEN - Clamps before compensating
video_relative = unix_timestamp - video_start_time  # Raw timestamp
video_relative = clamp(video_relative, 0, duration)  # Clamp first
# Drift compensation never applied!
```

**Why it breaks**:
- Raw timestamps include drift errors (e.g., 87ms accumulated drift)
- Clamping locks in the drift error
- Drift compensation is never applied
- Results: Systematic timing offset in all measurements

**Fix Applied**:
```python
# FIXED - Compensates THEN clamps
compensated = unix_timestamp - (drift_ms / 1000.0)  # Compensate first
video_relative = compensated - video_start_time     # Calculate offset
video_relative = clamp(video_relative, 0, duration) # Then clamp
```

### Cause 3: Drift Formula Verification
**Location**: `timestamp_compensation_service.py` lines 61-96

**Status**: ✅ Already correct - No changes needed

**Current implementation**:
```python
def compensate_detection_timestamp(
    self,
    detection_id: str,
    raw_timestamp: float,
    drift_ms: float,
    clock_offset_ms: float = 0.0,
    metadata: Optional[Dict] = None
) -> float:
    """
    Compensate a single detection timestamp.

    Formula: T_compensated = T_raw - (drift_ms + clock_offset_ms) / 1000
    """
    # Total correction in seconds
    total_correction_s = (drift_ms + clock_offset_ms) / 1000.0

    # Apply correction
    compensated = raw_timestamp - total_correction_s

    return compensated
```

## Changes Made

### File 1: timing_synchronization_calculator.py

**Lines**: 263-284
**Change**: Replaced fallback logic with strict requirement

**Before**:
```python
if video_start_time is None:
    video_start_system_time = labjack_start_time
    logger.warning("⚠️ Using labjack_start_time as fallback...")
```

**After**:
```python
if video_start_time is None:
    logger.error("❌ CRITICAL: video_start_time is required")
    raise ValueError(
        "video_start_time is required for accurate latency calculation. "
        "Cannot fallback to labjack_start_time as it causes negative latency bug."
    )
```

**Impact**:
- Prevents silent failures with incorrect timing
- Forces callers to provide correct video_start_time
- Eliminates 352ms systematic offset

### File 2: video_timing_service.py

**Lines**: 456-517
**Change**: Apply drift compensation before clamping

**Before**:
```python
def convert_unix_to_video_relative(self, session_id: str, unix_timestamp: float) -> Optional[float]:
    video_relative_time = unix_timestamp - timing_data.start_timestamp
    # Clamp to [0, duration]
    if timing_data.duration_s is not None:
        video_relative_time = clamp(video_relative_time, 0, timing_data.duration_s)
    return video_relative_time
```

**After**:
```python
def convert_unix_to_video_relative(self, session_id: str, unix_timestamp: float,
                                  drift_ms: float = 0.0) -> Optional[float]:
    # CRITICAL FIX: Apply drift compensation FIRST
    compensated_timestamp = unix_timestamp - (drift_ms / 1000.0)
    video_relative_time = compensated_timestamp - timing_data.start_timestamp

    # THEN clamp to [0, duration]
    if timing_data.duration_s is not None:
        video_relative_time = clamp(video_relative_time, 0, timing_data.duration_s)
    return video_relative_time
```

**Impact**:
- Eliminates drift-induced timing errors
- Corrects systematic offset in all measurements
- Maintains valid range constraints after correction

### File 3: timestamp_compensation_service.py

**Lines**: 61-96
**Change**: None - Already correct

**Current formula**:
```python
compensated = raw_timestamp - (drift_ms / 1000.0)
```

**Status**: ✅ Verified correct

## Testing Requirements

### Unit Tests Required

1. **Test negative latency prevention**:
   ```python
   def test_requires_video_start_time():
       with pytest.raises(ValueError, match="video_start_time is required"):
           calculator.calculate_corrected_latency(
               video_start_time=None  # Should fail
           )
   ```

2. **Test drift compensation order**:
   ```python
   def test_drift_compensated_before_clamping():
       # Given: timestamp at 10.5s with 500ms drift
       result = service.convert_unix_to_video_relative(
           unix_timestamp=video_start + 10.5,
           drift_ms=500.0
       )
       # Should compensate THEN clamp
       assert result == 10.0  # Not 10.5 (would be if clamped first)
   ```

3. **Test compensation formula**:
   ```python
   def test_compensation_formula():
       raw = 1000.0
       drift_ms = 87.3
       result = service.compensate_detection_timestamp(
           raw_timestamp=raw,
           drift_ms=drift_ms
       )
       assert result == pytest.approx(raw - 0.0873)  # 999.9127
   ```

### Integration Tests Required

1. **Test with real timing data**:
   - Create session with video_start_time
   - Generate detection with known drift
   - Verify latency is positive and correct

2. **Test sequence handling**:
   - Test with multi-video sequences
   - Verify each video uses its own start_time
   - Confirm no cross-video contamination

## Expected Results

### Before Fixes
- ❌ Negative latencies: -5.9ms, -18.7ms
- ❌ Systematic 352ms offset from labjack fallback
- ❌ Uncorrected drift errors (87ms)

### After Fixes
- ✅ All latencies positive: 50-350ms range
- ✅ No systematic offsets
- ✅ Drift-compensated accurate timing

## Verification Checklist

- [x] timing_synchronization_calculator.py - Fixed fallback logic
- [x] video_timing_service.py - Fixed operation order
- [x] timestamp_compensation_service.py - Verified correct (no changes)
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Documentation updated
- [ ] Code review completed

## Related Issues

- Negative latency bug: -5.9ms, -18.7ms detections
- 352ms labjack_start_time offset
- 87ms accumulated drift not compensated
- Clamping masking timing errors

## References

- `DRIFT_COMPENSATION_ACCURACY_ANALYSIS.md` - Drift compensation implementation
- `NEGATIVE_LATENCY_BUG_ANALYSIS.md` - Root cause analysis
- `FIXES_SUMMARY_FINAL.md` - Overall fixes summary
