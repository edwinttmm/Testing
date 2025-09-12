"""
Secure Upload Middleware for FastAPI
Integrates enterprise file upload security validation into the API endpoints
"""

import os
import tempfile
import logging
import json
from typing import Optional, Dict, Any
from fastapi import HTTPException, UploadFile, Request, status
from fastapi.responses import JSONResponse
import aiofiles
import asyncio
from pathlib import Path

from src.security.file_upload_security import (
    FileUploadSecurityValidator, 
    FileSecurityReport, 
    SecurityThreatLevel, 
    ScanResult,
    file_security_validator
)

logger = logging.getLogger(__name__)

class SecureUploadMiddleware:
    """Middleware for secure file upload handling"""
    
    def __init__(self, upload_dir: str = "uploads", temp_dir: str = "temp_uploads"):
        self.upload_dir = Path(upload_dir)
        self.temp_dir = Path(temp_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.security_validator = file_security_validator
        
    async def validate_and_process_upload(
        self, 
        file: UploadFile, 
        request: Request,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB default
        allowed_mime_types: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Securely validate and process file upload
        
        Args:
            file: FastAPI UploadFile object
            request: FastAPI Request object for IP tracking
            max_file_size: Maximum allowed file size
            allowed_mime_types: List of allowed MIME types
            
        Returns:
            Dict containing validation results and secure file path
            
        Raises:
            HTTPException: If file validation fails
        """
        client_ip = self._get_client_ip(request)
        temp_file_path = None
        
        try:
            # 1. Basic file checks
            if not file or not file.filename:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No file provided or filename is empty"
                )
            
            # 2. Create secure temporary file
            temp_file_path = await self._create_secure_temp_file(file)
            
            # 3. Run comprehensive security validation
            security_report = self.security_validator.validate_file_upload(
                file_path=temp_file_path,
                original_filename=file.filename,
                client_ip=client_ip
            )
            
            # 4. Check if upload should be allowed
            is_safe = self.security_validator.is_upload_safe(security_report)
            
            if not is_safe:
                # Clean up temp file
                self._cleanup_temp_file(temp_file_path)
                
                # Return detailed security error
                error_details = self._create_security_error_response(security_report)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_details
                )
            
            # 5. Move file to secure storage if validation passed
            secure_file_path = await self._move_to_secure_storage(
                temp_file_path, security_report.filename
            )
            
            # 6. Return validation results
            return {
                "success": True,
                "secure_file_path": str(secure_file_path),
                "security_report": self._serialize_security_report(security_report),
                "recommendations": self.security_validator.get_security_recommendations(security_report)
            }
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Clean up temp file on any error
            if temp_file_path:
                self._cleanup_temp_file(temp_file_path)
            
            logger.error(f"Secure upload processing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "File upload processing failed",
                    "message": "An internal error occurred during security validation",
                    "details": str(e) if logger.level == logging.DEBUG else None
                }
            )
    
    async def _create_secure_temp_file(self, file: UploadFile) -> str:
        """Create a secure temporary file for validation"""
        # Generate secure temporary filename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.temp_dir,
            prefix="upload_",
            suffix=".tmp"
        )
        
        try:
            # Write uploaded file to temp location with size checking
            bytes_written = 0
            chunk_size = 64 * 1024  # 64KB chunks
            max_size = 100 * 1024 * 1024  # 100MB limit
            
            with os.fdopen(temp_fd, 'wb') as temp_file:
                # Read and write file in chunks
                await file.seek(0)  # Ensure we're at the beginning
                
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    
                    bytes_written += len(chunk)
                    if bytes_written > max_size:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File size exceeds maximum allowed size of {max_size // (1024*1024)}MB"
                        )
                    
                    temp_file.write(chunk)
                
                # Ensure data is written to disk
                temp_file.flush()
                os.fsync(temp_file.fileno())
            
            return temp_path
            
        except Exception as e:
            # Clean up on error
            try:
                os.unlink(temp_path)
            except:
                pass
            raise
    
    async def _move_to_secure_storage(self, temp_path: str, original_filename: str) -> str:
        """Move validated file to secure storage location"""
        # Generate secure filename
        import uuid
        from pathlib import Path
        
        file_ext = Path(original_filename).suffix
        secure_filename = f"{uuid.uuid4()}{file_ext}"
        secure_path = self.upload_dir / secure_filename
        
        # Ensure upload directory exists with secure permissions
        self.upload_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
        
        # Move file atomically
        os.rename(temp_path, str(secure_path))
        
        # Set secure file permissions
        os.chmod(str(secure_path), 0o644)
        
        return str(secure_path)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (common in proxy setups)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def _cleanup_temp_file(self, temp_path: str):
        """Safely cleanup temporary file"""
        try:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
    
    def _create_security_error_response(self, report: FileSecurityReport) -> Dict[str, Any]:
        """Create detailed security error response"""
        return {
            "error": "File upload blocked by security validation",
            "threat_level": report.threat_level.value,
            "risk_score": report.risk_score,
            "security_errors": report.security_errors,
            "security_warnings": report.security_warnings,
            "recommendations": self.security_validator.get_security_recommendations(report),
            "scan_details": {
                "virus_scan": report.virus_scan_result.value,
                "content_analysis": report.content_analysis_result.value,
                "file_size": report.file_size,
                "mime_type": report.mime_type,
                "file_extension": report.file_extension,
            }
        }
    
    def _serialize_security_report(self, report: FileSecurityReport) -> Dict[str, Any]:
        """Serialize security report for JSON response"""
        return {
            "filename": report.filename,
            "file_size": report.file_size,
            "mime_type": report.mime_type,
            "file_extension": report.file_extension,
            "threat_level": report.threat_level.value,
            "risk_score": report.risk_score,
            "validation_results": {
                "magic_number_valid": report.magic_number_valid,
                "mime_type_valid": report.mime_type_valid,
                "file_size_valid": report.file_size_valid,
                "path_secure": report.path_secure,
                "content_secure": report.content_secure,
            },
            "scan_results": {
                "virus_scan": report.virus_scan_result.value,
                "content_analysis": report.content_analysis_result.value,
            },
            "security_errors": report.security_errors,
            "security_warnings": report.security_warnings,
            "scan_timestamp": report.scan_timestamp.isoformat(),
            "scan_duration_ms": report.scan_duration_ms,
            "file_hash": report.file_hash[:16] + "..." if len(report.file_hash) > 16 else report.file_hash,  # Truncate for response
        }

# Decorator for secure file upload endpoints
def secure_file_upload(
    max_file_size: int = 100 * 1024 * 1024,
    allowed_mime_types: Optional[list] = None
):
    """Decorator for FastAPI endpoints that handle file uploads"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Extract file and request from function arguments
            file = None
            request = None
            
            for arg in args:
                if isinstance(arg, UploadFile):
                    file = arg
                elif isinstance(arg, Request):
                    request = arg
            
            # Check kwargs as well
            if not file:
                file = kwargs.get('file')
            if not request:
                request = kwargs.get('request')
            
            if not file or not request:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Secure upload decorator requires file and request parameters"
                )
            
            # Run security validation
            middleware = SecureUploadMiddleware()
            validation_result = await middleware.validate_and_process_upload(
                file=file,
                request=request,
                max_file_size=max_file_size,
                allowed_mime_types=allowed_mime_types
            )
            
            # Add validation result to kwargs for the endpoint function
            kwargs['security_validation'] = validation_result
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

# Global middleware instance
secure_upload_middleware = SecureUploadMiddleware()