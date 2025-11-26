#!/usr/bin/env python3
"""
Scipy Installation Verification Script

Verifies scipy is properly installed and functional for AI Model Validation Platform.
Tests both import capability and key functions needed for ground truth matching.
"""

import sys
import os
from typing import Tuple


def verify_scipy_import() -> Tuple[bool, str]:
    """Verify scipy can be imported."""
    try:
        import scipy
        return True, f"scipy version {scipy.__version__} imported successfully"
    except ImportError as e:
        return False, f"Failed to import scipy: {e}"


def verify_linear_sum_assignment() -> Tuple[bool, str]:
    """Verify the Hungarian algorithm function is available."""
    try:
        from scipy.optimize import linear_sum_assignment

        # Test with a simple cost matrix
        import numpy as np
        cost_matrix = np.array([
            [4, 1, 3],
            [2, 0, 5],
            [3, 2, 2]
        ])

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        if len(row_ind) == 3 and len(col_ind) == 3:
            return True, "linear_sum_assignment working correctly"
        else:
            return False, "linear_sum_assignment returned unexpected results"

    except ImportError as e:
        return False, f"Failed to import linear_sum_assignment: {e}"
    except Exception as e:
        return False, f"Error testing linear_sum_assignment: {e}"


def verify_numpy() -> Tuple[bool, str]:
    """Verify numpy is available (required dependency)."""
    try:
        import numpy as np
        return True, f"numpy version {np.__version__} imported successfully"
    except ImportError as e:
        return False, f"Failed to import numpy: {e}"


def get_python_info() -> str:
    """Get current Python environment information."""
    info = [
        f"Python Version: {sys.version}",
        f"Python Executable: {sys.executable}",
        f"Virtual Environment: {'Yes' if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) else 'No'}",
    ]

    if 'VIRTUAL_ENV' in os.environ:
        info.append(f"VIRTUAL_ENV: {os.environ['VIRTUAL_ENV']}")

    return "\n".join(info)


def main():
    """Run all verification checks."""
    print("="*70)
    print("Scipy Installation Verification")
    print("="*70)
    print()

    print("Python Environment:")
    print("-"*70)
    print(get_python_info())
    print()

    print("Dependency Checks:")
    print("-"*70)

    all_passed = True

    # Check numpy
    passed, message = verify_numpy()
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {message}")
    all_passed = all_passed and passed

    # Check scipy import
    passed, message = verify_scipy_import()
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {message}")
    all_passed = all_passed and passed

    # Check linear_sum_assignment
    passed, message = verify_linear_sum_assignment()
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {message}")
    all_passed = all_passed and passed

    print()
    print("="*70)

    if all_passed:
        print("✓ All checks passed - scipy is ready for production use")
        print("="*70)
        return 0
    else:
        print("✗ Some checks failed - see errors above")
        print("="*70)
        print()
        print("Solution:")
        print("  1. Activate virtual environment: source venv/bin/activate")
        print("  2. Or install scipy: pip3 install scipy")
        print("  3. Re-run this script to verify")
        return 1


if __name__ == "__main__":
    sys.exit(main())
