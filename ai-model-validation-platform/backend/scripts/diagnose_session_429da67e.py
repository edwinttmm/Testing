#!/usr/bin/env python3
"""
Comprehensive diagnostic script for session 429da67e-a8be-4947-a126-f2cfac7b0a0b

Analyzes:
1. Why LabJack light stopped during video 2
2. Why latencies are 8-9 seconds instead of 50-200ms
3. Why constant_voltage_mode wasn't used
4. Why corrected_results are all NULL
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Change directory to backend for relative imports
os.chdir(backend_path)

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Import models from backend root
from models import (
    TestSession, DetectionEvent, Video, VideoTestSequence,
    GroundTruthObject, SequenceVideoResult
)

# Import database configuration
from database import get_database_url

# Database setup
DATABASE_URL = get_database_url()
print(f"Using database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def format_time(dt):
    """Format datetime for display"""
    if dt is None:
        return "NULL"
    return dt.strftime("%H:%M:%S.%f")[:-3]

def format_duration(seconds):
    """Format duration in seconds"""
    if seconds is None:
        return "NULL"
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    return f"{seconds:.3f}s"

def analyze_session():
    """Main diagnostic function"""
    db = SessionLocal()
    session_id = "429da67e-a8be-4947-a126-f2cfac7b0a0b"

    try:
        print("=" * 80)
        print(f"SESSION DIAGNOSIS: {session_id}")
        print("=" * 80)
        print()

        # Get session
        session = db.query(TestSession).filter_by(id=session_id).first()
        if not session:
            print(f"❌ Session {session_id} not found!")
            return

        # 1. CONFIGURATION ANALYSIS
        print("📋 CONFIGURATION ANALYSIS")
        print("-" * 80)

        config = session.test_configuration
        if config is None:
            config = {}
        elif isinstance(config, str):
            try:
                config = json.loads(config)
            except:
                config = {}

        constant_voltage_mode = config.get('constant_voltage_mode', False)
        voltage_threshold = config.get('voltage_threshold', 'N/A')
        debounce_ms = config.get('debounce_ms', 'N/A')

        print(f"  constant_voltage_mode: {constant_voltage_mode}")
        if not constant_voltage_mode:
            print("    ❌ ISSUE: Should be TRUE for testing (light stays on)")
        else:
            print("    ✅ Correctly configured")

        print(f"  voltage_threshold: {voltage_threshold}V")
        print(f"  debounce_ms: {debounce_ms}ms")
        print(f"  Session status: {session.status}")
        print(f"  Started: {format_time(session.started_at)}")
        print(f"  Completed: {format_time(session.completed_at)}")

        if session.completed_at and session.started_at:
            duration = (session.completed_at - session.started_at).total_seconds()
            print(f"  Total duration: {format_duration(duration)}")

        print()

        # 2. VIDEO SEQUENCE ANALYSIS
        print("🎬 VIDEO SEQUENCE ANALYSIS")
        print("-" * 80)

        # Get all videos for this session (detections link to session and video)
        video_ids = db.query(DetectionEvent.video_id).filter(
            DetectionEvent.test_session_id == session_id
        ).distinct().all()

        video_ids = [vid[0] for vid in video_ids if vid[0]]
        videos_data = []

        if video_ids:
            # Get videos and their sequence results for timing info
            videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
            for i, video in enumerate(videos):
                # Try to get sequence result for timing
                seq_result = db.query(SequenceVideoResult).filter_by(video_id=video.id).first()
                videos_data.append((video, i+1, seq_result))

        print(f"  Total videos: {len(videos_data)}")
        print()

        total_detections = 0
        total_gt = 0

        for video, order, seq_result in videos_data:
            print(f"  Video {order}: {video.filename}")
            print(f"    Duration: {format_duration(video.duration)}")
            if seq_result and seq_result.video_start_time:
                print(f"    Playback start: {format_duration(seq_result.video_start_time)}")

            # Count detections for this video
            det_count = db.query(func.count(DetectionEvent.id)).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.video_id == video.id
            ).scalar()

            # Count ground truth for this video
            gt_count = db.query(func.count(GroundTruthObject.id)).filter(
                GroundTruthObject.video_id == video.id
            ).scalar()

            total_detections += det_count
            total_gt += gt_count

            if gt_count > 0:
                percentage = (det_count / gt_count) * 100
                status = "✅" if percentage > 90 else "⚠️" if percentage > 70 else "❌"
                print(f"    Detections: {det_count}/{gt_count} ({percentage:.1f}%) {status}")
            else:
                print(f"    Detections: {det_count}/0 (no ground truth)")

            # Get detection time range for this video
            first_det = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.video_id == video.id
            ).order_by(DetectionEvent.labjack_timestamp).first()

            last_det = db.query(DetectionEvent).filter(
                DetectionEvent.test_session_id == session_id,
                DetectionEvent.video_id == video.id
            ).order_by(DetectionEvent.labjack_timestamp.desc()).first()

            if first_det and last_det:
                # Use labjack_timestamp or timestamp
                first_time = first_det.labjack_timestamp or first_det.timestamp
                last_time = last_det.labjack_timestamp or last_det.timestamp
                print(f"    First detection: {format_duration(first_time)}")
                print(f"    Last detection: {format_duration(last_time)}")

                # Check if detections stopped before video ended
                if seq_result and seq_result.video_start_time and video.duration:
                    video_end_time = seq_result.video_start_time + video.duration
                    if last_time < video_end_time - 1:
                        time_before_end = video_end_time - last_time
                        print(f"    ❌ ISSUE: Detections stopped {format_duration(time_before_end)} before video ended!")

            print()

        print(f"  TOTAL: {total_detections}/{total_gt} detections ({(total_detections/total_gt*100) if total_gt > 0 else 0:.1f}%)")
        print()

        # 3. DETAILED LATENCY ANALYSIS
        print("⏱️  DETAILED LATENCY ANALYSIS")
        print("-" * 80)

        detections = db.query(DetectionEvent).filter_by(
            test_session_id=session_id
        ).order_by(DetectionEvent.labjack_timestamp).all()

        print(f"  Total detections: {len(detections)}")

        latencies = []
        corrected_count = 0
        null_corrected = 0

        for det in detections:
            # Use actual_latency_ms (canonical field)
            if det.actual_latency_ms is not None:
                latencies.append(det.actual_latency_ms)
            # Check for corrected_result field if it exists
            if hasattr(det, 'corrected_result'):
                if det.corrected_result is not None:
                    corrected_count += 1
                else:
                    null_corrected += 1

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            print(f"  Average latency: {avg_latency:.0f}ms")
            print(f"  Min latency: {min_latency:.0f}ms")
            print(f"  Max latency: {max_latency:.0f}ms")

            # Check if latencies are unrealistic
            if avg_latency > 1000:
                print(f"    ❌ ISSUE: Average latency {avg_latency:.0f}ms is UNREALISTIC!")
                print(f"    Expected range: 50-200ms")
                print(f"    Root cause: Likely incorrect video_start_time calculation")
            elif avg_latency < 10:
                print(f"    ⚠️  WARNING: Latency seems too low")
            else:
                print(f"    ✅ Latency within expected range (50-200ms)")
        else:
            print(f"  ❌ No latency data available")

        print()
        print(f"  Corrected results: {corrected_count}/{len(detections)} saved")
        print(f"  NULL corrected results: {null_corrected}/{len(detections)}")

        if null_corrected > 0:
            print(f"    ❌ ISSUE: {null_corrected} detections missing corrected results")
            print(f"    Possible reasons:")
            print(f"      1. Validation failed due to unrealistic latencies")
            print(f"      2. Detection outside video timeframe")
            print(f"      3. Processing error")

        print()

        # 4. MANUAL LATENCY CALCULATION
        print("🔍 MANUAL LATENCY CALCULATION (First 3 Detections)")
        print("-" * 80)

        for i, det in enumerate(detections[:3]):
            print(f"\n  Detection {i+1} (ID: {det.id[:8]}...):")
            det_time = det.labjack_timestamp or det.timestamp
            print(f"    LabJack timestamp: {format_duration(det_time)}")
            print(f"    Video ID: {det.video_id[:8] if det.video_id else 'NULL'}...")

            if det.video_id:
                video = db.query(Video).filter_by(id=det.video_id).first()
                seq_result = db.query(SequenceVideoResult).filter_by(video_id=det.video_id).first()

                if video:
                    if seq_result and seq_result.video_start_time:
                        print(f"    Video start (from seq): {format_duration(seq_result.video_start_time)}")
                    if det.video_start_time:
                        print(f"    Detection's video_start_time: {format_duration(det.video_start_time)}")

                    # Get matched ground truth
                    if det.ground_truth_match_id:
                        gt = db.query(GroundTruthObject).filter_by(id=det.ground_truth_match_id).first()
                        if gt:
                            print(f"    GT event at video time: {format_duration(gt.timestamp)}")

                            # Calculate expected latency
                            if seq_result and seq_result.video_start_time and det.labjack_timestamp:
                                gt_absolute_time = seq_result.video_start_time + gt.timestamp
                                manual_latency = (det.labjack_timestamp - gt_absolute_time) * 1000
                                print(f"    MANUAL CALCULATED LATENCY: {manual_latency:.0f}ms")

                            stored_latency = det.actual_latency_ms
                            print(f"    STORED LATENCY: {stored_latency:.0f}ms" if stored_latency else "    STORED LATENCY: NULL")

                            if stored_latency and 'manual_latency' in locals() and abs(manual_latency - stored_latency) > 10:
                                print(f"    ❌ MISMATCH: Calculation differs from stored value!")
                    else:
                        print(f"    ⚠️  No matched GT")
                else:
                    print(f"    ❌ Video not found")

        print()

        # 5. LABJACK TIMING ANALYSIS
        print("💡 LABJACK TIMING ANALYSIS")
        print("-" * 80)

        # Check if there's a pattern to when detections stopped
        if len(detections) > 0:
            # Group detections by video
            video_detections = {}
            for det in detections:
                if det.video_id not in video_detections:
                    video_detections[det.video_id] = []
                video_detections[det.video_id].append(det)

            for video_id, dets in video_detections.items():
                video = db.query(Video).filter_by(id=video_id).first()
                if not video:
                    continue

                print(f"\n  Video: {video.filename}")
                print(f"    Total detections: {len(dets)}")

                if len(dets) > 0:
                    first = dets[0]
                    last = dets[-1]
                    first_time = first.labjack_timestamp or first.timestamp
                    last_time = last.labjack_timestamp or last.timestamp
                    span = last_time - first_time
                    print(f"    Detection span: {format_duration(span)}")
                    print(f"    Video duration: {format_duration(video.duration)}")

                    # Check if detections span the full video
                    if video.duration and span < video.duration * 0.9:
                        print(f"    ❌ ISSUE: Detections only cover {(span/video.duration)*100:.1f}% of video")
                        print(f"    Possible causes:")
                        print(f"      1. LabJack light turned off early")
                        print(f"      2. Health monitor exited")
                        print(f"      3. Voltage dropped below threshold")
                        print(f"      4. Connection lost")

        print()

        # 6. RECOMMENDATIONS
        print("💡 RECOMMENDATIONS")
        print("-" * 80)
        print()

        issues_found = []

        if not constant_voltage_mode:
            issues_found.append("Enable constant_voltage_mode for testing")

        if latencies and sum(latencies) / len(latencies) > 1000:
            issues_found.append("Fix video_start_time in latency calculation")

        if null_corrected > 0:
            issues_found.append("Investigate why corrected_results are NULL")

        if total_detections < total_gt * 0.9:
            issues_found.append("Investigate LabJack LED behavior (light may have stopped)")

        if not issues_found:
            print("  ✅ No major issues detected!")
        else:
            for i, issue in enumerate(issues_found, 1):
                print(f"  {i}. {issue}")

        print()
        print("  Next steps:")
        print("    1. Apply fixes to video start time calculation")
        print("    2. Enable constant_voltage_mode in test configuration")
        print("    3. Add health monitor logging to detect exits")
        print("    4. Rerun test with fixes applied")
        print()

        print("=" * 80)
        print("DIAGNOSIS COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR during diagnosis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    analyze_session()
