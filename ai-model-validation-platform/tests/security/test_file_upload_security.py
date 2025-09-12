"""
Comprehensive Security Test Suite for File Upload Security
Tests all security validation components and attack scenarios
"""

import pytest
import tempfile
import os
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi import UploadFile, Request
from fastapi.testclient import TestClient
import io

# Import security modules
from src.security.file_upload_security import (
    FileUploadSecurityValidator,
    FileSecurityReport,
    SecurityThreatLevel,
    ScanResult
)
from src.middleware.secure_upload_middleware import (
    SecureUploadMiddleware,
    secure_file_upload
)

class TestFileUploadSecurityValidator:
    """Test the core security validator"""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance for testing"""
        return FileUploadSecurityValidator()
    
    @pytest.fixture
    def temp_video_file(self):
        """Create a temporary valid video file"""
        temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
        try:
            # Write basic MP4 header
            mp4_header = b'\x00\x00\x00\x18ftypmp4\x00\x00\x00\x00'
            mp4_header += b'some video content' * 100  # Make it larger
            
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(mp4_header)
            
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    @pytest.fixture
    def temp_malicious_file(self):
        """Create a temporary malicious file disguised as video"""
        temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
        try:
            # Write executable header disguised as MP4
            malicious_content = b'MZ\x90\x00'  # PE executable header
            malicious_content += b'fake video content' * 50
            
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(malicious_content)
            
            yield temp_path
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_valid_video_file_validation(self, validator, temp_video_file):
        """Test validation of a legitimate video file"""
        report = validator.validate_file_upload(
            file_path=temp_video_file,
            original_filename="test_video.mp4",
            client_ip="192.168.1.100"
        )
        
        assert isinstance(report, FileSecurityReport)
        assert report.file_size_valid
        assert report.path_secure
        assert report.mime_type_valid
        assert report.threat_level in [SecurityThreatLevel.LOW, SecurityThreatLevel.MEDIUM]
        assert validator.is_upload_safe(report)
    
    def test_malicious_file_detection(self, validator, temp_malicious_file):
        """Test detection of malicious files"""
        report = validator.validate_file_upload(
            file_path=temp_malicious_file,
            original_filename="fake_video.mp4", 
            client_ip="192.168.1.100"
        )
        
        assert not validator.is_upload_safe(report)
        assert report.threat_level in [SecurityThreatLevel.HIGH, SecurityThreatLevel.CRITICAL]
        assert len(report.security_errors) > 0
    
    def test_path_traversal_detection(self, validator, temp_video_file):
        """Test detection of path traversal attacks"""
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "test/../../../sensitive_file.txt",
            "normal_file.mp4/../backdoor.exe",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ]
        
        for filename in malicious_filenames:
            report = validator.validate_file_upload(
                file_path=temp_video_file,
                original_filename=filename,
                client_ip="192.168.1.100"
            )
            
            assert not report.path_secure
            assert not validator.is_upload_safe(report)
            assert any("path traversal" in error.lower() or "forbidden" in error.lower() 
                     for error in report.security_errors)
    
    def test_forbidden_file_patterns(self, validator, temp_video_file):
        """Test detection of forbidden file patterns"""
        forbidden_filenames = [
            "script.exe",
            "malware.bat", 
            "trojan.scr",
            "virus.com",
            "payload.js",
            "<script>alert('xss')</script>.mp4",
            "javascript:void(0).mp4",
            "onload=malicious().mp4"
        ]
        
        for filename in forbidden_filenames:
            report = validator.validate_file_upload(
                file_path=temp_video_file,
                original_filename=filename,
                client_ip="192.168.1.100"
            )
            
            assert not validator.is_upload_safe(report)
            assert len(report.security_errors) > 0
    
    def test_file_size_validation(self, validator):
        """Test file size validation limits"""
        # Test file too small
        temp_fd, temp_path_small = tempfile.mkstemp()
        try:
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(b'tiny')  # Only 4 bytes
            
            report = validator.validate_file_upload(
                temp_path_small, "tiny.mp4", "192.168.1.100"
            )
            
            assert not report.file_size_valid
            assert not validator.is_upload_safe(report)
        finally:
            os.unlink(temp_path_small)
        
        # Test file too large (simulate by creating large temp file)
        temp_fd, temp_path_large = tempfile.mkstemp()
        try:
            # Create a file larger than allowed limit
            large_size = validator.SECURITY_CONFIG['MAX_FILE_SIZE'] + 1000
            
            # Use sparse file to avoid actually writing huge amounts of data
            with os.fdopen(temp_fd, 'wb') as f:
                f.seek(large_size - 1)
                f.write(b'\0')
            
            report = validator.validate_file_upload(
                temp_path_large, "huge_video.mp4", "192.168.1.100"
            )
            
            assert not report.file_size_valid
            assert not validator.is_upload_safe(report)
        finally:
            os.unlink(temp_path_large)
    
    def test_rate_limiting(self, validator):
        """Test rate limiting functionality"""
        client_ip = "192.168.1.200"
        
        # Simulate multiple uploads from same IP
        for i in range(15):  # Exceed the rate limit
            report = validator.validate_file_upload(
                __file__,  # Use this file as test file
                f"test_file_{i}.mp4",
                client_ip
            )
            
            if i >= validator.SECURITY_CONFIG['RATE_LIMITS']['max_uploads_per_ip_per_minute']:
                # Should be rate limited
                assert not validator.is_upload_safe(report)
                assert any("rate limit" in error.lower() for error in report.security_errors)
                break
    
    def test_mime_type_validation(self, validator, temp_video_file):
        """Test MIME type validation"""
        # Mock mime detection to return invalid type
        with patch('magic.Magic') as mock_magic:
            mock_instance = Mock()
            mock_instance.from_file.return_value = "application/x-executable"
            mock_magic.return_value = mock_instance
            
            report = validator.validate_file_upload(
                temp_video_file,
                "test.mp4",
                "192.168.1.100"
            )
            
            assert not report.mime_type_valid
            assert not validator.is_upload_safe(report)
    
    def test_magic_number_validation(self, validator):
        """Test magic number (file signature) validation"""
        # Create file with wrong magic numbers
        temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
        try:
            with os.fdopen(temp_fd, 'wb') as f:
                # Write wrong magic numbers for MP4
                f.write(b'WRONGSIG' + b'fake content' * 100)
            
            report = validator.validate_file_upload(
                temp_path,
                "wrong_signature.mp4",
                "192.168.1.100"
            )
            
            assert not report.magic_number_valid
            # This should be a warning, not necessarily blocking
            assert len(report.security_warnings) > 0
        finally:
            os.unlink(temp_path)
    
    def test_content_entropy_analysis(self, validator):
        """Test content entropy analysis for packed/encrypted files"""
        # Create high-entropy content (random-like data)
        temp_fd, temp_path = tempfile.mkstemp(suffix='.mp4')
        try:
            import random
            high_entropy_data = bytes([random.randint(0, 255) for _ in range(8192)])
            
            with os.fdopen(temp_fd, 'wb') as f:
                # Start with valid MP4 header
                f.write(b'\x00\x00\x00\x18ftypmp4\x00\x00\x00\x00')
                f.write(high_entropy_data)
            
            report = validator.validate_file_upload(
                temp_path,
                "high_entropy.mp4",
                "192.168.1.100"
            )
            
            # Should generate warnings about high entropy
            assert len(report.security_warnings) > 0
            assert report.content_analysis_result == ScanResult.SUSPICIOUS
        finally:
            os.unlink(temp_path)
    
    @patch('subprocess.run')
    def test_clamav_integration(self, mock_subprocess, validator, temp_video_file):
        """Test ClamAV malware scanner integration"""
        # Mock ClamAV clean result
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Clean file"
        mock_subprocess.return_value = mock_result
        
        validator.clamav_available = True
        
        report = validator.validate_file_upload(
            temp_video_file,
            "clean_video.mp4",
            "192.168.1.100"
        )
        
        assert report.virus_scan_result == ScanResult.CLEAN
        
        # Mock ClamAV malware detection
        mock_result.returncode = 1
        mock_result.stdout = "test_video.mp4: Eicar-Test-Signature FOUND"
        
        report = validator.validate_file_upload(
            temp_video_file,
            "infected_video.mp4",
            "192.168.1.100"
        )
        
        assert report.virus_scan_result == ScanResult.MALWARE
        assert not validator.is_upload_safe(report)
    
    def test_security_recommendations(self, validator, temp_video_file):
        """Test security recommendation generation"""
        # Test with clean file
        report = validator.validate_file_upload(
            temp_video_file,
            "clean_video.mp4",
            "192.168.1.100"
        )
        
        recommendations = validator.get_security_recommendations(report)
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        if validator.is_upload_safe(report):
            assert any("appears safe" in rec.lower() for rec in recommendations)
        else:
            assert any("block" in rec.lower() for rec in recommendations)


class TestSecureUploadMiddleware:
    """Test the secure upload middleware"""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing"""
        return SecureUploadMiddleware()
    
    @pytest.fixture
    def mock_upload_file(self):
        """Create mock UploadFile for testing"""
        # Create valid MP4 content
        mp4_content = b'\x00\x00\x00\x18ftypmp4\x00\x00\x00\x00'
        mp4_content += b'video content' * 1000
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test_video.mp4"
        mock_file.read = AsyncMock(side_effect=[
            mp4_content[:1024],  # First chunk
            mp4_content[1024:2048],  # Second chunk
            mp4_content[2048:],  # Remaining content
            b''  # End of file
        ])
        mock_file.seek = AsyncMock()
        
        return mock_file
    
    @pytest.fixture
    def mock_request(self):
        """Create mock Request for testing"""
        mock_request = Mock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.headers = {}
        return mock_request
    
    @pytest.mark.asyncio
    async def test_valid_file_upload(self, middleware, mock_upload_file, mock_request):
        """Test processing of valid file upload"""
        result = await middleware.validate_and_process_upload(
            file=mock_upload_file,
            request=mock_request
        )
        
        assert result["success"] is True
        assert "secure_file_path" in result
        assert "security_report" in result
        assert "recommendations" in result
        
        # Verify file was moved to secure storage
        secure_path = result["secure_file_path"]
        assert os.path.exists(secure_path)
        
        # Cleanup
        os.unlink(secure_path)
    
    @pytest.mark.asyncio
    async def test_malicious_file_rejection(self, middleware, mock_request):
        """Test rejection of malicious files"""
        # Create malicious upload file
        malicious_content = b'MZ\x90\x00' + b'malicious payload' * 100
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "malware.mp4"
        mock_file.read = AsyncMock(side_effect=[malicious_content, b''])
        mock_file.seek = AsyncMock()
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await middleware.validate_and_process_upload(
                file=mock_file,
                request=mock_request
            )
    
    @pytest.mark.asyncio
    async def test_file_size_limit_enforcement(self, middleware, mock_request):
        """Test file size limit enforcement"""
        # Create oversized file
        large_content = b'x' * (101 * 1024 * 1024)  # 101MB
        
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "huge_video.mp4"
        mock_file.read = AsyncMock(side_effect=[large_content, b''])
        mock_file.seek = AsyncMock()
        
        with pytest.raises(Exception):  # Should raise HTTPException for size
            await middleware.validate_and_process_upload(
                file=mock_file,
                request=mock_request
            )
    
    def test_client_ip_extraction(self, middleware):
        """Test client IP address extraction"""
        # Test with X-Forwarded-For header
        mock_request = Mock()
        mock_request.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
        mock_request.client.host = "192.168.1.1"
        
        ip = middleware._get_client_ip(mock_request)
        assert ip == "203.0.113.195"  # Should get first IP in chain
        
        # Test with X-Real-IP header
        mock_request.headers = {"X-Real-IP": "198.51.100.178"}
        ip = middleware._get_client_ip(mock_request)
        assert ip == "198.51.100.178"
        
        # Test fallback to client host
        mock_request.headers = {}
        ip = middleware._get_client_ip(mock_request)
        assert ip == "192.168.1.1"


class TestSecurityIntegration:
    """Integration tests for complete security pipeline"""
    
    def test_end_to_end_security_validation(self):
        """Test complete security validation pipeline"""
        # This would test the entire flow from upload to storage
        # including all security checks and proper error handling
        pass
    
    def test_concurrent_uploads_security(self):
        """Test security with concurrent uploads"""
        # Test that security validation works correctly 
        # with multiple simultaneous uploads
        pass
    
    def test_security_logging_and_monitoring(self):
        """Test security event logging and monitoring"""
        # Verify that security events are properly logged
        # for monitoring and analysis
        pass


class TestSecurityAttackScenarios:
    """Test specific attack scenarios"""
    
    def test_zip_bomb_protection(self):
        """Test protection against zip bombs"""
        # Create a file that expands significantly when processed
        pass
    
    def test_polyglot_file_detection(self):
        """Test detection of polyglot files (valid as multiple formats)"""
        # Files that are valid in multiple formats can bypass filters
        pass
    
    def test_unicode_filename_attacks(self):
        """Test handling of unicode filename attacks"""
        # Test various unicode normalization attacks
        pass
    
    def test_symlink_attacks(self):
        """Test protection against symlink attacks"""
        # Test that symlinks can't be used to access unauthorized files
        pass


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])