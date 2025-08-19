"""
Unit tests for database models
"""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
import uuid


class TestProjectModel:
    """Test Project model functionality"""
    
    def test_project_creation(self, test_db_session, sample_project_data):
        """Test basic project creation"""
        from models import Project
        
        project = Project(
            name=sample_project_data["name"],
            description=sample_project_data["description"],
            camera_model=sample_project_data["cameraModel"],
            camera_view=sample_project_data["cameraView"],
            lens_type=sample_project_data["lensType"],
            resolution=sample_project_data["resolution"],
            frame_rate=sample_project_data["frameRate"],
            signal_type=sample_project_data["signalType"]
        )
        
        test_db_session.add(project)
        test_db_session.commit()
        test_db_session.refresh(project)
        
        assert project.id is not None
        assert project.name == sample_project_data["name"]
        assert project.status == "Active"  # Default status
        assert project.created_at is not None
        assert isinstance(project.created_at, datetime)
    
    def test_project_uuid_generation(self, test_db_session):
        """Test UUID generation for project IDs"""
        from models import Project
        
        project = Project(
            name="UUID Test",
            camera_model="Test Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        
        test_db_session.add(project)
        test_db_session.commit()
        
        # Should generate valid UUID
        assert len(project.id) == 36
        uuid.UUID(project.id)  # Should not raise exception
    
    def test_project_required_fields(self, test_db_session):
        """Test that required fields are enforced"""
        from models import Project
        
        # Missing required fields should fail
        with pytest.raises(IntegrityError):
            project = Project(description="Missing required fields")
            test_db_session.add(project)
            test_db_session.commit()
    
    def test_project_relationships(self, test_db_session, created_project):
        """Test project relationships work correctly"""
        from models import Video
        
        # Create video linked to project
        video = Video(
            filename="test.mp4",
            file_path="/test/test.mp4",
            project_id=created_project.id
        )
        test_db_session.add(video)
        test_db_session.commit()
        
        # Test relationship access
        assert len(created_project.videos) == 1
        assert created_project.videos[0].filename == "test.mp4"


class TestVideoModel:
    """Test Video model functionality"""
    
    def test_video_creation(self, test_db_session, created_project, sample_video_data):
        """Test basic video creation"""
        from models import Video
        
        video = Video(
            filename=sample_video_data["filename"],
            file_path=f"/uploads/{sample_video_data['filename']}",
            file_size=sample_video_data["file_size"],
            duration=sample_video_data["duration"],
            fps=sample_video_data["fps"],
            resolution=sample_video_data["resolution"],
            project_id=created_project.id
        )
        
        test_db_session.add(video)
        test_db_session.commit()
        test_db_session.refresh(video)
        
        assert video.id is not None
        assert video.filename == sample_video_data["filename"]
        assert video.status == "uploaded"  # Default status
        assert video.processing_status == "pending"  # Default processing status
        assert video.ground_truth_generated is False  # Default
    
    def test_video_processing_status_transitions(self, test_db_session, created_video):
        """Test processing status workflow"""
        valid_statuses = ["pending", "processing", "completed", "failed"]
        
        for status in valid_statuses:
            created_video.processing_status = status
            test_db_session.commit()
            test_db_session.refresh(created_video)
            assert created_video.processing_status == status
    
    def test_video_foreign_key_constraint(self, test_db_session):
        """Test foreign key constraint with invalid project_id"""
        from models import Video
        
        with pytest.raises(IntegrityError):
            video = Video(
                filename="test.mp4",
                file_path="/test/test.mp4",
                project_id="invalid-project-id"  # Non-existent project
            )
            test_db_session.add(video)
            test_db_session.commit()
    
    def test_video_metadata_fields(self, test_db_session, created_project):
        """Test video metadata fields"""
        from models import Video
        
        video = Video(
            filename="metadata_test.mp4",
            file_path="/uploads/metadata_test.mp4",
            project_id=created_project.id,
            file_size=5242880,  # 5MB
            duration=120.5,     # 2 minutes, 0.5 seconds
            fps=29.97,          # Standard NTSC frame rate
            resolution="1920x1080"
        )
        
        test_db_session.add(video)
        test_db_session.commit()
        
        assert video.file_size == 5242880
        assert video.duration == 120.5
        assert video.fps == 29.97
        assert video.resolution == "1920x1080"


class TestGroundTruthObjectModel:
    """Test GroundTruthObject model functionality"""
    
    def test_ground_truth_creation(self, test_db_session, created_video):
        """Test ground truth object creation"""
        from models import GroundTruthObject
        
        gt_obj = GroundTruthObject(
            video_id=created_video.id,
            frame_number=150,
            timestamp=5.0,
            class_label="pedestrian",
            x=100.5,
            y=200.3,
            width=50.7,
            height=100.2,
            confidence=0.95,
            validated=True
        )
        
        test_db_session.add(gt_obj)
        test_db_session.commit()
        test_db_session.refresh(gt_obj)
        
        assert gt_obj.id is not None
        assert gt_obj.video_id == created_video.id
        assert gt_obj.frame_number == 150
        assert gt_obj.timestamp == 5.0
        assert gt_obj.class_label == "pedestrian"
        assert gt_obj.confidence == 0.95
        assert gt_obj.validated is True
    
    def test_ground_truth_bounding_box_coordinates(self, test_db_session, created_video):
        """Test individual coordinate fields vs JSON bounding box"""
        from models import GroundTruthObject
        
        # Test with individual coordinates
        gt_obj = GroundTruthObject(
            video_id=created_video.id,
            timestamp=1.0,
            class_label="cyclist",
            x=10.5, y=20.3, width=30.7, height=40.2,
            confidence=0.8
        )
        
        test_db_session.add(gt_obj)
        test_db_session.commit()
        
        assert gt_obj.x == 10.5
        assert gt_obj.y == 20.3
        assert gt_obj.width == 30.7
        assert gt_obj.height == 40.2
    
    def test_ground_truth_json_bounding_box(self, test_db_session, created_video):
        """Test JSON bounding box field (legacy support)"""
        from models import GroundTruthObject
        
        bbox_data = {
            "x": 100,
            "y": 200,
            "width": 50,
            "height": 100,
            "normalized": True,
            "confidence": 0.9
        }
        
        gt_obj = GroundTruthObject(
            video_id=created_video.id,
            timestamp=2.0,
            class_label="pedestrian",
            x=100, y=200, width=50, height=100,
            bounding_box=bbox_data,
            confidence=0.9
        )
        
        test_db_session.add(gt_obj)
        test_db_session.commit()
        test_db_session.refresh(gt_obj)
        
        assert gt_obj.bounding_box == bbox_data
        assert gt_obj.bounding_box["normalized"] is True
    
    def test_ground_truth_cascade_delete(self, test_db_session, created_video):
        """Test cascade delete when video is deleted"""
        from models import GroundTruthObject
        
        gt_obj = GroundTruthObject(
            video_id=created_video.id,
            timestamp=1.0,
            class_label="pedestrian",
            x=100, y=200, width=50, height=100,
            confidence=0.9
        )
        
        test_db_session.add(gt_obj)
        test_db_session.commit()
        gt_obj_id = gt_obj.id
        
        # Delete video
        test_db_session.delete(created_video)
        test_db_session.commit()
        
        # Ground truth should be deleted
        remaining = test_db_session.query(GroundTruthObject).filter_by(id=gt_obj_id).first()
        assert remaining is None


class TestTestSessionModel:
    """Test TestSession model functionality"""
    
    def test_test_session_creation(self, test_db_session, created_project, created_video):
        """Test test session creation"""
        from models import TestSession
        
        session = TestSession(
            name="Performance Test Session",
            project_id=created_project.id,
            video_id=created_video.id,
            tolerance_ms=50
        )
        
        test_db_session.add(session)
        test_db_session.commit()
        test_db_session.refresh(session)
        
        assert session.id is not None
        assert session.name == "Performance Test Session"
        assert session.tolerance_ms == 50
        assert session.status == "created"  # Default status
    
    def test_test_session_timestamps(self, test_db_session, created_test_session):
        """Test test session timestamp management"""
        from datetime import datetime
        
        # Start the session
        start_time = datetime.now()
        created_test_session.started_at = start_time
        created_test_session.status = "running"
        test_db_session.commit()
        
        assert created_test_session.started_at == start_time
        assert created_test_session.status == "running"
        
        # Complete the session
        end_time = datetime.now()
        created_test_session.completed_at = end_time
        created_test_session.status = "completed"
        test_db_session.commit()
        
        assert created_test_session.completed_at == end_time
        assert created_test_session.status == "completed"


class TestDetectionEventModel:
    """Test DetectionEvent model functionality"""
    
    def test_detection_event_creation(self, test_db_session, created_test_session):
        """Test detection event creation"""
        from models import DetectionEvent
        
        event = DetectionEvent(
            test_session_id=created_test_session.id,
            timestamp=5.5,
            confidence=0.92,
            class_label="pedestrian",
            validation_result="TP"
        )
        
        test_db_session.add(event)
        test_db_session.commit()
        test_db_session.refresh(event)
        
        assert event.id is not None
        assert event.timestamp == 5.5
        assert event.confidence == 0.92
        assert event.class_label == "pedestrian"
        assert event.validation_result == "TP"
    
    def test_detection_event_validation_results(self, test_db_session, created_test_session):
        """Test different validation result types"""
        from models import DetectionEvent
        
        validation_types = ["TP", "FP", "FN", "TN"]
        
        for i, val_type in enumerate(validation_types):
            event = DetectionEvent(
                test_session_id=created_test_session.id,
                timestamp=float(i),
                confidence=0.8,
                class_label="pedestrian",
                validation_result=val_type
            )
            test_db_session.add(event)
        
        test_db_session.commit()
        
        # Verify all types were stored correctly
        for val_type in validation_types:
            event = test_db_session.query(DetectionEvent).filter_by(
                validation_result=val_type
            ).first()
            assert event is not None
            assert event.validation_result == val_type


class TestAnnotationModel:
    """Test Annotation model functionality"""
    
    def test_annotation_creation(self, test_db_session, created_video):
        """Test annotation creation with detection ID tracking"""
        from models import Annotation
        
        annotation = Annotation(
            video_id=created_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 200, "width": 50, "height": 100},
            occluded=False,
            truncated=False,
            difficult=False,
            notes="Clear detection",
            annotator="annotator_001",
            validated=True
        )
        
        test_db_session.add(annotation)
        test_db_session.commit()
        test_db_session.refresh(annotation)
        
        assert annotation.id is not None
        assert annotation.detection_id == "DET_PED_0001"
        assert annotation.vru_type == "pedestrian"
        assert annotation.validated is True
    
    def test_annotation_bounding_box_json(self, test_db_session, created_video):
        """Test JSON bounding box storage"""
        from models import Annotation
        
        complex_bbox = {
            "x": 150.5,
            "y": 300.7,
            "width": 75.2,
            "height": 150.8,
            "rotation": 5.5,
            "keypoints": [
                {"name": "head", "x": 175, "y": 310},
                {"name": "torso", "x": 175, "y": 375}
            ]
        }
        
        annotation = Annotation(
            video_id=created_video.id,
            frame_number=200,
            timestamp=6.67,
            vru_type="pedestrian",
            bounding_box=complex_bbox
        )
        
        test_db_session.add(annotation)
        test_db_session.commit()
        test_db_session.refresh(annotation)
        
        assert annotation.bounding_box == complex_bbox
        assert annotation.bounding_box["keypoints"][0]["name"] == "head"


class TestAuditLogModel:
    """Test AuditLog model functionality"""
    
    def test_audit_log_creation(self, test_db_session):
        """Test audit log creation"""
        from models import AuditLog
        
        log_entry = AuditLog(
            user_id="user_123",
            event_type="video_upload",
            event_data={
                "video_id": "video_456",
                "filename": "test.mp4",
                "size": 1024000
            },
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0 Test Browser"
        )
        
        test_db_session.add(log_entry)
        test_db_session.commit()
        test_db_session.refresh(log_entry)
        
        assert log_entry.id is not None
        assert log_entry.event_type == "video_upload"
        assert log_entry.event_data["video_id"] == "video_456"
        assert log_entry.ip_address == "192.168.1.100"
    
    def test_audit_log_anonymous_user(self, test_db_session):
        """Test audit log with anonymous user"""
        from models import AuditLog
        
        log_entry = AuditLog(
            event_type="api_access",
            event_data={"endpoint": "/health"},
            ip_address="10.0.0.1"
        )
        
        test_db_session.add(log_entry)
        test_db_session.commit()
        test_db_session.refresh(log_entry)
        
        assert log_entry.user_id == "anonymous"  # Default value