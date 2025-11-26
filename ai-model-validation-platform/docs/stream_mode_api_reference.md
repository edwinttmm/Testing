# LabJack Stream Mode API Reference

**Updated:** 2025-11-18
**Status:** Production Ready

---

## Overview

Stream mode provides hardware-timed, buffered data acquisition for high-speed monitoring (200-100,000 Hz). This document describes the corrected synchronous API.

---

## Key API Methods

### 1. Start Stream Mode

```python
success, actual_scan_rate = labjack_service.start_stream_mode(
    channels=["AIN0", "AIN1"],
    scan_rate=1000,           # Desired Hz
    scans_per_read=100        # Buffer size
)
```

**Returns:**
- `success` (bool): True if stream started successfully
- `actual_scan_rate` (float): Actual achieved scan rate (may differ from requested)

**Notes:**
- Synchronous method (no async/await)
- Safe to call from daemon threads
- Hardware-timed acquisition begins immediately
- Buffer fills in background

---

### 2. Read Stream Data

```python
stream_data, backlog, read_success = labjack_service.read_stream_mode()
```

**Returns:**
- `stream_data` (List[float]): Interleaved channel samples [CH0, CH1, CH0, CH1, ...]
- `backlog` (int): Number of scans waiting in device buffer
- `read_success` (bool): True if read succeeded

**Notes:**
- **BLOCKING** call (waits for hardware)
- Safe in daemon threads
- Call regularly to prevent buffer overflow
- High backlog (>2x scans_per_read) indicates slow reading

**Data Structure:**
```python
# For 2 channels, 100 scans per read:
# stream_data = [CH0_sample0, CH1_sample0, CH0_sample1, CH1_sample1, ...]
# Length = num_channels * scans_per_read

num_channels = len(channels)
num_samples = len(stream_data) // num_channels

for i in range(num_samples):
    ch0_value = stream_data[i * num_channels + 0]
    ch1_value = stream_data[i * num_channels + 1]
```

---

### 3. Stop Stream Mode

```python
success = labjack_service.stop_stream_mode()
```

**Returns:**
- `success` (bool): True if stream stopped successfully

**Notes:**
- Synchronous method
- Halts hardware-timed streaming
- Remaining buffered data is lost
- Safe to call from cleanup/finally blocks

---

## Usage Examples

### Basic Stream Mode

```python
# Start stream
success, rate = service.start_stream_mode(
    channels=["AIN0"],
    scan_rate=1000,
    scans_per_read=200
)

if not success:
    print("Failed to start stream")
    return

print(f"Stream active at {rate} Hz")

try:
    # Read data in loop
    while running:
        data, backlog, ok = service.read_stream_mode()

        if not ok:
            print("Read failed")
            break

        if len(data) > 0:
            # Process data
            process_samples(data)

        if backlog > 400:
            print(f"Warning: high backlog {backlog}")

finally:
    # Always stop stream
    service.stop_stream_mode()
```

---

### Multi-Channel Monitoring

```python
channels = ["AIN0", "AIN1", "AIN2"]
success, rate = service.start_stream_mode(
    channels=channels,
    scan_rate=2000,
    scans_per_read=100
)

if success:
    data, backlog, ok = service.read_stream_mode()

    if ok and len(data) > 0:
        num_samples = len(data) // len(channels)

        for i in range(num_samples):
            ain0 = data[i * 3 + 0]
            ain1 = data[i * 3 + 1]
            ain2 = data[i * 3 + 2]

            print(f"Sample {i}: AIN0={ain0:.3f}V, AIN1={ain1:.3f}V, AIN2={ain2:.3f}V")
```

---

### With Error Handling

```python
consecutive_errors = 0
max_errors = 5

success, rate = service.start_stream_mode(["AIN0"], 1000, 200)

if not success:
    # Fall back to polling mode
    use_polling_mode()
    return

try:
    while running:
        data, backlog, ok = service.read_stream_mode()

        if not ok:
            consecutive_errors += 1

            if consecutive_errors >= max_errors:
                print("Too many errors, stopping stream")
                break

            time.sleep(0.1)  # Brief pause
            continue

        # Reset error counter on success
        consecutive_errors = 0

        if len(data) > 0:
            process_samples(data)
        else:
            time.sleep(0.001)  # Prevent CPU spinning

finally:
    service.stop_stream_mode()
```

---

## Thread Safety

### ✅ SAFE: Daemon Thread Pattern

```python
def monitoring_thread():
    """Daemon thread for stream monitoring"""
    success, rate = service.start_stream_mode(["AIN0"], 1000)

    if not success:
        return

    try:
        while not stop_event.is_set():
            data, backlog, ok = service.read_stream_mode()
            # Process synchronously
            process_data(data)
    finally:
        service.stop_stream_mode()

# Start thread
thread = threading.Thread(target=monitoring_thread, daemon=True)
thread.start()
```

### ❌ WRONG: AsyncIO in Thread

```python
# DON'T DO THIS - causes deadlocks!
def monitoring_thread():
    loop = asyncio.new_event_loop()  # ❌ DEADLOCK
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_operation())  # ❌ BLOCKS FOREVER
    loop.close()
```

---

## Performance Guidelines

### Optimal Settings

| Sample Rate | scans_per_read | Read Frequency | CPU Load |
|-------------|----------------|----------------|----------|
| 200 Hz      | 20             | 10 Hz          | Low      |
| 1,000 Hz    | 100            | 10 Hz          | Low      |
| 10,000 Hz   | 500            | 20 Hz          | Medium   |
| 50,000 Hz   | 2,500          | 20 Hz          | High     |

### Buffer Sizing

```python
# Rule of thumb:
read_frequency = 10-20  # Hz
scans_per_read = scan_rate // read_frequency

# Example for 1000 Hz:
scans_per_read = 1000 // 10 = 100
```

### Backlog Monitoring

```python
if backlog > scans_per_read * 2:
    # Buffer filling up - three options:
    # 1. Increase read frequency
    # 2. Increase scans_per_read
    # 3. Lower scan_rate
    pass
```

---

## Fallback Strategy

```python
def start_with_fallback(channels, scan_rate):
    """Start stream with automatic fallback to polling"""

    # Try stream mode first
    success, rate = service.start_stream_mode(channels, scan_rate)

    if success:
        return "stream", rate

    # Fall back to polling
    logger.warning("Stream failed, using polling mode")
    return "polling", scan_rate
```

---

## Common Issues

### Issue: Stream Fails to Start
**Symptom:** `start_stream_mode()` returns `(False, 0.0)`
**Causes:**
- No hardware connection
- Unsupported scan rate
- Device already streaming
**Solution:** Check connection, validate rate, stop existing stream

### Issue: Empty Data Returns
**Symptom:** `read_stream_mode()` returns `([], 0, True)`
**Causes:**
- Buffer not yet filled
- Read called too quickly
**Solution:** Wait longer between reads, increase `scans_per_read`

### Issue: High Backlog
**Symptom:** `backlog > 400` consistently
**Causes:**
- Reading too slowly
- Processing taking too long
**Solution:** Increase read frequency, optimize processing

---

## Migration from Old API

### Before (Broken)
```python
# ❌ OLD WAY (with asyncio in threads)
loop = asyncio.new_event_loop()
loop.run_until_complete(service.start_stream(channels, rate))
data = service.get_stream_data()  # Returns empty!
loop.run_until_complete(service.stop_stream())
```

### After (Fixed)
```python
# ✅ NEW WAY (fully synchronous)
success, rate = service.start_stream_mode(channels, rate)
data, backlog, ok = service.read_stream_mode()
service.stop_stream_mode()
```

---

## See Also

- `phase2_stream_mode_fixes_summary.md` - Complete fix documentation
- `labjack_detection_service.py` - Implementation reference
- `labjack_hardware_service.py` - Hardware interface

---

**Status:** ✅ Production Ready
**Last Updated:** 2025-11-18
