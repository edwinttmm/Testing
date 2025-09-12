# Database Data Integrity Documentation

## Overview

This document provides a comprehensive analysis of data integrity mechanisms, constraints, validations, and consistency measures implemented in the AI Model Validation Platform database.

## Table of Contents

1. [Data Integrity Principles](#data-integrity-principles)
2. [Constraint Analysis](#constraint-analysis)
3. [Validation Rules](#validation-rules)
4. [Referential Integrity](#referential-integrity)
5. [Business Logic Constraints](#business-logic-constraints)
6. [Data Consistency Mechanisms](#data-consistency-mechanisms)
7. [Integrity Monitoring](#integrity-monitoring)

---

## Data Integrity Principles

### ACID Compliance

The platform maintains strict ACID (Atomicity, Consistency, Isolation, Durability) properties:

**Atomicity:**
- All database operations are wrapped in transactions
- Rollback on any failure ensures all-or-nothing execution
- Batch operations maintain transactional integrity

**Consistency:**
- Foreign key constraints prevent orphaned records
- Check constraints enforce business rules
- Trigger-based validation for complex rules

**Isolation:**
- Read committed isolation level prevents dirty reads
- Row-level locking for concurrent access
- Deadlock detection and resolution

**Durability:**
- Write-ahead logging (WAL) ensures data persistence
- Point-in-time recovery capabilities
- Regular automated backups

### Data Quality Framework

**Four Pillars of Data Quality:**

1. **Accuracy:** Data reflects real-world values correctly
2. **Completeness:** All required data is present
3. **Consistency:** Data follows established formats and rules
4. **Validity:** Data meets defined business requirements

---

## Constraint Analysis

### Primary Key Constraints

**UUID Primary Keys Throughout:**
```sql
-- Consistent pattern across all tables
CREATE TABLE example_table (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Ensures unique identification
    -- Prevents duplicate records
    -- Supports distributed systems
);
```

**Benefits:**
- Guaranteed uniqueness across all instances
- Non-sequential for security (prevents enumeration)
- Compatible with database replication and sharding
- 36-character string format for API consistency

### NOT NULL Constraints

**Critical Fields Protection:**

```sql
-- Authentication table
CREATE TABLE auth_users (
    id VARCHAR(36) PRIMARY KEY NOT NULL,
    email VARCHAR UNIQUE NOT NULL,           -- Required for login
    username VARCHAR UNIQUE NOT NULL,        -- Required for identification  
    hashed_password VARCHAR NOT NULL,        -- Required for authentication
    is_active BOOLEAN NOT NULL DEFAULT TRUE, -- Required for access control
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Project table
CREATE TABLE projects (
    id VARCHAR(36) PRIMARY KEY NOT NULL,
    name VARCHAR NOT NULL,              -- Required for identification
    camera_model VARCHAR NOT NULL,      -- Required for validation context
    camera_view VARCHAR NOT NULL,       -- Required for test configuration
    signal_type VARCHAR NOT NULL,       -- Required for hardware integration
    owner_id VARCHAR(36) NOT NULL DEFAULT 'anonymous' -- Required for security
);
```

**NOT NULL Validation Rules:**

| Table | Required Fields | Business Justification |
|-------|----------------|------------------------|
| auth_users | email, username, hashed_password | Authentication impossible without these |
| projects | name, camera_model, camera_view, signal_type | Test configuration requires complete hardware specification |
| videos | filename, project_id | File identification and project association mandatory |
| test_sessions | name, project_id, video_id | Test execution requires complete context |
| detection_events | test_session_id, timestamp | Event tracking requires session and time context |

### UNIQUE Constraints

**Duplicate Prevention:**

```sql
-- User uniqueness
ALTER TABLE auth_users ADD CONSTRAINT unique_email UNIQUE (email);
ALTER TABLE auth_users ADD CONSTRAINT unique_username UNIQUE (username);

-- Session security
ALTER TABLE user_sessions ADD CONSTRAINT unique_session_token UNIQUE (session_token);

-- Video-project assignment uniqueness
ALTER TABLE video_project_links ADD CONSTRAINT unique_video_project 
    UNIQUE (video_id, project_id);
```

**Compound Uniqueness:**
- Prevents duplicate email registrations
- Ensures session token uniqueness for security
- Prevents duplicate video assignments to same project

### CHECK Constraints (Database-Dependent)

**PostgreSQL Check Constraints:**

```sql
-- Validation score ranges
ALTER TABLE video_validation_results 
ADD CONSTRAINT check_overall_score 
CHECK (overall_score >= 0 AND overall_score <= 100);

-- Latency validation
ALTER TABLE detection_events 
ADD CONSTRAINT check_latency_positive 
CHECK (latency_ms IS NULL OR latency_ms >= 0);

-- Coordinate validation
ALTER TABLE ground_truth_objects 
ADD CONSTRAINT check_coordinates_positive 
CHECK (x >= 0 AND y >= 0 AND width > 0 AND height > 0);
```

---

## Validation Rules

### Application-Level Validation

**Pydantic Schema Validation:**

```python
# Project creation validation
class ProjectCreate(CamelCaseModel):
    name: str = Field(min_length=1, max_length=255)
    camera_view: CameraTypeEnum  # Enum ensures valid values
    signal_type: SignalTypeEnum  # Enum ensures valid values
    frame_rate: Optional[int] = Field(gt=0, le=240)  # Positive, reasonable range
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Project name cannot be empty')
        return v.strip()

# Video validation
class VideoResponse(CamelCaseModel):
    id: str = Field(regex=r'^[0-9a-fA-F-]{36}$')  # UUID format
    status: VideoStatus  # Enum validation
    file_size: Optional[int] = Field(gt=0)  # Positive file sizes only
    duration: Optional[float] = Field(gt=0)  # Positive duration only
    fps: Optional[float] = Field(gt=0, le=240)  # Reasonable FPS range
```

**Email Validation:**
```python
class UserCreate(CamelCaseModel):
    email: EmailStr  # Pydantic email validation
    username: str = Field(min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_-]+$')
    password: str = Field(min_length=8)  # Minimum password length
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain number')
        return v
```

### Database-Level Validation

**Stored Procedure Validation (PostgreSQL):**

```sql
-- Validate video file extension
CREATE OR REPLACE FUNCTION validate_video_filename(filename VARCHAR)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN filename ~* '\.(mp4|avi|mov|mkv|webm)$';
END;
$$ LANGUAGE plpgsql;

-- Trigger for filename validation
CREATE TRIGGER trigger_validate_video_filename
    BEFORE INSERT OR UPDATE ON videos
    FOR EACH ROW
    EXECUTE FUNCTION check_video_filename();

CREATE OR REPLACE FUNCTION check_video_filename()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT validate_video_filename(NEW.filename) THEN
        RAISE EXCEPTION 'Invalid video file extension: %', NEW.filename;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Business Rule Validation

**Status Transition Validation:**

```python
class VideoStatusManager:
    """Validates video status transitions according to business rules"""
    
    VALID_TRANSITIONS = {
        'uploaded': ['processing', 'error'],
        'processing': ['completed', 'error'],  
        'completed': ['validated', 'pending_annotation', 'error'],
        'pending_annotation': ['completed', 'error'],
        'validated': ['hil_ready', 'error'],
        'error': ['uploaded', 'processing']  # Allow retry
    }
    
    @classmethod
    def validate_transition(cls, from_status: str, to_status: str) -> bool:
        """Validate if status transition is allowed"""
        allowed_transitions = cls.VALID_TRANSITIONS.get(from_status, [])
        return to_status in allowed_transitions
    
    @classmethod
    def transition_video_status(cls, db: Session, video_id: str, 
                              new_status: str, user_id: str, reason: str):
        """Safely transition video status with validation"""
        video = get_video(db, video_id, user_id)
        if not video:
            raise ValueError("Video not found")
        
        if not cls.validate_transition(video.status, new_status):
            raise ValueError(f"Invalid transition from {video.status} to {new_status}")
        
        # Record transition
        transition = VideoStatusTransition(
            video_id=video_id,
            from_status=video.status,
            to_status=new_status,
            transition_reason=reason,
            triggered_by=user_id
        )
        db.add(transition)
        
        # Update video status
        video.status = new_status
        video.updated_at = func.now()
        
        db.commit()
```

---

## Referential Integrity

### Foreign Key Relationships

**CASCADE DELETE Relationships:**

```sql
-- User sessions cascade when user is deleted
ALTER TABLE user_sessions 
ADD CONSTRAINT fk_user_sessions_user_id 
FOREIGN KEY (user_id) REFERENCES auth_users(id) ON DELETE CASCADE;

-- Project resources cascade when project is deleted
ALTER TABLE test_sessions 
ADD CONSTRAINT fk_test_sessions_project_id 
FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;

-- Video content cascades when video is deleted
ALTER TABLE ground_truth_objects 
ADD CONSTRAINT fk_ground_truth_video_id 
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE;
```

**SET NULL Relationships:**

```sql
-- Optional ground truth matching
ALTER TABLE detection_events 
ADD CONSTRAINT fk_detection_events_ground_truth_match_id 
FOREIGN KEY (ground_truth_match_id) REFERENCES ground_truth_objects(id) ON DELETE SET NULL;

-- Optional report snapshot references
ALTER TABLE report_snapshots 
ADD CONSTRAINT fk_report_snapshots_video_id 
FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL;
```

### Referential Integrity Matrix

| Parent Table | Child Table | Relationship | On Delete | Justification |
|--------------|-------------|--------------|-----------|---------------|
| auth_users | user_sessions | 1:N | CASCADE | Sessions invalid without user |
| projects | test_sessions | 1:N | CASCADE | Sessions belong to project |
| projects | video_project_links | 1:N | CASCADE | Links invalid without project |
| videos | ground_truth_objects | 1:N | CASCADE | GT belongs to specific video |
| videos | detection_events | 1:N | CASCADE | Events belong to specific video |
| test_sessions | detection_events | 1:N | CASCADE | Events belong to test session |
| ground_truth_objects | detection_events | N:1 | SET NULL | GT matching is optional |
| test_sessions | test_results | 1:N | CASCADE | Results belong to session |

### Integrity Validation Functions

**Orphan Record Detection:**

```python
def find_orphaned_records(db: Session) -> Dict[str, int]:
    """Find orphaned records that violate referential integrity"""
    orphans = {}
    
    # Find videos without valid project links
    orphaned_videos = db.query(Video).outerjoin(VideoProjectLink).filter(
        VideoProjectLink.video_id.is_(None)
    ).count()
    orphans['orphaned_videos'] = orphaned_videos
    
    # Find detection events without sessions
    orphaned_detections = db.query(DetectionEvent).outerjoin(TestSession).filter(
        TestSession.id.is_(None)
    ).count()
    orphans['orphaned_detections'] = orphaned_detections
    
    # Find sessions without projects
    orphaned_sessions = db.query(TestSession).outerjoin(Project).filter(
        Project.id.is_(None)
    ).count()
    orphans['orphaned_sessions'] = orphaned_sessions
    
    return orphans

def validate_referential_integrity(db: Session) -> Dict[str, bool]:
    """Comprehensive referential integrity validation"""
    results = {}
    
    # Check all foreign key relationships
    integrity_checks = [
        ("user_sessions -> auth_users", "SELECT COUNT(*) FROM user_sessions us LEFT JOIN auth_users au ON us.user_id = au.id WHERE au.id IS NULL"),
        ("test_sessions -> projects", "SELECT COUNT(*) FROM test_sessions ts LEFT JOIN projects p ON ts.project_id = p.id WHERE p.id IS NULL"),
        ("detection_events -> test_sessions", "SELECT COUNT(*) FROM detection_events de LEFT JOIN test_sessions ts ON de.test_session_id = ts.id WHERE ts.id IS NULL"),
    ]
    
    for check_name, query in integrity_checks:
        orphan_count = db.execute(text(query)).scalar()
        results[check_name] = orphan_count == 0
    
    return results
```

---

## Business Logic Constraints

### Domain-Specific Validation Rules

#### Video Validation Constraints

```python
class VideoValidator:
    """Business logic validation for video files"""
    
    SUPPORTED_FORMATS = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    MIN_DURATION = 1.0  # 1 second
    MAX_DURATION = 3600.0  # 1 hour
    MIN_RESOLUTION = (640, 480)
    
    @classmethod
    def validate_video_file(cls, video_data: Dict) -> List[str]:
        """Comprehensive video validation"""
        errors = []
        
        # File format validation
        if not any(video_data['filename'].lower().endswith(fmt) 
                  for fmt in cls.SUPPORTED_FORMATS):
            errors.append(f"Unsupported format. Allowed: {cls.SUPPORTED_FORMATS}")
        
        # File size validation
        if video_data.get('file_size', 0) > cls.MAX_FILE_SIZE:
            errors.append(f"File too large. Maximum: {cls.MAX_FILE_SIZE / 1024 / 1024}MB")
        
        # Duration validation
        duration = video_data.get('duration', 0)
        if duration and (duration < cls.MIN_DURATION or duration > cls.MAX_DURATION):
            errors.append(f"Invalid duration. Must be {cls.MIN_DURATION}-{cls.MAX_DURATION} seconds")
        
        # Resolution validation
        resolution = video_data.get('resolution')
        if resolution:
            try:
                width, height = map(int, resolution.split('x'))
                if width < cls.MIN_RESOLUTION[0] or height < cls.MIN_RESOLUTION[1]:
                    errors.append(f"Resolution too low. Minimum: {cls.MIN_RESOLUTION[0]}x{cls.MIN_RESOLUTION[1]}")
            except (ValueError, AttributeError):
                errors.append("Invalid resolution format. Use 'WIDTHxHEIGHT'")
        
        return errors
```

#### Test Session Validation

```python
class TestSessionValidator:
    """Validation rules for test execution"""
    
    @classmethod
    def validate_session_creation(cls, db: Session, session_data: Dict, user_id: str) -> List[str]:
        """Validate test session creation"""
        errors = []
        
        # Verify user owns the project
        project = get_project(db, session_data['project_id'], user_id)
        if not project:
            errors.append("Project not found or access denied")
            return errors
        
        # Verify video belongs to project
        video_link = db.query(VideoProjectLink).filter(
            VideoProjectLink.project_id == session_data['project_id'],
            VideoProjectLink.video_id == session_data['video_id']
        ).first()
        if not video_link:
            errors.append("Video not assigned to this project")
        
        # Verify video is ready for testing
        video = get_video(db, session_data['video_id'], user_id)
        if video and video.status != 'validated':
            errors.append(f"Video not ready for testing. Current status: {video.status}")
        
        # Validate tolerance range
        tolerance = session_data.get('tolerance_ms', 100)
        if tolerance < 1 or tolerance > 10000:
            errors.append("Tolerance must be between 1-10000 milliseconds")
        
        return errors
```

#### Ground Truth Validation

```python
class GroundTruthValidator:
    """Validation for ground truth annotations"""
    
    VALID_VRU_TYPES = ['pedestrian', 'cyclist', 'motorcyclist', 'wheelchair', 'scooter']
    MIN_CONFIDENCE = 0.0
    MAX_CONFIDENCE = 1.0
    
    @classmethod
    def validate_annotation(cls, annotation_data: Dict) -> List[str]:
        """Validate ground truth annotation"""
        errors = []
        
        # VRU type validation
        vru_type = annotation_data.get('vru_type', '').lower()
        if vru_type not in cls.VALID_VRU_TYPES:
            errors.append(f"Invalid VRU type. Allowed: {cls.VALID_VRU_TYPES}")
        
        # Confidence validation
        confidence = annotation_data.get('confidence', 0)
        if not (cls.MIN_CONFIDENCE <= confidence <= cls.MAX_CONFIDENCE):
            errors.append(f"Confidence must be between {cls.MIN_CONFIDENCE} and {cls.MAX_CONFIDENCE}")
        
        # Bounding box validation
        bbox = annotation_data.get('bounding_box', {})
        if bbox:
            required_keys = ['x', 'y', 'width', 'height']
            missing_keys = [key for key in required_keys if key not in bbox]
            if missing_keys:
                errors.append(f"Missing bounding box keys: {missing_keys}")
            
            # Validate positive dimensions
            if bbox.get('width', 0) <= 0 or bbox.get('height', 0) <= 0:
                errors.append("Bounding box width and height must be positive")
        
        # Temporal validation
        timestamp = annotation_data.get('timestamp', 0)
        if timestamp < 0:
            errors.append("Timestamp cannot be negative")
        
        return errors
```

---

## Data Consistency Mechanisms

### Transaction Management

**Atomic Operations:**

```python
class DatabaseTransaction:
    """Context manager for atomic database operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.savepoint = None
    
    def __enter__(self):
        self.savepoint = self.db.begin_nested()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.savepoint.rollback()
        else:
            self.savepoint.commit()

# Usage example
def create_test_session_with_detection_events(
    db: Session, 
    session_data: Dict, 
    events: List[Dict]
) -> TestSession:
    """Atomically create session and events"""
    
    with DatabaseTransaction(db):
        # Create session
        session = TestSession(**session_data)
        db.add(session)
        db.flush()  # Get ID without committing
        
        # Create all detection events
        for event_data in events:
            event = DetectionEvent(
                test_session_id=session.id,
                **event_data
            )
            db.add(event)
        
        # Calculate and store results
        results = calculate_session_results(events)
        test_result = TestResult(
            test_session_id=session.id,
            **results
        )
        db.add(test_result)
    
    return session
```

### Data Synchronization

**Multi-Table Consistency:**

```python
def update_video_ground_truth_stats(db: Session, video_id: str):
    """Keep video ground truth statistics in sync"""
    
    # Calculate current statistics
    stats = db.query(
        func.count(GroundTruthObject.id).label('count'),
        func.avg(GroundTruthObject.confidence).label('avg_confidence'),
        func.min(GroundTruthObject.timestamp).label('first_detection'),
        func.max(GroundTruthObject.timestamp).label('last_detection')
    ).filter(GroundTruthObject.video_id == video_id).first()
    
    # Update video record atomically
    with DatabaseTransaction(db):
        video = db.query(Video).filter(Video.id == video_id).first()
        if video:
            video.ground_truth_count = stats.count or 0
            video.ground_truth_quality_score = stats.avg_confidence
            video.ground_truth_completed_at = func.now() if stats.count > 0 else None
            video.updated_at = func.now()

def synchronize_test_results(db: Session, session_id: str):
    """Synchronize test results with detection events"""
    
    # Calculate comprehensive statistics
    detection_stats = db.query(
        func.count(DetectionEvent.id).label('total'),
        func.sum(case([(DetectionEvent.validation_result == 'Pass', 1)], else_=0)).label('passed'),
        func.avg(DetectionEvent.latency_ms).label('avg_latency'),
        func.min(DetectionEvent.latency_ms).label('min_latency'),
        func.max(DetectionEvent.latency_ms).label('max_latency'),
        func.percentile_cont(0.5).within_group(DetectionEvent.latency_ms).label('median_latency'),
        func.stddev(DetectionEvent.latency_ms).label('std_dev_latency')
    ).filter(DetectionEvent.test_session_id == session_id).first()
    
    # Update test results atomically
    with DatabaseTransaction(db):
        result = db.query(TestResult).filter(
            TestResult.test_session_id == session_id
        ).first()
        
        if not result:
            result = TestResult(test_session_id=session_id)
            db.add(result)
        
        # Update all calculated fields
        result.total_detections = detection_stats.total or 0
        result.passed_detections = detection_stats.passed or 0
        result.failed_detections = (detection_stats.total or 0) - (detection_stats.passed or 0)
        result.pass_rate = (detection_stats.passed / detection_stats.total * 100) if detection_stats.total > 0 else 0
        result.avg_latency_ms = detection_stats.avg_latency
        result.min_latency_ms = detection_stats.min_latency
        result.max_latency_ms = detection_stats.max_latency
        result.median_latency_ms = detection_stats.median_latency
        result.std_dev_latency_ms = detection_stats.std_dev_latency
```

### Consistency Validation

**Data Consistency Checks:**

```python
def validate_data_consistency(db: Session) -> Dict[str, bool]:
    """Comprehensive data consistency validation"""
    results = {}
    
    # Video ground truth count consistency
    gt_count_check = db.execute(text("""
        SELECT COUNT(*) FROM videos v
        WHERE v.ground_truth_count != (
            SELECT COUNT(*) FROM ground_truth_objects gt 
            WHERE gt.video_id = v.id
        )
    """)).scalar()
    results['ground_truth_counts_consistent'] = gt_count_check == 0
    
    # Test result calculation consistency  
    test_result_check = db.execute(text("""
        SELECT COUNT(*) FROM test_results tr
        WHERE tr.total_detections != (
            SELECT COUNT(*) FROM detection_events de 
            WHERE de.test_session_id = tr.test_session_id
        )
    """)).scalar()
    results['test_result_counts_consistent'] = test_result_check == 0
    
    # Video project link consistency
    link_consistency_check = db.execute(text("""
        SELECT COUNT(*) FROM videos v
        WHERE v.project_id IS NOT NULL 
        AND NOT EXISTS (
            SELECT 1 FROM video_project_links vpl 
            WHERE vpl.video_id = v.id AND vpl.project_id = v.project_id
        )
    """)).scalar()
    results['video_project_links_consistent'] = link_consistency_check == 0
    
    return results
```

---

## Integrity Monitoring

### Automated Integrity Checks

**Scheduled Validation:**

```python
import schedule
import time
from datetime import datetime, timedelta

class IntegrityMonitor:
    """Automated database integrity monitoring"""
    
    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.setup_monitoring_schedule()
    
    def setup_monitoring_schedule(self):
        """Setup automated integrity checking schedule"""
        # Daily comprehensive checks
        schedule.every().day.at("02:00").do(self.run_comprehensive_check)
        
        # Hourly critical checks
        schedule.every().hour.do(self.run_critical_checks)
        
        # Real-time monitoring for high-frequency operations
        schedule.every(5).minutes.do(self.check_recent_data)
    
    def run_comprehensive_check(self):
        """Daily comprehensive integrity validation"""
        db = self.db_session_factory()
        try:
            results = {
                'timestamp': datetime.now().isoformat(),
                'referential_integrity': validate_referential_integrity(db),
                'data_consistency': validate_data_consistency(db),
                'orphaned_records': find_orphaned_records(db),
                'constraint_violations': self.check_constraint_violations(db)
            }
            
            # Log results and alert if issues found
            self.log_integrity_results(results)
            if self.has_integrity_issues(results):
                self.send_integrity_alert(results)
            
        finally:
            db.close()
    
    def check_constraint_violations(self, db: Session) -> Dict[str, int]:
        """Check for constraint violations"""
        violations = {}
        
        # Check NOT NULL violations (shouldn't exist but good to verify)
        null_checks = {
            'users_without_email': "SELECT COUNT(*) FROM auth_users WHERE email IS NULL",
            'projects_without_name': "SELECT COUNT(*) FROM projects WHERE name IS NULL",
            'videos_without_filename': "SELECT COUNT(*) FROM videos WHERE filename IS NULL",
        }
        
        for check_name, query in null_checks.items():
            count = db.execute(text(query)).scalar()
            violations[check_name] = count
        
        return violations
    
    def has_integrity_issues(self, results: Dict) -> bool:
        """Determine if integrity issues exist"""
        # Check referential integrity
        for check, passed in results['referential_integrity'].items():
            if not passed:
                return True
        
        # Check data consistency
        for check, passed in results['data_consistency'].items():
            if not passed:
                return True
        
        # Check orphaned records
        for table, count in results['orphaned_records'].items():
            if count > 0:
                return True
        
        # Check constraint violations
        for violation, count in results['constraint_violations'].items():
            if count > 0:
                return True
        
        return False
```

### Performance Impact Monitoring

**Constraint Performance Analysis:**

```sql
-- Monitor constraint check performance
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE tablename IN ('auth_users', 'projects', 'videos', 'detection_events')
ORDER BY tablename, attname;

-- Foreign key constraint performance
SELECT 
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    rc.update_rule,
    rc.delete_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu 
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc 
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public'
ORDER BY tc.table_name;
```

### Integrity Repair Procedures

**Automated Repair Functions:**

```python
def repair_orphaned_records(db: Session) -> Dict[str, int]:
    """Repair orphaned records where possible"""
    repair_results = {}
    
    # Remove orphaned detection events
    orphaned_events = db.query(DetectionEvent).outerjoin(TestSession).filter(
        TestSession.id.is_(None)
    ).delete(synchronize_session=False)
    repair_results['removed_orphaned_events'] = orphaned_events
    
    # Remove orphaned user sessions
    orphaned_sessions = db.query(UserSession).outerjoin(AuthUser).filter(
        AuthUser.id.is_(None)
    ).delete(synchronize_session=False)
    repair_results['removed_orphaned_sessions'] = orphaned_sessions
    
    # Repair inconsistent ground truth counts
    videos_with_wrong_counts = db.execute(text("""
        UPDATE videos 
        SET ground_truth_count = (
            SELECT COUNT(*) FROM ground_truth_objects 
            WHERE ground_truth_objects.video_id = videos.id
        ),
        updated_at = NOW()
        WHERE ground_truth_count != (
            SELECT COUNT(*) FROM ground_truth_objects 
            WHERE ground_truth_objects.video_id = videos.id
        )
    """)).rowcount
    repair_results['repaired_ground_truth_counts'] = videos_with_wrong_counts
    
    db.commit()
    return repair_results

def rebuild_test_result_statistics(db: Session, session_id: str = None):
    """Rebuild test result statistics from detection events"""
    
    if session_id:
        sessions_to_rebuild = [session_id]
    else:
        # Rebuild all sessions with inconsistent results
        sessions_to_rebuild = db.execute(text("""
            SELECT DISTINCT tr.test_session_id 
            FROM test_results tr
            WHERE tr.total_detections != (
                SELECT COUNT(*) FROM detection_events de 
                WHERE de.test_session_id = tr.test_session_id
            )
        """)).scalars().all()
    
    rebuilt_count = 0
    for session_id in sessions_to_rebuild:
        synchronize_test_results(db, session_id)
        rebuilt_count += 1
    
    db.commit()
    return rebuilt_count
```

This comprehensive data integrity documentation ensures the AI Model Validation Platform maintains the highest standards of data quality, consistency, and reliability throughout its operations.