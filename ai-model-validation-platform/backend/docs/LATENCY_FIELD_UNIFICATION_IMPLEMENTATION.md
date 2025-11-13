# Latency Field Unification Implementation

## Executive Summary

This document describes the implementation of unified latency field handling across the HIL test validation platform to resolve inconsistencies where latency shows as 0ms/Infinity/contradictions.

## Current State Analysis

### Existing Latency Fields

**Primary (Canonical):**
- `actual_latency_ms` - The single source of truth for latency measurements

**Legacy/Deprecated:**
- `latency_ms` - Generic field, inconsistently populated
- `detection_time_ms` - Processing time, not actual latency
- `real_latency_ms` - Duplicate of actual_latency_ms
- `apparent_latency_ms` - Timing artifact field
- `corrected_latency` - Complex nested structure

**Supporting Fields (Keep):**
- `video_relative_timestamp` - Video position when detection occurred
- `labjack_timestamp` - Hardware detection timestamp
- `video_start_time` - Reference point for latency calculation

## Canonical Formula

```python
# Single location: labjack_detection_service.py _create_detection_event()
def calculate_unified_latency(
    labjack_timestamp: float,
    video_start_time: float,
    video_relative_timestamp: float
) -> float:
    """
    Calculate actual latency from video playback start

    Args:
        labjack_timestamp: Hardware detection timestamp (Unix seconds)
        video_start_time: Video playback start timestamp (Unix seconds)
        video_relative_timestamp: Position in video (seconds from start)

    Returns:
        Latency in milliseconds (always >= 0)
    """
    # Latency = (Hardware detection time - Video start time) - Video position
    # This gives us how long after the video event the hardware detected it
    detection_delay_s = labjack_timestamp - video_start_time
    actual_latency_s = detection_delay_s - video_relative_timestamp

    # Add system processing overhead (LabJack T7 + backend)
    SYSTEM_LATENCY_MS = 50.0
    actual_latency_ms = max(0.0, actual_latency_s * 1000) + SYSTEM_LATENCY_MS

    return actual_latency_ms
```

## Implementation Plan

### Phase 1: Backend Detection Service Consolidation

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/labjack_detection_service.py`

**Changes:**
1. Update `_create_detection_event()` to use canonical formula (lines 658-723)
2. Remove calculation of legacy fields
3. Set `actual_latency_ms` as the only latency output

```python
# BEFORE (lines 692-700):
SYSTEM_LATENCY_MS = 50.0
if video_relative_timestamp is not None:
    # Latency = video playback position + system processing overhead
    actual_latency_ms = (video_relative_timestamp * 1000) + SYSTEM_LATENCY_MS
else:
    actual_latency_ms = None

# AFTER (unified):
actual_latency_ms = calculate_unified_latency(
    labjack_timestamp=timestamp.timestamp(),
    video_start_time=reference_time,
    video_relative_timestamp=video_relative_timestamp
)
```

### Phase 2: Database Model Updates

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/models.py`

**Changes:**
1. Add comments marking deprecated fields (lines 289-298)
2. Keep fields for backward compatibility but document as legacy

```python
# DetectionEvent model (lines 276-430)

# PRIMARY LATENCY FIELD (use this)
actual_latency_ms = Column(Float, nullable=True, index=True)  # Actual measured latency (milliseconds)

# DEPRECATED FIELDS (for backward compatibility only, do not use)
latency_ns = Column(String, nullable=True)  # DEPRECATED: Use actual_latency_ms
processing_time_ms = Column(Float, nullable=True)  # DEPRECATED: This is not latency
```

### Phase 3: Schema Updates

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/schemas.py`

**Changes:**
1. Update `DetectionEventResponse` to prioritize `actual_latency_ms` (lines 302-320)
2. Add field documentation

```python
class DetectionEventResponse(DetectionEvent):
    # ... existing fields ...

    # PRIMARY LATENCY FIELD - Always use this for latency calculations
    actual_latency_ms: Optional[float] = Field(
        None,
        alias="actualLatencyMs",
        description="Actual measured latency in milliseconds from video event to hardware detection"
    )

    # Legacy fields maintained for backward compatibility
    latency_ms: Optional[float] = Field(
        None,
        alias="latencyMs",
        deprecated=True,
        description="DEPRECATED: Use actual_latency_ms instead"
    )
```

### Phase 4: Frontend Normalizer Updates

**File:** `/home/rigade/Testing/ai-model-validation-platform/frontend/src/utils/hilResultsNormalization.ts`

**Changes:**
1. Update field priority order (lines 144-153)
2. Ensure `actual_latency_ms` is always preferred

```typescript
// BEFORE (lines 144-153):
const realLatency = toNumber(
  source.actual_latency_ms ??
    source.real_latency_ms ??
    source.latency_ms ??
    source.actualLatencyMs ??
    source.detection_latency_ms ??
    source.apparent_latency_ms ??
    source.corrected_latency?.real_latency_ms ??
    source.original_latency?.apparent_latency_ms
);

// AFTER (simplified):
const realLatency = toNumber(
  source.actual_latency_ms ??
    source.actualLatencyMs ??
    // Fallbacks for legacy data only
    source.latency_ms ??
    source.real_latency_ms
);
```

### Phase 5: API Endpoint Updates

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/api/hil_test_complete.py`

**Changes:**
1. Ensure all detection event serialization uses `actual_latency_ms`
2. Remove legacy field mappings

### Phase 6: Migration Script

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/migrations/versions/unify_latency_fields.py`

```python
"""Unify latency fields and mark legacy fields

Revision ID: unify_latency_001
"""

def upgrade():
    # Add comment to deprecated fields
    op.execute("""
        COMMENT ON COLUMN detection_events.latency_ns IS
        'DEPRECATED: Use actual_latency_ms. Kept for backward compatibility.';

        COMMENT ON COLUMN detection_events.processing_time_ms IS
        'DEPRECATED: This is processing time, not latency. Use actual_latency_ms.';
    """)

    # Backfill actual_latency_ms for any NULL values using legacy calculation
    op.execute("""
        UPDATE detection_events
        SET actual_latency_ms = COALESCE(
            actual_latency_ms,
            video_relative_timestamp * 1000 + 50.0,
            latency_threshold_ms
        )
        WHERE actual_latency_ms IS NULL
        AND video_relative_timestamp IS NOT NULL;
    """)

def downgrade():
    # Remove comments
    op.execute("COMMENT ON COLUMN detection_events.latency_ns IS NULL;")
    op.execute("COMMENT ON COLUMN detection_events.processing_time_ms IS NULL;")
```

## Expected Impact

### Before Unification
- `actual_latency_ms`: Sometimes 0, sometimes correct
- `latency_ms`: Inconsistent, often 0
- `detection_time_ms`: Random values
- Frontend shows: "0ms", "Infinity", contradictions

### After Unification
- `actual_latency_ms`: Always populated with correct value
- Legacy fields: Maintained for compatibility but not used
- Frontend shows: Consistent real latency values (50-200ms typical)
- No more 0ms/Infinity issues

## Verification Steps

1. **Database Check:**
   ```sql
   SELECT
     COUNT(*) as total_detections,
     COUNT(actual_latency_ms) as populated_latency,
     AVG(actual_latency_ms) as avg_latency,
     MIN(actual_latency_ms) as min_latency,
     MAX(actual_latency_ms) as max_latency
   FROM detection_events
   WHERE test_session_id = 'test-session-id';
   ```

2. **API Response Check:**
   ```bash
   curl http://localhost:8000/api/v1/test-sessions/SESSION_ID/results \
     | jq '.detection_events[0].actual_latency_ms'
   # Should return: 85.2 (not 0 or null)
   ```

3. **Frontend Display Check:**
   - Open HIL Results page
   - Verify Detection Timeline shows real latency values
   - Verify Detection Table "Latency" column shows real values
   - No "0ms" or "Infinity" should appear

## Rollback Plan

If issues occur:
1. Revert migration: `alembic downgrade -1`
2. Revert code changes via git
3. Frontend will fall back to legacy field names automatically
4. No data loss (legacy fields maintained)

## Success Criteria

✅ Single latency field (`actual_latency_ms`) consistently populated
✅ No detections with 0ms latency (except true hardware failures)
✅ No Infinity or contradiction errors in frontend
✅ Average latency 50-200ms (realistic for LabJack T7)
✅ API docs updated to reflect canonical field
✅ Frontend normalizer prefers actual_latency_ms
✅ Legacy fields maintained for backward compatibility

## References

- **Canonical Calculation:** `services/labjack_detection_service.py:_create_detection_event()`
- **Database Schema:** `models.py:DetectionEvent`
- **API Schema:** `schemas.py:DetectionEventResponse`
- **Frontend Normalizer:** `frontend/src/utils/hilResultsNormalization.ts`
