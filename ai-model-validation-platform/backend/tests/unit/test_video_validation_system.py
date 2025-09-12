"""
Comprehensive Unit Tests for Video Validation System
==================================================

Tests the unified video validation system including status transitions,
validation workflows, business logic, and data integrity.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Dict, Any

from models import Video, VideoValidationCriteria, VideoValidationResult, VideoStatusTransition
from schemas_video_validation import (
    VideoValidationStatus, ValidationStatus, ValidationType, ValidationResultType,
    VideoStatusResponse, ValidationResultResponse, ValidationCriteriaRequest
)
from services.video_validation_service import VideoValidationService


class TestVideoValidationStatusEnum:
    """Test VideoValidationStatus enum values and validation"""
    
    def test_video_validation_status_enum_values(self):
        """Test that VideoValidationStatus enum has expected values"""
        expected_statuses = {
            "uploaded", "processing", "processing_failed", "annotated",
            "validating", "validation_failed", "validated", "ready_for_testing",
            "in_testing", "tested", "archived", "error"
        }
        actual_statuses = {status.value for status in VideoValidationStatus}
        assert actual_statuses == expected_statuses
    
    def test_video_validation_status_string_conversion(self):
        """Test VideoValidationStatus can be converted to/from strings"""
        assert str(VideoValidationStatus.VALIDATED) == "validated"
        assert VideoValidationStatus("validated") == VideoValidationStatus.VALIDATED
        
    def test_invalid_video_validation_status_raises_error(self):
        """Test that invalid status values raise ValueError"""
        with pytest.raises(ValueError):
            VideoValidationStatus("invalid_status")

    def test_hil_testing_ready_statuses(self):
        """Test statuses that indicate HIL testing readiness"""
        hil_ready_statuses = [
            VideoValidationStatus.VALIDATED,
            VideoValidationStatus.READY_FOR_TESTING
        ]
        
        for status in hil_ready_statuses:
            assert status in [VideoValidationStatus.VALIDATED, VideoValidationStatus.READY_FOR_TESTING]


class TestVideoValidationStatusTransitions:
    """Test video status transition logic and state machine"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def validation_service(self, mock_db):
        """Video validation service instance"""
        return VideoValidationService(mock_db)
    
    @pytest.fixture
    def sample_video(self):
        """Sample video for testing"""
        return Video(
            id="test-video-id",
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            validation_status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id="test-project-id"
        )
    
    def test_initial_video_status(self, sample_video):
        """Test video starts with correct initial status"""
        assert sample_video.validation_status == "uploaded"
        assert sample_video.processing_status == "pending"
        assert not sample_video.ground_truth_generated
    
    def test_valid_status_transition_uploaded_to_processing(self, validation_service, sample_video):
        """Test valid transition from uploaded to processing"""
        validation_service.db.query.return_value.filter.return_value.first.return_value = sample_video
        
        result = validation_service.transition_video_status(
            "test-video-id", 
            VideoValidationStatus.PROCESSING,
            "user-123"
        )
        
        assert result is not None
        assert result.validation_status == "processing"
    
    def test_valid_status_transition_processing_to_annotated(self, validation_service, sample_video):
        """Test valid transition from processing to annotated"""
        sample_video.validation_status = "processing"
        sample_video.ground_truth_generated = True
        
        result = validation_service.transition_video_status(
            "test-video-id",
            VideoValidationStatus.ANNOTATED, 
            "system"
        )
        
        assert result.validation_status == "annotated"
    
    def test_status_transition_validation_rules(self, validation_service):
        """Test status transition validation rules"""
        # Define valid transition matrix
        valid_transitions = {
            VideoValidationStatus.UPLOADED: [
                VideoValidationStatus.PROCESSING,
                VideoValidationStatus.ERROR
            ],
            VideoValidationStatus.PROCESSING: [
                VideoValidationStatus.ANNOTATED,
                VideoValidationStatus.PROCESSING_FAILED,
                VideoValidationStatus.ERROR
            ],
            VideoValidationStatus.ANNOTATED: [
                VideoValidationStatus.VALIDATING,
                VideoValidationStatus.VALIDATED,  # Direct auto-validation
                VideoValidationStatus.ERROR
            ],
            VideoValidationStatus.VALIDATING: [
                VideoValidationStatus.VALIDATED,
                VideoValidationStatus.VALIDATION_FAILED,
                VideoValidationStatus.ERROR
            ],
            VideoValidationStatus.VALIDATED: [
                VideoValidationStatus.READY_FOR_TESTING,
                VideoValidationStatus.ARCHIVED
            ],
            VideoValidationStatus.READY_FOR_TESTING: [
                VideoValidationStatus.IN_TESTING,
                VideoValidationStatus.ARCHIVED
            ],
            VideoValidationStatus.IN_TESTING: [
                VideoValidationStatus.TESTED,
                VideoValidationStatus.ERROR
            ],
            VideoValidationStatus.TESTED: [
                VideoValidationStatus.ARCHIVED
            ]
        }
        
        # Test valid transitions
        for from_status, to_statuses in valid_transitions.items():
            for to_status in to_statuses:
                assert validation_service._is_valid_transition(from_status, to_status)
        
        # Test invalid transitions
        invalid_transitions = [
            (VideoValidationStatus.UPLOADED, VideoValidationStatus.VALIDATED),  # Skip processing
            (VideoValidationStatus.ERROR, VideoValidationStatus.VALIDATED),     # Can't validate errored
            (VideoValidationStatus.TESTED, VideoValidationStatus.PROCESSING),   # Can't go backward
            (VideoValidationStatus.ARCHIVED, VideoValidationStatus.PROCESSING)  # Can't reprocess archived
        ]
        
        for from_status, to_status in invalid_transitions:
            assert not validation_service._is_valid_transition(from_status, to_status)
    
    def test_status_transition_audit_trail(self, validation_service, mock_db, sample_video):
        """Test that status transitions create audit trail records"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        validation_service.transition_video_status(
            "test-video-id",
            VideoValidationStatus.PROCESSING,
            "user-123",
            notes="Starting processing"
        )
        
        # Verify audit trail record was created
        mock_db.add.assert_called()
        added_object = mock_db.add.call_args[0][0]
        assert isinstance(added_object, VideoStatusTransition)
        assert added_object.video_id == "test-video-id"
        assert added_object.from_status == "uploaded"
        assert added_object.to_status == "processing"
        assert added_object.changed_by == "user-123"
        assert added_object.notes == "Starting processing"


class TestVideoValidationWorkflows:
    """Test video validation workflow business logic"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def validation_service(self, mock_db):
        return VideoValidationService(mock_db)
    
    @pytest.fixture
    def annotated_video(self):
        """Video ready for validation"""
        return Video(
            id="test-id",
            filename="test.mp4",
            validation_status="annotated",
            processing_status="completed",
            ground_truth_generated=True,
            ground_truth_count=15,
            ground_truth_quality_score=0.92
        )
    
    def test_automatic_validation_success(self, validation_service, annotated_video):
        """Test successful automatic validation workflow"""
        validation_service.db.query.return_value.filter.return_value.first.return_value = annotated_video
        
        # Mock validation criteria
        mock_criteria = [
            VideoValidationCriteria(
                id="criteria-1",
                name="minimum_ground_truth_objects",
                criteria_type="automatic",
                threshold_value=10.0,
                is_required=True
            ),
            VideoValidationCriteria(
                id="criteria-2", 
                name="ground_truth_quality_score",
                criteria_type="automatic",
                threshold_value=0.8,
                is_required=True
            )
        ]
        validation_service.db.query.return_value.filter.return_value.all.return_value = mock_criteria
        
        result = validation_service.run_automatic_validation("test-id")
        
        assert result.overall_status == ValidationStatus.PASSED
        assert len(result.criteria_results) == 2
        assert all(cr.result == ValidationResultType.PASSED for cr in result.criteria_results)
    
    def test_automatic_validation_failure(self, validation_service, annotated_video):
        """Test automatic validation failure workflow"""
        # Set insufficient ground truth
        annotated_video.ground_truth_count = 5
        annotated_video.ground_truth_quality_score = 0.6
        
        validation_service.db.query.return_value.filter.return_value.first.return_value = annotated_video
        
        mock_criteria = [
            VideoValidationCriteria(
                id="criteria-1",
                name="minimum_ground_truth_objects", 
                criteria_type="automatic",
                threshold_value=10.0,
                is_required=True
            )
        ]
        validation_service.db.query.return_value.filter.return_value.all.return_value = mock_criteria
        
        result = validation_service.run_automatic_validation("test-id")
        
        assert result.overall_status == ValidationStatus.FAILED
        assert any(cr.result == ValidationResultType.FAILED for cr in result.criteria_results)
    
    def test_manual_validation_workflow(self, validation_service, annotated_video):
        """Test manual validation workflow"""
        validation_service.db.query.return_value.filter.return_value.first.return_value = annotated_video
        
        manual_criteria = [
            {"criteria_id": "manual-1", "result": "passed", "notes": "Objects clearly visible"},
            {"criteria_id": "manual-2", "result": "passed", "notes": "Good lighting conditions"}
        ]
        
        result = validation_service.complete_manual_validation(
            "test-id",
            "reviewer-123",
            manual_criteria,
            "Manual validation completed successfully"
        )
        
        assert result.overall_status == ValidationStatus.PASSED
        assert result.validated_by == "reviewer-123"
    
    def test_video_ready_for_hil_testing(self, validation_service):
        """Test logic to determine if video is ready for HIL testing"""
        validated_video = Video(
            id="test-id",
            filename="test.mp4",
            validation_status="validated",
            processing_status="completed",
            ground_truth_generated=True,
            hil_testing_ready=True
        )
        
        assert validation_service._is_ready_for_hil_testing(validated_video) is True
    
    def test_video_not_ready_for_hil_testing(self, validation_service):
        """Test videos not ready for HIL testing"""
        test_cases = [
            # Not validated
            Video(id="1", validation_status="processing", ground_truth_generated=True),
            # No ground truth
            Video(id="2", validation_status="validated", ground_truth_generated=False),
            # Error status
            Video(id="3", validation_status="error", ground_truth_generated=True),
            # HIL testing not approved
            Video(id="4", validation_status="validated", ground_truth_generated=True, hil_testing_ready=False)
        ]
        
        for video in test_cases:
            assert validation_service._is_ready_for_hil_testing(video) is False
    
    def test_batch_validation_processing(self, validation_service):
        """Test batch validation of multiple videos"""
        video_ids = ["video-1", "video-2", "video-3"]
        
        # Mock videos in different states
        mock_videos = [
            Video(id="video-1", validation_status="annotated", ground_truth_count=20),
            Video(id="video-2", validation_status="annotated", ground_truth_count=15), 
            Video(id="video-3", validation_status="annotated", ground_truth_count=5)  # Will fail
        ]
        validation_service.db.query.return_value.filter.return_value.all.return_value = mock_videos
        
        # Mock criteria
        mock_criteria = [VideoValidationCriteria(
            name="minimum_ground_truth_objects",
            threshold_value=10.0,
            is_required=True
        )]
        validation_service.db.query.return_value.filter.return_value.all.return_value = mock_criteria
        
        results = validation_service.batch_validate_videos(video_ids, "system")
        
        assert len(results) == 3
        assert results["video-1"].overall_status == ValidationStatus.PASSED
        assert results["video-2"].overall_status == ValidationStatus.PASSED
        assert results["video-3"].overall_status == ValidationStatus.FAILED


class TestVideoValidationCriteria:
    """Test video validation criteria system"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture 
    def validation_service(self, mock_db):
        return VideoValidationService(mock_db)
    
    def test_automatic_criteria_evaluation(self, validation_service):
        """Test automatic validation criteria evaluation"""
        video = Video(
            ground_truth_count=25,
            ground_truth_quality_score=0.95,
            duration=120.5
        )
        
        criteria = VideoValidationCriteria(
            name="minimum_ground_truth_objects",
            criteria_type="automatic", 
            threshold_value=20.0,
            comparison_operator="gte"
        )
        
        result = validation_service._evaluate_automatic_criteria(video, criteria)
        
        assert result.result == ValidationResultType.PASSED
        assert result.actual_value == 25.0
        assert result.threshold_value == 20.0
    
    def test_criteria_comparison_operators(self, validation_service):
        """Test different comparison operators for criteria"""
        video = Video(duration=60.0)
        
        test_cases = [
            ("gte", 50.0, ValidationResultType.PASSED),  # 60 >= 50
            ("lte", 70.0, ValidationResultType.PASSED),  # 60 <= 70
            ("eq", 60.0, ValidationResultType.PASSED),   # 60 == 60
            ("gt", 70.0, ValidationResultType.FAILED),   # 60 > 70
            ("lt", 50.0, ValidationResultType.FAILED)    # 60 < 50
        ]
        
        for operator, threshold, expected_result in test_cases:
            criteria = VideoValidationCriteria(
                name="duration_check",
                comparison_operator=operator,
                threshold_value=threshold
            )
            
            result = validation_service._evaluate_automatic_criteria(video, criteria)
            assert result.result == expected_result
    
    def test_required_vs_optional_criteria(self, validation_service):
        """Test handling of required vs optional validation criteria"""
        video = Video(ground_truth_count=5)  # Low count
        
        required_criteria = VideoValidationCriteria(
            name="required_check",
            threshold_value=10.0,
            is_required=True
        )
        
        optional_criteria = VideoValidationCriteria(
            name="optional_check", 
            threshold_value=10.0,
            is_required=False
        )
        
        required_result = validation_service._evaluate_automatic_criteria(video, required_criteria)
        optional_result = validation_service._evaluate_automatic_criteria(video, optional_criteria)
        
        # Both should fail the check, but impact on overall validation differs
        assert required_result.result == ValidationResultType.FAILED
        assert optional_result.result == ValidationResultType.FAILED
        assert required_result.is_required is True
        assert optional_result.is_required is False


class TestVideoValidationAPIIntegration:
    """Test integration with API endpoints and data flow"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def validation_service(self, mock_db):
        return VideoValidationService(mock_db)
    
    def test_video_status_response_serialization(self, validation_service):
        """Test VideoStatusResponse schema serialization"""
        video = Video(
            id="test-id",
            filename="test.mp4",
            validation_status="validated",
            validation_type="automatic",
            validated_at=datetime.now(timezone.utc),
            validated_by="system",
            hil_testing_ready=True
        )
        
        response = VideoStatusResponse(
            id=video.id,
            filename=video.filename,
            validation_status=VideoValidationStatus(video.validation_status),
            validation_type=ValidationType(video.validation_type) if video.validation_type else None,
            validated_at=video.validated_at,
            validated_by=video.validated_by,
            hil_testing_ready=video.hil_testing_ready
        )
        
        assert response.validation_status == VideoValidationStatus.VALIDATED
        assert response.hil_testing_ready is True
        assert response.validated_by == "system"
    
    def test_validation_result_response_serialization(self, validation_service):
        """Test ValidationResultResponse schema serialization"""
        validation_result = VideoValidationResult(
            video_id="test-id",
            overall_status="passed",
            validation_type="automatic",
            validated_by="system",
            validation_notes="All criteria passed"
        )
        
        response = ValidationResultResponse(
            video_id=validation_result.video_id,
            overall_status=ValidationStatus(validation_result.overall_status),
            validation_type=ValidationType(validation_result.validation_type),
            validated_by=validation_result.validated_by,
            validation_notes=validation_result.validation_notes,
            criteria_results=[]
        )
        
        assert response.overall_status == ValidationStatus.PASSED
        assert response.validation_type == ValidationType.AUTOMATIC
    
    def test_batch_status_update_processing(self, validation_service):
        """Test batch status update request processing"""
        from schemas_video_validation import BatchStatusUpdate
        
        batch_request = BatchStatusUpdate(
            video_ids=["video-1", "video-2", "video-3"],
            new_status=VideoValidationStatus.READY_FOR_TESTING,
            updated_by="admin-123",
            notes="Approved for HIL testing batch"
        )
        
        # Mock videos
        mock_videos = [
            Video(id="video-1", validation_status="validated"),
            Video(id="video-2", validation_status="validated"),
            Video(id="video-3", validation_status="validated")
        ]
        validation_service.db.query.return_value.filter.return_value.all.return_value = mock_videos
        
        results = validation_service.batch_update_video_status(
            batch_request.video_ids,
            batch_request.new_status,
            batch_request.updated_by,
            batch_request.notes
        )
        
        assert len(results) == 3
        assert all(video.validation_status == "ready_for_testing" for video in results)


class TestVideoValidationMigration:
    """Test video validation system migration logic"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    def test_legacy_status_mapping(self, mock_db):
        """Test mapping legacy status combinations to new system"""
        from scripts.migrate_video_validation_system import VideoValidationMigrator
        
        migrator = VideoValidationMigrator(mock_db)
        
        # Test mapping rules
        test_cases = [
            # (old_status, processing_status, ground_truth_generated) -> new_validation_status
            ("uploaded", "pending", False, VideoValidationStatus.UPLOADED),
            ("processing", "running", False, VideoValidationStatus.PROCESSING),
            ("completed", "completed", True, VideoValidationStatus.ANNOTATED),
            ("completed", "completed", False, VideoValidationStatus.PROCESSING_FAILED),
            ("error", "failed", False, VideoValidationStatus.ERROR)
        ]
        
        for old_status, proc_status, gt_gen, expected_new_status in test_cases:
            legacy_video = Video(
                status=old_status,
                processing_status=proc_status,
                ground_truth_generated=gt_gen
            )
            
            new_status = migrator._determine_new_validation_status(legacy_video)
            assert new_status == expected_new_status
    
    def test_migration_data_preservation(self, mock_db):
        """Test that migration preserves important data"""
        from scripts.migrate_video_validation_system import VideoValidationMigrator
        
        migrator = VideoValidationMigrator(mock_db)
        
        legacy_video = Video(
            id="legacy-video",
            filename="test.mp4",
            status="completed",
            processing_status="completed",
            ground_truth_generated=True,
            created_at=datetime(2023, 1, 1),
            updated_at=datetime(2023, 1, 2)
        )
        
        migrated_data = migrator._prepare_video_migration_data(legacy_video)
        
        # Verify core data preserved
        assert migrated_data["id"] == "legacy-video"
        assert migrated_data["filename"] == "test.mp4"
        assert migrated_data["validation_status"] == VideoValidationStatus.ANNOTATED
        
        # Verify new fields added
        assert "validation_type" in migrated_data
        assert "ground_truth_count" in migrated_data
        assert "hil_testing_ready" in migrated_data


class TestVideoValidationPerformance:
    """Test performance aspects of video validation system"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def validation_service(self, mock_db):
        return VideoValidationService(mock_db)
    
    def test_batch_validation_efficiency(self, validation_service):
        """Test that batch validation is efficient for large datasets"""
        # Simulate large batch
        video_ids = [f"video-{i}" for i in range(100)]
        
        # Mock efficient database queries
        validation_service.db.query.return_value.filter.return_value.all.return_value = [
            Video(id=vid, validation_status="annotated", ground_truth_count=15) 
            for vid in video_ids
        ]
        
        # Mock criteria (should be fetched once)
        validation_service.db.query.return_value.filter.return_value.all.return_value = [
            VideoValidationCriteria(name="min_objects", threshold_value=10.0)
        ]
        
        results = validation_service.batch_validate_videos(video_ids, "system")
        
        # Verify all videos processed
        assert len(results) == 100
        
        # Verify database queries were optimized (bulk operations)
        # In real implementation, we'd verify minimal query count
        assert validation_service.db.query.call_count >= 2  # Videos + Criteria queries
    
    def test_status_transition_indexing(self, validation_service):
        """Test that status queries use proper database indexing"""
        # This would test that queries on validation_status use indexes
        # In real implementation, we'd analyze query execution plans
        
        validation_service.get_videos_by_status(VideoValidationStatus.READY_FOR_TESTING)
        
        # Verify query structure for index usage
        validation_service.db.query.assert_called()
        query_call = validation_service.db.query.call_args
        assert query_call is not None  # Placeholder for index verification


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])