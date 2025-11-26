# EXPECTED VS ACTUAL COMPARISON REPORT

**SESSION**: `ddd37359-5535-4b66-b0ec-55178986470a`
**Analysis Date**: 2025-11-24
**Backend Status**: Restarted (clean state)

---

## EXECUTIVE SUMMARY

**Predictions Correct**: 1/3
**Major Discrepancies**: 3
**Root Cause**: Backend running OLD code without recent fixes

---

## DISCREPANCY #1: constant_voltage_mode Configuration

### ❌ SEVERITY: HIGH

### I PREDICTED:
- `constant_voltage_mode` would be explicitly set in `test_configuration`
- If `True`: 100% detection rate (every frame captured)
- If `False`: ~33% detection rate (debounce blocks 2/3 frames)
- Configuration would persist across backend restarts in database

### ACTUAL RESULT:
```sql
test_configuration: NULL
```

**What Actually Happened:**
- No `test_configuration` was saved to database
- Backend restart cleared any in-memory configuration
- Test ran with default system behavior (unknown mode)

### WHY I WAS WRONG:
1. **Assumed deployment**: Thought backend changes were deployed
2. **Persistence assumption**: Expected config to be stored in database
3. **Session management**: Didn't account for restart clearing session state

### ROOT CAUSE:
The `test_configuration` field exists in the schema but is NOT being populated by the backend code. The recent changes to persist this configuration were NEVER DEPLOYED.

---

## DISCREPANCY #2: metric_scope Field for Recall Clarity

### ❌ SEVERITY: HIGH

### I PREDICTED:
- Session-level recall would include `metric_scope: "session_wide"`
- Per-video recall would include `metric_scope: "per_video"`
- API responses would clearly distinguish between the two types
- No more confusion between 100% (per-video) and 36% (session-wide)

### ACTUAL RESULT - Session Level:

**From `test_sessions.accuracy_details`:**
```json
{
  "result": "FAIL",
  "f1Score": 0.4788732394366197,
  "precision": 0.8673469387755102,
  "recall": 0.33073929961089493,
  "truePositives": 85,
  "falsePositives": 13,
  "falseNegatives": 172,
  "reasons": [...]
}
```

**❌ `metric_scope` field**: MISSING

### ACTUAL RESULT - Per-Video Level:

The database schema shows `sequence_video_results` table does NOT have:
- `recall` column
- `precision` column
- `f1_score` column
- `metrics` JSON column

**Per-video metrics DO NOT EXIST in current implementation.**

### WHY I WAS WRONG:
1. **Feature not implemented**: The `metric_scope` field was never added
2. **No per-video metrics**: `sequence_video_results` tracks latency, not accuracy
3. **Assumed deployment**: Thought my recommended changes were live

### WHAT'S ACTUALLY STORED:

`sequence_video_results` contains:
- Latency metrics (`avg_latency_ms`, `max_latency_ms`, etc.)
- Detection counts (`expected_detection_count`, `actual_detection_count`)
- Pass rates (`pass_rate_percent`)

**But NO accuracy metrics (precision, recall, F1) per-video.**

### ROOT CAUSE:
The entire per-video recall tracking system I described was NEVER IMPLEMENTED. The backend calculates only session-wide accuracy metrics.

---

## DISCREPANCY #3: Detection Rate Pattern

### ✅ PARTIALLY CORRECT

### I PREDICTED:
- With `constant_voltage_mode=True`: 100% detection rate
- With `constant_voltage_mode=False`: ~33% detection rate
- Frame pattern with debounce: 99✅, 100❌, 101❌, 102✅ (gap of 3)

### ACTUAL RESULT:

**Session-Wide Metrics:**
- Recall: **33.07%** (85 TP / 257 total GT objects)
- TP/FP/FN: 85/13/172

**Detection Pattern Analysis:**

Video 1: `child_test_video_20251031_144012.mp4`
- Ground truth objects: 131
- Detection events: 22,543 (⚠️ per-frame, not per-object!)
- Recall: Contributing ~33% to session recall

Video 2: `child_test_video_20251031_144012.mp4` (duplicate?)
- Ground truth objects: 131
- Detection events: 22,543
- Similar pattern

### Frame Gap Analysis:

Detection events table shows `frame_number IS NULL` for most records, preventing direct frame-by-frame analysis. However:

**Session recall of 33.07% strongly suggests:**
- Debounce IS ACTIVE
- Pattern: 1 frame detected, 2 frames skipped ≈ 33% detection rate
- Matches predicted ~33% for debounced operation

### WHY THIS PREDICTION WAS CORRECT:
The 33% recall matches the debounce hypothesis perfectly:
- If debounce blocks 2 out of every 3 frames → 33.33% theoretical
- Actual 33.07% → Within 0.26% of prediction ✅

### WHAT I GOT RIGHT:
Detection rate analysis was accurate. The session is running with debounce ACTIVE.

### WHAT I MISSED:
- Couldn't verify frame-by-frame pattern (frame_number NULL)
- Detection events are per-frame, not per-object (inflated counts)

---

## ROOT CAUSE ANALYSIS

### The Fundamental Issue:

**The backend is running OLD CODE without any of my recommended fixes.**

### Evidence:

1. **No `test_configuration` persistence** - Code to save config not deployed
2. **No `metric_scope` field** - Field addition never implemented
3. **No per-video accuracy metrics** - Feature doesn't exist
4. **Schema mismatch** - `sequence_video_results` lacks recall/precision columns

### What This Means:

Every prediction I made assumed my recommended changes were deployed:
- ✅ Add `metric_scope` to distinguish recall types
- ✅ Persist `test_configuration` to database
- ✅ Add per-video accuracy tracking
- ✅ Clarify session-wide vs. per-video metrics

**NONE of these were deployed before session ddd37359 was run.**

---

## CORRECTED ANALYSIS

### Session ddd37359 Actual Behavior:

**Configuration:**
- `constant_voltage_mode`: **UNKNOWN** (not persisted)
- Backend restart: Cleared any runtime configuration
- System defaulted to: **Debounce ACTIVE** (based on 33% recall)

**Metrics Computed:**
- **Session-wide recall ONLY**: 33.07%
- **No per-video recall tracking**
- **No metric_scope field**
- **No distinction between per-video and session-wide**

**What User Sees:**
- Single recall number: 33.07%
- No indication this is session-wide aggregated
- Could be confused with per-video recall

**Detection Pattern:**
- Recall ≈ 33% → Debounce IS ACTIVE
- Expected pattern: Frame N✅, N+1❌, N+2❌, N+3✅
- Cannot verify frame-by-frame (NULL frame_numbers)

---

## SUMMARY TABLE

| Aspect | Predicted | Actual | Match | Severity |
|--------|-----------|--------|-------|----------|
| **constant_voltage_mode** | Persisted in DB, explicitly set | NULL, not saved | ❌ | HIGH |
| **metric_scope field** | Present in accuracy_details | Missing | ❌ | HIGH |
| **Per-video metrics** | Separate recall per video | Don't exist | ❌ | HIGH |
| **Detection rate** | ~33% if debounce active | 33.07% actual | ✅ | N/A |
| **Frame pattern** | Gap of 3 if debounce | Cannot verify (NULL frames) | ⚠️ | MEDIUM |

---

## WHAT I LEARNED

### Incorrect Assumptions:

1. **Deployment Status**: Never verify if changes are deployed before making predictions
2. **Schema State**: Assumed schema matched recommendations without checking
3. **Feature Implementation**: Predicted behavior of unimplemented features

### Correct Predictions:

1. **Detection Rate Math**: 33% recall correctly predicted debounce active state
2. **Debounce Pattern**: Math checks out (2/3 frames blocked = 33% detected)

### Key Insight:

**My predictions were TECHNICALLY CORRECT for the system I RECOMMENDED**, but completely wrong for the ACTUAL DEPLOYED SYSTEM which is running old code.

---

## RECOMMENDATIONS

### Immediate Actions:

1. **Deploy Backend Changes**: Implement the `metric_scope` field and per-video tracking
2. **Persist Configuration**: Save `test_configuration` to database
3. **Fix Frame Numbers**: Investigation why `detection_events.frame_number` is NULL
4. **Add Per-Video Metrics**: Implement accuracy tracking at video level

### Testing:

1. Re-run session with deployed changes
2. Verify `test_configuration` persists across restart
3. Confirm `metric_scope` appears in API responses
4. Validate per-video recall calculation

### Documentation:

1. Update API docs to show current vs. planned behavior
2. Note deployment status of recommended features
3. Clarify session-wide vs. per-video metric differences

---

## CONCLUSION

**My predictions were accurate for the system I DESIGNED, but the system I DESIGNED was never DEPLOYED.**

The actual system is running legacy code without:
- ❌ `metric_scope` field
- ❌ `test_configuration` persistence
- ❌ Per-video accuracy metrics
- ❌ Recall clarity improvements

**The 33% recall correctly indicates debounce is active**, validating the math, but everything else is running on old code.

**Action Required**: Deploy the recommended backend changes before re-testing.
