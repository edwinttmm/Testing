-- QUICK FIX: Clean Frame 0 GT Data Corruption
-- Session: 49e5d00f-eea7-44cb-a647-480268ef43ee
-- Issue: Frame 0 contains 257 corrupted GT objects spanning entire video
-- Impact: 0% precision, 0% recall in GT matching
-- Date: 2025-11-20

-- ============================================================================
-- BACKUP FIRST (Safety measure)
-- ============================================================================

CREATE TABLE IF NOT EXISTS ground_truth_objects_backup_20251120 AS
SELECT * FROM ground_truth_objects WHERE frame_number = 0;

-- Verify backup
SELECT COUNT(*) as backed_up_objects FROM ground_truth_objects_backup_20251120;

-- ============================================================================
-- INVESTIGATE (Before deleting)
-- ============================================================================

-- Show Frame 0 corruption statistics
SELECT
    video_id,
    COUNT(*) as frame0_objects,
    MIN(timestamp) as min_timestamp,
    MAX(timestamp) as max_timestamp,
    ROUND(MAX(timestamp) - MIN(timestamp), 2) as time_span_seconds
FROM ground_truth_objects
WHERE frame_number = 0
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
)
GROUP BY video_id;

-- Expected output:
-- video_id                               frame0_objects  min_timestamp  max_timestamp  time_span_seconds
-- 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5  131             0.000          5.000          5.00
-- 550e3cf8-2755-42df-8c3c-041300735f93  126             0.000          5.000          5.00

-- ============================================================================
-- DELETE CORRUPTED FRAME 0 DATA
-- ============================================================================

-- Delete Frame 0 objects (corrupted data)
DELETE FROM ground_truth_objects
WHERE frame_number = 0
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
);

-- Expected: 257 rows deleted

-- ============================================================================
-- VERIFY CLEANUP
-- ============================================================================

-- Should return 0 (all Frame 0 data deleted)
SELECT COUNT(*) as remaining_frame0_objects
FROM ground_truth_objects
WHERE frame_number = 0
AND video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
);

-- Check remaining GT data is valid
SELECT
    video_id,
    MIN(frame_number) as min_frame,
    MAX(frame_number) as max_frame,
    COUNT(DISTINCT frame_number) as unique_frames,
    COUNT(*) as total_objects
FROM ground_truth_objects
WHERE video_id IN (
    '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    '550e3cf8-2755-42df-8c3c-041300735f93'
)
GROUP BY video_id;

-- Expected output (after cleanup):
-- video_id                               min_frame  max_frame  unique_frames  total_objects
-- 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5  1          121        121            131
-- 550e3cf8-2755-42df-8c3c-041300735f93  1          121        121            126

-- Check timestamp distribution is now correct
SELECT
    frame_number,
    COUNT(*) as objects,
    ROUND(MIN(timestamp), 3) as min_time,
    ROUND(MAX(timestamp), 3) as max_time
FROM ground_truth_objects
WHERE video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5'
GROUP BY frame_number
ORDER BY frame_number
LIMIT 10;

-- Expected: Frame N at ~(N/24) seconds
-- Frame 1: ~0.000s
-- Frame 2: ~0.042s
-- Frame 3: ~0.083s
-- etc.

-- ============================================================================
-- NEXT STEPS
-- ============================================================================

-- 1. Re-run GT matching:
--    python3 -c "
--    from services.ground_truth_matching_service import GroundTruthMatchingService
--    service = GroundTruthMatchingService()
--    metrics = service.match_detections_to_ground_truth(
--        '49e5d00f-eea7-44cb-a647-480268ef43ee',
--        force_rematch=True
--    )
--    print(f'Precision: {metrics.precision:.1%}')
--    print(f'Recall: {metrics.recall:.1%}')
--    print(f'TP: {metrics.true_positives}')
--    print(f'FP: {metrics.false_positives}')
--    print(f'FN: {metrics.false_negatives}')
--    "
--
-- 2. Expected results:
--    - Precision: >70% (up from 0%)
--    - Recall: >90% (up from 0%)
--    - TP: >100 (up from 0)
--    - FP: <50 (down from 192)
--    - FN: <30 (down from 257)
--
-- 3. If successful, update INTEGRATION_VERIFICATION_REPORT.md with new metrics
