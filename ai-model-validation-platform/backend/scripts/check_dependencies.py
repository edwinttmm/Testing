#!/usr/bin/env python3
"""
Dependency Checker for AI Model Validation Platform

This script verifies that all required Python dependencies are installed
and functioning correctly. Run this before starting the backend server.

Usage:
    python3 scripts/check_dependencies.py

Exit codes:
    0 - All dependencies OK
    1 - Missing or broken dependencies
"""

import sys
import importlib.util


def check_dependency(package_name, import_name=None, description=None):
    """
    Check if a Python package is installed and importable.

    Args:
        package_name: Package name for pip install
        import_name: Import name (defaults to package_name)
        description: Human-readable description of what this is used for

    Returns:
        bool: True if package is available, False otherwise
    """
    if import_name is None:
        import_name = package_name

    try:
        spec = importlib.util.find_spec(import_name)
        if spec is None:
            print(f"❌ MISSING: {package_name}")
            if description:
                print(f"   Used for: {description}")
            print(f"   Fix: pip install {package_name}")
            return False

        # Try actually importing to catch version issues
        __import__(import_name)
        print(f"✅ OK: {package_name}")
        return True
    except ImportError as e:
        print(f"❌ ERROR: {package_name} - {e}")
        if description:
            print(f"   Used for: {description}")
        print(f"   Fix: pip install {package_name}")
        return False


def check_all_dependencies():
    """
    Check all required dependencies for the backend.

    Returns:
        bool: True if all dependencies are available, False otherwise
    """
    print("=" * 60)
    print("Checking Backend Dependencies")
    print("=" * 60)
    print()

    dependencies = [
        # Core framework
        ("fastapi", "fastapi", "REST API framework"),
        ("uvicorn", "uvicorn", "ASGI server"),
        ("pydantic", "pydantic", "Data validation"),

        # Database
        ("sqlalchemy", "sqlalchemy", "ORM and database toolkit"),
        ("alembic", "alembic", "Database migrations"),

        # Scientific computing - CRITICAL
        ("scipy", "scipy", "Optimal matching algorithm (Hungarian)"),
        ("numpy", "numpy", "Numerical computations"),

        # Optional but recommended
        ("python-multipart", "multipart", "File upload support"),
        ("python-jose", "jose", "JWT token handling"),
        ("passlib", "passlib", "Password hashing"),
        ("bcrypt", "bcrypt", "Password encryption"),
    ]

    all_ok = True
    missing = []

    for package_name, import_name, description in dependencies:
        if not check_dependency(package_name, import_name, description):
            all_ok = False
            missing.append(package_name)

    print()
    print("=" * 60)

    if all_ok:
        print("✅ All dependencies OK")
        print("=" * 60)
        return True
    else:
        print(f"❌ Missing {len(missing)} dependencies")
        print("=" * 60)
        print()
        print("Install missing packages with:")
        print(f"pip install {' '.join(missing)}")
        print()
        print("Or install all from requirements.txt:")
        print("pip install -r requirements.txt")
        return False


def check_critical_scipy():
    """
    Special check for scipy since ground truth matching absolutely requires it.

    Returns:
        bool: True if scipy is available and working
    """
    print()
    print("=" * 60)
    print("Critical Dependency Check: scipy")
    print("=" * 60)
    print()

    try:
        from scipy.optimize import linear_sum_assignment
        print("✅ scipy.optimize.linear_sum_assignment: OK")

        # Test with simple example
        import numpy as np
        cost_matrix = np.array([[4, 1, 3], [2, 0, 5], [3, 2, 2]])
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        print("✅ scipy Hungarian algorithm test: PASSED")
        print()
        return True
    except ImportError as e:
        print(f"❌ scipy import FAILED: {e}")
        print()
        print("Ground truth matching WILL NOT WORK without scipy!")
        print()
        print("Install with:")
        print("  pip install scipy")
        print()
        return False
    except Exception as e:
        print(f"❌ scipy test FAILED: {e}")
        print()
        return False


if __name__ == "__main__":
    # Check all dependencies
    all_ok = check_all_dependencies()

    # Extra check for scipy
    scipy_ok = check_critical_scipy()

    if all_ok and scipy_ok:
        print("🎉 System ready for backend startup")
        sys.exit(0)
    else:
        print("⚠️  Please install missing dependencies before running the backend")
        sys.exit(1)
