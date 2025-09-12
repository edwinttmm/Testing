"""
Comprehensive Test Suite for Annotation Models
SPARC TDD Implementation - Red Phase
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Import models and database
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from models import Base, Project, Video, Annotation, AnnotationSession, DetectionEvent, GroundTruthObject
from database import get_db

class TestAnnotationModels:
    """Test suite for annotation database models"""
    
    @pytest.fixture
    def db_session(self):
        """Create in-memory SQLite database for testing"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def sample_project(self, db_session):
        """Create sample project for testing"""
        project = Project(
            name="Test Annotation Project",
            description="Testing annotation system",
            camera_model="TestCam V1",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        return project
    
    @pytest.fixture
    def sample_video(self, db_session, sample_project):
        """Create sample video for testing"""
        video = Video(
            filename="test_video.mp4",
            file_path="/uploads/test_video.mp4",
            file_size=1024000,
            duration=30.0,
            fps=30.0,
            resolution="1920x1080",
            project_id=sample_project.id
        )
        db_session.add(video)
        db_session.commit()
        return video

    def test_annotation_creation(self, db_session, sample_video):
        """Test basic annotation creation"""
        annotation = Annotation(
            video_id=sample_video.id,
            detection_id="DET_PED_0001",
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 200, "width": 50, "height": 100},
            annotator="test_user"
        )
        
        db_session.add(annotation)
        db_session.commit()
        
        assert annotation.id is not None
        assert annotation.video_id == sample_video.id
        assert annotation.detection_id == "DET_PED_0001"
        assert annotation.frame_number == 100
        assert annotation.timestamp == 3.33
        assert annotation.vru_type == "pedestrian"
        assert annotation.bounding_box["width"] == 50
        assert annotation.validated is False
    
    def test_annotation_bounding_box_validation(self, db_session, sample_video):
        """Test bounding box data validation"""
        # Valid bounding box
        valid_bbox = {"x": 100, "y": 200, "width": 50, "height": 100}
        annotation = Annotation(
            video_id=sample_video.id,
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box=valid_bbox
        )
        
        db_session.add(annotation)
        db_session.commit()
        
        assert annotation.bounding_box == valid_bbox
    
    def test_annotation_temporal_constraints(self, db_session, sample_video):
        """Test temporal annotation constraints"""
        # Create annotation with end timestamp
        annotation = Annotation(
            video_id=sample_video.id,
            frame_number=100,
            timestamp=3.33,
            end_timestamp=5.67,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 200, "width": 50, "height": 100}
        )
        
        db_session.add(annotation)
        db_session.commit()
        
        assert annotation.timestamp < annotation.end_timestamp
        assert annotation.end_timestamp == 5.67
    
    def test_annotation_required_fields(self, db_session, sample_video):
        """Test annotation required field validation"""
        with pytest.raises(IntegrityError):
            # Missing required vru_type
            annotation = Annotation(
                video_id=sample_video.id,
                frame_number=100,
                timestamp=3.33,
                bounding_box={"x": 100, "y": 200, "width": 50, "height": 100}
            )
            db_session.add(annotation)
            db_session.commit()
    
    def test_annotation_session_creation(self, db_session, sample_project, sample_video):
        """Test annotation session creation"""
        session_obj = AnnotationSession(
            video_id=sample_video.id,
            project_id=sample_project.id,
            annotator_id="user_123",
            status="active",
            total_detections=10,
            validated_detections=5,
            current_frame=100,
            total_frames=900
        )
        
        db_session.add(session_obj)
        db_session.commit()
        
        assert session_obj.id is not None
        assert session_obj.status == "active"
        assert session_obj.total_detections == 10
        assert session_obj.validated_detections == 5
        assert session_obj.current_frame == 100
    
    def test_annotation_video_relationship(self, db_session, sample_video):
        """Test annotation-video relationship"""
        annotation1 = Annotation(
            video_id=sample_video.id,
            frame_number=100,
            timestamp=3.33,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 200, "width": 50, "height": 100}
        )
        annotation2 = Annotation(
            video_id=sample_video.id,
            frame_number=200,
            timestamp=6.67,
            vru_type="cyclist",
            bounding_box={"x": 150, "y": 250, "width": 60, "height": 120}
        )
        
        db_session.add_all([annotation1, annotation2])
        db_session.commit()
        
        # Check relationship
        video = db_session.query(Video).filter_by(id=sample_video.id).first()
        assert len(video.annotations) == 2
        assert video.annotations[0].vru_type in ["pedestrian", "cyclist"]
        assert video.annotations[1].vru_type in ["pedestrian", "cyclist"]
    
    def test_annotation_indexes_performance(self, db_session, sample_video):
        """Test that indexes are created for performance queries"""
        # Create multiple annotations
        annotations = []
        for i in range(100):
            annotation = Annotation(
                video_id=sample_video.id,
                detection_id=f"DET_PED_{i:04d}",
                frame_number=i * 10,
                timestamp=i * 0.333,
                vru_type="pedestrian" if i % 2 == 0 else "cyclist",
                bounding_box={"x": 100 + i, "y": 200 + i, "width": 50, "height": 100},
                validated=i % 3 == 0
            )
            annotations.append(annotation)
        
        db_session.add_all(annotations)
        db_session.commit()
        
        # Test indexed queries should be fast
        # Query by video_id and frame_number
        frame_query = db_session.query(Annotation).filter(
            Annotation.video_id == sample_video.id,
            Annotation.frame_number.between(100, 500)
        ).all()
        assert len(frame_query) == 41  # Frames 100-500, step 10
        
        # Query by video_id and timestamp
        time_query = db_session.query(Annotation).filter(
            Annotation.video_id == sample_video.id,
            Annotation.timestamp.between(10.0, 20.0)
        ).all()
        assert len(time_query) == 31  # Timestamps in range
        
        # Query by video_id and validated status
        validated_query = db_session.query(Annotation).filter(
            Annotation.video_id == sample_video.id,
            Annotation.validated == True
        ).all()
        assert len(validated_query) == 34  # Every 3rd annotation is validated

class TestAnnotationValidation:
    """Test annotation validation logic"""
    
    def test_bounding_box_format_validation(self):
        """Test bounding box format validation"""
        # This will be implemented in the validator
        valid_bbox = {"x": 100, "y": 200, "width": 50, "height": 100}
        assert self._is_valid_bounding_box(valid_bbox)
        
        # Invalid bounding boxes
        invalid_bboxes = [
            {"x": -10, "y": 200, "width": 50, "height": 100},  # Negative x
            {"x": 100, "y": -10, "width": 50, "height": 100},  # Negative y
            {"x": 100, "y": 200, "width": 0, "height": 100},   # Zero width
            {"x": 100, "y": 200, "width": 50, "height": 0},    # Zero height
            {"x": 100, "y": 200, "width": -50, "height": 100}, # Negative width
            {"x": 100, "y": 200, "width": 50, "height": -100}, # Negative height
            {"y": 200, "width": 50, "height": 100},             # Missing x
            {"x": 100, "width": 50, "height": 100},             # Missing y
            {"x": 100, "y": 200, "height": 100},                # Missing width
            {"x": 100, "y": 200, "width": 50},                  # Missing height
        ]
        
        for bbox in invalid_bboxes:
            assert not self._is_valid_bounding_box(bbox)
    
    def test_bounding_box_bounds_validation(self):
        """Test bounding box image bounds validation"""
        image_width, image_height = 1920, 1080
        
        # Valid bounding box within bounds
        valid_bbox = {"x": 100, "y": 200, "width": 50, "height": 100}
        assert self._is_within_image_bounds(valid_bbox, image_width, image_height)
        
        # Invalid - extends beyond right edge
        invalid_right = {"x": 1900, "y": 200, "width": 50, "height": 100}
        assert not self._is_within_image_bounds(invalid_right, image_width, image_height)
        
        # Invalid - extends beyond bottom edge
        invalid_bottom = {"x": 100, "y": 1000, "width": 50, "height": 100}
        assert not self._is_within_image_bounds(invalid_bottom, image_width, image_height)
        
        # Edge case - exactly at bounds (should be valid)
        edge_case = {"x": 1870, "y": 980, "width": 50, "height": 100}
        assert self._is_within_image_bounds(edge_case, image_width, image_height)
    
    def test_temporal_validation(self):
        """Test temporal constraint validation"""
        video_duration = 30.0  # 30 seconds
        
        # Valid timestamps
        assert self._is_valid_timestamp(5.0, video_duration)
        assert self._is_valid_timestamp(0.0, video_duration)
        assert self._is_valid_timestamp(30.0, video_duration)
        
        # Invalid timestamps
        assert not self._is_valid_timestamp(-1.0, video_duration)
        assert not self._is_valid_timestamp(31.0, video_duration)
        
        # Valid temporal range
        assert self._is_valid_temporal_range(5.0, 10.0, video_duration)
        
        # Invalid temporal ranges
        assert not self._is_valid_temporal_range(10.0, 5.0, video_duration)  # End before start
        assert not self._is_valid_temporal_range(-1.0, 5.0, video_duration)   # Start negative
        assert not self._is_valid_temporal_range(5.0, 31.0, video_duration)   # End beyond duration
    
    def _is_valid_bounding_box(self, bbox: dict) -> bool:
        """Helper method to validate bounding box format"""
        required_keys = ["x", "y", "width", "height"]
        
        # Check all required keys exist
        if not all(key in bbox for key in required_keys):
            return False
        
        # Check all values are numeric and positive (except x,y can be 0)
        if bbox["width"] <= 0 or bbox["height"] <= 0:
            return False
        
        if bbox["x"] < 0 or bbox["y"] < 0:
            return False
            
        return True
    
    def _is_within_image_bounds(self, bbox: dict, img_width: int, img_height: int) -> bool:
        """Helper method to validate bounding box is within image bounds"""
        return (bbox["x"] + bbox["width"] <= img_width and
                bbox["y"] + bbox["height"] <= img_height)
    
    def _is_valid_timestamp(self, timestamp: float, video_duration: float) -> bool:
        """Helper method to validate timestamp"""
        return 0.0 <= timestamp <= video_duration
    
    def _is_valid_temporal_range(self, start: float, end: float, video_duration: float) -> bool:
        """Helper method to validate temporal range"""
        return (start <= end and 
                self._is_valid_timestamp(start, video_duration) and
                self._is_valid_timestamp(end, video_duration))

class TestAnnotationStatistics:
    """Test annotation statistics and analytics"""
    
    @pytest.fixture
    def db_session(self):
        """Create in-memory SQLite database for testing"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()
    
    @pytest.fixture
    def sample_data(self, db_session):
        """Create comprehensive sample data for statistics testing"""
        project = Project(
            name="Stats Test Project",
            camera_model="TestCam",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.flush()
        
        video = Video(
            filename="stats_test.mp4",
            file_path="/uploads/stats_test.mp4",
            file_size=2048000,
            duration=60.0,
            fps=30.0,
            resolution="1920x1080",
            project_id=project.id
        )
        db_session.add(video)
        db_session.flush()
        
        # Create varied annotations for testing
        annotations = []
        vru_types = ["pedestrian", "cyclist", "wheelchair_user"]
        for i in range(50):
            annotation = Annotation(
                video_id=video.id,
                detection_id=f"DET_{vru_types[i % 3].upper()}_{i:04d}",
                frame_number=i * 10,
                timestamp=i * 2.0,
                vru_type=vru_types[i % 3],
                bounding_box={
                    "x": 100 + (i * 5) % 500,
                    "y": 200 + (i * 3) % 300,
                    "width": 50 + (i % 20),
                    "height": 100 + (i % 30)
                },
                validated=i % 4 == 0,  # 25% validated
                difficult=i % 10 == 0,  # 10% difficult
                occluded=i % 8 == 0,    # 12.5% occluded
                annotator=f"annotator_{i % 3}"  # 3 different annotators
            )
            annotations.append(annotation)
        
        db_session.add_all(annotations)
        db_session.commit()
        
        return {"project": project, "video": video, "annotations": annotations}
    
    def test_annotation_count_statistics(self, db_session, sample_data):
        """Test basic annotation counting statistics"""
        video_id = sample_data["video"].id
        
        # Total annotations
        total_count = db_session.query(Annotation).filter_by(video_id=video_id).count()
        assert total_count == 50
        
        # Count by VRU type
        pedestrian_count = db_session.query(Annotation).filter(
            Annotation.video_id == video_id,
            Annotation.vru_type == "pedestrian"
        ).count()
        assert pedestrian_count == 17  # 50/3 rounded up
        
        cyclist_count = db_session.query(Annotation).filter(
            Annotation.video_id == video_id,
            Annotation.vru_type == "cyclist"
        ).count()
        assert cyclist_count == 17
        
        wheelchair_count = db_session.query(Annotation).filter(
            Annotation.video_id == video_id,
            Annotation.vru_type == "wheelchair_user"
        ).count()
        assert wheelchair_count == 16
        
        # Validated annotations
        validated_count = db_session.query(Annotation).filter(
            Annotation.video_id == video_id,
            Annotation.validated == True
        ).count()
        assert validated_count == 13  # 25% of 50 (rounded up)
    
    def test_annotation_quality_statistics(self, db_session, sample_data):
        """Test annotation quality metrics"""
        video_id = sample_data["video"].id
        
        # Difficult annotations
        difficult_count = db_session.query(Annotation).filter(
            Annotation.video_id == video_id,
            Annotation.difficult == True
        ).count()
        assert difficult_count == 5  # 10% of 50
        
        # Occluded annotations
        occluded_count = db_session.query(Annotation).filter(
            Annotation.video_id == video_id,
            Annotation.occluded == True
        ).count()
        assert occluded_count == 7  # 12.5% of 50 (rounded up)
    
    def test_annotator_performance_statistics(self, db_session, sample_data):
        """Test annotator performance metrics"""
        video_id = sample_data["video"].id
        
        # Annotations by annotator
        from sqlalchemy import func
        
        annotator_stats = db_session.query(
            Annotation.annotator,
            func.count(Annotation.id).label('total'),
            func.sum(func.cast(Annotation.validated, int)).label('validated')
        ).filter(
            Annotation.video_id == video_id
        ).group_by(Annotation.annotator).all()
        
        assert len(annotator_stats) == 3  # 3 different annotators
        
        # Each annotator should have roughly equal work distribution
        for stat in annotator_stats:
            assert stat.total >= 16  # At least 16 annotations each
            assert stat.total <= 17  # At most 17 annotations each
            assert stat.validated >= 4  # At least 4 validated each

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])