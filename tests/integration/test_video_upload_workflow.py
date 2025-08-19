"""
Integration tests for video upload workflow
"""
import pytest
import json
import io
from pathlib import Path
from unittest.mock import patch, AsyncMock


class TestVideoUploadWorkflow:
    """Test complete video upload workflow with processing_status"""
    
    def test_video_upload_complete_workflow(self, test_client, test_upload_dir, created_project, sample_test_video_file):
        """Test complete video upload workflow"""
        # Prepare upload data
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("test_video.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            response = test_client.post("/upload-video", files=files, data=data)
        
        assert response.status_code == 200
        response_data = response.json()
        
        # Verify response structure
        assert "id" in response_data
        assert response_data["projectId"] == created_project.id
        assert response_data["filename"] == "test_video.mp4"
        assert response_data["status"] == "uploaded"
        assert "groundTruthStatus" in response_data
        assert "processingStatus" in response_data
    
    def test_video_upload_with_metadata_extraction(self, test_client, test_upload_dir, created_project, sample_test_video_file):
        """Test video upload triggers metadata extraction"""
        with patch('services.ground_truth_service.GroundTruthService.extract_metadata') as mock_extract:
            mock_extract.return_value = {
                "duration": 10.0,
                "fps": 30.0,
                "resolution": "1920x1080",
                "frame_count": 300
            }
            
            with open(sample_test_video_file, "rb") as video_file:
                files = {"file": ("metadata_test.mp4", video_file, "video/mp4")}
                data = {"projectId": created_project.id}
                
                response = test_client.post("/upload-video", files=files, data=data)
            
            assert response.status_code == 200
            
            # Verify metadata extraction was called
            mock_extract.assert_called_once()
    
    def test_video_upload_processing_status_workflow(self, test_client, test_db_session, created_project, sample_test_video_file):
        """Test processing_status workflow during upload"""
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("process_test.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            response = test_client.post("/upload-video", files=files, data=data)
        
        assert response.status_code == 200
        video_id = response.json()["id"]
        
        # Check video in database
        from models import Video
        video = test_db_session.query(Video).filter_by(id=video_id).first()
        
        assert video is not None
        assert video.processing_status == "pending"  # Initial status
        assert video.ground_truth_generated is False
    
    @patch('services.ground_truth_service.GroundTruthService.process_video_async')
    def test_background_processing_trigger(self, mock_process, test_client, created_project, sample_test_video_file):
        """Test that background processing is triggered after upload"""
        mock_process.return_value = AsyncMock()
        
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("bg_test.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            response = test_client.post("/upload-video", files=files, data=data)
        
        assert response.status_code == 200
        
        # Verify background processing was triggered
        mock_process.assert_called_once()
    
    def test_video_upload_file_validation(self, test_client, created_project):
        """Test file validation during upload"""
        # Test invalid file type
        invalid_file = io.BytesIO(b"not a video file")
        files = {"file": ("test.txt", invalid_file, "text/plain")}
        data = {"projectId": created_project.id}
        
        response = test_client.post("/upload-video", files=files, data=data)
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    
    def test_video_upload_large_file_handling(self, test_client, created_project, large_video_file):
        """Test large file upload handling"""
        with open(large_video_file, "rb") as video_file:
            files = {"file": ("large_test.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            response = test_client.post("/upload-video", files=files, data=data)
        
        # Should handle large files (within limits)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["fileSize"] > 10 * 1024 * 1024  # 10MB+
    
    def test_video_upload_error_handling(self, test_client, created_project, database_error_simulator):
        """Test error handling during upload"""
        # Simulate database error
        database_error_simulator.simulate_commit_error()
        
        video_content = b'\x00\x00\x00\x18ftypmp41\x00\x00\x00\x00mp41isom' + b'\x00' * 1000
        files = {"file": ("error_test.mp4", io.BytesIO(video_content), "video/mp4")}
        data = {"projectId": created_project.id}
        
        response = test_client.post("/upload-video", files=files, data=data)
        
        # Should handle database errors gracefully
        assert response.status_code == 500
        
        # Restore database for cleanup
        database_error_simulator.restore()
    
    def test_video_upload_duplicate_filename_handling(self, test_client, created_project, sample_test_video_file):
        """Test handling of duplicate filenames"""
        # Upload first video
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("duplicate.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            response1 = test_client.post("/upload-video", files=files, data=data)
        
        assert response1.status_code == 200
        
        # Upload second video with same filename
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("duplicate.mp4", video_file, "video/mp4")}
            data = {"projectId": created_project.id}
            
            response2 = test_client.post("/upload-video", files=files, data=data)
        
        assert response2.status_code == 200
        
        # Should handle duplicates (rename or error)
        assert response1.json()["id"] != response2.json()["id"]
    
    def test_video_upload_project_assignment(self, test_client, test_db_session, sample_test_video_file):
        """Test automatic project assignment for central store"""
        # Upload without specific project (should go to central store)
        with open(sample_test_video_file, "rb") as video_file:
            files = {"file": ("central_store.mp4", video_file, "video/mp4")}
            
            response = test_client.post("/upload-video", files=files)
        
        assert response.status_code == 200
        response_data = response.json()
        
        # Should assign to central store project
        assert "projectId" in response_data
        
        # Verify project exists in database
        from models import Project
        project = test_db_session.query(Project).filter_by(
            id=response_data["projectId"]
        ).first()
        assert project is not None
    
    def test_video_metadata_persistence(self, test_client, test_db_session, created_project, sample_test_video_file):
        """Test that video metadata is properly persisted"""
        with patch('services.ground_truth_service.GroundTruthService.extract_metadata') as mock_extract:
            mock_extract.return_value = {
                "duration": 45.5,
                "fps": 29.97,
                "resolution": "1920x1080",
                "frame_count": 1364
            }
            
            with open(sample_test_video_file, "rb") as video_file:
                files = {"file": ("metadata_persist.mp4", video_file, "video/mp4")}
                data = {"projectId": created_project.id}
                
                response = test_client.post("/upload-video", files=files, data=data)
            
            video_id = response.json()["id"]
            
            # Check database persistence
            from models import Video
            video = test_db_session.query(Video).filter_by(id=video_id).first()
            
            assert video.duration == 45.5
            assert video.fps == 29.97
            assert video.resolution == "1920x1080"


class TestVideoProcessingStatusUpdates:
    """Test processing status updates throughout the workflow"""
    
    def test_processing_status_transitions(self, test_db_session, created_video):
        """Test valid processing status transitions"""
        # Test transition: pending -> processing
        created_video.processing_status = "processing"
        test_db_session.commit()
        test_db_session.refresh(created_video)
        assert created_video.processing_status == "processing"
        
        # Test transition: processing -> completed
        created_video.processing_status = "completed"
        created_video.ground_truth_generated = True
        test_db_session.commit()
        test_db_session.refresh(created_video)
        assert created_video.processing_status == "completed"
        assert created_video.ground_truth_generated is True
    
    def test_processing_status_failure_handling(self, test_db_session, created_video):
        """Test processing failure status"""
        created_video.processing_status = "failed"
        test_db_session.commit()
        test_db_session.refresh(created_video)
        
        assert created_video.processing_status == "failed"
        assert created_video.ground_truth_generated is False
    
    def test_processing_status_api_endpoint(self, test_client, created_video):
        """Test API endpoint for checking processing status"""
        response = test_client.get(f"/videos/{created_video.id}/status")
        
        assert response.status_code == 200
        status_data = response.json()
        
        assert "processingStatus" in status_data
        assert "groundTruthGenerated" in status_data
        assert status_data["processingStatus"] == "pending"


class TestGroundTruthGeneration:
    """Test ground truth generation workflow"""
    
    @patch('services.ground_truth_service.GroundTruthService.generate_ground_truth')
    def test_ground_truth_generation_workflow(self, mock_generate, test_db_session, created_video):
        """Test ground truth generation updates video status"""
        # Mock ground truth generation
        mock_generate.return_value = [
            {
                "timestamp": 1.0,
                "class_label": "pedestrian",
                "x": 100, "y": 200, "width": 50, "height": 100,
                "confidence": 0.9
            }
        ]
        
        # Simulate ground truth service processing
        from services.ground_truth_service import GroundTruthService
        service = GroundTruthService()
        
        # Process video
        created_video.processing_status = "processing"
        test_db_session.commit()
        
        # Generate ground truth
        detections = service.generate_ground_truth(created_video.file_path)
        
        # Update status
        created_video.processing_status = "completed"
        created_video.ground_truth_generated = True
        test_db_session.commit()
        
        assert created_video.processing_status == "completed"
        assert created_video.ground_truth_generated is True
    
    def test_ground_truth_object_creation(self, test_db_session, created_video):
        """Test ground truth objects are created correctly"""
        from models import GroundTruthObject
        
        # Create sample ground truth objects
        detections = [
            {
                "timestamp": 1.0,
                "class_label": "pedestrian",
                "x": 100, "y": 200, "width": 50, "height": 100,
                "confidence": 0.9,
                "frame_number": 30
            },
            {
                "timestamp": 2.0,
                "class_label": "cyclist",
                "x": 150, "y": 250, "width": 60, "height": 120,
                "confidence": 0.85,
                "frame_number": 60
            }
        ]
        
        # Add ground truth objects
        for detection in detections:
            gt_obj = GroundTruthObject(
                video_id=created_video.id,
                **detection
            )
            test_db_session.add(gt_obj)
        
        test_db_session.commit()
        
        # Verify objects were created
        gt_objects = test_db_session.query(GroundTruthObject).filter_by(
            video_id=created_video.id
        ).all()
        
        assert len(gt_objects) == 2
        assert gt_objects[0].class_label == "pedestrian"
        assert gt_objects[1].class_label == "cyclist"