"""
Enterprise File Upload Security Module
Provides comprehensive security validation for file uploads including:
- Magic number validation
- MIME type verification  
- Malware scanning
- Path traversal protection
- Content analysis
- Security event logging
"""

import os
import hashlib
import magic
import tempfile
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import mimetypes
import subprocess
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SecurityThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"

class ScanResult(Enum):
    CLEAN = "clean"
    SUSPICIOUS = "suspicious"
    MALWARE = "malware"
    ERROR = "error"

@dataclass
class FileSecurityReport:
    """Comprehensive security analysis report for uploaded files"""
    filename: str
    file_size: int
    mime_type: str
    file_extension: str
    
    # Security check results
    magic_number_valid: bool
    mime_type_valid: bool
    file_size_valid: bool
    path_secure: bool
    content_secure: bool
    
    # Scan results
    virus_scan_result: ScanResult
    content_analysis_result: ScanResult
    
    # Threat assessment
    threat_level: SecurityThreatLevel
    risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    
    # Details
    security_errors: List[str]
    security_warnings: List[str]
    scan_details: Dict[str, Any]
    
    # Metadata
    scan_timestamp: datetime
    scan_duration_ms: int
    file_hash: str

class FileUploadSecurityValidator:
    """Enterprise-grade file upload security validator"""
    
    # Security configuration
    SECURITY_CONFIG = {
        # File size limits
        'MAX_FILE_SIZE': 100 * 1024 * 1024,  # 100MB
        'MIN_FILE_SIZE': 1024,  # 1KB
        
        # Allowed MIME types and extensions
        'ALLOWED_TYPES': {
            'video/mp4': ['.mp4'],
            'video/avi': ['.avi'], 
            'video/x-msvideo': ['.avi'],
            'video/quicktime': ['.mov'],
            'video/x-matroska': ['.mkv'],
        },
        
        # Magic number signatures for video files
        'MAGIC_SIGNATURES': {
            '.mp4': [
                b'\x00\x00\x00\x18ftypmp4',  # MP4 signature
                b'\x00\x00\x00\x20ftypisom', # ISO MP4 signature
                b'\x00\x00\x00\x1cftyp3gp',  # 3GP signature
            ],
            '.avi': [
                b'RIFF',  # RIFF header (first 4 bytes)
            ],
            '.mov': [
                b'\x00\x00\x00\x14ftypqt',   # QuickTime signature
                b'\x00\x00\x00\x18ftypqt',   # Alternative QuickTime
            ],
            '.mkv': [
                b'\x1a\x45\xdf\xa3',  # Matroska signature
            ],
        },
        
        # Forbidden patterns in filenames
        'FORBIDDEN_PATTERNS': [
            r'\.exe$', r'\.bat$', r'\.cmd$', r'\.scr$', r'\.pif$',
            r'\.com$', r'\.jar$', r'\.js$', r'\.vbs$', r'\.ps1$',
            r'\.php$', r'\.asp$', r'\.jsp$', r'<script', r'javascript:',
            r'vbscript:', r'on\w+\s*=',  # Event handlers
        ],
        
        # Path security patterns
        'PATH_TRAVERSAL_PATTERNS': [
            '..', '/.', '\\.', '//', '\\\\', '%2e%2e', '%2f', '%5c',
        ],
        
        # Content scanning
        'SCAN_FIRST_BYTES': 8192,  # Scan first 8KB for suspicious content
        'SUSPICIOUS_STRINGS': [
            b'<script', b'javascript:', b'vbscript:', b'eval(',
            b'system(', b'exec(', b'shell_exec(', b'passthru(',
        ],
        
        # Rate limiting
        'RATE_LIMITS': {
            'max_uploads_per_ip_per_minute': 10,
            'max_bytes_per_ip_per_minute': 200 * 1024 * 1024,  # 200MB
        }
    }
    
    def __init__(self, upload_dir: str = "/tmp/uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize security components
        self._init_malware_scanner()
        self._init_rate_limiter()
        self._init_security_logger()
        
    def _init_malware_scanner(self):
        """Initialize malware scanning capabilities"""
        try:
            # Check if ClamAV is available
            result = subprocess.run(['clamscan', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            self.clamav_available = result.returncode == 0
            logger.info("ClamAV malware scanner initialized successfully")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self.clamav_available = False
            logger.warning("ClamAV not available - using basic content analysis")
    
    def _init_rate_limiter(self):
        """Initialize rate limiting"""
        self.upload_history = {}  # IP -> [(timestamp, bytes), ...]
        
    def _init_security_logger(self):
        """Initialize security event logging"""
        self.security_logger = logging.getLogger('file_upload_security')
        handler = logging.FileHandler('security_events.log')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.security_logger.addHandler(handler)
        self.security_logger.setLevel(logging.INFO)
    
    def validate_file_upload(self, file_path: str, original_filename: str, 
                           client_ip: str = None) -> FileSecurityReport:
        """
        Perform comprehensive security validation on uploaded file
        
        Args:
            file_path: Path to the uploaded file
            original_filename: Original filename from client
            client_ip: Client IP address for rate limiting
            
        Returns:
            FileSecurityReport with detailed security analysis
        """
        start_time = time.time()
        
        # Initialize report
        report = FileSecurityReport(
            filename=original_filename,
            file_size=0,
            mime_type="",
            file_extension="",
            magic_number_valid=False,
            mime_type_valid=False,
            file_size_valid=False,
            path_secure=False,
            content_secure=False,
            virus_scan_result=ScanResult.ERROR,
            content_analysis_result=ScanResult.ERROR,
            threat_level=SecurityThreatLevel.HIGH,
            risk_score=1.0,
            security_errors=[],
            security_warnings=[],
            scan_details={},
            scan_timestamp=datetime.now(),
            scan_duration_ms=0,
            file_hash=""
        )
        
        try:
            # Basic file validation
            if not os.path.exists(file_path):
                report.security_errors.append("File does not exist")
                return report
                
            file_stat = os.stat(file_path)
            report.file_size = file_stat.st_size
            
            # Generate file hash
            report.file_hash = self._calculate_file_hash(file_path)
            
            # Extract file extension
            report.file_extension = Path(original_filename).suffix.lower()
            
            # 1. Rate limiting check
            if client_ip:
                rate_limit_result = self._check_rate_limits(client_ip, report.file_size)
                if not rate_limit_result['allowed']:
                    report.security_errors.append(f"Rate limit exceeded: {rate_limit_result['reason']}")
                    report.threat_level = SecurityThreatLevel.MEDIUM
                    
            # 2. File size validation
            report.file_size_valid = self._validate_file_size(report.file_size, report)
            
            # 3. Path security validation
            report.path_secure = self._validate_path_security(original_filename, report)
            
            # 4. MIME type validation
            report.mime_type = self._detect_mime_type(file_path)
            report.mime_type_valid = self._validate_mime_type(report.mime_type, report.file_extension, report)
            
            # 5. Magic number validation  
            report.magic_number_valid = self._validate_magic_numbers(file_path, report.file_extension, report)
            
            # 6. Content security analysis
            report.content_analysis_result = self._analyze_file_content(file_path, report)
            report.content_secure = report.content_analysis_result in [ScanResult.CLEAN, ScanResult.SUSPICIOUS]
            
            # 7. Malware scanning
            report.virus_scan_result = self._scan_for_malware(file_path, report)
            
            # 8. Calculate overall risk score and threat level
            self._calculate_risk_assessment(report)
            
            # Log security event
            self._log_security_event(report, client_ip)
            
        except Exception as e:
            logger.error(f"Security validation failed: {e}")
            report.security_errors.append(f"Validation failed: {str(e)}")
            report.threat_level = SecurityThreatLevel.CRITICAL
            report.risk_score = 1.0
            
        finally:
            report.scan_duration_ms = int((time.time() - start_time) * 1000)
            
        return report
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of file"""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate file hash: {e}")
            return "unknown"
    
    def _check_rate_limits(self, client_ip: str, file_size: int) -> Dict[str, Any]:
        """Check if upload request exceeds rate limits"""
        now = time.time()
        one_minute_ago = now - 60
        
        # Clean old entries
        if client_ip in self.upload_history:
            self.upload_history[client_ip] = [
                (timestamp, size) for timestamp, size in self.upload_history[client_ip]
                if timestamp > one_minute_ago
            ]
        else:
            self.upload_history[client_ip] = []
        
        history = self.upload_history[client_ip]
        
        # Check upload count limit
        max_uploads = self.SECURITY_CONFIG['RATE_LIMITS']['max_uploads_per_ip_per_minute']
        if len(history) >= max_uploads:
            return {'allowed': False, 'reason': f'Too many uploads (max {max_uploads} per minute)'}
        
        # Check bandwidth limit
        total_bytes = sum(size for _, size in history)
        max_bytes = self.SECURITY_CONFIG['RATE_LIMITS']['max_bytes_per_ip_per_minute']
        if total_bytes + file_size > max_bytes:
            return {'allowed': False, 'reason': f'Bandwidth limit exceeded (max {max_bytes} bytes per minute)'}
        
        # Record this upload
        self.upload_history[client_ip].append((now, file_size))
        
        return {'allowed': True}
    
    def _validate_file_size(self, file_size: int, report: FileSecurityReport) -> bool:
        """Validate file size is within acceptable limits"""
        min_size = self.SECURITY_CONFIG['MIN_FILE_SIZE']
        max_size = self.SECURITY_CONFIG['MAX_FILE_SIZE']
        
        if file_size < min_size:
            report.security_errors.append(f"File too small (minimum {min_size} bytes)")
            return False
        elif file_size > max_size:
            report.security_errors.append(f"File too large (maximum {max_size // (1024*1024)}MB)")
            return False
        elif file_size == 0:
            report.security_errors.append("Empty file not allowed")
            return False
            
        return True
    
    def _validate_path_security(self, filename: str, report: FileSecurityReport) -> bool:
        """Validate filename for path traversal and other security issues"""
        # Check for path traversal patterns
        for pattern in self.SECURITY_CONFIG['PATH_TRAVERSAL_PATTERNS']:
            if pattern in filename:
                report.security_errors.append(f"Path traversal pattern detected: {pattern}")
                return False
        
        # Check for forbidden filename patterns
        for pattern in self.SECURITY_CONFIG['FORBIDDEN_PATTERNS']:
            if re.search(pattern, filename, re.IGNORECASE):
                report.security_errors.append(f"Forbidden filename pattern: {pattern}")
                return False
        
        # Check for null bytes and control characters
        if '\x00' in filename or any(ord(c) < 32 for c in filename if c not in '\t\n\r'):
            report.security_errors.append("Filename contains null bytes or control characters")
            return False
        
        # Check filename length
        if len(filename) > 255:
            report.security_errors.append("Filename too long")
            return False
            
        return True
    
    def _detect_mime_type(self, file_path: str) -> str:
        """Detect MIME type using python-magic"""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(file_path)
        except Exception as e:
            logger.warning(f"Failed to detect MIME type using magic: {e}")
            # Fallback to mimetypes module
            mime_type, _ = mimetypes.guess_type(file_path)
            return mime_type or "application/octet-stream"
    
    def _validate_mime_type(self, mime_type: str, file_extension: str, report: FileSecurityReport) -> bool:
        """Validate MIME type matches allowed types and file extension"""
        allowed_types = self.SECURITY_CONFIG['ALLOWED_TYPES']
        
        # Check if MIME type is allowed
        if mime_type not in allowed_types:
            report.security_errors.append(f"MIME type not allowed: {mime_type}")
            return False
        
        # Check if file extension matches MIME type
        expected_extensions = allowed_types[mime_type]
        if file_extension not in expected_extensions:
            report.security_warnings.append(
                f"File extension {file_extension} doesn't match MIME type {mime_type}"
            )
            # This is a warning, not an error, as it might be a legitimate mismatch
            
        return True
    
    def _validate_magic_numbers(self, file_path: str, file_extension: str, report: FileSecurityReport) -> bool:
        """Validate file magic numbers (file signatures)"""
        if file_extension not in self.SECURITY_CONFIG['MAGIC_SIGNATURES']:
            report.security_warnings.append(f"No magic signature validation available for {file_extension}")
            return True  # Not an error, just unsupported
        
        try:
            with open(file_path, 'rb') as f:
                file_header = f.read(32)  # Read first 32 bytes
            
            expected_signatures = self.SECURITY_CONFIG['MAGIC_SIGNATURES'][file_extension]
            
            for signature in expected_signatures:
                if file_header.startswith(signature):
                    report.scan_details['magic_number_match'] = signature.hex()
                    return True
            
            # Special handling for AVI files (RIFF container)
            if file_extension == '.avi' and file_header.startswith(b'RIFF'):
                # Check for AVI identifier at offset 8
                if len(file_header) > 12 and file_header[8:12] == b'AVI ':
                    report.scan_details['magic_number_match'] = 'RIFF...AVI'
                    return True
            
            report.security_warnings.append(
                f"Magic number doesn't match expected signature for {file_extension}"
            )
            report.scan_details['magic_number_mismatch'] = file_header[:16].hex()
            return False
            
        except Exception as e:
            logger.error(f"Magic number validation failed: {e}")
            report.security_warnings.append(f"Could not validate magic numbers: {e}")
            return False
    
    def _analyze_file_content(self, file_path: str, report: FileSecurityReport) -> ScanResult:
        """Analyze file content for suspicious patterns"""
        try:
            with open(file_path, 'rb') as f:
                content_sample = f.read(self.SECURITY_CONFIG['SCAN_FIRST_BYTES'])
            
            # Check for suspicious strings
            suspicious_found = []
            for pattern in self.SECURITY_CONFIG['SUSPICIOUS_STRINGS']:
                if pattern in content_sample:
                    suspicious_found.append(pattern.decode('utf-8', errors='ignore'))
            
            if suspicious_found:
                report.security_warnings.append(
                    f"Suspicious content patterns found: {', '.join(suspicious_found)}"
                )
                report.scan_details['suspicious_patterns'] = suspicious_found
                return ScanResult.SUSPICIOUS
            
            # Check for high entropy (might indicate encrypted/packed content)
            entropy = self._calculate_entropy(content_sample)
            report.scan_details['content_entropy'] = entropy
            
            if entropy > 7.5:  # High entropy threshold
                report.security_warnings.append(f"High content entropy detected: {entropy:.2f}")
                return ScanResult.SUSPICIOUS
            
            return ScanResult.CLEAN
            
        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            report.security_errors.append(f"Content analysis failed: {e}")
            return ScanResult.ERROR
    
        import math
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data"""
        if len(data) == 0:
            return 0
        
        # Count byte frequencies
        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1
        
        # Calculate entropy
        entropy = 0.0
        data_len = len(data)
        
        for count in byte_counts:
            if count == 0:
                continue
            frequency = count / data_len
            entropy -= frequency * math.log2(frequency)
        
        return entropy
    
    def _scan_for_malware(self, file_path: str, report: FileSecurityReport) -> ScanResult:
        """Scan file for malware using ClamAV or fallback methods"""
        if self.clamav_available:
            return self._clamav_scan(file_path, report)
        else:
            return self._basic_malware_check(file_path, report)
    
    def _clamav_scan(self, file_path: str, report: FileSecurityReport) -> ScanResult:
        """Scan file using ClamAV"""
        try:
            result = subprocess.run([
                'clamscan', 
                '--no-summary',
                '--infected',
                file_path
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                report.scan_details['clamav_result'] = 'clean'
                return ScanResult.CLEAN
            elif result.returncode == 1:
                # Malware found
                output_lines = result.stdout.strip().split('\n')
                for line in output_lines:
                    if 'FOUND' in line:
                        malware_name = line.split(': ')[1].replace(' FOUND', '')
                        report.security_errors.append(f"Malware detected: {malware_name}")
                        report.scan_details['malware_detected'] = malware_name
                        break
                return ScanResult.MALWARE
            else:
                # Scan error
                report.security_warnings.append(f"ClamAV scan error: {result.stderr}")
                return ScanResult.ERROR
                
        except subprocess.TimeoutExpired:
            report.security_warnings.append("ClamAV scan timed out")
            return ScanResult.ERROR
        except Exception as e:
            logger.error(f"ClamAV scan failed: {e}")
            report.security_warnings.append(f"ClamAV scan failed: {e}")
            return ScanResult.ERROR
    
    def _basic_malware_check(self, file_path: str, report: FileSecurityReport) -> ScanResult:
        """Basic malware check without external scanner"""
        try:
            # Check file size anomalies
            file_size = os.path.getsize(file_path)
            
            # Very small files claiming to be videos are suspicious
            if file_size < 10000:  # Less than 10KB
                report.security_warnings.append("Unusually small file size for video")
                return ScanResult.SUSPICIOUS
            
            # Check for executable signatures in video files
            with open(file_path, 'rb') as f:
                header = f.read(1024)
            
            # Check for PE (Windows executable) header
            if b'MZ' in header[:2] or b'\x7fELF' in header[:4]:
                report.security_errors.append("Executable file signature detected in video file")
                return ScanResult.MALWARE
            
            return ScanResult.CLEAN
            
        except Exception as e:
            logger.error(f"Basic malware check failed: {e}")
            return ScanResult.ERROR
    
    def _calculate_risk_assessment(self, report: FileSecurityReport):
        """Calculate overall risk score and threat level"""
        risk_factors = 0
        max_risk_factors = 8
        
        # Factor 1: Security errors (critical)
        if report.security_errors:
            risk_factors += len(report.security_errors)
        
        # Factor 2: Failed validations
        if not report.magic_number_valid:
            risk_factors += 0.5
        if not report.mime_type_valid:
            risk_factors += 1
        if not report.file_size_valid:
            risk_factors += 1
        if not report.path_secure:
            risk_factors += 2  # Path issues are serious
        if not report.content_secure:
            risk_factors += 1
        
        # Factor 3: Scan results
        if report.virus_scan_result == ScanResult.MALWARE:
            risk_factors += 3  # Maximum penalty
        elif report.virus_scan_result == ScanResult.SUSPICIOUS:
            risk_factors += 1
        
        if report.content_analysis_result == ScanResult.SUSPICIOUS:
            risk_factors += 0.5
        
        # Calculate normalized risk score (0.0 to 1.0)
        report.risk_score = min(risk_factors / max_risk_factors, 1.0)
        
        # Determine threat level
        if report.risk_score >= 0.8:
            report.threat_level = SecurityThreatLevel.CRITICAL
        elif report.risk_score >= 0.6:
            report.threat_level = SecurityThreatLevel.HIGH
        elif report.risk_score >= 0.3:
            report.threat_level = SecurityThreatLevel.MEDIUM
        else:
            report.threat_level = SecurityThreatLevel.LOW
    
    def _log_security_event(self, report: FileSecurityReport, client_ip: str = None):
        """Log security event for monitoring and analysis"""
        event_data = {
            'timestamp': report.scan_timestamp.isoformat(),
            'filename': report.filename,
            'file_hash': report.file_hash,
            'file_size': report.file_size,
            'client_ip': client_ip,
            'threat_level': report.threat_level.value,
            'risk_score': report.risk_score,
            'security_errors': report.security_errors,
            'security_warnings': report.security_warnings,
            'scan_duration_ms': report.scan_duration_ms,
        }
        
        if report.threat_level in [SecurityThreatLevel.HIGH, SecurityThreatLevel.CRITICAL]:
            self.security_logger.error(f"HIGH RISK FILE UPLOAD: {json.dumps(event_data)}")
        elif report.threat_level == SecurityThreatLevel.MEDIUM:
            self.security_logger.warning(f"MEDIUM RISK FILE UPLOAD: {json.dumps(event_data)}")
        else:
            self.security_logger.info(f"FILE UPLOAD: {json.dumps(event_data)}")
    
    def is_upload_safe(self, report: FileSecurityReport) -> bool:
        """Determine if file upload should be allowed based on security report"""
        # Block critical and high threat files
        if report.threat_level in [SecurityThreatLevel.CRITICAL, SecurityThreatLevel.HIGH]:
            return False
        
        # Block files with security errors
        if report.security_errors:
            return False
        
        # Block malware
        if report.virus_scan_result == ScanResult.MALWARE:
            return False
        
        # Allow files with warnings but no errors (with monitoring)
        return True
    
    def get_security_recommendations(self, report: FileSecurityReport) -> List[str]:
        """Get security recommendations based on the scan report"""
        recommendations = []
        
        if report.threat_level == SecurityThreatLevel.CRITICAL:
            recommendations.append("🚨 BLOCK: File poses critical security risk")
        elif report.threat_level == SecurityThreatLevel.HIGH:
            recommendations.append("⚠️ BLOCK: File poses high security risk")
        elif report.threat_level == SecurityThreatLevel.MEDIUM:
            recommendations.append("⚠️ CAUTION: File should be reviewed before processing")
        
        if not report.magic_number_valid:
            recommendations.append("Verify file format integrity")
        
        if report.security_warnings:
            recommendations.append("Monitor file during processing")
        
        if report.virus_scan_result == ScanResult.ERROR:
            recommendations.append("Retry malware scan with updated definitions")
        
        if not recommendations:
            recommendations.append("✅ File appears safe for processing")
        
        return recommendations

# Global instance
file_security_validator = FileUploadSecurityValidator()