# Detection Event Flow Analysis: Hardware to UI

## Executive Summary

This document traces the complete detection event flow from hardware (LabJack) to frontend UI, identifying where the chain breaks and causes the disconnect between stored database events and UI display.

**CRITICAL FINDINGS:**
1. ✅ Detection events ARE being created correctly
2. ✅ Detection events ARE being stored in database
3. ❌ **BREAK IN CHAIN**: WebSocket emission logic exists but may not be called properly
4. ❌ Frontend detection service is NOT subscribed to LabJack detection events
5. ❌ Frontend only listens to YOLO ground truth API, not LabJack hardware events

---

## 1. Detection Event Creation Flow

### 1.1 Hardware Detection (LabJack)

**File**: `backend/services/labjack_detection_service.py`

```python
# Entry Point: Detection monitoring loop
def _monitoring_loop(self, session_id: str):
    """Main monitoring loop for a session"""
    # Line 409-484

    # Step 1: Read voltage from hardware
    voltage = self.connection_manager.read_voltage(channel)  # Line 437

    # Step 2: Check threshold
    if voltage >= config.voltage_threshold:  # Line 459
        logger.info(f"🎯 DETECTION! {channel}: {voltage:.3f}V")

        # Step 3: Create detection event
        if self._should_record_detection(session_id, channel, current_time, config):
            event = self._create_detection_event(
                session_id, channel, voltage, threshold, current_time
            )  # Line 462-464

            # Step 4: Record and persist
            self._record_detection_event(session_id, event)  # Line 465
```

**Detection Event Structure** (Lines 84-113):
```python
@dataclass
class DetectionEvent:
    id: str
    session_id: str
    timestamp: datetime
    channel: str
    voltage: float
    threshold: float
    detected: bool = True
    video_relative_timestamp: Optional[float] = None
    actual_latency_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
```

---

## 2. Database Storage Flow

### 2.1 Direct Storage Path

**File**: `backend/services/labjack_detection_service.py`

```python
def _record_detection_event(self, session_id: str, event: DetectionEvent):
    """Record detection event and notify callbacks"""  # Line 556

    # Step 1: Store in memory
    self.detection_events[session_id].append(event)  # Line 563

    # Step 2: Queue for database storage
    if config.store_in_db and DATABASE_AVAILABLE:
        self._schedule_db_storage(event)  # Line 575

    # Step 3: Notify callbacks
    self._notify_detection_callbacks(event)  # Line 578

    # Step 4: WebSocket notification
    if config.enable_websocket:
        self._notify_websocket_callbacks(session_id, event)  # Line 582
```

### 2.2 Database Storage Implementation

**File**: `backend/services/labjack_detection_service.py`

```python
async def _store_event_in_db(self, event: DetectionEvent):
    """Store detection event in database"""  # Line 618-689

    # Validates session exists (Line 630-637)
    session = db.query(TestSession).filter(
        TestSession.id == event.session_id
    ).first()

    # Creates database record with full timing data (Lines 650-672)
    db_event = DBDetectionEvent(
        id=event.id,
        test_session_id=session.id,
        video_id=video_id,
        timestamp=event.timestamp.timestamp(),
        detection_channel=event.channel,
        labjack_voltage=event.voltage,
        voltage_level=event.voltage,
        latency_threshold_ms=event.threshold,
        video_relative_timestamp=event.video_relative_timestamp,
        actual_latency_ms=event.actual_latency_ms,
        detection_metadata={...}  # Includes timing calibration
    )

    db.add(db_event)
    db.commit()
    logger.info(f"✅ PRODUCTION: Stored detection event with timing calibration: {event.id}")
```

**Storage Quality**: ✅ EXCELLENT
- Session validation
- Complete timing data
- Metadata preservation
- Error handling with rollback

---

## 3. WebSocket Emission Flow

### 3.1 WebSocket Notification Path

**File**: `backend/services/labjack_detection_service.py`

```python
def _notify_websocket_callbacks(self, session_id: str, event: DetectionEvent):
    """Send WebSocket notification"""  # Line 764-776

    message = {
        'type': 'detection_event',
        'session_id': session_id,
        'event': event.to_dict()
    }

    for callback in self.websocket_callbacks:
        try:
            callback(session_id, message)  # Line 774
        except Exception as e:
            logger.error(f"Error in WebSocket callback: {e}")
```

**❓ POTENTIAL BREAK #1**:
- WebSocket callbacks must be registered via `add_websocket_callback()`
- No evidence of callback registration in startup code
- Callbacks may be empty list → no emission

### 3.2 Socket.IO Server

**File**: `backend/socketio_server.py`

The server has event emission utilities but they're NOT called from detection service:

```python
async def emit_detection_event(detection_data: dict, test_session_id: str):
    """Emit real-time detection event to all connected clients"""  # Line 324
    room = f"test_session_{test_session_id}"
    await sio.emit('detection_event', detection_data, room=room)
    await sio.emit('detection_event', detection_data, room='detections')
```

**❌ BREAK IN CHAIN #1**:
- `emit_detection_event()` function exists but is NEVER imported or called by labjack_detection_service
- WebSocket emission logic is disconnected from detection event creation
- No bridge between hardware detection and Socket.IO emission

### 3.3 Alternative Emission via Dedicated Monitor

**File**: `backend/services/dedicated_labjack_monitor.py`

```python
def _schedule_websocket_emission(self, hil_event: HILDetectionEvent, session_id: str):
    """Emit detection event via WebSocket"""  # Line 547-558
    threading.Thread(
        target=self._emit_detection_event_sync,
        args=(hil_event, session_id),
        daemon=True
    ).start()

def _emit_detection_event_sync(self, hil_event: HILDetectionEvent, session_id: str):
    """Thread-safe wrapper for async WebSocket emission"""  # Line 560-598

    detection_data = {
        'id': hil_event.id,
        'session_id': hil_event.session_id,
        'timestamp': hil_event.unix_timestamp,
        'video_relative_timestamp': hil_event.video_relative_timestamp,
        'latency_ms': hil_event.actual_latency_ms,
        'voltage': hil_event.labjack_voltage,
        'channel': hil_event.detection_channel,
        # ... more fields
    }

    from socketio_server import emit_detection_event
    loop.run_until_complete(emit_detection_event(detection_data, session_id))
```

**✅ This path WORKS**: Dedicated monitor properly emits WebSocket events
**❌ BUT**: Only used when `dedicated_labjack_monitor` is active, not basic detection service

---

## 4. Session Completion Flow

**File**: `backend/services/session_completion_service.py`

```python
async def complete_session(self, session_id: str, force: bool = False):
    """Complete a session and generate results"""  # Line 62-155

    # Step 1: Check detection count (Lines 101-106)
    detection_count = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).count()

    if detection_count == 0:
        logger.warning(f"⚠️ No detection events found for session {session_id}")
        # ⚠️ Does NOT create mock events (removed in fix)

    # Step 2: Mark session completed
    session.status = "completed"
    session.completed_at = datetime.now(timezone.utc)
    db.commit()

    # Step 3: Generate results
    result_data = test_execution_service.get_session_results(session_id)
```

**Analysis**: ✅ CORRECT
- No longer creates fake mock events
- Properly warns about missing detections
- Completion happens regardless of detection count

---

## 5. Frontend State Update Flow

### 5.1 WebSocket Service

**File**: `frontend/src/services/websocketService.ts`

```typescript
class WebSocketService {
    connect(): Promise<boolean> {
        // Lines 147-320

        // Connection setup
        this.socket = io(this.url, {
            transports: ['websocket', 'polling'],
            timeout: 20000,
            reconnection: true,
            // ...
        });

        // Handle all incoming messages
        this.socket.onAny((eventName: string, data: unknown) => {
            // Line 298-312
            console.log(`📨 WebSocket message [${eventName}]:`, data);

            this.notifySubscribers(eventName, data);
            this.notifySubscribers('*', message); // Wildcard
        });
    }

    subscribe(eventType: string, callback: (data: T) => void) {
        // Line 408-439
        this.subscribers.get(eventType)!.add(callback);

        if (this.socket && this.connectionState === 'connected') {
            this.socket.on(eventType, callback);
        }
    }
}
```

**WebSocket Service Quality**: ✅ EXCELLENT
- Proper event handling
- Wildcard subscriptions
- Reconnection logic
- Type-safe callbacks

### 5.2 Detection Service (Frontend)

**File**: `frontend/src/services/detectionService.ts`

```typescript
class DetectionService {
    async runDetection(videoId: string, config: DetectionConfig): Promise<DetectionResult> {
        // Lines 29-95

        // Only runs YOLO detection via HTTP API
        const result = await this.runBackendDetection(videoId, config);
    }

    private async runBackendDetection(videoId: string, config: DetectionConfig) {
        // Lines 97-353

        // Step 1: Check existing ground truth
        let response = await apiService.getGroundTruth(videoId);

        // Step 2: Trigger YOLO processing if needed
        if (!hasObjects) {
            await apiService.cachedRequest('POST', `/api/videos/${videoId}/process-ground-truth`);
            // Poll for results...
        }

        // Step 3: Convert to annotations
        const annotations = this.convertDetectionsToAnnotations(videoId, validDetections);

        return { success: true, detections: annotations, source: 'backend' };
    }

    // WebSocket functionality REMOVED
    connectWebSocket(videoId: string, onUpdate: (data: DetectionUpdate) => void): void {
        console.log('ℹ️ WebSocket functionality disabled - using HTTP-only detection workflow');
        // No WebSocket connections will be established
    }
}
```

**❌ BREAK IN CHAIN #2**:
- Frontend detection service is HTTP-only
- Does NOT subscribe to real-time LabJack detection events
- Only fetches YOLO ground truth via REST API
- WebSocket functionality explicitly disabled

---

## 6. Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          HARDWARE LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  LabJack Hardware                                                        │
│       │                                                                   │
│       │ Voltage Reading                                                  │
│       ▼                                                                   │
│  labjack_detection_service.py                                           │
│       │                                                                   │
│       ├─► _monitoring_loop()          ✅ WORKS                          │
│       ├─► _create_detection_event()   ✅ WORKS                          │
│       └─► _record_detection_event()   ✅ WORKS                          │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        DATABASE LAYER                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  _schedule_db_storage()         ✅ WORKS                                │
│       │                                                                   │
│       ▼                                                                   │
│  _store_event_in_db()           ✅ WORKS                                │
│       │                                                                   │
│       └─► DetectionEvent INSERT  ✅ SUCCESSFUL                          │
│                                                                           │
│  Database: detection_events table                                       │
│    - id, session_id, timestamp    ✅ STORED                            │
│    - voltage, channel             ✅ STORED                            │
│    - video_relative_timestamp     ✅ STORED                            │
│    - actual_latency_ms            ✅ STORED                            │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    │ ❌ BREAK POINT #1
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      WEBSOCKET LAYER                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  _notify_websocket_callbacks()                                          │
│       │                                                                   │
│       ├─► self.websocket_callbacks    ❌ EMPTY LIST                    │
│       └─► No callbacks registered     ❌ NO EMISSION                   │
│                                                                           │
│  socketio_server.emit_detection_event()                                 │
│       │                                                                   │
│       └─► Function exists but        ❌ NEVER CALLED                   │
│           NOT imported/called                                            │
│                                                                           │
│  Alternative: dedicated_labjack_monitor.py                              │
│       │                                                                   │
│       └─► _emit_detection_event_sync() ✅ WORKS                        │
│           BUT only for HIL mode                                         │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    │ Events NOT emitted
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  websocketService.ts                                                     │
│       │                                                                   │
│       ├─► subscribe('detection_event') ❌ NO SUBSCRIBERS               │
│       └─► Connection established       ✅ CONNECTED                    │
│                                                                           │
│  detectionService.ts                                                     │
│       │                                                                   │
│       ├─► runDetection()               ✅ YOLO ONLY                    │
│       ├─► getGroundTruth()             ✅ HTTP API                     │
│       └─► connectWebSocket()           ❌ DISABLED                     │
│                                                                           │
│  UI Components                                                           │
│       │                                                                   │
│       └─► Show only YOLO detections   ❌ NO LABJACK DATA               │
│           from HTTP polling                                              │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Root Cause Analysis

### Primary Issue: WebSocket Callback Registration Missing

**Location**: `backend/services/labjack_detection_service.py`

**Problem**: WebSocket callbacks are never registered during service initialization.

```python
# Current code (Line 137)
self.websocket_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

# Line 189: add_websocket_callback method exists but never called
def add_websocket_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
    with self.lock:
        self.websocket_callbacks.append(callback)
```

**Missing Integration**:
```python
# SHOULD exist in main.py or socketio_server.py but DOESN'T:
from services.labjack_detection_service import get_detection_service
from socketio_server import emit_detection_event

detection_service = get_detection_service()

async def websocket_emission_callback(session_id: str, message: Dict[str, Any]):
    await emit_detection_event(message['event'], session_id)

detection_service.add_websocket_callback(websocket_emission_callback)
```

### Secondary Issue: Frontend Not Subscribed

**Location**: `frontend/src/services/detectionService.ts`

**Problem**: Frontend detection service explicitly disables WebSocket functionality.

```typescript
// Line 483-485
connectWebSocket(videoId: string, onUpdate: (data: DetectionUpdate) => void): void {
    console.log('ℹ️ WebSocket functionality disabled - using HTTP-only detection workflow');
    // No WebSocket connections will be established
}
```

**Missing Subscription**:
```typescript
// SHOULD exist but DOESN'T:
import websocketService from './websocketService';

websocketService.subscribe('detection_event', (data: any) => {
    // Update UI with real-time detection
    console.log('📊 Real-time detection:', data);
    // Trigger UI update
});
```

---

## 8. Why Database Has Events But UI Doesn't

### The Complete Picture:

1. **Hardware Detection**: ✅ **WORKING**
   - LabJack reads voltage correctly
   - Threshold detection triggers properly
   - Events created with all required data

2. **Database Storage**: ✅ **WORKING**
   - Events stored with complete timing data
   - Session validation works
   - Transaction commits successfully

3. **WebSocket Emission**: ❌ **BROKEN**
   - No callbacks registered in detection service
   - Socket.IO emission function exists but isolated
   - Bridge between detection and WebSocket missing

4. **Frontend Reception**: ❌ **BROKEN**
   - WebSocket service works but no detection subscriptions
   - Detection service uses HTTP-only mode
   - No real-time event handlers registered

5. **Result**:
   - Database accumulates detection events ✅
   - UI never receives real-time updates ❌
   - Frontend only shows YOLO ground truth from HTTP API ❌
   - LabJack detections invisible to user ❌

---

## 9. Ground Truth Matching Impact

**File**: `backend/services/ground_truth_matching_service.py`

The ground truth matching service CAN read stored detection events:

```python
def match_detections_to_ground_truth(self, session_id: str):
    """Match all LabJack detections to ground truth objects"""  # Line 91

    # Reads from database successfully (Lines 150-175)
    detection_query = text("""
        SELECT id, timestamp, confidence, class_label, actual_latency_ms,
               video_relative_timestamp, video_frame_number, timing_sync_quality
        FROM detection_events
        WHERE test_session_id = :session_id
        ORDER BY timestamp
    """)
    detection_results = db.execute(detection_query, {'session_id': session_id}).fetchall()
```

**✅ This WORKS**: Ground truth matching can access all stored detections from database
**❌ But DOESN'T HELP**: UI still doesn't display them in real-time during test execution

---

## 10. Recommendations

### Critical Fixes Required:

1. **Register WebSocket Callback** (HIGH PRIORITY)
   ```python
   # In main.py or socketio_server startup:
   from services.labjack_detection_service import get_detection_service
   from socketio_server import emit_detection_event

   detection_service = get_detection_service()

   async def emission_bridge(session_id: str, message: Dict[str, Any]):
       await emit_detection_event(message['event'], session_id)

   detection_service.add_websocket_callback(emission_bridge)
   ```

2. **Enable Frontend Subscription** (HIGH PRIORITY)
   ```typescript
   // In UI component or detection service:
   websocketService.subscribe('detection_event', (data: any) => {
       console.log('📊 LabJack detection:', data);
       // Update detection state
       // Trigger UI re-render
   });
   ```

3. **Verify Socket.IO Rooms** (MEDIUM PRIORITY)
   - Ensure clients join correct session rooms
   - Verify `test_session_{session_id}` room subscription
   - Check 'detections' general room subscription

4. **Add Monitoring** (LOW PRIORITY)
   - Log WebSocket callback executions
   - Track emission success/failure
   - Monitor frontend subscription status

---

## 11. Verification Steps

After implementing fixes:

```bash
# 1. Backend: Verify callback registration
curl http://localhost:8000/api/debug/detection-service-status
# Should show: websocket_callbacks_registered: 1

# 2. WebSocket: Monitor emissions
# Watch browser console for:
# "📨 WebSocket message [detection_event]"

# 3. Database: Verify storage continues
sqlite3 dev_database.db "SELECT COUNT(*) FROM detection_events WHERE test_session_id='test-123';"

# 4. Frontend: Check subscription
# Browser console should show:
# "🔔 Subscribed to Socket.IO event: detection_event"
```

---

## 12. Conclusion

**The disconnect is caused by TWO independent breaks in the chain:**

1. **Backend**: WebSocket callbacks never registered → events stored but not emitted
2. **Frontend**: Detection service HTTP-only → real-time events not subscribed

**Both must be fixed** for complete hardware-to-UI real-time detection display.

The database correctly stores all detection events, proving the detection logic works. The issue is purely in the real-time communication layer between backend and frontend.
