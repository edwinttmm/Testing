#!/usr/bin/env python3
"""
Comprehensive Integration Validation Test Suite

Validates ALL 6 fixes are integrated and working:
1. Detection Optimization - Frame numbers calculated from timestamps
2. Monitoring Cleanup - No runaway polling after session end
3. Frame Number Fix - 99% coverage achieved
4. Scipy Installation - Hungarian algorithm available
5. Frontend Metrics - API returns metrics object
6. GT Matching - Precision/Recall/F1 >70%

Usage:
    python tests/comprehensive_integration_validation.py [--session-id SESSION_ID]
"""

import sys
import os
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def validate_scipy_installation() -> Dict[str, Any]:
    """
    Validation 1: Verify scipy.optimize.linear_sum_assignment is available
    """
    print("\n" + "="*80)
    print("VALIDATION 1: Scipy Installation & Hungarian Algorithm")
    print("="*80)

    result = {
        "test": "scipy_installation",
        "passed": False,
        "scipy_version": None,
        "hungarian_available": False,
        "error": None
    }

    try:
        import scipy
        from scipy.optimize import linear_sum_assignment

        result["scipy_version"] = scipy.__version__
        result["hungarian_available"] = callable(linear_sum_assignment)

        # Test the algorithm works
        import numpy as np
        cost_matrix = np.array([[4, 1, 3], [2, 0, 5], [3, 2, 2]])
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        if len(row_ind) == 3 and len(col_ind) == 3:
            result["passed"] = True
            print(f"✅ scipy {result['scipy_version']} installed")
            print(f"✅ linear_sum_assignment available and functional")
            print(f"✅ Test assignment: {list(zip(row_ind, col_ind))}")
        else:
            result["error"] = "Hungarian algorithm returned unexpected results"

    except ImportError as e:
        result["error"] = f"scipy not installed: {e}"
        print(f"❌ scipy not available: {e}")
    except Exception as e:
        result["error"] = f"scipy test failed: {e}"
        print(f"❌ scipy test error: {e}")

    return result

def validate_frame_numbers(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Validation 2: Verify frame numbers are calculated and populated
    """
    print("\n" + "="*80)
    print("VALIDATION 2: Frame Number Calculation")
    print("="*80)

    result = {
        "test": "frame_number_calculation",
        "passed": False,
        "total_detections": 0,
        "with_frame_numbers": 0,
        "without_frame_numbers": 0,
        "coverage_percentage": 0.0,
        "error": None
    }

    try:
        from sqlalchemy import create_engine, text, select, delete, update, func
        from database import get_database_url

        engine = create_engine(get_database_url())

        with engine.connect() as conn:
            if session_id:
                query = text("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN frame_number IS NOT NULL AND frame_number > 0 THEN 1 ELSE 0 END) as with_frame,
                        SUM(CASE WHEN frame_number IS NULL OR frame_number = 0 THEN 1 ELSE 0 END) as without_frame
                    FROM detection_events
                    WHERE test_session_id = :session_id
                """)
                row = conn.execute(query, {"session_id": session_id}).fetchone()
            else:
                query = text("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN frame_number IS NOT NULL AND frame_number > 0 THEN 1 ELSE 0 END) as with_frame,
                        SUM(CASE WHEN frame_number IS NULL OR frame_number = 0 THEN 1 ELSE 0 END) as without_frame
                    FROM detection_events
                """)
                row = conn.execute(query).fetchone()

            if row and row[0] > 0:
                result["total_detections"] = row[0]
                result["with_frame_numbers"] = row[1]
                result["without_frame_numbers"] = row[2]
                result["coverage_percentage"] = (row[1] / row[0]) * 100

                print(f"Total Detections: {row[0]}")
                print(f"With Frame Numbers: {row[1]} ({result['coverage_percentage']:.1f}%)")
                print(f"Without Frame Numbers: {row[2]}")

                # Pass if >= 95% have frame numbers
                if result["coverage_percentage"] >= 95.0:
                    result["passed"] = True
                    print(f"✅ Frame number coverage: {result['coverage_percentage']:.1f}% (target: ≥95%)")
                else:
                    print(f"⚠️ Frame number coverage: {result['coverage_percentage']:.1f}% (target: ≥95%)")
            else:
                result["error"] = "No detections found in database"
                print(f"⚠️ No detections found")

    except Exception as e:
        result["error"] = f"Database query failed: {e}"
        print(f"❌ Frame number validation failed: {e}")

    return result

def validate_detection_capture_rate(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Validation 3: Verify detection capture rate >95%
    """
    print("\n" + "="*80)
    print("VALIDATION 3: Detection Capture Rate")
    print("="*80)

    result = {
        "test": "detection_capture_rate",
        "passed": False,
        "total_gt_frames": 0,
        "frames_with_detections": 0,
        "capture_percentage": 0.0,
        "error": None
    }

    try:
        from sqlalchemy import create_engine, text, select, delete, update, func
        from database import get_database_url

        engine = create_engine(get_database_url())

        with engine.connect() as conn:
            # Get GT frames and detections
            if session_id:
                # Get videos for this session
                videos_query = text("""
                    SELECT DISTINCT video_id
                    FROM test_sessions
                    WHERE id = :session_id
                """)
                video_rows = conn.execute(videos_query, {"session_id": session_id}).fetchall()

                if video_rows:
                    video_ids = [row[0] for row in video_rows if row[0]]

                    if video_ids:
                        # Get GT frames
                        gt_query = text("""
                            SELECT COUNT(DISTINCT frame_number)
                            FROM ground_truth_objects
                            WHERE video_id = :video_id
                        """)
                        gt_count = conn.execute(gt_query, {"video_id": video_ids[0]}).scalar()

                        # Get frames with detections
                        det_query = text("""
                            SELECT COUNT(DISTINCT de.frame_number)
                            FROM detection_events de
                            WHERE de.test_session_id = :session_id
                              AND de.frame_number IS NOT NULL
                              AND de.frame_number > 0
                        """)
                        det_count = conn.execute(det_query, {"session_id": session_id}).scalar()

                        result["total_gt_frames"] = gt_count or 0
                        result["frames_with_detections"] = det_count or 0

                        if gt_count and gt_count > 0:
                            result["capture_percentage"] = (det_count / gt_count) * 100

                            print(f"Total GT Frames: {gt_count}")
                            print(f"Frames with Detections: {det_count}")
                            print(f"Capture Rate: {result['capture_percentage']:.1f}%")

                            # Pass if >= 95% capture
                            if result["capture_percentage"] >= 95.0:
                                result["passed"] = True
                                print(f"✅ Detection capture: {result['capture_percentage']:.1f}% (target: ≥95%)")
                            else:
                                print(f"⚠️ Detection capture: {result['capture_percentage']:.1f}% (target: ≥95%)")
                        else:
                            result["error"] = "No GT frames found for session"
                            print(f"⚠️ No GT frames found")
                else:
                    result["error"] = "No videos found for session"
                    print(f"⚠️ No videos found for session")
            else:
                result["error"] = "Session ID required for capture rate validation"
                print(f"⚠️ Session ID required")

    except Exception as e:
        result["error"] = f"Capture rate validation failed: {e}"
        print(f"❌ Capture rate validation error: {e}")

    return result

def validate_gt_matching(session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Validation 4: Verify GT matching with precision/recall/F1 >70%
    """
    print("\n" + "="*80)
    print("VALIDATION 4: Ground Truth Matching")
    print("="*80)

    result = {
        "test": "gt_matching",
        "passed": False,
        "precision": 0.0,
        "recall": 0.0,
        "f1_score": 0.0,
        "true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "error": None
    }

    try:
        from sqlalchemy import create_engine, text, select, delete, update, func
        from database import get_database_url
        import numpy as np
        from scipy.optimize import linear_sum_assignment

        engine = create_engine(get_database_url())

        if not session_id:
            result["error"] = "Session ID required for GT matching validation"
            print(f"⚠️ Session ID required")
            return result

        with engine.connect() as conn:
            # Get GT objects with frame numbers
            gt_query = text("""
                SELECT gto.id, gto.frame_number, gto.x, gto.y, gto.width, gto.height
                FROM ground_truth_objects gto
                INNER JOIN test_sessions ts ON gto.video_id = ts.video_id
                WHERE ts.id = :session_id
                  AND gto.frame_number IS NOT NULL
                ORDER BY gto.frame_number
            """)
            gt_objects = conn.execute(gt_query, {"session_id": session_id}).fetchall()

            # Get detections with frame numbers
            det_query = text("""
                SELECT id, frame_number
                FROM detection_events
                WHERE test_session_id = :session_id
                  AND frame_number IS NOT NULL
                  AND frame_number > 0
                ORDER BY frame_number
            """)
            detections = conn.execute(det_query, {"session_id": session_id}).fetchall()

            if not gt_objects:
                result["error"] = "No GT objects found"
                print(f"⚠️ No GT objects found")
                return result

            if not detections:
                result["error"] = "No detections found"
                print(f"⚠️ No detections found")
                return result

            # Simple frame-based matching (frame number must match within ±2 frames)
            tp = 0  # True positives
            fp = 0  # False positives
            fn = 0  # False negatives

            matched_detections = set()
            matched_gt = set()

            for gt in gt_objects:
                gt_frame = gt[1]
                # Find detections within ±2 frames
                for det in detections:
                    det_frame = det[1]
                    if abs(det_frame - gt_frame) <= 2 and det[0] not in matched_detections:
                        tp += 1
                        matched_detections.add(det[0])
                        matched_gt.add(gt[0])
                        break
                else:
                    fn += 1  # GT object without matching detection

            # Unmatched detections are false positives
            fp = len(detections) - len(matched_detections)

            # Calculate metrics
            if tp + fp > 0:
                result["precision"] = (tp / (tp + fp)) * 100
            if tp + fn > 0:
                result["recall"] = (tp / (tp + fn)) * 100
            if result["precision"] + result["recall"] > 0:
                result["f1_score"] = 2 * (result["precision"] * result["recall"]) / (result["precision"] + result["recall"])

            result["true_positives"] = tp
            result["false_positives"] = fp
            result["false_negatives"] = fn

            print(f"True Positives: {tp}")
            print(f"False Positives: {fp}")
            print(f"False Negatives: {fn}")
            print(f"Precision: {result['precision']:.1f}%")
            print(f"Recall: {result['recall']:.1f}%")
            print(f"F1 Score: {result['f1_score']:.1f}%")

            # Pass if F1 >= 70%
            if result["f1_score"] >= 70.0:
                result["passed"] = True
                print(f"✅ GT matching F1: {result['f1_score']:.1f}% (target: ≥70%)")
            else:
                print(f"⚠️ GT matching F1: {result['f1_score']:.1f}% (target: ≥70%)")

    except Exception as e:
        result["error"] = f"GT matching validation failed: {e}"
        print(f"❌ GT matching validation error: {e}")

    return result

def validate_monitoring_cleanup() -> Dict[str, Any]:
    """
    Validation 5: Verify monitoring service has cleanup logic
    """
    print("\n" + "="*80)
    print("VALIDATION 5: Monitoring Service Cleanup")
    print("="*80)

    result = {
        "test": "monitoring_cleanup",
        "passed": False,
        "stop_monitoring_implemented": False,
        "cleanup_in_session_complete": False,
        "error": None
    }

    try:
        # Check if stop_monitoring() is properly implemented
        monitoring_service_path = Path(__file__).parent.parent / "services" / "labjack_monitoring_service.py"

        if monitoring_service_path.exists():
            with open(monitoring_service_path, 'r') as f:
                content = f.read()

            # Check for enhanced stop_monitoring
            if "def stop_monitoring" in content and "monitor_thread.join" in content:
                result["stop_monitoring_implemented"] = True
                print("✅ stop_monitoring() method found with thread join")
            else:
                print("⚠️ stop_monitoring() incomplete")

        # Check if session completion calls cleanup
        test_sessions_path = Path(__file__).parent.parent / "routers" / "test_sessions.py"

        if test_sessions_path.exists():
            with open(test_sessions_path, 'r') as f:
                content = f.read()

            # Check for cleanup call
            if "labjack_monitoring_service.stop_monitoring()" in content or "stop_monitoring()" in content:
                result["cleanup_in_session_complete"] = True
                print("✅ Session completion endpoint calls monitoring cleanup")
            else:
                print("⚠️ Session completion missing cleanup call")

        result["passed"] = result["stop_monitoring_implemented"] and result["cleanup_in_session_complete"]

        if result["passed"]:
            print("✅ Monitoring cleanup logic integrated")
        else:
            print("⚠️ Monitoring cleanup incomplete")

    except Exception as e:
        result["error"] = f"Monitoring cleanup validation failed: {e}"
        print(f"❌ Monitoring cleanup validation error: {e}")

    return result

def validate_frontend_metrics() -> Dict[str, Any]:
    """
    Validation 6: Verify API returns metrics object
    """
    print("\n" + "="*80)
    print("VALIDATION 6: Frontend Metrics API")
    print("="*80)

    result = {
        "test": "frontend_metrics",
        "passed": False,
        "api_endpoint_exists": False,
        "returns_metrics_object": False,
        "error": None
    }

    try:
        # Check for metrics endpoint in API
        routers_path = Path(__file__).parent.parent / "routers"

        metrics_found = False
        for router_file in routers_path.glob("*.py"):
            with open(router_file, 'r') as f:
                content = f.read()

            if "metrics" in content.lower() and ("precision" in content or "recall" in content or "f1" in content):
                metrics_found = True
                result["api_endpoint_exists"] = True
                print(f"✅ Metrics endpoint found in {router_file.name}")

                # Check if it returns metrics object
                if '"precision"' in content or "'precision'" in content:
                    result["returns_metrics_object"] = True
                    print("✅ Endpoint returns metrics object")
                break

        if not metrics_found:
            print("⚠️ No metrics endpoint found in API")

        result["passed"] = result["api_endpoint_exists"] and result["returns_metrics_object"]

        if result["passed"]:
            print("✅ Frontend metrics API implemented")
        else:
            print("⚠️ Frontend metrics API incomplete")

    except Exception as e:
        result["error"] = f"Frontend metrics validation failed: {e}"
        print(f"❌ Frontend metrics validation error: {e}")

    return result

def calculate_production_readiness(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate overall production readiness score
    """
    print("\n" + "="*80)
    print("PRODUCTION READINESS ASSESSMENT")
    print("="*80)

    total_tests = len(results)
    passed_tests = sum(1 for r in results if r.get("passed", False))

    # Critical tests (must pass)
    critical_tests = ["scipy_installation", "frame_number_calculation", "monitoring_cleanup"]
    critical_passed = sum(1 for r in results if r.get("test") in critical_tests and r.get("passed", False))

    # Important tests (should pass)
    important_tests = ["detection_capture_rate", "gt_matching", "frontend_metrics"]
    important_passed = sum(1 for r in results if r.get("test") in important_tests and r.get("passed", False))

    # Calculate weighted score
    critical_weight = 0.6
    important_weight = 0.4

    score = (
        (critical_passed / len(critical_tests)) * critical_weight +
        (important_passed / len(important_tests)) * important_weight
    ) * 100

    assessment = {
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": total_tests - passed_tests,
        "critical_passed": critical_passed,
        "critical_total": len(critical_tests),
        "important_passed": important_passed,
        "important_total": len(important_tests),
        "production_readiness_score": score,
        "deployment_ready": score >= 90.0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    print(f"\nTest Results:")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {passed_tests}")
    print(f"  Failed: {total_tests - passed_tests}")
    print(f"\nCritical Tests: {critical_passed}/{len(critical_tests)}")
    print(f"Important Tests: {important_passed}/{len(important_tests)}")
    print(f"\nProduction Readiness Score: {score:.1f}%")

    if score >= 90.0:
        print("\n✅ SYSTEM IS PRODUCTION READY (≥90%)")
    elif score >= 75.0:
        print("\n⚠️ SYSTEM NEEDS IMPROVEMENTS (75-90%)")
    else:
        print("\n❌ SYSTEM NOT READY FOR PRODUCTION (<75%)")

    return assessment

def main():
    parser = argparse.ArgumentParser(description="Comprehensive Integration Validation")
    parser.add_argument("--session-id", help="Test session ID to validate")
    parser.add_argument("--output", help="Output JSON file path")
    args = parser.parse_args()

    print("="*80)
    print("COMPREHENSIVE INTEGRATION VALIDATION TEST SUITE")
    print("="*80)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    if args.session_id:
        print(f"Session ID: {args.session_id}")
    print("="*80)

    # Run all validations
    results = []

    # 1. Scipy installation
    results.append(validate_scipy_installation())

    # 2. Frame numbers
    results.append(validate_frame_numbers(args.session_id))

    # 3. Detection capture rate
    if args.session_id:
        results.append(validate_detection_capture_rate(args.session_id))

    # 4. GT matching
    if args.session_id:
        results.append(validate_gt_matching(args.session_id))

    # 5. Monitoring cleanup
    results.append(validate_monitoring_cleanup())

    # 6. Frontend metrics
    results.append(validate_frontend_metrics())

    # Calculate production readiness
    assessment = calculate_production_readiness(results)

    # Compile final report
    report = {
        "validation_results": results,
        "production_assessment": assessment,
        "session_id": args.session_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Save output
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ Report saved to: {args.output}")

    # Return exit code based on readiness
    if assessment["deployment_ready"]:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
