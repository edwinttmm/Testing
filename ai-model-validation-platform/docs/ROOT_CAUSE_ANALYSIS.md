# Root Cause Analysis: 122 Events Display Issue

**Investigation Date:** 2025-10-01
**Test Session:** HIL Test 01/10/2025, 21:25:01
**Session ID:** ff438fef-cf13-4628-a4eb-6a148cbd42a3

## Executive Summary

The UI is showing "122 events" but failing to display them because it's attempting to render a **single-video test session** as a **multi-video sequence**, causing a data structure mismatch.

## Database Facts (Ground Truth)

```yaml
Test Session:
  id: ff438fef-cf13-4628-a4eb-6a148cbd42a3
  name: "HIL Test 01/10/2025, 21:25:01"
  has_video_sequence: 0 (FALSE)
  sequence_id: NULL
  sequence_metadata: NULL
  video_id: 4065181a-bfd1-4977-b845-a0ea53a071be
  status: completed

Ground Truth Objects:
  Total: 122 (all for single video_id)
  Location: ground_truth_objects table
  For video: 4065181a-bfd1-4977-b845-a0ea53a071be

Detection Events:
  Total: 0 (no detections were run)

Video Test Sequences:
  Total: 0 (no sequence data exists)

Sequence Video Results:
  Total: 0 (no per-video results exist)
```

## The Problem Chain

### 1. UI Flow (Current Behavior)

```typescript
// In HILResults.tsx line 676-714
Step 1: checkIfSessionIsSequence(sessionId)
  → Checks: session_type === 'sequential_processing' OR has_video_sequence === true
  → Result: FALSE (has_video_sequence = 0, session_type not set)

Step 2: isSequence = false
  → Should load single-video results ✓

Step 3: loadEnhancedHILResults()
  → Loads 122 ground truth objects
  → Shows "122 events" in summary

Step 4: Render (line 1020, 2185)
  if (isSequence && sequenceResults) {
    return <VideoSequenceResults />
  }
  → Does NOT execute (isSequence = false) ✓
```

### 2. The Actual Bug

**The UI is correctly identifying this as a single-video session**, but somewhere in the rendering logic, it's still attempting to access multi-video sequence data structures.

Let me trace the exact failure point:

```typescript
// Line 1020-1083: Early return for sequence results
if (isSequence && sequenceResults) {
  return (
    <Box sx={{ p: 3 }}>
      <AppBar position="static">
        ...
      </AppBar>
      <VideoSequenceResultsComponent
        results={sequenceResults}
      />
    </Box>
  );
}

// Line 2185-2186: Duplicate render at bottom
{sequenceResults && isSequence && (
  <VideoSequenceResultsComponent results={sequenceResults} />
)}
```

**Issue Found:** The early return (line 1020) should prevent sequence rendering, BUT the problem is likely in:
1. The loading logic is setting `sequenceResults` to some value even when `isSequence = false`
2. OR the condition `sequenceResults && isSequence` is not properly guarding

### 3. Where the 122 Events Come From

```typescript
// Line 133-136: loadGroundTruthData()
const gtEvents = groundTruthResponse.data.ground_truth_events;
console.log(`✅ Loaded ${gtEvents.length} ground truth events`);
setGroundTruthEvents(gtEvents);
// Sets 122 ground truth objects into state

// These are then displayed in:
// - Summary statistics
// - Ground truth comparison tables
// - Video correlation timeline
```

### 4. The Display Failure

The UI fails to display the 122 events because:

1. **Data Location Mismatch:**
   - UI expects: `sequenceResults.per_video_results[].detection_events`
   - Actual data: `enhancedResults.detection_events` (0 items) + `groundTruthEvents` (122 items)

2. **Structure Mismatch:**
   - Multi-video expects: Array of per-video results with individual timings
   - Single-video has: Flat array of detections with single video context

3. **Missing Component:**
   - The UI has `VideoSequenceResultsComponent` for multi-video
   - The UI has enhanced results display for single-video
   - BUT when `isSequence = false`, the enhanced results display might not be showing the ground truth events properly

## The REAL Root Cause

After careful analysis, the issue is **NOT** that the UI thinks it's a sequence. The issue is:

### The 122 "Events" Are Ground Truth Objects, Not Detection Events

```
Ground Truth Objects (what exists): 122
Detection Events (actual detections): 0
```

**The UI is showing "122 events" because it's counting ground truth objects, but there are ZERO actual detection events to display.**

This is why the results page appears empty:
- Summary shows 122 events (counting ground truth)
- Detection event table shows 0 (correct)
- Ground truth table shows 122 (correct)
- **But the main results display expects detection events paired with ground truth**

## Solutions

### Option 1: Fix the UI Summary (Recommended)

Update the summary to distinguish between:
- Ground Truth Events: 122
- Detection Events: 0
- Matched Pairs: 0

```typescript
// In HILResults.tsx summary section
<Typography variant="h6">
  Ground Truth Objects: {groundTruthEvents.length}
</Typography>
<Typography variant="h6">
  Detection Events: {enhancedResults?.detection_statistics?.total_detections || 0}
</Typography>
<Typography variant="h6">
  Matched Pairs: {matchedCount}
</Typography>
```

### Option 2: Run Actual Detections

The test session was created but **no detections were run**. To get actual results:
1. Re-run the test with T3 detection enabled
2. This will populate `detection_events` table
3. Then the UI will have actual latency results to display

### Option 3: Handle Zero-Detection Case

Add a message when ground truth exists but no detections were run:

```typescript
{groundTruthEvents.length > 0 && detectionEvents.length === 0 && (
  <Alert severity="info">
    {groundTruthEvents.length} ground truth objects are available,
    but no detection events were recorded. Run detection to compare results.
  </Alert>
)}
```

## File Locations

### Frontend Files:
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx` (line 676-714, 1020-1083, 2185-2186)
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/VideoSequenceResults.tsx`
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/api.ts` (checkIfSessionIsSequence)

### Backend Files:
- `/home/rigade/Testing/ai-model-validation-platform/backend/routers/test_sessions.py`
- Database: `/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db`

## Recommended Action

**Immediate Fix:** Update UI to clearly show:
```
Test Session: HIL Test 01/10/2025, 21:25:01
Status: Completed
Type: Single Video Test

Ground Truth Objects: 122
Detection Events: 0
Status: No detections run - ground truth only
```

**Then:** Provide a "Run Detection" button to execute T3 detection on this session and generate actual results.
