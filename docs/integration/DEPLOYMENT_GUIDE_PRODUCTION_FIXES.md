# Production Deployment Guide - 15 Fixes Integration

**Generated:** 2025-11-11
**Target Environment:** Production HIL Validation Platform
**Deployment Strategy:** Phased Rollout (5 Phases)
**Total Duration:** 12-15 days

---

## Table of Contents

1. [Pre-Deployment Requirements](#pre-deployment-requirements)
2. [Phase 1: Foundation (Days 1-2)](#phase-1-foundation-days-1-2)
3. [Phase 2: Outcome & Approval (Days 3-5)](#phase-2-outcome--approval-days-3-5)
4. [Phase 3: API & Frontend (Days 6-7)](#phase-3-api--frontend-days-6-7)
5. [Phase 4: Infrastructure (Days 8-11)](#phase-4-infrastructure-days-8-11)
6. [Phase 5: Observability (Day 12)](#phase-5-observability-day-12)
7. [Post-Deployment Validation](#post-deployment-validation)
8. [Rollback Procedures](#rollback-procedures)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## Pre-Deployment Requirements

### Environment Preparation

```bash
# 1. Backup production database
pg_dump -h production-db.example.com -U hil_user -d hil_production > \
  backups/hil_production_$(date +%Y%m%d_%H%M%S).sql

# 2. Verify backup integrity
pg_restore --list backups/hil_production_*.sql | head -20

# 3. Create staging snapshot
CREATE DATABASE hil_staging_clone WITH TEMPLATE hil_production;

# 4. Tag current production version
git tag -a v8.0-pre-fixes -m "Production state before 15-fix deployment"
git push origin v8.0-pre-fixes
```

### Required Access & Permissions

- [ ] Production database admin access
- [ ] Backend server SSH access (sudo privileges)
- [ ] Frontend deployment pipeline access
- [ ] CDN cache purge access
- [ ] Monitoring dashboard admin
- [ ] On-call escalation path confirmed

### Test Environment Validation

```bash
# Run full test suite on staging
cd ai-model-validation-platform/backend
pytest tests/ -v --cov=services --cov=routers --cov-report=html

# Expected: >90% coverage, all tests pass
# Coverage report: htmlcov/index.html

# Run integration tests
pytest tests/test_integration_production.py -v

# Run performance benchmarks
python scripts/benchmark_all_fixes.py

# Verify migrations
alembic upgrade head
alembic current
```

### Stakeholder Communication

**Send Deployment Notice:**

```
Subject: [ACTION REQUIRED] HIL Platform Maintenance Window - 15 Production Fixes

Dear Stakeholders,

We will be deploying 15 critical production fixes to the HIL Validation Platform.

Deployment Schedule:
- Phase 1: [Date] 02:00-04:00 UTC (Foundation)
- Phase 2: [Date] 02:00-04:00 UTC (Approval Workflow)
- Phase 3: [Date] 02:00-04:00 UTC (API Changes - BREAKING)
- Phase 4: [Date] 02:00-04:00 UTC (Infrastructure)
- Phase 5: [Date] 02:00-04:00 UTC (Observability)

Expected Impact:
- Phase 1-2: No downtime, backend restart required
- Phase 3: 15-minute downtime (API contract change)
- Phase 4-5: No downtime

Action Required:
- Clear browser cache after Phase 3 deployment
- Approval workflow training session: [Date/Time]

Contact: devops@example.com for questions

Deployment Lead: [Name]
On-Call Engineer: [Name]
```

---

## Phase 1: Foundation (Days 1-2)

**Fixes Deployed:** #6 (Transaction), #5 (GT Double-Matching), #8 (Tolerance Clamp), #11 (Validation State)

### Day 1: Backend Code Changes

#### Fix #6: Transaction Atomicity

**File:** `backend/services/session_completion_service.py`

```python
# BEFORE (Lines 56-213) - Multiple commits
def complete_test_session(session_id):
    session = db.query(TestSession).get(session_id)

    # Validation
    reassign_null_video_ids(session_id)  # Commit 1
    matching_results = match_detections_to_ground_truth(session_id)  # Commit 2
    metrics = calculate_session_metrics(session_id)  # Commit 3

    session.status = "completed"
    db.commit()  # Commit 4 - if fails, previous 3 already applied!

# AFTER - Single transaction
def complete_test_session(session_id):
    """Session completion with atomic transaction."""
    try:
        with db.begin():  # Single transaction wrapper
            session = db.query(TestSession).get(session_id)

            # Validation
            if session.has_video_sequence:
                validation = validate_video_sequence_completion(session_id)
                if not validation['valid']:
                    # Mark as failed instead of raising
                    session.status = "VALIDATION_FAILED"
                    session.failure_reason = validation['reason']
                    session.failure_details = json.dumps(validation['missing_data'])
                    # Transaction commits here with failure state
                    raise ValidationFailedException(validation['reason'])

            # All operations within transaction
            reassign_null_video_ids(session_id)
            matching_results = match_detections_to_ground_truth(session_id, tolerance_ms=100)
            metrics = calculate_session_metrics(session_id)

            # Update session
            session.precision = metrics.precision
            session.recall = metrics.recall
            session.f1_score = metrics.f1_score
            session.true_positives = metrics.true_positives
            session.false_positives = metrics.false_positives
            session.false_negatives = metrics.false_negatives
            session.mean_latency_ms = metrics.mean_latency_ms
            session.status = "completed"
            session.completed_at = datetime.utcnow()

            # Single commit at end (all or nothing)

        # Emit WebSocket after successful commit
        socketio.emit('session_completed', {
            'session_id': session_id,
            'status': 'completed',
            'metrics': {
                'precision': metrics.precision,
                'recall': metrics.recall,
                'f1_score': metrics.f1_score
            }
        })

    except ValidationFailedException as e:
        logger.warning(f"Session {session_id} validation failed: {e}")
        socketio.emit('session_failed', {
            'session_id': session_id,
            'reason': str(e)
        })
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Session {session_id} completion error: {e}")

        # Mark session as error state in separate transaction
        try:
            session = db.query(TestSession).get(session_id)
            session.status = "ERROR"
            session.failure_reason = f"Completion failed: {str(e)}"
            db.commit()
        except Exception as commit_error:
            logger.error(f"Failed to mark session as ERROR: {commit_error}")

        socketio.emit('session_failed', {
            'session_id': session_id,
            'reason': 'internal_error'
        })
        raise HTTPException(status_code=500, detail="Session completion failed")
```

**Test:**
```bash
pytest tests/test_session_completion_transactionality.py -v
```

#### Fix #5: GT Double-Matching Prevention

**File:** `backend/services/ground_truth_matching_service.py` (Lines 644-918)

```python
# BEFORE - Potential double-matching
for gt_object in gt_list:
    best_match = None
    min_time_diff = float('inf')

    for detection in video_detections:  # ❌ Doesn't skip matched
        if detection.video_id != video_id:
            continue

        time_diff_ms = abs(detection.timestamp - gt_object.timestamp) * 1000

        if time_diff_ms <= tolerance_ms and time_diff_ms < min_time_diff:
            best_match = detection  # Could match same detection multiple times!

# AFTER - Skip matched detections
matched_detection_ids = set()  # Track matched detections

for gt_object in gt_list:
    best_match = None
    min_time_diff = float('inf')

    for detection in video_detections:
        # ✅ FIX: Skip already-matched detections
        if detection.id in matched_detection_ids:
            continue

        if detection.video_id != video_id:
            continue

        time_diff_ms = abs(detection.timestamp - gt_object.timestamp) * 1000

        if time_diff_ms <= tolerance_ms and time_diff_ms < min_time_diff:
            best_match = detection
            min_time_diff = time_diff_ms

    if best_match:
        # Mark as matched BEFORE next iteration
        matched_detection_ids.add(best_match.id)

        # TRUE POSITIVE
        latency_ms = (best_match.timestamp - gt_object.timestamp) * 1000
        temporal_iou = 1.0 - (min_time_diff / tolerance_ms)

        true_positives.append(MatchResult(
            detection_id=best_match.id,
            ground_truth_id=gt_object.id,
            match_type='TP',
            latency_ms=latency_ms,
            temporal_iou=temporal_iou
        ))

        best_match.classification = 'TP'
        best_match.latency_ms = latency_ms
```

**Test:**
```bash
pytest tests/test_gt_double_matching_prevention.py -v
```

#### Fix #8: Tolerance Window Clamping

**File:** `backend/services/video_id_resolver.py` (Lines 45-120)

```python
# BEFORE - Tolerance can overlap into next video
def resolve_video_id(session_id, timestamp_ms, sequence_metadata):
    video_timing = sequence_metadata.get('video_timing', {})

    for video_id, timing in video_timing.items():
        start = timing['cumulative_offset_ms']
        end = start + timing['actual_duration_ms']
        tolerance_ms = 500  # ❌ Can extend into next video

        if start <= timestamp_ms < (end + tolerance_ms):
            return video_id  # First match wins

# AFTER - Clamp tolerance to next video boundary
def resolve_video_id(session_id, timestamp_ms, sequence_metadata):
    """
    Resolve video ID from timestamp with boundary protection.

    ✅ Clamps tolerance window to prevent overlap with next video.
    """
    video_timing = sequence_metadata.get('video_timing', {})

    if not video_timing:
        return None

    # Sort videos by start time
    videos = sorted(video_timing.items(), key=lambda x: x[1]['cumulative_offset_ms'])

    for idx, (video_id, timing) in enumerate(videos):
        start = timing['cumulative_offset_ms']
        end = start + timing['actual_duration_ms']
        tolerance_ms = 500

        # ✅ FIX: Clamp tolerance to not exceed next video start
        if idx < len(videos) - 1:
            next_start = videos[idx + 1][1]['cumulative_offset_ms']
            max_end = min(end + tolerance_ms, next_start)
        else:
            max_end = end + tolerance_ms

        if start <= timestamp_ms < max_end:
            logger.debug(
                f"Timestamp {timestamp_ms}ms assigned to video {video_id} "
                f"(window: {start}-{max_end}ms)"
            )
            return video_id

    # Fallback: assign to last video if after all windows
    last_video_id = videos[-1][0]
    logger.warning(
        f"Timestamp {timestamp_ms}ms beyond all video windows, "
        f"assigning to last video {last_video_id}"
    )
    return last_video_id
```

**Test:**
```bash
pytest tests/test_tolerance_clamping.py -v
```

#### Fix #11: Validation Failure State

**Integrated into Fix #6 (see above)** - No separate deployment needed.

### Day 2: Deploy Phase 1 to Production

```bash
# 1. Pull latest code
cd /opt/hil-backend
git fetch origin
git checkout v8.1-phase1-foundation

# 2. Install dependencies (if any new)
pip install -r requirements.txt

# 3. Run database migrations (none for Phase 1, code-only changes)
alembic current  # Verify current state

# 4. Run pre-deployment tests on production snapshot
pytest tests/test_phase1_integration.py --db-url=postgresql://staging-clone

# 5. Restart backend (zero downtime with rolling restart)
systemctl restart hil-backend

# 6. Verify health
curl http://localhost:8000/health
# Expected: {"status": "healthy", "version": "v8.1-phase1"}

# 7. Run smoke tests
pytest tests/smoke/test_session_completion.py --production
```

**Post-Deployment Validation:**

```bash
# Monitor logs for errors
tail -f /var/log/hil-backend/application.log | grep -i error

# Check metrics dashboard
# - Session completion rate should remain >95%
# - No spike in 500 errors
# - GT matching duration <500ms

# Run production test session
python scripts/create_test_session.py --video-count=2 --detections=20
# Verify completion succeeds and metrics calculated correctly
```

**Rollback Criteria:**
- Session completion rate drops below 90%
- Error rate exceeds 1%
- GT matching duration exceeds 1s

**If Rollback Needed:**
```bash
git checkout v8.0-pre-fixes
systemctl restart hil-backend
```

---

## Phase 2: Outcome & Approval (Days 3-5)

**Fixes Deployed:** #4 (Store Outcome), #2 (Approval Workflow), #17 (Failure Reasons)

### Day 3: Database Migration

#### Fix #4: Add Outcome Field

**Migration File:** `backend/migrations/versions/add_outcome_and_approval_fields.py`

```python
"""Add outcome and approval fields to test_sessions

Revision ID: abc123def456
Revises: previous_revision
Create Date: 2025-11-11 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add outcome field
    op.add_column('test_sessions', sa.Column('outcome', sa.String(20), nullable=True))
    op.add_column('test_sessions', sa.Column('outcome_reasons', sa.JSON, nullable=True))

    # Add approval workflow fields
    op.add_column('test_sessions', sa.Column('approval_status', sa.String(20),
                                             server_default='pending'))
    op.add_column('test_sessions', sa.Column('approved_by', sa.String(255), nullable=True))
    op.add_column('test_sessions', sa.Column('approved_at', sa.DateTime, nullable=True))
    op.add_column('test_sessions', sa.Column('approval_comments', sa.Text, nullable=True))
    op.add_column('test_sessions', sa.Column('rejection_reason', sa.Text, nullable=True))

    # Create index for approval queries
    op.create_index('idx_approval_status', 'test_sessions', ['approval_status'])

def downgrade():
    op.drop_index('idx_approval_status', table_name='test_sessions')
    op.drop_column('test_sessions', 'rejection_reason')
    op.drop_column('test_sessions', 'approval_comments')
    op.drop_column('test_sessions', 'approved_at')
    op.drop_column('test_sessions', 'approved_by')
    op.drop_column('test_sessions', 'approval_status')
    op.drop_column('test_sessions', 'outcome_reasons')
    op.drop_column('test_sessions', 'outcome')
```

**Deploy Migration:**

```bash
# Test on staging clone first
alembic upgrade head --sql > migration_phase2.sql
# Review SQL manually

# Apply to staging
alembic upgrade head

# Verify migration
psql -d hil_staging_clone -c "SELECT outcome, approval_status FROM test_sessions LIMIT 1;"

# If successful, apply to production
cd /opt/hil-backend
alembic upgrade head

# Verify production
psql -d hil_production -c "\d test_sessions"
# Should show new columns: outcome, outcome_reasons, approval_status, etc.
```

### Day 4: Backend Code Changes

#### Fix #4: Store Outcome

**File:** `backend/services/ground_truth_matching_service.py`

```python
# Add to calculate_session_metrics() function

def determine_session_status_with_reasons(metrics: SessionMetrics) -> dict:
    """
    Determine pass/fail outcome with detailed reasons.

    Returns:
        {
            'outcome': str,  # "PASS" | "CONDITIONAL_PASS" | "FAIL"
            'reasons': List[str]  # Why it passed/failed
        }
    """
    reasons = []

    precision = metrics.precision or 0
    recall = metrics.recall or 0
    mean_latency = metrics.mean_latency_ms or 0

    # Check thresholds
    if precision < 0.6:
        reasons.append(f"Precision {precision:.1%} below 60% threshold")

    if recall < 0.6:
        reasons.append(f"Recall {recall:.1%} below 60% threshold")

    if mean_latency > 150:
        reasons.append(f"Mean latency {mean_latency:.0f}ms exceeds 150ms limit")

    # Determine outcome
    if precision >= 0.8 and recall >= 0.75 and mean_latency <= 100:
        outcome = "PASS"
        if not reasons:
            reasons = [
                f"Precision {precision:.1%} ≥ 80%",
                f"Recall {recall:.1%} ≥ 75%",
                f"Mean latency {mean_latency:.0f}ms ≤ 100ms"
            ]
    elif (precision >= 0.6 or recall >= 0.6) and mean_latency <= 150:
        outcome = "CONDITIONAL_PASS"
        if not reasons:
            reasons = ["Meets conditional pass criteria, requires manual approval"]
    else:
        outcome = "FAIL"
        if not reasons:
            reasons = ["Does not meet minimum pass criteria"]

    return {
        'outcome': outcome,
        'reasons': reasons
    }


# Update session completion
def complete_test_session(session_id):
    try:
        with db.begin():
            # ... existing completion logic ...

            metrics = calculate_session_metrics(session_id)

            # ✅ NEW: Determine and store outcome
            outcome_result = determine_session_status_with_reasons(metrics)

            session.precision = metrics.precision
            session.recall = metrics.recall
            session.f1_score = metrics.f1_score
            session.outcome = outcome_result['outcome']  # NEW
            session.outcome_reasons = outcome_result['reasons']  # NEW
            session.status = "completed"

    except Exception as e:
        # ... error handling ...
```

#### Fix #2: Approval Workflow Endpoints

**File:** `backend/routers/test_sessions.py`

```python
from pydantic import BaseModel
from typing import Optional

class ApprovalRequest(BaseModel):
    approver_id: str
    comments: Optional[str] = None
    action: str  # 'approve' or 'reject'
    rejection_reason: Optional[str] = None

@router.post("/{session_id}/approval", response_model=dict)
def approve_or_reject_session(
    session_id: str,
    approval: ApprovalRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)  # Auth middleware
):
    """
    Approve or reject a completed test session.

    - **PASS** sessions can be auto-approved or manually approved
    - **CONDITIONAL_PASS** sessions MUST be manually approved
    - **FAIL** sessions can be rejected with reason
    """
    session = db.query(TestSession).get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Can only approve completed sessions"
        )

    # Validate approver authorization
    if not current_user.get('can_approve_sessions'):
        raise HTTPException(status_code=403, detail="Unauthorized to approve sessions")

    if approval.action == 'approve':
        session.approval_status = 'approved'
        session.approved_by = approval.approver_id
        session.approved_at = datetime.utcnow()
        session.approval_comments = approval.comments

        logger.info(f"Session {session_id} approved by {approval.approver_id}")

    elif approval.action == 'reject':
        session.approval_status = 'rejected'
        session.approved_by = approval.approver_id
        session.approved_at = datetime.utcnow()
        session.rejection_reason = approval.rejection_reason

        logger.warning(
            f"Session {session_id} rejected by {approval.approver_id}: "
            f"{approval.rejection_reason}"
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    db.commit()

    # Emit WebSocket event
    socketio.emit('session_approval_updated', {
        'session_id': session_id,
        'approval_status': session.approval_status,
        'approved_by': approval.approver_id
    })

    return {
        'session_id': session_id,
        'approval_status': session.approval_status,
        'outcome': session.outcome
    }


@router.get("/{session_id}/approval-required", response_model=bool)
def check_approval_required(session_id: str, db: Session = Depends(get_db)):
    """Check if session requires manual approval."""
    session = db.query(TestSession).get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # CONDITIONAL_PASS always requires approval
    # PASS can be auto-approved based on configuration
    requires_approval = (
        session.outcome == "CONDITIONAL_PASS" or
        (session.outcome == "PASS" and config.REQUIRE_APPROVAL_FOR_PASS)
    )

    return requires_approval
```

#### Fix #17: Failure Reasons in API

**File:** `backend/src/api/enhanced_hil_results_endpoints.py`

```python
class EnhancedHILResultsResponse(BaseModel):
    session_id: str = Field(alias='sessionId')
    status: str
    outcome: Optional[str] = None  # ✅ NEW
    outcome_reasons: Optional[List[str]] = Field(default=[], alias='outcomeReasons')  # ✅ NEW
    approval_status: Optional[str] = Field(default='pending', alias='approvalStatus')  # ✅ NEW
    approved_by: Optional[str] = Field(default=None, alias='approvedBy')  # ✅ NEW
    approved_at: Optional[str] = Field(default=None, alias='approvedAt')  # ✅ NEW
    ground_truth_comparison: GroundTruthComparison = Field(alias='groundTruthComparison')
    detection_events: List[DetectionEvent] = Field(alias='detectionEvents')
    per_video_results: Optional[List[PerVideoResult]] = Field(default=None, alias='perVideoResults')

    class Config:
        populate_by_name = True
        alias_generator = camelize
```

### Day 5: Frontend Changes

**File:** `frontend/src/pages/HILResults.tsx`

```typescript
// Add approval state
const [approvalStatus, setApprovalStatus] = useState<ApprovalStatus>('pending');
const [approvalComments, setApprovalComments] = useState('');
const [showApprovalDialog, setShowApprovalDialog] = useState(false);

// Handle approval
async function handleApprove() {
  try {
    await approveTestSession(sessionId, {
      approver_id: currentUser.id,
      comments: approvalComments,
      action: 'approve'
    });

    setApprovalStatus('approved');
    showSuccess('Test session approved successfully');
  } catch (error) {
    showError(`Failed to approve session: ${error.message}`);
  }
}

async function handleReject() {
  const reason = await promptForRejectionReason();

  if (!reason) return;

  try {
    await approveTestSession(sessionId, {
      approver_id: currentUser.id,
      action: 'reject',
      rejection_reason: reason
    });

    setApprovalStatus('rejected');
    showWarning('Test session rejected');
  } catch (error) {
    showError(`Failed to reject session: ${error.message}`);
  }
}

// Render approval UI
<Box sx={{ mt: 4 }}>
  {/* Test Status Banner with Outcome */}
  <TestStatusBanner
    outcome={enhancedResults.outcome}
    outcomeReasons={enhancedResults.outcomeReasons}
    approvalStatus={enhancedResults.approvalStatus}
  />

  {/* Approval Buttons (if pending) */}
  {enhancedResults.approvalStatus === 'pending' && (
    <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'center' }}>
      <Button
        variant="contained"
        color="success"
        size="large"
        onClick={() => setShowApprovalDialog(true)}
        startIcon={<CheckIcon />}
      >
        Approve Results
      </Button>
      <Button
        variant="contained"
        color="error"
        size="large"
        onClick={handleReject}
        startIcon={<CloseIcon />}
      >
        Reject Results
      </Button>
    </Box>
  )}

  {/* Approval Status (if approved/rejected) */}
  {enhancedResults.approvalStatus === 'approved' && (
    <Alert severity="success" sx={{ mt: 3 }}>
      <AlertTitle>Approved</AlertTitle>
      Approved by {enhancedResults.approvedBy} on {formatDate(enhancedResults.approvedAt)}
      {enhancedResults.approvalComments && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          Comments: {enhancedResults.approvalComments}
        </Typography>
      )}
    </Alert>
  )}
</Box>

{/* Approval Dialog */}
<ApprovalDialog
  open={showApprovalDialog}
  onClose={() => setShowApprovalDialog(false)}
  onApprove={handleApprove}
  comments={approvalComments}
  setComments={setApprovalComments}
  sessionOutcome={enhancedResults.outcome}
/>
```

**Deploy Phase 2:**

```bash
# Backend
cd /opt/hil-backend
git checkout v8.1-phase2-approval
systemctl restart hil-backend

# Frontend
cd /opt/hil-frontend
git checkout v8.1-phase2-approval
npm run build
npm run deploy

# Verify
curl http://backend/api/test-sessions/{session_id}/approval-required
```

---

## Phase 3: API & Frontend (Days 6-7)

**Fixes Deployed:** #7 (API Schema Standardization), #3 (Delete Deprecated Code)

### Day 6: API Schema Standardization (Breaking Change)

**⚠️ CRITICAL: This is a breaking change requiring frontend update.**

**Strategy:** Deploy with dual-format support, then migrate.

#### Step 1: Deploy Dual-Format API

**File:** `backend/src/api/enhanced_hil_results_endpoints.py`

```python
# Temporary: Support both formats during transition
def to_dual_format(pydantic_model: BaseModel) -> dict:
    """Return both camelCase and snake_case for transition period."""
    camel_case = pydantic_model.dict(by_alias=True)
    snake_case = pydantic_model.dict(by_alias=False)

    return {**camel_case, **snake_case}

@router.get("/test-sessions/{session_id}/corrected-results")
async def get_enhanced_hil_results(session_id: str):
    results = build_enhanced_results(session_id)

    # During transition: Return both formats
    return to_dual_format(results)
```

**Deploy:**
```bash
cd /opt/hil-backend
git checkout v8.1-phase3-dual-format
systemctl restart hil-backend

# Verify both formats present
curl http://backend/api/enhanced-hil/test-sessions/{id}/corrected-results | jq 'keys'
# Should show both sessionId and session_id
```

#### Step 2: Update Frontend (Remove Normalization)

**File:** `frontend/src/services/api.ts`

```typescript
// BEFORE - Normalization workaround
function normalizeHILResults(data: any) {
  return {
    sessionId: data.sessionId || data.session_id,
    groundTruthComparison: {
      truePositives: data.groundTruthComparison?.truePositives ||
                     data.ground_truth_comparison?.true_positives || 0,
      // ... 50+ lines of redundant mapping
    }
  };
}

export async function getEnhancedHILResultsWithGroundTruth(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`);
  const data = await response.json();
  return normalizeHILResults(data);  // ❌ Remove this
}

// AFTER - Direct use of camelCase API
export async function getEnhancedHILResultsWithGroundTruth(sessionId: string) {
  const response = await fetch(`${API_BASE_URL}/api/enhanced-hil/test-sessions/${sessionId}/corrected-results`);

  if (!response.ok) {
    throw new Error(`Failed to fetch results: ${response.statusText}`);
  }

  return await response.json();  // ✅ Direct use, no normalization
}
```

**Deploy Frontend:**
```bash
cd /opt/hil-frontend
git checkout v8.1-phase3-camelcase
npm run build

# Test on staging first
STAGING_URL=staging.example.com npm run deploy:staging

# Run smoke tests
npm run test:e2e -- --env=staging

# If successful, deploy to production
npm run deploy:production

# CRITICAL: Clear CDN cache
npm run cache:clear
```

**User Communication:**
```
Subject: [ACTION REQUIRED] Clear Browser Cache - API Update

All users must clear browser cache after this deployment:
- Chrome/Edge: Ctrl+Shift+Delete → "Cached images and files"
- Firefox: Ctrl+Shift+Delete → "Cache"
- Safari: Cmd+Option+E

Or use hard refresh: Ctrl+F5 (Windows) / Cmd+Shift+R (Mac)

Failure to clear cache may result in display errors.
```

#### Step 3: Remove Snake_Case from Backend

**After frontend deployed and validated:**

```bash
# Remove dual-format support
cd /opt/hil-backend
git checkout v8.1-phase3-camelcase-only
systemctl restart hil-backend

# Verify only camelCase present
curl http://backend/api/enhanced-hil/test-sessions/{id}/corrected-results | jq 'keys'
# Should NOT show session_id or ground_truth_comparison
```

### Day 7: Delete Deprecated Frontend Code (Fix #3)

**File:** `frontend/src/pages/HILResults.tsx`

```typescript
// DELETE Lines 106-188 - createMetricsFromDetections()
// ❌ REMOVE ENTIRELY
function createMetricsFromDetections(
  detections: DetectionEvent[],
  groundTruthObjects: GroundTruthObject[]
): GroundTruthComparison {
  // 82 lines of incorrect code
  // ... DELETE ALL OF THIS ...
}

// ✅ All metrics now from backend only
const metrics = enhancedResults.groundTruthComparison;  // Direct use
```

**Deploy:**
```bash
cd /opt/hil-frontend
git checkout v8.1-phase3-cleanup
npm run build
npm run deploy:production
```

---

## Phase 4: Infrastructure (Days 8-11)

**Fixes Deployed:** #10 (WebSocket Rooms), #12 (Detection Buffering), #9 (Sequence Ack), #1 (Backend Timeout)

### Day 8-9: WebSocket Room Isolation (Fix #10)

**File:** `backend/socketio_server.py`

```python
from flask_socketio import join_room, leave_room, emit

@socketio.on('join_session')
def handle_join_session(data):
    """Client joins room for their session."""
    session_id = data.get('session_id')

    if not session_id:
        emit('error', {'message': 'session_id required'})
        return

    join_room(session_id)
    logger.info(f"Client {request.sid} joined session room {session_id}")

    emit('joined_session', {'session_id': session_id})

@socketio.on('leave_session')
def handle_leave_session(data):
    """Client leaves session room."""
    session_id = data.get('session_id')

    if session_id:
        leave_room(session_id)
        logger.info(f"Client {request.sid} left session room {session_id}")

# Update all emit calls to use rooms
def emit_detection_event(session_id, detection_data):
    """Emit detection event only to session room."""
    socketio.emit('detection_event', detection_data, room=session_id)  # ✅ room-scoped

def emit_session_completed(session_id, metrics):
    """Emit completion only to session room."""
    socketio.emit('session_completed', {
        'session_id': session_id,
        'metrics': metrics
    }, room=session_id)  # ✅ room-scoped
```

**File:** `frontend/src/services/websocketService.ts`

```typescript
class WebSocketService {
  private socket: Socket | null = null;
  private currentSessionId: string | null = null;

  connect(sessionId: string) {
    this.socket = io(WEBSOCKET_URL);
    this.currentSessionId = sessionId;

    this.socket.on('connect', () => {
      // ✅ Join session room on connect
      this.socket!.emit('join_session', { session_id: sessionId });
    });

    this.socket.on('joined_session', (data) => {
      console.log(`Joined session room: ${data.session_id}`);
    });

    // No longer need to filter events by session_id
    this.socket.on('detection_event', (data) => {
      // Already scoped to this session, no filtering needed
      this.handleDetectionEvent(data);
    });
  }

  disconnect() {
    if (this.socket && this.currentSessionId) {
      this.socket.emit('leave_session', { session_id: this.currentSessionId });
      this.socket.disconnect();
    }
  }
}
```

### Day 10: Detection Buffering (Fix #12)

**New File:** `backend/services/detection_buffer.py`

```python
from collections import defaultdict
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class DetectionBuffer:
    """
    Buffers detections until video start confirmed.
    Prevents race condition where detection arrives before onPlay event.
    """

    def __init__(self):
        self.pending_detections: Dict[str, List[dict]] = defaultdict(list)

    def should_buffer(self, session_id: str, db: Session) -> bool:
        """Check if detections should be buffered for this session."""
        session = db.query(TestSession).get(session_id)

        if not session:
            return False

        # Buffer if sequence metadata not initialized yet
        if not session.sequence_metadata or 'video_timing' not in session.sequence_metadata:
            return True

        return False

    def buffer_detection(self, session_id: str, detection_data: dict):
        """Add detection to buffer."""
        self.pending_detections[session_id].append(detection_data)
        logger.info(
            f"Buffered detection for session {session_id} "
            f"(total buffered: {len(self.pending_detections[session_id])})"
        )

    def flush_buffered(self, session_id: str, db: Session) -> int:
        """Process all buffered detections for a session."""
        buffered = self.pending_detections.pop(session_id, [])

        if not buffered:
            return 0

        logger.info(f"Flushing {len(buffered)} buffered detections for session {session_id}")

        from services.dedicated_labjack_monitor import create_detection_event

        for detection_data in buffered:
            try:
                create_detection_event(session_id, detection_data, db)
            except Exception as e:
                logger.error(f"Failed to create buffered detection: {e}")

        db.commit()
        return len(buffered)

# Global instance
detection_buffer = DetectionBuffer()
```

**Update:** `backend/services/dedicated_labjack_monitor.py`

```python
from services.detection_buffer import detection_buffer

def process_voltage_detection(session_id, voltage, t_detection, db):
    """Process detection with buffering support."""

    detection_data = {
        'voltage': voltage,
        'timestamp': t_detection,
        'video_relative_timestamp': None  # Calculated later
    }

    # Check if should buffer
    if detection_buffer.should_buffer(session_id, db):
        detection_buffer.buffer_detection(session_id, detection_data)
        logger.warning(f"Detection buffered for {session_id} - video not started yet")
        return None

    # Process immediately
    return create_detection_event(session_id, detection_data, db)

# When video starts, flush buffer
def handle_video_start(session_id, video_id, db):
    """Called when frontend emits 'video_started' event."""
    # ... existing video start logic ...

    # ✅ NEW: Flush buffered detections
    flushed_count = detection_buffer.flush_buffered(session_id, db)
    if flushed_count > 0:
        logger.info(f"Flushed {flushed_count} buffered detections for {session_id}")
```

### Day 11: Backend Timeout Mechanism (Fix #1)

**New File:** `backend/services/session_monitor.py`

```python
import asyncio
from datetime import datetime, timedelta
from typing import Set
import logging

logger = logging.getLogger(__name__)

class SessionMonitor:
    """
    Monitors session health and auto-fails stalled sessions.
    Prevents sessions from being stuck in 'running' state indefinitely.
    """

    def __init__(self, db_session_factory):
        self.db_session_factory = db_session_factory
        self.monitored_sessions: Set[str] = set()
        self.running = False

    async def start(self):
        """Start monitoring loop."""
        self.running = True
        logger.info("Session monitor started")

        while self.running:
            try:
                await self.check_all_sessions()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Session monitor error: {e}")

    async def check_all_sessions(self):
        """Check all running sessions for timeouts."""
        db = self.db_session_factory()

        try:
            # Find sessions in 'created' or 'running' state
            active_sessions = db.query(TestSession).filter(
                TestSession.status.in_(['created', 'running'])
            ).all()

            for session in active_sessions:
                await self.check_session_timeout(session, db)

        finally:
            db.close()

    async def check_session_timeout(self, session: TestSession, db: Session):
        """Check if session has timed out."""
        timeout_minutes = 10  # Configurable
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)

        # Check if session created too long ago
        if session.created_at < timeout_threshold:
            # Check if any progress made
            if session.has_video_sequence:
                video_results = db.query(SequenceVideoResult).filter_by(
                    sequence_id=session.sequence_id
                ).all()

                # Check if any videos started
                started_videos = [v for v in video_results if v.started_at is not None]

                if not started_videos:
                    # No videos started, timeout
                    await self.fail_session(session, "No video lifecycle events received", db)
                    return

                # Check if any videos are stuck "playing"
                for video_result in video_results:
                    if video_result.started_at and not video_result.ended_at:
                        video_duration = (datetime.utcnow() - video_result.started_at).total_seconds()
                        expected_duration_s = (video_result.expected_duration_ms or 30000) / 1000

                        if video_duration > expected_duration_s * 2:  # 2x expected duration
                            await self.fail_session(
                                session,
                                f"Video {video_result.video_id} stuck playing for {video_duration:.0f}s",
                                db
                            )
                            return
            else:
                # Single video session timeout
                await self.fail_session(session, "Session timeout: No activity", db)

    async def fail_session(self, session: TestSession, reason: str, db: Session):
        """Mark session as failed due to timeout."""
        logger.error(f"Session {session.id} timed out: {reason}")

        session.status = "VALIDATION_FAILED"
        session.failure_reason = reason
        session.failure_details = json.dumps({
            'timeout_type': 'lifecycle_event_timeout',
            'created_at': session.created_at.isoformat(),
            'failed_at': datetime.utcnow().isoformat()
        })

        db.commit()

        # Emit WebSocket event
        from backend.socketio_server import socketio
        socketio.emit('session_failed', {
            'session_id': session.id,
            'reason': reason
        }, room=session.id)

    def stop(self):
        """Stop monitoring loop."""
        self.running = False
        logger.info("Session monitor stopped")

# Global monitor instance
session_monitor = SessionMonitor(get_db)
```

**Start Monitor:** `backend/main.py`

```python
import asyncio
from services.session_monitor import session_monitor

@app.on_event("startup")
async def startup_event():
    # Start session monitor
    asyncio.create_task(session_monitor.start())

@app.on_event("shutdown")
async def shutdown_event():
    session_monitor.stop()
```

---

## Phase 5: Observability (Day 12)

**Fixes Deployed:** #15 (Centralize Formulas), #13 (Logging & Metrics)

### Centralize Metric Formulas (Fix #15)

**New File:** `backend/utils/metrics.py`

```python
"""
Centralized metric calculation formulas.
Single source of truth for all performance metrics.
"""

def calculate_precision(true_positives: int, false_positives: int) -> float:
    """
    Precision = TP / (TP + FP)

    Meaning: Of all detections, what percentage were correct?
    """
    if true_positives + false_positives == 0:
        return 0.0
    return true_positives / (true_positives + false_positives)


def calculate_recall(true_positives: int, false_negatives: int) -> float:
    """
    Recall = TP / (TP + FN)

    Meaning: Of all ground truth events, what percentage were detected?
    """
    if true_positives + false_negatives == 0:
        return 0.0
    return true_positives / (true_positives + false_negatives)


def calculate_f1_score(precision: float, recall: float) -> float:
    """
    F1 Score = 2 × (P × R) / (P + R)

    Meaning: Harmonic mean balancing precision and recall.
    """
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def calculate_all_metrics(true_positives: int, false_positives: int, false_negatives: int) -> dict:
    """Calculate all classification metrics."""
    precision = calculate_precision(true_positives, false_positives)
    recall = calculate_recall(true_positives, false_negatives)
    f1_score = calculate_f1_score(precision, recall)

    return {
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives
    }
```

**Update all services to use centralized formulas:**

```python
# In ground_truth_matching_service.py
from utils.metrics import calculate_all_metrics

def calculate_session_metrics(session_id):
    # ... count TP/FP/FN ...

    # ✅ Use centralized formula
    metrics_dict = calculate_all_metrics(tp_count, fp_count, fn_count)

    return SessionMetrics(**metrics_dict)
```

### Enhanced Logging (Fix #13)

**New File:** `backend/middleware/structured_logging.py`

```python
import logging
import json
from datetime import datetime
from fastapi import Request
import time

logger = logging.getLogger(__name__)

class StructuredLoggingMiddleware:
    """
    Log all API requests with structured data.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, request: Request, call_next):
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        start_time = time.time()

        # Log request
        logger.info("API Request", extra={
            'request_id': request_id,
            'method': request.method,
            'path': request.url.path,
            'client_ip': request.client.host
        })

        try:
            response = await call_next(request)

            duration = time.time() - start_time

            # Log response
            logger.info("API Response", extra={
                'request_id': request_id,
                'status_code': response.status_code,
                'duration_ms': duration * 1000
            })

            return response

        except Exception as e:
            duration = time.time() - start_time

            logger.error("API Error", extra={
                'request_id': request_id,
                'error': str(e),
                'duration_ms': duration * 1000
            }, exc_info=True)

            raise

# Add to main.py
from middleware.structured_logging import StructuredLoggingMiddleware

app.add_middleware(StructuredLoggingMiddleware)
```

**Instrument Key Operations:**

```python
# In session_completion_service.py
import logging
import time

logger = logging.getLogger(__name__)

def complete_test_session(session_id):
    logger.info("Session completion started", extra={'session_id': session_id})
    start_time = time.time()

    try:
        with db.begin():
            # ... completion logic ...

            duration = time.time() - start_time
            logger.info(
                "Session completed successfully",
                extra={
                    'session_id': session_id,
                    'duration_seconds': duration,
                    'outcome': session.outcome,
                    'metrics': {
                        'precision': session.precision,
                        'recall': session.recall,
                        'f1_score': session.f1_score
                    }
                }
            )

    except ValidationFailedException as e:
        logger.warning(
            "Session validation failed",
            extra={
                'session_id': session_id,
                'failure_reason': str(e)
            }
        )

    except Exception as e:
        logger.error(
            "Session completion error",
            extra={'session_id': session_id},
            exc_info=True
        )
```

**Prometheus Metrics:**

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
session_completions = Counter(
    'session_completions_total',
    'Total session completions',
    ['status']  # completed, validation_failed, error
)

gt_matching_duration = Histogram(
    'gt_matching_duration_seconds',
    'Ground truth matching duration',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

active_sessions = Gauge(
    'active_sessions',
    'Number of sessions currently running'
)

# Instrument functions
@gt_matching_duration.time()
def match_detections_to_ground_truth(session_id, tolerance_ms):
    # ... matching logic ...
    pass

# Track completions
def complete_test_session(session_id):
    try:
        # ... completion logic ...
        session_completions.labels(status='completed').inc()
    except ValidationFailedException:
        session_completions.labels(status='validation_failed').inc()
    except Exception:
        session_completions.labels(status='error').inc()
```

---

## Post-Deployment Validation

### Comprehensive Smoke Tests

```bash
# Script: scripts/post_deploy_smoke_test.sh

#!/bin/bash
set -e

echo "🚀 Running post-deployment smoke tests..."

# Test 1: Health check
echo "✓ Testing health endpoint..."
curl -f http://backend/health || exit 1

# Test 2: Create test session
echo "✓ Creating test session..."
SESSION_ID=$(python scripts/create_test_session.py --video-count=2 | jq -r '.session_id')

# Test 3: Verify outcome stored
echo "✓ Verifying outcome stored..."
OUTCOME=$(curl -s http://backend/api/test-sessions/$SESSION_ID/corrected-results | jq -r '.outcome')
[ -n "$OUTCOME" ] || { echo "❌ Outcome not stored"; exit 1; }

# Test 4: Approval workflow
echo "✓ Testing approval workflow..."
curl -f -X POST http://backend/api/test-sessions/$SESSION_ID/approval \
  -H "Content-Type: application/json" \
  -d '{"approver_id":"test_user","action":"approve"}' || exit 1

# Test 5: WebSocket connection
echo "✓ Testing WebSocket..."
node scripts/test_websocket.js || exit 1

# Test 6: Performance check
echo "✓ Checking performance metrics..."
LATENCY=$(curl -s http://backend/metrics | grep 'gt_matching_duration' | grep 'quantile="0.95"' | awk '{print $2}')
(( $(echo "$LATENCY < 0.5" | bc -l) )) || { echo "❌ Performance degraded"; exit 1; }

echo "✅ All smoke tests passed!"
```

### Monitoring Dashboard Validation

**Grafana Dashboard Checklist:**

- [ ] Session completion rate > 95% (last 1 hour)
- [ ] API p95 latency < 200ms
- [ ] GT matching p95 duration < 500ms
- [ ] WebSocket connection success rate > 99%
- [ ] Error rate < 0.5%
- [ ] No spike in 500 errors
- [ ] Database connection pool healthy (<80% utilization)

### User Acceptance Testing

**Test Scenarios:**

1. **Single Video Session**
   - Create session with 1 video
   - Verify completion succeeds
   - Check outcome determined
   - Approve session

2. **Multi-Video Sequence**
   - Create session with 3 videos
   - Verify all videos complete
   - Check aggregated metrics
   - Verify approval workflow

3. **Failure Scenarios**
   - Create session, close browser before video starts
   - Wait 10 minutes, verify timeout triggered
   - Check session marked as VALIDATION_FAILED

4. **API Schema Validation**
   - Fetch results, verify only camelCase present
   - Check no snake_case fields
   - Verify TypeScript types match

---

## Rollback Procedures

### Emergency Rollback (Complete System)

```bash
#!/bin/bash
# Script: scripts/emergency_rollback.sh

echo "🚨 EMERGENCY ROLLBACK INITIATED"

# 1. Revert backend code
cd /opt/hil-backend
git checkout v8.0-pre-fixes
systemctl restart hil-backend

# 2. Rollback database migrations
alembic downgrade -5  # Revert last 5 migrations (Phase 1-5)

# 3. Revert frontend
cd /opt/hil-frontend
git checkout v8.0-pre-fixes
npm run build
npm run deploy:production

# 4. Clear CDN cache
npm run cache:clear

# 5. Verify health
curl http://backend/health
curl http://frontend/

echo "✅ Rollback complete. System reverted to v8.0"
```

### Partial Rollback (Per Phase)

**Phase 1 Rollback (Foundation):**
```bash
# Code-only changes, no migrations
git revert <phase1-commits>
systemctl restart hil-backend
```

**Phase 2 Rollback (Approval):**
```bash
# Rollback migration
alembic downgrade -1

# Revert code
git revert <phase2-commits>
systemctl restart hil-backend
```

**Phase 3 Rollback (API):**
```bash
# Re-enable dual-format API
git checkout v8.1-phase3-dual-format
systemctl restart hil-backend
```

---

## Troubleshooting Guide

### Issue: Sessions Stuck in "Running" State

**Symptoms:**
- Sessions never complete
- Metrics not calculated
- Approval workflow not triggered

**Diagnosis:**
```bash
# Check session status
psql -d hil_production -c "SELECT id, status, created_at FROM test_sessions WHERE status='running' ORDER BY created_at DESC LIMIT 10;"

# Check for missing lifecycle events
psql -d hil_production -c "SELECT svr.video_id, svr.started_at, svr.ended_at FROM sequence_video_results svr WHERE svr.started_at IS NULL OR svr.ended_at IS NULL;"
```

**Resolution:**
```python
# Manual completion script
python scripts/manual_complete_session.py --session-id=<session_id>
```

### Issue: Double-Matching Detected

**Symptoms:**
- TP count higher than GT count
- Precision > 1.0

**Diagnosis:**
```sql
-- Find detections matched to multiple GTs
SELECT detection_event_id, COUNT(*) as match_count
FROM detection_comparisons
WHERE match_type = 'TP'
GROUP BY detection_event_id
HAVING COUNT(*) > 1;
```

**Resolution:**
- Deploy Fix #5 hotfix immediately
- Reprocess affected sessions

### Issue: API Schema Errors

**Symptoms:**
- TypeScript errors in frontend
- API calls failing
- "undefined" values in UI

**Diagnosis:**
```bash
# Check API response format
curl http://backend/api/enhanced-hil/test-sessions/{id}/corrected-results | jq 'keys'

# Should show camelCase only: sessionId, groundTruthComparison, etc.
# If shows both camelCase and snake_case: dual-format still active (Phase 3 incomplete)
```

**Resolution:**
- Verify frontend deployed with v8.1-phase3-camelcase
- Clear CDN cache
- Instruct users to hard-refresh (Ctrl+F5)

---

**Document Status:** Production-Ready Deployment Guide
**Review Required:** DevOps Lead, QA Lead
**Deployment Authorization:** Required before Phase 1 execution
