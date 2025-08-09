from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.hash import bcrypt
from sqlalchemy.orm import Session
import os
import secrets
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        # Generate secure secret key if not provided
        self.secret_key = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None):
        """Create a new access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode access token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            return None
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def authenticate_user(self, email: str, password: str, db: Session) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password"""
        try:
            # For demo purposes, we'll use a simple check
            # In production, query from database
            if email == "admin@example.com" and password == "admin":
                return {
                    "id": "admin-id",
                    "email": email,
                    "full_name": "Administrator",
                    "is_active": True
                }
            return None
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None
    
    def get_current_user(self, token: str, db: Session) -> Optional[Dict[str, Any]]:
        """Get current user from token"""
        try:
            payload = self.verify_token(token)
            if payload is None:
                return None
                
            user_email: str = payload.get("sub")
            if user_email is None:
                return None
                
            # For demo purposes, return mock user
            # In production, query from database
            user_data = {
                "id": payload.get("user_id", "admin-id"),
                "email": user_email,
                "full_name": payload.get("full_name", "Administrator"),
                "is_active": True
            }
            
            # Return a simple object that allows attribute access
            class UserObj:
                def __init__(self, data):
                    self.id = data["id"]
                    self.email = data["email"]
                    self.full_name = data["full_name"]
                    self.is_active = data["is_active"]
                    
            return UserObj(user_data)
        except Exception as e:
            logger.error(f"Get current user error: {str(e)}")
            return None