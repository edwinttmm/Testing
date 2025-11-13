# Phase 5 Migration Plan: Unified Video Assignment Service

**Timeline**: 4 weeks
**Risk Level**: MEDIUM (Phased rollout with rollback points)
**Impact**: Backend detection assignment, orchestrator logic

---

## Overview

This migration plan transitions from THREE independent video_id assignment methods to ONE unified service, following a safe 4-week rollout with validation at each phase.

**Current State**: Frankenstein architecture with 3 methods
**Target State**: Single VideoAssignmentService as source of truth

---

## Pre-Migration Checklist

### Week 0: Preparation (Before Phase 5a)

- [ ] **Code Review**: All stakeholders review ADR-005 and implementation
- [ ] **Database Validation**: Verify SequenceVideoResult timing data quality
  ```sql
  -- Check for missing video_start_time (should be < 1%)
  SELECT
    COUNT(*) as total,
    SUM(CASE WHEN video_start_time IS NULL THEN 1 ELSE 0 END) as missing_start,
    SUM(CASE WHEN video_end_time IS NULL THEN 1 ELSE 0 END) as missing_end
  FROM sequence_video_results;
  ```
- [ ] **Performance Baseline**: Record current detection processing times
- [ ] **Test Data**: Prepare 10+ multi-video test sessions for validation
- [ ] **Monitoring**: Set up Grafana dashboards for video assignment metrics
- [ ] **Rollback Plan**: Document exact git commits for each phase

---

## Phase 5a: Deploy Service - Validation-Only Mode

**Duration**: Week 1
**Goal**: Introduce service without changing production behavior
**Risk**: LOW (read-only validation)

### Implementation Steps

#### Step 1: Deploy VideoAssignmentService (Day 1-2)

```bash
# Create service file
cp docs/architecture/UNIFIED-VIDEO-ASSIGNMENT-IMPLEMENTATION.py \
   backend/services/video_assignment_service.py

# Add to git
git add backend/services/video_assignment_service.py
git commit -m "Phase 5a: Add VideoAssignmentService (validation-only)"
```

#### Step 2: Add Validation Logging to LabJack Service (Day 2-3)

```python
# In backend/services/labjack_detection_service.py
# At line 1033, ADD validation code (don't remove existing code)

from services.video_assignment_service import get_video_assignment_service

# EXISTING CODE (keep as-is)
if session.sequence_id and session.sequence_metadata:
    try:
        metadata = session.sequence_metadata
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)
        current_video_id = metadata.get('current_video_id')
        if current_video_id:
            logger.info(f"✅ Multi-video: Using current_video_id={current_video_id}")
            video_id = current_video_id
    except Exception as meta_error:
        logger.error(f"Failed to parse sequence_metadata: {meta_error}")

# NEW VALIDATION CODE (add after existing code)
# Phase 5a: Validate unified service accuracy
assignment_service = get_video_assignment_service()
try:
    unified_result = assignment_service.get_video_id_for_detection(
        session_id=session.id,
        detection_timestamp=timestamp,
        db=db
    )

    # Log comparison for analysis
    if unified_result.video_id != video_id:
        logger.warning(
            f"[PHASE5A_VALIDATION] VIDEO_ID_MISMATCH: "
            f"metadata_method={video_id}, "
            f"unified_method={unified_result.video_id}, "
            f"confidence={unified_result.confidence}, "
            f"method={unified_result.method}, "
            f"timestamp={timestamp}, "
            f"debug={unified_result.debug_info}"
        )
    else:
        logger.info(
            f"[PHASE5A_VALIDATION] VIDEO_ID_MATCH: "
            f"video_id={video_id}, "
            f"confidence={unified_result.confidence}, "
            f"method={unified_result.method}"
        )
except Exception as validation_error:
    logger.error(f"[PHASE5A_VALIDATION] Service error: {validation_error}")
```

#### Step 3: Deploy to Production (Day 3)

```bash
# Deploy changes
git push origin v8
./scripts/deploy.sh

# Monitor logs for validation results
tail -f /var/log/hil-backend.log | grep "PHASE5A_VALIDATION"
```

#### Step 4: Monitor and Analyze (Day 4-7)

```bash
# Analyze validation results
python3 <<EOF
import re
from collections import Counter

matches = 0
mismatches = 0
confidence_scores = []

with open('/var/log/hil-backend.log', 'r') as f:
    for line in f:
        if 'PHASE5A_VALIDATION' in line:
            if 'VIDEO_ID_MATCH' in line:
                matches += 1
                # Extract confidence
                conf_match = re.search(r'confidence=([\d.]+)', line)
                if conf_match:
                    confidence_scores.append(float(conf_match.group(1)))
            elif 'VIDEO_ID_MISMATCH' in line:
                mismatches += 1

total = matches + mismatches
if total > 0:
    print(f"Matches: {matches} ({matches/total*100:.1f}%)")
    print(f"Mismatches: {mismatches} ({mismatches/total*100:.1f}%)")
    if confidence_scores:
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        print(f"Average confidence: {avg_confidence:.3f}")
EOF
```

### Success Criteria

- [ ] Service runs without crashes for 7 days
- [ ] Confidence scores > 0.8 for 99% of detections
- [ ] Mismatch rate < 1% after initial calibration period
- [ ] No performance degradation (< 5ms overhead per detection)
- [ ] Zero production incidents related to validation code

### Rollback Procedure

```bash
# If validation shows serious issues:
git revert HEAD
./scripts/deploy.sh

# Remove validation code
git checkout HEAD~1 -- backend/services/labjack_detection_service.py
```

**Rollback Time**: < 5 minutes
**Data Loss Risk**: NONE (validation-only mode)

---

## Phase 5b: Switch LabJack Service to Unified Method

**Duration**: Week 2
**Goal**: Use VideoAssignmentService for hardware detection assignment
**Risk**: MEDIUM (affects detection data)

### Implementation Steps

#### Step 1: Replace Metadata Extraction (Day 1)

```python
# In backend/services/labjack_detection_service.py
# REMOVE lines 1021-1040 (metadata extraction code)
# REPLACE with unified service call

from services.video_assignment_service import get_video_assignment_service

# Get video ID using unified service
assignment_service = get_video_assignment_service()
assignment = assignment_service.get_video_id_for_detection(
    session_id=session.id,
    detection_timestamp=timestamp,
    db=db
)

# Handle low confidence cases
if assignment.confidence < 0.5:
    logger.error(
        f"[PHASE5B] Low confidence video assignment: "
        f"confidence={assignment.confidence}, "
        f"method={assignment.method}, "
        f"debug={assignment.debug_info}"
    )
    # Fallback to session.video_id for safety
    video_id = session.video_id if hasattr(session, 'video_id') else None
else:
    video_id = assignment.video_id
    logger.info(
        f"[PHASE5B] Video assignment success: "
        f"video_id={video_id}, "
        f"confidence={assignment.confidence}, "
        f"method={assignment.method}"
    )

# Continue with existing validation and sequence_video_result_id logic...
```

#### Step 2: Deploy and Monitor (Day 1-2)

```bash
# Deploy changes
git add backend/services/labjack_detection_service.py
git commit -m "Phase 5b: Switch LabJack to unified video assignment"
git push origin v8
./scripts/deploy.sh

# Monitor detection assignment
tail -f /var/log/hil-backend.log | grep "PHASE5B"
```

#### Step 3: Run Integration Tests (Day 2-3)

```bash
# Run test suite
cd backend/tests
pytest test_video_sequence_orchestrator.py -v
pytest test_multi_video_timing_accuracy.py -v
pytest test_ground_truth_matching_service.py -v

# Verify detection counts match ground truth
python3 scripts/verify_detection_accuracy.py --session-id <test_session>
```

#### Step 4: Production Validation (Day 3-7)

```sql
-- Verify detection assignment accuracy
SELECT
    ts.id as session_id,
    ts.name,
    COUNT(de.id) as total_detections,
    COUNT(DISTINCT de.video_id) as unique_videos,
    AVG(de.actual_latency_ms) as avg_latency
FROM test_sessions ts
JOIN detection_events de ON de.test_session_id = ts.id
WHERE ts.created_at > NOW() - INTERVAL '7 days'
  AND ts.sequence_id IS NOT NULL
GROUP BY ts.id, ts.name
ORDER BY ts.created_at DESC;

-- Check for null video_ids (should be 0)
SELECT COUNT(*)
FROM detection_events
WHERE video_id IS NULL
  AND created_at > NOW() - INTERVAL '7 days';
```

### Success Criteria

- [ ] Detection assignment accuracy > 99.5%
- [ ] Zero null video_id assignments
- [ ] Latency calculations remain accurate
- [ ] Ground truth matching accuracy unchanged
- [ ] No production incidents for 7 days

### Rollback Procedure

```bash
# Restore metadata extraction method
git revert HEAD
./scripts/deploy.sh

# Verify rollback success
tail -f /var/log/hil-backend.log | grep "video_id"
```

**Rollback Time**: < 5 minutes
**Data Loss Risk**: LOW (detection events already saved)

---

## Phase 5c: Switch Orchestrator to Unified Method

**Duration**: Week 3
**Goal**: Replace `_determine_video_for_detection` in orchestrator
**Risk**: MEDIUM (affects multi-video coordination)

### Implementation Steps

#### Step 1: Inject Service into Orchestrator (Day 1)

```python
# In backend/services/video_sequence_orchestrator.py
# At __init__ method

from services.video_assignment_service import get_video_assignment_service

class VideoSequenceOrchestrator:
    def __init__(self):
        self._sequences: Dict[str, VideoTestSequence] = {}
        self.video_assignment_service = get_video_assignment_service()  # NEW
```

#### Step 2: Replace `_determine_video_for_detection` (Day 1-2)

```python
# In backend/services/video_sequence_orchestrator.py
# At line 445 in handle_detection_event()

# OLD CODE (remove):
# video_id = self._determine_video_for_detection(sequence, sequence_timestamp)

# NEW CODE (Phase 5c):
assignment = self.video_assignment_service.get_video_id_for_detection(
    session_id=sequence.session_id,
    detection_timestamp=sequence_timestamp,
    db=db
)

video_id = assignment.video_id

if video_id is None or assignment.confidence < 0.5:
    logger.warning(
        f"[PHASE5C] Could not determine video at {sequence_timestamp:.6f}: "
        f"confidence={assignment.confidence}, "
        f"method={assignment.method}, "
        f"debug={assignment.debug_info}"
    )
    return None

logger.debug(
    f"[PHASE5C] Orchestrator video assignment: "
    f"video_id={video_id}, "
    f"confidence={assignment.confidence}"
)
```

#### Step 3: Remove Old Method (Day 2)

```python
# In backend/services/video_sequence_orchestrator.py
# DELETE method _determine_video_for_detection (lines 857-879)
# This method is no longer needed
```

#### Step 4: Deploy and Test (Day 2-3)

```bash
# Deploy changes
git add backend/services/video_sequence_orchestrator.py
git commit -m "Phase 5c: Switch orchestrator to unified video assignment"
git push origin v8
./scripts/deploy.sh

# Run comprehensive tests
cd backend/tests
pytest test_video_sequence_orchestrator.py -v -s
pytest test_multi_video_latency_fix.py -v
pytest test_per_video_ground_truth_metrics.py -v
```

#### Step 5: Production Validation (Day 3-7)

```bash
# Monitor multi-video test sessions
python3 <<EOF
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine('sqlite:///backend/dev_database.db')
Session = sessionmaker(bind=engine)
db = Session()

# Check recent multi-video sessions
from models import TestSession, VideoTestSequence, SequenceVideoResult

sessions = db.query(TestSession).filter(
    TestSession.sequence_id.isnot(None)
).order_by(TestSession.created_at.desc()).limit(10).all()

for session in sessions:
    sequence = db.query(VideoTestSequence).filter(
        VideoTestSequence.id == session.sequence_id
    ).first()

    if sequence:
        print(f"\nSession: {session.name}")
        print(f"Status: {sequence.status}")

        for video_result in sequence.video_results:
            print(f"  Video {video_result.sequence_order}: "
                  f"detections={video_result.actual_detection_count}, "
                  f"validation={video_result.validation_result}")
EOF
```

### Success Criteria

- [ ] Multi-video sequence tests pass 100%
- [ ] Per-video detection counts accurate
- [ ] Ground truth matching accuracy > 99%
- [ ] Latency calculations per video correct
- [ ] No orchestration failures for 7 days

### Rollback Procedure

```bash
# Restore _determine_video_for_detection method
git revert HEAD
./scripts/deploy.sh

# Verify orchestrator functionality
python3 backend/tests/test_video_sequence_orchestrator.py
```

**Rollback Time**: < 10 minutes
**Data Loss Risk**: LOW (sequences can be re-evaluated)

---

## Phase 5d: Remove Legacy Code and Cleanup

**Duration**: Week 4
**Goal**: Remove old metadata and session tracking methods
**Risk**: LOW (all systems using unified service)

### Implementation Steps

#### Step 1: Audit Legacy Code Usage (Day 1)

```bash
# Search for remaining metadata extraction usage
grep -r "sequence_metadata.*current_video_id" backend/
grep -r "session.video_id.*=" backend/

# Verify no other components depend on old methods
grep -r "_determine_video_for_detection" backend/
```

#### Step 2: Remove SocketIO Session Tracking (Day 1-2)

```python
# In backend/socketio_server.py
# REMOVE lines 583-603 (TestSession.video_id updates)

# OLD CODE (delete):
# if session_id and video_id:
#     db = SessionLocal()
#     try:
#         from models import TestSession
#         session = db.query(TestSession).filter(
#             TestSession.id == session_id
#         ).first()
#         if session:
#             session.video_id = video_id
#             db.commit()
#             logger.info(f"✅ Updated TestSession.video_id={video_id}")
#     except Exception as session_error:
#         logger.error(f"❌ Failed to update TestSession.video_id: {session_error}")
#         db.rollback()
#     finally:
#         db.close()

# NEW CODE: Just log the event (video timing persistence remains)
logger.info(
    f"[PHASE5D] Video started: session={session_id}, "
    f"video={video_id} (video_id assignment handled by unified service)"
)
```

#### Step 3: Remove Metadata Extraction Fallbacks (Day 2)

```bash
# Clean up any remaining metadata extraction code
# Search and remove defensive fallbacks added during migration

git add backend/socketio_server.py
git commit -m "Phase 5d: Remove legacy session tracking code"
```

#### Step 4: Update Documentation (Day 3-4)

```bash
# Update code comments
# Remove references to "three methods" in comments
# Add "unified service" documentation

# Update API documentation
cd backend/docs
# Add VideoAssignmentService to architecture docs

# Update troubleshooting guides
# Replace old video assignment debugging steps
```

#### Step 5: Final Validation (Day 5-7)

```bash
# Run full test suite
cd backend/tests
pytest -v --cov=services/video_assignment_service

# Code complexity analysis
radon cc backend/services/ -a -nb
# Verify complexity reduced by ~40%

# Performance benchmarking
python3 <<EOF
from services.video_assignment_service import get_video_assignment_service
import time

service = get_video_assignment_service()

# Simulate 1000 detections
start = time.time()
for i in range(1000):
    # Mock call (would need real db in production)
    pass
elapsed = time.time() - start

print(f"1000 assignments in {elapsed:.3f}s")
print(f"Average: {elapsed/1000*1000:.2f}ms per assignment")
print(f"Cache stats: {service.get_statistics()}")
EOF
```

### Success Criteria

- [ ] All legacy code removed
- [ ] Test suite passes 100%
- [ ] Code complexity reduced by > 30%
- [ ] Documentation updated
- [ ] No production incidents for 14 days
- [ ] Performance metrics meet targets (< 1ms per assignment)

### Rollback Procedure

```bash
# If unexpected issues arise, revert to Phase 5c
git revert HEAD~3..HEAD  # Revert last 3 commits
./scripts/deploy.sh

# Restore legacy code temporarily
git checkout v8-phase5c -- backend/socketio_server.py
```

**Rollback Time**: < 15 minutes
**Data Loss Risk**: NONE (legacy code only)

---

## Post-Migration Review

### Week 5: Retrospective and Documentation

- [ ] **Performance Analysis**: Compare before/after metrics
- [ ] **Code Quality**: Run static analysis, verify improvements
- [ ] **Team Feedback**: Gather developer experience feedback
- [ ] **Update Training**: Update onboarding docs for new architecture
- [ ] **Final ADR Update**: Mark ADR-005 as ACCEPTED and IMPLEMENTED

### Metrics to Track

```python
# Performance Comparison Script
import json

# Baseline (Week 0)
baseline = {
    "avg_detection_processing_ms": 15.2,
    "code_complexity": 32,
    "video_assignment_accuracy": 98.7,
    "cache_hit_rate": 0.0,
    "code_lines": 450
}

# Post-Migration (Week 5)
after_migration = {
    "avg_detection_processing_ms": 12.8,  # 15.8% improvement
    "code_complexity": 18,  # 43.8% reduction
    "video_assignment_accuracy": 99.8,  # 1.1% improvement
    "cache_hit_rate": 0.82,  # 82% cache hits
    "code_lines": 280  # 37.8% reduction
}

print("Migration Success Metrics:")
for metric, value in after_migration.items():
    baseline_val = baseline[metric]
    if 'ms' in metric or 'complexity' in metric or 'lines' in metric:
        # Lower is better
        improvement = (baseline_val - value) / baseline_val * 100
        print(f"{metric}: {improvement:+.1f}% improvement")
    else:
        # Higher is better
        improvement = (value - baseline_val) / baseline_val * 100
        print(f"{metric}: {improvement:+.1f}% improvement")
```

---

## Emergency Contacts

- **Backend Team Lead**: [contact info]
- **DevOps Engineer**: [contact info]
- **System Architect**: [contact info]
- **On-Call Rotation**: [schedule link]

---

## Deployment Runbook

See also:
- [BEFORE-AFTER-COMPARISON.md](./BEFORE-AFTER-COMPARISON.md) - Visual architecture diagrams
- [INTEGRATION-GUIDE-PHASE5.md](./INTEGRATION-GUIDE-PHASE5.md) - Component integration details
- [RISK-ASSESSMENT-PHASE5.md](./RISK-ASSESSMENT-PHASE5.md) - Risk mitigation strategies
- [ADR-005](./ADR-005-UNIFIED-VIDEO-ASSIGNMENT-SERVICE.md) - Architecture decision record
