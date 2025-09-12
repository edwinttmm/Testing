# Frontend Custom Hooks Complete Analysis

## Overview
This document provides comprehensive analysis of all custom React hooks in the AI Model Validation Platform frontend, including their parameters, return values, internal state management, side effects, and integration dependencies.

## Hook Categories

### Error Handling Hooks

#### 1. useErrorHandler
**File Path**: `/frontend/src/hooks/useErrorHandler.ts`

##### Hook Signature
```typescript
const useErrorHandler = (options: ErrorHandlerOptions = {}): UseErrorHandlerReturn
```

##### Parameters
```typescript
interface ErrorHandlerOptions {
  showNotifications?: boolean;        // Default: true
  messagePrefix?: string;            // Custom error message prefix
  logErrors?: boolean;               // Default: true
  maxRetries?: number;               // Default: 3
  retryDelay?: number;              // Default: 1000ms
  exponentialBackoff?: boolean;      // Default: true
  transformError?: ErrorTransformer; // Custom error transformer
}
```

##### Return Values
```typescript
interface UseErrorHandlerReturn {
  handleError: (error: Error | unknown, context?: string) => void;
  withErrorHandling: <T>(fn: () => Promise<T>, options?) => Promise<T | null>;
  withRetry: <T>(fn: RetryableFunction<T>, options?) => Promise<T | null>;
  createHandler: (context: string) => (error: Error | unknown) => void;
  getErrorMessage: (error: Error | unknown) => string;
}
```

##### Internal State
- `abortControllerRef: useRef<AbortController | null>` - Request cancellation control

##### Hook Dependencies
- `useErrorNotification()` - Error notification system
- `useCallback()` - Function memoization for performance
- `useMemo()` - Options object memoization
- `useEffect()` - Cleanup on unmount

##### Features
- **Error Classification**: Categorizes errors by type and severity
- **User-Friendly Messages**: Converts technical errors to readable messages
- **Retry Logic**: Configurable retry with exponential backoff
- **Context Preservation**: Maintains error context for debugging
- **Memory Management**: Automatic cleanup of abort controllers

##### Usage Patterns
```typescript
const { handleError, withErrorHandling, withRetry } = useErrorHandler({
  showNotifications: true,
  messagePrefix: 'API Error',
  maxRetries: 3
});

// Basic error handling
try {
  await apiCall();
} catch (error) {
  handleError(error, 'DataFetching');
}

// With automatic error handling
const data = await withErrorHandling(async () => {
  return await apiService.getProjects();
}, { context: 'ProjectLoading' });

// With retry logic
const result = await withRetry(
  () => unreliableApiCall(),
  { maxRetries: 5, context: 'RetryableOperation' }
);
```

#### 2. useErrorBoundary
**File Path**: `/frontend/src/hooks/useErrorBoundary.ts`

##### Hook Signature
```typescript
const useErrorBoundary = (): {
  resetBoundary: () => void;
  captureError: (error: Error, errorInfo?: ErrorInfo) => void;
}
```

##### Features
- **Boundary Reset**: Programmatic error boundary reset
- **Error Capture**: Manual error reporting to boundaries
- **Recovery Mechanisms**: Structured error recovery flows

### Real-time Data Hooks

#### 3. useWebSocket
**File Path**: `/frontend/src/hooks/useWebSocket.ts`

##### Hook Signature
```typescript
const useWebSocket = (
  url?: string,
  options: WebSocketOptions = {}
): WebSocketHookReturn
```

##### Parameters
```typescript
interface WebSocketOptions {
  reconnectAttempts?: number;        // Default: 5
  reconnectDelay?: number;          // Default: 1000ms
  heartbeatInterval?: number;       // Default: 30000ms
  messageTypes?: string[];          // Message type filtering
  onConnect?: () => void;           // Connection callback
  onDisconnect?: () => void;        // Disconnection callback
  onError?: (error: Event) => void; // Error callback
}
```

##### Return Values
```typescript
interface WebSocketHookReturn {
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  lastMessage: any;
  sendMessage: (message: any) => void;
  connect: () => void;
  disconnect: () => void;
  subscribe: (messageType: string, handler: (data: any) => void) => () => void;
}
```

##### Internal State
- `ws: useRef<WebSocket | null>` - WebSocket connection reference
- `isConnected: boolean` - Connection status
- `isConnecting: boolean` - Connection attempt status
- `error: string | null` - Connection error state
- `lastMessage: any` - Most recent message received
- `reconnectCount: number` - Current reconnection attempt count
- `messageHandlers: Map<string, Set<Function>>` - Message type handlers

##### Features
- **Automatic Reconnection**: Configurable reconnection with backoff
- **Message Type Filtering**: Subscribe to specific message types
- **Connection Health**: Heartbeat monitoring and recovery
- **Message Queue**: Buffer messages during disconnection
- **Memory Management**: Automatic cleanup on unmount

##### Usage Patterns
```typescript
const {
  isConnected,
  sendMessage,
  subscribe,
  error
} = useWebSocket('ws://localhost:8000/ws', {
  reconnectAttempts: 10,
  heartbeatInterval: 30000
});

// Subscribe to specific message types
useEffect(() => {
  const unsubscribe = subscribe('detection_result', (data) => {
    setDetectionResults(prev => [...prev, data]);
  });
  return unsubscribe;
}, [subscribe]);

// Send messages
const handleStartDetection = () => {
  sendMessage({
    type: 'start_detection',
    payload: { videoId: currentVideo.id }
  });
};
```

#### 4. useRealTimeData
**File Path**: `/frontend/src/hooks/useRealTimeData.ts`

##### Hook Signature
```typescript
const useRealTimeData = <T>(
  endpoint: string,
  options: RealTimeOptions<T> = {}
): RealTimeDataReturn<T>
```

##### Parameters
```typescript
interface RealTimeOptions<T> {
  initialData?: T;
  pollInterval?: number;           // Default: 5000ms
  enableWebSocket?: boolean;       // Default: true
  transformData?: (data: any) => T;
  onUpdate?: (data: T) => void;
}
```

##### Return Values
```typescript
interface RealTimeDataReturn<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}
```

##### Features
- **Hybrid Updates**: WebSocket + polling fallback
- **Data Transformation**: Client-side data processing
- **Update Notifications**: Real-time change callbacks
- **Intelligent Polling**: Adaptive polling based on activity

### Video Processing Hooks

#### 5. useVideoPlayer
**File Path**: `/frontend/src/hooks/useVideoPlayer.ts`

##### Hook Signature
```typescript
const useVideoPlayer = (
  videoRef: RefObject<HTMLVideoElement>,
  options: VideoPlayerOptions = {}
): VideoPlayerReturn
```

##### Parameters
```typescript
interface VideoPlayerOptions {
  autoPlay?: boolean;
  loop?: boolean;
  muted?: boolean;
  volume?: number;
  playbackRate?: number;
  onTimeUpdate?: (currentTime: number) => void;
  onEnded?: () => void;
  onError?: (error: Error) => void;
}
```

##### Return Values
```typescript
interface VideoPlayerReturn {
  // Playback state
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  buffered: TimeRanges | null;
  volume: number;
  playbackRate: number;
  
  // Controls
  play: () => Promise<void>;
  pause: () => void;
  seek: (time: number) => void;
  setVolume: (volume: number) => void;
  setPlaybackRate: (rate: number) => void;
  toggleMute: () => void;
  
  // State
  loading: boolean;
  error: string | null;
  canPlay: boolean;
}
```

##### Internal State Management
- **Playback State**: Current time, duration, playing status
- **Buffer Management**: Loading and buffering states
- **Error Handling**: Playback error recovery
- **Event Listeners**: Video element event management

##### Features
- **Safe Playback Control**: Handles browser autoplay policies
- **Buffer Monitoring**: Loading and buffering state tracking
- **Error Recovery**: Automatic retry on playback failures
- **Performance Optimization**: Throttled time updates

#### 6. useSequentialVideoPlayback
**File Path**: `/frontend/src/hooks/useSequentialVideoPlayback.ts`

##### Hook Signature
```typescript
const useSequentialVideoPlayback = (
  videos: VideoFile[],
  options: SequentialPlaybackOptions = {}
): SequentialPlaybackReturn
```

##### Parameters
```typescript
interface SequentialPlaybackOptions {
  autoAdvance?: boolean;           // Default: true
  loopPlayback?: boolean;         // Default: false
  onVideoStart?: (video: VideoFile, index: number) => void;
  onVideoEnd?: (video: VideoFile, index: number) => void;
  onPlaybackComplete?: () => void;
  onError?: (error: Error, video: VideoFile) => void;
}
```

##### Return Values
```typescript
interface SequentialPlaybackReturn {
  currentVideoIndex: number;
  totalProgress: number;
  isPlaying: boolean;
  currentVideo: VideoFile | null;
  
  start: () => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  skipToNext: () => void;
  skipToPrevious: () => void;
  skipToVideo: (index: number) => void;
  
  loading: boolean;
  error: string | null;
}
```

##### Features
- **Video Queue Management**: Maintains playback queue and state
- **Progress Tracking**: Overall and per-video progress
- **Transition Handling**: Smooth video transitions
- **Error Recovery**: Skip failed videos and continue

### Detection and Validation Hooks

#### 7. useDetection
**File Path**: `/frontend/src/hooks/useDetection.ts`

##### Hook Signature
```typescript
const useDetection = (
  videoId: string,
  config: DetectionConfig
): DetectionHookReturn
```

##### Parameters
```typescript
interface DetectionConfig {
  confidenceThreshold: number;
  nmsThreshold: number;
  modelName: string;
  targetClasses: string[];
  enableTracking?: boolean;
}
```

##### Return Values
```typescript
interface DetectionHookReturn {
  isRunning: boolean;
  progress: number;
  results: Detection[];
  error: string | null;
  
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
  
  // Real-time updates
  onDetection: (handler: (detection: Detection) => void) => () => void;
  onProgress: (handler: (progress: number) => void) => () => void;
}
```

##### Features
- **Pipeline Control**: Start/stop detection processing
- **Real-time Results**: Live detection result streaming
- **Progress Monitoring**: Processing progress updates
- **Configuration Management**: Dynamic config updates

#### 8. useHILTestExecution
**File Path**: `/frontend/src/hooks/useHILTestExecution.ts`

##### Hook Signature
```typescript
const useHILTestExecution = (
  projectId: string,
  config: HILConfig
): HILTestReturn
```

##### Parameters
```typescript
interface HILConfig {
  detectionWindowMs: number;
  voltageThreshold: number;
  sampleRate: number;
  channels: string[];
  enableLabJack: boolean;
}
```

##### Return Values
```typescript
interface HILTestReturn {
  isRunning: boolean;
  currentVideo: VideoFile | null;
  progress: TestProgress;
  results: HILTestResult[];
  
  start: () => Promise<void>;
  stop: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  
  // LabJack integration
  labJackStatus: LabJackStatus;
  signalData: SignalData[];
  
  error: string | null;
}
```

##### Features
- **Hardware Integration**: LabJack signal validation
- **Test Orchestration**: Automated test sequence execution
- **Real-time Monitoring**: Live test progress and results
- **Signal Processing**: Hardware signal validation

### UI Enhancement Hooks

#### 9. useResponsiveVideoPlayer
**File Path**: `/frontend/src/hooks/useResponsiveVideoPlayer.ts`

##### Hook Signature
```typescript
const useResponsiveVideoPlayer = (
  containerRef: RefObject<HTMLElement>
): ResponsiveVideoReturn
```

##### Return Values
```typescript
interface ResponsiveVideoReturn {
  dimensions: { width: number; height: number };
  aspectRatio: number;
  isFullscreen: boolean;
  isMobile: boolean;
  
  enterFullscreen: () => Promise<void>;
  exitFullscreen: () => Promise<void>;
  toggleFullscreen: () => Promise<void>;
  
  // Responsive behavior
  autoResize: boolean;
  setAutoResize: (enabled: boolean) => void;
}
```

##### Features
- **Responsive Sizing**: Automatic size adjustment
- **Fullscreen Management**: Native fullscreen API integration
- **Mobile Optimization**: Touch-friendly controls
- **Aspect Ratio Preservation**: Maintain video proportions

#### 10. useBoundaryBoxSnapping
**File Path**: `/frontend/src/hooks/useBoundaryBoxSnapping.ts`

##### Hook Signature
```typescript
const useBoundaryBoxSnapping = (
  canvasRef: RefObject<HTMLCanvasElement>,
  config: SnappingConfig = {}
): SnappingReturn
```

##### Parameters
```typescript
interface SnappingConfig {
  snapThreshold: number;          // Default: 10px
  snapToGrid: boolean;           // Default: false
  gridSize: number;              // Default: 10px
  snapToObjects: boolean;        // Default: true
  magneticStrength: number;      // Default: 0.5
}
```

##### Return Values
```typescript
interface SnappingReturn {
  snapPoint: (point: Point) => Point;
  snapBox: (box: BoundingBox) => BoundingBox;
  getSnapPoints: () => Point[];
  enableSnapping: boolean;
  setEnableSnapping: (enabled: boolean) => void;
  
  // Visual feedback
  snapIndicators: SnapIndicator[];
  isSnapping: boolean;
}
```

##### Features
- **Intelligent Snapping**: Smart boundary box alignment
- **Grid Snapping**: Optional grid-based alignment
- **Object Snapping**: Snap to existing annotations
- **Visual Feedback**: Real-time snapping indicators

### Performance Optimization Hooks

#### 11. useSmartErrorRecovery
**File Path**: `/frontend/src/hooks/useSmartErrorRecovery.ts`

##### Hook Signature
```typescript
const useSmartErrorRecovery = <T>(
  operation: () => Promise<T>,
  options: RecoveryOptions<T> = {}
): SmartRecoveryReturn<T>
```

##### Parameters
```typescript
interface RecoveryOptions<T> {
  maxRetries: number;
  backoffMultiplier: number;
  initialDelay: number;
  fallbackValue?: T;
  shouldRetry?: (error: Error) => boolean;
  onRetry?: (attempt: number, error: Error) => void;
  onFallback?: () => void;
}
```

##### Return Values
```typescript
interface SmartRecoveryReturn<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  retryCount: number;
  
  retry: () => Promise<void>;
  reset: () => void;
  
  // Recovery state
  isRecovering: boolean;
  hasFallback: boolean;
  canRetry: boolean;
}
```

##### Features
- **Intelligent Retry**: Context-aware retry decisions
- **Fallback Management**: Graceful degradation strategies
- **Recovery Analytics**: Track recovery success rates
- **Adaptive Behavior**: Learn from failure patterns

## Hook Integration Patterns

### 1. Hook Composition
```typescript
const useVideoAnnotation = (videoId: string) => {
  const { handleError } = useErrorHandler();
  const { data: annotations, loading } = useRealTimeData(`/api/videos/${videoId}/annotations`);
  const videoPlayer = useVideoPlayer(videoRef);
  const snapping = useBoundaryBoxSnapping(canvasRef);
  
  return {
    annotations,
    loading,
    videoPlayer,
    snapping,
    error: videoPlayer.error
  };
};
```

### 2. Dependency Chain
```
useHILTestExecution
├── useDetection (video processing)
├── useWebSocket (real-time updates)
├── useErrorHandler (error management)
└── useVideoPlayer (playback control)

useVideoAnnotation
├── useRealTimeData (annotation data)
├── useVideoPlayer (video control)
├── useBoundaryBoxSnapping (UI enhancement)
└── useErrorHandler (error management)
```

### 3. State Synchronization
```typescript
// Synchronized state between hooks
const useDetectionWorkflow = () => {
  const detection = useDetection(videoId, config);
  const webSocket = useWebSocket();
  const errorHandler = useErrorHandler();
  
  // Sync detection state with WebSocket
  useEffect(() => {
    if (detection.isRunning) {
      webSocket.subscribe('detection_progress', (data) => {
        detection.updateProgress(data.progress);
      });
    }
  }, [detection.isRunning]);
  
  return { detection, webSocket, errorHandler };
};
```

## Performance Considerations

### 1. Memory Management
- **Cleanup Functions**: Proper cleanup in useEffect returns
- **Ref Management**: Avoid memory leaks with DOM references
- **Event Listeners**: Remove listeners on unmount
- **Timer Cleanup**: Clear intervals and timeouts

### 2. Render Optimization
- **Callback Memoization**: Use useCallback for expensive functions
- **Value Memoization**: Use useMemo for computed values
- **Dependency Arrays**: Minimize unnecessary re-renders
- **State Batching**: Batch related state updates

### 3. Resource Efficiency
- **Lazy Loading**: Load resources only when needed
- **Connection Pooling**: Reuse WebSocket connections
- **Request Deduplication**: Avoid duplicate API calls
- **Cache Utilization**: Leverage cached data

## Testing Strategies

### 1. Unit Testing
```typescript
describe('useErrorHandler', () => {
  it('should handle errors correctly', () => {
    const { result } = renderHook(() => useErrorHandler());
    
    act(() => {
      result.current.handleError(new Error('Test error'));
    });
    
    expect(mockShowError).toHaveBeenCalled();
  });
});
```

### 2. Integration Testing
```typescript
describe('useVideoPlayer integration', () => {
  it('should integrate with detection hooks', async () => {
    const { result } = renderHook(() => ({
      player: useVideoPlayer(videoRef),
      detection: useDetection(videoId, config)
    }));
    
    await act(async () => {
      await result.current.player.play();
      await result.current.detection.start();
    });
    
    expect(result.current.detection.isRunning).toBe(true);
  });
});
```

### 3. Performance Testing
- **Memory Leak Detection**: Monitor hook memory usage
- **Render Count Tracking**: Measure unnecessary re-renders
- **Resource Usage**: Monitor API calls and WebSocket connections
- **Cleanup Verification**: Ensure proper resource cleanup

## Known Issues and Future Improvements

### Current Issues
1. **Memory Leaks**: Some hooks may not clean up properly in edge cases
2. **Race Conditions**: Async operations may conflict with component unmounting
3. **Error Propagation**: Error boundaries may not catch all async errors
4. **Performance**: Some hooks cause unnecessary re-renders

### Planned Enhancements
1. **Better Error Boundaries**: Enhanced error recovery mechanisms
2. **State Persistence**: Hook state persistence across navigation
3. **Performance Optimization**: Reduce re-renders and memory usage
4. **Testing Coverage**: Comprehensive unit and integration tests

### Technical Debt
1. **Hook Dependencies**: Some hooks have circular dependencies
2. **Type Safety**: Improve TypeScript types for better safety
3. **Documentation**: Add comprehensive JSDoc comments
4. **Consistency**: Standardize hook patterns and naming