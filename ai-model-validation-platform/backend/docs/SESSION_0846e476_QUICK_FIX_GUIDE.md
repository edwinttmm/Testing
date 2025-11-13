# Session 0846e476 - Quick Fix Guide

## 🚨 Critical Issues Summary

**Session:** `0846e476-2e21-499c-bfc8-0b2218081c77`
**Total Detections:** 502
**Data Quality:** 🔴 0% usable

### The Three Bugs:

1. **501/502 detections have NULL video_id (99.8%)**
2. **Year 1762 timestamp bug** - all timestamps show wrong year
3. **277 detections stuck at 10.083333s (55%)**

---

## Quick Diagnosis Script

Run this to verify the bugs still exist:

```python
import sqlite3
conn = sqlite3.connect('dev_database.db')
cursor = conn.cursor()

session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'

# Check bug #1: NULL video_id count
cursor.execute("""
    SELECT
        COUNT(*) as total,
        COUNT(CASE WHEN video_id IS NULL THEN 1 END) as null_video_id
    FROM detection_events WHERE test_session_id = ?
""", (session_id,))
total, null_count = cursor.fetchone()
print(f"Bug #1: {null_count}/{total} detections have NULL video_id")

# Check bug #2: Year 1762
cursor.execute("""
    SELECT MIN(labjack_timestamp),
           DATETIME(MIN(labjack_timestamp), 'unixepoch')
    FROM detection_events WHERE test_session_id = ?
""", (session_id,))
min_ts, interpreted_date = cursor.fetchone()
print(f"Bug #2: Timestamp {min_ts} = {interpreted_date}")

# Check bug #3: Stuck values
cursor.execute("""
    SELECT video_relative_timestamp, COUNT(*)
    FROM detection_events
    WHERE test_session_id = ?
    GROUP BY video_relative_timestamp
    HAVING COUNT(*) > 10
    ORDER BY COUNT(*) DESC
    LIMIT 1
""", (session_id,))
stuck = cursor.fetchone()
if stuck:
    print(f"Bug #3: {stuck[1]} detections stuck at {stuck[0]}s")

conn.close()
```

**Expected output if bugs still exist:**
```
Bug #1: 501/502 detections have NULL video_id
Bug #2: Timestamp 1762266382.751773 = 1762-11-04 14:26:22
Bug #3: 277 detections stuck at 10.083333333333334s
```

---

## Fix #1: NULL video_id Assignment

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_video_reassignment.py`

**The service exists but wasn't called during session completion!**

### Immediate Fix:

```python
# Run this manually to fix session 0846e476
from services.detection_video_reassignment import reassign_null_video_ids

result = await reassign_null_video_ids(
    session_id='0846e476-2e21-499c-bfc8-0b2218081c77',
    dry_run=False  # Set to True to preview changes first
)

print(f"Reassigned: {result['reassigned_count']}")
print(f"Assignments: {result['video_assignments']}")
```

### Permanent Fix:

**File:** `services/session_completion_service.py` (add to session finalization)

```python
async def finalize_session(session_id: str):
    # ... existing code ...

    # NEW: Reassign video_id to detections based on timing
    from services.detection_video_reassignment import reassign_null_video_ids
    reassignment_result = await reassign_null_video_ids(session_id)
    logger.info(f"Video reassignment: {reassignment_result['reassigned_count']} detections fixed")
```

---

## Fix #2: Year 1762 Timestamp Bug

**Root Cause:** Timestamp epoch calculation using wrong base year.

### Where to Look:

1. **File:** `services/precision_timing_service.py`
   - Search for: `video_start_timestamp` calculation
   - Verify: All timestamps use Unix epoch (seconds since 1970-01-01)

2. **File:** `services/timing_synchronization_calculator.py` line 206-221
   - The `video_start_system_time` calculation
   - Check for year offset adjustments

### Expected Values:

```python
# Correct Unix epoch timestamp for 2025-11-04 14:26:22
expected_timestamp = 1730728002.0  # NOT 1762266382.0

# If you see timestamps in the 1762000000 range, the epoch is wrong
```

### Debug Print Statements to Add:

```python
# In precision_timing_service.py
import time
current_epoch = time.time()
logger.info(f"Current time: {current_epoch} = {datetime.fromtimestamp(current_epoch)}")
logger.info(f"Video start: {video_start_timestamp} = {datetime.fromtimestamp(video_start_timestamp)}")

if video_start_timestamp < current_epoch - 86400:
    logger.error(f"⚠️ TIMESTAMP BUG: Video start is {(current_epoch - video_start_timestamp)/86400:.1f} days in the past!")
```

---

## Fix #3: Stuck video_relative_timestamp

**Root Cause:** Constant value (10.083333s) written instead of calculated.

### Where to Fix:

**File:** `services/timing_synchronization_calculator.py` lines 293-303

**Current code:**
```python
# CRITICAL FIX: Calculate video_relative_timestamp (time since video started)
video_relative_timestamp = detection_system_time - video_start_system_time
logger.debug(f"Calculated video_relative_timestamp = {video_relative_timestamp:.6f}s")

# CRITICAL FIX: Calculate video_frame_number from video_relative_timestamp
fps = video_timing_metadata.fps if video_timing_metadata and video_timing_metadata.fps > 0 else 24.0
video_frame_number = int(video_relative_timestamp * fps)
```

**Check for:**
- Hardcoded fallback values
- Default constants
- Cached values not being updated

### Validation Query:

```sql
-- video_relative_timestamp should be continuous, not stuck
SELECT
    frame_number,
    video_relative_timestamp,
    labjack_timestamp,
    video_relative_timestamp - LAG(video_relative_timestamp) OVER (ORDER BY labjack_timestamp) as time_delta
FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
ORDER BY labjack_timestamp
LIMIT 20;
```

**Expected:** `time_delta` should vary (0.02s to 0.15s typical)
**Bug:** Many rows show `time_delta = 0.0` (stuck at same value)

---

## Validation Checklist

After applying fixes, verify:

- [ ] **All 502 detections have video_id assigned**
  ```sql
  SELECT COUNT(*) FROM detection_events
  WHERE test_session_id = '0846e476...' AND video_id IS NULL;
  -- Expected: 0
  ```

- [ ] **Timestamps show year 2025**
  ```sql
  SELECT MIN(labjack_timestamp),
         DATETIME(MIN(labjack_timestamp), 'unixepoch')
  FROM detection_events WHERE test_session_id = '0846e476...';
  -- Expected: 2025-11-04, NOT 1762-11-04
  ```

- [ ] **No stuck video_relative_timestamp values**
  ```sql
  SELECT COUNT(DISTINCT video_relative_timestamp)
  FROM detection_events WHERE test_session_id = '0846e476...';
  -- Expected: ~400-500 unique values, NOT ~225
  ```

- [ ] **sequence_video_results has timing data**
  ```sql
  SELECT video_id, video_start_time, video_end_time, actual_duration_ms
  FROM sequence_video_results
  WHERE video_sequence_id = '368de9c9-0e2e-473a-874c-054b9ddc1d96';
  -- Expected: 2 rows with non-NULL start/end times
  ```

---

## Frontend Impact

Once fixed, the frontend should be able to:

1. **Query:** `GET http://localhost:3000/results/0846e476-2e21-499c-bfc8-0b2218081c77`

2. **Receive:**
```json
{
  "session_id": "0846e476-...",
  "total_detections": 502,
  "videos": [
    {
      "video_id": "10c2b16c-...",
      "video_name": "video1.mp4",
      "detections": 262,
      "timing_range": [0.0, 5.2],
      "avg_latency_ms": 85.3
    },
    {
      "video_id": "550e3cf8-...",
      "video_name": "video2.mp4",
      "detections": 240,
      "timing_range": [0.0, 4.8],
      "avg_latency_ms": 87.1
    }
  ]
}
```

3. **Display:**
   - Per-video detection timeline
   - Latency distribution charts
   - Ground truth comparison

**Currently:** Frontend receives incomplete data, cannot render per-video breakdown.

---

## Testing After Fixes

```bash
# 1. Fix the data
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 << 'EOF'
import asyncio
from services.detection_video_reassignment import reassign_null_video_ids

async def fix_session():
    result = await reassign_null_video_ids(
        session_id='0846e476-2e21-499c-bfc8-0b2218081c77',
        dry_run=False
    )
    print(f"Fixed {result['reassigned_count']} detections")
    return result

asyncio.run(fix_session())
EOF

# 2. Verify the fix
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('dev_database.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT video_id, COUNT(*)
    FROM detection_events
    WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
    GROUP BY video_id
""")
for row in cursor.fetchall():
    print(f"video_id={row[0][:8] if row[0] else 'NULL'}: {row[1]} detections")
EOF

# 3. Test the API
curl -X GET "http://localhost:3000/api/sessions/0846e476-2e21-499c-bfc8-0b2218081c77/results" | jq
```

---

## Summary

| Bug | Impact | Fix Location | Fix Type | Priority |
|-----|--------|--------------|----------|----------|
| NULL video_id | Cannot display per-video results | `detection_video_reassignment.py` | Call service after session | 🔴 CRITICAL |
| Year 1762 timestamps | Wrong epoch calculation | `precision_timing_service.py` | Fix timestamp epoch | 🔴 CRITICAL |
| Stuck relative_timestamp | Invalid timing data | `timing_synchronization_calculator.py` | Remove constants | 🔴 CRITICAL |

**All three must be fixed before production deployment.**
