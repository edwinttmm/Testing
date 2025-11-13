# Frontend Data Fetching Analysis - HIL Results Pages

**Date**: 2025-10-29
**Analysis Type**: Frontend API Integration & Data Flow
**Focus Areas**: Detection data fetching, data structures, transformation issues

---

## Executive Summary

This analysis examines how the frontend HIL Results and Enhanced Results pages fetch and process detection data, identifying the complete data flow from API calls to component rendering.

### Key Findings

1. **Multiple Data Fetching Paths**: HIL results page uses 4+ different API endpoints to fetch detection data
2. **Complex Data Normalization**: Extensive client-side data transformation and normalization logic
3. **Fallback Strategies**: Multiple fallback mechanisms for missing or incomplete data
4. **Type Structure Mismatch**: Some data transformation issues between backend response and frontend expectations

---

## 1. HILResults Page Data Fetching

### File: `/frontend/src/pages/HILResults.tsx`

#### Primary Data Flow

```typescript
loadHILResults() {
  // Step 1: Fetch enhanced HIL results
  → apiService.getEnhancedHILResultsWithGroundTruth(sessionId)

  // Step 2: Extract detection events from response
  → Extract from multiple possible locations:
     - detection_events
     - detectionEvents
     - combined_detection_events
     - combinedDetectionEvents
     - detection_statistics.detection_events
     - detection_statistics.combined_detection_events

  // Step 3: Fallback - Try session events endpoint
  → apiService.getTestSessionEvents(sessionId, 2000)

  // Step 4: Fallback - Try detection endpoint
  → apiService.getTestSessionDetections(sessionId)

  // Step 5: Load ground truth data
  → apiService.getGroundTruthEvents(videoId)
}
```

#### API Endpoints Used

**Primary Endpoint:**
```typescript
GET /api/enhanced-hil/test-sessions/{sessionId}/ground-truth-comparison
GET /api/enhanced-hil/test-sessions/{sessionId}/corrected-results
```

**Fallback Endpoints:**
```typescript
GET /api/test-sessions/{sessionId}/events?limit=2000&offset=0
GET /api/test-sessions/{sessionId}/detections
GET /api/videos/{videoId}/ground-truth-events
```

#### Detection Event Normalization

The page uses extensive normalization logic to handle inconsistent backend responses:

```typescript
normalizeDetectionEvent(event: any, index: number): EnhancedDetectionEvent {
  // Timestamp extraction from 10+ possible field names
  timestamp = event.video_relative_timestamp
    ?? event.videoRelativeTimestamp
    ?? event.frame_timestamp
    ?? event.timestamp
    ?? event.video_time_seconds
    ?? calculated from frame_number/fps

  // Latency extraction from 8+ possible field names
  realLatency = event.real_latency_ms
    ?? event.latency_ms
    ?? event.actualLatencyMs
    ?? event.detection_latency_ms
    ?? event.apparent_latency_ms
    ?? event.corrected_latency?.real_latency_ms
    ?? event.original_latency?.apparent_latency_ms

  // Voltage extraction from 5+ possible field names
  voltage = event.voltage_level
    ?? event.voltage
    ?? event.signal_value
    ?? event.signalValue
    ?? event.labjack_voltage

  // Result/Pass-Fail determination
  result = event.result ?? event.validation_result
    ?? event.pass_fail ?? event.status
  passed = typeof event.passed === 'boolean'
    ? event.passed
    : result === 'pass' ? true
    : result === 'fail' ? false
    : undefined
}
```

#### Data Structure Issues Identified

**Issue 1: Inconsistent Field Naming**
- Backend sends both snake_case AND camelCase versions of fields
- Frontend must check 10+ variations for each field
- No standardized response schema

**Issue 2: Missing Detection Events**
```typescript
// Detection events may be nested at different levels:
enhancedData.detection_events                     // Level 1
enhancedData.combined_detection_events           // Level 1
enhancedData.detection_statistics.detection_events  // Level 2
enhancedData.detection_statistics.combined_detection_events  // Level 2

// Or scattered throughout the response requiring deep traversal
collectDetectionCandidates(enhancedData)  // Recursive search
```

**Issue 3: Multi-Video Sequence Complexity**
```typescript
// Detections may be:
// 1. Combined in single array
// 2. Grouped by video_id field
// 3. Sliced by detection count
// 4. Distributed evenly across videos

// Complex logic to distribute detections to videos:
sortedPerVideo.forEach((video, index) => {
  const expected = video.detectionCount ?? video.detection_count;
  let sliceEnd = pointer + expected;

  if (expected === 0) {
    // Fallback: distribute evenly
    const autoSize = Math.floor(remainingDetections / remainingVideos);
    sliceEnd = pointer + autoSize;
  }

  detectionMap[video.id] = allDetections.slice(pointer, sliceEnd);
  pointer = sliceEnd;
});
```

---

## 2. EnhancedResults Page Data Fetching

### File: `/frontend/src/pages/EnhancedResults.tsx`

#### Primary Data Flow

```typescript
loadSessionData(sessionId: string) {
  // Step 1: Load session metadata
  → apiService.getTestSession(sessionId)

  // Step 2: Load enhanced test execution data
  → apiService.get('/api/enhanced-test-sessions/{sessionId}')

  // Step 3: Load comparison data (if completed)
  → apiService.get('/api/enhanced-test-sessions/{sessionId}/comparison')

  // Step 4: Load validation data based on type
  if (validationType === 'labjack') {
    → loadLatencyValidation(sessionId)
  } else {
    → loadStatisticalValidation(sessionId)
  }

  // Step 5: Load detailed results
  → apiService.get('/api/enhanced-test-sessions/{sessionId}/detailed-results')
}
```

#### Latency Validation Loading (LabJack)

```typescript
loadLatencyValidation(sessionId: string) {
  // Primary endpoint
  → GET /api/enhanced-test-sessions/{sessionId}/latency-validation

  // Fallback: Load HIL session results
  → GET /api/test-sessions/{sessionId}/results
  → GET /api/test-sessions/{sessionId}/events  // ← CRITICAL: Gets actual detections

  // Transform HIL data to LatencyValidationResult format
  const detectionEvents = await apiService.get('/api/test-sessions/{sessionId}/events');
  console.log('🔍 Enhanced Results fetched detection events:', detectionEvents.length);

  // Build latency validation result from raw detection events
  latencyValidationResults = {
    detection_events: detectionEvents.map(evt => ({
      id: evt.id,
      detection_time_ms: evt.latency_ms ?? evt.actual_latency_ms,  // ← Uses latency
      voltage: evt.voltage,  // ← Voltage preserved
      channel: evt.channel,
      passed: true,
      timestamp: evt.timestamp,
      frame_number: evt.video_frame
    }))
  };
}
```

**Key Fix Applied (Lines 351-370):**
- Previously used `evt.voltage` for `detection_time_ms` field (BUG)
- Now correctly uses `evt.latency_ms` or `evt.actual_latency_ms`
- Keeps voltage in the `voltage` field where it belongs

---

## 3. API Service Implementation

### File: `/frontend/src/services/api.ts`

#### Detection-Related Methods

```typescript
class ApiService {
  // Method 1: Get enhanced HIL results
  async getEnhancedHILResults(sessionId: string): Promise<any> {
    const response = await this.api.get(
      `/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`
    );
    return response.data;
  }

  // Method 2: Get enhanced HIL results with ground truth
  async getEnhancedHILResultsWithGroundTruth(sessionId: string): Promise<any> {
    const response = await this.api.get(
      `/api/enhanced-hil/test-sessions/${sessionId}/ground-truth-comparison`
    );
    return response.data;
  }

  // Method 3: Get test session detections
  async getTestSessionDetections(sessionId: string): Promise<Record<string, unknown>[]> {
    const response = await this.api.get(`/api/test-sessions/${sessionId}/detections`);
    return response.data.detections || [];
  }

  // Method 4: Get test session events (paginated)
  async getTestSessionEvents(
    sessionId: string,
    limit: number = 1000,
    offset: number = 0
  ): Promise<Record<string, unknown>[]> {
    const response = await this.api.get(`/api/test-sessions/${sessionId}/events`, {
      params: { limit, offset }
    });
    return response.data.events || [];
  }

  // Method 5: Get ground truth events for a video
  async getGroundTruthEvents(videoId: string): Promise<any> {
    const response = await this.api.get(`/api/videos/${videoId}/ground-truth-events`);
    return {
      success: true,
      data: {
        ground_truth_events: response.data.data?.ground_truth_events
          ?? response.data.ground_truth_events
          ?? []
      }
    };
  }
}
```

#### Response Data Transformation

```typescript
// Minimal transformation applied by interceptor
private transformResponseData(data: unknown): unknown {
  // Backend uses camelCase serializers
  // Only minimal transformation for backward compatibility

  if (Array.isArray(data)) {
    return data.map(item => this.transformResponseData(item));
  }

  if (isObject(data)) {
    const transformed = { ...data };

    // Handle remaining snake_case fields
    if ('created_at' in data && !('createdAt' in data)) {
      transformed.createdAt = data.created_at;
      delete transformed.created_at;
    }

    return transformed;
  }

  return data;
}
```

---

## 4. T3 Service Integration

### File: `/frontend/src/services/t3Service.ts`

This service provides T3 YOLO detection capabilities but is **NOT** used by HIL results pages:

```typescript
// T3 Service methods (not relevant to HIL results pages)
async function startT3Session(sessionId, videoPath, videoId);
async function getT3Stats(sessionId);
async function getT3Alerts(sessionId);
function openT3WebSocket(sessionId);
```

**Note:** T3 service is for real-time object detection, not timing validation.

---

## 5. WebSocket Service Integration

### File: `/frontend/src/services/websocketService.ts`

#### Socket.IO Connection Management

```typescript
class WebSocketService {
  // WebSocket URL resolution
  getWebSocketUrl() {
    return getConfigValueSync('REACT_APP_SOCKETIO_URL', '')
      || getConfigValueSync('REACT_APP_WS_URL', '')
      || `http://${hostname}:8000`;  // Backend API port
  }

  // Event subscription for real-time updates
  subscribe<T>(eventType: string, callback: (data: T) => void) {
    this.socket.on(eventType, callback);
  }

  // Emit messages to server
  emit<T>(eventType: string, data?: T) {
    this.socket.emit(eventType, data);
  }

  // Sequence subscription for multi-video testing
  subscribeToSequence(sequenceId: string) {
    this.emit('subscribe_sequence', { sequence_id: sequenceId });

    return {
      onVideoTransition: (callback) => this.subscribe('video_transition', callback),
      onVideoCompleted: (callback) => this.subscribe('video_completed', callback),
      onSequenceCompleted: (callback) => this.subscribe('sequence_completed', callback)
    };
  }
}
```

#### WebSocket Events Used by Results Pages

**HILResults Page:**
- Does NOT use WebSocket (loads static results only)

**EnhancedResults Page:**
```typescript
// Real-time update subscription
useEffect(() => {
  if (pageState.realtimeUpdates && pageState.selectedSession) {
    const unsubscribe = realTimeResultsService.subscribe(
      pageState.selectedSession,
      handleRealTimeUpdate
    );
  }
}, [pageState.realtimeUpdates, pageState.selectedSession]);

// Update handlers
handleRealTimeUpdate(update: RealTimeUpdate) {
  switch (update.updateType) {
    case 'frame_processed':
      // Update current frame
    case 'metrics_updated':
      // Update running metrics
    case 'anomaly_detected':
      // Display anomaly warning
    case 'completed':
      // Load final results
  }
}
```

---

## 6. Type Definitions

### File: `/frontend/src/types/enhanced-results.ts`

#### Core Detection Event Types

```typescript
// LabJack timing validation event
export interface DetectionLatencyEvent {
  id: string;
  timestamp: number;
  frame_number: number;
  detection_time_ms: number;  // ← SHOULD be latency value
  processing_latency_ms?: number;
  labJack_trigger_time_ms: number;
  passed: boolean;
  error_message?: string;

  // Failure snapshot fields
  screenshot_path?: string;
  screenshot_zoom_path?: string;
  failure_reason?: string;
  failure_type?: 'timing' | 'accuracy' | 'detection' | 'system' | 'voltage' | 'none';

  // Ground truth integration
  voltage?: number;  // ← Voltage should be separate
  channel?: string;
  actual_latency_ms?: string;
}

// Enhanced detection event with all variations
export interface EnhancedDetectionEvent extends DetectionLatencyEvent {
  // Enhanced timing fields
  real_latency_ms?: number;
  apparent_latency_ms?: number;
  timing_quality?: 'excellent' | 'good' | 'fair' | 'poor';
  confidence_score?: number;
  processing_time_ms?: number;

  // Ground truth matching
  ground_truth_match_id?: string;
  ground_truth_available?: boolean;
  match_distance_pixels?: number;
  match_iou_score?: number;

  // Video context
  video_frame?: number;
  voltage?: number;
  labjack_voltage?: number;
  channel?: string;

  // Measured breakdown
  measured_breakdown?: {
    system_processing_ms: number | string;
    frame_timing_variance_ms: number;
    initial_startup_effect_ms: number;
    camera_processing_note: string;
    total_measured_latency_ms: number;
    measurement_source: string;
    measurement_method: string;
  };
}
```

#### Enhanced HIL Results Type

```typescript
export interface EnhancedHILResults {
  session_id: string;
  hardware_status: {
    labjack_connected: boolean;
    model: string;
    firmware_version?: string;
  };
  video_timing: {
    startup_delay_ms: number;
    timing_sync_status: string;
    fps?: number;
    duration?: number;
    filename?: string;
  };
  detection_statistics: {
    total_detections: number;
    original_results: {
      average_apparent_latency_ms: number;
      passed_detections: number;
      failed_detections: number;
      pass_rate: number;
    };
    corrected_results: {
      average_real_latency_ms: number;
      median_real_latency_ms: number;
      passed_detections: number;
      failed_detections: number;
      pass_rate: number;
    };
  };
  ground_truth_comparison?: {
    ground_truth_events_available: number;
    total_detections: number;
    events_with_matches: number;
    average_confidence_score: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
    true_positives?: number;
    false_positives?: number;
    false_negatives?: number;
  };
  detection_events: Array<{
    event_id: string;
    detection_time: string;
    labjack_trigger_time: string;
    frame_number: number;
    threshold_ms: number;
    result: 'pass' | 'fail';
    voltage_level: number;
    corrected_latency?: {
      real_latency_ms: number;
    };
    timing_synchronization?: {
      timing_quality: 'excellent' | 'good' | 'fair' | 'poor';
      confidence_score: number;
      ground_truth_available: boolean;
    };
  }>;
}
```

#### Multi-Video Sequence Types

```typescript
export interface VideoSequenceResults {
  sequence_id?: string;
  sequenceId?: string;
  total_videos?: number;
  overall_pass_rate?: number;
  combined_detection_events?: EnhancedDetectionEvent[];
  per_video_results?: PerVideoResult[];
  aggregate_metrics?: Record<string, unknown>;
}

export interface PerVideoResult {
  video_id?: string;
  videoId?: string;
  video_name?: string;
  status?: 'pass' | 'fail';
  detection_count?: number;
  detection_events?: EnhancedDetectionEvent[];
  pass_rate?: number;
  average_latency_ms?: number;
}
```

---

## 7. Data Transformation Issues

### Issue 1: Voltage vs Latency Field Confusion

**Problem:**
```typescript
// INCORRECT (EnhancedResults.tsx lines 351-370 - BEFORE FIX)
detection_time_ms: evt.voltage || 0  // ❌ Using voltage for latency field!

// CORRECT (AFTER FIX)
detection_time_ms: evt.latency_ms ?? evt.actual_latency_ms ?? 0  // ✅ Using latency
voltage: evt.voltage || 0  // ✅ Voltage in correct field
```

**Impact:**
- Detection time displayed as voltage values (4.2V instead of 50ms)
- Latency statistics completely wrong
- Average latency showing voltage average instead

### Issue 2: Inconsistent Field Names Across Endpoints

**Backend Sends Multiple Variations:**
```typescript
// Timestamp field variations
timestamp
video_relative_timestamp
videoRelativeTimestamp
frame_timestamp
video_time_seconds

// Latency field variations
real_latency_ms
latency_ms
actualLatencyMs
detection_latency_ms
apparent_latency_ms
detection_time_ms
processing_time_ms

// Voltage field variations
voltage
voltage_level
signal_value
signalValue
labjack_voltage
```

**Frontend Must Check All Variations:**
```typescript
// Frontend normalization checking 10+ field variations per property
const timestamp = event.video_relative_timestamp
  ?? event.videoRelativeTimestamp
  ?? event.frame_timestamp
  ?? event.timestamp
  ?? event.video_time_seconds
  ?? (event.frame_number / (event.fps ?? 24));
```

### Issue 3: Missing Detection Events in Response

**Problem:**
- Detection events may be at different nesting levels
- May be split across multiple response fields
- May require deep recursive search

**Solution:**
```typescript
// HILResults.tsx uses multi-level extraction
const detectionCandidates: any[] = [];

// Level 1: Direct arrays
addCandidateEvents(enhancedData.detection_events);
addCandidateEvents(enhancedData.detectionEvents);
addCandidateEvents(enhancedData.combined_detection_events);

// Level 2: Nested in statistics
addCandidateEvents(enhancedData.detection_statistics?.detection_events);
addCandidateEvents(enhancedData.detection_statistics?.combined_detection_events);

// Level 3: Deep recursive search
addCandidateEvents(collectDetectionCandidates(enhancedData));

// Fallback: Additional API calls
if (detectionCandidates.length === 0) {
  const events = await apiService.getTestSessionEvents(sessionId, 2000);
  const detections = await apiService.getTestSessionDetections(sessionId);
}
```

### Issue 4: Multi-Video Detection Distribution

**Problem:**
- Combined detection events need to be split per video
- Detection counts may not match
- Video order may not be preserved

**Current Algorithm:**
```typescript
// Distribute detections to videos by slicing
let pointer = 0;
sortedPerVideo.forEach((video, index) => {
  const expected = video.detection_count ?? 0;

  if (expected === 0) {
    // Auto-distribute evenly
    const autoSize = Math.floor(remainingDetections / remainingVideos);
    detectionMap[video.id] = allDetections.slice(pointer, pointer + autoSize);
  } else {
    // Use expected count
    detectionMap[video.id] = allDetections.slice(pointer, pointer + expected);
  }

  pointer += expected || autoSize;
});
```

**Issues:**
- Assumes sequential ordering
- Doesn't handle video_id field in detection events
- May cut detections in middle of video

---

## 8. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      HILResults Page                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  apiService.getEnhancedHILResultsWithGroundTruth()  │
        └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │  GET /api/enhanced-hil/test-sessions/{id}/   │
        │      ground-truth-comparison                  │
        └─────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │ detection_events │        │ detection_       │
    │                  │        │ statistics       │
    └──────────────────┘        └──────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              ▼
            ┌────────────────────────────────┐
            │ normalizeDetectionEvents()     │
            │ - Extract timestamp            │
            │ - Extract latency              │
            │ - Extract voltage              │
            │ - Determine pass/fail          │
            └────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │ detections.length === 0?      │
              └───────────────┬───────────────┘
                     YES      │      NO
                              │       │
                              ▼       └────────────────┐
            ┌─────────────────────────┐                │
            │ FALLBACK 1:             │                │
            │ getTestSessionEvents()  │                │
            └─────────────────────────┘                │
                              │                        │
                detections.length === 0?               │
                              │                        │
                         YES  ▼   NO                   │
            ┌─────────────────────────┐                │
            │ FALLBACK 2:             │                │
            │ getTestSessionDetections│                │
            └─────────────────────────┘                │
                              │                        │
                              └────────┬───────────────┘
                                       ▼
                        ┌───────────────────────────┐
                        │ Multi-Video Sequence?     │
                        └───────────────────────────┘
                                       │
                            ┌──────────┴──────────┐
                           YES                   NO
                            │                     │
                            ▼                     ▼
                ┌──────────────────────┐  ┌──────────────┐
                │ Distribute detections│  │ Use all      │
                │ across videos         │  │ detections   │
                └──────────────────────┘  └──────────────┘
                            │                     │
                            └──────────┬──────────┘
                                       ▼
                        ┌───────────────────────────┐
                        │ Load Ground Truth Events   │
                        │ getGroundTruthEvents()     │
                        └───────────────────────────┘
                                       │
                                       ▼
                        ┌───────────────────────────┐
                        │ Render Detection Table     │
                        │ - Time                     │
                        │ - Voltage                  │
                        │ - Latency                  │
                        │ - Pass/Fail                │
                        └───────────────────────────┘
```

---

## 9. Recommendations

### Immediate Fixes Required

1. **Standardize Backend Response Schema**
   - Use consistent field naming (prefer camelCase throughout)
   - Always include detection_events at top level
   - Document exact response structure per endpoint

2. **Fix Field Name Mapping**
   ```typescript
   // Backend should always send:
   {
     detection_events: [{
       id: string,
       timestamp: number,          // ← ONE standard field
       latency_ms: number,         // ← ONE standard field
       voltage: number,            // ← ONE standard field
       result: 'pass' | 'fail'    // ← ONE standard field
     }]
   }
   ```

3. **Remove Frontend Normalization**
   - Once backend is standardized, remove 90% of normalization code
   - Keep only backward compatibility for old sessions

4. **Add Response Validation**
   ```typescript
   // Add Zod schema validation
   const DetectionEventSchema = z.object({
     id: z.string(),
     timestamp: z.number(),
     latency_ms: z.number(),
     voltage: z.number(),
     result: z.enum(['pass', 'fail'])
   });

   // Validate response
   const validated = DetectionEventSchema.array().parse(response.data);
   ```

### Data Structure Improvements

1. **Consistent Multi-Video Format**
   ```typescript
   {
     sequence_id: string,
     per_video_results: [{
       video_id: string,
       video_order: number,
       detection_events: [...],  // ← Detections for THIS video only
       metrics: {...}
     }]
   }
   ```

2. **Always Include Video ID in Detection Events**
   ```typescript
   {
     id: string,
     video_id: string,  // ← ALWAYS include for multi-video support
     timestamp: number,
     // ... other fields
   }
   ```

3. **Separate Timing and Validation Data**
   ```typescript
   {
     detection_events: [...],      // Raw timing data
     validation_results: [...],    // Pass/fail assessment
     ground_truth_comparison: {...}  // Comparison metrics
   }
   ```

### Frontend Improvements

1. **Create Adapter Layer**
   ```typescript
   // adapters/detectionEventAdapter.ts
   export function adaptDetectionEvent(raw: any): DetectionEvent {
     return {
       id: raw.id,
       timestamp: raw.timestamp,
       latency_ms: raw.latency_ms,
       voltage: raw.voltage,
       result: raw.result
     };
   }
   ```

2. **Use React Query for Data Fetching**
   ```typescript
   const { data, error, isLoading } = useQuery({
     queryKey: ['hil-results', sessionId],
     queryFn: () => apiService.getEnhancedHILResults(sessionId),
     select: (data) => adaptDetectionEvents(data.detection_events)
   });
   ```

3. **Add Error Boundaries**
   ```typescript
   <ErrorBoundary fallback={<DetectionLoadError />}>
     <DetectionTable detections={detections} />
   </ErrorBoundary>
   ```

---

## 10. Testing Requirements

### Unit Tests Needed

1. **Detection Event Normalization**
   ```typescript
   describe('normalizeDetectionEvent', () => {
     it('should extract timestamp from video_relative_timestamp', () => {
       const event = { video_relative_timestamp: 1.5 };
       const result = normalizeDetectionEvent(event, 0);
       expect(result.timestamp).toBe(1.5);
     });

     it('should correctly map latency_ms field', () => {
       const event = { latency_ms: 50 };
       const result = normalizeDetectionEvent(event, 0);
       expect(result.real_latency_ms).toBe(50);
     });
   });
   ```

2. **Multi-Video Distribution**
   ```typescript
   describe('distributeDetectionsToVideos', () => {
     it('should distribute detections evenly when counts missing', () => {
       const detections = [/* 10 detections */];
       const videos = [{ id: 'v1' }, { id: 'v2' }];
       const result = distributeDetections(detections, videos);
       expect(result.v1.length).toBe(5);
       expect(result.v2.length).toBe(5);
     });
   });
   ```

### Integration Tests Needed

1. **Complete Data Flow Test**
   ```typescript
   test('HILResults page loads and displays detections', async () => {
     // Mock API responses
     mockApi.getEnhancedHILResults.mockResolvedValue(mockResults);

     // Render page
     render(<HILResults />);

     // Wait for data load
     await waitFor(() => {
       expect(screen.getByText('Detection Events')).toBeInTheDocument();
     });

     // Verify detections displayed
     expect(screen.getByText('50ms')).toBeInTheDocument(); // latency
     expect(screen.getByText('4.2V')).toBeInTheDocument(); // voltage
   });
   ```

2. **Fallback Path Test**
   ```typescript
   test('Falls back to events endpoint when detection_events missing', async () => {
     // Mock primary endpoint with no detections
     mockApi.getEnhancedHILResults.mockResolvedValue({ detection_events: [] });

     // Mock fallback endpoint
     mockApi.getTestSessionEvents.mockResolvedValue([/* events */]);

     render(<HILResults />);

     await waitFor(() => {
       expect(mockApi.getTestSessionEvents).toHaveBeenCalled();
     });
   });
   ```

---

## 11. Summary of Critical Issues

### High Priority

1. **Voltage/Latency Field Mix-up** ✅ FIXED
   - EnhancedResults.tsx was using voltage for detection_time_ms
   - Now correctly uses latency_ms field

2. **Inconsistent Field Naming** ⚠️ ONGOING
   - Backend sends 10+ variations per field
   - Frontend must check all variations
   - Needs backend standardization

3. **Missing Detection Events** ⚠️ ONGOING
   - Events may be at multiple nesting levels
   - Requires recursive search + multiple fallbacks
   - Needs guaranteed top-level array

### Medium Priority

4. **Multi-Video Distribution Logic**
   - Complex slicing algorithm
   - Doesn't use video_id field
   - May split detections incorrectly

5. **No Response Validation**
   - No schema validation
   - Runtime type errors possible
   - Silent data corruption

### Low Priority

6. **Excessive Client-Side Normalization**
   - 300+ lines of normalization code
   - Could be eliminated with proper backend schema

7. **Missing Error Handling**
   - No error boundaries
   - Failed API calls may crash page
   - Poor user experience

---

## Conclusion

The frontend data fetching for HIL results pages is complex due to:

1. Multiple API endpoints with different response structures
2. Inconsistent field naming between endpoints
3. Complex multi-video detection distribution logic
4. Extensive client-side data normalization

The critical voltage/latency field bug has been identified and fixed in EnhancedResults.tsx. However, the underlying issue of inconsistent backend responses remains and should be addressed through backend API standardization.

**Next Steps:**
1. Review backend API response schemas
2. Standardize detection event structure
3. Add response validation
4. Reduce frontend normalization complexity
5. Add comprehensive tests

---

**Document Version**: 1.0
**Last Updated**: 2025-10-29
**Author**: Code Analysis Agent
