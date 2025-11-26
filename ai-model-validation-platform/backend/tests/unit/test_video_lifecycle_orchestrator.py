"""
Unit Tests for Video Lifecycle Orchestrator
============================================

Tests the VideoSequenceOrchestrator service in isolation.

Author: QA Specialist Agent
Date: 2025-11-20
"""

import pytest
import time
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from services.video_lifecycle_orchestrator import (
    VideoSequenceOrchestrator,
    SequenceStatus,
    VideoStatus,
    VideoMetadata,
    SequenceVideoResult
)
from models import Video, GroundTruthObject, TestSession


class TestVideoSequenceOrchestratorInit:
    """Test orchestrator initialization."""

    def test_orchestrator_creates_successfully(self):
        """Test orchestrator can be instantiated."""
        orchestrator = VideoSequenceOrchestrator()

        assert orchestrator is not None
        assert orchestrator._active_sequences == {}

    def test_orchestrator_with_custom_timing_service(self):
        """Test orchestrator accepts custom timing service."""
        mock_timing_service = Mock()
        orchestrator = VideoSequenceOrchestrator(video_timing_service=mock_timing_service)

        assert orchestrator._timing_service == mock_timing_service


class TestStartSequence:
    """Test sequence initialization."""

    @pytest.fixture
    def mock_video_data(self, test_db):
        """Create mock video data."""
        from models import Project, Video, GroundTruthObject

        project = Project(
            id=str(uuid.uuid4()),
            name="Test Project"
        )
        test_db.add(project)

        video = Video(
            id=str(uuid.uuid4()),
            filename="test.mp4",
            duration=10.0,
            fps=30.0,
            frame_count=300,
            project_id=project.id
        )
        test_db.add(video)

        # Add ground truth
        for i in range(3):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                timestamp=2.0 + i,
                frame_number=60 + (i * 30),
                object_class="vehicle"
            )
            test_db.add(gt)

        test_db.commit()
        return {'project': project, 'video': video}

    def test_start_sequence_creates_sequence(self, test_db, mock_video_data):
        """Test starting a new sequence."""
        orchestrator = VideoSequenceOrchestrator()
        project = mock_video_data['project']
        video = mock_video_data['video']

        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video.id],
            max_latency_ms=100.0,
            db=test_db
        )

        assert sequence_id is not None
        assert sequence_id in orchestrator._active_sequences

        sequence = orchestrator._active_sequences[sequence_id]
        assert sequence.status == SequenceStatus.READY
        assert sequence.video_ids == [video.id]
        assert sequence.max_latency_ms == 100.0
        assert sequence.total_expected_detections == 3

    def test_start_sequence_loads_video_metadata(self, test_db, mock_video_data):
        """Test sequence loads video metadata correctly."""
        orchestrator = VideoSequenceOrchestrator()
        project = mock_video_data['project']
        video = mock_video_data['video']

        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video.id],
            max_latency_ms=100.0,
            db=test_db
        )

        sequence = orchestrator._active_sequences[sequence_id]

        assert video.id in sequence.video_metadata
        metadata = sequence.video_metadata[video.id]

        assert metadata.video_id == video.id
        assert metadata.filename == "test.mp4"
        assert metadata.duration == 10.0
        assert metadata.fps == 30.0
        assert metadata.ground_truth_count == 3

    def test_start_sequence_with_invalid_video(self, test_db, mock_video_data):
        """Test starting sequence with non-existent video fails gracefully."""
        orchestrator = VideoSequenceOrchestrator()
        project = mock_video_data['project']
        fake_video_id = str(uuid.uuid4())

        with pytest.raises(Exception):  # Should raise VideoSequenceOrchestratorError
            orchestrator.start_sequence(
                project_id=project.id,
                video_ids=[fake_video_id],
                max_latency_ms=100.0,
                db=test_db
            )


class TestVideoStartedNotification:
    """Test video start notification handling."""

    @pytest.fixture
    def setup_sequence(self, test_db):
        """Setup test sequence."""
        from models import Project, Video, GroundTruthObject

        project = Project(id=str(uuid.uuid4()), name="Test")
        test_db.add(project)

        video = Video(
            id=str(uuid.uuid4()),
            filename="test.mp4",
            duration=10.0,
            fps=30.0,
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        orchestrator = VideoSequenceOrchestrator()
        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video.id],
            max_latency_ms=100.0,
            db=test_db
        )

        return {
            'orchestrator': orchestrator,
            'sequence_id': sequence_id,
            'video': video
        }

    def test_notify_video_started_updates_state(self, test_db, setup_sequence):
        """Test video start notification updates sequence state."""
        orchestrator = setup_sequence['orchestrator']
        sequence_id = setup_sequence['sequence_id']
        video = setup_sequence['video']

        video_start = time.time()
        success = orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id=video.id,
            actual_start_timestamp=video_start,
            db=test_db
        )

        assert success is True

        sequence = orchestrator._active_sequences[sequence_id]
        assert sequence.sequence_start_time == video_start
        assert sequence.status == SequenceStatus.RUNNING

        metadata = sequence.video_metadata[video.id]
        assert metadata.video_start_time == video_start
        assert metadata.video_play_offset_ms == 0.0  # First video

    def test_notify_video_started_sets_play_offset(self, test_db):
        """Test second video gets correct play offset."""
        from models import Project, Video

        project = Project(id=str(uuid.uuid4()), name="Test")
        test_db.add(project)

        video1 = Video(
            id=str(uuid.uuid4()),
            filename="video1.mp4",
            duration=5.0,
            fps=30.0,
            project_id=project.id
        )
        video2 = Video(
            id=str(uuid.uuid4()),
            filename="video2.mp4",
            duration=5.0,
            fps=30.0,
            project_id=project.id
        )
        test_db.add_all([video1, video2])
        test_db.commit()

        orchestrator = VideoSequenceOrchestrator()
        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video1.id, video2.id],
            max_latency_ms=100.0,
            db=test_db
        )

        # Start first video
        sequence_start = time.time()
        orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id=video1.id,
            actual_start_timestamp=sequence_start,
            db=test_db
        )

        # Start second video 6 seconds later
        video2_start = sequence_start + 6.0
        orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id=video2.id,
            actual_start_timestamp=video2_start,
            db=test_db
        )

        sequence = orchestrator._active_sequences[sequence_id]
        metadata2 = sequence.video_metadata[video2.id]

        # Play offset should be 6000ms
        assert metadata2.video_play_offset_ms == 6000.0

    @patch('services.video_sequence_orchestrator.validate_clock_sync')
    def test_notify_video_started_rejects_bad_clock_sync(
        self,
        mock_validate,
        test_db,
        setup_sequence
    ):
        """Test video start rejected if clock sync is bad."""
        from services.clock_sync_service_v2 import ClockSkewError

        mock_validate.side_effect = ClockSkewError(
            "Clock skew too large",
            drift_seconds=10.0
        )

        orchestrator = setup_sequence['orchestrator']
        sequence_id = setup_sequence['sequence_id']
        video = setup_sequence['video']

        # Should fail due to clock skew
        success = orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id=video.id,
            actual_start_timestamp=time.time(),
            db=test_db
        )

        assert success is False


class TestVideoEndedNotification:
    """Test video end notification handling."""

    @pytest.fixture
    def setup_started_video(self, test_db):
        """Setup sequence with started video."""
        from models import Project, Video, GroundTruthObject

        project = Project(id=str(uuid.uuid4()), name="Test")
        test_db.add(project)

        video = Video(
            id=str(uuid.uuid4()),
            filename="test.mp4",
            duration=10.0,
            fps=30.0,
            project_id=project.id
        )
        test_db.add(video)

        # Add ground truth
        gt = GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=video.id,
            timestamp=5.0,
            frame_number=150,
            object_class="vehicle"
        )
        test_db.add(gt)
        test_db.commit()

        orchestrator = VideoSequenceOrchestrator()
        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video.id],
            max_latency_ms=100.0,
            db=test_db
        )

        video_start = time.time()
        orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id=video.id,
            actual_start_timestamp=video_start,
            db=test_db
        )

        return {
            'orchestrator': orchestrator,
            'sequence_id': sequence_id,
            'video': video,
            'video_start': video_start
        }

    def test_notify_video_ended_updates_state(self, test_db, setup_started_video):
        """Test video end notification updates state."""
        orchestrator = setup_started_video['orchestrator']
        sequence_id = setup_started_video['sequence_id']
        video = setup_started_video['video']
        video_start = setup_started_video['video_start']

        video_end = video_start + 10.0
        success = orchestrator.notify_video_ended(
            sequence_id=sequence_id,
            video_id=video.id,
            actual_end_timestamp=video_end,
            db=test_db
        )

        assert success is True

        sequence = orchestrator._active_sequences[sequence_id]
        metadata = sequence.video_metadata[video.id]
        result = sequence.video_results[video.id]

        assert metadata.video_end_time == video_end
        assert result.status == VideoStatus.COMPLETED
        assert result.video_end_time == video_end

    def test_notify_video_ended_evaluates_results(self, test_db, setup_started_video):
        """Test video end triggers result evaluation."""
        orchestrator = setup_started_video['orchestrator']
        sequence_id = setup_started_video['sequence_id']
        video = setup_started_video['video']
        video_start = setup_started_video['video_start']

        video_end = video_start + 10.0
        orchestrator.notify_video_ended(
            sequence_id=sequence_id,
            video_id=video.id,
            actual_end_timestamp=video_end,
            db=test_db
        )

        sequence = orchestrator._active_sequences[sequence_id]
        result = sequence.video_results[video.id]

        # Evaluation should have run
        assert result.evaluated_at is not None
        assert result.evaluation_duration_ms is not None
        assert result.expected_detections == 1  # We added 1 GT


class TestDetectionEventProcessing:
    """Test detection event processing."""

    @pytest.fixture
    def setup_running_sequence(self, test_db):
        """Setup running sequence."""
        from models import Project, Video

        project = Project(id=str(uuid.uuid4()), name="Test")
        test_db.add(project)

        video = Video(
            id=str(uuid.uuid4()),
            filename="test.mp4",
            duration=10.0,
            fps=30.0,
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        orchestrator = VideoSequenceOrchestrator()
        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video.id],
            max_latency_ms=100.0,
            db=test_db
        )

        video_start = time.time()
        orchestrator.notify_video_started(
            sequence_id=sequence_id,
            video_id=video.id,
            actual_start_timestamp=video_start,
            db=test_db
        )

        return {
            'orchestrator': orchestrator,
            'sequence_id': sequence_id,
            'video': video,
            'video_start': video_start
        }

    def test_process_detection_creates_event(self, test_db, setup_running_sequence):
        """Test detection event processing creates DetectionEvent."""
        orchestrator = setup_running_sequence['orchestrator']
        sequence_id = setup_running_sequence['sequence_id']
        video_start = setup_running_sequence['video_start']

        detection_time = video_start + 5.0
        labjack_signal = {
            'voltage': 3.3,
            'channel': 0,
            'signal_type': 'digital'
        }

        detection_id = orchestrator.process_detection_event(
            sequence_id=sequence_id,
            labjack_signal=labjack_signal,
            sequence_timestamp=detection_time,
            db=test_db
        )

        assert detection_id is not None

        # Verify detection stored in database
        from models import DetectionEvent
        detection = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.id == detection_id
        )).scalar_one_or_none()

        assert detection is not None
        assert detection.video_relative_timestamp is not None
        assert abs(detection.video_relative_timestamp - 5.0) < 0.01

    def test_process_detection_calculates_frame_number(
        self,
        test_db,
        setup_running_sequence
    ):
        """Test detection calculates correct frame number."""
        orchestrator = setup_running_sequence['orchestrator']
        sequence_id = setup_running_sequence['sequence_id']
        video_start = setup_running_sequence['video_start']

        # Detection at 2.5 seconds
        detection_time = video_start + 2.5

        detection_id = orchestrator.process_detection_event(
            sequence_id=sequence_id,
            labjack_signal={'voltage': 3.3},
            sequence_timestamp=detection_time,
            db=test_db
        )

        from models import DetectionEvent
        detection = test_db.execute(select(DetectionEvent).where(
            DetectionEvent.id == detection_id
        )).scalar_one_or_none()

        # At 30fps, 2.5s = frame 75
        assert detection.video_frame_number == 75

    def test_process_detection_updates_sequence_metrics(
        self,
        test_db,
        setup_running_sequence
    ):
        """Test detection updates sequence-level metrics."""
        orchestrator = setup_running_sequence['orchestrator']
        sequence_id = setup_running_sequence['sequence_id']
        video_start = setup_running_sequence['video_start']

        # Process 3 detections
        for i in range(3):
            detection_time = video_start + (i + 1)
            orchestrator.process_detection_event(
                sequence_id=sequence_id,
                labjack_signal={'voltage': 3.3},
                sequence_timestamp=detection_time,
                db=test_db
            )

        sequence = orchestrator._active_sequences[sequence_id]
        assert sequence.total_detected == 3


class TestSequenceStatus:
    """Test sequence status retrieval."""

    def test_get_sequence_status_returns_correct_info(self, test_db):
        """Test getting sequence status."""
        from models import Project, Video

        project = Project(id=str(uuid.uuid4()), name="Test")
        test_db.add(project)

        video = Video(
            id=str(uuid.uuid4()),
            filename="test.mp4",
            duration=10.0,
            fps=30.0,
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        orchestrator = VideoSequenceOrchestrator()
        sequence_id = orchestrator.start_sequence(
            project_id=project.id,
            video_ids=[video.id],
            max_latency_ms=100.0,
            db=test_db
        )

        status = orchestrator.get_sequence_status(sequence_id)

        assert status['sequence_id'] == sequence_id
        assert status['status'] == 'ready'
        assert status['total_videos'] == 1
        assert status['current_video_index'] == 0
