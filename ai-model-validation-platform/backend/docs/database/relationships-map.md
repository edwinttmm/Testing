# Database Relationships Mapping

## Overview

This document provides a comprehensive mapping of all table relationships, foreign key constraints, and dependencies in the AI Model Validation Platform database schema.

## Table of Contents

1. [Relationship Diagram](#relationship-diagram)
2. [Core Entity Relationships](#core-entity-relationships)
3. [Foreign Key Constraints](#foreign-key-constraints)
4. [Cascade Behaviors](#cascade-behaviors)
5. [Junction Tables](#junction-tables)
6. [Relationship Analysis](#relationship-analysis)

---

## Relationship Diagram

```
                    ┌─────────────┐
                    │  AuthUser   │
                    │ (auth_users)│
                    └──────┬──────┘
                           │ 1:N CASCADE
                    ┌──────▼──────┐
                    │ UserSession │
                    │(user_sessions)│
                    └─────────────┘

┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│   Project   │◄────┤VideoProjectLink├────►    Video     │
│ (projects)  │ 1:N │(video_project_│ N:1 │  (videos)    │
└──────┬──────┘     │    links)   │     └──────┬───────┘
       │            └─────────────┘            │
       │ 1:N                                   │ 1:N
       │ CASCADE                               │ CASCADE
       ▼                                       ▼
┌─────────────┐                         ┌──────────────┐
│TestSession  │                         │GroundTruth   │
│(test_sessions)│                       │   Object     │
└──────┬──────┘                         │(ground_truth_│
       │ 1:N CASCADE                    │  objects)    │
       ▼                                └──────────────┘
┌─────────────┐
│DetectionEvent│              Video 1:N CASCADE
│(detection_   │◄─────────────────────────────────┐
│  events)    │                                  │
└──────┬──────┘                                  ▼
       │                                 ┌──────────────┐
       │ 1:N CASCADE                     │ Annotation   │
       ▼                                 │(annotations) │
┌─────────────┐                         └──────┬───────┘
│ TestResult  │                                │
│(test_results)│                               │ 1:N
└─────────────┘                                ▼
                                        ┌──────────────┐
       TestSession 1:N CASCADE          │AnnotationSession│
       ┌─────────────────────┐          │(annotation_  │
       ▼                     ▼          │  sessions)   │
┌─────────────┐     ┌─────────────┐     └──────────────┘
│ TestReport  │     │DetectionComparison│
│(test_reports)│    │(detection_   │
└──────┬──────┘     │  comparisons)│
       │ 1:N        └─────────────┘
       │ CASCADE
       ▼
┌─────────────┐
│ReportSnapshot│
│(report_     │
│ snapshots)  │
└─────────────┘
```

---

## Core Entity Relationships

### 1. Authentication Hierarchy

**AuthUser (Parent)**
- **→ UserSession**: One-to-Many, CASCADE DELETE
- **Purpose**: Each user can have multiple active sessions
- **FK**: `user_sessions.user_id → auth_users.id`
- **Constraint**: When user is deleted, all sessions are automatically removed

### 2. Project-Video Many-to-Many Structure

**Project ↔ Video**: Many-to-Many via Junction Table
- **Junction Table**: `VideoProjectLink`
- **Purpose**: Videos can belong to multiple projects, projects can contain multiple videos
- **Left FK**: `video_project_links.project_id → projects.id`
- **Right FK**: `video_project_links.video_id → videos.id`
- **Constraints**: 
  - Unique constraint on (video_id, project_id) - no duplicate links
  - CASCADE DELETE on both sides - removes links when either entity is deleted

**Legacy Direct Relationship** (Deprecated but maintained):
- **Video → Project**: Many-to-One (legacy)
- **FK**: `videos.project_id → projects.id` (nullable, being phased out)
- **Note**: Being migrated to junction table system

### 3. Video Content Relationships

**Video (Parent)**
- **→ GroundTruthObject**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ Annotation**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ AnnotationSession**: One-to-Many, CASCADE DELETE-ORPHAN
- **Purpose**: All video-related content is deleted when video is removed

### 4. Project Management Relationships

**Project (Parent)**
- **→ TestSession**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ AnnotationSession**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ VideoProjectLink**: One-to-Many, CASCADE DELETE-ORPHAN
- **Purpose**: Project deletion removes all associated workflows

### 5. Test Execution Hierarchy

**TestSession (Parent)**
- **→ DetectionEvent**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ TestResult**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ DetectionComparison**: One-to-Many, CASCADE DELETE-ORPHAN
- **→ TestReport**: One-to-Many (backref), CASCADE via FK

**TestReport (Parent)**
- **→ ReportSnapshot**: One-to-Many, CASCADE DELETE-ORPHAN

### 6. Ground Truth Relationships

**GroundTruthObject (Referenced)**
- **← DetectionEvent**: Many-to-One, SET NULL
- **FK**: `detection_events.ground_truth_match_id → ground_truth_objects.id`
- **Purpose**: Optional ground truth matching for validation

**Annotation (Referenced)**
- **← DetectionComparison**: Many-to-One, SET NULL
- **FK**: `detection_comparisons.ground_truth_id → annotations.id`

---

## Foreign Key Constraints

### Authentication Foreign Keys

| Child Table | Child Column | Parent Table | Parent Column | On Delete |
|-------------|--------------|--------------|---------------|-----------|
| user_sessions | user_id | auth_users | id | CASCADE |

### Project-Video Foreign Keys

| Child Table | Child Column | Parent Table | Parent Column | On Delete |
|-------------|--------------|--------------|---------------|-----------|
| video_project_links | project_id | projects | id | CASCADE |
| video_project_links | video_id | videos | id | CASCADE |
| videos | project_id | projects | id | NULL (legacy) |

### Content Foreign Keys

| Child Table | Child Column | Parent Table | Parent Column | On Delete |
|-------------|--------------|--------------|---------------|-----------|
| ground_truth_objects | video_id | videos | id | CASCADE |
| annotations | video_id | videos | id | CASCADE |
| annotation_sessions | video_id | videos | id | CASCADE |
| annotation_sessions | project_id | projects | id | CASCADE |

### Test Execution Foreign Keys

| Child Table | Child Column | Parent Table | Parent Column | On Delete |
|-------------|--------------|--------------|---------------|-----------|
| test_sessions | project_id | projects | id | CASCADE |
| test_sessions | video_id | videos | id | CASCADE |
| detection_events | test_session_id | test_sessions | id | CASCADE |
| detection_events | video_id | videos | id | CASCADE |
| detection_events | ground_truth_match_id | ground_truth_objects | id | SET NULL |
| test_results | test_session_id | test_sessions | id | CASCADE |
| detection_comparisons | test_session_id | test_sessions | id | CASCADE |
| detection_comparisons | ground_truth_id | annotations | id | SET NULL |
| detection_comparisons | detection_event_id | detection_events | id | SET NULL |

### Reporting Foreign Keys

| Child Table | Child Column | Parent Table | Parent Column | On Delete |
|-------------|--------------|--------------|---------------|-----------|
| test_reports | test_session_id | test_sessions | id | CASCADE |
| report_snapshots | report_id | test_reports | id | CASCADE |
| report_snapshots | detection_event_id | detection_events | id | CASCADE |
| report_snapshots | video_id | videos | id | SET NULL |

### Validation System Foreign Keys

| Child Table | Child Column | Parent Table | Parent Column | On Delete |
|-------------|--------------|--------------|---------------|-----------|
| video_validation_criteria | project_id | projects | id | CASCADE |
| video_validation_results | video_id | videos | id | CASCADE |
| video_validation_results | validation_criteria_id | video_validation_criteria | id | RESTRICT |
| video_status_transitions | video_id | videos | id | CASCADE |

---

## Cascade Behaviors

### CASCADE DELETE (Parent deletion removes children)

**AuthUser CASCADE:**
- `AuthUser` deleted → All `UserSession` records deleted

**Project CASCADE:**
- `Project` deleted → All related `TestSession`, `AnnotationSession`, `VideoProjectLink` deleted
- `Project` deleted → Videos are NOT deleted (many-to-many relationship)

**Video CASCADE:**
- `Video` deleted → All `GroundTruthObject`, `Annotation`, `AnnotationSession` deleted
- `Video` deleted → All `DetectionEvent` where video_id matches deleted

**TestSession CASCADE:**
- `TestSession` deleted → All `DetectionEvent`, `TestResult`, `DetectionComparison`, `TestReport` deleted

**TestReport CASCADE:**
- `TestReport` deleted → All `ReportSnapshot` records deleted

### SET NULL (Parent deletion keeps children but nullifies reference)

**Optional References:**
- `GroundTruthObject` deleted → `DetectionEvent.ground_truth_match_id` set to NULL
- `Annotation` deleted → `DetectionComparison.ground_truth_id` set to NULL
- `DetectionEvent` deleted → `DetectionComparison.detection_event_id` set to NULL
- `Video` deleted → `ReportSnapshot.video_id` set to NULL

### DELETE-ORPHAN (SQLAlchemy ORM level)

Used in relationship definitions to automatically remove orphaned records:
- Project relationships use `cascade="all, delete-orphan"`
- Video relationships use `cascade="all, delete-orphan"`
- TestSession relationships use `cascade="all, delete-orphan"`

---

## Junction Tables

### VideoProjectLink Table

**Purpose**: Implements many-to-many relationship between projects and videos

**Schema:**
```sql
CREATE TABLE video_project_links (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) REFERENCES videos(id) ON DELETE CASCADE,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    assignment_reason TEXT,
    intelligent_match BOOLEAN DEFAULT TRUE,
    confidence_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Unique constraint prevents duplicate assignments
CREATE UNIQUE INDEX idx_video_project_unique 
ON video_project_links (video_id, project_id);
```

**Relationship Pattern:**
```python
# Project side
video_links = relationship("VideoProjectLink", back_populates="project", 
                          cascade="all, delete-orphan")

# Video side  
project_links = relationship("VideoProjectLink", back_populates="video", 
                           cascade="all, delete-orphan")

# Junction table relationships
project = relationship("Project", back_populates="video_links")
video = relationship("Video", back_populates="project_links")
```

---

## Relationship Analysis

### 1. Data Integrity Features

**Referential Integrity:**
- All foreign keys have proper constraints
- Cascade behaviors prevent orphaned records
- SET NULL used where appropriate for optional references

**Constraint Violations Prevention:**
- Unique constraints on critical combinations
- NOT NULL constraints on required foreign keys
- Default values for status and boolean fields

### 2. Performance Implications

**Join Optimization:**
- Foreign key columns are indexed
- Composite indexes for common join patterns
- Junction table has indexes on both foreign keys

**Query Performance:**
- Relationships designed for efficient queries
- Back references (backref) for bidirectional navigation
- Lazy loading configured appropriately

### 3. Scalability Considerations

**Many-to-Many Design:**
- VideoProjectLink allows flexible video assignment
- Supports video reuse across multiple projects
- Metadata storage in junction table (confidence_score, assignment_reason)

**Hierarchical Relationships:**
- Clear parent-child hierarchies for data organization
- CASCADE behaviors support bulk operations
- Audit trail maintained through status transitions

### 4. Business Logic Support

**Workflow Support:**
- Relationships support video validation workflow
- Test execution hierarchy maintains context
- Report generation has complete data lineage

**Security Integration:**
- User ownership tracked through relationships
- Session management with CASCADE cleanup
- Audit logging captures relationship changes

### 5. Migration Support

**Legacy Compatibility:**
- Direct video→project relationship maintained during migration
- Gradual migration to junction table system
- Validation functions ensure data consistency

**Evolution Support:**
- Nullable foreign keys allow schema evolution
- JSON columns for flexible data expansion
- Migration scripts handle relationship updates

---

## Common Relationship Patterns

### 1. Getting Project Videos (Many-to-Many)

```python
# Via junction table (current)
project_videos = db.query(Video).join(VideoProjectLink).filter(
    VideoProjectLink.project_id == project_id
).all()

# Direct query (legacy, being phased out)
legacy_videos = db.query(Video).filter(Video.project_id == project_id).all()
```

### 2. User Security Filtering

```python
# Ensure user can only access their projects
user_projects = db.query(Project).filter(Project.owner_id == user_id).all()

# Get videos accessible to user through projects
user_videos = db.query(Video).join(VideoProjectLink).join(Project).filter(
    Project.owner_id == user_id
).distinct().all()
```

### 3. Cascade Deletion Example

```python
# Deleting project cascades to related entities
db.delete(project)  # Automatically deletes:
# - test_sessions (CASCADE)
# - annotation_sessions (CASCADE) 
# - video_project_links (CASCADE)
# - Videos remain if linked to other projects
db.commit()
```

### 4. Report Generation Relationships

```python
# Complete report with all relationships
report = db.query(TestReport).options(
    joinedload(TestReport.snapshots),
    joinedload(TestReport.test_session).joinedload(TestSession.detection_events)
).filter(TestReport.id == report_id).first()
```

---

## Relationship Maintenance

### 1. Integrity Checks

Regular maintenance functions check relationship integrity:
- `validate_project_video_relationships()`: Checks junction table consistency
- `cleanup_orphaned_videos()`: Removes videos not linked to any project
- `migrate_legacy_video_relationships()`: Converts direct to junction table links

### 2. Performance Monitoring

Key performance indicators for relationships:
- Join query performance
- Foreign key constraint check time
- CASCADE operation duration
- Index utilization on relationship columns

### 3. Evolution Strategy

**Phase 1**: Legacy direct relationships (completed)
**Phase 2**: Junction table introduction (current)
**Phase 3**: Legacy relationship removal (future)
**Phase 4**: Advanced relationship features (future)

This comprehensive relationship mapping ensures data consistency, query performance, and supports the complex workflows of the VRU detection validation platform.