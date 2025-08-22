"""
Detection Pipeline API Tests
Tests for detection endpoints, event storage, and status updates
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.database import SessionLocal
from backend.models import DetectionEvent, TestSession, Video, Project
from backend.schemas import DetectionEvent as DetectionEventSchema


class TestDetectionPipelineAPI:
    """Test suite for detection pipeline API functionality"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def async_client(self):
        """Create async test client"""
        return AsyncClient(app=app, base_url="http://test")

    @pytest.fixture
    def db_session(self):
        """Create test database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    @pytest.fixture
    def test_project(self, db_session):
        """Create test project"""
        project = Project(
            name="Detection Test Project",
            description="Project for detection pipeline testing",
            camera_model="YOLO Camera",
            camera_view="Front-facing VRU",
            signal_type="GPIO"
        )
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    @pytest.fixture
    def test_video(self, db_session, test_project):
        """Create test video"""
        video = Video(
            filename="detection_test.mp4",
            file_path="/uploads/detection_test.mp4",
            project_id=test_project.id,
            duration=30.0,
            fps=30.0,
            resolution="1920x1080"
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)
        return video

    @pytest.fixture
    def test_session(self, db_session, test_project, test_video):
        """Create test session"""
        session = TestSession(
            name="Detection Pipeline Test",
            project_id=test_project.id,
            video_id=test_video.id,
            tolerance_ms=100,
            status="created"
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        return session

    @pytest.mark.asyncio
    async def test_start_detection_success(self, async_client, test_session):
        """Test successful detection start"""
        start_data = {
            "session_id": test_session.id,
            "detection_config": {
                "model": "yolov8n",
                "confidence_threshold": 0.5,
                "iou_threshold": 0.45,
                "classes": ["person", "bicycle", "car"]
            }
        }
        
        with patch('backend.services.detection_pipeline_service.start_detection') as mock_start:
            mock_start.return_value = {"status": "started", "task_id": "det-123"}
            
            response = await async_client.post(
                "/api/detection/start",
                json=start_data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "started"
        assert "task_id" in result

    @pytest.mark.asyncio
    async def test_start_detection_invalid_session(self, async_client):
        """Test detection start with invalid session ID"""
        start_data = {
            "session_id": "invalid-session-id",
            "detection_config": {
                "model": "yolov8n",
                "confidence_threshold": 0.5
            }
        }
        
        response = await async_client.post("/api/detection/start", json=start_data)
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_stop_detection_success(self, async_client, test_session):
        """Test successful detection stop"""
        stop_data = {
            "session_id": test_session.id,
            "task_id": "det-123"
        }
        
        with patch('backend.services.detection_pipeline_service.stop_detection') as mock_stop:
            mock_stop.return_value = {"status": "stopped", "detections_processed": 45}
            
            response = await async_client.post(
                "/api/detection/stop",
                json=stop_data
            )
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "stopped"
        assert result["detections_processed"] == 45

    @pytest.mark.asyncio
    async def test_detection_status_check(self, async_client, test_session):
        """Test detection status checking"""
        with patch('backend.services.detection_pipeline_service.get_detection_status') as mock_status:
            mock_status.return_value = {
                "status": "running",
                "progress": 0.75,
                "frames_processed": 750,
                "total_frames": 1000,
                "detections_count": 23,
                "current_fps": 28.5
            }
            
            response = await async_client.get(f"/api/detection/status/{test_session.id}")
        
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "running"
        assert result["progress"] == 0.75
        assert result["detections_count"] == 23

    @pytest.mark.asyncio
    async def test_detection_event_creation(self, async_client, test_session, db_session):
        """Test detection event creation through API"""
        detection_data = {
            "session_id": test_session.id,
            "timestamp": 15.5,
            "frame_number": 465,
            "detections": [
                {
                    "class_label": "person",
                    "confidence": 0.85,
                    "bbox": {"x": 100, "y": 150, "width": 80, "height": 200}
                },
                {
                    "class_label": "bicycle",
                    "confidence": 0.72,
                    "bbox": {"x": 200, "y": 300, "width": 120, "height": 80}
                }
            ]
        }
        
        response = await async_client.post(
            "/api/detection/events",
            json=detection_data
        )
        
        assert response.status_code == 201
        result = response.json()
        assert len(result["events"]) == 2
        assert result["events"][0]["class_label"] == "person"
        assert result["events"][1]["class_label"] == "bicycle"

    @pytest.mark.asyncio
    async def test_detection_event_validation(self, async_client, test_session):
        """Test detection event data validation"""
        invalid_detection_data = {
            "session_id": test_session.id,
            "timestamp": "invalid_timestamp",  # Should be float
            "detections": [
                {
                    "class_label": "person",
                    "confidence": 1.5,  # Invalid confidence > 1.0
                    "bbox": {"x": 100, "y": 150}  # Missing width/height
                }
            ]
        }
        
        response = await async_client.post(
            "/api/detection/events",
            json=invalid_detection_data
        )
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("timestamp" in str(error) for error in errors)
        assert any("confidence" in str(error) for error in errors)

    @pytest.mark.asyncio
    async def test_get_detection_events(self, async_client, test_session, db_session):
        """Test retrieving detection events"""
        # Create test detection events
        events = [
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=10.0,
                frame_number=300,
                class_label="person",
                confidence=0.9,
                x=100, y=150, width=80, height=200
            ),
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=15.5,
                frame_number=465,
                class_label="car",
                confidence=0.8,
                x=300, y=200, width=150, height=100
            )
        ]
        
        for event in events:
            db_session.add(event)
        db_session.commit()
        
        response = await async_client.get(f"/api/detection/events/{test_session.id}")
        
        assert response.status_code == 200
        result = response.json()
        assert len(result["events"]) == 2
        assert result["total_count"] == 2

    @pytest.mark.asyncio
    async def test_detection_events_filtering(self, async_client, test_session, db_session):
        """Test filtering detection events by various criteria"""
        # Create detection events with different classes and confidence levels
        events = [
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=5.0,
                class_label="person",
                confidence=0.9,
                x=100, y=100, width=50, height=100
            ),
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=10.0,
                class_label="person",
                confidence=0.6,
                x=200, y=100, width=50, height=100
            ),
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=15.0,
                class_label="car",
                confidence=0.8,
                x=300, y=200, width=100, height=60
            )
        ]
        
        for event in events:
            db_session.add(event)
        db_session.commit()
        
        # Filter by class
        response = await async_client.get(
            f"/api/detection/events/{test_session.id}",
            params={"class_label": "person"}
        )
        assert response.status_code == 200
        result = response.json()
        assert len(result["events"]) == 2
        
        # Filter by confidence threshold
        response = await async_client.get(
            f"/api/detection/events/{test_session.id}",
            params={"min_confidence": 0.8}
        )
        assert response.status_code == 200
        result = response.json()
        assert len(result["events"]) == 2  # 0.9 and 0.8 confidence

    @pytest.mark.asyncio
    async def test_detection_analytics(self, async_client, test_session, db_session):
        """Test detection analytics endpoint"""
        # Create sample detection events
        events = [
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=i * 2.0,
                class_label="person" if i % 2 == 0 else "car",
                confidence=0.8 + (i % 3) * 0.1,
                x=100 + i * 10, y=100, width=50, height=100
            )
            for i in range(10)
        ]
        
        for event in events:
            db_session.add(event)
        db_session.commit()
        
        response = await async_client.get(f"/api/detection/analytics/{test_session.id}")
        
        assert response.status_code == 200
        result = response.json()
        assert "total_detections" in result
        assert "class_distribution" in result
        assert "confidence_stats" in result
        assert "temporal_distribution" in result
        assert result["total_detections"] == 10

    @pytest.mark.asyncio
    async def test_real_time_detection_websocket(self, async_client, test_session):
        """Test real-time detection updates via WebSocket"""
        # This would typically use a WebSocket test client
        # For now, we'll test the HTTP endpoint that would feed the WebSocket
        
        detection_update = {
            "session_id": test_session.id,
            "type": "detection_update",
            "data": {
                "current_frame": 500,
                "detections_in_frame": 3,
                "processing_fps": 25.0,
                "total_detections": 45
            }
        }
        
        with patch('backend.socketio_server.emit_detection_update') as mock_emit:
            response = await async_client.post(
                "/api/detection/realtime/update",
                json=detection_update
            )
            
            assert response.status_code == 200
            mock_emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_detection_model_configuration(self, async_client):
        """Test detection model configuration endpoints"""
        # Get available models
        response = await async_client.get("/api/detection/models")
        assert response.status_code == 200
        result = response.json()
        assert "models" in result
        assert len(result["models"]) > 0
        
        # Update model configuration
        config_data = {
            "model": "yolov8s",
            "confidence_threshold": 0.6,
            "iou_threshold": 0.5,
            "max_detections": 100,
            "classes": ["person", "bicycle", "car", "motorcycle"]
        }
        
        response = await async_client.put(
            "/api/detection/config",
            json=config_data
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_detection_export(self, async_client, test_session, db_session):
        """Test detection results export functionality"""
        # Create sample detection events
        events = [
            DetectionEvent(
                test_session_id=test_session.id,
                timestamp=i * 1.0,
                frame_number=i * 30,
                class_label="person",
                confidence=0.8,
                x=100, y=100, width=50, height=100
            )
            for i in range(5)
        ]
        
        for event in events:
            db_session.add(event)
        db_session.commit()
        
        # Test CSV export
        response = await async_client.get(
            f"/api/detection/export/{test_session.id}",
            params={"format": "csv"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        
        # Test JSON export
        response = await async_client.get(
            f"/api/detection/export/{test_session.id}",
            params={"format": "json"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @pytest.mark.performance
    async def test_detection_pipeline_performance(self, async_client, test_session):
        """Test detection pipeline performance under load"""
        # Simulate high-frequency detection events
        detection_batches = []
        for batch in range(10):
            batch_data = {
                "session_id": test_session.id,
                "timestamp": batch * 0.1,
                "frame_number": batch * 3,
                "detections": [
                    {
                        "class_label": "person",
                        "confidence": 0.8,
                        "bbox": {"x": 100 + batch * 10, "y": 150, "width": 80, "height": 200}
                    }
                ]
            }
            detection_batches.append(batch_data)
        
        # Send concurrent detection events
        tasks = [
            async_client.post("/api/detection/events", json=batch)
            for batch in detection_batches
        ]
        
        start_time = asyncio.get_event_loop().time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = asyncio.get_event_loop().time()
        
        # All requests should complete within reasonable time
        assert end_time - start_time < 2.0
        
        # Check that all requests succeeded
        success_count = sum(1 for r in responses if not isinstance(r, Exception) and r.status_code == 201)
        assert success_count == len(detection_batches)

    @pytest.mark.asyncio
    async def test_detection_error_recovery(self, async_client, test_session):
        """Test detection pipeline error recovery"""
        # Test recovery from model loading failure
        with patch('backend.services.detection_pipeline_service.load_model', side_effect=Exception("Model load failed")):
            start_data = {
                "session_id": test_session.id,
                "detection_config": {"model": "invalid_model"}
            }
            
            response = await async_client.post("/api/detection/start", json=start_data)
            assert response.status_code == 500
            assert "Model load failed" in response.json()["detail"]
        
        # Test recovery and successful restart
        with patch('backend.services.detection_pipeline_service.start_detection') as mock_start:
            mock_start.return_value = {"status": "started", "task_id": "det-456"}
            
            start_data = {
                "session_id": test_session.id,
                "detection_config": {"model": "yolov8n"}
            }
            
            response = await async_client.post("/api/detection/start", json=start_data)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_detection_memory_management(self, async_client, test_session):
        """Test detection pipeline memory management"""
        # Test memory usage monitoring
        response = await async_client.get("/api/detection/memory-stats")
        assert response.status_code == 200
        result = response.json()
        assert "memory_usage_mb" in result
        assert "gpu_memory_mb" in result
        
        # Test memory cleanup
        response = await async_client.post("/api/detection/cleanup")
        assert response.status_code == 200

    @pytest.mark.security
    async def test_detection_api_security(self, async_client, test_session):
        """Test detection API security measures"""
        # Test SQL injection protection
        malicious_session_id = "'; DROP TABLE detection_events; --"
        response = await async_client.get(f"/api/detection/events/{malicious_session_id}")
        assert response.status_code == 400  # Bad request due to invalid UUID format
        
        # Test XSS protection in class labels
        xss_detection_data = {
            "session_id": test_session.id,
            "timestamp": 1.0,
            "detections": [
                {
                    "class_label": "<script>alert('xss')</script>",
                    "confidence": 0.8,
                    "bbox": {"x": 100, "y": 150, "width": 80, "height": 200}
                }
            ]
        }
        
        response = await async_client.post("/api/detection/events", json=xss_detection_data)
        # Should either sanitize or reject
        assert response.status_code in [201, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])