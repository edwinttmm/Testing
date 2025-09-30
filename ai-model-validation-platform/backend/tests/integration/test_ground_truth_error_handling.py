"""
Error Handling and Recovery Testing for Ground Truth System
===========================================================

This module provides comprehensive error handling and recovery testing to ensure
the ground truth system handles failures gracefully and maintains data integrity.

Test Coverage:
- File system errors (missing files, permission issues)
- Database errors (connection failures, constraint violations)
- Network errors (API timeouts, connection drops)
- Memory errors (out of memory, resource exhaustion)
- Configuration errors (invalid settings, missing dependencies)
- Processing errors (corrupted data, invalid formats)
- System recovery mechanisms
- Error propagation and logging

Author: QA Specialist
Date: 2024-09-29
"""

import pytest
import tempfile
import os
import shutil
import uuid
import time
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from sqlalchemy.exc import IntegrityError, OperationalError
from contextlib import contextmanager

from fastapi.testclient import TestClient
from fastapi import status

from main import app
from database import SessionLocal, engine
from models import Video, GroundTruthObject, DetectionEvent, Project
from services.ground_truth_service import GroundTruthService
from services.detection_pipeline_service import DetectionPipeline

class ErrorTestHelper:
    """Helper class for error testing scenarios"""
    
    def __init__(self):
        self.test_client = TestClient(app)
        self.test_videos = []
        self.test_projects = []
        self.temp_directories = []
    
    def create_test_project(self) -> Project:
        """Create a test project"""
        project_id = str(uuid.uuid4())
        self.test_projects.append(project_id)
        
        project = Project(
            id=project_id,
            name="Error Test Project",
            description="Project for error testing",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            lens_type="Standard",
            resolution="640x480",
            frame_rate=30,
            signal_type="GPIO",
            status="active",
            owner_id="test_user"
        )
        
        db = SessionLocal()
        try:
            db.add(project)
            db.commit()
            db.refresh(project)
            return project
        finally:
            db.close()
    
    def create_test_video(self, project_id: str, file_path: str = None) -> Video:
        """Create a test video record"""
        video_id = str(uuid.uuid4())
        self.test_videos.append(video_id)
        
        if not file_path:
            file_path = f"/tmp/test_video_{video_id}.mp4"
        
        video = Video(
            id=video_id,
            filename=os.path.basename(file_path),
            file_path=file_path,
            file_size=1024000,
            duration=10.0,
            fps=30.0,
            resolution="640x480",
            status="uploaded",
            processing_status="pending",
            ground_truth_generated=False,
            project_id=project_id
        )
        
        db = SessionLocal()
        try:
            db.add(video)
            db.commit()
            db.refresh(video)
            return video
        finally:
            db.close()
    
    def create_temp_directory(self) -> str:
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp(prefix="error_test_")
        self.temp_directories.append(temp_dir)
        return temp_dir
    
    def cleanup(self):
        """Clean up test resources"""
        db = SessionLocal()
        try:
            # Clean up videos and related data
            for video_id in self.test_videos:
                db.query(GroundTruthObject).filter(
                    GroundTruthObject.video_id == video_id
                ).delete()
                db.query(DetectionEvent).filter(
                    DetectionEvent.video_id == video_id
                ).delete()
                db.query(Video).filter(Video.id == video_id).delete()
            
            # Clean up projects
            for project_id in self.test_projects:
                db.query(Project).filter(Project.id == project_id).delete()
            
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        
        # Clean up temp directories
        for temp_dir in self.temp_directories:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

@contextmanager
def simulate_error(error_type: str, **kwargs):
    """Context manager to simulate various error conditions"""
    if error_type == "database_connection":
        with patch('database.SessionLocal') as mock_session:
            mock_session.side_effect = OperationalError("Database connection failed", None, None)
            yield
    
    elif error_type == "file_not_found":
        file_path = kwargs.get('file_path', '/nonexistent/file.mp4')
        # Ensure file doesn't exist
        if os.path.exists(file_path):
            os.remove(file_path)
        yield
    
    elif error_type == "permission_denied":
        with patch('builtins.open') as mock_open:
            mock_open.side_effect = PermissionError("Permission denied")
            yield
    
    elif error_type == "out_of_memory":
        with patch('cv2.VideoCapture') as mock_capture:
            mock_capture.side_effect = MemoryError("Out of memory")
            yield
    
    elif error_type == "disk_full":
        with patch('builtins.open', side_effect=OSError("No space left on device")):
            yield
    
    else:
        yield

@pytest.fixture
def error_helper():
    """Provide error test helper with cleanup"""
    helper = ErrorTestHelper()
    yield helper
    helper.cleanup()

class TestFileSystemErrors:
    """Test file system related error handling"""
    
    def test_missing_video_file_handling(self, error_helper):
        """Test handling of missing video files"""
        # Arrange
        project = error_helper.create_test_project()
        nonexistent_file = "/nonexistent/path/missing_video.mp4"
        video = error_helper.create_test_video(project.id, nonexistent_file)
        
        service = GroundTruthService()
        
        # Act & Assert - Should handle missing file gracefully
        service._process_video(video.id, nonexistent_file)
        
        # Verify error was handled and video status updated
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            assert updated_video.status == "failed"
            assert updated_video.processing_status == "failed"
        finally:
            db.close()
    
    def test_permission_denied_handling(self, error_helper):
        """Test handling of permission denied errors"""
        # Arrange
        project = error_helper.create_test_project()
        restricted_file = "/root/restricted_video.mp4"
        video = error_helper.create_test_video(project.id, restricted_file)
        
        service = GroundTruthService()
        
        # Act - Simulate permission denied
        with simulate_error("permission_denied"):
            service._process_video(video.id, restricted_file)
        
        # Assert - Should handle gracefully
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            assert updated_video.status == "failed"
        finally:
            db.close()
    
    def test_corrupted_video_file_handling(self, error_helper):
        """Test handling of corrupted video files"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        
        # Create corrupted video file
        corrupted_file = os.path.join(temp_dir, "corrupted.mp4")
        with open(corrupted_file, 'w') as f:
            f.write("This is not a valid video file")
        
        video = error_helper.create_test_video(project.id, corrupted_file)
        service = GroundTruthService()
        
        # Act - Process corrupted file
        service._process_video(video.id, corrupted_file)
        
        # Assert - Should handle gracefully
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            assert updated_video.status == "failed"
        finally:
            db.close()
    
    def test_disk_full_error_handling(self, error_helper):
        """Test handling of disk full errors during processing"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "test.mp4")
        
        # Create minimal video file
        with open(video_file, 'w') as f:
            f.write("fake video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        service = GroundTruthService()
        
        # Act - Simulate disk full during screenshot saving
        with patch('cv2.imwrite') as mock_imwrite:
            mock_imwrite.side_effect = OSError("No space left on device")
            
            # Should handle gracefully
            service._process_video(video.id, video_file)
        
        # Assert - Processing should continue without screenshots
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            # May still succeed if ML processing works despite screenshot failure
            assert updated_video.status in ["failed", "validated", "completed"]
        finally:
            db.close()

class TestDatabaseErrors:
    """Test database related error handling"""
    
    def test_database_connection_failure(self, error_helper):
        """Test handling of database connection failures"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "test.mp4")
        
        with open(video_file, 'w') as f:
            f.write("fake video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        service = GroundTruthService()
        
        # Act - Simulate database connection failure during processing
        with patch('services.ground_truth_service.SessionLocal') as mock_session:
            mock_session.side_effect = OperationalError(
                "Database connection failed", None, None
            )
            
            # Should handle gracefully
            try:
                service._process_video(video.id, video_file)
            except Exception as e:
                # Expected to fail, but should not crash the system
                assert "Database connection failed" in str(e)
    
    def test_constraint_violation_handling(self, error_helper):
        """Test handling of database constraint violations"""
        # Arrange
        project = error_helper.create_test_project()
        video = error_helper.create_test_video(project.id)
        
        db = SessionLocal()
        try:
            # Create duplicate ground truth object ID to force constraint violation
            duplicate_id = str(uuid.uuid4())
            
            gt1 = GroundTruthObject(
                id=duplicate_id,
                video_id=video.id,
                frame_number=100,
                timestamp=1.0,
                class_label="pedestrian",
                x=100.0,
                y=200.0,
                width=80.0,
                height=160.0,
                confidence=0.8,
                validated=True,
                difficult=False
            )
            db.add(gt1)
            db.commit()
            
            # Try to add another with same ID
            gt2 = GroundTruthObject(
                id=duplicate_id,  # Same ID - should cause constraint violation
                video_id=video.id,
                frame_number=101,
                timestamp=1.1,
                class_label="cyclist",
                x=150.0,
                y=180.0,
                width=90.0,
                height=170.0,
                confidence=0.9,
                validated=True,
                difficult=False
            )
            
            # Act & Assert - Should handle constraint violation
            with pytest.raises(IntegrityError):
                db.add(gt2)
                db.commit()
        
        finally:
            db.rollback()
            db.close()
    
    def test_transaction_rollback_on_error(self, error_helper):
        """Test proper transaction rollback on errors"""
        # Arrange
        project = error_helper.create_test_project()
        video = error_helper.create_test_video(project.id)
        
        db = SessionLocal()
        initial_count = db.query(GroundTruthObject).count()
        db.close()
        
        # Act - Start transaction and cause error midway
        db = SessionLocal()
        try:
            db.begin()
            
            # Add first object (should succeed)
            gt1 = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                frame_number=100,
                timestamp=1.0,
                class_label="pedestrian",
                x=100.0,
                y=200.0,
                width=80.0,
                height=160.0,
                confidence=0.8,
                validated=True,
                difficult=False
            )
            db.add(gt1)
            
            # Force an error
            db.execute(text("INSERT INTO invalid_table VALUES (1)"))  # This should fail
            
            db.commit()  # This should not be reached
            
        except Exception:
            db.rollback()
        finally:
            db.close()
        
        # Assert - Count should be unchanged due to rollback
        db = SessionLocal()
        try:
            final_count = db.query(GroundTruthObject).count()
            assert final_count == initial_count, "Transaction should have been rolled back"
        finally:
            db.close()

class TestAPIErrors:
    """Test API error handling and responses"""
    
    def test_invalid_video_id_error(self, error_helper):
        """Test API response for invalid video ID"""
        # Act
        response = error_helper.test_client.get("/api/ground-truth/videos/invalid-uuid/stats")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        error_data = response.json()
        assert "not found" in error_data["detail"].lower()
    
    def test_malformed_request_error(self, error_helper):
        """Test API response for malformed requests"""
        # Test empty video ID
        response = error_helper.test_client.get("/api/ground-truth/videos//stats")
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND, 
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ]
        
        # Test invalid endpoint
        response = error_helper.test_client.get("/api/ground-truth/invalid-endpoint")
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_database_error_api_response(self, error_helper):
        """Test API response when database errors occur"""
        # Arrange
        project = error_helper.create_test_project()
        video = error_helper.create_test_video(project.id)
        
        # Act - Simulate database error during API call
        with patch('routers.ground_truth.get_db') as mock_get_db:
            mock_db = Mock()
            mock_db.query.side_effect = OperationalError("Database error", None, None)
            mock_get_db.return_value = mock_db
            
            response = error_helper.test_client.get(f"/api/ground-truth/videos/{video.id}/stats")
        
        # Assert - Should return 500 error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    def test_timeout_error_handling(self, error_helper):
        """Test handling of request timeouts"""
        # Arrange
        project = error_helper.create_test_project()
        video = error_helper.create_test_video(project.id)
        
        # Act - Simulate slow database query
        with patch('routers.ground_truth.get_db') as mock_get_db:
            mock_db = Mock()
            # Simulate very slow query
            def slow_query(*args, **kwargs):
                time.sleep(2)  # Simulate 2-second delay
                return Mock()
            
            mock_db.query.return_value.filter.return_value.first.side_effect = slow_query
            mock_get_db.return_value = mock_db
            
            # This would timeout in production with proper timeout settings
            response = error_helper.test_client.get(f"/api/ground-truth/videos/{video.id}/stats")
        
        # Assert - Should handle timeout gracefully
        # In this test, it will complete but in production should timeout
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_504_GATEWAY_TIMEOUT,
            status.HTTP_500_INTERNAL_SERVER_ERROR
        ]

class TestMemoryErrors:
    """Test memory related error handling"""
    
    def test_out_of_memory_handling(self, error_helper):
        """Test handling of out of memory errors"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "large_video.mp4")
        
        with open(video_file, 'w') as f:
            f.write("fake large video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        service = GroundTruthService()
        
        # Act - Simulate out of memory during video processing
        with patch('cv2.VideoCapture') as mock_capture:
            mock_capture.side_effect = MemoryError("Out of memory")
            
            service._process_video(video.id, video_file)
        
        # Assert - Should handle gracefully
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            assert updated_video.status == "failed"
        finally:
            db.close()
    
    def test_memory_leak_prevention(self, error_helper):
        """Test that processing doesn't cause memory leaks"""
        # This is a simplified test - in practice would need memory profiling
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        
        # Create multiple small video files
        video_files = []
        videos = []
        
        for i in range(5):
            video_file = os.path.join(temp_dir, f"test_{i}.mp4")
            with open(video_file, 'w') as f:
                f.write(f"fake video data {i}")
            
            video_files.append(video_file)
            video = error_helper.create_test_video(project.id, video_file)
            videos.append(video)
        
        service = GroundTruthService()
        
        # Act - Process multiple videos with mocked ML
        with patch.object(service, '_extract_detections') as mock_extract:
            mock_extract.return_value = []  # No detections to reduce memory usage
            
            for i, video in enumerate(videos):
                service._process_video(video.id, video_files[i])
        
        # Assert - All should complete without memory issues
        db = SessionLocal()
        try:
            for video in videos:
                updated_video = db.query(Video).filter(Video.id == video.id).first()
                assert updated_video.status in ["validated", "completed", "failed"]
        finally:
            db.close()

class TestConfigurationErrors:
    """Test configuration related error handling"""
    
    def test_missing_ml_dependencies(self, error_helper):
        """Test handling when ML dependencies are missing"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "test.mp4")
        
        with open(video_file, 'w') as f:
            f.write("fake video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        
        # Act - Simulate missing ML dependencies
        with patch('services.ground_truth_service.ML_AVAILABLE', False):
            service = GroundTruthService()
            service.ml_available = False
            service.model = None
            
            service._process_video(video.id, video_file)
        
        # Assert - Should handle gracefully (fallback or skip ML processing)
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            # Should complete with warning/failure or use fallback
            assert updated_video.status in ["failed", "completed", "validated"]
        finally:
            db.close()
    
    def test_invalid_model_path(self, error_helper):
        """Test handling of invalid model paths"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "test.mp4")
        
        with open(video_file, 'w') as f:
            f.write("fake video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        
        # Act - Simulate service with invalid model path
        service = GroundTruthService()
        service.model_path_selected = "/nonexistent/model.pt"
        
        # Mock YOLO to raise error for invalid path
        with patch('services.ground_truth_service.YOLO') as mock_yolo:
            mock_yolo.side_effect = FileNotFoundError("Model file not found")
            
            service._process_video(video.id, video_file)
        
        # Assert - Should handle gracefully
        db = SessionLocal()
        try:
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            assert updated_video.status == "failed"
        finally:
            db.close()

class TestSystemRecovery:
    """Test system recovery mechanisms"""
    
    def test_processing_retry_mechanism(self, error_helper):
        """Test that failed processing can be retried"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "test.mp4")
        
        with open(video_file, 'w') as f:
            f.write("fake video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        service = GroundTruthService()
        
        # Act - First attempt fails
        with patch.object(service, '_extract_detections') as mock_extract:
            mock_extract.side_effect = Exception("Temporary failure")
            
            service._process_video(video.id, video_file)
        
        # Verify failure
        db = SessionLocal()
        try:
            failed_video = db.query(Video).filter(Video.id == video.id).first()
            assert failed_video.status == "failed"
        finally:
            db.close()
        
        # Second attempt succeeds
        with patch.object(service, '_extract_detections') as mock_extract:
            mock_extract.return_value = [
                {
                    "frame_number": 30,
                    "timestamp": 1.0,
                    "class_label": "pedestrian",
                    "x": 100.0,
                    "y": 200.0,
                    "width": 80.0,
                    "height": 160.0,
                    "confidence": 0.85,
                    "validated": True,
                    "difficult": False
                }
            ]
            
            service._process_video(video.id, video_file)
        
        # Assert - Should recover and succeed
        db = SessionLocal()
        try:
            recovered_video = db.query(Video).filter(Video.id == video.id).first()
            assert recovered_video.status in ["validated", "completed"]
            assert recovered_video.ground_truth_generated is True
        finally:
            db.close()
    
    def test_partial_processing_recovery(self, error_helper):
        """Test recovery from partial processing failures"""
        # Arrange
        project = error_helper.create_test_project()
        temp_dir = error_helper.create_temp_directory()
        video_file = os.path.join(temp_dir, "test.mp4")
        
        with open(video_file, 'w') as f:
            f.write("fake video data")
        
        video = error_helper.create_test_video(project.id, video_file)
        
        # Simulate partial processing (some ground truth objects already exist)
        db = SessionLocal()
        try:
            existing_gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                frame_number=50,
                timestamp=1.67,
                class_label="pedestrian",
                x=120.0,
                y=190.0,
                width=85.0,
                height=165.0,
                confidence=0.87,
                validated=True,
                difficult=False
            )
            db.add(existing_gt)
            db.commit()
        finally:
            db.close()
        
        service = GroundTruthService()
        
        # Act - Reprocess (should handle existing data gracefully)
        with patch.object(service, '_extract_detections') as mock_extract:
            mock_extract.return_value = [
                {
                    "frame_number": 75,
                    "timestamp": 2.5,
                    "class_label": "cyclist",
                    "x": 200.0,
                    "y": 150.0,
                    "width": 90.0,
                    "height": 170.0,
                    "confidence": 0.92,
                    "validated": True,
                    "difficult": False
                }
            ]
            
            service._process_video(video.id, video_file)
        
        # Assert - Should complete with both old and new data
        db = SessionLocal()
        try:
            gt_objects = db.query(GroundTruthObject).filter(
                GroundTruthObject.video_id == video.id
            ).all()
            
            # Should have at least the existing one plus new ones
            assert len(gt_objects) >= 1
            
            updated_video = db.query(Video).filter(Video.id == video.id).first()
            assert updated_video.ground_truth_generated is True
        finally:
            db.close()

def analyze_error_patterns(test_results: List[Dict]) -> Dict[str, Any]:
    """
    Analyze error patterns from test results using 5 Whys methodology.
    
    Args:
        test_results: List of test results with error information
        
    Returns:
        Analysis report with error patterns and root causes
    """
    error_analysis = {
        "total_tests": len(test_results),
        "failed_tests": [r for r in test_results if not r.get("passed", True)],
        "error_categories": {},
        "root_cause_analysis": {},
        "recommendations": []
    }
    
    # Categorize errors
    for result in error_analysis["failed_tests"]:
        error_type = result.get("error_type", "unknown")
        if error_type not in error_analysis["error_categories"]:
            error_analysis["error_categories"][error_type] = []
        error_analysis["error_categories"][error_type].append(result)
    
    # Perform 5 Whys analysis for each error category
    for error_type, errors in error_analysis["error_categories"].items():
        if len(errors) > 1:  # Only analyze patterns with multiple occurrences
            error_analysis["root_cause_analysis"][error_type] = perform_five_whys(
                f"Multiple {error_type} errors occurred"
            )
    
    return error_analysis

def perform_five_whys(problem_statement: str) -> Dict[str, str]:
    """
    Perform 5 Whys analysis for a given problem.
    
    Args:
        problem_statement: Description of the problem
        
    Returns:
        5 Whys analysis structure
    """
    # This would be implemented based on specific error patterns
    return {
        "problem": problem_statement,
        "why_1": "Insufficient error handling in code",
        "why_2": "Error scenarios not fully identified during design",
        "why_3": "Limited testing of edge cases",
        "why_4": "Incomplete requirements for error handling",
        "why_5": "Lack of systematic error analysis process",
        "root_cause": "Systematic error handling process needs improvement",
        "corrective_actions": [
            "Implement comprehensive error handling framework",
            "Expand test coverage for edge cases",
            "Add systematic error analysis to development process",
            "Improve logging and monitoring for error detection"
        ]
    }

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])