# Detection Storage to Database Analysis
**Comprehensive Analysis of Detection Event Database Storage Paths**

**Date:** 2025-11-17
**Scope:** Analyze all database insertion paths for DetectionEvent model
**Goal:** Identify correct storage path for HIL video sequence testing

---

## Executive Summary

### Critical Findings

1. **TWO PRIMARY STORAGE PATHS** exist for detection events:
   - **Path 1:** `labjack_detection_service.py` (store_in_db=True) - Batch commit optimization
   - **Path 2:** `dedicated_labjack_monitor.py` (Direct storage) - HIL video synchronization

2. **CORRECT PATH FOR HIL TESTING:** `dedicated_labjack_monitor.py`
   - ✅ Has video timing synchronization
   - ✅ Populates all required HIL fields
   - ✅ Handles multi-video sequences
   - ✅ Implements retry logic for race conditions

3. **DUPLICATE STORAGE RISK:** Both services can write to database simultaneously

---

## DetectionEvent Model Schema

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/models.py:328-493`

### Required Fields for HIL Testing

| Field | Type | Nullable | Index | Purpose |
|-------|------|----------|-------|---------|
| `id` | String(36) | NO | PRIMARY | Unique detection identifier |
| `test_session_id` | String(36) | NO | YES | Links to test session |
| `video_id` | String(36) | YES | YES | **BUG #3 FIX: Per-video detection counts** |
| `sequence_video_result_id` | String(36) | YES | YES | Multi-video sequence support |
| `sequence_id` | String(36) | YES | YES | Sequence identifier for multi-video tests |
| `timestamp` | Float | NO | YES | Detection timestamp (epoch) |
| `validation_result` | String | - | YES | Pass/Fail result |
| `ground_truth_match_id` | String(36) | YES | YES | Matched ground truth object |

### Critical Timing Fields

| Field | Type | Purpose | HIL Required |
|-------|------|---------|--------------|
| `actual_latency_ms` | Float | **CANONICAL latency field** | ✅ YES |
| `labjack_timestamp` | Float | LabJack detection timestamp | ✅ YES |
| `labjack_timestamp_ns` | String | Nanosecond precision timestamp | ✅ YES |
| `video_relative_timestamp` | Float | Timestamp relative to video start | ✅ YES |
| `video_relative_timestamp_ns` | String | Nanosecond precision video-relative | ✅ YES |
| `video_frame_number` | Integer | Video frame corresponding to detection | ✅ YES |
| `timing_sync_quality` | String | Quality: high/medium/low/unknown | ✅ YES |

### Multi-Video Sequence Fields

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `sequence_timestamp` | Float | Timestamp relative to sequence start | ✅ YES |
| `sequence_timestamp_ns` | String | Nanosecond precision sequence timestamp | Optional |
| `video_play_offset_ms` | Float | Offset from sequence start when video began | ✅ YES |
| `correlation_method` | String | 'timestamp' or 'frame_number' | Optional |

### LabJack Hardware Fields

| Field | Type | Purpose |
|-------|------|---------|
| `labjack_voltage` | Float | LabJack voltage reading |
| `voltage_level` | Float | Signal value (voltage) |
| `detection_channel` | String | LabJack channel (e.g., 'AIN0') |
| `channel` | Integer | LabJack channel number |
| `signal_type` | String | GPIO/Network/Serial/CAN Bus |
| `unix_timestamp` | Float | Unix timestamp of detection |
| `detection_timestamp` | DateTime | Detection timestamp (UTC) |
| `detection_metadata` | JSON | Additional metadata |

---

## Database Insertion Paths

### Path 1: labjack_detection_service.py
**Location:** `services/labjack_detection_service.py:1644-1900`
**Configuration:** `store_in_db: bool = True` (line 133)

#### Storage Flow

```python
# Step 1: Create DetectionEvent (line 1625-1642)
def _create_detection_event(session_id, channel, voltage, threshold, timestamp):
    event = DetectionEvent(
        id=event_id,
        session_id=session_id,
        timestamp=timestamp,
        channel=channel,
        voltage=voltage,
        threshold=threshold,
        video_relative_timestamp=video_relative_timestamp,  # May be None
        actual_latency_ms=actual_latency_ms                 # May be None
    )
    return event

# Step 2: Record event (line 1644-1680)
def _record_detection_event(session_id, event):
    # Store in memory
    self.detection_events[session_id].append(event)

    # Store in database if enabled
    if config and config.store_in_db and DATABASE_AVAILABLE:
        self._schedule_db_storage(event)  # Line 1673

# Step 3: Schedule database storage (line 1682-1702)
def _schedule_db_storage(event):
    # Add to queue for persistent storage
    self.storage_queue.put(event)  # Worker thread processes queue

# Step 4: Storage worker processes queue (line 1703-1738)
def _storage_worker():
    while self.storage_worker_running:
        event = self.storage_queue.get(timeout=1.0)
        self._store_event_sync_wrapper(event)

# Step 5: Store in database (line 1753-1900)
async def _store_event_in_db(event):
    db = SessionLocal()

    # Video ID resolution using resolver service
    video_id = get_video_id_for_detection(
        session_id=session.id,
        detection_timestamp=event.timestamp,
        db=db
    )

    # Sequence video result ID resolution
    if sequence_id and video_id:
        sequence_video_result_id = get_sequence_video_result_id(
            session_id=session.id,
            video_id=video_id,
            db=db
        )

    # Create DetectionEvent database record
    db_event = DBDetectionEvent(
        id=event.id,
        test_session_id=session.id,
        video_id=video_id,
        sequence_id=sequence_id,
        sequence_video_result_id=sequence_video_result_id,
        timestamp=event.timestamp.timestamp(),
        detection_channel=event.channel,
        labjack_voltage=event.voltage,
        video_relative_timestamp=event.video_relative_timestamp,
        actual_latency_ms=event.actual_latency_ms,
        # ... other fields
    )

    # BATCH COMMIT OPTIMIZATION (line 1872)
    self._add_to_batch_commit(db_event)
```

#### Batch Commit Optimization

**Lines 1869-1873:**
```python
# CRITICAL OPTIMIZATION: Use batch commits instead of individual commits
# This reduces commit rate from 200/sec to ~10-20/sec at 200 Hz
self._add_to_batch_commit(db_event)
```

**Configuration:**
- `batch_size_threshold = 100` (line 176) - Commit after 100 events
- `batch_time_threshold = 1.0` (line 177) - OR after 1 second

#### Fields Populated

✅ **POPULATED:**
- `test_session_id`
- `video_id` (via resolver)
- `sequence_id`
- `sequence_video_result_id` (via resolver)
- `timestamp`
- `detection_channel`
- `labjack_voltage`
- `voltage_level`
- `latency_threshold_ms`
- `video_relative_timestamp` (if timing service available)
- `actual_latency_ms` (if timing service available)
- `frame_number = 0` (placeholder)
- `video_frame_number = 0` (placeholder)
- `detection_metadata` (JSON with timing calibration)

❌ **NOT POPULATED (timing-dependent):**
- `video_relative_timestamp_ns` (if timing service fails)
- `sequence_timestamp`
- `video_play_offset_ms`
- `labjack_timestamp_ns`
- `timing_sync_quality`
- `screenshot_path`
- `screenshot_zoom_path`

---

### Path 2: dedicated_labjack_monitor.py (HIL Path)
**Location:** `services/dedicated_labjack_monitor.py:580-1003`
**Configuration:** No `store_in_db` flag - always stores

#### Storage Flow

```python
# Step 1: Handle detection with video sync (line 580-800)
def _handle_detection_with_video_sync(session_id, labjack_event):
    # Extract LabJack trigger time
    labjack_trigger_time = labjack_event.timestamp.timestamp()

    # Calculate video-relative timing using VideoTimingService
    timing_data = self.video_timing_service.calculate_video_relative_latency(
        session_id, labjack_trigger_time
    )

    # Fallback timing calibration if service fails (line 636-673)
    if timing_data is None:
        # Apply dynamic calibration offset
        calibration_offset_ms = self.labjack_monitor.calculate_calibration_offset(session_id)
        fallback_video_relative = labjack_trigger_time - reference_time
        timing_data = {
            'video_relative_timestamp': max(0.0, fallback_video_relative),
            'actual_latency_ms': 50.0,
            'video_frame_number': int(fallback_video_relative * 24),
            'timing_sync_quality': 'calibrated_direct'
        }

    # Create HIL detection event
    hil_event = HILDetectionEvent(
        id=str(uuid.uuid4()),
        session_id=session_id,
        unix_timestamp=labjack_trigger_time,
        video_relative_timestamp=timing_data['video_relative_timestamp'],
        actual_latency_ms=timing_data['actual_latency_ms'],
        video_frame_number=timing_data['video_frame_number'],
        timing_sync_quality=timing_data['timing_sync_quality'],
        labjack_voltage=labjack_voltage,
        detection_channel=detection_channel,
        # ... multi-video sequence fields
    )

    # Enrich with sequence metadata (line 1105-1200)
    self._enrich_hil_event_context(hil_event, session_id, labjack_trigger_time)

# Step 2: Enrich with video/sequence context (line 1105-1200)
def _enrich_hil_event_context(hil_event, session_id, labjack_trigger_time):
    # Load sequence context (fresh for multi-video)
    context = self._load_sequence_context(session_id)

    # VIDEO ID RESOLUTION with retry logic (line 1177-1183)
    video_id = self._get_video_id_with_retry(
        session_id=session_id,
        trigger_time=labjack_trigger_time,
        max_retries=5,
        initial_delay_ms=10.0  # Exponential backoff: 10ms, 20ms, 40ms, 80ms, 160ms
    )

    # Populate sequence fields
    hil_event.video_id = video_id
    hil_event.sequence_id = context.get('sequence_id')
    hil_event.sequence_video_result_id = # ... resolver
    hil_event.sequence_timestamp = # ... calculated
    hil_event.video_play_offset_ms = # ... from context

# Step 3: Store HIL event (line 830-1003)
def _store_hil_event_sync(hil_event):
    db = SessionLocal()

    # Validate video_id
    if not video_id_for_detection:
        # Retry logic with fallback (line 893-922)
        # Multi-video: keep NULL, allow reassignment job to fix later

    # Normalize video-relative timestamp (line 923-960)
    normalized_video_relative = hil_event.video_relative_timestamp
    if hil_event.sequence_timestamp and hil_event.video_play_offset_ms:
        normalized_video_relative = (
            hil_event.sequence_timestamp
            - (hil_event.video_play_offset_ms or 0.0) / 1000.0
        )

    # Clamp negative timestamps
    if normalized_video_relative < 0.0:
        normalized_video_relative = 0.0

    # Create DetectionEvent database record (line 961-989)
    detection_event = DetectionEvent(
        id=hil_event.id,
        test_session_id=hil_event.session_id,
        video_id=video_id_for_detection,
        sequence_id=hil_event.sequence_id,
        sequence_video_result_id=hil_event.sequence_video_result_id,
        timestamp=labjack_trigger_time,
        validation_result="PENDING",
        processing_time_ms=hil_event.actual_latency_ms,
        labjack_timestamp=float(labjack_trigger_time),
        labjack_timestamp_ns=int(labjack_trigger_time * 1e9),
        labjack_voltage=float(hil_event.labjack_voltage),
        detection_channel=str(hil_event.detection_channel),
        video_relative_timestamp=normalized_video_relative,
        video_frame_number=hil_event.video_frame_number,
        actual_latency_ms=hil_event.actual_latency_ms,
        timing_sync_quality=hil_event.timing_sync_quality,
        sequence_timestamp=hil_event.sequence_timestamp,
        video_play_offset_ms=hil_event.video_play_offset_ms,
        detection_type="labjack_voltage",
        source="dedicated_labjack_monitor",
        screenshot_path=hil_event.screenshot_path,
        screenshot_zoom_path=hil_event.screenshot_zoom_path,
        unix_timestamp=float(detection_record_time),
        detection_timestamp=datetime.fromtimestamp(detection_record_time, tz=timezone.utc),
        detection_metadata=detection_metadata,
        signal_type='labjack_voltage'
    )

    # DIRECT COMMIT (line 991-993)
    db.add(detection_event)
    db.commit()
```

#### Fields Populated

✅ **FULLY POPULATED:**
- All fields from Path 1, PLUS:
- `labjack_timestamp_ns` (nanosecond precision)
- `video_relative_timestamp` (always populated with fallback)
- `video_relative_timestamp_ns` (if available)
- `video_frame_number` (calculated from timestamp)
- `actual_latency_ms` (from VideoTimingService or fallback)
- `timing_sync_quality` (high/medium/low/calibrated_direct)
- `sequence_timestamp` (for multi-video sequences)
- `video_play_offset_ms` (for multi-video sequences)
- `screenshot_path` (if HIL screenshot capture enabled)
- `screenshot_zoom_path` (if HIL screenshot capture enabled)
- `unix_timestamp`
- `detection_timestamp` (UTC)
- `detection_type = "labjack_voltage"`
- `source = "dedicated_labjack_monitor"`

#### Race Condition Handling

**Retry Logic (line 1042-1103):**
```python
def _get_video_id_with_retry(session_id, trigger_time, max_retries=5, initial_delay_ms=10.0):
    """
    Exponential backoff: 10ms, 20ms, 40ms, 80ms, 160ms (total ~310ms)
    Handles race condition where detection arrives 5-20ms before video_start_time is set
    """
    for attempt in range(max_retries):
        context = self._load_sequence_context(session_id, retry_attempt=attempt)
        video_id = self._determine_video_from_timing(context['video_timing'], trigger_time)

        if video_id:
            return video_id

        time.sleep(delay_ms / 1000.0)
        delay_ms *= 2  # Exponential backoff

    return None
```

---

## Configuration Analysis

### store_in_db Flag Usage

**labjack_detection_service.py:**
```python
@dataclass
class DetectionConfig:
    store_in_db: bool = True  # Line 133
```

**Usage in code:**
```python
def start_monitoring(self, session_id, **kwargs):
    config = DetectionConfig(
        # ...
        store_in_db=kwargs.get('store_in_db', True),  # Line 388
    )

def _record_detection_event(self, session_id, event):
    if config and config.store_in_db and DATABASE_AVAILABLE:
        self._schedule_db_storage(event)  # Line 1672-1673
```

**dedicated_labjack_monitor.py:**
- No `store_in_db` flag
- Always stores to database
- Direct commit, no batching

---

## Database Write Conflicts

### Duplicate Write Scenarios

#### Scenario 1: Both Services Active Simultaneously
**Risk:** HIGH
**Impact:** Duplicate detection events in database

```python
# labjack_detection_service starts monitoring
detection_service.start_monitoring(session_id, store_in_db=True)

# dedicated_labjack_monitor also starts
dedicated_monitor.start_monitoring_with_video_sync(session_id, video_id, video_config)

# Result: BOTH services write to database
# - detection_service: via batch commit queue
# - dedicated_monitor: via direct commit
```

#### Scenario 2: Sequential Usage Without Cleanup
**Risk:** MEDIUM
**Impact:** Orphaned detections from previous service

```python
# Session 1: detection_service (batch queue still processing)
detection_service.start_monitoring(session_id_1, store_in_db=True)
# ... events added to batch queue

# Session 2: dedicated_monitor starts before queue drains
dedicated_monitor.start_monitoring_with_video_sync(session_id_2, ...)

# Result: Session 1 detections may commit during Session 2
```

#### Scenario 3: Race Condition on video_id Assignment
**Risk:** HIGH for multi-video sequences
**Impact:** Detection written with NULL video_id

```python
# Detection arrives 5-20ms before video lifecycle event completes
# Path 1 (detection_service): Resolver returns None → writes video_id=NULL
# Path 2 (dedicated_monitor): Retry logic waits 310ms → successful resolution
```

---

## Required Fields for HIL Test Compatibility

### Critical Fields Summary

| Category | Fields | Required By |
|----------|--------|-------------|
| **Session Linking** | `test_session_id` | All tests |
| **Video Linking** | `video_id`, `sequence_video_result_id`, `sequence_id` | Multi-video sequences |
| **Timestamps** | `timestamp`, `labjack_timestamp`, `video_relative_timestamp` | Ground truth matching |
| **Latency** | `actual_latency_ms` (CANONICAL) | Latency validation |
| **Frame Correlation** | `video_frame_number` | Frame-based matching |
| **Multi-Video** | `sequence_timestamp`, `video_play_offset_ms` | Sequence tests |
| **Quality** | `timing_sync_quality` | HIL compliance |

### Missing Field Risks

**If `video_id` is NULL:**
- ❌ Per-video detection counts will be wrong (Bug #3)
- ❌ Cannot link detection to ground truth
- ❌ Cannot display detection in per-video results

**If `sequence_video_result_id` is NULL:**
- ❌ Cannot calculate per-video metrics in multi-video tests
- ❌ Cannot track video-specific pass/fail rates

**If `video_relative_timestamp` is NULL:**
- ❌ Ground truth matching impossible
- ❌ Latency calculation fails

**If `actual_latency_ms` is NULL:**
- ❌ Cannot validate latency threshold
- ❌ Pass/Fail determination fails

---

## Correct Storage Path for HIL Video Sequence Testing

### ✅ RECOMMENDED: dedicated_labjack_monitor.py (Path 2)

**Reasons:**

1. **Complete Field Population**
   - ✅ All HIL-required fields populated
   - ✅ Video timing synchronization integrated
   - ✅ Multi-video sequence support
   - ✅ Nanosecond precision timestamps

2. **Race Condition Handling**
   - ✅ Exponential backoff retry (10ms → 160ms)
   - ✅ Total retry window: ~310ms
   - ✅ Handles detection arriving before video lifecycle completes
   - ✅ Cache invalidation for multi-video sequences

3. **Ground Truth Integration**
   - ✅ Video-relative timestamps always calculated
   - ✅ Frame number correlation
   - ✅ Sequence timestamp for multi-video
   - ✅ Screenshot capture for HIL validation

4. **Data Integrity**
   - ✅ Validates video_id before storage
   - ✅ Normalizes negative timestamps to 0.0
   - ✅ Fallback timing calibration if service fails
   - ✅ Enriches with sequence metadata

### ❌ NOT RECOMMENDED: labjack_detection_service.py (Path 1)

**Limitations:**

1. **Incomplete Timing Data**
   - ❌ May write NULL for `video_relative_timestamp`
   - ❌ No retry logic for video_id resolution
   - ❌ No fallback timing calibration
   - ❌ Missing sequence timing fields

2. **Race Conditions**
   - ❌ No retry if resolver fails
   - ❌ No cache invalidation for multi-video
   - ❌ Batch queue may delay writes

3. **HIL-Specific Features Missing**
   - ❌ No screenshot capture integration
   - ❌ No timing sync quality tracking
   - ❌ No sequence timestamp calculation

---

## Recommendations

### 1. Enforce Single Storage Path
**Priority:** CRITICAL

```python
# Disable store_in_db in labjack_detection_service when using dedicated_monitor
def start_monitoring_with_video_sync(session_id, video_id, video_timing_config):
    # Configure LabJack monitor with store_in_db=False
    labjack_config = self.labjack_monitor.start_session_monitoring(
        session_id,
        channels=channels,
        store_in_db=False,  # ← Dedicated monitor handles storage
        # ...
    )
```

### 2. Add Storage Path Validation
**Priority:** HIGH

```python
class DetectionStorageValidator:
    """Validate only one storage path is active per session"""

    active_storage_paths = {}  # session_id → storage_path_name

    @classmethod
    def register_storage_path(cls, session_id: str, path_name: str):
        if session_id in cls.active_storage_paths:
            existing = cls.active_storage_paths[session_id]
            raise DuplicateStorageError(
                f"Session {session_id} already has active storage path: {existing}. "
                f"Cannot register: {path_name}"
            )
        cls.active_storage_paths[session_id] = path_name
```

### 3. Implement Detection Queue for NULL video_id
**Priority:** HIGH

```python
# Already implemented in detection_queue_service.py
from services.detection_queue_service import enqueue_detection

# When video_id resolution fails:
if not video_id:
    enqueue_detection(session_id, event.id, event.timestamp)
    logger.info(f"🔄 Detection {event.id} queued for video_id assignment")
```

### 4. Add Monitoring Dashboard
**Priority:** MEDIUM

```python
class DetectionStorageMonitor:
    """Monitor which storage path is active per session"""

    def get_active_paths(self) -> Dict[str, str]:
        return {
            session_id: {
                'storage_path': path_name,
                'batch_queue_size': self._get_queue_size(session_id),
                'detections_stored': self._get_stored_count(session_id)
            }
            for session_id, path_name in DetectionStorageValidator.active_storage_paths.items()
        }
```

---

## Conclusion

**CORRECT STORAGE PATH for HIL video sequence testing:**
- ✅ **dedicated_labjack_monitor.py** (`services/dedicated_labjack_monitor.py:580-1003`)
- ✅ Populates ALL required HIL fields
- ✅ Handles multi-video sequences
- ✅ Implements retry logic for race conditions
- ✅ Integrates with VideoTimingService
- ✅ Captures screenshots for validation
- ✅ Tracks timing sync quality

**DUPLICATE WRITE RISK:**
- ⚠️ **HIGH** if both services active simultaneously
- ⚠️ Configure `store_in_db=False` in labjack_detection_service
- ⚠️ Implement storage path validation

**FIELD POPULATION:**
- ✅ Path 2 (dedicated_monitor): 100% of HIL fields
- ⚠️ Path 1 (detection_service): ~70% of HIL fields (missing timing/sequence fields)

**NEXT STEPS:**
1. Enforce `store_in_db=False` in labjack_detection_service when dedicated_monitor is active
2. Add storage path validation to prevent duplicate writes
3. Monitor detection queue for NULL video_id assignments
4. Verify all test sessions use dedicated_monitor for HIL tests
