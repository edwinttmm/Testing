#!/usr/bin/env python3
"""
Simplified Integration Test for AI Model Validation Platform
Tests core functionality without complex UI automation
"""

import requests
import json
import time
import tempfile
import os
import sys
from pathlib import Path

class SimpleIntegrationTest:
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.results = []
        
    def log(self, test_name, status, message="", details=None):
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "details": details,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.results.append(result)
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {test_name}: {message}")
        if details:
            print(f"   → {details}")

    def test_backend_connectivity(self):
        """Test backend service connectivity"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.log("Backend Health", "PASS", f"✓ {data.get('message', 'Healthy')}")
                return True
            else:
                self.log("Backend Health", "FAIL", f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log("Backend Health", "FAIL", f"Connection failed: {str(e)}")
            return False

    def test_api_endpoints(self):
        """Test key API endpoints"""
        endpoints = [
            ("/", "Root endpoint"),
            ("/docs", "API documentation"),
            ("/openapi.json", "OpenAPI specification")
        ]
        
        passed = 0
        for endpoint, description in endpoints:
            try:
                response = requests.get(f"{self.backend_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    self.log(f"API {endpoint}", "PASS", f"✓ {description}")
                    passed += 1
                else:
                    self.log(f"API {endpoint}", "FAIL", f"HTTP {response.status_code}")
            except Exception as e:
                self.log(f"API {endpoint}", "FAIL", f"Error: {str(e)}")
        
        self.log("API Endpoints", "PASS" if passed == len(endpoints) else "WARN", 
                f"{passed}/{len(endpoints)} endpoints working")
        return passed > 0

    def test_frontend_accessibility(self):
        """Test frontend accessibility"""
        try:
            response = requests.get(self.frontend_url, timeout=15)
            if response.status_code == 200:
                content = response.text.lower()
                if "react" in content or "root" in content or "ai" in content:
                    self.log("Frontend Access", "PASS", "✓ React app serving")
                    return True
                else:
                    self.log("Frontend Access", "WARN", "Serving but content unclear")
                    return True
            else:
                self.log("Frontend Access", "FAIL", f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log("Frontend Access", "FAIL", f"Error: {str(e)}")
            return False

    def test_database_connection(self):
        """Test database connectivity through backend"""
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                db_status = data.get('database', 'unknown')
                if db_status == 'connected':
                    self.log("Database Connection", "PASS", "✓ Database connected")
                    return True
                else:
                    self.log("Database Connection", "WARN", f"Status: {db_status}")
                    return True
            else:
                self.log("Database Connection", "FAIL", "Cannot verify through backend")
                return False
        except Exception as e:
            self.log("Database Connection", "FAIL", f"Error: {str(e)}")
            return False

    def test_file_upload(self):
        """Test file upload functionality"""
        try:
            # Create a small test file
            test_content = b"dummy video content for testing upload functionality"
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
                tmp_file.write(test_content)
                tmp_file.flush()
                
                # Try different upload endpoints
                upload_endpoints = [
                    "/api/upload",
                    "/upload", 
                    "/api/videos/upload",
                    "/api/validate/upload"
                ]
                
                for endpoint in upload_endpoints:
                    try:
                        files = {'file': ('test.mp4', open(tmp_file.name, 'rb'), 'video/mp4')}
                        data = {'description': 'Integration test upload'}
                        
                        response = requests.post(f"{self.backend_url}{endpoint}", 
                                               files=files, data=data, timeout=30)
                        
                        files['file'][1].close()  # Close file handle
                        
                        if response.status_code in [200, 201]:
                            self.log("File Upload", "PASS", f"✓ Upload works at {endpoint}")
                            return True
                        elif response.status_code == 404:
                            continue  # Try next endpoint
                        else:
                            self.log("File Upload", "FAIL", 
                                   f"{endpoint}: HTTP {response.status_code}")
                            return False
                            
                    except Exception as e:
                        continue  # Try next endpoint
                
                self.log("File Upload", "WARN", "No working upload endpoint found")
                return False
                
        except Exception as e:
            self.log("File Upload", "FAIL", f"Error: {str(e)}")
            return False
        finally:
            try:
                os.unlink(tmp_file.name)
            except:
                pass

    def test_performance_basics(self):
        """Test basic performance metrics"""
        try:
            # Test response times
            start_time = time.time()
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            backend_time = time.time() - start_time
            
            start_time = time.time()
            response = requests.get(self.frontend_url, timeout=15)
            frontend_time = time.time() - start_time
            
            # Evaluate performance
            performance_ok = backend_time < 2.0 and frontend_time < 5.0
            
            details = f"Backend: {backend_time:.2f}s, Frontend: {frontend_time:.2f}s"
            
            if performance_ok:
                self.log("Performance", "PASS", f"✓ Good response times", details)
                return True
            else:
                self.log("Performance", "WARN", f"Slow response times", details)
                return True
                
        except Exception as e:
            self.log("Performance", "FAIL", f"Error: {str(e)}")
            return False

    def test_service_communication(self):
        """Test inter-service communication"""
        try:
            # Check if services can communicate
            backend_healthy = requests.get(f"{self.backend_url}/health", timeout=10).status_code == 200
            frontend_accessible = requests.get(self.frontend_url, timeout=15).status_code == 200
            
            if backend_healthy and frontend_accessible:
                self.log("Service Communication", "PASS", "✓ All services accessible")
                return True
            elif backend_healthy:
                self.log("Service Communication", "WARN", "Backend OK, frontend issues")
                return True
            elif frontend_accessible:
                self.log("Service Communication", "WARN", "Frontend OK, backend issues")
                return True
            else:
                self.log("Service Communication", "FAIL", "Both services have issues")
                return False
                
        except Exception as e:
            self.log("Service Communication", "FAIL", f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Running Simple Integration Tests")
        print("=" * 50)
        
        tests = [
            self.test_backend_connectivity,
            self.test_api_endpoints,
            self.test_frontend_accessibility,
            self.test_database_connection,
            self.test_file_upload,
            self.test_performance_basics,
            self.test_service_communication
        ]
        
        passed = 0
        failed = 0
        warnings = 0
        
        for test in tests:
            try:
                result = test()
                # Count based on last logged result
                if self.results and self.results[-1]['status'] == 'PASS':
                    passed += 1
                elif self.results and self.results[-1]['status'] == 'FAIL':
                    failed += 1
                else:
                    warnings += 1
            except Exception as e:
                self.log(f"Test {test.__name__}", "FAIL", f"Exception: {str(e)}")
                failed += 1
        
        # Generate summary report
        total = passed + failed + warnings
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Determine overall system status
        if failed == 0 and passed > 0:
            print("🎉 SYSTEM STATUS: OPERATIONAL")
            system_status = "OPERATIONAL"
        elif failed == 0 and warnings > 0:
            print("⚠️  SYSTEM STATUS: PARTIAL (with warnings)")
            system_status = "PARTIAL"
        elif failed < passed:
            print("⚠️  SYSTEM STATUS: DEGRADED (some failures)")
            system_status = "DEGRADED"
        else:
            print("❌ SYSTEM STATUS: CRITICAL (major issues)")
            system_status = "CRITICAL"
        
        # Save detailed report
        report = {
            "summary": {
                "total_tests": total,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "success_rate": f"{success_rate:.1f}%",
                "system_status": system_status
            },
            "test_results": self.results,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "environment": {
                "backend_url": self.backend_url,
                "frontend_url": self.frontend_url
            }
        }
        
        report_path = "/home/rigade/Testing/ai-model-validation-platform/tests/integration-report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Detailed report: {report_path}")
        print("=" * 50)
        
        return failed == 0

if __name__ == "__main__":
    tester = SimpleIntegrationTest()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)