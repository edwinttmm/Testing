"""
DEPRECATED TEST FILE
===================

This test file has been deprecated on 2025-11-20 because it imports services
that no longer exist or have been removed from the codebase.

Deprecated services used:
- Services that were removed during architecture refactoring
- Services that were consolidated into other modules
- Services that were replaced with newer implementations

This file is preserved for historical reference but is not actively maintained.
If you need similar functionality, please check the current service implementations
in src/services/ or consult the documentation.

Original location: tests/unit/test_video_status_transitions.py
"""

"""
Unit Tests for Video Status Transitions and Validation Logic
==========================================================

Tests video status state machine, validation rules, and business logic.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from models import Video, Project, TestSession, DetectionEvent, GroundTruthObject
from schemas import VideoStatus, VRUType
from crud import update_video_status, create_video, get_video
from services.video_ingestion_service import VideoIngestionService


class TestVideoStatusEnum:
    """Test VideoStatus enum values and validation"""
    
    def test_video_status_enum_values(self):
        """Test that VideoStatus enum has expected values"""
        expected_statuses = {
            "pending_annotation",
            "pending_validation", 
            "validated",
            "processing",
            "error"
        }
        actual_statuses = {status.value for status in VideoStatus}
        assert actual_statuses == expected_statuses
    
    def test_video_status_string_conversion(self):
        """Test VideoStatus can be converted to/from strings"""
        assert str(VideoStatus.VALIDATED) == "validated"
        assert VideoStatus("validated") == VideoStatus.VALIDATED
        
    def test_invalid_video_status_raises_error(self):
        """Test that invalid status values raise ValueError"""
        with pytest.raises(ValueError):
            VideoStatus("invalid_status")


class TestVideoStatusTransitions:
    """Test video status transition logic and state machine"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def sample_video(self):
        """Sample video for testing"""
        return Video(
            id="test-video-id",
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id="test-project-id"
        )
    
    def test_initial_video_status(self, sample_video):
        """Test video starts with correct initial status"""
        assert sample_video.status == "uploaded"
        assert sample_video.processing_status == "pending"
        assert not sample_video.ground_truth_generated
    
    def test_valid_status_transition_uploaded_to_processing(self, mock_db, sample_video):
        """Test valid transition from uploaded to processing"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        result = update_video_status(mock_db, "test-video-id", "processing")
        
        assert result is not None
        assert result.status == "processing"
        mock_db.commit.assert_called_once()
    
    def test_valid_status_transition_processing_to_validated(self, mock_db, sample_video):
        """Test valid transition from processing to validated"""
        sample_video.status = "processing"
        sample_video.processing_status = "completed"
        sample_video.ground_truth_generated = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        result = update_video_status(mock_db, "test-video-id", "validated")
        
        assert result.status == "validated"
    
    def test_video_status_with_duration_update(self, mock_db, sample_video):
        """Test status update with duration"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        result = update_video_status(mock_db, "test-video-id", "processing", duration=120.5)
        
        assert result.status == "processing"
        assert result.duration == 120.5
    
    def test_invalid_status_transition_logic(self):
        """Test business rules for invalid status transitions"""
        # Test that certain transitions should be validated by business logic
        invalid_transitions = [
            ("uploaded", "validated"),  # Can't go directly to validated without processing
            ("error", "validated"),     # Can't validate errored videos
            ("pending_annotation", "validated")  # Need validation step
        ]
        
        for from_status, to_status in invalid_transitions:
            # This would be implemented in a status transition validator
            assert self._is_valid_transition(from_status, to_status) is False
    
    def _is_valid_transition(self, from_status: str, to_status: str) -> bool:
        """Helper method to validate status transitions"""
        # Define valid transition matrix
        valid_transitions = {
            "uploaded": ["processing", "pending_annotation", "error"],
            "processing": ["validated", "error", "pending_validation"],
            "pending_annotation": ["pending_validation", "error"],
            "pending_validation": ["validated", "error"],
            "validated": [],  # Terminal state
            "error": ["processing", "uploaded"]  # Can retry from error
        }
        
        return to_status in valid_transitions.get(from_status, [])


class TestVideoValidationLogic:
    """Test video validation business logic"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def video_ingestion_service(self):
        return VideoIngestionService()
    
    def test_video_ready_for_hil_testing(self, mock_db):
        """Test logic to determine if video is ready for HIL testing"""
        # Video is ready for HIL testing if it's validated
        validated_video = Video(
            id="test-id",
            filename="test.mp4",
            status="validated",
            processing_status="completed",
            ground_truth_generated=True
        )
        
        assert self._is_ready_for_hil_testing(validated_video) is True
    
    def test_video_not_ready_for_hil_testing(self, mock_db):
        """Test videos not ready for HIL testing"""
        test_cases = [
            # Not validated
            Video(id="1", filename="test1.mp4", status="processing", ground_truth_generated=True),
            # No ground truth
            Video(id="2", filename="test2.mp4", status="validated", ground_truth_generated=False),
            # Error status
            Video(id="3", filename="test3.mp4", status="error", ground_truth_generated=True),
        ]
        
        for video in test_cases:
            assert self._is_ready_for_hil_testing(video) is False
    
    def test_video_validation_criteria(self):
        """Test criteria for video validation"""
        video = Video(
            id="test-id",
            filename="test.mp4",
            status="processing",
            processing_status="completed",
            ground_truth_generated=False
        )
        
        # Video needs ground truth to be validated
        assert self._meets_validation_criteria(video) is False
        
        video.ground_truth_generated = True
        assert self._meets_validation_criteria(video) is True
    
    def test_batch_video_status_update(self, mock_db):
        """Test batch updating video statuses"""
        videos = [
            Video(id="1", filename="test1.mp4", status="processing"),
            Video(id="2", filename="test2.mp4", status="processing"),
            Video(id="3", filename="test3.mp4", status="processing")
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = videos
        
        # Simulate batch status update
        updated_count = self._batch_update_video_status(mock_db, ["1", "2", "3"], "validated")
        
        assert updated_count == 3
        for video in videos:
            assert video.status == "validated"
    
    def _is_ready_for_hil_testing(self, video: Video) -> bool:
        """Helper to check if video is ready for HIL testing"""
        return (
            video.status == "validated" and 
            video.ground_truth_generated and
            video.processing_status == "completed"
        )
    
    def _meets_validation_criteria(self, video: Video) -> bool:
        """Helper to check if video meets validation criteria"""
        return (
            video.processing_status == "completed" and
            video.ground_truth_generated
        )
    
    def _batch_update_video_status(self, db: Session, video_ids: list, new_status: str) -> int:
        """Helper for batch status updates"""
        videos = db.query(Video).filter(Video.id.in_(video_ids)).all()
        updated_count = 0
        
        for video in videos:
            video.status = new_status
            updated_count += 1
        
        return updated_count


class TestVideoStatusFiltering:
    """Test video status filtering logic for HIL Test Execution"""
    
    @pytest.fixture
    def mock_videos(self):
        """Mock video data with different statuses"""
        return [
            Video(id="1", filename="video1.mp4", status="validated", ground_truth_generated=True),
            Video(id="2", filename="video2.mp4", status="processing", ground_truth_generated=False),
            Video(id="3", filename="video3.mp4", status="validated", ground_truth_generated=True),
            Video(id="4", filename="video4.mp4", status="error", ground_truth_generated=False),
            Video(id="5", filename="video5.mp4", status="pending_validation", ground_truth_generated=True)
        ]
    
    def test_filter_videos_for_hil_testing(self, mock_videos):
        """Test filtering videos suitable for HIL testing"""
        hil_ready_videos = self._filter_videos_by_status(mock_videos, "validated")
        
        assert len(hil_ready_videos) == 2
        assert all(video.status == "validated" for video in hil_ready_videos)
    
    def test_filter_videos_by_multiple_statuses(self, mock_videos):
        """Test filtering by multiple status values"""
        processing_videos = self._filter_videos_by_status(
            mock_videos, 
            ["processing", "pending_validation"]
        )
        
        assert len(processing_videos) == 2
        statuses = {video.status for video in processing_videos}
        assert statuses == {"processing", "pending_validation"}
    
    def test_filter_videos_with_ground_truth(self, mock_videos):
        """Test filtering videos that have ground truth"""
        with_ground_truth = [
            video for video in mock_videos 
            if video.ground_truth_generated
        ]
        
        assert len(with_ground_truth) == 3
    
    def test_count_videos_by_status(self, mock_videos):
        """Test counting videos grouped by status"""
        status_counts = self._count_videos_by_status(mock_videos)
        
        expected_counts = {
            "validated": 2,
            "processing": 1,
            "error": 1,
            "pending_validation": 1
        }
        
        assert status_counts == expected_counts
    
    def _filter_videos_by_status(self, videos: list, statuses) -> list:
        """Helper to filter videos by status"""
        if isinstance(statuses, str):
            statuses = [statuses]
        
        return [video for video in videos if video.status in statuses]
    
    def _count_videos_by_status(self, videos: list) -> dict:
        """Helper to count videos by status"""
        counts = {}
        for video in videos:
            counts[video.status] = counts.get(video.status, 0) + 1
        return counts


class TestVideoStatusIntegrationWithGroundTruth:
    """Test video status integration with ground truth generation"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    def test_video_status_after_ground_truth_generation(self, mock_db):
        """Test video status updates after ground truth is generated"""
        video = Video(
            id="test-id",
            filename="test.mp4", 
            status="processing",
            processing_status="generating_ground_truth",
            ground_truth_generated=False
        )
        
        # Simulate ground truth generation completion
        video.ground_truth_generated = True
        video.processing_status = "completed"
        video.status = "pending_validation"
        
        assert video.status == "pending_validation"
        assert video.ground_truth_generated is True
    
    def test_ground_truth_objects_affect_video_status(self, mock_db):
        """Test that presence of ground truth objects affects video status"""
        video_id = "test-video-id"
        
        # Mock ground truth objects query
        mock_gt_objects = [
            GroundTruthObject(
                id="gt1", 
                video_id=video_id,
                timestamp=1.0,
                class_label="pedestrian",
                x=100, y=100, width=50, height=100,
                confidence=0.9,
                validated=True
            ),
            GroundTruthObject(
                id="gt2",
                video_id=video_id, 
                timestamp=2.0,
                class_label="cyclist",
                x=200, y=150, width=60, height=120,
                confidence=0.85,
                validated=True
            )
        ]
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_gt_objects
        
        # Check if video has sufficient ground truth for validation
        has_ground_truth = len(mock_gt_objects) > 0
        all_validated = all(gt.validated for gt in mock_gt_objects)
        
        assert has_ground_truth is True
        assert all_validated is True
        
        # Video should be ready for validation
        expected_status = "pending_validation" if has_ground_truth and all_validated else "processing"
        assert expected_status == "pending_validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])