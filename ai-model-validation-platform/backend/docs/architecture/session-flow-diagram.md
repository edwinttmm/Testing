# Session Flow Architecture Diagram

## Current Architecture (With Bug)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                                  │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ POST /api/video-sequences/start                                    │ │
│  │  {                                                                 │ │
│  │    project_id: "...",                                              │ │
│  │    video_ids: ["10c2b16c..."],                                     │ │
│  │    enable_labjack_monitoring: true                                 │ │
│  │  }                                                                 │ │
│  └────────────────────────┬──────────────────────────────────────────┘ │
└───────────────────────────┼────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     API Layer (FastAPI)                                  │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ routers/video_sequence_testing.py:start_video_sequence()          │ │
│  │                                                                    │ │
│  │ Step 1: Create database session                                   │ │
│  │   test_session_id = uuid4()  # 028afcb1... (PRIMARY)              │ │
│  │   sequence_id = uuid4()                                           │ │
│  │                                                                    │ │
│  │   test_session = TestSession(                                     │ │
│  │     id=test_session_id,                                           │ │
│  │     project_id=project_id,                                        │ │
│  │     video_id=video_ids[0],                                        │ │
│  │     status="running"                                              │ │
│  │   )                                                               │ │
│  │   db.add(test_session)                                            │ │
│  │   db.commit()  ✅                                                  │ │
│  │                                                                    │ │
│  │ Step 2: Prepare monitoring config                                 │ │
│  │   video_timing_config = {                                         │ │
│  │     'test_session_id': test_session_id,  ✅ PRIMARY ID            │ │
│  │     'video_id': video_ids[0],                                     │ │
│  │     'sequence_id': sequence_id,                                   │ │
│  │     'use_stream_mode': False  # Polling                           │ │
│  │   }                                                               │ │
│  │                                                                    │ │
│  │ Step 3: Start monitoring                                          │ │
│  │   await start_hil_monitoring(video_timing_config)                 │ │
│  └────────────────────────┬──────────────────────────────────────────┘ │
└───────────────────────────┼────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               Monitor Wrapper (Correct Behavior)                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ services/dedicated_labjack_monitor.py:start_hil_monitoring()      │ │
│  │                                                                    │ │
│  │ # Extract PRIMARY session ID from config                          │ │
│  │ primary_session_id = config.get('test_session_id')                │ │
│  │ # Returns: 028afcb1... ✅                                          │ │
│  │                                                                    │ │
│  │ # Validate session ID exists                                      │ │
│  │ if not primary_session_id:                                        │ │
│  │     raise ValueError("test_session_id required")                  │ │
│  │                                                                    │ │
│  │ # Call monitor with PRIMARY session ID                            │ │
│  │ return await monitor.start_monitoring_with_video_sync(            │ │
│  │     primary_session_id,  # 028afcb1... ✅                          │ │
│  │     video_timing_config                                           │ │
│  │ )                                                                 │ │
│  └────────────────────────┬──────────────────────────────────────────┘ │
└───────────────────────────┼────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│          Monitor Core (Creates Session 1 - Correct)                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ DedicatedLabJackMonitor.start_monitoring_with_video_sync()        │ │
│  │                                                                    │ │
│  │ session_id = 028afcb1... (from parameter) ✅                       │ │
│  │                                                                    │ │
│  │ # Initialize session entry                                        │ │
│  │ self.active_sessions[session_id] = {                              │ │
│  │   'video_timing_config': video_timing_config,                     │ │
│  │   'started_at': datetime.now(),                                   │ │
│  │   'video_start_time': 1764082088.275,  # From video player        │ │
│  │   'detection_callback': callback_1,                               │ │
│  │   'labjack_config': {                                             │ │
│  │     'use_stream_mode': False  # Polling ✅                         │ │
│  │   }                                                               │ │
│  │ }                                                                 │ │
│  │                                                                    │ │
│  │ # Register detection callback                                     │ │
│  │ callback_1 = lambda e: handle_detection(028afcb1..., e)           │ │
│  │ labjack_monitor.add_detection_callback(callback_1) ✅              │ │
│  │ # Total callbacks: 1 ✅                                            │ │
│  │                                                                    │ │
│  │ return True                                                       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

                            ⚠️⚠️⚠️ BUG OCCURS HERE ⚠️⚠️⚠️

┌─────────────────────────────────────────────────────────────────────────┐
│           UNKNOWN PATH (Creates Session 2 - BUG)                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ ❓ Mystery Caller (Not Yet Identified)                             │ │
│  │                                                                    │ │
│  │ Possible sources:                                                 │ │
│  │  • WebSocket handler (websocket_orchestration.py)                 │ │
│  │  • Background worker thread                                       │ │
│  │  • LabJack service manager                                        │ │
│  │  • Windows bridge (windows_labjack_bridge.py)                     │ │
│  │  • Video lifecycle orchestrator                                   │ │
│  │  • Health check / recovery process                                │ │
│  │                                                                    │ │
│  │ Calls:                                                            │ │
│  │   monitor.start_monitoring_with_video_sync(                       │ │
│  │     "90fb1ae4...",  # ❌ NEW SESSION ID (not in database)         │ │
│  │     different_config  # Stream mode instead of polling            │ │
│  │   )                                                               │ │
│  └────────────────────────┬──────────────────────────────────────────┘ │
└───────────────────────────┼────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│          Monitor Core (Creates Session 2 - BUG)                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ DedicatedLabJackMonitor.start_monitoring_with_video_sync()        │ │
│  │                                                                    │ │
│  │ session_id = 90fb1ae4... (from parameter) ❌ PHANTOM SESSION       │ │
│  │                                                                    │ │
│  │ # No guards - accepts duplicate session                           │ │
│  │ # No validation - session not in database                         │ │
│  │                                                                    │ │
│  │ # Initialize SECOND session entry                                 │ │
│  │ self.active_sessions[session_id] = {  # ❌ DUPLICATE               │ │
│  │   'video_timing_config': different_config,                        │ │
│  │   'started_at': datetime.now(),  # Different time!                │ │
│  │   'video_start_time': 1764082088.494,  # 219ms drift! ❌           │ │
│  │   'detection_callback': callback_2,  # ❌ SECOND CALLBACK          │ │
│  │   'labjack_config': {                                             │ │
│  │     'use_stream_mode': True  # Stream ❌ CONFLICTS with polling    │ │
│  │   }                                                               │ │
│  │ }                                                                 │ │
│  │                                                                    │ │
│  │ # Register SECOND detection callback                              │ │
│  │ callback_2 = lambda e: handle_detection(90fb1ae4..., e)           │ │
│  │ labjack_monitor.add_detection_callback(callback_2) ❌              │ │
│  │ # Total callbacks: 2 ❌ DUPLICATE!                                 │ │
│  │                                                                    │ │
│  │ return True  # ❌ Should have returned False                       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

                        ⚠️ SYSTEM NOW IN BROKEN STATE ⚠️

┌─────────────────────────────────────────────────────────────────────────┐
│                  Hardware Layer (Confused State)                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ LabJack U3 Hardware                                               │ │
│  │                                                                    │ │
│  │ Configured by: Both sessions (conflict!)                          │ │
│  │                                                                    │ │
│  │ Session 028afcb1... wants: Polling mode, 200 Hz                   │ │
│  │ Session 90fb1ae4... wants: Stream mode, 500 Hz                    │ │
│  │                                                                    │ │
│  │ Result: Hardware mode oscillates ❌                                │ │
│  │   - Unreliable timing                                             │ │
│  │   - Missed detections                                             │ │
│  │   - Inconsistent sample rates                                     │ │
│  │                                                                    │ │
│  │ When voltage spike detected on AIN0:                              │ │
│  │   ┌─────────────────────────────────────────┐                    │ │
│  │   │ Detection Event at t=5.234s              │                    │ │
│  │   └──────────┬──────────────────────┬────────┘                    │ │
│  │              │                      │                              │ │
│  │              ▼                      ▼                              │ │
│  │        callback_1()            callback_2()                        │ │
│  │        ❌ DUPLICATE PROCESSING ❌                                   │ │
│  │                                                                    │ │
│  │   Both callbacks fire for SAME detection!                         │ │
│  │   - callback_1 assigns to session 028afcb1...                     │ │
│  │   - callback_2 assigns to session 90fb1ae4...                     │ │
│  │                                                                    │ │
│  │   Database now has 2 DetectionEvent records for 1 actual event!   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Impact of Duplicate Sessions

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Problem Cascade                                 │
└─────────────────────────────────────────────────────────────────────────┘

1. DATA INTEGRITY
   ┌──────────────────────────────────────────────────────────────┐
   │ Single Detection → Stored Twice                              │
   │                                                               │
   │ detection_events table:                                       │
   │   ├─ Record 1: session_id = 028afcb1..., timestamp = 5.234   │
   │   └─ Record 2: session_id = 90fb1ae4..., timestamp = 5.453   │
   │                                                               │
   │ Result:                                                       │
   │  • Inflated detection counts (2x actual)                      │
   │  • Timing inconsistencies (219ms drift)                       │
   │  • Confusing results analysis                                 │
   └──────────────────────────────────────────────────────────────┘

2. HARDWARE RELIABILITY
   ┌──────────────────────────────────────────────────────────────┐
   │ LabJack U3 Reconfigured Continuously                          │
   │                                                               │
   │ Timeline:                                                     │
   │ T+0ms:  Session 1 sets polling mode                           │
   │ T+50ms: Session 2 sets stream mode  ← CONFLICT                │
   │ T+100ms: Hardware confused, drops samples                     │
   │                                                               │
   │ Result:                                                       │
   │  • Missed detections                                          │
   │  • Unreliable timing                                          │
   │  • Hardware errors                                            │
   └──────────────────────────────────────────────────────────────┘

3. RESOURCE CONTENTION
   ┌──────────────────────────────────────────────────────────────┐
   │ Two Sessions Competing for Same Resources                     │
   │                                                               │
   │ Contention points:                                            │
   │  • LabJack USB connection                                     │
   │  • Detection callbacks                                        │
   │  • Database connections                                       │
   │  • WebSocket bandwidth                                        │
   │                                                               │
   │ Result:                                                       │
   │  • Race conditions                                            │
   │  • Performance degradation                                    │
   │  • Unpredictable behavior                                     │
   └──────────────────────────────────────────────────────────────┘

4. SYSTEM CORRECTNESS
   ┌──────────────────────────────────────────────────────────────┐
   │ Fundamental Assumption Violated                               │
   │                                                               │
   │ Assumption: 1 test = 1 session = 1 video                      │
   │ Reality: 1 test = 2 sessions = 1 video (shared)               │
   │                                                               │
   │ This breaks:                                                  │
   │  • Session lifecycle management                               │
   │  • Result aggregation logic                                   │
   │  • Report generation                                          │
   │  • Test validation                                            │
   │                                                               │
   │ Result:                                                       │
   │  • Invalid test results                                       │
   │  • Cannot trust system output                                 │
   │  • Manual data cleanup required                               │
   └──────────────────────────────────────────────────────────────┘
```

## Proposed Architecture (With Fix)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  Session Registry (New Component)                        │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ SessionRegistry (Singleton)                                       │ │
│  │                                                                    │ │
│  │ Purpose: Prevent duplicate sessions                               │ │
│  │                                                                    │ │
│  │ Data Structures:                                                  │ │
│  │   _sessions: Dict[session_id, SessionInfo]                        │ │
│  │   _video_to_session: Dict[video_id, session_id]                   │ │
│  │                                                                    │ │
│  │ Key Methods:                                                      │ │
│  │   register_session(session_id, video_id, config)                  │ │
│  │     → Checks _video_to_session                                    │ │
│  │     → Raises DuplicateSessionError if video already monitored     │ │
│  │     → Returns True if registration successful                     │ │
│  │                                                                    │ │
│  │   unregister_session(session_id)                                  │ │
│  │     → Removes from both dicts                                     │ │
│  │     → Allows new session for video                                │ │
│  │                                                                    │ │
│  │   get_video_session(video_id) → Optional[session_id]              │ │
│  │     → Returns existing session for video                          │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│          Monitor Core (With Guards)                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ DedicatedLabJackMonitor.start_monitoring_with_video_sync()        │ │
│  │                                                                    │ │
│  │ GUARD 1: Check if session already initialized                     │ │
│  │   if session_id in self.active_sessions:                          │ │
│  │       logger.warning("Session already exists")                    │ │
│  │       return False  # Idempotent                                  │ │
│  │                                                                    │ │
│  │ GUARD 2: Validate session exists in database                      │ │
│  │   session_db = db.query(TestSession).filter(                      │ │
│  │       TestSession.id == session_id                                │ │
│  │   ).first()                                                       │ │
│  │   if not session_db:                                              │ │
│  │       logger.error("Session not in database")                     │ │
│  │       return False                                                │ │
│  │                                                                    │ │
│  │ GUARD 3: Register with session registry                           │ │
│  │   try:                                                            │ │
│  │       session_registry.register_session(                          │ │
│  │           session_id, video_id, config                            │ │
│  │       )                                                           │ │
│  │   except DuplicateSessionError as e:                              │ │
│  │       logger.error(f"Video already monitored: {e}")               │ │
│  │       return False  # ✅ BLOCKS DUPLICATE!                         │ │
│  │                                                                    │ │
│  │ # All guards passed - create session                              │ │
│  │ self.active_sessions[session_id] = {...}                          │ │
│  │ labjack_monitor.add_detection_callback(callback)                  │ │
│  │                                                                    │ │
│  │ return True                                                       │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│          Mystery Caller (Blocked by Guards)                              │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │ ❓ Unknown component tries to create Session 2                     │ │
│  │                                                                    │ │
│  │ Calls:                                                            │ │
│  │   monitor.start_monitoring_with_video_sync(                       │ │
│  │     "90fb1ae4...",  # New session ID                              │ │
│  │     different_config                                              │ │
│  │   )                                                               │ │
│  │                                                                    │ │
│  │ Guard 3 triggers:                                                 │ │
│  │   session_registry.register_session() called                      │ │
│  │   → Checks _video_to_session[video_id]                            │ │
│  │   → Finds existing session: 028afcb1...                           │ │
│  │   → Raises DuplicateSessionError ✅                                │ │
│  │                                                                    │ │
│  │ Result:                                                           │ │
│  │   logger.error("Video already monitored by session 028afcb1...")  │ │
│  │   return False  # ✅ DUPLICATE BLOCKED!                            │ │
│  │                                                                    │ │
│  │ Session 2 NEVER CREATED ✅                                         │ │
│  │ Only ONE session exists ✅                                         │ │
│  │ Only ONE detection callback ✅                                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘

Result: System maintains ONE session per test execution ✅
        Hardware operates in single mode ✅
        Detections processed once ✅
        Data integrity preserved ✅
```

## Investigation Tools

### 1. Call Stack Logging

```python
# Add to start_monitoring_with_video_sync():

import traceback

logger.info("📞 start_monitoring_with_video_sync() called")
logger.info(f"   Session ID: {session_id}")
logger.info(f"   Video ID: {video_timing_config.get('video_id')}")
logger.info(f"   Call stack (last 5 frames):")
for line in traceback.format_stack()[-5:]:
    logger.info(f"      {line.strip()}")
```

### 2. Session Creation Monitor

```python
# Run in separate terminal:

python backend/scripts/find_duplicate_sessions.py

# Output will show:
# 🆕 NEW SESSION: 028afcb1... (PRIMARY)
# 🆕 NEW SESSION: 90fb1ae4... (PHANTOM) ← Identify this caller!
# 🚨 DUPLICATE SESSION DETECTED!
```

### 3. Metrics Dashboard

```
Active Sessions:  ▁▂▃▄▅▆▇█ 2 ❌ (should be 1)
Callbacks:        ▁▂▃▄▅▆▇█ 2 ❌ (should be 1)
Duplicate Blocks: ▁▁▁▁▁▁▁█ 0 (will be > 0 after fix)
Hardware Mode:    Polling → Stream → Polling ❌ (should be constant)
```

## Summary

**Current State:**
- ❌ Two sessions created per test
- ❌ Two detection callbacks registered
- ❌ Hardware mode conflicts
- ❌ Duplicate data in database

**After Fix:**
- ✅ One session per test
- ✅ One detection callback
- ✅ Consistent hardware mode
- ✅ Clean data

**Key Files:**
- `/backend/services/dedicated_labjack_monitor.py` - Add guards
- `/backend/services/session_registry.py` - New file
- `/backend/routers/video_sequence_testing.py` - Already correct
- `/backend/scripts/find_duplicate_sessions.py` - Investigation tool
