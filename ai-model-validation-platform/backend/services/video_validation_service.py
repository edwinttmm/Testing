"""
Video File Validation Service
Provides robust video file validation including structure checks, corruption detection, and metadata extraction.
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class VideoValidationService:
    """Service for comprehensive video file validation"""
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv'}
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MIN_FILE_SIZE = 1024  # 1KB minimum
    
    def __init__(self):
        self.validation_cache = {}
    
    def validate_video_file(self, file_path: str) -> Dict[str, Any]:
        """
        Comprehensive video file validation
        
        Args:
            file_path: Path to the video file
            
        Returns:
            dict: Validation result with status, metadata, and error details
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "metadata": None,
            "file_info": {}
        }
        
        try:
            # Basic file existence and size checks
            if not os.path.exists(file_path):
                result["errors"].append("File does not exist")
                return result
            
            file_size = os.path.getsize(file_path)
            result["file_info"]["size"] = file_size
            
            if file_size < self.MIN_FILE_SIZE:
                result["errors"].append(f"File too small (minimum {self.MIN_FILE_SIZE} bytes)")
                return result
                
            if file_size > self.MAX_FILE_SIZE:
                result["errors"].append(f"File too large (maximum {self.MAX_FILE_SIZE / (1024*1024):.1f} MB)")
                return result
            
            # File extension validation
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.SUPPORTED_FORMATS:
                result["errors"].append(f"Unsupported format: {file_ext}. Supported: {', '.join(self.SUPPORTED_FORMATS)}")
                return result
            
            # Video structure validation using OpenCV
            validation_result = self._validate_video_structure(file_path)
            if not validation_result["valid"]:
                result["errors"].extend(validation_result["errors"])
                result["warnings"].extend(validation_result.get("warnings", []))
                return result
            
            # If we get here, the video is valid
            result["valid"] = True
            result["metadata"] = validation_result["metadata"]
            result["file_info"]["format"] = file_ext
            
            logger.info(f"Video validation successful: {file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Video validation error for {file_path}: {e}")
            result["errors"].append(f"Validation failed: {str(e)}")
            return result
    
    def _validate_video_structure(self, file_path: str) -> Dict[str, Any]:
        """
        Validate video file structure and extract metadata
        
        Args:
            file_path: Path to video file
            
        Returns:
            dict: Structure validation result
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "metadata": {}
        }
        
        try:
            import cv2
            
            # Attempt to open video file
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                result["errors"].append("Cannot open video file - file may be corrupted or format unsupported")
                return result
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Validate basic properties
            if fps <= 0:
                result["errors"].append("Invalid frame rate detected")
                cap.release()
                return result
            
            if width <= 0 or height <= 0:
                result["errors"].append("Invalid video dimensions detected")
                cap.release()
                return result
            
            if frame_count <= 0:
                result["warnings"].append("Frame count could not be determined")
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 and frame_count > 0 else None
            
            # Try to read first few frames to verify structure
            valid_frames = 0
            test_frames = min(5, int(frame_count) if frame_count > 0 else 5)
            
            for i in range(test_frames):
                ret, frame = cap.read()
                if ret and frame is not None:
                    valid_frames += 1
                else:
                    break
            
            cap.release()
            
            if valid_frames == 0:
                result["errors"].append("No valid frames found - video may be corrupted")
                return result
            
            if valid_frames < test_frames:
                result["warnings"].append(f"Some frames could not be read ({valid_frames}/{test_frames})")
            
            # Video is structurally valid
            result["valid"] = True
            result["metadata"] = {
                "duration": duration,
                "fps": fps,
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}",
                "frame_count": int(frame_count) if frame_count > 0 else None,
                "valid_frames_tested": valid_frames
            }
            
            return result
            
        except ImportError:
            logger.warning("OpenCV not available, skipping detailed video validation")
            result["warnings"].append("Advanced validation skipped (OpenCV not available)")
            result["valid"] = True  # Allow file through with warning
            return result
            
        except Exception as e:
            logger.error(f"Video structure validation error: {e}")
            result["errors"].append(f"Structure validation failed: {str(e)}")
            return result
    
    def validate_upload_file(self, file, expected_filename: str) -> Dict[str, Any]:
        """
        Validate uploaded file before processing
        
        Args:
            file: UploadFile object
            expected_filename: Expected filename
            
        Returns:
            dict: Validation result
        """
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "secure_filename": None,
            "file_extension": None
        }
        
        try:
            # Validate filename
            if not file.filename or not file.filename.strip():
                result["errors"].append("Filename is required")
                return result
            
            # Check file extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in self.SUPPORTED_FORMATS:
                result["errors"].append(f"Unsupported file format: {file_ext}")
                return result
            
            # Generate secure filename
            import uuid
            secure_filename = f"{uuid.uuid4()}{file_ext}"
            
            result["valid"] = True
            result["secure_filename"] = secure_filename
            result["file_extension"] = file_ext
            
            return result
            
        except Exception as e:
            logger.error(f"Upload file validation error: {e}")
            result["errors"].append(f"Upload validation failed: {str(e)}")
            return result
    
    def create_temp_file_safely(self, file_extension: str, upload_dir: str) -> Tuple[str, str]:
        """
        Create a temporary file safely for upload processing
        
        Args:
            file_extension: File extension (e.g., '.mp4')
            upload_dir: Upload directory
            
        Returns:
            tuple: (temp_file_path, final_file_path)
        """
        import uuid
        
        # Generate secure filename for final destination
        secure_filename = f"{uuid.uuid4()}{file_extension}"
        final_file_path = os.path.join(upload_dir, secure_filename)
        
        # Generate temporary filename (don't create the file yet)
        temp_filename = f"upload_{uuid.uuid4()}{file_extension}"
        temp_file_path = os.path.join(upload_dir, temp_filename)
        
        return temp_file_path, final_file_path
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """
        Safely cleanup temporary file
        
        Args:
            temp_file_path: Path to temporary file
        """
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temp file: {temp_file_path}")
        except OSError as e:
            logger.warning(f"Could not clean up temp file {temp_file_path}: {e}")

# Global instance
video_validation_service = VideoValidationService()