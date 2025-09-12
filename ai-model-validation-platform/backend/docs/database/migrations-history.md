# Database Migrations History

## Overview

This document provides a comprehensive analysis of all database migrations, schema evolution, and version management in the AI Model Validation Platform.

## Table of Contents

1. [Migration Architecture](#migration-architecture)
2. [Migration Timeline](#migration-timeline)
3. [Core Schema Migrations](#core-schema-migrations)
4. [Feature-Specific Migrations](#feature-specific-migrations)
5. [Schema Evolution Strategy](#schema-evolution-strategy)
6. [Migration Management](#migration-management)

---

## Migration Architecture

### Alembic Configuration

The platform uses Alembic for database migrations with the following structure:

```
migrations/
├── env.py                      # Alembic environment configuration
├── script.py.mako             # Migration template
├── alembic.ini                # Configuration file
└── versions/                  # Migration files
    ├── 0001_initial_schema_with_auth.py
    ├── 0002_labjack_timing_schema.py
    ├── 0003_latency_validation_schema.py
    ├── 001_video_validation_system.py
    └── ...
```

### Migration Naming Convention

**Standard Format:**
- `NNNN_descriptive_name.py` (e.g., `0001_initial_schema_with_auth.py`)
- Numeric prefixes for sequential ordering
- Descriptive names indicating the feature/change

**Special Migrations:**
- `comprehensive_migration.py` - Multi-table comprehensive updates
- `rollback_migration.py` - Rollback utilities
- `add_*.py` - Specific column/feature additions

---

## Migration Timeline

### Phase 1: Foundation (0001)
**Migration:** `0001_initial_schema_with_auth.py`
**Date:** 2025-08-27
**Purpose:** Initial schema with authentication support

**Tables Created:**
1. **auth_users** - Core authentication
2. **user_sessions** - Session management  
3. **projects** - Project containers

**Key Features:**
- UUID primary keys throughout
- Comprehensive indexing strategy
- Authentication security model
- User ownership patterns

**Indexes Created (16 total):**
```sql
-- Auth Users (6 indexes)
idx_auth_user_email_active (email, is_active)
idx_auth_user_username_active (username, is_active)  
idx_auth_user_active_verified (is_active, is_verified)
idx_auth_user_superuser_active (is_superuser, is_active)
idx_auth_user_created_active (created_at, is_active)
idx_auth_user_last_login (last_login)

-- User Sessions (6 indexes)
idx_session_user_active (user_id, is_active)
idx_session_token_active (session_token, is_active)
idx_session_expires_active (expires_at, is_active)
idx_session_user_activity (user_id, last_activity)
idx_session_ip_activity (ip_address, last_activity)  
idx_session_cleanup (expires_at, is_active)

-- Projects (4 indexes)
ix_projects_created_at (created_at)
ix_projects_name (name)
ix_projects_owner_id (owner_id)
ix_projects_status (status)
```

### Phase 2: LabJack Integration (0002)
**Migration:** `0002_labjack_timing_schema.py`
**Date:** 2025-09-09
**Purpose:** Add LabJack hardware timing validation support

**Tables Modified:**
1. **test_sessions** - Added timing thresholds
2. **detection_events** - Added LabJack timing fields
3. **test_results** - Added latency metrics

**New Columns Added (18 total):**

*TestSession Table:*
- `latency_threshold_ms` (Integer, Default: 100)
- `video_start_timestamp` (Float)

*DetectionEvent Table:*
- `latency_ms` (Float) - Calculated latency
- `labjack_timestamp` (Float) - LabJack signal timestamp
- `video_start_time` (Float) - Video reference time
- `labjack_voltage` (Float) - Voltage reading

*TestResult Table:*
- `pass_rate` (Float) - Pass percentage
- `avg_latency_ms` (Float) - Average latency
- `max_latency_ms` (Float) - Maximum latency
- `min_latency_ms` (Float) - Minimum latency
- `total_detections` (Integer) - Total detection count
- `passed_detections` (Integer) - Passed count
- `failed_detections` (Integer) - Failed count
- `latency_distribution` (JSON) - Distribution data

**New Indexes (13 total):**
```sql
-- LabJack Timing Indexes
idx_detection_latency_validation (latency_ms, validation_result)
idx_detection_labjack_timestamp (labjack_timestamp)
idx_detection_session_latency (test_session_id, latency_ms)
idx_detection_video_start_time (video_start_time)
idx_detection_labjack_voltage (labjack_voltage)
idx_detection_session_labjack_validation (test_session_id, validation_result, latency_ms)

-- Test Results Indexes  
idx_testresult_session_pass_rate (test_session_id, pass_rate)
idx_testresult_avg_latency (avg_latency_ms)
idx_testresult_max_latency (max_latency_ms)
idx_testresult_total_detections (total_detections)
idx_testresult_latency_range (min_latency_ms, max_latency_ms)
idx_testresult_pass_fail_counts (passed_detections, failed_detections)
```

### Phase 3: Enhanced Validation (0003)
**Migration:** `0003_latency_validation_schema.py`
**Date:** 2025-09-09  
**Purpose:** Extended latency validation for stored detection events

**Tables Modified:**
1. **stored_detection_events** - Latency validation fields
2. **test_results** - Enhanced statistical metrics

**New Columns Added (14 total):**

*StoredDetectionEvents Table:*
- `latency_ms` (Float)
- `validation_result` (String) - 'pass'/'fail'
- `threshold_ms` (Integer)
- `video_start_time` (Float)

*TestResults Table (Enhanced):*
- `median_latency_ms` (Float) - Statistical median
- `std_dev_latency_ms` (Float) - Standard deviation
- `validation_type` (String) - 'latency_based'
- `test_duration_seconds` (Float)
- `detection_rate_hz` (Float) - Rate analysis

**Performance Indexes (12 new):**
```sql
-- Statistical Analysis Indexes
idx_test_results_median_latency (median_latency_ms)
idx_test_results_std_dev_latency (std_dev_latency_ms)
idx_test_results_validation_type (validation_type)

-- Detection Event Indexes
idx_stored_detection_latency_ms (latency_ms)
idx_stored_detection_validation_result (validation_result)
```

### Phase 4: Video Validation System (001)
**Migration:** `001_video_validation_system.py`
**Date:** 2025-01-11
**Purpose:** Unified video validation workflow system

**Tables Created (3 new):**
1. **video_validation_criteria** - Configurable validation rules
2. **video_validation_results** - Validation outcomes
3. **video_status_transitions** - Audit trail

**Tables Modified:**
1. **videos** - Enhanced validation workflow fields

**New Video Columns (10 total):**
```sql
-- Validation Workflow
validation_status VARCHAR(50) NOT NULL DEFAULT 'pending'
validation_type VARCHAR(20) NULL
validated_at TIMESTAMP WITH TIME ZONE NULL
validated_by VARCHAR(36) NULL

-- Ground Truth Enhancement  
ground_truth_count INTEGER NOT NULL DEFAULT 0
ground_truth_quality_score FLOAT NULL
ground_truth_completed_at TIMESTAMP WITH TIME ZONE NULL

-- HIL Testing Readiness
hil_testing_ready BOOLEAN NOT NULL DEFAULT FALSE
hil_testing_approved_by VARCHAR(36) NULL
hil_testing_approved_at TIMESTAMP WITH TIME ZONE NULL
```

**New Tables Schema:**

*VideoValidationCriteria:*
- Configurable per-project or global validation rules
- Ground truth, technical, and content requirements
- Threshold configuration for automated validation

*VideoValidationResults:*
- Detailed validation scoring and outcomes
- Audit trail of validation decisions
- Support for manual and automated validation

*VideoStatusTransitions:*
- Complete audit trail of status changes
- Transition reasons and metadata
- User or system attribution

**New Indexes (18 total):**
```sql
-- Video Validation Workflow
idx_video_validation_status (validation_status)
idx_video_status_validation (status, validation_status)  
idx_video_hil_ready (hil_testing_ready, status)
idx_video_validation_completed (validated_at, validation_type)
idx_video_testing_workflow (status, hil_testing_ready, validated_at)

-- Validation Results
idx_validation_result_video (video_id)
idx_validation_result_type (validation_type) 
idx_validation_result_overall (overall_result)
idx_validation_result_score (overall_score)

-- Status Transitions (Audit)
idx_status_transition_video (video_id)
idx_status_transition_video_time (video_id, created_at)
idx_status_transition_from_to (from_status, to_status)
```

### Phase 5: Comprehensive Schema Updates
**Migration:** `comprehensive_migration.py`
**Purpose:** Systematic schema updates across all tables

**Enhanced Features:**
- Safe column addition with conflict resolution
- Index creation with existence checking
- Cross-database compatibility (PostgreSQL/SQLite)
- Rollback tracking and logging
- Performance optimization

**Key Improvements:**
1. **Detection Events Enhancement** - 15+ new columns for complete detection storage
2. **Ground Truth Coordinates** - Individual x,y,width,height columns
3. **Annotation Tracking** - Detection ID linkage and quality flags
4. **Performance Indexes** - 50+ indexes for query optimization

---

## Core Schema Migrations

### Authentication System Evolution

**Initial (0001):**
```sql
CREATE TABLE auth_users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    username VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    is_verified BOOLEAN DEFAULT FALSE
);
```

**Indexes Added:**
- Performance: Email and username lookups
- Security: Active user filtering
- Analytics: Creation time tracking

### Video Management Evolution

**Phase 1 - Basic Structure:**
- File metadata storage
- Project association
- Basic status tracking

**Phase 2 - Validation Integration (001):**
```sql
ALTER TABLE videos ADD COLUMN validation_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE videos ADD COLUMN validation_type VARCHAR(20);
ALTER TABLE videos ADD COLUMN validated_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE videos ADD COLUMN ground_truth_quality_score FLOAT;
ALTER TABLE videos ADD COLUMN hil_testing_ready BOOLEAN DEFAULT FALSE;
```

**Phase 3 - Performance Optimization:**
- Composite indexes for common queries
- Status workflow indexes
- Time-based analytics indexes

### Detection System Evolution

**Phase 1 - Basic Detection (Initial):**
```sql
CREATE TABLE detection_events (
    id VARCHAR(36) PRIMARY KEY,
    test_session_id VARCHAR(36) REFERENCES test_sessions(id),
    timestamp FLOAT NOT NULL,
    confidence FLOAT,
    class_label VARCHAR
);
```

**Phase 2 - LabJack Integration (0002):**
```sql
ALTER TABLE detection_events ADD COLUMN latency_ms FLOAT;
ALTER TABLE detection_events ADD COLUMN labjack_timestamp FLOAT;
ALTER TABLE detection_events ADD COLUMN video_start_time FLOAT;
ALTER TABLE detection_events ADD COLUMN labjack_voltage FLOAT;
```

**Phase 3 - Comprehensive Storage (comprehensive):**
```sql
-- Spatial data
ALTER TABLE detection_events ADD COLUMN bounding_box_x FLOAT;
ALTER TABLE detection_events ADD COLUMN bounding_box_y FLOAT;
ALTER TABLE detection_events ADD COLUMN bounding_box_width FLOAT;
ALTER TABLE detection_events ADD COLUMN bounding_box_height FLOAT;

-- Visual evidence
ALTER TABLE detection_events ADD COLUMN screenshot_path TEXT;
ALTER TABLE detection_events ADD COLUMN screenshot_zoom_path TEXT;

-- Processing metadata
ALTER TABLE detection_events ADD COLUMN processing_time_ms FLOAT;
ALTER TABLE detection_events ADD COLUMN model_version VARCHAR(100);
```

---

## Feature-Specific Migrations

### LabJack Hardware Integration

**Purpose:** Support hardware-in-the-loop testing with precise timing

**Migration Files:**
- `0002_labjack_timing_schema.py` - Core timing fields
- `0003_latency_validation_schema.py` - Extended validation

**Key Features Added:**
1. **Precise Timing Measurement**
   - Microsecond-level timestamp capture
   - Video synchronization references
   - Voltage level recording

2. **Pass/Fail Validation**
   - Configurable latency thresholds
   - Statistical analysis support
   - Distribution histogram data

3. **Performance Metrics**
   - Real-time pass rate calculation
   - Latency statistics (min, max, avg, median, std dev)
   - Detection rate monitoring

### Video Validation Workflow

**Purpose:** Standardized video qualification process

**Migration File:** `001_video_validation_system.py`

**Workflow States Added:**
```
uploaded → processing → completed → validated → hil_ready
    ↓         ↓           ↓          ↓         ↓
  error   pending_annotation  pending_validation  error
```

**Validation Criteria System:**
- Per-project or global configuration
- Technical requirements (duration, resolution, fps)
- Content requirements (VRU types, scene complexity)
- Ground truth quality thresholds

### Report Generation System

**Purpose:** Automated test report generation with visual evidence

**Tables Added:**
- `test_reports` - Report metadata and file paths
- `report_snapshots` - Failure snapshot tracking

**Features:**
- Multiple format support (HTML, PDF, JSON)
- Failure snapshot capture and storage
- Comprehensive metrics aggregation
- Audit trail and regeneration support

---

## Schema Evolution Strategy

### Version Management

**Alembic Integration:**
- Sequential migration numbering
- Dependency tracking via `down_revision`
- Branch merging support via `branch_labels`
- Database state inspection

**Migration Safety:**
- Non-destructive column additions
- Index creation with conflict resolution
- Default value assignment for new columns
- Rollback script generation

### Backward Compatibility

**Legacy Support:**
1. **Direct Project-Video Relationships**
   - Maintained during junction table migration
   - Gradual migration to many-to-many structure
   - Validation functions for data integrity

2. **Status Field Mapping**
   - Legacy `processing_status` mapped to `status`
   - Backward-compatible API responses
   - Client migration support

3. **Bounding Box Storage**
   - JSON format maintained alongside individual coordinates
   - Property methods for API compatibility
   - Flexible client support

### Performance Optimization Evolution

**Index Strategy Development:**

*Phase 1 - Basic Indexes:*
- Primary key indexes
- Foreign key indexes
- Simple column indexes

*Phase 2 - Composite Indexes:*
- Multi-column query optimization
- Join operation acceleration
- Status filtering performance

*Phase 3 - Analytics Indexes:*
- Time-series query support
- Statistical analysis optimization
- Reporting query acceleration

**Current Index Count by Table:**
- `auth_users`: 6 composite + 6 single = 12 total
- `user_sessions`: 6 composite + 7 single = 13 total  
- `videos`: 9 composite + 5 single = 14 total
- `detection_events`: 15 composite + 10 single = 25 total
- `ground_truth_objects`: 10 composite + 4 single = 14 total
- `annotations`: 11 composite + 5 single = 16 total

### Data Type Evolution

**Precision Improvements:**
- Integer milliseconds → Float microseconds (timing)
- VARCHAR → TEXT (flexible content)
- Boolean flags → Enumerated states (status)

**JSON Column Utilization:**
- Flexible metadata storage
- Statistical distribution data
- Validation criteria configuration
- Report generation templates

---

## Migration Management

### Rollback Strategy

**Automatic Rollback Support:**
- All migrations include `downgrade()` functions
- Index removal in reverse order
- Column removal with dependency checking
- Data preservation where possible

**Manual Rollback Tools:**
- `rollback_migration.py` - Interactive rollback utility
- Migration log tracking
- State verification after rollback

### Testing Strategy

**Migration Testing:**
1. **Dry Run Capability**
   - Preview changes without application
   - Conflict detection and resolution
   - Resource requirement estimation

2. **Validation Testing**
   - Schema comparison before/after
   - Data integrity verification
   - Performance regression testing

3. **Rollback Testing**
   - Complete rollback verification
   - Data loss prevention testing
   - Recovery time measurement

### Production Deployment

**Zero-Downtime Strategy:**
1. **Additive Changes First**
   - Add new columns with defaults
   - Create new indexes
   - Deploy application updates

2. **Non-Breaking Updates**
   - Update application to use new fields
   - Migrate data in background
   - Verify functionality

3. **Cleanup Phase**
   - Remove deprecated columns
   - Drop unused indexes
   - Optimize performance

**Monitoring and Verification:**
- Migration execution time tracking
- Database size impact measurement
- Query performance monitoring
- Error rate tracking during migration

### Development Workflow

**Local Development:**
```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Review generated migration
# Edit migration file if needed

# Apply migration
alembic upgrade head

# Test rollback
alembic downgrade -1
```

**Production Workflow:**
```bash
# Backup database
pg_dump production_db > backup.sql

# Dry run migration
python comprehensive_migration.py --dry-run

# Apply migration with monitoring
alembic upgrade head --sql > migration.sql
# Review SQL before applying
psql production_db < migration.sql

# Verify migration success
python verify_schema.py
```

This comprehensive migration history ensures reliable database evolution while maintaining data integrity and system performance throughout the AI Model Validation Platform's development lifecycle.