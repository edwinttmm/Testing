"""
Comprehensive Test Suite for Enhanced Upload System
Tests all components: chunked upload service, validation pipeline,
frontend integration, and error handling.
"""

import pytest
import tempfile
import os
import shutil
import asyncio
import hashlib
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any

# Import the modules to test
import sys
sys.path.append('/home/user/Testing/src')

from enhanced_upload_service import EnhancedUploadService, UploadConfiguration, UploadStatus, ChunkStatus
from upload_validation_pipeline import FileValidator, ValidationStatus, validate_uploaded_file, create_validation_config
from upload_middleware import create_upload_router


class TestEnhancedUploadService:
    """Test the enhanced upload service with chunked uploads"""

    @pytest.fixture
    def upload_config(self):
        """Create test upload configuration"""
        return UploadConfiguration(
            max_file_size=50 * 1024 * 1024,  # 50MB for testing
            chunk_size=5 * 1024 * 1024,     # 5MB chunks
            max_concurrent_chunks=3,
            upload_timeout=300,              # 5 minutes for testing
            temp_directory="test_temp_uploads",
            final_directory="test_uploads",
            enable_integrity_check=True
        )

    @pytest.fixture
    def upload_service(self, upload_config):
        """Create upload service instance"""
        service = EnhancedUploadService(upload_config)
        yield service
        # Cleanup
        asyncio.create_task(service.shutdown())

    @pytest.fixture
    def temp_test_dir(self):
        """Create temporary test directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_video_file(self, temp_test_dir):
        """Create a test video file"""
        file_path = os.path.join(temp_test_dir, 'test_video.mp4')
        # Create a 10MB test file with known content
        with open(file_path, 'wb') as f:
            test_data = b'TEST_VIDEO_DATA_' * (1024 * 64)  # Repeating pattern
            for i in range(160):  # 10MB total (160 * 64KB)
                chunk_data = test_data + bytes([i % 256])
                f.write(chunk_data)
        return file_path

    @pytest.mark.asyncio
    async def test_upload_initiation(self, upload_service, test_video_file):
        """Test initiating a chunked upload"""
        file_size = os.path.getsize(test_video_file)
        filename = "test_video.mp4"
        
        result = await upload_service.initiate_upload(
            filename=filename,
            file_size=file_size,
            content_type="video/mp4"
        )
        
        assert "upload_id" in result
        assert result["chunk_size"] == upload_service.config.chunk_size
        assert result["total_chunks"] == (file_size + upload_service.config.chunk_size - 1) // upload_service.config.chunk_size
        
        # Verify session was created
        upload_id = result["upload_id"]
        session = upload_service.active_uploads.get(upload_id)
        assert session is not None
        assert session.filename != filename  # Should be secure filename
        assert session.original_filename == filename
        assert session.total_size == file_size
        assert session.status == UploadStatus.INITIATED

    @pytest.mark.asyncio
    async def test_single_chunk_upload(self, upload_service, test_video_file):
        """Test uploading a single chunk"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Read first chunk
        with open(test_video_file, 'rb') as f:
            chunk_data = f.read(upload_service.config.chunk_size)
        
        # Calculate chunk hash
        chunk_hash = hashlib.md5(chunk_data).hexdigest()
        
        # Upload chunk
        result = await upload_service.upload_chunk(
            upload_id=upload_id,
            chunk_number=0,
            chunk_data=chunk_data,
            chunk_hash=chunk_hash,
            hash_algorithm="md5"
        )
        
        assert result["upload_id"] == upload_id
        assert result["chunk_number"] == 0
        assert result["chunk_status"] == ChunkStatus.COMPLETED.value
        assert result["uploaded_size"] == len(chunk_data)
        assert result["progress_percentage"] > 0
        
        # Verify chunk was stored
        session = upload_service.active_uploads[upload_id]
        assert 0 in session.chunks
        assert session.chunks[0].status == ChunkStatus.COMPLETED
        assert session.status == UploadStatus.UPLOADING

    @pytest.mark.asyncio
    async def test_complete_upload_workflow(self, upload_service, test_video_file):
        """Test complete upload workflow with multiple chunks"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        total_chunks = init_result["total_chunks"]
        
        # Upload all chunks
        with open(test_video_file, 'rb') as f:
            for chunk_number in range(total_chunks):
                chunk_data = f.read(upload_service.config.chunk_size)
                if not chunk_data:
                    break
                
                chunk_hash = hashlib.md5(chunk_data).hexdigest()
                
                result = await upload_service.upload_chunk(
                    upload_id=upload_id,
                    chunk_number=chunk_number,
                    chunk_data=chunk_data,
                    chunk_hash=chunk_hash
                )
                
                assert result["chunk_status"] == ChunkStatus.COMPLETED.value
        
        # Verify upload completed
        session = upload_service.active_uploads[upload_id]
        assert session.status == UploadStatus.COMPLETED
        assert len(session.chunks) == total_chunks
        assert all(chunk.status == ChunkStatus.COMPLETED for chunk in session.chunks.values())
        
        # Verify final file exists
        assert os.path.exists(session.final_file_path)
        final_size = os.path.getsize(session.final_file_path)
        assert final_size == file_size

    @pytest.mark.asyncio
    async def test_upload_with_hash_mismatch(self, upload_service, test_video_file):
        """Test upload with incorrect chunk hash"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Read first chunk
        with open(test_video_file, 'rb') as f:
            chunk_data = f.read(upload_service.config.chunk_size)
        
        # Upload with wrong hash
        with pytest.raises(Exception) as exc_info:
            await upload_service.upload_chunk(
                upload_id=upload_id,
                chunk_number=0,
                chunk_data=chunk_data,
                chunk_hash="wrong_hash",
                hash_algorithm="md5"
            )
        
        assert "hash mismatch" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_upload_status_tracking(self, upload_service, test_video_file):
        """Test upload status and progress tracking"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Check initial status
        status = await upload_service.get_upload_status(upload_id)
        assert status is not None
        assert status["upload_id"] == upload_id
        assert status["status"] == UploadStatus.INITIATED.value
        assert status["progress_percentage"] == 0
        
        # Upload first chunk
        with open(test_video_file, 'rb') as f:
            chunk_data = f.read(upload_service.config.chunk_size)
        
        await upload_service.upload_chunk(
            upload_id=upload_id,
            chunk_number=0,
            chunk_data=chunk_data
        )
        
        # Check updated status
        status = await upload_service.get_upload_status(upload_id)
        assert status["status"] == UploadStatus.UPLOADING.value
        assert status["progress_percentage"] > 0
        assert status["uploaded_size"] == len(chunk_data)
        assert status["completed_chunks"] == 1

    @pytest.mark.asyncio
    async def test_upload_cancellation(self, upload_service, test_video_file):
        """Test cancelling an active upload"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Cancel upload
        success = await upload_service.cancel_upload(upload_id)
        assert success is True
        
        # Verify upload was cancelled
        status = await upload_service.get_upload_status(upload_id)
        assert status is None  # Should be cleaned up

    @pytest.mark.asyncio
    async def test_retry_failed_chunks(self, upload_service, test_video_file):
        """Test retrying failed chunks"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Manually mark some chunks as failed for testing
        session = upload_service.active_uploads[upload_id]
        from enhanced_upload_service import ChunkInfo
        session.chunks[0] = ChunkInfo(chunk_number=0, size=1024, status=ChunkStatus.FAILED)
        session.chunks[1] = ChunkInfo(chunk_number=1, size=1024, status=ChunkStatus.FAILED)
        
        # Retry failed chunks
        result = await upload_service.retry_failed_chunks(upload_id)
        assert result["retryable_chunks"] == 2
        assert 0 in result["chunk_numbers"]
        assert 1 in result["chunk_numbers"]
        
        # Verify chunks were reset to pending
        assert session.chunks[0].status == ChunkStatus.PENDING
        assert session.chunks[1].status == ChunkStatus.PENDING

    @pytest.mark.asyncio
    async def test_file_size_validation(self, upload_service):
        """Test file size validation"""
        # Test file too large
        with pytest.raises(Exception) as exc_info:
            await upload_service.initiate_upload(
                filename="huge_file.mp4",
                file_size=upload_service.config.max_file_size + 1,
                content_type="video/mp4"
            )
        assert "exceeds maximum allowed size" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_timeout_cleanup(self, upload_service, test_video_file):
        """Test cleanup of timed out uploads"""
        file_size = os.path.getsize(test_video_file)
        
        # Initiate upload
        init_result = await upload_service.initiate_upload(
            filename="test_video.mp4",
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Manually set last activity to past timeout
        session = upload_service.active_uploads[upload_id]
        session.last_activity = time.time() - upload_service.config.upload_timeout - 1
        
        # Trigger cleanup
        await upload_service._cleanup_expired_uploads()
        
        # Verify upload was cleaned up
        assert upload_id not in upload_service.active_uploads


class TestFileValidationPipeline:
    """Test the file validation pipeline"""

    @pytest.fixture
    def validator(self):
        """Create file validator instance"""
        config = create_validation_config(
            max_file_size=100 * 1024 * 1024,  # 100MB
            enable_virus_scan=False,  # Disable for testing
            enable_deep_inspection=True
        )
        return FileValidator(config)

    @pytest.fixture
    def temp_test_dir(self):
        """Create temporary test directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def valid_video_file(self, temp_test_dir):
        """Create a valid video file for testing"""
        file_path = os.path.join(temp_test_dir, 'valid_video.mp4')
        # Create a minimal valid MP4 file structure (simplified)
        with open(file_path, 'wb') as f:
            # MP4 header (simplified)
            f.write(b'\x00\x00\x00\x20ftypmp42')  # ftyp box
            f.write(b'\x00\x00\x00\x00mp42isom')  # brand
            f.write(b'A' * 1024)  # Some data
        return file_path

    @pytest.fixture
    def invalid_file(self, temp_test_dir):
        """Create an invalid file for testing"""
        file_path = os.path.join(temp_test_dir, 'invalid_file.txt')
        with open(file_path, 'w') as f:
            f.write("This is not a video file")
        return file_path

    @pytest.mark.asyncio
    async def test_valid_file_validation(self, validator, valid_video_file):
        """Test validation of a valid video file"""
        result = await validator.validate_file(valid_video_file)
        
        assert result.file_path == valid_video_file
        assert result.status in [ValidationStatus.PASSED, ValidationStatus.WARNING]
        assert result.metadata is not None
        assert result.metadata.filename == os.path.basename(valid_video_file)
        assert result.metadata.file_size > 0
        assert result.metadata.hash_md5 is not None
        assert result.metadata.hash_sha256 is not None
        assert result.processing_time > 0

    @pytest.mark.asyncio
    async def test_invalid_file_validation(self, validator, invalid_file):
        """Test validation of an invalid file"""
        result = await validator.validate_file(invalid_file)
        
        assert result.file_path == invalid_file
        assert result.status == ValidationStatus.FAILED
        assert len(result.errors) > 0
        
        # Should have extension error
        extension_errors = [e for e in result.errors if e['error_code'] == 'INVALID_EXTENSION']
        assert len(extension_errors) > 0

    @pytest.mark.asyncio
    async def test_nonexistent_file_validation(self, validator):
        """Test validation of non-existent file"""
        result = await validator.validate_file("/nonexistent/file.mp4")
        
        assert result.status == ValidationStatus.FAILED
        assert len(result.errors) > 0
        
        # Should have file not found error
        not_found_errors = [e for e in result.errors if e['error_code'] == 'FILE_NOT_FOUND']
        assert len(not_found_errors) > 0

    @pytest.mark.asyncio
    async def test_file_size_validation(self, validator, temp_test_dir):
        """Test file size validation"""
        # Create file that's too large
        large_file = os.path.join(temp_test_dir, 'large_file.mp4')
        with open(large_file, 'wb') as f:
            f.write(b'A' * (validator.config['max_file_size'] + 1))
        
        result = await validator.validate_file(large_file)
        
        assert result.status == ValidationStatus.FAILED
        size_errors = [e for e in result.errors if e['error_code'] == 'FILE_TOO_LARGE']
        assert len(size_errors) > 0

    @pytest.mark.asyncio
    async def test_metadata_extraction(self, validator, valid_video_file):
        """Test metadata extraction"""
        result = await validator.validate_file(valid_video_file)
        
        assert result.metadata is not None
        assert result.metadata.filename == os.path.basename(valid_video_file)
        assert result.metadata.file_size == os.path.getsize(valid_video_file)
        assert result.metadata.mime_type is not None
        assert result.metadata.file_extension == '.mp4'
        assert len(result.metadata.hash_md5) == 32
        assert len(result.metadata.hash_sha256) == 64

    @pytest.mark.asyncio
    async def test_content_analysis(self, validator, valid_video_file):
        """Test content analysis with OpenCV"""
        # Mock OpenCV to avoid dependency issues in testing
        with patch('cv2.VideoCapture') as mock_cv2:
            mock_cap = Mock()
            mock_cap.isOpened.return_value = True
            mock_cap.read.return_value = (True, Mock())
            mock_cv2.return_value = mock_cap
            
            result = await validator.validate_file(valid_video_file)
            
            # Should complete without content errors if OpenCV works
            content_errors = [e for e in result.errors if 'VIDEO_UNREADABLE' in e['error_code']]
            assert len(content_errors) == 0

    @pytest.mark.asyncio
    async def test_additional_checks(self, validator, valid_video_file):
        """Test additional validation checks"""
        additional_checks = ['codec_compatibility', 'audio_track_validation']
        
        # Mock ffprobe for additional checks
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b'{"streams": [{"codec_type": "video", "codec_name": "h264"}]}', b'')
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await validator.validate_file(valid_video_file, additional_checks)
            
            # Should complete additional checks
            assert result.status in [ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.FAILED]

    @pytest.mark.asyncio
    async def test_validation_config_creation(self):
        """Test validation configuration creation"""
        config = create_validation_config(
            max_file_size=200 * 1024 * 1024,
            max_duration=3600,
            enable_virus_scan=True,
            enable_deep_inspection=False
        )
        
        assert config['max_file_size'] == 200 * 1024 * 1024
        assert config['max_duration'] == 3600
        assert config['enable_virus_scan'] is True
        assert config['deep_inspection_enabled'] is False

    def test_validation_summary_generation(self, validator, temp_test_dir):
        """Test validation summary generation"""
        # Create a simple validation result
        from upload_validation_pipeline import ValidationResult, FileMetadata
        
        metadata = FileMetadata(
            filename="test.mp4",
            file_size=1024,
            mime_type="video/mp4",
            file_extension=".mp4",
            hash_md5="test_hash",
            hash_sha256="test_hash_256",
            created_at=time.time()
        )
        
        result = ValidationResult(
            file_path="/test/path.mp4",
            status=ValidationStatus.PASSED,
            metadata=metadata,
            processing_time=1.5
        )
        
        summary = validator.get_validation_summary(result)
        
        assert summary['file_path'] == "/test/path.mp4"
        assert summary['status'] == 'passed'
        assert summary['processing_time'] == 1.5
        assert summary['error_count'] == 0
        assert summary['warning_count'] == 0
        assert summary['metadata']['filename'] == "test.mp4"
        assert isinstance(summary['recommendations'], list)


class TestUploadIntegration:
    """Test integration between upload service and validation pipeline"""

    @pytest.fixture
    def temp_test_dir(self):
        """Create temporary test directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def test_video_file(self, temp_test_dir):
        """Create a test video file"""
        file_path = os.path.join(temp_test_dir, 'integration_test.mp4')
        # Create a valid-looking MP4 file
        with open(file_path, 'wb') as f:
            f.write(b'\x00\x00\x00\x20ftypmp42')  # MP4 header
            f.write(b'\x00\x00\x00\x00mp42isom')  # Brand
            f.write(b'A' * (2 * 1024 * 1024))    # 2MB of data
        return file_path

    @pytest.mark.asyncio
    async def test_integrated_upload_and_validation(self, test_video_file):
        """Test complete workflow: upload + validation"""
        # Setup upload service
        upload_config = UploadConfiguration(
            max_file_size=10 * 1024 * 1024,  # 10MB
            chunk_size=1 * 1024 * 1024,     # 1MB chunks
            temp_directory="test_temp",
            final_directory="test_final"
        )
        upload_service = EnhancedUploadService(upload_config)
        
        try:
            # Step 1: Initiate upload
            file_size = os.path.getsize(test_video_file)
            init_result = await upload_service.initiate_upload(
                filename="integration_test.mp4",
                file_size=file_size,
                content_type="video/mp4"
            )
            upload_id = init_result["upload_id"]
            
            # Step 2: Upload chunks
            with open(test_video_file, 'rb') as f:
                chunk_number = 0
                while True:
                    chunk_data = f.read(upload_config.chunk_size)
                    if not chunk_data:
                        break
                    
                    await upload_service.upload_chunk(
                        upload_id=upload_id,
                        chunk_number=chunk_number,
                        chunk_data=chunk_data
                    )
                    chunk_number += 1
            
            # Step 3: Verify upload completed
            session = upload_service.active_uploads[upload_id]
            assert session.status == UploadStatus.COMPLETED
            assert os.path.exists(session.final_file_path)
            
            # Step 4: Validate uploaded file
            validation_config = create_validation_config(enable_virus_scan=False)
            validation_result = await validate_uploaded_file(session.final_file_path, validation_config)
            
            assert validation_result.status in [ValidationStatus.PASSED, ValidationStatus.WARNING]
            assert validation_result.metadata is not None
            assert validation_result.metadata.file_size == file_size
            
        finally:
            await upload_service.shutdown()

    @pytest.mark.asyncio
    async def test_upload_with_validation_failure(self, temp_test_dir):
        """Test upload workflow when validation fails"""
        # Create invalid file
        invalid_file = os.path.join(temp_test_dir, 'invalid.mp4')
        with open(invalid_file, 'w') as f:
            f.write("This is not a valid video file")
        
        # Setup upload service
        upload_config = UploadConfiguration(
            max_file_size=10 * 1024 * 1024,
            chunk_size=1024,
            temp_directory="test_temp",
            final_directory="test_final"
        )
        upload_service = EnhancedUploadService(upload_config)
        
        try:
            # Upload the invalid file
            file_size = os.path.getsize(invalid_file)
            init_result = await upload_service.initiate_upload(
                filename="invalid.mp4",
                file_size=file_size,
                content_type="video/mp4"
            )
            upload_id = init_result["upload_id"]
            
            # Upload single chunk
            with open(invalid_file, 'rb') as f:
                chunk_data = f.read()
            
            await upload_service.upload_chunk(
                upload_id=upload_id,
                chunk_number=0,
                chunk_data=chunk_data
            )
            
            # Validate the uploaded file
            session = upload_service.active_uploads[upload_id]
            validation_config = create_validation_config(enable_virus_scan=False)
            validation_result = await validate_uploaded_file(session.final_file_path, validation_config)
            
            # Should fail validation
            assert validation_result.status == ValidationStatus.FAILED
            assert len(validation_result.errors) > 0
            
        finally:
            await upload_service.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_uploads(self, temp_test_dir):
        """Test multiple concurrent uploads"""
        # Create multiple test files
        test_files = []
        for i in range(3):
            file_path = os.path.join(temp_test_dir, f'concurrent_test_{i}.mp4')
            with open(file_path, 'wb') as f:
                f.write(b'\x00\x00\x00\x20ftypmp42')  # MP4 header
                f.write(b'A' * (1024 * i + 1024))     # Different sizes
            test_files.append(file_path)
        
        # Setup upload service
        upload_config = UploadConfiguration(
            max_file_size=10 * 1024 * 1024,
            chunk_size=1024,
            max_concurrent_chunks=5,
            temp_directory="test_temp",
            final_directory="test_final"
        )
        upload_service = EnhancedUploadService(upload_config)
        
        try:
            # Start concurrent uploads
            upload_tasks = []
            for i, file_path in enumerate(test_files):
                task = asyncio.create_task(self._upload_file(upload_service, file_path, f"concurrent_{i}.mp4"))
                upload_tasks.append(task)
            
            # Wait for all uploads to complete
            upload_ids = await asyncio.gather(*upload_tasks)
            
            # Verify all uploads completed
            for upload_id in upload_ids:
                session = upload_service.active_uploads.get(upload_id)
                assert session is not None
                assert session.status == UploadStatus.COMPLETED
            
        finally:
            await upload_service.shutdown()

    async def _upload_file(self, service, file_path, filename):
        """Helper method to upload a single file"""
        file_size = os.path.getsize(file_path)
        
        # Initiate upload
        init_result = await service.initiate_upload(
            filename=filename,
            file_size=file_size,
            content_type="video/mp4"
        )
        upload_id = init_result["upload_id"]
        
        # Upload chunks
        with open(file_path, 'rb') as f:
            chunk_number = 0
            while True:
                chunk_data = f.read(service.config.chunk_size)
                if not chunk_data:
                    break
                
                await service.upload_chunk(
                    upload_id=upload_id,
                    chunk_number=chunk_number,
                    chunk_data=chunk_data
                )
                chunk_number += 1
        
        return upload_id


class TestPerformanceAndScalability:
    """Test performance and scalability aspects"""

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_large_file_upload_performance(self, tmp_path):
        """Test upload performance with large files"""
        # Create a 50MB test file
        large_file = tmp_path / "large_test.mp4"
        with open(large_file, 'wb') as f:
            # Write 50MB of data in chunks
            chunk = b'A' * (1024 * 1024)  # 1MB chunk
            for _ in range(50):
                f.write(chunk)
        
        upload_config = UploadConfiguration(
            max_file_size=100 * 1024 * 1024,  # 100MB
            chunk_size=5 * 1024 * 1024,      # 5MB chunks
            max_concurrent_chunks=3
        )
        upload_service = EnhancedUploadService(upload_config)
        
        try:
            start_time = time.time()
            
            # Upload the large file
            file_size = os.path.getsize(large_file)
            init_result = await upload_service.initiate_upload(
                filename="large_test.mp4",
                file_size=file_size,
                content_type="video/mp4"
            )
            upload_id = init_result["upload_id"]
            
            # Upload all chunks
            with open(large_file, 'rb') as f:
                chunk_number = 0
                while True:
                    chunk_data = f.read(upload_config.chunk_size)
                    if not chunk_data:
                        break
                    
                    await upload_service.upload_chunk(
                        upload_id=upload_id,
                        chunk_number=chunk_number,
                        chunk_data=chunk_data
                    )
                    chunk_number += 1
            
            end_time = time.time()
            upload_time = end_time - start_time
            
            # Verify upload completed
            session = upload_service.active_uploads[upload_id]
            assert session.status == UploadStatus.COMPLETED
            
            # Performance assertions (adjust based on expected performance)
            # Upload should complete within reasonable time
            assert upload_time < 60  # Should complete within 60 seconds
            
            # Calculate throughput
            throughput_mbps = (file_size / (1024 * 1024)) / upload_time
            print(f"Upload throughput: {throughput_mbps:.2f} MB/s")
            
            # Throughput should be reasonable (>1 MB/s for local testing)
            assert throughput_mbps > 1.0
            
        finally:
            await upload_service.shutdown()

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_memory_usage_during_upload(self, tmp_path):
        """Test memory usage remains reasonable during large uploads"""
        import psutil
        
        # Create test file
        test_file = tmp_path / "memory_test.mp4"
        with open(test_file, 'wb') as f:
            f.write(b'A' * (10 * 1024 * 1024))  # 10MB file
        
        upload_config = UploadConfiguration(
            max_file_size=50 * 1024 * 1024,
            chunk_size=1 * 1024 * 1024,  # Smaller chunks to test memory usage
        )
        upload_service = EnhancedUploadService(upload_config)
        
        try:
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Upload file
            file_size = os.path.getsize(test_file)
            init_result = await upload_service.initiate_upload(
                filename="memory_test.mp4",
                file_size=file_size,
                content_type="video/mp4"
            )
            upload_id = init_result["upload_id"]
            
            max_memory = initial_memory
            
            with open(test_file, 'rb') as f:
                chunk_number = 0
                while True:
                    chunk_data = f.read(upload_config.chunk_size)
                    if not chunk_data:
                        break
                    
                    await upload_service.upload_chunk(
                        upload_id=upload_id,
                        chunk_number=chunk_number,
                        chunk_data=chunk_data
                    )
                    
                    # Check memory usage
                    current_memory = process.memory_info().rss / 1024 / 1024  # MB
                    max_memory = max(max_memory, current_memory)
                    
                    chunk_number += 1
            
            # Memory usage should not increase dramatically
            memory_increase = max_memory - initial_memory
            print(f"Memory increase during upload: {memory_increase:.2f} MB")
            
            # Should not use more than 50MB additional memory for a 10MB file
            assert memory_increase < 50
            
        finally:
            await upload_service.shutdown()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s", "--tb=short"])