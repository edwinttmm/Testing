#!/usr/bin/env python3
"""
Comprehensive Production Validation Tests for AI Model Validation Platform
Tests all critical functionality against real backend implementation
"""
import pytest
import httpx
import json
import asyncio
import time
import sqlite3
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime
import io

# Test Configuration
BASE_URL = "http://localhost:8001"
TIMEOUT = 30.0

class ComprehensiveValidator:
    """Production validation test suite"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.test_data = {
            'projects': [],
            'videos': []
        }
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

class TestServerStartup:
    """Test server initialization and startup"""
    
    @pytest.mark.asyncio
    async def test_server_health(self):
        """Test server health endpoint"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "message" in data
            
    @pytest.mark.asyncio
    async def test_cors_headers(self):
        """Test CORS configuration"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.options(f"{BASE_URL}/health")
            assert response.status_code == 200
            
    @pytest.mark.asyncio 
    async def test_database_initialization(self):
        """Test database is properly initialized"""
        # Check database file exists
        db_path = "./simple_test.db"
        assert os.path.exists(db_path)
        
        # Check tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        assert 'projects' in tables
        assert 'videos' in tables
        
        conn.close()

class TestProjectCRUD:
    """Test project CRUD operations"""
    
    @pytest.mark.asyncio
    async def test_create_project_success(self):
        """Test successful project creation"""
        project_data = {
            "name": "Test Project",
            "description": "Test Description", 
            "cameraModel": "Test Camera",
            "cameraView": "Front-facing VRU",
            "lensType": "Wide Angle",
            "resolution": "1920x1080",
            "frameRate": 30,
            "signalType": "GPIO"
        }
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{BASE_URL}/api/projects",
                json=project_data
            )
            
            assert response.status_code == 201
            data = response.json()
            
            assert data["name"] == project_data["name"]
            assert data["description"] == project_data["description"]
            assert data["status"] == "active"
            assert "id" in data
            assert "created_at" in data
            
    @pytest.mark.asyncio
    async def test_create_project_validation(self):
        """Test project creation validation"""
        invalid_data = {
            "description": "Missing required name field"
        }
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{BASE_URL}/api/projects",
                json=invalid_data
            )
            
            assert response.status_code == 422  # Validation error
            
    @pytest.mark.asyncio
    async def test_get_projects(self):
        """Test retrieving projects"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/projects")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            
    @pytest.mark.asyncio
    async def test_delete_project(self):
        """Test project deletion"""
        # First create a project
        project_data = {
            "name": "Delete Test Project",
            "cameraModel": "Test Camera",
            "signalType": "GPIO"
        }
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            create_response = await client.post(
                f"{BASE_URL}/api/projects",
                json=project_data
            )
            assert create_response.status_code == 201
            project_id = create_response.json()["id"]
            
            # Delete the project
            delete_response = await client.delete(
                f"{BASE_URL}/api/projects/{project_id}"
            )
            assert delete_response.status_code == 200

class TestFileUpload:
    """Test file upload functionality"""
    
    @pytest.mark.asyncio
    async def test_video_upload_success(self):
        """Test successful video upload"""
        # First create a project
        project_data = {
            "name": "Video Upload Test Project",
            "cameraModel": "Test Camera", 
            "signalType": "GPIO"
        }
        
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            project_response = await client.post(
                f"{BASE_URL}/api/projects",
                json=project_data
            )
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]
            
            # Create test video file
            test_video_content = b"fake video content for testing"
            
            # Upload video
            files = {"file": ("test_video.mp4", io.BytesIO(test_video_content), "video/mp4")}
            data = {"project_id": project_id}
            
            upload_response = await client.post(
                f"{BASE_URL}/api/videos",
                files=files,
                data=data
            )
            
            assert upload_response.status_code == 201
            upload_data = upload_response.json()
            
            assert upload_data["filename"] == "test_video.mp4"
            assert upload_data["file_size"] == len(test_video_content)
            assert upload_data["project_id"] == project_id
            assert upload_data["status"] == "uploaded"
            
    @pytest.mark.asyncio
    async def test_get_videos(self):
        """Test retrieving videos"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/videos")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

class TestDashboardAPI:
    """Test dashboard statistics API"""
    
    @pytest.mark.asyncio
    async def test_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/dashboard/stats")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "totalProjects" in data
            assert "totalVideos" in data
            assert "totalTestSessions" in data
            assert isinstance(data["totalProjects"], int)
            assert isinstance(data["totalVideos"], int)
            assert isinstance(data["totalTestSessions"], int)

class TestDatabaseOperations:
    """Test database operations directly"""
    
    def test_database_crud_operations(self):
        """Test database CRUD operations directly"""
        db_path = "./simple_test.db"
        assert os.path.exists(db_path)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Test INSERT
        test_id = "test-direct-crud"
        cursor.execute("""
            INSERT OR REPLACE INTO projects (id, name, camera_model, signal_type)
            VALUES (?, ?, ?, ?)
        """, (test_id, "Direct CRUD Test", "Test Camera", "GPIO"))
        
        # Test SELECT
        cursor.execute("SELECT * FROM projects WHERE id = ?", (test_id,))
        result = cursor.fetchone()
        assert result is not None
        assert result[1] == "Direct CRUD Test"  # name field
        
        # Test UPDATE
        cursor.execute("""
            UPDATE projects SET name = ? WHERE id = ?
        """, ("Updated CRUD Test", test_id))
        
        cursor.execute("SELECT name FROM projects WHERE id = ?", (test_id,))
        updated_result = cursor.fetchone()
        assert updated_result[0] == "Updated CRUD Test"
        
        # Test DELETE
        cursor.execute("DELETE FROM projects WHERE id = ?", (test_id,))
        cursor.execute("SELECT * FROM projects WHERE id = ?", (test_id,))
        deleted_result = cursor.fetchone()
        assert deleted_result is None
        
        conn.commit()
        conn.close()

class TestPerformance:
    """Test performance and load handling"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        async def make_health_request():
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                response = await client.get(f"{BASE_URL}/health")
                return response.status_code == 200
        
        # Make 10 concurrent requests
        tasks = [make_health_request() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert all(results)
        
    @pytest.mark.asyncio
    async def test_response_time(self):
        """Test API response times"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            start_time = time.time()
            response = await client.get(f"{BASE_URL}/health")
            end_time = time.time()
            
            assert response.status_code == 200
            response_time = end_time - start_time
            assert response_time < 1.0  # Should respond within 1 second

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.mark.asyncio
    async def test_invalid_endpoints(self):
        """Test invalid endpoint handling"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/invalid/endpoint")
            assert response.status_code == 404
            
    @pytest.mark.asyncio
    async def test_malformed_requests(self):
        """Test malformed request handling"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Send malformed JSON
            response = await client.post(
                f"{BASE_URL}/api/projects",
                content="invalid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code in [400, 422]

# Integration test that runs the full workflow
class TestIntegrationWorkflow:
    """Test complete integration workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete project-video workflow"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # 1. Create project
            project_data = {
                "name": "Integration Test Project",
                "description": "Full workflow integration test",
                "cameraModel": "Integration Camera",
                "cameraView": "Front-facing VRU",
                "lensType": "Standard",
                "resolution": "1920x1080",
                "frameRate": 30,
                "signalType": "GPIO"
            }
            
            create_response = await client.post(
                f"{BASE_URL}/api/projects",
                json=project_data
            )
            assert create_response.status_code == 201
            project_id = create_response.json()["id"]
            
            # 2. Upload video
            test_video = b"integration test video content"
            files = {"file": ("integration_test.mp4", io.BytesIO(test_video), "video/mp4")}
            data = {"project_id": project_id}
            
            upload_response = await client.post(
                f"{BASE_URL}/api/videos",
                files=files,
                data=data
            )
            assert upload_response.status_code == 201
            video_id = upload_response.json()["id"]
            
            # 3. Check dashboard stats
            stats_response = await client.get(f"{BASE_URL}/api/dashboard/stats")
            assert stats_response.status_code == 200
            stats = stats_response.json()
            assert stats["totalProjects"] >= 1
            assert stats["totalVideos"] >= 1
            
            # 4. Verify project exists
            projects_response = await client.get(f"{BASE_URL}/api/projects")
            assert projects_response.status_code == 200
            projects = projects_response.json()
            project_exists = any(p["id"] == project_id for p in projects)
            assert project_exists
            
            # 5. Verify video exists
            videos_response = await client.get(f"{BASE_URL}/api/videos")
            assert videos_response.status_code == 200
            videos = videos_response.json()
            video_exists = any(v["id"] == video_id for v in videos)
            assert video_exists
            
            # 6. Cleanup - delete video then project
            delete_video_response = await client.delete(f"{BASE_URL}/api/videos/{video_id}")
            assert delete_video_response.status_code == 200
            
            delete_project_response = await client.delete(f"{BASE_URL}/api/projects/{project_id}")
            assert delete_project_response.status_code == 200

if __name__ == "__main__":
    print("🧪 Running Comprehensive Production Validation Tests")
    print("=" * 60)
    
    # Run pytest with verbose output
    import subprocess
    result = subprocess.run([
        "python", "-m", "pytest", __file__, 
        "-v", "--tb=short", "--no-header"
    ], cwd=os.path.dirname(__file__) or ".")
    
    exit_code = result.returncode
    if exit_code == 0:
        print("\n✅ All validation tests passed!")
    else:
        print(f"\n❌ Some tests failed (exit code: {exit_code})")
    
    exit(exit_code)