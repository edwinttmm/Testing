# Security Action Items - Critical Priority
AI Model Validation Platform Security Remediation Plan

## 🔴 CRITICAL SECURITY ISSUES - IMMEDIATE ACTION REQUIRED

### 1. File Upload Security Vulnerability

**Priority**: CRITICAL  
**Impact**: High - Potential for malicious file uploads  
**Location**: `/backend/main.py` lines 485-803

#### Current Issue:
```python
# ❌ VULNERABLE: Only validates file extension
def generate_secure_filename(original_filename: str) -> tuple[str, str]:
    file_extension = original_path.suffix.lower()
    if file_extension not in ALLOWED_VIDEO_EXTENSIONS:  # Only checks extension!
        raise HTTPException(status_code=400, detail="Invalid file format")
```

#### Required Fix:
```python
# ✅ SECURE: Add MIME type and content validation
import magic

ALLOWED_MIME_TYPES = {
    'video/mp4': ['.mp4'],
    'video/avi': ['.avi'], 
    'video/quicktime': ['.mov'],
    'video/x-msvideo': ['.avi'],
    'video/x-matroska': ['.mkv']
}

def validate_file_security(file_path: str, original_filename: str) -> bool:
    """Comprehensive file security validation"""
    try:
        # 1. MIME type validation using magic numbers
        detected_mime = magic.from_file(file_path, mime=True)
        if detected_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {detected_mime}")
        
        # 2. Extension validation against MIME type
        file_extension = Path(original_filename).suffix.lower()
        if file_extension not in ALLOWED_MIME_TYPES[detected_mime]:
            raise HTTPException(status_code=400, detail="File extension doesn't match content")
        
        # 3. File size validation
        if os.path.getsize(file_path) > 100 * 1024 * 1024:  # 100MB
            raise HTTPException(status_code=413, detail="File too large")
        
        # 4. Basic malware scanning (optional - implement if needed)
        if not scan_for_malicious_content(file_path):
            raise HTTPException(status_code=400, detail="Potentially malicious file detected")
        
        return True
        
    except Exception as e:
        logger.error(f"File validation failed: {e}")
        return False

# Implementation in upload endpoints
async def upload_video_with_security(file: UploadFile, db: Session):
    # ... existing upload logic ...
    
    # ADD AFTER TEMP FILE CREATION:
    if not validate_file_security(temp_file_path, file.filename):
        os.unlink(temp_file_path)
        raise HTTPException(status_code=400, detail="File security validation failed")
    
    # Continue with existing logic...
```

**Installation Required**:
```bash
pip install python-magic
# On Ubuntu/Debian: apt-get install libmagic1
# On CentOS/RHEL: yum install file-libs
```

### 2. Authentication and Authorization Missing

**Priority**: CRITICAL  
**Impact**: High - No access control  
**Location**: Throughout `/backend/main.py`

#### Current Issue:
```python
# ❌ VULNERABLE: No authentication on any endpoint
@app.post("/api/projects")
async def create_new_project(project: ProjectCreate, db: Session = Depends(get_db)):
    return create_project(db=db, project=project, user_id="anonymous")  # Always anonymous!
```

#### Required Fix:
```python
# ✅ SECURE: Add JWT authentication middleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify JWT token and return user ID"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Apply to all protected endpoints
@app.post("/api/projects")
async def create_new_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(verify_token)  # ✅ Now requires authentication
):
    return create_project(db=db, project=project, user_id=user_id)
```

### 3. API Rate Limiting Missing

**Priority**: HIGH  
**Impact**: Medium - DoS vulnerability  
**Location**: All API endpoints

#### Required Fix:
```python
# ✅ SECURE: Add rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply rate limits to upload endpoints
@app.post("/api/videos")
@limiter.limit("5/minute")  # 5 uploads per minute per IP
async def upload_video_central(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # ... existing logic ...
```

## 🟡 HIGH PRIORITY SECURITY IMPROVEMENTS

### 4. SQL Injection Prevention Enhancement

**Priority**: HIGH  
**Current Status**: GOOD (using parameterized queries)  
**Enhancement Needed**: Add query validation

```python
# ✅ ENHANCEMENT: Add query validation middleware
@app.middleware("http")
async def sql_injection_prevention(request: Request, call_next):
    """Additional SQL injection prevention"""
    if request.method in ["POST", "PUT", "PATCH"]:
        # Validate request body for suspicious patterns
        body = await request.body()
        suspicious_patterns = [
            r"(?i)(union|select|insert|update|delete|drop|create|alter)\s+",
            r"(?i)(\bor\b|\band\b)\s+\d+\s*=\s*\d+",
            r"(?i)'|\"|;|--|\|\|"
        ]
        
        for pattern in suspicious_patterns:
            if re.search(pattern, body.decode('utf-8', errors='ignore')):
                logger.warning(f"Potential SQL injection attempt from {request.client.host}")
                raise HTTPException(status_code=400, detail="Invalid request format")
    
    response = await call_next(request)
    return response
```

### 5. Security Headers Implementation

**Priority**: HIGH  
**Impact**: Medium - Defense in depth

```python
# ✅ SECURE: Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response
```

### 6. Input Validation Enhancement

**Priority**: HIGH  
**Location**: All API endpoints

```python
# ✅ SECURE: Enhanced input validation
from pydantic import validator, Field

class SecureProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, regex=r'^[a-zA-Z0-9\s\-_]+$')
    description: str = Field(None, max_length=1000)
    
    @validator('name')
    def validate_name(cls, v):
        # Prevent XSS in project names
        if '<' in v or '>' in v or 'script' in v.lower():
            raise ValueError('Invalid characters in project name')
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        if v and len(v.strip()) == 0:
            return None
        return v.strip() if v else None
```

## 🟢 MEDIUM PRIORITY SECURITY IMPROVEMENTS

### 7. Audit Logging Enhancement

**Priority**: MEDIUM  
**Current Status**: Basic logging present

```python
# ✅ ENHANCEMENT: Comprehensive audit logging
class SecurityAuditLogger:
    def __init__(self):
        self.audit_logger = logging.getLogger("security_audit")
        
    def log_file_upload(self, user_id: str, filename: str, file_size: int, ip_address: str):
        self.audit_logger.info(
            "FILE_UPLOAD",
            extra={
                "user_id": user_id,
                "filename": filename,
                "file_size": file_size,
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def log_auth_failure(self, ip_address: str, attempted_endpoint: str):
        self.audit_logger.warning(
            "AUTH_FAILURE",
            extra={
                "ip_address": ip_address,
                "endpoint": attempted_endpoint,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

audit_logger = SecurityAuditLogger()
```

### 8. Session Management

**Priority**: MEDIUM  
**Current Status**: Missing

```python
# ✅ SECURE: Session management
from fastapi.middleware.cors import CORSMiddleware
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

class SessionManager:
    def __init__(self):
        self.session_timeout = 3600  # 1 hour
    
    async def create_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_access": datetime.utcnow().isoformat()
        }
        redis_client.setex(f"session:{session_id}", self.session_timeout, json.dumps(session_data))
        return session_id
    
    async def validate_session(self, session_id: str) -> Optional[str]:
        session_data = redis_client.get(f"session:{session_id}")
        if not session_data:
            return None
        
        data = json.loads(session_data)
        # Refresh session timeout
        redis_client.expire(f"session:{session_id}", self.session_timeout)
        return data["user_id"]
```

## Implementation Timeline

### Week 1 (CRITICAL)
- [ ] Implement file MIME type validation
- [ ] Add python-magic dependency
- [ ] Test file upload security with various file types

### Week 2 (CRITICAL)
- [ ] Implement JWT authentication system
- [ ] Add rate limiting to upload endpoints
- [ ] Test authentication flows

### Week 3 (HIGH PRIORITY)
- [ ] Add security headers middleware
- [ ] Enhance input validation
- [ ] Implement comprehensive audit logging

### Week 4 (MEDIUM PRIORITY)
- [ ] Add session management
- [ ] Implement monitoring and alerting
- [ ] Security testing and penetration testing

## Testing Requirements

### Security Tests to Add:
```python
# File upload security tests
def test_malicious_file_upload():
    """Test that malicious files are rejected"""
    # Test with renamed executables
    # Test with files containing scripts
    # Test with oversized files

def test_authentication_bypass():
    """Test that authentication cannot be bypassed"""
    # Test direct endpoint access
    # Test invalid tokens
    # Test expired tokens

def test_sql_injection_prevention():
    """Test SQL injection prevention"""
    # Test malicious input in all fields
    # Test parameterized query protection
```

## Monitoring and Alerting

### Security Metrics to Monitor:
- Failed authentication attempts per IP
- File upload failures and rejections
- Unusual API access patterns
- Large file upload attempts
- SQL injection attempt patterns

### Alerts to Configure:
- Multiple failed auth attempts from same IP
- Rejected file uploads (potential attack)
- Unusual API usage patterns
- Security middleware violations

---

**Document Owner**: Security Team  
**Last Updated**: August 22, 2025  
**Review Date**: Weekly until implementation complete  
**Status**: PENDING IMPLEMENTATION