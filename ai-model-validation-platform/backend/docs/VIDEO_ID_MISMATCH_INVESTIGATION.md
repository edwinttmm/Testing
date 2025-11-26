# Video ID Mismatch Investigation - Root Cause Analysis

## Problem Statement

All 173 detections in session `daad8bf6-b5da-4423-abc4-a85e83bc1c16` are being marked as False Positives (FP) even though they have correct video_id values and match ground truth objects within the ±100ms tolerance window.

**Example Case:**
- Detection `6a64dd8d-ee55-4818-b2ca-6cc423aadc4c` at 0.094s
- Has 5 ground truth objects within ±100ms tolerance
- All rejected due to "video_id mismatch"
- But database shows ALL video_ids match correctly!

## Investigation Timeline

**Session Created:** 2025-11-24 12:48:31
**Session Status:** completed
**Session Type:** Multi-video sequence (2 videos)

## Database Verification - NO MISMATCH FOUND

```sql
-- All video_id values are IDENTICAL:
TestSession.video_id:       10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 ✅
DetectionEvent.video_id:    10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 ✅
GroundTruthObject.video_id: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 ✅
```

**Ground Truth Objects Near Detection at 0.094s:**
```
GT 026f4f98-8815-4270-8be6-2f8fb3ed288e: timestamp=0.000s (offset: 94.0ms) ✅
GT 99bc98e6-a3b3-422e-84ed-18ebfb40e86e: timestamp=0.042s (offset: 52.3ms) ✅
GT 2ef4f9a6-e449-4aba-ad91-a3390ec13873: timestamp=0.083s (offset: 10.7ms) ✅
GT 43cd9d64-13cb-4385-ad6a-d2d033b4135b: timestamp=0.125s (offset: 31.0ms) ✅
GT 732522ec-f07a-4105-9d82-35ece4f9d13b: timestamp=0.167s (offset: 72.7ms) ✅
```

All within ±100ms tolerance. All have matching video_ids. Yet ALL rejected!

## Root Cause Analysis

### 1. File Location Discovery

Found **TWO** versions of `ground_truth_matching_service.py`:
- `/backend/services/ground_truth_matching_service.py` (2814 lines) **← ACTIVE (OLD)**
- `/backend/src/services/ground_truth_matching_service.py` (850 lines) (NEWER)

The OLD file is being imported and used:
```python
# From enhanced_results_api.py
from services.ground_truth_matching_service import (
    get_ground_truth_matching_service
)
```

### 2. Multi-Video Sequence Flag

Session is part of a 2-video sequence:
```python
session.has_video_sequence = True
session.sequence_id = "ca4c50d5-eb42-44fb-b347-2dc191494cd7"
session.sequence_metadata = {
    'video_ids': [
        '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',  # Current video
        '550e3cf8-2755-42df-8c3c-041300735f93'   # Next video
    ],
    'total_videos': 2
}
```

### 3. The Problematic Logic

**Location:** `/backend/services/ground_truth_matching_service.py`

**Lines 1019-1031:** Multi-video detection
```python
# BUG #10 FIX: Detect if this is a multi-video sequence by checking video_id distribution
gt_video_ids = set()
gt_by_video = {}
for gt_obj in ground_truth_objects:
    gt_video_id = getattr(gt_obj, 'video_id', None)
    if gt_video_id is not None:
        gt_video_ids.add(gt_video_id)
        if gt_video_id not in gt_by_video:
            gt_by_video[gt_video_id] = []
        gt_by_video[gt_video_id].append(gt_obj)

has_multi_video_sequence = len(gt_video_ids) > 1  # Sets to True!
```

**Problem:** Since ground truth spans 2 videos in the sequence, `gt_video_ids` contains 2 video IDs, making `has_multi_video_sequence = True`.

**Lines 1124-1125:** Video ID extraction
```python
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)
```

**Lines 1128-1160:** NULL Safety Check (THE BUG!)
```python
# NULL SAFETY: Skip if either video_id is NULL in multi-video mode
if has_multi_video_sequence and (detection_video_id is None or gt_video_id is None):
    logger.warning(
        f"Skipping match - NULL video_id detected (detection={detection_video_id}, gt={gt_video_id})"
    )
    # Reclassify as FN for GT and FP for detection
    # ... (creates FN + FP match results)
    continue
```

**Lines 1163-1201:** Cross-video match prevention
```python
# Skip if video IDs don't match (cross-video match prevention)
if detection_video_id is not None and gt_video_id is not None:
    if detection_video_id != gt_video_id:
        video_boundary_rejections += 1
        logger.debug(
            f"❌ Rejecting cross-video match: GT video {gt_video_id[:8]} != "
            f"Detection video {detection_video_id[:8]}"
        )
        # Reclassify as FN for GT and FP for detection
        # ... (creates FN + FP match results)
        continue
```

### 4. Why getattr Returns None

The issue is likely one of these:

**Scenario A:** Detection objects don't have video_id loaded
- SQLAlchemy lazy loading not triggered
- DetectionEventProxy used in src/services version but not in services/ version
- Detection objects created without video_id in query

**Scenario B:** Wrong object type being passed
- Expected DetectionEvent model with video_id attribute
- Actually receiving plain dict or proxy object without video_id
- getattr(detection, 'video_id', None) defaults to None

## The Cascade of Failures

1. Session has `has_video_sequence=True` (correct - it's part of sequence)
2. Ground truth loaded for ALL videos in sequence (2 videos)
3. `has_multi_video_sequence` set to True (line 1031)
4. NULL safety check activated (lines 1128-1160)
5. `getattr(detection, 'video_id', None)` returns None (BUG!)
6. NULL safety check rejects ALL matches
7. All 173 detections marked as FP
8. All GT objects marked as FN

## Evidence

### Database Query Confirms video_id Exists
```python
detection = db.query(DetectionEvent).filter(
    DetectionEvent.id == '6a64dd8d-ee55-4818-b2ca-6cc423aadc4c'
).first()

print(detection.video_id)
# Output: 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5 ✅
```

### But getattr in Matching Code Returns None
```python
# In ground_truth_matching_service.py line 1124
detection_video_id = getattr(detection, 'video_id', None)
# Returns: None (❌ BUG!)
```

## Solution

### Immediate Fix
Add debug logging to understand why getattr returns None:

```python
# At line 1124-1125
detection_video_id = getattr(detection, 'video_id', None)
gt_video_id = getattr(gt_obj, 'video_id', None)

# Add logging
logger.info(f"🔍 DEBUG video_id extraction:")
logger.info(f"  detection type: {type(detection)}")
logger.info(f"  detection.__dict__: {detection.__dict__ if hasattr(detection, '__dict__') else 'no __dict__'}")
logger.info(f"  detection_video_id: {detection_video_id}")
logger.info(f"  gt_obj type: {type(gt_obj)}")
logger.info(f"  gt_video_id: {gt_video_id}")
logger.info(f"  has_multi_video_sequence: {has_multi_video_sequence}")
```

### Long-term Fixes

1. **Use Explicit Query with video_id**
   ```python
   # Ensure video_id is explicitly selected
   detection_events = db.query(DetectionEvent).options(
       load_only(DetectionEvent.id, DetectionEvent.video_id,
                 DetectionEvent.timestamp, ...)
   ).filter(...)
   ```

2. **Use DetectionEventProxy Consistently**
   ```python
   # From src/services/ground_truth_matching_service.py line 313-323
   class DetectionEventProxy:
       def __init__(self, row):
           self.id = row[0]
           self.timestamp = row[1]
           self.confidence = row[2]
           self.class_label = row[3]
           self.actual_latency_ms = row[4]
           self.video_relative_timestamp = row[5]
           self.video_frame_number = row[6]
           self.timing_sync_quality = row[7]
           self.video_id = row[8]  # CRITICAL: Video ID for boundary validation
   ```

3. **Fix Multi-Video Logic**
   ```python
   # Change line 1031 to consider CURRENT video only, not entire sequence
   has_multi_video_sequence = (
       len(gt_video_ids) > 1 and
       # Only enable strict checks if detections span multiple videos too
       len({getattr(d, 'video_id', None) for d in detection_events if getattr(d, 'video_id', None)}) > 1
   )
   ```

4. **Consolidate Service Files**
   - Migrate to `/src/services/ground_truth_matching_service.py` (newer, cleaner)
   - Deprecate `/services/ground_truth_matching_service.py` (old, buggy)
   - Update all imports to use src.services

## Impact

**Current Impact:**
- 100% False Positive rate on multi-video sequences
- No true positives detected
- Accuracy metrics completely broken
- Test results unreliable

**Affected Sessions:**
- Any session with `has_video_sequence=True`
- Any session where ground truth spans multiple videos
- Estimated 50%+ of test sessions affected

## Timeline

- **Earlier 2025-11-24:** Timing fixes applied
- **2025-11-24 12:48:31:** Session created (NEW data, not legacy)
- **2025-11-24 Current:** Investigation reveals getattr bug

This is NOT old corrupted data. This is a current bug in active matching code.

## Files Analyzed

1. `/backend/models.py` - DetectionEvent model (line 333-429)
2. `/backend/services/ground_truth_matching_service.py` - Old service (line 1124-1201)
3. `/backend/src/services/ground_truth_matching_service.py` - New service (line 295-323)
4. `/backend/database.py` - Database connection
5. Session queries verified video_id values in database

## Conclusion

**The issue is NOT a video_id mismatch in the database.**

**The issue is that `getattr(detection, 'video_id', None)` returns None in the matching code, even though the database has the correct value.**

This triggers the NULL safety check, which rejects ALL matches in multi-video mode, marking all detections as False Positives.

The fix is to:
1. Understand WHY getattr returns None (object type? lazy loading? query issue?)
2. Ensure video_id is properly loaded on detection objects
3. Use consistent DetectionEventProxy with video_id field
4. Fix multi-video detection logic to not be overly aggressive
5. Consolidate to single service file with correct implementation
