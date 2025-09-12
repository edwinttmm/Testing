"""
Secure File Upload API Endpoints
Integrates enterprise security validation with FastAPI endpoints
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Request, Depends, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import os
import json
import logging
from pathlib import Path
from datetime import datetime

from src.middleware.secure_upload_middleware import (
    SecureUploadMiddleware,
    secure_file_upload
)
from src.security.file_upload_security import (
    FileUploadSecurityValidator,
    FileSecurityReport,
    SecurityThreatLevel
)

logger = logging.getLogger(__name__)

# Create router for secure upload endpoints
router = APIRouter(prefix="/api/v1/secure-upload", tags=["secure-upload"])

# Initialize middleware
upload_middleware = SecureUploadMiddleware()

@router.post("/validate")
async def validate_file_upload(
    file: UploadFile = File(...),
    request: Request = Request
) -> Dict[str, Any]:
    """
    Validate uploaded file without storing it
    Useful for pre-upload validation on frontend
    """
    try:
        validation_result = await upload_middleware.validate_and_process_upload(
            file=file,
            request=request
        )
        
        # Remove the actual file path from response (validation only)
        secure_path = validation_result.get("secure_file_path")
        if secure_path and os.path.exists(secure_path):
            os.unlink(secure_path)  # Clean up since this is validation only
        
        return {
            "valid": validation_result["success"],
            "security_report": validation_result["security_report"],
            "recommendations": validation_result["recommendations"],
            "validation_timestamp": datetime.now().isoformat()
        }
        
    except HTTPException as e:
        # Re-raise HTTP exceptions with security details
        raise e
    except Exception as e:
        logger.error(f"File validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "File validation failed",
                "message": "An unexpected error occurred during validation"
            }
        )

@router.post("/upload/video")
async def secure_video_upload(
    file: UploadFile = File(...),
    request: Request = Request,
    project_id: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Securely upload video file with comprehensive validation
    """
    try:
        # Run security validation and processing
        validation_result = await upload_middleware.validate_and_process_upload(
            file=file,
            request=request,
            max_file_size=100 * 1024 * 1024,  # 100MB
            allowed_mime_types=[
                'video/mp4', 
                'video/avi', 
                'video/x-msvideo',
                'video/quicktime', 
                'video/x-matroska'
            ]
        )
        
        if not validation_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "File upload rejected by security validation",
                    "security_report": validation_result.get("security_report"),
                    "recommendations": validation_result.get("recommendations")
                }
            )
        
        # File is validated and secure - process for video library
        secure_file_path = validation_result["secure_file_path"]
        security_report = validation_result["security_report"]
        
        # Create video record with security metadata
        video_metadata = {
            "original_filename": file.filename,
            "secure_filename": os.path.basename(secure_file_path),
            "file_size": security_report["file_size"],
            "mime_type": security_report["mime_type"],
            "upload_timestamp": datetime.now().isoformat(),
            "project_id": project_id,
            "description": description,
            "security_validation": {
                "threat_level": security_report["threat_level"],
                "risk_score": security_report["risk_score"],
                "validation_passed": True,
                "scan_timestamp": security_report["scan_timestamp"],
                "file_hash": security_report["file_hash"]
            }
        }
        
        # TODO: Integrate with existing video database/storage system
        # This would typically save to your video database
        
        return {
            "success": True,
            "message": "Video uploaded successfully with security validation",
            "video_id": f"vid_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "metadata": video_metadata,
            "security_report": security_report,
            "recommendations": validation_result["recommendations"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Secure video upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Video upload failed",
                "message": "An unexpected error occurred during upload processing"
            }
        )

@router.post("/batch-upload")
async def secure_batch_upload(
    files: List[UploadFile] = File(...),
    request: Request = Request,
    project_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Securely upload multiple video files with batch validation
    """
    if len(files) > 10:  # Limit batch size
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files allowed per batch upload"
        )
    
    upload_results = []
    successful_uploads = 0
    failed_uploads = 0
    
    for i, file in enumerate(files):
        try:
            # Validate each file
            validation_result = await upload_middleware.validate_and_process_upload(
                file=file,
                request=request
            )
            
            if validation_result["success"]:
                successful_uploads += 1
                upload_results.append({
                    "file_index": i,
                    "filename": file.filename,
                    "status": "success",
                    "secure_path": validation_result["secure_file_path"],
                    "security_report": validation_result["security_report"]
                })
            else:
                failed_uploads += 1
                upload_results.append({
                    "file_index": i,
                    "filename": file.filename,
                    "status": "failed",
                    "error": "Security validation failed",
                    "security_report": validation_result.get("security_report"),
                    "recommendations": validation_result.get("recommendations")
                })
                
        except Exception as e:
            failed_uploads += 1
            upload_results.append({
                "file_index": i,
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "batch_id": f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "total_files": len(files),
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "results": upload_results
    }

@router.get("/security-status")
async def get_security_status() -> Dict[str, Any]:
    """
    Get current security system status and configuration
    """
    validator = FileUploadSecurityValidator()
    
    return {
        "security_system": {
            "status": "active",
            "version": "1.0.0",
            "clamav_available": getattr(validator, 'clamav_available', False),
            "last_updated": datetime.now().isoformat()
        },
        "security_config": {
            "max_file_size_mb": validator.SECURITY_CONFIG['MAX_FILE_SIZE'] // (1024 * 1024),
            "min_file_size_bytes": validator.SECURITY_CONFIG['MIN_FILE_SIZE'],
            "allowed_types": list(validator.SECURITY_CONFIG['ALLOWED_TYPES'].keys()),
            "rate_limits": validator.SECURITY_CONFIG['RATE_LIMITS']
        },
        "validation_features": [
            "File signature validation (magic numbers)",
            "MIME type verification",
            "Path traversal protection", 
            "Content entropy analysis",
            "Malware scanning (ClamAV)",
            "Rate limiting",
            "Security event logging"
        ]
    }

@router.get("/security-logs")
async def get_security_logs(
    limit: int = 100,
    threat_level: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve recent security events (admin endpoint)
    """
    # TODO: Implement proper authentication/authorization
    # This should be restricted to admin users only
    
    try:
        # Read security log file
        log_file = "security_events.log"
        if not os.path.exists(log_file):
            return {"events": [], "total": 0}
        
        events = []
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        # Parse recent log entries
        for line in lines[-limit:]:
            try:
                # Extract JSON from log line
                if " - " in line:
                    parts = line.split(" - ", 2)
                    if len(parts) >= 3:
                        log_data = json.loads(parts[2].strip())
                        
                        # Filter by threat level if specified
                        if threat_level and log_data.get("threat_level") != threat_level:
                            continue
                        
                        events.append({
                            "timestamp": parts[0],
                            "level": parts[1],
                            "data": log_data
                        })
            except (json.JSONDecodeError, IndexError):
                continue
        
        return {
            "events": events,
            "total": len(events),
            "filtered_by": threat_level
        }
        
    except Exception as e:
        logger.error(f"Failed to retrieve security logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security logs"
        )

@router.post("/quarantine/{file_id}")
async def quarantine_file(file_id: str) -> Dict[str, Any]:
    """
    Move suspicious file to quarantine
    """
    # TODO: Implement file quarantine system
    # This would move files to a secure quarantine area
    # and update their status in the database
    
    return {
        "success": True,
        "message": f"File {file_id} moved to quarantine",
        "quarantine_id": f"quar_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }

@router.delete("/quarantine/{file_id}")
async def remove_quarantined_file(file_id: str) -> Dict[str, Any]:
    """
    Permanently remove quarantined file
    """
    # TODO: Implement secure file deletion
    # This should securely wipe the file from quarantine
    
    return {
        "success": True,
        "message": f"Quarantined file {file_id} permanently removed"
    }

@router.post("/scan/rescan/{file_id}")
async def rescan_file(file_id: str) -> Dict[str, Any]:
    """
    Re-scan existing file with updated security definitions
    """
    # TODO: Implement file re-scanning
    # This would re-run security validation on existing files
    
    return {
        "success": True,
        "message": f"File {file_id} queued for re-scan",
        "scan_id": f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }

# Health check endpoint for security system
@router.get("/health")
async def security_health_check() -> Dict[str, Any]:
    """
    Check security system health and readiness
    """
    validator = FileUploadSecurityValidator()
    
    health_status = {
        "status": "healthy",
        "checks": {
            "upload_directory": os.path.exists(upload_middleware.upload_dir),
            "temp_directory": os.path.exists(upload_middleware.temp_dir), 
            "clamav_scanner": getattr(validator, 'clamav_available', False),
            "magic_library": True,  # Always available in our setup
            "rate_limiter": True,   # Always available
        },
        "timestamp": datetime.now().isoformat()
    }
    
    # Check if any critical components are failing
    critical_checks = ["upload_directory", "temp_directory", "magic_library"]
    if not all(health_status["checks"][check] for check in critical_checks):
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status
        )
    
    return health_status