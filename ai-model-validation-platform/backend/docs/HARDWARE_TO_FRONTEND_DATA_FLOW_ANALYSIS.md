# Hardware-to-Frontend Data Flow: Complete System Architecture Analysis

**Analysis Date**: 2025-10-29
**System**: AI Model Validation Platform - HIL Testing
**Focus**: LabJack Hardware → Frontend Display Data Pipeline

---

## Executive Summary

### Critical Finding
**Detection events ARE being created but are NOT reaching the frontend display** due to a multi-layered data flow architecture with disconnected integration points.

### Root Cause
The system has **THREE parallel detection pipelines** that are not properly integrated:
1. **Raw LabJack Logger** - High-frequency raw data capture
2. **Dedicated LabJack Monitor** - HIL-specific video sync detection
3. **LabJack Detection Service** - Event-based detection monitoring

**Problem**: Each service creates detection events independently, but only some emit WebSocket events, and database storage is fragmented.

---

## 1. Hardware → Backend: LabJack Trigger Detection

### 1.1 Hardware Layer
```
┌─────────────────────────────────────────────────────┐
│ LabJack T7/T4 Hardware                              │
│ - Analog Input Channels (AIN0, AIN1, etc.)        │
│ - Real-time voltage monitoring                     │
│ - Threshold: 3.3V (configurable)                   │
└─────────────────────────────────────────────────────┘
                    │
                    ▼
```

**Physical Detection**:
- LabJack hardware continuously monitors analog input channels
- When voltage crosses threshold (default 3.3V), detection trigger occurs
- Hardware provides microsecond-level timestamp precision

### 1.2 Service Layer - THREE PARALLEL SYSTEMS

#### System A: Raw LabJack Logger
**File**: `/backend/services/raw_labjack_logger.py`

```python
class RawLabJackLogger:
    async def start_session(self, session_name, test_session_id, channels, sample_rate=1000):
        """
        HIGH-FREQUENCY RAW DATA CAPTURE
        - Sample rate: 1000 Hz (configurable)
        - Captures ALL voltage readings (not just detections)
        - Applies compression (ZSTD/LZ4)
        - Stores in separate raw_labjack_sessions table
        """

        # Detection callback mechanism
        if voltage >= detection_threshold:
            for callback in self.detection_callbacks:
                callback({
                    'voltage': voltage,
                    'channel': channel,
                    'timestamp': timestamp,
                    'timestamp_ns': timestamp_ns
                })
```

**Storage Target**: `raw_labjack_sessions` table (NOT `detection_events`)
**WebSocket Emission**: ❌ **NO direct WebSocket emission**
**Database Integration**: ✅ Separate raw data storage

#### System B: Dedicated LabJack Monitor
**File**: `/backend/services/dedicated_labjack_monitor.py`

```python
class DedicatedLabJackMonitor:
    def start_monitoring_with_video_sync(self, test_session_id, video_config):
        """
        HIL VIDEO SYNCHRONIZATION MONITORING
        - Monitors for video timing alignment
        - Creates detection events WITH video sync data
        - Emits WebSocket events for real-time updates
        """

    def _handle_detection_with_video_sync(self, test_session_id, labjack_event):
        """
        CRITICAL: Creates DetectionEvent with video timing
        """
        detection_event = DetectionEvent(
            test_session_id=test_session_id,
            timestamp=labjack_timestamp,
            labjack_timestamp=labjack_timestamp,
            video_relative_timestamp=video_relative_timestamp,
            actual_latency_ms=calculated_latency,
            # ... other fields
        )

        # Store in database
        db.add(detection_event)
        db.commit()

        # ✅ EMITS WEBSOCKET EVENT
        self._emit_detection_websocket(test_session_id, detection_data)
```

**Storage Target**: `detection_events` table ✅
**WebSocket Emission**: ✅ **YES - emits to `detection_event` room**
**Database Integration**: ✅ Full DetectionEvent model

#### System C: LabJack Detection Service
**File**: `/backend/services/labjack_detection_service.py`

```python
class LabJackDetectionMonitor:
    def start_monitoring(self, session_id, channels, voltage_threshold=2.5,
                        debounce_ms=100, sample_rate=1000,
                        store_in_db=True, enable_websocket=True):
        """
        EVENT-BASED DETECTION MONITORING
        - Monitors channels for threshold crossings
        - Applies debounce logic
        - Stores in detection_events table
        - Can emit WebSocket events (if enabled)
        """

    def _record_detection_event(self, session_id, event):
        """
        STORES IN DATABASE via queue system
        """
        if config.store_in_db and DATABASE_AVAILABLE:
            self._schedule_db_storage(event)  # Queues for async storage

        # Notify callbacks
        self._notify_detection_callbacks(event)

        # Send WebSocket notification
        if config.enable_websocket:
            self._notify_websocket_callbacks(session_id, event)

    async def _store_event_in_db(self, event):
        """
        CRITICAL DATABASE STORAGE
        """
        db_event = DBDetectionEvent(
            id=event.id,
            test_session_id=event.session_id,
            video_id=video_id,  # ✅ Validates video exists
            timestamp=event.timestamp,
            detection_channel=event.channel,
            labjack_voltage=event.voltage,
            # ... timing calibration fields
        )
        db.add(db_event)
        db.commit()
```

**Storage Target**: `detection_events` table ✅
**WebSocket Emission**: ⚠️ **Conditional - only if `enable_websocket=True`**
**Database Integration**: ✅ Full DetectionEvent model with validation

### 1.3 Integration Service - The Bridge
**File**: `/backend/services/raw_labjack_integration.py`

```python
class RawLabJackIntegrationService:
    async def start_integrated_session(self, session_name, test_session_id,
                                       channels, video_config):
        """
        COORDINATES ALL THREE SYSTEMS
        1. Starts raw logging (System A)
        2. Starts HIL monitoring (System B)
        3. Starts detection monitoring (System C)
        4. Sets up callbacks to bridge systems
        """

        # Start raw logging
        raw_session_id = await self.raw_logger.start_session(...)

        # Start HIL monitoring
        hil_success = self.dedicated_monitor.start_monitoring_with_video_sync(
            test_session_id, video_timing_config
        )

        # Start detection monitoring
        detection_success = self.detection_service.start_monitoring(
            test_session_id,
            channels=channels,
            store_in_db=True,
            enable_websocket=True  # ✅ CRITICAL: Must be True
        )

        # Setup detection callbacks
        await self._setup_detection_callbacks(raw_session_id, test_session_id)

    async def _setup_detection_callbacks(self, raw_session_id, test_session_id):
        """
        BRIDGE BETWEEN RAW LOGGER AND OTHER SYSTEMS
        """
        def detection_callback(detection_data):
            # Convert raw detection to LabJack event format
            mock_event = MockLabJackEvent(voltage, channel, timestamp)

            # Forward to HIL monitor
            if session_mapping.hil_session_active:
                self.dedicated_monitor._handle_detection_with_video_sync(
                    test_session_id, mock_event
                )

            # Create detection event for database
            if session_mapping.detection_session_active:
                self._create_detection_event(test_session_id, detection_data, raw_session_id)

        # Add callback to raw logger
        self.raw_logger.add_detection_callback(detection_callback)
```

**Key Role**: Bridges raw data capture with detection event creation and WebSocket emission

---

## 2. Backend Processing: Detection Event Creation

### 2.1 Database Model - DetectionEvent
**File**: `/backend/models.py`

```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    # Primary Keys and Relationships
    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id"))
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=True)

    # Timing Fields
    timestamp = Column(Float, nullable=False, index=True)
    labjack_timestamp = Column(Float, nullable=True, index=True)
    labjack_timestamp_ns = Column(String, nullable=True)

    # Video Synchronization
    video_start_time = Column(Float, nullable=True, index=True)
    video_start_time_ns = Column(String, nullable=True)

    # Latency Calculation
    actual_latency_ms = Column(Float, nullable=True)
    latency_ns = Column(String, nullable=True)
    latency_threshold_ms = Column(Float, nullable=True)
    latency_result = Column(String, nullable=True, index=True)

    # Hardware Data
    labjack_voltage = Column(Float, nullable=True)
    voltage_level = Column(Float, nullable=True)
    detection_channel = Column(String, nullable=True)

    # Validation
    validation_result = Column(String, index=True)
    ground_truth_match_id = Column(String(36), ForeignKey("ground_truth_objects.id"))
```

**Critical Fields**:
- `test_session_id`: Links to active test session ✅
- `video_id`: Links to video being tested ⚠️ (must exist in videos table)
- `labjack_timestamp`: Hardware detection time ✅
- `video_start_time`: Video playback start reference ⚠️ (must be set by frontend)
- `actual_latency_ms`: Calculated latency ⚠️ (requires both timestamps)

### 2.2 Data Validation Flow

```
Detection Trigger
      │
      ▼
┌─────────────────────────────────────┐
│ 1. Session Validation               │
│    - Test session must exist        │
│    - Status must be "running"       │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 2. Video Validation                 │
│    - Video ID must exist            │
│    - Video must be linked to session│
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 3. Timing Data Validation           │
│    - video_start_time must be set   │ ⚠️ POTENTIAL FAILURE POINT
│    - LabJack timestamp must be valid│
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 4. Create DetectionEvent            │
│    - Calculate latency              │
│    - Store in database              │
└─────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────┐
│ 5. Emit WebSocket Event             │ ⚠️ DEPENDS ON SERVICE CONFIG
│    - Room: test_session_{id}        │
│    - Event: 'detection_event'       │
└─────────────────────────────────────┘
```

**Failure Points**:
1. ❌ Video ID not set or invalid → Event NOT created
2. ❌ `video_start_time` not set → Latency calculation fails → Event may be created but incomplete
3. ❌ `enable_websocket=False` → Event created in DB but NO WebSocket emission
4. ❌ Wrong WebSocket room → Frontend not subscribed → Event lost

---

## 3. Backend → Frontend: WebSocket Communication

### 3.1 WebSocket Server Configuration
**File**: `/backend/socketio_server.py`

```python
# Socket.IO Server Setup
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=[...],
    ping_timeout=60,
    ping_interval=25,
    transports=['websocket', 'polling']
)

# Room Structure
ROOMS = {
    'general': 'All connected clients',
    'detections': 'All detection event subscribers',
    'test_session_{session_id}': 'Session-specific updates',
    'hardware_signals_{session_id}': 'Hardware signal updates',
    'sequence_{sequence_id}': 'Video sequence updates'
}
```

### 3.2 Event Emission Patterns

#### Pattern A: Detection Event Emission (Dedicated Monitor)
```python
# From dedicated_labjack_monitor.py
def _emit_detection_websocket(self, test_session_id, detection_data):
    """
    Emits detection event to WebSocket clients
    """
    message = {
        'type': 'detection_event',
        'session_id': test_session_id,
        'event': {
            'id': detection_data['id'],
            'timestamp': detection_data['timestamp'],
            'labjack_timestamp': detection_data['labjack_timestamp'],
            'video_relative_timestamp': detection_data['video_relative_timestamp'],
            'actual_latency_ms': detection_data['actual_latency_ms'],
            'voltage': detection_data['voltage'],
            'channel': detection_data['channel']
        }
    }

    # Emit to session room
    room = f"test_session_{test_session_id}"
    await sio.emit('detection_event', message, room=room)

    # Also emit to general detections room
    await sio.emit('detection_event', message, room='detections')
```

#### Pattern B: Detection Event Emission (Detection Service)
```python
# From labjack_detection_service.py
def _notify_websocket_callbacks(self, session_id, event):
    """
    Send WebSocket notification via callbacks
    """
    message = {
        'type': 'detection_event',
        'session_id': session_id,
        'event': event.to_dict()
    }

    for callback in self.websocket_callbacks:
        try:
            callback(session_id, message)
        except Exception as e:
            logger.error(f"Error in WebSocket callback: {e}")
```

**Critical Difference**:
- Dedicated Monitor: Direct `sio.emit()` call ✅
- Detection Service: Callback-based ⚠️ (callbacks must be registered)

### 3.3 WebSocket Callback Registration

**File**: `/backend/main.py` (or initialization code)

```python
# REQUIRED: Register WebSocket callbacks for detection service
from services.labjack_detection_service import setup_websocket_integration

# Setup WebSocket integration
setup_websocket_integration(websocket_manager)

# This registers the callback:
async def websocket_callback(session_id: str, message: Dict[str, Any]):
    """Send detection event via WebSocket"""
    if websocket_manager:
        await websocket_manager.broadcast_to_session(session_id, message)

monitor.add_websocket_callback(websocket_callback)
```

**⚠️ CRITICAL**: If this registration is missing, detection events are created in database but NEVER emitted via WebSocket!

---

## 4. Frontend Display: Reception and Rendering

### 4.1 Frontend WebSocket Connection
**Expected Location**: `/frontend/src/services/websocketService.ts`

```typescript
// WebSocket connection setup
class WebSocketService {
  private socket: Socket;

  connect() {
    this.socket = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: 5
    });

    // Connection events
    this.socket.on('connect', () => {
      console.log('WebSocket connected');
    });

    // Subscribe to test session
    this.subscribeToSession(sessionId);
  }

  subscribeToSession(sessionId: string) {
    // Join session room
    this.socket.emit('subscribe_to_updates', {
      type: 'session',
      target_id: sessionId
    });

    // Listen for detection events
    this.socket.on('detection_event', (data) => {
      this.handleDetectionEvent(data);
    });
  }

  handleDetectionEvent(data: any) {
    // Update UI with detection event
    const event = data.event;
    console.log('Detection received:', event);

    // Update state/store
    store.dispatch(addDetectionEvent(event));
  }
}
```

### 4.2 Frontend Results Display
**Expected Location**: `/frontend/src/pages/HILResults.tsx`

```typescript
const HILResults = () => {
  const [detectionEvents, setDetectionEvents] = useState([]);
  const { sessionId } = useParams();

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocketService();
    ws.connect();
    ws.subscribeToSession(sessionId);

    // Listen for events
    ws.on('detection_event', (event) => {
      setDetectionEvents(prev => [...prev, event]);
    });

    // Fetch existing events
    fetchDetectionEvents(sessionId);

    return () => ws.disconnect();
  }, [sessionId]);

  return (
    <div>
      <h1>HIL Test Results</h1>
      <DetectionEventList events={detectionEvents} />
      <LatencyGraph events={detectionEvents} />
    </div>
  );
};
```

---

## 5. Data Structures at Each Step

### Step 1: Hardware Detection
```python
{
    'channel': 'AIN0',
    'voltage': 3.45,  # Volts
    'timestamp': 1698765432.123456,  # Unix timestamp (float)
    'timestamp_ns': '1698765432123456789'  # Nanosecond precision (string)
}
```

### Step 2: Detection Event Creation (Database)
```python
DetectionEvent(
    id='550e8400-e29b-41d4-a716-446655440000',
    test_session_id='abc-123-def-456',
    video_id='video-789',
    timestamp=1698765432.123456,
    labjack_timestamp=1698765432.123456,
    labjack_timestamp_ns='1698765432123456789',
    video_start_time=1698765430.0,  # Set by frontend when video starts
    video_relative_timestamp=2.123456,  # labjack_timestamp - video_start_time
    actual_latency_ms=166.0,  # Calculated from pipeline timing
    labjack_voltage=3.45,
    voltage_level=3.45,
    detection_channel='AIN0',
    latency_result='pass',  # 'pass' if < latency_threshold_ms
    validation_result='PENDING',
    created_at=datetime.now()
)
```

### Step 3: WebSocket Emission
```json
{
  "type": "detection_event",
  "session_id": "abc-123-def-456",
  "event": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": 1698765432.123456,
    "labjack_timestamp": 1698765432.123456,
    "video_relative_timestamp": 2.123456,
    "actual_latency_ms": 166.0,
    "voltage": 3.45,
    "channel": "AIN0",
    "latency_result": "pass",
    "validation_result": "PENDING"
  }
}
```

### Step 4: Frontend Reception
```typescript
interface DetectionEvent {
  id: string;
  timestamp: number;
  labjack_timestamp: number;
  video_relative_timestamp: number;
  actual_latency_ms: number;
  voltage: number;
  channel: string;
  latency_result: 'pass' | 'fail';
  validation_result: string;
}
```

---

## 6. Current Failure Points - WHERE ARE EVENTS LOST?

### Issue #1: WebSocket Callback Registration Missing
**Location**: Backend initialization
**Symptom**: Events created in database but NOT emitted
**Root Cause**: `setup_websocket_integration()` not called in `main.py`

```python
# MISSING IN main.py:
from services.labjack_detection_service import setup_websocket_integration
setup_websocket_integration(websocket_manager)
```

### Issue #2: Conditional WebSocket Emission
**Location**: `labjack_detection_service.py`
**Symptom**: Events only emitted if `enable_websocket=True`
**Root Cause**: Configuration not consistently set

```python
# Detection service start_monitoring() call MUST include:
self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    enable_websocket=True,  # ⚠️ CRITICAL
    store_in_db=True
)
```

### Issue #3: Video Start Time Not Set
**Location**: Frontend → Backend timing sync
**Symptom**: Latency calculation fails or incomplete
**Root Cause**: Frontend doesn't send `video_start_time` to backend

**Required Flow**:
```typescript
// Frontend MUST send when video starts:
socket.emit('video_started', {
  sessionId: sessionId,
  videoStartTime: performance.now(),  // High precision timestamp
  setupDelay: setupDuration
});

// Backend MUST update test session:
test_session.video_start_timestamp = video_start_time
db.commit()
```

### Issue #4: Frontend Not Subscribed to Correct Room
**Location**: Frontend WebSocket service
**Symptom**: Backend emits but frontend doesn't receive
**Root Cause**: Frontend subscribed to wrong room or not subscribed at all

**Required Subscription**:
```typescript
// Frontend MUST subscribe to session room:
socket.emit('subscribe_to_updates', {
  type: 'session',
  target_id: sessionId  // Must match test_session_id
});

// Backend emits to: test_session_{sessionId}
```

### Issue #5: Multiple Service Confusion
**Location**: Integration layer
**Symptom**: Duplicate or missing events
**Root Cause**: Three services creating events independently

**Solution**: Use integration service consistently:
```python
# Use RawLabJackIntegrationService for all HIL tests
integration_service = get_raw_labjack_integration()
await integration_service.start_integrated_session(
    session_name=session_name,
    test_session_id=test_session_id,
    channels=channels,
    video_config=video_config  # Enables HIL monitoring
)
```

### Issue #6: Database-Only Storage
**Location**: Some code paths
**Symptom**: Events in database but never emitted in real-time
**Root Cause**: WebSocket emission happens BEFORE database commit

**Correct Order**:
```python
# 1. Create event object
event = DetectionEvent(...)

# 2. Store in database
db.add(event)
db.commit()

# 3. Emit WebSocket (after successful storage)
if config.enable_websocket:
    self._emit_websocket(event)
```

---

## 7. Expected vs Actual Behavior

### Expected Behavior ✅
```
LabJack Trigger (3.3V)
    → Detection Service creates DetectionEvent
    → Event stored in detection_events table
    → WebSocket emitted to test_session_{id} room
    → Frontend receives event via socket.on('detection_event')
    → UI updates with detection data
    → Latency calculated and displayed
```

### Actual Behavior ❌
```
LabJack Trigger (3.3V)
    → Multiple services may detect (Raw Logger, Dedicated Monitor, Detection Service)
    → Events MAY be created (depends on which service is active)
    → Database storage MAY happen (depends on config)
    → WebSocket emission MAY happen (depends on callbacks registered)
    → Frontend MAY be subscribed (depends on room subscription)
    → UI MAY update (depends on all above working)
```

**Result**: Intermittent or complete failure to display detection events

---

## 8. Complete Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        HARDWARE LAYER                                 │
│  LabJack T7/T4: Voltage Monitoring (AIN0-AIN3)                       │
│  Threshold: 3.3V | Timestamp: Microsecond precision                  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  BACKEND SERVICE LAYER (3 SYSTEMS)                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌──────────────┐│
│  │ Raw LabJack Logger  │  │ Dedicated Monitor   │  │ Detection    ││
│  │ (System A)          │  │ (System B)          │  │ Service      ││
│  │                     │  │                     │  │ (System C)   ││
│  │ - 1000Hz sampling   │  │ - Video sync        │  │ - Event-based││
│  │ - Raw data capture  │  │ - HIL timing        │  │ - Threshold  ││
│  │ - Compression       │  │ - Latency calc      │  │ - Debounce   ││
│  │ - Callbacks         │  │ - WebSocket emit ✅  │  │ - Callbacks⚠️││
│  │ - NO WebSocket ❌   │  │ - DB storage ✅      │  │ - DB storage✅││
│  └─────────────────────┘  └─────────────────────┘  └──────────────┘│
│                              │                         │             │
│                              ▼                         ▼             │
│                    ┌──────────────────────────────────────┐          │
│                    │ Integration Service (Bridge)         │          │
│                    │ - Coordinates all 3 systems          │          │
│                    │ - Manages callbacks                  │          │
│                    │ - Ensures WebSocket emission         │          │
│                    └──────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                                  │
│  ┌──────────────────────┐                                            │
│  │ detection_events     │  ← PRIMARY STORAGE                         │
│  │ - test_session_id    │                                            │
│  │ - video_id           │  ⚠️ Must exist in videos table             │
│  │ - labjack_timestamp  │                                            │
│  │ - video_start_time   │  ⚠️ Must be set by frontend                │
│  │ - actual_latency_ms  │  ← Calculated                              │
│  │ - validation_result  │                                            │
│  └──────────────────────┘                                            │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    WEBSOCKET LAYER                                    │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │ Socket.IO Server                                         │        │
│  │ - Rooms: test_session_{id}, detections, general        │        │
│  │ - Events: 'detection_event', 'hil_update'               │        │
│  │ - Transport: WebSocket + Polling fallback               │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                       │
│  ⚠️ CRITICAL REQUIREMENTS:                                           │
│  1. WebSocket callbacks must be registered in main.py               │
│  2. Frontend must subscribe to correct room                         │
│  3. enable_websocket must be True in service config                 │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      NETWORK LAYER                                    │
│  HTTP/WebSocket Connection                                           │
│  Backend: ws://localhost:8000 or wss://production-url                │
│  Frontend: Socket.IO client connection                               │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                                     │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │ WebSocket Service (websocketService.ts)                 │        │
│  │ - Connection management                                  │        │
│  │ - Room subscription: subscribe_to_updates()             │        │
│  │ - Event handlers: on('detection_event')                 │        │
│  │ - Reconnection logic                                    │        │
│  └──────────────────────────────────────────────────────────┘        │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │ State Management (Redux/Context)                        │        │
│  │ - Detection events array                                │        │
│  │ - Real-time updates                                     │        │
│  │ - Historical data                                       │        │
│  └──────────────────────────────────────────────────────────┘        │
│                              │                                        │
│                              ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │ UI Components (HILResults.tsx)                          │        │
│  │ - Detection event list                                  │        │
│  │ - Latency graphs                                        │        │
│  │ - Real-time indicators                                  │        │
│  │ - Video timeline synchronization                        │        │
│  └──────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. Critical Timing Synchronization Points

### Point 1: Video Playback Start
**Frontend → Backend**
```typescript
// When video starts playing:
socket.emit('video_started', {
  sessionId: testSessionId,
  videoStartTime: performance.now(),  // High precision
  setupDelay: videoSetupDuration
});
```

**Backend Processing**:
```python
@sio.event
async def video_started(sid, data):
    session_id = data.get('sessionId')
    video_start_time = data.get('videoStartTime')

    # Update test session with video timing
    db = SessionLocal()
    session = db.query(TestSession).filter_by(id=session_id).first()
    session.video_start_timestamp = video_start_time
    session.video_timing_sync_status = 'synced'
    db.commit()
```

### Point 2: LabJack Detection Timestamp
**Hardware → Service**
```python
# When LabJack detects voltage crossing:
detection_timestamp = time.time()  # Unix timestamp
detection_timestamp_ns = time.time_ns()  # Nanosecond precision
```

### Point 3: Latency Calculation
**Service Logic**
```python
# Calculate video-relative timestamp:
video_relative_timestamp = labjack_timestamp - video_start_timestamp

# Apply calibration offset (empirically determined):
TIMING_CALIBRATION_OFFSET_MS = 166.0
calibrated_timestamp = video_relative_timestamp + (TIMING_CALIBRATION_OFFSET_MS / 1000.0)

# Latency is pipeline processing time (not timestamp difference):
actual_latency_ms = t3_processing_time_ms  # From YOLO detection pipeline
```

---

## 10. Recommendations to Fix Data Flow

### Immediate Fixes (High Priority)

1. **Register WebSocket Callbacks in main.py**
```python
# In backend/main.py after app initialization:
from services.labjack_detection_service import setup_websocket_integration

@app.on_event("startup")
async def startup_event():
    # Setup WebSocket integration for detection events
    setup_websocket_integration(sio)
    logger.info("✅ WebSocket detection callbacks registered")
```

2. **Ensure Integration Service is Used**
```python
# All HIL test endpoints should use:
integration_service = get_raw_labjack_integration()
session_ids = await integration_service.start_integrated_session(
    session_name=session_name,
    test_session_id=test_session_id,
    channels=['AIN0', 'AIN1'],
    video_config={
        'enable_websocket': True,  # ✅ CRITICAL
        'voltage_threshold': 3.3,
        'debounce_ms': 50
    }
)
```

3. **Frontend Video Timing Sync**
```typescript
// When video starts, IMMEDIATELY send timing event:
const videoElement = videoRef.current;
const videoStartTime = performance.now();

socket.emit('video_started', {
  sessionId: testSessionId,
  videoStartTime: videoStartTime,
  videoTimestamp: videoElement.currentTime
});
```

4. **Frontend Room Subscription**
```typescript
// Subscribe to BOTH session-specific and general rooms:
useEffect(() => {
  // Subscribe to session room
  socket.emit('subscribe_to_updates', {
    type: 'session',
    target_id: testSessionId
  });

  // Also subscribe to detections room for monitoring
  socket.emit('subscribe_to_updates', {
    type: 'detections'
  });

  // Listen for detection events
  socket.on('detection_event', handleDetectionEvent);

  return () => {
    socket.off('detection_event', handleDetectionEvent);
  };
}, [testSessionId]);
```

### Long-term Fixes (Architectural)

1. **Unify Detection Services**
   - Single detection service with configurable modes
   - Eliminate duplicate event creation
   - Guaranteed WebSocket emission

2. **Add Monitoring Dashboard**
   - Real-time service health checks
   - WebSocket connection status
   - Event flow visualization
   - Database write confirmation

3. **Implement Event Acknowledgment**
   - Frontend sends ACK when receiving event
   - Backend retries if no ACK received
   - Prevents silent failures

4. **Enhanced Logging**
   - Log every step of data flow
   - Timestamp each stage
   - Identify bottlenecks and failures

---

## 11. Testing Checklist

### Backend Testing
- [ ] LabJack hardware detection triggers successfully
- [ ] Detection events created in database
- [ ] `test_session_id` and `video_id` valid for all events
- [ ] `video_start_timestamp` set in test_sessions table
- [ ] WebSocket callbacks registered in main.py
- [ ] WebSocket events emitted to correct room
- [ ] Latency calculated correctly

### Frontend Testing
- [ ] WebSocket connection established
- [ ] Subscribed to `test_session_{id}` room
- [ ] Listening for `detection_event` events
- [ ] Video start time sent to backend
- [ ] Detection events received in real-time
- [ ] UI updates with detection data
- [ ] Latency displayed correctly

### Integration Testing
- [ ] End-to-end flow: LabJack → Frontend
- [ ] Multiple detections handled
- [ ] Reconnection after disconnect
- [ ] Database persistence verified
- [ ] Real-time and historical data consistent

---

## Conclusion

The detection events ARE being created and stored in the database, but the **WebSocket emission layer** is the primary failure point. The system has three parallel detection services that need proper coordination through the integration service, and WebSocket callbacks must be registered at application startup.

**Key Missing Piece**: `setup_websocket_integration()` not called in `main.py`, causing detection events to be stored but never emitted to the frontend.

**Secondary Issues**:
- Frontend video timing sync not implemented
- Multiple services creating duplicate events
- Room subscription inconsistencies
- Conditional WebSocket emission

Fixing these issues will restore the complete data flow from hardware trigger to frontend display.
