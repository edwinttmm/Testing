"""
CSRF Protection Implementation
============================
Add CSRF token protection for state-changing operations.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.status import HTTP_403_FORBIDDEN
import secrets
import hmac
import hashlib
from typing import Optional

class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection middleware"""
    
    def __init__(self, app, secret_key: str, cookie_name: str = "csrf_token", 
                 header_name: str = "X-CSRF-Token"):
        super().__init__(app)
        self.secret_key = secret_key.encode()
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.safe_methods = {"GET", "HEAD", "OPTIONS", "TRACE"}
    
    def generate_csrf_token(self, user_id: Optional[str] = None) -> str:
        """Generate CSRF token"""
        random_token = secrets.token_urlsafe(32)
        user_id = user_id or "anonymous"
        
        # Create HMAC signature
        signature = hmac.new(
            self.secret_key,
            f"{random_token}:{user_id}".encode(),
            hashlib.sha256
        ).hexdigest()
        
        return f"{random_token}:{signature}"
    
    def validate_csrf_token(self, token: str, user_id: Optional[str] = None) -> bool:
        """Validate CSRF token"""
        try:
            random_token, signature = token.split(":", 1)
            user_id = user_id or "anonymous"
            
            expected_signature = hmac.new(
                self.secret_key,
                f"{random_token}:{user_id}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except (ValueError, AttributeError):
            return False
    
    async def dispatch(self, request: Request, call_next):
        # Skip CSRF check for safe methods
        if request.method in self.safe_methods:
            response = await call_next(request)
            
            # Add CSRF token to safe method responses
            if not request.cookies.get(self.cookie_name):
                user_id = getattr(request.state, 'user_id', None)
                csrf_token = self.generate_csrf_token(user_id)
                response.set_cookie(
                    self.cookie_name,
                    csrf_token,
                    httponly=True,
                    secure=True,
                    samesite="strict"
                )
            
            return response
        
        # Check CSRF token for state-changing methods
        csrf_token = request.headers.get(self.header_name) or request.cookies.get(self.cookie_name)
        
        if not csrf_token:
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token missing"}
            )
        
        user_id = getattr(request.state, 'user_id', None)
        if not self.validate_csrf_token(csrf_token, user_id):
            return JSONResponse(
                status_code=HTTP_403_FORBIDDEN,
                content={"detail": "Invalid CSRF token"}
            )
        
        response = await call_next(request)
        return response

# Usage in main.py:
"""
from csrf_protection import CSRFMiddleware

app.add_middleware(CSRFMiddleware, secret_key=settings.secret_key)
"""
