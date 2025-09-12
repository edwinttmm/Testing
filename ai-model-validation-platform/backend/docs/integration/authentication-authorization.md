# Authentication and Authorization Flow Analysis

## Overview
This document analyzes the authentication and authorization systems, user session management, and security flows within the AI Model Validation Platform. Currently the system operates in a simplified mode without full authentication, but this document outlines both the current state and the planned security architecture.

## Current Authentication State

### 1. Simplified Anonymous Mode

#### Current Implementation
```python
# Current simplified authentication (main.py)
# Authentication system temporarily disabled for development
from auth_endpoints import router as auth_router

# Default user context
DEFAULT_USER_ID = "anonymous"
DEFAULT_USER_CONTEXT = {
    "user_id": "anonymous",
    "username": "anonymous_user",
    "permissions": ["read", "write", "execute"],
    "role": "developer"
}

def get_current_user() -> dict:
    """Get current user context (simplified)"""
    return DEFAULT_USER_CONTEXT

def get_user_projects_filter(user_id: str = "anonymous") -> dict:
    """Get user-specific project filter"""
    return {"owner_id": user_id}
```

#### Simplified Authorization Pattern
```python
# CRUD operations with minimal authorization
def get_projects(db: Session, user_id: str = "anonymous", skip: int = 0, limit: int = 100):
    """Get projects for user with basic filtering"""
    return db.query(Project).filter(
        Project.owner_id == user_id
    ).offset(skip).limit(limit).all()

def create_project(db: Session, project: ProjectCreate, user_id: str = "anonymous"):
    """Create project with user ownership"""
    db_project = Project(
        **project.model_dump(),
        owner_id=user_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project
```

## Planned Authentication Architecture

### 1. JWT Token-Based Authentication

#### Authentication Service Design
```python
# auth_service.py - Planned authentication service
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

class AuthenticationService:
    """JWT-based authentication service"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.jwt_secret_key
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.jwt_expire_minutes
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: timedelta = None) -> str:
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
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id: str = payload.get("sub")
            
            if user_id is None:
                return None
                
            return {
                "user_id": user_id,
                "username": payload.get("username"),
                "email": payload.get("email"),
                "role": payload.get("role", "user"),
                "permissions": payload.get("permissions", []),
                "exp": payload.get("exp")
            }
        except JWTError:
            return None
    
    def authenticate_user(self, db: Session, email: str, password: str) -> Optional[dict]:
        """Authenticate user credentials"""
        user = self.get_user_by_email(db, email)
        if not user:
            return None
            
        if not self.verify_password(password, user.hashed_password):
            return None
            
        return {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "permissions": user.permissions,
            "is_active": user.is_active
        }
    
    def refresh_token(self, refresh_token: str) -> Optional[str]:
        """Generate new access token from refresh token"""
        payload = self.verify_token(refresh_token)
        if not payload:
            return None
            
        # Create new access token
        token_data = {
            "sub": payload["user_id"],
            "username": payload["username"],
            "email": payload.get("email"),
            "role": payload.get("role")
        }
        
        return self.create_access_token(token_data)
```

#### User Model Design
```python
# models.py - User and role models
from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Table
from sqlalchemy.orm import relationship

# Many-to-many table for user roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', String(36), ForeignKey('users.id', ondelete='CASCADE')),
    Column('role_id', String(36), ForeignKey('roles.id', ondelete='CASCADE'))
)

class User(Base):
    """User authentication and profile model"""
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    
    # Profile information
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Security fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    email_verification_token = Column(String, nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    projects = relationship("Project", back_populates="owner")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        for role in self.roles:
            if permission in role.permissions:
                return True
        return False
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role"""
        return any(role.name == role_name for role in self.roles)

class Role(Base):
    """User roles and permissions"""
    __tablename__ = "roles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    permissions = Column(JSON, default=list)  # List of permission strings
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")

class UserSession(Base):
    """User session tracking"""
    __tablename__ = "user_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token = Column(String, unique=True, nullable=False, index=True)
    refresh_token = Column(String, unique=True, nullable=True, index=True)
    
    # Session metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
```

### 2. Authorization Middleware

#### FastAPI Dependency System
```python
# auth_dependencies.py - Authentication dependencies
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

security = HTTPBearer(auto_error=False)

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[dict]:
    """Get current user if authenticated, otherwise return None"""
    
    if not credentials:
        # Return anonymous user context for development
        if settings.app_environment == "development":
            return DEFAULT_USER_CONTEXT
        return None
    
    auth_service = AuthenticationService()
    user_data = auth_service.verify_token(credentials.credentials)
    
    if not user_data:
        return None
        
    # Verify user still exists and is active
    user = db.query(User).filter(User.id == user_data["user_id"]).first()
    if not user or not user.is_active:
        return None
        
    return user_data

async def get_current_user(
    user_data: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """Get current authenticated user (required)"""
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return user_data

def require_permissions(*required_permissions: str):
    """Decorator to require specific permissions"""
    
    async def permission_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        user_permissions = current_user.get("permissions", [])
        
        missing_permissions = [
            perm for perm in required_permissions 
            if perm not in user_permissions
        ]
        
        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permissions: {', '.join(missing_permissions)}"
            )
        
        return current_user
    
    return permission_checker

def require_roles(*required_roles: str):
    """Decorator to require specific roles"""
    
    async def role_checker(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        user_role = current_user.get("role")
        
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {' or '.join(required_roles)}"
            )
        
        return current_user
    
    return role_checker
```

### 3. Protected API Endpoints

#### Secured Endpoint Examples
```python
# API endpoints with authentication
@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create new project (authentication required)"""
    
    return crud.create_project(db, project, current_user["user_id"])

@app.get("/api/admin/users", response_model=List[UserResponse])
async def get_all_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("admin", "super_admin"))
):
    """Get all users (admin only)"""
    
    return crud.get_users(db)

@app.delete("/api/projects/{project_id}")
async def delete_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permissions("project:delete"))
):
    """Delete project (delete permission required)"""
    
    # Check project ownership
    project = crud.get_project(db, project_id, current_user["user_id"])
    if not project:
        raise HTTPException(
            status_code=404,
            detail="Project not found or access denied"
        )
    
    return crud.delete_project(db, project_id, current_user["user_id"])
```

## Frontend Authentication Integration

### 1. Authentication Context

#### React Authentication Context
```typescript
// contexts/AuthContext.tsx - Authentication context
interface AuthContextValue {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: RegisterData) => Promise<void>;
  refreshToken: () => Promise<void>;
  isAuthenticated: boolean;
  isLoading: boolean;
  permissions: string[];
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
}

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('access_token')
  );
  const [isLoading, setIsLoading] = useState(true);
  
  // Initialize authentication state
  useEffect(() => {
    if (token) {
      verifyToken(token)
        .then(userData => {
          setUser(userData);
        })
        .catch(() => {
          // Token invalid, clear it
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setToken(null);
        })
        .finally(() => {
          setIsLoading(false);
        });
    } else {
      setIsLoading(false);
    }
  }, [token]);
  
  const login = useCallback(async (email: string, password: string) => {
    try {
      const response = await apiService.login({ email, password });
      const { access_token, refresh_token, user: userData } = response.data;
      
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('refresh_token', refresh_token);
      
      setToken(access_token);
      setUser(userData);
      
      // Update API service with token
      apiService.setAuthToken(access_token);
      
    } catch (error) {
      throw new Error('Invalid credentials');
    }
  }, []);
  
  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    setToken(null);
    setUser(null);
    
    // Clear API service token
    apiService.setAuthToken(null);
    
    // Redirect to login
    window.location.href = '/login';
  }, []);
  
  const register = useCallback(async (userData: RegisterData) => {
    try {
      await apiService.register(userData);
      // Registration successful, user needs to verify email
    } catch (error) {
      throw new Error('Registration failed');
    }
  }, []);
  
  const refreshToken = useCallback(async () => {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) {
      logout();
      return;
    }
    
    try {
      const response = await apiService.refreshToken(refresh);
      const { access_token } = response.data;
      
      localStorage.setItem('access_token', access_token);
      setToken(access_token);
      
      apiService.setAuthToken(access_token);
      
    } catch (error) {
      logout();
    }
  }, [logout]);
  
  const hasPermission = useCallback((permission: string) => {
    return user?.permissions?.includes(permission) || false;
  }, [user]);
  
  const hasRole = useCallback((role: string) => {
    return user?.role === role;
  }, [user]);
  
  // Auto-refresh token before expiry
  useEffect(() => {
    if (!token || !user) return;
    
    const tokenData = JSON.parse(atob(token.split('.')[1]));
    const expiresAt = tokenData.exp * 1000;
    const refreshAt = expiresAt - (5 * 60 * 1000); // 5 minutes before expiry
    
    const timeout = setTimeout(() => {
      refreshToken();
    }, refreshAt - Date.now());
    
    return () => clearTimeout(timeout);
  }, [token, user, refreshToken]);
  
  const value: AuthContextValue = {
    user,
    token,
    login,
    logout,
    register,
    refreshToken,
    isAuthenticated: !!user,
    isLoading,
    permissions: user?.permissions || [],
    hasPermission,
    hasRole
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

### 2. Protected Routes

#### Route Protection Component
```typescript
// components/ProtectedRoute.tsx - Route protection
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions?: string[];
  requiredRoles?: string[];
  fallback?: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredPermissions = [],
  requiredRoles = [],
  fallback
}) => {
  const { isAuthenticated, isLoading, user, hasPermission, hasRole } = useAuth();
  
  // Show loading while checking authentication
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // Check required permissions
  const hasRequiredPermissions = requiredPermissions.length === 0 || 
    requiredPermissions.every(permission => hasPermission(permission));
  
  // Check required roles
  const hasRequiredRoles = requiredRoles.length === 0 || 
    requiredRoles.some(role => hasRole(role));
  
  // Show fallback or error if access denied
  if (!hasRequiredPermissions || !hasRequiredRoles) {
    return fallback || (
      <div className="access-denied">
        <h2>Access Denied</h2>
        <p>You don't have permission to access this page.</p>
      </div>
    );
  }
  
  return <>{children}</>;
};

// Usage in routing
export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      
      {/* Protected routes */}
      <Route path="/projects" element={
        <ProtectedRoute>
          <ProjectsPage />
        </ProtectedRoute>
      } />
      
      <Route path="/admin" element={
        <ProtectedRoute 
          requiredRoles={['admin', 'super_admin']}
          fallback={<AdminAccessDenied />}
        >
          <AdminDashboard />
        </ProtectedRoute>
      } />
      
      <Route path="/projects/:id/delete" element={
        <ProtectedRoute requiredPermissions={['project:delete']}>
          <DeleteProjectPage />
        </ProtectedRoute>
      } />
    </Routes>
  );
};
```

## Security Considerations

### 1. Token Security

#### Secure Token Handling
```typescript
// services/tokenService.ts - Secure token management
class TokenService {
  private static readonly ACCESS_TOKEN_KEY = 'access_token';
  private static readonly REFRESH_TOKEN_KEY = 'refresh_token';
  
  static setTokens(accessToken: string, refreshToken: string) {
    // Store tokens securely
    if (this.supportsSecureStorage()) {
      // Use secure storage if available
      this.storeSecurely(this.ACCESS_TOKEN_KEY, accessToken);
      this.storeSecurely(this.REFRESH_TOKEN_KEY, refreshToken);
    } else {
      // Fallback to localStorage with encryption
      localStorage.setItem(this.ACCESS_TOKEN_KEY, this.encrypt(accessToken));
      localStorage.setItem(this.REFRESH_TOKEN_KEY, this.encrypt(refreshToken));
    }
  }
  
  static getAccessToken(): string | null {
    if (this.supportsSecureStorage()) {
      return this.retrieveSecurely(this.ACCESS_TOKEN_KEY);
    } else {
      const encrypted = localStorage.getItem(this.ACCESS_TOKEN_KEY);
      return encrypted ? this.decrypt(encrypted) : null;
    }
  }
  
  static clearTokens() {
    if (this.supportsSecureStorage()) {
      this.clearSecurely(this.ACCESS_TOKEN_KEY);
      this.clearSecurely(this.REFRESH_TOKEN_KEY);
    } else {
      localStorage.removeItem(this.ACCESS_TOKEN_KEY);
      localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    }
  }
  
  private static supportsSecureStorage(): boolean {
    // Check for secure storage capabilities
    return 'credentials' in navigator;
  }
  
  private static encrypt(data: string): string {
    // Simple encryption for fallback (in production, use proper encryption)
    return btoa(data);
  }
  
  private static decrypt(encrypted: string): string {
    try {
      return atob(encrypted);
    } catch {
      return '';
    }
  }
}
```

### 2. API Request Security

#### Automatic Token Attachment
```typescript
// Enhanced API service with authentication
class AuthenticatedApiService extends ApiService {
  constructor() {
    super();
    this.setupAuthInterceptors();
  }
  
  private setupAuthInterceptors() {
    // Request interceptor - attach auth token
    this.httpClient.interceptors.request.use(
      (config) => {
        const token = TokenService.getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );
    
    // Response interceptor - handle auth errors
    this.httpClient.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        
        // Handle token expiry
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;
          
          try {
            await this.refreshToken();
            // Retry original request with new token
            const newToken = TokenService.getAccessToken();
            if (newToken) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
            }
            return this.httpClient(originalRequest);
          } catch (refreshError) {
            // Refresh failed, logout user
            TokenService.clearTokens();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }
        
        return Promise.reject(error);
      }
    );
  }
  
  async refreshToken(): Promise<void> {
    const refreshToken = TokenService.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }
    
    const response = await this.httpClient.post('/api/auth/refresh', {
      refresh_token: refreshToken
    });
    
    const { access_token, refresh_token: newRefreshToken } = response.data;
    TokenService.setTokens(access_token, newRefreshToken);
  }
}
```

## Session Management

### 1. Session Tracking

#### Server-Side Session Management
```python
# Session management service
class SessionManagementService:
    """Manage user sessions and security"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_session(
        self, 
        user_id: str, 
        access_token: str,
        refresh_token: str,
        request: Request
    ) -> UserSession:
        """Create new user session"""
        
        # End any existing active sessions (optional - single session mode)
        self.end_user_sessions(user_id)
        
        session = UserSession(
            user_id=user_id,
            session_token=access_token,
            refresh_token=refresh_token,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        
        self.db.add(session)
        self.db.commit()
        
        return session
    
    def validate_session(self, session_token: str) -> Optional[UserSession]:
        """Validate and update session"""
        
        session = self.db.query(UserSession).filter(
            UserSession.session_token == session_token,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if session:
            # Update last activity
            session.last_activity = datetime.utcnow()
            self.db.commit()
        
        return session
    
    def end_session(self, session_token: str) -> bool:
        """End specific session"""
        
        session = self.db.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
        
        if session:
            session.is_active = False
            self.db.commit()
            return True
        
        return False
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        
        expired_count = self.db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).update({"is_active": False})
        
        self.db.commit()
        
        return expired_count
```

## Future Authentication Enhancements

### Planned Security Features

1. **Multi-Factor Authentication (MFA)**
   - TOTP (Time-based One-Time Passwords)
   - SMS verification
   - Email verification codes
   - Hardware security keys

2. **Advanced Session Management**
   - Session fingerprinting
   - Concurrent session limits
   - Geographic access controls
   - Device registration

3. **OAuth2 Integration**
   - Google OAuth2
   - GitHub OAuth2
   - Microsoft Azure AD
   - Custom OIDC providers

4. **Security Monitoring**
   - Failed login attempt tracking
   - Suspicious activity detection
   - Account lockout mechanisms
   - Security audit logging

5. **Advanced Authorization**
   - Role-based access control (RBAC)
   - Attribute-based access control (ABAC)
   - Resource-level permissions
   - Dynamic permission evaluation