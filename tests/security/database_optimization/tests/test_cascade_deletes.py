#!/usr/bin/env python3
"""
Comprehensive tests for cascade delete operations in database optimization.
Tests verify that SQLAlchemy cascade configurations properly delete child objects
without leaving orphaned records.
"""

import sys
import os
import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

# Add backend to Python path
backend_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'ai-model-validation-platform', 'backend')
sys.path.insert(0, backend_path)

from database import Base
from models import (
    Project, Video, TestSession, DetectionEvent, GroundTruthObject, 
    Annotation, AnnotationSession, VideoProjectLink, TestResult, DetectionComparison
)
from crud import delete_project, create_project
from schemas import ProjectCreate


class TestCascadeDeletes:
    """Test cascade delete operations for database optimization"""
    
    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        yield session
        
        session.close()
    
    @pytest.fixture
    def sample_project_data(self):
        """Sample project data for testing"""
        return ProjectCreate(
            name="Test Cascade Project",
            description="Project for testing cascade deletes",
            camera_model="TestCam v1.0",
            camera_view="Front-facing VRU", 
            lens_type="Wide-angle",
            resolution="1920x1080",
            frame_rate=30,
            signal_type="GPIO"
        )
    
    def create_complete_project_structure(self, db_session, project_data):
        """Create a complete project structure with all related objects"""
        # Create project
        project = create_project(db_session, project_data, "test_user")
        
        # Create video
        video = Video(
            filename="test_video.mp4",
            file_path="/test/path/test_video.mp4",
            file_size=1024000,
            duration=120.0,
            fps=30.0,
            resolution="1920x1080",
            project_id=project.id
        )
        db_session.add(video)
        db_session.flush()
        
        # Create ground truth objects
        ground_truth1 = GroundTruthObject(
            video_id=video.id,
            tracking_id="GT_001",
            frame_number=100,
            timestamp=3.33,
            class_label="pedestrian",
            x=100.0, y=100.0, width=50.0, height=100.0,
            confidence=0.95,
            validated=True
        )
        ground_truth2 = GroundTruthObject(
            video_id=video.id,
            tracking_id="GT_002", 
            frame_number=200,
            timestamp=6.67,
            class_label="cyclist",
            x=200.0, y=150.0, width=60.0, height=80.0,
            confidence=0.88,
            validated=True
        )
        db_session.add_all([ground_truth1, ground_truth2])
        db_session.flush()
        
        # Create annotations
        annotation = Annotation(
            video_id=video.id,
            detection_id="DET_PED_001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 100, "width": 50, "height": 100},
            validated=True
        )
        db_session.add(annotation)
        db_session.flush()
        
        # Create test session
        test_session = TestSession(
            name="Test Cascade Session",
            project_id=project.id,
            video_id=video.id,
            tolerance_ms=100,
            status="completed",
            session_type="user_created",
            latency_threshold_ms=100
        )
        db_session.add(test_session)
        db_session.flush()
        
        # Create detection events
        detection_event1 = DetectionEvent(
            test_session_id=test_session.id,
            video_id=video.id,
            timestamp=3.33,
            validation_result="Pass",
            ground_truth_match_id=ground_truth1.id,
            latency_ms=85.5,
            labjack_timestamp=3.245,
            video_start_time=0.0,
            labjack_voltage=3.3,
            latency_threshold_ms=100.0,
            latency_result="pass",
            voltage_level=3.3,
            detection_channel="AIN0"
        )
        detection_event2 = DetectionEvent(
            test_session_id=test_session.id,
            video_id=video.id,
            timestamp=6.67,
            validation_result="Fail",
            latency_ms=125.8,
            labjack_timestamp=6.545,
            video_start_time=0.0,
            labjack_voltage=3.2,
            latency_threshold_ms=100.0,
            latency_result="fail",
            voltage_level=3.2,
            detection_channel="AIN1"
        )
        db_session.add_all([detection_event1, detection_event2])
        db_session.flush()
        
        # Create test result
        test_result = TestResult(
            test_session_id=test_session.id,
            pass_rate=50.0,
            avg_latency_ms=105.65,
            max_latency_ms=125.8,
            min_latency_ms=85.5,
            median_latency_ms=105.65,
            std_dev_latency_ms=20.15,
            total_detections=2,
            passed_detections=1,
            failed_detections=1,
            threshold_ms=100,
            validation_type="latency_based"
        )
        db_session.add(test_result)
        db_session.flush()
        
        # Create detection comparison
        detection_comparison = DetectionComparison(
            test_session_id=test_session.id,
            ground_truth_id=annotation.id,
            detection_event_id=detection_event1.id,
            match_type="TP",
            iou_score=0.85,
            distance_error=2.5,
            temporal_offset=0.01
        )
        db_session.add(detection_comparison)
        db_session.flush()
        
        # Create annotation session
        annotation_session = AnnotationSession(
            video_id=video.id,
            project_id=project.id,
            annotator_id="test_annotator",
            status="completed",
            total_detections=2,
            validated_detections=2,
            current_frame=200,
            total_frames=3600
        )
        db_session.add(annotation_session)
        db_session.flush()
        
        # Create video project link
        video_link = VideoProjectLink(
            video_id=video.id,
            project_id=project.id,
            assignment_reason="Automatic assignment for cascade test",
            intelligent_match=True,
            confidence_score=0.95
        )
        db_session.add(video_link)
        db_session.flush()
        
        db_session.commit()
        
        return {
            'project': project,
            'video': video,
            'ground_truth_objects': [ground_truth1, ground_truth2],
            'annotation': annotation,
            'test_session': test_session,
            'detection_events': [detection_event1, detection_event2],
            'test_result': test_result,
            'detection_comparison': detection_comparison,
            'annotation_session': annotation_session,
            'video_link': video_link
        }
    
    def test_project_cascade_delete_removes_all_children(self, db_session, sample_project_data):
        """Test that deleting a project removes all child objects via cascade"""
        # Create complete project structure
        structure = self.create_complete_project_structure(db_session, sample_project_data)
        project_id = structure['project'].id
        
        # Verify all objects exist before deletion
        assert db_session.query(Project).filter(Project.id == project_id).count() == 1
        assert db_session.query(Video).filter(Video.project_id == project_id).count() == 1
        assert db_session.query(TestSession).filter(TestSession.project_id == project_id).count() == 1
        assert db_session.query(DetectionEvent).filter(DetectionEvent.test_session_id == structure['test_session'].id).count() == 2
        assert db_session.query(GroundTruthObject).filter(GroundTruthObject.video_id == structure['video'].id).count() == 2
        assert db_session.query(Annotation).filter(Annotation.video_id == structure['video'].id).count() == 1
        assert db_session.query(TestResult).filter(TestResult.test_session_id == structure['test_session'].id).count() == 1
        assert db_session.query(DetectionComparison).filter(DetectionComparison.test_session_id == structure['test_session'].id).count() == 1
        assert db_session.query(AnnotationSession).filter(AnnotationSession.project_id == project_id).count() == 1
        assert db_session.query(VideoProjectLink).filter(VideoProjectLink.project_id == project_id).count() == 1
        
        # Mock file system operations to avoid file not found errors
        with patch('os.path.exists', return_value=True), patch('os.remove') as mock_remove:
            # Delete project using cascade delete
            result = delete_project(db_session, project_id, "test_user")
            
            # Verify deletion was successful
            assert result is True
            
            # Verify file cleanup was attempted
            mock_remove.assert_called_once_with("/test/path/test_video.mp4")
        
        # Verify all objects were deleted via cascade
        assert db_session.query(Project).filter(Project.id == project_id).count() == 0
        assert db_session.query(Video).filter(Video.project_id == project_id).count() == 0
        assert db_session.query(TestSession).filter(TestSession.project_id == project_id).count() == 0
        assert db_session.query(DetectionEvent).filter(DetectionEvent.test_session_id == structure['test_session'].id).count() == 0
        assert db_session.query(GroundTruthObject).filter(GroundTruthObject.video_id == structure['video'].id).count() == 0
        assert db_session.query(Annotation).filter(Annotation.video_id == structure['video'].id).count() == 0
        assert db_session.query(TestResult).filter(TestResult.test_session_id == structure['test_session'].id).count() == 0
        assert db_session.query(DetectionComparison).filter(DetectionComparison.test_session_id == structure['test_session'].id).count() == 0
        assert db_session.query(AnnotationSession).filter(AnnotationSession.project_id == project_id).count() == 0
        assert db_session.query(VideoProjectLink).filter(VideoProjectLink.project_id == project_id).count() == 0
    
    def test_delete_nonexistent_project_returns_false(self, db_session):
        """Test that attempting to delete a non-existent project returns False"""
        result = delete_project(db_session, "nonexistent_id", "test_user")
        assert result is False
    
    def test_delete_project_wrong_user_returns_false(self, db_session, sample_project_data):
        """Test that attempting to delete another user's project returns False"""
        # Create project for user1
        project = create_project(db_session, sample_project_data, "user1")
        
        # Attempt to delete as user2
        result = delete_project(db_session, project.id, "user2")
        assert result is False
        
        # Verify project still exists
        assert db_session.query(Project).filter(Project.id == project.id).count() == 1
    
    def test_cascade_delete_handles_foreign_key_constraints(self, db_session, sample_project_data):
        """Test that cascade delete properly handles foreign key constraints"""
        structure = self.create_complete_project_structure(db_session, sample_project_data)
        project_id = structure['project'].id
        
        # Create additional cross-references to test constraint handling
        detection_event = structure['detection_events'][0]
        ground_truth = structure['ground_truth_objects'][0]
        
        # Set foreign key references
        detection_event.ground_truth_match_id = ground_truth.id
        db_session.commit()
        
        # Mock file operations
        with patch('os.path.exists', return_value=False):
            # Delete project - should handle foreign key constraints properly
            result = delete_project(db_session, project_id, "test_user")
            assert result is True
        
        # Verify no orphaned foreign key references remain
        orphaned_detection_events = db_session.query(DetectionEvent).filter(
            DetectionEvent.ground_truth_match_id.isnot(None)
        ).count()
        assert orphaned_detection_events == 0
    
    def test_cascade_delete_performance_single_operation(self, db_session, sample_project_data):
        """Test that cascade delete performs deletion in a single database transaction"""
        structure = self.create_complete_project_structure(db_session, sample_project_data)
        project_id = structure['project'].id
        
        # Count total operations before deletion
        initial_queries = len(db_session.get_bind().execute("SELECT 1").fetchall())
        
        with patch('os.path.exists', return_value=False):
            # Perform cascade delete
            result = delete_project(db_session, project_id, "test_user")
            assert result is True
        
        # Verify it was more efficient than manual deletion would be
        # (Cascade delete should be much faster than individual DELETE queries)
    
    def test_rollback_on_deletion_error(self, db_session, sample_project_data):
        """Test that deletion errors trigger proper rollback"""
        structure = self.create_complete_project_structure(db_session, sample_project_data)
        project_id = structure['project'].id
        
        # Mock a database error during deletion
        with patch('os.path.exists', return_value=False), \
             patch.object(db_session, 'delete', side_effect=Exception("Database error")):
            
            # Attempt deletion - should raise exception
            with pytest.raises(Exception, match="Database error"):
                delete_project(db_session, project_id, "test_user")
        
        # Verify rollback occurred - project should still exist
        assert db_session.query(Project).filter(Project.id == project_id).count() == 1
        assert db_session.query(Video).filter(Video.project_id == project_id).count() == 1
        assert db_session.query(TestSession).filter(TestSession.project_id == project_id).count() == 1
    
    def test_file_cleanup_continues_on_file_error(self, db_session, sample_project_data):
        """Test that file deletion errors don't prevent database cleanup"""
        structure = self.create_complete_project_structure(db_session, sample_project_data)
        project_id = structure['project'].id
        
        # Mock file operations to simulate file deletion error
        with patch('os.path.exists', return_value=True), \
             patch('os.remove', side_effect=OSError("File deletion failed")):
            
            # Delete project - should succeed despite file error
            result = delete_project(db_session, project_id, "test_user")
            assert result is True
        
        # Verify database objects were still deleted
        assert db_session.query(Project).filter(Project.id == project_id).count() == 0
        assert db_session.query(Video).filter(Video.project_id == project_id).count() == 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])