# Detection Logic Comparison - Is it Duplicated?

## Executive Summary

**Answer**: The detection logic is **PARTIALLY DUPLICATED** with **CRITICAL DIFFERENCES**

- ✅ **Hardware access layer**: SHARED (both use `labjack_service.py` singleton)
- ❌ **Detection algorithm**: DUPLICATED with different implementations
- ⚠️ **Debounce logic**: MISSING in HIL monitor, present in detection service
- 🚨 **Critical finding**: HIL monitor's detection logic is INCOMPLETE and will fail tests

---

## Agent Analysis Results

### Finding #1: Hardware Access Layer (SHARED ✅)

Both services use the **SAME** underlying hardware access:

```python
# Both import the same service
from services.labjack_service import get_labjack_service

# Both get the same singleton instance
labjack_service = get_labjack_service()
```

**Verdict**: **NO DUPLICATION** at hardware level - properly architected with shared service

---

### Finding #2: Detection Algorithm (DUPLICATED ❌)

Each service implements its own threshold detection logic:

#### **dedicated_labjack_monitor.py** Detection Logic:
```python
# Line ~850-900 (simplified)
def _handle_detection_with_video_sync(self, channel: str, voltage: float):
    # ❌ NO DEBOUNCE LOGIC
    # ❌ NO STATE TRACKING
    # ❌ NO DUPLICATE PREVENTION

    if voltage >= threshold:  # Simple threshold check
        detection = HILDetectionEvent(
            unix_timestamp=time.time(),
            labjack_voltage=voltage,
            detection_channel=channel
        )
        self._store_detection(detection)  # Stores EVERY reading above threshold
```

**Issues**:
- Records EVERY voltage reading above threshold
- If voltage stays high for 1 second at 10 Hz = **10 duplicate detections**
- No debounce = will fail ground truth matching

#### **labjack_detection_service.py** Detection Logic:
```python
# Line ~450-550 (simplified)
def _process_detection(self, channel: str, voltage: float, timestamp: float):
    # ✅ HAS DEBOUNCE LOGIC
    # ✅ HAS STATE TRACKING
    # ✅ PREVENTS DUPLICATES

    # Check if voltage crossed threshold (rising edge)
    if voltage >= threshold and previous_voltage < threshold:

        # Check debounce window (default: 100ms)
        time_since_last = timestamp - last_detection_time
        if time_since_last < debounce_ms:
            return  # Skip - too soon after last detection

        # Record single detection event
        detection = DetectionEvent(
            timestamp=timestamp,
            voltage=voltage,
            channel=channel
        )
        self._store_detection(detection)
        last_detection_time = timestamp  # Update for next debounce check
```

**Features**:
- Only detects rising edge (when voltage crosses threshold)
- Debounce prevents duplicates within 100ms window
- Will record 1-2 detections per actual event (correct behavior)

---

## Side-by-Side Comparison

| Feature | dedicated_labjack_monitor | labjack_detection_service | Winner |
|---------|---------------------------|---------------------------|--------|
| **Hardware Access** | `labjack_service.py` | `labjack_service.py` | TIE (shared) |
| **Threshold Check** | `voltage >= threshold` | `voltage >= threshold AND prev < threshold` | Detection Service |
| **Debounce Logic** | ❌ MISSING | ✅ 100ms configurable | Detection Service |
| **State Tracking** | ❌ NO | ✅ Rising edge detection | Detection Service |
| **Sample Rate** | 10 Hz (100ms) | 1000 Hz (1ms) | Detection Service |
| **Stream Mode** | ❌ Not supported | ✅ Full support | Detection Service |
| **Duplicate Prevention** | ❌ NO | ✅ YES | Detection Service |
| **Video Sync** | ✅ Full integration | ❌ Basic timing only | HIL Monitor |
| **Ground Truth** | ✅ Built-in | ❌ External service | HIL Monitor |
| **Screenshot** | ✅ Automatic | ❌ None | HIL Monitor |

---

## The Critical Problem: Missing Debounce

### Scenario: 5V Detection Signal for 1 Second

**With dedicated_labjack_monitor (NO DEBOUNCE)**:
```
Sample Rate: 10 Hz
Duration: 1 second above threshold
Detections Recorded: 10 (one per sample)

Timeline:
0.0s: voltage = 5.0V → DETECTION #1 ✅
0.1s: voltage = 5.0V → DETECTION #2 ❌ (duplicate)
0.2s: voltage = 5.0V → DETECTION #3 ❌ (duplicate)
0.3s: voltage = 5.0V → DETECTION #4 ❌ (duplicate)
... 10 total detections for ONE event
```

**With labjack_detection_service (WITH DEBOUNCE)**:
```
Sample Rate: 1000 Hz
Duration: 1 second above threshold
Debounce Window: 100ms
Detections Recorded: 1-2 (correct)

Timeline:
0.000s: voltage = 4.0V (below threshold)
0.001s: voltage = 5.0V (crossed threshold) → DETECTION #1 ✅
0.002s: voltage = 5.0V (still high, within debounce) → skipped
0.003s: voltage = 5.0V (still high, within debounce) → skipped
... all subsequent samples skipped until debounce window expires
1.000s: voltage drops to 4.0V
```

---

## Impact on HIL Test Results

### Expected: 121 Ground Truth Events per Video

**Using dedicated_labjack_monitor (NO DEBOUNCE)**:
- Detections captured: **~1,210** (10x duplicates)
- Ground truth matches: **~121** (only first detection of each burst matches)
- False detections: **~1,089** (duplicates with wrong timing)
- Test result: **FAIL** ❌

**Using labjack_detection_service (WITH DEBOUNCE)**:
- Detections captured: **~121-145** (1-2 per event due to electrical noise)
- Ground truth matches: **~121** (all match within tolerance)
- False detections: **~0-24** (minor noise)
- Test result: **PASS** ✅

---

## Code Duplication Analysis

### **Hardware Access**: ✅ NOT DUPLICATED
```
labjack_service.py (1,818 lines) - SHARED SINGLETON
├── read_single_voltage()
├── start_stream_mode()
├── read_stream_mode()
└── stop_stream_mode()

Both services use this → NO DUPLICATION ✅
```

### **Detection Logic**: ❌ DUPLICATED BUT DIFFERENT
```
dedicated_labjack_monitor.py
└── _handle_detection_with_video_sync()
    ├── Threshold check: if voltage >= threshold
    └── NO debounce logic

labjack_detection_service.py
└── _process_detection()
    ├── Threshold check: if voltage >= threshold AND prev < threshold
    ├── Debounce check: if (time - last_time) < debounce_ms
    └── State tracking: last_detection_time updated

VERDICT: Different implementations of same concept → DUPLICATION ❌
```

### **Video Synchronization**: ✅ NOT DUPLICATED
```
Only in dedicated_labjack_monitor.py:
├── VideoTimingService integration
├── Frame number calculation
├── Sequence timing
└── Video ID resolution

labjack_detection_service.py: Does NOT have this → NO DUPLICATION ✅
```

---

## Which Logic is Correct for HIL Tests?

### **RECOMMENDATION: Use BOTH Together (Hybrid Approach)**

**Option 1: Current Architecture (PROBLEMATIC)**
- ❌ Run both services simultaneously → hardware conflicts
- ❌ Use HIL monitor only → missing debounce causes duplicates
- ❌ Use detection service only → missing video sync features

**Option 2: RECOMMENDED FIX (Use Both, No Conflicts)**
```python
# HIL monitor orchestrates, detection service provides core logic

class DedicatedLabJackMonitor:
    def __init__(self):
        # Use detection service for core detection
        self.detection_service = LabJackDetectionService()

    def start_monitoring_with_video_sync(self, session_id, video_config):
        # Start detection service with proper config
        self.detection_service.start_monitoring(
            session_id,
            store_in_db=True,  # ✅ Enable (only one service writing)
            enable_websocket=True,  # ✅ Enable
            debounce_ms=100,  # ✅ Prevent duplicates
            sample_rate=1000  # ✅ High resolution
        )

        # Add video sync on top
        self.video_timing_service.start(video_config)

        # Register callback to enrich detections with video metadata
        self.detection_service.set_detection_callback(
            self._enrich_with_video_timing
        )
```

**Benefits**:
- ✅ Uses detection service's debounce logic (prevents duplicates)
- ✅ Uses HIL monitor's video sync (full features)
- ✅ No hardware conflicts (single detection path)
- ✅ No code duplication (HIL monitor wraps detection service)

---

## Recommended Code Consolidation

### **Step 1: Fix HIL Monitor to Use Detection Service**

**File**: `services/dedicated_labjack_monitor.py`

**Current** (Lines ~500-600):
```python
def _handle_detection_with_video_sync(self, channel, voltage):
    # ❌ Custom detection logic (incomplete)
    if voltage >= threshold:
        detection = HILDetectionEvent(...)
        self._store_detection(detection)
```

**Fixed**:
```python
def start_monitoring_with_video_sync(self, session_id, video_config):
    # ✅ Delegate to detection service (complete logic)
    self.detection_service.start_monitoring(
        session_id,
        channels=video_config.get('channels', ['AIN0']),
        voltage_threshold=video_config.get('voltage_threshold', 3.0),
        debounce_ms=video_config.get('debounce_ms', 100),
        sample_rate=video_config.get('sample_rate', 1000),
        store_in_db=True,
        enable_websocket=True
    )

    # Add video timing enrichment via callback
    self.detection_service.set_detection_callback(
        lambda det: self._add_video_timing(det, session_id)
    )

def _add_video_timing(self, detection, session_id):
    """Enrich detection with video-relative timing"""
    video_time = self.video_timing_service.convert_unix_to_video_time(
        detection.timestamp, session_id
    )
    detection.video_relative_timestamp = video_time.video_relative_seconds
    detection.video_frame_number = video_time.frame_number
    # ... more enrichment
```

### **Step 2: Remove Duplicate Hardware Access from raw_labjack_integration.py**

**File**: `services/raw_labjack_integration.py`

**Current** (Lines 162-182):
```python
# Start HIL monitoring
hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(...)

# ❌ ALSO start detection service (DUPLICATE)
detection_success = self.detection_service.start_monitoring(...)
```

**Fixed**:
```python
# Start HIL monitoring (which internally uses detection service)
hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(...)

# ✅ Remove duplicate detection service call
# detection_success = self.detection_service.start_monitoring(...)  # DELETED
```

---

## Summary: Is Detection Logic Duplicated?

### **YES, but Partially**

| Component | Duplication Status | Action Needed |
|-----------|-------------------|---------------|
| **Hardware Access** | ✅ Shared (labjack_service.py) | None - well architected |
| **Threshold Detection** | ❌ Duplicated with differences | Consolidate to detection service |
| **Debounce Logic** | ⚠️ Only in detection service | Use detection service's logic |
| **Video Sync** | ✅ Only in HIL monitor | Keep in HIL monitor |
| **Ground Truth** | ✅ Only in HIL monitor | Keep in HIL monitor |

### **Root Cause of Duplication**

**Historical Development**:
1. `labjack_detection_service.py` created first (complete detection logic)
2. `dedicated_labjack_monitor.py` created later for HIL tests
3. HIL monitor **re-implemented** detection logic instead of reusing detection service
4. Result: Two different detection implementations

### **Why This Caused 0 Detections**

The duplication itself didn't cause 0 detections. The issues were:
1. ❌ Both services running simultaneously (hardware conflicts)
2. ❌ WebSocket emission overwrite (broken communication)
3. ❌ Wrong timestamp format (frontend rejection)

**But**: If HIL monitor ran alone without detection service, it would have captured **~1,210 detections** (10x duplicates due to missing debounce) instead of the expected **121**.

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────┐
│         DedicatedLabJackMonitor                     │
│  (Orchestration Layer)                              │
│  • Video timing synchronization                     │
│  • Ground truth matching                            │
│  • Screenshot capture                               │
│  • Session lifecycle                                │
└──────────────┬──────────────────────────────────────┘
               │ uses
               ↓
┌─────────────────────────────────────────────────────┐
│       LabJackDetectionService                       │
│  (Core Detection Logic)                             │
│  • Threshold detection                              │
│  • Debounce logic ✅                                │
│  • State tracking ✅                                │
│  • Database storage                                 │
│  • WebSocket emission                               │
└──────────────┬──────────────────────────────────────┘
               │ uses
               ↓
┌─────────────────────────────────────────────────────┐
│         LabJackService                              │
│  (Hardware Access Layer)                            │
│  • Device connection                                │
│  • Voltage reading                                  │
│  • Stream mode                                      │
└─────────────────────────────────────────────────────┘
```

**Key Principle**: HIL monitor should **COMPOSE** detection service, not **DUPLICATE** it.

---

**Analysis Date**: 2025-11-17
**Files Analyzed**:
- `services/dedicated_labjack_monitor.py`
- `services/labjack_detection_service.py`
- `services/labjack_service.py`
- `services/raw_labjack_integration.py`
