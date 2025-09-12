# WebSocket Real-Time Communication Flow Analysis

## Overview
This document provides comprehensive analysis of WebSocket communication patterns, real-time data flows, connection management, and event propagation in the AI Model Validation Platform.

## WebSocket Architecture Overview

```
┌─────────────────┐    WebSocket    ┌──────────────────┐
│  React Frontend │ ◄─────────────► │  FastAPI Backend │
│   (Port 3000)   │   Socket.IO     │   (Port 8001)    │
└─────────────────┘                 └──────────────────┘
         │                                     │
         │                                     │
    ┌────▼────┐                          ┌────▼────┐
    │WebSocket│                          │Socket.IO│
    │ Client  │                          │ Server  │
    │Manager  │                          │ Manager │
    └─────────┘                          └─────────┘
         │                                     │
    ┌────▼────┐                          ┌────▼────┐
    │Component│                          │ Service │
    │Event Bus│                          │ Layer   │
    └─────────┘                          └─────────┘
```

## WebSocket Server Implementation

### 1. Socket.IO Server Setup

#### FastAPI Socket.IO Integration
```python
# socketio_server.py - Backend WebSocket server
import socketio
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Create Socket.IO server with CORS support
sio = socketio.AsyncServer(
    cors_allowed_origins=settings.cors_origins,
    async_mode='asgi',
    logger=True,
    engineio_logger=True
)

class WebSocketManager:
    def __init__(self):
        self.active_connections = {}
        self.session_rooms = {}
        self.connection_stats = {
            'total_connections': 0,
            'active_sessions': 0,
            'events_sent': 0
        }
    
    async def connect_client(self, sid: str, environ: dict):
        """Handle new client connection"""
        self.active_connections[sid] = {
            'connected_at': time.time(),
            'session_id': None,
            'user_agent': environ.get('HTTP_USER_AGENT', 'unknown')
        }
        self.connection_stats['total_connections'] += 1
        
        await sio.emit('connection_established', {
            'sid': sid,
            'server_time': time.time()
        }, room=sid)
    
    async def disconnect_client(self, sid: str):
        """Handle client disconnection"""
        if sid in self.active_connections:
            session_id = self.active_connections[sid].get('session_id')
            if session_id:
                await self.leave_session(sid, session_id)
            del self.active_connections[sid]
    
    async def join_session(self, sid: str, session_id: str):
        """Add client to test session room"""
        room_name = f"session_{session_id}"
        await sio.enter_room(sid, room_name)
        
        # Track session membership
        if session_id not in self.session_rooms:
            self.session_rooms[session_id] = set()
        self.session_rooms[session_id].add(sid)
        
        # Update client info
        if sid in self.active_connections:
            self.active_connections[sid]['session_id'] = session_id
        
        await sio.emit('session_joined', {
            'session_id': session_id,
            'room_size': len(self.session_rooms[session_id])
        }, room=sid)

websocket_manager = WebSocketManager()
```

### 2. Event Handlers

#### Core WebSocket Events
```python
@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    logger.info(f"Client {sid} connecting from {environ.get('HTTP_ORIGIN', 'unknown')}")
    
    try:
        await websocket_manager.connect_client(sid, environ)
        return True  # Accept connection
    except Exception as e:
        logger.error(f"Connection error for {sid}: {e}")
        return False  # Reject connection

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client {sid} disconnected")
    await websocket_manager.disconnect_client(sid)

@sio.event
async def join_test_session(sid, data):
    """Join a test session for real-time updates"""
    try:
        session_id = data.get('session_id')
        if not session_id:
            await sio.emit('error', {'message': 'session_id required'}, room=sid)
            return
        
        # Validate session exists
        session = await get_test_session(session_id)
        if not session:
            await sio.emit('error', {'message': 'Session not found'}, room=sid)
            return
            
        await websocket_manager.join_session(sid, session_id)
        
        # Send current session state
        await sio.emit('session_state', {
            'session': serialize_session(session),
            'status': session.status
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Error joining session {session_id}: {e}")
        await sio.emit('error', {'message': 'Failed to join session'}, room=sid)

@sio.event
async def leave_test_session(sid, data):
    """Leave test session room"""
    session_id = data.get('session_id')
    if session_id:
        await websocket_manager.leave_session(sid, session_id)
```

### 3. Real-Time Event Broadcasting

#### Detection Event Broadcasting
```python
class DetectionEventBroadcaster:
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
        
    async def broadcast_detection_event(self, session_id: str, detection_event: DetectionEvent):
        """Broadcast detection event to all session clients"""
        room_name = f"session_{session_id}"
        
        event_data = {
            'event_id': detection_event.id,
            'timestamp': detection_event.timestamp,
            'latency_ms': detection_event.latency_ms,
            'labjack_timestamp': detection_event.labjack_timestamp,
            'voltage_level': detection_event.voltage_level,
            'validation_result': detection_event.validation_result,
            'frame_number': detection_event.frame_number,
            'detection_confidence': detection_event.confidence
        }
        
        await sio.emit('detection_event', event_data, room=room_name)
        
        # Update statistics
        self.websocket_manager.connection_stats['events_sent'] += 1
        
        # Log for monitoring
        logger.info(f"Broadcasted detection event {detection_event.id} to session {session_id}")

    async def broadcast_test_status(self, session_id: str, status: str, details: dict = None):
        """Broadcast test status change"""
        room_name = f"session_{session_id}"
        
        status_data = {
            'status': status,
            'timestamp': time.time(),
            'details': details or {}
        }
        
        await sio.emit('test_status_update', status_data, room=room_name)
        
    async def broadcast_error(self, session_id: str, error: Exception):
        """Broadcast error to session clients"""
        room_name = f"session_{session_id}"
        
        error_data = {
            'error_type': type(error).__name__,
            'message': str(error),
            'timestamp': time.time(),
            'recoverable': hasattr(error, 'recoverable') and error.recoverable
        }
        
        await sio.emit('test_error', error_data, room=room_name)

detection_broadcaster = DetectionEventBroadcaster(websocket_manager)
```

## Frontend WebSocket Client

### 1. WebSocket Hook Implementation

#### Connection Management
```typescript
// hooks/useWebSocket.ts - Frontend WebSocket client
interface UseWebSocketOptions {
  url?: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  autoConnect?: boolean;
  requireBackendAvailable?: boolean;
}

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [backendAvailable, setBackendAvailable] = useState(false);
  const socketRef = useRef<Socket | null>(null);
  const reconnectCountRef = useRef(0);
  const listenersRef = useRef<Map<string, Set<(data: unknown) => void>>>(new Map());
  
  // Configuration loading
  const [socketConfig, setSocketConfig] = useState(() => {
    if (isConfigInitialized()) {
      return getServiceConfig('socketio');
    }
    return { url: '', retryAttempts: 5, retryDelay: 1000, timeout: 20000 };
  });
  
  const connect = useCallback(() => {
    if (!url || socketRef.current?.connected) return;
    
    try {
      const socket = io(url, {
        transports: ['websocket'],
        timeout: socketConfig.timeout || 20000,
        forceNew: false,
        reconnection: false, // Manual reconnection
        withCredentials: false
      });
      
      socketRef.current = socket;
      
      // Connection event handlers
      socket.on('connect', () => {
        setIsConnected(true);
        setError(null);
        reconnectCountRef.current = 0;
        logger.debug('✅ WebSocket connected successfully to', url);
        onConnect?.();
      });
      
      socket.on('disconnect', (reason) => {
        setIsConnected(false);
        logger.warn(`🔌 WebSocket disconnected: ${reason}`);
        onDisconnect?.();
        
        // Auto-reconnect for certain reasons
        if (reason === 'io server disconnect' || reason === 'transport close') {
          scheduleReconnect();
        }
      });
      
      socket.on('connect_error', (err) => {
        const error = new Error(`WebSocket connection error: ${err.message}`);
        setError(error);
        onError?.(error);
        scheduleReconnect();
      });
      
      // Re-register existing listeners
      Array.from(listenersRef.current.entries()).forEach(([event, callbacks]) => {
        callbacks.forEach(callback => {
          socket.on(event, callback);
        });
      });
      
      socket.connect();
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown WebSocket error');
      setError(error);
      onError?.(error);
    }
  }, [url, onConnect, onDisconnect, onError, socketConfig.timeout]);
  
  return {
    socket: socketRef.current,
    isConnected,
    error,
    connect,
    disconnect,
    emit,
    on,
    backendAvailable
  };
};
```

### 2. Event Subscription Patterns

#### Test Session Event Handling
```typescript
// Component using WebSocket for real-time updates
export const EnhancedTestExecution: React.FC<{ sessionId: string }> = ({ sessionId }) => {
  const [detectionEvents, setDetectionEvents] = useState<DetectionEvent[]>([]);
  const [testStatus, setTestStatus] = useState<TestStatus>('idle');
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  
  const { socket, isConnected, connect, disconnect, on } = useWebSocket({
    url: getServiceConfig('socketio').url,
    onConnect: () => setConnectionStatus('connected'),
    onDisconnect: () => setConnectionStatus('disconnected'),
    onError: (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    }
  });
  
  // Join test session on connection
  useEffect(() => {
    if (socket && isConnected && sessionId) {
      socket.emit('join_test_session', { session_id: sessionId });
    }
  }, [socket, isConnected, sessionId]);
  
  // Subscribe to detection events
  useEffect(() => {
    if (!socket || !isConnected) return;
    
    const unsubscribeDetection = on('detection_event', (data: DetectionEvent) => {
      setDetectionEvents(prev => [...prev, data]);
      
      // Trigger UI animations or notifications
      if (data.validation_result === 'PASS') {
        showSuccessNotification('Detection validated successfully');
      } else if (data.validation_result === 'FAIL') {
        showErrorNotification('Detection validation failed');
      }
    });
    
    const unsubscribeStatus = on('test_status_update', (data: TestStatusUpdate) => {
      setTestStatus(data.status);
      
      // Handle status-specific logic
      if (data.status === 'completed') {
        showCompletionModal(data.details);
      }
    });
    
    const unsubscribeError = on('test_error', (data: TestError) => {
      showErrorModal({
        title: 'Test Error',
        message: data.message,
        recoverable: data.recoverable
      });
    });
    
    // Cleanup subscriptions
    return () => {
      unsubscribeDetection();
      unsubscribeStatus();
      unsubscribeError();
    };
  }, [socket, isConnected, on]);
  
  // Leave session on unmount
  useEffect(() => {
    return () => {
      if (socket && sessionId) {
        socket.emit('leave_test_session', { session_id: sessionId });
      }
    };
  }, [socket, sessionId]);
};
```

### 3. Connection Health Monitoring

#### Connection Status Component
```typescript
// Component for monitoring WebSocket health
export const WebSocketConnectionStatus: React.FC = () => {
  const { isConnected, error, backendAvailable } = useWebSocket();
  const [connectionQuality, setConnectionQuality] = useState<'excellent' | 'good' | 'poor' | 'offline'>('offline');
  const [latency, setLatency] = useState<number | null>(null);
  const [lastHeartbeat, setLastHeartbeat] = useState<number | null>(null);
  
  // Ping-pong for latency measurement
  useEffect(() => {
    if (!isConnected) return;
    
    const interval = setInterval(() => {
      const startTime = performance.now();
      socket.emit('ping', { timestamp: startTime });
      
      const handlePong = (data: { timestamp: number }) => {
        const endTime = performance.now();
        const roundTripTime = endTime - data.timestamp;
        setLatency(roundTripTime);
        setLastHeartbeat(Date.now());
        
        // Determine connection quality
        if (roundTripTime < 50) {
          setConnectionQuality('excellent');
        } else if (roundTripTime < 100) {
          setConnectionQuality('good');
        } else {
          setConnectionQuality('poor');
        }
      };
      
      socket.once('pong', handlePong);
    }, 5000); // Ping every 5 seconds
    
    return () => clearInterval(interval);
  }, [isConnected]);
  
  const getStatusColor = () => {
    if (!isConnected) return 'red';
    switch (connectionQuality) {
      case 'excellent': return 'green';
      case 'good': return 'yellow';
      case 'poor': return 'orange';
      default: return 'red';
    }
  };
  
  return (
    <div className="websocket-status">
      <div 
        className={`status-indicator ${getStatusColor()}`}
        title={`WebSocket: ${isConnected ? 'Connected' : 'Disconnected'}`}
      />
      <span className="status-text">
        {isConnected ? `Connected (${latency?.toFixed(0)}ms)` : 'Offline'}
      </span>
      {error && (
        <div className="error-message" title={error.message}>
          ⚠️ Connection Error
        </div>
      )}
    </div>
  );
};
```

## Real-Time Data Flow Patterns

### 1. Detection Event Flow

#### End-to-End Detection Flow
```
1. LabJack Hardware → Voltage Reading
2. Backend Service → Process Signal
3. Validation Logic → Validate Detection
4. Database → Store Event
5. WebSocket → Broadcast to Clients
6. Frontend → Update UI in Real-Time
```

#### Detailed Flow Implementation
```python
# Backend: Real-time detection processing
async def process_detection_event(session_id: str, voltage_reading: float, timestamp: float):
    """Process detection event and broadcast in real-time"""
    try:
        # Validate detection
        is_valid_detection = voltage_reading > DETECTION_THRESHOLD
        
        # Create detection event
        detection_event = DetectionEvent(
            id=str(uuid.uuid4()),
            test_session_id=session_id,
            timestamp=timestamp,
            voltage_level=voltage_reading,
            validation_result='PASS' if is_valid_detection else 'FAIL',
            latency_ms=calculate_latency(timestamp)
        )
        
        # Store in database
        db.add(detection_event)
        await db.commit()
        
        # Broadcast immediately (don't wait for DB commit)
        await detection_broadcaster.broadcast_detection_event(session_id, detection_event)
        
        # Update session statistics
        await update_session_stats(session_id, detection_event)
        
    except Exception as e:
        logger.error(f"Error processing detection event: {e}")
        await detection_broadcaster.broadcast_error(session_id, e)
```

### 2. Session State Synchronization

#### Multi-Client State Sync
```typescript
// Frontend: Synchronized session state across multiple clients
export const useSessionSync = (sessionId: string) => {
  const [sessionState, setSessionState] = useState<TestSessionState | null>(null);
  const [participants, setParticipants] = useState<string[]>([]);
  const { socket, isConnected, on } = useWebSocket();
  
  // Join session and sync state
  useEffect(() => {
    if (socket && isConnected && sessionId) {
      socket.emit('join_test_session', { session_id: sessionId });
      
      // Request current state
      socket.emit('request_session_state', { session_id: sessionId });
    }
  }, [socket, isConnected, sessionId]);
  
  // Listen for state updates
  useEffect(() => {
    if (!socket || !isConnected) return;
    
    const unsubscribeState = on('session_state', (data: SessionStateUpdate) => {
      setSessionState(data.session);
      setParticipants(data.participants || []);
    });
    
    const unsubscribeParticipant = on('participant_joined', (data: ParticipantUpdate) => {
      setParticipants(prev => [...prev, data.participant_id]);
      showNotification(`${data.participant_name} joined the session`);
    });
    
    const unsubscribeParticipantLeft = on('participant_left', (data: ParticipantUpdate) => {
      setParticipants(prev => prev.filter(p => p !== data.participant_id));
      showNotification(`${data.participant_name} left the session`);
    });
    
    return () => {
      unsubscribeState();
      unsubscribeParticipant();
      unsubscribeParticipantLeft();
    };
  }, [socket, isConnected, on]);
  
  return { sessionState, participants };
};
```

## Error Handling and Recovery

### 1. Connection Recovery Patterns

#### Automatic Reconnection Strategy
```typescript
// Advanced reconnection with exponential backoff
export const useWebSocketWithRecovery = (url: string) => {
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const maxReconnectAttempts = 10;
  const baseDelay = 1000;
  
  const reconnect = useCallback(async () => {
    if (reconnectAttempts >= maxReconnectAttempts) {
      setConnectionState('error');
      return;
    }
    
    setConnectionState('connecting');
    
    // Exponential backoff with jitter
    const delay = Math.min(
      baseDelay * Math.pow(2, reconnectAttempts) + Math.random() * 1000,
      30000
    );
    
    await new Promise(resolve => setTimeout(resolve, delay));
    
    try {
      // Attempt to reconnect
      await connect();
      setReconnectAttempts(0);
      setConnectionState('connected');
    } catch (error) {
      setReconnectAttempts(prev => prev + 1);
      // Will retry automatically
      reconnect();
    }
  }, [reconnectAttempts, connect]);
  
  // Auto-reconnect on connection loss
  useEffect(() => {
    if (connectionState === 'disconnected' && reconnectAttempts < maxReconnectAttempts) {
      reconnect();
    }
  }, [connectionState, reconnectAttempts, reconnect]);
};
```

### 2. Message Reliability

#### Message Acknowledgment Pattern
```python
# Backend: Reliable message delivery
class ReliableMessageDelivery:
    def __init__(self):
        self.pending_messages = {}
        self.message_timeout = 30  # seconds
        
    async def send_with_acknowledgment(self, room: str, event: str, data: dict, message_id: str = None):
        """Send message with delivery confirmation"""
        if not message_id:
            message_id = str(uuid.uuid4())
            
        message_data = {
            **data,
            'message_id': message_id,
            'timestamp': time.time()
        }
        
        # Store pending message
        self.pending_messages[message_id] = {
            'room': room,
            'event': event,
            'data': message_data,
            'sent_at': time.time(),
            'retries': 0
        }
        
        # Send message
        await sio.emit(event, message_data, room=room)
        
        # Set timeout for acknowledgment
        asyncio.create_task(self._check_acknowledgment(message_id))
        
    async def _check_acknowledgment(self, message_id: str):
        """Check if message was acknowledged"""
        await asyncio.sleep(self.message_timeout)
        
        if message_id in self.pending_messages:
            # Message not acknowledged, retry
            pending = self.pending_messages[message_id]
            if pending['retries'] < 3:
                pending['retries'] += 1
                await sio.emit(pending['event'], pending['data'], room=pending['room'])
                asyncio.create_task(self._check_acknowledgment(message_id))
            else:
                # Give up after 3 retries
                del self.pending_messages[message_id]
                logger.warning(f"Message {message_id} delivery failed after 3 retries")

# Frontend: Message acknowledgment
const handleMessage = useCallback((data: MessageWithId) => {
  // Process message
  processMessage(data);
  
  // Send acknowledgment
  socket.emit('message_ack', { message_id: data.message_id });
}, [socket]);
```

## Performance Optimization

### 1. Message Batching

#### Efficient Event Batching
```python
# Backend: Batch multiple events for efficiency
class EventBatcher:
    def __init__(self, batch_size: int = 10, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.event_batches = {}
        
    async def add_event(self, room: str, event_type: str, data: dict):
        """Add event to batch for room"""
        if room not in self.event_batches:
            self.event_batches[room] = []
            
        self.event_batches[room].append({
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        })
        
        # Check if batch should be sent
        if len(self.event_batches[room]) >= self.batch_size:
            await self._send_batch(room)
        else:
            # Schedule batch send after timeout
            asyncio.create_task(self._delayed_send(room))
            
    async def _send_batch(self, room: str):
        """Send batched events to room"""
        if room not in self.event_batches or not self.event_batches[room]:
            return
            
        events = self.event_batches[room]
        self.event_batches[room] = []
        
        await sio.emit('batched_events', {
            'events': events,
            'batch_size': len(events),
            'timestamp': time.time()
        }, room=room)
        
    async def _delayed_send(self, room: str):
        """Send batch after timeout"""
        await asyncio.sleep(self.batch_timeout)
        await self._send_batch(room)

event_batcher = EventBatcher()
```

### 2. Connection Pool Management

#### Connection Pool Optimization
```python
# Backend: Efficient connection management
class WebSocketConnectionPool:
    def __init__(self, max_connections: int = 1000):
        self.max_connections = max_connections
        self.connections = {}
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'rejected_connections': 0
        }
        
    async def add_connection(self, sid: str, connection_info: dict) -> bool:
        """Add connection to pool with limits"""
        if len(self.connections) >= self.max_connections:
            self.connection_stats['rejected_connections'] += 1
            logger.warning(f"Connection limit reached, rejecting {sid}")
            return False
            
        self.connections[sid] = {
            **connection_info,
            'connected_at': time.time(),
            'last_activity': time.time(),
            'message_count': 0
        }
        
        self.connection_stats['total_connections'] += 1
        self.connection_stats['active_connections'] += 1
        
        return True
        
    async def remove_connection(self, sid: str):
        """Remove connection from pool"""
        if sid in self.connections:
            del self.connections[sid]
            self.connection_stats['active_connections'] -= 1
            
    async def cleanup_idle_connections(self, max_idle_time: float = 3600):
        """Remove idle connections"""
        current_time = time.time()
        idle_connections = []
        
        for sid, conn_info in self.connections.items():
            if current_time - conn_info['last_activity'] > max_idle_time:
                idle_connections.append(sid)
                
        for sid in idle_connections:
            await sio.disconnect(sid)
            await self.remove_connection(sid)
            
        if idle_connections:
            logger.info(f"Cleaned up {len(idle_connections)} idle connections")

connection_pool = WebSocketConnectionPool()
```

## Monitoring and Metrics

### 1. WebSocket Metrics Collection

#### Real-Time Metrics
```python
# Backend: Comprehensive WebSocket metrics
class WebSocketMetrics:
    def __init__(self):
        self.metrics = {
            'connections': {
                'total': 0,
                'active': 0,
                'peak_concurrent': 0
            },
            'messages': {
                'sent': 0,
                'received': 0,
                'failed': 0
            },
            'latency': {
                'min': float('inf'),
                'max': 0,
                'avg': 0,
                'samples': []
            },
            'rooms': {},
            'errors': {
                'connection_errors': 0,
                'message_errors': 0,
                'timeout_errors': 0
            }
        }
        
    def record_connection(self, sid: str):
        """Record new connection"""
        self.metrics['connections']['total'] += 1
        self.metrics['connections']['active'] += 1
        
        if self.metrics['connections']['active'] > self.metrics['connections']['peak_concurrent']:
            self.metrics['connections']['peak_concurrent'] = self.metrics['connections']['active']
            
    def record_disconnection(self, sid: str):
        """Record disconnection"""
        self.metrics['connections']['active'] -= 1
        
    def record_message_sent(self, event: str, room: str = None):
        """Record sent message"""
        self.metrics['messages']['sent'] += 1
        
        if room:
            if room not in self.metrics['rooms']:
                self.metrics['rooms'][room] = {'messages': 0, 'clients': 0}
            self.metrics['rooms'][room]['messages'] += 1
            
    def record_latency(self, latency_ms: float):
        """Record message latency"""
        self.metrics['latency']['min'] = min(self.metrics['latency']['min'], latency_ms)
        self.metrics['latency']['max'] = max(self.metrics['latency']['max'], latency_ms)
        
        # Keep rolling average
        samples = self.metrics['latency']['samples']
        samples.append(latency_ms)
        if len(samples) > 100:  # Keep last 100 samples
            samples.pop(0)
            
        self.metrics['latency']['avg'] = sum(samples) / len(samples)

websocket_metrics = WebSocketMetrics()

# Metrics endpoint
@app.get("/api/websocket/metrics")
async def get_websocket_metrics():
    return {
        "websocket_metrics": websocket_metrics.metrics,
        "timestamp": time.time()
    }
```

### 2. Health Check Integration

#### WebSocket Health Monitoring
```python
# Backend: WebSocket health checks
@app.get("/api/websocket/health")
async def websocket_health_check():
    """Comprehensive WebSocket health check"""
    try:
        # Check server status
        server_healthy = sio.manager is not None
        
        # Check active connections
        active_connections = len(websocket_manager.active_connections)
        connection_healthy = active_connections < 1000  # Threshold
        
        # Check recent errors
        recent_errors = sum(websocket_metrics.metrics['errors'].values())
        error_healthy = recent_errors < 10  # Error threshold
        
        # Overall health
        overall_healthy = server_healthy and connection_healthy and error_healthy
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "websocket_server": "running" if server_healthy else "stopped",
            "active_connections": active_connections,
            "recent_errors": recent_errors,
            "metrics": websocket_metrics.metrics,
            "timestamp": time.time()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }
```

## Future WebSocket Enhancements

### Planned Improvements

1. **Message Queue Integration**
   - Redis Pub/Sub for scalability
   - Message persistence
   - Cross-server communication

2. **Advanced Security**
   - JWT token validation
   - Rate limiting per connection
   - Message encryption

3. **Performance Optimizations**
   - Message compression
   - Binary message support
   - Connection multiplexing

4. **Monitoring Enhancements**
   - Real-time dashboards
   - Alerting on connection issues
   - Performance profiling

5. **High Availability**
   - Load balancer support
   - Failover mechanisms
   - Session persistence