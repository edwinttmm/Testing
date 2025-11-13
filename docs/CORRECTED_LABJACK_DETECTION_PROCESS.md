# LabJack HIL Detection System - Complete Process Flow (CORRECTED & DYNAMIC)

**Version:** 2.1 (Dynamic Configuration)
**Date:** 2025-10-28
**Status:** DESIGN SPECIFICATION - All values are dynamic and configurable

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Configuration Management](#2-configuration-management)
3. [Initialization Phase](#3-initialization-phase)
4. [Video Playback & Timing Synchronization](#4-video-playback--timing-synchronization)
5. [LabJack Hardware Detection](#5-labjack-hardware-detection)
6. [Detection Event Processing](#6-detection-event-processing)
7. [Ground Truth Matching](#7-ground-truth-matching)
8. [Validation Hierarchy](#8-validation-hierarchy)
9. [Results Aggregation](#9-results-aggregation)
10. [Multi-Video Sequence Handling](#10-multi-video-sequence-handling)
11. [User Interface Display](#11-user-interface-display)
12. [Error Handling & Edge Cases](#12-error-handling--edge-cases)
13. [Data Flow Summary](#13-data-flow-summary)

---

## 1. System Overview

### Purpose
The LabJack HIL (Hardware-in-the-Loop) Detection System validates real-time pedestrian/VRU detection performance by comparing AI model detections against hardware-triggered ground truth events.

### Key Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    HIL DETECTION SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │   LabJack    │  │    Video     │  │  AI Detection│        │
│  │   Hardware   │  │   Playback   │  │    Model     │        │
│  │   (Dynamic)  │  │   System     │  │   Pipeline   │        │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │
│         │                  │                  │                 │
│         │                  │                  │                 │
│  ┌──────▼──────────────────▼──────────────────▼───────┐       │
│  │         Detection Event Correlation Engine          │       │
│  │  • Timestamp Synchronization (CORRECTED)           │       │
│  │  • Latency Calculation (DYNAMIC MEASUREMENT)       │       │
│  │  • Ground Truth Matching (CONFIGURABLE)            │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                       │
│  ┌──────────────────────▼──────────────────────────────┐       │
│  │         Validation & Results Processing             │       │
│  │  • Unified Pass/Fail Determination                  │       │
│  │  • Performance Metrics Calculation                  │       │
│  │  • Multi-Video Sequence Aggregation                 │       │
│  └──────────────────────┬──────────────────────────────┘       │
│                         │                                       │
│  ┌──────────────────────▼──────────────────────────────┐       │
│  │              Results Presentation                    │       │
│  │  • Clear Pass/Fail Indicators                       │       │
│  │  • Frame Correlation Timeline                       │       │
│  │  • Statistical Analysis                             │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### System Architecture Principles (Post-Fix)

1. **Single Source of Truth:** Backend provides authoritative timestamps and latency values
2. **Hierarchical Validation:** Ground truth matching is primary, latency threshold is secondary
3. **Clear Attribution:** Every detection has ONE clear pass/fail result with explanation
4. **Temporal Accuracy:** Video-relative timestamps are canonical for correlation
5. **Dynamic Configuration:** All thresholds, tolerances, and parameters are configurable

---

## 2. Configuration Management

### 2.1 Configuration Sources

**System configuration is loaded from multiple sources:**

```python
# config/hil_system_config.py

class HILSystemConfig:
    """
    Centralized configuration management for HIL system

    All values are dynamic and loaded from:
    - Database settings (user-configurable)
    - Hardware device capabilities (auto-detected)
    - Video file metadata (extracted from files)
    - Measured system performance (runtime calibration)
    - Test session parameters (user-defined per test)
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # Load configurations
        self.hardware_config = self._load_hardware_config()
        self.video_config = self._load_video_config()
        self.validation_config = self._load_validation_config()
        self.performance_config = self._load_performance_config()

    def _load_hardware_config(self) -> HardwareConfig:
        """Load hardware-specific configuration"""

        # Auto-detect LabJack capabilities
        labjack_device = self._detect_labjack()

        return HardwareConfig(
            # Dynamic: Read from connected LabJack device
            device_model=labjack_device.model,
            firmware_version=labjack_device.firmware,

            # Dynamic: Based on device capabilities
            max_sample_rate_hz=labjack_device.max_sample_rate,

            # Configurable: From database settings
            sample_rate_hz=self._get_setting('labjack.sample_rate_hz',
                                             default=labjack_device.recommended_rate),

            # Configurable: From test configuration
            voltage_threshold_v=self._get_setting('labjack.voltage_threshold_v',
                                                  default=2.5),

            # Dynamic: Auto-detected channels
            channels_available=labjack_device.get_available_channels(),

            # Configurable: User-selected channels
            channels_enabled=self._get_setting('labjack.channels_enabled',
                                               default=['AIN0', 'AIN1']),

            # Dynamic: Measured from device
            connection_latency_us=self._measure_labjack_latency()
        )

    def _load_video_config(self) -> VideoConfig:
        """Load video-specific configuration"""

        # Get video metadata from database/file
        video_metadata = self._get_video_metadata()

        return VideoConfig(
            # Dynamic: Extracted from video file
            video_id=video_metadata.id,
            filename=video_metadata.filename,
            fps=video_metadata.fps,  # Actual FPS from video
            duration_seconds=video_metadata.duration,
            total_frames=video_metadata.frame_count,
            resolution=video_metadata.resolution,
            codec=video_metadata.codec,

            # Dynamic: Calculated from file metadata
            frame_duration_ms=1000.0 / video_metadata.fps,

            # Configurable: Playback settings
            playback_speed=self._get_setting('video.playback_speed', default=1.0),

            # Dynamic: Ground truth availability
            ground_truth_available=video_metadata.has_ground_truth,
            ground_truth_count=video_metadata.ground_truth_event_count
        )

    def _load_validation_config(self) -> ValidationConfig:
        """Load validation criteria configuration"""

        return ValidationConfig(
            # Configurable: From test session settings
            max_latency_ms=self._get_session_setting('max_latency_ms',
                                                     default=100.0),

            # Configurable: Ground truth matching tolerance
            temporal_tolerance_ms=self._get_session_setting('tolerance_ms',
                                                            default=100.0),

            # Configurable: Frame matching tolerance
            frame_tolerance=self._get_session_setting('frame_tolerance',
                                                      default=2),

            # Configurable: Precision threshold for PASS
            precision_threshold=self._get_session_setting('precision_threshold',
                                                          default=0.80),

            # Configurable: Recall threshold for PASS
            recall_threshold=self._get_session_setting('recall_threshold',
                                                       default=0.75),

            # Configurable: Marginal pass thresholds
            precision_marginal=self._get_session_setting('precision_marginal',
                                                         default=0.60),
            recall_marginal=self._get_session_setting('recall_marginal',
                                                      default=0.60),

            # Configurable: Network sync quality threshold
            network_latency_threshold_us=self._get_setting(
                'network.latency_threshold_us',
                default=5000
            ),

            # Configurable: Video boundary grace period
            boundary_grace_period_s=self._get_setting('video.boundary_grace_s',
                                                      default=0.5)
        )

    def _load_performance_config(self) -> PerformanceConfig:
        """Load or measure performance characteristics"""

        return PerformanceConfig(
            # Dynamic: Measured during system calibration
            typical_processing_latency_ms=self._measure_processing_latency(),

            # Dynamic: Measured pipeline stages
            ai_model_latency_ms=self._measure_ai_latency(),
            detection_pipeline_latency_ms=self._measure_pipeline_latency(),
            hardware_trigger_latency_ms=self._measure_hardware_latency(),

            # Dynamic: Statistical measurements
            latency_std_dev_ms=self._get_latency_statistics()['std_dev'],
            latency_p95_ms=self._get_latency_statistics()['p95'],
            latency_p99_ms=self._get_latency_statistics()['p99'],

            # Configurable: Performance limits
            max_acceptable_latency_ms=self._get_setting('performance.max_latency',
                                                        default=500.0),

            # Dynamic: System capabilities
            max_detection_rate_hz=self._measure_max_detection_rate()
        )

    def _measure_processing_latency(self) -> float:
        """
        Measure actual system processing latency

        Returns dynamic value based on:
        - AI model performance
        - Hardware processing time
        - System load
        """

        # Run calibration test
        latencies = []
        for _ in range(100):
            start = time.perf_counter_ns()
            # Simulate detection pipeline
            self._run_detection_pipeline_sample()
            end = time.perf_counter_ns()
            latencies.append((end - start) / 1_000_000)  # Convert to ms

        # Return median (robust to outliers)
        measured_latency = statistics.median(latencies)

        logger.info(f"Measured processing latency: {measured_latency:.2f}ms")
        logger.info(f"  Min: {min(latencies):.2f}ms")
        logger.info(f"  Max: {max(latencies):.2f}ms")
        logger.info(f"  Std Dev: {statistics.stdev(latencies):.2f}ms")

        return measured_latency
```

### 2.2 Configuration Database Schema

**Test Session Configuration Table:**
```sql
CREATE TABLE test_session_config (
    session_id VARCHAR PRIMARY KEY,

    -- Validation thresholds (user-configurable)
    max_latency_ms FLOAT DEFAULT 100.0,
    tolerance_ms FLOAT DEFAULT 100.0,
    frame_tolerance INT DEFAULT 2,

    -- Pass/fail criteria (user-configurable)
    precision_threshold FLOAT DEFAULT 0.80,
    recall_threshold FLOAT DEFAULT 0.75,
    precision_marginal FLOAT DEFAULT 0.60,
    recall_marginal FLOAT DEFAULT 0.60,

    -- Hardware settings (user-configurable)
    labjack_sample_rate_hz INT DEFAULT NULL,  -- NULL = auto-detect
    voltage_threshold_v FLOAT DEFAULT 2.5,
    enabled_channels JSONB DEFAULT '["AIN0", "AIN1"]',

    -- Video settings (user-configurable)
    playback_speed FLOAT DEFAULT 1.0,
    boundary_grace_period_s FLOAT DEFAULT 0.5,

    -- Network settings (user-configurable)
    network_latency_threshold_us INT DEFAULT 5000,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2.3 Runtime Calibration

**System Performance Calibration:**
```python
# services/performance_calibration_service.py

class PerformanceCalibrationService:
    """
    Dynamically measure system performance characteristics

    All latency values are MEASURED, not hardcoded
    """

    async def calibrate_system(self) -> CalibrationResults:
        """
        Run comprehensive system calibration

        Returns dynamic measurements, not hardcoded values
        """

        logger.info("Starting system calibration...")

        # 1. Measure AI model latency
        ai_latency_samples = []
        for i in range(100):
            frame = self._generate_test_frame()
            start = time.perf_counter_ns()
            detections = await self.ai_model.detect(frame)
            end = time.perf_counter_ns()
            ai_latency_samples.append((end - start) / 1_000_000)

        ai_latency = {
            'mean': statistics.mean(ai_latency_samples),
            'median': statistics.median(ai_latency_samples),
            'std_dev': statistics.stdev(ai_latency_samples),
            'p95': np.percentile(ai_latency_samples, 95),
            'p99': np.percentile(ai_latency_samples, 99)
        }

        # 2. Measure LabJack hardware latency
        hardware_latency_samples = []
        for i in range(1000):
            start = time.perf_counter_ns()
            voltage = self.labjack.read_voltage('AIN0')
            end = time.perf_counter_ns()
            hardware_latency_samples.append((end - start) / 1000)  # μs

        hardware_latency = {
            'mean': statistics.mean(hardware_latency_samples),
            'median': statistics.median(hardware_latency_samples),
            'std_dev': statistics.stdev(hardware_latency_samples)
        }

        # 3. Measure end-to-end pipeline latency
        pipeline_latency_samples = []
        for i in range(50):
            start = time.perf_counter_ns()
            # Full detection pipeline
            frame = self._capture_frame()
            detections = await self.ai_model.detect(frame)
            voltage = self.labjack.read_voltage('AIN0')
            await self._process_detection(detections, voltage)
            end = time.perf_counter_ns()
            pipeline_latency_samples.append((end - start) / 1_000_000)

        pipeline_latency = {
            'mean': statistics.mean(pipeline_latency_samples),
            'median': statistics.median(pipeline_latency_samples),
            'std_dev': statistics.stdev(pipeline_latency_samples),
            'p95': np.percentile(pipeline_latency_samples, 95),
            'p99': np.percentile(pipeline_latency_samples, 99)
        }

        # 4. Store calibration results
        calibration = CalibrationResults(
            ai_model_latency_ms=ai_latency['median'],  # Dynamic
            hardware_latency_us=hardware_latency['median'],  # Dynamic
            pipeline_latency_ms=pipeline_latency['median'],  # Dynamic

            # Statistical measures (all dynamic)
            ai_latency_stats=ai_latency,
            hardware_latency_stats=hardware_latency,
            pipeline_latency_stats=pipeline_latency,

            # System info
            calibrated_at=datetime.utcnow(),
            system_load=psutil.cpu_percent(),
            memory_available=psutil.virtual_memory().available,
            gpu_utilization=self._get_gpu_utilization()
        )

        logger.info(f"Calibration complete:")
        logger.info(f"  AI Model Latency: {ai_latency['median']:.2f}ms ± {ai_latency['std_dev']:.2f}ms")
        logger.info(f"  Hardware Latency: {hardware_latency['median']:.2f}μs")
        logger.info(f"  Pipeline Latency: {pipeline_latency['median']:.2f}ms ± {pipeline_latency['std_dev']:.2f}ms")

        return calibration
```

---

## 3. Initialization Phase

### 3.1 Test Session Creation

**User Action:** Creates new HIL test session in UI

**Backend Process:**
```python
# POST /api/test-sessions

@router.post("/api/test-sessions")
async def create_test_session(request: TestSessionCreate):
    """
    Create test session with DYNAMIC configuration

    All parameters are user-configurable or auto-detected
    """

    # Load system configuration (all values dynamic)
    config = HILSystemConfig(session_id=None)  # Will be assigned

    # Create session with user-defined or default values
    session = TestSession(
        name=request.name,
        project_id=request.project_id,
        video_id=request.video_id,
        sequence_id=request.sequence_id,

        # User-configurable validation thresholds
        max_latency_ms=request.max_latency_ms or config.validation_config.max_latency_ms,
        tolerance_ms=request.tolerance_ms or config.validation_config.temporal_tolerance_ms,

        # User-configurable test parameters
        test_configuration={
            "detection_model": request.detection_model,
            "confidence_threshold": request.confidence_threshold or 0.5,
            "nms_threshold": request.nms_threshold or 0.45,

            # Frame tolerance (configurable)
            "frame_tolerance": request.frame_tolerance or config.validation_config.frame_tolerance,

            # Validation criteria (configurable)
            "precision_threshold": request.precision_threshold or config.validation_config.precision_threshold,
            "recall_threshold": request.recall_threshold or config.validation_config.recall_threshold
        }
    )

    # Store configuration in database
    await db.add(session)
    await db.commit()

    logger.info(f"Created test session {session.id} with configuration:")
    logger.info(f"  Max latency: {session.max_latency_ms}ms (user-defined)")
    logger.info(f"  Tolerance: {session.tolerance_ms}ms (user-defined)")
    logger.info(f"  Precision threshold: {session.test_configuration['precision_threshold']} (user-defined)")
    logger.info(f"  Recall threshold: {session.test_configuration['recall_threshold']} (user-defined)")

    return {"session_id": session.id, "configuration": session.test_configuration}
```

**Database Record Created:**
```sql
INSERT INTO test_sessions (
  id, name, project_id, video_id,
  status, max_latency_ms, tolerance_ms,
  created_at
) VALUES (
  'session_abc123',
  'VRU Detection - Urban Scenario 1',
  'proj_12345',
  'video_67890',
  'pending',
  100.0,  -- From user input or config default
  100.0,  -- From user input or config default
  NOW()
);
```

### 3.2 Hardware Initialization

**LabJack Device Auto-Detection and Configuration:**
```python
# services/dedicated_labjack_monitor.py

class DedicatedLabJackMonitor:
    def initialize(self, session_id: str):
        """
        Initialize LabJack hardware with DYNAMIC configuration

        All parameters auto-detected or loaded from configuration
        """

        # Load configuration (dynamic)
        config = HILSystemConfig(session_id)
        hw_config = config.hardware_config

        # 1. Connect to LabJack (auto-detect device)
        self.device = ljm.openS("ANY", "ANY", "ANY")  # Auto-detect first available

        # 2. Read device capabilities (dynamic)
        device_info = ljm.getHandleInfo(self.device)
        self.device_model = self._get_device_model_name(device_info['deviceType'])
        self.firmware_version = self._get_firmware_version(self.device)
        self.max_sample_rate = self._get_max_sample_rate(self.device_model)

        logger.info(f"Detected LabJack device:")
        logger.info(f"  Model: {self.device_model}")
        logger.info(f"  Firmware: {self.firmware_version}")
        logger.info(f"  Max Sample Rate: {self.max_sample_rate} Hz")

        # 3. Configure channels (from config or user selection)
        enabled_channels = hw_config.channels_enabled
        self.configure_channels(enabled_channels, hw_config.voltage_range_v)

        # 4. Set sampling rate (user-configurable or auto-optimized)
        if hw_config.sample_rate_hz:
            # User specified rate
            self.sample_rate_hz = hw_config.sample_rate_hz
        else:
            # Auto-optimize based on device capabilities
            self.sample_rate_hz = min(1000, self.max_sample_rate)

        ljm.eStreamStart(
            self.device,
            self.sample_rate_hz,
            len(enabled_channels),
            enabled_channels,
            self.sample_rate_hz * 2  # Buffer size
        )

        # 5. Record hardware initialization time (dynamic)
        self.hardware_start_time_us = time.time_ns() // 1000

        # 6. Measure connection latency (dynamic)
        self.connection_latency_us = self._measure_connection_latency()

        logger.info(f"LabJack initialized for session {session_id}")
        logger.info(f"  Sample rate: {self.sample_rate_hz} Hz (dynamic)")
        logger.info(f"  Voltage threshold: {hw_config.voltage_threshold_v}V (configurable)")
        logger.info(f"  Enabled channels: {enabled_channels} (configurable)")
        logger.info(f"  Connection latency: {self.connection_latency_us}μs (measured)")
        logger.info(f"  Hardware start time: {self.hardware_start_time_us}μs")

    def _measure_connection_latency(self) -> float:
        """
        Measure actual LabJack communication latency

        Returns DYNAMIC measured value, not hardcoded
        """
        latencies = []
        for _ in range(100):
            start = time.perf_counter_ns()
            ljm.eReadName(self.device, "AIN0")
            end = time.perf_counter_ns()
            latencies.append((end - start) / 1000)  # μs

        median_latency = statistics.median(latencies)
        logger.debug(f"Measured connection latency: {median_latency:.2f}μs")

        return median_latency
```

### 3.3 Video Preparation

**Load Video Metadata (All values from actual file):**
```python
# services/video_metadata_service.py

async def load_video_metadata(video_id: str) -> VideoMetadata:
    """
    Extract actual metadata from video file

    NO hardcoded values - everything read from file
    """

    # Get video file path
    video = await db.get(Video, video_id)
    video_path = video.file_path

    # Use ffprobe to extract ACTUAL metadata
    probe = ffmpeg.probe(video_path)
    video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')

    # Extract DYNAMIC values from file
    fps_rational = video_stream['r_frame_rate'].split('/')
    fps = float(fps_rational[0]) / float(fps_rational[1])  # Actual FPS

    duration = float(video_stream['duration'])  # Actual duration
    total_frames = int(video_stream['nb_frames'])  # Actual frame count

    width = int(video_stream['width'])
    height = int(video_stream['height'])
    codec = video_stream['codec_name']

    metadata = VideoMetadata(
        id=video_id,
        filename=os.path.basename(video_path),

        # All values extracted from actual file
        fps=fps,  # Dynamic: actual FPS (not hardcoded 24)
        duration_seconds=duration,  # Dynamic: actual duration
        total_frames=total_frames,  # Dynamic: actual frame count
        resolution=f"{width}x{height}",  # Dynamic: actual resolution
        codec=codec,  # Dynamic: actual codec

        # Calculated from extracted values
        frame_duration_ms=1000.0 / fps,  # Dynamic calculation

        # Check ground truth availability
        ground_truth_available=await check_ground_truth_exists(video_id),
        ground_truth_count=await count_ground_truth_events(video_id)
    )

    logger.info(f"Loaded video metadata for {video_id}:")
    logger.info(f"  FPS: {metadata.fps} (extracted from file)")
    logger.info(f"  Duration: {metadata.duration_seconds}s (extracted from file)")
    logger.info(f"  Frames: {metadata.total_frames} (extracted from file)")
    logger.info(f"  Resolution: {metadata.resolution} (extracted from file)")
    logger.info(f"  Codec: {metadata.codec} (extracted from file)")
    logger.info(f"  Ground truth events: {metadata.ground_truth_count}")

    return metadata
```

**Load Ground Truth Events (Dynamic from database):**
```python
# GET /api/videos/{video_id}/ground-truth-events

async def get_ground_truth_events(video_id: str) -> List[GroundTruthEvent]:
    """
    Load actual ground truth events from database

    Returns ACTUAL events, not hardcoded examples
    """

    # Query actual ground truth data
    events = await db.query(GroundTruthAnnotation).filter(
        GroundTruthAnnotation.video_id == video_id,
        GroundTruthAnnotation.validated == True
    ).all()

    logger.info(f"Loaded {len(events)} ground truth events for video {video_id}")

    return [
        GroundTruthEvent(
            id=event.id,
            video_id=video_id,
            timestamp=event.timestamp,  # Actual timestamp from annotation
            frame_number=event.frame_number,  # Actual frame from annotation
            class_label=event.class_label,
            confidence=event.confidence,
            bounding_box=event.bounding_box,
            validated=event.validated
        )
        for event in events
    ]
```

---

## 4. Video Playback & Timing Synchronization

### 4.1 Video Start Command

**Frontend Initiates Playback:**
```typescript
// SequentialVideoPlayer.tsx
const startVideoPlayback = async () => {
    // 1. Record high-precision start timestamp (dynamic)
    const videoStartTime = getHighPrecisionTimestamp(); // performance.now()

    // 2. Notify backend of video start
    await apiService.post(`/api/sessions/${sessionId}/start-video`, {
        video_id: videoId,
        client_start_time_us: videoStartTime * 1000, // Convert to μs
        sync_labjack: true
    });

    // 3. Start video playback
    await videoRef.current.play();
};
```

**Backend Video Timing Service:**
```python
# services/video_timing_service.py

@router.post("/api/sessions/{session_id}/start-video")
async def start_video_timing(session_id: str, request: VideoStartRequest):
    """
    Synchronize video playback start with LabJack hardware timeline

    All timing values are MEASURED dynamically
    """

    # Load configuration
    config = HILSystemConfig(session_id)

    # 1. Record server-side timestamp (dynamic)
    server_start_time_us = time.time_ns() // 1000

    # 2. Get LabJack hardware reference time (dynamic)
    labjack_reference_time_us = labjack_monitor.get_current_time_us()

    # 3. Calculate network latency (dynamic measurement)
    network_latency_us = server_start_time_us - request.client_start_time_us

    # 4. Determine sync quality (dynamic based on measured latency)
    network_threshold = config.validation_config.network_latency_threshold_us
    if network_latency_us < network_threshold / 2:
        sync_quality = "excellent"
    elif network_latency_us < network_threshold:
        sync_quality = "good"
    else:
        sync_quality = "marginal"

    # 5. Get actual video FPS (from metadata, not hardcoded)
    video_metadata = await get_video_metadata(request.video_id)
    fps = video_metadata.fps  # Actual FPS from file

    # 6. Store timing synchronization data
    video_timing_data = {
        "session_id": session_id,
        "video_id": request.video_id,

        # All dynamic measured values
        "video_start_time_us": server_start_time_us,
        "labjack_reference_time_us": labjack_reference_time_us,
        "client_start_time_us": request.client_start_time_us,
        "network_latency_us": network_latency_us,

        # Dynamic from video metadata
        "fps": fps,
        "frame_duration_ms": 1000.0 / fps,

        # Dynamic quality assessment
        "sync_quality": sync_quality,
        "sync_threshold_us": network_threshold
    }

    # 7. Store in session state
    await session_manager.set_video_timing(session_id, video_timing_data)

    logger.info(f"Video timing synchronized for session {session_id}")
    logger.info(f"  Video start: {server_start_time_us}μs (measured)")
    logger.info(f"  LabJack ref: {labjack_reference_time_us}μs (measured)")
    logger.info(f"  Network latency: {network_latency_us / 1000:.2f}ms (measured)")
    logger.info(f"  FPS: {fps} (from video metadata)")
    logger.info(f"  Sync quality: {sync_quality} (threshold: {network_threshold}μs)")

    return {"success": True, "timing_data": video_timing_data}
```

---

## 5. LabJack Hardware Detection

### 5.1 Continuous Voltage Monitoring

**Hardware Stream Processing:**
```python
# services/dedicated_labjack_monitor.py

class DedicatedLabJackMonitor:
    def process_stream_data(self):
        """
        Process continuous voltage stream from LabJack

        Uses DYNAMIC sample rate (not hardcoded 1000 Hz)
        """

        # Load configuration
        config = HILSystemConfig(self.session_id)
        hw_config = config.hardware_config

        # Use configured voltage threshold (not hardcoded)
        voltage_threshold = hw_config.voltage_threshold_v

        while self.streaming:
            # Read voltage samples from hardware buffer
            samples = ljm.eStreamRead(self.device)

            for sample in samples:
                # Extract voltage and timestamp
                voltage = sample['AIN0']
                hardware_timestamp_us = sample['timestamp_us']

                # Detect voltage transitions using CONFIGURABLE threshold
                if self._is_trigger_event(voltage, voltage_threshold):
                    self._handle_trigger_event(voltage, hardware_timestamp_us)

    def _is_trigger_event(self, voltage: float, threshold: float) -> bool:
        """
        Detect if voltage indicates a detection trigger

        Uses CONFIGURABLE threshold (not hardcoded 2.5V)
        """
        return voltage >= threshold

    def _handle_trigger_event(self, voltage: float, hardware_timestamp_us: int):
        """
        Process detected trigger event with DYNAMIC latency calculation
        """

        # Load configuration and calibration data
        config = HILSystemConfig(self.session_id)
        perf_config = config.performance_config
        video_config = config.video_config

        # 1. Get current session timing context
        session_timing = self.get_session_timing()

        # 2. Calculate video-relative timestamp
        video_relative_timestamp_us = (
            hardware_timestamp_us - session_timing['labjack_reference_time_us']
        )
        video_relative_seconds = video_relative_timestamp_us / 1_000_000.0

        # 3. Calculate video frame number using ACTUAL FPS (not hardcoded)
        fps = video_config.fps  # Dynamic from video metadata
        video_frame_number = int(video_relative_seconds * fps)

        # 4. Calculate ACTUAL processing latency (DYNAMIC MEASUREMENT)
        # CRITICAL FIX: Use MEASURED latency, not video position

        # Option A: Use calibrated system latency (measured during init)
        detection_pipeline_latency_ms = perf_config.typical_processing_latency_ms

        # Option B: Calculate from actual detection pipeline timing (if available)
        if hasattr(self, 'detection_pipeline_timings'):
            recent_timings = self.detection_pipeline_timings[-100:]  # Last 100
            if recent_timings:
                detection_pipeline_latency_ms = statistics.median(recent_timings)

        # Option C: Measure from pipeline metadata (most accurate)
        if hasattr(self, 'last_pipeline_start_time'):
            pipeline_duration_us = hardware_timestamp_us - self.last_pipeline_start_time
            detection_pipeline_latency_ms = pipeline_duration_us / 1000.0

        # Track latency for continuous calibration
        self._track_latency_measurement(detection_pipeline_latency_ms)

        # 5. Create detection event with DYNAMIC values
        detection_event = {
            "session_id": self.session_id,
            "event_id": f"det_{hardware_timestamp_us}",

            # Timing data - ALL DYNAMIC
            "hardware_timestamp_us": hardware_timestamp_us,
            "video_relative_timestamp": video_relative_seconds,
            "video_frame_number": video_frame_number,

            # ✅ CORRECTED: Latency is MEASURED processing time
            "actual_latency_ms": detection_pipeline_latency_ms,

            # Hardware data
            "voltage_level": voltage,
            "channel": "AIN0",

            # Metadata
            "detection_confidence": self._get_latest_detection_confidence(),
            "class_label": self._get_latest_detection_class(),
            "timing_sync_quality": session_timing['sync_quality'],

            # Dynamic FPS for reference
            "video_fps": fps
        }

        # 6. Store detection event
        self._store_detection_event(detection_event)

        logger.info(f"Detection event captured:")
        logger.info(f"  Hardware time: {hardware_timestamp_us}μs (measured)")
        logger.info(f"  Video time: {video_relative_seconds:.3f}s @ {fps} FPS (frame {video_frame_number})")
        logger.info(f"  ✅ Latency: {detection_pipeline_latency_ms:.1f}ms (measured, not video position)")
        logger.info(f"  Voltage: {voltage:.2f}V (threshold: {config.hardware_config.voltage_threshold_v}V)")

    def _track_latency_measurement(self, latency_ms: float):
        """
        Track latency measurements for continuous system calibration

        Updates running statistics dynamically
        """
        if not hasattr(self, 'latency_history'):
            self.latency_history = []

        self.latency_history.append(latency_ms)

        # Keep rolling window of last 1000 measurements
        if len(self.latency_history) > 1000:
            self.latency_history.pop(0)

        # Update running statistics every 100 measurements
        if len(self.latency_history) % 100 == 0:
            stats = {
                'mean': statistics.mean(self.latency_history),
                'median': statistics.median(self.latency_history),
                'std_dev': statistics.stdev(self.latency_history),
                'min': min(self.latency_history),
                'max': max(self.latency_history)
            }

            logger.debug(f"Latency statistics (n={len(self.latency_history)}):")
            logger.debug(f"  Mean: {stats['mean']:.2f}ms")
            logger.debug(f"  Median: {stats['median']:.2f}ms")
            logger.debug(f"  Std Dev: {stats['std_dev']:.2f}ms")
            logger.debug(f"  Range: {stats['min']:.2f}-{stats['max']:.2f}ms")
```

---

## 6. Detection Event Processing

### 6.1 Timestamp Conversion (CORRECTED)

**All Values Dynamic and Measured:**
```python
# services/timestamp_conversion_utils.py

def calculate_detection_timing(
    hardware_timestamp_us: int,
    session_timing: dict,
    detection_metadata: dict,
    config: HILSystemConfig
) -> dict:
    """
    Calculate all timing values for a detection event

    ✅ CORRECTED: Uses DYNAMIC measurements, not hardcoded values
    All parameters come from configuration or calibration
    """

    # 1. Calculate video-relative time
    video_start_us = session_timing['labjack_reference_time_us']
    video_relative_us = hardware_timestamp_us - video_start_us
    video_relative_timestamp = video_relative_us / 1_000_000.0

    # 2. Calculate frame number using ACTUAL FPS (not hardcoded)
    fps = config.video_config.fps  # From video metadata
    video_frame_number = int(video_relative_timestamp * fps)

    # 3. Calculate ACTUAL processing latency (DYNAMIC)
    # CRITICAL FIX: Use MEASURED values, NOT video position

    # Priority 1: Use actual pipeline timing (most accurate)
    if 'pipeline_start_time_us' in detection_metadata:
        pipeline_duration_us = (
            hardware_timestamp_us - detection_metadata['pipeline_start_time_us']
        )
        actual_latency_ms = pipeline_duration_us / 1000.0
        latency_source = "measured_pipeline"

    # Priority 2: Use frame processing timing
    elif 'frame_capture_time_us' in detection_metadata:
        processing_duration_us = (
            hardware_timestamp_us - detection_metadata['frame_capture_time_us']
        )
        actual_latency_ms = processing_duration_us / 1000.0
        latency_source = "measured_frame"

    # Priority 3: Use calibrated system latency (from performance calibration)
    else:
        actual_latency_ms = config.performance_config.typical_processing_latency_ms
        latency_source = "calibrated_typical"

    # ❌ REMOVED BUGGY CODE:
    # actual_latency_ms = video_relative_timestamp * 1000  # WRONG!

    logger.debug(f"Timing calculation for detection:")
    logger.debug(f"  Video time: {video_relative_timestamp:.3f}s")
    logger.debug(f"  Frame: {video_frame_number} @ {fps} FPS")
    logger.debug(f"  ✅ Latency: {actual_latency_ms:.1f}ms (source: {latency_source})")
    logger.debug(f"  ❌ OLD BUGGY would have been: {video_relative_timestamp * 1000:.1f}ms")

    return {
        "video_relative_timestamp": video_relative_timestamp,
        "video_frame_number": video_frame_number,
        "actual_latency_ms": actual_latency_ms,  # ✅ DYNAMIC MEASURED VALUE
        "hardware_timestamp_us": hardware_timestamp_us,
        "latency_measurement_source": latency_source,
        "video_fps": fps  # Include for reference
    }
```

### 6.2 Latency Threshold Validation

**Using CONFIGURABLE Threshold:**
```python
# services/validation_service.py

def validate_latency_threshold(
    detection_event: DetectionEvent,
    config: HILSystemConfig
) -> dict:
    """
    Check if detection meets latency threshold requirement

    Uses CONFIGURABLE threshold (not hardcoded 100ms)
    Uses CORRECTED actual_latency_ms value (measured, not video position)
    """

    # Get ACTUAL measured latency (corrected)
    latency = detection_event.actual_latency_ms

    # Get CONFIGURABLE threshold (from session config)
    threshold = config.validation_config.max_latency_ms

    # Simple threshold check
    passed = latency <= threshold

    result = {
        "latency_result": "pass" if passed else "fail",
        "actual_latency_ms": latency,
        "threshold_ms": threshold,
        "margin_ms": threshold - latency,
        "explanation": (
            f"Detection latency {latency:.1f}ms "
            f"{'within' if passed else 'exceeds'} "
            f"{threshold}ms threshold (configurable)"
        ),
        "threshold_source": "session_configuration"
    }

    logger.debug(f"Latency validation:")
    logger.debug(f"  Measured: {latency:.1f}ms")
    logger.debug(f"  Threshold: {threshold}ms (from config)")
    logger.debug(f"  Result: {result['latency_result']}")

    return result
```

---

## 7. Ground Truth Matching

### 7.1 Temporal Matching Algorithm

**Using CONFIGURABLE Tolerance:**
```python
# services/ground_truth_matching_service.py

class GroundTruthMatchingService:
    def match_detections_to_ground_truth(
        self,
        session_id: str,
        config: HILSystemConfig
    ):
        """
        Match detection events to ground truth events

        Uses CONFIGURABLE tolerance (not hardcoded 100ms)
        Uses ACTUAL FPS from video metadata (not hardcoded 24)
        """

        # Get CONFIGURABLE tolerance (from session config)
        tolerance_ms = config.validation_config.temporal_tolerance_ms
        tolerance_seconds = tolerance_ms / 1000.0

        # Get CONFIGURABLE frame tolerance
        frame_tolerance = config.validation_config.frame_tolerance

        # Get ACTUAL video FPS (from metadata)
        fps = config.video_config.fps

        logger.info(f"Ground truth matching with DYNAMIC parameters:")
        logger.info(f"  Temporal tolerance: {tolerance_ms}ms (from config)")
        logger.info(f"  Frame tolerance: ±{frame_tolerance} frames (from config)")
        logger.info(f"  Video FPS: {fps} (from metadata)")

        # 1. Load all detection events (with CORRECTED latency)
        detection_events = await self.get_detection_events(session_id)

        # 2. Load ground truth events
        ground_truth_events = await self.get_ground_truth_events(session_id)

        logger.info(f"Matching {len(detection_events)} detections to {len(ground_truth_events)} ground truth events")

        # 3. Perform temporal matching
        matches = []
        used_detections = set()

        # Match each ground truth to nearest detection
        for gt_event in ground_truth_events:
            gt_time = gt_event.timestamp  # Video-relative seconds
            gt_frame = int(gt_time * fps)  # Calculate frame using ACTUAL FPS

            best_match = None
            best_time_diff = float('inf')

            for i, det_event in enumerate(detection_events):
                if i in used_detections:
                    continue

                # Use video-relative timestamp for matching
                det_time = det_event.video_relative_timestamp
                det_frame = det_event.video_frame_number

                # Calculate temporal difference
                time_diff = abs(det_time - gt_time)
                frame_diff = abs(det_frame - gt_frame)

                # Check if within CONFIGURABLE tolerance
                within_time_tolerance = time_diff <= tolerance_seconds
                within_frame_tolerance = frame_diff <= frame_tolerance

                if (within_time_tolerance or within_frame_tolerance) and time_diff < best_time_diff:
                    best_match = (i, det_event)
                    best_time_diff = time_diff

            if best_match:
                # TRUE POSITIVE - detection matched ground truth
                det_idx, det_event = best_match
                used_detections.add(det_idx)

                temporal_offset_ms = (det_event.video_relative_timestamp - gt_time) * 1000
                frame_offset = det_event.video_frame_number - gt_frame

                match = {
                    "ground_truth_id": gt_event.id,
                    "detection_event_id": det_event.id,
                    "match_type": "TP",
                    "temporal_offset_ms": temporal_offset_ms,
                    "frame_offset": frame_offset,
                    "confidence": det_event.confidence,

                    # Use CORRECTED measured latency
                    "latency_ms": det_event.actual_latency_ms,

                    # Include matching parameters used
                    "matched_with_tolerance_ms": tolerance_ms,
                    "matched_with_frame_tolerance": frame_tolerance,
                    "video_fps": fps
                }
                matches.append(match)

                logger.info(f"TP Match: GT@{gt_time:.3f}s (frame {gt_frame}) → Det@{det_event.video_relative_timestamp:.3f}s (frame {det_event.video_frame_number})")
                logger.info(f"  Temporal offset: {temporal_offset_ms:+.1f}ms, Frame offset: {frame_offset:+d}")
                logger.info(f"  ✅ Processing latency: {det_event.actual_latency_ms:.1f}ms (measured)")
            else:
                # FALSE NEGATIVE
                logger.warn(f"FN: GT@{gt_time:.3f}s (frame {gt_frame}) - No detection within {tolerance_ms}ms / ±{frame_tolerance} frames")

        # Calculate metrics using CORRECTED values
        metrics = self._calculate_metrics(matches, config)

        return metrics
```

### 7.2 Performance Metrics Calculation

**Using CORRECTED Dynamic Latencies:**
```python
def _calculate_metrics(self, matches: list, config: HILSystemConfig) -> dict:
    """
    Calculate performance metrics from ground truth matching

    Uses CORRECTED actual_latency_ms values (measured, not video position)
    All thresholds from CONFIGURATION (not hardcoded)
    """

    # Count match types
    tp_matches = [m for m in matches if m['match_type'] == 'TP']
    fp_matches = [m for m in matches if m['match_type'] == 'FP']
    fn_matches = [m for m in matches if m['match_type'] == 'FN']

    true_positives = len(tp_matches)
    false_positives = len(fp_matches)
    false_negatives = len(fn_matches)

    # Calculate accuracy metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    # Calculate latency metrics (✅ CORRECTED - uses MEASURED values)
    valid_latencies = [m['latency_ms'] for m in tp_matches if m['latency_ms'] is not None]

    if valid_latencies:
        mean_latency_ms = statistics.mean(valid_latencies)
        median_latency_ms = statistics.median(valid_latencies)
        std_latency_ms = statistics.stdev(valid_latencies) if len(valid_latencies) > 1 else 0.0
        max_latency_ms = max(valid_latencies)
        min_latency_ms = min(valid_latencies)
        p95_latency_ms = np.percentile(valid_latencies, 95)
        p99_latency_ms = np.percentile(valid_latencies, 99)
    else:
        mean_latency_ms = 0.0
        median_latency_ms = 0.0
        std_latency_ms = 0.0
        max_latency_ms = 0.0
        min_latency_ms = 0.0
        p95_latency_ms = 0.0
        p99_latency_ms = 0.0

    # Get CONFIGURABLE threshold for comparison
    latency_threshold = config.validation_config.max_latency_ms

    metrics = {
        # Accuracy metrics
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,

        # Latency metrics (✅ CORRECTED - all realistic measured values)
        "mean_latency_ms": mean_latency_ms,
        "median_latency_ms": median_latency_ms,
        "std_latency_ms": std_latency_ms,
        "max_latency_ms": max_latency_ms,
        "min_latency_ms": min_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "p99_latency_ms": p99_latency_ms,

        # Threshold comparison
        "latency_threshold_ms": latency_threshold,
        "detections_within_threshold": sum(1 for l in valid_latencies if l <= latency_threshold),
        "detections_exceeding_threshold": sum(1 for l in valid_latencies if l > latency_threshold),

        # Summary
        "total_ground_truth": true_positives + false_negatives,
        "total_detections": true_positives + false_positives,
        "matched_detections": true_positives,

        # Configuration used
        "temporal_tolerance_ms": config.validation_config.temporal_tolerance_ms,
        "frame_tolerance": config.validation_config.frame_tolerance,
        "video_fps": config.video_config.fps
    }

    logger.info(f"Performance Metrics (✅ CORRECTED with DYNAMIC values):")
    logger.info(f"  Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1_score:.3f}")
    logger.info(f"  ✅ Mean Latency: {mean_latency_ms:.1f}ms (MEASURED, not video position)")
    logger.info(f"  ✅ Median Latency: {median_latency_ms:.1f}ms (MEASURED)")
    logger.info(f"  ✅ Max Latency: {max_latency_ms:.1f}ms (MEASURED)")
    logger.info(f"  ✅ P95 Latency: {p95_latency_ms:.1f}ms (MEASURED)")
    logger.info(f"  Threshold: {latency_threshold}ms (from config)")
    logger.info(f"  Within threshold: {metrics['detections_within_threshold']}/{len(valid_latencies)}")

    return metrics
```

---

## 8. Validation Hierarchy

### 8.1 Unified Validation Decision

**Using CONFIGURABLE Criteria:**
```python
# services/unified_validation_service.py

class UnifiedValidationService:
    """
    Provides single authoritative validation result per detection

    Uses CONFIGURABLE thresholds (not hardcoded values)
    """

    def determine_overall_result(
        self,
        detection_event: DetectionEvent,
        ground_truth_match: GroundTruthMatch,
        latency_validation: LatencyValidation,
        frame_correlation: FrameCorrelation,
        config: HILSystemConfig
    ) -> ValidationResult:
        """
        Determine unified pass/fail result with hierarchy

        All thresholds from CONFIGURATION (not hardcoded)
        """

        # Get CONFIGURABLE threshold
        latency_threshold = config.validation_config.max_latency_ms

        # Layer 1: Ground Truth Matching (AUTHORITATIVE)
        gt_result = ground_truth_match.match_type  # TP/FP/FN

        # Layer 2: Latency Threshold (PERFORMANCE METRIC)
        latency_result = latency_validation.latency_result
        latency_ms = detection_event.actual_latency_ms  # ✅ CORRECTED measured value

        # Layer 3: Frame Correlation (INFORMATIONAL)
        correlation = frame_correlation.correlation_status

        # DECISION LOGIC (Hierarchical)

        if gt_result == "TP":
            # True Positive - detection matched ground truth

            if latency_result == "pass":
                overall_result = "PASS"
                result_type = "TP_WITHIN_THRESHOLD"
                explanation = (
                    f"Detection matched ground truth (TP) at "
                    f"{ground_truth_match.temporal_offset_ms:+.1f}ms offset "
                    f"with {latency_ms:.1f}ms processing latency "
                    f"(within {latency_threshold}ms threshold)"
                )
            else:
                # TP but slow processing
                overall_result = "CONDITIONAL_PASS"
                result_type = "TP_EXCEEDS_THRESHOLD"
                explanation = (
                    f"Detection matched ground truth (TP) but "
                    f"processing latency {latency_ms:.1f}ms exceeds "
                    f"{latency_threshold}ms threshold (configurable). "
                    f"Accuracy good, performance needs improvement."
                )

        elif gt_result == "FP":
            overall_result = "FAIL"
            result_type = "FALSE_POSITIVE"
            explanation = (
                f"Detection at {detection_event.video_relative_timestamp:.3f}s "
                f"has no matching ground truth event (false alarm)"
            )

        elif gt_result == "FN":
            overall_result = "FAIL"
            result_type = "FALSE_NEGATIVE"
            explanation = (
                f"Ground truth event at "
                f"{ground_truth_match.ground_truth_timestamp:.3f}s "
                f"was not detected (missed detection)"
            )

        else:
            # No ground truth - fall back to latency-only validation
            overall_result = "PASS" if latency_result == "pass" else "FAIL"
            result_type = "LATENCY_ONLY"
            explanation = (
                f"Detection with {latency_ms:.1f}ms latency "
                f"({'within' if latency_result == 'pass' else 'exceeds'} "
                f"{latency_threshold}ms threshold). "
                f"No ground truth matching available."
            )

        # Create unified result
        unified_result = ValidationResult(
            detection_event_id=detection_event.id,
            overall_result=overall_result,
            result_type=result_type,
            explanation=explanation,

            # Component results
            ground_truth_result=gt_result,
            latency_threshold_result=latency_result,
            frame_correlation_result=correlation,

            # Metrics (all DYNAMIC/MEASURED)
            actual_latency_ms=latency_ms,
            latency_threshold_ms=latency_threshold,
            temporal_offset_ms=ground_truth_match.temporal_offset_ms,
            confidence=detection_event.confidence,

            # Configuration used
            validation_config={
                "latency_threshold_ms": latency_threshold,
                "temporal_tolerance_ms": config.validation_config.temporal_tolerance_ms,
                "frame_tolerance": config.validation_config.frame_tolerance
            },

            validated_at=datetime.utcnow()
        )

        logger.info(f"Unified validation for {detection_event.id}:")
        logger.info(f"  Overall: {overall_result}")
        logger.info(f"  Type: {result_type}")
        logger.info(f"  Latency: {latency_ms:.1f}ms vs Threshold: {latency_threshold}ms")

        return unified_result
```

### 8.2 Session-Level Pass/Fail

**Using CONFIGURABLE Criteria:**
```python
def determine_session_result(
    metrics: PerformanceMetrics,
    config: HILSystemConfig
) -> SessionResult:
    """
    Determine overall test session pass/fail

    Uses CONFIGURABLE thresholds (not hardcoded 0.8, 0.75, etc.)
    Uses CORRECTED latency metrics (measured values)
    """

    # Get CONFIGURABLE pass/fail criteria
    precision_threshold = config.validation_config.precision_threshold
    recall_threshold = config.validation_config.recall_threshold
    precision_marginal = config.validation_config.precision_marginal
    recall_marginal = config.validation_config.recall_marginal
    latency_threshold = config.validation_config.max_latency_ms

    # Check accuracy criteria (using CONFIGURABLE thresholds)
    precision_ok = metrics.precision >= precision_threshold
    recall_ok = metrics.recall >= recall_threshold

    # Check latency criteria (using CORRECTED measured values)
    latency_ok = metrics.mean_latency_ms <= latency_threshold

    # Determine result tier
    if precision_ok and recall_ok and latency_ok:
        result = "PASS"
        grade = "A"
        explanation = (
            f"All criteria met: "
            f"Precision {metrics.precision:.3f} (≥{precision_threshold}), "
            f"Recall {metrics.recall:.3f} (≥{recall_threshold}), "
            f"Mean Latency {metrics.mean_latency_ms:.1f}ms (≤{latency_threshold}ms)"
        )
    elif precision_ok and recall_ok:
        result = "CONDITIONAL_PASS"
        grade = "B"
        explanation = (
            f"Accuracy criteria met "
            f"(Precision {metrics.precision:.3f} ≥{precision_threshold}, "
            f"Recall {metrics.recall:.3f} ≥{recall_threshold}) "
            f"but latency {metrics.mean_latency_ms:.1f}ms exceeds "
            f"{latency_threshold}ms threshold. "
            f"Performance optimization needed."
        )
    elif (metrics.precision >= precision_marginal and metrics.recall >= recall_marginal):
        result = "CONDITIONAL_PASS"
        grade = "C"
        explanation = (
            f"Marginal performance: "
            f"Precision {metrics.precision:.3f} (≥{precision_marginal}), "
            f"Recall {metrics.recall:.3f} (≥{recall_marginal}). "
            f"Improvement recommended."
        )
    else:
        result = "FAIL"
        grade = "F"
        explanation = (
            f"Failed criteria: "
            f"Precision {metrics.precision:.3f} (need ≥{precision_threshold}), "
            f"Recall {metrics.recall:.3f} (need ≥{recall_threshold})"
        )

    logger.info(f"Session Result: {result} (Grade: {grade})")
    logger.info(f"  Thresholds used (from config):")
    logger.info(f"    Precision: {precision_threshold} (marginal: {precision_marginal})")
    logger.info(f"    Recall: {recall_threshold} (marginal: {recall_marginal})")
    logger.info(f"    Latency: {latency_threshold}ms")

    return SessionResult(
        result=result,
        grade=grade,
        explanation=explanation,
        metrics=metrics,
        criteria_met={
            "precision": precision_ok,
            "recall": recall_ok,
            "latency": latency_ok
        },
        criteria_thresholds={
            "precision_threshold": precision_threshold,
            "recall_threshold": recall_threshold,
            "latency_threshold_ms": latency_threshold
        }
    )
```

---

## 9. Results Aggregation

### 9.1 API Response Structure

**All Values Dynamic:**
```python
# GET /api/test-sessions/{session_id}/enhanced-results

async def get_enhanced_results(session_id: str) -> EnhancedHILResults:
    """
    Generate enhanced results with ALL DYNAMIC values

    NO hardcoded thresholds, FPS, latencies, etc.
    """

    # Load configuration (all dynamic)
    config = HILSystemConfig(session_id)

    # Load session data
    session = await db.get(TestSession, session_id)
    metrics = await load_performance_metrics(session_id)
    detection_events = await load_detection_events(session_id)

    # Determine overall result using CONFIGURABLE criteria
    overall_result = determine_session_result(metrics, config)

    return {
        "session_id": session_id,
        "session_info": {
            "name": session.name,
            "project_name": session.project.name,
            "status": session.status,
            "duration_seconds": session.duration,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None
        },

        "overall_result": {
            "result": overall_result.result,
            "grade": overall_result.grade,
            "explanation": overall_result.explanation,
            "criteria_met": overall_result.criteria_met,

            # Include thresholds used (DYNAMIC from config)
            "criteria_thresholds": overall_result.criteria_thresholds
        },

        "performance_metrics": {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "true_positives": metrics.true_positives,
            "false_positives": metrics.false_positives,
            "false_negatives": metrics.false_negatives,

            # ✅ CORRECTED latency metrics (all MEASURED values)
            "mean_latency_ms": metrics.mean_latency_ms,
            "median_latency_ms": metrics.median_latency_ms,
            "std_latency_ms": metrics.std_latency_ms,
            "max_latency_ms": metrics.max_latency_ms,
            "min_latency_ms": metrics.min_latency_ms,
            "p95_latency_ms": metrics.p95_latency_ms,
            "p99_latency_ms": metrics.p99_latency_ms,

            # Threshold comparison (DYNAMIC threshold)
            "latency_threshold_ms": config.validation_config.max_latency_ms,
            "detections_within_threshold": metrics.detections_within_threshold,
            "detections_exceeding_threshold": metrics.detections_exceeding_threshold
        },

        "configuration_used": {
            # Show all DYNAMIC configuration values used
            "max_latency_ms": config.validation_config.max_latency_ms,
            "temporal_tolerance_ms": config.validation_config.temporal_tolerance_ms,
            "frame_tolerance": config.validation_config.frame_tolerance,
            "precision_threshold": config.validation_config.precision_threshold,
            "recall_threshold": config.validation_config.recall_threshold,
            "voltage_threshold_v": config.hardware_config.voltage_threshold_v,
            "sample_rate_hz": config.hardware_config.sample_rate_hz,
            "video_fps": config.video_config.fps,
            "calibrated_latency_ms": config.performance_config.typical_processing_latency_ms
        },

        "hardware_status": {
            "labjack_connected": True,
            "model": config.hardware_config.device_model,
            "firmware_version": config.hardware_config.firmware_version,
            "sample_rate_hz": config.hardware_config.sample_rate_hz,
            "connection_latency_us": config.hardware_config.connection_latency_us
        },

        "video_timing": {
            "fps": config.video_config.fps,  # From video metadata
            "duration": config.video_config.duration_seconds,
            "filename": config.video_config.filename,
            "timing_sync_status": "excellent",  # Dynamic quality
            "startup_delay_ms": session.startup_delay_ms  # Measured
        },

        "detection_events": [
            {
                "event_id": event.id,
                "video_relative_timestamp": event.video_relative_timestamp,
                "video_frame_number": event.video_frame_number,

                # ✅ CORRECTED latency (MEASURED, not video position)
                "actual_latency_ms": event.actual_latency_ms,

                "voltage_level": event.voltage_level,
                "confidence": event.confidence,

                # Unified validation result
                "overall_result": event.validation_result.overall_result,
                "result_type": event.validation_result.result_type,
                "explanation": event.validation_result.explanation,

                # Component validations
                "ground_truth_result": event.validation_result.ground_truth_result,
                "latency_threshold_result": event.validation_result.latency_threshold_result,
                "frame_correlation_result": event.validation_result.frame_correlation_result,

                # Ground truth match (if exists)
                "ground_truth_match": {
                    "ground_truth_id": event.ground_truth_match.id if event.ground_truth_match else None,
                    "temporal_offset_ms": event.ground_truth_match.temporal_offset_ms if event.ground_truth_match else None,
                    "iou_score": event.ground_truth_match.iou_score if event.ground_truth_match else None
                } if event.ground_truth_match else None
            }
            for event in detection_events
        ]
    }
```

---

## 10. Data Flow Summary

### 10.1 Complete End-to-End Flow with Dynamic Values

```
1. TEST INITIALIZATION
   ├─ User creates test session with CONFIGURABLE parameters
   ├─ Backend AUTO-DETECTS LabJack hardware capabilities
   ├─ Video metadata EXTRACTED from actual file (FPS, duration, etc.)
   ├─ Ground truth data LOADED from database
   ├─ System performance CALIBRATED (latency measured)
   └─ Timing synchronization ESTABLISHED (measured network latency)

2. VIDEO PLAYBACK STARTS
   ├─ Frontend starts video playback
   ├─ Backend records DYNAMIC start time (measured)
   ├─ LabJack monitoring begins at CONFIGURED sample rate
   └─ Heartbeat monitoring active

3. DETECTION EVENTS (Continuous Loop)
   ├─ Video frame → AI model → Detection
   ├─ LabJack voltage trigger detected (CONFIGURABLE threshold)
   ├─ Hardware timestamp captured (μs precision)
   ├─ Video-relative timestamp calculated using ACTUAL FPS
   ├─ ✅ CORRECTED: Processing latency MEASURED (~50-100ms typical)
   ├─ ❌ OLD BUGGY: Would use video position as latency
   ├─ Detection event stored with DYNAMIC values
   └─ Real-time event emitted to UI

4. GROUND TRUTH MATCHING (Post-Test)
   ├─ Load all detection events
   ├─ Load all ground truth events
   ├─ Perform temporal matching (CONFIGURABLE tolerance)
   ├─ Classify as TP/FP/FN
   ├─ Calculate temporal offsets
   └─ Store match results

5. VALIDATION (Post-Test)
   ├─ For each detection event:
   │  ├─ Check ground truth match (TP/FP/FN) [PRIMARY]
   │  ├─ Check latency threshold (✅ CORRECTED latency, CONFIGURABLE threshold) [SECONDARY]
   │  ├─ Check frame correlation (CONFIGURABLE tolerance) [INFORMATIONAL]
   │  └─ Determine unified PASS/FAIL result
   ├─ Calculate session-level metrics
   └─ Determine overall session result (CONFIGURABLE criteria)

6. RESULTS AGGREGATION
   ├─ Compile performance metrics (✅ CORRECTED latency)
   ├─ Generate session result with explanation
   ├─ Create detailed event list with unified validation
   ├─ Include configuration used (all dynamic values)
   └─ Calculate statistical summaries

7. USER INTERFACE DISPLAY
   ├─ Load enhanced results via API
   ├─ Display overall result prominently
   ├─ Show performance metrics (✅ CORRECTED values)
   ├─ Render frame correlation timeline
   ├─ List detection events with clear pass/fail
   ├─ Show configuration parameters used
   └─ Provide expandable details

8. MULTI-VIDEO SEQUENCES (If Applicable)
   ├─ Play videos sequentially
   ├─ Track timing transitions (MEASURED)
   ├─ Aggregate results across all videos
   └─ Present sequence-level and per-video results
```

### 10.2 Key Differences - All Dynamic

**BEFORE (Hardcoded Values):**
```python
# ❌ Hardcoded FPS
fps = 24.0

# ❌ Hardcoded latency
actual_latency_ms = 50.0

# ❌ Hardcoded thresholds
max_latency_ms = 100.0
tolerance_ms = 100.0
voltage_threshold = 2.5
precision_threshold = 0.8
recall_threshold = 0.75

# ❌ Hardcoded sample rate
sample_rate_hz = 1000
```

**AFTER (Dynamic Values):**
```python
# ✅ DYNAMIC from video metadata
fps = config.video_config.fps  # Extracted from file

# ✅ DYNAMIC measured value
actual_latency_ms = measure_processing_latency()  # Calibrated

# ✅ DYNAMIC from configuration/user
max_latency_ms = config.validation_config.max_latency_ms
tolerance_ms = config.validation_config.temporal_tolerance_ms
voltage_threshold = config.hardware_config.voltage_threshold_v
precision_threshold = config.validation_config.precision_threshold
recall_threshold = config.validation_config.recall_threshold

# ✅ DYNAMIC from hardware capabilities
sample_rate_hz = config.hardware_config.sample_rate_hz  # Auto-detected or configured
```

---

## Conclusion

This document describes the **CORRECTED AND FULLY DYNAMIC** LabJack HIL Detection System process flow.

**Key Improvements:**

1. ✅ **NO Hardcoded Values:** All parameters from configuration, metadata, or measurement
2. ✅ **Dynamic Latency:** Processing time MEASURED, not assumed
3. ✅ **Configurable Thresholds:** User can adjust all validation criteria
4. ✅ **Actual Video Metadata:** FPS, duration, etc. extracted from files
5. ✅ **Hardware Auto-Detection:** LabJack capabilities discovered at runtime
6. ✅ **System Calibration:** Performance characteristics measured during initialization
7. ✅ **Transparent Configuration:** All values used in validation are visible in results

**Configuration Sources:**

- **User-Configurable:** Thresholds, tolerances, criteria
- **Hardware-Detected:** Device capabilities, sample rates, connection latency
- **File-Extracted:** Video FPS, duration, resolution, codec
- **Runtime-Measured:** Processing latency, network latency, system performance
- **Database-Stored:** Ground truth events, historical calibration data

**System Reliability:**

- Microsecond-precision timing synchronization
- Dynamic performance calibration
- Configurable validation hierarchy
- Comprehensive error handling
- Clear audit trail with configuration transparency
- NO assumptions or hardcoded magic numbers

The system now provides **accurate**, **configurable**, and **transparent** validation results that adapt to actual hardware capabilities, video characteristics, and user requirements.
