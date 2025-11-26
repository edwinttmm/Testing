# Complete HIL Detection Event Flow & Filtering Pipeline Analysis

## Executive Summary

This document traces the complete detection event flow from LabJack hardware trigger through to API response, identifying **ALL filtering and validation points** that can cause detections to be dropped or filtered.

### Critical Finding
**Multiple cascading filters exist at 7 different pipeline stages**, each capable of dropping detections independently. The effective detection rate is the product of all filter pass-rates.

---

## Pipeline Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE DETECTION PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────┘

[STAGE 1] LabJack Hardware
    │
    ├─ Voltage sampling (10,000 Hz default)
    ├─ Hardware threshold (2.5V default)
    └─ Signal conditioning
         │
         ▼
[STAGE 2] LabJack Detection Service (labjack_detection_service.py)
    │
    ├─ FILTER 1: Debounce Filter (20ms)
    ├─ FILTER 2: Continuous Mode Throttling (5ms intervals)
    ├─ FILTER 3: Video Window Validation (2000ms grace period)
    └─ FILTER 4: Duplicate Detection Merging (150ms window)
         │
         ▼
[STAGE 3] Dedicated LabJack Monitor (dedicated_labjack_monitor.py)
    │
    ├─ FILTER 5: Active Session Validation
    ├─ FILTER 6: Timing Ready Timeout (10s wait)
    ├─ FILTER 7: Video-Relative Timing Calculation
    └─ Timing degradation detection
         │
         ▼
[STAGE 4] Database Storage (DetectionEvent table)
    │
    ├─ Transaction commit validation
    └─ Foreign key constraints
         │
         ▼
[STAGE 5] API Retrieval (hil_testing.py)
    │
    ├─ Session validation
    └─ Query filtering (ORDER BY timestamp)
         │
         ▼
[STAGE 6] Client Application
    │
    └─ Response processing
```

---

## STAGE 1: LabJack Hardware Layer

### Configuration
**File**: `/backend/config/labjack_config.py`

| Parameter | Default Value | Environment Variable | Purpose |
|-----------|---------------|---------------------|---------|
| `sample_rate` | 10,000 Hz | `LABJACK_SAMPLE_RATE` | Analog-to-digital sampling frequency |
| `voltage_range` | ±10.0V | `LABJACK_VOLTAGE_RANGE` | Input voltage range |
| `resolution_index` | 0 (default) | `LABJACK_RESOLUTION_INDEX` | ADC resolution (0-8) |
| `stream_scans_per_read` | 100 | `LABJACK_STREAM_SCANS_PER_READ` | Buffer size for streaming |
| `signal_timeout_ms` | 5,000ms | `LABJACK_SIGNAL_TIMEOUT_MS` | Hardware signal timeout |

### Hardware Filtering (None at this layer)
- **No filtering** - raw voltage samples captured at configured rate
- **Signal conditioning** - hardware-level noise reduction
- **Threshold detection** - voltage > 2.5V triggers event

### Data Flow
```python
# Hardware samples voltage continuously
voltage = labjack.read_ain(channel="AIN0")
if voltage > VOLTAGE_THRESHOLD_V:  # 2.5V default
    trigger_timestamp = time.time()
    emit_detection_event(trigger_timestamp, voltage, channel)
```

---

## STAGE 2: LabJack Detection Service

### File: `/backend/services/labjack_detection_service.py`

### Configuration Structure
```python
@dataclass
class DetectionConfig:
    session_id: str
    channels: List[str]
    voltage_threshold: float = 2.5
    debounce_ms: int = 20  # FIX #4: Reduced from 100ms to support 24fps
    sample_rate: int = 1000
    enable_websocket: bool = True
    store_in_db: bool = True
    continuous_mode: bool = False
    continuous_interval_ms: int = 5
    steady_high_interval_ms: int = 5
    use_stream_mode: bool = True
    enable_duplicate_filtering: bool = True
    enable_signal_quality_check: bool = True
    enable_spatial_temporal_clustering: bool = True
    constant_voltage_mode: bool = False  # Bypass debounce when True
```

### FILTER 1: Debounce Logic
**Method**: `_should_record_detection()` (lines 1565-1680)

```python
def _should_record_detection(self, session_id: str, channel: str,
                            current_time: datetime, config: DetectionConfig) -> Optional[str]:
    """
    Determines if detection should be recorded based on debounce timing.

    Returns:
        - "threshold_cross": Normal detection event
        - "steady_high": Periodic logging during sustained high signal
        - "continuous": Continuous mode sample
        - None: FILTERED OUT (detection dropped)
    """

    # BYPASS OPTION: Constant voltage mode disables debounce
    if config.constant_voltage_mode:
        return "threshold_cross"  # Accept every detection

    # Normal debounce filtering
    session_detections = self.last_detection_times.setdefault(session_id, {})
    last_detection = session_detections.get(channel, datetime.min)
    debounce_delta = timedelta(milliseconds=config.debounce_ms)

    if current_time - last_detection < debounce_delta:
        # DETECTION DROPPED: Too soon after previous detection
        self._increment_decision_stat(session_id, 'debounce_skipped')
        logger.debug(f"⛔ [Decision] threshold suppressed by debounce")
        return None  # ← DETECTION LOST HERE

    # Debounce passed - record detection
    session_detections[channel] = current_time
    return "threshold_cross"
```

**Filtering Criteria**:
- Time since last detection < `debounce_ms` (default: **20ms**)
- Prevents rapid-fire duplicates
- **Critical for 24fps video**: Frame period = 41.67ms, debounce = 20ms allows 2 detections per frame

**Configuration Override**:
```python
# Disable debounce for testing
config = DetectionConfig(
    session_id=session_id,
    constant_voltage_mode=True  # Bypasses debounce filter
)
```

### FILTER 2: Continuous Mode Throttling
**Method**: `_should_record_detection()` (lines 1576-1615)

```python
if config.continuous_mode:
    last_emit = self.last_continuous_emit_times.get(session_id, {}).get(channel, datetime.min)
    interval_delta = timedelta(milliseconds=config.continuous_interval_ms)

    if current_time - last_emit < interval_delta:
        # DETECTION DROPPED: Throttled by continuous interval
        self._increment_decision_stat(session_id, 'continuous_throttled')
        return None  # ← DETECTION LOST HERE

    return "continuous"
```

**Filtering Criteria**:
- Active when `continuous_mode = True`
- Enforces minimum interval: `continuous_interval_ms` (default: **5ms**)
- Used for high-frequency sampling scenarios

### FILTER 3: Video Window Validation
**Method**: `_is_detection_within_video_window()` (lines 1869-1920)

```python
def _is_detection_within_video_window(self, session_id: str, detection_timestamp: datetime) -> bool:
    """
    Validate detection falls within video playback window.
    """
    config = self.detection_configs.get(session_id)
    if not config or not config.metadata:
        return True  # No window validation possible

    # Extract video timing from config
    video_start_time = config.metadata.get('video_start_time')
    video_duration = config.metadata.get('video_duration')

    if not video_start_time or not video_duration:
        return True  # Can't validate, assume valid

    # Calculate video end time with grace period
    grace_period = timedelta(milliseconds=GRACE_PERIOD_MS)  # 2000ms default
    video_end_time = video_start_time + video_duration + grace_period

    # Check if detection falls within window
    if detection_timestamp < video_start_time - grace_period:
        # DETECTION DROPPED: Before video start
        logger.warning(f"⚠️ Detection before video start: {detection_timestamp}")
        return False  # ← DETECTION LOST HERE

    if detection_timestamp > video_end_time:
        # DETECTION DROPPED: After video end
        logger.warning(f"⚠️ Detection after video end: {detection_timestamp}")
        return False  # ← DETECTION LOST HERE

    return True
```

**Filtering Criteria**:
- Detection must fall within: `[video_start - grace_period, video_end + grace_period]`
- Grace period: **2000ms** (configurable via `HIL_GRACE_PERIOD_MS`)
- Prevents recording detections outside video playback window

**Configuration**: `/backend/config/timing_config.py`
```python
DEFAULT_GRACE_PERIOD_MS = 2000  # 2 seconds
GRACE_PERIOD_MS = int(os.getenv("HIL_GRACE_PERIOD_MS", DEFAULT_GRACE_PERIOD_MS))
```

### FILTER 4: Duplicate Detection Merging
**Method**: `_should_merge_with_existing()` (lines 1746-1800)

```python
def _should_merge_with_existing(self, session_id: str, timestamp: datetime,
                                voltage: float, channel: str,
                                merge_window_ms: float = 150.0) -> Optional[str]:
    """
    Check if detection should be merged with existing detection.

    Returns:
        - Existing detection ID if merge should happen
        - None if this is a new unique detection
    """
    # Find duplicates within time window
    duplicates = self._find_duplicate_detections(session_id, timestamp, merge_window_ms)

    if not duplicates:
        return None  # New detection

    # Filter by same channel
    same_channel_duplicates = [d for d in duplicates if d.channel == channel]

    if not same_channel_duplicates:
        return None  # No duplicates on this channel

    # Find highest voltage detection in window
    best_match = max(same_channel_duplicates, key=lambda d: d.voltage)

    if best_match.voltage >= voltage:
        # DETECTION DROPPED: Merged with stronger existing signal
        logger.info(f"🔗 Merging duplicate detection with existing {best_match.id}")
        return best_match.id  # ← DETECTION MERGED (not saved separately)

    # This detection is stronger - mark old ones as duplicates
    for dup in same_channel_duplicates:
        dup.is_duplicate = True

    return None  # Save this as primary detection
```

**Filtering Criteria**:
- Time window: **150ms** (hardcoded in method calls)
- Same channel only
- Lower voltage detections merged into higher voltage
- Prevents saving near-duplicate events

**Spatial-Temporal Clustering**: `_apply_spatial_temporal_clustering()` (lines 1802-1868)
```python
def _apply_spatial_temporal_clustering(self, session_id: str,
                                      events: List[DetectionEvent],
                                      time_threshold_ms: float = 150.0) -> List[DetectionEvent]:
    """
    Cluster nearby detections and keep only representative events.
    """
    clusters = []
    current_cluster = [sorted_events[0]]

    for i in range(1, len(sorted_events)):
        time_diff_ms = (sorted_events[i].timestamp - current_cluster[-1].timestamp).total_seconds() * 1000

        if (sorted_events[i].channel == current_cluster[0].channel and
            time_diff_ms <= time_threshold_ms):
            current_cluster.append(sorted_events[i])
        else:
            clusters.append(current_cluster)
            current_cluster = [sorted_events[i]]

    # Keep highest voltage from each cluster
    filtered_events = []
    for cluster in clusters:
        if len(cluster) == 1:
            filtered_events.append(cluster[0])
        else:
            best_detection = max(cluster, key=lambda e: e.voltage)
            filtered_events.append(best_detection)

            # Mark others as duplicates
            for event in cluster:
                if event.id != best_detection.id:
                    event.is_duplicate = True  # ← DETECTION MARKED AS DUPLICATE

    return filtered_events
```

### Decision Statistics Tracking
```python
# Internal counters (per session)
self._decision_stats = {
    'threshold_cross': 0,     # Normal detections
    'debounce_skipped': 0,    # Filtered by debounce
    'continuous': 0,          # Continuous mode samples
    'continuous_throttled': 0, # Throttled continuous
    'steady_high': 0,         # Steady high logging
    'before_window': 0,       # Before video window
    'after_window': 0         # After video window
}
```

---

## STAGE 3: Dedicated LabJack Monitor

### File: `/backend/services/dedicated_labjack_monitor.py`

### FILTER 5: Active Session Validation
**Method**: `_handle_detection_with_video_sync()` (lines 908-920)

```python
def _handle_detection_with_video_sync(self, session_id: str, labjack_event) -> None:
    """
    Handle detection event with video timing synchronization.
    """
    # FILTER: Only process detections for ACTIVE sessions
    if session_id not in self.active_sessions:
        # DETECTION DROPPED: Session not active or already completed
        logger.debug(f"🚫 Skipping detection for inactive session: {session_id}")
        return  # ← DETECTION LOST HERE

    session_info = self.active_sessions.get(session_id)
    if not session_info:
        # DETECTION DROPPED: Session disappeared during processing
        logger.warning(f"⚠️ Session {session_id} disappeared while processing detection.")
        return  # ← DETECTION LOST HERE
```

**Filtering Criteria**:
- Session must exist in `self.active_sessions`
- Session must not be completed or stopped
- Prevents processing detections after session cleanup

### FILTER 6: Timing Ready Timeout
**Method**: `_handle_detection_with_video_sync()` (lines 930-950)

```python
# Wait for timing data to be ready
timing_ready_event = session_info.get('timing_ready_event')
timing_available = True

if timing_ready_event:
    # CRITICAL: 10 second timeout for timing readiness
    is_set = timing_ready_event.wait(timeout=10.0)

    if not is_set:
        # TIMING DEGRADED: Video timing not ready after 10s
        logger.warning(f"⚠️ Timing data not ready after 10s for session {session_id}")
        timing_available = False
        timing_degraded = True
        # IMPORTANT: Detection is NOT dropped, but marked as degraded
        # Will use wall clock timestamp instead of video-relative timing
```

**Impact**:
- Detections NOT dropped, but marked with degraded timing quality
- Fallback to wall clock timestamps
- May affect ground truth matching accuracy

### FILTER 7: Video-Relative Timing Calculation
**Method**: `_handle_detection_with_video_sync()` (lines 970-1100)

```python
# Calculate video-relative timing
timing_data = self.video_timing_service.calculate_video_relative_latency(
    session_id, labjack_trigger_time
)

if timing_data is None or not timing_data.get('video_relative_timestamp'):
    # FALLBACK: Apply calibrated timing calculation
    logger.warning(f"Video timing service failed, using calibrated fallback timing")

    # Dynamic calibration offset calculation
    dynamic_calibration_offset_ms = self.labjack_monitor.calculate_calibration_offset(session_id)

    # Calculate fallback video-relative timestamp
    video_start_time = session_info.get('video_start_time')
    if video_start_time:
        reference_time = video_start_time + (dynamic_calibration_offset_ms / 1000.0)
        fallback_video_relative = labjack_trigger_time - reference_time

        timing_data = {
            'video_relative_timestamp': max(0.0, fallback_video_relative),
            'actual_latency_ms': 50.0,
            'video_frame_number': int(max(0.0, fallback_video_relative) * 24),
            'timing_sync_quality': 'calibrated_direct',
            'calibration_applied': True,
            'calibration_offset_ms': dynamic_calibration_offset_ms
        }
    else:
        # ULTIMATE FALLBACK: Estimated timing
        estimated_video_time = (labjack_trigger_time % 10)
        timing_data = {
            'video_relative_timestamp': estimated_video_time,
            'actual_latency_ms': 50.0,
            'video_frame_number': int(estimated_video_time * 24),
            'timing_sync_quality': 'estimated_fallback',
            'calibration_applied': False
        }
```

**Timing Quality Levels**:
1. **`video_timing_service`** - Full video synchronization (best)
2. **`calibrated_direct`** - Fallback with dynamic calibration
3. **`video_start_fallback`** - Basic video start reference
4. **`estimated_fallback`** - Crude estimate (worst)

### Detection Event Storage
**Method**: `_store_detection_event_async()` (lines 2063-2150)

```python
async def _store_detection_event_async(self, hil_event: HILDetectionEvent) -> None:
    """
    Store detection event in database with error handling.
    """
    try:
        db = SessionLocal()
        try:
            # Create database record
            detection_record = DetectionEvent(
                id=hil_event.id,
                test_session_id=hil_event.session_id,
                timestamp=datetime.fromtimestamp(hil_event.unix_timestamp, tz=timezone.utc),
                video_relative_timestamp=hil_event.video_relative_timestamp,
                actual_latency_ms=hil_event.actual_latency_ms,
                video_frame_number=hil_event.video_frame_number,
                labjack_voltage=hil_event.labjack_voltage,
                detection_channel=hil_event.detection_channel,
                timing_sync_quality=hil_event.timing_sync_quality,
                video_id=hil_event.video_id,
                sequence_video_result_id=hil_event.sequence_video_result_id
            )

            db.add(detection_record)
            db.commit()
            db.refresh(detection_record)

            logger.info(f"✅ Detection stored: {hil_event.id[:12]} @ {hil_event.video_relative_timestamp:.3f}s")

        except SQLAlchemyError as e:
            db.rollback()
            # DETECTION MAY BE LOST: Database error during storage
            logger.error(f"❌ Failed to store detection {hil_event.id}: {e}")
            raise
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ Unexpected error storing detection: {e}")
```

**Potential Loss Points**:
- Database connection failures
- Transaction rollback on constraint violations
- SQLAlchemy errors during commit

---

## STAGE 4: Database Storage Layer

### Table: `detection_events`

**Schema** (from models):
```sql
CREATE TABLE detection_events (
    id VARCHAR PRIMARY KEY,
    test_session_id VARCHAR NOT NULL REFERENCES test_sessions(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    video_relative_timestamp FLOAT,
    actual_latency_ms FLOAT,
    video_frame_number INTEGER,
    labjack_voltage FLOAT NOT NULL,
    detection_channel VARCHAR NOT NULL,
    timing_sync_quality VARCHAR,
    validation_result VARCHAR,
    video_id VARCHAR REFERENCES videos(id),
    sequence_video_result_id VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Database Constraints
1. **Foreign Key**: `test_session_id` must exist in `test_sessions`
2. **Foreign Key**: `video_id` must exist in `videos` (if not NULL)
3. **NOT NULL**: `timestamp`, `labjack_voltage`, `detection_channel`

**Potential Filtering**:
- Foreign key constraint violations → INSERT fails
- Database transaction failures → Data loss
- No explicit filtering at this layer (all valid records stored)

---

## STAGE 5: API Retrieval Layer

### File: `/backend/routers/hil_testing.py`

### Endpoint: `GET /{session_id}/detection-events`
**Method**: `get_hil_detection_events()` (lines 192-240)

```python
@router.get("/{session_id}/detection-events")
async def get_hil_detection_events(
    session_id: str,
    include_screenshots: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get HIL detection events with screenshot evidence and timing data.
    """
    try:
        # Verify session exists
        test_session = db.query(TestSession).filter(
            TestSession.id == session_id
        ).first()

        if not test_session:
            raise HTTPException(status_code=404, detail=f"Test session {session_id} not found")

        # Query detection events
        detection_events = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).order_by(DetectionEvent.timestamp).all()

        # Get HIL-specific events from monitoring service
        hil_events = get_hil_session_events(session_id)

        # Enhance with screenshot URLs
        enhanced_events = []
        for event in detection_events:
            event_data = {
                'id': event.id,
                'detection_id': getattr(event, 'detection_id', None),
                'timestamp': event.timestamp,
                'video_relative_timestamp': event.video_relative_timestamp,
                'actual_latency_ms': event.actual_latency_ms,
                'video_frame_number': event.video_frame_number,
                'labjack_voltage': event.labjack_voltage,
                'detection_channel': event.detection_channel,
                'timing_sync_quality': event.timing_sync_quality,
                'validation_result': event.validation_result,
                'video_id': event.video_id
            }

            # Add screenshot URLs if available
            if include_screenshots:
                event_data['screenshot_url'] = f"/screenshots/{event.id}/screen.png"
                event_data['screenshot_zoom_url'] = f"/screenshots/{event.id}/zoom.png"

            enhanced_events.append(event_data)

        return {
            'session_id': session_id,
            'detection_count': len(enhanced_events),
            'events': enhanced_events
        }

    except Exception as e:
        logger.error(f"Error getting HIL detection events for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Query Logic**:
- **Filter**: `test_session_id == session_id`
- **Order**: `timestamp ASC`
- **No additional filtering** - returns all stored detections

**No filtering at API layer** - all database records are returned.

---

## Summary: All Filtering Points & Values

### Table: Complete Filtering Configuration

| Stage | Filter Name | Location | Default Value | Configurable? | Environment Variable | Impact |
|-------|-------------|----------|---------------|---------------|---------------------|--------|
| **1** | Hardware Sampling | `labjack_config.py` | 10,000 Hz | ✅ | `LABJACK_SAMPLE_RATE` | Determines maximum temporal resolution |
| **2A** | Debounce Filter | `labjack_detection_service.py:1565` | **20ms** | ✅ | N/A (config param) | **Drops detections < 20ms apart** |
| **2B** | Constant Voltage Bypass | `DetectionConfig.constant_voltage_mode` | `False` | ✅ | N/A | **Disables debounce when True** |
| **2C** | Continuous Throttle | `labjack_detection_service.py:1576` | 5ms | ✅ | N/A | Limits continuous sample rate |
| **2D** | Video Window Start | `timing_config.py:22` | **2000ms grace** | ✅ | `HIL_GRACE_PERIOD_MS` | **Drops detections before video start - grace** |
| **2E** | Video Window End | `timing_config.py:22` | **2000ms grace** | ✅ | `HIL_GRACE_PERIOD_MS` | **Drops detections after video end + grace** |
| **2F** | Duplicate Merge Window | `labjack_detection_service.py:1752` | **150ms** | ❌ | N/A | **Merges detections within 150ms** |
| **2G** | Clustering Window | `labjack_detection_service.py:1820` | **150ms** | ❌ | N/A | **Groups similar detections** |
| **3A** | Active Session Check | `dedicated_labjack_monitor.py:908` | N/A | ❌ | N/A | **Drops if session inactive** |
| **3B** | Timing Ready Timeout | `dedicated_labjack_monitor.py:940` | **10 seconds** | ❌ | N/A | Degrades timing quality, not dropped |
| **3C** | Video Timing Calculation | `dedicated_labjack_monitor.py:970` | N/A | N/A | N/A | Fallback logic, not dropped |
| **4** | Database Constraints | `models.py` | N/A | ❌ | N/A | Foreign key violations drop |
| **5** | API Query Filter | `hil_testing.py:215` | N/A | ❌ | N/A | **None - all stored events returned** |

### Critical Thresholds Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                   CRITICAL TIMING VALUES                         │
├──────────────────────────────────────────────────────────────────┤
│ Debounce Period:           20ms  (allows 50 detections/second)  │
│ Video Grace Period:        2000ms (±2s around video window)     │
│ Duplicate Merge Window:    150ms (groups near-simultaneous)     │
│ Clustering Window:         150ms (spatial-temporal grouping)    │
│ Timing Ready Timeout:      10s   (max wait for video timing)    │
│ Matching Tolerance:        100ms (GT vs detection alignment)    │
│ Continuous Sample Interval: 5ms  (when continuous mode active)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Detection Loss Scenarios

### Scenario 1: Rapid Fire Detections
**Cause**: Hardware triggers multiple times within debounce window
**Filter**: Stage 2A - Debounce Filter
**Loss Rate**: All detections < 20ms apart from previous detection
**Solution**: Enable `constant_voltage_mode = True` to bypass debounce

### Scenario 2: Pre-Video Detections
**Cause**: Hardware trigger fires before video starts playing
**Filter**: Stage 2D - Video Window Start
**Loss Rate**: All detections before `video_start - 2000ms`
**Solution**: Increase `HIL_GRACE_PERIOD_MS` environment variable

### Scenario 3: Post-Video Detections
**Cause**: Hardware trigger fires after video ends
**Filter**: Stage 2E - Video Window End
**Loss Rate**: All detections after `video_end + 2000ms`
**Solution**: Increase `HIL_GRACE_PERIOD_MS` environment variable

### Scenario 4: Duplicate Signal Bounce
**Cause**: Electrical noise or signal bounce creates multiple triggers
**Filter**: Stage 2F/2G - Duplicate Merge/Clustering
**Loss Rate**: All detections within 150ms of stronger signal
**Solution**: Improve hardware signal conditioning, or disable clustering

### Scenario 5: Session Timing Race
**Cause**: Detection arrives before session is fully initialized
**Filter**: Stage 3A - Active Session Check
**Loss Rate**: All detections during session startup (~100-200ms)
**Solution**: Ensure `start_monitoring` completes before video playback

### Scenario 6: Database Transaction Failure
**Cause**: Database connection error or constraint violation
**Filter**: Stage 4 - Database Constraints
**Loss Rate**: Variable, depends on database health
**Solution**: Monitor database connection pool, check foreign keys

---

## Recommendations for Maximizing Detection Capture

### 1. Disable Debounce for Constant Voltage Testing
```python
config = DetectionConfig(
    session_id=session_id,
    channels=['AIN0'],
    voltage_threshold=2.5,
    constant_voltage_mode=True,  # ← Bypass debounce filter
    enable_duplicate_filtering=False,  # ← Disable merging
    enable_spatial_temporal_clustering=False  # ← Disable clustering
)
```

### 2. Extend Grace Period for Edge Detection
```bash
export HIL_GRACE_PERIOD_MS=5000  # 5 seconds instead of 2
```

### 3. Reduce Debounce for High-Frequency Events
```python
config = DetectionConfig(
    debounce_ms=5,  # Minimum safe value for 200Hz sampling
)
```

### 4. Monitor Filter Statistics
```python
# Check decision statistics after session
stats = labjack_monitor.get_decision_stats(session_id)
print(f"Detections captured: {stats['threshold_cross']}")
print(f"Debounce filtered: {stats['debounce_skipped']}")
print(f"Before window: {stats['before_window']}")
print(f"After window: {stats['after_window']}")
```

### 5. Enable Debug Logging
```python
import logging
logging.getLogger('labjack_detection_service').setLevel(logging.DEBUG)
logging.getLogger('dedicated_labjack_monitor').setLevel(logging.DEBUG)
```

---

## Diagnostic Commands

### Check Current Configuration
```bash
# View timing configuration
cat /home/rigade/Testing/ai-model-validation-platform/backend/config/timing_config.py

# Check environment overrides
echo $HIL_GRACE_PERIOD_MS
echo $HIL_MATCHING_TOLERANCE_MS
echo $LABJACK_SAMPLE_RATE
```

### Query Detection Statistics
```sql
-- Count detections by session
SELECT
    test_session_id,
    COUNT(*) as detection_count,
    MIN(timestamp) as first_detection,
    MAX(timestamp) as last_detection,
    AVG(actual_latency_ms) as avg_latency
FROM detection_events
GROUP BY test_session_id;

-- Check for duplicate detection clusters
SELECT
    test_session_id,
    video_relative_timestamp,
    COUNT(*) as cluster_size
FROM detection_events
GROUP BY test_session_id, ROUND(video_relative_timestamp * 1000 / 150)  -- 150ms windows
HAVING COUNT(*) > 1
ORDER BY cluster_size DESC;
```

### Check Session Timing Windows
```python
import asyncio
from services.dedicated_labjack_monitor import get_dedicated_labjack_monitor

monitor = get_dedicated_labjack_monitor()
session_info = monitor.active_sessions.get(session_id)

if session_info:
    video_start = session_info.get('video_start_time')
    video_duration = session_info.get('video_duration')
    grace_period = 2.0  # seconds

    print(f"Valid detection window:")
    print(f"  Start: {video_start - grace_period}")
    print(f"  End: {video_start + video_duration + grace_period}")
```

---

## Architecture Decision Records

### ADR-001: Debounce Reduction to 20ms
**Context**: Original 100ms debounce was filtering legitimate detections at 24fps (41.67ms frame period)
**Decision**: Reduced to 20ms to allow 2 detections per frame
**Consequences**:
- ✅ Captures more legitimate detections
- ⚠️ May increase duplicate detections
- ✅ Better alignment with video frame rate

### ADR-002: 150ms Duplicate Merge Window
**Context**: Hardware signal bounce can create multiple triggers
**Decision**: Merge detections within 150ms, keep highest voltage
**Consequences**:
- ✅ Reduces false positives from signal bounce
- ⚠️ May merge legitimate rapid detections
- ✅ Improves precision metrics

### ADR-003: 2-Second Grace Period
**Context**: Video timing synchronization not exact, hardware may trigger slightly early/late
**Decision**: Allow ±2 seconds around video playback window
**Consequences**:
- ✅ Captures edge-case detections
- ⚠️ May include out-of-scope triggers
- ✅ Tolerates timing drift

### ADR-004: Constant Voltage Bypass Mode
**Context**: Testing scenarios need to capture every single detection
**Decision**: Add `constant_voltage_mode` to bypass all filtering
**Consequences**:
- ✅ 100% capture rate for testing
- ⚠️ Produces many duplicates
- ✅ Allows validation of filtering logic

---

## Appendix: File Locations

| Component | File Path |
|-----------|-----------|
| Timing Config | `/backend/config/timing_config.py` |
| LabJack Config | `/backend/config/labjack_config.py` |
| Detection Service | `/backend/services/labjack_detection_service.py` |
| Dedicated Monitor | `/backend/services/dedicated_labjack_monitor.py` |
| API Endpoints | `/backend/routers/hil_testing.py` |
| Database Models | `/backend/models.py` |

---

## Glossary

- **Debounce**: Minimum time between consecutive detections to prevent duplicates
- **Grace Period**: Extended time window around video playback for timing tolerance
- **Merge Window**: Time range for combining duplicate detections
- **Clustering**: Grouping spatially and temporally close detections
- **Video-Relative Timestamp**: Detection time relative to video start (not wall clock)
- **Timing Sync Quality**: Indicator of timing calculation accuracy (video_timing_service, calibrated_direct, fallback, estimated)

---

*Document generated: 2025-11-25*
*System Architecture: Hardware-in-the-Loop Detection Pipeline*
*Version: 1.0*
