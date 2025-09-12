"""
Enhanced Redis-based Rate Limiter
================================
Replace in-memory rate limiting with Redis for production scalability.
"""

import redis
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class RedisRateLimiter:
    """Redis-based rate limiter with sliding window"""
    
    def __init__(self, redis_url: str, default_limit: int = 100, window_seconds: int = 60):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.default_limit = default_limit
        self.window_seconds = window_seconds
    
    def is_allowed(self, key: str, limit: Optional[int] = None) -> bool:
        """Check if request is allowed within rate limit"""
        limit = limit or self.default_limit
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        
        pipe = self.redis_client.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(f"rate_limit:{key}", 0, window_start)
        
        # Count current requests
        pipe.zcard(f"rate_limit:{key}")
        
        # Add current request
        pipe.zadd(f"rate_limit:{key}", {current_time: current_time})
        
        # Set expiration
        pipe.expire(f"rate_limit:{key}", self.window_seconds + 10)
        
        results = pipe.execute()
        current_count = results[1]
        
        return current_count < limit
    
    def get_remaining_requests(self, key: str, limit: Optional[int] = None) -> int:
        """Get remaining requests in current window"""
        limit = limit or self.default_limit
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        
        # Clean old entries and count
        self.redis_client.zremrangebyscore(f"rate_limit:{key}", 0, window_start)
        current_count = self.redis_client.zcard(f"rate_limit:{key}")
        
        return max(0, limit - current_count)
    
    def get_reset_time(self, key: str) -> datetime:
        """Get time when rate limit resets"""
        oldest_request = self.redis_client.zrange(f"rate_limit:{key}", 0, 0, withscores=True)
        if oldest_request:
            oldest_time = oldest_request[0][1]
            return datetime.fromtimestamp(oldest_time + self.window_seconds)
        return datetime.utcnow()

class SecurityEventLogger:
    """Redis-based security event logging"""
    
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], 
                          ip_address: str, user_id: Optional[str] = None):
        """Log security event to Redis"""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': event_type,
            'details': details,
            'ip_address': ip_address,
            'user_id': user_id
        }
        
        # Store event with TTL of 30 days
        event_key = f"security_event:{int(time.time())}:{secrets.token_hex(8)}"
        self.redis_client.setex(event_key, 2592000, json.dumps(event))
        
        # Add to sorted set for querying
        self.redis_client.zadd("security_events", {event_key: int(time.time())})
        
        # Trim old events (keep last 10,000)
        self.redis_client.zremrangebyrank("security_events", 0, -10001)
    
    def get_recent_events(self, event_type: Optional[str] = None, 
                         limit: int = 100) -> list:
        """Get recent security events"""
        event_keys = self.redis_client.zrevrange("security_events", 0, limit - 1)
        events = []
        
        for key in event_keys:
            event_data = self.redis_client.get(key)
            if event_data:
                event = json.loads(event_data)
                if not event_type or event.get('event_type') == event_type:
                    events.append(event)
        
        return events

# Usage in auth_middleware.py:
"""
from security_fixes import RedisRateLimiter, SecurityEventLogger

# Initialize Redis components
redis_url = settings.redis_url or "redis://localhost:6379/0"
rate_limiter = RedisRateLimiter(redis_url)
security_logger = SecurityEventLogger(redis_url)

# In middleware:
if not rate_limiter.is_allowed(client_ip):
    security_logger.log_security_event(
        'rate_limit_exceeded',
        {'requests_remaining': 0, 'reset_time': rate_limiter.get_reset_time(client_ip)},
        client_ip
    )
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded"}
    )
"""
