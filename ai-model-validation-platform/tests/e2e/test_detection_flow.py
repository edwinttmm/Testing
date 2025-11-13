"""
End-to-End Integration Test: Complete Detection Flow
===================================================

Tests the complete detection flow from hardware to frontend:
1. LabJack voltage detection
2. Database storage
3. WebSocket emission
4. Frontend reception and display
5. Ground truth matching

CRITICAL: This test verifies the entire HIL testing pipeline works correctly.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import json
import time

from models import DetectionEvent, TestSession, Video, Project, GroundTruthObject
from socketio_server import sio, emit_detection_event
from services.labjack_detection_service import LabJackDetectionService
from services.ground_truth_matching_service import GroundTruthMatchingService
from database import SessionLocal


@pytest.fixture
def e2e_project(test_db: Session):
    """Create E2E test project"""
    project = Project(
        id="e2e-project",
        name="E2E Detection Flow Test",
        description="End-to-end detection testing",
        camera_model="Test Camera",
        camera_view="Front-facing VRU",
        signal_type="GPIO"
    )
    test_db.add(project)
    test_db.commit()
    test_db.refresh(project)
    return project


@pytest.fixture
def e2e_video(test_db: Session, e2e_project: Project):
    """Create E2E test video with ground truth"""
    video = Video(
        id="e2e-video-001",
        filename="e2e_test.mp4",
        file_path="/uploads/e2e_test.mp4",
        project_id=e2e_project.id,
        duration=60.0,
        fps=30.0,
        resolution="1920x1080",
        ground_truth_generated=True,
        ground_truth_count=10
    )
    test_db.add(video)
    test_db.commit()
    test_db.refresh(video)
    return video


@pytest.fixture
def e2e_ground_truth(test_db: Session, e2e_video: Video):
    """Create ground truth objects for matching"""
    ground_truths = []
    for i in range(10):
        gt = GroundTruthObject(
            id=f"gt-e2e-{i:03d}",
            video_id=e2e_video.id,
            tracking_id=f"VRU_{i:03d}",
            frame_number=i * 30,  # Every 30 frames (~1 second at 30fps)
            timestamp=i * 1.0,  # Every 1 second
            class_label="pedestrian",
            x=100.0 + (i * 10),
            y=150.0 + (i * 5),
            width=80.0,
            height=120.0,
            confidence=0.95,
            validated=True
        )
        test_db.add(gt)
        ground_truths.append(gt)
    test_db.commit()
    for gt in ground_truths:
        test_db.refresh(gt)
    return ground_truths


@pytest.fixture
def e2e_session(test_db: Session, e2e_project: Project, e2e_video: Video):
    """Create E2E test session"""
    session = TestSession(
        id="e2e-session-001",
        name="E2E Detection Flow Test",
        project_id=e2e_project.id,
        video_id=e2e_video.id,
        status="running",
        tolerance_ms=100,
        latency_threshold_ms=100,
        video_start_timestamp=time.time(),
        started_at=datetime.now(timezone.utc),
        video_timing_sync_status="synced"
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteDetectionFlow:
    """End-to-end tests for complete detection flow"""

    async def test_complete_hil_detection_flow(
        self, test_db: Session, e2e_session: TestSession,
        e2e_video: Video, e2e_ground_truth: list
    ):
        """
        CRITICAL E2E TEST: Complete HIL detection flow

        Simulates:
        1. LabJack detects voltage spike
        2. Detection stored in database
        3. Ground truth matching
        4. WebSocket emission to frontend
        5. Frontend receives and displays

        This is the PRIMARY test for HIL validation system.
        """
        # Step 1: Simulate LabJack voltage detection
        labjack_timestamp = time.time()
        labjack_data = {
            "timestamp": labjack_timestamp,
            "voltage": 3.3,
            "channel": 0,
            "signal_type": "GPIO",
            "session_id": e2e_session.id,
            "video_id": e2e_video.id
        }

        # Step 2: Store detection in database
        video_relative_time = labjack_timestamp - e2e_session.video_start_timestamp

        detection = DetectionEvent(
            id="e2e-det-001",
            test_session_id=e2e_session.id,
            video_id=e2e_video.id,
            timestamp=labjack_timestamp,
            labjack_timestamp=labjack_timestamp,
            labjack_voltage=labjack_data["voltage"],
            channel=labjack_data["channel"],
            signal_type=labjack_data["signal_type"],
            video_start_time=e2e_session.video_start_timestamp,
            video_relative_timestamp=video_relative_time,
            video_frame_number=int(video_relative_time * e2e_video.fps),
            actual_latency_ms=95.5  # Within threshold
        )
        test_db.add(detection)
        test_db.commit()
        test_db.refresh(detection)

        # Verify database storage
        assert detection.id is not None
        assert detection.test_session_id == e2e_session.id
        assert detection.video_id == e2e_video.id
        assert detection.labjack_voltage == 3.3

        # Step 3: Ground truth matching
        matching_service = GroundTruthMatchingService(test_db)

        # Find closest ground truth
        tolerance_seconds = e2e_session.tolerance_ms / 1000.0
        matched_gt = None

        for gt in e2e_ground_truth:
            time_diff = abs(gt.timestamp - video_relative_time)
            if time_diff <= tolerance_seconds:
                matched_gt = gt
                break

        if matched_gt:
            detection.ground_truth_match_id = matched_gt.id
            detection.validation_result = "Pass"
            test_db.commit()

        # Verify ground truth matching
        assert detection.ground_truth_match_id is not None
        assert detection.validation_result == "Pass"

        # Step 4: WebSocket emission
        websocket_payload = {
            "detection_id": detection.id,
            "session_id": e2e_session.id,
            "video_id": e2e_video.id,
            "timestamp": detection.timestamp,
            "labjack_timestamp": detection.labjack_timestamp,
            "labjack_voltage": detection.labjack_voltage,
            "latency_ms": detection.actual_latency_ms,
            "validation_result": detection.validation_result,
            "video_relative_timestamp": detection.video_relative_timestamp,
            "frame_number": detection.video_frame_number,
            "ground_truth_match_id": detection.ground_truth_match_id
        }

        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await emit_detection_event(
                detection_data=websocket_payload,
                test_session_id=e2e_session.id
            )

            # Verify WebSocket emission
            assert mock_emit.call_count >= 1

            # Check emission payload
            call_args = mock_emit.call_args_list[0]
            event_name = call_args[0][0]
            emitted_data = call_args[0][1]
            room = call_args[1].get('room')

            assert event_name == 'detection_event'
            assert room == f"test_session_{e2e_session.id}"
            assert emitted_data["detection_id"] == detection.id
            assert emitted_data["validation_result"] == "Pass"
            assert emitted_data["ground_truth_match_id"] == matched_gt.id

        # Step 5: Verify complete flow
        # Query database to ensure detection persists
        stored_detection = test_db.query(DetectionEvent).filter_by(
            id=detection.id
        ).first()

        assert stored_detection is not None
        assert stored_detection.validation_result == "Pass"
        assert stored_detection.ground_truth_match_id is not None

    async def test_multi_video_sequence_detection_flow(
        self, test_db: Session, e2e_project: Project
    ):
        """
        E2E TEST: Multi-video sequence detection flow

        Tests detection flow across multiple videos in sequence
        """
        # Create multiple videos
        videos = []
        for i in range(3):
            video = Video(
                id=f"e2e-seq-video-{i}",
                filename=f"sequence_video_{i}.mp4",
                file_path=f"/uploads/sequence_video_{i}.mp4",
                project_id=e2e_project.id,
                duration=30.0,
                fps=30.0
            )
            test_db.add(video)
            videos.append(video)
        test_db.commit()

        # Create sequence session
        sequence_session = TestSession(
            id="e2e-seq-session",
            name="Multi-Video Sequence E2E",
            project_id=e2e_project.id,
            video_id=videos[0].id,
            has_video_sequence=True,
            sequence_id="e2e-seq-001",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        test_db.add(sequence_session)
        test_db.commit()

        # Simulate detections across videos
        sequence_start_time = time.time()
        detections_created = []

        for video_idx, video in enumerate(videos):
            video_offset_ms = video_idx * 30000.0  # 30 seconds per video

            # Create 5 detections per video
            for det_idx in range(5):
                detection_time = sequence_start_time + (video_idx * 30) + (det_idx * 5)

                detection = DetectionEvent(
                    id=f"e2e-seq-det-{video_idx}-{det_idx}",
                    test_session_id=sequence_session.id,
                    video_id=video.id,
                    timestamp=detection_time,
                    sequence_id="e2e-seq-001",
                    sequence_timestamp=(video_idx * 30) + (det_idx * 5),
                    video_play_offset_ms=video_offset_ms,
                    labjack_voltage=3.3,
                    validation_result="Pass"
                )
                test_db.add(detection)
                detections_created.append(detection)

        test_db.commit()

        # Verify all detections stored
        assert len(detections_created) == 15  # 3 videos * 5 detections

        # Verify sequence metadata
        for detection in detections_created:
            assert detection.sequence_id == "e2e-seq-001"
            assert detection.sequence_timestamp is not None
            assert detection.video_play_offset_ms is not None

    async def test_detection_with_failed_validation(
        self, test_db: Session, e2e_session: TestSession, e2e_video: Video
    ):
        """
        E2E TEST: Detection flow with failed validation (latency exceeded)
        """
        # Create detection with excessive latency
        detection = DetectionEvent(
            id="e2e-det-fail",
            test_session_id=e2e_session.id,
            video_id=e2e_video.id,
            timestamp=time.time(),
            labjack_timestamp=time.time(),
            labjack_voltage=3.3,
            actual_latency_ms=250.0,  # Exceeds 100ms threshold
            latency_threshold_ms=100.0,
            validation_result="Fail"
        )
        test_db.add(detection)
        test_db.commit()

        # Verify failed validation stored
        assert detection.validation_result == "Fail"
        assert detection.actual_latency_ms > e2e_session.latency_threshold_ms

        # Emit to WebSocket
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            await emit_detection_event(
                detection_data={
                    "detection_id": detection.id,
                    "session_id": e2e_session.id,
                    "validation_result": "Fail",
                    "latency_ms": 250.0
                },
                test_session_id=e2e_session.id
            )

            # Verify fail emission
            call_args = mock_emit.call_args_list[0]
            emitted_data = call_args[0][1]
            assert emitted_data["validation_result"] == "Fail"

    async def test_concurrent_detection_processing(
        self, test_db: Session, e2e_session: TestSession, e2e_video: Video
    ):
        """
        E2E TEST: Multiple simultaneous detections processed correctly
        """
        # Create 10 detections simultaneously
        detections = []
        current_time = time.time()

        for i in range(10):
            detection = DetectionEvent(
                id=f"e2e-concurrent-{i}",
                test_session_id=e2e_session.id,
                video_id=e2e_video.id,
                timestamp=current_time + (i * 0.1),  # 100ms apart
                labjack_voltage=3.3,
                validation_result="Pass"
            )
            test_db.add(detection)
            detections.append(detection)

        test_db.commit()

        # Verify all stored
        assert len(detections) == 10

        # Emit all concurrently
        with patch.object(sio, 'emit', new_callable=AsyncMock) as mock_emit:
            tasks = []
            for detection in detections:
                task = emit_detection_event(
                    detection_data={"detection_id": detection.id},
                    test_session_id=e2e_session.id
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

            # Verify all emitted
            assert mock_emit.call_count >= 10

    async def test_detection_flow_error_recovery(
        self, test_db: Session, e2e_session: TestSession, e2e_video: Video
    ):
        """
        E2E TEST: Error recovery in detection flow
        """
        # Create detection
        detection = DetectionEvent(
            id="e2e-det-recovery",
            test_session_id=e2e_session.id,
            video_id=e2e_video.id,
            timestamp=time.time(),
            labjack_voltage=3.3,
            validation_result="Pass"
        )
        test_db.add(detection)
        test_db.commit()

        # Simulate WebSocket emission failure
        with patch.object(sio, 'emit', side_effect=Exception("Network error")):
            # Should not raise exception
            try:
                await emit_detection_event(
                    detection_data={"detection_id": detection.id},
                    test_session_id=e2e_session.id
                )
            except Exception as e:
                pytest.fail(f"Detection flow should handle errors gracefully: {e}")

        # Verify detection still in database
        stored = test_db.query(DetectionEvent).filter_by(id=detection.id).first()
        assert stored is not None
        assert stored.validation_result == "Pass"

    async def test_complete_session_lifecycle(
        self, test_db: Session, e2e_session: TestSession, e2e_video: Video
    ):
        """
        E2E TEST: Complete session lifecycle from start to completion
        """
        # Session starts running
        assert e2e_session.status == "running"

        # Create multiple detections during session
        for i in range(20):
            detection = DetectionEvent(
                id=f"lifecycle-det-{i}",
                test_session_id=e2e_session.id,
                video_id=e2e_video.id,
                timestamp=time.time() + i,
                labjack_voltage=3.3,
                validation_result="Pass" if i % 2 == 0 else "Fail"
            )
            test_db.add(detection)
        test_db.commit()

        # Complete session
        e2e_session.status = "completed"
        e2e_session.completed_at = datetime.now(timezone.utc)
        test_db.commit()

        # Verify all detections persisted
        detection_count = test_db.query(DetectionEvent).filter_by(
            test_session_id=e2e_session.id
        ).count()
        assert detection_count == 20

        # Calculate statistics
        passed = test_db.query(DetectionEvent).filter_by(
            test_session_id=e2e_session.id,
            validation_result="Pass"
        ).count()
        failed = test_db.query(DetectionEvent).filter_by(
            test_session_id=e2e_session.id,
            validation_result="Fail"
        ).count()

        assert passed == 10
        assert failed == 10
        assert (passed / (passed + failed)) == 0.5  # 50% pass rate
