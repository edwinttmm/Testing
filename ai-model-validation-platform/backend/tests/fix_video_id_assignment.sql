-- Quick Fix: Assign video_id based on video_relative_timestamp
-- Session: 0846e476-2e21-499c-bfc8-0b2218081c77
-- Date: 2025-11-04
-- Issue: 501/502 detections have NULL video_id

-- Backup current state
CREATE TABLE IF NOT EXISTS detection_events_backup_20251104 AS
SELECT * FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77';

-- Verify backup
SELECT COUNT(*) as backup_count FROM detection_events_backup_20251104;

-- Fix: Assign Video 1 (first 5 seconds)
UPDATE detection_events
SET video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5',
    updated_at = CURRENT_TIMESTAMP
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
  AND video_id IS NULL
  AND video_relative_timestamp < 5.0;

-- Fix: Assign Video 2 (second 5 seconds)
UPDATE detection_events
SET video_id = '550e3cf8-2755-42df-8c3c-041300735f93',
    updated_at = CURRENT_TIMESTAMP
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
  AND video_id IS NULL
  AND video_relative_timestamp >= 5.0;

-- Verify results
SELECT
    video_id,
    COUNT(*) as count,
    MIN(video_relative_timestamp) as min_ts,
    MAX(video_relative_timestamp) as max_ts,
    ROUND(AVG(video_relative_timestamp), 3) as avg_ts
FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
GROUP BY video_id
ORDER BY video_id;

-- Verify no NULL video_ids remain
SELECT COUNT(*) as null_count
FROM detection_events
WHERE test_session_id = '0846e476-2e21-499c-bfc8-0b2218081c77'
  AND video_id IS NULL;

-- Expected output:
-- Video 10c2b16c-86fa-4140-b1cf-c0ea42f82ca5: ~251 detections (0-5s)
-- Video 550e3cf8-2755-42df-8c3c-041300735f93: ~251 detections (5-10s)
-- NULL count: 0
