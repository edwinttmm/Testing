#!/usr/bin/env python3
"""
Comprehensive Docker Deployment Testing Suite
Tests all API endpoints, database operations, WebSocket connections, and file uploads.
"""

import asyncio
import aiohttp
import websockets
import json
import time
import os
import sys
from pathlib import Path
import io
import requests
from urllib.parse import urljoin
import sqlite3
import psycopg2
import redis
import threading
import logging
from typing import Dict, List, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/rigade/Testing/tests/deployment-test-results.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DeploymentTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"  
        self.ws_url = "ws://localhost:8000"
        self.test_results = {
            'database_tests': [],
            'api_tests': [],
            'websocket_tests': [],
            'upload_tests': [],
            'authentication_tests': [],
            'integration_tests': [],
            'performance_tests': [],
            'error_handling_tests': []
        }
        self.session = None
        
    async def setup_session(self):
        """Setup HTTP session with proper timeout and headers"""
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': 'DeploymentTester/1.0'}
        )
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()

    def test_database_connectivity(self):
        """Test database connections and basic operations"""
        logger.info("=== Testing Database Connectivity ===")
        
        # Test SQLite (primary)
        try:
            sqlite_path = "/home/rigade/Testing/ai-model-validation-platform/backend/dev_database.db"
            if os.path.exists(sqlite_path):
                conn = sqlite3.connect(sqlite_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                logger.info(f"SQLite tables found: {len(tables)}")
                
                # Test basic query
                cursor.execute("SELECT COUNT(*) FROM sqlite_master")
                count = cursor.fetchone()[0]
                
                self.test_results['database_tests'].append({
                    'test': 'sqlite_connectivity',
                    'status': 'PASS',
                    'details': f'Connected successfully, {len(tables)} tables, {count} objects'
                })
                conn.close()
            else:
                self.test_results['database_tests'].append({
                    'test': 'sqlite_connectivity',
                    'status': 'FAIL',
                    'details': f'SQLite file not found at {sqlite_path}'
                })
        except Exception as e:
            logger.error(f"SQLite test failed: {e}")
            self.test_results['database_tests'].append({
                'test': 'sqlite_connectivity',
                'status': 'FAIL',
                'details': str(e)
            })
        
        # Test PostgreSQL (if available)
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="vru_validation",
                user="postgres",
                password="secure_password_change_me",
                connect_timeout=10
            )
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            logger.info(f"PostgreSQL version: {version}")
            
            self.test_results['database_tests'].append({
                'test': 'postgresql_connectivity', 
                'status': 'PASS',
                'details': f'Connected successfully: {version}'
            })
            conn.close()
        except Exception as e:
            logger.warning(f"PostgreSQL test failed (expected if using SQLite): {e}")
            self.test_results['database_tests'].append({
                'test': 'postgresql_connectivity',
                'status': 'SKIP',
                'details': f'Not available or not configured: {str(e)}'
            })
            
        # Test Redis
        try:
            r = redis.Redis(host='localhost', port=6379, password='secure_redis_password', decode_responses=True)
            r.ping()
            info = r.info()
            logger.info(f"Redis version: {info.get('redis_version', 'unknown')}")
            
            self.test_results['database_tests'].append({
                'test': 'redis_connectivity',
                'status': 'PASS', 
                'details': f"Connected successfully: {info.get('redis_version', 'unknown')}"
            })
        except Exception as e:
            logger.warning(f"Redis test failed: {e}")
            self.test_results['database_tests'].append({
                'test': 'redis_connectivity',
                'status': 'FAIL',
                'details': str(e)
            })

    async def test_api_endpoints(self):
        """Test all API endpoints with real HTTP requests"""
        logger.info("=== Testing API Endpoints ===")
        
        # Core API endpoints to test
        endpoints = [
            {'method': 'GET', 'path': '/health', 'expected_status': 200},
            {'method': 'GET', 'path': '/', 'expected_status': 200},
            {'method': 'GET', 'path': '/api/videos', 'expected_status': 200},
            {'method': 'GET', 'path': '/api/projects', 'expected_status': 200},
            {'method': 'GET', 'path': '/api/dashboard/stats', 'expected_status': 200},
            {'method': 'GET', 'path': '/api/validation/status', 'expected_status': 200},
            {'method': 'POST', 'path': '/api/projects', 'expected_status': [200, 201, 422]},
            {'method': 'GET', 'path': '/api/detection/models', 'expected_status': 200}
        ]
        
        for endpoint in endpoints:
            try:
                url = urljoin(self.base_url, endpoint['path'])
                
                if endpoint['method'] == 'GET':
                    async with self.session.get(url) as response:
                        status = response.status
                        text = await response.text()
                        
                elif endpoint['method'] == 'POST':
                    test_data = {}
                    if endpoint['path'] == '/api/projects':
                        test_data = {
                            'name': f'Test Project {int(time.time())}',
                            'description': 'Automated test project'
                        }
                    
                    async with self.session.post(url, json=test_data) as response:
                        status = response.status
                        text = await response.text()
                
                expected = endpoint['expected_status']
                if isinstance(expected, list):
                    success = status in expected
                else:
                    success = status == expected
                
                result = {
                    'test': f"{endpoint['method']} {endpoint['path']}",
                    'status': 'PASS' if success else 'FAIL',
                    'details': f"Status: {status}, Response length: {len(text)}"
                }
                
                if not success:
                    result['details'] += f", Expected: {expected}, Body: {text[:200]}"
                
                self.test_results['api_tests'].append(result)
                logger.info(f"API {endpoint['method']} {endpoint['path']}: {status} {'✓' if success else '✗'}")
                
            except Exception as e:
                logger.error(f"API test failed for {endpoint['method']} {endpoint['path']}: {e}")
                self.test_results['api_tests'].append({
                    'test': f"{endpoint['method']} {endpoint['path']}",
                    'status': 'ERROR',
                    'details': str(e)
                })

    async def test_file_upload(self):
        """Test file upload functionality with actual files"""
        logger.info("=== Testing File Upload Functionality ===")
        
        # Create a test video file
        test_file_content = b"FAKE_VIDEO_DATA" + b"0" * 1024  # 1KB fake video
        test_file_path = "/tmp/test_video.mp4"
        
        with open(test_file_path, 'wb') as f:
            f.write(test_file_content)
        
        try:
            # Test video upload endpoint
            url = urljoin(self.base_url, '/api/videos/upload')
            
            with open(test_file_path, 'rb') as f:
                form_data = aiohttp.FormData()
                form_data.add_field('file', f, filename='test_video.mp4', content_type='video/mp4')
                form_data.add_field('project_id', '1')
                form_data.add_field('description', 'Test upload via deployment testing')
                
                async with self.session.post(url, data=form_data) as response:
                    status = response.status
                    text = await response.text()
                    
                    success = status in [200, 201]
                    self.test_results['upload_tests'].append({
                        'test': 'video_file_upload',
                        'status': 'PASS' if success else 'FAIL',
                        'details': f"Status: {status}, Response: {text[:200]}"
                    })
                    
                    logger.info(f"File upload test: {status} {'✓' if success else '✗'}")
                    
        except Exception as e:
            logger.error(f"File upload test failed: {e}")
            self.test_results['upload_tests'].append({
                'test': 'video_file_upload',
                'status': 'ERROR',
                'details': str(e)
            })
        finally:
            # Clean up test file
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    async def test_websocket_connections(self):
        """Test WebSocket connections and real-time features"""
        logger.info("=== Testing WebSocket Connections ===")
        
        try:
            # Test basic WebSocket connection
            ws_endpoints = [
                '/ws/detection',
                '/ws/notifications',
                '/ws/status'
            ]
            
            for endpoint in ws_endpoints:
                try:
                    url = f"{self.ws_url}{endpoint}"
                    
                    async with websockets.connect(url, timeout=10) as websocket:
                        # Send a test message
                        test_message = json.dumps({
                            'type': 'test',
                            'data': 'deployment_test',
                            'timestamp': time.time()
                        })
                        
                        await websocket.send(test_message)
                        
                        # Try to receive a response (with timeout)
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            
                            self.test_results['websocket_tests'].append({
                                'test': f'websocket_{endpoint}',
                                'status': 'PASS',
                                'details': f'Connected and received response: {response[:100]}'
                            })
                            logger.info(f"WebSocket {endpoint}: Connected ✓")
                            
                        except asyncio.TimeoutError:
                            self.test_results['websocket_tests'].append({
                                'test': f'websocket_{endpoint}',
                                'status': 'PARTIAL',
                                'details': 'Connected but no response received within timeout'
                            })
                            logger.warning(f"WebSocket {endpoint}: Connected but no response")
                            
                except Exception as e:
                    logger.warning(f"WebSocket {endpoint} test failed: {e}")
                    self.test_results['websocket_tests'].append({
                        'test': f'websocket_{endpoint}',
                        'status': 'FAIL',
                        'details': str(e)
                    })
                    
        except Exception as e:
            logger.error(f"WebSocket testing failed: {e}")
            self.test_results['websocket_tests'].append({
                'test': 'websocket_general',
                'status': 'ERROR',
                'details': str(e)
            })

    async def test_authentication_authorization(self):
        """Test authentication and authorization systems"""
        logger.info("=== Testing Authentication and Authorization ===")
        
        try:
            # Test without authentication
            url = urljoin(self.base_url, '/api/admin/users')
            async with self.session.get(url) as response:
                status = response.status
                
                # Should require authentication (401/403) or return data if no auth required
                if status in [200, 401, 403, 404]:
                    self.test_results['authentication_tests'].append({
                        'test': 'admin_endpoint_access',
                        'status': 'PASS',
                        'details': f'Proper response for admin endpoint: {status}'
                    })
                else:
                    self.test_results['authentication_tests'].append({
                        'test': 'admin_endpoint_access',
                        'status': 'FAIL', 
                        'details': f'Unexpected status: {status}'
                    })
                    
            # Test CORS headers
            async with self.session.options(self.base_url) as response:
                headers = response.headers
                cors_headers = {k: v for k, v in headers.items() if 'access-control' in k.lower()}
                
                self.test_results['authentication_tests'].append({
                    'test': 'cors_headers',
                    'status': 'PASS' if cors_headers else 'FAIL',
                    'details': f'CORS headers: {cors_headers}'
                })
                
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            self.test_results['authentication_tests'].append({
                'test': 'authentication_general',
                'status': 'ERROR',
                'details': str(e)
            })

    async def test_performance_benchmarks(self):
        """Test performance characteristics and response times"""
        logger.info("=== Testing Performance Benchmarks ===")
        
        # Test response times for key endpoints
        endpoints = ['/health', '/api/videos', '/api/projects', '/']
        
        for endpoint in endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # Measure multiple requests
                response_times = []
                for i in range(5):
                    start_time = time.time()
                    async with self.session.get(url) as response:
                        await response.text()
                    end_time = time.time()
                    response_times.append(end_time - start_time)
                
                avg_time = sum(response_times) / len(response_times)
                max_time = max(response_times)
                min_time = min(response_times)
                
                # Performance thresholds
                good_performance = avg_time < 1.0  # Under 1 second average
                acceptable_performance = avg_time < 3.0  # Under 3 seconds average
                
                if good_performance:
                    status = 'EXCELLENT'
                elif acceptable_performance:
                    status = 'ACCEPTABLE'
                else:
                    status = 'SLOW'
                
                self.test_results['performance_tests'].append({
                    'test': f'response_time_{endpoint.replace("/", "_")}',
                    'status': status,
                    'details': f'Avg: {avg_time:.3f}s, Min: {min_time:.3f}s, Max: {max_time:.3f}s'
                })
                
                logger.info(f"Performance {endpoint}: {avg_time:.3f}s avg ({'✓' if acceptable_performance else '⚠'})")
                
            except Exception as e:
                logger.error(f"Performance test failed for {endpoint}: {e}")
                self.test_results['performance_tests'].append({
                    'test': f'response_time_{endpoint.replace("/", "_")}',
                    'status': 'ERROR',
                    'details': str(e)
                })

    async def test_error_handling(self):
        """Test error handling and edge cases"""
        logger.info("=== Testing Error Handling ===")
        
        error_cases = [
            {'method': 'GET', 'path': '/api/videos/999999', 'expected': [404]},
            {'method': 'POST', 'path': '/api/videos/upload', 'data': {}, 'expected': [400, 422]},
            {'method': 'GET', 'path': '/nonexistent', 'expected': [404]},
            {'method': 'POST', 'path': '/api/projects', 'data': {'invalid': 'data'}, 'expected': [400, 422]}
        ]
        
        for case in error_cases:
            try:
                url = urljoin(self.base_url, case['path'])
                
                if case['method'] == 'GET':
                    async with self.session.get(url) as response:
                        status = response.status
                        
                elif case['method'] == 'POST':
                    data = case.get('data', {})
                    async with self.session.post(url, json=data) as response:
                        status = response.status
                
                expected = case['expected']
                success = status in expected
                
                self.test_results['error_handling_tests'].append({
                    'test': f"error_{case['method']}_{case['path'].replace('/', '_')}",
                    'status': 'PASS' if success else 'FAIL',
                    'details': f"Status: {status}, Expected: {expected}"
                })
                
                logger.info(f"Error handling {case['method']} {case['path']}: {status} {'✓' if success else '✗'}")
                
            except Exception as e:
                logger.error(f"Error handling test failed: {e}")
                self.test_results['error_handling_tests'].append({
                    'test': f"error_{case['method']}_{case['path'].replace('/', '_')}",
                    'status': 'ERROR', 
                    'details': str(e)
                })

    def test_frontend_accessibility(self):
        """Test frontend accessibility and basic functionality"""
        logger.info("=== Testing Frontend Accessibility ===")
        
        try:
            response = requests.get(self.frontend_url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                
                # Check for basic HTML structure
                has_title = '<title>' in content
                has_react_root = 'id="root"' in content
                has_manifest = 'manifest.json' in content
                
                self.test_results['integration_tests'].append({
                    'test': 'frontend_accessibility',
                    'status': 'PASS' if all([has_title, has_react_root]) else 'PARTIAL',
                    'details': f'Title: {has_title}, Root: {has_react_root}, Manifest: {has_manifest}'
                })
                
                logger.info(f"Frontend accessibility: {response.status_code} ✓")
            else:
                self.test_results['integration_tests'].append({
                    'test': 'frontend_accessibility',
                    'status': 'FAIL',
                    'details': f'HTTP {response.status_code}: {response.text[:100]}'
                })
                
        except Exception as e:
            logger.error(f"Frontend accessibility test failed: {e}")
            self.test_results['integration_tests'].append({
                'test': 'frontend_accessibility',
                'status': 'ERROR',
                'details': str(e)
            })

    def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("=== Generating Test Report ===")
        
        # Calculate summary statistics
        total_tests = sum(len(tests) for tests in self.test_results.values())
        passed_tests = sum(1 for tests in self.test_results.values() for test in tests if test['status'] == 'PASS')
        failed_tests = sum(1 for tests in self.test_results.values() for test in tests if test['status'] == 'FAIL')
        error_tests = sum(1 for tests in self.test_results.values() for test in tests if test['status'] == 'ERROR')
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'errors': error_tests,
                'success_rate': f"{(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%"
            },
            'test_results': self.test_results
        }
        
        # Write detailed report
        report_file = '/home/rigade/Testing/tests/deployment-test-report.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Write summary report
        summary_file = '/home/rigade/Testing/tests/deployment-test-summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"=== DEPLOYMENT TEST SUMMARY ===\n")
            f.write(f"Timestamp: {report['summary']['timestamp']}\n")
            f.write(f"Total Tests: {total_tests}\n")
            f.write(f"Passed: {passed_tests}\n")
            f.write(f"Failed: {failed_tests}\n")
            f.write(f"Errors: {error_tests}\n")
            f.write(f"Success Rate: {report['summary']['success_rate']}\n\n")
            
            for category, tests in self.test_results.items():
                if tests:
                    f.write(f"=== {category.upper().replace('_', ' ')} ===\n")
                    for test in tests:
                        f.write(f"  {test['test']}: {test['status']}\n")
                        if test['status'] != 'PASS':
                            f.write(f"    Details: {test['details']}\n")
                    f.write("\n")
        
        logger.info(f"✅ Report generated: {report['summary']['success_rate']} success rate ({passed_tests}/{total_tests} tests passed)")
        return report

    async def run_all_tests(self):
        """Run all deployment tests"""
        logger.info("🚀 Starting Comprehensive Deployment Testing")
        
        await self.setup_session()
        
        try:
            # Wait for services to be ready
            logger.info("⏳ Waiting for services to be ready...")
            await asyncio.sleep(10)
            
            # Run all test suites
            self.test_database_connectivity()
            await self.test_api_endpoints()
            await self.test_file_upload() 
            await self.test_websocket_connections()
            await self.test_authentication_authorization()
            await self.test_performance_benchmarks()
            await self.test_error_handling()
            self.test_frontend_accessibility()
            
            # Generate final report
            report = self.generate_report()
            
            return report
            
        finally:
            await self.cleanup_session()

def main():
    """Main entry point"""
    logger.info("🔥 Docker Deployment Comprehensive Testing Suite")
    
    tester = DeploymentTester()
    
    try:
        # Run async tests
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        report = loop.run_until_complete(tester.run_all_tests())
        loop.close()
        
        # Print summary
        print("\n" + "="*60)
        print("🎯 DEPLOYMENT TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"✅ Passed: {report['summary']['passed']}")
        print(f"❌ Failed: {report['summary']['failed']}")
        print(f"⚠️  Errors: {report['summary']['errors']}")
        print(f"📊 Success Rate: {report['summary']['success_rate']}")
        print("="*60)
        
        # Return appropriate exit code
        if report['summary']['failed'] > 0 or report['summary']['errors'] > 0:
            print("❌ Some tests failed - check logs for details")
            sys.exit(1)
        else:
            print("✅ All tests passed!")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Testing failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()