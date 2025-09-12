"""
Video Validation Test Suite Runner
==================================

Comprehensive test runner for all video validation status tests.
Validates test coverage and integration with existing test infrastructure.
"""

import pytest
import sys
import os
from pathlib import Path
import subprocess
import json
import time
from typing import Dict, List, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class VideoValidationTestSuite:
    """Test suite coordinator for video validation tests"""
    
    def __init__(self):
        self.test_results = {}
        self.coverage_data = {}
        self.test_directories = {
            "unit": Path(__file__).parent / "unit",
            "integration": Path(__file__).parent / "integration", 
            "e2e": Path(__file__).parent / "e2e",
            "frontend": Path(__file__).parent / "frontend",
            "migration": Path(__file__).parent / "migration",
            "performance": Path(__file__).parent / "performance"
        }
    
    def run_test_category(self, category: str, verbose: bool = True) -> Dict[str, Any]:
        """Run tests for a specific category"""
        if category not in self.test_directories:
            raise ValueError(f"Unknown test category: {category}")
        
        test_dir = self.test_directories[category]
        if not test_dir.exists():
            return {"error": f"Test directory does not exist: {test_dir}"}
        
        print(f"\n{'='*50}")
        print(f"Running {category.upper()} tests")
        print(f"{'='*50}")
        
        # Build pytest command
        cmd = [
            "python", "-m", "pytest",
            str(test_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "--durations=10",
            f"--junitxml=test-results-{category}.xml",
            f"--cov=.",
            f"--cov-report=json:coverage-{category}.json",
            "--cov-report=term-missing"
        ]
        
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_root,
                timeout=600  # 10 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            return {
                "category": category,
                "exit_code": result.returncode,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {
                "category": category,
                "error": "Test execution timed out",
                "success": False
            }
        except Exception as e:
            return {
                "category": category,
                "error": str(e),
                "success": False
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test categories"""
        print("Starting comprehensive video validation test suite")
        print(f"Test categories: {list(self.test_directories.keys())}")
        
        overall_start = time.time()
        results = {}
        
        # Run each test category
        for category in self.test_directories.keys():
            print(f"\n[{category.upper()}] Starting tests...")
            result = self.run_test_category(category)
            results[category] = result
            
            if result.get("success"):
                print(f"[{category.upper()}] ✅ PASSED ({result.get('duration', 0):.2f}s)")
            else:
                print(f"[{category.upper()}] ❌ FAILED")
                if result.get("stderr"):
                    print(f"Error: {result['stderr'][:200]}...")
        
        overall_duration = time.time() - overall_start
        
        # Generate summary
        summary = self._generate_test_summary(results, overall_duration)
        
        return {
            "results": results,
            "summary": summary,
            "overall_success": all(r.get("success", False) for r in results.values())
        }
    
    def _generate_test_summary(self, results: Dict[str, Any], duration: float) -> Dict[str, Any]:
        """Generate test execution summary"""
        total_categories = len(results)
        passed_categories = sum(1 for r in results.values() if r.get("success", False))
        failed_categories = total_categories - passed_categories
        
        summary = {
            "total_duration": duration,
            "total_categories": total_categories,
            "passed_categories": passed_categories,
            "failed_categories": failed_categories,
            "success_rate": (passed_categories / total_categories) * 100,
            "category_details": {}
        }
        
        for category, result in results.items():
            summary["category_details"][category] = {
                "success": result.get("success", False),
                "duration": result.get("duration", 0),
                "error": result.get("error", ""),
                "exit_code": result.get("exit_code", -1)
            }
        
        return summary
    
    def validate_test_coverage(self) -> Dict[str, Any]:
        """Validate test coverage for video validation functionality"""
        print("\nValidating test coverage...")
        
        coverage_files = []
        for category in self.test_directories.keys():
            coverage_file = f"coverage-{category}.json"
            if os.path.exists(coverage_file):
                coverage_files.append(coverage_file)
        
        if not coverage_files:
            return {"error": "No coverage files found"}
        
        # Analyze coverage data
        coverage_analysis = self._analyze_coverage(coverage_files)
        
        return coverage_analysis
    
    def _analyze_coverage(self, coverage_files: List[str]) -> Dict[str, Any]:
        """Analyze test coverage from coverage files"""
        total_statements = 0
        covered_statements = 0
        file_coverage = {}
        
        for coverage_file in coverage_files:
            try:
                with open(coverage_file, 'r') as f:
                    data = json.load(f)
                
                if 'files' in data:
                    for file_path, file_data in data['files'].items():
                        # Focus on video validation related files
                        if self._is_video_validation_file(file_path):
                            if file_path not in file_coverage:
                                file_coverage[file_path] = {
                                    "statements": file_data.get('summary', {}).get('num_statements', 0),
                                    "covered": file_data.get('summary', {}).get('covered_lines', 0),
                                    "missing_lines": file_data.get('missing_lines', [])
                                }
                                total_statements += file_coverage[file_path]["statements"]
                                covered_statements += file_coverage[file_path]["covered"]
            
            except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                print(f"Warning: Could not process coverage file {coverage_file}: {e}")
        
        overall_coverage = (covered_statements / total_statements * 100) if total_statements > 0 else 0
        
        return {
            "overall_coverage": overall_coverage,
            "total_statements": total_statements,
            "covered_statements": covered_statements,
            "file_coverage": file_coverage,
            "coverage_goal": 80.0,  # Target 80% coverage
            "meets_goal": overall_coverage >= 80.0
        }
    
    def _is_video_validation_file(self, file_path: str) -> bool:
        """Check if file is related to video validation functionality"""
        video_validation_patterns = [
            "video",
            "validation",
            "status",
            "ground_truth",
            "hil",
            "crud",
            "models",
            "schemas"
        ]
        
        file_path_lower = file_path.lower()
        return any(pattern in file_path_lower for pattern in video_validation_patterns)
    
    def check_test_infrastructure_integration(self) -> Dict[str, Any]:
        """Check integration with existing test infrastructure"""
        print("\nChecking test infrastructure integration...")
        
        checks = {
            "pytest_config": self._check_pytest_config(),
            "database_fixtures": self._check_database_fixtures(),
            "test_dependencies": self._check_test_dependencies(),
            "existing_tests_compatibility": self._check_existing_tests_compatibility()
        }
        
        all_passed = all(check["passed"] for check in checks.values())
        
        return {
            "all_checks_passed": all_passed,
            "individual_checks": checks
        }
    
    def _check_pytest_config(self) -> Dict[str, Any]:
        """Check pytest configuration"""
        config_files = ["pytest.ini", "pyproject.toml", "setup.cfg"]
        found_config = None
        
        for config_file in config_files:
            config_path = project_root / config_file
            if config_path.exists():
                found_config = config_file
                break
        
        return {
            "passed": found_config is not None,
            "config_file": found_config,
            "message": f"Found pytest config: {found_config}" if found_config else "No pytest config found"
        }
    
    def _check_database_fixtures(self) -> Dict[str, Any]:
        """Check database test fixtures"""
        conftest_path = project_root / "tests" / "conftest.py"
        has_conftest = conftest_path.exists()
        
        db_fixtures_found = []
        if has_conftest:
            try:
                with open(conftest_path, 'r') as f:
                    content = f.read()
                    if "test_db" in content or "db_session" in content:
                        db_fixtures_found.append("database_session")
                    if "TestClient" in content:
                        db_fixtures_found.append("test_client")
            except Exception as e:
                pass
        
        return {
            "passed": has_conftest and len(db_fixtures_found) > 0,
            "conftest_exists": has_conftest,
            "fixtures_found": db_fixtures_found,
            "message": f"Found {len(db_fixtures_found)} database fixtures" if db_fixtures_found else "No database fixtures found"
        }
    
    def _check_test_dependencies(self) -> Dict[str, Any]:
        """Check required test dependencies"""
        required_packages = [
            "pytest", "pytest-asyncio", "pytest-cov",
            "fastapi", "sqlalchemy", "requests"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace("-", "_"))
            except ImportError:
                missing_packages.append(package)
        
        return {
            "passed": len(missing_packages) == 0,
            "required_packages": required_packages,
            "missing_packages": missing_packages,
            "message": f"All dependencies available" if not missing_packages else f"Missing: {missing_packages}"
        }
    
    def _check_existing_tests_compatibility(self) -> Dict[str, Any]:
        """Check compatibility with existing tests"""
        existing_test_files = list(Path(project_root / "tests").glob("test_*.py"))
        
        compatibility_issues = []
        
        # Check for naming conflicts
        new_test_names = [
            "test_video_status_transitions.py",
            "test_video_validation_api.py", 
            "test_video_validation_workflow.py",
            "test_video_filtering_frontend.py",
            "test_video_status_migration.py",
            "test_video_validation_performance.py",
            "test_video_status_error_handling.py"
        ]
        
        for test_file in existing_test_files:
            if test_file.name in new_test_names:
                compatibility_issues.append(f"Naming conflict: {test_file.name}")
        
        return {
            "passed": len(compatibility_issues) == 0,
            "existing_test_count": len(existing_test_files),
            "compatibility_issues": compatibility_issues,
            "message": "No compatibility issues" if not compatibility_issues else f"Issues found: {compatibility_issues}"
        }
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """Generate comprehensive test report"""
        report_lines = [
            "# Video Validation Test Suite Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Executive Summary",
            f"- **Overall Success**: {'✅ PASSED' if results.get('overall_success') else '❌ FAILED'}",
            f"- **Total Duration**: {results.get('summary', {}).get('total_duration', 0):.2f}s",
            f"- **Categories Tested**: {results.get('summary', {}).get('total_categories', 0)}",
            f"- **Success Rate**: {results.get('summary', {}).get('success_rate', 0):.1f}%",
            "",
            "## Test Categories",
        ]
        
        if "summary" in results and "category_details" in results["summary"]:
            for category, details in results["summary"]["category_details"].items():
                status = "✅ PASSED" if details["success"] else "❌ FAILED"
                duration = details.get("duration", 0)
                report_lines.append(f"- **{category.title()}**: {status} ({duration:.2f}s)")
        
        report_lines.extend([
            "",
            "## Coverage Analysis",
        ])
        
        # Add coverage information if available
        coverage_data = self.validate_test_coverage()
        if "overall_coverage" in coverage_data:
            coverage_pct = coverage_data["overall_coverage"]
            meets_goal = coverage_data.get("meets_goal", False)
            status = "✅ MEETS GOAL" if meets_goal else "⚠️ BELOW TARGET"
            
            report_lines.extend([
                f"- **Overall Coverage**: {coverage_pct:.1f}% {status}",
                f"- **Statements Covered**: {coverage_data.get('covered_statements', 0)}/{coverage_data.get('total_statements', 0)}",
                f"- **Target Coverage**: {coverage_data.get('coverage_goal', 80)}%"
            ])
        
        report_lines.extend([
            "",
            "## Infrastructure Integration",
        ])
        
        # Add infrastructure check results
        infra_checks = self.check_test_infrastructure_integration()
        if "individual_checks" in infra_checks:
            for check_name, check_result in infra_checks["individual_checks"].items():
                status = "✅ PASSED" if check_result["passed"] else "❌ FAILED"
                message = check_result.get("message", "")
                report_lines.append(f"- **{check_name.replace('_', ' ').title()}**: {status} - {message}")
        
        return "\n".join(report_lines)


def main():
    """Main test runner function"""
    print("🧪 Video Validation Comprehensive Test Suite")
    print("=" * 60)
    
    suite = VideoValidationTestSuite()
    
    # Run all tests
    results = suite.run_all_tests()
    
    # Generate and save report
    report = suite.generate_test_report(results)
    
    report_file = "video_validation_test_report.md"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n📋 Test report saved to: {report_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUITE SUMMARY")
    print("=" * 60)
    print(report.split("## Test Categories")[0])  # Print only executive summary
    
    # Exit with appropriate code
    exit_code = 0 if results.get("overall_success") else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()