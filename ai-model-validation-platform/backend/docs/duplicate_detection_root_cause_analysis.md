# Duplicate Detection Entries - Root Cause Analysis

## Executive Summary

**Status**: ❌ **FIXES NOT WORKING** - Duplicates still appear with DIFFERENT "real" latency values

**Critical Finding**: The duplicates are NOT the same database row being returned twice. They are DIFFERENT calculations of the same detection event, producing different latency values.

## Evidence of Failure

```
Frame 0: aligned -8.5ms, real 9ms → GT PASS
Frame 0: aligned -8.5ms, real 1ms → GT PASS  ← DIFFERENT "real" value (9ms vs 1ms)

Frame 3: aligned -15.5ms, real 15ms → GT PASS
Frame 3: aligned -15.5ms, real 8ms → GT PASS  ← DIFFERENT "real" value (15ms vs 8ms)
```

**Key Observation**: Same frame, same aligned latency, but TWO different "real" latency values.

## Implemented Fixes (That Didn't Work)

### Fix #1: Changed joinedload to selectinload
**Location**: `enhanced_hil_results_endpoints.py:325`
```python
detection_events_query = db.query(DetectionEvent).options(
    selectinload(DetectionEvent.video),  # ← Changed from joinedload
    selectinload(DetectionEvent.ground_truth_match),
    selectinload(DetectionEvent.test_session)
)
```
**Status**: ✅ In place, but doesn't solve the problem
**Why it didn't work**: This optimizes query performance but doesn't prevent duplicate processing

### Fix #2: Added processed_event_ids in fallback path
**Location**: `enhanced_hil_results_endpoints.py:862-874`
```python
processed_event_ids = set()

for i, original_event in enumerate(detection_events_result):
    if original_event.id in processed_event_ids:
        logger.debug(f"Skipping duplicate event_id {original_event.id} in fallback path")
        continue
    processed_event_ids.add(original_event.id)
```
**Status**: ✅ In place, but doesn't execute
**Why it didn't work**: The code path being used is NOT the fallback path (corrected_results exist)

### Fix #3: Added processed_event_ids in normal path
**Location**: `enhanced_hil_results_endpoints.py:957-961`
```python
for i, (original_event, corrected_result) in enumerate(zip(detection_events_result, corrected_results)):
    if original_event.id in processed_event_ids:
        logger.debug(f"Skipping duplicate event_id {original_event.id} in normal path")
        continue
    processed_event_ids.add(original_event.id)
```
**Status**: ✅ In place, but duplicates still appear
**Why it didn't work**: The duplicates are being CREATED UPSTREAM in calculate_batch_corrected_latencies

### Fix #4 & #5: Added video_start_time calculation
**Location**: `dedicated_labjack_monitor.py:1347-1388`, `dedicated_labjack_monitor.py:2085-2124`
**Status**: ✅ In place
**Why it didn't work**: This doesn't address the duplicate generation issue

## Root Cause Identification

### The REAL Problem: Multiple Passes Through calculate_batch_corrected_latencies

The duplicates are being created in `timing_synchronization_calculator.py:579-689` by **processing the same detection_event multiple times**.

#### Analysis of calculate_batch_corrected_latencies

```python
def calculate_batch_corrected_latencies(self,
    session_id: str,
    detection_events: List[Dict[str, Any]],  # ← Input list
    ground_truth_events: List[Dict[str, Any]],
    video_timing_metadata: VideoTimingMetadata,
    labjack_start_time: float) -> List[TimingSynchronizationResult]:

    results = []

    # Match detection events to closest ground truth events
    for detection in detection_events:  # ← Iterates through ALL detections
        detection_id = detection.get('id', ...)

        # Find closest ground truth event
        closest_gt = self._find_closest_ground_truth(detection, ground_truth_events)

        if closest_gt is None:
            continue

        # Calculate corrected latency
        result = self.calculate_corrected_latency_with_frame_data(...)
        results.append(result)  # ← Creates ONE result per detection

    return results
```

### Hypothesis: Why Are There Duplicates with Different Latencies?

**Theory 1: Same detection matches MULTIPLE ground truth events**
- A single detection event might match Frame 0, Frame 1, Frame 2, etc.
- Each match creates a DIFFERENT `TimingSynchronizationResult` with different `gt_video_time`
- This would produce different "real" latency values (9ms vs 1ms)

**Theory 2: Detection events list contains duplicates**
- The `detection_events` input list might contain the same event ID multiple times
- Each duplicate gets processed independently
- This would explain same aligned latency but different calculations

**Theory 3: Multiple calls to calculate_batch_corrected_latencies**
- The function might be called multiple times in the same request
- Each call processes all events, creating duplicates

## Verification Steps Needed

### Step 1: Check if detection_events contains duplicates
```python
# In enhanced_hil_results_endpoints.py around line 547
detection_events = []
event_ids_seen = set()
for event in detection_events_result:
    if event.id in event_ids_seen:
        logger.warning(f"⚠️ DUPLICATE DETECTION EVENT IN INPUT: {event.id}")
    else:
        event_ids_seen.add(event.id)
    # ... rest of processing
```

### Step 2: Check if _find_closest_ground_truth returns multiple matches
```python
# In timing_synchronization_calculator.py around line 620
closest_gt = self._find_closest_ground_truth(detection, ground_truth_events)

# Add logging to see if this is being called multiple times for same detection
logger.debug(f"Finding GT for detection {detection_id}, matched: {closest_gt}")
```

### Step 3: Check if calculate_batch_corrected_latencies is called multiple times
```python
# In enhanced_hil_results_endpoints.py around line 818
logger.info(f"📞 CALLING calculate_batch_corrected_latencies with {len(detection_events)} events")
corrected_results = timing_calculator.calculate_batch_corrected_latencies(...)
logger.info(f"📥 RECEIVED {len(corrected_results)} results from timing calculator")
```

### Step 4: Check the corrected_results for duplicate detection_ids
```python
# In enhanced_hil_results_endpoints.py after line 823
result_ids = [r.detection_id for r in corrected_results]
duplicate_ids = [id for id in result_ids if result_ids.count(id) > 1]
if duplicate_ids:
    logger.error(f"❌ DUPLICATES FOUND IN CORRECTED RESULTS: {duplicate_ids}")
```

## Proposed Real Fix

### Fix Location: timing_synchronization_calculator.py:606-625

**Add deduplication BEFORE processing**:

```python
def calculate_batch_corrected_latencies(self, ...):
    results = []
    processed_detection_ids = set()  # ← ADD THIS

    for detection in detection_events:
        detection_id = detection.get('id', detection.get('event_id', f"det_{len(results)}"))

        # ← ADD THIS CHECK
        if detection_id in processed_detection_ids:
            logger.warning(f"⚠️ Skipping duplicate detection_id in input: {detection_id}")
            continue
        processed_detection_ids.add(detection_id)

        # ... rest of processing
```

### Alternative Fix: Limit ONE ground truth match per detection

**In _find_closest_ground_truth**: Return ONLY the single closest match, not multiple candidates.

```python
def _find_closest_ground_truth(self, detection, ground_truth_events):
    # Find the SINGLE closest ground truth event
    # Current implementation might be returning multiple matches
    # Fix: Return only ONE match per detection
```

## Questions to Answer

1. ✅ Are the fixes actually being executed?
   - **Answer**: Yes, fixes are in place in code

2. ❌ Is `processed_event_ids` deduplication working?
   - **Answer**: No, because duplicates are created UPSTREAM

3. ❓ Where do the TWO DIFFERENT "real" values come from?
   - **Theory**: Different ground truth matches or different video_start_time values
   - **Need to verify**: Add logging to see what closest_gt returns

4. ❓ Is there a SECOND source creating entries?
   - **Theory**: calculate_batch_corrected_latencies is the source
   - **Need to verify**: Check if it's called multiple times or creates multiple results per detection

## Next Steps

1. **Add diagnostic logging** to track:
   - Input detection_events count and IDs
   - Output corrected_results count and IDs
   - Whether calculate_batch_corrected_latencies is called multiple times
   - What _find_closest_ground_truth returns for each detection

2. **Run test and capture logs** to confirm hypothesis

3. **Implement fix** based on findings:
   - If duplicates in input: Filter detection_events before processing
   - If multiple GT matches: Limit to ONE match per detection
   - If multiple calls: Deduplicate at call site

## Files to Modify

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/timing_synchronization_calculator.py`
   - Line 606: Add processed_detection_ids deduplication
   - Check _find_closest_ground_truth implementation

2. `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/enhanced_hil_results_endpoints.py`
   - Line 547: Check for duplicate detection events in input
   - Line 818: Add logging before/after calculate_batch_corrected_latencies
   - Line 823: Check corrected_results for duplicates

## Confidence Level

**Root Cause Confidence**: 85%
- The duplicates are created in calculate_batch_corrected_latencies
- The different "real" latency values suggest different ground truth matches or timing calculations
- The processed_event_ids fix doesn't work because it's too late in the pipeline

**Fix Confidence**: 70%
- Adding deduplication in calculate_batch_corrected_latencies should prevent duplicates
- Need to verify which of the 3 theories is correct before implementing final fix
