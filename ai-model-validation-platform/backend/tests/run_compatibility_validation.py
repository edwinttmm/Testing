"""
Comprehensive Backward Compatibility Validation Runner

This script runs all backward compatibility tests and generates a detailed
validation report for the hybrid LabJack logging system.

Usage:
    python run_compatibility_validation.py [--verbose] [--output report.json]
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

import pytest
import subprocess


class CompatibilityValidationRunner:
    """Runs comprehensive backward compatibility validation tests"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {
            "validation_timestamp": datetime.now(timezone.utc).isoformat(),
            "test_suites": {},
            "summary": {
                "total_tests": 0,
                "passed_tests": 0,
                "failed_tests": 0,
                "skipped_tests": 0,
                "success_rate": 0.0
            },
            "compatibility_status": "UNKNOWN",
            "critical_failures": [],
            "warnings": [],
            "recommendations": []
        }
    
    def run_test_suite(self, test_file: str, suite_name: str) -> Dict[str, Any]:
        """Run a specific test suite and return results"""
        print(f"\n🧪 Running {suite_name}...")
        
        # Construct pytest command
        cmd = [
            sys.executable, "-m", "pytest", 
            test_file,
            "-v",
            "--tb=short",
            "--json-report", 
            "--json-report-file=/tmp/pytest_report.json"
        ]
        
        if not self.verbose:
            cmd.extend(["-q", "--tb=no"])
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd, 
                cwd=Path(__file__).parent,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per suite
            )
            
            duration = time.time() - start_time
            
            # Parse pytest JSON report if available
            report_data = {}
            try:
                with open("/tmp/pytest_report.json", "r") as f:
                    report_data = json.load(f)
            except FileNotFoundError:
                pass
            
            suite_result = {
                "suite_name": suite_name,
                "test_file": test_file,
                "duration_seconds": round(duration, 2),
                "return_code": result.returncode,
                "stdout": result.stdout if self.verbose else "",
                "stderr": result.stderr,
                "tests": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0
                },
                "status": "PASSED" if result.returncode == 0 else "FAILED"
            }
            
            # Extract test counts from pytest JSON report
            if "summary" in report_data:
                summary = report_data["summary"]
                suite_result["tests"] = {
                    "total": summary.get("total", 0),
                    "passed": summary.get("passed", 0),
                    "failed": summary.get("failed", 0),
                    "skipped": summary.get("skipped", 0)
                }
            
            # Extract individual test results
            if "tests" in report_data:
                suite_result["test_details"] = []
                for test in report_data["tests"]:
                    suite_result["test_details"].append({
                        "name": test.get("nodeid", ""),
                        "outcome": test.get("outcome", ""),
                        "duration": test.get("duration", 0),
                        "keywords": test.get("keywords", [])
                    })
            
            if result.returncode == 0:
                print(f"✅ {suite_name} - PASSED ({suite_result['tests']['total']} tests)")
            else:
                print(f"❌ {suite_name} - FAILED ({suite_result['tests']['failed']} failures)")
                if result.stderr:
                    print(f"   Error: {result.stderr[:200]}...")
            
            return suite_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {suite_name} - TIMEOUT (exceeded 5 minutes)")
            return {
                "suite_name": suite_name,
                "test_file": test_file,
                "duration_seconds": 300,
                "return_code": -1,
                "status": "TIMEOUT",
                "error": "Test suite exceeded timeout limit"
            }
        
        except Exception as e:
            print(f"💥 {suite_name} - ERROR: {e}")
            return {
                "suite_name": suite_name,
                "test_file": test_file,
                "duration_seconds": time.time() - start_time,
                "return_code": -2,
                "status": "ERROR",
                "error": str(e)
            }
    
    def run_all_compatibility_tests(self) -> Dict[str, Any]:
        """Run all backward compatibility test suites"""
        print("🔍 Starting Comprehensive Backward Compatibility Validation")
        print("=" * 60)
        
        test_suites = [
            {
                "file": "test_backward_compatibility.py",
                "name": "Core Backward Compatibility",
                "critical": True,
                "description": "Tests that existing HIL workflows remain unchanged"
            },
            {
                "file": "test_api_contract_validation.py", 
                "name": "API Contract Validation",
                "critical": True,
                "description": "Validates API endpoints maintain exact same contracts"
            },
            {
                "file": "test_database_schema_integrity.py",
                "name": "Database Schema Integrity",
                "critical": True,
                "description": "Ensures database schema changes don't break existing code"
            },
            {
                "file": "test_frontend_compatibility.py",
                "name": "Frontend Compatibility", 
                "critical": True,
                "description": "Tests HILResults.tsx and other frontend components"
            }
        ]
        
        total_start_time = time.time()
        
        for suite_config in test_suites:
            test_file = suite_config["file"]
            suite_name = suite_config["name"]
            
            # Check if test file exists
            test_path = Path(__file__).parent / test_file
            if not test_path.exists():
                print(f"⚠️  {suite_name} - Test file not found: {test_file}")
                self.results["test_suites"][suite_name] = {
                    "suite_name": suite_name,
                    "test_file": test_file,
                    "status": "NOT_FOUND",
                    "error": f"Test file {test_file} not found"
                }
                self.results["warnings"].append(f"Test suite '{suite_name}' not found")
                continue
            
            # Run the test suite
            suite_result = self.run_test_suite(str(test_path), suite_name)
            suite_result.update({
                "critical": suite_config["critical"],
                "description": suite_config["description"]
            })
            
            self.results["test_suites"][suite_name] = suite_result
            
            # Update summary counts
            if "tests" in suite_result:
                tests = suite_result["tests"]
                self.results["summary"]["total_tests"] += tests.get("total", 0)
                self.results["summary"]["passed_tests"] += tests.get("passed", 0)
                self.results["summary"]["failed_tests"] += tests.get("failed", 0)
                self.results["summary"]["skipped_tests"] += tests.get("skipped", 0)
            
            # Track critical failures
            if suite_config["critical"] and suite_result["status"] in ["FAILED", "ERROR", "TIMEOUT"]:
                self.results["critical_failures"].append({
                    "suite": suite_name,
                    "status": suite_result["status"],
                    "error": suite_result.get("error", "Test failures detected")
                })
        
        total_duration = time.time() - total_start_time
        self.results["total_duration_seconds"] = round(total_duration, 2)
        
        # Calculate success rate
        total = self.results["summary"]["total_tests"]
        passed = self.results["summary"]["passed_tests"]
        self.results["summary"]["success_rate"] = (passed / total * 100) if total > 0 else 0
        
        # Determine overall compatibility status
        self._determine_compatibility_status()
        
        return self.results
    
    def _determine_compatibility_status(self):
        """Determine overall compatibility status based on test results"""
        critical_failures = len(self.results["critical_failures"])
        success_rate = self.results["summary"]["success_rate"]
        
        if critical_failures == 0 and success_rate >= 95:
            self.results["compatibility_status"] = "FULLY_COMPATIBLE"
            self.results["recommendations"].append(
                "✅ All critical compatibility tests passed. System is safe for deployment."
            )
        elif critical_failures == 0 and success_rate >= 80:
            self.results["compatibility_status"] = "MOSTLY_COMPATIBLE"
            self.results["recommendations"].append(
                "⚠️  Most compatibility tests passed, but some minor issues detected. Review test failures."
            )
            self.results["warnings"].append("Some non-critical compatibility tests failed")
        elif critical_failures <= 2 and success_rate >= 60:
            self.results["compatibility_status"] = "PARTIALLY_COMPATIBLE"
            self.results["recommendations"].append(
                "🔶 Significant compatibility issues detected. Address critical failures before deployment."
            )
        else:
            self.results["compatibility_status"] = "INCOMPATIBLE"
            self.results["recommendations"].append(
                "❌ Major compatibility issues detected. System is NOT safe for deployment without fixes."
            )
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate comprehensive validation report"""
        report_lines = [
            "=" * 80,
            "🔍 BACKWARD COMPATIBILITY VALIDATION REPORT",
            "=" * 80,
            f"Generated: {self.results['validation_timestamp']}",
            f"Total Duration: {self.results.get('total_duration_seconds', 0):.1f} seconds",
            "",
            "📊 SUMMARY",
            "-" * 40,
            f"Overall Status: {self.results['compatibility_status']}",
            f"Total Tests: {self.results['summary']['total_tests']}",
            f"Passed: {self.results['summary']['passed_tests']}",
            f"Failed: {self.results['summary']['failed_tests']}",
            f"Skipped: {self.results['summary']['skipped_tests']}",
            f"Success Rate: {self.results['summary']['success_rate']:.1f}%",
            ""
        ]
        
        # Critical failures
        if self.results["critical_failures"]:
            report_lines.extend([
                "🚨 CRITICAL FAILURES",
                "-" * 40
            ])
            for failure in self.results["critical_failures"]:
                report_lines.append(f"❌ {failure['suite']}: {failure['status']}")
                if "error" in failure:
                    report_lines.append(f"   Error: {failure['error']}")
            report_lines.append("")
        
        # Test suite details
        report_lines.extend([
            "📋 TEST SUITE DETAILS",
            "-" * 40
        ])
        
        for suite_name, suite_result in self.results["test_suites"].items():
            status_icon = {
                "PASSED": "✅",
                "FAILED": "❌", 
                "ERROR": "💥",
                "TIMEOUT": "⏰",
                "NOT_FOUND": "⚠️"
            }.get(suite_result["status"], "❓")
            
            report_lines.append(f"{status_icon} {suite_name}: {suite_result['status']}")
            
            if "description" in suite_result:
                report_lines.append(f"   {suite_result['description']}")
            
            if "tests" in suite_result:
                tests = suite_result["tests"]
                report_lines.append(
                    f"   Tests: {tests['total']} total, {tests['passed']} passed, "
                    f"{tests['failed']} failed, {tests['skipped']} skipped"
                )
            
            if "duration_seconds" in suite_result:
                report_lines.append(f"   Duration: {suite_result['duration_seconds']:.1f}s")
            
            if suite_result.get("critical", False):
                report_lines.append("   🔴 CRITICAL TEST SUITE")
            
            report_lines.append("")
        
        # Warnings
        if self.results["warnings"]:
            report_lines.extend([
                "⚠️  WARNINGS",
                "-" * 40
            ])
            for warning in self.results["warnings"]:
                report_lines.append(f"⚠️  {warning}")
            report_lines.append("")
        
        # Recommendations
        if self.results["recommendations"]:
            report_lines.extend([
                "💡 RECOMMENDATIONS",
                "-" * 40
            ])
            for rec in self.results["recommendations"]:
                report_lines.append(rec)
            report_lines.append("")
        
        report_lines.extend([
            "=" * 80,
            "End of Report",
            "=" * 80
        ])
        
        report_content = "\n".join(report_lines)
        
        # Save to file if requested
        if output_file:
            try:
                with open(output_file, "w") as f:
                    if output_file.endswith(".json"):
                        json.dump(self.results, f, indent=2)
                    else:
                        f.write(report_content)
                print(f"\n📄 Report saved to: {output_file}")
            except Exception as e:
                print(f"❌ Failed to save report to {output_file}: {e}")
        
        return report_content
    
    def get_exit_code(self) -> int:
        """Get appropriate exit code based on validation results"""
        if self.results["compatibility_status"] == "FULLY_COMPATIBLE":
            return 0
        elif self.results["compatibility_status"] in ["MOSTLY_COMPATIBLE", "PARTIALLY_COMPATIBLE"]:
            return 1
        else:
            return 2


def main():
    """Main entry point for compatibility validation"""
    parser = argparse.ArgumentParser(
        description="Run comprehensive backward compatibility validation for hybrid LabJack system"
    )
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for validation report (supports .txt or .json)"
    )
    parser.add_argument(
        "--json-only",
        action="store_true", 
        help="Output only JSON results (for CI/CD integration)"
    )
    
    args = parser.parse_args()
    
    # Create validation runner
    runner = CompatibilityValidationRunner(verbose=args.verbose)
    
    try:
        # Run all tests
        results = runner.run_all_compatibility_tests()
        
        if args.json_only:
            # Output JSON for CI/CD
            print(json.dumps(results, indent=2))
        else:
            # Generate and display report
            report = runner.generate_report(args.output)
            print(report)
        
        # Exit with appropriate code
        sys.exit(runner.get_exit_code())
        
    except KeyboardInterrupt:
        print("\n🛑 Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()