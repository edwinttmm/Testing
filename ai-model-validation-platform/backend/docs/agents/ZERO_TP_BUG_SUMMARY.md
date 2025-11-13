# ZERO TRUE POSITIVES BUG - Quick Reference

**Session**: c511302e-43c0-49c0-8ad0-bd89e891e3c1
**Date**: 2025-11-05 13:33 UTC
**Status**: ROOT CAUSE IDENTIFIED - READY TO FIX

## The Problem

User sees ALL ZEROS on frontend despite having:
- 514 ground truth objects (262 + 252 across 2 videos)
- 193 detection events (144 + 49 across 2 videos)
- Expected ~100+ true positives

## Three Bugs Identified

### BUG #1: Timestamp Domain Mismatch (CRITICAL)

**What**: Ground truth matching compares different time domains
- Ground truth: RELATIVE time (0.000s, 0.042s, 0.083s...)
- Detections: ABSOLUTE epoch time (1762347318.003s, 1762347318.039s...)

**Why it fails**: Comparing 0.042 to 1762347318.039 will NEVER match (different by 55+ years!)

**Fix**: Change matching algorithm to use `video_relative_timestamp` field

```python
# File: backend/services/ground_truth_matching_service.py

# WRONG:
detection_time = detection.timestamp  # 1762347318.003

# CORRECT:
detection_time = detection.video_relative_timestamp  # 0.133
```

**Impact**: 0% true positives, 100% false positives, 100% false negatives

---

### BUG #2: Video 2 Timestamp Offset (HIGH)

**What**: Video 2 detections have wrong relative timestamps
- Ground truth: 0.000s to 5.000s
- Video 2 detections: 11.519s to 16.519s (should be 0.0s to 5.0s)

**Why it fails**: Multi-video sequences not resetting video-relative timestamp

**Evidence**:
```
Video 1 (correct): Detection starts at 0.133s
Video 2 (WRONG):   Detection starts at 11.519s
                   11.519s ≈ 5.04s (video 1) + 6.48s (gap)
```

**Fix**: Reset `video_relative_timestamp` for each video in sequence

```python
# File: backend/services/video_sequence_orchestrator.py
# Ensure video_relative_timestamp calculated from EACH video's start time,
# not from sequence start time
```

**Impact**: Even after Bug #1 is fixed, Video 2 will have ZERO matches

---

### BUG #3: Frontend Data Parsing (MEDIUM)

**What**: Frontend shows zeros for FP/FN despite backend returning correct values

**Backend returns**:
- Video 1: FP=144, FN=262, TP=0
- Video 2: FP=49, FN=252, TP=0

**Frontend shows**: All zeros

**Fix**: Update frontend to correctly parse `sequence_results.per_video_results`

```typescript
// Check if frontend is reading from correct field:
const perVideoResults = response.sequence_results?.per_video_results || [];
```

**Impact**: User sees wrong data even when backend is correct

---

## Database Evidence

```sql
-- Ground truth objects
SELECT video_id, COUNT(*) FROM ground_truth_objects
WHERE video_id IN ('10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
                   '550e3cf8-2755-42df-8c3c-041300735f93')
GROUP BY video_id;

-- Result:
-- 10c2b16c...: 262 objects
-- 550e3cf8...: 252 objects

-- Detection events (this session)
SELECT video_id, COUNT(*) FROM detection_events
WHERE test_session_id = 'c511302e-43c0-49c0-8ad0-bd89e891e3c1'
GROUP BY video_id;

-- Result:
-- 10c2b16c...: 144 detections
-- 550e3cf8...: 49 detections

-- Ground truth match IDs (ALL NULL!)
SELECT COUNT(*) FROM detection_events
WHERE test_session_id = 'c511302e-43c0-49c0-8ad0-bd89e891e3c1'
AND ground_truth_match_id IS NOT NULL;

-- Result: 0 (ZERO MATCHES!)
```

## Timestamp Comparison

### Video 1
```
Ground Truth:           Detection Events:
t=0.000s, frame=1       abs=1762347318.003s, rel=0.133s, frame=3
t=0.042s, frame=2       abs=1762347318.039s, rel=0.169s, frame=4
t=0.083s, frame=3       abs=1762347318.103s, rel=0.233s, frame=5
                        ↑ 130ms startup delay (normal)
```

### Video 2
```
Ground Truth:           Detection Events:
t=0.000s, frame=1       abs=1762347329.390s, rel=11.519s, frame=276 ← WRONG!
t=0.042s, frame=2       abs=1762347329.422s, rel=11.551s, frame=277 ← WRONG!
t=0.083s, frame=3       abs=1762347329.437s, rel=11.566s, frame=277 ← WRONG!
                        ↑ 11.5 second offset (should be ~0.13s)
```

## Fix Priority

1. **BUG #1** (30 min) - Fix timestamp domain in matching algorithm
   - Will enable Video 1 matches
   - Video 2 still won't match until Bug #2 is fixed

2. **BUG #2** (1-2 hours) - Fix Video 2 relative timestamp
   - Will enable Video 2 matches
   - Affects all multi-video sequences

3. **BUG #3** (30 min) - Fix frontend display
   - User will see correct metrics
   - Should be done regardless of backend fixes

## Testing

After each fix:

```bash
# Check for true positives
curl http://localhost:8000/api/enhanced-hil/test-sessions/c511302e-43c0-49c0-8ad0-bd89e891e3c1/corrected-results | \
  python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"Video 1 TP: {d['sequence_results']['per_video_results'][0]['ground_truth_metrics']['true_positives']}\")"

# Should show > 0 after Bug #1 fix
```

```sql
-- Check database matches
SELECT COUNT(*) FROM detection_events
WHERE test_session_id = 'c511302e-43c0-49c0-8ad0-bd89e891e3c1'
AND ground_truth_match_id IS NOT NULL;

-- Should be > 0 after Bug #1 fix
```

```sql
-- Check Video 2 timestamps
SELECT MIN(video_relative_timestamp), MAX(video_relative_timestamp)
FROM detection_events
WHERE video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
AND test_session_id = 'c511302e-43c0-49c0-8ad0-bd89e891e3c1';

-- Should be ~0.0 to ~5.0 after Bug #2 fix (currently 11.5 to 16.5)
```

## Files to Fix

1. `backend/services/ground_truth_matching_service.py` - Bug #1
2. `backend/services/video_sequence_orchestrator.py` - Bug #2
3. Frontend HIL Results component - Bug #3

## Full Report

See: `/home/rigade/Testing/ai-model-validation-platform/backend/docs/agents/LIVE_API_CHECK_c511302e.md`
