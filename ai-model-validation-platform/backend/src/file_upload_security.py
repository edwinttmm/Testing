"""
File Upload Security System - SPARC Refinement Implementation
Comprehensive file upload validation with security checks
Root cause fix for file upload security vulnerabilities
"""

import os
import re
import mimetypes
import hashlib
import magic
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import logging

from fastapi import UploadFile, HTTPException, status
from src.form_validation_middleware import ValidationMiddleware

logger = logging.getLogger(__name__)

class FileUploadSecurityError(Exception):
    """Raised when file upload security validation fails"""
    pass

class FileUploadValidator:
    """
    Comprehensive file upload validation with security hardening
    Root cause fix for missing file upload validation and security
    """
    
    # Allowed file extensions and their corresponding MIME types
    ALLOWED_VIDEO_EXTENSIONS = {
        '.mp4': ['video/mp4', 'video/x-mp4'],
        '.avi': ['video/avi', 'video/x-msvideo'],
        '.mov': ['video/quicktime'],
        '.mkv': ['video/x-matroska'],
        '.wmv': ['video/x-ms-wmv'],
        '.flv': ['video/x-flv'],
        '.webm': ['video/webm']
    }
    
    ALLOWED_IMAGE_EXTENSIONS = {
        '.jpg': ['image/jpeg'],
        '.jpeg': ['image/jpeg'],
        '.png': ['image/png'],
        '.bmp': ['image/bmp'],
        '.tiff': ['image/tiff'],
        '.gif': ['image/gif']
    }
    
    # Dangerous file patterns to block
    DANGEROUS_PATTERNS = [
        r'\.(exe|bat|cmd|scr|pif|com)$',        # Executable files
        r'\.(php|asp|aspx|jsp)$',               # Web scripts
        r'\.(sh|bash|zsh|fish)$',               # Shell scripts
        r'\.(py|pl|rb|jar)$',                   # Script files
        r'\.(dll|so|dylib)$',                   # Library files
        r'\.htaccess$',                         # Apache config
        r'\.config$',                           # Configuration files
    ]
    
    # File signature validation (magic bytes)
    FILE_SIGNATURES = {
        'mp4': [b'\x00\x00\x00\x18ftypmp4', b'\x00\x00\x00\x20ftypmp4'],
        'avi': [b'RIFF', b'AVI '],
        'mov': [b'\x00\x00\x00\x14ftypqt'],
        'jpg': [b'\xff\xd8\xff'],
        'png': [b'\x89PNG\x0d\x0a\x1a\x0a'],
        'gif': [b'GIF87a', b'GIF89a'],
        'bmp': [b'BM']
    }
    
    def __init__(self, max_file_size: int = 2 * 1024 * 1024 * 1024):  # 2GB default
        self.max_file_size = max_file_size
        self.allowed_extensions = {**self.ALLOWED_VIDEO_EXTENSIONS, **self.ALLOWED_IMAGE_EXTENSIONS}
    
    async def validate_upload_file(self, file: UploadFile) -> Dict[str, Any]:
        """
        Comprehensive file upload validation
        Returns validation results with security checks
        """
        try:
            validation_results = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "file_info": {},
                "security_checks": {}
            }
            
            # Basic file information validation
            filename_validation = self._validate_filename(file.filename)
            if not filename_validation["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(filename_validation["errors"])
                return validation_results
            
            # File size validation
            file_size = 0
            if hasattr(file, 'size'):
                file_size = file.size
            else:
                # Read file to get size if not available
                content = await file.read()
                file_size = len(content)
                await file.seek(0)  # Reset file pointer
            
            size_validation = self._validate_file_size(file_size)
            if not size_validation["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(size_validation["errors"])
            
            # MIME type validation
            mime_validation = self._validate_mime_type(file.content_type, filename_validation["sanitized_filename"])
            if not mime_validation["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(mime_validation["errors"])
            
            # File signature validation (magic bytes)
            signature_validation = await self._validate_file_signature(file, filename_validation["file_extension"])
            if not signature_validation["valid"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(signature_validation["errors"])
            
            # Security scans
            security_validation = await self._perform_security_scans(file)
            validation_results["security_checks"] = security_validation
            if not security_validation["passed"]:
                validation_results["valid"] = False
                validation_results["errors"].extend(security_validation["errors"])
            
            # Compile file information
            validation_results["file_info"] = {
                "original_filename": file.filename,
                "sanitized_filename": filename_validation["sanitized_filename"],
                "file_extension": filename_validation["file_extension"],
                "file_size": file_size,
                "content_type": file.content_type,
                "mime_validation": mime_validation,
                "signature_validation": signature_validation["signature_matched"]
            }
            
            return validation_results
            
        except Exception as e:
            logger.error(f"File upload validation error: {str(e)}")
            return {
                "valid": False,
                "errors": [f"File validation failed: {str(e)}"],
                "warnings": [],
                "file_info": {},
                "security_checks": {"passed": False, "error": str(e)}
            }
    
    def _validate_filename(self, filename: str) -> Dict[str, Any]:
        """Validate and sanitize filename"""
        if not filename:
            return {"valid": False, "errors": ["Filename cannot be empty"]}
        
        try:
            # Sanitize filename using security middleware
            sanitized_filename = ValidationMiddleware.sanitize_string_input(filename, 255)
        except Exception as e:
            return {"valid": False, "errors": [f"Filename security validation failed: {str(e)}"]}
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sanitized_filename.lower()):
                return {"valid": False, "errors": ["File type potentially dangerous"]}
        
        # Extract and validate file extension
        file_ext = '.' + sanitized_filename.lower().split('.')[-1] if '.' in sanitized_filename else ''
        if file_ext not in self.allowed_extensions:
            allowed_exts = ', '.join(self.allowed_extensions.keys())
            return {
                "valid": False,
                "errors": [f"File extension '{file_ext}' not allowed. Allowed extensions: {allowed_exts}"]
            }
        
        # Check for path traversal attempts
        if '..' in sanitized_filename or '/' in sanitized_filename or '\\' in sanitized_filename:
            return {"valid": False, "errors": ["Filename contains invalid path characters"]}
        
        # Check filename length
        if len(sanitized_filename) > 255:
            return {"valid": False, "errors": ["Filename too long (max 255 characters)"]}
        
        return {
            "valid": True,
            "sanitized_filename": sanitized_filename,
            "file_extension": file_ext,
            "errors": []
        }
    
    def _validate_file_size(self, file_size: int) -> Dict[str, Any]:
        """Validate file size"""
        if file_size == 0:
            return {"valid": False, "errors": ["File is empty"]}
        
        if file_size > self.max_file_size:
            max_size_mb = self.max_file_size / (1024 * 1024)
            actual_size_mb = file_size / (1024 * 1024)
            return {
                "valid": False,
                "errors": [f"File size ({actual_size_mb:.1f} MB) exceeds maximum allowed size ({max_size_mb:.0f} MB)"]
            }
        
        return {"valid": True, "errors": []}
    
    def _validate_mime_type(self, content_type: str, filename: str) -> Dict[str, Any]:
        """Validate MIME type against filename extension"""
        if not content_type:
            return {"valid": False, "errors": ["Content-Type header missing"]}
        
        file_ext = '.' + filename.lower().split('.')[-1] if '.' in filename else ''
        if file_ext not in self.allowed_extensions:
            return {"valid": False, "errors": ["File extension not in allowed list"]}
        
        allowed_mimes = self.allowed_extensions[file_ext]
        if content_type not in allowed_mimes:
            return {
                "valid": False,
                "errors": [f"MIME type '{content_type}' doesn't match file extension '{file_ext}'. Expected: {', '.join(allowed_mimes)}"]
            }
        
        return {"valid": True, "errors": []}
    
    async def _validate_file_signature(self, file: UploadFile, file_extension: str) -> Dict[str, Any]:
        """Validate file signature (magic bytes) to prevent file type spoofing"""
        try:
            # Read first 32 bytes for signature check
            file_header = await file.read(32)
            await file.seek(0)  # Reset file pointer
            
            if len(file_header) < 4:
                return {"valid": False, "errors": ["File too small for signature validation"], "signature_matched": False}
            
            # Get expected signatures for this file type
            file_type = file_extension[1:] if file_extension.startswith('.') else file_extension
            expected_signatures = self.FILE_SIGNATURES.get(file_type, [])
            
            if not expected_signatures:
                # If no signature defined, consider it valid but note it
                return {
                    "valid": True,
                    "errors": [],
                    "signature_matched": "unknown",
                    "warning": f"No signature validation available for {file_type}"
                }
            
            # Check if file header matches any expected signature
            signature_matched = False
            for signature in expected_signatures:
                if file_header.startswith(signature):
                    signature_matched = True
                    break
            
            if not signature_matched:
                return {
                    "valid": False,
                    "errors": [f"File signature doesn't match expected format for {file_type}"],
                    "signature_matched": False
                }
            
            return {
                "valid": True,
                "errors": [],
                "signature_matched": True
            }
            
        except Exception as e:
            logger.error(f"File signature validation error: {str(e)}")
            return {
                "valid": False,
                "errors": [f"Signature validation failed: {str(e)}"],
                "signature_matched": False
            }
    
    async def _perform_security_scans(self, file: UploadFile) -> Dict[str, Any]:
        """Perform additional security scans on the file"""
        security_results = {
            "passed": True,
            "errors": [],
            "warnings": [],
            "scans_performed": []
        }
        
        try:
            # Read file content for scanning
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Scan for embedded scripts or malicious content
            script_scan = self._scan_for_embedded_scripts(content)
            security_results["scans_performed"].append("embedded_scripts")
            if not script_scan["clean"]:
                security_results["passed"] = False
                security_results["errors"].extend(script_scan["issues"])
            
            # Scan for suspicious binary patterns
            binary_scan = self._scan_binary_patterns(content)
            security_results["scans_performed"].append("binary_patterns")
            if not binary_scan["clean"]:
                security_results["warnings"].extend(binary_scan["warnings"])
            
            # Calculate file hash for integrity
            file_hash = hashlib.sha256(content).hexdigest()
            security_results["file_hash"] = file_hash
            security_results["scans_performed"].append("hash_calculation")
            
            return security_results
            
        except Exception as e:
            logger.error(f"Security scan error: {str(e)}")
            return {
                "passed": False,
                "errors": [f"Security scan failed: {str(e)}"],
                "warnings": [],
                "scans_performed": ["failed"]
            }
    
    def _scan_for_embedded_scripts(self, content: bytes) -> Dict[str, Any]:
        """Scan for embedded scripts or malicious content"""
        try:
            # Convert bytes to string for text-based scanning
            content_str = content.decode('utf-8', errors='ignore').lower()
            
            dangerous_patterns = [
                r'<script[^>]*>',
                r'javascript:',
                r'vbscript:',
                r'onload\s*=',
                r'onerror\s*=',
                r'eval\s*\(',
                r'exec\s*\(',
                r'system\s*\(',
                r'shell_exec',
                r'<?php',
                r'<%.*%>',
            ]
            
            issues = []
            for pattern in dangerous_patterns:
                if re.search(pattern, content_str):
                    issues.append(f"Potential malicious pattern detected: {pattern}")
            
            return {
                "clean": len(issues) == 0,
                "issues": issues
            }
            
        except Exception:
            # If we can't decode as text, assume it's binary and clean
            return {"clean": True, "issues": []}
    
    def _scan_binary_patterns(self, content: bytes) -> Dict[str, Any]:
        """Scan for suspicious binary patterns"""
        warnings = []
        
        # Check for executable signatures
        executable_signatures = [
            b'MZ',      # PE executable
            b'\x7fELF', # ELF executable
            b'\xfe\xed\xfa', # Mach-O executable
        ]
        
        for signature in executable_signatures:
            if content.startswith(signature):
                warnings.append("File contains executable signature")
                break
        
        # Check for embedded archives
        archive_signatures = [
            b'PK\x03\x04',  # ZIP
            b'Rar!',        # RAR
            b'\x1f\x8b',    # GZIP
        ]
        
        for signature in archive_signatures:
            if signature in content[:100]:  # Check first 100 bytes
                warnings.append("File may contain embedded archive")
                break
        
        return {
            "clean": len(warnings) == 0,
            "warnings": warnings
        }
    
    def generate_secure_filename(self, original_filename: str) -> str:
        """Generate a secure filename for storage"""
        try:
            # Sanitize the original filename
            validation_result = self._validate_filename(original_filename)
            if not validation_result["valid"]:
                # If original filename is invalid, generate a generic one
                file_ext = '.' + original_filename.split('.')[-1] if '.' in original_filename else '.bin'
                base_name = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            else:
                sanitized = validation_result["sanitized_filename"]
                file_ext = validation_result["file_extension"]
                base_name = sanitized.rsplit('.', 1)[0] if '.' in sanitized else sanitized
            
            # Add timestamp and hash for uniqueness
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            hash_suffix = hashlib.md5(f"{base_name}{timestamp}".encode()).hexdigest()[:8]
            
            secure_filename = f"{base_name}_{timestamp}_{hash_suffix}{file_ext}"
            
            return secure_filename
            
        except Exception as e:
            # Fallback to completely generated filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"secure_upload_{timestamp}.bin"

# Utility functions for file upload handling
async def validate_and_process_upload(file: UploadFile, validator: FileUploadValidator = None) -> Dict[str, Any]:
    """
    Convenience function to validate and process file uploads
    """
    if validator is None:
        validator = FileUploadValidator()
    
    # Validate the file
    validation_result = await validator.validate_upload_file(file)
    
    if validation_result["valid"]:
        # Generate secure filename
        secure_filename = validator.generate_secure_filename(file.filename)
        validation_result["secure_filename"] = secure_filename
        
        # Add processing recommendations
        validation_result["processing_recommendations"] = {
            "store_with_secure_filename": True,
            "scan_with_antivirus": validation_result["file_info"]["file_size"] > 100 * 1024 * 1024,  # Files > 100MB
            "quarantine_period": 24 if validation_result["security_checks"].get("warnings") else 0,  # hours
            "access_restrictions": "authenticated_users_only"
        }
    
    return validation_result

# FastAPI dependency for file upload validation
def get_file_upload_validator():
    """FastAPI dependency to get file upload validator"""
    return FileUploadValidator()

# Example usage with FastAPI endpoint
from fastapi import APIRouter, Depends

file_upload_router = APIRouter(prefix="/api/files", tags=["file-upload"])

@file_upload_router.post("/upload")
async def upload_file(
    file: UploadFile,
    validator: FileUploadValidator = Depends(get_file_upload_validator)
):
    """
    Secure file upload endpoint with comprehensive validation
    """
    try:
        # Validate the uploaded file
        validation_result = await validate_and_process_upload(file, validator)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "File upload validation failed",
                    "errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            )
        
        # File is valid, return success response
        return {
            "message": "File upload validation passed",
            "file_info": validation_result["file_info"],
            "secure_filename": validation_result["secure_filename"],
            "security_checks": validation_result["security_checks"],
            "processing_recommendations": validation_result["processing_recommendations"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload processing failed"
        )