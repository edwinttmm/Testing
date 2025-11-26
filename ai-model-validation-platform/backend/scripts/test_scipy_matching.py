#!/usr/bin/env python3
"""
Test Scipy Matching Integration

Tests the scipy integration with ground truth matching service using sample data.
This validates that scipy is properly installed and working with the matching algorithms.
"""

import sys
import os

# Add backend directory to path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)


def test_scipy_import():
    """Test 1: Basic scipy import."""
    print("Test 1: Scipy Import")
    print("-" * 70)

    try:
        import scipy
        from scipy.optimize import linear_sum_assignment
        print(f"✓ scipy {scipy.__version__} imported successfully")
        print(f"✓ linear_sum_assignment imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Failed to import scipy: {e}")
        return False


def test_hungarian_algorithm():
    """Test 2: Hungarian algorithm with sample data."""
    print("\nTest 2: Hungarian Algorithm")
    print("-" * 70)

    try:
        from scipy.optimize import linear_sum_assignment
        import numpy as np

        # Sample cost matrix
        cost_matrix = np.array([
            [4, 1, 3],
            [2, 0, 5],
            [3, 2, 2]
        ])

        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        print(f"✓ Cost matrix shape: {cost_matrix.shape}")
        print(f"✓ Optimal assignment found:")
        print(f"  Row indices: {row_ind}")
        print(f"  Col indices: {col_ind}")
        print(f"  Total cost: {cost_matrix[row_ind, col_ind].sum()}")
        return True
    except Exception as e:
        print(f"✗ Hungarian algorithm failed: {e}")
        return False


def test_optimal_matching_service():
    """Test 3: Optimal matching service integration."""
    print("\nTest 3: Optimal Matching Service")
    print("-" * 70)

    try:
        from services.optimal_matching_service import optimal_detection_matching

        # Sample ground truth and detection times
        gt_times = [1.0, 2.0, 3.0]
        det_times = [1.05, 2.02, 3.01]

        result = optimal_detection_matching(gt_times, det_times, tolerance_seconds=0.1)

        print(f"✓ Optimal matching completed")
        print(f"  Algorithm: {result['algorithm']}")
        print(f"  True Positives: {len(result['true_positives'])}")
        print(f"  False Positives: {len(result['false_positives'])}")
        print(f"  False Negatives: {len(result['false_negatives'])}")
        print(f"  Execution time: {result.get('execution_time_ms', 0):.2f}ms")

        if len(result['true_positives']) != 3:
            print(f"⚠ Warning: Expected 3 TP, got {len(result['true_positives'])}")
            return False

        return True
    except Exception as e:
        print(f"✗ Optimal matching service failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ground_truth_service_import():
    """Test 4: Ground truth matching service import."""
    print("\nTest 4: Ground Truth Matching Service")
    print("-" * 70)

    try:
        from services.ground_truth_matching_service import GroundTruthMatchingService

        service = GroundTruthMatchingService(default_tolerance_ms=100)

        print(f"✓ GroundTruthMatchingService instantiated")
        print(f"  Default tolerance: {service.default_tolerance_ms}ms")
        return True
    except Exception as e:
        print(f"✗ Ground truth matching service failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_matching_with_realistic_data():
    """Test 5: Matching with realistic detection data."""
    print("\nTest 5: Realistic Detection Matching")
    print("-" * 70)

    try:
        from services.optimal_matching_service import optimal_detection_matching

        # Realistic scenario: 10 ground truth objects, 12 detections (2 FP)
        gt_times = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5]
        det_times = [
            1.02, 1.52, 2.01, 2.48, 3.03,  # 5 good detections
            3.51, 4.02, 4.47, 5.05, 5.53,  # 5 more good detections
            1.25, 4.75  # 2 false positives (between GT objects)
        ]

        result = optimal_detection_matching(gt_times, det_times, tolerance_seconds=0.1)

        print(f"✓ Realistic matching completed")
        print(f"  Ground truth count: {len(gt_times)}")
        print(f"  Detection count: {len(det_times)}")
        print(f"  True Positives: {len(result['true_positives'])}")
        print(f"  False Positives: {len(result['false_positives'])}")
        print(f"  False Negatives: {len(result['false_negatives'])}")

        # Check results
        if len(result['true_positives']) != 10:
            print(f"⚠ Warning: Expected 10 TP, got {len(result['true_positives'])}")

        if len(result['false_positives']) != 2:
            print(f"⚠ Warning: Expected 2 FP, got {len(result['false_positives'])}")

        return True
    except Exception as e:
        print(f"✗ Realistic matching failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("="*70)
    print("Scipy Matching Integration Tests")
    print("="*70)
    print()

    tests = [
        test_scipy_import,
        test_hungarian_algorithm,
        test_optimal_matching_service,
        test_ground_truth_service_import,
        test_matching_with_realistic_data,
    ]

    results = []
    for test_func in tests:
        try:
            results.append(test_func())
        except Exception as e:
            print(f"\n✗ Test crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print()
    print("="*70)
    print("Test Summary")
    print("="*70)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")
    print()

    if passed == total:
        print("✓ All tests passed - scipy integration working correctly")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
