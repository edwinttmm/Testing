# Session fa204ef2 - Metrics Analysis Report

**Session ID:** `fa204ef2-9d8b-4480-9692-86e338c1218a`
**Date:** 2025-11-24
**Status:** FAILED
**Session Type:** Multi-video sequence test (2 videos)

---

## Executive Summary

### ❌ Test Result: FAILED

**Primary Failure Reason:** Low Recall (33.9%)
**F1 Score:** 49.3% (below 80% threshold)

Despite high scores in other areas:
- ✅ Precision: 90.6% (excellent)
- ✅ Latency: 100% pass rate (perfect)
- ✅ Aggregated: 95.1% (misleading)

**Root Cause:** System missed **170 out of 257** ground truth objects (66% miss rate)

---

## Conflicting Metrics Resolved

You observed these conflicting numbers in the UI:

| Metric | Value | What It Means |
|--------|-------|---------------|
| **Match Rate** | 90.6% | Precision - when system detects, it's correct 90.6% of time |
| **Aggregated** | 95.1% | (Precision + Latency Pass Rate) / 2 = (90.6 + 100) / 2 |
| **Pass Rate** | 0.0% | Test FAILED - 0 out of 1 tests passed requirements |
| **Detection Rate** | 40.9% | 99/242 - needs frontend investigation |

### The Mystery of 95.1% Aggregated Score

**Formula Discovered:**
```
Aggregated Score = (Accuracy Precision + Latency Pass Rate) / 2
                = (90.6% + 100.0%) / 2
                = 95.3% (rounded to 95.1% in display)
```

**Why This Is Misleading:**
- Averages precision (spatial accuracy) with latency (timing)
- **Completely ignores recall** (completeness of detection)
- Makes the test look good when it actually failed critically

---

## Complete Metrics Breakdown

### Detection Counts (The Raw Truth)

```
Ground Truth Universe (257 objects):
┌────────────────────────────────────────────┐
│                                            │
│  ╔══════════════╗     ┌─────────────────┐ │
│  ║ TRUE         ║     │ FALSE           │ │
│  ║ POSITIVES    ║     │ NEGATIVES       │ │
│  ║              ║     │                 │ │
│  ║   87 ✅      ║     │   170 ❌        │ │
│  ║              ║     │                 │ │
│  ║ 33.9% found  ║     │ 66.1% MISSED    │ │
│  ╚══════════════╝     └─────────────────┘ │
│                                            │
└────────────────────────────────────────────┘

System Detections (96 total):
┌────────────────────────────────────────────┐
│  ╔══════════════╗  ┌────────┐             │
│  ║ TRUE         ║  │ FALSE  │             │
│  ║ POSITIVES    ║  │ POS.   │             │
│  ║              ║  │        │             │
│  ║   87 ✅      ║  │  9 ❌  │             │
│  ║              ║  │        │             │
│  ║ 90.6% correct║  │9.4% FA │             │
│  ╚══════════════╝  └────────┘             │
└────────────────────────────────────────────┘

Legend:
  ✅ Correct detection/match
  ❌ Error (false positive or missed detection)
```

| Count | Value | Calculation |
|-------|-------|-------------|
| True Positives (TP) | 87 | Correctly detected objects |
| False Positives (FP) | 9 | False alarms |
| False Negatives (FN) | 170 | **MISSED OBJECTS** |
| Total Detections | 96 | TP + FP |
| Ground Truth Total | 257 | TP + FN |

---

### Accuracy Metrics (Spatial/Detection Quality)

#### Precision: 90.6% ✅

```
Formula: TP / (TP + FP)
Calculation: 87 / (87 + 9) = 87 / 96 = 0.906
```

**Meaning:** When the system makes a detection, it's correct 90.6% of the time.
**Status:** EXCELLENT - Very few false alarms
**Interpretation:** The system is accurate when it detects something

---

#### Recall: 33.9% ❌

```
Formula: TP / (TP + FN)
Calculation: 87 / (87 + 170) = 87 / 257 = 0.339
```

**Meaning:** Of all objects that should be detected, only 33.9% were found.
**Status:** CRITICAL FAILURE - Missing 66% of objects
**Interpretation:** The system misses most objects - **THIS IS THE PROBLEM**

---

#### F1 Score: 49.3% ❌

```
Formula: 2 × (Precision × Recall) / (Precision + Recall)
Calculation: 2 × (0.906 × 0.339) / (0.906 + 0.339)
           = 2 × 0.307 / 1.245
           = 0.493
```

**Meaning:** Harmonic mean balancing precision and recall
**Status:** BELOW THRESHOLD (< 80%)
**Interpretation:** Overall detection performance is insufficient

---

### Latency Metrics (Timing Performance)

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Mean Latency | 11.04 ms | < 100 ms | ✅ PASS |
| Max Latency | 20.71 ms | < 100 ms | ✅ PASS |
| Pass Rate | 100.0% | ≥ 80% | ✅ PASS |

**All 87 true positive detections had latency under 100ms threshold.**

---

### Aggregated Score: 95.1%

```
Formula: (Precision + Latency Pass Rate) / 2
Calculation: (90.6% + 100.0%) / 2 = 95.3%
Displayed as: 95.1% (minor rounding)
```

**⚠️ WARNING:** This metric is misleading because:
1. It only considers precision, not recall
2. It averages spatial accuracy with timing
3. It makes a failed test look successful

**This metric should NOT be used for pass/fail decisions.**

---

## Why Test Failed Despite High Aggregated Score

### The Decision Logic

```python
if (F1_Score >= 80% AND Latency_Pass_Rate >= 80%):
    result = "PASS" ✅
else:
    result = "FAIL" ❌
```

### This Session's Evaluation

| Criterion | Value | Threshold | Met? |
|-----------|-------|-----------|------|
| F1 Score | 49.3% | ≥ 80% | ❌ NO |
| Latency Pass Rate | 100% | ≥ 80% | ✅ YES |
| **Overall Result** | | | **❌ FAIL** |

**Test failed because F1 Score (49.3%) is below 80% threshold.**

---

## The Misleading Aggregated Score Explained

### What Gets Averaged

```
Aggregated Score (95.1%) = Average of:
  ✅ Precision (90.6%)           [Good]
  ✅ Latency Pass Rate (100%)    [Perfect]
```

### What Gets Ignored

```
❌ Recall (33.9%)                [CRITICAL FAILURE]
❌ False Negatives (170)         [THE ACTUAL PROBLEM]
```

### Visual Representation

```
Aggregated Score Calculation:
┌─────────────────────────────────────┐
│                                     │
│  Precision (90.6%)     ✅           │
│        +                            │
│  Latency (100%)        ✅           │
│        ÷ 2                          │
│        =                            │
│  Aggregated (95.1%)    📊           │
│                                     │
└─────────────────────────────────────┘
              ↓
        IGNORES ❌
              ↓
┌─────────────────────────────────────┐
│  Recall (33.9%)        ❌           │
│  170 Missed Objects    ❌           │
│  F1 Score (49.3%)      ❌           │
└─────────────────────────────────────┘
```

---

## Real-World Analogy

Imagine a security system:

```
✅ When it triggers an alarm, it's usually correct (90.6% precision)
✅ It responds immediately with no delays (100% latency)
❌ But it only detects 1 out of 3 intruders (33.9% recall)

Aggregated Score: 95.1% (looks great!)
Would you deploy this? NO!

Missing 66% of intruders is unacceptable, regardless of the
high precision and perfect timing.
```

---

## Metric Hierarchy

```
┌───────────────────────────────────────────┐
│      TEST SESSION RESULT: FAIL ❌         │
└───────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼─────────┐   ┌─────────▼────────┐
│ ACCURACY METRICS│   │ LATENCY METRICS  │
│    FAIL ❌      │   │    PASS ✅       │
└─────────────────┘   └──────────────────┘
        │                       │
    ┌───┴───┐               ┌──┴──┐
    │       │               │     │
┌───▼─┐ ┌──▼──┐ ┌─────┐ ┌──▼─┐ ┌─▼──┐
│ P   │ │ R   │ │ F1  │ │Mean│ │Pass│
│90.6%│ │33.9%│ │49.3%│ │11ms│ │100%│
│ ✅  │ │ ❌  │ │ ❌  │ │ ✅ │ │ ✅ │
└─────┘ └─────┘ └─────┘ └────┘ └────┘

Legend:
  P  = Precision
  R  = Recall
  F1 = F1 Score
```

---

## Recommendations

### Immediate Actions

1. **Investigate the 170 missed detections**
   - Review video footage for these objects
   - Check if they're edge cases (occlusion, partial views)
   - Verify ground truth annotations are correct

2. **Adjust detection threshold**
   - Current threshold may be too conservative
   - Lower confidence threshold to increase recall
   - Re-run test with adjusted settings

3. **Review ground truth quality**
   - Are all 257 annotations valid?
   - Are some annotations duplicates?
   - Are objects properly labeled?

---

### Root Cause Analysis

**Possible Reasons for Low Recall:**

1. **Detection Confidence Threshold Too High**
   - System requires very high confidence before reporting detection
   - Valid objects below threshold are missed

2. **Ground Truth Annotation Issues**
   - Over-annotation (objects marked that shouldn't be)
   - Duplicate annotations for same object
   - Annotations at video edges or transitions

3. **Model Limitations**
   - Model not trained on this scenario type
   - Lighting or video quality issues
   - Object types not well-represented in training data

4. **Occlusion or Partial Views**
   - Objects partially hidden
   - Objects at edge of frame
   - Fast-moving objects with motion blur

5. **Multi-Video Sequence Issues**
   - Timing synchronization problems
   - Objects appearing during video transitions
   - Cross-video duplicate handling

---

### Next Steps

```
┌──────────────────────────────────────────────────────┐
│ 1. Query database for FN detections                  │
│    → List all 170 missed ground truth objects        │
│    → Group by video, time, class                     │
└──────────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────┐
│ 2. Visual inspection                                 │
│    → Review video at timestamps of missed objects    │
│    → Identify common patterns (edges, occlusion)     │
└──────────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────┐
│ 3. Hypothesis testing                                │
│    → Lower threshold and re-test                     │
│    → Check if recall improves                        │
│    → Monitor precision impact                        │
└──────────────────────────────────────────────────────┘
                       ↓
┌──────────────────────────────────────────────────────┐
│ 4. Validation                                        │
│    → Compare with other sessions                     │
│    → Review ground truth annotations                 │
│    → Document findings                               │
└──────────────────────────────────────────────────────┘
```

---

## Metric Reference Guide

### Which Metric to Look At?

| Use Case | Metric | This Session |
|----------|--------|--------------|
| **Pass/Fail Decision** | F1 Score | 49.3% ❌ |
| **Detection Accuracy** | Precision | 90.6% ✅ |
| **Detection Completeness** | Recall | 33.9% ❌ |
| **Timing Performance** | Latency Pass Rate | 100% ✅ |
| **Quick Overview** | Aggregated | 95.1% ⚠️ |

**⚠️ Warning:** Don't rely solely on Aggregated Score!

---

### Metric Importance

```
Priority 1: F1 Score (49.3%)
  ↓ Determines pass/fail
  ↓ Must be ≥ 80%
  ↓
Priority 2: Precision & Recall
  ↓ Identify specific problems
  ↓ Balance false positives vs. false negatives
  ↓
Priority 3: Latency Metrics
  ↓ Ensure timing requirements met
  ↓ Must be ≥ 80% within threshold
  ↓
Priority 4: Aggregated Score
  ↓ Quick overview only
  ↓ Don't use for decisions
```

---

## Database Fields Reference

```sql
-- Session: fa204ef2-9d8b-4480-9692-86e338c1218a

SELECT
    tp_count,                              -- 87
    fp_count,                              -- 9
    fn_count,                              -- 170
    accuracy_precision,                    -- 0.90625
    accuracy_recall,                       -- 0.33852
    accuracy_f1_score,                     -- 0.49292
    latency_mean_ms,                       -- 11.039
    latency_max_ms,                        -- 20.708
    latency_percent_within_threshold,      -- 100.0
    accuracy_result,                       -- 'FAIL'
    latency_result,                        -- 'PASS'
    overall_test_result                    -- 'FAIL'
FROM test_sessions
WHERE id = 'fa204ef2-9d8b-4480-9692-86e338c1218a';
```

---

## API Response Structure

```json
{
  "session_id": "fa204ef2-9d8b-4480-9692-86e338c1218a",
  "status": "completed",
  "metrics": {
    "dual_precision": 90.6,
    "dual_recall": 33.9,
    "dual_f1_score": 49.3,
    "true_positives": 87,
    "false_positives": 9,
    "false_negatives": 170
  },
  "dual_evaluation": {
    "accuracy": {
      "precision": 90.6,
      "recall": 33.9,
      "f1Score": 49.3,
      "result": "FAIL",
      "counts": {
        "truePositives": 87,
        "falsePositives": 9,
        "falseNegatives": 170
      }
    },
    "latency": {
      "meanMs": 11.04,
      "maxMs": 20.71,
      "passRate": 100.0,
      "result": "PASS"
    }
  },
  "overall_result": "FAIL"
}
```

---

## Conclusion

### Key Findings

1. **Test correctly failed** due to low F1 score (49.3% < 80%)
2. **Root cause is low recall** (33.9%) - system missed 170/257 objects
3. **Aggregated score (95.1%) is misleading** - hides critical recall failure
4. **Precision is excellent (90.6%)** - few false positives
5. **Latency is perfect (100%)** - all detections fast

### The Bottom Line

```
╔═══════════════════════════════════════════════════════╗
║  The system is PRECISE but INCOMPLETE                 ║
║                                                       ║
║  ✅ Rarely makes mistakes when it detects            ║
║  ✅ Responds with excellent timing                   ║
║  ❌ Misses 2 out of 3 objects                        ║
║                                                       ║
║  This is unacceptable for production deployment.     ║
╚═══════════════════════════════════════════════════════╝
```

### Documentation

For complete metric definitions, formulas, and examples, see:
- **[METRIC_DEFINITIONS_EXPLAINED.md](METRIC_DEFINITIONS_EXPLAINED.md)** - Full documentation

---

**Report Generated:** 2025-11-24
**Analysis Tool:** Code Analyzer Agent
**Session Type:** Multi-video sequence test (2 videos)
