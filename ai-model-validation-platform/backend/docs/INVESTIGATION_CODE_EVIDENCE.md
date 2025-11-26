# Code Evidence: Health Monitor Premature Start

**Investigation Date:** 2025-11-19
**Root Cause:** Legacy hardware service auto-connects at startup despite "per-test mode"

---

## Evidence 1: The Misleading Log Message

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Lines:** 459-465

```python
# Start LabJack monitoring service automatically
# ✅ CRITICAL FIX: Auto-start monitoring service DISABLED
# This service was creating duplicate "HIL Test" sessions with different IDs,
# causing detection events to be stored in the wrong session.
# HIL monitoring should ONLY be started per-test via dedicated_labjack_monitor.py
logger.info("ℹ️ Standalone LabJack monitoring service auto-start DISABLED")
logger.info("ℹ️ HIL monitoring will be started per-test as needed")
```

**Analysis:**
- Comments state monitoring should ONLY be started per-test
- Log message says "per-test as needed"
- This is **TRUE** for the standalone monitoring service
- BUT legacy hardware service contradicts this 760 lines later

---

## Evidence 2: The New Service (Working Correctly)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Lines:** 1209-1219

```python
# Initialize real LabJack hardware service (lazy initialization - no connection)
from services.real_labjack_service import initialize_real_labjack_service
try:
    # Initialize without auto-connection to prevent device claiming during startup
    labjack_initialized = initialize_real_labjack_service(auto_connect=False)
    if labjack_initialized:
        logger.info("✅ Real LabJack hardware service initialized (lazy connection)")
    else:
        logger.warning("⚠️ LabJack hardware service initialization failed")
except Exception as e:
    logger.warning(f"⚠️ LabJack hardware service error: {e}")
```

**Analysis:**
- Uses `auto_connect=False` parameter
- Logs "lazy connection"
- Works as intended for per-test architecture

---

## Evidence 3: The Legacy Service (THE BUG)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Lines:** 1221-1234

```python
# Initialize COMPREHENSIVE LabJack hardware services - CRITICAL P0 FUNCTIONALITY
disable_legacy_hardware = os.getenv("DISABLE_LEGACY_LABJACK_HARDWARE", "").lower() in ("1", "true", "yes")
if not disable_legacy_hardware:
    try:
        from services.labjack_hardware_service import initialize_hardware_service
        from services.video_hardware_sync_service import get_video_hardware_sync_service
        from services.labjack_error_handler import get_error_handler_service

        # Initialize core hardware service - override WSL check since USB passthrough is working
        hardware_initialized = initialize_hardware_service(force_wsl_connection=True)
        if hardware_initialized:
            logger.info("✅ CRITICAL: LabJack hardware service fully initialized")
        else:
            logger.warning("⚠️ LabJack hardware service initialized in fallback mode")
```

**Analysis:**
- ❌ Uses `force_wsl_connection=True` (auto-connects)
- ❌ No `auto_connect=False` parameter
- ❌ Comment says "override WSL check" (forcing connection)
- ❌ Logs "fully initialized" (implies connection succeeded)

---

## Evidence 4: The Auto-Connect Function

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 967-999

```python
def initialize_hardware_service(config: Optional[LabJackConfig] = None, force_wsl_connection: bool = False) -> bool:
    """Initialize LabJack hardware service and attempt connection"""
    try:
        # Check for WSL environment - but allow override if USB passthrough is working
        import platform
        is_wsl = platform.system() == "Linux" and "microsoft" in platform.uname().release.lower()
        if is_wsl and not force_wsl_connection:
            logger.warning("⚠️ WSL environment detected - skipping direct LabJack LJM initialization")
            logger.info("💡 To override this check (if USB passthrough is working), set force_wsl_connection=True")
            return False

        # Line 978: Get or create singleton
        service = get_labjack_hardware_service(config)

        # Line 979: Detect devices
        devices = service.detect_devices()

        if devices:
            # ❌ BUG: Automatically connects to first available device
            device = devices[0]
            success = service.connect(
                device_type=device["device_type"],
                connection_type=device["connection_type"],
                identifier=str(device["serial_number"])
            )

            if success:
                logger.info(f"✅ LabJack hardware service initialized and connected to {device['device_type']}")
                return True

        logger.warning("⚠️ No LabJack devices detected for connection")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to initialize LabJack hardware service: {e}")
        return False
```

**Analysis:**
- ❌ Function name says "initialize" but actually **CONNECTS**
- ❌ No parameter to disable auto-connection
- ❌ Always connects if device found (lines 982-988)
- ❌ No respect for per-test mode

---

## Evidence 5: The Connect Method (Health Monitor Start)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 334-456 (focusing on 417-424)

```python
def connect(self, device_type: str = "ANY", connection_type: str = "ANY", identifier: str = "ANY") -> bool:
    """Connect to LabJack hardware device"""
    with self.lock:
        if self.is_connected():
            logger.warning("⚠️ Already connected to LabJack")
            return True

        self.connection_status = HardwareConnectionStatus.CONNECTING
        self.statistics["connection_attempts"] += 1

        try:
            logger.info(f"🔌 Attempting to connect to LabJack {device_type} via {connection_type}...")

            # Open device connection
            self.handle = ljm.openS(device_type, connection_type, identifier)

            # Validate handle is actually valid
            time.sleep(0.1)
            try:
                ljm.getHandleInfo(self.handle)
                logger.info(f"✅ Connected to LabJack: {device_type} via {connection_type}, handle validated")
            except Exception as validate_error:
                logger.error(f"❌ Handle validation failed: {validate_error}")
                # ... error handling ...
                return False

            # ... Get device info, configure channels (lines 375-415) ...

            # Set connection state
            self.connection_status = HardwareConnectionStatus.CONNECTED
            self.connected_at = datetime.now()
            self.statistics["successful_connections"] += 1
            self.should_be_connected = True  # Mark as intentionally connected

            # ❌ BUG: Unconditionally starts health monitoring
            self._start_health_monitoring()

            logger.info(f"✅ Connected to {device_type_str} S/N:{serial_number} via {connection_type_str}")
            return True
```

**Analysis:**
- Line 421: Sets `should_be_connected = True`
- Line 424: ❌ **UNCONDITIONALLY** starts health monitoring
- No check for per-test mode
- No option to defer health monitoring

---

## Evidence 6: Health Monitor Thread Start

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 733-748

```python
def _start_health_monitoring(self):
    """Start health monitoring thread"""
    # Check if thread already running
    if self.health_thread and self.health_thread.is_alive():
        return

    # Check if device connected
    if not self.is_connected():
        logger.debug("Skipping health monitor start - hardware not connected")
        return

    # ❌ NO CHECK FOR PER-TEST MODE HERE
    # Missing: if not self.should_be_connected: return

    # Start health monitoring thread
    self.health_check_active = True
    self.health_thread = threading.Thread(
        target=self._health_monitoring_loop,
        daemon=True,
        name="LabJackHealthMonitor"
    )
    self.health_thread.start()
    logger.debug("🩺 Health monitoring started")
```

**Analysis:**
- ❌ Checks if device is connected (which it is at startup)
- ❌ **MISSING:** Check for per-test mode
- ❌ **MISSING:** Check for `auto_start_health` flag
- Starts health thread immediately

---

## Evidence 7: Health Monitor Loop (Where It Fails)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 750-791

```python
def _health_monitoring_loop(self):
    """Health monitoring loop with proper thread safety"""
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        try:
            # ❌ This is where it fails 28 seconds after startup
            test_voltage = self.read_single_voltage("AIN0")
            consecutive_failures = 0
            logger.debug(f"✅ Health check passed: AIN0={test_voltage:.3f}V")

        except RuntimeError as e:
            # Device not connected - expected during disconnection
            if "not connected" in str(e).lower():
                logger.debug("Health monitor exiting - device disconnected")
                break
            consecutive_failures += 1
            logger.warning(f"⚠️ Health check failed (attempt {consecutive_failures}/{max_consecutive_failures}): {e}")

        except Exception as e:
            consecutive_failures += 1
            logger.warning(f"⚠️ Health check failed (attempt {consecutive_failures}/{max_consecutive_failures}): {e}")

            # ❌ Error 1224: DEVICE_NOT_OPEN (LJM handle closed)
            error_code = getattr(e, "errorCode", None)
            if error_code == 1224:
                logger.warning("🔌 LabJack handle closed (LJME_DEVICE_NOT_OPEN); pausing health monitor until next connection")
                break

            if consecutive_failures >= max_consecutive_failures:
                logger.error(f"❌ Health check failed {consecutive_failures} consecutive times")
                self.connection_status = HardwareConnectionStatus.ERROR
                break

        # Sleep 30 seconds between checks (5 seconds if failures)
        time.sleep(5 if consecutive_failures > 0 else 30)

    self.health_check_active = False
    logger.debug("🩺 Health monitoring stopped")
```

**Analysis:**
- Line 758: First health check 28-30 seconds after thread start
- Line 758: `read_single_voltage("AIN0")` raises exception
- Line 774: Error code 1224 = LJME_DEVICE_NOT_OPEN
- Device handle became invalid between connection (09:29:07) and first check (09:29:35)

---

## Evidence 8: Actual Log Output

```
09:29:07 - INFO - Application startup completed successfully
09:29:07 - INFO - ℹ️ HIL monitoring will be started per-test as needed
09:29:07 - INFO - 🔧 LabJack Hardware Service initialized (USB_STUB)
09:29:07 - INFO - ✅ Connected to LabJack: T7 via USB, handle validated
09:29:07 - DEBUG - 🩺 Health monitoring started
09:29:35 - ERROR - Failed to read AIN0: DEVICE_NOT_OPEN
09:29:35 - WARNING - ⚠️ Health check failed (attempt 1/10)
```

**Analysis:**
1. **09:29:07:** Log says "per-test mode"
2. **09:29:07:** Service initialized and **CONNECTED** (contradicting per-test)
3. **09:29:07:** Health monitoring **STARTED** (contradicting per-test)
4. **09:29:35:** Health check fails (device unavailable)

---

## Evidence 9: The __init__ Method (Doesn't Start Monitoring)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 172-218

```python
def __init__(self, config: Optional[LabJackConfig] = None):
    if not LJM_AVAILABLE:
        raise RuntimeError("CRITICAL: LabJack LJM library not available.")

    self.config = config or (load_config_from_env() if load_config_from_env else None)

    # Hardware state
    self.handle: Optional[int] = None
    self.connection_status = HardwareConnectionStatus.NOT_DETECTED
    self.device_info: Optional[DeviceInfo] = None
    self.connected_at: Optional[datetime] = None

    # Channel configuration
    self.channels: Dict[str, ChannelConfiguration] = {}
    self._configure_default_channels()

    # Signal monitoring
    self.monitoring_active = False
    self.monitoring_thread: Optional[threading.Thread] = None
    self.stop_monitoring = threading.Event()
    self.hardware_events = queue.Queue(maxsize=50000)
    self.event_callbacks: List[Callable[[HardwareEvent], None]] = []

    # Statistics
    self.statistics = {
        "connection_attempts": 0,
        "successful_connections": 0,
        "total_signals_detected": 0,
        "last_signal_time": None,
        "monitoring_duration_seconds": 0.0,
        "errors_count": 0,
        "last_error": None,
        "ljm_type": LJM_TYPE
    }

    # Thread safety
    self.lock = threading.RLock()

    # Health monitoring
    self.health_thread: Optional[threading.Thread] = None
    self.health_check_active = False
    self.should_be_connected = False  # ✅ Initialized to False

    logger.info(f"🔧 LabJack Hardware Service initialized ({LJM_TYPE})")
```

**Analysis:**
- ✅ `__init__` does NOT start health monitoring
- ✅ `health_check_active = False` initially
- ✅ `should_be_connected = False` initially
- Health monitoring only starts in `connect()` method

---

## Evidence 10: The Singleton Pattern (Phase 1 Fix)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 889-946

```python
def get_labjack_hardware_service(
    config: Optional[LabJackConfig] = None,
    force_recreate: bool = False
) -> LabJackHardwareService:
    """
    Get thread-safe singleton instance of LabJack hardware service.
    """
    global _hardware_service, _initialized_config_hash

    with _singleton_lock:
        current_config_hash = _config_hash(config)

        # Check if we need to create new instance
        if _hardware_service is None or force_recreate:
            # Clean up existing instance if recreating
            if _hardware_service is not None and force_recreate:
                logger.info("Forcing recreation of hardware service")
                try:
                    _hardware_service.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting during forced recreation: {e}")
                _hardware_service = None

            # Create new instance
            try:
                logger.info("Creating new LabJack hardware service instance")
                _hardware_service = LabJackHardwareService(config)
                _initialized_config_hash = current_config_hash
                logger.info("LabJack hardware service instance created successfully")
            except Exception as e:
                _hardware_service = None
                _initialized_config_hash = None
                logger.error(f"Failed to create LabJack hardware service: {e}")
                raise RuntimeError(f"Failed to initialize LabJack hardware service: {e}")

        # Validate config hasn't changed
        elif current_config_hash != _initialized_config_hash:
            error_msg = (
                "Configuration mismatch: Singleton already exists with different config. "
                "Use force_recreate=True to replace existing instance or use reset_labjack_hardware_service()."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return _hardware_service
```

**Analysis:**
- ✅ Singleton pattern implemented correctly (Phase 1 fix)
- ✅ Creates instance without connecting
- ❌ But caller (`initialize_hardware_service()`) immediately connects after getting singleton

---

## Summary of Evidence

### The Bug Flow:

1. **main.py:465** - Logs "per-test mode" (misleading)
2. **main.py:1230** - Calls `initialize_hardware_service(force_wsl_connection=True)`
3. **labjack_hardware_service.py:978** - Gets singleton instance
4. **labjack_hardware_service.py:979** - Detects devices
5. **labjack_hardware_service.py:984** - ❌ Auto-connects to first device
6. **labjack_hardware_service.py:424** - ❌ Starts health monitoring
7. **labjack_hardware_service.py:747** - Health thread starts
8. **labjack_hardware_service.py:788** - Thread sleeps 30 seconds
9. **09:29:35 (28s later)** - Health check fails with DEVICE_NOT_OPEN

### The Missing Code:

**What's needed in `_start_health_monitoring()`:**
```python
def _start_health_monitoring(self):
    """Start health monitoring thread"""
    if self.health_thread and self.health_thread.is_alive():
        return
    if not self.is_connected():
        logger.debug("Skipping health monitor start - hardware not connected")
        return

    # ✅ ADD THIS CHECK:
    if not self.should_be_connected:
        logger.debug("Skipping health monitor start - per-test mode active")
        return

    self.health_check_active = True
    self.health_thread = threading.Thread(
        target=self._health_monitoring_loop,
        daemon=True,
        name="LabJackHealthMonitor"
    )
    self.health_thread.start()
    logger.debug("🩺 Health monitoring started")
```

---

## Conclusion

The evidence clearly shows:
1. Application logs "per-test mode" message
2. Legacy service contradicts this by auto-connecting
3. Connection triggers health monitoring unconditionally
4. Health monitor fails when device becomes unavailable
5. No code exists to respect per-test mode in legacy service

**This is a straightforward architectural violation, not a hardware issue.**
