"""
Comprehensive Test Suite for Ground Truth Management System
SPARC Implementation - Test-Driven Development for ground truth functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import uuid
import json
import os
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import status

# Import system under test
from src.models.ground_truth_models import (
    GroundTruthValidationWorkflow, ValidationHistory, GroundTruthBatch,
    GroundTruthBatchItem, GroundTruthExport, GroundTruthQualityMetrics,
    ValidationStatus, GenerationMethod, QualityLevel
)
from src.services.ground_truth_service import GroundTruthService
from src.services.ml_generation_service import MLGenerationService
from src.routes.ground_truth_routes import router
from models import GroundTruthObject, Video, Project
from database import SessionLocal

# Test fixtures
@pytest.fixture
def db_session():
    """Create test database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up test data
        db.rollback()
        db.close()

@pytest.fixture
def test_client():
    """Create test client"""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)

@pytest.fixture
def sample_video(db_session):
    """Create sample video for testing"""
    video = Video(
        id=str(uuid.uuid4()),
        filename="test_video.mp4",
        file_path="/tmp/test_video.mp4",
        file_size=1024000,
        duration=10.0,
        fps=30.0,
        resolution="1920x1080",
        status="uploaded",
        processing_status="pending",
        ground_truth_generated=False,
        project_id=str(uuid.uuid4()),
        created_at=datetime.utcnow()
    )
    db_session.add(video)
    db_session.commit()
    return video

@pytest.fixture
def sample_ground_truth(db_session, sample_video):
    """Create sample ground truth object"""
    gt = GroundTruthObject(
        id=str(uuid.uuid4()),
        video_id=sample_video.id,
        frame_number=100,
        timestamp=3.33,
        class_label="pedestrian",
        x=150.0,
        y=200.0,
        width=80.0,
        height=160.0,
        confidence=0.85,
        validated=False,
        difficult=False,
        created_at=datetime.utcnow()
    )
    db_session.add(gt)
    db_session.commit()
    return gt

@pytest.fixture
def ground_truth_service():
    """Create ground truth service instance"""
    return GroundTruthService()

@pytest.fixture
def ml_generation_service():
    """Create ML generation service instance"""
    return MLGenerationService()

# Unit Tests for Ground Truth Models
class TestGroundTruthModels:
    """Test ground truth database models"""
    
    def test_validation_workflow_creation(self, db_session, sample_ground_truth):
        """Test creating a validation workflow"""
        # Arrange
        workflow = GroundTruthValidationWorkflow(
            id=str(uuid.uuid4()),
            ground_truth_id=sample_ground_truth.id,
            video_id=sample_ground_truth.video_id,
            generation_method=GenerationMethod.MANUAL,
            validation_status=ValidationStatus.PENDING,
            quality_level=QualityLevel.MEDIUM,
            confidence_score=0.85,
            created_at=datetime.utcnow()
        )
        
        # Act
        db_session.add(workflow)
        db_session.commit()
        
        # Assert
        retrieved = db_session.execute(select(GroundTruthValidationWorkflow).where(
            GroundTruthValidationWorkflow.id == workflow.id
        )).scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.validation_status == ValidationStatus.PENDING
        assert retrieved.generation_method == GenerationMethod.MANUAL
        assert retrieved.quality_level == QualityLevel.MEDIUM
        assert retrieved.confidence_score == 0.85
    
    def test_validation_history_tracking(self, db_session, sample_ground_truth):
        """Test validation history tracking"""
        # Arrange
        workflow = GroundTruthValidationWorkflow(
            id=str(uuid.uuid4()),
            ground_truth_id=sample_ground_truth.id,
            video_id=sample_ground_truth.video_id,
            generation_method=GenerationMethod.MANUAL,
            validation_status=ValidationStatus.PENDING,
            quality_level=QualityLevel.MEDIUM,
            created_at=datetime.utcnow()
        )
        db_session.add(workflow)
        db_session.commit()
        
        history = ValidationHistory(
            id=str(uuid.uuid4()),
            workflow_id=workflow.id,
            previous_status=ValidationStatus.PENDING,
            new_status=ValidationStatus.APPROVED,
            changed_by="test_user",
            change_reason="Approved after review",
            timestamp=datetime.utcnow()
        )
        
        # Act
        db_session.add(history)
        db_session.commit()
        
        # Assert
        retrieved = db_session.execute(select(ValidationHistory).where(
            ValidationHistory.workflow_id == workflow.id
        )).scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.previous_status == ValidationStatus.PENDING
        assert retrieved.new_status == ValidationStatus.APPROVED
        assert retrieved.changed_by == "test_user"
    
    def test_batch_processing_model(self, db_session):
        """Test batch processing model"""
        # Arrange
        batch = GroundTruthBatch(
            id=str(uuid.uuid4()),
            batch_name="Test Batch",
            description="Test batch processing",
            processing_method=GenerationMethod.AUTOMATED_ML,
            total_videos=5,
            status="created",
            created_at=datetime.utcnow()
        )
        
        # Act
        db_session.add(batch)
        db_session.commit()
        
        # Assert
        retrieved = db_session.execute(select(GroundTruthBatch).where(
            GroundTruthBatch.id == batch.id
        )).scalar_one_or_none()
        
        assert retrieved is not None
        assert retrieved.batch_name == "Test Batch"
        assert retrieved.total_videos == 5
        assert retrieved.processing_method == GenerationMethod.AUTOMATED_ML

# Unit Tests for Ground Truth Service
class TestGroundTruthService:
    """Test ground truth business logic service"""
    
    @pytest.mark.asyncio
    async def test_calculate_quality_metrics(self, ground_truth_service, sample_ground_truth, db_session):
        """Test quality metrics calculation"""
        # Act
        metrics = await ground_truth_service.calculate_quality_metrics(sample_ground_truth.id)
        
        # Assert
        assert metrics is not None
        assert "annotation_quality_score" in metrics
        assert "spatial_accuracy" in metrics
        assert "temporal_consistency" in metrics
        assert "complexity_metrics" in metrics
        assert 0.0 <= metrics["annotation_quality_score"] <= 1.0
        assert 0.0 <= metrics["spatial_accuracy"] <= 1.0
    
    def test_annotation_quality_calculation(self, ground_truth_service, sample_ground_truth):
        """Test annotation quality score calculation"""
        # Act
        quality_score = ground_truth_service._calculate_annotation_quality(sample_ground_truth)
        
        # Assert
        assert 0.0 <= quality_score <= 1.0
        # Should be high quality due to good confidence and valid bounding box
        assert quality_score > 0.7
    
    def test_spatial_accuracy_calculation(self, ground_truth_service, sample_ground_truth):
        """Test spatial accuracy calculation"""
        # Act
        spatial_accuracy = ground_truth_service._calculate_spatial_accuracy(sample_ground_truth)
        
        # Assert
        assert 0.0 <= spatial_accuracy <= 1.0
        # Should have good spatial accuracy for valid bounding box
        assert spatial_accuracy > 0.5
    
    def test_spatial_similarity_calculation(self, ground_truth_service, sample_ground_truth, db_session):
        """Test spatial similarity between ground truth objects"""
        # Arrange - create similar ground truth object
        similar_gt = GroundTruthObject(
            id=str(uuid.uuid4()),
            video_id=sample_ground_truth.video_id,
            frame_number=105,
            timestamp=3.5,
            class_label="pedestrian",
            x=155.0,  # Slightly different position
            y=205.0,
            width=75.0,
            height=155.0,
            confidence=0.80,
            validated=False,
            difficult=False
        )
        
        # Act
        similarity = ground_truth_service._calculate_spatial_similarity(sample_ground_truth, similar_gt)
        
        # Assert
        assert 0.0 <= similarity <= 1.0
        # Should have some overlap
        assert similarity > 0.0
    
    @pytest.mark.asyncio
    async def test_process_batch(self, ground_truth_service, db_session, sample_video):
        """Test batch processing functionality"""
        with patch.object(ground_truth_service, '_process_batch_item', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = None
            
            # Arrange
            batch = GroundTruthBatch(
                id=str(uuid.uuid4()),
                batch_name="Test Batch",
                processing_method=GenerationMethod.AUTOMATED_ML,
                total_videos=1,
                status="created",
                created_at=datetime.utcnow()
            )
            db_session.add(batch)
            
            batch_item = GroundTruthBatchItem(
                id=str(uuid.uuid4()),
                batch_id=batch.id,
                video_id=sample_video.id,
                status="pending",
                created_at=datetime.utcnow()
            )
            db_session.add(batch_item)
            db_session.commit()
            
            # Act
            await ground_truth_service.process_batch(batch.id)
            
            # Assert
            mock_process.assert_called_once()
    
    def test_quality_distribution_calculation(self, ground_truth_service):
        """Test quality distribution calculation"""
        # Arrange
        mock_metrics = [
            Mock(annotation_quality_score=0.9),  # High quality
            Mock(annotation_quality_score=0.6),  # Medium quality
            Mock(annotation_quality_score=0.3),  # Low quality
        ]
        
        # Act
        distribution = ground_truth_service.calculate_quality_distribution(mock_metrics)
        
        # Assert
        assert distribution["high"] == 1
        assert distribution["medium"] == 1
        assert distribution["low"] == 1
    
    def test_complexity_metrics_calculation(self, ground_truth_service):
        """Test complexity metrics calculation"""
        # Arrange
        mock_metrics = [
            Mock(
                object_size_score=0.5,
                occlusion_level=0.2,
                motion_complexity=0.3,
                background_complexity=0.4
            ),
            Mock(
                object_size_score=0.7,
                occlusion_level=0.1,
                motion_complexity=0.2,
                background_complexity=0.3
            )
        ]
        
        # Act
        complexity = ground_truth_service.calculate_complexity_metrics(mock_metrics)
        
        # Assert
        assert "average_object_size_complexity" in complexity
        assert "average_occlusion_level" in complexity
        assert "complexity_distribution" in complexity
        assert complexity["average_object_size_complexity"] == 0.6

# Unit Tests for ML Generation Service
class TestMLGenerationService:
    """Test ML-powered ground truth generation"""
    
    def test_ml_service_initialization(self, ml_generation_service):
        """Test ML service initialization"""
        # Assert
        assert ml_generation_service is not None
        assert hasattr(ml_generation_service, 'ml_available')
        assert hasattr(ml_generation_service, 'vru_classes')
        assert hasattr(ml_generation_service, 'quality_thresholds')
    
    def test_quality_level_determination(self, ml_generation_service):
        """Test quality level determination from confidence"""
        # Act & Assert
        assert ml_generation_service._determine_quality_level(0.9) == QualityLevel.HIGH
        assert ml_generation_service._determine_quality_level(0.6) == QualityLevel.MEDIUM
        assert ml_generation_service._determine_quality_level(0.4) == QualityLevel.LOW
        assert ml_generation_service._determine_quality_level(0.2) == QualityLevel.UNCERTAIN
    
    @pytest.mark.asyncio
    async def test_fallback_ground_truth_generation(self, ml_generation_service, sample_video, db_session):
        """Test fallback ground truth generation"""
        # Act
        detection_count = await ml_generation_service._generate_fallback_ground_truth(
            sample_video.id, GenerationMethod.AUTOMATED_ML
        )
        
        # Assert
        assert detection_count > 0
        
        # Verify ground truth objects were created
        created_objects = db_session.execute(select(GroundTruthObject).where(
            GroundTruthObject.video_id == sample_video.id
        )).scalars().all()
        assert len(created_objects) == detection_count
    
    def test_get_model_info(self, ml_generation_service):
        """Test model information retrieval"""
        # Act
        model_info = ml_generation_service.get_model_info()
        
        # Assert
        assert "ml_available" in model_info
        assert "model_loaded" in model_info
        assert "supported_classes" in model_info
        assert "quality_thresholds" in model_info
        assert isinstance(model_info["supported_classes"], list)
    
    @pytest.mark.asyncio
    async def test_video_validation(self, ml_generation_service):
        """Test video validation for processing"""
        # Test with non-existent file
        is_valid, message = await ml_generation_service.validate_video_for_processing("/nonexistent/video.mp4")
        assert not is_valid
        assert "not found" in message.lower()

# Integration Tests for API Routes
class TestGroundTruthAPI:
    """Test ground truth API endpoints"""
    
    def test_create_ground_truth_object(self, test_client, sample_video):
        """Test creating ground truth object via API"""
        # Arrange
        request_data = {
            "videoId": sample_video.id,
            "frameNumber": 100,
            "timestamp": 3.33,
            "classLabel": "pedestrian",
            "boundingBox": {
                "x": 150.0,
                "y": 200.0,
                "width": 80.0,
                "height": 160.0
            },
            "confidence": 0.85,
            "validated": False,
            "difficult": False,
            "generationMethod": "manual"
        }
        
        # Act
        response = test_client.post("/api/ground-truth/", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert "id" in response_data
        assert "workflow_id" in response_data
        assert response_data["status"] == "created"
    
    def test_create_validation_workflow(self, test_client, sample_ground_truth):
        """Test creating validation workflow via API"""
        # Arrange
        request_data = {
            "groundTruthId": sample_ground_truth.id,
            "assignedReviewer": "test_reviewer",
            "qualityLevel": "medium",
            "reviewNotes": "Needs review",
            "confidenceScore": 0.75
        }
        
        # Act
        response = test_client.post("/api/ground-truth/validation-workflow", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert "workflow_id" in response_data
        assert response_data["status"] == "created"
    
    def test_submit_validation_decision(self, test_client, db_session, sample_ground_truth):
        """Test submitting validation decision via API"""
        # Arrange - create workflow first
        workflow = GroundTruthValidationWorkflow(
            id=str(uuid.uuid4()),
            ground_truth_id=sample_ground_truth.id,
            video_id=sample_ground_truth.video_id,
            generation_method=GenerationMethod.MANUAL,
            validation_status=ValidationStatus.PENDING,
            created_at=datetime.utcnow()
        )
        db_session.add(workflow)
        db_session.commit()
        
        request_data = {
            "validationStatus": "approved",
            "reviewNotes": "Looks good",
            "qualityLevel": "high",
            "reviewerId": "test_reviewer"
        }
        
        # Act
        response = test_client.put(f"/api/ground-truth/validation-workflow/{workflow.id}/review", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["status"] == "approved"
    
    def test_generate_automated_ground_truth(self, test_client, sample_video):
        """Test automated ground truth generation via API"""
        # Act
        response = test_client.post(
            f"/api/ground-truth/generate/video/{sample_video.id}",
            params={"confidence_threshold": 0.5, "processing_method": "automated_ml"}
        )
        
        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        response_data = response.json()
        assert response_data["video_id"] == sample_video.id
        assert response_data["status"] == "processing"
    
    def test_create_batch_processing(self, test_client, sample_video):
        """Test batch processing creation via API"""
        # Arrange
        request_data = {
            "batchName": "Test Batch",
            "videoIds": [sample_video.id],
            "processingMethod": "automated_ml",
            "description": "Test batch processing"
        }
        
        # Act
        response = test_client.post("/api/ground-truth/batch", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert "batch_id" in response_data
        assert response_data["total_videos"] == 1
    
    def test_create_export_job(self, test_client):
        """Test export job creation via API"""
        # Arrange
        request_data = {
            "exportName": "Test Export",
            "formatType": "json",
            "description": "Test export job"
        }
        
        # Act
        response = test_client.post("/api/ground-truth/export", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        response_data = response.json()
        assert "export_id" in response_data
        assert response_data["format"] == "json"

# Performance Tests
class TestGroundTruthPerformance:
    """Test performance aspects of ground truth system"""
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, ground_truth_service, db_session):
        """Test batch processing performance with multiple videos"""
        # Arrange - create multiple videos
        video_ids = []
        for i in range(5):
            video = Video(
                id=str(uuid.uuid4()),
                filename=f"test_video_{i}.mp4",
                file_path=f"/tmp/test_video_{i}.mp4",
                status="uploaded",
                processing_status="pending",
                project_id=str(uuid.uuid4()),
                created_at=datetime.utcnow()
            )
            db_session.add(video)
            video_ids.append(video.id)
        
        db_session.commit()
        
        # Create batch
        batch = GroundTruthBatch(
            id=str(uuid.uuid4()),
            batch_name="Performance Test Batch",
            processing_method=GenerationMethod.AUTOMATED_ML,
            total_videos=len(video_ids),
            status="created",
            created_at=datetime.utcnow()
        )
        db_session.add(batch)
        
        # Create batch items
        for video_id in video_ids:
            item = GroundTruthBatchItem(
                id=str(uuid.uuid4()),
                batch_id=batch.id,
                video_id=video_id,
                status="pending",
                created_at=datetime.utcnow()
            )
            db_session.add(item)
        
        db_session.commit()
        
        # Mock the processing to avoid actual ML inference
        with patch.object(ground_truth_service, '_process_batch_item', new_callable=AsyncMock):
            start_time = datetime.utcnow()
            
            # Act
            await ground_truth_service.process_batch(batch.id)
            
            # Assert
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            
            # Should complete within reasonable time (mocked, so very fast)
            assert processing_time < 10.0
    
    def test_quality_metrics_calculation_performance(self, ground_truth_service):
        """Test performance of quality metrics calculation"""
        # Arrange - create mock ground truth object
        mock_gt = Mock()
        mock_gt.confidence = 0.85
        mock_gt.width = 80.0
        mock_gt.height = 160.0
        mock_gt.x = 150.0
        mock_gt.y = 200.0
        mock_gt.class_label = "pedestrian"
        
        start_time = datetime.utcnow()
        
        # Act - calculate quality metrics multiple times
        for _ in range(100):
            quality_score = ground_truth_service._calculate_annotation_quality(mock_gt)
            spatial_accuracy = ground_truth_service._calculate_spatial_accuracy(mock_gt)
        
        # Assert
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()
        
        # Should be fast for 100 calculations
        assert processing_time < 1.0

# Error Handling Tests
class TestGroundTruthErrorHandling:
    """Test error handling in ground truth system"""
    
    def test_create_ground_truth_with_invalid_video_id(self, test_client):
        """Test creating ground truth with non-existent video"""
        # Arrange
        request_data = {
            "videoId": str(uuid.uuid4()),  # Non-existent video
            "timestamp": 3.33,
            "classLabel": "pedestrian",
            "boundingBox": {"x": 150.0, "y": 200.0, "width": 80.0, "height": 160.0}
        }
        
        # Act
        response = test_client.post("/api/ground-truth/", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"]
    
    def test_create_ground_truth_with_invalid_class_label(self, test_client, sample_video):
        """Test creating ground truth with invalid class label"""
        # Arrange
        request_data = {
            "videoId": sample_video.id,
            "timestamp": 3.33,
            "classLabel": "invalid_class",
            "boundingBox": {"x": 150.0, "y": 200.0, "width": 80.0, "height": 160.0}
        }
        
        # Act
        response = test_client.post("/api/ground-truth/", json=request_data)
        
        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_validation_decision_with_invalid_workflow(self, test_client):
        """Test validation decision with non-existent workflow"""
        # Arrange
        fake_workflow_id = str(uuid.uuid4())
        request_data = {
            "validationStatus": "approved",
            "reviewNotes": "Test",
            "reviewerId": "test_reviewer"
        }
        
        # Act
        response = test_client.put(
            f"/api/ground-truth/validation-workflow/{fake_workflow_id}/review",
            json=request_data
        )
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_batch_processing_with_invalid_video(self, ground_truth_service, db_session):
        """Test batch processing with invalid video"""
        # Arrange - create batch with non-existent video
        batch = GroundTruthBatch(
            id=str(uuid.uuid4()),
            batch_name="Error Test Batch",
            processing_method=GenerationMethod.AUTOMATED_ML,
            total_videos=1,
            status="created",
            created_at=datetime.utcnow()
        )
        db_session.add(batch)
        
        batch_item = GroundTruthBatchItem(
            id=str(uuid.uuid4()),
            batch_id=batch.id,
            video_id=str(uuid.uuid4()),  # Non-existent video
            status="pending",
            created_at=datetime.utcnow()
        )
        db_session.add(batch_item)
        db_session.commit()
        
        # Act
        await ground_truth_service.process_batch(batch.id)
        
        # Assert - batch should handle error gracefully
        updated_batch = db_session.execute(select(GroundTruthBatch).where(
            GroundTruthBatch.id == batch.id
        )).scalar_one_or_none()
        assert updated_batch.status in ["completed_with_errors", "failed"]

# Data Validation Tests
class TestGroundTruthDataValidation:
    """Test data validation in ground truth system"""
    
    def test_bounding_box_validation(self, test_client, sample_video):
        """Test bounding box validation"""
        # Test negative coordinates
        request_data = {
            "videoId": sample_video.id,
            "timestamp": 3.33,
            "classLabel": "pedestrian",
            "boundingBox": {"x": -10.0, "y": -20.0, "width": 80.0, "height": 160.0}
        }
        
        response = test_client.post("/api/ground-truth/", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test zero/negative dimensions
        request_data["boundingBox"] = {"x": 150.0, "y": 200.0, "width": 0.0, "height": 160.0}
        response = test_client.post("/api/ground-truth/", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_confidence_score_validation(self, test_client, sample_video):
        """Test confidence score validation"""
        # Test confidence > 1.0
        request_data = {
            "videoId": sample_video.id,
            "timestamp": 3.33,
            "classLabel": "pedestrian",
            "boundingBox": {"x": 150.0, "y": 200.0, "width": 80.0, "height": 160.0},
            "confidence": 1.5
        }
        
        response = test_client.post("/api/ground-truth/", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Test negative confidence
        request_data["confidence"] = -0.1
        response = test_client.post("/api/ground-truth/", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_timestamp_validation(self, test_client, sample_video):
        """Test timestamp validation"""
        # Test negative timestamp
        request_data = {
            "videoId": sample_video.id,
            "timestamp": -1.0,
            "classLabel": "pedestrian",
            "boundingBox": {"x": 150.0, "y": 200.0, "width": 80.0, "height": 160.0}
        }
        
        response = test_client.post("/api/ground-truth/", json=request_data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])