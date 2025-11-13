# NULL Video ID Fix - Quick Reference Guide

## Problem
501/502 detections have NULL video_id due to race condition where detection events arrive before video lifecycle events.

## Solution Components

### 1. Automatic Fix (New Sessions)
**Location**: `services/session_completion_service.py` (lines 266-293)
- Runs automatically during session completion
- Reassigns NULL video_ids using timing analysis
- No manual intervention required

### 2. Manual Backfill (Existing Sessions)

#### Quick Commands
```bash
# Check which sessions need fixing
python3 scripts/backfill_null_video_ids.py --all --dry-run

# Fix specific session (dry-run first)
python3 scripts/backfill_null_video_ids.py --session-id <SESSION_ID> --dry-run
python3 scripts/backfill_null_video_ids.py --session-id <SESSION_ID>

# Verify fix
python3 scripts/verify_video_id_fix.py --session-id <SESSION_ID>

# Fix all sessions with NULL video_ids
python3 scripts/backfill_null_video_ids.py --all
```

#### Example: Fix Session 026c36cc
```bash
# Step 1: Dry run (preview changes)
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 scripts/backfill_null_video_ids.py --session-id 026c36cc-3801-4aa7-971f-b54c24d27505 --dry-run

# Expected output:
#   - Reassigned NULL detections: 105
#   - Corrected existing assignments: 0
#   - Total detections: 108
#   - Video assignments: {'video-1': 62, 'video-2': 43}

# Step 2: Apply fix
python3 scripts/backfill_null_video_ids.py --session-id 026c36cc-3801-4aa7-971f-b54c24d27505

# Step 3: Verify
python3 scripts/verify_video_id_fix.py --session-id 026c36cc-3801-4aa7-971f-b54c24d27505

# Expected output:
#   ✅ STATUS: PASSED - All detections have valid video_ids
#   NULL video_ids: 0
```

## Files Modified/Created

### Modified Files
- `services/session_completion_service.py` - Added automatic reassignment
- `services/detection_video_reassignment.py` - Already existed, using it

### New Files
- `scripts/backfill_null_video_ids.py` - Manual backfill script
- `scripts/verify_video_id_fix.py` - Verification script
- `tests/test_video_id_reassignment.py` - Test suite
- `docs/NULL_VIDEO_ID_FIX_SUMMARY.md` - Complete documentation
- `docs/NULL_VIDEO_ID_QUICK_REFERENCE.md` - This file

## How It Works

1. **Build Video Timing Map**
   ```python
   video_timing_map = {
       "video-1-id": {
           "start_time": 1000.0,  # When video started
           "end_time": 1010.0,    # When video ended
           "duration_s": 10.0
       }
   }
   ```

2. **Match Detections to Videos**
   ```python
   for detection in detections_with_null_video_id:
       for video_id, timing in video_timing_map.items():
           if timing["start_time"] <= detection.timestamp <= timing["end_time"]:
               detection.video_id = video_id
   ```

3. **Update Related Fields**
   - `video_id` - Assigned video
   - `video_relative_timestamp` - Time since video started
   - `video_frame_number` - Frame number in video
   - `sequence_video_result_id` - Link to sequence result

## Edge Cases Handled

1. **Detection before first video** → Assigned to first video (within 10s window)
2. **Detection after last video** → Assigned to last video (within 10s window)
3. **Detection at exact boundary** → Assigned to later video
4. **Detection in gap between videos** → Not assigned (rare, needs investigation)
5. **Missing timing metadata** → Error logged, can be fixed manually

## Verification Checklist

After applying fix:
- [ ] Run verification script
- [ ] Check NULL video_id count = 0
- [ ] Verify video distribution looks correct
- [ ] Check relative timestamps are populated
- [ ] Verify frame numbers are calculated
- [ ] Test ground truth matching still works

## Monitoring

### Success Indicators
```
✅ Video ID reassignment complete: reassigned 108 NULL detections
✅ STATUS: PASSED - All detections have valid video_ids
```

### Warning Indicators
```
⚠️ Detection <ID> occurs before first video start
⚠️ WARNING: 3 detections still have NULL video_ids
```

### Error Indicators
```
❌ Failed to run video_id reassignment
❌ Session <ID> not found
❌ No video results found for sequence
```

## Testing

```bash
# Run test suite
cd /home/rigade/Testing/ai-model-validation-platform/backend
pytest tests/test_video_id_reassignment.py -v

# Test specific edge case
pytest tests/test_video_id_reassignment.py::TestVideoIDReassignmentEdgeCases::test_detection_at_exact_video_start_boundary -v
```

## Common Issues

### Issue: "No video results found for sequence"
**Cause**: SequenceVideoResult records missing
**Fix**: Ensure video lifecycle events fired during session

### Issue: "Video has no start time - skipping"
**Cause**: video_start_time is NULL in SequenceVideoResult
**Fix**: Check frontend video timing capture

### Issue: "Detection does not match any video time range"
**Cause**: Detection timestamp outside all video ranges
**Fix**: Check if detection is in gap between videos (may need manual review)

## Quick Diagnosis

```bash
# Check current status
python3 -c "
from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
result = db.execute(text('''
    SELECT
        test_session_id,
        COUNT(*) as null_count,
        (SELECT COUNT(*) FROM detection_events de2 WHERE de2.test_session_id = de.test_session_id) as total
    FROM detection_events de
    WHERE video_id IS NULL
    GROUP BY test_session_id
''')).fetchall()

print('Sessions with NULL video_ids:')
for session_id, null, total in result:
    print(f'  {session_id}: {null}/{total} ({null/total*100:.1f}% NULL)')
"
```

## Support

- **Documentation**: `docs/NULL_VIDEO_ID_FIX_SUMMARY.md`
- **Logs**: `logs/backfill_null_video_ids.log`
- **Tests**: `tests/test_video_id_reassignment.py`

---

**Quick Start**: `python3 scripts/backfill_null_video_ids.py --all --dry-run`
