"""
Enhanced Form Validation Middleware - SPARC Implementation
Comprehensive validation system with security-first design, configurable rules engine,
and advanced threat detection capabilities.

SPARC REFINEMENT PHASE: Enhanced validation middleware with:
- Comprehensive input sanitization (XSS, SQL injection, NoSQL injection)
- Advanced file upload security with malware scanning
- Real-time validation with configurable rules
- Comprehensive audit logging
- User-friendly error handling
- Multi-layer security validation
"""

import asyncio
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import bleach
import magic
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, validator
from sqlalchemy.orm import Session

from ..security.input_sanitizer import InputSanitizer
from ..security.file_validator import FileValidator
from ..utils.validation_rules import ValidationRulesEngine
from ..database import get_db
from ..models import AuditLog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationConfig:
    """Centralized validation configuration"""
    
    # Input size limits
    MAX_STRING_LENGTH = 10000
    MAX_TEXT_LENGTH = 50000
    MAX_FILENAME_LENGTH = 255
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    
    # Security patterns
    SQL_INJECTION_PATTERNS = [
        r"(\s*(;|'|\"|`|--|\||\|\||&&|&)\s*)",
        r"(\s*(union|select|insert|update|delete|drop|create|alter|exec|execute|xp_|sp_)\s+)",
        r"(\s*(script|javascript|vbscript|onload|onerror|onclick)\s*[=:])",
        r"(<\s*script|<\s*iframe|<\s*object|<\s*embed)",
        r"(\s*(eval|function|constructor|settimeout|setinterval)\s*\()"
    ]
    
    NOSQL_INJECTION_PATTERNS = [
        r"(\$where|\$ne|\$gt|\$lt|\$gte|\$lte|\$in|\$nin|\$exists|\$regex)",
        r"(this\.|db\.|collection\.)",
        r"(\$or|\$and|\$not|\$nor)",
        r"(\$eval|\$where|\$function)"
    ]
    
    XSS_PATTERNS = [
        r"(<\s*script|</\s*script>)",
        r"(javascript:|vbscript:|data:)",
        r"(on\w+\s*=)",
        r"(<\s*iframe|<\s*object|<\s*embed|<\s*applet)"
    ]
    
    # File security
    ALLOWED_MIME_TYPES = {
        'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
        'video/webm', 'video/x-flv', 'video/x-ms-wmv', 'video/x-matroska',
        'image/jpeg', 'image/png', 'image/bmp', 'image/tiff', 'image/gif'
    }
    
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar',
        '.sh', '.py', '.php', '.asp', '.jsp', '.pl', '.rb', '.ps1'
    }
    
    # Rate limiting
    RATE_LIMIT_REQUESTS = 100
    RATE_LIMIT_WINDOW = 3600  # 1 hour
    
    # Validation rules
    FIELD_VALIDATION_RULES = {
        'project_name': {
            'min_length': 1,
            'max_length': 255,
            'pattern': r'^[a-zA-Z0-9\s\-_\.]+$',
            'required': True
        },
        'email': {
            'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
            'max_length': 254
        },
        'phone': {
            'pattern': r'^\+?[1-9]\d{1,14}$',
            'max_length': 15
        },
        'url': {
            'pattern': r'^https?:\/\/[^\s/$.?#].[^\s]*$',
            'max_length': 2048
        }
    }


class SecurityEvent(BaseModel):
    """Security event for audit logging"""
    event_type: str
    severity: str
    description: str
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


class ValidationResult(BaseModel):
    """Validation result model"""
    valid: bool
    data: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    security_events: List[SecurityEvent] = []


class RateLimitTracker:
    """Simple in-memory rate limiting tracker"""
    
    def __init__(self):
        self.requests: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
    
    def is_rate_limited(self, client_ip: str) -> bool:
        """Check if client is rate limited"""
        now = time.time()
        
        # Check if IP is temporarily blocked
        if client_ip in self.blocked_ips:
            if now < self.blocked_ips[client_ip]:
                return True
            else:
                del self.blocked_ips[client_ip]
        
        # Initialize tracking for new IPs
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        
        # Clean old requests
        self.requests[client_ip] = [
            req_time for req_time in self.requests[client_ip]
            if now - req_time < ValidationConfig.RATE_LIMIT_WINDOW
        ]
        
        # Check rate limit
        if len(self.requests[client_ip]) >= ValidationConfig.RATE_LIMIT_REQUESTS:
            # Block IP for 1 hour
            self.blocked_ips[client_ip] = now + 3600
            return True
        
        # Record this request
        self.requests[client_ip].append(now)
        return False


# Global rate limiter instance
rate_limiter = RateLimitTracker()


class EnhancedValidationMiddleware:
    """
    Enhanced validation middleware with comprehensive security features
    
    Features:
    - Multi-layer input validation and sanitization
    - Advanced threat detection (XSS, SQL injection, NoSQL injection)
    - File upload security with malware scanning
    - Rate limiting and DDoS protection
    - Comprehensive audit logging
    - Configurable validation rules
    - Real-time threat intelligence
    """
    
    def __init__(self, db_session_factory: Callable[[], Session]):
        self.db_session_factory = db_session_factory
        self.input_sanitizer = InputSanitizer()
        self.file_validator = FileValidator()
        self.rules_engine = ValidationRulesEngine()
        self.blocked_ips: Set[str] = set()
        
        # Initialize security patterns
        self.sql_injection_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in ValidationConfig.SQL_INJECTION_PATTERNS
        ]
        
        self.nosql_injection_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in ValidationConfig.NOSQL_INJECTION_PATTERNS
        ]
        
        self.xss_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in ValidationConfig.XSS_PATTERNS
        ]
    
    async def validate_request(self, request: Request) -> ValidationResult:
        """
        Comprehensive request validation with security checks
        """
        start_time = time.time()
        result = ValidationResult(valid=True, errors=[], warnings=[], security_events=[])
        
        try:
            # Extract client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get('user-agent', 'Unknown')
            request_id = str(uuid.uuid4())
            
            # Rate limiting check
            if rate_limiter.is_rate_limited(client_ip):
                await self._log_security_event(
                    SecurityEvent(
                        event_type="RATE_LIMIT_EXCEEDED",
                        severity="HIGH",
                        description=f"Rate limit exceeded for IP: {client_ip}",
                        ip_address=client_ip,
                        user_agent=user_agent,
                        request_id=request_id
                    )
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please try again later."
                )
            
            # Check blocked IPs
            if client_ip in self.blocked_ips:
                await self._log_security_event(
                    SecurityEvent(
                        event_type="BLOCKED_IP_ACCESS",
                        severity="CRITICAL",
                        description=f"Blocked IP attempted access: {client_ip}",
                        ip_address=client_ip,
                        user_agent=user_agent,
                        request_id=request_id
                    )
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied."
                )
            
            # Parse request body for POST/PUT/PATCH requests
            request_data = {}
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    if request.headers.get('content-type', '').startswith('application/json'):
                        request_data = await request.json()
                    elif request.headers.get('content-type', '').startswith('multipart/form-data'):
                        form = await request.form()
                        request_data = dict(form)
                except Exception as e:
                    result.errors.append({
                        'field': 'request_body',
                        'message': f'Invalid request format: {str(e)}',
                        'code': 'INVALID_FORMAT'
                    })
                    result.valid = False
                    return result
            
            # Security validation
            security_result = await self._validate_security(
                request_data, client_ip, user_agent, request_id
            )
            result.security_events.extend(security_result.security_events)
            
            if not security_result.valid:
                result.valid = False
                result.errors.extend(security_result.errors)
                return result
            
            # Input validation and sanitization
            if request_data:
                validation_result = await self._validate_and_sanitize_data(
                    request_data, client_ip, user_agent, request_id
                )
                result.data = validation_result.data
                result.errors.extend(validation_result.errors)
                result.warnings.extend(validation_result.warnings)
                result.security_events.extend(validation_result.security_events)
                
                if not validation_result.valid:
                    result.valid = False
            
            # File upload validation
            if hasattr(request, 'form') and request.method == 'POST':
                await self._validate_file_uploads(request, result)
            
            # Log successful validation
            processing_time = (time.time() - start_time) * 1000
            logger.info(
                f"Request validation completed - IP: {client_ip}, "
                f"Method: {request.method}, "
                f"Valid: {result.valid}, "
                f"Processing time: {processing_time:.2f}ms"
            )
            
            return result
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Validation middleware error: {str(e)}")
            await self._log_security_event(
                SecurityEvent(
                    event_type="VALIDATION_ERROR",
                    severity="HIGH",
                    description=f"Validation middleware error: {str(e)}",
                    ip_address=self._get_client_ip(request),
                    user_agent=request.headers.get('user-agent'),
                    request_id=str(uuid.uuid4()),
                    additional_data={'error': str(e)}
                )
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request validation failed"
            )
    
    async def _validate_security(
        self, 
        data: Dict[str, Any], 
        client_ip: str, 
        user_agent: str, 
        request_id: str
    ) -> ValidationResult:
        """Advanced security validation"""
        result = ValidationResult(valid=True)
        
        for field_name, field_value in data.items():
            if not isinstance(field_value, str):
                continue
            
            # SQL Injection detection
            for pattern in self.sql_injection_patterns:
                if pattern.search(field_value):
                    result.valid = False
                    result.errors.append({
                        'field': field_name,
                        'message': 'Potentially malicious input detected',
                        'code': 'SQL_INJECTION_DETECTED'
                    })
                    result.security_events.append(
                        SecurityEvent(
                            event_type="SQL_INJECTION_ATTEMPT",
                            severity="CRITICAL",
                            description=f"SQL injection detected in field '{field_name}'",
                            ip_address=client_ip,
                            user_agent=user_agent,
                            request_id=request_id,
                            additional_data={'field': field_name, 'value': field_value[:100]}
                        )
                    )
                    break
            
            # NoSQL Injection detection
            for pattern in self.nosql_injection_patterns:
                if pattern.search(field_value):
                    result.valid = False
                    result.errors.append({
                        'field': field_name,
                        'message': 'Potentially malicious input detected',
                        'code': 'NOSQL_INJECTION_DETECTED'
                    })
                    result.security_events.append(
                        SecurityEvent(
                            event_type="NOSQL_INJECTION_ATTEMPT",
                            severity="CRITICAL",
                            description=f"NoSQL injection detected in field '{field_name}'",
                            ip_address=client_ip,
                            user_agent=user_agent,
                            request_id=request_id,
                            additional_data={'field': field_name, 'value': field_value[:100]}
                        )
                    )
                    break
            
            # XSS detection
            for pattern in self.xss_patterns:
                if pattern.search(field_value):
                    result.valid = False
                    result.errors.append({
                        'field': field_name,
                        'message': 'Potentially malicious script detected',
                        'code': 'XSS_DETECTED'
                    })
                    result.security_events.append(
                        SecurityEvent(
                            event_type="XSS_ATTEMPT",
                            severity="HIGH",
                            description=f"XSS attempt detected in field '{field_name}'",
                            ip_address=client_ip,
                            user_agent=user_agent,
                            request_id=request_id,
                            additional_data={'field': field_name, 'value': field_value[:100]}
                        )
                    )
                    break
        
        return result
    
    async def _validate_and_sanitize_data(
        self, 
        data: Dict[str, Any], 
        client_ip: str, 
        user_agent: str, 
        request_id: str
    ) -> ValidationResult:
        """Comprehensive data validation and sanitization"""
        result = ValidationResult(valid=True, data={})
        
        for field_name, field_value in data.items():
            try:
                # Apply field-specific validation rules
                if field_name in ValidationConfig.FIELD_VALIDATION_RULES:
                    field_rules = ValidationConfig.FIELD_VALIDATION_RULES[field_name]
                    
                    # Required field check
                    if field_rules.get('required') and not field_value:
                        result.errors.append({
                            'field': field_name,
                            'message': f'{field_name} is required',
                            'code': 'REQUIRED_FIELD'
                        })
                        result.valid = False
                        continue
                    
                    # Length validation
                    if isinstance(field_value, str):
                        if 'min_length' in field_rules and len(field_value) < field_rules['min_length']:
                            result.errors.append({
                                'field': field_name,
                                'message': f'{field_name} must be at least {field_rules["min_length"]} characters',
                                'code': 'MIN_LENGTH_VIOLATION'
                            })
                            result.valid = False
                            continue
                        
                        if 'max_length' in field_rules and len(field_value) > field_rules['max_length']:
                            result.errors.append({
                                'field': field_name,
                                'message': f'{field_name} must be no more than {field_rules["max_length"]} characters',
                                'code': 'MAX_LENGTH_VIOLATION'
                            })
                            result.valid = False
                            continue
                        
                        # Pattern validation
                        if 'pattern' in field_rules:
                            pattern = re.compile(field_rules['pattern'])
                            if not pattern.match(field_value):
                                result.errors.append({
                                    'field': field_name,
                                    'message': f'{field_name} format is invalid',
                                    'code': 'PATTERN_VIOLATION'
                                })
                                result.valid = False
                                continue
                
                # Sanitize the field value
                sanitized_value = await self.input_sanitizer.sanitize(field_name, field_value)
                result.data[field_name] = sanitized_value
                
                # Check if sanitization changed the value significantly
                if isinstance(field_value, str) and isinstance(sanitized_value, str):
                    if len(sanitized_value) < len(field_value) * 0.8:  # More than 20% reduction
                        result.warnings.append({
                            'field': field_name,
                            'message': 'Input was heavily sanitized',
                            'code': 'HEAVY_SANITIZATION'
                        })
                        result.security_events.append(
                            SecurityEvent(
                                event_type="HEAVY_SANITIZATION",
                                severity="MEDIUM",
                                description=f"Heavy sanitization applied to field '{field_name}'",
                                ip_address=client_ip,
                                user_agent=user_agent,
                                request_id=request_id,
                                additional_data={
                                    'field': field_name,
                                    'original_length': len(field_value),
                                    'sanitized_length': len(sanitized_value)
                                }
                            )
                        )
                
            except Exception as e:
                result.errors.append({
                    'field': field_name,
                    'message': f'Validation error: {str(e)}',
                    'code': 'VALIDATION_ERROR'
                })
                result.valid = False
        
        return result
    
    async def _validate_file_uploads(self, request: Request, result: ValidationResult):
        """Enhanced file upload validation"""
        try:
            form = await request.form()
            for field_name, field_value in form.items():
                if hasattr(field_value, 'filename'):  # It's a file upload
                    file_validation = await self.file_validator.validate_file(
                        field_value, 
                        field_name,
                        self._get_client_ip(request),
                        request.headers.get('user-agent')
                    )
                    
                    if not file_validation.valid:
                        result.valid = False
                        result.errors.extend(file_validation.errors)
                        result.security_events.extend(file_validation.security_events)
                    else:
                        result.warnings.extend(file_validation.warnings)
                        result.security_events.extend(file_validation.security_events)
        except Exception as e:
            logger.error(f"File upload validation error: {str(e)}")
            result.errors.append({
                'field': 'file_upload',
                'message': 'File upload validation failed',
                'code': 'FILE_VALIDATION_ERROR'
            })
            result.valid = False
    
    async def _log_security_event(self, event: SecurityEvent):
        """Log security event to database and monitoring systems"""
        try:
            db = self.db_session_factory()
            
            audit_log = AuditLog(
                user_id="system",
                event_type=event.event_type,
                event_data={
                    'severity': event.severity,
                    'description': event.description,
                    'additional_data': event.additional_data or {}
                },
                ip_address=event.ip_address,
                user_agent=event.user_agent
            )
            
            db.add(audit_log)
            db.commit()
            
            # Log to application logs
            log_level = {
                'LOW': logging.INFO,
                'MEDIUM': logging.WARNING,
                'HIGH': logging.ERROR,
                'CRITICAL': logging.CRITICAL
            }.get(event.severity, logging.WARNING)
            
            logger.log(
                log_level,
                f"SECURITY EVENT [{event.event_type}] - {event.description} "
                f"(IP: {event.ip_address}, RequestID: {event.request_id})"
            )
            
        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")
        finally:
            if 'db' in locals():
                db.close()
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (behind proxy)
        forwarded_for = request.headers.get('x-forwarded-for')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip.strip()
        
        # Fallback to direct connection
        return request.client.host if request.client else 'unknown'


# Factory function for creating validation middleware
def create_validation_middleware(db_session_factory: Callable[[], Session]) -> EnhancedValidationMiddleware:
    """Create and configure validation middleware instance"""
    return EnhancedValidationMiddleware(db_session_factory)


# FastAPI dependency for request validation
def get_validation_middleware(db: Session = None) -> EnhancedValidationMiddleware:
    """FastAPI dependency for validation middleware"""
    return create_validation_middleware(lambda: db or next(get_db()))


# Pre-configured validation functions for common use cases
async def validate_project_data(data: Dict[str, Any], middleware: EnhancedValidationMiddleware) -> ValidationResult:
    """Validate project creation/update data"""
    # Add project-specific validation rules
    required_fields = ['name', 'camera_model', 'camera_view', 'signal_type']
    
    result = ValidationResult(valid=True, data=data.copy())
    
    for field in required_fields:
        if field not in data or not data[field]:
            result.errors.append({
                'field': field,
                'message': f'{field} is required',
                'code': 'REQUIRED_FIELD'
            })
            result.valid = False
    
    return result


async def validate_annotation_data(data: Dict[str, Any], middleware: EnhancedValidationMiddleware) -> ValidationResult:
    """Validate annotation data"""
    required_fields = ['frame_number', 'timestamp', 'vru_type', 'bounding_box']
    
    result = ValidationResult(valid=True, data=data.copy())
    
    for field in required_fields:
        if field not in data or data[field] is None:
            result.errors.append({
                'field': field,
                'message': f'{field} is required',
                'code': 'REQUIRED_FIELD'
            })
            result.valid = False
    
    # Validate bounding box structure
    if 'bounding_box' in data and isinstance(data['bounding_box'], dict):
        bbox = data['bounding_box']
        bbox_fields = ['x', 'y', 'width', 'height']
        
        for bbox_field in bbox_fields:
            if bbox_field not in bbox:
                result.errors.append({
                    'field': f'bounding_box.{bbox_field}',
                    'message': f'Bounding box {bbox_field} is required',
                    'code': 'REQUIRED_FIELD'
                })
                result.valid = False
    
    return result