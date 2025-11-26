# Visual Diagram: Health Monitor Premature Start

## The Contradiction

```
┌─────────────────────────────────────────────────────────────────┐
│                    APPLICATION STARTUP                           │
│                     (main.py)                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Line 465: "HIL monitoring will be started per-test as needed"  │
│  ✅ Monitoring service auto-start DISABLED                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                        [760 lines of code]
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Line 1230: initialize_hardware_service(force_wsl_connection=T) │
│  ❌ AUTO-CONNECT AND START MONITORING IMMEDIATELY               │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Call Chain

```
main.py:1230
initialize_hardware_service(force_wsl_connection=True)
    │
    ├─► labjack_hardware_service.py:978
    │   get_labjack_hardware_service(config)
    │   │
    │   └─► Creates singleton instance
    │       LabJackHardwareService.__init__()
    │       • Sets health_check_active = False
    │       • Sets should_be_connected = False
    │       • Device handle = None
    │
    ├─► labjack_hardware_service.py:979
    │   service.detect_devices()
    │   │
    │   └─► Scans for LabJack devices
    │       • Found: T7 device on USB
    │
    └─► labjack_hardware_service.py:984
        service.connect(device_type="T7", connection_type="USB", ...)
        │
        ├─► labjack_hardware_service.py:358
        │   ljm.openS(device_type, connection_type, identifier)
        │   • Opens device handle
        │   • Connection succeeds initially
        │
        ├─► labjack_hardware_service.py:421
        │   self.should_be_connected = True
        │   • Marks device as intentionally connected
        │
        └─► labjack_hardware_service.py:424
            self._start_health_monitoring()
            │
            └─► labjack_hardware_service.py:742
                • Creates health monitor thread
                • Thread starts with 30-second interval
                • self.health_check_active = True
                │
                └─► [28 seconds later]
                    labjack_hardware_service.py:758
                    • First health check attempt
                    • read_single_voltage("AIN0")
                    • ❌ FAILS: DEVICE_NOT_OPEN (error 1224)
```

---

## Two Services Conflict

```
┌───────────────────────────────────────────────────────────────────┐
│                        MAIN.PY STARTUP                            │
└───────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│  NEW SERVICE (Per-Test)   │   │  LEGACY SERVICE (Auto)    │
│  real_labjack_service.py  │   │  labjack_hardware_service │
├───────────────────────────┤   ├───────────────────────────┤
│ Line: main.py:1213        │   │ Line: main.py:1230        │
│ Mode: auto_connect=FALSE  │   │ Mode: force_wsl=TRUE      │
│ Status: ✅ Working        │   │ Status: ❌ Auto-connects  │
│                           │   │                           │
│ Behavior:                 │   │ Behavior:                 │
│ • Lazy initialization     │   │ • Immediate connection    │
│ • No auto-connect         │   │ • Auto-start health mon.  │
│ • Connect only per-test   │   │ • Conflicts with new svc  │
│ • Proper per-test arch.   │   │ • Violates per-test mode  │
└───────────────────────────┘   └───────────────────────────┘
            ✅                              ❌
     Works as intended              Causes the bug
```

---

## Timeline Visualization

```
Time     | Event                              | Status
---------|------------------------------------|---------
09:29:07 | App starts                         | 🟢
09:29:07 | Log: "per-test mode"               | 🟢 (misleading)
09:29:07 | initialize_hardware_service()      | 🟡
09:29:07 | detect_devices() - found T7        | 🟡
09:29:07 | connect() - success                | 🟢
09:29:07 | _start_health_monitoring()         | 🟡 (shouldn't start)
09:29:07 | Health thread created              | 🟡
09:29:07 | Thread sleeps 30 seconds           | 🟡
09:29:35 | [28 seconds later]                 | ⏰
09:29:35 | First health check attempt         | 🔴
09:29:35 | read_single_voltage("AIN0")        | 🔴
09:29:35 | ERROR: DEVICE_NOT_OPEN             | 🔴
09:29:35 | WARNING: Health check failed (1/10)| 🔴
```

---

## Why Device Becomes Unavailable

```
Connection Timeline:

┌──────────────────────────────────────────────────────────┐
│  09:29:07 - ljm.openS() succeeds                         │
│  • Creates LJM handle                                    │
│  • Device appears available                              │
│  • Handle validated successfully                         │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
         [Unknown event occurs in 28 seconds]
         Possible causes:
         • USB stub implementation issue
         • Device power issue
         • Handle becomes stale
         • Conflict with other service
         • WSL USB passthrough instability
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  09:29:35 - ljm.eReadName() fails                        │
│  • Error 1224: LJME_DEVICE_NOT_OPEN                      │
│  • Handle is no longer valid                             │
│  • Device disconnected or not accessible                 │
└──────────────────────────────────────────────────────────┘
```

---

## The Fix (Visual)

### BEFORE (Current - Broken):
```
startup
  │
  ├─► Log: "per-test mode"
  │
  └─► initialize_hardware_service(force_wsl_connection=True)
      │
      └─► Auto-connects to device ❌
          │
          └─► Starts health monitor ❌
              │
              └─► Health check fails 28s later ❌
```

### AFTER (Fixed):
```
startup
  │
  ├─► Log: "per-test mode"
  │
  └─► initialize_hardware_service(auto_connect=False) ✅
      │
      └─► Creates service but doesn't connect ✅
          │
          └─► Health monitor NOT started ✅

[Later, during test session creation]

test_session_start
  │
  └─► service.connect() ✅
      │
      └─► Starts health monitor ✅
          │
          └─► Health check succeeds ✅
```

---

## Environment Variable Solution

```
┌──────────────────────────────────────────────────────────┐
│  .env file                                               │
├──────────────────────────────────────────────────────────┤
│  DISABLE_LEGACY_LABJACK_HARDWARE=true                    │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  main.py:1222                                            │
├──────────────────────────────────────────────────────────┤
│  disable_legacy_hardware = os.getenv(...)                │
│  if not disable_legacy_hardware:  # Skips this block!   │
│      # Legacy service initialization not executed        │
└──────────────────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│  Result: Only new per-test service runs ✅               │
│  • No auto-connection at startup                         │
│  • No premature health monitoring                        │
│  • No conflicting services                               │
└──────────────────────────────────────────────────────────┘
```

---

## Code Location Reference

### Key Files:
1. **main.py**
   - Line 465: "per-test" log message
   - Line 1213: New service init (working)
   - Line 1230: Legacy service init (broken)

2. **labjack_hardware_service.py**
   - Line 424: Health monitor auto-start (bug location)
   - Line 742: Health thread creation
   - Line 758: Health check that fails
   - Line 978: Singleton getter
   - Line 984: Auto-connect call

### Critical Code Sections:
```python
# labjack_hardware_service.py:424 (THE BUG)
def connect(self, ...):
    # ... connection code ...
    self.should_be_connected = True
    self._start_health_monitoring()  # ❌ Should be conditional
    # ... rest of code ...

# Recommended fix:
def connect(self, ...):
    # ... connection code ...
    self.should_be_connected = True
    # Only start health monitoring if not in per-test mode
    if getattr(self, 'auto_start_health', True):
        self._start_health_monitoring()
    # ... rest of code ...
```

---

## Summary

```
┌─────────────────────────────────────────────────────────────┐
│                      ROOT CAUSE                             │
├─────────────────────────────────────────────────────────────┤
│  Legacy hardware service contradicts "per-test" mode by:    │
│  1. Auto-connecting to device at startup                    │
│  2. Auto-starting health monitor at connection              │
│  3. Health monitor fails when device becomes unavailable    │
├─────────────────────────────────────────────────────────────┤
│                      THE FIX                                │
├─────────────────────────────────────────────────────────────┤
│  Option A: export DISABLE_LEGACY_LABJACK_HARDWARE=true      │
│  Option B: Add auto_connect=False parameter                 │
│  Option C: Conditional health monitor start                 │
└─────────────────────────────────────────────────────────────┘
```
