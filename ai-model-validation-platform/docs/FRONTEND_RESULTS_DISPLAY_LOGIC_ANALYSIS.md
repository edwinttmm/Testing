# Frontend Results Display Logic - Comprehensive Analysis

**Date**: 2025-11-11
**Purpose**: Document frontend pass/fail determination logic and user display flow
**Scope**: HIL Results, Enhanced Results, Metrics Cards, Ground Truth Comparison

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Main Results Pages](#main-results-pages)
3. [Pass/Fail Determination Logic](#passfail-determination-logic)
4. [Metrics Display Components](#metrics-display-components)
5. [Data Flow Architecture](#data-flow-architecture)
6. [Type System & Data Contracts](#type-system--data-contracts)
7. [User Approval Workflow](#user-approval-workflow)
8. [Key Findings & Issues](#key-findings--issues)

---

## Executive Summary

### Architecture Overview
The frontend results display system consists of two main pages:
- **HILResults.tsx** - Primary results page for Hardware-in-Loop tests (1944 lines)
- **EnhancedResults.tsx** - Advanced analytics page with validation tabs (1194 lines)

### Pass/Fail Philosophy
The system uses **dual validation models**:
1. **LabJack Timing Validation** - Pass rate based on latency thresholds
2. **AI Ground Truth Validation** - Precision/Recall/F1 Score metrics

### Critical Data Sources
All pass/fail determinations are derived from **backend API responses**:
- `/api/enhanced-test-sessions/{sessionId}` - Session results with ground truth comparison
- `/api/test-sessions/{sessionId}/events` - Detection events
- `/api/ground-truth/{videoId}` - Ground truth events
- `/api/video-sequence-results/{sequenceId}` - Multi-video sequence results

---

## Main Results Pages

### 1. HILResults.tsx (Primary Results Page)

**File Location**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`

#### Key Features
- Single/multi-video test results display
- Ground truth comparison with F1 Score, Precision, Recall
- Real-time WebSocket updates
- Detection timeline visualization
- Per-video result breakdown
- Video playback dialog with detection timestamps

#### State Management (Lines 229-246)
```typescript
const [enhancedResults, setEnhancedResults] = useState<EnhancedHILResults | null>(null);
const [sequenceResults, setSequenceResults] = useState<VideoSequenceResults | null>(null);
const [isSequence, setIsSequence] = useState(false);
const [groundTruthEvents, setGroundTruthEvents] = useState<any[]>([]);
const [videoId, setVideoId] = useState<string | null>(null);
const [baseDetections, setBaseDetections] = useState<EnhancedDetectionEvent[]>([]);
const [perVideoSummaries, setPerVideoSummaries] = useState<PerVideoResult[]>([]);
const [videoDetectionMap, setVideoDetectionMap] = useState<Record<string, EnhancedDetectionEvent[]>>({});
const [videoGroundTruthMap, setVideoGroundTruthMap] = useState<Record<string, any[]>>({});
const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
```

#### Data Loading Flow (Lines 577-900)
```typescript
// 1. Load session data and determine if multi-video sequence
const loadHILResults = useCallback(async () => {
  // Load enhanced results with ground truth comparison
  enhancedData = await apiService.getEnhancedHILResultsWithGroundTruth(sessionId);

  // Check if multi-video sequence
  const hasSequence = Boolean(session?.hasVideoSequence ?? session?.has_video_sequence);

  if (hasSequence && detectedSequenceId) {
    // Load sequence results from backend
    const seqResults = await apiService.getVideoSequenceResults(detectedSequenceId);
    setSequenceResults(effectiveSeqResults);

    // CRITICAL: Preload ALL detections for aggregated metrics
    const loadPromises = sortedPerVideo.map(async (video) => {
      // Load detections for each video
      const detResponse = await apiService.getDetectionEvents(sessionId, videoId);
      detectionMap[videoId] = detections;

      // Load ground truth for each video
      const gtResponse = await apiService.getGroundTruthEvents(videoId);
      groundTruthMap[videoId] = dedupedEvents;
    });

    await Promise.all(loadPromises);
  }
}, [sessionId, loadGroundTruthData]);
```

---

## Pass/Fail Determination Logic

### 1. Overall Test Status (Lines 1281-1288)

**Primary Logic**:
```typescript
// CRITICAL: Pass/fail based on failed detection count
const testPassed = overallFailedDetections === 0;

// Criteria text shown to user
const criteriaBaseText = latencyThresholdMs
  ? `Pass if corrected latency ≤ ${latencyThresholdMs}ms`
  : 'Pass if all detections meet latency tolerance';

const criteriaText = overallFailedDetections > 0
  ? `${criteriaBaseText} • ${overallFailedDetections} detection(s) exceeded the limit`
  : criteriaBaseText;
```

**Data Source** (Lines 1232-1238):
```typescript
// Backend provides corrected results
const overallCorrectedStats = enhancedResults?.detection_statistics?.corrected_results;
const overallPassedDetections = overallCorrectedStats?.passed_detections ?? allDetections.filter(d => d?.passed || d?.result === 'pass').length;
const overallFailedDetections = overallCorrectedStats?.failed_detections ?? Math.max(0, overallDetectionCount - overallPassedDetections);
const overallPassRate = sequenceResults?.overallPassRate
  ?? sequenceResults?.overall_pass_rate
  ?? overallCorrectedStats?.pass_rate
  ?? (overallDetectionCount > 0 ? (overallPassedDetections / overallDetectionCount) * 100 : 0);
```

### 2. Ground Truth Metrics (Lines 1238-1273)

**CRITICAL BACKEND DEPENDENCY**:
```typescript
// Backend calculates TP/FP/FN from ground truth matching
const gtComparison = enhancedResults?.ground_truth_comparison;
const hasGroundTruth = Boolean(gtComparison && gtComparison.ground_truth_events_available > 0);

console.log('[HILResults] Single video ground truth comparison from backend:', gtComparison);

const precision = gtComparison?.precision ?? 0;
const recall = gtComparison?.recall ?? 0;
const f1Score = gtComparison?.f1_score ?? 0;
const truePositives = gtComparison?.true_positives ?? 0;
const falsePositives = gtComparison?.false_positives ?? 0;
const falseNegatives = gtComparison?.false_negatives ?? 0;
```

**⚠️ DEPRECATED FRONTEND CALCULATION** (Lines 106-188):
```typescript
/**
 * @deprecated - DO NOT USE FOR GROUND TRUTH METRICS
 *
 * This function recalculates ground truth metrics from frontend detection data,
 * which is WRONG because:
 * 1. It uses validation_result = "PASS"/"FAIL" field (test result, not ground truth match)
 * 2. Backend already provides correct ground_truth_comparison with proper TP/FP/FN
 * 3. Frontend recalculation produces incorrect metrics (0% recall instead of 11.5%)
 */
const createMetricsFromDetections = (
  detections: any[] = [],
  groundTruthEvents: any[] = []
) => {
  console.warn('⚠️ DEPRECATED: createMetricsFromDetections() should not be used...');
  // ... legacy logic ...
};
```

### 3. Multi-Video Aggregation (Lines 998-1121)

**Aggregated Metrics Calculation**:
```typescript
const aggregatedMetrics = useMemo(() => {
  if (!isSequence) return null;

  const videos = effectivePerVideoSummaries;

  // CRITICAL: Aggregate from backend's ground_truth_comparison
  const totalTP = videos.reduce((sum, v) => {
    const gtComp = v.ground_truth_comparison ?? v.groundTruthComparison;
    return sum + toNumber(gtComp.true_positives ?? gtComp.truePositives ?? 0);
  }, 0);

  const totalFP = videos.reduce((sum, v) => {
    const gtComp = v.ground_truth_comparison ?? v.groundTruthComparison;
    return sum + toNumber(gtComp.false_positives ?? gtComp.falsePositives ?? 0);
  }, 0);

  const totalFN = videos.reduce((sum, v) => {
    const gtComp = v.ground_truth_comparison ?? v.groundTruthComparison;
    return sum + toNumber(gtComp.false_negatives ?? gtComp.falseNegatives ?? 0);
  }, 0);

  console.log(`[aggregatedMetrics] ✅ AGGREGATED: TP=${totalTP}, FP=${totalFP}, FN=${totalFN}`);

  // Calculate aggregated precision, recall, F1
  const aggregatedPrecision = (totalTP + totalFP) > 0 ? (totalTP / (totalTP + totalFP)) * 100 : 0;
  const aggregatedRecall = (totalTP + totalFN) > 0 ? (totalTP / (totalTP + totalFN)) * 100 : 0;
  const aggregatedF1 = (aggregatedPrecision + aggregatedRecall) > 0
    ? (2 * (aggregatedPrecision * aggregatedRecall) / (aggregatedPrecision + aggregatedRecall))
    : 0;

  return { aggregatedF1Score, aggregatedPrecision, aggregatedRecall, totalTP, totalFP, totalFN, ... };
}, [isSequence, sequenceResults, perVideoSummaries, videoDetectionMap, videoGroundTruthMap]);
```

### 4. Per-Video Status (Lines 1298-1340)

**Video Tab Status**:
```typescript
const videoTabs = useMemo(() => {
  return effectivePerVideoSummaries.map((video, index) => {
    // Normalize status field from backend
    const statusRaw = (video.passFail ?? video.pass_fail ?? video.status ?? '') as string;
    const normalizedStatus = typeof statusRaw === 'string' ? statusRaw.toLowerCase() : '';

    // Determine pass/fail/pending
    const status: 'pass' | 'fail' | 'pending' =
      normalizedStatus === 'pass' ? 'pass' :
      normalizedStatus === 'fail' ? 'fail' : 'pending';

    return { id, name, detectionCount, status };
  });
}, [isSequence, effectivePerVideoSummaries, videoDetectionMap]);
```

---

## Metrics Display Components

### 1. TestStatusBanner (Lines 1505-1520)

**Component**: `<TestStatusBanner />`

**Props**:
```typescript
<TestStatusBanner
  passed={testPassed}                     // Boolean: overallFailedDetections === 0
  detectionCount={overallDetectionCount}  // Total detections
  expectedCount={overallExpectedCount}    // Ground truth count OR detection count
  matchRate={overallMatchRate}            // Precision from backend
  passRate={overallPassRate}              // Pass rate from backend
  failedCount={overallFailedDetections}   // Failed detections from backend
  latencyThresholdMs={latencyThresholdMs} // Threshold from backend config
  criteriaText={criteriaText}             // Human-readable pass/fail criteria
  videoCount={isSequence ? effectivePerVideoSummaries.length : undefined}
  videosPassedCount={isSequence ? videosPassedCount : undefined}
/>
```

**Display Logic**:
- Shows large **PASS** or **FAIL** banner at top of results
- Green banner if `passed=true`, red if `passed=false`
- Displays detection count, pass rate, match rate
- For multi-video: Shows "X/Y videos passed"

### 2. GroundTruthComparisonCards (Lines 1623-1633)

**Component**: `<GroundTruthComparisonCards />`

**Props** (Single Video):
```typescript
<GroundTruthComparisonCards
  precision={precision}                // From backend gtComparison
  recall={recall}                      // From backend gtComparison
  f1Score={f1Score}                    // From backend gtComparison
  truePositives={truePositives}        // From backend gtComparison
  falsePositives={falsePositives}      // From backend gtComparison
  falseNegatives={falseNegatives}      // From backend gtComparison
  totalGroundTruth={totalGroundTruth}  // From backend gtComparison
/>
```

**Props** (Multi-Video Aggregated):
```typescript
<GroundTruthComparisonCards
  precision={aggregatedPrecision}      // Calculated from per-video TP/FP
  recall={aggregatedRecall}            // Calculated from per-video TP/FN
  f1Score={aggregatedF1Score}          // Calculated from aggregated P/R
  truePositives={totalTruePositives}   // Sum of per-video TP
  falsePositives={totalFalsePositives} // Sum of per-video FP
  falseNegatives={totalFalseNegatives} // Sum of per-video FN
  title="Aggregated Across All Videos"
/>
```

**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/GroundTruthComparisonCards.tsx`

**Display Logic** (Lines 31-89):
```typescript
// F1 Score quality assessment
const getF1Quality = (score: number) => {
  if (score >= 90) return { label: 'Excellent', color: 'success.main', bgColor: 'success.light' };
  if (score >= 80) return { label: 'Good', color: 'warning.main', bgColor: 'warning.light' };
  return { label: 'Needs Improvement', color: 'error.main', bgColor: 'error.light' };
};

// Visual hierarchy: F1 Score > Precision > Recall
// F1 Score card has elevation={4} and colored border
// Precision/Recall cards have elevation={4}
// Confusion matrix summary at bottom with TP/FP/FN breakdown
```

### 3. MetricsSummaryCards (Lines 1636-1649)

**Component**: `<MetricsSummaryCards />`

**File**: `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/MetricsSummaryCards.tsx`

**Props**:
```typescript
<MetricsSummaryCards
  detections={activeDetectionCount}    // Detections for selected video
  expected={activeExpectedCount}       // Ground truth count
  avgLatency={activeAvgLatency}        // Calculated from detection events
  matchRate={activeMatchRate}          // Percentage of matched detections
  hardwareStatus={hardwareStatus}      // LabJack connection status
  detectionLatency={detectionLatency}  // Backend corrected latency
  videoStartupDelay={videoStartupDelay} // System startup delay (separate from detection latency)
/>
```

**Display Logic** (Lines 32-175):
```typescript
// 5 cards: Detections, Detection Latency (PROMINENT), Video Startup, Match Rate, Hardware
const displayLatency = detectionLatency !== undefined ? detectionLatency : avgLatency;

const getLatencyQuality = (latency: number) => {
  if (latency < 50) return { label: 'Excellent', color: 'success.main' };
  if (latency < 100) return { label: 'Good', color: 'warning.main' };
  return { label: 'Needs Improvement', color: 'error.main' };
};

// Detection Latency card has:
// - elevation={3} (highest)
// - border: 2px primary color
// - fontWeight: bold on title
// - Color-coded progress bar based on latency quality
```

---

## Data Flow Architecture

### 1. Data Fetching Hierarchy

```
loadHILResults()
  ├── getEnhancedHILResultsWithGroundTruth(sessionId)
  │     └── Returns: EnhancedHILResults with ground_truth_comparison
  │
  ├── getTestSession(sessionId)
  │     └── Returns: Session metadata, hasVideoSequence flag
  │
  ├── IF hasVideoSequence:
  │   └── getVideoSequenceResults(sequenceId)
  │         ├── Returns: VideoSequenceResults
  │         │     ├── per_video_results[] (PerVideoResult)
  │         │     ├── aggregate_metrics
  │         │     └── sequence_summary
  │         │
  │         └── FOR EACH video in per_video_results:
  │               ├── getDetectionEvents(sessionId, videoId)
  │               │     └── Returns: Detection events for video
  │               │
  │               └── getGroundTruthEvents(videoId)
  │                     └── Returns: Ground truth events for video
  │
  └── ELSE (single video):
        ├── getTestSessionEvents(sessionId, 2000)
        │     └── Returns: All detection events
        │
        └── getGroundTruthEvents(videoId)
              └── Returns: Ground truth events
```

### 2. State Update Flow

```
Backend API Response
  ↓
setEnhancedResults(enhancedData)
  ├── enhancedResults.ground_truth_comparison
  │     ├── precision, recall, f1_score
  │     ├── true_positives, false_positives, false_negatives
  │     └── ground_truth_events_available
  │
  └── enhancedResults.detection_statistics.corrected_results
        ├── average_real_latency_ms
        ├── passed_detections
        ├── failed_detections
        └── pass_rate

setSequenceResults(seqResults) [IF multi-video]
  ├── sequenceResults.per_video_results[]
  │     └── FOR EACH video:
  │           ├── ground_truth_comparison { precision, recall, f1_score, TP, FP, FN }
  │           ├── total_detections, passed_detections, failed_detections
  │           └── average_latency_ms, max_latency_ms, min_latency_ms
  │
  └── sequenceResults.aggregate_metrics
        ├── overall_pass_rate
        ├── average_latency_ms
        └── total_detections

Aggregated Metrics Calculation (Frontend)
  ↓
aggregatedMetrics = useMemo(() => {
  // Sum TP, FP, FN from all videos' ground_truth_comparison
  // Calculate aggregated precision, recall, F1
  // Calculate overall detection count, pass rate
  // Calculate average, worst, best latency
})
  ↓
UI Components
  ├── TestStatusBanner (testPassed, overallPassRate, overallMatchRate)
  ├── GroundTruthComparisonCards (precision, recall, f1Score, TP, FP, FN)
  └── MetricsSummaryCards (detections, latency, matchRate, hardware)
```

### 3. Real-Time Updates (Lines 932-995)

**WebSocket Integration**:
```typescript
useEffect(() => {
  if (!sessionId || !realtimeEnabled) return;

  import('../services/websocketService').then(({ default: websocketService }) => {
    // Subscribe to detection_event updates
    unsubscribeDetections = websocketService.subscribe('detection_event', (data: any) => {
      console.log('🎯 HILResults: Received detection event:', data);

      // Normalize incoming detection event
      const newDetection = normalizeDetectionEvent(data, baseDetections.length);

      // Add to base detections
      setBaseDetections(prev => [...prev, newDetection]);

      // Update video detection map if video ID is available
      const videoIdFromEvent = data.video_id ?? data.videoId ?? selectedVideoId;
      if (videoIdFromEvent) {
        setVideoDetectionMap(prev => ({
          ...prev,
          [videoIdFromEvent]: [...(prev[videoIdFromEvent] || []), newDetection]
        }));
      }
    });

    // Join session room for detection events
    websocketService.emit('join_session', { session_id: sessionId });
  });

  return () => {
    if (unsubscribeDetections) unsubscribeDetections();
    websocketService.emit('leave_session', { session_id: sessionId });
  };
}, [sessionId, realtimeEnabled, selectedVideoId]);
```

---

## Type System & Data Contracts

### 1. EnhancedHILResults (Lines 789-879)

**File**: `enhanced-results.ts`

**Key Fields**:
```typescript
export interface EnhancedHILResults {
  session_id: string;

  hardware_status: {
    labjack_connected: boolean;
    model: string;
  };

  video_timing: {
    startup_delay_ms: number;          // System timing delay
    timing_sync_status: string;
    fps?: number;
    duration?: number;
    filename?: string;
  };

  detection_statistics: {
    total_detections: number;
    corrected_results: {
      average_real_latency_ms: number; // TRUE detection latency (what we care about)
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
    precision?: number;              // TP / (TP + FP)
    recall?: number;                 // TP / (TP + FN)
    f1_score?: number;               // 2 * (P * R) / (P + R)
    true_positives?: number;         // Correct detections matched to GT
    false_positives?: number;        // Detections with no matching GT
    false_negatives?: number;        // GT events missed by detection
  };
}
```

### 2. VideoSequenceResults (Lines 1281-1375)

**Multi-Video Container**:
```typescript
export interface VideoSequenceResults {
  sequence_id?: string;
  session_id?: string;
  total_videos?: number;
  videos_completed?: number;
  videos_passed?: number;
  videos_failed?: number;
  overall_pass_rate?: number;

  sequence_duration_seconds?: number;
  total_detections?: number;
  total_passed_detections?: number;
  total_failed_detections?: number;
  average_latency_ms?: number;
  worst_latency_ms?: number;
  best_latency_ms?: number;

  per_video_results?: PerVideoResult[];  // CRITICAL: Contains per-video GT metrics
  aggregate_metrics?: Record<string, unknown>;
}
```

### 3. PerVideoResult (Lines 1189-1279)

**Per-Video Metrics**:
```typescript
export interface PerVideoResult {
  video_id?: string;
  video_name?: string;
  video_number?: number;
  sequence_index?: number;

  status?: 'pass' | 'fail';
  pass_fail?: 'pass' | 'fail' | 'pending' | 'error';

  total_detections?: number;
  passed_detections?: number;
  failed_detections?: number;
  pass_rate?: number;

  average_latency_ms?: number;
  max_latency_ms?: number;
  min_latency_ms?: number;

  // CRITICAL: Ground truth metrics from backend
  ground_truth_comparison?: {
    events_available?: number;
    events_matched?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
  };

  ground_truth_metrics?: {
    total_ground_truth?: number;
    true_positives?: number;
    false_positives?: number;
    false_negatives?: number;
    precision?: number;
    recall?: number;
    f1_score?: number;
  };

  detection_events?: EnhancedDetectionEvent[];
}
```

---

## User Approval Workflow

### Current State: NO EXPLICIT APPROVAL WORKFLOW

**Observation**: The frontend displays test results but does **NOT** have an explicit user approval mechanism.

**Evidence**:
1. No "Approve" or "Reject" buttons in HILResults.tsx
2. No approval state in EnhancedResultsPageState
3. No approval API endpoints called
4. No approval status stored in state

**What Users Can Do**:
1. **View Results** - See pass/fail status, metrics, detection events
2. **Export Results** - Download PDF/Excel/CSV/JSON reports
3. **Navigate Away** - No confirmation dialog or save prompt

### Potential Future Enhancement

If approval workflow is needed:

```typescript
// State
const [approvalStatus, setApprovalStatus] = useState<'pending' | 'approved' | 'rejected' | null>(null);
const [approvalComment, setApprovalComment] = useState<string>('');

// UI Component
<Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'flex-end' }}>
  {approvalStatus === null && (
    <>
      <Button
        variant="contained"
        color="success"
        onClick={() => handleApproval('approved')}
        startIcon={<CheckCircle />}
      >
        Approve Results
      </Button>
      <Button
        variant="outlined"
        color="error"
        onClick={() => handleApproval('rejected')}
        startIcon={<Cancel />}
      >
        Reject Results
      </Button>
    </>
  )}
  {approvalStatus && (
    <Chip
      label={`Results ${approvalStatus.toUpperCase()}`}
      color={approvalStatus === 'approved' ? 'success' : 'error'}
      icon={approvalStatus === 'approved' ? <CheckCircle /> : <Cancel />}
    />
  )}
</Box>

// API Handler
const handleApproval = async (status: 'approved' | 'rejected') => {
  try {
    await apiService.post(`/api/test-sessions/${sessionId}/approval`, {
      approval_status: status,
      comment: approvalComment,
      approver: currentUser.id,
      timestamp: new Date().toISOString()
    });
    setApprovalStatus(status);
  } catch (error) {
    console.error('Failed to submit approval:', error);
  }
};
```

---

## Key Findings & Issues

### ✅ Strengths

1. **Backend-Driven Metrics**
   - All pass/fail determinations come from backend APIs
   - No client-side business logic for test validation
   - Backend calculates correct TP/FP/FN from ground truth matching

2. **Dual Validation Support**
   - LabJack timing validation (pass rate based on latency)
   - AI ground truth validation (precision/recall/F1)
   - Clear separation of concerns

3. **Multi-Video Aggregation**
   - Correctly aggregates TP/FP/FN across videos
   - Calculates aggregated precision/recall/F1
   - Maintains per-video breakdown

4. **Real-Time Updates**
   - WebSocket integration for live detection events
   - Automatic state updates when new detections arrive
   - Real-time pass rate recalculation

### ⚠️ Issues & Concerns

1. **Deprecated Frontend Calculation** (Lines 106-188)
   - `createMetricsFromDetections()` function still exists
   - Uses wrong field (`validation_result` instead of ground truth match)
   - Produces incorrect metrics (0% recall instead of 11.5%)
   - **SHOULD BE REMOVED** to prevent accidental use

2. **Field Name Inconsistency**
   - Backend returns both snake_case and camelCase fields
   - Frontend checks multiple field variants (e.g., `video_id`, `videoId`)
   - Makes code harder to maintain
   - Example:
     ```typescript
     const videoId = video.video_id ?? video.videoId;
     const videoName = video.video_name ?? video.videoName ?? video.video_filename;
     ```

3. **Complex State Management**
   - Multiple state variables for same data (baseDetections, videoDetectionMap, perVideoSummaries)
   - Synchronization logic between states
   - Risk of state inconsistency

4. **No User Approval Workflow**
   - Results are displayed but not formally approved/rejected
   - No audit trail of who reviewed results
   - No mechanism to flag suspicious results

5. **Loading State Complexity** (Lines 1164-1200)
   - Separate loading state per video (`videoLoadingState`)
   - Complex logic to determine when to show spinner vs. data
   - Potential race conditions with concurrent video loads

### 📋 Recommendations

1. **Remove Deprecated Code**
   - Delete `createMetricsFromDetections()` function
   - Remove all frontend metric calculation logic
   - Rely 100% on backend metrics

2. **Standardize Field Names**
   - Backend should return ONLY one format (preferably camelCase for TypeScript)
   - Frontend should not check multiple variants
   - Use type guards and normalization at API boundary

3. **Simplify State Management**
   - Consolidate detection state into single source of truth
   - Use derived state (useMemo) for computed values
   - Reduce number of useState calls

4. **Add Approval Workflow** (if required)
   - Add approval buttons to results page
   - Store approval status in backend
   - Display approval history
   - Require approval before results are finalized

5. **Improve Error Handling**
   - Add retry logic for failed API calls
   - Display user-friendly error messages
   - Provide fallback UI when data is unavailable

---

## Code References

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `loadHILResults()` | HILResults.tsx:577-900 | Main data loading function |
| `loadGroundTruthData()` | HILResults.tsx:394-450 | Load GT events for video |
| `loadDetectionsForVideo()` | HILResults.tsx:474-558 | Load detection events |
| `normalizeGroundTruthMetrics()` | HILResults.tsx:58-104 | Normalize backend GT metrics |
| `aggregatedMetrics` | HILResults.tsx:998-1121 | Calculate multi-video aggregation |
| `handleVideoTabChange()` | HILResults.tsx:563-572 | Switch between videos |
| `handleDetectionClick()` | HILResults.tsx:1373-1381 | Open video playback dialog |

### Key Components

| Component | File | Props | Purpose |
|-----------|------|-------|---------|
| TestStatusBanner | TestStatusBanner.tsx | passed, detectionCount, passRate | Overall pass/fail banner |
| GroundTruthComparisonCards | GroundTruthComparisonCards.tsx | precision, recall, f1Score, TP, FP, FN | GT metrics display |
| MetricsSummaryCards | MetricsSummaryCards.tsx | detections, latency, matchRate | Signal quality metrics |
| DetectionTableRow | DetectionTableRow.tsx | detection, videoName, videoSequenceNumber | Individual detection row |
| FrameCorrelationTimeline | FrameCorrelationTimeline.tsx | detections, groundTruthEvents, videoMetadata | Timeline visualization |

---

## Conclusion

The frontend results display system is **backend-driven** with pass/fail determinations calculated by the backend and displayed by the frontend. The system supports both **LabJack timing validation** and **AI ground truth validation**, with proper aggregation for multi-video sequences.

**Key Takeaway**: The frontend's primary responsibility is to **fetch, normalize, and display** backend-provided metrics. It does NOT perform pass/fail business logic itself, which is the correct architectural pattern.

**Critical Issue**: The deprecated `createMetricsFromDetections()` function must be removed to prevent accidental use of incorrect frontend calculation logic.

**Missing Feature**: No explicit user approval workflow exists. Results are displayed but not formally approved/rejected by users.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-11
**Author**: Code Analyzer Agent
