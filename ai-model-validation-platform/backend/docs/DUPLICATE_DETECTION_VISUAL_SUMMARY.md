# Duplicate Detection Visual Summary

## The Problem (Frame 0 shows 2 detections)

```
Frame 0 (t=0.000s)
├─ Detection 1: "Frame 0, 0.000s, aligned -2.6ms, real 0ms"
└─ Detection 2: "Frame 0, 0.000s, aligned -2.6ms, real 0ms" ← DUPLICATE
```

---

## Root Cause: Temporal Expansion Bug

### Current Buggy Logic

```python
# temporal_expansion.py (BUGGY VERSION)

def expand_detections_temporally(detections, window_ms=500, interval_ms=40, include_original=True):
    for detection in detections:
        sequence_num = 0
        current_time_offset = 0.0  # BUG: Starts at 0
        
        while current_time_offset <= window_ms:
            virtual_timestamp = detection.timestamp + current_time_offset
            
            expanded = ExpandedDetection(
                virtual_id=f"{detection.id}-v{sequence_num}",
                timestamp=virtual_timestamp,
                is_original=(sequence_num == 0 and include_original),  # PROBLEM
                sequence_number=sequence_num
            )
            
            expanded_detections.append(expanded)
            sequence_num += 1
            current_time_offset += interval_ms  # Next: 40ms, 80ms, ...
```

### What Happens at Frame 0

```
Original detection: timestamp=0.000s

Iteration 1 (sequence_num=0, offset=0ms):
  ✓ Creates: det-1-v0 at t=0.000s (is_original=True)
  
Iteration 2 (sequence_num=1, offset=40ms):
  ✓ Creates: det-1-v1 at t=0.040s (is_original=False)
  
Iteration 3 (sequence_num=2, offset=80ms):
  ✓ Creates: det-1-v2 at t=0.080s (is_original=False)
  
...continue to t=500ms

Result: 13 detections total
  - 1 at t=0.000s (marked as "original")
  - 12 at t=40ms, 80ms, ..., 500ms (virtual)
```

### Ground Truth Matching

```
Ground Truth Object: gt-1 at t=0.000s (Frame 0)

Hungarian Matching:
  det-1-v0 (t=0.000s) → gt-1 (offset=0ms) ✓ MATCH
  det-1-v1 (t=0.040s) → gt-1 (offset=40ms) ✓ MATCH (within 500ms tolerance)
  det-1-v2 (t=0.080s) → gt-1 (offset=80ms) ✓ MATCH
  ...

After matching: 13 matches for gt-1 (all from same parent detection)
```

### Deduplication Attempts to Fix

```python
# collapse_duplicates() tries to deduplicate by parent_detection_id

matches_for_det1 = [
  Match(detection_id="det-1-v0", gt_id="gt-1", offset=0ms),
  Match(detection_id="det-1-v1", gt_id="gt-1", offset=40ms),
  Match(detection_id="det-1-v2", gt_id="gt-1", offset=80ms),
  ...
]

# Strategy: "first" - keep match with smallest offset
best_match = min(matches, key=lambda m: m.temporal_offset_ms)
# Returns: det-1-v0 with offset=0ms

# But sometimes deduplication fails when:
# - Multiple matches have SAME offset (rare but possible)
# - Tie-breaking logic is insufficient
# Result: 2 detections shown for Frame 0
```

---

## The Fix: Separate Original from Virtual Detections

### Fixed Logic

```python
# temporal_expansion.py (FIXED VERSION)

def expand_detections_temporally(detections, window_ms=500, interval_ms=40, include_original=True):
    for detection in detections:
        # NEW: Add original detection FIRST (if requested)
        if include_original:
            expanded_detections.append(ExpandedDetection(
                virtual_id=detection.id,  # Use parent ID (no -v suffix)
                timestamp=detection.timestamp,
                is_original=True,
                sequence_number=0
            ))
            
            # Start virtual detections from NEXT interval
            sequence_num = 1
            current_time_offset = interval_ms  # Start at 40ms, not 0ms
        else:
            sequence_num = 0
            current_time_offset = 0.0
        
        # Generate VIRTUAL detections only
        while current_time_offset <= window_ms:
            virtual_timestamp = detection.timestamp + current_time_offset
            
            expanded = ExpandedDetection(
                virtual_id=f"{detection.id}-v{sequence_num}",
                timestamp=virtual_timestamp,
                is_original=False,  # Virtual detections are NEVER original
                sequence_number=sequence_num
            )
            
            expanded_detections.append(expanded)
            sequence_num += 1
            current_time_offset += interval_ms
```

### What Happens at Frame 0 (After Fix)

```
Original detection: timestamp=0.000s

Step 1: Add original (include_original=True):
  ✓ Creates: det-1 at t=0.000s (is_original=True, NO -v suffix)

Step 2: Generate virtual detections starting from t+40ms:
  ✓ Creates: det-1-v1 at t=0.040s (is_original=False)
  ✓ Creates: det-1-v2 at t=0.080s (is_original=False)
  ...
  ✓ Creates: det-1-v12 at t=0.500s (is_original=False)

Result: 13 detections total
  - 1 at t=0.000s (original, ID="det-1")
  - 12 at t=40ms, 80ms, ..., 500ms (virtual, IDs="det-1-v1" to "det-1-v12")
```

### Ground Truth Matching (After Fix)

```
Ground Truth Object: gt-1 at t=0.000s (Frame 0)

Hungarian Matching:
  det-1 (t=0.000s) → gt-1 (offset=0ms) ✓ MATCH
  det-1-v1 (t=0.040s) → gt-1 (offset=40ms) ✓ MATCH
  det-1-v2 (t=0.080s) → gt-1 (offset=80ms) ✓ MATCH
  ...

After matching: 13 matches for gt-1
```

### Deduplication (After Fix)

```python
# collapse_duplicates() groups by parent_detection_id

# Parse parent IDs:
# "det-1" → parent="det-1"
# "det-1-v1" → parent="det-1" (remove "-v1" suffix)
# "det-1-v2" → parent="det-1"

matches_for_det1 = [
  Match(detection_id="det-1", gt_id="gt-1", offset=0ms),      # Original
  Match(detection_id="det-1-v1", gt_id="gt-1", offset=40ms),  # Virtual
  Match(detection_id="det-1-v2", gt_id="gt-1", offset=80ms),  # Virtual
  ...
]

# Strategy: "first" - keep match with smallest offset
best_match = min(matches, key=lambda m: m.temporal_offset_ms)
# Returns: det-1 with offset=0ms (the original)

# Update detection_id to parent
best_match.detection_id = "det-1"

Result: Exactly 1 detection shown for Frame 0 ✓
```

---

## Before vs After Comparison

### Before Fix (13 detections, 1 duplicate at Frame 0)

```
Expanded Detections:
┌─────────────┬────────────┬─────────────┬──────────┐
│ Virtual ID  │ Timestamp  │ is_original │ Sequence │
├─────────────┼────────────┼─────────────┼──────────┤
│ det-1-v0    │ 0.000s     │ True        │ 0        │ ← At Frame 0
│ det-1-v1    │ 0.040s     │ False       │ 1        │
│ det-1-v2    │ 0.080s     │ False       │ 2        │
│ det-1-v3    │ 0.120s     │ False       │ 3        │
│ ...         │ ...        │ ...         │ ...      │
│ det-1-v12   │ 0.500s     │ False       │ 12       │
└─────────────┴────────────┴─────────────┴──────────┘

After Ground Truth Matching:
  Frame 0 (t=0.000s): 2 detections shown (BUG) ✗
```

### After Fix (13 detections, no duplicates)

```
Expanded Detections:
┌─────────────┬────────────┬─────────────┬──────────┐
│ Virtual ID  │ Timestamp  │ is_original │ Sequence │
├─────────────┼────────────┼─────────────┼──────────┤
│ det-1       │ 0.000s     │ True        │ 0        │ ← At Frame 0 (original)
│ det-1-v1    │ 0.040s     │ False       │ 1        │ ← Virtual starts here
│ det-1-v2    │ 0.080s     │ False       │ 2        │
│ det-1-v3    │ 0.120s     │ False       │ 3        │
│ ...         │ ...        │ ...         │ ...      │
│ det-1-v12   │ 0.500s     │ False       │ 12       │
└─────────────┴────────────┴─────────────┴──────────┘

After Ground Truth Matching:
  Frame 0 (t=0.000s): 1 detection shown (CORRECT) ✓
```

---

## Quick Reference

| Aspect | Before Fix | After Fix |
|--------|-----------|-----------|
| Detections at t=0 | 1 (but marked as virtual) | 1 (marked as original) |
| Virtual ID at t=0 | `det-1-v0` | `det-1` (no suffix) |
| First virtual | t=0.000s | t=0.040s |
| Deduplication | Sometimes fails (same offset) | Always works (unique offsets) |
| UI Display | 2 detections at Frame 0 ✗ | 1 detection at Frame 0 ✓ |
| Memory Usage | 13 detections | 13 detections (same) |
| Correctness | Buggy | Correct |

---

## Testing the Fix

```bash
# Run temporal expansion test
cd /home/rigade/Testing/ai-model-validation-platform/backend
source venv/bin/activate
python -c "
from services.temporal_expansion import expand_detections_temporally
from models import DetectionEvent

det = DetectionEvent(id='test-1', timestamp=0.0, confidence=0.95)
expanded = expand_detections_temporally([det], window_ms=500, interval_ms=40, include_original=True)

t0_dets = [e for e in expanded if e.timestamp == 0.0]
print(f'Detections at t=0: {len(t0_dets)}')  # Should be 1
print(f'Original ID: {t0_dets[0].virtual_id}')  # Should be 'test-1' (no -v suffix)
print(f'Is original: {t0_dets[0].is_original}')  # Should be True

first_virtual = [e for e in expanded if not e.is_original][0]
print(f'First virtual: {first_virtual.virtual_id} at t={first_virtual.timestamp}s')
# Should be 'test-1-v1' at t=0.040s
"
```

Expected output:
```
Detections at t=0: 1
Original ID: test-1
Is original: True
First virtual: test-1-v1 at t=0.04s
```

---

**Fix Status**: 🔴 Not Yet Applied
**File to Modify**: `/backend/src/services/temporal_expansion.py`
**Lines to Change**: 150-177
**Estimated Fix Time**: 30 minutes
**Testing Time**: 1 hour
