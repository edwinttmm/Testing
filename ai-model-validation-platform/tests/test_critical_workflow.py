#!/usr/bin/env python3
"""
CRITICAL END-TO-END WORKFLOW TESTER
Tests the complete user workflow from project creation to video processing.

CRITICAL REQUIREMENTS:
1. Test project creation API endpoint works
2. Test video upload functionality works  
3. Test dashboard displays project data
4. Fix any broken API chains in the workflow
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import uuid
import aiohttp
import pytest
import time

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent.parent / "backend"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CriticalWorkflowTester:
    """Test critical user workflow endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_project_id = None
        self.test_video_id = None
        self.results = {
            "project_creation": False,
            "video_upload": False,
            "dashboard_stats": False,
            "api_chain_working": False
        }
    
    async def setup(self):
        """Initialize test session"""
        logger.info("🔧 Setting up test session...")
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={"Content-Type": "application/json"}
        )
        
    async def cleanup(self):
        """Cleanup test resources"""
        logger.info("🧹 Cleaning up test resources...")
        
        # Clean up test video
        if self.test_video_id and self.session:
            try:
                async with self.session.delete(f"{self.base_url}/api/videos/{self.test_video_id}") as response:
                    if response.status in [200, 204, 404]:
                        logger.info(f"✅ Cleaned up test video: {self.test_video_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup video: {e}")
        
        # Clean up test project
        if self.test_project_id and self.session:
            try:
                async with self.session.delete(f"{self.base_url}/api/projects/{self.test_project_id}") as response:
                    if response.status in [200, 204, 404]:
                        logger.info(f"✅ Cleaned up test project: {self.test_project_id}")
            except Exception as e:
                logger.warning(f"Failed to cleanup project: {e}")
        
        if self.session:
            await self.session.close()

    async def test_backend_health(self) -> bool:
        """Test if backend is running and healthy"""
        logger.info("🔍 Testing backend health...")
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    logger.info(f"✅ Backend health: {health_data.get('status', 'unknown')}")
                    return True
                else:
                    logger.error(f"❌ Backend health check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ Backend not reachable: {e}")
            return False

    async def test_project_creation(self) -> bool:
        """Test POST /api/projects endpoint"""
        logger.info("🧪 Testing project creation endpoint...")
        
        project_data = {
            "name": f"Critical Test Project {uuid.uuid4().hex[:8]}",
            "description": "Critical workflow test project",
            "cameraModel": "Test Camera Model",
            "cameraView": "Front-facing VRU", 
            "lensType": "Wide Angle",
            "resolution": "1920x1080",
            "frameRate": 30,
            "signalType": "GPIO"
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/projects",
                json=project_data
            ) as response:
                
                # Check status code
                if response.status != 201:
                    error_text = await response.text()
                    logger.error(f"❌ Project creation failed: {response.status} - {error_text}")
                    return False
                
                # Check response data
                result = await response.json()
                
                # Verify required fields
                required_fields = ['id', 'name', 'status']
                for field in required_fields:
                    if field not in result:
                        logger.error(f"❌ Missing required field '{field}' in project response")
                        return False
                
                self.test_project_id = result['id']
                logger.info(f"✅ Project created successfully: {self.test_project_id}")
                self.results["project_creation"] = True
                return True
                
        except Exception as e:
            logger.error(f"❌ Project creation error: {e}")
            return False

    async def test_video_upload(self) -> bool:
        """Test POST /api/videos endpoint"""
        logger.info("🧪 Testing video upload endpoint...")
        
        if not self.test_project_id:
            logger.error("❌ Cannot test video upload without project ID")
            return False
        
        # Create a small test video file
        test_video_content = b"FAKE_VIDEO_DATA_FOR_TESTING_" + b"X" * 1024  # 1KB fake video
        
        try:
            # Create multipart form data
            data = aiohttp.FormData()
            data.add_field('file', test_video_content, 
                          filename='test_video.mp4', 
                          content_type='video/mp4')
            data.add_field('project_id', self.test_project_id)
            
            async with self.session.post(
                f"{self.base_url}/api/videos",
                data=data
            ) as response:
                
                # Check status code
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error(f"❌ Video upload failed: {response.status} - {error_text}")
                    return False
                
                # Check response data
                result = await response.json()
                
                # Verify required fields
                required_fields = ['id', 'filename', 'status']
                for field in required_fields:
                    if field not in result:
                        logger.error(f"❌ Missing required field '{field}' in video response")
                        return False
                
                self.test_video_id = result['id']
                logger.info(f"✅ Video uploaded successfully: {self.test_video_id}")
                self.results["video_upload"] = True
                return True
                
        except Exception as e:
            logger.error(f"❌ Video upload error: {e}")
            return False

    async def test_dashboard_stats(self) -> bool:
        """Test GET /api/dashboard/stats endpoint"""
        logger.info("🧪 Testing dashboard stats endpoint...")
        
        try:
            async with self.session.get(f"{self.base_url}/api/dashboard/stats") as response:
                
                # Check status code
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ Dashboard stats failed: {response.status} - {error_text}")
                    return False
                
                # Check response data
                result = await response.json()
                
                # Verify required fields
                required_fields = ['totalProjects', 'totalVideos', 'totalTestSessions']
                for field in required_fields:
                    if field not in result:
                        logger.error(f"❌ Missing required field '{field}' in dashboard response")
                        return False
                
                # Verify data types
                numeric_fields = ['totalProjects', 'totalVideos', 'totalTestSessions']
                for field in numeric_fields:
                    if not isinstance(result[field], int):
                        logger.error(f"❌ Field '{field}' should be integer, got {type(result[field])}")
                        return False
                
                logger.info(f"✅ Dashboard stats retrieved: Projects={result['totalProjects']}, Videos={result['totalVideos']}")
                self.results["dashboard_stats"] = True
                return True
                
        except Exception as e:
            logger.error(f"❌ Dashboard stats error: {e}")
            return False

    async def test_api_chain_integrity(self) -> bool:
        """Test that the complete API chain works together"""
        logger.info("🧪 Testing complete API chain integrity...")
        
        # Verify project exists in project list
        try:
            async with self.session.get(f"{self.base_url}/api/projects") as response:
                if response.status == 200:
                    projects = await response.json()
                    project_found = any(p.get('id') == self.test_project_id for p in projects)
                    if not project_found:
                        logger.error("❌ Created project not found in project list")
                        return False
                    logger.info("✅ Project found in project list")
        except Exception as e:
            logger.error(f"❌ Error checking project list: {e}")
            return False
        
        # Verify video exists in video list  
        try:
            async with self.session.get(f"{self.base_url}/api/videos") as response:
                if response.status == 200:
                    videos = await response.json()
                    video_found = any(v.get('id') == self.test_video_id for v in videos)
                    if not video_found:
                        logger.error("❌ Uploaded video not found in video list")
                        return False
                    logger.info("✅ Video found in video list")
        except Exception as e:
            logger.error(f"❌ Error checking video list: {e}")
            return False
        
        # Verify dashboard stats reflect our data
        try:
            async with self.session.get(f"{self.base_url}/api/dashboard/stats") as response:
                if response.status == 200:
                    stats = await response.json()
                    if stats.get('totalProjects', 0) == 0:
                        logger.error("❌ Dashboard shows 0 projects after creation")
                        return False
                    if stats.get('totalVideos', 0) == 0:
                        logger.error("❌ Dashboard shows 0 videos after upload")
                        return False
                    logger.info("✅ Dashboard stats reflect our test data")
        except Exception as e:
            logger.error(f"❌ Error verifying dashboard consistency: {e}")
            return False
        
        self.results["api_chain_working"] = True
        return True

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run complete test suite"""
        logger.info("🚀 Starting Critical Workflow Test Suite")
        
        await self.setup()
        
        try:
            # Test 1: Backend Health
            if not await self.test_backend_health():
                raise Exception("Backend is not healthy - cannot proceed with tests")
            
            # Test 2: Project Creation
            if not await self.test_project_creation():
                raise Exception("Project creation failed - critical workflow broken")
            
            # Test 3: Video Upload  
            if not await self.test_video_upload():
                raise Exception("Video upload failed - critical workflow broken")
            
            # Test 4: Dashboard Stats
            if not await self.test_dashboard_stats():
                raise Exception("Dashboard stats failed - critical workflow broken")
            
            # Test 5: API Chain Integrity
            if not await self.test_api_chain_integrity():
                raise Exception("API chain integrity failed - workflow broken")
            
            # Final success check
            all_passed = all(self.results.values())
            if all_passed:
                logger.info("🎉 ALL CRITICAL TESTS PASSED!")
            else:
                logger.error(f"❌ Some tests failed: {self.results}")
            
            return {
                "success": all_passed,
                "results": self.results,
                "message": "All critical workflow tests passed" if all_passed else "Some critical tests failed"
            }
            
        except Exception as e:
            logger.error(f"💥 Critical test failure: {e}")
            return {
                "success": False,
                "results": self.results,
                "error": str(e),
                "message": "Critical workflow test suite failed"
            }
        
        finally:
            await self.cleanup()

def run_sync():
    """Synchronous wrapper for async tests"""
    async def main():
        tester = CriticalWorkflowTester()
        return await tester.run_all_tests()
    
    return asyncio.run(main())

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("CRITICAL END-TO-END WORKFLOW TESTER")
    logger.info("Testing: Project Creation → Video Upload → Dashboard Stats")
    logger.info("=" * 60)
    
    result = run_sync()
    
    print("\n" + "=" * 60)
    print("FINAL TEST RESULTS:")
    print("=" * 60)
    
    for test_name, passed in result["results"].items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name.upper()}: {status}")
    
    print(f"\nOVERALL RESULT: {'🎉 SUCCESS' if result['success'] else '💥 FAILURE'}")
    print(f"MESSAGE: {result['message']}")
    
    if not result["success"]:
        sys.exit(1)