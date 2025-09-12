# Database Model Relationships and Schema

## Overview

The database schema implements a comprehensive data model for AI model validation with emphasis on VRU (Vulnerable Road User) detection, LabJack hardware timing integration, and comprehensive test result tracking. The schema supports both legacy single-project relationships and modern many-to-many project-video assignments.

## Core Entity Relationships

### 1. Authentication & User Management

#### AuthUser Model
**Primary Entity**: User authentication and authorization
```python
class AuthUser(Base):
    __tablename__ = "auth_users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    is_superuser = Column(Boolean, default=False, index=True)
```

**Relationships**: 
- **One-to-Many**: AuthUser → UserSession
- **One-to-Many**: AuthUser → Project (via owner_id)
- **Security Indexes**: Composite indexes for performance and security queries

#### UserSession Model
**Purpose**: Session tracking and security
```python
class UserSession(Base):
    __tablename__ = "user_sessions"
    
    user_id = Column(String(36), ForeignKey("auth_users.id", ondelete="CASCADE"))
    session_token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Relationship
    user = relationship("AuthUser")
```

### 2. Project-Video Many-to-Many System

#### Project Model
**Core Entity**: Project containers for organizing videos and tests
```python
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    owner_id = Column(String(36), nullable=True, default="anonymous", index=True)
    camera_view = Column(String, nullable=False)  # Front-facing VRU, etc.
    signal_type = Column(String, nullable=False)  # GPIO, Network Packet, Serial
    status = Column(String, default="Active", index=True)
```

**Relationships**:
- **One-to-Many**: Project → TestSession
- **One-to-Many**: Project → AnnotationSession
- **Many-to-Many**: Project ↔ Video (via VideoProjectLink)

#### Video Model
**Core Entity**: Video files with comprehensive metadata
```python
class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String(36), primary_key=True)
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    
    # UNIFIED STATUS SYSTEM
    status = Column(String, default="uploaded", index=True)
    validation_status = Column(String, default="pending", index=True)
    ground_truth_generated = Column(Boolean, default=False, index=True)
    hil_testing_ready = Column(Boolean, default=False, index=True)
    
    # Legacy compatibility
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
```

**Relationships**:
- **Many-to-Many**: Video ↔ Project (via VideoProjectLink)
- **One-to-Many**: Video → GroundTruthObject
- **One-to-Many**: Video → Annotation
- **One-to-Many**: Video → TestSession

#### VideoProjectLink Model (Junction Table)
**Purpose**: Many-to-many relationship between videos and projects
```python
class VideoProjectLink(Base):
    __tablename__ = "video_project_links"
    
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    assignment_reason = Column(Text)
    intelligent_match = Column(Boolean, default=True)
    confidence_score = Column(Float)
    
    # Relationships
    video = relationship("Video", back_populates="project_links")
    project = relationship("Project", back_populates="video_links")
    
    # Unique constraint
    __table_args__ = (
        Index('idx_video_project_unique', 'video_id', 'project_id', unique=True),
    )
```

### 3. Ground Truth and Annotation System

#### GroundTruthObject Model
**Purpose**: VRU detection ground truth annotations
```python
class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"
    
    id = Column(String(36), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    tracking_id = Column(String, nullable=True, index=True)  # VRU tracking across frames
    frame_number = Column(Integer, nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    class_label = Column(String, nullable=False, index=True)  # pedestrian, cyclist, etc.
    
    # Bounding box coordinates (normalized)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False) 
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    
    confidence = Column(Float, index=True)
    validated = Column(Boolean, default=False, index=True)
```

**Advanced Indexes**:
```python
__table_args__ = (
    Index('idx_gt_video_timestamp', 'video_id', 'timestamp'),
    Index('idx_gt_video_tracking_id', 'video_id', 'tracking_id'),  # VRU tracking
    Index('idx_gt_spatial_bounds', 'x', 'y', 'width', 'height'),  # Spatial queries
)
```

#### Annotation Model
**Purpose**: Manual annotation system with detection ID tracking
```python
class Annotation(Base):
    __tablename__ = "annotations"
    
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    detection_id = Column(String(36), nullable=True, index=True)  # DET_PED_0001, etc.
    vru_type = Column(String, nullable=False, index=True)
    bounding_box = Column(JSON, nullable=False)
    annotator = Column(String(36))
    validated = Column(Boolean, default=False, index=True)
```

### 4. Test Execution System

#### TestSession Model
**Purpose**: Test execution orchestration with LabJack timing
```python
class TestSession(Base):
    __tablename__ = "test_sessions"
    
    id = Column(String(36), primary_key=True)
    name = Column(String, nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    status = Column(String, default="created", index=True)
    session_type = Column(String, default="user_created", index=True)
    
    # LabJack timing fields
    latency_threshold_ms = Column(Integer, default=100, index=True)
    video_start_timestamp = Column(Float, nullable=True, index=True)
```

**Relationships**:
- **Many-to-One**: TestSession → Project
- **Many-to-One**: TestSession → Video
- **One-to-Many**: TestSession → DetectionEvent
- **One-to-Many**: TestSession → TestResult
- **One-to-Many**: TestSession → DetectionComparison

#### DetectionEvent Model  
**Purpose**: Individual detection events with LabJack timing data
```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"
    
    id = Column(String(36), primary_key=True)
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    timestamp = Column(Float, nullable=False, index=True)
    validation_result = Column(String, index=True)  # 'Pass', 'Fail'
    
    # LabJack timing data (PRIMARY)
    latency_ms = Column(Float, nullable=True, index=True)
    labjack_timestamp = Column(Float, nullable=True, index=True)
    labjack_voltage = Column(Float, nullable=True)
    latency_result = Column(String, nullable=True, index=True)  # 'pass', 'fail', 'timeout'
    
    # Legacy AI fields (for backward compatibility)
    confidence = Column(Float, index=True)
    class_label = Column(String, index=True)
    
    # Source tracking for display
    source = Column(String, nullable=True, index=True, default='ai')  # 'ai' or 'manual'
    detection_type = Column(String, nullable=True, index=True, default='automatic')
```

**Performance Indexes**:
```python
__table_args__ = (
    Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
    Index('idx_detection_latency_validation', 'latency_ms', 'validation_result'),
    Index('idx_detection_session_labjack_validation', 'test_session_id', 'validation_result', 'latency_ms'),
)
```

### 5. Results and Analytics System

#### TestResult Model
**Purpose**: Aggregated test results with LabJack timing metrics
```python
class TestResult(Base):
    __tablename__ = "test_results"
    
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"))
    
    # PRIMARY LABJACK TIMING METRICS
    pass_rate = Column(Float, index=True)
    avg_latency_ms = Column(Float, index=True)
    max_latency_ms = Column(Float, index=True) 
    min_latency_ms = Column(Float, index=True)
    median_latency_ms = Column(Float, index=True)
    std_dev_latency_ms = Column(Float, index=True)
    total_detections = Column(Integer, index=True)
    passed_detections = Column(Integer, index=True)
    failed_detections = Column(Integer, index=True)
    threshold_ms = Column(Integer, index=True)
    latency_distribution = Column(JSON)  # Histogram data
    
    # Legacy AI metrics (mapped from latency for compatibility)
    accuracy = Column(Float)  # Maps to pass_rate
    precision = Column(Float)  # Maps to pass_rate
```

#### DetectionComparison Model
**Purpose**: Ground truth validation and comparison
```python
class DetectionComparison(Base):
    __tablename__ = "detection_comparisons"
    
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"))
    ground_truth_id = Column(String(36), ForeignKey("annotations.id", ondelete="SET NULL"))
    detection_event_id = Column(String(36), ForeignKey("detection_events.id", ondelete="SET NULL"))
    match_type = Column(String, nullable=False, index=True)  # 'TP', 'FP', 'FN', 'TN'
    iou_score = Column(Float)
    temporal_offset = Column(Float)
```

### 6. Reporting System (PRD Module 4.2)

#### TestReport Model
**Purpose**: Test report metadata and file tracking
```python
class TestReport(Base):
    __tablename__ = "test_reports"
    
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"))
    report_name = Column(String, nullable=False, index=True)
    report_type = Column(String, nullable=False, index=True)  # 'comprehensive', 'summary'
    formats_generated = Column(JSON)  # ['html', 'pdf', 'json']
    
    # Report metrics snapshot
    total_events = Column(Integer, default=0)
    passed_events = Column(Integer, default=0)
    failed_events = Column(Integer, default=0)
    pass_rate_percent = Column(Float, index=True)
    test_outcome = Column(String, index=True)  # 'PASS', 'FAIL', 'NO_DATA'
    
    # File paths
    html_report_path = Column(String)
    pdf_report_path = Column(String)
    json_report_path = Column(String)
    
    # Failure snapshots
    failure_snapshots_count = Column(Integer, default=0)
    snapshots_storage_path = Column(String)
```

#### ReportSnapshot Model
**Purpose**: Failure snapshot metadata for visual evidence
```python
class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    
    report_id = Column(String(36), ForeignKey("test_reports.id", ondelete="CASCADE"))
    detection_event_id = Column(String(36), ForeignKey("detection_events.id", ondelete="CASCADE"))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="SET NULL"))
    
    failure_type = Column(String, nullable=False, index=True)  # 'HIGH_LATENCY', 'MISSED_DETECTION'
    timestamp_ms = Column(Float, nullable=False, index=True)
    frame_number = Column(Integer, index=True)
    snapshot_filename = Column(String, nullable=False)
    snapshot_path = Column(String, nullable=False)
```

### 7. Video Validation System

#### VideoValidationCriteria Model
**Purpose**: Configurable validation criteria per project
```python
class VideoValidationCriteria(Base):
    __tablename__ = "video_validation_criteria"
    
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    min_detection_count = Column(Integer, default=5)
    min_confidence_threshold = Column(Float, default=0.7)
    min_frame_coverage_percent = Column(Float, default=80.0)
    required_vru_types = Column(JSON)  # ['pedestrian', 'cyclist']
```

#### VideoValidationResult Model
**Purpose**: Results of video validation process
```python
class VideoValidationResult(Base):
    __tablename__ = "video_validation_results"
    
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    validation_criteria_id = Column(String(36), ForeignKey("video_validation_criteria.id"))
    validation_type = Column(String, nullable=False, index=True)  # 'automatic', 'manual'
    overall_result = Column(String, nullable=False, index=True)  # 'passed', 'failed'
    overall_score = Column(Float, index=True)
    criteria_met = Column(JSON)  # Detailed pass/fail criteria
```

#### VideoStatusTransition Model
**Purpose**: Audit trail for video status changes
```python
class VideoStatusTransition(Base):
    __tablename__ = "video_status_transitions"
    
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    from_status = Column(String, nullable=False, index=True)
    to_status = Column(String, nullable=False, index=True)
    transition_reason = Column(String, nullable=False)
    triggered_by = Column(String(36), nullable=True)  # User ID or 'system'
    transition_metadata = Column(JSON)
```

### 8. Annotation Session Management

#### AnnotationSession Model
**Purpose**: Collaborative annotation session tracking
```python
class AnnotationSession(Base):
    __tablename__ = "annotation_sessions"
    
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    annotator_id = Column(String(36), nullable=True, index=True)
    status = Column(String, default="active", index=True)  # 'active', 'paused', 'completed'
    total_detections = Column(Integer, default=0)
    validated_detections = Column(Integer, default=0)
```

### 9. Audit and Logging

#### AuditLog Model
**Purpose**: Comprehensive system audit trail
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    user_id = Column(String(36), nullable=True, default="anonymous", index=True)
    event_type = Column(String, nullable=False, index=True)
    event_data = Column(JSON)
    ip_address = Column(String, index=True)
    user_agent = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
```

## Cascade Relationships and Data Integrity

### Cascade Deletion Rules

#### Project Deletion
```python
# CASCADE relationships for Project
videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
test_sessions = relationship("TestSession", back_populates="project", cascade="all, delete-orphan")
annotation_sessions = relationship("AnnotationSession", back_populates="project", cascade="all, delete-orphan")
video_links = relationship("VideoProjectLink", back_populates="project", cascade="all, delete-orphan")
```

**Cascade Effect**: Deleting a project automatically removes:
- All VideoProjectLink associations
- All TestSessions and their DetectionEvents
- All AnnotationSessions
- Videos only if not in other projects

#### Video Deletion
```python
# CASCADE relationships for Video
ground_truth_objects = relationship("GroundTruthObject", back_populates="video", cascade="all, delete-orphan")
annotations = relationship("Annotation", back_populates="video", cascade="all, delete-orphan")
project_links = relationship("VideoProjectLink", back_populates="video", cascade="all, delete-orphan")
```

#### TestSession Deletion
```python
# CASCADE relationships for TestSession
detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")
results = relationship("TestResult", back_populates="test_session", cascade="all, delete-orphan")
detection_comparisons = relationship("DetectionComparison", back_populates="test_session", cascade="all, delete-orphan")
```

### Foreign Key Constraints

#### Strong References (CASCADE)
- `video_id` → `videos.id` (CASCADE for dependent data)
- `project_id` → `projects.id` (CASCADE for project-owned entities)
- `test_session_id` → `test_sessions.id` (CASCADE for session data)

#### Weak References (SET NULL)
- `ground_truth_match_id` → `ground_truth_objects.id` (SET NULL)
- `validated_by` → `auth_users.id` (SET NULL for audit preservation)

## Performance Optimization Indexes

### Composite Indexes for Complex Queries

#### Video Status and Validation
```python
Index('idx_video_status_validation', 'status', 'validation_status')
Index('idx_video_hil_ready', 'hil_testing_ready', 'status')
Index('idx_video_testing_workflow', 'status', 'hil_testing_ready', 'validated_at')
```

#### Detection Event Performance
```python
Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp')
Index('idx_detection_latency_validation', 'latency_ms', 'validation_result') 
Index('idx_detection_session_labjack_validation', 'test_session_id', 'validation_result', 'latency_ms')
```

#### Ground Truth Temporal Queries
```python
Index('idx_gt_video_timestamp', 'video_id', 'timestamp')
Index('idx_gt_video_tracking_id', 'video_id', 'tracking_id')
Index('idx_gt_tracking_timestamp', 'tracking_id', 'timestamp')
```

#### User Security Indexes
```python
Index('idx_auth_user_email_active', 'email', 'is_active')
Index('idx_session_user_active', 'user_id', 'is_active')
Index('idx_project_owner_status', 'owner_id', 'status')
```

## Data Migration and Compatibility

### Legacy Relationship Migration
```python
def migrate_legacy_video_relationships(db: Session) -> int:
    """Migrate videos with direct project_id to VideoProjectLink table"""
    legacy_videos = db.query(Video).filter(Video.project_id.isnot(None)).all()
    
    for video in legacy_videos:
        # Create VideoProjectLink entry
        link = VideoProjectLink(
            video_id=video.id,
            project_id=video.project_id,
            assignment_reason="legacy_migration",
            intelligent_match=False
        )
        db.add(link)
```

### Backward Compatibility Properties
```python
class Video(Base):
    @property
    def uploaded_at(self):
        """Backward compatibility property - maps to created_at"""
        return self.created_at
```

## Data Validation and Business Rules

### Model-Level Validation
```python
class TestSession(Base):
    @validates('latency_threshold_ms')
    def validate_threshold(self, key, threshold):
        if threshold <= 0 or threshold > 10000:  # 0-10s range
            raise ValueError('Latency threshold must be between 1-10000ms')
        return threshold
```

### Database Constraints
```python
# Unique constraints
__table_args__ = (
    Index('idx_video_project_unique', 'video_id', 'project_id', unique=True),
    UniqueConstraint('email', name='uq_auth_user_email'),
    UniqueConstraint('session_token', name='uq_user_session_token')
)
```

## Query Patterns and Optimization

### Efficient Join Patterns
```python
# Get videos with ground truth for user
videos_with_gt = db.query(Video).join(VideoProjectLink).join(Project).filter(
    Project.owner_id == user_id,
    Video.ground_truth_generated == True
).options(joinedload(Video.ground_truth_objects)).all()
```

### Aggregation Queries
```python
# Dashboard statistics with proper joins
project_count = db.query(func.count(Project.id)).filter(Project.owner_id == user_id).scalar()

video_count = db.query(func.count(Video.id.distinct())).join(VideoProjectLink).join(Project).filter(
    Project.owner_id == user_id
).scalar()
```

### Temporal Range Queries
```python
# Detection events in time range
events = db.query(DetectionEvent).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.timestamp.between(start_time, end_time)
).order_by(DetectionEvent.timestamp).all()
```