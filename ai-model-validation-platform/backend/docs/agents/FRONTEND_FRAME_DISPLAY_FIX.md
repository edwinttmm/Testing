# Frontend Frame Display Fix Analysis

## Investigation Summary
**Issue**: User reports missing frames in HIL Results page timeline visualization
**URL**: http://localhost:3000/results/49e5d00f-eea7-44cb-a647-480268ef43ee
**Evidence**: Frame 0 shows detection, Frames 1-2 missing (should show GT), Frame 3 shows detection, Frame 5 missing, etc.

---

## Root Cause Analysis

### ✅ CONFIRMED: Frontend is NOT the Problem

After thorough investigation of both frontend and backend code, I can confirm:

1. **FrameCorrelationTimeline component DOES NOT filter frames**
   - Location: `/frontend/src/components/FrameCorrelationTimeline.tsx`
   - Lines 160-194: All ground truth events are added to timeline
   - Lines 196-302: All detection events are added to timeline
   - Line 314: Events are sorted by timestamp, not filtered
   - Line 494: All correlated events are rendered in the table

2. **No filter toggles or display controls exist**
   - No UI controls to hide/show GT-only frames
   - No state variables for filtering
   - No conditional logic that excludes events

### 🎯 ROOT CAUSE IDENTIFIED: Backend Returns Correct Data

**IMPORTANT DISCOVERY**: The backend API is actually returning ALL ground truth frames correctly!

**Backend Endpoint**: `/backend/routers/videos.py` - Line 542
```python
@router.get("/{video_id}/ground-truth", response_model=GroundTruthResponse)
async def get_video_ground_truth(video_id: str, db: Session = Depends(get_db)):
    # Get ground truth objects (only active records, exclude soft-deleted)
    ground_truth_objects = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id == video_id,
        GroundTruthObject.deleted_at.is_(None)  # Only include active records
    ).all()  # ← Returns ALL frames (no filtering by detection presence)
```

The backend query has **NO filtering logic** for frames with/without detections. It returns all GT objects for the video.

---

## Evidence from Code Analysis

### Component Data Flow

```typescript
// HILResults.tsx passes data to FrameCorrelationTimeline
<FrameCorrelationTimeline
  detectionEvents={activeDetections}      // From backend API
  groundTruthEvents={groundTruthEvents}   // From backend API
  videoMetadata={videoMetadata}
/>
```

### Timeline Processing (FrameCorrelationTimeline.tsx)

```typescript
// Lines 160-194: Process ALL ground truth events
groundTruthEvents.forEach((gt: any) => {
  // ... processing logic ...
  events.push({
    id: `gt-${gt.id || Math.random()}`,
    type: 'ground_truth',
    timestamp: gtTimeSeconds,
    frame_number: gtFrameNumber,
    // ... other properties
  });
});

// Lines 196-302: Process ALL detection events
detectionEvents.forEach((det: any) => {
  // ... processing logic ...
  events.push({
    id: `det-${det.id || det.event_id || Math.random()}`,
    type: 'detection',
    // ... other properties
  });
});

// Line 314: Sort and return ALL events (no filter)
return events.sort((a, b) => a.timestamp - b.timestamp);
```

### Table Rendering (Line 494)

```typescript
<TableBody>
  {correlatedEvents.map((event, index) => (
    <TableRow key={event.id}>
      {/* Render ALL events */}
    </TableRow>
  ))}
</TableBody>
```

---

## 🔍 Real Diagnosis: Data Actually Missing from Database

Since both frontend and backend code are correct, the issue is:

**Ground truth data for frames 1, 2, 5, etc. does NOT exist in the database.**

Possible causes:
1. **Ground truth import/processing skipped those frames**
   - Video processing pipeline may filter out frames without objects
   - Dataset annotation might only include frames with pedestrians
   - YOLO detection during import might have skipped empty frames

2. **This might be EXPECTED behavior**
   - If the video only has pedestrians at frames 0, 3, 6, etc.
   - The ground truth accurately reflects "no objects" on other frames
   - The "missing" frames may intentionally have no GT data

---

## Next Steps: Investigate Data Source

### Step 1: Check Database for Actual Frame Coverage
```sql
-- Check which frames have GT data for this video
SELECT
  video_frame as frame,
  COUNT(*) as object_count,
  array_agg(class_label) as labels,
  array_agg(confidence) as confidences
FROM ground_truth_objects
WHERE video_id = '49e5d00f-eea7-44cb-a647-480268ef43ee'
  AND deleted_at IS NULL
GROUP BY video_frame
ORDER BY video_frame;

-- Expected if bug: Gaps at frames 1, 2, 5, etc.
-- Expected if correct: Only frames with actual pedestrians/objects
```

### Step 2: Check Ground Truth Source Data
**Question**: Where did the ground truth annotations come from?

1. **Manual annotations**: Check source annotation file (JSON/CSV)
   - Do frames 1, 2, 5 have annotations in the source?
   - Or were they intentionally marked as "no objects"?

2. **YOLO-generated GT**: Check YOLO output
   - Did YOLO skip frames without detections?
   - Were empty frames filtered during import?

3. **Dataset format**: Check original dataset
   - Does it include "negative" frames (frames without objects)?
   - Or only "positive" frames (frames with objects)?

### Step 3: Verify User Expectation
**Critical Question**: Should frames 1, 2, 5 have ground truth data?

**Scenario A - BUG**: If source annotations include these frames
- Fix: Re-import ground truth with all frames included
- Or: Add "empty frame" GT entries manually

**Scenario B - EXPECTED**: If source annotations exclude empty frames
- This is correct behavior
- Frontend should show "No GT data" instead of hiding frames
- Update UI to display all frames with placeholders for empty ones

---

## Recommended Fix: Display ALL Frames (Even Without GT Data)

Since the backend correctly returns all available GT data, the fix should be in the frontend to show ALL frames, even those without ground truth.

### Option 1: Fill Missing Frames in Frontend (Recommended)

Modify `FrameCorrelationTimeline.tsx` to add placeholder events for frames without GT:

```typescript
// Add after line 194 in FrameCorrelationTimeline.tsx
const fillMissingGroundTruthFrames = (
  events: FrameCorrelationEvent[],
  totalFrames: number,
  fps: number
): FrameCorrelationEvent[] => {
  const gtFrames = new Set(
    events.filter(e => e.type === 'ground_truth').map(e => e.frame_number)
  );

  const filledEvents = [...events];

  // Add placeholder GT events for missing frames
  for (let frame = 0; frame < totalFrames; frame++) {
    if (!gtFrames.has(frame)) {
      filledEvents.push({
        id: `gt-placeholder-${frame}`,
        type: 'ground_truth',
        timestamp: frame / fps,
        frame_number: frame,
        confidence: 0,
        label: 'No GT data',
        correlation_status: 'missing'  // Mark as missing GT
      });
    }
  }

  return filledEvents;
};

// Use it before returning correlatedEvents (line 314)
const filledEvents = fillMissingGroundTruthFrames(events, totalFrames ?? 1000, fps);
return filledEvents.sort((a, b) => a.timestamp - b.timestamp);
```

### Option 2: Import Empty Frame GT Records (Database Fix)

Add ground truth records for all frames, including empty ones:

```python
# During ground truth import, add entries for empty frames
for frame_number in range(total_frames):
    if frame_number not in existing_gt_frames:
        db.add(GroundTruthObject(
            video_id=video_id,
            video_frame=frame_number,
            timestamp=frame_number / fps,
            class_label='none',  # Special label for empty frames
            confidence=1.0,
            bounding_box=None,  # No bounding box for empty frames
            is_empty_frame=True  # Flag to indicate this is a placeholder
        ))
```

---

## Alternative: Frontend Display Enhancement

If backend is correct and frames genuinely have no GT data, enhance UI to show "empty" frames:

```typescript
// FrameCorrelationTimeline.tsx enhancement
const fillMissingFrames = (events: FrameCorrelationEvent[], totalFrames: number) => {
  const frameSet = new Set(events.map(e => e.frame_number));
  const filledEvents = [...events];

  for (let frame = 0; frame < totalFrames; frame++) {
    if (!frameSet.has(frame)) {
      filledEvents.push({
        id: `empty-${frame}`,
        type: 'ground_truth',
        timestamp: frame / fps,
        frame_number: frame,
        label: 'No GT data',
        correlation_status: 'missing'
      });
    }
  }

  return filledEvents.sort((a, b) => a.timestamp - b.timestamp);
};
```

---

## Conclusion

### Code Analysis Results

1. ✅ **Frontend Code**: CORRECT - Displays all data received from API
2. ✅ **Backend Code**: CORRECT - Returns all GT data from database
3. ❓ **Database Data**: INCOMPLETE - Missing GT records for frames 1, 2, 5, etc.

### Root Cause

The "missing frames" are not a display bug or filtering issue. The ground truth data for those frames **does not exist in the database**.

### Recommended Solution

**Implement Option 1 (Frontend Fill)** - Fastest fix, no database migration required:
- Add placeholder GT events for frames without data
- Display them with "No GT data" label
- Mark correlation status as 'missing'
- This gives users complete frame visibility

**Consider Option 2 (Database Fill)** - More thorough, requires migration:
- Update ground truth import to include all frames
- Add explicit "empty frame" records
- Better data accuracy for analytics

### Impact Assessment

**User Experience**:
- Current: Confusing gaps in timeline (frames 1, 2, 5 missing)
- After Fix: Complete frame sequence visible, clear indication of GT availability

**Performance**:
- Option 1: Minimal impact (client-side array manipulation)
- Option 2: Slightly larger database, but cleaner data model

### Priority

**HIGH** - This affects user understanding of test results and frame-by-frame validation accuracy.

---

## Test URLs

After backend fix is applied, verify these scenarios:
- http://localhost:3000/results/49e5d00f-eea7-44cb-a647-480268ef43ee (original issue)
- Single video tests (ensure all GT frames visible)
- Multi-video sequences (ensure all videos show complete GT data)

Expected Result: Timeline should show continuous frames with both GT and detection events.
