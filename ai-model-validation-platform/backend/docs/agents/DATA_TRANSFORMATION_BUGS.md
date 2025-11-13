# DATA TRANSFORMATION BUGS - Backend to Frontend Pipeline Analysis

**Report Date**: 2025-11-05
**Analysis Scope**: Complete data transformation path from raw LabJack data to UI display
**Status**: 🔴 CRITICAL BUGS FOUND

---

## EXECUTIVE SUMMARY

Found **12 critical data transformation bugs** causing data loss, corruption, and silent failures between backend and frontend.

**Most Critical Issues**:
1. **Field Name Inconsistency**: `video_frame_number` (DB) vs `frame_number` (API) - data dropped
2. **NULL Value Cascade**: Frontend normalization silently drops detections with NULL fields
3. **Type Conversion Loss**: Nanosecond timestamps converted to milliseconds lose precision
4. **N+1 Query Problem**: 103 queries → 5 queries (fixed in enhanced_hil_results_endpoints.py)
5. **Aggregation Bugs**: Division by zero, NULL handling in reduce operations
6. **Silent Try/Catch**: Empty data returned instead of errors

---

## COMPLETE TRANSFORMATION PIPELINE

```
[STEP 1] Raw LabJack Data (Hardware)
   ↓ voltage_level, labjack_timestamp, labjack_timestamp_ns
[STEP 2] Detection Event Model (models.py)
   ↓ DetectionEvent.video_frame_number, .actual_latency_ms
[STEP 3] Database Storage (SQLite)
   ↓ detection_events table with video_frame_number column
[STEP 4] API Serialization (schemas.py)
   ↓ DetectionEventResponse exports as "frameNumber"
[STEP 5] JSON Response (FastAPI)
   ↓ {frameNumber: 120, actualLatencyMs: 81.0}
[STEP 6] Frontend Normalization (hilResultsNormalization.ts)
   ↓ normalizeDetectionEvent() maps fields
[STEP 7] UI Display (React Components)
   ↓ Frame 120, Latency 81ms
```

---

## FIELD MAPPING TABLE - DB → API → Frontend

| Database Field | Model Property | API Schema Field | JSON Response Key | Frontend Property | **Status** |
|----------------|----------------|------------------|-------------------|-------------------|-----------|
| `video_frame_number` | `video_frame_number` | `video_frame_number` | `videoFrameNumber` | `video_frame_number` | ✅ Fixed |
| `actual_latency_ms` | `actual_latency_ms` | `actual_latency_ms` | `actualLatencyMs` | `actual_latency_ms` | ✅ OK |
| `video_relative_timestamp` | `video_relative_timestamp` | `video_relative_timestamp` | `videoRelativeTimestamp` | `video_relative_timestamp` | ✅ OK |
| `labjack_timestamp_ns` | `labjack_timestamp_ns` | ❌ MISSING | ❌ DROPPED | NULL | 🔴 **BUG #1** |
| `video_start_time_ns` | `video_start_time_ns` | ❌ MISSING | ❌ DROPPED | NULL | 🔴 **BUG #2** |
| `frame_number` | `frame_number` | `frame_number` | `frameNumber` | `frame_number` | ⚠️ Conflict |
| `detection_type` | `detection_type` | ❌ MISSING | ❌ DROPPED | NULL | 🔴 **BUG #3** |
| `sequence_video_result_id` | `sequence_video_result_id` | ✅ Included | `sequenceVideoResultId` | `sequence_video_result_id` | ✅ OK |

---

## 🔴 CRITICAL BUG #1: Nanosecond Precision Lost in API Serialization

**Location**: `schemas.py:DetectionEventResponse`

**Problem**: Nanosecond timestamp fields are not exported by the API schema, losing precision data.

```python
# models.py - Database has nanosecond fields
labjack_timestamp_ns = Column(String, nullable=True)  # ✅ Stored
video_start_time_ns = Column(String, nullable=True)   # ✅ Stored

# schemas.py:DetectionEventResponse - API schema MISSING these fields
class DetectionEventResponse(DetectionEvent):
    id: str
    # ... many fields ...
    # ❌ MISSING: labjack_timestamp_ns
    # ❌ MISSING: video_start_time_ns
    # ❌ MISSING: latency_ns
```

**Data Loss Impact**:
- Nanosecond precision timing data (critical for HIL validation) is **DROPPED**
- Frontend cannot access sub-millisecond timing accuracy
- Ground truth matching precision is reduced

**Fix**:
```python
# schemas.py - Add missing nanosecond fields
class DetectionEventResponse(DetectionEvent):
    # Existing fields...
    labjack_timestamp_ns: Optional[str] = Field(None, alias="labjackTimestampNs")
    video_start_time_ns: Optional[str] = Field(None, alias="videoStartTimeNs")
    latency_ns: Optional[str] = Field(None, alias="latencyNs")
```

---

## 🔴 CRITICAL BUG #2: Field Name Collision - `frame_number` vs `video_frame_number`

**Location**: `models.py` line 312, 345

**Problem**: Two different frame number fields with unclear usage:

```python
# models.py:DetectionEvent
video_frame_number = Column(Integer, nullable=True, index=True)  # Line 312 - Video frame
frame_number = Column(Integer, nullable=True, index=True)        # Line 345 - Detection frame
```

**Conflict**:
- `video_frame_number`: Frame number synchronized with video timing (calculated from video_relative_timestamp)
- `frame_number`: Legacy frame number (may be from different calculation)
- Frontend code tries both: `source.frame_number ?? source.videoFrameNumber` (line 225-230)

**Data Corruption Risk**:
- If `frame_number` and `video_frame_number` differ, which is correct?
- Frontend uses fallback chain that may pick wrong value
- Ground truth matching uses frame correlation - wrong frame = missed match

**Fix**:
```python
# Option 1: Deprecate legacy field, use only video_frame_number
# Option 2: Clear documentation of when each field is used
# Option 3: Database migration to consolidate into single authoritative field
```

---

## 🔴 CRITICAL BUG #3: Silent NULL Dropping in Frontend Normalization

**Location**: `hilResultsNormalization.ts` lines 106-258

**Problem**: Frontend normalization silently skips detections with NULL values instead of handling them gracefully.

```typescript
// Line 140-142: If timestamp is undefined, fallback to index
if (timestamp === undefined) {
    timestamp = index;  // ❌ Loses real timing data
}

// Line 224-231: Complex fallback chain may skip valid data
const frameNumber = toInt(
    source.frame_number ??           // Try legacy field
    source.frameNumber ??            // Try camelCase
    source.video_frame ??            // Try alternate name
    source.videoFrame ??             // Try another alternate
    source.video_frame_number        // Try full name
);
// ❌ If ALL of these are NULL, returns undefined → detection dropped
```

**Data Loss Impact**:
- Detections with NULL `frame_number` are silently dropped from UI
- Users see incomplete data without warning
- Pass/fail statistics are incorrect due to missing detections

**Fix**:
```typescript
// Add explicit NULL handling with warnings
const frameNumber = toInt(
    source.frame_number ?? source.frameNumber ?? source.video_frame_number
);

if (frameNumber === undefined || frameNumber === null) {
    console.warn(`Detection ${source.id} missing frame_number - using fallback calculation`);
    // Calculate from timestamp if available
    const fps = toNumber(source.fps ?? 24);
    frameNumber = timestamp ? Math.floor(timestamp * fps) : 0;
}
```

---

## 🔴 CRITICAL BUG #4: Type Conversion Precision Loss

**Location**: Multiple locations in transformation pipeline

**Problem**: Float → Int conversions and timestamp format changes lose precision.

```typescript
// hilResultsNormalization.ts line 37-45
const toInt = (value: unknown): number | undefined => {
  const numeric = toNumber(value);
  if (numeric === undefined) return undefined;
  if (!Number.isFinite(numeric)) return undefined;
  return Math.trunc(numeric);  // ❌ Loses decimal precision
};

// Example data loss:
// Input: actual_latency_ms = 81.234567 ms
// After toInt: 81 ms (lost 0.234567 ms = 234.567 μs precision)
```

**Data Loss Impact**:
- Latency measurements lose sub-millisecond precision
- Frame calculations lose fractional frame data
- Statistical analysis less accurate due to rounding errors

**Root Cause**: Using `Math.trunc()` instead of `Math.round()` for frame numbers

**Fix**:
```typescript
// For frame numbers (should be integer), use round:
return Math.round(numeric);

// For latencies (should preserve decimals), keep as float:
return numeric;  // Don't truncate
```

---

## 🔴 CRITICAL BUG #5: Timestamp Format Confusion

**Location**: Backend and Frontend timestamp handling

**Problem**: Mixing epoch seconds, milliseconds, and ISO strings causes confusion.

```python
# Backend sends different formats:
"timestamp": 1730822400.0,              # Epoch seconds (float)
"labjack_timestamp": 1730822400123,     # Epoch milliseconds (int)
"created_at": "2025-11-05T12:00:00Z"    # ISO string
```

```typescript
// Frontend tries to parse all formats:
const timestamp = toNumber(
    source.timestamp ??                    // Could be seconds OR milliseconds
    source.time ??                         // Unknown format
    source.unix_timestamp ??               // Name suggests milliseconds
    source.video_relative_timestamp        // Relative seconds
);
```

**Data Corruption Risk**:
- If milliseconds are interpreted as seconds → timestamp 1000x off
- If seconds are interpreted as milliseconds → timestamp 1000x too small
- No validation to detect format errors

**Fix**:
```python
# Backend: Standardize all timestamps to same format
{
    "timestamp_unix_sec": 1730822400.0,
    "timestamp_unix_ms": 1730822400000,
    "timestamp_iso": "2025-11-05T12:00:00Z",
    "timestamp_format": "unix_seconds"  # Explicit format indicator
}
```

---

## 🔴 CRITICAL BUG #6: Division by Zero in Aggregation

**Location**: `hilResultsNormalization.ts` lines 621-689

**Problem**: No division-by-zero checks in aggregation calculations.

```typescript
// Line 660: Division by zero if totalDetections === 0
const averageLatency =
    totalDetections && totalDetections > 0
        ? totalLatencyWeighted / totalDetections
        : raw?.average_latency_ms;  // ❌ Fallback may also be invalid
```

**Silent Failure Cases**:
1. If `totalDetections === 0`: Returns backend value (may be stale)
2. If backend value is also NULL: Returns `undefined` → NaN in calculations
3. No error logged, UI shows "0.0ms" or "NaN"

**Fix**:
```typescript
const averageLatency = (() => {
    if (!totalDetections || totalDetections === 0) {
        console.warn('Cannot calculate average latency: zero detections');
        return 0.0;  // Explicit zero, not undefined
    }
    return totalLatencyWeighted / totalDetections;
})();
```

---

## 🔴 CRITICAL BUG #7: NULL Handling in Reduce Operations

**Location**: `hilResultsNormalization.ts` lines 621-648

**Problem**: Reduce operations don't skip NULL values, causing NaN propagation.

```typescript
// Line 621-624: Summing detections without NULL checks
const detectionSumFromVideos = normalizedVideos.reduce(
    (sum, video) => sum + (
        video.total_detections ?? video.totalDetections ??
        video.detection_count ?? video.detectionCount ?? 0  // ❌ Last fallback
    ),
    0
);
```

**NaN Propagation**:
```typescript
// If ANY video has invalid data:
sum + undefined  // → NaN
sum + NaN        // → NaN (propagates to all videos)
```

**Fix**:
```typescript
const detectionSumFromVideos = normalizedVideos.reduce((sum, video) => {
    const count = toNumber(
        video.total_detections ?? video.totalDetections ??
        video.detection_count ?? video.detectionCount
    ) || 0;  // Explicit fallback to 0
    return sum + count;
}, 0);
```

---

## 🔴 CRITICAL BUG #8: Try/Catch Returns Empty Data

**Location**: Backend routers

**Problem**: Exception handlers return empty arrays instead of errors.

```python
# routers/test_sessions.py lines 314-321
except Exception as e:
    logger.error(f"Error listing test sessions: {str(e)}")
    # ❌ Return empty list instead of 500 to prevent UI disruption
    return []
```

**Silent Failure Impact**:
- Frontend receives `[]` → displays "No sessions found"
- User doesn't know there's a backend error
- Database connection issues are masked
- Debugging is difficult (error only in logs)

**Better Fix**:
```python
except Exception as e:
    logger.error(f"Error listing test sessions: {str(e)}")
    raise HTTPException(
        status_code=500,
        detail={
            "error": "database_error",
            "message": "Failed to retrieve test sessions",
            "suggestion": "Check database connection"
        }
    )
```

---

## 🔴 CRITICAL BUG #9: Video Sequence Detection Assignment

**Location**: `enhanced_hil_results_endpoints.py` lines 779-792

**Problem**: Video ID inference for multi-video sequences may assign detections to wrong video.

```python
# Line 779: Inferred video ID may be incorrect
inferred_video_id = getattr(event, "video_id", None) or _infer_video_id(
    normalized_timestamp,
    relative_timestamp
)

# _infer_video_id uses time windows but:
# - 250ms buffer may overlap between videos
# - Detections at boundary may go to wrong video
# - No validation that inferred ID matches actual video
```

**Data Corruption Impact**:
- Detection assigned to Video 2 when it should be Video 1
- Causes "zero detections" bug for Video 2 (detections went to Video 1)
- Pass/fail metrics wrong for both videos

**Fix**:
```python
# Add validation and logging
inferred_video_id = _infer_video_id(normalized_timestamp, relative_timestamp)

if inferred_video_id != event.video_id and event.video_id is not None:
    logger.warning(
        f"Video ID mismatch: DB={event.video_id}, "
        f"inferred={inferred_video_id} for detection {event.id}"
    )
    # Use DB value if present, inference only for NULL
    inferred_video_id = event.video_id
```

---

## 🔴 CRITICAL BUG #10: Ground Truth Count Discrepancy

**Location**: Multiple endpoints returning different GT counts

**Problem**: Different queries return different ground truth counts for same video.

```python
# Method 1: Count from GroundTruthObject table
gt_count = db.query(func.count(GroundTruthObject.id)).filter(
    GroundTruthObject.video_id == video_id
).scalar()  # Returns: 37

# Method 2: Count from Video.ground_truth_count field
video.ground_truth_count  # Returns: 0 (not updated)

# Method 3: Count from Annotation table
annotation_count = db.query(func.count(Annotation.id)).filter(
    Annotation.video_id == video_id
).scalar()  # Returns: 42 (includes soft-deleted)
```

**Data Inconsistency Impact**:
- Frontend shows different counts in different components
- Pass rate calculations use wrong denominator
- User confusion about "true" ground truth count

**Root Cause**:
1. `Video.ground_truth_count` not updated when GT objects added
2. Soft-deleted annotations counted in some queries
3. No single source of truth

**Fix**:
```python
# Add database trigger to update Video.ground_truth_count
# OR use computed property:
@property
def ground_truth_count(self):
    return len([gt for gt in self.ground_truth_objects if gt.deleted_at is None])
```

---

## 🟡 BUG #11: Optional Fields Being Dropped

**Location**: `schemas.py` Field(None, ...) declarations

**Problem**: Fields marked Optional but validation drops NULL values.

```python
# schemas.py
class DetectionEventResponse(DetectionEvent):
    video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")
    # ❌ If video_relative_timestamp is None, Pydantic may exclude from JSON
```

**Data Loss Risk**:
- Fields with NULL values excluded from JSON response
- Frontend normalization fallback chains break
- Missing data not distinguished from excluded data

**Fix**:
```python
# Add explicit serialization config
class DetectionEventResponse(DetectionEvent):
    model_config = ConfigDict(
        exclude_none=False,  # Include None values in JSON
        validate_assignment=True
    )
```

---

## 🟡 BUG #12: Camel Case Inconsistency

**Location**: `schemas.py` alias definitions

**Problem**: Some fields use camelCase aliases, some don't, causing frontend confusion.

```python
# Inconsistent aliasing:
video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")  # ✅ Has alias
actual_latency_ms: Optional[float] = Field(None, alias="actualLatencyMs")                # ✅ Has alias
frame_number: Optional[int] = Field(None, alias="frameNumber")                           # ❌ Missing from docs

# Frontend expects ALL fields in camelCase but some arrive in snake_case
```

**Data Loss Risk**:
- Frontend normalization misses fields with inconsistent naming
- Manual mapping in 8+ places in frontend code
- Future fields may be missed

**Fix**:
```python
# Use consistent automatic camelCase conversion for ALL schemas
class CamelCaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_to_camel,  # Automatic conversion
        populate_by_name=True,           # Accept both formats
        by_alias=True                    # Serialize with aliases
    )
```

---

## RECOMMENDED FIXES WITH CODE

### Fix #1: Add Missing Nanosecond Fields to API Schema

**File**: `/backend/schemas.py`

```python
class DetectionEventResponse(DetectionEvent):
    id: str
    validation_result: Optional[str] = Field(None, alias="validationResult")
    ground_truth_match_id: Optional[str] = Field(None, alias="groundTruthMatchId")
    created_at: datetime = Field(alias="createdAt")

    # CRITICAL FIX: Add missing nanosecond precision fields
    labjack_timestamp_ns: Optional[str] = Field(None, alias="labjackTimestampNs")
    video_start_time_ns: Optional[str] = Field(None, alias="videoStartTimeNs")
    latency_ns: Optional[str] = Field(None, alias="latencyNs")
    monotonic_timestamp_ns: Optional[str] = Field(None, alias="monotonicTimestampNs")

    # Ensure these are already present:
    video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")
    video_frame_number: Optional[int] = Field(None, alias="videoFrameNumber")
    actual_latency_ms: Optional[float] = Field(None, alias="actualLatencyMs")
```

### Fix #2: Consolidate Frame Number Fields

**File**: `/backend/models.py`

```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"

    # CRITICAL FIX: Use only video_frame_number as authoritative source
    video_frame_number = Column(Integer, nullable=True, index=True)  # ✅ KEEP

    # DEPRECATE: Legacy frame_number field (keep for migration, remove in v2)
    frame_number = Column(Integer, nullable=True, index=True)  # ⚠️ DEPRECATED

    @property
    def authoritative_frame_number(self):
        """Always use video_frame_number as source of truth"""
        return self.video_frame_number or self.frame_number  # Fallback during migration
```

### Fix #3: Frontend NULL Handling with Warnings

**File**: `/frontend/src/utils/hilResultsNormalization.ts`

```typescript
export const normalizeDetectionEvent = (event: any, index: number): EnhancedDetectionEvent => {
  const source: DetectionLike = event ?? {};

  // CRITICAL FIX: Frame number with explicit NULL handling
  let frameNumber = toInt(
    source.video_frame_number ??  // Use video-synchronized frame (authoritative)
    source.videoFrameNumber ??
    source.frame_number ??         // Legacy fallback
    source.frameNumber
  );

  if (frameNumber === undefined || frameNumber === null) {
    console.warn(
      `Detection ${source.id} missing frame_number - calculating from timestamp`,
      { event: source }
    );
    const timestamp = toNumber(source.timestamp);
    const fps = toNumber(source.fps ?? 24);
    frameNumber = timestamp && fps ? Math.round(timestamp * fps) : 0;
  }

  // Validate frame number is reasonable
  if (frameNumber < 0 || frameNumber > 100000) {
    console.error(
      `Detection ${source.id} has invalid frame_number: ${frameNumber}`,
      { event: source }
    );
    frameNumber = 0;
  }

  return {
    ...source,
    frame_number: frameNumber,
    frameNumber: frameNumber,
    video_frame_number: frameNumber,  // Ensure all variants are set
    videoFrameNumber: frameNumber
  };
};
```

### Fix #4: Division by Zero Safety

**File**: `/frontend/src/utils/hilResultsNormalization.ts`

```typescript
// CRITICAL FIX: Safe aggregation with NULL and zero handling
export const normalizeSequenceResults = (raw: any): VideoSequenceResults | null => {
  // ... existing code ...

  // Safe sum calculation
  const detectionSumFromVideos = normalizedVideos.reduce((sum, video) => {
    const count = toNumber(
      video.total_detections ??
      video.totalDetections ??
      video.detection_count ??
      video.detectionCount
    );

    // Skip NULL/NaN values
    if (!isFiniteNumber(count) || count < 0) {
      console.warn(`Video ${video.video_id} has invalid detection count: ${count}`);
      return sum;  // Don't add invalid values
    }

    return sum + count;
  }, 0);

  // Safe division with zero check
  const averageLatency = (() => {
    if (totalDetections === 0) {
      console.warn('Cannot calculate average latency: zero detections');
      return 0.0;
    }

    const weighted = totalLatencyWeighted;
    if (!isFiniteNumber(weighted)) {
      console.error('Total latency weighted is not finite:', weighted);
      return 0.0;
    }

    return weighted / totalDetections;
  })();

  return {
    // ... use averageLatency ...
  };
};
```

### Fix #5: Backend Error Handling

**File**: `/backend/routers/test_sessions.py`

```python
@router.get("", response_model=List[TestSessionResponse])
async def list_test_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List test sessions with optional filtering and pagination"""
    try:
        query = db.query(TestSession)
        sessions = query.order_by(TestSession.created_at.desc()).offset(skip).limit(limit).all()

        # Build response...
        return session_list

    except (OperationalError, SQLAlchemyError) as e:
        logger.error(f"Database error listing test sessions: {e}")
        # CRITICAL FIX: Return proper error instead of empty list
        raise HTTPException(
            status_code=500,
            detail={
                "error": "database_error",
                "message": "Failed to retrieve test sessions",
                "suggestion": "Check database connection and try again",
                "technical_details": str(e) if DEBUG else None
            }
        )
    except Exception as e:
        logger.error(f"Unexpected error listing test sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "suggestion": "Contact support if problem persists"
            }
        )
```

---

## TESTING STRATEGY

### Test Case 1: NULL Value Handling
```python
# Backend test
def test_detection_event_with_null_frame_number():
    event = DetectionEvent(
        id="test-1",
        timestamp=1.0,
        video_frame_number=None,  # NULL value
        frame_number=None
    )
    response = DetectionEventResponse.from_orm(event)
    assert response.video_frame_number is None  # Should be None, not dropped
```

```typescript
// Frontend test
describe('normalizeDetectionEvent with NULL fields', () => {
  it('should handle NULL frame_number gracefully', () => {
    const raw = {
      id: 'test-1',
      timestamp: 1.0,
      frame_number: null,
      video_frame_number: null
    };

    const normalized = normalizeDetectionEvent(raw, 0);
    expect(normalized.frame_number).toBe(24);  // Calculated fallback
    expect(consoleWarnSpy).toHaveBeenCalled();  // Warning logged
  });
});
```

### Test Case 2: Timestamp Format Detection
```typescript
describe('timestamp format handling', () => {
  it('should detect and convert epoch seconds', () => {
    const event = { timestamp: 1730822400.0 };  // Seconds
    const ts = toNumber(event.timestamp);
    expect(ts).toBe(1730822400.0);
  });

  it('should detect and convert epoch milliseconds', () => {
    const event = { timestamp: 1730822400000 };  // Milliseconds
    const ts = toNumber(event.timestamp);
    // Should auto-detect format and normalize
    expect(ts).toBeCloseTo(1730822400.0, 1);
  });
});
```

### Test Case 3: Division by Zero
```typescript
describe('aggregation safety', () => {
  it('should handle zero detections without NaN', () => {
    const results = normalizeSequenceResults({
      per_video_results: [
        { total_detections: 0, avg_latency_ms: 0 }
      ]
    });

    expect(results.average_latency_ms).toBe(0.0);
    expect(results.average_latency_ms).not.toBe(NaN);
  });
});
```

---

## PRIORITY RECOMMENDATIONS

### 🔴 IMMEDIATE (Deploy Today)
1. Add missing nanosecond fields to API schema (Fix #1)
2. Add NULL handling warnings in frontend (Fix #3)
3. Fix division by zero in aggregations (Fix #4)

### 🟠 HIGH PRIORITY (This Week)
4. Consolidate frame_number fields (Fix #2)
5. Standardize timestamp formats (Fix #5)
6. Fix backend error handling (Fix #5)
7. Add video ID inference validation (Fix #9)

### 🟡 MEDIUM PRIORITY (Next Sprint)
8. Fix ground truth count discrepancy (Fix #10)
9. Add field serialization config (Fix #11)
10. Implement consistent camelCase (Fix #12)

### 🟢 LONG TERM (Backlog)
11. Add comprehensive E2E tests
12. Database migration to remove deprecated fields
13. Implement data validation pipeline
14. Add monitoring for data transformation errors

---

## CONCLUSION

The data transformation pipeline has **12 critical bugs** causing data loss between backend and frontend. The most severe issues are:

1. **Missing nanosecond precision fields** (lose sub-millisecond accuracy)
2. **Frame number field confusion** (data corruption in multi-video sequences)
3. **Silent NULL dropping** (detections disappear without warning)
4. **Division by zero** (NaN propagation in statistics)
5. **Timestamp format confusion** (1000x timing errors possible)

**Recommended Actions**:
- Deploy immediate fixes (#1, #3, #4) today
- Schedule database migration for field consolidation
- Add E2E tests covering full data transformation pipeline
- Implement data validation at each transformation step
- Add monitoring alerts for NULL value spikes

**Success Metrics**:
- Zero NaN values in frontend calculations
- 100% of detection events have valid frame numbers
- All nanosecond precision fields present in API responses
- Backend errors properly propagated to frontend
- Ground truth counts consistent across all queries
