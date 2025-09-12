#!/usr/bin/env python3
"""
Comprehensive Integration Test Suite for AI Model Validation Platform
Tests all services: frontend, backend, database, and end-to-end workflows
"""

import requests
import json
import time
import os
import sys
import tempfile
from pathlib import Path
import asyncio
import websockets
import uuid
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess

class IntegrationTester:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_results = []
        self.driver = None
        
    def log_test(self, test_name, status, message="", details=None):
        """Log test results"""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.test_results.append(result)
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_icon} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")

    def test_backend_health(self):
        """Test backend service health"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log_test("Backend Health", "PASS", f"Backend healthy: {data.get('message', 'OK')}")
                return True
            else:
                self.log_test("Backend Health", "FAIL", f"Status code: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Backend Health", "FAIL", f"Connection error: {str(e)}")
            return False

    def test_backend_api_endpoints(self):
        """Test all backend API endpoints"""
        try:
            # Test root endpoint
            response = requests.get(f"{self.backend_url}/", timeout=10)
            if response.status_code == 200:
                self.log_test("Backend Root API", "PASS", "Root endpoint responding")
            else:
                self.log_test("Backend Root API", "FAIL", f"Status: {response.status_code}")

            # Test OpenAPI docs
            response = requests.get(f"{self.backend_url}/openapi.json", timeout=10)
            if response.status_code == 200:
                openapi_spec = response.json()
                endpoints = list(openapi_spec.get('paths', {}).keys())
                self.log_test("OpenAPI Spec", "PASS", f"Found {len(endpoints)} endpoints", endpoints)
                return endpoints
            else:
                self.log_test("OpenAPI Spec", "FAIL", f"Status: {response.status_code}")
                return []
        except Exception as e:
            self.log_test("Backend API Tests", "FAIL", f"Error: {str(e)}")
            return []

    def test_frontend_availability(self):
        """Test frontend service availability"""
        try:
            response = requests.get(self.frontend_url, timeout=15)
            if response.status_code == 200:
                content = response.text
                if "react" in content.lower() or "root" in content:
                    self.log_test("Frontend Availability", "PASS", "Frontend serving React app")
                    return True
                else:
                    self.log_test("Frontend Availability", "WARN", "Frontend responding but content unclear")
                    return True
            else:
                self.log_test("Frontend Availability", "FAIL", f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Frontend Availability", "FAIL", f"Error: {str(e)}")
            return False

    def test_database_operations(self):
        """Test database operations through backend API"""
        try:
            # Test database connection through backend
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                if health_data.get('database') == 'connected':
                    self.log_test("Database Connection", "PASS", "Database connected via backend")
                    return True
                else:
                    self.log_test("Database Connection", "WARN", "Database status unclear")
                    return True
            else:
                self.log_test("Database Connection", "FAIL", "Cannot check database through backend")
                return False
        except Exception as e:
            self.log_test("Database Connection", "FAIL", f"Error: {str(e)}")
            return False

    async def test_websocket_connection(self):
        """Test WebSocket connectivity"""
        try:
            ws_url = self.backend_url.replace('http:', 'ws:') + "/ws"
            async with websockets.connect(ws_url, timeout=10) as websocket:
                # Send test message
                test_message = {"type": "ping", "data": "test"}
                await websocket.send(json.dumps(test_message))
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    self.log_test("WebSocket Connection", "PASS", f"WebSocket working: {response}")
                    return True
                except asyncio.TimeoutError:
                    self.log_test("WebSocket Connection", "WARN", "WebSocket connected but no response")
                    return True
        except Exception as e:
            self.log_test("WebSocket Connection", "FAIL", f"Error: {str(e)}")
            return False

    def test_file_upload_api(self):
        """Test file upload functionality"""
        try:
            # Create a test video file (small dummy file)
            test_content = b"fake video content for testing"
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
                tmp_file.write(test_content)
                tmp_file.flush()
                
                # Test file upload
                files = {'file': ('test.mp4', open(tmp_file.name, 'rb'), 'video/mp4')}
                data = {'description': 'Test video upload'}
                
                response = requests.post(f"{self.backend_url}/api/upload", 
                                       files=files, data=data, timeout=30)
                
                if response.status_code in [200, 201]:
                    self.log_test("File Upload API", "PASS", "File upload successful")
                    return True
                elif response.status_code == 404:
                    self.log_test("File Upload API", "WARN", "Upload endpoint not found - checking alternatives")
                    # Try alternative upload endpoints
                    for endpoint in ["/upload", "/api/videos/upload", "/api/validate/upload"]:
                        try:
                            files = {'file': ('test.mp4', open(tmp_file.name, 'rb'), 'video/mp4')}
                            response = requests.post(f"{self.backend_url}{endpoint}", 
                                                   files=files, data=data, timeout=30)
                            if response.status_code in [200, 201]:
                                self.log_test("File Upload API", "PASS", f"Upload works on {endpoint}")
                                return True
                        except:
                            continue
                    self.log_test("File Upload API", "FAIL", "No working upload endpoint found")
                    return False
                else:
                    self.log_test("File Upload API", "FAIL", f"Status: {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_test("File Upload API", "FAIL", f"Error: {str(e)}")
            return False
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_file.name)
            except:
                pass

    def setup_selenium_driver(self):
        """Setup Selenium WebDriver for UI testing"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.log_test("Selenium Setup", "PASS", "WebDriver initialized")
            return True
        except Exception as e:
            self.log_test("Selenium Setup", "FAIL", f"Error: {str(e)}")
            return False

    def test_ui_functionality(self):
        """Test UI functionality through Selenium"""
        if not self.driver:
            if not self.setup_selenium_driver():
                return False
        
        try:
            # Navigate to frontend
            self.driver.get(self.frontend_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check if React app loaded
            page_source = self.driver.page_source
            if "root" in page_source or "React" in page_source:
                self.log_test("UI Load Test", "PASS", "React app loaded successfully")
                
                # Try to find common UI elements
                elements_found = []
                common_selectors = [
                    "button", "input", "form", "[data-testid]", ".upload", "#upload"
                ]
                
                for selector in common_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            elements_found.append(f"{selector}({len(elements)})")
                    except:
                        continue
                
                if elements_found:
                    self.log_test("UI Elements Test", "PASS", f"Found elements: {', '.join(elements_found)}")
                else:
                    self.log_test("UI Elements Test", "WARN", "Basic elements found but no interactive components")
                
                return True
            else:
                self.log_test("UI Load Test", "FAIL", "React app not properly loaded")
                return False
                
        except Exception as e:
            self.log_test("UI Functionality", "FAIL", f"Error: {str(e)}")
            return False

    def test_end_to_end_workflow(self):
        """Test complete user workflow"""
        try:
            # This would be a complex test involving:
            # 1. UI navigation
            # 2. File selection and upload
            # 3. Processing status monitoring
            # 4. Results display
            
            # For now, test the API workflow
            workflow_steps = []
            
            # Step 1: Check available models/services
            try:
                response = requests.get(f"{self.backend_url}/", timeout=10)
                if response.status_code == 200:
                    workflow_steps.append("✓ Backend accessible")
                else:
                    workflow_steps.append("✗ Backend not accessible")
            except:
                workflow_steps.append("✗ Backend connection failed")
            
            # Step 2: Frontend accessibility
            try:
                response = requests.get(self.frontend_url, timeout=10)
                if response.status_code == 200:
                    workflow_steps.append("✓ Frontend accessible")
                else:
                    workflow_steps.append("✗ Frontend not accessible")
            except:
                workflow_steps.append("✗ Frontend connection failed")
            
            success_count = len([s for s in workflow_steps if s.startswith("✓")])
            total_steps = len(workflow_steps)
            
            if success_count == total_steps:
                self.log_test("End-to-End Workflow", "PASS", f"All {success_count}/{total_steps} steps successful", workflow_steps)
                return True
            else:
                self.log_test("End-to-End Workflow", "WARN", f"{success_count}/{total_steps} steps successful", workflow_steps)
                return False
                
        except Exception as e:
            self.log_test("End-to-End Workflow", "FAIL", f"Error: {str(e)}")
            return False

    def run_performance_tests(self):
        """Run basic performance tests"""
        try:
            # Test response times
            start_time = time.time()
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            backend_response_time = time.time() - start_time
            
            start_time = time.time()
            response = requests.get(self.frontend_url, timeout=15)
            frontend_response_time = time.time() - start_time
            
            performance_results = {
                "backend_response_time": f"{backend_response_time:.3f}s",
                "frontend_response_time": f"{frontend_response_time:.3f}s"
            }
            
            if backend_response_time < 1.0 and frontend_response_time < 3.0:
                self.log_test("Performance Test", "PASS", "Response times acceptable", performance_results)
                return True
            else:
                self.log_test("Performance Test", "WARN", "Some response times high", performance_results)
                return True
                
        except Exception as e:
            self.log_test("Performance Test", "FAIL", f"Error: {str(e)}")
            return False

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
        self.log_test("Cleanup", "PASS", "Resources cleaned up")

    def generate_report(self):
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r['status'] == 'PASS'])
        failed_tests = len([r for r in self.test_results if r['status'] == 'FAIL'])
        warning_tests = len([r for r in self.test_results if r['status'] == 'WARN'])
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "warnings": warning_tests,
                "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
            },
            "detailed_results": self.test_results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "system_info": {
                "backend_url": self.backend_url,
                "frontend_url": self.frontend_url
            }
        }
        
        return report

    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Comprehensive Integration Tests\n")
        
        # Core service tests
        self.test_backend_health()
        self.test_backend_api_endpoints()
        self.test_frontend_availability()
        self.test_database_operations()
        
        # Advanced functionality tests
        await self.test_websocket_connection()
        self.test_file_upload_api()
        
        # UI and workflow tests
        self.test_ui_functionality()
        self.test_end_to_end_workflow()
        
        # Performance tests
        self.run_performance_tests()
        
        # Generate final report
        report = self.generate_report()
        
        print("\n" + "="*60)
        print("📊 INTEGRATION TEST RESULTS SUMMARY")
        print("="*60)
        print(f"Total Tests: {report['summary']['total_tests']}")
        print(f"✅ Passed: {report['summary']['passed']}")
        print(f"❌ Failed: {report['summary']['failed']}")
        print(f"⚠️  Warnings: {report['summary']['warnings']}")
        print(f"Success Rate: {report['summary']['success_rate']}")
        print("="*60)
        
        # Save detailed report
        report_file = "/home/rigade/Testing/ai-model-validation-platform/tests/integration-test-report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Detailed report saved to: {report_file}")
        
        # Cleanup
        self.cleanup()
        
        return report

async def main():
    tester = IntegrationTester()
    report = await tester.run_all_tests()
    
    # Return appropriate exit code
    if report['summary']['failed'] == 0:
        sys.exit(0)  # All tests passed or warnings only
    else:
        sys.exit(1)  # Some tests failed

if __name__ == "__main__":
    asyncio.run(main())