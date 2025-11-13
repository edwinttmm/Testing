"""
Error Tracking and Monitoring Integration

Provides Sentry integration for production error tracking with:
- Exception capture and aggregation
- Performance monitoring
- Release tracking
- User context enrichment
- Custom tags and breadcrumbs
"""

import os
from typing import Optional, Dict, Any
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from utils.logging_config import StructuredLogger

logger = StructuredLogger(__name__)


def init_error_tracking(
    environment: str = "production",
    release: Optional[str] = None,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1
):
    """
    Initialize Sentry error tracking.

    Args:
        environment: Deployment environment (production, staging, development)
        release: Release version (e.g., "v1.2.3" or git commit hash)
        traces_sample_rate: Percentage of transactions to trace (0.0-1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0-1.0)

    Environment Variables:
        SENTRY_DSN: Sentry Data Source Name (required)
        ENVIRONMENT: Deployment environment (optional)
        RELEASE_VERSION: Release version (optional)
    """
    sentry_dsn = os.getenv('SENTRY_DSN')

    if not sentry_dsn:
        logger.warning(
            "Sentry DSN not configured - error tracking disabled",
            environment=environment
        )
        return

    # Get environment and release from env vars if not provided
    environment = environment or os.getenv('ENVIRONMENT', 'production')
    release = release or os.getenv('RELEASE_VERSION')

    try:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            release=release,

            # Integrations
            integrations=[
                FastApiIntegration(
                    transaction_style="endpoint"  # Group by endpoint not URL
                ),
                SqlalchemyIntegration(),
                RedisIntegration(),
            ],

            # Performance monitoring
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,

            # Additional configuration
            send_default_pii=False,  # Don't send personally identifiable info
            attach_stacktrace=True,   # Include stack traces
            max_breadcrumbs=50,       # Keep last 50 breadcrumbs

            # Custom tag defaults
            default_integrations=True,

            # Before send hook for filtering
            before_send=before_send_filter,
        )

        logger.info(
            "Sentry error tracking initialized",
            environment=environment,
            release=release,
            traces_sample_rate=traces_sample_rate
        )

    except Exception as e:
        logger.error(
            "Failed to initialize Sentry",
            exc_info=True,
            error=str(e)
        )


def before_send_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter events before sending to Sentry.

    Can be used to:
    - Drop uninteresting errors
    - Scrub sensitive data
    - Modify event data

    Return None to drop the event, or the modified event to send it.
    """
    # Example: Drop health check errors
    if 'exception' in event:
        exc_info = event['exception'].get('values', [{}])[0]
        exc_type = exc_info.get('type', '')

        # Drop certain error types
        if exc_type in ['HealthCheckException', 'ReadinessCheckException']:
            return None

    # Example: Scrub sensitive data from extra
    if 'extra' in event:
        sensitive_keys = ['password', 'token', 'api_key', 'secret']
        for key in sensitive_keys:
            if key in event['extra']:
                event['extra'][key] = '[REDACTED]'

    return event


def capture_exception(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
    level: str = "error"
):
    """
    Capture an exception and send to Sentry with additional context.

    Args:
        error: Exception to capture
        context: Additional context data
        tags: Custom tags for filtering/grouping
        level: Error level (fatal, error, warning, info, debug)

    Example:
        try:
            process_session(session_id)
        except Exception as e:
            capture_exception(
                e,
                context={'session_id': session_id},
                tags={'component': 'session_completion'},
                level='error'
            )
            raise
    """
    with sentry_sdk.push_scope() as scope:
        # Set error level
        scope.level = level

        # Add custom tags
        if tags:
            for key, value in tags.items():
                scope.set_tag(key, str(value))

        # Add context data
        if context:
            scope.set_context("custom", context)

        # Capture exception
        sentry_sdk.capture_exception(error)

        logger.error(
            "Exception captured and sent to Sentry",
            exc_info=True,
            error=str(error),
            tags=tags,
            context=context
        )


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: Optional[Dict[str, Any]] = None
):
    """
    Add a breadcrumb for debugging context.

    Breadcrumbs provide a trail of events leading up to an error.

    Args:
        message: Breadcrumb message
        category: Category for grouping (e.g., 'query', 'http', 'navigation')
        level: Severity level
        data: Additional data

    Example:
        add_breadcrumb(
            "Starting ground truth matching",
            category="matching",
            data={'session_id': session_id, 'tolerance_ms': 100}
        )
    """
    sentry_sdk.add_breadcrumb(
        message=message,
        category=category,
        level=level,
        data=data or {}
    )


def set_user_context(user_id: str, email: Optional[str] = None, username: Optional[str] = None):
    """
    Set user context for error tracking.

    Args:
        user_id: User identifier
        email: User email (optional)
        username: Username (optional)

    Example:
        set_user_context(
            user_id=current_user.id,
            email=current_user.email,
            username=current_user.username
        )
    """
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "username": username
    })


def set_session_context(session_id: str, session_data: Optional[Dict[str, Any]] = None):
    """
    Set session context for error tracking.

    Args:
        session_id: Test session identifier
        session_data: Additional session data

    Example:
        set_session_context(
            session_id=session.id,
            session_data={
                'video_count': 3,
                'status': 'running',
                'detection_count': 42
            }
        )
    """
    context = {"session_id": session_id}
    if session_data:
        context.update(session_data)

    sentry_sdk.set_context("session", context)


def start_transaction(name: str, op: str = "task") -> Any:
    """
    Start a performance transaction.

    Args:
        name: Transaction name (e.g., "session_completion")
        op: Operation type (task, http.server, db.query)

    Returns:
        Transaction object (use in context manager)

    Example:
        with start_transaction("session_completion", op="task") as transaction:
            # ... session completion logic ...
            transaction.set_tag("session_id", session_id)
            transaction.set_data("detection_count", 42)
    """
    return sentry_sdk.start_transaction(name=name, op=op)


# Example usage in service:
"""
from utils.error_tracking import (
    capture_exception,
    add_breadcrumb,
    set_session_context,
    start_transaction
)

def complete_test_session(session_id: str):
    # Set context for this operation
    set_session_context(session_id)

    # Start performance tracking
    with start_transaction("session_completion", op="task") as transaction:
        try:
            # Add breadcrumbs for debugging trail
            add_breadcrumb(
                "Validating video sequence",
                category="validation",
                data={'session_id': session_id}
            )

            validation = validate_video_sequence_completion(session_id)

            if not validation['valid']:
                add_breadcrumb(
                    "Validation failed",
                    category="validation",
                    level="error",
                    data=validation
                )
                raise ValidationError(validation['reason'])

            add_breadcrumb(
                "Starting ground truth matching",
                category="matching"
            )

            matching_results = match_detections_to_ground_truth(session_id)

            # Set transaction data
            transaction.set_data("tp_count", matching_results.true_positives)
            transaction.set_data("fp_count", matching_results.false_positives)

        except Exception as e:
            # Capture with additional context
            capture_exception(
                e,
                context={'session_id': session_id},
                tags={'component': 'session_completion'},
                level='error'
            )
            raise
"""
