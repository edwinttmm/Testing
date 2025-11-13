"""
Performance Monitoring Middleware

Tracks API request performance and logs slow requests.
Integrates with Prometheus metrics and structured logging.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import uuid

from utils.logging_config import api_logger, set_correlation_id, clear_correlation_id
from utils.metrics import (
    api_request_duration_seconds,
    api_requests_total,
    slow_requests_total
)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API request performance.

    Features:
    - Request duration tracking
    - Slow request logging (>1s)
    - Prometheus metrics collection
    - Correlation ID generation
    - Structured logging
    """

    def __init__(self, app, slow_threshold_seconds: float = 1.0):
        super().__init__(app)
        self.slow_threshold_seconds = slow_threshold_seconds

    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Add correlation ID to request state
        request.state.correlation_id = correlation_id

        # Start timing
        start_time = time.time()

        # Extract request info
        endpoint = request.url.path
        method = request.method

        # Log request start
        api_logger.debug(
            f"Request started: {method} {endpoint}",
            endpoint=endpoint,
            method=method,
            correlation_id=correlation_id
        )

        # Process request
        response = None
        status_code = 500  # Default to error

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response

        except Exception as e:
            # Log exception
            api_logger.error(
                f"Request failed: {method} {endpoint}",
                exc_info=True,
                endpoint=endpoint,
                method=method,
                error=str(e)
            )
            raise

        finally:
            # Calculate duration
            duration = time.time() - start_time
            duration_ms = duration * 1000

            # Record Prometheus metrics
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

            # Log slow requests
            if duration > self.slow_threshold_seconds:
                slow_requests_total.labels(endpoint=endpoint).inc()

                api_logger.warning(
                    f"Slow request detected: {method} {endpoint}",
                    endpoint=endpoint,
                    method=method,
                    duration_ms=round(duration_ms, 2),
                    status_code=status_code,
                    threshold_ms=self.slow_threshold_seconds * 1000
                )

            # Log request completion
            api_logger.info(
                f"Request completed: {method} {endpoint}",
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=round(duration_ms, 2)
            )

            # Add performance headers to response
            if response:
                response.headers['X-Request-ID'] = correlation_id
                response.headers['X-Response-Time'] = f"{duration_ms:.2f}ms"

            # Clear correlation ID
            clear_correlation_id()


# Example integration in main.py:
"""
from middleware.performance import PerformanceMiddleware

app.add_middleware(
    PerformanceMiddleware,
    slow_threshold_seconds=1.0  # Log requests slower than 1 second
)
"""
