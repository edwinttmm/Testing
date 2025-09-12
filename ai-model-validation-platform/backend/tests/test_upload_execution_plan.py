"""
Upload Testing Execution Plan
============================

Comprehensive test execution plan for video upload workflow testing.
This script orchestrates all upload tests and generates detailed reports.
"""

import subprocess
import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

class UploadTestOrchestrator:
    """Orchestrates comprehensive upload testing"""
    
    def __init__(self):
        self.backend_dir = Path("/home/rigade/Testing/ai-model-validation-platform/backend")
        self.test_results = {}
        self.start_time = None
        
    def run_test_suite(self, test_file: str, test_description: str) -> Dict[str, Any]:
        """Run a specific test suite and capture results"""
        print(f"\n{'='*60}")
        print(f"🧪 Running {test_description}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            # Run pytest with detailed output
            result = subprocess.run([
                sys.executable, '-m', 'pytest', 
                f'tests/{test_file}',
                '-v', '--tb=short', '--json-report', 
                f'--json-report-file=test_results_{test_file.replace(".py", "")}.json'
            ], 
            cwd=self.backend_dir,
            capture_output=True, 
            text=True,
            timeout=300  # 5 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            success = result.returncode == 0
            
            test_result = {
                'test_file': test_file,
                'description': test_description,
                'success': success,
                'duration': duration,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'timestamp': datetime.now().isoformat()
            }
            
            # Try to load JSON report if available
            json_report_path = self.backend_dir / f'test_results_{test_file.replace(".py", "")}.json'
            if json_report_path.exists():
                try:
                    with open(json_report_path, 'r') as f:
                        json_report = json.load(f)
                        test_result['detailed_results'] = json_report
                except Exception as e:
                    test_result['json_parse_error'] = str(e)
            
            print(f"✅ Test suite completed in {duration:.2f}s" if success else f"❌ Test suite failed after {duration:.2f}s")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            return {
                'test_file': test_file,
                'description': test_description,
                'success': False,
                'duration': 300.0,
                'error': 'Test suite timed out after 5 minutes',
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'test_file': test_file,
                'description': test_description,
                'success': False,
                'duration': time.time() - start_time,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def run_backend_health_check(self) -> Dict[str, Any]:
        """Run backend health check before testing"""
        print("\n🏥 Running backend health check...")
        
        try:
            result = subprocess.run([
                sys.executable, '-c', '''
import sys
sys.path.append(".")
from health_check import comprehensive_health_check
import asyncio

async def main():
    health = await comprehensive_health_check()
    print(f"Health Status: {health['status']}")
    print(f"Database: {health['components']['database']['status']}")
    print(f"Storage: {health['components']['storage']['status']}")
    return health['status'] == 'healthy'

result = asyncio.run(main())
sys.exit(0 if result else 1)
'''
            ], 
            cwd=self.backend_dir,
            capture_output=True, 
            text=True,
            timeout=30
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_upload_endpoint_availability(self) -> Dict[str, Any]:
        """Test if upload endpoints are available"""
        print("\n🌐 Testing upload endpoint availability...")
        
        try:
            result = subprocess.run([
                sys.executable, '-c', '''
import requests
import sys
import time

# Test backend availability
try:
    response = requests.get("http://localhost:8000/health", timeout=5)
    print(f"Backend health check: {response.status_code}")
    backend_available = response.status_code == 200
except:
    backend_available = False
    print("Backend health check: FAILED")

# Test API documentation availability  
try:
    response = requests.get("http://localhost:8000/docs", timeout=5)
    print(f"API docs: {response.status_code}")
    docs_available = response.status_code == 200
except:
    docs_available = False
    print("API docs: FAILED")

print(f"Backend Available: {backend_available}")
print(f"Docs Available: {docs_available}")

sys.exit(0 if backend_available else 1)
'''
            ], 
            cwd=self.backend_dir,
            capture_output=True, 
            text=True,
            timeout=15
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def run_manual_upload_test(self) -> Dict[str, Any]:
        """Run manual upload test to verify basic functionality"""
        print("\n📤 Running manual upload verification...")
        
        try:
            result = subprocess.run([
                sys.executable, '-c', '''
import tempfile
import os
import requests
import json
import sys

# Create test project first
project_data = {
    "name": "Manual Test Project",
    "description": "Testing manual upload",
    "camera_model": "TestCam",
    "camera_view": "Front-facing VRU", 
    "signal_type": "GPIO"
}

try:
    # Create project
    response = requests.post("http://localhost:8000/api/projects", 
                           json=project_data, timeout=10)
    if response.status_code != 200:
        print(f"Project creation failed: {response.status_code} - {response.text}")
        sys.exit(1)
    
    project_id = response.json()["id"]
    print(f"Created test project: {project_id}")
    
    # Create test video file
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
        test_content = b"fake mp4 content for manual test" * 1000
        temp_file.write(test_content)
        temp_file.flush()
        
        # Upload video
        with open(temp_file.name, "rb") as f:
            files = {"file": ("manual_test.mp4", f, "video/mp4")}
            upload_response = requests.post(
                f"http://localhost:8000/api/projects/{project_id}/videos",
                files=files,
                timeout=30
            )
        
        # Cleanup temp file
        os.unlink(temp_file.name)
    
    if upload_response.status_code == 200:
        video_data = upload_response.json()
        print(f"Upload successful: {video_data['filename']}")
        print(f"Video ID: {video_data['id']}")
        print(f"File size: {video_data.get('file_size', 'unknown')}")
        sys.exit(0)
    else:
        print(f"Upload failed: {upload_response.status_code} - {upload_response.text}")
        sys.exit(1)
        
except requests.RequestException as e:
    print(f"Network error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Unexpected error: {e}")
    sys.exit(1)
'''
            ], 
            cwd=self.backend_dir,
            capture_output=True, 
            text=True,
            timeout=60
            )
            
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr if result.returncode != 0 else None
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_comprehensive_report(self) -> str:
        """Generate comprehensive testing report"""
        report_lines = [
            "# Video Upload Workflow Testing Report",
            f"Generated: {datetime.now().isoformat()}",
            f"Total Duration: {time.time() - self.start_time:.2f}s" if self.start_time else "Unknown",
            "",
            "## Executive Summary"
        ]
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
        
        report_lines.extend([
            f"- **Total Test Suites**: {total_tests}",
            f"- **Successful**: {successful_tests}",
            f"- **Failed**: {total_tests - successful_tests}",
            f"- **Success Rate**: {success_rate:.1f}%",
            "",
            "## Detailed Results"
        ])
        
        for test_name, result in self.test_results.items():
            status_emoji = "✅" if result.get('success') else "❌"
            duration = result.get('duration', 0)
            
            report_lines.extend([
                f"### {status_emoji} {result.get('description', test_name)}",
                f"- **File**: `{result.get('test_file', 'N/A')}`",
                f"- **Duration**: {duration:.2f}s",
                f"- **Status**: {'PASS' if result.get('success') else 'FAIL'}",
                ""
            ])
            
            if not result.get('success'):
                error = result.get('error', result.get('stderr', 'Unknown error'))
                report_lines.extend([
                    "**Error Details:**",
                    "```",
                    error,
                    "```",
                    ""
                ])
        
        # Add recommendations
        report_lines.extend([
            "## Recommendations",
            ""
        ])
        
        if success_rate < 100:
            report_lines.extend([
                "### Failed Tests",
                "- Review failed test outputs above",
                "- Check backend service availability",
                "- Verify database connectivity",
                "- Ensure all dependencies are installed",
                ""
            ])
        
        if success_rate >= 90:
            report_lines.extend([
                "### Upload System Status: HEALTHY",
                "- Most tests passed successfully",
                "- Upload workflow is functioning properly",
                "- System is ready for production use",
                ""
            ])
        else:
            report_lines.extend([
                "### Upload System Status: NEEDS ATTENTION",
                "- Multiple test failures detected", 
                "- Review system configuration",
                "- Check service dependencies",
                "- Consider system debugging before production deployment",
                ""
            ])
        
        return "\\n".join(report_lines)
    
    def execute_comprehensive_testing(self):
        """Execute the complete upload testing workflow"""
        self.start_time = time.time()
        
        print("🚀 Starting Comprehensive Video Upload Testing")
        print("=" * 80)
        
        # Step 1: Pre-flight checks
        print("\\n📋 Phase 1: Pre-flight System Checks")
        
        health_result = self.run_backend_health_check()
        self.test_results['health_check'] = health_result
        
        if health_result['success']:
            print("✅ Backend health check passed")
        else:
            print("⚠️  Backend health check failed - continuing with limited testing")
        
        endpoint_result = self.test_upload_endpoint_availability()
        self.test_results['endpoint_availability'] = endpoint_result
        
        if endpoint_result['success']:
            print("✅ Upload endpoints are available")
        else:
            print("❌ Upload endpoints not available - testing may fail")
        
        # Step 2: Manual upload verification
        print("\\n📋 Phase 2: Manual Upload Verification")
        
        manual_result = self.run_manual_upload_test()
        self.test_results['manual_upload'] = manual_result
        
        if manual_result['success']:
            print("✅ Manual upload test passed")
        else:
            print("❌ Manual upload test failed")
            print(f"Error: {manual_result.get('error', 'Unknown')}")
        
        # Step 3: Comprehensive test suites
        print("\\n📋 Phase 3: Comprehensive Test Suite Execution")
        
        test_suites = [
            ("test_video_upload_comprehensive.py", "Comprehensive Upload Functionality Tests"),
            ("test_upload_error_handling.py", "Upload Error Handling and Recovery Tests"), 
            ("test_upload_performance.py", "Upload Performance and Load Tests")
        ]
        
        for test_file, description in test_suites:
            # Check if test file exists
            test_path = self.backend_dir / "tests" / test_file
            if test_path.exists():
                result = self.run_test_suite(test_file, description)
                self.test_results[test_file] = result
            else:
                print(f"⚠️  Test file {test_file} not found - skipping")
                self.test_results[test_file] = {
                    'test_file': test_file,
                    'description': description,
                    'success': False,
                    'error': 'Test file not found',
                    'timestamp': datetime.now().isoformat()
                }
        
        # Step 4: Generate report
        print("\\n📋 Phase 4: Report Generation")
        
        report = self.generate_comprehensive_report()
        
        # Save report to file
        report_path = self.backend_dir / "tests" / "upload_test_report.md"
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"📄 Comprehensive report saved to: {report_path}")
        
        # Save detailed JSON results
        results_path = self.backend_dir / "tests" / "upload_test_results.json"
        with open(results_path, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"📊 Detailed results saved to: {results_path}")
        
        # Final summary
        total_duration = time.time() - self.start_time
        successful_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        total_tests = len(self.test_results)
        
        print("\\n" + "=" * 80)
        print("🏁 Testing Complete!")
        print(f"⏱️  Total Duration: {total_duration:.2f}s")
        print(f"✅ Successful Tests: {successful_tests}/{total_tests}")
        print(f"📊 Success Rate: {(successful_tests/total_tests*100) if total_tests > 0 else 0:.1f}%")
        
        if successful_tests == total_tests:
            print("🎉 ALL TESTS PASSED - Upload system is fully operational!")
            return True
        else:
            print("⚠️  Some tests failed - Review report for details")
            return False


if __name__ == "__main__":
    orchestrator = UploadTestOrchestrator()
    success = orchestrator.execute_comprehensive_testing()
    sys.exit(0 if success else 1)