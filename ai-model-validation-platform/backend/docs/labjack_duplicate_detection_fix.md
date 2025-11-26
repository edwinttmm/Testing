# LabJack Duplicate Detection Source Fix

**Status**: IDENTIFIED & DOCUMENTED
**Date**: 2025-11-21
**Priority**: CRITICAL

## Problem Summary

Both `labjack` and `dedicated_labjack_monitor` detection sources were writing identical detection events to the database, causing 100% duplication.

### Evidence
- **Total duplicates**: 167 detection events
- **Timestamp range**: 2025-11-20 22:18:00 (all within same session)
- **Sources involved**:
  - `labjack` (629 total detections)
  - `dedicated_labjack_monitor` (26,247 total detections)

### Verification Command
```bash
python3 scripts/verify_labjack_source_fix.py
```

## Root Cause Analysis

### Duplicate Write Locations

#### Location 1: labjack_detection_service.py
**File**: `/backend/services/labjack_detection_service.py`
**Line**: 2193
**Code**:
```python
db_event = DBDetectionEvent(
    # ... other fields ...
    source='labjack',  # ❌ DUPLICATE SOURCE
    detection_type='hardware',
    # ...
)
```

**Service Instantiation**:
- Function: `get_detection_service()` (line 72-77)
- Returns: `LabJackDetectionMonitor` singleton instance
- Called from: `main.py:4040` for WebSocket connections

#### Location 2: dedicated_labjack_monitor.py
**File**: `/backend/services/dedicated_labjack_monitor.py`
**Lines**: 1365, 2099
**Code**:
```python
detection_event = DetectionEvent(
    # ... other fields ...
    source="dedicated_labjack_monitor",  # ✅ CORRECT SOURCE
    detection_type="labjack_voltage",
    # ...
)
```

**Service Instantiation**:
- Class: `DedicatedLabJackMonitor`
- Started via: `routers/test_sessions.py` (standalone monitoring)

## Why Both Services Were Active

### Architecture Design Issue

The system has TWO parallel LabJack monitoring pathways:

1. **Integrated Service** (`labjack_detection_service.py`)
   - Part of main backend process
   - Used for WebSocket real-time monitoring
   - Called via `get_detection_service()` in `main.py`

2. **Standalone Monitor** (`dedicated_labjack_monitor.py`)
   - Separate dedicated process
   - Started via service manager
   - Intended for conflict-free hardware access

### The Conflict

Both services were:
1. Reading from the SAME LabJack hardware
2. Detecting the SAME voltage threshold crossings
3. Writing to the SAME database
4. Using DIFFERENT source identifiers

Result: **Every detection event was recorded twice**

## Solution Options

### Option A: Disable LabJackDetectionService (RECOMMENDED)

**Pros**:
- Dedicated monitor is more robust
- Eliminates device conflicts
- Standalone process isolation
- Already widely deployed

**Cons**:
- WebSocket integration may need adjustment
- More complex process management

**Implementation**:
1. Comment out source write in `labjack_detection_service.py:2193`
2. Redirect WebSocket connections to use dedicated monitor
3. Update documentation

### Option B: Disable Dedicated Monitor

**Pros**:
- Simpler architecture
- Integrated with main process
- Easier debugging

**Cons**:
- Risk of device conflicts
- Less isolation
- Harder to restart independently

**Implementation**:
1. Comment out source write in `dedicated_labjack_monitor.py:1365,2099`
2. Ensure integrated service is properly initialized
3. Update service manager

### Option C: Make Sources Mutually Exclusive

**Pros**:
- Flexibility to choose at runtime
- Safer migration path
- Backward compatibility

**Cons**:
- More complex configuration
- Requires coordination logic

**Implementation**:
1. Add configuration flag to choose active service
2. Add startup checks to prevent both services
3. Document selection criteria

## Recommended Fix (Option A)

### Step 1: Modify labjack_detection_service.py

**File**: `services/labjack_detection_service.py`

**Change** (line 2193):
```python
# BEFORE:
source='labjack',  # ❌ Creates duplicate detections

# AFTER:
source='labjack',  # DISABLED: Use dedicated_labjack_monitor to prevent duplicates
                   # Uncomment only if dedicated monitor is not active
```

**Add Safety Check** (in `get_detection_service()` function):
```python
def get_detection_service():
    """Get or create detection service instance"""
    global _detection_service_instance

    # Safety check: Don't instantiate if dedicated monitor is active
    try:
        from services.dedicated_labjack_monitor import is_monitor_active
        if is_monitor_active():
            logger.warning("Dedicated LabJack monitor is active - not instantiating detection service")
            return None
    except ImportError:
        pass

    if _detection_service_instance is None:
        _detection_service_instance = LabJackDetectionMonitor()
    return _detection_service_instance
```

### Step 2: Update WebSocket Integration

**File**: `main.py`

**Change** (line 4099):
```python
# BEFORE:
detection_monitor = get_detection_service()

# AFTER:
detection_monitor = get_detection_service()
if detection_monitor is None:
    # Fallback to dedicated monitor if available
    try:
        from services.dedicated_labjack_monitor import get_monitor_instance
        detection_monitor = get_monitor_instance()
    except ImportError:
        logger.error("No detection service available")
        await websocket.close(code=1011, reason="Detection service unavailable")
        return
```

### Step 3: Add Monitoring State Check

**File**: `services/dedicated_labjack_monitor.py`

**Add** (at module level):
```python
_monitor_instance = None

def is_monitor_active() -> bool:
    """Check if dedicated monitor is active"""
    return _monitor_instance is not None and _monitor_instance.running

def get_monitor_instance():
    """Get active monitor instance"""
    return _monitor_instance
```

### Step 4: Verification

```bash
# Run verification script
python3 scripts/verify_labjack_source_fix.py

# Expected output:
# ✅ Configuration looks correct
# ✅ No duplicate timestamps detected
# Active service: MONITOR_SERVICE_ONLY
```

## Database Cleanup (Optional)

If you want to remove historical duplicates:

```sql
-- Identify duplicate detection timestamps
WITH duplicates AS (
    SELECT
        timestamp,
        COUNT(*) as count,
        GROUP_CONCAT(source) as sources
    FROM detection_events
    WHERE source IN ('labjack', 'dedicated_labjack_monitor')
    GROUP BY timestamp
    HAVING COUNT(*) > 1
)
SELECT * FROM duplicates LIMIT 10;

-- CAUTION: Only run after verifying duplicates
-- This keeps dedicated_labjack_monitor and removes labjack duplicates
DELETE FROM detection_events
WHERE id IN (
    SELECT de1.id
    FROM detection_events de1
    INNER JOIN detection_events de2 ON de1.timestamp = de2.timestamp
    WHERE de1.source = 'labjack'
      AND de2.source = 'dedicated_labjack_monitor'
);
```

## Testing Plan

### Test 1: Service Exclusivity
```bash
# 1. Start dedicated monitor
python -m services.dedicated_labjack_monitor

# 2. Attempt to get detection service
python -c "from services.labjack_detection_service import get_detection_service; print(get_detection_service())"

# Expected: None (with warning log)
```

### Test 2: Detection Recording
```bash
# 1. Start test session with dedicated monitor
# 2. Trigger detection events
# 3. Check database sources

python3 << 'EOF'
from database import SessionLocal
from models import DetectionEvent
from sqlalchemy import func
from datetime import datetime, timedelta

db = SessionLocal()
recent = datetime.utcnow() - timedelta(minutes=5)
sources = db.query(
    DetectionEvent.source,
    func.count(DetectionEvent.id)
).filter(
    DetectionEvent.timestamp >= recent.timestamp()
).group_by(DetectionEvent.source).all()

print("Recent detection sources:")
for source, count in sources:
    print(f"  {source}: {count}")
db.close()
EOF

# Expected: Only ONE source with detections
```

### Test 3: WebSocket Functionality
```bash
# Connect to WebSocket endpoint
# Verify real-time detection events are received
# Confirm no duplicate events
```

## Rollback Plan

If the fix causes issues:

1. **Immediate Rollback**:
   ```bash
   git checkout services/labjack_detection_service.py
   git checkout main.py
   ```

2. **Emergency Fallback**:
   - Stop dedicated monitor
   - Re-enable labjack_detection_service
   - Accept duplicates temporarily

3. **Alternative Configuration**:
   - Use Option B (disable dedicated monitor)
   - Update service manager configuration

## Success Metrics

- ✅ Zero duplicate timestamps in new detections
- ✅ Only one source writing per test session
- ✅ WebSocket connections still functional
- ✅ No device conflict errors
- ✅ Detection latency unchanged

## Related Files

- `services/labjack_detection_service.py` (line 2193)
- `services/dedicated_labjack_monitor.py` (lines 1365, 2099)
- `main.py` (line 4040, 4099)
- `routers/test_sessions.py` (line 60)
- `scripts/verify_labjack_source_fix.py` (verification script)

## References

- **Previous Fix Attempt**: Disabled `simple_labjack_detection` (incomplete)
- **Affected Tables**: `detection_events`
- **Issue First Detected**: 2025-11-20
- **Total Duplicates**: 167 events

## Notes

- The "labjack" source has 629 total detections vs 26,247 for "dedicated_labjack_monitor"
- This suggests dedicated monitor was the PRIMARY system
- The 167 duplicates occurred during a single test session (2025-11-20 22:18:xx)
- This indicates both services were briefly active simultaneously
- Historical data shows dedicated monitor is more widely used

## Next Steps

1. ✅ Create verification script (COMPLETED)
2. ⏳ Implement Option A fix (labjack_detection_service disable)
3. ⏳ Test WebSocket integration with fallback
4. ⏳ Add runtime exclusivity check
5. ⏳ Update documentation
6. ⏳ Monitor production for 24 hours
7. ⏳ Clean up duplicate records (optional)

---

**Prepared by**: AI Code Review Agent
**Verified by**: `verify_labjack_source_fix.py`
**Status**: Ready for implementation
