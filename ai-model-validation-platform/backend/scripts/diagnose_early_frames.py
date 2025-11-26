#!/usr/bin/env python3
"""
Diagnostic script to investigate why early frames (0, 1, 3, 4, 6, 8) have no detection matched.

This script analyzes:
1. Detection timestamps vs ground truth frame timestamps
2. Time gaps between GT frames and nearest detections
3. Whether gaps exceed tolerance threshold
4. Distribution of detections across video timeline

Usage:
    python scripts/diagnose_early_frames.py <session_id>
    python scripts/diagnose_early_frames.py --latest  # Use latest session
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from sqlalchemy import text
from typing import List, Tuple


def get_latest_session_id(db) -> str:
    """Get the most recent test session ID."""
    query = text("SELECT id FROM test_sessions ORDER BY created_at DESC LIMIT 1")
    result = db.execute(query).fetchone()
    return result[0] if result else None


def diagnose_early_frame_issue(session_id: str):
    """Diagnose why early frames have no detection matched."""
    db = SessionLocal()

    try:
        # Verify session exists
        session_query = text("SELECT id, video_id, tolerance_ms FROM test_sessions WHERE id = :session_id")
        session = db.execute(session_query, {'session_id': session_id}).fetchone()

        if not session:
            print(f"❌ Session {session_id} not found")
            return

        video_id = session[1]
        tolerance_ms = session[2] or 100  # Default to 100ms

        print(f"=" * 80)
        print(f"SESSION: {session_id}")
        print(f"VIDEO:   {video_id}")
        print(f"TOLERANCE: {tolerance_ms}ms")
        print(f"=" * 80)

        # Get detections
        det_query = text("""
            SELECT id, timestamp, video_relative_timestamp, frame_number
            FROM detection_events
            WHERE test_session_id = :session_id
            ORDER BY timestamp
        """)
        detections = db.execute(det_query, {'session_id': session_id}).fetchall()

        # Get GT
        gt_query = text("""
            SELECT id, timestamp, frame_number
            FROM ground_truth_objects
            WHERE video_id = :video_id
            ORDER BY timestamp
        """)
        ground_truths = db.execute(gt_query, {'video_id': video_id}).fetchall()

        print(f"\nDETECTIONS: {len(detections)} total")
        print(f"GROUND TRUTH: {len(ground_truths)} total")

        if not detections:
            print("\n❌ NO DETECTIONS FOUND")
            return

        if not ground_truths:
            print("\n❌ NO GROUND TRUTH FOUND")
            return

        # Show earliest detections
        print(f"\n{'=' * 80}")
        print(f"FIRST 15 DETECTIONS")
        print(f"{'=' * 80}")
        for i, det in enumerate(detections[:15]):
            det_id, timestamp, video_rel, frame = det
            print(f"Det {i:2d}: ts={timestamp:10.6f}s, "
                  f"video_rel={str(video_rel):>10s}s, frame={frame}")

        # Show earliest GT frames
        print(f"\n{'=' * 80}")
        print(f"FIRST 15 GROUND TRUTH FRAMES")
        print(f"{'=' * 80}")
        for gt in ground_truths[:15]:
            gt_id, timestamp, frame = gt
            print(f"GT Frame {frame:2d}: ts={timestamp:.6f}s")

        # Calculate gaps for early frames
        print(f"\n{'=' * 80}")
        print(f"FRAME-TO-DETECTION GAP ANALYSIS (tolerance={tolerance_ms}ms)")
        print(f"{'=' * 80}")

        tolerance_seconds = tolerance_ms / 1000.0
        no_match_frames = []

        for gt in ground_truths[:20]:  # Analyze first 20 frames
            gt_id, gt_time, gt_frame = gt

            # Find closest detection
            closest_det = None
            min_gap = float('inf')

            for det in detections:
                det_id, det_time, video_rel, det_frame = det
                # Use video_relative_timestamp if available, otherwise timestamp
                effective_time = video_rel if video_rel is not None else det_time
                gap = abs(effective_time - gt_time)

                if gap < min_gap:
                    min_gap = gap
                    closest_det = (det_id, effective_time, det_frame)

            gap_ms = min_gap * 1000

            if min_gap <= tolerance_seconds:
                status = "✅ MATCH"
                symbol = "✓"
            else:
                status = "❌ NO MATCH"
                symbol = "✗"
                no_match_frames.append((gt_frame, gt_time, gap_ms))

            if closest_det:
                det_id, det_time, det_frame = closest_det
                print(f"{symbol} Frame {gt_frame:2d} (ts={gt_time:.3f}s): "
                      f"closest det at {det_time:.3f}s (frame {det_frame}), "
                      f"gap={gap_ms:6.1f}ms {status}")
            else:
                print(f"{symbol} Frame {gt_frame:2d} (ts={gt_time:.3f}s): "
                      f"NO DETECTIONS AVAILABLE")

        # Summary
        print(f"\n{'=' * 80}")
        print(f"SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total frames analyzed: {min(20, len(ground_truths))}")
        print(f"Frames with NO MATCH: {len(no_match_frames)}")

        if no_match_frames:
            print(f"\nFrames with no match:")
            for frame, gt_time, gap_ms in no_match_frames:
                print(f"  - Frame {frame:2d}: gap={gap_ms:.1f}ms (exceeds {tolerance_ms}ms tolerance)")

        # Check for detection startup delay
        if detections:
            first_det_time = detections[0][1]  # timestamp of first detection
            first_gt_time = ground_truths[0][1] if ground_truths else 0

            startup_delay_ms = (first_det_time - first_gt_time) * 1000

            print(f"\n{'=' * 80}")
            print(f"DETECTION STARTUP DELAY ANALYSIS")
            print(f"{'=' * 80}")
            print(f"First GT frame: {first_gt_time:.6f}s")
            print(f"First detection: {first_det_time:.6f}s")
            print(f"Startup delay: {startup_delay_ms:.1f}ms")

            if startup_delay_ms > tolerance_ms:
                print(f"\n⚠️  WARNING: Startup delay ({startup_delay_ms:.1f}ms) "
                      f"exceeds tolerance ({tolerance_ms}ms)")
                print(f"   This will cause early frames to have NO MATCH")

        # Check detection density
        print(f"\n{'=' * 80}")
        print(f"DETECTION DENSITY ANALYSIS")
        print(f"{'=' * 80}")

        if len(detections) > 1:
            det_times = [d[1] for d in detections]
            time_span = det_times[-1] - det_times[0]
            avg_interval_ms = (time_span / (len(detections) - 1)) * 1000

            print(f"Detection time span: {time_span:.3f}s")
            print(f"Average detection interval: {avg_interval_ms:.1f}ms")
            print(f"Detections per second: {len(detections) / time_span:.1f}")

        # Check for sparse regions
        print(f"\n{'=' * 80}")
        print(f"DETECTION GAPS (intervals > {tolerance_ms}ms)")
        print(f"{'=' * 80}")

        large_gaps = []
        for i in range(len(detections) - 1):
            gap = (detections[i + 1][1] - detections[i][1]) * 1000
            if gap > tolerance_ms:
                large_gaps.append((i, gap))

        if large_gaps:
            print(f"Found {len(large_gaps)} large gaps between detections:")
            for idx, gap_ms in large_gaps[:10]:  # Show first 10
                print(f"  - Between det {idx} and {idx + 1}: {gap_ms:.1f}ms")
        else:
            print(f"No gaps larger than {tolerance_ms}ms found")

        # Recommendations
        print(f"\n{'=' * 80}")
        print(f"RECOMMENDATIONS")
        print(f"{'=' * 80}")

        if no_match_frames:
            max_gap = max(gap for _, _, gap in no_match_frames)
            recommended_tolerance = int(max_gap) + 20  # Add 20ms buffer

            print(f"1. INCREASE TOLERANCE:")
            print(f"   Current: {tolerance_ms}ms")
            print(f"   Recommended: {recommended_tolerance}ms (to cover {max_gap:.1f}ms gap)")

        if detections and startup_delay_ms > 50:
            print(f"\n2. ADDRESS STARTUP DELAY:")
            print(f"   Detection system has {startup_delay_ms:.1f}ms startup delay")
            print(f"   Options:")
            print(f"   - Apply voltage earlier before video starts")
            print(f"   - Ignore GT frames before first detection")
            print(f"   - Add startup compensation to matching logic")

        if large_gaps:
            print(f"\n3. IMPROVE DETECTION CONSISTENCY:")
            print(f"   Found {len(large_gaps)} gaps > {tolerance_ms}ms between detections")
            print(f"   This suggests sparse/irregular detection pattern")

    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_early_frames.py <session_id>")
        print("   or: python scripts/diagnose_early_frames.py --latest")
        sys.exit(1)

    db = SessionLocal()
    try:
        if sys.argv[1] == '--latest':
            session_id = get_latest_session_id(db)
            if not session_id:
                print("❌ No sessions found in database")
                sys.exit(1)
            print(f"Using latest session: {session_id}\n")
        else:
            session_id = sys.argv[1]

        diagnose_early_frame_issue(session_id)
    finally:
        db.close()
