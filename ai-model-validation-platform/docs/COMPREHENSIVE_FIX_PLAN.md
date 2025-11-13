# Comprehensive Fix Plan - All Issues Master Document
**Generated**: 2025-11-05
**Status**: 🔴 CRITICAL BUGS IDENTIFIED - ACTION REQUIRED
**Total Issues**: 8 Critical, 12 High, 7 Medium, 5 Low

---

## 📋 Executive Summary

This master plan consolidates **ALL findings from 10+ agent analysis reports** into a single actionable fix strategy. The platform has **8 CRITICAL bugs** preventing accurate test results display and data integrity.

### Critical Path Issues (Must Fix First)
1. **Frame clamping bug** - All detections after video end shown as "aligned" (100% false positive)
2. **Video assignment bug** - 51 detections assigned to wrong video (19% data corruption)
3. **Field name mismatch** - Backend returns `ground_truth_metrics`, frontend expects `ground_truth_comparison`
4. **Video dropdown broken** - Reading from empty `sequenceResults` instead of populated `perVideoSummaries`
5. **Frame 120 bunching** - Timeline visualization shows all late detections at frame 119

### Current System State
- ✅ Backend API: 100% correct, no changes needed
- ❌ Frontend Display: Multiple critical bugs in data access and visualization
- ❌ Data Integrity: 19% of detections have wrong video_id in database
- ⚠️ Ground Truth Matching: 0% TP rate (algorithm issue, separate from display bugs)

---

## 🎯 Complete Bug Inventory

### CRITICAL (8 Bugs) - System Breaking

| ID | Bug | Impact | Component | Lines |
|----|-----|--------|-----------|-------|
| C1 | Frame clamping causes false 100% alignment | All detections >video end marked "aligned" | FrameCorrelationTimeline.tsx | 82-86 |
| C2 | Video assignment logic broken | 51 detections (19%) assigned to wrong video | Backend detection service | N/A |
| C3 | Field name mismatch (ground_truth_metrics) | F1 score shows 0%, GT cards hidden | HILResults.tsx | 655-677 |
| C4 | Video dropdown reads wrong data source | Dropdown shows no options | HILResults.tsx | 1250 |
| C5 | aggregatedMetrics returns null | Entire GT section hidden | HILResults.tsx | 1087 |
| C6 | Frame bunching at Frame 119 | Timeline shows incorrect distribution | FrameCorrelationTimeline.tsx | 82-86 |
| C7 | Detection timestamp vs frame mismatch | Shows 4.958s instead of 6.000s | FrameCorrelationTimeline.tsx | 371-374 |
| C8 | Video timing window incorrect | 9.143s gap between expected and actual | Backend sequence_metadata | N/A |

### HIGH Priority (12 Bugs) - Data Accuracy

| ID | Bug | Impact | Component | Lines |
|----|-----|--------|-----------|-------|
| H1 | Video status always "pending" | Pass/fail not calculated from metrics | Backend API response | N/A |
| H2 | Out-of-bounds detections not flagged | No way to identify post-video detections | FrameCorrelationTimeline.tsx | 178-183 |
| H3 | Frame validation threshold too permissive | Allows 150% overshoot but still clamps | FrameCorrelationTimeline.tsx | 163-166 |
| H4 | Multiple field name variations | 3 different names for same data | HILResults.tsx | Multiple |
| H5 | Normalization doesn't map GT metrics | ground_truth_metrics not normalized | hilResultsNormalization.ts | 497-576 |
| H6 | Detection count mismatch in metadata | DB=268, Metadata=183 (85 missing) | Backend sequence_metadata | N/A |
| H7 | Detections before video start | 34 detections 9s before video window | Backend timing logic | N/A |
| H8 | Video dropdown selection logic | Uses sequenceResults instead of perVideoSummaries | HILResults.tsx | 1242 |
| H9 | Frame-based vs time-based latency conflict | Two different latency calculations | FrameCorrelationTimeline.tsx | 268-279 |
| H10 | Video transition gap handling | 381ms gap not properly handled | Backend detection assignment | N/A |
| H11 | Detection density anomaly | Video1=42.9 det/s, Video2=10.1 det/s | Backend detection capture | N/A |
| H12 | Timeline display uses clamped frames | Shows Frame 119 instead of actual frame | FrameCorrelationTimeline.tsx | 519-530 |

### MEDIUM Priority (7 Bugs) - UX Issues

| ID | Bug | Impact | Component | Lines |
|----|-----|--------|-----------|-------|
| M1 | No tooltip explaining frame capping | Users confused by Frame 119 limit | FrameCorrelationTimeline.tsx | 519-530 |
| M2 | Infinite loop risk in useEffect | Potential performance degradation | HILResults.tsx | Multiple |
| M3 | XSS vulnerability in video URLs | Unsanitized URLs from API | HILResults.tsx | N/A |
| M4 | WebSocket subscription churn | Creates/destroys subscriptions repeatedly | HILResults.tsx | N/A |
| M5 | Detection table missing frame column | Users can't see frame numbers | DetectionTableRow.tsx | 5-24 |
| M6 | Video metadata inconsistency | 3 timing sources not synchronized | Backend/Frontend | Multiple |
| M7 | Ground truth access path inconsistency | Aggregation uses wrong field vs per-video display | HILResults.tsx | 655, 1343 |

### LOW Priority (5 Bugs) - Minor Issues

| ID | Bug | Impact | Component | Lines |
|----|-----|--------|-----------|-------|
| L1 | Frame offset calculation precision | Uses absolute instead of signed offset | FrameCorrelationTimeline.tsx | 268-279 |
| L2 | Video-ended logic only for GT | Detections don't get marked as video_ended | FrameCorrelationTimeline.tsx | 178-183 |
| L3 | Missing detection window parameter | No separate config for detection vs video duration | FrameCorrelationTimeline.tsx | N/A |
| L4 | Statistics exclude out-of-bounds | Alignment rate calculation needs updating | FrameCorrelationTimeline.tsx | 326-349 |
| L5 | Performance: O(n*m) GT matching | Could use binary search for speed | FrameCorrelationTimeline.tsx | 561-568 |

---

## 🔧 Fix Execution Plan

### Phase 1: Critical Data Integrity (Day 1) - BLOCKING

**Priority**: HIGHEST - Prevents all accurate test results

#### Fix 1.1: Remove Frame Clamping (C1, C6, C7)
**Impact**: 70 detections currently showing as "aligned" when they're actually out of bounds

**File**: `/frontend/src/components/FrameCorrelationTimeline.tsx`

**Changes**:
```typescript
// Lines 82-86: REMOVE clampFrame, replace with validation
const validateFrame = (frame: number): number | null => {
  if (!Number.isFinite(frame)) return null;
  if (frame < 0) return null;
  return Math.floor(frame);
};

const getFrameStatus = (frame: number | null, totalFrames: number | undefined): 'valid' | 'out_of_bounds' => {
  if (frame === null) return 'out_of_bounds';
  if (totalFrames !== undefined && frame >= totalFrames) return 'out_of_bounds';
  return 'valid';
};
```

**Usage Update** (Lines 163-167, 198-206):
```typescript
// Ground Truth
const gtFrameNumber = validateFrame(gtFrameRaw);
const gtFrameStatus = getFrameStatus(gtFrameNumber, totalFrames);

// Detections
const detectionFrameNumber = validateFrame(detectionFrameRaw);
const detectionFrameStatus = getFrameStatus(detectionFrameNumber, totalFrames);

if (detectionFrameStatus === 'out_of_bounds') {
  correlationStatus = 'out_of_bounds';
}
```

**Testing**: Verify detections at 6.75s no longer show as Frame 119

**Time**: 3-4 hours (implementation + testing)

---

#### Fix 1.2: Fix Video Assignment Logic (C2)
**Impact**: 51 detections (19%) currently assigned to wrong video

**File**: Backend detection service (needs investigation)

**Required Investigation**:
1. Find where `video_id` is set when storing detection events
2. Verify it checks current video in sequence vs timestamp
3. Add timing window validation

**Expected Code Location**:
```python
# Backend: labjack_detection_service.py or similar
def assign_video_id(labjack_timestamp, session):
    if session.sequence_metadata:
        for video in session.sequence_metadata['video_timing'].values():
            if video['started_at'] <= labjack_timestamp <= video['ended_at']:
                return video['video_id']
    return session.video_id  # fallback
```

**Migration Script**:
```sql
-- Reassign detections to correct video based on timestamp
UPDATE detection_events
SET video_id = '550e3cf8-2755-42df-8c3c-041300735f93'
WHERE test_session_id = '71976ec4-b37d-4b19-8df7-11fefcb9bba7'
AND labjack_timestamp >= 1762191683.453
AND labjack_timestamp <= 1762191688.610;
```

**Testing**: Verify new sessions assign detections to correct video in real-time

**Time**: 4-6 hours (investigation + implementation + migration)

---

#### Fix 1.3: Field Name Normalization (C3, H4, H5)
**Impact**: F1 score, precision, recall all show incorrect values

**File 1**: `/frontend/src/pages/HILResults.tsx`

**Lines 655-657**: Add ground_truth_metrics fallback
```typescript
const totalTP = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.true_positives ??
         v.groundTruthComparison?.truePositives ??
         v.ground_truth_metrics?.true_positives ?? // ADD THIS
         0), 0);

const totalFP = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.false_positives ??
         v.groundTruthComparison?.falsePositives ??
         v.ground_truth_metrics?.false_positives ?? // ADD THIS
         0), 0);

const totalFN = videos.reduce((sum, v) =>
  sum + (v.ground_truth_comparison?.false_negatives ??
         v.groundTruthComparison?.falseNegatives ??
         v.ground_truth_metrics?.false_negatives ?? // ADD THIS
         0), 0);
```

**Lines 672-677**: Update total ground truth calculation
```typescript
const totalGroundTruthEvents = videos.reduce((sum, v) => {
  const currentId = v.videoId ?? v.video_id ?? v.id;
  const mapCount = currentId ? (videoGroundTruthMap[currentId]?.length ?? 0) : 0;
  const fallback = v.ground_truth_events_available ??
                   v.groundTruthEventsAvailable ??
                   v.ground_truth_count ??
                   v.groundTruthCount ??
                   v.ground_truth_metrics?.total_ground_truth ?? // ADD THIS
                   0;
  return sum + (mapCount || fallback);
}, 0);
```

**File 2**: `/frontend/src/utils/hilResultsNormalization.ts`

**Lines 497-576**: Add ground truth normalization
```typescript
const normalized: PerVideoResult = {
  ...(video ?? {}),

  // ADD: Ground truth metrics normalization
  ground_truth_metrics: video?.ground_truth_metrics ?? video?.groundTruthMetrics ?? {},
  groundTruthMetrics: video?.groundTruthMetrics ?? video?.ground_truth_metrics ?? {},
  ground_truth_comparison: video?.ground_truth_comparison ?? video?.ground_truth_metrics ?? {},
  groundTruthComparison: video?.groundTruthComparison ?? video?.ground_truth_metrics ?? {},

  // ... rest of fields
};
```

**Testing**: Verify F1 score shows actual values (0% for session c511302e)

**Time**: 2-3 hours

---

#### Fix 1.4: Video Dropdown Data Source (C4, H8)
**Impact**: Video selector completely broken

**File**: `/frontend/src/pages/HILResults.tsx`

**Line 1242**: Fix video selection logic
```typescript
// BEFORE
const videoIndex = sequenceResults?.per_video_results?.findIndex(...)

// AFTER
const videoIndex = perVideoSummaries?.findIndex(
  (v) => (v.video_id ?? v.videoId) === newVideoId
) ?? 0;
```

**Line 1250**: Fix dropdown options
```typescript
// BEFORE
{sequenceResults?.per_video_results?.map((video, index) => {

// AFTER
{perVideoSummaries?.map((video, index) => {
```

**Testing**: Verify dropdown shows 2 video options with filenames

**Time**: 1 hour (ALREADY FIXED in previous session)

---

### Phase 2: Display & UX Fixes (Day 2) - HIGH PRIORITY

#### Fix 2.1: Add Out-of-Bounds Status (H2, L2)
**File**: `/frontend/src/components/FrameCorrelationTimeline.tsx`

**Type Definition**:
```typescript
type CorrelationStatus = 'aligned' | 'misaligned' | 'missing' | 'video_ended' | 'out_of_bounds';
```

**Apply to Detections** (after line 280):
```typescript
if (detectionFrameStatus === 'out_of_bounds') {
  correlationStatus = 'out_of_bounds';
} else if (closestGT) {
  // existing correlation logic
}
```

**Update Statistics** (lines 326-349):
```typescript
const outOfBounds = detections.filter(e => e.correlation_status === 'out_of_bounds').length;
const validDetections = detections.length - outOfBounds;
const alignmentRate = validDetections > 0 ? (aligned / validDetections) * 100 : 0;
```

**Time**: 2-3 hours

---

#### Fix 2.2: Fix Display Time Calculation (C7, H12)
**File**: `/frontend/src/components/FrameCorrelationTimeline.tsx`

**Line 534**: Use actual timestamp instead of frame-derived time
```typescript
// BEFORE
<Typography variant="body2">
  {formatFrameTime(event.frame_number)}
</Typography>

// AFTER
<Typography variant="body2">
  {event.timestamp.toFixed(3)}s
</Typography>
```

**Time**: 1 hour

---

#### Fix 2.3: Add Video Status Calculation (H1)
**Option A (Backend - Recommended)**:
```python
# Backend: Update video_status based on metrics
if pass_rate >= 95:
    video_status = "pass"
elif pass_rate < 80:
    video_status = "fail"
else:
    video_status = "partial"
```

**Option B (Frontend - Workaround)**:
```typescript
// HILResults.tsx: Calculate from metrics
const videosPassed = videos.filter(v => {
  const passRate = v.pass_rate ?? v.passRate ?? v.pass_rate_percent ?? 0;
  return passRate >= 95;
}).length;
```

**Time**: 2 hours (backend) OR 1 hour (frontend workaround)

---

#### Fix 2.4: Add Frame Column to Detection Table (M5)
**File**: `/frontend/src/components/DetectionTableRow.tsx`

**Interface Update** (lines 5-24):
```typescript
interface DetectionTableRowProps {
  detection: {
    frame_number?: number;  // ADD
    video_frame_number?: number;  // ADD
    // ... existing fields
  };
}
```

**Add Column** (after line 120):
```typescript
<TableCell>
  <Typography variant="body2">
    Frame {detection.frame_number || detection.video_frame_number || '—'}
  </Typography>
</TableCell>
```

**Time**: 1-2 hours

---

### Phase 3: Backend Data Quality (Day 3) - MEDIUM PRIORITY

#### Fix 3.1: Video Timing Synchronization (C8, M6)
**Investigation Required**: Reconcile 3 timing sources
1. `video_start_timestamp` (session level): 1762191668.606187
2. `started_at` (metadata): 1762191677.750000
3. Actual first detection: 1762191668.607250

**Difference**: 9.143 seconds gap

**Possible Causes**:
- Videos loading/buffering before playback
- Timing metadata created post-hoc
- UI events vs hardware events mismatch

**Fix Approach**:
- Use LabJack timestamp as source of truth
- Update `started_at` to match first detection time
- Or: Add separate `detection_start_time` field

**Time**: 4-6 hours (investigation + implementation)

---

#### Fix 3.2: Metadata Count Sync (H6)
**Backend**: Update detection count in sequence_metadata when detections stored

```python
# Update sequence_metadata after each detection
session.sequence_metadata['video_timing'][video_id]['detection_count'] = \
    db.query(DetectionEvent).filter_by(video_id=video_id).count()
```

**Time**: 2 hours

---

### Phase 4: Performance & Optimization (Day 4) - LOW PRIORITY

#### Fix 4.1: Binary Search for GT Matching (L5)
**File**: `/frontend/src/components/FrameCorrelationTimeline.tsx`

**Lines 561-568**: Replace O(n*m) with O(n log m)
```typescript
// Sort GTs once
const sortedGTs = [...groundTruthEvents].sort((a, b) => a.frame - b.frame);

// Binary search for closest
const closestGT = findClosestGT(detectionFrame, sortedGTs);
```

**Time**: 2-3 hours

---

#### Fix 4.2: WebSocket Subscription Optimization (M4)
**File**: `/frontend/src/pages/HILResults.tsx`

**Issue**: Creates/destroys subscriptions on every render

**Fix**: Memoize subscription logic
```typescript
const subscription = useMemo(() => {
  if (!sessionId) return null;
  return websocketService.subscribe(...);
}, [sessionId]); // Only recreate when sessionId changes
```

**Time**: 1-2 hours

---

#### Fix 4.3: XSS Vulnerability (M3)
**File**: `/frontend/src/pages/HILResults.tsx`

**Sanitize video URLs**:
```typescript
import DOMPurify from 'dompurify';

const sanitizedUrl = DOMPurify.sanitize(videoUrl);
```

**Time**: 1 hour

---

## 📊 Fix Dependencies & Execution Order

### Critical Path (Sequential)
```
Fix 1.1 (Frame clamping)
  ↓
Fix 1.2 (Video assignment) ← Requires backend investigation
  ↓
Fix 1.3 (Field names) ← Can run in parallel with 1.2
  ↓
Fix 2.1 (Out-of-bounds status) ← Depends on 1.1
```

### Parallel Tracks
```
Track A: Display Fixes
  Fix 2.2 (Display time)
  Fix 2.4 (Frame column)
  Fix 4.1 (Binary search)

Track B: Backend Fixes
  Fix 1.2 (Video assignment)
  Fix 3.1 (Timing sync)
  Fix 3.2 (Metadata sync)

Track C: UX Improvements
  Fix 2.3 (Video status)
  Fix 4.2 (WebSocket)
  Fix 4.3 (XSS)
```

---

## 🧪 Testing Strategy

### Unit Tests Required
1. **Frame validation logic** (Fix 1.1)
   - Test frame < 0 → returns null
   - Test frame >= totalFrames → returns 'out_of_bounds'
   - Test valid frame → returns frame number

2. **Video assignment logic** (Fix 1.2)
   - Test detection within video window → correct video_id
   - Test detection during transition gap → correct handling
   - Test detection before/after all videos → fallback behavior

3. **Field name normalization** (Fix 1.3)
   - Test all 3 field name variants
   - Test missing data → defaults to 0
   - Test normalization preserves all variants

### Integration Tests Required
1. **Multi-video session end-to-end**
   - Create session with 2 videos
   - Verify detections assigned to correct video
   - Check timing windows match detection ranges
   - Validate per-video metrics

2. **Frame correlation accuracy**
   - Test detections within video bounds → correct correlation
   - Test detections beyond video end → marked 'out_of_bounds'
   - Verify alignment rates exclude out-of-bounds

3. **Frontend data display**
   - Verify dropdown shows all videos
   - Check F1 score section renders
   - Validate detection table shows correct data
   - Test video selection updates display

### Test Cases by Session

**Session 71976ec4** (Video assignment bug):
- [ ] Detections 1-217 → Video 1
- [ ] Detections 218-268 → Video 2
- [ ] No detections with wrong video_id
- [ ] Metadata counts match DB

**Session c511302e** (Field name bug):
- [ ] F1 score shows 0%
- [ ] GT cards show: 0 TP, 193 FP, 514 FN
- [ ] Video dropdown shows 2 options
- [ ] Per-video metrics display correctly

---

## ⏱️ Time Estimates

### Phase 1: Critical Fixes (Day 1)
- Fix 1.1: Frame clamping → 3-4 hours
- Fix 1.2: Video assignment → 4-6 hours
- Fix 1.3: Field names → 2-3 hours
- Fix 1.4: Video dropdown → 1 hour (DONE)
- **Subtotal**: 10-14 hours

### Phase 2: Display Fixes (Day 2)
- Fix 2.1: Out-of-bounds status → 2-3 hours
- Fix 2.2: Display time → 1 hour
- Fix 2.3: Video status → 2 hours
- Fix 2.4: Frame column → 1-2 hours
- **Subtotal**: 6-8 hours

### Phase 3: Backend Quality (Day 3)
- Fix 3.1: Timing sync → 4-6 hours
- Fix 3.2: Metadata sync → 2 hours
- **Subtotal**: 6-8 hours

### Phase 4: Performance (Day 4)
- Fix 4.1: Binary search → 2-3 hours
- Fix 4.2: WebSocket → 1-2 hours
- Fix 4.3: XSS → 1 hour
- **Subtotal**: 4-6 hours

### Testing & Validation
- Unit tests → 4-6 hours
- Integration tests → 6-8 hours
- Manual testing → 4 hours
- **Subtotal**: 14-18 hours

### **TOTAL ESTIMATE**: 40-54 hours (5-7 business days)

---

## 🎯 Risk Assessment

### High Risk Fixes (Could Break Existing Functionality)

| Fix | Risk | Mitigation |
|-----|------|------------|
| Frame clamping removal | May affect existing saved results | Add feature flag, test with historical data |
| Video assignment logic | Could break single-video sessions | Add fallback to session.video_id |
| Field name changes | May break other components | Update all access patterns consistently |

### Backward Compatibility Issues

1. **Database Migration** (Fix 1.2)
   - Risk: Existing sessions have wrong video_id
   - Solution: Run migration script on all multi-video sessions
   - Rollback: Keep original video_id in backup column

2. **API Response Changes** (Fix 2.3)
   - Risk: Frontend expects "pending", backend changes to "pass"/"fail"
   - Solution: Support both old and new status values
   - Rollback: Backend can revert to always "pending"

3. **Frontend Bundle Changes** (All fixes)
   - Risk: Cached old version in browsers
   - Solution: Force cache bust with build version
   - Rollback: Deploy previous bundle version

### Deployment Strategy

**Option A: Big Bang (High Risk)**
- Deploy all fixes at once
- Pros: Fast, clean cutover
- Cons: Hard to isolate issues if something breaks

**Option B: Incremental (Recommended)**
1. Day 1: Deploy Phase 1 (critical fixes) + cache bust
2. Day 2: Monitor for 24h, deploy Phase 2 if stable
3. Day 3: Deploy Phase 3 (backend quality)
4. Day 4: Deploy Phase 4 (performance)

**Rollback Plan**:
- Keep previous 3 deployments in artifact storage
- Document exact commit hash for each deployment
- Test rollback procedure before first deployment

---

## ✅ Verification Plan

### Automated Verification
```bash
# Frontend tests
npm run test:unit
npm run test:integration
npm run test:e2e

# Backend tests
pytest backend/tests/
pytest backend/tests/test_video_assignment.py
pytest backend/tests/test_ground_truth_matching.py

# API contract tests
npm run test:api-contract
```

### Manual Verification Checklist

**For Each Fix Applied**:
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual test in dev environment
- [ ] Code review completed
- [ ] Documentation updated
- [ ] Changelog entry added

**Before Production Deploy**:
- [ ] All tests green on CI
- [ ] Staging environment tested
- [ ] Performance metrics acceptable
- [ ] No console errors in browser
- [ ] Database migration dry run successful
- [ ] Rollback plan tested

**After Production Deploy**:
- [ ] Monitor error rates (first 1 hour)
- [ ] Check user session metrics
- [ ] Verify test results display correctly
- [ ] Validate detection assignment accuracy
- [ ] Review WebSocket connection stability

### Metrics to Track

**Pre-Fix Baseline**:
- Frame correlation accuracy: 0% (false 100%)
- Video assignment accuracy: 81% (19% wrong)
- F1 score display: 0% (hidden)
- Video dropdown functionality: 0% (broken)

**Post-Fix Target**:
- Frame correlation accuracy: >95%
- Video assignment accuracy: 100%
- F1 score display: 100% (visible with correct data)
- Video dropdown functionality: 100%

---

## 📋 Deliverables

### Code Changes
- [ ] Frontend fixes (15 files modified)
- [ ] Backend fixes (5 files modified)
- [ ] Database migration script
- [ ] Unit test suite (20+ tests)
- [ ] Integration test suite (10+ tests)

### Documentation
- [ ] Fix implementation guide (this document)
- [ ] API changes documentation
- [ ] Database schema changes log
- [ ] User-facing changelog
- [ ] Developer handoff notes

### Deployment Artifacts
- [ ] Frontend production build
- [ ] Backend deployment package
- [ ] Database migration SQL
- [ ] Rollback scripts
- [ ] Deployment runbook

---

## 🚀 Action Items

### Immediate (Today)
1. Review this comprehensive fix plan with team
2. Prioritize which fixes are blocking (all Phase 1)
3. Assign developers to parallel tracks
4. Set up test environments for validation

### This Week
1. Implement Phase 1 critical fixes (Day 1)
2. Run migration script on dev database
3. Complete manual testing of all Phase 1 fixes
4. Deploy to staging environment
5. Begin Phase 2 implementation

### Next Week
1. Deploy Phase 1 to production (after staging validation)
2. Complete Phase 2 & 3 implementation
3. Full regression testing
4. Deploy Phase 2 & 3 to production

### Next Sprint
1. Implement Phase 4 performance optimizations
2. Add comprehensive monitoring
3. Document lessons learned
4. Create preventive measures for future

---

## 📚 Related Documents

**Agent Analysis Reports** (10+ documents):
1. Frame Correlation Analysis (700+ lines)
2. Frontend Display Verification
3. Session 71976ec4 Timing Analysis
4. F1 Score Missing Root Cause
5. Session c511302e Complete Analysis
6. Comprehensive Fix Summary (Previous)
7. Code Analyzer Report
8. Data Flow Analysis (Reviewer)
9. API Verification (Backend-Dev)
10. Feature Inventory (Researcher)

**All reports available in**:
- `/frontend/docs/agents/`
- `/backend/docs/agents/`
- `/docs/`

---

## 🎓 Lessons Learned

### Why These Bugs Happened
1. **Frame clamping**: Defensive programming gone wrong - clamping hid the real issue
2. **Video assignment**: Real-time state not tracked, relied on static session.video_id
3. **Field names**: API contract changed without frontend update
4. **Video dropdown**: Multiple data sources, unclear which is canonical

### Prevention for Future
1. ✅ Add TypeScript interfaces for ALL API responses
2. ✅ Create API contract tests (fail on field name changes)
3. ✅ Use single data normalization layer
4. ✅ Add runtime validation for critical fields
5. ✅ Require integration tests for multi-entity features
6. ✅ Document timing synchronization architecture
7. ✅ Add monitoring for data integrity issues

---

## 🏁 Success Criteria

This fix plan is **COMPLETE** when:

✅ **Data Integrity**
- 100% of detections assigned to correct video
- 0% false alignment due to frame clamping
- All timing windows match actual detection ranges

✅ **Display Accuracy**
- F1 score shows actual values (not 0%)
- Video dropdown works with correct options
- Timeline shows true detection distribution

✅ **System Stability**
- No console errors
- WebSocket connections stable
- Page load time < 2 seconds
- No infinite loops or memory leaks

✅ **User Experience**
- All 14 features working (per Feature Inventory)
- Test results trusted by users
- Ground truth matching accurate

---

**Document Status**: ✅ READY FOR IMPLEMENTATION
**Next Step**: Team review & assignment of fix ownership
**Priority**: 🔴 CRITICAL - Blocking accurate test results

---

**Generated by**: Research Agent (Multi-Agent Analysis Compilation)
**Based on**: 10+ agent analysis reports, 2000+ lines of findings
**Last Updated**: 2025-11-05
