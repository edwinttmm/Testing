"""
Audit Log Model for Accountability and Compliance

Tracks all critical operations for:
- Regulatory compliance
- Security auditing
- Debugging complex issues
- User accountability
"""

from sqlalchemy import Column, String, DateTime, JSON, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class AuditLog(Base):
    """
    Comprehensive audit trail for all critical operations.

    Records:
    - Who performed the action (user_id)
    - What action was performed (action type)
    - When it happened (timestamp)
    - What resource was affected (resource_type, resource_id)
    - What changed (changes dict with before/after)
    - Where it came from (ip_address, user_agent)
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # When
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Who
    user_id = Column(String, index=True)  # User who performed action
    user_email = Column(String)           # User email at time of action

    # What
    action = Column(String, nullable=False, index=True)  # e.g., 'session_created', 'session_approved'
    resource_type = Column(String, nullable=False, index=True)  # e.g., 'test_session', 'detection_event'
    resource_id = Column(String, nullable=False, index=True)    # ID of affected resource

    # Details
    changes = Column(JSON)  # Before/after state: {'before': {...}, 'after': {...}}
    metadata = Column(JSON)  # Additional context

    # Where
    ip_address = Column(String)
    user_agent = Column(String)

    # Request context
    correlation_id = Column(String, index=True)  # For request tracing
    session_id = Column(String, index=True)      # Test session (if applicable)

    # Result
    success = Column(Integer, default=1)  # 1 = success, 0 = failure
    error_message = Column(String)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_action_timestamp', 'action', 'timestamp'),
    )


# Common action types (constants for consistency)
class AuditAction:
    # Session lifecycle
    SESSION_CREATED = "session_created"
    SESSION_STARTED = "session_started"
    SESSION_COMPLETED = "session_completed"
    SESSION_FAILED = "session_failed"
    SESSION_APPROVED = "session_approved"
    SESSION_REJECTED = "session_rejected"

    # Detection events
    DETECTION_CREATED = "detection_created"
    DETECTION_CLASSIFIED = "detection_classified"
    DETECTION_REASSIGNED = "detection_reassigned"

    # Ground truth
    GROUND_TRUTH_UPLOADED = "ground_truth_uploaded"
    GROUND_TRUTH_UPDATED = "ground_truth_updated"
    GROUND_TRUTH_DELETED = "ground_truth_deleted"

    # Matching
    MATCHING_COMPLETED = "matching_completed"
    METRICS_CALCULATED = "metrics_calculated"

    # Configuration
    CONFIG_UPDATED = "config_updated"
    THRESHOLD_CHANGED = "threshold_changed"


# Resource types
class ResourceType:
    TEST_SESSION = "test_session"
    DETECTION_EVENT = "detection_event"
    GROUND_TRUTH = "ground_truth_object"
    VIDEO = "video"
    PROJECT = "project"
    USER = "user"
    CONFIG = "configuration"


# Example audit logging functions
"""
from models_audit import AuditLog, AuditAction, ResourceType
from utils.logging_config import get_correlation_id

def log_audit(
    db,
    action: str,
    resource_type: str,
    resource_id: str,
    changes: dict = None,
    user_id: str = None,
    user_email: str = None,
    session_id: str = None,
    ip_address: str = None,
    user_agent: str = None,
    metadata: dict = None,
    success: bool = True,
    error_message: str = None
):
    '''
    Create audit log entry.

    Example:
        log_audit(
            db,
            action=AuditAction.SESSION_APPROVED,
            resource_type=ResourceType.TEST_SESSION,
            resource_id=session_id,
            changes={
                'before': {'approval_status': 'pending'},
                'after': {'approval_status': 'approved', 'approved_by': user_id}
            },
            user_id=current_user.id,
            user_email=current_user.email,
            ip_address=request.client.host,
            user_agent=request.headers.get('User-Agent'),
            metadata={'comments': 'Looks good, approved for deployment'}
        )
    '''
    audit = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        changes=changes,
        user_id=user_id,
        user_email=user_email,
        session_id=session_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
        correlation_id=get_correlation_id(),
        success=1 if success else 0,
        error_message=error_message
    )

    db.add(audit)
    db.commit()

    return audit.id


# Example usage in session completion:
def complete_test_session(session_id: str, db, user_id: str = None):
    session = db.query(TestSession).get(session_id)
    old_status = session.status

    try:
        # ... completion logic ...

        session.status = "completed"
        session.precision = metrics.precision
        session.recall = metrics.recall
        db.commit()

        # Audit successful completion
        log_audit(
            db,
            action=AuditAction.SESSION_COMPLETED,
            resource_type=ResourceType.TEST_SESSION,
            resource_id=session_id,
            changes={
                'before': {
                    'status': old_status,
                    'precision': None,
                    'recall': None
                },
                'after': {
                    'status': 'completed',
                    'precision': metrics.precision,
                    'recall': metrics.recall
                }
            },
            user_id=user_id,
            session_id=session_id,
            metadata={
                'tp_count': metrics.true_positives,
                'fp_count': metrics.false_positives,
                'fn_count': metrics.false_negatives
            },
            success=True
        )

    except Exception as e:
        # Audit failure
        log_audit(
            db,
            action=AuditAction.SESSION_COMPLETED,
            resource_type=ResourceType.TEST_SESSION,
            resource_id=session_id,
            user_id=user_id,
            session_id=session_id,
            success=False,
            error_message=str(e)
        )
        raise


# Query examples:
# Get all actions by user
user_actions = db.query(AuditLog).filter(
    AuditLog.user_id == user_id
).order_by(AuditLog.timestamp.desc()).limit(100).all()

# Get audit trail for specific session
session_audit = db.query(AuditLog).filter(
    AuditLog.session_id == session_id
).order_by(AuditLog.timestamp).all()

# Get all approvals in last 24 hours
from datetime import timedelta
recent_approvals = db.query(AuditLog).filter(
    AuditLog.action == AuditAction.SESSION_APPROVED,
    AuditLog.timestamp >= datetime.utcnow() - timedelta(days=1)
).all()

# Get failed operations
failures = db.query(AuditLog).filter(
    AuditLog.success == 0
).order_by(AuditLog.timestamp.desc()).all()
"""
