# Database Integration Analysis

## Overview
This document provides comprehensive analysis of database integration, ORM mappings, data persistence flows, and query patterns in the AI Model Validation Platform.

## Database Architecture

### Technology Stack
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **ORM**: SQLAlchemy 2.x with declarative base
- **Migration**: Alembic for schema versioning
- **Connection Management**: SQLAlchemy Session with connection pooling

### Database Schema Overview
```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Projects  │    │    Videos    │    │Ground Truth │
│             │◄───┤              │◄───┤   Objects   │
│ - id        │    │ - id         │    │ - id        │
│ - name      │    │ - filename   │    │ - timestamp │
│ - owner_id  │    │ - status     │    │ - class_label│
└─────────────┘    │ - project_id │    │ - bounding_box│
       │           └──────────────┘    └─────────────┘
       │                  │                    │
       ▼                  ▼                    ▼
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│Test Sessions│    │ Annotations  │    │ Detection   │
│             │    │              │    │   Events    │
│ - id        │    │ - id         │    │ - id        │
│ - project_id│    │ - video_id   │    │ - session_id│
│ - status    │    │ - detection_id│    │ - timestamp │
└─────────────┘    └──────────────┘    │ - latency_ms│
                                       └─────────────┘
```

## Core Model Relationships

### 1. Project-Video Many-to-Many Relationship

#### Models Definition
```python
# Project Model
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    owner_id = Column(String(36), nullable=True, default="anonymous", index=True)
    
    # Relationships
    videos = relationship("Video", back_populates="project", cascade="all, delete-orphan")
    video_links = relationship("VideoProjectLink", back_populates="project", cascade="all, delete-orphan")

# Video Model
class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)
    status = Column(String, default="uploaded", index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    project = relationship("Project", back_populates="videos")
    project_links = relationship("VideoProjectLink", back_populates="video", cascade="all, delete-orphan")

# Junction Table for Many-to-Many
class VideoProjectLink(Base):
    __tablename__ = "video_project_links"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationships
    video = relationship("Video", back_populates="project_links")
    project = relationship("Project", back_populates="video_links")
```

### 2. Test Session and Detection Events

#### Model Structure
```python
class TestSession(Base):
    __tablename__ = "test_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String, default="created", index=True)
    
    # LabJack timing fields
    latency_threshold_ms = Column(Integer, default=100, index=True)
    video_start_timestamp = Column(Float, nullable=True, index=True)
    
    # Relationships
    project = relationship("Project", back_populates="test_sessions")
    detection_events = relationship("DetectionEvent", back_populates="test_session", cascade="all, delete-orphan")

class DetectionEvent(Base):
    __tablename__ = "detection_events"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_session_id = Column(String(36), ForeignKey("test_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    
    # LabJack timing data
    latency_ms = Column(Float, nullable=True, index=True)
    labjack_timestamp = Column(Float, nullable=True, index=True)
    voltage_level = Column(Float, nullable=True)
    
    # Relationships
    test_session = relationship("TestSession", back_populates="detection_events")
    video = relationship("Video")
```

## Database Connection Management

### Session Lifecycle
```python
# Connection configuration
from database import SessionLocal, engine, get_db

# Dependency injection pattern
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI endpoint usage
@app.get("/api/projects")
async def get_projects(db: Session = Depends(get_db)):
    return crud.get_projects(db)
```

### Connection Pool Configuration
```python
# SQLAlchemy engine setup
engine = create_engine(
    DATABASE_URL,
    pool_size=20,           # Base connections
    max_overflow=30,        # Additional connections
    pool_timeout=30,        # Wait time for connection
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True      # Validate connections before use
)
```

## Data Persistence Patterns

### 1. Create Operations

#### Project Creation Flow
```python
def create_project(db: Session, project: ProjectCreate, user_id: str = "anonymous") -> Project:
    # Convert Pydantic model to dictionary
    project_data = project.model_dump()
    
    # Create SQLAlchemy model instance
    db_project = Project(
        **project_data,
        owner_id=user_id
    )
    
    # Persist to database
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return db_project
```

#### Video Upload with Project Assignment
```python
def create_video(db: Session, filename: str, file_path: str = None, 
                file_size: int = None, project_ids: List[str] = None) -> Video:
    # Create primary video record
    primary_project_id = project_ids[0] if project_ids else None
    
    db_video = Video(
        filename=filename,
        file_path=file_path or f"/uploads/{filename}",
        file_size=file_size,
        project_id=primary_project_id  # Required by NOT NULL constraint
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)
    
    # Create many-to-many links for additional projects
    if project_ids and len(project_ids) > 1:
        for project_id in project_ids[1:]:
            assign_video_to_project(db, db_video.id, project_id)
    
    return db_video
```

### 2. Query Patterns

#### Optimized Project Loading with Videos
```python
def get_project(db: Session, project_id: str, user_id: str = "anonymous", 
               load_videos: bool = False) -> Optional[Project]:
    if load_videos:
        # Eager loading with JOIN to prevent N+1 queries
        from sqlalchemy.orm import joinedload
        return db.query(Project).options(
            joinedload(Project.video_links).joinedload(VideoProjectLink.video)
        ).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()
    else:
        # Lightweight loading without videos
        return db.query(Project).filter(
            Project.id == project_id,
            Project.owner_id == user_id
        ).first()
```

#### Security-Filtered Video Queries
```python
def get_videos(db: Session, project_id: str = None, user_id: str = "anonymous", 
              skip: int = 0, limit: int = 100) -> List[Video]:
    if project_id:
        # Get videos for specific project with security filter
        query = db.query(Video).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id,
            VideoProjectLink.project_id == project_id
        )
    else:
        # Get all videos accessible to user across projects
        query = db.query(Video).join(VideoProjectLink).join(Project).filter(
            Project.owner_id == user_id
        ).distinct()  # Prevent duplicates if video is in multiple projects
    
    return query.offset(skip).limit(limit).all()
```

### 3. Complex Aggregation Queries

#### Dashboard Statistics
```python
def get_dashboard_stats(db: Session, user_id: str):
    from sqlalchemy import func
    
    # Project count
    project_count = db.query(func.count(Project.id)).filter(
        Project.owner_id == user_id
    ).scalar() or 0
    
    # Unique video count through junction table
    video_count = db.query(func.count(Video.id.distinct())).join(
        VideoProjectLink
    ).join(Project).filter(
        Project.owner_id == user_id
    ).scalar() or 0
    
    # Test session count
    test_session_count = db.query(func.count(TestSession.id)).join(Project).filter(
        Project.owner_id == user_id
    ).scalar() or 0
    
    return {
        "project_count": project_count,
        "video_count": video_count,
        "test_session_count": test_session_count
    }
```

## Index Strategy and Performance

### Database Indexes
```python
# Comprehensive indexing strategy
class Video(Base):
    __tablename__ = "videos"
    
    # ... column definitions ...
    
    # Enhanced composite indexes for performance-critical queries
    __table_args__ = (
        # Validation system indexes
        Index('idx_video_status_validation', 'status', 'validation_status'),
        Index('idx_video_hil_ready', 'hil_testing_ready', 'status'),
        Index('idx_video_validation_completed', 'validated_at', 'validation_type'),
        
        # Legacy indexes (maintained for compatibility)
        Index('idx_video_project_status', 'project_id', 'status'),
        Index('idx_video_project_created', 'project_id', 'created_at'),
        Index('idx_video_ground_truth_status', 'ground_truth_generated', 'processing_status'),
        
        # File and metadata indexes
        Index('idx_video_file_path', 'file_path'),
        Index('idx_video_duration_fps', 'duration', 'fps'),
        Index('idx_video_size_resolution', 'file_size', 'resolution'),
    )
```

### Query Performance Analysis
```python
# LabJack timing queries with optimized indexes
class DetectionEvent(Base):
    __table_args__ = (
        # Core session queries
        Index('idx_detection_session_timestamp', 'test_session_id', 'timestamp'),
        Index('idx_detection_session_validation', 'test_session_id', 'validation_result'),
        
        # LabJack-specific indexes
        Index('idx_detection_latency_validation', 'latency_ms', 'validation_result'),
        Index('idx_detection_labjack_timestamp', 'labjack_timestamp'),
        Index('idx_detection_session_latency', 'test_session_id', 'latency_ms'),
        
        # Complex analytics queries
        Index('idx_detection_session_labjack_validation', 'test_session_id', 'validation_result', 'latency_ms'),
    )
```

## Transaction Management

### Database Transaction Patterns
```python
def delete_project(db: Session, project_id: str, user_id: str = "anonymous") -> bool:
    db_project = get_project(db, project_id, user_id, load_videos=True)
    if not db_project:
        return False
    
    try:
        # Complex deletion with cascade handling
        project_videos = get_project_videos(db, project_id, user_id)
        
        for video in project_videos:
            # Check if video is in other projects
            other_projects = db.query(VideoProjectLink).filter(
                VideoProjectLink.video_id == video.id,
                VideoProjectLink.project_id != project_id
            ).count()
            
            # Only delete video if not in other projects
            if other_projects == 0:
                # Clean up physical file
                if video.file_path and os.path.exists(video.file_path):
                    os.remove(video.file_path)
                db.delete(video)
        
        # Delete project (CASCADE handles related records)
        db.delete(db_project)
        db.commit()
        
        return True
        
    except Exception as e:
        db.rollback()
        raise e
```

## Data Migration and Schema Evolution

### Alembic Migration Pattern
```python
# Migration script example
def upgrade():
    # Add new columns for LabJack timing
    op.add_column('detection_events', 
                 sa.Column('latency_ms', sa.Float(), nullable=True))
    op.add_column('detection_events', 
                 sa.Column('labjack_timestamp', sa.Float(), nullable=True))
    
    # Create indexes for new columns
    op.create_index('idx_detection_latency_validation', 'detection_events', 
                   ['latency_ms', 'validation_result'])

def downgrade():
    # Remove indexes first
    op.drop_index('idx_detection_latency_validation', 'detection_events')
    
    # Remove columns
    op.drop_column('detection_events', 'labjack_timestamp')
    op.drop_column('detection_events', 'latency_ms')
```

## Error Handling and Recovery

### Database Error Patterns
```python
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

@app.post("/api/projects")
async def create_project_endpoint(project: ProjectCreate, db: Session = Depends(get_db)):
    try:
        result = crud.create_project(db, project)
        return result
    except IntegrityError as e:
        # Handle unique constraint violations
        raise HTTPException(status_code=400, detail="Project name already exists")
    except OperationalError as e:
        # Handle connection issues
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except SQLAlchemyError as e:
        # Handle other database errors
        raise HTTPException(status_code=500, detail="Database error occurred")
```

## Performance Monitoring

### Query Performance Tracking
```python
# Database operation logging
import time
import logging

def timed_db_operation(operation_name: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logging.info(f"DB Operation: {operation_name} completed in {duration:.3f}s")
                return result
            except Exception as e:
                duration = time.time() - start_time
                logging.error(f"DB Operation: {operation_name} failed after {duration:.3f}s: {e}")
                raise
        return wrapper
    return decorator
```

## Backup and Recovery Strategy

### Database Backup Integration
```python
# Automated backup configuration
BACKUP_CONFIG = {
    "schedule": "0 2 * * *",  # Daily at 2 AM
    "retention_days": 30,
    "storage_path": "/backups/database",
    "compression": True
}

def create_database_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_CONFIG['storage_path']}/backup_{timestamp}.sql"
    
    # SQLite backup
    if DATABASE_URL.startswith("sqlite"):
        import shutil
        shutil.copy2("database.db", backup_path)
    
    # PostgreSQL backup
    else:
        os.system(f"pg_dump {DATABASE_URL} > {backup_path}")
        
    # Compress if enabled
    if BACKUP_CONFIG["compression"]:
        import gzip
        with open(backup_path, 'rb') as f_in:
            with gzip.open(f"{backup_path}.gz", 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(backup_path)
```

## Future Database Enhancements

### Planned Improvements
1. **Read Replicas**: Separate read/write database connections
2. **Partitioning**: Time-based partitioning for large tables
3. **Caching Layer**: Redis integration for frequently accessed data
4. **Connection Pooling**: Advanced pool management with monitoring
5. **Query Optimization**: Automated query analysis and optimization
6. **Data Archival**: Automated archiving of old test data