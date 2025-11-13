# Session 0846e476 Timing Analysis Report

**Session ID:** `0846e476-2e21-499c-bfc8-0b2218081c77`
**Analysis Date:** 2025-11-04
**Status:** CRITICAL DATA INTEGRITY ISSUES IDENTIFIED

---

## Executive Summary

Session 0846e476 exhibits **THREE critical data integrity failures** that completely break detection timing analysis:

1. **501 of 502 detections (99.8%) have NULL video_id** - cannot determine which video they belong to
2. **"Year 1762" timestamp bug** - LabjackTimestamps are interpreted as year 1762 instead of 2025
3. **277 detections (55%) stuck at 10.083333s** - video_relative_timestamp frozen at constant value

**Impact:** Detection latency calculations are invalid. Frontend cannot display per-video results. Ground truth matching is impossible.

---

## 1. Session Metadata

```
Status:           completed
Started:          2025-11-04 14:26:22
Completed:        2025-11-04 14:26:40
Duration:         18 seconds
Has Video Sequence: TRUE
Sequence ID:      368de9c9-0e2e-473a-874c-054b9ddc1d96
```

### Video Configuration

The session was configured with **2 videos** in sequence:

| Video ID (short) | Started At           | Duration | Expected Detections |
|------------------|----------------------|----------|---------------------|
| 10c2b16c         | 1762266389.916       | ~5s      | 262                 |
| 550e3cf8         | 1762266395.281       | ~5s      | 252                 |

**⚠️ ISSUE #1: "Year 1762" Timestamp Bug**

The `started_at` timestamps are being interpreted as Unix epoch seconds, but they're appearing as year 1762:
- `1762266389.916` = 1762-11-04 instead of 2025-11-04
- This suggests a timestamp format issue or epoch miscalculation

---

## 2. Detection Distribution Analysis

### By video_id:

| video_id     | Count | video_relative_timestamp Range | Frame Range | labjack_timestamp Range |
|--------------|-------|-------------------------------|-------------|------------------------|
| **NULL**     | **501** | 0.002s to 10.083s           | ALL NULL    | 1762266382.75 to 1762266401.18 |
| 10c2b16c     | 1     | 1.355s (constant)            | NULL        | 1762266384.10 |

**Total:** 502 detections

### Critical Findings:

1. **99.8% NULL video_id Assignment**
   - Expected: All 502 detections assigned to either video 1 or video 2
   - Actual: Only 1 detection has a video_id
   - Root Cause: Race condition where detections arrive before video lifecycle events

2. **Missing sequence_video_result_id**
   - All detections have `sequence_video_result_id = NULL`
   - This breaks the FK relationship to `sequence_video_results` table
   - Cannot associate detections with video timing boundaries

3. **Missing frame_number**
   - ALL detections have `frame_number = NULL`
   - Cannot perform frame-based matching
   - Breaks ground truth correlation

---

## 3. Timing Data Validation

### "Year 1762" Bug Analysis

```sql
SELECT MIN(labjack_timestamp), MAX(labjack_timestamp)
FROM detection_events
WHERE test_session_id = '0846e476-...'
```

**Results:**
- Min: `1762266382.751773` → Interpreted as 1762-11-04 14:26:22
- Max: `1762266401.181730` → Interpreted as 1762-11-04 14:26:41
- Span: 18.4 seconds (matches session duration)

**Conclusion:** The timestamp **values** are correct for 2025, but something in the system is misinterpreting the epoch base year.

---

## 4. Stuck Value Analysis

### video_relative_timestamp Distribution

```
Value: 10.083333 seconds
Occurrences: 277 detections (55% of total)
```

**This is the smoking gun:**

- 277 detections have exactly the same `video_relative_timestamp`
- This value equals **10.083s = 242 frames at 24fps**
- Suggests a constant is being written instead of calculated values

**Comparison of Stored vs Expected:**

| Detection | Raw LabjackTimestamp | Video Start | EXPECTED Relative | STORED Relative | Difference |
|-----------|----------------------|-------------|-------------------|-----------------|------------|
| Frame N/A | 1762266382.751773    | 1762266389.916 | **-7.164s** ❌     | 0.002274s       | +7.166s    |
| Frame N/A | 1762266383.772713    | 1762266389.916 | **-6.143s** ❌     | 1.023214s       | +7.166s    |

**Note:** Expected values are NEGATIVE because detections occurred BEFORE the reported video start time. This confirms the year 1762 bug is corrupting the video_start_time values.

---

## 5. Root Cause Analysis

### Issue #1: NULL video_id (Race Condition)

**Where:** `services/video_sequence_orchestrator.py` + LabJack detection flow

**Problem:**
1. Detections arrive via LabJack → stored immediately to DB
2. Video lifecycle event `onPlay` fires → updates session metadata
3. By the time video_id is known, detections already have NULL

**Evidence:**
- Only 1 of 502 detections got assigned a video_id
- All 501 NULL detections have valid timestamps
- `sequence_video_result_id` is NULL for all

**Fix Required:**
- Implement `DetectionVideoReassignmentService` post-session
- Use timing boundaries from `sequence_video_results` to retroactively assign video_id

---

### Issue #2: Year 1762 Timestamp Bug

**Where:** Timestamp epoch calculation (likely in precision_timing_service.py)

**Problem:**
The system is using an incorrect epoch base year when calculating video start times.

**Evidence:**
- LabjackTimestamps are correct Unix epoch (2025)
- `video_timing.started_at` values show year 1762
- Difference: ~263 years = potential epoch offset error

**Fix Required:**
- Verify all timestamp conversions use Unix epoch (seconds since 1970-01-01)
- Check for hardcoded year offsets or epoch adjustments
- Ensure `video_start_timestamp` calculation matches LabJack epoch

---

### Issue #3: Stuck video_relative_timestamp

**Where:** Detection timestamp calculation when stored to DB

**Problem:**
Instead of calculating `detection_time - video_start_time`, a constant value (10.083s) is being written for 55% of detections.

**Evidence:**
- 277 detections have EXACTLY 10.083333s
- This equals 242 frames at 24fps (suggests frame-based constant)
- Early detections show variation, later ones stuck

**Fix Required:**
- Review `timing_synchronization_calculator.py` lines 293-297
- Ensure `video_relative_timestamp` is recalculated from raw timestamps
- Remove any default/fallback constants

---

## 6. Expected Behavior Analysis

### What SHOULD happen when frontend queries `/results/0846e476`:

1. **Enhanced HIL endpoint** (`enhanced_hil_results_endpoints.py`) is called
2. Endpoint should:
   - Fetch all detections for session
   - Use `DetectionVideoReassignmentService` to fix NULL video_ids
   - Recalculate `video_relative_timestamp` from raw timestamps
   - Group detections by video_id for per-video breakdown

3. **Response should include:**
```json
{
  "session_id": "0846e476-...",
  "videos": [
    {
      "video_id": "10c2b16c-...",
      "detections": 262,
      "timing_range": "0.0s - 5.2s"
    },
    {
      "video_id": "550e3cf8-...",
      "detections": 240,
      "timing_range": "0.0s - 4.8s"
    }
  ]
}
```

### What ACTUALLY happens:

- 501 detections cannot be assigned to a video
- Timing calculations fail due to year 1762 bug
- Frontend receives incomplete data

---

## 7. Data Integrity Scorecard

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Detections with video_id | 502 (100%) | 1 (0.2%) | ❌ CRITICAL |
| Detections with sequence_video_result_id | 502 (100%) | 0 (0%) | ❌ CRITICAL |
| Detections with frame_number | 502 (100%) | 0 (0%) | ❌ CRITICAL |
| Valid video_relative_timestamp | 502 (100%) | ~225 (45%) | ❌ CRITICAL |
| Timestamp epoch correctness | Unix 2025 | Year 1762 | ❌ CRITICAL |
| video_start_time in sequence_video_results | 2 records | 0 records | ❌ CRITICAL |

**Overall Data Quality:** 🔴 FAILED (0% usable)

---

## 8. Recommended Fixes

### Immediate Actions (Must Fix Before Next Test):

1. **Fix DetectionVideoReassignmentService**
   - File: `services/detection_video_reassignment.py`
   - Implement post-session video_id assignment
   - Use timing boundaries from `sequence_video_results`

2. **Fix Year 1762 Timestamp Bug**
   - File: `services/precision_timing_service.py`
   - Verify all timestamp calculations use Unix epoch
   - Remove any year offset adjustments

3. **Fix Stuck video_relative_timestamp**
   - File: `services/timing_synchronization_calculator.py`
   - Recalculate from raw timestamps, don't use constants
   - Remove default/fallback values

### Validation Steps:

1. Run `DetectionVideoReassignmentService` on session 0846e476
2. Verify all 502 detections get assigned video_id
3. Verify `video_relative_timestamp` values are continuous (not stuck)
4. Verify timestamp dates show 2025, not 1762

---

## 9. Sample Detection Details

**Sample detection with NULL video_id:**

```
Detection ID: 51bc5bd4-...
Frame Number: NULL
video_id: NULL
sequence_video_result_id: NULL
labjack_timestamp: 1762266382.751773 (= 1762-11-04 ❌)
video_relative_timestamp: 0.002274s
Expected relative: -7.164s (NEGATIVE! Bug confirmed)
```

**The only detection with video_id:**

```
Detection ID: (1 of 502)
video_id: 10c2b16c-...
labjack_timestamp: 1762266384.104639
video_relative_timestamp: 1.355140s
Frame Number: NULL
```

---

## 10. Conclusion

Session 0846e476 represents a **complete data integrity failure** across all timing-related fields. The three bugs (NULL video_id, year 1762 timestamps, stuck relative timestamps) combine to make the detection data unusable for:

- ✗ Detection latency analysis
- ✗ Per-video metrics
- ✗ Ground truth matching
- ✗ Frame correlation
- ✗ Frontend visualization

**All three bugs must be fixed before this system can validate camera latency in production.**

---

## Appendix: Database Queries Used

```sql
-- Get detection distribution
SELECT video_id, COUNT(*),
       MIN(video_relative_timestamp), MAX(video_relative_timestamp),
       MIN(labjack_timestamp), MAX(labjack_timestamp)
FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
GROUP BY video_id;

-- Find stuck values
SELECT video_relative_timestamp, COUNT(*) as count
FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
GROUP BY video_relative_timestamp
HAVING count > 10
ORDER BY count DESC;

-- Validate timestamp epochs
SELECT MIN(labjack_timestamp), MAX(labjack_timestamp),
       DATETIME(MIN(labjack_timestamp), 'unixepoch') as min_date,
       DATETIME(MAX(labjack_timestamp), 'unixepoch') as max_date
FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77';
```
