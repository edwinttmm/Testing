-- =====================================================================
-- AI Model Validation Platform - FIXED DATABASE INITIALIZATION
-- =====================================================================
-- This script fixes all database initialization issues identified in root cause analysis

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Set timezone for consistent timestamps
SET timezone = 'UTC';

-- =====================================================================
-- USERS TABLE - Authentication and authorization
-- =====================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create default admin user
INSERT INTO users (id, email, hashed_password, full_name, is_active, is_superuser) 
VALUES (
    uuid_generate_v4(),
    'admin@aivalidation.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewU5GdgH2rUXvOGe', -- 'admin123'
    'System Administrator',
    true,
    true
) ON CONFLICT (email) DO NOTHING;

-- =====================================================================
-- PROJECTS TABLE - Project management
-- =====================================================================
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================
-- DATASETS TABLE - Dataset management
-- =====================================================================
CREATE TABLE IF NOT EXISTS datasets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    created_by UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================
-- VIDEOS TABLE - Video file management
-- =====================================================================
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    duration FLOAT,
    width INTEGER,
    height INTEGER,
    fps FLOAT,
    codec VARCHAR(100),
    dataset_id UUID REFERENCES datasets(id) ON DELETE CASCADE,
    uploaded_by UUID REFERENCES users(id) ON DELETE CASCADE,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processing_status VARCHAR(50) DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')),
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================
-- GROUND_TRUTH_OBJECTS TABLE - Ground truth annotations
-- =====================================================================
CREATE TABLE IF NOT EXISTS ground_truth_objects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    class_name VARCHAR(100) NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    bbox_x FLOAT NOT NULL CHECK (bbox_x >= 0.0 AND bbox_x <= 1.0),
    bbox_y FLOAT NOT NULL CHECK (bbox_y >= 0.0 AND bbox_y <= 1.0),
    bbox_width FLOAT NOT NULL CHECK (bbox_width >= 0.0 AND bbox_width <= 1.0),
    bbox_height FLOAT NOT NULL CHECK (bbox_height >= 0.0 AND bbox_height <= 1.0),
    frame_number INTEGER NOT NULL CHECK (frame_number >= 0),
    timestamp_ms FLOAT,
    metadata JSONB DEFAULT '{}',
    created_by UUID REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================
-- DETECTION_EVENTS TABLE - Model detection results
-- =====================================================================
CREATE TABLE IF NOT EXISTS detection_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) DEFAULT 'unknown',
    class_name VARCHAR(100) NOT NULL,
    confidence FLOAT NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    bbox_x FLOAT NOT NULL CHECK (bbox_x >= 0.0 AND bbox_x <= 1.0),
    bbox_y FLOAT NOT NULL CHECK (bbox_y >= 0.0 AND bbox_y <= 1.0),
    bbox_width FLOAT NOT NULL CHECK (bbox_width >= 0.0 AND bbox_width <= 1.0),
    bbox_height FLOAT NOT NULL CHECK (bbox_height >= 0.0 AND bbox_height <= 1.0),
    frame_number INTEGER NOT NULL CHECK (frame_number >= 0),
    timestamp_ms FLOAT,
    processing_time_ms FLOAT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================
-- VALIDATION_RESULTS TABLE - Validation metrics and comparisons
-- =====================================================================
CREATE TABLE IF NOT EXISTS validation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) DEFAULT 'unknown',
    ground_truth_id UUID REFERENCES ground_truth_objects(id) ON DELETE CASCADE,
    detection_event_id UUID REFERENCES detection_events(id) ON DELETE CASCADE,
    iou_score FLOAT CHECK (iou_score >= 0.0 AND iou_score <= 1.0),
    precision_score FLOAT CHECK (precision_score >= 0.0 AND precision_score <= 1.0),
    recall_score FLOAT CHECK (recall_score >= 0.0 AND recall_score <= 1.0),
    f1_score FLOAT CHECK (f1_score >= 0.0 AND f1_score <= 1.0),
    match_type VARCHAR(20) CHECK (match_type IN ('true_positive', 'false_positive', 'false_negative')),
    confidence_threshold FLOAT DEFAULT 0.5,
    validation_metadata JSONB DEFAULT '{}',
    validated_by UUID REFERENCES users(id) ON DELETE CASCADE,
    validated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

-- =====================================================================
-- INDEXES for performance optimization
-- =====================================================================

-- Users indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);

-- Projects indexes
CREATE INDEX IF NOT EXISTS idx_projects_created_by ON projects(created_by);
CREATE INDEX IF NOT EXISTS idx_projects_active ON projects(is_active);

-- Datasets indexes
CREATE INDEX IF NOT EXISTS idx_datasets_project_id ON datasets(project_id);
CREATE INDEX IF NOT EXISTS idx_datasets_created_by ON datasets(created_by);
CREATE INDEX IF NOT EXISTS idx_datasets_active ON datasets(is_active);

-- Videos indexes
CREATE INDEX IF NOT EXISTS idx_videos_dataset_id ON videos(dataset_id);
CREATE INDEX IF NOT EXISTS idx_videos_uploaded_by ON videos(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_videos_processing_status ON videos(processing_status);
CREATE INDEX IF NOT EXISTS idx_videos_active ON videos(is_active);
CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename);

-- Ground truth indexes
CREATE INDEX IF NOT EXISTS idx_ground_truth_video_id ON ground_truth_objects(video_id);
CREATE INDEX IF NOT EXISTS idx_ground_truth_class_name ON ground_truth_objects(class_name);
CREATE INDEX IF NOT EXISTS idx_ground_truth_frame_number ON ground_truth_objects(frame_number);
CREATE INDEX IF NOT EXISTS idx_ground_truth_created_by ON ground_truth_objects(created_by);
CREATE INDEX IF NOT EXISTS idx_ground_truth_active ON ground_truth_objects(is_active);

-- Detection events indexes
CREATE INDEX IF NOT EXISTS idx_detection_events_video_id ON detection_events(video_id);
CREATE INDEX IF NOT EXISTS idx_detection_events_model_name ON detection_events(model_name);
CREATE INDEX IF NOT EXISTS idx_detection_events_class_name ON detection_events(class_name);
CREATE INDEX IF NOT EXISTS idx_detection_events_frame_number ON detection_events(frame_number);
CREATE INDEX IF NOT EXISTS idx_detection_events_confidence ON detection_events(confidence);
CREATE INDEX IF NOT EXISTS idx_detection_events_active ON detection_events(is_active);

-- Validation results indexes
CREATE INDEX IF NOT EXISTS idx_validation_results_video_id ON validation_results(video_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_model_name ON validation_results(model_name);
CREATE INDEX IF NOT EXISTS idx_validation_results_ground_truth_id ON validation_results(ground_truth_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_detection_event_id ON validation_results(detection_event_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_validated_by ON validation_results(validated_by);
CREATE INDEX IF NOT EXISTS idx_validation_results_active ON validation_results(is_active);

-- =====================================================================
-- TRIGGERS for automatic timestamp updates
-- =====================================================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update triggers to relevant tables
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_datasets_updated_at ON datasets;
CREATE TRIGGER update_datasets_updated_at BEFORE UPDATE ON datasets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_ground_truth_objects_updated_at ON ground_truth_objects;
CREATE TRIGGER update_ground_truth_objects_updated_at BEFORE UPDATE ON ground_truth_objects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================================
-- PERMISSIONS - Grant necessary permissions
-- =====================================================================

-- Grant permissions to application user
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_user WHERE usename = 'vru_user') THEN
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vru_user;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vru_user;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO vru_user;
    END IF;
END
$$;

-- =====================================================================
-- EXAMPLE DATA for testing (optional)
-- =====================================================================

-- Insert example project
INSERT INTO projects (id, name, description, created_by)
SELECT 
    uuid_generate_v4(),
    'Default Project',
    'Default project for testing and validation',
    u.id
FROM users u 
WHERE u.email = 'admin@aivalidation.local'
ON CONFLICT DO NOTHING;

-- Insert example dataset
INSERT INTO datasets (id, name, description, project_id, created_by)
SELECT 
    uuid_generate_v4(),
    'Default Dataset',
    'Default dataset for video uploads',
    p.id,
    u.id
FROM projects p
CROSS JOIN users u
WHERE p.name = 'Default Project' AND u.email = 'admin@aivalidation.local'
ON CONFLICT DO NOTHING;

-- =====================================================================
-- DATABASE STATISTICS and MAINTENANCE
-- =====================================================================

-- Analyze tables for query optimization
ANALYZE users;
ANALYZE projects;
ANALYZE datasets;
ANALYZE videos;
ANALYZE ground_truth_objects;
ANALYZE detection_events;
ANALYZE validation_results;

-- Log initialization completion
DO $$
BEGIN
    RAISE NOTICE 'AI Model Validation Platform database initialization completed successfully';
    RAISE NOTICE 'Tables created: users, projects, datasets, videos, ground_truth_objects, detection_events, validation_results';
    RAISE NOTICE 'Indexes created for performance optimization';
    RAISE NOTICE 'Triggers created for automatic timestamp updates';
    RAISE NOTICE 'Default admin user created: admin@aivalidation.local (password: admin123)';
END
$$;