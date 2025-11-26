#!/usr/bin/env python3
"""
Per-Video Detection Rate Breakdown Analysis
Session: fa204ef2-9d8b-4480-9692-86e338c1218a
"""

import sqlite3
import json
from collections import defaultdict
from typing import Dict, List, Tuple

def connect_db(db_path: str = "dev_database.db"):
    """Connect to the SQLite database."""
    return sqlite3.connect(db_path)

def get_session_info(conn, session_id: str):
    """Get basic session information."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, status, created_at, completed_at,
               actual_detections, expected_detections,
               tp_count, fp_count, fn_count,
               pass_fail_result, accuracy_f1_score,
               accuracy_precision, accuracy_recall
        FROM test_sessions
        WHERE id = ?
    """, (session_id,))
    return cursor.fetchone()

def get_videos_for_session(conn, session_id: str):
    """Get all videos associated with this session."""
    cursor = conn.cursor()

    # First try to find videos directly linked to the session
    cursor.execute("""
        SELECT DISTINCT v.file_path, v.id, v.filename
        FROM videos v
        JOIN test_sessions ts ON ts.video_id = v.id
        WHERE ts.id = ?
    """, (session_id,))

    videos = cursor.fetchall()

    if not videos:
        # Try through detection_events
        cursor.execute("""
            SELECT DISTINCT v.file_path, v.id, v.filename
            FROM videos v
            JOIN detection_events de ON de.video_id = v.id
            WHERE de.test_session_id = ?
        """, (session_id,))
        videos = cursor.fetchall()

    if not videos:
        # Try through ground_truth_objects
        cursor.execute("""
            SELECT DISTINCT v.file_path, v.id, v.filename
            FROM videos v
            JOIN ground_truth_objects gt ON gt.video_id = v.id
            WHERE EXISTS (
                SELECT 1 FROM test_sessions ts
                WHERE ts.id = ? AND ts.video_id = v.id
            )
        """, (session_id,))
        videos = cursor.fetchall()

    return videos

def get_ground_truth_by_video(conn, session_id: str, video_path: str = None, video_id: str = None):
    """Get all ground truth events for a specific video."""
    cursor = conn.cursor()

    if video_id:
        cursor.execute("""
            SELECT id, class_label as event_type, frame_number, timestamp,
                   bounding_box, confidence, video_id, tracking_id
            FROM ground_truth_objects
            WHERE video_id = ? AND deleted_at IS NULL
            ORDER BY frame_number
        """, (video_id,))
    else:
        return []

    return cursor.fetchall()

def get_detections_by_video(conn, session_id: str, video_path: str = None, video_id: str = None):
    """Get all detections for a specific video."""
    cursor = conn.cursor()

    if video_id:
        cursor.execute("""
            SELECT id, class_label as event_type, frame_number, timestamp,
                   CASE
                     WHEN bounding_box_x IS NOT NULL THEN
                       json_object('x', bounding_box_x, 'y', bounding_box_y,
                                   'width', bounding_box_width, 'height', bounding_box_height)
                     ELSE NULL
                   END as bounding_box,
                   confidence,
                   CASE WHEN validation_result = 'TP' THEN 1 ELSE 0 END as is_true_positive,
                   ground_truth_match_id, video_id
            FROM detection_events
            WHERE test_session_id = ? AND video_id = ?
            ORDER BY frame_number
        """, (session_id, video_id))
    else:
        return []

    return cursor.fetchall()

def analyze_frame_coverage(ground_truths: List, detections: List):
    """Analyze which frames have GT events and which have detections."""
    gt_frames = set()
    detection_frames = set()

    for gt in ground_truths:
        frame_num = gt[2]  # frame_number is 3rd column
        if frame_num is not None:
            gt_frames.add(frame_num)

    for det in detections:
        frame_num = det[2]  # frame_number is 3rd column
        if frame_num is not None:
            detection_frames.add(frame_num)

    missed_frames = sorted(gt_frames - detection_frames)
    detected_frames = sorted(gt_frames & detection_frames)

    return {
        'gt_frames': sorted(gt_frames),
        'detection_frames': sorted(detection_frames),
        'missed_frames': missed_frames,
        'detected_frames': detected_frames,
        'frame_range': (min(gt_frames) if gt_frames else 0,
                       max(gt_frames) if gt_frames else 0)
    }

def identify_missing_pattern(missed_frames: List[int], detected_frames: List[int]):
    """Identify patterns in missing frames."""
    if not missed_frames:
        return "No missing frames"

    # Check if frames are clustered
    gaps = []
    for i in range(len(missed_frames) - 1):
        gap = missed_frames[i + 1] - missed_frames[i]
        gaps.append(gap)

    if not gaps:
        return f"Single missed frame: {missed_frames[0]}"

    avg_gap = sum(gaps) / len(gaps) if gaps else 0

    patterns = []

    # Check for systematic skipping (every Nth frame)
    if len(missed_frames) >= 3:
        frame_diffs = [missed_frames[i+1] - missed_frames[i] for i in range(len(missed_frames)-1)]
        if len(set(frame_diffs)) == 1:
            patterns.append(f"Systematic skip pattern: every {frame_diffs[0]} frames")

    # Check for clustered missing frames
    consecutive_groups = []
    current_group = [missed_frames[0]]
    for i in range(1, len(missed_frames)):
        if missed_frames[i] - missed_frames[i-1] == 1:
            current_group.append(missed_frames[i])
        else:
            if len(current_group) > 1:
                consecutive_groups.append(current_group)
            current_group = [missed_frames[i]]
    if len(current_group) > 1:
        consecutive_groups.append(current_group)

    if consecutive_groups:
        patterns.append(f"Clustered missing frames: {len(consecutive_groups)} groups")
        for group in consecutive_groups[:3]:  # Show first 3 groups
            patterns.append(f"  - Frames {group[0]} to {group[-1]} ({len(group)} consecutive)")

    # Check for random distribution
    if avg_gap > 10 and len(set(gaps)) > len(gaps) * 0.7:
        patterns.append(f"Random/sparse missing frames (avg gap: {avg_gap:.1f})")

    return "; ".join(patterns) if patterns else f"Irregular pattern (avg gap: {avg_gap:.1f})"

def calculate_video_metrics(ground_truths: List, detections: List):
    """Calculate detailed metrics for a single video."""
    total_gt = len(ground_truths)
    total_detections = len(detections)

    # Count true positives (detections that matched GT)
    true_positives = sum(1 for det in detections if det[6])  # is_true_positive column

    # Count which GT events were matched
    matched_gt_ids = set(det[7] for det in detections if det[7])  # matched_ground_truth_id
    false_negatives = total_gt - len(matched_gt_ids)

    detection_rate = (true_positives / total_gt * 100) if total_gt > 0 else 0

    return {
        'total_gt': total_gt,
        'total_detections': total_detections,
        'true_positives': true_positives,
        'false_negatives': false_negatives,
        'detection_rate': detection_rate,
        'matched_gt_ids': matched_gt_ids
    }

def main():
    session_id = "fa204ef2-9d8b-4480-9692-86e338c1218a"

    print("=" * 80)
    print("PER-VIDEO DETECTION BREAKDOWN ANALYSIS")
    print("=" * 80)
    print(f"\nSession: {session_id}\n")

    conn = connect_db()

    # Get session overview
    session_info = get_session_info(conn, session_id)
    if session_info:
        (sess_id, status, created, completed, actual_det, expected_det,
         tp_count, fp_count, fn_count, pass_fail, f1_score, precision, recall) = session_info
        print(f"SESSION OVERVIEW:")
        print(f"- Status: {status}")
        print(f"- Expected Detections (GT): {expected_det}")
        print(f"- Actual Detections: {actual_det}")
        print(f"- True Positives: {tp_count}")
        print(f"- False Positives: {fp_count}")
        print(f"- False Negatives: {fn_count}")
        print(f"- Overall Detection Rate: {(tp_count / expected_det * 100) if expected_det and expected_det > 0 else 0:.1f}%")
        print(f"- Pass/Fail: {pass_fail}")
        if f1_score is not None:
            print(f"- F1 Score: {f1_score:.3f}")
        if precision is not None:
            print(f"- Precision: {precision:.3f}")
        if recall is not None:
            print(f"- Recall: {recall:.3f}")
    else:
        print("Session not found!")
        conn.close()
        return

    print("\n" + "=" * 80)

    # Get videos
    videos = get_videos_for_session(conn, session_id)

    if not videos:
        print("No videos found for this session!")
        conn.close()
        return

    print(f"\nFound {len(videos)} video(s) in session\n")

    video_results = []

    for idx, (video_path, video_id, video_filename) in enumerate(videos, 1):
        print("=" * 80)
        print(f"VIDEO {idx}:")
        print("=" * 80)
        print(f"- Video Filename: {video_filename or 'N/A'}")
        print(f"- Video Path: {video_path or 'N/A'}")
        print(f"- Video ID: {video_id or 'N/A'}")

        # Get ground truth and detections
        ground_truths = get_ground_truth_by_video(conn, session_id, video_path, video_id)
        detections = get_detections_by_video(conn, session_id, video_path, video_id)

        # Calculate metrics
        metrics = calculate_video_metrics(ground_truths, detections)

        print(f"\nMETRICS:")
        print(f"- Total GT Events: {metrics['total_gt']}")
        print(f"- Detections Captured (TP): {metrics['true_positives']}")
        print(f"- Detection Rate: {metrics['detection_rate']:.1f}%")
        print(f"- False Negatives: {metrics['false_negatives']}")

        # Analyze frame coverage
        frame_analysis = analyze_frame_coverage(ground_truths, detections)

        print(f"\nFRAME ANALYSIS:")
        print(f"- Frame Range: {frame_analysis['frame_range'][0]} - {frame_analysis['frame_range'][1]}")
        print(f"- Frames with GT Events: {len(frame_analysis['gt_frames'])}")
        print(f"- Frames with Detections: {len(frame_analysis['detected_frames'])}")
        print(f"- Missed Frames: {len(frame_analysis['missed_frames'])}")

        if frame_analysis['missed_frames']:
            print(f"\nMISSED FRAMES:")
            if len(frame_analysis['missed_frames']) <= 20:
                print(f"- {frame_analysis['missed_frames']}")
            else:
                print(f"- First 10: {frame_analysis['missed_frames'][:10]}")
                print(f"- Last 10: {frame_analysis['missed_frames'][-10:]}")

        # Identify pattern
        pattern = identify_missing_pattern(
            frame_analysis['missed_frames'],
            frame_analysis['detected_frames']
        )
        print(f"\nMISSING FRAME PATTERN:")
        print(f"- {pattern}")

        # Show sample of GT events with match status
        print(f"\nSAMPLE GT EVENTS (first 10):")
        for i, gt in enumerate(ground_truths[:10], 1):
            gt_id, event_type, frame_num, timestamp, bbox, conf, *_ = gt
            matched = "✓ MATCHED" if gt_id in metrics['matched_gt_ids'] else "✗ MISSED"
            print(f"  {i}. Frame {frame_num}: {event_type} - {matched}")

        if len(ground_truths) > 10:
            print(f"  ... and {len(ground_truths) - 10} more GT events")

        video_results.append({
            'video_num': idx,
            'video_filename': video_filename,
            'video_path': video_path,
            'video_id': video_id,
            'metrics': metrics,
            'frame_analysis': frame_analysis,
            'pattern': pattern
        })

        print()

    # Comparison section
    if len(video_results) >= 2:
        print("=" * 80)
        print("COMPARISON:")
        print("=" * 80)

        # Check if both videos have similar detection rates
        rates = [v['metrics']['detection_rate'] for v in video_results]
        rate_diff = abs(rates[0] - rates[1])

        print(f"\nDetection Rate Comparison:")
        for v in video_results:
            print(f"- Video {v['video_num']}: {v['metrics']['detection_rate']:.1f}%")

        print(f"\nRate Difference: {rate_diff:.1f} percentage points")

        equally_affected = rate_diff < 10  # Within 10% points
        print(f"\nAre both videos equally affected? {'YES' if equally_affected else 'NO'}")

        if equally_affected:
            print("Both videos show similar detection rates, suggesting a systematic issue")
        else:
            better_video = 1 if rates[0] > rates[1] else 2
            worse_video = 2 if better_video == 1 else 1
            print(f"Video {better_video} performs better than Video {worse_video}")

        print(f"\nPattern Consistency:")
        for v in video_results:
            print(f"- Video {v['video_num']}: {v['pattern']}")

        # Hypothesis
        print(f"\nHYPOTHESIS:")
        if equally_affected and all(v['metrics']['detection_rate'] < 50 for v in video_results):
            print("Both videos show poor detection rates (<50%). Possible causes:")
            print("1. Frame skipping in model inference (processing every Nth frame)")
            print("2. Temporal filtering removing valid detections")
            print("3. Confidence threshold too high")
            print("4. Model not suited for these video characteristics")
            print("5. Ground truth annotation at finer granularity than model output")
        elif equally_affected:
            print("Both videos show moderate detection rates. This suggests:")
            print("1. Consistent model behavior across different videos")
            print("2. Systematic detection limitations")
            print("3. Ground truth may include edge cases the model doesn't handle")
        else:
            print("Videos show different detection rates. Possible causes:")
            print("1. Different video characteristics (lighting, motion, quality)")
            print("2. Different event distributions or difficulty levels")
            print("3. Video-specific processing issues")

    # Detailed frame-by-frame if requested
    print("\n" + "=" * 80)
    print("FRAME-BY-FRAME ANALYSIS:")
    print("=" * 80)

    for v in video_results:
        print(f"\nVideo {v['video_num']}:")
        gt_frames = v['frame_analysis']['gt_frames']
        detected = v['frame_analysis']['detected_frames']
        missed = v['frame_analysis']['missed_frames']

        print(f"Frame coverage: {len(detected)}/{len(gt_frames)} frames with detections")

        if len(gt_frames) <= 30:
            print("Frame-by-frame status:")
            for frame in gt_frames:
                status = "✓ DETECTED" if frame in detected else "✗ MISSED"
                print(f"  Frame {frame:4d}: {status}")
        else:
            print(f"First 15 frames:")
            for frame in gt_frames[:15]:
                status = "✓ DETECTED" if frame in detected else "✗ MISSED"
                print(f"  Frame {frame:4d}: {status}")
            print(f"  ... ({len(gt_frames) - 15} more frames)")

    conn.close()
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
