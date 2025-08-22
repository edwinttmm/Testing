# Real-Time Notification System Specifications

**Component:** WebSocket-based Real-time Notification System  
**Integration:** Video Processing Platform  
**Purpose:** Provide instant status updates and progress tracking  

## OVERVIEW

The real-time notification system enables immediate communication between the backend video processing pipeline and frontend clients, delivering instant updates on upload progress, processing status, error conditions, and completion notifications.

## SYSTEM ARCHITECTURE

### 1. Notification Flow Diagram

```
Video Processing Event → Database Trigger → Notification Queue → WebSocket Server → Client
```

### 2. Component Integration

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Video Processor │ → │ Notification     │ → │ WebSocket       │
│                 │    │ Queue System     │    │ Server          │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ↓                       ↓                       ↓
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Database        │    │ Redis/Memory     │    │ Socket.IO       │
│ Triggers        │    │ Queue            │    │ Rooms           │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## NOTIFICATION EVENT SPECIFICATIONS

### 1. Event Type Definitions

```typescript
enum NotificationEventType {
    // Upload Events
    UPLOAD_STARTED = 'upload_started',
    UPLOAD_PROGRESS = 'upload_progress',
    UPLOAD_COMPLETED = 'upload_completed',
    UPLOAD_FAILED = 'upload_failed',
    
    // Processing Events
    PROCESSING_STARTED = 'processing_started',
    PROCESSING_PROGRESS = 'processing_progress',
    PROCESSING_STAGE_CHANGED = 'processing_stage_changed',
    PROCESSING_COMPLETED = 'processing_completed',
    PROCESSING_FAILED = 'processing_failed',
    
    // Ground Truth Events
    GROUND_TRUTH_STARTED = 'ground_truth_started',
    GROUND_TRUTH_PROGRESS = 'ground_truth_progress',
    GROUND_TRUTH_COMPLETED = 'ground_truth_completed',
    GROUND_TRUTH_FAILED = 'ground_truth_failed',
    
    // System Events
    SYSTEM_ALERT = 'system_alert',
    RESOURCE_WARNING = 'resource_warning',
    CONNECTION_STATUS = 'connection_status'
}
```

### 2. Event Payload Structure

```typescript
interface NotificationEvent {
    id: string;
    type: NotificationEventType;
    timestamp: string;
    priority: 1 | 2 | 3 | 4 | 5;  // 1 = highest, 5 = lowest
    
    // Target information
    target: {
        session_id?: string;
        user_id?: string;
        room?: string;
        broadcast?: boolean;
    };
    
    // Event-specific data
    data: {
        video_id?: string;
        project_id?: string;
        stage?: string;
        progress?: {
            percentage: number;
            current_step: number;
            total_steps: number;
            estimated_completion?: string;
        };
        error?: {
            code: string;
            message: string;
            recoverable: boolean;
            retry_count?: number;
        };
        metadata?: Record<string, any>;
    };
    
    // Delivery tracking
    delivery: {
        attempts: number;
        max_attempts: number;
        next_retry?: string;
        expires_at: string;
    };
}
```

## DATABASE INTEGRATION

### 1. Notification Queue Table

```sql
CREATE TABLE realtime_notification_queue (
    id VARCHAR(36) PRIMARY KEY,
    
    -- Event Classification
    event_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    
    -- Target Specification
    session_id VARCHAR(255),
    user_id VARCHAR(36),
    room_name VARCHAR(255),
    broadcast_to_all BOOLEAN DEFAULT FALSE,
    
    -- Event Content
    event_data JSON NOT NULL,
    event_metadata JSON,
    
    -- Processing State
    status ENUM('pending', 'processing', 'sent', 'failed', 'expired') DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    -- Timing Control
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    process_after TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    sent_at TIMESTAMP,
    
    -- Error Handling
    last_error TEXT,
    next_retry_at TIMESTAMP,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Performance Indexes
    INDEX idx_notification_processing (status, priority, process_after),
    INDEX idx_notification_session (session_id, status),
    INDEX idx_notification_expiry (expires_at, status),
    INDEX idx_notification_retry (next_retry_at, status),
    INDEX idx_notification_type (event_type, created_at)
);
```

### 2. Database Triggers for Automatic Notification

```sql
DELIMITER $$

CREATE TRIGGER tr_video_status_notification
    AFTER UPDATE ON videos
    FOR EACH ROW
BEGIN
    DECLARE notification_id VARCHAR(36) DEFAULT UUID();
    DECLARE event_type VARCHAR(50);
    DECLARE priority_level INTEGER DEFAULT 3;
    
    -- Determine event type based on status change
    IF NEW.workflow_state != OLD.workflow_state THEN
        SET event_type = CASE NEW.workflow_state
            WHEN 'uploading' THEN 'upload_started'
            WHEN 'uploaded' THEN 'upload_completed'
            WHEN 'processing' THEN 'processing_started'
            WHEN 'completed' THEN 'processing_completed'
            WHEN 'failed' THEN 'processing_failed'
            ELSE 'status_changed'
        END;
        
        -- Set priority based on event importance
        SET priority_level = CASE NEW.workflow_state
            WHEN 'failed' THEN 1      -- High priority for failures
            WHEN 'completed' THEN 2   -- High priority for completion
            WHEN 'processing' THEN 3  -- Medium priority for processing
            ELSE 4                    -- Normal priority for other changes
        END;
        
        -- Queue notification
        INSERT INTO realtime_notification_queue (
            id, event_type, priority, room_name, event_data, expires_at
        ) VALUES (
            notification_id,
            event_type,
            priority_level,
            CONCAT('video_', NEW.id),
            JSON_OBJECT(
                'video_id', NEW.id,
                'project_id', NEW.project_id,
                'old_status', OLD.workflow_state,
                'new_status', NEW.workflow_state,
                'filename', NEW.filename,
                'updated_at', NEW.updated_at
            ),
            DATE_ADD(NOW(), INTERVAL 1 HOUR)
        );
    END IF;
END$$

CREATE TRIGGER tr_processing_progress_notification
    AFTER UPDATE ON video_processing_status
    FOR EACH ROW
BEGIN
    DECLARE notification_id VARCHAR(36) DEFAULT UUID();
    
    -- Only notify on meaningful progress changes (>5% change or stage change)
    IF (NEW.progress_percentage - OLD.progress_percentage >= 5.0) OR 
       (NEW.current_stage != OLD.current_stage) OR
       (NEW.error_count != OLD.error_count) THEN
        
        INSERT INTO realtime_notification_queue (
            id, event_type, priority, room_name, event_data, expires_at
        ) VALUES (
            notification_id,
            CASE 
                WHEN NEW.error_count > OLD.error_count THEN 'processing_failed'
                WHEN NEW.current_stage != OLD.current_stage THEN 'processing_stage_changed'
                ELSE 'processing_progress'
            END,
            CASE 
                WHEN NEW.error_count > OLD.error_count THEN 1
                WHEN NEW.progress_percentage = 100 THEN 2
                ELSE 3
            END,
            CONCAT('video_', NEW.video_id),
            JSON_OBJECT(
                'video_id', NEW.video_id,
                'stage', NEW.current_stage,
                'progress_percentage', NEW.progress_percentage,
                'processed_frames', NEW.processed_frames,
                'total_frames', NEW.total_frames,
                'error_count', NEW.error_count,
                'last_error', NEW.last_error_message,
                'estimated_completion', NEW.estimated_completion_time
            ),
            DATE_ADD(NOW(), INTERVAL 30 MINUTE)
        );
    END IF;
END$$

DELIMITER ;
```

## WEBSOCKET SERVER IMPLEMENTATION

### 1. Enhanced Socket.IO Server Configuration

```python
import socketio
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
import logging
from sqlalchemy.orm import Session
from database import SessionLocal

logger = logging.getLogger(__name__)

class NotificationServer:
    def __init__(self):
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins="*",  # Configure appropriately for production
            logger=True,
            engineio_logger=True,
            ping_timeout=60,
            ping_interval=25
        )
        
        # Active connections tracking
        self.active_connections: Dict[str, Dict] = {}
        self.room_subscriptions: Dict[str, List[str]] = {}
        
        # Notification processing
        self.processing_notifications = False
        self.notification_batch_size = 100
        self.notification_process_interval = 1.0  # seconds
        
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        @self.sio.event
        async def connect(sid, environ, auth):
            """Handle client connections with authentication"""
            try:
                # Extract user information from auth token
                user_id = self._authenticate_user(auth)
                
                # Store connection info
                self.active_connections[sid] = {
                    'user_id': user_id,
                    'connected_at': datetime.utcnow(),
                    'last_ping': datetime.utcnow(),
                    'subscriptions': []
                }
                
                logger.info(f"Client {sid} connected (user: {user_id})")
                
                # Send connection confirmation
                await self.sio.emit('connection_status', {
                    'status': 'connected',
                    'session_id': sid,
                    'server_time': datetime.utcnow().isoformat()
                }, room=sid)
                
                return True
                
            except Exception as e:
                logger.error(f"Connection failed for {sid}: {e}")
                return False
        
        @self.sio.event
        async def disconnect(sid):
            """Handle client disconnections"""
            if sid in self.active_connections:
                user_id = self.active_connections[sid].get('user_id')
                
                # Clean up subscriptions
                for room in self.active_connections[sid].get('subscriptions', []):
                    if room in self.room_subscriptions:
                        self.room_subscriptions[room].remove(sid)
                        if not self.room_subscriptions[room]:
                            del self.room_subscriptions[room]
                
                del self.active_connections[sid]
                logger.info(f"Client {sid} disconnected (user: {user_id})")
        
        @self.sio.event
        async def subscribe_to_video(sid, data):
            """Subscribe to video-specific notifications"""
            try:
                video_id = data.get('video_id')
                if not video_id:
                    await self.sio.emit('error', {
                        'message': 'video_id required for subscription'
                    }, room=sid)
                    return
                
                room_name = f"video_{video_id}"
                await self.sio.enter_room(sid, room_name)
                
                # Track subscription
                if sid in self.active_connections:
                    self.active_connections[sid]['subscriptions'].append(room_name)
                
                if room_name not in self.room_subscriptions:
                    self.room_subscriptions[room_name] = []
                self.room_subscriptions[room_name].append(sid)
                
                logger.info(f"Client {sid} subscribed to {room_name}")
                
                # Send current video status
                await self._send_current_video_status(sid, video_id)
                
            except Exception as e:
                logger.error(f"Subscription error for {sid}: {e}")
                await self.sio.emit('error', {
                    'message': f'Subscription failed: {str(e)}'
                }, room=sid)
        
        @self.sio.event
        async def subscribe_to_project(sid, data):
            """Subscribe to project-wide notifications"""
            try:
                project_id = data.get('project_id')
                if not project_id:
                    await self.sio.emit('error', {
                        'message': 'project_id required for subscription'
                    }, room=sid)
                    return
                
                room_name = f"project_{project_id}"
                await self.sio.enter_room(sid, room_name)
                
                # Track subscription
                if sid in self.active_connections:
                    self.active_connections[sid]['subscriptions'].append(room_name)
                
                if room_name not in self.room_subscriptions:
                    self.room_subscriptions[room_name] = []
                self.room_subscriptions[room_name].append(sid)
                
                logger.info(f"Client {sid} subscribed to {room_name}")
                
            except Exception as e:
                logger.error(f"Project subscription error for {sid}: {e}")
        
        @self.sio.event
        async def ping(sid):
            """Handle client ping for connection health"""
            if sid in self.active_connections:
                self.active_connections[sid]['last_ping'] = datetime.utcnow()
            await self.sio.emit('pong', {'timestamp': datetime.utcnow().isoformat()}, room=sid)
    
    async def start_notification_processor(self):
        """Start the background notification processor"""
        self.processing_notifications = True
        while self.processing_notifications:
            try:
                await self._process_pending_notifications()
                await asyncio.sleep(self.notification_process_interval)
            except Exception as e:
                logger.error(f"Notification processor error: {e}")
                await asyncio.sleep(5)  # Back off on error
    
    async def _process_pending_notifications(self):
        """Process pending notifications from the database queue"""
        db = SessionLocal()
        try:
            # Get pending notifications ordered by priority and creation time
            notifications = db.execute("""
                SELECT id, event_type, priority, session_id, room_name, 
                       broadcast_to_all, event_data, attempts, max_attempts
                FROM realtime_notification_queue 
                WHERE status = 'pending' 
                AND process_after <= NOW()
                AND expires_at > NOW()
                ORDER BY priority ASC, created_at ASC
                LIMIT %s
            """, (self.notification_batch_size,)).fetchall()
            
            for notification in notifications:
                try:
                    # Mark as processing
                    db.execute("""
                        UPDATE realtime_notification_queue 
                        SET status = 'processing', updated_at = NOW()
                        WHERE id = %s
                    """, (notification.id,))
                    
                    # Send notification
                    success = await self._send_notification(notification)
                    
                    if success:
                        # Mark as sent
                        db.execute("""
                            UPDATE realtime_notification_queue 
                            SET status = 'sent', sent_at = NOW(), updated_at = NOW()
                            WHERE id = %s
                        """, (notification.id,))
                    else:
                        # Handle failure
                        await self._handle_notification_failure(db, notification)
                    
                    db.commit()
                    
                except Exception as e:
                    logger.error(f"Failed to process notification {notification.id}: {e}")
                    db.rollback()
                    
                    # Mark as failed
                    db.execute("""
                        UPDATE realtime_notification_queue 
                        SET status = 'failed', last_error = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (str(e), notification.id))
                    db.commit()
        
        finally:
            db.close()
    
    async def _send_notification(self, notification) -> bool:
        """Send a notification to the appropriate targets"""
        try:
            event_data = json.loads(notification.event_data)
            
            # Determine target
            if notification.broadcast_to_all:
                # Broadcast to all connected clients
                await self.sio.emit(notification.event_type, event_data)
                
            elif notification.session_id:
                # Send to specific session
                await self.sio.emit(notification.event_type, event_data, 
                                  room=notification.session_id)
                
            elif notification.room_name:
                # Send to room
                await self.sio.emit(notification.event_type, event_data, 
                                  room=notification.room_name)
            
            else:
                logger.warning(f"No valid target for notification {notification.id}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send notification {notification.id}: {e}")
            return False
    
    async def _handle_notification_failure(self, db: Session, notification):
        """Handle notification sending failure with retry logic"""
        attempts = notification.attempts + 1
        
        if attempts >= notification.max_attempts:
            # Max attempts reached, mark as failed
            db.execute("""
                UPDATE realtime_notification_queue 
                SET status = 'failed', attempts = %s, updated_at = NOW()
                WHERE id = %s
            """, (attempts, notification.id))
        else:
            # Schedule retry with exponential backoff
            retry_delay = min(300, 2 ** attempts)  # Cap at 5 minutes
            next_retry = datetime.utcnow() + timedelta(seconds=retry_delay)
            
            db.execute("""
                UPDATE realtime_notification_queue 
                SET status = 'pending', attempts = %s, 
                    next_retry_at = %s, process_after = %s, updated_at = NOW()
                WHERE id = %s
            """, (attempts, next_retry, next_retry, notification.id))
    
    async def _send_current_video_status(self, sid: str, video_id: str):
        """Send current video status to newly subscribed client"""
        db = SessionLocal()
        try:
            # Get current video and processing status
            result = db.execute("""
                SELECT v.id, v.filename, v.workflow_state, v.updated_at,
                       vps.current_stage, vps.progress_percentage, 
                       vps.processed_frames, vps.total_frames,
                       vps.error_count, vps.last_error_message
                FROM videos v
                LEFT JOIN video_processing_status vps ON v.id = vps.video_id
                WHERE v.id = %s
            """, (video_id,)).fetchone()
            
            if result:
                await self.sio.emit('video_status_update', {
                    'video_id': result.id,
                    'filename': result.filename,
                    'workflow_state': result.workflow_state,
                    'current_stage': result.current_stage,
                    'progress_percentage': float(result.progress_percentage or 0),
                    'processed_frames': result.processed_frames or 0,
                    'total_frames': result.total_frames or 0,
                    'error_count': result.error_count or 0,
                    'last_error': result.last_error_message,
                    'updated_at': result.updated_at.isoformat() if result.updated_at else None
                }, room=sid)
        
        finally:
            db.close()
    
    def _authenticate_user(self, auth) -> Optional[str]:
        """Authenticate user from auth token"""
        if not auth or 'token' not in auth:
            return 'anonymous'
        
        # TODO: Implement proper JWT token validation
        # For now, return anonymous user
        return 'anonymous'
```

### 2. Client-Side JavaScript Integration

```javascript
class VideoProcessingNotificationClient {
    constructor(serverUrl, options = {}) {
        this.serverUrl = serverUrl;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
        this.reconnectDelay = options.reconnectDelay || 1000;
        this.videoSubscriptions = new Set();
        this.projectSubscriptions = new Set();
        
        // Event handlers
        this.eventHandlers = new Map();
        
        this.connect();
    }
    
    connect() {
        this.socket = io(this.serverUrl, {
            transports: ['websocket', 'polling'],
            timeout: 20000,
            forceNew: true
        });
        
        this.socket.on('connect', () => {
            console.log('Connected to notification server');
            this.reconnectAttempts = 0;
            
            // Resubscribe to all active subscriptions
            this.resubscribeAll();
        });
        
        this.socket.on('disconnect', (reason) => {
            console.log('Disconnected from notification server:', reason);
            if (reason === 'io server disconnect') {
                // Server initiated disconnect, don't reconnect
                return;
            }
            this.scheduleReconnect();
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('Connection error:', error);
            this.scheduleReconnect();
        });
        
        // Set up event handlers
        this.setupEventHandlers();
    }
    
    setupEventHandlers() {
        // Video processing events
        this.socket.on('upload_started', (data) => this.handleEvent('upload_started', data));
        this.socket.on('upload_progress', (data) => this.handleEvent('upload_progress', data));
        this.socket.on('upload_completed', (data) => this.handleEvent('upload_completed', data));
        this.socket.on('upload_failed', (data) => this.handleEvent('upload_failed', data));
        
        this.socket.on('processing_started', (data) => this.handleEvent('processing_started', data));
        this.socket.on('processing_progress', (data) => this.handleEvent('processing_progress', data));
        this.socket.on('processing_stage_changed', (data) => this.handleEvent('processing_stage_changed', data));
        this.socket.on('processing_completed', (data) => this.handleEvent('processing_completed', data));
        this.socket.on('processing_failed', (data) => this.handleEvent('processing_failed', data));
        
        this.socket.on('ground_truth_started', (data) => this.handleEvent('ground_truth_started', data));
        this.socket.on('ground_truth_progress', (data) => this.handleEvent('ground_truth_progress', data));
        this.socket.on('ground_truth_completed', (data) => this.handleEvent('ground_truth_completed', data));
        this.socket.on('ground_truth_failed', (data) => this.handleEvent('ground_truth_failed', data));
        
        // System events
        this.socket.on('system_alert', (data) => this.handleEvent('system_alert', data));
        this.socket.on('connection_status', (data) => this.handleEvent('connection_status', data));
        
        // Status updates
        this.socket.on('video_status_update', (data) => this.handleEvent('video_status_update', data));
    }
    
    handleEvent(eventType, data) {
        console.log(`Received ${eventType}:`, data);
        
        // Call registered handlers
        const handlers = this.eventHandlers.get(eventType);
        if (handlers) {
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in event handler for ${eventType}:`, error);
                }
            });
        }
    }
    
    on(eventType, handler) {
        if (!this.eventHandlers.has(eventType)) {
            this.eventHandlers.set(eventType, []);
        }
        this.eventHandlers.get(eventType).push(handler);
    }
    
    off(eventType, handler) {
        const handlers = this.eventHandlers.get(eventType);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    subscribeToVideo(videoId) {
        if (this.socket && this.socket.connected) {
            this.socket.emit('subscribe_to_video', { video_id: videoId });
            this.videoSubscriptions.add(videoId);
        }
    }
    
    subscribeToProject(projectId) {
        if (this.socket && this.socket.connected) {
            this.socket.emit('subscribe_to_project', { project_id: projectId });
            this.projectSubscriptions.add(projectId);
        }
    }
    
    resubscribeAll() {
        // Resubscribe to all videos
        this.videoSubscriptions.forEach(videoId => {
            this.socket.emit('subscribe_to_video', { video_id: videoId });
        });
        
        // Resubscribe to all projects
        this.projectSubscriptions.forEach(projectId => {
            this.socket.emit('subscribe_to_project', { project_id: projectId });
        });
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
            
            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
            this.socket = null;
        }
    }
}

// Usage example
const notificationClient = new VideoProcessingNotificationClient('http://localhost:8000');

// Set up event handlers
notificationClient.on('upload_progress', (data) => {
    console.log(`Upload progress for video ${data.video_id}: ${data.progress?.percentage}%`);
    updateProgressBar(data.video_id, data.progress?.percentage);
});

notificationClient.on('processing_completed', (data) => {
    console.log(`Processing completed for video ${data.video_id}`);
    showSuccessNotification(`Video processing completed for ${data.filename}`);
});

notificationClient.on('processing_failed', (data) => {
    console.error(`Processing failed for video ${data.video_id}:`, data.error?.message);
    showErrorNotification(`Processing failed: ${data.error?.message}`);
});

// Subscribe to specific video updates
notificationClient.subscribeToVideo('video-uuid-here');
```

## PERFORMANCE OPTIMIZATION

### 1. Notification Batching

```python
class NotificationBatcher:
    def __init__(self, batch_size=50, flush_interval=2.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.pending_notifications = []
        self.last_flush = time.time()
    
    async def add_notification(self, notification):
        self.pending_notifications.append(notification)
        
        # Check if we should flush
        if (len(self.pending_notifications) >= self.batch_size or 
            time.time() - self.last_flush >= self.flush_interval):
            await self.flush_notifications()
    
    async def flush_notifications(self):
        if not self.pending_notifications:
            return
        
        # Group notifications by target
        grouped_notifications = {}
        for notification in self.pending_notifications:
            target = notification.get('target', 'global')
            if target not in grouped_notifications:
                grouped_notifications[target] = []
            grouped_notifications[target].append(notification)
        
        # Send grouped notifications
        for target, notifications in grouped_notifications.items():
            await self._send_grouped_notifications(target, notifications)
        
        self.pending_notifications.clear()
        self.last_flush = time.time()
```

### 2. Connection Health Monitoring

```python
class ConnectionHealthMonitor:
    def __init__(self, notification_server):
        self.server = notification_server
        self.health_check_interval = 30  # seconds
        self.connection_timeout = 120  # seconds
    
    async def start_monitoring(self):
        while True:
            try:
                await self.check_connection_health()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(5)
    
    async def check_connection_health(self):
        current_time = datetime.utcnow()
        disconnected_sessions = []
        
        for sid, connection_info in self.server.active_connections.items():
            last_ping = connection_info.get('last_ping', connection_info['connected_at'])
            time_since_ping = (current_time - last_ping).total_seconds()
            
            if time_since_ping > self.connection_timeout:
                disconnected_sessions.append(sid)
        
        # Clean up disconnected sessions
        for sid in disconnected_sessions:
            await self.server.sio.disconnect(sid)
            logger.info(f"Disconnected inactive session {sid}")
```

## MONITORING AND ALERTING

### 1. Notification System Metrics

```sql
-- Notification delivery performance
SELECT 
    event_type,
    status,
    COUNT(*) as notification_count,
    AVG(TIMESTAMPDIFF(SECOND, created_at, sent_at)) as avg_delivery_time,
    AVG(attempts) as avg_attempts,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) / COUNT(*) * 100 as failure_rate
FROM realtime_notification_queue 
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
GROUP BY event_type, status;

-- Queue health monitoring
SELECT 
    status,
    priority,
    COUNT(*) as queue_count,
    MIN(created_at) as oldest_notification,
    AVG(TIMESTAMPDIFF(SECOND, created_at, NOW())) as avg_age_seconds
FROM realtime_notification_queue
WHERE status IN ('pending', 'processing')
GROUP BY status, priority;
```

### 2. Alert Thresholds

```python
NOTIFICATION_ALERTS = {
    'queue_backlog': {
        'warning': 100,    # notifications
        'critical': 500
    },
    'failure_rate': {
        'warning': 5,      # percent
        'critical': 15
    },
    'delivery_time': {
        'warning': 10,     # seconds
        'critical': 30
    },
    'connection_count': {
        'warning': 1000,   # concurrent connections
        'critical': 2000
    }
}
```

This comprehensive real-time notification system specification provides instant, reliable communication between the video processing backend and frontend clients, ensuring users receive immediate updates on their video processing workflows.