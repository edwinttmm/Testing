"""
File utility functions for VRU Detection System
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
import mimetypes
import magic


def ensure_directory_exists(directory: Path) -> None:
    """Ensure directory exists, create if it doesn't"""
    if isinstance(directory, str):
        directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)


def get_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Calculate hash of file contents"""
    hasher = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> bool:
    """Validate file extension against allowed list"""
    if not filename:
        return False
    
    file_extension = Path(filename).suffix.lower().lstrip('.')
    return file_extension in [ext.lower() for ext in allowed_extensions]


def get_file_mime_type(file_path: Path) -> Tuple[str, Optional[str]]:
    """Get MIME type of file"""
    try:
        # Use python-magic for accurate detection
        mime_type = magic.from_file(str(file_path), mime=True)
        encoding = magic.from_file(str(file_path))
        return mime_type, encoding
    except:
        # Fallback to mimetypes
        mime_type, encoding = mimetypes.guess_type(str(file_path))
        return mime_type or "application/octet-stream", encoding


def safe_filename(filename: str) -> str:
    """Generate safe filename by removing/replacing unsafe characters"""
    import re
    
    # Remove or replace unsafe characters
    safe_name = re.sub(r'[^\w\s.-]', '', filename)
    safe_name = re.sub(r'\s+', '_', safe_name)
    
    # Limit length
    if len(safe_name) > 255:
        name_part = Path(safe_name).stem[:200]
        ext_part = Path(safe_name).suffix
        safe_name = name_part + ext_part
    
    return safe_name


def get_directory_size(directory: Path) -> int:
    """Calculate total size of directory in bytes"""
    total_size = 0
    
    for dirpath, dirnames, filenames in os.walk(directory):
        for filename in filenames:
            filepath = Path(dirpath) / filename
            try:
                total_size += filepath.stat().st_size
            except (OSError, FileNotFoundError):
                continue
    
    return total_size


def cleanup_old_files(directory: Path, max_age_days: int) -> int:
    """Remove files older than specified days"""
    import time
    
    current_time = time.time()
    cutoff_time = current_time - (max_age_days * 24 * 3600)
    
    removed_count = 0
    
    for file_path in directory.rglob("*"):
        if file_path.is_file():
            try:
                file_time = file_path.stat().st_mtime
                if file_time < cutoff_time:
                    file_path.unlink()
                    removed_count += 1
            except (OSError, FileNotFoundError):
                continue
    
    return removed_count


def copy_file_safe(source: Path, destination: Path) -> bool:
    """Safely copy file with verification"""
    try:
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file
        shutil.copy2(source, destination)
        
        # Verify copy by comparing sizes
        if source.stat().st_size == destination.stat().st_size:
            return True
        else:
            # Remove incomplete copy
            destination.unlink()
            return False
            
    except Exception:
        return False


def move_file_safe(source: Path, destination: Path) -> bool:
    """Safely move file with verification"""
    try:
        # First try atomic move
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return True
        
    except Exception:
        # Fallback to copy and delete
        if copy_file_safe(source, destination):
            try:
                source.unlink()
                return True
            except Exception:
                # Remove copied file if we can't delete source
                destination.unlink()
                return False
        return False


def get_available_disk_space(path: Path) -> Tuple[int, int, int]:
    """Get available disk space (total, used, free) in bytes"""
    statvfs = os.statvfs(path)
    
    total = statvfs.f_frsize * statvfs.f_blocks
    free = statvfs.f_frsize * statvfs.f_available
    used = total - free
    
    return total, used, free


def is_video_file(file_path: Path) -> bool:
    """Check if file is a video file based on MIME type"""
    mime_type, _ = get_file_mime_type(file_path)
    return mime_type.startswith('video/') if mime_type else False


def compress_file(source: Path, destination: Path, compression_level: int = 6) -> bool:
    """Compress file using gzip"""
    import gzip
    
    try:
        with open(source, 'rb') as f_in:
            with gzip.open(destination, 'wb', compresslevel=compression_level) as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True
    except Exception:
        return False


def decompress_file(source: Path, destination: Path) -> bool:
    """Decompress gzip file"""
    import gzip
    
    try:
        with gzip.open(source, 'rb') as f_in:
            with open(destination, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True
    except Exception:
        return False


class FileManager:
    """File management utility class"""
    
    def __init__(self, base_directory: Path):
        self.base_directory = Path(base_directory)
        ensure_directory_exists(self.base_directory)
    
    def store_file(self, source: Path, relative_path: str) -> Path:
        """Store file in managed directory structure"""
        destination = self.base_directory / relative_path
        
        if copy_file_safe(source, destination):
            return destination
        else:
            raise IOError(f"Failed to store file: {source}")
    
    def retrieve_file(self, relative_path: str) -> Optional[Path]:
        """Retrieve file from managed directory"""
        file_path = self.base_directory / relative_path
        
        if file_path.exists() and file_path.is_file():
            return file_path
        else:
            return None
    
    def delete_file(self, relative_path: str) -> bool:
        """Delete file from managed directory"""
        file_path = self.base_directory / relative_path
        
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False
    
    def list_files(self, pattern: str = "*") -> List[Path]:
        """List files matching pattern"""
        return list(self.base_directory.rglob(pattern))
    
    def get_storage_stats(self) -> dict:
        """Get storage statistics"""
        total_files = 0
        total_size = 0
        
        for file_path in self.base_directory.rglob("*"):
            if file_path.is_file():
                total_files += 1
                try:
                    total_size += file_path.stat().st_size
                except (OSError, FileNotFoundError):
                    continue
        
        disk_total, disk_used, disk_free = get_available_disk_space(self.base_directory)
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            "disk_total_gb": round(disk_total / (1024 * 1024 * 1024), 2),
            "disk_used_gb": round(disk_used / (1024 * 1024 * 1024), 2),
            "disk_free_gb": round(disk_free / (1024 * 1024 * 1024), 2),
            "disk_usage_percent": round((disk_used / disk_total) * 100, 2)
        }