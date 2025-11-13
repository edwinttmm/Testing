# Multi-Video Test Session Results - UI Presentation Analysis

## Executive Summary

This document analyzes how multi-video test session results should be presented to users, providing detailed wireframes, component recommendations, and UX flow based on existing codebase analysis.

---

## 1. Current Single-Video Presentation (HILResults.tsx)

### Component Structure
```
Container
├── AppBar (Header)
│   ├── Back Button
│   ├── Title: "HIL Test Results"
│   └── Live Updates Toggle
├── TestStatusBanner (Overall Pass/Fail)
├── GroundTruthComparisonCards (F1, Precision, Recall)
├── MetricsSummaryCards (Signal Quality)
├── Video Tabs (if multi-video)
├── Per-Video Summary Chips
├── FrameCorrelationTimeline
└── Detection Events Table
```

### Current Metrics Displayed
- **Top-level:** F1 Score, Precision, Recall, TP/FP/FN
- **Signal Quality:** Detections count, Detection Latency (ms), Video Startup (ms), Match Rate (%), Hardware Status
- **Timeline:** Frame-by-frame correlation, alignment statistics
- **Table:** Individual detection events with latency, voltage, pass/fail

### Strengths
- Clear pass/fail banner at top
- Ground Truth Comparison is prominent (PRIMARY DISPLAY)
- Separation between "Ground Truth Performance" and "Signal Quality"
- Clean Material-UI cards with color-coded status indicators

### Weaknesses for Multi-Video
- No aggregated overview across all videos
- Video tabs are basic (lines 924-968) - limited metadata shown
- Detection table shows ALL videos mixed OR filtered by selected video (unclear behavior)
- No comparison view between videos
- No per-video performance summary cards

---

## 2. Existing Multi-Video UI Components

### VideoSequenceResults.tsx (Lines 1-558)

**Key Features:**
- **Sequence Summary Section** (lines 103-212)
  - Overall status chip (pass/fail/partial)
  - Videos passed count (X/Total)
  - Sequence duration formatted
  - Latency metrics (avg, worst, best)
  - Detection summary (total, passed, failed, pass rate)

- **Video Progression Timeline** (lines 214-287)
  - Visual horizontal timeline showing all videos
  - Color-coded by pass/fail status
  - Proportional width based on duration
  - Click to see details
  - Time markers at start and end

- **Per-Video Results Table** (lines 289-470)
  - Expandable rows for each video
  - Columns: Video #, Name, Status, Duration, Detections, Pass/Fail, Avg Latency, Max Latency
  - Nested detection events table (first 10 events shown)
  - "Details" button opens full dialog

- **Video Detail Dialog** (lines 473-553)
  - Full metrics grid (Duration, Detections, Pass Rate, Avg Latency)
  - FrameCorrelationTimeline for that specific video
  - Export button

**UX Pattern:** Drill-down from overview → per-video summary → detailed timeline

---

## 3. Recommended UX Flow for Multi-Video Results

### User Journey

```
┌─────────────────────────────────────────────────┐
│ 1. FIRST VIEW: Overall Summary (Aggregated)    │
│    - All videos combined pass/fail status       │
│    - Total detections across all videos         │
│    - Average metrics across sequence             │
│    - Video selector/tabs prominently displayed  │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 2. VIDEO SELECTOR: Choose specific video       │
│    - Dropdown OR Tabs with metadata             │
│    - Show: Video #, Name, Status, Detection Cnt │
│    - Color-coded status indicators               │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ 3. PER-VIDEO VIEW: Selected video details      │
│    - Video-specific metrics cards                │
│    - Timeline filtered to that video             │
│    - Detection table for that video only         │
└─────────────────────────────────────────────────┘
                      ↓ (optional)
┌─────────────────────────────────────────────────┐
│ 4. COMPARISON VIEW: Side-by-side comparison    │
│    - Select multiple videos to compare          │
│    - Metrics comparison table                    │
│    - "Which performed best/worst?"               │
└─────────────────────────────────────────────────┘
```

---

## 4. Detailed Wireframes

### WIREFRAME 1: Initial View (Multi-Video Session Detected)

```
┌────────────────────────────────────────────────────────────────────┐
│  ← Back    HIL Test Results                    [Live Updates: ON]  │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  ✓ TEST PASSED                                    [PASSED]          │
│  45 out of 45 detections captured across 3 videos                   │
│  Overall Pass Rate: 100.0% • Avg Latency: 42.3ms                    │
└────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════╗
║  GROUND TRUTH COMPARISON - Aggregated Across All Videos           ║
╠═══════════════════════════════════════════════════════════════════╣
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ║
║  │ F1 Score        │  │ Precision       │  │ Recall          │  ║
║  │ 95.2%          │  │ 96.1%          │  │ 94.3%          │  ║
║  │ ⭐ Excellent    │  │ ✓ Good         │  │ ✓ Good         │  ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────────┐
│  📊 Multi-Video Sequence                            [3 videos]      │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Select Video:                                     [Dropdown] │ │
│  │ ┌──────────────────────────────────────────────────────────┐ │ │
│  │ │ 1. highway_scene_1080p.mp4  [PASS] [15 detections]      │ │ │
│  │ │ 2. urban_crossing_720p.mp4  [PASS] [20 detections]      │ │ │
│  │ │ 3. suburban_street_720p.mp4 [PASS] [10 detections]   ▼  │ │ │
│  │ └──────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  OR: TABS LAYOUT                                                    │
│  ┌──────────────┬──────────────┬──────────────┐                    │
│  │ Video 1      │ Video 2      │ Video 3      │                    │
│  │ highway_1080p│ urban_720p   │ suburban_720p│                    │
│  │ ✓ PASS       │ ✓ PASS       │ ✓ PASS       │                    │
│  │ 15 detections│ 20 detections│ 10 detections│                    │
│  └──────────────┴──────────────┴──────────────┘                    │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  📈 Sequence Performance Overview                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Timeline: [░░░V1░░░░][░░░░░V2░░░░░][░░V3░░] (10.5s total)  │ │
│  │            └─ PASS ─┘└──── PASS ────┘└ PASS ┘                │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  📊 Per-Video Summary Table                                         │
│  ┌──────┬─────────────────────┬────────┬──────────┬──────────┐   │
│  │ #    │ Video Name          │ Status │ Duration │ Avg Lat  │   │
│  ├──────┼─────────────────────┼────────┼──────────┼──────────┤   │
│  │ 1    │ highway_scene_1080p │ ✓ PASS │ 3.5s     │ 41.2ms   │   │
│  │ 2    │ urban_crossing_720p │ ✓ PASS │ 5.0s     │ 38.7ms   │   │
│  │ 3    │ suburban_street_720p│ ✓ PASS │ 2.0s     │ 49.1ms   │   │
│  └──────┴─────────────────────┴────────┴──────────┴──────────┘   │
└────────────────────────────────────────────────────────────────────┘

                       [Export All Results]
```

### WIREFRAME 2: Per-Video View (After Selecting Video 1)

```
┌────────────────────────────────────────────────────────────────────┐
│  ← Back to Overview                                                 │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  🎬 Video #1: highway_scene_1080p.mp4                              │
│  ✓ PASS • 15 detections • Pass rate: 100.0%                        │
└────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════╗
║  Video-Specific Ground Truth Comparison                            ║
╠═══════════════════════════════════════════════════════════════════╣
║  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ║
║  │ F1 Score        │  │ Precision       │  │ Recall          │  ║
║  │ 96.8%          │  │ 97.2%          │  │ 96.4%          │  ║
║  └─────────────────┘  └─────────────────┘  └─────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────────────────────────────────────┐
│  Signal Quality Metrics (Video 1 Only)                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ Detections  │ │ Det Latency │ │ Match Rate  │ │ Hardware    │ │
│  │ 15/15       │ │ 41.2ms     │ │ 93.3%       │ │ T7-Pro      │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  Detection Timeline (Video 1)                                       │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Frame Correlation: 14 Aligned, 1 Misaligned, 0 Missing      │ │
│  │ [Timeline visualization for this video only]                 │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  Detection Events (15 total for Video 1)                            │
│  ┌────┬────────┬─────────┬──────────┬───────────┬────────┐        │
│  │ #  │ Time(s)│ Voltage │ Latency  │ Matched GT│ Result │        │
│  ├────┼────────┼─────────┼──────────┼───────────┼────────┤        │
│  │ 1  │ 0.125  │ 4.52V   │ 42.1ms   │ ✓ Yes     │ PASS   │        │
│  │ 2  │ 0.375  │ 4.48V   │ 39.7ms   │ ✓ Yes     │ PASS   │        │
│  │... │ ...    │ ...     │ ...      │ ...       │ ...    │        │
│  └────┴────────┴─────────┴──────────┴───────────┴────────┘        │
└────────────────────────────────────────────────────────────────────┘
```

---

## 5. Aggregated Metrics Presentation

### Top-Level (Session)
Should display FIRST when user opens multi-video test results:

```javascript
{
  // Overall status
  overallStatus: 'pass' | 'fail' | 'partial',
  videosPassedCount: 2,
  videosTotalCount: 3,

  // Aggregated Ground Truth Metrics
  aggregatedF1Score: 95.2,          // Combined across all videos
  aggregatedPrecision: 96.1,        // TP / (TP + FP) across all videos
  aggregatedRecall: 94.3,           // TP / (TP + FN) across all videos
  totalTruePositives: 42,           // Sum across all videos
  totalFalsePositives: 2,           // Sum across all videos
  totalFalseNegatives: 1,           // Sum across all videos

  // Aggregated Latency Metrics
  averageLatencyMs: 42.3,           // Mean of all detection latencies
  worstLatencyMs: 68.9,             // Max latency across all videos
  bestLatencyMs: 28.1,              // Min latency across all videos

  // Aggregated Detection Metrics
  totalDetections: 45,              // Sum across all videos
  totalPassedDetections: 45,
  totalFailedDetections: 0,
  overallPassRate: 100.0,

  // Sequence Metadata
  sequenceDurationSeconds: 10.5,
  sequenceDurationFormatted: "00:00:10.5"
}
```

### Per-Video Level
Should display when user selects a specific video:

```javascript
{
  videoId: "vid_123",
  videoNumber: 1,
  videoName: "highway_scene_1080p.mp4",
  videoOrder: 0,                    // Sequence index
  videoStartTime: 0.0,              // Start time within sequence
  videoEndTime: 3.5,                // End time within sequence

  // Video-specific Ground Truth Metrics
  f1Score: 96.8,
  precision: 97.2,
  recall: 96.4,
  truePositives: 14,
  falsePositives: 1,
  falseNegatives: 0,

  // Video-specific Performance
  status: 'pass' | 'fail',
  durationSeconds: 3.5,
  durationFormatted: "00:00:03.5",
  totalDetections: 15,
  passedDetections: 15,
  failedDetections: 0,
  passRate: 100.0,

  // Video-specific Latency
  averageLatencyMs: 41.2,
  maxLatencyMs: 58.3,
  minLatencyMs: 32.1,
  latencyThresholdMs: 100.0,

  // Video metadata
  fps: 30,
  frameCount: 105
}
```

---

## 6. Detection Event Display Strategy

### Recommended Approach: **FILTERED BY SELECTED VIDEO**

**Rationale:**
- Clearer user experience - no mixing of data from different videos
- Easier to correlate detection table with timeline visualization
- Matches user mental model (I'm viewing "Video 1", show me Video 1's detections)

**Implementation:**
```typescript
// In HILResults.tsx
const activeDetections = useMemo(() => {
  if (selectedVideoId) {
    return videoDetectionMap[selectedVideoId] || [];
  }
  // Fallback: show all detections if no video selected
  return allDetections;
}, [selectedVideoId, videoDetectionMap, allDetections]);
```

### Timeline Display
- **FrameCorrelationTimeline**: Show ONE video at a time (the selected video)
- Timeline props should receive:
  - `detectionEvents`: Filtered to selected video only
  - `groundTruthEvents`: Filtered to selected video's time window
  - `videoMetadata`: Selected video's FPS, duration, filename

---

## 7. Comparison Features (Optional Enhancement)

### "Compare Videos" View
Add a new section/tab for side-by-side comparison:

```
┌────────────────────────────────────────────────────────────────────┐
│  📊 Video Comparison                                                │
│  ┌────────────────────┬────────────────────┬────────────────────┐ │
│  │ Video 1            │ Video 2            │ Video 3            │ │
│  │ highway_scene_1080p│ urban_crossing_720p│ suburban_street... │ │
│  ├────────────────────┼────────────────────┼────────────────────┤ │
│  │ F1: 96.8% ⭐       │ F1: 94.2% ✓        │ F1: 94.8% ✓        │ │
│  │ Precision: 97.2%   │ Precision: 95.1%   │ Precision: 96.0%   │ │
│  │ Recall: 96.4%      │ Recall: 93.3%      │ Recall: 93.7%      │ │
│  ├────────────────────┼────────────────────┼────────────────────┤ │
│  │ Avg Lat: 41.2ms    │ Avg Lat: 38.7ms ✓  │ Avg Lat: 49.1ms    │ │
│  │ Max Lat: 58.3ms    │ Max Lat: 52.1ms    │ Max Lat: 68.9ms ⚠  │ │
│  ├────────────────────┼────────────────────┼────────────────────┤ │
│  │ Detections: 15     │ Detections: 20     │ Detections: 10     │ │
│  │ Pass Rate: 100%    │ Pass Rate: 100%    │ Pass Rate: 100%    │ │
│  └────────────────────┴────────────────────┴────────────────────┘ │
│                                                                      │
│  🏆 Best Performer: Video 1 (highway_scene_1080p)                   │
│  ⚠️  Needs Attention: Video 3 (highest max latency)                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## 8. Specific UI Components Needed

### 8.1 Existing Components (Reusable)

✅ **TestStatusBanner** (TestStatusBanner.tsx)
- Already supports pass/fail display
- Extend to show "X/Y videos passed" for multi-video

✅ **GroundTruthComparisonCards** (GroundTruthComparisonCards.tsx)
- Works for both aggregated AND per-video metrics
- Just pass different data depending on view

✅ **MetricsSummaryCards** (MetricsSummaryCards.tsx)
- Already supports detection latency, match rate, hardware status
- Works for both aggregated and per-video views

✅ **FrameCorrelationTimeline** (FrameCorrelationTimeline.tsx)
- Already supports filtering by video metadata
- Pass video-specific detection events and ground truth events

✅ **VideoSequenceResults** (VideoSequenceResults.tsx)
- Full sequence summary, timeline, per-video table
- Can be embedded as a section in HILResults.tsx

### 8.2 New Components Needed

❌ **AggregatedMetricsOverview**
```typescript
interface AggregatedMetricsOverviewProps {
  sequenceSummary: {
    overallStatus: 'pass' | 'fail' | 'partial';
    videosPassedCount: number;
    videosTotalCount: number;
    totalDetections: number;
    averageLatencyMs: number;
    worstLatencyMs: number;
    bestLatencyMs: number;
  };
  aggregatedGroundTruth: {
    f1Score: number;
    precision: number;
    recall: number;
    totalTP: number;
    totalFP: number;
    totalFN: number;
  };
}

// Location: /frontend/src/components/AggregatedMetricsOverview.tsx
```

❌ **VideoComparisonTable** (Optional)
```typescript
interface VideoComparisonTableProps {
  videos: PerVideoResult[];
  comparisonMetrics: ('f1Score' | 'precision' | 'recall' | 'avgLatency' | 'maxLatency' | 'passRate')[];
  highlightBest?: boolean;
  highlightWorst?: boolean;
}

// Location: /frontend/src/components/VideoComparisonTable.tsx
```

### 8.3 Modified Components

⚙️ **HILResults.tsx** - Needs Updates:
1. Add aggregated metrics section at top (lines 894-906)
2. Modify video tabs to show more metadata (currently lines 924-968)
3. Add "Overview" vs "Per-Video" view toggle
4. Conditionally render aggregated vs per-video GroundTruthComparisonCards

---

## 9. Recommended Layout Structure

### Hierarchical Information Architecture

```
1. PAGE HEADER
   - Back button
   - Title: "HIL Test Results"
   - Live updates toggle

2. OVERALL TEST STATUS BANNER
   - Pass/Fail for entire sequence
   - X/Y videos passed
   - Criteria text

3. AGGREGATED GROUND TRUTH COMPARISON
   - F1 Score (combined)
   - Precision (combined)
   - Recall (combined)
   - TP/FP/FN totals

4. SEQUENCE OVERVIEW SECTION
   - Video count
   - Total duration
   - Video progression timeline
   - Quick stats (total detections, avg latency across sequence)

5. VIDEO SELECTOR
   - Tabs OR Dropdown
   - Shows: Video #, Name, Status chip, Detection count

6. PER-VIDEO GROUND TRUTH (if video selected)
   - Video-specific F1, Precision, Recall

7. PER-VIDEO SIGNAL QUALITY METRICS (if video selected)
   - Video-specific detections, latency, match rate

8. DETECTION TIMELINE (filtered to selected video)
   - FrameCorrelationTimeline component

9. DETECTION EVENTS TABLE (filtered to selected video)
   - Individual detection rows

10. SESSION INFORMATION FOOTER
    - Session ID, project name, test name
```

---

## 10. UX Best Practices from Similar Testing Tools

### From Industrial Test Automation (NI TestStand, LabVIEW)
- **Progressive disclosure**: Show summary first, details on demand
- **Color coding**: Green (pass), Red (fail), Yellow (partial/warning)
- **Hierarchical drill-down**: Overview → Component → Detail

### From CI/CD Pipelines (Jenkins, GitHub Actions)
- **Timeline visualization**: Shows sequence of steps/videos
- **Expandable sections**: Click to see more details
- **Status badges**: Quick visual indicators on each item

### From Analytics Dashboards (Grafana, Kibana)
- **Comparison view**: Side-by-side metrics for different entities
- **Filtering**: Select which data to display
- **Aggregation levels**: Overall, per-group, per-item

### Key Takeaways
1. ✅ Show aggregated summary FIRST
2. ✅ Make video selection PROMINENT (tabs work better than dropdown for ≤5 videos)
3. ✅ Use consistent color coding throughout (green=pass, red=fail)
4. ✅ Provide drill-down path: Overview → Per-Video → Detection Details
5. ✅ Display timeline visualization for sequence understanding
6. ✅ Keep metrics consistent between views (same metric names, units)

---

## 11. Implementation Priority

### Phase 1: Core Multi-Video Support (MVP)
1. ✅ Aggregated metrics at top (reuse GroundTruthComparisonCards with aggregated data)
2. ✅ Video tabs with enhanced metadata (extend current implementation)
3. ✅ Per-video view filtering (already mostly working)
4. ✅ Detection table filtering by selected video (add logic)

### Phase 2: Enhanced Visualization
1. ⭐ Video progression timeline (adapt VideoSequenceResults timeline)
2. ⭐ Per-video summary cards above timeline
3. ⭐ Better video selector UI (tabs with more info)

### Phase 3: Comparison Features (Optional)
1. 🔮 Side-by-side comparison view
2. 🔮 "Best/Worst performer" indicators
3. 🔮 Export comparison reports

---

## 12. ASCII Wireframe: Final Recommended Layout

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ← Back    HIL Test Results                       [Live Updates: ON]     │
└──────────────────────────────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════════════════════════════╗
║                        OVERALL TEST STATUS                                ║
║  ✓ TEST PASSED                                    [PASSED]               ║
║  3/3 videos passed • 45 detections • Pass rate: 100.0%                   ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║       GROUND TRUTH COMPARISON - Aggregated Across All Videos             ║
╠══════════════════════════════════════════════════════════════════════════╣
║  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐ ║
║  │ F1 Score           │  │ Precision          │  │ Recall             │ ║
║  │ 95.2%             │  │ 96.1%             │  │ 94.3%             │ ║
║  │ ⭐ Excellent       │  │ ✓ Good            │  │ ✓ Good            │ ║
║  │                    │  │                    │  │                    │ ║
║  │ 42 TP, 2 FP, 1 FN │  │ TP/(TP+FP)        │  │ TP/(TP+FN)        │ ║
║  └────────────────────┘  └────────────────────┘  └────────────────────┘ ║
╚══════════════════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────────────────────┐
│  📊 MULTI-VIDEO SEQUENCE OVERVIEW                   [3 videos]           │
│                                                                            │
│  Timeline:  [░░░░Video 1░░░░][░░░░░Video 2░░░░░][░░Video 3░░]           │
│  Duration:  └──── 3.5s ────┘└───── 5.0s ─────┘└─── 2.0s ──┘           │
│  Status:    └───── PASS ────┘└────── PASS ─────┘└─── PASS ──┘           │
│                                                                            │
│  Total Duration: 10.5s • Avg Latency: 42.3ms • Worst: 68.9ms             │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  🎬 VIDEO SELECTOR                                                        │
│  ┌────────────────┬────────────────┬────────────────┐                   │
│  │ Video 1        │ Video 2        │ Video 3        │  ← TABS            │
│  │ highway_1080p  │ urban_720p     │ suburban_720p  │                   │
│  │ ✓ PASS         │ ✓ PASS         │ ✓ PASS         │                   │
│  │ 15 detections  │ 20 detections  │ 10 detections  │                   │
│  │ 41.2ms avg     │ 38.7ms avg     │ 49.1ms avg     │                   │
│  └────────────────┴────────────────┴────────────────┘                   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  📈 PER-VIDEO GROUND TRUTH (Video 1 Selected)                            │
│  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐ │
│  │ F1 Score           │  │ Precision          │  │ Recall             │ │
│  │ 96.8%             │  │ 97.2%             │  │ 96.4%             │ │
│  └────────────────────┘  └────────────────────┘  └────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  🔧 SIGNAL QUALITY METRICS (Video 1)                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Detect.  │ │ Det Lat. │ │ Video    │ │ Match    │ │ Hardware │      │
│  │ 15/15    │ │ 41.2ms   │ │ Startup  │ │ Rate     │ │ T7-Pro   │      │
│  │ ▓▓▓▓▓▓▓▓ │ │ ✓ Good   │ │ 28.3ms   │ │ 93.3%    │ │ ✓ Conn.  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  📊 DETECTION TIMELINE (Video 1)                                          │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │ Frame Correlation: 14 Aligned, 1 Misaligned, 0 Missing            │  │
│  │ [Timeline visualization - see FrameCorrelationTimeline component] │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  📋 DETECTION EVENTS (15 total for Video 1)                               │
│  ┌────┬────────┬─────────┬──────────┬────────────┬────────┐             │
│  │ #  │ Time(s)│ Voltage │ Latency  │ Matched GT │ Result │             │
│  ├────┼────────┼─────────┼──────────┼────────────┼────────┤             │
│  │ 1  │ 0.125  │ 4.52V   │ 42.1ms   │ ✓ Yes      │ PASS   │             │
│  │ 2  │ 0.375  │ 4.48V   │ 39.7ms   │ ✓ Yes      │ PASS   │             │
│  │... │ ...    │ ...     │ ...      │ ...        │ ...    │             │
│  └────┴────────┴─────────┴──────────┴────────────┴────────┘             │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  Session ID: test_123 • Project: ADAS_Validation • Test: Multi_Video_1  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Key Recommendations Summary

### What to Display FIRST (Initial View)
✅ **Overall summary across all videos**
- Aggregated Ground Truth Comparison (F1, Precision, Recall)
- Overall test status banner (X/Y videos passed)
- Sequence overview (timeline, duration, total detections)
- Video selector prominently placed

### How Users Should Switch Between Videos
✅ **Tabs (preferred for ≤5 videos)**
- Shows: Video #, Name, Status chip, Detection count, Avg latency
- Color-coded by pass/fail status
- Active tab highlighted

Alternative: **Dropdown (for >5 videos)**
- Each option shows same metadata as tabs
- Less visual clutter for many videos

### Where Aggregated Metrics Should Appear
✅ **Fixed section at top, above video selector**
- Always visible regardless of video selection
- Provides context for per-video metrics
- Users can compare "this video" vs "overall sequence"

### Per-Video Metrics Display
✅ **Below video selector, updates when video changes**
- Video-specific Ground Truth cards
- Video-specific Signal Quality cards
- Timeline filtered to selected video
- Detection table filtered to selected video

### Detection Event Display Strategy
✅ **Filtered by selected video** (recommended)
- Clearer user experience
- Easier to correlate with timeline
- No mixing of data from different videos

---

## 14. Files Referenced

- `/frontend/src/pages/HILResults.tsx` (lines 1-1066)
- `/frontend/src/pages/EnhancedResults.tsx` (lines 1-1194)
- `/frontend/src/components/VideoSequenceResults.tsx` (lines 1-558)
- `/frontend/src/components/MetricsSummaryCards.tsx` (lines 1-176)
- `/frontend/src/components/GroundTruthComparisonCards.tsx` (lines 1-226)
- `/frontend/src/components/VideoSequenceSelector.tsx` (lines 1-76)
- `/frontend/src/components/TestStatusBanner.tsx` (lines 1-88)
- `/frontend/src/components/FrameCorrelationTimeline.tsx` (lines 1-601)

---

**Document Created:** 2025-10-30
**Analysis By:** Research Agent
**Status:** Detailed wireframes and recommendations complete
