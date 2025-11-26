# Architecture Options for Minimal Code Integration

## Executive Summary

**Current Problem**: Both monitoring systems running simultaneously → hardware conflicts
**Goal**: Combine best features with MINIMAL code changes
**Requirements**: ±1-2ms timing, video sync, ground truth, no duplicates

---

## 1. Current Call Path Analysis

### File: `/services/raw_labjack_integration.py` (Lines 158-199)

```python
# Line 162: HIL Monitor with Video Sync
hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
    test_session_id, video_timing_config
)

# Line 177: Detection Service for Basic Monitoring
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10,
    store_in_db=True,
    enable_websocket=True
)
```

### Why Both Are Called?

1. **HIL Monitor (`dedicated_labjack_monitor.py`)** - 2079 lines
   - **Purpose**: Video timing synchronization for ground truth matching
   - **Key Features**:
     - Video-relative timestamp conversion (Unix → video-relative)
     - HIL screenshot capture for validation
     - Ground truth comparison service integration
     - Detection window clamping (prevents overlaps in sequences)
     - Video timing service integration
     - High precision (nanosecond-level) timing
   - **What it does**: Wraps Detection Service, adds video sync layer

2. **Detection Service (`labjack_detection_service.py`)** - 2315 lines
   - **Purpose**: Core hardware monitoring and detection events
   - **Key Features**:
     - Hardware-timed stream mode (high-frequency sampling)
     - Polling mode (lower-frequency sampling)
     - Voltage threshold detection with debounce
     - Continuous mode (steady-state logging)
     - WebSocket emission for real-time updates
     - Database storage with batching
     - Auto-stop based on video duration
   - **What it does**: Direct LabJack hardware interface

### Current Duplication Problem

**Both systems start separate monitoring threads:**
- HIL Monitor: Calls `detection_service.start_monitoring()` internally (Line 92)
- Raw Integration: Calls `detection_service.start_monitoring()` again (Line 177)

**Result**: Two threads sampling same hardware → conflicts, duplicates, timing issues

---

## 2. Architecture Option A: HIL Monitor as Orchestrator

### **Concept**: HIL Monitor becomes the single entry point, delegates to Detection Service

### Architecture Diagram

```
raw_labjack_integration.py
         |
         v
   DedicatedLabJackMonitor (HIL)
         |
         |-- VideoTimingService (sync timestamps)
         |-- HILGroundTruthComparison (screenshots)
         |-- DetectionWindowClampService (overlap prevention)
         |
         v
   LabJackDetectionMonitor (hardware)
         |
         v
   LabJack Hardware
```

### Code Changes Required

#### File 1: `/services/raw_labjack_integration.py`
**Lines to modify**: 158-193 (remove duplicate call)

```python
# ✅ CHANGE: Only call HIL monitor, remove detection_service call
hil_session_active = False
if video_config:
    try:
        # Single entry point - HIL monitor handles everything
        hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
            test_session_id, video_timing_config
        )
        hil_session_active = hil_success

        if hil_success:
            logger.info(f"✅ HIL monitoring started (includes detection) for session {test_session_id}")
        else:
            logger.warning(f"⚠️ HIL monitoring failed for session {test_session_id}")
    except Exception as e:
        logger.error(f"HIL monitoring startup error: {e}")

# ❌ REMOVE: Lines 174-193 (detection_service.start_monitoring call)
# This is now handled internally by HIL monitor
```

#### File 2: `/services/dedicated_labjack_monitor.py`
**Lines to modify**: 226-450 (ensure detection service is properly configured)

```python
# ✅ VERIFY: Line 292-299 already starts detection service internally
# Ensure all parameters from raw_labjack_integration are passed through

async def start_monitoring_with_video_sync(self, session_id: str, video_timing_config: Dict[str, Any]) -> bool:
    """
    ENHANCED: Now the single entry point for all monitoring.
    Internally delegates to LabJackDetectionMonitor with proper config.
    """
    try:
        # ... existing video config setup ...

        # ✅ ENSURE: Detection service gets all necessary params
        labjack_config = {
            'channels': video_timing_config.get('channels', ['AIN0']),
            'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),
            'debounce_ms': video_timing_config.get('debounce_ms', 0),
            'sample_rate': sample_rate,
            'store_in_db': True,  # Always store for HIL
            'enable_websocket': video_timing_config.get('enable_websocket', True),

            # ✅ ADD: Pass through continuous mode settings
            'continuous_mode': video_timing_config.get('continuous_mode', False),
            'continuous_lower_bound': video_timing_config.get('continuous_lower_bound'),
            'continuous_upper_bound': video_timing_config.get('continuous_upper_bound'),
            'continuous_interval_ms': video_timing_config.get('continuous_interval_ms', 20),
            'steady_high_logging': video_timing_config.get('steady_high_logging', True),
            'steady_high_interval_ms': video_timing_config.get('steady_high_interval_ms', 10),
        }

        # Start detection monitoring (Line 450+)
        success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)
```

### Pros
- ✅ **Minimal changes**: Only 2 files, ~40 lines modified
- ✅ **Preserves all features**: Video sync, ground truth, detection all intact
- ✅ **Single hardware access**: No conflicts, no duplicates
- ✅ **Clean abstraction**: HIL is the orchestrator, Detection is the worker
- ✅ **Backward compatible**: Other callers of Detection Service unaffected

### Cons
- ⚠️ **HIL becomes mandatory**: Can't use Detection Service standalone for video tests
- ⚠️ **Tight coupling**: HIL depends on Detection Service implementation details

### Risk Level: **LOW** ✅
- No breaking changes to core detection logic
- Only removes duplicate call
- All features preserved

### Implementation Time: **2-3 hours**
- Code changes: 30 mins
- Testing: 1-2 hours
- Validation: 30 mins

### Testing Required
1. Single video test (verify no duplicates)
2. Multi-video sequence test (verify window clamping works)
3. Stream mode test (verify high-frequency sampling)
4. Continuous mode test (verify steady-state logging)
5. WebSocket test (verify real-time updates)

---

## 3. Architecture Option B: Detection Service with HIL Plugin

### **Concept**: Detection Service becomes extensible, HIL features as plugin layer

### Architecture Diagram

```
raw_labjack_integration.py
         |
         v
   LabJackDetectionMonitor (core)
         |
         |-- BaseDetectionMonitor (common logic)
         |-- HILPlugin (optional, adds video sync)
         |    |-- VideoTimingService
         |    |-- HILGroundTruthComparison
         |    |-- DetectionWindowClampService
         |
         v
   LabJack Hardware
```

### Code Changes Required

#### File 1: `/services/labjack_detection_service.py`
**Lines to modify**: 335-397 (add plugin architecture)

```python
# ✅ ADD: Plugin system for extensibility
class DetectionPlugin(ABC):
    """Base class for detection plugins"""

    @abstractmethod
    async def on_detection_event(self, event: DetectionEvent) -> DetectionEvent:
        """Called when detection event occurs"""
        pass

    @abstractmethod
    async def on_session_start(self, session_id: str, config: DetectionConfig) -> bool:
        """Called when monitoring session starts"""
        pass

    @abstractmethod
    async def on_session_stop(self, session_id: str) -> bool:
        """Called when monitoring session stops"""
        pass


class LabJackDetectionMonitor:
    def __init__(self):
        # ... existing init ...
        self.plugins: List[DetectionPlugin] = []

    def register_plugin(self, plugin: DetectionPlugin):
        """Register a detection plugin"""
        self.plugins.append(plugin)
        logger.info(f"✅ Registered plugin: {plugin.__class__.__name__}")

    def start_monitoring(self, session_id: str, ...):
        """Start monitoring with plugin support"""
        with self.lock:
            # ... existing setup ...

            # Notify plugins
            for plugin in self.plugins:
                await plugin.on_session_start(session_id, config)

            # ... start monitoring thread ...

    def _process_detection_event(self, event):
        """Process detection event through plugin chain"""
        # Process through each plugin
        for plugin in self.plugins:
            event = await plugin.on_detection_event(event)

        # ... existing storage logic ...
```

#### File 2: `/services/hil_detection_plugin.py` (NEW FILE)
**Lines of code**: ~300 lines

```python
"""
HIL Detection Plugin
Adds video timing synchronization and ground truth comparison to detection events.
"""
from services.labjack_detection_service import DetectionPlugin, DetectionEvent
from services.video_timing_service import VideoTimingService
from services.hil_screenshot_service import HILGroundTruthComparison

class HILDetectionPlugin(DetectionPlugin):
    """Plugin that adds HIL video timing features to detection monitoring"""

    def __init__(self, video_timing_service: VideoTimingService):
        self.video_timing_service = video_timing_service
        self.hil_comparison = HILGroundTruthComparison()
        self.active_video_sessions: Dict[str, Dict] = {}

    async def on_session_start(self, session_id: str, config: DetectionConfig) -> bool:
        """Setup video timing for session"""
        video_config = config.metadata.get('video_timing_config')
        if video_config:
            # Extract video info and start timing service
            video_id = video_config.get('video_id')
            # ... setup video timing ...
        return True

    async def on_detection_event(self, event: DetectionEvent) -> DetectionEvent:
        """Enhance detection event with video timing"""
        session_id = event.session_id

        if session_id in self.active_video_sessions:
            # Convert Unix timestamp to video-relative
            video_relative_ts = self.video_timing_service.convert_to_video_time(
                session_id, event.unix_timestamp
            )

            # Add video timing fields
            event.video_relative_timestamp = video_relative_ts
            event.video_frame_number = self._calculate_frame_number(...)

            # Capture screenshot if needed
            if self._should_capture_screenshot(event):
                screenshot_path = await self.hil_comparison.capture_screenshot(...)
                event.screenshot_path = screenshot_path

        return event

    async def on_session_stop(self, session_id: str) -> bool:
        """Cleanup video timing resources"""
        # ... cleanup ...
        return True
```

#### File 3: `/services/raw_labjack_integration.py`
**Lines to modify**: 158-193

```python
# ✅ CHANGE: Register HIL plugin, single detection service call
from services.hil_detection_plugin import HILDetectionPlugin

# Setup HIL plugin if video config provided
if video_config:
    hil_plugin = HILDetectionPlugin(self.video_timing_service)
    self.detection_service.register_plugin(hil_plugin)

# Single monitoring call with plugin support
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10,
    store_in_db=True,
    enable_websocket=True,
    metadata={'video_timing_config': video_timing_config}  # Pass video config
)
```

### Pros
- ✅ **True extensibility**: Easy to add more plugins (e.g., ML detection, anomaly detection)
- ✅ **Clean separation**: Core detection vs. optional features
- ✅ **Flexible**: HIL features only active when needed
- ✅ **Testable**: Each plugin can be tested independently
- ✅ **Future-proof**: Easy to add more plugins without modifying core

### Cons
- ⚠️ **More refactoring**: Need to extract HIL logic from DedicatedLabJackMonitor
- ⚠️ **New abstractions**: Plugin interface adds complexity
- ⚠️ **Migration effort**: Existing HIL code needs to be moved to plugin
- ⚠️ **Breaking changes**: DedicatedLabJackMonitor becomes wrapper around plugin

### Risk Level: **MEDIUM** ⚠️
- Requires extracting and moving HIL logic
- New plugin interface must be designed correctly
- Potential for regressions during refactoring

### Implementation Time: **1-2 days**
- Plugin interface design: 2 hours
- Extract HIL logic to plugin: 4 hours
- Update Detection Service: 2 hours
- Testing: 4-6 hours
- Integration validation: 2 hours

### Testing Required
1. All tests from Option A
2. Plugin registration/unregistration
3. Non-video tests (without HIL plugin)
4. Multiple plugins simultaneously
5. Plugin error handling

---

## 4. Architecture Option C: Shared Core with Role-Based Interfaces

### **Concept**: Extract common monitoring logic to base class, specialized interfaces for different use cases

### Architecture Diagram

```
raw_labjack_integration.py
         |
         +-- HILMonitoringInterface (for video sync tests)
         |        |
         |        v
         |   BaseLabJackMonitor (shared core)
         |        |
         v        v
    BasicDetectionInterface (for simple tests)
         |
         v
   LabJack Hardware
```

### Code Changes Required

#### File 1: `/services/base_labjack_monitor.py` (NEW FILE)
**Lines of code**: ~800 lines (extracted from both existing files)

```python
"""
Base LabJack Monitor
Shared core logic for all monitoring scenarios.
"""

class BaseLabJackMonitor:
    """
    Core LabJack monitoring logic shared by all interfaces.
    Handles hardware communication, sampling, and basic event detection.
    """

    def __init__(self):
        self.labjack_service = get_labjack_service()
        self.active_sessions: Dict[str, MonitoringSession] = {}
        self.lock = threading.RLock()

    def _start_monitoring_thread(self, session_id: str, config: MonitoringConfig):
        """Core monitoring thread logic"""
        # Extracted from labjack_detection_service.py
        pass

    def _process_voltage_reading(self, session_id: str, voltage: float, timestamp: float):
        """Core voltage processing logic"""
        # Shared by all interfaces
        pass

    def _stream_mode_loop(self, session_id: str):
        """Hardware-timed stream mode (high-frequency)"""
        # Extracted from labjack_detection_service.py (lines 1200-1400)
        pass

    def _polling_mode_loop(self, session_id: str):
        """Software-timed polling mode (lower-frequency)"""
        # Extracted from labjack_detection_service.py (lines 900-1100)
        pass
```

#### File 2: `/services/hil_monitoring_interface.py` (NEW FILE)
**Lines of code**: ~500 lines

```python
"""
HIL Monitoring Interface
Specialized interface for video-synchronized HIL validation tests.
"""

class HILMonitoringInterface(BaseLabJackMonitor):
    """
    HIL-specific monitoring with video timing synchronization.
    Extends base monitor with video timing and ground truth features.
    """

    def __init__(self, video_timing_service: VideoTimingService):
        super().__init__()
        self.video_timing_service = video_timing_service
        self.hil_comparison = HILGroundTruthComparison()
        self.detection_window_clamp = DetectionWindowClampService()

    async def start_monitoring_with_video_sync(self, session_id: str, video_config: Dict):
        """Start monitoring with video timing synchronization"""
        # Setup video timing
        video_id = video_config.get('video_id')
        await self.video_timing_service.start_video_timing(session_id, video_id, ...)

        # Start base monitoring with enhanced callback
        monitoring_config = self._build_monitoring_config(video_config)
        monitoring_config.detection_callback = self._on_detection_with_video_sync

        return self._start_monitoring_thread(session_id, monitoring_config)

    async def _on_detection_with_video_sync(self, event: DetectionEvent):
        """Enhanced detection callback with video timing"""
        # Convert timestamp to video-relative
        video_ts = self.video_timing_service.convert_to_video_time(
            event.session_id, event.unix_timestamp
        )

        # Add video timing metadata
        event.video_relative_timestamp = video_ts
        event.video_frame_number = self._calculate_frame_number(...)

        # Capture screenshot for ground truth
        screenshot = await self.hil_comparison.capture_screenshot(...)
        event.screenshot_path = screenshot

        # Call base event handler
        await self._store_detection_event(event)
```

#### File 3: `/services/basic_detection_interface.py` (NEW FILE)
**Lines of code**: ~200 lines

```python
"""
Basic Detection Interface
Simple interface for non-video monitoring scenarios.
"""

class BasicDetectionInterface(BaseLabJackMonitor):
    """
    Basic detection monitoring without video synchronization.
    Lightweight interface for simple detection tests.
    """

    def start_monitoring(self, session_id: str, channels: List[str],
                        voltage_threshold: float, sample_rate: int, **kwargs):
        """Start basic detection monitoring"""
        monitoring_config = MonitoringConfig(
            session_id=session_id,
            channels=channels,
            voltage_threshold=voltage_threshold,
            sample_rate=sample_rate,
            detection_callback=self._on_detection_basic,
            **kwargs
        )

        return self._start_monitoring_thread(session_id, monitoring_config)

    async def _on_detection_basic(self, event: DetectionEvent):
        """Basic detection callback without video features"""
        # Store event directly
        await self._store_detection_event(event)
```

#### File 4: `/services/raw_labjack_integration.py`
**Lines to modify**: 158-193

```python
# ✅ CHANGE: Use appropriate interface based on test type
from services.hil_monitoring_interface import HILMonitoringInterface
from services.basic_detection_interface import BasicDetectionInterface

# Choose interface based on whether video config is provided
if video_config:
    # Use HIL interface for video-synchronized tests
    hil_monitor = HILMonitoringInterface(self.video_timing_service)
    hil_success = await hil_monitor.start_monitoring_with_video_sync(
        test_session_id, video_timing_config
    )
    session_active = hil_success
else:
    # Use basic interface for non-video tests
    basic_monitor = BasicDetectionInterface()
    basic_success = basic_monitor.start_monitoring(
        test_session_id,
        channels=channels,
        voltage_threshold=self.config.detection_threshold_volts,
        sample_rate=10
    )
    session_active = basic_success
```

### Pros
- ✅ **Maximum code reuse**: Shared core eliminates duplication
- ✅ **Clear separation of concerns**: Each interface has single responsibility
- ✅ **Optimal for each use case**: HIL gets full features, basic gets lightweight
- ✅ **Easy to extend**: Add new interfaces without touching core
- ✅ **Better testing**: Test core once, then test each interface

### Cons
- ⚠️ **Major refactoring**: Need to extract and reorganize 3000+ lines of code
- ⚠️ **High risk**: Many moving parts, easy to introduce bugs
- ⚠️ **Migration complexity**: Need to update all callers
- ⚠️ **Long timeline**: Significant development and testing effort

### Risk Level: **HIGH** 🔴
- Requires reorganizing both major services
- Risk of breaking existing functionality
- Complex dependencies need careful handling
- Extensive testing required

### Implementation Time: **3-5 days**
- Extract base monitor logic: 8 hours
- Create HIL interface: 4 hours
- Create basic interface: 2 hours
- Update all callers: 4 hours
- Comprehensive testing: 8-12 hours
- Bug fixes and refinement: 4-6 hours

### Testing Required
1. All tests from Option A and B
2. Base monitor unit tests
3. HIL interface integration tests
4. Basic interface integration tests
5. Cross-interface compatibility tests
6. Performance regression tests
7. Memory leak tests

---

## 5. Recommendation: Option A (HIL Monitor as Orchestrator)

### Why Option A is Best

#### ✅ **Minimal Changes (Lowest Risk)**
- Only 2 files modified
- ~40 lines of code changed
- No new abstractions or interfaces
- No major refactoring

#### ✅ **Preserves All Features**
- Video timing synchronization ✅
- Ground truth comparison ✅
- Detection window clamping ✅
- Stream mode / polling mode ✅
- Continuous mode ✅
- WebSocket updates ✅
- Database storage ✅

#### ✅ **Solves Root Problem**
- Single hardware access point
- No duplicate monitoring threads
- No timing conflicts
- No duplicate events

#### ✅ **Fast Implementation**
- 2-3 hours total
- Can be completed in single session
- Low testing burden
- Easy rollback if needed

### Implementation Plan

#### Phase 1: Code Changes (30 minutes)

1. **File: `/services/raw_labjack_integration.py`**
   - Remove lines 174-193 (detection_service.start_monitoring call)
   - Update logging to reflect HIL handles everything
   - Update session mapping to track single monitoring source

2. **File: `/services/dedicated_labjack_monitor.py`**
   - Verify lines 450-470 properly pass all detection config
   - Ensure continuous_mode, steady_high_logging, etc. are passed
   - Add comprehensive logging for observability

#### Phase 2: Testing (1-2 hours)

1. **Unit Tests**
   - Verify single thread started per session
   - Verify all config parameters passed correctly
   - Verify WebSocket emissions work

2. **Integration Tests**
   - Single video test with detection
   - Multi-video sequence test
   - Stream mode test (high frequency)
   - Continuous mode test
   - Auto-stop test (based on video duration)

3. **Validation Tests**
   - Check database for duplicate events (should be zero)
   - Verify timing accuracy (±1-2ms)
   - Verify ground truth matching works
   - Verify video-relative timestamps correct

#### Phase 3: Validation (30 minutes)

1. Run full test suite
2. Check logs for errors
3. Verify no performance regression
4. Document changes

### Rollback Plan

If issues arise:
1. Restore lines 174-193 in raw_labjack_integration.py
2. Restart services
3. Debug offline

---

## 6. Code Sketches for Option A

### Before (Current - Causes Conflicts)

```python
# raw_labjack_integration.py:158-193

# Start HIL monitoring with video sync
hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
    test_session_id, video_timing_config
)  # ← Starts monitoring thread #1

# Start basic detection monitoring
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10
)  # ← Starts monitoring thread #2 (CONFLICT!)

# Both threads sample same hardware → duplicates, conflicts
```

### After (Option A - Clean Integration)

```python
# raw_labjack_integration.py:158-175

# Single entry point - HIL monitor handles everything
if video_config:
    # HIL monitor orchestrates detection service internally
    hil_success = await self.dedicated_monitor.start_monitoring_with_video_sync(
        test_session_id, video_timing_config
    )  # ← Single monitoring thread, no conflicts

    session_active = hil_success

    if hil_success:
        logger.info(f"✅ HIL monitoring started (includes detection) for {test_session_id}")
        logger.info(f"   → Video timing: ENABLED")
        logger.info(f"   → Ground truth: ENABLED")
        logger.info(f"   → Detection monitoring: ENABLED via HIL orchestration")
    else:
        logger.warning(f"⚠️ HIL monitoring failed for {test_session_id}")
else:
    # No video config - use basic detection service directly
    detection_success = self.detection_service.start_monitoring(
        test_session_id,
        channels=channels,
        voltage_threshold=self.config.detection_threshold_volts,
        sample_rate=10
    )
    session_active = detection_success

# Clean: Only ONE monitoring thread per session, all features intact
```

### Internal Flow in HIL Monitor

```python
# dedicated_labjack_monitor.py:226-470

async def start_monitoring_with_video_sync(self, session_id: str, video_timing_config: Dict[str, Any]) -> bool:
    """
    Single entry point for HIL monitoring.
    Orchestrates video timing + detection monitoring.
    """
    try:
        # 1. Setup video timing service
        video_id = video_timing_config.get('video_id')
        await self.video_timing_service.start_video_timing(session_id, video_id, ...)

        # 2. Configure detection monitoring with video metadata
        labjack_config = {
            'channels': video_timing_config.get('channels', ['AIN0']),
            'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),
            'debounce_ms': video_timing_config.get('debounce_ms', 0),
            'sample_rate': video_timing_config.get('sample_rate', 1000),
            'store_in_db': True,
            'enable_websocket': True,

            # Pass through all detection features
            'continuous_mode': video_timing_config.get('continuous_mode', False),
            'continuous_lower_bound': video_timing_config.get('continuous_lower_bound'),
            'continuous_upper_bound': video_timing_config.get('continuous_upper_bound'),
            'continuous_interval_ms': video_timing_config.get('continuous_interval_ms', 20),
            'steady_high_logging': video_timing_config.get('steady_high_logging', True),
            'steady_high_interval_ms': video_timing_config.get('steady_high_interval_ms', 10),
            'use_stream_mode': video_timing_config.get('sample_rate', 1000) >= 200,

            # Add video metadata for auto-stop
            'metadata': {
                'video_id': video_id,
                'duration': video_timing_config.get('duration'),
                'video_start_time': video_timing_config.get('video_start_time'),
            }
        }

        # 3. Register detection callback for video timing enhancement
        self.labjack_monitor.register_detection_callback(
            session_id,
            self._on_detection_with_video_timing
        )

        # 4. Start detection monitoring (SINGLE THREAD)
        success = self.labjack_monitor.start_monitoring(session_id, **labjack_config)

        if success:
            logger.info(f"✅ HIL orchestration complete for {session_id}")
            logger.info(f"   → Detection monitoring: ACTIVE")
            logger.info(f"   → Video timing: SYNCED")
            logger.info(f"   → Ground truth: READY")

        return success

    except Exception as e:
        logger.error(f"HIL orchestration failed: {e}")
        return False

async def _on_detection_with_video_timing(self, event: DetectionEvent):
    """
    Callback that enhances detection events with video timing.
    Called by detection service when event detected.
    """
    session_id = event.session_id

    # Convert Unix timestamp to video-relative
    video_ts = self.video_timing_service.convert_to_video_time(
        session_id, event.unix_timestamp
    )

    # Enhance event with video timing metadata
    event.video_relative_timestamp = video_ts
    event.video_frame_number = self._calculate_frame_number(video_ts, session_id)
    event.timing_sync_quality = "HIGH"

    # Capture screenshot for ground truth if needed
    if self._should_capture_screenshot(event):
        screenshot_path = await self.hil_comparison.capture_screenshot(
            session_id, event.video_frame_number
        )
        event.screenshot_path = screenshot_path

    # Event automatically stored by detection service
    return event
```

---

## 7. Summary Comparison Table

| Criteria | Option A: HIL Orchestrator | Option B: Plugin Architecture | Option C: Shared Core |
|----------|---------------------------|------------------------------|----------------------|
| **Code Changes** | 2 files, ~40 lines | 4 files, ~600 lines | 5+ files, ~1500 lines |
| **Lines of Code Modified** | ~40 | ~600 | ~1500+ |
| **New Files Created** | 0 | 1 (plugin) | 3 (base + interfaces) |
| **Risk Level** | ✅ LOW | ⚠️ MEDIUM | 🔴 HIGH |
| **Implementation Time** | 2-3 hours | 1-2 days | 3-5 days |
| **Testing Effort** | 1-2 hours | 4-6 hours | 8-12 hours |
| **Breaking Changes** | None | Few (plugin interface) | Many (all callers) |
| **Code Reusability** | Medium | High | Highest |
| **Extensibility** | Low | High | Highest |
| **Maintenance Burden** | Low | Medium | Higher |
| **Preserves Features** | ✅ All | ✅ All | ✅ All |
| **Solves Duplication** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Performance Impact** | None | Minimal | Minimal |
| **Rollback Difficulty** | ✅ Easy | ⚠️ Moderate | 🔴 Difficult |

---

## 8. Final Recommendation

### **Choose Option A: HIL Monitor as Orchestrator**

**Reasoning:**
1. **Solves the problem**: Eliminates hardware conflicts and duplicates ✅
2. **Minimal risk**: Only 40 lines changed, easy rollback ✅
3. **Fast implementation**: 2-3 hours total ✅
4. **Preserves all features**: Video sync, ground truth, detection, etc. ✅
5. **No breaking changes**: Other code unaffected ✅
6. **Production-ready**: Can deploy same day after testing ✅

**When to Consider Other Options:**
- **Option B** if future needs many specialized detection modes (ML, anomaly, etc.)
- **Option C** if planning major refactoring anyway or need maximum code reuse

**Action Plan:**
1. Implement Option A today (2-3 hours)
2. Test thoroughly (1-2 hours)
3. Deploy to production
4. Monitor for issues
5. If future extensibility needed, migrate to Option B incrementally

---

## 9. Integration Points Reference

### Key Files and Their Roles

| File | Role | Lines | Depends On |
|------|------|-------|------------|
| `raw_labjack_integration.py` | Entry point | ~400 | HIL Monitor, Detection Service |
| `dedicated_labjack_monitor.py` | HIL orchestrator | 2079 | Detection Service, Video Timing |
| `labjack_detection_service.py` | Hardware interface | 2315 | LabJack Service |
| `video_timing_service.py` | Timestamp conversion | ~500 | Video records |
| `hil_screenshot_service.py` | Ground truth capture | ~300 | Video playback |
| `detection_window_clamp_service.py` | Overlap prevention | ~200 | Video sequences |

### Critical Integration Points

1. **Hardware Access**
   - `labjack_service.py` → LabJack USB device
   - MUST be single-threaded per device

2. **Timestamp Conversion**
   - Unix timestamp (LabJack) → Video-relative timestamp (HIL)
   - `video_timing_service.convert_to_video_time()`

3. **Event Storage**
   - `detection_events` table (database)
   - Batched writes for performance
   - Dual-write to TS ingestion endpoint

4. **Real-time Updates**
   - WebSocket emission via `websocket_emit_fn`
   - FastAPI WebSocket manager

---

## 10. Conclusion

**Option A (HIL Monitor as Orchestrator)** provides the optimal balance of:
- ✅ Minimal code changes
- ✅ Low risk
- ✅ Fast implementation
- ✅ Preserves all features
- ✅ Solves root problem

This architecture achieves the goal of combining best features with minimal changes while maintaining ±1-2ms timing accuracy, video synchronization, ground truth validation, and zero duplicates.

**Estimated Total Time**: 3-4 hours (implementation + testing + validation)
**Risk Assessment**: LOW ✅
**Recommendation**: PROCEED with Option A
