#!/usr/bin/env python3
"""
Multi-Video Detection Rate Breakdown Analysis
Session: fa204ef2-9d8b-4480-9692-86e338c1218a
Analyzes each video in a sequence separately
"""

import sqlite3
from typing import List, Dict

session_id = "fa204ef2-9d8b-4480-9692-86e338c1218a"

def main():
    conn = sqlite3.connect('dev_database.db')
    cursor = conn.cursor()

    print("=" * 80)
    print("PER-VIDEO DETECTION BREAKDOWN ANALYSIS")
    print("=" * 80)
    print(f"\nSession: {session_id}\n")

    # Get session overview
    cursor.execute("""
        SELECT id, status, created_at, completed_at, actual_detections, expected_detections,
               tp_count, fp_count, fn_count, pass_fail_result, accuracy_f1_score,
               accuracy_precision, accuracy_recall
        FROM test_sessions
        WHERE id = ?
    """, (session_id,))

    session_info = cursor.fetchone()
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
    print("VIDEO SEQUENCE BREAKDOWN")
    print("=" * 80)

    # Get all videos in the sequence
    cursor.execute("""
        SELECT svr.id, svr.video_id, svr.sequence_order,
               svr.video_status, svr.validation_result,
               svr.expected_detection_count, svr.actual_detection_count,
               svr.passed_detections, svr.failed_detections,
               svr.pass_rate_percent, v.filename
        FROM sequence_video_results svr
        JOIN videos v ON v.id = svr.video_id
        WHERE svr.video_sequence_id IN (
            SELECT sequence_id FROM test_sessions WHERE id = ?
        )
        ORDER BY svr.sequence_order
    """, (session_id,))

    sequence_videos = cursor.fetchall()

    if not sequence_videos:
        print("\nNo sequence videos found!")
        conn.close()
        return

    print(f"\nFound {len(sequence_videos)} video(s) in sequence\n")

    video_results = []

    for (svr_id, video_id, seq_order, video_status, validation_result,
         expected_det, actual_det, passed_det, failed_det, pass_rate, filename) in sequence_videos:

        print("=" * 80)
        print(f"VIDEO {seq_order + 1}:")
        print("=" * 80)
        print(f"- Filename: {filename}")
        print(f"- Video ID: {video_id}")
        print(f"- Sequence Video Result ID: {svr_id}")
        print(f"- Status: {video_status}")
        print(f"- Validation Result: {validation_result}")

        # Get ground truth objects for this video
        cursor.execute("""
            SELECT COUNT(*) FROM ground_truth_objects
            WHERE video_id = ? AND deleted_at IS NULL
        """, (video_id,))
        gt_count = cursor.fetchone()[0]

        # Get detections for this sequence video result
        cursor.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN validation_result = 'TP' THEN 1 ELSE 0 END) as tp,
                   SUM(CASE WHEN validation_result = 'FP' THEN 1 ELSE 0 END) as fp
            FROM detection_events
            WHERE test_session_id = ? AND sequence_video_result_id = ?
        """, (session_id, svr_id))
        det_count, tp, fp = cursor.fetchone()
        tp = tp if tp else 0
        fp = fp if fp else 0
        fn = gt_count - tp

        print(f"\nMETRICS:")
        print(f"- Total GT Events: {gt_count}")
        print(f"- Total Detections: {det_count}")
        print(f"- True Positives: {tp}")
        print(f"- False Positives: {fp}")
        print(f"- False Negatives: {fn}")
        print(f"- Detection Rate: {(tp / gt_count * 100) if gt_count > 0 else 0:.1f}%")

        # Get frame coverage
        cursor.execute("""
            SELECT DISTINCT frame_number
            FROM ground_truth_objects
            WHERE video_id = ? AND deleted_at IS NULL
            ORDER BY frame_number
        """, (video_id,))
        gt_frames = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT DISTINCT frame_number
            FROM detection_events
            WHERE test_session_id = ? AND sequence_video_result_id = ?
              AND frame_number IS NOT NULL
            ORDER BY frame_number
        """, (session_id, svr_id))
        det_frames = [row[0] for row in cursor.fetchall()]

        missed_frames = sorted(set(gt_frames) - set(det_frames))
        detected_frames = sorted(set(gt_frames) & set(det_frames))

        print(f"\nFRAME ANALYSIS:")
        if gt_frames:
            print(f"- Frame Range: {min(gt_frames)} - {max(gt_frames)}")
            print(f"- Frames with GT Events: {len(gt_frames)}")
            print(f"- Frames with Detections: {len(detected_frames)}")
            print(f"- Missed Frames: {len(missed_frames)}")

            if missed_frames:
                print(f"\nMISSED FRAMES:")
                if len(missed_frames) <= 20:
                    print(f"- {missed_frames}")
                else:
                    print(f"- First 10: {missed_frames[:10]}")
                    print(f"- Last 10: {missed_frames[-10:]}")

                # Identify pattern
                if len(missed_frames) >= 2:
                    gaps = [missed_frames[i+1] - missed_frames[i] for i in range(len(missed_frames)-1)]
                    if len(set(gaps)) == 1:
                        print(f"\nPATTERN: Systematic skip - every {gaps[0]} frames")
                    elif len(missed_frames) == len(gt_frames):
                        print(f"\nPATTERN: All frames missed - no detections captured")
                    else:
                        print(f"\nPATTERN: Irregular missing frames")

            # Show sample GT events
            cursor.execute("""
                SELECT gt.id, gt.class_label, gt.frame_number,
                       EXISTS(
                           SELECT 1 FROM detection_events de
                           WHERE de.ground_truth_match_id = gt.id
                             AND de.test_session_id = ?
                             AND de.sequence_video_result_id = ?
                       ) as matched
                FROM ground_truth_objects gt
                WHERE gt.video_id = ? AND gt.deleted_at IS NULL
                ORDER BY gt.frame_number
                LIMIT 10
            """, (session_id, svr_id, video_id))

            print(f"\nSAMPLE GT EVENTS (first 10):")
            for i, (gt_id, class_label, frame_num, matched) in enumerate(cursor.fetchall(), 1):
                status = "✓ MATCHED" if matched else "✗ MISSED"
                print(f"  {i}. Frame {frame_num}: {class_label} - {status}")

        video_results.append({
            'seq_order': seq_order + 1,
            'filename': filename,
            'gt_count': gt_count,
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'det_rate': (tp / gt_count * 100) if gt_count > 0 else 0,
            'frames_analyzed': len(gt_frames),
            'frames_detected': len(detected_frames),
            'frames_missed': len(missed_frames)
        })

        print()

    # Comparison section
    if len(video_results) >= 2:
        print("=" * 80)
        print("COMPARISON:")
        print("=" * 80)

        print(f"\nDetection Rate Comparison:")
        for v in video_results:
            print(f"- Video {v['seq_order']}: {v['det_rate']:.1f}% ({v['tp']}/{v['gt_count']} GT events)")

        rates = [v['det_rate'] for v in video_results]
        rate_diff = max(rates) - min(rates)

        print(f"\nRate Difference: {rate_diff:.1f} percentage points")

        equally_affected = rate_diff < 10
        print(f"\nAre both videos equally affected? {'YES' if equally_affected else 'NO'}")

        if equally_affected:
            print("Both videos show similar detection rates, suggesting a systematic issue")
            if all(v['det_rate'] < 50 for v in video_results):
                print("\nHYPOTHESIS:")
                print("1. Model may be processing frames at lower frequency than GT annotation")
                print("2. Temporal filtering removing valid detections")
                print("3. Confidence threshold too high")
                print("4. Frame skipping in model inference pipeline")
        else:
            best_idx = rates.index(max(rates))
            worst_idx = rates.index(min(rates))
            print(f"\nVideo {video_results[best_idx]['seq_order']} performs better than Video {video_results[worst_idx]['seq_order']}")

            print(f"\nHYPOTHESIS:")
            print("1. Videos may have different characteristics (lighting, motion, occlusion)")
            print("2. Different event distributions or difficulty levels")
            print("3. Video-specific processing issues")

    elif len(video_results) == 1:
        print("=" * 80)
        print("SINGLE VIDEO ANALYSIS:")
        print("=" * 80)
        v = video_results[0]
        print(f"\nOnly one video in sequence")
        print(f"- Detection Rate: {v['det_rate']:.1f}%")

        if v['det_rate'] < 50:
            print(f"\nHYPOTHESIS:")
            print("1. Model inference may be skipping frames")
            print("2. Temporal filtering too aggressive")
            print("3. Confidence threshold too high")
            print("4. Ground truth has finer granularity than model output")
            print(f"5. {v['frames_missed']}/{v['frames_analyzed']} frames have no detections")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    conn.close()

if __name__ == "__main__":
    main()
