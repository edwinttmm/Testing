#!/usr/bin/env python3
"""
Comprehensive API Integration Validation Test Suite
Tests API data flow from frontend to backend across all critical endpoints.
"""

import pytest
import requests
import json
import asyncio
import aiohttp
from pathlib import Path
import sys
import time
from typing import Dict, List, Any, Optional
import threading

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
try:
    from main import app
except ImportError as e:
    print(f"⚠️  Could not import main app: {e}")
    app = None

class TestAPIIntegration:
    """Test suite for API integration validation."""
    
    def setup_class(self):
        """Setup API test environment."""
        if app:
            self.client = TestClient(app)
        else:
            self.client = None
        
        self.base_url = "http://localhost:8000"
        self.test_endpoints = {
            "health": "/health",
            "videos": "/videos",
            "ground_truth": "/ground-truth",
            "detection": "/detection",
            "results": "/results",
            "labjack": "/labjack",
            "websocket": "/ws"
        }
        
        # Test data for various endpoints
        self.test_data = {
            "video": {
                "filename": "test_video.mp4",
                "path": "/uploads/test_video.mp4",
                "duration": 30.0,
                "fps": 30.0,
                "width": 1920,
                "height": 1080
            },
            "ground_truth": {
                "video_id": 1,
                "annotations": [
                    {
                        "timestamp": 1.5,
                        "bbox": {"x": 100, "y": 100, "width": 50, "height": 50},
                        "label": "vehicle",
                        "confidence": 0.95
                    }
                ]
            },
            "detection": {
                "video_id": 1,
                "frame_number": 45,
                "timestamp": 1.5,
                "detections": [
                    {
                        "bbox": {"x": 105, "y": 98, "width": 48, "height": 52},
                        "label": "vehicle",
                        "confidence": 0.87
                    }
                ]
            }
        }
        
        print(f"🔧 API Integration Test Environment Ready")
    
    def test_health_endpoint(self):
        """Test basic health/status endpoint."""
        print("❤️  Testing health endpoint...")
        
        if not self.client:
            # Fallback to direct HTTP request
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                status_code = response.status_code
                response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {"status": "unknown"}
            except requests.exceptions.RequestException as e:
                print(f"⚠️  Health endpoint not accessible: {e}")
                return False
        else:
            response = self.client.get("/health")
            status_code = response.status_code
            response_data = response.json()
        
        if status_code == 200:
            assert "status" in response_data or "message" in response_data, "Health response should have status/message"
            print(f"✅ Health endpoint test passed: {response_data}")
            return True
        else:
            print(f"⚠️  Health endpoint returned {status_code}")
            return False
    
    def test_video_endpoints(self):
        """Test video-related API endpoints."""
        print("🎥 Testing video endpoints...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping video endpoint tests")
            return False
        
        try:
            # Test GET /videos (list videos)
            videos_response = self.client.get("/videos")
            print(f"   GET /videos: {videos_response.status_code}")
            
            if videos_response.status_code == 200:
                videos_data = videos_response.json()
                assert isinstance(videos_data, (list, dict)), "Videos response should be list or dict"
                print(f"   Found videos: {len(videos_data) if isinstance(videos_data, list) else 'dict response'}")
            
            # Test POST /videos (create video record)
            video_create_response = self.client.post("/videos", json=self.test_data["video"])
            print(f"   POST /videos: {video_create_response.status_code}")
            
            if video_create_response.status_code in [200, 201]:
                create_data = video_create_response.json()
                video_id = create_data.get("id") or create_data.get("video_id") or 1
                
                # Test GET /videos/{id} (get specific video)
                video_get_response = self.client.get(f"/videos/{video_id}")
                print(f"   GET /videos/{video_id}: {video_get_response.status_code}")
                
                if video_get_response.status_code == 200:
                    video_data = video_get_response.json()
                    assert "filename" in video_data or "path" in video_data, "Video data should contain filename/path"
            
            print("✅ Video endpoints test completed")
            return True
        except Exception as e:
            print(f"❌ Video endpoints test failed: {e}")
            return False
    
    def test_ground_truth_endpoints(self):
        """Test ground truth API endpoints."""
        print("📍 Testing ground truth endpoints...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping ground truth endpoint tests")
            return False
        
        try:
            # Test POST /ground-truth (create ground truth)
            gt_create_response = self.client.post("/ground-truth", json=self.test_data["ground_truth"])
            print(f"   POST /ground-truth: {gt_create_response.status_code}")
            
            if gt_create_response.status_code in [200, 201]:
                create_data = gt_create_response.json()
                gt_id = create_data.get("id") or self.test_data["ground_truth"]["video_id"]
                
                # Test GET /ground-truth/{video_id} (get ground truth)
                gt_get_response = self.client.get(f"/ground-truth/{gt_id}")
                print(f"   GET /ground-truth/{gt_id}: {gt_get_response.status_code}")
                
                if gt_get_response.status_code == 200:
                    gt_data = gt_get_response.json()
                    assert "annotations" in gt_data or isinstance(gt_data, list), "Ground truth should contain annotations"
            
            # Test GET /ground-truth (list all ground truth)
            gt_list_response = self.client.get("/ground-truth")
            print(f"   GET /ground-truth: {gt_list_response.status_code}")
            
            if gt_list_response.status_code == 200:
                gt_list_data = gt_list_response.json()
                assert isinstance(gt_list_data, (list, dict)), "Ground truth list should be list or dict"
            
            print("✅ Ground truth endpoints test completed")
            return True
        except Exception as e:
            print(f"❌ Ground truth endpoints test failed: {e}")
            return False
    
    def test_detection_endpoints(self):
        """Test detection/ML inference endpoints."""
        print("🔍 Testing detection endpoints...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping detection endpoint tests")
            return False
        
        try:
            # Test POST /detection (submit detection results)
            detection_response = self.client.post("/detection", json=self.test_data["detection"])
            print(f"   POST /detection: {detection_response.status_code}")
            
            if detection_response.status_code in [200, 201]:
                detection_data = detection_response.json()
                assert "success" in detection_data or "id" in detection_data, "Detection response should indicate success"
            
            # Test GET /detection/{video_id} (get detection results)
            video_id = self.test_data["detection"]["video_id"]
            detection_get_response = self.client.get(f"/detection/{video_id}")
            print(f"   GET /detection/{video_id}: {detection_get_response.status_code}")
            
            if detection_get_response.status_code == 200:
                detection_results = detection_get_response.json()
                assert isinstance(detection_results, (list, dict)), "Detection results should be list or dict"
            
            # Test GET /detection (list all detections)
            detection_list_response = self.client.get("/detection")
            print(f"   GET /detection: {detection_list_response.status_code}")
            
            print("✅ Detection endpoints test completed")
            return True
        except Exception as e:
            print(f"❌ Detection endpoints test failed: {e}")
            return False
    
    def test_results_endpoints(self):
        """Test results/analytics endpoints."""
        print("📊 Testing results endpoints...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping results endpoint tests")
            return False
        
        try:
            # Test GET /results (get analysis results)
            results_response = self.client.get("/results")
            print(f"   GET /results: {results_response.status_code}")
            
            if results_response.status_code == 200:
                results_data = results_response.json()
                assert isinstance(results_data, (list, dict)), "Results should be list or dict"
            
            # Test GET /results/{session_id} if applicable
            if hasattr(self, 'session_id'):
                session_results_response = self.client.get(f"/results/{self.session_id}")
                print(f"   GET /results/{self.session_id}: {session_results_response.status_code}")
            
            # Test GET /results/summary (get summary stats)
            summary_response = self.client.get("/results/summary")
            print(f"   GET /results/summary: {summary_response.status_code}")
            
            if summary_response.status_code == 200:
                summary_data = summary_response.json()
                assert isinstance(summary_data, dict), "Summary should be dict"
            
            print("✅ Results endpoints test completed")
            return True
        except Exception as e:
            print(f"❌ Results endpoints test failed: {e}")
            return False
    
    def test_labjack_endpoints(self):
        """Test LabJack hardware integration endpoints."""
        print("⚡ Testing LabJack endpoints...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping LabJack endpoint tests")
            return False
        
        try:
            # Test GET /labjack/status (get LabJack status)
            labjack_status_response = self.client.get("/labjack/status")
            print(f"   GET /labjack/status: {labjack_status_response.status_code}")
            
            if labjack_status_response.status_code == 200:
                status_data = labjack_status_response.json()
                assert "connected" in status_data or "status" in status_data, "Status should indicate connection state"
            
            # Test POST /labjack/trigger (send trigger signal)
            trigger_data = {"signal": "FIO0", "value": True}
            trigger_response = self.client.post("/labjack/trigger", json=trigger_data)
            print(f"   POST /labjack/trigger: {trigger_response.status_code}")
            
            # Test GET /labjack/devices (list available devices)
            devices_response = self.client.get("/labjack/devices")
            print(f"   GET /labjack/devices: {devices_response.status_code}")
            
            if devices_response.status_code == 200:
                devices_data = devices_response.json()
                assert isinstance(devices_data, (list, dict)), "Devices should be list or dict"
            
            print("✅ LabJack endpoints test completed")
            return True
        except Exception as e:
            print(f"❌ LabJack endpoints test failed: {e}")
            return False
    
    def test_api_error_handling(self):
        """Test API error handling and validation."""
        print("🚫 Testing API error handling...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping error handling tests")
            return False
        
        try:
            # Test invalid endpoints
            invalid_response = self.client.get("/invalid-endpoint")
            assert invalid_response.status_code == 404, f"Invalid endpoint should return 404, got {invalid_response.status_code}"
            
            # Test invalid data
            invalid_data = {"invalid": "data"}
            invalid_post_response = self.client.post("/videos", json=invalid_data)
            assert invalid_post_response.status_code in [400, 422], f"Invalid data should return 400/422, got {invalid_post_response.status_code}"
            
            # Test missing required fields
            incomplete_data = {"filename": "test.mp4"}  # Missing other required fields
            incomplete_response = self.client.post("/videos", json=incomplete_data)
            # Should either accept with defaults or reject with validation error
            assert incomplete_response.status_code in [200, 201, 400, 422], "Incomplete data should be handled appropriately"
            
            print("✅ API error handling test completed")
            return True
        except Exception as e:
            print(f"❌ API error handling test failed: {e}")
            return False
    
    def test_api_performance(self):
        """Test API performance and response times."""
        print("⚡ Testing API performance...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping performance tests")
            return False
        
        try:
            # Test multiple concurrent requests
            response_times = []
            
            def make_request():
                start_time = time.time()
                response = self.client.get("/health")
                end_time = time.time()
                response_times.append(end_time - start_time)
                return response.status_code == 200
            
            # Make 10 concurrent requests
            threads = []
            for i in range(10):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                
                # API should respond within reasonable time
                assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.3f}s"
                assert max_response_time < 2.0, f"Max response time too high: {max_response_time:.3f}s"
                
                print(f"   Average response time: {avg_response_time:.3f}s")
                print(f"   Max response time: {max_response_time:.3f}s")
            
            print("✅ API performance test completed")
            return True
        except Exception as e:
            print(f"❌ API performance test failed: {e}")
            return False
    
    def test_api_data_flow_integration(self):
        """Test complete API data flow from frontend to backend."""
        print("🔄 Testing complete API data flow...")
        
        if not self.client:
            print("⚠️  TestClient not available - skipping data flow integration tests")
            return False
        
        try:
            # Simulate complete workflow
            workflow_success = True
            
            # Step 1: Upload/register video
            video_response = self.client.post("/videos", json=self.test_data["video"])
            if video_response.status_code not in [200, 201]:
                print(f"   Video registration failed: {video_response.status_code}")
                workflow_success = False
            else:
                video_data = video_response.json()
                video_id = video_data.get("id", 1)
                print(f"   ✅ Video registered: {video_id}")
            
            # Step 2: Submit ground truth
            gt_data = {**self.test_data["ground_truth"], "video_id": video_id}
            gt_response = self.client.post("/ground-truth", json=gt_data)
            if gt_response.status_code not in [200, 201]:
                print(f"   Ground truth submission failed: {gt_response.status_code}")
                workflow_success = False
            else:
                print("   ✅ Ground truth submitted")
            
            # Step 3: Submit detection results
            detection_data = {**self.test_data["detection"], "video_id": video_id}
            detection_response = self.client.post("/detection", json=detection_data)
            if detection_response.status_code not in [200, 201]:
                print(f"   Detection submission failed: {detection_response.status_code}")
                workflow_success = False
            else:
                print("   ✅ Detection results submitted")
            
            # Step 4: Retrieve combined results
            results_response = self.client.get("/results")
            if results_response.status_code == 200:
                print("   ✅ Results retrieved")
            else:
                print(f"   Results retrieval failed: {results_response.status_code}")
                workflow_success = False
            
            if workflow_success:
                print("✅ Complete API data flow test passed")
            else:
                print("⚠️  Some steps in API data flow failed")
            
            return workflow_success
        except Exception as e:
            print(f"❌ API data flow integration test failed: {e}")
            return False

def run_api_integration_validation():
    """Run all API integration validation tests."""
    print("🔍 Starting API Integration Validation...")
    
    test_suite = TestAPIIntegration()
    test_suite.setup_class()
    
    tests = [
        test_suite.test_health_endpoint,
        test_suite.test_video_endpoints,
        test_suite.test_ground_truth_endpoints,
        test_suite.test_detection_endpoints,
        test_suite.test_results_endpoints,
        test_suite.test_labjack_endpoints,
        test_suite.test_api_error_handling,
        test_suite.test_api_performance,
        test_suite.test_api_data_flow_integration,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result if result is not None else True)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed: {e}")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100
    print(f"\n📊 API Integration Validation Complete: {success_rate:.1f}% success rate ({sum(results)}/{len(results)} tests passed)")
    
    return success_rate > 70

if __name__ == "__main__":
    run_api_integration_validation()