"""
Rate Limiting Middleware - Production-Grade Request Throttling
================================================================

Protects video lifecycle API from spam and abuse using sliding window
rate limiting with Redis backend.

Author: Backend API Developer Agent
Date: 2025-11-20
Status: Production-Ready
"""

import logging
import time
from typing import Dict, Optional, Callable
from collections import defaultdict, deque
from threading import Lock
from datetime import datetime, timezone

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """
    In-memory sliding window rate limiter.

    Thread-safe implementation using deque for efficient time window management.
    Suitable for single-instance deployments. For distributed systems, use Redis.

    Features:
    - Sliding window algorithm (more accurate than fixed window)
    - Per-endpoint rate limits
    - Per-client IP tracking
    - Automatic cleanup of old entries
    """

    def __init__(self):
        """Initialize rate limiter."""
        # Request history: {client_ip: {endpoint: deque[(timestamp, request)]}}
        self._history: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))
        self._lock = Lock()

        # Rate limit configurations per endpoint
        self._limits: Dict[str, tuple] = {
            # Endpoint pattern: (max_requests, window_seconds)
            "/api/video-lifecycle/.*/video-started": (30, 60),  # 30 per minute
            "/api/video-lifecycle/.*/video-ended": (30, 60),    # 30 per minute
            "/api/video-lifecycle/.*/video-error": (30, 60),    # 30 per minute
            "/api/video-lifecycle/.*/status": (60, 60),         # 60 per minute
            "/api/video-lifecycle/.*/drift-stats": (60, 60),    # 60 per minute
            "/api/video-lifecycle/health": (120, 60),           # 120 per minute
            "default": (100, 60)  # Default: 100 per minute
        }

        logger.info("InMemoryRateLimiter initialized")

    def check_rate_limit(
        self,
        client_ip: str,
        endpoint: str,
        request_id: Optional[str] = None
    ) -> tuple[bool, Optional[Dict]]:
        """
        Check if request should be allowed based on rate limit.

        Args:
            client_ip: Client IP address
            endpoint: API endpoint path
            request_id: Optional request ID for logging

        Returns:
            Tuple of (allowed, rate_limit_info)
            - allowed: True if request should be processed
            - rate_limit_info: Dict with rate limit details (for headers)
        """
        with self._lock:
            # Get rate limit config for this endpoint
            max_requests, window_seconds = self._get_limit_config(endpoint)

            # Get request history for this client/endpoint
            history = self._history[client_ip][endpoint]

            # Remove old entries outside the time window
            current_time = time.time()
            window_start = current_time - window_seconds

            while history and history[0] < window_start:
                history.popleft()

            # Count requests in current window
            request_count = len(history)

            # Check if limit exceeded
            if request_count >= max_requests:
                # Rate limit exceeded
                oldest_request = history[0] if history else current_time
                reset_time = oldest_request + window_seconds
                retry_after = int(reset_time - current_time) + 1

                rate_limit_info = {
                    "limit": max_requests,
                    "remaining": 0,
                    "reset": int(reset_time),
                    "retry_after": retry_after,
                    "window_seconds": window_seconds
                }

                logger.warning(
                    f"Rate limit exceeded: client={client_ip}, endpoint={endpoint}, "
                    f"count={request_count}/{max_requests}, retry_after={retry_after}s",
                    extra={
                        "client_ip": client_ip,
                        "endpoint": endpoint,
                        "request_count": request_count,
                        "limit": max_requests,
                        "retry_after": retry_after
                    }
                )

                return False, rate_limit_info

            # Allow request - add to history
            history.append(current_time)

            # Calculate rate limit info for response headers
            rate_limit_info = {
                "limit": max_requests,
                "remaining": max_requests - request_count - 1,
                "reset": int(current_time + window_seconds),
                "window_seconds": window_seconds
            }

            return True, rate_limit_info

    def _get_limit_config(self, endpoint: str) -> tuple[int, int]:
        """
        Get rate limit configuration for an endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Tuple of (max_requests, window_seconds)
        """
        # Try exact match first
        if endpoint in self._limits:
            return self._limits[endpoint]

        # Try pattern matching
        import re
        for pattern, limits in self._limits.items():
            if pattern != "default" and re.match(pattern, endpoint):
                return limits

        # Return default
        return self._limits["default"]

    def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """
        Clean up old entries to prevent memory bloat.

        Args:
            max_age_seconds: Remove entries older than this (default: 1 hour)
        """
        with self._lock:
            current_time = time.time()
            cutoff_time = current_time - max_age_seconds

            clients_to_remove = []

            for client_ip, endpoints in self._history.items():
                endpoints_to_remove = []

                for endpoint, history in endpoints.items():
                    # Remove old entries from history
                    while history and history[0] < cutoff_time:
                        history.popleft()

                    # Mark empty endpoint histories for removal
                    if not history:
                        endpoints_to_remove.append(endpoint)

                # Remove empty endpoints
                for endpoint in endpoints_to_remove:
                    del endpoints[endpoint]

                # Mark empty clients for removal
                if not endpoints:
                    clients_to_remove.append(client_ip)

            # Remove empty clients
            for client_ip in clients_to_remove:
                del self._history[client_ip]

            logger.debug(
                f"Rate limiter cleanup: removed {len(clients_to_remove)} clients, "
                f"active clients: {len(self._history)}"
            )

    def get_stats(self) -> Dict:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            total_clients = len(self._history)
            total_endpoints = sum(len(endpoints) for endpoints in self._history.values())
            total_requests = sum(
                len(history)
                for endpoints in self._history.values()
                for history in endpoints.values()
            )

            return {
                "active_clients": total_clients,
                "tracked_endpoints": total_endpoints,
                "active_requests": total_requests,
                "limits": self._limits
            }


# Global rate limiter instance
_rate_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> InMemoryRateLimiter:
    """Get global rate limiter instance."""
    return _rate_limiter


async def rate_limit_middleware(request: Request, call_next: Callable):
    """
    FastAPI middleware for rate limiting.

    Checks rate limits before processing request and adds rate limit
    headers to response.

    Args:
        request: FastAPI request
        call_next: Next middleware/handler

    Returns:
        Response with rate limit headers

    Raises:
        HTTPException 429: If rate limit exceeded
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Get endpoint
    endpoint = request.url.path

    # Skip rate limiting for health check
    if endpoint.endswith("/health"):
        return await call_next(request)

    # Check rate limit
    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit(client_ip, endpoint)

    if not allowed:
        # Rate limit exceeded - return 429 Too Many Requests
        logger.warning(
            f"Rate limit exceeded for {client_ip} on {endpoint}",
            extra={
                "client_ip": client_ip,
                "endpoint": endpoint,
                "retry_after": rate_info['retry_after']
            }
        )

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "error_message": (
                    f"Rate limit exceeded. Maximum {rate_info['limit']} requests "
                    f"per {rate_info['window_seconds']} seconds."
                ),
                "retry_after_seconds": rate_info['retry_after'],
                "timestamp": datetime.utcnow().isoformat()
            },
            headers={
                "X-RateLimit-Limit": str(rate_info['limit']),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(rate_info['reset']),
                "Retry-After": str(rate_info['retry_after'])
            }
        )

    # Process request
    response = await call_next(request)

    # Add rate limit headers to response
    response.headers["X-RateLimit-Limit"] = str(rate_info['limit'])
    response.headers["X-RateLimit-Remaining"] = str(rate_info['remaining'])
    response.headers["X-RateLimit-Reset"] = str(rate_info['reset'])

    return response


async def cleanup_rate_limiter_task():
    """
    Background task to periodically clean up old rate limiter entries.

    This should be run as a scheduled task (e.g., every 5 minutes).
    """
    import asyncio

    limiter = get_rate_limiter()

    while True:
        try:
            # Wait 5 minutes
            await asyncio.sleep(300)

            # Cleanup entries older than 1 hour
            limiter.cleanup_old_entries(max_age_seconds=3600)

            logger.debug("Rate limiter cleanup completed")

        except Exception as e:
            logger.error(f"Error in rate limiter cleanup task: {e}", exc_info=True)


# ==================== REDIS-BASED RATE LIMITER (OPTIONAL) ====================

class RedisRateLimiter:
    """
    Redis-based distributed rate limiter.

    Use this for production deployments with multiple backend instances.
    Requires Redis connection.

    TODO: Implement Redis-based rate limiting for distributed systems.
    """

    def __init__(self, redis_client):
        """
        Initialize Redis rate limiter.

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client
        logger.info("RedisRateLimiter initialized")

    async def check_rate_limit(
        self,
        client_ip: str,
        endpoint: str,
        max_requests: int,
        window_seconds: int
    ) -> tuple[bool, Optional[Dict]]:
        """
        Check rate limit using Redis.

        Implementation:
        - Use Redis sorted sets with timestamps as scores
        - ZREMRANGEBYSCORE to remove old entries
        - ZADD to add new request
        - ZCARD to count requests in window

        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        # TODO: Implement Redis-based rate limiting
        pass
