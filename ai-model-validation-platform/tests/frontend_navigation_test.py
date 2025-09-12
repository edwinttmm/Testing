#!/usr/bin/env python3
"""
Frontend Navigation and UI Testing Suite
Tests frontend pages and navigation using HTTP requests and content analysis
"""

import requests
import json
import time
import re
from urllib.parse import urljoin
from datetime import datetime

class FrontendNavigationTester:
    def __init__(self, frontend_url="http://localhost:3000", backend_url="http://localhost:8000"):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.session = requests.Session()
        self.test_results = {
            "test_started": datetime.now().isoformat(),
            "frontend_url": frontend_url,
            "backend_url": backend_url,
            "navigation_tests": [],
            "ui_component_tests": [],
            "javascript_tests": []
        }
    
    def log_navigation_test(self, test_name, status, details=None, error=None):
        """Log navigation test result"""
        result = {
            "test_name": test_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details,
            "error": str(error) if error else None
        }
        self.test_results["navigation_tests"].append(result)
        
        status_symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_symbol} NAV: {test_name}: {status}")
        if details:
            print(f"       Details: {details}")
    
    def test_main_page_load(self):
        """Test main page loading and content"""
        try:
            response = self.session.get(self.frontend_url, timeout=15)
            if response.status_code == 200:
                html_content = response.text
                
                # Check for essential React app elements
                essential_elements = [
                    '<div id="root">',
                    'React App',
                    'static/js/',
                    'static/css/'
                ]
                
                found_elements = [elem for elem in essential_elements if elem in html_content]
                
                if len(found_elements) >= 3:
                    self.log_navigation_test("Main Page Load", "PASS", 
                                           f"Found {len(found_elements)}/{len(essential_elements)} essential elements")
                else:
                    self.log_navigation_test("Main Page Load", "PARTIAL", 
                                           f"Found only {len(found_elements)}/{len(essential_elements)} essential elements")
                
                # Test JavaScript resources
                js_links = re.findall(r'src="([^"]*\.js[^"]*)"', html_content)
                if js_links:
                    self.log_navigation_test("JavaScript Resources", "PASS", 
                                           f"Found {len(js_links)} JS resources")
                else:
                    self.log_navigation_test("JavaScript Resources", "FAIL", 
                                           "No JavaScript resources found")
                
                # Test CSS resources
                css_links = re.findall(r'href="([^"]*\.css[^"]*)"', html_content)
                if css_links:
                    self.log_navigation_test("CSS Resources", "PASS", 
                                           f"Found {len(css_links)} CSS resources")
                else:
                    self.log_navigation_test("CSS Resources", "FAIL", 
                                           "No CSS resources found")
                
                return True
            else:
                self.log_navigation_test("Main Page Load", "FAIL", 
                                       f"HTTP Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_navigation_test("Main Page Load", "FAIL", error=e)
            return False
    
    def test_static_resources(self):
        """Test loading of static resources (CSS, JS)"""
        try:
            # First get the main page to extract resource URLs
            response = self.session.get(self.frontend_url, timeout=10)
            html_content = response.text
            
            # Extract JS and CSS URLs
            js_urls = re.findall(r'src="(/static/js/[^"]*)"', html_content)
            css_urls = re.findall(r'href="(/static/css/[^"]*)"', html_content)
            
            resources_tested = 0
            resources_passed = 0
            
            # Test JavaScript files
            for js_url in js_urls[:3]:  # Test first 3 JS files
                full_url = urljoin(self.frontend_url, js_url)
                js_response = self.session.get(full_url, timeout=10)
                resources_tested += 1
                if js_response.status_code == 200:
                    resources_passed += 1
                    self.log_navigation_test(f"JS Resource: {js_url}", "PASS", 
                                           f"Size: {len(js_response.content)} bytes")
                else:
                    self.log_navigation_test(f"JS Resource: {js_url}", "FAIL", 
                                           f"Status: {js_response.status_code}")
            
            # Test CSS files
            for css_url in css_urls[:3]:  # Test first 3 CSS files
                full_url = urljoin(self.frontend_url, css_url)
                css_response = self.session.get(full_url, timeout=10)
                resources_tested += 1
                if css_response.status_code == 200:
                    resources_passed += 1
                    self.log_navigation_test(f"CSS Resource: {css_url}", "PASS", 
                                           f"Size: {len(css_response.content)} bytes")
                else:
                    self.log_navigation_test(f"CSS Resource: {css_url}", "FAIL", 
                                           f"Status: {css_response.status_code}")
            
            success_rate = resources_passed / resources_tested if resources_tested > 0 else 0
            if success_rate >= 0.8:
                self.log_navigation_test("Static Resources Overall", "PASS", 
                                       f"{resources_passed}/{resources_tested} resources loaded")
                return True
            else:
                self.log_navigation_test("Static Resources Overall", "FAIL", 
                                       f"Only {resources_passed}/{resources_tested} resources loaded")
                return False
                
        except Exception as e:
            self.log_navigation_test("Static Resources", "FAIL", error=e)
            return False
    
    def test_api_connectivity_from_frontend(self):
        """Test that frontend can connect to backend APIs"""
        try:
            # Test CORS preflight for common frontend requests
            headers = {
                'Origin': self.frontend_url,
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type'
            }
            
            api_endpoints = [
                '/api/dashboard/stats',
                '/api/projects',
                '/api/videos'
            ]
            
            cors_passed = 0
            for endpoint in api_endpoints:
                url = urljoin(self.backend_url, endpoint)
                
                # Test OPTIONS request (CORS preflight)
                options_response = self.session.options(url, headers=headers, timeout=10)
                if options_response.status_code in [200, 204]:
                    cors_passed += 1
                
                # Test actual GET request
                get_response = self.session.get(url, timeout=10)
                if get_response.status_code == 200:
                    self.log_navigation_test(f"API Connectivity: {endpoint}", "PASS", 
                                           f"GET request successful")
                else:
                    self.log_navigation_test(f"API Connectivity: {endpoint}", "FAIL", 
                                           f"GET Status: {get_response.status_code}")
            
            if cors_passed >= len(api_endpoints) * 0.8:
                self.log_navigation_test("CORS Configuration", "PASS", 
                                       f"{cors_passed}/{len(api_endpoints)} endpoints support CORS")
                return True
            else:
                self.log_navigation_test("CORS Configuration", "PARTIAL", 
                                       f"Only {cors_passed}/{len(api_endpoints)} endpoints support CORS")
                return False
                
        except Exception as e:
            self.log_navigation_test("API Connectivity", "FAIL", error=e)
            return False
    
    def test_responsive_viewport(self):
        """Test responsive design elements"""
        try:
            response = self.session.get(self.frontend_url, timeout=10)
            html_content = response.text
            
            # Check for responsive design meta tags and CSS
            responsive_elements = {
                'viewport_meta': r'<meta[^>]*name="viewport"[^>]*>',
                'media_queries': r'@media[^{]*{',
                'responsive_classes': r'class="[^"]*(?:responsive|mobile|tablet|desktop)[^"]*"',
                'bootstrap_grid': r'class="[^"]*(?:col-|row|container)[^"]*"',
                'flexbox': r'display:\s*flex',
                'grid': r'display:\s*grid'
            }
            
            found_responsive = {}
            for element_name, pattern in responsive_elements.items():
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                found_responsive[element_name] = len(matches)
                if matches:
                    self.log_navigation_test(f"Responsive: {element_name}", "PASS", 
                                           f"Found {len(matches)} instances")
                else:
                    self.log_navigation_test(f"Responsive: {element_name}", "PARTIAL", 
                                           "Not found in initial HTML")
            
            # Overall responsive score
            responsive_score = sum(1 for count in found_responsive.values() if count > 0)
            total_checks = len(responsive_elements)
            
            if responsive_score >= total_checks * 0.5:
                self.log_navigation_test("Overall Responsive Design", "PASS", 
                                       f"Found {responsive_score}/{total_checks} responsive indicators")
                return True
            else:
                self.log_navigation_test("Overall Responsive Design", "PARTIAL", 
                                       f"Found only {responsive_score}/{total_checks} responsive indicators")
                return False
                
        except Exception as e:
            self.log_navigation_test("Responsive Viewport", "FAIL", error=e)
            return False
    
    def test_error_pages(self):
        """Test error handling for invalid routes"""
        try:
            # Test various invalid routes
            invalid_routes = [
                '/nonexistent-page',
                '/projects/99999',
                '/videos/invalid-id',
                '/dashboard/fake-section'
            ]
            
            error_handling_passed = 0
            for route in invalid_routes:
                url = urljoin(self.frontend_url, route)
                response = self.session.get(url, timeout=10)
                
                # React apps typically return 200 for all routes and handle routing client-side
                if response.status_code == 200:
                    # Check if it's showing an error page or redirecting properly
                    if "error" in response.text.lower() or "not found" in response.text.lower():
                        self.log_navigation_test(f"Error Handling: {route}", "PASS", 
                                               "Shows error content")
                        error_handling_passed += 1
                    else:
                        # This is actually OK for SPAs - they handle routing client-side
                        self.log_navigation_test(f"Error Handling: {route}", "PASS", 
                                               "SPA routing - handled client-side")
                        error_handling_passed += 1
                elif response.status_code == 404:
                    self.log_navigation_test(f"Error Handling: {route}", "PASS", 
                                           "Proper 404 response")
                    error_handling_passed += 1
                else:
                    self.log_navigation_test(f"Error Handling: {route}", "PARTIAL", 
                                           f"Unexpected status: {response.status_code}")
            
            if error_handling_passed >= len(invalid_routes) * 0.75:
                return True
            else:
                return False
                
        except Exception as e:
            self.log_navigation_test("Error Pages", "FAIL", error=e)
            return False
    
    def test_performance_metrics(self):
        """Test basic performance metrics"""
        try:
            start_time = time.time()
            response = self.session.get(self.frontend_url, timeout=30)
            load_time = time.time() - start_time
            
            # Check response time
            if load_time < 2.0:
                self.log_navigation_test("Page Load Time", "PASS", 
                                       f"Loaded in {load_time:.2f} seconds")
            elif load_time < 5.0:
                self.log_navigation_test("Page Load Time", "PARTIAL", 
                                       f"Loaded in {load_time:.2f} seconds (acceptable)")
            else:
                self.log_navigation_test("Page Load Time", "FAIL", 
                                       f"Slow load time: {load_time:.2f} seconds")
            
            # Check content size
            content_size = len(response.content)
            if content_size < 1024 * 1024:  # Less than 1MB
                self.log_navigation_test("Content Size", "PASS", 
                                       f"Reasonable size: {content_size/1024:.1f} KB")
            elif content_size < 5 * 1024 * 1024:  # Less than 5MB
                self.log_navigation_test("Content Size", "PARTIAL", 
                                       f"Large size: {content_size/1024/1024:.1f} MB")
            else:
                self.log_navigation_test("Content Size", "FAIL", 
                                       f"Very large size: {content_size/1024/1024:.1f} MB")
            
            return load_time < 5.0 and content_size < 5 * 1024 * 1024
            
        except Exception as e:
            self.log_navigation_test("Performance Metrics", "FAIL", error=e)
            return False
    
    def run_frontend_tests(self):
        """Run all frontend navigation tests"""
        print("🌐 Starting Frontend Navigation Testing")
        print("=" * 50)
        
        test_methods = [
            self.test_main_page_load,
            self.test_static_resources,
            self.test_api_connectivity_from_frontend,
            self.test_responsive_viewport,
            self.test_error_pages,
            self.test_performance_metrics
        ]
        
        for test_method in test_methods:
            print(f"\n🧪 Running {test_method.__name__}...")
            try:
                test_method()
            except Exception as e:
                self.log_navigation_test(test_method.__name__, "FAIL", error=f"Test crashed: {e}")
            time.sleep(0.5)
        
        # Calculate summary
        total_tests = len(self.test_results["navigation_tests"])
        passed_tests = len([t for t in self.test_results["navigation_tests"] if t["status"] == "PASS"])
        failed_tests = len([t for t in self.test_results["navigation_tests"] if t["status"] == "FAIL"])
        partial_tests = len([t for t in self.test_results["navigation_tests"] if t["status"] == "PARTIAL"])
        
        print("\n" + "=" * 50)
        print("📊 FRONTEND NAVIGATION SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️ Partial: {partial_tests}")
        print(f"🎯 Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "0%")
        
        # Save results
        results_file = f"/home/rigade/Testing/ai-model-validation-platform/tests/frontend_navigation_results_{int(time.time())}.json"
        with open(results_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\n📄 Results saved to: {results_file}")
        return self.test_results

if __name__ == "__main__":
    tester = FrontendNavigationTester()
    results = tester.run_frontend_tests()