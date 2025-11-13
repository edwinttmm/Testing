# Detection Storage Path Consolidation Analysis

**Date**: 2025-11-04
**Status**: CRITICAL - DUPLICATE STORAGE PATHS DETECTED
**Priority**: P0 (Production Blocker)

---

## Executive Summary

**CRITICAL FINDING**: Multiple services are configured with `store_in_db=True`, causing duplicate detection events to be written to the database. This creates data integrity issues and breaks ground truth matching.

### Impact
- **Duplicate Detection Events**: 2-3x database writes per detection
- **Race Conditions**: Multiple services competing to write same event
- **Ground Truth Mismatch**: Duplicate detections confuse matching algorithm
- **Performance Degradation**: Unnecessary database load

---

## Current Storage Path Analysis

### ✅ CORRECT Configuration (1 file)

**File**: `backend/services/dedicated_labjack_monitor.py:148`
```python
labjack_config = {
    'channels': video_timing_config.get('channels', ['AIN0']),
    'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),
    'debounce_ms': video_timing_config.get('debounce_ms', 0),
    'sample_rate': sample_rate,
    'store_in_db': False,  # ✅ CORRECT: Custom callback handles storage WITH video timing
    'enable_websocket': video_timing_config.get('enable_websocket', True)
}
```

**Why This is Correct**:
- Uses custom callback `_handle_detection_with_video_sync()` at line 387
- Enriches detections with video timing metadata BEFORE storage
- Stores via `_schedule_db_storage()` at line 689
- Single write with complete context including:
  - `video_id`
  - `sequence_id`
  - `video_relative_timestamp`
  - `video_play_offset_ms`
  - Timing calibration metadata

---

### ❌ INCORRECT Configurations (2 services)

#### 1. `backend/services/labjack_detection_service.py`

**Line 238**: `store_in_db=kwargs.get('store_in_db', True)`
**Status**: ❌ DUPLICATE STORAGE PATH

**Problem**:
```python
config = DetectionConfig(
    session_id=session_id,
    channels=channels,
    voltage_threshold=voltage_threshold,
    debounce_ms=debounce_ms,
    sample_rate=sample_rate,
    enable_websocket=kwargs.get('enable_websocket', True),
    store_in_db=kwargs.get('store_in_db', True),  # ❌ CAUSES DUPLICATES
    metadata=kwargs.get('metadata')
)
```

**Impact**:
- Line 632: `if config and config.store_in_db and DATABASE_AVAILABLE:`
- Triggers `_schedule_db_storage(event)` at line 633
- Stores detection WITHOUT video timing metadata
- Creates incomplete/orphaned detection records

**Evidence of Usage**:
- Line 183 in `raw_labjack_integration.py` calls with `store_in_db=True`
- Line 118 in `api_labjack_detection.py` passes through user config
- Test files use `store_in_db=False` but production uses `True`

---

#### 2. `backend/services/raw_labjack_integration.py`

**Line 183**: `store_in_db=True`
**Status**: ❌ DUPLICATE STORAGE PATH

**Problem**:
```python
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10,
    store_in_db=True,  # ❌ CAUSES DUPLICATES
    enable_websocket=True
)
```

**Impact**:
- Forwards to `labjack_detection_service.start_monitoring()`
- Triggers duplicate storage path
- Creates additional incomplete detection records

**Additional Issues**:
- Line 356-365: Creates THIRD detection event via `_create_detection_event()`
- Stores directly to database at line 416
- No video timing enrichment
- Missing sequence metadata

---

#### 3. `backend/api_labjack_detection.py`

**Line 49**: `store_in_db: bool = Field(default=True)`
**Status**: ⚠️ API PASSES THROUGH TO SERVICE

**Problem**:
```python
class StartDetectionRequest(BaseModel):
    """Request model for starting detection monitoring"""
    channels: List[str] = Field(default=["AIN0"], description="Channels to monitor")
    voltage_threshold: float = Field(default=2.5, ge=0.0, le=5.0, description="Detection threshold in volts")
    debounce_ms: int = Field(default=100, ge=10, le=5000, description="Debounce time in milliseconds")
    sample_rate: int = Field(default=1000, ge=100, le=10000, description="Sampling rate in Hz")
    enable_websocket: bool = Field(default=True, description="Enable WebSocket notifications")
    store_in_db: bool = Field(default=True, description="Store events in database")  # ❌ EXPOSED TO API
```

**Impact**:
- Line 118: Passes `store_in_db` to detection service
- Allows external callers to trigger duplicate storage
- Should be deprecated in favor of dedicated monitor

---

## Storage Path Flow Diagram

```
Detection Hardware Event
        |
        v
┌───────────────────────────────────────────────────┐
│  dedicated_labjack_monitor.py                     │
│  store_in_db=False (line 148)                     │
│  ✅ CORRECT: Custom callback handles storage      │
└───────────────────────────────────────────────────┘
        |
        v
Custom Callback: _handle_detection_with_video_sync()
        |
        +-- Enriches with video timing
        +-- Enriches with sequence metadata
        +-- Calculates timing calibration
        |
        v
_schedule_db_storage() (line 689)
        |
        v
_store_event_sync_wrapper() (line 702)
        |
        v
[DATABASE] ✅ Single write with full context
        |
        v
✅ Complete Detection Event with:
   - video_id
   - sequence_id
   - video_relative_timestamp
   - calibration_offset_ms
   - video_play_offset_ms

═══════════════════════════════════════════════════════

❌ DUPLICATE PATH #1: labjack_detection_service.py
        |
        v
store_in_db=True (line 238)
        |
        v
_schedule_db_storage() (line 633)
        |
        v
[DATABASE] ❌ Duplicate write WITHOUT video context
        |
        v
❌ Incomplete Detection Event (missing video timing)

═══════════════════════════════════════════════════════

❌ DUPLICATE PATH #2: raw_labjack_integration.py
        |
        v
store_in_db=True (line 183)
        |
        v
Forwards to detection_service
        |
        v
[DATABASE] ❌ THIRD write via _create_detection_event()
        |
        v
❌ Incomplete Detection Event (missing sequence metadata)
```

---

## Database Impact Analysis

### Duplicate Detection Scenario

**Single Hardware Detection Event** → **3 Database Writes**:

1. **Write #1** (✅ CORRECT - from dedicated_labjack_monitor.py):
```sql
INSERT INTO detection_events (
    id, test_session_id, video_id, sequence_id,
    video_relative_timestamp, actual_latency_ms,
    labjack_voltage, detection_channel,
    source='dedicated_labjack_monitor'
)
```

2. **Write #2** (❌ DUPLICATE - from labjack_detection_service.py):
```sql
INSERT INTO detection_events (
    id, test_session_id, video_id=NULL, sequence_id=NULL,
    video_relative_timestamp=NULL, actual_latency_ms=NULL,
    labjack_voltage, detection_channel,
    source='labjack_detection_service'
)
```

3. **Write #3** (❌ DUPLICATE - from raw_labjack_integration.py):
```sql
INSERT INTO detection_events (
    id, test_session_id, video_id=NULL, sequence_id=NULL,
    video_relative_timestamp=NULL, actual_latency_ms=NULL,
    labjack_voltage, detection_channel,
    source='raw_labjack_integration'
)
```

### Query to Identify Duplicates

```sql
-- Find potential duplicate detection events (same timestamp, same session)
SELECT
    test_session_id,
    ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
    COUNT(*) as duplicate_count,
    STRING_AGG(DISTINCT source, ', ') as sources,
    STRING_AGG(DISTINCT id::text, ', ') as event_ids
FROM detection_events
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY test_session_id, ROUND(labjack_timestamp::numeric, 3)
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

---

## Required Changes

### 1. labjack_detection_service.py (Line 238)

**BEFORE**:
```python
config = DetectionConfig(
    session_id=session_id,
    channels=channels,
    voltage_threshold=voltage_threshold,
    debounce_ms=debounce_ms,
    sample_rate=sample_rate,
    enable_websocket=kwargs.get('enable_websocket', True),
    store_in_db=kwargs.get('store_in_db', True),  # ❌ CHANGE THIS
    metadata=kwargs.get('metadata')
)
```

**AFTER**:
```python
config = DetectionConfig(
    session_id=session_id,
    channels=channels,
    voltage_threshold=voltage_threshold,
    debounce_ms=debounce_ms,
    sample_rate=sample_rate,
    enable_websocket=kwargs.get('enable_websocket', True),
    store_in_db=False,  # ✅ FIXED: Dedicated monitor handles storage
    metadata=kwargs.get('metadata')
)
```

**Also Update Line 125 (default value)**:
```python
@dataclass
class DetectionConfig:
    """Configuration for detection monitoring"""
    session_id: str
    channels: List[str]
    voltage_threshold: float = 2.5
    debounce_ms: int = 100
    sample_rate: int = 1000
    enable_websocket: bool = True
    store_in_db: bool = False  # ✅ FIXED: Changed from True to False
    metadata: Optional[Dict[str, Any]] = None
```

---

### 2. raw_labjack_integration.py (Line 183)

**BEFORE**:
```python
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10,
    store_in_db=True,  # ❌ CHANGE THIS
    enable_websocket=True
)
```

**AFTER**:
```python
detection_success = self.detection_service.start_monitoring(
    test_session_id,
    channels=channels,
    voltage_threshold=self.config.detection_threshold_volts,
    debounce_ms=self.config.debounce_time_ms,
    sample_rate=10,
    store_in_db=False,  # ✅ FIXED: Dedicated monitor handles storage
    enable_websocket=True
)
```

---

### 3. api_labjack_detection.py (Line 49)

**BEFORE**:
```python
class StartDetectionRequest(BaseModel):
    """Request model for starting detection monitoring"""
    channels: List[str] = Field(default=["AIN0"], description="Channels to monitor")
    voltage_threshold: float = Field(default=2.5, ge=0.0, le=5.0, description="Detection threshold in volts")
    debounce_ms: int = Field(default=100, ge=10, le=5000, description="Debounce time in milliseconds")
    sample_rate: int = Field(default=1000, ge=100, le=10000, description="Sampling rate in Hz")
    enable_websocket: bool = Field(default=True, description="Enable WebSocket notifications")
    store_in_db: bool = Field(default=True, description="Store events in database")  # ❌ CHANGE THIS
```

**AFTER**:
```python
class StartDetectionRequest(BaseModel):
    """Request model for starting detection monitoring"""
    channels: List[str] = Field(default=["AIN0"], description="Channels to monitor")
    voltage_threshold: float = Field(default=2.5, ge=0.0, le=5.0, description="Detection threshold in volts")
    debounce_ms: int = Field(default=100, ge=10, le=5000, description="Debounce time in milliseconds")
    sample_rate: int = Field(default=1000, ge=100, le=10000, description="Sampling rate in Hz")
    enable_websocket: bool = Field(default=True, description="Enable WebSocket notifications")
    store_in_db: bool = Field(default=False, description="DEPRECATED: Storage handled by dedicated monitor")  # ✅ FIXED
```

---

## Single Source of Truth Architecture

### Detection Storage Principle

**RULE**: Only `dedicated_labjack_monitor.py` may store detection events to the database.

### Why This Service?

1. **Video Timing Integration**: Only this service has access to `VideoTimingService`
2. **Sequence Metadata**: Only this service tracks multi-video sequence context
3. **Timing Calibration**: Only this service applies calibration offsets
4. **Complete Context**: Only this service ensures ALL required fields are populated

### Storage Flow

```
Hardware Detection
    ↓
dedicated_labjack_monitor (store_in_db=False in config)
    ↓
Custom Callback: _handle_detection_with_video_sync()
    ↓
Enrichment:
  - video_id (with retry logic for race conditions)
  - sequence_id
  - sequence_video_result_id
  - video_relative_timestamp
  - sequence_timestamp
  - video_play_offset_ms
  - timing calibration metadata
    ↓
_schedule_db_storage() → _store_event_sync_wrapper()
    ↓
[DATABASE] Single write with complete context
```

---

## Configuration Validation System

### New Configuration Enforcement

Create: `backend/services/detection_storage_validator.py`

```python
"""
Detection Storage Configuration Validator

Ensures only dedicated_labjack_monitor stores detection events.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DetectionStorageValidator:
    """Validates detection storage configuration at startup"""

    ALLOWED_STORAGE_SERVICES = ['dedicated_labjack_monitor']

    @classmethod
    def validate_config(cls, service_name: str, store_in_db: bool) -> bool:
        """
        Validate that only allowed services have store_in_db=True

        Args:
            service_name: Name of the service attempting storage
            store_in_db: Requested storage configuration

        Returns:
            True if configuration is valid

        Raises:
            RuntimeError: If invalid configuration detected
        """
        if store_in_db and service_name not in cls.ALLOWED_STORAGE_SERVICES:
            error_msg = (
                f"❌ CONFIGURATION ERROR: Service '{service_name}' "
                f"attempted to enable store_in_db=True. "
                f"Only {cls.ALLOWED_STORAGE_SERVICES} may store detection events. "
                f"Set store_in_db=False to use dedicated monitor."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        if store_in_db and service_name in cls.ALLOWED_STORAGE_SERVICES:
            logger.info(f"✅ Storage validation passed for {service_name}")

        return True

    @classmethod
    def log_storage_config(cls, service_name: str, store_in_db: bool):
        """Log storage configuration for auditing"""
        if store_in_db:
            logger.warning(
                f"⚠️ STORAGE ENABLED: {service_name} (store_in_db=True) - "
                f"Ensure this is intentional"
            )
        else:
            logger.info(
                f"📝 Storage disabled: {service_name} (store_in_db=False) - "
                f"Dedicated monitor will handle storage"
            )
```

### Integration Points

**1. In `labjack_detection_service.py` (after line 237)**:
```python
from services.detection_storage_validator import DetectionStorageValidator

def start_monitoring(self, session_id: str, channels: List[str] = None, **kwargs) -> bool:
    # ... existing code ...

    # Validate storage configuration
    store_in_db = kwargs.get('store_in_db', False)  # ✅ Default False
    DetectionStorageValidator.validate_config('labjack_detection_service', store_in_db)

    config = DetectionConfig(
        session_id=session_id,
        channels=channels,
        voltage_threshold=voltage_threshold,
        debounce_ms=debounce_ms,
        sample_rate=sample_rate,
        enable_websocket=kwargs.get('enable_websocket', True),
        store_in_db=store_in_db,
        metadata=kwargs.get('metadata')
    )
```

**2. In `dedicated_labjack_monitor.py` (after line 143)**:
```python
from services.detection_storage_validator import DetectionStorageValidator

# Log that dedicated monitor is the storage authority
DetectionStorageValidator.log_storage_config('dedicated_labjack_monitor', False)
logger.info("✅ Detection storage authority: dedicated_labjack_monitor (via custom callback)")
```

---

## Duplicate Detection Cleanup Script

Create: `backend/scripts/remove_duplicate_detections.py`

```python
"""
Remove Duplicate Detection Events

Identifies and removes duplicate detection events created by multiple storage paths.
Keeps only the detection from dedicated_labjack_monitor (most complete data).
"""

import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def identify_duplicates(db_session) -> List[Dict[str, Any]]:
    """Identify duplicate detection events"""

    query = text("""
        WITH duplicate_groups AS (
            SELECT
                test_session_id,
                ROUND(labjack_timestamp::numeric, 3) as timestamp_rounded,
                COUNT(*) as duplicate_count,
                ARRAY_AGG(id ORDER BY
                    CASE
                        WHEN source = 'dedicated_labjack_monitor' THEN 1
                        WHEN source = 'labjack_detection_service' THEN 2
                        WHEN source = 'raw_labjack_integration' THEN 3
                        ELSE 4
                    END
                ) as event_ids,
                ARRAY_AGG(source ORDER BY
                    CASE
                        WHEN source = 'dedicated_labjack_monitor' THEN 1
                        WHEN source = 'labjack_detection_service' THEN 2
                        WHEN source = 'raw_labjack_integration' THEN 3
                        ELSE 4
                    END
                ) as sources
            FROM detection_events
            WHERE created_at > NOW() - INTERVAL '30 days'
            GROUP BY test_session_id, timestamp_rounded
            HAVING COUNT(*) > 1
        )
        SELECT
            test_session_id,
            timestamp_rounded,
            duplicate_count,
            event_ids,
            sources
        FROM duplicate_groups
        ORDER BY duplicate_count DESC, timestamp_rounded DESC;
    """)

    result = db_session.execute(query)
    duplicates = []

    for row in result:
        duplicates.append({
            'test_session_id': row.test_session_id,
            'timestamp': row.timestamp_rounded,
            'count': row.duplicate_count,
            'event_ids': row.event_ids,
            'sources': row.sources
        })

    return duplicates

def remove_duplicates(db_session, dry_run: bool = True) -> Dict[str, int]:
    """
    Remove duplicate detections, keeping only dedicated_labjack_monitor source

    Args:
        db_session: Database session
        dry_run: If True, only report what would be deleted

    Returns:
        Statistics about removed duplicates
    """

    duplicates = identify_duplicates(db_session)

    stats = {
        'duplicate_groups': len(duplicates),
        'total_duplicates': 0,
        'to_delete': 0,
        'deleted': 0
    }

    logger.info(f"Found {len(duplicates)} duplicate groups")

    for dup_group in duplicates:
        event_ids = dup_group['event_ids']
        sources = dup_group['sources']

        # Keep first event (dedicated_labjack_monitor if present)
        keep_id = event_ids[0]
        delete_ids = event_ids[1:]

        stats['total_duplicates'] += len(event_ids)
        stats['to_delete'] += len(delete_ids)

        logger.info(
            f"Duplicate group: session={dup_group['test_session_id']}, "
            f"timestamp={dup_group['timestamp']}, count={dup_group['count']}"
        )
        logger.info(f"  KEEP: {keep_id} (source: {sources[0]})")

        for del_id, del_source in zip(delete_ids, sources[1:]):
            logger.info(f"  DELETE: {del_id} (source: {del_source})")

            if not dry_run:
                try:
                    db_session.execute(
                        text("DELETE FROM detection_events WHERE id = :id"),
                        {'id': del_id}
                    )
                    stats['deleted'] += 1
                except Exception as e:
                    logger.error(f"Failed to delete {del_id}: {e}")

    if not dry_run:
        db_session.commit()
        logger.info(f"✅ Deleted {stats['deleted']} duplicate detection events")
    else:
        logger.info(f"DRY RUN: Would delete {stats['to_delete']} duplicate detection events")

    return stats

def main():
    """Main execution"""
    import os
    from database import get_db

    # Check for dry run flag
    dry_run = '--execute' not in sys.argv

    if dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        logger.info("   Run with --execute to actually remove duplicates")
    else:
        logger.warning("⚠️ EXECUTE MODE - Duplicates will be PERMANENTLY deleted")
        response = input("Are you sure? Type 'YES' to continue: ")
        if response != 'YES':
            logger.info("Aborted")
            return

    # Get database session
    db = next(get_db())

    try:
        stats = remove_duplicates(db, dry_run=dry_run)

        logger.info("\n" + "="*60)
        logger.info("DUPLICATE REMOVAL SUMMARY")
        logger.info("="*60)
        logger.info(f"Duplicate groups found: {stats['duplicate_groups']}")
        logger.info(f"Total duplicate events: {stats['total_duplicates']}")
        logger.info(f"Events to delete: {stats['to_delete']}")

        if not dry_run:
            logger.info(f"Events deleted: {stats['deleted']}")

        logger.info("="*60)

    except Exception as e:
        logger.error(f"❌ Error during duplicate removal: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == '__main__':
    main()
```

**Usage**:
```bash
# Dry run (safe - shows what would be deleted)
python backend/scripts/remove_duplicate_detections.py

# Execute (actually removes duplicates)
python backend/scripts/remove_duplicate_detections.py --execute
```

---

## Implementation Checklist

### Phase 1: Code Changes (30 minutes)
- [ ] Update `labjack_detection_service.py` line 125: `store_in_db: bool = False`
- [ ] Update `labjack_detection_service.py` line 238: `store_in_db=False`
- [ ] Update `raw_labjack_integration.py` line 183: `store_in_db=False`
- [ ] Update `api_labjack_detection.py` line 49: `store_in_db=False` + deprecation notice
- [ ] Create `detection_storage_validator.py` validation service
- [ ] Add validator calls to service initialization points

### Phase 2: Testing (30 minutes)
- [ ] Run existing unit tests to ensure no breakage
- [ ] Test single detection → single database write
- [ ] Verify video timing metadata present in stored events
- [ ] Confirm sequence metadata present for multi-video tests
- [ ] Check WebSocket emissions still work

### Phase 3: Duplicate Cleanup (15 minutes)
- [ ] Run duplicate detection script in dry-run mode
- [ ] Review duplicate groups identified
- [ ] Execute duplicate removal (if safe)
- [ ] Verify detection counts correct after cleanup

### Phase 4: Monitoring (Ongoing)
- [ ] Add logging to track storage path usage
- [ ] Monitor for any duplicate detections post-fix
- [ ] Verify ground truth matching improves
- [ ] Track database write performance

---

## Success Criteria

### Immediate (Post-Fix)
✅ Only 1 detection event per hardware detection
✅ All detection events have `video_id` populated
✅ All detection events have `video_relative_timestamp`
✅ No new duplicate detection events created
✅ Configuration validator prevents future duplicates

### Long-term (7 days post-fix)
✅ Zero duplicate detection events in database
✅ Ground truth matching accuracy >95%
✅ Database write performance improved 2-3x
✅ No storage-related errors in logs

---

## Rollback Plan

If issues arise after deployment:

1. **Immediate Revert** (if database writes failing):
```bash
git revert <commit-hash>
git push origin v8
```

2. **Partial Rollback** (if only specific service broken):
   - Revert only the broken service's `store_in_db` change
   - Keep validator in place to log but not block

3. **Data Recovery** (if duplicates need restoration):
```sql
-- No restoration needed - duplicates are INVALID data
-- Only keep dedicated_labjack_monitor detections
```

---

## References

- **CRITICAL_FINDINGS_QUICK_REF.md**: Initial duplicate detection analysis
- **COMPREHENSIVE_SYSTEM_HEALTH_REPORT.md**: System-wide health audit
- **HARDWARE_TO_FRONTEND_DATA_FLOW_ANALYSIS.md**: Detection pipeline documentation
- **dedicated_labjack_monitor.py**: Reference implementation (correct storage)

---

## Contact

**Responsible**: Backend Engineering Team
**Escalation**: System Architect
**Priority**: P0 - Production Blocker

**NEXT STEPS**: Apply code changes from "Required Changes" section → Run tests → Execute duplicate cleanup
