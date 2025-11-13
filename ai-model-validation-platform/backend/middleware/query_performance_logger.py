"""
Query Performance Logging Middleware
Monitors and logs database query counts per request to detect N+1 query patterns
"""
from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time
import logging
from typing import Dict, List
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

# Thread-local storage for query tracking
_local = threading.local()


class QueryCounter:
    """Track query counts and timing per request"""

    def __init__(self):
        self.query_count = 0
        self.queries: List[Dict] = []
        self.start_time = time.time()

    def add_query(self, statement: str, duration: float):
        """Add a query to the counter"""
        self.query_count += 1
        self.queries.append({
            "statement": statement[:200],  # Truncate long queries
            "duration_ms": duration * 1000,
            "timestamp": time.time()
        })

    def get_stats(self) -> Dict:
        """Get query statistics"""
        total_duration = time.time() - self.start_time
        query_time = sum(q["duration_ms"] for q in self.queries)

        return {
            "query_count": self.query_count,
            "total_request_time_ms": total_duration * 1000,
            "total_query_time_ms": query_time,
            "query_percentage": (query_time / (total_duration * 1000)) * 100 if total_duration > 0 else 0,
            "queries": self.queries
        }


def get_query_counter() -> QueryCounter:
    """Get or create query counter for current thread"""
    if not hasattr(_local, 'counter'):
        _local.counter = QueryCounter()
    return _local.counter


def reset_query_counter():
    """Reset query counter for current thread"""
    _local.counter = QueryCounter()


@contextmanager
def query_counter_context():
    """Context manager for query counting"""
    reset_query_counter()
    yield get_query_counter()


# SQLAlchemy event listener for query tracking
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query start time"""
    context._query_start_time = time.time()


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Track query completion and add to counter"""
    if hasattr(context, '_query_start_time'):
        duration = time.time() - context._query_start_time
        counter = get_query_counter()
        counter.add_query(statement, duration)


async def query_performance_middleware(request: Request, call_next):
    """
    Middleware to track and log query performance per request

    Warns if:
    - Query count > 10 for a single request (potential N+1 pattern)
    - Query time > 50% of total request time (database bottleneck)
    """
    # Skip static files and health checks
    if request.url.path.startswith(("/static", "/health", "/docs", "/openapi.json")):
        return await call_next(request)

    # Initialize query counter for this request
    reset_query_counter()

    # Process request
    response = await call_next(request)

    # Get query statistics
    counter = get_query_counter()
    stats = counter.get_stats()

    # Log query performance
    log_level = logging.INFO
    warnings = []

    # Check for potential N+1 queries
    if stats["query_count"] > 10:
        log_level = logging.WARNING
        warnings.append(f"High query count: {stats['query_count']} queries (potential N+1 pattern)")

    # Check for database bottleneck
    if stats["query_percentage"] > 50 and stats["total_request_time_ms"] > 100:
        log_level = logging.WARNING
        warnings.append(f"Database bottleneck: {stats['query_percentage']:.1f}% of request time")

    # Check for slow queries
    slow_queries = [q for q in stats["queries"] if q["duration_ms"] > 100]
    if slow_queries:
        log_level = logging.WARNING
        warnings.append(f"Slow queries detected: {len(slow_queries)} queries > 100ms")

    # Log with appropriate level
    log_message = (
        f"{request.method} {request.url.path} - "
        f"{stats['query_count']} queries, "
        f"{stats['total_query_time_ms']:.2f}ms query time, "
        f"{stats['total_request_time_ms']:.2f}ms total"
    )

    if warnings:
        log_message += f" - WARNINGS: {'; '.join(warnings)}"

    logger.log(log_level, log_message)

    # Add query stats to response headers (for development)
    response.headers["X-Query-Count"] = str(stats["query_count"])
    response.headers["X-Query-Time-Ms"] = f"{stats['total_query_time_ms']:.2f}"

    return response


def init_query_logging(app):
    """Initialize query performance logging for FastAPI app"""
    app.middleware("http")(query_performance_middleware)
    logger.info("Query performance logging middleware initialized")
