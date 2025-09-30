# Security Remediation Implementation Plan

## Critical Priority Actions (P0) - IMMEDIATE

### 1. Emergency Authentication Implementation

**Timeline: 1-2 days**

#### Step 1: Enable Security Middleware
```python
# main.py - UNCOMMENT AND CONFIGURE
from security_middleware import setup_security_middleware, SecurityHeadersMiddleware
from logging_config import setup_logging as setup_enhanced_logging, security_logger

# Add to app initialization
setup_security_middleware(app)
app.add_middleware(SecurityHeadersMiddleware)
```

#### Step 2: Implement Basic Authentication
```python
# security/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime, timedelta

security = HTTPBearer()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        return username
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication")
```

#### Step 3: Protect All Endpoints
```python
# routers/ground_truth.py - ADD AUTHENTICATION
from security.auth import get_current_user

@router.get("/videos/available", response_model=List[VideoFile])
async def get_available_videos(
    current_user: str = Depends(get_current_user),  # ADD THIS LINE
    db: Session = Depends(get_db),
    project_id: Optional[str] = None,
    min_detections: int = 1
):
```

### 2. Secure File Upload Implementation

**Timeline: 1 day**

```python
# security/file_validator.py
import magic
from pathlib import Path

ALLOWED_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
ALLOWED_MIME_TYPES = {
    'video/mp4', 'video/avi', 'video/quicktime', 
    'video/x-msvideo', 'video/webm'
}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

def validate_video_file(file: UploadFile) -> bool:
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Invalid file type. Allowed: {ALLOWED_EXTENSIONS}")
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large. Maximum size: 500MB")
    
    # Check MIME type using python-magic
    file_magic = magic.from_buffer(file.file.read(2048), mime=True)
    file.file.seek(0)  # Reset file pointer
    
    if file_magic not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Invalid file content. Detected: {file_magic}")
    
    return True

# Implement virus scanning (optional but recommended)
def scan_for_malware(file_path: str) -> bool:
    # Integrate with ClamAV or similar
    # For now, basic file signature check
    with open(file_path, 'rb') as f:
        header = f.read(1024)
        # Check for executable headers
        if header.startswith(b'MZ') or header.startswith(b'\x7fELF'):
            raise HTTPException(400, "Executable files not allowed")
    return True
```

### 3. Path Traversal Protection

**Timeline: 1 day**

```python
# security/path_validator.py
import os
from pathlib import Path

UPLOAD_BASE_DIR = Path("/secure/uploads")
SCREENSHOT_BASE_DIR = Path("/secure/screenshots")

def validate_safe_path(file_path: str, base_dir: Path) -> Path:
    """Validate that file path is safe and within allowed directory"""
    try:
        # Resolve the path and check it's within base directory
        resolved_path = (base_dir / Path(file_path).name).resolve()
        base_resolved = base_dir.resolve()
        
        # Ensure the path is within the base directory
        if not str(resolved_path).startswith(str(base_resolved)):
            raise SecurityError("Path traversal attempt detected")
        
        return resolved_path
    except Exception as e:
        raise SecurityError(f"Invalid file path: {str(e)}")

def secure_file_save(filename: str, content: bytes, base_dir: Path) -> str:
    """Securely save file with path validation"""
    safe_path = validate_safe_path(filename, base_dir)
    
    # Create directory if it doesn't exist
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write file securely
    with open(safe_path, 'wb') as f:
        f.write(content)
    
    return str(safe_path)
```

## High Priority Actions (P1) - 1 Week

### 4. Input Validation and Sanitization

```python
# security/validators.py
from pydantic import BaseModel, validator, Field
import re

class GroundTruthQuery(BaseModel):
    project_id: Optional[str] = Field(None, max_length=36)
    min_detections: int = Field(default=1, ge=0, le=10000)
    
    @validator('project_id')
    def validate_project_id(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9-_]+$', v):
            raise ValueError('Invalid project ID format')
        return v

class VideoStatsQuery(BaseModel):
    video_id: str = Field(..., max_length=36)
    
    @validator('video_id')
    def validate_video_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9-_]+$', v):
            raise ValueError('Invalid video ID format')
        return v

# Apply to endpoints
@router.get("/videos/available")
async def get_available_videos(
    query: GroundTruthQuery = Depends(),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
```

### 5. Secure Error Handling

```python
# security/error_handler.py
import logging
from fastapi import HTTPException
from starlette.responses import JSONResponse

security_logger = logging.getLogger("security")

class SecurityError(Exception):
    pass

async def security_error_handler(request, exc):
    """Handle security-related errors safely"""
    security_logger.error(f"Security error: {str(exc)} - IP: {request.client.host}")
    
    return JSONResponse(
        status_code=403,
        content={"detail": "Access denied"}
    )

async def general_error_handler(request, exc):
    """Handle general errors without information disclosure"""
    error_id = uuid.uuid4()
    logging.error(f"Error {error_id}: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_id": str(error_id)
        }
    )

# Register handlers
app.add_exception_handler(SecurityError, security_error_handler)
app.add_exception_handler(Exception, general_error_handler)
```

### 6. SQL Injection Prevention

```python
# Update all database queries to use parameterized statements
# database/secure_queries.py

def get_videos_with_ground_truth_secure(
    db: Session, 
    project_id: Optional[str] = None,
    min_detections: int = 1,
    user_id: str = None
) -> List[Video]:
    """Secure implementation with parameterized queries"""
    
    # Base query with explicit joins
    query = db.query(Video).join(Project, Video.project_id == Project.id)
    
    # Add user authorization filter
    query = query.filter(Project.owner_id == user_id)
    
    # Add project filter using bound parameters
    if project_id:
        query = query.filter(Video.project_id == project_id)
    
    # Use subquery for detection counts to avoid injection
    gt_subquery = db.query(
        GroundTruthObject.video_id,
        func.count(GroundTruthObject.id).label('gt_count')
    ).group_by(GroundTruthObject.video_id).subquery()
    
    # Join with bound parameters
    query = query.outerjoin(gt_subquery, Video.id == gt_subquery.c.video_id)
    query = query.filter(func.coalesce(gt_subquery.c.gt_count, 0) >= min_detections)
    
    return query.all()
```

## Medium Priority Actions (P2) - 2 Weeks

### 7. Security Headers and HTTPS

```python
# middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        return response
```

### 8. Rate Limiting

```python
# middleware/rate_limiter.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import redis

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@router.get("/videos/available")
@limiter.limit("30/minute")  # 30 requests per minute
async def get_available_videos(request: Request, ...):
```

### 9. Audit Logging

```python
# security/audit_logger.py
import json
from datetime import datetime

class AuditLogger:
    def __init__(self):
        self.logger = logging.getLogger("audit")
    
    def log_access(self, user_id: str, resource: str, action: str, 
                  ip_address: str, success: bool, details: dict = None):
        audit_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "ip_address": ip_address,
            "success": success,
            "details": details or {}
        }
        
        self.logger.info(json.dumps(audit_event))
    
    def log_security_event(self, event_type: str, severity: str, 
                          details: dict, ip_address: str):
        security_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "ip_address": ip_address,
            "details": details
        }
        
        self.logger.warning(json.dumps(security_event))

# Usage in endpoints
audit_logger = AuditLogger()

@router.get("/videos/available")
async def get_available_videos(
    request: Request,
    current_user: str = Depends(get_current_user),
    ...
):
    try:
        # ... endpoint logic ...
        audit_logger.log_access(
            user_id=current_user,
            resource="ground_truth_videos",
            action="list",
            ip_address=request.client.host,
            success=True
        )
    except Exception as e:
        audit_logger.log_access(
            user_id=current_user,
            resource="ground_truth_videos", 
            action="list",
            ip_address=request.client.host,
            success=False,
            details={"error": "Access denied"}
        )
```

## Implementation Checklist

### Week 1 (Critical)
- [ ] Uncomment and configure security middleware
- [ ] Implement JWT authentication
- [ ] Add authentication dependencies to all endpoints
- [ ] Implement file upload validation
- [ ] Add path traversal protection
- [ ] Test authentication bypass scenarios

### Week 2 (High Priority)
- [ ] Add input validation to all endpoints
- [ ] Implement secure error handling
- [ ] Update database queries for SQL injection prevention
- [ ] Add parameter sanitization
- [ ] Test injection vulnerabilities

### Week 3-4 (Medium Priority)
- [ ] Configure security headers
- [ ] Implement rate limiting
- [ ] Set up audit logging
- [ ] Configure HTTPS certificates
- [ ] Implement session management
- [ ] Set up monitoring and alerting

## Testing and Validation

### Security Testing Suite
```bash
# Run security tests after each implementation
python security_audit/tests/penetration_test_suite.py
python security_audit/scans/bandit_security_scan.py

# Manual testing
curl -X GET "http://localhost:8000/api/ground-truth/videos/available" 
# Should return 401 Unauthorized

curl -X POST "http://localhost:8000/api/videos/upload" \
  -F "file=@malicious.php" 
# Should return 400 Bad Request
```

### Validation Criteria
- [ ] All endpoints require authentication
- [ ] File uploads reject non-video files
- [ ] SQL injection tests return safe errors
- [ ] Path traversal attempts are blocked
- [ ] Error messages don't expose system information
- [ ] Rate limiting prevents abuse
- [ ] Security headers are present

## Monitoring and Maintenance

### Security Monitoring
```python
# security/monitoring.py
def monitor_security_events():
    # Monitor failed authentication attempts
    # Track unusual file upload patterns  
    # Alert on SQL injection attempts
    # Monitor for path traversal attempts
    # Track rate limit violations
```

### Regular Security Tasks
- Weekly security scans
- Monthly penetration testing
- Quarterly security reviews
- Annual third-party security audit

## Emergency Response Plan

### Security Incident Response
1. **Immediate Actions**
   - Disable affected endpoints
   - Block malicious IP addresses
   - Review audit logs
   
2. **Investigation**
   - Analyze attack vectors
   - Assess data exposure
   - Document incident details
   
3. **Recovery**
   - Apply security patches
   - Update security configurations
   - Restore secure operations
   
4. **Post-Incident**
   - Conduct security review
   - Update security procedures
   - Implement additional controls

---

**CRITICAL NOTICE**: This system MUST NOT be deployed to production until AT MINIMUM the P0 critical security issues are resolved. The current state presents unacceptable security risks.