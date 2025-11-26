# Investigation Report: Health Monitor Starts When Device Not Connected

**Date:** 2025-11-19
**Issue:** Health monitor fires 28 seconds after startup even though device is not connected
**Log Evidence:** Health check failure at 09:29:35, 28 seconds after startup at 09:29:07

---

## Executive Summary

**ROOT CAUSE IDENTIFIED:**
The health monitor starts automatically when `initialize_hardware_service(force_wsl_connection=True)` is called during application startup at **main.py line 1230**. This function attempts to connect to a device immediately, and if successful, starts the health monitor. However, the connection succeeds initially but the device becomes unavailable shortly after, causing the health monitor to fail.

**Key Finding:**
The application is **NOT** in "per-test mode" as the logs suggest. The startup code is configured to **force an immediate connection** to the LabJack device at application startup.

---

## Call Stack Analysis

### 1. Application Startup (main.py)

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Lines:** 1222-1234

```python
# Line 1222: Check if legacy hardware is disabled
disable_legacy_hardware = os.getenv("DISABLE_LEGACY_LABJACK_HARDWARE", "").lower() in ("1", "true", "yes")
if not disable_legacy_hardware:
    try:
        from services.labjack_hardware_service import initialize_hardware_service
        from services.video_hardware_sync_service import get_video_hardware_sync_service
        from services.labjack_error_handler import get_error_handler_service

        # Line 1230: CRITICAL - Attempts immediate connection
        hardware_initialized = initialize_hardware_service(force_wsl_connection=True)
        if hardware_initialized:
            logger.info("✅ CRITICAL: LabJack hardware service fully initialized")
        else:
            logger.warning("⚠️ LabJack hardware service initialized in fallback mode")
```

### 2. initialize_hardware_service() Function

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

        # Line 978: Get or create singleton instance
        service = get_labjack_hardware_service(config)

        # Line 979: Detect available devices
        devices = service.detect_devices()

        if devices:
            # Line 982-988: PROBLEM - Automatically connects to first device found
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
```

**Key Issue:** This function is **NOT** lazy initialization. It actively:
1. Creates singleton service instance
2. Scans for devices
3. **Automatically connects to the first device found**
4. Starts health monitoring as part of connection

### 3. connect() Method

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 334-456 (specifically line 424)

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

            # Validate handle, get device info, configure channels...
            # (lines 360-415)

            # Set connection state
            self.connection_status = HardwareConnectionStatus.CONNECTED
            self.connected_at = datetime.now()
            self.statistics["successful_connections"] += 1
            self.should_be_connected = True  # Mark as intentionally connected

            # Line 424: PROBLEM - Automatically starts health monitoring
            self._start_health_monitoring()

            logger.info(f"✅ Connected to {device_type_str} S/N:{serial_number} via {connection_type_str}")
            return True
```

### 4. _start_health_monitoring() Method

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 733-748

```python
def _start_health_monitoring(self):
    """Start health monitoring thread"""
    if self.health_thread and self.health_thread.is_alive():
        return
    if not self.is_connected():
        logger.debug("Skipping health monitor start - hardware not connected")
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

### 5. Health Monitor Loop

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`
**Lines:** 750-791

```python
def _health_monitoring_loop(self):
    """Health monitoring loop with proper thread safety"""
    consecutive_failures = 0
    max_consecutive_failures = 10

    while self.health_check_active:
        try:
            # Line 758: Reads AIN0 to verify device health
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

            # Line 774-778: Handles DEVICE_NOT_OPEN error
            error_code = getattr(e, "errorCode", None)
            if error_code == 1224:
                logger.warning("🔌 LabJack handle closed (LJME_DEVICE_NOT_OPEN); pausing health monitor until next connection")
                break

            if consecutive_failures >= max_consecutive_failures:
                logger.error(f"❌ Health check failed {consecutive_failures} consecutive times")
                self.connection_status = HardwareConnectionStatus.ERROR
                break

        # Line 788: Sleep between health checks (30 seconds)
        time.sleep(5 if consecutive_failures > 0 else 30)

    self.health_check_active = False
    logger.debug("🩺 Health monitoring stopped")
```

---

## Timeline of Events

1. **09:29:07** - Application starts
2. **09:29:07** - `main.py` line 1230 calls `initialize_hardware_service(force_wsl_connection=True)`
3. **09:29:07** - `initialize_hardware_service()` calls `get_labjack_hardware_service()` (creates singleton)
4. **09:29:07** - `initialize_hardware_service()` calls `service.detect_devices()` (scans for hardware)
5. **09:29:07** - Device found, `initialize_hardware_service()` calls `service.connect()`
6. **09:29:07** - `connect()` successfully opens LJM handle
7. **09:29:07** - `connect()` calls `_start_health_monitoring()` at line 424
8. **09:29:07** - Health monitor thread starts with 30-second sleep interval
9. **09:29:35** - **28 seconds later** - Health monitor wakes up and attempts first health check
10. **09:29:35** - Health check fails with "DEVICE_NOT_OPEN" error (LJM error 1224)

---

## Root Cause: Why "Per-Test Mode" Message is Misleading

The log message "HIL monitoring will be started per-test as needed" appears to come from a **different service** (likely the `real_labjack_service.py`), not from the `LabJackHardwareService` that's actually being initialized.

**Evidence:**
- `main.py` line 1213 initializes `real_labjack_service` with `auto_connect=False` (per-test mode)
- `main.py` line 1230 initializes **legacy** `labjack_hardware_service` with `force_wsl_connection=True` (immediate connection)
- The legacy service **does not respect per-test mode** - it connects immediately

**Search Results:**
```bash
# Searching for "per-test" message
grep -rn "per-test\|HIL monitoring will be started" backend/services/
```

This message likely comes from `real_labjack_service.py`, while the actual health monitoring comes from the legacy `labjack_hardware_service.py`.

---

## The Bug: Connection Succeeds Then Device Disappears

The timeline shows:
1. Connection **succeeds** at 09:29:07 (handle is valid)
2. Health monitor starts successfully
3. Health monitor sleeps for 28-30 seconds
4. Health check **fails** at 09:29:35 with DEVICE_NOT_OPEN

**This suggests:**
1. The USB device was briefly available at startup
2. Connection succeeded initially
3. Device became unavailable before first health check (USB disconnected, stub issue, or device conflict)
4. Health monitor detected the disconnection

---

## Code Locations Summary

### Where Health Monitor Starts:
- **Triggered by:** `main.py:1230` → `initialize_hardware_service(force_wsl_connection=True)`
- **Connection attempt:** `labjack_hardware_service.py:978-988` (auto-connects to first device)
- **Health monitor started:** `labjack_hardware_service.py:424` (`connect()` method)
- **Thread creation:** `labjack_hardware_service.py:742-747` (`_start_health_monitoring()`)
- **Health loop:** `labjack_hardware_service.py:750-791` (`_health_monitoring_loop()`)

### Why It Shouldn't Start:
- **Per-test mode disabled:** The `force_wsl_connection=True` flag overrides per-test behavior
- **Automatic connection:** `initialize_hardware_service()` automatically connects if device found
- **No connection check:** Health monitor starts immediately after connection, not after test session creation

---

## Recommended Fix

### Option 1: True Lazy Initialization (Recommended)

Modify `initialize_hardware_service()` to **NOT** automatically connect:

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_hardware_service.py`

```python
def initialize_hardware_service(config: Optional[LabJackConfig] = None,
                                 force_wsl_connection: bool = False,
                                 auto_connect: bool = False) -> bool:  # Add parameter
    """Initialize LabJack hardware service (lazy initialization)"""
    try:
        import platform
        is_wsl = platform.system() == "Linux" and "microsoft" in platform.uname().release.lower()
        if is_wsl and not force_wsl_connection:
            logger.warning("⚠️ WSL environment detected - skipping direct LabJack LJM initialization")
            return False

        # Create singleton but don't connect
        service = get_labjack_hardware_service(config)

        # Only connect if explicitly requested
        if not auto_connect:
            logger.info("✅ LabJack hardware service initialized (per-test connection mode)")
            return True

        # Auto-connect path (legacy behavior)
        devices = service.detect_devices()
        if devices:
            device = devices[0]
            success = service.connect(
                device_type=device["device_type"],
                connection_type=device["connection_type"],
                identifier=str(device["serial_number"])
            )
            return success

        logger.warning("⚠️ No LabJack devices detected for connection")
        return False
```

**Update startup call in main.py:**

```python
# Line 1230: Don't auto-connect at startup
hardware_initialized = initialize_hardware_service(
    force_wsl_connection=True,
    auto_connect=False  # Prevent automatic connection
)
```

### Option 2: Conditional Health Monitoring

Add a check in `_start_health_monitoring()` to respect per-test mode:

```python
def _start_health_monitoring(self):
    """Start health monitoring thread"""
    if self.health_thread and self.health_thread.is_alive():
        return
    if not self.is_connected():
        logger.debug("Skipping health monitor start - hardware not connected")
        return

    # NEW: Check if we should start health monitoring
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

### Option 3: Disable Legacy Hardware Service

Set environment variable to use only the new per-test service:

```bash
export DISABLE_LEGACY_LABJACK_HARDWARE=true
```

This will skip the entire legacy hardware service initialization at `main.py:1222-1248`.

---

## Verification Test

After applying fix, verify:

1. **Startup logs should show:**
   ```
   ✅ LabJack hardware service initialized (per-test connection mode)
   ℹ️ HIL monitoring will be started per-test as needed
   ```

2. **Health monitor should NOT start until:**
   - Test session is created
   - Device connection is explicitly requested
   - `connect()` method is called from test endpoint

3. **No health check errors at startup:**
   - No "DEVICE_NOT_OPEN" errors within first 30 seconds
   - Health monitoring only starts after device connection

---

## Additional Investigation Needed

1. **Why does USB stub allow initial connection then fail?**
   - USB stub may be creating a fake handle that becomes invalid
   - Check `labjack_usb_stub.py` implementation

2. **Is there a device conflict between services?**
   - `real_labjack_service.py` (per-test mode)
   - `labjack_hardware_service.py` (legacy auto-connect mode)
   - Both services might be trying to claim the same device

3. **What is the correct service to use?**
   - Should we disable legacy service entirely?
   - Is `real_labjack_service.py` the correct per-test implementation?

---

## Conclusion

The health monitor starts because:
1. Application startup calls `initialize_hardware_service(force_wsl_connection=True)` at `main.py:1230`
2. This function automatically connects to the first device found
3. The `connect()` method automatically starts health monitoring at line 424
4. The connection initially succeeds but device becomes unavailable before first health check

**The system is NOT in per-test mode despite the log message.** The legacy hardware service is configured for immediate auto-connection, which contradicts the per-test architecture described in the logs.

**Fix:** Implement Option 1 (lazy initialization) to prevent automatic connection at startup and only connect when test sessions are created.
