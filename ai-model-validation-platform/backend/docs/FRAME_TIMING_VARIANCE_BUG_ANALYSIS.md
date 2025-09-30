# Frame Timing Variance Bug Analysis

## Bug Summary

**Location**: `/backend/src/api/enhanced_hil_results_endpoints.py` line 544
**Issue**: Frame Variance calculation is mathematically inconsistent and uses wrong metric

## Current Incorrect Implementation

```python
"frame_timing_variance_ms": round(abs(to_float(getattr(corrected_result, 'latency_correction_ms', None)) or 0.0), 1),
```

## Problem Analysis

### What `latency_correction_ms` Actually Represents
From `timing_synchronization_calculator.py` lines 207-208:
```python
latency_correction_ms = apparent_latency_ms - real_latency_ms
```

**Meaning**: `latency_correction_ms` is the difference between:
- `apparent_latency_ms` = `(detection_system_time - labjack_start_time) * 1000.0`
- `real_latency_ms` = `(detection_system_time - gt_system_time) * 1000.0`

This represents **timing synchronization correction**, NOT frame timing variance.

### What Frame Timing Variance Should Be

**Frame Timing Variance** should measure how well a detection aligns with expected frame boundaries:

```python
expected_frame_time = frame_number / fps
actual_detection_time = detection_video_relative_timestamp  
frame_variance = abs(actual_detection_time - expected_frame_time) * 1000.0  # Convert to ms
```

## Mathematical Inconsistency

### Example Case Analysis:
- **Detection at Frame 3** (24fps video)
- **Expected frame time**: 3/24 = 0.125 seconds
- **Actual detection time**: 0.125 seconds (perfectly aligned)
- **Current calculation**: Shows 11.3ms "Frame Variance" 
- **Correct calculation**: Should show ~0ms variance

### Why Current Result is Wrong:
The 11.3ms comes from `latency_correction_ms`, which measures:
```
11.3ms = |apparent_latency - real_latency|
```

This has **no relationship** to frame alignment. A detection can be perfectly frame-aligned (0ms variance) but still have timing synchronization corrections due to video startup delays.

## Available Data for Correct Implementation

From the enhanced HIL results endpoint, we have access to:

1. **Video FPS**: `session_result.fps` from videos table
2. **Detection Frame**: `event.video_frame_number` from detection_events table  
3. **Detection Video Time**: `event.video_relative_timestamp` from detection_events table
4. **Ground Truth Frame**: `gt.frame_number` from ground_truth_objects table
5. **Ground Truth Video Time**: `gt.timestamp` from ground_truth_objects table

## Correct Implementation

### For Detection Events with Ground Truth:
```python
def calculate_frame_timing_variance_ms(detection_event, ground_truth_event, video_fps):
    """Calculate actual frame timing variance"""
    try:
        # Get ground truth frame and FPS
        gt_frame = float(ground_truth_event.get('frame_number', 0))
        fps = float(video_fps) if video_fps else 24.0
        
        # Calculate expected time for this frame
        expected_frame_time = gt_frame / fps
        
        # Get actual detection time (video-relative)
        actual_detection_time = float(detection_event.get('video_relative_timestamp', 0))
        
        # Calculate frame timing variance
        variance_seconds = abs(actual_detection_time - expected_frame_time)
        variance_ms = variance_seconds * 1000.0
        
        return round(variance_ms, 1)
        
    except Exception as e:
        logger.warning(f"Failed to calculate frame timing variance: {e}")
        return 0.0
```

### For Detection Events without Ground Truth:
```python
def calculate_detection_frame_variance_ms(detection_event, video_fps):
    """Calculate frame variance using detection's own frame data"""
    try:
        # Get detection frame number and video timestamp
        detection_frame = float(detection_event.get('video_frame_number', 0))
        detection_time = float(detection_event.get('video_relative_timestamp', 0))
        fps = float(video_fps) if video_fps else 24.0
        
        # Calculate expected time for detection frame
        expected_time = detection_frame / fps
        
        # Calculate variance
        variance_ms = abs(detection_time - expected_time) * 1000.0
        
        return round(variance_ms, 1)
        
    except Exception as e:
        return 0.0
```

## Expected Results After Fix

### For Aligned Detections:
- **Frame Variance**: ~0-2ms (truly aligned with frame boundaries)
- **Latency Correction**: Can still be 11.3ms (separate timing sync issue)

### For Misaligned Detections:
- **Frame Variance**: 5-20ms (detection between frame boundaries)
- **Latency Correction**: Variable based on video startup timing

## Implementation Priority

1. **High Priority**: Fix frame variance calculation to use correct formula
2. **Medium Priority**: Investigate why latency_correction_ms is 11.3ms for aligned detection
3. **Low Priority**: Add validation to ensure frame variance and latency correction are measuring different aspects

## Files to Modify

1. `/backend/src/api/enhanced_hil_results_endpoints.py` - Fix frame variance calculation
2. Add helper functions for frame timing calculations
3. Update tests to validate correct frame variance values

## Validation Criteria

After fix, frame variance should:
- Show ~0ms for detections perfectly aligned with frame boundaries
- Show 5-20ms for detections between frames
- Be independent of timing synchronization corrections
- Use ground truth frame timing when available
- Fall back to detection frame data when ground truth unavailable