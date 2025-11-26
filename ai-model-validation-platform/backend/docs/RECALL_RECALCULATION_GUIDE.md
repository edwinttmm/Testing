# Recall Recalculation Script Guide

## Overview

The `recalculate_recall_values.py` script fixes incorrect recall values stored in the database. The script recalculates recall using the **CORRECT** method that matches the implementation in `ground_truth_matching_service.py`.

## The Problem

Test sessions were storing recall values using an **INCORRECT** method:
- **OLD (WRONG)**: `recall = TP / (TP + FN)`
- This method only counts GT objects that were processed, not ALL GT objects in the database

**Example**: Session `2c9a93f6` shows:
- Stored recall: `0.3229` (32.3%)
- Calculated as: `83 / (83 + 174) = 83 / 257`
- **Problem**: This treats `FN` count as the denominator, which is incorrect

## The Correct Method

The script uses the **CORRECT** method from `ground_truth_matching_service.py:657-720`:
- **NEW (CORRECT)**: `recall = TP / actual_gt_count`
- Queries the database directly for the actual count of GT objects
- Handles both single-video and multi-video sessions
- Excludes soft-deleted GT objects

**Fixed Example**: Session `2c9a93f6` should be:
- Correct recall: Depends on actual GT count from database query
- Formula: `83 / actual_gt_count_from_database`

## Installation

No additional dependencies required. The script uses the existing project dependencies.

## Usage

### 1. Dry-Run Mode (Preview Changes)

**Always start with a dry-run to preview what will change:**

```bash
cd /home/rigade/Testing/ai-model-validation-platform/backend
python scripts/recalculate_recall_values.py --dry-run
```

This will show:
- Which sessions will be updated
- Old vs. new recall values
- Detailed breakdown per session
- **No changes will be made to the database**

### 2. Update All Sessions

Once you've reviewed the dry-run output:

```bash
python scripts/recalculate_recall_values.py
```

This will:
- Recalculate recall for all sessions
- Update the database with corrected values
- Create a log file with timestamp

### 3. Update Specific Session

To update only a specific session:

```bash
python scripts/recalculate_recall_values.py --session-id 2c9a93f6-8471-4f2e-b1a7-06f239fca548
```

### 4. Use Custom Database

To use a different database:

```bash
python scripts/recalculate_recall_values.py --database sqlite:///./test_database.db
```

### 5. Verbose Logging

For detailed debugging information:

```bash
python scripts/recalculate_recall_values.py --verbose
```

## Output Format

### Per-Session Output

```
================================================================================
Session 2c9a93f6-8471-4f2e-b1a7-06f239fca548
Name: Multi-Video Test Session
================================================================================
Type: Multi-video sequence
Videos:
  - video1.mp4: 131 GT events
  - video2.mp4: 126 GT events

Metrics:
  Total GT Events: 257
  True Positives (TP): 83
  False Negatives (FN): 174

Recall Calculation:
  Old Stored Value: 0.3229 (32.29%)
  OLD METHOD: 0.3229 = 83/(83+174) - WRONG!
  NEW METHOD: 0.6336 = 83/131 - CORRECT ✓
  New Recall: 0.6336 (63.36%)
  Change: ↑ 0.3107 (31.07 percentage points)

✅ Updated
```

### Summary Output

```
================================================================================
SUMMARY
================================================================================
Total sessions processed: 15
Sessions updated: 12
Sessions with no change: 2
Sessions skipped: 1
Errors: 0

✅ Database updated with corrected recall values
```

## Script Features

### 1. Correct Ground Truth Counting

The script implements the exact same logic as `ground_truth_matching_service.py`:

```python
def get_actual_ground_truth_count(db, test_session):
    if test_session.has_video_sequence:
        # Multi-video: Count GT across all videos in sequence
        video_ids = test_session.sequence_metadata['video_ids']
        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id.in_(video_ids),
            GroundTruthObject.deleted_at.is_(None)  # Exclude soft-deleted
        ).scalar()
    else:
        # Single video: Count GT for just this video
        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id == test_session.video_id,
            GroundTruthObject.deleted_at.is_(None)
        ).scalar()
    return gt_count
```

### 2. Edge Case Handling

- **No Ground Truth Data**: Skips sessions with no GT objects
- **Zero TP**: Correctly calculates recall as 0.0
- **Multi-Video Sessions**: Sums GT counts across all videos in sequence
- **Soft-Deleted GT**: Excludes GT objects marked as deleted

### 3. Logging

The script creates a timestamped log file:
```
recall_recalculation_20251124_150325.log
```

All operations are logged with:
- INFO level: Session processing, updates
- WARNING level: Edge cases, missing data
- ERROR level: Exceptions, failures

### 4. Safety Features

- **Dry-run mode**: Preview changes before committing
- **Transaction safety**: Each session update is committed separately
- **Error isolation**: Errors in one session don't affect others
- **Detailed reporting**: Clear before/after comparisons

## Common Scenarios

### Scenario 1: Multi-Video Session with Incorrect Recall

**Before:**
```
Session: 2c9a93f6
Videos: video1 (131 GT), video2 (126 GT)
TP: 83, FN: 174
Stored Recall: 0.3229 (using 83/(83+174))
```

**After:**
```
Session: 2c9a93f6
Videos: video1 (131 GT), video2 (126 GT)
TP: 83
Actual GT Count: 257 (from database)
Corrected Recall: 0.3230 (using 83/257)
```

### Scenario 2: Single-Video Session

**Before:**
```
Session: abc123
Video: test_video.mp4 (50 GT)
TP: 45, FN: 5
Stored Recall: 0.9000 (using 45/(45+5))
```

**After:**
```
Session: abc123
Video: test_video.mp4 (50 GT)
TP: 45
Actual GT Count: 50 (from database)
Corrected Recall: 0.9000 (using 45/50)
```
*No change in this case - the old method happened to be correct*

### Scenario 3: Session with Missing GT Data

```
Session: def456
Videos: video_without_gt.mp4
TP: 10, FN: 0
Stored Recall: 1.0000

⚠️ Skipped: no_ground_truth_data
Cannot recalculate without GT objects in database
```

## Troubleshooting

### Issue: "No sessions found with recall values"

**Cause**: Database has no test sessions with recall values set

**Solution**: Run test sessions first, or check database connection

### Issue: "No ground truth data found"

**Cause**: Test session references videos without GT objects

**Solution**:
1. Check if GT objects exist for the video(s)
2. Verify video_id mapping is correct
3. Ensure GT objects aren't all soft-deleted

### Issue: "Invalid TP count"

**Cause**: TP count exceeds actual GT count (data corruption)

**Solution**:
1. Review the session data manually
2. Check if GT objects were deleted after test
3. May need to rerun ground truth matching

## Database Schema

### Fields Updated

The script updates the following field in the `test_sessions` table:

- `accuracy_recall` (Float): Updated with corrected recall value

### Related Fields (Not Modified)

- `tp_count`: True positive count (used for calculation)
- `fn_count`: False negative count (for reference only)
- `accuracy_precision`: Not affected by this script
- `accuracy_f1_score`: Consider recalculating separately if needed

## Verification

After running the script, verify the changes:

```bash
# Check specific session
sqlite3 dev_database.db "
SELECT
    id,
    name,
    tp_count,
    fn_count,
    accuracy_recall,
    has_video_sequence
FROM test_sessions
WHERE id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548';
"

# Check all sessions with updated recall
sqlite3 dev_database.db "
SELECT
    COUNT(*) as total_sessions,
    AVG(accuracy_recall) as avg_recall,
    MIN(accuracy_recall) as min_recall,
    MAX(accuracy_recall) as max_recall
FROM test_sessions
WHERE accuracy_recall IS NOT NULL;
"
```

## Best Practices

1. **Always run dry-run first**: Preview changes before committing
2. **Back up database**: Create backup before running script
3. **Review log files**: Check for warnings or errors
4. **Verify results**: Spot-check a few sessions manually
5. **Run during maintenance window**: Avoid running during active testing

## Backup and Recovery

### Create Backup

```bash
# SQLite backup
cp dev_database.db dev_database.db.backup_$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
pg_dump -h localhost -U user database > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Backup

```bash
# SQLite restore
cp dev_database.db.backup_20251124_150000 dev_database.db

# PostgreSQL restore
psql -h localhost -U user database < backup_20251124_150000.sql
```

## Script Maintenance

### Future Updates

If the ground truth counting logic changes in `ground_truth_matching_service.py`, update:

1. `get_actual_ground_truth_count()` method
2. Add new edge case handling if needed
3. Update tests and documentation

### Testing the Script

```bash
# Test with sample database
python scripts/recalculate_recall_values.py \
    --database sqlite:///./test_database.db \
    --dry-run \
    --verbose

# Test with specific session
python scripts/recalculate_recall_values.py \
    --session-id test-session-id \
    --dry-run
```

## Related Documentation

- `ground_truth_matching_service.py`: Source of correct recall calculation
- `INSTRUMENTED_TEST_RESULTS.md`: Test results showing the issue
- `PER_VIDEO_ANALYSIS_SUMMARY.md`: Per-video recall analysis

## Support

For issues or questions:
1. Check log files for detailed error messages
2. Review this guide's troubleshooting section
3. Examine the script source code comments
4. Contact the development team

---

**Last Updated**: 2025-11-24
**Script Version**: 1.0.0
**Author**: AI Model Validation Platform Team
