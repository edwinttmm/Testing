# HIL Monitoring System Architecture Diagram

## Current Architecture (Problematic)

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[HIL Test UI]
        WS[WebSocket Client]
    end
    
    subgraph "API Layer"
        Router[Test Sessions Router<br/>routers/test_sessions.py]
        HIL_API[HIL Test Complete API<br/>api/hil_test_complete.py]
    end
    
    subgraph "Service Layer - Session Management"
        DLM[DedicatedLabJackMonitor<br/>services/dedicated_labjack_monitor.py]
        LMS[LabJackMonitoringService<br/>services/labjack_monitoring_service.py]
    end
    
    subgraph "Service Layer - Detection"
        LDS[LabJackDetectionService<br/>services/labjack_detection_service.py]
        VTS[VideoTimingService<br/>services/video_timing_service.py]
        GTS[GroundTruthMatchingService]
    end
    
    subgraph "Hardware Layer"
        LJ[LabJack T7 Hardware]
        WSL[Windows-WSL Bridge<br/>services/windows_labjack_bridge.py]
    end
    
    subgraph "Storage Layer"
        DB[(SQLite Database)]
        MEM[In-Memory Session Data]
    end
    
    %% Flow connections
    UI -->|Start HIL Test| Router
    Router -->|start_hil_monitoring| DLM
    DLM -->|add_detection_callback| LDS
    DLM -->|start_monitoring| LDS
    LDS -->|read_analog_voltage| WSL
    WSL -->|voltage readings| LJ
    
    %% Problem flows (red)
    LDS -.->|callback fires| DLM
    DLM -.->|KeyError!| MEM
    
    %% Persistence issues
    LDS -.->|continues after cleanup| LJ
    
    %% Data flows
    DLM -->|store events| DB
    DLM -->|session state| MEM
    LDS -->|detection events| DB
    
    %% WebSocket
    DLM -->|status updates| WS
    
    style DLM fill:#ffcccc
    style LDS fill:#ffcccc
    style MEM fill:#ffcccc
```

## Problem Areas Identified

### 1. Race Condition Zone
```mermaid
sequenceDiagram
    participant Router
    participant DLM as DedicatedLabJackMonitor
    participant LDS as LabJackDetectionService
    participant Hardware as LabJack Hardware
    
    Router->>DLM: start_hil_monitoring()
    
    rect rgb(255, 200, 200)
        Note over DLM,Hardware: RACE CONDITION ZONE
        DLM->>DLM: Initialize active_sessions[id] = {}
        DLM->>LDS: add_detection_callback(callback)
        DLM->>LDS: start_monitoring(session_id)
        
        Hardware-->>LDS: Immediate voltage detection!
        LDS->>DLM: callback(event) 
        
        Note over DLM: KeyError: session_id not fully initialized
        DLM->>DLM: active_sessions.get(session_id) ❌
    end
```

### 2. Session Lifecycle Issues
```mermaid
stateDiagram-v2
    [*] --> Initializing
    Initializing --> Ready: session_dict_complete
    Ready --> Processing: detection_events
    Processing --> Stopping: test_complete
    Stopping --> Stopped: cleanup_complete
    Stopped --> [*]
    
    state "Problem States" as Problems {
        Initializing --> KeyError: callback_fires_early
        Stopped --> GhostEvents: callbacks_still_registered
    }
```

## Improved Architecture (Recommended)

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[HIL Test UI]
        WS[WebSocket Client]
    end
    
    subgraph "API Layer"
        Router[Test Sessions Router]
        HIL_API[HIL Test Complete API]
    end
    
    subgraph "Session Management Layer - IMPROVED"
        SM[SessionManager<br/>🔒 Atomic Operations]
        SC[SessionController<br/>🔄 State Machine]
        CB[CallbackRegistry<br/>🧹 Cleanup Manager]
    end
    
    subgraph "Monitoring Layer - SEPARATED"
        DLM[DedicatedLabJackMonitor<br/>📊 Session-Scoped]
        GM[GlobalMonitor<br/>🔌 Hardware Manager]
        ER[EventRouter<br/>🎯 Event Distribution]
    end
    
    subgraph "Detection Layer"
        LDS[LabJackDetectionService<br/>⚡ Real-time Detection]
        VTS[VideoTimingService<br/>📹 Timestamp Sync]
        GTS[GroundTruthMatching<br/>✅ Validation]
    end
    
    subgraph "Hardware Layer"
        LJ[LabJack T7 Hardware]
        WSL[Windows-WSL Bridge]
    end
    
    subgraph "Storage Layer"
        DB[(SQLite Database)]
        MEM[🔒 Thread-Safe Session Store]
        BUF[🔄 Event Buffer]
    end
    
    %% Improved flows
    UI -->|Start HIL Test| Router
    Router -->|atomic_session_create| SM
    SM -->|initialize_complete| SC
    SC -->|register_callbacks| CB
    CB -->|session_ready| DLM
    
    DLM -->|scoped_monitoring| GM
    GM -->|hardware_control| LDS
    LDS -->|voltage_readings| WSL
    WSL -->|device_access| LJ
    
    %% Safe callback flow
    LDS -->|detection_event| ER
    ER -->|route_to_session| DLM
    DLM -->|validate_session| SC
    SC -->|process_if_ready| BUF
    BUF -->|batch_store| DB
    
    %% Cleanup flow
    Router -->|test_complete| SM
    SM -->|cleanup_sequence| SC
    SC -->|remove_callbacks| CB
    CB -->|stop_monitoring| GM
    GM -->|session_cleanup| DLM
    
    style SM fill:#ccffcc
    style SC fill:#ccffcc
    style CB fill:#ccffcc
    style ER fill:#ccffcc
    style MEM fill:#ccffcc
```

## Key Architectural Improvements

### 1. Atomic Session Management
```python
class SessionManager:
    """Ensures atomic session lifecycle operations"""
    
    @atomic_operation
    def create_hil_session(self, session_id: str, config: Dict) -> bool:
        """Atomically creates session with all dependencies"""
        with self.global_lock:
            # 1. Validate preconditions
            # 2. Initialize complete session state
            # 3. Register callbacks
            # 4. Start monitoring
            # 5. Mark as ready
            return True
```

### 2. State Machine Control
```python
class SessionState(Enum):
    INITIALIZING = "initializing"
    READY = "ready"  
    PROCESSING = "processing"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class SessionController:
    """Controls session state transitions safely"""
    
    def transition_to(self, session_id: str, new_state: SessionState) -> bool:
        """Thread-safe state transitions with validation"""
```

### 3. Callback Registry with Cleanup
```python
class CallbackRegistry:
    """Manages callback lifecycle with proper cleanup"""
    
    def register_callback(self, session_id: str, callback: Callable) -> str:
        """Register callback with automatic cleanup"""
        
    def cleanup_session_callbacks(self, session_id: str) -> None:
        """Remove all callbacks for session before cleanup"""
```

### 4. Event Router for Safe Distribution
```python
class EventRouter:
    """Routes events to appropriate handlers safely"""
    
    def route_detection_event(self, event: DetectionEvent) -> None:
        """Route event only to active, ready sessions"""
        session_id = event.session_id
        if self.session_controller.is_ready(session_id):
            self.dedicated_monitor.handle_event(session_id, event)
```

## Implementation Priority

1. **CRITICAL**: Fix race condition in session initialization
2. **HIGH**: Implement proper callback cleanup sequence
3. **HIGH**: Add session state validation to detection handlers
4. **MEDIUM**: Separate global vs session-scoped monitoring
5. **MEDIUM**: Add event buffering for cleanup grace periods
6. **LOW**: Implement full state machine architecture

## Files Requiring Changes

1. `services/dedicated_labjack_monitor.py` - Fix race condition
2. `services/labjack_detection_service.py` - Add callback cleanup
3. `routers/test_sessions.py` - Improve session lifecycle
4. `services/labjack_monitoring_service.py` - Scope monitoring properly

This architecture ensures **thread-safe session management**, **proper resource cleanup**, and **elimination of race conditions** in the HIL monitoring system.