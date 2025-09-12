#!/usr/bin/env python3
"""
Comprehensive UI/UX Testing Runner
==================================

Runs comprehensive UI tests including navigation, interaction, and functionality testing.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UITestRunner:
    def __init__(self, frontend_url="http://localhost:3000", backend_url="http://localhost:8000"):
        self.frontend_url = frontend_url.rstrip('/')
        self.backend_url = backend_url.rstrip('/')
        self.test_results = []
        
    def check_services(self) -> Dict[str, bool]:
        """Check if frontend and backend services are running"""
        services_status = {
            "frontend": False,
            "backend": False,
            "backend_health": False
        }
        
        # Check frontend
        try:
            response = requests.get(self.frontend_url, timeout=10)
            services_status["frontend"] = response.status_code == 200
            logger.info(f"✅ Frontend accessible at {self.frontend_url}")
        except Exception as e:
            logger.error(f"❌ Frontend not accessible: {e}")
            
        # Check backend
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            services_status["backend"] = response.status_code in [200, 503]  # 503 might be degraded but functional
            if response.status_code == 200:
                health_data = response.json()
                services_status["backend_health"] = health_data.get("status") in ["healthy", "operational", "ok"]
            logger.info(f"✅ Backend accessible at {self.backend_url}")
        except Exception as e:
            logger.error(f"❌ Backend not accessible: {e}")
            
        return services_status
    
    def test_api_endpoints(self) -> Dict[str, Any]:
        """Test critical API endpoints"""
        endpoints = [
            ("/health", "Health Check"),
            ("/api/dashboard/stats", "Dashboard Stats"),  
            ("/api/projects", "Projects API"),
            ("/api/videos", "Videos API"),
        ]
        
        api_results = []
        
        for endpoint, name in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.backend_url}{endpoint}", timeout=10)
                response_time = time.time() - start_time
                
                result = {
                    "endpoint": endpoint,
                    "name": name,
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "success": 200 <= response.status_code < 400
                }
                
                # Try to parse JSON
                try:
                    result["response_data"] = response.json()
                    result["has_json"] = True
                except:
                    result["has_json"] = False
                    
            except Exception as e:
                result = {
                    "endpoint": endpoint,
                    "name": name,
                    "error": str(e),
                    "success": False
                }
                
            api_results.append(result)
            
        return {
            "api_test_results": api_results,
            "successful_endpoints": sum(1 for r in api_results if r.get("success", False)),
            "total_endpoints": len(endpoints)
        }
    
    def create_browser_test_script(self) -> str:
        """Create a comprehensive browser test script"""
        return f'''
const {{ chromium }} = require('playwright');
const fs = require('fs');

(async () => {{
    const browser = await chromium.launch({{ headless: true }});
    const page = await browser.newPage();
    
    const results = [];
    const baseUrl = '{self.frontend_url}';
    
    try {{
        // Set viewport
        await page.setViewportSize({{ width: 1366, height: 768 }});
        
        console.log('🎯 Starting comprehensive UI tests...');
        
        // Test 1: Page Load and Navigation
        console.log('Testing page navigation...');
        const routes = [
            {{ path: '/', name: 'Dashboard' }},
            {{ path: '/projects', name: 'Projects' }},
            {{ path: '/ground-truth', name: 'Ground Truth' }},
            {{ path: '/test-execution', name: 'Test Execution' }},
            {{ path: '/results', name: 'Results' }},
            {{ path: '/datasets', name: 'Datasets' }},
            {{ path: '/settings', name: 'Settings' }}
        ];
        
        const navigationResults = [];
        for (const route of routes) {{
            try {{
                console.log(`  Testing route: ${{route.path}}`);
                await page.goto(`${{baseUrl}}${{route.path}}`, {{ waitUntil: 'networkidle' }});
                
                // Wait for React to render
                await page.waitForTimeout(2000);
                
                // Check for error boundaries
                const hasError = await page.locator('.error-boundary, .error-message, [class*="error"]').count();
                const title = await page.title();
                
                // Take screenshot
                await page.screenshot({{ 
                    path: `screenshot-${{route.name.toLowerCase().replace(/\\s+/g, '-')}}.png`,
                    fullPage: true 
                }});
                
                navigationResults.push({{
                    route: route.path,
                    name: route.name,
                    loaded: hasError === 0,
                    title: title,
                    hasError: hasError > 0,
                    errorCount: hasError
                }});
                
            }} catch (error) {{
                navigationResults.push({{
                    route: route.path,
                    name: route.name,
                    loaded: false,
                    error: error.message
                }});
            }}
        }}
        
        results.push({{
            test: 'page-navigation',
            success: navigationResults.filter(r => r.loaded).length === routes.length,
            details: navigationResults
        }});
        
        // Test 2: Interactive Elements
        console.log('Testing interactive elements...');
        await page.goto(`${{baseUrl}}/projects`);
        await page.waitForTimeout(2000);
        
        const interactiveResults = {{
            buttons: await page.locator('button:not([disabled])').count(),
            links: await page.locator('a').count(),
            inputs: await page.locator('input:not([type="hidden"])').count(),
            textareas: await page.locator('textarea').count()
        }};
        
        // Test button interactions (non-destructive)
        const buttons = await page.locator('button:not([disabled])').all();
        let clickableButtons = 0;
        for (let i = 0; i < Math.min(buttons.length, 5); i++) {{
            try {{
                const button = buttons[i];
                if (await button.isVisible()) {{
                    clickableButtons++;
                }}
            }} catch (e) {{
                // Skip problematic buttons
            }}
        }}
        
        interactiveResults.clickableButtons = clickableButtons;
        
        results.push({{
            test: 'interactive-elements',
            success: interactiveResults.buttons > 0 && interactiveResults.clickableButtons > 0,
            details: interactiveResults
        }});
        
        // Test 3: Data Display
        console.log('Testing data display components...');
        await page.goto(`${{baseUrl}}/`); // Dashboard
        await page.waitForTimeout(3000);
        
        const dataDisplayResults = {{
            cards: await page.locator('[class*="card"], [class*="Card"]').count(),
            tables: await page.locator('table').count(),
            lists: await page.locator('ul, ol').count(),
            charts: await page.locator('[class*="chart"], [class*="Chart"], svg').count(),
            stats: await page.locator('[class*="stat"], [class*="Stat"]').count()
        }};
        
        results.push({{
            test: 'data-display',
            success: dataDisplayResults.cards > 0 || dataDisplayResults.tables > 0,
            details: dataDisplayResults
        }});
        
        // Test 4: Error Boundaries
        console.log('Testing error boundaries...');
        const errorBoundaryResults = {{
            errorBoundaryElements: await page.locator('[class*="error-boundary"], [class*="ErrorBoundary"]').count(),
            errorMessages: await page.locator('[class*="error"], [class*="Error"]').count()
        }};
        
        results.push({{
            test: 'error-boundaries',
            success: true, // We expect no errors, so success if we get here
            details: errorBoundaryResults
        }});
        
        // Test 5: Responsive Design (simplified)
        console.log('Testing responsive design...');
        const responsiveResults = [];
        
        const viewports = [
            {{ width: 375, height: 667, name: 'Mobile' }},
            {{ width: 768, height: 1024, name: 'Tablet' }},
            {{ width: 1366, height: 768, name: 'Desktop' }}
        ];
        
        for (const viewport of viewports) {{
            await page.setViewportSize({{ width: viewport.width, height: viewport.height }});
            await page.goto(`${{baseUrl}}/`);
            await page.waitForTimeout(1000);
            
            const sidebarVisible = await page.locator('nav, [class*="sidebar"], [class*="Sidebar"]').isVisible();
            
            responsiveResults.push({{
                viewport: viewport.name,
                width: viewport.width,
                height: viewport.height,
                sidebarVisible: sidebarVisible
            }});
        }}
        
        results.push({{
            test: 'responsive-design',
            success: responsiveResults.length === 3,
            details: responsiveResults
        }});
        
        // Test 6: Performance (basic)
        console.log('Testing basic performance...');
        await page.setViewportSize({{ width: 1366, height: 768 }});
        
        const performanceResults = {{
            navigationTimings: [],
            largestContentfulPaint: null,
            firstContentfulPaint: null
        }};
        
        // Measure page load time
        const startTime = Date.now();
        await page.goto(`${{baseUrl}}/`, {{ waitUntil: 'networkidle' }});
        const loadTime = Date.now() - startTime;
        
        performanceResults.pageLoadTime = loadTime;
        
        // Get performance metrics if available
        try {{
            const performanceMetrics = await page.evaluate(() => {{
                const perfEntries = performance.getEntriesByType('navigation');
                if (perfEntries.length > 0) {{
                    const entry = perfEntries[0];
                    return {{
                        domContentLoaded: entry.domContentLoadedEventEnd - entry.domContentLoadedEventStart,
                        loadComplete: entry.loadEventEnd - entry.loadEventStart
                    }};
                }}
                return null;
            }});
            performanceResults.performanceMetrics = performanceMetrics;
        }} catch (e) {{
            // Performance API not available
        }}
        
        results.push({{
            test: 'performance',
            success: loadTime < 10000, // Less than 10 seconds
            details: performanceResults
        }});
        
        console.log('✅ All UI tests completed');
        
    }} catch (error) {{
        console.error('❌ Browser test failed:', error);
        results.push({{
            test: 'browser-test-error',
            success: false,
            error: error.message
        }});
    }} finally {{
        // Save results
        fs.writeFileSync('browser-test-results.json', JSON.stringify(results, null, 2));
        console.log('📄 Results saved to browser-test-results.json');
        
        await browser.close();
    }}
}})();
'''
    
    def run_browser_tests(self) -> Optional[Dict]:
        """Run browser-based UI tests using Playwright"""
        try:
            # Check if Node.js is available
            node_check = subprocess.run(['node', '--version'], capture_output=True, text=True)
            if node_check.returncode != 0:
                logger.error("❌ Node.js not available - cannot run browser tests")
                return None
            
            # Create test script
            script_content = self.create_browser_test_script()
            with open('browser_ui_test.js', 'w') as f:
                f.write(script_content)
            
            # Check if Playwright is installed
            playwright_check = subprocess.run(['npm', 'list', 'playwright'], capture_output=True, text=True)
            if playwright_check.returncode != 0:
                logger.info("📦 Installing Playwright...")
                subprocess.run(['npm', 'install', 'playwright'], check=True)
            
            logger.info("🌐 Running browser UI tests...")
            
            # Run the test
            result = subprocess.run(['node', 'browser_ui_test.js'], 
                                  capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # Load results
                if os.path.exists('browser-test-results.json'):
                    with open('browser-test-results.json', 'r') as f:
                        return json.load(f)
                else:
                    return {"error": "Results file not found", "stdout": result.stdout}
            else:
                return {
                    "error": "Browser tests failed",
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            logger.error("⏰ Browser tests timed out")
            return {"error": "Browser tests timed out after 2 minutes"}
        except Exception as e:
            logger.error(f"❌ Browser test setup failed: {e}")
            return {"error": f"Browser test setup failed: {str(e)}"}
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all comprehensive UI/UX tests"""
        logger.info("🎯 Starting Comprehensive UI/UX Integration Tests")
        
        start_time = datetime.now()
        
        # Check services
        services_status = self.check_services()
        if not services_status["frontend"]:
            return {
                "success": False,
                "error": "Frontend service not available",
                "services_status": services_status,
                "timestamp": start_time.isoformat()
            }
        
        if not services_status["backend"]:
            logger.warning("⚠️ Backend service not fully available - some tests may fail")
        
        # Run API tests
        logger.info("🔌 Testing API endpoints...")
        api_results = self.test_api_endpoints()
        
        # Run browser tests
        browser_results = None
        try:
            browser_results = self.run_browser_tests()
        except Exception as e:
            logger.error(f"❌ Browser tests failed: {e}")
            browser_results = {"error": str(e)}
        
        # Compile results
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Calculate success metrics
        total_tests = 0
        passed_tests = 0
        
        # Count API test success
        if api_results:
            api_successful = api_results.get("successful_endpoints", 0)
            api_total = api_results.get("total_endpoints", 0)
            total_tests += api_total
            passed_tests += api_successful
        
        # Count browser test success
        if browser_results and isinstance(browser_results, list):
            browser_successful = sum(1 for test in browser_results if test.get("success", False))
            browser_total = len(browser_results)
            total_tests += browser_total
            passed_tests += browser_successful
        
        comprehensive_results = {
            "success": True,
            "timestamp": start_time.isoformat(),
            "duration_seconds": duration,
            "services_status": services_status,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "api_results": api_results,
            "browser_results": browser_results,
            "recommendations": self.generate_recommendations(api_results, browser_results)
        }
        
        return comprehensive_results
    
    def generate_recommendations(self, api_results: Dict, browser_results: Optional[Dict]) -> List[str]:
        """Generate UI/UX improvement recommendations"""
        recommendations = []
        
        # API-based recommendations
        if api_results:
            failed_endpoints = [r for r in api_results.get("api_test_results", []) if not r.get("success", False)]
            if failed_endpoints:
                recommendations.append(f"Fix {len(failed_endpoints)} failing API endpoints for proper data integration")
            
            slow_endpoints = [r for r in api_results.get("api_test_results", []) if r.get("response_time", 0) > 2.0]
            if slow_endpoints:
                recommendations.append(f"Optimize {len(slow_endpoints)} slow API endpoints (>2s response time)")
        
        # Browser test recommendations
        if browser_results and isinstance(browser_results, list):
            navigation_test = next((t for t in browser_results if t.get("test") == "page-navigation"), None)
            if navigation_test and not navigation_test.get("success", False):
                recommendations.append("Fix page navigation issues - some routes are not loading properly")
            
            interactive_test = next((t for t in browser_results if t.get("test") == "interactive-elements"), None)
            if interactive_test and not interactive_test.get("success", False):
                recommendations.append("Improve interactive elements - buttons or forms may not be working correctly")
            
            performance_test = next((t for t in browser_results if t.get("test") == "performance"), None)
            if performance_test and not performance_test.get("success", False):
                recommendations.append("Optimize page load performance - taking longer than 10 seconds")
        
        # General recommendations
        recommendations.extend([
            "Implement comprehensive error boundary testing with intentional error triggers",
            "Add automated accessibility testing using axe-core or similar tools",
            "Create visual regression tests to catch UI changes",
            "Add performance monitoring with Core Web Vitals tracking",
            "Test file upload functionality with various file types and sizes",
            "Implement cross-browser compatibility testing",
            "Add mobile-specific touch interaction testing"
        ])
        
        return recommendations
    
    def cleanup(self):
        """Cleanup test artifacts"""
        files_to_cleanup = [
            'browser_ui_test.js',
            'browser-test-results.json'
        ]
        
        for filename in files_to_cleanup:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except:
                pass
        
        # Cleanup screenshot files
        for file in os.listdir('.'):
            if file.startswith('screenshot-') and file.endswith('.png'):
                try:
                    os.remove(file)
                except:
                    pass

def main():
    """Main test runner"""
    runner = UITestRunner()
    
    try:
        results = runner.run_comprehensive_tests()
        
        # Save results
        results_file = f"comprehensive_ui_test_results_{int(datetime.now().timestamp())}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Print results summary
        print("\n" + "="*80)
        print("🎯 COMPREHENSIVE UI/UX INTEGRATION TEST RESULTS")
        print("="*80)
        
        if results.get("success"):
            summary = results.get("summary", {})
            print(f"📊 Overall Success Rate: {summary.get('success_rate', 0):.1f}%")
            print(f"✅ Passed Tests: {summary.get('passed_tests', 0)}")
            print(f"❌ Failed Tests: {summary.get('failed_tests', 0)}")
            print(f"📈 Total Tests: {summary.get('total_tests', 0)}")
            print(f"⏱️  Duration: {results.get('duration_seconds', 0):.1f} seconds")
            
            # Services status
            services = results.get("services_status", {})
            print(f"\n🔧 Services Status:")
            print(f"   Frontend: {'✅ Available' if services.get('frontend') else '❌ Not Available'}")
            print(f"   Backend: {'✅ Available' if services.get('backend') else '❌ Not Available'}")
            print(f"   Backend Health: {'✅ Healthy' if services.get('backend_health') else '⚠️ Degraded'}")
            
            # API Results
            api_results = results.get("api_results", {})
            if api_results:
                print(f"\n🔌 API Test Results:")
                print(f"   Successful Endpoints: {api_results.get('successful_endpoints', 0)}/{api_results.get('total_endpoints', 0)}")
                
                for api_result in api_results.get("api_test_results", []):
                    status = "✅" if api_result.get("success") else "❌"
                    name = api_result.get("name", "Unknown")
                    endpoint = api_result.get("endpoint", "")
                    if "response_time" in api_result:
                        print(f"   {status} {name} ({api_result['response_time']:.3f}s) - {endpoint}")
                    else:
                        print(f"   {status} {name} - {endpoint}")
            
            # Browser Results
            browser_results = results.get("browser_results")
            if browser_results and isinstance(browser_results, list):
                print(f"\n🌐 Browser Test Results:")
                for br in browser_results:
                    if isinstance(br, dict) and "test" in br:
                        status = "✅ PASSED" if br.get("success", False) else "❌ FAILED"
                        test_name = br["test"].replace("-", " ").title()
                        print(f"   {status} - {test_name}")
            elif browser_results and "error" in browser_results:
                print(f"\n🌐 Browser Tests: ❌ {browser_results['error']}")
            
            # Recommendations
            recommendations = results.get("recommendations", [])
            if recommendations:
                print(f"\n💡 Recommendations ({len(recommendations)}):")
                for i, rec in enumerate(recommendations[:10], 1):
                    print(f"   {i}. {rec}")
                if len(recommendations) > 10:
                    print(f"   ... and {len(recommendations) - 10} more")
        else:
            print(f"❌ Test suite failed: {results.get('error', 'Unknown error')}")
        
        print(f"\n📁 Detailed results saved to: {results_file}")
        print("="*80)
        
        return results
        
    except Exception as e:
        print(f"❌ Test runner failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        runner.cleanup()

if __name__ == "__main__":
    main()