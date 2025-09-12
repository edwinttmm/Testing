"""
Redis Session Store Implementation
================================
Replace database sessions with Redis for better performance.
"""

import redis
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

class RedisSessionStore:
    """Redis-based session storage"""
    
    def __init__(self, redis_url: str, key_prefix: str = "session:"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.key_prefix = key_prefix
    
    def create_session(self, user_id: str, session_data: Dict[str, Any], 
                      expires_in: int = 1800) -> str:
        """Create new session in Redis"""
        session_id = str(uuid.uuid4())
        session_key = f"{self.key_prefix}{session_id}"
        
        session_data.update({
            'user_id': user_id,
            'created_at': datetime.utcnow().isoformat(),
            'last_activity': datetime.utcnow().isoformat()
        })
        
        self.redis_client.setex(
            session_key,
            expires_in,
            json.dumps(session_data)
        )
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data from Redis"""
        session_key = f"{self.key_prefix}{session_id}"
        session_data = self.redis_client.get(session_key)
        
        if session_data:
            return json.loads(session_data)
        return None
    
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        session_key = f"{self.key_prefix}{session_id}"
        session_data = self.get_session(session_id)
        
        if session_data:
            session_data.update(updates)
            session_data['last_activity'] = datetime.utcnow().isoformat()
            
            # Preserve TTL
            ttl = self.redis_client.ttl(session_key)
            if ttl > 0:
                self.redis_client.setex(
                    session_key,
                    ttl,
                    json.dumps(session_data)
                )
                return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session from Redis"""
        session_key = f"{self.key_prefix}{session_id}"
        return bool(self.redis_client.delete(session_key))
    
    def extend_session(self, session_id: str, expires_in: int = 1800) -> bool:
        """Extend session expiration"""
        session_key = f"{self.key_prefix}{session_id}"
        return bool(self.redis_client.expire(session_key, expires_in))
    
    def get_user_sessions(self, user_id: str) -> list:
        """Get all sessions for a user"""
        pattern = f"{self.key_prefix}*"
        sessions = []
        
        for key in self.redis_client.scan_iter(match=pattern):
            session_data = self.redis_client.get(key)
            if session_data:
                data = json.loads(session_data)
                if data.get('user_id') == user_id:
                    sessions.append({
                        'session_id': key.replace(self.key_prefix, ''),
                        **data
                    })
        
        return sessions
    
    def cleanup_expired_sessions(self) -> int:
        """Cleanup expired sessions (Redis handles this automatically)"""
        # Redis handles expiration automatically, but we can count active sessions
        pattern = f"{self.key_prefix}*"
        active_sessions = 0
        
        for key in self.redis_client.scan_iter(match=pattern):
            if self.redis_client.exists(key):
                active_sessions += 1
        
        return active_sessions

# Usage in auth_service.py:
"""
from session_redis_store import RedisSessionStore

# Initialize Redis session store
redis_url = settings.redis_url or "redis://localhost:6379/0"
session_store = RedisSessionStore(redis_url)

def create_user_session(user_id: str, ip_address: str, user_agent: str) -> str:
    session_data = {
        'ip_address': ip_address,
        'user_agent': user_agent,
        'is_active': True
    }
    return session_store.create_session(user_id, session_data)
"""
