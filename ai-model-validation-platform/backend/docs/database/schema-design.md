# Database Schema Design Documentation

## Overview

This document provides a comprehensive analysis of the database schema design principles, architecture decisions, and design patterns used in the AI Model Validation Platform.

## Table of Contents

1. [Schema Design Principles](#schema-design-principles)
2. [Architectural Patterns](#architectural-patterns)
3. [Data Modeling Decisions](#data-modeling-decisions)
4. [Normalization Strategy](#normalization-strategy)
5. [Performance Design](#performance-design)
6. [Security Design](#security-design)
7. [Scalability Considerations](#scalability-considerations)

---

## Schema Design Principles

### 1. Domain-Driven Design

The schema is organized around core business domains:

**Authentication Domain:**
- `auth_users` - User management and authentication
- `user_sessions` - Session lifecycle and security

**Project Management Domain:**
- `projects` - Test campaign organization
- `video_project_links` - Flexible video assignment

**Content Domain:**
- `videos` - Media asset management
- `ground_truth_objects` - Reference data
- `annotations` - Manual annotation tracking

**Testing Domain:**
- `test_sessions` - Test execution context
- `detection_events` - Individual detection records
- `test_results` - Aggregated test outcomes

**Reporting Domain:**
- `test_reports` - Report metadata
- `report_snapshots` - Visual evidence storage

**Validation Domain:**
- `video_validation_criteria` - Validation rules
- `video_validation_results` - Validation outcomes
- `video_status_transitions` - Audit trail

### 2. Data Integrity First

**Foreign Key Constraints:**
- Every relationship has explicit foreign key constraints
- Cascade behaviors prevent orphaned data
- SET NULL used for optional references

**Validation Rules:**
- NOT NULL constraints on critical fields
- DEFAULT values prevent incomplete records
- CHECK constraints on enumerated values (where supported)

**Unique Constraints:**
- Prevent duplicate user emails/usernames
- Ensure unique session tokens
- Prevent duplicate video-project assignments

### 3. Audit and Compliance

**Timestamp Tracking:**
- `created_at` on all entities for audit trails
- `updated_at` for modification tracking
- Timezone-aware timestamps throughout

**Change Tracking:**
- `video_status_transitions` for workflow audit
- `audit_logs` for security events
- User attribution on all operations

**Data Lineage:**
- Detection events link to ground truth for validation
- Reports link to source sessions and events
- Complete traceability from input to output

---

## Architectural Patterns

### 1. Multi-Tenancy Through User Ownership

**Pattern:** Horizontal partitioning by user ownership

```sql
-- Every user-scoped table includes owner_id
CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR NOT NULL,
    owner_id VARCHAR(36) NOT NULL DEFAULT 'anonymous',
    -- ... other fields
    INDEX idx_projects_owner_id (owner_id)
);

-- Access control through joins
SELECT videos.* FROM videos 
JOIN video_project_links ON videos.id = video_project_links.video_id
JOIN projects ON video_project_links.project_id = projects.id
WHERE projects.owner_id = :user_id
```

**Benefits:**
- Complete data isolation between users
- Simplified security model
- Efficient user-scoped queries
- GDPR compliance support (user data deletion)

### 2. Many-to-Many with Metadata

**Pattern:** Junction tables with additional attributes

```sql
-- Junction table with metadata
CREATE TABLE video_project_links (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) REFERENCES videos(id) ON DELETE CASCADE,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Metadata fields
    assignment_reason TEXT,
    intelligent_match BOOLEAN DEFAULT TRUE,
    confidence_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE INDEX idx_video_project_unique (video_id, project_id)
);
```

**Benefits:**
- Flexible video-project relationships
- Metadata storage for business logic
- Audit trail of assignments
- Support for AI-driven matching

### 3. Temporal Data Management

**Pattern:** Time-series optimization with proper indexing

```sql
-- Temporal data with optimized indexes
CREATE TABLE detection_events (
    id VARCHAR(36) PRIMARY KEY,
    timestamp FLOAT NOT NULL,
    labjack_timestamp FLOAT,
    video_start_time FLOAT,
    -- ... other fields
    
    -- Temporal indexes for range queries
    INDEX idx_detection_timestamp (timestamp),
    INDEX idx_detection_session_timestamp (test_session_id, timestamp),
    INDEX idx_detection_labjack_timestamp (labjack_timestamp),
    INDEX idx_detection_video_start_time (video_start_time)
);
```

**Features:**
- Float timestamps for microsecond precision
- Multiple time references for synchronization
- Range query optimization
- Time-series analysis support

### 4. Flexible Metadata Storage

**Pattern:** JSON columns for extensible data

```sql
-- JSON columns for flexible storage
CREATE TABLE test_results (
    id VARCHAR(36) PRIMARY KEY,
    -- Structured metrics
    pass_rate FLOAT,
    avg_latency_ms FLOAT,
    
    -- Flexible metadata
    latency_distribution JSON,  -- Histogram data
    statistical_analysis JSON,  -- Advanced statistics
    confidence_intervals JSON,  -- Statistical confidence
    -- ...
);

-- Validation criteria with JSON configuration
CREATE TABLE video_validation_criteria (
    id VARCHAR(36) PRIMARY KEY,
    required_vru_types JSON,    -- ['pedestrian', 'cyclist']
    -- ...
);
```

**Benefits:**
- Schema evolution without migrations
- Complex data structure storage
- API flexibility
- Advanced analytics support

---

## Data Modeling Decisions

### 1. Primary Key Strategy

**Decision:** String UUIDs for all primary keys

```sql
-- Consistent UUID primary keys
CREATE TABLE example_table (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- ...
);
```

**Rationale:**
- **Distributed System Support:** UUIDs prevent ID collisions across instances
- **Security:** Non-sequential IDs prevent enumeration attacks  
- **API Flexibility:** String IDs work consistently across all clients
- **Migration Support:** UUIDs simplify database merging/splitting

**Trade-offs:**
- Larger storage footprint vs integers
- Slower joins vs sequential integers
- **Mitigation:** Proper indexing and query optimization

### 2. Timestamp Strategy

**Decision:** Timezone-aware timestamps with server defaults

```sql
-- Consistent timestamp pattern
CREATE TABLE example_table (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE ON UPDATE NOW(),
    -- ...
);
```

**Rationale:**
- **Global Deployment:** Timezone awareness for international users
- **Audit Requirements:** Precise creation and modification tracking
- **Time-series Analysis:** Consistent temporal data for analytics

### 3. Status Enumeration Strategy

**Decision:** String enums with database-level defaults

```sql
-- Status with default values
CREATE TABLE videos (
    id VARCHAR(36) PRIMARY KEY,
    status VARCHAR(50) NOT NULL DEFAULT 'uploaded',
    validation_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- ...
    
    INDEX idx_video_status (status),
    INDEX idx_video_validation_status (validation_status)
);
```

**Benefits:**
- **Readable:** Status values are self-documenting
- **Extensible:** New statuses added without schema changes
- **Queryable:** Status filtering with proper indexes
- **API-Friendly:** Direct JSON serialization

### 4. Spatial Data Strategy

**Decision:** Individual coordinate columns + JSON backup

```sql
-- Spatial data with dual storage
CREATE TABLE ground_truth_objects (
    id VARCHAR(36) PRIMARY KEY,
    
    -- Individual coordinates (preferred)
    x FLOAT NOT NULL,
    y FLOAT NOT NULL, 
    width FLOAT NOT NULL,
    height FLOAT NOT NULL,
    
    -- JSON backup (legacy compatibility)
    bounding_box JSON,
    
    -- Spatial query optimization
    INDEX idx_gt_spatial_bounds (x, y, width, height)
);
```

**Rationale:**
- **Query Performance:** Individual columns enable efficient spatial queries
- **API Compatibility:** JSON format for client applications
- **Analytics Support:** Numerical operations on coordinates
- **Migration Support:** Gradual transition from JSON to structured format

---

## Normalization Strategy

### 1. Third Normal Form (3NF) with Performance Exceptions

**Primary Strategy:** Full normalization to 3NF

**Example - User Authentication:**
```sql
-- Properly normalized
CREATE TABLE auth_users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    username VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    -- No derived or redundant data
);

CREATE TABLE user_sessions (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) REFERENCES auth_users(id),
    session_token VARCHAR UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    -- Normalized relationship
);
```

### 2. Strategic Denormalization for Performance

**Calculated Fields for Performance:**

```sql
-- Denormalized aggregates in test_results
CREATE TABLE test_results (
    id VARCHAR(36) PRIMARY KEY,
    test_session_id VARCHAR(36) REFERENCES test_sessions(id),
    
    -- Denormalized aggregates (calculated from detection_events)
    total_detections INTEGER,
    passed_detections INTEGER,
    failed_detections INTEGER,
    pass_rate FLOAT,
    avg_latency_ms FLOAT,
    -- These could be calculated but stored for performance
);
```

**Rationale:**
- **Query Performance:** Avoid expensive aggregate calculations
- **Dashboard Speed:** Real-time metrics without complex joins
- **Report Generation:** Pre-calculated statistics for reports
- **Data Consistency:** Managed through application logic and triggers

### 3. Hybrid Approach for Flexible Data

**Semi-Structured Data in JSON:**

```sql
-- Normalized core + flexible metadata
CREATE TABLE video_validation_criteria (
    id VARCHAR(36) PRIMARY KEY,
    
    -- Normalized core fields
    min_detection_count INTEGER NOT NULL DEFAULT 5,
    min_confidence_threshold FLOAT NOT NULL DEFAULT 0.7,
    
    -- Semi-structured flexible data  
    required_vru_types JSON, -- ['pedestrian', 'cyclist']
    custom_criteria JSON,   -- Extensible validation rules
);
```

---

## Performance Design

### 1. Index Strategy

**Comprehensive Index Design:**

```sql
-- 1. Primary access patterns
CREATE INDEX idx_videos_project_status ON videos (project_id, status);
CREATE INDEX idx_detection_session_timestamp ON detection_events (test_session_id, timestamp);

-- 2. Security filtering
CREATE INDEX idx_projects_owner_id ON projects (owner_id);
CREATE INDEX idx_auth_user_email_active ON auth_users (email, is_active);

-- 3. Analytics and reporting
CREATE INDEX idx_detection_session_latency ON detection_events (test_session_id, latency_ms);
CREATE INDEX idx_video_validation_workflow ON videos (status, hil_testing_ready, validated_at);

-- 4. Temporal analysis
CREATE INDEX idx_gt_video_timestamp ON ground_truth_objects (video_id, timestamp);
CREATE INDEX idx_annotation_video_frame ON annotations (video_id, frame_number);
```

**Index Categories:**

*Security Indexes (12):*
- User ownership filtering
- Active session lookups
- Permission verification

*Performance Indexes (25):*
- Join optimization
- Sort operation support
- Range query acceleration

*Analytics Indexes (18):*
- Aggregation support
- Time-series analysis
- Statistical calculations

### 2. Query Optimization Design

**Composite Index Patterns:**

```sql
-- Pattern: (foreign_key, filter_column, sort_column)
CREATE INDEX idx_detection_session_validation_time 
ON detection_events (test_session_id, validation_result, timestamp);

-- Supports queries like:
-- SELECT * FROM detection_events 
-- WHERE test_session_id = :id 
--   AND validation_result = 'Fail' 
-- ORDER BY timestamp;
```

**Covering Indexes for Hot Queries:**

```sql
-- Covering index includes all needed columns
CREATE INDEX idx_video_project_status_created_filename 
ON videos (project_id, status, created_at, filename);

-- Covers dashboard queries without table access
-- SELECT filename, created_at FROM videos 
-- WHERE project_id = :id AND status = 'validated'
-- ORDER BY created_at DESC;
```

### 3. Partitioning Strategy (Future)

**Time-Based Partitioning Design:**

```sql
-- Partition large tables by time (PostgreSQL example)
CREATE TABLE detection_events_2025_01 PARTITION OF detection_events
FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE detection_events_2025_02 PARTITION OF detection_events  
FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
```

**Benefits:**
- **Query Performance:** Partition pruning for time ranges
- **Maintenance:** Efficient archiving of old data
- **Storage Management:** Separate storage for different time periods

---

## Security Design

### 1. Defense in Depth

**Multi-Layer Security:**

*Layer 1 - Database Level:*
```sql
-- Foreign key constraints prevent orphaned data
-- Unique constraints prevent duplicates
-- NOT NULL constraints prevent incomplete data
```

*Layer 2 - Application Level:*
```python
# User ownership verification in all queries
def get_resource(db: Session, resource_id: str, user_id: str):
    return db.query(Resource).join(Project).filter(
        Resource.id == resource_id,
        Project.owner_id == user_id  # Security filter
    ).first()
```

*Layer 3 - API Level:*
```python
# Authentication required for all endpoints
# Rate limiting on sensitive operations
# Input validation on all parameters
```

### 2. Data Isolation

**User Data Segregation:**

```sql
-- Every user query includes ownership filter
SELECT videos.* FROM videos 
JOIN video_project_links ON videos.id = video_project_links.video_id
JOIN projects ON video_project_links.project_id = projects.id
WHERE projects.owner_id = :current_user_id
  AND videos.id = :requested_video_id;
```

**Row-Level Security Pattern:**
- Every resource access verified through ownership chain
- No direct resource access without user context
- Consistent security pattern across all operations

### 3. Audit Trail Design

**Comprehensive Tracking:**

```sql
-- Status change audit
CREATE TABLE video_status_transitions (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) REFERENCES videos(id),
    from_status VARCHAR NOT NULL,
    to_status VARCHAR NOT NULL,
    transition_reason VARCHAR NOT NULL,
    triggered_by VARCHAR(36), -- User ID or 'system'
    transition_metadata JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- General audit log
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) DEFAULT 'anonymous',
    event_type VARCHAR NOT NULL,
    event_data JSON,
    ip_address VARCHAR,
    user_agent VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Scalability Considerations

### 1. Horizontal Scaling Preparation

**Sharding-Friendly Design:**

```sql
-- User-based sharding preparation
-- All data associated with user_id for horizontal partitioning
CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY,
    owner_id VARCHAR(36) NOT NULL, -- Sharding key
    -- Indexes include sharding key
    INDEX idx_projects_owner_created (owner_id, created_at)
);
```

### 2. Read Replica Support

**Read-Heavy Query Optimization:**

```python
# Read operations can use replicas
@use_read_replica
def get_dashboard_stats(db: Session, user_id: str):
    # Analytics queries suitable for eventual consistency
    pass

# Write operations always use primary
@use_primary_db  
def create_video(db: Session, video_data: dict):
    # Consistency-critical operations
    pass
```

### 3. Caching Strategy Design

**Cache-Friendly Schema:**

```sql
-- Immutable data ideal for caching
CREATE TABLE ground_truth_objects (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) NOT NULL,
    -- Ground truth rarely changes after creation
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Frequently updated data with cache invalidation triggers
CREATE TABLE test_results (
    id VARCHAR(36) PRIMARY KEY,
    updated_at TIMESTAMP WITH TIME ZONE ON UPDATE NOW(),
    -- Cache TTL based on updated_at
);
```

### 4. Archive and Retention Strategy

**Data Lifecycle Management:**

```sql
-- Time-based archiving design
CREATE TABLE detection_events (
    id VARCHAR(36) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Partition by created_at for efficient archiving
    
    INDEX idx_detection_created_archival (created_at)
);
```

**Retention Policies:**
- Detection events: 2 years active, 5 years archived
- Audit logs: 7 years retention
- User sessions: 30 days active, 90 days audit
- Test reports: Permanent retention

---

## Design Evolution Strategy

### 1. Schema Versioning

**Migration-Friendly Design:**
- Nullable columns for new features
- Default values for backward compatibility
- JSON columns for extensible metadata
- Gradual migration paths planned

### 2. API Compatibility

**Backward Compatibility:**
```python
# Property methods for API compatibility
class Video(Base):
    @property
    def uploaded_at(self):
        # Maps new field to legacy API
        return self.created_at
    
    @property  
    def bounding_box(self):
        # Constructs JSON from individual coordinates
        if self.bounding_box_x is not None:
            return {
                "x": self.bounding_box_x,
                "y": self.bounding_box_y,
                "width": self.bounding_box_width,
                "height": self.bounding_box_height
            }
        return None
```

### 3. Performance Monitoring

**Query Performance Tracking:**
- Slow query logging enabled
- Index usage monitoring
- Query plan analysis
- Performance regression detection

This comprehensive schema design provides a robust foundation for the AI Model Validation Platform's data management needs while supporting future growth and evolution.