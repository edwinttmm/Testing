"""
Authentication Dependencies for AI Model Validation Platform
===========================================================

Centralized authentication dependencies for FastAPI endpoints providing:
- JWT token validation and user extraction
- Role-based access control
- Session management
- Security policy enforcement
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, List, Union
import jwt
import logging
from datetime import datetime
from functools import wraps

# Import models and database
from database import get_db
from models import AuthUser, UserSession
from config import settings
from services.auth_service import auth_service

logger = logging.getLogger(__name__)
security = HTTPBearer()

# ============================================================================
# CORE AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AuthUser:
    """
    Core dependency to extract and validate current user from JWT token
    
    Validates:
    - JWT token format and signature
    - Token expiration
    - User existence and status
    - Session validity
    """
    try:
        token = credentials.credentials
        
        # Decode and validate JWT token
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm]
            )
        except jwt.ExpiredSignatureError:
            logger.warning("Expired token used")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token used: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Validate token type
        if payload.get("type") != "access":
            logger.warning("Non-access token used for authentication")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Extract user ID
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("Token missing user ID")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Query user from database
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if user is None:
            logger.warning(f"User not found for ID: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify user account is active
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify session is still valid
        session = db.query(UserSession).filter(
            UserSession.session_token == token,
            UserSession.user_id == user_id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            logger.warning(f"Invalid or expired session for user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Update session activity timestamp
        session.last_activity = datetime.utcnow()
        db.commit()
        
        logger.debug(f"Authenticated user: {user.email}")
        return user
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in authentication: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

async def get_current_active_user(
    current_user: AuthUser = Depends(get_current_user)
) -> AuthUser:
    """
    Dependency to ensure current user has an active account
    """
    if not current_user.is_active:
        logger.warning(f"Inactive user attempted access: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )
    return current_user

async def get_current_verified_user(
    current_user: AuthUser = Depends(get_current_active_user)
) -> AuthUser:
    """
    Dependency to ensure current user has a verified email address
    """
    if not current_user.is_verified:
        logger.warning(f"Unverified user attempted protected access: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required"
        )
    return current_user

async def get_current_superuser(
    current_user: AuthUser = Depends(get_current_active_user)
) -> AuthUser:
    """
    Dependency to ensure current user has superuser privileges
    """
    if not current_user.is_superuser:
        logger.warning(f"Non-superuser attempted admin access: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required"
        )
    return current_user

async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db)
) -> Optional[AuthUser]:
    """
    Optional authentication dependency - returns None if no valid token
    """
    if credentials is None:
        return None
    
    try:
        # Use the main authentication dependency
        return await get_current_user(credentials, db)
    except HTTPException:
        # Return None for any authentication failures in optional context
        return None

# ============================================================================
# ROLE-BASED ACCESS CONTROL
# ============================================================================

def require_roles(*allowed_roles: str):
    """
    Decorator to require specific user roles
    
    Usage:
        @require_roles("admin", "moderator")
        async def admin_endpoint(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current user from kwargs or request
            current_user = None
            for key, value in kwargs.items():
                if isinstance(value, AuthUser):
                    current_user = value
                    break
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # For now, we'll use is_superuser as admin role
            # In future, implement proper role system
            user_roles = []
            if current_user.is_superuser:
                user_roles.append("admin")
            if current_user.is_active:
                user_roles.append("user")
            
            if not any(role in user_roles for role in allowed_roles):
                logger.warning(f"User {current_user.email} attempted access requiring roles: {allowed_roles}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires one of these roles: {', '.join(allowed_roles)}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================================
# PERMISSION-BASED ACCESS CONTROL
# ============================================================================

class Permission:
    """Permission constants for access control"""
    
    # User management permissions
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_ADMIN = "user:admin"
    
    # Project permissions
    PROJECT_READ = "project:read"
    PROJECT_WRITE = "project:write"
    PROJECT_DELETE = "project:delete"
    PROJECT_ADMIN = "project:admin"
    
    # Video permissions
    VIDEO_READ = "video:read"
    VIDEO_WRITE = "video:write"
    VIDEO_DELETE = "video:delete"
    VIDEO_PROCESS = "video:process"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    SYSTEM_CONFIG = "system:config"

def check_permission(user: AuthUser, permission: str) -> bool:
    """
    Check if user has specific permission
    
    For now, simplified permission system:
    - Superusers have all permissions
    - Active users have basic read/write permissions
    - Future: implement granular permission system
    """
    if not user.is_active:
        return False
    
    if user.is_superuser:
        return True  # Superusers have all permissions
    
    # Basic permissions for active users
    basic_permissions = [
        Permission.USER_READ,
        Permission.PROJECT_READ,
        Permission.PROJECT_WRITE,
        Permission.VIDEO_READ,
        Permission.VIDEO_WRITE
    ]
    
    return permission in basic_permissions

async def require_permission(
    permission: str,
    current_user: AuthUser = Depends(get_current_active_user)
) -> AuthUser:
    """
    Dependency to require specific permission
    """
    if not check_permission(current_user, permission):
        logger.warning(f"User {current_user.email} lacks permission: {permission}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}"
        )
    return current_user

# ============================================================================
# RESOURCE OWNERSHIP VALIDATION
# ============================================================================

async def validate_resource_ownership(
    resource_owner_id: str,
    current_user: AuthUser = Depends(get_current_active_user)
) -> AuthUser:
    """
    Validate that current user owns the resource or is superuser
    """
    if current_user.is_superuser:
        return current_user  # Superusers can access any resource
    
    if current_user.id != resource_owner_id:
        logger.warning(f"User {current_user.email} attempted unauthorized resource access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource ownership required"
        )
    
    return current_user

# ============================================================================
# SESSION MANAGEMENT DEPENDENCIES
# ============================================================================

async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserSession:
    """
    Get current user session from token
    """
    token = credentials.credentials
    
    # Validate token first
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Get session
    session = db.query(UserSession).filter(
        UserSession.session_token == token,
        UserSession.user_id == user_id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or expired"
        )
    
    return session

async def validate_session_ownership(
    session_id: str,
    current_user: AuthUser = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserSession:
    """
    Validate that current user owns the session
    """
    session = db.query(UserSession).filter(UserSession.id == session_id).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: session ownership required"
        )
    
    return session

# ============================================================================
# UTILITY DEPENDENCIES
# ============================================================================

async def get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_superuser)
) -> AuthUser:
    """
    Get any user by ID (superuser only)
    """
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

async def get_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_superuser)
) -> AuthUser:
    """
    Get user by email (superuser only)
    """
    user = db.query(AuthUser).filter(AuthUser.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user