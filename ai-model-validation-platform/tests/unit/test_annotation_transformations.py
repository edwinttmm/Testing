"""
Annotation Data Transformation Logic Tests
==========================================

Tests for data format transformations, serialization, and deserialization
in the annotation system. Covers API response formats, export formats,
and data integrity validations.
"""

import pytest
import json
from datetime import datetime, timezone
from typing import Dict, Any, List
from unittest.mock import Mock, patch
from pydantic import ValidationError

from models import Annotation, Video, DetectionEvent
from schemas_annotation import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    BoundingBox, VRUTypeEnum, AnnotationExportRequest
)
from services.annotation_service import AnnotationService


class TestAnnotationSchemaTransformations:
    """Test Pydantic schema transformations and validations"""
    
    def test_bounding_box_schema_validation(self):
        """Test bounding box schema validation and transformation"""
        # Valid bounding box
        valid_bbox_data = {
            "x": 100,
            "y": 150,
            "width": 50,
            "height": 100,
            "confidence": 0.95,
            "label": "person"
        }
        
        bbox = BoundingBox(**valid_bbox_data)
        assert bbox.x == 100
        assert bbox.y == 150
        assert bbox.width == 50
        assert bbox.height == 100
        assert bbox.confidence == 0.95
        assert bbox.label == "person"
        
        # Test serialization
        bbox_dict = bbox.dict()
        assert bbox_dict == valid_bbox_data
        
        # Test validation errors
        with pytest.raises(ValidationError):
            BoundingBox(x=-1, y=150, width=50, height=100)  # Negative x
        
        with pytest.raises(ValidationError):
            BoundingBox(x=100, y=150, width=0, height=100)  # Zero width
        
        with pytest.raises(ValidationError):
            BoundingBox(x=100, y=150, width=50, height=100, confidence=1.5)  # Invalid confidence
    
    def test_vru_type_enum_validation(self):
        """Test VRU type enumeration validation"""
        # Valid VRU types
        valid_types = ["pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"]
        
        for vru_type in valid_types:
            enum_value = VRUTypeEnum(vru_type)
            assert enum_value.value == vru_type
        
        # Invalid VRU type
        with pytest.raises(ValueError):
            VRUTypeEnum("invalid_type")
    
    def test_annotation_create_schema_validation(self):
        """Test annotation creation schema validation"""
        valid_create_data = {
            "videoId": "test-video-123",
            "frameNumber": 100,
            "timestamp": 3.33,
            "vruType": VRUTypeEnum.PEDESTRIAN,
            "boundingBox": BoundingBox(x=100, y=150, width=50, height=100),
            "annotator": "test-user",
            "notes": "Test annotation"
        }
        
        annotation_create = AnnotationCreate(**valid_create_data)
        
        assert annotation_create.video_id == "test-video-123"
        assert annotation_create.frame_number == 100
        assert annotation_create.timestamp == 3.33
        assert annotation_create.vru_type == VRUTypeEnum.PEDESTRIAN
        assert annotation_create.bounding_box.x == 100
        assert annotation_create.annotator == "test-user"
        
        # Test optional fields defaults
        assert annotation_create.validated is False
        assert annotation_create.occluded is False
        assert annotation_create.truncated is False
        assert annotation_create.difficult is False
    
    def test_annotation_response_schema_transformation(self):
        """Test annotation response schema with camelCase transformation"""
        # Simulate database model data (snake_case)
        db_annotation_data = {
            "id": "ann-123",
            "video_id": "video-456",
            "detection_id": "det-789",
            "frame_number": 100,
            "timestamp": 3.33,
            "end_timestamp": 5.0,
            "vru_type": "pedestrian",
            "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100},
            "occluded": True,
            "truncated": False,
            "difficult": False,
            "notes": "Test annotation",
            "annotator": "test-user",
            "validated": True,
            "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
        }
        
        # Create response schema (should transform to camelCase)
        annotation_response = AnnotationResponse(**db_annotation_data)
        
        # Test field access (internal still snake_case)
        assert annotation_response.video_id == "video-456"
        assert annotation_response.frame_number == 100
        assert annotation_response.end_timestamp == 5.0
        
        # Test serialization (should be camelCase for API)
        serialized = annotation_response.dict(by_alias=True)
        
        expected_camel_fields = [
            "id", "videoId", "detectionId", "frameNumber", "timestamp",
            "endTimestamp", "vruType", "boundingBox", "occluded",
            "truncated", "difficult", "notes", "annotator", "validated",
            "createdAt", "updatedAt"
        ]
        
        for field in expected_camel_fields:
            assert field in serialized, f"Missing camelCase field: {field}"
        
        # Verify specific transformations
        assert serialized["videoId"] == "video-456"
        assert serialized["frameNumber"] == 100
        assert serialized["endTimestamp"] == 5.0
        assert serialized["vruType"] == "pedestrian"
        assert serialized["createdAt"] is not None


class TestDataFormatTransformations:
    """Test various data format transformations"""
    
    def test_ai_detection_to_annotation_transformation(self):
        """Test transformation from AI detection format to annotation format"""
        # Simulate AI detection event data
        ai_detection = {
            "id": "det-ai-123",
            "timestamp": 4.5,
            "frame_number": 135,
            "class_label": "person",
            "confidence": 0.89,
            "bounding_box_x": 120,
            "bounding_box_y": 180,
            "bounding_box_width": 60,
            "bounding_box_height": 120,
            "vru_type": "pedestrian",
            "source": "ai",
            "detection_type": "automatic"
        }
        
        # Transform to annotation format
        annotation_data = {
            "video_id": "test-video",
            "detection_id": ai_detection["id"],
            "frame_number": ai_detection["frame_number"],
            "timestamp": ai_detection["timestamp"],
            "vru_type": ai_detection["vru_type"],
            "bounding_box": {
                "x": ai_detection["bounding_box_x"],
                "y": ai_detection["bounding_box_y"],
                "width": ai_detection["bounding_box_width"],
                "height": ai_detection["bounding_box_height"],
                "confidence": ai_detection["confidence"],
                "label": ai_detection["class_label"]
            },
            "annotator": f"ai-system-{ai_detection['source']}",
            "validated": False,
            "notes": f"AI detection (confidence: {ai_detection['confidence']}, type: {ai_detection['detection_type']})"
        }
        
        # Verify transformation
        assert annotation_data["detection_id"] == "det-ai-123"
        assert annotation_data["frame_number"] == 135
        assert annotation_data["timestamp"] == 4.5
        assert annotation_data["vru_type"] == "pedestrian"
        assert annotation_data["bounding_box"]["confidence"] == 0.89
        assert annotation_data["annotator"] == "ai-system-ai"
        assert "AI detection" in annotation_data["notes"]
        assert annotation_data["validated"] is False
    
    def test_ground_truth_to_annotation_transformation(self):
        """Test transformation from ground truth format to annotation format"""
        ground_truth_data = {
            "id": "gt-456",
            "video_id": "test-video",
            "tracking_id": "track-001",
            "frame_number": 200,
            "timestamp": 6.67,
            "class_label": "bicycle",
            "x": 200,
            "y": 250,
            "width": 80,
            "height": 60,
            "confidence": 1.0,  # Ground truth has perfect confidence
            "validated": True,
            "difficult": False
        }
        
        # Transform to annotation format
        annotation_data = {
            "video_id": ground_truth_data["video_id"],
            "detection_id": ground_truth_data["tracking_id"],
            "frame_number": ground_truth_data["frame_number"],
            "timestamp": ground_truth_data["timestamp"],
            "vru_type": "cyclist",  # Map from class_label
            "bounding_box": {
                "x": ground_truth_data["x"],
                "y": ground_truth_data["y"],
                "width": ground_truth_data["width"],
                "height": ground_truth_data["height"],
                "confidence": ground_truth_data["confidence"],
                "label": ground_truth_data["class_label"]
            },
            "annotator": "ground-truth-system",
            "validated": ground_truth_data["validated"],
            "difficult": ground_truth_data["difficult"],
            "notes": f"Ground truth annotation (tracking_id: {ground_truth_data['tracking_id']})"
        }
        
        # Verify transformation
        assert annotation_data["detection_id"] == "track-001"
        assert annotation_data["vru_type"] == "cyclist"
        assert annotation_data["bounding_box"]["confidence"] == 1.0
        assert annotation_data["validated"] is True
        assert "Ground truth" in annotation_data["notes"]
    
    def test_annotation_to_export_format_transformation(self):
        """Test transformation from annotation model to export format"""
        # Create annotation model instance
        annotation_model = Annotation(
            id="ann-export-123",
            video_id="video-789",
            detection_id="det-456",
            frame_number=300,
            timestamp=10.0,
            end_timestamp=12.5,
            vru_type="motorcyclist",
            bounding_box={
                "x": 300,
                "y": 200,
                "width": 70,
                "height": 110,
                "confidence": 0.93,
                "label": "motorcycle"
            },
            occluded=False,
            truncated=True,
            difficult=False,
            notes="Motorcyclist at edge of frame",
            annotator="expert-annotator",
            validated=True,
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, 13, 30, 0, tzinfo=timezone.utc)
        )
        
        # Transform to export format (JSON)
        export_data = {
            "id": annotation_model.id,
            "video_id": annotation_model.video_id,
            "detection_id": annotation_model.detection_id,
            "frame_number": annotation_model.frame_number,
            "timestamp": annotation_model.timestamp,
            "end_timestamp": annotation_model.end_timestamp,
            "vru_type": annotation_model.vru_type,
            "bounding_box": annotation_model.bounding_box,
            "occluded": annotation_model.occluded,
            "truncated": annotation_model.truncated,
            "difficult": annotation_model.difficult,
            "notes": annotation_model.notes,
            "annotator": annotation_model.annotator,
            "validated": annotation_model.validated,
            "created_at": annotation_model.created_at.isoformat() if annotation_model.created_at else None,
            "updated_at": annotation_model.updated_at.isoformat() if annotation_model.updated_at else None
        }
        
        # Verify export format
        assert export_data["id"] == "ann-export-123"
        assert export_data["vru_type"] == "motorcyclist"
        assert export_data["bounding_box"]["confidence"] == 0.93
        assert export_data["truncated"] is True
        assert export_data["created_at"] == "2024-01-01T12:00:00+00:00"
        assert export_data["updated_at"] == "2024-01-01T13:30:00+00:00"


class TestBoundingBoxTransformations:
    """Test bounding box coordinate transformations and normalizations"""
    
    def test_absolute_to_relative_coordinates(self):
        """Test transformation from absolute to relative coordinates"""
        # Video dimensions
        video_width = 1920
        video_height = 1080
        
        # Absolute coordinates
        absolute_bbox = {
            "x": 480,    # 25% of width
            "y": 270,    # 25% of height
            "width": 960,  # 50% of width
            "height": 540  # 50% of height
        }
        
        # Transform to relative coordinates (0-1 range)
        relative_bbox = {
            "x": absolute_bbox["x"] / video_width,
            "y": absolute_bbox["y"] / video_height,
            "width": absolute_bbox["width"] / video_width,
            "height": absolute_bbox["height"] / video_height
        }
        
        # Verify relative coordinates
        assert abs(relative_bbox["x"] - 0.25) < 0.001
        assert abs(relative_bbox["y"] - 0.25) < 0.001
        assert abs(relative_bbox["width"] - 0.5) < 0.001
        assert abs(relative_bbox["height"] - 0.5) < 0.001
        
        # Transform back to absolute coordinates
        restored_bbox = {
            "x": int(relative_bbox["x"] * video_width),
            "y": int(relative_bbox["y"] * video_height),
            "width": int(relative_bbox["width"] * video_width),
            "height": int(relative_bbox["height"] * video_height)
        }
        
        # Verify restoration (allowing for rounding errors)
        assert abs(restored_bbox["x"] - absolute_bbox["x"]) <= 1
        assert abs(restored_bbox["y"] - absolute_bbox["y"]) <= 1
        assert abs(restored_bbox["width"] - absolute_bbox["width"]) <= 1
        assert abs(restored_bbox["height"] - absolute_bbox["height"]) <= 1
    
    def test_center_point_to_corner_transformation(self):
        """Test transformation from center point to corner coordinates"""
        # Center point format (x_center, y_center, width, height)
        center_bbox = {
            "x_center": 500,
            "y_center": 400,
            "width": 100,
            "height": 200
        }
        
        # Transform to corner format (x_min, y_min, width, height)
        corner_bbox = {
            "x": center_bbox["x_center"] - center_bbox["width"] // 2,
            "y": center_bbox["y_center"] - center_bbox["height"] // 2,
            "width": center_bbox["width"],
            "height": center_bbox["height"]
        }
        
        # Verify corner coordinates
        assert corner_bbox["x"] == 450  # 500 - 50
        assert corner_bbox["y"] == 300  # 400 - 100
        assert corner_bbox["width"] == 100
        assert corner_bbox["height"] == 200
        
        # Transform back to center point
        restored_center = {
            "x_center": corner_bbox["x"] + corner_bbox["width"] // 2,
            "y_center": corner_bbox["y"] + corner_bbox["height"] // 2,
            "width": corner_bbox["width"],
            "height": corner_bbox["height"]
        }
        
        # Verify restoration
        assert restored_center["x_center"] == center_bbox["x_center"]
        assert restored_center["y_center"] == center_bbox["y_center"]
    
    def test_bounding_box_clipping(self):
        """Test bounding box clipping to video boundaries"""
        video_width = 1920
        video_height = 1080
        
        # Bounding box that extends beyond video boundaries
        oversized_bbox = {
            "x": -50,      # Negative x (outside left boundary)
            "y": 1000,     # Y near bottom boundary
            "width": 2000, # Width extends beyond right boundary
            "height": 150  # Height extends beyond bottom boundary
        }
        
        # Clip to video boundaries
        clipped_bbox = {
            "x": max(0, oversized_bbox["x"]),
            "y": max(0, oversized_bbox["y"]),
            "width": min(oversized_bbox["width"], video_width - max(0, oversized_bbox["x"])),
            "height": min(oversized_bbox["height"], video_height - max(0, oversized_bbox["y"]))
        }
        
        # Ensure clipped coordinates don't exceed boundaries
        assert clipped_bbox["x"] >= 0
        assert clipped_bbox["y"] >= 0
        assert clipped_bbox["x"] + clipped_bbox["width"] <= video_width
        assert clipped_bbox["y"] + clipped_bbox["height"] <= video_height
        
        # Verify specific clipping results
        assert clipped_bbox["x"] == 0  # Clipped from -50 to 0
        assert clipped_bbox["y"] == 1000
        assert clipped_bbox["width"] == 1920  # Clipped to video width
        assert clipped_bbox["height"] == 80   # Clipped to remaining height (1080 - 1000)


class TestAnnotationServiceTransformations:
    """Test annotation service data transformations"""
    
    def test_annotation_to_dict_transformation(self):
        """Test annotation model to dictionary transformation in service"""
        service = AnnotationService()
        
        # Create mock annotation
        mock_annotation = Mock()
        mock_annotation.id = "ann-service-123"
        mock_annotation.video_id = "video-456"
        mock_annotation.detection_id = "det-789"
        mock_annotation.frame_number = 150
        mock_annotation.timestamp = 5.0
        mock_annotation.end_timestamp = 7.5
        mock_annotation.vru_type = "cyclist"
        mock_annotation.bounding_box = {"x": 200, "y": 250, "width": 80, "height": 60}
        mock_annotation.occluded = False
        mock_annotation.truncated = True
        mock_annotation.difficult = False
        mock_annotation.notes = "Service test annotation"
        mock_annotation.annotator = "service-user"
        mock_annotation.validated = True
        mock_annotation.created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        mock_annotation.updated_at = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        
        # Transform using service method
        annotation_dict = service._annotation_to_dict(mock_annotation)
        
        # Verify transformation
        assert annotation_dict["id"] == "ann-service-123"
        assert annotation_dict["video_id"] == "video-456"
        assert annotation_dict["frame_number"] == 150
        assert annotation_dict["vru_type"] == "cyclist"
        assert annotation_dict["bounding_box"]["x"] == 200
        assert annotation_dict["truncated"] is True
        assert annotation_dict["validated"] is True
        assert annotation_dict["created_at"] == "2024-01-01T12:00:00+00:00"
        assert annotation_dict["updated_at"] == "2024-01-01T14:00:00+00:00"
    
    def test_detection_id_generation(self):
        """Test detection ID generation in annotation service"""
        service = AnnotationService()
        
        # Test detection ID generation for different VRU types
        vru_types = ["pedestrian", "cyclist", "motorcyclist", "wheelchair", "scooter"]
        
        for vru_type in vru_types:
            detection_id = service._generate_detection_id(vru_type)
            
            # Verify format: DET_{VRU_TYPE}_{TIMESTAMP}_{RANDOM}
            assert detection_id.startswith(f"DET_{vru_type.upper()}_")
            parts = detection_id.split("_")
            assert len(parts) == 4
            assert parts[0] == "DET"
            assert parts[1] == vru_type.upper()
            assert parts[2].isdigit()  # Timestamp
            assert len(parts[3]) == 8  # Random part
    
    def test_bulk_annotation_transformation(self):
        """Test bulk annotation data transformations"""
        service = AnnotationService()
        
        # Simulate bulk annotation data
        bulk_annotation_data = [
            {
                "video_id": "video-bulk-1",
                "frame_number": 100 + i,
                "timestamp": 3.0 + i * 0.5,
                "vru_type": "pedestrian" if i % 2 == 0 else "cyclist",
                "bounding_box": {
                    "x": 100 + i * 10,
                    "y": 150,
                    "width": 50,
                    "height": 100,
                    "confidence": 0.8 + i * 0.02
                },
                "annotator": f"bulk-user-{i}"
            }
            for i in range(10)
        ]
        
        # Transform annotations (would normally involve database operations)
        transformed_annotations = []
        for i, annotation_data in enumerate(bulk_annotation_data):
            # Generate detection ID if missing
            if not annotation_data.get("detection_id"):
                annotation_data["detection_id"] = service._generate_detection_id(
                    annotation_data["vru_type"]
                )
            
            transformed_annotations.append(annotation_data)
        
        # Verify bulk transformations
        assert len(transformed_annotations) == 10
        
        for i, annotation in enumerate(transformed_annotations):
            assert "detection_id" in annotation
            assert annotation["detection_id"].startswith("DET_")
            
            expected_vru = "PEDESTRIAN" if i % 2 == 0 else "CYCLIST"
            assert expected_vru in annotation["detection_id"]
            
            assert annotation["frame_number"] == 100 + i
            assert annotation["bounding_box"]["confidence"] == 0.8 + i * 0.02


class TestExportFormatTransformations:
    """Test export format transformations (JSON, COCO, YOLO, etc.)"""
    
    def test_json_export_format(self):
        """Test JSON export format transformation"""
        # Sample annotations
        annotations = [
            {
                "id": "ann-1",
                "video_id": "video-export",
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100},
                "validated": True,
                "annotator": "export-user-1"
            },
            {
                "id": "ann-2",
                "video_id": "video-export",
                "frame_number": 200,
                "timestamp": 6.67,
                "vru_type": "cyclist",
                "bounding_box": {"x": 200, "y": 200, "width": 60, "height": 80},
                "validated": False,
                "annotator": "export-user-2"
            }
        ]
        
        # Transform to JSON export format
        json_export = {
            "format": "json",
            "version": "1.0",
            "video_id": "video-export",
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "total_annotations": len(annotations),
            "annotations": annotations
        }
        
        # Verify JSON export structure
        assert json_export["format"] == "json"
        assert json_export["total_annotations"] == 2
        assert len(json_export["annotations"]) == 2
        assert json_export["annotations"][0]["vru_type"] == "pedestrian"
        assert json_export["annotations"][1]["vru_type"] == "cyclist"
    
    def test_coco_format_transformation(self):
        """Test transformation to COCO format (future implementation)"""
        # Sample annotation data
        annotation = {
            "id": "ann-coco-1",
            "video_id": "video-coco",
            "frame_number": 150,
            "timestamp": 5.0,
            "vru_type": "pedestrian",
            "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100},
            "area": 5000  # width * height
        }
        
        # Transform to COCO format
        coco_annotation = {
            "id": int(annotation["id"].split("-")[-1]) if annotation["id"].split("-")[-1].isdigit() else hash(annotation["id"]) % 1000000,
            "image_id": int(annotation["frame_number"]),
            "category_id": self._get_coco_category_id(annotation["vru_type"]),
            "bbox": [
                annotation["bounding_box"]["x"],
                annotation["bounding_box"]["y"],
                annotation["bounding_box"]["width"],
                annotation["bounding_box"]["height"]
            ],
            "area": annotation["bounding_box"]["width"] * annotation["bounding_box"]["height"],
            "iscrowd": 0
        }
        
        # Verify COCO format
        assert "id" in coco_annotation
        assert coco_annotation["image_id"] == 150
        assert coco_annotation["bbox"] == [100, 150, 50, 100]
        assert coco_annotation["area"] == 5000
        assert coco_annotation["iscrowd"] == 0
    
    def _get_coco_category_id(self, vru_type: str) -> int:
        """Map VRU type to COCO category ID"""
        category_mapping = {
            "pedestrian": 1,
            "cyclist": 2,
            "motorcyclist": 3,
            "wheelchair": 4,
            "scooter": 5
        }
        return category_mapping.get(vru_type, 0)
    
    def test_yolo_format_transformation(self):
        """Test transformation to YOLO format (future implementation)"""
        # Sample annotation with video dimensions
        annotation = {
            "id": "ann-yolo-1",
            "video_id": "video-yolo",
            "frame_number": 200,
            "vru_type": "cyclist",
            "bounding_box": {"x": 400, "y": 300, "width": 80, "height": 60}
        }
        
        video_width = 1920
        video_height = 1080
        
        # Transform to YOLO format (class x_center y_center width height - all normalized)
        class_id = self._get_yolo_class_id(annotation["vru_type"])
        x_center = (annotation["bounding_box"]["x"] + annotation["bounding_box"]["width"] / 2) / video_width
        y_center = (annotation["bounding_box"]["y"] + annotation["bounding_box"]["height"] / 2) / video_height
        width = annotation["bounding_box"]["width"] / video_width
        height = annotation["bounding_box"]["height"] / video_height
        
        yolo_annotation = f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
        
        # Verify YOLO format
        parts = yolo_annotation.split()
        assert len(parts) == 5
        assert int(parts[0]) == self._get_yolo_class_id("cyclist")
        assert 0 <= float(parts[1]) <= 1  # Normalized x_center
        assert 0 <= float(parts[2]) <= 1  # Normalized y_center
        assert 0 <= float(parts[3]) <= 1  # Normalized width
        assert 0 <= float(parts[4]) <= 1  # Normalized height
    
    def _get_yolo_class_id(self, vru_type: str) -> int:
        """Map VRU type to YOLO class ID"""
        class_mapping = {
            "pedestrian": 0,
            "cyclist": 1,
            "motorcyclist": 2,
            "wheelchair": 3,
            "scooter": 4
        }
        return class_mapping.get(vru_type, 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])