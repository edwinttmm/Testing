"""
Authentication Service for AI Model Validation Platform
=====================================================

Centralized authentication service providing:
- User authentication and authorization
- JWT token management
- Session handling
- Password security
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import jwt
import logging
from passlib.context import CryptContext
import uuid

from database import SessionLocal
from models import AuthUser, UserSession
from config import settings

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service for user management"""
    
    def __init__(self):
        self.pwd_context = pwd_context
        self.secret_key = getattr(settings, 'jwt_secret_key', settings.secret_key)
        self.algorithm = getattr(settings, 'jwt_algorithm', 'HS256')
        self.access_token_expire_minutes = getattr(settings, 'jwt_expire_minutes', 30)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[AuthUser]:
        """Authenticate user by email and password"""
        try:
            user = db.query(AuthUser).filter(
                AuthUser.email == email,
                AuthUser.is_active == True
            ).first()
            
            if not user:
                return None
            
            if not self.verify_password(password, user.hashed_password):
                return None
            
            # Update last login
            user.last_login = datetime.utcnow()
            db.commit()
            
            return user
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.PyJWTError:
            return None
    
    def create_user_session(self, db: Session, user_id: str, token: str, 
                          ip_address: str, user_agent: str) -> UserSession:
        """Create new user session"""
        session = UserSession(
            user_id=user_id,
            session_token=token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    
    def invalidate_session(self, db: Session, session_token: str) -> bool:
        """Invalidate user session"""
        try:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.is_active == True
            ).first()
            
            if session:
                session.is_active = False
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Session invalidation error: {str(e)}")
            return False
    
    def cleanup_expired_sessions(self, db: Session) -> int:
        """Clean up expired sessions"""
        try:
            expired_count = db.query(UserSession).filter(
                UserSession.expires_at < datetime.utcnow(),
                UserSession.is_active == True
            ).update({"is_active": False})
            
            db.commit()
            logger.info(f"Cleaned up {expired_count} expired sessions")
            return expired_count
        except Exception as e:
            logger.error(f"Session cleanup error: {str(e)}")
            return 0


# Global auth service instance
auth_service = AuthService()