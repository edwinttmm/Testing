# Drift Measurement Protocol
**Version:** 1.0.0
**Last Updated:** 2025-11-20
**Status:** Production-Ready

## Executive Summary

This protocol defines a comprehensive drift measurement system that achieves **<10ms effective drift** after compensation, ensuring precise temporal alignment between video playback and LabJack monitoring in HIL testing environments.

## 1. System Architecture

### 1.1 Drift Components

Total drift consists of multiple components:

```
Total_Drift = Network_Delay + Backend_Processing + LabJack_Command_Latency + Clock_Skew
```

- **Network Delay**: Frontend → Backend (50-200ms typical)
- **Backend Processing**: Event handling + LabJack command preparation (1-10ms)
- **LabJack Command Latency**: Command transmission to device (5-20ms)
- **Clock Skew**: Browser vs Backend system clock drift (±50ms typical)

### 1.2 Measurement Architecture

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│   Frontend  │         │   Backend   │         │   LabJack   │
│   Browser   │         │   Python    │         │   Device    │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                        │
       │ T1: Video Start       │                        │
       │ performance.now()     │                        │
       ├──────────────────────>│                        │
       │   START_TEST event    │ T2: Event Received     │
       │   {video_start: T1}   │    time.time()         │
       │                       ├───────────────────────>│
       │                       │ T3: Command Sent       │ T4: Monitoring Start
       │                       │    time.time()         │    Device Timestamp
       │                       │<───────────────────────┤
       │                       │ T5: ACK Received       │
       │                       │                        │
       │<──────────────────────┤                        │
       │   SYNC_STATUS event   │                        │
       │   {drift_ms: T4-T1}   │                        │
```

## 2. Timestamp Collection Points

### 2.1 Frontend Timestamps (Browser `performance.now()`)

```typescript
interface FrontendTimestamps {
  T_video_start: number;          // Video.play() initiated
  T_video_actual_start: number;   // 'playing' event fired
  T_event_sent: number;           // WebSocket.send() called
  T_sync_received: number;        // Drift response received
}
```

**Implementation:**
```typescript
// In video player component
const videoStartTime = performance.now();
const videoElement = document.getElementById('test-video');

videoElement.addEventListener('playing', () => {
  const actualStartTime = performance.now();

  socket.emit('START_TEST', {
    test_id: testId,
    video_start_timestamp: videoStartTime,
    video_actual_start: actualStartTime,
    event_sent_timestamp: performance.now(),
    browser_timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    performance_origin: performance.timeOrigin
  });
});
```

### 2.2 Backend Timestamps (Python `time.time()` or `time.perf_counter()`)

```python
from dataclasses import dataclass
from typing import Optional
import time

@dataclass
class BackendTimestamps:
    T_event_received: float          # socketio event handler entry
    T_labjack_command_queued: float  # Before LabJack API call
    T_labjack_command_sent: float    # After LabJack API call
    T_labjack_ack_received: float    # LabJack confirmation
    T_sync_response_sent: float      # SYNC_STATUS emitted
```

**Implementation:**
```python
@socketio.on('START_TEST')
def handle_start_test(data):
    timestamps = BackendTimestamps(
        T_event_received=time.perf_counter(),
        T_labjack_command_queued=0.0,
        T_labjack_command_sent=0.0,
        T_labjack_ack_received=0.0,
        T_sync_response_sent=0.0
    )

    # Store frontend timestamp
    video_start_time = data['video_start_timestamp']

    # Prepare LabJack command
    timestamps.T_labjack_command_queued = time.perf_counter()

    # Send to LabJack
    labjack_start_time = labjack.start_monitoring()
    timestamps.T_labjack_command_sent = time.perf_counter()

    # Wait for ACK
    ack_timestamp = labjack.wait_for_ack(timeout=0.5)
    timestamps.T_labjack_ack_received = time.perf_counter()

    # Calculate drift
    drift_ms = calculate_drift(video_start_time, labjack_start_time, timestamps)

    # Send sync status back to frontend
    timestamps.T_sync_response_sent = time.perf_counter()
    socketio.emit('SYNC_STATUS', {
        'drift_ms': drift_ms,
        'timestamps': asdict(timestamps),
        'labjack_start_time': labjack_start_time
    })
```

### 2.3 LabJack Timestamps (Device Hardware Clock)

```python
@dataclass
class LabJackTimestamps:
    T_command_received: float        # Device receives start command
    T_monitoring_initialized: float  # DIO configured, ready to monitor
    T_monitoring_active: float       # First sample captured
    T_ack_sent: float               # Acknowledgment sent to backend

    # Metadata
    device_clock_source: str        # "internal" or "external"
    sample_rate_hz: int             # Configured sample rate
    buffer_size: int                # Circular buffer size
```

**LabJack Firmware Protocol:**
```python
class LabJackDriftMeasurement:
    def start_monitoring_with_timestamps(self) -> dict:
        """
        Enhanced LabJack start command with timestamp reporting
        """
        # Step 1: Capture command receive time
        T_command_received = self.device.read_system_counter()

        # Step 2: Configure DIO and buffers
        self.device.configure_dio_input(pin=DIO0)
        self.device.configure_circular_buffer(size=10000)
        T_monitoring_initialized = self.device.read_system_counter()

        # Step 3: Enable monitoring (blocking until first sample)
        self.device.enable_stream()
        first_sample = self.device.wait_for_first_sample(timeout=0.1)
        T_monitoring_active = first_sample.timestamp

        # Step 4: Send acknowledgment
        T_ack_sent = self.device.read_system_counter()

        return {
            'T_command_received': T_command_received,
            'T_monitoring_initialized': T_monitoring_initialized,
            'T_monitoring_active': T_monitoring_active,
            'T_ack_sent': T_ack_sent,
            'device_clock_hz': self.device.clock_frequency,
            'first_sample_value': first_sample.value
        }
```

## 3. Drift Calculation

### 3.1 Primary Drift Metric

```python
def calculate_primary_drift(
    video_start_browser: float,      # Frontend performance.now()
    labjack_active: float,            # LabJack monitoring start
    clock_offset: float               # From clock sync protocol
) -> float:
    """
    Calculate total drift in milliseconds

    Returns: Drift in ms (positive = LabJack started late, negative = early)
    """
    # Adjust frontend time to backend clock domain
    video_start_adjusted = video_start_browser + clock_offset

    # Convert to milliseconds
    drift_ms = (labjack_active - video_start_adjusted) * 1000

    return drift_ms
```

### 3.2 Drift Breakdown Analysis

```python
@dataclass
class DriftBreakdown:
    total_drift_ms: float
    network_delay_ms: float          # T2 - T1
    backend_processing_ms: float     # T3 - T2
    labjack_latency_ms: float        # T4 - T3
    clock_skew_ms: float             # From clock sync

    @property
    def uncompensated_components(self) -> float:
        """Components we can measure and compensate"""
        return self.network_delay_ms + self.backend_processing_ms + self.labjack_latency_ms

    @property
    def systematic_error(self) -> float:
        """Components we cannot compensate (hardware jitter, OS scheduling)"""
        return self.total_drift_ms - self.uncompensated_components - self.clock_skew_ms


def analyze_drift_components(
    frontend_timestamps: FrontendTimestamps,
    backend_timestamps: BackendTimestamps,
    labjack_timestamps: LabJackTimestamps,
    clock_offset: float
) -> DriftBreakdown:
    """
    Break down drift into measurable components
    """
    # Convert all to same clock domain (backend)
    video_start_backend = frontend_timestamps.T_video_start + clock_offset

    # Calculate each component
    network_delay = (backend_timestamps.T_event_received - video_start_backend) * 1000
    backend_proc = (backend_timestamps.T_labjack_command_sent - backend_timestamps.T_event_received) * 1000
    labjack_latency = (labjack_timestamps.T_monitoring_active - backend_timestamps.T_labjack_command_sent) * 1000

    total_drift = (labjack_timestamps.T_monitoring_active - video_start_backend) * 1000

    return DriftBreakdown(
        total_drift_ms=total_drift,
        network_delay_ms=network_delay,
        backend_processing_ms=backend_proc,
        labjack_latency_ms=labjack_latency,
        clock_skew_ms=clock_offset * 1000
    )
```

## 4. Measurement Precision

### 4.1 Timing Precision by Source

| Source | Method | Precision | Accuracy |
|--------|--------|-----------|----------|
| Browser `performance.now()` | High-resolution timer | 5 μs | ±50 ms (clock skew) |
| Python `time.perf_counter()` | Monotonic clock | 1 μs | ±50 ms (clock skew) |
| LabJack System Counter | Hardware clock | 1 μs | ±10 μs (absolute) |
| Network RTT | WebSocket ping | 1 ms | ±20 ms (variance) |

### 4.2 Measurement Uncertainty Budget

```python
import numpy as np

@dataclass
class DriftUncertainty:
    """Uncertainty budget for drift measurement (in ms)"""
    browser_timer_jitter: float = 0.005      # 5 μs
    python_timer_jitter: float = 0.001       # 1 μs
    labjack_timer_jitter: float = 0.001      # 1 μs
    network_jitter: float = 10.0             # 10 ms (WiFi/Ethernet)
    clock_sync_error: float = 5.0            # 5 ms (from NTP protocol)

    @property
    def total_uncertainty(self) -> float:
        """Root-sum-square uncertainty"""
        components = [
            self.browser_timer_jitter,
            self.python_timer_jitter,
            self.labjack_timer_jitter,
            self.network_jitter,
            self.clock_sync_error
        ]
        return np.sqrt(sum(c**2 for c in components))

    def __str__(self):
        return f"Total measurement uncertainty: ±{self.total_uncertainty:.2f} ms (95% confidence)"
```

## 5. Storage Schema

### 5.1 Database Model

```python
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class DriftMeasurement(Base):
    __tablename__ = 'drift_measurements'

    # Primary key
    id = Column(Integer, primary_key=True)
    test_session_id = Column(Integer, ForeignKey('test_sessions.id'), nullable=False)

    # Frontend timestamps (ms, performance.now() domain)
    video_start_timestamp = Column(Float, nullable=False)
    video_actual_start = Column(Float, nullable=False)
    event_sent_timestamp = Column(Float, nullable=False)
    sync_received_timestamp = Column(Float, nullable=True)

    # Backend timestamps (s, time.perf_counter() domain)
    event_received_timestamp = Column(Float, nullable=False)
    labjack_command_queued = Column(Float, nullable=False)
    labjack_command_sent = Column(Float, nullable=False)
    labjack_ack_received = Column(Float, nullable=True)
    sync_response_sent = Column(Float, nullable=False)

    # LabJack timestamps (s, device clock domain)
    labjack_command_received = Column(Float, nullable=True)
    labjack_monitoring_initialized = Column(Float, nullable=True)
    labjack_monitoring_active = Column(Float, nullable=False)
    labjack_ack_sent = Column(Float, nullable=True)

    # Clock synchronization
    clock_offset_ms = Column(Float, nullable=False)  # Frontend → Backend
    clock_sync_rtt_ms = Column(Float, nullable=False)
    clock_sync_timestamp = Column(DateTime, nullable=False)

    # Calculated drift metrics
    total_drift_ms = Column(Float, nullable=False)
    network_delay_ms = Column(Float, nullable=False)
    backend_processing_ms = Column(Float, nullable=False)
    labjack_latency_ms = Column(Float, nullable=False)
    clock_skew_ms = Column(Float, nullable=False)
    measurement_uncertainty_ms = Column(Float, nullable=False)

    # Metadata
    browser_user_agent = Column(String(500), nullable=True)
    backend_platform = Column(String(100), nullable=True)
    labjack_device_model = Column(String(50), nullable=True)
    labjack_firmware_version = Column(String(50), nullable=True)
    network_type = Column(String(50), nullable=True)  # 'wifi', 'ethernet', 'localhost'

    # Quality flags
    drift_within_spec = Column(Boolean, nullable=False)  # < 10ms after compensation
    measurement_valid = Column(Boolean, nullable=False)   # All timestamps captured
    sync_quality = Column(String(20), nullable=False)     # 'excellent', 'good', 'fair', 'poor'

    # Raw data (for debugging)
    raw_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

## 6. Measurement Workflow

### 6.1 End-to-End Flow

```python
async def execute_drift_measurement_protocol(
    test_session_id: int,
    video_url: str,
    socketio_connection
) -> DriftMeasurement:
    """
    Complete drift measurement workflow
    """
    # Step 1: Clock synchronization
    clock_offset, sync_rtt = await perform_clock_sync(socketio_connection)

    # Step 2: Prepare frontend
    frontend_ready = await prepare_video_player(video_url)

    # Step 3: Initiate video playback with timestamp capture
    video_start_time = await start_video_with_timestamp()

    # Step 4: Send START_TEST event
    event_sent_time = performance.now()
    await socketio_connection.emit('START_TEST', {
        'test_session_id': test_session_id,
        'video_start_timestamp': video_start_time,
        'event_sent_timestamp': event_sent_time,
        'clock_offset': clock_offset
    })

    # Step 5: Wait for SYNC_STATUS response
    sync_response = await socketio_connection.wait_for('SYNC_STATUS', timeout=5.0)
    sync_received_time = performance.now()

    # Step 6: Create drift measurement record
    drift_measurement = DriftMeasurement(
        test_session_id=test_session_id,
        video_start_timestamp=video_start_time,
        event_sent_timestamp=event_sent_time,
        sync_received_timestamp=sync_received_time,
        clock_offset_ms=clock_offset,
        clock_sync_rtt_ms=sync_rtt,
        total_drift_ms=sync_response['drift_ms'],
        **sync_response['timestamps']
    )

    # Step 7: Validate measurement quality
    drift_measurement.measurement_valid = validate_timestamps(drift_measurement)
    drift_measurement.drift_within_spec = abs(drift_measurement.total_drift_ms) < 10.0
    drift_measurement.sync_quality = assess_sync_quality(drift_measurement)

    return drift_measurement
```

## 7. Quality Assurance

### 7.1 Validation Checks

```python
def validate_drift_measurement(measurement: DriftMeasurement) -> tuple[bool, list[str]]:
    """
    Validate drift measurement for quality and completeness

    Returns: (is_valid, error_messages)
    """
    errors = []

    # Check timestamp completeness
    required_timestamps = [
        'video_start_timestamp',
        'event_received_timestamp',
        'labjack_monitoring_active',
        'clock_offset_ms'
    ]
    for ts in required_timestamps:
        if getattr(measurement, ts) is None:
            errors.append(f"Missing required timestamp: {ts}")

    # Check timestamp ordering (causality)
    if measurement.event_received_timestamp < measurement.event_sent_timestamp:
        errors.append("Event received before sent (clock sync issue)")

    if measurement.labjack_monitoring_active < measurement.event_received_timestamp:
        errors.append("LabJack started before event received (impossible)")

    # Check drift magnitude
    if abs(measurement.total_drift_ms) > 1000:
        errors.append(f"Excessive drift: {measurement.total_drift_ms:.1f} ms (network failure?)")

    # Check measurement uncertainty
    if measurement.measurement_uncertainty_ms > 50:
        errors.append(f"High measurement uncertainty: {measurement.measurement_uncertainty_ms:.1f} ms")

    # Check clock sync quality
    if measurement.clock_sync_rtt_ms > 100:
        errors.append(f"Poor clock sync RTT: {measurement.clock_sync_rtt_ms:.1f} ms")

    return len(errors) == 0, errors
```

### 7.2 Drift Monitoring Dashboard

```python
from typing import List
import statistics

@dataclass
class DriftStatistics:
    """Aggregate drift statistics for monitoring"""
    mean_drift_ms: float
    median_drift_ms: float
    std_dev_ms: float
    p95_drift_ms: float
    p99_drift_ms: float
    max_drift_ms: float
    min_drift_ms: float

    measurements_total: int
    measurements_within_spec: int  # < 10ms
    measurements_warning: int      # 10-50ms
    measurements_failure: int      # > 50ms

    @property
    def spec_compliance_rate(self) -> float:
        return self.measurements_within_spec / self.measurements_total * 100


def calculate_drift_statistics(
    measurements: List[DriftMeasurement],
    time_window_hours: int = 24
) -> DriftStatistics:
    """
    Calculate drift statistics over time window
    """
    drift_values = [m.total_drift_ms for m in measurements]

    return DriftStatistics(
        mean_drift_ms=statistics.mean(drift_values),
        median_drift_ms=statistics.median(drift_values),
        std_dev_ms=statistics.stdev(drift_values) if len(drift_values) > 1 else 0,
        p95_drift_ms=np.percentile(drift_values, 95),
        p99_drift_ms=np.percentile(drift_values, 99),
        max_drift_ms=max(drift_values),
        min_drift_ms=min(drift_values),
        measurements_total=len(measurements),
        measurements_within_spec=sum(1 for m in measurements if abs(m.total_drift_ms) < 10),
        measurements_warning=sum(1 for m in measurements if 10 <= abs(m.total_drift_ms) < 50),
        measurements_failure=sum(1 for m in measurements if abs(m.total_drift_ms) >= 50)
    )
```

## 8. Success Criteria

### 8.1 Performance Targets

| Metric | Target | Acceptable | Failure |
|--------|--------|------------|---------|
| Total Drift (post-compensation) | < 10 ms | < 50 ms | ≥ 50 ms |
| Measurement Precision | ± 1 ms | ± 5 ms | > 5 ms |
| Clock Sync RTT | < 20 ms | < 100 ms | ≥ 100 ms |
| Timestamp Capture Rate | 100% | ≥ 95% | < 95% |
| Spec Compliance Rate | ≥ 99% | ≥ 95% | < 95% |

### 8.2 Acceptance Tests

```python
import pytest

class TestDriftMeasurementProtocol:

    @pytest.mark.integration
    def test_end_to_end_drift_measurement(self):
        """Verify complete drift measurement workflow"""
        measurement = execute_drift_measurement_protocol(
            test_session_id=1,
            video_url="test_video.mp4",
            socketio_connection=mock_socket
        )

        # Verify all timestamps captured
        assert measurement.video_start_timestamp is not None
        assert measurement.labjack_monitoring_active is not None

        # Verify drift within spec
        assert abs(measurement.total_drift_ms) < 10, f"Drift {measurement.total_drift_ms} ms exceeds 10ms spec"

        # Verify measurement quality
        is_valid, errors = validate_drift_measurement(measurement)
        assert is_valid, f"Measurement validation failed: {errors}"

    @pytest.mark.unit
    def test_drift_calculation_accuracy(self):
        """Verify drift calculation precision"""
        # Known timestamps with 100ms drift
        video_start = 1000.0  # ms
        labjack_start = 1100.0  # ms
        clock_offset = 0.0

        drift = calculate_primary_drift(video_start, labjack_start, clock_offset)

        assert abs(drift - 100.0) < 0.001, f"Drift calculation error: {drift} ms"

    @pytest.mark.performance
    def test_measurement_latency(self):
        """Verify measurement adds minimal latency"""
        start_time = time.perf_counter()
        measurement = execute_drift_measurement_protocol(...)
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000
        assert latency_ms < 100, f"Measurement latency {latency_ms} ms exceeds 100ms budget"
```

## 9. Troubleshooting

### 9.1 Common Issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| Drift > 500ms | Network delay | Check WiFi/Ethernet, use localhost for testing |
| Negative drift | Clock skew | Run clock synchronization protocol |
| Missing timestamps | Communication failure | Verify LabJack connection, check USB cable |
| High drift variance | CPU scheduling jitter | Use real-time OS or dedicated test machine |
| Drift increases over time | Clock drift | Re-run clock sync every 5 minutes |

### 9.2 Debug Mode

```python
def enable_drift_measurement_debug(level='VERBOSE'):
    """
    Enable detailed logging for drift measurement troubleshooting
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    # Log every timestamp
    @socketio.on('START_TEST')
    def handle_start_test_debug(data):
        logger.debug(f"T0 (frontend): Video start = {data['video_start_timestamp']} ms")
        T1 = time.perf_counter()
        logger.debug(f"T1 (backend): Event received = {T1:.6f} s")

        T2 = time.perf_counter()
        labjack.start_monitoring()
        logger.debug(f"T2 (backend): Command sent = {T2:.6f} s")

        labjack_time = labjack.get_start_timestamp()
        logger.debug(f"T3 (labjack): Monitoring active = {labjack_time:.6f} s")

        drift_ms = (labjack_time - T1) * 1000
        logger.debug(f"Calculated drift: {drift_ms:.3f} ms")
```

## 10. Future Enhancements

### 10.1 Roadmap

1. **Hardware Timestamping** (Q2 2025)
   - Use LabJack hardware timestamps for video sync
   - Bypass software latency entirely
   - Target: <1ms absolute accuracy

2. **Predictive Drift Compensation** (Q3 2025)
   - Machine learning model predicts drift from network conditions
   - Pre-compensate start timing
   - Target: Zero-shot <5ms drift

3. **Multi-Device Synchronization** (Q4 2025)
   - Sync multiple LabJacks for multi-camera HIL testing
   - GPS or PTP time source
   - Target: <100μs inter-device sync

## 11. References

- NTP Protocol: RFC 5905
- IEEE 1588 Precision Time Protocol
- LabJack T-Series Datasheet
- Browser Performance API Specification
- Python `time` module documentation

---

**Document Version:** 1.0.0
**Author:** System Architecture Designer
**Approved By:** [Pending Review]
**Next Review Date:** 2025-12-20
