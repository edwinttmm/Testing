# WebSocket Keep-Alive Quick Start Guide

## 🚀 Quick Implementation (Frontend)

### Basic Setup (3 Lines of Code)

```javascript
// 1. Subscribe to detection stream (enables keep-alive)
socket.emit('subscribe_detections', { session_id: sessionId });

// 2. Receive detections
socket.on('detection_event', (data) => {
  console.log('Detection:', data.detection);
});

// 3. Cleanup when done
socket.emit('unsubscribe_detections', { session_id: sessionId });
```

That's it! The backend automatically maintains the connection.

---

## 🔍 Verify Keep-Alive is Working

### Check Connection Confirmation

```javascript
socket.on('detection_subscription_confirmed', (data) => {
  console.log('✅ Keep-alive enabled:', data.keep_alive_enabled);
  console.log('Heartbeat interval:', data.heartbeat_interval_seconds);
  // Expected: { keep_alive_enabled: true, heartbeat_interval_seconds: 5 }
});
```

### Monitor Heartbeats (Optional)

```javascript
socket.on('heartbeat_ping', (data) => {
  console.log('💓 Heartbeat #' + data.count,
              'Stream active:', data.has_detection_stream);
});
```

---

## 🐛 Troubleshooting

### Problem: Connection closes before detections arrive

**Solution**: Subscribe before monitoring starts

```javascript
// ❌ WRONG ORDER
startMonitoring(sessionId);
socket.emit('subscribe_detections', { session_id: sessionId });

// ✅ CORRECT ORDER
socket.emit('subscribe_detections', { session_id: sessionId });
startMonitoring(sessionId);
```

### Problem: No detections received

**Check**: Subscription confirmed?

```javascript
socket.emit('subscribe_detections', { session_id: sessionId });
socket.on('detection_subscription_confirmed', (data) => {
  console.log('✅ Subscribed to:', data.room); // Should be test_session_{id}
});
```

### Problem: Connection keeps dropping

**Check**: WebSocket transport used?

```javascript
const socket = io(serverUrl, {
  transports: ['websocket'],  // Force WebSocket (not polling)
  reconnection: true,
  reconnectionDelay: 1000
});
```

---

## 📊 Server-Side Verification

### Check Active Streams

```bash
# Backend logs should show:
🔌 Detection stream opened: session-abc123 (sid: xyz789) - Keep-alive enabled
🔌 KEEP-ALIVE: Heartbeat #1 sent to xyz789 (detection stream: session-abc123)
```

### Monitor Detection Delivery

```bash
# Each detection increments counter:
Emitted detection event to room test_session_abc123
```

### Verify Cleanup

```bash
# When unsubscribe or disconnect:
🔌 Detection stream closed: session-abc123 (sid: xyz789) - Detections received: 42
```

---

## 🔧 Configuration Options

### Adjust Heartbeat Response (Optional)

```javascript
// Respond to heartbeats (optional, for latency monitoring)
socket.on('heartbeat_ping', (data) => {
  socket.emit('heartbeat_pong', {
    timestamp: data.timestamp,
    client_time: Date.now()
  });
});
```

### Handle Connection Loss

```javascript
socket.on('disconnect', (reason) => {
  console.warn('Connection lost:', reason);
  if (reason === 'io server disconnect') {
    // Server initiated disconnect (cleanup)
    console.log('Server closed connection');
  } else {
    // Network issue, will auto-reconnect
    socket.connect();
  }
});
```

---

## ✅ Best Practices

1. **Always subscribe before starting monitoring**
   ```javascript
   await subscribeToDetections(sessionId);
   await startMonitoring(sessionId);
   ```

2. **Always unsubscribe when done**
   ```javascript
   socket.emit('unsubscribe_detections', { session_id: sessionId });
   ```

3. **Use room-based subscriptions**
   ```javascript
   // Join session room first
   socket.emit('join_session', { session_id: sessionId });
   // Then subscribe to detections
   socket.emit('subscribe_detections', { session_id: sessionId });
   ```

4. **Handle reconnection**
   ```javascript
   socket.on('reconnect', () => {
     // Re-subscribe after reconnect
     socket.emit('subscribe_detections', { session_id: sessionId });
   });
   ```

---

## 📈 Performance Expectations

- **Heartbeat Frequency**: Every 5 seconds during active streaming
- **Overhead**: ~20 bytes/second per connection
- **Timeout Tolerance**: 3 missed heartbeats (15 seconds)
- **Detection Latency**: < 100ms from hardware to frontend

---

## 🎯 Complete Example

```javascript
// Complete detection streaming setup with keep-alive

const socket = io('http://localhost:8000', {
  transports: ['websocket'],
  reconnection: true
});

async function startDetectionStream(sessionId) {
  // 1. Join session room
  socket.emit('join_session', { session_id: sessionId });

  // 2. Subscribe to detections (enables keep-alive)
  socket.emit('subscribe_detections', { session_id: sessionId });

  // 3. Confirm subscription
  socket.once('detection_subscription_confirmed', (data) => {
    console.log('✅ Stream opened:', data.session_id);
    console.log('Keep-alive enabled:', data.keep_alive_enabled);
  });

  // 4. Handle detections
  socket.on('detection_event', (data) => {
    console.log('Detection:', data.detection.class,
                'Confidence:', data.detection.confidence);
  });

  // 5. Monitor heartbeats (optional)
  socket.on('heartbeat_ping', (data) => {
    console.log('💓 Connection alive #' + data.count);
  });

  // 6. Start monitoring on hardware
  await fetch(`/api/sessions/${sessionId}/start`, { method: 'POST' });
}

async function stopDetectionStream(sessionId) {
  // 1. Stop monitoring on hardware
  await fetch(`/api/sessions/${sessionId}/stop`, { method: 'POST' });

  // 2. Unsubscribe from detections
  socket.emit('unsubscribe_detections', { session_id: sessionId });

  // 3. Confirm cleanup
  socket.once('detection_unsubscription_confirmed', (data) => {
    console.log('✅ Stream closed:', data.session_id);
  });

  // 4. Leave session room
  socket.emit('leave_session', { session_id: sessionId });
}

// Usage
await startDetectionStream('session-abc-123');
// ... wait for monitoring to complete ...
await stopDetectionStream('session-abc-123');
```

---

## 🆘 Support

**Issue**: Connection closes before detections delivered
**Fix**: Ensure `subscribe_detections` called before `startMonitoring`

**Issue**: No heartbeats received
**Fix**: Check server logs for `KEEP-ALIVE: Heartbeat started`

**Issue**: Detections not arriving
**Fix**: Verify subscription confirmed with `detection_subscription_confirmed`

**Issue**: Stream not cleaning up
**Fix**: Call `unsubscribe_detections` explicitly before disconnect

---

## 📚 Related Documentation

- [Full Implementation Guide](./websocket-keep-alive-implementation.md)
- [WebSocket Enhanced Features](./websocket-enhanced.md)
- [Real-time Detection Streaming](./detection-streaming.md)

---

## 🔄 Version History

- **v1.0** (2025-01-17): Initial keep-alive implementation
  - 5-second heartbeat interval
  - Active stream tracking
  - Detection counter monitoring
  - Graceful cleanup

---

**Last Updated**: 2025-01-17
**Author**: Backend API Developer
