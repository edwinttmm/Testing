#!/usr/bin/env python3
"""
Verification Script: Check Video ID Assignment Status

This script verifies that the NULL video_id fix has been applied correctly
and provides detailed diagnostics about detection-to-video assignments.

Usage:
    # Check specific session:
    python3 scripts/verify_video_id_fix.py --session-id <SESSION_ID>

    # Check all recent sessions:
    python3 scripts/verify_video_id_fix.py --all

    # Generate detailed report:
    python3 scripts/verify_video_id_fix.py --session-id <SESSION_ID> --detailed

Author: AI Model Validation Platform Team
Date: 2025-01-04
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, List
from tabulate import tabulate

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text
from database import SessionLocal
from models import TestSession, DetectionEvent, SequenceVideoResult, Video


def check_session_video_ids(session_id: str, detailed: bool = False) -> Dict[str, Any]:
    """
    Check video_id assignment status for a session.

    Args:
        session_id: Session ID to check
        detailed: Whether to return detailed detection information

    Returns:
        Dict with verification results
    """
    db = SessionLocal()
    try:
        # Get session info
        session = db.query(TestSession).filter(TestSession.id == session_id).first()

        if not session:
            return {
                "success": False,
                "error": f"Session {session_id} not found"
            }

        # Count total detections
        total_detections = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id
        ).count()

        # Count NULL video_ids
        null_count = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_id.is_(None)
        ).count()

        # Get video_id distribution
        video_distribution = db.execute(text('''
            SELECT
                COALESCE(de.video_id, 'NULL') as video_id,
                COUNT(*) as count,
                MIN(de.timestamp) as min_timestamp,
                MAX(de.timestamp) as max_timestamp,
                v.filename
            FROM detection_events de
            LEFT JOIN videos v ON v.id = de.video_id
            WHERE de.test_session_id = :sid
            GROUP BY de.video_id, v.filename
            ORDER BY MIN(de.timestamp)
        '''), {"sid": session_id}).fetchall()

        # Build distribution dict
        distribution = []
        for row in video_distribution:
            video_id, count, min_ts, max_ts, filename = row
            distribution.append({
                "video_id": video_id,
                "count": count,
                "min_timestamp": min_ts,
                "max_timestamp": max_ts,
                "filename": filename or "N/A",
                "percentage": (count / total_detections * 100) if total_detections > 0 else 0
            })

        # Check for detections with missing relative timestamps
        missing_relative_ts = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_relative_timestamp.is_(None),
            DetectionEvent.video_id.isnot(None)
        ).count()

        # Check for detections with missing frame numbers
        missing_frame_numbers = db.query(DetectionEvent).filter(
            DetectionEvent.test_session_id == session_id,
            DetectionEvent.video_frame_number.is_(None),
            DetectionEvent.video_id.isnot(None)
        ).count()

        # Get sequence video results if multi-video session
        sequence_results = []
        if session.has_video_sequence and session.sequence_id:
            video_results = db.query(SequenceVideoResult).filter(
                SequenceVideoResult.video_sequence_id == session.sequence_id
            ).order_by(SequenceVideoResult.sequence_order).all()

            for vr in video_results:
                video = db.query(Video).filter(Video.id == vr.video_id).first()
                sequence_results.append({
                    "video_id": vr.video_id,
                    "filename": video.filename if video else "N/A",
                    "sequence_order": vr.sequence_order,
                    "start_time": vr.video_start_time,
                    "end_time": vr.video_end_time,
                    "duration_ms": vr.actual_duration_ms,
                    "expected_detections": vr.expected_detection_count,
                    "actual_detections": vr.actual_detection_count
                })

        # Detailed detection info (if requested)
        detection_details = []
        if detailed:
            detections = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id
            ).order_by(DetectionEvent.timestamp).all()

            for det in detections:
                detection_details.append({
                    "id": det.id,
                    "timestamp": det.timestamp,
                    "video_id": det.video_id or "NULL",
                    "video_relative_timestamp": det.video_relative_timestamp,
                    "video_frame_number": det.video_frame_number,
                    "sequence_video_result_id": det.sequence_video_result_id
                })

        return {
            "success": True,
            "session_id": session_id,
            "session_status": session.status,
            "has_video_sequence": session.has_video_sequence,
            "total_detections": total_detections,
            "null_video_ids": null_count,
            "null_percentage": (null_count / total_detections * 100) if total_detections > 0 else 0,
            "video_distribution": distribution,
            "missing_relative_timestamps": missing_relative_ts,
            "missing_frame_numbers": missing_frame_numbers,
            "sequence_results": sequence_results,
            "detection_details": detection_details if detailed else [],
            "is_fixed": null_count == 0 and missing_relative_ts == 0
        }

    finally:
        db.close()


def print_verification_report(result: Dict[str, Any]):
    """Print formatted verification report."""
    if not result["success"]:
        print(f"❌ ERROR: {result.get('error', 'Unknown error')}")
        return

    print("="*80)
    print(f"VIDEO ID ASSIGNMENT VERIFICATION REPORT")
    print("="*80)
    print(f"Session ID: {result['session_id']}")
    print(f"Session Status: {result['session_status']}")
    print(f"Multi-Video Sequence: {'Yes' if result['has_video_sequence'] else 'No'}")
    print(f"Total Detections: {result['total_detections']}")
    print()

    # Status check
    if result['is_fixed']:
        print("✅ STATUS: PASSED - All detections have valid video_ids and metadata")
    else:
        print("⚠️ STATUS: ISSUES DETECTED")
        if result['null_video_ids'] > 0:
            print(f"  • {result['null_video_ids']} detections have NULL video_id ({result['null_percentage']:.1f}%)")
        if result['missing_relative_timestamps'] > 0:
            print(f"  • {result['missing_relative_timestamps']} detections missing relative timestamps")
        if result['missing_frame_numbers'] > 0:
            print(f"  • {result['missing_frame_numbers']} detections missing frame numbers")

    print()
    print("-"*80)
    print("VIDEO DISTRIBUTION:")
    print("-"*80)

    # Create table data
    table_data = []
    for dist in result['video_distribution']:
        table_data.append([
            dist['video_id'][:36],
            dist['filename'],
            dist['count'],
            f"{dist['percentage']:.1f}%",
            f"{dist['min_timestamp']:.3f}s" if dist['min_timestamp'] else "N/A",
            f"{dist['max_timestamp']:.3f}s" if dist['max_timestamp'] else "N/A"
        ])

    headers = ["Video ID", "Filename", "Count", "Percentage", "Min Time", "Max Time"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))

    # Sequence results (if available)
    if result['sequence_results']:
        print()
        print("-"*80)
        print("SEQUENCE VIDEO RESULTS:")
        print("-"*80)

        seq_table_data = []
        for sr in result['sequence_results']:
            seq_table_data.append([
                sr['sequence_order'],
                sr['filename'],
                f"{sr['start_time']:.3f}s" if sr['start_time'] else "N/A",
                f"{sr['end_time']:.3f}s" if sr['end_time'] else "N/A",
                f"{sr['duration_ms']/1000:.2f}s" if sr['duration_ms'] else "N/A",
                sr['expected_detections'],
                sr['actual_detections']
            ])

        seq_headers = ["Order", "Filename", "Start", "End", "Duration", "Expected", "Actual"]
        print(tabulate(seq_table_data, headers=seq_headers, tablefmt="grid"))

    # Detection details (if requested)
    if result['detection_details']:
        print()
        print("-"*80)
        print("DETECTION DETAILS (First 20):")
        print("-"*80)

        det_table_data = []
        for det in result['detection_details'][:20]:
            det_table_data.append([
                det['id'][:16],
                f"{det['timestamp']:.3f}s",
                det['video_id'][:16] if det['video_id'] != "NULL" else "NULL",
                f"{det['video_relative_timestamp']:.3f}s" if det['video_relative_timestamp'] else "NULL",
                det['video_frame_number'] if det['video_frame_number'] is not None else "NULL"
            ])

        det_headers = ["Detection ID", "Timestamp", "Video ID", "Relative Time", "Frame #"]
        print(tabulate(det_table_data, headers=det_headers, tablefmt="grid"))

        if len(result['detection_details']) > 20:
            print(f"\n... and {len(result['detection_details']) - 20} more detections")

    print()


def check_all_sessions(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Check video_id status for all recent sessions.

    Args:
        limit: Maximum number of sessions to check

    Returns:
        List of verification results
    """
    db = SessionLocal()
    try:
        # Get recent sessions with detections
        sessions = db.execute(text('''
            SELECT DISTINCT ts.id, ts.status, ts.has_video_sequence, ts.created_at
            FROM test_sessions ts
            INNER JOIN detection_events de ON de.test_session_id = ts.id
            ORDER BY ts.created_at DESC
            LIMIT :limit
        '''), {"limit": limit}).fetchall()

        results = []
        for session_id, status, has_sequence, created_at in sessions:
            result = check_session_video_ids(session_id, detailed=False)
            results.append(result)

        return results

    finally:
        db.close()


def print_summary_table(results: List[Dict[str, Any]]):
    """Print summary table for multiple sessions."""
    print("="*80)
    print(f"VIDEO ID ASSIGNMENT SUMMARY ({len(results)} sessions)")
    print("="*80)

    table_data = []
    for result in results:
        if not result["success"]:
            continue

        status_icon = "✅" if result["is_fixed"] else "⚠️"
        null_pct = result["null_percentage"]

        table_data.append([
            status_icon,
            result["session_id"][:16],
            result["session_status"],
            "Yes" if result["has_video_sequence"] else "No",
            result["total_detections"],
            result["null_video_ids"],
            f"{null_pct:.1f}%"
        ])

    headers = ["Status", "Session ID", "Status", "Multi-Video", "Total", "NULL", "%"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()

    # Summary statistics
    total_sessions = len([r for r in results if r["success"]])
    fixed_sessions = len([r for r in results if r["success"] and r["is_fixed"]])
    sessions_with_nulls = len([r for r in results if r["success"] and r["null_video_ids"] > 0])

    print(f"Summary:")
    print(f"  • Total sessions checked: {total_sessions}")
    print(f"  • Sessions fully fixed: {fixed_sessions} ({fixed_sessions/total_sessions*100:.1f}%)")
    print(f"  • Sessions with NULL video_ids: {sessions_with_nulls}")


def main():
    """Main entry point for verification script."""
    parser = argparse.ArgumentParser(
        description="Verify video_id assignment status for detection events",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--session-id",
        type=str,
        help="Specific session ID to verify"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all recent sessions"
    )

    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Include detailed detection information"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of sessions to check when using --all (default: 10)"
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.session_id and not args.all:
        parser.error("Must specify either --session-id or --all")

    if args.session_id and args.all:
        parser.error("Cannot specify both --session-id and --all")

    try:
        if args.session_id:
            # Single session verification
            result = check_session_video_ids(args.session_id, detailed=args.detailed)
            print_verification_report(result)

            # Exit with appropriate code
            sys.exit(0 if result.get("is_fixed", False) else 1)

        else:
            # Multiple session verification
            results = check_all_sessions(limit=args.limit)
            print_summary_table(results)

            # Exit code based on whether all sessions are fixed
            all_fixed = all(r.get("is_fixed", False) for r in results if r["success"])
            sys.exit(0 if all_fixed else 1)

    except Exception as e:
        print(f"❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
