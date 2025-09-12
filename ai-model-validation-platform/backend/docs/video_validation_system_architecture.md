# Video Validation System Architecture

## Problem Analysis

### Current Status Contract Mismatches

**Backend Models (models.py)**
- Video.status: `"uploaded"` (default), indexed
- Video.processing_status: `"pending"` (default), indexed for ground truth processing
- Video.ground_truth_generated: Boolean flag

**Frontend Schemas (schemas.py)**
- VideoStatus enum: `PENDING_ANNOTATION`, `PENDING_VALIDATION`, `VALIDATED`, `PROCESSING`, `ERROR`
- VideoResponse.status: Generic string field
- VideoResponse.ground_truth_generated: Boolean

**Frontend Types (types.ts)**
- VideoStatus enum: Same as schemas but different from backend reality
- VideoFile interface: Multiple status fields with inconsistent naming

### Core Issues
1. **Status Mismatch**: Backend uses `"uploaded"/"completed"` while frontend expects validation workflow states
2. **Field Confusion**: Multiple status fields (`status`, `processing_status`, `ground_truth_generated`) with unclear relationships  
3. **HIL Readiness**: No clear indication when videos are ready for HIL testing
4. **Validation Workflow**: Missing validation states for automatic and manual validation
5. **Migration Challenge**: Existing videos with `"completed"` status need mapping to new system

## Unified Video Status System Design

### Status Workflow States

```
upload → processing → annotated → validating → validated → ready_for_testing → in_testing → tested
   ↓         ↓           ↓          ↓           ↓             ↓              ↓         ↓
error    error      error      error       error         error          error     archived
```

### Primary Status Enumeration

```python
class VideoValidationStatus(str, Enum):
    # Initial states
    UPLOADED = "uploaded"                    # Video file uploaded, pending processing
    PROCESSING = "processing"                # Ground truth generation in progress
    PROCESSING_FAILED = "processing_failed" # Ground truth generation failed
    
    # Annotation states  
    ANNOTATED = "annotated"                  # Ground truth generated, pending validation
    
    # Validation states
    VALIDATING = "validating"                # Validation in progress (auto or manual)
    VALIDATION_FAILED = "validation_failed" # Validation failed, needs review
    VALIDATED = "validated"                  # Validation complete and passed
    
    # Testing readiness
    READY_FOR_TESTING = "ready_for_testing"  # Available for HIL test sessions
    IN_TESTING = "in_testing"                # Currently being used in test session
    TESTED = "tested"                        # Has completed test sessions
    
    # Final states
    ARCHIVED = "archived"                    # Archived for historical reference
    ERROR = "error"                          # Unrecoverable error state
```

### Validation Criteria Framework

Videos transition to `validated` status when they meet all criteria:

#### Automatic Validation Criteria
1. **Ground Truth Quality**
   - Minimum detection count threshold
   - Confidence score distribution requirements
   - Frame coverage percentage
   
2. **Technical Validation**
   - Video format compliance
   - Resolution and frame rate validation
   - Duration within acceptable ranges
   
3. **Content Validation**
   - VRU type distribution requirements
   - Scene complexity analysis
   - Lighting and visibility conditions

#### Manual Validation Criteria
1. **Annotation Review**
   - Manual review of ground truth annotations
   - Correction of false positives/negatives
   - Validation of VRU classifications
   
2. **Quality Assurance**
   - Visual inspection of video content
   - Verification of testing scenarios
   - Approval for HIL testing use

## Database Schema Updates

### Enhanced Video Model

```python
class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    duration = Column(Float)
    fps = Column(Float)
    resolution = Column(String)
    
    # UNIFIED STATUS SYSTEM
    status = Column(String, default="uploaded", index=True)  # Primary status field
    
    # VALIDATION SPECIFIC FIELDS
    validation_status = Column(String, default="pending", index=True)  # Validation workflow
    validation_type = Column(String, nullable=True)  # 'automatic', 'manual', 'hybrid'
    validated_at = Column(DateTime(timezone=True), nullable=True, index=True)
    validated_by = Column(String(36), nullable=True)  # User ID who validated
    
    # GROUND TRUTH FIELDS
    ground_truth_generated = Column(Boolean, default=False, index=True)
    ground_truth_count = Column(Integer, default=0)
    ground_truth_quality_score = Column(Float, nullable=True)
    ground_truth_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # TESTING READINESS FIELDS
    hil_testing_ready = Column(Boolean, default=False, index=True)
    hil_testing_approved_by = Column(String(36), nullable=True)
    hil_testing_approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # METADATA
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Enhanced indexes for validation queries
    __table_args__ = (
        Index('idx_video_status_validation', 'status', 'validation_status'),
        Index('idx_video_hil_ready', 'hil_testing_ready', 'status'),
        Index('idx_video_validation_completed', 'validated_at', 'validation_type'),
        Index('idx_video_ground_truth_quality', 'ground_truth_quality_score', 'ground_truth_count'),
        Index('idx_video_project_status', 'project_id', 'status'),
        Index('idx_video_testing_workflow', 'status', 'hil_testing_ready', 'validated_at'),
    )
```

### New Validation Tables

```python
class VideoValidationCriteria(Base):
    """Configurable validation criteria per project or globally"""
    __tablename__ = "video_validation_criteria"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)  # NULL = global
    
    # Ground truth quality requirements
    min_detection_count = Column(Integer, default=5)
    min_confidence_threshold = Column(Float, default=0.7)
    min_frame_coverage_percent = Column(Float, default=80.0)
    
    # Technical requirements
    min_duration_seconds = Column(Float, default=10.0)
    max_duration_seconds = Column(Float, default=300.0)
    required_resolution_min = Column(String, default="640x480")
    min_fps = Column(Float, default=24.0)
    
    # Content requirements
    required_vru_types = Column(JSON)  # ['pedestrian', 'cyclist']
    min_scene_complexity_score = Column(Float, default=0.5)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class VideoValidationResult(Base):
    """Results of validation process"""
    __tablename__ = "video_validation_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    validation_criteria_id = Column(String(36), ForeignKey("video_validation_criteria.id"), nullable=False)
    
    # Validation results
    validation_type = Column(String, nullable=False, index=True)  # 'automatic', 'manual'
    overall_result = Column(String, nullable=False, index=True)  # 'passed', 'failed', 'needs_review'
    
    # Detailed results
    ground_truth_score = Column(Float)
    technical_score = Column(Float)
    content_score = Column(Float)
    overall_score = Column(Float, index=True)
    
    # Validation details
    criteria_met = Column(JSON)  # Detailed criteria pass/fail
    validation_notes = Column(Text)
    validated_by = Column(String(36), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class VideoStatusTransition(Base):
    """Audit trail for status changes"""
    __tablename__ = "video_status_transitions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    
    from_status = Column(String, nullable=False, index=True)
    to_status = Column(String, nullable=False, index=True)
    transition_reason = Column(String, nullable=False)
    
    # Context
    triggered_by = Column(String(36), nullable=True)  # User ID or 'system'
    metadata = Column(JSON)  # Additional context data
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_status_transition_video_time', 'video_id', 'created_at'),
        Index('idx_status_transition_from_to', 'from_status', 'to_status'),
    )
```

## API Endpoints for Video Validation

### Core Validation Endpoints

```python
# Video status management
GET    /api/v1/videos/{video_id}/status
PUT    /api/v1/videos/{video_id}/status
GET    /api/v1/videos/{video_id}/validation-history

# Validation operations
POST   /api/v1/videos/{video_id}/validate
POST   /api/v1/videos/{video_id}/validate/automatic
POST   /api/v1/videos/{video_id}/validate/manual
GET    /api/v1/videos/{video_id}/validation-result

# Validation criteria management
GET    /api/v1/validation/criteria
POST   /api/v1/validation/criteria
GET    /api/v1/validation/criteria/{criteria_id}
PUT    /api/v1/validation/criteria/{criteria_id}

# HIL testing readiness
GET    /api/v1/videos/ready-for-testing
POST   /api/v1/videos/{video_id}/approve-for-testing
POST   /api/v1/videos/{video_id}/mark-in-testing
POST   /api/v1/videos/{video_id}/mark-tested

# Batch operations
POST   /api/v1/videos/batch-validate
GET    /api/v1/videos/validation-queue
POST   /api/v1/videos/batch-status-update
```

## Status Transition Rules

### Automatic Transitions

```python
class VideoStatusTransitionRules:
    
    AUTOMATIC_TRANSITIONS = {
        'uploaded': ['processing', 'error'],
        'processing': ['annotated', 'processing_failed'],
        'annotated': ['validating', 'error'],
        'validating': ['validated', 'validation_failed'],
        'validated': ['ready_for_testing'],
        'ready_for_testing': ['in_testing'],
        'in_testing': ['tested', 'ready_for_testing'],  # Can return to ready
        'tested': ['archived'],
        'processing_failed': ['processing', 'error'],  # Retry or give up
        'validation_failed': ['validating', 'error'],  # Retry or give up
    }
    
    MANUAL_TRANSITIONS = {
        'annotated': ['validated'],  # Skip automatic validation
        'validation_failed': ['validated'],  # Manual override
        'validated': ['annotated'],  # Revert for re-annotation
        'ready_for_testing': ['validated'],  # Revert approval
        'tested': ['ready_for_testing'],  # Re-use for testing
        'any': ['error', 'archived'],  # Admin actions
    }
```

### Validation Business Rules

1. **Ground Truth Completion Rule**: Videos transition to `annotated` only when ground truth generation is complete with quality score above threshold

2. **Automatic Validation Rule**: Videos in `annotated` status automatically enter `validating` if automatic validation is enabled

3. **HIL Readiness Rule**: Only `validated` videos can transition to `ready_for_testing`

4. **Testing Exclusivity Rule**: Videos in `in_testing` cannot be modified or used by other test sessions

5. **Quality Gate Rule**: Videos failing validation criteria must be manually reviewed before retry

## Migration Strategy

### Phase 1: Schema Migration

```sql
-- Add new columns to existing videos table
ALTER TABLE videos 
ADD COLUMN validation_status VARCHAR(50) DEFAULT 'pending',
ADD COLUMN validation_type VARCHAR(20),
ADD COLUMN validated_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN validated_by VARCHAR(36),
ADD COLUMN ground_truth_count INTEGER DEFAULT 0,
ADD COLUMN ground_truth_quality_score FLOAT,
ADD COLUMN ground_truth_completed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN hil_testing_ready BOOLEAN DEFAULT FALSE,
ADD COLUMN hil_testing_approved_by VARCHAR(36),
ADD COLUMN hil_testing_approved_at TIMESTAMP WITH TIME ZONE;

-- Create indexes
CREATE INDEX idx_video_status_validation ON videos(status, validation_status);
CREATE INDEX idx_video_hil_ready ON videos(hil_testing_ready, status);
CREATE INDEX idx_video_validation_completed ON videos(validated_at, validation_type);

-- Create new tables
CREATE TABLE video_validation_criteria (...);
CREATE TABLE video_validation_results (...);
CREATE TABLE video_status_transitions (...);
```

### Phase 2: Data Migration

```python
def migrate_existing_videos():
    """Migrate existing video statuses to new system"""
    
    # Query all existing videos
    videos = db.query(Video).all()
    
    for video in videos:
        # Create status transition record
        transition = VideoStatusTransition(
            video_id=video.id,
            from_status=video.status,
            to_status=map_legacy_status(video),
            transition_reason="schema_migration",
            triggered_by="system",
            metadata={"migration_version": "1.0"}
        )
        
        # Update video status
        video.status = map_legacy_status(video)
        video.validation_status = map_validation_status(video)
        
        # Set HIL readiness for completed videos
        if video.ground_truth_generated and video.status == "validated":
            video.hil_testing_ready = True
            
        db.add(transition)
    
    db.commit()

def map_legacy_status(video: Video) -> str:
    """Map legacy status to new status system"""
    if video.status == "uploaded" and not video.ground_truth_generated:
        return "uploaded"
    elif video.status == "uploaded" and video.ground_truth_generated:
        return "annotated"
    elif video.processing_status == "completed":
        return "validated"
    elif video.processing_status == "failed":
        return "processing_failed"
    elif video.processing_status == "pending":
        return "processing"
    else:
        return "error"
```

### Phase 3: API Compatibility

```python
class VideoResponseWithCompatibility(VideoResponse):
    """Response with backward compatibility"""
    
    # New unified fields
    status: VideoValidationStatus
    validation_status: str
    hil_testing_ready: bool
    
    # Legacy compatibility fields (computed)
    processing_status: str = Field(computed=True)
    ground_truth_generated: bool = Field(computed=True)
    
    @computed_field
    @property
    def processing_status(self) -> str:
        """Legacy processing_status computed from new status"""
        status_map = {
            "uploaded": "pending",
            "processing": "processing", 
            "annotated": "completed",
            "validated": "completed",
            "ready_for_testing": "completed",
            "processing_failed": "failed",
            "error": "failed"
        }
        return status_map.get(self.status, "pending")
    
    @computed_field  
    @property
    def ground_truth_generated(self) -> bool:
        """Legacy ground_truth_generated computed from status"""
        return self.status in ["annotated", "validated", "ready_for_testing", "tested"]
```

## Implementation Roadmap

### Week 1: Foundation
- [ ] Database schema updates and migrations
- [ ] Core status enumeration and models
- [ ] Status transition service implementation

### Week 2: Validation System  
- [ ] Validation criteria configuration
- [ ] Automatic validation service
- [ ] Manual validation workflow

### Week 3: API Development
- [ ] Video validation endpoints
- [ ] Status management APIs
- [ ] Batch operation support

### Week 4: Frontend Integration
- [ ] Updated TypeScript types
- [ ] Status display components
- [ ] Validation workflow UI

### Week 5: Testing & Migration
- [ ] Comprehensive test suite
- [ ] Data migration scripts
- [ ] Production deployment

## Success Metrics

1. **Status Clarity**: 100% consistent status representation across frontend/backend
2. **Validation Coverage**: All videos have clear validation results
3. **HIL Readiness**: Clear indication of test-ready videos  
4. **Migration Success**: Zero data loss during legacy status migration
5. **Performance**: Status queries under 100ms response time
6. **User Experience**: Intuitive status workflow for operators

This architecture provides a comprehensive solution for the video validation status contract mismatch while ensuring backward compatibility and clear upgrade path for existing deployments.