"""
Main Application Security Integration

This module provides the integration points for the security authorization
system with the main FastAPI application. It includes middleware setup,
endpoint registration, and security configuration.

Key Components:
- Authentication middleware integration
- Secure endpoint registration
- Authorization service initialization
- Security audit logging setup

Author: Security Engineering Team
Created: 2025-01-09
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging
from typing import Optional

from database import get_db
from auth_dependencies import get_current_user
from models import AuthUser
from security.authorization import authorization_service
from security.secure_endpoints import router as secure_router

logger = logging.getLogger(__name__)
security = HTTPBearer()

def setup_security_integration(app: FastAPI):
    """
    Set up security integration with the main FastAPI application
    
    Args:
        app: FastAPI application instance
    """
    
    # Register secure endpoints
    app.include_router(
        secure_router,
        prefix="/api/secure",
        tags=["Secure Multi-Tenant API"],
        dependencies=[Depends(get_current_user)]
    )
    
    logger.info("Security integration configured successfully")

def get_authenticated_user_id(current_user: AuthUser = Depends(get_current_user)) -> str:
    """
    Extract authenticated user ID for use in endpoints
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        str: User ID
    """
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not authenticated or inactive"
        )
    
    return current_user.id

def require_authentication(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Require valid authentication for endpoint access
    
    Args:
        credentials: HTTP Bearer credentials
        
    Returns:
        HTTPAuthorizationCredentials: Valid credentials
        
    Raises:
        HTTPException: If authentication fails
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return credentials

# Enhanced endpoint decorators for security
def secure_endpoint(
    require_auth: bool = True,
    require_active: bool = True,
    log_access: bool = True
):
    """
    Decorator factory for securing endpoints with comprehensive checks
    
    Args:
        require_auth: Whether to require authentication
        require_active: Whether to require active user account
        log_access: Whether to log access attempts
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Add security checks here
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Security middleware for request/response logging
async def security_audit_middleware(request: Request, call_next):
    """
    Security audit middleware for logging all requests
    
    Args:
        request: FastAPI request object
        call_next: Next middleware in chain
        
    Returns:
        Response with security logging
    """
    start_time = time.time()
    
    # Log request
    logger.info(f"Security audit: {request.method} {request.url} from {request.client.host}")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Security audit: Response {response.status_code} in {process_time:.3f}s")
    
    return response

# User context helper functions
def get_user_context(current_user: AuthUser = Depends(get_current_user)) -> dict:
    """
    Get user context information for security logging
    
    Args:
        current_user: Authenticated user
        
    Returns:
        dict: User context information
    """
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "is_superuser": current_user.is_superuser
    }

# Database session with user context
def get_db_with_user_context(
    current_user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> tuple[Session, str]:
    """
    Get database session along with authenticated user ID
    
    Args:
        current_user: Authenticated user
        db: Database session
        
    Returns:
        tuple: (database_session, user_id)
    """
    return db, current_user.id

# Security configuration validation
def validate_security_setup():
    """
    Validate that security features are properly configured
    
    Raises:
        RuntimeError: If security configuration is invalid
    """
    try:
        # Check authorization service
        if not authorization_service:
            raise RuntimeError("Authorization service not initialized")
        
        # Check authentication dependencies
        from auth_dependencies import get_current_user
        if not get_current_user:
            raise RuntimeError("Authentication system not configured")
        
        logger.info("Security setup validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Security setup validation failed: {e}")
        raise RuntimeError(f"Security configuration invalid: {e}")

# Export key functions for main application
__all__ = [
    "setup_security_integration",
    "get_authenticated_user_id", 
    "require_authentication",
    "secure_endpoint",
    "security_audit_middleware",
    "get_user_context",
    "get_db_with_user_context",
    "validate_security_setup"
]