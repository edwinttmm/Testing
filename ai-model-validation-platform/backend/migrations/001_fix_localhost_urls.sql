-- Migration: Fix localhost URLs to production URLs
-- Version: 001
-- Description: Update all localhost URLs to production server URLs (155.138.239.131:8000)
-- Author: Backend Migration System
-- Date: 2025-08-26

-- Start transaction for atomic operation
BEGIN TRANSACTION;

-- Create backup table for videos before migration
CREATE TABLE IF NOT EXISTS videos_backup_pre_url_migration AS 
SELECT * FROM videos WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%';

-- Create migration log table
CREATE TABLE IF NOT EXISTS migration_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    migration_name VARCHAR(255) NOT NULL,
    table_name VARCHAR(255) NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    executed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending'
);

-- Function to log migration changes
INSERT INTO migration_logs (migration_name, table_name, column_name, old_value, new_value, status)
SELECT 
    '001_fix_localhost_urls',
    'videos',
    'url',
    url,
    REPLACE(
        REPLACE(url, 'http://localhost:8000', 'http://155.138.239.131:8000'),
        'http://127.0.0.1:8000', 'http://155.138.239.131:8000'
    ),
    'pending'
FROM videos 
WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%';

-- Update videos table - replace localhost URLs
UPDATE videos 
SET url = REPLACE(
    REPLACE(url, 'http://localhost:8000', 'http://155.138.239.131:8000'),
    'http://127.0.0.1:8000', 'http://155.138.239.131:8000'
)
WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%';

-- Update any thumbnail_url columns if they exist
UPDATE videos 
SET thumbnail_url = REPLACE(
    REPLACE(thumbnail_url, 'http://localhost:8000', 'http://155.138.239.131:8000'),
    'http://127.0.0.1:8000', 'http://155.138.239.131:8000'
)
WHERE thumbnail_url LIKE '%localhost%' OR thumbnail_url LIKE '%127.0.0.1%';

-- Check for other tables with potential URL columns
-- This will be expanded by the schema analyzer

-- Mark migration as completed in logs
UPDATE migration_logs 
SET status = 'completed' 
WHERE migration_name = '001_fix_localhost_urls' AND status = 'pending';

-- Create migration status record
INSERT INTO migration_logs (migration_name, table_name, column_name, old_value, new_value, status)
VALUES ('001_fix_localhost_urls', 'system', 'migration_status', 'started', 'completed', 'completed');

COMMIT;

-- Verification queries (to be run separately)
/*
-- Count of remaining localhost URLs
SELECT 
    'videos' as table_name,
    'url' as column_name,
    COUNT(*) as localhost_count
FROM videos 
WHERE url LIKE '%localhost%' OR url LIKE '%127.0.0.1%';

-- Sample of updated URLs
SELECT id, url FROM videos LIMIT 10;

-- Migration log summary
SELECT 
    table_name,
    column_name,
    COUNT(*) as records_updated,
    status
FROM migration_logs 
WHERE migration_name = '001_fix_localhost_urls'
GROUP BY table_name, column_name, status;
*/