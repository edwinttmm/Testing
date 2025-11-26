# HIL Detection Pipeline Monitoring Setup

## Overview

This document describes the comprehensive logging and monitoring setup for the HIL detection pipeline, including Prometheus metrics, logging configuration, and dashboard setup.

## Monitoring Components

### 1. Prometheus Metrics (`monitoring/metrics.py`)

#### Detection Pipeline Metrics
- **hil_detections_total**: Total detection events recorded (labels: session_id, video_id, channel)
- **hil_detection_latency_ms**: Detection processing latency histogram (buckets: 10ms to 2000ms)
- **hil_null_video_id_rate**: Percentage of detections with NULL video_id (gauge)

#### WebSocket Metrics
- **hil_websocket_emissions_total**: Total WebSocket emissions (labels: session_id, success)

#### Queue Processing Metrics
- **hil_queue_flush_total**: Total queue flush operations (labels: session_id, video_id, events_count)
- **hil_queue_size**: Current queue size (labels: session_id)
- **hil_queue_processing_time_ms**: Queue processing time histogram (buckets: 10ms to 1000ms)

#### Video Lifecycle Metrics
- **hil_video_starts_total**: Video start events (labels: session_id, video_id)
- **hil_video_ends_total**: Video end events (labels: session_id, video_id)

#### Timing Synchronization Metrics
- **hil_timing_sync_quality**: Timing sync quality 0-1 (labels: session_id, video_id)
- **hil_calibration_offset_ms**: Calibration offset in milliseconds (labels: session_id)

#### Database Metrics
- **hil_db_storage_success_total**: Successful storage operations
- **hil_db_storage_failures_total**: Failed storage operations (labels: session_id, error_type)

#### Window Validation Metrics
- **hil_window_validation_skipped_early_total**: Detections skipped (too early)
- **hil_window_validation_skipped_late_total**: Detections skipped (too late)
- **hil_window_validation_accepted_total**: Detections accepted within window

### 2. Logging Configuration (`config/logging.yaml`)

#### Log Files
- **hil-detection.log**: Main detection pipeline logs (100MB rotating, JSON format)
- **hil-errors.log**: Error-level logs only (100MB rotating, JSON format)
- **detection-events.log**: Detection event logs (50MB rotating, JSON format)
- **websocket.log**: WebSocket communication logs (50MB rotating, JSON format)

#### Log Levels
- **DEBUG**: `labjack_detection_service`, `dedicated_labjack_monitor`, `detection_queue_service`
- **INFO**: `hil_testing`, `video_sequence_testing`, `websocket_rooms`

### 3. Dashboard Configuration (`config/monitoring.yaml`)

#### HIL Detection Pipeline Dashboard
- Detection Event Rate (rate per 5 minutes)
- NULL Video ID Percentage (gauge with thresholds: 1% yellow, 5% red)
- Detection Latency P95 (milliseconds)
- WebSocket Emission Success Rate (percentage)
- Queue Size (current count)
- Queue Processing Time P95 (milliseconds)
- Timing Sync Quality (percentage)
- Window Validation Stats (accepted, skipped early, skipped late)
- Database Storage Success Rate (percentage)
- Video Lifecycle Events (starts vs ends)

#### HIL Performance Dashboard
- Detection Latency Distribution (heatmap)
- Calibration Offset (milliseconds over time)
- LabJack Connection Status (stat)

## Alert Thresholds

### Critical Alerts
1. **HighNullVideoIdRate**: NULL video_id rate > 5%
   - Indicates queue flush not working properly
   - Check `/video-started` endpoint and queue service

2. **NoDetections**: No detections for 5 minutes during active session
   - Check LabJack hardware connection
   - Verify monitoring loop is running

3. **HighDbStorageFailures**: DB storage failure rate > 5%
   - Check database connectivity
   - Review error logs for schema issues

### Warning Alerts
1. **WebSocketEmissionFailure**: Emission failure rate > 10%
   - Check WebSocket server health
   - Review client connection stability

2. **LabJackDisconnected**: Connection status = 0
   - Check hardware connection
   - Verify USB connection and drivers

3. **HighQueueSize**: Queue size > 100 events
   - Queue flush may be delayed
   - Check `/video-started` endpoint timing

4. **SlowQueueProcessing**: P95 latency > 500ms
   - Database performance degradation
   - Check for lock contention

5. **LowTimingSyncQuality**: Average quality < 80%
   - Review timing synchronization service
   - Check video metadata accuracy

## Instrumentation Locations

### Enhanced Detection Event Logging

**Location**: `services/labjack_detection_service.py`
**Function**: `_record_detection_event()`

```python
logger.info(f"🎯 Detection event recorded: session={session_id}, "
           f"timestamp={event.timestamp_ms}ms, "
           f"channel={event.channel}, "
           f"voltage={event.voltage:.3f}V, "
           f"video_id={event.video_id or 'NULL'}")
```

### WebSocket Emission Logging

**Location**: `main.py` or `services/websocket_rooms.py`
**Function**: WebSocket emission

```python
logger.info(f"📤 WebSocket emission: session={session_id}, "
           f"event_type={data['type']}, "
           f"timestamp={data.get('timestamp', 'N/A')}")
```

### Queue Flush Logging

**Location**: `services/detection_queue_service.py`
**Function**: `flush_queue()`

```python
logger.info(f"🚀 Queue flush triggered: session={session_id}, "
           f"video_id={video_id}, "
           f"queued_events={len(queue)}, "
           f"timestamp={datetime.now().isoformat()}")
```

### /video-started Endpoint Logging

**Location**: `routers/video_sequence_testing.py`
**Function**: `/video-started` endpoint

```python
logger.info(f"🎬 Video started notification: session={session_id}, "
           f"video_id={video_id}, "
           f"video_index={video_index}, "
           f"timestamp={timestamp}")
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install prometheus-client python-json-logger
```

### 2. Initialize Logging

Add to application startup (`main.py`):

```python
import logging.config
import yaml

# Load logging configuration
with open('config/logging.yaml', 'r') as f:
    logging_config = yaml.safe_load(f)
    logging.config.dictConfig(logging_config)

logger = logging.getLogger(__name__)
logger.info("Logging configured from logging.yaml")
```

### 3. Initialize Prometheus Metrics

Add to application startup:

```python
from prometheus_client import start_http_server
from monitoring import metrics

# Start Prometheus metrics server
start_http_server(8001)  # Metrics available at http://localhost:8001/metrics
logger.info("Prometheus metrics server started on port 8001")
```

### 4. Instrument Code

Import metrics in relevant services:

```python
from monitoring.metrics import (
    detections_total,
    detection_latency,
    websocket_emissions,
    queue_flushes,
    null_video_id_rate
)

# Increment detection counter
detections_total.labels(
    session_id=session_id,
    video_id=video_id or "NULL",
    channel=channel
).inc()

# Record latency
with detection_latency.time():
    # Detection processing code
    pass

# Increment WebSocket emission counter
websocket_emissions.labels(
    session_id=session_id,
    success="true"
).inc()

# Record queue flush
queue_flushes.labels(
    session_id=session_id,
    video_id=video_id,
    events_count=str(len(events))
).inc()

# Update NULL video_id rate
total_detections = db.query(DetectionEvent).filter_by(test_session_id=session_id).count()
null_detections = db.query(DetectionEvent).filter_by(test_session_id=session_id, video_id=None).count()
if total_detections > 0:
    null_video_id_rate.set(null_detections / total_detections)
```

## Querying Metrics

### Prometheus Queries

1. **Detection Rate**: `rate(hil_detections_total[5m])`
2. **P95 Latency**: `histogram_quantile(0.95, rate(hil_detection_latency_ms_bucket[5m]))`
3. **NULL Video ID Rate**: `hil_null_video_id_rate * 100`
4. **WebSocket Success Rate**:
   ```promql
   rate(hil_websocket_emissions_total{success="true"}[5m]) /
   rate(hil_websocket_emissions_total[5m]) * 100
   ```
5. **Queue Processing P95**: `histogram_quantile(0.95, rate(hil_queue_processing_time_ms_bucket[5m]))`

### Log Analysis

#### Search for Detection Events
```bash
grep "Detection event recorded" logs/detection-events.log | jq '.'
```

#### Count NULL video_id Events
```bash
grep "video_id.*NULL" logs/detection-events.log | wc -l
```

#### WebSocket Emission Failures
```bash
grep "WebSocket emission.*failed" logs/websocket.log | jq '.'
```

#### Queue Flush Operations
```bash
grep "Queue flush triggered" logs/hil-detection.log | jq '.'
```

## Performance Monitoring

### Key Performance Indicators (KPIs)

1. **Detection Capture Rate**: Should match expected trigger frequency
2. **NULL Video ID Rate**: Should be < 1% (ideally 0%)
3. **Detection Latency P95**: Should be < 200ms
4. **WebSocket Emission Success Rate**: Should be > 99%
5. **Queue Processing Time P95**: Should be < 100ms
6. **Timing Sync Quality**: Should be > 90%

### Troubleshooting Guide

#### High NULL Video ID Rate
- Check `/video-started` endpoint is being called
- Verify queue flush logic is working
- Review timing between video lifecycle events and detections

#### High Detection Latency
- Check database connection pool size
- Review queue processing performance
- Monitor CPU and memory usage

#### WebSocket Emission Failures
- Check client connection stability
- Review server event loop performance
- Monitor network connectivity

#### Queue Not Flushing
- Verify `/video-started` endpoint execution
- Check queue service initialization
- Review session lifecycle management

## Maintenance

### Log Rotation
- Logs automatically rotate at 100MB (main) and 50MB (detection events)
- Backup count: 10 for main logs, 20 for detection events

### Metrics Retention
- Configure Prometheus retention period (default: 15 days)
- Consider remote storage for long-term retention

### Dashboard Updates
- Import `config/monitoring.yaml` into Grafana
- Configure alert channels (email, Slack, PagerDuty)
- Set up alert routing rules

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Python Logging YAML Configuration](https://docs.python.org/3/library/logging.config.html)
- [Grafana Dashboard Design](https://grafana.com/docs/grafana/latest/dashboards/)
