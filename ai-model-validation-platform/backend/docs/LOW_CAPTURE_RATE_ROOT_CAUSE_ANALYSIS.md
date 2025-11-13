# Low Detection Capture Rate Root Cause Analysis

## Executive Summary

**Critical Finding**: Detection capture rate is only 33% of expected (6.7Hz vs 20Hz).

- **Expected**: 20Hz sample rate = ~400 detections for 2 videos × 5s each
- **Actual**: 101 detections = ~6.7Hz average  
- **Loss**: 299 detections (75% missing)

## Root Cause: Configuration vs Implementation Mismatch

### Primary Issue: Sample Rate Configuration Not Applied

**Location**: `backend/services/dedicated_labjack_monitor.py:143`

The configuration specifies 20Hz:
```python
labjack_config = {
    'sample_rate': video_timing_config.get('sample_rate', 20),  # ✅ Configured as 20Hz
    'debounce_ms': video_timing_config.get('debounce_ms', 0),   # ✅ No debounce
}
```

**BUT** - The underlying detection service defaults are different:

**Location**: `backend/services/labjack_detection_service.py:123`
```python
@dataclass
class DetectionConfig:
    debounce_ms: int = 100      # ❌ Default 100ms debounce!
    sample_rate: int = 1000     # ❌ Default 1000Hz, not 20Hz!
```

### Secondary Issue: Integration Service Override

**Location**: `backend/services/raw_labjack_integration.py:143`
```python
video_timing_config = {
    'sample_rate': 10,  # ❌ Hardcoded to 10Hz here!
}
```

**This integration layer is forcing 10Hz regardless of configured 20Hz!**

### Tertiary Issue: Debounce Converting Level to Edge Detection

With 100ms debounce (default), the system can only record detections 10 times per second maximum (1000ms / 100ms = 10Hz).

**This converts constant voltage (level) detection into edge detection!**

## Constant Voltage Mode Analysis

**CRITICAL FINDING**: The system is configured for **edge detection**, not **level detection**.

### Current Behavior (Edge Detection):
- Detects voltage CHANGES (0V → 3.3V transition)
- Only records when voltage crosses threshold
- Debounce suppresses subsequent detections for 100ms
- Result: Only ~7Hz capture rate

### Required Behavior (Level Detection):  
- Continuously records when voltage is ABOVE threshold
- Sample at 20Hz while voltage >= 3.3V
- No debounce (debounce_ms = 0)
- Result: 20Hz capture rate

## Configuration Chain Issues

```
User Config (test execution) → 20Hz desired
    ↓
dedicated_labjack_monitor.py → 20Hz configured
    ↓  
raw_labjack_integration.py → ❌ OVERRIDES to 10Hz
    ↓
labjack_detection_service.py → ❌ Uses defaults (1000Hz + 100ms debounce)
    ↓
Actual Hardware → ~7Hz due to debounce
```

**Problem**: Configuration is overridden at multiple layers!

## Recommended Fixes

### Fix #1: Remove Integration Service Override

**File**: `backend/services/raw_labjack_integration.py:143`

Change from:
```python
'sample_rate': 10,  # ❌ Hardcoded
```

To:
```python
'sample_rate': 20,  # ✅ Match intended rate
```

### Fix #2: Implement True Level Detection

**File**: `backend/services/labjack_detection_service.py:499`

Add check for constant voltage mode:
```python
def _should_record_detection(self, session_id: str, channel: str,
                            current_time: datetime, config: DetectionConfig) -> bool:
    """Check if detection should be recorded based on debounce logic"""

    # FIXED: For constant voltage mode (debounce_ms == 0), always record
    if config.debounce_ms == 0:
        return True  # ✅ Level detection - record every sample

    # Only apply debounce if configured
    last_detection = self.last_detection_times.get(session_id, {}).get(channel, datetime.min)
    debounce_delta = timedelta(milliseconds=config.debounce_ms)
    return current_time - last_detection >= debounce_delta
```

### Fix #3: Add Configuration Validation

**New function in**: `backend/services/dedicated_labjack_monitor.py`

```python
def _validate_constant_voltage_config(self, labjack_config: Dict[str, Any]) -> None:
    """Validate configuration for constant voltage monitoring"""
    required_rate = 20  # Hz
    required_debounce = 0  # ms

    actual_rate = labjack_config.get('sample_rate')
    actual_debounce = labjack_config.get('debounce_ms')

    if actual_rate != required_rate:
        raise ValueError(f"Constant voltage mode requires {required_rate}Hz, got {actual_rate}Hz")

    if actual_debounce != required_debounce:
        raise ValueError(f"Constant voltage mode requires {required_debounce}ms debounce, got {actual_debounce}ms")
```

### Fix #4: Add Debug Logging

**File**: `backend/services/labjack_detection_service.py:421`

```python
def _monitoring_loop(self, session_id: str):
    config = self.active_sessions[session_id]
    
    # ✅ ADD: Configuration validation logging
    logger.info(f"🔧 MONITORING CONFIG:")
    logger.info(f"   Sample Rate: {config.sample_rate}Hz")
    logger.info(f"   Poll Interval: {1.0/config.sample_rate*1000:.1f}ms")
    logger.info(f"   Debounce: {config.debounce_ms}ms")
    logger.info(f"   Mode: {'LEVEL (constant voltage)' if config.debounce_ms == 0 else 'EDGE (transitions)'}")

    detection_count = 0
    start_time = time.time()

    while not stop_event.is_set():
        # ... existing monitoring logic ...
        
        # ✅ ADD: Periodic rate logging every 20 detections
        if detection_count % 20 == 0 and detection_count > 0:
            elapsed = time.time() - start_time
            actual_rate = detection_count / elapsed
            logger.info(f"📊 Rate: {actual_rate:.1f}Hz (target: {config.sample_rate}Hz)")
```

## Verification Tests

### Test #1: Verify Sample Rate
```sql
SELECT
  COUNT(*) as total_detections,
  MAX(labjack_timestamp) - MIN(labjack_timestamp) as duration_seconds,
  COUNT(*) / (MAX(labjack_timestamp) - MIN(labjack_timestamp)) as actual_rate_hz
FROM detection_events
WHERE test_session_id = '{session_id}'
```

Expected result: actual_rate_hz ≈ 20Hz

### Test #2: Check Detection Gaps  
```sql
WITH gaps AS (
  SELECT
    labjack_timestamp - LAG(labjack_timestamp) OVER (ORDER BY labjack_timestamp) as gap_seconds
  FROM detection_events
  WHERE test_session_id = '{session_id}'
)
SELECT
  COUNT(*) as total_gaps,
  AVG(gap_seconds) as avg_gap,
  MAX(gap_seconds) as max_gap
FROM gaps
WHERE gap_seconds IS NOT NULL
```

Expected result: avg_gap ≈ 0.050s (50ms), max_gap < 0.100s (100ms)

### Test #3: Verify Voltage Consistency
```sql
SELECT
  COUNT(*) as total,
  AVG(labjack_voltage) as avg_voltage,
  MIN(labjack_voltage) as min_voltage,
  MAX(labjack_voltage) as max_voltage
FROM detection_events
WHERE test_session_id = '{session_id}'
```

Expected result: avg_voltage ≈ 3.3V, min_voltage >= 3.3V

## Impact Assessment

### Current State (Broken)
- **Capture Rate**: 6.7Hz (33% of target)
- **Missing Detections**: ~299 per test (75% loss)
- **Ground Truth Matching**: Poor coverage
- **Latency Measurement**: Inaccurate

### After Fixes (Working)
- **Capture Rate**: 20Hz (100% of target)
- **Detection Count**: ~400 per test (2 videos × 5s × 20Hz × 2 = 400)
- **Ground Truth Matching**: Full coverage
- **Latency Measurement**: Accurate

## Conclusion

The low capture rate is caused by a **configuration propagation failure**:

1. Top-level config specifies 20Hz + 0ms debounce ✅
2. Integration service overrides to 10Hz ❌
3. Detection service uses 100ms debounce default ❌
4. Result: ~7Hz capture rate (67% loss) ❌

**All fixes are software-only - no hardware changes needed.**

## Action Items

Priority | Item | File | Estimated Time
---------|------|------|---------------
🔴 HIGH | Fix integration service override | `raw_labjack_integration.py:143` | 5 min
🔴 HIGH | Implement level detection | `labjack_detection_service.py:499` | 15 min
🟡 MEDIUM | Add config validation | `dedicated_labjack_monitor.py` | 20 min
🟡 MEDIUM | Add debug logging | `labjack_detection_service.py:421` | 15 min
🟢 LOW | Add verification tests | New test file | 30 min

**Total Estimated Time**: 1.5 hours
**Testing Required**: Run HIL test and verify 200+ detections captured
