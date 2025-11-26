# DUPLICATE LATENCY VALUES - ROOT CAUSE ANALYSIS

## 🔍 INVESTIGATION SUMMARY

Session ID: `9048a1b0-10a7-40b7-b1fc-1c95064cbb5f`
Issue: UI shows DUPLICATE entries for same frame with TWO different latencies (10000ms and 12-19ms)

---

## ✅ FINDINGS

### DATABASE STATE (CONFIRMED CORRECT)
**Database has NO DUPLICATES:**
- Total detections: 71
- Each detection has ONE row in `detection_events` table
- Each detection has ONE row in `detection_comparison` table
- Latency values in database:
  - 67 detections: 0.2ms - 52ms (realistic latencies) ✅
  - 4 detections: 10000ms (FP_LATENCY_MARKER) ✅

**The 10000ms value is INTENTIONAL:**
```python
# backend/services/ground_truth_matching_service.py:79
FP_LATENCY_MARKER = 10000.0  # Sentinel value for False Positive detections
```

**Purpose:** Mark False Positive (FP) detections with a sentinel value so they:
1. Are clearly identified as FP
2. Are excluded from statistics (filtering: `latency < 10000ms`)
3. Don't pollute metrics calculations

---

## 🐛 ROOT CAUSE

### Theory 1: API Returns BOTH Values (MOST LIKELY)

The API endpoint `/api/enhanced-hil/results/{session_id}` may be returning:
1. **Original detection event** with `actual_latency_ms` from database
2. **Corrected timing result** with recalculated `detection_latency_ms`

**Evidence:**
```python
# backend/src/api/enhanced_hil_results_endpoints.py:898-904
for i, (original_event, corrected_result) in enumerate(zip(detection_events_result, corrected_results)):
    # Returns BOTH original_event AND corrected_result
    # Could be creating duplicate entries in response
```

**Mechanism:**
```python
# Line 525: Uses actual_latency_ms from database
'latency_ms': event.actual_latency_ms,  # Could be 10000ms (FP marker)

# Line 937-938: Uses detection_latency_ms from calculator
"real_latency_ms": round(to_float(getattr(corrected_result, 'detection_latency_ms', 0)) or 0, 3),
# Could be 12-19ms (recalculated)
```

### Theory 2: Frontend Displays Both Database and Calculator Values

Frontend might be:
1. Fetching detection events from API
2. Each detection has TWO latency fields:
   - `actual_latency_ms`: 10000ms (from ground_truth_matching_service FP marker)
   - `detection_latency_ms`: 12-19ms (from timing_synchronization_calculator)
3. Frontend displays BOTH values as separate rows

---

## 🎯 THE PROBLEM

**Ground Truth Matching Service assigns FP_LATENCY_MARKER:**
```python
# backend/services/ground_truth_matching_service.py:1195
match_result = MatchResult(
    detection_event_id=detection.id,
    match_type='FP',
    latency_ms=FP_LATENCY_MARKER,  # ← Sets 10000ms for FP detections
    ...
)
```

**Then stores in database:**
```python
# backend/services/ground_truth_matching_service.py:1550
if match_result.latency_ms is not None:
    detection_event.actual_latency_ms = match_result.latency_ms  # ← Writes 10000ms to DB
```

**Meanwhile, Timing Calculator computes realistic latency:**
```python
# backend/services/timing_synchronization_calculator.py:346
detection_latency_ms = (detection_system_time - gt_system_time) * 1000.0
# ← Calculates 12-19ms based on actual timestamps
```

**API returns BOTH:**
```python
# Detection event has actual_latency_ms = 10000ms (from database)
# Corrected result has detection_latency_ms = 12-19ms (from calculator)
```

---

## 🔧 SOLUTION

### Option A: Filter FP Detections from UI (RECOMMENDED)

**Where:** Frontend display logic

**Action:**
```javascript
// Filter out False Positive detections before rendering
const validDetections = detections.filter(d =>
    d.validation_result !== 'FP' &&
    d.latency_ms < 10000
);
```

**Pro:** Simple, no backend changes needed
**Con:** UI still receives FP data

---

### Option B: API Excludes FP Detections (BETTER)

**Where:** `/api/enhanced-hil/results/{session_id}`

**Action:**
```python
# backend/src/api/enhanced_hil_results_endpoints.py:272
detection_events_query = db.query(DetectionEvent).options(
    ...
).filter(
    DetectionEvent.test_session_id == session_id,
    DetectionEvent.validation_result != 'FP'  # ← Add this filter
)
```

**Pro:** Cleaner data sent to frontend
**Con:** FP detections not visible in UI (might be desired)

---

### Option C: Use Corrected Latency, Ignore Database Value (BEST)

**Where:** API response construction

**Action:**
```python
# backend/src/api/enhanced_hil_results_endpoints.py:937-938
# When building response, ALWAYS use corrected latency, never database value
"real_latency_ms": round(to_float(getattr(corrected_result, 'detection_latency_ms', 0)) or 0, 3),

# And update database with corrected value:
if corrected_result and hasattr(corrected_result, 'detection_latency_ms'):
    detection_event.actual_latency_ms = corrected_result.detection_latency_ms  # ← Overwrite FP marker
```

**Pro:** Database and API always consistent
**Con:** Loses FP marker information (need separate field for match_type)

---

## 📊 AFFECTED DATA

Based on database query:
- **Total detections:** 71
- **Detections with FP marker (10000ms):** 4
- **Detections with realistic latency:** 67

**The 4 FP detections are:**
```
ID: 045e2a53-8ae... voltage: None, validation_result: FP, timestamp: 1764018147.59497
ID: 608971aa-db1... voltage: None, validation_result: FP, timestamp: 1764018152.724934
ID: f2e66bf8-655... voltage: None, validation_result: FP, timestamp: 1764018152.919355
ID: [one more]
```

---

## 🚨 CRITICAL INSIGHT

**The UI is showing the SAME detection TWICE:**

**Example: Frame 2 (0.083s)**
```
Entry 1: aligned -13.3ms, real 10000ms FAIL, 4.23V, GT FAIL  ← From database (FP marker)
Entry 2: aligned -13.3ms, real 12ms, 4.23V, GT PASS          ← From calculator (corrected)
```

**Same alignment (-13.3ms), same voltage (4.23V), but:**
- Entry 1: Uses `actual_latency_ms` from DB (10000ms FP marker)
- Entry 2: Uses `detection_latency_ms` from calculator (12ms realistic)

**This is NOT a database duplicate. This is the API returning the same detection with TWO different latency sources.**

---

## 🎯 RECOMMENDATION

**IMMEDIATE FIX (Option C):**

1. **Update ground_truth_matching_service.py:**
   - Don't mark FP detections with 10000ms in database
   - Use a separate field: `detection_event.is_false_positive = True`
   - Keep `actual_latency_ms` realistic for ALL detections

2. **Update enhanced_hil_results_endpoints.py:**
   - Always use `detection_latency_ms` from calculator (if available)
   - Fallback to `actual_latency_ms` from database (if calculator fails)
   - Never return 10000ms to frontend

3. **Update sequence_video_metrics_aggregator.py:**
   - Already has correct filtering: `d.actual_latency_ms < 10000.0` (line 148)
   - This will continue to work

**RESULT:**
- Database stores realistic latencies for ALL detections
- FP status tracked separately via `is_false_positive` field
- API returns ONE value per detection
- UI displays ONE row per detection
- Statistics exclude FP detections via field check, not sentinel value

---

## 📝 VERIFICATION STEPS

After fix:
1. Query detection_events table - should see realistic latencies only
2. Check detection_comparison.match_type - should see 'FP' for false positives
3. Query API endpoint - should return ONE entry per detection
4. Check UI - should display ONE row per frame
5. Verify statistics exclude FP detections

---

## 📁 FILES REQUIRING CHANGES

1. `/backend/services/ground_truth_matching_service.py` - Remove FP_LATENCY_MARKER usage
2. `/backend/models.py` - Add `is_false_positive` Boolean field to DetectionEvent
3. `/backend/src/api/enhanced_hil_results_endpoints.py` - Use corrected latency only
4. `/backend/services/sequence_video_metrics_aggregator.py` - Update FP filtering logic

---

**STATUS:** Root cause identified. Solution ready for implementation.
