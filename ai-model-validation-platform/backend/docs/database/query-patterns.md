# Database Query Patterns Documentation

## Overview

This document provides a comprehensive analysis of all CRUD operations and query patterns used throughout the AI Model Validation Platform's database layer.

## Table of Contents

1. [CRUD Operations Analysis](#crud-operations-analysis)
2. [Common Query Patterns](#common-query-patterns)
3. [Performance-Critical Queries](#performance-critical-queries)
4. [Security Patterns](#security-patterns)
5. [Complex Join Operations](#complex-join-operations)
6. [Query Optimization Examples](#query-optimization-examples)

---

## CRUD Operations Analysis

### Authentication Operations

#### User Creation and Authentication

**Create User (Security-First):**
```python
def create_user(db: Session, user: UserCreate) -> AuthUser:
    """Create new user with hashed password"""
    db_user = AuthUser(
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        hashed_password=AuthUser.get_password_hash(user.password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Generated SQL:
# INSERT INTO auth_users (id, email, username, full_name, hashed_password, 
#                        is_active, is_superuser, is_verified, created_at)
# VALUES (uuid4(), %s, %s, %s, %s, TRUE, FALSE, FALSE, now())
```

**User Authentication Query:**
```python
def authenticate_user(db: Session, email: str, password: str) -> Optional[AuthUser]:
    """Authenticate user with email and password"""
    user = db.query(AuthUser).filter(
        AuthUser.email == email,
        AuthUser.is_active == True
    ).first()
    
    if user and user.verify_password(password):
        # Update last login
        user.last_login = func.now()
        db.commit()
        return user
    return None

# Optimized SQL (uses composite index):
# SELECT * FROM auth_users 
# WHERE email = %s AND is_active = TRUE
# LIMIT 1
```

#### Session Management Queries

**Active Session Retrieval:**
```python
def get_active_session(db: Session, token: str) -> Optional[UserSession]:
    """Get active session by token"""
    return db.query(UserSession).filter(
        UserSession.session_token == token,
        UserSession.is_active == True,
        UserSession.expires_at > func.now()
    ).first()

# Uses composite index: idx_session_token_active
# SELECT * FROM user_sessions 
# WHERE session_token = %s AND is_active = TRUE AND expires_at > now()
```

**Session Cleanup (Maintenance):**
```python
def cleanup_expired_sessions(db: Session) -> int:
    """Remove expired sessions"""
    expired_count = db.query(UserSession).filter(
        UserSession.expires_at < func.now()
    ).delete(synchronize_session=False)
    db.commit()
    return expired_count

# Uses index: idx_session_cleanup (expires_at, is_active)
# DELETE FROM user_sessions WHERE expires_at < now()
```

### Project Management Operations

#### Project CRUD with User Security

**Create Project (User-Scoped):**
```python
def create_project(db: Session, project: ProjectCreate, user_id: str) -> Project:
    """Create project with user ownership"""
    db_project = Project(
        **project.model_dump(),
        owner_id=user_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project
```

**User-Filtered Project Listing:**
```python
def get_projects(db: Session, user_id: str, skip: int = 0, limit: int = 100) -> List[Project]:
    """Get user's projects with pagination"""
    return db.query(Project).filter(
        Project.owner_id == user_id
    ).offset(skip).limit(limit).all()

# Uses index: ix_projects_owner_id
# SELECT * FROM projects WHERE owner_id = %s OFFSET %s LIMIT %s
```

**Project with Video Count (Analytics):**
```python
def get_project_with_stats(db: Session, project_id: str, user_id: str) -> Dict:
    """Get project with video statistics"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner_id == user_id
    ).first()
    
    if not project:
        return None
    
    # Get video count via junction table
    video_count = db.query(func.count(VideoProjectLink.video_id)).filter(
        VideoProjectLink.project_id == project_id
    ).scalar()
    
    return {
        "project": project,
        "video_count": video_count
    }
```

### Video Management Operations

#### Many-to-Many Video-Project Assignment

**Create Video with Project Assignment:**
```python
def create_video(db: Session, filename: str, project_ids: List[str]) -> Video:
    """Create video and assign to multiple projects"""
    primary_project_id = project_ids[0]
    
    db_video = Video(
        filename=filename,
        project_id=primary_project_id  # Legacy constraint
    )
    db.add(db_video)
    db.flush()  # Get ID without committing
    
    # Create junction table entries
    for project_id in project_ids:
        link = VideoProjectLink(
            video_id=db_video.id,
            project_id=project_id,
            assignment_reason="initial_upload"
        )
        db.add(link)
    
    db.commit()
    db.refresh(db_video)
    return db_video
```

**Get Project Videos (Junction Table):**
```python
def get_project_videos(db: Session, project_id: str, user_id: str) -> List[Video]:
    """Get videos assigned to project with security check"""
    return db.query(Video).join(VideoProjectLink).join(Project).filter(
        VideoProjectLink.project_id == project_id,
        Project.owner_id == user_id
    ).all()

# Generated SQL with joins:
# SELECT videos.* FROM videos 
# JOIN video_project_links ON videos.id = video_project_links.video_id
# JOIN projects ON video_project_links.project_id = projects.id
# WHERE video_project_links.project_id = %s AND projects.owner_id = %s
```

**Video Access Security Pattern:**
```python
def get_video(db: Session, video_id: str, user_id: str) -> Optional[Video]:
    """Get video with user access verification"""
    return db.query(Video).join(VideoProjectLink).join(Project).filter(
        Video.id == video_id,
        Project.owner_id == user_id
    ).first()

# Security through joins ensures user can only access their videos
```

### Ground Truth and Detection Operations

#### Ground Truth Creation with Spatial Data

**Create Ground Truth Object:**
```python
def create_ground_truth_object(
    db: Session, 
    video_id: str, 
    timestamp: float,
    class_label: str, 
    x: float, y: float, 
    width: float, height: float,
    confidence: float = 1.0,
    frame_number: int = None
) -> GroundTruthObject:
    """Create ground truth with individual coordinates"""
    
    db_object = GroundTruthObject(
        video_id=video_id,
        timestamp=timestamp,
        class_label=class_label,
        x=x, y=y, width=width, height=height,
        confidence=confidence,
        frame_number=frame_number,
        validated=True  # Ground truth is validated by definition
    )
    db.add(db_object)
    db.commit()
    db.refresh(db_object)
    return db_object
```

**Temporal Ground Truth Queries:**
```python
def get_ground_truth_in_timerange(
    db: Session, 
    video_id: str, 
    start_time: float, 
    end_time: float
) -> List[GroundTruthObject]:
    """Get ground truth objects within time range"""
    return db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id == video_id,
        GroundTruthObject.timestamp >= start_time,
        GroundTruthObject.timestamp <= end_time
    ).order_by(GroundTruthObject.timestamp).all()

# Uses composite index: idx_gt_video_timestamp
```

#### Detection Event Storage (LabJack Integration)

**Create Detection Event with LabJack Timing:**
```python
def create_detection_event_labjack(
    db: Session,
    test_session_id: str,
    video_id: str,
    timestamp: float,
    labjack_timestamp: float,
    video_start_time: float,
    threshold_ms: int
) -> DetectionEvent:
    """Create detection event with LabJack timing validation"""
    
    # Calculate latency
    latency_ms = (timestamp - labjack_timestamp) * 1000
    
    # Determine validation result
    validation_result = "Pass" if latency_ms <= threshold_ms else "Fail"
    
    db_event = DetectionEvent(
        test_session_id=test_session_id,
        video_id=video_id,
        timestamp=timestamp,
        labjack_timestamp=labjack_timestamp,
        video_start_time=video_start_time,
        latency_ms=latency_ms,
        latency_threshold_ms=threshold_ms,
        validation_result=validation_result,
        source='labjack'
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event
```

### Test Execution Queries

#### Test Session with Statistics

**Get Test Session Results:**
```python
def get_test_session_with_results(db: Session, session_id: str) -> Dict:
    """Get test session with comprehensive statistics"""
    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session:
        return None
    
    # Get detection statistics
    detection_stats = db.query(
        func.count(DetectionEvent.id).label('total_detections'),
        func.count(case([(DetectionEvent.validation_result == 'Pass', 1)])).label('passed'),
        func.count(case([(DetectionEvent.validation_result == 'Fail', 1)])).label('failed'),
        func.avg(DetectionEvent.latency_ms).label('avg_latency'),
        func.min(DetectionEvent.latency_ms).label('min_latency'),
        func.max(DetectionEvent.latency_ms).label('max_latency')
    ).filter(DetectionEvent.test_session_id == session_id).first()
    
    return {
        "session": session,
        "statistics": detection_stats._asdict()
    }

# Uses composite index: idx_detection_session_validation
```

---

## Common Query Patterns

### 1. User-Scoped Resource Access

**Pattern:** All user data access goes through ownership verification

```python
# Template for user-scoped queries
def get_user_resource(db: Session, resource_id: str, user_id: str):
    return db.query(Resource).join(Project).filter(
        Resource.id == resource_id,
        Project.owner_id == user_id
    ).first()
```

**Applied Examples:**
- Videos: `video → project → owner_id`
- Test Sessions: `test_session → project → owner_id`
- Detection Events: `detection_event → test_session → project → owner_id`
- Ground Truth: `ground_truth → video → project → owner_id`

### 2. Temporal Range Queries

**Pattern:** Time-based filtering with proper indexing

```python
def get_events_in_range(db: Session, start_time: datetime, end_time: datetime):
    return db.query(Event).filter(
        Event.created_at >= start_time,
        Event.created_at <= end_time
    ).order_by(Event.created_at).all()
```

**Performance Optimization:**
- Uses time-based indexes (`created_at`, `timestamp`)
- Proper ordering for time-series analysis
- Range queries optimized with BETWEEN operations

### 3. Status Workflow Queries

**Pattern:** Multi-status filtering with state transitions

```python
def get_videos_by_workflow_status(db: Session, project_id: str, statuses: List[str]):
    return db.query(Video).join(VideoProjectLink).filter(
        VideoProjectLink.project_id == project_id,
        Video.status.in_(statuses)
    ).all()
```

**Status Combinations:**
- Ready for testing: `status='validated' AND hil_testing_ready=True`
- Needs annotation: `status='completed' AND validation_status='pending'`
- In progress: `status IN ('processing', 'pending_annotation')`

### 4. Aggregation and Analytics Queries

**Pattern:** Statistical analysis with grouping

```python
def get_project_analytics(db: Session, project_id: str) -> Dict:
    """Get comprehensive project analytics"""
    
    # Video status distribution
    video_status_stats = db.query(
        Video.status,
        func.count(Video.id).label('count')
    ).join(VideoProjectLink).filter(
        VideoProjectLink.project_id == project_id
    ).group_by(Video.status).all()
    
    # Test session performance
    test_performance = db.query(
        func.count(TestSession.id).label('total_sessions'),
        func.avg(TestResult.pass_rate).label('avg_pass_rate'),
        func.sum(TestResult.total_detections).label('total_detections')
    ).join(TestResult).filter(
        TestSession.project_id == project_id
    ).first()
    
    return {
        "video_status_distribution": dict(video_status_stats),
        "test_performance": test_performance._asdict()
    }
```

### 5. Complex Join Patterns

**Multi-Level Joins for Deep Relationships:**
```python
def get_detection_with_ground_truth(db: Session, session_id: str):
    """Get detection events with matched ground truth"""
    return db.query(
        DetectionEvent,
        GroundTruthObject
    ).outerjoin(
        GroundTruthObject,
        DetectionEvent.ground_truth_match_id == GroundTruthObject.id
    ).join(
        TestSession,
        DetectionEvent.test_session_id == TestSession.id
    ).join(
        Video,
        TestSession.video_id == Video.id
    ).filter(
        TestSession.id == session_id
    ).all()
```

---

## Performance-Critical Queries

### 1. Real-Time Detection Processing

**High-Frequency Insert Operations:**
```python
def batch_insert_detections(db: Session, events: List[DetectionEventCreate]):
    """Batch insert detection events for performance"""
    db_events = [
        DetectionEvent(**event.model_dump()) 
        for event in events
    ]
    db.add_all(db_events)
    db.commit()
    return len(db_events)

# Optimizations:
# - Batch operations instead of individual inserts
# - Uses bulk insert when possible
# - Minimal object creation overhead
```

**Real-Time Statistics Updates:**
```python
def update_test_results_realtime(db: Session, session_id: str):
    """Update test results with latest detection statistics"""
    
    # Single query to get all statistics
    stats = db.query(
        func.count(DetectionEvent.id).label('total'),
        func.sum(case([(DetectionEvent.validation_result == 'Pass', 1)], else_=0)).label('passed'),
        func.avg(DetectionEvent.latency_ms).label('avg_latency'),
        func.min(DetectionEvent.latency_ms).label('min_latency'),
        func.max(DetectionEvent.latency_ms).label('max_latency'),
        func.percentile_cont(0.5).within_group(DetectionEvent.latency_ms).label('median_latency')
    ).filter(DetectionEvent.test_session_id == session_id).first()
    
    # Update test results in single operation
    db.query(TestResult).filter(
        TestResult.test_session_id == session_id
    ).update({
        'total_detections': stats.total,
        'passed_detections': stats.passed,
        'failed_detections': stats.total - stats.passed,
        'pass_rate': (stats.passed / stats.total * 100) if stats.total > 0 else 0,
        'avg_latency_ms': stats.avg_latency,
        'min_latency_ms': stats.min_latency,
        'max_latency_ms': stats.max_latency,
        'median_latency_ms': stats.median_latency
    })
    db.commit()
```

### 2. Dashboard Analytics Queries

**Dashboard Statistics (Optimized):**
```python
def get_dashboard_stats_optimized(db: Session, user_id: str) -> Dict:
    """Optimized dashboard statistics with single query per metric"""
    
    # Get all counts in parallel queries
    from sqlalchemy import text
    
    stats_query = text("""
        WITH user_projects AS (
            SELECT id FROM projects WHERE owner_id = :user_id
        ),
        user_videos AS (
            SELECT DISTINCT v.id 
            FROM videos v 
            JOIN video_project_links vpl ON v.id = vpl.video_id
            JOIN user_projects up ON vpl.project_id = up.id
        )
        SELECT 
            (SELECT COUNT(*) FROM user_projects) as project_count,
            (SELECT COUNT(*) FROM user_videos) as video_count,
            (SELECT COUNT(*) FROM test_sessions ts JOIN user_projects up ON ts.project_id = up.id) as test_count,
            (SELECT COUNT(*) FROM detection_events de JOIN test_sessions ts ON de.test_session_id = ts.id JOIN user_projects up ON ts.project_id = up.id) as detection_count
    """)
    
    result = db.execute(stats_query, {"user_id": user_id}).first()
    
    return {
        "project_count": result.project_count,
        "video_count": result.video_count,
        "test_session_count": result.test_count,
        "detection_event_count": result.detection_count
    }
```

### 3. Report Generation Queries

**Comprehensive Report Data:**
```python
def get_report_data(db: Session, session_id: str) -> Dict:
    """Get all data needed for report generation"""
    
    # Main session data
    session = db.query(TestSession).options(
        joinedload(TestSession.project),
        joinedload(TestSession.results)
    ).filter(TestSession.id == session_id).first()
    
    # Detection events with pagination for large datasets
    events_query = db.query(DetectionEvent).filter(
        DetectionEvent.test_session_id == session_id
    ).order_by(DetectionEvent.timestamp)
    
    # Get failure events for snapshots
    failure_events = events_query.filter(
        DetectionEvent.validation_result == 'Fail'
    ).all()
    
    # Get success summary
    success_summary = db.query(
        func.count(DetectionEvent.id).label('count'),
        func.avg(DetectionEvent.latency_ms).label('avg_latency'),
        DetectionEvent.vru_type,
    ).filter(
        DetectionEvent.test_session_id == session_id,
        DetectionEvent.validation_result == 'Pass'
    ).group_by(DetectionEvent.vru_type).all()
    
    return {
        "session": session,
        "failure_events": failure_events,
        "success_summary": [s._asdict() for s in success_summary]
    }
```

---

## Security Patterns

### 1. User Isolation

**Principle:** Every query must verify user ownership

```python
def secure_query_pattern(db: Session, resource_id: str, user_id: str):
    """Template for secure resource access"""
    
    # Method 1: Direct ownership check
    resource = db.query(Resource).filter(
        Resource.id == resource_id,
        Resource.owner_id == user_id
    ).first()
    
    # Method 2: Through project ownership
    resource = db.query(Resource).join(Project).filter(
        Resource.id == resource_id,
        Project.owner_id == user_id
    ).first()
    
    # Method 3: Through junction table
    resource = db.query(Resource).join(Junction).join(Project).filter(
        Resource.id == resource_id,
        Project.owner_id == user_id
    ).first()
    
    return resource
```

### 2. Input Validation Patterns

**SQL Injection Prevention:**
```python
# ✅ SAFE: Parameterized queries
def safe_search(db: Session, search_term: str, user_id: str):
    return db.query(Video).join(VideoProjectLink).join(Project).filter(
        Video.filename.ilike(f"%{search_term}%"),  # SQLAlchemy handles escaping
        Project.owner_id == user_id
    ).all()

# ❌ DANGEROUS: String concatenation (never used in codebase)
# query = f"SELECT * FROM videos WHERE filename LIKE '%{search_term}%'"
```

**Data Type Validation:**
```python
def validate_and_query(db: Session, video_id: str, user_id: str):
    """Validate UUID format before querying"""
    try:
        # Validate UUID format
        uuid.UUID(video_id)
        uuid.UUID(user_id)
    except ValueError:
        raise ValueError("Invalid UUID format")
    
    return db.query(Video).join(VideoProjectLink).join(Project).filter(
        Video.id == video_id,
        Project.owner_id == user_id
    ).first()
```

### 3. Session Security

**Session Validation Pattern:**
```python
def validate_session(db: Session, token: str) -> Optional[AuthUser]:
    """Comprehensive session validation"""
    
    session = db.query(UserSession).filter(
        UserSession.session_token == token,
        UserSession.is_active == True,
        UserSession.expires_at > func.now()
    ).first()
    
    if not session:
        return None
    
    # Update last activity
    session.last_activity = func.now()
    db.commit()
    
    return session.user
```

---

## Complex Join Operations

### 1. Multi-Level Security Joins

**Video Access Through Project Ownership:**
```sql
-- Generated SQL for video access verification
SELECT videos.* 
FROM videos 
JOIN video_project_links ON videos.id = video_project_links.video_id
JOIN projects ON video_project_links.project_id = projects.id 
WHERE videos.id = %s AND projects.owner_id = %s
```

**Detection Event Access Chain:**
```sql
-- Access detection events through ownership chain
SELECT detection_events.* 
FROM detection_events 
JOIN test_sessions ON detection_events.test_session_id = test_sessions.id
JOIN projects ON test_sessions.project_id = projects.id
WHERE detection_events.id = %s AND projects.owner_id = %s
```

### 2. Analytics Joins

**Cross-Table Performance Metrics:**
```python
def get_performance_metrics(db: Session, project_id: str):
    """Complex analytics query across multiple tables"""
    
    return db.query(
        Video.id.label('video_id'),
        Video.filename,
        func.count(DetectionEvent.id).label('total_detections'),
        func.avg(DetectionEvent.latency_ms).label('avg_latency'),
        func.count(case([(DetectionEvent.validation_result == 'Pass', 1)])).label('passed'),
        func.count(GroundTruthObject.id).label('ground_truth_count')
    ).select_from(Video)\
     .join(VideoProjectLink)\
     .outerjoin(TestSession, Video.id == TestSession.video_id)\
     .outerjoin(DetectionEvent, TestSession.id == DetectionEvent.test_session_id)\
     .outerjoin(GroundTruthObject, Video.id == GroundTruthObject.video_id)\
     .filter(VideoProjectLink.project_id == project_id)\
     .group_by(Video.id, Video.filename)\
     .all()
```

### 3. Temporal Correlation Joins

**Detection-Ground Truth Matching:**
```python
def find_temporal_matches(db: Session, video_id: str, tolerance_ms: int = 100):
    """Find detection events that match ground truth temporally"""
    
    tolerance_seconds = tolerance_ms / 1000.0
    
    return db.query(
        DetectionEvent,
        GroundTruthObject,
        func.abs(DetectionEvent.timestamp - GroundTruthObject.timestamp).label('time_diff')
    ).join(
        TestSession, DetectionEvent.test_session_id == TestSession.id
    ).join(
        GroundTruthObject, 
        and_(
            TestSession.video_id == GroundTruthObject.video_id,
            func.abs(DetectionEvent.timestamp - GroundTruthObject.timestamp) <= tolerance_seconds
        )
    ).filter(
        TestSession.video_id == video_id
    ).order_by('time_diff').all()
```

---

## Query Optimization Examples

### 1. Index Usage Optimization

**Before Optimization:**
```python
# Slow: Full table scan
def get_recent_videos_slow(db: Session, days: int = 7):
    cutoff_date = datetime.now() - timedelta(days=days)
    return db.query(Video).filter(
        Video.created_at > cutoff_date
    ).all()

# No index on created_at -> Full table scan
```

**After Optimization:**
```python
# Fast: Uses index
def get_recent_videos_fast(db: Session, days: int = 7):
    cutoff_date = datetime.now() - timedelta(days=days)
    return db.query(Video).filter(
        Video.created_at > cutoff_date
    ).order_by(Video.created_at.desc()).all()

# Uses: ix_videos_created_at index
# Additional: Order by same column as filter for optimal performance
```

### 2. Join Optimization

**Before: N+1 Query Problem:**
```python
# Inefficient: N+1 queries
def get_projects_with_video_counts_slow(db: Session, user_id: str):
    projects = db.query(Project).filter(Project.owner_id == user_id).all()
    
    result = []
    for project in projects:
        # This creates N additional queries!
        video_count = db.query(func.count(VideoProjectLink.video_id)).filter(
            VideoProjectLink.project_id == project.id
        ).scalar()
        
        result.append({
            "project": project,
            "video_count": video_count
        })
    
    return result
```

**After: Single Query with Join:**
```python
# Efficient: Single query with aggregation
def get_projects_with_video_counts_fast(db: Session, user_id: str):
    return db.query(
        Project,
        func.coalesce(func.count(VideoProjectLink.video_id), 0).label('video_count')
    ).outerjoin(
        VideoProjectLink, Project.id == VideoProjectLink.project_id
    ).filter(
        Project.owner_id == user_id
    ).group_by(Project.id).all()
```

### 3. Pagination Optimization

**Efficient Pagination Pattern:**
```python
def get_paginated_results(db: Session, user_id: str, page: int = 1, size: int = 20):
    """Optimized pagination with total count"""
    
    # Base query with security
    base_query = db.query(Video).join(VideoProjectLink).join(Project).filter(
        Project.owner_id == user_id
    )
    
    # Get total count (uses count query optimization)
    total = base_query.count()
    
    # Get paginated results
    offset = (page - 1) * size
    results = base_query.offset(offset).limit(size).all()
    
    return {
        "items": results,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size
    }
```

### 4. Bulk Operations

**Efficient Bulk Updates:**
```python
def bulk_update_video_status(db: Session, video_ids: List[str], new_status: str):
    """Bulk update video status efficiently"""
    
    updated_count = db.query(Video).filter(
        Video.id.in_(video_ids)
    ).update(
        {"status": new_status, "updated_at": func.now()},
        synchronize_session=False
    )
    
    db.commit()
    return updated_count

# Single UPDATE query instead of N individual updates
# synchronize_session=False disables object synchronization for performance
```

This comprehensive query patterns documentation provides the foundation for understanding and optimizing database operations throughout the AI Model Validation Platform.