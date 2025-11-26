"""Rate limiting to prevent DoS via retry logic"""
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter"""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests = defaultdict(list)
        self.lock = Lock()
        logger.info(
            f"Rate limiter initialized: {max_requests} requests per {window_seconds}s"
        )

    def is_allowed(self, key: str) -> bool:
        """
        Check if request is allowed.

        Args:
            key: Unique identifier for rate limiting (e.g., session_id, IP)

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        with self.lock:
            now = datetime.now()
            cutoff = now - self.window

            # Remove old requests
            self.requests[key] = [
                req_time for req_time in self.requests[key]
                if req_time > cutoff
            ]

            # Check limit
            if len(self.requests[key]) >= self.max_requests:
                logger.warning(
                    f"Rate limit exceeded for key: {key} "
                    f"({len(self.requests[key])} requests in window)"
                )
                return False

            # Record request
            self.requests[key].append(now)
            return True

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for key"""
        with self.lock:
            now = datetime.now()
            cutoff = now - self.window

            # Count valid requests in window
            valid_requests = [
                req_time for req_time in self.requests.get(key, [])
                if req_time > cutoff
            ]

            return max(0, self.max_requests - len(valid_requests))

    def reset(self, key: str):
        """Reset rate limit for key"""
        with self.lock:
            if key in self.requests:
                del self.requests[key]
                logger.info(f"Rate limit reset for key: {key}")

# Global instances for different rate limiting scenarios
session_retry_limiter = RateLimiter(max_requests=20, window_seconds=60)
detection_event_limiter = RateLimiter(max_requests=1000, window_seconds=60)  # Higher limit for detection events
api_request_limiter = RateLimiter(max_requests=100, window_seconds=60)
