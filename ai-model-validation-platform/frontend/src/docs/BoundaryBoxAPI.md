# Boundary Box API Integration Documentation

This document explains how to use the boundary box API integration services that connect the frontend to the Node.js boundary detection system.

## Overview

The boundary box integration consists of several interconnected services:

1. **BoundaryBoxService** - Core boundary box validation and processing
2. **PedestrianDetectionService** - Pedestrian detection with confidence analysis
3. **BoundaryBoxWebSocketService** - Real-time updates via WebSocket
4. **API Service Extensions** - HTTP endpoints for backend integration
5. **Integration Example** - Complete system demonstration

## Service Architecture

```
Frontend Services
├── boundaryBoxService.ts          # Core boundary box operations
├── pedestrianDetectionService.ts  # Pedestrian detection & tracking
├── boundaryBoxWebSocketService.ts # Real-time WebSocket updates
├── api.ts (extended)              # HTTP API integration
└── boundaryBoxIntegrationExample.ts # Complete system example
```

## Quick Start

### 1. Initialize the System

```typescript
import { boundaryBoxIntegration } from './services/boundaryBoxIntegrationExample';

// Initialize for a specific video
const success = await boundaryBoxIntegration.initialize('video-123');
if (success) {
  console.log('✅ Boundary box system ready');
}
```

### 2. Process a Single Frame

```typescript
// Process frame 80 (the problematic frame)
const result = await boundaryBoxIntegration.processFrame(80);

console.log('Detections:', result.pedestrianDetections.length);
console.log('Boundary results:', result.boundaryResults.length);

if (result.frame80Analysis) {
  console.log('Frame 80 issues:', result.frame80Analysis.issues);
}
```

### 3. Debug Frame 80 Issues

```typescript
// Run comprehensive Frame 80 debugging
const debugging = await boundaryBoxIntegration.debugFrame80();

console.log('Analysis:', debugging.analysis);
console.log('Issues:', debugging.analysis.issues);
console.log('Recommendations:', debugging.recommendations);
```

## Core Services

### BoundaryBoxService

Handles boundary box validation, processing, and snapping.

#### Key Methods

```typescript
import { boundaryBoxService } from './services/boundaryBoxService';

// Validate a boundary box
const validation = await boundaryBoxService.validateBoundingBox(
  { x: 0, y: 0, width: 100, height: 100 },
  { width: 1920, height: 1080 }
);

// Process with snapping
const processing = await boundaryBoxService.processBoundingBox(
  boundingBox,
  { enableSnapping: true }
);

// Frame 80 specific debugging
const debugData = await boundaryBoxService.getFrame80DebugData('video-123');

// Fix Frame 80 issues
const fixResult = await boundaryBoxService.fixFrame80Issues('video-123', 80);
```

#### Configuration

```typescript
// Update snapping configuration
await boundaryBoxService.updateSnappingConfig({
  enabled: true,
  tolerance: 5,
  snapToGrid: false,
  snapToEdges: true,
  snapToCenter: true
});
```

### PedestrianDetectionService

Manages pedestrian detection, confidence analysis, and tracking.

#### Key Methods

```typescript
import { pedestrianDetectionService } from './services/pedestrianDetectionService';

// Detect pedestrians in a frame
const detections = await pedestrianDetectionService.detectInFrame(
  'video-123',
  80
);

// Detect across multiple frames
const frameMap = await pedestrianDetectionService.detectInFrameRange(
  'video-123',
  75,
  85
);

// Analyze Frame 80 specifically
const frame80Analysis = await pedestrianDetectionService.analyzeFrame80('video-123');

// Analyze confidence for tracking
const confidenceAnalysis = await pedestrianDetectionService.analyzeConfidence('track-001');
```

#### Configuration

```typescript
// Update detection configuration
await pedestrianDetectionService.updateConfig({
  confidenceThreshold: 0.8,
  nmsThreshold: 0.4,
  modelName: 'yolov8n',
  targetClasses: ['person', 'bicycle', 'motorcycle'],
  enableTracking: true,
  trackingPersistence: 5
});
```

### BoundaryBoxWebSocketService

Provides real-time updates for boundary box processing.

#### Connection

```typescript
import { boundaryBoxWebSocketService } from './services/boundaryBoxWebSocketService';

// Connect to WebSocket
const connected = await boundaryBoxWebSocketService.connect('video-123');

if (connected) {
  console.log('🔌 Connected to boundary box WebSocket');
}
```

#### Subscriptions

```typescript
// Subscribe to boundary box updates
const unsubscribe = boundaryBoxWebSocketService.subscribe(
  'boundary_update',
  (message) => {
    console.log('📦 Boundary update:', message.frameNumber);
  }
);

// Subscribe to pedestrian detection updates
boundaryBoxWebSocketService.subscribe(
  'pedestrian_update',
  (message) => {
    console.log('🚶 Pedestrian update:', message.detections.length);
  }
);

// Subscribe to Frame 80 debug updates
boundaryBoxWebSocketService.subscribe(
  'frame_80_debug',
  (message) => {
    console.log('🐛 Frame 80 debug:', message.debugData);
  }
);
```

#### Real-time Requests

```typescript
// Request boundary processing
boundaryBoxWebSocketService.requestBoundaryProcessing(
  'video-123',
  80,
  { x: 0, y: 0, width: 100, height: 100 }
);

// Request pedestrian detection
boundaryBoxWebSocketService.requestPedestrianDetection('video-123', 80);

// Request Frame 80 debugging
boundaryBoxWebSocketService.requestFrame80Debug('video-123');
```

## API Endpoints

The API service has been extended with boundary box endpoints that integrate with the Node.js backend system.

### Boundary Box Endpoints

```typescript
import { apiService } from './services/api';

// Validate boundary box
const validation = await apiService.validateBoundingBox(boundingBox, frameSize);

// Process boundary box
const processing = await apiService.processBoundingBox(boundingBox, options);

// Get Frame 80 debug data
const debugData = await apiService.getFrame80DebugData('video-123');

// Fix Frame 80 issues
const fixResult = await apiService.fixFrame80Issues('video-123', 80);

// Update snapping configuration
await apiService.updateSnappingConfig(snappingConfig);

// Calculate accuracy
const accuracy = await apiService.calculateBoundingBoxAccuracy(boundingBox, groundTruth);

// Batch process multiple boxes
const batchResults = await apiService.batchProcessBoundingBoxes(boundingBoxes, options);
```

### Pedestrian Detection Endpoints

```typescript
// Detect pedestrians in frame
const detections = await apiService.detectPedestriansInFrame(
  'video-123',
  80,
  detectionConfig
);

// Detect across frame range
const rangeResults = await apiService.detectPedestriansInFrameRange(
  'video-123',
  75,
  85,
  detectionConfig
);

// Analyze Frame 80
const frame80Analysis = await apiService.analyzeFrame80Pedestrians('video-123');

// Analyze confidence levels
const confidenceAnalysis = await apiService.analyzeConfidenceLevels('track-001');

// Update configuration
await apiService.updatePedestrianDetectionConfig(newConfig);
```

### Backend Integration Endpoints

```typescript
// Direct integration with Node.js boundary detection system
const result = await apiService.callBoundaryDetectionSystem('endpoint', data);

// Validate and process boundary box
const processing = await apiService.validateAndProcessBoundaryBox(boundingBox);

// Check boundary snapping
const snapping = await apiService.checkBoundarySnapping(boundingBox);

// Process pedestrian detection frame
const frameResult = await apiService.processPedestrianDetectionFrame(frameData);

// Get statistics
const stats = await apiService.getBoundaryDetectionStatistics();

// Validate detection
const validation = await apiService.validatePedestrianDetection(detection);
```

## Frame 80 Debugging

Frame 80 has specific issues with pedestrian detection at coordinates "0,0100×100" with 99% confidence. Here's how to debug and fix these issues:

### 1. Analyze Frame 80

```typescript
const analysis = await pedestrianDetectionService.analyzeFrame80('video-123');

console.log('Has detection:', analysis.hasDetection);
console.log('Confidence:', analysis.confidence);
console.log('Coordinates:', analysis.coordinates);
console.log('Issues:', analysis.issues);
console.log('Recommendations:', analysis.recommendations);
```

### 2. Get Debug Data

```typescript
const debugData = await boundaryBoxService.getFrame80DebugData('video-123');

debugData.forEach(debug => {
  console.log('Frame:', debug.frameNumber);
  console.log('Expected coordinates:', debug.expectedCoordinates);
  console.log('Actual coordinates:', debug.actualCoordinates);
  console.log('Has snapping issue:', debug.hasSnappingIssue);
});
```

### 3. Attempt Fix

```typescript
const fixResult = await boundaryBoxService.fixFrame80Issues('video-123', 80);

if (fixResult.success) {
  console.log('✅ Frame 80 fixed:', fixResult.message);
  console.log('Fixed box:', fixResult.fixedBox);
} else {
  console.log('❌ Fix failed:', fixResult.message);
}
```

## Error Handling

All services include comprehensive error handling:

```typescript
try {
  const result = await boundaryBoxService.processBoundingBox(invalidBox);
} catch (error) {
  console.error('Boundary processing failed:', error);
  
  // Services provide graceful fallbacks
  if (error.message.includes('validation')) {
    // Handle validation errors
  } else if (error.message.includes('network')) {
    // Handle network errors
  }
}
```

## Performance Optimization

### Caching

Both services implement intelligent caching:

```typescript
// Clear caches when needed
boundaryBoxService.clearCache();
pedestrianDetectionService.clearHistory();

// Get cache statistics
const stats = boundaryBoxService.getStatistics();
console.log('Cache size:', stats.cacheSize);
```

### Batch Processing

Process multiple frames efficiently:

```typescript
// Process frame range
const results = await boundaryBoxIntegration.processFrameRange(75, 85);

// Batch process boundary boxes
const batchResults = await boundaryBoxService.batchProcess(
  boundingBoxes,
  { enableSnapping: true }
);
```

## Configuration

### Detection Configuration

```typescript
const detectionConfig = {
  confidenceThreshold: 0.8,    // Minimum confidence level
  nmsThreshold: 0.4,           // Non-maximum suppression threshold
  modelName: 'yolov8n',        // YOLO model variant
  targetClasses: [             // Classes to detect
    'person',
    'bicycle', 
    'motorcycle'
  ],
  enableTracking: true,        // Enable object tracking
  trackingPersistence: 5       // Frames to persist tracking
};
```

### Snapping Configuration

```typescript
const snappingConfig = {
  enabled: true,               // Enable snapping
  tolerance: 5,                // Snapping tolerance in pixels
  snapToGrid: false,           // Snap to grid points
  gridSize: 10,                // Grid size in pixels
  snapToEdges: true,           // Snap to frame edges
  snapToCenter: true,          // Snap to center points
  preserveAspectRatio: false   // Maintain aspect ratio when snapping
};
```

### WebSocket Configuration

```typescript
const wsOptions = {
  reconnectInterval: 3000,     // Reconnection delay in ms
  maxReconnectAttempts: 5,     // Maximum reconnection attempts
  heartbeatInterval: 30000,    // Heartbeat interval in ms
  bufferSize: 100             // Message buffer size
};
```

## Statistics and Monitoring

### System Statistics

```typescript
const stats = await boundaryBoxIntegration.getSystemStatistics();

console.log('Boundary box stats:', stats.boundaryBox);
console.log('Pedestrian detection stats:', stats.pedestrianDetection);
console.log('WebSocket stats:', stats.webSocket);
console.log('API integration stats:', stats.apiIntegration);
```

### Service Statistics

```typescript
// Boundary box service statistics
const boundaryStats = boundaryBoxService.getStatistics();

// Pedestrian detection statistics  
const detectionStats = pedestrianDetectionService.getStatistics();

// WebSocket status
const wsStatus = boundaryBoxWebSocketService.getStatus();
```

## Testing

### Unit Testing

```typescript
// Test boundary box validation
describe('BoundaryBoxService', () => {
  test('should validate boundary box correctly', async () => {
    const result = await boundaryBoxService.validateBoundingBox({
      x: 0, y: 0, width: 100, height: 100
    });
    
    expect(result.isValid).toBe(true);
    expect(result.atFrameOrigin).toBe(true);
  });
});
```

### Integration Testing

```typescript
// Test complete system integration
describe('BoundaryBoxIntegration', () => {
  test('should process Frame 80 correctly', async () => {
    await boundaryBoxIntegration.initialize('test-video');
    
    const result = await boundaryBoxIntegration.processFrame(80);
    
    expect(result.frame80Analysis).toBeDefined();
    expect(result.pedestrianDetections.length).toBeGreaterThan(0);
  });
});
```

## Best Practices

1. **Always initialize the system** before processing frames
2. **Use batch processing** for multiple frames to improve performance
3. **Handle Frame 80 specially** as it has known issues
4. **Monitor confidence levels** and validate low-confidence detections
5. **Enable snapping** for boundary boxes at frame origin
6. **Use WebSocket subscriptions** for real-time updates
7. **Cache results** when possible to reduce API calls
8. **Clean up resources** when done to prevent memory leaks

## Troubleshooting

### Common Issues

1. **Frame 80 Detection Issues**
   - Coordinates showing as "0,0100×100"
   - 99% confidence at frame origin
   - Solution: Use `fixFrame80Issues()` method

2. **WebSocket Connection Failures**
   - Network connectivity issues
   - Server not supporting WebSocket
   - Solution: System falls back to HTTP-only mode

3. **Low Detection Confidence**
   - Poor video quality
   - Occlusion or difficult conditions
   - Solution: Adjust confidence threshold or review manually

4. **Snapping Not Working**
   - Snapping disabled in configuration
   - Tolerance too low
   - Solution: Enable snapping and adjust tolerance

### Debug Mode

Enable debug mode for detailed logging:

```typescript
// Check if debug is enabled
import { isDebugEnabled } from '../utils/envConfig';

if (isDebugEnabled()) {
  console.log('Debug mode enabled - detailed logging active');
}
```

## API Reference

See the TypeScript interface definitions in:
- `/src/services/boundaryBoxService.ts` - Core boundary box types
- `/src/services/pedestrianDetectionService.ts` - Pedestrian detection types  
- `/src/services/boundaryBoxWebSocketService.ts` - WebSocket message types

## Backend Integration

This frontend system integrates with the Node.js boundary detection system located at:
- `/src/boundary-detection/detector.js` - Core boundary detection
- `/src/boundary-detection/pedestrian-detection.js` - Pedestrian detection
- `/src/boundary-detection/snap-engine.js` - Snapping functionality

The integration provides a seamless bridge between the frontend React application and the backend Node.js processing system.