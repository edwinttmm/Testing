# Database Migration Strategy Specifications

**Component:** Zero-Downtime Database Migration  
**Platform:** Video Processing Platform  
**Objective:** Migrate from current schema to enhanced video processing database  

## MIGRATION OVERVIEW

This migration strategy transforms the current basic video processing database into a comprehensive, production-ready system with enhanced status tracking, real-time notifications, error handling, and performance optimization.

## CURRENT STATE ANALYSIS

### 1. Existing Schema Assessment

```sql
-- Current problematic schema structure
CREATE TABLE videos (
    id VARCHAR(36) PRIMARY KEY,
    filename VARCHAR(255),
    file_path VARCHAR(500),
    file_size INTEGER,
    duration FLOAT,
    fps FLOAT,
    resolution VARCHAR(50),
    status VARCHAR(50) DEFAULT "uploaded",           -- TOO SIMPLISTIC
    processing_status VARCHAR(50) DEFAULT "pending", -- INADEQUATE
    ground_truth_generated BOOLEAN DEFAULT FALSE,    -- BINARY ONLY
    project_id VARCHAR(36),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Critical Issues:**
- Binary status tracking insufficient for complex workflows
- No processing pipeline state management
- Missing error tracking and recovery mechanisms
- No real-time notification support
- Performance bottlenecks in queries
- No audit trail or compliance features

### 2. Data Volume Assessment

```sql
-- Analyze current data volume and patterns
SELECT 
    COUNT(*) as total_videos,
    COUNT(CASE WHEN status = 'uploaded' THEN 1 END) as uploaded_count,
    COUNT(CASE WHEN ground_truth_generated = TRUE THEN 1 END) as processed_count,
    AVG(file_size) as avg_file_size,
    MAX(created_at) as latest_upload,
    MIN(created_at) as earliest_upload
FROM videos;

-- Analyze processing patterns
SELECT 
    DATE(created_at) as upload_date,
    COUNT(*) as daily_uploads,
    AVG(file_size) as avg_size_mb
FROM videos 
WHERE created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY upload_date DESC;
```

## ZERO-DOWNTIME MIGRATION STRATEGY

### Phase 1: Schema Extension (No Service Interruption)

**Duration:** 1-2 hours  
**Impact:** None - Additive changes only  
**Rollback:** Immediate  

```sql
-- Phase 1.1: Add new columns to existing tables
ALTER TABLE videos 
ADD COLUMN workflow_state ENUM(
    'initializing', 'uploading', 'uploaded', 'validating', 
    'processing', 'completed', 'failed', 'archived'
) DEFAULT 'uploaded' AFTER status,

ADD COLUMN ml_model_version VARCHAR(50) AFTER workflow_state,
ADD COLUMN inference_config JSON AFTER ml_model_version,
ADD COLUMN processing_node_id VARCHAR(36) AFTER inference_config,

-- Quality and validation
ADD COLUMN video_quality_score DECIMAL(3,2) DEFAULT 0.75 AFTER processing_node_id,
ADD COLUMN frame_quality_analysis JSON AFTER video_quality_score,
ADD COLUMN audio_quality_score DECIMAL(3,2) AFTER frame_quality_analysis,

-- Enhanced file management
ADD COLUMN original_filename VARCHAR(500) AFTER audio_quality_score,
ADD COLUMN file_hash VARCHAR(128) AFTER original_filename,
ADD COLUMN file_mime_type VARCHAR(100) AFTER file_hash,
ADD COLUMN storage_location VARCHAR(500) AFTER file_mime_type,
ADD COLUMN backup_location VARCHAR(500) AFTER storage_location,

-- Processing metrics
ADD COLUMN total_processing_time_seconds INTEGER AFTER backup_location,
ADD COLUMN frames_per_second_processed DECIMAL(8,4) AFTER total_processing_time_seconds,
ADD COLUMN objects_detected_count INTEGER DEFAULT 0 AFTER frames_per_second_processed,
ADD COLUMN annotations_count INTEGER DEFAULT 0 AFTER objects_detected_count,

-- Business logic
ADD COLUMN expiry_date TIMESTAMP AFTER annotations_count,
ADD COLUMN retention_policy VARCHAR(100) AFTER expiry_date,
ADD COLUMN compliance_tags JSON AFTER retention_policy;

-- Phase 1.2: Create new supporting tables
CREATE TABLE video_processing_status (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) NOT NULL,
    
    -- Processing Pipeline States
    upload_status ENUM('pending', 'uploading', 'completed', 'failed') DEFAULT 'completed',
    validation_status ENUM('pending', 'validating', 'completed', 'failed') DEFAULT 'pending',
    extraction_status ENUM('pending', 'extracting', 'completed', 'failed') DEFAULT 'pending',
    inference_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    ground_truth_status ENUM('pending', 'generating', 'completed', 'failed') DEFAULT 'pending',
    
    -- Processing Metadata
    current_stage VARCHAR(50) DEFAULT 'validation',
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    total_frames INTEGER,
    processed_frames INTEGER DEFAULT 0,
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,
    
    -- Error Tracking
    error_count INTEGER DEFAULT 0,
    last_error_message TEXT,
    last_error_timestamp TIMESTAMP,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Resource Allocation
    assigned_worker_id VARCHAR(36),
    processing_priority INTEGER DEFAULT 5,
    estimated_completion_time TIMESTAMP,
    
    -- Performance Metrics
    processing_duration_seconds INTEGER,
    memory_usage_mb INTEGER,
    cpu_usage_percentage DECIMAL(5,2),
    
    -- Audit Fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Foreign Key (added after table creation to avoid lock)
    INDEX idx_video_processing_status_video_id (video_id),
    INDEX idx_video_processing_status_current_stage (current_stage),
    INDEX idx_video_processing_status_processing_started (processing_started_at)
);

-- Add foreign key constraint separately to minimize lock time
ALTER TABLE video_processing_status 
ADD CONSTRAINT fk_video_processing_status_video 
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE;

-- Create notification queue table
CREATE TABLE realtime_notification_queue (
    id VARCHAR(36) PRIMARY KEY,
    
    -- Event Classification
    event_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5,
    
    -- Target Specification
    session_id VARCHAR(255),
    user_id VARCHAR(36),
    room_name VARCHAR(255),
    broadcast_to_all BOOLEAN DEFAULT FALSE,
    
    -- Event Content
    event_data JSON NOT NULL,
    event_metadata JSON,
    
    -- Processing State
    status ENUM('pending', 'processing', 'sent', 'failed', 'expired') DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    
    -- Timing Control
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    process_after TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    sent_at TIMESTAMP,
    
    -- Error Handling
    last_error TEXT,
    next_retry_at TIMESTAMP,
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Performance Indexes
    INDEX idx_notification_processing (status, priority, process_after),
    INDEX idx_notification_session (session_id, status),
    INDEX idx_notification_expiry (expires_at, status)
);

-- Create error logging table
CREATE TABLE processing_error_log (
    id VARCHAR(36) PRIMARY KEY,
    
    -- Error Context
    video_id VARCHAR(36),
    processing_stage VARCHAR(50) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    
    -- Error Details
    error_message TEXT NOT NULL,
    error_code VARCHAR(50),
    stack_trace TEXT,
    system_state JSON,
    
    -- Recovery Information
    recovery_strategy VARCHAR(100),
    recovery_attempted BOOLEAN DEFAULT FALSE,
    recovery_successful BOOLEAN,
    recovery_timestamp TIMESTAMP,
    
    -- Correlation
    correlation_id VARCHAR(36),
    parent_error_id VARCHAR(36),
    
    -- Severity and Impact
    severity ENUM('low', 'medium', 'high', 'critical') DEFAULT 'medium',
    user_impact ENUM('none', 'low', 'medium', 'high') DEFAULT 'low',
    
    -- Audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_error_video_stage (video_id, processing_stage),
    INDEX idx_error_type_severity (error_type, severity),
    INDEX idx_error_created (created_at),
    
    -- Foreign Key
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_error_id) REFERENCES processing_error_log(id) ON DELETE SET NULL
);
```

### Phase 2: Data Migration (Background Process)

**Duration:** 2-4 hours  
**Impact:** Minimal - Background processing  
**Rollback:** Data restoration from backup  

```sql
-- Phase 2.1: Populate processing status for existing videos
INSERT INTO video_processing_status (
    id, video_id, upload_status, ground_truth_status, current_stage, 
    created_at, updated_at
)
SELECT 
    UUID() as id,
    v.id as video_id,
    'completed' as upload_status,
    CASE 
        WHEN v.ground_truth_generated = TRUE THEN 'completed'
        WHEN v.processing_status = 'pending' THEN 'pending'
        WHEN v.processing_status = 'processing' THEN 'generating'
        ELSE 'failed'
    END as ground_truth_status,
    CASE 
        WHEN v.ground_truth_generated = TRUE THEN 'completed'
        WHEN v.processing_status = 'processing' THEN 'ground_truth'
        ELSE 'validation'
    END as current_stage,
    v.created_at,
    v.updated_at
FROM videos v
WHERE NOT EXISTS (
    SELECT 1 FROM video_processing_status vps WHERE vps.video_id = v.id
);

-- Phase 2.2: Update workflow states based on current status
UPDATE videos v
JOIN video_processing_status vps ON v.id = vps.video_id
SET v.workflow_state = CASE 
    WHEN vps.ground_truth_status = 'completed' THEN 'completed'
    WHEN vps.ground_truth_status = 'generating' THEN 'processing'
    WHEN vps.ground_truth_status = 'failed' THEN 'failed'
    WHEN v.status = 'uploaded' THEN 'uploaded'
    ELSE 'uploaded'
END;

-- Phase 2.3: Populate enhanced metadata
UPDATE videos 
SET 
    original_filename = filename,
    file_mime_type = CASE 
        WHEN filename LIKE '%.mp4' THEN 'video/mp4'
        WHEN filename LIKE '%.avi' THEN 'video/avi'
        WHEN filename LIKE '%.mov' THEN 'video/quicktime'
        WHEN filename LIKE '%.mkv' THEN 'video/x-matroska'
        ELSE 'video/unknown'
    END,
    storage_location = file_path,
    retention_policy = 'standard_90_days'
WHERE original_filename IS NULL;

-- Phase 2.4: Calculate file hashes for existing videos (background job)
-- This will be done by a background service to avoid blocking
```

**Background Hash Calculation Service:**

```python
import hashlib
import asyncio
from sqlalchemy.orm import Session
from database import SessionLocal
import logging

logger = logging.getLogger(__name__)

class VideoHashCalculator:
    def __init__(self, batch_size=10, delay_between_batches=5):
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
    
    async def process_videos_without_hashes(self):
        """Process videos that don't have file hashes calculated"""
        db = SessionLocal()
        try:
            # Get videos without hashes
            videos_without_hashes = db.execute("""
                SELECT id, file_path, filename 
                FROM videos 
                WHERE file_hash IS NULL 
                AND file_path IS NOT NULL
                LIMIT %s
            """, (self.batch_size,)).fetchall()
            
            for video in videos_without_hashes:
                try:
                    file_hash = await self._calculate_file_hash(video.file_path)
                    if file_hash:
                        db.execute("""
                            UPDATE videos 
                            SET file_hash = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (file_hash, video.id))
                        
                        logger.info(f"Calculated hash for video {video.id}: {file_hash}")
                    
                except Exception as e:
                    logger.error(f"Failed to calculate hash for video {video.id}: {e}")
                
                # Small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)
            
            db.commit()
            
            # Return True if there are more videos to process
            return len(videos_without_hashes) == self.batch_size
            
        finally:
            db.close()
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None
    
    async def run_background_processing(self):
        """Run the background hash calculation process"""
        logger.info("Starting background video hash calculation")
        
        while True:
            try:
                has_more = await self.process_videos_without_hashes()
                
                if not has_more:
                    logger.info("All videos processed, waiting for new uploads")
                    await asyncio.sleep(60)  # Check for new uploads every minute
                else:
                    await asyncio.sleep(self.delay_between_batches)
                    
            except Exception as e:
                logger.error(f"Background processing error: {e}")
                await asyncio.sleep(30)  # Back off on error
```

### Phase 3: Application Update (Rolling Deployment)

**Duration:** 1-2 hours  
**Impact:** Gradual rollout with feature flags  
**Rollback:** Feature flag toggle  

```python
# Feature flag implementation
import os
from typing import Optional

class FeatureFlags:
    def __init__(self):
        self.flags = {
            'enhanced_video_processing': os.getenv('ENABLE_ENHANCED_PROCESSING', 'false').lower() == 'true',
            'realtime_notifications': os.getenv('ENABLE_REALTIME_NOTIFICATIONS', 'false').lower() == 'true',
            'advanced_error_handling': os.getenv('ENABLE_ADVANCED_ERROR_HANDLING', 'false').lower() == 'true',
            'performance_monitoring': os.getenv('ENABLE_PERFORMANCE_MONITORING', 'true').lower() == 'true'
        }
    
    def is_enabled(self, flag_name: str) -> bool:
        return self.flags.get(flag_name, False)
    
    def enable_flag(self, flag_name: str):
        self.flags[flag_name] = True
    
    def disable_flag(self, flag_name: str):
        self.flags[flag_name] = False

feature_flags = FeatureFlags()

# Updated video processing service with feature flags
class VideoProcessingService:
    def __init__(self):
        self.feature_flags = feature_flags
    
    async def get_video_status(self, video_id: str, db: Session):
        """Get video status with enhanced processing if enabled"""
        if self.feature_flags.is_enabled('enhanced_video_processing'):
            return await self._get_enhanced_video_status(video_id, db)
        else:
            return await self._get_legacy_video_status(video_id, db)
    
    async def _get_enhanced_video_status(self, video_id: str, db: Session):
        """Enhanced video status with full pipeline information"""
        result = db.execute("""
            SELECT 
                v.id, v.filename, v.workflow_state, v.updated_at,
                vps.current_stage, vps.progress_percentage,
                vps.processed_frames, vps.total_frames,
                vps.error_count, vps.last_error_message,
                vps.estimated_completion_time
            FROM videos v
            LEFT JOIN video_processing_status vps ON v.id = vps.video_id
            WHERE v.id = %s
        """, (video_id,)).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {
            "id": result.id,
            "filename": result.filename,
            "workflow_state": result.workflow_state,
            "current_stage": result.current_stage,
            "progress_percentage": float(result.progress_percentage or 0),
            "processed_frames": result.processed_frames or 0,
            "total_frames": result.total_frames or 0,
            "error_count": result.error_count or 0,
            "last_error": result.last_error_message,
            "estimated_completion": result.estimated_completion_time.isoformat() if result.estimated_completion_time else None,
            "updated_at": result.updated_at.isoformat() if result.updated_at else None,
            "enhanced_processing": True
        }
    
    async def _get_legacy_video_status(self, video_id: str, db: Session):
        """Legacy video status for backwards compatibility"""
        result = db.execute("""
            SELECT id, filename, status, processing_status, 
                   ground_truth_generated, updated_at
            FROM videos 
            WHERE id = %s
        """, (video_id,)).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {
            "id": result.id,
            "filename": result.filename,
            "status": result.status,
            "processing_status": result.processing_status,
            "ground_truth_generated": result.ground_truth_generated,
            "updated_at": result.updated_at.isoformat() if result.updated_at else None,
            "enhanced_processing": False
        }
```

### Phase 4: Index Creation and Optimization

**Duration:** 30 minutes - 1 hour  
**Impact:** Temporary performance impact during index creation  
**Rollback:** Drop indexes  

```sql
-- Phase 4.1: Create performance indexes (during low traffic)
-- Use ALGORITHM=INPLACE where possible to minimize downtime

-- Video table indexes
CREATE INDEX idx_video_workflow_state ON videos (workflow_state) ALGORITHM=INPLACE;
CREATE INDEX idx_video_processing_node ON videos (processing_node_id) ALGORITHM=INPLACE;
CREATE INDEX idx_video_quality ON videos (video_quality_score) ALGORITHM=INPLACE;
CREATE INDEX idx_video_hash ON videos (file_hash) ALGORITHM=INPLACE;
CREATE INDEX idx_video_expiry ON videos (expiry_date) ALGORITHM=INPLACE;
CREATE INDEX idx_video_objects_count ON videos (objects_detected_count) ALGORITHM=INPLACE;

-- Composite indexes for common queries
CREATE INDEX idx_video_workflow_updated ON videos (workflow_state, updated_at) ALGORITHM=INPLACE;
CREATE INDEX idx_video_project_workflow ON videos (project_id, workflow_state) ALGORITHM=INPLACE;

-- Processing status indexes
CREATE INDEX idx_processing_progress ON video_processing_status (video_id, progress_percentage) ALGORITHM=INPLACE;
CREATE INDEX idx_processing_errors ON video_processing_status (error_count, last_error_timestamp) ALGORITHM=INPLACE;
CREATE INDEX idx_processing_retry ON video_processing_status (retry_count, max_retries) ALGORITHM=INPLACE;

-- Notification queue indexes
CREATE INDEX idx_notification_retry ON realtime_notification_queue (next_retry_at, status) ALGORITHM=INPLACE;
CREATE INDEX idx_notification_event_type ON realtime_notification_queue (event_type, created_at) ALGORITHM=INPLACE;

-- Error log indexes
CREATE INDEX idx_error_correlation ON processing_error_log (correlation_id) ALGORITHM=INPLACE;
CREATE INDEX idx_error_recovery ON processing_error_log (recovery_strategy, recovery_attempted) ALGORITHM=INPLACE;

-- Phase 4.2: Create materialized views for dashboard performance
CREATE VIEW v_processing_dashboard_stats AS
SELECT 
    COUNT(CASE WHEN workflow_state = 'uploading' THEN 1 END) as uploading_count,
    COUNT(CASE WHEN workflow_state = 'processing' THEN 1 END) as processing_count,
    COUNT(CASE WHEN workflow_state = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN workflow_state = 'failed' THEN 1 END) as failed_count,
    AVG(CASE WHEN total_processing_time_seconds > 0 THEN total_processing_time_seconds END) as avg_processing_time,
    SUM(objects_detected_count) as total_objects_detected,
    COUNT(*) as total_videos,
    MAX(updated_at) as last_updated
FROM videos v
WHERE v.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR);
```

### Phase 5: Database Triggers and Automation

**Duration:** 30 minutes  
**Impact:** None - Enhancement only  
**Rollback:** Drop triggers  

```sql
-- Phase 5.1: Create synchronization triggers
DELIMITER $$

CREATE TRIGGER tr_video_workflow_sync
    AFTER UPDATE ON videos
    FOR EACH ROW
BEGIN
    -- Sync workflow state changes to processing status
    IF NEW.workflow_state != OLD.workflow_state THEN
        UPDATE video_processing_status 
        SET 
            current_stage = CASE NEW.workflow_state
                WHEN 'processing' THEN 'inference'
                WHEN 'completed' THEN 'completed'
                WHEN 'failed' THEN 'failed'
                ELSE current_stage
            END,
            updated_at = NOW()
        WHERE video_id = NEW.id;
        
        -- Queue real-time notification if enabled
        IF @enable_realtime_notifications = 1 THEN
            INSERT INTO realtime_notification_queue (
                id, event_type, priority, room_name, event_data, expires_at
            ) VALUES (
                UUID(),
                CONCAT('workflow_', NEW.workflow_state),
                CASE NEW.workflow_state
                    WHEN 'failed' THEN 1
                    WHEN 'completed' THEN 2
                    ELSE 3
                END,
                CONCAT('video_', NEW.id),
                JSON_OBJECT(
                    'video_id', NEW.id,
                    'old_state', OLD.workflow_state,
                    'new_state', NEW.workflow_state,
                    'timestamp', NOW()
                ),
                DATE_ADD(NOW(), INTERVAL 1 HOUR)
            );
        END IF;
    END IF;
END$$

CREATE TRIGGER tr_processing_status_progress_notification
    AFTER UPDATE ON video_processing_status
    FOR EACH ROW
BEGIN
    -- Queue progress notifications for significant changes
    IF @enable_realtime_notifications = 1 AND (
        (NEW.progress_percentage - OLD.progress_percentage >= 5.0) OR
        (NEW.current_stage != OLD.current_stage) OR
        (NEW.error_count > OLD.error_count)
    ) THEN
        INSERT INTO realtime_notification_queue (
            id, event_type, priority, room_name, event_data, expires_at
        ) VALUES (
            UUID(),
            CASE 
                WHEN NEW.error_count > OLD.error_count THEN 'processing_error'
                WHEN NEW.current_stage != OLD.current_stage THEN 'stage_changed'
                ELSE 'progress_update'
            END,
            CASE 
                WHEN NEW.error_count > OLD.error_count THEN 1
                WHEN NEW.progress_percentage = 100 THEN 2
                ELSE 4
            END,
            CONCAT('video_', NEW.video_id),
            JSON_OBJECT(
                'video_id', NEW.video_id,
                'stage', NEW.current_stage,
                'progress', NEW.progress_percentage,
                'error_count', NEW.error_count,
                'timestamp', NOW()
            ),
            DATE_ADD(NOW(), INTERVAL 30 MINUTE)
        );
    END IF;
END$$

DELIMITER ;
```

## ROLLBACK STRATEGY

### 1. Immediate Rollback (Phase 1-2)

```sql
-- Emergency rollback procedure
DELIMITER $$

CREATE PROCEDURE sp_emergency_rollback()
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;
    
    START TRANSACTION;
    
    -- Disable triggers
    SET @enable_realtime_notifications = 0;
    
    -- Drop new triggers
    DROP TRIGGER IF EXISTS tr_video_workflow_sync;
    DROP TRIGGER IF EXISTS tr_processing_status_progress_notification;
    
    -- Drop new tables (will cascade to foreign key references)
    DROP TABLE IF EXISTS processing_error_log;
    DROP TABLE IF EXISTS realtime_notification_queue;
    DROP TABLE IF EXISTS video_processing_status;
    
    -- Remove new columns from videos table
    ALTER TABLE videos 
    DROP COLUMN IF EXISTS workflow_state,
    DROP COLUMN IF EXISTS ml_model_version,
    DROP COLUMN IF EXISTS inference_config,
    DROP COLUMN IF EXISTS processing_node_id,
    DROP COLUMN IF EXISTS video_quality_score,
    DROP COLUMN IF EXISTS frame_quality_analysis,
    DROP COLUMN IF EXISTS audio_quality_score,
    DROP COLUMN IF EXISTS original_filename,
    DROP COLUMN IF EXISTS file_hash,
    DROP COLUMN IF EXISTS file_mime_type,
    DROP COLUMN IF EXISTS storage_location,
    DROP COLUMN IF EXISTS backup_location,
    DROP COLUMN IF EXISTS total_processing_time_seconds,
    DROP COLUMN IF EXISTS frames_per_second_processed,
    DROP COLUMN IF EXISTS objects_detected_count,
    DROP COLUMN IF EXISTS annotations_count,
    DROP COLUMN IF EXISTS expiry_date,
    DROP COLUMN IF EXISTS retention_policy,
    DROP COLUMN IF EXISTS compliance_tags;
    
    COMMIT;
    
    SELECT 'Emergency rollback completed successfully' as status;
END$$

DELIMITER ;
```

### 2. Application Rollback

```python
# Emergency feature flag disable
def emergency_disable_enhanced_features():
    """Disable all enhanced features immediately"""
    feature_flags.disable_flag('enhanced_video_processing')
    feature_flags.disable_flag('realtime_notifications')
    feature_flags.disable_flag('advanced_error_handling')
    
    # Update environment variables for persistence
    os.environ['ENABLE_ENHANCED_PROCESSING'] = 'false'
    os.environ['ENABLE_REALTIME_NOTIFICATIONS'] = 'false'
    os.environ['ENABLE_ADVANCED_ERROR_HANDLING'] = 'false'
    
    logger.warning("Enhanced features disabled via emergency rollback")
```

## VALIDATION AND TESTING

### 1. Migration Validation Queries

```sql
-- Validate data integrity after migration
SELECT 
    'Data Integrity Check' as check_type,
    COUNT(*) as total_videos,
    COUNT(CASE WHEN workflow_state IS NOT NULL THEN 1 END) as videos_with_workflow_state,
    COUNT(vps.id) as videos_with_processing_status
FROM videos v
LEFT JOIN video_processing_status vps ON v.id = vps.video_id;

-- Validate foreign key relationships
SELECT 
    'Foreign Key Validation' as check_type,
    COUNT(*) as processing_status_records,
    COUNT(v.id) as valid_video_references
FROM video_processing_status vps
LEFT JOIN videos v ON vps.video_id = v.id;

-- Validate enum values
SELECT 
    workflow_state,
    COUNT(*) as count
FROM videos 
WHERE workflow_state IS NOT NULL
GROUP BY workflow_state;
```

### 2. Performance Validation

```sql
-- Test query performance with new indexes
EXPLAIN SELECT v.*, vps.current_stage, vps.progress_percentage
FROM videos v
LEFT JOIN video_processing_status vps ON v.id = vps.video_id
WHERE v.workflow_state = 'processing'
ORDER BY v.updated_at DESC
LIMIT 20;

-- Validate notification queue performance
EXPLAIN SELECT *
FROM realtime_notification_queue
WHERE status = 'pending'
AND process_after <= NOW()
ORDER BY priority ASC, created_at ASC
LIMIT 100;
```

### 3. Application Integration Testing

```python
import pytest
import asyncio
from unittest.mock import patch
from sqlalchemy.orm import Session

@pytest.mark.asyncio
async def test_enhanced_video_processing_migration():
    """Test that enhanced video processing works correctly after migration"""
    # Test video status retrieval with new schema
    video_service = VideoProcessingService()
    
    # Test with enhanced processing enabled
    with patch.object(feature_flags, 'is_enabled', return_value=True):
        status = await video_service.get_video_status('test-video-id', db_session)
        assert 'enhanced_processing' in status
        assert status['enhanced_processing'] is True
        assert 'current_stage' in status
        assert 'progress_percentage' in status
    
    # Test fallback to legacy processing
    with patch.object(feature_flags, 'is_enabled', return_value=False):
        status = await video_service.get_video_status('test-video-id', db_session)
        assert status['enhanced_processing'] is False

@pytest.mark.asyncio
async def test_notification_system_integration():
    """Test that notification system works after migration"""
    # Simulate video status update
    db_session.execute("""
        UPDATE videos 
        SET workflow_state = 'processing' 
        WHERE id = 'test-video-id'
    """)
    db_session.commit()
    
    # Check that notification was queued
    notifications = db_session.execute("""
        SELECT * FROM realtime_notification_queue 
        WHERE JSON_EXTRACT(event_data, '$.video_id') = 'test-video-id'
    """).fetchall()
    
    assert len(notifications) > 0
    assert notifications[0].event_type == 'workflow_processing'

def test_data_migration_integrity():
    """Test that all existing data was migrated correctly"""
    # Check that all videos have processing status records
    orphaned_videos = db_session.execute("""
        SELECT v.id FROM videos v
        LEFT JOIN video_processing_status vps ON v.id = vps.video_id
        WHERE vps.id IS NULL
    """).fetchall()
    
    assert len(orphaned_videos) == 0, "Some videos missing processing status records"
    
    # Check workflow state consistency
    inconsistent_states = db_session.execute("""
        SELECT v.id FROM videos v
        JOIN video_processing_status vps ON v.id = vps.video_id
        WHERE (v.workflow_state = 'completed' AND vps.ground_truth_status != 'completed')
        OR (v.workflow_state = 'failed' AND vps.ground_truth_status NOT IN ('failed', 'pending'))
    """).fetchall()
    
    assert len(inconsistent_states) == 0, "Workflow state inconsistencies found"
```

## MONITORING AND ALERTING DURING MIGRATION

### 1. Migration Progress Monitoring

```sql
-- Monitor migration progress
SELECT 
    'Migration Progress' as metric,
    COUNT(*) as total_videos,
    COUNT(CASE WHEN workflow_state IS NOT NULL THEN 1 END) as migrated_videos,
    ROUND(COUNT(CASE WHEN workflow_state IS NOT NULL THEN 1 END) / COUNT(*) * 100, 2) as completion_percentage
FROM videos;

-- Monitor system performance during migration
SELECT 
    'System Performance' as metric,
    COUNT(*) as active_connections,
    AVG(time) as avg_query_time,
    MAX(time) as max_query_time
FROM information_schema.processlist
WHERE command != 'Sleep';
```

### 2. Error Monitoring

```python
import logging
import time
from typing import Dict, Any

class MigrationMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'videos_migrated': 0,
            'errors_encountered': 0,
            'processing_status_created': 0,
            'notifications_queued': 0
        }
        
        self.logger = logging.getLogger(__name__)
    
    def log_migration_step(self, step: str, success: bool, details: Dict[str, Any] = None):
        """Log migration step completion"""
        elapsed_time = time.time() - self.start_time
        
        log_data = {
            'step': step,
            'success': success,
            'elapsed_time': elapsed_time,
            'details': details or {}
        }
        
        if success:
            self.logger.info(f"Migration step completed: {step}", extra=log_data)
        else:
            self.logger.error(f"Migration step failed: {step}", extra=log_data)
            self.metrics['errors_encountered'] += 1
    
    def update_metric(self, metric_name: str, increment: int = 1):
        """Update migration metrics"""
        if metric_name in self.metrics:
            self.metrics[metric_name] += increment
    
    def get_progress_report(self) -> Dict[str, Any]:
        """Generate progress report"""
        elapsed_time = time.time() - self.start_time
        
        return {
            'elapsed_time_seconds': elapsed_time,
            'metrics': self.metrics,
            'estimated_completion': self._estimate_completion(),
            'error_rate': self.metrics['errors_encountered'] / max(self.metrics['videos_migrated'], 1)
        }
    
    def _estimate_completion(self) -> str:
        """Estimate completion time based on current progress"""
        # Implementation would depend on specific migration metrics
        return "Estimating..."
```

This comprehensive migration strategy ensures zero-downtime transformation of the video processing platform's database while maintaining data integrity, providing rollback capabilities, and enabling gradual feature rollout through feature flags.