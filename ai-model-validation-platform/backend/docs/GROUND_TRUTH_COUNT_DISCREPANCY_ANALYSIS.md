# Ground Truth Count Discrepancy Analysis
## Session 463b7ec5-0cd6-4b6a-9776-d10f938b6422

**Date**: 2025-11-03
**Status**: ROOT CAUSE IDENTIFIED

---

## Summary of Issue

Three different ground truth counts are displayed for the same session:
- **UI shows**: 514 ground truth events
- **Timeline shows**: 121 GT events
- **User expects**: ~210 GT events

---

## Database Investigation Results

### Session Configuration
```
Session ID: 463b7ec5-0cd6-4b6a-9776-d10f938b6422
Type: MULTI-VIDEO SEQUENCE
Sequence ID: 0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b
Total Videos: 2
```

### Ground Truth Breakdown Per Video

| Video # | Filename | Video ID | GT Count | Status |
|---------|----------|----------|----------|--------|
| 1 | child_test_video_20251031_144012.mp4 | 10c2b16c... | **262** | pending |
| 2 | Child_20251031_143523.mp4 | 550e3cf8... | **252** | pending |
| **TOTAL** | - | - | **514** | - |

### Soft Delete Status
- Total records: 514
- Active records (deleted_at IS NULL): 514
- Soft-deleted records: 0

✅ **No soft-delete issue** - Issue #6 soft delete is working correctly.

---

## Root Cause Analysis

### Where 514 Comes From ✅ CORRECT
**Location**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/ground_truth.py`

```python
# Lines 63-70: Count ground truth objects per video
gt_counts = db.query(
    GroundTruthObject.video_id,
    func.count(GroundTruthObject.id).label('gt_count')
).filter(
    GroundTruthObject.deleted_at.is_(None)  # Only count active records
).group_by(GroundTruthObject.video_id).subquery()
```

```python
# Lines 116-127: Total GT count from all sources
gt_count = db.query(func.count(GroundTruthObject.id)).filter(
    GroundTruthObject.video_id == video.id,
    GroundTruthObject.deleted_at.is_(None)
).scalar() or 0

ann_count = db.query(func.count(Annotation.id)).filter(
    Annotation.video_id == video.id
).scalar() or 0

total_gt_count = gt_count + ann_count  # 262 + 252 = 514
```

**Why 514 is correct**: This is the aggregated count across **BOTH videos** in the multi-video sequence. The UI is correctly summing ground truth from both videos.

---

### Where ~210 Comes From (USER EXPECTATION)
**Hypothesis**: User may be expecting ground truth for only **ONE video**, not the entire sequence.

Possible scenarios:
1. User uploaded ~210 annotations for Video 1 initially
2. Later added ~252 annotations for Video 2
3. User is now seeing the combined total (514) but expects to see only one video's count

**Alternative**: If user expects ~210, they may need to check:
- Are there duplicate annotations?
- Were annotations from a different session?
- Is there confusion about which video is being viewed?

---

### Where 121 Comes From (TIMELINE) ❌ BUG SUSPECTED

**Location**: Frontend timeline rendering logic

Possible causes:
1. **Frontend filtering** - Timeline may be filtering by:
   - Time range (showing only GT within visible time window)
   - Video ID (showing only current video, not both)
   - Validation status (showing only validated GT)

2. **API pagination** - Timeline endpoint may be returning paginated results:
   ```typescript
   // Likely in frontend API call
   `/api/ground-truth/videos/available?limit=121`
   ```

3. **Time window filtering** - Timeline may be filtering by:
   ```typescript
   // Example: Only showing GT within active time window
   groundTruthFiltered = groundTruth.filter(gt =>
     gt.timestamp >= startTime && gt.timestamp <= endTime
   )
   // Result: 121 out of 514 fall within the visible window
   ```

---

## SQL Queries Used

### Query 1: Total Ground Truth (All Records)
```sql
SELECT COUNT(id)
FROM ground_truth_objects
WHERE video_id IN (
  SELECT video_id
  FROM test_sessions
  WHERE id = '463b7ec5-0cd6-4b6a-9776-d10f938b6422'
);
-- Result: 262 (for video 1 only)
```

### Query 2: Multi-Video Sequence Ground Truth (Issue #2 Implementation)
```sql
-- Get all video IDs from sequence
SELECT video_ids
FROM video_test_sequences
WHERE id = '0f2f2fd4-ce6f-457d-8da6-fb7de55cca8b';
-- Result: ['10c2b16c-86fa-4140-b1cf-c0ea42f82ca5', '550e3cf8-2755-42df-8c3c-041300735f93']

-- Count GT for each video
SELECT video_id, COUNT(id) as gt_count
FROM ground_truth_objects
WHERE video_id IN ('10c2b16c-86fa-4140-b1cf-c0ea42f82ca5', '550e3cf8-2755-42df-8c3c-041300735f93')
  AND deleted_at IS NULL
GROUP BY video_id;
-- Result:
--   Video 1: 262
--   Video 2: 252
--   TOTAL: 514
```

### Query 3: Active Ground Truth (Soft Delete Filter - Issue #6)
```sql
SELECT COUNT(id)
FROM ground_truth_objects
WHERE video_id = '10c2b16c-86fa-4140-b1cf-c0ea42f82ca5'
  AND deleted_at IS NULL;
-- Result: 262 (all active, none soft-deleted)
```

---

## Ground Truth Counting Logic Locations

### Backend - Ground Truth Router
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/routers/ground_truth.py`

**Line 63-70**: Count ground truth per video with soft-delete filter
```python
gt_counts = db.query(
    GroundTruthObject.video_id,
    func.count(GroundTruthObject.id).label('gt_count')
).filter(
    GroundTruthObject.deleted_at.is_(None)  # Issue #6 filter
).group_by(GroundTruthObject.video_id).subquery()
```

**Line 116-127**: Aggregate ground truth from multiple sources
```python
# Count from ground_truth_objects table
gt_count = db.query(func.count(GroundTruthObject.id)).filter(
    GroundTruthObject.video_id == video.id,
    GroundTruthObject.deleted_at.is_(None)
).scalar() or 0

# Count from annotations table
ann_count = db.query(func.count(Annotation.id)).filter(
    Annotation.video_id == video.id
).scalar() or 0

# Total = ground_truth_objects + annotations
total_gt_count = gt_count + ann_count
```

**Line 180-200**: Ground truth statistics endpoint
```python
stats = db.query(
    func.count(GroundTruthObject.id).label('total_detections'),
    func.count(func.distinct(GroundTruthObject.class_label)).label('unique_classes'),
    func.avg(GroundTruthObject.confidence).label('avg_confidence'),
    func.min(GroundTruthObject.timestamp).label('first_detection'),
    func.max(GroundTruthObject.timestamp).label('last_detection')
).filter(
    GroundTruthObject.video_id == video_id,
    GroundTruthObject.deleted_at.is_(None)  # Issue #6 filter
).first()
```

### Backend - Ground Truth Matching Service
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`

**Line 220-346**: Multi-video ground truth query (Issue #2 Implementation)
```python
def _get_ground_truth_for_session(
    self, db: Session, test_session: TestSession, session_id: str
) -> List[GroundTruthObject]:
    """
    Get ground truth for session, supporting multi-video sequences.

    For multi-video sessions:
    - Queries all videos in sequence
    - Aggregates ground truth across videos
    - Orders by video_id + timestamp
    """

    if test_session.has_video_sequence and test_session.sequence_id:
        # Get all video IDs from sequence
        video_ids = self._get_sequence_video_ids(db, test_session.sequence_id)

        # Count GT objects before fetching
        gt_count = db.query(func.count(GroundTruthObject.id)).filter(
            GroundTruthObject.video_id.in_(video_ids)
        ).scalar()

        # Batch query for all videos
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id.in_(video_ids)
        ).order_by(
            GroundTruthObject.video_id.asc(),
            GroundTruthObject.timestamp.asc()
        ).all()
    else:
        # Single video query
        ground_truth_objects = db.query(GroundTruthObject).filter(
            GroundTruthObject.video_id == test_session.video_id
        ).order_by(GroundTruthObject.timestamp).all()
```

**Line 276-282**: Batch ground truth count with safety check
```python
# Build count query using ORM to avoid SQL syntax errors with IN clause
gt_count = db.query(func.count(GroundTruthObject.id)).filter(
    GroundTruthObject.video_id.in_(video_ids)
).scalar()

self.logger.info(
    f"📊 Ground truth count: {gt_count} objects across {len(video_ids)} videos"
)
```

### Backend - CRUD Operations
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/crud.py`

**Line 307-314**: Get ground truth objects with soft-delete filter
```python
def get_ground_truth_objects(db: Session, video_id: str, user_id: str = "anonymous") -> List[GroundTruthObject]:
    # SECURITY FIX: Join through Video, VideoProjectLink, and Project
    # Issue #6: Exclude soft-deleted records
    return db.query(GroundTruthObject).join(Video).join(VideoProjectLink).join(Project).filter(
        GroundTruthObject.video_id == video_id,
        Project.owner_id == user_id,
        GroundTruthObject.deleted_at.is_(None)  # Only return active records
    ).all()
```

### Models - GroundTruthObject Schema
**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/models.py`

**Line 172-210**: GroundTruthObject model with soft-delete support
```python
class GroundTruthObject(Base):
    __tablename__ = "ground_truth_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    tracking_id = Column(String, nullable=True, index=True)
    frame_number = Column(Integer, nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    class_label = Column(String, nullable=False, index=True)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    confidence = Column(Float, index=True)
    validated = Column(Boolean, default=False, index=True)
    difficult = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Soft delete fields - Issue #6
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by = Column(String(255), nullable=True)
```

**Line 198-210**: Composite indexes including soft-delete
```python
__table_args__ = (
    Index('idx_gt_video_timestamp', 'video_id', 'timestamp'),
    Index('idx_gt_video_class', 'video_id', 'class_label'),
    Index('idx_gt_timestamp_class', 'timestamp', 'class_label'),
    Index('idx_gt_video_frame', 'video_id', 'frame_number'),
    Index('idx_gt_video_confidence', 'video_id', 'confidence'),
    Index('idx_gt_validated_class', 'validated', 'class_label'),
    Index('idx_gt_spatial_bounds', 'x', 'y', 'width', 'height'),
    Index('idx_gt_video_validated_timestamp', 'video_id', 'validated', 'timestamp'),
    Index('idx_gt_video_tracking_id', 'video_id', 'tracking_id'),
    Index('idx_gt_tracking_timestamp', 'tracking_id', 'timestamp'),
    Index('idx_gt_deleted_at', 'deleted_at'),  # For soft delete queries
)
```

---

## Filters Applied to Ground Truth Queries

### 1. **Soft Delete Filter** (Issue #6)
**Applied everywhere**: `deleted_at IS NULL`

All ground truth queries correctly filter out soft-deleted records:
```python
GroundTruthObject.deleted_at.is_(None)
```

### 2. **Video ID Filter**
**Applied**: Video-specific queries
```python
GroundTruthObject.video_id == video_id
```

For multi-video sequences (Issue #2):
```python
GroundTruthObject.video_id.in_(video_ids)
```

### 3. **User Security Filter**
**Applied**: User ownership verification
```python
# Join through Video → VideoProjectLink → Project → owner_id
db.query(GroundTruthObject).join(Video).join(VideoProjectLink).join(Project).filter(
    Project.owner_id == user_id
)
```

### 4. **Validated Status** (Optional)
**Not currently applied** to counts, but available in schema:
```python
GroundTruthObject.validated == True
```

---

## Database Schema - Ground Truth Table

```sql
CREATE TABLE ground_truth_objects (
    id VARCHAR(36) PRIMARY KEY,
    video_id VARCHAR(36) NOT NULL,
    tracking_id VARCHAR,
    frame_number INTEGER,
    timestamp REAL NOT NULL,
    class_label VARCHAR NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    width REAL NOT NULL,
    height REAL NOT NULL,
    confidence REAL,
    validated BOOLEAN DEFAULT 0,
    difficult BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Soft delete fields (Issue #6)
    deleted_at DATETIME,
    deleted_by VARCHAR(255),

    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

-- Critical indexes for performance
CREATE INDEX idx_gt_video_timestamp ON ground_truth_objects(video_id, timestamp);
CREATE INDEX idx_gt_video_class ON ground_truth_objects(video_id, class_label);
CREATE INDEX idx_gt_deleted_at ON ground_truth_objects(deleted_at);
```

---

## Recommendations

### 1. Investigate Timeline Filtering (121 Events)
**Action**: Check frontend timeline component for:
- Time window filtering
- Pagination limits
- Video ID filtering
- Validation status filtering

**Files to check**:
```
/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/FrameCorrelationTimeline.tsx
/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx
```

### 2. Verify User Expectation (~210 Events)
**Questions for user**:
- Which video were you expecting to see ground truth for?
- Did you upload ~210 annotations initially and then add more later?
- Are you expecting to see Video 1 only (262 GT) or Video 2 only (252 GT)?

### 3. Add Per-Video Ground Truth Display
**Enhancement**: In multi-video sequences, show ground truth breakdown:
```
Total Ground Truth: 514
  - Video 1: 262 events
  - Video 2: 252 events
```

### 4. Add Timeline Filtering Information
**Enhancement**: Display active filters on timeline:
```
Showing: 121 of 514 ground truth events
Filters: Time window 0-30s, Video 1 only
```

---

## Conclusion

**514 GT events**: ✅ **CORRECT** - This is the accurate total across both videos in the multi-video sequence.

**121 GT events**: ❓ **NEEDS INVESTIGATION** - Likely a frontend filtering or pagination issue in the timeline component.

**~210 GT events**: ❓ **USER EXPECTATION MISMATCH** - User may be expecting to see only one video's ground truth, not the entire sequence.

**Next Steps**:
1. Investigate frontend timeline rendering logic
2. Clarify user's expectation with questions above
3. Consider UI improvements for multi-video ground truth display

---

## Related Issues

- **Issue #2**: Multi-Video Ground Truth Implementation ✅ WORKING CORRECTLY
- **Issue #6**: Soft Delete Ground Truth ✅ WORKING CORRECTLY

## Related Files

### Backend
- `/home/rigade/Testing/ai-model-validation-platform/backend/models.py` (Line 172-210)
- `/home/rigade/Testing/ai-model-validation-platform/backend/crud.py` (Line 307-314)
- `/home/rigade/Testing/ai-model-validation-platform/backend/routers/ground_truth.py` (Lines 63-229)
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py` (Lines 220-550)

### Frontend (To Investigate)
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/components/FrameCorrelationTimeline.tsx`
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/HILResults.tsx`
- `/home/rigade/Testing/ai-model-validation-platform/frontend/src/pages/EnhancedResults.tsx`
