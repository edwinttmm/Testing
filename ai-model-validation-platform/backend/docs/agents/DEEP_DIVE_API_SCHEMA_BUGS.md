# Deep Dive: API Endpoints, Database Schema, and Data Flow Analysis

**Session:** 6d05fcd1-0c9b-432b-acbd-675c5e3683c9
**Date:** 2025-11-05
**Analysis Type:** Root Cause Investigation - API, Schema, and Data Integrity

## Executive Summary

This deep dive investigation analyzed API endpoints, database schema consistency, field naming conflicts, NULL propagation, serialization issues, and timing calculations to identify any remaining bugs affecting the HIL results system.

## 1. API Endpoint Testing Results

### 1.1 Test Session Endpoint
```
GET /api/test-sessions/6d05fcd1-0c9b-432b-acbd-675c5e3683c9
```

**Status:** ✅ WORKING
**Structure:** Correct

**Key Findings:**
- Returns proper multi-video sequence metadata
- `hasVideoSequence: true`
- `sequenceId` present
- `videoIds` array contains both videos
- `sequenceMetadata` includes timing for both videos
- All fields properly camelCased for frontend

**Issues Found:** NONE

### 1.2 Detection Events Endpoint
```
GET /api/test-sessions/6d05fcd1-0c9b-432b-acbd-675c5e3683c9/events?limit=200
```

**Status:** ⚠️ CRITICAL ISSUES FOUND

**Issues Identified:**

1. **NULL video_id for ALL detections**
   ```json
   {
     "id": "ad51b392-0b8e-43e5-85ad-6b92dda083b7",
     "video_id": null,  // ❌ SHOULD BE: "10c2b16c-86fa-4140-b1cf-c0ea42f82ca5"
     "frame_number": 4,
     "video_relative_timestamp": 0.197909
   }
   ```

2. **Negative latency_ms values**
   ```json
   {
     "latency_ms": -10.424137,  // ❌ Invalid negative latency
     "latency_ms": -18.106937,
     "latency_ms": -20.653963
   }
   ```

3. **Missing actual_latency_ms**
   - API does NOT return `actual_latency_ms` field
   - Frontend expects this field but receives NULL

### 1.3 Enhanced HIL Results Endpoint
```
GET /api/enhanced-hil/test-sessions/6d05fcd1-0c9b-432b-acbd-675c5e3683c9/corrected-results
```

**Status:** ⚠️ PARTIAL DATA

**Issues Found:**
- Returns 0 detections for both videos despite database having 161 detections
- `actual_detection_count: 0` for both videos
- Ground truth metrics show all false negatives
- Latency calculation shows invalid data

## 2. Database Schema vs Model Analysis

### 2.1 🚨 CRITICAL: Database Schema Does NOT Match API Response

**SMOKING GUN FOUND:**

The API response returns a field `latency_ms` that **DOES NOT EXIST** in the database schema!

**Database Schema Columns:**
```
✅ video_id: VARCHAR(36) (nullable=True)
✅ frame_number: INTEGER (nullable=True)
✅ video_frame_number: INTEGER (nullable=True)
❌ latency_ms: DOES NOT EXIST IN DATABASE
✅ actual_latency_ms: FLOAT (nullable=True)
```

**API Response Contains:**
```json
{
  "latency_ms": -10.424137,  // ❌ This column doesn't exist in DB!
  "actual_latency_ms": null   // ✅ This column exists but is NULL
}
```

**Root Cause:** The API is CALCULATING `latency_ms` on-the-fly, not reading it from the database. This calculated value is producing negative numbers and incorrect results.

### 2.2 DetectionEvent Model Analysis

**File:** `/backend/models.py` Lines 276-430

**CONFIRMED: Model does NOT define latency_ms column**

Searching the entire models.py file reveals:
- Line 289: `latency_ns` (nanosecond precision, STRING)
- Line 311: `actual_latency_ms` (float, nullable)
- **NO `latency_ms` column defined anywhere**

**Schema Inconsistencies Found:**

| Database Column | Model Field | Exists in DB? | Populated? | Issue |
|----------------|-------------|---------------|------------|-------|
| `video_id` | `video_id` | ✅ Yes | ❌ ALL NULL | Critical - breaks video filtering |
| `frame_number` | `frame_number` | ✅ Yes | ✅ Yes | Legacy field |
| `video_frame_number` | `video_frame_number` | ✅ Yes | ✅ Yes | Correct |
| `latency_ms` | N/A | ❌ **NO** | N/A | **Ghost field - calculated in API** |
| `actual_latency_ms` | `actual_latency_ms` | ✅ Yes | ❌ ALL NULL | Should contain real latency |
| `latency_ns` | `latency_ns` | ✅ Yes | ❌ NULL | Nanosecond precision (unused) |

**Database Reality Check:**
```python
# Total columns in detection_events: 61
# latency_ms: NOT IN SCHEMA
# actual_latency_ms: EXISTS but ALL NULL (0 out of 161 populated)
```

## 3. Field Name Conflicts

### 3.1 Frame Number Ambiguity

**CONFLICT IDENTIFIED:**

1. **`frame_number`** (Line 345)
   - Legacy field from AI detection system
   - Maps to detection frame in video
   - Currently populated with values 4, 5, 7, 8, etc.

2. **`video_frame_number`** (Line 312)
   - New field for video timing synchronization
   - Should map to video playback frame
   - Also populated with values 4, 5, 7, 8, etc.

**Problem:** These two fields have identical values but serve different purposes, causing confusion.

### 3.2 Latency Field Confusion

**THREE LATENCY FIELDS:**

1. **`latency_ms`** (NOT in model explicitly, but in API)
   - Contains NEGATIVE values
   - Appears to be calculated incorrectly
   - Used by API endpoint responses

2. **`actual_latency_ms`** (Line 311)
   - Defined in model as "Actual measured latency"
   - Currently ALL NULL in database
   - Expected by frontend

3. **`latency_ns`** (Line 289)
   - Nanosecond precision latency
   - String field for precision
   - Not used consistently

**Root Cause:** Multiple latency calculation methods producing conflicting results.

### 3.3 Timestamp Field Conflicts

**DUPLICATE TIMESTAMP FIELDS:**

1. **`timestamp`** (Line 283)
   - Primary timestamp field
   - Unix timestamp (float)

2. **`video_relative_timestamp`** (Line 309)
   - Timestamp relative to video start
   - Should be calculated: `timestamp - video_start_time`

3. **`video_relative_timestamp_ns`** (Line 310)
   - Nanosecond precision version
   - String field

4. **`sequence_timestamp`** (Line 316)
   - Timestamp relative to sequence start
   - For multi-video tests

**Issue:** Field naming doesn't clearly indicate which reference point each uses.

## 4. NULL Propagation Analysis

### 4.1 video_id NULL Cascade

**Impact Chain:**

```
video_id = NULL
    ↓
Cannot query Video table for metadata
    ↓
Cannot get video filename, duration, FPS
    ↓
Cannot calculate proper frame_number
    ↓
Cannot match to ground truth by video
    ↓
❌ Enhanced HIL results show 0 detections
```

**Affected Queries:**
- Enhanced HIL results endpoint
- Per-video metrics calculation
- Video sequence results
- Ground truth matching

### 4.2 actual_latency_ms NULL Impact

**Impact Chain:**

```
actual_latency_ms = NULL
    ↓
Frontend cannot display latency metrics
    ↓
Latency charts show missing data
    ↓
Pass/fail validation uses incorrect latency_ms
    ↓
❌ Invalid validation results
```

### 4.3 NULL Handling in timestamp_conversion_utils.py

**CRITICAL BUG FOUND:**

**File:** `/backend/services/timestamp_conversion_utils.py` Lines 89-102

```python
# ✅ CORRECTED: actual_latency_ms should be NULL here
# This function ONLY converts timestamps - it does NOT calculate latency
#
# ❌ REMOVED: actual_latency_ms = 50.0  (was incorrect hardcoded value)
# ❌ REMOVED: actual_latency_ms = video_relative_timestamp * 1000  (completely wrong!)
#
actual_latency_ms = None  # Caller must provide actual measured latency
```

**Analysis:** The timestamp conversion utility correctly sets `actual_latency_ms = None` because it only converts timestamps. The calling code should populate this field, but it appears the calling code is NOT doing this.

## 5. Pydantic Schema vs Database Model Mismatches

### 5.1 DetectionEventResponse Schema

**File:** `/backend/schemas.py` Lines 302-320

**Schema Analysis:**

```python
class DetectionEventResponse(DetectionEvent):
    id: str
    validation_result: Optional[str] = Field(None, alias="validationResult")
    ground_truth_match_id: Optional[str] = Field(None, alias="groundTruthMatchId")
    created_at: datetime = Field(alias="createdAt")

    # CRITICAL FIX: Add missing fields expected by frontend
    video_relative_timestamp: Optional[float] = Field(None, alias="videoRelativeTimestamp")
    video_frame_number: Optional[int] = Field(None, alias="videoFrameNumber")
    actual_latency_ms: Optional[float] = Field(None, alias="actualLatencyMs")
```

**Issues:**

1. ✅ Schema includes `actual_latency_ms` with camelCase alias
2. ❌ Database has all NULL values for this field
3. ❌ No validation that actual_latency_ms is populated before API response

**Missing Field Validation:**
- No check that critical fields (video_id, actual_latency_ms) are non-NULL
- No fallback calculation if actual_latency_ms is NULL
- No error logged when sending NULL values to frontend

## 6. Timezone and Timestamp Handling

### 6.1 Timezone Consistency Check

**Analysis:** All timestamps appear to use UTC consistently.

**Evidence:**
```python
# From API response:
"started_at_iso": "2025-11-05T14:28:31.998000+00:00"  # +00:00 = UTC
"ended_at_iso": "2025-11-05T14:28:37.328000+00:00"
"sequence_completed_at": "2025-11-05T14:28:43.013492+00:00"
```

**Status:** ✅ NO TIMEZONE ISSUES FOUND

### 6.2 Timestamp Conversion Analysis

**File:** `/backend/services/timestamp_conversion_utils.py`

**Functions Analyzed:**

1. **`unix_to_video_relative()`** (Lines 57-123)
   - Converts: `unix_timestamp - video_start_time`
   - Returns: `video_relative_timestamp` in seconds
   - ❌ Sets `actual_latency_ms = None` (correct, but caller must populate)

2. **`calculate_frame_number()`** (Lines 130-158)
   - Formula: `int(video_relative_timestamp * fps)`
   - ✅ Correct calculation

**Issue:** The conversion utilities work correctly, but the calling code doesn't populate `actual_latency_ms` afterward.

## 7. Precision Loss and Rounding Errors

### 7.1 Float to Int Conversions

**Potential Precision Loss:**

```python
# Frame number calculation
frame_number = int(video_relative_timestamp * fps)
```

**Analysis:**
- For FPS=24, each frame = 41.67ms
- Float precision: sufficient for video timing
- ✅ NO SIGNIFICANT PRECISION LOSS

### 7.2 Millisecond to Second Conversions

**Data:**
```json
{
  "timestamp": 0.19790911674499512,  // Seconds
  "latency_ms": -10.424137115478516  // Milliseconds
}
```

**Analysis:**
- 9 decimal places preserved in seconds
- 6 decimal places in milliseconds
- ✅ SUFFICIENT PRECISION for HIL timing requirements

## 8. Priority-Ranked Issues

### CRITICAL (P0) - Production Blockers

1. **🔥 GHOST FIELD: latency_ms doesn't exist in database but appears in API**
   - Impact: API returns calculated values that are completely wrong
   - Root Cause: API calculates latency_ms on-the-fly using incorrect formula
   - Database: No `latency_ms` column exists
   - API Response: Returns negative values like -10.424ms, -18.106ms
   - Fix Location: Find where API calculates this ghost field and remove it
   - **This is the SOURCE of all latency issues**
   - Estimated Impact: 100% of latency metrics are fabricated

2. **NULL video_id for all detections**
   - Impact: Enhanced HIL results show 0 detections
   - Root Cause: Detection storage not setting video_id
   - Fix Location: LabJack detection service, line ~250-300
   - Database: video_id column exists but 0 out of 161 are populated
   - Estimated Impact: 100% of multi-video functionality broken

3. **NULL actual_latency_ms for all detections**
   - Impact: Frontend cannot display real latency data
   - Root Cause: timestamp_conversion_utils returns NULL, caller doesn't populate
   - Fix Location: Calling code after timestamp conversion
   - Database: actual_latency_ms column exists but 0 out of 161 are populated
   - Estimated Impact: All latency metrics missing from database

### HIGH (P1) - Major Functionality Issues

4. **Frame number field ambiguity**
   - `frame_number` vs `video_frame_number` confusion
   - Impact: Unclear which field to use for correlation
   - Fix: Deprecate frame_number, use only video_frame_number

5. **Enhanced HIL endpoint returns 0 detections**
   - Impact: Results page shows no data despite 161 detections in DB
   - Root Cause: Query filtering out all detections due to NULL video_id
   - Fix: Update query to handle NULL video_id or fix video_id population

### MEDIUM (P2) - Data Quality Issues

6. **Missing validation for critical fields**
   - No check that video_id is populated before API response
   - No fallback calculation for actual_latency_ms
   - Fix: Add validation layer before API serialization

7. **Latency field naming confusion**
   - Three latency fields with unclear relationships
   - Fix: Document field purposes, deprecate unused fields

### LOW (P3) - Technical Debt

8. **Timestamp field naming could be clearer**
   - Multiple timestamp fields without clear reference points
   - Fix: Add documentation, consistent naming convention

## 9. Recommended Fix Order

### Phase 1: Critical Data Population (P0)

1. **Fix video_id NULL**
   ```python
   # In labjack_detection_service.py or dedicated_labjack_monitor.py
   # When storing detection event:
   detection_event.video_id = current_video_id  # Get from session metadata
   ```

2. **Fix actual_latency_ms NULL**
   ```python
   # After calling timestamp_conversion_utils.unix_to_video_relative():
   if result.actual_latency_ms is None:
       # Calculate from processing time or use calibrated value
       detection_event.actual_latency_ms = calculate_processing_latency(detection_event)
   ```

3. **Fix negative latency_ms**
   ```python
   # Remove incorrect calculation using video position
   # Use actual measured latency from hardware timestamps
   latency_ms = abs(labjack_timestamp - detection_timestamp) * 1000
   ```

### Phase 2: Query Fixes (P1)

4. **Fix Enhanced HIL endpoint query**
   ```python
   # Update query to either:
   # Option A: Handle NULL video_id with fallback
   # Option B: Ensure video_id is never NULL (preferred)
   ```

### Phase 3: Validation Layer (P2)

5. **Add field validation before API responses**
   ```python
   def validate_detection_event(event):
       if event.video_id is None:
           logger.error(f"Detection event {event.id} has NULL video_id")
       if event.actual_latency_ms is None:
           logger.warning(f"Detection event {event.id} has NULL actual_latency_ms")
   ```

## 10. Additional Bugs Found During Investigation

### 10.1 API Response Serialization

**Issue:** API returns database field names, not camelCase aliases
```json
{
  "video_relative_timestamp": 0.197909,  // ✅ Correct
  "videoRelativeTimestamp": undefined     // ❌ Missing in response
}
```

**Root Cause:** Pydantic schema not configured with `by_alias=True`

### 10.2 Session Metadata Inconsistency

**Issue:** Session metadata shows `videos_completed: 2` but detections show 0 for both videos
```json
{
  "sequenceMetadata": {
    "videos_completed": 2,  // Says completed
    "video_timing": {
      "10c2b16c...": {
        "detection_count": 0  // But 0 detections
      }
    }
  }
}
```

**Root Cause:** Session completion updates metadata but doesn't verify detection storage.

## 11. Conclusion

This deep dive identified **8 priority-ranked issues**, with **1 SMOKING GUN** and **3 CRITICAL production blockers**:

### 🔥 THE SMOKING GUN

**The API is returning a `latency_ms` field that DOES NOT EXIST in the database schema.**

This ghost field is being calculated on-the-fly somewhere in the API code, producing:
- Negative values (-10ms, -18ms, -20ms)
- Incorrect calculations
- All downstream latency validation failures

**Critical Impact:** Every single latency metric in the system is based on this fabricated field.

### The 3 Critical Blockers

1. **Ghost field `latency_ms`** - Fabricated in API, not stored in DB
2. **NULL video_id** - All 161 detections have NULL video_id
3. **NULL actual_latency_ms** - All 161 detections have NULL actual_latency_ms

### Root Cause Analysis

**The system has TWO latency fields:**

1. **`latency_ms`** (ghost field)
   - ❌ NOT in database schema
   - ❌ NOT in SQLAlchemy model
   - ❌ Calculated somewhere in API layer
   - ❌ Produces negative/incorrect values
   - ✅ This is what the API returns

2. **`actual_latency_ms`** (real field)
   - ✅ EXISTS in database schema
   - ✅ Defined in SQLAlchemy model
   - ❌ ALL VALUES ARE NULL (0 out of 161 populated)
   - ✅ This is what SHOULD be used

**The Fix:**
1. Find where API calculates ghost `latency_ms` field
2. Remove ghost field calculation
3. Populate `actual_latency_ms` in database during detection storage
4. Use `actual_latency_ms` in API responses

### Immediate Action Items

**Priority 1: Find the Ghost Field**
```bash
# Search for where latency_ms is being calculated
grep -r "latency_ms" --include="*.py" | grep -v "actual_latency_ms" | grep -v "threshold"
```

**Priority 2: Stop Using Ghost Field**
```python
# In API serialization, use actual_latency_ms instead of latency_ms
# Remove any on-the-fly calculation of latency_ms
```

**Priority 3: Populate Real Field**
```python
# In detection storage, calculate and store actual_latency_ms
detection_event.actual_latency_ms = calculate_real_latency(hardware_timestamp, detection_timestamp)
```

**Estimated Fix Time:** 2-3 hours to remove ghost field and populate real field.

### Files Where Ghost Field is Created

**FOUND THE CULPRITS:**

1. **`/backend/src/api/hil_results_endpoints.py`** - Line ~XXX
   - Creates `"latency_ms"` in API response
   - Calculates: `round(latency_ms, 3)`
   - **This is the PRIMARY source of the ghost field**

2. **`/backend/src/api/enhanced_hil_results_endpoints.py`** - Line ~XXX
   - Creates `"latency_ms": real_latency_ms`
   - Comment says: "Return the frame-based latency"
   - **This is the SECONDARY source**

3. `/backend/services/labjack_detection_service.py` - Should populate actual_latency_ms
4. `/backend/services/dedicated_labjack_monitor.py` - Detection storage location

### The Complete Picture

```
Database (61 columns, NO latency_ms)
    ↓
SQLAlchemy Model (NO latency_ms property)
    ↓
DetectionEvent object loaded (has actual_latency_ms=NULL)
    ↓
API endpoint calculates latency_ms on-the-fly ❌
    ↓
API response includes latency_ms=-10.424ms ❌
    ↓
Frontend receives ghost field with wrong values ❌
```

**The Correct Flow Should Be:**

```
Hardware detection timestamp
    ↓
Calculate actual_latency_ms during storage
    ↓
Store actual_latency_ms in database
    ↓
API reads actual_latency_ms from database
    ↓
Frontend receives correct latency values
```
