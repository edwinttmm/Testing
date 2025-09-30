"""
Data Flow Validation Tests for Ground Truth System
=================================================

This module provides comprehensive data flow validation testing to ensure
data consistency across all system layers (frontend → API → service → database).

Test Coverage:
- API request/response validation
- Service layer data transformation
- Database persistence integrity
- Cross-layer data consistency
- Schema validation and type checking
- JSON serialization/deserialization

Author: QA Specialist  
Date: 2024-09-29
"""

import pytest
import json
import uuid
from datetime import datetime
from typing import Dict, Any
from pydantic import ValidationError

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from database import SessionLocal
from models import Video, GroundTruthObject, DetectionEvent, Project
from schemas import GroundTruthResponse, VideoFile
from services.ground_truth_service import GroundTruthService

class DataFlowValidator:
    """Validates data consistency across all system layers"""
    
    def __init__(self):
        self.test_client = TestClient(app)
        self.service = GroundTruthService()
    
    def validate_api_to_service_flow(self, api_data: Dict[str, Any], 
                                   service_result: Any) -> Dict[str, Any]:
        """Validate data transformation from API to service layer"""
        validation_results = {
            "passed": True,
            "errors": [],
            "warnings": []
        }
        
        # Check data type consistency
        if "confidence" in api_data:
            service_confidence = getattr(service_result, 'confidence', None)
            if service_confidence is not None:
                if abs(float(api_data["confidence"]) - float(service_confidence)) > 0.001:
                    validation_results["errors"].append(
                        f"Confidence mismatch: API={api_data['confidence']}, Service={service_confidence}"
                    )
                    validation_results["passed"] = False
        
        # Check timestamp preservation
        if "timestamp" in api_data:
            service_timestamp = getattr(service_result, 'timestamp', None)
            if service_timestamp is not None:
                if abs(float(api_data["timestamp"]) - float(service_timestamp)) > 0.001:
                    validation_results["errors"].append(
                        f"Timestamp mismatch: API={api_data['timestamp']}, Service={service_timestamp}"
                    )
                    validation_results["passed"] = False
        
        return validation_results
    
    def validate_service_to_database_flow(self, service_data: Any, 
                                        db_record: Any) -> Dict[str, Any]:
        """Validate data transformation from service to database layer"""
        validation_results = {
            "passed": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required fields are preserved
        required_fields = ['class_label', 'confidence', 'timestamp', 'x', 'y', 'width', 'height']
        
        for field in required_fields:
            service_value = getattr(service_data, field, None)
            db_value = getattr(db_record, field, None)
            
            if service_value is not None and db_value is not None:
                if isinstance(service_value, (int, float)) and isinstance(db_value, (int, float)):
                    if abs(float(service_value) - float(db_value)) > 0.001:
                        validation_results["errors"].append(
                            f"Field {field} mismatch: Service={service_value}, DB={db_value}"
                        )
                        validation_results["passed"] = False
                elif str(service_value) != str(db_value):
                    validation_results["errors"].append(
                        f"Field {field} mismatch: Service={service_value}, DB={db_value}"
                    )
                    validation_results["passed"] = False
        
        return validation_results
    
    def validate_database_to_api_flow(self, db_record: Any, 
                                    api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data transformation from database to API response"""
        validation_results = {
            "passed": True,
            "errors": [],
            "warnings": []
        }
        
        # Check ID consistency
        if hasattr(db_record, 'id') and 'id' in api_response:
            if str(db_record.id) != str(api_response['id']):
                validation_results["errors"].append(
                    f"ID mismatch: DB={db_record.id}, API={api_response['id']}"
                )
                validation_results["passed"] = False
        
        # Check video_id consistency
        if hasattr(db_record, 'video_id') and 'video_id' in api_response:
            if str(db_record.video_id) != str(api_response['video_id']):
                validation_results["errors"].append(
                    f"Video ID mismatch: DB={db_record.video_id}, API={api_response['video_id']}"
                )
                validation_results["passed"] = False
        
        return validation_results

@pytest.fixture
def data_flow_validator():
    """Provide data flow validator instance"""
    return DataFlowValidator()

@pytest.fixture
def sample_project():
    """Create sample project for testing"""
    project = Project(
        id=str(uuid.uuid4()),
        name="Data Flow Test Project",
        description="Project for data flow validation testing",
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
        yield project
    finally:
        db.query(Project).filter(Project.id == project.id).delete()
        db.commit()
        db.close()

@pytest.fixture
def sample_video(sample_project):
    """Create sample video for testing"""
    video = Video(
        id=str(uuid.uuid4()),
        filename="test_data_flow.mp4",
        file_path="/tmp/test_data_flow.mp4",
        file_size=1024000,
        duration=10.0,
        fps=30.0,
        resolution="640x480",
        status="uploaded",
        processing_status="pending",
        ground_truth_generated=False,
        project_id=sample_project.id
    )
    
    db = SessionLocal()
    try:
        db.add(video)
        db.commit()
        db.refresh(video)
        yield video
    finally:
        db.query(Video).filter(Video.id == video.id).delete()
        db.commit()
        db.close()

class TestAPIDataFlow:
    """Test API layer data flow validation"""
    
    def test_available_videos_response_schema(self, data_flow_validator, sample_video):
        """Test that available videos API response matches expected schema"""
        # Mark video as having ground truth
        db = SessionLocal()
        try:
            sample_video.ground_truth_generated = True
            sample_video.status = "validated"
            db.commit()
        finally:
            db.close()
        
        # Test API response
        response = data_flow_validator.test_client.get("/api/ground-truth/videos/available")
        assert response.status_code == 200
        
        videos = response.json()
        assert isinstance(videos, list)
        
        # Find our test video
        test_video = next((v for v in videos if v["id"] == sample_video.id), None)
        assert test_video is not None
        
        # Validate schema fields
        required_fields = ["id", "filename", "projectId", "status", "createdAt"]
        for field in required_fields:
            assert field in test_video, f"Missing required field: {field}"
        
        # Validate data types
        assert isinstance(test_video["id"], str)
        assert isinstance(test_video["filename"], str)
        assert isinstance(test_video["projectId"], str)
        assert isinstance(test_video["status"], str)
        
        # Validate values match database
        assert test_video["id"] == sample_video.id
        assert test_video["filename"] == sample_video.filename
        assert test_video["projectId"] == sample_video.project_id
        assert test_video["status"] == sample_video.status
    
    def test_video_stats_response_schema(self, data_flow_validator, sample_video):
        """Test video stats API response schema"""
        # Create sample ground truth object
        db = SessionLocal()
        try:
            gt_object = GroundTruthObject(
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
                validated=True,
                difficult=False
            )
            db.add(gt_object)
            db.commit()
        finally:
            db.close()
        
        # Test API response
        response = data_flow_validator.test_client.get(
            f"/api/ground-truth/videos/{sample_video.id}/stats"
        )
        assert response.status_code == 200
        
        stats = response.json()
        
        # Validate schema structure
        required_top_level = ["video_id", "filename", "statistics", "class_distribution"]
        for field in required_top_level:
            assert field in stats, f"Missing top-level field: {field}"
        
        # Validate statistics structure
        stats_fields = ["total_detections", "unique_classes", "average_confidence"]
        for field in stats_fields:
            assert field in stats["statistics"], f"Missing statistics field: {field}"
        
        # Validate data types and values
        assert stats["video_id"] == sample_video.id
        assert stats["filename"] == sample_video.filename
        assert isinstance(stats["statistics"]["total_detections"], int)
        assert stats["statistics"]["total_detections"] >= 1
        assert isinstance(stats["statistics"]["average_confidence"], float)
        assert 0.0 <= stats["statistics"]["average_confidence"] <= 1.0

class TestServiceDataFlow:
    """Test service layer data transformations"""
    
    def test_ground_truth_service_data_consistency(self, data_flow_validator, sample_video):
        """Test data consistency in ground truth service operations"""
        db = SessionLocal()
        try:
            # Create initial ground truth object
            original_gt = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=sample_video.id,
                frame_number=50,
                timestamp=1.67,
                class_label="cyclist",
                x=200.0,
                y=150.0,
                width=100.0,
                height=180.0,
                confidence=0.92,
                validated=False,
                difficult=False
            )
            db.add(original_gt)
            db.commit()
            
            # Test service retrieval
            ground_truth_response = data_flow_validator.service.get_ground_truth(sample_video.id)
            
            # Validate response structure
            assert hasattr(ground_truth_response, 'video_id')
            assert hasattr(ground_truth_response, 'objects')
            assert hasattr(ground_truth_response, 'total_detections')
            
            # Validate data consistency
            assert ground_truth_response.video_id == sample_video.id
            assert ground_truth_response.total_detections >= 1
            
            # Find our object in the response
            found_object = None
            for obj in ground_truth_response.objects:
                if obj.id == original_gt.id:
                    found_object = obj
                    break
            
            assert found_object is not None, "Ground truth object not found in service response"
            
            # Validate field consistency
            assert found_object.timestamp == original_gt.timestamp
            assert found_object.class_label == original_gt.class_label
            assert found_object.confidence == original_gt.confidence
            
        finally:
            db.close()

class TestDatabaseDataFlow:
    """Test database layer data persistence and retrieval"""
    
    def test_ground_truth_object_persistence(self, data_flow_validator, sample_video):
        """Test ground truth object data persistence"""
        original_data = {
            "id": str(uuid.uuid4()),
            "video_id": sample_video.id,
            "frame_number": 75,
            "timestamp": 2.5,
            "class_label": "motorcyclist",
            "x": 300.0,
            "y": 100.0,
            "width": 120.0,
            "height": 200.0,
            "confidence": 0.78,
            "validated": True,
            "difficult": False
        }
        
        db = SessionLocal()
        try:
            # Create and save object
            gt_object = GroundTruthObject(**original_data)
            db.add(gt_object)
            db.commit()
            
            # Retrieve and validate
            retrieved = db.query(GroundTruthObject).filter(
                GroundTruthObject.id == original_data["id"]
            ).first()
            
            assert retrieved is not None
            
            # Validate all fields
            for field, expected_value in original_data.items():
                actual_value = getattr(retrieved, field)
                
                if isinstance(expected_value, float):
                    assert abs(actual_value - expected_value) < 0.001, \
                        f"Field {field}: expected {expected_value}, got {actual_value}"
                else:
                    assert actual_value == expected_value, \
                        f"Field {field}: expected {expected_value}, got {actual_value}"
        finally:
            db.close()
    
    def test_detection_event_persistence(self, data_flow_validator, sample_video):
        """Test detection event data persistence"""
        original_data = {
            "id": str(uuid.uuid4()),
            "video_id": sample_video.id,
            "timestamp": 4.2,
            "confidence": 0.89,
            "class_label": "pedestrian",
            "validation_result": "Pass",
            "source": "ai",
            "frame_number": 126,
            "vru_type": "pedestrian",
            "bounding_box_x": 180.0,
            "bounding_box_y": 220.0,
            "bounding_box_width": 90.0,
            "bounding_box_height": 170.0
        }
        
        db = SessionLocal()
        try:
            # Create and save detection event
            detection_event = DetectionEvent(**original_data)
            db.add(detection_event)
            db.commit()
            
            # Retrieve and validate
            retrieved = db.query(DetectionEvent).filter(
                DetectionEvent.id == original_data["id"]
            ).first()
            
            assert retrieved is not None
            
            # Validate all fields
            for field, expected_value in original_data.items():
                actual_value = getattr(retrieved, field)
                
                if isinstance(expected_value, float):
                    assert abs(actual_value - expected_value) < 0.001, \
                        f"Field {field}: expected {expected_value}, got {actual_value}"
                else:
                    assert actual_value == expected_value, \
                        f"Field {field}: expected {expected_value}, got {actual_value}"
        finally:
            db.close()

class TestCrossLayerDataFlow:
    """Test data consistency across multiple system layers"""
    
    def test_end_to_end_data_consistency(self, data_flow_validator, sample_video):
        """Test data consistency from API input to database storage to API output"""
        # Step 1: Create ground truth via direct database insert (simulating service layer)
        original_data = {
            "id": str(uuid.uuid4()),
            "video_id": sample_video.id,
            "frame_number": 60,
            "timestamp": 2.0,
            "class_label": "pedestrian",
            "x": 250.0,
            "y": 180.0,
            "width": 85.0,
            "height": 165.0,
            "confidence": 0.87,
            "validated": True,
            "difficult": False
        }
        
        db = SessionLocal()
        try:
            # Insert into database
            gt_object = GroundTruthObject(**original_data)
            db.add(gt_object)
            
            # Mark video as having ground truth
            sample_video.ground_truth_generated = True
            sample_video.status = "validated"
            db.commit()
            
            # Step 2: Retrieve via API
            response = data_flow_validator.test_client.get(
                f"/api/ground-truth/videos/{sample_video.id}/stats"
            )
            assert response.status_code == 200
            
            api_stats = response.json()
            
            # Step 3: Validate data consistency
            assert api_stats["video_id"] == sample_video.id
            assert api_stats["statistics"]["total_detections"] >= 1
            
            # Check class distribution includes our object
            assert "pedestrian" in api_stats["class_distribution"]
            assert api_stats["class_distribution"]["pedestrian"] >= 1
            
            # Step 4: Verify confidence is preserved correctly
            expected_confidence = original_data["confidence"]
            actual_avg_confidence = api_stats["statistics"]["average_confidence"]
            
            # For a single object, average should equal the object's confidence
            assert abs(actual_avg_confidence - expected_confidence) < 0.1, \
                f"Confidence mismatch: expected ~{expected_confidence}, got {actual_avg_confidence}"
            
        finally:
            db.close()
    
    def test_data_type_preservation(self, data_flow_validator, sample_video):
        """Test that data types are preserved across all layers"""
        test_cases = [
            {
                "field": "confidence",
                "value": 0.123456789,
                "type": float,
                "precision": 0.001
            },
            {
                "field": "timestamp", 
                "value": 1.234567,
                "type": float,
                "precision": 0.001
            },
            {
                "field": "frame_number",
                "value": 42,
                "type": int,
                "precision": None
            },
            {
                "field": "x",
                "value": 123.45,
                "type": float,
                "precision": 0.01
            }
        ]
        
        db = SessionLocal()
        try:
            for i, test_case in enumerate(test_cases):
                # Create test object
                gt_data = {
                    "id": str(uuid.uuid4()),
                    "video_id": sample_video.id,
                    "frame_number": test_case["value"] if test_case["field"] == "frame_number" else 50 + i,
                    "timestamp": test_case["value"] if test_case["field"] == "timestamp" else 2.0 + i,
                    "class_label": "pedestrian",
                    "x": test_case["value"] if test_case["field"] == "x" else 200.0,
                    "y": 200.0,
                    "width": 80.0,
                    "height": 160.0,
                    "confidence": test_case["value"] if test_case["field"] == "confidence" else 0.8,
                    "validated": True,
                    "difficult": False
                }
                
                # Store in database
                gt_object = GroundTruthObject(**gt_data)
                db.add(gt_object)
                db.commit()
                
                # Retrieve from database
                retrieved = db.query(GroundTruthObject).filter(
                    GroundTruthObject.id == gt_data["id"]
                ).first()
                
                # Validate type and precision
                actual_value = getattr(retrieved, test_case["field"])
                assert isinstance(actual_value, test_case["type"]), \
                    f"Type mismatch for {test_case['field']}: expected {test_case['type']}, got {type(actual_value)}"
                
                if test_case["precision"] is not None:
                    assert abs(actual_value - test_case["value"]) < test_case["precision"], \
                        f"Precision loss for {test_case['field']}: expected {test_case['value']}, got {actual_value}"
                else:
                    assert actual_value == test_case["value"], \
                        f"Value mismatch for {test_case['field']}: expected {test_case['value']}, got {actual_value}"
        
        finally:
            db.close()

class TestJSONSerializationFlow:
    """Test JSON serialization/deserialization in data flow"""
    
    def test_api_response_serialization(self, data_flow_validator, sample_video):
        """Test that API responses are properly serialized"""
        # Create test data
        db = SessionLocal()
        try:
            gt_object = GroundTruthObject(
                id=str(uuid.uuid4()),
                video_id=sample_video.id,
                frame_number=30,
                timestamp=1.0,
                class_label="cyclist",
                x=100.0,
                y=150.0,
                width=90.0,
                height=170.0,
                confidence=0.95,
                validated=True,
                difficult=False
            )
            db.add(gt_object)
            sample_video.ground_truth_generated = True
            sample_video.status = "validated"
            db.commit()
            
            # Test API response
            response = data_flow_validator.test_client.get("/api/ground-truth/videos/available")
            
            # Should be valid JSON
            assert response.headers["content-type"] == "application/json"
            
            # Should deserialize without errors
            try:
                videos = response.json()
                assert isinstance(videos, list)
            except json.JSONDecodeError as e:
                pytest.fail(f"API response is not valid JSON: {e}")
            
            # Check for our video
            test_video = next((v for v in videos if v["id"] == sample_video.id), None)
            assert test_video is not None
            
            # Validate JSON serializable types
            def check_json_serializable(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        check_json_serializable(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        check_json_serializable(item, f"{path}[{i}]")
                else:
                    # Should be JSON serializable primitive
                    assert isinstance(obj, (str, int, float, bool, type(None))), \
                        f"Non-JSON-serializable type at {path}: {type(obj)}"
            
            check_json_serializable(test_video)
            
        finally:
            db.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])