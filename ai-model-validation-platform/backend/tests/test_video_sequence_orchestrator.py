"""
Unit tests for VideoSequenceOrchestrator service

Tests the core functionality of multi-video sequential testing including:
- Sequence initialization
- Video timing management
- Detection correlation
- Per-video evaluation
- Sequence-level aggregation
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

# Import the orchestrator
from services.video_sequence_orchestrator import (
    VideoSequenceOrchestrator,
    VideoSequenceOrchestratorError,
    SequenceStatus,
    VideoStatus,
    VideoMetadata,
    SequenceVideoResult
)


class TestVideoSequenceOrchestrator:
    """Test suite for VideoSequenceOrchestrator"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_video_timing_service(self):
        """Create a mock video timing service"""
        service = MagicMock()
        service.start_video_timing.return_value = time.time()
        return service

    @pytest.fixture
    def orchestrator(self, mock_video_timing_service):
        """Create orchestrator instance with mocked timing service"""
        return VideoSequenceOrchestrator(video_timing_service=mock_video_timing_service)

    @pytest.fixture
    def sample_videos(self, mock_db):
        """Create sample video data"""
        videos = []
        for i in range(3):
            video = Mock()
            video.id = f"video-{i}"
            video.filename = f"test_video_{i}.mp4"
            video.duration = 10.0 + i * 5  # 10s, 15s, 20s
            video.fps = 30.0
            videos.append(video)
        return videos

    def test_initialization(self, orchestrator):
        """Test orchestrator initialization"""
        assert orchestrator is not None
        assert orchestrator._timing_service is not None
        assert isinstance(orchestrator._active_sequences, dict)

    def test_start_sequence_success(self, orchestrator, mock_db, sample_videos):
        """Test successful sequence initialization"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup mocks
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]  # 5 ground truth objects per video

            # Start sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            # Verify sequence created
            assert sequence_id in orchestrator._active_sequences
            sequence = orchestrator._active_sequences[sequence_id]

            assert sequence.status == SequenceStatus.READY
            assert len(sequence.video_ids) == 3
            assert sequence.total_expected_detections == 15  # 3 videos * 5 detections

    def test_start_sequence_with_invalid_video(self, orchestrator, mock_db):
        """Test sequence initialization with invalid video"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video:
            mock_get_video.return_value = None

            with pytest.raises(VideoSequenceOrchestratorError):
                orchestrator.start_sequence(
                    project_id="test-project",
                    video_ids=["invalid-video"],
                    max_latency_ms=100.0,
                    db=mock_db
                )

    def test_notify_video_started(self, orchestrator, mock_db, sample_videos):
        """Test video start notification"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]

            # Initialize sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            # Notify video started
            start_time = time.time()
            result = orchestrator.notify_video_started(
                sequence_id=sequence_id,
                video_id=video_ids[0],
                actual_start_timestamp=start_time,
                db=mock_db
            )

            assert result is True
            sequence = orchestrator._active_sequences[sequence_id]
            assert sequence.status == SequenceStatus.RUNNING
            assert sequence.sequence_start_time == start_time

            metadata = sequence.video_metadata[video_ids[0]]
            assert metadata.video_start_time == start_time
            assert metadata.video_play_offset_ms == 0.0  # First video

    def test_notify_video_ended(self, orchestrator, mock_db, sample_videos):
        """Test video end notification"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]

            # Initialize and start sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            start_time = time.time()
            orchestrator.notify_video_started(
                sequence_id=sequence_id,
                video_id=video_ids[0],
                actual_start_timestamp=start_time,
                db=mock_db
            )

            # Mock query for detection events
            mock_db.query.return_value.filter.return_value.all.return_value = []

            # Notify video ended
            end_time = start_time + 10.0
            result = orchestrator.notify_video_ended(
                sequence_id=sequence_id,
                video_id=video_ids[0],
                actual_end_timestamp=end_time,
                db=mock_db
            )

            assert result is True
            sequence = orchestrator._active_sequences[sequence_id]
            video_result = sequence.video_results[video_ids[0]]
            assert video_result.status == VideoStatus.COMPLETED
            assert video_result.video_end_time == end_time

    def test_process_detection_event(self, orchestrator, mock_db, sample_videos):
        """Test detection event processing"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]

            # Initialize and start sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            start_time = time.time()
            orchestrator.notify_video_started(
                sequence_id=sequence_id,
                video_id=video_ids[0],
                actual_start_timestamp=start_time,
                db=mock_db
            )

            # Process detection event
            detection_time = start_time + 2.0  # 2 seconds into video
            labjack_signal = {
                'voltage': 3.3,
                'channel': 'AIN0'
            }

            detection_id = orchestrator.process_detection_event(
                sequence_id=sequence_id,
                labjack_signal=labjack_signal,
                sequence_timestamp=detection_time,
                db=mock_db
            )

            # Verify detection was created
            assert detection_id is not None
            sequence = orchestrator._active_sequences[sequence_id]
            video_result = sequence.video_results[video_ids[0]]
            assert video_result.detected_count == 1

    def test_determine_video_for_detection(self, orchestrator, mock_db, sample_videos):
        """Test detection-to-video correlation"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]

            # Initialize sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            sequence = orchestrator._active_sequences[sequence_id]

            # Start first video
            base_time = time.time()
            sequence.video_metadata[video_ids[0]].video_start_time = base_time
            sequence.video_metadata[video_ids[0]].video_end_time = base_time + 10.0

            # Start second video
            sequence.video_metadata[video_ids[1]].video_start_time = base_time + 10.0
            sequence.video_metadata[video_ids[1]].video_end_time = base_time + 25.0

            # Test detection correlation
            # Detection in first video
            detected_video = orchestrator._determine_video_for_detection(
                sequence, base_time + 5.0
            )
            assert detected_video == video_ids[0]

            # Detection in second video
            detected_video = orchestrator._determine_video_for_detection(
                sequence, base_time + 15.0
            )
            assert detected_video == video_ids[1]

            # Detection before any video
            detected_video = orchestrator._determine_video_for_detection(
                sequence, base_time - 5.0
            )
            assert detected_video is None

    def test_get_sequence_status(self, orchestrator, mock_db, sample_videos):
        """Test sequence status retrieval"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]

            # Initialize sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            # Get status
            status = orchestrator.get_sequence_status(sequence_id)

            assert status['sequence_id'] == sequence_id
            assert status['status'] == SequenceStatus.READY.value
            assert status['total_videos'] == 3
            assert status['current_video_index'] == 0

    def test_sequence_not_found_error(self, orchestrator):
        """Test error handling for non-existent sequence"""
        with pytest.raises(VideoSequenceOrchestratorError):
            orchestrator.get_sequence_status("invalid-sequence-id")

    def test_video_not_in_sequence_error(self, orchestrator, mock_db, sample_videos):
        """Test error handling for invalid video ID"""
        with patch('services.video_sequence_orchestrator.get_video') as mock_get_video, \
             patch('services.video_sequence_orchestrator.get_ground_truth_objects') as mock_get_gt:

            # Setup
            mock_get_video.side_effect = sample_videos
            mock_get_gt.return_value = [Mock() for _ in range(5)]

            # Initialize sequence
            video_ids = [v.id for v in sample_videos]
            sequence_id = orchestrator.start_sequence(
                project_id="test-project",
                video_ids=video_ids,
                max_latency_ms=100.0,
                db=mock_db
            )

            # Try to start invalid video
            with pytest.raises(VideoSequenceOrchestratorError):
                orchestrator.notify_video_started(
                    sequence_id=sequence_id,
                    video_id="invalid-video-id",
                    actual_start_timestamp=time.time(),
                    db=mock_db
                )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])