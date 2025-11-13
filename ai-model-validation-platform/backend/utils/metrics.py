"""
Production Metrics Instrumentation with Prometheus

Provides comprehensive metrics collection for:
- Session completion tracking
- Detection event processing
- Ground truth matching performance
- API request latency
- System resource usage
- Business KPIs
"""

from prometheus_client import Counter, Histogram, Gauge, Summary, Info
import time
from typing import Optional, Callable, Any
from functools import wraps


# ============================================================================
# Session Metrics
# ============================================================================

session_completions_total = Counter(
    'hil_session_completions_total',
    'Total number of test session completions',
    ['status', 'outcome']  # status: success/validation_failed/error, outcome: PASS/FAIL/CONDITIONAL_PASS
)

session_duration_seconds = Histogram(
    'hil_session_duration_seconds',
    'Session completion duration in seconds',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

active_sessions = Gauge(
    'hil_active_sessions',
    'Number of currently active test sessions'
)


# ============================================================================
# Detection Metrics
# ============================================================================

detection_events_total = Counter(
    'hil_detection_events_total',
    'Total number of detection events processed',
    ['session_id', 'classification']  # classification: TP/FP/FN
)

detection_latency_ms = Histogram(
    'hil_detection_latency_milliseconds',
    'Detection latency in milliseconds',
    buckets=[10, 25, 50, 75, 100, 150, 200, 300, 500, 1000]
)

detections_per_video = Histogram(
    'hil_detections_per_video',
    'Number of detections per video',
    buckets=[5, 10, 20, 30, 50, 100, 200]
)


# ============================================================================
# Ground Truth Matching Metrics
# ============================================================================

matching_duration_seconds = Histogram(
    'hil_gt_matching_duration_seconds',
    'Ground truth matching algorithm duration',
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

matching_pairs_total = Counter(
    'hil_gt_matching_pairs_total',
    'Total ground truth matching pairs processed',
    ['match_type']  # TP/FP/FN
)

temporal_iou_score = Histogram(
    'hil_temporal_iou_score',
    'Temporal IoU scores for matched pairs',
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)


# ============================================================================
# API Performance Metrics
# ============================================================================

api_request_duration_seconds = Histogram(
    'hil_api_request_duration_seconds',
    'API request duration in seconds',
    ['endpoint', 'method', 'status_code'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

api_requests_total = Counter(
    'hil_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status_code']
)

slow_requests_total = Counter(
    'hil_slow_requests_total',
    'Number of slow API requests (>1s)',
    ['endpoint']
)


# ============================================================================
# Database Metrics
# ============================================================================

db_query_duration_seconds = Histogram(
    'hil_db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

db_connections_active = Gauge(
    'hil_db_connections_active',
    'Number of active database connections'
)

db_queries_total = Counter(
    'hil_db_queries_total',
    'Total database queries',
    ['operation', 'table', 'status']  # status: success/error
)


# ============================================================================
# Business KPI Metrics
# ============================================================================

test_pass_rate = Gauge(
    'hil_test_pass_rate',
    'Percentage of tests that pass',
    ['time_window']  # 1h, 24h, 7d
)

mean_precision = Gauge(
    'hil_mean_precision',
    'Mean precision across recent sessions',
    ['time_window']
)

mean_recall = Gauge(
    'hil_mean_recall',
    'Mean recall across recent sessions',
    ['time_window']
)

mean_f1_score = Gauge(
    'hil_mean_f1_score',
    'Mean F1 score across recent sessions',
    ['time_window']
)


# ============================================================================
# WebSocket Metrics
# ============================================================================

websocket_connections_active = Gauge(
    'hil_websocket_connections_active',
    'Number of active WebSocket connections'
)

websocket_events_total = Counter(
    'hil_websocket_events_total',
    'Total WebSocket events emitted',
    ['event_type']  # detection_event, session_completed, etc.
)

websocket_errors_total = Counter(
    'hil_websocket_errors_total',
    'Total WebSocket errors',
    ['error_type']
)


# ============================================================================
# System Metrics
# ============================================================================

validation_failures_total = Counter(
    'hil_validation_failures_total',
    'Total validation failures',
    ['failure_reason']  # missing_timestamps, null_video_ids, etc.
)

race_conditions_detected = Counter(
    'hil_race_conditions_detected',
    'Number of race conditions detected and recovered',
    ['race_type']  # null_video_id, early_detection, etc.
)

null_video_id_reassignments = Counter(
    'hil_null_video_id_reassignments',
    'Number of NULL video_id reassignments during completion'
)


# ============================================================================
# Decorator Functions for Easy Instrumentation
# ============================================================================

def track_session_completion(func: Callable) -> Callable:
    """Decorator to track session completion metrics"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        active_sessions.inc()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # Assume result contains session info
            status = getattr(result, 'status', 'success')
            outcome = getattr(result, 'outcome', 'UNKNOWN')

            session_completions_total.labels(
                status=status,
                outcome=outcome
            ).inc()

            session_duration_seconds.observe(duration)

            return result

        except Exception as e:
            duration = time.time() - start_time
            session_completions_total.labels(
                status='error',
                outcome='ERROR'
            ).inc()
            session_duration_seconds.observe(duration)
            raise

        finally:
            active_sessions.dec()

    return wrapper


def track_api_request(endpoint: str, method: str):
    """Decorator to track API request metrics"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status_code = 500  # Default to error

            try:
                result = func(*args, **kwargs)
                status_code = 200
                return result

            except Exception as e:
                # Extract status code from exception if available
                if hasattr(e, 'status_code'):
                    status_code = e.status_code
                raise

            finally:
                duration = time.time() - start_time

                api_request_duration_seconds.labels(
                    endpoint=endpoint,
                    method=method,
                    status_code=str(status_code)
                ).observe(duration)

                api_requests_total.labels(
                    endpoint=endpoint,
                    method=method,
                    status_code=str(status_code)
                ).inc()

                if duration > 1.0:
                    slow_requests_total.labels(endpoint=endpoint).inc()

        return wrapper
    return decorator


def track_matching_performance(func: Callable) -> Callable:
    """Decorator to track ground truth matching performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            matching_duration_seconds.observe(duration)

            # Track matching results
            if hasattr(result, 'true_positives'):
                matching_pairs_total.labels(match_type='TP').inc(result.true_positives)
            if hasattr(result, 'false_positives'):
                matching_pairs_total.labels(match_type='FP').inc(result.false_positives)
            if hasattr(result, 'false_negatives'):
                matching_pairs_total.labels(match_type='FN').inc(result.false_negatives)

            return result

        except Exception as e:
            duration = time.time() - start_time
            matching_duration_seconds.observe(duration)
            raise

    return wrapper


def track_database_query(operation: str, table: str):
    """Decorator to track database query performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            status = 'error'

            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result

            except Exception:
                raise

            finally:
                duration = time.time() - start_time

                db_query_duration_seconds.labels(
                    operation=operation,
                    table=table
                ).observe(duration)

                db_queries_total.labels(
                    operation=operation,
                    table=table,
                    status=status
                ).inc()

        return wrapper
    return decorator


# Example usage patterns
"""
# Session completion tracking
from utils.metrics import track_session_completion

@track_session_completion
def complete_test_session(session_id: str):
    # ... completion logic ...
    return session  # Must have .status and .outcome attributes

# API request tracking
from utils.metrics import track_api_request

@track_api_request(endpoint="/api/sessions", method="POST")
async def create_session(request):
    # ... session creation logic ...
    return response

# Ground truth matching
from utils.metrics import track_matching_performance

@track_matching_performance
def match_detections_to_ground_truth(session_id, tolerance_ms):
    # ... matching logic ...
    return MatchingResults(true_positives=18, false_positives=4, false_negatives=6)

# Manual metric recording
from utils.metrics import detection_latency_ms, detection_events_total

detection_latency_ms.observe(latency_value_ms)
detection_events_total.labels(
    session_id=session_id,
    classification='TP'
).inc()
"""
