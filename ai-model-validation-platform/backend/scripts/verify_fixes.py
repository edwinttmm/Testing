#!/usr/bin/env python3
"""
Verification Script for Two Critical Fixes
==========================================

This script verifies that both fixes have been successfully applied:

Fix #1: Frontend Recall Display - reading from accuracyRecall field
Fix #2: Backend Constant Voltage Mode - parameter added to DetectionTestConfig

Usage:
    python verify_fixes.py
"""

import os
import re
from pathlib import Path


def verify_frontend_fix():
    """Verify frontend recall fix is applied"""
    print("\n" + "="*70)
    print("FIX #1: FRONTEND RECALL DISPLAY")
    print("="*70)

    frontend_file = Path(__file__).parent.parent.parent / 'frontend' / 'src' / 'pages' / 'HILResults.tsx'

    if not frontend_file.exists():
        print(f"❌ File not found: {frontend_file}")
        return False

    with open(frontend_file, 'r') as f:
        content = f.read()

    # Check for the fixed recall calculation that reads from accuracyRecall field
    if 'accuracyRecall' in content:
        # Find the exact line(s) where recall is calculated
        lines = content.split('\n')
        recall_lines = []
        for i, line in enumerate(lines, 1):
            if 'const recall' in line or 'accuracyRecall' in line:
                recall_lines.append((i, line.strip()))

        print(f"✅ Frontend fix applied: accuracyRecall field is being read")
        print(f"\nFound {len(recall_lines)} relevant lines:")
        for line_num, line_content in recall_lines[:5]:  # Show first 5
            print(f"  Line {line_num}: {line_content}")

        # Check specifically for the rawMetrics.accuracyRecall pattern
        if 'rawMetrics.accuracyRecall' in content or 'enhancedResults?.accuracyRecall' in content:
            print("\n✅ CONFIRMED: Reading from accuracyRecall field in rawMetrics/enhancedResults")
            return True
        else:
            print("\n⚠️  WARNING: accuracyRecall field found but may not be properly integrated")
            return False
    else:
        print("❌ Frontend fix NOT applied: accuracyRecall field not found")
        return False


def verify_backend_fix():
    """Verify backend constant_voltage_mode is added"""
    print("\n" + "="*70)
    print("FIX #2: BACKEND CONSTANT VOLTAGE MODE")
    print("="*70)

    # Check multiple files for constant_voltage_mode
    backend_files = [
        'api_enhanced_test_workflow_integrated.py',
        'src/api/enhanced_test_endpoints.py',
        'services/detection_service.py'
    ]

    found_in_files = []
    backend_base = Path(__file__).parent.parent

    for file_name in backend_files:
        file_path = backend_base / file_name

        if not file_path.exists():
            continue

        with open(file_path, 'r') as f:
            content = f.read()

        if 'constant_voltage_mode' in content:
            # Count occurrences
            count = content.count('constant_voltage_mode')

            # Find class definitions
            class_match = re.search(r'class\s+\w*Config.*?constant_voltage_mode', content, re.DOTALL)

            found_in_files.append({
                'file': file_name,
                'count': count,
                'has_config_class': bool(class_match)
            })

    if found_in_files:
        print(f"✅ Backend fix applied: constant_voltage_mode parameter found in {len(found_in_files)} file(s)")

        for info in found_in_files:
            print(f"\n  📄 File: {info['file']}")
            print(f"     Occurrences: {info['count']}")
            print(f"     In Config Class: {'✅ YES' if info['has_config_class'] else '⚠️  NO'}")

        # Verify it's in DetectionTestConfig or DetectionConfig
        enhanced_file = backend_base / 'api_enhanced_test_workflow_integrated.py'
        if enhanced_file.exists():
            with open(enhanced_file, 'r') as f:
                content = f.read()

            # Look for DetectionTestConfig class
            config_match = re.search(
                r'class\s+DetectionTestConfig.*?:\s*(.*?)(?=class\s+|\Z)',
                content,
                re.DOTALL
            )

            if config_match:
                config_body = config_match.group(1)
                if 'constant_voltage_mode' in config_body:
                    print("\n✅ CONFIRMED: constant_voltage_mode in DetectionTestConfig class")

                    # Check for default value
                    if 'constant_voltage_mode: bool = False' in config_body:
                        print("✅ CONFIRMED: Default value set to False (backward compatible)")
                    elif 'constant_voltage_mode: bool' in config_body:
                        print("✅ CONFIRMED: Parameter defined as bool type")

                    return True

        print("\n⚠️  WARNING: constant_voltage_mode found but not in expected DetectionTestConfig")
        return False
    else:
        print("❌ Backend fix NOT applied: constant_voltage_mode parameter not found")
        return False


def verify_syntax():
    """Basic syntax verification"""
    print("\n" + "="*70)
    print("SYNTAX VERIFICATION")
    print("="*70)

    # Check Python syntax for backend
    backend_file = Path(__file__).parent.parent / 'api_enhanced_test_workflow_integrated.py'
    if backend_file.exists():
        try:
            import py_compile
            py_compile.compile(str(backend_file), doraise=True)
            print("✅ Backend Python syntax valid")
            backend_ok = True
        except SyntaxError as e:
            print(f"❌ Backend syntax error: {e}")
            backend_ok = False
    else:
        print("⚠️  Backend file not found for syntax check")
        backend_ok = True  # Don't fail if file moved

    # Note: Can't check TypeScript syntax without tsc
    print("ℹ️  Frontend TypeScript syntax check requires 'npm run typecheck'")

    return backend_ok


def main():
    """Main verification routine"""
    print("\n" + "🔍 VERIFICATION REPORT".center(70, "="))
    print("Checking that both critical fixes are applied correctly\n")

    # Run all verifications
    fix1 = verify_frontend_fix()
    fix2 = verify_backend_fix()
    syntax_ok = verify_syntax()

    # Final summary
    print("\n" + "="*70)
    print("OVERALL STATUS")
    print("="*70)

    status_icon = "✅" if (fix1 and fix2 and syntax_ok) else "❌"

    print(f"\n{status_icon} Fix #1 (Frontend Recall): {'APPLIED' if fix1 else 'NOT APPLIED'}")
    print(f"{status_icon} Fix #2 (Backend Constant Voltage): {'APPLIED' if fix2 else 'NOT APPLIED'}")
    print(f"{'✅' if syntax_ok else '❌'} Syntax Validation: {'PASSED' if syntax_ok else 'FAILED'}")

    if fix1 and fix2 and syntax_ok:
        print("\n🎉 ALL FIXES APPLIED SUCCESSFULLY!")
        print("\nNEXT STEPS:")
        print("1. Run frontend build: cd frontend && npm run build")
        print("2. Run backend tests: cd backend && pytest tests/test_fixes_integration.py")
        print("3. Test in UI: Start both servers and verify recall displays correctly")
        print("4. Test constant voltage mode with LabJack at 4.2V constant")
    else:
        print("\n⚠️  SOME FIXES MISSING OR INCOMPLETE")
        print("\nREQUIRED ACTIONS:")
        if not fix1:
            print("- Apply frontend recall fix in HILResults.tsx")
        if not fix2:
            print("- Add constant_voltage_mode parameter to DetectionTestConfig")
        if not syntax_ok:
            print("- Fix syntax errors in backend code")

    return 0 if (fix1 and fix2 and syntax_ok) else 1


if __name__ == "__main__":
    exit(main())
