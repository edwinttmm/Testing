# CRUD Operations Documentation

## Overview

The CRUD operations layer (`crud.py`) provides a comprehensive data access layer for the AI Model Validation Platform. It implements secure, efficient database operations with user-based access control and supports both legacy single-project and modern many-to-many project-video relationships.

## Security Model

### User-Based Access Control
All CRUD operations implement user-based security filtering:
```python
def get_projects(db: Session, user_id: str = "anonymous", skip: int = 0, limit: int = 100):
    return db.query(Project).filter(Project.owner_id == user_id).offset(skip).limit(limit).all()
```

### Security Features
- **User Isolation**: Each user only accesses their own data
- **Cascade Protection**: Safe deletion with relationship preservation
- **SQL Injection Prevention**: Parameterized queries only
- **Access Validation**: Multi-layer security checks

## Project CRUD Operations

### Create Project
```python
def create_project(db: Session, project: ProjectCreate, user_id: str = "anonymous") -> Project
```
**Features**:
- Automatic owner assignment
- Schema validation via Pydantic
- UUID generation for primary keys
- Audit trail creation

### Read Projects
```python
def get_projects(db: Session, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Project]
def get_project(db: Session, project_id: str, user_id: str = "anonymous", load_videos: bool = False) -> Optional[Project]
```
**Features**:
- Pagination support
- Optional video loading with `joinedload`
- User security filtering
- Null-safe operations

### Update Project
```python
def update_project(db: Session, project_id: str, project_update: ProjectUpdate, user_id: str) -> Optional[Project]
```
**Features**:
- Partial updates via `exclude_unset=True`
- User ownership validation
- Automatic timestamp updates
- Field-level validation

### Delete Project
```python
def delete_project(db: Session, project_id: str, user_id: str = "anonymous") -> bool
```
**Features**:
- Cascade deletion handling
- Physical file cleanup
- Many-to-many relationship management
- Orphan video handling
- Atomic transaction operations

## Video CRUD Operations

### Many-to-Many Video Management
The system supports videos assigned to multiple projects through the `VideoProjectLink` junction table.

#### Create Video
```python
def create_video(db: Session, filename: str, file_path: str = None, file_size: int = None, project_ids: List[str] = None) -> Video
```
**Features**:
- Multi-project assignment
- Primary project requirement for database constraints
- Automatic file path generation
- Bulk project assignment

#### Video-Project Assignment
```python
def assign_video_to_project(db: Session, video_id: str, project_id: str, assignment_reason: str = None, confidence_score: float = None) -> VideoProjectLink
def remove_video_from_project(db: Session, video_id: str, project_id: str, user_id: str = "anonymous") -> bool
```

**Features**:
- Duplicate assignment prevention
- Intelligent matching with confidence scores
- Assignment reason tracking
- User security validation

#### Video Queries
```python
def get_project_videos(db: Session, project_id: str, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Video]
def get_video_projects(db: Session, video_id: str, user_id: str = "anonymous") -> List[Project]
def get_videos(db: Session, project_id: str = None, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[Video]
```

**Features**:
- Cross-project video queries with `DISTINCT`
- Join optimization through `VideoProjectLink`
- User security at every level
- Pagination support

## Ground Truth CRUD Operations

### Create Ground Truth Object
```python
def create_ground_truth_object(db: Session, video_id: str, timestamp: float, 
                              class_label: str, x: float, y: float, width: float, height: float,
                              confidence: float, frame_number: int = None, validated: bool = True, 
                              difficult: bool = False, bounding_box: dict = None,
                              screenshot_path: str = None, screenshot_zoom_path: str = None) -> GroundTruthObject
```

**Features**:
- Comprehensive bounding box management
- Frame-level synchronization
- Validation state tracking
- Screenshot path management
- Backward compatibility with legacy bounding_box field

### Query Ground Truth
```python
def get_ground_truth_objects(db: Session, video_id: str, user_id: str = "anonymous") -> List[GroundTruthObject]
```

**Features**:
- Multi-table join security filtering
- Video ownership validation
- Performance-optimized queries

## Test Session CRUD Operations

### Create Test Session
```python
def create_test_session(db: Session, test_session: TestSessionCreate, user_id: str) -> TestSession
```

### Query Test Sessions
```python
def get_test_sessions(db: Session, project_id: str = None, video_id: str = None, user_id: str = "anonymous", skip: int = 0, limit: int = 100) -> List[TestSession]
def get_test_session(db: Session, session_id: str, user_id: str = "anonymous") -> Optional[TestSession]
```

**Features**:
- Multi-parameter filtering
- Video access validation through subqueries
- Project-based security filtering

## Detection Event CRUD Operations

### Create Detection Event
```python
def create_detection_event(db: Session, detection: DetectionEventSchema) -> DetectionEvent
```

### Query Detection Events
```python
def get_detection_events(db: Session, test_session_id: str, user_id: str = "anonymous") -> List[DetectionEvent]
```

**Features**:
- Cascaded security through TestSession → Project
- Session-based event grouping

## Audit & Dashboard Operations

### Audit Log Management
```python
def create_audit_log(db: Session, audit_log: AuditLogCreate, user_id: str = None) -> AuditLog
def get_audit_logs(db: Session, user_id: str = None, event_type: str = None, skip: int = 0, limit: int = 100) -> List[AuditLog]
```

### Dashboard Statistics
```python
def get_dashboard_stats(db: Session, user_id: str) -> dict
```

**Features**:
- Cross-table aggregation with `func.count()`
- Distinct counting for many-to-many relationships
- User-scoped statistics

## Bulk Operations

### Bulk Video Assignment
```python
def bulk_assign_videos_to_project(db: Session, project_id: str, video_ids: List[str], user_id: str = "anonymous") -> List[VideoProjectLink]
def bulk_remove_videos_from_project(db: Session, project_id: str, video_ids: List[str], user_id: str = "anonymous") -> int
```

**Features**:
- Batch processing optimization
- Individual security validation
- Error tolerance (partial success)

## Database Relationship Management

### Orphan Management
```python
def get_orphaned_videos(db: Session, user_id: str = "anonymous") -> List[Video]
def cleanup_orphaned_videos(db: Session, user_id: str = "anonymous") -> int
```

**Features**:
- Orphan detection across junction tables
- Safe cleanup with file system integration
- Transaction safety

### Legacy Migration
```python
def migrate_legacy_video_relationships(db: Session) -> int
```

**Features**:
- Seamless migration from direct relationships to junction table
- Duplicate prevention
- Metadata preservation

### Relationship Validation
```python
def validate_project_video_relationships(db: Session, user_id: str = "anonymous") -> dict
```

**Features**:
- Integrity checking
- Duplicate detection
- Orphan identification
- Health monitoring

## Query Optimization Features

### Index Utilization
All queries leverage composite indexes defined in models:
```python
# Example: Leveraging project_id + status index
query.filter(Project.owner_id == user_id, Project.status == 'active')
```

### Eager Loading
```python
# Load project with associated videos in single query
return db.query(Project).options(
    joinedload(Project.video_links).joinedload(VideoProjectLink.video)
).filter(...)
```

### Pagination
```python
# Consistent pagination pattern
return query.offset(skip).limit(limit).all()
```

## Error Handling Patterns

### Exception Handling
```python
try:
    db.delete(db_project)
    db.commit()
    return True
except Exception as e:
    db.rollback()
    raise e
```

### Null Safety
```python
# Graceful handling of missing records
if not db_project:
    return None
```

### Resource Cleanup
```python
# Physical file cleanup with error tolerance
if video.file_path and os.path.exists(video.file_path):
    try:
        os.remove(video.file_path)
    except OSError:
        pass  # File may already be deleted
```

## Transaction Management

### Automatic Commit/Rollback
```python
def safe_operation(db: Session):
    try:
        # Multiple database operations
        db.add(object1)
        db.add(object2)
        db.commit()
    except Exception:
        db.rollback()
        raise
```

### Cascade Operations
```python
# Leverage SQLAlchemy cascade for complex deletions
# CASCADE defined in model relationships handles:
# - TestSessions (via cascade="all, delete-orphan")
# - DetectionEvents (via TestSession cascade)
# - VideoProjectLinks (via cascade="all, delete-orphan")
```

## Performance Considerations

### Query Optimization
- Use of indexes for all filtering operations
- Minimal N+1 query issues via `joinedload`
- Subquery optimization for complex filters

### Memory Management
- Pagination to prevent large result sets
- Lazy loading by default
- Selective eager loading only when needed

### Database Connection Management
- Session-per-request pattern
- Proper session cleanup in finally blocks
- Connection pooling at engine level

## Data Integrity Features

### Foreign Key Constraints
- Automatic constraint validation
- Cascade deletion protection
- Reference integrity enforcement

### Unique Constraints
- Duplicate prevention at database level
- Unique index utilization
- Composite uniqueness validation

### Data Validation
- Pydantic schema validation before database operations
- Type safety through SQLAlchemy models
- Business rule validation in service layer

## Backward Compatibility

### Legacy Field Support
```python
@property
def uploaded_at(self):
    """Backward compatibility property - maps to created_at"""
    return self.created_at
```

### Migration Support
- Automatic migration of legacy relationships
- Gradual schema evolution
- Fallback query patterns