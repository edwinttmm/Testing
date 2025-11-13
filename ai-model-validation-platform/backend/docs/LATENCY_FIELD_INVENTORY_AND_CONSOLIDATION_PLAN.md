# LATENCY FIELD INVENTORY AND CONSOLIDATION PLAN
## Complete Audit of All Latency Calculation Paths

**Generated:** 2025-01-05
**Agent:** Code Review Agent 5
**Critical Bug:** Multiple contradictory latency fields with different meanings

---

## EXECUTIVE SUMMARY

**CRITICAL FINDING:** The codebase contains **7 different latency field names** with overlapping/contradictory meanings, calculated in **5 different locations**, stored in **3 different places** (DB columns, JSON metadata, API responses).

**Impact:** This causes:
- Frontend displays wrong latency values (uses wrong field)
- API returns multiple conflicting latency values in same response
- Database stores redundant/contradictory data
- Impossible to determine "ground truth" latency value

---

## COMPLETE LATENCY FIELD INVENTORY

### 1. DATABASE MODEL FIELDS (models.py - DetectionEvent)

#### 1.1 `actual_latency_ms` (Line 311)
```python
actual_latency_ms = Column(Float, nullable=True, index=True)
```
- **Location:** DetectionEvent model column
- **Meaning:** "Actual measured latency from video start (milliseconds)"
- **Calculation:** Set in multiple places:
  - `labjack_detection_service.py` line 698: Uses video position as latency (WRONG!)
  - `timestamp_conversion_utils.py` line 102: FIXED to NULL (correct - not a timestamp conversion concern)
  - `enhanced_hil_results_endpoints.py` line 739: Uses corrected `real_latency_ms` from calculator
- **Status:** **PRIMARY FIELD** but inconsistently populated

#### 1.2 `latency_ns` (Line 289)
```python
latency_ns = Column(String, nullable=True)
```
- **Location:** DetectionEvent model column
- **Meaning:** "Nanosecond precision latency (stored as string for precision)"
- **Calculation:** NOT FOUND in codebase (never populated!)
- **Status:** **UNUSED FIELD** - Should be removed or populated

#### 1.3 `t3_processing_time_ms` (Line 334)
```python
t3_processing_time_ms = Column(Float, nullable=True)
```
- **Location:** DetectionEvent model column
- **Meaning:** "T3: YOLO inference processing time"
- **Calculation:** Phase 2 T3 YOLO pipeline (not yet implemented)
- **Status:** **FUTURE FIELD** - T3 detection pipeline only

#### 1.4 `processing_time_ms` (Line 371)
```python
processing_time_ms = Column(Float, nullable=True)
```
- **Location:** DetectionEvent model column
- **Meaning:** "Time taken for detection (generic processing time)"
- **Calculation:** Detection pipeline metadata
- **Status:** **SYSTEM OVERHEAD** field - NOT camera latency

#### 1.5 `latency_threshold_ms` (Line 297)
```python
latency_threshold_ms = Column(Float, nullable=True)
```
- **Location:** DetectionEvent model column
- **Meaning:** "Threshold used for validation (pass/fail criteria)"
- **Calculation:** Copied from TestSession.tolerance_ms
- **Status:** **THRESHOLD VALUE** - Not actual latency

---

### 2. TIMING CALCULATOR FIELDS (timing_synchronization_calculator.py)

#### 2.1 `real_latency_ms` (TimingSynchronizationResult Line 64)
```python
real_latency_ms: float  # Corrected calculation
```
- **Location:** TimingSynchronizationCalculator output
- **Meaning:** "Corrected latency accounting for video startup delay"
- **Calculation:** Line 281
  ```python
  real_latency_ms = (detection_system_time - gt_system_time) * 1000.0
  ```
- **Formula:** `detection_time - (video_start + gt_video_time)`
- **Status:** **CANONICAL LATENCY** - This is the correct value

#### 2.2 `apparent_latency_ms` (TimingSynchronizationResult Line 63)
```python
apparent_latency_ms: float  # Old incorrect calculation
```
- **Location:** TimingSynchronizationCalculator output
- **Meaning:** "Original latency (includes video startup delay - WRONG)"
- **Calculation:** Line 274
  ```python
  apparent_latency_ms = (detection_system_time - labjack_start_time) * 1000.0
  ```
- **Formula:** `detection_time - video_start_time`
- **Status:** **DEPRECATED** - Shows timing bug, not real latency

#### 2.3 `latency_correction_ms` (TimingSynchronizationResult Line 65)
```python
latency_correction_ms: float  # Difference between apparent and real
```
- **Location:** TimingSynchronizationCalculator output
- **Meaning:** "Amount of correction applied (video startup delay offset)"
- **Calculation:** Line 285-290 (dynamic calculation)
- **Status:** **METADATA** - Explains difference, not actual latency

#### 2.4 `camera_only_latency_ms` (TimingSynchronizationResult Line 77)
```python
camera_only_latency_ms: float = 0.0  # Pure camera response time
```
- **Location:** TimingSynchronizationCalculator output (latency decomposition)
- **Meaning:** "Isolated camera latency (real_latency - system_overhead)"
- **Calculation:** Line 354 (from decomposition service)
  ```python
  camera_latency_ms = decomposition.camera_latency_ms
  ```
- **Status:** **DECOMPOSED COMPONENT** - Part of real_latency_ms

#### 2.5 `system_overhead_ms` (TimingSynchronizationResult Line 78)
```python
system_overhead_ms: float = 0.0  # System/hardware overhead
```
- **Location:** TimingSynchronizationCalculator output
- **Meaning:** "System processing overhead (NOT camera latency)"
- **Calculation:** Line 355 (from decomposition service)
- **Status:** **DECOMPOSED COMPONENT** - Part of real_latency_ms

---

### 3. API RESPONSE FIELDS (enhanced_hil_results_endpoints.py)

#### 3.1 API Response: `latency_ms` (Line 469)
```python
'latency_ms': event.actual_latency_ms  # Uses labjack_timestamp internally
```
- **Location:** Detection events summary in API response
- **Meaning:** Alias for `actual_latency_ms`
- **Status:** **ALIAS FIELD** - Duplicate of actual_latency_ms

#### 3.2 API Response: `processing_time_ms` (Line 470)
```python
'processing_time_ms': event.processing_time_ms
```
- **Location:** Detection events summary
- **Meaning:** System processing time (NOT latency)
- **Status:** **SYSTEM METRIC** - Separate from latency

#### 3.3 API Response: Multiple Latency Fields in Same Object (Lines 865-923)
```python
# CONTRADICTION: Same detection event has 3 different "latency" values!
"original_latency": {
    "apparent_latency_ms": round(to_float(getattr(corrected_result, 'apparent_latency_ms', 0)) or 0, 3),
},
"corrected_latency": {
    "real_latency_ms": round(to_float(getattr(corrected_result, 'real_latency_ms', 0)) or 0, 3),
},
"measured_breakdown": {
    "camera_processing_ms": round(to_float(getattr(corrected_result, 'camera_only_latency_ms', 0)), 1),
    "system_processing_ms": round(to_float(getattr(corrected_result, 'system_overhead_ms', 0)), 1),
}
```
- **Status:** **CONTRADICTION** - Frontend receives conflicting values

---

### 4. WEBSOCKET EMISSION FIELDS (labjack_detection_service.py)

#### 4.1 WebSocket: `actual_latency_ms` (Line 858)
```python
detection_data = {
    'actual_latency_ms': event.actual_latency_ms,
    'metadata': event.metadata
}
```
- **Location:** Real-time WebSocket emission
- **Status:** Uses database field directly

---

## CONFLICT ANALYSIS

### Conflict 1: actual_latency_ms vs real_latency_ms
**Problem:** Two fields with nearly identical names but different values
- `actual_latency_ms` (DB field): Sometimes wrong (uses video position as latency)
- `real_latency_ms` (calculator output): Correct (uses timing calculator)

**Root Cause:** `actual_latency_ms` populated before timing correction in some code paths

**Evidence:**
```python
# labjack_detection_service.py line 698 (WRONG!)
actual_latency_ms = (video_relative_timestamp * 1000) + SYSTEM_LATENCY_MS

# vs

# timing_synchronization_calculator.py line 281 (CORRECT!)
real_latency_ms = (detection_system_time - gt_system_time) * 1000.0
```

---

### Conflict 2: processing_time_ms Overloaded Meaning
**Problem:** Used for TWO different things:
1. System processing overhead (LabJack to storage time)
2. YOLO inference time (t3_processing_time_ms)

**Root Cause:** Generic field name used for multiple purposes

**Evidence:**
- Line 371 (models.py): Generic processing time
- Line 334 (models.py): T3 YOLO-specific processing time
- Used inconsistently across codebase (50 occurrences found)

---

### Conflict 3: Multiple Latency Values in API Response
**Problem:** Frontend receives 3-4 different latency values for SAME detection
- `apparent_latency_ms`: 5000ms (includes startup delay)
- `real_latency_ms`: 75ms (corrected)
- `camera_only_latency_ms`: 25ms (decomposed)
- `latency_ms`: Could be any of the above!

**Root Cause:** No clear "primary" field designation in API contract

**Evidence:** Lines 865-923 in enhanced_hil_results_endpoints.py

---

### Conflict 4: Timestamp Conversion Creates Latency
**Problem:** `timestamp_conversion_utils.py` originally calculated latency during timestamp conversion

**Root Cause:** Line 98 (NOW FIXED to NULL)
```python
# ❌ REMOVED: actual_latency_ms = video_relative_timestamp * 1000
# (was completely wrong - used video position as latency!)
actual_latency_ms = None  # Caller must provide actual measured latency
```

**Status:** PARTIALLY FIXED but shows historical confusion about responsibilities

---

## CONSOLIDATION PLAN

### RECOMMENDED CANONICAL FIELD: `real_latency_ms`

**Rationale:**
1. Most accurate calculation (from timing_synchronization_calculator)
2. Accounts for video startup delay
3. Matches actual camera response time
4. Already used by corrected HIL results endpoint

---

### PHASE 1: DATABASE SCHEMA CHANGES

#### Step 1.1: Rename Primary Latency Field
```sql
-- Rename to clarify this is the canonical latency value
ALTER TABLE detection_events RENAME COLUMN actual_latency_ms TO real_latency_ms;

-- Add index for performance
CREATE INDEX idx_detection_real_latency ON detection_events(real_latency_ms);
```

#### Step 1.2: Add Explicit Deprecated Fields (Backward Compatibility)
```sql
-- Keep old field as computed column for backward compatibility (optional)
ALTER TABLE detection_events ADD COLUMN actual_latency_ms FLOAT GENERATED ALWAYS AS (real_latency_ms) STORED;
```

#### Step 1.3: Remove Unused Field
```sql
-- latency_ns never populated
ALTER TABLE detection_events DROP COLUMN latency_ns;
```

#### Step 1.4: Clarify System Overhead Field
```sql
-- Rename to make purpose clear
ALTER TABLE detection_events RENAME COLUMN processing_time_ms TO system_overhead_ms;
```

---

### PHASE 2: CODE CHANGES

#### Step 2.1: Update DetectionEvent Model (models.py)
```python
# PRIMARY LATENCY FIELD (Line 311)
real_latency_ms = Column(Float, nullable=True, index=True,
    comment="Actual measured camera latency from ground truth event (milliseconds)")

# DEPRECATED - For backward compatibility only
@property
def actual_latency_ms(self):
    """Deprecated: Use real_latency_ms instead"""
    return self.real_latency_ms

# SYSTEM OVERHEAD - NOT CAMERA LATENCY
system_overhead_ms = Column(Float, nullable=True,
    comment="System processing overhead (LabJack + backend) - NOT camera latency")

# T3 DETECTION PIPELINE ONLY
t3_processing_time_ms = Column(Float, nullable=True,
    comment="T3 YOLO inference processing time (Phase 2 only)")
```

#### Step 2.2: Update Timing Calculator (timing_synchronization_calculator.py)
**NO CHANGES NEEDED** - Already uses `real_latency_ms` as canonical field

#### Step 2.3: Update LabJack Detection Service (labjack_detection_service.py)
```python
# Line 698 - Fix calculation
# ❌ OLD (WRONG):
actual_latency_ms = (video_relative_timestamp * 1000) + SYSTEM_LATENCY_MS

# ✅ NEW (CORRECT):
real_latency_ms = None  # Will be calculated by timing_synchronization_calculator

# Store system overhead separately
system_overhead_ms = SYSTEM_LATENCY_MS  # 50ms typical
```

#### Step 2.4: Update Timestamp Conversion (timestamp_conversion_utils.py)
**ALREADY FIXED** (Line 102) - Returns NULL for latency

---

### PHASE 3: API CONTRACT CHANGES

#### Step 3.1: Enhanced HIL Results API Response
```python
# Return ONLY canonical latency field
"detection_events": [
    {
        "event_id": "...",
        "real_latency_ms": 75.0,  # ✅ PRIMARY FIELD

        # Breakdown (optional, for analysis)
        "latency_breakdown": {
            "camera_latency_ms": 25.0,      # Isolated camera response
            "system_overhead_ms": 50.0,      # Hardware/backend processing
            "total_latency_ms": 75.0         # Sum = real_latency_ms
        },

        # Historical/debug fields (deprecated)
        "timing_analysis": {
            "apparent_latency_ms": 5075.0,       # Old calculation (includes startup delay)
            "latency_correction_ms": 5000.0,     # Amount of correction applied
            "corrected_to_real": true
        }
    }
]
```

#### Step 3.2: WebSocket Emission
```python
# Update field name
detection_data = {
    'real_latency_ms': event.real_latency_ms,  # ✅ Use canonical field
    'system_overhead_ms': event.system_overhead_ms,
    'timing_quality': event.timing_sync_quality
}
```

---

### PHASE 4: FRONTEND CHANGES

#### Step 4.1: Update TypeScript Interfaces
```typescript
interface DetectionEvent {
    id: string;
    real_latency_ms: number;  // ✅ PRIMARY FIELD - Use this for all displays

    // Backward compatibility (deprecated)
    /** @deprecated Use real_latency_ms instead */
    actual_latency_ms?: number;

    // Optional breakdown
    latency_breakdown?: {
        camera_latency_ms: number;
        system_overhead_ms: number;
    };
}
```

#### Step 4.2: Update All Latency Displays
```typescript
// ❌ OLD (WRONG - might use wrong field)
const latency = detection.actual_latency_ms || detection.latency_ms;

// ✅ NEW (CORRECT - always use canonical field)
const latency = detection.real_latency_ms;
```

---

## MIGRATION STRATEGY

### Database Migration Script
```python
def upgrade():
    # Step 1: Add new column
    op.add_column('detection_events',
        sa.Column('real_latency_ms', sa.Float(), nullable=True, index=True))

    # Step 2: Copy data from old column
    op.execute("""
        UPDATE detection_events
        SET real_latency_ms = actual_latency_ms
        WHERE actual_latency_ms IS NOT NULL
    """)

    # Step 3: Drop unused column
    op.drop_column('detection_events', 'latency_ns')

    # Step 4: Rename system overhead column
    op.alter_column('detection_events', 'processing_time_ms',
        new_column_name='system_overhead_ms')

    # Step 5: Add backward compatibility property (handled in model)

def downgrade():
    # Reverse all changes
    op.alter_column('detection_events', 'system_overhead_ms',
        new_column_name='processing_time_ms')
    op.add_column('detection_events',
        sa.Column('latency_ns', sa.String(), nullable=True))
    op.drop_column('detection_events', 'real_latency_ms')
```

---

## TESTING PLAN

### Test 1: Verify Single Source of Truth
```python
def test_canonical_latency_field():
    """Verify all code paths use real_latency_ms"""
    detection = DetectionEvent(...)

    # Should be same value everywhere
    assert detection.real_latency_ms == 75.0
    assert detection.actual_latency_ms == 75.0  # Backward compat

    # API response should only contain canonical field
    api_response = get_detection_event_api(detection.id)
    assert 'real_latency_ms' in api_response
    assert api_response['real_latency_ms'] == 75.0
```

### Test 2: Verify No Contradictions
```python
def test_no_contradictory_latency_values():
    """Ensure API doesn't return conflicting latency values"""
    response = get_enhanced_hil_results(session_id)

    for event in response['detection_events']:
        # If breakdown provided, should sum to real_latency
        if 'latency_breakdown' in event:
            breakdown = event['latency_breakdown']
            calculated = (breakdown['camera_latency_ms'] +
                         breakdown['system_overhead_ms'])
            assert abs(calculated - event['real_latency_ms']) < 1.0
```

### Test 3: Verify Timing Calculator Integration
```python
def test_timing_calculator_populates_canonical_field():
    """Timing calculator should set real_latency_ms"""
    result = timing_calculator.calculate_corrected_latency(...)

    assert hasattr(result, 'real_latency_ms')
    assert result.real_latency_ms > 0
    assert result.real_latency_ms < 500  # Reasonable range
```

---

## ROLLOUT PLAN

### Stage 1: Backend Database Changes (Week 1)
- [ ] Run database migration
- [ ] Verify data copied correctly
- [ ] Update DetectionEvent model
- [ ] Deploy to staging

### Stage 2: Backend API Changes (Week 2)
- [ ] Update timing calculator integration
- [ ] Update LabJack detection service
- [ ] Update API responses
- [ ] Deploy to staging
- [ ] Run integration tests

### Stage 3: Frontend Changes (Week 3)
- [ ] Update TypeScript interfaces
- [ ] Update all latency displays
- [ ] Test with staging API
- [ ] Deploy to production

### Stage 4: Cleanup (Week 4)
- [ ] Remove deprecated fields (if no breaking changes)
- [ ] Update documentation
- [ ] Archive old API versions

---

## RISKS AND MITIGATION

### Risk 1: Breaking Changes for Frontend
**Mitigation:** Keep backward compatibility property `actual_latency_ms` as alias

### Risk 2: Data Loss During Migration
**Mitigation:** Copy data to new column before dropping old column

### Risk 3: Existing Integrations Break
**Mitigation:** Version API endpoints, maintain old format for 3 months

---

## CONCLUSION

**Current State:** 7 latency fields, 5 calculation paths, 3 storage locations = CHAOS

**Target State:** 1 canonical field (`real_latency_ms`), 1 calculation path (timing_synchronization_calculator), 1 storage location (database)

**Benefits:**
- ✅ No more contradictory latency values
- ✅ Clear "single source of truth"
- ✅ Frontend displays correct values
- ✅ Easier debugging and maintenance
- ✅ Accurate latency measurements

**Recommended Canonical Field:** `real_latency_ms`
**Recommended Removal:** `latency_ns`, `apparent_latency_ms` (API only), `latency_ms` (alias)
**Recommended Rename:** `processing_time_ms` → `system_overhead_ms`
**Recommended Deprecation:** `actual_latency_ms` (keep as property for backward compat)
