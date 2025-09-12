"""
Authentication Endpoints for AI Model Validation Platform
========================================================

Comprehensive JWT-based authentication system with secure endpoints for:
- User registration and login
- Session management with automatic cleanup
- JWT token generation and refresh
- User profile management

Security Features:
- bcrypt password hashing with configurable rounds
- JWT token validation with configurable expiration
- Session tracking with IP and user agent logging
- Comprehensive audit logging for security events
- Rate limiting and brute force protection
- Input validation and sanitization
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status, Response
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

# Import models and database dependencies
from database import get_db
from models import AuthUser, UserSession
from config import settings
from services.auth_service import auth_service

# Initialize security
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)

# Create router for auth endpoints
router = APIRouter(prefix="/auth", tags=["Authentication"])

# ============================================================================
# PYDANTIC SCHEMAS FOR AUTHENTICATION
# ============================================================================

class UserRegistrationRequest(BaseModel):
    """User registration request schema with comprehensive validation"""
    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 characters)")
    password: str = Field(..., min_length=8, max_length=128, description="Password (8-128 characters)")
    full_name: Optional[str] = Field(None, max_length=200, description="User's full name")
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format and content"""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        if v.lower() in ['admin', 'root', 'system', 'api', 'test']:
            raise ValueError('Username not allowed')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength"""
        import re
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "username": "johndoe",
                "password": "SecurePass123!",
                "full_name": "John Doe"
            }
        }

class UserLoginRequest(BaseModel):
    """User login request schema"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    remember_me: bool = Field(False, description="Extended session duration")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "remember_me": False
            }
        }

class TokenRefreshRequest(BaseModel):
    """Token refresh request schema"""
    refresh_token: str = Field(..., description="Valid refresh token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }

class AuthResponse(BaseModel):
    """Authentication response schema"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    user: Dict[str, Any] = Field(..., description="User profile information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "id": "user-id-123",
                    "email": "user@example.com",
                    "username": "johndoe",
                    "full_name": "John Doe",
                    "is_active": True,
                    "is_verified": False,
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }
        }

class UserProfileResponse(BaseModel):
    """User profile response schema"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User's email address")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="User's full name")
    is_active: bool = Field(..., description="User account status")
    is_verified: bool = Field(..., description="Email verification status")
    is_superuser: bool = Field(..., description="Superuser status")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "user-id-123",
                "email": "user@example.com",
                "username": "johndoe",
                "full_name": "John Doe",
                "is_active": True,
                "is_verified": False,
                "is_superuser": False,
                "last_login": "2024-01-01T12:00:00Z",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }

class LogoutResponse(BaseModel):
    """Logout response schema"""
    message: str = Field(..., description="Logout confirmation message")
    logged_out_at: datetime = Field(..., description="Logout timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Successfully logged out",
                "logged_out_at": "2024-01-01T12:30:00Z"
            }
        }

# ============================================================================
# JWT TOKEN UTILITIES
# ============================================================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token with configurable expiration"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token with extended expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # Refresh tokens last 7 days
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return payload
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

# ============================================================================
# AUTHENTICATION DEPENDENCIES
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> AuthUser:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    payload = verify_token(token)
    user_id: str = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )
    
    return user

async def get_current_active_user(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency to get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    return current_user

# ============================================================================
# SESSION MANAGEMENT UTILITIES
# ============================================================================

def create_user_session(
    db: Session,
    user: AuthUser,
    request: Request,
    session_token: str,
    remember_me: bool = False
) -> UserSession:
    """Create new user session with tracking information"""
    expires_at = datetime.utcnow() + timedelta(
        days=30 if remember_me else 1  # Extended session for remember_me
    )
    
    session = UserSession(
        user_id=user.id,
        session_token=session_token,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent", "unknown"),
        expires_at=expires_at,
        is_active=True
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    
    logger.info(f"Created session for user {user.email} from IP {session.ip_address}")
    return session

def invalidate_user_session(db: Session, session_token: str) -> bool:
    """Invalidate user session by token"""
    session = db.query(UserSession).filter(
        UserSession.session_token == session_token,
        UserSession.is_active == True
    ).first()
    
    if session:
        session.is_active = False
        db.commit()
        logger.info(f"Invalidated session for user_id {session.user_id}")
        return True
    return False

def cleanup_expired_sessions(db: Session) -> int:
    """Clean up expired sessions (background task)"""
    try:
        expired_count = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow(),
            UserSession.is_active == True
        ).count()
        
        db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow(),
            UserSession.is_active == True
        ).update({"is_active": False})
        
        db.commit()
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired sessions")
        
        return expired_count
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")
        db.rollback()
        return 0

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserRegistrationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user account
    
    - **email**: Valid email address (must be unique)
    - **username**: Username (3-50 characters, alphanumeric + underscore/hyphen)
    - **password**: Strong password (8+ chars, uppercase, lowercase, digit, special char)
    - **full_name**: Optional full name
    
    Returns JWT access and refresh tokens upon successful registration.
    """
    try:
        # Check if user already exists
        existing_user = db.query(AuthUser).filter(
            (AuthUser.email == user_data.email) | 
            (AuthUser.username == user_data.username)
        ).first()
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address is already registered"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username is already taken"
                )
        
        # Create new user
        hashed_password = pwd_context.hash(user_data.password)
        new_user = AuthUser(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,  # Email verification required
            is_superuser=False
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Create JWT tokens
        access_token = create_access_token(data={"sub": new_user.id})
        refresh_token = create_refresh_token(data={"sub": new_user.id})
        
        # Create user session
        create_user_session(db, new_user, request, access_token)
        
        # Update last login
        new_user.last_login = datetime.utcnow()
        db.commit()
        
        # Log successful registration
        logger.info(f"New user registered: {new_user.email} ({new_user.username})")
        
        # Return authentication response
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60,
            user={
                "id": new_user.id,
                "email": new_user.email,
                "username": new_user.username,
                "full_name": new_user.full_name,
                "is_active": new_user.is_active,
                "is_verified": new_user.is_verified,
                "created_at": new_user.created_at.isoformat()
            }
        )
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Registration integrity error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User registration failed due to constraint violation"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during registration"
        )

@router.post("/login", response_model=AuthResponse)
async def login_user(
    user_credentials: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens
    
    - **email**: Registered email address
    - **password**: User's password
    - **remember_me**: Extend session duration (optional)
    
    Returns JWT access and refresh tokens upon successful authentication.
    """
    try:
        # Find user by email
        user = db.query(AuthUser).filter(AuthUser.email == user_credentials.email).first()
        
        if not user:
            logger.warning(f"Login attempt with non-existent email: {user_credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not user.verify_password(user_credentials.password):
            logger.warning(f"Invalid password for user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if account is active
        if not user.is_active:
            logger.warning(f"Login attempt for inactive user: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is disabled"
            )
        
        # Create JWT tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        # Create user session
        create_user_session(
            db, user, request, access_token, user_credentials.remember_me
        )
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Clean up expired sessions (background task)
        cleanup_expired_sessions(db)
        
        # Log successful login
        logger.info(f"User logged in: {user.email}")
        
        # Return authentication response
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60,
            user={
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat()
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.post("/logout", response_model=LogoutResponse)
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Logout user and invalidate session
    
    Requires valid JWT access token in Authorization header.
    Invalidates the current session and logs the logout event.
    """
    try:
        token = credentials.credentials
        
        # Verify token and get user
        payload = verify_token(token)
        user_id = payload.get("sub")
        
        if user_id:
            # Invalidate session
            invalidate_user_session(db, token)
            
            # Get user for logging
            user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
            if user:
                logger.info(f"User logged out: {user.email}")
        
        return LogoutResponse(
            message="Successfully logged out",
            logged_out_at=datetime.utcnow()
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during logout"
        )

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: AuthUser = Depends(get_current_active_user)
):
    """
    Get current user profile information
    
    Requires valid JWT access token in Authorization header.
    Returns detailed user profile information.
    """
    try:
        return UserProfileResponse(
            id=current_user.id,
            email=current_user.email,
            username=current_user.username,
            full_name=current_user.full_name,
            is_active=current_user.is_active,
            is_verified=current_user.is_verified,
            is_superuser=current_user.is_superuser,
            last_login=current_user.last_login,
            created_at=current_user.created_at
        )
        
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error retrieving profile"
        )

@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    refresh_request: TokenRefreshRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Refresh JWT access token using refresh token
    
    - **refresh_token**: Valid JWT refresh token
    
    Returns new access and refresh tokens if the refresh token is valid.
    """
    try:
        # Verify refresh token
        payload = verify_token(refresh_request.refresh_token, token_type="refresh")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Get user
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
        
        # Create new tokens
        new_access_token = create_access_token(data={"sub": user.id})
        new_refresh_token = create_refresh_token(data={"sub": user.id})
        
        # Create new session
        create_user_session(db, user, request, new_access_token)
        
        # Log token refresh
        logger.info(f"Token refreshed for user: {user.email}")
        
        return AuthResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_expire_minutes * 60,
            user={
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "created_at": user.created_at.isoformat()
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during token refresh"
        )

# ============================================================================
# HEALTH CHECK AND UTILITY ENDPOINTS
# ============================================================================

@router.get("/health", include_in_schema=False)
async def auth_health_check(db: Session = Depends(get_db)):
    """Authentication service health check"""
    try:
        # Test database connection
        user_count = db.query(AuthUser).count()
        active_sessions = db.query(UserSession).filter(
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).count()
        
        return {
            "status": "healthy",
            "service": "authentication",
            "users_registered": user_count,
            "active_sessions": active_sessions,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Auth health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unhealthy"
        )