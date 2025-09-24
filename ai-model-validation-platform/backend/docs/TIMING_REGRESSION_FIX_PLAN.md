# HIL Timing Regression Fix Plan

## Summary

**ROOT CAUSE**: The new timing orchestration system introduced a systematic timing offset where the video start timestamp reference point was changed, causing detection-to-video alignment to show false misalignments of -167ms, -125ms, -83ms.

## Specific Code Changes Required

### 1. Fix Video Timing Service Reference Point

**File**: `backend/services/video_timing_service.py`
**Line**: 161
**CURRENT (BROKEN)**:
```python
start_timestamp = sync_point.utc_timestamp.timestamp()
```

**SHOULD BE (FIXED)**:
```python
start_timestamp = sync_point.system_time  # Use system_time attribute instead
# OR revert to simple approach:
start_timestamp = time.time()  # Simple system timestamp
```

### 2. Verify T1 Capture Integration

**File**: `backend/api/hil_test_complete.py`
**Lines**: 356-362

The T1 capture integration may be interfering with existing timing:
```python
# POTENTIAL ISSUE: This may change timing reference
t1_capture = timing_orchestration_service.capture_t1_video_start_timestamp(
    session_id=str(session_id),
    video_id=video_id,
    db=db,
    video_metadata=video_metadata
)
```

**ACTION**: Verify this doesn't override the video_timing_service timestamp

### 3. Preserve Duration Auto-Stop Logic

**File**: `backend/services/dedicated_labjack_monitor.py`
**Lines**: 186-231

**KEEP THESE CHANGES** (they fix the duration issue):
```python
# Enhanced fallback mechanism for missing duration
if not isinstance(duration, (int, float)) or duration <= 0:
    # Fallback logic - KEEP THIS
    if video_id:
        # Database fallback - KEEP THIS
```

## Fix Implementation Strategy

### Phase 1: Minimal Revert (Immediate Fix)

1. **Change video_timing_service.py line 161**:
   ```python
   # BEFORE (broken)
   start_timestamp = sync_point.utc_timestamp.timestamp()
   
   # AFTER (fixed)
   start_timestamp = time.time()  # Simple system timestamp
   ```

2. **Test immediately** with known ground truth video

3. **Verify frame alignment** shows ~0ms instead of -167ms

### Phase 2: Proper Integration (Follow-up)

1. **Investigate sync_point timing** if simple fix doesn't work
2. **Ensure T1 capture doesn't interfere** with ground truth matching
3. **Add integration test** to prevent future regressions

## Verification Test Plan

### 1. Create Test Script
```python
# backend/tests/test_timing_regression_fix.py

def test_frame_alignment_after_fix():
    """Test that fixes the -167ms, -125ms, -83ms regression"""
    
    # Use known test video with ground truth at frames 1, 2, 3
    session_id = "timing_test_session"
    video_id = "test_video_24fps"
    
    # Simulate detections at expected frame times
    expected_times = [0.042, 0.083, 0.125]  # 24fps frame times
    
    for i, expected_time in enumerate(expected_times):
        # Calculate what alignment should be
        alignment = calculate_detection_alignment(session_id, expected_time)
        
        # Should be near 0ms, not -167ms, -125ms, -83ms
        assert abs(alignment) < 10  # Within 10ms tolerance
        print(f"Frame {i+1}: {alignment:.1f}ms (PASS)")
```

### 2. Before/After Comparison

**BEFORE FIX (Broken)**:
```
Frame 1 (0.042s): -167ms misalignment  ❌
Frame 2 (0.083s): -125ms misalignment  ❌  
Frame 3 (0.125s): -83ms misalignment   ❌
```

**AFTER FIX (Working)**:
```
Frame 1 (0.042s): ~0ms misalignment    ✅
Frame 2 (0.083s): ~0ms misalignment    ✅
Frame 3 (0.125s): ~0ms misalignment    ✅
```

### 3. Duration Functionality Test

**MUST STILL WORK**:
```python
def test_duration_auto_stop_still_works():
    """Ensure duration fix is preserved"""
    
    # Test video with 5s duration
    monitor.start_monitoring_with_video_sync(session_id, {
        'video_id': 'test_video',
        'duration': 5.0,  # Should auto-stop after 5s
        'fps': 24
    })
    
    # Wait for auto-stop
    time.sleep(6)
    
    # Should have stopped automatically
    assert not monitor.is_monitoring(session_id)
```

## Implementation Steps

### Step 1: Immediate Fix (5 minutes)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Edit video_timing_service.py
sed -i 's/start_timestamp = sync_point.utc_timestamp.timestamp()/start_timestamp = time.time()  # Fixed timing regression/' services/video_timing_service.py

# Test immediately
python3 tests/test_timing_regression_fix.py
```

### Step 2: Verify Fix (10 minutes)

1. **Run HIL test** with known ground truth video
2. **Check alignment results** show ~0ms instead of -167ms
3. **Verify auto-stop** duration functionality still works

### Step 3: Deploy (5 minutes)

1. **Commit fix** with clear message
2. **Deploy to staging** environment
3. **Run full regression test**

## Risk Assessment

### Low Risk Changes
- Simple `time.time()` reversion is very safe
- Preserves all duration auto-stop functionality
- Only affects video start timestamp reference

### High Confidence Fix
- Pattern analysis shows systematic offset
- Simple timestamp reference fix should resolve
- Duration fix logic is preserved

## Success Criteria

### ✅ Fix Successful When:
1. Frame 1 detections show 0±10ms alignment (not -167ms)
2. Frame 2 detections show 0±10ms alignment (not -125ms)  
3. Frame 3 detections show 0±10ms alignment (not -83ms)
4. Video duration auto-stop still works correctly
5. No other timing functionality is broken

### ❌ Fix Failed If:
1. Alignment issues persist
2. Auto-stop duration breaks
3. New timing errors appear

## Rollback Plan

If fix fails:
1. **Revert change**: `git revert <commit_hash>`
2. **Investigate sync_point system** more deeply
3. **Consider alternative timing reference** approaches

## Timeline

- **Immediate**: 20 minutes (implement + test)
- **Validation**: 30 minutes (full regression test)
- **Deploy**: 10 minutes (commit + deploy)
- **Total**: ~1 hour to resolution