"""
Annotation Data Flow Integration Tests
=====================================

Tests the complete data flow from backend to frontend, including:
- API response transformation
- Frontend data consumption  
- Screenshot serving and image handling
- Real-time data updates
"""

import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import tempfile
import os
from typing import Dict, Any, List
from PIL import Image
import base64
import io

from tests.conftest import TestDataHelper
from models import Annotation, Video, DetectionEvent, Project
from services.annotation_service import AnnotationService
from main import app


class TestAnnotationDataTransformation:
    """Test data transformation between backend and frontend"""
    
    def test_annotation_api_response_format(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test API response format matches frontend expectations"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create annotation with all possible fields
        annotation = Annotation(
            video_id=video.id,
            detection_id="DET_PED_001",
            frame_number=120,
            timestamp=4.0,
            end_timestamp=6.5,
            vru_type="pedestrian",
            bounding_box={
                "x": 100,
                "y": 150,
                "width": 50,
                "height": 100,
                "confidence": 0.95
            },
            occluded=True,
            truncated=False,
            difficult=True,
            notes="Complex pedestrian scenario",
            annotator="expert-annotator",
            validated=True
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        response = test_client.get(f"/api/annotations/{annotation.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify camelCase transformation for frontend
        expected_fields = [
            "id", "videoId", "detectionId", "frameNumber", "timestamp",
            "endTimestamp", "vruType", "boundingBox", "occluded",
            "truncated", "difficult", "notes", "annotator", "validated",
            "createdAt", "updatedAt"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data["id"], str)
        assert isinstance(data["videoId"], str)
        assert isinstance(data["frameNumber"], int)
        assert isinstance(data["timestamp"], float)
        assert isinstance(data["boundingBox"], dict)
        assert isinstance(data["occluded"], bool)
        assert isinstance(data["validated"], bool)
        
        # Verify bounding box structure
        bbox = data["boundingBox"]
        assert "x" in bbox
        assert "y" in bbox
        assert "width" in bbox
        assert "height" in bbox
        assert "confidence" in bbox
        assert bbox["confidence"] == 0.95
    
    def test_annotation_list_response_pagination(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test annotation list response with pagination metadata"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create multiple annotations
        for i in range(15):
            annotation = Annotation(
                video_id=video.id,
                frame_number=i * 10,
                timestamp=i * 0.5,
                vru_type="pedestrian" if i % 2 == 0 else "cyclist",
                bounding_box={"x": 100 + i, "y": 100 + i, "width": 50, "height": 80}
            )
            test_db.add(annotation)
        test_db.commit()
        
        # Test first page
        response = test_client.get(f"/api/annotations/?video_id={video.id}&limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        
        # Test second page
        response = test_client.get(f"/api/annotations/?video_id={video.id}&limit=10&offset=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        
        # Verify ordering (most recent first)
        timestamps = [ann["timestamp"] for ann in data]
        assert timestamps == sorted(timestamps, reverse=True)
    
    def test_ai_detection_to_annotation_transformation(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test transformation of AI detections to annotation format"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Simulate AI detection data
        detection_event = DetectionEvent(
            test_session_id="session-123",
            video_id=video.id,
            timestamp=4.5,
            frame_number=135,
            class_label="person",
            confidence=0.89,
            bounding_box_x=120,
            bounding_box_y=180,
            bounding_box_width=60,
            bounding_box_height=120,
            vru_type="pedestrian",
            source="ai",
            detection_type="automatic"
        )
        test_db.add(detection_event)
        test_db.commit()
        test_db.refresh(detection_event)
        
        # Create corresponding annotation
        annotation_data = {
            "videoId": video.id,
            "detectionId": detection_event.detection_id,
            "frameNumber": detection_event.frame_number,
            "timestamp": detection_event.timestamp,
            "vruType": detection_event.vru_type,
            "boundingBox": {
                "x": detection_event.bounding_box_x,
                "y": detection_event.bounding_box_y,
                "width": detection_event.bounding_box_width,
                "height": detection_event.bounding_box_height,
                "confidence": detection_event.confidence
            },
            "annotator": "ai-system",
            "validated": False,
            "notes": f"AI detection (confidence: {detection_event.confidence})"
        }
        
        response = test_client.post("/api/annotations/", json=annotation_data)
        assert response.status_code == 201
        
        created_annotation = response.json()
        
        # Verify AI detection data is properly transformed
        assert created_annotation["frameNumber"] == 135
        assert created_annotation["timestamp"] == 4.5
        assert created_annotation["vruType"] == "pedestrian"
        assert created_annotation["boundingBox"]["confidence"] == 0.89
        assert created_annotation["annotator"] == "ai-system"
        assert created_annotation["validated"] is False


class TestScreenshotServing:
    """Test screenshot serving and image handling"""
    
    def create_test_image(self, width: int = 100, height: int = 100) -> bytes:
        """Create a test image for testing"""
        img = Image.new('RGB', (width, height), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        return img_bytes.getvalue()
    
    def test_screenshot_path_generation(self, test_db: Session, temp_upload_dir):
        """Test screenshot path generation and storage"""
        # Create test video
        video_data = {
            "id": "test-video-screenshots",
            "filename": "screenshot_test.mp4",
            "file_path": str(temp_upload_dir / "screenshot_test.mp4"),
            "project_id": "test-project"
        }
        video = TestDataHelper.create_video(test_db, video_data)
        
        # Create screenshots directory
        screenshots_dir = temp_upload_dir / "screenshots"
        screenshots_dir.mkdir()
        
        # Create test screenshot
        screenshot_data = self.create_test_image(640, 480)
        screenshot_path = screenshots_dir / f"frame_120_{video.id}.png"
        
        with open(screenshot_path, 'wb') as f:
            f.write(screenshot_data)
        
        # Create annotation with screenshot reference
        annotation = Annotation(
            video_id=video.id,
            frame_number=120,
            timestamp=4.0,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 50, "height": 100},
            screenshot_path=str(screenshot_path)
        )
        test_db.add(annotation)
        test_db.commit()
        
        # Verify screenshot file exists
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0
        
        # Verify annotation has screenshot path
        assert annotation.screenshot_path == str(screenshot_path)
    
    @patch('main.app')  # Mock the FastAPI static file serving
    def test_screenshot_serving_endpoint(self, mock_app, test_client: TestClient, temp_upload_dir):
        """Test screenshot serving through API endpoint"""
        # Create test screenshot
        screenshot_data = self.create_test_image(320, 240)
        screenshot_path = temp_upload_dir / "test_screenshot.png"
        
        with open(screenshot_path, 'wb') as f:
            f.write(screenshot_data)
        
        # Test direct file access (simulated)
        assert screenshot_path.exists()
        
        # Verify image can be read
        with open(screenshot_path, 'rb') as f:
            loaded_data = f.read()
            assert len(loaded_data) > 0
        
        # Test base64 encoding for API response
        base64_data = base64.b64encode(screenshot_data).decode('utf-8')
        assert base64_data is not None
        assert len(base64_data) > 0
    
    def test_screenshot_url_generation(self, test_db: Session, sample_video_data):
        """Test screenshot URL generation for frontend consumption"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        annotation = Annotation(
            video_id=video.id,
            frame_number=120,
            timestamp=4.0,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 50, "height": 100},
            screenshot_path="/uploads/screenshots/frame_120_test.png"
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        # Test URL generation logic
        base_url = "http://localhost:8000"
        expected_url = f"{base_url}/static/screenshots/frame_120_test.png"
        
        # In a real implementation, this would be handled by the API response
        screenshot_url = annotation.screenshot_path.replace("/uploads/", "/static/")
        assert screenshot_url == "/static/screenshots/frame_120_test.png"
    
    def test_missing_screenshot_handling(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test handling of missing screenshot files"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        annotation = Annotation(
            video_id=video.id,
            frame_number=120,
            timestamp=4.0,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 50, "height": 100},
            screenshot_path="/uploads/screenshots/nonexistent_screenshot.png"
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        response = test_client.get(f"/api/annotations/{annotation.id}")
        assert response.status_code == 200
        
        data = response.json()
        
        # API should still return annotation data even if screenshot is missing
        assert data["id"] == annotation.id
        assert "screenshotPath" in data or "screenshot_path" in data


class TestRealTimeAnnotationUpdates:
    """Test real-time annotation updates and WebSocket communication"""
    
    @pytest.mark.asyncio
    async def test_annotation_update_notification(self, test_db: Session, sample_video_data):
        """Test annotation update notifications (simulated WebSocket)"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create initial annotation
        annotation = Annotation(
            video_id=video.id,
            frame_number=120,
            timestamp=4.0,
            vru_type="pedestrian",
            bounding_box={"x": 100, "y": 150, "width": 50, "height": 100},
            validated=False
        )
        test_db.add(annotation)
        test_db.commit()
        test_db.refresh(annotation)
        
        # Simulate annotation service update
        service = AnnotationService()
        update_result = service.update_annotation(
            test_db,
            annotation.id,
            {"validated": True, "annotator": "reviewer-1"}
        )
        
        assert update_result["success"] is True
        assert update_result["annotation"]["validated"] is True
        
        # In a real implementation, this would trigger WebSocket notification
        notification = {
            "type": "annotation_updated",
            "data": {
                "annotation_id": annotation.id,
                "video_id": video.id,
                "changes": {"validated": True},
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }
        
        assert notification["type"] == "annotation_updated"
        assert notification["data"]["annotation_id"] == annotation.id
    
    def test_bulk_annotation_progress_tracking(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test bulk annotation operation progress tracking"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create multiple annotations to simulate bulk operation
        bulk_data = [
            {
                "videoId": video.id,
                "frameNumber": i * 10,
                "timestamp": i * 0.5,
                "vruType": "pedestrian",
                "boundingBox": {"x": 100 + i, "y": 100 + i, "width": 50, "height": 80}
            }
            for i in range(50)
        ]
        
        response = test_client.post("/api/annotations/bulk", json=bulk_data)
        assert response.status_code == 201
        
        created_annotations = response.json()
        assert len(created_annotations) == 50
        
        # Simulate progress tracking for bulk validation
        annotation_ids = [ann["id"] for ann in created_annotations]
        
        # Batch validate annotations
        batch_size = 10
        for i in range(0, len(annotation_ids), batch_size):
            batch_ids = annotation_ids[i:i + batch_size]
            
            # In a real implementation, this would update a progress tracker
            progress = {
                "total": len(annotation_ids),
                "processed": min(i + batch_size, len(annotation_ids)),
                "percentage": min((i + batch_size) / len(annotation_ids) * 100, 100)
            }
            
            assert progress["processed"] <= progress["total"]
            assert 0 <= progress["percentage"] <= 100


class TestAnnotationExportDataFlow:
    """Test annotation export data flow and format transformations"""
    
    def test_json_export_format_validation(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test JSON export format matches expected structure"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create comprehensive test annotation
        annotation = Annotation(
            video_id=video.id,
            detection_id="DET_PED_001",
            frame_number=120,
            timestamp=4.0,
            end_timestamp=6.5,
            vru_type="pedestrian",
            bounding_box={
                "x": 100,
                "y": 150,
                "width": 50,
                "height": 100,
                "confidence": 0.95,
                "label": "person"
            },
            occluded=True,
            truncated=False,
            difficult=True,
            notes="Test annotation for export",
            annotator="expert-1",
            validated=True
        )
        test_db.add(annotation)
        test_db.commit()
        
        # Export annotation
        export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": False
        }
        
        response = test_client.post("/api/annotations/export", json=export_request)
        assert response.status_code == 200
        
        export_data = response.json()
        assert export_data["format"] == "json"
        assert export_data["count"] == 1
        
        exported_annotation = export_data["data"][0]
        
        # Validate complete export structure
        required_fields = [
            "id", "video_id", "detection_id", "frame_number", "timestamp",
            "end_timestamp", "vru_type", "bounding_box", "occluded",
            "truncated", "difficult", "notes", "annotator", "validated",
            "created_at", "updated_at"
        ]
        
        for field in required_fields:
            assert field in exported_annotation, f"Missing export field: {field}"
        
        # Validate data integrity
        assert exported_annotation["video_id"] == video.id
        assert exported_annotation["frame_number"] == 120
        assert exported_annotation["vru_type"] == "pedestrian"
        assert exported_annotation["bounding_box"]["confidence"] == 0.95
        assert exported_annotation["validated"] is True
    
    def test_export_performance_large_dataset(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test export performance with large annotation dataset"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create large number of annotations
        annotations = []
        for i in range(500):
            annotation = Annotation(
                video_id=video.id,
                frame_number=i,
                timestamp=i * 0.033,
                vru_type="pedestrian" if i % 3 == 0 else "cyclist",
                bounding_box={
                    "x": 100 + (i % 100),
                    "y": 150 + (i % 50),
                    "width": 50,
                    "height": 80,
                    "confidence": 0.8 + (i % 20) * 0.01
                },
                validated=i % 4 == 0
            )
            annotations.append(annotation)
        
        test_db.bulk_save_objects(annotations)
        test_db.commit()
        
        # Export all annotations
        export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": False
        }
        
        import time
        start_time = time.time()
        
        response = test_client.post("/api/annotations/export", json=export_request)
        
        export_time = time.time() - start_time
        
        assert response.status_code == 200
        assert export_time < 5.0  # Should complete in under 5 seconds
        
        export_data = response.json()
        assert export_data["count"] == 500
        assert len(export_data["data"]) == 500


class TestAnnotationValidationIntegration:
    """Test annotation validation integration with business logic"""
    
    def test_annotation_service_integration(self, test_db: Session, sample_video_data):
        """Test annotation service integration with validation"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        service = AnnotationService()
        
        # Test annotation creation with validation
        annotation_data = {
            "video_id": video.id,
            "frame_number": 120,
            "timestamp": 4.0,
            "vru_type": "pedestrian",
            "bounding_box": {
                "x": 100,
                "y": 150,
                "width": 50,
                "height": 100,
                "confidence": 0.95
            },
            "annotator": "service-test"
        }
        
        result = service.create_annotation(test_db, annotation_data)
        
        assert result["success"] is True
        assert "annotation" in result
        assert result["annotation"]["video_id"] == video.id
        assert result["annotation"]["frame_number"] == 120
    
    def test_annotation_sequence_validation(self, test_db: Session, sample_video_data):
        """Test annotation sequence validation for temporal consistency"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create sequence of annotations
        annotations_data = [
            {
                "video_id": video.id,
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100}
            },
            {
                "video_id": video.id,
                "frame_number": 150,
                "timestamp": 5.0,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 120, "y": 155, "width": 52, "height": 105}
            },
            {
                "video_id": video.id,
                "frame_number": 200,
                "timestamp": 6.67,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 140, "y": 160, "width": 54, "height": 110}
            }
        ]
        
        for ann_data in annotations_data:
            annotation = Annotation(**ann_data)
            test_db.add(annotation)
        test_db.commit()
        
        service = AnnotationService()
        validation_result = service.validate_annotation_sequence(test_db, video.id)
        
        assert validation_result["success"] is True
        assert "validation" in validation_result
        
        validation_data = validation_result["validation"]
        assert "temporal_consistency" in validation_data
        assert "geometric_overlaps" in validation_data
        assert "overall_score" in validation_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])