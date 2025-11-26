# Clock Synchronization Design
**Version:** 1.0.0
**Last Updated:** 2025-11-20
**Status:** Production-Ready

## Executive Summary

This document defines an NTP-like clock synchronization protocol to eliminate clock skew between browser (frontend) and backend systems, achieving **±5ms clock offset accuracy** for precise drift compensation in HIL testing.

## 1. Problem Statement

### 1.1 Clock Skew Sources

Different systems maintain independent clocks that drift over time:

- **Browser**: `performance.now()` - High-resolution monotonic timer (microsecond precision)
- **Backend**: `time.perf_counter()` - OS monotonic timer (microsecond precision)
- **LabJack**: Hardware clock - Device oscillator (nanosecond precision)

**Key Issue**: Browser and backend clocks are initialized independently and drift due to:
- Different oscillator frequencies
- Temperature variations
- Power management (CPU throttling)
- System load (interrupt latency)

Typical clock skew: **±50-200ms** without synchronization.

### 1.2 Impact on Drift Measurement

```
Without clock sync:
  video_start (browser clock): 1000.0 ms
  labjack_start (backend clock): 1100.0 ms
  Reported drift: 100 ms
  Actual drift: 50 ms (50 ms is clock skew!)

With clock sync (offset = +50 ms):
  video_start_adjusted: 1000.0 + 50 = 1050.0 ms
  labjack_start: 1100.0 ms
  Corrected drift: 50 ms ✓
```

## 2. NTP-Like Protocol Design

### 2.1 Basic Ping-Pong Exchange

```
┌─────────────┐                              ┌─────────────┐
│   Browser   │                              │   Backend   │
│ (Client)    │                              │  (Server)   │
└──────┬──────┘                              └──────┬──────┘
       │                                            │
       │ T1: CLOCK_SYNC_REQUEST                    │
       │    client_send_time = T1                  │
       ├──────────────────────────────────────────>│
       │                                            │ T2: Request Received
       │                                            │     server_receive_time = T2
       │                                            │
       │                                            │ T3: Response Sent
       │    CLOCK_SYNC_RESPONSE                     │     server_send_time = T3
       │    {T2, T3}                                │
       │<──────────────────────────────────────────┤
       │ T4: Response Received                      │
       │     client_receive_time = T4               │
       │                                            │
       │ Calculate:                                 │
       │   RTT = T4 - T1                            │
       │   Offset = ((T2-T1) + (T3-T4)) / 2         │
```

### 2.2 Mathematical Foundation

**Round-Trip Time (RTT):**
```
RTT = (T4 - T1)
```

**Clock Offset (θ):**
```
θ = ((T2 - T1) + (T3 - T4)) / 2
```

**Derivation:**

Let:
- `δ` = forward propagation delay (client → server)
- `θ` = clock offset (server clock - client clock)

Then:
```
T2 = T1 + δ + θ        (server receives)
T4 = T3 + δ - θ        (client receives)

Solving for θ:
T2 - T1 = δ + θ
T3 - T4 = -δ + θ

Adding equations:
(T2 - T1) + (T3 - T4) = 2θ

θ = ((T2 - T1) + (T3 - T4)) / 2
```

**Assumptions:**
1. Forward and reverse delays are approximately equal: `δ_forward ≈ δ_reverse`
2. Server processing time is negligible (< 1ms)
3. Network delay is symmetric (reasonable for LAN/localhost)

### 2.3 Multi-Sample Averaging

Single measurements are noisy due to network jitter. Use multiple samples:

```python
import numpy as np
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class ClockSyncSample:
    T1: float  # Client send (ms)
    T2: float  # Server receive (ms)
    T3: float  # Server send (ms)
    T4: float  # Client receive (ms)

    @property
    def rtt_ms(self) -> float:
        return self.T4 - self.T1

    @property
    def offset_ms(self) -> float:
        return ((self.T2 - self.T1) + (self.T3 - self.T4)) / 2

    @property
    def delay_ms(self) -> float:
        """One-way delay estimate"""
        return self.rtt_ms / 2


def perform_clock_sync_multi_sample(
    num_samples: int = 10,
    sample_interval_ms: int = 100
) -> Tuple[float, float, List[ClockSyncSample]]:
    """
    Perform multi-sample clock synchronization

    Returns:
        offset_ms: Best estimate of clock offset (server - client)
        rtt_ms: Minimum RTT observed
        samples: All sync samples for analysis
    """
    samples = []

    for i in range(num_samples):
        # Send sync request
        T1 = performance.now()
        response = await socketio.emit_and_wait('CLOCK_SYNC_REQUEST', {
            'T1': T1,
            'sample_index': i
        })
        T4 = performance.now()

        sample = ClockSyncSample(
            T1=T1,
            T2=response['T2'],
            T3=response['T3'],
            T4=T4
        )
        samples.append(sample)

        # Wait before next sample
        if i < num_samples - 1:
            await sleep(sample_interval_ms)

    # Select best samples using Marzullo's algorithm
    best_offset, best_rtt = select_best_clock_estimate(samples)

    return best_offset, best_rtt, samples
```

## 3. Algorithm Selection

### 3.1 Simple Minimum RTT Filter

**Strategy**: Use offset from sample with minimum RTT (assumes minimum delay = least network interference)

```python
def simple_min_rtt_filter(samples: List[ClockSyncSample]) -> Tuple[float, float]:
    """
    Select offset from sample with minimum RTT
    """
    best_sample = min(samples, key=lambda s: s.rtt_ms)
    return best_sample.offset_ms, best_sample.rtt_ms
```

**Pros:**
- Simple, fast
- Works well for LAN/localhost
- Eliminates samples with network queuing

**Cons:**
- Single-sample result (no averaging)
- Vulnerable to outliers

### 3.2 Median-Based Filter

**Strategy**: Use median offset from all samples

```python
def median_filter(samples: List[ClockSyncSample]) -> Tuple[float, float]:
    """
    Use median offset from all samples
    """
    offsets = [s.offset_ms for s in samples]
    rtts = [s.rtt_ms for s in samples]

    return np.median(offsets), np.median(rtts)
```

**Pros:**
- Robust to outliers
- More stable than single sample

**Cons:**
- Includes high-delay samples
- Less accurate than min-RTT for good networks

### 3.3 Marzullo's Algorithm (Recommended)

**Strategy**: Find intersection of confidence intervals, weight by uncertainty

```python
def marzullo_algorithm(samples: List[ClockSyncSample]) -> Tuple[float, float]:
    """
    Marzullo's algorithm for clock sync (used in NTP)

    Creates confidence intervals for each sample based on RTT,
    then finds best consensus interval.
    """
    intervals = []

    for sample in samples:
        # Uncertainty is ±RTT/2 (one-way delay uncertainty)
        uncertainty = sample.rtt_ms / 2
        lower = sample.offset_ms - uncertainty
        upper = sample.offset_ms + uncertainty

        intervals.append((lower, 1))   # Interval start
        intervals.append((upper, -1))  # Interval end

    # Sort by position
    intervals.sort(key=lambda x: x[0])

    # Find interval with maximum overlap
    max_overlap = 0
    current_overlap = 0
    best_start = 0
    best_end = 0

    for i, (pos, delta) in enumerate(intervals):
        current_overlap += delta

        if current_overlap > max_overlap:
            max_overlap = current_overlap
            best_start = pos
            # Find next position as end
            if i + 1 < len(intervals):
                best_end = intervals[i + 1][0]

    # Best estimate is center of best interval
    best_offset = (best_start + best_end) / 2

    # Report minimum RTT as quality metric
    best_rtt = min(s.rtt_ms for s in samples)

    return best_offset, best_rtt
```

**Pros:**
- Optimal for NTP-like scenarios
- Handles outliers gracefully
- Accounts for measurement uncertainty

**Cons:**
- More complex
- Requires multiple samples

### 3.4 Algorithm Comparison

| Algorithm | Accuracy | Robustness | Complexity | Best For |
|-----------|----------|------------|------------|----------|
| Min RTT | Excellent (LAN) | Good | Low | Stable networks |
| Median | Good | Excellent | Low | Noisy networks |
| Marzullo | Excellent | Excellent | Medium | Production systems |

**Recommendation**: Use **Marzullo's algorithm** for production, with min-RTT as fallback.

## 4. Implementation

### 4.1 Frontend (TypeScript)

```typescript
// src/services/clockSync.ts

interface ClockSyncSample {
  T1: number;  // Client send
  T2: number;  // Server receive
  T3: number;  // Server send
  T4: number;  // Client receive
  rtt: number;
  offset: number;
}

interface ClockSyncResult {
  offsetMs: number;
  rttMs: number;
  samples: ClockSyncSample[];
  accuracy: 'excellent' | 'good' | 'fair' | 'poor';
  timestamp: Date;
}

class ClockSynchronizer {
  private socket: Socket;
  private currentSync: ClockSyncResult | null = null;
  private syncIntervalId: number | null = null;

  constructor(socket: Socket) {
    this.socket = socket;
  }

  /**
   * Perform clock synchronization with backend
   */
  async synchronize(
    numSamples: number = 10,
    sampleIntervalMs: number = 100
  ): Promise<ClockSyncResult> {
    const samples: ClockSyncSample[] = [];

    for (let i = 0; i < numSamples; i++) {
      const sample = await this.performSingleSync();
      samples.push(sample);

      if (i < numSamples - 1) {
        await this.sleep(sampleIntervalMs);
      }
    }

    // Use Marzullo's algorithm
    const { offsetMs, rttMs } = this.marzulloAlgorithm(samples);

    const result: ClockSyncResult = {
      offsetMs,
      rttMs,
      samples,
      accuracy: this.assessAccuracy(rttMs),
      timestamp: new Date()
    };

    this.currentSync = result;
    console.log(`Clock sync complete: offset=${offsetMs.toFixed(2)}ms, RTT=${rttMs.toFixed(2)}ms`);

    return result;
  }

  /**
   * Perform single sync sample
   */
  private async performSingleSync(): Promise<ClockSyncSample> {
    return new Promise((resolve, reject) => {
      const T1 = performance.now();

      this.socket.emit('CLOCK_SYNC_REQUEST', { T1 }, (response: any) => {
        const T4 = performance.now();

        if (!response || !response.T2 || !response.T3) {
          reject(new Error('Invalid clock sync response'));
          return;
        }

        const T2 = response.T2;
        const T3 = response.T3;

        const rtt = T4 - T1;
        const offset = ((T2 - T1) + (T3 - T4)) / 2;

        resolve({ T1, T2, T3, T4, rtt, offset });
      });

      // Timeout after 1 second
      setTimeout(() => reject(new Error('Clock sync timeout')), 1000);
    });
  }

  /**
   * Marzullo's algorithm implementation
   */
  private marzulloAlgorithm(samples: ClockSyncSample[]): { offsetMs: number; rttMs: number } {
    const intervals: Array<[number, number]> = [];

    samples.forEach(sample => {
      const uncertainty = sample.rtt / 2;
      intervals.push([sample.offset - uncertainty, 1]);
      intervals.push([sample.offset + uncertainty, -1]);
    });

    intervals.sort((a, b) => a[0] - b[0]);

    let maxOverlap = 0;
    let currentOverlap = 0;
    let bestStart = 0;
    let bestEnd = 0;

    for (let i = 0; i < intervals.length; i++) {
      const [pos, delta] = intervals[i];
      currentOverlap += delta;

      if (currentOverlap > maxOverlap) {
        maxOverlap = currentOverlap;
        bestStart = pos;
        bestEnd = i + 1 < intervals.length ? intervals[i + 1][0] : pos;
      }
    }

    const offsetMs = (bestStart + bestEnd) / 2;
    const rttMs = Math.min(...samples.map(s => s.rtt));

    return { offsetMs, rttMs };
  }

  /**
   * Assess clock sync accuracy
   */
  private assessAccuracy(rttMs: number): 'excellent' | 'good' | 'fair' | 'poor' {
    if (rttMs < 10) return 'excellent';      // < 10ms RTT
    if (rttMs < 50) return 'good';           // < 50ms RTT
    if (rttMs < 100) return 'fair';          // < 100ms RTT
    return 'poor';                            // > 100ms RTT
  }

  /**
   * Get current clock offset (with auto-resync if stale)
   */
  async getClockOffset(): Promise<number> {
    if (!this.currentSync || this.isSyncStale()) {
      await this.synchronize();
    }
    return this.currentSync!.offsetMs;
  }

  /**
   * Check if sync is stale (> 5 minutes old)
   */
  private isSyncStale(): boolean {
    if (!this.currentSync) return true;
    const ageMs = Date.now() - this.currentSync.timestamp.getTime();
    return ageMs > 5 * 60 * 1000;  // 5 minutes
  }

  /**
   * Start automatic resync every 5 minutes
   */
  startAutoResync(intervalMs: number = 5 * 60 * 1000) {
    this.stopAutoResync();
    this.syncIntervalId = window.setInterval(() => {
      this.synchronize().catch(err => {
        console.error('Auto clock resync failed:', err);
      });
    }, intervalMs);
  }

  /**
   * Stop automatic resync
   */
  stopAutoResync() {
    if (this.syncIntervalId !== null) {
      clearInterval(this.syncIntervalId);
      this.syncIntervalId = null;
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export default ClockSynchronizer;
```

### 4.2 Backend (Python)

```python
# backend/services/clock_sync.py

from flask_socketio import emit
import time
from typing import Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClockSyncMetrics:
    """Metrics for monitoring clock sync performance"""
    total_requests: int = 0
    avg_processing_time_us: float = 0.0
    min_processing_time_us: float = float('inf')
    max_processing_time_us: float = 0.0


class ClockSyncHandler:
    """
    Handles clock synchronization requests from frontend
    """

    def __init__(self):
        self.metrics = ClockSyncMetrics()

    def handle_sync_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle CLOCK_SYNC_REQUEST from frontend

        Must respond with minimal latency to ensure accurate sync
        """
        # Timestamp as early as possible
        T2 = time.perf_counter() * 1000  # Convert to milliseconds

        # Extract T1 from request
        T1 = data.get('T1')
        if T1 is None:
            logger.error("Clock sync request missing T1 timestamp")
            return {'error': 'Missing T1 timestamp'}

        # Minimal processing (just prepare response)
        # T3 captured immediately before sending
        T3 = time.perf_counter() * 1000

        # Update metrics
        processing_time_us = (T3 - T2) * 1000  # ms to μs
        self._update_metrics(processing_time_us)

        response = {
            'T2': T2,
            'T3': T3,
            'server_processing_us': processing_time_us
        }

        logger.debug(f"Clock sync: T2={T2:.3f}ms, T3={T3:.3f}ms, processing={processing_time_us:.1f}μs")

        return response

    def _update_metrics(self, processing_time_us: float):
        """Update performance metrics"""
        self.metrics.total_requests += 1

        # Running average
        n = self.metrics.total_requests
        self.metrics.avg_processing_time_us = (
            (self.metrics.avg_processing_time_us * (n - 1) + processing_time_us) / n
        )

        self.metrics.min_processing_time_us = min(
            self.metrics.min_processing_time_us,
            processing_time_us
        )

        self.metrics.max_processing_time_us = max(
            self.metrics.max_processing_time_us,
            processing_time_us
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get clock sync performance metrics"""
        return {
            'total_requests': self.metrics.total_requests,
            'avg_processing_time_us': round(self.metrics.avg_processing_time_us, 2),
            'min_processing_time_us': round(self.metrics.min_processing_time_us, 2),
            'max_processing_time_us': round(self.metrics.max_processing_time_us, 2)
        }


# Global instance
clock_sync_handler = ClockSyncHandler()


# SocketIO event handler
def register_clock_sync_handlers(socketio):
    """
    Register clock sync event handlers with SocketIO
    """

    @socketio.on('CLOCK_SYNC_REQUEST')
    def handle_clock_sync_request(data):
        """
        Handle clock sync request with immediate response

        CRITICAL: This handler must have MINIMAL processing time
        """
        response = clock_sync_handler.handle_sync_request(data)
        return response  # Synchronous response (uses callback)

    @socketio.on('CLOCK_SYNC_METRICS')
    def handle_clock_sync_metrics():
        """Get clock sync performance metrics"""
        return clock_sync_handler.get_metrics()
```

### 4.3 SocketIO Event Registration

```python
# backend/app.py

from flask import Flask
from flask_socketio import SocketIO
from services.clock_sync import register_clock_sync_handlers

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Register clock sync handlers
register_clock_sync_handlers(socketio)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
```

## 5. Validation & Testing

### 5.1 Unit Tests

```python
# tests/test_clock_sync.py

import pytest
import time
from services.clock_sync import ClockSyncHandler


class TestClockSync:

    def test_sync_request_response_time(self):
        """Verify sync handler responds in < 100μs"""
        handler = ClockSyncHandler()

        T1 = time.perf_counter() * 1000
        response = handler.handle_sync_request({'T1': T1})

        assert 'T2' in response
        assert 'T3' in response
        assert response['server_processing_us'] < 100, "Server processing too slow"

    def test_sync_timestamp_ordering(self):
        """Verify T2 < T3 (causality)"""
        handler = ClockSyncHandler()

        response = handler.handle_sync_request({'T1': 1000.0})

        assert response['T2'] < response['T3'], "T2 must be before T3"

    def test_metrics_tracking(self):
        """Verify metrics are tracked correctly"""
        handler = ClockSyncHandler()

        # Perform 10 sync requests
        for _ in range(10):
            handler.handle_sync_request({'T1': time.perf_counter() * 1000})

        metrics = handler.get_metrics()
        assert metrics['total_requests'] == 10
        assert metrics['avg_processing_time_us'] > 0
```

```typescript
// tests/clockSync.test.ts

import ClockSynchronizer from '../services/clockSync';
import { io, Socket } from 'socket.io-client';

describe('Clock Synchronization', () => {
  let socket: Socket;
  let synchronizer: ClockSynchronizer;

  beforeAll(() => {
    socket = io('http://localhost:5000');
    synchronizer = new ClockSynchronizer(socket);
  });

  afterAll(() => {
    socket.disconnect();
  });

  test('Should perform single sync sample', async () => {
    const sample = await synchronizer['performSingleSync']();

    expect(sample.T1).toBeLessThan(sample.T4);
    expect(sample.T2).toBeLessThan(sample.T3);
    expect(sample.rtt).toBeGreaterThan(0);
  });

  test('Should complete full synchronization', async () => {
    const result = await synchronizer.synchronize(5, 50);

    expect(result.samples).toHaveLength(5);
    expect(result.offsetMs).toBeDefined();
    expect(result.rttMs).toBeDefined();
    expect(['excellent', 'good', 'fair', 'poor']).toContain(result.accuracy);
  });

  test('Should detect stale sync', async () => {
    synchronizer['currentSync'] = {
      offsetMs: 0,
      rttMs: 10,
      samples: [],
      accuracy: 'good',
      timestamp: new Date(Date.now() - 10 * 60 * 1000) // 10 minutes ago
    };

    expect(synchronizer['isSyncStale']()).toBe(true);
  });

  test('Should auto-resync when stale', async () => {
    synchronizer['currentSync'] = null;

    const offset = await synchronizer.getClockOffset();

    expect(synchronizer['currentSync']).not.toBeNull();
    expect(typeof offset).toBe('number');
  });
});
```

### 5.2 Integration Tests

```python
# tests/integration/test_clock_sync_e2e.py

import pytest
import asyncio
import socketio
import time


@pytest.mark.integration
async def test_end_to_end_clock_sync():
    """Test complete clock sync workflow"""

    # Connect to backend
    sio = socketio.AsyncClient()
    await sio.connect('http://localhost:5000')

    # Perform 10 sync samples
    samples = []
    for i in range(10):
        T1 = time.perf_counter() * 1000

        response = await sio.call('CLOCK_SYNC_REQUEST', {'T1': T1})

        T4 = time.perf_counter() * 1000
        T2 = response['T2']
        T3 = response['T3']

        rtt = T4 - T1
        offset = ((T2 - T1) + (T3 - T4)) / 2

        samples.append({'rtt': rtt, 'offset': offset})

        await asyncio.sleep(0.1)

    # Verify RTT is reasonable (< 50ms for localhost)
    avg_rtt = sum(s['rtt'] for s in samples) / len(samples)
    assert avg_rtt < 50, f"Average RTT {avg_rtt} ms too high for localhost"

    # Verify offset consistency (< 10ms variance)
    offsets = [s['offset'] for s in samples]
    offset_std = (sum((o - sum(offsets)/len(offsets))**2 for o in offsets) / len(offsets)) ** 0.5
    assert offset_std < 10, f"Offset variance {offset_std} ms too high"

    await sio.disconnect()
```

### 5.3 Performance Benchmarks

```python
# benchmarks/clock_sync_benchmark.py

import time
from services.clock_sync import ClockSyncHandler

def benchmark_sync_handler_latency(num_iterations=1000):
    """
    Benchmark clock sync handler processing latency

    Target: < 100μs per request
    """
    handler = ClockSyncHandler()
    latencies = []

    for _ in range(num_iterations):
        T1 = time.perf_counter() * 1000
        response = handler.handle_sync_request({'T1': T1})
        latency_us = response['server_processing_us']
        latencies.append(latency_us)

    print(f"\nClock Sync Handler Benchmark ({num_iterations} iterations):")
    print(f"  Mean latency: {sum(latencies)/len(latencies):.2f} μs")
    print(f"  Min latency:  {min(latencies):.2f} μs")
    print(f"  Max latency:  {max(latencies):.2f} μs")
    print(f"  P95 latency:  {sorted(latencies)[int(0.95*len(latencies))]:.2f} μs")
    print(f"  P99 latency:  {sorted(latencies)[int(0.99*len(latencies))]:.2f} μs")

    # Verify < 100μs requirement
    assert sum(latencies)/len(latencies) < 100, "Mean latency exceeds 100μs"


if __name__ == '__main__':
    benchmark_sync_handler_latency()
```

## 6. Monitoring & Alerting

### 6.1 Metrics Collection

```python
# backend/services/monitoring.py

from dataclasses import dataclass, asdict
from typing import List, Dict, Any
from datetime import datetime, timedelta
import statistics


@dataclass
class ClockSyncEvent:
    timestamp: datetime
    offset_ms: float
    rtt_ms: float
    accuracy: str
    client_id: str


class ClockSyncMonitor:
    """
    Monitor clock sync quality and alert on anomalies
    """

    def __init__(self, alert_threshold_ms: float = 50.0):
        self.events: List[ClockSyncEvent] = []
        self.alert_threshold_ms = alert_threshold_ms

    def record_sync(self, event: ClockSyncEvent):
        """Record a clock sync event"""
        self.events.append(event)

        # Alert if RTT is excessive
        if event.rtt_ms > self.alert_threshold_ms:
            self._alert_high_rtt(event)

        # Alert if offset changes dramatically
        if len(self.events) > 1:
            prev_offset = self.events[-2].offset_ms
            offset_change = abs(event.offset_ms - prev_offset)
            if offset_change > 50:  # Clock jumped > 50ms
                self._alert_clock_jump(event, offset_change)

    def get_statistics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get clock sync statistics over time window"""
        cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)
        recent_events = [e for e in self.events if e.timestamp > cutoff]

        if not recent_events:
            return {'error': 'No events in time window'}

        offsets = [e.offset_ms for e in recent_events]
        rtts = [e.rtt_ms for e in recent_events]

        return {
            'time_window_hours': time_window_hours,
            'total_syncs': len(recent_events),
            'offset': {
                'mean': statistics.mean(offsets),
                'median': statistics.median(offsets),
                'std_dev': statistics.stdev(offsets) if len(offsets) > 1 else 0,
                'min': min(offsets),
                'max': max(offsets)
            },
            'rtt': {
                'mean': statistics.mean(rtts),
                'median': statistics.median(rtts),
                'p95': sorted(rtts)[int(0.95 * len(rtts))],
                'p99': sorted(rtts)[int(0.99 * len(rtts))],
                'min': min(rtts),
                'max': max(rtts)
            },
            'accuracy_distribution': self._count_by_accuracy(recent_events)
        }

    def _count_by_accuracy(self, events: List[ClockSyncEvent]) -> Dict[str, int]:
        """Count events by accuracy level"""
        counts = {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0}
        for event in events:
            counts[event.accuracy] += 1
        return counts

    def _alert_high_rtt(self, event: ClockSyncEvent):
        """Alert when RTT exceeds threshold"""
        print(f"ALERT: High RTT detected - {event.rtt_ms:.2f}ms (threshold: {self.alert_threshold_ms}ms)")
        # TODO: Send to alerting system (PagerDuty, Slack, etc.)

    def _alert_clock_jump(self, event: ClockSyncEvent, jump_ms: float):
        """Alert when clock offset changes dramatically"""
        print(f"ALERT: Clock jump detected - {jump_ms:.2f}ms change in offset")
        # TODO: Send to alerting system
```

### 6.2 Grafana Dashboard Queries

```sql
-- Clock sync RTT over time
SELECT
  time_bucket('1 minute', created_at) AS time,
  avg(clock_sync_rtt_ms) AS avg_rtt,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY clock_sync_rtt_ms) AS p95_rtt,
  percentile_cont(0.99) WITHIN GROUP (ORDER BY clock_sync_rtt_ms) AS p99_rtt
FROM drift_measurements
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY time
ORDER BY time;

-- Clock offset distribution
SELECT
  clock_offset_ms,
  COUNT(*) AS count
FROM drift_measurements
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY clock_offset_ms
ORDER BY clock_offset_ms;

-- Sync quality distribution
SELECT
  sync_quality,
  COUNT(*) AS count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS percentage
FROM drift_measurements
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY sync_quality;
```

## 7. Best Practices

### 7.1 When to Synchronize

1. **Initial connection**: Always sync when frontend connects to backend
2. **Before each test**: Sync immediately before starting video playback
3. **Periodic refresh**: Re-sync every 5 minutes to handle clock drift
4. **After network disruption**: Re-sync after detecting connection issues

### 7.2 Error Handling

```typescript
class ClockSynchronizer {
  async synchronizeWithRetry(maxRetries: number = 3): Promise<ClockSyncResult> {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const result = await this.synchronize();

        // Verify quality
        if (result.accuracy === 'poor') {
          throw new Error(`Poor sync quality: RTT=${result.rttMs}ms`);
        }

        return result;

      } catch (error) {
        console.warn(`Clock sync attempt ${attempt} failed:`, error);

        if (attempt === maxRetries) {
          throw new Error(`Clock sync failed after ${maxRetries} attempts`);
        }

        // Exponential backoff
        await this.sleep(100 * Math.pow(2, attempt - 1));
      }
    }

    throw new Error('Unreachable');
  }
}
```

### 7.3 Fallback Strategies

```typescript
async getClockOffsetWithFallback(): Promise<number> {
  try {
    // Try full multi-sample sync
    return await this.getClockOffset();

  } catch (error) {
    console.warn('Clock sync failed, using fallback strategies:', error);

    // Fallback 1: Use cached offset if recent (< 10 minutes)
    if (this.currentSync) {
      const ageMs = Date.now() - this.currentSync.timestamp.getTime();
      if (ageMs < 10 * 60 * 1000) {
        console.warn('Using cached clock offset:', this.currentSync.offsetMs);
        return this.currentSync.offsetMs;
      }
    }

    // Fallback 2: Assume zero offset (localhost scenario)
    console.warn('Assuming zero clock offset (localhost)');
    return 0;
  }
}
```

## 8. Future Enhancements

### 8.1 Hardware Timestamping

Use LabJack hardware timestamps to bypass OS scheduling delays:

```python
# Direct hardware timestamp capture
T_hardware = labjack.read_hardware_counter()  # Nanosecond precision
```

### 8.2 IEEE 1588 PTP (Precision Time Protocol)

For sub-microsecond synchronization in multi-device scenarios:

```python
# Use PTP grandmaster clock
ptp_client = PTPClient()
ptp_client.sync_to_grandmaster('192.168.1.1')
T_synced = ptp_client.get_synchronized_time()  # < 1μs accuracy
```

### 8.3 Machine Learning Clock Drift Prediction

Predict clock drift based on system load and temperature:

```python
# Train ML model to predict drift
drift_predictor = ClockDriftPredictor()
drift_predictor.train(historical_data)

# Predict next sync interval
predicted_drift = drift_predictor.predict(current_system_state)
next_sync_time = calculate_optimal_sync_time(predicted_drift)
```

---

**Document Version:** 1.0.0
**Author:** System Architecture Designer
**Approved By:** [Pending Review]
**Next Review Date:** 2025-12-20
