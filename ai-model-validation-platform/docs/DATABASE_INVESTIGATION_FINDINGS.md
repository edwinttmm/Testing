# Database Investigation Findings - Multi-Video Sequence Issue

**Investigation Date:** 2025-10-01
**Test Session:** HIL Test 01/10/2025, 21:25:01
**Session ID:** ff438fef-cf13-4628-a4eb-6a148cbd42a3

## Critical Discovery: NO Multi-Video Data Exists

### Database Reality vs UI Expectations

#### What the Database Contains:
```
✓ Test Session: HIL Test 01/10/2025, 21:25:01
✓ Has video sequence: 0 (FALSE)
✓ Primary video_id: 4065181a-bfd1-4977-b845-a0ea53a071be
✓ Sequence ID: None
✓ Ground truth count in session: None
✓ Video test sequences count: 0
✓ Detection events: 0
✓ Ground truth objects: 122 (all for single video)
```

#### What the UI Expects:
- Multiple videos in a sequence
- Video playlist data
- Sequence timing information
- Per-video detection results
- Video transitions and playback coordination

### Root Cause Analysis

**THE FUNDAMENTAL PROBLEM:** The test session was created as a **SINGLE VIDEO TEST**, not a multi-video sequence test, but the UI is attempting to render it as a multi-video sequence.

### Database Schema Analysis

#### Tables Involved:
1. **test_sessions** - Contains session metadata
   - `has_video_sequence`: 0 (FALSE) ← **This is the key indicator**
   - `sequence_id`: None
   - `sequence_metadata`: None
   - `video_id`: Single video ID reference

2. **video_test_sequences** - Should contain sequence definitions
   - **NO ROWS** for this test session
   - Should have: video_ids (JSON array), sequence_order, total_videos

3. **sequence_video_results** - Should contain per-video results
   - **NO ROWS** for this test session
   - Should have: per-video latency, detection counts, pass rates

4. **ground_truth_objects** - Contains ground truth data
   - **122 objects** for the single video
   - All belong to video_id: 4065181a-bfd1-4977-b845-a0ea53a071be

5. **detection_events** - Contains actual detections
   - **0 events** - No detections were made during this test

### The Data Flow Problem

```
UI Request Flow:
1. HILResults component loads test session
2. Checks if session has video sequence (has_video_sequence = 0)
3. Attempts to load video playlist (doesn't exist)
4. Tries to render VideoSequenceResults (no sequence data)
5. FAILURE: Cannot display results

Actual Data Flow:
1. Test session created with single video
2. 122 ground truth objects loaded for that video
3. No detections were run (0 detection_events)
4. No sequence data was ever created
```

### Why the 122 Events Show in UI

The UI is likely:
1. Loading the 122 ground truth objects
2. Displaying them as if they were multi-video sequence events
3. Attempting to correlate them with non-existent video sequence data
4. Failing when it can't find the sequence metadata

### Missing Database Components

For a proper multi-video sequence test, we would need:

1. **test_sessions table:**
   ```sql
   has_video_sequence = 1
   sequence_id = 'some-uuid'
   sequence_metadata = '{"videos": [...], "timing": {...}}'
   ```

2. **video_test_sequences table:**
   ```sql
   INSERT INTO video_test_sequences (
     id, test_session_id, name, video_ids, sequence_order,
     total_videos, max_latency_ms
   ) VALUES (
     'seq-uuid', 'session-uuid', 'Sequence Name',
     '["video1-id", "video2-id", "video3-id"]',
     '[0, 1, 2]',
     3, 1000
   )
   ```

3. **sequence_video_results table:**
   ```sql
   INSERT INTO sequence_video_results (
     id, video_sequence_id, video_id, sequence_order,
     expected_detection_count, actual_detection_count, ...
   )
   ```

### Solution Paths

#### Option 1: Fix the UI (Recommended)
- Detect when `has_video_sequence = 0`
- Fall back to single-video rendering mode
- Don't attempt to load sequence data
- Display the 122 ground truth objects in single-video context

#### Option 2: Retrofit the Data (Complex)
- Create missing video_test_sequences entry
- Create sequence_video_results entries
- Update test_sessions.has_video_sequence to 1
- Migrate ground truth objects to sequence structure

#### Option 3: Re-run the Test (Clean)
- Use the proper multi-video sequence creation endpoint
- Ensure video_test_sequences is populated
- Run detections to populate detection_events
- Generate proper sequence_video_results

### Code Locations Affected

1. **Frontend:**
   - `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
   - `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/VideoSequenceResults.tsx`
   - `/home/rigade/Testing/ai-model-validation-platform/frontend/src/services/api.ts`

2. **Backend:**
   - `/home/rigade/Testing/ai-model-validation-platform/backend/routers/video_sequence_testing.py`
   - `/home/rigade/Testing/ai-model-validation-platform/backend/services/video_sequence_orchestrator.py`

### Immediate Action Required

**The UI must check `has_video_sequence` before attempting to render multi-video components:**

```typescript
// In HILResults.tsx
const renderResults = () => {
  if (!session.has_video_sequence) {
    // Render single-video results
    return <SingleVideoResults session={session} />;
  } else {
    // Render multi-video sequence results
    return <VideoSequenceResults session={session} />;
  }
};
```

### Test Data Creation Checklist

For future multi-video sequence tests, ensure:
- [ ] test_sessions.has_video_sequence = TRUE
- [ ] test_sessions.sequence_id is populated
- [ ] video_test_sequences table has entry with:
  - [ ] video_ids (JSON array of video IDs)
  - [ ] sequence_order (JSON array of positions)
  - [ ] total_videos count
- [ ] Each video has ground_truth_objects
- [ ] Detection run creates detection_events
- [ ] sequence_video_results generated for each video

### Conclusion

**This is NOT a multi-video sequence test.** The database confirms this is a single-video test with 122 ground truth objects and 0 detection events. The UI is incorrectly attempting to treat it as a multi-video sequence, causing the display failure.

The fix should be in the UI to properly detect and handle single-video tests differently from multi-video sequence tests.
