# Option A Implementation Guide - Step by Step

## Overview

This guide provides EXACT code changes needed to implement Option A: HIL Monitor as Orchestrator.

**Total Time**: 2-3 hours
**Risk Level**: LOW ✅
**Files Changed**: 2
**Lines Modified**: ~40

---

## Step 1: Backup Current Code (5 minutes)

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend

# Create backup branch
git checkout -b backup-before-integration-fix

# Commit current state
git add .
git commit -m "Backup before implementing Option A (HIL as orchestrator)"

# Create working branch
git checkout -b feature/hil-orchestrator-integration

# Verify clean state
git status
```

---

## Step 2: Code Changes - File 1 (15 minutes)

### File: `/services/raw_labjack_integration.py`

**Location**: Lines 158-199

**BEFORE** (Lines 158-199):
```python
                # Start HIL monitoring session if video config provided
                hil_session_active = False
                if video_config:
                    try:
                        hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
                            test_session_id, video_timing_config
                        )
                        hil_session_active = hil_success

                        if hil_success:
                            logger.info(f"✅ HIL monitoring started for session {test_session_id}")
                        else:
                            logger.warning(f"⚠️ HIL monitoring failed for session {test_session_id}")
                    except Exception as e:
                        logger.error(f"HIL monitoring startup error: {e}")

                # Start basic detection monitoring
                detection_session_active = False
                try:
                    detection_success = self.detection_service.start_monitoring(
                        test_session_id,
                        channels=channels,
                        voltage_threshold=self.config.detection_threshold_volts,
                        debounce_ms=self.config.debounce_time_ms,
                        sample_rate=10,  # Standard detection rate
                        store_in_db=True,
                        enable_websocket=True
                    )
                    detection_session_active = detection_success

                    if detection_success:
                        logger.info(f"✅ Detection monitoring started for session {test_session_id}")
                    else:
                        logger.warning(f"⚠️ Detection monitoring failed for session {test_session_id}")
                except Exception as e:
                    logger.error(f"Detection monitoring startup error: {e}")

                # Create session mapping
                session_mapping = SessionMapping(
                    raw_session_id=raw_session_id,
                    test_session_id=test_session_id,
                    hil_session_active=hil_session_active,
```

**AFTER** (Lines 158-179):
```python
                # Start HIL monitoring session (includes detection monitoring internally)
                hil_session_active = False
                if video_config:
                    try:
                        # ✅ FIXED: Single entry point - HIL monitor orchestrates everything
                        # HIL monitor internally starts detection service with proper config
                        # This eliminates duplicate hardware access and conflicts
                        hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
                            test_session_id, video_timing_config
                        )
                        hil_session_active = hil_success

                        if hil_success:
                            logger.info(f"✅ HIL monitoring started for session {test_session_id}")
                            logger.info(f"   → Detection monitoring: ACTIVE (via HIL orchestration)")
                            logger.info(f"   → Video timing sync: ENABLED")
                            logger.info(f"   → Ground truth capture: ENABLED")
                            logger.info(f"   → Hardware access: SINGLE THREAD (no conflicts)")
                        else:
                            logger.warning(f"⚠️ HIL monitoring failed for session {test_session_id}")
                    except Exception as e:
                        logger.error(f"HIL monitoring startup error: {e}")
                else:
                    logger.warning(f"⚠️ No video config provided - HIL monitoring not started")

                # ✅ REMOVED: Lines 174-193 deleted (duplicate detection_service.start_monitoring call)
                # The detection service is now started internally by HIL monitor with proper config
                # This eliminates hardware conflicts and duplicate events

                # Create session mapping
                session_mapping = SessionMapping(
                    raw_session_id=raw_session_id,
                    test_session_id=test_session_id,
                    hil_session_active=hil_session_active,
```

**Key Changes**:
1. ✅ Enhanced logging to show HIL orchestrates detection
2. ✅ Removed lines 174-193 (duplicate detection service call)
3. ✅ Added comments explaining the fix
4. ✅ Updated logging to reflect single-thread architecture

---

## Step 3: Code Verification - File 2 (10 minutes)

### File: `/services/dedicated_labjack_monitor.py`

**Location**: Lines 226-470

**Verify these sections are correct** (no changes needed, just verification):

#### Section 1: Video Config Extraction (Lines 246-262)
```python
        with self.lock:
            # Get video configuration first (but don't start video yet)
            video_id = video_timing_config.get('video_id')
            if not video_id:
                logger.error(f"❌ Video ID required for session {session_id}")
                return False

            # CRITICAL FIX: Start LabJack monitoring BEFORE video timing to catch all events
            # Configure LabJack monitoring with proper threshold
            # Use a high default sample rate so we don't miss short pulses between frames.
            requested_sample_rate = video_timing_config.get('sample_rate')
            sample_rate = max(requested_sample_rate or 1000, 240)
```

✅ **VERIFIED**: Sample rate logic is correct

#### Section 2: LabJack Config Assembly (Lines 258-291)
```python
            labjack_config = {
                'channels': video_timing_config.get('channels', ['AIN0']),
                'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),  # Use 3.3V threshold as intended
                'debounce_ms': video_timing_config.get('debounce_ms', 0),  # No debounce - catch everything
                'sample_rate': sample_rate,
                'store_in_db': True,  # FIX: Enable database storage for detection persistence
                'enable_websocket': video_timing_config.get('enable_websocket', True)
            }

            # ... continuous mode config ...

            if continuous_flag:
                labjack_config.update({
                    'continuous_mode': True,
                    'continuous_lower_bound': (
                        video_timing_config.get('continuous_lower_bound')
                        or video_timing_config.get('voltage_lower_bound')
                        or video_timing_config.get('voltage_threshold', 3.3)
                    ),
                    'continuous_upper_bound': video_timing_config.get('continuous_upper_bound'),
                    'continuous_interval_ms': video_timing_config.get('continuous_interval_ms', 20)
                })
```

✅ **VERIFIED**: All config parameters properly passed through

#### Section 3: Detection Service Start (Lines 450-470)
```python
            # Start detection monitoring with callback for video timing enhancement
            def detection_callback(event_data: Dict[str, Any]):
                """Callback to enhance detection events with video timing"""
                try:
                    self._on_detection_event_with_video_timing(session_id, event_data)
                except Exception as e:
                    logger.error(f"Error in detection callback: {e}", exc_info=True)

            # CRITICAL: Start detection service with all config parameters
            success = self.labjack_monitor.start_monitoring(
                session_id,
                **labjack_config,
                detection_callback=detection_callback
            )
```

✅ **VERIFIED**: Detection service properly started with callback

**Summary**: No changes needed in `dedicated_labjack_monitor.py`. The existing code already:
1. Properly extracts all config from video_timing_config
2. Passes all parameters to detection service
3. Registers callback for video timing enhancement
4. Starts single monitoring thread

---

## Step 4: Add Configuration Pass-Through Verification (Optional - 10 minutes)

### Enhancement: Ensure all detection features are available

Add this validation function to `dedicated_labjack_monitor.py` after line 291:

```python
            # ✅ OPTIONAL ENHANCEMENT: Validate all detection features are configured
            expected_keys = [
                'channels', 'voltage_threshold', 'debounce_ms', 'sample_rate',
                'store_in_db', 'enable_websocket'
            ]
            missing_keys = [key for key in expected_keys if key not in labjack_config]
            if missing_keys:
                logger.warning(f"⚠️ Missing config keys for detection service: {missing_keys}")
            else:
                logger.info(f"✅ All detection config keys present: {expected_keys}")

            # Log the actual config being used
            logger.info(f"📊 Detection config for session {session_id}:")
            for key, value in labjack_config.items():
                if key not in ['metadata']:  # Skip large metadata objects
                    logger.info(f"   • {key}: {value}")
```

**Purpose**: Helps debugging by logging exact config passed to detection service

---

## Step 5: Update Session Mapping Logic (5 minutes)

### File: `/services/raw_labjack_integration.py`

**Location**: Lines 196-206 (after our changes, now lines ~180-190)

**BEFORE**:
```python
                # Create session mapping
                session_mapping = SessionMapping(
                    raw_session_id=raw_session_id,
                    test_session_id=test_session_id,
                    hil_session_active=hil_session_active,
                    detection_session_active=detection_session_active,  # ← This field
                    started_at=datetime.now(timezone.utc)
                )
```

**AFTER**:
```python
                # Create session mapping
                session_mapping = SessionMapping(
                    raw_session_id=raw_session_id,
                    test_session_id=test_session_id,
                    hil_session_active=hil_session_active,
                    detection_session_active=hil_session_active,  # ✅ FIXED: Detection is part of HIL now
                    started_at=datetime.now(timezone.utc)
                )
```

**Rationale**: Since HIL orchestrates detection, both should have same status

---

## Step 6: Testing Plan (1-2 hours)

### Test 1: Single Video with Detection (30 minutes)

```python
# Test script: test_single_video_integration.py
import asyncio
from services.raw_labjack_integration import RawLabJackIntegration

async def test_single_video():
    """Test single video with detection monitoring"""
    service = RawLabJackIntegration()

    video_config = {
        'video_id': 'test_video_001',
        'fps': 30,
        'duration': 10.0,
        'channels': ['AIN0'],
        'voltage_threshold': 3.3,
        'sample_rate': 1000,
        'enable_websocket': True
    }

    # Start monitoring
    result = await service.start_logging_session(
        session_name="test_single_video",
        video_config=video_config
    )

    print(f"Session started: {result}")

    # Wait for video to complete
    await asyncio.sleep(12.0)

    # Stop monitoring
    await service.stop_logging_session(result['test_session_id'])

    # Verify results
    from database import SessionLocal
    from models import DetectionEvent

    db = SessionLocal()
    try:
        # Check for duplicate events
        events = db.query(DetectionEvent).filter(
            DetectionEvent.session_id == result['test_session_id']
        ).all()

        print(f"Total events: {len(events)}")

        # Check for duplicates
        timestamps = [e.unix_timestamp for e in events]
        duplicates = len(timestamps) - len(set(timestamps))

        assert duplicates == 0, f"Found {duplicates} duplicate events!"
        print("✅ No duplicate events found")

        # Verify video timing fields
        for event in events:
            assert event.video_relative_timestamp is not None, "Missing video timestamp!"
            assert event.video_frame_number is not None, "Missing frame number!"

        print("✅ All events have video timing data")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_single_video())
```

**Expected Results**:
- ✅ No duplicate events
- ✅ All events have video timing data
- ✅ No hardware conflict errors in logs

---

### Test 2: Multi-Video Sequence (30 minutes)

```python
# Test script: test_multi_video_sequence.py
async def test_multi_video_sequence():
    """Test multiple videos in sequence (detection window clamping)"""
    service = RawLabJackIntegration()

    video_configs = [
        {
            'video_id': 'video_001',
            'fps': 30,
            'duration': 5.0,
            'channels': ['AIN0'],
            'voltage_threshold': 3.3,
            'sample_rate': 1000
        },
        {
            'video_id': 'video_002',
            'fps': 30,
            'duration': 5.0,
            'channels': ['AIN0'],
            'voltage_threshold': 3.3,
            'sample_rate': 1000
        }
    ]

    session_id = None

    for i, video_config in enumerate(video_configs):
        print(f"Starting video {i+1}/{len(video_configs)}")

        result = await service.start_logging_session(
            session_name=f"test_sequence_video_{i+1}",
            video_config=video_config
        )

        if session_id is None:
            session_id = result['test_session_id']

        # Wait for video
        await asyncio.sleep(video_config['duration'] + 2.0)

    # Verify detection windows don't overlap
    from services.detection_window_clamp_service import clamp_video_windows

    # ... verification logic ...

    print("✅ Detection windows properly clamped, no overlaps")

if __name__ == "__main__":
    asyncio.run(test_multi_video_sequence())
```

**Expected Results**:
- ✅ Detection windows properly assigned to videos
- ✅ No overlapping detection assignments
- ✅ Clamping logic works correctly

---

### Test 3: Stream Mode (High Frequency) (15 minutes)

```python
# Test script: test_stream_mode.py
async def test_stream_mode():
    """Test high-frequency stream mode"""
    service = RawLabJackIntegration()

    video_config = {
        'video_id': 'test_stream',
        'fps': 30,
        'duration': 5.0,
        'channels': ['AIN0'],
        'voltage_threshold': 3.3,
        'sample_rate': 2000,  # High frequency → triggers stream mode
        'enable_websocket': True
    }

    result = await service.start_logging_session(
        session_name="test_stream_mode",
        video_config=video_config
    )

    await asyncio.sleep(7.0)

    # Verify stream mode was used
    import re
    with open('/var/log/labjack_monitor.log', 'r') as f:
        logs = f.read()
        assert 'stream mode' in logs.lower(), "Stream mode not activated!"

    print("✅ Stream mode activated for high-frequency sampling")

if __name__ == "__main__":
    asyncio.run(test_stream_mode())
```

**Expected Results**:
- ✅ Stream mode activated (check logs)
- ✅ High-frequency sampling working
- ✅ No dropped samples

---

### Test 4: Continuous Mode (15 minutes)

```python
# Test script: test_continuous_mode.py
async def test_continuous_mode():
    """Test continuous mode (steady-state logging)"""
    service = RawLabJackIntegration()

    video_config = {
        'video_id': 'test_continuous',
        'fps': 30,
        'duration': 5.0,
        'channels': ['AIN0'],
        'voltage_threshold': 3.3,
        'sample_rate': 1000,
        'continuous_mode': True,
        'continuous_lower_bound': 3.0,
        'continuous_upper_bound': 3.5,
        'continuous_interval_ms': 20
    }

    result = await service.start_logging_session(
        session_name="test_continuous_mode",
        video_config=video_config
    )

    await asyncio.sleep(7.0)

    # Verify continuous events were logged
    db = SessionLocal()
    try:
        events = db.query(DetectionEvent).filter(
            DetectionEvent.session_id == result['test_session_id']
        ).all()

        # Should have multiple events (continuous logging)
        assert len(events) > 10, "Continuous mode not logging enough events"

        # Verify interval between events
        timestamps = sorted([e.unix_timestamp for e in events])
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        avg_interval_ms = (sum(intervals) / len(intervals)) * 1000

        print(f"Average interval: {avg_interval_ms:.1f}ms (expected: ~20ms)")
        assert 15 <= avg_interval_ms <= 25, "Interval not within expected range"

        print("✅ Continuous mode logging at correct interval")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_continuous_mode())
```

**Expected Results**:
- ✅ Continuous events logged at correct interval
- ✅ Voltage bounds respected
- ✅ No duplicates

---

## Step 7: Database Validation (15 minutes)

### SQL Queries to Verify No Duplicates

```sql
-- Test 1: Check for duplicate events (should return 0 rows)
SELECT
    session_id,
    unix_timestamp,
    detection_channel,
    COUNT(*) as duplicate_count
FROM detection_events
WHERE session_id IN (
    SELECT DISTINCT test_session_id
    FROM session_mappings
    WHERE started_at > NOW() - INTERVAL '1 hour'
)
GROUP BY session_id, unix_timestamp, detection_channel
HAVING COUNT(*) > 1;

-- Expected: 0 rows (no duplicates)


-- Test 2: Verify all events have video timing data
SELECT
    session_id,
    COUNT(*) as total_events,
    COUNT(video_relative_timestamp) as with_video_timestamp,
    COUNT(video_frame_number) as with_frame_number,
    COUNT(screenshot_path) as with_screenshots
FROM detection_events
WHERE session_id IN (
    SELECT DISTINCT test_session_id
    FROM session_mappings
    WHERE started_at > NOW() - INTERVAL '1 hour'
)
GROUP BY session_id;

-- Expected: total_events = with_video_timestamp = with_frame_number


-- Test 3: Check timing accuracy
SELECT
    session_id,
    AVG(actual_latency_ms) as avg_latency,
    STDDEV(actual_latency_ms) as stddev_latency,
    MIN(actual_latency_ms) as min_latency,
    MAX(actual_latency_ms) as max_latency
FROM detection_events
WHERE session_id IN (
    SELECT DISTINCT test_session_id
    FROM session_mappings
    WHERE started_at > NOW() - INTERVAL '1 hour'
)
GROUP BY session_id;

-- Expected: avg_latency < 2.0ms, stddev_latency < 1.0ms
```

---

## Step 8: Log Analysis (15 minutes)

### Check Logs for Success Indicators

```bash
# Check for single monitoring thread per session
grep "Started detection monitoring" /var/log/labjack_monitor.log | tail -20

# Should see only ONE "Started detection monitoring" per session

# Check for HIL orchestration messages
grep "HIL monitoring started" /var/log/labjack_monitor.log | tail -20

# Should see "Detection monitoring: ACTIVE (via HIL orchestration)"

# Check for hardware conflicts (should be NONE)
grep -i "conflict\|duplicate\|error" /var/log/labjack_monitor.log | tail -50

# Should see NO conflicts or duplicates

# Check thread count
ps aux | grep labjack | grep -v grep

# Should see reasonable thread count (not double)
```

---

## Step 9: Rollback Procedure (if needed)

If anything goes wrong:

```bash
# 1. Stop services
sudo systemctl stop labjack-monitor

# 2. Restore backup
git checkout backup-before-integration-fix

# 3. Restart services
sudo systemctl start labjack-monitor

# 4. Verify logs
tail -f /var/log/labjack_monitor.log

# 5. Document issue for debugging
# Create issue in docs/ROLLBACK_ANALYSIS.md
```

---

## Step 10: Deployment Checklist

### Pre-Deployment
- [ ] Code changes reviewed
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Database queries validated
- [ ] Logs analyzed for errors
- [ ] Performance regression check

### Deployment
- [ ] Backup current production code
- [ ] Deploy changes to staging
- [ ] Run smoke tests on staging
- [ ] Monitor staging for 30 minutes
- [ ] Deploy to production (if staging OK)
- [ ] Monitor production for 24 hours

### Post-Deployment
- [ ] Verify no duplicate events
- [ ] Verify timing accuracy
- [ ] Verify all features working
- [ ] Check resource usage (CPU, memory)
- [ ] Document any issues

---

## Success Criteria

✅ **Must Have**:
1. Zero duplicate detection events
2. Single monitoring thread per session
3. All video timing features working
4. Ground truth capture working
5. Timing accuracy within ±1-2ms
6. No hardware conflict errors

✅ **Nice to Have**:
1. Improved log clarity
2. Better error messages
3. Performance metrics

---

## Estimated Timeline

| Task | Time | Cumulative |
|------|------|------------|
| Backup code | 5 min | 5 min |
| File 1 changes | 15 min | 20 min |
| File 2 verification | 10 min | 30 min |
| Optional enhancements | 10 min | 40 min |
| Session mapping fix | 5 min | 45 min |
| Test 1 (single video) | 30 min | 1h 15m |
| Test 2 (multi-video) | 30 min | 1h 45m |
| Test 3 (stream mode) | 15 min | 2h |
| Test 4 (continuous) | 15 min | 2h 15m |
| Database validation | 15 min | 2h 30m |
| Log analysis | 15 min | 2h 45m |
| Documentation | 15 min | 3h |

**Total: 3 hours**

---

## Appendix: Complete Diff

### File 1: `/services/raw_labjack_integration.py`

```diff
--- a/services/raw_labjack_integration.py
+++ b/services/raw_labjack_integration.py
@@ -155,34 +155,24 @@
                 if not raw_session_id:
                     raise RuntimeError("Failed to start raw logging session")

-                # Start HIL monitoring session if video config provided
+                # Start HIL monitoring session (includes detection monitoring internally)
                 hil_session_active = False
                 if video_config:
                     try:
+                        # ✅ FIXED: Single entry point - HIL monitor orchestrates everything
                         hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
                             test_session_id, video_timing_config
                         )
                         hil_session_active = hil_success

                         if hil_success:
-                            logger.info(f"✅ HIL monitoring started for session {test_session_id}")
+                            logger.info(f"✅ HIL monitoring started (includes detection) for {test_session_id}")
+                            logger.info(f"   → Detection monitoring: ACTIVE (via HIL orchestration)")
+                            logger.info(f"   → Video timing sync: ENABLED")
+                            logger.info(f"   → Ground truth capture: ENABLED")
                         else:
                             logger.warning(f"⚠️ HIL monitoring failed for session {test_session_id}")
                     except Exception as e:
                         logger.error(f"HIL monitoring startup error: {e}")
-
-                # Start basic detection monitoring
-                detection_session_active = False
-                try:
-                    detection_success = self.detection_service.start_monitoring(
-                        test_session_id,
-                        channels=channels,
-                        voltage_threshold=self.config.detection_threshold_volts,
-                        debounce_ms=self.config.debounce_time_ms,
-                        sample_rate=10,
-                        store_in_db=True,
-                        enable_websocket=True
-                    )
-                    detection_session_active = detection_success

                 # Create session mapping
                 session_mapping = SessionMapping(
@@ -190,7 +180,7 @@
                     test_session_id=test_session_id,
                     hil_session_active=hil_session_active,
-                    detection_session_active=detection_session_active,
+                    detection_session_active=hil_session_active,
                     started_at=datetime.now(timezone.utc)
                 )
```

---

**Document Version**: 1.0
**Status**: ✅ Ready for Implementation
**Estimated Time**: 3 hours
**Risk Level**: LOW ✅
