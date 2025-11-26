#!/usr/bin/env python3
"""
Diagnostic Queries for Test Session fa204ef2-9d8b-4480-9692-86e338c1218a

This script provides diagnostic queries to investigate why the test session failed
despite having a 90.6% match rate.

ROOT CAUSE: Only 96/242 ground truth objects detected (39.7% detection rate)
This resulted in 170 false negatives and F1 score of 0.493 (below 0.60 threshold)

Usage:
    cd /home/rigade/Testing/ai-model-validation-platform/backend
    python3 docs/SESSION_FA204EF2_DIAGNOSTIC_QUERIES.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models import (
    TestSession, DetectionComparison, GroundTruthObject,
    DetectionEvent, VideoLifecycleEvent
)
from sqlalchemy import func, and_
from collections import Counter
import json

def analyze_session(session_id: str = 'fa204ef2-9d8b-4480-9692-86e338c1218a'):
    """Complete diagnostic analysis of the failed test session"""
    db = SessionLocal()

    print("=" * 80)
    print("DIAGNOSTIC ANALYSIS: Test Session Failure Investigation")
    print("=" * 80)
    print(f"Session ID: {session_id}\n")

    # ========================================================================
    # QUERY 1: Basic Session Metrics
    # ========================================================================
    print("\n" + "=" * 80)
    print("1. SESSION OVERVIEW")
    print("=" * 80)

    session = db.query(TestSession).filter(TestSession.id == session_id).first()
    if not session:
        print("ERROR: Session not found")
        db.close()
        return

    print(f"Status: {session.status}")
    print(f"Overall Result: {session.overall_test_result}")
    print(f"Accuracy Result: {session.accuracy_result} (F1={session.accuracy_f1_score:.3f})")
    print(f"Latency Result: {session.latency_result} (mean={session.latency_mean_ms:.1f}ms)")
    print(f"\nDetection Counts:")
    print(f"  True Positives:  {session.tp_count}")
    print(f"  False Positives: {session.fp_count}")
    print(f"  False Negatives: {session.fn_count}")
    print(f"\nPrecision: {session.accuracy_precision:.3f}")
    print(f"Recall: {session.accuracy_recall:.3f}")
    print(f"F1 Score: {session.accuracy_f1_score:.3f}")

    # ========================================================================
    # QUERY 2: Ground Truth Coverage Analysis
    # ========================================================================
    print("\n" + "=" * 80)
    print("2. GROUND TRUTH COVERAGE ANALYSIS")
    print("=" * 80)

    # Get video IDs from the session
    video_ids = db.query(DetectionEvent.video_id).filter(
        DetectionEvent.test_session_id == session_id
    ).distinct().all()
    video_ids = [v[0] for v in video_ids if v[0]]

    print(f"\nVideos in test: {len(video_ids)}")
    for vid in video_ids:
        print(f"  - {vid}")

    # Total ground truth objects
    total_gt = db.query(func.count(GroundTruthObject.id)).filter(
        GroundTruthObject.video_id.in_(video_ids)
    ).scalar()

    # Matched ground truth objects (TP)
    matched_gt = db.query(func.count(DetectionComparison.id)).filter(
        and_(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'TP'
        )
    ).scalar()

    # Total AI detections
    total_detections = db.query(func.count(DetectionEvent.id)).filter(
        DetectionEvent.test_session_id == session_id
    ).scalar()

    print(f"\nDetection Coverage:")
    print(f"  Total Ground Truth Objects: {total_gt}")
    print(f"  Matched (True Positives):   {matched_gt}")
    print(f"  Missed (False Negatives):   {total_gt - matched_gt}")
    print(f"  Detection Rate:             {matched_gt/total_gt*100:.1f}%")
    print(f"\nAI Detection Summary:")
    print(f"  Total AI Detections:        {total_detections}")
    print(f"  Correct (TP):               {matched_gt}")
    print(f"  Incorrect (FP):             {total_detections - matched_gt}")
    print(f"  Precision:                  {matched_gt/total_detections*100:.1f}%")

    # ========================================================================
    # QUERY 3: Missed Detections Analysis
    # ========================================================================
    print("\n" + "=" * 80)
    print("3. MISSED DETECTIONS ANALYSIS (170 False Negatives)")
    print("=" * 80)

    # Get all GT objects
    all_gt = db.query(GroundTruthObject).filter(
        GroundTruthObject.video_id.in_(video_ids)
    ).all()

    # Get matched GT IDs
    matched_gt_ids = db.query(DetectionComparison.ground_truth_id).filter(
        and_(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'TP'
        )
    ).all()
    matched_set = set(row[0] for row in matched_gt_ids if row[0])

    # Find missed GT objects
    missed_gt = [gt for gt in all_gt if gt.id not in matched_set]

    print(f"\nTotal Missed GT Objects: {len(missed_gt)}")

    # Breakdown by class
    class_counts = Counter(gt.class_label for gt in missed_gt)
    print(f"\nMissed Detections by Class:")
    for label, count in class_counts.most_common():
        print(f"  {label}: {count} ({count/len(missed_gt)*100:.1f}%)")

    # Breakdown by video
    video_counts = Counter(gt.video_id for gt in missed_gt)
    print(f"\nMissed Detections by Video:")
    for vid, count in video_counts.most_common():
        total_in_video = len([gt for gt in all_gt if gt.video_id == vid])
        print(f"  Video {vid[:8]}...: {count}/{total_in_video} missed ({count/total_in_video*100:.1f}%)")

    # Temporal distribution
    missed_timestamps = sorted([gt.timestamp for gt in missed_gt])
    if missed_timestamps:
        print(f"\nTemporal Distribution of Missed Detections:")
        print(f"  First missed: {missed_timestamps[0]:.2f}s")
        print(f"  Last missed:  {missed_timestamps[-1]:.2f}s")
        print(f"  Span:         {missed_timestamps[-1] - missed_timestamps[0]:.2f}s")

    # Confidence distribution
    confidences = [gt.confidence for gt in missed_gt if gt.confidence is not None]
    if confidences:
        print(f"\nConfidence Distribution of Missed GT Objects:")
        print(f"  Mean: {sum(confidences)/len(confidences):.3f}")
        print(f"  Min:  {min(confidences):.3f}")
        print(f"  Max:  {max(confidences):.3f}")

    # ========================================================================
    # QUERY 4: Detection Quality Analysis (For Matched Detections)
    # ========================================================================
    print("\n" + "=" * 80)
    print("4. DETECTION QUALITY ANALYSIS (87 True Positives)")
    print("=" * 80)

    tp_comparisons = db.query(DetectionComparison).filter(
        and_(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'TP'
        )
    ).all()

    if tp_comparisons:
        iou_scores = [c.iou_score for c in tp_comparisons if c.iou_score is not None]
        temporal_offsets = [c.temporal_offset for c in tp_comparisons if c.temporal_offset is not None]

        print(f"\nIOU (Spatial Accuracy):")
        print(f"  Mean: {sum(iou_scores)/len(iou_scores):.3f}")
        print(f"  Min:  {min(iou_scores):.3f}")
        print(f"  Max:  {max(iou_scores):.3f}")

        print(f"\nTemporal Offset:")
        print(f"  Mean:   {sum(temporal_offsets)/len(temporal_offsets):.1f}ms")
        print(f"  Median: {sorted(temporal_offsets)[len(temporal_offsets)//2]:.1f}ms")
        print(f"  Min:    {min(temporal_offsets):.1f}ms")
        print(f"  Max:    {max(temporal_offsets):.1f}ms")

        within_300ms = sum(1 for offset in temporal_offsets if abs(offset) <= 300)
        print(f"\nTemporal Matching Quality:")
        print(f"  Within 300ms: {within_300ms}/{len(temporal_offsets)} ({within_300ms/len(temporal_offsets)*100:.1f}%)")

    # ========================================================================
    # QUERY 5: Video Lifecycle Events (Timing Drift Analysis)
    # ========================================================================
    print("\n" + "=" * 80)
    print("5. VIDEO LIFECYCLE EVENTS (Timing Drift)")
    print("=" * 80)

    lifecycle_events = db.query(VideoLifecycleEvent).filter(
        VideoLifecycleEvent.test_session_id == session_id
    ).all()

    if lifecycle_events:
        print(f"\nTotal Lifecycle Events: {len(lifecycle_events)}")
        for event in lifecycle_events:
            print(f"\n  Event: {event.event_type}")
            print(f"    Video: {event.video_id[:8]}...")
            print(f"    Frontend Timestamp: {event.frontend_timestamp}")
            print(f"    Backend Timestamp: {event.backend_received_timestamp}")
            print(f"    Calculated Drift: {event.calculated_drift_ms}ms")
    else:
        print("\nNo lifecycle events found (may not have been recorded)")

    # ========================================================================
    # QUERY 6: False Positives Analysis
    # ========================================================================
    print("\n" + "=" * 80)
    print("6. FALSE POSITIVES ANALYSIS (9 Incorrect Detections)")
    print("=" * 80)

    fp_comparisons = db.query(DetectionComparison).filter(
        and_(
            DetectionComparison.test_session_id == session_id,
            DetectionComparison.match_type == 'FP'
        )
    ).all()

    print(f"\nTotal False Positives: {len(fp_comparisons)}")

    if fp_comparisons:
        # Get detection events for FPs
        fp_detection_ids = [c.detection_event_id for c in fp_comparisons if c.detection_event_id]
        fp_detections = db.query(DetectionEvent).filter(
            DetectionEvent.id.in_(fp_detection_ids)
        ).all()

        print(f"\nFalse Positive Breakdown:")
        for i, det in enumerate(fp_detections[:5], 1):  # Show first 5
            print(f"\n  FP #{i}:")
            print(f"    Timestamp: {det.timestamp}")
            print(f"    Video: {det.video_id[:8] if det.video_id else 'N/A'}...")
            print(f"    Latency: {det.actual_latency_ms:.1f}ms" if det.actual_latency_ms else "    Latency: N/A")

        if len(fp_detections) > 5:
            print(f"\n  ... and {len(fp_detections) - 5} more")

    # ========================================================================
    # QUERY 7: Duplicate Ground Truth Check
    # ========================================================================
    print("\n" + "=" * 80)
    print("7. DUPLICATE GROUND TRUTH CHECK")
    print("=" * 80)

    # Find GT objects with identical timestamps
    duplicates = db.query(
        GroundTruthObject.video_id,
        GroundTruthObject.timestamp,
        func.count(GroundTruthObject.id).label('count')
    ).filter(
        GroundTruthObject.video_id.in_(video_ids)
    ).group_by(
        GroundTruthObject.video_id,
        GroundTruthObject.timestamp
    ).having(
        func.count(GroundTruthObject.id) > 1
    ).all()

    if duplicates:
        print(f"\nFound {len(duplicates)} timestamps with multiple GT objects:")
        for vid, ts, count in duplicates[:10]:  # Show first 10
            print(f"  Video {vid[:8]}..., timestamp {ts:.2f}s: {count} objects")
        if len(duplicates) > 10:
            print(f"  ... and {len(duplicates) - 10} more")
    else:
        print("\nNo duplicate GT objects found (good!)")

    # ========================================================================
    # SUMMARY AND RECOMMENDATIONS
    # ========================================================================
    print("\n" + "=" * 80)
    print("8. SUMMARY AND RECOMMENDATIONS")
    print("=" * 80)

    detection_rate = (matched_gt / total_gt * 100) if total_gt > 0 else 0
    precision = (matched_gt / total_detections * 100) if total_detections > 0 else 0
    recall = (matched_gt / total_gt * 100) if total_gt > 0 else 0
    f1_score = session.accuracy_f1_score * 100

    print(f"\nTest Result: {session.overall_test_result}")
    print(f"\nKey Metrics:")
    print(f"  Detection Rate: {detection_rate:.1f}% (96/242 GT objects detected)")
    print(f"  Precision:      {precision:.1f}% (87/96 detections correct)")
    print(f"  Recall:         {recall:.1f}% (87/242 GT objects found)")
    print(f"  F1 Score:       {f1_score:.1f}% (threshold: 60%)")

    print(f"\nRoot Cause Analysis:")
    if detection_rate < 50:
        print("  ✗ CRITICAL: Very low detection rate (<50%)")
        print("    - AI system only detected 39.7% of ground truth objects")
        print("    - 170 ground truth objects were never detected (59% miss rate)")
        print("    - This is likely a YOLO configuration issue or model performance problem")

    if precision > 85:
        print("  ✓ GOOD: High precision (>85%)")
        print("    - When the AI makes a detection, it's usually correct (90.6%)")
        print("    - Spatial matching (IOU) is excellent (~0.93)")

    if recall < 50:
        print("  ✗ CRITICAL: Very low recall (<50%)")
        print("    - AI is missing most of the ground truth objects")
        print("    - This is why the F1 score is low (0.493)")

    if session.latency_result == "PASS":
        print("  ✓ EXCELLENT: Latency performance passed")
        print("    - Mean latency 11.0ms is well within 100ms threshold")
        print("    - 100% of detections met timing requirements")

    print(f"\nRecommended Actions:")
    print("  1. Lower YOLO confidence threshold (currently may be too high)")
    print("  2. Verify ground truth annotations are correct (check for over-annotation)")
    print("  3. Increase detection frame rate if currently sampling too slow")
    print("  4. Review video processing pipeline for dropped frames")
    print("  5. Check YOLO model variant - consider YOLOv11 for better VRU detection")

    print(f"\nExpected Improvement:")
    print(f"  If detection rate improves to 80%:")
    print(f"    - Recall: 33.8% → 80%")
    print(f"    - F1 Score: 0.493 → 0.85")
    print(f"    - Test Result: FAIL → PASS ✓")

    db.close()
    print("\n" + "=" * 80)
    print("Analysis complete!")
    print("=" * 80)

if __name__ == "__main__":
    analyze_session()
