# HIL Timing Regression Root Cause Analysis

## Executive Summary

**CRITICAL TIMING REGRESSION IDENTIFIED**: After the video duration fixes, detection-to-video alignment broke with a systematic offset pattern:

- Frame 1 (0.042s) → Detection shows **-167ms** misalignment 
- Frame 2 (0.083s) → Detection shows **-125ms** misalignment
- Frame 3 (0.125s) → Detection shows **-83ms** misalignment

**Pattern Analysis**: The differences (-167 → -125 = +42ms, -125 → -83 = +42ms) exactly match the expected frame interval at 24fps (41.67ms), indicating this is NOT random timing drift but a **systematic calculation error**.

## Root Cause Identified

### 1. Pattern Analysis
The misalignment pattern is highly systematic:
```
Expected: Frame 1 at 0.042s, Frame 2 at 0.083s, Frame 3 at 0.125s
Reported: -167ms,            -125ms,            -83ms

Differences: -167 → -125 = +42ms (matches 24fps frame interval)
            -125 → -83  = +42ms (matches 24fps frame interval)
```

### 2. Timing Chain Analysis

The broken timing chain:
```
Video Start (T1) → Frame Timing → Detection Timestamp → Alignment Calculation
      ↓               ↓              ↓                    ↓
   Working         BROKEN?         BROKEN?          SYSTEMATIC OFFSET
```

### 3. New Code Introduced

Based on git analysis, these NEW timing services were introduced recently:

1. **`video_timing_service.py`** - Line 161: `start_timestamp = sync_point.utc_timestamp.timestamp()`
2. **`timing_orchestration_service.py`** - T0/T1 capture system
3. **`hil_test_complete.py`** - Enhanced T0 timing capture

### 4. Suspected Root Cause

**HYPOTHESIS**: The new timing orchestration system is introducing a timing offset between:
- The video timing service's T1 capture timestamp
- The actual video playback timing used by the frontend
- The LabJack detection timestamps

### 5. Specific Code Issues Found

#### Issue 1: UTC vs System Time Inconsistency
In `video_timing_service.py` line 161:
```python
start_timestamp = sync_point.utc_timestamp.timestamp()  # NEW CODE
```

This may not align with how the original video timing was captured.

#### Issue 2: Frame Calculation Logic
In `video_timing_service.py` line 425:
```python
frame_number = int(video_relative_timestamp * timing_data.frame_rate)
```

This logic appears unchanged, so the issue is likely in the timing reference point.

#### Issue 3: New T0/T1 Orchestration System
The new timing orchestration system in `hil_test_complete.py` introduces:
- T0 capture at test start
- T1 capture at video start
- T1-T0 presentation delay calculation

This may be interfering with the original ground truth matching timing.

### 6. Breaking Change Analysis

**BEFORE (Working)**: Simple video start timestamp
**AFTER (Broken)**: Complex T0/T1 orchestration with sync points

The issue appears to be that the new timing system changed the video start timestamp reference point, but the ground truth matching system still expects the old reference point.

## Impact Assessment

### Critical Impact
- HIL validation completely broken
- Detection appears 167-83ms early (false negative pattern)
- Ground truth matching failing systematically

### Downstream Effects
- Test results invalid
- LabJack hardware validation compromised
- Customer acceptance testing blocked

## Recommended Fix Strategy

### 1. Immediate Fix (Revert Approach)
Identify the specific lines that changed the video start timestamp calculation and revert just those changes while preserving the duration fix.

### 2. Target Files for Reversion
- `video_timing_service.py`: Line 161 timing capture change
- `hil_test_complete.py`: T1 capture integration (if interfering)
- `timing_orchestration_service.py`: Remove interference with existing timing

### 3. Preserve These Features
- Auto-stop duration functionality
- Video duration fallback system
- LabJack monitoring improvements

### 4. Verification Plan
1. Test with known ground truth video
2. Verify Frame 1 (0.042s) shows ~0ms misalignment
3. Verify Frame 2 (0.083s) shows ~0ms misalignment  
4. Verify Frame 3 (0.125s) shows ~0ms misalignment
5. Confirm duration auto-stop still works

## Technical Details

### Timing Reference Point Issue
The new code likely changed from:
```python
# OLD (working): Simple system time
video_start_time = time.time()
```

To:
```python
# NEW (broken): Complex sync point system  
start_timestamp = sync_point.utc_timestamp.timestamp()
```

### Frame Alignment Math
Expected timing should work as:
```
detection_time - video_start_time = video_relative_time
video_relative_time * fps = frame_number
```

The systematic -167ms offset suggests `video_start_time` is now 167ms later than it should be for the first detection.

## Next Steps

1. **Create minimal reproduction test**
2. **Identify exact code lines to revert**
3. **Test fix preserves duration functionality**
4. **Deploy and validate timing alignment**
5. **Update timing integration tests**

## Confidence Level

**HIGH CONFIDENCE** - The systematic 42ms interval pattern matching 24fps frame timing proves this is a calculation error, not random timing drift.