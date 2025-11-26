# HIL Detection Pipeline Alert Thresholds

## Overview

This document defines alert thresholds for the HIL detection pipeline monitoring system. These thresholds are based on the Queen's diagnostic analysis and production requirements.

## Critical Alerts

### 1. High NULL Video ID Rate
**Metric**: `hil_null_video_id_rate`
**Threshold**: > 5% (0.05)
**Severity**: CRITICAL

**Description**: Detections are being stored without video_id, indicating queue flush failure or timing issues.

**Possible Causes**:
- `/video-started` endpoint not called or delayed
- Queue flush logic not executing
- Race condition between detection capture and video lifecycle events
- Video timing metadata not updated in session

**Resolution**:
1. Check `/video-started` endpoint execution logs
2. Verify queue service is running
3. Review detection timing relative to video start
4. Check database session.sequence_metadata updates

**Prometheus Query**:
```promql
hil_null_video_id_rate > 0.05
```

### 2. No Detections During Active Session
**Metric**: `hil_detections_total`
**Threshold**: 0 detections over 5 minutes during active session
**Severity**: CRITICAL

**Description**: No detection events are being captured during an active test session.

**Possible Causes**:
- LabJack hardware disconnected
- Monitoring loop not running
- Voltage threshold too high
- Channel configuration incorrect
- Hardware trigger not connected

**Resolution**:
1. Check LabJack connection status: `hil_labjack_connection_status`
2. Verify monitoring thread is running
3. Review voltage threshold settings
4. Check hardware wiring and trigger source
5. Test with known trigger signal

**Prometheus Query**:
```promql
rate(hil_detections_total[5m]) == 0
```

### 3. High Database Storage Failures
**Metric**: `hil_db_storage_failures_total` / `hil_db_storage_success_total`
**Threshold**: > 5% failure rate
**Severity**: CRITICAL

**Description**: Detection events are failing to persist to database.

**Possible Causes**:
- Database connection pool exhausted
- Schema migration issues
- Foreign key constraint violations
- Disk space full
- Transaction deadlocks

**Resolution**:
1. Check database connection pool metrics
2. Review error logs for SQLAlchemy exceptions
3. Verify schema matches DetectionEvent model
4. Check disk space on database server
5. Review transaction isolation level

**Prometheus Query**:
```promql
rate(hil_db_storage_failures_total[5m]) /
(rate(hil_db_storage_success_total[5m]) + rate(hil_db_storage_failures_total[5m])) > 0.05
```

## Warning Alerts

### 4. WebSocket Emission Failures
**Metric**: `hil_websocket_emissions_total`
**Threshold**: > 10% failure rate over 1 minute
**Severity**: WARNING

**Description**: WebSocket emissions to frontend are failing.

**Possible Causes**:
- Client disconnected
- Network connectivity issues
- Server event loop blocked
- Too many concurrent emissions

**Resolution**:
1. Check client connection status
2. Review network latency metrics
3. Monitor event loop lag
4. Consider rate limiting emissions

**Prometheus Query**:
```promql
rate(hil_websocket_emissions_total{success="false"}[1m]) /
rate(hil_websocket_emissions_total[1m]) > 0.1
```

### 5. LabJack Disconnected
**Metric**: `hil_labjack_connection_status`
**Threshold**: = 0 (disconnected)
**Severity**: WARNING

**Description**: LabJack hardware connection lost.

**Possible Causes**:
- USB cable disconnected
- Power loss to LabJack
- Driver issues
- Device access conflict

**Resolution**:
1. Check USB connection
2. Verify LabJack power LED
3. Test with LJM library directly
4. Check for driver updates
5. Ensure no other processes using device

**Prometheus Query**:
```promql
hil_labjack_connection_status == 0
```

### 6. High Queue Size
**Metric**: `hil_queue_size`
**Threshold**: > 100 events
**Severity**: WARNING

**Description**: Detection queue is growing, indicating flush delays.

**Possible Causes**:
- `/video-started` endpoint not called
- Queue flush logic not triggered
- Database write performance issues
- Lock contention on queue

**Resolution**:
1. Check video lifecycle event logs
2. Verify queue flush trigger conditions
3. Monitor database write latency
4. Review queue lock contention

**Prometheus Query**:
```promql
hil_queue_size > 100
```

### 7. Slow Queue Processing
**Metric**: `hil_queue_processing_time_ms`
**Threshold**: P95 > 500ms
**Severity**: WARNING

**Description**: Queue flush operations taking too long.

**Possible Causes**:
- Large batch updates
- Database performance degradation
- Network latency to database
- Inefficient UPDATE queries

**Resolution**:
1. Review database query performance
2. Check for missing indexes
3. Monitor database connection pool
4. Consider batch size optimization

**Prometheus Query**:
```promql
histogram_quantile(0.95, rate(hil_queue_processing_time_ms_bucket[5m])) > 500
```

### 8. Low Timing Sync Quality
**Metric**: `hil_timing_sync_quality`
**Threshold**: Average < 0.8 (80%)
**Severity**: WARNING

**Description**: Timing synchronization quality degraded.

**Possible Causes**:
- Video timing metadata inaccurate
- Clock drift between systems
- Calibration offset misconfigured
- Frame rate detection issues

**Resolution**:
1. Verify video metadata accuracy
2. Check system clock synchronization
3. Review calibration offset calculation
4. Validate frame rate detection

**Prometheus Query**:
```promql
avg(hil_timing_sync_quality) < 0.8
```

### 9. High Detection Latency
**Metric**: `hil_detection_latency_ms`
**Threshold**: P95 > 200ms
**Severity**: WARNING

**Description**: Detection processing latency exceeds acceptable threshold.

**Possible Causes**:
- Database write delays
- WebSocket emission backlog
- CPU contention
- Memory pressure

**Resolution**:
1. Profile detection processing pipeline
2. Check database write performance
3. Monitor CPU and memory usage
4. Review concurrent session load

**Prometheus Query**:
```promql
histogram_quantile(0.95, rate(hil_detection_latency_ms_bucket[5m])) > 200
```

### 10. High Window Validation Rejection Rate
**Metric**: `hil_window_validation_skipped_early_total` + `hil_window_validation_skipped_late_total`
**Threshold**: > 20% of total detections
**Severity**: WARNING

**Description**: Too many detections rejected by window validation.

**Possible Causes**:
- Grace period too restrictive
- Video timing metadata incorrect
- Hardware trigger timing drift
- System clock synchronization issues

**Resolution**:
1. Review grace period configuration (GRACE_PERIOD_MS)
2. Verify video start/end timestamps
3. Check hardware trigger timing
4. Validate system clock accuracy

**Prometheus Query**:
```promql
(rate(hil_window_validation_skipped_early_total[5m]) +
 rate(hil_window_validation_skipped_late_total[5m])) /
(rate(hil_window_validation_accepted_total[5m]) +
 rate(hil_window_validation_skipped_early_total[5m]) +
 rate(hil_window_validation_skipped_late_total[5m])) > 0.2
```

## Threshold Tuning Guidelines

### 1. Baseline Establishment
- Run production workload for 7 days
- Calculate P50, P95, P99 for all metrics
- Set thresholds at P99 + 10% margin

### 2. Seasonal Adjustments
- Review thresholds quarterly
- Account for increased load during testing cycles
- Adjust for hardware upgrades

### 3. Alert Fatigue Prevention
- Set appropriate evaluation periods (5m for transient issues, 15m for persistent)
- Use alert grouping for related metrics
- Implement smart alert routing based on severity

### 4. Escalation Policy
1. **INFO**: Log only, no notification
2. **WARNING**: Slack notification to #monitoring channel
3. **CRITICAL**: PagerDuty alert to on-call engineer

## Alert Response Runbook

### Step 1: Acknowledge Alert
- Acknowledge in monitoring system
- Check current system status
- Review recent changes

### Step 2: Initial Diagnosis
- Check related metrics
- Review error logs
- Verify system connectivity

### Step 3: Mitigation
- Apply resolution steps from alert definition
- Monitor metric recovery
- Document actions taken

### Step 4: Post-Incident
- Create incident report
- Update runbook if needed
- Review threshold if false positive

## Metric Collection Best Practices

1. **Cardinality Control**: Limit label combinations to avoid metric explosion
2. **Sampling**: Use histograms for latency metrics, not gauges
3. **Aggregation**: Pre-aggregate metrics at collection time when possible
4. **Retention**: Balance detail level with storage costs

## Related Documentation

- [Monitoring Setup Guide](MONITORING_SETUP.md)
- [Dashboard Configuration](../config/monitoring.yaml)
- [Logging Configuration](../config/logging.yaml)
- [Queen's Diagnostic Report](../../docs/QUEEN_COMPLETE_FIX_REPORT.md)
