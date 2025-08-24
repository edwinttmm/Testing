"""
Security middleware and utilities for the AI Model Validation Platform.

This module provides comprehensive security features including:
- Security headers middleware
- Authentication and authorization utilities
- Rate limiting
- Input validation and sanitization
- CSRF protection
"""

import time
import logging
from typing import Callable, Dict, List, Optional, Set
from functools import wraps
from collections import defaultdict, deque

from fastapi import FastAPI, Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import jwt
from passlib.context import CryptContext
import hashlib
import hmac
import secrets

from config import Settings, get_settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security bearer for JWT tokens
security = HTTPBearer()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.
    
    Implements OWASP recommended security headers for web applications.
    """
    
    def __init__(self, app: FastAPI, settings: Settings):
        super().__init__(app)
        self.settings = settings
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        if not self.settings.security_headers_enabled:
            return response
            
        # Content Security Policy
        if self.settings.csp_enabled:
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; "
                "font-src 'self' data:; "
                "connect-src 'self' ws: wss:; "
                "media-src 'self' blob:; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )
            response.headers["Content-Security-Policy"] = csp_policy
            
        # Strict Transport Security (HTTPS only)
        if self.settings.hsts_enabled and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
            
        # X-Frame-Options
        response.headers["X-Frame-Options"] = "DENY"
        
        # X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-XSS-Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), accelerometer=(), gyroscope=(), magnetometer=()"
        )
        
        # Remove server header
        if "server" in response.headers:
            del response.headers["server"]
        
        # Custom security header
        response.headers["X-Security-Version"] = "1.0"
        
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse and DoS attacks.
    
    Implements sliding window rate limiting with configurable limits.
    """
    
    def __init__(
        self, 
        app: FastAPI, 
        calls: int = 100, 
        period: int = 60,
        exempt_paths: Optional[List[str]] = None
    ):
        super().__init__(app)
        self.calls = calls  # Number of calls allowed
        self.period = period  # Time period in seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.exempt_paths = exempt_paths or ["/health", "/metrics"]
        
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier (IP address + User-Agent hash)"""
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        ua_hash = hashlib.md5(user_agent.encode()).hexdigest()[:8]
        return f"{client_ip}:{ua_hash}"
        
    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from rate limiting"""
        return any(exempt in path for exempt in self.exempt_paths)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)
            
        client_id = self._get_client_id(request)
        current_time = time.time()
        
        # Clean old requests outside the time window
        request_times = self.requests[client_id]
        while request_times and request_times[0] <= current_time - self.period:
            request_times.popleft()
            
        # Check if rate limit exceeded
        if len(request_times) >= self.calls:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.calls} requests per {self.period} seconds allowed",
                    "retry_after": self.period
                },
                headers={"Retry-After": str(self.period)}
            )
            
        # Add current request time
        request_times.append(current_time)
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.calls)
        response.headers["X-RateLimit-Remaining"] = str(self.calls - len(request_times))
        response.headers["X-RateLimit-Reset"] = str(int(current_time + self.period))
        
        return response

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    IP Whitelist middleware for production security.
    
    Allows only specified IP addresses or ranges to access the API.
    """
    
    def __init__(self, app: FastAPI, allowed_ips: Optional[Set[str]] = None):
        super().__init__(app)
        self.allowed_ips = allowed_ips or set()
        
    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if IP address is allowed"""
        if not self.allowed_ips:
            return True  # No restrictions if no IPs configured
            
        # Exact IP match
        if ip in self.allowed_ips:
            return True
            
        # Check for CIDR ranges (basic implementation)
        # TODO: Implement proper CIDR matching for production
        
        return False
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        
        if not self._is_ip_allowed(client_ip):
            logger.warning(f"Access denied for IP {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access forbidden",
                    "message": "Your IP address is not authorized to access this resource"
                }
            )
            
        return await call_next(request)

class JWTAuthHandler:
    """
    JWT Authentication handler with secure token management.
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        
    def encode_token(self, user_id: str, expires_delta: Optional[int] = None) -> str:
        """Create a JWT token for user"""
        if expires_delta is None:
            expires_delta = self.settings.jwt_expire_minutes
            
        payload = {
            "user_id": user_id,
            "exp": time.time() + (expires_delta * 60),
            "iat": time.time(),
            "jti": secrets.token_urlsafe(16)  # Unique token ID
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
    def decode_token(self, token: str) -> Dict:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if token is expired
            if payload.get("exp", 0) < time.time():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired"
                )
                
            return payload
            
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )

class PasswordManager:
    """
    Secure password hashing and verification utilities.
    """
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
        
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
        
    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """Generate a cryptographically secure random password"""
        return secrets.token_urlsafe(length)

class CSRFProtection:
    """
    CSRF (Cross-Site Request Forgery) protection utilities.
    """
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()
        
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        message = f"{session_id}:{time.time()}"
        signature = hmac.new(
            self.secret_key, 
            message.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        return f"{message}:{signature}"
        
    def validate_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Validate CSRF token"""
        try:
            parts = token.split(":")
            if len(parts) != 3:
                return False
                
            token_session, timestamp_str, signature = parts
            
            if token_session != session_id:
                return False
                
            timestamp = float(timestamp_str)
            if time.time() - timestamp > max_age:
                return False
                
            expected_signature = hmac.new(
                self.secret_key,
                f"{session_id}:{timestamp}".encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except (ValueError, TypeError):
            return False

class InputSanitizer:
    """
    Input validation and sanitization utilities.
    """
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal attacks"""
        import os
        import re
        
        # Remove path separators and null bytes
        filename = filename.replace(os.path.sep, "_").replace("\0", "")
        
        # Remove or replace dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:250] + ext
            
        return filename
        
    @staticmethod
    def validate_video_file(filename: str, content_type: str, max_size: int) -> bool:
        """Validate video file upload"""
        # Check file extension
        allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v'}
        file_ext = filename.lower().split('.')[-1]
        if f'.{file_ext}' not in allowed_extensions:
            return False
            
        # Check content type
        allowed_types = {
            'video/mp4', 'video/avi', 'video/quicktime', 
            'video/x-msvideo', 'video/webm', 'video/x-matroska'
        }
        if content_type not in allowed_types:
            return False
            
        return True

def setup_security_middleware(app: FastAPI, settings: Settings) -> None:
    """
    Setup all security middleware for the FastAPI application.
    """
    
    # Add security headers middleware
    if settings.security_headers_enabled:
        app.add_middleware(SecurityHeadersMiddleware, settings=settings)
        logger.info("Security headers middleware enabled")
    
    # Add rate limiting middleware
    if settings.app_environment.lower() == "production":
        app.add_middleware(
            RateLimitMiddleware, 
            calls=100, 
            period=60,
            exempt_paths=["/health", "/metrics", "/docs", "/redoc"]
        )
        logger.info("Rate limiting middleware enabled")
    
    # IP whitelist middleware (configure in production)
    # app.add_middleware(IPWhitelistMiddleware, allowed_ips={"127.0.0.1", "::1"})
    
    logger.info("Security middleware setup completed")

# Decorator for requiring authentication
def require_auth(settings: Settings = None):
    """Decorator to require JWT authentication for endpoints"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # This is a placeholder - implement based on your auth requirements
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Utility functions for security validation
def validate_secret_key(secret_key: str, environment: str) -> bool:
    """Validate that secret key meets security requirements"""
    if not secret_key or len(secret_key) < 32:
        return False
        
    # Check for common insecure values
    insecure_keys = [
        "your-secret-key-change-in-production",
        "INSECURE-DEFAULT-CHANGE-ME",
        "development-key-only",
        "test-key"
    ]
    
    return secret_key not in insecure_keys

def generate_secure_config() -> Dict[str, str]:
    """Generate secure configuration values"""
    return {
        "secret_key": secrets.token_urlsafe(32),
        "jwt_secret": secrets.token_urlsafe(32),
        "session_secret": secrets.token_urlsafe(24),
        "csrf_secret": secrets.token_urlsafe(24)
    }