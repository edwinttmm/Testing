"""
Test Video Upload Fixes
Tests for critical video upload issues found by UI testing.
"""

import pytest
import os
import tempfile
import asyncio
import sqlite3
from fastapi.testclient import TestClient
from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch, AsyncMock
import json

# Import the app and dependencies
from main import app, get_db
from database import Base
from models import Video, Project
from services.video_validation_service import VideoValidationService

class TestVideoUploadFixes:
    """Test critical video upload fixes"""
    
    def setup_method(self):
        """Set up test environment"""
        # Create test database engine
        self.test_engine = create_engine(
            "sqlite:///./test_upload_fixes.db",
            connect_args={"check_same_thread": False}
        )
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)
        
        # Create tables
        Base.metadata.create_all(bind=self.test_engine)
        
        # Override dependency
        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
    
    def teardown_method(self):
        """Clean up test environment"""
        app.dependency_overrides.clear()
        if os.path.exists("./test_upload_fixes.db"):
            os.unlink("./test_upload_fixes.db")
    
    def test_valid_mp4_upload_includes_processing_status(self):
        """Test that valid MP4 upload includes processingStatus in response"""
        # Create test MP4 file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            # Create a minimal MP4-like file structure
            tmp_file.write(b"\\x00\\x00\\x00\\x18ftypmp41")  # MP4 header
            tmp_file.write(b"\\x00" * 1000)  # Some content
            tmp_file.flush()
            
            # Mock video validation to return valid
            with patch.object(VideoValidationService, 'validate_video_file') as mock_validate:
                mock_validate.return_value = {
                    "valid": True,
                    "errors": [],
                    "warnings": [],
                    "metadata": {"duration": 10.0, "fps": 30.0, "width": 640, "height": 480, "resolution": "640x480"}
                }
                
                with patch.object(VideoValidationService, 'validate_upload_file') as mock_upload_validate:
                    mock_upload_validate.return_value = {
                        "valid": True,
                        "errors": [],
                        "secure_filename": "test.mp4",
                        "file_extension": ".mp4"
                    }
                    
                    # Upload file
                    with open(tmp_file.name, 'rb') as f:
                        response = self.client.post(
                            "/api/videos",
                            files={"file": ("test_video.mp4", f, "video/mp4")}
                        )
        
        # Cleanup
        os.unlink(tmp_file.name)
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        
        # Critical: processingStatus must be included
        assert "processingStatus" in data, "Response missing processingStatus field"
        assert data["processingStatus"] in ["pending", "processing", "completed"]
        
        # Other required fields
        assert "id" in data
        assert "filename" in data
        assert "status" in data
        assert "groundTruthGenerated" in data
    
    def test_corrupted_mp4_upload_handled_gracefully(self):
        """Test that corrupted MP4 files are handled gracefully"""
        # Create corrupted MP4 file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(b"corrupted data not a real mp4 file")
            tmp_file.flush()
            
            # Mock video validation to return invalid
            with patch.object(VideoValidationService, 'validate_upload_file') as mock_upload_validate:
                mock_upload_validate.return_value = {
                    "valid": True,
                    "errors": [],
                    "secure_filename": "test.mp4",
                    "file_extension": ".mp4"
                }
                
                with patch.object(VideoValidationService, 'validate_video_file') as mock_validate:
                    mock_validate.return_value = {
                        "valid": False,
                        "errors": ["Cannot open video file - file may be corrupted or format unsupported"],
                        "warnings": [],
                        "metadata": None
                    }
                    
                    # Upload file
                    with open(tmp_file.name, 'rb') as f:
                        response = self.client.post(
                            "/api/videos",
                            files={"file": ("corrupted.mp4", f, "video/mp4")}
                        )
        
        # Cleanup
        os.unlink(tmp_file.name)
        
        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "validation failed" in data["detail"].lower()
    
    def test_invalid_file_format_rejected(self):
        """Test that invalid file formats are rejected"""
        # Create text file with MP4 extension
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp_file:
            tmp_file.write(b"This is not a video file")
            tmp_file.flush()
            
            # Upload file
            with open(tmp_file.name, 'rb') as f:
                response = self.client.post(
                    "/api/videos",
                    files={"file": ("test.txt", f, "text/plain")}
                )
        
        # Cleanup
        os.unlink(tmp_file.name)
        
        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "unsupported" in data["detail"].lower() or "validation failed" in data["detail"].lower()
    
    def test_empty_file_upload_rejected(self):
        """Test that empty files are rejected"""
        # Create empty file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            # File is empty
            tmp_file.flush()
            
            # Mock validation to pass upload validation
            with patch.object(VideoValidationService, 'validate_upload_file') as mock_upload_validate:
                mock_upload_validate.return_value = {
                    "valid": True,
                    "errors": [],
                    "secure_filename": "empty.mp4",
                    "file_extension": ".mp4"
                }
                
                # Upload file
                with open(tmp_file.name, 'rb') as f:
                    response = self.client.post(
                        "/api/videos",
                        files={"file": ("empty.mp4", f, "video/mp4")}
                    )
        
        # Cleanup
        os.unlink(tmp_file.name)
        
        # Assertions
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "empty" in data["detail"].lower()
    
    def test_concurrent_uploads_database_stability(self):
        """Test database stability under concurrent upload load"""
        import concurrent.futures
        import threading
        
        def create_upload_request(thread_id):
            """Create a single upload request"""
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
                tmp_file.write(b"\\x00\\x00\\x00\\x18ftypmp41")  # MP4 header
                tmp_file.write(f"thread_{thread_id}_content".encode() * 100)
                tmp_file.flush()
                
                try:
                    # Mock validation for success
                    with patch.object(VideoValidationService, 'validate_video_file') as mock_validate:
                        mock_validate.return_value = {
                            "valid": True,
                            "errors": [],
                            "warnings": [],
                            "metadata": {"duration": 5.0, "fps": 30.0}
                        }
                        
                        with patch.object(VideoValidationService, 'validate_upload_file') as mock_upload_validate:
                            mock_upload_validate.return_value = {
                                "valid": True,
                                "errors": [],
                                "secure_filename": f"thread_{thread_id}.mp4",
                                "file_extension": ".mp4"
                            }
                            
                            with open(tmp_file.name, 'rb') as f:
                                response = self.client.post(
                                    "/api/videos",
                                    files={"file": (f"video_{thread_id}.mp4", f, "video/mp4")}
                                )
                    return response.status_code
                finally:
                    if os.path.exists(tmp_file.name):
                        os.unlink(tmp_file.name)
        
        # Run 10 concurrent uploads
        success_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_upload_request, i) for i in range(10)]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    status_code = future.result()
                    if status_code == 200:
                        success_count += 1
                except Exception as e:
                    print(f"Upload failed with exception: {e}")
        
        # At least some uploads should succeed (database should handle concurrency)
        assert success_count >= 5, f"Only {success_count}/10 uploads succeeded - database connection issues"
    
    def test_database_connection_pool_efficiency(self):
        """Test database connection pool handles requests efficiently"""
        from database import engine
        
        # Check initial pool state
        initial_pool_size = engine.pool.size()
        initial_checked_out = engine.pool.checkedout()
        
        # Make several sequential requests
        for i in range(5):
            response = self.client.get("/health")
            assert response.status_code == 200
        
        # Pool should not be exhausted
        current_checked_out = engine.pool.checkedout()
        assert current_checked_out <= initial_pool_size, "Connection pool exhausted"
    
    def test_video_upload_response_schema_completeness(self):
        """Test that video upload response contains all required fields"""
        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
            tmp_file.write(b"\\x00\\x00\\x00\\x18ftypmp41")  # MP4 header
            tmp_file.write(b"test content" * 100)
            tmp_file.flush()
            
            # Mock successful validation
            with patch.object(VideoValidationService, 'validate_video_file') as mock_validate:
                mock_validate.return_value = {
                    "valid": True,
                    "errors": [],
                    "warnings": [],
                    "metadata": {"duration": 10.0, "fps": 30.0, "width": 1920, "height": 1080, "resolution": "1920x1080"}
                }
                
                with patch.object(VideoValidationService, 'validate_upload_file') as mock_upload_validate:
                    mock_upload_validate.return_value = {
                        "valid": True,
                        "errors": [],
                        "secure_filename": "complete_test.mp4",
                        "file_extension": ".mp4"
                    }
                    
                    # Upload file
                    with open(tmp_file.name, 'rb') as f:
                        response = self.client.post(
                            "/api/videos",
                            files={"file": ("complete_test.mp4", f, "video/mp4")}
                        )
        
        # Cleanup
        os.unlink(tmp_file.name)
        
        # Verify response completeness
        assert response.status_code == 200
        data = response.json()
        
        # All required fields must be present
        required_fields = [
            "id", "projectId", "filename", "originalName", "url", "size", "fileSize",
            "uploadedAt", "createdAt", "status", "groundTruthGenerated", 
            "processingStatus", "detectionCount", "message"
        ]
        
        for field in required_fields:
            assert field in data, f"Required field '{field}' missing from response"
        
        # Specific validation for critical fields
        assert data["processingStatus"] in ["pending", "processing", "completed", "failed"]
        assert isinstance(data["size"], int) and data["size"] > 0
        assert isinstance(data["detectionCount"], int) and data["detectionCount"] >= 0
        assert data["groundTruthGenerated"] in [True, False]

if __name__ == "__main__":
    # Run the tests
    test_instance = TestVideoUploadFixes()
    test_instance.setup_method()
    
    try:
        # Run all tests
        print("🧪 Testing video upload response schema completeness...")
        test_instance.test_video_upload_response_schema_completeness()
        print("✅ PASS: Response schema test")
        
        print("🧪 Testing corrupted MP4 handling...")
        test_instance.test_corrupted_mp4_upload_handled_gracefully()
        print("✅ PASS: Corrupted file handling test")
        
        print("🧪 Testing invalid file format rejection...")
        test_instance.test_invalid_file_format_rejected()
        print("✅ PASS: Invalid format test")
        
        print("🧪 Testing empty file rejection...")
        test_instance.test_empty_file_upload_rejected()
        print("✅ PASS: Empty file test")
        
        print("🧪 Testing database connection efficiency...")
        test_instance.test_database_connection_pool_efficiency()
        print("✅ PASS: Database efficiency test")
        
        print("\\n🎉 ALL CRITICAL TESTS PASSED!")
        print("✅ Video upload response schema validation fixed")
        print("✅ Video file corruption handling improved")
        print("✅ Database connection pooling optimized")
        print("✅ File format validation enhanced")
        
    except Exception as e:
        print(f"❌ TEST FAILED: {e}")
    finally:
        test_instance.teardown_method()