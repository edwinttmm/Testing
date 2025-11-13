# HIL System Quick Reference

## Critical Information for HIL Testing

### 🚨 CRITICAL FINDING

**The dedicated monitoring service is NOT automatically started with the main application.**

```bash
# ❌ WRONG - Just starting FastAPI won't enable monitoring
uvicorn main:app

# ✅ CORRECT - Must start monitoring service separately
python scripts/start_monitoring_service.py --mode subprocess --daemon &
uvicorn main:app
```

---

## Service Startup Commands

### Development Environment

```bash
# Terminal 1: Start monitoring service (REQUIRED)
cd /home/rigade/Testing/ai-model-validation-platform/backend
python scripts/start_monitoring_service.py --mode subprocess --daemon

# Terminal 2: Start main API
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Verify services are running
curl http://localhost:8000/api/system/health  # Check API health
python -c "import socket; s = socket.socket(socket.AF_UNIX); s.connect('/tmp/monitoring_service.sock'); print('Monitoring OK')"
```

### Production Environment

```bash
# Use process manager like systemd or supervisord
# See deployment guide for production setup
```

---

## Service Architecture at a Glance

### What's Auto-Started ✅
- FastAPI main application
- Database connection
- WebSocket manager
- API route handlers
- Session management service
- Timing synchronization service
- Ground truth matching service

### What's NOT Auto-Started ❌
- **Dedicated monitoring service** ← CRITICAL
- LabJack hardware initialization (done on-demand)

---

## Data Flow Summary

```
Camera → LED Signal → LabJack → Monitoring Service → Database → Frontend
                                     ↑
                              (MUST BE STARTED MANUALLY)
```

### Complete Flow

1. **Camera detects object** → LED triggers (5V TTL signal)
2. **LabJack reads voltage** → AIN0 channel (monitored by monitoring service)
3. **Monitoring service detects rising edge** → Creates detection event
4. **Timing sync calculates video timestamp** → Applies 166ms calibration
5. **Detection stored in database** → `detection_events` table
6. **GT matching compares to annotations** → Calculates precision/recall
7. **WebSocket broadcasts results** → Real-time updates to frontend
8. **Frontend displays** → Timeline visualization + metrics

---

## Key Services & Their Roles

### 1. Dedicated Monitoring Service
**File:** `/services/dedicated_monitoring_service.py`
**Purpose:** Standalone process that monitors LabJack signals
**Startup:** ❌ Manual (should be automatic)
**Communication:** IPC via Unix socket `/tmp/monitoring_service.sock`

**Key Functions:**
- Continuously reads LabJack AIN0 channel
- Detects rising edges (voltage > threshold)
- Stores detection events in database
- Provides IPC interface for control

### 2. LabJack Detection Service
**File:** `/services/labjack_detection_service.py`
**Purpose:** Event-based detection with timing calibration
**Startup:** ✅ On-demand (when test starts)

**Key Functions:**
- Thread-based voltage monitoring
- Debounce logic (prevents duplicates)
- Timing synchronization with video
- WebSocket notifications

### 3. Timing Synchronization Service
**File:** `/services/timing_synchronization_service.py`
**Purpose:** Align LabJack timestamps with video playback

**Key Functions:**
- Records video lifecycle events (play start, etc.)
- Converts raw timestamps to video-relative time
- Applies calibration offsets (166ms empirically determined)
- Calculates timing quality metrics

### 4. Ground Truth Matching Service
**File:** `/services/ground_truth_matching_service.py`
**Purpose:** Compare detections to annotated ground truth

**Key Functions:**
- Matches detections to GT objects within tolerance window
- Calculates precision, recall, F1-score
- Computes latency statistics
- Identifies true positives, false positives, false negatives

### 5. WebSocket Manager
**File:** `/services/websocket_service.py`
**Purpose:** Real-time communication with frontend

**Key Functions:**
- Connection pooling and room management
- Session-based message routing
- Message history and replay
- Periodic connection cleanup

---

## Database Schema (Key Tables)

### test_sessions
```sql
- id: UUID
- name: TEXT
- status: TEXT (running, completed, failed)
- video_id: UUID
- video_start_timestamp: FLOAT (epoch)
- created_at: TIMESTAMP
- completed_at: TIMESTAMP
```

### detection_events
```sql
- id: UUID
- test_session_id: UUID
- timestamp: FLOAT (epoch)
- video_relative_timestamp: FLOAT (seconds from video start)
- actual_latency_ms: FLOAT (processing latency)
- labjack_voltage: FLOAT
- detection_channel: TEXT (AIN0, AIN1)
- timing_sync_quality: FLOAT (0.0-1.0)
- validation_result: TEXT (passed/failed)
- created_at: TIMESTAMP
```

### ground_truth_objects
```sql
- id: UUID
- video_id: UUID
- timestamp: FLOAT (video time)
- class_label: TEXT
- bounding_box: JSON
- metadata: JSON
```

---

## API Endpoints Reference

### HIL Testing
```
POST   /api/hil/start-test                    # Start HIL test
GET    /api/hil/{session_id}/status           # Get test status
GET    /api/hil/{session_id}/detections       # Get detection events
GET    /api/hil/{session_id}/ground-truth-comparison  # GT comparison
POST   /api/hil/{session_id}/stop             # Stop test
```

### Monitoring Service
```
POST   /api/monitoring/start/{session_id}     # Start monitoring
POST   /api/monitoring/stop/{session_id}      # Stop monitoring
GET    /api/monitoring/status/{session_id}    # Get monitoring status
GET    /api/monitoring/health                 # Health check
```

### Test Sessions
```
GET    /api/test-sessions                     # List sessions
POST   /api/test-sessions                     # Create session
GET    /api/test-sessions/{id}                # Get session
PUT    /api/test-sessions/{id}                # Update session
DELETE /api/test-sessions/{id}                # Delete session
```

### Latency Analysis
```
GET    /api/latency-analysis/{session_id}     # Get latency metrics
GET    /api/latency-analysis/{session_id}/decomposition  # Detailed breakdown
```

---

## Configuration Files

### LabJack Config
**Location:** `/config/labjack_config.json`
```json
{
  "device_type": "U3",
  "channels": ["AIN0", "AIN1"],
  "sample_rate": 1000,
  "voltage_range": {
    "min": 0,
    "max": 5
  },
  "detection_threshold": 2.5,
  "debounce_ms": 100
}
```

### Timing Calibration
**Location:** Code in `timing_synchronization_service.py`
```python
TIMING_CALIBRATION_OFFSET_MS = 166.0  # Empirically determined
```

---

## Troubleshooting

### Issue: No Detections Recorded

**Symptom:** Test runs but no detection events appear
**Cause:** Monitoring service not running
**Fix:**
```bash
# Check if monitoring service is running
ps aux | grep monitoring_service

# If not running, start it
python scripts/start_monitoring_service.py --mode subprocess --daemon

# Verify IPC socket exists
ls -la /tmp/monitoring_service.sock
```

### Issue: Timing Offset Incorrect

**Symptom:** Detections don't align with ground truth
**Cause:** Calibration offset may need adjustment
**Fix:**
```python
# Edit timing_synchronization_service.py
TIMING_CALIBRATION_OFFSET_MS = 166.0  # Adjust this value

# Or use dynamic calibration (recommended)
sync_service.calibrate_offset(session_id)
```

### Issue: LabJack Connection Failed

**Symptom:** "LabJack device not found"
**Fix:**
```bash
# Check USB connection
lsusb | grep LabJack

# Test connection
python scripts/test_labjack_connection.py

# Check permissions (Linux)
sudo usermod -a -G plugdev $USER
```

### Issue: WebSocket Not Updating

**Symptom:** Frontend doesn't receive real-time updates
**Fix:**
```javascript
// Check WebSocket connection in browser console
ws = new WebSocket('ws://localhost:8000/ws/test');
ws.onopen = () => console.log('Connected');
ws.onmessage = (msg) => console.log('Message:', msg.data);

// Check backend WebSocket status
curl http://localhost:8000/api/websocket/status
```

---

## Health Check Commands

### System Health
```bash
# Check all services
curl http://localhost:8000/api/system/health

# Expected response:
{
  "api": "healthy",
  "database": "connected",
  "monitoring": "active",  # ← Should be "active"
  "labjack": "connected",
  "websocket": "healthy"
}
```

### Individual Service Checks

```bash
# Database
curl http://localhost:8000/api/database/health

# Monitoring service
curl http://localhost:8000/api/monitoring/health

# LabJack hardware
curl http://localhost:8000/api/labjack/status

# WebSocket connections
curl http://localhost:8000/api/websocket/stats
```

---

## Environment Variables

```bash
# Database
DATABASE_URL="postgresql://user:pass@localhost/validation_db"  # Production
# DATABASE_URL="sqlite:///./dev_database.db"  # Development

# LabJack
LABJACK_MOCK_MODE="false"  # Set to "true" for testing without hardware
LABJACK_SAMPLE_RATE="1000"
LABJACK_DETECTION_THRESHOLD="2.5"

# Monitoring
MONITORING_AUTO_START="true"  # Not yet implemented
MONITORING_IPC_SOCKET="/tmp/monitoring_service.sock"

# API
API_HOST="0.0.0.0"
API_PORT="8000"
CORS_ORIGINS="http://localhost:3000,http://localhost:5173"
```

---

## Testing Commands

### Unit Tests
```bash
# Run all tests
pytest

# Run specific test files
pytest tests/test_labjack_detection_service.py
pytest tests/test_timing_synchronization.py
pytest tests/test_ground_truth_matching.py
```

### Integration Tests
```bash
# Full HIL test workflow
pytest tests/integration/test_hil_workflow.py

# WebSocket integration
pytest tests/test_websocket_hil_integration.py
```

### Manual Testing
```bash
# Test LabJack connection
python scripts/test_labjack_connection.py

# Validate monitoring service
python scripts/validate_monitoring_service.py

# Test timing synchronization
python tests/test_timing_accuracy.py
```

---

## Logging

### Log Files
```
backend/logs/
├── app.log                    # Main application logs
├── monitoring_service.log     # Monitoring service logs
├── labjack.log               # LabJack hardware logs
└── websocket.log             # WebSocket communication logs
```

### Log Levels
```python
# Set in code or environment
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Viewing Logs
```bash
# Tail main application log
tail -f logs/app.log

# Watch monitoring service
tail -f monitoring_service.log

# Filter for errors
grep ERROR logs/app.log

# Follow WebSocket activity
tail -f logs/websocket.log | grep "test_session"
```

---

## Performance Metrics

### Expected Latencies
- **LabJack sampling:** ~1ms (1000 Hz sample rate)
- **Detection processing:** ~5ms (signal validation + storage)
- **Timing synchronization:** ~2ms (timestamp calculation)
- **Database write:** ~10ms (SQLite), ~5ms (PostgreSQL)
- **WebSocket broadcast:** ~3ms (local network)
- **Total detection latency:** ~20-30ms typical

### System Requirements
- **CPU:** Multi-core (4+ cores recommended)
- **RAM:** 4GB minimum, 8GB recommended
- **Disk:** SSD recommended for database
- **Network:** 1Gbps for high-frequency testing

---

## Quick Deployment Checklist

### Pre-Deployment
- [ ] All environment variables set
- [ ] Database migrations applied
- [ ] LabJack hardware connected and tested
- [ ] Monitoring service configured
- [ ] WebSocket CORS configured for frontend

### Startup Sequence
1. [ ] Start database (if external)
2. [ ] Start monitoring service
3. [ ] Start main FastAPI application
4. [ ] Verify all health checks pass
5. [ ] Test end-to-end with sample HIL test

### Post-Deployment
- [ ] Monitor logs for errors
- [ ] Verify detection events are recorded
- [ ] Check timing accuracy against ground truth
- [ ] Validate WebSocket real-time updates

---

## Important File Locations

### Service Files
```
/backend/services/
├── dedicated_monitoring_service.py    ← Main monitoring process
├── labjack_detection_service.py       ← Detection with timing
├── timing_synchronization_service.py  ← Video-LabJack sync
├── ground_truth_matching_service.py   ← GT comparison
└── websocket_service.py               ← Real-time updates
```

### API Routers
```
/backend/routers/
├── hil_testing.py                     ← HIL test endpoints
├── test_sessions.py                   ← Session management
├── monitoring_service_endpoints.py    ← Monitoring API
└── latency_analysis.py                ← Latency endpoints
```

### Configuration
```
/backend/config/
└── labjack_config.json                ← LabJack settings
```

### Scripts
```
/backend/scripts/
├── start_monitoring_service.py        ← Service startup
└── test_labjack_connection.py         ← Hardware test
```

---

## Common Code Patterns

### Starting a HIL Test
```python
# API endpoint pattern
@router.post("/api/hil/start-test")
async def start_hil_test(request: HILTestRequest, db: Session = Depends(get_db)):
    # 1. Create test session
    session = TestSession(
        id=str(uuid.uuid4()),
        video_id=request.video_id,
        status="running"
    )
    db.add(session)
    db.commit()

    # 2. Start monitoring
    monitoring_service.start_monitoring(session.id)

    # 3. Record video start time
    timing_sync.record_video_event(session.id, "play_start")

    return {"session_id": session.id}
```

### Processing Detections
```python
# Detection callback pattern
def on_detection(event: DetectionEvent):
    # 1. Apply timing synchronization
    video_time, quality = timing_sync.get_synchronized_timestamp(
        event.session_id, event.timestamp
    )

    # 2. Store in database
    db_event = DetectionEvent(
        id=event.id,
        test_session_id=event.session_id,
        timestamp=event.timestamp,
        video_relative_timestamp=video_time,
        timing_sync_quality=quality
    )
    db.add(db_event)
    db.commit()

    # 3. Broadcast via WebSocket
    websocket_manager.send_json_to_room(
        {"type": "detection", "data": event.to_dict()},
        f"test_session_{event.session_id}"
    )
```

---

## Contact & Support

**Architecture Documentation:** `/backend/docs/HIL_SYSTEM_ARCHITECTURE_REVIEW.md`
**Dependency Map:** `/backend/docs/HIL_SERVICE_DEPENDENCY_MAP.md`
**This Guide:** `/backend/docs/HIL_QUICK_REFERENCE.md`

---

**Last Updated:** 2025-10-01
**Version:** 1.0
**Status:** Architecture review complete, critical gaps identified
