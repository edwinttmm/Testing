"""
Test Suite for Annotation Service Layer
SPARC TDD Implementation - Testing business logic
"""

import pytest
import uuid
from unittest.mock import Mock, patch
from datetime import datetime

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from src.services.annotation_service import AnnotationService, AnnotationSessionService
from src.utils.annotation_validators import ValidationResult


class TestAnnotationService:
    """Test annotation service business logic"""
    
    @pytest.fixture
    def service(self):
        return AnnotationService()
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def sample_video(self):
        video = Mock()
        video.id = "test-video-id"
        video.duration = 30.0
        video.fps = 30.0
        video.resolution = "1920x1080"
        video.filename = "test_video.mp4"
        return video
    
    @pytest.fixture
    def valid_annotation_data(self):
        return {
            "video_id": "test-video-id",
            "frame_number": 100,
            "timestamp": 3.33,
            "vru_type": "pedestrian",
            "bounding_box": {"x": 100, "y": 200, "width": 50, "height": 100},
            "annotator": "test_user"
        }
    
    def test_create_annotation_success(self, service, mock_db, sample_video, valid_annotation_data):
        """Test successful annotation creation"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        # Mock validator to return valid result
        with patch.object(service.validator, 'validate_annotation') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True, 
                errors=[], 
                warnings=[], 
                metadata={}
            )
            
            result = service.create_annotation(mock_db, valid_annotation_data)
            
            assert result["success"] is True
            assert "annotation" in result
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    def test_create_annotation_video_not_found(self, service, mock_db, valid_annotation_data):
        """Test annotation creation with non-existent video"""
        # Setup mock to return None (video not found)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = service.create_annotation(mock_db, valid_annotation_data)
        
        assert result["success"] is False
        assert result["code"] == "VIDEO_NOT_FOUND"
    
    def test_create_annotation_validation_failure(self, service, mock_db, sample_video, valid_annotation_data):
        """Test annotation creation with validation failure"""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = sample_video
        
        # Mock validator to return invalid result
        with patch.object(service.validator, 'validate_annotation') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=False,
                errors=["Invalid bounding box"],
                warnings=[],
                metadata={}
            )
            
            result = service.create_annotation(mock_db, valid_annotation_data)
            
            assert result["success"] is False
            assert result["code"] == "VALIDATION_FAILED"
            assert "validation_errors" in result
    
    def test_get_annotation_success(self, service, mock_db):
        """Test successful annotation retrieval"""
        # Create mock annotation
        mock_annotation = Mock()
        mock_annotation.id = "test-annotation-id"
        mock_annotation.video_id = "test-video-id"
        mock_annotation.vru_type = "pedestrian"
        mock_annotation.bounding_box = {"x": 100, "y": 200, "width": 50, "height": 100}
        mock_annotation.created_at = datetime.utcnow()
        mock_annotation.updated_at = None
        
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = mock_annotation
        
        result = service.get_annotation(mock_db, "test-annotation-id")
        
        assert result is not None
        assert result["id"] == "test-annotation-id"
        assert result["vru_type"] == "pedestrian"
    
    def test_get_annotation_not_found(self, service, mock_db):
        """Test annotation retrieval with non-existent ID"""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = service.get_annotation(mock_db, "non-existent-id")
        
        assert result is None
    
    def test_update_annotation_success(self, service, mock_db, sample_video):
        """Test successful annotation update"""
        # Create mock annotation
        mock_annotation = Mock()
        mock_annotation.id = "test-annotation-id"
        mock_annotation.video_id = "test-video-id"
        mock_annotation.vru_type = "pedestrian"
        mock_annotation.bounding_box = {"x": 100, "y": 200, "width": 50, "height": 100}
        mock_annotation.validated = False
        
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.side_effect = [mock_annotation, sample_video]
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        update_data = {"validated": True, "annotator": "updated_user"}
        
        with patch.object(service.validator, 'validate_annotation') as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                metadata={}
            )
            
            with patch.object(service, '_annotation_to_dict') as mock_to_dict:
                mock_to_dict.return_value = {"id": "test-annotation-id", "validated": True}
                
                result = service.update_annotation(mock_db, "test-annotation-id", update_data)
                
                assert result["success"] is True
                mock_db.commit.assert_called_once()
    
    def test_delete_annotation_success(self, service, mock_db):
        """Test successful annotation deletion"""
        mock_annotation = Mock()
        mock_annotation.id = "test-annotation-id"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_annotation
        mock_db.delete = Mock()
        mock_db.commit = Mock()
        
        result = service.delete_annotation(mock_db, "test-annotation-id")
        
        assert result["success"] is True
        mock_db.delete.assert_called_once_with(mock_annotation)
        mock_db.commit.assert_called_once()
    
    def test_get_video_annotations_with_filters(self, service, mock_db):
        """Test getting video annotations with filters applied"""
        # Mock query chain
        mock_query = Mock()
        mock_db.query.return_value.filter.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value.all.return_value = []
        
        filters = {
            "vru_type": "pedestrian",
            "validated": True,
            "frame_range": (100, 500)
        }
        
        with patch.object(service, '_annotation_to_dict', return_value={}):
            result = service.get_video_annotations(mock_db, "test-video-id", filters)
            
            assert result["success"] is True
            assert result["count"] == 0
            assert result["filters_applied"] == filters
    
    def test_bulk_update_annotations(self, service, mock_db):
        """Test bulk updating annotations"""
        # Create mock annotations
        mock_annotations = [Mock(), Mock(), Mock()]
        for i, ann in enumerate(mock_annotations):
            ann.id = f"test-annotation-{i}"
            ann.updated_at = None
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_annotations
        mock_db.commit = Mock()
        
        annotation_ids = ["test-annotation-0", "test-annotation-1", "test-annotation-2"]
        update_data = {"validated": True, "annotator": "bulk_user"}
        
        result = service.bulk_update_annotations(mock_db, annotation_ids, update_data)
        
        assert result["success"] is True
        assert result["updated_count"] == 3
        assert result["total_requested"] == 3
        mock_db.commit.assert_called_once()


class TestAnnotationStatistics:
    """Test annotation statistics functionality"""
    
    @pytest.fixture
    def service(self):
        return AnnotationService()
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    def test_get_annotation_statistics(self, service, mock_db):
        """Test annotation statistics calculation"""
        # Create mock annotations with varied data
        mock_annotations = []
        vru_types = ["pedestrian", "cyclist", "pedestrian", "wheelchair_user"]
        
        for i, vru_type in enumerate(vru_types):
            mock_ann = Mock()
            mock_ann.vru_type = vru_type
            mock_ann.validated = i % 2 == 0  # Half validated
            mock_ann.difficult = i % 3 == 0  # Some difficult
            mock_ann.occluded = i % 4 == 0   # Some occluded
            mock_ann.truncated = False
            mock_ann.annotator = f"annotator_{i % 2}"  # Two annotators
            mock_ann.timestamp = float(i * 5)  # Timestamps: 0, 5, 10, 15
            mock_annotations.append(mock_ann)
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_annotations
        
        # Mock video
        mock_video = Mock()
        mock_video.id = "test-video-id"
        mock_video.resolution = "1920x1080"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_video
        
        with patch.object(service, '_annotation_to_dict', side_effect=lambda x: {"vru_type": x.vru_type}):
            with patch.object(service.geometric_validator, 'validate_annotation_density') as mock_geo:
                mock_geo.return_value = {"density": 0.1, "distribution": "balanced"}
                
                result = service.get_annotation_statistics(mock_db, "test-video-id")
                
                assert result["success"] is True
                stats = result["statistics"]
                
                assert stats["total_annotations"] == 4
                assert stats["by_vru_type"]["pedestrian"] == 2
                assert stats["by_vru_type"]["cyclist"] == 1
                assert stats["by_vru_type"]["wheelchair_user"] == 1
                assert stats["validation_status"]["validated"] == 2
                assert stats["validation_status"]["pending"] == 2
    
    def test_validate_annotation_sequence(self, service, mock_db):
        """Test annotation sequence validation"""
        mock_annotations = [Mock() for _ in range(3)]
        for i, ann in enumerate(mock_annotations):
            ann.timestamp = float(i * 5)  # 0, 5, 10
            
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_annotations
        
        with patch.object(service, '_annotation_to_dict', return_value={}):
            with patch.object(service.temporal_validator, 'validate_temporal_consistency') as mock_temporal:
                mock_temporal.return_value = {"consistency": 0.9, "issues": []}
                
                with patch.object(service.geometric_validator, 'find_overlapping_annotations') as mock_geo:
                    mock_geo.return_value = []
                    
                    with patch.object(service.validator, 'validate_annotation') as mock_validate:
                        mock_validate.return_value = ValidationResult(True, [], [], {})
                        
                        result = service.validate_annotation_sequence(mock_db, "test-video-id")
                        
                        assert result["success"] is True
                        assert "temporal_consistency" in result["validation"]
                        assert "geometric_overlaps" in result["validation"]
                        assert "overall_score" in result["validation"]


class TestAnnotationSessionService:
    """Test annotation session service"""
    
    @pytest.fixture
    def service(self):
        return AnnotationSessionService()
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    def test_create_session_success(self, service, mock_db):
        """Test successful session creation"""
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        session_data = {
            "video_id": "test-video-id",
            "project_id": "test-project-id",
            "annotator_id": "test-user",
            "total_frames": 900
        }
        
        with patch.object(service, '_session_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {"id": "test-session-id"}
            
            result = service.create_session(mock_db, session_data)
            
            assert result["success"] is True
            assert "session" in result
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
    
    def test_update_session_progress(self, service, mock_db):
        """Test session progress update"""
        mock_session = Mock()
        mock_session.id = "test-session-id"
        mock_session.current_frame = 100
        mock_session.total_detections = 10
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        progress_data = {
            "current_frame": 200,
            "total_detections": 15,
            "validated_detections": 12
        }
        
        with patch.object(service, '_session_to_dict') as mock_to_dict:
            mock_to_dict.return_value = {"id": "test-session-id", "current_frame": 200}
            
            result = service.update_session_progress(mock_db, "test-session-id", progress_data)
            
            assert result["success"] is True
            assert mock_session.current_frame == 200
            assert mock_session.total_detections == 15
            mock_db.commit.assert_called_once()


class TestAnnotationServiceIntegration:
    """Integration tests for annotation service components"""
    
    def test_service_validator_integration(self):
        """Test that service properly integrates with validators"""
        service = AnnotationService()
        
        # Test that validator is properly initialized
        assert service.validator is not None
        assert service.geometric_validator is not None
        assert service.temporal_validator is not None
        
        # Test validator integration
        annotation_data = {
            "video_id": "test-video",
            "frame_number": 100,
            "timestamp": 3.33,
            "vru_type": "pedestrian",
            "bounding_box": {"x": 100, "y": 200, "width": 50, "height": 100}
        }
        
        video_metadata = {
            "duration": 30.0,
            "fps": 30.0,
            "resolution": "1920x1080"
        }
        
        validation_result = service.validator.validate_annotation(annotation_data, video_metadata)
        assert isinstance(validation_result, ValidationResult)
    
    def test_detection_id_generation(self):
        """Test detection ID generation"""
        service = AnnotationService()
        
        detection_id1 = service._generate_detection_id("pedestrian")
        detection_id2 = service._generate_detection_id("cyclist")
        
        assert detection_id1.startswith("DET_PEDESTRIAN_")
        assert detection_id2.startswith("DET_CYCLIST_")
        assert detection_id1 != detection_id2  # Should be unique
    
    def test_annotation_to_dict_conversion(self):
        """Test annotation model to dictionary conversion"""
        service = AnnotationService()
        
        # Create mock annotation
        mock_annotation = Mock()
        mock_annotation.id = "test-id"
        mock_annotation.video_id = "video-id"
        mock_annotation.detection_id = "DET_PED_001"
        mock_annotation.frame_number = 100
        mock_annotation.timestamp = 3.33
        mock_annotation.end_timestamp = None
        mock_annotation.vru_type = "pedestrian"
        mock_annotation.bounding_box = {"x": 100, "y": 200, "width": 50, "height": 100}
        mock_annotation.occluded = False
        mock_annotation.truncated = False
        mock_annotation.difficult = False
        mock_annotation.notes = "Test annotation"
        mock_annotation.annotator = "test_user"
        mock_annotation.validated = True
        mock_annotation.created_at = datetime.utcnow()
        mock_annotation.updated_at = None
        
        result = service._annotation_to_dict(mock_annotation)
        
        assert result["id"] == "test-id"
        assert result["vru_type"] == "pedestrian"
        assert result["validated"] is True
        assert result["bounding_box"]["width"] == 50
        assert isinstance(result["created_at"], str)  # ISO format


if __name__ == "__main__":
    pytest.main([__file__, "-v"])