#!/usr/bin/env python3
"""
FINAL Per-Video Detection Rate Breakdown Analysis
Session: fa204ef2-9d8b-4480-9692-86e338c1218a
"""

import sqlite3

session_id = "fa204ef2-9d8b-4480-9692-86e338c1218a"

def main():
    conn = sqlite3.connect('dev_database.db')
    cursor = conn.cursor()

    print("=" * 80)
    print("PER-VIDEO DETECTION BREAKDOWN")
    print("=" * 80)
    print(f"\nSession: {session_id}\n")

    # Get session overview
    cursor.execute("""
        SELECT status, actual_detections, expected_detections,
               tp_count, fp_count, fn_count, pass_fail_result,
               accuracy_f1_score, accuracy_precision, accuracy_recall
        FROM test_sessions
        WHERE id = ?
    """, (session_id,))

    session_info = cursor.fetchone()
    if not session_info:
        print("Session not found!")
        conn.close()
        return

    (status, actual_det, expected_det, tp_count, fp_count, fn_count,
     pass_fail, f1_score, precision, recall) = session_info

    print(f"SESSION OVERVIEW:")
    print(f"- Status: {status}")
    print(f"- Total Detections: {actual_det}")
    print(f"- True Positives: {tp_count}")
    print(f"- False Positives: {fp_count}")
    print(f"- False Negatives: {fn_count}")
    print(f"- Pass/Fail: {pass_fail}")
    if recall is not None:
        print(f"- Overall Detection Rate (Recall): {recall * 100:.1f}%")

    print("\n" + "=" * 80)

    # Get all videos in the sequence
    cursor.execute("""
        SELECT svr.id, svr.video_id, svr.sequence_order, v.filename
        FROM sequence_video_results svr
        JOIN videos v ON v.id = svr.video_id
        WHERE svr.video_sequence_id IN (
            SELECT sequence_id FROM test_sessions WHERE id = ?
        )
        ORDER BY svr.sequence_order
    """, (session_id,))

    sequence_videos = cursor.fetchall()
    print(f"\nFound {len(sequence_videos)} video(s) in sequence\n")

    video_results = []

    for svr_id, video_id, seq_order, filename in sequence_videos:
        print("=" * 80)
        print(f"VIDEO {seq_order + 1}:")
        print("=" * 80)
        print(f"- Video ID/Path: {filename}")

        # Get ground truth count
        cursor.execute("""
            SELECT COUNT(*) FROM ground_truth_objects
            WHERE video_id = ? AND deleted_at IS NULL
        """, (video_id,))
        gt_count = cursor.fetchone()[0]

        # Get detections for this video
        cursor.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN validation_result = 'TP' THEN 1 ELSE 0 END) as tp
            FROM detection_events
            WHERE test_session_id = ? AND sequence_video_result_id = ?
        """, (session_id, svr_id))
        det_count, tp = cursor.fetchone()
        tp = tp if tp else 0
        fn = gt_count - tp
        detection_rate = (tp / gt_count * 100) if gt_count > 0 else 0

        print(f"- Total GT Events: {gt_count}")
        print(f"- Detections Captured: {tp}")
        print(f"- Detection Rate: {detection_rate:.1f}%")

        # Get frame ranges
        cursor.execute("""
            SELECT MIN(frame_number), MAX(frame_number), COUNT(DISTINCT frame_number)
            FROM ground_truth_objects
            WHERE video_id = ? AND deleted_at IS NULL
        """, (video_id,))
        min_frame, max_frame, unique_frames = cursor.fetchone()

        print(f"- Frame Range: {min_frame} - {max_frame}")

        # Get detected frames using video_frame_number
        cursor.execute("""
            SELECT DISTINCT video_frame_number
            FROM detection_events
            WHERE test_session_id = ? AND sequence_video_result_id = ?
              AND video_frame_number IS NOT NULL
            ORDER BY video_frame_number
        """, (session_id, svr_id))
        det_frames = [row[0] for row in cursor.fetchall()]

        # Get GT frames
        cursor.execute("""
            SELECT DISTINCT frame_number
            FROM ground_truth_objects
            WHERE video_id = ? AND deleted_at IS NULL
            ORDER BY frame_number
        """, (video_id,))
        gt_frames = [row[0] for row in cursor.fetchall()]

        missing_frames = sorted(set(gt_frames) - set(det_frames))

        print(f"- Missing Frames: {len(missing_frames)}")

        if missing_frames:
            if len(missing_frames) <= 30:
                print(f"\nMISSING FRAME LIST:")
                print(f"  {missing_frames}")
            else:
                print(f"\nMISSING FRAMES (sample):")
                print(f"  First 15: {missing_frames[:15]}")
                print(f"  Last 15: {missing_frames[-15:]}")

        video_results.append({
            'video_num': seq_order + 1,
            'filename': filename,
            'gt_count': gt_count,
            'tp': tp,
            'detection_rate': detection_rate,
            'missing_frames': len(missing_frames),
            'total_frames': len(gt_frames)
        })

        print()

    # Comparison
    print("=" * 80)
    print("COMPARISON:")
    print("=" * 80)

    rates = [v['detection_rate'] for v in video_results]
    rate_diff = abs(rates[0] - rates[1]) if len(rates) >= 2 else 0

    print(f"\nDetection Rate Comparison:")
    for v in video_results:
        print(f"- Video {v['video_num']}: {v['detection_rate']:.1f}%")

    if len(rates) >= 2:
        print(f"\nRate Difference: {rate_diff:.1f} percentage points")

        equally_affected = rate_diff < 10
        print(f"\nAre both videos equally affected? {'YES' if equally_affected else 'NO'}")

        print(f"\nPattern consistency:")
        for v in video_results:
            pct_missing = (v['missing_frames'] / v['total_frames'] * 100) if v['total_frames'] > 0 else 0
            print(f"- Video {v['video_num']}: {pct_missing:.1f}% frames missing ({v['missing_frames']}/{v['total_frames']})")

        print(f"\nHYPOTHESIS:")
        if all(v['detection_rate'] < 50 for v in video_results):
            print("Both videos show poor detection rates (<50%).")
            print("Likely causes:")
            print("1. Frame skipping in model inference (processing every Nth frame)")
            print("2. Model outputting detections at lower frequency than GT annotation")
            print("3. Temporal filtering removing valid detections")
            print("4. Confidence threshold too high")
            print("5. Ground truth has finer granularity than model output")
        elif equally_affected:
            print("Both videos show similar moderate detection rates.")
            print("This suggests consistent model behavior across videos.")
        else:
            print(f"Video {video_results[0]['video_num'] if rates[0] > rates[1] else video_results[1]['video_num']} performs better.")
            print("Possible reasons:")
            print("1. Different video characteristics (lighting, motion, occlusion)")
            print("2. Different event distributions or difficulty levels")
            print("3. Video-specific processing issues")

    # Frame skipping pattern
    print(f"\n" + "=" * 80)
    print("FRAME SKIPPING PATTERN PER VIDEO:")
    print("=" * 80)

    for svr_id, video_id, seq_order, filename in sequence_videos:
        print(f"\nVideo {seq_order + 1} ({filename}):")

        # Get sample of detected vs missed frames
        cursor.execute("""
            SELECT DISTINCT video_frame_number
            FROM detection_events
            WHERE test_session_id = ? AND sequence_video_result_id = ?
              AND video_frame_number IS NOT NULL
            ORDER BY video_frame_number
        """, (session_id, svr_id))
        det_frames = [row[0] for row in cursor.fetchall()]

        if len(det_frames) >= 2:
            frame_gaps = [det_frames[i+1] - det_frames[i] for i in range(len(det_frames)-1)]
            avg_gap = sum(frame_gaps) / len(frame_gaps) if frame_gaps else 0

            print(f"  Detected frames: {len(det_frames)}")
            print(f"  Sample: {det_frames[:10] if len(det_frames) > 10 else det_frames}")
            print(f"  Average gap between detections: {avg_gap:.1f} frames")

            if len(set(frame_gaps)) == 1 and len(frame_gaps) > 3:
                print(f"  Pattern: Systematic - detecting every {frame_gaps[0]} frames")
            elif avg_gap > 3:
                print(f"  Pattern: Sparse detections (avg {avg_gap:.1f} frame gap)")
            else:
                print(f"  Pattern: Relatively continuous detection")
        else:
            print(f"  Insufficient detections for pattern analysis")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    conn.close()

if __name__ == "__main__":
    main()
