"""
Complete Annotation Workflow Integration Tests
==============================================

Tests the end-to-end annotation workflows including:
- Video upload and processing
- AI detection generation
- Annotation creation and validation
- Export and reporting
"""

import pytest
import json
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from typing import Dict, Any, List

from tests.conftest import TestDataHelper
from models import (
    Annotation, Video, Project, DetectionEvent, GroundTruthObject,
    TestSession, AnnotationSession
)
from services.annotation_service import AnnotationService
from main import app


class TestVideoToAnnotationWorkflow:
    """Test complete workflow from video upload to annotation creation"""
    
    def test_video_upload_to_ai_detection_workflow(self, test_client: TestClient, test_db: Session, temp_upload_dir):
        """Test workflow from video upload to AI detection generation"""
        # 1. Create project
        project_data = {
            "name": "Test Annotation Project",
            "description": "Project for annotation workflow testing",
            "cameraModel": "Test Camera",
            "cameraView": "Front-facing VRU",
            "signalType": "GPIO"
        }
        
        project_response = test_client.post("/api/projects/", json=project_data)
        assert project_response.status_code == 201
        project = project_response.json()
        project_id = project["id"]
        
        # 2. Simulate video upload
        video_data = {
            "id": "workflow-test-video",
            "filename": "test_workflow.mp4",
            "file_path": str(temp_upload_dir / "test_workflow.mp4"),
            "project_id": project_id,
            "file_size": 1024000,
            "duration": 30.0,
            "fps": 30.0,
            "resolution": "1920x1080",
            "status": "uploaded"
        }
        
        video = TestDataHelper.create_video(test_db, video_data)
        
        # 3. Simulate AI detection processing
        ai_detections = [
            {
                "frame_number": 100,
                "timestamp": 3.33,
                "class_label": "person",
                "confidence": 0.92,
                "bounding_box_x": 100,
                "bounding_box_y": 150,
                "bounding_box_width": 50,
                "bounding_box_height": 100,
                "vru_type": "pedestrian",
                "source": "ai",
                "detection_type": "automatic"
            },
            {
                "frame_number": 150,
                "timestamp": 5.0,
                "class_label": "bicycle",
                "confidence": 0.87,
                "bounding_box_x": 200,
                "bounding_box_y": 200,
                "bounding_box_width": 80,
                "bounding_box_height": 60,
                "vru_type": "cyclist",
                "source": "ai",
                "detection_type": "automatic"
            }
        ]
        
        # Create test session for detections
        test_session_data = {
            "name": "AI Detection Session",
            "projectId": project_id,
            "videoId": video.id,
            "toleranceMs": 100
        }
        
        session_response = test_client.post("/api/test-sessions/", json=test_session_data)
        assert session_response.status_code == 201
        test_session = session_response.json()
        
        # Add detections to session
        detection_events = []
        for detection_data in ai_detections:
            detection_event = DetectionEvent(
                test_session_id=test_session["id"],
                video_id=video.id,
                **detection_data
            )
            test_db.add(detection_event)
            detection_events.append(detection_event)
        
        test_db.commit()
        
        # 4. Convert AI detections to annotations
        for detection_event in detection_events:
            test_db.refresh(detection_event)
            
            annotation_data = {
                "videoId": video.id,
                "detectionId": detection_event.id,
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
            
            annotation_response = test_client.post("/api/annotations/", json=annotation_data)
            assert annotation_response.status_code == 201
        
        # 5. Verify annotations were created
        annotations_response = test_client.get(f"/api/annotations/?video_id={video.id}")
        assert annotations_response.status_code == 200
        
        annotations = annotations_response.json()
        assert len(annotations) == 2
        
        # Verify annotation data integrity
        pedestrian_annotation = next((a for a in annotations if a["vruType"] == "pedestrian"), None)
        assert pedestrian_annotation is not None
        assert pedestrian_annotation["frameNumber"] == 100
        assert pedestrian_annotation["boundingBox"]["confidence"] == 0.92
        assert pedestrian_annotation["annotator"] == "ai-system"
        assert pedestrian_annotation["validated"] is False
        
        cyclist_annotation = next((a for a in annotations if a["vruType"] == "cyclist"), None)
        assert cyclist_annotation is not None
        assert cyclist_annotation["frameNumber"] == 150
        assert cyclist_annotation["boundingBox"]["confidence"] == 0.87
    
    def test_manual_annotation_workflow(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test manual annotation creation workflow"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # 1. Create annotation session
        session_data = {
            "video_id": video.id,
            "project_id": video.project_id,
            "annotator_id": "manual-annotator-123",
            "total_frames": 1000
        }
        
        service = AnnotationService()
        session_result = service._annotation_session_service.create_session(test_db, session_data)
        assert session_result["success"] is True
        session = session_result["session"]
        
        # 2. Create manual annotations
        manual_annotations = [
            {
                "videoId": video.id,
                "frameNumber": 50,
                "timestamp": 1.67,
                "vruType": "pedestrian",
                "boundingBox": {"x": 120, "y": 180, "width": 45, "height": 90},
                "annotator": "manual-annotator-123",
                "validated": True,
                "notes": "Clear pedestrian crossing street"
            },
            {
                "videoId": video.id,
                "frameNumber": 75,
                "timestamp": 2.5,
                "endTimestamp": 4.0,
                "vruType": "cyclist",
                "boundingBox": {"x": 200, "y": 150, "width": 70, "height": 110},
                "annotator": "manual-annotator-123",
                "validated": True,
                "notes": "Cyclist with temporal tracking",
                "occluded": False,
                "truncated": False,
                "difficult": False
            }
        ]
        
        created_annotations = []
        for annotation_data in manual_annotations:
            response = test_client.post("/api/annotations/", json=annotation_data)
            assert response.status_code == 201
            created_annotations.append(response.json())
        
        # 3. Update session progress
        progress_data = {
            "current_frame": 100,
            "total_detections": 2,
            "validated_detections": 2
        }
        
        progress_result = service._annotation_session_service.update_session_progress(
            test_db, session["id"], progress_data
        )
        assert progress_result["success"] is True
        
        # 4. Verify annotation quality
        for annotation in created_annotations:
            assert annotation["validated"] is True
            assert annotation["annotator"] == "manual-annotator-123"
            assert len(annotation["notes"]) > 0


class TestAnnotationValidationWorkflow:
    """Test annotation validation and quality assurance workflow"""
    
    def test_annotation_validation_workflow(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test complete annotation validation workflow"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # 1. Create unvalidated annotations
        unvalidated_annotations = []
        for i in range(5):
            annotation_data = {
                "videoId": video.id,
                "frameNumber": 100 + i * 20,
                "timestamp": 3.33 + i * 0.67,
                "vruType": "pedestrian",
                "boundingBox": {
                    "x": 100 + i * 10,
                    "y": 150,
                    "width": 50,
                    "height": 100,
                    "confidence": 0.8 + i * 0.02
                },
                "annotator": "initial-annotator",
                "validated": False
            }
            
            response = test_client.post("/api/annotations/", json=annotation_data)
            assert response.status_code == 201
            unvalidated_annotations.append(response.json())
        
        # 2. Validation review process
        validator_updates = []
        for i, annotation in enumerate(unvalidated_annotations):
            # Simulate validator reviewing each annotation
            if i % 2 == 0:  # Approve even-indexed annotations
                update_data = {
                    "validated": True,
                    "annotator": "validator-1",
                    "notes": f"Validated - good quality detection"
                }
            else:  # Request changes for odd-indexed annotations
                update_data = {
                    "validated": False,
                    "annotator": "validator-1",
                    "notes": f"Needs revision - bounding box adjustment required",
                    "boundingBox": {
                        "x": annotation["boundingBox"]["x"] + 5,  # Adjust bounding box
                        "y": annotation["boundingBox"]["y"] + 3,
                        "width": annotation["boundingBox"]["width"],
                        "height": annotation["boundingBox"]["height"],
                        "confidence": annotation["boundingBox"]["confidence"]
                    }
                }
            
            response = test_client.put(f"/api/annotations/{annotation['id']}", json=update_data)
            assert response.status_code == 200
            validator_updates.append(response.json())
        
        # 3. Final validation pass
        for i, annotation in enumerate(validator_updates):
            if not annotation["validated"]:
                # Final approval after revision
                final_update = {
                    "validated": True,
                    "annotator": "validator-1",
                    "notes": annotation["notes"] + " - Revised and approved"
                }
                
                response = test_client.put(f"/api/annotations/{annotation['id']}", json=final_update)
                assert response.status_code == 200
        
        # 4. Verify final validation statistics
        stats_response = test_client.get(f"/api/annotations/stats/summary?video_id={video.id}")
        assert stats_response.status_code == 200
        
        stats = stats_response.json()
        assert stats["total_annotations"] == 5
        assert stats["validated_annotations"] == 5
        assert stats["validation_rate"] == 1.0
    
    def test_annotation_quality_assessment(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test annotation quality assessment workflow"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        service = AnnotationService()
        
        # Create annotations with various quality indicators
        quality_annotations = [
            {
                "video_id": video.id,
                "frame_number": 100,
                "timestamp": 3.33,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100},
                "difficult": False,
                "occluded": False,
                "truncated": False,
                "validated": True
            },
            {
                "video_id": video.id,
                "frame_number": 150,
                "timestamp": 5.0,
                "vru_type": "cyclist",
                "bounding_box": {"x": 200, "y": 200, "width": 60, "height": 80},
                "difficult": True,  # Difficult detection
                "occluded": True,   # Partially occluded
                "truncated": False,
                "validated": True
            },
            {
                "video_id": video.id,
                "frame_number": 200,
                "timestamp": 6.67,
                "vru_type": "pedestrian",
                "bounding_box": {"x": 300, "y": 100, "width": 45, "height": 95},
                "difficult": False,
                "occluded": False,
                "truncated": True,  # Edge of frame
                "validated": True
            }
        ]
        
        for ann_data in quality_annotations:
            annotation = Annotation(**ann_data)
            test_db.add(annotation)
        test_db.commit()
        
        # Get annotation statistics for quality assessment
        stats_result = service.get_annotation_statistics(test_db, video.id)
        
        assert stats_result["success"] is True
        stats = stats_result["statistics"]
        
        assert stats["total_annotations"] == 3
        assert stats["quality_metrics"]["difficult"] == 1
        assert stats["quality_metrics"]["occluded"] == 1
        assert stats["quality_metrics"]["truncated"] == 1
        assert stats["quality_metrics"]["quality_rate"] == 2/3  # 2 non-difficult out of 3


class TestAnnotationExportWorkflow:
    """Test annotation export and data exchange workflows"""
    
    def test_complete_export_workflow(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test complete annotation export workflow"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # 1. Create diverse annotation dataset
        annotation_types = [
            {"vru_type": "pedestrian", "count": 15},
            {"vru_type": "cyclist", "count": 10},
            {"vru_type": "motorcyclist", "count": 5}
        ]
        
        total_annotations = 0
        for vru_type_info in annotation_types:
            for i in range(vru_type_info["count"]):
                annotation_data = {
                    "videoId": video.id,
                    "frameNumber": total_annotations * 10,
                    "timestamp": total_annotations * 0.5,
                    "vruType": vru_type_info["vru_type"],
                    "boundingBox": {
                        "x": 100 + (total_annotations % 20) * 10,
                        "y": 150,
                        "width": 50,
                        "height": 100,
                        "confidence": 0.75 + (total_annotations % 25) * 0.01
                    },
                    "validated": total_annotations % 3 == 0,  # 1/3 validated
                    "annotator": f"annotator-{total_annotations % 3 + 1}",
                    "notes": f"Annotation {total_annotations + 1}"
                }
                
                response = test_client.post("/api/annotations/", json=annotation_data)
                assert response.status_code == 201
                total_annotations += 1
        
        assert total_annotations == 30
        
        # 2. Test different export scenarios
        
        # Export all annotations
        all_export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": False
        }
        
        all_response = test_client.post("/api/annotations/export", json=all_export_request)
        assert all_response.status_code == 200
        
        all_data = all_response.json()
        assert all_data["count"] == 30
        assert len(all_data["data"]) == 30
        
        # Export validated only
        validated_export_request = {
            "video_ids": [video.id],
            "format": "json",
            "include_validated_only": True
        }
        
        validated_response = test_client.post("/api/annotations/export", json=validated_export_request)
        assert validated_response.status_code == 200
        
        validated_data = validated_response.json()
        assert validated_data["count"] == 10  # 30 / 3 = 10 validated
        
        # 3. Verify export data integrity
        exported_annotations = all_data["data"]
        
        # Check VRU type distribution
        vru_counts = {}
        for annotation in exported_annotations:
            vru_type = annotation["vru_type"]
            vru_counts[vru_type] = vru_counts.get(vru_type, 0) + 1
        
        assert vru_counts["pedestrian"] == 15
        assert vru_counts["cyclist"] == 10
        assert vru_counts["motorcyclist"] == 5
        
        # Check required fields presence
        required_fields = [
            "id", "video_id", "frame_number", "timestamp", "vru_type",
            "bounding_box", "validated", "annotator", "created_at"
        ]
        
        for annotation in exported_annotations[:5]:  # Check first 5
            for field in required_fields:
                assert field in annotation, f"Missing field: {field}"
    
    def test_annotation_import_validation_workflow(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test annotation import validation workflow (future feature)"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Prepare import data (simulated)
        import_data = {
            "annotations": [
                {
                    "frame_number": 100,
                    "timestamp": 3.33,
                    "vru_type": "pedestrian",
                    "bounding_box": {"x": 100, "y": 150, "width": 50, "height": 100},
                    "confidence": 0.9,
                    "annotator": "external-system",
                    "validated": False
                },
                {
                    "frame_number": 200,
                    "timestamp": 6.67,
                    "vru_type": "cyclist",
                    "bounding_box": {"x": 200, "y": 200, "width": 60, "height": 80},
                    "confidence": 0.85,
                    "annotator": "external-system",
                    "validated": False
                }
            ]
        }
        
        # In a real implementation, this would be handled by import endpoint
        # For now, simulate by creating annotations via API
        
        imported_count = 0
        for annotation_data in import_data["annotations"]:
            api_annotation = {
                "videoId": video.id,
                "frameNumber": annotation_data["frame_number"],
                "timestamp": annotation_data["timestamp"],
                "vruType": annotation_data["vru_type"],
                "boundingBox": {
                    **annotation_data["bounding_box"],
                    "confidence": annotation_data["confidence"]
                },
                "annotator": annotation_data["annotator"],
                "validated": annotation_data["validated"],
                "notes": "Imported from external system"
            }
            
            response = test_client.post("/api/annotations/", json=api_annotation)
            if response.status_code == 201:
                imported_count += 1
        
        assert imported_count == 2
        
        # Verify imported annotations
        annotations_response = test_client.get(f"/api/annotations/?video_id={video.id}")
        assert annotations_response.status_code == 200
        
        annotations = annotations_response.json()
        assert len(annotations) == 2
        
        for annotation in annotations:
            assert annotation["annotator"] == "external-system"
            assert "Imported from external system" in annotation["notes"]


class TestCollaborativeAnnotationWorkflow:
    """Test collaborative annotation workflows with multiple users"""
    
    def test_multi_user_annotation_session(self, test_client: TestClient, test_db: Session, sample_video_data):
        """Test multi-user collaborative annotation workflow"""
        video = TestDataHelper.create_video(test_db, sample_video_data)
        
        # Create annotation session for collaboration
        session_data = {
            "video_id": video.id,
            "project_id": video.project_id,
            "annotator_id": "session-coordinator",
            "total_frames": 300
        }
        
        service = AnnotationService()
        session_result = service._annotation_session_service.create_session(test_db, session_data)
        assert session_result["success"] is True
        
        # Simulate multiple annotators working on different frame ranges
        annotators = [
            {"id": "annotator-1", "frame_range": (0, 100), "specialty": "pedestrians"},
            {"id": "annotator-2", "frame_range": (100, 200), "specialty": "cyclists"},
            {"id": "annotator-3", "frame_range": (200, 300), "specialty": "quality-review"}
        ]
        
        all_annotations = []
        
        for annotator in annotators:
            # Each annotator creates annotations in their assigned range
            for i in range(5):  # 5 annotations per annotator
                frame_num = annotator["frame_range"][0] + i * 20
                
                if annotator["specialty"] == "quality-review":
                    # Quality reviewer validates existing annotations
                    continue
                
                vru_type = "pedestrian" if annotator["specialty"] == "pedestrians" else "cyclist"
                
                annotation_data = {
                    "videoId": video.id,
                    "frameNumber": frame_num,
                    "timestamp": frame_num * 0.033,
                    "vruType": vru_type,
                    "boundingBox": {
                        "x": 100 + i * 15,
                        "y": 150,
                        "width": 50,
                        "height": 100,
                        "confidence": 0.85 + i * 0.02
                    },
                    "annotator": annotator["id"],
                    "validated": False,
                    "notes": f"Created by {annotator['id']} - {annotator['specialty']}"
                }
                
                response = test_client.post("/api/annotations/", json=annotation_data)
                assert response.status_code == 201
                all_annotations.append(response.json())
        
        # Quality reviewer validates all annotations
        reviewer_id = "annotator-3"
        for annotation in all_annotations:
            validation_update = {
                "validated": True,
                "annotator": reviewer_id,
                "notes": annotation["notes"] + f" - Reviewed by {reviewer_id}"
            }
            
            response = test_client.put(f"/api/annotations/{annotation['id']}", json=validation_update)
            assert response.status_code == 200
        
        # Verify collaborative workflow results
        final_stats = test_client.get(f"/api/annotations/stats/summary?video_id={video.id}")
        assert final_stats.status_code == 200
        
        stats = final_stats.json()
        assert stats["total_annotations"] == 10  # 2 annotators * 5 annotations
        assert stats["validated_annotations"] == 10  # All reviewed by quality reviewer
        assert stats["validation_rate"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])