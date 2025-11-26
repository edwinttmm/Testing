# Drift Monitoring Strategy
**Version:** 1.0.0
**Last Updated:** 2025-11-20
**Status:** Production-Ready

## Executive Summary

This document defines a comprehensive drift monitoring and alerting strategy to ensure the HIL testing platform maintains **<10ms effective drift** in production. The strategy includes real-time monitoring, automated alerting, performance dashboards, and troubleshooting workflows.

## 1. Monitoring Architecture

### 1.1 Monitoring Layers

```
┌────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                        │
├────────────────────────────────────────────────────────────┤
│  Layer 4: Dashboards & Visualization                      │
│  - Grafana Dashboards                                      │
│  - Real-time drift charts                                  │
│  - Historical trend analysis                               │
├────────────────────────────────────────────────────────────┤
│  Layer 3: Alerting & Notifications                        │
│  - Threshold-based alerts                                  │
│  - Anomaly detection                                       │
│  - PagerDuty/Slack integration                            │
├────────────────────────────────────────────────────────────┤
│  Layer 2: Metrics Collection & Aggregation                │
│  - Prometheus metrics                                      │
│  - Time-series database (TimescaleDB)                     │
│  - Statistical aggregation                                 │
├────────────────────────────────────────────────────────────┤
│  Layer 1: Raw Data Capture                                │
│  - Per-test drift measurements                             │
│  - Clock sync samples                                      │
│  - LabJack timestamps                                      │
└────────────────────────────────────────────────────────────┘
```

### 1.2 Metrics Taxonomy

**Primary Metrics:**
- `drift_total_ms`: Total drift (LabJack start - video start)
- `drift_compensated_effective_ms`: Post-compensation drift
- `clock_offset_ms`: Browser ↔ Backend clock offset
- `clock_sync_rtt_ms`: Clock sync round-trip time

**Component Metrics:**
- `drift_network_delay_ms`: Network propagation time
- `drift_backend_processing_ms`: Backend command processing
- `drift_labjack_latency_ms`: LabJack command latency
- `drift_measurement_uncertainty_ms`: Measurement uncertainty

**Quality Metrics:**
- `drift_spec_compliance_rate`: % of tests with drift < 10ms
- `clock_sync_success_rate`: % of successful clock syncs
- `timestamp_capture_completeness`: % of timestamps captured

## 2. Data Collection

### 2.1 Database Schema

```sql
-- Time-series optimized table for drift measurements
CREATE TABLE drift_measurements (
    id SERIAL PRIMARY KEY,
    test_session_id INTEGER NOT NULL REFERENCES test_sessions(id),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    measurement_timestamp TIMESTAMPTZ NOT NULL,

    -- Primary drift metrics (ms)
    total_drift_ms DOUBLE PRECISION NOT NULL,
    compensated_drift_ms DOUBLE PRECISION NOT NULL,
    clock_offset_ms DOUBLE PRECISION NOT NULL,
    clock_sync_rtt_ms DOUBLE PRECISION NOT NULL,

    -- Drift breakdown (ms)
    network_delay_ms DOUBLE PRECISION,
    backend_processing_ms DOUBLE PRECISION,
    labjack_latency_ms DOUBLE PRECISION,

    -- Quality indicators
    measurement_uncertainty_ms DOUBLE PRECISION,
    drift_within_spec BOOLEAN NOT NULL,
    sync_quality VARCHAR(20) NOT NULL,  -- 'excellent', 'good', 'fair', 'poor'

    -- Metadata
    test_video_id INTEGER REFERENCES test_videos(id),
    labjack_device_id VARCHAR(50),
    network_type VARCHAR(50),  -- 'localhost', 'lan', 'wan'

    -- Indexes for efficient querying
    INDEX idx_drift_created_at (created_at DESC),
    INDEX idx_drift_session (test_session_id),
    INDEX idx_drift_within_spec (drift_within_spec)
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('drift_measurements', 'created_at');

-- Retention policy: Keep detailed data for 90 days, aggregated data forever
SELECT add_retention_policy('drift_measurements', INTERVAL '90 days');

-- Continuous aggregates for fast dashboard queries
CREATE MATERIALIZED VIEW drift_measurements_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', created_at) AS bucket,
    COUNT(*) AS measurement_count,
    AVG(total_drift_ms) AS avg_drift_ms,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_drift_ms) AS median_drift_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY total_drift_ms) AS p95_drift_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_drift_ms) AS p99_drift_ms,
    MAX(total_drift_ms) AS max_drift_ms,
    MIN(total_drift_ms) AS min_drift_ms,
    STDDEV(total_drift_ms) AS stddev_drift_ms,
    SUM(CASE WHEN drift_within_spec THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS spec_compliance_rate,
    AVG(clock_sync_rtt_ms) AS avg_clock_sync_rtt_ms
FROM drift_measurements
GROUP BY bucket;

-- Refresh policy for continuous aggregates
SELECT add_continuous_aggregate_policy('drift_measurements_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

### 2.2 Metrics Export

```python
# backend/services/drift_metrics.py

from prometheus_client import Counter, Histogram, Gauge, Summary
import logging

logger = logging.getLogger(__name__)

# Prometheus metrics
drift_total = Histogram(
    'drift_total_milliseconds',
    'Total drift between video start and LabJack monitoring start',
    buckets=[0, 10, 25, 50, 100, 200, 500, 1000, 2000, 5000]
)

drift_compensated = Histogram(
    'drift_compensated_milliseconds',
    'Post-compensation effective drift',
    buckets=[0, 5, 10, 25, 50, 100]
)

clock_sync_rtt = Histogram(
    'clock_sync_rtt_milliseconds',
    'Clock synchronization round-trip time',
    buckets=[0, 5, 10, 20, 50, 100, 200, 500]
)

clock_offset = Gauge(
    'clock_offset_milliseconds',
    'Clock offset between browser and backend'
)

drift_measurements_total = Counter(
    'drift_measurements_total',
    'Total number of drift measurements performed',
    ['sync_quality', 'within_spec']
)

timestamp_capture_failures = Counter(
    'timestamp_capture_failures_total',
    'Number of failed timestamp captures',
    ['timestamp_type']
)

measurement_latency = Summary(
    'drift_measurement_latency_seconds',
    'Time taken to perform drift measurement'
)


class DriftMetricsCollector:
    """
    Collects and exports drift metrics to monitoring systems
    """

    @staticmethod
    def record_drift_measurement(measurement: DriftMeasurement):
        """
        Record drift measurement to all monitoring systems

        Args:
            measurement: DriftMeasurement object from database
        """
        # Update Prometheus histograms
        drift_total.observe(measurement.total_drift_ms)
        drift_compensated.observe(abs(measurement.compensated_drift_ms))
        clock_sync_rtt.observe(measurement.clock_sync_rtt_ms)
        clock_offset.set(measurement.clock_offset_ms)

        # Update counters
        drift_measurements_total.labels(
            sync_quality=measurement.sync_quality,
            within_spec=str(measurement.drift_within_spec)
        ).inc()

        logger.info(
            f"Drift measurement recorded: "
            f"drift={measurement.total_drift_ms:.2f}ms, "
            f"compensated={measurement.compensated_drift_ms:.2f}ms, "
            f"within_spec={measurement.drift_within_spec}"
        )

    @staticmethod
    def record_timestamp_failure(timestamp_type: str):
        """Record failed timestamp capture"""
        timestamp_capture_failures.labels(timestamp_type=timestamp_type).inc()
        logger.error(f"Timestamp capture failed: {timestamp_type}")

    @staticmethod
    def record_measurement_duration(duration_seconds: float):
        """Record drift measurement latency"""
        measurement_latency.observe(duration_seconds)
```

## 3. Alerting Rules

### 3.1 Alert Definitions

```yaml
# alerts/drift_monitoring_alerts.yml

groups:
  - name: drift_monitoring
    interval: 30s
    rules:

      # CRITICAL: High drift rate
      - alert: HighDriftRate
        expr: |
          (
            sum(rate(drift_measurements_total{within_spec="false"}[5m]))
            /
            sum(rate(drift_measurements_total[5m]))
          ) > 0.05
        for: 5m
        labels:
          severity: critical
          component: drift_measurement
        annotations:
          summary: "High drift failure rate detected"
          description: "{{ $value | humanizePercentage }} of drift measurements exceed 10ms spec (threshold: 5%)"
          runbook_url: "https://docs.example.com/runbooks/high-drift-rate"

      # CRITICAL: Excessive drift detected
      - alert: ExcessiveDrift
        expr: |
          drift_total_milliseconds{quantile="0.95"} > 500
        for: 2m
        labels:
          severity: critical
          component: drift_measurement
        annotations:
          summary: "Excessive drift detected"
          description: "P95 drift is {{ $value }}ms (threshold: 500ms). Possible network or system issue."
          runbook_url: "https://docs.example.com/runbooks/excessive-drift"

      # WARNING: Clock sync degraded
      - alert: ClockSyncDegraded
        expr: |
          clock_sync_rtt_milliseconds{quantile="0.95"} > 100
        for: 5m
        labels:
          severity: warning
          component: clock_sync
        annotations:
          summary: "Clock sync quality degraded"
          description: "P95 clock sync RTT is {{ $value }}ms (threshold: 100ms). Network latency increased."
          runbook_url: "https://docs.example.com/runbooks/clock-sync-degraded"

      # WARNING: Clock offset drift
      - alert: ClockOffsetDrift
        expr: |
          abs(delta(clock_offset_milliseconds[10m])) > 50
        for: 5m
        labels:
          severity: warning
          component: clock_sync
        annotations:
          summary: "Clock offset changing rapidly"
          description: "Clock offset changed by {{ $value }}ms in 10 minutes. Possible clock drift issue."
          runbook_url: "https://docs.example.com/runbooks/clock-offset-drift"

      # WARNING: Timestamp capture failures
      - alert: TimestampCaptureFailures
        expr: |
          rate(timestamp_capture_failures_total[5m]) > 0.01
        for: 2m
        labels:
          severity: warning
          component: drift_measurement
        annotations:
          summary: "Timestamp capture failures detected"
          description: "{{ $value }} timestamp captures failing per second"
          runbook_url: "https://docs.example.com/runbooks/timestamp-failures"

      # INFO: Drift measurement latency high
      - alert: DriftMeasurementLatencyHigh
        expr: |
          drift_measurement_latency_seconds{quantile="0.95"} > 5
        for: 10m
        labels:
          severity: info
          component: drift_measurement
        annotations:
          summary: "Drift measurement taking longer than expected"
          description: "P95 measurement latency is {{ $value }}s (threshold: 5s)"
          runbook_url: "https://docs.example.com/runbooks/measurement-latency"
```

### 3.2 Alert Routing

```yaml
# alertmanager/config.yml

route:
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'default'

  routes:
    # Critical alerts go to PagerDuty + Slack
    - match:
        severity: critical
      receiver: pagerduty-critical
      continue: true

    - match:
        severity: critical
      receiver: slack-critical

    # Warnings go to Slack only
    - match:
        severity: warning
      receiver: slack-warnings

    # Info alerts logged only
    - match:
        severity: info
      receiver: slack-info

receivers:
  - name: 'default'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#hil-testing-alerts'
        title: 'HIL Testing Alert'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: 'YOUR_PAGERDUTY_KEY'
        description: '{{ .CommonAnnotations.summary }}'
        severity: 'critical'

  - name: 'slack-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#hil-critical'
        color: 'danger'
        title: '🚨 CRITICAL: {{ .CommonAnnotations.summary }}'
        text: |
          {{ range .Alerts }}
          *Description:* {{ .Annotations.description }}
          *Runbook:* {{ .Annotations.runbook_url }}
          {{ end }}

  - name: 'slack-warnings'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#hil-testing-alerts'
        color: 'warning'
        title: '⚠️ WARNING: {{ .CommonAnnotations.summary }}'

  - name: 'slack-info'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX'
        channel: '#hil-testing-logs'
        color: 'good'
        title: 'ℹ️ INFO: {{ .CommonAnnotations.summary }}'
```

### 3.3 Alert Handler

```python
# backend/services/alert_handler.py

from typing import Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import requests
import logging

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class DriftAlert:
    """Drift monitoring alert"""
    severity: AlertSeverity
    title: str
    description: str
    metric_name: str
    metric_value: float
    threshold: float
    runbook_url: str
    timestamp: datetime


class DriftAlertHandler:
    """
    Handles drift monitoring alerts with custom logic
    """

    def __init__(self, slack_webhook_url: str = None):
        self.slack_webhook_url = slack_webhook_url
        self.alert_history: List[DriftAlert] = []

    def check_drift_thresholds(self, measurement: DriftMeasurement) -> List[DriftAlert]:
        """
        Check drift measurement against thresholds and generate alerts

        Args:
            measurement: DriftMeasurement from database

        Returns:
            List of alerts generated
        """
        alerts = []

        # Check total drift
        if abs(measurement.total_drift_ms) > 500:
            alerts.append(DriftAlert(
                severity=AlertSeverity.CRITICAL,
                title="Excessive Drift Detected",
                description=f"Total drift {measurement.total_drift_ms:.2f}ms exceeds 500ms threshold",
                metric_name="total_drift_ms",
                metric_value=measurement.total_drift_ms,
                threshold=500.0,
                runbook_url="https://docs.example.com/runbooks/excessive-drift",
                timestamp=datetime.utcnow()
            ))

        # Check compensated drift (should be near zero)
        if abs(measurement.compensated_drift_ms) > 50:
            alerts.append(DriftAlert(
                severity=AlertSeverity.WARNING,
                title="High Compensated Drift",
                description=f"Compensated drift {measurement.compensated_drift_ms:.2f}ms exceeds 50ms",
                metric_name="compensated_drift_ms",
                metric_value=measurement.compensated_drift_ms,
                threshold=50.0,
                runbook_url="https://docs.example.com/runbooks/compensation-failure",
                timestamp=datetime.utcnow()
            ))

        # Check clock sync quality
        if measurement.clock_sync_rtt_ms > 100:
            alerts.append(DriftAlert(
                severity=AlertSeverity.WARNING,
                title="Poor Clock Sync Quality",
                description=f"Clock sync RTT {measurement.clock_sync_rtt_ms:.2f}ms exceeds 100ms",
                metric_name="clock_sync_rtt_ms",
                metric_value=measurement.clock_sync_rtt_ms,
                threshold=100.0,
                runbook_url="https://docs.example.com/runbooks/clock-sync-degraded",
                timestamp=datetime.utcnow()
            ))

        # Check spec compliance
        if not measurement.drift_within_spec:
            alerts.append(DriftAlert(
                severity=AlertSeverity.INFO,
                title="Drift Specification Violation",
                description=f"Drift {measurement.total_drift_ms:.2f}ms exceeds 10ms specification",
                metric_name="drift_within_spec",
                metric_value=measurement.total_drift_ms,
                threshold=10.0,
                runbook_url="https://docs.example.com/runbooks/spec-violation",
                timestamp=datetime.utcnow()
            ))

        # Send alerts
        for alert in alerts:
            self._send_alert(alert)
            self.alert_history.append(alert)

        return alerts

    def _send_alert(self, alert: DriftAlert):
        """Send alert to configured channels"""
        logger.warning(f"DRIFT ALERT [{alert.severity.value}]: {alert.title} - {alert.description}")

        # Send to Slack if configured
        if self.slack_webhook_url:
            self._send_slack_alert(alert)

        # TODO: Send to other channels (email, PagerDuty, etc.)

    def _send_slack_alert(self, alert: DriftAlert):
        """Send alert to Slack"""
        color_map = {
            AlertSeverity.CRITICAL: "danger",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.INFO: "good"
        }

        emoji_map = {
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.INFO: "ℹ️"
        }

        payload = {
            "attachments": [{
                "color": color_map[alert.severity],
                "title": f"{emoji_map[alert.severity]} {alert.title}",
                "text": alert.description,
                "fields": [
                    {
                        "title": "Metric",
                        "value": alert.metric_name,
                        "short": True
                    },
                    {
                        "title": "Value",
                        "value": f"{alert.metric_value:.2f}",
                        "short": True
                    },
                    {
                        "title": "Threshold",
                        "value": f"{alert.threshold:.2f}",
                        "short": True
                    },
                    {
                        "title": "Severity",
                        "value": alert.severity.value,
                        "short": True
                    }
                ],
                "footer": "HIL Drift Monitoring",
                "footer_icon": "https://example.com/icon.png",
                "ts": int(alert.timestamp.timestamp())
            }]
        }

        try:
            response = requests.post(self.slack_webhook_url, json=payload, timeout=5)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    def get_alert_summary(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get summary of alerts in time window"""
        cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)
        recent_alerts = [a for a in self.alert_history if a.timestamp > cutoff]

        return {
            'time_window_hours': time_window_hours,
            'total_alerts': len(recent_alerts),
            'by_severity': {
                'critical': sum(1 for a in recent_alerts if a.severity == AlertSeverity.CRITICAL),
                'warning': sum(1 for a in recent_alerts if a.severity == AlertSeverity.WARNING),
                'info': sum(1 for a in recent_alerts if a.severity == AlertSeverity.INFO)
            },
            'by_metric': {
                metric: sum(1 for a in recent_alerts if a.metric_name == metric)
                for metric in set(a.metric_name for a in recent_alerts)
            }
        }
```

## 4. Dashboards

### 4.1 Grafana Dashboard Configuration

```json
{
  "dashboard": {
    "title": "HIL Drift Monitoring",
    "tags": ["hil", "drift", "monitoring"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Real-Time Drift",
        "type": "graph",
        "targets": [
          {
            "expr": "drift_total_milliseconds",
            "legendFormat": "Total Drift"
          },
          {
            "expr": "drift_compensated_milliseconds",
            "legendFormat": "Compensated Drift"
          }
        ],
        "yaxis": {
          "label": "Drift (ms)",
          "min": 0
        },
        "thresholds": [
          {
            "value": 10,
            "color": "orange",
            "line": true,
            "fill": false
          },
          {
            "value": 50,
            "color": "red",
            "line": true,
            "fill": false
          }
        ]
      },
      {
        "id": 2,
        "title": "Drift Distribution (24h)",
        "type": "histogram",
        "targets": [
          {
            "query": "SELECT total_drift_ms FROM drift_measurements WHERE created_at > NOW() - INTERVAL '24 hours'",
            "format": "time_series"
          }
        ],
        "buckets": [0, 10, 25, 50, 100, 200, 500, 1000]
      },
      {
        "id": 3,
        "title": "Spec Compliance Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(drift_measurements_total{within_spec=\"true\"}[1h])) / sum(rate(drift_measurements_total[1h])) * 100"
          }
        ],
        "thresholds": [
          {
            "value": 95,
            "color": "red"
          },
          {
            "value": 99,
            "color": "orange"
          },
          {
            "value": 100,
            "color": "green"
          }
        ],
        "unit": "percent"
      },
      {
        "id": 4,
        "title": "Clock Sync Quality",
        "type": "graph",
        "targets": [
          {
            "expr": "clock_sync_rtt_milliseconds{quantile=\"0.5\"}",
            "legendFormat": "Median RTT"
          },
          {
            "expr": "clock_sync_rtt_milliseconds{quantile=\"0.95\"}",
            "legendFormat": "P95 RTT"
          },
          {
            "expr": "clock_sync_rtt_milliseconds{quantile=\"0.99\"}",
            "legendFormat": "P99 RTT"
          }
        ],
        "yaxis": {
          "label": "RTT (ms)",
          "min": 0
        }
      },
      {
        "id": 5,
        "title": "Drift Component Breakdown",
        "type": "graph",
        "targets": [
          {
            "query": "SELECT avg(network_delay_ms), avg(backend_processing_ms), avg(labjack_latency_ms) FROM drift_measurements_hourly WHERE bucket > NOW() - INTERVAL '24 hours'",
            "format": "time_series"
          }
        ],
        "stacking": "normal"
      },
      {
        "id": 6,
        "title": "Alert Activity",
        "type": "table",
        "targets": [
          {
            "query": "SELECT created_at, severity, title, description FROM drift_alerts WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC LIMIT 10",
            "format": "table"
          }
        ]
      }
    ]
  }
}
```

### 4.2 Custom Dashboard Widgets

```typescript
// frontend/components/DriftMonitoringWidget.tsx

import React, { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';

interface DriftMetrics {
  totalDriftMs: number;
  compensatedDriftMs: number;
  clockSyncRttMs: number;
  withinSpec: boolean;
  timestamp: Date;
}

export const DriftMonitoringWidget: React.FC = () => {
  const [metrics, setMetrics] = useState<DriftMetrics[]>([]);
  const [currentStats, setCurrentStats] = useState({
    avgDrift: 0,
    p95Drift: 0,
    specComplianceRate: 0
  });

  useEffect(() => {
    // Subscribe to real-time drift metrics
    const socket = io('/drift-monitoring');

    socket.on('drift_measurement', (data: DriftMetrics) => {
      setMetrics(prev => [...prev.slice(-100), data]);  // Keep last 100 measurements
    });

    socket.on('drift_statistics', (stats) => {
      setCurrentStats(stats);
    });

    return () => socket.disconnect();
  }, []);

  const chartData = {
    labels: metrics.map(m => m.timestamp),
    datasets: [
      {
        label: 'Total Drift (ms)',
        data: metrics.map(m => m.totalDriftMs),
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      },
      {
        label: 'Compensated Drift (ms)',
        data: metrics.map(m => m.compensatedDriftMs),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Drift (ms)'
        }
      }
    },
    plugins: {
      annotation: {
        annotations: {
          specLine: {
            type: 'line',
            yMin: 10,
            yMax: 10,
            borderColor: 'orange',
            borderWidth: 2,
            label: {
              content: 'Spec Limit (10ms)',
              enabled: true
            }
          }
        }
      }
    }
  };

  return (
    <div className="drift-monitoring-widget">
      <div className="stats-summary">
        <div className="stat-card">
          <h3>Avg Drift</h3>
          <p className={currentStats.avgDrift < 10 ? 'good' : 'warning'}>
            {currentStats.avgDrift.toFixed(2)} ms
          </p>
        </div>
        <div className="stat-card">
          <h3>P95 Drift</h3>
          <p className={currentStats.p95Drift < 50 ? 'good' : 'warning'}>
            {currentStats.p95Drift.toFixed(2)} ms
          </p>
        </div>
        <div className="stat-card">
          <h3>Spec Compliance</h3>
          <p className={currentStats.specComplianceRate > 99 ? 'good' : 'warning'}>
            {currentStats.specComplianceRate.toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="chart-container">
        <Line data={chartData} options={chartOptions} />
      </div>

      <div className="latest-measurements">
        <h4>Latest Measurements</h4>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Total Drift</th>
              <th>Compensated</th>
              <th>RTT</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {metrics.slice(-10).reverse().map((m, idx) => (
              <tr key={idx} className={m.withinSpec ? 'within-spec' : 'outside-spec'}>
                <td>{new Date(m.timestamp).toLocaleTimeString()}</td>
                <td>{m.totalDriftMs.toFixed(2)} ms</td>
                <td>{m.compensatedDriftMs.toFixed(2)} ms</td>
                <td>{m.clockSyncRttMs.toFixed(2)} ms</td>
                <td>{m.withinSpec ? '✓' : '✗'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
```

## 5. Troubleshooting Workflows

### 5.1 Runbook: Excessive Drift

**Trigger**: Total drift > 500ms

**Investigation Steps:**

1. **Check Network Connectivity**
   ```bash
   # Measure network latency
   ping -c 10 <backend-host>

   # Expected: <10ms for localhost, <50ms for LAN
   ```

2. **Verify Clock Synchronization**
   ```python
   # Check clock sync quality
   GET /api/drift/clock-sync-status

   # Expected: RTT < 50ms, offset < 100ms
   ```

3. **Check LabJack Connection**
   ```python
   # Test LabJack response time
   python scripts/test_labjack_latency.py

   # Expected: <20ms command latency
   ```

4. **Examine System Load**
   ```bash
   # Check CPU/memory usage
   top -bn1 | grep "Cpu(s)"
   free -m

   # Expected: CPU < 80%, memory < 90%
   ```

**Resolution:**
- Network issue: Switch to wired connection, restart router
- Clock sync issue: Force re-sync, check NTP configuration
- LabJack issue: Check USB cable, update firmware
- System load: Close background apps, upgrade hardware

### 5.2 Runbook: Clock Sync Degraded

**Trigger**: Clock sync RTT > 100ms

**Investigation Steps:**

1. **Test Network Path**
   ```bash
   traceroute <backend-host>
   mtr -r -c 10 <backend-host>
   ```

2. **Check WebSocket Connection**
   ```javascript
   // Frontend console
   socket.io.engine.transport.name  // Should be 'websocket', not 'polling'
   ```

3. **Verify Server Performance**
   ```python
   GET /api/drift/clock-sync-metrics

   # Check server processing time < 100μs
   ```

**Resolution:**
- Upgrade to WebSocket transport if using long-polling
- Increase clock sync sample count (10 → 20)
- Use wired network instead of WiFi

### 5.3 Runbook: Spec Compliance Rate Low

**Trigger**: Spec compliance < 95%

**Investigation Steps:**

1. **Analyze Drift Distribution**
   ```sql
   SELECT
     percentile_cont(0.5) WITHIN GROUP (ORDER BY total_drift_ms) AS p50,
     percentile_cont(0.95) WITHIN GROUP (ORDER BY total_drift_ms) AS p95,
     percentile_cont(0.99) WITHIN GROUP (ORDER BY total_drift_ms) AS p99
   FROM drift_measurements
   WHERE created_at > NOW() - INTERVAL '1 hour';
   ```

2. **Check Drift Trends**
   ```sql
   SELECT
     date_trunc('hour', created_at) AS hour,
     avg(total_drift_ms) AS avg_drift
   FROM drift_measurements
   WHERE created_at > NOW() - INTERVAL '24 hours'
   GROUP BY hour
   ORDER BY hour;
   ```

3. **Identify Problem Tests**
   ```sql
   SELECT
     test_session_id,
     total_drift_ms,
     network_type,
     labjack_device_id
   FROM drift_measurements
   WHERE total_drift_ms > 10
     AND created_at > NOW() - INTERVAL '1 hour'
   ORDER BY total_drift_ms DESC;
   ```

**Resolution:**
- If specific device: Check LabJack hardware
- If time-correlated: Check system/network at that time
- If test-correlated: Check video file or test configuration

## 6. Performance Benchmarks

### 6.1 Target SLAs

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Spec Compliance Rate | ≥ 99% | < 99% | < 95% |
| P95 Total Drift | < 50ms | < 100ms | ≥ 100ms |
| P99 Total Drift | < 100ms | < 200ms | ≥ 200ms |
| Clock Sync RTT | < 20ms | < 50ms | ≥ 100ms |
| Measurement Latency | < 1s | < 2s | ≥ 5s |

### 6.2 Benchmark Tests

```python
# benchmarks/drift_monitoring_benchmark.py

import time
import statistics
from services.drift_measurement import perform_drift_measurement

def benchmark_drift_measurement(num_iterations=100):
    """
    Benchmark drift measurement performance

    Target: < 1s per measurement
    """
    latencies = []

    for i in range(num_iterations):
        start_time = time.perf_counter()
        measurement = perform_drift_measurement()
        end_time = time.perf_counter()

        latency = end_time - start_time
        latencies.append(latency)

        print(f"Iteration {i+1}: {latency*1000:.2f}ms")

    print(f"\nResults ({num_iterations} iterations):")
    print(f"  Mean: {statistics.mean(latencies)*1000:.2f}ms")
    print(f"  Median: {statistics.median(latencies)*1000:.2f}ms")
    print(f"  P95: {sorted(latencies)[int(0.95*len(latencies))]*1000:.2f}ms")
    print(f"  P99: {sorted(latencies)[int(0.99*len(latencies))]*1000:.2f}ms")
    print(f"  Max: {max(latencies)*1000:.2f}ms")

    assert statistics.mean(latencies) < 1.0, "Mean latency exceeds 1s target"


if __name__ == '__main__':
    benchmark_drift_measurement()
```

## 7. Continuous Improvement

### 7.1 Metrics Review Schedule

| Frequency | Review Type | Stakeholders |
|-----------|-------------|--------------|
| Daily | Quick status check | Engineering team |
| Weekly | Trend analysis | Team lead, QA |
| Monthly | Performance review | Management, stakeholders |
| Quarterly | Architecture review | System architect, CTO |

### 7.2 Improvement Tracking

```python
# backend/models/drift_improvement.py

class DriftImprovementTarget(Base):
    __tablename__ = 'drift_improvement_targets'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    target_date = Column(Date, nullable=False)

    # Current vs target metrics
    current_p95_drift_ms = Column(Float, nullable=False)
    target_p95_drift_ms = Column(Float, nullable=False)

    current_spec_compliance_rate = Column(Float, nullable=False)
    target_spec_compliance_rate = Column(Float, nullable=False)

    # Improvement actions
    improvement_actions = Column(JSON, nullable=False)  # List of planned actions
    status = Column(String(20), nullable=False)  # 'planned', 'in_progress', 'completed'

    # Results
    actual_p95_drift_ms = Column(Float, nullable=True)
    actual_spec_compliance_rate = Column(Float, nullable=True)
    completion_date = Column(Date, nullable=True)
```

## 8. Documentation & Training

### 8.1 Operator Training

**Topics:**
1. Understanding drift metrics
2. Interpreting dashboard widgets
3. Responding to alerts
4. Running troubleshooting workflows
5. Escalation procedures

**Materials:**
- Video tutorials
- Interactive dashboard walkthroughs
- Runbook simulations
- Quiz assessments

### 8.2 Documentation Links

- [Drift Measurement Protocol](./DRIFT_MEASUREMENT_PROTOCOL.md)
- [Clock Synchronization Design](./CLOCK_SYNCHRONIZATION_DESIGN.md)
- [Timestamp Compensation Algorithm](./TIMESTAMP_COMPENSATION_ALGORITHM.md)
- [API Reference](./API_REFERENCE.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)

---

**Document Version:** 1.0.0
**Author:** System Architecture Designer
**Approved By:** [Pending Review]
**Next Review Date:** 2025-12-20
