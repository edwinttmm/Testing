# Project Schema Refactoring Analysis

## Current Architecture Issues

### Project Model Problems (Lines 80-100)
The current `Project` model is bloated with camera-specific metadata that should belong to individual videos:

```python
class Project(Base):
    # Core playlist fields (KEEP)
    id = Column(String(36), primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="Active")
    owner_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    
    # Camera metadata (MOVE TO VIDEO) - ARCHITECTURAL MISMATCH
    camera_model = Column(String, nullable=False)      # → Video
    camera_view = Column(String, nullable=False)       # → Video
    lens_type = Column(String)                         # → Video
    resolution = Column(String)                        # → Video
    frame_rate = Column(Integer)                       # → Video
    signal_type = Column(String, nullable=False)       # → Video/TestSession
```

### PRD Compliance Analysis

**PRD Requirement (Lines 88-96):**
> "Project-Based Workflow: A system for grouping validated videos into specific test suites"
> "Users must be able to create, name, and delete 'Projects'"
> "Users must be able to add or remove any number of 'Validated' videos from a project"

**Current Implementation Issues:**
1. **Single Video Assignment**: Current 1:N relationship forces all videos in a project to share camera metadata
2. **Metadata Duplication**: Camera specifications repeated across projects instead of stored per video
3. **Inflexible Playlists**: Cannot mix videos with different camera specifications in same test suite

## Proposed New Architecture

### 1. Simplified Project Model (Playlist Container)
```python
class Project(Base):
    __tablename__ = "projects"
    
    # Core playlist identity
    id = Column(String(36), primary_key=True)
    name = Column(String, nullable=False, index=True)
    description = Column(Text)
    
    # Playlist management
    status = Column(String, default="Active", index=True)
    owner_id = Column(String(36), nullable=True, index=True)
    video_count = Column(Integer, default=0)  # Cached count
    total_duration = Column(Float, nullable=True)  # Cached duration
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Many-to-many relationship with videos
    videos = relationship("Video", secondary="project_videos", back_populates="projects")
```

### 2. Enhanced Video Model (Camera Metadata Container)
```python
class Video(Base):
    __tablename__ = "videos"
    
    # Existing video identity
    id = Column(String(36), primary_key=True)
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    
    # MOVED FROM PROJECT: Camera technical specifications
    camera_model = Column(String, nullable=True, index=True)
    camera_view = Column(String, nullable=True, index=True)
    lens_type = Column(String, nullable=True)
    camera_resolution = Column(String, nullable=True)  # Renamed for clarity
    camera_frame_rate = Column(Integer, nullable=True)
    signal_type = Column(String, nullable=True)
    
    # Video technical metadata
    file_size = Column(Integer)
    duration = Column(Float)  # in seconds
    fps = Column(Float)  # Actual video fps (may differ from camera_frame_rate)
    video_resolution = Column(String)  # Actual video resolution
    
    # Processing status
    status = Column(String, default="uploaded", index=True)
    processing_status = Column(String, default="pending", index=True)
    ground_truth_generated = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Many-to-many relationship with projects
    projects = relationship("Project", secondary="project_videos", back_populates="videos")
```

### 3. Project-Video Junction Table
```python
class ProjectVideo(Base):
    __tablename__ = "project_videos"
    
    # Primary keys
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True)
    
    # Playlist ordering and metadata
    sequence_order = Column(Integer, nullable=False, default=0, index=True)
    added_by = Column(String(36), nullable=True)
    notes = Column(Text)
    
    # Timestamps
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Composite indexes for performance
    __table_args__ = (
        Index('idx_project_video_order', 'project_id', 'sequence_order'),
        Index('idx_video_project_added', 'video_id', 'added_at'),
    )
```

## Migration Strategy

### Phase 1: Add New Columns to Video Model
```sql
ALTER TABLE videos ADD COLUMN camera_model VARCHAR;
ALTER TABLE videos ADD COLUMN camera_view VARCHAR;
ALTER TABLE videos ADD COLUMN lens_type VARCHAR;
ALTER TABLE videos ADD COLUMN camera_resolution VARCHAR;
ALTER TABLE videos ADD COLUMN camera_frame_rate INTEGER;
ALTER TABLE videos ADD COLUMN signal_type VARCHAR;
```

### Phase 2: Create Junction Table
```sql
CREATE TABLE project_videos (
    project_id VARCHAR(36) NOT NULL,
    video_id VARCHAR(36) NOT NULL,
    sequence_order INTEGER DEFAULT 0,
    added_by VARCHAR(36),
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, video_id),
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);
```

### Phase 3: Data Migration
```sql
-- Migrate camera metadata from project to videos
UPDATE videos v SET 
    camera_model = (SELECT p.camera_model FROM projects p WHERE p.id = v.project_id),
    camera_view = (SELECT p.camera_view FROM projects p WHERE p.id = v.project_id),
    lens_type = (SELECT p.lens_type FROM projects p WHERE p.id = v.project_id),
    camera_resolution = (SELECT p.resolution FROM projects p WHERE p.id = v.project_id),
    camera_frame_rate = (SELECT p.frame_rate FROM projects p WHERE p.id = v.project_id),
    signal_type = (SELECT p.signal_type FROM projects p WHERE p.id = v.project_id);

-- Populate junction table with existing relationships
INSERT INTO project_videos (project_id, video_id, sequence_order, added_at)
SELECT project_id, id, ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY created_at), created_at
FROM videos;
```

### Phase 4: Remove Obsolete Columns
```sql
ALTER TABLE projects DROP COLUMN camera_model;
ALTER TABLE projects DROP COLUMN camera_view;
ALTER TABLE projects DROP COLUMN lens_type;
ALTER TABLE projects DROP COLUMN resolution;
ALTER TABLE projects DROP COLUMN frame_rate;
ALTER TABLE projects DROP COLUMN signal_type;

-- Remove foreign key constraint on videos.project_id
ALTER TABLE videos DROP CONSTRAINT fk_videos_project_id;
ALTER TABLE videos DROP COLUMN project_id;
```

## Benefits of New Architecture

### 1. PRD Compliance
- **True Playlist Functionality**: Projects are lightweight containers for video collections
- **Mixed Camera Types**: Can combine videos from different cameras in single test suite
- **Flexible Video Reuse**: Same video can be part of multiple projects without duplication

### 2. Data Integrity
- **Normalized Schema**: Camera metadata stored once per video, not duplicated per project
- **Referential Integrity**: Junction table ensures clean many-to-many relationships
- **Metadata Accuracy**: Technical specs stay with the actual video file

### 3. Performance Benefits
- **Reduced Redundancy**: Eliminates duplicate camera metadata storage
- **Efficient Queries**: Proper indexing on junction table for playlist operations
- **Scalability**: Many-to-many design supports large video libraries

### 4. Backwards Compatibility
- **Gradual Migration**: Phased approach minimizes disruption
- **Data Preservation**: All existing relationships maintained during transition
- **API Compatibility**: Models can expose legacy interfaces during migration period

## Implementation Priority

1. **HIGH**: Create new Video model columns and junction table
2. **HIGH**: Implement data migration scripts with rollback capability
3. **MEDIUM**: Update ORM relationships and cascade rules
4. **MEDIUM**: Modify API endpoints to use new schema
5. **LOW**: Remove deprecated Project columns after full migration