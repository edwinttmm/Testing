# Dual-Evaluation Architecture for HIL Test System

## Executive Summary

This document defines a fundamental architectural redesign to separate **Detection Accuracy Evaluation** from **Latency Performance Evaluation** in the HIL test validation system. The current implementation incorrectly conflates these two independent metrics, leading to incorrect pass/fail determinations.

---

## 1. Problem Statement

### Current WRONG Implementation (lines 1260-1270 in ground_truth_matching_service.py)

```python
# INCORRECT: Conflates accuracy with latency
if metrics.precision >= 0.8 and metrics.recall >= 0.75 and metrics.mean_latency_ms <= 100:
    test_session.pass_fail_result = "PASS"
elif metrics.precision >= 0.6 and metrics.recall >= 0.6:
    test_session.pass_fail_result = "CONDITIONAL_PASS"
else:
    test_session.pass_fail_result = "FAIL"
```

### Why This Is Fundamentally Wrong

1. **Detection accuracy (TP/FP/FN)** should be based ONLY on temporal matching within ±100ms tolerance
2. **Latency performance** should NOT affect whether a detection is classified as TP/FP/FN
3. A detection can be **TP (correct)** but still **FAIL on latency** (too slow)
4. Mixing these metrics produces invalid test results

**Example of the Problem:**
- Ground truth object at T=5.000s
- Detection at T=5.050s (50ms latency)
- **Correct behavior:**
  - Detection Accuracy: TP (within 100ms tolerance) ✓
  - Latency Performance: PASS (50ms < 100ms threshold) ✓
- **Current WRONG behavior:**
  - If latency is 120ms, the entire detection is marked as FAIL
  - But it should be: TP (accuracy) + FAIL (latency)

---

## 2. Correct Architecture: Dual-Evaluation System

### 2.1 Two Independent Evaluation Pipelines

```
┌─────────────────────────────────────────────────────────────┐
│                    HIL Test Evaluation                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────┐   ┌────────────────────────┐  │
│  │ Detection Accuracy      │   │ Latency Performance    │  │
│  │ Evaluation              │   │ Evaluation             │  │
│  ├─────────────────────────┤   ├────────────────────────┤  │
│  │ Input:                  │   │ Input:                 │  │
│  │ - TP count              │   │ - TP latencies ONLY    │  │
│  │ - FP count              │   │ - (FP/FN have no      │  │
│  │ - FN count              │   │   latency)             │  │
│  ├─────────────────────────┤   ├────────────────────────┤  │
│  │ Metrics:                │   │ Metrics:               │  │
│  │ - Precision             │   │ - Mean latency         │  │
│  │ - Recall                │   │ - Max latency          │  │
│  │ - F1 Score              │   │ - % within threshold   │  │
│  ├─────────────────────────┤   ├────────────────────────┤  │
│  │ Result:                 │   │ Result:                │  │
│  │ - accuracy_result       │   │ - latency_result       │  │
│  └─────────────────────────┘   └────────────────────────┘  │
│               │                           │                 │
│               └───────────┬───────────────┘                 │
│                           ▼                                 │
│                  ┌─────────────────┐                        │
│                  │ Overall Result  │                        │
│                  │ Aggregation     │                        │
│                  └─────────────────┘                        │
│                           │                                 │
│                           ▼                                 │
│                  overall_test_result                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Detection Accuracy Evaluation (Independent of Latency)

**Purpose:** Determine if the system correctly identifies objects

**Classification Logic:**
```python
for each ground_truth_object:
    for each detection_event:
        temporal_offset = abs(detection.timestamp - ground_truth.timestamp)

        if temporal_offset <= tolerance_ms (100ms):
            classification = "TP"  # True Positive
            # Latency is recorded but doesn't affect TP status
        else:
            classification = "FP"  # False Positive

    if no_detection_matched:
        classification = "FN"  # False Negative
```

**Metrics Calculation:**
```python
precision = TP / (TP + FP)
recall = TP / (TP + FN)
f1_score = 2 * (precision * recall) / (precision + recall)
```

**Pass Criteria:**
```python
if f1_score >= 0.75:
    accuracy_result = "PASS"
elif f1_score >= 0.60:
    accuracy_result = "CONDITIONAL_PASS"
else:
    accuracy_result = "FAIL"
```

**Reasoning:**
- F1 Score >= 75%: Production-ready detection accuracy
- F1 Score 60-75%: Acceptable with monitoring
- F1 Score < 60%: Unacceptable detection performance

### 2.3 Latency Performance Evaluation (TP Detections Only)

**Purpose:** Determine if TP detections meet real-time latency requirements

**Input Data:**
- Only TP (True Positive) detections have meaningful latency
- FP and FN have no latency to measure

**Metrics Calculation:**
```python
tp_detections = [d for d in detections if d.match_type == "TP"]
latencies_ms = [d.actual_latency_ms for d in tp_detections]

mean_latency = sum(latencies_ms) / len(latencies_ms)
max_latency = max(latencies_ms)
within_threshold = sum(1 for lat in latencies_ms if lat <= threshold_ms)
percent_within_threshold = (within_threshold / len(latencies_ms)) * 100
```

**Pass Criteria:**
```python
if mean_latency <= 100 and percent_within_threshold >= 95:
    latency_result = "PASS"
elif mean_latency <= 200 and percent_within_threshold >= 80:
    latency_result = "CONDITIONAL_PASS"
else:
    latency_result = "FAIL"
```

**Reasoning:**
- PASS: Mean ≤100ms + 95% within threshold = Real-time performance
- CONDITIONAL_PASS: Mean ≤200ms + 80% within threshold = Acceptable with optimization
- FAIL: Beyond acceptable latency for safety-critical HIL testing

### 2.4 Overall Test Result Aggregation

**Logic:**
```python
def calculate_overall_result(accuracy_result: str, latency_result: str) -> str:
    """
    Combine accuracy and latency results into overall test result.

    Both must PASS for overall PASS.
    Either CONDITIONAL_PASS results in overall CONDITIONAL_PASS.
    Either FAIL results in overall FAIL.
    """

    if accuracy_result == "FAIL" or latency_result == "FAIL":
        return "FAIL"

    if accuracy_result == "CONDITIONAL_PASS" or latency_result == "CONDITIONAL_PASS":
        return "CONDITIONAL_PASS"

    # Both are PASS
    return "PASS"
```

**All Possible Outcomes:**

| Accuracy Result   | Latency Result   | Overall Result    | Interpretation                                    |
|-------------------|------------------|-------------------|---------------------------------------------------|
| PASS              | PASS             | PASS              | Excellent: Accurate + Fast                        |
| PASS              | CONDITIONAL_PASS | CONDITIONAL_PASS  | Good detection, slow latency (needs optimization) |
| PASS              | FAIL             | FAIL              | Accurate but too slow (unacceptable latency)      |
| CONDITIONAL_PASS  | PASS             | CONDITIONAL_PASS  | Fast but moderate accuracy (needs improvement)    |
| CONDITIONAL_PASS  | CONDITIONAL_PASS | CONDITIONAL_PASS  | Both need improvement                             |
| CONDITIONAL_PASS  | FAIL             | FAIL              | Too slow (latency blocker)                        |
| FAIL              | PASS             | FAIL              | Fast but inaccurate (accuracy blocker)            |
| FAIL              | CONDITIONAL_PASS | FAIL              | Inaccurate (accuracy blocker)                     |
| FAIL              | FAIL             | FAIL              | Both metrics fail                                 |

---

## 3. Database Schema Changes

### 3.1 TestSession Model Updates

**Add new fields to `test_sessions` table:**

```python
class TestSession(Base):
    __tablename__ = "test_sessions"

    # ... existing fields ...

    # DUAL EVALUATION RESULTS - NEW FIELDS
    accuracy_result = Column(String, nullable=True, index=True)
    # Values: 'PASS', 'CONDITIONAL_PASS', 'FAIL'
    # Based on F1 score from TP/FP/FN classification

    latency_result = Column(String, nullable=True, index=True)
    # Values: 'PASS', 'CONDITIONAL_PASS', 'FAIL'
    # Based on mean latency of TP detections only

    overall_test_result = Column(String, nullable=True, index=True)
    # Values: 'PASS', 'CONDITIONAL_PASS', 'FAIL'
    # Aggregation of accuracy_result and latency_result

    # DETAILED METRICS FOR DUAL EVALUATION
    accuracy_f1_score = Column(Float, nullable=True, index=True)
    # F1 score from TP/FP/FN classification

    accuracy_precision = Column(Float, nullable=True)
    # Precision = TP / (TP + FP)

    accuracy_recall = Column(Float, nullable=True)
    # Recall = TP / (TP + FN)

    latency_mean_ms = Column(Float, nullable=True, index=True)
    # Mean latency of TP detections only

    latency_max_ms = Column(Float, nullable=True)
    # Maximum latency among TP detections

    latency_percent_within_threshold = Column(Float, nullable=True)
    # Percentage of TP detections within latency threshold

    # COUNTS FOR TRANSPARENCY
    tp_count = Column(Integer, nullable=True, index=True)
    # True Positive count

    fp_count = Column(Integer, nullable=True)
    # False Positive count

    fn_count = Column(Integer, nullable=True)
    # False Negative count

    # DEPRECATED FIELD (kept for backward compatibility)
    # pass_fail_result = Column(String)  # DEPRECATED: Use overall_test_result instead

    # ... rest of fields ...
```

### 3.2 Migration Strategy

**Alembic Migration:**

```python
"""Add dual evaluation fields to test_sessions

Revision ID: add_dual_evaluation_fields
Revises: previous_revision
Create Date: 2025-11-11
"""

def upgrade():
    # Add new dual evaluation fields
    op.add_column('test_sessions', sa.Column('accuracy_result', sa.String(), nullable=True))
    op.add_column('test_sessions', sa.Column('latency_result', sa.String(), nullable=True))
    op.add_column('test_sessions', sa.Column('overall_test_result', sa.String(), nullable=True))

    op.add_column('test_sessions', sa.Column('accuracy_f1_score', sa.Float(), nullable=True))
    op.add_column('test_sessions', sa.Column('accuracy_precision', sa.Float(), nullable=True))
    op.add_column('test_sessions', sa.Column('accuracy_recall', sa.Float(), nullable=True))

    op.add_column('test_sessions', sa.Column('latency_mean_ms', sa.Float(), nullable=True))
    op.add_column('test_sessions', sa.Column('latency_max_ms', sa.Float(), nullable=True))
    op.add_column('test_sessions', sa.Column('latency_percent_within_threshold', sa.Float(), nullable=True))

    op.add_column('test_sessions', sa.Column('tp_count', sa.Integer(), nullable=True))
    op.add_column('test_sessions', sa.Column('fp_count', sa.Integer(), nullable=True))
    op.add_column('test_sessions', sa.Column('fn_count', sa.Integer(), nullable=True))

    # Add indexes for performance
    op.create_index('idx_testsession_accuracy_result', 'test_sessions', ['accuracy_result'])
    op.create_index('idx_testsession_latency_result', 'test_sessions', ['latency_result'])
    op.create_index('idx_testsession_overall_result', 'test_sessions', ['overall_test_result'])
    op.create_index('idx_testsession_f1_score', 'test_sessions', ['accuracy_f1_score'])
    op.create_index('idx_testsession_latency_mean', 'test_sessions', ['latency_mean_ms'])
    op.create_index('idx_testsession_tp_count', 'test_sessions', ['tp_count'])

def downgrade():
    # Remove indexes
    op.drop_index('idx_testsession_tp_count', 'test_sessions')
    op.drop_index('idx_testsession_latency_mean', 'test_sessions')
    op.drop_index('idx_testsession_f1_score', 'test_sessions')
    op.drop_index('idx_testsession_overall_result', 'test_sessions')
    op.drop_index('idx_testsession_latency_result', 'test_sessions')
    op.drop_index('idx_testsession_accuracy_result', 'test_sessions')

    # Remove columns
    op.drop_column('test_sessions', 'fn_count')
    op.drop_column('test_sessions', 'fp_count')
    op.drop_column('test_sessions', 'tp_count')
    op.drop_column('test_sessions', 'latency_percent_within_threshold')
    op.drop_column('test_sessions', 'latency_max_ms')
    op.drop_column('test_sessions', 'latency_mean_ms')
    op.drop_column('test_sessions', 'accuracy_recall')
    op.drop_column('test_sessions', 'accuracy_precision')
    op.drop_column('test_sessions', 'accuracy_f1_score')
    op.drop_column('test_sessions', 'overall_test_result')
    op.drop_column('test_sessions', 'latency_result')
    op.drop_column('test_sessions', 'accuracy_result')
```

---

## 4. Pass/Fail Threshold Definitions

### 4.1 Detection Accuracy Thresholds

**Metric:** F1 Score (harmonic mean of precision and recall)

| Threshold        | F1 Score Range | Classification     | Business Meaning                                      |
|------------------|----------------|--------------------|-------------------------------------------------------|
| **PASS**         | >= 75%         | PASS               | Production-ready detection accuracy                   |
| **CONDITIONAL**  | 60% - 75%      | CONDITIONAL_PASS   | Acceptable with monitoring, needs improvement         |
| **FAIL**         | < 60%          | FAIL               | Unacceptable detection performance, blocks deployment |

**Rationale:**
- **F1 >= 75%:** Industry standard for safety-critical systems
- **F1 60-75%:** Acceptable for development/testing, requires improvement plan
- **F1 < 60%:** Indicates fundamental detection issues, must be resolved

**Example Calculations:**

| Scenario | TP  | FP | FN | Precision | Recall | F1 Score | Result            |
|----------|-----|----|----|-----------|--------|----------|-------------------|
| Good     | 95  | 5  | 5  | 95%       | 95%    | 95%      | PASS              |
| Moderate | 70  | 20 | 10 | 77.8%     | 87.5%  | 82.4%    | PASS              |
| Marginal | 60  | 30 | 10 | 66.7%     | 85.7%  | 75.0%    | CONDITIONAL_PASS  |
| Poor     | 50  | 40 | 10 | 55.6%     | 83.3%  | 66.7%    | CONDITIONAL_PASS  |
| Bad      | 40  | 50 | 20 | 44.4%     | 66.7%  | 53.3%    | FAIL              |

### 4.2 Latency Performance Thresholds

**Metrics:**
1. Mean latency of TP detections
2. Percentage of TP detections within threshold

| Threshold        | Mean Latency | % Within Threshold | Classification     | Business Meaning                              |
|------------------|--------------|--------------------|--------------------|-----------------------------------------------|
| **PASS**         | <= 100ms     | >= 95%             | PASS               | Real-time performance for safety applications |
| **CONDITIONAL**  | <= 200ms     | >= 80%             | CONDITIONAL_PASS   | Acceptable with optimization needed           |
| **FAIL**         | > 200ms      | < 80%              | FAIL               | Too slow for real-time HIL testing            |

**Rationale:**
- **100ms threshold:** Industry standard for real-time VRU detection systems
- **95% consistency:** High reliability required for safety-critical applications
- **200ms conditional:** Maximum acceptable for development, requires optimization

**Example Calculations:**

| Scenario      | Mean Latency | Max Latency | % Within 100ms | Result            |
|---------------|--------------|-------------|----------------|-------------------|
| Excellent     | 45ms         | 85ms        | 100%           | PASS              |
| Good          | 85ms         | 120ms       | 95%            | PASS              |
| Marginal      | 110ms        | 180ms       | 85%            | CONDITIONAL_PASS  |
| Poor          | 150ms        | 250ms       | 75%            | CONDITIONAL_PASS  |
| Unacceptable  | 220ms        | 400ms       | 60%            | FAIL              |

### 4.3 Configuration and Flexibility

**Thresholds should be configurable per test session:**

```python
class TestSession(Base):
    # ... fields ...

    # Accuracy thresholds (configurable)
    accuracy_pass_threshold = Column(Float, default=0.75)
    accuracy_conditional_threshold = Column(Float, default=0.60)

    # Latency thresholds (configurable)
    latency_pass_mean_ms = Column(Float, default=100.0)
    latency_pass_percent = Column(Float, default=95.0)
    latency_conditional_mean_ms = Column(Float, default=200.0)
    latency_conditional_percent = Column(Float, default=80.0)
```

---

## 5. Decision Tree: All Possible Outcomes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     HIL Test Evaluation Decision Tree                   │
└─────────────────────────────────────────────────────────────────────────┘

START: Test session completed
  │
  ├─ Step 1: Calculate TP/FP/FN from temporal matching (±100ms tolerance)
  │    │
  │    ├─ TP: Detection within 100ms of ground truth
  │    ├─ FP: Detection NOT within 100ms of any ground truth
  │    └─ FN: Ground truth NOT matched by any detection
  │
  ├─ Step 2: Evaluate Detection Accuracy
  │    │
  │    ├─ Calculate: precision = TP / (TP + FP)
  │    ├─ Calculate: recall = TP / (TP + FN)
  │    ├─ Calculate: f1_score = 2 * (precision * recall) / (precision + recall)
  │    │
  │    └─ Determine accuracy_result:
  │         ├─ f1_score >= 0.75 → accuracy_result = "PASS"
  │         ├─ f1_score >= 0.60 → accuracy_result = "CONDITIONAL_PASS"
  │         └─ f1_score < 0.60  → accuracy_result = "FAIL"
  │
  ├─ Step 3: Evaluate Latency Performance (TP detections only)
  │    │
  │    ├─ Extract latencies: latencies = [tp.actual_latency_ms for tp in TP_detections]
  │    ├─ Calculate: mean_latency = mean(latencies)
  │    ├─ Calculate: percent_within = (count(lat <= 100) / total) * 100
  │    │
  │    └─ Determine latency_result:
  │         ├─ mean <= 100ms AND percent >= 95% → latency_result = "PASS"
  │         ├─ mean <= 200ms AND percent >= 80% → latency_result = "CONDITIONAL_PASS"
  │         └─ Otherwise                        → latency_result = "FAIL"
  │
  └─ Step 4: Aggregate Overall Result
       │
       ├─ IF accuracy_result == "FAIL" OR latency_result == "FAIL":
       │    └─ overall_test_result = "FAIL"
       │
       ├─ ELSE IF accuracy_result == "CONDITIONAL_PASS" OR latency_result == "CONDITIONAL_PASS":
       │    └─ overall_test_result = "CONDITIONAL_PASS"
       │
       └─ ELSE:
            └─ overall_test_result = "PASS"

END: Test session updated with:
  - accuracy_result
  - latency_result
  - overall_test_result
  - All supporting metrics
```

### 5.1 Outcome Matrix (All 9 Combinations)

| #  | Accuracy Result   | Latency Result   | Overall Result    | User Action                                           |
|----|-------------------|------------------|-------------------|-------------------------------------------------------|
| 1  | PASS              | PASS             | PASS              | ✓ Deploy to production                                |
| 2  | PASS              | CONDITIONAL_PASS | CONDITIONAL_PASS  | ⚠ Optimize latency before production                  |
| 3  | PASS              | FAIL             | FAIL              | ✗ Fix latency issues (accuracy is good)               |
| 4  | CONDITIONAL_PASS  | PASS             | CONDITIONAL_PASS  | ⚠ Improve detection accuracy (latency is good)        |
| 5  | CONDITIONAL_PASS  | CONDITIONAL_PASS | CONDITIONAL_PASS  | ⚠ Improve both accuracy and latency                   |
| 6  | CONDITIONAL_PASS  | FAIL             | FAIL              | ✗ Critical: Fix latency, improve accuracy             |
| 7  | FAIL              | PASS             | FAIL              | ✗ Critical: Fix detection accuracy (latency is good)  |
| 8  | FAIL              | CONDITIONAL_PASS | FAIL              | ✗ Critical: Fix detection accuracy                    |
| 9  | FAIL              | FAIL             | FAIL              | ✗ Critical: System needs major overhaul               |

---

## 6. How This Fixes the Conflation Issue

### 6.1 Before: Single Conflated Metric

**Problem:**
```python
# WRONG: Latency affects TP/FP/FN classification
if precision >= 0.8 and recall >= 0.75 and mean_latency_ms <= 100:
    result = "PASS"
```

**Issues:**
1. A detection can be temporally correct (TP) but fail due to high latency
2. System cannot distinguish between "wrong detection" vs "slow detection"
3. No actionable feedback: "Fix accuracy" or "Fix latency"?

### 6.2 After: Dual Independent Metrics

**Solution:**
```python
# CORRECT: Separate evaluations
accuracy_result = evaluate_detection_accuracy(tp, fp, fn)
latency_result = evaluate_latency_performance(tp_detections)
overall_result = aggregate_results(accuracy_result, latency_result)
```

**Benefits:**
1. **Clear distinction:** TP/FP/FN based only on temporal matching
2. **Independent metrics:** Accuracy and latency evaluated separately
3. **Actionable feedback:** Know exactly what to fix
4. **Realistic scenarios:** Can have accurate but slow detections (TP + latency FAIL)

### 6.3 Example: Real-World Scenario

**Test Session:**
- 100 ground truth objects
- 95 detections matched within 100ms → TP = 95
- 5 detections outside 100ms → FP = 5
- 5 ground truth objects unmatched → FN = 5
- **BUT:** Of the 95 TP detections, 30 have latency > 100ms

**Current WRONG Evaluation:**
```python
precision = 95/100 = 95%
recall = 95/100 = 95%
mean_latency = 120ms  # High due to 30 slow detections

# Result: FAIL (because latency > 100ms)
# Problem: Good detection accuracy is hidden!
```

**Correct DUAL Evaluation:**
```python
# Accuracy Evaluation
precision = 95/100 = 95%
recall = 95/100 = 95%
f1_score = 95%
accuracy_result = "PASS"  # Excellent detection accuracy!

# Latency Evaluation (TP detections only)
mean_latency = 120ms
percent_within_100ms = 65/95 = 68.4%
latency_result = "CONDITIONAL_PASS"  # Needs optimization

# Overall Result
overall_test_result = "CONDITIONAL_PASS"

# Actionable Feedback:
# - Detection accuracy: EXCELLENT ✓
# - Latency performance: NEEDS OPTIMIZATION ⚠
# - Action: Optimize processing pipeline for faster latency
```

---

## 7. Implementation Pseudocode

### 7.1 Core Evaluation Function

```python
def evaluate_test_session_dual(
    db: Session,
    test_session: TestSession,
    match_results: List[MatchResult]
) -> None:
    """
    Evaluate test session using dual-evaluation architecture.

    This function:
    1. Evaluates detection accuracy (TP/FP/FN)
    2. Evaluates latency performance (TP detections only)
    3. Aggregates into overall result
    4. Updates test_session with all metrics
    """

    # =====================================================================
    # STEP 1: Calculate TP/FP/FN counts
    # =====================================================================
    tp_count = sum(1 for m in match_results if m.match_type == "TP")
    fp_count = sum(1 for m in match_results if m.match_type == "FP")
    fn_count = sum(1 for m in match_results if m.match_type == "FN")

    # =====================================================================
    # STEP 2: Evaluate Detection Accuracy
    # =====================================================================
    accuracy_result, accuracy_metrics = evaluate_detection_accuracy(
        tp_count=tp_count,
        fp_count=fp_count,
        fn_count=fn_count,
        pass_threshold=test_session.accuracy_pass_threshold or 0.75,
        conditional_threshold=test_session.accuracy_conditional_threshold or 0.60
    )

    # =====================================================================
    # STEP 3: Evaluate Latency Performance (TP detections only)
    # =====================================================================
    tp_detections = [m for m in match_results if m.match_type == "TP"]

    if tp_detections:
        latency_result, latency_metrics = evaluate_latency_performance(
            tp_detections=tp_detections,
            mean_threshold_ms=test_session.latency_pass_mean_ms or 100.0,
            percent_threshold=test_session.latency_pass_percent or 95.0,
            conditional_mean_ms=test_session.latency_conditional_mean_ms or 200.0,
            conditional_percent=test_session.latency_conditional_percent or 80.0
        )
    else:
        # No TP detections = cannot evaluate latency
        latency_result = "N/A"
        latency_metrics = None

    # =====================================================================
    # STEP 4: Aggregate Overall Result
    # =====================================================================
    overall_result = aggregate_dual_results(accuracy_result, latency_result)

    # =====================================================================
    # STEP 5: Update TestSession
    # =====================================================================
    test_session.accuracy_result = accuracy_result
    test_session.accuracy_f1_score = accuracy_metrics['f1_score']
    test_session.accuracy_precision = accuracy_metrics['precision']
    test_session.accuracy_recall = accuracy_metrics['recall']

    test_session.latency_result = latency_result
    if latency_metrics:
        test_session.latency_mean_ms = latency_metrics['mean_latency']
        test_session.latency_max_ms = latency_metrics['max_latency']
        test_session.latency_percent_within_threshold = latency_metrics['percent_within']

    test_session.overall_test_result = overall_result

    test_session.tp_count = tp_count
    test_session.fp_count = fp_count
    test_session.fn_count = fn_count

    test_session.actual_detections = tp_count + fp_count
    test_session.overall_score = accuracy_metrics['f1_score'] * 100  # Legacy field

    # Set completion time if not set
    if not test_session.completed_at:
        test_session.completed_at = datetime.utcnow()

    db.commit()


def evaluate_detection_accuracy(
    tp_count: int,
    fp_count: int,
    fn_count: int,
    pass_threshold: float = 0.75,
    conditional_threshold: float = 0.60
) -> Tuple[str, Dict]:
    """
    Evaluate detection accuracy based on TP/FP/FN.

    Returns:
        (accuracy_result, accuracy_metrics)
    """
    if tp_count + fp_count == 0:
        precision = 0.0
    else:
        precision = tp_count / (tp_count + fp_count)

    if tp_count + fn_count == 0:
        recall = 0.0
    else:
        recall = tp_count / (tp_count + fn_count)

    if precision + recall == 0:
        f1_score = 0.0
    else:
        f1_score = 2 * (precision * recall) / (precision + recall)

    # Determine result based on F1 score
    if f1_score >= pass_threshold:
        result = "PASS"
    elif f1_score >= conditional_threshold:
        result = "CONDITIONAL_PASS"
    else:
        result = "FAIL"

    metrics = {
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'tp_count': tp_count,
        'fp_count': fp_count,
        'fn_count': fn_count
    }

    return result, metrics


def evaluate_latency_performance(
    tp_detections: List[MatchResult],
    mean_threshold_ms: float = 100.0,
    percent_threshold: float = 95.0,
    conditional_mean_ms: float = 200.0,
    conditional_percent: float = 80.0
) -> Tuple[str, Dict]:
    """
    Evaluate latency performance of TP detections.

    Returns:
        (latency_result, latency_metrics)
    """
    if not tp_detections:
        return "N/A", None

    # Extract latencies from TP detections
    latencies = []
    for det in tp_detections:
        if hasattr(det, 'temporal_offset') and det.temporal_offset is not None:
            latency_ms = abs(det.temporal_offset * 1000)  # Convert to ms
            latencies.append(latency_ms)

    if not latencies:
        return "N/A", None

    # Calculate metrics
    mean_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    min_latency = min(latencies)
    within_threshold = sum(1 for lat in latencies if lat <= mean_threshold_ms)
    percent_within = (within_threshold / len(latencies)) * 100

    # Determine result
    if mean_latency <= mean_threshold_ms and percent_within >= percent_threshold:
        result = "PASS"
    elif mean_latency <= conditional_mean_ms and percent_within >= conditional_percent:
        result = "CONDITIONAL_PASS"
    else:
        result = "FAIL"

    metrics = {
        'mean_latency': mean_latency,
        'max_latency': max_latency,
        'min_latency': min_latency,
        'percent_within': percent_within,
        'total_tp_detections': len(latencies)
    }

    return result, metrics


def aggregate_dual_results(accuracy_result: str, latency_result: str) -> str:
    """
    Aggregate accuracy and latency results into overall test result.

    Logic:
    - Both PASS → overall PASS
    - Either CONDITIONAL_PASS → overall CONDITIONAL_PASS
    - Either FAIL → overall FAIL
    - N/A handled specially
    """
    if latency_result == "N/A":
        # If no latency data, overall result is based on accuracy only
        return accuracy_result

    if accuracy_result == "FAIL" or latency_result == "FAIL":
        return "FAIL"

    if accuracy_result == "CONDITIONAL_PASS" or latency_result == "CONDITIONAL_PASS":
        return "CONDITIONAL_PASS"

    return "PASS"
```

---

## 8. API Response Schema

### 8.1 Test Session Response (Updated)

```json
{
  "id": "abc123",
  "name": "HIL Test Session 2025-11-11",
  "status": "completed",

  "dualEvaluation": {
    "accuracyResult": "PASS",
    "accuracyMetrics": {
      "f1Score": 0.95,
      "precision": 0.95,
      "recall": 0.95,
      "tpCount": 95,
      "fpCount": 5,
      "fnCount": 5
    },

    "latencyResult": "CONDITIONAL_PASS",
    "latencyMetrics": {
      "meanLatencyMs": 120.5,
      "maxLatencyMs": 250.0,
      "minLatencyMs": 45.0,
      "percentWithinThreshold": 68.4,
      "totalTpDetections": 95
    },

    "overallTestResult": "CONDITIONAL_PASS",

    "interpretation": {
      "summary": "Good detection accuracy, latency needs optimization",
      "accuracyVerdict": "Excellent detection performance (F1: 95%)",
      "latencyVerdict": "Latency exceeds target (mean: 120ms, target: 100ms)",
      "recommendation": "Optimize processing pipeline to reduce latency"
    }
  },

  "thresholds": {
    "accuracyPassThreshold": 0.75,
    "accuracyConditionalThreshold": 0.60,
    "latencyPassMeanMs": 100.0,
    "latencyPassPercent": 95.0,
    "latencyConditionalMeanMs": 200.0,
    "latencyConditionalPercent": 80.0
  }
}
```

---

## 9. Benefits of Dual-Evaluation Architecture

### 9.1 Technical Benefits

1. **Architectural Correctness**
   - Separates concerns: accuracy vs. performance
   - Each metric evaluated independently with correct logic
   - No conflation of unrelated measurements

2. **Data Integrity**
   - TP/FP/FN classification based solely on temporal matching
   - Latency measured only for meaningful detections (TP)
   - FP and FN correctly excluded from latency calculations

3. **Actionable Insights**
   - Clear diagnosis: "accuracy problem" vs "latency problem"
   - Targeted optimization: know exactly what to fix
   - Progress tracking: monitor each metric independently

### 9.2 Business Benefits

1. **Better Decision Making**
   - Distinguish between "wrong" and "slow"
   - Prioritize fixes: accuracy vs. latency optimization
   - Realistic assessment of system readiness

2. **Compliance and Reporting**
   - Transparent metrics for regulatory requirements
   - Separate accuracy and latency reporting
   - Clear pass/fail criteria for each dimension

3. **Development Efficiency**
   - Focus optimization efforts on actual bottlenecks
   - Avoid unnecessary rework from incorrect diagnoses
   - Faster iteration cycles with clear feedback

---

## 10. Migration and Rollout Plan

### 10.1 Phase 1: Database Migration
- [ ] Create Alembic migration for new fields
- [ ] Run migration on development database
- [ ] Verify schema changes

### 10.2 Phase 2: Service Layer Updates
- [ ] Update `ground_truth_matching_service.py`:
  - Replace `_update_test_session_result()` with `evaluate_test_session_dual()`
  - Implement `evaluate_detection_accuracy()`
  - Implement `evaluate_latency_performance()`
  - Implement `aggregate_dual_results()`
- [ ] Update `SessionMetrics` dataclass to include dual evaluation fields
- [ ] Add unit tests for each evaluation function

### 10.3 Phase 3: API Updates
- [ ] Update test session response schemas
- [ ] Add dual evaluation fields to API responses
- [ ] Maintain backward compatibility with legacy `pass_fail_result` field

### 10.4 Phase 4: Frontend Updates
- [ ] Update UI to display dual evaluation results
- [ ] Add separate badges for accuracy and latency results
- [ ] Show detailed metrics for each dimension

### 10.5 Phase 5: Testing and Validation
- [ ] Test with existing test sessions
- [ ] Verify correct classification of TP/FP/FN
- [ ] Verify latency calculations for TP detections only
- [ ] Compare old vs. new evaluation logic

### 10.6 Phase 6: Deprecation
- [ ] Mark `pass_fail_result` as deprecated
- [ ] Update documentation to use `overall_test_result`
- [ ] Plan eventual removal of deprecated field

---

## 11. Testing Strategy

### 11.1 Unit Tests

```python
def test_evaluate_detection_accuracy_pass():
    result, metrics = evaluate_detection_accuracy(
        tp_count=95, fp_count=5, fn_count=5
    )
    assert result == "PASS"
    assert metrics['f1_score'] >= 0.75

def test_evaluate_detection_accuracy_conditional():
    result, metrics = evaluate_detection_accuracy(
        tp_count=70, fp_count=20, fn_count=10
    )
    assert result == "CONDITIONAL_PASS"
    assert 0.60 <= metrics['f1_score'] < 0.75

def test_evaluate_latency_performance_pass():
    tp_detections = [
        MatchResult(temporal_offset=0.045),  # 45ms
        MatchResult(temporal_offset=0.050),  # 50ms
        # ... 95% within 100ms
    ]
    result, metrics = evaluate_latency_performance(tp_detections)
    assert result == "PASS"
    assert metrics['mean_latency'] <= 100
    assert metrics['percent_within'] >= 95

def test_aggregate_dual_results():
    assert aggregate_dual_results("PASS", "PASS") == "PASS"
    assert aggregate_dual_results("PASS", "FAIL") == "FAIL"
    assert aggregate_dual_results("CONDITIONAL_PASS", "PASS") == "CONDITIONAL_PASS"
```

### 11.2 Integration Tests

```python
def test_dual_evaluation_realistic_scenario(db_session):
    # Setup test session with 100 ground truth, 95 TP, 5 FP, 5 FN
    # 30 TP detections have latency > 100ms

    session = create_test_session(...)
    match_results = create_match_results(...)

    evaluate_test_session_dual(db_session, session, match_results)

    # Verify dual evaluation
    assert session.accuracy_result == "PASS"  # F1 = 95%
    assert session.latency_result == "CONDITIONAL_PASS"  # Mean > 100ms
    assert session.overall_test_result == "CONDITIONAL_PASS"

    # Verify metrics
    assert session.tp_count == 95
    assert session.fp_count == 5
    assert session.fn_count == 5
    assert session.accuracy_f1_score == 0.95
    assert session.latency_mean_ms > 100
```

---

## 12. Conclusion

The dual-evaluation architecture solves the fundamental conflation issue in the current HIL test validation system by:

1. **Separating concerns:** Detection accuracy (TP/FP/FN) and latency performance are independent metrics
2. **Correct classification:** TP/FP/FN based solely on temporal matching, not latency
3. **Actionable feedback:** Clear diagnosis of accuracy vs. latency issues
4. **Realistic assessment:** A detection can be accurate but slow (TP + latency FAIL)
5. **Better decision-making:** Know exactly what to optimize

This architecture aligns with industry best practices for safety-critical HIL testing and provides transparent, traceable, and actionable metrics for system validation.

---

**Document Version:** 1.0
**Date:** 2025-11-11
**Author:** System Architecture Designer
**Status:** Design Specification
**Next Steps:** Implementation, Testing, Deployment
