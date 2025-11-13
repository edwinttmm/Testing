# HIL Service Dependency Map

## Visual Service Dependencies

### Core Service Graph

```
                    ┌─────────────────────┐
                    │   main.py FastAPI   │
                    │   (Entry Point)     │
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
            ↓                  ↓                  ↓
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │   Database   │   │   WebSocket  │   │   LabJack    │
    │   Service    │   │   Manager    │   │   Services   │
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           │                  │                   │
           │                  │                   │
           ↓                  ↓                   ↓
    ┌──────────────────────────────────────────────────┐
    │              HIL Testing Services                 │
    │  ┌─────────────────────────────────────────┐    │
    │  │  1. Session Management Service          │    │
    │  │  2. Timing Synchronization Service      │    │
    │  │  3. Detection Pipeline Service          │    │
    │  │  4. Ground Truth Matching Service       │    │
    │  │  5. Results Storage Service             │    │
    │  └─────────────────────────────────────────┘    │
    └──────────────────────────────────────────────────┘
                               │
                               ↓
    ┌──────────────────────────────────────────────────┐
    │     ⚠️ ISOLATED - NOT AUTO-STARTED               │
    │                                                   │
    │  dedicated_monitoring_service.py                 │
    │  • Runs as separate process                      │
    │  • IPC via Unix socket                           │
    │  • Manual startup required                       │
    └──────────────────────────────────────────────────┘
```

---

## Service Startup Dependencies

### Level 1: Foundation (Must Start First)
```
┌─────────────────────────────────────────────┐
│  1. Database Connection                     │
│     • SQLite: dev_database.db               │
│     • PostgreSQL: production                │
│     Status: ✅ Auto-initialized             │
└─────────────────────────────────────────────┘
```

### Level 2: Core Infrastructure
```
┌─────────────────────────────────────────────┐
│  2. LabJack Hardware Detection              │
│     • Scan for U3/U6 devices                │
│     • Initialize connection pool            │
│     • Fallback to mock if unavailable       │
│     Status: ⚠️ On-demand (should be startup)│
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  3. WebSocket Manager                       │
│     • Initialize connection pool            │
│     • Create room registry                  │
│     • Start cleanup task                    │
│     Status: ✅ Auto-initialized             │
└─────────────────────────────────────────────┘
```

### Level 3: Monitoring Services (CRITICAL GAP)
```
┌─────────────────────────────────────────────┐
│  4. ⚠️ Dedicated Monitoring Service         │
│     • Launch subprocess                     │
│     • Wait for IPC socket                   │
│     • Verify health check                   │
│     Status: ❌ Manual startup required      │
└─────────────────────────────────────────────┘
```

### Level 4: Application Services
```
┌─────────────────────────────────────────────┐
│  5. Session Management Service              │
│  6. Timing Synchronization Service          │
│  7. Detection Pipeline Service              │
│  8. Ground Truth Matching Service           │
│  9. Results Storage Service                 │
│     Status: ✅ On-demand (as needed)        │
└─────────────────────────────────────────────┘
```

---

## Service Communication Matrix

| Service | Communicates With | Protocol | Status |
|---------|-------------------|----------|--------|
| **Main API** | Frontend | HTTP/REST, WebSocket | ✅ |
| **Main API** | Database | SQLAlchemy ORM | ✅ |
| **Main API** | LabJack Services | Python import | ✅ |
| **Main API** | Monitoring Service | ❌ None (should be IPC) | ❌ |
| **Monitoring Service** | LabJack Hardware | Direct USB | ⚠️ (not auto-started) |
| **Monitoring Service** | Database | SQLite direct | ⚠️ (not auto-started) |
| **Detection Service** | WebSocket Manager | Python function call | ✅ |
| **WebSocket Manager** | Frontend | WebSocket protocol | ✅ |
| **Timing Sync** | Database | SQLAlchemy ORM | ✅ |
| **GT Matching** | Database | SQLAlchemy ORM | ✅ |

---

## Data Flow Dependencies

### HIL Test Data Pipeline

```
Step 1: Test Initiation
   Frontend → HTTP → Main API
   Main API → Database (create test_session)

Step 2: Video Start
   Frontend → HTTP → Main API
   Main API → Timing Sync (record video_start_timestamp)

Step 3: ⚠️ MISSING - Monitoring Start
   ❌ Should: Main API → IPC → Monitoring Service
   ❌ Actually: Manual script execution required

Step 4: Detection
   Monitoring Service → LabJack Hardware
   Monitoring Service → Database (detection_events)

Step 5: Synchronization
   Detection Service → Timing Sync
   Timing Sync → Calculate video_relative_timestamp

Step 6: Storage
   Detection Service → Database (update detection_events)

Step 7: GT Matching
   GT Matching Service → Database (query GT + detections)
   GT Matching Service → Calculate metrics

Step 8: Results Delivery
   Results Service → Database
   Results Service → WebSocket Manager
   WebSocket Manager → Frontend
```

---

## Critical Dependencies Not Met

### ❌ Monitoring Service Auto-Start

**Current Flow:**
```
User starts FastAPI app
  ↓
main.py initializes
  ↓
API routers registered
  ↓
❌ Monitoring service NOT started
  ↓
User must manually run:
  python scripts/start_monitoring_service.py
  ↓
Only then monitoring works
```

**Required Flow:**
```
User starts FastAPI app
  ↓
main.py lifespan startup
  ↓
✅ Launch monitoring service subprocess
  ↓
✅ Wait for IPC socket ready
  ✅ Verify health check
  ↓
API routers registered
  ↓
✅ Monitoring automatically active
```

---

## Service File Locations

### Main Application
```
/backend/main.py
  └─ Entry point for FastAPI application
```

### Monitoring Services
```
/backend/services/
  ├── dedicated_monitoring_service.py    ← Standalone process (not auto-started)
  ├── labjack_monitoring_service.py      ← Thread-based monitoring
  ├── labjack_detection_service.py       ← Event detection with WebSocket
  └── monitoring_process_manager.py      ← Process lifecycle (exists but not used)
```

### Startup Scripts
```
/backend/scripts/
  └── start_monitoring_service.py        ← Manual startup script
```

### LabJack Hardware
```
/backend/services/
  ├── labjack_service.py                 ← Base service
  ├── labjack_hardware_service.py        ← Hardware interface
  ├── real_labjack_service.py            ← Real device operations
  └── labjack_connection_manager.py      ← Connection pooling
```

### Timing & Sync
```
/backend/services/
  ├── timing_synchronization_service.py  ← Video-LabJack sync
  ├── video_timing_service.py            ← Video timestamps
  ├── precision_timing_service.py        ← High-precision timing
  └── latency_validation_service.py      ← Latency analysis
```

### API Endpoints
```
/backend/routers/
  ├── hil_testing.py                     ← HIL test endpoints
  ├── test_sessions.py                   ← Session management
  ├── monitoring_service_endpoints.py    ← Monitoring API (exists but service not started)
  └── latency_analysis.py                ← Latency endpoints
```

---

## Integration Points

### 1. FastAPI ↔ Database
- **Protocol:** SQLAlchemy ORM
- **Status:** ✅ Working
- **Location:** `database.py`, `models.py`

### 2. FastAPI ↔ WebSocket
- **Protocol:** WebSocket
- **Status:** ✅ Working
- **Location:** `services/websocket_service.py`

### 3. FastAPI ↔ LabJack
- **Protocol:** Python imports
- **Status:** ✅ Working (on-demand)
- **Location:** `services/labjack_service.py`

### 4. ⚠️ FastAPI ↔ Monitoring Service
- **Protocol:** IPC via Unix socket
- **Status:** ❌ NOT INTEGRATED
- **Issue:** Service not auto-started
- **Location:** `services/dedicated_monitoring_service.py`

### 5. Frontend ↔ Backend
- **Protocol:** HTTP/REST, WebSocket
- **Status:** ✅ Working
- **Endpoints:** `/api/*`, `/ws`

---

## Dependency Resolution Strategy

### Phase 1: Service Lifecycle
```python
# Add to main.py lifespan
from services.monitoring_process_manager import monitoring_process_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup ...

    # Start monitoring service
    logger.info("Starting monitoring service...")
    result = await monitoring_process_manager.start_service(auto_restart=True)

    if not result.get("success"):
        logger.error("Monitoring service failed to start")
        # Decide: fail startup or continue without monitoring

    yield

    # Shutdown monitoring service
    await monitoring_process_manager.stop_service()
```

### Phase 2: Health Checks
```python
# Add health check endpoint
@app.get("/api/system/health")
async def system_health():
    return {
        "api": "healthy",
        "database": await check_db(),
        "monitoring": await check_monitoring_service(),
        "labjack": await check_labjack(),
        "websocket": await check_websocket()
    }
```

### Phase 3: Service Discovery
```python
# Create service registry
class ServiceRegistry:
    def __init__(self):
        self.services = {}

    def register(self, name, service, health_check_fn):
        self.services[name] = {
            "service": service,
            "health_check": health_check_fn,
            "status": "unknown"
        }

    async def check_all_health(self):
        for name, info in self.services.items():
            info["status"] = await info["health_check"]()
```

---

## Critical Path Analysis

### Test Execution Critical Path

1. **✅ User initiates test** (Frontend → API)
2. **✅ Create test session** (API → Database)
3. **✅ Start video playback** (Frontend)
4. **❌ Start monitoring** ← **CRITICAL GAP**
5. **⚠️ Detect LED signals** (if monitoring running)
6. **✅ Store detections** (Monitoring → Database)
7. **✅ Synchronize timing** (Timing Service)
8. **✅ Match ground truth** (GT Service)
9. **✅ Send results** (WebSocket → Frontend)

**Failure Point:** Step 4
- If monitoring service not running, steps 5-9 fail
- No error feedback to user
- Test appears to succeed but has no detection data

---

## Recommendations

### Immediate Actions

1. **Modify main.py lifespan:**
   ```python
   # Add monitoring service to startup sequence
   await monitoring_process_manager.start_service()
   ```

2. **Add health check endpoint:**
   ```python
   # Verify all services are running
   @app.get("/api/system/health")
   ```

3. **Create service status UI:**
   ```typescript
   // Frontend component to show service status
   <ServiceHealthDashboard />
   ```

### Long-term Improvements

1. **Service orchestration framework**
2. **Circuit breaker pattern for services**
3. **Automatic service recovery**
4. **Centralized configuration management**

---

## Dependencies Summary

### External Dependencies
- **Hardware:** LabJack U3/U6 DAQ device
- **OS:** Linux (WSL compatible), Windows (with bridge)
- **Database:** SQLite (dev) or PostgreSQL (prod)
- **Python:** 3.9+ with asyncio support

### Internal Service Dependencies
- **High Priority:** Database, WebSocket Manager
- **Medium Priority:** LabJack Services, Timing Services
- **Critical Gap:** Monitoring Service lifecycle

### Configuration Dependencies
- `config/labjack_config.json` - LabJack settings
- Environment variables - API keys, database URLs
- Hardcoded values - Timing offsets (should be configurable)

---

**Last Updated:** 2025-10-01
**Status:** Architecture review complete, implementation gaps identified
