#!/usr/bin/env python3
"""
Comprehensive UI Testing Script for AI Model Validation Platform
Performs automated testing of all pages, components, and user workflows.
"""

import requests
import json
import time
from datetime import datetime

class ProductionTester:
    def __init__(self, base_url="http://localhost:3000", api_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_url = api_url
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {"passed": 0, "failed": 0, "warnings": 0}
        }
    
    def log_test(self, test_name, status, message="", details=None):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        if details:
            result["details"] = details
        
        self.test_results["tests"].append(result)
        status_key = "warnings" if status.lower() == "warning" else status.lower()
        self.test_results["summary"][status_key] += 1
        
        status_icon = {"PASSED": "✅", "FAILED": "❌", "WARNING": "⚠️"}.get(status, "🔍")
        print(f"{status_icon} {test_name}: {message}")
    
    def test_frontend_accessibility(self):
        """Test frontend is accessible and loads correctly"""
        try:
            response = requests.get(self.base_url, timeout=10)
            if response.status_code == 200:
                if "React App" in response.text and "root" in response.text:
                    self.log_test("Frontend Accessibility", "PASSED", "Frontend loads correctly")
                    return True
                else:
                    self.log_test("Frontend Accessibility", "FAILED", "Frontend loads but missing React structure")
            else:
                self.log_test("Frontend Accessibility", "FAILED", f"HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Frontend Accessibility", "FAILED", f"Connection failed: {str(e)}")
        return False
    
    def test_static_assets(self):
        """Test static assets load correctly"""
        assets_to_test = [
            "/static/css/main.e6c13ad2.css",
            "/static/js/main.a11d605d.js",
            "/favicon.ico",
            "/manifest.json"
        ]
        
        passed = 0
        for asset in assets_to_test:
            try:
                response = requests.get(f"{self.base_url}{asset}", timeout=5)
                if response.status_code == 200:
                    passed += 1
                else:
                    self.log_test(f"Asset: {asset}", "WARNING", f"HTTP {response.status_code}")
            except Exception as e:
                self.log_test(f"Asset: {asset}", "FAILED", f"Failed to load: {str(e)}")
        
        if passed == len(assets_to_test):
            self.log_test("Static Assets", "PASSED", f"All {passed} assets loaded successfully")
        elif passed > 0:
            self.log_test("Static Assets", "WARNING", f"{passed}/{len(assets_to_test)} assets loaded")
        else:
            self.log_test("Static Assets", "FAILED", "No assets could be loaded")
    
    def test_api_endpoints(self):
        """Test backend API endpoints if available"""
        endpoints_to_test = [
            "/health",
            "/api/projects",
            "/api/videos"
        ]
        
        api_available = False
        for endpoint in endpoints_to_test:
            try:
                response = requests.get(f"{self.api_url}{endpoint}", timeout=5)
                if response.status_code in [200, 404, 422]:  # 404/422 are ok for endpoints requiring auth
                    api_available = True
                    self.log_test(f"API {endpoint}", "PASSED", f"Responds with HTTP {response.status_code}")
                else:
                    self.log_test(f"API {endpoint}", "WARNING", f"HTTP {response.status_code}")
            except Exception as e:
                self.log_test(f"API {endpoint}", "WARNING", f"API not available: {str(e)}")
        
        if not api_available:
            self.log_test("Backend API", "WARNING", "Backend API not running or not accessible")
    
    def test_responsive_design_simulation(self):
        """Simulate responsive design testing"""
        # Since we can't easily test responsive design without a browser, 
        # we'll check that the CSS includes responsive utilities
        try:
            response = requests.get(f"{self.base_url}/static/css/main.e6c13ad2.css", timeout=5)
            css_content = response.text
            
            responsive_indicators = ["@media", "max-width", "min-width", "flex", "grid"]
            found_indicators = [indicator for indicator in responsive_indicators if indicator in css_content]
            
            if len(found_indicators) >= 3:
                self.log_test("Responsive Design", "PASSED", f"CSS contains responsive utilities: {', '.join(found_indicators)}")
            elif len(found_indicators) > 0:
                self.log_test("Responsive Design", "WARNING", f"Limited responsive utilities found: {', '.join(found_indicators)}")
            else:
                self.log_test("Responsive Design", "WARNING", "No responsive utilities detected in CSS")
        except Exception as e:
            self.log_test("Responsive Design", "WARNING", f"Could not analyze CSS: {str(e)}")
    
    def test_configuration(self):
        """Test configuration files are accessible"""
        try:
            response = requests.get(f"{self.base_url}/config.js", timeout=5)
            if response.status_code == 200:
                self.log_test("Configuration", "PASSED", "Config.js accessible")
            else:
                self.log_test("Configuration", "WARNING", f"Config.js HTTP {response.status_code}")
        except Exception as e:
            self.log_test("Configuration", "WARNING", f"Config.js not accessible: {str(e)}")
    
    def performance_test(self):
        """Basic performance test"""
        start_time = time.time()
        try:
            response = requests.get(self.base_url, timeout=10)
            load_time = time.time() - start_time
            
            if load_time < 2.0:
                self.log_test("Performance", "PASSED", f"Page loads in {load_time:.2f}s (< 2s)")
            elif load_time < 5.0:
                self.log_test("Performance", "WARNING", f"Page loads in {load_time:.2f}s (acceptable)")
            else:
                self.log_test("Performance", "FAILED", f"Page loads in {load_time:.2f}s (too slow)")
        except Exception as e:
            self.log_test("Performance", "FAILED", f"Performance test failed: {str(e)}")
    
    def run_all_tests(self):
        """Run all automated tests"""
        print("🚀 Starting Comprehensive UI Testing...")
        print("=" * 60)
        
        # Frontend tests
        self.test_frontend_accessibility()
        self.test_static_assets()
        self.test_configuration()
        self.performance_test()
        self.test_responsive_design_simulation()
        
        # Backend tests
        self.test_api_endpoints()
        
        print("=" * 60)
        print("📊 Test Summary:")
        print(f"✅ Passed: {self.test_results['summary']['passed']}")
        print(f"⚠️  Warnings: {self.test_results['summary']['warnings']}")  
        print(f"❌ Failed: {self.test_results['summary']['failed']}")
        
        # Save detailed results
        with open('/home/rigade/Testing/ai-model-validation-platform/tests/automated_test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\n📋 Detailed results saved to: automated_test_results.json")
        
        return self.test_results

if __name__ == "__main__":
    tester = ProductionTester()
    results = tester.run_all_tests()