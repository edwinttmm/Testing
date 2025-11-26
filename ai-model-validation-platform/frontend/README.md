# Frontend Timing Implementation

## Overview

Production-grade timing measurement system with sub-millisecond precision for video synchronization testing.

## Features

### 1. High-Precision Video Timing
- **Microsecond Precision**: Uses `performance.now()` for all timestamps
- **Reliable Event Capture**: Monitors `playing` event (not `play`)
- **Complete Lifecycle**: Tracks loading, canplay, playing, pause, ended, error
- **Rich Metadata**: Captures video state, network timing, and browser info

### 2. Clock Synchronization
- **NTP-like Protocol**: Implements ping-pong clock sync with backend
- **Drift Compensation**: Adjusts all timestamps for clock offset
- **Automatic Sync**: Periodic synchronization every 30 seconds
- **Health Monitoring**: Validates sync quality and freshness

### 3. Network Resilience
- **Automatic Reconnection**: Exponential backoff on disconnect
- **Latency Tracking**: Monitors WebSocket RTT
- **Throttle Detection**: Identifies browser tab throttling
- **Visibility Awareness**: Tracks tab visibility state

### 4. Real-time Visualization
- **Drift Monitor**: Shows synchronization status per video
- **Color-coded Severity**: Green (<50ms), Yellow (50-200ms), Red (>200ms)
- **Clock Status**: Displays offset, RTT, accuracy
- **Live Updates**: 100ms refresh rate

## Architecture

```
frontend/src/
├── types/
│   └── timing.types.ts          # TypeScript type definitions
├── services/
│   ├── clockSyncService.ts      # NTP-like clock synchronization
│   ├── timingService.ts         # Video timing capture
│   └── __tests__/               # Unit tests with fake timers
│       ├── clockSyncService.test.ts
│       └── timingService.test.ts
├── components/
│   └── DriftMonitor.tsx         # Real-time drift visualization
└── examples/
    └── timingUsageExample.ts    # Usage examples
```

## Usage

### Initialize Timing Service

```typescript
import { TimingService } from './services/timingService';

const config = {
  syncInterval: 30000,     // Sync every 30 seconds
  maxRTT: 200,            // Reject syncs > 200ms RTT
  syncSamples: 5,         // Average last 5 samples
  wsEndpoint: 'ws://localhost:3000/timing',
};

const timingService = new TimingService(config);
await timingService.initialize();
```

### Register Video Elements

```typescript
const videoElement = document.querySelector('video');
timingService.registerVideo('video-1', videoElement);
```

### Monitor Status

```typescript
// Get clock sync status
const syncStatus = timingService.getClockSyncStatus();
console.log('Offset:', syncStatus.offset, 'ms');
console.log('Healthy:', syncStatus.isHealthy);

// Get WebSocket latency
const latency = timingService.getWebSocketLatency();
console.log('WS Latency:', latency, 'ms');
```

### React Component Integration

```tsx
import { DriftMonitor } from './components/DriftMonitor';

function VideoTestPage() {
  const [timingService] = useState(() => new TimingService(config));
  const [videoIds, setVideoIds] = useState(['video-1', 'video-2']);

  useEffect(() => {
    timingService.initialize();
    return () => timingService.shutdown();
  }, []);

  return (
    <div>
      <video id="video-1" src="/test1.mp4" controls />
      <video id="video-2" src="/test2.mp4" controls />

      <DriftMonitor
        timingService={timingService}
        videoIds={videoIds}
      />
    </div>
  );
}
```

## Timing Data Structure

### High-Precision Timestamp
```typescript
{
  timestamp: 1000.123,          // performance.now() (ms)
  timeOrigin: 1600000000000,    // performance.timeOrigin
  absolute: 1600000001000.123,  // Combined absolute time
  clockOffset: 50.456,          // Offset from server (ms)
  adjusted: 1600000001050.579   // Compensated timestamp
}
```

### Video Timing Event
```typescript
{
  videoId: 'video-1',
  event: 'playing',
  timing: { ... },              // High-precision timestamp
  readyState: 4,                // HAVE_ENOUGH_DATA
  currentTime: 0.0,
  duration: 60.0,
  networkState: 2               // NETWORK_LOADING
}
```

### Video Timing Metadata
```typescript
{
  event: { ... },               // Video timing event
  networkTiming: {
    dnsLookupTime: 5,
    tcpConnectionTime: 10,
    ttfb: 50,
    downloadTime: 100
  },
  wsLatency: 15.234,
  userAgent: 'Mozilla/5.0...',
  tabVisible: true,
  wasThrottled: false
}
```

## Clock Synchronization Protocol

### Request (Client → Server)
```typescript
{
  type: 'clock_sync_request',
  payload: {
    clientTimestamp: 1600000001000.123,
    sequence: 0
  }
}
```

### Response (Server → Client)
```typescript
{
  type: 'clock_sync_response',
  payload: {
    clientTimestamp: 1600000001000.123,  // T1: Client send
    serverTimestamp: 1600000001050.456,  // T2: Server receive
    serverSendTimestamp: 1600000001051.789, // T3: Server send
    sequence: 0
  }
}
```

### Offset Calculation (NTP Algorithm)
```
offset = ((T2 - T1) + (T3 - T4)) / 2
where T4 = client receive time
```

## Testing

### Run Unit Tests
```bash
npm test -- --testPathPattern=timing
```

### Test Coverage
- Clock synchronization with mocked WebSocket
- Video event capture with fake timers
- Timestamp adjustment calculations
- Reconnection logic with exponential backoff
- RTT validation and rejection

## Browser Compatibility

### Required APIs
- ✅ `performance.now()` - All modern browsers
- ✅ `performance.timeOrigin` - Chrome 62+, Firefox 53+, Safari 14.1+
- ✅ `Navigation Timing API` - All modern browsers
- ✅ `WebSocket` - All modern browsers

### Handling Throttling
- Detects tab throttling via timing gaps
- Warns when tab is hidden (visibility API)
- Marks timing data with throttle status

## Performance

### Timing Precision
- **Resolution**: 0.001ms (1 microsecond) via `performance.now()`
- **Accuracy**: ±(RTT/2) typically <5ms
- **Overhead**: <1ms per event capture

### Network Usage
- Clock sync: ~100 bytes every 30 seconds
- Video events: ~500 bytes per event
- WebSocket ping: ~50 bytes every 5 seconds

## Production Considerations

### Error Handling
- ✅ WebSocket disconnection with auto-reconnect
- ✅ High RTT sync rejection (>200ms)
- ✅ Stale sync detection
- ✅ Video element cleanup on unregister

### Security
- Uses secure WebSocket (wss://) in production
- No sensitive data in timing events
- CORS-compliant WebSocket connections

### Monitoring
- Clock sync health checks
- WebSocket latency tracking
- Tab visibility monitoring
- Throttle detection

## Integration Checklist

- [ ] Backend implements clock sync protocol (see backend README)
- [ ] WebSocket endpoint configured correctly
- [ ] Video elements registered before playback
- [ ] DriftMonitor component mounted in UI
- [ ] Cleanup on component unmount
- [ ] Error handling for initialization failures
- [ ] Monitoring alerts for unhealthy sync

## Troubleshooting

### Clock Sync Not Working
1. Check WebSocket connection: `timingService.getClockSyncStatus()`
2. Verify backend implements clock sync protocol
3. Check for network issues (high latency)
4. Look for CORS errors in console

### High Drift Values
1. Check if tab is throttled (hidden)
2. Verify network stability (RTT spikes)
3. Ensure regular sync intervals
4. Check backend clock accuracy

### Missing Timing Events
1. Verify video element is registered
2. Check video `readyState` progression
3. Look for video loading errors
3. Ensure WebSocket is connected

## Future Enhancements

- [ ] Event queue for offline resilience
- [ ] Local storage for sync history
- [ ] Advanced drift prediction
- [ ] Multi-server clock sync
- [ ] Compressed event batching
- [ ] Performance profiling tools

## References

- [Performance API](https://developer.mozilla.org/en-US/docs/Web/API/Performance)
- [Navigation Timing API](https://developer.mozilla.org/en-US/docs/Web/API/Navigation_timing_API)
- [NTP Algorithm](https://en.wikipedia.org/wiki/Network_Time_Protocol)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
