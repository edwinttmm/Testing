# ADR-002: HIL Video Duration Resolution and LabJack Auto-Stop Enhancement

## Status
**ACCEPTED** - Implemented 2024-09-24

## Context

### Problem Statement
The HIL (Hardware-in-the-Loop) testing system was experiencing premature LabJack monitoring termination due to missing video duration information. LabJack monitoring would stop at approximately 3.675 seconds instead of the actual video duration (e.g., 5.0 seconds for a 5-second video), causing incomplete test data collection.

### Root Cause Analysis
1. **Missing Duration Flow**: Video duration was not being properly passed through the HIL workflow chain
2. **Hardcoded Fallback**: System fell back to hardcoded timeout values instead of querying actual video duration  
3. **No Database Fallback**: When `duration_s` was missing from API payload, no fallback mechanism existed
4. **Limited Validation**: Insufficient logging and validation for missing duration scenarios

### Impact
- **Test Data Loss**: LabJack monitoring ended before video completion, missing critical detection events
- **False Results**: Incomplete data led to inaccurate latency measurements and test outcomes
- **Debugging Difficulty**: Limited logging made it hard to diagnose duration resolution issues

## Decision

### Enhanced Video Duration Resolution System

We implement a comprehensive 3-tier duration resolution system:

#### Tier 1: API Payload (Primary)
```python
duration = video_data.get("duration_s") or video_data.get("duration")
```

#### Tier 2: Database Fallback (Secondary)
```python
if not duration:
    video_record = db.query(Video).filter(Video.id == video_id).first()
    if video_record and video_record.duration:
        duration = video_record.duration
```

#### Tier 3: Safe Default (Tertiary)
```python
if not duration:
    duration = 30  # 30 second default instead of hardcoded 3.675s
```

### Key Components Modified

#### 1. Enhanced LabJack Monitor (`dedicated_labjack_monitor.py`)
```python
# Before: Limited duration handling
duration = video_timing_config.get('duration')
if isinstance(duration, (int, float)) and duration > 0:
    # Start auto-stop timer

# After: Comprehensive fallback system
duration = video_timing_config.get('duration')
if not isinstance(duration, (int, float)) or duration <= 0:
    # Try database fallback
    if video_id:
        video = db.query(Video).filter(Video.id == video_id).first()
        if video and video.duration:
            duration = video.duration
    
    # Safe default fallback
    if not isinstance(duration, (int, float)) or duration <= 0:
        duration = 30  # Reasonable default
```

#### 2. Enhanced HIL API (`hil_test_complete.py`)
- Existing `get_video_duration()` function already implemented robust resolution
- Added comprehensive logging for duration resolution debugging
- Enhanced error handling and validation

#### 3. Auto-Stop Grace Period Calculation
```python
grace = max(0.25, min(2.0, duration * 0.05))  # 5% or [0.25s..2s]
total_monitoring_time = duration + grace
```

## Alternatives Considered

### Alternative 1: Frontend-Only Fix
**Rejected**: Would require modifying all frontend components and doesn't address backend resilience.

### Alternative 2: Remove Auto-Stop Entirely
**Rejected**: Auto-stop is critical for resource management and test completion detection.

### Alternative 3: Hardcode Duration by Video Type
**Rejected**: Not scalable and doesn't handle custom video uploads.

## Implementation Details

### Files Modified
1. `/backend/services/dedicated_labjack_monitor.py`
   - Added Video model import
   - Enhanced duration fallback logic
   - Improved error handling and logging

2. `/backend/api/hil_test_complete.py`  
   - Already had robust `get_video_duration()` function
   - Enhanced logging for debugging

### Expected Behavior After Fix
```
5-second video  → LabJack monitors for 5.25s (5.0s + 0.25s grace)
10-second video → LabJack monitors for 10.5s (10.0s + 0.5s grace)  
30-second video → LabJack monitors for 31.5s (30.0s + 1.5s grace)
60-second video → LabJack monitors for 62.0s (60.0s + 2.0s grace - capped)
```

### Logging Enhancements
```
✅ Retrieved video duration from database: 5.0s for video abc-123
⚠️  Missing video duration in timing config - using database fallback  
⚠️  Using default monitoring duration: 30s for session xyz-789
🕒 Monitoring will auto-stop after 5.25s (duration: 5.0s + grace: 0.25s)
```

## Testing Strategy

### Comprehensive Test Suite (`test_hil_video_duration_fix.py`)
1. **Duration Resolution Tests**
   - API payload resolution (primary path)
   - Database fallback resolution (secondary path)  
   - Default fallback handling (tertiary path)

2. **Auto-Stop Timing Tests**
   - Various video durations (5s, 10s, 30s, 60s)
   - Grace period calculations
   - Edge cases and invalid durations

3. **Integration Tests**
   - End-to-end HIL workflow with proper duration
   - Error scenarios and fallback behavior

### Manual Testing Scenarios
1. Upload 5-second video, verify LabJack runs for 5.25 seconds
2. Test with missing duration_s in API payload  
3. Test with video missing from database
4. Verify logging shows correct duration resolution path

## Monitoring and Observability

### Key Metrics to Monitor
- **Duration Resolution Success Rate**: % of videos with successful duration resolution
- **Auto-Stop Timing Accuracy**: Difference between expected and actual monitoring duration
- **Database Fallback Usage**: Frequency of database fallback activation
- **Default Fallback Triggers**: Cases where no duration was available

### Logging Strategy
- **INFO**: Successful duration resolution with source
- **WARN**: Missing duration requiring fallback  
- **ERROR**: Complete duration resolution failure

## Rollback Plan

### Immediate Rollback
```bash
# Revert the enhanced duration logic
git revert <commit-hash>

# Restart services
systemctl restart labjack-monitoring
```

### Gradual Rollback
1. Add feature flag for enhanced duration resolution
2. Gradually roll back problematic components
3. Monitor for regression in test completion rates

## Future Considerations

### Phase 2 Enhancements
1. **Predictive Duration**: Use ML to estimate duration from file metadata
2. **Dynamic Grace Period**: Adjust grace period based on video content type
3. **Real-time Duration Detection**: Detect actual video end during playback

### Long-term Architecture  
1. **Event-Driven Architecture**: Move to event-based duration resolution
2. **Caching Layer**: Cache resolved durations for performance
3. **Health Checks**: Automated validation of duration resolution accuracy

## Success Criteria

✅ **Primary Success Criteria (All Met)**
- LabJack monitoring runs for full video duration + grace period
- No premature monitoring termination at 3.675s  
- Robust fallback mechanism handles missing durations
- Comprehensive logging enables easy debugging

✅ **Secondary Success Criteria**  
- All existing HIL tests continue to pass
- No performance degradation in video start timing
- Enhanced test coverage for duration resolution
- Clear documentation for troubleshooting

## Lessons Learned

### Technical Insights
1. **Robust Fallback Systems**: Multiple fallback layers prevent single points of failure
2. **Database as Fallback**: Video model duration field provides reliable fallback source
3. **Logging is Critical**: Comprehensive logging essential for debugging timing issues

### Process Improvements  
1. **End-to-End Testing**: Need comprehensive testing of entire HIL workflow
2. **Edge Case Handling**: Must consider all possible duration sources and failures
3. **Documentation**: Clear ADRs help future maintainers understand design decisions

---

**Author**: Claude Code (System Architecture Designer)
**Date**: 2024-09-24
**Review Status**: Self-reviewed and implemented
**Related Issues**: HIL LabJack monitoring stopping too early due to missing video duration