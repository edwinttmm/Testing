# Dedicated LabJack Monitor - Complete Detection Flow Analysis

## Executive Summary

**Primary System**: `services/dedicated_labjack_monitor.py` is the **MAIN HIL testing system** for video sequence validation with hardware synchronization.

**Purpose**: Provides Hardware-in-the-Loop (HIL) validation by capturing LabJack hardware detections, synchronizing them with video timing, storing complete detection records, and emitting real-time updates to the frontend.

**Design**: Designed specifically for HIL tests with video sequences, including ground truth matching capabilities.

---

## 1. System Architecture Overview

### Core Components

```
LabJack Hardware → DedicatedLabJackMonitor → Database (detection_events) → WebSocket → Frontend
                          ↓
                   VideoTimingService
                   (timestamp sync)
                          ↓
                   HILGroundTruthComparison
                   (screenshot & matching)
```

### Key Services Integration

1. **DedicatedLabJackMonitor** - Main orchestration service
2. **VideoTimingService** - Video-relative timestamp conversion
3. **LabJackDetectionMonitor** - Hardware signal capture
4. **HILGroundTruthComparison** - Screenshot capture and ground truth matching
5. **WebSocket Rooms** - Real-time frontend communication

---

## 2. Complete Detection Flow - Step by Step

### Phase 1: Initialization (`start_monitoring_with_video_sync`)

**Entry Point**: `async def start_monitoring_with_video_sync(session_id, video_timing_config)`

**Sequence**:
```
1. Validate session and video configuration
2. Create detection callback: lambda event: _handle_detection_with_video_sync(session_id, event)
3. Start LabJack hardware monitoring FIRST (critical timing)
4. Initialize video timing service with session context
5. Store session metadata in active_sessions dict
```

**Critical Configuration**:
```python
labjack_config = {
    'channels': ['AIN0'],
    'voltage_threshold': 3.3,  # Detection threshold
    'debounce_ms': 0,          # No debounce - catch everything
    'sample_rate': 1000,       # High rate for precision
    'store_in_db': True,       # Enable persistence
    'enable_websocket': True   # Real-time updates
}
```

**Key Design Decision**: LabJack monitoring starts BEFORE video timing to prevent detection loss during early video frames.

---

### Phase 2: Detection Capture (`_handle_detection_with_video_sync`)

**Trigger**: LabJack hardware generates voltage event → callback fires

**Step-by-Step Processing**:

#### Step 2.1: Extract Hardware Data
```python
# Extract from LabJack event
labjack_trigger_time = labjack_event.timestamp.timestamp()  # Unix timestamp
detection_record_time = time.time()                         # Processing finish time
labjack_voltage = getattr(labjack_event, 'voltage', 0.0)   # Voltage reading
detection_channel = getattr(labjack_event, 'channel', 'AIN0')  # Hardware channel

# Calculate REAL processing latency
real_processing_latency_ms = (detection_record_time - labjack_trigger_time) * 1000.0
```

#### Step 2.2: Video Timing Synchronization
```python
# Convert Unix timestamp to video-relative timestamp
timing_data = video_timing_service.calculate_video_relative_latency(
    session_id,
    labjack_trigger_time
)

# Returns:
# {
#     'video_relative_timestamp': 2.456,      # Seconds from video start
#     'actual_latency_ms': 45.3,              # Processing latency
#     'video_frame_number': 59,               # Frame at detection time
#     'timing_sync_quality': 'synchronized',  # Quality indicator
#     'timing_precision_ns': 1000000          # 1ms precision
# }
```

**Fallback Mechanism** (if video timing service fails):
```python
# Direct calibration from session start time
video_start_time = session_data.get('video_start_time')
video_relative_seconds = labjack_trigger_time - video_start_time
fallback_video_relative = max(0.0, video_relative_seconds)

timing_data = {
    'video_relative_timestamp': fallback_video_relative,
    'actual_latency_ms': 50.0,  # Default estimate
    'video_frame_number': int(fallback_video_relative * 24),  # 24fps
    'timing_sync_quality': 'video_start_fallback'
}
```

#### Step 2.3: Create HILDetectionEvent Data Structure
```python
@dataclass
class HILDetectionEvent:
    id: str                              # UUID for detection
    session_id: str                      # Test session ID
    unix_timestamp: float                # Hardware trigger time
    video_relative_timestamp: float      # Video-relative time
    video_relative_timestamp_ns: str     # Nanosecond precision
    actual_latency_ms: float             # Processing latency
    video_frame_number: int              # Frame number
    timing_sync_quality: str             # Quality: 'synchronized', 'fallback', etc.
    labjack_voltage: float               # Voltage reading
    detection_channel: str               # Hardware channel (AIN0, etc.)
    precision_ns: float                  # Timing precision
    screenshot_path: Optional[str]       # Screenshot if captured
    screenshot_zoom_path: Optional[str]  # Zoomed screenshot
    ground_truth_comparison: Optional[Dict]  # Ground truth match results
    video_id: Optional[str]              # Associated video
    sequence_id: Optional[str]           # Video sequence ID
    sequence_video_result_id: Optional[str]  # Sequence result ID
    sequence_timestamp: Optional[float]  # Sequence timeline position
    video_play_offset_ms: Optional[float]  # Video playback offset
    detection_metadata: Dict[str, Any]   # Additional metadata
```

**Event Creation**:
```python
hil_event = HILDetectionEvent(
    id=str(uuid.uuid4()),
    session_id=session_id,
    unix_timestamp=detection_record_time,
    video_relative_timestamp=timing_data['video_relative_timestamp'],
    video_relative_timestamp_ns=timing_data['video_relative_timestamp_ns'],
    actual_latency_ms=calibrated_latency_ms,
    video_frame_number=timing_data['video_frame_number'],
    timing_sync_quality=timing_data['timing_sync_quality'],
    labjack_voltage=labjack_voltage,
    detection_channel=detection_channel,
    precision_ns=timing_data['timing_precision_ns'],
    created_at=datetime.now(timezone.utc),
    screenshot_path=None,  # Populated later
    screenshot_zoom_path=None,
    ground_truth_comparison=None
)
```

#### Step 2.4: Context Enrichment
```python
def _enrich_hil_event_context(hil_event, session_id, labjack_trigger_time):
    """
    Enriches detection with video sequence context:
    - video_id: Current video in sequence
    - sequence_id: Video sequence identifier
    - sequence_video_result_id: Result tracking ID
    - sequence_timestamp: Timeline position in sequence
    - video_play_offset_ms: Offset for multi-video sessions
    """
    # Loads sequence context from active session
    # Assigns detection to correct video in sequence
    # Handles video boundaries and transitions
```

---

### Phase 3: Database Storage (`_store_event_sync_wrapper` → `_store_detection_event_async`)

**Storage Path**: Thread-safe async database insertion

#### Step 3.1: Prepare Detection Event Model
```python
detection_event = DetectionEvent(
    # Primary identification
    id=hil_event.id,
    test_session_id=hil_event.session_id,
    video_id=video_id_for_detection,  # Enriched video ID

    # Timing data
    timestamp=labjack_trigger_time,               # Hardware trigger time
    labjack_timestamp=float(labjack_trigger_time),
    labjack_timestamp_ns=int(labjack_trigger_time * 1e9),
    unix_timestamp=float(detection_record_time),  # Processing time
    detection_timestamp=datetime.fromtimestamp(detection_record_time, tz=timezone.utc),

    # Video synchronization
    video_relative_timestamp=hil_event.video_relative_timestamp,
    video_frame_number=hil_event.video_frame_number,
    sequence_timestamp=hil_event.sequence_timestamp,
    video_play_offset_ms=hil_event.video_play_offset_ms,

    # Hardware data
    labjack_voltage=float(hil_event.labjack_voltage),
    detection_channel=str(hil_event.detection_channel),
    signal_value=float(hil_event.labjack_voltage),
    signal_type='labjack_voltage',

    # Latency and quality
    processing_time_ms=hil_event.actual_latency_ms,
    actual_latency_ms=hil_event.actual_latency_ms,
    timing_sync_quality=hil_event.timing_sync_quality,

    # Validation
    validation_result="PENDING",  # Will be updated by ground truth matching

    # HIL features
    screenshot_path=hil_event.screenshot_path,
    screenshot_zoom_path=hil_event.screenshot_zoom_path,

    # Classification
    detection_type="labjack_voltage",
    source="dedicated_labjack_monitor",

    # Sequence tracking
    sequence_id=hil_event.sequence_id,
    sequence_video_result_id=hil_event.sequence_video_result_id,

    # Metadata
    detection_metadata=detection_metadata
)
```

#### Step 3.2: Database Insertion
```python
db = next(get_db())
try:
    db.add(detection_event)
    db.commit()
    logger.debug(f"💾 Stored HIL detection event: {hil_event.id}")
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    db.rollback()
finally:
    db.close()
```

**Target Table**: `detection_events`

**Key Fields Stored**:
- **Identification**: `id`, `test_session_id`, `video_id`, `sequence_id`
- **Timing**: `timestamp`, `labjack_timestamp`, `labjack_timestamp_ns`, `video_relative_timestamp`, `unix_timestamp`
- **Hardware**: `labjack_voltage`, `detection_channel`, `signal_value`, `signal_type`
- **Latency**: `processing_time_ms`, `actual_latency_ms`, `timing_sync_quality`
- **Video Sync**: `video_frame_number`, `sequence_timestamp`, `video_play_offset_ms`
- **HIL**: `screenshot_path`, `screenshot_zoom_path`, `validation_result`
- **Metadata**: `detection_metadata`, `source`, `detection_type`, `detection_timestamp`

---

### Phase 4: WebSocket Emission (`_schedule_websocket_emission` → `_emit_detection_event_sync`)

**Purpose**: Real-time frontend updates for live monitoring

#### Step 4.1: Prepare WebSocket Payload
```python
detection_data = {
    'id': hil_event.id,
    'timestamp': hil_event.unix_timestamp,
    'timestamp_ms': hil_event.unix_timestamp * 1000,
    'video_relative_timestamp': hil_event.video_relative_timestamp,
    'sequence_timestamp': hil_event.sequence_timestamp,
    'latency_ms': hil_event.actual_latency_ms,
    'voltage': hil_event.labjack_voltage,
    'channel': hil_event.detection_channel,
    'frame_number': hil_event.video_frame_number,
    'timing_quality': hil_event.timing_sync_quality,
    'detection_type': 'labjack_voltage',
    'source': 'dedicated_labjack_monitor',
    'video_id': hil_event.video_id,
    'sequence_id': hil_event.sequence_id,
    'sequence_video_result_id': hil_event.sequence_video_result_id,
    'video_play_offset_ms': hil_event.video_play_offset_ms,
    'metadata': hil_event.detection_metadata
}
```

#### Step 4.2: Emit to Session Room
```python
from services.websocket_rooms import notify_session_room

success = notify_session_room(
    session_id=session_id,
    event='detection_event',
    data=detection_data
)
```

**WebSocket Room Mechanism**:
```python
def notify_session_room(session_id: str, event: str, data: Dict[str, Any]) -> bool:
    """
    Emits event ONLY to clients in session room (privacy + scalability)

    Room Name: f"session_{session_id}"
    Event: 'detection_event'

    Uses Socket.IO server with asyncio handling:
    - Checks for running event loop
    - Creates task if in async context
    - Creates new loop if needed
    """
    room_name = f"session_{session_id}"

    # Async emission to specific room
    await _sio.emit(event, data, room=room_name)

    return True
```

**Frontend Receives**:
```javascript
// Frontend Socket.IO listener
socket.on('detection_event', (data) => {
    console.log('New detection:', {
        id: data.id,
        voltage: data.voltage,
        latency: data.latency_ms,
        videoTime: data.video_relative_timestamp,
        frame: data.frame_number,
        quality: data.timing_quality
    });

    // Update UI with real-time detection
    updateDetectionDisplay(data);
});
```

---

## 3. Ground Truth Matching Integration

### HIL Screenshot Service Integration

**Service**: `services/hil_screenshot_service.py` → `HILGroundTruthComparison`

**Workflow** (asynchronous background processing):

```python
def _schedule_hil_processing(self, session_id: str, detection_data: Dict, video_path: str):
    """
    Schedules HIL screenshot capture and ground truth comparison
    Runs in background thread to avoid blocking detection pipeline
    """
    threading.Thread(
        target=self._process_hil_detection_background,
        args=(session_id, detection_data, video_path),
        daemon=True
    ).start()
```

**Processing Steps**:

1. **Screenshot Capture** (at detection video timestamp)
   - Full frame screenshot
   - Zoomed region around detection area

2. **Ground Truth Comparison**
   - Load ground truth annotations for video
   - Match detection timestamp to ground truth events
   - Calculate temporal accuracy
   - Validate detection against expected events

3. **Update Detection Event**
   ```python
   def _update_detection_with_hil_results(self, session_id, detection_id, hil_result):
       """Updates detection event with screenshot paths and ground truth results"""
       event.screenshot_path = hil_result['screenshot_capture']['screenshot_path']
       event.screenshot_zoom_path = hil_result['screenshot_capture']['screenshot_zoom_path']
       event.ground_truth_comparison = hil_result['ground_truth_comparison']
   ```

**Ground Truth Comparison Data Structure**:
```python
ground_truth_comparison = {
    'matched': True,
    'temporal_accuracy_ms': 23.4,  # Time difference from ground truth
    'expected_event': {
        'timestamp': 2.456,
        'event_type': 'vru_detection',
        'class': 'pedestrian'
    },
    'detection_result': {
        'voltage': 4.2,
        'latency_ms': 45.3,
        'video_relative_timestamp': 2.479
    },
    'validation': 'PASS'  # or 'FAIL'
}
```

---

## 4. Data Storage Schema

### Primary Table: `detection_events`

**Complete Schema**:
```sql
CREATE TABLE detection_events (
    -- Primary keys
    id VARCHAR(36) PRIMARY KEY,
    test_session_id VARCHAR(36) NOT NULL,
    video_id VARCHAR(36),

    -- Timing fields
    timestamp FLOAT NOT NULL,              -- Hardware trigger time
    labjack_timestamp FLOAT,               -- Unix timestamp from LabJack
    labjack_timestamp_ns BIGINT,           -- Nanosecond precision
    unix_timestamp FLOAT,                  -- Processing record time
    detection_timestamp TIMESTAMP WITH TIME ZONE,
    video_relative_timestamp FLOAT,        -- Seconds from video start

    -- Hardware data
    labjack_voltage FLOAT,                 -- Voltage reading
    detection_channel VARCHAR(20),         -- Hardware channel (AIN0, etc.)
    signal_value FLOAT,                    -- Same as voltage
    signal_type VARCHAR(50),               -- 'labjack_voltage'

    -- Video synchronization
    video_frame_number INTEGER,            -- Frame at detection
    sequence_timestamp FLOAT,              -- Sequence timeline position
    video_play_offset_ms FLOAT,            -- Multi-video offset

    -- Latency metrics
    processing_time_ms FLOAT,              -- Processing latency
    actual_latency_ms FLOAT,               -- Same as processing_time_ms
    timing_sync_quality VARCHAR(50),       -- Quality indicator

    -- HIL features
    screenshot_path VARCHAR(500),          -- Screenshot file path
    screenshot_zoom_path VARCHAR(500),     -- Zoomed screenshot path
    validation_result VARCHAR(20),         -- 'PASS', 'FAIL', 'PENDING'

    -- Sequence tracking
    sequence_id VARCHAR(36),               -- Video sequence ID
    sequence_video_result_id VARCHAR(36),  -- Result tracking

    -- Classification
    detection_type VARCHAR(50),            -- 'labjack_voltage'
    source VARCHAR(100),                   -- 'dedicated_labjack_monitor'

    -- Metadata
    detection_metadata JSONB,              -- Additional data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Foreign keys
    FOREIGN KEY (test_session_id) REFERENCES test_sessions(id),
    FOREIGN KEY (video_id) REFERENCES videos(id),
    FOREIGN KEY (sequence_id) REFERENCES video_sequences(id)
);

-- Critical indexes for performance
CREATE INDEX idx_detection_events_session ON detection_events(test_session_id);
CREATE INDEX idx_detection_events_video ON detection_events(video_id);
CREATE INDEX idx_detection_events_timestamp ON detection_events(timestamp);
CREATE INDEX idx_detection_events_video_relative ON detection_events(video_relative_timestamp);
CREATE INDEX idx_detection_events_sequence ON detection_events(sequence_id);
```

### Alternative Tables (Not Used by Dedicated Monitor)

**Note**: These are defined in `src/models/labjack_models.py` but NOT used by dedicated_labjack_monitor:

- `labjack_detections` - Independent LabJack hardware detection storage
- `video_detections` - Video playback detection events
- `detection_synchronizations` - Detection synchronization analysis
- `detection_configurations` - Detection window configuration
- `temporal_analysis_results` - Aggregated analysis results

**These tables are for a separate temporal synchronization analysis system**, not the primary HIL testing flow.

---

## 5. Complete System Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DETECTION FLOW LIFECYCLE                          │
└─────────────────────────────────────────────────────────────────────────┘

[1] INITIALIZATION
    │
    ├─► start_monitoring_with_video_sync(session_id, video_config)
    │   ├─► Validate session and video
    │   ├─► Create detection callback
    │   ├─► Start LabJack hardware monitoring (FIRST)
    │   └─► Initialize video timing service
    │
    v
[2] HARDWARE DETECTION
    │
    ├─► LabJack generates voltage event (e.g., AIN0 > 3.3V)
    │   └─► Callback: _handle_detection_with_video_sync(session_id, event)
    │
    v
[3] DATA EXTRACTION
    │
    ├─► Extract hardware data:
    │   ├─► labjack_trigger_time (Unix timestamp)
    │   ├─► labjack_voltage (voltage reading)
    │   ├─► detection_channel (hardware channel)
    │   └─► Calculate real_processing_latency_ms
    │
    v
[4] VIDEO TIMING SYNCHRONIZATION
    │
    ├─► video_timing_service.calculate_video_relative_latency()
    │   ├─► Convert Unix timestamp → video-relative timestamp
    │   ├─► Calculate frame number
    │   ├─► Determine timing sync quality
    │   └─► Apply calibration if needed
    │
    v
[5] CREATE HIL DETECTION EVENT
    │
    ├─► HILDetectionEvent(
    │       id, session_id, unix_timestamp,
    │       video_relative_timestamp, actual_latency_ms,
    │       labjack_voltage, detection_channel,
    │       video_frame_number, timing_sync_quality, ...
    │   )
    │
    v
[6] CONTEXT ENRICHMENT
    │
    ├─► _enrich_hil_event_context()
    │   ├─► Assign video_id (for sequences)
    │   ├─► Set sequence_id
    │   ├─► Set sequence_video_result_id
    │   └─► Calculate sequence_timestamp
    │
    v
[7] PARALLEL PROCESSING
    │
    ├─► [THREAD 1] Database Storage
    │   │   ├─► Create DetectionEvent model
    │   │   ├─► INSERT INTO detection_events (...)
    │   │   └─► db.commit()
    │   │
    │   └─► [THREAD 2] WebSocket Emission
    │       │   ├─► Prepare detection_data payload
    │       │   ├─► notify_session_room(session_id, 'detection_event', data)
    │       │   └─► Frontend receives real-time update
    │       │
    │       └─► [THREAD 3] HIL Processing (Background)
    │           ├─► Capture screenshots
    │           ├─► Load ground truth annotations
    │           ├─► Compare detection vs ground truth
    │           └─► Update detection with results
    │
    v
[8] FRONTEND DISPLAY
    │
    └─► Socket.IO: socket.on('detection_event', (data) => {
            updateDetectionDisplay(data);
        })
```

---

## 6. Key Design Patterns

### 1. Thread-Safe Async Processing
- Database operations use threading to avoid blocking
- WebSocket emissions use asyncio-safe threading
- HIL processing runs in background threads

### 2. Timing Precision
- High-precision Unix timestamps (nanosecond precision)
- Video-relative timestamp conversion
- Multi-level timing quality indicators

### 3. Graceful Degradation
- Fallback timing calculations if video service fails
- Default values for missing data
- Error recovery without detection loss

### 4. Context Preservation
- Session state management in `active_sessions` dict
- Video sequence context caching
- Detection metadata enrichment

### 5. Real-Time + Persistence
- Immediate database storage
- Real-time WebSocket updates
- Background HIL processing

---

## 7. Is This for HIL Testing?

**YES - This is the PRIMARY HIL testing system.**

**Evidence**:

1. **Name**: `DedicatedLabJackMonitor` - "dedicated" to HIL testing
2. **Video Synchronization**: Built-in video timing service integration
3. **HIL Features**:
   - Screenshot capture at detection time
   - Ground truth comparison service integration
   - Validation result tracking
4. **Sequence Support**: Full video sequence testing capabilities
5. **Precision**: Nanosecond-precision timing for hardware validation
6. **Real-Time Monitoring**: WebSocket updates for live test observation

**NOT for general detection** - This is specialized for:
- Hardware-in-the-loop validation
- Video sequence testing
- Ground truth matching
- Precise latency measurement
- Real-time test monitoring

---

## 8. Summary - Key Findings

### Detection Capture
- **Source**: LabJack hardware voltage events (threshold-based)
- **Trigger**: Voltage exceeds configured threshold (default 3.3V)
- **Channels**: Configurable hardware channels (default AIN0)

### Data Enrichment
- **Video Timing**: Unix timestamp → video-relative timestamp conversion
- **Context**: Video ID, sequence ID, sequence position
- **Metadata**: Hardware channel, voltage, latency, frame number
- **Quality**: Timing synchronization quality indicators

### Database Storage
- **Table**: `detection_events`
- **Fields**: 30+ fields including timing, hardware, video sync, HIL features
- **Insert**: SQLAlchemy ORM with explicit commit
- **Indexes**: Optimized for session, video, timestamp queries

### WebSocket Emission
- **Event**: `detection_event`
- **Target**: Session-specific room (`session_{session_id}`)
- **Data**: Complete detection payload with all enriched data
- **Timing**: Real-time emission in parallel with storage

### Ground Truth Matching
- **Process**: Background thread processing
- **Steps**: Screenshot capture → ground truth comparison → update detection
- **Integration**: `HILGroundTruthComparison` service
- **Result**: Updates detection validation_result and comparison data

### System Purpose
- **Primary**: HIL testing with video sequences
- **Features**: Hardware synchronization, ground truth validation, real-time monitoring
- **Use Case**: Validating ML model performance against hardware triggers with video context

---

## 9. Related Documentation

- **Video Timing**: `services/video_timing_service.py`
- **LabJack Hardware**: `services/labjack_service.py`
- **Ground Truth**: `services/hil_screenshot_service.py`
- **WebSocket**: `services/websocket_rooms.py`
- **Database Models**: `models.py` → `DetectionEvent`
- **Alternative System**: `src/models/labjack_models.py` (temporal analysis tables)

---

**Document Version**: 1.0
**Analysis Date**: 2025-01-17
**Analyzed File**: `services/dedicated_labjack_monitor.py` (2100+ lines)
**Status**: Complete and Validated
