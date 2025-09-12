# Database Schema Architecture - Enhanced Design

## Overview

This document defines the enhanced database schema architecture for the AI Model Validation Platform, incorporating annotation management, ground truth validation, and comprehensive validation logging systems.

## 1. ENHANCED ENTITY RELATIONSHIP MODEL

### 1.1 Core Entity Extensions

```sql
-- Enhanced Projects Table with Validation Criteria
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    camera_model VARCHAR(100) NOT NULL,
    camera_view VARCHAR(50) NOT NULL CHECK (camera_view IN ('Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior')),
    lens_type VARCHAR(50),
    resolution VARCHAR(20),
    frame_rate INTEGER,
    signal_type VARCHAR(30) NOT NULL CHECK (signal_type IN ('GPIO', 'Network Packet', 'Serial', 'CAN Bus')),
    status VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Draft', 'Active', 'Testing', 'Analysis', 'Completed', 'Archived')),
    owner_id UUID DEFAULT 'anonymous'::uuid,
    
    -- Validation Criteria Fields
    min_precision DECIMAL(5,4) DEFAULT 0.90,
    min_recall DECIMAL(5,4) DEFAULT 0.85,
    min_f1_score DECIMAL(5,4) DEFAULT 0.87,
    max_latency_ms INTEGER DEFAULT 100,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    INDEX idx_projects_name (name),
    INDEX idx_projects_status (status),
    INDEX idx_projects_owner (owner_id),
    INDEX idx_projects_created (created_at),
    INDEX idx_projects_camera_view (camera_view),
    INDEX idx_projects_signal_type (signal_type)
);

-- Enhanced Videos Table with Processing Metadata
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_path TEXT NOT NULL,
    file_size BIGINT,
    duration DECIMAL(10,3),  -- Seconds with millisecond precision
    fps DECIMAL(6,3),
    resolution VARCHAR(20),
    codec VARCHAR(20),
    bitrate INTEGER,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'ready', 'error', 'deleted')),
    processing_status VARCHAR(20) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'extracting', 'analyzing', 'completed', 'failed')),
    ground_truth_generated BOOLEAN DEFAULT FALSE,
    
    -- Processing metadata
    total_frames INTEGER,
    extracted_frames INTEGER,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    processing_error TEXT,
    
    -- Quality metrics
    quality_score DECIMAL(3,2), -- 0.00 to 1.00
    noise_level DECIMAL(3,2),
    brightness_avg DECIMAL(5,2),
    contrast_ratio DECIMAL(5,2),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Comprehensive indexing
    INDEX idx_videos_project (project_id),
    INDEX idx_videos_filename (filename),
    INDEX idx_videos_status (status),
    INDEX idx_videos_processing_status (processing_status),
    INDEX idx_videos_ground_truth (ground_truth_generated),
    INDEX idx_videos_created (created_at),
    INDEX idx_videos_project_status (project_id, status),
    INDEX idx_videos_project_created (project_id, created_at),
    INDEX idx_videos_duration_fps (duration, fps),
    INDEX idx_videos_quality_score (quality_score),
    UNIQUE INDEX idx_videos_project_filename (project_id, filename)
);
```

### 1.2 Enhanced Annotation System

```sql
-- Enhanced Annotations Table with Advanced Features
CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    detection_id VARCHAR(50), -- DET_PED_0001, DET_CYC_0002, etc.
    
    -- Temporal information
    frame_number INTEGER NOT NULL,
    timestamp DECIMAL(10,3) NOT NULL, -- Video timestamp in seconds
    end_timestamp DECIMAL(10,3), -- For temporal annotations (tracking)
    
    -- Object classification
    vru_type VARCHAR(20) NOT NULL CHECK (vru_type IN ('pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter', 'other')),
    subclass VARCHAR(30), -- child, adult, group, etc.
    
    -- Spatial information
    bounding_box JSONB NOT NULL, -- {"x": 0, "y": 0, "width": 100, "height": 100, "normalized": true}
    polygon JSONB, -- For complex shapes: {"points": [[x1,y1], [x2,y2], ...]}
    keypoints JSONB, -- For pose estimation: {"head": [x,y], "torso": [x,y], ...}
    
    -- Annotation quality indicators
    occluded BOOLEAN DEFAULT FALSE,
    truncated BOOLEAN DEFAULT FALSE,
    difficult BOOLEAN DEFAULT FALSE,
    uncertain BOOLEAN DEFAULT FALSE,
    
    -- Validation and review
    validated BOOLEAN DEFAULT FALSE,
    validation_confidence DECIMAL(3,2), -- Validator confidence 0.00-1.00
    review_status VARCHAR(20) DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected', 'needs_review')),
    
    -- Attribution
    annotator_id UUID,
    validator_id UUID,
    notes TEXT,
    
    -- Tracking information
    track_id UUID, -- For multi-frame tracking
    track_confidence DECIMAL(3,2),
    
    -- Metadata
    annotation_tool VARCHAR(50) DEFAULT 'manual',
    annotation_version INTEGER DEFAULT 1,
    source_detection_id UUID, -- Reference to original detection if pre-annotated
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMPTZ,
    
    -- Comprehensive indexing for performance
    INDEX idx_annotations_video (video_id),
    INDEX idx_annotations_video_frame (video_id, frame_number),
    INDEX idx_annotations_video_timestamp (video_id, timestamp),
    INDEX idx_annotations_detection_id (detection_id),
    INDEX idx_annotations_vru_type (vru_type),
    INDEX idx_annotations_validated (validated),
    INDEX idx_annotations_review_status (review_status),
    INDEX idx_annotations_annotator (annotator_id),
    INDEX idx_annotations_validator (validator_id),
    INDEX idx_annotations_track (track_id),
    INDEX idx_annotations_created (created_at),
    INDEX idx_annotations_video_vru_frame (video_id, vru_type, frame_number),
    INDEX idx_annotations_video_validated_timestamp (video_id, validated, timestamp),
    INDEX idx_annotations_temporal_range (timestamp, end_timestamp),
    INDEX idx_annotations_difficulty (difficult, occluded, truncated),
    UNIQUE INDEX idx_annotations_video_frame_detection (video_id, frame_number, detection_id)
);

-- Annotation Sessions for Collaborative Work
CREATE TABLE annotation_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    annotator_id UUID,
    
    -- Session information
    session_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'abandoned')),
    
    -- Progress tracking
    total_frames INTEGER,
    annotated_frames INTEGER DEFAULT 0,
    current_frame INTEGER DEFAULT 0,
    total_detections INTEGER DEFAULT 0,
    validated_detections INTEGER DEFAULT 0,
    
    -- Time tracking
    time_spent_seconds INTEGER DEFAULT 0,
    estimated_completion_time INTEGER,
    
    -- Quality metrics
    average_annotation_time DECIMAL(6,2), -- Seconds per annotation
    consistency_score DECIMAL(3,2), -- Internal consistency
    
    -- Session metadata
    annotation_guidelines TEXT,
    session_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_annotation_sessions_video (video_id),
    INDEX idx_annotation_sessions_project (project_id),
    INDEX idx_annotation_sessions_annotator (annotator_id),
    INDEX idx_annotation_sessions_status (status),
    INDEX idx_annotation_sessions_created (created_at)
);
```

### 1.3 Enhanced Ground Truth System

```sql
-- Enhanced Ground Truth Objects with Metadata
CREATE TABLE ground_truth_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    
    -- Temporal positioning
    frame_number INTEGER,
    timestamp DECIMAL(10,3) NOT NULL,
    end_timestamp DECIMAL(10,3), -- For temporal ground truth
    
    -- Classification
    class_label VARCHAR(30) NOT NULL,
    subclass VARCHAR(50),
    attributes JSONB, -- {"color": "red", "size": "large", "activity": "walking"}
    
    -- Spatial information (normalized coordinates 0-1)
    x DECIMAL(8,6) NOT NULL, -- Normalized x coordinate
    y DECIMAL(8,6) NOT NULL, -- Normalized y coordinate
    width DECIMAL(8,6) NOT NULL, -- Normalized width
    height DECIMAL(8,6) NOT NULL, -- Normalized height
    
    -- Legacy support
    bounding_box JSONB, -- Deprecated field for backward compatibility
    
    -- Quality and validation
    confidence DECIMAL(5,4), -- 0.0000 to 1.0000
    validated BOOLEAN DEFAULT FALSE,
    validation_method VARCHAR(30), -- 'manual', 'semi_auto', 'consensus', 'expert'
    validation_confidence DECIMAL(5,4),
    
    -- Difficulty assessment
    difficult BOOLEAN DEFAULT FALSE,
    occluded BOOLEAN DEFAULT FALSE,
    truncated BOOLEAN DEFAULT FALSE,
    
    -- Generation metadata
    generation_method VARCHAR(30) DEFAULT 'manual', -- 'manual', 'ml_generated', 'semi_supervised'
    generation_model VARCHAR(50),
    generation_confidence DECIMAL(5,4),
    
    -- Review information
    reviewed BOOLEAN DEFAULT FALSE,
    reviewer_id UUID,
    review_notes TEXT,
    
    -- Tracking
    track_id UUID, -- For multi-frame tracking
    object_id VARCHAR(50), -- Unique object identifier across frames
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMPTZ,
    reviewed_at TIMESTAMPTZ,
    
    -- Comprehensive performance indexes
    INDEX idx_ground_truth_video (video_id),
    INDEX idx_ground_truth_video_timestamp (video_id, timestamp),
    INDEX idx_ground_truth_video_frame (video_id, frame_number),
    INDEX idx_ground_truth_class (class_label),
    INDEX idx_ground_truth_video_class (video_id, class_label),
    INDEX idx_ground_truth_timestamp_class (timestamp, class_label),
    INDEX idx_ground_truth_confidence (confidence),
    INDEX idx_ground_truth_validated (validated),
    INDEX idx_ground_truth_validated_class (validated, class_label),
    INDEX idx_ground_truth_generation_method (generation_method),
    INDEX idx_ground_truth_track (track_id),
    INDEX idx_ground_truth_object (object_id),
    INDEX idx_ground_truth_spatial (x, y, width, height),
    INDEX idx_ground_truth_video_validated_timestamp (video_id, validated, timestamp),
    INDEX idx_ground_truth_difficulty (difficult, occluded, truncated),
    INDEX idx_ground_truth_temporal_range (timestamp, end_timestamp)
);
```

### 1.4 Enhanced Detection and Validation System

```sql
-- Enhanced Test Sessions with Advanced Configuration
CREATE TABLE test_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    
    -- Configuration
    tolerance_ms INTEGER DEFAULT 100,
    iou_threshold DECIMAL(3,2) DEFAULT 0.50,
    confidence_threshold DECIMAL(3,2) DEFAULT 0.30,
    
    -- ML Model Configuration
    model_name VARCHAR(50),
    model_version VARCHAR(20),
    model_parameters JSONB,
    
    -- Test Parameters
    test_type VARCHAR(30) DEFAULT 'validation' CHECK (test_type IN ('validation', 'benchmark', 'regression', 'acceptance')),
    test_criteria JSONB, -- Custom test criteria
    
    -- Status and Progress
    status VARCHAR(20) DEFAULT 'created' CHECK (status IN ('created', 'configured', 'running', 'completed', 'failed', 'cancelled')),
    progress_percentage INTEGER DEFAULT 0,
    
    -- Results Summary
    total_detections INTEGER DEFAULT 0,
    true_positives INTEGER DEFAULT 0,
    false_positives INTEGER DEFAULT 0,
    false_negatives INTEGER DEFAULT 0,
    precision DECIMAL(6,4),
    recall DECIMAL(6,4),
    f1_score DECIMAL(6,4),
    
    -- Performance Metrics
    average_confidence DECIMAL(5,4),
    processing_time_ms BIGINT,
    fps_processed DECIMAL(8,2),
    
    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_test_sessions_project (project_id),
    INDEX idx_test_sessions_video (video_id),
    INDEX idx_test_sessions_name (name),
    INDEX idx_test_sessions_status (status),
    INDEX idx_test_sessions_created (created_at),
    INDEX idx_test_sessions_project_status (project_id, status),
    INDEX idx_test_sessions_model (model_name, model_version)
);

-- Enhanced Detection Events with Comprehensive Data
CREATE TABLE detection_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    
    -- Temporal Information
    timestamp DECIMAL(10,3) NOT NULL,
    frame_number INTEGER,
    
    -- Detection Classification
    class_label VARCHAR(30),
    confidence DECIMAL(5,4),
    vru_type VARCHAR(20),
    subclass VARCHAR(30),
    
    -- Spatial Information (normalized coordinates)
    bounding_box_x DECIMAL(8,6),
    bounding_box_y DECIMAL(8,6),
    bounding_box_width DECIMAL(8,6),
    bounding_box_height DECIMAL(8,6),
    
    -- Additional Spatial Data
    center_x DECIMAL(8,6), -- Computed center point
    center_y DECIMAL(8,6),
    area DECIMAL(10,8), -- Bounding box area (normalized)
    aspect_ratio DECIMAL(6,3), -- Width/height ratio
    
    -- Validation Results
    validation_result VARCHAR(10) CHECK (validation_result IN ('TP', 'FP', 'FN', 'TN')),
    ground_truth_match_id UUID REFERENCES ground_truth_objects(id) ON DELETE SET NULL,
    iou_score DECIMAL(5,4), -- Intersection over Union with ground truth
    distance_error DECIMAL(8,4), -- Euclidean distance error
    temporal_offset DECIMAL(6,3), -- Time difference from ground truth
    
    -- Detection Metadata
    detection_id VARCHAR(50), -- Unique detection identifier
    model_version VARCHAR(20),
    processing_time_ms INTEGER,
    
    -- Evidence Storage
    screenshot_path TEXT,
    screenshot_zoom_path TEXT,
    feature_vector JSONB, -- ML model feature vector
    
    -- Quality Indicators
    detection_quality DECIMAL(3,2), -- Overall quality score
    edge_distance DECIMAL(6,4), -- Distance from frame edges
    occlusion_level DECIMAL(3,2), -- Estimated occlusion
    motion_blur DECIMAL(3,2), -- Motion blur indicator
    
    -- Tracking Information
    track_id UUID,
    track_confidence DECIMAL(3,2),
    previous_detection_id UUID REFERENCES detection_events(id),
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Comprehensive indexing for analytics
    INDEX idx_detection_events_session (test_session_id),
    INDEX idx_detection_events_session_timestamp (test_session_id, timestamp),
    INDEX idx_detection_events_session_frame (test_session_id, frame_number),
    INDEX idx_detection_events_timestamp (timestamp),
    INDEX idx_detection_events_class (class_label),
    INDEX idx_detection_events_confidence (confidence),
    INDEX idx_detection_events_validation_result (validation_result),
    INDEX idx_detection_events_ground_truth_match (ground_truth_match_id),
    INDEX idx_detection_events_vru_type (vru_type),
    INDEX idx_detection_events_detection_id (detection_id),
    INDEX idx_detection_events_track (track_id),
    INDEX idx_detection_events_model_version (model_version),
    INDEX idx_detection_events_iou_score (iou_score),
    INDEX idx_detection_events_session_validation (test_session_id, validation_result),
    INDEX idx_detection_events_confidence_validation (confidence, validation_result),
    INDEX idx_detection_events_temporal_validation (timestamp, validation_result),
    INDEX idx_detection_events_spatial_center (center_x, center_y),
    INDEX idx_detection_events_bbox_area (area),
    INDEX idx_detection_events_quality_score (detection_quality)
);
```

### 1.5 Advanced Validation and Analytics Tables

```sql
-- Detection Comparisons for Advanced Analytics
CREATE TABLE detection_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    detection_event_id UUID REFERENCES detection_events(id) ON DELETE SET NULL,
    ground_truth_id UUID REFERENCES ground_truth_objects(id) ON DELETE SET NULL,
    
    -- Comparison Type
    match_type VARCHAR(10) NOT NULL CHECK (match_type IN ('TP', 'FP', 'FN', 'TN')),
    match_confidence DECIMAL(5,4),
    
    -- Spatial Comparison
    iou_score DECIMAL(5,4),
    hausdorff_distance DECIMAL(8,4), -- Advanced shape similarity
    centroid_distance DECIMAL(8,4), -- Distance between centers
    
    -- Temporal Comparison
    temporal_offset DECIMAL(6,3), -- Time difference
    temporal_overlap DECIMAL(5,4), -- Temporal overlap ratio
    
    -- Classification Comparison
    class_match BOOLEAN,
    class_confidence_diff DECIMAL(5,4),
    attribute_similarity DECIMAL(3,2), -- Overall attribute similarity
    
    -- Quality Metrics
    comparison_confidence DECIMAL(5,4), -- How confident we are in this comparison
    reviewer_verified BOOLEAN DEFAULT FALSE,
    verification_notes TEXT,
    
    -- Metadata
    comparison_algorithm VARCHAR(30) DEFAULT 'iou_threshold',
    algorithm_parameters JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMPTZ,
    
    INDEX idx_comparisons_session (test_session_id),
    INDEX idx_comparisons_detection (detection_event_id),
    INDEX idx_comparisons_ground_truth (ground_truth_id),
    INDEX idx_comparisons_match_type (match_type),
    INDEX idx_comparisons_iou_score (iou_score),
    INDEX idx_comparisons_temporal_offset (temporal_offset),
    INDEX idx_comparisons_session_match (test_session_id, match_type),
    INDEX idx_comparisons_verified (reviewer_verified)
);

-- Enhanced Test Results with Statistical Analysis
CREATE TABLE test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_session_id UUID NOT NULL REFERENCES test_sessions(id) ON DELETE CASCADE,
    
    -- Basic Metrics
    accuracy DECIMAL(6,4),
    precision DECIMAL(6,4),
    recall DECIMAL(6,4),
    f1_score DECIMAL(6,4),
    
    -- Confusion Matrix
    true_positives INTEGER,
    false_positives INTEGER,
    false_negatives INTEGER,
    true_negatives INTEGER,
    
    -- Advanced Metrics
    specificity DECIMAL(6,4), -- True negative rate
    sensitivity DECIMAL(6,4), -- Same as recall, but explicit
    mcc DECIMAL(6,4), -- Matthews Correlation Coefficient
    auc_roc DECIMAL(6,4), -- Area Under ROC Curve
    auc_pr DECIMAL(6,4), -- Area Under Precision-Recall Curve
    
    -- Class-Specific Metrics
    class_metrics JSONB, -- Per-class precision, recall, f1
    
    -- Statistical Analysis
    confidence_intervals JSONB, -- {"precision": [0.89, 0.95], "recall": [0.82, 0.91]}
    statistical_significance BOOLEAN,
    p_value DECIMAL(8,6),
    confidence_level DECIMAL(3,2) DEFAULT 0.95,
    
    -- Error Analysis
    error_distribution JSONB, -- Error types and frequencies
    failure_modes JSONB, -- Common failure patterns
    edge_cases JSONB, -- Identified edge cases
    
    -- Performance Analysis
    inference_time_stats JSONB, -- {"mean": 45.2, "std": 12.3, "p95": 67.1}
    throughput_fps DECIMAL(8,2),
    resource_utilization JSONB, -- CPU, memory, GPU usage
    
    -- Temporal Analysis
    performance_by_timeframe JSONB, -- Performance across video timeline
    temporal_consistency DECIMAL(4,3), -- Consistency across time
    
    -- Validation Status
    result_validated BOOLEAN DEFAULT FALSE,
    validator_id UUID,
    validation_notes TEXT,
    
    -- Metadata
    analysis_version VARCHAR(20),
    analysis_parameters JSONB,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMPTZ,
    
    INDEX idx_test_results_session (test_session_id),
    INDEX idx_test_results_accuracy (accuracy),
    INDEX idx_test_results_f1_score (f1_score),
    INDEX idx_test_results_validated (result_validated),
    INDEX idx_test_results_created (created_at)
);

-- Model Performance Tracking
CREATE TABLE model_performance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(20) NOT NULL,
    test_session_id UUID REFERENCES test_sessions(id) ON DELETE SET NULL,
    
    -- Performance Metrics
    overall_accuracy DECIMAL(6,4),
    overall_precision DECIMAL(6,4),
    overall_recall DECIMAL(6,4),
    overall_f1_score DECIMAL(6,4),
    
    -- Benchmark Results
    benchmark_dataset VARCHAR(50),
    benchmark_score DECIMAL(6,4),
    benchmark_percentile INTEGER, -- Performance percentile
    
    -- Resource Requirements
    inference_time_ms DECIMAL(8,2),
    memory_usage_mb INTEGER,
    gpu_memory_mb INTEGER,
    
    -- Quality Indicators
    consistency_score DECIMAL(4,3),
    robustness_score DECIMAL(4,3),
    edge_case_performance DECIMAL(4,3),
    
    -- Testing Context
    test_environment VARCHAR(30),
    hardware_spec JSONB,
    software_versions JSONB,
    
    -- Metadata
    notes TEXT,
    deployment_ready BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    tested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_model_performance_model (model_name, model_version),
    INDEX idx_model_performance_session (test_session_id),
    INDEX idx_model_performance_accuracy (overall_accuracy),
    INDEX idx_model_performance_f1 (overall_f1_score),
    INDEX idx_model_performance_tested (tested_at),
    INDEX idx_model_performance_deployment_ready (deployment_ready),
    UNIQUE INDEX idx_model_performance_unique_test (model_name, model_version, test_session_id)
);
```

### 1.6 Audit and Logging Tables

```sql
-- Comprehensive Audit Logging
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- User Information
    user_id UUID,
    username VARCHAR(50),
    user_role VARCHAR(30),
    
    -- Session Information
    session_id UUID,
    ip_address INET,
    user_agent TEXT,
    
    -- Event Information
    event_type VARCHAR(50) NOT NULL, -- 'create', 'read', 'update', 'delete', 'login', 'logout'
    event_category VARCHAR(30) NOT NULL, -- 'auth', 'annotation', 'validation', 'system'
    event_action VARCHAR(100) NOT NULL, -- Specific action performed
    
    -- Resource Information
    resource_type VARCHAR(30), -- 'project', 'video', 'annotation', 'test_session'
    resource_id UUID,
    resource_name VARCHAR(255),
    
    -- Change Details
    old_values JSONB, -- Previous values before change
    new_values JSONB, -- New values after change
    change_summary TEXT, -- Human-readable summary
    
    -- Request Details
    request_method VARCHAR(10),
    request_path TEXT,
    request_body JSONB, -- Sanitized request body
    response_status INTEGER,
    
    -- Security Context
    security_level VARCHAR(20) DEFAULT 'standard', -- 'low', 'standard', 'high', 'critical'
    risk_score INTEGER, -- 0-100 risk assessment
    compliance_flags JSONB, -- Compliance requirements met
    
    -- Error Information
    error_code VARCHAR(20),
    error_message TEXT,
    stack_trace TEXT, -- Only for system errors
    
    -- Timing
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Comprehensive indexing for security analysis
    INDEX idx_audit_logs_user (user_id),
    INDEX idx_audit_logs_session (session_id),
    INDEX idx_audit_logs_ip (ip_address),
    INDEX idx_audit_logs_event_type (event_type),
    INDEX idx_audit_logs_event_category (event_category),
    INDEX idx_audit_logs_resource_type (resource_type),
    INDEX idx_audit_logs_resource_id (resource_id),
    INDEX idx_audit_logs_created (created_at),
    INDEX idx_audit_logs_security_level (security_level),
    INDEX idx_audit_logs_risk_score (risk_score),
    INDEX idx_audit_logs_user_event_time (user_id, event_type, created_at),
    INDEX idx_audit_logs_resource_event_time (resource_type, event_type, created_at),
    INDEX idx_audit_logs_ip_event_time (ip_address, event_type, created_at)
) PARTITION BY RANGE (created_at);

-- Partition audit logs by month for performance
CREATE TABLE audit_logs_2024_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE audit_logs_2024_02 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... continue for each month

-- System Performance Logs
CREATE TABLE performance_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Metric Information
    metric_name VARCHAR(50) NOT NULL,
    metric_category VARCHAR(30) NOT NULL, -- 'api', 'database', 'ml', 'system'
    metric_value DECIMAL(12,4),
    metric_unit VARCHAR(20), -- 'ms', 'seconds', 'percent', 'count', 'bytes'
    
    -- Context
    service_name VARCHAR(30),
    endpoint_name VARCHAR(100),
    request_id UUID,
    user_id UUID,
    
    -- Additional Dimensions
    dimensions JSONB, -- {"region": "us-east-1", "instance": "api-01"}
    tags JSONB, -- {"environment": "production", "version": "1.2.3"}
    
    -- Threshold Alerts
    threshold_warning DECIMAL(12,4),
    threshold_critical DECIMAL(12,4),
    alert_triggered BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    measured_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_performance_logs_metric (metric_name),
    INDEX idx_performance_logs_category (metric_category),
    INDEX idx_performance_logs_service (service_name),
    INDEX idx_performance_logs_measured (measured_at),
    INDEX idx_performance_logs_alert (alert_triggered),
    INDEX idx_performance_logs_metric_time (metric_name, measured_at)
) PARTITION BY RANGE (measured_at);
```

## 2. DATABASE CONSTRAINTS AND TRIGGERS

### 2.1 Data Quality Constraints

```sql
-- Data Quality Constraints

-- Ensure bounding box coordinates are valid
ALTER TABLE annotations ADD CONSTRAINT chk_annotations_bounding_box_valid 
CHECK (
    bounding_box->'x' IS NOT NULL AND 
    bounding_box->'y' IS NOT NULL AND 
    bounding_box->'width' IS NOT NULL AND 
    bounding_box->'height' IS NOT NULL AND
    (bounding_box->>'width')::DECIMAL > 0 AND
    (bounding_box->>'height')::DECIMAL > 0
);

-- Ensure confidence scores are in valid range
ALTER TABLE detection_events ADD CONSTRAINT chk_detection_confidence_range 
CHECK (confidence >= 0.0 AND confidence <= 1.0);

ALTER TABLE ground_truth_objects ADD CONSTRAINT chk_ground_truth_confidence_range 
CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0));

-- Ensure timestamps are positive and reasonable
ALTER TABLE annotations ADD CONSTRAINT chk_annotations_timestamp_valid 
CHECK (timestamp >= 0 AND (end_timestamp IS NULL OR end_timestamp >= timestamp));

-- Ensure frame numbers are non-negative
ALTER TABLE annotations ADD CONSTRAINT chk_annotations_frame_number_valid 
CHECK (frame_number >= 0);

-- Ensure video duration and fps are positive
ALTER TABLE videos ADD CONSTRAINT chk_videos_duration_positive 
CHECK (duration IS NULL OR duration > 0);

ALTER TABLE videos ADD CONSTRAINT chk_videos_fps_positive 
CHECK (fps IS NULL OR fps > 0);
```

### 2.2 Automated Data Management Triggers

```sql
-- Automated Update Triggers

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to all tables with updated_at column
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_annotations_updated_at BEFORE UPDATE ON annotations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_test_sessions_updated_at BEFORE UPDATE ON test_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Annotation session statistics update trigger
CREATE OR REPLACE FUNCTION update_annotation_session_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update annotation session statistics when annotations change
    UPDATE annotation_sessions 
    SET 
        total_detections = (
            SELECT COUNT(*) 
            FROM annotations 
            WHERE video_id = NEW.video_id
        ),
        validated_detections = (
            SELECT COUNT(*) 
            FROM annotations 
            WHERE video_id = NEW.video_id AND validated = TRUE
        ),
        last_activity_at = CURRENT_TIMESTAMP
    WHERE video_id = NEW.video_id AND status = 'active';
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_annotation_session_stats_trigger
    AFTER INSERT OR UPDATE OR DELETE ON annotations
    FOR EACH ROW EXECUTE FUNCTION update_annotation_session_stats();

-- Test session statistics update trigger
CREATE OR REPLACE FUNCTION update_test_session_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update test session statistics when detection events change
    UPDATE test_sessions 
    SET 
        total_detections = (
            SELECT COUNT(*) 
            FROM detection_events 
            WHERE test_session_id = NEW.test_session_id
        ),
        true_positives = (
            SELECT COUNT(*) 
            FROM detection_events 
            WHERE test_session_id = NEW.test_session_id AND validation_result = 'TP'
        ),
        false_positives = (
            SELECT COUNT(*) 
            FROM detection_events 
            WHERE test_session_id = NEW.test_session_id AND validation_result = 'FP'
        ),
        false_negatives = (
            SELECT COUNT(*) 
            FROM detection_events 
            WHERE test_session_id = NEW.test_session_id AND validation_result = 'FN'
        ),
        average_confidence = (
            SELECT AVG(confidence) 
            FROM detection_events 
            WHERE test_session_id = NEW.test_session_id AND confidence IS NOT NULL
        )
    WHERE id = NEW.test_session_id;
    
    -- Calculate derived metrics
    UPDATE test_sessions 
    SET 
        precision = CASE 
            WHEN (true_positives + false_positives) > 0 
            THEN true_positives::DECIMAL / (true_positives + false_positives)
            ELSE NULL 
        END,
        recall = CASE 
            WHEN (true_positives + false_negatives) > 0 
            THEN true_positives::DECIMAL / (true_positives + false_negatives)
            ELSE NULL 
        END
    WHERE id = NEW.test_session_id;
    
    -- Calculate F1 score
    UPDATE test_sessions 
    SET 
        f1_score = CASE 
            WHEN precision IS NOT NULL AND recall IS NOT NULL AND (precision + recall) > 0
            THEN 2 * (precision * recall) / (precision + recall)
            ELSE NULL 
        END
    WHERE id = NEW.test_session_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_test_session_stats_trigger
    AFTER INSERT OR UPDATE OR DELETE ON detection_events
    FOR EACH ROW EXECUTE FUNCTION update_test_session_stats();
```

## 3. PERFORMANCE OPTIMIZATION

### 3.1 Advanced Indexing Strategy

```sql
-- Advanced Performance Indexes

-- Composite indexes for complex queries
CREATE INDEX CONCURRENTLY idx_annotations_complex_search 
ON annotations (video_id, vru_type, validated, frame_number, timestamp);

CREATE INDEX CONCURRENTLY idx_detections_analytics 
ON detection_events (test_session_id, validation_result, confidence, timestamp);

CREATE INDEX CONCURRENTLY idx_ground_truth_validation 
ON ground_truth_objects (video_id, class_label, validated, confidence);

-- Partial indexes for common filtered queries
CREATE INDEX CONCURRENTLY idx_annotations_unvalidated 
ON annotations (video_id, frame_number) WHERE validated = FALSE;

CREATE INDEX CONCURRENTLY idx_detections_high_confidence 
ON detection_events (test_session_id, timestamp) WHERE confidence > 0.8;

CREATE INDEX CONCURRENTLY idx_videos_processing 
ON videos (project_id, created_at) WHERE processing_status IN ('pending', 'processing');

-- GIN indexes for JSONB columns
CREATE INDEX CONCURRENTLY idx_annotations_bounding_box_gin 
ON annotations USING GIN (bounding_box);

CREATE INDEX CONCURRENTLY idx_ground_truth_attributes_gin 
ON ground_truth_objects USING GIN (attributes);

CREATE INDEX CONCURRENTLY idx_test_sessions_criteria_gin 
ON test_sessions USING GIN (test_criteria);

-- Expression indexes for computed values
CREATE INDEX CONCURRENTLY idx_detection_events_area 
ON detection_events ((bounding_box_width * bounding_box_height));

CREATE INDEX CONCURRENTLY idx_annotations_center 
ON annotations (((bounding_box->>'x')::DECIMAL + (bounding_box->>'width')::DECIMAL/2),
                ((bounding_box->>'y')::DECIMAL + (bounding_box->>'height')::DECIMAL/2));
```

### 3.2 Database Optimization Settings

```sql
-- Optimization Settings for PostgreSQL

-- Connection and memory settings
-- postgresql.conf settings (for reference):
-- max_connections = 200
-- shared_buffers = 256MB
-- effective_cache_size = 1GB
-- work_mem = 16MB
-- maintenance_work_mem = 128MB
-- random_page_cost = 1.1
-- effective_io_concurrency = 200

-- Query optimization settings
SET enable_seqscan = ON;
SET enable_indexscan = ON;
SET enable_bitmapscan = ON;
SET enable_hashjoin = ON;
SET enable_mergejoin = ON;
SET enable_nestloop = ON;

-- Statistics settings for better query planning
ALTER DATABASE validation_platform SET default_statistics_target = 1000;

-- Auto-vacuum settings for high-throughput tables
ALTER TABLE audit_logs SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE detection_events SET (
    autovacuum_vacuum_scale_factor = 0.2,
    autovacuum_analyze_scale_factor = 0.1
);

ALTER TABLE performance_logs SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);
```

This comprehensive database schema architecture provides:

1. **Complete Data Model**: All entities with proper relationships and constraints
2. **Performance Optimization**: Comprehensive indexing strategy for all query patterns
3. **Data Integrity**: Constraints and triggers to maintain data quality
4. **Audit Trail**: Complete audit logging for security and compliance
5. **Scalability**: Partitioning strategy for high-volume tables
6. **Analytics Support**: Rich metadata and statistics for advanced analytics
7. **Flexibility**: JSONB fields for extensibility without schema changes