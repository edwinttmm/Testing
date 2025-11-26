#!/usr/bin/env python3
"""
Startup Dependency Check Script

Verifies all critical dependencies are available before starting the backend services.
This script should be run during container/service startup to catch dependency issues early.

Usage:
    python3 scripts/startup_check.py

Exit codes:
    0: All checks passed
    1: One or more checks failed
"""

import sys
import os


def check_scipy():
    """Check scipy availability and key functions."""
    try:
        import scipy
        from scipy.optimize import linear_sum_assignment
        import numpy as np

        # Test with simple cost matrix
        cost_matrix = np.array([[1, 2], [3, 4]])
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        print(f"✓ scipy {scipy.__version__} - OK")
        print(f"  - linear_sum_assignment: functional")
        return True
    except ImportError as e:
        print(f"✗ scipy - MISSING")
        print(f"  Error: {e}")
        print(f"  Solution: pip install scipy")
        return False
    except Exception as e:
        print(f"✗ scipy - ERROR")
        print(f"  Error: {e}")
        return False


def check_numpy():
    """Check numpy availability."""
    try:
        import numpy as np
        print(f"✓ numpy {np.__version__} - OK")
        return True
    except ImportError as e:
        print(f"✗ numpy - MISSING")
        print(f"  Error: {e}")
        print(f"  Solution: pip install numpy")
        return False


def check_sqlalchemy():
    """Check SQLAlchemy availability."""
    try:
        import sqlalchemy
        print(f"✓ sqlalchemy {sqlalchemy.__version__} - OK")
        return True
    except ImportError as e:
        print(f"✗ sqlalchemy - MISSING")
        print(f"  Error: {e}")
        print(f"  Solution: pip install sqlalchemy")
        return False


def check_fastapi():
    """Check FastAPI availability."""
    try:
        import fastapi
        print(f"✓ fastapi {fastapi.__version__} - OK")
        return True
    except ImportError as e:
        print(f"✗ fastapi - MISSING")
        print(f"  Error: {e}")
        print(f"  Solution: pip install fastapi")
        return False


def check_virtual_environment():
    """Check if running in virtual environment."""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

    if in_venv:
        venv_path = os.environ.get('VIRTUAL_ENV', sys.prefix)
        print(f"✓ Virtual Environment - ACTIVE")
        print(f"  Path: {venv_path}")
        return True
    else:
        print(f"⚠ Virtual Environment - NOT DETECTED")
        print(f"  Recommendation: Activate venv with 'source venv/bin/activate'")
        # Not a failure, just a warning
        return True


def check_ground_truth_service():
    """Check if ground truth matching service can import."""
    try:
        # Add parent directory to path to allow imports
        import sys
        import os
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        # Try importing the service
        from services.ground_truth_matching_service import GroundTruthMatchingService
        print(f"✓ ground_truth_matching_service - OK")
        return True
    except ImportError as e:
        print(f"✗ ground_truth_matching_service - IMPORT ERROR")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"✗ ground_truth_matching_service - ERROR")
        print(f"  Error: {e}")
        return False


def check_optimal_matching_service():
    """Check if optimal matching service can import."""
    try:
        # Add parent directory to path to allow imports
        import sys
        import os
        backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        # Try importing the service
        from services.optimal_matching_service import optimal_detection_matching
        print(f"✓ optimal_matching_service - OK")
        return True
    except ImportError as e:
        print(f"✗ optimal_matching_service - IMPORT ERROR")
        print(f"  Error: {e}")
        return False
    except Exception as e:
        print(f"✗ optimal_matching_service - ERROR")
        print(f"  Error: {e}")
        return False


def main():
    """Run all startup checks."""
    print("="*70)
    print("Backend Startup Dependency Check")
    print("="*70)
    print()

    print("Python Environment:")
    print("-"*70)
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print()

    print("Dependency Checks:")
    print("-"*70)

    checks = [
        ("Virtual Environment", check_virtual_environment),
        ("numpy", check_numpy),
        ("scipy", check_scipy),
        ("sqlalchemy", check_sqlalchemy),
        ("fastapi", check_fastapi),
        ("Ground Truth Service", check_ground_truth_service),
        ("Optimal Matching Service", check_optimal_matching_service),
    ]

    results = {}
    for name, check_func in checks:
        results[name] = check_func()
        print()

    print("="*70)

    # Count failures
    failures = [name for name, passed in results.items() if not passed]

    if not failures:
        print("✓ All checks passed - backend ready to start")
        print("="*70)
        return 0
    else:
        print(f"✗ {len(failures)} check(s) failed:")
        for name in failures:
            print(f"  - {name}")
        print("="*70)
        print()
        print("Next Steps:")
        print("  1. Activate virtual environment: source venv/bin/activate")
        print("  2. Install missing dependencies: pip install -r requirements.txt")
        print("  3. Re-run this check: python3 scripts/startup_check.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
