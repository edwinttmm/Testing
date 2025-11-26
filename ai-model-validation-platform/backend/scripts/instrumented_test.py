#!/usr/bin/env python3
"""
Instrumented Test Script - Captures Real-Time Debug Data
Run this to get ACTUAL values during execution, not hypotheses.
"""

import sys
import os
import logging
from datetime import datetime
import traceback

# Setup paths
sys.path.insert(0, '/home/rigade/Testing/ai-model-validation-platform/backend')
os.chdir('/home/rigade/Testing/ai-model-validation-platform/backend')

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/tmp/instrumented_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*80)
logger.info("INSTRUMENTED TEST STARTING")
logger.info(f"Timestamp: {datetime.now().isoformat()}")
logger.info("="*80)

try:
    # Import services
    logger.info("[IMPORT] Importing services...")
    from services.ground_truth_matching_service import GroundTruthMatchingService
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from models import GroundTruthObject, TestSession, DetectionEvent
    from database import SessionLocal
    logger.info("[IMPORT] Successfully imported all modules")

    # Monkey-patch critical methods
    logger.info("[PATCH] Applying instrumentation patches...")
    original_get_gt_count = GroundTruthMatchingService._get_actual_ground_truth_count

    def instrumented_get_gt_count(self, session_id):
        """Instrumented version that logs actual values"""
        logger.info(f"[TRACE] _get_actual_ground_truth_count called for session: {session_id}")
        logger.info(f"[TRACE] Method type: {type(original_get_gt_count)}")

        try:
            # Get result from original method
            result = original_get_gt_count(self, session_id)
            logger.info(f"[TRACE] Original method returned: {result} (type: {type(result)})")
        except Exception as e:
            logger.error(f"[TRACE] Original method raised exception: {e}")
            logger.error(traceback.format_exc())
            result = None

        # Also query directly for verification
        logger.info("[TRACE] Performing direct database verification...")
        db = SessionLocal()
        try:
            direct_count = db.query(GroundTruthObject).filter(
                GroundTruthObject.session_id == session_id
            ).count()
            logger.info(f"[TRACE] Direct GT query returned: {direct_count}")

            # Get actual GT records
            gt_records = db.query(GroundTruthObject).filter(
                GroundTruthObject.session_id == session_id
            ).all()
            logger.info(f"[TRACE] GT records found: {len(gt_records)}")
            for i, gt in enumerate(gt_records[:5], 1):  # Show first 5
                logger.info(f"[TRACE]   GT {i}: mac={gt.mac_address}, channel={gt.channel}")

            if result is not None and result != direct_count:
                logger.error(f"[MISMATCH] Method:{result} != Query:{direct_count}")

            # Get session data
            session = db.query(TestSession).filter(
                TestSession.id == session_id
            ).first()

            if session:
                logger.info(f"[TRACE] Session found: {session.id}")
                logger.info(f"[TRACE] Session name: {session.name if hasattr(session, 'name') else 'N/A'}")
                logger.info(f"[TRACE] Session TP: {session.true_positives if hasattr(session, 'true_positives') else 'N/A'}")
                logger.info(f"[TRACE] Session FP: {session.false_positives if hasattr(session, 'false_positives') else 'N/A'}")
                logger.info(f"[TRACE] Session FN: {session.false_negatives if hasattr(session, 'false_negatives') else 'N/A'}")
                logger.info(f"[TRACE] Session TN: {session.true_negatives if hasattr(session, 'true_negatives') else 'N/A'}")

                # Calculate what recall SHOULD be
                tp = session.true_positives if hasattr(session, 'true_positives') and session.true_positives else 0
                fn = session.false_negatives if hasattr(session, 'false_negatives') and session.false_negatives else 0

                if direct_count > 0:
                    expected_recall = tp / direct_count
                    logger.info(f"[CALC] Expected recall: {tp}/{direct_count} = {expected_recall:.4f}")
                else:
                    logger.warning(f"[CALC] Cannot calculate recall: direct_count = {direct_count}")

                if (tp + fn) > 0:
                    formula_recall = tp / (tp + fn)
                    logger.info(f"[CALC] Formula recall: {tp}/({tp}+{fn}) = {formula_recall:.4f}")
                else:
                    logger.warning(f"[CALC] Cannot calculate formula recall: TP+FN = 0")

            else:
                logger.warning(f"[TRACE] Session {session_id} not found in database")

        except Exception as e:
            logger.error(f"[TRACE] Database verification failed: {e}")
            logger.error(traceback.format_exc())
        finally:
            db.close()

        return result

    # Apply instrumentation
    GroundTruthMatchingService._get_actual_ground_truth_count = instrumented_get_gt_count
    logger.info("[PATCH] Successfully applied logging to _get_actual_ground_truth_count")

    # Test with existing session
    test_session_id = '2c9a93f6-8471-4f2e-b1a7-06f239fca548'
    logger.info(f"[TEST] Testing with session: {test_session_id}")

    # Query session data first
    logger.info("[DB] Querying session from database...")
    db = SessionLocal()

    try:
        session = db.query(TestSession).filter(
            TestSession.id == test_session_id
        ).first()

        if session:
            logger.info(f"[SESSION] Found session: {session.id}")
            logger.info(f"[SESSION] Name: {session.name if hasattr(session, 'name') else 'N/A'}")
            logger.info(f"[SESSION] Status: {session.status if hasattr(session, 'status') else 'N/A'}")
            logger.info(f"[SESSION] TP: {session.true_positives if hasattr(session, 'true_positives') else 'N/A'}")
            logger.info(f"[SESSION] FP: {session.false_positives if hasattr(session, 'false_positives') else 'N/A'}")
            logger.info(f"[SESSION] FN: {session.false_negatives if hasattr(session, 'false_negatives') else 'N/A'}")
            logger.info(f"[SESSION] TN: {session.true_negatives if hasattr(session, 'true_negatives') else 'N/A'}")

            # Test recall calculation
            logger.info("[SERVICE] Testing GroundTruthMatchingService...")
            service = GroundTruthMatchingService()

            try:
                gt_count = service._get_actual_ground_truth_count(test_session_id)
                logger.info(f"[RESULT] GT count returned: {gt_count}")

                # Test full metrics calculation
                logger.info("[SERVICE] Testing full metrics calculation...")

                # Get detection results
                detection_count = db.query(DetectionEvent).filter(
                    DetectionEvent.session_id == test_session_id
                ).count()
                logger.info(f"[DATA] Detection results in session: {detection_count}")

                # Try to calculate metrics manually
                tp = session.true_positives if hasattr(session, 'true_positives') and session.true_positives else 0
                fp = session.false_positives if hasattr(session, 'false_positives') and session.false_positives else 0
                fn = session.false_negatives if hasattr(session, 'false_negatives') and session.false_negatives else 0

                logger.info(f"[MANUAL] TP={tp}, FP={fp}, FN={fn}, GT={gt_count}")

                if gt_count and gt_count > 0:
                    manual_recall = tp / gt_count
                    logger.info(f"[MANUAL] Calculated recall: {manual_recall:.4f}")
                else:
                    logger.warning(f"[MANUAL] Cannot calculate recall: gt_count={gt_count}")

                if (tp + fp) > 0:
                    manual_precision = tp / (tp + fp)
                    logger.info(f"[MANUAL] Calculated precision: {manual_precision:.4f}")
                else:
                    logger.warning(f"[MANUAL] Cannot calculate precision: TP+FP=0")

            except Exception as e:
                logger.error(f"[ERROR] Failed to get GT count: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.warning(f"[SESSION] Session {test_session_id} not found in database")
            logger.info("[SESSION] Checking all databases...")

            # Check all databases
            import glob
            for db_path in glob.glob('/home/rigade/Testing/ai-model-validation-platform/**/*.db', recursive=True):
                logger.info(f"[CHECK] Checking: {db_path}")
                try:
                    temp_engine = create_engine(f'sqlite:///{db_path}')
                    TempSession = sessionmaker(bind=temp_engine)
                    temp_db = TempSession()

                    session = temp_db.query(TestSession).filter(
                        TestSession.id == test_session_id
                    ).first()

                    if session:
                        logger.info(f"[FOUND] Session found in: {db_path}")
                        logger.info(f"[FOUND] TP: {session.true_positives if hasattr(session, 'true_positives') else 'N/A'}")
                        break
                    temp_db.close()
                except Exception as e:
                    logger.debug(f"[SKIP] {db_path}: {e}")
    finally:
        db.close()

    logger.info("="*80)
    logger.info("INSTRUMENTED TEST COMPLETE - SUCCESS")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    logger.info("Log saved to: /tmp/instrumented_test.log")
    logger.info("="*80)

except Exception as e:
    logger.error("="*80)
    logger.error("INSTRUMENTED TEST FAILED")
    logger.error(f"Error: {e}")
    logger.error(traceback.format_exc())
    logger.error("="*80)
    sys.exit(1)
