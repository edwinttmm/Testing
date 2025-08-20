"""
Database Persistence Validation Tests
Tests database consistency, transactions, and data integrity
"""

import pytest
import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import tempfile
import os
import uuid
from datetime import datetime

# Import models and database setup
import sys
sys.path.append('../../../ai-model-validation-platform/backend')

from database import Base, get_db
from models import Project, Video, GroundTruthObject, TestSession, DetectionEvent, Annotation, AnnotationSession
from schemas import ProjectCreate, VideoUploadResponse
from conftest import test_client, test_db


class TestDatabasePersistence:
    """Test database persistence and consistency"""

    @pytest.fixture(autouse=True)
    def setup_test_db(self, test_db):
        """Setup test database for each test"""
        self.db = test_db
        yield
        # Cleanup is handled by conftest.py

    def test_project_creation_persistence(self, test_db):
        """Test project creation persists correctly to database"""
        # Arrange
        project_data = {
            "id": str(uuid.uuid4()),
            "name": "Test Project Persistence",
            "description": "Testing database persistence",
            "camera_model": "TestCam v1.0",
            "camera_view": "Front-facing VRU",
            "lens_type": "Wide-angle",
            "resolution": "1920x1080",
            "frame_rate": 30,
            "signal_type": "GPIO",
            "status": "Active",
            "owner_id": "test-user"
        }

        # Act
        project = Project(**project_data)
        test_db.add(project)
        test_db.commit()
        test_db.refresh(project)

        # Query from database
        persisted_project = test_db.query(Project).filter(Project.id == project.id).first()

        # Assert
        assert persisted_project is not None
        assert persisted_project.name == project_data["name"]
        assert persisted_project.description == project_data["description"]
        assert persisted_project.camera_model == project_data["camera_model"]
        assert persisted_project.status == project_data["status"]
        assert persisted_project.created_at is not None
        assert persisted_project.id == project_data["id"]

    def test_video_upload_persistence(self, test_db):
        """Test video upload data persists correctly"""
        # Arrange - Create project first
        project = Project(
            id=str(uuid.uuid4()),
            name="Video Test Project",
            description="For testing video persistence",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        video_data = {
            "id": str(uuid.uuid4()),
            "filename": "test-persistence-video.mp4",
            "file_path": "/uploads/test-persistence-video.mp4",
            "file_size": 5000000,  # 5MB
            "duration": 30.0,
            "fps": 30.0,
            "resolution": "1920x1080",
            "status": "uploaded",
            "processing_status": "pending",
            "ground_truth_generated": False,
            "project_id": project.id
        }

        # Act
        video = Video(**video_data)
        test_db.add(video)
        test_db.commit()
        test_db.refresh(video)

        # Query from database
        persisted_video = test_db.query(Video).filter(Video.id == video.id).first()

        # Assert
        assert persisted_video is not None
        assert persisted_video.filename == video_data["filename"]
        assert persisted_video.file_size == video_data["file_size"]
        assert persisted_video.duration == video_data["duration"]
        assert persisted_video.fps == video_data["fps"]
        assert persisted_video.project_id == project.id
        assert persisted_video.created_at is not None

        # Test relationship
        assert persisted_video.project is not None
        assert persisted_video.project.id == project.id

    def test_ground_truth_annotation_persistence(self, test_db):
        """Test ground truth annotations persist correctly"""
        # Arrange - Create project and video
        project = Project(
            id=str(uuid.uuid4()),
            name="GT Test Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        video = Video(
            id=str(uuid.uuid4()),
            filename="test-gt-video.mp4",
            file_path="/uploads/test-gt-video.mp4",
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        # Create ground truth object
        gt_data = {
            "id": str(uuid.uuid4()),
            "video_id": video.id,
            "frame_number": 150,
            "timestamp": 5.0,
            "class_label": "pedestrian",
            "x": 100.0,
            "y": 50.0,
            "width": 60.0,
            "height": 120.0,
            "confidence": 0.95,
            "validated": True,
            "difficult": False
        }

        # Act
        gt_object = GroundTruthObject(**gt_data)
        test_db.add(gt_object)
        test_db.commit()
        test_db.refresh(gt_object)

        # Query from database
        persisted_gt = test_db.query(GroundTruthObject).filter(
            GroundTruthObject.id == gt_object.id
        ).first()

        # Assert
        assert persisted_gt is not None
        assert persisted_gt.video_id == video.id
        assert persisted_gt.frame_number == gt_data["frame_number"]
        assert persisted_gt.timestamp == gt_data["timestamp"]
        assert persisted_gt.class_label == gt_data["class_label"]
        assert persisted_gt.x == gt_data["x"]
        assert persisted_gt.y == gt_data["y"]
        assert persisted_gt.width == gt_data["width"]
        assert persisted_gt.height == gt_data["height"]
        assert persisted_gt.confidence == gt_data["confidence"]
        assert persisted_gt.validated == gt_data["validated"]

        # Test relationship
        assert persisted_gt.video is not None
        assert persisted_gt.video.id == video.id

    def test_foreign_key_constraints(self, test_db):
        """Test foreign key constraints are enforced"""
        # Try to create video without valid project_id
        invalid_video = Video(
            id=str(uuid.uuid4()),
            filename="invalid-video.mp4",
            file_path="/uploads/invalid-video.mp4",
            project_id="non-existent-project-id"
        )

        test_db.add(invalid_video)
        
        # Should raise integrity error due to foreign key constraint
        with pytest.raises(IntegrityError):
            test_db.commit()
        
        test_db.rollback()

    def test_cascade_delete_project_videos(self, test_db):
        """Test that deleting project cascades to delete videos"""
        # Arrange
        project = Project(
            id=str(uuid.uuid4()),
            name="Cascade Test Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        # Create multiple videos
        videos = []
        for i in range(3):
            video = Video(
                id=str(uuid.uuid4()),
                filename=f"cascade-test-video-{i}.mp4",
                file_path=f"/uploads/cascade-test-video-{i}.mp4",
                project_id=project.id
            )
            videos.append(video)
            test_db.add(video)
        test_db.commit()

        video_ids = [v.id for v in videos]

        # Act - Delete project
        test_db.delete(project)
        test_db.commit()

        # Assert - Videos should be deleted due to cascade
        remaining_videos = test_db.query(Video).filter(Video.id.in_(video_ids)).all()
        assert len(remaining_videos) == 0

    def test_cascade_delete_video_ground_truth(self, test_db):
        """Test that deleting video cascades to delete ground truth objects"""
        # Arrange
        project = Project(
            id=str(uuid.uuid4()),
            name="GT Cascade Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        video = Video(
            id=str(uuid.uuid4()),
            filename="gt-cascade-video.mp4",
            file_path="/uploads/gt-cascade-video.mp4",
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        # Create ground truth objects
        gt_objects = []
        for i in range(5):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=video.id,
                frame_number=i * 10,
                timestamp=i * 0.33,
                class_label="pedestrian",
                x=10.0 * i,
                y=20.0 * i,
                width=60.0,
                height=120.0
            )
            gt_objects.append(gt)
            test_db.add(gt)
        test_db.commit()

        gt_ids = [gt.id for gt in gt_objects]

        # Act - Delete video
        test_db.delete(video)
        test_db.commit()

        # Assert - Ground truth objects should be deleted due to cascade
        remaining_gt = test_db.query(GroundTruthObject).filter(GroundTruthObject.id.in_(gt_ids)).all()
        assert len(remaining_gt) == 0

    def test_transaction_rollback_on_error(self, test_db):
        """Test transaction rollback on database errors"""
        # Arrange
        project1 = Project(
            id=str(uuid.uuid4()),
            name="Transaction Test 1",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )

        project2 = Project(
            id=project1.id,  # Duplicate ID - should cause error
            name="Transaction Test 2",
            camera_model="TestCam",
            camera_view="Front-facing VRU", 
            signal_type="GPIO"
        )

        # Act - Try to add both projects in same transaction
        test_db.add(project1)
        test_db.add(project2)

        with pytest.raises(IntegrityError):
            test_db.commit()

        test_db.rollback()

        # Assert - Neither project should exist
        projects = test_db.query(Project).filter(Project.id == project1.id).all()
        assert len(projects) == 0

    def test_concurrent_operations_integrity(self, test_db):
        """Test database integrity under concurrent operations"""
        # Arrange
        project = Project(
            id=str(uuid.uuid4()),
            name="Concurrent Test Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        # Simulate concurrent video uploads
        videos = []
        for i in range(10):
            video = Video(
                id=str(uuid.uuid4()),
                filename=f"concurrent-video-{i}.mp4",
                file_path=f"/uploads/concurrent-video-{i}.mp4",
                project_id=project.id,
                file_size=1000000 * i
            )
            videos.append(video)
            test_db.add(video)

        # Act - Commit all at once
        test_db.commit()

        # Assert - All videos should be persisted
        persisted_videos = test_db.query(Video).filter(Video.project_id == project.id).all()
        assert len(persisted_videos) == 10

        # Check each video
        for i, video in enumerate(persisted_videos):
            assert video.project_id == project.id
            assert f"concurrent-video-" in video.filename

    def test_database_indexes_performance(self, test_db):
        """Test that database indexes improve query performance"""
        # Arrange - Create project and many videos
        project = Project(
            id=str(uuid.uuid4()),
            name="Performance Test Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        # Create many ground truth objects for performance testing
        import time
        start_time = time.time()

        for i in range(100):
            gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=str(uuid.uuid4()),  # Random video IDs
                frame_number=i,
                timestamp=i * 0.1,
                class_label="pedestrian" if i % 2 == 0 else "cyclist",
                x=float(i),
                y=float(i * 2),
                width=60.0,
                height=120.0
            )
            test_db.add(gt)

        test_db.commit()
        insert_time = time.time() - start_time

        # Act - Query with indexed fields
        start_time = time.time()
        pedestrians = test_db.query(GroundTruthObject).filter(
            GroundTruthObject.class_label == "pedestrian"
        ).all()
        query_time = time.time() - start_time

        # Assert
        assert len(pedestrians) == 50  # Half should be pedestrians
        assert insert_time < 5.0  # Should insert quickly
        assert query_time < 1.0   # Should query quickly with index

    def test_data_type_constraints(self, test_db):
        """Test that data type constraints are enforced"""
        # Test invalid data types
        project = Project(
            id=str(uuid.uuid4()),
            name="Data Type Test",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        # Try to create video with invalid data types
        with pytest.raises((ValueError, IntegrityError)):
            invalid_video = Video(
                id=str(uuid.uuid4()),
                filename="test-video.mp4",
                file_path="/uploads/test-video.mp4",
                project_id=project.id,
                file_size="not_a_number",  # Should be integer
                duration="invalid_duration"  # Should be float
            )
            test_db.add(invalid_video)
            test_db.commit()

        test_db.rollback()

    def test_null_constraints(self, test_db):
        """Test that NOT NULL constraints are enforced"""
        # Try to create project without required fields
        with pytest.raises(IntegrityError):
            invalid_project = Project(
                id=str(uuid.uuid4()),
                # name is missing - should be NOT NULL
                description="Test description",
                camera_model="TestCam",
                camera_view="Front-facing VRU",
                signal_type="GPIO"
            )
            test_db.add(invalid_project)
            test_db.commit()

        test_db.rollback()

    def test_annotation_persistence(self, test_db):
        """Test annotation data persistence"""
        # Arrange
        project = Project(
            id=str(uuid.uuid4()),
            name="Annotation Test Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        video = Video(
            id=str(uuid.uuid4()),
            filename="annotation-test-video.mp4",
            file_path="/uploads/annotation-test-video.mp4",
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        annotation_data = {
            "id": str(uuid.uuid4()),
            "video_id": video.id,
            "detection_id": "det-001",
            "frame_number": 150,
            "timestamp": 5.0,
            "vru_type": "pedestrian",
            "bounding_box": {"x": 100, "y": 50, "width": 60, "height": 120},
            "occluded": False,
            "truncated": False,
            "difficult": False,
            "notes": "Test annotation",
            "annotator": "test-user",
            "validated": True
        }

        # Act
        annotation = Annotation(**annotation_data)
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)

        # Query from database
        persisted_annotation = test_db.query(Annotation).filter(
            Annotation.id == annotation.id
        ).first()

        # Assert
        assert persisted_annotation is not None
        assert persisted_annotation.detection_id == annotation_data["detection_id"]
        assert persisted_annotation.frame_number == annotation_data["frame_number"]
        assert persisted_annotation.timestamp == annotation_data["timestamp"]
        assert persisted_annotation.vru_type == annotation_data["vru_type"]
        assert persisted_annotation.bounding_box == annotation_data["bounding_box"]
        assert persisted_annotation.validated == annotation_data["validated"]
        assert persisted_annotation.video_id == video.id

    def test_test_session_persistence(self, test_db):
        """Test test session data persistence"""
        # Arrange
        project = Project(
            id=str(uuid.uuid4()),
            name="Test Session Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        video = Video(
            id=str(uuid.uuid4()),
            filename="session-test-video.mp4",
            file_path="/uploads/session-test-video.mp4",
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        session_data = {
            "id": str(uuid.uuid4()),
            "name": "Test Session",
            "project_id": project.id,
            "video_id": video.id,
            "tolerance_ms": 100,
            "status": "created",
            "started_at": datetime.utcnow(),
            "completed_at": None
        }

        # Act
        session = TestSession(**session_data)
        test_db.add(session)
        test_db.commit()
        test_db.refresh(session)

        # Query from database
        persisted_session = test_db.query(TestSession).filter(
            TestSession.id == session.id
        ).first()

        # Assert
        assert persisted_session is not None
        assert persisted_session.name == session_data["name"]
        assert persisted_session.project_id == project.id
        assert persisted_session.video_id == video.id
        assert persisted_session.tolerance_ms == session_data["tolerance_ms"]
        assert persisted_session.status == session_data["status"]
        assert persisted_session.started_at is not None

    def test_detection_event_persistence(self, test_db):
        """Test detection event data persistence"""
        # Arrange
        project = Project(
            id=str(uuid.uuid4()),
            name="Detection Event Project", 
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        test_db.add(project)
        test_db.commit()

        video = Video(
            id=str(uuid.uuid4()),
            filename="detection-event-video.mp4",
            file_path="/uploads/detection-event-video.mp4",
            project_id=project.id
        )
        test_db.add(video)
        test_db.commit()

        session = TestSession(
            id=str(uuid.uuid4()),
            name="Detection Test Session",
            project_id=project.id,
            video_id=video.id,
            status="running"
        )
        test_db.add(session)
        test_db.commit()

        event_data = {
            "id": str(uuid.uuid4()),
            "test_session_id": session.id,
            "timestamp": 5.5,
            "detection_id": "det-event-001",
            "validation_result": "TP",
            "confidence": 0.92,
            "class_label": "pedestrian",
            "bounding_box": {"x": 150, "y": 75, "width": 80, "height": 160},
            "ground_truth_match": True
        }

        # Act
        event = DetectionEvent(**event_data)
        test_db.add(event)
        test_db.commit()
        test_db.refresh(event)

        # Query from database
        persisted_event = test_db.query(DetectionEvent).filter(
            DetectionEvent.id == event.id
        ).first()

        # Assert
        assert persisted_event is not None
        assert persisted_event.test_session_id == session.id
        assert persisted_event.timestamp == event_data["timestamp"]
        assert persisted_event.detection_id == event_data["detection_id"]
        assert persisted_event.validation_result == event_data["validation_result"]
        assert persisted_event.confidence == event_data["confidence"]
        assert persisted_event.class_label == event_data["class_label"]
        assert persisted_event.bounding_box == event_data["bounding_box"]
        assert persisted_event.ground_truth_match == event_data["ground_truth_match"]


if __name__ == "__main__":
    pytest.main([__file__])