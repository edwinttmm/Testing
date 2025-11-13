# Data Flow Analysis: Test Session ff438fef-cf13-4628-a4eb-6a148cbd42a3

## Visual Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         TEST SESSION                             │
│  ID: ff438fef-cf13-4628-a4eb-6a148cbd42a3                       │
│  Name: "HIL Test 01/10/2025, 21:25:01"                          │
│  Type: Single Video (has_video_sequence = 0)                     │
│  Status: completed                                               │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ references
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                         VIDEO                                    │
│  ID: 4065181a-bfd1-4977-b845-a0ea53a071be                       │
│  Filename: [video file]                                          │
│  Ground Truth Ready: YES                                         │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ has
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GROUND TRUTH OBJECTS                           │
│  Count: 122                                                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Frame 1:  timestamp=0.000s, class=pedestrian           │     │
│  │ Frame 2:  timestamp=0.042s, class=pedestrian           │     │
│  │ Frame 3:  timestamp=0.083s, class=pedestrian           │     │
│  │ ...                                                     │     │
│  │ Frame 122: timestamp=[end], class=pedestrian           │     │
│  └────────────────────────────────────────────────────────┘     │
│  ✅ LOADED AND AVAILABLE                                        │
└─────────────────────────────────────────────────────────────────┘


                               ❌
                               │ MISSING
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DETECTION EVENTS                               │
│  Count: 0                                                        │
│  ┌────────────────────────────────────────────────────────┐     │
│  │                     (EMPTY)                             │     │
│  │                                                         │     │
│  │  Detection pipeline did not execute                     │     │
│  └────────────────────────────────────────────────────────┘     │
│  ❌ NOT POPULATED                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Data Table Comparison

| Table | Expected | Actual | Status |
|-------|----------|--------|--------|
| `test_sessions` | 1 session | ✅ 1 session | OK |
| `videos` | 1 video | ✅ 1 video | OK |
| `ground_truth_objects` | 122 objects | ✅ 122 objects | OK |
| `detection_events` | 122 events | ❌ 0 events | **MISSING** |
| `test_results` | 1 result | ? | Unknown |
| `detection_comparisons` | 122 comparisons | ❌ 0 comparisons | Missing |

## UI Data Flow

```
Frontend Request:
  GET /api/test-sessions/ff438fef-cf13-4628-a4eb-6a148cbd42a3
    │
    ▼
Backend Response:
  {
    id: "ff438fef-cf13-4628-a4eb-6a148cbd42a3",
    has_video_sequence: 0,          ← Single video flag
    video_id: "4065181a-...",
    status: "completed"
  }
    │
    ▼
Frontend Logic:
  isSequence = checkIfSessionIsSequence()
    → has_video_sequence === 0
    → Returns: FALSE
    │
    ▼
  Load Single-Video Results:
    loadEnhancedHILResults()
      │
      ├─→ Load detection events:
      │     API returns: detection_events = []
      │     Set: hil.summary.totalTests = 0
      │
      └─→ Load ground truth:
            API returns: ground_truth_objects = [122 items]
            Set: groundTruthEvents = [122 items]
    │
    ▼
Render Results:
  Detection Count: 0                  ← hil.summary.totalTests
  Ground Truth: 122                   ← groundTruthEvents.length
  False Negatives: 122                ← 122 - 0 = 122  ⚠️ USER SEES THIS
  True Positives: 0
  False Positives: 0
  Precision: 0%
  Recall: 0%
```

## The "122" Display Chain

### Where Users See "122"

```
Location 1: Ground Truth Table
  ┌──────────────────────────────────┐
  │  Ground Truth Objects (122)      │
  │  ┌────────────────────────────┐  │
  │  │ Frame | Time | Type        │  │
  │  │   1   | 0.00 | pedestrian  │  │
  │  │   2   | 0.04 | pedestrian  │  │
  │  │  ...  | ...  | ...         │  │
  │  │  122  | 5.08 | pedestrian  │  │
  │  └────────────────────────────┘  │
  └──────────────────────────────────┘

Location 2: False Negatives Metric
  ┌──────────────────────────────────┐
  │  Ground Truth Comparison         │
  │                                  │
  │  True Positives:     0           │
  │  False Positives:    0           │
  │  False Negatives:    122  ⚠️     │
  │                                  │
  │  (All ground truth missed)       │
  └──────────────────────────────────┘

Location 3: Recall Calculation
  ┌──────────────────────────────────┐
  │  Recall: 0.0%                    │
  │  (0 detected / 122 expected)     │
  └──────────────────────────────────┘
```

## Calculation Breakdown

### Detection Statistics
```python
total_ground_truth = 122        # From ground_truth_objects table
total_detections = 0            # From detection_events table
matched_detections = 0          # From detection_comparisons table

# Results:
true_positives = matched_detections = 0
false_positives = total_detections - matched_detections = 0 - 0 = 0
false_negatives = total_ground_truth - matched_detections = 122 - 0 = 122 ⚠️

# Metrics:
precision = true_positives / (true_positives + false_positives) = 0 / 0 = undefined → 0%
recall = true_positives / (true_positives + false_negatives) = 0 / 122 = 0%
f1_score = 2 * (precision * recall) / (precision + recall) = 0%
```

## Missing Pipeline Components

### Expected Detection Flow

```
1. Test Start
   ├─→ Load video: 4065181a-bfd1-4977-b845-a0ea53a071be
   ├─→ Load ground truth: 122 objects
   └─→ Initialize detection pipeline
       │
       ▼
2. Video Playback Loop
   ├─→ Frame 1: Play video frame
   │   ├─→ T3 Detection: Analyze frame
   │   ├─→ LabJack: Monitor voltage trigger
   │   └─→ Record: detection_event {timestamp, object, latency}
   │
   ├─→ Frame 2: Play video frame
   │   └─→ ... (repeat)
   │
   └─→ Frame 122: Play video frame
       └─→ ... (repeat)
       │
       ▼
3. Test Complete
   ├─→ 122 detection_events recorded ✅
   ├─→ Compare with ground truth
   ├─→ Calculate metrics (TP, FP, FN)
   └─→ Generate results
```

### Actual Flow (What Happened)

```
1. Test Start ✅
   ├─→ Load video: 4065181a-bfd1-4977-b845-a0ea53a071be ✅
   ├─→ Load ground truth: 122 objects ✅
   └─→ Initialize detection pipeline ❌ FAILED
       │
       ▼
2. Video Playback Loop ❌ SKIPPED
   (No detection events recorded)
       │
       ▼
3. Test Complete ✅
   ├─→ 0 detection_events recorded ❌
   ├─→ No comparison possible
   ├─→ Metrics all zero
   └─→ False Negatives = 122 (all missed)
```

## Root Cause Hypothesis

### Possible Failure Points

```
┌─────────────────────────────────────────────────┐
│  1. T3 Detection Service                        │
│     ┌─────────────────────────────────────┐    │
│     │ Status: Not Running / Not Connected │    │
│     │ Impact: No object detection         │    │
│     └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                     OR
┌─────────────────────────────────────────────────┐
│  2. LabJack Hardware                            │
│     ┌─────────────────────────────────────┐    │
│     │ Status: Not Connected               │    │
│     │ Impact: No voltage triggers         │    │
│     └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                     OR
┌─────────────────────────────────────────────────┐
│  3. Video Playback Pipeline                     │
│     ┌─────────────────────────────────────┐    │
│     │ Status: Failed / Not Configured     │    │
│     │ Impact: No frames processed         │    │
│     └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
                     OR
┌─────────────────────────────────────────────────┐
│  4. Detection Recording                         │
│     ┌─────────────────────────────────────┐    │
│     │ Status: Database write failure      │    │
│     │ Impact: Events not persisted        │    │
│     └─────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

## Validation Queries

### Check Session Data
```sql
SELECT
  id,
  name,
  has_video_sequence,
  sequence_id,
  status,
  started_at,
  completed_at,
  ROUND((JULIANDAY(completed_at) - JULIANDAY(started_at)) * 86400, 2) as duration_seconds
FROM test_sessions
WHERE id = 'ff438fef-cf13-4628-a4eb-6a148cbd42a3';

-- Result:
-- duration = 13 seconds
-- status = completed
-- has_video_sequence = 0
```

### Check Ground Truth
```sql
SELECT COUNT(*) as ground_truth_count
FROM ground_truth_objects
WHERE video_id = '4065181a-bfd1-4977-b845-a0ea53a071be';

-- Result: 122
```

### Check Detection Events
```sql
SELECT COUNT(*) as detection_count
FROM detection_events
WHERE test_session_id = 'ff438fef-cf13-4628-a4eb-6a148cbd42a3';

-- Result: 0  ❌
```

### Check Test Results
```sql
SELECT *
FROM test_results
WHERE test_session_id = 'ff438fef-cf13-4628-a4eb-6a148cbd42a3';

-- Result: ?
```

## Recommended Investigation Steps

1. **Check Backend Logs**
   ```bash
   # Look for errors during test execution
   grep -r "ff438fef-cf13-4628-a4eb-6a148cbd42a3" backend/logs/
   ```

2. **Verify T3 Service**
   ```bash
   # Check if T3 detection service was running
   ps aux | grep t3_detection
   curl http://localhost:8001/health  # T3 service health
   ```

3. **Check LabJack Connection**
   ```python
   # Test hardware connectivity
   from labjack import ljm
   handle = ljm.openS("T7", "USB", "ANY")
   print(f"Connected: {handle}")
   ```

4. **Review Video Playback**
   ```bash
   # Check if video was accessible
   ls -la /path/to/video/4065181a-bfd1-4977-b845-a0ea53a071be.*
   ```

5. **Database Transaction Log**
   ```sql
   -- Check if any detection inserts were attempted
   SELECT * FROM sqlite_sequence WHERE name = 'detection_events';
   ```

## Conclusion

The test session completed successfully from a **session management** perspective, but the **detection pipeline** never executed. This resulted in:

- ✅ Session created and tracked
- ✅ Ground truth loaded (122 objects)
- ❌ Detection pipeline failed (0 events)
- ❌ No results to display

**The "122"** users see is the **false negatives count** (all ground truth objects missed), NOT a count of detection events.

**Action Required:**
1. Fix UI to clarify false negatives display
2. Investigate and fix detection pipeline failure
3. Add pre-test validation checks
4. Re-run test with working detection pipeline
