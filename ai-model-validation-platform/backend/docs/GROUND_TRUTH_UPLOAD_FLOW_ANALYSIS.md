# Ground Truth Upload and Verification Flow Analysis

## Executive Summary

**CRITICAL FINDING**: The codebase does NOT have a CSV upload endpoint for ground truth data. Ground truth is generated ONLY via automated YOLO inference. There is no CSV parsing, validation, or manual upload functionality.

---

## Complete Ground Truth Flow Analysis

### 1. Ground Truth Data Sources

#### A. Automated YOLO Generation (PRIMARY METHOD)
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_service.py`

```python
class GroundTruthService:
    def __init__(self):
        # Loads YOLO model for automated detection
        self.model = YOLO('yolo11l.pt')  # or yolov8n.pt

        # VRU class mapping
        self.vru_classes = {
            0: 'pedestrian',      # person -> pedestrian
            1: 'cyclist',         # bicycle -> cyclist
            3: 'motorcyclist'     # motorcycle -> motorcyclist
        }
```

**Flow**:
1. Video uploaded via `/api/videos/upload`
2. Background task triggers YOLO processing
3. Frame-by-frame detection generates `GroundTruthObject` records
4. Direct database insertion via `crud.create_ground_truth_object()`

#### B. Annotation API (SECONDARY METHOD)
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/unified_annotation_endpoints.py`

**Endpoint**: `POST /api/annotations/videos/{video_id}/annotations`

**Input Schema**:
```python
class AnnotationCreate(BaseModel):
    detection_id: Optional[str]
    frame_number: int
    timestamp: float
    vru_type: VRUTypeEnum  # pedestrian, cyclist, motorcyclist
    bounding_box: BoundingBox  # {x, y, width, height}
    confidence: Optional[float]
```

**Database Storage**:
- Stores to `annotations` table (NOT `ground_truth_objects`)
- Manual annotations are separate from YOLO ground truth
- Can export to JSON/CSV/COCO/YOLO/Pascal formats

---

## 2. Database Schema Analysis

### GroundTruthObject Model
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/models.py:172-210`

```python
class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    tracking_id = Column(String, nullable=True)  # VRU tracking across frames
    frame_number = Column(Integer, nullable=True)
    timestamp = Column(Float, nullable=False)
    class_label = Column(String, nullable=False)  # pedestrian, cyclist, etc.

    # Bounding box coordinates (NEW: individual columns)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)

    # Legacy field (kept for backward compatibility)
    bounding_box = Column(JSON)  # {"x": 0, "y": 0, "width": 100, "height": 100}

    confidence = Column(Float)
    validated = Column(Boolean, default=False)
    difficult = Column(Boolean, default=False)

    # Soft delete fields - Issue #6
    deleted_at = Column(DateTime, nullable=True)  # NULL = active
    deleted_by = Column(String, nullable=True)
```

### Annotation Model (Separate Table)
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/models.py:540-578`

```python
class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(String(36), primary_key=True)
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    detection_id = Column(String(36), nullable=True)  # DET_PED_0001
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    vru_type = Column(String, nullable=False)
    bounding_box = Column(JSON, nullable=False)

    # Quality flags
    occluded = Column(Boolean, default=False)
    truncated = Column(Boolean, default=False)
    difficult = Column(Boolean, default=False)

    # Validation
    validated = Column(Boolean, default=False)
    annotator = Column(String)
```

**KEY DIFFERENCE**:
- `ground_truth_objects` = YOLO-generated detections
- `annotations` = Manual annotations from UI

---

## 3. Ground Truth Retrieval Flow

### A. Available Videos Endpoint
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/ground_truth.py:19-156`

**Endpoint**: `GET /api/ground-truth/videos/available`

**Query Logic** (Lines 64-106):
```python
# Count ground truth objects per video (EXCLUDES soft-deleted)
gt_counts = db.query(
    GroundTruthObject.video_id,
    func.count(GroundTruthObject.id).label('gt_count')
).filter(
    GroundTruthObject.deleted_at.is_(None)  # Only active records
).group_by(GroundTruthObject.video_id).subquery()

# Count detection events per video
de_counts = db.query(
    DetectionEvent.video_id,
    func.count(DetectionEvent.id).label('de_count')
).group_by(DetectionEvent.video_id).subquery()

# Count annotations per video
ann_counts = db.query(
    Annotation.video_id,
    func.count(Annotation.id).label('ann_count')
).group_by(Annotation.video_id).subquery()

# Build query with OR condition
query = base_query.outerjoin(gt_counts).outerjoin(de_counts).outerjoin(ann_counts).filter(
    or_(
        gt_counts.c.gt_count != None,
        de_counts.c.de_count != None,
        ann_counts.c.ann_count != None
    )
)
```

**Return Structure**:
```python
VideoFile(
    id=video.id,
    filename=video.filename,
    ground_truth_count=total_gt_count,  # Sum of GT + annotations
    ground_truth_generated=video.ground_truth_generated,
    validation_status=video.validation_status
)
```

### B. Video Stats Endpoint
**Endpoint**: `GET /api/ground-truth/videos/{video_id}/stats`

**Returns**:
```json
{
  "statistics": {
    "total_detections": 150,
    "unique_classes": 3,
    "average_confidence": 0.87,
    "first_detection_time": 2.5,
    "last_detection_time": 45.8,
    "temporal_coverage": 43.3
  },
  "class_distribution": {
    "pedestrian": 80,
    "cyclist": 50,
    "motorcyclist": 20
  }
}
```

---

## 4. Video Association Logic

### Video-Project Relationship
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/models.py:600-622`

```python
class VideoProjectLink(Base):
    """Many-to-many relationship: Videos can be in multiple projects"""
    __tablename__ = "video_project_links"

    video_id = Column(String(36), ForeignKey("videos.id"))
    project_id = Column(String(36), ForeignKey("projects.id"))
    assignment_reason = Column(Text)
    intelligent_match = Column(Boolean, default=True)
    confidence_score = Column(Float)
```

**Assignment Flow** (crud.py:116-137):
```python
def assign_video_to_project(db, video_id, project_id, assignment_reason, confidence_score):
    # Check if assignment already exists
    existing = db.query(VideoProjectLink).filter(
        VideoProjectLink.video_id == video_id,
        VideoProjectLink.project_id == project_id
    ).first()

    if existing:
        return existing

    db_link = VideoProjectLink(
        video_id=video_id,
        project_id=project_id,
        assignment_reason=assignment_reason,
        confidence_score=confidence_score
    )
    db.add(db_link)
    db.commit()
```

**Ground Truth Inheritance**:
- Ground truth is attached to `video_id`
- When video is assigned to project, ground truth follows
- Same ground truth shared across all projects containing the video

---

## 5. Data Validation Steps

### A. CRUD-Level Validation
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/crud.py:278-305`

```python
def create_ground_truth_object(
    db, video_id, timestamp, class_label,
    x, y, width, height, confidence,
    frame_number=None, validated=True, difficult=False, bounding_box=None
):
    # Create bounding_box dict for backward compatibility
    if bounding_box is None:
        bounding_box = {"x": x, "y": y, "width": width, "height": height}

    db_object = GroundTruthObject(
        video_id=video_id,
        frame_number=frame_number,
        timestamp=timestamp,
        class_label=class_label,
        x=x, y=y, width=width, height=height,
        bounding_box=bounding_box,  # Legacy JSON field
        confidence=confidence,
        validated=validated,
        difficult=difficult
    )
    db.add(db_object)
    db.commit()
    db.refresh(db_object)
    return db_object
```

**NO INPUT VALIDATION**:
- No range checks (x, y, width, height can be negative)
- No class_label enum validation
- No confidence range validation (should be 0.0-1.0)
- No timestamp validation

### B. Annotation API Validation
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/src/api/unified_annotation_endpoints.py:51-81`

```python
def validate_annotation_data(annotation_data, video_id, db):
    errors = []

    # Validate video exists
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        errors.append(f"Video with ID {video_id} does not exist")

    # Validate frame number and timestamp
    if annotation_data.frame_number < 0:
        errors.append("Frame number must be non-negative")

    if annotation_data.timestamp < 0:
        errors.append("Timestamp must be non-negative")

    # Validate bounding box
    bbox = annotation_data.bounding_box
    if bbox.x < 0 or bbox.y < 0:
        errors.append("Bounding box coordinates must be non-negative")

    if bbox.width <= 0 or bbox.height <= 0:
        errors.append("Bounding box dimensions must be positive")

    return {"valid": len(errors) == 0, "errors": errors}
```

**VALIDATION GAPS**:
- No maximum bounds validation (x+width, y+height can exceed frame dimensions)
- No confidence score validation
- No class label enum validation

---

## 6. Potential Bugs and Data Loss Issues

### BUG #1: No CSV Upload Endpoint
**Impact**: CRITICAL
**Description**: System claims to support ground truth import but has no endpoint for it.
**Evidence**: No routes for CSV upload in any router file.
**Fix Required**: Implement CSV upload endpoint with proper validation.

### BUG #2: Missing Input Validation in CRUD
**Impact**: HIGH
**File**: `crud.py:278-305`
**Issues**:
- Negative coordinates allowed
- Bounding box can exceed frame dimensions
- Invalid confidence scores accepted (e.g., 1.5 or -0.5)
- No class_label enum validation

**Example Bad Data**:
```python
create_ground_truth_object(
    db, video_id="test",
    timestamp=-5.0,  # Negative timestamp ❌
    class_label="invalid_class",  # Not a valid VRU type ❌
    x=-100, y=-100,  # Negative coordinates ❌
    width=-50, height=-50,  # Negative dimensions ❌
    confidence=2.5  # Out of range ❌
)
```

### BUG #3: Soft Delete Not Applied Consistently
**Impact**: MEDIUM
**Description**: Some queries check `deleted_at.is_(None)`, others don't.
**Files**:
- ✅ `routers/ground_truth.py:69` - Filters soft-deleted records
- ✅ `routers/ground_truth.py:118` - Filters soft-deleted records
- ❌ `crud.py:307-314` - Does NOT filter soft-deleted records
- ❌ Legacy endpoints may return soft-deleted data

**Fix Required**: Add consistent soft delete filtering in all ground truth queries.

### BUG #4: Bounding Box Data Duplication
**Impact**: LOW (Data inconsistency risk)
**Description**: Bounding box stored in TWO places:
1. Individual columns: `x, y, width, height`
2. JSON column: `bounding_box = {"x": 0, "y": 0, ...}`

**Risk**: Updates to one may not update the other, causing data inconsistency.

**Evidence** (crud.py:283-286):
```python
db_object = GroundTruthObject(
    x=x, y=y, width=width, height=height,  # Individual columns
    bounding_box=bounding_box,  # JSON column (duplicate data)
)
```

### BUG #5: Video Association Race Condition
**Impact**: LOW
**File**: `crud.py:116-137`
**Issue**: Check-then-create pattern without proper locking

```python
# Check if assignment exists
existing = db.query(VideoProjectLink).filter(...).first()
if existing:
    return existing

# Race condition here - another thread could create the same link
db_link = VideoProjectLink(...)
db.add(db_link)
db.commit()  # May raise IntegrityError if another thread created it
```

**Fix**: Add database-level unique constraint and handle IntegrityError.

---

## 7. How video_id Gets Associated

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. VIDEO UPLOAD                                              │
│    POST /api/videos/upload                                   │
│    ↓                                                          │
│    Creates Video record with:                                │
│    - id = UUID()                                             │
│    - project_id = provided or CENTRAL_STORE_PROJECT_ID      │
│    - file_path = "/uploads/{filename}"                       │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. YOLO PROCESSING (Background Task)                        │
│    services/ground_truth_service.py::_process_video()       │
│    ↓                                                          │
│    For each detection:                                        │
│      crud.create_ground_truth_object(                        │
│          video_id=video.id,  ← Associates with video         │
│          timestamp=frame_time,                               │
│          class_label="pedestrian",                           │
│          x=100, y=200, width=50, height=80,                  │
│          confidence=0.85                                     │
│      )                                                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. DATABASE STORAGE                                          │
│    ground_truth_objects table:                              │
│    ┌──────────┬──────────┬───────────┬───────┬────┐        │
│    │ id       │ video_id │ timestamp │ class │ x  │        │
│    ├──────────┼──────────┼───────────┼───────┼────┤        │
│    │ uuid-1   │ vid-123  │ 2.5       │ ped   │ 100│        │
│    │ uuid-2   │ vid-123  │ 3.2       │ cyc   │ 250│        │
│    └──────────┴──────────┴───────────┴───────┴────┘        │
│                   ↑                                          │
│            Foreign key to videos.id                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. RETRIEVAL                                                 │
│    GET /api/ground-truth/videos/available                   │
│    ↓                                                          │
│    SELECT videos.*, COUNT(gt.id) as gt_count                │
│    FROM videos                                               │
│    LEFT JOIN ground_truth_objects gt                        │
│      ON videos.id = gt.video_id                             │
│      AND gt.deleted_at IS NULL  ← Filters soft-deleted      │
│    WHERE gt_count > 0                                        │
│    GROUP BY videos.id                                        │
└─────────────────────────────────────────────────────────────┘
```

### Association Rules

1. **Direct Foreign Key**: `ground_truth_objects.video_id` → `videos.id`
2. **Cascade Behavior**: When video deleted, ground truth CASCADE deletes
3. **No Orphan Prevention**: Can delete video while ground truth in use
4. **Project Independence**: Ground truth belongs to video, not project
5. **Multi-Project Sharing**: Same ground truth visible in all projects containing the video

---

## 8. Export/Import Functionality

### Export Endpoints (WORKING)
**File**: `src/api/unified_annotation_endpoints.py:435-679`

**Endpoint**: `GET /api/annotations/videos/{video_id}/annotations/export`

**Supported Formats**:
- ✅ JSON (custom format)
- ✅ CSV (flat structure)
- ✅ COCO (Microsoft format)
- ✅ YOLO (text files per frame)
- ✅ Pascal VOC (XML format)

### Import Endpoints (MISSING)
**Status**: ❌ NOT IMPLEMENTED

**Evidence**:
```bash
$ grep -r "UploadFile.*csv\|import.*csv" backend/
# No results - no CSV upload handlers found
```

**Expected But Missing**:
- `POST /api/ground-truth/videos/{video_id}/import` - Import ground truth from CSV
- `POST /api/annotations/videos/{video_id}/import` - Import annotations from JSON/CSV

---

## 9. Recommendations

### CRITICAL (P0) - Must Fix Before Production

1. **Implement CSV Upload Endpoint**
   ```python
   @router.post("/videos/{video_id}/ground-truth/import")
   async def import_ground_truth_csv(
       video_id: str,
       file: UploadFile = File(...),
       db: Session = Depends(get_db)
   ):
       # Parse CSV
       # Validate each row
       # Bulk insert to ground_truth_objects
       pass
   ```

2. **Add Input Validation to CRUD Layer**
   ```python
   def create_ground_truth_object(db, video_id, timestamp, class_label, x, y, width, height, confidence, ...):
       # Validate video exists
       if not db.query(Video).filter(Video.id == video_id).first():
           raise ValueError(f"Video {video_id} not found")

       # Validate timestamp
       if timestamp < 0:
           raise ValueError("Timestamp must be non-negative")

       # Validate bounding box
       if x < 0 or y < 0:
           raise ValueError("Coordinates must be non-negative")
       if width <= 0 or height <= 0:
           raise ValueError("Dimensions must be positive")

       # Validate confidence
       if not (0.0 <= confidence <= 1.0):
           raise ValueError("Confidence must be between 0.0 and 1.0")

       # Validate class label
       VALID_CLASSES = ['pedestrian', 'cyclist', 'motorcyclist']
       if class_label not in VALID_CLASSES:
           raise ValueError(f"Invalid class label: {class_label}")
   ```

### HIGH (P1) - Important Quality Issues

3. **Fix Soft Delete Inconsistency**
   - Add default scope to GroundTruthObject model
   - OR add explicit soft delete filtering to all queries

4. **Remove Bounding Box Duplication**
   - Deprecate JSON `bounding_box` column
   - Use only individual `x, y, width, height` columns
   - Create migration to remove old column

### MEDIUM (P2) - Nice to Have

5. **Add Database Constraints**
   ```sql
   ALTER TABLE ground_truth_objects
   ADD CONSTRAINT check_positive_dimensions
   CHECK (width > 0 AND height > 0);

   ADD CONSTRAINT check_non_negative_coords
   CHECK (x >= 0 AND y >= 0);

   ADD CONSTRAINT check_confidence_range
   CHECK (confidence BETWEEN 0.0 AND 1.0);
   ```

6. **Add Video Association Unique Constraint**
   ```sql
   ALTER TABLE video_project_links
   ADD CONSTRAINT unique_video_project
   UNIQUE (video_id, project_id);
   ```

---

## 10. Testing Requirements

### Unit Tests Needed

1. **CSV Upload Validation**
   - Valid CSV with all fields
   - CSV with missing required fields
   - CSV with invalid coordinates
   - CSV with out-of-range confidence
   - CSV with unknown class labels

2. **Bounding Box Validation**
   - Negative coordinates
   - Negative dimensions
   - Coordinates exceeding frame dimensions
   - Zero width/height

3. **Soft Delete Filtering**
   - Verify deleted records excluded from counts
   - Verify deleted records excluded from retrieval
   - Verify soft delete via API endpoint

### Integration Tests Needed

1. **End-to-End Upload Flow**
   - Upload video → YOLO processing → ground truth creation
   - Upload CSV → validation → database insertion
   - Query ground truth → verify correct counts

2. **Multi-Project Ground Truth Sharing**
   - Create video in project A
   - Generate ground truth
   - Assign video to project B
   - Verify ground truth visible in both projects

---

## Conclusion

The system has a **partial implementation** of ground truth management:

✅ **WORKING**:
- Automated YOLO generation
- Database storage with soft delete
- Retrieval and filtering APIs
- Export to multiple formats
- Soft delete endpoint

❌ **MISSING**:
- CSV upload endpoint
- Input validation in CRUD layer
- Consistent soft delete filtering
- Import functionality

⚠️ **RISKS**:
- Invalid data can be stored (negative coords, invalid classes)
- Soft-deleted records may leak in some queries
- No way to manually import ground truth from external sources

**Priority**: Implement CSV upload with proper validation before production deployment.
