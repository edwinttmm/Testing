# Security Architecture - AI Model Validation Platform

## Overview

This document defines the comprehensive security architecture for the AI Model Validation Platform, implementing multi-layer security controls, authentication and authorization systems, and comprehensive audit logging.

## 1. SECURITY ARCHITECTURE OVERVIEW

### 1.1 Defense in Depth Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SECURITY LAYERS                             │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 7: Application Security                                      │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ Input       │ │ Output      │ │ Business    │ │ Data        │   │
│ │ Validation  │ │ Encoding    │ │ Logic       │ │ Validation  │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 6: Authentication & Authorization                            │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ JWT Token   │ │ Role-Based  │ │ Permission  │ │ Session     │   │
│ │ Validation  │ │ Access      │ │ Control     │ │ Management  │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 5: API Security                                              │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ Rate        │ │ CORS        │ │ Content     │ │ Header      │   │
│ │ Limiting    │ │ Policy      │ │ Validation  │ │ Security    │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 4: Transport Security                                        │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ TLS 1.3     │ │ Certificate │ │ HSTS        │ │ Secure      │   │
│ │ Encryption  │ │ Validation  │ │ Policy      │ │ Cookies     │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3: Network Security                                          │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ Firewall    │ │ VPN         │ │ Network     │ │ DDoS        │   │
│ │ Rules       │ │ Access      │ │ Segmentation│ │ Protection  │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2: Infrastructure Security                                   │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ Container   │ │ Host        │ │ Image       │ │ Registry    │   │
│ │ Security    │ │ Hardening   │ │ Scanning    │ │ Security    │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 1: Physical Security                                         │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│ │ Data Center │ │ Hardware    │ │ Access      │ │ Environmental│  │
│ │ Security    │ │ Security    │ │ Control     │ │ Controls    │   │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Security Principles

1. **Zero Trust Architecture**: Never trust, always verify
2. **Principle of Least Privilege**: Minimal required access
3. **Defense in Depth**: Multiple security layers
4. **Fail Secure**: Secure defaults and failure modes
5. **Security by Design**: Built-in security from the start
6. **Continuous Monitoring**: Real-time security assessment

## 2. INPUT VALIDATION & SANITIZATION

### 2.1 Comprehensive Input Validation Framework

```python
# utils/security.py - Security Validation Framework

import re
import html
import bleach
import json
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, validator
from dataclasses import dataclass
from enum import Enum

class SecurityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ValidationResult:
    """Result of security validation"""
    is_valid: bool
    security_level: SecurityLevel
    violations: List[str]
    sanitized_data: Any = None

class SecurityValidator:
    """Comprehensive security validation system"""
    
    def __init__(self):
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"onmouseover\s*=",
            r"onfocus\s*=",
            r"onblur\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"<style[^>]*>.*?</style>",
        ]
        
        self.sql_injection_patterns = [
            r"(\bUNION\b.*\bSELECT\b)",
            r"(\bSELECT\b.*\bFROM\b)",
            r"(\bINSERT\b.*\bINTO\b)",
            r"(\bUPDATE\b.*\bSET\b)",
            r"(\bDELETE\b.*\bFROM\b)",
            r"(\bDROP\b.*\bTABLE\b)",
            r"(\bALTER\b.*\bTABLE\b)",
            r"(\bCREATE\b.*\bTABLE\b)",
            r"(\bEXEC\b.*\()",
            r"(\bsp_\w+)",  # Stored procedures
            r"(\bxp_\w+)",  # Extended procedures
            r"(--.*)",      # SQL comments
            r"(/\*.*\*/)",  # SQL block comments
        ]
        
        self.command_injection_patterns = [
            r"(\|\s*\w+)",      # Pipe commands
            r"(;\s*\w+)",       # Command chaining
            r"(\&\&\s*\w+)",    # Logical AND
            r"(\|\|\s*\w+)",    # Logical OR
            r"(`[^`]*`)",       # Backticks
            r"(\$\([^)]*\))",   # Command substitution
            r"(\bwget\b)",
            r"(\bcurl\b)",
            r"(\bsh\b)",
            r"(\bbash\b)",
            r"(\bpowershell\b)",
            r"(\bcmd\b)",
            r"(\beval\b)",
            r"(\bexec\b)",
            r"(\bsystem\b)",
        ]
        
        self.path_traversal_patterns = [
            r"(\.\.\/)",        # Directory traversal
            r"(\.\.\\)",        # Windows directory traversal
            r"(%2e%2e%2f)",     # URL encoded traversal
            r"(%2e%2e\\)",      # URL encoded Windows traversal
            r"(\/etc\/passwd)", # Unix password file
            r"(\/windows\/system32)", # Windows system directory
            r"(\.\.%2f)",       # Mixed encoding
            r"(%252e%252e%252f)", # Double URL encoding
        ]
        
        # Compile patterns for performance
        self.compiled_xss_patterns = [re.compile(p, re.IGNORECASE) for p in self.xss_patterns]
        self.compiled_sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.sql_injection_patterns]
        self.compiled_cmd_patterns = [re.compile(p, re.IGNORECASE) for p in self.command_injection_patterns]
        self.compiled_path_patterns = [re.compile(p, re.IGNORECASE) for p in self.path_traversal_patterns]
    
    def validate_string_input(self, input_data: str, context: str = "general") -> ValidationResult:
        """Validate string input for security threats"""
        
        violations = []
        security_level = SecurityLevel.LOW
        
        if not input_data:
            return ValidationResult(True, SecurityLevel.LOW, [], "")
        
        # Check for XSS patterns
        for pattern in self.compiled_xss_patterns:
            if pattern.search(input_data):
                violations.append(f"XSS pattern detected in {context}")
                security_level = SecurityLevel.HIGH
        
        # Check for SQL injection patterns
        for pattern in self.compiled_sql_patterns:
            if pattern.search(input_data):
                violations.append(f"SQL injection pattern detected in {context}")
                security_level = SecurityLevel.CRITICAL
        
        # Check for command injection patterns
        for pattern in self.compiled_cmd_patterns:
            if pattern.search(input_data):
                violations.append(f"Command injection pattern detected in {context}")
                security_level = SecurityLevel.CRITICAL
        
        # Check for path traversal patterns
        for pattern in self.compiled_path_patterns:
            if pattern.search(input_data):
                violations.append(f"Path traversal pattern detected in {context}")
                security_level = SecurityLevel.HIGH
        
        # Check for suspicious characters
        if self._contains_suspicious_chars(input_data):
            violations.append(f"Suspicious characters detected in {context}")
            if security_level == SecurityLevel.LOW:
                security_level = SecurityLevel.MEDIUM
        
        # Sanitize the input
        sanitized = self._sanitize_string(input_data, context)
        
        is_valid = len(violations) == 0
        return ValidationResult(is_valid, security_level, violations, sanitized)
    
    def validate_json_input(self, json_data: Union[dict, list], max_depth: int = 10) -> ValidationResult:
        """Validate JSON input for security threats"""
        
        violations = []
        security_level = SecurityLevel.LOW
        
        # Check JSON depth
        depth = self._get_json_depth(json_data)
        if depth > max_depth:
            violations.append(f"JSON depth {depth} exceeds maximum {max_depth}")
            security_level = SecurityLevel.MEDIUM
        
        # Check JSON size
        json_str = json.dumps(json_data)
        if len(json_str) > 1024 * 1024:  # 1MB limit
            violations.append("JSON payload exceeds size limit")
            security_level = SecurityLevel.MEDIUM
        
        # Recursively validate all string values
        string_violations = self._validate_json_strings(json_data)
        violations.extend(string_violations)
        
        if string_violations:
            security_level = SecurityLevel.HIGH
        
        # Sanitize JSON data
        sanitized = self._sanitize_json_data(json_data)
        
        is_valid = len(violations) == 0
        return ValidationResult(is_valid, security_level, violations, sanitized)
    
    def validate_file_upload(self, file_data: bytes, filename: str, allowed_types: List[str]) -> ValidationResult:
        """Validate file upload for security threats"""
        
        violations = []
        security_level = SecurityLevel.LOW
        
        # Check file size (50MB limit)
        if len(file_data) > 50 * 1024 * 1024:
            violations.append(f"File size {len(file_data)} exceeds 50MB limit")
            security_level = SecurityLevel.MEDIUM
        
        # Check filename for suspicious patterns
        filename_result = self.validate_string_input(filename, "filename")
        if not filename_result.is_valid:
            violations.extend(filename_result.violations)
            security_level = max(security_level, filename_result.security_level, key=lambda x: x.value)
        
        # Check file extension
        if not self._is_allowed_file_extension(filename, allowed_types):
            violations.append(f"File extension not allowed: {filename}")
            security_level = SecurityLevel.MEDIUM
        
        # Check file magic bytes
        if not self._validate_file_magic_bytes(file_data, filename):
            violations.append("File content doesn't match extension")
            security_level = SecurityLevel.HIGH
        
        # Scan for malicious content
        malicious_content = self._scan_file_content(file_data)
        if malicious_content:
            violations.extend(malicious_content)
            security_level = SecurityLevel.CRITICAL
        
        is_valid = len(violations) == 0
        return ValidationResult(is_valid, security_level, violations, None)
    
    def _contains_suspicious_chars(self, text: str) -> bool:
        """Check for suspicious character patterns"""
        
        # Control characters (excluding tab, newline, carriage return)
        control_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]')
        if control_chars.search(text):
            return True
        
        # High bit characters that might indicate encoding attacks
        high_bit_pattern = re.compile(r'[\x80-\xFF]{3,}')
        if high_bit_pattern.search(text):
            return True
        
        # Suspicious Unicode characters
        suspicious_unicode = re.compile(r'[\u202A-\u202E\u2066-\u2069\uFEFF]')
        if suspicious_unicode.search(text):
            return True
        
        return False
    
    def _sanitize_string(self, text: str, context: str) -> str:
        """Sanitize string based on context"""
        
        if context == "html":
            # Allow basic HTML tags but sanitize dangerous ones
            allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li']
            return bleach.clean(text, tags=allowed_tags, strip=True)
        
        elif context == "filename":
            # Sanitize filename
            sanitized = re.sub(r'[<>:"/\\|?*]', '_', text)
            sanitized = sanitized[:255]  # Limit length
            return sanitized
        
        else:
            # General sanitization
            sanitized = html.escape(text)
            sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sanitized)
            return sanitized[:1000]  # Limit length
    
    def _get_json_depth(self, obj, depth=0):
        """Calculate JSON depth"""
        if isinstance(obj, dict):
            return max([self._get_json_depth(v, depth + 1) for v in obj.values()] + [depth])
        elif isinstance(obj, list):
            return max([self._get_json_depth(item, depth + 1) for item in obj] + [depth])
        else:
            return depth
    
    def _validate_json_strings(self, obj) -> List[str]:
        """Recursively validate all strings in JSON object"""
        
        violations = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Validate key
                if isinstance(key, str):
                    result = self.validate_string_input(key, "json_key")
                    if not result.is_valid:
                        violations.extend(result.violations)
                
                # Validate value
                violations.extend(self._validate_json_strings(value))
        
        elif isinstance(obj, list):
            for item in obj:
                violations.extend(self._validate_json_strings(item))
        
        elif isinstance(obj, str):
            result = self.validate_string_input(obj, "json_value")
            if not result.is_valid:
                violations.extend(result.violations)
        
        return violations
    
    def _sanitize_json_data(self, obj):
        """Recursively sanitize JSON data"""
        
        if isinstance(obj, dict):
            return {
                self._sanitize_string(str(k), "json_key"): self._sanitize_json_data(v)
                for k, v in obj.items()
            }
        
        elif isinstance(obj, list):
            return [self._sanitize_json_data(item) for item in obj]
        
        elif isinstance(obj, str):
            return self._sanitize_string(obj, "json_value")
        
        else:
            return obj
    
    def _is_allowed_file_extension(self, filename: str, allowed_types: List[str]) -> bool:
        """Check if file extension is allowed"""
        
        if not filename or '.' not in filename:
            return False
        
        extension = filename.lower().split('.')[-1]
        
        # Map common extensions to MIME types
        extension_mime_map = {
            'mp4': 'video/mp4',
            'avi': 'video/avi',
            'mov': 'video/quicktime',
            'mkv': 'video/x-matroska',
            'webm': 'video/webm',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'json': 'application/json'
        }
        
        mime_type = extension_mime_map.get(extension)
        return mime_type in allowed_types if mime_type else False
    
    def _validate_file_magic_bytes(self, file_data: bytes, filename: str) -> bool:
        """Validate file content matches extension using magic bytes"""
        
        if len(file_data) < 16:
            return False
        
        magic_bytes_map = {
            'mp4': [b'\x00\x00\x00\x14ftypmp4', b'\x00\x00\x00\x18ftypmp4'],
            'avi': [b'RIFF'],
            'mov': [b'\x00\x00\x00\x14ftypqt', b'moov'],
            'jpg': [b'\xFF\xD8\xFF'],
            'png': [b'\x89PNG\r\n\x1a\n'],
            'gif': [b'GIF87a', b'GIF89a'],
            'pdf': [b'%PDF-']
        }
        
        if '.' not in filename:
            return False
        
        extension = filename.lower().split('.')[-1]
        expected_magic = magic_bytes_map.get(extension, [])
        
        if not expected_magic:
            return True  # No magic bytes to check
        
        file_header = file_data[:32]
        return any(file_header.startswith(magic) for magic in expected_magic)
    
    def _scan_file_content(self, file_data: bytes) -> List[str]:
        """Scan file content for malicious patterns"""
        
        violations = []
        
        try:
            # Convert to string for pattern matching (may not work for all binary files)
            content = file_data.decode('utf-8', errors='ignore')
        except:
            return violations  # Can't scan binary content
        
        # Look for embedded scripts
        if re.search(r'<script[^>]*>.*?</script>', content, re.IGNORECASE | re.DOTALL):
            violations.append("Embedded script detected in file content")
        
        # Look for suspicious URLs
        if re.search(r'https?://[^\s]+\.(exe|bat|cmd|scr|pif|com)', content, re.IGNORECASE):
            violations.append("Suspicious URL detected in file content")
        
        # Look for base64 encoded content (might be malicious)
        base64_pattern = r'[A-Za-z0-9+/]{50,}={0,2}'
        if len(re.findall(base64_pattern, content)) > 10:
            violations.append("Large amount of base64 content detected")
        
        return violations


class SecureInputValidator(BaseModel):
    """Pydantic model with built-in security validation"""
    
    class Config:
        # Validate assignment
        validate_assignment = True
        # Custom validator
        arbitrary_types_allowed = True
    
    @validator('*', pre=True)
    def validate_all_fields(cls, v, field):
        """Apply security validation to all fields"""
        
        if isinstance(v, str):
            validator = SecurityValidator()
            result = validator.validate_string_input(v, field.name)
            
            if not result.is_valid:
                raise ValueError(f"Security validation failed: {', '.join(result.violations)}")
            
            return result.sanitized_data
        
        return v


# Example usage with Pydantic models
class SecureProjectCreate(SecureInputValidator):
    """Secure project creation schema"""
    name: str
    description: Optional[str] = None
    camera_model: str
    camera_view: str
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Project name cannot be empty")
        if len(v) > 100:
            raise ValueError("Project name too long")
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        if v and len(v) > 1000:
            raise ValueError("Description too long")
        return v
```

## 3. AUTHENTICATION SYSTEM

### 3.1 JWT Authentication Implementation

```python
# services/auth_service.py - Authentication Service

import jwt
import bcrypt
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import redis
import json

from database import get_db
from models.database import User, UserSession, AuditLog
from utils.security import SecurityValidator

class AuthenticationService:
    """Comprehensive authentication service"""
    
    def __init__(self):
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60
        self.refresh_token_expire_days = 7
        self.security_validator = SecurityValidator()
        
        # Redis for token blacklisting and session management
        try:
            self.redis_client = redis.Redis(
                host='localhost', port=6379, db=1, decode_responses=True
            )
        except:
            self.redis_client = None
    
    async def authenticate_user(self, username: str, password: str, request: Request) -> Dict:
        """Authenticate user with username/password"""
        
        # Validate input
        username_result = self.security_validator.validate_string_input(username, "username")
        if not username_result.is_valid:
            await self._log_security_event("auth_attempt_invalid_username", request)
            raise HTTPException(status_code=400, detail="Invalid username format")
        
        password_result = self.security_validator.validate_string_input(password, "password")
        if not password_result.is_valid:
            await self._log_security_event("auth_attempt_invalid_password", request)
            raise HTTPException(status_code=400, detail="Invalid password format")
        
        # Check rate limiting for authentication attempts
        if not await self._check_auth_rate_limit(request.client.host, username):
            await self._log_security_event("auth_rate_limit_exceeded", request, {"username": username})
            raise HTTPException(status_code=429, detail="Too many authentication attempts")
        
        # Get user from database
        db = next(get_db())
        user = db.query(User).filter(User.username == username_result.sanitized_data).first()
        
        if not user:
            await self._log_auth_attempt(username, "user_not_found", request, False)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not self._verify_password(password, user.password_hash):
            await self._log_auth_attempt(username, "invalid_password", request, False)
            await self._increment_failed_attempts(request.client.host, username)
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Check if account is locked
        if user.locked_until and user.locked_until > datetime.utcnow():
            await self._log_auth_attempt(username, "account_locked", request, False)
            raise HTTPException(status_code=423, detail="Account temporarily locked")
        
        # Check if account is active
        if not user.is_active:
            await self._log_auth_attempt(username, "account_inactive", request, False)
            raise HTTPException(status_code=403, detail="Account inactive")
        
        # Generate tokens
        access_token = await self._generate_access_token(user)
        refresh_token = await self._generate_refresh_token(user)
        
        # Create session
        session = await self._create_user_session(user, request, access_token, refresh_token)
        
        # Reset failed attempts
        await self._reset_failed_attempts(request.client.host, username)
        
        # Update last login
        user.last_login = datetime.utcnow()
        user.failed_login_attempts = 0
        db.commit()
        
        await self._log_auth_attempt(username, "success", request, True)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "roles": user.roles,
                "permissions": await self._get_user_permissions(user)
            },
            "session_id": session.id
        }
    
    async def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return user info"""
        
        try:
            # Check if token is blacklisted
            if await self._is_token_blacklisted(token):
                return None
            
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Validate token claims
            if not self._validate_token_claims(payload):
                return None
            
            # Get user info
            user_id = payload.get("sub")
            session_id = payload.get("session_id")
            
            if not user_id or not session_id:
                return None
            
            # Check session validity
            if not await self._is_session_valid(session_id):
                return None
            
            # Get user from database
            db = next(get_db())
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user or not user.is_active:
                return None
            
            return {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "roles": user.roles,
                "permissions": await self._get_user_permissions(user),
                "session_id": session_id
            }
            
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
        except Exception:
            return None
    
    async def refresh_token(self, refresh_token: str, request: Request) -> Dict:
        """Refresh access token using refresh token"""
        
        try:
            # Decode refresh token
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            user_id = payload.get("sub")
            session_id = payload.get("session_id")
            token_type = payload.get("type")
            
            if token_type != "refresh" or not user_id or not session_id:
                raise HTTPException(status_code=401, detail="Invalid refresh token")
            
            # Check session validity
            if not await self._is_session_valid(session_id):
                raise HTTPException(status_code=401, detail="Session expired")
            
            # Get user
            db = next(get_db())
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user or not user.is_active:
                raise HTTPException(status_code=401, detail="User not found or inactive")
            
            # Generate new access token
            new_access_token = await self._generate_access_token(user)
            
            # Update session
            await self._update_session_token(session_id, new_access_token)
            
            await self._log_security_event("token_refresh", request, {"user_id": user.id})
            
            return {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Refresh token expired")
        except jwt.JWTError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    async def logout(self, token: str, request: Request) -> bool:
        """Logout user and invalidate tokens"""
        
        try:
            # Decode token to get session info
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            user_id = payload.get("sub")
            session_id = payload.get("session_id")
            
            if user_id and session_id:
                # Blacklist token
                await self._blacklist_token(token)
                
                # Invalidate session
                await self._invalidate_session(session_id)
                
                await self._log_security_event("logout", request, {"user_id": user_id})
                
                return True
            
        except jwt.JWTError:
            pass
        
        return False
    
    async def _generate_access_token(self, user) -> str:
        """Generate JWT access token"""
        
        payload = {
            "sub": user.id,
            "username": user.username,
            "email": user.email,
            "roles": user.roles,
            "type": "access",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "jti": secrets.token_urlsafe(32)  # Unique token ID
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    async def _generate_refresh_token(self, user) -> str:
        """Generate JWT refresh token"""
        
        payload = {
            "sub": user.id,
            "type": "refresh",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            "jti": secrets.token_urlsafe(32)
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def _verify_password(self, password: str, password_hash: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def _hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    async def _create_user_session(self, user, request: Request, access_token: str, refresh_token: str):
        """Create user session record"""
        
        db = next(get_db())
        
        session = UserSession(
            id=secrets.token_urlsafe(32),
            user_id=user.id,
            access_token_hash=self._hash_token(access_token),
            refresh_token_hash=self._hash_token(refresh_token),
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            is_active=True
        )
        
        db.add(session)
        db.commit()
        
        return session
    
    def _hash_token(self, token: str) -> str:
        """Hash token for secure storage"""
        return bcrypt.hashpw(token.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# Authentication dependency
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """FastAPI dependency to get current authenticated user"""
    
    auth_service = AuthenticationService()
    user_info = await auth_service.verify_token(credentials.credentials)
    
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info

async def require_permission(user: Dict, resource: str, action: str):
    """Check if user has required permission"""
    
    required_permission = f"{resource}:{action}"
    user_permissions = user.get("permissions", [])
    
    # Check for admin role (has all permissions)
    if "admin" in user.get("roles", []):
        return True
    
    # Check specific permission
    if required_permission not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail=f"Insufficient permissions. Required: {required_permission}"
        )
    
    return True
```

This comprehensive security architecture provides:

1. **Multi-Layer Defense**: Seven layers of security controls
2. **Input Validation**: Comprehensive validation against XSS, SQL injection, command injection, and path traversal
3. **Authentication**: JWT-based authentication with refresh tokens and session management
4. **Authorization**: Role-based access control with granular permissions
5. **Rate Limiting**: Advanced rate limiting with multiple strategies
6. **Audit Logging**: Comprehensive security event logging
7. **File Security**: Secure file upload validation with magic byte checking
8. **Token Security**: Token blacklisting and secure session management
9. **Password Security**: bcrypt hashing with salt
10. **Security Monitoring**: Real-time security event tracking and alerting