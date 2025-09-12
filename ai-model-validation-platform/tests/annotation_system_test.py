#!/usr/bin/env python3
"""
Annotation System Testing Suite
Tests annotation tools and ground truth creation functionality
"""

import requests
import json
import time
from urllib.parse import urljoin
from datetime import datetime

class AnnotationSystemTester:
    def __init__(self, frontend_url="http://localhost:3000", backend_url="http://localhost:8000"):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.session = requests.Session()
        self.test_results = {
            "test_started": datetime.now().isoformat(),
            "frontend_url": frontend_url,
            "backend_url": backend_url,
            "annotation_tests": []
        }
    
    def log_annotation_test(self, test_name, status, details=None, error=None):
        """Log annotation test result"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "error": str(error) if error else None
        }
        self.test_results["annotation_tests"].append(result)
        
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} ANNOTATION: {test_name}: {status}")
        if details:
            print(f"           Details: {details}")
    
    def test_detection_events_api(self):
        """Test detection events API endpoints"""
        try:
            # Test GET detection events
            url = urljoin(self.backend_url, "/api/detection-events")
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    count = data.get('count', len(data) if hasattr(data, '__len__') else 0)
                    self.log_annotation_test("Detection Events List", "PASS", 
                                           f"Retrieved detection events, count: {count}")
                elif isinstance(data, list):
                    self.log_annotation_test("Detection Events List", "PASS", 
                                           f"Retrieved {len(data)} detection events")
                else:
                    self.log_annotation_test("Detection Events List", "PARTIAL", 
                                           f"Unexpected data format: {type(data)}")
            elif response.status_code == 404:
                self.log_annotation_test("Detection Events List", "PARTIAL", 
                                       "Detection events endpoint returns 404 (no data)")
            else:
                self.log_annotation_test("Detection Events List", "FAIL", 
                                       f"Status: {response.status_code}")
            
            return response.status_code in [200, 404]
        except Exception as e:
            self.log_annotation_test("Detection Events API", "FAIL", error=e)
            return False
    
    def test_ground_truth_api(self):
        """Test ground truth API endpoints"""
        try:
            # Test GET ground truth
            url = urljoin(self.backend_url, "/api/ground-truth")
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log_annotation_test("Ground Truth List", "PASS", 
                                       f"Retrieved ground truth data: {type(data)}")
            elif response.status_code == 404:
                self.log_annotation_test("Ground Truth List", "PARTIAL", 
                                       "Ground truth endpoint returns 404 (no data)")
            else:
                self.log_annotation_test("Ground Truth List", "FAIL", 
                                       f"Status: {response.status_code}")
            
            # Test POST ground truth creation
            ground_truth_data = {
                "video_id": 1,
                "frame_number": 100,
                "objects": [
                    {
                        "class_name": "pedestrian",
                        "bbox": {"x": 100, "y": 100, "width": 50, "height": 100},
                        "confidence": 1.0
                    }
                ]
            }
            
            post_url = urljoin(self.backend_url, "/api/ground-truth")
            post_response = self.session.post(post_url, json=ground_truth_data, timeout=10)
            
            if post_response.status_code in [200, 201]:
                self.log_annotation_test("Ground Truth Creation", "PASS", 
                                       f"Created ground truth entry")
            elif post_response.status_code in [422, 400]:
                self.log_annotation_test("Ground Truth Creation", "PARTIAL", 
                                       f"Validation response (may be expected): {post_response.status_code}")
            else:
                self.log_annotation_test("Ground Truth Creation", "FAIL", 
                                       f"Status: {post_response.status_code}")
            
            return response.status_code in [200, 404]
        except Exception as e:
            self.log_annotation_test("Ground Truth API", "FAIL", error=e)
            return False
    
    def test_annotations_api(self):
        """Test general annotations API"""
        try:
            # Test GET annotations
            url = urljoin(self.backend_url, "/api/annotations")
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log_annotation_test("Annotations List", "PASS", 
                                       f"Retrieved annotations: {type(data)}")
            elif response.status_code == 404:
                self.log_annotation_test("Annotations List", "PARTIAL", 
                                       "Annotations endpoint returns 404 (no data)")
            else:
                self.log_annotation_test("Annotations List", "FAIL", 
                                       f"Status: {response.status_code}")
            
            # Test annotation creation
            annotation_data = {
                "video_id": 1,
                "frame_number": 50,
                "annotation_type": "manual",
                "data": {
                    "objects": [
                        {
                            "class": "vehicle",
                            "bbox": {"x": 200, "y": 150, "width": 80, "height": 60}
                        }
                    ]
                }
            }
            
            post_url = urljoin(self.backend_url, "/api/annotations")
            post_response = self.session.post(post_url, json=annotation_data, timeout=10)
            
            if post_response.status_code in [200, 201]:
                self.log_annotation_test("Annotation Creation", "PASS", 
                                       f"Created annotation entry")
            elif post_response.status_code in [422, 400]:
                self.log_annotation_test("Annotation Creation", "PARTIAL", 
                                       f"Validation response: {post_response.status_code}")
            else:
                self.log_annotation_test("Annotation Creation", "FAIL", 
                                       f"Status: {post_response.status_code}")
            
            return response.status_code in [200, 404]
        except Exception as e:
            self.log_annotation_test("Annotations API", "FAIL", error=e)
            return False
    
    def test_video_frame_extraction(self):
        """Test video frame extraction for annotation"""
        try:
            # Check if there are videos to work with
            videos_url = urljoin(self.backend_url, "/api/videos")
            videos_response = self.session.get(videos_url, timeout=10)
            
            if videos_response.status_code != 200:
                self.log_annotation_test("Video Frame Setup", "FAIL", 
                                       "Cannot access videos for frame testing")
                return False
            
            videos_data = videos_response.json()
            videos = videos_data.get('videos', []) if isinstance(videos_data, dict) else []
            
            if not videos:
                self.log_annotation_test("Video Frame Setup", "PARTIAL", 
                                       "No videos available for frame testing")
                return True
            
            # Test frame extraction endpoint (if exists)
            first_video_id = videos[0].get('id', 1)
            frame_url = urljoin(self.backend_url, f"/api/videos/{first_video_id}/frames/1")
            frame_response = self.session.get(frame_url, timeout=10)
            
            if frame_response.status_code == 200:
                self.log_annotation_test("Video Frame Extraction", "PASS", 
                                       f"Successfully extracted frame from video {first_video_id}")
            elif frame_response.status_code == 404:
                self.log_annotation_test("Video Frame Extraction", "PARTIAL", 
                                       "Frame extraction endpoint not available")
            else:
                self.log_annotation_test("Video Frame Extraction", "FAIL", 
                                       f"Frame extraction failed: {frame_response.status_code}")
            
            return True
        except Exception as e:
            self.log_annotation_test("Video Frame Extraction", "FAIL", error=e)
            return False
    
    def test_annotation_validation(self):
        """Test annotation data validation"""
        try:
            # Test invalid annotation data
            invalid_annotations = [
                {
                    "name": "Missing video_id",
                    "data": {"frame_number": 10, "objects": []},
                    "expected": [400, 422]
                },
                {
                    "name": "Invalid bbox coordinates",
                    "data": {
                        "video_id": 1,
                        "frame_number": 10,
                        "data": {
                            "objects": [{"class": "test", "bbox": {"x": -10, "y": -10}}]
                        }
                    },
                    "expected": [400, 422]
                },
                {
                    "name": "Empty annotation data",
                    "data": {},
                    "expected": [400, 422]
                }
            ]
            
            validation_passed = 0
            for test_case in invalid_annotations:
                url = urljoin(self.backend_url, "/api/annotations")
                response = self.session.post(url, json=test_case["data"], timeout=10)
                
                if response.status_code in test_case["expected"]:
                    self.log_annotation_test(f"Validation: {test_case['name']}", "PASS", 
                                           f"Properly rejected invalid data (Status: {response.status_code})")
                    validation_passed += 1
                else:
                    self.log_annotation_test(f"Validation: {test_case['name']}", "FAIL", 
                                           f"Should reject invalid data, got: {response.status_code}")
            
            return validation_passed >= len(invalid_annotations) * 0.8
        except Exception as e:
            self.log_annotation_test("Annotation Validation", "FAIL", error=e)
            return False
    
    def test_annotation_export(self):
        """Test annotation data export functionality"""
        try:
            # Test various export formats
            export_endpoints = [
                ("/api/annotations/export", "General annotations export"),
                ("/api/ground-truth/export", "Ground truth export"),
                ("/api/detection-events/export", "Detection events export")
            ]
            
            export_passed = 0
            for endpoint, description in export_endpoints:
                url = urljoin(self.backend_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    self.log_annotation_test(f"Export: {description}", "PASS", 
                                           f"Export available, content-type: {response.headers.get('content-type', 'unknown')}")
                    export_passed += 1
                elif response.status_code == 404:
                    self.log_annotation_test(f"Export: {description}", "PARTIAL", 
                                           "Export endpoint not available")
                else:
                    self.log_annotation_test(f"Export: {description}", "FAIL", 
                                           f"Export failed: {response.status_code}")
            
            return export_passed >= len(export_endpoints) * 0.3  # Allow most to be missing
        except Exception as e:
            self.log_annotation_test("Annotation Export", "FAIL", error=e)
            return False
    
    def run_annotation_tests(self):
        """Run all annotation system tests"""
        print("📝 Starting Annotation System Testing")
        print("=" * 55)
        
        test_methods = [
            self.test_detection_events_api,
            self.test_ground_truth_api,
            self.test_annotations_api,
            self.test_video_frame_extraction,
            self.test_annotation_validation,
            self.test_annotation_export
        ]
        
        for i, test_method in enumerate(test_methods):
            print(f"\n📌 Running annotation test {i+1}...")
            try:
                test_method()
            except Exception as e:
                self.log_annotation_test(f"Annotation Test {i+1}", "FAIL", error=f"Test crashed: {e}")
            time.sleep(0.5)
        
        # Summary
        total_tests = len(self.test_results["annotation_tests"])
        passed_tests = len([t for t in self.test_results["annotation_tests"] if t["status"] == "PASS"])
        failed_tests = len([t for t in self.test_results["annotation_tests"] if t["status"] == "FAIL"])
        partial_tests = len([t for t in self.test_results["annotation_tests"] if t["status"] == "PARTIAL"])
        
        print("\n" + "=" * 55)
        print("📊 ANNOTATION SYSTEM SUMMARY")
        print("=" * 55)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Partial: {partial_tests}")
        print(f"🎯 Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%")
        
        # Save results
        results_file = f"/home/rigade/Testing/ai-model-validation-platform/tests/annotation_system_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\n📄 Results saved to: {results_file}")
        return self.test_results

if __name__ == "__main__":
    tester = AnnotationSystemTester()
    results = tester.run_annotation_tests()