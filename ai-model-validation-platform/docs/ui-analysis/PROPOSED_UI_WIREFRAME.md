# HIL Results UI - Proposed Wireframe

## Current UI Problem: User sees "two tables etc its so confusing"

### BEFORE (Current Confusing Layout):
```
┌─────────────────────────────────────────────────────────────────┐
│ ← HIL Test Results                                    [Refresh] │
│   Session XYZ - Project Alpha                                   │
│   [Auto Refresh] [Enhanced Timing] [Raw μs Data]                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ ⚙️ Startup Timing (Debug)                                       │
│ GT First Event: 0.123s | First Detection: 0.456s               │
│ Offset vs GT: 333ms | Inferred Display Delay: 250ms            │
│ processing≈50ms • fps=24                                        │
└─────────────────────────────────────────────────────────────────┘
   ⬆️ PROBLEM 1: Debug info confusing users

┌─────────────────────────────────────────────────────────────────┐
│ 📊 Session Overview                                             │
│ Test Name: Pedestrian Detection                                │
│ Status: COMPLETED ✓ | Duration: 3m 45s | Start: 2:30 PM        │
└─────────────────────────────────────────────────────────────────┘
   ⬆️ PROBLEM 2: "COMPLETED" doesn't mean "PASSED"

┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Hardware Status  │ │ Video Metadata   │ │ Detection Stats  │
│ LabJack: ✓       │ │ FPS: 24          │ │ Total: 12        │
│ Model: T7        │ │ Duration: 3m 45s │ │ Passed: 12       │
└──────────────────┘ └──────────────────┘ └──────────────────┘
   ⬆️ PROBLEM 3: Duplicate info (Duration appears twice)

┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Latency Metrics  │ │ Ground Truth     │ │ ... more cards   │
│ Avg: 45ms        │ │ Matched: 12/12   │ │ ... even more    │
│ Min: 32ms        │ │ Precision: 100%  │ │ ... cards        │
└──────────────────┘ └──────────────────┘ └──────────────────┘
   ⬆️ PROBLEM 4: Too many cards, no clear hierarchy

┌─────────────────────────────────────────────────────────────────┐
│ 📋 Detection Events Table #1 (Main)                             │
├─────────────────────────────────────────────────────────────────┤
│ Frame │ Time   │ Latency │ Status │ Voltage │ GT Match         │
├───────┼────────┼─────────┼────────┼─────────┼──────────────────┤
│   0   │ 0.041s │  45ms   │  PASS  │  4.2V   │  TP              │
│   2   │ 0.103s │  52ms   │  PASS  │  4.2V   │  TP              │
│  ...  │  ...   │  ...    │  ...   │  ...    │  ...             │
└───────┴────────┴─────────┴────────┴─────────┴──────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 📊 Frame Correlation Timeline                                   │
│ Detection Events (12) vs Ground Truth (12)                      │
├─────────────────────────────────────────────────────────────────┤
│ Type      │ Frame │ Time   │ Correlation │ Latency │ Status    │
├───────────┼───────┼────────┼─────────────┼─────────┼───────────┤
│ GT        │   0   │ 0.041s │   aligned   │    —    │    —      │
│ Detection │   0   │ 0.041s │   aligned   │  45ms   │  GT PASS  │
│ GT        │   2   │ 0.103s │   aligned   │    —    │    —      │
│ Detection │   2   │ 0.103s │   aligned   │  52ms   │  GT PASS  │
│  ...      │  ...  │  ...   │    ...      │  ...    │   ...     │
└───────────┴───────┴────────┴─────────────┴─────────┴───────────┘
   ⬆️ PROBLEM 5: Same detection data shown TWICE (confusing!)

┌─────────────────────────────────────────────────────────────────┐
│ 🔬 Raw Timing Data (μs precision)                               │
│ Voltage Transitions: 48 events                                  │
│ Timestamp (μs) │ Channel │ Voltage │ Type                       │
│ 1234567890123  │  AIN0   │  4.2V   │ rising_edge                │
│  ...           │  ...    │  ...    │  ...                       │
└─────────────────────────────────────────────────────────────────┘
   ⬆️ PROBLEM 6: Developer debug data visible to users
```

**User Reaction:** "There are two tables showing the same detections... it's so confusing!"

---

## AFTER (Proposed Clean Layout):

```
┌─────────────────────────────────────────────────────────────────┐
│ ← Back to Tests                                                 │
│                                                                  │
│ HIL Test: Pedestrian Detection - Project Alpha                  │
│ Session: ABC123 • Started: 2:30 PM • Duration: 3m 45s          │
│                                                                  │
│ [🔄 Refresh]  [📥 Export]  [🔧 Compute Results]                │
└─────────────────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                                                                  ┃
┃  ✅  TEST RESULT: PASS                                          ┃
┃                                                                  ┃
┃  12 out of 12 detections passed (100% pass rate)                ┃
┃  All detections within 100ms threshold ✓                        ┃
┃                                                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
   ⬆️ SOLUTION: Clear, prominent PASS/FAIL - user knows immediately!

┌─────────────────────────────────────────────────────────────────┐
│  📊  SUMMARY METRICS                                            │
└─────────────────────────────────────────────────────────────────┘

┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
│  DETECTIONS    │ │  LATENCY       │ │  GROUND TRUTH  │ │  HARDWARE      │
│                │ │                │ │                │ │                │
│     12/12      │ │   Avg: 45ms    │ │  Match: 100%   │ │  ✅ Connected  │
│   100% Pass    │ │   Min: 32ms    │ │  Precision:1.0 │ │  LabJack T7    │
│                │ │   Max: 67ms    │ │  Recall: 1.0   │ │  v1.2.3        │
│                │ │  (Limit: 100ms)│ │  F1: 1.0       │ │  4 channels    │
└────────────────┘ └────────────────┘ └────────────────┘ └────────────────┘
   ⬆️ SOLUTION: 4 clear cards, no duplicate information

┌─────────────────────────────────────────────────────────────────┐
│  🎬  VIDEO SEQUENCE (Multi-Video Tests Only)                   │
├─────────────────────────────────────────────────────────────────┤
│  Current Video: [Video 2 of 3 ▼] pedestrian_crossing_02.mp4   │
│  Video Progress: ████████████░░░░░░░░ 60% (1m 30s / 2m 30s)   │
│  Sequence Progress: ████████░░░░░░░░░░░░ 40% (2m 15s / 5m)    │
└─────────────────────────────────────────────────────────────────┘
   ⬆️ SOLUTION: Only shown for multi-video tests, clear progress

┌─────────────────────────────────────────────────────────────────┐
│  📈  FRAME CORRELATION TIMELINE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [Interactive visualization - NOT a data table]                 │
│                                                                  │
│  Detection Events (12) ━━━━ Ground Truth (12)                  │
│  Alignment Rate: 100% │ All events within ±2 frames            │
│                                                                  │
│  Timeline shows visual correlation, NOT duplicate event list    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
   ⬆️ SOLUTION: Timeline is VISUAL ONLY, not a second table

┌─────────────────────────────────────────────────────────────────┐
│  📋  DETECTION EVENTS                                           │
│                                                                  │
│  Showing all 12 detection events with ground truth validation   │
├─────────────────────────────────────────────────────────────────┤
│ Frame │ Video Time │ Latency │ Status │ Voltage │ GT Match     │
├───────┼────────────┼─────────┼────────┼─────────┼──────────────┤
│   0   │  0.041s    │  45ms   │  ✅ PASS│  4.2V   │ ✅ TP (100%)│
│   2   │  0.103s    │  52ms   │  ✅ PASS│  4.2V   │ ✅ TP (98%) │
│   3   │  0.158s    │  48ms   │  ✅ PASS│  4.2V   │ ✅ TP (100%)│
│   5   │  0.234s    │  67ms   │  ✅ PASS│  4.2V   │ ✅ TP (95%) │
│   7   │  0.289s    │  43ms   │  ✅ PASS│  4.2V   │ ✅ TP (100%)│
│   9   │  0.356s    │  51ms   │  ✅ PASS│  4.2V   │ ✅ TP (98%) │
│  11   │  0.423s    │  39ms   │  ✅ PASS│  4.2V   │ ✅ TP (100%)│
│  13   │  0.478s    │  55ms   │  ✅ PASS│  4.2V   │ ✅ TP (97%) │
│  15   │  0.541s    │  47ms   │  ✅ PASS│  4.2V   │ ✅ TP (100%)│
│  17   │  0.602s    │  62ms   │  ✅ PASS│  4.2V   │ ✅ TP (96%) │
│  19   │  0.667s    │  41ms   │  ✅ PASS│  4.2V   │ ✅ TP (100%)│
│  21   │  0.734s    │  58ms   │  ✅ PASS│  4.2V   │ ✅ TP (99%) │
└───────┴────────────┴─────────┴────────┴─────────┴──────────────┘
   ⬆️ SOLUTION: ONE master table with all info (no duplicates!)

┌─────────────────────────────────────────────────────────────────┐
│  💾  EXPORT OPTIONS                                             │
├─────────────────────────────────────────────────────────────────┤
│  [📥 Export Full Results (JSON)]  [📊 Export Summary (PDF)]    │
│  [🔬 Export Raw Timing Data]      [📈 Export Charts (PNG)]     │
└─────────────────────────────────────────────────────────────────┘
   ⬆️ SOLUTION: Export actions grouped at bottom

[🔍 Show Debug Info] ← Hidden toggle for developers
   ⬆️ SOLUTION: Debug timing data hidden by default
```

---

## Visual Comparison: Information Architecture

### BEFORE (Current - Confusing):
```
Page Structure:
├── Header (OK)
├── 🔴 DEBUG TIMING CARD (confusing!)
├── Session Overview (OK)
├── 🔴 6 METRIC CARDS (too many, duplicates!)
│   ├── Hardware Status
│   ├── Video Metadata (duplicate Duration!)
│   ├── Detection Statistics
│   ├── Latency Metrics
│   ├── Ground Truth Comparison
│   └── Enhanced Results
├── 🔴 DETECTION EVENTS TABLE #1 (12 events)
├── 🔴 FRAME CORRELATION TIMELINE TABLE #2 (same 12 events!)
├── 🔴 RAW TIMING DATA (developer debug!)
└── Export Dialog (OK)

USER SEES: "There are 12 detections... wait, now I see them again...
            and again... is that 36 total? I'm confused!"
```

### AFTER (Proposed - Clear):
```
Page Structure:
├── Header with Actions (streamlined)
├── ✅ TEST STATUS BANNER (prominent PASS/FAIL)
├── ✅ 4 SUMMARY METRIC CARDS (no duplicates)
│   ├── Detections (count + pass rate)
│   ├── Latency (avg/min/max)
│   ├── Ground Truth (match rate)
│   └── Hardware (status)
├── ✅ VIDEO SELECTOR (only for multi-video)
├── ✅ TIMELINE VISUALIZATION (visual only)
├── ✅ ONE DETECTION EVENTS TABLE (single source of truth)
└── Export Options (clear actions)

[Hidden: Debug Info Panel - accessible via toggle]

USER SEES: "OK, test PASSED, 12/12 detections good,
            here's the detailed table. Clear!"
```

---

## Mobile Responsive Layout

### Desktop (1200px+):
```
┌──────────────────────────────────────────────────────────────┐
│  TEST RESULT: PASS ✅                                        │
│  12/12 detections passed (100%)                              │
└──────────────────────────────────────────────────────────────┘

┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
│ DETECTIONS │ │  LATENCY   │ │ GROUND TR. │ │  HARDWARE  │
│   12/12    │ │  Avg: 45ms │ │ Match:100% │ │ Connected  │
└────────────┘ └────────────┘ └────────────┘ └────────────┘
```

### Tablet (768px - 1199px):
```
┌──────────────────────────────────────────────────────────────┐
│  TEST RESULT: PASS ✅                                        │
│  12/12 detections passed (100%)                              │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────┐ ┌──────────────────────────┐
│     DETECTIONS           │ │      LATENCY             │
│       12/12              │ │     Avg: 45ms            │
└──────────────────────────┘ └──────────────────────────┘

┌──────────────────────────┐ ┌──────────────────────────┐
│    GROUND TRUTH          │ │      HARDWARE            │
│    Match: 100%           │ │     Connected            │
└──────────────────────────┘ └──────────────────────────┘
```

### Mobile (< 768px):
```
┌────────────────────────────┐
│  TEST RESULT: PASS ✅      │
│  12/12 passed (100%)       │
└────────────────────────────┘

┌────────────────────────────┐
│  DETECTIONS                │
│  12/12 • 100% Pass         │
└────────────────────────────┘

┌────────────────────────────┐
│  LATENCY                   │
│  Avg: 45ms (32-67ms)       │
└────────────────────────────┘

┌────────────────────────────┐
│  GROUND TRUTH              │
│  Match: 100%               │
└────────────────────────────┘

┌────────────────────────────┐
│  HARDWARE                  │
│  ✅ LabJack T7 Connected   │
└────────────────────────────┘
```

---

## Color Coding Guide

### Status Colors:
- **Green (#4CAF50):** PASS, Connected, Success
- **Red (#F44336):** FAIL, Disconnected, Error
- **Yellow (#FFC107):** Warning, Misaligned
- **Blue (#2196F3):** Info, Running, Processing

### Table Row Colors:
```
┌───────────────────────────────────────────┐
│ Frame │ Time   │ Latency │ Status        │
├───────┼────────┼─────────┼───────────────┤
│   0   │ 0.041s │  45ms   │  ✅ PASS     │ ← Light green background
│   2   │ 0.103s │  52ms   │  ✅ PASS     │ ← Light green background
│   5   │ 0.234s │  152ms  │  ❌ FAIL     │ ← Light red background
│   7   │ 0.289s │  43ms   │  ✅ PASS     │ ← Light green background
└───────┴────────┴─────────┴───────────────┘
```

### Card Emphasis:
```
NORMAL CARD:
┌────────────────┐
│  DETECTIONS    │
│     12/12      │ ← Normal text
│   100% Pass    │
└────────────────┘

HIGHLIGHTED CARD (when issue detected):
┏━━━━━━━━━━━━━━━━┓
┃  DETECTIONS    ┃
┃     8/12       ┃ ← Bold red text
┃   67% Pass     ┃ ← Warning color
┗━━━━━━━━━━━━━━━━┛
```

---

## Component Breakdown

### 1. TestStatusBanner (NEW)
**Purpose:** Immediately show overall test result
**Props:**
- `status: 'PASS' | 'FAIL'`
- `passRate: number`
- `totalDetections: number`
- `passedDetections: number`
- `threshold: number`

### 2. MetricsSummaryCards (NEW)
**Purpose:** Show 4 key metrics in grid
**Props:**
- `detections: { total, passed, failed }`
- `latency: { avg, min, max, threshold }`
- `groundTruth: { precision, recall, f1 } | null`
- `hardware: { connected, model, version }`

### 3. VideoSelector (NEW - multi-video only)
**Purpose:** Select and show current video in sequence
**Props:**
- `videos: VideoFile[]`
- `currentVideoIndex: number`
- `onVideoChange: (index: number) => void`
- `sequenceProgress: number`

### 4. DetectionEventsTable (NEW)
**Purpose:** Single source of truth for detection events
**Props:**
- `events: DetectionEvent[]`
- `showGroundTruth: boolean`
- `onEventClick?: (event: DetectionEvent) => void`

### 5. FrameCorrelationTimeline (KEEP - but clarify it's visual)
**Purpose:** Visual timeline correlation
**Props:** (existing)
**Change:** Add clear label "Visual Timeline - Details in table below"

### 6. HILResultsContainer (REFACTORED)
**Purpose:** Orchestrate all components
**Responsibilities:**
- Data loading
- State management (< 10 useState)
- Route event handlers
- Conditional rendering (multi-video vs single)

---

## User Journey Comparison

### BEFORE (Current):
1. User lands on page
2. Sees "HIL Test Results" header
3. ❓ Sees debug timing card - "What is this?"
4. Sees "Status: COMPLETED" - "Did it pass or fail?"
5. Scrolls through 6 metric cards - "Which one matters?"
6. Sees detection events table - "OK, 12 detections"
7. Scrolls more...
8. ❌ Sees ANOTHER table with same 12 events - "Wait, is this 24 total?"
9. Confused, scrolls back up
10. Tries to understand if test passed
11. **FRUSTRATED**

### AFTER (Proposed):
1. User lands on page
2. Sees "HIL Test Results" header
3. ✅ Sees big green "TEST RESULT: PASS" banner - **IMMEDIATELY KNOWS**
4. Sees 4 clear metric cards - "12/12 detections, 45ms avg latency, all matched"
5. Sees timeline visualization - "Visual confirmation of alignment"
6. Sees ONE table with all 12 events - "Here are the details"
7. **SATISFIED**

Time to understand: **45 seconds → 10 seconds** (75% reduction!)

---

## Implementation Notes

### Phase 1: Quick Wins (2-3 hours)
1. Add TestStatusBanner at top
2. Hide debug timing card
3. Remove duplicate timeline table
4. Consolidate 6 cards → 4 cards

**Result:** User confusion eliminated immediately

### Phase 2: Component Extraction (1-2 days)
1. Extract MetricsSummaryCards
2. Extract DetectionEventsTable
3. Extract VideoSelector
4. Refactor HILResultsContainer

**Result:** Maintainable codebase

### Phase 3: Polish (1 day)
1. Add loading states
2. Add empty states
3. Improve error handling
4. Add responsive design
5. Add export functionality

**Result:** Production-ready UI

---

## Testing Checklist

### Visual Testing:
- [ ] PASS status shows green banner
- [ ] FAIL status shows red banner
- [ ] 4 metric cards display correctly
- [ ] Single detection table shows all events
- [ ] Timeline is clearly visual (not duplicate data)
- [ ] No debug info visible by default
- [ ] Mobile responsive (all breakpoints)

### Functional Testing:
- [ ] Data loads correctly from API
- [ ] Video selector works (multi-video)
- [ ] Export functions work
- [ ] Refresh updates data
- [ ] Auto-refresh works (running tests)
- [ ] Error states display properly
- [ ] Empty states display properly

### User Testing:
- [ ] User can identify PASS/FAIL in < 5 seconds
- [ ] User can find detection count in < 10 seconds
- [ ] User reports "clear and easy to understand"
- [ ] User does NOT report "confusing" or "duplicate info"

---

## Success Metrics

**Before:**
- Time to understand result: ~45 seconds
- User confusion reports: High
- File size: 2,423 lines
- Components: 1 monolithic file
- Duplicate displays: 2+ tables

**After:**
- Time to understand result: ~10 seconds (75% improvement)
- User confusion reports: None
- File size: < 500 lines (main container)
- Components: 6-8 focused components
- Duplicate displays: 0 (single source of truth)

**ROI:**
- Development time: 3-4 days
- Maintenance savings: 50% reduction in bug reports
- User satisfaction: High
- Future feature additions: Much easier (modular components)
