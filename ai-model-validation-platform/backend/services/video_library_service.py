from typing import Dict, List, Optional, Tuple
from pathlib import Path
import os
import uuid
import logging
from enum import Enum
from dataclasses import dataclass
from sqlalchemy.orm import Session
from models import Video, Project
from database import SessionLocal
import cv2
import shutil

logger = logging.getLogger(__name__)

class CameraType(Enum):
    FRONT_FACING_VRU = "front-facing-vru"
    REAR_FACING_VRU = "rear-facing-vru"
    IN_CAB_DRIVER_BEHAVIOR = "in-cab-driver-behavior"
    MULTI_ANGLE_SCENARIOS = "multi-angle-scenarios"

class VideoCategory(Enum):
    PEDESTRIAN_DETECTION = "pedestrian-detection"
    CYCLIST_DETECTION = "cyclist-detection"
    VEHICLE_DETECTION = "vehicle-detection"
    BACKUP_SCENARIOS = "backup-scenarios"
    PARKING_ASSISTANCE = "parking-assistance"
    DISTRACTION_DETECTION = "distraction-detection"
    DROWSINESS_MONITORING = "drowsiness-monitoring"
    INTERSECTION_ANALYSIS = "intersection-analysis"
    COMPLEX_ENVIRONMENTS = "complex-environments"

@dataclass
class VideoFilters:
    project_id: Optional[str] = None
    camera_type: Optional[CameraType] = None
    category: Optional[VideoCategory] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    resolution: Optional[str] = None
    status: Optional[str] = None

@dataclass
class VideoMetadata:
    duration: float
    fps: float
    resolution: Tuple[int, int]
    codec: str
    bitrate: int
    frame_count: int
    file_size: int
    creation_time: str
    quality_metrics: Dict

class VideoLibraryManager:
    """Centralized video lifecycle management with folder organization"""
    
    def __init__(self, base_upload_dir: str = "/app/uploads"):
        self.base_upload_dir = Path(base_upload_dir)
        self.setup_folder_structure()
    
    def setup_folder_structure(self):
        """Create the organized folder structure based on camera functions"""
        folder_structure = {
            "front-facing-vru": [
                "pedestrian-detection",
                "cyclist-detection", 
                "vehicle-detection"
            ],
            "rear-facing-vru": [
                "backup-scenarios",
                "parking-assistance"
            ],
            "in-cab-driver-behavior": [
                "distraction-detection",
                "drowsiness-monitoring"
            ],
            "multi-angle-scenarios": [
                "intersection-analysis",
                "complex-environments"
            ]
        }
        
        for camera_type, categories in folder_structure.items():
            camera_dir = self.base_upload_dir / camera_type
            camera_dir.mkdir(parents=True, exist_ok=True)
            
            for category in categories:
                category_dir = camera_dir / category
                category_dir.mkdir(exist_ok=True)
        
        logger.info(f"Video library folder structure created at {self.base_upload_dir}")
    
    def organize_by_camera_function(self, camera_view: str, category: Optional[str] = None) -> str:
        """Determine appropriate folder path based on camera function"""
        camera_type_mapping = {
            "Front-facing VRU": CameraType.FRONT_FACING_VRU,
            "Rear-facing VRU": CameraType.REAR_FACING_VRU,
            "In-Cab Driver Behavior": CameraType.IN_CAB_DRIVER_BEHAVIOR,
            "Multi-angle": CameraType.MULTI_ANGLE_SCENARIOS
        }
        
        camera_type = camera_type_mapping.get(camera_view, CameraType.FRONT_FACING_VRU)
        folder_path = self.base_upload_dir / camera_type.value
        
        # If specific category is provided, use it
        if category:
            folder_path = folder_path / category
        else:
            # Default categorization based on camera type
            if camera_type == CameraType.FRONT_FACING_VRU:
                folder_path = folder_path / "pedestrian-detection"
            elif camera_type == CameraType.REAR_FACING_VRU:
                folder_path = folder_path / "backup-scenarios"
            elif camera_type == CameraType.IN_CAB_DRIVER_BEHAVIOR:
                folder_path = folder_path / "distraction-detection"
            else:
                folder_path = folder_path / "intersection-analysis"
        
        folder_path.mkdir(parents=True, exist_ok=True)
        return str(folder_path)
    
    def upload_video(self, file_path: str, project_id: str, metadata: dict) -> Video:
        """Upload video with intelligent organization"""
        db = SessionLocal()
        try:
            # Get project to determine camera configuration
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Determine organized folder location
            organized_folder = self.organize_by_camera_function(
                project.camera_view, 
                metadata.get('category')
            )
            
            # Generate secure filename
            original_filename = Path(file_path).name
            secure_filename = f"{uuid.uuid4()}{Path(original_filename).suffix}"
            organized_path = Path(organized_folder) / secure_filename
            
            # Move file to organized location
            shutil.move(file_path, organized_path)
            
            # Extract video metadata
            video_metadata = self.extract_video_metadata(str(organized_path))
            
            # Create video record
            video = Video(
                filename=original_filename,
                file_path=str(organized_path),
                file_size=organized_path.stat().st_size,
                duration=video_metadata.duration if video_metadata else None,
                resolution=f"{video_metadata.resolution[0]}x{video_metadata.resolution[1]}" if video_metadata else None,
                fps=video_metadata.fps if video_metadata else None,
                project_id=project_id,
                status="uploaded"
            )
            
            db.add(video)
            db.commit()
            db.refresh(video)
            
            logger.info(f"Video {original_filename} organized to {organized_path}")
            return video
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error uploading video: {str(e)}")
            raise
        finally:
            db.close()
    
    def assign_to_project(self, video_id: str, project_id: str) -> bool:
        """Assign video to project with compatibility validation"""
        db = SessionLocal()
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            project = db.query(Project).filter(Project.id == project_id).first()
            
            if not video or not project:
                return False
            
            # Check compatibility
            if self.is_compatible(video, project):
                video.project_id = project_id
                db.commit()
                logger.info(f"Video {video_id} assigned to project {project_id}")
                return True
            else:
                logger.warning(f"Video {video_id} not compatible with project {project_id}")
                return False
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error assigning video to project: {str(e)}")
            return False
        finally:
            db.close()
    
    def is_compatible(self, video: Video, project: Project) -> bool:
        """Check compatibility between video and project"""
        # Resolution compatibility check
        if project.resolution and video.resolution:
            if project.resolution != video.resolution:
                return False
        
        # Frame rate compatibility check  
        if project.frame_rate and video.fps:
            fps_tolerance = 5  # 5 FPS tolerance
            if abs(project.frame_rate - video.fps) > fps_tolerance:
                return False
        
        return True
    
    def get_videos_by_criteria(self, filters: VideoFilters) -> List[Video]:
        """Get videos based on filtering criteria"""
        db = SessionLocal()
        try:
            query = db.query(Video)
            
            if filters.project_id:
                query = query.filter(Video.project_id == filters.project_id)
            
            if filters.status:
                query = query.filter(Video.status == filters.status)
            
            if filters.min_duration:
                query = query.filter(Video.duration >= filters.min_duration)
            
            if filters.max_duration:
                query = query.filter(Video.duration <= filters.max_duration)
            
            if filters.resolution:
                query = query.filter(Video.resolution == filters.resolution)
            
            return query.order_by(Video.created_at.desc()).all()
            
        except Exception as e:
            logger.error(f"Error filtering videos: {str(e)}")
            return []
        finally:
            db.close()
    
    def delete_video(self, video_id: str, cascade: bool = False) -> bool:
        """Delete video with optional cascade deletion"""
        db = SessionLocal()
        try:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return False
            
            # Delete physical file
            if video.file_path and os.path.exists(video.file_path):
                os.remove(video.file_path)
            
            # Delete database record (cascade handled by model relationships)
            db.delete(video)
            db.commit()
            
            logger.info(f"Video {video_id} deleted successfully")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting video: {str(e)}")
            return False
        finally:
            db.close()
    
    def extract_video_metadata(self, file_path: str) -> Optional[VideoMetadata]:
        """Extract comprehensive video metadata"""
        try:
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return None
            
            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            # Calculate duration
            duration = frame_count / fps if fps > 0 else 0
            
            # Get file size
            file_size = Path(file_path).stat().st_size
            
            # Estimate bitrate
            bitrate = int((file_size * 8) / duration) if duration > 0 else 0
            
            cap.release()
            
            # Quality assessment
            quality_metrics = self._assess_video_quality(file_path, width, height, fps)
            
            return VideoMetadata(
                duration=duration,
                fps=fps,
                resolution=(width, height),
                codec="H.264",  # Default assumption
                bitrate=bitrate,
                frame_count=frame_count,
                file_size=file_size,
                creation_time=Path(file_path).stat().st_ctime,
                quality_metrics=quality_metrics
            )
            
        except Exception as e:
            logger.error(f"Error extracting video metadata: {str(e)}")
            return None
    
    def _assess_video_quality(self, file_path: str, width: int, height: int, fps: float) -> Dict:
        """Assess video quality metrics"""
        quality_score = 0
        
        # Resolution score
        if width >= 1920 and height >= 1080:
            quality_score += 40
        elif width >= 1280 and height >= 720:
            quality_score += 30
        elif width >= 640 and height >= 480:
            quality_score += 20
        else:
            quality_score += 10
        
        # Frame rate score
        if fps >= 30:
            quality_score += 30
        elif fps >= 24:
            quality_score += 25
        elif fps >= 15:
            quality_score += 15
        else:
            quality_score += 5
        
        # Additional quality checks would go here
        quality_score += 30  # Placeholder for codec, bitrate, etc.
        
        return {
            "overall_score": min(quality_score, 100),
            "resolution_category": self._categorize_resolution(width, height),
            "frame_rate_category": self._categorize_frame_rate(fps),
            "suitable_for_detection": quality_score >= 60
        }
    
    def _categorize_resolution(self, width: int, height: int) -> str:
        """Categorize video resolution"""
        if width >= 3840 and height >= 2160:
            return "4K"
        elif width >= 1920 and height >= 1080:
            return "Full HD"
        elif width >= 1280 and height >= 720:
            return "HD"
        elif width >= 854 and height >= 480:
            return "SD"
        else:
            return "Low Resolution"
    
    def _categorize_frame_rate(self, fps: float) -> str:
        """Categorize video frame rate"""
        if fps >= 60:
            return "High FPS"
        elif fps >= 30:
            return "Standard FPS"
        elif fps >= 24:
            return "Cinema FPS"
        else:
            return "Low FPS"

class VideoUploadHandler:
    """Multi-format video ingestion with upload progress tracking"""
    
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv'}
    SUPPORTED_CODECS = {'H.264', 'H.265', 'Motion JPEG', 'x264'}
    
    def __init__(self, temp_dir: str = "/tmp/video_uploads"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
    
    async def validate_video_file(self, file_path: str) -> Dict:
        """Comprehensive video file validation"""
        try:
            file_path_obj = Path(file_path)
            
            # Check file extension
            if file_path_obj.suffix.lower() not in self.SUPPORTED_FORMATS:
                return {
                    "is_valid": False,
                    "errors": [f"Unsupported format: {file_path_obj.suffix}"]
                }
            
            # Check file size (max 10GB)
            max_size = 10 * 1024 * 1024 * 1024  # 10GB
            if file_path_obj.stat().st_size > max_size:
                return {
                    "is_valid": False,
                    "errors": ["File size exceeds 10GB limit"]
                }
            
            # Check video properties with OpenCV
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                return {
                    "is_valid": False,
                    "errors": ["Cannot open video file - corrupted or invalid format"]
                }
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            cap.release()
            
            errors = []
            
            # Check resolution (minimum 640x480, maximum 4K)
            if width < 640 or height < 480:
                errors.append("Resolution too low (minimum 640x480)")
            if width > 3840 or height > 2160:
                errors.append("Resolution too high (maximum 4K)")
            
            # Check frame rate (5-120 FPS)
            if fps < 5 or fps > 120:
                errors.append(f"Invalid frame rate: {fps} FPS (must be 5-120)")
            
            # Check duration (maximum 60 minutes)
            duration = frame_count / fps if fps > 0 else 0
            if duration > 3600:  # 60 minutes
                errors.append("Video too long (maximum 60 minutes)")
            
            return {
                "is_valid": len(errors) == 0,
                "errors": errors,
                "metadata": {
                    "duration": duration,
                    "fps": fps,
                    "resolution": (width, height),
                    "frame_count": frame_count
                }
            }
            
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"Validation error: {str(e)}"]
            }
    
    def scan_for_security_threats(self, file_path: str) -> Dict:
        """Basic security scanning for video files"""
        # This is a placeholder for security scanning
        # In production, integrate with antivirus/malware detection
        
        file_size = Path(file_path).stat().st_size
        
        # Basic heuristics
        threats = []
        
        # Check for suspicious file size patterns
        if file_size < 1024:  # Less than 1KB
            threats.append("Suspiciously small file size")
        
        # Check for executable content (basic check)
        with open(file_path, 'rb') as f:
            header = f.read(1024)
            if b'MZ' in header or b'PE' in header:
                threats.append("Contains executable content")
        
        return {
            "is_safe": len(threats) == 0,
            "threats": threats
        }

class VideoThumbnailGenerator:
    """Video thumbnail and preview generation"""
    
    def __init__(self, thumbnail_dir: str = "/app/thumbnails"):
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(exist_ok=True)
    
    def generate_thumbnail(self, video_path: str, video_id: str) -> str:
        """Generate thumbnail from video middle frame"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError("Cannot open video file")
            
            # Get middle frame
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame = frame_count // 2
            
            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                raise ValueError("Cannot read frame from video")
            
            # Resize to thumbnail size (320x240)
            thumbnail = cv2.resize(frame, (320, 240))
            
            # Save thumbnail
            thumbnail_path = self.thumbnail_dir / f"{video_id}_thumbnail.jpg"
            cv2.imwrite(str(thumbnail_path), thumbnail)
            
            logger.info(f"Thumbnail generated: {thumbnail_path}")
            return str(thumbnail_path)
            
        except Exception as e:
            logger.error(f"Error generating thumbnail: {str(e)}")
            return None
    
    def generate_preview_frames(self, video_path: str, video_id: str, frame_count: int = 9) -> List[str]:
        """Generate multiple preview frames from video"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError("Cannot open video file")
            
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_interval = total_frames // (frame_count + 1)
            
            preview_paths = []
            
            for i in range(1, frame_count + 1):
                frame_pos = i * frame_interval
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                ret, frame = cap.read()
                
                if ret:
                    # Resize preview frame
                    preview_frame = cv2.resize(frame, (160, 120))
                    
                    # Save preview frame
                    preview_path = self.thumbnail_dir / f"{video_id}_preview_{i}.jpg"
                    cv2.imwrite(str(preview_path), preview_frame)
                    preview_paths.append(str(preview_path))
            
            cap.release()
            
            logger.info(f"Generated {len(preview_paths)} preview frames for video {video_id}")
            return preview_paths
            
        except Exception as e:
            logger.error(f"Error generating preview frames: {str(e)}")
            return []