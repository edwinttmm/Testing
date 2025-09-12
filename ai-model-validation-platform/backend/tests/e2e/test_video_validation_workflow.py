"""
End-to-End Tests for Video Validation Workflow
==============================================

Tests complete video validation workflows from upload to HIL testing,
including database migrations, API interactions, and frontend integration.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import json
import time
from pathlib import Path

from main import app
from models import Base, Video, VideoValidationCriteria, VideoValidationResult, VideoStatusTransition
from schemas_video_validation import VideoValidationStatus, ValidationStatus, ValidationType
from config import get_db
from scripts.migrate_video_validation_system import VideoValidationMigrator


# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_e2e_video_validation.db"
test_engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def test_client():
    """Create test client with test database"""
    Base.metadata.create_all(bind=test_engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    
    # Cleanup
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def test_db():
    """Create test database session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestCompleteVideoValidationWorkflow:
    """Test complete video validation workflow from upload to HIL testing"""
    
    def test_video_upload_to_hil_testing_workflow(self, test_client, test_db):
        """Test complete workflow: upload → processing → annotated → validated → ready for HIL"""
        
        # Step 1: Upload video (simulated)
        video_data = {
            "id": "workflow-test-video",
            "filename": "test_workflow.mp4",
            "file_path": "/uploads/test_workflow.mp4",
            "project_id": "test-project"
        }
        
        upload_response = test_client.post("/api/videos/upload", json=video_data)
        assert upload_response.status_code in [200, 201]  # Video uploaded successfully
        
        # Verify initial status
        status_response = test_client.get("/api/videos/workflow-test-video/status")
        assert status_response.status_code == 200
        assert status_response.json()["validation_status"] == "uploaded"
        
        # Step 2: Start processing
        update_response = test_client.put(
            "/api/videos/workflow-test-video/status",
            json={"validation_status": "processing", "updated_by": "system"}
        )
        assert update_response.status_code == 200
        
        # Step 3: Processing completes with ground truth generation
        processing_complete_response = test_client.put(
            "/api/videos/workflow-test-video/status", 
            json={
                "validation_status": "annotated",
                "updated_by": "system",
                "ground_truth_generated": True,
                "ground_truth_count": 25,
                "ground_truth_quality_score": 0.92
            }
        )
        assert processing_complete_response.status_code == 200
        
        # Step 4: Run automatic validation
        validation_response = test_client.post("/api/videos/workflow-test-video/validate/automatic")
        assert validation_response.status_code == 200
        validation_data = validation_response.json()
        assert validation_data["overall_status"] == "passed"
        
        # Step 5: Approve for HIL testing
        hil_approval_response = test_client.post(
            "/api/videos/workflow-test-video/approve-hil-testing",
            json={
                "approved_by": "test-engineer-001",
                "notes": "Approved for HIL testing campaign"
            }
        )
        assert hil_approval_response.status_code == 200
        hil_data = hil_approval_response.json()
        assert hil_data["hil_testing_ready"] is True
        
        # Step 6: Verify final status
        final_status = test_client.get("/api/videos/workflow-test-video/status")
        final_data = final_status.json()
        assert final_data["validation_status"] == "ready_for_testing"
        assert final_data["hil_testing_ready"] is True
        assert final_data["hil_testing_approved_by"] == "test-engineer-001"
    
    def test_manual_validation_workflow(self, test_client):
        """Test manual validation workflow path"""
        
        # Create video with ground truth
        video_data = {
            "id": "manual-validation-video",
            "filename": "manual_test.mp4", 
            "file_path": "/uploads/manual_test.mp4",
            "project_id": "test-project"
        }
        test_client.post("/api/videos/upload", json=video_data)
        
        # Transition to annotated status
        test_client.put(
            "/api/videos/manual-validation-video/status",
            json={
                "validation_status": "annotated",
                "updated_by": "system",
                "ground_truth_generated": True,
                "ground_truth_count": 15
            }
        )
        
        # Perform manual validation
        manual_validation_response = test_client.post(
            "/api/videos/manual-validation-video/validate/manual",
            json={
                "validated_by": "human-reviewer-123",
                "criteria_results": [
                    {"criteria_id": "manual-quality", "result": "passed", "notes": "Good quality annotations"},
                    {"criteria_id": "manual-coverage", "result": "passed", "notes": "Adequate object coverage"}
                ],
                "validation_notes": "Manual validation passed after review"
            }
        )
        
        assert manual_validation_response.status_code == 200
        manual_data = manual_validation_response.json()
        assert manual_data["overall_status"] == "passed"
        assert manual_data["validation_type"] == "manual"
        assert manual_data["validated_by"] == "human-reviewer-123"
        
        # Verify video is now validated
        status_response = test_client.get("/api/videos/manual-validation-video/status")
        status_data = status_response.json()
        assert status_data["validation_status"] == "validated"
    
    def test_validation_failure_recovery_workflow(self, test_client):
        """Test workflow when validation fails and needs to be reprocessed"""
        
        # Create video with insufficient ground truth
        video_data = {
            "id": "failure-recovery-video",
            "filename": "failure_test.mp4",
            "file_path": "/uploads/failure_test.mp4", 
            "project_id": "test-project"
        }
        test_client.post("/api/videos/upload", json=video_data)
        
        # Transition to annotated with poor quality ground truth
        test_client.put(
            "/api/videos/failure-recovery-video/status",
            json={
                "validation_status": "annotated",
                "updated_by": "system",
                "ground_truth_generated": True,
                "ground_truth_count": 3,  # Too few objects
                "ground_truth_quality_score": 0.5  # Poor quality
            }
        )
        
        # Attempt automatic validation (should fail)
        validation_response = test_client.post("/api/videos/failure-recovery-video/validate/automatic")
        validation_data = validation_response.json()
        
        if validation_response.status_code == 200:
            assert validation_data["overall_status"] == "failed"
        else:
            # Validation might return 400 for insufficient data
            assert validation_response.status_code == 400
        
        # Check video transitioned to validation_failed status
        status_response = test_client.get("/api/videos/failure-recovery-video/status") 
        status_data = status_response.json()
        assert status_data["validation_status"] in ["validation_failed", "annotated"]
        
        # Recovery: Improve ground truth and retry
        test_client.put(
            "/api/videos/failure-recovery-video/status",
            json={
                "validation_status": "annotated",
                "updated_by": "system", 
                "ground_truth_count": 20,  # Improved
                "ground_truth_quality_score": 0.95  # Much better
            }
        )
        
        # Retry validation (should pass now)
        retry_validation_response = test_client.post("/api/videos/failure-recovery-video/validate/automatic")
        assert retry_validation_response.status_code == 200
        retry_data = retry_validation_response.json()
        assert retry_data["overall_status"] == "passed"


class TestBatchVideoValidationWorkflow:
    """Test batch processing workflows for video validation"""
    
    def test_batch_validation_large_dataset(self, test_client, test_db):
        """Test batch validation of multiple videos"""
        
        # Create multiple videos with ground truth
        video_ids = []
        for i in range(10):
            video_id = f"batch-video-{i}"
            video_ids.append(video_id)
            
            video_data = {
                "id": video_id,
                "filename": f"batch_test_{i}.mp4",
                "file_path": f"/uploads/batch_test_{i}.mp4",
                "project_id": "batch-test-project"
            }
            test_client.post("/api/videos/upload", json=video_data)
            
            # Set to annotated with good ground truth
            test_client.put(
                f"/api/videos/{video_id}/status",
                json={
                    "validation_status": "annotated",
                    "updated_by": "system",
                    "ground_truth_generated": True,
                    "ground_truth_count": 15 + i,  # Varying counts
                    "ground_truth_quality_score": 0.85 + (i * 0.01)  # Varying quality
                }
            )
        
        # Perform batch validation
        batch_validation_response = test_client.post(
            "/api/videos/batch-validate",
            json={
                "video_ids": video_ids,
                "validation_type": "automatic", 
                "validated_by": "batch-system"
            }
        )
        
        assert batch_validation_response.status_code == 200
        batch_data = batch_validation_response.json()
        assert len(batch_data["results"]) == 10
        
        # Verify all passed validation
        passed_count = sum(1 for result in batch_data["results"].values() 
                          if result["overall_status"] == "passed")
        assert passed_count == 10
        
        # Batch approve for HIL testing
        batch_approval_response = test_client.post(
            "/api/videos/batch-approve-hil-testing",
            json={
                "video_ids": video_ids,
                "approved_by": "batch-test-manager",
                "notes": "Batch approval for HIL testing"
            }
        )
        
        assert batch_approval_response.status_code == 200
        approval_data = batch_approval_response.json()
        assert len(approval_data["approved_videos"]) == 10
    
    def test_batch_status_transitions(self, test_client):
        """Test batch status transitions with validation"""
        
        # Create videos in different states
        video_configs = [
            ("batch-status-1", "uploaded"),
            ("batch-status-2", "processing"),
            ("batch-status-3", "annotated")
        ]
        
        for video_id, initial_status in video_configs:
            video_data = {
                "id": video_id,
                "filename": f"{video_id}.mp4",
                "file_path": f"/uploads/{video_id}.mp4",
                "project_id": "batch-status-project"
            }
            test_client.post("/api/videos/upload", json=video_data)
            
            if initial_status != "uploaded":
                test_client.put(
                    f"/api/videos/{video_id}/status",
                    json={"validation_status": initial_status, "updated_by": "setup"}
                )
        
        # Batch update to processing (should work for uploaded, fail for others)
        batch_update_response = test_client.post(
            "/api/videos/batch-update-status",
            json={
                "video_ids": ["batch-status-1", "batch-status-2", "batch-status-3"],
                "new_status": "processing",
                "updated_by": "batch-updater",
                "notes": "Batch processing start"
            }
        )
        
        # Should be partial success (multi-status response)
        assert batch_update_response.status_code in [200, 207]
        
        # Verify the results
        for video_id in ["batch-status-1", "batch-status-2", "batch-status-3"]:
            status_response = test_client.get(f"/api/videos/{video_id}/status")
            status_data = status_response.json()
            
            if video_id == "batch-status-1":
                # Should have transitioned successfully
                assert status_data["validation_status"] == "processing"
            # Others may or may not have changed depending on validation rules


class TestVideoValidationMigrationWorkflow:
    """Test migration from legacy video status system"""
    
    def test_legacy_video_migration(self, test_db):
        """Test migration of legacy videos to new validation system"""
        
        # Create legacy videos in database directly
        legacy_videos_data = [
            {
                "id": "legacy-1",
                "filename": "legacy1.mp4",
                "status": "completed",  # Legacy status
                "processing_status": "completed",
                "ground_truth_generated": True
            },
            {
                "id": "legacy-2", 
                "filename": "legacy2.mp4",
                "status": "uploaded",  # Legacy status
                "processing_status": "pending",
                "ground_truth_generated": False
            },
            {
                "id": "legacy-3",
                "filename": "legacy3.mp4",
                "status": "error",  # Legacy status
                "processing_status": "failed", 
                "ground_truth_generated": False
            }
        ]
        
        # Insert legacy videos
        for video_data in legacy_videos_data:
            legacy_video = Video(**video_data)
            test_db.add(legacy_video)
        test_db.commit()
        
        # Run migration
        migrator = VideoValidationMigrator(test_db)
        migration_results = migrator.migrate_videos()
        
        assert migration_results["migrated_count"] == 3
        assert migration_results["errors_count"] == 0
        
        # Verify migration results
        migrated_videos = test_db.query(Video).all()
        video_by_id = {v.id: v for v in migrated_videos}
        
        # legacy-1: completed + ground_truth -> annotated
        assert video_by_id["legacy-1"].validation_status == "annotated"
        
        # legacy-2: uploaded + no ground_truth -> uploaded
        assert video_by_id["legacy-2"].validation_status == "uploaded"
        
        # legacy-3: error -> error
        assert video_by_id["legacy-3"].validation_status == "error"
        
        # Verify migration audit trails were created
        transitions = test_db.query(VideoStatusTransition).all()
        assert len(transitions) == 3  # One for each migrated video
    
    def test_migration_rollback(self, test_db):
        """Test migration rollback functionality"""
        
        # Create a video and migrate it
        original_video = Video(
            id="rollback-test",
            filename="rollback.mp4",
            status="completed",
            processing_status="completed",
            ground_truth_generated=True
        )
        test_db.add(original_video)
        test_db.commit()
        
        # Store original state
        original_status = original_video.status
        
        # Migrate
        migrator = VideoValidationMigrator(test_db)
        migration_results = migrator.migrate_videos()
        assert migration_results["migrated_count"] == 1
        
        # Verify migration
        migrated_video = test_db.query(Video).filter(Video.id == "rollback-test").first()
        assert migrated_video.validation_status == "annotated"
        
        # Rollback 
        rollback_results = migrator.rollback_migration()
        assert rollback_results["rollback_count"] == 1
        
        # Verify rollback
        rolled_back_video = test_db.query(Video).filter(Video.id == "rollback-test").first()
        assert rolled_back_video.status == original_status
        assert not hasattr(rolled_back_video, 'validation_status') or rolled_back_video.validation_status is None


class TestVideoValidationPerformanceWorkflow:
    """Test performance aspects of video validation workflows"""
    
    def test_high_volume_validation_performance(self, test_client):
        """Test system performance with high volume validation requests"""
        
        start_time = time.time()
        
        # Create 50 videos
        video_ids = []
        for i in range(50):
            video_id = f"perf-test-{i}"
            video_ids.append(video_id)
            
            test_client.post("/api/videos/upload", json={
                "id": video_id,
                "filename": f"perf_test_{i}.mp4",
                "file_path": f"/uploads/perf_test_{i}.mp4",
                "project_id": "performance-test"
            })
        
        setup_time = time.time() - start_time
        
        # Batch update to annotated
        batch_annotated_time = time.time()
        test_client.post("/api/videos/batch-update-status", json={
            "video_ids": video_ids,
            "new_status": "annotated",
            "updated_by": "perf-test",
            "ground_truth_generated": True,
            "ground_truth_count": 20
        })
        batch_annotated_duration = time.time() - batch_annotated_time
        
        # Batch validate
        batch_validate_time = time.time()
        validation_response = test_client.post("/api/videos/batch-validate", json={
            "video_ids": video_ids,
            "validation_type": "automatic",
            "validated_by": "perf-test-system"
        })
        batch_validate_duration = time.time() - batch_validate_time
        
        total_time = time.time() - start_time
        
        # Performance assertions
        assert setup_time < 10.0  # Setup should complete in under 10 seconds
        assert batch_annotated_duration < 5.0  # Batch update should be fast
        assert batch_validate_duration < 15.0  # Validation should complete reasonably fast
        assert total_time < 30.0  # Total workflow under 30 seconds
        
        # Verify all validations completed successfully
        assert validation_response.status_code == 200
        validation_data = validation_response.json()
        assert len(validation_data["results"]) == 50
    
    def test_concurrent_validation_requests(self, test_client):
        """Test handling of concurrent validation requests"""
        import threading
        import queue
        
        # Create videos for concurrent testing
        video_ids = [f"concurrent-test-{i}" for i in range(10)]
        for video_id in video_ids:
            test_client.post("/api/videos/upload", json={
                "id": video_id,
                "filename": f"{video_id}.mp4",
                "file_path": f"/uploads/{video_id}.mp4",
                "project_id": "concurrent-test"
            })
            
            test_client.put(f"/api/videos/{video_id}/status", json={
                "validation_status": "annotated",
                "updated_by": "concurrent-setup",
                "ground_truth_generated": True,
                "ground_truth_count": 15
            })
        
        # Function to run validation in thread
        results_queue = queue.Queue()
        
        def validate_video(video_id):
            try:
                response = test_client.post(f"/api/videos/{video_id}/validate/automatic")
                results_queue.put(("success", video_id, response.status_code))
            except Exception as e:
                results_queue.put(("error", video_id, str(e)))
        
        # Start concurrent validation threads
        threads = []
        for video_id in video_ids:
            thread = threading.Thread(target=validate_video, args=(video_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Verify all validations completed successfully
        assert len(results) == 10
        success_count = sum(1 for result in results if result[0] == "success" and result[2] == 200)
        assert success_count == 10  # All should succeed


class TestVideoValidationAuditTrail:
    """Test audit trail and status transition tracking"""
    
    def test_complete_audit_trail_tracking(self, test_client, test_db):
        """Test that all status transitions are properly tracked"""
        
        video_id = "audit-trail-test"
        
        # Create video
        test_client.post("/api/videos/upload", json={
            "id": video_id,
            "filename": "audit_test.mp4",
            "file_path": "/uploads/audit_test.mp4", 
            "project_id": "audit-test"
        })
        
        # Perform series of status transitions
        transitions = [
            ("processing", "user-1", "Started processing"),
            ("annotated", "system", "Ground truth generation completed"),
            ("validating", "validator-1", "Starting manual validation"),
            ("validated", "validator-1", "Manual validation passed"), 
            ("ready_for_testing", "approver-1", "Approved for HIL testing")
        ]
        
        for status, user, notes in transitions:
            test_client.put(f"/api/videos/{video_id}/status", json={
                "validation_status": status,
                "updated_by": user,
                "notes": notes
            })
        
        # Verify audit trail
        audit_trail = test_db.query(VideoStatusTransition).filter(
            VideoStatusTransition.video_id == video_id
        ).order_by(VideoStatusTransition.changed_at).all()
        
        assert len(audit_trail) == len(transitions)
        
        for i, (expected_to_status, expected_user, expected_notes) in enumerate(transitions):
            trail_entry = audit_trail[i]
            assert trail_entry.to_status == expected_to_status
            assert trail_entry.changed_by == expected_user
            assert trail_entry.notes == expected_notes
            assert trail_entry.changed_at is not None
        
        # Verify status transition chain
        expected_from_statuses = ["uploaded"] + [t[0] for t in transitions[:-1]]
        for i, trail_entry in enumerate(audit_trail):
            assert trail_entry.from_status == expected_from_statuses[i]
    
    def test_validation_history_retrieval(self, test_client):
        """Test retrieval of validation history"""
        
        video_id = "validation-history-test"
        
        # Create and setup video
        test_client.post("/api/videos/upload", json={
            "id": video_id,
            "filename": "history_test.mp4",
            "file_path": "/uploads/history_test.mp4",
            "project_id": "history-test"
        })
        
        test_client.put(f"/api/videos/{video_id}/status", json={
            "validation_status": "annotated",
            "updated_by": "system",
            "ground_truth_generated": True,
            "ground_truth_count": 20
        })
        
        # Perform multiple validations
        test_client.post(f"/api/videos/{video_id}/validate/automatic")
        
        test_client.post(f"/api/videos/{video_id}/validate/manual", json={
            "validated_by": "human-reviewer",
            "criteria_results": [
                {"criteria_id": "manual-1", "result": "passed", "notes": "Good quality"}
            ],
            "validation_notes": "Manual validation for verification"
        })
        
        # Retrieve validation history
        history_response = test_client.get(f"/api/videos/{video_id}/validation-history")
        
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data["history"]) >= 2
        
        # Verify history contains both automatic and manual validations
        validation_types = [entry["validation_type"] for entry in history_data["history"]]
        assert "automatic" in validation_types
        assert "manual" in validation_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--maxfail=5"])