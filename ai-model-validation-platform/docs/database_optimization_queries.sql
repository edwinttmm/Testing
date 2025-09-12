-- Database Optimization Queries for AI Model Validation Platform
-- Optimized queries for common operations with proper index utilization

-- ================================
-- VIDEO MANAGEMENT QUERIES
-- ================================

-- Get videos ready for HIL testing (optimized with compound index)
SELECT v.id, v.filename, v.status, v.ground_truth_count, v.validated_at
FROM videos v
WHERE v.hil_testing_ready = true 
  AND v.status = 'validated'
  AND v.validation_status = 'approved'
ORDER BY v.validated_at DESC;
-- Uses: idx_video_hil_ready, idx_video_status_validation

-- Video validation workflow status (optimized)
SELECT v.id, v.filename, v.status, v.validation_status, 
       v.ground_truth_count, v.ground_truth_quality_score
FROM videos v
WHERE v.project_id = ? 
  AND v.status IN ('processing', 'validated', 'pending_validation')
ORDER BY v.updated_at DESC;
-- Uses: idx_video_project_status

-- ================================
-- GROUND TRUTH ANALYSIS QUERIES  
-- ================================

-- Get ground truth objects for video with temporal filtering (optimized)
SELECT gto.id, gto.timestamp, gto.frame_number, gto.class_label,
       gto.x, gto.y, gto.width, gto.height, gto.confidence
FROM ground_truth_objects gto
WHERE gto.video_id = ?
  AND gto.timestamp BETWEEN ? AND ?
  AND gto.validated = true
ORDER BY gto.timestamp, gto.frame_number;
-- Uses: idx_gt_video_validated_timestamp

-- Ground truth quality analysis (optimized)
SELECT gto.class_label, 
       COUNT(*) as total_objects,
       AVG(gto.confidence) as avg_confidence,
       COUNT(CASE WHEN gto.validated = true THEN 1 END) as validated_count,
       COUNT(CASE WHEN gto.difficult = true THEN 1 END) as difficult_count
FROM ground_truth_objects gto
WHERE gto.video_id = ?
GROUP BY gto.class_label
ORDER BY total_objects DESC;
-- Uses: idx_gt_video_class, idx_gt_validated_class

-- VRU tracking across frames (optimized for temporal analysis)
SELECT gto.tracking_id, gto.timestamp, gto.frame_number, 
       gto.class_label, gto.x, gto.y, gto.width, gto.height
FROM ground_truth_objects gto
WHERE gto.video_id = ? 
  AND gto.tracking_id IS NOT NULL
ORDER BY gto.tracking_id, gto.timestamp;
-- Uses: idx_gt_video_tracking_id, idx_gt_tracking_timestamp

-- ================================
-- DETECTION EVENT ANALYSIS QUERIES
-- ================================

-- LabJack timing analysis for test session (optimized)
SELECT de.id, de.timestamp, de.latency_ms, de.validation_result,
       de.labjack_timestamp, de.voltage_level, de.detection_channel
FROM detection_events de
WHERE de.test_session_id = ?
ORDER BY de.latency_ms DESC;
-- Uses: idx_detection_session_latency

-- Failed detections with high latency (optimized)
SELECT de.id, de.timestamp, de.latency_ms, de.latency_threshold_ms,
       de.screenshot_path, de.vru_type, de.validation_result
FROM detection_events de
WHERE de.test_session_id = ?
  AND de.validation_result = 'Fail'
  AND de.latency_ms > de.latency_threshold_ms
ORDER BY de.latency_ms DESC;
-- Uses: idx_detection_session_labjack_validation

-- Detection events by video with temporal correlation (optimized)
SELECT de.id, de.timestamp, de.latency_ms, de.validation_result,
       de.frame_number, de.vru_type, de.confidence
FROM detection_events de
WHERE de.video_id = ?
  AND de.timestamp BETWEEN ? AND ?
ORDER BY de.timestamp;
-- Uses: idx_detection_video_timestamp

-- ================================
-- ANNOTATION WORKFLOW QUERIES
-- ================================

-- Get annotations for video annotation interface (optimized)
SELECT a.id, a.detection_id, a.frame_number, a.timestamp,
       a.vru_type, a.bounding_box, a.validated, a.annotator
FROM annotations a
WHERE a.video_id = ?
ORDER BY a.frame_number, a.timestamp;
-- Uses: idx_annotation_video_frame

-- Annotation quality analysis per annotator (optimized) 
SELECT a.annotator, a.vru_type,
       COUNT(*) as total_annotations,
       COUNT(CASE WHEN a.validated = true THEN 1 END) as validated_count,
       COUNT(CASE WHEN a.difficult = true THEN 1 END) as difficult_count,
       AVG(CASE WHEN a.end_timestamp IS NOT NULL 
           THEN a.end_timestamp - a.timestamp END) as avg_duration
FROM annotations a
WHERE a.video_id = ?
GROUP BY a.annotator, a.vru_type
ORDER BY total_annotations DESC;
-- Uses: idx_annotation_annotator_validated, idx_annotation_vru_validated

-- Temporal coverage analysis (optimized)
SELECT a.vru_type,
       MIN(a.timestamp) as first_detection,
       MAX(COALESCE(a.end_timestamp, a.timestamp)) as last_detection,
       COUNT(*) as detection_count
FROM annotations a  
WHERE a.video_id = ?
  AND a.validated = true
GROUP BY a.vru_type;
-- Uses: idx_annotation_video_temporal_coverage

-- ================================
-- TEST SESSION & RESULTS QUERIES
-- ================================

-- Test session summary with results (optimized join)
SELECT ts.id, ts.name, ts.status, ts.latency_threshold_ms,
       tr.pass_rate, tr.avg_latency_ms, tr.total_detections,
       tr.passed_detections, tr.failed_detections
FROM test_sessions ts
LEFT JOIN test_results tr ON ts.id = tr.test_session_id
WHERE ts.project_id = ?
ORDER BY ts.created_at DESC;
-- Uses: idx_testsession_project_created, idx_testresult_session_pass_rate

-- Active test sessions monitoring (optimized)
SELECT ts.id, ts.name, ts.status, ts.started_at,
       COUNT(de.id) as detection_count,
       COUNT(CASE WHEN de.validation_result = 'Pass' THEN 1 END) as passed_count
FROM test_sessions ts
LEFT JOIN detection_events de ON ts.id = de.test_session_id
WHERE ts.status = 'running'
  AND ts.started_at > ?
GROUP BY ts.id, ts.name, ts.status, ts.started_at
ORDER BY ts.started_at DESC;
-- Uses: idx_testsession_type_status, idx_detection_session_validation

-- ================================
-- PERFORMANCE ANALYSIS QUERIES
-- ================================

-- Latency distribution analysis (optimized)
SELECT 
    CASE 
        WHEN de.latency_ms < 50 THEN '<50ms'
        WHEN de.latency_ms < 100 THEN '50-100ms'  
        WHEN de.latency_ms < 200 THEN '100-200ms'
        WHEN de.latency_ms < 500 THEN '200-500ms'
        ELSE '>500ms'
    END as latency_bucket,
    COUNT(*) as event_count,
    AVG(de.latency_ms) as avg_latency
FROM detection_events de
WHERE de.test_session_id = ?
  AND de.latency_ms IS NOT NULL
GROUP BY latency_bucket
ORDER BY MIN(de.latency_ms);
-- Uses: idx_detection_session_latency

-- Video processing performance (optimized)
SELECT v.id, v.filename, v.file_size, v.duration,
       COUNT(gto.id) as ground_truth_count,
       COUNT(de.id) as detection_count,
       v.ground_truth_quality_score
FROM videos v
LEFT JOIN ground_truth_objects gto ON v.id = gto.video_id
LEFT JOIN detection_events de ON v.id = de.video_id  
WHERE v.project_id = ?
  AND v.status = 'validated'
GROUP BY v.id, v.filename, v.file_size, v.duration, v.ground_truth_quality_score
ORDER BY v.ground_truth_quality_score DESC;
-- Uses: idx_video_project_status, idx_gt_video_timestamp, idx_detection_video_timestamp

-- ================================
-- SYSTEM HEALTH & MONITORING
-- ================================

-- Database health check queries
SELECT 'videos' as table_name, COUNT(*) as record_count,
       COUNT(CASE WHEN status = 'validated' THEN 1 END) as validated_count
FROM videos
UNION ALL
SELECT 'ground_truth_objects', COUNT(*), COUNT(CASE WHEN validated = true THEN 1 END)
FROM ground_truth_objects  
UNION ALL
SELECT 'detection_events', COUNT(*), COUNT(CASE WHEN validation_result = 'Pass' THEN 1 END)
FROM detection_events
UNION ALL
SELECT 'annotations', COUNT(*), COUNT(CASE WHEN validated = true THEN 1 END)  
FROM annotations;

-- Recent activity monitoring (optimized)
SELECT 'video_upload' as activity_type, COUNT(*) as count
FROM videos 
WHERE created_at > datetime('now', '-1 hour')
UNION ALL
SELECT 'detection_event', COUNT(*)
FROM detection_events
WHERE created_at > datetime('now', '-1 hour')  
UNION ALL
SELECT 'annotation', COUNT(*)
FROM annotations
WHERE created_at > datetime('now', '-1 hour');
-- Uses: idx_video_project_created, idx_detection_created, idx_annotation_created

-- ================================  
-- CLEANUP & MAINTENANCE QUERIES
-- ================================

-- Find orphaned detection events (data integrity check)
SELECT de.id, de.test_session_id, de.video_id
FROM detection_events de
LEFT JOIN test_sessions ts ON de.test_session_id = ts.id
LEFT JOIN videos v ON de.video_id = v.id  
WHERE ts.id IS NULL OR v.id IS NULL;

-- Find videos without ground truth (validation check)
SELECT v.id, v.filename, v.status, v.ground_truth_generated
FROM videos v
LEFT JOIN ground_truth_objects gto ON v.id = gto.video_id
WHERE v.ground_truth_generated = true 
  AND gto.id IS NULL;

-- Storage usage analysis
SELECT 
    'detection_screenshots' as file_type,
    COUNT(CASE WHEN screenshot_path IS NOT NULL THEN 1 END) as file_count,
    COUNT(CASE WHEN screenshot_zoom_path IS NOT NULL THEN 1 END) as zoom_file_count
FROM detection_events
UNION ALL  
SELECT 
    'report_snapshots',
    COUNT(*),
    0
FROM report_snapshots
WHERE capture_success = true;

-- ================================
-- INDEXES UTILIZATION VERIFICATION  
-- ================================

-- These queries verify that indexes are being used properly
-- Run with EXPLAIN QUERY PLAN in SQLite to verify index usage

-- Verify video status index usage
EXPLAIN QUERY PLAN
SELECT * FROM videos 
WHERE status = 'validated' AND hil_testing_ready = true;
-- Should use: idx_video_hil_ready

-- Verify ground truth temporal index usage  
EXPLAIN QUERY PLAN
SELECT * FROM ground_truth_objects
WHERE video_id = 'test-uuid' AND timestamp > 10.0;
-- Should use: idx_gt_video_timestamp

-- Verify detection event latency index usage
EXPLAIN QUERY PLAN  
SELECT * FROM detection_events
WHERE test_session_id = 'test-uuid' AND latency_ms > 100;
-- Should use: idx_detection_session_latency