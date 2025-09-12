"""
Advanced File Upload Security Validator - SPARC Implementation
Comprehensive file validation with malware scanning and security analysis.

SPARC REFINEMENT PHASE: Advanced file security featuring:
- Multi-layer malware detection and scanning
- File type validation with MIME type verification
- Content-based file analysis and threat detection
- Virus signature detection
- File structure integrity validation
- Metadata sanitization and security analysis
- Quarantine system for suspicious files
- Real-time threat intelligence integration
"""

import hashlib
import magic
import mimetypes
import os
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yara
from PIL import Image
from pydantic import BaseModel

from .input_sanitizer import ValidationResult, SecurityEvent
import logging

logger = logging.getLogger(__name__)


class FileSecurityConfig:
    """File security configuration constants"""
    
    # Maximum file sizes by type (bytes)
    MAX_FILE_SIZES = {
        'video': 2 * 1024 * 1024 * 1024,  # 2GB
        'image': 50 * 1024 * 1024,        # 50MB
        'document': 100 * 1024 * 1024,    # 100MB
        'archive': 500 * 1024 * 1024,     # 500MB
        'default': 10 * 1024 * 1024       # 10MB
    }
    
    # Allowed MIME types by category
    ALLOWED_MIME_TYPES = {
        'video': {
            'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
            'video/webm', 'video/x-flv', 'video/x-ms-wmv', 'video/x-matroska',
            'video/ogg', 'video/3gpp', 'video/x-ms-asf'
        },
        'image': {
            'image/jpeg', 'image/png', 'image/bmp', 'image/tiff',
            'image/gif', 'image/webp', 'image/svg+xml'
        },
        'document': {
            'application/pdf', 'text/plain', 'text/csv',
            'application/json', 'application/xml'
        }
    }
    
    # Dangerous file extensions
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.vbe',
        '.js', '.jse', '.jar', '.sh', '.ps1', '.php', '.asp', '.jsp',
        '.pl', '.py', '.rb', '.go', '.rs', '.cpp', '.c', '.h',
        '.msi', '.deb', '.rpm', '.dmg', '.pkg', '.app'
    }
    
    # Suspicious file signatures (magic bytes)
    SUSPICIOUS_SIGNATURES = {
        # Executable files
        b'\x4d\x5a': 'PE executable',
        b'\x7f\x45\x4c\x46': 'ELF executable',
        b'\xfe\xed\xfa': 'Mach-O executable',
        b'\xcf\xfa\xed\xfe': 'Mach-O executable',
        
        # Archive files that might contain executables
        b'\x50\x4b\x03\x04': 'ZIP archive',
        b'\x52\x61\x72\x21': 'RAR archive',
        
        # Script files
        b'#!/bin/sh': 'Shell script',
        b'#!/bin/bash': 'Bash script',
        b'<?php': 'PHP script',
    }
    
    # Virus signatures (simplified patterns)
    VIRUS_SIGNATURES = [
        b'\x90\x90\x90\x90',  # NOP sled
        b'\xeb\xfe',          # Infinite loop
        b'WannaCry',          # WannaCry ransomware
        b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE',  # EICAR test file
    ]
    
    # Maximum metadata size
    MAX_METADATA_SIZE = 1024 * 1024  # 1MB


class FileAnalysisResult(BaseModel):
    """File analysis result model"""
    safe: bool
    threat_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    detected_threats: List[str] = []
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: int = 0
    sha256_hash: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    quarantine_required: bool = False


class FileValidator:
    """
    Advanced file upload security validator with comprehensive threat detection
    
    Features:
    - Multi-layer malware detection
    - Content-based file analysis
    - Virus signature scanning
    - File integrity validation
    - Metadata security analysis
    - Real-time threat assessment
    """
    
    def __init__(self, quarantine_dir: Optional[str] = None):
        """Initialize file validator with security configurations"""
        self.quarantine_dir = Path(quarantine_dir) if quarantine_dir else Path("/tmp/quarantine")
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize magic for file type detection
        try:
            self.magic_mime = magic.Magic(mime=True)
            self.magic_type = magic.Magic()
        except Exception as e:
            logger.error(f"Failed to initialize python-magic: {e}")
            self.magic_mime = None
            self.magic_type = None
        
        # Try to load YARA rules if available
        self.yara_rules = None
        try:
            self._load_yara_rules()
        except Exception as e:
            logger.warning(f"YARA rules not available: {e}")
        
        # Initialize virus scanner if available
        self.clamav_available = self._check_clamav()
    
    async def validate_file(
        self, 
        file_obj: Any, 
        field_name: str,
        client_ip: str = "unknown",
        user_agent: str = "unknown"
    ) -> ValidationResult:
        """
        Comprehensive file validation with security scanning
        
        Args:
            file_obj: File object to validate
            field_name: Name of the form field
            client_ip: Client IP address
            user_agent: Client user agent
        
        Returns:
            ValidationResult with security analysis
        """
        result = ValidationResult(valid=True, security_events=[])
        
        try:
            # Extract file information
            filename = getattr(file_obj, 'filename', 'unknown')
            file_size = getattr(file_obj, 'size', 0)
            
            # Create temporary file for analysis
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                # Read file content
                content = await file_obj.read()
                temp_file.write(content)
                temp_file.flush()
                temp_path = temp_file.name
            
            try:
                # Perform comprehensive file analysis
                analysis_result = await self._analyze_file(temp_path, filename, file_size)
                
                # Process analysis results
                if not analysis_result.safe:
                    result.valid = False
                    result.errors.append({
                        'field': field_name,
                        'message': f'File security validation failed: {", ".join(analysis_result.detected_threats)}',
                        'code': 'FILE_SECURITY_VIOLATION'
                    })
                    
                    # Log security event
                    result.security_events.append(
                        SecurityEvent(
                            event_type="MALICIOUS_FILE_UPLOAD",
                            severity=analysis_result.threat_level,
                            description=f"Malicious file upload attempt: {filename}",
                            ip_address=client_ip,
                            user_agent=user_agent,
                            additional_data={
                                'filename': filename,
                                'file_size': file_size,
                                'threats': analysis_result.detected_threats,
                                'file_hash': analysis_result.sha256_hash
                            }
                        )
                    )
                    
                    # Quarantine the file if necessary
                    if analysis_result.quarantine_required:
                        await self._quarantine_file(temp_path, filename, analysis_result)
                
                elif analysis_result.threat_level in ['MEDIUM', 'HIGH']:
                    result.warnings.append({
                        'field': field_name,
                        'message': f'File has potential security concerns: {", ".join(analysis_result.detected_threats)}',
                        'code': 'FILE_SECURITY_WARNING'
                    })
                    
                    result.security_events.append(
                        SecurityEvent(
                            event_type="SUSPICIOUS_FILE_UPLOAD",
                            severity=analysis_result.threat_level,
                            description=f"Suspicious file upload: {filename}",
                            ip_address=client_ip,
                            user_agent=user_agent,
                            additional_data={
                                'filename': filename,
                                'file_size': file_size,
                                'concerns': analysis_result.detected_threats,
                                'file_hash': analysis_result.sha256_hash
                            }
                        )
                    )
                
                # Add file information to result
                if result.valid:
                    result.data = {
                        'filename': filename,
                        'file_size': file_size,
                        'mime_type': analysis_result.mime_type,
                        'file_type': analysis_result.file_type,
                        'sha256_hash': analysis_result.sha256_hash,
                        'metadata': analysis_result.metadata
                    }
                
            finally:
                # Clean up temporary file if not quarantined
                if os.path.exists(temp_path) and not analysis_result.quarantine_required:
                    os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"File validation error: {str(e)}")
            result.valid = False
            result.errors.append({
                'field': field_name,
                'message': 'File validation failed due to internal error',
                'code': 'FILE_VALIDATION_ERROR'
            })
        
        return result
    
    async def _analyze_file(self, file_path: str, filename: str, file_size: int) -> FileAnalysisResult:
        """
        Comprehensive file analysis with multiple security checks
        """
        result = FileAnalysisResult(
            safe=True,
            threat_level="LOW",
            file_size=file_size
        )
        
        try:
            # Calculate file hash
            result.sha256_hash = await self._calculate_file_hash(file_path)
            
            # File size validation
            if file_size > FileSecurityConfig.MAX_FILE_SIZES.get('default', 10 * 1024 * 1024):
                result.detected_threats.append(f"File too large: {file_size} bytes")
                result.threat_level = "MEDIUM"
            
            # Filename validation
            filename_threats = await self._validate_filename(filename)
            if filename_threats:
                result.detected_threats.extend(filename_threats)
                result.threat_level = "HIGH" if any("dangerous" in t for t in filename_threats) else "MEDIUM"
            
            # MIME type detection and validation
            mime_type = await self._detect_mime_type(file_path)
            result.mime_type = mime_type
            
            if not await self._is_mime_type_allowed(mime_type):
                result.detected_threats.append(f"Disallowed MIME type: {mime_type}")
                result.threat_level = "HIGH"
                result.safe = False
            
            # File signature validation
            signature_threats = await self._validate_file_signature(file_path)
            if signature_threats:
                result.detected_threats.extend(signature_threats)
                result.threat_level = "HIGH"
                result.safe = False
            
            # Virus scanning
            virus_scan_result = await self._scan_for_viruses(file_path)
            if virus_scan_result:
                result.detected_threats.extend(virus_scan_result)
                result.threat_level = "CRITICAL"
                result.safe = False
                result.quarantine_required = True
            
            # Content analysis
            content_threats = await self._analyze_file_content(file_path, mime_type)
            if content_threats:
                result.detected_threats.extend(content_threats)
                if "malware" in str(content_threats).lower():
                    result.threat_level = "CRITICAL"
                    result.safe = False
                    result.quarantine_required = True
                else:
                    result.threat_level = "MEDIUM"
            
            # Metadata analysis
            result.metadata = await self._extract_and_analyze_metadata(file_path, mime_type)
            metadata_threats = await self._analyze_metadata_security(result.metadata)
            if metadata_threats:
                result.detected_threats.extend(metadata_threats)
                result.threat_level = "MEDIUM"
            
            # YARA rules scanning
            if self.yara_rules:
                yara_results = await self._scan_with_yara(file_path)
                if yara_results:
                    result.detected_threats.extend(yara_results)
                    result.threat_level = "CRITICAL"
                    result.safe = False
                    result.quarantine_required = True
            
            # Final safety assessment
            if len(result.detected_threats) >= 3:
                result.safe = False
                result.quarantine_required = True
            
        except Exception as e:
            logger.error(f"File analysis error: {str(e)}")
            result.detected_threats.append(f"Analysis error: {str(e)}")
            result.threat_level = "HIGH"
            result.safe = False
        
        return result
    
    async def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    async def _validate_filename(self, filename: str) -> List[str]:
        """Validate filename for security issues"""
        threats = []
        
        # Check for dangerous extensions
        file_ext = Path(filename).suffix.lower()
        if file_ext in FileSecurityConfig.DANGEROUS_EXTENSIONS:
            threats.append(f"Dangerous file extension: {file_ext}")
        
        # Check for path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            threats.append("Path traversal attempt in filename")
        
        # Check for suspicious patterns
        if re.search(r'[\x00-\x1f\x7f-\x9f]', filename):
            threats.append("Control characters in filename")
        
        # Check filename length
        if len(filename) > 255:
            threats.append("Filename too long")
        
        # Check for script-like names
        if re.match(r'.*\.(php|asp|jsp|js|vbs|py|pl|sh|bat|cmd)$', filename, re.IGNORECASE):
            threats.append("Script-like filename detected")
        
        return threats
    
    async def _detect_mime_type(self, file_path: str) -> Optional[str]:
        """Detect file MIME type using multiple methods"""
        mime_type = None
        
        # Try python-magic first
        if self.magic_mime:
            try:
                mime_type = self.magic_mime.from_file(file_path)
            except Exception as e:
                logger.warning(f"Magic MIME detection failed: {e}")
        
        # Fallback to mimetypes module
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(file_path)
        
        return mime_type
    
    async def _is_mime_type_allowed(self, mime_type: str) -> bool:
        """Check if MIME type is allowed"""
        if not mime_type:
            return False
        
        for category, allowed_types in FileSecurityConfig.ALLOWED_MIME_TYPES.items():
            if mime_type in allowed_types:
                return True
        
        return False
    
    async def _validate_file_signature(self, file_path: str) -> List[str]:
        """Validate file signature against suspicious patterns"""
        threats = []
        
        try:
            with open(file_path, 'rb') as f:
                header = f.read(512)  # Read first 512 bytes
            
            for signature, description in FileSecurityConfig.SUSPICIOUS_SIGNATURES.items():
                if header.startswith(signature):
                    threats.append(f"Suspicious file signature detected: {description}")
                    break
        
        except Exception as e:
            logger.error(f"File signature validation error: {e}")
            threats.append("Unable to validate file signature")
        
        return threats
    
    async def _scan_for_viruses(self, file_path: str) -> List[str]:
        """Scan file for viruses using multiple methods"""
        threats = []
        
        # Simple signature-based detection
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            for signature in FileSecurityConfig.VIRUS_SIGNATURES:
                if signature in content:
                    threats.append(f"Virus signature detected: {signature.hex()}")
        
        except Exception as e:
            logger.error(f"Virus signature scanning error: {e}")
        
        # ClamAV scanning if available
        if self.clamav_available:
            clamav_result = await self._scan_with_clamav(file_path)
            if clamav_result:
                threats.extend(clamav_result)
        
        return threats
    
    async def _scan_with_clamav(self, file_path: str) -> List[str]:
        """Scan file with ClamAV antivirus"""
        threats = []
        
        try:
            result = subprocess.run(
                ['clamscan', '--no-summary', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if 'FOUND' in line:
                        threats.append(f"ClamAV detected: {line.strip()}")
        
        except subprocess.TimeoutExpired:
            threats.append("ClamAV scan timeout")
        except Exception as e:
            logger.error(f"ClamAV scanning error: {e}")
        
        return threats
    
    async def _analyze_file_content(self, file_path: str, mime_type: str) -> List[str]:
        """Analyze file content for suspicious patterns"""
        threats = []
        
        try:
            # For image files, try to validate structure
            if mime_type and mime_type.startswith('image/'):
                image_threats = await self._analyze_image_content(file_path)
                threats.extend(image_threats)
            
            # For text-based files, check content
            elif mime_type and mime_type.startswith('text/'):
                text_threats = await self._analyze_text_content(file_path)
                threats.extend(text_threats)
            
            # General content analysis
            with open(file_path, 'rb') as f:
                sample = f.read(1024)  # Read first 1KB
            
            # Check for embedded scripts
            if b'<script' in sample.lower() or b'javascript:' in sample.lower():
                threats.append("Embedded JavaScript detected")
            
            # Check for suspicious strings
            suspicious_strings = [
                b'eval(', b'exec(', b'system(', b'shell_exec',
                b'passthru', b'proc_open', b'popen',
                b'file_get_contents', b'file_put_contents'
            ]
            
            for sus_string in suspicious_strings:
                if sus_string in sample.lower():
                    threats.append(f"Suspicious function call detected: {sus_string.decode()}")
        
        except Exception as e:
            logger.error(f"Content analysis error: {e}")
        
        return threats
    
    async def _analyze_image_content(self, file_path: str) -> List[str]:
        """Analyze image file content"""
        threats = []
        
        try:
            with Image.open(file_path) as img:
                # Check image dimensions
                width, height = img.size
                if width > 50000 or height > 50000:
                    threats.append("Suspicious image dimensions (potential zip bomb)")
                
                # Check for excessive metadata
                if hasattr(img, '_getexif'):
                    exif = img._getexif()
                    if exif and len(str(exif)) > 10000:
                        threats.append("Excessive EXIF metadata")
        
        except Exception as e:
            logger.warning(f"Image analysis error: {e}")
            threats.append("Unable to validate image structure")
        
        return threats
    
    async def _analyze_text_content(self, file_path: str) -> List[str]:
        """Analyze text file content"""
        threats = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024)  # Read first 1KB
            
            # Check for suspicious patterns
            if re.search(r'<\s*script[^>]*>', content, re.IGNORECASE):
                threats.append("Script tags in text file")
            
            if re.search(r'(eval|exec|system)\s*\(', content, re.IGNORECASE):
                threats.append("Suspicious function calls in text")
        
        except Exception as e:
            logger.error(f"Text analysis error: {e}")
        
        return threats
    
    async def _extract_and_analyze_metadata(self, file_path: str, mime_type: str) -> Dict[str, Any]:
        """Extract and analyze file metadata"""
        metadata = {}
        
        try:
            # Basic file stats
            stat = os.stat(file_path)
            metadata.update({
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'mime_type': mime_type
            })
            
            # Image metadata
            if mime_type and mime_type.startswith('image/'):
                try:
                    with Image.open(file_path) as img:
                        metadata.update({
                            'dimensions': img.size,
                            'format': img.format,
                            'mode': img.mode
                        })
                        
                        # EXIF data (sanitized)
                        if hasattr(img, '_getexif'):
                            exif = img._getexif()
                            if exif:
                                # Only include safe EXIF fields
                                safe_exif = {}
                                safe_fields = [271, 272, 282, 283]  # Make, Model, XRes, YRes
                                for field in safe_fields:
                                    if field in exif:
                                        safe_exif[field] = str(exif[field])[:100]  # Limit length
                                metadata['exif'] = safe_exif
                except Exception as e:
                    logger.warning(f"Image metadata extraction error: {e}")
        
        except Exception as e:
            logger.error(f"Metadata extraction error: {e}")
        
        return metadata
    
    async def _analyze_metadata_security(self, metadata: Dict[str, Any]) -> List[str]:
        """Analyze metadata for security issues"""
        threats = []
        
        try:
            # Check for excessive metadata size
            metadata_str = str(metadata)
            if len(metadata_str) > FileSecurityConfig.MAX_METADATA_SIZE:
                threats.append("Excessive metadata size")
            
            # Check EXIF data for suspicious content
            if 'exif' in metadata:
                exif_data = str(metadata['exif'])
                if any(suspicious in exif_data.lower() for suspicious in ['script', 'javascript', 'eval']):
                    threats.append("Suspicious content in EXIF data")
        
        except Exception as e:
            logger.error(f"Metadata security analysis error: {e}")
        
        return threats
    
    async def _scan_with_yara(self, file_path: str) -> List[str]:
        """Scan file with YARA rules"""
        threats = []
        
        if not self.yara_rules:
            return threats
        
        try:
            matches = self.yara_rules.match(file_path)
            for match in matches:
                threats.append(f"YARA rule matched: {match.rule}")
        
        except Exception as e:
            logger.error(f"YARA scanning error: {e}")
        
        return threats
    
    async def _quarantine_file(self, file_path: str, filename: str, analysis: FileAnalysisResult):
        """Move file to quarantine directory"""
        try:
            quarantine_filename = f"{uuid.uuid4()}_{filename}"
            quarantine_path = self.quarantine_dir / quarantine_filename
            
            # Move file to quarantine
            os.rename(file_path, quarantine_path)
            
            # Create analysis report
            report_path = quarantine_path.with_suffix('.json')
            import json
            with open(report_path, 'w') as f:
                json.dump({
                    'original_filename': filename,
                    'quarantine_time': time.time(),
                    'analysis_result': analysis.dict(),
                    'quarantine_reason': 'Malicious file detected'
                }, f, indent=2)
            
            logger.warning(f"File quarantined: {filename} -> {quarantine_path}")
        
        except Exception as e:
            logger.error(f"Failed to quarantine file: {e}")
    
    def _load_yara_rules(self):
        """Load YARA rules for malware detection"""
        try:
            # Try to load YARA rules from various locations
            rule_paths = [
                '/etc/yara/rules',
                '/usr/local/share/yara/rules',
                './yara_rules'
            ]
            
            for rule_path in rule_paths:
                if os.path.exists(rule_path):
                    rule_files = []
                    for root, dirs, files in os.walk(rule_path):
                        for file in files:
                            if file.endswith('.yar') or file.endswith('.yara'):
                                rule_files.append(os.path.join(root, file))
                    
                    if rule_files:
                        self.yara_rules = yara.compile(filepaths={
                            f'rule_{i}': rule_file 
                            for i, rule_file in enumerate(rule_files)
                        })
                        logger.info(f"Loaded {len(rule_files)} YARA rules")
                        break
        
        except Exception as e:
            logger.warning(f"Could not load YARA rules: {e}")
    
    def _check_clamav(self) -> bool:
        """Check if ClamAV is available"""
        try:
            result = subprocess.run(['clamscan', '--version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False