# PASS/FAIL CRITERIA INVESTIGATION

## Session: 2c9a93f6-8471-4f2e-b1a7-06f239fca548

**User Report:** "the pass criteria seems to not checking against how many truths there are"

**Current Test Results:**
- F1 Score: 95.4% (Excellent!)
- Precision: 91.2%
- Recall: 100.0% (WRONG - actually 34.3%)
- **TEST RESULT: FAILED**

---

## 1. PASS/FAIL LOGIC LOCATIONS

### Primary Location: `services/ground_truth_matching_service.py`

**Lines 1800-1848:** `_evaluate_detection_accuracy()`
```python
def _evaluate_detection_accuracy(self, metrics: SessionMetrics):
    """Evaluate accuracy based on F1 score thresholds"""
    f1_score = metrics.f1_score

    # Thresholds
    if f1_score >= 0.75:
        accuracy_result = "PASS"
    elif f1_score >= 0.60:
        accuracy_result = "CONDITIONAL_PASS"
    else:
        accuracy_result = "FAIL"
```

**Lines 1951-1957:** Overall verdict determination
```python
# Determine overall result based on both evaluations
if accuracy_result == "PASS" and latency_result == "PASS":
    overall_result = "PASS"
elif accuracy_result == "FAIL" or latency_result == "FAIL":
    overall_result = "FAIL"
else:
    # One or both are CONDITIONAL_PASS
    overall_result = "CONDITIONAL_PASS"
```

### Secondary Location: `services/sequence_video_metrics_aggregator.py`

**Lines 312-318:** Per-video pass/fail logic
```python
# Determine validation result based on pass rate and metrics
if metrics['f1'] >= 0.8 and pass_rate_percent >= 80.0:
    sequence_video_result.validation_result = 'Pass'
elif metrics['total_detections'] == 0:
    sequence_video_result.validation_result = 'Error'
else:
    sequence_video_result.validation_result = 'Fail'
```

---

## 2. CURRENT THRESHOLDS

### Session-Level Thresholds:
- **F1 PASS threshold:** ≥ 0.75 (75%)
- **F1 CONDITIONAL_PASS threshold:** ≥ 0.60 (60%)
- **F1 FAIL threshold:** < 0.60 (60%)

### Per-Video Thresholds:
- **F1 threshold:** ≥ 0.8 (80%)
- **Pass rate threshold:** ≥ 80%
- **Both must be met:** `F1 >= 0.8 AND pass_rate >= 80%`

### Latency Thresholds:
- **PASS:** mean ≤ 100ms AND 95% within tolerance
- **CONDITIONAL_PASS:** mean ≤ 200ms
- **FAIL:** mean > 200ms

---

## 3. EVALUATION LOGIC ANALYSIS

### What is Checked:
1. **Accuracy Evaluation** (F1 score based)
   - ✅ Checks F1 score against 0.75 / 0.60 thresholds
   - ✅ Considers TP, FP, FN in F1 calculation
   - ✅ Logs precision and recall

2. **Latency Evaluation** (for TP detections only)
   - ✅ Checks mean latency
   - ✅ Checks percentage within tolerance

3. **Overall Verdict**
   - ✅ Combines accuracy and latency results
   - ✅ FAIL if either component fails

### What is NOT Checked:
- ❌ **Detection rate** (TP / Total GT events)
- ❌ **False negative count threshold**
- ❌ **Minimum recall threshold**
- ❌ **Per-video pass requirements**

---

## 4. SESSION 2c9a93f6 EVALUATION

### Calculated Metrics:
```
TP: 83
FP: 8
FN: 159
Total GT: 242 (83 + 159)

Precision: 91.2% (83 / 91)
Recall (WRONG): 100.0%
Recall (CORRECT): 34.3% (83 / 242)

F1 Score: 95.4%
```

### Why F1 Score is High Despite Low Detection Rate:

**The F1 Formula:**
```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
F1 = 2 × (0.912 × 1.000) / (0.912 + 1.000)
F1 = 2 × 0.912 / 1.912
F1 = 0.954 (95.4%)
```

**THE PROBLEM:** Recall is being calculated as **100%** when it should be **34.3%**

**Correct F1 Calculation:**
```
Precision: 91.2% (83 / 91)
Recall: 34.3% (83 / 242)

F1 = 2 × (0.912 × 0.343) / (0.912 + 0.343)
F1 = 2 × 0.313 / 1.255
F1 = 0.498 (49.8%)
```

### With Correct F1:
- **F1: 49.8%** < 60% threshold
- **Should FAIL** ✓ (correctly failing)

### Why Test Failed:
- **Per-video validation:** At least one video failed per-video criteria
- **Video-level logic:** Checks both F1 >= 80% AND pass_rate >= 80%
- **Session fails if ANY video fails**

---

## 5. ISSUE IDENTIFIED

### Root Cause: **RECALL CALCULATION BUG**

The recall metric is being calculated **incorrectly** somewhere in the metrics pipeline.

**Expected Behavior:**
```
Recall = TP / (TP + FN)
Recall = 83 / (83 + 159)
Recall = 83 / 242
Recall = 34.3%
```

**Actual Behavior:**
```
Recall = 100.0% (WRONG!)
```

### Possible Causes:

1. **Wrong denominator in recall calculation**
   - Using `TP + FP` instead of `TP + FN`
   - Using `total_detections` instead of `total_ground_truth`

2. **Missing false negatives in calculation**
   - FN count (159) not being included
   - Only counting matched GT events, not total GT

3. **Confusion between metrics**
   - Mixing up precision and recall formulas
   - Using detection count instead of GT count

---

## 6. USER IS CORRECT

**User's Observation:** "pass criteria seems to not checking against how many truths there are"

**User is RIGHT because:**
1. ✅ Recall should check TP against **total ground truth** (242)
2. ✅ Currently showing 100% recall when only 83/242 GT detected
3. ✅ The 159 false negatives are not being properly factored
4. ✅ Pass criteria should fail tests with 34.3% detection rate

**However:**
- ❌ The test DID fail (correctly)
- ❌ But the F1 score of 95.4% is misleading
- ❌ The recall of 100% is incorrect

---

## 7. CORRECT LOGIC SHOULD BE

### Accuracy Evaluation Should Check:
1. **F1 Score** (with correct recall)
   ```
   Recall = TP / (TP + FN)
   F1 = 2 × (Precision × Recall) / (Precision + Recall)
   ```

2. **Minimum Detection Rate** (optional additional check)
   ```
   detection_rate = TP / total_ground_truth
   if detection_rate < 0.60:  # 60% minimum
       return "FAIL"
   ```

3. **Maximum FN Tolerance** (optional additional check)
   ```
   fn_rate = FN / total_ground_truth
   if fn_rate > 0.40:  # Max 40% missed
       return "FAIL"
   ```

### Per-Video Logic Should Use:
```python
# Current (potentially flawed)
if metrics['f1'] >= 0.8 and pass_rate_percent >= 80.0:
    validation_result = 'Pass'

# Should also check detection rate
detection_rate = metrics['tp'] / (metrics['tp'] + metrics['fn'])
if metrics['f1'] >= 0.8 and pass_rate_percent >= 80.0 and detection_rate >= 0.60:
    validation_result = 'Pass'
```

---

## 8. RECOMMENDATION

### Immediate Action:
1. **Fix recall calculation** in metrics pipeline
   - Ensure using `TP / (TP + FN)` formula
   - Verify FN count includes ALL unmatched GT events

2. **Add detection rate check** to pass criteria
   ```python
   detection_rate = tp_count / (tp_count + fn_count)
   if detection_rate < 0.60:  # Must detect at least 60% of GT
       return "FAIL", "Insufficient detection rate"
   ```

3. **Add explicit FN threshold**
   ```python
   if fn_count > (tp_count + fn_count) * 0.40:  # FN > 40% of GT
       return "FAIL", "Too many missed detections"
   ```

### Investigation Needed:
1. **Find where recall is calculated** as 100%
2. **Verify FN counting logic** in matching service
3. **Check if GT events are being missed** in the count
4. **Review SessionMetrics calculation** in `_calculate_session_metrics()`

### Files to Check:
- `/home/rigade/Testing/ai-model-validation-platform/backend/services/ground_truth_matching_service.py`
  - Line ~2050: `_calculate_session_metrics()`
  - Recall calculation logic

- `/home/rigade/Testing/ai-model-validation-platform/backend/services/sequence_video_metrics_aggregator.py`
  - Line ~150-200: Metrics calculation from DetectionEvent table

---

## 9. SUMMARY

### Pass/Fail Criteria Investigation Results:

**Location of Pass Logic:**
- File: `services/ground_truth_matching_service.py`
- Function: `_evaluate_detection_accuracy()` (lines 1800-1848)
- Lines: 1951-1957 (overall verdict)

**Current Thresholds:**
- Session F1 threshold: 75% (PASS) / 60% (CONDITIONAL)
- Per-video F1: 80%
- Per-video pass rate: 80%
- Uses aggregated metrics: YES
- Uses per-video: YES (both must pass)

**Evaluation Logic:**
- Checks: F1 score, latency metrics, per-video results
- Formula: Dual evaluation (accuracy + latency)
- Uses per-video: YES
- Uses aggregated: YES

**Session 2c9a93f6 Evaluation:**
- F1: 95.4% (should be 49.8% with correct recall)
- Should pass by F1: NO (with correct calculation)
- Why it failed: Per-video criteria not met

**Issue Identified:**
- **Problem:** Recall calculated as 100% instead of 34.3%
- **User is right:** YES - pass criteria not checking GT count correctly
- **Location:** Recall calculation in metrics pipeline
- **Impact:** F1 score inflated, but test still fails on per-video criteria

**Correct Logic Should Be:**
- Fix recall: `TP / (TP + FN)` not `TP / total_detections`
- Add detection rate check: `TP / total_GT >= 60%`
- Add FN threshold: `FN / total_GT <= 40%`
- Ensure per-video and session-level consistency

**Recommendation:**
1. Fix recall calculation bug immediately
2. Add explicit detection rate threshold
3. Add FN count threshold
4. Verify GT event counting logic
5. Update per-video pass criteria to include detection rate
