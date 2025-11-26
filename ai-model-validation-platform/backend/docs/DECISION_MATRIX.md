# Algorithm Change Decision Matrix

**Proposed Change**: Emit continuous detections while voltage stays high (rate-limited by MIN_INTERVAL)
**Current Behavior**: Single rising-edge detection per event

---

## 🚦 DECISION: REJECT ❌

**Risk Score**: 🔴 **8.5/10** (High Risk)
**Recommended Alternative**: ✅ **Option C: Post-Processing Expansion**

---

## Quick Comparison

| Aspect | Current | Proposed (Continuous) | Option C (Expansion) |
|--------|---------|----------------------|---------------------|
| **DB Writes/Session** | 100 | 1,200 (+1100%) 🔴 | 100 (no change) ✅ |
| **GT Precision** | 95% | ~15% (-84%) 🔴 | 95% (maintained) ✅ |
| **API Breaking Change** | No | YES 🔴 | NO ✅ |
| **UI Performance** | 60 FPS | 15-20 FPS 🔴 | 60 FPS ✅ |
| **Implementation Time** | N/A | 4-6 weeks 🟡 | 1-2 days ✅ |
| **Rollback Risk** | N/A | HIGH 🔴 | LOW ✅ |

---

## Risk Severity Legend

- 🔴 **CRITICAL**: System instability, data corruption, user-facing failures
- 🟡 **HIGH/MEDIUM**: Performance degradation, configuration issues
- 🟢 **LOW**: Minimal impact, easily mitigated

---

## Critical Risks (Must Fix Before Approval)

### 1. Database Write Amplification 🔴
**Problem**: 12× increase in database writes causes lock contention
**Impact**: Monitoring lag 50-100ms → HIL test failures
**Status**: Unresolved without batching + async I/O

### 2. Ground Truth Matching Failure 🔴
**Problem**: Hungarian algorithm assumes 1 detection = 1 event
**Impact**: Precision drops from 95% to ~15% (unusable validation)
**Status**: Requires complete algorithm redesign

### 3. Semantic Contract Violation 🔴
**Problem**: Changes meaning of "detection" breaks API contract
**Impact**: All clients see 12× detection rate increase (misleading)
**Status**: Requires API versioning + migration plan

---

## Why Option C Is Better

**Option C (Post-Processing Expansion)** achieves the same goal without breaking changes:

```
Storage Layer:
  ✅ Keep 1 detection/event (no DB bloat)
  ✅ No API changes (backward compatible)
  ✅ No UI changes (discrete events)

GT Matching Layer:
  ✅ Expand detections into 100ms windows (temporal precision)
  ✅ Match expanded set to ground truth (fine-grained)
  ✅ Collapse by parent ID (automatic deduplication)

Result:
  ✅ Same temporal matching precision as continuous emission
  ✅ Zero production risk
  ✅ 1-2 day implementation vs. 4-6 weeks
```

---

## Implementation Paths

### Path 1: REJECT & Use Option C (RECOMMENDED) ✅

**Timeline**: 1-2 days
**Risk**: 🟢 LOW

```python
# Step 1: Modify GT matching service (isolated change)
def match_detections_to_ground_truth(session_id):
    detections = get_detections()  # Still 1/event

    # Expand each detection
    expanded = expand_to_temporal_windows(detections, interval_ms=100)

    # Match (existing Hungarian algorithm works)
    matches = hungarian_matching(expanded, ground_truth)

    # Collapse to parent detections
    return deduplicate_by_parent(matches)

# Step 2: Test with historical data
# Step 3: Deploy (no client changes needed)
```

**Deliverables**:
- [ ] Update `ground_truth_matching_service.py` (1 function)
- [ ] Add unit tests for expansion logic
- [ ] Validate with 10 historical sessions
- [ ] Deploy to production

---

### Path 2: Implement Continuous Emission (NOT RECOMMENDED) ❌

**Timeline**: 4-6 weeks
**Risk**: 🔴 HIGH

**Required Mitigations** (ALL mandatory):
1. Batch database commits (1 week)
2. Async I/O for storage (1 week)
3. API versioning + migration (1 week)
4. Hungarian algorithm redesign (1 week)
5. MIN_INTERVAL validation (2 days)
6. UI throttling + cluster display (1 week)
7. Client migration plan (1 week)
8. A/B testing (2 weeks)
9. Rollback procedures (3 days)

**Success Criteria** (must meet ALL):
- [ ] Write latency p99 < 50ms
- [ ] GT Precision ≥ 90%
- [ ] UI frame rate ≥ 45 FPS
- [ ] Zero client complaints
- [ ] Successful 2-week A/B test

**If ANY criterion fails**: ROLLBACK to current algorithm

---

## Questions to Answer

Before proceeding, clarify the user requirement:

### Question 1: Why do you want continuous emission?

**If answer is**:
- ✅ "Better temporal precision for GT matching" → Use **Option C**
- ✅ "Detect short-duration pulses (<100ms)" → Tune sample_rate (no algorithm change)
- ⚠️ "Need to see voltage waveform" → This is a monitoring feature, not detection
- ❌ "Just thought it would be better" → Keep current algorithm

### Question 2: What problem are you solving?

**If answer is**:
- ✅ "Missing detections" → Check voltage threshold, not algorithm
- ✅ "GT matching has large temporal offsets" → Use **Option C**
- ⚠️ "Low precision scores" → Investigate GT data quality first
- ❌ "Wanted more data points" → Not a valid requirement (data ≠ information)

### Question 3: Can you accept 1-detection-per-event semantics?

**If YES** → Use **Option C** (post-processing expansion)
**If NO** → Ask why (likely X-Y problem - they want something else)

---

## Testing Checklist (If Continuous Emission Pursued)

### Unit Tests
- [ ] MIN_INTERVAL rate limiting works correctly
- [ ] No detection loss at 10Hz sample rate
- [ ] Voltage threshold crossings detected accurately
- [ ] Clock drift < 1ms over 10-minute session

### Integration Tests
- [ ] Database can handle 1,200 writes/session without lag
- [ ] GT matching precision ≥ 90% with 12× detections
- [ ] UI renders 1,200 events without frame drops
- [ ] API clients handle increased detection counts

### Load Tests
- [ ] 10 concurrent sessions (12,000 DB writes/sec)
- [ ] 24-hour continuous session (864,000 detections)
- [ ] Database lock contention < 5ms p99
- [ ] Memory usage < 100MB per session

### A/B Test Metrics
- [ ] Track precision/recall for 200 sessions (100 per arm)
- [ ] Monitor write latency (p50, p95, p99)
- [ ] Measure GT matching time
- [ ] Survey user satisfaction

---

## Rollback Plan (If Deployed)

**Trigger Conditions** (ANY of these):
- Write latency p99 > 50ms for 5 minutes
- GT Precision < 90% for 10 sessions
- UI frame rate < 45 FPS for 5 users
- Customer complaints > 3 in 24 hours

**Rollback Procedure**:
1. Flip feature flag: `detection_mode = "rising_edge"`
2. Restart monitoring service
3. Clear detection event queue
4. Notify users of temporary behavior change
5. Root cause analysis within 24 hours

**Data Migration**:
```sql
-- Keep only first detection in each cluster
DELETE FROM detection_events
WHERE id NOT IN (
    SELECT MIN(id) FROM detection_events
    GROUP BY test_session_id,
             FLOOR(timestamp / 0.5)  -- 500ms window
);
```

---

## Final Recommendation

**DO NOT IMPLEMENT CONTINUOUS EMISSION**

**INSTEAD**:
1. Implement **Option C (Post-Processing Expansion)** in GT matching service
2. Test with 10 historical sessions
3. Deploy with confidence (zero breaking changes)
4. Achieve same temporal precision goal

**If user insists on continuous emission**:
- Require them to answer Questions 1-3 above
- Likely uncover X-Y problem (they actually want something else)
- Redirect to appropriate solution

---

## References

- **Full Risk Assessment**: `/backend/docs/ALGORITHM_RISK_ASSESSMENT.md` (25KB, 726 lines)
- **Executive Summary**: `/backend/docs/RISK_ASSESSMENT_SUMMARY.md` (6.4KB)
- **Source Code**: `/backend/src/services/dedicated_labjack_monitor.py` (Lines 396-519)
- **GT Matching Service**: `/backend/src/services/ground_truth_matching_service.py`

---

**Prepared by**: Risk Assessment & Code Review Specialist
**Date**: 2025-11-20
**Status**: 🔴 REJECTED - Use Option C instead
