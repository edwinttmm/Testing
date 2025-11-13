-- ====================================================================
-- GROUND TRUTH DUPLICATE CLEANUP - Session 6c899aa4
-- ====================================================================
-- Problem: 514 objects shown when expected ~240 (2 videos × ~120 each)
-- Root Cause: Duplicate class labels stored as both:
--   - 'VRUTypeEnum.PEDESTRIAN' (enum repr - WRONG)
--   - 'pedestrian' (enum value - CORRECT)
-- Impact: 257 duplicate records across 2 videos
-- ====================================================================

-- STEP 1: Backup Verification (Run BEFORE cleanup)
-- ====================================================================
SELECT
    '=== BEFORE CLEANUP ===' as step,
    video_id,
    class_label,
    COUNT(*) as count
FROM ground_truth_objects
WHERE deleted_at IS NULL
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
)
GROUP BY video_id, class_label
ORDER BY video_id, class_label;

-- Expected output:
-- Video 10c2b16c...: VRUTypeEnum.PEDESTRIAN (121), pedestrian (121), VRUTypeEnum.CYCLIST (10), cyclist (10)
-- Video 550e3cf8...: VRUTypeEnum.PEDESTRIAN (121), pedestrian (121), VRUTypeEnum.CYCLIST (5), cyclist (5)
-- Total: 514 objects

-- STEP 2: Count records to be deleted
-- ====================================================================
SELECT
    '=== RECORDS TO BE DELETED ===' as step,
    COUNT(*) as duplicate_count,
    COUNT(DISTINCT video_id) as video_count
FROM ground_truth_objects
WHERE class_label LIKE 'VRUTypeEnum.%'
AND deleted_at IS NULL;

-- Expected: 257 records across 2 videos

-- STEP 3: Soft Delete Duplicate Records
-- ====================================================================
-- WARNING: This marks 257 records as deleted. They remain in database but excluded from queries.

UPDATE ground_truth_objects
SET
    deleted_at = datetime('now'),
    deleted_by = 'system_cleanup_agent7_514bug'
WHERE
    class_label LIKE 'VRUTypeEnum.%'
    AND deleted_at IS NULL;

-- STEP 4: Verify Cleanup Success
-- ====================================================================
SELECT
    '=== AFTER CLEANUP ===' as step,
    video_id,
    class_label,
    COUNT(*) as count
FROM ground_truth_objects
WHERE deleted_at IS NULL
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
)
GROUP BY video_id, class_label
ORDER BY video_id, class_label;

-- Expected output after cleanup:
-- Video 10c2b16c...: pedestrian (121), cyclist (10)  = 131 objects
-- Video 550e3cf8...: pedestrian (121), cyclist (5)   = 126 objects
-- Total: 257 objects (was 514 before)

-- STEP 5: Verify Deleted Count
-- ====================================================================
SELECT
    '=== CLEANUP SUMMARY ===' as step,
    COUNT(*) as deleted_count,
    MIN(deleted_at) as first_deleted,
    MAX(deleted_at) as last_deleted
FROM ground_truth_objects
WHERE deleted_by = 'system_cleanup_agent7_514bug';

-- Expected: 257 records deleted

-- STEP 6: Session Ground Truth Verification
-- ====================================================================
SELECT
    '=== SESSION VERIFICATION ===' as step,
    svr.video_id,
    v.filename,
    COUNT(gt.id) as active_gt_count
FROM sequence_video_results svr
JOIN videos v ON v.id = svr.video_id
LEFT JOIN ground_truth_objects gt ON gt.video_id = svr.video_id AND gt.deleted_at IS NULL
WHERE svr.video_sequence_id IN (
    SELECT id FROM video_test_sequences
    WHERE test_session_id = '6c899aa4-bbd2-4a93-b052-f09e4e11889c'
)
GROUP BY svr.video_id, v.filename
ORDER BY svr.sequence_order;

-- Expected:
-- Video 1: 131 active GT objects
-- Video 2: 126 active GT objects
-- Total: 257 (was 514 before cleanup)

-- STEP 7: Check for Other Sessions with Same Issue
-- ====================================================================
SELECT
    '=== GLOBAL CHECK ===' as step,
    COUNT(*) as total_enum_prefix_records
FROM ground_truth_objects
WHERE class_label LIKE 'VRUTypeEnum.%'
AND deleted_at IS NULL;

-- If > 0, there are other sessions with the same bug

-- STEP 8: Rollback Instructions (IF NEEDED)
-- ====================================================================
-- To restore deleted records (ONLY IF CLEANUP WAS WRONG):
--
-- UPDATE ground_truth_objects
-- SET
--     deleted_at = NULL,
--     deleted_by = NULL
-- WHERE deleted_by = 'system_cleanup_agent7_514bug';

-- ====================================================================
-- NOTES FOR PRODUCTION:
-- ====================================================================
-- 1. Run STEP 1 first to confirm expected state
-- 2. Backup database before running STEP 3
-- 3. Run STEP 3 (UPDATE) during low-traffic period
-- 4. Verify with STEP 4 immediately after
-- 5. Check STEP 7 to find other affected sessions
-- 6. Keep rollback SQL (STEP 8) ready for 24 hours
-- ====================================================================
