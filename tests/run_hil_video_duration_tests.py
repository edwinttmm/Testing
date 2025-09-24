#!/usr/bin/env python3
"""
HIL Video Duration Auto-Stop Test Runner

Comprehensive test runner for validating the HIL video duration auto-stop system.
This runner executes all test suites with detailed reporting and validation.

Features:
- Runs all duration resolution tests
- Validates LabJack auto-stop timer calculations  
- Tests database fallback scenarios
- Integration testing with HIL components
- Detailed test reporting with timing metrics
- Failure analysis and debugging information

Usage:
    python run_hil_video_duration_tests.py [--verbose] [--category=<category>] [--output=<file>]
"""

import sys
import os
import unittest
import time
import json
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from io import StringIO
import traceback

# Add the test directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

# Import test modules
from test_hil_video_duration import (
    TestGetVideoDuration,
    TestLabJackAutoStopTiming, 
    TestHILVideoTimingIntegration,
    TestDatabaseFallbackScenarios,
    TestVideoTimingServiceDurationHandling,
    TestErrorHandlingAndValidation,
    TestLabJackAutoStopEndToEnd
)

from test_hil_video_duration_fixtures import (
    VideoFixtureFactory,
    GracePeriodCalculator,
    TestScenarioBuilder
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class HILDurationTestResult(unittest.TestResult):
    """Custom test result class for detailed reporting"""
    
    def __init__(self):
        super().__init__()
        self.test_results = []
        self.start_time = None
        self.end_time = None
        self.total_duration = 0
    
    def startTest(self, test):
        super().startTest(test)
        self.start_time = time.time()
    
    def stopTest(self, test):
        super().stopTest(test)
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        self.total_duration += duration
        
        # Record test result
        result = {
            "test_name": str(test),
            "class_name": test.__class__.__name__,
            "method_name": test._testMethodName,
            "duration": duration,
            "status": "PASS",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.test_results.append(result)
    
    def addError(self, test, err):
        super().addError(test, err)
        self._update_test_result(test, "ERROR", err)
    
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._update_test_result(test, "FAIL", err)
    
    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._update_test_result(test, "SKIP", reason)
    
    def _update_test_result(self, test, status, details):
        """Update the last test result with error/failure information"""
        if self.test_results:
            last_result = self.test_results[-1]
            if str(test) == last_result["test_name"]:
                last_result["status"] = status
                if isinstance(details, tuple):
                    last_result["error_type"] = details[0].__name__
                    last_result["error_message"] = str(details[1])
                    last_result["traceback"] = ''.join(traceback.format_exception(*details))
                else:
                    last_result["skip_reason"] = str(details)


class HILDurationTestRunner:
    """Main test runner for HIL video duration tests"""
    
    def __init__(self, verbose: bool = False, output_file: Optional[str] = None):
        self.verbose = verbose
        self.output_file = output_file
        self.test_results = None
        self.total_start_time = None
        self.total_end_time = None
    
    def run_all_tests(self, test_category: Optional[str] = None) -> Dict[str, Any]:
        """Run all HIL duration tests with comprehensive reporting"""
        logger.info("Starting HIL Video Duration Auto-Stop Test Suite")
        logger.info("=" * 80)
        
        self.total_start_time = time.time()
        
        # Create test suite
        test_suite = self._build_test_suite(test_category)
        
        # Run tests with custom result collector
        self.test_results = HILDurationTestResult()
        
        if self.verbose:
            runner = unittest.TextTestRunner(
                verbosity=2,
                stream=sys.stdout,
                resultclass=lambda: self.test_results
            )
        else:
            # Capture output for clean reporting
            test_output = StringIO()
            runner = unittest.TextTestRunner(
                verbosity=1,
                stream=test_output,
                resultclass=lambda: self.test_results
            )
        
        # Execute test suite
        result = runner.run(test_suite)
        
        self.total_end_time = time.time()
        
        # Generate comprehensive report
        report = self._generate_report(result)
        
        # Output report
        self._output_report(report)
        
        return report
    
    def _build_test_suite(self, category: Optional[str] = None) -> unittest.TestSuite:
        """Build test suite based on category filter"""
        suite = unittest.TestSuite()
        
        # Define test categories
        test_categories = {
            "duration_resolution": [TestGetVideoDuration],
            "auto_stop_timing": [TestLabJackAutoStopTiming],
            "integration": [TestHILVideoTimingIntegration],
            "database_fallback": [TestDatabaseFallbackScenarios],
            "timing_service": [TestVideoTimingServiceDurationHandling],
            "error_handling": [TestErrorHandlingAndValidation],
            "end_to_end": [TestLabJackAutoStopEndToEnd]
        }
        
        if category and category in test_categories:
            test_classes = test_categories[category]
            logger.info(f"Running tests for category: {category}")
        else:
            # Run all test categories
            test_classes = []
            for classes in test_categories.values():
                test_classes.extend(classes)
            logger.info("Running all test categories")
        
        # Add test classes to suite
        for test_class in test_classes:
            tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
            suite.addTests(tests)
        
        return suite
    
    def _generate_report(self, result: unittest.TestResult) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_duration = self.total_end_time - self.total_start_time
        
        # Calculate statistics
        total_tests = result.testsRun
        errors = len(result.errors)
        failures = len(result.failures)
        skipped = len(result.skipped) if hasattr(result, 'skipped') else 0
        passed = total_tests - errors - failures - skipped
        success_rate = (passed / total_tests * 100) if total_tests > 0 else 0
        
        # Categorize test results
        results_by_category = {}
        for test_result in self.test_results.test_results:
            class_name = test_result["class_name"]
            if class_name not in results_by_category:
                results_by_category[class_name] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "errors": 0,
                    "skipped": 0,
                    "duration": 0
                }
            
            category_stats = results_by_category[class_name]
            category_stats["total"] += 1
            category_stats["duration"] += test_result["duration"]
            
            if test_result["status"] == "PASS":
                category_stats["passed"] += 1
            elif test_result["status"] == "FAIL":
                category_stats["failed"] += 1
            elif test_result["status"] == "ERROR":
                category_stats["errors"] += 1
            elif test_result["status"] == "SKIP":
                category_stats["skipped"] += 1
        
        # Generate fixture validation report
        fixture_report = self._validate_test_fixtures()
        
        # Generate timing analysis
        timing_analysis = self._analyze_test_timing()
        
        # Build comprehensive report
        report = {
            "test_run_info": {
                "start_time": datetime.fromtimestamp(self.total_start_time, timezone.utc).isoformat(),
                "end_time": datetime.fromtimestamp(self.total_end_time, timezone.utc).isoformat(),
                "total_duration": total_duration,
                "test_runner_version": "1.0.0"
            },
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failures,
                "errors": errors,
                "skipped": skipped,
                "success_rate": success_rate
            },
            "categories": results_by_category,
            "detailed_results": self.test_results.test_results,
            "fixture_validation": fixture_report,
            "timing_analysis": timing_analysis,
            "validation_report": self._generate_validation_summary()
        }
        
        return report
    
    def _validate_test_fixtures(self) -> Dict[str, Any]:
        """Validate test fixtures and generate fixture report"""
        logger.info("Validating test fixtures...")
        
        # Get all fixtures
        all_fixtures = VideoFixtureFactory.get_all_fixtures()
        
        fixture_stats = {}
        total_fixtures = 0
        valid_fixtures = 0
        
        for category, fixtures in all_fixtures.items():
            category_stats = {
                "count": len(fixtures),
                "valid": 0,
                "invalid": 0,
                "duration_range": {"min": float('inf'), "max": 0}
            }
            
            for fixture in fixtures:
                total_fixtures += 1
                
                # Validate fixture
                is_valid = True
                if fixture.duration is not None:
                    if fixture.duration <= 0 or fixture.duration > 7200:
                        is_valid = False
                    else:
                        category_stats["duration_range"]["min"] = min(
                            category_stats["duration_range"]["min"], 
                            fixture.duration
                        )
                        category_stats["duration_range"]["max"] = max(
                            category_stats["duration_range"]["max"], 
                            fixture.duration
                        )
                
                if is_valid:
                    category_stats["valid"] += 1
                    valid_fixtures += 1
                else:
                    category_stats["invalid"] += 1
            
            # Handle case where no valid durations were found
            if category_stats["duration_range"]["min"] == float('inf'):
                category_stats["duration_range"]["min"] = 0
            
            fixture_stats[category] = category_stats
        
        return {
            "total_fixtures": total_fixtures,
            "valid_fixtures": valid_fixtures,
            "invalid_fixtures": total_fixtures - valid_fixtures,
            "categories": fixture_stats
        }
    
    def _analyze_test_timing(self) -> Dict[str, Any]:
        """Analyze test execution timing patterns"""
        if not self.test_results.test_results:
            return {}
        
        durations = [r["duration"] for r in self.test_results.test_results]
        
        return {
            "total_test_duration": sum(durations),
            "average_test_duration": sum(durations) / len(durations),
            "fastest_test": min(durations),
            "slowest_test": max(durations),
            "tests_by_duration": sorted([
                {"test": r["test_name"], "duration": r["duration"]}
                for r in self.test_results.test_results
            ], key=lambda x: x["duration"], reverse=True)[:5]  # Top 5 slowest
        }
    
    def _generate_validation_summary(self) -> Dict[str, Any]:
        """Generate validation summary for HIL auto-stop functionality"""
        # Test grace period calculations
        grace_scenarios = GracePeriodCalculator.get_grace_period_test_cases()
        
        validation_tests = {
            "grace_period_calculations": {
                "total_scenarios": len(grace_scenarios),
                "min_grace": 0.25,
                "max_grace": 2.0,
                "calculation_formula": "max(0.25, min(2.0, duration * 0.05))"
            },
            "duration_sources": {
                "primary": "video_data['duration_s']",
                "fallback1": "video_data['duration']",
                "fallback2": "database Video.duration",
                "validation": "0.1 <= duration <= 7200 seconds"
            },
            "auto_stop_timing": {
                "formula": "auto_stop_time = video_duration + grace_period",
                "purpose": "Prevent early LabJack monitoring termination",
                "detection_window": "Video duration + grace period"
            }
        }
        
        return validation_tests
    
    def _output_report(self, report: Dict[str, Any]):
        """Output the test report"""
        # Print summary to console
        self._print_summary_report(report)
        
        # Save detailed report to file if specified
        if self.output_file:
            self._save_detailed_report(report)
    
    def _print_summary_report(self, report: Dict[str, Any]):
        """Print summary report to console"""
        print("\n" + "=" * 80)
        print("HIL VIDEO DURATION AUTO-STOP TEST RESULTS")
        print("=" * 80)
        
        summary = report["summary"]
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed']}")
        print(f"Failed: {summary['failed']}")
        print(f"Errors: {summary['errors']}")
        print(f"Skipped: {summary['skipped']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        print(f"\nExecution Time: {report['test_run_info']['total_duration']:.2f} seconds")
        
        # Print category breakdown
        print("\nTest Categories:")
        print("-" * 40)
        for category, stats in report["categories"].items():
            success_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            print(f"{category:30} {stats['passed']}/{stats['total']} ({success_rate:.1f}%)")
        
        # Print fixture validation
        fixture = report["fixture_validation"]
        print(f"\nTest Fixtures: {fixture['valid_fixtures']}/{fixture['total_fixtures']} valid")
        
        # Print validation summary
        print("\nValidation Summary:")
        print("-" * 40)
        validation = report["validation_report"]
        print(f"Grace Period Range: {validation['grace_period_calculations']['min_grace']}s - {validation['grace_period_calculations']['max_grace']}s")
        print(f"Duration Sources: {len(validation['duration_sources'])} fallback levels")
        print(f"Auto-Stop Formula: {validation['auto_stop_timing']['formula']}")
        
        if summary["failed"] > 0 or summary["errors"] > 0:
            print(f"\n❌ TESTS FAILED - Review detailed results for debugging")
        else:
            print(f"\n✅ ALL TESTS PASSED - HIL auto-stop system validated")
    
    def _save_detailed_report(self, report: Dict[str, Any]):
        """Save detailed report to JSON file"""
        try:
            with open(self.output_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Detailed test report saved to: {self.output_file}")
        except Exception as e:
            logger.error(f"Failed to save report to {self.output_file}: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="HIL Video Duration Auto-Stop Test Runner")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--category", "-c", help="Test category to run")
    parser.add_argument("--output", "-o", help="Output file for detailed report")
    parser.add_argument("--list-categories", action="store_true", help="List available test categories")
    
    args = parser.parse_args()
    
    if args.list_categories:
        print("Available test categories:")
        print("- duration_resolution: Test video duration resolution from various sources")
        print("- auto_stop_timing: Test LabJack auto-stop timer calculations")
        print("- integration: Test integration with HIL components")
        print("- database_fallback: Test database fallback scenarios")
        print("- timing_service: Test video timing service integration")
        print("- error_handling: Test error handling and validation")
        print("- end_to_end: Test complete auto-stop workflow")
        return
    
    # Create and run test runner
    runner = HILDurationTestRunner(
        verbose=args.verbose,
        output_file=args.output
    )
    
    try:
        report = runner.run_all_tests(test_category=args.category)
        
        # Exit with non-zero code if tests failed
        if report["summary"]["failed"] > 0 or report["summary"]["errors"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Test runner failed: {e}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()