"""
HIL Ground Truth Matching Test Suite Runner

Comprehensive test runner for the HIL (Hardware-in-the-Loop) ground truth matching system.
Executes all test categories and provides detailed reporting on test coverage and results.

Test Suite Coverage:
1. Ground Truth Matching Algorithm Tests
2. Video Timing Synchronization Tests  
3. End-to-End HIL Workflow Tests
4. Session Completion Logic Tests
5. Performance Benchmark Tests
6. Database Integration Tests

Usage:
    python tests/run_hil_test_suite.py [--verbose] [--category CATEGORY] [--benchmark]
"""

import sys
import os
import argparse
import time
import subprocess
from typing import Dict, List, Any
from datetime import datetime

# Add backend to path
sys.path.append('/home/rigade/Testing/ai-model-validation-platform/backend')


class HILTestSuiteRunner:
    """Comprehensive test suite runner for HIL system"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.test_results = {}
        self.start_time = None
        self.test_categories = {
            "ground_truth_matching": {
                "file": "test_ground_truth_matching.py",
                "description": "Ground truth matching algorithm validation",
                "critical": True
            },
            "video_timing": {
                "file": "test_video_timing_service.py", 
                "description": "Video timing synchronization accuracy",
                "critical": True
            },
            "hil_workflow": {
                "file": "test_hil_workflow_end_to_end.py",
                "description": "End-to-end HIL workflow integration",
                "critical": True
            },
            "session_completion": {
                "file": "test_session_completion_logic.py",
                "description": "Session completion service logic",
                "critical": True
            },
            "performance": {
                "file": "test_performance_benchmarks.py",
                "description": "Performance benchmarks and load testing",
                "critical": False
            },
            "database": {
                "file": "test_database_integration.py",
                "description": "Database integration and data integrity",
                "critical": True
            }
        }
    
    def run_test_category(self, category: str) -> Dict[str, Any]:
        """Run a specific test category"""
        if category not in self.test_categories:
            raise ValueError(f"Unknown test category: {category}")
        
        test_info = self.test_categories[category]
        test_file = f"tests/{test_info['file']}"
        
        print(f"\\n{'='*60}")
        print(f"Running {category.upper()} Tests")
        print(f"Description: {test_info['description']}")
        print(f"File: {test_file}")
        print(f"Critical: {'Yes' if test_info['critical'] else 'No'}")
        print(f"{'='*60}")
        
        # Build pytest command
        pytest_cmd = [
            "python", "-m", "pytest",
            test_file,
            "-v" if self.verbose else "-q",
            "--tb=short",
            "--durations=10",  # Show 10 slowest tests
            "--strict-markers",
            "--disable-warnings"
        ]
        
        # Add performance reporting for benchmark tests
        if category == "performance":
            pytest_cmd.extend(["--benchmark-only", "--benchmark-sort=mean"])
        
        start_time = time.time()
        
        try:
            # Run pytest
            result = subprocess.run(
                pytest_cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per category
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            test_result = {
                "category": category,
                "file": test_file,
                "duration": duration,
                "return_code": result.returncode,
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "critical": test_info["critical"]
            }
            
            # Extract test statistics from pytest output
            test_result.update(self._parse_pytest_output(result.stdout))
            
            if self.verbose or not test_result["success"]:
                print(f"\\nSTDOUT:\\n{result.stdout}")
                if result.stderr:
                    print(f"\\nSTDERR:\\n{result.stderr}")
            
            # Print summary
            if test_result["success"]:
                print(f"✅ {category.upper()} TESTS PASSED")
                print(f"   Duration: {duration:.2f}s")
                if "total_tests" in test_result:
                    print(f"   Tests: {test_result['passed_tests']}/{test_result['total_tests']} passed")
            else:
                print(f"❌ {category.upper()} TESTS FAILED")
                print(f"   Duration: {duration:.2f}s")
                print(f"   Return Code: {result.returncode}")
                if "failed_tests" in test_result and test_result["failed_tests"] > 0:
                    print(f"   Failed: {test_result['failed_tests']} tests")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            return {
                "category": category,
                "file": test_file,
                "duration": 300,
                "return_code": -1,
                "success": False,
                "error": "Test timeout (300s)",
                "critical": test_info["critical"]
            }
        
        except Exception as e:
            return {
                "category": category,
                "file": test_file,
                "duration": 0,
                "return_code": -2,
                "success": False,
                "error": str(e),
                "critical": test_info["critical"]
            }
    
    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse pytest output to extract test statistics"""
        stats = {}
        
        # Look for test summary line
        for line in output.split('\\n'):
            line = line.strip()
            
            # Parse test counts
            if "passed" in line and ("failed" in line or "error" in line or "skipped" in line):
                # Extract numbers from pytest summary
                import re
                
                # Match patterns like "5 passed, 2 failed in 3.45s"
                passed_match = re.search(r'(\\d+) passed', line)
                failed_match = re.search(r'(\\d+) failed', line)
                error_match = re.search(r'(\\d+) error', line)
                skipped_match = re.search(r'(\\d+) skipped', line)
                
                stats["passed_tests"] = int(passed_match.group(1)) if passed_match else 0
                stats["failed_tests"] = int(failed_match.group(1)) if failed_match else 0
                stats["error_tests"] = int(error_match.group(1)) if error_match else 0
                stats["skipped_tests"] = int(skipped_match.group(1)) if skipped_match else 0
                
                stats["total_tests"] = (
                    stats["passed_tests"] + 
                    stats["failed_tests"] + 
                    stats["error_tests"] + 
                    stats["skipped_tests"]
                )
                
                break
            
            # Simple case - just passed tests
            elif "passed" in line and "failed" not in line:
                passed_match = re.search(r'(\\d+) passed', line)
                if passed_match:
                    stats["passed_tests"] = int(passed_match.group(1))
                    stats["failed_tests"] = 0
                    stats["error_tests"] = 0
                    stats["skipped_tests"] = 0
                    stats["total_tests"] = stats["passed_tests"]
        
        return stats
    
    def run_all_tests(self, categories: List[str] = None) -> Dict[str, Any]:
        """Run all test categories or specified categories"""
        self.start_time = time.time()
        
        if categories is None:
            categories = list(self.test_categories.keys())
        
        print(f"\\n🚀 Starting HIL Test Suite")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Categories: {', '.join(categories)}")
        print(f"Verbose: {self.verbose}")
        
        # Run each test category
        for category in categories:
            try:
                result = self.run_test_category(category)
                self.test_results[category] = result
            except Exception as e:
                print(f"❌ Error running {category} tests: {e}")
                self.test_results[category] = {
                    "category": category,
                    "success": False,
                    "error": str(e),
                    "critical": self.test_categories[category]["critical"]
                }
        
        # Generate final report
        return self._generate_final_report()
    
    def _generate_final_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        end_time = time.time()
        total_duration = end_time - self.start_time
        
        # Calculate statistics
        total_categories = len(self.test_results)
        passed_categories = sum(1 for r in self.test_results.values() if r.get("success", False))
        failed_categories = total_categories - passed_categories
        
        critical_failures = [
            r for r in self.test_results.values() 
            if not r.get("success", False) and r.get("critical", False)
        ]
        
        total_tests = sum(r.get("total_tests", 0) for r in self.test_results.values())
        total_passed = sum(r.get("passed_tests", 0) for r in self.test_results.values())
        total_failed = sum(r.get("failed_tests", 0) for r in self.test_results.values())
        
        # Generate report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_duration": total_duration,
            "summary": {
                "total_categories": total_categories,
                "passed_categories": passed_categories,
                "failed_categories": failed_categories,
                "critical_failures": len(critical_failures),
                "total_tests": total_tests,
                "passed_tests": total_passed,
                "failed_tests": total_failed,
                "success_rate": (total_passed / total_tests * 100) if total_tests > 0 else 0
            },
            "category_results": self.test_results,
            "critical_failures": critical_failures,
            "overall_success": len(critical_failures) == 0 and failed_categories == 0
        }
        
        # Print final report
        self._print_final_report(report)
        
        return report
    
    def _print_final_report(self, report: Dict[str, Any]):
        """Print comprehensive final report"""
        print(f"\\n\\n{'='*80}")
        print(f"HIL TEST SUITE FINAL REPORT")
        print(f"{'='*80}")
        
        summary = report["summary"]
        
        # Overall status
        if report["overall_success"]:
            print(f"🎉 OVERALL RESULT: SUCCESS")
        else:
            print(f"💥 OVERALL RESULT: FAILURE")
        
        print(f"\\n📊 SUMMARY STATISTICS:")
        print(f"   Total Duration: {report['total_duration']:.2f}s")
        print(f"   Test Categories: {summary['passed_categories']}/{summary['total_categories']} passed")
        print(f"   Individual Tests: {summary['passed_tests']}/{summary['total_tests']} passed")
        print(f"   Success Rate: {summary['success_rate']:.1f}%")
        print(f"   Critical Failures: {summary['critical_failures']}")
        
        # Category breakdown
        print(f"\\n📋 CATEGORY BREAKDOWN:")
        for category, result in report["category_results"].items():
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            critical = "🔥 CRITICAL" if result.get("critical", False) else "📝 OPTIONAL"
            duration = result.get("duration", 0)
            
            print(f"   {category:20} {status:8} {critical:12} ({duration:.2f}s)")
            
            if "total_tests" in result:
                passed = result.get("passed_tests", 0)
                total = result.get("total_tests", 0)
                print(f"   {' '*20} Tests: {passed}/{total}")
        
        # Critical failures detail
        if report["critical_failures"]:
            print(f"\\n🚨 CRITICAL FAILURES:")
            for failure in report["critical_failures"]:
                print(f"   - {failure['category']}: {failure.get('error', 'Test failures')}")
        
        # Performance summary (if available)
        perf_result = report["category_results"].get("performance")
        if perf_result and perf_result.get("success"):
            print(f"\\n⚡ PERFORMANCE HIGHLIGHTS:")
            print(f"   Performance tests completed successfully")
            print(f"   Duration: {perf_result.get('duration', 0):.2f}s")
        
        # Test coverage summary
        print(f"\\n🎯 TEST COVERAGE VALIDATION:")
        coverage_areas = [
            ("Video Timing Synchronization", "video_timing"),
            ("Ground Truth Matching", "ground_truth_matching"), 
            ("End-to-End HIL Workflow", "hil_workflow"),
            ("Session Completion Logic", "session_completion"),
            ("Database Integration", "database"),
            ("Performance Benchmarks", "performance")
        ]
        
        for area_name, category in coverage_areas:
            if category in report["category_results"]:
                result = report["category_results"][category]
                status = "✅" if result.get("success", False) else "❌"
                print(f"   {area_name:30} {status}")
            else:
                print(f"   {area_name:30} ⚠️  NOT RUN")
        
        print(f"\\n{'='*80}")
        
        # Return exit code suggestion
        if report["overall_success"]:
            print(f"✨ All critical tests passed! HIL system ready for deployment.")
            return 0
        else:
            print(f"🛑 Critical test failures detected. Review and fix before deployment.")
            return 1


def main():
    """Main entry point for test suite runner"""
    parser = argparse.ArgumentParser(description="HIL Ground Truth Matching Test Suite Runner")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--category", "-c", choices=["ground_truth_matching", "video_timing", "hil_workflow", "session_completion", "performance", "database"], help="Run specific category only")
    parser.add_argument("--benchmark", "-b", action="store_true", help="Run performance benchmarks only")
    parser.add_argument("--critical-only", action="store_true", help="Run only critical tests")
    
    args = parser.parse_args()
    
    # Create test runner
    runner = HILTestSuiteRunner(verbose=args.verbose)
    
    # Determine which categories to run
    if args.benchmark:
        categories = ["performance"]
    elif args.category:
        categories = [args.category]
    elif args.critical_only:
        categories = [cat for cat, info in runner.test_categories.items() if info["critical"]]
    else:
        categories = None  # Run all
    
    # Run tests
    try:
        report = runner.run_all_tests(categories)
        exit_code = 0 if report["overall_success"] else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print(f"\\n\\n⚠️  Test suite interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        print(f"\\n\\n💥 Test suite runner error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()