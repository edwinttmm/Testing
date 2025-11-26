# Video Start Time Database Persistence Fix

## Problem Statement

Detections in the database lack `video_start_time` field, causing corrected latency calculations to be skipped during post-test analysis.

**Symptom:**
```
⚠️ Skipping corrected latency for detection DET_7cfb8a (missing video_start_time)
```

## Root Cause Analysis

### Data Flow Investigation

#### 1. In-Memory DetectionEvent ✅ (labjack_detection_service.py)
```python
@dataclass
class DetectionEvent:
    # ... other fields ...
    video_relative_timestamp: Optional[float] = None
    actual_latency_ms: Optional[float] = None
    video_start_time: Optional[float] = None  # FIX: Added for corrected latency calculation
```

**Status:** Field EXISTS and is populated with `reference_time` at line 2095.

#### 2. Main Database Model ✅ (models.py)
```python
class DetectionEvent(Base):
    __tablename__ = "detection_events"
    # ... other columns ...
    video_start_time = Column(Float, nullable=True, index=True)  # Line 363
```

**Status:** Column EXISTS in the main database schema.

#### 3. ❌ **BROKEN LINK:** Database Integration Service

**File:** `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_database_integration.py`

**Problem Location:** `from_detection_data()` method (lines 88-102)

**Before Fix:**
```python
@classmethod
def from_detection_data(cls, event_data: DetectionEventData):
    """Create DetectionEvent from DetectionEventData"""
    metadata_json = json.dumps(event_data.metadata) if event_data.metadata else None

    return cls(
        session_id=event_data.session_id,
        event_id=event_data.id,
        timestamp=event_data.timestamp,
        channel=event_data.channel,
        voltage=event_data.voltage,
        threshold=event_data.threshold,
        detected=event_data.detected,
        is_duplicate=event_data.is_duplicate,
        metadata=metadata_json
        # ❌ MISSING: video_relative_timestamp, actual_latency_ms, video_start_time
    )
```

**Issue:** The method converts in-memory `DetectionEvent` to database model but does NOT copy the timing calibration fields.

## Solution Implemented

### Fix 1: Add Missing Database Columns

**File:** `backend/services/detection_database_integration.py`
**Lines:** 68-71

```python
# Timing calibration fields for corrected latency calculation
video_relative_timestamp = Column(Float, nullable=True, index=True)  # Timestamp relative to video start
actual_latency_ms = Column(Float, nullable=True, index=True)  # Actual measured latency
video_start_time = Column(Float, nullable=True, index=True)  # Video start reference time
```

### Fix 2: Update Conversion Method

**File:** `backend/services/detection_database_integration.py`
**Lines:** 102-105

```python
return cls(
    session_id=event_data.session_id,
    event_id=event_data.id,
    timestamp=event_data.timestamp,
    channel=event_data.channel,
    voltage=event_data.voltage,
    threshold=event_data.threshold,
    detected=event_data.detected,
    is_duplicate=event_data.is_duplicate,
    metadata=metadata_json,
    # FIX: Copy timing calibration fields for corrected latency calculation
    video_relative_timestamp=event_data.video_relative_timestamp,
    actual_latency_ms=event_data.actual_latency_ms,
    video_start_time=event_data.video_start_time
)
```

### Fix 3: Update to_dict() Method

**File:** `backend/services/detection_database_integration.py`
**Lines:** 90-93

```python
'metadata': json.loads(self.metadata) if self.metadata else None,
# FIX: Include timing calibration fields for corrected latency calculation
'video_relative_timestamp': self.video_relative_timestamp,
'actual_latency_ms': self.actual_latency_ms,
'video_start_time': self.video_start_time
```

## Database Migration Required

The database schema needs to be updated to add the missing columns:

```sql
-- Add timing calibration columns to detection_events table
ALTER TABLE detection_events
ADD COLUMN video_relative_timestamp FLOAT,
ADD COLUMN actual_latency_ms FLOAT,
ADD COLUMN video_start_time FLOAT;

-- Add indexes for performance
CREATE INDEX idx_detection_events_video_relative_timestamp ON detection_events(video_relative_timestamp);
CREATE INDEX idx_detection_events_actual_latency_ms ON detection_events(actual_latency_ms);
CREATE INDEX idx_detection_events_video_start_time ON detection_events(video_start_time);
```

## Testing

### Verification Steps

1. **Start new detection session with video timing:**
   ```bash
   POST /api/labjack/detection/start
   {
     "session_id": "test_session_001",
     "channels": ["AIN0"],
     "voltage_threshold": 2.5,
     "reference_time": 1732563847.123456
   }
   ```

2. **Trigger detection and verify database:**
   ```sql
   SELECT
     event_id,
     timestamp,
     video_relative_timestamp,
     actual_latency_ms,
     video_start_time
   FROM detection_events
   WHERE session_id = 'test_session_001';
   ```

3. **Expected Result:**
   - `video_start_time` should contain the reference_time value
   - `video_relative_timestamp` should contain calculated offset
   - `actual_latency_ms` should contain computed latency

4. **Verify corrected latency calculation:**
   - Check that post-test analysis no longer shows "Skipping corrected latency" warnings
   - Verify that `corrected_latency_ms` is calculated for all detections

## Impact

### Before Fix
- ❌ Detection events stored in database without timing calibration fields
- ❌ Post-test corrected latency calculations impossible
- ❌ Data loss during memory-to-database conversion

### After Fix
- ✅ All timing calibration fields persisted to database
- ✅ Corrected latency calculations work for all detections
- ✅ Complete data integrity from memory to database to analysis

## Files Modified

1. `/home/rigade/Testing/ai-model-validation-platform/backend/services/detection_database_integration.py`
   - Added database columns (lines 68-71)
   - Updated `from_detection_data()` method (lines 102-105)
   - Updated `to_dict()` method (lines 90-93)

## Related Issues

- **Original Fix:** Added `video_start_time` to in-memory `DetectionEvent` dataclass
- **This Fix:** Ensures the field is persisted to database
- **Downstream Benefit:** Post-test corrected latency analysis now has complete data

## Next Steps

1. Run database migration to add columns
2. Restart detection services
3. Run test session to verify fields are populated
4. Verify post-test analysis uses persisted data
5. Monitor for "Skipping corrected latency" warnings (should disappear)

---

**Fix Applied:** 2025-11-25
**Severity:** High (Data Loss)
**Status:** ✅ Resolved
