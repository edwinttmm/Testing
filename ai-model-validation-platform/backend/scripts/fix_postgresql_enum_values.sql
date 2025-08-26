-- Fix PostgreSQL Enum Values for Projects Table
-- This script updates invalid enum values in the PostgreSQL database

-- Update camera_view enum values
-- Change "Mixed" to "Multi-angle"
UPDATE projects 
SET camera_view = 'Multi-angle'
WHERE camera_view = 'Mixed';

-- Update signal_type enum values  
-- Change "Mixed" to "Network Packet"
UPDATE projects
SET signal_type = 'Network Packet'
WHERE signal_type = 'Mixed';

-- Verify the updates
SELECT 
    id,
    name,
    camera_view,
    signal_type,
    created_at
FROM projects
WHERE camera_view IN ('Mixed', 'Multi-angle') 
   OR signal_type IN ('Mixed', 'Network Packet')
ORDER BY created_at DESC;

-- Count affected records
SELECT 
    'camera_view fixes' as fix_type,
    COUNT(*) as fixed_count
FROM projects 
WHERE camera_view = 'Multi-angle'
UNION ALL
SELECT 
    'signal_type fixes' as fix_type,
    COUNT(*) as fixed_count
FROM projects 
WHERE signal_type = 'Network Packet';