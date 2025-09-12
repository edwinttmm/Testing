# WebSocket Integration Fixes - Implementation Guide

## Critical Fixes Required

### Fix 1: Frontend URL Configuration Issue

**Problem**: Frontend connects to wrong port (`ws://localhost:8001` vs server `localhost:8000`)

**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/LabJackStatusPanel.tsx`
**Line 186**: 
```typescript
const wsUrl = process.env.REACT_APP_WS_URL?.replace('http', 'ws') || 'ws://localhost:8001';
```

**Fix**:
```typescript
const wsUrl = process.env.REACT_APP_WS_URL?.replace('http', 'ws') || 'ws://localhost:8000';
```

### Fix 2: React useEffect Dependencies Creating Connection Loops

**Problem**: Every status change triggers new WebSocket connections

**Current Code** (Line 244):
```typescript
}, [status?.streaming, status?.connected, autoReconnect, onDataReceived]);
```

**Fix**:
```typescript
// Only create connection when BOTH streaming AND connected are true
useEffect(() => {
  if (status?.streaming && status?.connected && !wsConnection) {
    const wsUrl = process.env.REACT_APP_WS_URL?.replace('http', 'ws') || 'ws://localhost:8000';
    const ws = new WebSocket(`${wsUrl}/ws/labjack/stream`);
    
    ws.onopen = () => {
      console.log('LabJack WebSocket connected');
      setWsConnection(ws);
    };
    
    // ... rest of WebSocket setup
    
    return () => {
      ws.close();
      setWsConnection(null);
    };
  } else if (!status?.streaming || !status?.connected) {
    // Clean up existing connection if conditions not met
    if (wsConnection) {
      wsConnection.close();
      setWsConnection(null);
    }
  }
}, [status?.streaming && status?.connected, wsConnection]);
```

### Fix 3: Server-Side Concurrent Message Sending

**Problem**: Two async tasks sending to same WebSocket cause conflicts

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/main.py`
**Lines 301-336**: Concurrent periodic updates and message handling

**Fix**:
```python
@app.websocket("/ws/labjack/stream")
async def labjack_websocket_stream(websocket: WebSocket):
    import asyncio
    import json
    from datetime import datetime
    
    connection_id = f"labjack-{datetime.now().timestamp()}"
    logger.info(f"LabJack WebSocket connection attempt: {connection_id}")
    
    try:
        await websocket.accept()
        logger.info(f"LabJack WebSocket client connected: {connection_id}")
        
        # Get services
        from services.labjack_service import get_labjack_service
        service = get_labjack_service()
        
        # Connection state tracking
        is_connected = True
        last_heartbeat = datetime.now()
        
        # Send initial status
        status = service.get_status()
        initial_message = {
            "type": "initial_status",
            "payload": {
                "connected": status.connected,
                "streaming": status.streaming,
                "mode": status.mode.value,
                "sample_rate": 33,
                "channels": status.channels,
                "voltage_threshold": status.voltage_threshold,
                "connection_id": connection_id
            },
            "timestamp": datetime.now().timestamp()
        }
        
        await websocket.send_text(json.dumps(initial_message))
        logger.info(f"Initial status sent to {connection_id}")
        
        # Single unified message loop
        while is_connected:
            try:
                # Check for incoming messages with short timeout
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                    message = json.loads(data)
                    
                    # Handle client messages
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "connection_id": connection_id,
                            "timestamp": datetime.now().timestamp()
                        }))
                        last_heartbeat = datetime.now()
                        
                except asyncio.TimeoutError:
                    # No message received, continue with periodic updates
                    pass
                
                # Send periodic updates based on streaming status
                current_status = service.get_status()
                now = datetime.now()
                
                if current_status.streaming:
                    # Send streaming data every 33ms (30 Hz)
                    update_message = {
                        "type": "streaming_data",
                        "payload": {
                            "connected": current_status.connected,
                            "streaming": current_status.streaming,
                            "voltage_data": [1.23, 2.45],  # Replace with actual data
                            "timestamp": now.timestamp()
                        }
                    }
                    await websocket.send_text(json.dumps(update_message))
                    await asyncio.sleep(0.033)  # 33ms
                else:
                    # Send status ping every 1 second when not streaming
                    ping_message = {
                        "type": "status_ping",
                        "payload": {
                            "connected": current_status.connected,
                            "streaming": current_status.streaming
                        },
                        "timestamp": now.timestamp()
                    }
                    await websocket.send_text(json.dumps(ping_message))
                    await asyncio.sleep(1.0)
                
                # Check connection health (heartbeat timeout)
                if (now - last_heartbeat).total_seconds() > 30:
                    logger.warning(f"WebSocket {connection_id} heartbeat timeout")
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket {connection_id} disconnected by client")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop for {connection_id}: {e}")
                break
                
    except Exception as e:
        logger.error(f"LabJack WebSocket error for {connection_id}: {e}")
    finally:
        is_connected = False
        logger.info(f"LabJack WebSocket connection {connection_id} closed")
```

### Fix 4: Connection State Management

**Add proper connection state tracking to prevent multiple connections:**

**Frontend Addition**:
```typescript
// Add connection state tracking
const [connectionState, setConnectionState] = useState<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');

useEffect(() => {
  if (status?.streaming && status?.connected && connectionState === 'disconnected') {
    setConnectionState('connecting');
    const wsUrl = process.env.REACT_APP_WS_URL?.replace('http', 'ws') || 'ws://localhost:8000';
    const ws = new WebSocket(`${wsUrl}/ws/labjack/stream`);
    
    ws.onopen = () => {
      console.log('LabJack WebSocket connected');
      setWsConnection(ws);
      setConnectionState('connected');
    };
    
    ws.onclose = () => {
      console.log('LabJack WebSocket disconnected');
      setWsConnection(null);
      setConnectionState('disconnected');
    };
    
    ws.onerror = (error) => {
      console.error('LabJack WebSocket error:', error);
      setError('WebSocket connection error');
      setConnectionState('error');
    };
    
    // ... message handling
    
    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
      setWsConnection(null);
      setConnectionState('disconnected');
    };
  }
}, [status?.streaming && status?.connected, connectionState]);
```

### Fix 5: Environment Variable Configuration

**Create/Update `.env` file for frontend**:
```bash
# Frontend .env file
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_API_URL=http://localhost:8000
```

## Implementation Priority

1. **High Priority** - Fix URL configuration (Fix 1)
2. **High Priority** - Fix useEffect dependencies (Fix 2)  
3. **Medium Priority** - Server-side message loop (Fix 3)
4. **Medium Priority** - Connection state management (Fix 4)
5. **Low Priority** - Environment configuration (Fix 5)

## Testing Strategy

1. **Test Fix 1**: Change frontend URL and verify connections attempt correct port
2. **Test Fix 2**: Monitor for multiple concurrent WebSocket connections
3. **Test Fix 3**: Check server logs for message sending conflicts
4. **Test Fix 4**: Verify proper connection lifecycle management
5. **Integration Test**: Full real-time data streaming functionality

## Expected Results After Fixes

- Single, stable WebSocket connection between frontend and backend
- Proper connection lifecycle (connect → stream → disconnect)
- No more rapid reconnection attempts
- Successful real-time LabJack data streaming
- Clean connection termination without resource leaks

These fixes address the root cause of the WebSocket integration failure and establish robust real-time communication infrastructure.