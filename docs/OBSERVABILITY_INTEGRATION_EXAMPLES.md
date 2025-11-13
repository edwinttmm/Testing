# Observability Integration Examples

Quick reference for integrating production observability into existing services.

---

## Session Completion Service Integration

```python
# backend/services/session_completion_service.py

from utils.logging_config import session_logger
from utils.metrics import (
    track_session_completion,
    session_duration_seconds,
    validation_failures_total,
    null_video_id_reassignments
)
from utils.error_tracking import (
    capture_exception,
    add_breadcrumb,
    set_session_context,
    start_transaction
)
from models_audit import log_audit, AuditAction, ResourceType

@track_session_completion  # Automatic metrics tracking
def complete_test_session(session_id: str, db, user_id: str = None):
    """Complete test session with full observability"""

    # Set context for error tracking
    set_session_context(session_id, {'user_id': user_id})

    # Log start
    session_logger.info(
        "Session completion started",
        session_id=session_id,
        user_id=user_id
    )

    # Start performance transaction
    with start_transaction("session_completion", op="task") as transaction:
        try:
            # Add debug breadcrumb
            add_breadcrumb(
                "Validating video sequence",
                category="validation",
                data={'session_id': session_id}
            )

            # Validation
            if session.has_video_sequence:
                validation = validate_video_sequence_completion(session_id)

                if not validation['valid']:
                    # Track validation failure
                    validation_failures_total.labels(
                        failure_reason=validation['reason']
                    ).inc()

                    # Log failure
                    session_logger.error(
                        "Session validation failed",
                        session_id=session_id,
                        reason=validation['reason'],
                        missing_data=validation.get('missing_data')
                    )

                    # Audit log
                    log_audit(
                        db,
                        action=AuditAction.SESSION_FAILED,
                        resource_type=ResourceType.TEST_SESSION,
                        resource_id=session_id,
                        user_id=user_id,
                        success=False,
                        error_message=validation['reason'],
                        metadata={'validation': validation}
                    )

                    raise ValidationError(validation['reason'])

            # Reassign NULL video IDs
            add_breadcrumb("Reassigning NULL video IDs", category="fixing")
            null_count = reassign_null_video_ids(session_id)

            if null_count > 0:
                null_video_id_reassignments.inc(null_count)
                session_logger.warning(
                    "NULL video IDs reassigned",
                    session_id=session_id,
                    count=null_count
                )

            # Ground truth matching
            add_breadcrumb("Starting ground truth matching", category="matching")
            matching_results = match_detections_to_ground_truth(session_id)

            # Calculate metrics
            metrics = calculate_session_metrics(session_id)

            # Update session
            session.status = "completed"
            session.precision = metrics.precision
            session.recall = metrics.recall
            session.f1_score = metrics.f1_score
            db.commit()

            # Set transaction data
            transaction.set_data("tp_count", metrics.true_positives)
            transaction.set_data("precision", metrics.precision)
            transaction.set_data("recall", metrics.recall)

            # Audit log success
            log_audit(
                db,
                action=AuditAction.SESSION_COMPLETED,
                resource_type=ResourceType.TEST_SESSION,
                resource_id=session_id,
                changes={
                    'before': {'status': 'running'},
                    'after': {
                        'status': 'completed',
                        'precision': metrics.precision,
                        'recall': metrics.recall
                    }
                },
                user_id=user_id,
                metadata={
                    'true_positives': metrics.true_positives,
                    'false_positives': metrics.false_positives,
                    'false_negatives': metrics.false_negatives
                }
            )

            # Log success
            session_logger.info(
                "Session completed successfully",
                session_id=session_id,
                metrics={
                    'precision': metrics.precision,
                    'recall': metrics.recall,
                    'f1_score': metrics.f1_score
                },
                null_reassignments=null_count
            )

            return session

        except Exception as e:
            # Capture exception with context
            capture_exception(
                e,
                context={
                    'session_id': session_id,
                    'user_id': user_id
                },
                tags={
                    'component': 'session_completion',
                    'session_id': session_id
                },
                level='error'
            )

            # Log error
            session_logger.error(
                "Session completion failed",
                exc_info=True,
                session_id=session_id,
                error_type=type(e).__name__
            )

            raise
```

---

## Ground Truth Matching Service Integration

```python
# backend/services/ground_truth_matching_service.py

from utils.logging_config import matching_logger
from utils.metrics import (
    track_matching_performance,
    matching_pairs_total,
    temporal_iou_score
)

@track_matching_performance  # Automatic duration tracking
def match_detections_to_ground_truth(session_id: str, tolerance_ms: int = 100):
    """Match detections to ground truth with observability"""

    matching_logger.info(
        "Starting ground truth matching",
        session_id=session_id,
        tolerance_ms=tolerance_ms
    )

    try:
        # ... existing matching logic ...

        # Track results
        matching_pairs_total.labels(match_type='TP').inc(len(true_positives))
        matching_pairs_total.labels(match_type='FP').inc(len(false_positives))
        matching_pairs_total.labels(match_type='FN').inc(len(false_negatives))

        # Track temporal IoU scores
        for tp in true_positives:
            if tp.temporal_iou:
                temporal_iou_score.observe(tp.temporal_iou)

        # Log results
        matching_logger.info(
            "Ground truth matching completed",
            session_id=session_id,
            true_positives=len(true_positives),
            false_positives=len(false_positives),
            false_negatives=len(false_negatives),
            mean_iou=sum(tp.temporal_iou for tp in true_positives) / len(true_positives) if true_positives else 0
        )

        return MatchingResults(
            true_positives=len(true_positives),
            false_positives=len(false_positives),
            false_negatives=len(false_negatives)
        )

    except Exception as e:
        matching_logger.error(
            "Ground truth matching failed",
            exc_info=True,
            session_id=session_id,
            error=str(e)
        )
        raise
```

---

## Detection Event Processing Integration

```python
# backend/services/dedicated_labjack_monitor.py

from utils.logging_config import detection_logger
from utils.metrics import (
    detection_events_total,
    detection_latency_ms,
    race_conditions_detected
)

def process_voltage_detection(session_id: str, voltage: float, timestamp: float):
    """Process detection event with observability"""

    try:
        # Resolve video ID
        video_id = VideoIdResolver.resolve_video_id(
            session_id=session_id,
            timestamp_ms=video_relative_ms,
            sequence_metadata=session.sequence_metadata
        )

        # Track race condition
        if video_id is None:
            race_conditions_detected.labels(race_type='null_video_id').inc()
            detection_logger.warning(
                "Race condition: NULL video_id detected",
                session_id=session_id,
                timestamp_ms=video_relative_ms
            )

        # Create detection
        detection = DetectionEvent(
            session_id=session_id,
            video_id=video_id,
            voltage=voltage,
            timestamp=timestamp
        )
        db.add(detection)
        db.commit()

        # Track event
        detection_events_total.labels(
            session_id=session_id,
            classification='pending'
        ).inc()

        detection_logger.debug(
            "Detection event created",
            session_id=session_id,
            video_id=video_id,
            voltage=voltage
        )

    except Exception as e:
        detection_logger.error(
            "Detection event processing failed",
            exc_info=True,
            session_id=session_id,
            error=str(e)
        )
        raise
```

---

## API Endpoint Integration

```python
# backend/routers/test_sessions.py

from fastapi import APIRouter, HTTPException
from utils.logging_config import api_logger, set_correlation_id
from utils.metrics import track_api_request
from models_audit import log_audit, AuditAction, ResourceType

router = APIRouter()

@router.post("/{session_id}/complete")
@track_api_request(endpoint="/sessions/{id}/complete", method="POST")
async def complete_session_endpoint(
    session_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Complete session with full observability"""

    # Set correlation ID for request
    set_correlation_id(str(uuid.uuid4()))

    api_logger.info(
        "Session completion request received",
        session_id=session_id,
        user_id=current_user.id
    )

    try:
        session = complete_test_session(
            session_id=session_id,
            db=db,
            user_id=current_user.id
        )

        return {
            "session_id": session.id,
            "status": session.status,
            "precision": session.precision,
            "recall": session.recall
        }

    except ValidationError as e:
        api_logger.warning(
            "Session completion validation failed",
            session_id=session_id,
            error=str(e)
        )
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        api_logger.error(
            "Session completion request failed",
            exc_info=True,
            session_id=session_id
        )
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## Main Application Integration

```python
# backend/main.py

from fastapi import FastAPI
from middleware.performance import PerformanceMiddleware
from routers import health
from utils.error_tracking import init_error_tracking
from utils.logging_config import api_logger
import os

# Initialize app
app = FastAPI(title="HIL Test Platform")

# Initialize error tracking
init_error_tracking(
    environment=os.getenv('ENVIRONMENT', 'production'),
    release=os.getenv('RELEASE_VERSION', 'dev'),
    traces_sample_rate=0.1
)

# Add performance monitoring
app.add_middleware(
    PerformanceMiddleware,
    slow_threshold_seconds=1.0
)

# Add health check router
app.include_router(health.router)

# Startup event
@app.on_event("startup")
async def startup_event():
    api_logger.info(
        "HIL Backend starting",
        version=os.getenv('RELEASE_VERSION', 'dev'),
        environment=os.getenv('ENVIRONMENT', 'dev')
    )

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    api_logger.info("HIL Backend shutting down")
```

---

## Database Migration for Audit Logs

```python
# backend/migrations/versions/add_audit_logs.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

def upgrade():
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('user_id', sa.String()),
        sa.Column('user_email', sa.String()),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('resource_id', sa.String(), nullable=False),
        sa.Column('changes', JSON),
        sa.Column('metadata', JSON),
        sa.Column('ip_address', sa.String()),
        sa.Column('user_agent', sa.String()),
        sa.Column('correlation_id', sa.String()),
        sa.Column('session_id', sa.String()),
        sa.Column('success', sa.Integer(), default=1),
        sa.Column('error_message', sa.String()),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('idx_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_correlation', 'audit_logs', ['correlation_id'])

def downgrade():
    op.drop_table('audit_logs')
```

---

## Quick Deployment Checklist

1. **Install Dependencies:**
```bash
pip install prometheus-client sentry-sdk psutil
```

2. **Set Environment Variables:**
```bash
export SENTRY_DSN="https://your-dsn@sentry.io/project"
export ENVIRONMENT="production"
export RELEASE_VERSION="v1.0.0"
```

3. **Run Migrations:**
```bash
alembic upgrade head
```

4. **Update main.py:**
- Add performance middleware
- Add health router
- Initialize error tracking

5. **Configure Prometheus:**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'hil-backend'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/health/metrics'
```

6. **Verify Health Checks:**
```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/health
curl http://localhost:8000/health/metrics
```

7. **Monitor Logs:**
```bash
# Logs will be in JSON format
tail -f /var/log/hil-backend.log | jq
```

---

**All components ready for production deployment.**
