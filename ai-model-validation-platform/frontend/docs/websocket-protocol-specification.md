# WebSocket Protocol Specification

## Overview

The AI Model Validation Platform uses Socket.IO for real-time bidirectional communication between clients and the server. This document details all WebSocket events, message formats, connection patterns, and integration protocols.

## Connection Configuration

### Server Details
- **URL**: `http://155.138.239.131:8001` (Production)
- **URL**: `http://localhost:8001` (Development)
- **Transport**: Socket.IO with WebSocket and polling fallback
- **Namespace**: `/` (default namespace)

### Connection Options
```typescript
const socketConfig = {
  transports: ['websocket', 'polling'],
  timeout: 20000,
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 1000,
  maxReconnectionDelay: 30000,
  reconnectionDelayGrowth: 1.5,
  randomizationFactor: 0.5
};
```

## Event Categories

### 1. Connection Management Events

#### Connection Established
```typescript
socket.on('connect', () => {
  console.log('Connected with ID:', socket.id);
  // Client should register for relevant channels
  socket.emit('register_client', {
    client_type: 'frontend',
    user_id: 'anonymous',
    interests: ['detections', 'annotations', 'test_sessions']
  });
});
```

#### Connection Error
```typescript
socket.on('connect_error', (error) => {
  console.error('Connection failed:', error.message);
  // Error types: timeout, authentication, server_error
});
```

#### Disconnection
```typescript
socket.on('disconnect', (reason) => {
  console.log('Disconnected:', reason);
  // Reasons: io server disconnect, io client disconnect, ping timeout, transport close, transport error
});
```

#### Reconnection Events
```typescript
socket.on('reconnect_attempt', (attemptNumber) => {
  console.log(`Reconnection attempt ${attemptNumber}`);
});

socket.on('reconnect', (attemptNumber) => {
  console.log(`Reconnected after ${attemptNumber} attempts`);
  // Re-register client and subscriptions
});

socket.on('reconnect_failed', () => {
  console.error('Failed to reconnect after all attempts');
});
```

### 2. Detection Events

#### Real-time Detection Updates
```typescript
socket.on('detection_update', (data: DetectionUpdateEvent) => {
  // Process real-time detection updates
});

interface DetectionUpdateEvent {
  video_id: string;
  detection_id: string;
  test_session_id?: string;
  timestamp: number;
  frame_number: number;
  class_label: string;
  vru_type: string;
  confidence: number;
  bounding_box: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  status: 'new' | 'updated' | 'validated' | 'rejected';
  validation_result?: 'TP' | 'FP' | 'FN';
  processing_time_ms: number;
  model_version: string;
  screenshot_path?: string;
  screenshot_zoom_path?: string;
}
```

#### Detection Processing Progress
```typescript
socket.on('detection_progress', (data: DetectionProgressEvent) => {
  // Update progress bars and status displays
});

interface DetectionProgressEvent {
  video_id: string;
  test_session_id?: string;
  progress: number; // 0-100
  current_frame: number;
  total_frames: number;
  frames_per_second: number;
  eta_seconds: number;
  status: 'starting' | 'processing' | 'completing' | 'completed' | 'error';
  detections_found: number;
  error_message?: string;
}
```

#### Detection Pipeline Status
```typescript
socket.on('detection_pipeline_status', (data: PipelineStatusEvent) => {
  // Monitor ML pipeline health and performance
});

interface PipelineStatusEvent {
  pipeline_id: string;
  status: 'initializing' | 'ready' | 'processing' | 'error' | 'maintenance';
  model_name: string;
  model_version: string;
  gpu_utilization?: number;
  memory_usage?: number;
  queue_length: number;
  throughput_fps?: number;
  error_details?: {
    error_type: string;
    message: string;
    stack_trace?: string;
  };
}
```

### 3. Video Processing Events

#### Video Upload Progress
```typescript
socket.on('video_upload_progress', (data: VideoUploadProgressEvent) => {
  // Update upload progress indicators
});

interface VideoUploadProgressEvent {
  video_id: string;
  project_id: string;
  filename: string;
  upload_progress: number; // 0-100
  bytes_uploaded: number;
  total_bytes: number;
  upload_speed_mbps: number;
  eta_seconds: number;
  status: 'uploading' | 'processing_metadata' | 'completed' | 'error';
  error_message?: string;
}
```

#### Ground Truth Generation Progress
```typescript
socket.on('ground_truth_progress', (data: GroundTruthProgressEvent) => {
  // Track ground truth generation progress
});

interface GroundTruthProgressEvent {
  video_id: string;
  progress: number; // 0-100
  current_frame: number;
  total_frames: number;
  status: 'extracting_frames' | 'analyzing' | 'generating' | 'completed' | 'error';
  objects_detected: number;
  confidence_threshold: number;
  processing_fps: number;
  eta_seconds: number;
  error_details?: {
    error_type: string;
    message: string;
    frame_number?: number;
  };
}
```

#### Video Processing Status
```typescript
socket.on('video_processing_status', (data: VideoProcessingStatusEvent) => {
  // Monitor overall video processing pipeline
});

interface VideoProcessingStatusEvent {
  video_id: string;
  project_id: string;
  processing_stage: 'upload' | 'validation' | 'frame_extraction' | 'ground_truth' | 'indexing' | 'completed';
  stage_progress: number; // 0-100 for current stage
  overall_progress: number; // 0-100 for entire process
  stages_completed: string[];
  current_stage_details: {
    name: string;
    description: string;
    estimated_duration_seconds: number;
    started_at: string;
  };
  error_details?: {
    stage: string;
    error_type: string;
    message: string;
    recoverable: boolean;
  };
}
```

### 4. Test Session Events

#### Test Session Status Updates
```typescript
socket.on('test_session_update', (data: TestSessionUpdateEvent) => {
  // Update test session status and results
});

interface TestSessionUpdateEvent {
  session_id: string;
  project_id: string;
  video_id: string;
  name: string;
  status: 'created' | 'initializing' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  started_at?: string;
  estimated_completion?: string;
  current_phase: 'setup' | 'detection' | 'validation' | 'analysis' | 'reporting';
  results?: {
    detections_processed: number;
    true_positives: number;
    false_positives: number;
    false_negatives: number;
    precision: number;
    recall: number;
    f1_score: number;
    accuracy: number;
  };
  error_details?: {
    error_type: string;
    message: string;
    phase: string;
    recoverable: boolean;
  };
}
```

#### Test Execution Control
```typescript
// Client to Server: Control test execution
socket.emit('test_session_control', {
  session_id: string;
  action: 'start' | 'pause' | 'resume' | 'stop' | 'cancel';
  parameters?: {
    frame_rate_multiplier?: number;
    confidence_threshold?: number;
    validation_mode?: 'strict' | 'normal' | 'lenient';
  };
});

// Server to Client: Control acknowledgment
socket.on('test_session_control_ack', (data: TestControlAckEvent) => {
  // Handle control command acknowledgment
});

interface TestControlAckEvent {
  session_id: string;
  action: string;
  status: 'accepted' | 'rejected' | 'completed';
  message: string;
  timestamp: string;
}
```

### 5. Annotation & Collaboration Events

#### Real-time Annotation Updates
```typescript
socket.on('annotation_update', (data: AnnotationUpdateEvent) => {
  // Handle collaborative annotation changes
});

interface AnnotationUpdateEvent {
  video_id: string;
  annotation_id: string;
  annotator_id: string;
  annotator_name: string;
  action: 'created' | 'updated' | 'deleted' | 'validated' | 'rejected';
  timestamp: string;
  frame_number: number;
  annotation: {
    id: string;
    detection_id?: string;
    vru_type: string;
    bounding_box: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
    confidence: number;
    occluded: boolean;
    truncated: boolean;
    difficult: boolean;
    notes?: string;
    validated: boolean;
  };
  change_summary?: {
    fields_changed: string[];
    previous_values?: Record<string, any>;
  };
}
```

#### Collaborative Cursor & Selection
```typescript
socket.on('annotation_cursor', (data: AnnotationCursorEvent) => {
  // Show other users' cursors and selections
});

interface AnnotationCursorEvent {
  video_id: string;
  annotator_id: string;
  annotator_name: string;
  annotator_color: string;
  frame_number: number;
  cursor_position: {
    x: number;
    y: number;
  };
  selected_annotation?: string;
  drawing_mode?: 'select' | 'create' | 'edit' | 'delete';
  viewport: {
    zoom: number;
    pan_x: number;
    pan_y: number;
  };
  timestamp: string;
}
```

#### Annotation Session Management
```typescript
socket.on('annotation_session_update', (data: AnnotationSessionEvent) => {
  // Track annotation session state
});

interface AnnotationSessionEvent {
  session_id: string;
  video_id: string;
  project_id: string;
  annotator_id: string;
  status: 'active' | 'paused' | 'completed' | 'abandoned';
  statistics: {
    total_annotations: number;
    validated_annotations: number;
    current_frame: number;
    total_frames: number;
    time_spent_seconds: number;
    annotations_per_hour: number;
  };
  current_activity: {
    action: 'viewing' | 'annotating' | 'validating' | 'reviewing';
    frame_number: number;
    annotation_id?: string;
    started_at: string;
  };
}
```

### 6. System Status & Health Events

#### System Health Updates
```typescript
socket.on('system_status', (data: SystemStatusEvent) => {
  // Monitor system component health
});

interface SystemStatusEvent {
  component: 'api' | 'database' | 'ml_pipeline' | 'storage' | 'websocket' | 'queue';
  status: 'healthy' | 'degraded' | 'error' | 'maintenance';
  response_time_ms?: number;
  error_rate?: number;
  message: string;
  details?: {
    cpu_usage?: number;
    memory_usage?: number;
    disk_usage?: number;
    queue_length?: number;
    active_connections?: number;
  };
  timestamp: string;
  severity: 'info' | 'warning' | 'error' | 'critical';
}
```

#### Performance Metrics
```typescript
socket.on('performance_metrics', (data: PerformanceMetricsEvent) => {
  // Display real-time performance data
});

interface PerformanceMetricsEvent {
  metric_type: 'detection_throughput' | 'api_latency' | 'upload_speed' | 'processing_queue';
  value: number;
  unit: string;
  trend: 'increasing' | 'decreasing' | 'stable';
  threshold_status: 'normal' | 'warning' | 'critical';
  historical_data?: {
    timestamp: string;
    value: number;
  }[];
  timestamp: string;
}
```

### 7. Notification Events

#### User Notifications
```typescript
socket.on('notification', (data: NotificationEvent) => {
  // Display notifications to users
});

interface NotificationEvent {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  category: 'system' | 'detection' | 'test' | 'annotation' | 'upload';
  action_required: boolean;
  actions?: {
    label: string;
    action: string;
    parameters?: Record<string, any>;
  }[];
  auto_dismiss_seconds?: number;
  timestamp: string;
  related_entities?: {
    project_id?: string;
    video_id?: string;
    session_id?: string;
    annotation_id?: string;
  };
}
```

## Client-to-Server Events

### Room Management
```typescript
// Join specific rooms for targeted updates
socket.emit('join_room', {
  room_type: 'project' | 'video' | 'test_session' | 'annotation_session';
  room_id: string;
  user_id?: string;
});

socket.emit('leave_room', {
  room_type: 'project' | 'video' | 'test_session' | 'annotation_session';
  room_id: string;
});
```

### Heartbeat & Connection Monitoring
```typescript
// Periodic heartbeat to maintain connection
socket.emit('ping', {
  timestamp: Date.now(),
  client_info: {
    user_agent: navigator.userAgent,
    viewport: {
      width: window.innerWidth,
      height: window.innerHeight
    }
  }
});

socket.on('pong', (data) => {
  const latency = Date.now() - data.timestamp;
  console.log('Connection latency:', latency, 'ms');
});
```

### Request-Response Pattern
```typescript
// Request specific data with acknowledgment
socket.emit('get_detection_results', {
  video_id: 'uuid',
  frame_range?: {
    start: number;
    end: number;
  }
}, (response) => {
  if (response.success) {
    console.log('Detection results:', response.data);
  } else {
    console.error('Request failed:', response.error);
  }
});
```

## Connection Lifecycle Management

### Client Implementation
```typescript
class WebSocketManager {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private subscriptions = new Map<string, Function[]>();
  
  async connect(): Promise<boolean> {
    try {
      this.socket = io(WEBSOCKET_URL, socketConfig);
      
      // Setup event handlers
      this.setupConnectionHandlers();
      this.setupEventHandlers();
      
      // Wait for connection
      return new Promise((resolve, reject) => {
        this.socket!.on('connect', () => {
          this.onConnected();
          resolve(true);
        });
        
        this.socket!.on('connect_error', (error) => {
          reject(error);
        });
        
        setTimeout(() => reject(new Error('Connection timeout')), 10000);
      });
      
    } catch (error) {
      console.error('WebSocket connection failed:', error);
      return false;
    }
  }
  
  private onConnected() {
    console.log('WebSocket connected');
    this.reconnectAttempts = 0;
    
    // Register client
    this.socket!.emit('register_client', {
      client_type: 'frontend',
      user_id: this.getUserId(),
      interests: this.getSubscriptionInterests()
    });
    
    // Rejoin rooms
    this.rejoinRooms();
    
    // Restore subscriptions
    this.restoreSubscriptions();
  }
  
  private setupConnectionHandlers() {
    this.socket!.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      
      if (reason === 'io server disconnect') {
        // Server initiated disconnect, don't reconnect automatically
        this.handleServerDisconnect();
      } else {
        // Network issue, attempt reconnection
        this.attemptReconnection();
      }
    });
    
    this.socket!.on('reconnect', (attemptNumber) => {
      console.log('WebSocket reconnected after', attemptNumber, 'attempts');
      this.onConnected();
    });
    
    this.socket!.on('reconnect_failed', () => {
      console.error('WebSocket reconnection failed');
      this.handleReconnectionFailure();
    });
  }
  
  private attemptReconnection() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
      
      setTimeout(() => {
        this.connect().catch(console.error);
      }, this.calculateBackoffDelay());
    } else {
      this.handleReconnectionFailure();
    }
  }
  
  private calculateBackoffDelay(): number {
    const baseDelay = 1000;
    const maxDelay = 30000;
    const exponentialDelay = baseDelay * Math.pow(2, this.reconnectAttempts);
    const jitteredDelay = exponentialDelay * (0.5 + Math.random() * 0.5);
    return Math.min(jitteredDelay, maxDelay);
  }
}
```

## Error Handling & Recovery

### Error Types and Responses
```typescript
interface WebSocketError {
  error_type: 'connection_error' | 'authentication_error' | 'validation_error' | 'server_error' | 'rate_limit_error';
  message: string;
  error_code: string;
  details?: Record<string, any>;
  timestamp: string;
  request_id?: string;
}

// Error event handling
socket.on('error', (error: WebSocketError) => {
  console.error('WebSocket error:', error);
  
  switch (error.error_type) {
    case 'rate_limit_error':
      this.handleRateLimit(error);
      break;
    case 'authentication_error':
      this.handleAuthError(error);
      break;
    case 'validation_error':
      this.handleValidationError(error);
      break;
    default:
      this.handleGenericError(error);
  }
});
```

### Message Validation
```typescript
class MessageValidator {
  validateDetectionUpdate(data: any): data is DetectionUpdateEvent {
    return (
      typeof data === 'object' &&
      typeof data.video_id === 'string' &&
      typeof data.detection_id === 'string' &&
      typeof data.timestamp === 'number' &&
      typeof data.confidence === 'number' &&
      data.confidence >= 0 && data.confidence <= 1 &&
      typeof data.bounding_box === 'object' &&
      typeof data.bounding_box.x === 'number' &&
      typeof data.bounding_box.y === 'number' &&
      typeof data.bounding_box.width === 'number' &&
      typeof data.bounding_box.height === 'number'
    );
  }
  
  validateIncomingMessage(eventType: string, data: any): boolean {
    switch (eventType) {
      case 'detection_update':
        return this.validateDetectionUpdate(data);
      case 'test_session_update':
        return this.validateTestSessionUpdate(data);
      // Add more validators as needed
      default:
        console.warn('No validator for event type:', eventType);
        return true; // Allow unknown events
    }
  }
}
```

## Performance Optimization

### Message Batching
```typescript
class MessageBatcher {
  private batchQueue: Array<{eventType: string, data: any}> = [];
  private batchTimer: NodeJS.Timeout | null = null;
  private readonly BATCH_SIZE = 10;
  private readonly BATCH_DELAY_MS = 100;
  
  queueMessage(eventType: string, data: any) {
    this.batchQueue.push({eventType, data});
    
    if (this.batchQueue.length >= this.BATCH_SIZE) {
      this.flushBatch();
    } else if (!this.batchTimer) {
      this.batchTimer = setTimeout(() => this.flushBatch(), this.BATCH_DELAY_MS);
    }
  }
  
  private flushBatch() {
    if (this.batchQueue.length > 0) {
      socket.emit('batch_events', this.batchQueue);
      this.batchQueue = [];
    }
    
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = null;
    }
  }
}
```

### Connection Pooling
```typescript
class WebSocketPool {
  private connections: Map<string, Socket> = new Map();
  private readonly MAX_CONNECTIONS = 5;
  
  getConnection(namespace: string = '/'): Socket {
    if (!this.connections.has(namespace)) {
      if (this.connections.size >= this.MAX_CONNECTIONS) {
        // Close least recently used connection
        this.closeLRUConnection();
      }
      
      const socket = io(`${WEBSOCKET_URL}${namespace}`, socketConfig);
      this.connections.set(namespace, socket);
    }
    
    return this.connections.get(namespace)!;
  }
  
  private closeLRUConnection() {
    // Implementation for LRU eviction
    const oldestNamespace = this.connections.keys().next().value;
    const oldestSocket = this.connections.get(oldestNamespace);
    oldestSocket?.disconnect();
    this.connections.delete(oldestNamespace);
  }
}
```

## Security Considerations

### Message Sanitization
```typescript
class MessageSanitizer {
  sanitizeIncoming(data: any): any {
    if (typeof data === 'string') {
      return this.sanitizeString(data);
    } else if (Array.isArray(data)) {
      return data.map(item => this.sanitizeIncoming(item));
    } else if (typeof data === 'object' && data !== null) {
      const sanitized: any = {};
      for (const [key, value] of Object.entries(data)) {
        sanitized[this.sanitizeString(key)] = this.sanitizeIncoming(value);
      }
      return sanitized;
    }
    return data;
  }
  
  private sanitizeString(str: string): string {
    return str.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
              .replace(/javascript:/gi, '')
              .replace(/on\w+=/gi, '');
  }
}
```

### Rate Limiting
```typescript
class ClientRateLimiter {
  private messageCount = 0;
  private windowStart = Date.now();
  private readonly WINDOW_SIZE_MS = 60000; // 1 minute
  private readonly MAX_MESSAGES_PER_WINDOW = 100;
  
  canSendMessage(): boolean {
    const now = Date.now();
    
    if (now - this.windowStart >= this.WINDOW_SIZE_MS) {
      // Reset window
      this.windowStart = now;
      this.messageCount = 0;
    }
    
    if (this.messageCount >= this.MAX_MESSAGES_PER_WINDOW) {
      console.warn('Rate limit exceeded');
      return false;
    }
    
    this.messageCount++;
    return true;
  }
}
```

This WebSocket protocol specification provides comprehensive documentation for all real-time communication patterns in the AI Model Validation Platform, including detailed event schemas, error handling, performance optimization, and security considerations.