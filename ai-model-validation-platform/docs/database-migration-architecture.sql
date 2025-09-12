-- SPARC Architecture Phase: Database Migration Scripts
-- Comprehensive database schema implementation for the unified system architecture

-- =============================================================================
-- 1. EXTENSIONS AND CONFIGURATION
-- =============================================================================

-- Enable required PostgreSQL extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configure timezone
SET timezone = 'UTC';

-- =============================================================================
-- 2. CORE DOMAIN TABLES
-- =============================================================================

-- Users table with comprehensive security features
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('user', 'annotator', 'validator', 'admin', 'super_admin')),
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'locked', 'suspended')),
    
    -- Security tracking
    failed_login_attempts INTEGER DEFAULT 0,
    last_login_attempt TIMESTAMP,
    last_successful_login TIMESTAMP,
    locked_until TIMESTAMP,
    password_expires_at TIMESTAMP,
    
    -- Multi-factor authentication
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret VARCHAR(255),
    mfa_backup_codes TEXT[], -- Encrypted backup codes
    
    -- Profile information
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    organization VARCHAR(255),
    department VARCHAR(255),
    security_clearance VARCHAR(50),
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID,
    updated_by UUID,
    
    -- Constraints
    CONSTRAINT fk_users_created_by FOREIGN KEY (created_by) REFERENCES users(id),
    CONSTRAINT fk_users_updated_by FOREIGN KEY (updated_by) REFERENCES users(id),
    
    -- Check constraints
    CONSTRAINT chk_password_hash_length CHECK (length(password_hash) >= 60),
    CONSTRAINT chk_salt_length CHECK (length(salt) >= 32),
    CONSTRAINT chk_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Optimized indexes for users table
CREATE INDEX CONCURRENTLY idx_users_username_trgm ON users USING gin(username gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_users_email_trgm ON users USING gin(email gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_users_status ON users(status) WHERE status != 'active';
CREATE INDEX CONCURRENTLY idx_users_role ON users(role);
CREATE INDEX CONCURRENTLY idx_users_locked_until ON users(locked_until) WHERE locked_until IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_users_mfa_enabled ON users(mfa_enabled) WHERE mfa_enabled = true;

-- Projects table with hierarchical support
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    parent_project_id UUID, -- For hierarchical projects
    
    -- Ownership and access control
    owner_id UUID NOT NULL,
    organization_id UUID,
    
    -- Project configuration
    project_type VARCHAR(50) DEFAULT 'standard' CHECK (project_type IN ('standard', 'research', 'validation', 'benchmark')),
    classification VARCHAR(50) DEFAULT 'internal' CHECK (classification IN ('public', 'internal', 'confidential', 'secret')),
    
    -- Project settings
    settings JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    
    -- Status and lifecycle
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'suspended', 'deleted')),
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID NOT NULL,
    updated_by UUID,
    
    -- Constraints
    CONSTRAINT fk_projects_owner FOREIGN KEY (owner_id) REFERENCES users(id),
    CONSTRAINT fk_projects_parent FOREIGN KEY (parent_project_id) REFERENCES projects(id),
    CONSTRAINT fk_projects_created_by FOREIGN KEY (created_by) REFERENCES users(id),
    CONSTRAINT fk_projects_updated_by FOREIGN KEY (updated_by) REFERENCES users(id),
    
    -- Prevent circular references in project hierarchy
    CONSTRAINT chk_projects_not_self_parent CHECK (id != parent_project_id)
);

-- Indexes for projects table
CREATE INDEX CONCURRENTLY idx_projects_owner ON projects(owner_id);
CREATE INDEX CONCURRENTLY idx_projects_parent ON projects(parent_project_id);
CREATE INDEX CONCURRENTLY idx_projects_status ON projects(status) WHERE status != 'active';
CREATE INDEX CONCURRENTLY idx_projects_type ON projects(project_type);
CREATE INDEX CONCURRENTLY idx_projects_name_trgm ON projects USING gin(name gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_projects_settings ON projects USING gin(settings);
CREATE INDEX CONCURRENTLY idx_projects_metadata ON projects USING gin(metadata);

-- Videos table with comprehensive metadata
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL,
    
    -- File information
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT NOT NULL,
    file_hash VARCHAR(64) NOT NULL, -- SHA-256 hash for integrity
    mime_type VARCHAR(100) NOT NULL,
    
    -- Video metadata
    duration DECIMAL(10,3),
    fps DECIMAL(6,3),
    width INTEGER,
    height INTEGER,
    bitrate BIGINT,
    codec VARCHAR(50),
    format VARCHAR(50),
    color_space VARCHAR(50),
    
    -- Processing status
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (
        processing_status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')
    ),
    ground_truth_generated BOOLEAN DEFAULT FALSE,
    annotation_count INTEGER DEFAULT 0,
    validated_annotation_count INTEGER DEFAULT 0,
    
    -- Processing metadata
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    processing_error TEXT,
    processing_logs JSONB DEFAULT '[]',
    
    -- Quality metrics
    quality_score DECIMAL(5,3),
    quality_flags TEXT[],
    
    -- Upload tracking
    upload_session_id UUID,
    upload_completed_at TIMESTAMP,
    uploaded_by UUID NOT NULL,
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_videos_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_videos_uploader FOREIGN KEY (uploaded_by) REFERENCES users(id),
    
    -- Check constraints
    CONSTRAINT chk_video_file_size CHECK (file_size > 0),
    CONSTRAINT chk_video_dimensions CHECK (
        (width IS NULL AND height IS NULL) OR 
        (width > 0 AND height > 0)
    ),
    CONSTRAINT chk_video_duration CHECK (duration IS NULL OR duration > 0),
    CONSTRAINT chk_video_fps CHECK (fps IS NULL OR fps > 0),
    CONSTRAINT chk_video_quality_score CHECK (
        quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)
    )
);

-- Performance indexes for videos table
CREATE INDEX CONCURRENTLY idx_videos_project ON videos(project_id);
CREATE INDEX CONCURRENTLY idx_videos_uploader ON videos(uploaded_by);
CREATE INDEX CONCURRENTLY idx_videos_status ON videos(processing_status);
CREATE INDEX CONCURRENTLY idx_videos_ground_truth ON videos(ground_truth_generated);
CREATE INDEX CONCURRENTLY idx_videos_filename_trgm ON videos USING gin(filename gin_trgm_ops);
CREATE INDEX CONCURRENTLY idx_videos_file_hash ON videos(file_hash);
CREATE INDEX CONCURRENTLY idx_videos_upload_session ON videos(upload_session_id);
CREATE INDEX CONCURRENTLY idx_videos_processing_times ON videos(processing_started_at, processing_completed_at);
CREATE INDEX CONCURRENTLY idx_videos_quality ON videos(quality_score) WHERE quality_score IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_videos_processing_logs ON videos USING gin(processing_logs);

-- =============================================================================
-- 3. ANNOTATION TABLES
-- =============================================================================

-- Annotations table with comprehensive tracking
CREATE TABLE annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    detection_id VARCHAR(100) NOT NULL, -- Unique within video
    
    -- Temporal information
    frame_number INTEGER NOT NULL,
    timestamp DECIMAL(10,3) NOT NULL,
    end_timestamp DECIMAL(10,3), -- For multi-frame annotations
    duration DECIMAL(10,3) GENERATED ALWAYS AS (
        CASE WHEN end_timestamp IS NOT NULL THEN end_timestamp - timestamp ELSE NULL END
    ) STORED,
    
    -- Object classification
    vru_type VARCHAR(50) NOT NULL CHECK (
        vru_type IN ('pedestrian', 'cyclist', 'motorcyclist', 'wheelchair_user', 'other_vru')
    ),
    subclass VARCHAR(50), -- More specific classification
    attributes JSONB DEFAULT '{}', -- Flexible attributes
    
    -- Spatial information (normalized coordinates 0-1)
    x DECIMAL(8,6) NOT NULL CHECK (x >= 0 AND x <= 1),
    y DECIMAL(8,6) NOT NULL CHECK (y >= 0 AND y <= 1),
    width DECIMAL(8,6) NOT NULL CHECK (width > 0 AND width <= 1),
    height DECIMAL(8,6) NOT NULL CHECK (height > 0 AND height <= 1),
    
    -- Additional spatial validation
    CONSTRAINT chk_annotation_bounds CHECK (x + width <= 1 AND y + height <= 1),
    
    -- Quality indicators
    confidence DECIMAL(5,3) CHECK (confidence >= 0 AND confidence <= 1),
    visibility DECIMAL(3,2) CHECK (visibility >= 0 AND visibility <= 1),
    occluded BOOLEAN DEFAULT FALSE,
    truncated BOOLEAN DEFAULT FALSE,
    difficult BOOLEAN DEFAULT FALSE,
    
    -- Annotation metadata
    notes TEXT,
    tags TEXT[],
    interpolated BOOLEAN DEFAULT FALSE, -- Auto-generated between keyframes
    keyframe BOOLEAN DEFAULT FALSE, -- Manual annotation point
    
    -- Workflow tracking
    annotation_session_id UUID,
    annotator UUID NOT NULL,
    annotation_method VARCHAR(50) DEFAULT 'manual' CHECK (
        annotation_method IN ('manual', 'automated', 'semi_automated', 'imported')
    ),
    annotation_tool VARCHAR(50),
    annotation_time_ms INTEGER, -- Time spent on this annotation
    
    -- Validation tracking
    validator UUID,
    validated BOOLEAN DEFAULT FALSE,
    validation_status VARCHAR(50) DEFAULT 'pending' CHECK (
        validation_status IN ('pending', 'approved', 'rejected', 'requires_changes')
    ),
    validation_score DECIMAL(5,3) CHECK (
        validation_score IS NULL OR (validation_score >= 0 AND validation_score <= 1)
    ),
    validation_comments TEXT,
    validation_flags TEXT[],
    
    -- Version control
    version INTEGER DEFAULT 1,
    parent_annotation_id UUID, -- For annotation revisions
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_annotations_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    CONSTRAINT fk_annotations_annotator FOREIGN KEY (annotator) REFERENCES users(id),
    CONSTRAINT fk_annotations_validator FOREIGN KEY (validator) REFERENCES users(id),
    CONSTRAINT fk_annotations_parent FOREIGN KEY (parent_annotation_id) REFERENCES annotations(id),
    
    -- Unique constraints
    UNIQUE(video_id, detection_id, version),
    
    -- Check constraints
    CONSTRAINT chk_temporal_order CHECK (
        end_timestamp IS NULL OR end_timestamp > timestamp
    ),
    CONSTRAINT chk_annotation_not_self_parent CHECK (id != parent_annotation_id)
);

-- Performance indexes for annotations table
CREATE INDEX CONCURRENTLY idx_annotations_video_frame ON annotations(video_id, frame_number);
CREATE INDEX CONCURRENTLY idx_annotations_video_timestamp ON annotations(video_id, timestamp);
CREATE INDEX CONCURRENTLY idx_annotations_vru_type ON annotations(vru_type);
CREATE INDEX CONCURRENTLY idx_annotations_annotator ON annotations(annotator);
CREATE INDEX CONCURRENTLY idx_annotations_validator ON annotations(validator);
CREATE INDEX CONCURRENTLY idx_annotations_validated ON annotations(validated, validation_status);
CREATE INDEX CONCURRENTLY idx_annotations_session ON annotations(annotation_session_id);
CREATE INDEX CONCURRENTLY idx_annotations_detection_id ON annotations(video_id, detection_id);
CREATE INDEX CONCURRENTLY idx_annotations_confidence ON annotations(confidence) WHERE confidence IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_annotations_attributes ON annotations USING gin(attributes);
CREATE INDEX CONCURRENTLY idx_annotations_tags ON annotations USING gin(tags);
CREATE INDEX CONCURRENTLY idx_annotations_parent ON annotations(parent_annotation_id);
CREATE INDEX CONCURRENTLY idx_annotations_keyframe ON annotations(video_id, keyframe) WHERE keyframe = true;

-- Ground truth objects table
CREATE TABLE ground_truth_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL,
    
    -- Temporal information
    frame_number INTEGER NOT NULL,
    timestamp DECIMAL(10,3) NOT NULL,
    
    -- Object classification
    class_label VARCHAR(50) NOT NULL,
    confidence DECIMAL(5,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    
    -- Spatial information (normalized coordinates)
    x DECIMAL(8,6) NOT NULL CHECK (x >= 0 AND x <= 1),
    y DECIMAL(8,6) NOT NULL CHECK (y >= 0 AND y <= 1),
    width DECIMAL(8,6) NOT NULL CHECK (width > 0 AND width <= 1),
    height DECIMAL(8,6) NOT NULL CHECK (height > 0 AND height <= 1),
    
    -- Spatial validation
    CONSTRAINT chk_gt_bounds CHECK (x + width <= 1 AND y + height <= 1),
    
    -- Quality indicators
    validated BOOLEAN DEFAULT FALSE,
    difficult BOOLEAN DEFAULT FALSE,
    occluded BOOLEAN DEFAULT FALSE,
    
    -- Processing metadata
    ml_model_name VARCHAR(100),
    ml_model_version VARCHAR(50),
    inference_time_ms INTEGER,
    processing_batch_id UUID,
    
    -- Quality scores
    quality_score DECIMAL(5,3) CHECK (
        quality_score IS NULL OR (quality_score >= 0 AND quality_score <= 1)
    ),
    validation_score DECIMAL(5,3) CHECK (
        validation_score IS NULL OR (validation_score >= 0 AND validation_score <= 1)
    ),
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_gt_objects_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- Performance indexes for ground truth objects
CREATE INDEX CONCURRENTLY idx_gt_objects_video_frame ON ground_truth_objects(video_id, frame_number);
CREATE INDEX CONCURRENTLY idx_gt_objects_video_timestamp ON ground_truth_objects(video_id, timestamp);
CREATE INDEX CONCURRENTLY idx_gt_objects_class ON ground_truth_objects(class_label);
CREATE INDEX CONCURRENTLY idx_gt_objects_confidence ON ground_truth_objects(confidence);
CREATE INDEX CONCURRENTLY idx_gt_objects_validated ON ground_truth_objects(validated);
CREATE INDEX CONCURRENTLY idx_gt_objects_model ON ground_truth_objects(ml_model_name, ml_model_version);
CREATE INDEX CONCURRENTLY idx_gt_objects_quality ON ground_truth_objects(quality_score) WHERE quality_score IS NOT NULL;
CREATE INDEX CONCURRENTLY idx_gt_objects_batch ON ground_truth_objects(processing_batch_id);

-- =============================================================================
-- 4. SECURITY AND AUDIT TABLES
-- =============================================================================

-- User sessions table for authentication tracking
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    
    -- Session data
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    session_data JSONB DEFAULT '{}',
    
    -- Expiration
    expires_at TIMESTAMP NOT NULL,
    
    -- Client information
    ip_address INET,
    user_agent TEXT,
    client_fingerprint VARCHAR(255),
    
    -- Location data
    country_code VARCHAR(2),
    city VARCHAR(100),
    
    -- Session metadata
    login_method VARCHAR(50), -- password, oauth2, sso
    mfa_verified BOOLEAN DEFAULT FALSE,
    risk_score DECIMAL(3,2) CHECK (risk_score >= 0 AND risk_score <= 1),
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Check constraints
    CONSTRAINT chk_session_expires_future CHECK (expires_at > created_at)
);

-- Performance indexes for user sessions
CREATE INDEX CONCURRENTLY idx_sessions_user ON user_sessions(user_id);
CREATE INDEX CONCURRENTLY idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX CONCURRENTLY idx_sessions_expires ON user_sessions(expires_at);
CREATE INDEX CONCURRENTLY idx_sessions_ip ON user_sessions(ip_address);
CREATE INDEX CONCURRENTLY idx_sessions_active ON user_sessions(user_id, expires_at) 
    WHERE expires_at > CURRENT_TIMESTAMP;
CREATE INDEX CONCURRENTLY idx_sessions_risk ON user_sessions(risk_score) 
    WHERE risk_score > 0.5;

-- Comprehensive audit logs table with partitioning
CREATE TABLE audit_logs (
    id BIGSERIAL,
    
    -- Event identification
    event_type VARCHAR(100) NOT NULL,
    event_category VARCHAR(50) NOT NULL, -- AUTH, DATA, SYSTEM, SECURITY
    
    -- User context
    user_id UUID,
    session_id UUID,
    
    -- Resource context
    resource_type VARCHAR(100),
    resource_id UUID,
    
    -- Action details
    action VARCHAR(100) NOT NULL,
    outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('success', 'failure', 'error')),
    
    -- Request context
    ip_address INET,
    user_agent TEXT,
    request_id UUID,
    correlation_id UUID,
    
    -- Event data
    event_data JSONB DEFAULT '{}',
    error_details JSONB,
    
    -- Security metadata
    risk_score DECIMAL(3,2) CHECK (risk_score >= 0 AND risk_score <= 1),
    threat_indicators TEXT[],
    
    -- Compliance and retention
    classification VARCHAR(50) DEFAULT 'internal',
    retention_policy VARCHAR(50) DEFAULT 'standard',
    
    -- Integrity protection
    integrity_hash VARCHAR(64), -- SHA-256 of sensitive fields
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_audit_logs_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_audit_logs_session FOREIGN KEY (session_id) REFERENCES user_sessions(id),
    
    PRIMARY KEY (id, created_at) -- Composite key for partitioning
) PARTITION BY RANGE (created_at);

-- Create initial partitions for audit logs (monthly partitions)
CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-01-01 00:00:00') TO ('2025-02-01 00:00:00');

CREATE TABLE audit_logs_2025_02 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-02-01 00:00:00') TO ('2025-03-01 00:00:00');

CREATE TABLE audit_logs_2025_03 PARTITION OF audit_logs
    FOR VALUES FROM ('2025-03-01 00:00:00') TO ('2025-04-01 00:00:00');

-- Indexes for audit logs (created on each partition)
CREATE INDEX CONCURRENTLY idx_audit_logs_2025_01_user ON audit_logs_2025_01(user_id);
CREATE INDEX CONCURRENTLY idx_audit_logs_2025_01_event_type ON audit_logs_2025_01(event_type);
CREATE INDEX CONCURRENTLY idx_audit_logs_2025_01_resource ON audit_logs_2025_01(resource_type, resource_id);
CREATE INDEX CONCURRENTLY idx_audit_logs_2025_01_event_data ON audit_logs_2025_01 USING gin(event_data);
CREATE INDEX CONCURRENTLY idx_audit_logs_2025_01_risk ON audit_logs_2025_01(risk_score) 
    WHERE risk_score > 0.5;

-- =============================================================================
-- 5. WORKFLOW AND PROCESSING TABLES
-- =============================================================================

-- Export records table
CREATE TABLE export_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID,
    project_id UUID,
    
    -- Export configuration
    export_format VARCHAR(50) NOT NULL CHECK (
        export_format IN ('coco', 'yolo', 'pascal_voc', 'csv', 'json', 'xml')
    ),
    export_type VARCHAR(50) NOT NULL CHECK (
        export_type IN ('annotations', 'ground_truth', 'both')
    ),
    
    -- File information
    file_path TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_hash VARCHAR(64), -- SHA-256 hash
    
    -- Export metadata
    exported_objects_count INTEGER NOT NULL DEFAULT 0,
    export_options JSONB DEFAULT '{}',
    filters_applied JSONB DEFAULT '{}',
    
    -- Processing information
    processing_time_ms INTEGER,
    export_started_at TIMESTAMP,
    export_completed_at TIMESTAMP,
    
    -- Access tracking
    download_count INTEGER DEFAULT 0,
    last_downloaded_at TIMESTAMP,
    
    -- Expiration
    expires_at TIMESTAMP,
    
    -- User tracking
    created_by UUID NOT NULL,
    
    -- Audit fields
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_export_records_video FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    CONSTRAINT fk_export_records_project FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    CONSTRAINT fk_export_records_creator FOREIGN KEY (created_by) REFERENCES users(id),
    
    -- Check constraints
    CONSTRAINT chk_export_file_size CHECK (file_size > 0),
    CONSTRAINT chk_export_objects_count CHECK (exported_objects_count >= 0)
);

-- Indexes for export records
CREATE INDEX CONCURRENTLY idx_export_records_video ON export_records(video_id);
CREATE INDEX CONCURRENTLY idx_export_records_project ON export_records(project_id);
CREATE INDEX CONCURRENTLY idx_export_records_creator ON export_records(created_by);
CREATE INDEX CONCURRENTLY idx_export_records_format ON export_records(export_format);
CREATE INDEX CONCURRENTLY idx_export_records_expires ON export_records(expires_at);
CREATE INDEX CONCURRENTLY idx_export_records_hash ON export_records(file_hash);

-- Processing jobs table for async operations
CREATE TABLE processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type VARCHAR(50) NOT NULL CHECK (
        job_type IN ('video_processing', 'ground_truth_generation', 'annotation_export', 'data_migration')
    ),
    
    -- Job configuration
    input_data JSONB NOT NULL,
    configuration JSONB DEFAULT '{}',
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'retrying')
    ),
    
    -- Progress tracking
    progress_percentage DECIMAL(5,2) DEFAULT 0 CHECK (
        progress_percentage >= 0 AND progress_percentage <= 100
    ),
    progress_message TEXT,
    
    -- Results and errors
    result_data JSONB,
    error_message TEXT,
    error_details JSONB,
    
    -- Retry logic
    attempt_count INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 60,
    
    -- Timing
    scheduled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Priority and resource allocation
    priority INTEGER DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    worker_id VARCHAR(100),
    resource_requirements JSONB DEFAULT '{}',
    
    -- User tracking
    created_by UUID NOT NULL,
    
    -- Constraints
    CONSTRAINT fk_processing_jobs_creator FOREIGN KEY (created_by) REFERENCES users(id)
);

-- Indexes for processing jobs
CREATE INDEX CONCURRENTLY idx_processing_jobs_status ON processing_jobs(status);
CREATE INDEX CONCURRENTLY idx_processing_jobs_type ON processing_jobs(job_type);
CREATE INDEX CONCURRENTLY idx_processing_jobs_creator ON processing_jobs(created_by);
CREATE INDEX CONCURRENTLY idx_processing_jobs_scheduled ON processing_jobs(scheduled_at);
CREATE INDEX CONCURRENTLY idx_processing_jobs_priority ON processing_jobs(status, priority) 
    WHERE status IN ('pending', 'retrying');
CREATE INDEX CONCURRENTLY idx_processing_jobs_worker ON processing_jobs(worker_id, status);

-- =============================================================================
-- 6. SYSTEM CONFIGURATION TABLES
-- =============================================================================

-- System configuration table
CREATE TABLE system_configuration (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    data_type VARCHAR(50) NOT NULL CHECK (
        data_type IN ('string', 'number', 'boolean', 'object', 'array')
    ),
    description TEXT,
    category VARCHAR(100) NOT NULL,
    is_sensitive BOOLEAN DEFAULT FALSE,
    validation_rules JSONB DEFAULT '{}',
    
    -- Change tracking
    updated_by UUID,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT fk_config_updater FOREIGN KEY (updated_by) REFERENCES users(id)
);

-- Indexes for system configuration
CREATE INDEX CONCURRENTLY idx_system_config_category ON system_configuration(category);
CREATE INDEX CONCURRENTLY idx_system_config_sensitive ON system_configuration(is_sensitive) 
    WHERE is_sensitive = true;

-- =============================================================================
-- 7. TRIGGERS AND FUNCTIONS
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER trigger_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_projects_updated_at 
    BEFORE UPDATE ON projects 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_videos_updated_at 
    BEFORE UPDATE ON videos 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER trigger_annotations_updated_at 
    BEFORE UPDATE ON annotations 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to update annotation counts on videos
CREATE OR REPLACE FUNCTION update_video_annotation_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE videos 
        SET annotation_count = annotation_count + 1,
            validated_annotation_count = validated_annotation_count + CASE WHEN NEW.validated THEN 1 ELSE 0 END
        WHERE id = NEW.video_id;
        
    ELSIF TG_OP = 'UPDATE' THEN
        -- Handle validation status change
        IF OLD.validated != NEW.validated THEN
            UPDATE videos 
            SET validated_annotation_count = validated_annotation_count + CASE WHEN NEW.validated THEN 1 ELSE -1 END
            WHERE id = NEW.video_id;
        END IF;
        
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE videos 
        SET annotation_count = annotation_count - 1,
            validated_annotation_count = validated_annotation_count - CASE WHEN OLD.validated THEN 1 ELSE 0 END
        WHERE id = OLD.video_id;
    END IF;
    
    RETURN COALESCE(NEW, OLD);
END;
$$ language 'plpgsql';

-- Apply annotation count triggers
CREATE TRIGGER trigger_annotations_count 
    AFTER INSERT OR UPDATE OR DELETE ON annotations 
    FOR EACH ROW EXECUTE FUNCTION update_video_annotation_counts();

-- Function for audit log integrity
CREATE OR REPLACE FUNCTION generate_audit_integrity_hash()
RETURNS TRIGGER AS $$
BEGIN
    NEW.integrity_hash = encode(
        digest(
            COALESCE(NEW.user_id::text, '') || 
            NEW.event_type || 
            NEW.action || 
            COALESCE(NEW.resource_id::text, '') ||
            NEW.created_at::text,
            'sha256'
        ),
        'hex'
    );
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply integrity hash trigger to audit logs
CREATE TRIGGER trigger_audit_logs_integrity 
    BEFORE INSERT ON audit_logs 
    FOR EACH ROW EXECUTE FUNCTION generate_audit_integrity_hash();

-- =============================================================================
-- 8. VIEWS FOR COMMON QUERIES
-- =============================================================================

-- View for active user sessions
CREATE VIEW active_user_sessions AS
SELECT 
    s.id,
    s.user_id,
    u.username,
    u.email,
    s.ip_address,
    s.created_at as login_time,
    s.last_accessed_at,
    s.expires_at,
    s.risk_score,
    s.mfa_verified
FROM user_sessions s
JOIN users u ON s.user_id = u.id
WHERE s.expires_at > CURRENT_TIMESTAMP
    AND u.status = 'active';

-- View for project statistics
CREATE VIEW project_statistics AS
SELECT 
    p.id as project_id,
    p.name as project_name,
    p.owner_id,
    COUNT(v.id) as video_count,
    SUM(v.file_size) as total_file_size,
    AVG(v.duration) as average_duration,
    COUNT(CASE WHEN v.ground_truth_generated THEN 1 END) as processed_videos,
    SUM(v.annotation_count) as total_annotations,
    SUM(v.validated_annotation_count) as validated_annotations
FROM projects p
LEFT JOIN videos v ON p.id = v.project_id
WHERE p.status = 'active'
GROUP BY p.id, p.name, p.owner_id;

-- View for annotation quality metrics
CREATE VIEW annotation_quality_metrics AS
SELECT 
    v.project_id,
    v.id as video_id,
    v.filename,
    COUNT(a.id) as total_annotations,
    COUNT(CASE WHEN a.validated THEN 1 END) as validated_annotations,
    AVG(a.confidence) as average_confidence,
    COUNT(CASE WHEN a.difficult THEN 1 END) as difficult_annotations,
    COUNT(CASE WHEN a.occluded THEN 1 END) as occluded_annotations,
    COUNT(DISTINCT a.vru_type) as unique_vru_types
FROM videos v
LEFT JOIN annotations a ON v.id = a.video_id
GROUP BY v.project_id, v.id, v.filename;

-- =============================================================================
-- 9. SECURITY POLICIES (ROW LEVEL SECURITY)
-- =============================================================================

-- Enable RLS on sensitive tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- User access policy - users can see their own data and public profiles
CREATE POLICY user_access_policy ON users
    FOR ALL
    TO application_role
    USING (
        id = current_setting('app.current_user_id')::uuid OR
        current_setting('app.user_role') = 'admin'
    );

-- Project access policy - based on ownership and membership
CREATE POLICY project_access_policy ON projects
    FOR ALL
    TO application_role
    USING (
        owner_id = current_setting('app.current_user_id')::uuid OR
        current_setting('app.user_role') IN ('admin', 'super_admin')
    );

-- =============================================================================
-- 10. PERFORMANCE OPTIMIZATION
-- =============================================================================

-- Analyze tables for query optimization
ANALYZE users;
ANALYZE projects;
ANALYZE videos;
ANALYZE annotations;
ANALYZE ground_truth_objects;
ANALYZE user_sessions;
ANALYZE audit_logs;

-- Set up automatic vacuum and analyze
ALTER TABLE annotations SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

ALTER TABLE audit_logs SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- =============================================================================
-- 11. INITIAL DATA
-- =============================================================================

-- Create system admin user
INSERT INTO users (
    id,
    username,
    email,
    password_hash,
    salt,
    role,
    status,
    first_name,
    last_name,
    created_at
) VALUES (
    gen_random_uuid(),
    'system_admin',
    'admin@system.local',
    crypt('admin123!', gen_salt('bf', 10)),
    gen_salt('bf', 10),
    'super_admin',
    'active',
    'System',
    'Administrator',
    CURRENT_TIMESTAMP
) ON CONFLICT (username) DO NOTHING;

-- Insert default system configuration
INSERT INTO system_configuration (key, value, data_type, description, category, is_sensitive) VALUES
('system.version', '"1.0.0"', 'string', 'Current system version', 'system', false),
('auth.session_timeout_minutes', '60', 'number', 'User session timeout in minutes', 'authentication', false),
('auth.max_failed_attempts', '5', 'number', 'Maximum failed login attempts before lockout', 'authentication', false),
('auth.lockout_duration_minutes', '30', 'number', 'Account lockout duration in minutes', 'authentication', false),
('ml.confidence_threshold', '0.3', 'number', 'Minimum confidence threshold for ML detections', 'ml_processing', false),
('export.max_concurrent_exports', '5', 'number', 'Maximum concurrent export operations', 'export', false),
('upload.max_file_size_mb', '500', 'number', 'Maximum video file size in MB', 'upload', false)
ON CONFLICT (key) DO NOTHING;

-- =============================================================================
-- 12. MAINTENANCE FUNCTIONS
-- =============================================================================

-- Function to create monthly audit log partitions
CREATE OR REPLACE FUNCTION create_audit_log_partition(partition_date DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    partition_name := 'audit_logs_' || to_char(partition_date, 'YYYY_MM');
    start_date := to_char(date_trunc('month', partition_date), 'YYYY-MM-DD HH24:MI:SS');
    end_date := to_char(date_trunc('month', partition_date) + interval '1 month', 'YYYY-MM-DD HH24:MI:SS');
    
    EXECUTE format('CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs FOR VALUES FROM (''%s'') TO (''%s'')',
                   partition_name, start_date, end_date);
    
    -- Create indexes for the new partition
    EXECUTE format('CREATE INDEX CONCURRENTLY IF NOT EXISTS %I ON %I(user_id)', 
                   'idx_' || partition_name || '_user', partition_name);
    EXECUTE format('CREATE INDEX CONCURRENTLY IF NOT EXISTS %I ON %I(event_type)', 
                   'idx_' || partition_name || '_event_type', partition_name);
    EXECUTE format('CREATE INDEX CONCURRENTLY IF NOT EXISTS %I ON %I(resource_type, resource_id)', 
                   'idx_' || partition_name || '_resource', partition_name);
END;
$$ LANGUAGE plpgsql;

-- Function to clean up expired sessions
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions 
    WHERE expires_at < CURRENT_TIMESTAMP - interval '1 hour';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to archive old export records
CREATE OR REPLACE FUNCTION archive_old_exports()
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    DELETE FROM export_records 
    WHERE expires_at < CURRENT_TIMESTAMP 
    AND expires_at IS NOT NULL;
    
    GET DIAGNOSTICS archived_count = ROW_COUNT;
    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- MIGRATION COMPLETE
-- =============================================================================

-- Final verification
SELECT 'Database migration completed successfully' as status;
SELECT schemaname, tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'public' 
ORDER BY tablename, indexname;