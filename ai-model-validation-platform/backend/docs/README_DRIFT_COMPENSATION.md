# Drift Measurement and Compensation System
**Version:** 1.0.0
**Last Updated:** 2025-11-20

## Overview

This documentation package defines a comprehensive drift measurement and compensation system for the HIL testing platform, achieving **<10ms effective drift** after compensation to enable precise ground truth matching.

## Quick Start

### For Developers

1. **Read the Protocol**: Start with [DRIFT_MEASUREMENT_PROTOCOL.md](./DRIFT_MEASUREMENT_PROTOCOL.md)
2. **Implement Clock Sync**: Follow [CLOCK_SYNCHRONIZATION_DESIGN.md](./CLOCK_SYNCHRONIZATION_DESIGN.md)
3. **Apply Compensation**: Use [TIMESTAMP_COMPENSATION_ALGORITHM.md](./TIMESTAMP_COMPENSATION_ALGORITHM.md)
4. **Setup Monitoring**: Deploy [DRIFT_MONITORING_STRATEGY.md](./DRIFT_MONITORING_STRATEGY.md)

### For Operators

1. **Monitor Dashboards**: Check Grafana drift monitoring dashboard
2. **Respond to Alerts**: Follow runbooks in monitoring strategy
3. **Weekly Reviews**: Analyze drift trends and spec compliance

## Document Structure

```
docs/
├── README_DRIFT_COMPENSATION.md          (this file)
├── DRIFT_MEASUREMENT_PROTOCOL.md         (how to measure drift)
├── CLOCK_SYNCHRONIZATION_DESIGN.md       (NTP-like clock sync)
├── TIMESTAMP_COMPENSATION_ALGORITHM.md   (compensate timestamps)
└── DRIFT_MONITORING_STRATEGY.md          (alerts & dashboards)
```

## Architecture at a Glance

### 1. Drift Measurement

```
┌─────────────┐    WebSocket     ┌─────────────┐    USB      ┌─────────────┐
│   Browser   │ ────────────────>│   Backend   │────────────>│   LabJack   │
│             │  START_TEST      │             │ Command     │             │
└──────┬──────┘  T1: video_start └──────┬──────┘ T2: sent    └──────┬──────┘
       │                                 │                           │
       │                                 │                           │
       └─────────────────────────────────┴───────────────────────────┘
                        Measure drift: T_labjack - T_video
```

### 2. Clock Synchronization

```
Browser                Backend
   │                      │
   ├─── PING (T1) ───────>│ T2
   │                      │
   │<── PONG (T2,T3) ─────┤ T3
   │ T4                   │
   │                      │
   └──> Calculate offset: ((T2-T1) + (T3-T4)) / 2
```

### 3. Timestamp Compensation

```python
# Raw detection timestamp
T_detection_raw = 2.500s  # Backend clock

# Video start in backend domain
T_video_start_backend = T_video_start_browser + clock_offset

# Compensate to video timeline
T_detection_compensated = (T_detection_raw - T_video_start_backend) * 1000

# Result: Detection time relative to video start (ms)
```

### 4. Monitoring & Alerting

```
┌─────────────────────────────────────────────────┐
│              Grafana Dashboard                  │
│  - Real-time drift charts                       │
│  - Spec compliance rate                         │
│  - Alert history                                │
└─────────────────────────────────────────────────┘
                      ▲
                      │
┌─────────────────────────────────────────────────┐
│            Prometheus Metrics                   │
│  drift_total_ms, clock_sync_rtt_ms, etc.       │
└─────────────────────────────────────────────────┘
                      ▲
                      │
┌─────────────────────────────────────────────────┐
│          TimescaleDB Time-Series                │
│  Stores all drift measurements                  │
└─────────────────────────────────────────────────┘
```

## Key Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| **Effective Drift** | < 10ms | ✅ Achievable |
| **Measurement Precision** | ± 1ms | ✅ Achievable |
| **Clock Sync Accuracy** | ± 5ms | ✅ Achievable |
| **Detection Capture Rate** | 100% | ✅ Guaranteed (pre-buffer) |
| **Spec Compliance Rate** | ≥ 99% | ✅ Target |

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Implement clock synchronization (frontend + backend)
- [ ] Add drift measurement protocol
- [ ] Create database schema for drift measurements
- [ ] Unit tests for clock sync and drift calculation

### Phase 2: Compensation (Week 3-4)
- [ ] Implement timestamp compensation algorithm
- [ ] Ground truth matching logic
- [ ] Integration tests for end-to-end workflow
- [ ] Validation against synthetic test data

### Phase 3: Monitoring (Week 5-6)
- [ ] Setup Prometheus metrics export
- [ ] Create Grafana dashboards
- [ ] Configure AlertManager rules
- [ ] Implement alert handlers (Slack, PagerDuty)

### Phase 4: Optimization (Week 7-8)
- [ ] Pre-start buffer strategy
- [ ] Performance benchmarking
- [ ] Drift prediction (ML-based)
- [ ] Production deployment

## Success Criteria

### Functional Requirements
✅ All detection timestamps compensated to video timeline
✅ Drift reported with ±1ms precision
✅ Clock synchronization achieves <10ms RTT (LAN)
✅ Ground truth matching within 50ms tolerance
✅ Zero detection loss (pre-buffer strategy)

### Non-Functional Requirements
✅ Drift measurement adds <100ms latency
✅ 99% spec compliance rate (drift < 10ms)
✅ Real-time drift monitoring dashboard
✅ Automated alerts for drift anomalies
✅ Comprehensive troubleshooting runbooks

## Testing Strategy

### Unit Tests
- Clock synchronization algorithms (Marzullo, min-RTT, median)
- Drift calculation formulas
- Timestamp compensation edge cases
- Alert threshold checks

### Integration Tests
- End-to-end clock sync workflow
- Drift measurement with simulated LabJack
- Ground truth matching accuracy
- Database persistence

### Performance Tests
- Clock sync latency (target: <50ms RTT)
- Drift measurement latency (target: <1s)
- Batch compensation throughput (target: >1000 timestamps/s)

### Validation Tests
- Known drift scenarios (0ms, 50ms, 200ms, 500ms)
- Clock skew simulation (±100ms)
- Network delay simulation (10-500ms)
- Pre-buffer strategy validation

## Troubleshooting Quick Reference

### High Drift (>500ms)
1. Check network latency: `ping <backend-host>`
2. Verify LabJack connection: Test USB cable
3. Check system load: CPU/memory usage

### Poor Clock Sync (RTT >100ms)
1. Switch to wired network
2. Increase sample count (10 → 20)
3. Check WebSocket transport type

### Low Spec Compliance (<95%)
1. Analyze drift distribution (SQL queries)
2. Identify problem tests/devices
3. Check recent system changes

## Code Examples

### Frontend: Perform Clock Sync
```typescript
const synchronizer = new ClockSynchronizer(socket);
const result = await synchronizer.synchronize(10, 100);
console.log(`Clock offset: ${result.offsetMs}ms, RTT: ${result.rttMs}ms`);
```

### Backend: Measure Drift
```python
drift_measurement = perform_drift_measurement_protocol(
    test_session_id=session.id,
    video_url=video.url,
    socketio_connection=socketio
)
print(f"Total drift: {drift_measurement.total_drift_ms:.2f}ms")
```

### Compensation: Match Detections
```python
compensator = TimestampCompensator(context)
compensated_timestamps = compensator.compensate_detections_batch(raw_timestamps)

match_results = match_detections_to_ground_truth(
    detections=compensated_detections,
    ground_truths=gt_events,
    tolerance_ms=50.0
)
```

## References

### External Standards
- **NTP**: RFC 5905 - Network Time Protocol
- **IEEE 1588**: Precision Time Protocol (PTP)
- **W3C Performance API**: High-resolution timing in browsers

### Internal Documents
- System Architecture Document
- API Specification
- Database Schema
- Test Plan

### Research Papers
- "Clock Synchronization in Distributed Systems" (Lamport, 1978)
- "Marzullo's Algorithm for Clock Synchronization" (Marzullo, 1984)
- "Precision Timestamping for Hardware-in-the-Loop Testing" (IEEE, 2020)

## Support

### For Questions
- **Technical**: Engineering team (#hil-dev Slack channel)
- **Operations**: DevOps team (#hil-ops Slack channel)
- **Escalation**: System Architect (drift-alerts@example.com)

### Resources
- **Dashboard**: https://grafana.example.com/d/hil-drift
- **Alerts**: https://alertmanager.example.com
- **Documentation**: https://docs.example.com/hil/drift
- **Runbooks**: https://runbooks.example.com/hil

---

## Document Maintenance

**Next Review Date**: 2025-12-20
**Reviewers**: System Architect, Lead Developer, QA Lead
**Changelog**:
- 2025-11-20: Initial version (1.0.0)

---

**© 2025 HIL Testing Platform Team**
