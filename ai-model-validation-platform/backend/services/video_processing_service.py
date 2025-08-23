"""
Enhanced Video Processing Service with Error Handling and Validation

This service provides comprehensive video processing capabilities with:
- Safe video validation
- Enhanced error handling
- Progress tracking
- Resource management
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import cv2
from datetime import datetime

logger = logging.getLogger(__name__)

class VideoProcessingService:
    """Enhanced video processing service with comprehensive error handling"""
    
    def __init__(self):
        self.processing_tasks: Dict[str, Dict[str, Any]] = {}
        
    async def process_video_safely(self, video_path: str, video_id: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process video with comprehensive error handling and validation
        
        Args:
            video_path: Path to video file
            video_id: Unique video identifier
            config: Processing configuration
            
        Returns:
            Dict containing processing results and status
        """
        try:
            logger.info(f"Starting safe video processing for {video_id}")
            
            # Phase 1: Validate video file integrity
            is_valid, validation_message = self.validate_video_integrity(video_path)
            if not is_valid:
                logger.warning(f"Video validation failed for {video_id}: {validation_message}")
                return {
                    "status": "failed",
                    "error": f"Video validation failed: {validation_message}",
                    "video_id": video_id,
                    "processed_at": datetime.utcnow().isoformat()
                }
            
            # Phase 2: Extract comprehensive metadata
            metadata = await self.extract_enhanced_metadata(video_path)
            if not metadata:
                return {
                    "status": "failed",
                    "error": "Failed to extract video metadata",
                    "video_id": video_id,
                    "processed_at": datetime.utcnow().isoformat()
                }
            
            # Phase 3: Process with error recovery
            processing_result = await self.process_with_recovery(video_path, video_id, config or {})
            
            # Phase 4: Combine results
            result = {
                "status": "completed" if processing_result.get("success") else "failed",
                "video_id": video_id,
                "metadata": metadata,
                "processing_result": processing_result,
                "processed_at": datetime.utcnow().isoformat()
            }
            
            if processing_result.get("error"):
                result["error"] = processing_result["error"]
            
            logger.info(f"Completed safe video processing for {video_id}: {result['status']}")
            return result
            
        except Exception as e:
            logger.error(f"Critical error in video processing for {video_id}: {e}", exc_info=True)
            return {
                "status": "failed",
                "error": f"Critical processing error: {str(e)}",
                "video_id": video_id,
                "processed_at": datetime.utcnow().isoformat()
            }
    
    def validate_video_integrity(self, video_path: str) -> Tuple[bool, str]:
        """
        Comprehensive video file integrity validation
        
        Args:
            video_path: Path to video file
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            # Basic file checks
            if not os.path.exists(video_path):
                return False, "Video file does not exist"
            
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                return False, "Video file is empty"
            
            if file_size < 1024:  # Less than 1KB
                return False, "Video file is too small to be valid"
            
            # OpenCV validation
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return False, "Could not open video file - invalid format or corrupted"
            
            try:
                # Check frame count
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if frame_count == 0:
                    return False, "Video contains no frames"
                
                # Check basic properties
                fps = cap.get(cv2.CAP_PROP_FPS)
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                if fps <= 0:
                    return False, "Invalid frame rate"
                    
                if width <= 0 or height <= 0:
                    return False, "Invalid video dimensions"
                
                # Test frame reading
                ret, frame = cap.read()
                if not ret or frame is None:
                    return False, "Cannot read video frames - codec may be unsupported"
                
                if frame.size == 0:
                    return False, "Video frames contain no data"
                
                # Test multiple frames for consistency
                frames_tested = 0
                max_test_frames = min(5, frame_count - 1)
                
                for _ in range(max_test_frames):
                    ret, frame = cap.read()
                    if ret:
                        frames_tested += 1
                    else:
                        break
                
                cap.release()
                
                if frames_tested == 0 and frame_count > 1:
                    return False, "Could not read multiple frames - video may be corrupted"
                
                return True, f"Video is valid ({frame_count} frames, {fps:.1f}fps, {width}x{height})"
                
            except Exception as read_error:
                cap.release()
                return False, f"Error reading video data: {str(read_error)}"
                
        except ImportError:
            return False, "OpenCV not available for video validation"
        except Exception as e:
            return False, f"Video validation failed: {str(e)}"
    
    async def extract_enhanced_metadata(self, video_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract enhanced video metadata with error handling
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dictionary with video metadata or None if extraction fails
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Could not open video file for metadata extraction: {video_path}")
                return None
            
            # Basic properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 else None
            
            # File information
            file_size = os.path.getsize(video_path)
            file_name = os.path.basename(video_path)
            
            # Enhanced metadata
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec_name = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            
            cap.release()
            
            metadata = {
                "file_name": file_name,
                "file_size": file_size,
                "duration": duration,
                "fps": fps,
                "frame_count": frame_count,
                "width": width,
                "height": height,
                "resolution": f"{width}x{height}",
                "codec": codec_name,
                "aspect_ratio": round(width / height, 2) if height > 0 else None,
                "extracted_at": datetime.utcnow().isoformat(),
                "validation_passed": True
            }
            
            logger.info(f"Successfully extracted metadata for {file_name}: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to extract metadata from {video_path}: {e}")
            return None
    
    async def process_with_recovery(self, video_path: str, video_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process video with error recovery mechanisms
        
        Args:
            video_path: Path to video file
            video_id: Video identifier
            config: Processing configuration
            
        Returns:
            Dictionary with processing results
        """
        max_retries = config.get("max_retries", 2)
        retry_delay = config.get("retry_delay", 1.0)
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Processing attempt {attempt + 1} for video {video_id}")
                
                # Core processing logic
                result = await self.core_video_processing(video_path, video_id, config)
                
                if result.get("success"):
                    logger.info(f"Video processing succeeded on attempt {attempt + 1}")
                    return result
                else:
                    logger.warning(f"Processing failed on attempt {attempt + 1}: {result.get('error')}")
                    
                    if attempt < max_retries:
                        logger.info(f"Retrying in {retry_delay} seconds...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"Processing attempt {attempt + 1} failed with exception: {e}")
                
                if attempt < max_retries:
                    logger.info(f"Retrying after exception in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {
                        "success": False,
                        "error": f"All processing attempts failed. Last error: {str(e)}",
                        "attempts": attempt + 1
                    }
        
        return {
            "success": False,
            "error": f"Processing failed after {max_retries + 1} attempts",
            "attempts": max_retries + 1
        }
    
    async def core_video_processing(self, video_path: str, video_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Core video processing implementation
        
        Args:
            video_path: Path to video file
            video_id: Video identifier
            config: Processing configuration
            
        Returns:
            Dictionary with processing results
        """
        try:
            # This is where actual video processing would occur
            # For now, we'll simulate processing with validation
            
            # Verify file can still be read
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {
                    "success": False,
                    "error": "Could not open video file for processing"
                }
            
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            processed_frames = 0
            
            # Simulate frame-by-frame processing with error checking
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                processed_frames += 1
                
                # Check for processing cancellation or resource limits
                if processed_frames > config.get("max_frames", 10000):
                    logger.warning(f"Processing stopped at frame limit: {processed_frames}")
                    break
            
            cap.release()
            
            if processed_frames == 0:
                return {
                    "success": False,
                    "error": "No frames could be processed"
                }
            
            return {
                "success": True,
                "processed_frames": processed_frames,
                "total_frames": frame_count,
                "processing_completion": (processed_frames / frame_count) * 100 if frame_count > 0 else 0
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Core processing error: {str(e)}"
            }
    
    def get_processing_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get current processing status for a video"""
        return self.processing_tasks.get(video_id)
    
    def cleanup_processing_task(self, video_id: str) -> bool:
        """Clean up processing task resources"""
        if video_id in self.processing_tasks:
            del self.processing_tasks[video_id]
            return True
        return False

# Global instance
video_processing_service = VideoProcessingService()