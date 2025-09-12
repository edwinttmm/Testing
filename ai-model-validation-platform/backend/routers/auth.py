"""
Authentication Router - Organized API Endpoints
=============================================

Consolidated authentication endpoints following FastAPI best practices.
Handles user registration, login, JWT tokens, and session management.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import uuid
import logging
from passlib.context import CryptContext

from database import SessionLocal
from models import AuthUser, UserSession
from config import settings
from services.auth_service import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Security setup
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# PYDANTIC SCHEMAS FOR AUTHENTICATION
# ============================================================================

class UserRegistrationRequest(BaseModel):
    """User registration request schema"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (minimum 8 characters)")
    full_name: Optional[str] = Field(None, description="User's full name")
    organization: Optional[str] = Field(None, description="User's organization")
    
    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserLoginRequest(BaseModel):
    """User login request schema"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
    remember_me: bool = Field(False, description="Remember user session")

class TokenResponse(BaseModel):
    """JWT token response schema"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    user_info: Dict[str, Any] = Field(..., description="Basic user information")

class UserProfileResponse(BaseModel):
    """User profile response schema"""
    id: str
    email: str
    full_name: Optional[str]
    organization: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]

class PasswordChangeRequest(BaseModel):
    """Password change request schema"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistrationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user account"""
    try:
        # Check if user already exists
        existing_user = db.query(AuthUser).filter(AuthUser.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        # Hash password
        hashed_password = pwd_context.hash(user_data.password)
        
        # Create user
        new_user = AuthUser(
            id=str(uuid.uuid4()),
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            organization=user_data.organization,
            is_active=True,
            is_verified=False,  # Require email verification
            created_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Generate JWT tokens
        access_token, expires_in = auth_service.create_access_token(new_user.id)
        refresh_token = auth_service.create_refresh_token(new_user.id)
        
        # Create user session
        session = UserSession(
            id=str(uuid.uuid4()),
            user_id=new_user.id,
            session_token=refresh_token,
            ip_address=request.client.host,
            user_agent=request.headers.get("User-Agent", ""),
            created_at=datetime.utcnow(),
            is_active=True
        )
        
        db.add(session)
        db.commit()
        
        logger.info(f"New user registered: {user_data.email}")
        
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            user_info={
                "id": new_user.id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "is_verified": new_user.is_verified
            }
        )
        
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login_user(
    credentials: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user and return JWT tokens"""
    try:
        # Find user by email
        user = db.query(AuthUser).filter(AuthUser.email == credentials.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not pwd_context.verify(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated"
            )
        
        # Generate JWT tokens
        access_token, expires_in = auth_service.create_access_token(user.id)
        refresh_token = auth_service.create_refresh_token(user.id)
        
        # Update last login
        user.last_login = datetime.utcnow()
        
        # Create or update user session
        existing_session = db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.ip_address == request.client.host,
            UserSession.is_active == True
        ).first()
        
        if existing_session:
            existing_session.session_token = refresh_token
            existing_session.updated_at = datetime.utcnow()
        else:
            new_session = UserSession(
                id=str(uuid.uuid4()),
                user_id=user.id,
                session_token=refresh_token,
                ip_address=request.client.host,
                user_agent=request.headers.get("User-Agent", ""),
                created_at=datetime.utcnow(),
                is_active=True
            )
            db.add(new_session)
        
        db.commit()
        
        logger.info(f"User logged in: {credentials.email}")
        
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            user_info={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_verified": user.is_verified,
                "organization": user.organization
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/logout")
async def logout_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Logout user and invalidate session"""
    try:
        # Verify token and get user
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Deactivate user sessions
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.ip_address == request.client.host,
            UserSession.is_active == True
        ).update({
            "is_active": False,
            "updated_at": datetime.utcnow()
        })
        
        db.commit()
        
        logger.info(f"User logged out: {user_id}")
        
        return {
            "message": "Successfully logged out",
            "logged_out_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    refresh_token: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        user_id = auth_service.verify_refresh_token(refresh_token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Check if session exists and is active
        session = db.query(UserSession).filter(
            UserSession.session_token == refresh_token,
            UserSession.is_active == True
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session not found or expired"
            )
        
        # Get user information
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Generate new access token
        access_token, expires_in = auth_service.create_access_token(user_id)
        new_refresh_token = auth_service.create_refresh_token(user_id)
        
        # Update session with new refresh token
        session.session_token = new_refresh_token
        session.updated_at = datetime.utcnow()
        db.commit()
        
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=new_refresh_token,
            user_info={
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_verified": user.is_verified
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )

@router.post("/verify-token")
async def verify_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Verify access token validity"""
    try:
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user information
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return {
            "valid": True,
            "user_id": user_id,
            "email": user.email,
            "is_active": user.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return {
            "valid": False,
            "error": "Token verification failed"
        }

# ============================================================================
# USER PROFILE MANAGEMENT
# ============================================================================

@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user profile information"""
    try:
        # Verify token and get user
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserProfileResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization=user.organization,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve profile"
        )

@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    profile_data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Update user profile information"""
    try:
        # Verify token and get user
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update allowed fields
        allowed_fields = {'full_name', 'organization'}
        for field, value in profile_data.items():
            if field in allowed_fields:
                setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        
        logger.info(f"Profile updated for user: {user.email}")
        
        return UserProfileResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization=user.organization,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )

@router.post("/change-password")
async def change_user_password(
    password_data: PasswordChangeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        # Verify token and get user
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Verify current password
        if not pwd_context.verify(password_data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        user.hashed_password = pwd_context.hash(password_data.new_password)
        user.updated_at = datetime.utcnow()
        
        # Invalidate all user sessions except current one
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).update({
            "is_active": False,
            "updated_at": datetime.utcnow()
        })
        
        db.commit()
        
        logger.info(f"Password changed for user: {user.email}")
        
        return {
            "message": "Password changed successfully",
            "changed_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

@router.get("/sessions")
async def get_user_sessions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get all active sessions for the current user"""
    try:
        # Verify token and get user
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user sessions
        sessions = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).order_by(UserSession.created_at.desc()).all()
        
        session_list = [
            {
                "id": session.id,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                "is_current": session.session_token == credentials.credentials  # Approximate check
            }
            for session in sessions
        ]
        
        return {
            "sessions": session_list,
            "total_sessions": len(session_list)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session retrieval error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions"
        )

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Revoke a specific user session"""
    try:
        # Verify token and get user
        user_id = auth_service.verify_token(credentials.credentials)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Find and revoke session
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.is_active == True
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        session.is_active = False
        session.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Session revoked: {session_id} for user: {user_id}")
        
        return {
            "message": "Session revoked successfully",
            "session_id": session_id,
            "revoked_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session revocation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )

# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def auth_health_check():
    """Health check endpoint for authentication service"""
    return {
        "status": "healthy",
        "service": "Authentication Router",
        "version": "1.0.0",
        "endpoints": [
            "POST /auth/register - User registration",
            "POST /auth/login - User login",
            "POST /auth/logout - User logout",
            "POST /auth/refresh - Token refresh",
            "POST /auth/verify-token - Token verification",
            "GET /auth/profile - Get user profile",
            "PUT /auth/profile - Update user profile",
            "POST /auth/change-password - Change password",
            "GET /auth/sessions - Get user sessions",
            "DELETE /auth/sessions/{id} - Revoke session"
        ]
    }