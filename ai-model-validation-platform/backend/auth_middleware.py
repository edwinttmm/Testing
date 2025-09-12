"""
Authentication Middleware for AI Model Validation Platform
=========================================================

JWT-based authentication middleware providing:
- Automatic token validation for protected endpoints
- User context injection
- Session management
- Security headers and CORS handling
- Rate limiting and brute force protection
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, Callable, List
import jwt
import logging
from datetime import datetime
import time
from collections import defaultdict, deque

# Import models and dependencies
from database import SessionLocal
from models import AuthUser, UserSession
from config import settings

logger = logging.getLogger(__name__)

# Initialize security scheme
security = HTTPBearer(auto_error=False)

# Rate limiting storage (in production, use Redis)
rate_limit_store = defaultdict(lambda: deque())
failed_attempts_store = defaultdict(int)
blocked_ips = set()

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for JWT token validation and user context injection
    """
    
    def __init__(self, app, exempt_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/auth/login",
            "/auth/register",
            "/auth/health",
            "/favicon.ico"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through authentication middleware"""
        start_time = time.time()
        
        try:
            # Check if path is exempt from authentication
            if self._is_exempt_path(request.url.path):
                response = await call_next(request)
                return response
            
            # Apply rate limiting
            if self._is_rate_limited(request):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Rate limit exceeded. Please try again later."}
                )
            
            # Check for blocked IP
            client_ip = self._get_client_ip(request)
            if client_ip in blocked_ips:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Access denied"}
                )
            
            # Extract and validate JWT token
            user = await self._authenticate_request(request)
            
            # Add user context to request state
            if user:
                request.state.user = user
                request.state.authenticated = True
            else:
                request.state.authenticated = False
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            self._add_security_headers(response)
            
            # Log successful request
            process_time = time.time() - start_time
            if user:
                logger.debug(f"Authenticated request from {user.email} took {process_time:.3f}s")
            
            return response
            
        except HTTPException as e:
            # Handle authentication errors
            self._handle_auth_failure(request, e)
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Authentication middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal authentication error"}
            )
    
    def _is_exempt_path(self, path: str) -> bool:
        """Check if the path is exempt from authentication"""
        return any(path.startswith(exempt_path) for exempt_path in self.exempt_paths)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, request: Request) -> bool:
        """Apply rate limiting based on IP address"""
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        # Clean old entries (sliding window of 1 minute)
        window = 60  # seconds
        rate_limit_store[client_ip] = deque([
            timestamp for timestamp in rate_limit_store[client_ip]
            if current_time - timestamp < window
        ])
        
        # Check rate limit (100 requests per minute per IP)
        max_requests = 100
        if len(rate_limit_store[client_ip]) >= max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return True
        
        # Add current request timestamp
        rate_limit_store[client_ip].append(current_time)
        return False
    
    async def _authenticate_request(self, request: Request) -> Optional[AuthUser]:
        """Extract and validate JWT token from request"""
        try:
            # Extract Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return None
            
            if not auth_header.startswith("Bearer "):
                return None
            
            token = auth_header.split(" ", 1)[1]
            
            # Validate JWT token
            try:
                payload = jwt.decode(
                    token,
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm]
                )
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
            except jwt.InvalidTokenError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # Validate token type
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing user ID"
                )
            
            # Get user from database
            db = SessionLocal()
            try:
                user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found"
                    )
                
                if not user.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account is disabled"
                    )
                
                # Verify session is still active
                session = db.query(UserSession).filter(
                    UserSession.session_token == token,
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                ).first()
                
                if not session:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session expired or invalid"
                    )
                
                # Update session activity
                session.last_activity = datetime.utcnow()
                db.commit()
                
                return user
                
            finally:
                db.close()
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed"
            )
    
    def _handle_auth_failure(self, request: Request, error: HTTPException):
        """Handle authentication failure and apply security measures"""
        client_ip = self._get_client_ip(request)
        
        # Track failed attempts for brute force protection
        if error.status_code == status.HTTP_401_UNAUTHORIZED:
            failed_attempts_store[client_ip] += 1
            
            # Block IP after 10 failed attempts
            if failed_attempts_store[client_ip] >= 10:
                blocked_ips.add(client_ip)
                logger.warning(f"Blocked IP due to excessive failed attempts: {client_ip}")
        
        # Log security event
        logger.warning(f"Authentication failure from {client_ip}: {error.detail}")
    
    def _add_security_headers(self, response):
        """Add security headers to response"""
        if settings.security_headers_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            if settings.hsts_enabled:
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
            if settings.csp_enabled:
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; "
                    "font-src 'self'; "
                    "connect-src 'self'; "
                    "frame-ancestors 'none'"
                )

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

def get_current_user_from_request(request: Request) -> Optional[AuthUser]:
    """Get current user from request state (set by middleware)"""
    return getattr(request.state, "user", None)

def require_authentication(request: Request) -> AuthUser:
    """Dependency that requires valid authentication"""
    user = get_current_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

def require_active_user(request: Request) -> AuthUser:
    """Dependency that requires active user account"""
    user = require_authentication(request)
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )
    return user

def require_verified_user(request: Request) -> AuthUser:
    """Dependency that requires verified user account"""
    user = require_active_user(request)
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account verification required"
        )
    return user

def require_superuser(request: Request) -> AuthUser:
    """Dependency that requires superuser privileges"""
    user = require_active_user(request)
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required"
        )
    return user

def optional_authentication(request: Request) -> Optional[AuthUser]:
    """Optional authentication dependency"""
    return get_current_user_from_request(request)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clear_rate_limits():
    """Clear rate limiting data (for testing or maintenance)"""
    global rate_limit_store, failed_attempts_store, blocked_ips
    rate_limit_store.clear()
    failed_attempts_store.clear()
    blocked_ips.clear()
    logger.info("Rate limiting data cleared")

def unblock_ip(ip_address: str):
    """Manually unblock an IP address"""
    if ip_address in blocked_ips:
        blocked_ips.remove(ip_address)
        if ip_address in failed_attempts_store:
            del failed_attempts_store[ip_address]
        logger.info(f"Unblocked IP address: {ip_address}")

def get_blocked_ips() -> List[str]:
    """Get list of currently blocked IP addresses"""
    return list(blocked_ips)

def get_rate_limit_stats() -> dict:
    """Get rate limiting statistics"""
    return {
        "active_ips": len(rate_limit_store),
        "failed_attempts": dict(failed_attempts_store),
        "blocked_ips": list(blocked_ips),
        "total_blocked": len(blocked_ips)
    }