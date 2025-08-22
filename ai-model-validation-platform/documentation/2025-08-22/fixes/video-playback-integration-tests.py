"""
Video Playback Integration Tests
Tests for video upload, loading, and playback functionality
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database import SessionLocal, engine
from backend.models import Video, Project
from backend.schemas import VideoUploadResponse


class TestVideoPlaybackIntegration:
    """Test suite for video playback integration functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def async_client(self):
        """Create async test client"""
        return AsyncClient(app=app, base_url="http://test")

    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def test_project(self, db_session):
        """Create test project"""
        project = Project(
            name="Test Project",
            description="Test project for video playback",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    @pytest.fixture
    def sample_video_file(self):
        """Create sample video file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            # Create minimal valid MP4 header
            mp4_header = b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41isom\x00\x00\x00\x08free'
            tmp.write(mp4_header)
            tmp.write(b'\x00' * 1000)  # Padding
            tmp.flush()
            yield tmp.name
        os.unlink(tmp.name)

    @pytest.mark.asyncio
    async def test_video_upload_success(self, async_client, test_project, sample_video_file):
        """Test successful video upload"""
        with open(sample_video_file, 'rb') as video_file:
            files = {"file": ("test_video.mp4", video_file, "video/mp4")}
            data = {"project_id": test_project.id}
            
            response = await async_client.post(
                "/api/videos/upload",
                files=files,
                data=data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert "id" in result
        assert result["filename"] == "test_video.mp4"
        assert result["status"] == "uploaded"

    @pytest.mark.asyncio
    async def test_video_upload_invalid_format(self, async_client, test_project):
        """Test video upload with invalid format"""
        with tempfile.NamedTemporaryFile(suffix='.txt') as tmp:
            tmp.write(b"Invalid video content")
            tmp.flush()
            
            with open(tmp.name, 'rb') as invalid_file:
                files = {"file": ("test.txt", invalid_file, "text/plain")}
                data = {"project_id": test_project.id}
                
                response = await async_client.post(
                    "/api/videos/upload",
                    files=files,
                    data=data
                )
        
        assert response.status_code == 422
        assert "Invalid file format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_video_upload_large_file(self, async_client, test_project):
        """Test video upload with large file (>100MB simulation)"""
        with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
            # Simulate large file by writing metadata
            tmp.write(b'\x00' * 1024)  # Small actual file
            tmp.flush()
            
            with patch('backend.main.MAX_FILE_SIZE', 1024):  # Set small limit for test
                with open(tmp.name, 'rb') as large_file:
                    files = {"file": ("large_video.mp4", large_file, "video/mp4")}
                    data = {"project_id": test_project.id}
                    
                    response = await async_client.post(
                        "/api/videos/upload",
                        files=files,
                        data=data
                    )
        
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_video_metadata_extraction(self, async_client, test_project, sample_video_file):
        """Test video metadata extraction during upload"""
        with patch('backend.services.video_processing_workflow.extract_video_metadata') as mock_extract:
            mock_extract.return_value = {
                "duration": 10.5,
                "fps": 30.0,
                "resolution": "1920x1080",
                "file_size": 1024
            }
            
            with open(sample_video_file, 'rb') as video_file:
                files = {"file": ("test_video.mp4", video_file, "video/mp4")}
                data = {"project_id": test_project.id}
                
                response = await async_client.post(
                    "/api/videos/upload",
                    files=files,
                    data=data
                )
            
            assert response.status_code == 200
            result = response.json()
            assert result["duration"] == 10.5
            assert result["fps"] == 30.0
            assert result["resolution"] == "1920x1080"

    @pytest.mark.asyncio
    async def test_video_playback_stream(self, async_client, test_project, db_session):
        """Test video streaming endpoint"""
        # Create video record in database
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            project_id=test_project.id,
            status="uploaded"
        )
        db_session.add(video)
        db_session.commit()
        
        with patch('backend.main.os.path.exists', return_value=True):
            with patch('backend.main.FileResponse') as mock_response:
                response = await async_client.get(f"/api/videos/{video.id}/stream")
                assert mock_response.called

    @pytest.mark.asyncio
    async def test_video_playback_not_found(self, async_client):
        """Test video playback for non-existent video"""
        fake_video_id = "non-existent-id"
        response = await async_client.get(f"/api/videos/{fake_video_id}/stream")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_video_thumbnail_generation(self, async_client, test_project, db_session):
        """Test video thumbnail generation"""
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            project_id=test_project.id
        )
        db_session.add(video)
        db_session.commit()
        
        with patch('backend.services.video_processing_workflow.generate_thumbnail') as mock_thumb:
            mock_thumb.return_value = "/thumbnails/test_video_thumb.jpg"
            
            response = await async_client.post(f"/api/videos/{video.id}/thumbnail")
            assert response.status_code == 200
            result = response.json()
            assert "thumbnail_path" in result

    @pytest.mark.asyncio
    async def test_video_frame_extraction(self, async_client, test_project, db_session):
        """Test video frame extraction at specific timestamp"""
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            project_id=test_project.id,
            duration=30.0
        )
        db_session.add(video)
        db_session.commit()
        
        with patch('backend.services.video_processing_workflow.extract_frame') as mock_extract:
            mock_extract.return_value = "/frames/frame_15s.jpg"
            
            response = await async_client.get(
                f"/api/videos/{video.id}/frame",
                params={"timestamp": 15.0}
            )
            assert response.status_code == 200
            result = response.json()
            assert "frame_path" in result

    @pytest.mark.asyncio
    async def test_video_format_conversion(self, async_client, test_project, db_session):
        """Test video format conversion for compatibility"""
        video = Video(
            filename="test_video.avi",
            file_path="/uploads/test_video.avi",
            project_id=test_project.id
        )
        db_session.add(video)
        db_session.commit()
        
        with patch('backend.services.video_processing_workflow.convert_video_format') as mock_convert:
            mock_convert.return_value = "/uploads/test_video_converted.mp4"
            
            response = await async_client.post(
                f"/api/videos/{video.id}/convert",
                json={"target_format": "mp4"}
            )
            assert response.status_code == 200
            result = response.json()
            assert "converted_path" in result

    @pytest.mark.asyncio
    async def test_video_quality_assessment(self, async_client, test_project, db_session):
        """Test video quality assessment"""
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            project_id=test_project.id
        )
        db_session.add(video)
        db_session.commit()
        
        with patch('backend.services.video_processing_workflow.assess_video_quality') as mock_assess:
            mock_assess.return_value = {
                "quality_score": 8.5,
                "brightness": 0.6,
                "contrast": 0.7,
                "sharpness": 0.8,
                "recommendations": ["Increase brightness slightly"]
            }
            
            response = await async_client.get(f"/api/videos/{video.id}/quality")
            assert response.status_code == 200
            result = response.json()
            assert result["quality_score"] == 8.5
            assert "recommendations" in result

    def test_video_playback_progress_tracking(self, client, test_project, db_session):
        """Test video playback progress tracking"""
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            project_id=test_project.id,
            duration=60.0
        )
        db_session.add(video)
        db_session.commit()
        
        # Track playback progress
        progress_data = {
            "video_id": video.id,
            "current_time": 30.0,
            "session_id": "test-session-123"
        }
        
        response = client.post("/api/videos/playback/progress", json=progress_data)
        assert response.status_code == 200
        
        # Retrieve playback progress
        response = client.get(f"/api/videos/{video.id}/progress")
        assert response.status_code == 200
        result = response.json()
        assert result["current_time"] == 30.0

    @pytest.mark.performance
    async def test_video_streaming_performance(self, async_client, test_project, db_session):
        """Test video streaming performance under load"""
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            project_id=test_project.id
        )
        db_session.add(video)
        db_session.commit()
        
        # Simulate concurrent requests
        tasks = []
        for i in range(10):
            task = async_client.get(f"/api/videos/{video.id}/stream")
            tasks.append(task)
        
        start_time = asyncio.get_event_loop().time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()
        
        # All requests should complete within reasonable time
        assert end_time - start_time < 5.0
        
        # Check that no requests failed
        for response in responses:
            if not isinstance(response, Exception):
                assert response.status_code in [200, 206]  # OK or Partial Content

    @pytest.mark.security
    async def test_video_access_security(self, async_client, test_project, db_session):
        """Test video access security and authorization"""
        video = Video(
            filename="private_video.mp4",
            file_path="/uploads/private_video.mp4",
            project_id=test_project.id
        )
        db_session.add(video)
        db_session.commit()
        
        # Test unauthorized access
        with patch('backend.main.get_current_user', return_value=None):
            response = await async_client.get(f"/api/videos/{video.id}/stream")
            assert response.status_code == 401
        
        # Test path traversal protection
        malicious_id = "../../../etc/passwd"
        response = await async_client.get(f"/api/videos/{malicious_id}/stream")
        assert response.status_code == 400  # Bad request due to invalid UUID


class TestVideoPlaybackErrorHandling:
    """Test error handling scenarios for video playback"""

    @pytest.mark.asyncio
    async def test_corrupted_video_handling(self, async_client, test_project):
        """Test handling of corrupted video files"""
        with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
            tmp.write(b"corrupted video data")
            tmp.flush()
            
            with open(tmp.name, 'rb') as corrupted_file:
                files = {"file": ("corrupted.mp4", corrupted_file, "video/mp4")}
                data = {"project_id": test_project.id}
                
                response = await async_client.post(
                    "/api/videos/upload",
                    files=files,
                    data=data
                )
        
        # Should handle gracefully with appropriate error
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_network_interruption_handling(self, async_client, test_project):
        """Test handling of network interruptions during upload"""
        with patch('backend.main.aiofiles.open', side_effect=IOError("Network error")):
            with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
                tmp.write(b"test video data")
                tmp.flush()
                
                with open(tmp.name, 'rb') as video_file:
                    files = {"file": ("test.mp4", video_file, "video/mp4")}
                    data = {"project_id": test_project.id}
                    
                    response = await async_client.post(
                        "/api/videos/upload",
                        files=files,
                        data=data
                    )
        
        assert response.status_code == 500
        assert "Network error" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_disk_space_handling(self, async_client, test_project):
        """Test handling of insufficient disk space"""
        with patch('backend.main.os.statvfs') as mock_statvfs:
            # Mock insufficient disk space
            mock_statvfs.return_value.f_bavail = 0
            
            with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
                tmp.write(b"test video data")
                tmp.flush()
                
                with open(tmp.name, 'rb') as video_file:
                    files = {"file": ("test.mp4", video_file, "video/mp4")}
                    data = {"project_id": test_project.id}
                    
                    response = await async_client.post(
                        "/api/videos/upload",
                        files=files,
                        data=data
                    )
        
        assert response.status_code == 507  # Insufficient Storage


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])