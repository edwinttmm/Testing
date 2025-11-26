"""
Upload Error Handling and Recovery Tests
=======================================

Focused testing of error scenarios and recovery mechanisms for video uploads.
Tests unhandled promise rejections, async error handling, and system resilience.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
import aiofiles
from sqlalchemy.orm import Session

import sys
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')

from main import app
from models import Video, Project
from database import get_db, SessionLocal
from config import settings

class TestUploadErrorHandling:
    """Test suite for upload error handling and recovery"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def db_session(self):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @pytest.fixture
    def test_project(self, db_session):
        project = Project(
            name="Error Test Project",
            description="Testing error scenarios",
            camera_model="ErrorCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    # Test 1: Database Connection Failures
    @patch('main.get_db')
    def test_database_connection_failure(self, mock_get_db, client, test_project):
        """Test handling when database connection fails during upload"""
        def failing_db():
            raise Exception("Database connection failed")
        
        mock_get_db.side_effect = failing_db
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            temp_file.write(b"test content for db failure" * 100)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("db_failure_test.mp4", temp_file, "video/mp4")}
            )
            
            assert response.status_code == 500
            assert "database" in response.json()["detail"].lower()

    # Test 2: File System Errors
    @patch('aiofiles.open')
    def test_file_write_failure(self, mock_aiofiles_open, client, test_project):
        """Test handling when file write operations fail"""
        # Mock aiofiles.open to raise an exception
        mock_aiofiles_open.side_effect = OSError("Disk full")
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            temp_file.write(b"test content for write failure" * 100)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("write_failure_test.mp4", temp_file, "video/mp4")}
            )
            
            assert response.status_code == 500
            # Verify error message indicates storage issue
            assert "storage" in response.json()["detail"].lower() or "write" in response.json()["detail"].lower()

    # Test 3: Async Promise Rejection Handling
    @pytest.mark.asyncio
    async def test_unhandled_promise_rejection_prevention(self):
        """Test that async operations properly handle promise rejections"""
        
        async def failing_async_upload():
            # Simulate an async operation that fails
            await asyncio.sleep(0.01)
            raise Exception("Async upload operation failed")
        
        async def safe_upload_handler():
            try:
                await failing_async_upload()
            except Exception as e:
                # Proper exception handling prevents unhandled promise rejections
                assert str(e) == "Async upload operation failed"
                return False
            return True
        
        # Test that the handler properly catches exceptions
        result = await safe_upload_handler()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_async_upload_with_timeout(self):
        """Test async upload operations with timeout handling"""
        
        async def slow_upload():
            await asyncio.sleep(10)  # Simulates slow upload
            return "success"
        
        # Test timeout handling
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_upload(), timeout=0.1)

    # Test 4: Memory Exhaustion Scenarios
    def test_large_file_memory_handling(self, client, test_project):
        """Test system behavior when processing very large files"""
        # Create a file that would cause memory issues if loaded entirely
        large_size = 10 * 1024 * 1024  # 10MB (smaller for testing)
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            # Write in chunks to avoid memory issues in test
            chunk_size = 1024 * 1024  # 1MB chunks
            for _ in range(large_size // chunk_size):
                temp_file.write(b'x' * chunk_size)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("large_memory_test.mp4", temp_file, "video/mp4")}
            )
            
            # Should either succeed with streaming or fail gracefully
            assert response.status_code in [200, 413, 500]
            if response.status_code != 200:
                error_detail = response.json()["detail"].lower()
                assert any(keyword in error_detail for keyword in ["large", "size", "memory", "limit"])

    # Test 5: Concurrent Upload Collision Handling
    def test_concurrent_upload_name_collision(self, client, test_project):
        """Test handling when multiple uploads have the same filename"""
        import threading
        import time
        
        results = []
        
        def upload_same_name(thread_id):
            with tempfile.NamedTemporaryFile() as temp_file:
                content = f"thread {thread_id} content".encode() * 100
                temp_file.write(content)
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": ("collision_test.mp4", temp_file, "video/mp4")}
                )
                results.append({
                    'thread_id': thread_id,
                    'status': response.status_code,
                    'response': response.json() if response.status_code == 200 else None
                })
        
        # Launch concurrent uploads with same filename
        threads = []
        for i in range(3):
            thread = threading.Thread(target=upload_same_name, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=10)
        
        # Verify all uploads either succeeded with unique names or failed gracefully
        success_count = sum(1 for r in results if r['status'] == 200)
        assert success_count >= 1  # At least one should succeed
        
        # If multiple succeeded, verify they got unique filenames/paths
        successful_results = [r for r in results if r['status'] == 200]
        if len(successful_results) > 1:
            file_paths = [r['response']['file_path'] for r in successful_results]
            assert len(set(file_paths)) == len(file_paths)  # All unique

    # Test 6: Network Interruption Simulation
    @patch('fastapi.UploadFile.read')
    def test_upload_interruption_handling(self, mock_read, client, test_project):
        """Test handling when upload is interrupted"""
        # Simulate network interruption during file read
        mock_read.side_effect = ConnectionResetError("Connection lost during upload")
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            temp_file.write(b"interrupted upload test" * 100)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                files={"file": ("interrupted_test.mp4", temp_file, "video/mp4")}
            )
            
            # Should handle connection error gracefully
            assert response.status_code in [400, 500, 502, 503]

    # Test 7: Invalid Project State Handling
    def test_upload_to_deleted_project(self, client, db_session):
        """Test upload when project is deleted during upload process"""
        # Create and then delete project
        project = Project(
            name="To Be Deleted",
            description="Project that will be deleted",
            camera_model="DeleteTest",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        
        project_id = project.id
        
        # Delete the project
        db_session.delete(project)
        db_session.commit()
        
        # Try to upload to deleted project
        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            temp_file.write(b"upload to deleted project" * 100)
            temp_file.seek(0)
            
            response = client.post(
                f"/api/projects/{project_id}/videos",
                files={"file": ("deleted_project_test.mp4", temp_file, "video/mp4")}
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    # Test 8: Malformed Request Handling
    def test_malformed_upload_request(self, client, test_project):
        """Test handling of various malformed upload requests"""
        malformed_requests = [
            # Missing file data
            {},
            # Wrong field name
            {"wrong_field": "data"},
            # Multiple files when expecting single
            {"file": ["file1.mp4", "file2.mp4"]},
        ]
        
        for malformed_data in malformed_requests:
            response = client.post(
                f"/api/projects/{test_project.id}/videos",
                data=malformed_data
            )
            
            assert response.status_code in [400, 422]
            assert "detail" in response.json()

    # Test 9: Resource Cleanup on Failure
    def test_cleanup_after_processing_failure(self, client, test_project, db_session):
        """Test that resources are cleaned up when processing fails"""
        upload_dir = settings.upload_directory
        initial_file_count = len(os.listdir(upload_dir)) if os.path.exists(upload_dir) else 0
        initial_db_count = db_session.execute(select(func.count()).select_from(Video)).scalar()
        
        # Mock a processing failure after file upload
        with patch('main.process_video_metadata') as mock_process:
            mock_process.side_effect = Exception("Video processing failed")
            
            with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
                temp_file.write(b"cleanup test content" * 100)
                temp_file.seek(0)
                
                response = client.post(
                    f"/api/projects/{test_project.id}/videos",
                    files={"file": ("cleanup_test.mp4", temp_file, "video/mp4")}
                )
                
                # Should fail gracefully
                assert response.status_code in [500, 400]
        
        # Verify cleanup occurred
        final_file_count = len(os.listdir(upload_dir)) if os.path.exists(upload_dir) else 0
        final_db_count = db_session.execute(select(func.count()).select_from(Video)).scalar()
        
        # Files and DB records should be cleaned up
        assert final_file_count == initial_file_count
        assert final_db_count == initial_db_count

    # Test 10: Error Recovery and Retry Logic
    @pytest.mark.asyncio
    async def test_upload_retry_mechanism(self):
        """Test retry logic for failed upload operations"""
        
        attempt_count = 0
        
        async def flaky_upload():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count < 3:
                raise Exception(f"Upload failed on attempt {attempt_count}")
            return "success"
        
        async def retry_upload(max_retries=3):
            for attempt in range(max_retries):
                try:
                    result = await flaky_upload()
                    return result
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await asyncio.sleep(0.1)  # Brief delay between retries
        
        # Test successful retry
        result = await retry_upload()
        assert result == "success"
        assert attempt_count == 3  # Should have taken 3 attempts

    # Test 11: Validation Error Recovery
    def test_validation_error_handling(self, client, test_project):
        """Test handling of various validation errors"""
        validation_scenarios = [
            # Empty filename
            ("", "video/mp4"),
            # Filename with null bytes
            ("test\x00.mp4", "video/mp4"),
            # Extremely long filename
            ("x" * 1000 + ".mp4", "video/mp4"),
            # Invalid MIME type
            ("test.mp4", "application/evil"),
        ]
        
        for filename, mime_type in validation_scenarios:
            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(b"validation test content" * 50)
                temp_file.seek(0)
                
                try:
                    response = client.post(
                        f"/api/projects/{test_project.id}/videos",
                        files={"file": (filename, temp_file, mime_type)}
                    )
                    
                    # Should either reject invalid input or sanitize it
                    if response.status_code not in [200]:
                        assert response.status_code in [400, 422]
                        assert "detail" in response.json()
                
                except Exception as e:
                    # If exception occurs, it should be handled gracefully
                    pytest.fail(f"Unhandled exception for {filename}, {mime_type}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])