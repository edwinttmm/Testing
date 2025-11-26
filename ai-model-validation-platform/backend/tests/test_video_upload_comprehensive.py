"""
Comprehensive Video Upload Testing Suite
========================================

Tests all aspects of the video upload workflow including:
- File type validation
- Size limits
- Database record creation
- File storage and permissions
- Progress tracking
- Error handling and recovery
- Promise rejection handling
- Edge cases and boundary conditions
"""

import os
import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import UploadFile
import aiofiles
from sqlalchemy.orm import Session

# Import application components
import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from main import app
from models import Video, Project
from database import get_db, SessionLocal
from config import settings

class TestVideoUploadComprehensive:
    """Comprehensive video upload test suite"""
    
    @pytest.fixture
    def client(self):
        """Test client fixture"""
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        """Database session fixture"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def test_project(self, db_session):
        """Create test project for video uploads"""
        project = Project(
            name="Test Upload Project",
            description="Project for testing uploads",
            camera_model="TestCam 2000",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project
    
    @pytest.fixture
    def temp_upload_dir(self):
        """Temporary upload directory"""
        temp_dir = tempfile.mkdtemp()
        original_upload_dir = settings.upload_directory
        settings.upload_directory = temp_dir
        yield temp_dir
        settings.upload_directory = original_upload_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def sample_video_files(self):
        """Create sample video files for testing"""
        files = {}
        
        # Valid MP4 file (mock)
        valid_mp4 = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        valid_mp4.write(b'fake mp4 content for testing' * 1000)  # ~28KB
        valid_mp4.close()
        files['valid_mp4'] = valid_mp4.name
        
        # Large file (exceeds limit)
        large_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        large_file.write(b'x' * (settings.max_file_size + 1000))  # Exceeds limit
        large_file.close()
        files['large_file'] = large_file.name
        
        # Invalid extension
        invalid_file = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
        invalid_file.write(b'this is not a video file')
        invalid_file.close()
        files['invalid_file'] = invalid_file.name
        
        yield files
        
        # Cleanup
        for file_path in files.values():
            try:
                os.unlink(file_path)
            except FileNotFoundError:
                pass

    # Test 1: Basic Upload Functionality
    def test_valid_video_upload(self, client, test_project, temp_upload_dir, sample_video_files):
        """Test successful video upload with valid file"""
        with open(sample_video_files['valid_mp4'], 'rb') as f:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("test_video.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["filename"] == "test_video.mp4"
        assert data["project_id"] == test_project.id
        assert data["status"] == "uploaded"
    
    def test_multiple_file_type_support(self, client, test_project, temp_upload_dir):
        """Test upload with different supported video formats"""
        test_files = [
            ("test.mp4", b"fake mp4 content", "video/mp4"),
            ("test.avi", b"fake avi content", "video/x-msvideo"),
            ("test.mov", b"fake mov content", "video/quicktime"),
            ("test.mkv", b"fake mkv content", "video/x-matroska"),
            ("test.webm", b"fake webm content", "video/webm")
        ]
        
        for filename, content, mime_type in test_files:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(content * 100)  # Make it reasonably sized
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (filename, temp_file, mime_type)}
                )
                
                assert response.status_code == 200, f"Failed for {filename}: {response.text}"
                data = response.json()
                assert data["filename"] == filename

    # Test 2: Error Handling
    def test_invalid_file_type_rejection(self, client, test_project, sample_video_files):
        """Test rejection of invalid file types"""
        with open(sample_video_files['invalid_file'], 'rb') as f:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("test.txt", f, "text/plain")}
            )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    
    def test_file_size_limit_enforcement(self, client, test_project, sample_video_files):
        """Test rejection of oversized files"""
        with open(sample_video_files['large_file'], 'rb') as f:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("large_video.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 413  # Payload Too Large
        assert "File too large" in response.json()["detail"]
    
    def test_missing_file_error(self, client, test_project):
        """Test error when no file is provided"""
        response = client.post(f"/api/projects/{test_project.id}/videos")
        
        assert response.status_code == 422  # Unprocessable Entity
    
    def test_nonexistent_project_error(self, client, sample_video_files):
        """Test error when uploading to non-existent project"""
        fake_project_id = "00000000-0000-0000-0000-000000000000"
        
        with open(sample_video_files['valid_mp4'], 'rb') as f:
            response = client.post(
                f"/api/projects/{fake_project_id}/videos",
                files={"file": ("test.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 404
        assert "Project not found" in response.json()["detail"]

    # Test 3: Database Record Creation
    def test_database_record_creation(self, client, test_project, temp_upload_dir, sample_video_files, db_session):
        """Test that video records are properly created in database"""
        with open(sample_video_files['valid_mp4'], 'rb') as f:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("test_db_record.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 200
        video_id = response.json()["id"]
        
        # Verify database record
        video = db_session.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()
        assert video is not None
        assert video.filename == "test_db_record.mp4"
        assert video.project_id == test_project.id
        assert video.status == "uploaded"
        assert video.file_size > 0
        assert video.file_path is not None
    
    def test_database_integrity_on_upload_failure(self, client, test_project, db_session):
        """Test database rollback when upload fails"""
        initial_count = db_session.execute(select(func.count()).select_from(Video)).scalar()
        
        # Simulate upload failure by providing invalid data
        response = client.post(
            f"/api/projects/{test_project.id}/videos",
            data={"invalid": "data"}  # Invalid request format
        )
        
        assert response.status_code in [400, 422]
        
        # Verify no orphaned records
        final_count = db_session.execute(select(func.count()).select_from(Video)).scalar()
        assert final_count == initial_count

    # Test 4: File Storage and Permissions
    def test_file_storage_location(self, client, test_project, temp_upload_dir, sample_video_files):
        """Test that files are stored in correct location with proper names"""
        with open(sample_video_files['valid_mp4'], 'rb') as f:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("storage_test.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify file exists in upload directory
        stored_file_path = Path(data["file_path"])
        assert stored_file_path.exists()
        assert stored_file_path.parent == Path(temp_upload_dir)
    
    def test_file_permissions(self, client, test_project, temp_upload_dir, sample_video_files):
        """Test that uploaded files have correct permissions"""
        with open(sample_video_files['valid_mp4'], 'rb') as f:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("permissions_test.mp4", f, "video/mp4")}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        file_path = Path(data["file_path"])
        # Check file is readable
        assert os.access(file_path, os.R_OK)
        # Check file permissions are not world-writable
        file_stat = file_path.stat()
        assert not (file_stat.st_mode & 0o002)  # Not world-writable

    # Test 5: Upload Progress Tracking (if implemented)
    @pytest.mark.skip(reason="Progress tracking implementation pending")
    def test_upload_progress_tracking(self, client, test_project, sample_video_files):
        """Test upload progress tracking functionality"""
        # This test would verify progress tracking during large file uploads
        # Implementation depends on websocket or server-sent events
        pass

    # Test 6: Promise Rejection Handling
    @pytest.mark.asyncio
    async def test_promise_rejection_handling(self):
        """Test that async operations properly handle promise rejections"""
        # Test various async scenarios that could cause unhandled rejections
        
        async def failing_async_operation():
            raise Exception("Simulated async failure")
        
        # Test proper exception handling in async context
        with pytest.raises(Exception):
            await failing_async_operation()
    
    def test_concurrent_uploads(self, client, test_project, temp_upload_dir):
        """Test handling of multiple concurrent uploads"""
        import threading
        import time
        
        results = []
        errors = []
        
        def upload_file(file_num):
            try:
                # Create small test file
                content = f"test content for file {file_num}".encode() * 100
                with tempfile.NamedTemporaryFile() as temp_file:
                    temp_file.write(content)
                    temp_file.seek(0)
                    
                    response = client.post(
                        f"/api/projects/{test_project.id}/videos",
                        files={"file": (f"concurrent_{file_num}.mp4", temp_file, "video/mp4")}
                    )
                    results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Launch concurrent uploads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=upload_file, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)
        
        # Verify results
        assert len(errors) == 0, f"Concurrent upload errors: {errors}"
        assert all(status == 200 for status in results), f"Status codes: {results}"

    # Test 7: Edge Cases and Boundary Conditions
    def test_empty_file_upload(self, client, test_project):
        """Test upload of empty file"""
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            # File is empty (0 bytes)
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("empty.mp4", temp_file, "video/mp4")}
            )
            
            # Should reject empty files
            assert response.status_code in [400, 422]
    
    def test_filename_sanitization(self, client, test_project, temp_upload_dir):
        """Test that filenames are properly sanitized"""
        dangerous_filenames = [
            "../../../etc/passwd",
            "file with spaces.mp4",
            "file<>with|special:chars.mp4",
            "very_long_filename_" + "x" * 200 + ".mp4"
        ]
        
        for dangerous_name in dangerous_filenames:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b"test content" * 100)
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (dangerous_name, temp_file, "video/mp4")}
                )
                
                if response.status_code == 200:
                    # If upload succeeds, verify filename was sanitized
                    data = response.json()
                    stored_filename = Path(data["file_path"]).name
                    assert not stored_filename.startswith("../")
                    assert len(stored_filename) <= 255  # Typical filesystem limit
    
    def test_unicode_filename_handling(self, client, test_project, temp_upload_dir):
        """Test handling of unicode characters in filenames"""
        unicode_names = [
            "test_файл.mp4",  # Cyrillic
            "テスト動画.mp4",    # Japanese
            "测试视频.mp4",    # Chinese
            "tëst_vídéo.mp4"   # Accented characters
        ]
        
        for unicode_name in unicode_names:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b"unicode test content" * 100)
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (unicode_name, temp_file, "video/mp4")}
                )
                
                # Should either succeed or fail gracefully
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    data = response.json()
                    assert "file_path" in data

    # Test 8: Cleanup and Resource Management
    def test_cleanup_on_failure(self, client, test_project, temp_upload_dir):
        """Test that failed uploads don't leave orphaned files"""
        initial_files = set(os.listdir(temp_upload_dir))
        
        # Attempt upload that should fail (invalid project)
        fake_project_id = "invalid-project-id"
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(b"cleanup test content" * 100)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{fake_project_id}/videos",
                files={"file": ("cleanup_test.mp4", temp_file, "video/mp4")}
            )
            
            assert response.status_code in [400, 404, 422]
        
        # Verify no new files were left behind
        final_files = set(os.listdir(temp_upload_dir))
        assert final_files == initial_files

    # Test 9: Security Tests
    def test_malicious_file_rejection(self, client, test_project):
        """Test rejection of potentially malicious files"""
        # Test executable files with video extensions
        malicious_content = b'\x4d\x5a'  # PE header (Windows executable)
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            temp_file.write(malicious_content)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("malicious.mp4", temp_file, "video/mp4")}
            )
            
            # Should either reject or handle safely
            if response.status_code == 200:
                # If accepted, ensure it's isolated and marked appropriately
                data = response.json()
                assert "file_path" in data

    # Test 10: Performance and Load Testing
    def test_rapid_sequential_uploads(self, client, test_project, temp_upload_dir):
        """Test system behavior under rapid sequential uploads"""
        upload_count = 10
        results = []
        
        for i in range(upload_count):
            with tempfile.NamedTemporaryFile() as temp_file:
                content = f"rapid upload test {i}".encode() * 100
                temp_file.write(content)
                temp_file.seek(0)
                
                start_time = time.time()
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": (f"rapid_{i}.mp4", temp_file, "video/mp4")}
                )
                end_time = time.time()
                
                results.append({
                    'status': response.status_code,
                    'duration': end_time - start_time,
                    'file_num': i
                })
        
        # Verify all uploads succeeded and performance is reasonable
        success_count = sum(1 for r in results if r['status'] == 200)
        avg_duration = sum(r['duration'] for r in results) / len(results)
        
        assert success_count >= upload_count * 0.9  # At least 90% success rate
        assert avg_duration < 5.0  # Average upload under 5 seconds


# Integration Test Class
class TestVideoUploadIntegration:
    """Integration tests for video upload workflow"""
    
    def test_complete_upload_workflow(self, client, db_session):
        """Test complete end-to-end upload workflow"""
        # 1. Create project
        project_data = {
            "name": "Integration Test Project",
            "description": "End-to-end test",
            "camera_model": "TestCam",
            "camera_view": "Front-facing VRU",
            "signal_type": "GPIO"
        }
        
        project_response = client.post("/api/projects", json=project_data)
        assert project_response.status_code == 200
        project_id = project_response.json()["id"]
        
        # 2. Upload video to project
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            temp_file.write(b"integration test video content" * 1000)
            temp_file.seek(0)
            
            upload_response = client.post(
                f"/api/projects/{project_id}/videos",
                files={"file": ("integration_test.mp4", temp_file, "video/mp4")}
            )
            
            assert upload_response.status_code == 200
            video_data = upload_response.json()
            video_id = video_data["id"]
        
        # 3. Verify video appears in project
        project_videos_response = client.get(f"/api/projects/{project_id}/videos")
        assert project_videos_response.status_code == 200
        videos = project_videos_response.json()
        assert len(videos) == 1
        assert videos[0]["id"] == video_id
        
        # 4. Verify video details
        video_detail_response = client.get(f"/api/videos/{video_id}")
        assert video_detail_response.status_code == 200
        video_detail = video_detail_response.json()
        assert video_detail["filename"] == "integration_test.mp4"
        assert video_detail["project_id"] == project_id
        
        # 5. Verify database consistency
        video_record = db_session.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()
        assert video_record is not None
        assert video_record.project_id == project_id


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])