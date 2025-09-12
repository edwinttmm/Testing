# Critical Fixes - Phase 1 Implementation Guide

## Overview

This document provides step-by-step instructions for implementing the most critical fixes that must be completed before the system can function properly. These fixes address system-breaking issues that prevent deployment and basic operation.

## Pre-Implementation Checklist

- [ ] Backup current database
- [ ] Create feature branch: `git checkout -b critical-fixes-phase1`
- [ ] Document current configuration
- [ ] Verify development environment setup

---

## Fix 1: Authentication System Implementation

**Priority**: CRITICAL  
**Estimated Time**: 2-3 days  
**Risk Level**: Medium  

### Problem
The system has no authentication mechanism, making it a critical security vulnerability and preventing proper user management.

### Current State
- No user model in database
- No authentication endpoints
- Frontend assumes authentication but none exists
- No session management

### Implementation Steps

#### Step 1: Install Required Dependencies

```bash
# Backend dependencies
cd backend
pip install python-jose[cryptography]==3.3.0
pip install passlib[bcrypt]==1.7.4
pip install python-multipart==0.0.6

# Add to requirements.txt
echo "python-jose[cryptography]==3.3.0" >> requirements.txt
echo "passlib[bcrypt]==1.7.4" >> requirements.txt
echo "python-multipart==0.0.6" >> requirements.txt
```

#### Step 2: Update Database Models

Create or update `backend/models.py`:

```python
# Add to existing models.py
from passlib.context import CryptContext
import uuid
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.sql import func

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthUser(Base):
    """User authentication model"""
    __tablename__ = "auth_users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    is_superuser = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)
    
    @classmethod
    def get_password_hash(cls, password: str) -> str:
        return pwd_context.hash(password)
    
    def set_password(self, password: str) -> None:
        self.hashed_password = self.get_password_hash(password)
```

#### Step 3: Create Authentication Service

Create `backend/auth_service.py`:

```python
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import os

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

security = HTTPBearer()

class AuthService:
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

auth_service = AuthService()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    # Get user from database
    from database import get_db
    from models import AuthUser
    
    db = next(get_db())
    user = db.query(AuthUser).filter(AuthUser.username == payload.get("sub")).first()
    
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user

# Optional authentication (for endpoints that work with or without auth)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
):
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
```

#### Step 4: Create Authentication Endpoints

Create `backend/auth_endpoints.py`:

```python
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from database import get_db
from models import AuthUser
from auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

@router.post("/register", response_model=dict)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(AuthUser).filter(
        (AuthUser.email == user_data.email) | 
        (AuthUser.username == user_data.username)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    # Create new user
    db_user = AuthUser(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name
    )
    db_user.set_password(user_data.password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {"message": "User created successfully", "user_id": db_user.id}

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    # Authenticate user
    user = db.query(AuthUser).filter(AuthUser.username == user_data.username).first()
    
    if not user or not user.verify_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create access token
    access_token = auth_service.create_access_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name
        }
    }

@router.get("/me")
async def get_current_user_info(current_user: AuthUser = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active
    }
```

#### Step 5: Update Main Application

Update `backend/main.py`:

```python
# Add to existing imports
from auth_endpoints import router as auth_router

# Add to FastAPI app
app.include_router(auth_router)

# Add authentication to existing endpoints
from auth_service import get_current_user, get_current_user_optional

# Example: Protect video upload endpoint
@app.post("/api/projects/{project_id}/videos")
async def upload_video(
    project_id: str,
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user)  # Add this line
):
    # Existing video upload logic
    pass
```

#### Step 6: Create Database Migration

Create `backend/migrations/add_auth_tables.py`:

```python
"""Add authentication tables

Revision ID: auth_001
Create Date: 2024-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Create auth_users table
    op.create_table(
        'auth_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=True),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_superuser', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now())
    )
    
    # Create indexes
    op.create_index('idx_auth_users_email', 'auth_users', ['email'], unique=True)
    op.create_index('idx_auth_users_username', 'auth_users', ['username'], unique=True)
    op.create_index('idx_auth_users_active', 'auth_users', ['is_active'])
    
    # Create default admin user
    op.execute("""
        INSERT INTO auth_users (id, email, username, full_name, hashed_password, is_superuser)
        VALUES (
            'admin-user-id-12345',
            'admin@example.com',
            'admin',
            'System Administrator',
            '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',  -- password: admin123
            true
        );
    """)

def downgrade():
    op.drop_index('idx_auth_users_active')
    op.drop_index('idx_auth_users_username')
    op.drop_index('idx_auth_users_email')
    op.drop_table('auth_users')
```

#### Step 7: Frontend Authentication Hook

Create `frontend/src/hooks/useAuth.ts`:

```typescript
import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiService } from '../services/api';

interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => Promise<void>;
  isLoading: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check for existing token on startup
    const token = localStorage.getItem('access_token');
    if (token) {
      // Verify token and get user info
      checkAuthStatus();
    } else {
      setIsLoading(false);
    }
  }, []);

  const checkAuthStatus = async () => {
    try {
      const userInfo = await apiService.get('/auth/me');
      setUser(userInfo);
    } catch (error) {
      // Token is invalid, remove it
      localStorage.removeItem('access_token');
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await apiService.post('/auth/login', { username, password });
      
      localStorage.setItem('access_token', response.access_token);
      setUser(response.user);
    } catch (error) {
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (userData: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => {
    setIsLoading(true);
    try {
      await apiService.post('/auth/register', userData);
      // Auto-login after registration
      await login(userData.username, userData.password);
    } catch (error) {
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
  };

  const value = {
    user,
    login,
    logout,
    register,
    isLoading,
    isAuthenticated: !!user
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

#### Step 8: Update API Service for Authentication

Update `frontend/src/services/api.ts`:

```typescript
// Add to existing ApiService class
class ApiService {
  private getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  private setupInterceptors() {
    // Request interceptor to add auth token
    this.api.interceptors.request.use(
      (config) => {
        const token = this.getToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor to handle auth errors
    this.api.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          // Token is invalid, redirect to login
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }
}
```

#### Step 9: Create Login Component

Create `frontend/src/components/Auth/LoginForm.tsx`:

```typescript
import React, { useState } from 'react';
import { useAuth } from '../../hooks/useAuth';
import { useNavigate } from 'react-router-dom';

export const LoginForm: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Login failed');
    }
  };

  return (
    <div className="login-form">
      <h2>Login</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="username">Username:</label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>
        
        <div>
          <label htmlFor="password">Password:</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        
        {error && <div className="error">{error}</div>}
        
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Logging in...' : 'Login'}
        </button>
      </form>
    </div>
  );
};
```

#### Step 10: Testing Authentication

Create test script `backend/test_auth.py`:

```python
import requests
import json

BASE_URL = "http://localhost:8000"

def test_authentication_flow():
    print("Testing authentication flow...")
    
    # Test registration
    register_data = {
        "username": "testuser",
        "email": "test@example.com", 
        "password": "testpassword123",
        "full_name": "Test User"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    print(f"Registration: {response.status_code}")
    
    # Test login
    login_data = {
        "username": "testuser",
        "password": "testpassword123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    print(f"Login: {response.status_code}")
    
    if response.status_code == 200:
        token_data = response.json()
        token = token_data["access_token"]
        
        # Test protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        print(f"Protected endpoint: {response.status_code}")
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"User data: {json.dumps(user_data, indent=2)}")

if __name__ == "__main__":
    test_authentication_flow()
```

### Testing Checklist

- [ ] Backend starts without errors after migration
- [ ] Registration endpoint creates user successfully
- [ ] Login endpoint returns valid JWT token
- [ ] Protected endpoints reject requests without token
- [ ] Protected endpoints accept requests with valid token
- [ ] Frontend login form works with backend
- [ ] Authentication context manages user state correctly
- [ ] Token is persisted across browser sessions

---

## Fix 2: Frontend-Backend API Integration

**Priority**: CRITICAL  
**Estimated Time**: 3-4 days  
**Risk Level**: High  

### Problem
Frontend and backend have incompatible API contracts, causing all communication to fail.

### Current State Analysis

#### API Endpoint Mismatches Found:
1. Frontend expects `/api/projects/{id}/videos` but backend has `/projects/{id}/videos`
2. Response format inconsistencies (snake_case vs camelCase)
3. Missing error handling standards
4. CORS configuration incomplete
5. Video URL construction broken

### Implementation Steps

#### Step 1: Standardize API Response Format

Create `backend/api_standards.py`:

```python
from pydantic import BaseModel
from typing import Any, Optional, Dict, List
from datetime import datetime
import uuid

class APIResponse(BaseModel):
    """Standard API response format"""
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None
    timestamp: str
    request_id: str
    
    @classmethod
    def success_response(
        cls, 
        data: Any = None, 
        message: str = "Operation successful"
    ):
        return cls(
            success=True,
            data=data,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
            request_id=str(uuid.uuid4())[:8]
        )
    
    @classmethod
    def error_response(
        cls, 
        error: str, 
        message: str = "Operation failed",
        data: Any = None
    ):
        return cls(
            success=False,
            error=error,
            message=message,
            data=data,
            timestamp=datetime.utcnow().isoformat(),
            request_id=str(uuid.uuid4())[:8]
        )

class PaginatedResponse(BaseModel):
    """Standard paginated response"""
    items: List[Any]
    total: int
    page: int = 1
    per_page: int = 50
    has_next: bool
    has_prev: bool
    
def paginate_query(query, page: int = 1, per_page: int = 50):
    """Helper function to paginate SQLAlchemy queries"""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        has_next=page * per_page < total,
        has_prev=page > 1
    )
```

#### Step 2: Fix Video API Endpoints

Update `backend/main.py` video endpoints:

```python
from api_standards import APIResponse, paginate_query
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
import os
from pathlib import Path

# Video endpoints with correct paths and responses
@app.get("/api/projects/{project_id}/videos")
async def get_project_videos(
    project_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100)
):
    """Get videos for a specific project"""
    try:
        # Query videos for project
        query = db.query(Video).filter(Video.project_id == project_id)
        paginated_result = paginate_query(query, page, per_page)
        
        # Fix video URLs
        for video in paginated_result.items:
            video.url = f"/api/videos/{video.id}/stream"
            video.thumbnail_url = f"/api/videos/{video.id}/thumbnail"
        
        return APIResponse.success_response(
            data=paginated_result,
            message=f"Retrieved {len(paginated_result.items)} videos"
        )
        
    except Exception as e:
        return APIResponse.error_response(
            error=str(e),
            message="Failed to retrieve videos"
        )

@app.post("/api/projects/{project_id}/videos")
async def upload_project_video(
    project_id: str,
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload video to specific project"""
    try:
        # Validate file type
        if not file.content_type.startswith('video/'):
            raise HTTPException(400, "File must be a video")
        
        # Validate project exists
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(404, "Project not found")
        
        # Save file
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix.lower()
        filename = f"{file_id}{file_extension}"
        
        upload_dir = Path("uploads/videos")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename
        
        # Save uploaded file
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Extract video metadata
        metadata = extract_video_metadata(file_path)
        
        # Create database record
        video = Video(
            id=file_id,
            filename=file.filename,
            file_path=str(file_path),
            project_id=project_id,
            file_size=len(content),
            duration=metadata.get('duration'),
            fps=metadata.get('fps'),
            resolution=f"{metadata.get('width')}x{metadata.get('height')}",
            status='uploaded'
        )
        
        db.add(video)
        db.commit()
        db.refresh(video)
        
        # Add URLs to response
        video.url = f"/api/videos/{video.id}/stream"
        video.thumbnail_url = f"/api/videos/{video.id}/thumbnail"
        
        return APIResponse.success_response(
            data=video,
            message="Video uploaded successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        return APIResponse.error_response(
            error=str(e),
            message="Video upload failed"
        )

def extract_video_metadata(file_path: Path) -> Dict:
    """Extract metadata from video file"""
    try:
        import cv2
        cap = cv2.VideoCapture(str(file_path))
        
        if not cap.isOpened():
            return {}
        
        metadata = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        }
        
        cap.release()
        return metadata
        
    except Exception as e:
        print(f"Error extracting video metadata: {e}")
        return {}

# Video streaming endpoint
@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: str):
    """Stream video file"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    
    file_path = Path(video.file_path)
    if not file_path.exists():
        raise HTTPException(404, "Video file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        media_type='video/mp4',
        filename=video.filename
    )

# Thumbnail generation endpoint  
@app.get("/api/videos/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: str):
    """Get video thumbnail"""
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(404, "Video not found")
    
    thumbnail_path = Path(f"uploads/thumbnails/{video_id}.jpg")
    
    if not thumbnail_path.exists():
        # Generate thumbnail
        generate_thumbnail(video.file_path, thumbnail_path)
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=thumbnail_path,
        media_type='image/jpeg'
    )

def generate_thumbnail(video_path: str, output_path: Path):
    """Generate thumbnail from video"""
    try:
        import cv2
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cap = cv2.VideoCapture(video_path)
        
        # Seek to middle of video for thumbnail
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        middle_frame = frame_count // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
        
        ret, frame = cap.read()
        if ret:
            # Resize frame for thumbnail
            height, width = frame.shape[:2]
            max_size = 200
            
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            
            thumbnail = cv2.resize(frame, (new_width, new_height))
            cv2.imwrite(str(output_path), thumbnail)
        
        cap.release()
        
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        # Create placeholder thumbnail
        import numpy as np
        placeholder = np.zeros((200, 200, 3), dtype=np.uint8)
        cv2.imwrite(str(output_path), placeholder)
```

#### Step 3: Update Frontend API Service

Update `frontend/src/services/api.ts`:

```typescript
// Update ApiService class
export class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.api.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor for standard API responses
    this.api.interceptors.response.use(
      (response) => {
        // Handle standard API response format
        if (response.data && typeof response.data === 'object') {
          if ('success' in response.data) {
            // This is a standard API response
            if (!response.data.success) {
              throw new Error(response.data.error || 'API request failed');
            }
            // Return the data portion
            return {
              ...response,
              data: response.data.data
            };
          }
        }
        return response;
      },
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
        
        // Handle standard error response
        if (error.response?.data?.error) {
          throw new Error(error.response.data.error);
        }
        
        return Promise.reject(error);
      }
    );
  }

  // Updated video methods
  async getProjectVideos(projectId: string, page: number = 1): Promise<{items: VideoFile[], total: number}> {
    const response = await this.api.get(`/api/projects/${projectId}/videos`, {
      params: { page, per_page: 50 }
    });
    return response.data;
  }

  async uploadVideo(
    projectId: string, 
    file: File, 
    onProgress?: (progress: number) => void
  ): Promise<VideoFile> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.api.post(`/api/projects/${projectId}/videos`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          onProgress(progress);
        }
      },
    });

    return response.data;
  }

  // Helper method to get video URL
  getVideoUrl(videoId: string): string {
    return `${this.api.defaults.baseURL}/api/videos/${videoId}/stream`;
  }

  // Helper method to get thumbnail URL
  getThumbnailUrl(videoId: string): string {
    return `${this.api.defaults.baseURL}/api/videos/${videoId}/thumbnail`;
  }
}

export const apiService = new ApiService();
```

#### Step 4: Fix CORS Configuration

Update `backend/main.py` CORS setup:

```python
from fastapi.middleware.cors import CORSMiddleware

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000", 
        "http://localhost:3001",  # Dev server alternative
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add OPTIONS preflight handler
@app.options("/{full_path:path}")
async def options_handler():
    return {"message": "OK"}
```

#### Step 5: Create API Contract Tests

Create `backend/test_api_contract.py`:

```python
import pytest
import requests
import os
from pathlib import Path

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_USERNAME = "test_api_user"
TEST_PASSWORD = "test_password_123"
TEST_EMAIL = "test@api.com"

class TestAPIContract:
    def setup_method(self):
        """Setup test user and authentication"""
        # Register test user
        register_data = {
            "username": TEST_USERNAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
        
        try:
            requests.post(f"{BASE_URL}/auth/register", json=register_data)
        except:
            pass  # User might already exist
        
        # Login and get token
        login_data = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
        
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        assert response.status_code == 200
        
        token_data = response.json()
        self.token = token_data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_api_response_format(self):
        """Test that all API responses follow standard format"""
        # Test with a simple endpoint
        response = requests.get(f"{BASE_URL}/auth/me", headers=self.headers)
        
        assert response.status_code == 200
        # Note: We expect the actual user data, not the APIResponse wrapper
        # because the frontend interceptor extracts the data
        data = response.json()
        assert "id" in data
        assert "username" in data

    def test_project_video_endpoints(self):
        """Test project and video endpoint contracts"""
        # Create test project
        project_data = {
            "name": "Test Project",
            "description": "API Contract Test Project",
            "camera_model": "Test Camera",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        response = requests.post(f"{BASE_URL}/api/projects", json=project_data, headers=self.headers)
        assert response.status_code == 200
        
        project = response.json()
        project_id = project["id"]
        
        # Test get project videos (empty)
        response = requests.get(f"{BASE_URL}/api/projects/{project_id}/videos", headers=self.headers)
        assert response.status_code == 200
        
        video_data = response.json()
        assert "items" in video_data
        assert "total" in video_data
        assert video_data["total"] == 0

    def test_error_response_format(self):
        """Test that error responses follow standard format"""
        # Test with invalid endpoint
        response = requests.get(f"{BASE_URL}/api/nonexistent", headers=self.headers)
        
        assert response.status_code == 404
        # The frontend should receive an error

    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = requests.options(f"{BASE_URL}/api/projects", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers

if __name__ == "__main__":
    # Run tests
    test_client = TestAPIContract()
    test_client.setup_method()
    
    print("Testing API response format...")
    test_client.test_api_response_format()
    print("✓ API response format correct")
    
    print("Testing project/video endpoints...")
    test_client.test_project_video_endpoints()
    print("✓ Project/video endpoints working")
    
    print("Testing error responses...")
    test_client.test_error_response_format()
    print("✓ Error responses correct")
    
    print("Testing CORS headers...")
    test_client.test_cors_headers()
    print("✓ CORS headers present")
    
    print("\n🎉 All API contract tests passed!")
```

#### Step 6: Frontend Integration Testing

Create `frontend/src/tests/api-integration.test.ts`:

```typescript
import { apiService } from '../services/api';

describe('API Integration', () => {
  let authToken: string;
  let testProjectId: string;

  beforeAll(async () => {
    // Setup test user and get auth token
    try {
      await apiService.post('/auth/register', {
        username: 'test-frontend-user',
        email: 'frontend-test@example.com',
        password: 'test-password-123'
      });
    } catch (error) {
      // User might already exist
    }

    const loginResponse = await apiService.post('/auth/login', {
      username: 'test-frontend-user',
      password: 'test-password-123'
    });

    authToken = loginResponse.access_token;
    localStorage.setItem('access_token', authToken);
  });

  test('should create project successfully', async () => {
    const projectData = {
      name: 'Test Project Frontend',
      description: 'Frontend integration test',
      camera_model: 'Test Camera',
      camera_view: 'Front-facing VRU',
      signal_type: 'GPIO'
    };

    const project = await apiService.post('/api/projects', projectData);
    
    expect(project).toHaveProperty('id');
    expect(project.name).toBe(projectData.name);
    
    testProjectId = project.id;
  });

  test('should get project videos', async () => {
    const videos = await apiService.getProjectVideos(testProjectId);
    
    expect(videos).toHaveProperty('items');
    expect(videos).toHaveProperty('total');
    expect(Array.isArray(videos.items)).toBe(true);
    expect(videos.total).toBe(0); // Should be empty initially
  });

  test('should handle API errors gracefully', async () => {
    try {
      await apiService.get('/api/nonexistent-endpoint');
      fail('Should have thrown an error');
    } catch (error) {
      expect(error).toBeInstanceOf(Error);
    }
  });

  afterAll(async () => {
    // Cleanup test data if possible
    if (testProjectId) {
      try {
        await apiService.delete(`/api/projects/${testProjectId}`);
      } catch (error) {
        // Ignore cleanup errors
      }
    }
  });
});
```

### Testing Checklist

- [ ] All API endpoints return standard response format
- [ ] Frontend can successfully call all endpoints
- [ ] Authentication works end-to-end
- [ ] CORS headers allow frontend requests
- [ ] Error responses are handled correctly
- [ ] Video upload and streaming work
- [ ] Pagination works correctly
- [ ] API contract tests pass

---

## Fix 3: Configuration Management

**Priority**: CRITICAL  
**Estimated Time**: 1-2 days  
**Risk Level**: Low  

### Problem
Multiple conflicting environment variable systems prevent consistent configuration across environments.

### Current State
- 3 different naming conventions: `VRU_`, `AIVALIDATION_`, `REACT_APP_`
- Inconsistent database configuration
- CORS origins hardcoded in multiple places
- Port conflicts between services

### Implementation Steps

#### Step 1: Create Unified Environment Configuration

Create `.env.unified`:

```bash
# =============================================================================
# AI MODEL VALIDATION PLATFORM - UNIFIED CONFIGURATION
# =============================================================================

# Environment
ENVIRONMENT=development
DEBUG=true
NODE_ENV=development

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
# PostgreSQL Configuration (Production/Docker)
DATABASE_URL=postgresql://ai_user:ai_password_2024@postgres:5432/ai_validation
POSTGRES_DB=ai_validation
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=ai_password_2024
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Database Pool Settings
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_ECHO=false
DATABASE_SSLMODE=prefer

# =============================================================================
# API CONFIGURATION  
# =============================================================================
API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000

# =============================================================================
# FRONTEND CONFIGURATION
# =============================================================================
FRONTEND_PORT=3000
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_ENVIRONMENT=development
REACT_APP_DEBUG=true

# Build Configuration
GENERATE_SOURCEMAP=false
SKIP_PREFLIGHT_CHECK=true
TSC_COMPILE_ON_ERROR=true
ESLINT_NO_DEV_ERRORS=true

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================
# CRITICAL: Change these in production!
SECRET_KEY=dev-secret-key-change-in-production-32-chars
JWT_SECRET_KEY=dev-jwt-secret-change-in-production-32-chars
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# =============================================================================
# CORS CONFIGURATION
# =============================================================================
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================
REDIS_URL=redis://redis:6379/0
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=redis_password_2024
REDIS_DB=0

# =============================================================================
# FILE UPLOAD CONFIGURATION
# =============================================================================
MAX_FILE_SIZE=100MB
ALLOWED_VIDEO_EXTENSIONS=.mp4,.avi,.mov,.mkv,.webm
UPLOAD_DIRECTORY=uploads

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s

# =============================================================================
# DOCKER CONFIGURATION
# =============================================================================
DOCKER_MODE=true

# =============================================================================
# LABJACK CONFIGURATION
# =============================================================================
LABJACK_MOCK_MODE=true
LABJACK_DEVICE_TYPE=T7
LABJACK_CHANNELS=AIN0,AIN1
LABJACK_SAMPLE_RATE=1000

# =============================================================================
# DEVELOPMENT OVERRIDES (for local development)
# =============================================================================
# Uncomment and modify these for local development without Docker:
# DATABASE_URL=sqlite:///./dev_database.db
# REDIS_URL=redis://localhost:6379/0
# API_BASE_URL=http://localhost:8000
# REACT_APP_API_URL=http://localhost:8000
```

#### Step 2: Create Environment-Specific Files

Create `.env.development`:

```bash
# Development environment overrides
ENVIRONMENT=development
DEBUG=true

# Use SQLite for local development
DATABASE_URL=sqlite:///./dev_database.db

# Local Redis
REDIS_URL=redis://localhost:6379/0

# Development secrets (insecure, for dev only)
SECRET_KEY=dev-secret-key-for-development-only-32-chars
JWT_SECRET_KEY=dev-jwt-secret-for-development-only-32-chars

# Local services
API_BASE_URL=http://localhost:8000
REACT_APP_API_URL=http://localhost:8000
REACT_APP_WS_URL=ws://localhost:8000

# Enable debugging
REACT_APP_DEBUG=true
LOG_LEVEL=DEBUG

# LabJack in mock mode for development
LABJACK_MOCK_MODE=true
```

Create `.env.production`:

```bash
# Production environment configuration
ENVIRONMENT=production
DEBUG=false
NODE_ENV=production

# Production database (set actual values)
DATABASE_URL=${DATABASE_URL}  # Set via environment
POSTGRES_DB=${POSTGRES_DB}
POSTGRES_USER=${POSTGRES_USER}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}

# Production security (MUST be set via environment variables)
SECRET_KEY=${SECRET_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}

# Production URLs (set actual values)
API_BASE_URL=${API_BASE_URL}
REACT_APP_API_URL=${REACT_APP_API_URL}
REACT_APP_WS_URL=${REACT_APP_WS_URL}

# Production CORS (restrict to actual domains)
CORS_ORIGINS=${CORS_ORIGINS}

# Production logging
LOG_LEVEL=INFO

# Disable debug features
REACT_APP_DEBUG=false
GENERATE_SOURCEMAP=false

# Real LabJack hardware
LABJACK_MOCK_MODE=false
```

#### Step 3: Create Configuration Validation

Create `backend/config_manager.py`:

```python
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

@dataclass
class ConfigValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    missing_vars: List[str]

class ConfigManager:
    def __init__(self):
        self.required_vars = [
            'DATABASE_URL',
            'SECRET_KEY',
            'API_PORT',
            'ENVIRONMENT'
        ]
        
        self.production_required = [
            'POSTGRES_DB',
            'POSTGRES_USER', 
            'POSTGRES_PASSWORD',
            'JWT_SECRET_KEY',
            'CORS_ORIGINS'
        ]
        
        self.security_checks = [
            ('SECRET_KEY', 32),  # Minimum length
            ('JWT_SECRET_KEY', 32),
        ]
        
        self.insecure_defaults = [
            'dev-secret-key',
            'change-me',
            'insecure',
            'test-key',
            'dev-jwt-secret'
        ]

    def validate_configuration(self) -> ConfigValidationResult:
        """Validate current environment configuration"""
        errors = []
        warnings = []
        missing_vars = []
        
        environment = os.getenv('ENVIRONMENT', 'development').lower()
        
        # Check required variables
        for var in self.required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
                errors.append(f"Required variable {var} is missing")
        
        # Check production-specific requirements
        if environment == 'production':
            for var in self.production_required:
                if not os.getenv(var):
                    missing_vars.append(var)
                    errors.append(f"Production variable {var} is missing")
        
        # Security checks
        for var, min_length in self.security_checks:
            value = os.getenv(var, '')
            if len(value) < min_length:
                errors.append(f"{var} must be at least {min_length} characters long")
            
            # Check for insecure defaults
            if any(default in value.lower() for default in self.insecure_defaults):
                if environment == 'production':
                    errors.append(f"{var} is using an insecure default in production")
                else:
                    warnings.append(f"{var} is using a development default")
        
        # Database configuration checks
        db_url = os.getenv('DATABASE_URL', '')
        if 'sqlite' in db_url.lower() and environment == 'production':
            warnings.append("Using SQLite in production - consider PostgreSQL")
        
        # CORS configuration checks
        cors_origins = os.getenv('CORS_ORIGINS', '')
        if not cors_origins:
            warnings.append("CORS_ORIGINS not configured - may block frontend requests")
        elif cors_origins == '*':
            if environment == 'production':
                errors.append("CORS wildcard (*) not allowed in production")
            else:
                warnings.append("CORS wildcard should not be used in production")
        
        # Port configuration checks
        api_port = os.getenv('API_PORT', '8000')
        frontend_port = os.getenv('FRONTEND_PORT', '3000')
        if api_port == frontend_port:
            errors.append("API_PORT and FRONTEND_PORT cannot be the same")
        
        return ConfigValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            missing_vars=missing_vars
        )

    def get_config_summary(self) -> Dict:
        """Get summary of current configuration"""
        return {
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'database_type': 'postgresql' if 'postgresql' in os.getenv('DATABASE_URL', '') else 'sqlite',
            'api_port': os.getenv('API_PORT', '8000'),
            'frontend_port': os.getenv('FRONTEND_PORT', '3000'),
            'cors_origins_count': len(os.getenv('CORS_ORIGINS', '').split(',')) if os.getenv('CORS_ORIGINS') else 0,
            'debug_enabled': os.getenv('DEBUG', 'false').lower() == 'true',
            'labjack_mock_mode': os.getenv('LABJACK_MOCK_MODE', 'true').lower() == 'true',
        }

    def validate_and_log(self):
        """Validate configuration and log results"""
        logger = logging.getLogger(__name__)
        
        result = self.validate_configuration()
        config_summary = self.get_config_summary()
        
        logger.info(f"Configuration Summary: {config_summary}")
        
        if result.errors:
            logger.error("Configuration Errors Found:")
            for error in result.errors:
                logger.error(f"  - {error}")
        
        if result.warnings:
            logger.warning("Configuration Warnings:")
            for warning in result.warnings:
                logger.warning(f"  - {warning}")
        
        if result.is_valid:
            logger.info("✓ Configuration validation passed")
        else:
            logger.error("✗ Configuration validation failed")
            if config_summary['environment'] == 'production':
                raise ValueError("Production configuration validation failed")
        
        return result

# Global instance
config_manager = ConfigManager()
```

#### Step 4: Update Backend Configuration Loading

Update `backend/config.py`:

```python
import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator
import logging
from config_manager import config_manager

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Unified application settings"""
    
    # Environment
    environment: str = "development"
    debug: bool = False
    
    # Database
    database_url: str = "sqlite:///./dev_database.db"
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_echo: bool = False
    
    # API
    api_host: str = "0.0.0.0" 
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"
    
    # Security
    secret_key: str = "dev-secret-key-change-in-production-32-chars"
    jwt_secret_key: str = "dev-jwt-secret-change-in-production-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_credentials: bool = True
    cors_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_headers: List[str] = ["*"]
    
    # File uploads
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_video_extensions: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    upload_directory: str = "uploads"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # LabJack
    labjack_mock_mode: bool = True
    labjack_device_type: str = "T7"
    labjack_channels: List[str] = ["AIN0", "AIN1"]
    labjack_sample_rate: int = 1000
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @field_validator('cors_origins', mode='before')
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return ["http://localhost:3000"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    @field_validator('allowed_video_extensions', mode='before')
    def parse_allowed_extensions(cls, v):
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",") if ext.strip()]
        return v
    
    @field_validator('labjack_channels', mode='before')
    def parse_labjack_channels(cls, v):
        if isinstance(v, str):
            return [channel.strip() for channel in v.split(",") if channel.strip()]
        return v
    
    @field_validator('max_file_size', mode='before')
    def parse_file_size(cls, v):
        if isinstance(v, str):
            v = v.upper()
            if v.endswith('MB'):
                return int(v[:-2]) * 1024 * 1024
            elif v.endswith('GB'):
                return int(v[:-2]) * 1024 * 1024 * 1024
            else:
                return int(v)
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

def get_settings() -> Settings:
    """Get validated application settings"""
    # Validate configuration before creating settings
    validation_result = config_manager.validate_and_log()
    
    if not validation_result.is_valid:
        logger.error("Configuration validation failed!")
        if os.getenv('ENVIRONMENT', '').lower() == 'production':
            raise ValueError("Invalid production configuration")
    
    return Settings()

# Global settings instance
settings = get_settings()
```

#### Step 5: Update Docker Compose Configuration

Update `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    container_name: ai_validation_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - ai_validation_network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: ai_validation_redis
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - ai_validation_network
    command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  backend:
    build: ./backend
    container_name: ai_validation_backend
    ports:
      - "0.0.0.0:${API_PORT}:${API_PORT}"
    environment:
      # Pass all environment variables to container
      - DATABASE_URL=${DATABASE_URL}
      - SECRET_KEY=${SECRET_KEY}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - API_HOST=${API_HOST}
      - API_PORT=${API_PORT}
      - CORS_ORIGINS=${CORS_ORIGINS}
      - REDIS_URL=${REDIS_URL}
      - ENVIRONMENT=${ENVIRONMENT}
      - DEBUG=${DEBUG}
      - LOG_LEVEL=${LOG_LEVEL}
      - LABJACK_MOCK_MODE=${LABJACK_MOCK_MODE}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - ai_validation_network
    volumes:
      - ./backend:/app
      - uploaded_files:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${API_PORT}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  frontend:
    build: ./frontend
    container_name: ai_validation_frontend
    ports:
      - "0.0.0.0:${FRONTEND_PORT}:${FRONTEND_PORT}"
    environment:
      - REACT_APP_API_URL=${REACT_APP_API_URL}
      - REACT_APP_WS_URL=${REACT_APP_WS_URL}
      - REACT_APP_ENVIRONMENT=${REACT_APP_ENVIRONMENT}
      - REACT_APP_DEBUG=${REACT_APP_DEBUG}
      - NODE_ENV=${NODE_ENV}
      - GENERATE_SOURCEMAP=${GENERATE_SOURCEMAP}
      - PORT=${FRONTEND_PORT}
    depends_on:
      - backend
    networks:
      - ai_validation_network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${FRONTEND_PORT}"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  uploaded_files:

networks:
  ai_validation_network:
    driver: bridge
```

#### Step 6: Create Configuration Testing

Create `test_configuration.py`:

```python
#!/usr/bin/env python3

import os
import sys
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from config_manager import ConfigManager

def test_configuration_scenarios():
    """Test different configuration scenarios"""
    
    config_manager = ConfigManager()
    
    print("🧪 Testing Configuration Scenarios")
    print("=" * 50)
    
    # Test 1: Minimal valid configuration
    print("\nTest 1: Minimal Development Configuration")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        f.write("""
DATABASE_URL=sqlite:///./test.db
SECRET_KEY=test-secret-key-32-characters-long-enough
API_PORT=8000
ENVIRONMENT=development
        """)
        env_file = f.name
    
    # Load test environment
    from dotenv import load_dotenv
    load_dotenv(env_file)
    
    result = config_manager.validate_configuration()
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {len(result.errors)}")
    print(f"  Warnings: {len(result.warnings)}")
    
    # Test 2: Production configuration with errors
    print("\nTest 2: Invalid Production Configuration")
    os.environ.update({
        'ENVIRONMENT': 'production',
        'SECRET_KEY': 'insecure',  # Too short and insecure
        'DATABASE_URL': 'sqlite:///./prod.db'  # SQLite in production
    })
    
    result = config_manager.validate_configuration()
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {result.errors}")
    print(f"  Warnings: {result.warnings}")
    
    # Test 3: Valid production configuration
    print("\nTest 3: Valid Production Configuration")
    os.environ.update({
        'SECRET_KEY': 'secure-production-key-32-characters-long-enough-secure',
        'JWT_SECRET_KEY': 'secure-jwt-production-key-32-characters-long-enough',
        'DATABASE_URL': 'postgresql://user:pass@localhost:5432/ai_validation',
        'POSTGRES_DB': 'ai_validation',
        'POSTGRES_USER': 'user',
        'POSTGRES_PASSWORD': 'secure_password',
        'CORS_ORIGINS': 'https://example.com,https://www.example.com'
    })
    
    result = config_manager.validate_configuration()
    print(f"  Valid: {result.is_valid}")
    print(f"  Errors: {result.errors}")
    print(f"  Warnings: {result.warnings}")
    
    # Test 4: Configuration summary
    print("\nTest 4: Configuration Summary")
    summary = config_manager.get_config_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Cleanup
    os.unlink(env_file)
    
    print("\n✅ Configuration testing complete!")

if __name__ == "__main__":
    test_configuration_scenarios()
```

### Testing Checklist

- [ ] Configuration validation catches missing variables
- [ ] Development and production configs load correctly
- [ ] Docker Compose uses unified environment variables
- [ ] Backend and frontend use consistent configuration
- [ ] Security checks prevent insecure defaults in production
- [ ] Configuration summary provides useful information

---

## Implementation Timeline

### Day 1-2: Authentication System
- [ ] Install authentication dependencies
- [ ] Create user model and migration
- [ ] Implement authentication service and endpoints
- [ ] Create frontend authentication components
- [ ] Test authentication flow end-to-end

### Day 3-5: API Integration Fixes
- [ ] Standardize API response format
- [ ] Fix all video-related endpoints
- [ ] Update frontend API service
- [ ] Configure CORS properly
- [ ] Create and run API contract tests

### Day 6-7: Configuration Management
- [ ] Create unified environment configuration
- [ ] Implement configuration validation
- [ ] Update Docker Compose files
- [ ] Test configuration in different environments
- [ ] Create configuration documentation

### Day 8: Integration Testing
- [ ] Run end-to-end tests
- [ ] Fix any integration issues
- [ ] Verify deployment process works
- [ ] Create rollback procedures

## Success Criteria

**Phase 1 Complete When:**
- [ ] Users can register and login successfully
- [ ] Frontend can communicate with backend without errors
- [ ] Configuration is consistent across all services
- [ ] System can be deployed without manual intervention
- [ ] All basic CRUD operations work
- [ ] Authentication protects appropriate endpoints
- [ ] Error handling provides useful feedback
- [ ] Logging provides adequate debugging information

## Risk Mitigation

**High-Risk Areas:**
1. **Database Migration**: Test thoroughly on copy of production data
2. **Authentication Integration**: Verify doesn't break existing sessions
3. **CORS Configuration**: Test from all expected frontend origins
4. **Configuration Changes**: Validate in staging environment first

**Rollback Plan:**
1. Keep backup of current configuration files
2. Document all database schema changes
3. Create script to restore previous API format
4. Have staging environment that mirrors production

This completes the critical fixes documentation. The next phase will focus on implementing missing functionality and performance improvements.