# LabJack Connection Architecture Diagram

## Current Architecture (The Problem)

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       DedicatedLabJackMonitor                             │
│                     (Orchestrates HIL Sessions)                           │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
                ┌───────────────┴────────────────┐
                │                                │
                ▼                                ▼
┌───────────────────────────────────┐  ┌──────────────────────────────────┐
│   LabJackDetectionMonitor         │  │  VideoTimingService              │
│   (Session-Aware Detection)       │  │  (Video Synchronization)         │
│                                   │  │                                  │
│  ┌────────────────────────────┐  │  └──────────────────────────────────┘
│  │  self.labjack_service      │  │
│  │  (LabJackService)          │  │
│  │                            │  │
│  │  - session_count           │  │
│  │  - active_sessions         │  │
│  │  - Connection preserved    │  │
│  │    logging                 │  │
│  └────────────────────────────┘  │
│                                   │
│  ┌────────────────────────────┐  │
│  │  self.hardware_service     │  │
│  │  (LabJackHardwareService)  │  │
│  │                            │  │
│  │  - handle (hardware)       │  │
│  │  - health_check_active     │  │
│  │  - Health monitoring       │  │
│  │    thread                  │  │
│  └────────────────────────────┘  │
│                                   │
│  ⚠️  NO COORDINATION between      │
│      labjack_service and          │
│      hardware_service             │
└───────────────────────────────────┘
                │
                ▼
        ┌───────────────────────────┐
        │   LabJack USB Device      │
        │   (Physical Hardware)     │
        └───────────────────────────┘
```

## The Problem Timeline

```
Time    │ LabJackService         │ LabJackHardwareService  │ Hardware Handle
────────┼────────────────────────┼─────────────────────────┼─────────────────
T+0s    │ session_count = 0      │ health_check_active=T   │ VALID (open)
        │ "Connection preserved" │ health thread sleeping  │
        │                        │                         │
T+1s    │ [idle]                 │ [sleeping]              │ VALID
T+2s    │ [idle]                 │ [sleeping]              │ VALID
T+3s    │ [idle]                 │ [sleeping]              │ ???
T+4s    │ [idle]                 │ [sleeping]              │ ???
T+5s    │ [idle]                 │ [sleeping]              │ ???
T+6s    │ [idle]                 │ [sleeping]              │ ???
T+7s    │ [idle]                 │ [sleeping]              │ ???
T+8s    │ [idle]                 │ wakes up                │ CLOSED! ❌
        │                        │ read_single_voltage()   │
        │                        │ ❌ LJME_DEVICE_NOT_OPEN │
        │                        │ Error 1224              │
```

## Missing Communication Channel

```
┌─────────────────────────────────────────────────────────────────┐
│  What SHOULD Happen When Sessions = 0:                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  LabJackDetectionMonitor._cleanup_session_preserving_connection │
│          │                                                      │
│          ├─> 1. Clean up session data                          │
│          │                                                      │
│          ├─> 2. Update session count = 0                       │
│          │                                                      │
│          ├─> 3. ❌ MISSING: Notify hardware_service            │
│          │      "No active sessions, pause health checks"      │
│          │                                                      │
│          └─> 4. Log "Connection preserved"                     │
│                                                                 │
│  LabJackHardwareService                                        │
│          │                                                      │
│          ├─> ❌ NEVER NOTIFIED                                 │
│          │                                                      │
│          └─> Health monitor continues running                  │
│              Attempts to read from handle                       │
│              Handle has been closed (WHY?)                      │
│              ❌ LJME_DEVICE_NOT_OPEN                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Dual Service State Mismatch

```
┌─────────────────────────────────┐    ┌─────────────────────────────────┐
│      LabJackService             │    │   LabJackHardwareService        │
│   (Session Management)          │    │   (Hardware Access)             │
├─────────────────────────────────┤    ├─────────────────────────────────┤
│                                 │    │                                 │
│  State: CONNECTED               │    │  State: CONNECTED               │
│  active_session_count: 0        │    │  health_check_active: True      │
│  status: CONNECTED              │    │  connection_status: CONNECTED   │
│  direct_handle: VALID           │    │  handle: ??? (CLOSED?)          │
│                                 │    │                                 │
│  ✅ Session protection:         │    │  ❌ NO session awareness        │
│     Blocks disconnect if        │    │     No knowledge of sessions    │
│     sessions > 0                │    │     No coordination             │
│                                 │    │                                 │
│  ✅ Preserves connection        │    │  ⚠️ Health check continues     │
│     when sessions = 0           │    │     even when idle              │
│                                 │    │                                 │
└─────────────────────────────────┘    └─────────────────────────────────┘
         │                                          │
         │                                          │
         └──────────────────┬───────────────────────┘
                            │
                            ▼
            ⚠️ SAME HARDWARE, NO COORDINATION
```

## Connection Lifecycle Ownership Ambiguity

```
Who Owns the LabJack Hardware Connection?

┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  LabJackDetectionService mentions:                            │
│  ├─> self.connection_manager (line 186)                       │
│  ├─> "The connection manager handles the actual hardware      │
│  │    connection lifecycle" (line 2468 comment)               │
│  └─> get_connection_manager() from labjack_connection_manager │
│                                                                │
│  BUT:                                                          │
│  ├─> hardware_service has NO reference to connection_manager  │
│  ├─> hardware_service owns the actual handle                  │
│  └─> hardware_service.connect() creates connection            │
│                                                                │
│  QUESTION: Who is actually in charge?                         │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ a) connection_manager?     (mentioned but unclear)     │  │
│  │ b) hardware_service?       (has the handle)            │  │
│  │ c) labjack_service?        (has session tracking)      │  │
│  │ d) detection_service?      (orchestrates everything)   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                                │
│  ⚠️ ARCHITECTURAL AMBIGUITY                                   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Potential Connection Closure Paths

```
Where could handle be closed between T+0s and T+8s?

1. LabJackHardwareService.disconnect()
   ├─> Line 849: ljm.close(self.handle)
   ├─> Called by: ???
   └─> Has NO session protection

2. LabJackService.disconnect()
   ├─> Line 1755: ljm.close(self.direct_handle)
   ├─> ✅ HAS session protection (blocks if sessions > 0)
   └─> BUT sessions = 0, so could be called

3. Error cleanup paths
   ├─> Line 453: ljm.close during connection error
   ├─> Line 709: ljm.close in some method
   └─> Line 1214: ljm.close in some method

4. Garbage collection / __del__
   ├─> LabJackHardwareService.__del__ (line 864)
   └─> Calls self.disconnect() if connected

5. Connection manager (if it exists)
   ├─> Mentioned in code but unclear implementation
   └─> May have automatic cleanup logic

6. Timeout mechanism (speculative)
   ├─> Automatic disconnect after idle period?
   └─> No evidence found yet

┌──────────────────────────────────────────────────────────┐
│  CRITICAL: Need to add tracing to ALL ljm.close() calls │
│            to identify actual closure path               │
└──────────────────────────────────────────────────────────┘
```

## Health Monitor State Machine (Current)

```
┌─────────────────────────────────────────────────────────────┐
│  LabJackHardwareService Health Monitor                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  States:                                                    │
│  ┌──────────────┐         ┌──────────────┐                │
│  │   STOPPED    │────────>│   RUNNING    │                │
│  │              │ connect │              │                │
│  │  health_     │         │  health_     │                │
│  │  check_      │         │  check_      │                │
│  │  active=F    │         │  active=T    │                │
│  └──────────────┘         └──────┬───────┘                │
│         ▲                        │                         │
│         │                        │ disconnect              │
│         └────────────────────────┘                         │
│                                                             │
│  ❌ MISSING STATE: IDLE                                    │
│     (Connected but no active sessions)                     │
│                                                             │
│  Problem:                                                  │
│  ├─> No way to pause health checks when idle              │
│  ├─> Only options: RUNNING or STOPPED                     │
│  └─> When sessions=0, should pause, not stop              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Proposed Fix Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                       DedicatedLabJackMonitor                             │
└───────────────────────────────────┬───────────────────────────────────────┘
                                    │
                ┌───────────────────┴────────────────────┐
                │                                        │
                ▼                                        ▼
┌───────────────────────────────────────┐  ┌────────────────────────────────┐
│   UnifiedLabJackConnectionService     │  │  VideoTimingService            │
│   (Single Source of Truth)            │  └────────────────────────────────┘
│                                       │
│  ┌─────────────────────────────────┐ │
│  │  State Machine                  │ │
│  │  ┌──────────────────────────┐   │ │
│  │  │ DISCONNECTED             │   │ │
│  │  └───────┬──────────────────┘   │ │
│  │          │ connect               │ │
│  │          ▼                       │ │
│  │  ┌──────────────────────────┐   │ │
│  │  │ CONNECTED (sessions > 0) │   │ │
│  │  └───────┬──────────────────┘   │ │
│  │          │ sessions = 0          │ │
│  │          ▼                       │ │
│  │  ┌──────────────────────────┐   │ │
│  │  │ IDLE (sessions = 0)      │   │ │
│  │  │ - Handle preserved       │   │ │
│  │  │ - Health paused          │   │ │
│  │  └───────┬──────────────────┘   │ │
│  │          │ timeout / explicit    │ │
│  │          ▼                       │ │
│  │  ┌──────────────────────────┐   │ │
│  │  │ DISCONNECTED             │   │ │
│  │  └──────────────────────────┘   │ │
│  └─────────────────────────────────┘ │
│                                       │
│  Features:                            │
│  ✅ Single hardware handle            │
│  ✅ Session-aware health monitoring   │
│  ✅ Coordinated state transitions     │
│  ✅ Clear ownership                   │
│  ✅ Event notifications               │
│                                       │
└───────────────────────────────────────┘
                │
                ▼
        ┌───────────────────────────┐
        │   LabJack USB Device      │
        └───────────────────────────┘
```

## Key Findings Summary

1. **Dual Service Architecture** - Two services manage same hardware independently
2. **No Coordination** - Services don't communicate state changes
3. **Health Monitor Continues** - Runs even when sessions = 0 (should pause)
4. **Unclear Ownership** - Who controls connection lifecycle?
5. **Missing IDLE State** - No concept of "connected but inactive"
6. **8-Second Gap** - Health check interval explains timing of error
7. **Mystery Remains** - WHO closed the handle? Need tracing to identify

## Investigation Status

- ✅ Architecture mapped
- ✅ Services identified
- ✅ State mismatch explained
- ✅ Timing explained (health check interval)
- ❓ Actual closure path - STILL UNKNOWN
- ❓ Connection manager role - UNCLEAR
- ❓ Automatic cleanup - POSSIBLE

**Next Action**: Add debug tracing to all ljm.close() calls to catch the actual closure event.
