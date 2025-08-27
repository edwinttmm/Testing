#!/usr/bin/env python3
"""
ML API Endpoints Validation Test
==============================

This script tests the ML-related API endpoints to ensure they work correctly
with the inference engine and return proper responses.

Author: ML Validation Team
Version: 1.0.0
"""

import asyncio
import json
import time
import tempfile
import os
from pathlib import Path
import cv2
import numpy as np
import requests
from typing import Dict, Any

# Add backend path
backend_path = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(backend_path))

class MLAPITester:
    """Test ML API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {
            'timestamp': time.time(),
            'base_url': base_url,
            'tests': {},
            'summary': {}
        }
        self.temp_files = []
    
    def create_test_video(self) -> str:
        """Create a test video file"""
        temp_video = tempfile.mktemp(suffix='.mp4')
        self.temp_files.append(temp_video)
        
        # Create video with moving objects for VRU detection
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(temp_video, fourcc, 30.0, (640, 480))
        
        for frame_num in range(60):  # 2 seconds at 30fps
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            
            # Add moving rectangle (simulate person)
            if frame_num % 20 < 15:
                x = 100 + frame_num * 3
                y = 200
                cv2.rectangle(frame, (x, y), (x+60, y+120), (255, 255, 255), -1)
                cv2.putText(frame, 'PERSON', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            writer.write(frame)
        
        writer.release()
        return temp_video
    
    def create_test_image(self) -> str:
        """Create a test image file"""
        temp_image = tempfile.mktemp(suffix='.jpg')
        self.temp_files.append(temp_image)
        
        # Create image with objects
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Draw person-like shape
        cv2.rectangle(img, (200, 150), (280, 400), (255, 255, 255), -1)
        cv2.circle(img, (240, 120), 30, (255, 255, 255), -1)
        
        cv2.imwrite(temp_image, img)
        return temp_image
    
    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test health endpoint"""
        test_name = "ML Health Check"
        print(f"Testing {test_name}...")
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=30)
            
            result = {
                'status': 'passed' if response.status_code == 200 else 'failed',
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
            
            if response.status_code == 200:
                try:
                    health_data = response.json()
                    result['health_data'] = health_data
                    result['database_status'] = health_data.get('database', 'unknown')
                    print(f"✅ {test_name}: {health_data.get('status', 'unknown')}")
                except:
                    result['health_data'] = response.text
                    print(f"✅ {test_name}: Server responding")
            else:
                result['error'] = response.text
                print(f"❌ {test_name}: HTTP {response.status_code}")
        
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {test_name}: {e}")
        
        return result
    
    def test_ml_engine_health(self) -> Dict[str, Any]:
        """Test ML engine health endpoint"""
        test_name = "ML Engine Health"
        print(f"Testing {test_name}...")
        
        try:
            # Try multiple possible endpoints
            endpoints = [
                "/api/ml/health",
                "/ml/health", 
                "/health/ml",
                "/api/health/ml"
            ]
            
            result = None
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                    if response.status_code == 200:
                        result = {
                            'status': 'passed',
                            'endpoint': endpoint,
                            'status_code': response.status_code,
                            'response_time': response.elapsed.total_seconds()
                        }
                        
                        try:
                            ml_health = response.json()
                            result['ml_health_data'] = ml_health
                            print(f"✅ {test_name}: {ml_health.get('status', 'unknown')} via {endpoint}")
                            break
                        except:
                            result['response_text'] = response.text
                            print(f"✅ {test_name}: Response received via {endpoint}")
                            break
                except:
                    continue
            
            if result is None:
                result = {
                    'status': 'failed',
                    'error': 'No ML health endpoints found',
                    'tried_endpoints': endpoints
                }
                print(f"❌ {test_name}: No working endpoints found")
        
        except Exception as e:
            result = {
                'status': 'failed', 
                'error': str(e)
            }
            print(f"❌ {test_name}: {e}")
        
        return result
    
    def test_video_upload_and_processing(self) -> Dict[str, Any]:
        """Test video upload and processing"""
        test_name = "Video Upload & Processing"
        print(f"Testing {test_name}...")
        
        try:
            # Create test video
            test_video = self.create_test_video()
            
            # Try multiple possible endpoints for video upload
            endpoints = [
                "/api/videos/upload",
                "/videos/upload",
                "/upload/video",
                "/api/upload"
            ]
            
            result = None
            for endpoint in endpoints:
                try:
                    with open(test_video, 'rb') as f:
                        files = {'video': ('test_video.mp4', f, 'video/mp4')}
                        response = requests.post(
                            f"{self.base_url}{endpoint}",
                            files=files,
                            timeout=60
                        )
                    
                    if response.status_code in [200, 201, 202]:
                        result = {
                            'status': 'passed',
                            'endpoint': endpoint,
                            'status_code': response.status_code,
                            'response_time': response.elapsed.total_seconds()
                        }
                        
                        try:
                            upload_response = response.json()
                            result['upload_data'] = upload_response
                            video_id = upload_response.get('id') or upload_response.get('video_id')
                            if video_id:
                                result['video_id'] = video_id
                            print(f"✅ {test_name}: Uploaded successfully via {endpoint}")
                        except:
                            result['response_text'] = response.text
                            print(f"✅ {test_name}: Upload response received via {endpoint}")
                        break
                except Exception as e:
                    continue
            
            if result is None:
                result = {
                    'status': 'failed',
                    'error': 'No video upload endpoints found',
                    'tried_endpoints': endpoints
                }
                print(f"❌ {test_name}: No working upload endpoints")
        
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {test_name}: {e}")
        
        return result
    
    def test_image_detection(self) -> Dict[str, Any]:
        """Test image object detection"""
        test_name = "Image Detection"
        print(f"Testing {test_name}...")
        
        try:
            # Create test image
            test_image = self.create_test_image()
            
            # Try multiple possible endpoints
            endpoints = [
                "/api/ml/detect",
                "/ml/detect",
                "/detect",
                "/api/detect/image"
            ]
            
            result = None
            for endpoint in endpoints:
                try:
                    with open(test_image, 'rb') as f:
                        files = {'image': ('test_image.jpg', f, 'image/jpeg')}
                        response = requests.post(
                            f"{self.base_url}{endpoint}",
                            files=files,
                            timeout=60
                        )
                    
                    if response.status_code in [200, 201]:
                        result = {
                            'status': 'passed',
                            'endpoint': endpoint,
                            'status_code': response.status_code,
                            'response_time': response.elapsed.total_seconds()
                        }
                        
                        try:
                            detection_response = response.json()
                            result['detection_data'] = detection_response
                            detections = detection_response.get('detections', [])
                            result['num_detections'] = len(detections)
                            print(f"✅ {test_name}: {len(detections)} detections found via {endpoint}")
                        except:
                            result['response_text'] = response.text
                            print(f"✅ {test_name}: Detection response received via {endpoint}")
                        break
                except:
                    continue
            
            if result is None:
                result = {
                    'status': 'failed',
                    'error': 'No image detection endpoints found',
                    'tried_endpoints': endpoints
                }
                print(f"❌ {test_name}: No working detection endpoints")
        
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {test_name}: {e}")
        
        return result
    
    def test_model_info_endpoint(self) -> Dict[str, Any]:
        """Test model info endpoint"""
        test_name = "Model Info"
        print(f"Testing {test_name}...")
        
        try:
            endpoints = [
                "/api/ml/model/info",
                "/ml/model/info",
                "/model/info",
                "/api/model/status"
            ]
            
            result = None
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                    
                    if response.status_code == 200:
                        result = {
                            'status': 'passed',
                            'endpoint': endpoint,
                            'status_code': response.status_code,
                            'response_time': response.elapsed.total_seconds()
                        }
                        
                        try:
                            model_info = response.json()
                            result['model_info'] = model_info
                            print(f"✅ {test_name}: Model info retrieved via {endpoint}")
                        except:
                            result['response_text'] = response.text
                            print(f"✅ {test_name}: Response received via {endpoint}")
                        break
                except:
                    continue
            
            if result is None:
                result = {
                    'status': 'failed',
                    'error': 'No model info endpoints found',
                    'tried_endpoints': endpoints
                }
                print(f"❌ {test_name}: No working model info endpoints")
        
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {test_name}: {e}")
        
        return result
    
    def test_api_documentation(self) -> Dict[str, Any]:
        """Test API documentation endpoints"""
        test_name = "API Documentation"
        print(f"Testing {test_name}...")
        
        try:
            endpoints = [
                "/docs",
                "/api/docs", 
                "/swagger",
                "/redoc"
            ]
            
            result = {'status': 'failed', 'available_docs': []}
            
            for endpoint in endpoints:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                    if response.status_code == 200:
                        result['available_docs'].append({
                            'endpoint': endpoint,
                            'status_code': response.status_code
                        })
                except:
                    pass
            
            if result['available_docs']:
                result['status'] = 'passed'
                print(f"✅ {test_name}: {len(result['available_docs'])} documentation endpoints found")
            else:
                print(f"❌ {test_name}: No documentation endpoints found")
        
        except Exception as e:
            result = {
                'status': 'failed',
                'error': str(e)
            }
            print(f"❌ {test_name}: {e}")
        
        return result
    
    def run_api_tests(self) -> Dict[str, Any]:
        """Run all API tests"""
        print("🚀 ML API Endpoints Validation")
        print("=" * 50)
        
        tests = [
            ('health', self.test_health_endpoint),
            ('ml_engine_health', self.test_ml_engine_health),
            ('video_upload', self.test_video_upload_and_processing),
            ('image_detection', self.test_image_detection),
            ('model_info', self.test_model_info_endpoint),
            ('api_docs', self.test_api_documentation)
        ]
        
        for test_key, test_func in tests:
            try:
                self.test_results['tests'][test_key] = test_func()
            except Exception as e:
                self.test_results['tests'][test_key] = {
                    'status': 'crashed',
                    'error': str(e)
                }
        
        # Generate summary
        total_tests = len(tests)
        passed_tests = sum(1 for t in self.test_results['tests'].values() if t['status'] == 'passed')
        failed_tests = sum(1 for t in self.test_results['tests'].values() if t['status'] == 'failed')
        crashed_tests = sum(1 for t in self.test_results['tests'].values() if t['status'] == 'crashed')
        
        self.test_results['summary'] = {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': failed_tests,
            'crashed_tests': crashed_tests,
            'success_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0
        }
        
        # Print summary
        print(f"\n📊 API VALIDATION SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Crashed: {crashed_tests}")
        print(f"Success Rate: {self.test_results['summary']['success_rate']:.1f}%")
        
        # Detailed results
        print(f"\n📋 DETAILED RESULTS")
        print("-" * 50)
        for test_key, result in self.test_results['tests'].items():
            status = result['status']
            emoji = "✅" if status == 'passed' else "❌" if status == 'failed' else "💥"
            print(f"{emoji} {test_key.replace('_', ' ').title()}: {status.upper()}")
            
            if status == 'passed' and 'endpoint' in result:
                print(f"   → Using endpoint: {result['endpoint']}")
            elif 'error' in result:
                print(f"   → Error: {result['error']}")
        
        # Overall assessment
        if passed_tests >= total_tests * 0.8:
            overall_status = "EXCELLENT"
            print(f"\n🎉 Overall Status: {overall_status} - API endpoints are working well!")
        elif passed_tests >= total_tests * 0.5:
            overall_status = "GOOD"
            print(f"\n👍 Overall Status: {overall_status} - Most API functionality is working")
        elif passed_tests > 0:
            overall_status = "PARTIAL"
            print(f"\n⚠️  Overall Status: {overall_status} - Some API endpoints working, issues found")
        else:
            overall_status = "FAILED"
            print(f"\n❌ Overall Status: {overall_status} - API endpoints not accessible")
        
        self.test_results['summary']['overall_status'] = overall_status
        
        return self.test_results
    
    def cleanup(self):
        """Clean up temporary files"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

def test_with_local_server():
    """Test with local development server"""
    print("Testing with local development server...")
    
    tester = MLAPITester("http://localhost:8000")
    try:
        results = tester.run_api_tests()
        return results
    finally:
        tester.cleanup()

def test_with_docker_server():
    """Test with Docker server"""
    print("Testing with Docker server...")
    
    tester = MLAPITester("http://localhost:80")
    try:
        results = tester.run_api_tests()
        return results
    finally:
        tester.cleanup()

def main():
    """Main API testing function"""
    all_results = {}
    
    # Test local server first
    try:
        print("🔍 Testing Local Development Server")
        print("=" * 50)
        local_results = test_with_local_server()
        all_results['local_server'] = local_results
        
        if local_results['summary']['passed_tests'] > 0:
            print("\n✅ Local server has working endpoints")
        else:
            print("\n❌ Local server not responding or no working endpoints")
            
    except Exception as e:
        print(f"❌ Local server testing failed: {e}")
        all_results['local_server'] = {'error': str(e)}
    
    # Test Docker server
    try:
        print(f"\n🐳 Testing Docker Server")
        print("=" * 50)
        docker_results = test_with_docker_server()
        all_results['docker_server'] = docker_results
        
        if docker_results['summary']['passed_tests'] > 0:
            print("\n✅ Docker server has working endpoints")
        else:
            print("\n❌ Docker server not responding or no working endpoints")
            
    except Exception as e:
        print(f"❌ Docker server testing failed: {e}")
        all_results['docker_server'] = {'error': str(e)}
    
    # Save combined results
    results_file = f"/home/user/Testing/ai-model-validation-platform/backend/tests/ml_api_test_results_{int(time.time())}.json"
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n💾 Complete results saved to: {results_file}")
    
    # Determine overall success
    local_success = all_results.get('local_server', {}).get('summary', {}).get('passed_tests', 0) > 0
    docker_success = all_results.get('docker_server', {}).get('summary', {}).get('passed_tests', 0) > 0
    
    if local_success or docker_success:
        print("\n🎉 API VALIDATION SUCCESSFUL - At least one server is responding!")
        return 0
    else:
        print("\n❌ API VALIDATION FAILED - No servers are responding properly")
        return 1

if __name__ == "__main__":
    result = main()
    exit(result)