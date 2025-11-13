# Fix Dependency Graph & Quick Reference

## Visual Dependency Map

```
                    PHASE 1: CRITICAL (Day 1)
                    ========================

        ┌─────────────────────────────────────┐
        │  Fix 1.1: Frame Clamping Removal    │
        │  Priority: CRITICAL                  │
        │  Time: 3-4 hours                     │
        │  Component: FrameCorrelationTimeline │
        └────────────┬────────────────────────┘
                     │
                     ├──────────────────────────┐
                     ↓                          ↓
        ┌─────────────────────────┐  ┌──────────────────────┐
        │  Fix 2.1: Out-of-Bounds │  │  Fix 2.2: Display   │
        │  Status                 │  │  Time Calculation   │
        │  Time: 2-3 hours        │  │  Time: 1 hour       │
        └─────────────────────────┘  └──────────────────────┘

        ┌─────────────────────────────────────┐
        │  Fix 1.2: Video Assignment Logic    │◄─── BLOCKING
        │  Priority: CRITICAL                  │
        │  Time: 4-6 hours                     │
        │  Component: Backend Detection Service│
        │  + Database Migration Required       │
        └─────────────────────────────────────┘

        ┌─────────────────────────────────────┐
        │  Fix 1.3: Field Name Normalization  │◄─── PARALLEL
        │  Priority: CRITICAL                  │     with 1.2
        │  Time: 2-3 hours                     │
        │  Component: HILResults.tsx           │
        └──────────────┬──────────────────────┘
                       │
                       ↓
        ┌─────────────────────────────────────┐
        │  Fix 1.4: Video Dropdown Fix        │
        │  Priority: CRITICAL                  │
        │  Time: 1 hour (ALREADY DONE)         │
        │  Component: HILResults.tsx           │
        └─────────────────────────────────────┘


                    PHASE 2: DISPLAY (Day 2)
                    ========================

        ┌─────────────────────────────────────┐
        │  Fix 2.3: Video Status Calculation  │
        │  Priority: HIGH                      │
        │  Time: 2 hours                       │
        │  Component: Backend OR Frontend      │
        └─────────────────────────────────────┘

        ┌─────────────────────────────────────┐
        │  Fix 2.4: Frame Column in Table     │
        │  Priority: MEDIUM                    │
        │  Time: 1-2 hours                     │
        │  Component: DetectionTableRow.tsx    │
        └─────────────────────────────────────┘


                    PHASE 3: BACKEND (Day 3)
                    ========================

        ┌─────────────────────────────────────┐
        │  Fix 3.1: Timing Synchronization    │◄─── INVESTIGATION
        │  Priority: HIGH                      │     REQUIRED
        │  Time: 4-6 hours                     │
        │  Component: Backend Timing Logic     │
        └──────────────┬──────────────────────┘
                       │
                       ↓
        ┌─────────────────────────────────────┐
        │  Fix 3.2: Metadata Count Sync       │
        │  Priority: MEDIUM                    │
        │  Time: 2 hours                       │
        │  Component: Backend Detection Storage│
        └─────────────────────────────────────┘


                    PHASE 4: PERFORMANCE (Day 4)
                    =============================

        ┌─────────────────────────────────────┐
        │  Fix 4.1: Binary Search GT Matching │
        │  Priority: LOW                       │
        │  Time: 2-3 hours                     │
        │  Component: FrameCorrelationTimeline │
        └─────────────────────────────────────┘

        ┌─────────────────────────────────────┐
        │  Fix 4.2: WebSocket Optimization    │
        │  Priority: MEDIUM                    │
        │  Time: 1-2 hours                     │
        │  Component: HILResults.tsx           │
        └─────────────────────────────────────┘

        ┌─────────────────────────────────────┐
        │  Fix 4.3: XSS Sanitization          │
        │  Priority: MEDIUM                    │
        │  Time: 1 hour                        │
        │  Component: HILResults.tsx           │
        └─────────────────────────────────────┘
```

---

## Critical Path Analysis

**Longest Sequential Path**: 17-23 hours
```
Fix 1.1 (4h) → Fix 2.1 (3h) → Fix 1.2 (6h) → Fix 3.1 (6h) → Fix 4.1 (3h)
```

**Parallel Execution Optimized**: 26-34 hours
```
Day 1 (8-10h):
  Track A: Fix 1.1 + Fix 2.1 + Fix 2.2 (6-8h)
  Track B: Fix 1.2 (backend investigation + implementation) (4-6h)
  Track C: Fix 1.3 + Fix 1.4 (3-4h)

Day 2 (6-8h):
  Track A: Fix 2.3 + Fix 2.4 (3-4h)
  Track B: Testing Phase 1 fixes (3-4h)

Day 3 (6-8h):
  Track A: Fix 3.1 (timing investigation) (4-6h)
  Track B: Fix 3.2 (metadata sync) (2h)

Day 4 (4-6h):
  Track A: Fix 4.1 + Fix 4.2 + Fix 4.3 (4-6h)
```

---

## Quick Fix Lookup Table

| Code | Component | Issue | Fix Time | Blocking? |
|------|-----------|-------|----------|-----------|
| C1 | FrameCorrelationTimeline.tsx:82-86 | Frame clamping | 3-4h | ✅ YES |
| C2 | Backend detection service | Video assignment | 4-6h | ✅ YES |
| C3 | HILResults.tsx:655-677 | Field name mismatch | 2-3h | ✅ YES |
| C4 | HILResults.tsx:1250 | Dropdown data source | 1h | ✅ DONE |
| C5 | HILResults.tsx:1087 | aggregatedMetrics null | 0h | Fixed by C3 |
| C6 | FrameCorrelationTimeline.tsx:82-86 | Frame bunching | 0h | Fixed by C1 |
| C7 | FrameCorrelationTimeline.tsx:371-374 | Timestamp display | 1h | ⚠️ RELATED |
| C8 | Backend sequence_metadata | Timing window | 4-6h | ⚠️ INVESTIGATION |
| H1 | Backend API | Video status | 2h | ❌ NO |
| H2 | FrameCorrelationTimeline.tsx:178-183 | Out-of-bounds flag | 2-3h | ⚠️ DEPENDS C1 |
| H3 | FrameCorrelationTimeline.tsx:163-166 | Frame validation | 0h | Fixed by C1 |
| H4 | HILResults.tsx:multiple | Field variations | 0h | Fixed by C3 |
| H5 | hilResultsNormalization.ts:497-576 | Normalization | 0h | Fixed by C3 |
| H6 | Backend sequence_metadata | Count mismatch | 2h | ❌ NO |
| H7 | Backend timing logic | Early detections | 0h | Fixed by C2 |
| H8 | HILResults.tsx:1242 | Selection logic | 0h | Fixed by C4 |
| H9 | FrameCorrelationTimeline.tsx:268-279 | Latency conflict | 1h | ❌ NO |
| H10 | Backend detection | Transition gap | 0h | Fixed by C2 |
| H11 | Backend detection | Density anomaly | 0h | Data quality |
| H12 | FrameCorrelationTimeline.tsx:519-530 | Timeline display | 0h | Fixed by C1 |
| M1-M7 | Various | UX issues | 1-2h each | ❌ NO |
| L1-L5 | Various | Minor issues | 1-3h each | ❌ NO |

---

## File Modification Summary

### Frontend Files to Modify

| File | Fixes | Lines Modified | Complexity |
|------|-------|----------------|------------|
| FrameCorrelationTimeline.tsx | C1, C6, C7, H2, H12, L1-L5 | 82-86, 163-167, 178-183, 198-206, 268-279, 326-349, 371-374, 519-530 | HIGH |
| HILResults.tsx | C3, C4, C5, H4, H8, M2, M4 | 655-677, 1087, 1242, 1250 | MEDIUM |
| hilResultsNormalization.ts | H5 | 497-576 | LOW |
| DetectionTableRow.tsx | M5 | 5-24, 120 | LOW |

**Total Frontend Files**: 4 files

### Backend Files to Modify

| File | Fixes | Complexity |
|------|-------|------------|
| labjack_detection_service.py (or similar) | C2, H7, H10 | HIGH |
| sequence_metadata handler | C8, H6 | MEDIUM |
| video status calculator | H1 | LOW |
| timing synchronization service | C8 | HIGH |

**Total Backend Files**: 4-5 files

### Database Changes

| Type | Description | Risk |
|------|-------------|------|
| Migration Script | Reassign video_id for 51 detections | MEDIUM |
| Schema Change | None required | NONE |
| Data Cleanup | Update metadata counts | LOW |

---

## Testing Priority Matrix

### Must Test Before Deploy (Blocking)

| Test | Coverage | Time |
|------|----------|------|
| Frame validation logic | C1, C6, H3 | 2h |
| Video assignment accuracy | C2, H7, H10 | 3h |
| Field name normalization | C3, H4, H5 | 2h |
| Multi-video end-to-end | All Phase 1 | 4h |

**Subtotal**: 11 hours

### Should Test Before Deploy (High Value)

| Test | Coverage | Time |
|------|----------|------|
| Out-of-bounds handling | H2, L2 | 1h |
| Display time accuracy | C7, H12 | 1h |
| Video dropdown functionality | C4, H8 | 1h |
| F1 score display | C3, C5 | 1h |

**Subtotal**: 4 hours

### Nice to Test (QA)

| Test | Coverage | Time |
|------|----------|------|
| Performance optimizations | L5, M4 | 2h |
| XSS vulnerability | M3 | 1h |
| WebSocket stability | M4 | 2h |

**Subtotal**: 5 hours

---

## Rollback Decision Tree

```
Deployment Failed?
│
├─ YES → What Failed?
│        │
│        ├─ Frontend Build → Rollback to previous build
│        │                   Time: 5 minutes
│        │
│        ├─ Backend API → Check error type
│        │               │
│        │               ├─ Syntax Error → Rollback code
│        │               │                  Time: 10 minutes
│        │               │
│        │               └─ Data Error → Rollback migration
│        │                               Time: 20 minutes
│        │
│        └─ Database Migration → Run rollback script
│                                Time: 15 minutes
│
└─ NO → Monitor for 1 hour
         │
         ├─ Errors Increased? → Rollback + investigate
         │
         └─ All Good → Mark deployment successful
```

---

## Developer Assignment Recommendations

### Track A: Frontend Display (1 Developer)
**Skills**: React, TypeScript, UI/UX
**Fixes**: C1, C6, C7, H2, H12, M5, L1-L5
**Time**: 12-16 hours
**Files**: FrameCorrelationTimeline.tsx, DetectionTableRow.tsx

### Track B: Backend Data (1 Developer)
**Skills**: Python, FastAPI, Database
**Fixes**: C2, C8, H6, H7, H10, H11
**Time**: 14-18 hours
**Files**: Detection service, timing logic, metadata handler

### Track C: Frontend Integration (1 Developer)
**Skills**: React, TypeScript, Data Flow
**Fixes**: C3, C4, C5, H1, H4, H5, H8
**Time**: 8-10 hours
**Files**: HILResults.tsx, hilResultsNormalization.ts

### Track D: Performance & Security (1 Developer)
**Skills**: React optimization, Security
**Fixes**: M3, M4, L5
**Time**: 4-6 hours
**Files**: HILResults.tsx, FrameCorrelationTimeline.tsx

**Total Team Size**: 4 developers (can be 2-3 if time is flexible)

---

## Daily Standup Checklist

### Day 1 Standup
- [ ] Track A: Frame clamping removed?
- [ ] Track B: Video assignment logic identified?
- [ ] Track C: Field name fixes deployed?
- [ ] Blockers: Any investigation taking longer than expected?

### Day 2 Standup
- [ ] Track A: Display fixes complete?
- [ ] Track B: Migration script tested?
- [ ] Track C: Integration tests passing?
- [ ] Ready for staging deploy?

### Day 3 Standup
- [ ] Phase 1 deployed to staging?
- [ ] Any production incidents?
- [ ] Track B: Timing sync investigation complete?
- [ ] Ready for production deploy?

### Day 4 Standup
- [ ] Production deploy successful?
- [ ] All metrics improved?
- [ ] Performance optimizations ready?
- [ ] Documentation updated?

---

## Success Metrics Dashboard

### Before Fix (Baseline)
```
Frame Correlation Accuracy:   0% (false 100% due to clamping)
Video Assignment Accuracy:   81% (19% wrong video_id)
F1 Score Display:             0% (hidden due to field mismatch)
Video Dropdown:               0% (broken)
Detection Table Accuracy:   100% (but missing frame column)
Timeline Visualization:      20% (bunching at Frame 119)
```

### After Phase 1 (Target)
```
Frame Correlation Accuracy:  >95% (no false alignment)
Video Assignment Accuracy:   100% (correct video_id)
F1 Score Display:            100% (visible with correct data)
Video Dropdown:              100% (working)
Detection Table Accuracy:    100% (all data correct)
Timeline Visualization:      100% (accurate distribution)
```

### After All Phases (Goal)
```
All Above Metrics:           100%
Page Load Time:              <2 seconds
WebSocket Stability:        >99.9% uptime
XSS Vulnerabilities:         0
Code Performance:           <100ms render time
Test Coverage:              >80%
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Status**: Ready for Team Review
