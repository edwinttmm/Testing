# Database Investigation Summary

**Date:** 2025-10-01
**Test Session:** HIL Test 01/10/2025, 21:25:01
**Session ID:** `ff438fef-cf13-4628-a4eb-6a148cbd42a3`
**Investigator:** Research Agent

---

## Executive Summary

The failing test session shows "122 events" but displays no results because:

1. **0 detection events** were recorded (no actual detections occurred)
2. **122 ground truth objects** exist (expected reference data)
3. **The "122" is False Negatives** (122 expected - 0 detected = 122 missed)
4. **This is NOT a multi-video sequence** (single video test)

---

## Database Content Analysis

### Test Session Data
```yaml
ID: ff438fef-cf13-4628-a4eb-6a148cbd42a3
Name: "HIL Test 01/10/2025, 21:25:01"
Status: completed
Duration: 13 seconds (20:25:01 to 20:25:14)

Configuration:
  has_video_sequence: 0 (FALSE - single video)
  sequence_id: NULL
  sequence_metadata: NULL
  video_id: 4065181a-bfd1-4977-b845-a0ea53a071be
  tolerance_ms: 100
```

### Data Tables Content

| Table | Count | Notes |
|-------|-------|-------|
| `test_sessions` | 1 row | Session exists, marked complete |
| `ground_truth_objects` | **122 rows** | For video_id 4065181a-bfd1-4977-b845-a0ea53a071be |
| `detection_events` | **0 rows** | No detections recorded! |
| `video_test_sequences` | **0 rows** | Not a multi-video sequence |
| `sequence_video_results` | **0 rows** | No sequence results |

### Ground Truth Objects Sample
```
Frame 1: timestamp=0.000, class=pedestrian
Frame 2: timestamp=0.042, class=pedestrian
Frame 3: timestamp=0.083, class=pedestrian
...
Total: 122 objects across video duration
```

### Detection Events
```
(empty - no detections were recorded)
```

---

## Root Cause Analysis

### What Went Wrong

**The detection pipeline never executed during this test session.**

Possible causes:
1. T3 detection service not running/connected
2. LabJack hardware not connected
3. Video playback failure
4. Detection pipeline configuration error
5. Session created as "ground truth only" validation

### UI Behavior Analysis

**The UI is working correctly:**
- ✅ Identifies session as single-video (not sequence)
- ✅ Loads 122 ground truth objects
- ✅ Shows 0 detection events
- ✅ Calculates 122 false negatives (correct math: 122 - 0)
- ⚠️ **Displays "122" without context** (user confusion)

**The confusion:**
- User sees number "122" in UI
- Expects to see 122 detection results
- Sees empty detection table
- Doesn't understand "122" refers to false negatives, not detections

---

## UI Display Breakdown

### What Shows "122"

**Location 1: False Negatives Metric** (Most Likely)
```tsx
// Line 1467 in HILResults.tsx
<strong>False Negatives:</strong>
{Math.max(0, groundTruthEvents.length - hil.summary.totalTests)}
// Displays: 122 (122 GT - 0 detections)
```

**Location 2: Ground Truth Table**
```tsx
// Shows 122 rows of ground truth objects ✓
```

**Location 3: Detection Count**
```tsx
// Line 1382
{hil.summary.totalTests}
// Displays: 0
```

### What Shows "0"

- Detection Count: 0
- True Positives: 0
- False Positives: 0
- Precision: 0%
- Recall: 0%
- Pass Rate: 0%

---

## Data vs Expectations

### What Exists (Reality)
```
✓ Test session: created and completed
✓ Ground truth: 122 objects loaded
✓ Video reference: single video linked
✗ Detection events: NONE
✗ Sequence data: NONE (not a sequence test)
```

### What UI Expects (for full results)
```
Required:
  ✓ Test session
  ✓ Ground truth objects
  ✗ Detection events (MISSING)

Optional (for multi-video):
  ✗ video_test_sequences (N/A - single video)
  ✗ sequence_video_results (N/A - single video)
```

### The Gap
```
Expected: 122 detection events matching 122 ground truth objects
Actual:   0 detection events
Result:   122 false negatives (missed detections)
```

---

## Recommended Actions

### Immediate: Fix UI Clarity

**Update HILResults.tsx to show:**
```tsx
{detectionCount === 0 && groundTruthCount > 0 && (
  <Alert severity="error" sx={{ mb: 3 }}>
    <AlertTitle>No Detections Recorded</AlertTitle>
    This test session has {groundTruthCount} ground truth objects but
    recorded 0 detection events. This indicates the detection pipeline
    did not execute during the test.

    <Box sx={{ mt: 2 }}>
      <strong>Possible causes:</strong>
      <ul>
        <li>T3 detection service not running</li>
        <li>LabJack hardware not connected</li>
        <li>Video playback failure</li>
        <li>Detection pipeline configuration error</li>
      </ul>
    </Box>

    <Button variant="contained" sx={{ mt: 2 }}>
      Re-run Detection
    </Button>
  </Alert>
)}
```

### Short-term: Add Session Validation

**Verify detection pipeline before test:**
```python
# In backend before starting test
async def validate_detection_pipeline():
    if not t3_service.is_connected():
        raise HTTPException(400, "T3 detection service not available")
    if not labjack_service.is_connected():
        raise HTTPException(400, "LabJack hardware not connected")
    # ... other checks
```

### Long-term: Improve Test Workflow

1. **Pre-test validation:** Check all required services
2. **Real-time monitoring:** Alert if detections stop during test
3. **Post-test validation:** Verify expected detection count
4. **Session types:** Distinguish "ground truth only" vs "full detection"

---

## Technical Details

### File Locations

**Frontend:**
```
/home/rigade/Testing/ai-model-validation-platform/frontend/src/
  ├── pages/HILResults.tsx (line 1382, 1451, 1467)
  ├── components/VideoSequenceResults.tsx
  └── services/api.ts
```

**Backend:**
```
/home/rigade/Testing/ai-model-validation-platform/backend/
  ├── routers/test_sessions.py
  ├── services/t3_service.py
  └── dev_database.db
```

### Database Schema

**Relevant tables:**
- `test_sessions` - Session metadata and configuration
- `ground_truth_objects` - Expected detection objects (122 rows)
- `detection_events` - Actual detections (0 rows) ← **THE PROBLEM**
- `video_test_sequences` - Multi-video sequence data (N/A for this test)
- `sequence_video_results` - Per-video sequence results (N/A for this test)

### API Endpoints Used

```
GET /api/test-sessions/{session_id}
  → Returns: has_video_sequence = 0, video_id = 4065181a...

GET /api/enhanced-results/{session_id}
  → Returns: total_detections = 0, detection_events = []

GET /api/videos/{video_id}/ground-truth
  → Returns: 122 ground truth objects

GET /api/video-sequences/{session_id}/results
  → Not called (isSequence = false)
```

---

## Conclusion

### The Mystery Solved

**"122 events"** refers to **122 False Negatives**, not 122 detection events.

- Ground Truth Objects: **122** ✓
- Detection Events: **0** ✗
- False Negatives: **122** (all objects missed)

### The Fix

**UI Change Required:**
Update the false negatives display to clearly indicate what the number represents:

```tsx
<Alert severity="warning">
  <strong>False Negatives: 122</strong>
  <br/>
  All {groundTruthEvents.length} ground truth objects were missed
  because no detections were recorded.
</Alert>
```

### Next Steps

1. ✅ **Document findings** (this file)
2. ⏭️ **Update UI** to clarify false negatives display
3. ⏭️ **Add detection validation** before test execution
4. ⏭️ **Investigate why** detection pipeline didn't run
5. ⏭️ **Re-run test** with proper detection enabled

---

## Quick Reference

```bash
# View test session
sqlite3 backend/dev_database.db \
  "SELECT * FROM test_sessions WHERE id='ff438fef-cf13-4628-a4eb-6a148cbd42a3'"

# View ground truth objects (122 rows)
sqlite3 backend/dev_database.db \
  "SELECT COUNT(*) FROM ground_truth_objects WHERE video_id='4065181a-bfd1-4977-b845-a0ea53a071be'"

# View detection events (0 rows)
sqlite3 backend/dev_database.db \
  "SELECT COUNT(*) FROM detection_events WHERE test_session_id='ff438fef-cf13-4628-a4eb-6a148cbd42a3'"
```

---

**Report Generated:** 2025-10-01
**Status:** Investigation Complete ✅
**Action Required:** UI Update & Detection Pipeline Verification
