# SPARC Specification: Form Validation System

## 1. System Overview

### 1.1 Purpose
The Form Validation System provides comprehensive input sanitization, validation rules, error handling, and security controls for all user inputs across the AI model validation platform. It serves as the first line of defense against malicious inputs and ensures data integrity throughout the system.

### 1.2 Scope
- Client-side and server-side validation
- Input sanitization and XSS prevention
- SQL injection prevention
- File upload security
- API parameter validation
- Real-time validation feedback
- Custom validation rules
- Error handling and user feedback

### 1.3 Key Components
- Validation rule engine
- Input sanitization middleware
- Error handling framework
- Security validation layer
- File upload validator
- Real-time validation UI
- Custom validator registry
- Audit and logging system

## 2. Functional Requirements

### 2.1 Input Validation

#### FR-FV-2.1.1 Data Type Validation
- **Description**: System shall validate all inputs against expected data types
- **Priority**: High
- **Acceptance Criteria**:
  - String inputs validated for length, format, and character sets
  - Numeric inputs validated for range, precision, and type
  - Boolean inputs validated for proper true/false values
  - Date/time inputs validated for format and logical ranges
  - UUID inputs validated for proper format
  - Email addresses validated against RFC 5322 standards
- **Validation Rules**:
  - Strings: Min/max length, regex patterns, allowed characters
  - Numbers: Min/max values, decimal places, integer/float distinction
  - Dates: Format validation, logical date ranges, timezone handling

#### FR-FV-2.1.2 Business Logic Validation
- **Description**: System shall enforce business rules through validation
- **Priority**: High
- **Acceptance Criteria**:
  - Project names must be unique within user scope
  - Video files must meet format and size requirements
  - Bounding box coordinates must be within frame boundaries
  - Confidence scores must be between 0 and 1
  - Frame numbers must be valid for video duration
  - Timestamps must be within video timeline
- **Business Rules Implementation**:
  - Cross-field validation (end date after start date)
  - Conditional validation (required fields based on other inputs)
  - Dependency validation (related entity existence)

#### FR-FV-2.1.3 Format Validation
- **Description**: System shall validate input formats against predefined patterns
- **Priority**: High
- **Acceptance Criteria**:
  - Email format validation with proper domain checking
  - Phone number format validation with international support
  - URL format validation with protocol verification
  - File name validation with extension checking
  - JSON structure validation for complex inputs
  - Camera model format validation
- **Format Standards**:
  - ISO 8601 for date/time formats
  - RFC 3986 for URL validation
  - MIME types for file format validation

### 2.2 Input Sanitization

#### FR-FV-2.2.1 XSS Prevention
- **Description**: System shall prevent Cross-Site Scripting attacks
- **Priority**: Critical
- **Acceptance Criteria**:
  - HTML encoding of all user-provided text
  - Script tag stripping from text inputs
  - Event handler removal from HTML content
  - CSS expression filtering
  - URL sanitization to prevent javascript: protocols
  - Content Security Policy enforcement
- **Sanitization Techniques**:
  - HTML entity encoding for output
  - Whitelist-based HTML filtering
  - JavaScript context-aware encoding
  - Attribute value sanitization

#### FR-FV-2.2.2 SQL Injection Prevention
- **Description**: System shall prevent SQL injection attacks
- **Priority**: Critical
- **Acceptance Criteria**:
  - Parameterized queries for all database operations
  - Input validation before SQL operations
  - SQL keyword filtering in text inputs
  - Dynamic query sanitization
  - Stored procedure usage where appropriate
  - Database user privilege restrictions
- **Prevention Methods**:
  - SQLAlchemy ORM with parameterized queries
  - Input escaping for dynamic queries
  - SQL injection pattern detection
  - Query complexity limits

#### FR-FV-2.2.3 Path Traversal Prevention
- **Description**: System shall prevent path traversal attacks
- **Priority**: High
- **Acceptance Criteria**:
  - File path validation and normalization
  - Restricted directory access
  - Filename sanitization
  - Symbolic link detection and blocking
  - Absolute path validation
  - Upload directory restrictions
- **Security Measures**:
  - Whitelist-based path validation
  - Canonical path resolution
  - Chroot jail for file operations

### 2.3 File Upload Validation

#### FR-FV-2.3.1 File Type Validation
- **Description**: System shall validate uploaded file types and content
- **Priority**: High
- **Acceptance Criteria**:
  - MIME type validation against allowed types
  - File extension verification
  - Magic number (file signature) checking
  - Content scanning for embedded threats
  - File size limits enforcement
  - Video format validation (MP4, AVI, MOV)
- **Allowed File Types**:
  - Videos: MP4, AVI, MOV, WMV (max 2GB)
  - Images: JPG, PNG, GIF, BMP (max 50MB)
  - Documents: PDF, TXT, JSON (max 10MB)

#### FR-FV-2.3.2 Virus and Malware Scanning
- **Description**: System shall scan uploaded files for malicious content
- **Priority**: High
- **Acceptance Criteria**:
  - Integration with antivirus scanning engines
  - Quarantine system for suspicious files
  - Real-time scanning during upload
  - Periodic rescanning of stored files
  - Threat signature updates
  - Automated response to threats
- **Scanning Capabilities**:
  - Known malware signature detection
  - Heuristic analysis for unknown threats
  - Behavioral analysis for suspicious files

#### FR-FV-2.3.3 File Content Validation
- **Description**: System shall validate file content integrity and structure
- **Priority**: Medium
- **Acceptance Criteria**:
  - Video file structure validation
  - Metadata extraction and validation
  - Codec compatibility checking
  - Frame rate and resolution validation
  - Duration validation
  - Corruption detection
- **Validation Checks**:
  - Container format validation
  - Stream integrity verification
  - Metadata consistency checking

### 2.4 Real-time Validation

#### FR-FV-2.4.1 Client-side Validation
- **Description**: System shall provide immediate validation feedback
- **Priority**: Medium
- **Acceptance Criteria**:
  - Real-time validation as user types
  - Immediate error message display
  - Field highlighting for errors
  - Progress indicators for validation
  - Async validation for server-side checks
  - Debounced validation to prevent excessive requests
- **User Experience**:
  - Non-blocking validation messages
  - Clear error descriptions
  - Suggested corrections
  - Visual feedback (colors, icons)

#### FR-FV-2.4.2 Server-side Validation
- **Description**: System shall perform comprehensive server-side validation
- **Priority**: High
- **Acceptance Criteria**:
  - All client-side validation replicated on server
  - Database constraint validation
  - Business rule enforcement
  - Security validation layers
  - Error logging and monitoring
  - Rate limiting for validation requests
- **Validation Layers**:
  - Input layer validation
  - Business logic validation
  - Database constraint validation
  - Security policy validation

### 2.5 Error Handling and Reporting

#### FR-FV-2.5.1 Error Message Management
- **Description**: System shall provide clear and actionable error messages
- **Priority**: Medium
- **Acceptance Criteria**:
  - User-friendly error messages
  - Technical error details for debugging
  - Internationalization support for error messages
  - Error message templates
  - Context-aware error reporting
  - Error severity classification
- **Message Categories**:
  - Validation errors (user correctable)
  - System errors (technical issues)
  - Security errors (potential threats)
  - Warning messages (potential issues)

#### FR-FV-2.5.2 Error Logging and Monitoring
- **Description**: System shall log and monitor validation errors
- **Priority**: High
- **Acceptance Criteria**:
  - Comprehensive error logging
  - Error trend analysis
  - Security incident detection
  - Performance impact monitoring
  - Alert generation for critical errors
  - Error pattern recognition
- **Logging Details**:
  - User ID and session information
  - Input values (sanitized for security)
  - Validation rules that failed
  - Timestamp and request context
  - Error resolution status

## 3. Non-Functional Requirements

### 3.1 Performance
- **NFR-FV-3.1.1**: Client-side validation response < 50ms
- **NFR-FV-3.1.2**: Server-side validation response < 200ms
- **NFR-FV-3.1.3**: File upload validation < 5 seconds for typical files
- **NFR-FV-3.1.4**: Bulk validation operations < 1 second per 100 items

### 3.2 Security
- **NFR-FV-3.2.1**: Zero tolerance for XSS vulnerabilities
- **NFR-FV-3.2.2**: Zero tolerance for SQL injection vulnerabilities
- **NFR-FV-3.2.3**: 100% of file uploads scanned for malware
- **NFR-FV-3.2.4**: Input validation bypassed in < 0.1% of attempts

### 3.3 Reliability
- **NFR-FV-3.3.1**: 99.9% validation accuracy (no false negatives for security)
- **NFR-FV-3.3.2**: < 1% false positive rate for business logic validation
- **NFR-FV-3.3.3**: Graceful degradation when validation services unavailable
- **NFR-FV-3.3.4**: Automatic recovery from validation service failures

### 3.4 Usability
- **NFR-FV-3.4.1**: Error messages understandable to non-technical users
- **NFR-FV-3.4.2**: Validation feedback provided within 100ms of user action
- **NFR-FV-3.4.3**: < 5% of users require support for validation errors
- **NFR-FV-3.4.4**: Accessibility compliance (WCAG 2.1 AA)

## 4. Technical Architecture

### 4.1 Validation Pipeline
```python
# Validation pipeline architecture
class ValidationPipeline:
    def __init__(self):
        self.validators = [
            SecurityValidator(),      # XSS, SQL injection, etc.
            TypeValidator(),         # Data type validation
            FormatValidator(),       # Format and pattern validation
            BusinessLogicValidator(), # Business rule validation
            IntegrityValidator()     # Data integrity validation
        ]
    
    def validate(self, input_data, context):
        errors = []
        sanitized_data = input_data.copy()
        
        for validator in self.validators:
            try:
                sanitized_data = validator.validate_and_sanitize(
                    sanitized_data, context
                )
            except ValidationError as e:
                errors.extend(e.errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            sanitized_data=sanitized_data
        )
```

### 4.2 Validation Rules Engine
```python
# Flexible validation rules system
class ValidationRule:
    def __init__(self, field, rule_type, params, error_message):
        self.field = field
        self.rule_type = rule_type
        self.params = params
        self.error_message = error_message
    
    def validate(self, value, context=None):
        validator = get_validator(self.rule_type)
        return validator.validate(value, self.params, context)

# Example usage
project_validation_rules = [
    ValidationRule('name', 'required', {}, 'Project name is required'),
    ValidationRule('name', 'min_length', {'min': 3}, 'Name must be at least 3 characters'),
    ValidationRule('name', 'max_length', {'max': 100}, 'Name must not exceed 100 characters'),
    ValidationRule('name', 'unique', {'scope': 'user'}, 'Project name must be unique'),
    ValidationRule('camera_model', 'required', {}, 'Camera model is required'),
    ValidationRule('camera_view', 'enum', {'values': ['Front-facing VRU', 'Rear-facing VRU']}, 
                   'Invalid camera view'),
    ValidationRule('signal_type', 'enum', {'values': ['GPIO', 'Network Packet', 'Serial']},
                   'Invalid signal type')
]
```

## 5. API Validation Specifications

### 5.1 Request Validation Middleware
```yaml
# FastAPI validation middleware
components:
  schemas:
    ValidationError:
      type: object
      properties:
        field:
          type: string
          description: Field name that failed validation
        error_code:
          type: string
          description: Error code for programmatic handling
        message:
          type: string
          description: Human-readable error message
        severity:
          type: string
          enum: [error, warning, info]
        context:
          type: object
          description: Additional context about the error
    
    ValidationResponse:
      type: object
      properties:
        is_valid:
          type: boolean
        errors:
          type: array
          items:
            $ref: '#/components/schemas/ValidationError'
        warnings:
          type: array
          items:
            $ref: '#/components/schemas/ValidationError'
        sanitized_data:
          type: object
          description: Cleaned and sanitized input data

# Standard error responses
responses:
  ValidationError:
    description: Validation failed
    content:
      application/json:
        schema:
          type: object
          properties:
            detail:
              type: string
            validation_errors:
              $ref: '#/components/schemas/ValidationResponse'
        example:
          detail: "Validation failed"
          validation_errors:
            is_valid: false
            errors:
              - field: "name"
                error_code: "FIELD_REQUIRED"
                message: "Project name is required"
                severity: "error"
              - field: "camera_view"
                error_code: "INVALID_ENUM"
                message: "Invalid camera view. Must be one of: Front-facing VRU, Rear-facing VRU"
                severity: "error"
```

### 5.2 Endpoint-Specific Validation

#### 5.2.1 Project Creation Validation
```yaml
paths:
  /api/projects:
    post:
      summary: Create new project with comprehensive validation
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [name, camera_model, camera_view, signal_type]
              properties:
                name:
                  type: string
                  minLength: 3
                  maxLength: 100
                  pattern: '^[a-zA-Z0-9\s\-_]+$'
                  description: 'Alphanumeric characters, spaces, hyphens, and underscores only'
                description:
                  type: string
                  maxLength: 1000
                camera_model:
                  type: string
                  minLength: 2
                  maxLength: 50
                camera_view:
                  type: string
                  enum: ['Front-facing VRU', 'Rear-facing VRU', 'In-Cab Driver Behavior', 'Multi-angle']
                lens_type:
                  type: string
                  maxLength: 50
                resolution:
                  type: string
                  pattern: '^\d+x\d+$'
                  example: '1920x1080'
                frame_rate:
                  type: integer
                  minimum: 1
                  maximum: 120
                signal_type:
                  type: string
                  enum: ['GPIO', 'Network Packet', 'Serial', 'CAN Bus']
              additionalProperties: false
      responses:
        201:
          description: Project created successfully
        400:
          $ref: '#/responses/ValidationError'
        409:
          description: Project name already exists
```

#### 5.2.2 Annotation Creation Validation
```yaml
  /api/videos/{video_id}/annotations:
    post:
      summary: Create annotation with geometric and temporal validation
      parameters:
        - name: video_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [frame_number, timestamp, vru_type, bounding_box]
              properties:
                frame_number:
                  type: integer
                  minimum: 0
                  description: Must be valid frame number for the video
                timestamp:
                  type: number
                  minimum: 0
                  description: Must be within video duration
                end_timestamp:
                  type: number
                  minimum: 0
                  description: Must be greater than timestamp if provided
                vru_type:
                  type: string
                  enum: [pedestrian, cyclist, motorcyclist, wheelchair, scooter, animal, other]
                bounding_box:
                  type: object
                  required: [x, y, width, height]
                  properties:
                    x:
                      type: number
                      minimum: 0
                      maximum: 1
                      description: Normalized X coordinate (0-1)
                    y:
                      type: number
                      minimum: 0
                      maximum: 1
                      description: Normalized Y coordinate (0-1)
                    width:
                      type: number
                      minimum: 0.001
                      maximum: 1
                      description: Normalized width (0-1)
                    height:
                      type: number
                      minimum: 0.001
                      maximum: 1
                      description: Normalized height (0-1)
                    confidence:
                      type: number
                      minimum: 0
                      maximum: 1
                  additionalProperties: false
                occluded:
                  type: boolean
                  default: false
                truncated:
                  type: boolean
                  default: false
                difficult:
                  type: boolean
                  default: false
                notes:
                  type: string
                  maxLength: 2000
              additionalProperties: false
      responses:
        201:
          description: Annotation created successfully
        400:
          $ref: '#/responses/ValidationError'
```

#### 5.2.3 File Upload Validation
```yaml
  /api/videos/upload:
    post:
      summary: Upload video file with comprehensive validation
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [file, project_id]
              properties:
                file:
                  type: string
                  format: binary
                  description: Video file (MP4, AVI, MOV only, max 2GB)
                project_id:
                  type: string
                  format: uuid
                filename_override:
                  type: string
                  pattern: '^[a-zA-Z0-9\-_\.]+$'
                  maxLength: 255
            encoding:
              file:
                contentType: video/*
      responses:
        201:
          description: Video uploaded and validated successfully
        400:
          description: File validation failed
          content:
            application/json:
              schema:
                type: object
                properties:
                  detail:
                    type: string
                  file_errors:
                    type: array
                    items:
                      type: object
                      properties:
                        error_type:
                          type: string
                          enum: [invalid_format, file_too_large, corrupted_file, 
                                 invalid_codec, malware_detected, unsupported_container]
                        message:
                          type: string
                        technical_details:
                          type: string
        413:
          description: File too large
        415:
          description: Unsupported media type
```

### 5.3 Custom Validation Rules

```yaml
  /api/validation/rules:
    get:
      summary: Get available validation rules
      responses:
        200:
          description: List of validation rules
          content:
            application/json:
              schema:
                type: object
                properties:
                  rules:
                    type: object
                    additionalProperties:
                      type: object
                      properties:
                        description:
                          type: string
                        parameters:
                          type: array
                          items:
                            type: object
                            properties:
                              name:
                                type: string
                              type:
                                type: string
                              required:
                                type: boolean
                              description:
                                type: string
                example:
                  rules:
                    required:
                      description: "Field is required and cannot be empty"
                      parameters: []
                    min_length:
                      description: "String must have minimum length"
                      parameters:
                        - name: "min"
                          type: "integer"
                          required: true
                          description: "Minimum length"
                    unique:
                      description: "Value must be unique within scope"
                      parameters:
                        - name: "scope"
                          type: "string"
                          required: true
                          description: "Uniqueness scope (user, project, global)"
    
    post:
      summary: Validate data against custom rules
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                data:
                  type: object
                  description: Data to validate
                rules:
                  type: array
                  items:
                    type: object
                    properties:
                      field:
                        type: string
                      rule:
                        type: string
                      parameters:
                        type: object
                      message:
                        type: string
                context:
                  type: object
                  description: Additional context for validation
      responses:
        200:
          description: Validation results
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationResponse'
```

## 6. Security Implementation Details

### 6.1 XSS Prevention Implementation
```python
import html
import re
from urllib.parse import urlparse
from markupsafe import escape

class XSSPrevention:
    # Dangerous HTML tags that should be removed
    DANGEROUS_TAGS = [
        'script', 'iframe', 'object', 'embed', 'link', 
        'meta', 'style', 'base', 'form', 'input'
    ]
    
    # Dangerous attributes that should be removed
    DANGEROUS_ATTRIBUTES = [
        'onload', 'onerror', 'onclick', 'onmouseover', 
        'onfocus', 'onblur', 'javascript:', 'vbscript:'
    ]
    
    @staticmethod
    def sanitize_html(input_html: str) -> str:
        """Remove dangerous HTML tags and attributes"""
        if not input_html:
            return input_html
            
        # Remove dangerous tags
        for tag in XSSPrevention.DANGEROUS_TAGS:
            pattern = f'<{tag}[^>]*>.*?</{tag}>'
            input_html = re.sub(pattern, '', input_html, flags=re.IGNORECASE | re.DOTALL)
            
        # Remove dangerous attributes
        for attr in XSSPrevention.DANGEROUS_ATTRIBUTES:
            pattern = f'{attr}[^>]*'
            input_html = re.sub(pattern, '', input_html, flags=re.IGNORECASE)
            
        return input_html
    
    @staticmethod
    def sanitize_text(input_text: str) -> str:
        """HTML escape text for safe display"""
        if not input_text:
            return input_text
        return html.escape(input_text)
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        """Validate and sanitize URLs"""
        if not url:
            return url
            
        parsed = urlparse(url)
        
        # Block dangerous protocols
        if parsed.scheme.lower() in ['javascript', 'vbscript', 'data']:
            return ''
            
        # Only allow safe protocols
        if parsed.scheme.lower() not in ['http', 'https', 'ftp', 'mailto']:
            return ''
            
        return url

class SQLInjectionPrevention:
    # SQL keywords that might indicate injection attempts
    SQL_KEYWORDS = [
        'select', 'insert', 'update', 'delete', 'drop', 'create',
        'alter', 'exec', 'execute', 'sp_', 'xp_', 'union', 'script'
    ]
    
    @staticmethod
    def detect_sql_injection(input_string: str) -> bool:
        """Detect potential SQL injection patterns"""
        if not input_string:
            return False
            
        input_lower = input_string.lower()
        
        # Check for SQL keywords
        for keyword in SQLInjectionPrevention.SQL_KEYWORDS:
            if keyword in input_lower:
                return True
                
        # Check for SQL comment patterns
        if '--' in input_string or '/*' in input_string:
            return True
            
        # Check for quote manipulation
        quote_count = input_string.count("'")
        if quote_count > 2:
            return True
            
        return False
    
    @staticmethod
    def sanitize_sql_input(input_string: str) -> str:
        """Sanitize input to prevent SQL injection"""
        if not input_string:
            return input_string
            
        # Remove SQL comments
        sanitized = re.sub(r'--.*?$', '', input_string, flags=re.MULTILINE)
        sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
        
        # Escape single quotes
        sanitized = sanitized.replace("'", "''")
        
        return sanitized
```

### 6.2 File Upload Security Implementation
```python
import mimetypes
import magic
from pathlib import Path
import hashlib

class FileUploadSecurity:
    # Allowed MIME types
    ALLOWED_VIDEO_TYPES = {
        'video/mp4': ['.mp4'],
        'video/x-msvideo': ['.avi'],
        'video/quicktime': ['.mov'],
        'video/x-ms-wmv': ['.wmv']
    }
    
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/gif': ['.gif'],
        'image/bmp': ['.bmp']
    }
    
    # Maximum file sizes (in bytes)
    MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50MB
    
    # Dangerous file extensions
    DANGEROUS_EXTENSIONS = [
        '.exe', '.bat', '.cmd', '.scr', '.pif', '.com', '.vbs',
        '.js', '.jar', '.php', '.py', '.pl', '.sh', '.ps1'
    ]
    
    @staticmethod
    def validate_file_type(file_path: Path, expected_type: str) -> bool:
        """Validate file type using multiple methods"""
        # Check file extension
        extension = file_path.suffix.lower()
        if extension in FileUploadSecurity.DANGEROUS_EXTENSIONS:
            return False
            
        # Check MIME type from file content
        try:
            mime_type = magic.from_file(str(file_path), mime=True)
        except:
            return False
            
        # Validate against allowed types
        if expected_type == 'video':
            return mime_type in FileUploadSecurity.ALLOWED_VIDEO_TYPES
        elif expected_type == 'image':
            return mime_type in FileUploadSecurity.ALLOWED_IMAGE_TYPES
            
        return False
    
    @staticmethod
    def validate_file_size(file_path: Path, file_type: str) -> bool:
        """Validate file size against limits"""
        file_size = file_path.stat().st_size
        
        if file_type == 'video':
            return file_size <= FileUploadSecurity.MAX_VIDEO_SIZE
        elif file_type == 'image':
            return file_size <= FileUploadSecurity.MAX_IMAGE_SIZE
            
        return False
    
    @staticmethod
    def scan_for_malware(file_path: Path) -> bool:
        """Scan file for malware (placeholder for real implementation)"""
        # In real implementation, integrate with antivirus engine
        # For now, do basic checks
        
        # Check file size (extremely large files might be suspicious)
        if file_path.stat().st_size > 5 * 1024 * 1024 * 1024:  # 5GB
            return False
            
        # Check for embedded executables in video files
        try:
            with open(file_path, 'rb') as f:
                content = f.read(1024)  # Read first 1KB
                # Look for PE header (Windows executable)
                if b'MZ' in content and b'PE' in content:
                    return False
        except:
            return False
            
        return True
    
    @staticmethod
    def generate_safe_filename(original_filename: str) -> str:
        """Generate a safe filename"""
        # Remove path components
        filename = Path(original_filename).name
        
        # Remove dangerous characters
        safe_chars = re.sub(r'[^a-zA-Z0-9\-_\.]', '_', filename)
        
        # Limit length
        if len(safe_chars) > 255:
            name_part = safe_chars[:200]
            extension = Path(safe_chars).suffix
            safe_chars = f"{name_part}{extension}"
            
        return safe_chars
```

### 6.3 Input Sanitization Middleware
```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import json

class InputSanitizationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip sanitization for certain endpoints
        if request.url.path.startswith('/api/docs') or request.url.path.startswith('/static'):
            return await call_next(request)
        
        # Sanitize query parameters
        if request.query_params:
            sanitized_params = {}
            for key, value in request.query_params.items():
                sanitized_key = self.sanitize_parameter(key)
                sanitized_value = self.sanitize_parameter(value)
                sanitized_params[sanitized_key] = sanitized_value
            # Replace query params with sanitized versions
            request._query_params = sanitized_params
        
        # Sanitize request body for JSON requests
        if request.headers.get('content-type') == 'application/json':
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    sanitized_data = self.sanitize_json_data(data)
                    # Replace request body with sanitized data
                    request._body = json.dumps(sanitized_data).encode()
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        
        response = await call_next(request)
        return response
    
    def sanitize_parameter(self, value: str) -> str:
        """Sanitize a single parameter value"""
        if not isinstance(value, str):
            return value
            
        # Remove null bytes
        sanitized = value.replace('\x00', '')
        
        # XSS prevention
        sanitized = XSSPrevention.sanitize_text(sanitized)
        
        # SQL injection detection
        if SQLInjectionPrevention.detect_sql_injection(sanitized):
            raise HTTPException(status_code=400, detail="Potentially malicious input detected")
        
        return sanitized
    
    def sanitize_json_data(self, data):
        """Recursively sanitize JSON data"""
        if isinstance(data, dict):
            return {
                self.sanitize_parameter(k): self.sanitize_json_data(v) 
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self.sanitize_json_data(item) for item in data]
        elif isinstance(data, str):
            return self.sanitize_parameter(data)
        else:
            return data
```

## 7. Database Schema for Validation

### 7.1 Validation Rules Table
```sql
CREATE TABLE validation_rules (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    entity_type VARCHAR(50) NOT NULL, -- project, video, annotation, etc.
    field_name VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- required, min_length, max_length, enum, etc.
    rule_parameters JSON,
    error_message VARCHAR(500) NOT NULL,
    error_code VARCHAR(50) NOT NULL,
    severity ENUM('error', 'warning', 'info') DEFAULT 'error',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_validation_entity_field (entity_type, field_name),
    INDEX idx_validation_rule_type (rule_type),
    INDEX idx_validation_active (is_active)
);

-- Sample validation rules
INSERT INTO validation_rules VALUES
('rule-001', 'project', 'name', 'required', '{}', 'Project name is required', 'FIELD_REQUIRED', 'error', TRUE, NOW(), NOW()),
('rule-002', 'project', 'name', 'min_length', '{"min": 3}', 'Project name must be at least 3 characters', 'MIN_LENGTH', 'error', TRUE, NOW(), NOW()),
('rule-003', 'project', 'name', 'max_length', '{"max": 100}', 'Project name must not exceed 100 characters', 'MAX_LENGTH', 'error', TRUE, NOW(), NOW()),
('rule-004', 'project', 'camera_view', 'enum', '{"values": ["Front-facing VRU", "Rear-facing VRU", "In-Cab Driver Behavior"]}', 'Invalid camera view', 'INVALID_ENUM', 'error', TRUE, NOW(), NOW());
```

### 7.2 Validation Logs Table
```sql
CREATE TABLE validation_logs (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(36),
    user_id VARCHAR(36),
    session_id VARCHAR(100),
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- Validation Details
    validation_type ENUM('input', 'business', 'security', 'file_upload') NOT NULL,
    is_valid BOOLEAN NOT NULL,
    errors_count INTEGER DEFAULT 0,
    warnings_count INTEGER DEFAULT 0,
    
    -- Input Data (sanitized)
    original_data JSON,
    sanitized_data JSON,
    validation_rules_applied JSON,
    errors JSON,
    warnings JSON,
    
    -- Performance Metrics
    validation_duration_ms INTEGER,
    
    -- Security Flags
    security_threat_detected BOOLEAN DEFAULT FALSE,
    threat_type VARCHAR(100),
    blocked BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_validation_logs_entity (entity_type, entity_id),
    INDEX idx_validation_logs_user (user_id),
    INDEX idx_validation_logs_created (created_at),
    INDEX idx_validation_logs_security (security_threat_detected),
    INDEX idx_validation_logs_type (validation_type),
    INDEX idx_validation_logs_valid (is_valid)
);
```

### 7.3 File Upload Validation Table
```sql
CREATE TABLE file_upload_validations (
    id VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    original_filename VARCHAR(500) NOT NULL,
    sanitized_filename VARCHAR(500) NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    file_size BIGINT NOT NULL,
    mime_type VARCHAR(100),
    detected_type VARCHAR(100),
    
    -- Validation Results
    type_validation_passed BOOLEAN DEFAULT FALSE,
    size_validation_passed BOOLEAN DEFAULT FALSE,
    content_validation_passed BOOLEAN DEFAULT FALSE,
    malware_scan_passed BOOLEAN DEFAULT FALSE,
    
    -- Security Checks
    malware_detected BOOLEAN DEFAULT FALSE,
    malware_type VARCHAR(100),
    quarantined BOOLEAN DEFAULT FALSE,
    
    -- File Metadata
    video_duration FLOAT, -- For video files
    video_resolution VARCHAR(20), -- e.g., '1920x1080'
    video_codec VARCHAR(50),
    video_fps FLOAT,
    
    -- Processing Status
    processing_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    error_message TEXT,
    
    -- Audit Fields
    uploaded_by VARCHAR(36),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_upload_validation_filename (original_filename),
    INDEX idx_upload_validation_user (uploaded_by),
    INDEX idx_upload_validation_status (processing_status),
    INDEX idx_upload_validation_malware (malware_detected),
    INDEX idx_upload_validation_uploaded (uploaded_at)
);
```

## 8. User Experience Specifications

### 8.1 Real-time Validation UI
```typescript
// React component for real-time validation
interface ValidationState {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  isValidating: boolean;
}

const useRealTimeValidation = (field: string, value: any, rules: ValidationRule[]) => {
  const [validationState, setValidationState] = useState<ValidationState>({
    isValid: true,
    errors: [],
    warnings: [],
    isValidating: false
  });

  // Debounced validation to prevent excessive API calls
  const debouncedValidate = useMemo(
    () => debounce(async (val: any) => {
      setValidationState(prev => ({ ...prev, isValidating: true }));
      
      try {
        const result = await validateField(field, val, rules);
        setValidationState({
          isValid: result.isValid,
          errors: result.errors,
          warnings: result.warnings,
          isValidating: false
        });
      } catch (error) {
        setValidationState(prev => ({
          ...prev,
          isValidating: false,
          errors: [{ message: 'Validation service unavailable', severity: 'error' }]
        }));
      }
    }, 300),
    [field, rules]
  );

  useEffect(() => {
    if (value !== undefined && value !== '') {
      debouncedValidate(value);
    }
  }, [value, debouncedValidate]);

  return validationState;
};

// Validation UI component
const ValidatedInput: React.FC<{
  field: string;
  value: string;
  onChange: (value: string) => void;
  rules: ValidationRule[];
  placeholder?: string;
}> = ({ field, value, onChange, rules, placeholder }) => {
  const validation = useRealTimeValidation(field, value, rules);

  return (
    <div className="validated-input">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`
          form-input
          ${validation.errors.length > 0 ? 'error' : ''}
          ${validation.warnings.length > 0 ? 'warning' : ''}
          ${validation.isValid && value ? 'valid' : ''}
        `}
        aria-invalid={validation.errors.length > 0}
        aria-describedby={`${field}-validation`}
      />
      
      {validation.isValidating && (
        <div className="validation-spinner" aria-label="Validating...">
          <Spinner size="sm" />
        </div>
      )}
      
      <div id={`${field}-validation`} className="validation-messages">
        {validation.errors.map((error, index) => (
          <div key={index} className="error-message" role="alert">
            <Icon name="error" /> {error.message}
          </div>
        ))}
        {validation.warnings.map((warning, index) => (
          <div key={index} className="warning-message">
            <Icon name="warning" /> {warning.message}
          </div>
        ))}
      </div>
    </div>
  );
};
```

### 8.2 Form Validation Integration
```typescript
// Form validation hook
const useFormValidation = <T extends Record<string, any>>(
  initialData: T,
  validationRules: Record<keyof T, ValidationRule[]>
) => {
  const [data, setData] = useState<T>(initialData);
  const [validationStates, setValidationStates] = useState<Record<keyof T, ValidationState>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const updateField = (field: keyof T, value: any) => {
    setData(prev => ({ ...prev, [field]: value }));
  };

  const validateAll = async (): Promise<boolean> => {
    setIsSubmitting(true);
    
    try {
      const validationResults = await Promise.all(
        Object.entries(validationRules).map(async ([field, rules]) => {
          const result = await validateField(field as string, data[field as keyof T], rules as ValidationRule[]);
          return { field, result };
        })
      );

      const newValidationStates: Record<keyof T, ValidationState> = {};
      let isFormValid = true;

      for (const { field, result } of validationResults) {
        newValidationStates[field as keyof T] = {
          isValid: result.isValid,
          errors: result.errors,
          warnings: result.warnings,
          isValidating: false
        };
        if (!result.isValid) {
          isFormValid = false;
        }
      }

      setValidationStates(newValidationStates);
      return isFormValid;
    } finally {
      setIsSubmitting(false);
    }
  };

  const getFieldValidation = (field: keyof T): ValidationState => {
    return validationStates[field] || { isValid: true, errors: [], warnings: [], isValidating: false };
  };

  const isFormValid = Object.values(validationStates).every(state => state.isValid);
  const hasAnyErrors = Object.values(validationStates).some(state => state.errors.length > 0);

  return {
    data,
    updateField,
    validateAll,
    getFieldValidation,
    isFormValid,
    hasAnyErrors,
    isSubmitting
  };
};
```

## 9. Integration Points

### 9.1 Existing System Integration
- **API Layer**: Validation middleware integrated into all API endpoints
- **Database Layer**: Constraint validation at ORM and database levels
- **Frontend Components**: Validation UI components for forms and inputs
- **File Upload**: Integrated validation for all file upload workflows
- **User Management**: Validation rules based on user roles and permissions

### 9.2 Security Integration
- **Authentication System**: Validation of authentication tokens and sessions
- **Authorization System**: Role-based validation rules
- **Audit System**: Integration with audit logging for security events
- **Monitoring System**: Real-time monitoring of validation failures and threats

### 9.3 External System Integration
- **Antivirus Services**: Integration with external malware scanning services
- **Email Validation Services**: External email validation for improved accuracy
- **GeoIP Services**: Location-based validation and fraud detection
- **Machine Learning**: Anomaly detection for unusual validation patterns

## 10. Success Metrics

### 10.1 Security Metrics
- **Zero tolerance**: 0 successful XSS or SQL injection attacks
- **Threat detection**: 100% of known malware signatures detected
- **False positive rate**: < 0.1% for security validations
- **Response time**: Security validation < 100ms average

### 10.2 Performance Metrics
- **Validation speed**: Client-side validation < 50ms, server-side < 200ms
- **Availability**: 99.9% uptime for validation services
- **Throughput**: 10,000+ validation requests per minute
- **Error rate**: < 0.1% validation service errors

### 10.3 User Experience Metrics
- **Error clarity**: > 95% of users understand validation error messages
- **Completion rate**: > 98% of forms completed successfully after validation errors corrected
- **Support requests**: < 1% of validation errors result in support requests
- **Time to resolution**: Average 30 seconds to resolve validation errors

### 10.4 Data Quality Metrics
- **Accuracy**: > 99.9% of valid data passes validation
- **Completeness**: > 99% of required fields validated
- **Consistency**: > 99% consistency in validation rule application
- **Integrity**: 100% of data integrity constraints enforced

---

This comprehensive form validation specification provides the foundation for implementing robust input validation, security controls, and user experience enhancements across the AI model validation platform. The system ensures data integrity while maintaining security and usability standards.