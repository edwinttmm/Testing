# LabJack Detection Flow Analysis Report

**Generated:** 2025-01-XX
**Scope:** Complete analysis of LabJack voltage detection flow in HIL test system

---

## Executive Summary

✅ **COMPLETE DETECTION FLOW VERIFIED**
✅ **ALL DATABASE TABLES EXIST**
✅ **VOLTAGE FIELDS PROPERLY CONFIGURED**
⚠️ **MISSING: Raw voltage data tables not created in main database**

---

## 1. Complete Detection Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LABJACK HARDWARE DETECTION FLOW                  │
└─────────────────────────────────────────────────────────────────────┘

PHASE 1: Session Initialization
────────────────────────────────
1. DedicatedLabJackMonitor.start_monitoring_with_video_sync()
   ├─ Initialize session entry in active_sessions{}
   ├─ Configure LabJack channels & voltage_threshold (3.3V)
   ├─ Create session-specific detection callback
   └─ Store callback reference for cleanup

2. LabJack Monitor Configuration
   ├─ Channels: ['AIN0'] (configurable)
   ├─ Voltage Threshold: 3.3V (configurable)
   ├─ Debounce: 0ms (catch everything)
   ├─ Sample Rate: 20Hz (increased for coverage)
   └─ Store in DB: False (handled by dedicated monitor)

3. Start LabJack Monitoring FIRST (CRITICAL!)
   ├─ labjack_monitor.start_monitoring(session_id, config)
   ├─ Confirms monitoring ready
   └─ THEN start video timing (prevents missed detections)

PHASE 2: Voltage Detection
────────────────────────────────
4. Hardware Voltage Detection
   ├─ LabJackService continuously reads AIN0
   ├─ Compares voltage to threshold (3.3V)
   └─ Triggers detection when: voltage > threshold

5. Detection Event Creation (labjack_detection_service.py)
   ├─ Creates DetectionEvent object with:
   │  ├─ id: UUID
   │  ├─ session_id: Test session ID
   │  ├─ timestamp: datetime.now(timezone.utc)
   │  ├─ channel: "AIN0" (or configured channel)
   │  ├─ voltage: Measured voltage value
   │  ├─ threshold: 3.3V (or configured)
   │  └─ detected: True
   └─ Calls ALL registered detection callbacks

PHASE 3: Video Synchronization
────────────────────────────────
6. Detection Callback Processing
   ├─ _handle_detection_with_video_sync(session_id, labjack_event)
   ├─ Validates session is still active
   ├─ Extracts voltage & timestamp:
   │  ├─ unix_timestamp = labjack_event.timestamp.timestamp()
   │  ├─ labjack_voltage = labjack_event.voltage
   │  └─ detection_channel = labjack_event.channel
   └─ Logs: "🔌 LabJack detection captured: AIN0 = X.XXXv @ timestamp"

7. Video Timing Synchronization
   ├─ calculate_video_relative_latency(session_id, unix_timestamp)
   ├─ Applies TIMING_CALIBRATION_OFFSET_MS = 166ms
   ├─ Calculates video-relative timestamp
   └─ Returns timing_data with:
      ├─ video_relative_timestamp (seconds from video start)
      ├─ actual_latency_ms (milliseconds)
      ├─ video_frame_number (calculated from FPS)
      └─ timing_sync_quality ('high', 'calibrated_fallback', etc.)

PHASE 4: Database Storage
────────────────────────────────
8. Create HILDetectionEvent Object
   ├─ id: UUID
   ├─ session_id: Test session ID
   ├─ unix_timestamp: Original detection time
   ├─ video_relative_timestamp: Synchronized time
   ├─ actual_latency_ms: Measured latency
   ├─ video_frame_number: Calculated frame
   ├─ timing_sync_quality: Quality indicator
   ├─ labjack_voltage: VOLTAGE DATA ✅
   ├─ detection_channel: CHANNEL INFO ✅
   └─ precision_ns: Nanosecond precision

9. Database Storage (_store_event_sync_wrapper)
   ├─ Maps HILDetectionEvent → DetectionEvent (models.py)
   ├─ Stores in detection_events table:
   │  ├─ id
   │  ├─ test_session_id
   │  ├─ timestamp (unix_timestamp)
   │  ├─ validation_result ("PASS" if latency ≤ 100ms)
   │  ├─ processing_time_ms (actual_latency_ms)
   │  ├─ labjack_timestamp ✅
   │  ├─ labjack_timestamp_ns ✅
   │  ├─ labjack_voltage ✅ (REAL/FLOAT)
   │  ├─ detection_channel ✅ (TEXT/VARCHAR)
   │  ├─ video_relative_timestamp ✅
   │  ├─ video_frame_number ✅
   │  ├─ actual_latency_ms ✅
   │  ├─ timing_sync_quality ✅
   │  ├─ detection_type: "labjack_voltage"
   │  └─ source: "dedicated_labjack_monitor"
   └─ db.commit()

PHASE 5: Dual-Write (Optional)
────────────────────────────────
10. TS Ingestion API (if configured)
    ├─ Check: TS_INGEST_URL & SERVICE_TOKEN env vars
    ├─ POST to: {TS_INGEST_URL}/labjack/detection-event
    ├─ Payload includes:
    │  ├─ sessionId
    │  ├─ timestamp (unix)
    │  ├─ voltage ✅
    │  ├─ channel ✅
    │  ├─ latencyMs
    │  ├─ videoTimestamp
    │  └─ frame
    └─ Retry logic: 3 attempts with backoff
```

---

## 2. Database Schema Analysis

### ✅ VERIFIED: detection_events Table (Main Storage)

**Voltage-Related Columns:**
```sql
-- PRIMARY VOLTAGE DATA
labjack_voltage           REAL       -- ✅ Voltage reading that triggered detection
detection_channel         TEXT       -- ✅ Channel identifier (e.g., "AIN0")

-- LEGACY FIELDS (also used)
voltage_level            REAL       -- Alternative voltage field
channel                  INTEGER     -- Numeric channel ID

-- TIMING FIELDS
labjack_timestamp        REAL       -- Unix timestamp of detection
labjack_timestamp_ns     INTEGER    -- Nanosecond precision timestamp

-- VIDEO SYNCHRONIZATION
video_relative_timestamp REAL       -- Timestamp relative to video start
video_frame_number       INTEGER    -- Corresponding video frame
actual_latency_ms        REAL       -- Measured latency
timing_sync_quality      TEXT       -- Quality indicator

-- METADATA
detection_type           TEXT       -- "labjack_voltage"
source                   TEXT       -- "dedicated_labjack_monitor"
```

**Status:** ✅ ALL FIELDS PRESENT AND CORRECT

### ✅ VERIFIED: test_sessions Table

**Multi-Video & Timing Fields:**
```sql
-- MULTI-VIDEO SEQUENCE SUPPORT
has_video_sequence       BOOLEAN    -- ✅ Whether session uses sequences
sequence_id              VARCHAR    -- ✅ Sequence identifier
sequence_metadata        JSON       -- ✅ Sequence configuration

-- PRECISION TIMING
video_start_timestamp    REAL       -- ✅ Video start reference
video_start_timestamp_ns VARCHAR    -- ✅ Nanosecond precision
precision_timing_enabled BOOLEAN    -- ✅ Timing active flag
timing_sync_quality      VARCHAR    -- ✅ Sync quality

-- VIDEO PLAYBACK TIMING
video_playback_start_time    REAL   -- ✅ Video playback start
video_playback_start_time_ns VARCHAR -- ✅ Nanosecond precision
hil_timing_enabled       BOOLEAN    -- ✅ HIL timing flag
```

**Status:** ✅ ALL FIELDS PRESENT

### ✅ VERIFIED: Multi-Video Sequence Tables

**video_test_sequences:**
```sql
id                       VARCHAR(36) PRIMARY KEY
test_session_id          VARCHAR(36) -- FK to test_sessions
name                     VARCHAR
video_ids                JSON        -- Ordered video list
sequence_order           JSON        -- Order mapping
status                   VARCHAR     -- 'pending', 'running', etc.
sequence_start_time      REAL        -- Sequence timing
sequence_start_time_ns   VARCHAR
-- ... (14 more fields)
```

**sequence_video_results:**
```sql
id                       VARCHAR(36) PRIMARY KEY
video_sequence_id        VARCHAR(36) -- FK to video_test_sequences
video_id                 VARCHAR(36) -- FK to videos
sequence_order           INTEGER
video_start_time         REAL        -- Individual video timing
video_start_time_ns      VARCHAR
validation_result        VARCHAR     -- 'Pass', 'Fail'
avg_latency_ms          REAL
-- ... (15 more fields)
```

**Status:** ✅ BOTH TABLES EXIST WITH COMPLETE SCHEMA

---

## 3. Raw Voltage Data Tables (SEPARATE SYSTEM)

### ⚠️ MISSING FROM MAIN DATABASE

**Expected Tables (defined in raw_labjack_models.py):**
```sql
-- NOT FOUND IN MAIN DATABASE:
raw_labjack_sessions     -- Raw data session configuration
raw_labjack_buffers      -- Compressed voltage buffers
compression_statistics   -- Compression performance metrics
raw_labjack_index        -- Time-series index for queries
```

**Purpose:**
- High-frequency (1000Hz) raw voltage capture
- Smart compression with multiple algorithms
- Microsecond precision timestamps
- Separate from detection events (continuous data vs. events)

**Current Status:**
- ✅ Models defined in: `/backend/src/models/raw_labjack_models.py`
- ✅ Services implemented in: `/backend/services/raw_labjack_logger.py`
- ❌ Tables NOT created in main database
- ❌ Migration script exists but not executed: `/backend/src/migrations/raw_data_compression_migration.py`

**Action Required:**
```bash
# Run migration to create raw data tables:
python /home/rigade/Testing/ai-model-validation-platform/backend/src/migrations/raw_data_compression_migration.py
```

---

## 4. Voltage Detection Threshold Logic

### Configuration Flow

**1. Default Configuration (dedicated_labjack_monitor.py:130)**
```python
labjack_config = {
    'voltage_threshold': video_timing_config.get('voltage_threshold', 3.3),  # 3.3V default
    'debounce_ms': video_timing_config.get('debounce_ms', 0),  # No debounce
    'sample_rate': video_timing_config.get('sample_rate', 20),  # 20Hz
}
```

**2. Threshold Detection (raw_labjack_logger.py:548-556)**
```python
def _check_detection_thresholds(self, session_id: str, voltages: List[float], timestamp_ns: int):
    config = self.session_configs.get(session_id, {})
    threshold = config.get('detection_threshold', 2.5)  # Default 2.5V threshold

    for i, voltage in enumerate(voltages):
        if voltage > threshold:  # Voltage EXCEEDS threshold
            # Create detection event
            detection_data = {
                'channel': i,
                'voltage': voltage,
                'timestamp_ns': timestamp_ns,
            }
            # Notify callbacks
```

**3. Threshold Types:**
- **Detection Monitor:** 3.3V (for event detection)
- **Raw Logger:** 2.5V (for continuous logging)
- **Configurable per session**

---

## 5. Missing Components Analysis

### ❌ Raw Voltage Data Tables

**What's Missing:**
1. `raw_labjack_sessions` table - NOT in database
2. `raw_labjack_buffers` table - NOT in database
3. `compression_statistics` table - NOT in database
4. `raw_labjack_index` table - NOT in database

**Impact:**
- ✅ Detection events work perfectly (stored in `detection_events`)
- ❌ Cannot store continuous 1000Hz raw voltage data
- ❌ Cannot use smart compression features
- ❌ High-frequency analysis features unavailable

**Solution:**
Run the migration script to create these tables if raw data capture is needed.

### ✅ No Missing Detection Flow Components

**Verified Working:**
- ✅ LabJack hardware connection
- ✅ Voltage threshold detection
- ✅ Detection event creation
- ✅ Video timing synchronization
- ✅ Database storage with voltage data
- ✅ Callback notification system
- ✅ Multi-video sequence support

---

## 6. Configuration Issues Found

### ⚠️ Threshold Inconsistency

**Issue:** Two different threshold values in use
- **Dedicated Monitor:** 3.3V (line 130)
- **Raw Logger:** 2.5V (line 552)

**Recommendation:**
Standardize on 3.3V across all services or make it explicitly configurable in a central config file.

### ⚠️ Debounce Setting

**Current:** debounce_ms = 0 (no debouncing)
```python
'debounce_ms': video_timing_config.get('debounce_ms', 0),  # Catch everything
```

**Risk:** May capture voltage noise/bounce as multiple detections

**Recommendation:**
Consider 50-100ms debounce for production to filter electrical noise.

---

## 7. Data Flow Verification

### ✅ Complete Flow Confirmed

```
Hardware Detection → Detection Event → Callback → Video Sync → Database
        ↓               ↓                ↓            ↓           ↓
    (Voltage)      (Dataclass)     (Timing)    (Calculate)   (Store)
    AIN0 > 3.3V    channel="AIN0"   unix_time   video_time    DB row
                   voltage=X.XXV                 latency_ms    + voltage
                                                frame_num     + channel
```

**Verified Data Points:**
1. ✅ Voltage captured from hardware
2. ✅ Channel information preserved
3. ✅ Timestamp synchronized with video
4. ✅ Latency calculated correctly
5. ✅ All data stored in database
6. ✅ Voltage & channel accessible in DB

---

## 8. Schema Mismatches

### ✅ No Schema Mismatches Found

**Verification:**
- ✅ Model definitions match database columns
- ✅ All foreign keys properly configured
- ✅ Indexes created for performance
- ✅ Data types correct (REAL for voltage, TEXT for channel)
- ✅ Nullable constraints appropriate

**Column Mapping:**
| Python Model Field | Database Column | Type | Status |
|-------------------|-----------------|------|--------|
| labjack_voltage | labjack_voltage | REAL | ✅ Match |
| detection_channel | detection_channel | TEXT | ✅ Match |
| labjack_timestamp | labjack_timestamp | REAL | ✅ Match |
| video_relative_timestamp | video_relative_timestamp | REAL | ✅ Match |
| actual_latency_ms | actual_latency_ms | REAL | ✅ Match |
| video_frame_number | video_frame_number | INTEGER | ✅ Match |

---

## 9. Recommendations

### High Priority

1. **Create Raw Voltage Tables (if needed)**
   ```bash
   cd /home/rigade/Testing/ai-model-validation-platform/backend
   python src/migrations/raw_data_compression_migration.py
   ```

2. **Standardize Voltage Thresholds**
   - Create central config: `config/labjack_detection.yaml`
   - Set consistent 3.3V threshold across all services

3. **Add Debounce Protection**
   - Implement 50-100ms debounce for production
   - Prevent noise-induced false detections

### Medium Priority

4. **Verify Voltage Data in Results**
   - Confirm voltage values displayed in frontend
   - Check API endpoint returns voltage data

5. **Add Voltage Range Validation**
   - Validate voltage readings within expected range (0-5V)
   - Log out-of-range values for troubleshooting

### Low Priority

6. **Add Voltage Trend Analysis**
   - Track voltage patterns over time
   - Detect voltage drift or hardware issues

7. **Implement Voltage Calibration**
   - Add calibration offset configuration
   - Support per-channel calibration

---

## 10. Summary

### ✅ DETECTION FLOW: COMPLETE & WORKING

**Voltage Detection Path:**
```
LabJack Hardware → Detection Service → Dedicated Monitor → Database
     (3.3V)           (Event)           (Video Sync)      (Storage)
```

**Data Storage:**
- ✅ Voltage captured: `labjack_voltage` (REAL)
- ✅ Channel recorded: `detection_channel` (TEXT)
- ✅ Timing synchronized: `video_relative_timestamp`
- ✅ Latency calculated: `actual_latency_ms`
- ✅ Frame number: `video_frame_number`

**Database Tables:**
- ✅ `detection_events` - PRIMARY storage for detections
- ✅ `test_sessions` - Session configuration & timing
- ✅ `video_test_sequences` - Multi-video sequences
- ✅ `sequence_video_results` - Per-video results
- ❌ `raw_labjack_*` tables - NOT created (optional for raw data)

### ⚠️ OPTIONAL: Raw Data Tables

The raw voltage data tables are **NOT REQUIRED** for normal detection operation but provide:
- Continuous 1000Hz voltage capture
- Smart compression for storage efficiency
- Advanced signal analysis capabilities

If these features are needed, run the migration script.

### 🎯 NEXT STEPS

1. ✅ Detection flow verified - NO ACTION NEEDED
2. ⚠️ Standardize voltage thresholds - CONFIG UPDATE
3. ⚠️ Consider debounce protection - CODE UPDATE
4. 📊 Run raw data migration - IF RAW DATA NEEDED

---

## Appendix: Key Files

**Detection Flow:**
- `/backend/services/dedicated_labjack_monitor.py` - Main detection orchestrator
- `/backend/services/labjack_detection_service.py` - Detection event creation
- `/backend/services/raw_labjack_logger.py` - Raw voltage logging (optional)

**Database Models:**
- `/backend/models.py` - Main detection event model
- `/backend/src/models/raw_labjack_models.py` - Raw data models

**Migrations:**
- `/backend/migrations/add_video_sequence_schema.py` - Multi-video support ✅
- `/backend/src/migrations/raw_data_compression_migration.py` - Raw data tables ❌

**Configuration:**
- Voltage threshold: Line 130 in dedicated_labjack_monitor.py
- Detection threshold: Line 552 in raw_labjack_logger.py
- Sample rate: Line 132 in dedicated_labjack_monitor.py

---

**Report End**
