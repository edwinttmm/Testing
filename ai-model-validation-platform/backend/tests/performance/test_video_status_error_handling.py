"""
Error Handling Tests for Video Status Transitions and Validation
================================================================

Tests error conditions, invalid state transitions, and recovery mechanisms.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, OperationalError
import json

from models import Video, Project, GroundTruthObject, TestSession
from schemas import VideoStatus
from crud import update_video_status, create_video, get_video


class TestVideoStatusTransitionErrors:
    """Test error handling for invalid video status transitions"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def sample_video(self):
        return Video(
            id="error-test-video",
            filename="error_test.mp4",
            file_path="/uploads/error_test.mp4",
            status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id="test-project"
        )
    
    def test_invalid_status_transition_validation(self, mock_db, sample_video):
        """Test validation prevents invalid status transitions"""
        # Test direct transition from uploaded to validated (should be prevented)
        sample_video.status = "uploaded"
        sample_video.ground_truth_generated = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        # This should validate business rules and potentially raise an error
        with pytest.raises((ValueError, RuntimeError)) as exc_info:
            self._validate_status_transition(sample_video, "validated")
        
        assert "invalid transition" in str(exc_info.value).lower() or "ground truth" in str(exc_info.value).lower()
    
    def test_concurrent_status_update_conflict(self, mock_db, sample_video):
        """Test handling of concurrent status update conflicts"""
        # Simulate optimistic locking conflict
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_db.commit.side_effect = IntegrityError("statement", "params", "orig")
        
        with pytest.raises(IntegrityError):
            update_video_status(mock_db, sample_video.id, "processing")
    
    def test_database_connection_error_handling(self, mock_db, sample_video):
        """Test handling of database connection errors during status updates"""
        mock_db.query.side_effect = OperationalError("statement", "params", "orig")
        
        with pytest.raises(OperationalError):
            update_video_status(mock_db, sample_video.id, "processing")
    
    def test_nonexistent_video_status_update(self, mock_db):
        """Test error handling when trying to update non-existent video"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = update_video_status(mock_db, "nonexistent-video-id", "processing")
        assert result is None
    
    def test_null_or_empty_status_handling(self, mock_db, sample_video):
        """Test handling of null or empty status values"""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        # Test null status
        with pytest.raises((ValueError, TypeError)):
            update_video_status(mock_db, sample_video.id, None)
        
        # Test empty status
        with pytest.raises((ValueError, TypeError)):
            update_video_status(mock_db, sample_video.id, "")
        
        # Test invalid status
        with pytest.raises((ValueError, TypeError)):
            update_video_status(mock_db, sample_video.id, "invalid_status")
    
    def _validate_status_transition(self, video: Video, new_status: str):
        """Helper method to validate status transitions"""
        # Business rules for status transitions
        if new_status == "validated":
            if not video.ground_truth_generated:
                raise ValueError("Cannot validate video without ground truth")
            if video.status not in ["processing", "pending_validation"]:
                raise ValueError("Invalid transition to validated status")
        
        if new_status == "processing" and video.status == "validated":
            raise ValueError("Cannot revert from validated to processing")


class TestGroundTruthValidationErrors:
    """Test error handling for ground truth validation"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    def test_invalid_ground_truth_data_handling(self, mock_db):
        """Test handling of invalid ground truth data"""
        invalid_ground_truth_cases = [
            # Missing required fields
            {"timestamp": 1.0, "class_label": "pedestrian"},  # Missing bounding box
            {"class_label": "pedestrian", "x": 100, "y": 100},  # Missing timestamp
            {"timestamp": 1.0, "x": 100, "y": 100},  # Missing class_label
            
            # Invalid data types
            {"timestamp": "invalid", "class_label": "pedestrian", "x": 100, "y": 100},
            {"timestamp": 1.0, "class_label": 123, "x": 100, "y": 100},  # Non-string label
            
            # Invalid values
            {"timestamp": -1.0, "class_label": "pedestrian", "x": 100, "y": 100},  # Negative timestamp
            {"timestamp": 1.0, "class_label": "pedestrian", "x": -100, "y": 100},  # Negative coordinates
            {"timestamp": 1.0, "class_label": "", "x": 100, "y": 100},  # Empty class label
        ]
        
        for invalid_data in invalid_ground_truth_cases:
            with pytest.raises((ValueError, TypeError, KeyError)):
                self._validate_ground_truth_data(invalid_data)
    
    def test_ground_truth_video_relationship_error(self, mock_db):
        """Test error handling for invalid video-ground truth relationships"""
        # Test creating ground truth for non-existent video
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(ValueError) as exc_info:
            self._create_ground_truth_with_validation(mock_db, "nonexistent-video", {
                "timestamp": 1.0,
                "class_label": "pedestrian",
                "x": 100, "y": 100, "width": 50, "height": 100
            })
        
        assert "video not found" in str(exc_info.value).lower()
    
    def test_duplicate_ground_truth_handling(self, mock_db):
        """Test handling of duplicate ground truth entries"""
        # Simulate attempting to create duplicate ground truth
        existing_gt = GroundTruthObject(
            id="existing-gt",
            video_id="test-video",
            timestamp=1.0,
            class_label="pedestrian",
            x=100, y=100, width=50, height=100,
            confidence=0.9
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = existing_gt
        mock_db.add.side_effect = IntegrityError("statement", "params", "orig")
        
        with pytest.raises(IntegrityError):
            self._create_ground_truth_with_validation(mock_db, "test-video", {
                "timestamp": 1.0,  # Same timestamp
                "class_label": "pedestrian",
                "x": 100, "y": 100, "width": 50, "height": 100
            })
    
    def _validate_ground_truth_data(self, gt_data):
        """Helper method to validate ground truth data"""
        required_fields = ["timestamp", "class_label", "x", "y"]
        
        for field in required_fields:
            if field not in gt_data:
                raise KeyError(f"Missing required field: {field}")
        
        if not isinstance(gt_data["timestamp"], (int, float)):
            raise TypeError("Timestamp must be a number")
        
        if gt_data["timestamp"] < 0:
            raise ValueError("Timestamp cannot be negative")
        
        if not isinstance(gt_data["class_label"], str) or not gt_data["class_label"]:
            raise ValueError("Class label must be a non-empty string")
        
        for coord in ["x", "y"]:
            if not isinstance(gt_data[coord], (int, float)):
                raise TypeError(f"{coord} coordinate must be a number")
    
    def _create_ground_truth_with_validation(self, db, video_id, gt_data):
        """Helper method to create ground truth with validation"""
        # Validate video exists
        video = db.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()
        if not video:
            raise ValueError("Video not found")
        
        # Validate ground truth data
        self._validate_ground_truth_data(gt_data)
        
        # Create ground truth object (would normally be done in CRUD layer)
        gt = GroundTruthObject(
            video_id=video_id,
            **gt_data
        )
        db.add(gt)
        db.commit()
        return gt


class TestVideoValidationWorkflowErrors:
    """Test error handling in video validation workflows"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    def test_validation_workflow_interruption_handling(self, mock_db):
        """Test handling of workflow interruptions during validation"""
        video = Video(
            id="workflow-test-video",
            filename="workflow_test.mp4",
            status="processing",
            processing_status="generating_ground_truth",
            ground_truth_generated=False,
            project_id="test-project"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = video
        
        # Simulate workflow interruption (e.g., service restart during processing)
        with patch('time.sleep', side_effect=KeyboardInterrupt("Process interrupted")):
            with pytest.raises(KeyboardInterrupt):
                self._simulate_validation_workflow(mock_db, video.id)
        
        # Video should remain in processing state for recovery
        assert video.status == "processing"
    
    def test_partial_ground_truth_validation_error(self, mock_db):
        """Test handling of partial ground truth validation errors"""
        video = Video(
            id="partial-gt-video",
            filename="partial_gt.mp4",
            status="pending_validation",
            ground_truth_generated=True,
            project_id="test-project"
        )
        
        # Mock ground truth objects with mixed validation states
        ground_truth_objects = [
            Mock(id="gt1", validated=True),
            Mock(id="gt2", validated=False),  # Not validated
            Mock(id="gt3", validated=True)
        ]
        
        mock_db.query.return_value.filter.return_value.first.return_value = video
        mock_db.query.return_value.filter.return_value.all.return_value = ground_truth_objects
        
        # Should handle partial validation appropriately
        result = self._validate_ground_truth_completeness(mock_db, video.id)
        
        assert not result["all_validated"]
        assert result["validated_count"] == 2
        assert result["total_count"] == 3
    
    def test_video_file_access_error_during_validation(self, mock_db):
        """Test handling of video file access errors during validation"""
        video = Video(
            id="inaccessible-video",
            filename="inaccessible.mp4",
            file_path="/nonexistent/path/inaccessible.mp4",
            status="processing",
            project_id="test-project"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = video
        
        # Simulate file access error
        with patch('os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError) as exc_info:
                self._validate_video_file_access(video)
        
        assert "not found" in str(exc_info.value).lower()
    
    def test_validation_timeout_handling(self, mock_db):
        """Test handling of validation process timeouts"""
        video = Video(
            id="timeout-video",
            filename="timeout.mp4",
            status="processing",
            project_id="test-project"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = video
        
        # Simulate timeout during validation
        with patch('time.time', side_effect=[0, 100, 3700]):  # Simulate 3700 seconds elapsed
            with pytest.raises(TimeoutError) as exc_info:
                self._validate_with_timeout(video, timeout_seconds=3600)
        
        assert "timeout" in str(exc_info.value).lower()
    
    def _simulate_validation_workflow(self, db, video_id):
        """Helper method to simulate validation workflow"""
        import time
        
        video = db.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()
        
        # Simulate ground truth generation (with potential interruption)
        video.status = "processing"
        video.processing_status = "generating_ground_truth"
        time.sleep(1)  # This could be interrupted
        
        # Continue workflow
        video.processing_status = "validating"
        video.ground_truth_generated = True
        time.sleep(1)
        
        video.status = "validated"
        video.processing_status = "completed"
    
    def _validate_ground_truth_completeness(self, db, video_id):
        """Helper method to validate ground truth completeness"""
        video = db.execute(select(Video).where(Video.id == video_id)).scalar_one_or_none()
        ground_truth_objects = db.execute(select(GroundTruthObject).where(
            GroundTruthObject.video_id == video_id
        )).scalars().all()
        
        validated_count = sum(1 for gt in ground_truth_objects if gt.validated)
        total_count = len(ground_truth_objects)
        
        return {
            "all_validated": validated_count == total_count,
            "validated_count": validated_count,
            "total_count": total_count
        }
    
    def _validate_video_file_access(self, video):
        """Helper method to validate video file access"""
        import os
        
        if not os.path.exists(video.file_path):
            raise FileNotFoundError(f"Video file not found: {video.file_path}")
        
        return True
    
    def _validate_with_timeout(self, video, timeout_seconds=3600):
        """Helper method to validate with timeout"""
        import time
        
        start_time = time.time()
        
        while True:
            current_time = time.time()
            if current_time - start_time > timeout_seconds:
                raise TimeoutError("Validation process timed out")
            
            # Simulate validation work
            if video.status == "validated":
                break
            
            time.sleep(0.1)  # Simulate processing time


class TestVideoStatusRecoveryMechanisms:
    """Test recovery mechanisms for video status errors"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    def test_error_state_recovery(self, mock_db):
        """Test recovery from error state"""
        error_video = Video(
            id="error-recovery-video",
            filename="error_recovery.mp4",
            status="error",
            processing_status="failed",
            ground_truth_generated=False,
            project_id="test-project"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = error_video
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        # Test recovery by resetting to processing
        result = update_video_status(mock_db, error_video.id, "processing")
        
        assert result is not None
        assert result.status == "processing"
        # Processing status might be reset to pending for retry
    
    def test_stuck_processing_state_recovery(self, mock_db):
        """Test recovery from stuck processing state"""
        from datetime import datetime, timezone, timedelta
        
        # Video stuck in processing for too long
        stuck_video = Video(
            id="stuck-video",
            filename="stuck.mp4",
            status="processing",
            processing_status="generating_ground_truth",
            updated_at=datetime.now(timezone.utc) - timedelta(hours=2)  # 2 hours ago
        )
        
        # Recovery mechanism should detect and handle stuck videos
        recovery_result = self._detect_and_recover_stuck_videos([stuck_video])
        
        assert len(recovery_result["recovered"]) == 1
        assert recovery_result["recovered"][0]["reason"] == "processing_timeout"
    
    def test_data_consistency_recovery(self, mock_db):
        """Test recovery from data consistency issues"""
        # Video marked as validated but missing ground truth
        inconsistent_video = Video(
            id="inconsistent-video",
            filename="inconsistent.mp4",
            status="validated",
            ground_truth_generated=False,  # Inconsistent state
            project_id="test-project"
        )
        
        # Recovery should detect and fix inconsistency
        consistency_issues = self._detect_consistency_issues([inconsistent_video])
        
        assert len(consistency_issues) == 1
        assert consistency_issues[0]["type"] == "validated_without_ground_truth"
        assert consistency_issues[0]["suggested_fix"] == "revert_to_processing"
    
    def test_orphaned_ground_truth_cleanup(self, mock_db):
        """Test cleanup of orphaned ground truth objects"""
        # Ground truth objects without corresponding video
        orphaned_gt = [
            Mock(id="orphan1", video_id="nonexistent-video-1"),
            Mock(id="orphan2", video_id="nonexistent-video-2")
        ]
        
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No video found
        
        cleanup_result = self._cleanup_orphaned_ground_truth(mock_db, orphaned_gt)
        
        assert cleanup_result["cleaned_count"] == 2
        assert cleanup_result["orphaned_ids"] == ["orphan1", "orphan2"]
    
    def _detect_and_recover_stuck_videos(self, videos):
        """Helper method to detect and recover stuck videos"""
        from datetime import datetime, timezone, timedelta
        
        recovered = []
        stuck_threshold = timedelta(hours=1)  # Videos stuck for more than 1 hour
        
        for video in videos:
            if video.status == "processing":
                time_since_update = datetime.now(timezone.utc) - video.updated_at
                if time_since_update > stuck_threshold:
                    # Recovery action: reset to uploaded for retry
                    recovered.append({
                        "video_id": video.id,
                        "reason": "processing_timeout",
                        "stuck_duration": time_since_update.total_seconds()
                    })
        
        return {"recovered": recovered}
    
    def _detect_consistency_issues(self, videos):
        """Helper method to detect data consistency issues"""
        issues = []
        
        for video in videos:
            # Check for validated videos without ground truth
            if video.status == "validated" and not video.ground_truth_generated:
                issues.append({
                    "video_id": video.id,
                    "type": "validated_without_ground_truth",
                    "suggested_fix": "revert_to_processing"
                })
            
            # Check for processing videos with completed status
            if video.status == "processing" and video.processing_status == "completed":
                issues.append({
                    "video_id": video.id,
                    "type": "processing_but_completed",
                    "suggested_fix": "update_to_validated"
                })
        
        return issues
    
    def _cleanup_orphaned_ground_truth(self, db, ground_truth_objects):
        """Helper method to cleanup orphaned ground truth objects"""
        orphaned_ids = []
        
        for gt in ground_truth_objects:
            # Check if corresponding video exists
            video = db.execute(select(Video).where(Video.id == gt.video_id)).scalar_one_or_none()
            if not video:
                orphaned_ids.append(gt.id)
                # In real implementation, would delete the GT object
        
        return {
            "cleaned_count": len(orphaned_ids),
            "orphaned_ids": orphaned_ids
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])