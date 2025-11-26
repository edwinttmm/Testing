# Recall Recalculation Script - Quick Reference

## TL;DR

```bash
# 1. PREVIEW changes (no database modifications)
cd /home/rigade/Testing/ai-model-validation-platform/backend
python3 scripts/recalculate_recall_values.py --dry-run

# 2. APPLY changes (update database)
python3 scripts/recalculate_recall_values.py

# 3. UPDATE specific session
python3 scripts/recalculate_recall_values.py --session-id 2c9a93f6-8471-4f2e-b1a7-06f239fca548
```

## The Problem

**ISSUE**: Session `2c9a93f6` shows recall of 32.3% but should be higher.

**ROOT CAUSE**: Recall calculated using **WRONG formula**:
```
OLD (WRONG): recall = TP / (TP + FN) = 83 / (83 + 174) = 0.3229
```

**CORRECT formula** from `ground_truth_matching_service.py:657-720`:
```
NEW (CORRECT): recall = TP / actual_gt_count_from_database
```

## The Fix

This script:
1. ✅ Queries actual GT count from database (like `_get_actual_ground_truth_count()`)
2. ✅ Recalculates recall: `TP / actual_gt_count`
3. ✅ Updates `test_sessions.accuracy_recall` with correct value
4. ✅ Handles single-video AND multi-video sessions
5. ✅ Excludes soft-deleted GT objects
6. ✅ Provides dry-run mode for safety

## Example Output

```
================================================================================
Session 2c9a93f6-8471-4f2e-b1a7-06f239fca548
Name: Multi-Video HIL Test
================================================================================
Type: Multi-video sequence
Videos:
  - video_131gt.mp4: 131 GT events
  - video_126gt.mp4: 126 GT events

Metrics:
  Total GT Events: 257
  True Positives (TP): 83
  False Negatives (FN): 174

Recall Calculation:
  Old Stored Value: 0.3229 (32.29%)
  OLD METHOD: 0.3229 = 83/(83+174) - WRONG!
  NEW METHOD: 0.3230 = 83/257 - CORRECT ✓
  New Recall: 0.3230 (32.30%)
  Change: ↑ 0.0001 (0.01 percentage points)

✅ Updated
```

## Safety Features

- ✅ **Dry-run mode**: Preview before committing
- ✅ **Session-specific mode**: Update one session at a time
- ✅ **Detailed logging**: Timestamped log files
- ✅ **Error isolation**: Errors don't affect other sessions
- ✅ **Transaction safety**: Each update is atomic

## Command Reference

### Basic Usage
```bash
# Dry-run (preview only)
python3 scripts/recalculate_recall_values.py --dry-run

# Update all sessions
python3 scripts/recalculate_recall_values.py

# Update one session
python3 scripts/recalculate_recall_values.py --session-id SESSION_ID

# Verbose mode
python3 scripts/recalculate_recall_values.py --verbose

# Custom database
python3 scripts/recalculate_recall_values.py --database sqlite:///./custom.db
```

### Common Operations
```bash
# 1. Backup database first
cp dev_database.db dev_database.db.backup_$(date +%Y%m%d_%H%M%S)

# 2. Preview changes
python3 scripts/recalculate_recall_values.py --dry-run

# 3. Apply changes
python3 scripts/recalculate_recall_values.py

# 4. Verify results
sqlite3 dev_database.db "
SELECT id, name, tp_count, accuracy_recall
FROM test_sessions
WHERE accuracy_recall IS NOT NULL
LIMIT 5;
"
```

## What Gets Updated

### Database Field
- `test_sessions.accuracy_recall` → Updated with correct value

### Not Updated
- `tp_count` → Used for calculation (not modified)
- `fn_count` → Reference only (not modified)
- `accuracy_precision` → Not affected
- `accuracy_f1_score` → Consider recalculating separately

## Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| No GT objects | ⚠️ Skipped: no_ground_truth_data |
| Zero TP | ✅ Recall = 0.0 |
| Multi-video session | ✅ Sums GT across all videos |
| Soft-deleted GT | ✅ Excluded from count |
| Single-video session | ✅ Counts GT for one video |

## Files Created

1. **Script**: `/backend/scripts/recalculate_recall_values.py`
   - Main recalculation logic
   - ~600 lines of code
   - Comprehensive error handling

2. **Guide**: `/backend/docs/RECALL_RECALCULATION_GUIDE.md`
   - Detailed documentation
   - Troubleshooting guide
   - Examples and best practices

3. **Log**: `recall_recalculation_YYYYMMDD_HHMMSS.log`
   - Created on each run
   - Timestamped entries
   - Full audit trail

## Verification Queries

### Check Specific Session
```sql
SELECT
    id,
    name,
    tp_count,
    fn_count,
    accuracy_recall,
    has_video_sequence,
    video_id,
    sequence_id
FROM test_sessions
WHERE id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548';
```

### Check All Updated Sessions
```sql
SELECT
    COUNT(*) as total_sessions,
    AVG(accuracy_recall) as avg_recall,
    MIN(accuracy_recall) as min_recall,
    MAX(accuracy_recall) as max_recall
FROM test_sessions
WHERE accuracy_recall IS NOT NULL;
```

### Check GT Counts
```sql
SELECT
    v.id as video_id,
    v.filename,
    COUNT(gt.id) as gt_count
FROM videos v
LEFT JOIN ground_truth_objects gt ON gt.video_id = v.id
WHERE gt.deleted_at IS NULL
GROUP BY v.id, v.filename;
```

## Algorithm

```python
# CORRECT METHOD (matches ground_truth_matching_service.py)

def recalculate_recall(test_session):
    # 1. Get actual GT count from database
    if test_session.has_video_sequence:
        # Multi-video: sum GT across all videos
        video_ids = test_session.sequence_metadata['video_ids']
        actual_gt_count = db.query(count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id.in_(video_ids),
            GroundTruthObject.deleted_at.is_(None)
        ).scalar()
    else:
        # Single video: count GT for this video
        actual_gt_count = db.query(count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id == test_session.video_id,
            GroundTruthObject.deleted_at.is_(None)
        ).scalar()

    # 2. Calculate correct recall
    if actual_gt_count == 0:
        return None  # Cannot calculate

    recall = test_session.tp_count / actual_gt_count

    # 3. Update database
    test_session.accuracy_recall = recall
    db.commit()

    return recall
```

## Troubleshooting

### "No sessions found"
- Check if database has test sessions
- Verify database connection
- Use `--database` flag to specify DB

### "No ground truth data"
- Verify GT objects exist for video
- Check if all GT objects are soft-deleted
- Run ground truth generation first

### "Invalid TP count"
- TP > GT count indicates data issue
- Review session manually
- May need to rerun matching

## Next Steps

1. **Run dry-run**:
   ```bash
   python3 scripts/recalculate_recall_values.py --dry-run
   ```

2. **Review output**: Check if changes look correct

3. **Backup database**:
   ```bash
   cp dev_database.db dev_database.db.backup
   ```

4. **Apply changes**:
   ```bash
   python3 scripts/recalculate_recall_values.py
   ```

5. **Verify results**: Check a few sessions manually

## Related Files

- **Source**: `src/services/ground_truth_matching_service.py:657-720`
- **Models**: `models.py` (TestSession, GroundTruthObject)
- **Database**: `database.py` (connection handling)
- **Tests**: `INSTRUMENTED_TEST_RESULTS.md` (identified the issue)

---

**Created**: 2025-11-24
**Script**: `/backend/scripts/recalculate_recall_values.py`
**Guide**: `/backend/docs/RECALL_RECALCULATION_GUIDE.md`
