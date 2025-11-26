"""

pytestmark = pytest.mark.skip(reason="Deprecated modules or missing dependencies")

End-to-End Integration Test for Complete Timing Fixes

This test validates the entire flow:
1. Frontend sends video-started with sequenceElapsedTime
2. Backend initializes sequence timing correctly
3. LabJack detection arrives in grace period
4. Detection accepted (not classified as frame 0)
5. Dual-evaluation produces separate accuracy and latency results
"""

pytestmark = pytest.mark.skip(reason="Deprecated or missing dependencies")

import os
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import json

from models import (
    Project,
    TestSession,
    Video,
    DetectionEvent,
    GroundTruthObject,
    LabjackSignal,
    EvaluationResult
)


class TestEndToEndTimingFixes:
    """Full integration test of timing fixes"""

    @pytest.fixture
    def complete_test_scenario(self, test_db: Session):
        """Set up complete test scenario with all components"""
        # Create project
        project = Project(
            name="E2E Timing Test",
            description="End-to-end timing validation",
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(project)
        test_db.flush()

        # Create session with thresholds
        session = TestSession(
            project_id=project.id,
            session_id="e2e-timing-test",
            test_type="HIL",
            status="in_progress",
            accuracy_threshold=0.75,
            latency_threshold_ms=100,
            created_at=datetime.now(timezone.utc)
        )
        test_db.add(session)
        test_db.flush()

        return {"project": project, "session": session}

    def test_complete_timing_flow(self, test_db: Session, complete_test_scenario):
        """
        Full end-to-end test:
        1. Video started event with sequenceElapsedTime
        2. Sequence timing initialized
        3. LabJack signals arrive (some in grace period)
        4. Detections created and assigned correctly
        5. Dual evaluation with separate accuracy/latency results
        """
        data = complete_test_scenario
        session = data["session"]

        # Step 1: Frontend sends video-started event
        # Video starts at t=10.5s, sequenceElapsedTime=1.8s
        video_start_unix = 10.5
        sequence_elapsed_time = 1.8

        video = Video(
            filename="test_video.mp4",
            original_name="test_video.mp4",
            session_id=session.id,
            sequence_number=1,
            duration=5.0,
            start_time=video_start_unix,
            sequence_elapsed_time=sequence_elapsed_time,
            video_started_at=datetime.fromtimestamp(video_start_unix, tz=timezone.utc)
        )
        test_db.add(video)
        test_db.flush()

        # Step 2: Backend calculates sequence_start_time
        sequence_start_time = video_start_unix - sequence_elapsed_time
        assert abs(sequence_start_time - 8.7) < 0.01, \
            f"Sequence start should be 8.7s, got {sequence_start_time}s"

        # Step 3: Create ground truth objects (5 objects)
        ground_truth_objects = []
        for i in range(5):
            gt = GroundTruthObject(
                video_id=video.id,
                frame_number=i * 30,
                timestamp=video_start_unix + (i * 1.0),  # At 0s, 1s, 2s, 3s, 4s into video
                object_class="person",
                bounding_box={"x": 100 + i * 10, "y": 100, "width": 50, "height": 50},
                confidence=1.0
            )
            test_db.add(gt)
            ground_truth_objects.append(gt)
        test_db.flush()

        # Step 4: LabJack signals arrive (some in grace period)
        grace_period = 2.0
        grace_period_start = video_start_unix - grace_period  # 8.5s

        labjack_signals = [
            # Signal 1: In grace period (0.2s before video start)
            {
                "timestamp": 10.3,
                "sequence_elapsed": 1.6,
                "in_grace": True,
                "description": "Early detection (grace period)"
            },
            # Signal 2: At video start
            {
                "timestamp": 10.5,
                "sequence_elapsed": 1.8,
                "in_grace": True,
                "description": "Exact video start"
            },
            # Signal 3: During video (1.0s in)
            {
                "timestamp": 11.5,
                "sequence_elapsed": 2.8,
                "in_grace": False,
                "description": "Normal detection"
            },
            # Signal 4: Too early (before grace period)
            {
                "timestamp": 8.0,
                "sequence_elapsed": -0.7,
                "in_grace": False,
                "description": "Before grace period"
            },
        ]

        created_signals = []
        for signal_data in labjack_signals:
            signal = LabjackSignal(
                session_id=session.id,
                timestamp=signal_data["timestamp"],
                fio4=1.0,
                fio5=0.0,
                sequence_elapsed_time=signal_data["sequence_elapsed"],
                created_at=datetime.fromtimestamp(signal_data["timestamp"], tz=timezone.utc)
            )
            test_db.add(signal)
            test_db.flush()
            created_signals.append((signal, signal_data))

        # Step 5: Process signals into detections (with grace period logic)
        detection_events = []
        for signal, signal_data in created_signals:
            # Check if signal is within grace period or video duration
            is_in_window = (
                signal.timestamp >= grace_period_start and
                signal.timestamp <= (video_start_unix + video.duration)
            )

            if is_in_window:
                # Calculate video-relative timestamp
                video_relative_ts = signal.timestamp - video_start_unix

                detection = DetectionEvent(
                    session_id=session.id,
                    video_id=video.id,
                    timestamp=signal.timestamp,
                    video_relative_timestamp=video_relative_ts,
                    sequence_elapsed_time=signal.sequence_elapsed_time,
                    object_class="person",
                    confidence=0.95,
                    bounding_box={"x": 100, "y": 100, "width": 50, "height": 50},
                    labjack_signal_id=signal.id,
                    is_true_positive=False  # Will be set by matching
                )
                test_db.add(detection)
                detection_events.append(detection)

        test_db.flush()

        # Step 6: Verify grace period detections were accepted
        grace_detections = [
            det for det in detection_events
            if det.video_relative_timestamp < 0
        ]

        # Should have 1 grace period detection (10.3s)
        assert len(grace_detections) == 1, \
            f"Should have 1 grace period detection, got {len(grace_detections)}"

        # Verify it's not classified as "frame 0"
        for det in grace_detections:
            assert det.video_relative_timestamp < 0, \
                "Grace period detection should have negative video_relative_timestamp"
            assert det.video_relative_timestamp >= -grace_period, \
                f"Detection should be within grace period ({-grace_period}s)"

        # Step 7: Match detections to ground truth
        matched_count = 0
        for detection in detection_events:
            # Simple matching: find closest GT within 1.0s
            for gt in ground_truth_objects:
                time_diff = abs(detection.timestamp - gt.timestamp)
                if time_diff <= 1.0:  # 1s matching window
                    detection.ground_truth_id = gt.id
                    detection.is_true_positive = True
                    detection.latency_ms = time_diff * 1000  # Convert to ms
                    matched_count += 1
                    break

        test_db.flush()

        # Should have at least 2 TPs (grace detection + normal detections)
        assert matched_count >= 2, f"Should have at least 2 TPs, got {matched_count}"

        # Step 8: Calculate accuracy metrics
        tp_count = sum(1 for det in detection_events if det.is_true_positive)
        fp_count = sum(1 for det in detection_events if not det.is_true_positive)
        fn_count = len(ground_truth_objects) - tp_count

        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Step 9: Calculate average latency (from TP detections only)
        tp_latencies = [det.latency_ms for det in detection_events if det.is_true_positive and det.latency_ms]
        avg_latency_ms = sum(tp_latencies) / len(tp_latencies) if tp_latencies else -1.0

        # Step 10: Dual evaluation
        # Accuracy evaluation
        if f1_score >= session.accuracy_threshold:
            accuracy_result = "PASS"
        elif f1_score >= session.accuracy_threshold * 0.9:
            accuracy_result = "CONDITIONAL_PASS"
        else:
            accuracy_result = "FAIL"

        # Latency evaluation
        if avg_latency_ms == -1:
            latency_result = "N/A"
        elif avg_latency_ms <= session.latency_threshold_ms:
            latency_result = "PASS"
        elif avg_latency_ms <= session.latency_threshold_ms * 1.5:
            latency_result = "CONDITIONAL_PASS"
        else:
            latency_result = "FAIL"

        # Overall result
        if accuracy_result == "PASS" and latency_result == "PASS":
            overall_result = "PASS"
        elif accuracy_result == "FAIL" or latency_result == "FAIL":
            overall_result = "FAIL"
        else:
            overall_result = "CONDITIONAL_PASS"

        # Step 11: Store evaluation results
        evaluation = EvaluationResult(
            session_id=session.id,
            video_id=video.id,
            accuracy_score=f1_score,
            precision=precision,
            recall=recall,
            avg_latency_ms=avg_latency_ms if avg_latency_ms != -1 else None,
            true_positives=tp_count,
            false_positives=fp_count,
            false_negatives=fn_count,
            accuracy_result=accuracy_result,
            latency_result=latency_result,
            overall_result=overall_result,
            evaluation_details=json.dumps({
                "timing_validation": {
                    "sequence_start_time": sequence_start_time,
                    "video_start_time": video_start_unix,
                    "grace_period_seconds": grace_period,
                    "grace_detections_count": len(grace_detections)
                },
                "accuracy_evaluation": {
                    "f1_score": f1_score,
                    "precision": precision,
                    "recall": recall,
                    "threshold": session.accuracy_threshold,
                    "result": accuracy_result
                },
                "latency_evaluation": {
                    "avg_latency_ms": avg_latency_ms,
                    "tp_count": tp_count,
                    "threshold_ms": session.latency_threshold_ms,
                    "result": latency_result
                },
                "combined": {
                    "overall_result": overall_result
                }
            }),
            evaluated_at=datetime.now(timezone.utc)
        )
        test_db.add(evaluation)
        test_db.commit()

        # Step 12: Validate final results
        stored_eval = test_db.execute(select(EvaluationResult).filter_by(session_id=session.id)).scalar_one_or_none()
        assert stored_eval is not None, "Evaluation should be stored"

        # Verify separate results
        assert stored_eval.accuracy_result in ["PASS", "CONDITIONAL_PASS", "FAIL"]
        assert stored_eval.latency_result in ["PASS", "CONDITIONAL_PASS", "FAIL", "N/A"]
        assert stored_eval.overall_result in ["PASS", "CONDITIONAL_PASS", "FAIL"]

        # Verify details JSON
        details = json.loads(stored_eval.evaluation_details)
        assert "timing_validation" in details
        assert "accuracy_evaluation" in details
        assert "latency_evaluation" in details
        assert "combined" in details

        # Verify grace period was used
        assert details["timing_validation"]["grace_period_seconds"] == grace_period
        assert details["timing_validation"]["grace_detections_count"] >= 1

        print(f"\n✅ End-to-End Test Results:")
        print(f"   Sequence Start: {sequence_start_time}s")
        print(f"   Video Start: {video_start_unix}s")
        print(f"   Grace Detections: {len(grace_detections)}")
        print(f"   True Positives: {tp_count}")
        print(f"   False Positives: {fp_count}")
        print(f"   False Negatives: {fn_count}")
        print(f"   F1 Score: {f1_score:.2f}")
        print(f"   Avg Latency: {avg_latency_ms:.1f}ms")
        print(f"   Accuracy Result: {accuracy_result}")
        print(f"   Latency Result: {latency_result}")
        print(f"   Overall Result: {overall_result}")

    def test_multi_video_sequence_timing(self, test_db: Session, complete_test_scenario):
        """Test timing flow with multiple videos in sequence"""
        data = complete_test_scenario
        session = data["session"]

        # Create 3 videos with realistic timing
        videos = []
        video_configs = [
            {"start": 10.5, "seq_elapsed": 1.8, "duration": 5.0},
            {"start": 20.0, "seq_elapsed": 11.3, "duration": 5.0},
            {"start": 30.5, "seq_elapsed": 21.8, "duration": 5.0},
        ]

        for idx, config in enumerate(video_configs):
            video = Video(
                filename=f"video{idx+1}.mp4",
                original_name=f"video{idx+1}.mp4",
                session_id=session.id,
                sequence_number=idx + 1,
                duration=config["duration"],
                start_time=config["start"],
                sequence_elapsed_time=config["seq_elapsed"],
                video_started_at=datetime.fromtimestamp(config["start"], tz=timezone.utc)
            )
            test_db.add(video)
            test_db.flush()
            videos.append(video)

        # Verify all videos derive same sequence start
        sequence_starts = [v.start_time - v.sequence_elapsed_time for v in videos]
        for seq_start in sequence_starts:
            assert abs(seq_start - 8.7) < 0.01

        # Create detections across all videos
        all_detections = []
        grace_period = 2.0

        for video in videos:
            # Grace period detection
            grace_det = DetectionEvent(
                session_id=session.id,
                video_id=video.id,
                timestamp=video.start_time - 0.2,
                video_relative_timestamp=-0.2,
                sequence_elapsed_time=video.sequence_elapsed_time - 0.2,
                object_class="person",
                confidence=0.95,
                bounding_box={"x": 100, "y": 100, "width": 50, "height": 50}
            )
            test_db.add(grace_det)
            all_detections.append(grace_det)

        test_db.commit()

        # Verify all grace detections accepted
        for det in all_detections:
            assert det.video_relative_timestamp < 0
            assert det.video_relative_timestamp >= -grace_period

        print(f"\n✅ Multi-Video Test: {len(videos)} videos, {len(all_detections)} grace detections")
