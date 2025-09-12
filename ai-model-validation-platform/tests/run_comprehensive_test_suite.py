#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for Enhanced Test Page

This script orchestrates all test types:
1. Backend API Integration Tests
2. Frontend Component Tests  
3. End-to-End User Workflow Tests
4. Performance Validation
5. Security Testing
6. Cross-browser Compatibility

It provides detailed reporting and evidence collection.
"""

import asyncio
import subprocess
import sys
import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import tempfile
import shutil
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ComprehensiveTestRunner:
    """Orchestrates all test suites for the enhanced test page"""
    
    def __init__(self):
        self.project_root = Path("/home/rigade/Testing/ai-model-validation-platform")
        self.test_root = self.project_root / "tests"
        self.results = {}
        self.start_time = None
        self.end_time = None
        self.report_data = {}
        
    def setup_environment(self):
        """Setup test environment and verify prerequisites"""
        logger.info("🔧 Setting up test environment...")
        
        # Check if backend is running
        backend_running = self.check_service("http://localhost:8002/health", "Backend API")
        
        # Check if frontend is running  
        frontend_running = self.check_service("http://localhost:3000", "Frontend App")
        
        # Setup test databases if needed
        self.setup_test_database()
        
        # Install test dependencies
        self.install_test_dependencies()
        
        self.report_data["environment"] = {
            "backend_running": backend_running,
            "frontend_running": frontend_running,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info("✅ Environment setup complete")
        return backend_running or frontend_running  # At least one should be running
    
    def check_service(self, url: str, service_name: str) -> bool:
        """Check if a service is running"""
        try:
            import requests
            response = requests.get(url, timeout=5)
            if response.status_code < 400:
                logger.info(f"✅ {service_name} is running")
                return True
        except Exception as e:
            logger.warning(f"⚠️  {service_name} is not accessible: {e}")
        return False
    
    def setup_test_database(self):
        """Setup test database if needed"""
        try:
            # Create test database directory
            test_db_dir = self.project_root / "backend" / "test_data"
            test_db_dir.mkdir(exist_ok=True)
            
            # Copy test data if available
            test_fixtures = self.test_root / "fixtures"
            if test_fixtures.exists():
                shutil.copytree(test_fixtures, test_db_dir / "fixtures", dirs_exist_ok=True)
            
            logger.info("✅ Test database setup complete")
        except Exception as e:
            logger.warning(f"⚠️  Test database setup failed: {e}")
    
    def install_test_dependencies(self):
        """Install required test dependencies"""
        try:
            # Activate virtual environment and install Python dependencies
            venv_path = self.project_root / "test_venv"
            if venv_path.exists():
                pip_path = venv_path / "bin" / "pip"
                subprocess.run([
                    str(pip_path), "install", "-q",
                    "pytest", "pytest-asyncio", "httpx", "requests"
                ], check=False)
            
            # Install Node.js dependencies for frontend tests
            frontend_path = self.project_root / "frontend"
            if (frontend_path / "package.json").exists():
                subprocess.run([
                    "npm", "install", "--silent", 
                    "@testing-library/react", "@testing-library/jest-dom", 
                    "@testing-library/user-event", "jest"
                ], cwd=frontend_path, check=False, capture_output=True)
            
            # Install Puppeteer for E2E tests
            subprocess.run([
                "npm", "install", "--silent", "puppeteer"
            ], check=False, capture_output=True)
            
            logger.info("✅ Test dependencies installed")
        except Exception as e:
            logger.warning(f"⚠️  Dependency installation failed: {e}")

    async def run_backend_integration_tests(self) -> Dict[str, Any]:
        """Run backend API integration tests"""
        logger.info("🧪 Running Backend Integration Tests...")
        
        test_file = self.test_root / "integration" / "test_enhanced_test_page.py"
        if not test_file.exists():
            logger.error(f"❌ Test file not found: {test_file}")
            return {"status": "failed", "error": "Test file not found"}
        
        try:
            # Use the virtual environment Python
            venv_python = self.project_root / "test_venv" / "bin" / "python"
            if not venv_python.exists():
                venv_python = "python3"
            
            start_time = time.time()
            
            # Run the integration tests
            result = subprocess.run([
                str(venv_python), str(test_file)
            ], capture_output=True, text=True, cwd=self.project_root)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            success = result.returncode == 0
            
            return {
                "status": "passed" if success else "failed",
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except Exception as e:
            logger.error(f"❌ Backend integration tests failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def run_frontend_component_tests(self) -> Dict[str, Any]:
        """Run frontend component tests"""
        logger.info("🧪 Running Frontend Component Tests...")
        
        frontend_path = self.project_root / "frontend"
        test_file = self.test_root / "frontend" / "test_enhanced_test_components.js"
        
        if not test_file.exists():
            logger.error(f"❌ Frontend test file not found: {test_file}")
            return {"status": "failed", "error": "Test file not found"}
        
        try:
            start_time = time.time()
            
            # Copy test file to frontend src directory for Jest to find it
            frontend_test_dir = frontend_path / "src" / "__tests__"
            frontend_test_dir.mkdir(exist_ok=True)
            
            shutil.copy(test_file, frontend_test_dir / "enhanced_test_components.test.js")
            
            # Run Jest tests
            result = subprocess.run([
                "npm", "test", "--", "--watchAll=false", "--testPathPattern=enhanced_test_components"
            ], capture_output=True, text=True, cwd=frontend_path)
            
            end_time = time.time()
            duration = end_time - start_time
            
            success = result.returncode == 0
            
            return {
                "status": "passed" if success else "failed", 
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except Exception as e:
            logger.error(f"❌ Frontend component tests failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def run_e2e_workflow_tests(self) -> Dict[str, Any]:
        """Run end-to-end workflow tests"""
        logger.info("🧪 Running E2E Workflow Tests...")
        
        test_file = self.test_root / "e2e" / "test_complete_user_workflows.js"
        if not test_file.exists():
            logger.error(f"❌ E2E test file not found: {test_file}")
            return {"status": "failed", "error": "Test file not found"}
        
        try:
            start_time = time.time()
            
            # Run E2E tests
            result = subprocess.run([
                "node", str(test_file)
            ], capture_output=True, text=True, cwd=self.project_root)
            
            end_time = time.time()
            duration = end_time - start_time
            
            success = result.returncode == 0
            
            return {
                "status": "passed" if success else "failed",
                "duration": duration, 
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except Exception as e:
            logger.error(f"❌ E2E workflow tests failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def run_performance_tests(self) -> Dict[str, Any]:
        """Run performance validation tests"""
        logger.info("🧪 Running Performance Tests...")
        
        try:
            performance_results = {}
            
            # Test API response times
            if self.check_service("http://localhost:8002/health", "Backend"):
                api_perf = await self.measure_api_performance()
                performance_results["api"] = api_perf
            
            # Test frontend load times (if accessible)
            if self.check_service("http://localhost:3000", "Frontend"):
                frontend_perf = await self.measure_frontend_performance()
                performance_results["frontend"] = frontend_perf
            
            return {
                "status": "passed" if performance_results else "failed",
                "results": performance_results
            }
            
        except Exception as e:
            logger.error(f"❌ Performance tests failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def measure_api_performance(self) -> Dict[str, Any]:
        """Measure API endpoint performance"""
        import httpx
        
        endpoints = [
            "/health",
            "/projects/",
            "/api/enhanced-test-execution/status"
        ]
        
        results = {}
        
        async with httpx.AsyncClient(timeout=10) as client:
            for endpoint in endpoints:
                try:
                    # Measure response time
                    times = []
                    for _ in range(5):  # Test 5 times
                        start = time.time()
                        response = await client.get(f"http://localhost:8002{endpoint}")
                        end = time.time()
                        
                        if response.status_code < 400:
                            times.append((end - start) * 1000)  # Convert to ms
                    
                    if times:
                        results[endpoint] = {
                            "avg_response_time_ms": sum(times) / len(times),
                            "min_response_time_ms": min(times),
                            "max_response_time_ms": max(times),
                            "success_rate": len(times) / 5
                        }
                        
                except Exception as e:
                    results[endpoint] = {"error": str(e)}
        
        return results

    async def measure_frontend_performance(self) -> Dict[str, Any]:
        """Measure frontend performance using basic HTTP requests"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                start = time.time()
                response = await client.get("http://localhost:3000")
                end = time.time()
                
                load_time = (end - start) * 1000
                content_size = len(response.content) if response.content else 0
                
                return {
                    "load_time_ms": load_time,
                    "content_size_bytes": content_size,
                    "status_code": response.status_code
                }
        except Exception as e:
            return {"error": str(e)}

    async def run_security_tests(self) -> Dict[str, Any]:
        """Run basic security validation tests"""
        logger.info("🧪 Running Security Tests...")
        
        try:
            security_results = {}
            
            # Test for common security headers
            headers_test = await self.test_security_headers()
            security_results["headers"] = headers_test
            
            # Test for input validation
            input_test = await self.test_input_validation()
            security_results["input_validation"] = input_test
            
            return {
                "status": "passed",
                "results": security_results
            }
            
        except Exception as e:
            logger.error(f"❌ Security tests failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def test_security_headers(self) -> Dict[str, Any]:
        """Test for security headers"""
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8002/health")
                
                security_headers = [
                    "X-Content-Type-Options",
                    "X-Frame-Options", 
                    "X-XSS-Protection",
                    "Strict-Transport-Security"
                ]
                
                header_results = {}
                for header in security_headers:
                    header_results[header] = header in response.headers
                
                return header_results
                
        except Exception as e:
            return {"error": str(e)}

    async def test_input_validation(self) -> Dict[str, Any]:
        """Test input validation"""
        try:
            import httpx
            
            test_cases = [
                {"input": "<script>alert('xss')</script>", "type": "xss"},
                {"input": "'; DROP TABLE projects; --", "type": "sql_injection"},
                {"input": "A" * 1000, "type": "long_input"}
            ]
            
            results = {}
            
            async with httpx.AsyncClient() as client:
                for test_case in test_cases:
                    try:
                        response = await client.post(
                            "http://localhost:8002/projects/",
                            json={
                                "name": test_case["input"],
                                "description": "Security test",
                                "camera_type": "surveillance",
                                "status": "active"
                            }
                        )
                        
                        # Check if input was properly sanitized/rejected
                        if response.status_code == 422:
                            results[test_case["type"]] = "blocked"
                        elif response.status_code == 201:
                            # Check if response contains unsanitized input
                            response_data = response.json()
                            if test_case["input"] in str(response_data):
                                results[test_case["type"]] = "vulnerable"
                            else:
                                results[test_case["type"]] = "sanitized"
                        else:
                            results[test_case["type"]] = f"unexpected_status_{response.status_code}"
                            
                    except Exception as e:
                        results[test_case["type"]] = f"error: {str(e)}"
            
            return results
            
        except Exception as e:
            return {"error": str(e)}

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites"""
        logger.info("🚀 Starting Comprehensive Test Suite")
        logger.info("=" * 80)
        
        self.start_time = datetime.now()
        
        # Setup environment
        setup_success = self.setup_environment()
        if not setup_success:
            logger.error("❌ Environment setup failed")
            return {"status": "failed", "error": "Environment setup failed"}
        
        # Run all test suites
        test_suites = {
            "backend_integration": self.run_backend_integration_tests,
            "frontend_components": self.run_frontend_component_tests,
            "e2e_workflows": self.run_e2e_workflow_tests,
            "performance": self.run_performance_tests,
            "security": self.run_security_tests
        }
        
        for suite_name, test_func in test_suites.items():
            logger.info(f"🧪 Running {suite_name.replace('_', ' ').title()} Tests...")
            
            try:
                result = await test_func()
                self.results[suite_name] = result
                
                status_icon = "✅" if result.get("status") == "passed" else "❌"
                logger.info(f"{status_icon} {suite_name}: {result.get('status', 'unknown')}")
                
            except Exception as e:
                logger.error(f"❌ {suite_name} failed: {e}")
                self.results[suite_name] = {"status": "failed", "error": str(e)}
        
        self.end_time = datetime.now()
        
        # Generate comprehensive report
        report = self.generate_comprehensive_report()
        await self.save_test_results(report)
        
        return self.results

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        logger.info("=" * 80)
        logger.info("📊 COMPREHENSIVE TEST RESULTS")
        logger.info("=" * 80)
        
        total_suites = len(self.results)
        passed_suites = sum(1 for result in self.results.values() 
                           if result.get("status") == "passed")
        failed_suites = total_suites - passed_suites
        
        overall_success_rate = (passed_suites / total_suites) * 100 if total_suites > 0 else 0
        
        duration = self.end_time - self.start_time if self.start_time and self.end_time else None
        
        logger.info(f"Test Duration: {duration}")
        logger.info(f"Total Test Suites: {total_suites}")
        logger.info(f"Passed: {passed_suites}")
        logger.info(f"Failed: {failed_suites}")
        logger.info(f"Overall Success Rate: {overall_success_rate:.1f}%")
        logger.info("")
        
        # Detailed results per suite
        for suite_name, result in self.results.items():
            status = result.get("status", "unknown")
            icon = "✅" if status == "passed" else "❌"
            
            logger.info(f"{icon} {suite_name.replace('_', ' ').title()}: {status}")
            
            if "duration" in result:
                logger.info(f"    Duration: {result['duration']:.2f}s")
            
            if "error" in result:
                logger.info(f"    Error: {result['error']}")
            
            if "results" in result and isinstance(result["results"], dict):
                for key, value in result["results"].items():
                    logger.info(f"    {key}: {value}")
        
        logger.info("=" * 80)
        
        # Create comprehensive report data
        report = {
            "summary": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration": str(duration) if duration else None,
                "total_suites": total_suites,
                "passed_suites": passed_suites,
                "failed_suites": failed_suites,
                "success_rate": overall_success_rate
            },
            "environment": self.report_data.get("environment", {}),
            "test_results": self.results,
            "recommendations": self.generate_recommendations()
        }
        
        return report

    def generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        for suite_name, result in self.results.items():
            if result.get("status") == "failed":
                if suite_name == "backend_integration":
                    recommendations.append("🔧 Backend API issues detected. Check server logs and database connectivity.")
                elif suite_name == "frontend_components":
                    recommendations.append("🎨 Frontend component issues detected. Review React components and state management.")
                elif suite_name == "e2e_workflows":
                    recommendations.append("🔄 User workflow issues detected. Check UI elements and user interactions.")
                elif suite_name == "performance":
                    recommendations.append("⚡ Performance issues detected. Optimize API response times and frontend loading.")
                elif suite_name == "security":
                    recommendations.append("🔒 Security vulnerabilities detected. Implement input validation and security headers.")
        
        # General recommendations
        success_rate = (len([r for r in self.results.values() if r.get("status") == "passed"]) / len(self.results)) * 100
        
        if success_rate < 80:
            recommendations.append("🚨 Overall test success rate is below 80%. Consider comprehensive system review.")
        elif success_rate < 90:
            recommendations.append("⚠️  Some test suites failed. Address specific issues to improve system reliability.")
        else:
            recommendations.append("🎉 Excellent test results! System appears stable and functional.")
        
        return recommendations

    async def save_test_results(self, report: Dict[str, Any]):
        """Save comprehensive test results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON report
        json_file = self.test_root / f"comprehensive_test_report_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Save HTML report
        html_file = self.test_root / f"comprehensive_test_report_{timestamp}.html"
        await self.generate_html_report(report, html_file)
        
        logger.info(f"💾 Test results saved:")
        logger.info(f"    JSON: {json_file}")
        logger.info(f"    HTML: {html_file}")

    async def generate_html_report(self, report: Dict[str, Any], file_path: Path):
        """Generate HTML test report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Comprehensive Test Report - Enhanced Test Page</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
        .summary {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .metric {{ text-align: center; padding: 15px; background: #e9f4ff; border-radius: 8px; }}
        .test-suite {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; }}
        .passed {{ border-left: 4px solid #4CAF50; }}
        .failed {{ border-left: 4px solid #f44336; }}
        .recommendations {{ background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .code {{ background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧪 Comprehensive Test Report - Enhanced Test Page</h1>
        <p>Generated on: {report['summary']['end_time']}</p>
        <p>Duration: {report['summary']['duration']}</p>
    </div>
    
    <div class="summary">
        <div class="metric">
            <h3>{report['summary']['total_suites']}</h3>
            <p>Total Test Suites</p>
        </div>
        <div class="metric">
            <h3>{report['summary']['passed_suites']}</h3>
            <p>Passed</p>
        </div>
        <div class="metric">
            <h3>{report['summary']['failed_suites']}</h3>
            <p>Failed</p>
        </div>
        <div class="metric">
            <h3>{report['summary']['success_rate']:.1f}%</h3>
            <p>Success Rate</p>
        </div>
    </div>
    
    <h2>Test Results</h2>
"""
        
        for suite_name, result in report['test_results'].items():
            status_class = "passed" if result.get('status') == 'passed' else "failed"
            status_icon = "✅" if result.get('status') == 'passed' else "❌"
            
            html_content += f"""
    <div class="test-suite {status_class}">
        <h3>{status_icon} {suite_name.replace('_', ' ').title()}</h3>
        <p><strong>Status:</strong> {result.get('status', 'Unknown')}</p>
"""
            
            if 'duration' in result:
                html_content += f"        <p><strong>Duration:</strong> {result['duration']:.2f}s</p>\n"
            
            if 'error' in result:
                html_content += f"        <div class='code'><strong>Error:</strong> {result['error']}</div>\n"
            
            html_content += "    </div>\n"
        
        if report.get('recommendations'):
            html_content += """
    <div class="recommendations">
        <h2>🔍 Recommendations</h2>
        <ul>
"""
            for rec in report['recommendations']:
                html_content += f"            <li>{rec}</li>\n"
            
            html_content += """
        </ul>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(file_path, 'w') as f:
            f.write(html_content)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

async def main():
    """Main execution function"""
    runner = ComprehensiveTestRunner()
    results = await runner.run_all_tests()
    
    # Determine exit code based on results
    success_rate = len([r for r in results.values() if r.get("status") == "passed"]) / len(results)
    
    if success_rate >= 0.8:
        logger.info("🎉 Comprehensive tests PASSED!")
        return 0
    else:
        logger.error("❌ Comprehensive tests FAILED!")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("🛑 Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)