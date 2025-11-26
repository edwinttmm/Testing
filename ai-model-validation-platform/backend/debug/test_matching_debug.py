#!/usr/bin/env python3
"""
Debug script to test timestamp extraction and matching.

This will help identify why optimal_detection_matching finds no feasible matches
despite having correct timestamps in the database.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import logging
from services.optimal_matching_service import optimal_detection_matching

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def test_matching_with_known_values():
    """Test with values from the logs."""

    # Ground truth times from logs (video-relative, 0-5s range)
    gt_times = [0.000, 0.042, 0.083, 0.125, 0.167]  # 24 FPS intervals

    # Detection times from logs (video-relative, should match)
    det_times = [0.094, 0.236, 0.378, 0.520, 0.662]

    # Tolerance from spec: 100ms = 0.1s
    tolerance_seconds = 0.1

    logger.info("=" * 80)
    logger.info("TESTING OPTIMAL MATCHING WITH KNOWN VALUES")
    logger.info("=" * 80)
    logger.info(f"Ground truth times: {gt_times}")
    logger.info(f"Detection times: {det_times}")
    logger.info(f"Tolerance: {tolerance_seconds}s ({tolerance_seconds*1000}ms)")
    logger.info("")

    # Calculate time differences
    logger.info("Expected time differences (should be <100ms for valid matches):")
    for i, gt_time in enumerate(gt_times):
        for j, det_time in enumerate(det_times):
            time_diff = abs(det_time - gt_time)
            match_str = "✅ MATCH" if time_diff <= tolerance_seconds else "❌ NO MATCH"
            logger.info(f"  GT[{i}]={gt_time:.3f}s vs DET[{j}]={det_time:.3f}s: "
                       f"diff={time_diff*1000:.1f}ms {match_str}")
    logger.info("")

    # Run optimal matching
    result = optimal_detection_matching(
        ground_truth_times=gt_times,
        detection_times=det_times,
        tolerance_seconds=tolerance_seconds,
        return_cost_matrix=True
    )

    logger.info("=" * 80)
    logger.info("MATCHING RESULTS")
    logger.info("=" * 80)
    logger.info(f"Algorithm used: {result.get('algorithm', 'unknown')}")
    logger.info(f"True positives: {len(result['true_positives'])}")
    logger.info(f"False positives: {len(result['false_positives'])}")
    logger.info(f"False negatives: {len(result['false_negatives'])}")
    logger.info(f"Total cost: {result['total_cost']*1000:.1f}ms")
    logger.info("")

    if result['true_positives']:
        logger.info("True positive matches:")
        for gt_idx, det_idx, latency_ms in result['true_positives']:
            logger.info(f"  GT[{gt_idx}]={gt_times[gt_idx]:.3f}s ↔ "
                       f"DET[{det_idx}]={det_times[det_idx]:.3f}s "
                       f"(latency={latency_ms:.1f}ms)")
    else:
        logger.error("❌ NO TRUE POSITIVES FOUND!")
        logger.error("This is the bug we're investigating.")
    logger.info("")

    if 'cost_matrix' in result:
        import numpy as np
        cost_matrix = result['cost_matrix']
        logger.info("Cost matrix (in milliseconds, 'inf' = invalid):")
        logger.info("     " + " ".join(f"DET[{j}]" for j in range(len(det_times))))
        for i in range(len(gt_times)):
            row_str = f"GT[{i}] "
            for j in range(len(det_times)):
                cost = cost_matrix[i, j]
                if cost == float('inf'):
                    row_str += "  inf   "
                else:
                    row_str += f"{cost*1000:6.1f} "
            logger.info(row_str)

    return result


def test_with_epoch_timestamps():
    """Test with Unix epoch timestamps (as they appear in DB)."""

    # Base epoch time (example)
    base_epoch = 1732444800.0  # 2025-11-24 00:00:00 UTC

    # Ground truth: epoch timestamps
    gt_times_epoch = [base_epoch + t for t in [0.000, 0.042, 0.083, 0.125, 0.167]]

    # Detection: epoch timestamps
    det_times_epoch = [base_epoch + t for t in [0.094, 0.236, 0.378, 0.520, 0.662]]

    tolerance_seconds = 0.1

    logger.info("\n" + "=" * 80)
    logger.info("TESTING WITH EPOCH TIMESTAMPS (as in database)")
    logger.info("=" * 80)
    logger.info(f"Ground truth times: {gt_times_epoch[:3]}... (epoch)")
    logger.info(f"Detection times: {det_times_epoch[:3]}... (epoch)")
    logger.info(f"Tolerance: {tolerance_seconds}s ({tolerance_seconds*1000}ms)")
    logger.info("")

    # Run optimal matching
    result = optimal_detection_matching(
        ground_truth_times=gt_times_epoch,
        detection_times=det_times_epoch,
        tolerance_seconds=tolerance_seconds
    )

    logger.info("RESULTS WITH EPOCH TIMESTAMPS:")
    logger.info(f"True positives: {len(result['true_positives'])}")
    logger.info(f"False positives: {len(result['false_positives'])}")
    logger.info(f"False negatives: {len(result['false_negatives'])}")
    logger.info("")

    return result


if __name__ == '__main__':
    logger.info("Starting timestamp extraction debug test...")
    logger.info("")

    # Test 1: With video-relative timestamps (as expected)
    result1 = test_matching_with_known_values()

    # Test 2: With epoch timestamps (as they are in DB)
    result2 = test_with_epoch_timestamps()

    # Summary
    logger.info("=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    if result1['true_positives']:
        logger.info("✅ Test 1 (video-relative): PASSED")
    else:
        logger.error("❌ Test 1 (video-relative): FAILED - No matches found!")

    if result2['true_positives']:
        logger.info("✅ Test 2 (epoch timestamps): PASSED")
    else:
        logger.error("❌ Test 2 (epoch timestamps): FAILED - No matches found!")

    logger.info("")
    logger.info("If Test 1 passes but production fails, the issue is in timestamp extraction.")
    logger.info("If Test 1 fails, the issue is in the optimal matching algorithm itself.")
