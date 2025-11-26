# Investigation: Why Early Frames (0, 1, 3, 4, 6, 8) Have No Detection Matched

## Problem Statement
- User applies constant voltage BEFORE detection starts
- 120+ detections are generated
- Pre-aggregation was implemented to pick closest detection per GT frame
- BUT frames 0, 1, 3, 4, 6, 8 still show "No detection" despite having detections

## Root Cause Analysis

### 1. Pre-Aggregation Tolerance Setting

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/optimal_matching_service.py:50-129`

The `pre_aggregate_detections_by_frame()` function uses a **tolerance_seconds** parameter to find matching detections:

```python
def pre_aggregate_detections_by_frame(
    ground_truth_times: List[float],
    detection_times: List[float],
    tolerance_seconds: float  # <-- This is the key parameter
) -> Tuple[List[float], List[int]]:
    for gt_idx, gt_time in enumerate(ground_truth_times):
        best_det_idx = None
        best_diff = float('inf')

        # Find closest detection within tolerance for this GT frame
        for det_idx, det_time in enumerate(detection_times):
            diff = abs(det_time - gt_time)

            if diff <= tolerance_seconds and diff < best_diff:  # <-- Must be within tolerance
                best_diff = diff
                best_det_idx = det_idx
```

**Key Finding:** If no detection is within `tolerance_seconds` of a GT frame, that frame gets **no match**.

### 2. Tolerance Value Used

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py:1149-1156`

```python
# tolerance_ms comes from test session (lines 276-279)
tolerance_ms = test_session.tolerance_ms or self.default_tolerance_ms

# Converted to seconds for matching
tolerance_seconds = tolerance_ms / 1000.0

# Passed to optimal matching
optimal_result = optimal_detection_matching(
    gt_times,
    det_times,
    tolerance_seconds,  # <-- Default is 0.1s (100ms)
    ...
)
```

**Default tolerance:** 100ms (0.1 seconds)

### 3. Video Frame Timing

At 24fps:
- Frame 0: 0.000s
- Frame 1: 0.042s  (42ms later)
- Frame 2: 0.083s  (83ms later)
- Frame 3: 0.125s  (125ms later)
- Frame 4: 0.167s  (167ms later)

### 4. The Critical Issue: Detection Startup Delay

**HYPOTHESIS:** The detection system has a startup delay, causing the FIRST detection to arrive **after** frame 1 or 2.

**Evidence to check:**
1. What is the timestamp of the **earliest detection**?
2. Is it after frames 0, 1, 3, 4, 6, 8?

Example scenario that would cause this:
```
GT Frame 0:  0.000s  <-- No detection yet (startup delay)
GT Frame 1:  0.042s  <-- No detection yet (startup delay)
FIRST DET:   0.090s  <-- Detection starts here
GT Frame 2:  0.083s  <-- Match found (0.090 - 0.083 = 7ms < 100ms) ✅
GT Frame 3:  0.125s  <-- No detection close enough ❌
GT Frame 4:  0.167s  <-- No detection close enough ❌
```

### 5. Timestamp Extraction Logic

**Location:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py:130-169`

```python
def extract_detection_video_time(
    detection: Any,
    video_timing_map: Dict[str, Dict[str, Any]] = {},
    session_start_time: Optional[float] = None
) -> Optional[float]:
    """Resolve the best available video-relative timestamp"""

    # Priority 1: video_relative_timestamp (preferred)
    # Priority 2: Calculate from epoch timestamp if available
    # Priority 3: Use raw timestamp
```

**Critical Questions:**
1. Are `video_relative_timestamp` fields populated for early detections?
2. If using epoch timestamps, is `session_start_time` correct?
3. Could there be a timing offset causing early frames to appear misaligned?

## Diagnostic Steps

### Step 1: Check Earliest Detection Timestamps

Query the database to see actual detection times:

```sql
-- Get earliest detections
SELECT id, timestamp, video_relative_timestamp, frame_number
FROM detection_events
WHERE test_session_id = '<session_id>'
ORDER BY timestamp
LIMIT 20;

-- Get early ground truth frames
SELECT id, timestamp, frame_number
FROM ground_truth_objects
WHERE video_id = '<video_id>'
  AND frame_number IN (0, 1, 3, 4, 6, 8)
ORDER BY frame_number;
```

### Step 2: Check Pre-Aggregation Logs

Look for log messages like:
```
GT[0]=0.000s -> No detection within tolerance
GT[1]=0.042s -> No detection within tolerance
```

These indicate no detection was close enough within 100ms.

### Step 3: Verify Tolerance Setting

Check what tolerance is actually used:
```python
# In ground_truth_matching_service.py line 279
self.logger.info(f"Using tolerance window: ±{tolerance_ms}ms")
```

### Step 4: Check Detection Distribution

Calculate the gap between GT frames and nearest detections:

```python
# For each missed GT frame
gt_time = <frame_time>
nearest_detection = min(detection_times, key=lambda t: abs(t - gt_time))
gap_ms = abs(nearest_detection - gt_time) * 1000
print(f"Frame {frame_num} at {gt_time}s: nearest detection at {nearest_detection}s (gap: {gap_ms:.1f}ms)")
```

## Potential Root Causes

### Scenario A: Detection System Startup Delay

**Symptoms:**
- Frames 0-1 have no detection
- First detection appears around frame 2-3

**Fix:**
- Adjust tolerance for early frames
- Or filter out GT frames before first detection

### Scenario B: Sparse Detection Pattern

**Symptoms:**
- Constant voltage generates detections, but with gaps
- Some frames naturally fall into gaps

**Fix:**
- Increase tolerance (e.g., 150ms or 200ms)
- Use temporal interpolation

### Scenario C: Timestamp Misalignment

**Symptoms:**
- Detections exist but timestamps don't align
- video_relative_timestamp is NULL or incorrect

**Fix:**
- Improve timestamp extraction logic
- Ensure video_relative_timestamp is populated

### Scenario D: Pre-Aggregation Bug

**Symptoms:**
- Detections exist within tolerance but aren't selected
- Pre-aggregation logic has a flaw

**Fix:**
- Debug pre_aggregate_detections_by_frame()
- Add detailed logging

## Recommended Debugging Script

Create a script to diagnose the exact issue:

```python
import sys
from database import SessionLocal
from sqlalchemy import text

def diagnose_early_frame_issue(session_id: str):
    db = SessionLocal()

    # Get detections
    det_query = text("""
        SELECT timestamp, video_relative_timestamp, frame_number
        FROM detection_events
        WHERE test_session_id = :session_id
        ORDER BY timestamp
        LIMIT 50
    """)
    detections = db.execute(det_query, {'session_id': session_id}).fetchall()

    # Get GT
    gt_query = text("""
        SELECT gt.timestamp, gt.frame_number
        FROM ground_truth_objects gt
        JOIN test_sessions ts ON gt.video_id = ts.video_id
        WHERE ts.id = :session_id
        ORDER BY gt.timestamp
        LIMIT 50
    """)
    ground_truths = db.execute(gt_query, {'session_id': session_id}).fetchall()

    print("=== EARLY DETECTIONS ===")
    for i, det in enumerate(detections[:10]):
        print(f"Det {i}: ts={det[0]:.6f}, video_rel={det[1]}, frame={det[2]}")

    print("\n=== EARLY GROUND TRUTH ===")
    for gt in ground_truths[:10]:
        print(f"GT Frame {gt[1]}: ts={gt[0]:.6f}")

    print("\n=== FRAME-TO-DETECTION GAPS ===")
    tolerance_ms = 100
    for gt in ground_truths[:15]:
        gt_time = gt[0]
        gt_frame = gt[1]

        # Find closest detection
        closest_det = min(detections, key=lambda d: abs(d[0] - gt_time))
        gap_ms = abs(closest_det[0] - gt_time) * 1000

        status = "✅ MATCH" if gap_ms <= tolerance_ms else "❌ NO MATCH"
        print(f"Frame {gt_frame:2d} (ts={gt_time:.3f}s): "
              f"closest det at {closest_det[0]:.3f}s, "
              f"gap={gap_ms:.1f}ms {status}")

    db.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        diagnose_early_frame_issue(sys.argv[1])
    else:
        print("Usage: python diagnose_early_frames.py <session_id>")
```

## Next Steps

1. **Run diagnostic script** to see actual timestamp values
2. **Check logs** for pre-aggregation debug output
3. **Verify tolerance setting** in test session
4. **Identify root cause** from one of the scenarios above
5. **Implement appropriate fix** based on findings

## Files to Examine

- `/backend/services/optimal_matching_service.py` (lines 50-129) - Pre-aggregation logic
- `/backend/services/ground_truth_matching_service.py` (lines 1114-1156) - Timestamp extraction and matching
- `/backend/config/timing_config.py` - Default tolerance settings
- Database: `detection_events` and `ground_truth_objects` tables
