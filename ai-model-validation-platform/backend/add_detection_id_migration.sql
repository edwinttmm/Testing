
-- Migration: Add detection_id column to detection_events table
-- Date: 2025-08-22
-- Issue: Column "detection_id" of relation "detection_events" does not exist

-- Add detection_id column
ALTER TABLE detection_events 
ADD COLUMN IF NOT EXISTS detection_id VARCHAR(36);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_detection_events_detection_id 
ON detection_events(detection_id);

-- Verify the change
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'detection_events' 
ORDER BY ordinal_position;
