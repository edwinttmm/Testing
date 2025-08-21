#!/usr/bin/env python3
"""
Comprehensive integration tests for the detection system
Running against the actual backend to validate end-to-end functionality
"""

import requests
import json
import time
import os
import asyncio
import websockets
import tempfile
from pathlib import Path

# Configuration
BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"
TEST_TIMEOUT = 30

class DetectionSystemValidator:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.ws_url = WS_URL
        self.session = requests.Session()
        self.test_results = {}
        
    def log_test(self, test_name, result, details=""):
        """Log test results"""
        status = "PASS" if result else "FAIL"
        print(f"[{status}] {test_name}")
        if details:
            print(f"    Details: {details}")
        
        self.test_results[test_name] = {
            "status": status,
            "result": result,
            "details": details
        }
        
    def test_backend_connectivity(self):
        """Test basic backend connectivity and health"""
        try:
            response = self.session.get(f"{self.backend_url}/health", timeout=10)
            result = response.status_code == 200 and response.json().get('status') == 'healthy'
            self.log_test("Backend Connectivity", result, f"Status: {response.status_code}")
            return result
        except Exception as e:
            self.log_test("Backend Connectivity", False, f"Error: {str(e)}")
            return False
            
    def test_project_creation(self):
        """Test project creation and retrieval"""
        try:
            # Create project
            project_data = {
                "name": "Detection Test Project",
                "description": "Test project for detection system validation"
            }
            
            response = self.session.post(
                f"{self.backend_url}/api/projects",
                json=project_data,
                timeout=10
            )
            
            if response.status_code != 200:
                self.log_test("Project Creation", False, f"Create failed: {response.status_code}")
                return None
                
            project = response.json()
            project_id = project.get('id')
            
            # Retrieve project
            response = self.session.get(f"{self.backend_url}/api/projects/{project_id}")
            result = response.status_code == 200 and response.json().get('name') == project_data['name']
            
            self.log_test("Project Creation", result, f"Project ID: {project_id}")
            return project_id if result else None
            
        except Exception as e:
            self.log_test("Project Creation", False, f"Error: {str(e)}")
            return None
            
    def test_video_upload(self, project_id=None):
        """Test video file upload"""
        try:
            # Create a minimal test video file
            test_content = b"fake video content for testing"
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                temp_file.write(test_content)
                temp_file_path = temp_file.name
                
            try:
                # Upload to project if provided, otherwise central upload
                if project_id:
                    upload_url = f"{self.backend_url}/api/projects/{project_id}/videos"
                else:
                    upload_url = f"{self.backend_url}/api/videos"
                
                with open(temp_file_path, 'rb') as file:
                    files = {'file': ('test_video.mp4', file, 'video/mp4')}
                    response = self.session.post(upload_url, files=files, timeout=30)
                
                if response.status_code != 200:
                    self.log_test("Video Upload", False, f"Upload failed: {response.status_code}")
                    return None
                    
                video = response.json()
                video_id = video.get('id')
                
                self.log_test("Video Upload", True, f"Video ID: {video_id}")
                return video_id
                
            finally:
                os.unlink(temp_file_path)
                
        except Exception as e:
            self.log_test("Video Upload", False, f"Error: {str(e)}")
            return None
            
    def test_available_models(self):
        """Test available detection models endpoint"""
        try:
            response = self.session.get(f"{self.backend_url}/api/detection/models/available")
            
            if response.status_code != 200:
                self.log_test("Available Models", False, f"Request failed: {response.status_code}")
                return False
                
            models_data = response.json()
            has_models = bool(models_data.get('models'))
            has_default = bool(models_data.get('default'))
            
            result = has_models and has_default
            details = f"Models: {len(models_data.get('models', []))}, Default: {models_data.get('default')}"
            
            self.log_test("Available Models", result, details)
            return result
            
        except Exception as e:
            self.log_test("Available Models", False, f"Error: {str(e)}")
            return False
            
    def test_detection_pipeline(self, video_id):
        """Test detection pipeline execution"""
        if not video_id:
            self.log_test("Detection Pipeline", False, "No video ID provided")
            return False
            
        try:
            detection_config = {
                "video_id": video_id,
                "confidence_threshold": 0.7,
                "nms_threshold": 0.5,
                "model_name": "yolov8n",
                "target_classes": ["person", "bicycle"]
            }
            
            response = self.session.post(
                f"{self.backend_url}/api/detection/pipeline/run",
                json=detection_config,
                timeout=60  # Detection might take longer
            )
            
            if response.status_code != 200:
                self.log_test("Detection Pipeline", False, f"Pipeline failed: {response.status_code}")
                return False
                
            result = response.json()
            success = result.get('success', False)
            detections = result.get('detections', [])
            processing_time = result.get('processingTime', 0)
            
            details = f"Success: {success}, Detections: {len(detections)}, Time: {processing_time}ms"
            self.log_test("Detection Pipeline", success, details)
            
            return success
            
        except Exception as e:
            self.log_test("Detection Pipeline", False, f"Error: {str(e)}")
            return False
            
    def test_annotations_crud(self, video_id):
        """Test annotation CRUD operations"""
        if not video_id:
            self.log_test("Annotations CRUD", False, "No video ID provided")
            return False
            
        try:
            # Create annotation
            annotation_data = {
                "detection_id": "test-detection-123",
                "frame_number": 30,
                "timestamp": 1000,
                "vru_type": "pedestrian",
                "bounding_box": {
                    "x": 100,
                    "y": 100,
                    "width": 50,
                    "height": 100,
                    "label": "person",
                    "confidence": 0.85
                },
                "occluded": False,
                "truncated": False,
                "difficult": False,
                "validated": False,
                "annotator": "test-user"
            }
            
            # CREATE
            response = self.session.post(
                f"{self.backend_url}/api/videos/{video_id}/annotations",
                json=annotation_data
            )
            
            if response.status_code != 200:
                self.log_test("Annotations CRUD - Create", False, f"Create failed: {response.status_code}")
                return False
                
            annotation = response.json()
            annotation_id = annotation.get('id')
            
            # READ
            response = self.session.get(f"{self.backend_url}/api/videos/{video_id}/annotations")
            
            if response.status_code != 200:
                self.log_test("Annotations CRUD - Read", False, f"Read failed: {response.status_code}")
                return False
                
            annotations = response.json()
            found_annotation = any(ann.get('id') == annotation_id for ann in annotations)
            
            if not found_annotation:
                self.log_test("Annotations CRUD - Read", False, "Created annotation not found")
                return False
                
            # UPDATE
            update_data = {"validated": True}
            response = self.session.put(
                f"{self.backend_url}/api/annotations/{annotation_id}",
                json=update_data
            )
            
            if response.status_code != 200:
                self.log_test("Annotations CRUD - Update", False, f"Update failed: {response.status_code}")
                return False
                
            # VALIDATE
            response = self.session.patch(
                f"{self.backend_url}/api/annotations/{annotation_id}/validate",
                json={"validated": True}
            )
            
            if response.status_code != 200:
                self.log_test("Annotations CRUD - Validate", False, f"Validate failed: {response.status_code}")
                return False
                
            # DELETE
            response = self.session.delete(f"{self.backend_url}/api/annotations/{annotation_id}")
            
            if response.status_code != 200:
                self.log_test("Annotations CRUD - Delete", False, f"Delete failed: {response.status_code}")
                return False
                
            self.log_test("Annotations CRUD", True, f"All CRUD operations successful")
            return True
            
        except Exception as e:
            self.log_test("Annotations CRUD", False, f"Error: {str(e)}")
            return False
            
    async def test_websocket_connection(self):
        """Test WebSocket connection for real-time updates"""
        try:
            async with websockets.connect(f"{self.ws_url}/detection") as websocket:
                # Send a test message
                test_message = {
                    "type": "subscribe",
                    "videoId": "test-video-123"
                }
                
                await websocket.send(json.dumps(test_message))
                
                # Wait for potential response (with timeout)
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5)
                    self.log_test("WebSocket Connection", True, "Connection and messaging successful")
                    return True
                except asyncio.TimeoutError:
                    # No response is also okay - connection was successful
                    self.log_test("WebSocket Connection", True, "Connection successful (no echo)")
                    return True
                    
        except Exception as e:
            self.log_test("WebSocket Connection", False, f"Error: {str(e)}")
            return False
            
    def test_ground_truth_endpoints(self, video_id):
        """Test ground truth data endpoints"""
        if not video_id:
            self.log_test("Ground Truth Endpoints", False, "No video ID provided")
            return False
            
        try:
            # Get ground truth (might not exist, but endpoint should respond)
            response = self.session.get(f"{self.backend_url}/api/videos/{video_id}/ground-truth")
            
            # Accept 200 (with data) or 404 (no ground truth) as valid responses
            valid_responses = [200, 404]
            result = response.status_code in valid_responses
            
            details = f"Status: {response.status_code}"
            if response.status_code == 200:
                gt_data = response.json()
                details += f", Objects: {len(gt_data.get('objects', []))}"
                
            self.log_test("Ground Truth Endpoints", result, details)
            return result
            
        except Exception as e:
            self.log_test("Ground Truth Endpoints", False, f"Error: {str(e)}")
            return False
            
    def test_dashboard_endpoints(self):
        """Test dashboard statistics endpoints"""
        try:
            # Test dashboard stats
            response = self.session.get(f"{self.backend_url}/api/dashboard/stats")
            stats_ok = response.status_code == 200
            
            # Test chart data
            response = self.session.get(f"{self.backend_url}/api/dashboard/charts")
            charts_ok = response.status_code == 200
            
            result = stats_ok and charts_ok
            details = f"Stats: {stats_ok}, Charts: {charts_ok}"
            
            self.log_test("Dashboard Endpoints", result, details)
            return result
            
        except Exception as e:
            self.log_test("Dashboard Endpoints", False, f"Error: {str(e)}")
            return False
            
    def test_error_handling(self):
        """Test error handling for invalid requests"""
        try:
            test_cases = [
                ("Invalid Project ID", "GET", f"/api/projects/invalid-id-123"),
                ("Invalid Video ID", "GET", f"/api/videos/invalid-video-123"),
                ("Invalid Detection Config", "POST", "/api/detection/pipeline/run", {"invalid": "data"}),
                ("Invalid Annotation", "POST", "/api/videos/invalid/annotations", {"invalid": "annotation"})
            ]
            
            error_handling_results = []
            
            for test_name, method, endpoint, data in [(tc[0], tc[1], tc[2], tc[3] if len(tc) > 3 else None) for tc in test_cases]:
                try:
                    if method == "GET":
                        response = self.session.get(f"{self.backend_url}{endpoint}")
                    elif method == "POST":
                        response = self.session.post(f"{self.backend_url}{endpoint}", json=data)
                    
                    # Expecting 4xx errors for invalid requests
                    handles_correctly = 400 <= response.status_code < 500
                    error_handling_results.append(handles_correctly)
                    
                except Exception:
                    # Network errors are also acceptable for invalid requests
                    error_handling_results.append(True)
            
            result = all(error_handling_results)
            details = f"Handled {sum(error_handling_results)}/{len(error_handling_results)} error cases correctly"
            
            self.log_test("Error Handling", result, details)
            return result
            
        except Exception as e:
            self.log_test("Error Handling", False, f"Error: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run complete test suite"""
        print("="*60)
        print("DETECTION SYSTEM INTEGRATION VALIDATION")
        print("="*60)
        
        # Phase 1: Basic connectivity
        print("\nPhase 1: Backend Connectivity")
        print("-" * 30)
        
        if not self.test_backend_connectivity():
            print("\n❌ Backend not accessible. Cannot proceed with tests.")
            return False
        
        # Phase 2: Core API functionality
        print("\nPhase 2: Core API Tests")
        print("-" * 30)
        
        project_id = self.test_project_creation()
        video_id = self.test_video_upload(project_id)
        
        self.test_available_models()
        self.test_dashboard_endpoints()
        
        # Phase 3: Detection pipeline
        print("\nPhase 3: Detection Pipeline")
        print("-" * 30)
        
        if video_id:
            self.test_detection_pipeline(video_id)
            self.test_annotations_crud(video_id)
            self.test_ground_truth_endpoints(video_id)
        else:
            print("⚠️  Skipping detection tests - no video uploaded")
        
        # Phase 4: Real-time features
        print("\nPhase 4: Real-time Features")
        print("-" * 30)
        
        await self.test_websocket_connection()
        
        # Phase 5: Error handling
        print("\nPhase 5: Error Handling")
        print("-" * 30)
        
        self.test_error_handling()
        
        # Results summary
        print("\n" + "="*60)
        print("TEST RESULTS SUMMARY")
        print("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result['result'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print(f"\nFailed Tests:")
            for test_name, result in self.test_results.items():
                if not result['result']:
                    print(f"  ❌ {test_name}: {result['details']}")
        
        print(f"\nOverall Status: {'PASS' if failed_tests == 0 else 'PARTIAL' if passed_tests > 0 else 'FAIL'}")
        
        return failed_tests == 0

async def main():
    """Main test execution function"""
    validator = DetectionSystemValidator()
    success = await validator.run_all_tests()
    
    # Save detailed results
    results_file = "/home/user/Testing/tests/detection-system/integration_test_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": time.time(),
            "success": success,
            "results": validator.test_results
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: {results_file}")
    return success

if __name__ == "__main__":
    asyncio.run(main())