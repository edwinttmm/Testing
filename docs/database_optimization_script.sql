-- Database Performance Optimization Script
-- AI Model Validation Platform
-- Generated: 2025-08-10

-- ===================================
-- CRITICAL PERFORMANCE INDEXES
-- ===================================

-- Projects table indexes
CREATE INDEX IF NOT EXISTS idx_projects_owner_id ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);

-- Videos table indexes
CREATE INDEX IF NOT EXISTS idx_videos_project_id ON videos(project_id);
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_ground_truth ON videos(ground_truth_generated);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);

-- Ground Truth Objects indexes
CREATE INDEX IF NOT EXISTS idx_ground_truth_video_id ON ground_truth_objects(video_id);
CREATE INDEX IF NOT EXISTS idx_ground_truth_timestamp ON ground_truth_objects(timestamp);
CREATE INDEX IF NOT EXISTS idx_ground_truth_class ON ground_truth_objects(class_label);
CREATE INDEX IF NOT EXISTS idx_ground_truth_confidence ON ground_truth_objects(confidence DESC);

-- Test Sessions indexes
CREATE INDEX IF NOT EXISTS idx_test_sessions_project_id ON test_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_video_id ON test_sessions(video_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_status ON test_sessions(status);
CREATE INDEX IF NOT EXISTS idx_test_sessions_started_at ON test_sessions(started_at DESC);

-- Detection Events indexes
CREATE INDEX IF NOT EXISTS idx_detection_events_session_id ON detection_events(test_session_id);
CREATE INDEX IF NOT EXISTS idx_detection_events_timestamp ON detection_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_detection_events_validation ON detection_events(validation_result);
CREATE INDEX IF NOT EXISTS idx_detection_events_confidence ON detection_events(confidence DESC);

-- Audit Logs indexes
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ip_address ON audit_logs(ip_address);

-- ===================================
-- COMPOSITE INDEXES FOR COMMON QUERIES
-- ===================================

-- Project-Video relationship queries
CREATE INDEX IF NOT EXISTS idx_videos_project_status ON videos(project_id, status);

-- Test session performance queries
CREATE INDEX IF NOT EXISTS idx_test_sessions_project_status ON test_sessions(project_id, status);

-- Detection event analysis queries
CREATE INDEX IF NOT EXISTS idx_detection_events_session_validation ON detection_events(test_session_id, validation_result);
CREATE INDEX IF NOT EXISTS idx_detection_events_session_timestamp ON detection_events(test_session_id, timestamp);

-- Ground truth lookup queries
CREATE INDEX IF NOT EXISTS idx_ground_truth_video_timestamp ON ground_truth_objects(video_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_ground_truth_video_class ON ground_truth_objects(video_id, class_label);

-- ===================================
-- QUERY OPTIMIZATION VIEWS
-- ===================================

-- Dashboard statistics view for better performance
CREATE VIEW IF NOT EXISTS dashboard_stats AS
SELECT 
    COUNT(DISTINCT p.id) as project_count,
    COUNT(DISTINCT v.id) as video_count,
    COUNT(DISTINCT ts.id) as test_session_count,
    COUNT(DISTINCT de.id) as detection_event_count,
    AVG(CASE WHEN de.validation_result = 'TP' THEN de.confidence ELSE NULL END) as avg_accuracy
FROM projects p
LEFT JOIN videos v ON p.id = v.project_id
LEFT JOIN test_sessions ts ON p.id = ts.project_id
LEFT JOIN detection_events de ON ts.id = de.test_session_id;

-- Project summary view with aggregated data
CREATE VIEW IF NOT EXISTS project_summary AS
SELECT 
    p.id,
    p.name,
    p.status,
    p.created_at,
    COUNT(DISTINCT v.id) as video_count,
    COUNT(DISTINCT ts.id) as test_session_count,
    COUNT(DISTINCT CASE WHEN v.ground_truth_generated THEN v.id END) as processed_videos,
    AVG(CASE WHEN de.validation_result = 'TP' THEN de.confidence END) as avg_accuracy
FROM projects p
LEFT JOIN videos v ON p.id = v.project_id
LEFT JOIN test_sessions ts ON p.id = ts.project_id
LEFT JOIN detection_events de ON ts.id = de.test_session_id
GROUP BY p.id, p.name, p.status, p.created_at;

-- ===================================
-- PERFORMANCE ANALYSIS QUERIES
-- ===================================

-- Find slow queries (for PostgreSQL)
-- SELECT query, mean_time, calls, total_time 
-- FROM pg_stat_statements 
-- ORDER BY mean_time DESC 
-- LIMIT 10;

-- Table size analysis (for PostgreSQL)
-- SELECT 
--     schemaname,
--     tablename,
--     attname,
--     n_distinct,
--     correlation
-- FROM pg_stats
-- WHERE schemaname = 'public'
-- ORDER BY n_distinct DESC;

-- Index usage statistics (for PostgreSQL)
-- SELECT
--     schemaname,
--     tablename,
--     attname,
--     n_distinct,
--     correlation
-- FROM pg_stats
-- WHERE schemaname = 'public';

-- ===================================
-- MAINTENANCE QUERIES
-- ===================================

-- Analyze table statistics (for PostgreSQL)
-- ANALYZE projects;
-- ANALYZE videos;
-- ANALYZE ground_truth_objects;
-- ANALYZE test_sessions;
-- ANALYZE detection_events;
-- ANALYZE audit_logs;

-- Vacuum tables (for PostgreSQL)
-- VACUUM ANALYZE projects;
-- VACUUM ANALYZE videos;
-- VACUUM ANALYZE ground_truth_objects;
-- VACUUM ANALYZE test_sessions;
-- VACUUM ANALYZE detection_events;
-- VACUUM ANALYZE audit_logs;

-- ===================================
-- PERFORMANCE MONITORING QUERIES
-- ===================================

-- Monitor query performance
SELECT 
    'Database Performance Check' as check_type,
    datetime('now') as check_time,
    (SELECT COUNT(*) FROM projects) as total_projects,
    (SELECT COUNT(*) FROM videos) as total_videos,
    (SELECT COUNT(*) FROM ground_truth_objects) as total_ground_truth_objects,
    (SELECT COUNT(*) FROM test_sessions) as total_test_sessions,
    (SELECT COUNT(*) FROM detection_events) as total_detection_events;

-- Check for missing foreign key relationships
SELECT 
    'Data Integrity Check' as check_type,
    (SELECT COUNT(*) FROM videos WHERE project_id NOT IN (SELECT id FROM projects)) as orphaned_videos,
    (SELECT COUNT(*) FROM ground_truth_objects WHERE video_id NOT IN (SELECT id FROM videos)) as orphaned_ground_truth,
    (SELECT COUNT(*) FROM test_sessions WHERE project_id NOT IN (SELECT id FROM projects)) as orphaned_test_sessions,
    (SELECT COUNT(*) FROM detection_events WHERE test_session_id NOT IN (SELECT id FROM test_sessions)) as orphaned_detection_events;

-- Performance baseline metrics
SELECT 
    'Performance Baseline' as metric_type,
    datetime('now') as measured_at,
    (SELECT MAX(created_at) FROM projects) as latest_project,
    (SELECT MAX(created_at) FROM videos) as latest_video,
    (SELECT AVG(confidence) FROM detection_events WHERE validation_result = 'TP') as avg_tp_confidence,
    (SELECT COUNT(*) * 1.0 / COUNT(DISTINCT test_session_id) FROM detection_events) as avg_detections_per_session;

PRAGMA table_info(projects);
PRAGMA table_info(videos);
PRAGMA table_info(ground_truth_objects);
PRAGMA table_info(test_sessions);
PRAGMA table_info(detection_events);
PRAGMA table_info(audit_logs);