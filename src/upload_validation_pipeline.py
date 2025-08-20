"""
Enhanced File Validation and Processing Pipeline
Provides comprehensive file validation, virus scanning, format verification,
and metadata extraction for uploaded video files.
"""

import os
import asyncio
import hashlib
import mimetypes
import subprocess
import json
import tempfile
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import magic
import cv2
import aiofiles
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """File validation status"""
    PENDING = "pending"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"
    QUARANTINED = "quarantined"
    WARNING = "warning"


class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, error_code: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


@dataclass
class FileMetadata:
    """File metadata structure"""
    filename: str
    file_size: int
    mime_type: str
    file_extension: str
    hash_md5: str
    hash_sha256: str
    created_at: datetime
    modified_at: Optional[datetime] = None
    
    # Video-specific metadata
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[int] = None
    codec: Optional[str] = None
    format: Optional[str] = None
    frame_count: Optional[int] = None
    
    # Additional metadata
    exif_data: Optional[Dict] = None
    custom_metadata: Optional[Dict] = None


@dataclass
class ValidationResult:
    """File validation result"""
    file_path: str
    status: ValidationStatus
    metadata: Optional[FileMetadata] = None
    errors: List[Dict] = None
    warnings: List[Dict] = None
    processing_time: float = 0.0
    validation_timestamp: datetime = None
    virus_scan_result: Optional[Dict] = None
    content_analysis: Optional[Dict] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.validation_timestamp is None:
            self.validation_timestamp = datetime.utcnow()


class FileValidator:
    """Comprehensive file validation system"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or self._get_default_config()
        self.magic_mime = magic.Magic(mime=True)
        self.magic_type = magic.Magic(mime=False)
        
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default validation configuration"""
        return {
            # File size limits (in bytes)
            'max_file_size': 500 * 1024 * 1024,  # 500MB
            'min_file_size': 1024,  # 1KB
            
            # Allowed file types
            'allowed_extensions': ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v', '.flv'],
            'allowed_mime_types': [
                'video/mp4',
                'video/avi',
                'video/quicktime',
                'video/x-msvideo',
                'video/webm',
                'video/x-matroska',
                'video/x-flv'
            ],
            
            # Video constraints
            'max_duration': 7200,  # 2 hours in seconds
            'min_duration': 1,     # 1 second
            'max_resolution': (4096, 2160),  # 4K
            'min_resolution': (320, 240),
            'max_fps': 120,
            'min_fps': 1,
            'max_bitrate': 50_000_000,  # 50 Mbps
            
            # Security settings
            'enable_virus_scan': False,
            'enable_content_analysis': True,
            'quarantine_suspicious_files': True,
            'deep_inspection_enabled': True,
            
            # Processing settings
            'extract_metadata': True,
            'validate_integrity': True,
            'generate_thumbnail': False,
            'analyze_codec_compatibility': True,
            
            # Performance settings
            'max_processing_time': 300,  # 5 minutes
            'concurrent_validations': 5,
        }

    async def validate_file(self, file_path: str, additional_checks: List[str] = None) -> ValidationResult:
        """
        Comprehensive file validation
        
        Args:
            file_path: Path to the file to validate
            additional_checks: List of additional validation checks to perform
            
        Returns:
            ValidationResult with detailed validation information
        """
        start_time = asyncio.get_event_loop().time()
        result = ValidationResult(
            file_path=file_path,
            status=ValidationStatus.VALIDATING
        )
        
        try:
            logger.info(f"Starting validation for file: {file_path}")
            
            # Basic file checks
            await self._validate_file_exists(file_path, result)
            await self._validate_file_size(file_path, result)
            await self._validate_file_type(file_path, result)
            
            # Extract metadata
            if self.config['extract_metadata']:
                result.metadata = await self._extract_metadata(file_path)
            
            # Content validation
            if self.config['enable_content_analysis']:
                await self._validate_content(file_path, result)
            
            # Video-specific validation
            await self._validate_video_properties(file_path, result)
            
            # Security checks
            if self.config['enable_virus_scan']:
                await self._scan_for_viruses(file_path, result)
            
            # Deep inspection
            if self.config['deep_inspection_enabled']:
                await self._deep_file_inspection(file_path, result)
            
            # Additional custom checks
            if additional_checks:
                await self._run_additional_checks(file_path, result, additional_checks)
            
            # Determine final status
            if result.errors:
                result.status = ValidationStatus.FAILED
            elif result.warnings:
                result.status = ValidationStatus.WARNING
            else:
                result.status = ValidationStatus.PASSED
                
            logger.info(f"Validation completed for {file_path}: {result.status.value}")
            
        except Exception as e:
            logger.error(f"Validation failed for {file_path}: {e}")
            result.status = ValidationStatus.FAILED
            result.errors.append({
                'error_code': 'VALIDATION_EXCEPTION',
                'message': f"Validation exception: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            })
        
        finally:
            result.processing_time = asyncio.get_event_loop().time() - start_time
            
        return result

    async def _validate_file_exists(self, file_path: str, result: ValidationResult):
        """Validate file exists and is accessible"""
        if not os.path.exists(file_path):
            result.errors.append({
                'error_code': 'FILE_NOT_FOUND',
                'message': f"File not found: {file_path}",
                'timestamp': datetime.utcnow().isoformat()
            })
            return
            
        if not os.path.isfile(file_path):
            result.errors.append({
                'error_code': 'NOT_A_FILE',
                'message': f"Path is not a file: {file_path}",
                'timestamp': datetime.utcnow().isoformat()
            })
            return
            
        if not os.access(file_path, os.R_OK):
            result.errors.append({
                'error_code': 'FILE_NOT_READABLE',
                'message': f"File is not readable: {file_path}",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _validate_file_size(self, file_path: str, result: ValidationResult):
        """Validate file size is within acceptable limits"""
        try:
            file_size = os.path.getsize(file_path)
            
            if file_size < self.config['min_file_size']:
                result.errors.append({
                    'error_code': 'FILE_TOO_SMALL',
                    'message': f"File size ({file_size} bytes) is below minimum ({self.config['min_file_size']} bytes)",
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            if file_size > self.config['max_file_size']:
                result.errors.append({
                    'error_code': 'FILE_TOO_LARGE',
                    'message': f"File size ({file_size} bytes) exceeds maximum ({self.config['max_file_size']} bytes)",
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except OSError as e:
            result.errors.append({
                'error_code': 'SIZE_CHECK_FAILED',
                'message': f"Could not determine file size: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _validate_file_type(self, file_path: str, result: ValidationResult):
        """Validate file type and extension"""
        try:
            # Check file extension
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in self.config['allowed_extensions']:
                result.errors.append({
                    'error_code': 'INVALID_EXTENSION',
                    'message': f"File extension '{file_ext}' not allowed. Allowed: {self.config['allowed_extensions']}",
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Check MIME type using magic
            mime_type = self.magic_mime.from_file(file_path)
            if mime_type not in self.config['allowed_mime_types']:
                result.warnings.append({
                    'warning_code': 'UNEXPECTED_MIME_TYPE',
                    'message': f"Unexpected MIME type '{mime_type}'. Expected: {self.config['allowed_mime_types']}",
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Check file signature
            file_type = self.magic_type.from_file(file_path)
            if 'video' not in file_type.lower() and 'media' not in file_type.lower():
                result.warnings.append({
                    'warning_code': 'UNEXPECTED_FILE_TYPE',
                    'message': f"File type signature '{file_type}' doesn't match expected video format",
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            result.errors.append({
                'error_code': 'TYPE_CHECK_FAILED',
                'message': f"File type validation failed: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _extract_metadata(self, file_path: str) -> FileMetadata:
        """Extract comprehensive file metadata"""
        try:
            # Basic file metadata
            stat = os.stat(file_path)
            file_size = stat.st_size
            created_at = datetime.fromtimestamp(stat.st_ctime)
            modified_at = datetime.fromtimestamp(stat.st_mtime)
            
            # Calculate file hashes
            hash_md5, hash_sha256 = await self._calculate_file_hashes(file_path)
            
            # Get MIME type
            mime_type = self.magic_mime.from_file(file_path)
            
            metadata = FileMetadata(
                filename=os.path.basename(file_path),
                file_size=file_size,
                mime_type=mime_type,
                file_extension=Path(file_path).suffix.lower(),
                hash_md5=hash_md5,
                hash_sha256=hash_sha256,
                created_at=created_at,
                modified_at=modified_at
            )
            
            # Extract video metadata using ffprobe
            video_metadata = await self._extract_video_metadata(file_path)
            if video_metadata:
                metadata.duration = video_metadata.get('duration')
                metadata.width = video_metadata.get('width')
                metadata.height = video_metadata.get('height')
                metadata.fps = video_metadata.get('fps')
                metadata.bitrate = video_metadata.get('bitrate')
                metadata.codec = video_metadata.get('codec')
                metadata.format = video_metadata.get('format')
                metadata.frame_count = video_metadata.get('frame_count')
            
            return metadata
            
        except Exception as e:
            logger.error(f"Metadata extraction failed for {file_path}: {e}")
            raise ValidationError(
                f"Could not extract metadata: {str(e)}",
                "METADATA_EXTRACTION_FAILED",
                {'file_path': file_path}
            )

    async def _calculate_file_hashes(self, file_path: str) -> Tuple[str, str]:
        """Calculate MD5 and SHA256 hashes of the file"""
        hash_md5 = hashlib.md5()
        hash_sha256 = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_md5.update(chunk)
                hash_sha256.update(chunk)
        
        return hash_md5.hexdigest(), hash_sha256.hexdigest()

    async def _extract_video_metadata(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Extract video metadata using ffprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"ffprobe failed for {file_path}: {stderr.decode()}")
                return None
            
            data = json.loads(stdout.decode())
            
            # Find video stream
            video_stream = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_stream = stream
                    break
            
            if not video_stream:
                logger.warning(f"No video stream found in {file_path}")
                return None
            
            # Extract metadata
            metadata = {}
            
            # Duration
            duration = data.get('format', {}).get('duration')
            if duration:
                metadata['duration'] = float(duration)
            
            # Dimensions
            metadata['width'] = video_stream.get('width')
            metadata['height'] = video_stream.get('height')
            
            # Frame rate
            fps_str = video_stream.get('r_frame_rate', '0/1')
            if '/' in fps_str:
                num, den = fps_str.split('/')
                if int(den) != 0:
                    metadata['fps'] = int(num) / int(den)
            
            # Bitrate
            bitrate = video_stream.get('bit_rate') or data.get('format', {}).get('bit_rate')
            if bitrate:
                metadata['bitrate'] = int(bitrate)
            
            # Codec
            metadata['codec'] = video_stream.get('codec_name')
            
            # Format
            metadata['format'] = data.get('format', {}).get('format_name')
            
            # Frame count
            nb_frames = video_stream.get('nb_frames')
            if nb_frames:
                metadata['frame_count'] = int(nb_frames)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Video metadata extraction failed for {file_path}: {e}")
            return None

    async def _validate_content(self, file_path: str, result: ValidationResult):
        """Validate video content and structure"""
        try:
            # Try to open the video file with OpenCV
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                result.errors.append({
                    'error_code': 'VIDEO_UNREADABLE',
                    'message': "Video file cannot be opened or is corrupted",
                    'timestamp': datetime.utcnow().isoformat()
                })
                return
            
            # Check if we can read at least one frame
            ret, frame = cap.read()
            if not ret:
                result.errors.append({
                    'error_code': 'NO_VIDEO_FRAMES',
                    'message': "No video frames could be read",
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                # Check frame properties
                height, width, channels = frame.shape
                if width < self.config['min_resolution'][0] or height < self.config['min_resolution'][1]:
                    result.warnings.append({
                        'warning_code': 'LOW_RESOLUTION',
                        'message': f"Video resolution {width}x{height} is below recommended minimum",
                        'timestamp': datetime.utcnow().isoformat()
                    })
            
            cap.release()
            
        except Exception as e:
            result.warnings.append({
                'warning_code': 'CONTENT_ANALYSIS_FAILED',
                'message': f"Content analysis failed: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _validate_video_properties(self, file_path: str, result: ValidationResult):
        """Validate video properties against constraints"""
        if not result.metadata:
            return
        
        metadata = result.metadata
        
        # Duration validation
        if metadata.duration:
            if metadata.duration < self.config['min_duration']:
                result.errors.append({
                    'error_code': 'VIDEO_TOO_SHORT',
                    'message': f"Video duration ({metadata.duration}s) is below minimum ({self.config['min_duration']}s)",
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            if metadata.duration > self.config['max_duration']:
                result.errors.append({
                    'error_code': 'VIDEO_TOO_LONG',
                    'message': f"Video duration ({metadata.duration}s) exceeds maximum ({self.config['max_duration']}s)",
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # Resolution validation
        if metadata.width and metadata.height:
            if metadata.width > self.config['max_resolution'][0] or metadata.height > self.config['max_resolution'][1]:
                result.warnings.append({
                    'warning_code': 'HIGH_RESOLUTION',
                    'message': f"Video resolution ({metadata.width}x{metadata.height}) is above recommended maximum",
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # Frame rate validation
        if metadata.fps:
            if metadata.fps > self.config['max_fps']:
                result.warnings.append({
                    'warning_code': 'HIGH_FRAME_RATE',
                    'message': f"Frame rate ({metadata.fps}) is above recommended maximum ({self.config['max_fps']})",
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            if metadata.fps < self.config['min_fps']:
                result.warnings.append({
                    'warning_code': 'LOW_FRAME_RATE',
                    'message': f"Frame rate ({metadata.fps}) is below recommended minimum ({self.config['min_fps']})",
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        # Bitrate validation
        if metadata.bitrate and metadata.bitrate > self.config['max_bitrate']:
            result.warnings.append({
                'warning_code': 'HIGH_BITRATE',
                'message': f"Bitrate ({metadata.bitrate}) is above recommended maximum ({self.config['max_bitrate']})",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _scan_for_viruses(self, file_path: str, result: ValidationResult):
        """Scan file for viruses using ClamAV"""
        try:
            # This is a placeholder implementation
            # In a real scenario, you would integrate with ClamAV or another antivirus engine
            cmd = ['clamscan', '--no-summary', file_path]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                result.virus_scan_result = {
                    'status': 'clean',
                    'scanner': 'clamav',
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                result.virus_scan_result = {
                    'status': 'infected',
                    'scanner': 'clamav',
                    'details': stdout.decode(),
                    'timestamp': datetime.utcnow().isoformat()
                }
                result.errors.append({
                    'error_code': 'VIRUS_DETECTED',
                    'message': "Virus or malware detected in file",
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except FileNotFoundError:
            # ClamAV not installed, skip virus scanning
            result.virus_scan_result = {
                'status': 'skipped',
                'reason': 'antivirus_not_available',
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            result.warnings.append({
                'warning_code': 'VIRUS_SCAN_FAILED',
                'message': f"Virus scan failed: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _deep_file_inspection(self, file_path: str, result: ValidationResult):
        """Perform deep file structure inspection"""
        try:
            # Check for embedded files or suspicious content
            # This is a simplified implementation
            
            # Read first and last 1KB of file for analysis
            file_size = os.path.getsize(file_path)
            
            async with aiofiles.open(file_path, 'rb') as f:
                header = await f.read(1024)
                
                if file_size > 2048:
                    await f.seek(file_size - 1024)
                    footer = await f.read(1024)
                else:
                    footer = b''
            
            # Check for suspicious patterns (simplified)
            suspicious_patterns = [b'<script', b'javascript:', b'eval(', b'exec(']
            
            for pattern in suspicious_patterns:
                if pattern in header or pattern in footer:
                    result.warnings.append({
                        'warning_code': 'SUSPICIOUS_CONTENT',
                        'message': f"Suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}",
                        'timestamp': datetime.utcnow().isoformat()
                    })
            
            # Check file entropy (simplified)
            if len(header) > 0:
                entropy = self._calculate_entropy(header)
                if entropy > 7.5:  # Very high entropy might indicate encryption/compression
                    result.warnings.append({
                        'warning_code': 'HIGH_ENTROPY',
                        'message': f"File has high entropy ({entropy:.2f}), might be encrypted or compressed",
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
        except Exception as e:
            result.warnings.append({
                'warning_code': 'DEEP_INSPECTION_FAILED',
                'message': f"Deep inspection failed: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            })

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of byte sequence"""
        if not data:
            return 0
        
        # Count frequency of each byte value
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1
        
        # Calculate entropy
        entropy = 0
        data_len = len(data)
        for count in freq.values():
            p = count / data_len
            if p > 0:
                entropy -= p * (p).bit_length() - 1
        
        return entropy

    async def _run_additional_checks(self, file_path: str, result: ValidationResult, checks: List[str]):
        """Run additional custom validation checks"""
        for check in checks:
            try:
                if check == 'codec_compatibility':
                    await self._check_codec_compatibility(file_path, result)
                elif check == 'audio_track_validation':
                    await self._validate_audio_tracks(file_path, result)
                elif check == 'subtitle_validation':
                    await self._validate_subtitles(file_path, result)
                elif check == 'keyframe_analysis':
                    await self._analyze_keyframes(file_path, result)
                else:
                    result.warnings.append({
                        'warning_code': 'UNKNOWN_CHECK',
                        'message': f"Unknown validation check: {check}",
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except Exception as e:
                result.warnings.append({
                    'warning_code': 'ADDITIONAL_CHECK_FAILED',
                    'message': f"Additional check '{check}' failed: {str(e)}",
                    'timestamp': datetime.utcnow().isoformat()
                })

    async def _check_codec_compatibility(self, file_path: str, result: ValidationResult):
        """Check codec compatibility for web playback"""
        if not result.metadata or not result.metadata.codec:
            return
        
        # Common web-compatible codecs
        web_compatible_codecs = ['h264', 'h265', 'vp8', 'vp9', 'av1']
        
        if result.metadata.codec.lower() not in web_compatible_codecs:
            result.warnings.append({
                'warning_code': 'CODEC_NOT_WEB_COMPATIBLE',
                'message': f"Codec '{result.metadata.codec}' may not be compatible with web browsers",
                'timestamp': datetime.utcnow().isoformat()
            })

    async def _validate_audio_tracks(self, file_path: str, result: ValidationResult):
        """Validate audio tracks in the video file"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-select_streams', 'a',
                '-show_entries', 'stream=codec_name,channels,sample_rate',
                '-print_format', 'json', file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode())
                audio_streams = data.get('streams', [])
                
                if not audio_streams:
                    result.warnings.append({
                        'warning_code': 'NO_AUDIO_TRACK',
                        'message': "Video file contains no audio tracks",
                        'timestamp': datetime.utcnow().isoformat()
                    })
                else:
                    for i, stream in enumerate(audio_streams):
                        if stream.get('codec_name') == 'unknown':
                            result.warnings.append({
                                'warning_code': 'UNKNOWN_AUDIO_CODEC',
                                'message': f"Audio track {i} has unknown codec",
                                'timestamp': datetime.utcnow().isoformat()
                            })
                            
        except Exception as e:
            logger.warning(f"Audio track validation failed for {file_path}: {e}")

    async def _validate_subtitles(self, file_path: str, result: ValidationResult):
        """Validate subtitle tracks in the video file"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-select_streams', 's',
                '-show_entries', 'stream=codec_name,codec_type',
                '-print_format', 'json', file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                data = json.loads(stdout.decode())
                subtitle_streams = data.get('streams', [])
                
                for i, stream in enumerate(subtitle_streams):
                    if stream.get('codec_name') == 'unknown':
                        result.warnings.append({
                            'warning_code': 'UNKNOWN_SUBTITLE_CODEC',
                            'message': f"Subtitle track {i} has unknown codec",
                            'timestamp': datetime.utcnow().isoformat()
                        })
                        
        except Exception as e:
            logger.warning(f"Subtitle validation failed for {file_path}: {e}")

    async def _analyze_keyframes(self, file_path: str, result: ValidationResult):
        """Analyze keyframe distribution for streaming optimization"""
        try:
            # This is a simplified keyframe analysis
            # In a real implementation, you would analyze keyframe intervals
            
            cmd = [
                'ffprobe', '-v', 'quiet', '-select_streams', 'v:0',
                '-show_entries', 'frame=key_frame,pkt_pts_time',
                '-print_format', 'csv=nk=0', '-read_intervals', '%+#50',
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                lines = stdout.decode().strip().split('\n')
                keyframes = []
                
                for line in lines:
                    if line:
                        parts = line.split(',')
                        if len(parts) >= 2 and parts[0] == '1':  # keyframe
                            try:
                                timestamp = float(parts[1])
                                keyframes.append(timestamp)
                            except (ValueError, IndexError):
                                pass
                
                if len(keyframes) > 1:
                    # Check keyframe intervals
                    intervals = [keyframes[i+1] - keyframes[i] for i in range(len(keyframes)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                    
                    # Warn if keyframe interval is too high (bad for streaming)
                    if avg_interval > 10:  # 10 seconds
                        result.warnings.append({
                            'warning_code': 'LARGE_KEYFRAME_INTERVAL',
                            'message': f"Average keyframe interval ({avg_interval:.1f}s) is high, may affect streaming performance",
                            'timestamp': datetime.utcnow().isoformat()
                        })
                        
        except Exception as e:
            logger.warning(f"Keyframe analysis failed for {file_path}: {e}")

    def get_validation_summary(self, result: ValidationResult) -> Dict[str, Any]:
        """Generate a validation summary for reporting"""
        return {
            'file_path': result.file_path,
            'status': result.status.value,
            'processing_time': result.processing_time,
            'validation_timestamp': result.validation_timestamp.isoformat(),
            'error_count': len(result.errors),
            'warning_count': len(result.warnings),
            'errors': result.errors,
            'warnings': result.warnings,
            'metadata': {
                'filename': result.metadata.filename if result.metadata else None,
                'file_size': result.metadata.file_size if result.metadata else None,
                'duration': result.metadata.duration if result.metadata else None,
                'resolution': f"{result.metadata.width}x{result.metadata.height}" if result.metadata and result.metadata.width else None,
                'codec': result.metadata.codec if result.metadata else None,
                'hash_md5': result.metadata.hash_md5 if result.metadata else None
            },
            'virus_scan': result.virus_scan_result,
            'recommendations': self._generate_recommendations(result)
        }

    def _generate_recommendations(self, result: ValidationResult) -> List[str]:
        """Generate recommendations based on validation results"""
        recommendations = []
        
        for warning in result.warnings:
            code = warning.get('warning_code')
            
            if code == 'HIGH_RESOLUTION':
                recommendations.append("Consider reducing video resolution for better compatibility and smaller file size")
            elif code == 'HIGH_BITRATE':
                recommendations.append("Consider reducing bitrate to optimize file size and streaming performance")
            elif code == 'CODEC_NOT_WEB_COMPATIBLE':
                recommendations.append("Consider re-encoding with H.264 or H.265 for better web browser compatibility")
            elif code == 'LARGE_KEYFRAME_INTERVAL':
                recommendations.append("Consider re-encoding with smaller keyframe intervals for better streaming performance")
            elif code == 'NO_AUDIO_TRACK':
                recommendations.append("Consider adding audio track if this video requires sound")
        
        return recommendations


# Utility functions for integration
async def validate_uploaded_file(file_path: str, config: Dict[str, Any] = None) -> ValidationResult:
    """
    Convenience function to validate an uploaded file
    
    Args:
        file_path: Path to the uploaded file
        config: Optional validation configuration
        
    Returns:
        ValidationResult object
    """
    validator = FileValidator(config)
    return await validator.validate_file(file_path)


def create_validation_config(
    max_file_size: int = None,
    max_duration: int = None,
    enable_virus_scan: bool = False,
    enable_deep_inspection: bool = True
) -> Dict[str, Any]:
    """
    Create a validation configuration with custom settings
    
    Args:
        max_file_size: Maximum file size in bytes
        max_duration: Maximum video duration in seconds
        enable_virus_scan: Enable virus scanning
        enable_deep_inspection: Enable deep file inspection
        
    Returns:
        Configuration dictionary
    """
    validator = FileValidator()
    config = validator._get_default_config().copy()
    
    if max_file_size is not None:
        config['max_file_size'] = max_file_size
    if max_duration is not None:
        config['max_duration'] = max_duration
    if enable_virus_scan is not None:
        config['enable_virus_scan'] = enable_virus_scan
    if enable_deep_inspection is not None:
        config['deep_inspection_enabled'] = enable_deep_inspection
    
    return config