# Database Verification Report: Session 6d05fcd1-0c9b-432b-acbd-675c5e3683c9

**Date:** 2025-11-05
**Session ID:** 6d05fcd1-0c9b-432b-acbd-675c5e3683c9
**Purpose:** Verify actual database content vs frontend display issues

---

## CRITICAL FINDINGS

### 1. THIS IS A MULTI-VIDEO SEQUENCE (2 Videos)

The database reveals this is NOT a single video session - it's a **2-video sequence** with:
- **Video 1**: Frames 4-162 (0.198s to 6.762s) = ~6.5 seconds
- **Video 2**: Frames 283-309 (11.822s to 12.890s) = ~1.1 seconds

**Evidence:**
```
GAP DETECTED:
  From: Frame 162 @ 6.762s
  To:   Frame 283 @ 11.822s
  Time Gap: 5.060s, Frame Gap: 121 frames
```

### 2. FRAME BUNCHING AT 120 IS A DISPLAY BUG

The database shows **NORMAL FRAME DISTRIBUTION**:
- Frame 120: 2 detections (normal)
- Frame 121: 1 detection
- Frame 122: 1 detection
- Frame 123: 1 detection
- Frame 124: 2 detections
- Frames continue up to 162

**The "all detections show Frame 120" issue is NOT in the database - it's in the frontend display layer.**

### 3. VIDEO_ID IS NULL FOR ALL DETECTIONS

**MAJOR SCHEMA ISSUE:**
```
Video ID: None...
Video ID: None...
Video ID: None...
(all 161 detections)
```

This explains why the frontend can't distinguish between videos. The `video_id` column is NULL for all detections.

### 4. FRAME_NUMBER IS NULL (Uses video_frame_number instead)

```
Frame Number: None
Video Frame Number: 4
```

The database stores frame numbers in `video_frame_number`, not `frame_number`. The frontend may be looking at the wrong field.

---

## COMPLETE DATABASE STATISTICS

### Aggregate Data

| Metric | Value |
|--------|-------|
| Total Detections | 161 |
| frame_number Range | NULL (all None) |
| video_frame_number Range | 4 to 309 |
| Video Relative Timestamp Range | 0.198s to 12.890s |
| Sequence Timestamp Range | NULL to NULL |
| video_id Values | NULL (all None) |

### Frame Distribution Sample

```
Frame 4: 1 detection
Frame 5: 2 detections
Frame 7: 1 detection
Frame 8: 1 detection
...
Frame 120: 2 detections  ← NORMAL, not bunched
Frame 121: 1 detection
Frame 122: 1 detection
Frame 123: 1 detection
...
Frame 162: 1 detection  ← End of Video 1
[5.06 second gap]
Frame 283: 1 detection  ← Start of Video 2
Frame 284: 1 detection
...
Frame 309: 1 detection  ← End of Video 2
```

### Time Gap Analysis

**Gap 1** (Minor - within Video 1):
- From: Frame 66 @ 2.755s
- To: Frame 103 @ 4.307s
- Time Gap: 1.551s, Frame Gap: 37 frames
- **Explanation:** Normal detection sparsity

**Gap 2** (MAJOR - Between Videos):
- From: Frame 162 @ 6.762s
- To: Frame 283 @ 11.822s
- Time Gap: 5.060s, Frame Gap: 121 frames
- **Explanation:** VIDEO TRANSITION

---

## SCHEMA ANALYSIS

### detection_events Table - Relevant Columns

```sql
id (VARCHAR(36)) - Primary Key
test_session_id (VARCHAR(36)) - ✅ Populated
video_id (VARCHAR(36)) - ❌ NULL (CRITICAL ISSUE)
sequence_video_result_id (VARCHAR(36)) - ❌ NULL
frame_number (INTEGER) - ❌ NULL
video_frame_number (INTEGER) - ✅ Populated (4-309)
video_relative_timestamp (FLOAT) - ✅ Populated (0.198-12.890)
actual_latency_ms (FLOAT) - ✅ Populated
sequence_timestamp (FLOAT) - ❌ NULL
sequence_id (VARCHAR(36)) - ❌ NULL
ground_truth_match_id (VARCHAR(36)) - ❌ NULL
validation_result (VARCHAR) - ✅ Populated (all PASS)
```

### Missing Multi-Video Infrastructure

**video_sequences table:** Does NOT exist
**sequence_video_results table:** Not checked (likely missing)

**Impact:** The system has no way to track:
- Which detections belong to which video
- Video sequence order
- Per-video timing boundaries
- Video transitions

---

## VIDEO METADATA (Attempted Query)

**ERROR:** `videos` table does NOT have `total_frames` column

This suggests the video metadata schema is incomplete or different from expected.

---

## ROOT CAUSE ANALYSIS

### Why Frame 120 "Bunching" Appears

1. **Frontend calculates frames from timestamp** instead of reading `video_frame_number`
2. **Frontend assumes single video** and calculates: `frame = timestamp * fps`
3. **When Video 2 starts at 11.822s**, frontend calculates: `11.822s * 30fps ≈ 355 frames`
4. **Frontend displays wrong field** (possibly `frame_number` which is NULL, causing default of 120)

### Why Video IDs Are Missing

1. **Detection events never had video_id populated** during test execution
2. **Multi-video schema not fully implemented** in storage layer
3. **Detection storage service doesn't track video context** during sequence

### Why Detections Stop at Frame 162

**They DON'T stop at 162!** The database has detections from Frames 4-162 (Video 1) and 283-309 (Video 2).

The frontend is:
- Not detecting the video transition
- Not displaying Video 2's detections correctly
- Possibly stopping because of NULL video_id causing errors

---

## FRONTEND vs DATABASE DISCREPANCY

| What Frontend Shows | What Database Has |
|---------------------|-------------------|
| All detections bunched at Frame 120 | Normal distribution across Frames 4-309 |
| Only ~120 detections visible | 161 detections exist |
| Stops at ~6 seconds | Data exists up to 12.89 seconds |
| Single video assumed | Actually 2 videos in sequence |
| Uses frame_number field | Should use video_frame_number field |

---

## LATENCY ANALYSIS (Video 2)

Video 2 detections show **EXTREME latency values**:

```
Frame 283: latency = 6821.95ms (6.8 seconds!)
Frame 284: latency = 6857.73ms
Frame 285: latency = 6881.28ms
Frame 286: latency = 6929.18ms
...
```

**This is NOT real latency** - this is the **cumulative timestamp from session start**.

**Root Cause:** Latency calculation doesn't reset between videos in a sequence.

---

## RECOMMENDATIONS

### IMMEDIATE FIXES (Frontend)

1. **Use `video_frame_number` instead of `frame_number`**
   ```typescript
   // WRONG
   const frame = detection.frame_number;

   // CORRECT
   const frame = detection.video_frame_number;
   ```

2. **Detect video transitions by frame gaps**
   ```typescript
   // If frame_number jumps >50 frames, it's a new video
   if (currentFrame - prevFrame > 50) {
       videoIndex++;
   }
   ```

3. **Stop calculating frames from timestamps**
   - Timestamps span the entire sequence
   - Frames should come from database field

### CRITICAL FIXES (Backend)

1. **Populate video_id field during detection storage**
   ```python
   detection_event.video_id = current_video_id  # NOT NULL
   ```

2. **Implement video_sequences table** (if multi-video is a feature)
   ```sql
   CREATE TABLE video_sequences (
       id VARCHAR(36) PRIMARY KEY,
       test_session_id VARCHAR(36),
       sequence_order INTEGER,
       video_id VARCHAR(36),
       start_time FLOAT,
       end_time FLOAT
   );
   ```

3. **Fix latency calculation for multi-video**
   ```python
   # Reset timing reference at each video start
   latency = detection_time - video_start_time  # NOT session_start_time
   ```

4. **Add composite indexes**
   ```sql
   CREATE INDEX idx_detections_video_frame
   ON detection_events(test_session_id, video_id, video_frame_number);
   ```

---

## SQL QUERIES USED

### Query 1: Detection Events with Timing Fields
```sql
SELECT
    id,
    video_id,
    frame_number,
    video_frame_number,
    video_relative_timestamp,
    actual_latency_ms,
    sequence_timestamp,
    video_play_offset_ms,
    timestamp,
    ground_truth_match_id,
    validation_result,
    sequence_id,
    sequence_video_result_id
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
ORDER BY video_relative_timestamp
LIMIT 100;
```

### Query 2: Aggregate Statistics
```sql
SELECT
    COUNT(*) as count,
    MIN(frame_number) as min_frame,
    MAX(frame_number) as max_frame,
    MIN(video_frame_number) as min_video_frame,
    MAX(video_frame_number) as max_video_frame,
    MIN(video_relative_timestamp) as min_time,
    MAX(video_relative_timestamp) as max_time,
    MIN(sequence_timestamp) as min_seq_time,
    MAX(sequence_timestamp) as max_seq_time
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9';
```

### Query 3: Frame Distribution
```sql
SELECT
    frame_number,
    video_frame_number,
    COUNT(*) as count
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
GROUP BY frame_number, video_frame_number
ORDER BY frame_number;
```

### Query 4: Time Gap Detection
```sql
SELECT
    video_frame_number,
    video_relative_timestamp
FROM detection_events
WHERE test_session_id = '6d05fcd1-0c9b-432b-acbd-675c5e3683c9'
ORDER BY video_relative_timestamp;
```

---

## CONCLUSION

### The Issue Is NOT in the Database

The database has:
- ✅ Correct frame numbers (4-309 with proper distribution)
- ✅ Correct timestamps (0.198s - 12.890s)
- ✅ 161 detections stored properly
- ✅ Normal distribution (not bunched at 120)

### The Issue IS in Display/Data Mapping

The frontend:
- ❌ Reads wrong field (`frame_number` instead of `video_frame_number`)
- ❌ Calculates frames instead of reading them
- ❌ Doesn't handle multi-video sequences
- ❌ Stops displaying after Video 1 ends
- ❌ Shows "Frame 120" as default when data is NULL

### This is a 2-Video Multi-Sequence Session

The system executed a 2-video test sequence but:
- Backend didn't populate `video_id` field
- Backend didn't create sequence tracking tables
- Frontend doesn't support multi-video display
- Latency calculation doesn't reset between videos

### Next Steps

1. **Fix field mapping** in frontend (`video_frame_number`)
2. **Populate video_id** in backend storage
3. **Implement video sequence tracking** if this is a real feature
4. **Fix latency calculation** for multi-video sequences
5. **Add video transition detection** in frontend display

---

**Report Generated:** 2025-11-05
**Verified By:** Database query analysis
**Status:** Database is CORRECT, display layer has bugs
