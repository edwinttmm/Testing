#!/usr/bin/env python3
"""
Test script to verify Hungarian algorithm fix for sparse/infeasible cost matrices.

This test reproduces the bug from session daad8bf6 where scipy threw:
"cost matrix is infeasible" due to columns with all-infinity values.
"""

import sys
import os

# Add parent directory to path so we can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.optimal_matching_service import optimal_detection_matching


def test_sparse_matrix_fix():
    """
    Test the fix for sparse cost matrices (session daad8bf6).

    Problematic data:
    - GT times: [0.0, 0.042, 0.083, 0.125, 0.167]
    - Detection times: [0.094, 0.236, 0.347, 0.417, 0.468]
    - Tolerance: 0.1s (100ms)

    Cost Matrix (5 GTs × 5 Detections):
         DET[0]  DET[1]  DET[2]  DET[3]  DET[4]
    GT[0] 94ms    inf     inf     inf     inf
    GT[1] 52ms    inf     inf     inf     inf
    GT[2] 11ms    inf     inf     inf     inf  <-- Best match #1
    GT[3] 31ms    inf     inf     inf     inf
    GT[4] 73ms    69ms    inf     inf     inf  <-- Best match #2

    Columns 2,3,4 are all infinity → scipy would fail without prefiltering.

    Expected result:
    - 2 TP: GT[2]→DET[0] (11ms), GT[4]→DET[1] (69ms)
    - 3 FP: DET[2], DET[3], DET[4] (all outside tolerance)
    - 3 FN: GT[0], GT[1], GT[3] (no matches within tolerance)
    """
    print("🔬 Testing Hungarian Algorithm Fix for Sparse Matrices")
    print("=" * 70)

    # Test data from session daad8bf6
    gt_times = [0.0, 0.042, 0.083, 0.125, 0.167]
    det_times = [0.094, 0.236, 0.347, 0.417, 0.468]
    tolerance_seconds = 0.1

    print(f"\n📊 Input Data:")
    print(f"  Ground Truth: {gt_times}")
    print(f"  Detections:   {det_times}")
    print(f"  Tolerance:    {tolerance_seconds}s ({tolerance_seconds*1000:.0f}ms)")

    print("\n🔍 Expected Cost Matrix (time differences in ms):")
    print("         DET[0]  DET[1]  DET[2]  DET[3]  DET[4]")
    for i, gt_time in enumerate(gt_times):
        row = f"  GT[{i}] "
        for j, det_time in enumerate(det_times):
            diff_ms = abs(det_time - gt_time) * 1000
            if diff_ms <= tolerance_seconds * 1000:
                row += f"{diff_ms:6.0f}ms "
            else:
                row += "   inf  "
        print(row)

    print("\n⚙️  Running optimal_detection_matching()...")

    try:
        result = optimal_detection_matching(
            ground_truth_times=gt_times,
            detection_times=det_times,
            tolerance_seconds=tolerance_seconds,
            return_cost_matrix=True
        )

        print("\n✅ Algorithm completed successfully!")
        print(f"  Algorithm: {result['algorithm']}")
        print(f"  Execution time: {result['execution_time_ms']:.1f}ms")

        print(f"\n📈 Results:")
        print(f"  True Positives:  {len(result['true_positives'])}")
        print(f"  False Positives: {len(result['false_positives'])}")
        print(f"  False Negatives: {len(result['false_negatives'])}")
        print(f"  Total Cost:      {result['total_cost']*1000:.1f}ms")

        if result['true_positives']:
            print(f"\n✓ True Positive Matches:")
            for gt_idx, det_idx, latency_ms in result['true_positives']:
                print(f"    GT[{gt_idx}] ({gt_times[gt_idx]:.3f}s) → "
                      f"DET[{det_idx}] ({det_times[det_idx]:.3f}s) "
                      f"[latency: {latency_ms:+.1f}ms]")

        if result['false_positives']:
            print(f"\n✗ False Positives (unmatched detections):")
            for det_idx in result['false_positives']:
                print(f"    DET[{det_idx}] ({det_times[det_idx]:.3f}s)")

        if result['false_negatives']:
            print(f"\n✗ False Negatives (unmatched ground truth):")
            for gt_idx in result['false_negatives']:
                print(f"    GT[{gt_idx}] ({gt_times[gt_idx]:.3f}s)")

        # Validate results
        print("\n🔍 Validation:")

        expected_tp = 2  # Corrected: GT[2]→DET[0] and GT[4]→DET[1]
        expected_fp = 3  # Corrected: DET[2], DET[3], DET[4]
        expected_fn = 3  # Corrected: GT[0], GT[1], GT[3]

        tp_match = len(result['true_positives']) == expected_tp
        fp_match = len(result['false_positives']) == expected_fp
        fn_match = len(result['false_negatives']) == expected_fn

        print(f"  TP count: {len(result['true_positives'])} (expected {expected_tp}) "
              f"{'✓' if tp_match else '✗'}")
        print(f"  FP count: {len(result['false_positives'])} (expected {expected_fp}) "
              f"{'✓' if fp_match else '✗'}")
        print(f"  FN count: {len(result['false_negatives'])} (expected {expected_fn}) "
              f"{'✓' if fn_match else '✗'}")

        # Validate first match (GT[2]→DET[0], 11ms)
        if len(result['true_positives']) >= 1:
            gt_idx, det_idx, latency_ms = result['true_positives'][0]
            expected_gt_idx = 2
            expected_det_idx = 0

            gt_idx_match = gt_idx == expected_gt_idx
            det_idx_match = det_idx == expected_det_idx

            print(f"  TP[0] match indices: GT[{gt_idx}]→DET[{det_idx}] "
                  f"(expected GT[{expected_gt_idx}]→DET[{expected_det_idx}]) "
                  f"{'✓' if (gt_idx_match and det_idx_match) else '✗'}")

            latency_valid = 10 <= abs(latency_ms) <= 12  # Should be ~11ms
            print(f"  TP[0] latency: {latency_ms:.1f}ms (expected ~11ms) "
                  f"{'✓' if latency_valid else '✗'}")

        # Validate second match (GT[4]→DET[1], 69ms)
        if len(result['true_positives']) >= 2:
            gt_idx, det_idx, latency_ms = result['true_positives'][1]
            expected_gt_idx = 4
            expected_det_idx = 1

            gt_idx_match = gt_idx == expected_gt_idx
            det_idx_match = det_idx == expected_det_idx

            print(f"  TP[1] match indices: GT[{gt_idx}]→DET[{det_idx}] "
                  f"(expected GT[{expected_gt_idx}]→DET[{expected_det_idx}]) "
                  f"{'✓' if (gt_idx_match and det_idx_match) else '✗'}")

            latency_valid = 68 <= abs(latency_ms) <= 70  # Should be ~69ms
            print(f"  TP[1] latency: {latency_ms:.1f}ms (expected ~69ms) "
                  f"{'✓' if latency_valid else '✗'}")

        all_pass = (tp_match and fp_match and fn_match and
                   len(result['true_positives']) == expected_tp)

        print("\n" + "=" * 70)
        if all_pass:
            print("✅ ALL TESTS PASSED - Hungarian algorithm fix is working!")
            return 0
        else:
            print("❌ SOME TESTS FAILED - Review results above")
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        print("\nThis error suggests the fix is not working correctly.")
        import traceback
        traceback.print_exc()
        return 1


def test_edge_cases():
    """Test additional edge cases to ensure robustness."""
    print("\n\n🔬 Testing Edge Cases")
    print("=" * 70)

    test_cases = [
        {
            'name': 'All matches outside tolerance',
            'gt_times': [0.0, 1.0, 2.0],
            'det_times': [0.5, 1.5, 2.5],
            'tolerance': 0.1,
            'expected_tp': 0,
            'expected_fp': 3,
            'expected_fn': 3
        },
        {
            'name': 'Single perfect match',
            'gt_times': [1.0],
            'det_times': [1.0],
            'tolerance': 0.1,
            'expected_tp': 1,
            'expected_fp': 0,
            'expected_fn': 0
        },
        {
            'name': 'Empty detections',
            'gt_times': [1.0, 2.0],
            'det_times': [],
            'tolerance': 0.1,
            'expected_tp': 0,
            'expected_fp': 0,
            'expected_fn': 2
        },
        {
            'name': 'Empty ground truth',
            'gt_times': [],
            'det_times': [1.0, 2.0],
            'tolerance': 0.1,
            'expected_tp': 0,
            'expected_fp': 2,
            'expected_fn': 0
        },
    ]

    all_passed = True

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print(f"   GT: {test_case['gt_times']}, Det: {test_case['det_times']}")

        try:
            result = optimal_detection_matching(
                ground_truth_times=test_case['gt_times'],
                detection_times=test_case['det_times'],
                tolerance_seconds=test_case['tolerance']
            )

            tp_ok = len(result['true_positives']) == test_case['expected_tp']
            fp_ok = len(result['false_positives']) == test_case['expected_fp']
            fn_ok = len(result['false_negatives']) == test_case['expected_fn']

            if tp_ok and fp_ok and fn_ok:
                print(f"   ✓ PASS: TP={len(result['true_positives'])}, "
                      f"FP={len(result['false_positives'])}, "
                      f"FN={len(result['false_negatives'])}")
            else:
                print(f"   ✗ FAIL: Expected TP={test_case['expected_tp']}, "
                      f"FP={test_case['expected_fp']}, FN={test_case['expected_fn']}")
                print(f"           Got TP={len(result['true_positives'])}, "
                      f"FP={len(result['false_positives'])}, "
                      f"FN={len(result['false_negatives'])}")
                all_passed = False

        except Exception as e:
            print(f"   ✗ ERROR: {type(e).__name__}: {e}")
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL EDGE CASE TESTS PASSED")
        return 0
    else:
        print("❌ SOME EDGE CASE TESTS FAILED")
        return 1


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("HUNGARIAN ALGORITHM FIX - TEST SUITE")
    print("=" * 70)

    # Run main test
    result1 = test_sparse_matrix_fix()

    # Run edge case tests
    result2 = test_edge_cases()

    # Final summary
    print("\n\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    if result1 == 0 and result2 == 0:
        print("✅ ALL TESTS PASSED - Fix is working correctly!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED - Fix needs review")
        sys.exit(1)
