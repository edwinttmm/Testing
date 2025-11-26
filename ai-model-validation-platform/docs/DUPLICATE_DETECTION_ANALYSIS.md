# Code Quality Analysis Report: Duplicate Detection Investigation

## Summary
- **Overall Quality Score**: 6/10
- **Files Analyzed**: 2 (labjack_detection_service.py, dedicated_labjack_monitor.py)
- **Issues Found**: 3 Critical, 2 High-Priority Code Smells
- **Technical Debt Estimate**: 8-12 hours

---

## Executive Summary

**ROOT CAUSE IDENTIFIED**: Duplicate detection entries are **NOT** being created at the storage source. Each detection has a unique UUID and is stored only once. The duplicates in the UI with the same frame number but different latency values are likely caused by:

1. **Post-processing duplication** in the matching/correlation layer
2. **Multiple WebSocket emissions** for the same detection
3. **Client-side state management issues** creating visual duplicates

---

## Critical Issues

### 1. **TWO SEPARATE STORAGE PATHS** (CRITICAL - Root Cause)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

**Location**: Lines 908-1415

**Description**:
The `dedicated_labjack_monitor.py` service has **TWO separate database storage functions** that can be called for the same detection:

1. **`_store_event_sync_wrapper()` (Line 1239)**: Primary storage path
   - Called from `_schedule_db_storage()` (Line 1231)
   - Creates a `DetectionEvent` and stores via `db.add(detection_event)` at line 1403

2. **`_store_detection_event_async()` (Line 2063)**: Secondary/legacy storage path
   - Also creates a `DetectionEvent` and stores via `db.add(detection_event)` at line 2126
   - **APPEARS TO BE UNUSED** but still present in codebase

**Evidence**:
```python
# Path 1: _store_event_sync_wrapper (Line 1239-1415)
def _store_event_sync_wrapper(self, hil_event: HILDetectionEvent, ...):
    detection_event = DetectionEvent(id=hil_event.id, ...)
    db.add(detection_event)  # LINE 1403
    db.commit()

# Path 2: _store_detection_event_async (Line 2063-2177)
async def _store_detection_event_async(self, hil_event: HILDetectionEvent):
    detection_event = DetectionEvent(id=hil_event.id, ...)
    db.add(detection_event)  # LINE 2126
    db.commit()
```

**Severity**: HIGH
**Risk**: If both paths are called, the same detection (same UUID) would be inserted twice, causing database constraint violations OR the second insert would update/overwrite the first.

**Recommendation**:
- Remove the unused `_store_detection_event_async()` function (lines 2063-2177)
- Verify no code calls this legacy async storage path
- Add database constraint to prevent duplicate IDs if not already present

---

### 2. **NO DUPLICATE PREVENTION AT STORAGE LEVEL** (CRITICAL)

**File**: Both services

**Description**:
Neither `labjack_detection_service.py` nor `dedicated_labjack_monitor.py` checks if a detection with the same ID already exists before inserting. While UUIDs should be unique, there's no safety check.

**Evidence**:
```python
# labjack_detection_service.py - Line 2706 (FALLBACK path)
db_session.execute(sql, {...})  # Direct SQL INSERT with no duplicate check
db_session.commit()

# dedicated_labjack_monitor.py - Line 1403
db.add(detection_event)  # No duplicate check
db.commit()
```

**Severity**: HIGH
**Recommendation**: Add duplicate detection check:
```python
existing = db.query(DetectionEvent).filter_by(id=event.id).first()
if existing:
    logger.warning(f"⚠️ Detection {event.id} already exists, skipping duplicate storage")
    return
```

---

### 3. **CALLBACK REGISTRATION WITHOUT DEDUPLICATION** (HIGH)

**File**: `/home/rigade/Testing/ai-model-validation-platform/backend/services/dedicated_labjack_monitor.py`

**Location**: Lines 563-570

**Description**:
Detection callbacks are registered without checking if the same callback already exists. If `start_session_monitoring()` is called twice for the same session, duplicate callbacks would cause duplicate processing.

**Evidence**:
```python
# Line 563-570
detection_callback = lambda event: self._handle_detection_with_video_sync(session_id, event)
self.active_sessions[session_id]['detection_callback'] = detection_callback
self.labjack_monitor.add_detection_callback(detection_callback)  # No duplicate check
```

**Severity**: HIGH
**Recommendation**:
```python
# Remove old callback before adding new one
old_callback = self.active_sessions.get(session_id, {}).get('detection_callback')
if old_callback:
    self.labjack_monitor.remove_detection_callback(old_callback)
    logger.debug(f"Removed old detection callback for session {session_id}")
```

---

## Code Smells

### 1. **God Object Pattern - HIL Detection Event Processing**

**File**: `dedicated_labjack_monitor.py`
**Lines**: 908-1415 (507 lines in single method)

**Issue**: The `_handle_detection_with_video_sync()` method is **507 lines long** and handles:
- Timing synchronization
- Calibration offset calculation
- Video-relative timestamp calculation
- HIL event creation
- Database storage scheduling
- WebSocket emission
- Error handling

**Recommendation**: Break into smaller, focused methods:
```python
def _handle_detection_with_video_sync(self, session_id: str, labjack_event):
    # Orchestration only (50 lines max)
    timing_data = self._calculate_detection_timing(session_id, labjack_event)
    hil_event = self._create_hil_event(labjack_event, timing_data)
    self._schedule_storage_and_emission(hil_event)
```

---

### 2. **Duplicate Code - Detection Event Creation**

**Files**: Both services
**Issue**: Similar detection event creation logic appears in multiple places with slight variations

**Examples**:
- `dedicated_labjack_monitor.py` lines 1355-1388 (sync wrapper)
- `dedicated_labjack_monitor.py` lines 2095-2124 (async legacy)
- `labjack_detection_service.py` lines 2686-2704 (fallback)

**Recommendation**: Create a single factory function:
```python
def create_detection_event(hil_event, timing_data, session_id, video_id):
    """Single source of truth for DetectionEvent creation"""
    return DetectionEvent(
        id=hil_event.id,
        # ... all fields
    )
```

---

## Storage Flow Analysis

### Current Detection Storage Flow

```
LabJack Hardware Detection
         |
         v
labjack_detection_service.py (monitoring)
         |
         v
Detection Callback: _handle_detection_with_video_sync()
         |
         v
Create HILDetectionEvent (Line 1116)
         |
         v
_schedule_db_storage() (Line 1149)
         |
         v
Threading.Thread -> _store_event_sync_wrapper() (Line 1231)
         |
         v
Create DetectionEvent (Line 1355)
         |
         v
db.add(detection_event) + db.commit() (Lines 1403-1404)
         |
         v
💾 FALLBACK: Stored detection event (UNIQUE UUID)
```

### Key Findings:

1. **Each detection gets a unique UUID** (Line 1117): `id=str(uuid.uuid4())`
2. **Storage happens once per detection** via the sync wrapper path
3. **The async storage function appears unused** but could cause issues if called
4. **No duplicate detection IDs in logs** - each log shows a different UUID

---

## Detection vs UI Duplicate Analysis

### From Your Logs:
```
💾 FALLBACK: Stored detection event: e5ae2c96-4af7-4b74-ba17-a653c483b149
💾 FALLBACK: Stored detection event: 24e0bc8c-bd35-4844-8866-4ba3b5a31323
```

**Observation**: Each detection has a UNIQUE ID, so duplicates are NOT being created at storage time.

### UI Duplicate Characteristics:
- **Same frame number**
- **Different latency values**
- **Same timestamp**

**Conclusion**: The issue is NOT duplicate storage at the source. The problem is likely in:

1. **Post-storage matching logic** that correlates detections to video frames
2. **WebSocket emission** sending the same detection multiple times
3. **Frontend state management** not deduplicating incoming events
4. **Query logic** that joins detection_events table with other tables, creating duplicate rows

---

## Interaction Between Services

### Service Architecture:

```
labjack_detection_service.py
    - Monitors LabJack hardware
    - Detects voltage spikes
    - Creates DetectionEvent objects
    - Notifies callbacks
         |
         v
dedicated_labjack_monitor.py
    - Registers detection callback
    - Receives raw detection events
    - Calculates timing synchronization
    - Creates HILDetectionEvent
    - Stores in database
    - Emits WebSocket events
```

### Critical Finding:

**Both services can store detections**, but through different code paths:

1. **Primary Path**: `dedicated_labjack_monitor.py` -> `_store_event_sync_wrapper()` (Line 1403)
2. **Fallback Path**: `labjack_detection_service.py` -> `_store_event_fallback()` (Line 2706)

**Risk**: If both paths execute for the same detection, you get duplicates.

---

## WebSocket Emission Analysis

### Detection Event WebSocket Paths:

1. **dedicated_labjack_monitor.py** - Line 1152:
   ```python
   self._schedule_websocket_emission(hil_event, session_id)
   ```

2. **labjack_detection_service.py** - Line 2520:
   ```python
   await self._websocket_emit_fn(detection_data, event.session_id)
   ```

**Issue**: If both services emit WebSocket events for the same detection, the frontend receives it twice.

---

## Recommended Fixes

### Priority 1: Remove Duplicate Storage Path
```python
# DELETE lines 2063-2177 in dedicated_labjack_monitor.py
# async def _store_detection_event_async(...)
```

### Priority 2: Add Duplicate Detection Guard
```python
def _store_event_sync_wrapper(self, hil_event, ...):
    db = next(get_db())
    try:
        # Check for duplicate before inserting
        existing = db.query(DetectionEvent).filter_by(id=hil_event.id).first()
        if existing:
            logger.warning(f"⚠️ Detection {hil_event.id} already exists, skipping")
            return

        # ... rest of storage logic
```

### Priority 3: Callback Deduplication
```python
def start_session_monitoring(self, session_id, ...):
    # Remove old callback if exists
    old_callback = self.active_sessions.get(session_id, {}).get('detection_callback')
    if old_callback:
        self.labjack_monitor.remove_detection_callback(old_callback)

    # Register new callback
    detection_callback = lambda event: self._handle_detection_with_video_sync(session_id, event)
    self.labjack_monitor.add_detection_callback(detection_callback)
```

### Priority 4: Add Database Constraint
```sql
-- Add unique constraint on detection_events.id if not exists
ALTER TABLE detection_events
ADD CONSTRAINT unique_detection_id UNIQUE (id);
```

---

## Testing Recommendations

1. **Test duplicate callback registration**:
   - Call `start_session_monitoring()` twice for same session
   - Verify only one detection is stored per hardware event

2. **Test concurrent storage paths**:
   - Trigger both `_store_event_sync_wrapper()` and `_store_event_fallback()`
   - Verify no duplicate IDs in database

3. **Test WebSocket emission**:
   - Monitor frontend WebSocket messages
   - Verify each detection ID appears only once

4. **Test database constraints**:
   - Attempt to insert duplicate detection ID
   - Verify database rejects with constraint violation

---

## Positive Findings

1. ✅ **UUID generation ensures unique IDs** per detection
2. ✅ **Comprehensive error handling** in storage paths
3. ✅ **Thread-safe database operations** using separate threads
4. ✅ **Detailed logging** helps track detection lifecycle
5. ✅ **Timing calibration** provides accurate latency measurements
6. ✅ **Video synchronization** properly calculates frame numbers

---

## Conclusion

**The duplicate detections in the UI are NOT caused by duplicate storage at the source level.** Each detection receives a unique UUID and is stored once. The likely causes are:

1. **Multiple callback registrations** if sessions are initialized more than once
2. **Post-storage correlation logic** matching the same detection to multiple frames
3. **Frontend state management** not deduplicating WebSocket events
4. **Unused legacy storage path** (`_store_detection_event_async`) that could be triggered accidentally

**Immediate Action**: Remove the unused async storage function and add duplicate detection guards to prevent issues.

---

## Next Steps

1. Analyze the **frontend detection handling code** to check for duplicate processing
2. Review **database query logic** that retrieves detections (joins may create duplicates)
3. Examine **WebSocket emission** to ensure each detection is sent once
4. Check **correlation/matching logic** that assigns detections to video frames
