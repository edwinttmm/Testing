#!/usr/bin/env python3
"""Diagnostic script to verify test session state"""
import sqlite3
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

def format_timestamp(ts: str) -> str:
    """Format timestamp for display"""
    if not ts:
        return "NOT SET"
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    except:
        return ts

def check_session(session_id: str, sequence_id: str):
    db_path = Path(__file__).parent.parent / "dev_database.db"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"\n{'='*80}")
    print(f"SESSION DIAGNOSTIC REPORT")
    print(f"{'='*80}")
    print(f"Session ID: {session_id}")
    print(f"Sequence ID: {sequence_id}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    # 1. Check Session Exists
    print("📋 SESSION INFORMATION")
    print("-" * 80)
    cursor.execute("""
        SELECT id, name, status, created_at, completed_at
        FROM test_sessions
        WHERE id = ?
    """, (session_id,))
    session = cursor.fetchone()

    if not session:
        print(f"❌ Session {session_id} not found!")
        conn.close()
        sys.exit(1)

    print(f"Name: {session['name']}")
    print(f"Status: {session['status']}")
    print(f"Created: {format_timestamp(session['created_at'])}")
    print(f"Completed: {format_timestamp(session['completed_at'])}")

    # Calculate metrics from detection events
    cursor.execute("""
        SELECT
            COUNT(*) as total_detections,
            SUM(CASE WHEN validation_result = 'TP' THEN 1 ELSE 0 END) as tp,
            SUM(CASE WHEN validation_result = 'FP' THEN 1 ELSE 0 END) as fp,
            SUM(CASE WHEN validation_result = 'FN' THEN 1 ELSE 0 END) as fn
        FROM detection_events
        WHERE test_session_id = ?
    """, (session_id,))
    metrics = cursor.fetchone()

    total_det = metrics['total_detections'] or 0
    tp = metrics['tp'] or 0
    fp = metrics['fp'] or 0
    fn = metrics['fn'] or 0

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print(f"Total Detections: {total_det}")
    print(f"Validation Results:")
    print(f"  - True Positives: {tp}")
    print(f"  - False Positives: {fp}")
    print(f"  - False Negatives: {fn}")
    print(f"Metrics:")
    print(f"  - Precision: {precision:.4f}")
    print(f"  - Recall: {recall:.4f}")
    print(f"  - F1 Score: {f1:.4f}")
    print()

    # 2. Check Video Test Sequence
    print("🎬 VIDEO TEST SEQUENCE INFORMATION")
    print("-" * 80)
    cursor.execute("""
        SELECT id, name, status, total_videos, completed_videos,
               sequence_start_time, sequence_end_time, total_duration_ms,
               created_at, updated_at
        FROM video_test_sequences
        WHERE test_session_id = ?
    """, (session_id,))
    vts = cursor.fetchone()

    if not vts:
        print(f"⚠️  No video test sequence found for this session")
    else:
        print(f"Sequence Name: {vts['name']}")
        print(f"Status: {vts['status']}")
        print(f"Total Videos: {vts['total_videos']}")
        print(f"Completed Videos: {vts['completed_videos']}")
        print(f"Start Time: {format_timestamp(str(vts['sequence_start_time'])) if vts['sequence_start_time'] else 'NOT SET'}")
        print(f"End Time: {format_timestamp(str(vts['sequence_end_time'])) if vts['sequence_end_time'] else 'NOT SET'}")
        print(f"Total Duration: {vts['total_duration_ms']:.2f}ms" if vts['total_duration_ms'] else "NOT CALCULATED")
    print()

    # 3. Check Sequence Video Results (video lifecycle)
    print("🎥 VIDEO LIFECYCLE INFORMATION")
    print("-" * 80)
    cursor.execute("""
        SELECT
            svr.id,
            svr.video_id,
            svr.sequence_order,
            svr.video_start_time,
            svr.video_end_time,
            svr.actual_duration_ms,
            svr.video_status,
            svr.validation_result,
            svr.actual_detection_count,
            svr.passed_detections,
            svr.failed_detections,
            svr.avg_latency_ms,
            v.filename,
            v.duration
        FROM sequence_video_results svr
        JOIN videos v ON svr.video_id = v.id
        WHERE svr.video_sequence_id = ?
        ORDER BY svr.sequence_order
    """, (sequence_id,))
    video_results = cursor.fetchall()

    if not video_results:
        print("❌ No video results found!")
    else:
        for vr in video_results:
            lifecycle_complete = bool(vr['video_start_time'] and vr['video_end_time'])
            print(f"\nVideo {vr['sequence_order']} (ID: {vr['video_id']})")
            print(f"  Filename: {vr['filename']}")
            print(f"  Video Duration: {vr['duration']:.2f}s")
            print(f"  Start Time: {format_timestamp(str(vr['video_start_time'])) if vr['video_start_time'] else 'NOT SET'}")
            print(f"  End Time: {format_timestamp(str(vr['video_end_time'])) if vr['video_end_time'] else 'NOT SET'}")
            print(f"  Actual Duration: {vr['actual_duration_ms']:.2f}ms" if vr['actual_duration_ms'] else "  Actual Duration: NOT CALCULATED")
            print(f"  Lifecycle Complete: {'✅ YES' if lifecycle_complete else '❌ NO'}")
            print(f"  Video Status: {vr['video_status']}")
            print(f"  Validation Result: {vr['validation_result'] or 'NOT SET'}")
            print(f"  Detection Count: {vr['actual_detection_count'] or 0}")
            print(f"  Passed: {vr['passed_detections'] or 0}, Failed: {vr['failed_detections'] or 0}")
            print(f"  Avg Latency: {vr['avg_latency_ms']:.2f}ms" if vr['avg_latency_ms'] else "  Avg Latency: N/A")
    print()

    # 4. Check Detection Events Per Video
    print("🔍 DETECTION EVENTS BREAKDOWN")
    print("-" * 80)
    cursor.execute("""
        SELECT
            de.video_id,
            svr.sequence_order,
            COUNT(de.id) as total_detections,
            SUM(CASE WHEN de.validation_result = 'TP' THEN 1 ELSE 0 END) as tp_count,
            SUM(CASE WHEN de.validation_result = 'FP' THEN 1 ELSE 0 END) as fp_count,
            SUM(CASE WHEN de.validation_result = 'FN' THEN 1 ELSE 0 END) as fn_count,
            SUM(CASE WHEN de.validation_result IS NULL THEN 1 ELSE 0 END) as unvalidated,
            MIN(de.detection_timestamp) as first_detection,
            MAX(de.detection_timestamp) as last_detection,
            AVG(de.actual_latency_ms) as avg_latency,
            MIN(de.actual_latency_ms) as min_latency,
            MAX(de.actual_latency_ms) as max_latency
        FROM detection_events de
        JOIN sequence_video_results svr ON de.video_id = svr.video_id
        WHERE de.test_session_id = ? AND svr.video_sequence_id = ?
        GROUP BY de.video_id, svr.sequence_order
        ORDER BY svr.sequence_order
    """, (session_id, sequence_id))
    detections = cursor.fetchall()

    if not detections:
        print("⚠️  No detection events found!")
    else:
        total_tp = 0
        total_fp = 0
        total_fn = 0
        total_unvalidated = 0

        for det in detections:
            print(f"\nVideo {det['sequence_order']} (ID: {det['video_id']})")
            print(f"  Total Detections: {det['total_detections']}")
            print(f"  Validation Status:")
            print(f"    - True Positives: {det['tp_count']}")
            print(f"    - False Positives: {det['fp_count']}")
            print(f"    - False Negatives: {det['fn_count']}")
            print(f"    - Unvalidated: {det['unvalidated']}")
            print(f"  Detection Timespan:")
            print(f"    - First: {format_timestamp(det['first_detection'])}")
            print(f"    - Last: {format_timestamp(det['last_detection'])}")
            print(f"  Latency Stats:")
            print(f"    - Average: {det['avg_latency']:.2f}ms" if det['avg_latency'] else "    - Average: N/A")
            print(f"    - Min: {det['min_latency']:.2f}ms" if det['min_latency'] else "    - Min: N/A")
            print(f"    - Max: {det['max_latency']:.2f}ms" if det['max_latency'] else "    - Max: N/A")

            total_tp += det['tp_count']
            total_fp += det['fp_count']
            total_fn += det['fn_count']
            total_unvalidated += det['unvalidated']

        print(f"\n{'─' * 80}")
        print(f"TOTALS ACROSS ALL VIDEOS:")
        print(f"  True Positives: {total_tp}")
        print(f"  False Positives: {total_fp}")
        print(f"  False Negatives: {total_fn}")
        print(f"  Unvalidated: {total_unvalidated}")
    print()

    # 5. Check Ground Truth
    print("📊 GROUND TRUTH INFORMATION")
    print("-" * 80)
    cursor.execute("""
        SELECT
            gt.video_id,
            svr.sequence_order,
            COUNT(gt.id) as gt_count,
            SUM(CASE WHEN gt.validated THEN 1 ELSE 0 END) as validated_count,
            MIN(gt.timestamp) as first_gt,
            MAX(gt.timestamp) as last_gt
        FROM ground_truth_objects gt
        JOIN sequence_video_results svr ON gt.video_id = svr.video_id
        WHERE svr.video_sequence_id = ? AND gt.deleted_at IS NULL
        GROUP BY gt.video_id, svr.sequence_order
        ORDER BY svr.sequence_order
    """, (sequence_id,))
    ground_truths = cursor.fetchall()

    if not ground_truths:
        print("⚠️  No ground truth data found!")
    else:
        total_gt = 0
        total_validated = 0

        for gt in ground_truths:
            validation_rate = (gt['validated_count'] / gt['gt_count'] * 100) if gt['gt_count'] > 0 else 0
            print(f"\nVideo {gt['sequence_order']} (ID: {gt['video_id']})")
            print(f"  Ground Truth Objects: {gt['gt_count']}")
            print(f"  Validated: {gt['validated_count']} ({validation_rate:.1f}%)")
            print(f"  Timespan:")
            print(f"    - First: {format_timestamp(str(gt['first_gt']))}")
            print(f"    - Last: {format_timestamp(str(gt['last_gt']))}")

            total_gt += gt['gt_count']
            total_validated += gt['validated_count']

        overall_validation_rate = (total_validated / total_gt * 100) if total_gt > 0 else 0
        print(f"\n{'─' * 80}")
        print(f"TOTALS:")
        print(f"  Total Ground Truth Objects: {total_gt}")
        print(f"  Total Validated: {total_validated} ({overall_validation_rate:.1f}%)")
    print()

    # 6. System Health Checks
    print("🏥 SYSTEM HEALTH CHECKS")
    print("-" * 80)

    health_issues = []

    # Check for videos without lifecycle completion
    if video_results:
        incomplete_videos = [v for v in video_results if not (v['video_start_time'] and v['video_end_time'])]
        if incomplete_videos:
            health_issues.append(f"⚠️  {len(incomplete_videos)} video(s) without complete lifecycle timestamps")

    # Check for detections without validation
    if detections:
        total_unval = sum(d['unvalidated'] for d in detections)
        if total_unval > 0:
            health_issues.append(f"⚠️  {total_unval} detection(s) without validation result")

    # Check for ground truth
    if ground_truths:
        total_gt_events = sum(gt['gt_count'] for gt in ground_truths)
        total_validated_events = sum(gt['validated_count'] for gt in ground_truths)
        if total_gt_events > 0 and total_validated_events == 0:
            health_issues.append(f"⚠️  No ground truth objects validated!")
        elif total_gt_events > 0:
            validation_rate = (total_validated_events / total_gt_events) * 100
            if validation_rate < 50:
                health_issues.append(f"⚠️  Low ground truth validation rate: {validation_rate:.1f}%")

    # Check session status
    if session['status'] not in ['completed', 'active']:
        health_issues.append(f"⚠️  Session status is '{session['status']}'")

    # Check detection count
    if total_det == 0:
        health_issues.append(f"❌ Zero detections recorded!")

    if health_issues:
        print("Issues Found:")
        for issue in health_issues:
            print(f"  {issue}")
    else:
        print("✅ All health checks passed!")

    print()
    print("=" * 80)
    print("END OF DIAGNOSTIC REPORT")
    print("=" * 80)

    conn.close()

if __name__ == "__main__":
    check_session(
        "feb6f74a-ddcc-4668-8404-90cb414d57ad",
        "472ac3e7-07e2-44e8-ba86-4d015a528e6d"
    )
