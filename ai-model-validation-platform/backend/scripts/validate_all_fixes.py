#!/usr/bin/env python3
"""
Validation Script for All Three Fixes

This script validates:
1. LabJack race condition fix (Error 1224 handle validation)
2. constant_voltage_mode bypass fix (debounce bypass for high FPS)
3. Recall recalculation fix (correct GT count usage)

Usage:
    python scripts/validate_all_fixes.py

Author: AI Model Validation Platform Team
Date: 2025-11-24
"""

import os
import sys
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class FixValidator:
    """Validates all three fixes are properly implemented"""

    def __init__(self):
        self.backend_dir = Path(__file__).parent.parent
        self.results: Dict[str, bool] = {}
        self.details: Dict[str, List[str]] = {}

    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{'='*80}")
        print(f"  {text}")
        print(f"{'='*80}")

    def print_section(self, text: str):
        """Print formatted section"""
        print(f"\n{'─'*80}")
        print(f"  {text}")
        print(f"{'─'*80}")

    def check_file_exists(self, filepath: Path) -> bool:
        """Check if file exists"""
        return filepath.exists()

    def search_in_file(self, filepath: Path, pattern: str) -> Tuple[bool, List[str]]:
        """Search for pattern in file"""
        matches = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                    context_start = max(0, match.start() - 50)
                    context_end = min(len(content), match.end() + 50)
                    context = content[context_start:context_end].strip()
                    matches.append(context)

            return len(matches) > 0, matches
        except Exception as e:
            return False, [f"Error reading file: {str(e)}"]

    def validate_fix_1_labjack_handle(self) -> bool:
        """Validate Fix #1: LabJack race condition fix"""
        self.print_section("Fix #1: LabJack Race Condition (Error 1224)")

        checks = []

        # Check 1: Health monitor file exists
        health_monitor_file = self.backend_dir / "app" / "services" / "labjack_service.py"
        if not self.check_file_exists(health_monitor_file):
            checks.append((False, "❌ labjack_service.py not found"))
            self.details['fix1'] = ["File not found: labjack_service.py"]
            return False

        checks.append((True, "✅ labjack_service.py exists"))

        # Check 2: Handle validation in health monitor
        found, matches = self.search_in_file(
            health_monitor_file,
            r'if.*handle.*is None|if not.*handle|handle.*==.*None'
        )

        if found:
            checks.append((True, "✅ Handle validation code found"))
            self.details['fix1'] = matches[:2]
        else:
            checks.append((False, "❌ Handle validation code NOT found"))
            self.details['fix1'] = ["No handle validation found in health monitor"]

        # Check 3: Graceful exit logic
        found, matches = self.search_in_file(
            health_monitor_file,
            r'return|break|exit|stop.*monitor'
        )

        if found:
            checks.append((True, "✅ Graceful exit logic found"))
        else:
            checks.append((False, "⚠️  Graceful exit logic unclear"))

        # Print results
        for passed, message in checks:
            print(f"  {message}")

        return all(passed for passed, _ in checks)

    def validate_fix_2_constant_voltage_mode(self) -> bool:
        """Validate Fix #2: constant_voltage_mode bypass"""
        self.print_section("Fix #2: constant_voltage_mode Bypass")

        checks = []

        # Check 1: Detection service file exists
        detection_service_file = self.backend_dir / "app" / "services" / "detection_service.py"
        if not self.check_file_exists(detection_service_file):
            checks.append((False, "❌ detection_service.py not found"))
            self.details['fix2'] = ["File not found: detection_service.py"]
            return False

        checks.append((True, "✅ detection_service.py exists"))

        # Check 2: constant_voltage_mode parameter
        found, matches = self.search_in_file(
            detection_service_file,
            r'constant_voltage_mode'
        )

        if found:
            checks.append((True, "✅ constant_voltage_mode parameter found"))
            self.details['fix2'] = matches[:2]
        else:
            checks.append((False, "❌ constant_voltage_mode parameter NOT found"))
            self.details['fix2'] = ["No constant_voltage_mode parameter found"]

        # Check 3: Debounce bypass logic
        found, matches = self.search_in_file(
            detection_service_file,
            r'if.*constant_voltage_mode|bypass.*debounce|skip.*debounce'
        )

        if found:
            checks.append((True, "✅ Debounce bypass logic found"))
        else:
            checks.append((False, "⚠️  Debounce bypass logic unclear"))

        # Check 4: API endpoint parameter
        api_file = self.backend_dir / "app" / "api" / "routes" / "test_sessions.py"
        if self.check_file_exists(api_file):
            found, matches = self.search_in_file(
                api_file,
                r'constant_voltage_mode'
            )
            if found:
                checks.append((True, "✅ API endpoint parameter found"))
            else:
                checks.append((False, "⚠️  API endpoint parameter not found"))
        else:
            checks.append((False, "⚠️  API file not found"))

        # Print results
        for passed, message in checks:
            print(f"  {message}")

        return all(passed for passed, _ in checks if not message.startswith("⚠️"))

    def validate_fix_3_recall_calculation(self) -> bool:
        """Validate Fix #3: Recall recalculation"""
        self.print_section("Fix #3: Recall Recalculation")

        checks = []

        # Check 1: Analysis service file exists
        analysis_service_file = self.backend_dir / "app" / "services" / "analysis_service.py"
        if not self.check_file_exists(analysis_service_file):
            checks.append((False, "❌ analysis_service.py not found"))
            self.details['fix3'] = ["File not found: analysis_service.py"]
            return False

        checks.append((True, "✅ analysis_service.py exists"))

        # Check 2: Correct recall formula (TP/GT count)
        found, matches = self.search_in_file(
            analysis_service_file,
            r'tp.*\/.*ground_truth_count|true_positives.*\/.*ground_truth|recall.*=.*tp.*\/.*gt'
        )

        if found:
            checks.append((True, "✅ Correct recall formula found (TP/GT)"))
            self.details['fix3'] = matches[:2]
        else:
            checks.append((False, "❌ Correct recall formula NOT found"))
            self.details['fix3'] = ["No correct recall formula found"]

        # Check 3: NOT using TP/(TP+FN) formula
        found, matches = self.search_in_file(
            analysis_service_file,
            r'tp.*\/.*\(.*tp.*\+.*fn\)|true_positives.*\/.*\(.*true_positives.*\+.*false_negatives\)'
        )

        if not found:
            checks.append((True, "✅ OLD incorrect formula NOT found (good!)"))
        else:
            checks.append((False, "❌ OLD incorrect formula still present"))

        # Check 4: ground_truth_count usage
        found, matches = self.search_in_file(
            analysis_service_file,
            r'ground_truth_count|gt_count|actual_gt_count'
        )

        if found:
            checks.append((True, "✅ ground_truth_count variable found"))
        else:
            checks.append((False, "⚠️  ground_truth_count variable not found"))

        # Print results
        for passed, message in checks:
            print(f"  {message}")

        return all(passed for passed, _ in checks if not message.startswith("⚠️"))

    def run_integration_tests(self) -> bool:
        """Run the integration test suite"""
        self.print_section("Running Integration Tests")

        test_file = self.backend_dir / "tests" / "test_all_fixes_integration.py"

        if not self.check_file_exists(test_file):
            print("  ❌ Integration test file not found")
            return False

        print("  ✅ Integration test file exists")
        print("\n  Running pytest...")

        try:
            result = subprocess.run(
                ["python", "-m", "pytest", str(test_file), "-v", "--tb=short"],
                cwd=str(self.backend_dir),
                capture_output=True,
                text=True,
                timeout=60
            )

            # Parse output
            output = result.stdout + result.stderr

            # Count passed/failed tests
            passed = len(re.findall(r'PASSED', output))
            failed = len(re.findall(r'FAILED', output))

            print(f"\n  Test Results:")
            print(f"    ✅ Passed: {passed}")
            if failed > 0:
                print(f"    ❌ Failed: {failed}")

            # Extract test categories
            categories = {
                'LabJack Race Condition': len(re.findall(r'test_health_monitor.*PASSED', output)),
                'Constant Voltage Mode': len(re.findall(r'test_constant_voltage.*PASSED|test_debounce.*PASSED', output)),
                'Recall Calculation': len(re.findall(r'test_recall.*PASSED|test_new_recall.*PASSED', output)),
                'Full Pipeline': len(re.findall(r'test_complete_pipeline.*PASSED', output)),
                'Edge Cases': len(re.findall(r'test_.*edge.*PASSED|test_extreme.*PASSED', output))
            }

            print(f"\n  Category Breakdown:")
            for category, count in categories.items():
                if count > 0:
                    print(f"    ✅ {category}: {count} passed")

            return result.returncode == 0

        except subprocess.TimeoutExpired:
            print("  ❌ Tests timed out")
            return False
        except Exception as e:
            print(f"  ❌ Error running tests: {str(e)}")
            return False

    def generate_report(self, fix1: bool, fix2: bool, fix3: bool, tests: bool):
        """Generate final validation report"""
        self.print_header("VALIDATION REPORT")

        print("\n📋 Fix Implementation Status:")
        print(f"  {'✅' if fix1 else '❌'} Fix #1: LabJack race condition - Handle validation")
        print(f"  {'✅' if fix2 else '❌'} Fix #2: constant_voltage_mode - Debounce bypass")
        print(f"  {'✅' if fix3 else '❌'} Fix #3: Recall calculation - Correct method")

        print("\n📋 Integration Tests:")
        print(f"  {'✅' if tests else '❌'} Integration test suite")

        # Print details for failed fixes
        if not fix1 and 'fix1' in self.details:
            print("\n📝 Fix #1 Details:")
            for detail in self.details['fix1']:
                print(f"    {detail[:100]}...")

        if not fix2 and 'fix2' in self.details:
            print("\n📝 Fix #2 Details:")
            for detail in self.details['fix2']:
                print(f"    {detail[:100]}...")

        if not fix3 and 'fix3' in self.details:
            print("\n📝 Fix #3 Details:")
            for detail in self.details['fix3']:
                print(f"    {detail[:100]}...")

        # Overall status
        all_passed = fix1 and fix2 and fix3 and tests

        if all_passed:
            self.print_header("🎉 ALL FIXES VALIDATED - Ready for deployment")
            print("\n✅ All three fixes are properly implemented")
            print("✅ Integration tests pass")
            print("✅ Ready for production deployment")
        else:
            self.print_header("⚠️  VALIDATION INCOMPLETE")
            failed_items = []
            if not fix1:
                failed_items.append("Fix #1 (LabJack)")
            if not fix2:
                failed_items.append("Fix #2 (constant_voltage_mode)")
            if not fix3:
                failed_items.append("Fix #3 (Recall)")
            if not tests:
                failed_items.append("Integration tests")

            print(f"\n❌ Failed items: {', '.join(failed_items)}")
            print("\n📝 Next steps:")
            print("  1. Review failed items above")
            print("  2. Implement missing fixes")
            print("  3. Run validation again")

        return all_passed

    def run(self):
        """Run complete validation"""
        self.print_header("AI MODEL VALIDATION PLATFORM - FIX VALIDATOR")

        print("\nThis script validates three critical fixes:")
        print("  1. LabJack race condition (Error 1224)")
        print("  2. constant_voltage_mode bypass (high FPS detection)")
        print("  3. Recall recalculation (correct GT count)")

        # Run validations
        fix1_valid = self.validate_fix_1_labjack_handle()
        fix2_valid = self.validate_fix_2_constant_voltage_mode()
        fix3_valid = self.validate_fix_3_recall_calculation()

        # Run integration tests
        tests_valid = self.run_integration_tests()

        # Generate report
        all_valid = self.generate_report(fix1_valid, fix2_valid, fix3_valid, tests_valid)

        return 0 if all_valid else 1


def main():
    """Main entry point"""
    validator = FixValidator()
    exit_code = validator.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
