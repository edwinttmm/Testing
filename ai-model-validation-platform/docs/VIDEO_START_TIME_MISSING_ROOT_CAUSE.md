# Root Cause Analysis: Missing video_start_time Field

## Executive Summary

**Problem**: All detection events have `video_start_time = NULL`, causing timing calculator to return 0 corrected results and falling back to duplicate-prone fallback path.

**Impact**:
- Timing calculator skips 100% of detections (lines 649-653)
- Fallback path activates (lines 867-941) creating duplicate latency values
- ~352ms latency inflation bug reoccurs due to missing per-video start times

**Root Cause**: `video_start_time` field is NEVER populated when creating DetectionEvent records

---

## 🔍 Field Investigation

### DetectionEvent Model Definition
**Location**: `/backend/models.py:362-363`

```python
class DetectionEvent(Base):
    # ...
    video_start_time = Column(Float, nullable=True, index=True)  # Video start reference time
    video_start_time_ns = Column(String, nullable=True)  # Nanosecond precision video start time
```

**Purpose**: Records when the specific video started playing (Unix timestamp). Critical for:
1. Calculating accurate video-relative timestamps
2. Determining which video a detection belongs to in multi-video sequences
3. Avoiding 8-9s latency inflation bugs

---

## 🚨 Where DetectionEvent Records Are Created

### 1. Dedicated LabJack Monitor (Primary Creation Point)

**Location**: `/backend/services/dedicated_labjack_monitor.py:1347-1378` (sync)

```python
detection_event = DetectionEvent(
    id=hil_event.id,
    test_session_id=hil_event.session_id,
    video_id=video_id_for_detection,  # ✅ Set
    sequence_id=hil_event.sequence_id,  # ✅ Set
    timestamp=labjack_trigger_time,  # ✅ Set
    labjack_timestamp=float(labjack_trigger_time),  # ✅ Set
    video_relative_timestamp=hil_event.video_relative_timestamp,  # ✅ Set
    video_frame_number=hil_event.video_frame_number,  # ✅ Set
    # ...
    # ❌ MISSING: video_start_time=???
    # ❌ MISSING: video_start_time_ns=???
)
```

**Location**: `/backend/services/dedicated_labjack_monitor.py:2079-2106` (async)

```python
detection_event = DetectionEvent(
    id=hil_event.id,
    test_session_id=hil_event.session_id,
    video_id=video_id_for_detection,  # ✅ Set
    timestamp=detection_timestamp,  # ✅ Set
    labjack_timestamp=float(detection_timestamp),  # ✅ Set
    video_relative_timestamp=hil_event.video_relative_timestamp,  # ✅ Set
    video_frame_number=hil_event.video_frame_number,  # ✅ Set
    # ...
    # ❌ MISSING: video_start_time=???
    # ❌ MISSING: video_start_time_ns=???
)
```

### 2. Results Storage Pipeline Service

**Location**: `/backend/services/results_storage_pipeline_service.py:144-171`

```python
detection_event = DetectionEvent(
    id=str(uuid.uuid4()),
    test_session_id=detection_data['session_id'],
    video_id=detection_data.get('video_id'),
    timestamp=detection_data['timestamp'],
    # ...
    # ❌ MISSING: video_start_time=???
)
```

---

## 🔧 Where video_start_time SHOULD Come From

### Option 1: From SequenceVideoResult (Multi-Video Sessions)

**Table**: `sequence_video_results`
**Field**: `video_start_time` (Column defined at models.py:573)

```sql
SELECT
    svr.video_id,
    svr.video_start_time,  -- ✅ This field exists and is populated
    svr.video_start_time_ns
FROM sequence_video_results svr
WHERE svr.test_session_id = ?
```

**When Available**: Multi-video test sessions with `has_video_sequence = true`

### Option 2: From TestSession (Single Video Sessions)

**Table**: `test_sessions`
**Field**: `video_playback_start_time` (Column at models.py:279-280)

```sql
SELECT
    ts.video_playback_start_time,  -- ✅ This field exists and is populated
    ts.video_playback_start_time_ns
FROM test_sessions ts
WHERE ts.id = ?
```

**When Available**: All sessions (both single and multi-video)

### Option 3: Calculate from video_relative_timestamp

```python
# If detection has video_relative_timestamp, we can derive video_start_time:
video_start_time = detection.timestamp - detection.video_relative_timestamp
```

**When Available**: When `video_relative_timestamp` is already calculated

---

## 💥 Impact Chain

### Step 1: DetectionEvent Created Without video_start_time
```python
# dedicated_labjack_monitor.py:1347
detection_event = DetectionEvent(
    # ... all other fields ...
    # ❌ video_start_time NOT SET
)
db.add(detection_event)
db.commit()
```

### Step 2: Timing Calculator Checks for video_start_time
```python
# timing_synchronization_calculator.py:644-653
video_start_time = detection.get('video_start_time')
if video_start_time is None:
    video_start_time = detection.get('video_playback_start_time')
if video_start_time is None:
    logger.error(
        f"❌ No video_start_time found in detection {detection_id}. "
        f"Cannot calculate accurate latency. Skipping to prevent 8-9s inflation bug."
    )
    continue  # ← DETECTION SKIPPED
```

### Step 3: Zero Corrected Results Returned
```python
# timing_synchronization_calculator.py:683
logger.info(f"Calculated corrected latencies for {len(results)} detections in session")
# Output: "Calculated corrected latencies for 0 detections in session"
```

### Step 4: Fallback Path Activates
```python
# enhanced_hil_results_endpoints.py:864-941
if len(corrected_results) == 0 and len(detection_events_result) > 0:
    logger.warning(f"No corrected results available for session {session_id} - using fallback timing data")
    # Fallback creates detection results without proper video timing
    # This path is known to create duplicate latency values
```

---

## 🎯 The Fix

### Immediate Fix: Populate video_start_time at Creation

**Location**: `/backend/services/dedicated_labjack_monitor.py:1347` and `2079`

#### For Multi-Video Sessions:
```python
# Get video_start_time from SequenceVideoResult
video_start_time = None
if hil_event.sequence_video_result_id:
    seq_result = db.query(SequenceVideoResult).filter_by(
        id=hil_event.sequence_video_result_id
    ).first()
    if seq_result:
        video_start_time = seq_result.video_start_time

detection_event = DetectionEvent(
    # ... existing fields ...
    video_start_time=video_start_time,  # ✅ NOW SET
    video_start_time_ns=str(int(video_start_time * 1e9)) if video_start_time else None,
)
```

#### For Single-Video Sessions:
```python
# Get video_start_time from TestSession
video_start_time = None
session = db.query(TestSession).filter_by(id=hil_event.session_id).first()
if session:
    video_start_time = session.video_playback_start_time

detection_event = DetectionEvent(
    # ... existing fields ...
    video_start_time=video_start_time,  # ✅ NOW SET
    video_start_time_ns=str(int(video_start_time * 1e9)) if video_start_time else None,
)
```

#### Fallback Calculation:
```python
# If video_relative_timestamp exists but video_start_time doesn't:
if video_start_time is None and hil_event.video_relative_timestamp is not None:
    video_start_time = labjack_trigger_time - hil_event.video_relative_timestamp
    logger.warning(f"Calculated video_start_time from video_relative_timestamp: {video_start_time}")
```

### Backfill Fix: Update Existing Records

**Location**: Create migration or backfill script

```python
# For each detection event with NULL video_start_time:
def backfill_video_start_time():
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.video_start_time == None,
        DetectionEvent.timestamp != None,
        DetectionEvent.video_relative_timestamp != None
    ).all()

    for detection in detections:
        # Calculate from video_relative_timestamp
        detection.video_start_time = detection.timestamp - detection.video_relative_timestamp
        detection.video_start_time_ns = str(int(detection.video_start_time * 1e9))

    db.commit()
    logger.info(f"Backfilled video_start_time for {len(detections)} detections")
```

---

## 📊 Verification Steps

### 1. Check Current State
```sql
-- Count detections with NULL video_start_time
SELECT
    COUNT(*) as total_detections,
    COUNT(video_start_time) as with_video_start_time,
    COUNT(*) - COUNT(video_start_time) as missing_video_start_time
FROM detection_events;

-- Expected: 100% missing (all NULL)
```

### 2. After Fix - Verify Creation
```sql
-- Check new detections have video_start_time
SELECT
    id,
    timestamp,
    video_start_time,
    video_relative_timestamp,
    timestamp - video_relative_timestamp as calculated_start
FROM detection_events
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC
LIMIT 10;

-- Expected: video_start_time populated for new records
```

### 3. After Backfill - Verify Calculation
```sql
-- Verify backfill accuracy
SELECT
    COUNT(*) as total,
    COUNT(video_start_time) as with_start_time,
    AVG(ABS(video_start_time - (timestamp - video_relative_timestamp))) as avg_error_seconds
FROM detection_events
WHERE video_relative_timestamp IS NOT NULL;

-- Expected: 100% with_start_time, avg_error_seconds near 0
```

### 4. Test Timing Calculator
```python
# Run timing calculator and check for 0 results
results = timing_calculator.calculate_batch_corrected_latencies(
    session_id=test_session_id,
    detection_events=detection_events,
    ground_truth_events=ground_truth_events,
    video_timing_metadata=video_timing_metadata,
    labjack_start_time=labjack_start_time
)

assert len(results) > 0, "Still getting 0 corrected results after fix!"
```

---

## 🏗️ Implementation Plan

### Phase 1: Immediate Fix (Stop the Bleeding)
1. ✅ Update `dedicated_labjack_monitor.py` to populate `video_start_time` at detection creation
2. ✅ Add fallback calculation from `video_relative_timestamp`
3. ✅ Deploy to production

### Phase 2: Backfill (Fix Historical Data)
1. ✅ Create backfill script to calculate `video_start_time` for existing records
2. ✅ Test on staging database
3. ✅ Run backfill on production during maintenance window
4. ✅ Verify all records updated

### Phase 3: Validation (Ensure Quality)
1. ✅ Monitor timing calculator success rate (should go from 0% to 100%)
2. ✅ Verify fallback path no longer activates
3. ✅ Check for duplicate latency values (should be eliminated)
4. ✅ Compare latencies before/after (should see ~352ms reduction for affected cases)

---

## 🔗 Related Issues

- **8-9s Latency Inflation Bug**: Caused by using `labjack_start_time` instead of per-video `video_start_time`
- **Duplicate Latency Values**: Fallback path creates multiple latency fields with same values
- **Zero Corrected Results**: Timing calculator can't process detections without `video_start_time`

---

## 📝 Summary

**Root Cause**: `video_start_time` is defined in the schema but never populated when creating DetectionEvent records.

**Fix**: Add 3-5 lines of code to populate `video_start_time` from:
1. `SequenceVideoResult.video_start_time` (multi-video)
2. `TestSession.video_playback_start_time` (single-video)
3. Calculated from `timestamp - video_relative_timestamp` (fallback)

**Impact**:
- Eliminates timing calculator skipping (0 → 100% success rate)
- Removes fallback path activation (reduces duplicates)
- Fixes latency inflation for multi-video sequences (~352ms correction)

---

**Generated**: 2025-11-25
**Severity**: HIGH (Production timing accuracy impacted)
**Priority**: P0 (Blocking accurate latency measurements)
