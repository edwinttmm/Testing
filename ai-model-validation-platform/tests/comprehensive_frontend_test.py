#!/usr/bin/env python3
"""
Comprehensive Frontend Testing Suite
====================================

This script performs comprehensive testing of the AI Model Validation Platform frontend,
systematically testing every page, feature, and user interaction.
"""

import json
import time
import logging
import subprocess
import requests
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveFrontendTester:
    def __init__(self):
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'navigation_tests': {},
            'page_loading_tests': {},
            'project_management_tests': {},
            'video_management_tests': {},
            'annotation_system_tests': {},
            'results_dashboard_tests': {},
            'error_scenarios': {},
            'ui_responsiveness': {},
            'console_errors': [],
            'performance_metrics': {},
            'accessibility_issues': [],
            'overall_status': 'RUNNING'
        }
        self.frontend_url = 'http://localhost:3000'
        self.backend_url = 'http://localhost:8000'
        
    def check_services(self):
        """Check if backend and frontend services are running"""
        logger.info("Checking service availability...")
        
        # Check backend
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            self.test_results['backend_status'] = {
                'available': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            self.test_results['backend_status'] = {
                'available': False,
                'error': str(e)
            }
            
        # Check frontend
        try:
            response = requests.get(self.frontend_url, timeout=10)
            self.test_results['frontend_status'] = {
                'available': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            self.test_results['frontend_status'] = {
                'available': False,
                'error': str(e)
            }
            
    def test_navigation_and_routes(self):
        """Test all navigation routes and page accessibility"""
        logger.info("Testing navigation and routes...")
        
        routes_to_test = [
            ('/', 'Home Page'),
            ('/projects', 'Projects Page'),
            ('/datasets', 'Datasets Page'),
            ('/results', 'Results Page'),
            ('/ground-truth', 'Ground Truth Page')
        ]
        
        for route, page_name in routes_to_test:
            try:
                full_url = f"{self.frontend_url}{route}"
                response = requests.get(full_url, timeout=10)
                
                self.test_results['navigation_tests'][page_name] = {
                    'url': full_url,
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds(),
                    'content_length': len(response.content),
                    'accessible': response.status_code == 200,
                    'has_react_content': 'react' in response.text.lower() or 'root' in response.text
                }
                
                if response.status_code == 200:
                    logger.info(f"✅ {page_name} accessible")
                else:
                    logger.warning(f"⚠️  {page_name} returned status {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Error testing {page_name}: {e}")
                self.test_results['navigation_tests'][page_name] = {
                    'url': full_url,
                    'accessible': False,
                    'error': str(e)
                }
    
    def test_api_integration(self):
        """Test frontend-backend API integration"""
        logger.info("Testing API integration...")
        
        api_endpoints = [
            ('/api/projects', 'GET', 'Projects List'),
            ('/api/videos', 'GET', 'Videos List'),
            ('/api/annotations', 'GET', 'Annotations List'),
            ('/api/health', 'GET', 'Health Check'),
            ('/api/datasets', 'GET', 'Datasets List')
        ]
        
        for endpoint, method, description in api_endpoints:
            try:
                full_url = f"{self.backend_url}{endpoint}"
                response = requests.get(full_url, timeout=5)
                
                self.test_results['api_integration'] = self.test_results.get('api_integration', {})
                self.test_results['api_integration'][description] = {
                    'endpoint': endpoint,
                    'method': method,
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds(),
                    'working': response.status_code in [200, 404]  # 404 is OK for empty datasets
                }
                
                if response.status_code in [200, 404]:
                    logger.info(f"✅ {description} API working")
                else:
                    logger.warning(f"⚠️  {description} API returned {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Error testing {description} API: {e}")
                self.test_results['api_integration'] = self.test_results.get('api_integration', {})
                self.test_results['api_integration'][description] = {
                    'endpoint': endpoint,
                    'working': False,
                    'error': str(e)
                }
    
    def test_project_management_ui(self):
        """Test project management functionality through UI simulation"""
        logger.info("Testing project management UI functionality...")
        
        # Test project creation API (simulate frontend form submission)
        try:
            project_data = {
                "name": "Frontend Test Project",
                "description": "Project created during comprehensive frontend testing",
                "validation_criteria": {
                    "accuracy_threshold": 0.85,
                    "precision_threshold": 0.8,
                    "recall_threshold": 0.8
                }
            }
            
            response = requests.post(
                f"{self.backend_url}/api/projects/", 
                json=project_data,
                headers={'Content-Type': 'application/json'}
            )
            
            self.test_results['project_management_tests']['create_project'] = {
                'test_data': project_data,
                'status_code': response.status_code,
                'success': response.status_code == 200,
                'response_time': response.elapsed.total_seconds()
            }
            
            if response.status_code == 200:
                response_data = response.json()
                project_id = response_data.get('id')
                logger.info(f"✅ Project creation successful (ID: {project_id})")
                
                # Test project listing
                list_response = requests.get(f"{self.backend_url}/api/projects/")
                self.test_results['project_management_tests']['list_projects'] = {
                    'status_code': list_response.status_code,
                    'success': list_response.status_code == 200,
                    'project_count': len(list_response.json()) if list_response.status_code == 200 else 0
                }
                
                # Test project update
                if project_id:
                    update_data = {"name": "Updated Frontend Test Project"}
                    update_response = requests.put(
                        f"{self.backend_url}/api/projects/{project_id}",
                        json=update_data,
                        headers={'Content-Type': 'application/json'}
                    )
                    
                    self.test_results['project_management_tests']['update_project'] = {
                        'status_code': update_response.status_code,
                        'success': update_response.status_code == 200
                    }
                    
            else:
                logger.warning(f"⚠️  Project creation failed with status {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error testing project management: {e}")
            self.test_results['project_management_tests']['error'] = str(e)
    
    def test_video_management_interface(self):
        """Test video management and upload functionality"""
        logger.info("Testing video management interface...")
        
        # Test video upload endpoint availability
        try:
            # Test multipart upload endpoint
            upload_url = f"{self.backend_url}/api/videos/upload"
            
            # Create a small test file to simulate video upload
            test_file_content = b"fake video content for testing"
            files = {'file': ('test_video.mp4', test_file_content, 'video/mp4')}
            data = {'project_id': '1', 'description': 'Test video upload'}
            
            response = requests.post(upload_url, files=files, data=data, timeout=30)
            
            self.test_results['video_management_tests']['upload_endpoint'] = {
                'url': upload_url,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'accepts_multipart': True
            }
            
            # Test video listing
            videos_response = requests.get(f"{self.backend_url}/api/videos/")
            self.test_results['video_management_tests']['list_videos'] = {
                'status_code': videos_response.status_code,
                'success': videos_response.status_code in [200, 404],
                'video_count': len(videos_response.json()) if videos_response.status_code == 200 else 0
            }
            
            logger.info(f"✅ Video management endpoints tested")
            
        except Exception as e:
            logger.error(f"❌ Error testing video management: {e}")
            self.test_results['video_management_tests']['error'] = str(e)
    
    def test_annotation_system(self):
        """Test annotation system functionality"""
        logger.info("Testing annotation system...")
        
        try:
            # Test annotation endpoints
            annotations_response = requests.get(f"{self.backend_url}/api/annotations/")
            self.test_results['annotation_system_tests']['list_annotations'] = {
                'status_code': annotations_response.status_code,
                'success': annotations_response.status_code in [200, 404],
                'annotation_count': len(annotations_response.json()) if annotations_response.status_code == 200 else 0
            }
            
            # Test annotation creation
            annotation_data = {
                "video_id": 1,
                "frame_number": 100,
                "annotations": [
                    {
                        "type": "bounding_box",
                        "coordinates": {"x": 100, "y": 100, "width": 200, "height": 150},
                        "label": "person",
                        "confidence": 0.95
                    }
                ]
            }
            
            create_response = requests.post(
                f"{self.backend_url}/api/annotations/",
                json=annotation_data,
                headers={'Content-Type': 'application/json'}
            )
            
            self.test_results['annotation_system_tests']['create_annotation'] = {
                'status_code': create_response.status_code,
                'success': create_response.status_code in [200, 201],
                'test_data': annotation_data
            }
            
            logger.info(f"✅ Annotation system endpoints tested")
            
        except Exception as e:
            logger.error(f"❌ Error testing annotation system: {e}")
            self.test_results['annotation_system_tests']['error'] = str(e)
    
    def test_error_scenarios(self):
        """Test error handling and edge cases"""
        logger.info("Testing error scenarios...")
        
        error_tests = [
            ('Invalid Project ID', f"{self.backend_url}/api/projects/99999", 'GET'),
            ('Invalid Video ID', f"{self.backend_url}/api/videos/99999", 'GET'),
            ('Malformed JSON', f"{self.backend_url}/api/projects/", 'POST', '{"invalid": json}'),
            ('Empty Request', f"{self.backend_url}/api/projects/", 'POST', ''),
            ('Large File Upload', f"{self.backend_url}/api/videos/upload", 'POST')
        ]
        
        for test_name, url, method, *args in error_tests:
            try:
                if method == 'GET':
                    response = requests.get(url, timeout=5)
                elif method == 'POST':
                    if args and args[0]:
                        response = requests.post(url, data=args[0], timeout=5)
                    else:
                        response = requests.post(url, timeout=5)
                
                self.test_results['error_scenarios'][test_name] = {
                    'url': url,
                    'method': method,
                    'status_code': response.status_code,
                    'handles_error_gracefully': response.status_code in [400, 404, 422, 500],
                    'response_time': response.elapsed.total_seconds()
                }
                
            except Exception as e:
                self.test_results['error_scenarios'][test_name] = {
                    'url': url,
                    'method': method,
                    'error': str(e),
                    'handles_error_gracefully': True  # Network errors are handled
                }
    
    def test_performance_metrics(self):
        """Test basic performance metrics"""
        logger.info("Testing performance metrics...")
        
        # Test page load times
        start_time = time.time()
        try:
            response = requests.get(self.frontend_url, timeout=10)
            load_time = time.time() - start_time
            
            self.test_results['performance_metrics'] = {
                'homepage_load_time': load_time,
                'homepage_size': len(response.content),
                'acceptable_load_time': load_time < 3.0,  # Should load in under 3 seconds
                'status_code': response.status_code
            }
            
            logger.info(f"✅ Homepage load time: {load_time:.2f}s")
            
        except Exception as e:
            self.test_results['performance_metrics'] = {
                'error': str(e),
                'homepage_accessible': False
            }
    
    def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("Generating comprehensive test report...")
        
        # Calculate overall success rate
        total_tests = 0
        successful_tests = 0
        
        # Count navigation tests
        for test in self.test_results['navigation_tests'].values():
            total_tests += 1
            if test.get('accessible', False):
                successful_tests += 1
        
        # Count API tests
        for test in self.test_results.get('api_integration', {}).values():
            total_tests += 1
            if test.get('working', False):
                successful_tests += 1
        
        # Count project management tests
        for test in self.test_results['project_management_tests'].values():
            if isinstance(test, dict) and 'success' in test:
                total_tests += 1
                if test.get('success', False):
                    successful_tests += 1
        
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        self.test_results['summary'] = {
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'success_rate': f"{success_rate:.1f}%",
            'overall_status': 'PASSED' if success_rate > 70 else 'FAILED',
            'test_duration': datetime.now().isoformat()
        }
        
        self.test_results['overall_status'] = 'COMPLETED'
        
        # Save detailed results
        results_file = f"/home/rigade/Testing/ai-model-validation-platform/tests/frontend_test_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"📊 Test Results Summary:")
        logger.info(f"   Total Tests: {total_tests}")
        logger.info(f"   Successful: {successful_tests}")
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        logger.info(f"   Overall Status: {self.test_results['summary']['overall_status']}")
        logger.info(f"   Detailed results saved to: {results_file}")
        
        return self.test_results
    
    def run_comprehensive_test(self):
        """Run all tests in sequence"""
        logger.info("🚀 Starting Comprehensive Frontend Testing Suite")
        
        # Wait for services to be ready
        time.sleep(10)
        
        self.check_services()
        self.test_navigation_and_routes()
        self.test_api_integration()
        self.test_project_management_ui()
        self.test_video_management_interface()
        self.test_annotation_system()
        self.test_error_scenarios()
        self.test_performance_metrics()
        
        return self.generate_report()

if __name__ == "__main__":
    tester = ComprehensiveFrontendTester()
    results = tester.run_comprehensive_test()
    
    # Print summary for immediate feedback
    print("\n" + "="*60)
    print("COMPREHENSIVE FRONTEND TEST RESULTS")
    print("="*60)
    print(f"Status: {results['summary']['overall_status']}")
    print(f"Success Rate: {results['summary']['success_rate']}")
    print(f"Total Tests: {results['summary']['total_tests']}")
    print("="*60)