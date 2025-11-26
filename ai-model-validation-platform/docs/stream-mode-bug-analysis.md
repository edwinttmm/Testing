# LabJack Stream Mode Implementation Bug Analysis

## Executive Summary

The stream mode implementation in `labjack_detection_service.py` has **CRITICAL BUGS** that prevent it from functioning. The primary issue is **blocking asyncio event loop operations in a synchronous thread**, causing deadlocks and preventing stream data from being read.

---

## 🔴 CRITICAL BUG #1: Asyncio Event Loop Deadlock in Synchronous Thread

### Location
**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Function:** `_monitoring_loop_stream()`
**Lines:** 1227-1234, 1357-1362

### Root Cause
The `_monitoring_loop_stream()` function is called from a **standard threading.Thread** (line 463-470), which is **synchronous**. However, it attempts to use asyncio by creating new event loops and calling `run_until_complete()`:

```python
# Line 1227-1234 - BLOCKING IN SYNC THREAD
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
try:
    success = loop.run_until_complete(
        self.labjack_service.start_stream(channels, scan_rate)
    )
finally:
    loop.close()
```

### Why This Fails
1. **Thread Context Issue**: Creating event loops in daemon threads is problematic
2. **Blocking Behavior**: `run_until_complete()` blocks the entire thread
3. **Event Loop Cleanup**: The loop is closed immediately after use, preventing any background async operations
4. **No Error Recovery**: If `start_stream()` hangs or fails asynchronously, the thread blocks indefinitely

### Evidence from Code
```python
# Line 463-467 - Thread creation (SYNCHRONOUS)
monitor_thread = threading.Thread(
    target=target_func,  # _monitoring_loop_stream
    args=(session_id,),
    daemon=True,
    name=f"LabJackMonitor-{session_id}-{mode_label}"
)
```

The thread is **NOT** an asyncio task - it's a standard `threading.Thread` that cannot properly handle async operations.

---

## 🔴 CRITICAL BUG #2: Missing Stream Data Reading Implementation

### Location
**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Function:** `_monitoring_loop_stream()`
**Lines:** 1257-1276

### Root Cause
The stream mode attempts to read data using `get_stream_data()`, but this method relies on a **queue-based approach** that is never populated in DIRECT mode.

```python
# Line 1257 - BROKEN DATA RETRIEVAL
stream_data = self.labjack_service.get_stream_data(max_samples=scans_per_read * len(channels))

if not stream_data:
    time.sleep(0.01)  # Brief pause if no data
    continue
```

### Analysis of `get_stream_data()` Implementation

#### From `labjack_service.py` (Lines 1111-1148):
```python
def get_stream_data(self, max_samples: int = 1000) -> List[float]:
    """Get streaming data"""
    data = []

    # For HTTP bridge mode, poll the stream-read endpoint
    if self.mode == ConnectionMode.BRIDGE and hasattr(self, 'bridge_url'):
        # Works for BRIDGE mode
        response = requests.post(f"{self.bridge_url}/stream-read", ...)
        return data

    # For WebSocket or other modes, use the queue
    try:
        while samples_read < max_samples:
            try:
                batch = self.stream_data_queue.get_nowait()  # ❌ EMPTY FOR DIRECT MODE
                data.extend(batch)
                # ...
            except queue.Empty:
                break
    except Exception as e:
        logger.error(f"Error getting stream data: {e}")

    return data  # Returns empty list!
```

### Why `stream_data_queue` is Empty in DIRECT Mode

The queue is only populated in two scenarios:
1. **Bridge Mode**: HTTP/WebSocket responses push data to queue
2. **`_direct_stream_loop()` thread**: Should populate queue via `_handle_stream_data()`

#### The Missing Link (Lines 1034-1064):
```python
def _direct_stream_loop(self):
    """Direct streaming data acquisition loop"""
    # ...
    while not self._stop_streaming.is_set() and self.streaming:
        try:
            data, backlog, error = ljm.eStreamRead(self.direct_handle)  # ✅ Reads data
            if data:
                self._handle_stream_data(data)  # ✅ Should populate queue
            # ...
```

**However**, `_direct_stream_loop()` is started via `_start_direct_streaming()` (line 1009), which is **ONLY** called in `start_stream()` when mode is DIRECT.

### The Problem
The detection service's `_monitoring_loop_stream()` calls:
```python
success = loop.run_until_complete(
    self.labjack_service.start_stream(channels, scan_rate)
)
```

If successful, this:
1. Calls `configure_stream()` → `start_stream_mode()` → `ljm.eStreamStart()`
2. Sets `streaming = True`
3. Calls `_start_direct_streaming()` to start background thread

But then immediately closes the event loop:
```python
finally:
    loop.close()  # ❌ KILLS ANY ASYNC OPERATIONS
```

The `_direct_stream_loop()` thread may start, but the detection service doesn't properly wait for data to accumulate in the queue.

---

## 🔴 CRITICAL BUG #3: Incorrect Stream Configuration

### Location
**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_service.py`
**Function:** `start_stream_mode()`
**Lines:** 1340-1346

### Root Cause
The stream is configured with **FIXED** `scans_per_read` value that doesn't match the detection service's expectations.

```python
# Line 954 - In configure_stream()
scans_per_read = max(sample_rate // 10, 1)  # E.g., 1000 Hz → 100 scans

# Line 1340 - In start_stream_mode()
actual_scan_rate = ljm.eStreamStart(
    self.direct_handle,
    scans_per_read,  # 100 scans per read
    num_addresses,    # Number of channels
    addresses,
    scan_rate
)
```

But in detection service (line 1093):
```python
scans_per_read = 100  # Read 100 samples at a time
```

### The Mismatch
- **Detection service expects**: 100 **samples** (not scans)
- **Stream configured for**: 100 **scans** per read
- **With 2 channels**: Each scan = 2 samples, so 100 scans = 200 samples
- **Detection service tries to read**: `max_samples=scans_per_read * len(channels)` = 100 * 2 = 200 samples

This is actually correct by accident, but the variable naming is confusing and could lead to bugs with different channel counts.

---

## 🟡 MODERATE BUG #4: No Error Handling for Stream Initialization Failures

### Location
**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Lines:** 1236-1239

### Root Cause
When stream initialization fails, the code falls back to polling mode **but doesn't update the session configuration**.

```python
if not success:
    logger.error("Failed to start stream mode, falling back to polling")
    self._monitoring_loop(session_id)  # ❌ Recursion, no state cleanup
    return
```

### Problems
1. **Infinite Recursion Risk**: If `_monitoring_loop()` also tries stream mode, infinite recursion
2. **No Config Update**: The session still has `use_stream_mode=True` in config
3. **Lost Context**: The original thread's purpose (stream monitoring) is lost
4. **Resource Leak**: The original thread continues to exist, doing nothing

---

## 🟡 MODERATE BUG #5: Synchronous Blocking in Async Context

### Location
**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_service.py`
**Function:** `_direct_stream_loop()`
**Lines:** 1034-1064

### Root Cause
The `_direct_stream_loop()` calls `ljm.eStreamRead()` which is a **BLOCKING C library call**.

```python
def _direct_stream_loop(self):
    """Direct streaming data acquisition loop"""
    # ...
    while not self._stop_streaming.is_set() and self.streaming:
        try:
            data, backlog, error = ljm.eStreamRead(self.direct_handle)  # ❌ BLOCKS
            if data:
                self._handle_stream_data(data)
        # ...
        time.sleep(0.01)  # Small delay
```

### Why This Matters
- **Blocking C Call**: `ljm.eStreamRead()` blocks until data is available or timeout
- **GIL Contention**: Python's Global Interpreter Lock prevents true parallelism
- **No Timeout Control**: The LJM library may have its own timeouts, not configurable here

### Recommended Fix
Use `asyncio.to_thread()` to run the blocking call in a thread pool:

```python
async def _direct_stream_loop_async(self):
    """Direct streaming data acquisition loop (async)"""
    while not self._stop_streaming.is_set() and self.streaming:
        try:
            # Run blocking call in thread pool
            result = await asyncio.to_thread(
                ljm.eStreamRead,
                self.direct_handle
            )
            data, backlog, error = result
            if data:
                await self._handle_stream_data_async(data)
        # ...
```

---

## 🟡 MODERATE BUG #6: Race Condition in Stream Stop

### Location
**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`
**Lines:** 1354-1363

### Root Cause
Stream stop uses a new event loop in the finally block, but the stream may still be active in the background thread.

```python
finally:
    # Stop stream
    logger.info("Stopping stream mode...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(self.labjack_service.stop_stream())
    finally:
        loop.close()
    logger.info("Stream monitoring stopped")
```

### The Race Condition
1. Main thread exits `while` loop
2. Enters `finally` block, creates new event loop
3. Calls `stop_stream()` which sets `streaming = False`
4. **BUT** `_direct_stream_loop()` thread may still be processing data
5. Event loop is closed before `_direct_stream_loop()` fully stops
6. `stream_thread.join(timeout=5)` in `stop_stream()` may timeout

---

## 🟢 COMPARISON: Working Polling Mode

### Why Polling Works

The polling mode in `_monitoring_loop()` (lines 664-1078) works correctly because:

1. **Pure Synchronous**: No asyncio event loops
2. **Direct Hardware Access**: Uses `connection_manager.read_voltage(channel)` directly
3. **Simple Threading**: Standard `threading.Thread` with `time.sleep()` for rate limiting
4. **No Queue Dependencies**: Reads voltage on-demand, no buffering

```python
def _monitoring_loop(self, session_id: str):
    """Main monitoring loop for a session with auto-stop on video end"""
    # No asyncio - pure sync
    while not stop_event.is_set():
        # Direct voltage reading
        for channel in config.channels:
            voltage = self.connection_manager.read_voltage(channel)
            channel_readings[channel] = voltage

        # Process detections
        for channel, voltage in channel_readings.items():
            if voltage >= config.voltage_threshold:
                # Record detection

        # Simple rate limiting
        time.sleep(poll_interval)
```

---

## 📊 Summary of Bugs

| Bug # | Severity | Issue | Line(s) | Impact |
|-------|----------|-------|---------|--------|
| 1 | CRITICAL | Asyncio deadlock in sync thread | 1227-1234, 1357-1362 | Stream never starts, thread blocks |
| 2 | CRITICAL | Missing stream data reading | 1257-1276 | No data retrieved from stream |
| 3 | CRITICAL | Incorrect buffer configuration | 1093, 954, 1340 | Data loss or misalignment |
| 4 | MODERATE | No fallback state management | 1236-1239 | Infinite recursion risk |
| 5 | MODERATE | Blocking calls in async context | 1034-1064 | Performance degradation |
| 6 | MODERATE | Race condition on stream stop | 1354-1363 | Resource leak, zombie threads |

---

## 🛠️ RECOMMENDED FIXES

### Fix #1: Make Stream Monitoring Fully Async

**Change thread to async task:**

```python
# In start_session_monitoring()
if use_stream_mode:
    # Create async task instead of thread
    self.monitoring_tasks[session_id] = asyncio.create_task(
        self._monitoring_loop_stream_async(session_id)
    )
else:
    # Keep polling as thread (it's synchronous)
    monitor_thread = threading.Thread(
        target=self._monitoring_loop,
        args=(session_id,),
        daemon=True
    )
    self.monitoring_threads[session_id] = monitor_thread
    monitor_thread.start()
```

**Convert `_monitoring_loop_stream()` to async:**

```python
async def _monitoring_loop_stream_async(self, session_id: str):
    """Async stream mode monitoring loop"""
    try:
        config = self.active_sessions[session_id]
        stop_event = self.stop_events[session_id]

        # Start stream (already async)
        success = await self.labjack_service.start_stream(config.channels, config.sample_rate)
        if not success:
            logger.error("Failed to start stream, falling back to polling")
            # Start polling in thread instead
            self._start_polling_thread(session_id)
            return

        # Stream reading loop
        while not stop_event.is_set():
            # Use asyncio.to_thread for blocking read
            stream_data = await asyncio.to_thread(
                self.labjack_service.get_stream_data,
                max_samples=scans_per_read * len(config.channels)
            )

            if stream_data:
                await self._process_stream_data_async(stream_data, config)
            else:
                await asyncio.sleep(0.01)  # Non-blocking sleep

    finally:
        # Async cleanup
        await self.labjack_service.stop_stream()
```

### Fix #2: Use Direct LJM Stream Reading

**Bypass the queue, read directly from LJM:**

```python
async def _monitoring_loop_stream_async(self, session_id: str):
    """Stream mode with direct LJM reading"""
    # Start stream
    success = await self.labjack_service.start_stream(config.channels, config.sample_rate)

    if not success:
        logger.error("Stream start failed")
        return

    # Direct reading loop
    while not stop_event.is_set():
        # Use the working read_stream_mode() method
        data, backlog, success = await asyncio.to_thread(
            self.labjack_service.read_stream_mode
        )

        if not success:
            logger.error("Stream read failed")
            break

        if data:
            # Process interleaved data
            num_channels = len(config.channels)
            num_samples = len(data) // num_channels

            for i in range(num_samples):
                # Extract channel values
                for j, channel in enumerate(config.channels):
                    voltage = data[i * num_channels + j]

                    # Check threshold and record detection
                    if voltage >= config.voltage_threshold:
                        await self._record_detection_async(
                            session_id, channel, voltage, timestamp
                        )

        await asyncio.sleep(0.001)  # Small async delay
```

### Fix #3: Fallback to Polling on Stream Failure

**Proper fallback mechanism:**

```python
async def start_session_monitoring(self, session_id: str, config: DetectionConfig) -> bool:
    """Start monitoring with fallback"""
    try:
        if config.use_stream_mode and config.sample_rate >= 100:
            # Try stream mode
            task = asyncio.create_task(
                self._monitoring_loop_stream_async(session_id)
            )
            self.monitoring_tasks[session_id] = task

            # Wait briefly to check if stream started
            await asyncio.sleep(0.1)

            if task.done() and task.exception():
                logger.warning("Stream mode failed, falling back to polling")
                config.use_stream_mode = False
                # Fall through to polling

        if not config.use_stream_mode:
            # Start polling thread
            monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                args=(session_id,),
                daemon=True
            )
            self.monitoring_threads[session_id] = monitor_thread
            monitor_thread.start()

        return True

    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        return False
```

### Fix #4: Improve Error Handling in Stream Loop

**Add comprehensive error recovery:**

```python
async def _monitoring_loop_stream_async(self, session_id: str):
    """Stream mode with error recovery"""
    retry_count = 0
    max_retries = 3

    while not stop_event.is_set() and retry_count < max_retries:
        try:
            # Start stream
            success = await self.labjack_service.start_stream(channels, sample_rate)
            if not success:
                retry_count += 1
                logger.warning(f"Stream start failed, retry {retry_count}/{max_retries}")
                await asyncio.sleep(1.0)
                continue

            # Reset retry counter on success
            retry_count = 0

            # Main reading loop
            consecutive_errors = 0
            max_consecutive_errors = 10

            while not stop_event.is_set():
                try:
                    data, backlog, success = await asyncio.to_thread(
                        self.labjack_service.read_stream_mode
                    )

                    if not success:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error("Too many consecutive errors, restarting stream")
                            break
                        await asyncio.sleep(0.1)
                        continue

                    # Reset error counter on success
                    consecutive_errors = 0

                    # Process data...

                except Exception as e:
                    logger.error(f"Stream read error: {e}")
                    consecutive_errors += 1

        except Exception as e:
            logger.error(f"Fatal stream error: {e}")
            retry_count += 1

        finally:
            # Always stop stream on exit
            try:
                await self.labjack_service.stop_stream()
            except:
                pass

    # If we exhausted retries, fall back to polling
    if retry_count >= max_retries:
        logger.error("Stream mode failed after max retries, falling back to polling")
        self._start_polling_thread(session_id)
```

---

## 🧪 Testing Recommendations

1. **Unit Tests**:
   - Test stream initialization with mock LJM
   - Test async/sync boundary transitions
   - Test error recovery mechanisms

2. **Integration Tests**:
   - Test stream mode with real LabJack hardware
   - Verify data integrity (all samples received)
   - Test fallback from stream to polling

3. **Stress Tests**:
   - Run stream mode at various sample rates (100 Hz, 1 kHz, 10 kHz)
   - Test with multiple channels simultaneously
   - Verify buffer overflow handling

4. **Error Injection Tests**:
   - Simulate LJM errors (LJME_STREAM_IS_ACTIVE, etc.)
   - Disconnect hardware during streaming
   - Test timeout scenarios

---

## 📝 Conclusion

The stream mode implementation has **fundamental architectural flaws** that prevent it from working:

1. **Mixing async/sync**: The detection service uses sync threads but tries to call async methods
2. **Broken data pipeline**: The queue-based approach doesn't work for DIRECT mode
3. **Poor error handling**: No fallback mechanisms or retry logic

The **recommended fix** is to:
1. Convert stream monitoring to **fully async** with `asyncio.create_task()`
2. Use **direct LJM stream reading** via `read_stream_mode()` with `asyncio.to_thread()`
3. Implement **proper fallback** to polling mode on stream failures
4. Add **comprehensive error handling** with retries and recovery

The polling mode works because it's **purely synchronous** - the stream mode should either be **fully async** or **fully sync**, not a hybrid.
