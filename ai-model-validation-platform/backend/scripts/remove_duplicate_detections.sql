-- ========================================
-- Duplicate Detection Event Cleanup Script
-- ========================================
-- Purpose: Identify and remove duplicate detection events
-- Created: 2025-11-04
-- Priority: P0 - Production Blocker
-- ========================================

-- ========================================
-- STEP 1: Identify Duplicate Groups
-- ========================================

-- Find all potential duplicates (same timestamp, same session)
WITH duplicate_groups AS (
    SELECT
        test_session_id,
        ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
        COUNT(*) as duplicate_count,
        ARRAY_AGG(id ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as event_ids,
        ARRAY_AGG(source ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as sources,
        ARRAY_AGG(video_id ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as video_ids,
        ARRAY_AGG(video_relative_timestamp ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as video_timestamps
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '30 days'  -- Last 30 days
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
)
SELECT
    test_session_id,
    timestamp_rounded,
    duplicate_count,
    event_ids,
    sources,
    video_ids,
    video_timestamps
FROM duplicate_groups
ORDER BY duplicate_count DESC, timestamp_rounded DESC;

-- ========================================
-- STEP 2: Analyze Duplicate Quality
-- ========================================

-- Compare completeness of duplicate detection events
WITH duplicate_groups AS (
    SELECT
        test_session_id,
        ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
        COUNT(*) as duplicate_count,
        ARRAY_AGG(id) as event_ids
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '30 days'
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
)
SELECT
    de.id,
    de.source,
    de.test_session_id,
    de.labjack_timestamp,
    de.video_id,
    de.sequence_id,
    de.video_relative_timestamp,
    de.actual_latency_ms,
    de.labjack_voltage,
    de.detection_channel,
    CASE
        WHEN de.video_id IS NOT NULL THEN 1 ELSE 0
    END +
    CASE
        WHEN de.sequence_id IS NOT NULL THEN 1 ELSE 0
    END +
    CASE
        WHEN de.video_relative_timestamp IS NOT NULL THEN 1 ELSE 0
    END +
    CASE
        WHEN de.actual_latency_ms IS NOT NULL THEN 1 ELSE 0
    END AS completeness_score,
    de.created_at
FROM detection_events de
INNER JOIN duplicate_groups dg
    ON de.id = ANY(dg.event_ids)
ORDER BY
    de.test_session_id,
    de.labjack_timestamp,
    completeness_score DESC;

-- ========================================
-- STEP 3: Generate Delete Candidates
-- ========================================

-- List events to be deleted (keep first event from each group)
WITH duplicate_groups AS (
    SELECT
        test_session_id,
        ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
        ARRAY_AGG(id ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as event_ids
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '30 days'
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
),
delete_candidates AS (
    SELECT
        test_session_id,
        timestamp_rounded,
        event_ids[1] as keep_id,
        UNNEST(event_ids[2:]) as delete_id
    FROM duplicate_groups
)
SELECT
    dc.test_session_id,
    dc.timestamp_rounded,
    dc.keep_id,
    keep_de.source as keep_source,
    keep_de.video_id as keep_video_id,
    dc.delete_id,
    del_de.source as delete_source,
    del_de.video_id as delete_video_id,
    del_de.created_at as delete_created_at
FROM delete_candidates dc
INNER JOIN detection_events keep_de ON keep_de.id = dc.keep_id
INNER JOIN detection_events del_de ON del_de.id = dc.delete_id
ORDER BY dc.timestamp_rounded DESC;

-- ========================================
-- STEP 4: DRY RUN - Count Deletions
-- ========================================

-- Count how many events will be deleted
WITH duplicate_groups AS (
    SELECT
        ARRAY_AGG(id ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as event_ids
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '30 days'
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
),
delete_counts AS (
    SELECT
        ARRAY_LENGTH(event_ids, 1) - 1 as deletes_per_group
    FROM duplicate_groups
)
SELECT
    COUNT(*) as duplicate_groups,
    SUM(deletes_per_group) as total_deletes,
    ROUND(AVG(deletes_per_group), 2) as avg_duplicates_per_group
FROM delete_counts;

-- ========================================
-- STEP 5: BACKUP - Create Safety Backup
-- ========================================

-- Create backup table before deletion
CREATE TABLE IF NOT EXISTS detection_events_backup_20251104 AS
WITH duplicate_groups AS (
    SELECT
        test_session_id,
        ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '30 days'
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
)
SELECT de.*
FROM detection_events de
INNER JOIN duplicate_groups dg
    ON de.test_session_id = dg.test_session_id
    AND ROUND(de.labjack_timestamp::numeric, 3) = dg.timestamp_rounded;

-- Verify backup created
SELECT
    COUNT(*) as backup_count,
    MIN(created_at) as oldest_event,
    MAX(created_at) as newest_event
FROM detection_events_backup_20251104;

-- ========================================
-- STEP 6: EXECUTE - Delete Duplicates
-- ========================================

-- ⚠️ WARNING: THIS WILL PERMANENTLY DELETE DATA
-- Run ONLY after reviewing Steps 1-4 above
-- Uncomment the following block to execute

/*
WITH duplicate_groups AS (
    SELECT
        test_session_id,
        ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
        ARRAY_AGG(id ORDER BY
            CASE
                WHEN source = 'dedicated_labjack_monitor' THEN 1
                WHEN source = 'labjack_detection_service' THEN 2
                WHEN source = 'raw_labjack_integration' THEN 3
                ELSE 4
            END,
            created_at ASC
        ) as event_ids
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '30 days'
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
),
delete_candidates AS (
    SELECT UNNEST(event_ids[2:]) as delete_id
    FROM duplicate_groups
)
DELETE FROM detection_events
WHERE id IN (SELECT delete_id FROM delete_candidates);
*/

-- ========================================
-- STEP 7: Verification - Confirm No Duplicates Remain
-- ========================================

-- After deletion, verify no duplicates remain
SELECT
    test_session_id,
    ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
    COUNT(*) as event_count
FROM detection_events
WHERE created_at > NOW() - INTERVAL '30 days'
AND labjack_timestamp IS NOT NULL
GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
HAVING COUNT(*) > 1
ORDER BY event_count DESC;

-- Should return 0 rows if successful

-- ========================================
-- STEP 8: Statistics - Post-Cleanup Report
-- ========================================

-- Generate post-cleanup statistics
SELECT
    'Post-Cleanup Detection Event Stats' as report,
    COUNT(*) as total_events,
    COUNT(DISTINCT test_session_id) as unique_sessions,
    COUNT(CASE WHEN source = 'dedicated_labjack_monitor' THEN 1 END) as from_dedicated_monitor,
    COUNT(CASE WHEN source = 'labjack_detection_service' THEN 1 END) as from_detection_service,
    COUNT(CASE WHEN source = 'raw_labjack_integration' THEN 1 END) as from_raw_integration,
    COUNT(CASE WHEN video_id IS NOT NULL THEN 1 END) as with_video_id,
    COUNT(CASE WHEN sequence_id IS NOT NULL THEN 1 END) as with_sequence_id,
    COUNT(CASE WHEN video_relative_timestamp IS NOT NULL THEN 1 END) as with_video_timestamp,
    ROUND(AVG(actual_latency_ms), 2) as avg_latency_ms
FROM detection_events
WHERE created_at > NOW() - INTERVAL '30 days';

-- ========================================
-- STEP 9: Monitoring - Create Duplicate Detection Alert
-- ========================================

-- Query to run periodically to detect new duplicates
-- Can be used in monitoring system or scheduled job
CREATE OR REPLACE VIEW detection_event_duplicates_v AS
WITH duplicate_groups AS (
    SELECT
        test_session_id,
        ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
        COUNT(*) as duplicate_count,
        ARRAY_AGG(id) as event_ids,
        ARRAY_AGG(source) as sources,
        MAX(created_at) as latest_created
    FROM detection_events
    WHERE created_at > NOW() - INTERVAL '7 days'
    AND labjack_timestamp IS NOT NULL
    GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
    HAVING COUNT(*) > 1
)
SELECT
    test_session_id,
    timestamp_rounded,
    duplicate_count,
    event_ids,
    sources,
    latest_created,
    'ALERT: Duplicate detection events detected' as alert_message
FROM duplicate_groups;

-- Query the view to check for new duplicates
SELECT * FROM detection_event_duplicates_v;

-- ========================================
-- ROLLBACK PROCEDURE (if needed)
-- ========================================

-- If you need to restore deleted events from backup:
/*
INSERT INTO detection_events
SELECT * FROM detection_events_backup_20251104
WHERE id NOT IN (SELECT id FROM detection_events);

-- Verify restoration
SELECT
    'Restoration Stats' as report,
    COUNT(*) as events_restored
FROM detection_events_backup_20251104
WHERE id NOT IN (SELECT id FROM detection_events);
*/

-- ========================================
-- CLEANUP - Drop Backup Table (after verification)
-- ========================================

-- After 7 days, if everything is working correctly:
-- DROP TABLE IF EXISTS detection_events_backup_20251104;

-- ========================================
-- END OF SCRIPT
-- ========================================

-- Execution Summary:
-- 1. Run Steps 1-4 to analyze duplicates
-- 2. Run Step 5 to create backup
-- 3. Uncomment and run Step 6 to delete duplicates
-- 4. Run Step 7 to verify cleanup
-- 5. Run Step 8 to generate statistics
-- 6. Monitor Step 9 view for new duplicates
-- 7. Keep backup for 7 days, then cleanup
