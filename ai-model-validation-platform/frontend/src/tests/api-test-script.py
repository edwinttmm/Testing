#!/usr/bin/env python3
"""
Comprehensive API Testing Script
Tests all video endpoints and monitors status changes
"""

import requests
import json
import time
from datetime import datetime
import sys

class APITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.errors = []

    def log_test(self, test_name, result, details=None):
        timestamp = datetime.now().isoformat()
        test_result = {
            'timestamp': timestamp,
            'test': test_name,
            'result': result,
            'details': details or {}
        }
        self.test_results.append(test_result)
        
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {json.dumps(details, indent=2)}")
        print()

    def test_endpoint(self, method, endpoint, data=None, expected_status=200):
        """Test a specific API endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, timeout=10)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            result = response.status_code == expected_status
            
            try:
                response_data = response.json()
            except:
                response_data = response.text[:500]  # First 500 chars
            
            details = {
                'method': method.upper(),
                'url': url,
                'status_code': response.status_code,
                'expected_status': expected_status,
                'response_size': len(response.text),
                'response': response_data
            }
            
            if data:
                details['request_data'] = data
            
            self.log_test(f"{method.upper()} {endpoint}", result, details)
            return result, response_data, response.status_code
            
        except Exception as e:
            error_details = {
                'method': method.upper(),
                'url': url,
                'error': str(e),
                'error_type': type(e).__name__
            }
            self.errors.append(error_details)
            self.log_test(f"{method.upper()} {endpoint}", False, error_details)
            return False, None, None

    def test_manual_status_issue(self):
        """Specifically test the Manual status issue"""
        print("=" * 60)
        print("🔍 TESTING MANUAL STATUS ISSUE")
        print("=" * 60)
        
        # Get all videos
        success, videos_data, status_code = self.test_endpoint('GET', '/api/videos')
        if not success or not videos_data:
            print("❌ Cannot get videos list")
            return
        
        videos = videos_data if isinstance(videos_data, list) else []
        print(f"📹 Found {len(videos)} videos in the system")
        
        # Test first 3 videos for Manual status
        for i, video in enumerate(videos[:3]):
            video_id = video.get('id')
            filename = video.get('filename', 'unknown')
            status = video.get('status', 'unknown')
            
            print(f"\n🎬 Testing Video {i+1}: {filename} (ID: {video_id})")
            print(f"   Status from /api/videos: {status}")
            
            # Test individual video endpoint
            success, video_data, _ = self.test_endpoint('GET', f'/api/videos/{video_id}')
            if success and video_data:
                individual_status = video_data.get('status', 'unknown')
                processing_status = video_data.get('processing_status', 'none')
                print(f"   Status from /api/videos/{video_id}: {individual_status}")
                print(f"   Processing status: {processing_status}")
                
                # Check for Manual status
                if status == 'Manual' or individual_status == 'Manual':
                    print(f"🚨 MANUAL STATUS DETECTED!")
                    
                    # Get detections count
                    success, detections_data, _ = self.test_endpoint('GET', f'/api/videos/{video_id}/detections')
                    if success:
                        detections_count = len(detections_data) if isinstance(detections_data, list) else 0
                        print(f"   Detections found: {detections_count}")
                        
                        if detections_count > 0:
                            print(f"   🤔 Video has {detections_count} detections but shows Manual status")
                            print(f"   This indicates a potential status synchronization issue")
                        else:
                            print(f"   No detections found - Manual status may be correct")
            
            # Test status endpoint
            success, status_data, _ = self.test_endpoint('GET', f'/api/videos/{video_id}/status')
            if success and status_data:
                print(f"   Status endpoint response: {json.dumps(status_data)}")
        
        print("\n" + "=" * 60)

    def test_detection_workflow(self, video_id):
        """Test complete detection workflow for a video"""
        print(f"\n🎯 Testing Detection Workflow for video: {video_id}")
        
        # Get initial status
        success, initial_data, _ = self.test_endpoint('GET', f'/api/videos/{video_id}')
        if not success:
            print(f"❌ Cannot get initial video status")
            return
            
        initial_status = initial_data.get('status', 'unknown')
        print(f"Initial status: {initial_status}")
        
        # Trigger detection
        detection_payload = {"confidence_threshold": 0.5}
        success, detection_response, status_code = self.test_endpoint(
            'POST', f'/api/videos/{video_id}/detect', detection_payload
        )
        
        if success:
            print(f"✅ Detection triggered successfully")
            print(f"Response: {json.dumps(detection_response, indent=2)}")
        else:
            print(f"❌ Failed to trigger detection (Status: {status_code})")
            return
        
        # Monitor status changes
        print("🔄 Monitoring status changes...")
        for check in range(10):  # Check for 50 seconds max
            time.sleep(5)
            
            success, current_data, _ = self.test_endpoint('GET', f'/api/videos/{video_id}')
            if success:
                current_status = current_data.get('status', 'unknown')
                print(f"Status check {check+1}: {current_status}")
                
                if current_status != initial_status:
                    print(f"📊 Status changed: {initial_status} → {current_status}")
                
                if current_status in ['completed', 'failed']:
                    print(f"🏁 Final status reached: {current_status}")
                    break
        
        # Final check - get detections
        success, final_detections, _ = self.test_endpoint('GET', f'/api/videos/{video_id}/detections')
        if success:
            detections_count = len(final_detections) if isinstance(final_detections, list) else 0
            print(f"Final detections count: {detections_count}")

    def run_comprehensive_tests(self):
        """Run all comprehensive tests"""
        print("🚀 Starting Comprehensive API Tests")
        print("=" * 60)
        
        # Basic health checks
        self.test_endpoint('GET', '/health')
        self.test_endpoint('GET', '/api/docs')
        
        # Video API tests
        self.test_endpoint('GET', '/api/videos')
        self.test_endpoint('GET', '/api/videos/stats')
        
        # Test Manual Status Issue
        self.test_manual_status_issue()
        
        # Project tests
        self.test_endpoint('GET', '/api/projects')
        
        # Test session tests
        self.test_endpoint('GET', '/api/test-sessions')
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = len([t for t in self.test_results if t['result']])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Errors: {len(self.errors)}")
        
        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"   {error['method']} {error['url']}: {error['error']}")
        
        # Save results to file
        results_file = f"api_test_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': total_tests,
                    'passed_tests': passed_tests,
                    'failed_tests': failed_tests,
                    'error_count': len(self.errors)
                },
                'test_results': self.test_results,
                'errors': self.errors,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"\n📄 Full results saved to: {results_file}")

if __name__ == "__main__":
    tester = APITester()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "manual":
            tester.test_manual_status_issue()
        elif sys.argv[1] == "workflow" and len(sys.argv) > 2:
            video_id = sys.argv[2]
            tester.test_detection_workflow(video_id)
        else:
            print("Usage: python api-test-script.py [manual|workflow <video_id>]")
    else:
        tester.run_comprehensive_tests()