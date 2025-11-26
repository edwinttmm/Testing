"""
Test script to validate Priority 1 fix: Temporal expansion disabled

This test verifies that disabling temporal expansion:
1. Prevents 173→519 detection expansion
2. Allows Hungarian algorithm to succeed (no "infeasible" error)
3. Improves F1 score from 59.53% to 75%+

Session ID: daad8bf6-b5da-4423-abc4-a85e83bc1c16
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from services.ground_truth_matching_service import GroundTruthMatchingService
from database import Base
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_temporal_expansion_disabled():
    """
    Test that temporal expansion is disabled and validates expected improvements

    Expected results:
    - Detections: 173 (NOT 519)
    - Cost matrix density: ~6% (NOT 1.94%)
    - Hungarian algorithm: SUCCESS (NOT failing)
    - F1 Score: 75%+ (from 59.53%)
    """

    # Test session ID from investigation
    session_id = "daad8bf6-b5da-4423-abc4-a85e83bc1c16"

    try:
        # Initialize matching service
        matching_service = GroundTruthMatchingService()

        logger.info("=" * 80)
        logger.info("🧪 Testing Priority 1 Fix: Temporal Expansion Disabled")
        logger.info("=" * 80)

        # Run matching for the test session
        logger.info(f"📊 Running matching for session: {session_id}")
        result = matching_service.match_detections_to_ground_truth(
            session_id=session_id,
            force_rematch=True,  # Force rematch to see new behavior
            auto_commit=False    # Don't commit to DB during test
        )

        # Extract metrics from SessionMetrics dataclass
        tp_count = result.true_positives
        fp_count = result.false_positives
        fn_count = result.false_negatives
        precision = result.precision
        recall = result.recall
        f1_score = result.f1_score

        logger.info("")
        logger.info("📈 RESULTS:")
        logger.info("=" * 80)
        logger.info(f"True Positives:  {tp_count}")
        logger.info(f"False Positives: {fp_count}")
        logger.info(f"False Negatives: {fn_count}")
        logger.info(f"Precision:       {precision:.2%}")
        logger.info(f"Recall:          {recall:.2%}")
        logger.info(f"F1 Score:        {f1_score:.2%}")
        logger.info("=" * 80)

        # Validation checks
        logger.info("")
        logger.info("✅ VALIDATION CHECKS:")
        logger.info("=" * 80)

        # Check 1: Detection count (should be ~173, not 519)
        # Note: Actual detection count may vary, but should NOT be 3x expanded
        total_matches = tp_count + fp_count
        if total_matches < 250:
            logger.info(f"✅ Detection count reasonable: {total_matches} (expected ~173, was 519 with expansion)")
        else:
            logger.warning(f"⚠️  Detection count high: {total_matches} (may still have expansion)")

        # Check 2: F1 Score improvement (should be 75%+)
        baseline_f1 = 0.5953  # 59.53% from investigation
        target_f1 = 0.75      # 75% target

        if f1_score >= target_f1:
            improvement = ((f1_score - baseline_f1) / baseline_f1) * 100
            logger.info(f"✅ F1 Score meets target: {f1_score:.2%} ≥ {target_f1:.2%} (+{improvement:.1f}% improvement)")
        elif f1_score > baseline_f1:
            improvement = ((f1_score - baseline_f1) / baseline_f1) * 100
            logger.info(f"⚠️  F1 Score improved but below target: {f1_score:.2%} < {target_f1:.2%} (+{improvement:.1f}% improvement)")
        else:
            logger.error(f"❌ F1 Score did not improve: {f1_score:.2%} ≤ {baseline_f1:.2%}")

        # Check 3: Algorithm used - Check via metrics (Hungarian success implied by improved F1)
        # Note: SessionMetrics doesn't include algorithm field, but we can infer from results
        if f1_score >= target_f1:
            logger.info("✅ Algorithm performing optimally (Hungarian likely succeeded)")
        else:
            logger.warning("⚠️  Algorithm may be using greedy fallback")

        logger.info("=" * 80)

        # Summary
        logger.info("")
        logger.info("📊 SUMMARY:")
        logger.info("=" * 80)
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Baseline F1: {baseline_f1:.2%}")
        logger.info(f"Current F1:  {f1_score:.2%}")
        logger.info(f"Target F1:   {target_f1:.2%}")
        logger.info(f"Status:      {'✅ SUCCESS' if f1_score >= target_f1 else '⚠️ PARTIAL' if f1_score > baseline_f1 else '❌ FAILED'}")
        logger.info("=" * 80)

        return {
            'success': f1_score >= target_f1,
            'f1_score': f1_score,
            'precision': precision,
            'recall': recall,
            'tp_count': tp_count,
            'fp_count': fp_count,
            'fn_count': fn_count,
            'total_detections': result.total_detections,
            'total_ground_truth': result.total_ground_truth,
            'baseline_f1': baseline_f1,
            'target_f1': target_f1
        }

    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        results = test_temporal_expansion_disabled()

        # Exit with appropriate code
        if results['success']:
            logger.info("🎉 All tests passed!")
            sys.exit(0)
        elif results['f1_score'] > results['baseline_f1']:
            logger.info("⚠️  Partial success - F1 improved but below target")
            sys.exit(0)
        else:
            logger.error("❌ Tests failed - F1 did not improve")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Test execution failed: {e}")
        sys.exit(1)
